#!/usr/bin/env python3
"""chrome-claim: a Claude session says why it uses Chrome, what the user must do, and asks what is already open.

  chrome-claim --purpose "read the Migros receipts" --needs-human "log in to migros.ch"   # before opening a tab
  chrome-claim --purpose "send Kat the photo" --visible-because "WhatsApp Web needs the logged-in profile"
  chrome-claim --needs-human "solve the captcha in tab 249416209"   # the user must act now (the purpose stays)
  chrome-claim done                                                 # the user's part is over (needs_human cleared)
  chrome-claim --message "done: the receipts are in Drive"          # answer the user's comment, shown on the tab
  chrome-claim open [--project P] [--json]   # what is open for my project (any session, any job): reuse it or close it

A Claude in Chrome tab is always visible, so a claim needs --needs-human or --visible-because (the hook refuses a new
tab otherwise). The session is $CLAUDE_CODE_SESSION_ID (or --session); the job is $JR_JOB.
Reads and writes ~/opt/my-setup/state/chrome/ (chrome_kit: open.json, history/, sessions/).
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import argparse
import json
import os
import sys
import time
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


def main():
    ap = argparse.ArgumentParser(prog='chrome-claim', description=__doc__.split('\n')[0])
    ap.add_argument('cmd', nargs='?', choices=['done', 'open'], help='done: the user\'s part is over; open: what is open for my project')
    ap.add_argument('--purpose', help='why this session uses Chrome, in words the user understands')
    ap.add_argument('--needs-human', help='what the user must do in the tab (log in, solve a captcha, upload a file…)')
    ap.add_argument('--visible-because', help='why a headless Chrome cannot do it (a logged-in profile…)')
    ap.add_argument('--message', help="your answer to the user's comment on the tab: shown on the tab")
    ap.add_argument('--project', help='open: this project instead of the current folder\'s')
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
