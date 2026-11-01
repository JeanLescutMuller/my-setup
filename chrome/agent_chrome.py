#!/usr/bin/env python3
"""agent-chrome: how an agent says why it uses Chrome and what a human must do, and how anyone asks what is open.

  agent-chrome authorize-tab "<why>" (--needs-human "<what>" | --visible-because "<why headless can't>") [--session ID]
  agent-chrome mark-as-needing-human "<what the human must do>"
  agent-chrome mark-as-human-done
  agent-chrome reply-to-human "<text>"
  agent-chrome status [--mine] [--since 7d] [--project P] [--json]
  agent-chrome open-profile-window [--project P]

The Chrome kit (my-setup chrome/, skill chrome). A Claude in Chrome tab is always visible, so authorize-tab needs
--needs-human or --visible-because (the hook refuses a new tab otherwise). The session is $CLAUDE_CODE_SESSION_ID (or
--session); the job is $JR_JOB. Reads and writes ~/opt/my-setup/state/chrome/ (chrome_kit: open.json, history/,
sessions/, windows/) and reads `ps`.
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
VISIBLE_HELP = ('A Claude in Chrome tab is always visible to the human, so also say either what they must do in it '
                '(--needs-human "<what>") or why a headless Chrome cannot do it (--visible-because "<why>", e.g. a '
                'logged-in profile such as WhatsApp or LinkedIn). If neither applies, use a headless Chrome from a script '
                '(skill chrome) instead.')
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
    project = a.project or (kit.project_of(os.getcwd()) if a.mine else None)
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
        table(['when', 'event', 'session', 'project', 'job', 'tab', 'url', 'purpose', 'needs human / message'],
              [[hm(r['ts']), r['event'], (r.get('session_id') or '')[:8], r.get('project'), r.get('job'), r.get('tab_id'),
                (r.get('url') or '')[:50], (r.get('purpose') or '')[:50], r.get('needs_human') or r.get('message') or '']
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
        table(['opened', 'session', 'project', 'job', 'profile', 'tab', 'url', 'purpose', 'NEEDS HUMAN', 'reach it'],
              [[hm(e.get('opened_ts')), 'this session' if sid and e.get('session_id') == sid else (e.get('session_id') or '')[:8],
                e.get('project'), e.get('job'), e.get('profile'), str(e.get('tab_id'))[:12], (e.get('url') or '')[:50],
                (e.get('purpose') or '')[:50], e.get('needs_human') or '', e.get('reply_to') or ''] for e in l_e])
    if a.mine:
        return
    # a Chrome the kit knows: the launcher's (headless:<dir>) or the password layer's visible one (visible:<dir>)
    s_kit = {(e.get('profile') or '').split(':', 1)[1] for e in d_open.values()
             if (e.get('profile') or '').startswith(('headless:', 'visible:'))}
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
    r = subprocess.run(['osascript', '-e', 'tell application "Google Chrome" to get id of window 1'], capture_output=True, text=True)
    return r.stdout.strip()


def open_profile_window(project: str, sid: str | None, cwd: str, ctx: dict):
    """Claude in Chrome's profile is not connected: open a window of the session's profile (else the project's:
    Claude - LinkedIn for job-applications, Claude - Facebook for marketplace-seller, else Claude - general), only
    when that profile has no window, without taking focus; its first tab names the project, and the kit extension
    makes it the project's agent window. The one sanctioned way to open a visible Chrome window from the shell (the
    hook refuses others). Exits non-zero with the reason if refused."""
    me = f'{PROG} open-profile-window'
    d_sess = kit.session(sid)
    profile = d_sess.get('profile') or kit.profile_for(cwd)
    l_ok = next((l for n, l in kit.D_DEVICE.values() if n == profile), None)
    if l_ok and not any(x in cwd for x in l_ok):
        sys.exit(f'{me}: refused: "{profile}" is only for {" or ".join(l_ok)}')
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


# ---------------------------------------------------------------- the CLI
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=PROG, description=__doc__.split('\n')[0],
                                 epilog='Skill chrome. Record: ~/opt/my-setup/state/chrome/.')
    sub = ap.add_subparsers(dest='cmd', metavar='<subcommand>')
    p = sub.add_parser('authorize-tab', help='say why this session opens a Claude in Chrome tab (before opening it)',
                       description='Say why this session opens a Claude in Chrome tab, and why it must be visible.')
    p.add_argument('why', metavar='WHY', help='why this session uses Chrome, in words the human understands')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--needs-human', metavar='WHAT', help='what the human must do in the tab (log in, solve a captcha, upload a file…)')
    g.add_argument('--visible-because', metavar='REASON', help="why a headless Chrome can't do it (a logged-in profile…)")
    p.add_argument('--session', metavar='ID', help='session id, if not in $CLAUDE_CODE_SESSION_ID')
    p = sub.add_parser('mark-as-needing-human', help='a human must act in this session\'s tab now',
                       description="A human must act in this session's tab now: shown on the tab as NEEDS HUMAN.")
    p.add_argument('what', metavar='WHAT', help='what the human must do')
    p.add_argument('--session', metavar='ID', help='session id, if not in $CLAUDE_CODE_SESSION_ID')
    p = sub.add_parser('mark-as-human-done', help="the human's part is over", description="The human's part is over: NEEDS HUMAN cleared.")
    p.add_argument('--session', metavar='ID', help='session id, if not in $CLAUDE_CODE_SESSION_ID')
    p = sub.add_parser('reply-to-human', help="answer the human's comment, shown on the tab",
                       description="Answer the human's comment (typed on the tab): shown on this session's tabs.")
    p.add_argument('text', metavar='TEXT', help='your answer')
    p.add_argument('--session', metavar='ID', help='session id, if not in $CLAUDE_CODE_SESSION_ID')
    p = sub.add_parser('status', help='what is open now (agent tabs, Chrome processes), or the history',
                       description='What agents have open now (tabs and Chrome processes), or the history with --since.')
    p.add_argument('--mine', action='store_true', help="only the current folder's project (ask this before opening a tab)")
    p.add_argument('--since', metavar='PERIOD', help='the history over this period: 30m, 12h, 7d')
    p.add_argument('--project', metavar='P', help='only this project')
    p.add_argument('--json', action='store_true', help='JSON')
    p = sub.add_parser('open-profile-window', help="Claude in Chrome's profile not connected: open its window, in the background",
                       description=open_profile_window.__doc__.split('Exits')[0].strip())
    p.add_argument('--project', metavar='P', help="this project instead of the current folder's")
    return ap


def main(argv: list | None = None):
    ap = parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return
    me = f'{PROG} {a.cmd}'
    sid = getattr(a, 'session', None) or os.environ.get('CLAUDE_CODE_SESSION_ID')
    ctx = dict(session_id=sid, cwd=os.getcwd(), job=os.environ.get('JR_JOB'))
    if a.cmd == 'status':
        status(a, sid)
        return
    if a.cmd == 'open-profile-window':
        open_profile_window(a.project or kit.project_of(os.getcwd()), sid, os.getcwd(), ctx)
        return
    if not sid:
        sys.exit(f'{me}: no session: run it from a Claude Code session ($CLAUDE_CODE_SESSION_ID), or pass --session')
    d_sess = kit.session(sid)
    if a.cmd == 'authorize-tab':
        kit.update_session(sid, purpose=a.why, needs_human=a.needs_human, visible_because=a.visible_because)
        kit.record([{'event': 'claim', 'purpose': a.why, 'needs_human': a.needs_human}], ctx,
                   fanout={'purpose': a.why, 'needs_human': a.needs_human})
        print(f'{me}: recorded for {sid[:8]}: {a.why!r}' + (f', NEEDS HUMAN: {a.needs_human}' if a.needs_human
                                                             else f', visible because: {a.visible_because}'))
    elif a.cmd == 'mark-as-needing-human':
        if not d_sess.get('purpose'):
            sys.exit(f'{me}: refused: this session has not said why it uses Chrome: {PROG} authorize-tab "<why>" '
                     f'--needs-human "{a.what}"')
        kit.update_session(sid, needs_human=a.what)
        kit.record([{'event': 'needs_human', 'purpose': d_sess['purpose'], 'needs_human': a.what}], ctx,
                   fanout={'purpose': d_sess['purpose'], 'needs_human': a.what})
        print(f'{me}: recorded for {sid[:8]}: NEEDS HUMAN: {a.what}')
    elif a.cmd == 'mark-as-human-done':
        kit.update_session(sid, needs_human=None)
        kit.record([{'event': 'done', 'purpose': d_sess.get('purpose'), 'needs_human': None}], ctx, fanout={'needs_human': None})
        print(f'{me}: recorded for {sid[:8]}: nothing waits for a human any more')
    elif a.cmd == 'reply-to-human':
        kit.record([{'event': 'message', 'purpose': d_sess.get('purpose'), 'needs_human': d_sess.get('needs_human'),
                     'message': a.text}], ctx, fanout={'message': a.text})
        print(f'{me}: recorded for {sid[:8]}: shown on its tab(s)')


if __name__ == '__main__':
    main()
