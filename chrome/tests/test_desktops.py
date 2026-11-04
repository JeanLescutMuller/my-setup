#!/usr/bin/env python3
"""Tests of the desktop layer (desktops.py) and `agent-chrome show`: the pure choices with made-up windows, a read-only
look at this Mac's desktops (macOS only), and show's refusals (no window is ever opened: every case stops before).
Reads/writes only a temporary $CHROME_STATE and a fake Chrome "Local State". Run: /usr/bin/python3 -I tests/test_desktops.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix='chrome-desktops-test-'))
local_state = tmp / 'Local State'
local_state.write_text(json.dumps({'profile': {'info_cache': {
    'Default': {'name': 'Jean (jean.lescut@gmail.com)'}, 'Profile 1': {'name': 'Claude - general'},
    'Profile 2': {'name': 'Claude - LinkedIn'}}}}))
ENV = {**os.environ, 'CHROME_STATE': str(tmp / 'state'), 'CHROME_LOCAL_STATE': str(local_state)}
os.environ.update(ENV)   # before the import: chrome_kit reads them once
sys.path.insert(0, str(KIT))
import desktops as dk  # noqa: E402

n_fail = n_pass = 0


def check(name, ok, detail=''):
    global n_fail, n_pass
    n_fail, n_pass = n_fail + (not ok), n_pass + bool(ok)
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  -- {detail}'))


def show(*args, cwd=str(KIT)):
    return subprocess.run([sys.executable, '-IB', str(KIT / 'agent_chrome.py'), 'show', *args],
                          capture_output=True, text=True, env=ENV, cwd=cwd)


# ---- pure choices
check('profile from an accessibility title',
      dk.profile_of_title('Meta Deep-Dive - Google Chrome – Claude - general') == 'Claude - general')
check('no profile in a plain title', dk.profile_of_title('Keep or close') is None)
l_cg = [{'id': 1, 'rect': (0, 0, 800, 600)}, {'id': 2, 'rect': (10, 10, 800, 600)}, {'id': 3, 'rect': (20, 20, 800, 600)}]
d_prof = {1: 'Jean (jean.lescut@gmail.com)', 2: 'Claude - general', 3: 'Claude - general'}
d_sp = {1: [100], 2: [200], 3: [100]}
check('reuse: the profile\'s window on this desktop', (dk.pick(l_cg, d_prof, 'Claude - general', 100, d_sp) or {}).get('id') == 3)
check('never another profile\'s window', dk.pick(l_cg, d_prof, 'Claude - LinkedIn', 100, d_sp) is None)
check('no window of the profile on this desktop', dk.pick(l_cg, {2: 'Claude - general'}, 'Claude - general', 100, d_sp) is None)
check('AppleScript id by rect', dk.as_id_of((10, 10, 800, 600), [{'as_id': 7, 'rect': (10, 10, 800, 600)}]) == 7)
check('new window by rect, old ones excluded', (dk.cg_of((0, 0, 800, 600), l_cg + [{'id': 9, 'rect': (0, 0, 800, 600)}], {1}) or {}).get('id') == 9)

# ---- this Mac, read-only
lay = dk.layout()
check('desktops read', bool(lay) and sum(v['shown'] for v in lay.values()) >= 1, lay)
sp, rect, _ = dk.session_desktop()
check('this session\'s desktop found (or no iTerm2 window: on the phone)', sp is None or sp in lay, (sp, list(lay)))

# ---- show's refusals: nothing opens
page = tmp / 'p.html'
page.write_text('<title>t</title>')
r = show(str(tmp / 'missing.html'))
check('missing file: exit 2', r.returncode == 2 and 'no such file' in r.stdout, r.stdout + r.stderr)
r = show(str(page), '--profile', 'Jean (jean.lescut@gmail.com)')
check("the user's own profile: refused", r.returncode == 2 and 'refused' in r.stdout, r.stdout + r.stderr)
r = show(str(page), '--profile', 'Claude - LinkedIn')
check('a profile reserved for another project: refused', r.returncode == 2 and 'only for job-applications' in r.stdout, r.stdout + r.stderr)

print(f'{n_pass} passed, {n_fail} failed')
sys.exit(bool(n_fail))
