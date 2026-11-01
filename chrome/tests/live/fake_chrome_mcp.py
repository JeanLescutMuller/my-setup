#!/usr/bin/env python3
"""A fake "Claude in Chrome" MCP server (stdio, standard library only) for test_live.sh: same tool names and the
same result text as the real extension ("Created new tab. Tab ID: N", "Tab Context: - Available tabs: • tabId N:
"title" ("url")"), so the hooks can be tested in a real `claude -p` session without touching Chrome. Keeps its tabs
in memory. With $FAKE_COMMENTS set, a navigate also appends a comment "from the user" on that tab to that file (the
on-page note's comments.jsonl), to test delivery in the middle of a session."""
import json
import os
import sys
import time

d_tab, next_id = {}, [1000 + os.getpid() % 100000 * 10]  # like Chrome: tab ids unique across the test's sessions


def ctx(tab=None):
    l = [f'  • tabId {t}: "{u or "New tab"}" ("{u}")' for t, u in d_tab.items()]
    return ('\n\nTab Context:\n' + (f'- Executed on tabId: {tab}\n' if tab else '') + '- Available tabs:\n' + '\n'.join(l)) if l else ''


def call(name, a):
    if name == 'tabs_create_mcp':
        t = next_id[0]; next_id[0] += 1; d_tab[t] = ''
        return f'Created new tab. Tab ID: {t}' + ctx(t)
    if name == 'navigate':
        d_tab[int(a['tabId'])] = a['url']
        if os.environ.get('FAKE_COMMENTS'):
            with open(os.environ['FAKE_COMMENTS'], 'a') as f:
                f.write(json.dumps({'ts': int(time.time()), 'dt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                    'session_id': None, 'tab_id': int(a['tabId']), 'url': a['url'],
                                    'text': 'What is the title of this page? Answer me on the tab.'}) + '\n')
        return f'Navigated to {a["url"]}' + ctx(a['tabId'])
    if name == 'tabs_close_mcp':
        d_tab.pop(int(a['tabId']), None)
        return f'Closed tab {a["tabId"]}. {len(d_tab)} tab(s) remain.' + ctx()
    return ('Tabs:' + ctx()) if d_tab else 'This session has no tab group of its own.'


TOOLS = [{'name': 'tabs_create_mcp', 'description': 'Open a new tab in this session\'s group', 'inputSchema': {'type': 'object', 'properties': {}}},
         {'name': 'navigate', 'description': 'Go to a URL in a tab', 'inputSchema': {'type': 'object', 'properties': {'url': {'type': 'string'}, 'tabId': {'type': 'integer'}}, 'required': ['url', 'tabId']}},
         {'name': 'tabs_close_mcp', 'description': 'Close a tab', 'inputSchema': {'type': 'object', 'properties': {'tabId': {'type': 'integer'}}, 'required': ['tabId']}},
         {'name': 'tabs_context_mcp', 'description': 'List this session\'s tabs', 'inputSchema': {'type': 'object', 'properties': {}}}]
for line in sys.stdin:
    m = json.loads(line)
    if 'id' not in m:
        continue  # a notification
    meth, r = m.get('method'), None
    if meth == 'initialize':
        r = {'protocolVersion': m['params'].get('protocolVersion', '2025-06-18'), 'capabilities': {'tools': {}},
             'serverInfo': {'name': 'fakechrome', 'version': '0'}}
    elif meth == 'tools/list':
        r = {'tools': TOOLS}
    elif meth == 'tools/call':
        r = {'content': [{'type': 'text', 'text': call(m['params']['name'], m['params'].get('arguments') or {})}]}
    else:
        r = {}
    print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': r}), flush=True)
