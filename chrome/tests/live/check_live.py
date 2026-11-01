"""Checks of test_live.sh, on the kit's own files in its output folder. Run: python3 -I check_live.py <folder>"""
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
l_h = [json.loads(x) for f in sorted((out / 'state/history').glob('*.jsonl')) for x in f.read_text().splitlines()]
sid = {r: json.load(open(out / f'{r}.json'))['session_id'] for r in ('run1', 'run2', 'run3')}
ev = lambda r: [h['event'] for h in l_h if h['session_id'] == sid[r]]
l_in = [json.loads(x) for x in (out / 'hook-input.jsonl').read_text().splitlines()]
l_ok = [
    ('run1: refused, claimed, open, navigate, close', ev('run1')[:1] == ['claim'] and {'open', 'navigate', 'close'} <= set(ev('run1'))),
    ('run1: the claim was made by the hook\'s own session ($CLAUDE_CODE_SESSION_ID)', any(h['event'] == 'claim' and h['session_id'] == sid['run1'] for h in l_h)),
    ('hooks got tool_response as the MCP content list', any(isinstance(d.get('tool_response'), list) for d in l_in)),
    # the agent may say what the user must do up front (--needs-human) or after the Stop reminder: both are right
    ('run2: the tab left open says what the user must do, or was closed', 'close' in ev('run2') or any(
        e.get('session_id') == sid['run2'] and e.get('needs_human') for e in json.load(open(out / 'state/open.json')).values())),
    ('run3: the comment written mid-session got an answer on the tab', any(h['event'] == 'message' and h['session_id'] == sid['run3'] for h in l_h)),
    ('run4: the comment for the idle session got an answer', sum(h['event'] == 'message' and h['session_id'] == sid['run3'] for h in l_h) >= 2),
    ('no hook error', not (out / 'state/hook-errors.log').exists()),
]
for name, ok in l_ok:
    print(('PASS ' if ok else 'FAIL ') + name)
print(f"{sum(ok for _, ok in l_ok)} passed, {sum(not ok for _, ok in l_ok)} failed; cost ${sum(json.load(open(out / f'run{i}.json')).get('total_cost_usd', 0) for i in range(1, 5)):.3f}")
