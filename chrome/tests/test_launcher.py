#!/usr/bin/env python3
"""Test of launch_headless.py with a real headless Chrome (no window): run 1 opens, run 2 (keep) reuses the same
Chrome and tab, --close closes and checks, run 3 without keep leaves nothing. Writes only a temporary folder.
Run: python3 -I tests/test_launcher.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix='chrome-kit-launcher-'))
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
print(f'{n_fail} failed; folder: {tmp}')
sys.exit(bool(n_fail))
