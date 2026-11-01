#!/usr/bin/env python3
"""chrome-claim: a Claude session says why it uses Chrome, what the user must do, and asks what is already open.

  chrome-claim --purpose "read the Migros receipts" --needs-human "log in to migros.ch"   # before opening a tab
  chrome-claim --purpose "send Kat the photo" --visible-because "WhatsApp Web needs the logged-in profile"
  chrome-claim --needs-human "solve the captcha in tab 249416209"   # the user must act now (the purpose stays)
  chrome-claim done                                                 # the user's part is over (needs_human cleared)
  chrome-claim --message "done: the receipts are in Drive"          # answer the user's comment, shown on the tab
  chrome-claim open [--project P] [--json]   # what is open for my project (any session, any job): reuse it or close it
  chrome-claim window [--project P]          # Claude in Chrome's profile not connected: open its window, in the background

window: opens a window of the session's profile (else the project's: Claude - LinkedIn for job-applications, Claude -
Facebook for marketplace-seller, else Claude - general), only when that profile has no window, without taking focus;
its first tab names the project, and the kit extension makes it the project's agent window (sessions of the project
put their tabs there). The one sanctioned way to open a visible Chrome window from the shell (the hook refuses others).

A Claude in Chrome tab is always visible, so a claim needs --needs-human or --visible-because (the hook refuses a new
tab otherwise). The session is $CLAUDE_CODE_SESSION_ID (or --session); the job is $JR_JOB.
Reads and writes ~/opt/my-setup/state/chrome/ (chrome_kit: open.json, history/, sessions/).
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome_kit as kit  # noqa: E402

VISIBLE_HELP = ('A Claude in Chrome tab is always visible to the user, so also say either what they must do in it '
                '(--needs-human "<what>") or why a headless Chrome cannot do it (--visible-because "<why>", e.g. a '
                'logged-in profile such as WhatsApp or LinkedIn). If neither applies, use a headless Chrome from a script '
                '(skill chrome-headless) instead.')


def show(l_e: list[dict], sid: str | None):
    for e in sorted(l_e, key=lambda x: x.get('opened_ts') or 0):
        who = 'this session' if sid and e.get('session_id') == sid else (e.get('session_id') or '')[:8]
        print('\t'.join([str(e.get('tab_id')), time.strftime('%d %b %H:%M', time.localtime(e.get('opened_ts') or 0)), who,
                         e.get('job') or '', e.get('profile') or '', (e.get('url') or '')[:70], e.get('purpose') or '?',
                         f"YOUR TURN: {e['needs_human']}" if e.get('needs_human') else '']))


CHROME_BIN = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
EXT_ID = 'hfnfcdbehfbggjaccimmnolmhdkbfdie'   # "Agent tab notes": the "key" in extension/manifest.json


def frontmost() -> str:
    r = subprocess.run(['osascript', '-e', 'tell application "System Events" to get name of first process whose frontmost is true'],
                       capture_output=True, text=True)
    return r.stdout.strip() or f'? ({r.stderr.strip()[:60]})'


def window(project: str, sid: str | None, cwd: str, ctx: dict):
    """Open the profile's window in the background (see the module's doc); exits non-zero with the reason if refused."""
    d_sess = kit.session(sid)
    profile = d_sess.get('profile') or kit.profile_for(cwd)
    l_ok = next((l for n, l in kit.D_DEVICE.values() if n == profile), None)
    if l_ok and not any(x in cwd for x in l_ok):
        sys.exit(f'chrome-claim window: refused: "{profile}" is only for {" or ".join(l_ok)}')
    folder = kit.profile_folders().get(profile)
    if not folder or folder == 'Default':   # Default: the user's own profile, never
        sys.exit(f'chrome-claim window: no Chrome profile named "{profile}" in {kit.LOCAL_STATE}')
    if not any(p['kind'] == "user's Chrome" for p in kit.chrome_processes()):
        sys.exit("chrome-claim window: Chrome is not running: ask the user to start it (starting it from here would "
                 "also reopen the user's own profile)")
    l_win = kit.profile_windows(profile)
    if l_win:
        print(f'chrome-claim window: "{profile}" already has window(s) {l_win}: nothing opened. If Claude in Chrome is '
              'still not connected, ask the user to check the Claude extension in that window.')
        return
    url = f'chrome-extension://{EXT_ID}/window.html?' + urllib.parse.urlencode({'project': project, 'profile': profile})
    # The binary hands --profile-directory to the running Chrome (one more window); `open -g -a` would drop the
    # arguments of an app already running. Tests replace the command ($CHROME_WINDOW_CMD).
    cmd = [os.environ.get('CHROME_WINDOW_CMD') or CHROME_BIN, f'--profile-directory={folder}', url]
    if os.environ.get('CHROME_WINDOW_METHOD') == 'open-g':   # measured against the binary (2026-11-01)
        cmd = ['open', '-g', '-n', '-a', 'Google Chrome', '--args'] + cmd[1:]
    before = frontmost()
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
    l_win = None
    while time.monotonic() - t0 < 20 and not l_win:   # the kit extension of that profile reports its window
        l_win = kit.profile_windows(profile)
        time.sleep(0.5)
    kit.record([{'event': 'window', 'profile': profile, 'url': url, 'purpose': d_sess.get('purpose')}], ctx)
    stole = sorted(set(l_front) - {before})
    print(f'chrome-claim window: opened "{profile}" ({folder}) for project {project}: '
          + (f'window {l_win}' if l_win else 'no report from its "Agent tab notes" extension yet (not loaded in that profile?)')
          + f'. Frontmost app before: {before}; during 3 s: {", ".join(stole) if stole else "unchanged"}'
          + ('; focus given back to ' + before if given_back else '') + '.')


def main():
    ap = argparse.ArgumentParser(prog='chrome-claim', description=__doc__.split('\n')[0])
    ap.add_argument('cmd', nargs='?', choices=['done', 'open', 'window'],
                    help="done: the user's part is over; open: what is open for my project; window: open the profile's window")
    ap.add_argument('--purpose', help='why this session uses Chrome, in words the user understands')
    ap.add_argument('--needs-human', help='what the user must do in the tab (log in, solve a captcha, upload a file…)')
    ap.add_argument('--visible-because', help='why a headless Chrome cannot do it (a logged-in profile…)')
    ap.add_argument('--message', help="your answer to the user's comment on the tab: shown on the tab")
    ap.add_argument('--project', help="open, window: this project instead of the current folder's")
    ap.add_argument('--json', action='store_true', help='open: JSON')
    ap.add_argument('--session', help='session id, if not in $CLAUDE_CODE_SESSION_ID')
    a = ap.parse_args()
    sid = a.session or os.environ.get('CLAUDE_CODE_SESSION_ID')
    ctx = dict(session_id=sid, cwd=os.getcwd(), job=os.environ.get('JR_JOB'))

    if a.cmd == 'open':  # what this project has open now, by any session or job: reuse it, or close it before opening
        kit.correct(ctx)
        project = a.project or kit.project_of(os.getcwd())
        l_e = [e for e in kit.read_open().values() if e.get('project') == project]
        if a.json:
            print(json.dumps(l_e, indent=1, ensure_ascii=False))
        elif not l_e:
            print(f'chrome-claim: nothing open for project {project}')
        else:
            show(l_e, sid)
        return

    if a.cmd == 'window':
        window(a.project or kit.project_of(os.getcwd()), sid, os.getcwd(), ctx)
        return

    if not sid:
        sys.exit('chrome-claim: no session: run it from a Claude Code session ($CLAUDE_CODE_SESSION_ID), or pass --session')
    d_sess = kit.session(sid)
    if a.cmd == 'done':
        d_sess = kit.update_session(sid, needs_human=None)
        kit.record([{'event': 'done', 'purpose': d_sess.get('purpose'), 'needs_human': None}], ctx, fanout={'needs_human': None})
        print(f'chrome-claim: done: nothing waits for the user any more ({sid[:8]})')
        return
    if a.purpose or a.needs_human or a.visible_because:
        purpose = a.purpose or d_sess.get('purpose')
        if not purpose:
            sys.exit('chrome-claim: --purpose "<why this session uses Chrome>" is required first')
        need = a.needs_human if a.needs_human is not None else (None if a.purpose else d_sess.get('needs_human'))
        visible = a.visible_because or (None if a.purpose else d_sess.get('visible_because'))
        if a.purpose and not (need or visible):
            sys.exit('chrome-claim: refused: --purpose alone is not enough. ' + VISIBLE_HELP)
        kit.update_session(sid, purpose=purpose, needs_human=need, visible_because=visible)
        event = 'claim' if a.purpose else 'needs_human'
        kit.record([{'event': event, 'purpose': purpose, 'needs_human': need}], ctx,
                   fanout={'purpose': purpose, 'needs_human': need})
        print(f'chrome-claim: {event} recorded for {sid[:8]}: purpose={purpose!r}'
              + (f', YOUR TURN: {need}' if need else '') + (f', visible because: {visible}' if visible and not need else ''))
    if a.message:
        d_sess = kit.session(sid)
        kit.record([{'event': 'message', 'purpose': d_sess.get('purpose'), 'needs_human': d_sess.get('needs_human'),
                     'message': a.message}], ctx, fanout={'message': a.message})
        print(f'chrome-claim: message recorded for {sid[:8]}: shown on its tab(s)')
    if not (a.purpose or a.needs_human or a.visible_because or a.message):
        ap.print_help()


if __name__ == '__main__':
    main()
