#!/usr/bin/env python3
"""Unit tests of the Chrome kit: feeds hook.py the JSON Claude Code sends (tool results copied from real Claude in
Chrome calls in a transcript of October 2026), runs chrome-claim and chrome-who, and checks decisions and the files.
Reads/writes only a temporary $CHROME_STATE; `ps` is faked ($CHROME_TEST_PS). Run: python3 -I tests/test_kit.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix='chrome-kit-test-'))
proj = tmp / 'proj-x'                       # a "repo": its folder name is the project
(proj / '.git').mkdir(parents=True)
(proj / 'sub').mkdir()
ps = tmp / 'ps.txt'                         # the user's Chrome, started an hour ago
ps.write_text('  501 01:00:00 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome\n')
ENV = {**os.environ, 'CHROME_STATE': str(tmp / 'state'), 'CLAUDE_CODE_SESSION_ID': 'sess-A', 'CHROME_TEST_PS': str(ps)}
ENV.pop('JR_JOB', None)
GEN, C = '331a94e7-f123-4e09-a755-cdc63980187f', 'mcp__claude-in-chrome__'
CWD = str(proj / 'sub')
n_fail = n_pass = 0


def hook(event, tool='', d_input=None, response=None, cwd=CWD, **kw):
    d = {'session_id': kw.pop('session_id', 'sess-A'), 'cwd': cwd, 'hook_event_name': event, 'tool_name': tool,
         'tool_input': d_input or {}, **({'tool_response': response} if response is not None else {}), **kw}
    r = subprocess.run([sys.executable, '-IB', str(KIT / 'hook.py')], input=json.dumps(d), capture_output=True, text=True, env=ENV)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def cli(name, *args):
    return subprocess.run([sys.executable, '-IB', str(KIT / name), *args], capture_output=True, text=True, env=ENV, cwd=CWD)


def check(name, ok):
    global n_fail, n_pass
    n_fail, n_pass = n_fail + (not ok), n_pass + bool(ok)
    print(('PASS ' if ok else 'FAIL ') + name)


def decision(d):
    return d.get('hookSpecificOutput', {}).get('permissionDecision') or d.get('decision')


def reason(d):
    return d.get('hookSpecificOutput', {}).get('permissionDecisionReason') or d.get('reason') or ''


def ctx(d):
    return d.get('hookSpecificOutput', {}).get('additionalContext', '')


def history():
    return [json.loads(x) for f in sorted((tmp / 'state/history').glob('*.jsonl')) for x in f.read_text().splitlines()]


def opened():
    p = tmp / 'state/open.json'
    return json.loads(p.read_text()) if p.exists() else {}


def tabs(*l):
    return [{'type': 'text', 'text': '\n\nTab Context:\n- Available tabs:\n' + ''.join(f'  • tabId {t}: "{ti}" ("{u}")\n' for t, ti, u in l)}]


T = 249416209
# Profiles
check('Default profile refused', decision(hook('PreToolUse', C + 'select_browser', {'deviceId': '7ffa990a-3bd4-46be-bf9e-871ec9870f9a'})) == 'deny')
check('unknown profile refused', decision(hook('PreToolUse', C + 'select_browser', {'deviceId': '12345678-0000'})) == 'deny')
check('Facebook profile refused outside marketplace-seller', decision(hook('PreToolUse', C + 'select_browser', {'deviceId': 'db5922d3-1713-4df0-a025-1ac608fac5f1'})) == 'deny')
check('Facebook profile allowed in marketplace-seller', decision(hook('PreToolUse', C + 'select_browser', {'deviceId': 'db5922d3-1713-4df0-a025-1ac608fac5f1'}, cwd='/Users/jeanlescut/dev/marketplace-seller')) is None)
check('general profile allowed', decision(hook('PreToolUse', C + 'select_browser', {'deviceId': GEN})) is None)
hook('PostToolUse', C + 'select_browser', {'deviceId': GEN}, [{'type': 'text', 'text': 'Selected browser "Browser 1".'}])
# A reason before anything opens; a visible reason before a new tab
d = hook('PreToolUse', C + 'tabs_create_mcp')
check('tabs_create refused before a claim, explaining both options', decision(d) == 'deny' and '--needs-human' in reason(d) and '--visible-because' in reason(d))
check('navigate refused before a claim too', decision(hook('PreToolUse', C + 'navigate', {'url': 'https://x.ch', 'tabId': 1})) == 'deny')
check('reading tools never refused', decision(hook('PreToolUse', C + 'tabs_context_mcp')) is None)
r = cli('chrome_claim.py', '--purpose', 'find Amazon RIVR engineers')
check('claim with --purpose alone refused, explaining both options', r.returncode != 0 and '--visible-because' in r.stderr and '--needs-human' in r.stderr)
check('claim with --visible-because accepted', cli('chrome_claim.py', '--purpose', 'find Amazon RIVR engineers', '--visible-because', 'LinkedIn needs the logged-in profile').returncode == 0)
check('tabs_create allowed after the claim', decision(hook('PreToolUse', C + 'tabs_create_mcp')) is None)
d = hook('PostToolUse', C + 'tabs_create_mcp', {}, [{'type': 'text', 'text': f'Created new tab. Tab ID: {T}'}] + tabs((T, 'New tab', '')))
e = opened().get(str(T), {})
check('open.json entry: fields in order', list(e) == ['ts', 'dt', 'opened_ts', 'opened_dt', 'event', 'session_id', 'project', 'job', 'machine', 'cwd', 'profile', 'device_id', 'tab_id', 'url', 'purpose', 'needs_human', 'message', 'reply_to'])
check('open.json entry: session UUID, project = git toplevel, profile, purpose, no job', e.get('session_id') == 'sess-A' and e.get('project') == 'proj-x'
      and e.get('profile') == 'Claude - general' and e.get('purpose') == 'find Amazon RIVR engineers' and e.get('job') is None and e.get('reply_to', '').endswith('asm resume sess-A'))
check('history line: fields in order, ts first', list(history()[-1]) == ['ts', 'dt', 'event', 'session_id', 'project', 'job', 'machine', 'cwd', 'profile', 'device_id', 'tab_id', 'url', 'purpose', 'needs_human', 'message', 'reply_to'])
check('Claude is told the tab was recorded', 'recorded' in ctx(d))
d = hook('PreToolUse', C + 'tabs_create_mcp')
check('second tab refused: reuse tab N', decision(d) == 'deny' and f'tab {T}' in reason(d))
hook('PostToolUse', C + 'navigate', {'url': 'https://www.linkedin.com/search/', 'tabId': T}, tabs((T, 'Search | LinkedIn', 'https://www.linkedin.com/search/')))
check('navigate: entry and history updated', opened()[str(T)]['url'] == 'https://www.linkedin.com/search/' and history()[-1]['event'] == 'navigate')
r = cli('chrome_claim.py', 'open', '--json')
check('chrome-claim open: the project\'s open tab', r.returncode == 0 and [x['tab_id'] for x in json.loads(r.stdout)] == [T])
check('chrome-claim open --project other: nothing', 'nothing open' in cli('chrome_claim.py', 'open', '--project', 'other').stdout)
# End of turn
check('Stop blocked once while a tab is open and nobody waits', hook('Stop', stop_hook_active=False).get('decision') == 'block')
check('Stop not blocked twice in a row', hook('Stop', stop_hook_active=True) == {})
cli('chrome_claim.py', '--needs-human', 'log in to LinkedIn')
check('--needs-human: on the tab entry (what the bar shows), purpose kept', opened()[str(T)]['needs_human'] == 'log in to LinkedIn' and opened()[str(T)]['purpose'] == 'find Amazon RIVR engineers')
check('Stop allowed while the user must act', hook('Stop', stop_hook_active=False) == {})
hook('PostToolUse', C + 'computer', {'action': 'screenshot', 'tabId': T}, tabs((T, 'Feed', 'https://www.linkedin.com/feed/')))
check('later events keep needs_human', opened()[str(T)]['needs_human'] == 'log in to LinkedIn')


# The user's comments from the tab: delivered once, to the right session only
def comment(text, sid=None, tab=T):
    with open(tmp / 'state/comments.jsonl', 'a') as f:
        f.write(json.dumps({'ts': int(time.time()), 'dt': '2026-11-01T12:00:00Z', 'session_id': sid, 'tab_id': tab,
                            'url': 'https://www.linkedin.com/feed/', 'text': text}) + '\n')


comment('please also check Remco')
comment('not for you', sid='sess-B')
d = hook('PostToolUse', C + 'computer', {'action': 'screenshot', 'tabId': T}, tabs((T, 'Feed', 'https://www.linkedin.com/feed/')))
check('comment on the tab delivered at the next Chrome call, not the other session\'s', 'please also check Remco' in ctx(d) and 'not for you' not in ctx(d))
check('not delivered twice', 'Remco' not in ctx(hook('PreToolUse', C + 'computer', {'action': 'screenshot', 'tabId': T})))
check('UserPromptSubmit with nothing waiting: no output', hook('UserPromptSubmit', prompt='go on') == {})
comment('and Federico', sid='sess-A', tab=None)
check('comment naming the session delivered at the next prompt', 'and Federico' in ctx(hook('UserPromptSubmit', prompt='go on')))
comment('stop, wait for me')
d = hook('Stop', stop_hook_active=True)
check('comment arriving during the turn: Stop blocked with it', d.get('decision') == 'block' and 'stop, wait for me' in d.get('reason', ''))
cli('chrome_claim.py', '--message', 'OK, I will check Remco and Federico')
check('--message: on the tab entry, and a message line in the history', opened()[str(T)]['message'] == 'OK, I will check Remco and Federico' and history()[-1]['event'] == 'message')
hook('PostToolUse', C + 'computer', {'action': 'screenshot', 'tabId': T}, tabs((T, 'Feed', 'https://www.linkedin.com/x')))
check('the message stays on the tab after later events', opened()[str(T)]['message'] == 'OK, I will check Remco and Federico')
cli('chrome_claim.py', 'done')
check('done: needs_human cleared on the tab', opened()[str(T)]['needs_human'] is None)
# Close, and corrections
hook('PostToolUse', C + 'tabs_close_mcp', {'tabId': T}, [{'type': 'text', 'text': f'Closed tab {T}. 0 tab(s) remain.'}])
check('close: entry removed, close line in the history', str(T) not in opened() and history()[-1]['event'] == 'close')
check('Stop allowed once tabs are closed', hook('Stop', stop_hook_active=False) == {})
cli('chrome_claim.py', '--session', 'sess-old', '--purpose', 'old', '--needs-human', 'x')
subprocess.run([sys.executable, '-IB', '-c', f'import sys; sys.path.insert(0, {str(KIT)!r}); import chrome_kit as k; '
                'k.record([{"event": "open", "ts": 1000, "tab_id": 7, "device_id": "' + GEN + '", "url": "https://old"}], {"session_id": "sess-old", "cwd": "/tmp"}); '
                'k.record([{"event": "open", "tab_id": "ABC", "profile": "headless:/nowhere", "url": "https://h"}], {"session_id": "sess-old", "cwd": "/tmp"})'], env=ENV)
r = cli('chrome_who.py')
check('chrome-who: drops a tab older than the browser\'s start and a headless tab whose Chrome is gone', r.returncode == 0 and '7' not in opened() and 'ABC' not in opened()
      and sum(h['event'] == 'close' and h['tab_id'] in (7, 'ABC') for h in history()) == 2)
check('chrome-who lists processes', "user's Chrome" in r.stdout)
ps.write_text(ps.read_text() + '  777 00:10 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/x\n')
check('chrome-who says BLIND with two visible Chromes', 'BLIND' in cli('chrome_who.py').stdout)
check('chrome-who --since 1d: the history', 'navigate' in cli('chrome_who.py', '--since', '1d').stdout)
# A job without Bash says why in its environment; a new tab still needs a visible reason
ENV['CHROME_PURPOSE'] = 'auto-job-apply: apply to 3 jobs'
d = hook('PreToolUse', C + 'tabs_create_mcp', session_id='sess-J')
check('$CHROME_PURPOSE alone: claim recorded, new tab refused (no visible reason)', decision(d) == 'deny' and 'visible' in reason(d) and history()[-1]['purpose'] == 'auto-job-apply: apply to 3 jobs')
ENV['CHROME_VISIBLE_BECAUSE'] = 'the job applies through the logged-in LinkedIn profile'
check('$CHROME_PURPOSE + $CHROME_VISIBLE_BECAUSE: allowed', decision(hook('PreToolUse', C + 'tabs_create_mcp', session_id='sess-K')) is None)
# Shell launches of a visible Chrome
for cmd, want in [('open -na "Google Chrome" --args --profile-directory="Profile 3"', 'deny'),
                  ('open -a Google\\ Chrome https://x.ch', 'deny'), ('open -b com.google.Chrome', 'deny'),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --user-data-dir=/tmp/p about:blank', 'deny'),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --user-data-dir=/tmp/p', None),
                  ('pgrep -f "MacOS/Google Chrome"', None), ('grep -rn "Google Chrome" ~/dev', None),
                  ('.venv/bin/python -m common.chrome open', None)]:
    check(f'Bash {want or "allow"}: {cmd[:60]}', decision(hook('PreToolUse', 'Bash', {'command': cmd})) == want)
check('hook never failed (no hook-errors.log)', not (tmp / 'state/hook-errors.log').exists())
print(f'{n_pass} passed, {n_fail} failed; state: {tmp / "state"}')
sys.exit(bool(n_fail))
