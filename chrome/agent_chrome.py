#!/usr/bin/env python3
"""agent-chrome: how an agent says why it uses Chrome and what a human must do, and how anyone asks what is open.

  agent-chrome authorize-tab "<why>" --visibility invisible|unfocused|focused --visibility-reason "<why this level>"
               --mode single|subagents [--project P]
  agent-chrome mark-as-needing-human "<what the human must do>"
  agent-chrome mark-as-human-done
  agent-chrome reply-to-human "<text>"
  agent-chrome wait-for-human [--timeout SECONDS]
  agent-chrome status [--mine] [--since 7d] [--project P] [--json]
  agent-chrome open-profile-window [--project P]

The Chrome kit (my-setup chrome/, skill chrome). --visibility, enforced by the kit's hook and launcher:
  invisible  only a headless Chrome from the launcher (launch_headless.py): every Claude in Chrome tab is refused;
  unfocused  Claude in Chrome tabs, in the background (never brought to the front);
  focused    the same, and when the session marks its tab as needing a human, the kit brings it to the front once.
--mode: where the human answers. single: in the terminal (the tab's side panel says so, no comment box); subagents:
in the tab's side panel, read by the agent that owns the tab (wait-for-human, or next to its tool calls).
The first five subcommands act for the key that runs them: the Claude session ($CLAUDE_CODE_SESSION_ID, set by Claude
Code in every Bash call) and, in a subagent, its agent id (--agent-id, which the kit's hook adds to every agent-chrome
command a subagent runs; $CHROME_AGENT_ID too); status and open-profile-window work anywhere. The job is $JR_JOB. Reads and writes
~/opt/my-setup/state/chrome/ (chrome_kit: open.json, history/, sessions/, windows/) and reads `ps`.
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome_kit as kit  # noqa: E402

PROG = 'agent-chrome'
NO_SESSION = 'run this inside a Claude Code session ($CLAUDE_CODE_SESSION_ID is not set)'
AUTHORIZE_HELP = (f'  {PROG} authorize-tab "<why, in words the human understands>" --visibility invisible|unfocused|focused '
                  '--visibility-reason "<why this level>" [--project P]\n'
                  '  invisible: a headless Chrome from the launcher only; unfocused: Claude in Chrome tabs in the background; '
                  'focused: also brought to the front once when marked as needing a human (mark-as-needing-human).')
CHROME_BIN = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
EXT_ID = 'hfnfcdbehfbggjaccimmnolmhdkbfdie'   # "Agent tab notes": the "key" in extension/manifest.json


def hm(ts) -> str:
    return time.strftime('%d %b %H:%M', time.localtime(ts or 0))


def table(header: list, l_rows: list):
    l_rows = [[str(x if x is not None else '') for x in r] for r in l_rows]
    w = [max([len(h)] + [len(r[i]) for r in l_rows]) for i, h in enumerate(header)]
    for r in [header] + l_rows:
        print('  '.join(x.ljust(w[i]) for i, x in enumerate(r)).rstrip())


# ---------------------------------------------------------------- status: what is open (or was), by whom, why
def status(a, sid: str | None):
    # --mine: the session's authorized project, else the current folder's
    project = a.project or ((kit.session(sid).get('project') or kit.project_of(os.getcwd())) if a.mine else None)
    if a.since:
        m = re.fullmatch(r'(\d+)([mhd])', a.since)
        if not m:
            sys.exit(f'{PROG} status: --since takes 30m, 12h or 7d')
        since = time.time() - int(m.group(1)) * {'m': 60, 'h': 3600, 'd': 86400}[m.group(2)]
        l_r = []
        for f in sorted(kit.HISTORY.glob('*.jsonl')):
            if f.stem >= time.strftime('%Y-%m', time.gmtime(since)):
                for line in f.read_text().splitlines():
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r['ts'] >= since and (not project or r.get('project') == project):
                        l_r.append(r)
        if a.json:
            print(json.dumps(l_r, indent=1, ensure_ascii=False))
            return
        table(['when', 'event', 'session', 'agent', 'project', 'job', 'tab', 'url', 'purpose', 'visibility', 'needs human / message'],
              [[hm(r['ts']), r['event'], (r.get('session_id') or '')[:8], r.get('agent_id') or '', r.get('project'), r.get('job'), r.get('tab_id'),
                (r.get('url') or '')[:50], (r.get('purpose') or '')[:50], r.get('visibility') or '',
                r.get('needs_human') or r.get('message') or '']
               for r in l_r])
        return

    kit.correct({'session_id': sid, 'cwd': os.getcwd()})
    d_open = kit.read_open()
    l_e = sorted([e for e in d_open.values() if not project or e.get('project') == project], key=lambda e: e.get('opened_ts') or 0)
    l_p = [] if a.mine else kit.chrome_processes()
    if a.json:
        print(json.dumps({'tabs': l_e, 'processes': l_p}, indent=1, ensure_ascii=False))
        return
    if project and not l_e:
        print(f'{PROG} status: nothing open for project {project}')
    else:
        print(f'Agent tabs open now{" for project " + project if project else ""} ({len(l_e)})')
        table(['opened', 'session', 'agent', 'mode', 'project', 'job', 'profile', 'tab', 'url', 'purpose', 'visibility',
               'why that visibility', 'NEEDS HUMAN', 'reach it'],
              [[hm(e.get('opened_ts')), 'this session' if sid and e.get('session_id') == sid else (e.get('session_id') or '')[:8],
                e.get('agent_id') or '', e.get('mode') or '', e.get('project'), e.get('job'), e.get('profile'), str(e.get('tab_id'))[:12], (e.get('url') or '')[:50],
                (e.get('purpose') or '')[:50], e.get('visibility') or '', (e.get('visibility_reason') or '')[:40],
                e.get('needs_human') or '', e.get('reply_to') or ''] for e in l_e])
    if a.mine:
        return
    # a Chrome the kit knows: the launcher's (headless:<dir>) or the password layer's visible one (visible:<dir>)
    s_kit = {(e.get('profile') or '').split(':', 1)[1] for e in d_open.values()
             if (e.get('profile') or '').startswith(('headless:', 'visible:'))}
    for f in sorted(kit.HISTORY.glob('*.jsonl'))[-2:]:   # a visible Chrome a script recorded ("window": the password layer's)
        for line in f.read_text().splitlines():
            if '"window"' in line and '"visible:' in line:
                try:
                    s_kit.add(json.loads(line)['profile'].split(':', 1)[1])
                except (ValueError, KeyError, AttributeError, IndexError):
                    pass
    print(f'\nChrome processes ({len(l_p)})')
    table(['pid', 'running since', 'kind', 'data folder', 'in the kit'],
          [[p['pid'], hm(p['start_ts']), p['kind'], p['data_dir'] or '', 'yes' if p['data_dir'] in s_kit else
            ('' if p['kind'] == "user's Chrome" else 'NO: not started by the launcher')] for p in l_p])
    n_vis = sum(p['kind'] != 'headless' for p in l_p)
    if n_vis > 1:
        print(f'\nBLIND: {n_vis} visible Chrome instances: macOS window scripts (AppleScript) may see the wrong one; '
              'never report a window "closed (checked)" from them until the extra ones are quit.')


# ---------------------------------------------------------------- open-profile-window
def frontmost() -> str:
    r = subprocess.run(['osascript', '-e', 'tell application "System Events" to get name of first process whose frontmost is true'],
                       capture_output=True, text=True)
    return r.stdout.strip() or f'? ({r.stderr.strip()[:60]})'


def front_window() -> str:
    # Guarded: a bare `tell application "Google Chrome"` STARTS Chrome when it is not running, with this process's
    # environment (1 Nov 2026: a test run started the user's Chrome with the test's CHROME_STATE; every native host
    # Chrome then started wrote to the test's folder, and the bar never showed).
    r = subprocess.run(['osascript', '-e', 'if application "Google Chrome" is running then tell application "Google Chrome" to get id of window 1'],
                       capture_output=True, text=True)
    return r.stdout.strip()


def open_profile_window(project: str, sid: str | None, cwd: str, ctx: dict):
    """Claude in Chrome's profile is not connected: open a window of the session's profile (else the project's:
    Claude - LinkedIn for job-applications, Claude - Facebook for marketplace-seller, Claude - Bybit & Oxylabs for
    trading-bot, else Claude - general), only when that profile has no window, without taking focus; its first tab
    names the project, and the kit extension makes it the project's agent window. The one sanctioned way to open a visible Chrome window from the shell (the
    hook refuses others). Exits non-zero with the reason if refused."""
    me = f'{PROG} open-profile-window'
    d_sess = kit.session(sid)
    profile = d_sess.get('profile') or kit.profile_for(cwd, project)
    l_ok = next((l for n, l in kit.D_DEVICE.values() if n == profile), None)
    if l_ok and project not in kit.projects_of(l_ok):
        sys.exit(f'{me}: refused: "{profile}" is only for {" or ".join(sorted(kit.projects_of(l_ok)))} (project here: {project})')
    folder = kit.profile_folders().get(profile)
    if not folder or folder == 'Default':   # Default: the user's own profile, never
        sys.exit(f'{me}: no Chrome profile named "{profile}" in {kit.LOCAL_STATE}')
    if not any(p['kind'] == "user's Chrome" for p in kit.chrome_processes()):
        sys.exit(f"{me}: Chrome is not running: ask the human to start it (starting it from here would also reopen "
                 "the user's own profile)")
    l_win = kit.profile_windows(profile)
    if l_win:
        print(f'{me}: "{profile}" already has window(s) {l_win}: nothing opened. If Claude in Chrome is still not '
              'connected, ask the human to check the Claude extension in that window.')
        return
    if l_win is None and kit.profile_active(profile):   # no report from its extension, but Chrome says it has a window
        print(f'{me}: "{profile}" ({folder}) already has a window (Chrome\'s Local State, last_active_profiles), but its '
              '"Agent tab notes" extension does not report it: nothing opened. Ask the human to check, in that window, '
              'chrome://extensions: "Agent tab notes" enabled, no "Errors" button (else Reload), and the Claude extension.')
        return
    url = f'chrome-extension://{EXT_ID}/window.html?' + urllib.parse.urlencode({'project': project, 'profile': profile})
    # The binary hands --profile-directory to the running Chrome (one more window); `open -g -a` would drop the
    # arguments of an app already running. Tests replace the command ($CHROME_WINDOW_CMD).
    cmd = [os.environ.get('CHROME_WINDOW_CMD') or CHROME_BIN, f'--profile-directory={folder}', url]
    # Measured 2026-11-01: both the binary and `open -g -n -a … --args` bring Chrome forward (a frontmost app, or the
    # front Chrome window when the user is in Chrome): so the focus is given back below.
    before, win_before = frontmost(), front_window()
    t0 = time.monotonic()
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    l_front, given_back = [], False
    while time.monotonic() - t0 < 3:   # frontmost app, every 0.2 s for 3 s: did Chrome take the focus?
        f = frontmost()
        l_front.append(f)
        if f != before and f == 'Google Chrome' and not given_back and before != 'Google Chrome':
            subprocess.run(['osascript', '-e', f'tell application "System Events" to set frontmost of process "{before}" to true'],
                           capture_output=True)
            given_back = True
        time.sleep(0.2)
    if before == 'Google Chrome' and win_before and front_window() != win_before:   # the user was in Chrome
        subprocess.run(['osascript', '-e', f'tell application "Google Chrome" to set index of window id {win_before} to 1'],
                       capture_output=True)
        given_back = True
    l_win = None
    while time.monotonic() - t0 < 20 and not l_win:   # the kit extension of that profile reports its window
        l_win = kit.profile_windows(profile)
        time.sleep(0.5)
    kit.record([{'event': 'window', 'profile': profile, 'url': url, 'purpose': d_sess.get('purpose')}], ctx)
    stole = sorted(set(l_front) - {before})
    print(f'{me}: opened "{profile}" ({folder}) for project {project}: '
          + (f'window {l_win}' if l_win else 'no report from its "Agent tab notes" extension yet (not loaded in that profile?)')
          + f'. Frontmost app before: {before}; during 3 s: {", ".join(stole) if stole else "unchanged"}'
          + (f'; focus given back to {before}' + (f' (window {win_before})' if before == 'Google Chrome' else '') if given_back else '') + '.')


# ---------------------------------------------------------------- wait-for-human
WAIT_MAX = 300


def wait_for_human(a, sid: str, aid: str, me: str):
    """Block until a comment for this key's tab arrives (exit 0, printed, marked delivered) or the timeout (exit 2)."""
    t = a.timeout
    if not 1 <= t <= WAIT_MAX:
        sys.exit(f'{me}: --timeout takes 1 to {WAIT_MAX} seconds')
    end = time.monotonic() + t
    while True:
        l_c = kit.take_comments(sid, aid)
        if l_c:
            for c in l_c:
                print(f'{(c.get("dt") or "")[11:16]} UTC, tab {c.get("tab_id")} ({(c.get("url") or "")[:60]}): {c.get("text")}')
            print(f'(from the user, typed in the side panel of your tab; answer on the tab with {PROG} reply-to-human "<text>")')
            sys.exit(0)
        if time.monotonic() >= end:
            print(f'{me}: no comment in {t} s')
            sys.exit(2)
        time.sleep(1)


# ---------------------------------------------------------------- the CLI
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=PROG, description=__doc__.split('\n')[0],
                                 epilog='Skill chrome. Record: ~/opt/my-setup/state/chrome/.')
    ap.add_argument('--agent-id', metavar='ID', help="a subagent's id: the kit's hook adds it to every agent-chrome command "
                                                     'a subagent runs (never type it yourself); else $CHROME_AGENT_ID')
    sub = ap.add_subparsers(dest='cmd', metavar='<subcommand>')
    p = sub.add_parser('authorize-tab', help='say why this session uses Chrome, and how visible (before opening a tab)',
                       description='Say why this Claude session uses Chrome, for which project, and how visible it may be. '
                                   'A human who must act is marked after opening the tab: mark-as-needing-human.')
    p.add_argument('why', metavar='WHY', help='why this session uses Chrome, in words the human understands')
    p.add_argument('--visibility', required=True, choices=kit.VISIBILITIES,
                   help='invisible: headless only (the launcher; Claude in Chrome refused); unfocused: Claude in Chrome '
                        'tabs in the background; focused: also brought to the front once, when marked as needing a human')
    p.add_argument('--visibility-reason', required=True, metavar='REASON', help='why this level, in free text')
    p.add_argument('--mode', required=True, choices=kit.MODES,
                   help='where the human answers: single = in the terminal (the side panel says so, no comment box); '
                        'subagents = in the tab\'s side panel, read by the agent that owns the tab (wait-for-human)')
    p.add_argument('--project', metavar='P', help='the project the tab is for: required outside ~/dev/<repo> and '
                                                  '~/opt/<repo>; inside, <repo> (another value is refused)')
    p = sub.add_parser('mark-as-needing-human', help="a human must act in this session's tab now",
                       description="A human must act in this session's tab now: shown on the tab as NEEDS HUMAN (and, "
                                   'authorized focused, the tab is brought to the front once). If nobody acts within 2 h, '
                                   'the kit closes the tab ("expired") and tells the session at its next tool call.')
    p.add_argument('what', metavar='WHAT', help='what the human must do')
    sub.add_parser('mark-as-human-done', help="the human's part is over", description="The human's part is over: NEEDS HUMAN cleared.")
    p = sub.add_parser('reply-to-human', help="answer the human's comment, shown on the tab",
                       description="Answer the human's comment (typed on the tab): shown on this session's tabs.")
    p.add_argument('text', metavar='TEXT', help='your answer')
    p = sub.add_parser('wait-for-human', help="wait for the human's comment on your tab (mode subagents)",
                       description="Block until the human writes in your tab's side panel (mode subagents): prints the "
                                   'comment(s) and marks them delivered. Exit 0: a comment; 2: the timeout. Loop on it '
                                   'while you check your page between calls.')
    p.add_argument('--timeout', type=int, default=30, metavar='SECONDS', help=f'default 30, at most {WAIT_MAX}')
    p = sub.add_parser('status', help='what is open now (agent tabs, Chrome processes), or the history',
                       description='What agents have open now (tabs and Chrome processes), or the history with --since.')
    p.add_argument('--mine', action='store_true', help="only this session's authorized project, else the current folder's "
                                                       '(ask this before opening a tab)')
    p.add_argument('--since', metavar='PERIOD', help='the history over this period: 30m, 12h, 7d')
    p.add_argument('--project', metavar='P', help='only this project')
    p.add_argument('--json', action='store_true', help='JSON')
    p = sub.add_parser('open-profile-window', help="Claude in Chrome's profile not connected: open its window, in the background",
                       description=open_profile_window.__doc__.split('Exits')[0].strip())
    p.add_argument('--project', metavar='P', help="this project instead of the session's authorized one, else the current folder's")
    return ap


def authorized_project(given: str | None, cwd: str) -> str:
    """--project of authorize-tab: inside ~/dev/<repo> or ~/opt/<repo> it is <repo> (given or not); elsewhere required."""
    repo = kit.repo_of(cwd)
    if repo and given and given != repo:
        sys.exit(f'{PROG} authorize-tab: refused: --project {given}, but this folder is project {repo} ({cwd}): '
                 f'run it from ~/dev/{given}, or leave --project out')
    if not (repo or given):
        sys.exit(f'{PROG} authorize-tab: --project is required outside ~/dev/<repo> and ~/opt/<repo> (here: {cwd}): '
                 'say which project this tab is for')
    return repo or given


def main(argv: list | None = None):
    ap = parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return
    me = f'{PROG} {a.cmd}'
    sid = os.environ.get('CLAUDE_CODE_SESSION_ID')
    try:
        aid = kit.agent_id(a.agent_id or os.environ.get('CHROME_AGENT_ID'))
    except ValueError as e:
        sys.exit(f'{me}: {e}')
    d_sess = kit.session(sid, aid)
    me_key = f'{(sid or "")[:8]}' + (f' (subagent {aid})' if aid else '')
    pwd = os.environ.get('PWD') or ''   # the folder as the shell names it (~/dev/my-context is a link), if it is this one
    cwd = pwd if pwd and Path(pwd).resolve() == Path(os.getcwd()).resolve() else os.getcwd()
    ctx = dict(session_id=sid, agent_id=aid or None, cwd=os.getcwd(), job=os.environ.get('JR_JOB'), project=d_sess.get('project'),
               mode=d_sess.get('mode'))
    if a.cmd == 'status':
        status(a, sid)
        return
    if a.cmd == 'open-profile-window':
        open_profile_window(a.project or d_sess.get('project') or kit.project_of(os.getcwd()), sid, os.getcwd(), ctx)
        return
    if not sid:
        sys.exit(f'{me}: {NO_SESSION}')
    if a.cmd == 'authorize-tab':
        project = authorized_project(a.project, cwd)
        prof = kit.session(sid).get('profile')   # a profile this session already fixed must be allowed for the project
        l_ok = next((l for n, l in kit.D_DEVICE.values() if n == prof), None)
        if l_ok and project not in kit.projects_of(l_ok):
            sys.exit(f'{me}: refused: this session uses "{prof}", which is only for '
                     f'{" or ".join(sorted(kit.projects_of(l_ok)))}; start another Claude session for project {project}')
        kit.update_session(sid, aid, purpose=a.why, project=project, visibility=a.visibility,
                           visibility_reason=a.visibility_reason, visible_because=None, mode=a.mode)
        ctx.update(project=project, mode=a.mode)
        d = dict(purpose=a.why, visibility=a.visibility, visibility_reason=a.visibility_reason, mode=a.mode)
        kit.record([{'event': 'claim', **d, 'needs_human': d_sess.get('needs_human')}], ctx, fanout=d)
        print(f'{me}: recorded for {me_key}, project {project}: {a.why!r}, visibility {a.visibility} '
              f'({a.visibility_reason}), mode {a.mode}' + (f'. A human must act in the tab: {PROG} mark-as-needing-human "<what>" '
                                            'after opening it' if a.visibility != 'invisible' else
                                            '. Claude in Chrome tabs are refused; start the Chrome with the launcher')
              + (f'. The human answers in the tab\'s side panel: loop on {PROG} wait-for-human while you check the page'
                 if a.mode == 'subagents' else '. The human answers in the terminal (the side panel says so)'))
    elif a.cmd == 'mark-as-needing-human':
        if not d_sess.get('purpose'):
            sys.exit(f'{me}: refused: this session has not said why it uses Chrome: {PROG} authorize-tab "<why>" '
                     '--visibility … --visibility-reason "…"')
        kit.update_session(sid, aid, needs_human=a.what)
        kit.record([{'event': 'needs_human', 'purpose': d_sess['purpose'], 'visibility': d_sess.get('visibility'),
                     'visibility_reason': d_sess.get('visibility_reason'), 'needs_human': a.what}], ctx,
                   fanout={'purpose': d_sess['purpose'], 'needs_human': a.what})
        print(f'{me}: recorded for {me_key}: NEEDS HUMAN: {a.what}'
              + ('; its tab is brought to the front once (authorized focused)' if d_sess.get('visibility') == 'focused' else '')
              + f'. If nobody acts, the kit closes it at {hm(time.time() + kit.NEEDS_HUMAN_TTL)} '
                f'({kit.ttl_text()}) and tells this session ("expired").'
              + (f' The human may answer in the side panel: {PROG} wait-for-human' if d_sess.get('mode') == 'subagents' else ''))
    elif a.cmd == 'mark-as-human-done':
        kit.update_session(sid, aid, needs_human=None)
        kit.record([{'event': 'done', 'purpose': d_sess.get('purpose'), 'needs_human': None}], ctx, fanout={'needs_human': None})
        print(f'{me}: recorded for {me_key}: nothing waits for a human any more')
    elif a.cmd == 'reply-to-human':
        kit.record([{'event': 'message', 'purpose': d_sess.get('purpose'), 'needs_human': d_sess.get('needs_human'),
                     'message': a.text}], ctx, fanout={'message': a.text})
        print(f'{me}: recorded for {me_key}: shown on its tab(s)')
    elif a.cmd == 'wait-for-human':
        wait_for_human(a, sid, aid, me)


if __name__ == '__main__':
    main()
