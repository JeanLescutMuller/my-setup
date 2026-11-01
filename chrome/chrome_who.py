#!/usr/bin/env python3
"""chrome-who: which agent opened which Chrome tab, when, for which project and why; and every Chrome running.

  chrome-who [--project P] [--json]              every agent tab open now (open.json, corrected first) + Chrome processes
  chrome-who --since 7d [--project P] [--json]   the history instead (units: m, h, d)

Reads ~/opt/my-setup/state/chrome/ (open.json, history/YYYY-MM.jsonl) and `ps`. Writes: only the corrections (close
lines for tabs a browser restart or a quit headless Chrome took away).
With more than one visible Chrome, macOS window scripts (AppleScript) may talk to the wrong one: it says BLIND.
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome_kit as kit  # noqa: E402


def hm(ts) -> str:
    return time.strftime('%d %b %H:%M', time.localtime(ts or 0))


def table(header: list, l_rows: list):
    l_rows = [[str(x if x is not None else '') for x in r] for r in l_rows]
    w = [max([len(h)] + [len(r[i]) for r in l_rows]) for i, h in enumerate(header)]
    for r in [header] + l_rows:
        print('  '.join(x.ljust(w[i]) for i, x in enumerate(r)).rstrip())


def main():
    ap = argparse.ArgumentParser(prog='chrome-who', description=__doc__.split('\n')[0])
    ap.add_argument('--since', help='history over this period: 30m, 12h, 7d')
    ap.add_argument('--project', help='only this project')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    if a.since:
        m = re.fullmatch(r'(\d+)([mhd])', a.since)
        if not m:
            sys.exit('chrome-who: --since takes 30m, 12h or 7d')
        since = time.time() - int(m.group(1)) * {'m': 60, 'h': 3600, 'd': 86400}[m.group(2)]
        l_r = []
        for f in sorted(kit.HISTORY.glob('*.jsonl')):
            if f.stem >= time.strftime('%Y-%m', time.gmtime(since)):
                for line in f.read_text().splitlines():
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r['ts'] >= since and (not a.project or r.get('project') == a.project):
                        l_r.append(r)
        if a.json:
            print(json.dumps(l_r, indent=1, ensure_ascii=False))
            return
        table(['when', 'event', 'session', 'project', 'job', 'tab', 'url', 'purpose', 'needs_human / message'],
              [[hm(r['ts']), r['event'], (r.get('session_id') or '')[:8], r.get('project'), r.get('job'), r.get('tab_id'),
                (r.get('url') or '')[:50], (r.get('purpose') or '')[:50], r.get('needs_human') or r.get('message') or '']
               for r in l_r])
        return

    kit.correct({'cwd': os.getcwd()})
    l_e = sorted([e for e in kit.read_open().values() if not a.project or e.get('project') == a.project],
                 key=lambda e: e.get('opened_ts') or 0)
    l_p = kit.chrome_processes()
    if a.json:
        print(json.dumps({'tabs': l_e, 'processes': l_p}, indent=1, ensure_ascii=False))
        return
    print(f'Agent tabs open now ({len(l_e)})')
    table(['opened', 'session', 'project', 'job', 'profile', 'tab', 'url', 'purpose', 'YOUR TURN', 'reach it'],
          [[hm(e.get('opened_ts')), (e.get('session_id') or '')[:8], e.get('project'), e.get('job'), e.get('profile'),
            str(e.get('tab_id'))[:12], (e.get('url') or '')[:50], (e.get('purpose') or '')[:50], e.get('needs_human') or '',
            e.get('reply_to') or ''] for e in l_e])
    s_kit = {(e.get('profile') or '')[9:] for e in l_e if (e.get('profile') or '').startswith('headless:')}
    print(f'\nChrome processes ({len(l_p)})')
    table(['pid', 'running since', 'kind', 'data folder', 'in the kit'],
          [[p['pid'], hm(p['start_ts']), p['kind'], p['data_dir'] or '', 'yes' if p['data_dir'] in s_kit else
            ('' if p['kind'] == "user's Chrome" else 'NO: not started by the launcher')] for p in l_p])
    n_vis = sum(p['kind'] != 'headless' for p in l_p)
    if n_vis > 1:
        print(f'\nBLIND: {n_vis} visible Chrome instances: macOS window scripts (AppleScript) may see the wrong one; '
              'never report a window "closed (checked)" from them until the extra ones are quit.')


if __name__ == '__main__':
    main()
