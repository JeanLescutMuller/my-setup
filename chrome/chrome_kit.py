"""The Chrome kit's shared code: where agents' Chrome use is kept, who is asking, which Chromes run.

Kept in $CHROME_STATE (default ~/opt/my-setup/state/chrome/; tests set a scratch folder):
  open.json              what is open now: {tab_id: entry}, written under a lock with an atomic rename. Corrected from
                         every Claude in Chrome "Available tabs" answer (hook.py); entries older than the browser's
                         start, or headless ones whose Chrome is gone, are dropped (correct()).
  history/YYYY-MM.jsonl  every event, append only, one file per month (UTC).
  comments.jsonl         the user's comments typed on a tab (written by the extension): ts, dt, session_id, tab_id, url, text.
  sessions/<id>.json     per Claude session: its claim (purpose, needs_human, visible_because), the browser it
                         selected, how far its comments were read. Internal to the kit.
Fields, in this order: ts, dt, [opened_ts, opened_dt: open.json only], event (open|navigate|claim|needs_human|done|
message|close), session_id, project, job, machine, cwd, profile, device_id, tab_id, url, purpose, needs_human,
message, reply_to. Headless tabs: profile "headless:<data folder>", tab_id = the CDP target id, device_id null; a
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
FIELDS = ['ts', 'dt', 'event', 'session_id', 'project', 'job', 'machine', 'cwd', 'profile', 'device_id', 'tab_id',
          'url', 'purpose', 'needs_human', 'message', 'reply_to']
FIELDS_OPEN = FIELDS[:2] + ['opened_ts', 'opened_dt'] + FIELDS[2:]
RE_CHROME_MAIN = re.compile(r'MacOS/Google Chrome( |$)')


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


def row(ev: dict, d_ctx: dict) -> dict:
    """One history row in FIELDS order: the event's fields, then the context's (session, cwd…), then defaults."""
    d = {**d_ctx, **ev}
    d['ts'] = d.get('ts') or int(time.time())
    d['dt'] = utc(d['ts'])
    d['machine'] = d.get('machine') or machine_name()
    d['project'] = d.get('project') or project_of(d.get('cwd') or os.getcwd())
    if 'reply_to' not in d:
        d['reply_to'] = reply_to(d.get('session_id'), d.get('job'))
    return {k: d.get(k) for k in FIELDS}


def record(l_ev: list[dict], d_ctx: dict | None = None, fanout: dict | None = None) -> list[dict]:
    """Append events to the history and apply the tab ones to open.json, under one lock.
    An event with a tab_id updates (or opens, or on close removes) that tab's entry; fanout {field: value} also
    updates every open tab of d_ctx's session (a claim, a need, a message: what the tab shows)."""
    d_ctx = d_ctx or {}
    l_rows = [row(ev, d_ctx) for ev in l_ev]
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
            if r['event'] == 'close':
                d_open.pop(key, None)
                continue
            old = d_open.get(key, {'opened_ts': r['ts'], 'opened_dt': r['dt']})
            # message stays until a new one; needs_human is always the latest (null = nothing needed)
            new = {**old, **{k: v for k, v in r.items() if v is not None or k == 'needs_human'}}
            d_open[key] = {k: new.get(k) for k in FIELDS_OPEN}
        if fanout and l_rows:
            for key, e in d_open.items():
                if e.get('session_id') == d_ctx.get('session_id'):
                    e.update(fanout, ts=l_rows[-1]['ts'], dt=l_rows[-1]['dt'], event=l_rows[-1]['event'])
        write_json(OPEN, d_open)
    return l_rows


def session(sid: str | None) -> dict:
    return read_json(SESSIONS / f'{sid}.json') if sid else {}


def update_session(sid: str, **kw) -> dict:
    f = SESSIONS / f'{sid}.json'
    with locked(f):
        d = {**read_json(f), **kw}
        write_json(f, d)
    return d


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
