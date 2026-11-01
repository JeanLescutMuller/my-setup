#!/usr/bin/env python3
"""Unit tests of the Chrome kit: feeds hook.py the JSON Claude Code sends (tool results copied from real Claude in
Chrome calls in a transcript of October 2026), runs agent-chrome (and its old names), and checks decisions and the files.
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
# One profile per session: the first selection fixes it
d = hook('PreToolUse', C + 'select_browser', {'deviceId': 'f16617c3-d0dc-425b-a7a4-d925eec10bf5'}, cwd='/Users/jeanlescut/dev/job-applications')
check('one profile per session: a 2nd profile refused, naming both', decision(d) == 'deny' and 'Claude - general' in reason(d) and 'Claude - LinkedIn' in reason(d))
check('one profile per session: switch_browser refused once a profile is fixed', decision(hook('PreToolUse', C + 'switch_browser')) == 'deny')
check('one profile per session: the same profile again allowed', decision(hook('PreToolUse', C + 'select_browser', {'deviceId': GEN})) is None)
hook('PostToolUse', C + 'switch_browser', {}, [{'type': 'text', 'text': 'Connected to ' + 'f16617c3-d0dc-425b-a7a4-d925eec10bf5'}], session_id='sess-S')
d = hook('PreToolUse', C + 'select_browser', {'deviceId': GEN}, session_id='sess-S')
check('switch_browser fixes the profile when its answer names it', decision(d) == 'deny' and 'Claude - LinkedIn' in reason(d))
# A reason before anything opens; a visible reason before a new tab
d = hook('PreToolUse', C + 'tabs_create_mcp')
check('tabs_create refused before a claim, explaining both options', decision(d) == 'deny' and '--needs-human' in reason(d) and '--visible-because' in reason(d))
check('navigate refused before a claim too', decision(hook('PreToolUse', C + 'navigate', {'url': 'https://x.ch', 'tabId': 1})) == 'deny')
check('reading tools never refused', decision(hook('PreToolUse', C + 'tabs_context_mcp')) is None)
r = cli('agent_chrome.py', 'authorize-tab', 'find Amazon RIVR engineers')
check('authorize-tab without --needs-human or --visible-because refused, naming both', r.returncode != 0 and '--visible-because' in r.stderr and '--needs-human' in r.stderr)
r = cli('chrome_claim.py', '--purpose', 'find Amazon RIVR engineers')
check('old chrome-claim --purpose alone: still refused, explaining both options', r.returncode != 0 and '--visible-because' in r.stderr and '--needs-human' in r.stderr)
check('authorize-tab --visible-because accepted', cli('agent_chrome.py', 'authorize-tab', 'find Amazon RIVR engineers', '--visible-because', 'LinkedIn needs the logged-in profile').returncode == 0)
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
r = cli('agent_chrome.py', 'status', '--mine', '--json')
check('status --mine: the project\'s open tab', r.returncode == 0 and [x['tab_id'] for x in json.loads(r.stdout)['tabs']] == [T])
r = cli('agent_chrome.py', 'status', '--mine')
check('status --mine: "this session", no process list', 'this session' in r.stdout and 'Chrome processes' not in r.stdout)
check('status --project other: nothing', 'nothing open' in cli('agent_chrome.py', 'status', '--project', 'other').stdout)
r = cli('chrome_claim.py', 'open')
check('old chrome-claim open: works, with the one-line notice', r.returncode == 0 and 'this session' in r.stdout
      and r.stderr.strip() == 'chrome-claim: renamed: agent-chrome status (the old name stops working on 2026-11-08)')
# End of turn
check('Stop blocked once while a tab is open and nobody waits', hook('Stop', stop_hook_active=False).get('decision') == 'block')
check('Stop not blocked twice in a row', hook('Stop', stop_hook_active=True) == {})
cli('agent_chrome.py', 'mark-as-needing-human', 'log in to LinkedIn')
check('mark-as-needing-human: on the tab entry (what the bar shows), purpose kept', opened()[str(T)]['needs_human'] == 'log in to LinkedIn' and opened()[str(T)]['purpose'] == 'find Amazon RIVR engineers')
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
cli('agent_chrome.py', 'reply-to-human', 'OK, I will check Remco and Federico')
check('reply-to-human: on the tab entry, and a message line in the history', opened()[str(T)]['message'] == 'OK, I will check Remco and Federico' and history()[-1]['event'] == 'message')
hook('PostToolUse', C + 'computer', {'action': 'screenshot', 'tabId': T}, tabs((T, 'Feed', 'https://www.linkedin.com/x')))
check('the message stays on the tab after later events', opened()[str(T)]['message'] == 'OK, I will check Remco and Federico')
cli('agent_chrome.py', 'mark-as-human-done')
check('mark-as-human-done: needs_human cleared on the tab', opened()[str(T)]['needs_human'] is None)
# Close, and corrections
hook('PostToolUse', C + 'tabs_close_mcp', {'tabId': T}, [{'type': 'text', 'text': f'Closed tab {T}. 0 tab(s) remain.'}])
check('close: entry removed, close line in the history', str(T) not in opened() and history()[-1]['event'] == 'close')
check('Stop allowed once tabs are closed', hook('Stop', stop_hook_active=False) == {})
r = cli('chrome_claim.py', '--session', 'sess-old', '--purpose', 'old', '--needs-human', 'x')
check('old chrome-claim --purpose --needs-human: works, notice names authorize-tab', r.returncode == 0 and 'renamed: agent-chrome authorize-tab' in r.stderr)
subprocess.run([sys.executable, '-IB', '-c', f'import sys; sys.path.insert(0, {str(KIT)!r}); import chrome_kit as k; '
                'k.record([{"event": "open", "ts": 1000, "tab_id": 7, "device_id": "' + GEN + '", "url": "https://old"}], {"session_id": "sess-old", "cwd": "/tmp"}); '
                'k.record([{"event": "open", "tab_id": "ABC", "profile": "headless:/nowhere", "url": "https://h"}], {"session_id": "sess-old", "cwd": "/tmp"})'], env=ENV)
r = cli('agent_chrome.py', 'status')
check('status: drops a tab older than the browser\'s start and a headless tab whose Chrome is gone', r.returncode == 0 and '7' not in opened() and 'ABC' not in opened()
      and sum(h['event'] == 'close' and h['tab_id'] in (7, 'ABC') for h in history()) == 2)
check('status lists processes', "user's Chrome" in r.stdout)
ps.write_text(ps.read_text() + '  777 00:10 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/x\n')
check('status says BLIND with two visible Chromes', 'BLIND' in cli('agent_chrome.py', 'status').stdout)
check('status: a visible Chrome nobody recorded is "NO: not started by the launcher"', 'NO: not started' in cli('agent_chrome.py', 'status').stdout)
r = cli('chrome_who.py')
check('old chrome-who: works, with the one-line notice', r.returncode == 0 and 'BLIND' in r.stdout and 'renamed: agent-chrome status' in r.stderr)
subprocess.run([sys.executable, '-IB', '-c', f'import sys; sys.path.insert(0, {str(KIT)!r}); import chrome_kit as k; '
                'k.record([{"event": "open", "tab_id": "chrome:/tmp/x", "profile": "visible:/tmp/x", "url": "about:blank"}], {"session_id": "sess-pw", "cwd": "/tmp"})'], env=ENV)
r = cli('agent_chrome.py', 'status')
check('status: the password layer\'s visible:<dir> Chrome counts as in the kit', 'NO: not started' not in r.stdout and 'chrome:/tmp/x' in opened())
check('status --since 1d: the history', 'navigate' in cli('agent_chrome.py', 'status', '--since', '1d').stdout)
r = cli('agent_chrome.py', '--help')
check('agent-chrome --help names the 6 subcommands', all(x in r.stdout for x in ['authorize-tab', 'mark-as-needing-human',
      'mark-as-human-done', 'reply-to-human', 'status', 'open-profile-window']))
# A job without Bash says why in its environment; a new tab still needs a visible reason
ENV['CHROME_PURPOSE'] = 'auto-job-apply: apply to 3 jobs'
d = hook('PreToolUse', C + 'tabs_create_mcp', session_id='sess-J')
check('$CHROME_PURPOSE alone: claim recorded, new tab refused (no visible reason)', decision(d) == 'deny' and 'visible' in reason(d) and history()[-1]['purpose'] == 'auto-job-apply: apply to 3 jobs')
ENV['CHROME_VISIBLE_BECAUSE'] = 'the job applies through the logged-in LinkedIn profile'
check('$CHROME_PURPOSE + $CHROME_VISIBLE_BECAUSE: allowed', decision(hook('PreToolUse', C + 'tabs_create_mcp', session_id='sess-K')) is None)
# Shell launches of a visible Chrome
for cmd, want in [('open -na "Google Chrome" --args --profile-directory="Profile 3"', 'deny'),
                  ('open -a "Google Chrome"', 'deny'), ('cd x && open -na "Google Chrome" --args --new-window', 'deny'),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --profile-directory="Profile 3"', 'deny'),
                  ('X=1 open -a "Google Chrome" https://x.ch', 'deny'), ('ls\nopen -a "Google Chrome"', 'deny'),
                  ('open "/Applications/Google Chrome.app"', 'deny'),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\\n  --headless --user-data-dir=/tmp/p', None),
                  ("cat > /tmp/p.html <<'EOF'\n<p>run: open -a \"Google Chrome\" page.html</p>\nEOF\nls /tmp", None),
                  ("python3 - <<'PY'\nimport os; os.system('open -a \"Google Chrome\"')\nPY", None),
                  ('echo "then open -a Google Chrome yourself"', None), ('git commit -m "no more open -a Google Chrome"', None),
                  ('open -a Google\\ Chrome https://x.ch', 'deny'), ('open -b com.google.Chrome', 'deny'),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --user-data-dir=/tmp/p about:blank', 'deny'),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --user-data-dir=/tmp/p', None),
                  ('pgrep -f "MacOS/Google Chrome"', None), ('grep -rn "Google Chrome" ~/dev', None),
                  ('.venv/bin/python -m common.chrome open', None), ('chrome-claim window', None), ('agent-chrome open-profile-window', None),
                  ('chrome-claim window --project job-applications', None),
                  ('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --profile-directory="Profile 3"', 'deny')]:
    check(f'Bash {want or "allow"}: {cmd[:60]}', decision(hook('PreToolUse', 'Bash', {'command': cmd})) == want)
d = hook('PreToolUse', 'Bash', {'command': 'open -a "Google Chrome"'})
check('the shell-launch refusal points to agent-chrome open-profile-window and skill chrome', 'agent-chrome open-profile-window' in reason(d) and 'skill chrome;' in reason(d))

# agent-chrome open-profile-window: Claude in Chrome's profile not connected -> its window, in the background
(tmp / 'Local State').write_text(json.dumps({'profile': {'info_cache': {'Default': {'name': 'me@x.ch'}, 'Profile 3': {'name': 'Claude - general'},
                                                                        'Profile 6': {'name': 'Claude - LinkedIn'}}}}))
fake = tmp / 'fake_chrome.sh'      # the "Chrome binary": logs its arguments, then the extension reports the new window
fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CHROME_STATE/fake-args"\nmkdir -p "$CHROME_STATE/windows"\n'
                'printf \'{"pid": %s, "profile": "Claude - general", "windows": [77]}\' "$KEEP_PID" > "$CHROME_STATE/windows/Claude - general.json"\n')
fake.chmod(0o755)
keep = subprocess.Popen(['sleep', '60'])   # a live "native host" pid
ENV.update(CHROME_LOCAL_STATE=str(tmp / 'Local State'), CHROME_WINDOW_CMD=str(fake), KEEP_PID=str(keep.pid), CLAUDE_CODE_SESSION_ID='sess-W')
r = cli('agent_chrome.py', 'open-profile-window')
args = (tmp / 'state/fake-args').read_text().split('\n') if (tmp / 'state/fake-args').exists() else []
check('window: opens "Claude - general" (Profile 3) with the project\'s marker tab, waits for its window report',
      r.returncode == 0 and '--profile-directory=Profile 3' in args and any('window.html?project=proj-x' in a for a in args)
      and 'window [77]' in r.stdout and 'Frontmost app before' in r.stdout, )
check('window: recorded in the history', history()[-1]['event'] == 'window' and history()[-1]['profile'] == 'Claude - general')
(tmp / 'state/fake-args').unlink()
r = cli('agent_chrome.py', 'open-profile-window')
check('window: the profile already has a window -> nothing opened', r.returncode == 0 and 'already has' in r.stdout
      and not (tmp / 'state/fake-args').exists())
keep.kill()
ENV['CLAUDE_CODE_SESSION_ID'] = 'sess-L'
(tmp / 'state/sessions/sess-L.json').write_text(json.dumps({'profile': 'Claude - LinkedIn'}))
r = cli('agent_chrome.py', 'open-profile-window')
check('window: the session\'s LinkedIn profile from another project -> refused', r.returncode != 0 and 'only for' in r.stderr)
ENV['CLAUDE_CODE_SESSION_ID'] = 'sess-W'
ps_saved = ps.read_text()
ps.write_text('')
r = cli('agent_chrome.py', 'open-profile-window')
check('window: Chrome not running -> refused (never starts it: it would reopen the user\'s own profile)', r.returncode != 0 and 'not running' in r.stderr)
ps.write_text(ps_saved)
check('hook never failed (no hook-errors.log)', not (tmp / 'state/hook-errors.log').exists())
print(f'{n_pass} passed, {n_fail} failed; state: {tmp / "state"}')
sys.exit(bool(n_fail))
