"""The Chrome kit's shared code: where agents' Chrome use is kept, who is asking, which Chromes run.

Kept in $CHROME_STATE (default ~/opt/my-setup/state/chrome/; tests set a scratch folder):
  open.json              what is open now: {tab_id: entry}, written under a lock with an atomic rename. Corrected from
                         every Claude in Chrome "Available tabs" answer (hook.py); entries older than the browser's
                         start, or headless ones whose Chrome is gone, are dropped (correct()).
  history/YYYY-MM.jsonl  every event, append only, one file per month (UTC).
  comments.jsonl         the user's comments typed on a tab (written by the extension): ts, dt, session_id, agent_id,
                         tab_id, url, text.
  sessions/<key>.json    per key (below): its authorization (purpose, project, visibility, visibility_reason, mode),
                         needs_human, how far its comments were read; the main key also holds the browser the session
                         selected (one per session: its subagents share Claude in Chrome's connection). Internal to the kit.
  sessions/<key>.notices.jsonl  what the kit must tell the key at its next hook call (today: a tab of its that
                         expired), written by native_host.py, read and removed by hook.py.
The key (2 Nov 2026, "multiple-subagents mode"): (session_id, agent_id); agent_id is empty for the main agent and is
Claude Code's id of a subagent (the hook's input "agent_id"; agent-chrome gets it as --agent-id, which the hook adds).
Its file name: <session_id> for the main agent, <session_id>.<agent_id> for a subagent.
Fields, in this order: ts, dt, [opened_ts, opened_dt: open.json only], event (open|navigate|claim|needs_human|done|
message|close|expired|window), session_id, agent_id (null: the main agent), project, job, machine, cwd, profile,
device_id, tab_id, url, purpose, visibility (invisible|unfocused|focused), visibility_reason, mode (single|subagents:
where the human answers, the terminal or the tab's side panel), needs_human, expires_ts, message, reply_to.
expires_ts: when a tab that needs a human is closed if nobody acted (needs_human set + NEEDS_HUMAN_TTL; set by
record(), so every writer gets it); the extension closes it then and the record says "expired". Headless tabs: profile "headless:<data folder>", tab_id = the CDP target id, device_id null; a
visible Chrome a script records itself (secrets-and-account-migration's pwlayer): profile "visible:<data folder>".
Python 3.9+ (macOS's /usr/bin/python3), standard library only.
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE = Path(os.environ.get('CHROME_STATE') or Path.home() / 'opt/my-setup/state/chrome')
OPEN, HISTORY, COMMENTS, SESSIONS = STATE / 'open.json', STATE / 'history', STATE / 'comments.jsonl', STATE / 'sessions'
FIELDS = ['ts', 'dt', 'event', 'session_id', 'agent_id', 'project', 'job', 'machine', 'cwd', 'profile', 'device_id',
          'tab_id', 'url', 'purpose', 'visibility', 'visibility_reason', 'mode', 'needs_human', 'expires_ts', 'message',
          'reply_to']
MODES = ('single', 'subagents')   # authorize-tab --mode: the human answers in the terminal, or in the tab's side panel
RE_AGENT = re.compile(r'[A-Za-z0-9_-]{1,64}')   # a subagent's id (Claude Code: 17 hex characters)
# A tab kept for a human is closed after this, if nobody acted: 2 h, the deadline the user set for auto-job-apply
# (21 Oct 2026). $CHROME_NEEDS_HUMAN_TTL (seconds) overrides it for tests, in the process that marks the need.
NEEDS_HUMAN_TTL = int(os.environ.get('CHROME_NEEDS_HUMAN_TTL') or 7200)
GONE = ('close', 'expired')   # events that end a tab
VISIBILITIES = ('invisible', 'unfocused', 'focused')  # authorize-tab --visibility: what the hook lets the session do
FIELDS_OPEN = FIELDS[:2] + ['opened_ts', 'opened_dt'] + FIELDS[2:]
RE_CHROME_MAIN = re.compile(r'MacOS/Google Chrome( |$)')
# deviceId -> (profile name, folders of the only projects allowed to use it, or None = any): AGENTS_LOCAL.md "Chrome profiles"
# Two profiles since 2026-11-07 (the user): "Claude - LinkedIn" and "Claude - Facebook" merged into "Claude - general"
D_DEVICE = {
    '331a94e7-f123-4e09-a755-cdc63980187f': ('Claude - general', None),
    'aeb98e0d-7abb-4b30-88be-b700e160d76e': ('Claude - Bybit & Oxylabs', ('/dev/trading-bot', '/opt/trading-bot')),
}
# Chrome's top-level "Local State" (not inside a profile folder: profile folders are never read): profile names -> folders
LOCAL_STATE = Path(os.environ.get('CHROME_LOCAL_STATE') or Path.home() / 'Library/Application Support/Google/Chrome/Local State')
WINDOWS = STATE / 'windows'   # <profile>.json: the windows of a profile, as its "Agent tab notes" extension sees them


def utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def machine_name() -> str:
    """This machine's name: skill "machine-name" (copy it identically)."""
    name = (os.environ.get("JR_MACHINE_NAME") or (
        subprocess.run(["scutil", "--get", "HostName"], capture_output=True, text=True).stdout
        if sys.platform == "darwin" else Path("/etc/hostname").read_text())).strip().split(".")[0]
    if not re.fullmatch(r"[A-Za-z0-9-]+", name):
        raise RuntimeError("no machine name: macOS sudo scutil --set HostName <name>; Linux sudo hostnamectl set-hostname <name>")
    return name


def repo_of(cwd: str) -> str | None:
    """<repo> when cwd is inside ~/dev/<repo> or ~/opt/<repo> (the folder as given, or resolved: ~/dev/my-context is a
    link), else None."""
    for c in {cwd or '', str(Path(cwd or '.').resolve())}:
        for base in (Path.home() / 'dev', Path.home() / 'opt'):
            try:
                parts = Path(c).relative_to(base).parts
            except ValueError:
                continue
            if parts:
                return parts[0]
    return None


def projects_of(l_ok) -> set:
    """The project names of a profile's allowed folders ('/dev/job-applications' -> 'job-applications')."""
    return {Path(x).name for x in l_ok or ()}


def project_of(cwd: str) -> str:
    """The basename of the git toplevel holding cwd (a .git folder or file: worktrees too), else of cwd."""
    p = Path(cwd or '.').resolve()
    for d in [p, *p.parents]:
        if (d / '.git').exists():
            return d.name
    return p.name


def reply_to(session_id: str | None, job: str | None) -> str | None:
    """How the user reaches whoever opened the tab: its tmux window (the hook inherits the session's pane), and how
    to resume the session; a job: its log folder."""
    l_to = []
    if os.environ.get('TMUX_PANE'):
        r = subprocess.run(['tmux', 'display-message', '-p', '-t', os.environ['TMUX_PANE'], 'tmux #S:#I (#W)'],
                           capture_output=True, text=True)
        l_to += [r.stdout.strip()] if r.returncode == 0 and r.stdout.strip() else []
    if session_id:
        l_to.append(f'asm resume {session_id}')
    elif job:
        l_to.append(f'log: ~/opt/job-runner/logs/{job}/')
    return ' · '.join(l_to) or None


@contextlib.contextmanager
def locked(path: Path):
    """An exclusive lock on <path>.lock: one writer at a time (parallel tool calls run hooks in parallel)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(f'{path}.lock', 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def write_json(path: Path, d: dict):
    """Atomic: a reader never sees half a file."""
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


def read_open() -> dict:
    return read_json(OPEN)


def set_need(e: dict, need, ts: int):
    """e's needs_human becomes `need`; its deadline (expires_ts) starts when the need is new, goes with it."""
    if not need:
        e['expires_ts'] = None
    elif need != e.get('needs_human') or not e.get('expires_ts'):
        e['expires_ts'] = ts + NEEDS_HUMAN_TTL
    e['needs_human'] = need


def ttl_text(s: int | None = None) -> str:
    s = NEEDS_HUMAN_TTL if s is None else s
    return f'{s / 3600:g} h' if s >= 3600 else f'{s // 60} min' if s >= 60 else f'{s} s'


def row(ev: dict, d_ctx: dict) -> dict:
    """One history row in FIELDS order: the event's fields, then the context's (session, cwd…), then defaults."""
    d = {**d_ctx, **ev}
    d['ts'] = d.get('ts') or int(time.time())
    d['dt'] = utc(d['ts'])
    d['machine'] = d.get('machine') or machine_name()
    d['project'] = d.get('project') or project_of(d.get('cwd') or os.getcwd())
    d['agent_id'] = d.get('agent_id') or None   # null: the main agent
    if 'reply_to' not in d:
        d['reply_to'] = reply_to(d.get('session_id'), d.get('job'))
    return {k: d.get(k) for k in FIELDS}


def record(l_ev: list[dict], d_ctx: dict | None = None, fanout: dict | None = None) -> list[dict]:
    """Append events to the history and apply the tab ones to open.json, under one lock.
    An event with a tab_id updates (or opens, or on close removes) that tab's entry; fanout {field: value} also
    updates every open tab of d_ctx's session (a claim, a need, a message: what the tab shows)."""
    d_ctx = d_ctx or {}
    l_rows = [row(ev, d_ctx) for ev in l_ev]
    for r in l_rows:   # the need's deadline, in the history too
        if r['event'] == 'needs_human' and r['needs_human'] and not r['expires_ts']:
            r['expires_ts'] = r['ts'] + NEEDS_HUMAN_TTL
    with locked(OPEN):
        HISTORY.mkdir(parents=True, exist_ok=True)
        for r in l_rows:
            with open(HISTORY / f"{r['dt'][:7]}.jsonl", 'a') as f:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        d_open = read_open()
        for r in l_rows:
            if r['tab_id'] is None:
                continue
            key = str(r['tab_id'])
            if r['event'] in GONE:
                d_open.pop(key, None)
                continue
            old = d_open.get(key, {'opened_ts': r['ts'], 'opened_dt': r['dt']})
            # message stays until a new one; needs_human is always the latest (null = nothing needed), its deadline with it
            new = {**old, **{k: v for k, v in r.items() if v is not None and k not in ('needs_human', 'expires_ts')}}
            set_need(new, r['needs_human'], r['ts'])
            d_open[key] = {k: new.get(k) for k in FIELDS_OPEN}
        if fanout and l_rows:
            for key, e in d_open.items():
                if owner(e) == (d_ctx.get('session_id'), d_ctx.get('agent_id') or ''):
                    e.update({k: v for k, v in fanout.items() if k != 'needs_human'},
                             ts=l_rows[-1]['ts'], dt=l_rows[-1]['dt'], event=l_rows[-1]['event'])
                    if 'needs_human' in fanout:
                        set_need(e, fanout['needs_human'], l_rows[-1]['ts'])
        write_json(OPEN, d_open)
    return l_rows


def agent_id(aid: str | None) -> str:
    """A subagent's id as given (hook input, --agent-id, $CHROME_AGENT_ID), checked; '' for the main agent."""
    aid = (aid or '').strip()
    if aid and not RE_AGENT.fullmatch(aid):
        raise ValueError(f'not an agent id: {aid!r}')
    return aid


def owner(e: dict) -> tuple:
    """Who a tab (an open.json entry) or a comment belongs to: (session_id, agent_id or '')."""
    return e.get('session_id'), e.get('agent_id') or ''


def key_name(sid: str, aid: str = '') -> str:
    return f'{sid}.{aid}' if aid else sid


def who(aid: str) -> str:
    return f'subagent {aid}' if aid else 'the main agent'


def session(sid: str | None, aid: str = '') -> dict:
    return read_json(SESSIONS / f'{key_name(sid, aid)}.json') if sid else {}


def update_session(sid: str, aid: str = '', **kw) -> dict:
    f = SESSIONS / f'{key_name(sid, aid)}.json'
    with locked(f):
        d = {**read_json(f), **kw}
        write_json(f, d)
    return d


def take_comments(sid: str, aid: str, d_open: dict | None = None) -> list[dict]:
    """The user's comments for this key not given to it yet; marks them given (a byte offset in its sessions file,
    under its lock). A comment is the key's when it names the key (the native host copies the tab's session and agent),
    or, for an old row without a session, one of the key's open tabs and was written after that tab opened (Chrome
    reuses tab ids). Used by the hook (next to any tool call) and by agent-chrome wait-for-human."""
    if not COMMENTS.exists():
        return []
    d_open = read_open() if d_open is None else d_open
    f_sess = SESSIONS / f'{key_name(sid, aid)}.json'
    with locked(f_sess):
        d_sess = read_json(f_sess)
        off = d_sess.get('comments_offset', 0)
        with open(COMMENTS, 'rb') as f:
            f.seek(off)
            chunk = f.read()
        chunk = chunk[:chunk.rfind(b'\n') + 1]  # a line still being written waits for the next call
        if not chunk:
            return []
        l_mine = []
        for line in chunk.decode(errors='replace').splitlines():
            try:
                c = json.loads(line)
            except ValueError:
                continue
            tab = d_open.get(str(c.get('tab_id')))
            if (c.get('session_id') and owner(c) == (sid, aid)) or (
                    not c.get('session_id') and tab and owner(tab) == (sid, aid) and c.get('ts', 0) >= tab.get('opened_ts', 0)):
                l_mine.append(c)
        SESSIONS.mkdir(parents=True, exist_ok=True)
        write_json(f_sess, {**d_sess, 'comments_offset': off + len(chunk)})
    return l_mine


def comments_pending(sid: str, aid: str = '') -> bool:
    return COMMENTS.exists() and COMMENTS.stat().st_size > session(sid, aid).get('comments_offset', 0)


def profile_for(cwd: str, project: str | None = None) -> str:
    """The agent profile of a project (else of a folder): the one reserved for it (LinkedIn, Facebook), else
    "Claude - general"."""
    return next((n for n, l_ok in D_DEVICE.values() if l_ok and (project in projects_of(l_ok) if project
                 else any(x in cwd for x in l_ok))), 'Claude - general')


def profile_folders() -> dict:
    """{profile name: its folder name} from Chrome's Local State (profile.info_cache)."""
    d = read_json(LOCAL_STATE).get('profile', {}).get('info_cache', {})
    return {v.get('name'): k for k, v in d.items() if v.get('name')}


def alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def profile_windows(profile: str) -> list | None:
    """The window ids of this profile, as its kit extension reported them (windows/<profile>.json, written by
    native_host.py while the extension runs); None when no running extension reports for this profile."""
    d = read_json(WINDOWS / f'{profile}.json')
    return d.get('windows', []) if d and alive(d.get('pid')) else None


def profile_active(profile: str) -> bool | None:
    """Does Chrome say this profile has a window? Chrome's Local State "profile.last_active_profiles": the profile
    folders with a window, kept by Chrome while it runs (a folder leaves when its last window closes; written ~10 s
    after a change). None when it cannot tell: no such list, or Local State not written since the user's Chrome
    started (a stale list from before a crash). The fallback when no extension reports (profile_windows)."""
    folder = profile_folders().get(profile)
    l_main = [p['start_ts'] for p in chrome_processes() if p['kind'] == "user's Chrome"]
    d = read_json(LOCAL_STATE).get('profile', {})
    try:
        fresh = bool(l_main) and LOCAL_STATE.stat().st_mtime >= min(l_main) - 5
    except FileNotFoundError:
        fresh = False
    if not folder or not fresh or 'last_active_profiles' not in d:
        return None
    return folder in d['last_active_profiles']


def chrome_processes() -> list[dict]:
    """Every Chrome main process: pid, start ts, kind (the user's Chrome, visible with its own data folder, headless)."""
    l = []
    out = Path(os.environ['CHROME_TEST_PS']).read_text() if os.environ.get('CHROME_TEST_PS') else \
        subprocess.run(['ps', '-axo', 'pid=,etime=,command='], capture_output=True, text=True).stdout  # tests: a fake ps
    now = int(time.time())
    for line in out.splitlines():
        pid, etime, cmd = line.split(None, 2)
        if not RE_CHROME_MAIN.search(cmd) or 'Helper' in cmd or '--type=' in cmd:
            continue
        # etime: [[dd-]hh:]mm:ss, locale-free (lstart is in the user's language)
        d, _, hms = etime.rpartition('-')
        parts = [int(x) for x in hms.split(':')]
        secs = int(d or 0) * 86400 + sum(x * 60 ** i for i, x in enumerate(reversed(parts)))
        m = re.search(r'--user-data-dir=(\S+)', cmd)
        kind = 'headless' if '--headless' in cmd else 'visible' if m else "user's Chrome"
        l.append({'pid': int(pid), 'start_ts': now - secs, 'kind': kind, 'data_dir': m.group(1) if m else None})
    return l


def correct(d_ctx: dict | None = None) -> int:
    """Drop open.json entries that cannot be open any more: Claude in Chrome tabs older than the user's Chrome
    (it restarted; Chrome reuses tab ids), headless tabs whose Chrome is gone. Each drop is a close in the history.
    Returns how many were dropped."""
    l_proc = chrome_processes()
    l_main = [p['start_ts'] for p in l_proc if p['kind'] == "user's Chrome"]
    s_dirs = {p['data_dir'] for p in l_proc if p['data_dir']}
    l_close = []
    for e in read_open().values():
        prof = e.get('profile') or ''
        gone = (not l_main or e['opened_ts'] < min(l_main) - 5) if e.get('device_id') else \
            prof.startswith(('headless:', 'visible:')) and prof.split(':', 1)[1] not in s_dirs
        if gone:
            l_close.append({k: e.get(k) for k in FIELDS if k not in ('ts', 'dt', 'reply_to')} | {'event': 'close', 'ts': None, 'reply_to': e.get('reply_to')})
    if l_close:
        record(l_close, d_ctx)
    return len(l_close)
