#!/usr/bin/env python3
"""Test of launch_headless.py with a real headless Chrome (no window): run 1 opens, run 2 (keep) reuses the same
Chrome and tab, --close closes and checks, run 3 without keep leaves nothing. Writes only a temporary folder.
Run: python3 -I tests/test_launcher.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix='chrome-kit-launcher-')).resolve()  # /private/var…: what Chrome's command line shows
prof = tmp / 'prof'
ENV = {**os.environ, 'CHROME_STATE': str(tmp / 'state'), 'JR_JOB': 'test.job'}
ENV.pop('CLAUDE_CODE_SESSION_ID', None)
n_fail = 0


def run(*args):
    r = subprocess.run([sys.executable, '-IB', str(KIT / 'launch_headless.py'), '--data-dir', str(prof), *args],
                       capture_output=True, text=True, env=ENV, timeout=90)
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {'err': r.stderr[-300:]}


def check(name, ok):
    global n_fail
    n_fail += not ok
    print(('PASS ' if ok else 'FAIL ') + name)


def alive():
    return subprocess.run(['pgrep', '-f', f'user-data-dir={prof}'], capture_output=True, text=True).stdout.split()


def open_json():
    p = tmp / 'state/open.json'
    return json.loads(p.read_text()) if p.exists() else {}


h1 = run('--purpose', 'test run 1', '--url', 'https://example.com', '--keep')
check('run 1 starts a Chrome and opens a tab', h1.get('reused') is False and h1.get('target_id') in open_json())
e = open_json().get(h1.get('target_id'), {})
check('its entry: headless profile, job, no device', e.get('profile') == f'headless:{prof.resolve()}' and e.get('job') == 'test.job' and e.get('device_id') is None)
h2 = run('--purpose', 'test run 2', '--url', 'https://example.com', '--keep')
check('run 2 reuses the same Chrome and the same tab', h2.get('reused') is True and h2.get('target_id') == h1.get('target_id'))
r = run('--close')
check('--close: closed, no process left, entry gone', r.get('pids_left') == [] and not alive() and not open_json())
h3 = run('--purpose', 'test run 3', '--url', 'https://example.com')
check('run 3 without keep: nothing left', h3.get('reused') is False and not alive() and not open_json())

# Extra flags reach Chrome
h4 = run('--purpose', 'flags', '--keep', '--flag=--disk-cache-size=1')
cmdline = subprocess.run(['ps', '-axww', '-o', 'command='], capture_output=True, text=True).stdout
check('flags=(…) reach the Chrome command line', any(f'user-data-dir={prof}' in x and '--disk-cache-size=1' in x for x in cmdline.splitlines()))
run('--close')

# A killed caller (SIGKILL, as job-runner's timeout) never leaves Chrome running: the watcher quits it and records it
caller = subprocess.Popen([sys.executable, '-IB', str(KIT / 'launch_headless.py'), '--data-dir', str(prof), '--purpose',
                           'killed caller', '--hold', '120'], stdout=subprocess.PIPE, text=True, env=ENV)
h5 = json.loads(caller.stdout.readline())
check('caller running: its Chrome and tab are up', bool(alive()) and h5['target_id'] in open_json())
caller.kill()
caller.wait()
for _ in range(40):
    if not alive() and h5['target_id'] not in open_json():
        break
    time.sleep(0.5)
hist = [json.loads(x) for f in (tmp / 'state/history').glob('*.jsonl') for x in f.read_text().splitlines()]
check('SIGKILL on the caller: Chrome quit within 20 s, tab recorded closed', not alive() and h5['target_id'] not in open_json()
      and any(h['event'] == 'close' and h['tab_id'] == h5['target_id'] for h in hist))

# A data folder a visible Chrome already uses is refused (faked ps: no window opened)
busy_dir = tmp / 'busy'
(tmp / 'ps.txt').write_text(f'  999 00:05 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir={busy_dir}\n')
r = subprocess.run([sys.executable, '-IB', str(KIT / 'launch_headless.py'), '--data-dir', str(busy_dir), '--purpose', 'busy'],
                   capture_output=True, text=True, env={**ENV, 'CHROME_TEST_PS': str(tmp / 'ps.txt')}, timeout=60)
check('busy data folder (a visible Chrome on it) refused, clearly', r.returncode != 0 and 'already used by a visible Chrome (pid 999)' in r.stderr
      and not subprocess.run(['pgrep', '-f', f'user-data-dir={busy_dir}'], capture_output=True, text=True).stdout)
print(f'{n_fail} failed; folder: {tmp}')
sys.exit(bool(n_fail))
