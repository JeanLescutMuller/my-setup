#!/usr/bin/env python3
"""Read-only report of what agents left open in Chrome on this Mac (skill chrome-leftovers): Chrome processes,
open windows and tabs with the agent that opened each tab, when each profile's windows were opened, the shell
commands that started Chrome, and the job logs' "chrome:" lines. Closes nothing.

Reads: `ps`, Chrome through AppleScript (window and tab ids = the ids Claude in Chrome uses), Chrome's
"Local State" and <profile>/Sessions/ file names, ~/.claude/projects/**/*.jsonl (Claude Code transcripts, the last
--hours), ~/opt/job-runner/logs/*/*/*.log. Writes nothing.
Run: python3 -I ~/.claude/skills/chrome-leftovers/scripts/leftovers.py [--hours 24]
"""
import argparse
import glob
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--hours', type=float, default=24, help='how far back to read transcripts and job logs')
args = ap.parse_args()
since = time.time() - args.hours * 3600
HOME = Path.home()
CHROME_DIR = HOME / 'Library/Application Support/Google/Chrome'
# Chrome's own Claude-in-Chrome profiles (CLAUDE.md "Chrome profiles"); other deviceIds show raw
D_DEVICE = {'331a94e7': 'Claude - general', '7ffa990a': 'Default (the user\'s own: off-limits to agents)', 'db5922d3': 'Claude - Facebook'}
RE_LAUNCH = re.compile(r'Google Chrome|--profile-directory')  # cheap pre-filter of transcript lines


def utc(ts):  # '2026-10-16 11:13Z' -> epoch
    return datetime.strptime(ts[:16], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc).timestamp()


def hm(ts):
    return datetime.fromtimestamp(ts).strftime('%a %d %H:%M')


def table(title, header, l_rows):
    print(f'\n## {title}\n')
    if not l_rows:
        print('(none)')
        return
    print('| ' + ' | '.join(header) + ' |\n|' + '---|' * len(header))
    for r in l_rows:
        print('| ' + ' | '.join(str(x).replace('|', '/') for x in r) + ' |')


# 1. Chrome main processes. More than one non-headless instance: AppleScript may talk to the wrong one (17 Oct 2026:
#    three leftover test Chromes made it see 0 windows).
l_proc = []
for line in subprocess.run(['ps', '-axo', 'pid=,etime=,command='], capture_output=True, text=True).stdout.splitlines():
    pid, etime, cmd = line.split(None, 2)
    if not re.search(r'MacOS/Google Chrome( |$)', cmd) or 'Helper' in cmd or '--type=' in cmd:  # main processes only
        continue
    m = re.search(r'--user-data-dir=(\S+)', cmd)
    kind = 'headless' if '--headless' in cmd else 'visible'
    l_proc.append((pid, etime, kind, m.group(1) if m else "the user's Chrome"))
table('Chrome processes', ['pid', 'running for', 'kind', 'data folder'], l_proc)
n_visible = sum(1 for r in l_proc if r[2] == 'visible')
if n_visible > 1:
    print(f'\n**Warning:** {n_visible} visible Chrome instances; the window list below may come from the wrong one. '
          'Quit the leftover ones (a temporary data folder, running for hours) first, then run again.')

# 2. Openers in Claude Code transcripts: tab ids seen in Claude-in-Chrome results, profiles selected, Chrome launches
d_tab, d_sess, l_launch, s_seen = {}, {}, [], set()
for f in glob.glob(str(HOME / '.claude/projects/**/*.jsonl'), recursive=True):
    if os.path.getmtime(f) < since:
        continue
    sid = Path(f).stem[:8]
    d_s = d_sess.setdefault(sid, {'file': f, 'last': os.path.getmtime(f), 'cwd': '', 'profile': '', 'said': ''})
    ts = ''
    for line in open(f, errors='ignore'):
        m = re.search(r'"timestamp":"([^"]{16})', line)
        ts = m.group(1).replace('T', ' ') + 'Z' if m else ts
        if not d_s['cwd'] and (m := re.search(r'"cwd":"([^"]+)"', line)):
            d_s['cwd'] = m.group(1).replace(str(HOME), '~')
        if '"type":"assistant"' in line and '"type":"text"' in line:
            try:  # the session's last words: a question means it may still wait for the user
                l_t = [c['text'] for c in json.loads(line)['message']['content'] if c.get('type') == 'text']
                d_s['said'] = (l_t[-1].strip().splitlines() or [''])[-1][-120:] if l_t else d_s['said']
            except (ValueError, KeyError, TypeError):
                pass
        if 'claude-in-chrome' in line or 'tabId' in line:
            if (m := re.search(r'"deviceId":"([0-9a-f]{8})', line)):
                d_s['profile'] = D_DEVICE.get(m.group(1), m.group(1))
            for tab in re.findall(r'tabId[^0-9]{0,8}(\d{6,})', line):
                d_tab.setdefault(int(tab), (ts, sid))
        if '"name":"Bash"' in line and RE_LAUNCH.search(line):
            for cmd in re.findall(r'"command":"((?:[^"\\]|\\.)*)"', line):
                # a visible launch only (a headless Chrome is the rule, not a leftover), within the period
                visible = re.search(r'open\s+-\w*a\s+\\?"?Google Chrome|--profile-directory', cmd) or \
                    ('MacOS/Google Chrome' in cmd and '--headless' not in cmd)
                if visible and ts and utc(ts) > since and (ts, sid, cmd[:140]) not in s_seen:
                    s_seen.add((ts, sid, cmd[:140]))
                    l_launch.append((ts, sid, d_s['cwd'], cmd[:140]))

# 3. Windows and tabs now, with who opened each tab
l_win = []
script = ('tell application "Google Chrome"\nset out to ""\nrepeat with w in windows\nrepeat with t in tabs of w\n'
          'set out to out & (id of w) & (character id 9) & (id of t) & (character id 9) & (URL of t) & (character id 9) & (title of t) & linefeed\n'
          'end repeat\nend repeat\nreturn out\nend tell')
if n_visible:
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=30)
    if r.returncode:  # 17 Oct 2026: one run saw no window at all (a tab changing mid-listing): say so, don't show "none"
        print(f'\n**AppleScript failed, the window list is incomplete: run again.** {r.stderr.strip()[:200]}')
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        wid, tid, url, title = (line.split('\t') + ['', '', '', ''])[:4]
        ts, sid = d_tab.get(int(tid), ('', '')) if tid.isdigit() else ('', '')
        d_s = d_sess.get(sid, {})
        who = f"{sid} ({d_s.get('cwd')}, {d_s.get('profile') or '?'})" if sid else 'no agent seen (the user, or a shell launch below)'
        l_win.append((wid, tid, url[:70], title[:40], who, ts))
table('Open windows and tabs (window id, tab id)', ['window', 'tab', 'URL', 'title', 'opened by', 'first seen'], l_win)

# 4. Sessions that own an open tab: still busy, or waiting for the user?
s_owner = {r[4].split()[0] for r in l_win if r[4][:1] != 'n'}
table('Sessions owning an open tab', ['session', 'cwd', 'last active', 'its last words (a "?" = may wait for the user)'],
      [(s, d_sess[s]['cwd'], hm(d_sess[s]['last']), d_sess[s]['said']) for s in sorted(s_owner)])

# 5. Each profile: when its current window session was opened (the Session_<time> file name, Chrome's time in us
#    since 1601), and when Chrome last wrote it (a recent write = the profile has windows open)
l_prof = []
try:
    d_info = json.load(open(CHROME_DIR / 'Local State'))['profile']['info_cache']
except (OSError, ValueError, KeyError):
    d_info = {}
for folder, d_p in d_info.items():
    l_f = sorted(glob.glob(str(CHROME_DIR / folder / 'Sessions/Session_*')), key=os.path.getmtime)
    if l_f and os.path.getmtime(l_f[-1]) > since:
        opened = int(Path(l_f[-1]).name.split('_')[1]) / 1e6 - 11644473600
        l_prof.append((d_p.get('name'), folder, hm(opened), hm(os.path.getmtime(l_f[-1]))))
table('Profiles with windows in the period', ['profile', 'folder', 'windows opened', 'last written'], l_prof)

# 6. Shell commands that started Chrome (a window no Claude-in-Chrome tool can see or close), and the jobs' own lines
table('Chrome started from the shell (Claude transcripts)', ['time (UTC)', 'session', 'cwd', 'command'], sorted(l_launch))
l_job = []
for f in glob.glob(str(HOME / 'opt/job-runner/logs/*/*/*.log')):
    if os.path.getmtime(f) > since:
        l_job += [(hm(os.path.getmtime(f)), f.split('/logs/')[1].split('/')[0], x.strip()[:120])
                  for x in open(f, errors='ignore') if x.startswith('chrome:')]
table('Scheduled jobs\' "chrome:" log lines', ['log written', 'job', 'line'], sorted(l_job))
