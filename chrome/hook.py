#!/usr/bin/env python3
"""The Chrome kit's Claude Code hook: every Claude in Chrome use is recorded, and the Chrome rules are enforced.

Installed by modules/claude_config.sh (PreToolUse on `mcp__claude-in-chrome__.*` and on `Bash`, PostToolUse on
`mcp__claude-in-chrome__.*`, UserPromptSubmit, Stop, SubagentStop); each runs this file with the hook's JSON on stdin.
Everything is kept per key (session_id, agent_id): the input's agent_id is there only inside a subagent (Claude Code
2.1.316, measured 2 Nov 2026); the session's subagents share its Claude in Chrome tab group, so the hook says whose
tab is whose.

| Event | Tool | Does |
|---|---|---|
| PreToolUse | select_browser, switch_browser | refuses Chrome's Default profile (the user's own), an unknown deviceId, a profile of another project |
| PreToolUse | tabs_create_mcp, navigate, browser_batch with a navigate, tabs_context_mcp createIfEmpty | refuses until the session ran `agent-chrome authorize-tab "<why>" --visibility … --visibility-reason …`; all of them when it authorized `invisible`; a second tabs_create_mcp ("reuse tab N") |
| PreToolUse | Bash | refuses a visible Chrome started from the shell (`open -a "Google Chrome"`, `--profile-directory`, the binary without --headless); in a subagent, adds `--agent-id <id>` after each `agent-chrome` and `--agent <id>` after each `pwl` the shell runs (updatedInput) |
| PreToolUse | any Claude in Chrome tool with a tabId | refuses a tab of another key of the session ("tab N belongs to subagent X"); the main agent may still close its subagents' tabs |
| PostToolUse | any Claude in Chrome tool | its "Available tabs" list corrects open.json: new tab → open, new URL → navigate, gone → close |
| UserPromptSubmit, PreToolUse, PostToolUse (Chrome) | - | the user's unread comments from the tab → Claude (additionalContext) |
| Stop, SubagentStop | - | unread comments → block, so Claude answers; else, once per stop: a tab of the key still open and nobody waits → "close it, or mark it as needing a human" (at Stop, the main agent also hears of its finished subagents' tabs) |
| every event above, Bash too | - | the key's notices (sessions/<key>.notices.jsonl, written by native_host.py: "your tab N expired") → Claude, once |

Reads: stdin, ~/opt/my-setup/state/chrome/ (chrome_kit). Writes: open.json, history/, sessions/<id>.json, hook-errors.log;
removes sessions/<id>.notices.jsonl once delivered.
Fails open: on its own error it logs to hook-errors.log and lets the call through (exit 0, no output).
Tests only: $CHROME_HOOK_PREFIX (a fake MCP server's tool prefix), $AGENT_CHROME_CMD, $CHROME_HOOK_DEBUG (keep stdin).
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome_kit as kit  # noqa: E402  (next to this file)

CHROME = os.environ.get('CHROME_HOOK_PREFIX', 'mcp__claude-in-chrome__')
CLAIM = os.environ.get('AGENT_CHROME_CMD', 'agent-chrome')
D_DEVICE = kit.D_DEVICE  # deviceId -> (profile name, projects allowed or None): chrome_kit
DEFAULT_PREFIX = '7ffa990a'  # Chrome's Default profile: the user's own, with their password vault. Never.
RE_TAB = re.compile(r'tabId (\d+): "(?:[^"\\]|\\.)*" \("((?:[^"\\]|\\.)*)"\)')  # • tabId 249416209: "title" ("url")
RE_HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)(\w+)\2")
SKIP = {'exec', 'nohup', 'command', 'env', 'then', 'do', 'else', 'time', '!', '{', 'caffeinate'}


def visible_launch(cmd: str) -> bool:
    """Would the shell run a visible Chrome? Only what it would run counts (1 Nov 2026: a heredoc writing HTML that
    mentions `open -a "Google Chrome"` was refused): heredoc bodies are dropped, a quoted string stays one word, and
    `open` / the Chrome binary count only as the command word (start, or after ; && || | ( or a newline)."""
    import shlex
    l_keep, end = [], None
    for line in cmd.replace('\\\n', ' ').split('\n'):  # (a `\` line continuation joins); drop heredoc bodies: from the line after `<<X` up to the line `X`
        if end is not None:
            if (line.lstrip('\t') if end[1] else line).strip() == end[0]:
                end = None
            continue
        l_keep.append(line)
        m = RE_HEREDOC.search(line)
        end = (m.group(3), bool(m.group(1))) if m else None
    try:
        lex = shlex.shlex(' ; '.join(l_keep), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        l_tok = list(lex)
    except ValueError:  # unbalanced quotes: not a command we can read; never block on a guess
        return False
    l_cmd, cur = [], []
    for t in l_tok + [';']:  # cut into simple commands at ; & | ( ) < > and their pairs
        if t and set(t) <= set('();<>|&'):
            l_cmd.append(cur)
            cur = []
        else:
            cur.append(t)
    for c in l_cmd:
        while c and (c[0] in SKIP or re.fullmatch(r'\w+=.*', c[0])):  # X=1 open …, exec …, then …
            c = c[1:]
        if not c:
            continue
        word, args = c[0], c[1:]
        if word == 'open' and any(re.fullmatch(r'-\w*[ab]\w*', a) for a in args) and any(
                'google chrome' in a.lower() or a == 'com.google.Chrome' for a in args):
            return True  # open -a "Google Chrome", open -na …, open -b com.google.Chrome
        if word == 'open' and any(a.rstrip('/').endswith('Google Chrome.app') for a in args):
            return True  # open "/Applications/Google Chrome.app"
        if word.endswith('Contents/MacOS/Google Chrome') and not any(a.startswith('--headless') for a in args):
            return True  # the binary itself, not headless (--profile-directory or not)
    return False
CLAIM_HELP = (f'  {CLAIM} authorize-tab "<why, in words the human understands>" --visibility invisible|unfocused|focused '
              '--visibility-reason "<why this level>" --mode single|subagents [--project P]\n'
              '  --mode: where the human answers you: single = in the terminal; subagents = in the tab\'s side panel '
              f'(you read it with {CLAIM} wait-for-human).\n'
              '  invisible: a headless Chrome from the launcher only (~/opt/my-setup/chrome/launch_headless.py); unfocused: '
              'Claude in Chrome tabs in the background; focused: also brought to the front once when you mark the tab '
              f'as needing a human ({CLAIM} mark-as-needing-human "<what>", after opening it). Skill chrome.')


def out(d: dict):
    print(json.dumps(d))
    sys.exit(0)


NOTICES = ['']  # this call's notices (take_notices): a refusal carries them too, or they would be lost


def deny(reason: str):
    reason = '\n'.join(x for x in [reason, NOTICES[0]] if x)
    out({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}})


def comments_text(l_c: list, aid: str) -> str:
    """The user's comments for this key, as text for Claude."""
    if not l_c:
        return ''
    l_txt = [f'- {c.get("dt", "")[11:16]} UTC, tab {c.get("tab_id")} ({(c.get("url") or "")[:60]}): "{c.get("text", "")}"' for c in l_c]
    # Worded as the user's own message: on 2026-11-01 haiku ignored "a hook note" as not part of the request
    return ("Message from the user, typed in the comment box on the Chrome tab " + ('you opened' if aid else 'this session opened')
            + " (the agents' on-page note; only the user can type there). Treat it like a chat message from them:\n"
            + '\n'.join(l_txt) + f'\nAnswer it on the tab with {CLAIM} reply-to-human "<your answer>"' + ('.' if aid else ', and here.'))


def take_notices(sid: str, aid: str = '') -> str:
    """What the kit must tell this key (a tab of its expired), once: the file is removed under its lock."""
    f = kit.SESSIONS / f'{kit.key_name(sid, aid)}.notices.jsonl'
    if not f.exists():
        return ''
    with kit.locked(f):
        try:
            l_n = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
            f.unlink()
        except (FileNotFoundError, ValueError):
            return ''
    return '\n'.join(f'Chrome kit: your tab {n.get("tab_id")} ({(n.get("url") or "")[:60]}) expired: the human didn\'t act in '
                     f'{kit.ttl_text(n.get("after_s"))} (NEEDS HUMAN: "{n.get("needs_human")}"); the kit closed it at '
                     f'{(n.get("dt") or "")[11:16]} UTC. Tell the user; open it again only if they ask.' for n in l_n)


def visibility(d_sess: dict) -> str | None:
    """The session's authorized visibility; a session authorized before 2 Nov 2026 (no field): unfocused."""
    return d_sess.get('visibility') or ('unfocused' if d_sess.get('purpose') else None)


def reason(d_sess: dict) -> str | None:
    return d_sess.get('visibility_reason') or d_sess.get('visible_because') or d_sess.get('needs_human')


# ---------------------------------------------------------------- a subagent's agent-chrome and pwl commands
# Each gets the subagent's id as an argument right after the program's name (`agent-chrome --agent-id <id> …`,
# `pwl --agent <id> …`): measured 2 Nov 2026, an environment variable (`export X=…; …` or `X=… cmd`) makes Claude Code
# ask for approval (a second operation), while an argument keeps the user's `Bash(agent-chrome:*)` rule matching.
# Only what the shell runs as a command is changed: a word in quotes, a heredoc body or a comment never is.
PROGS = {'agent-chrome': '--agent-id', 'chrome-claim': '--agent-id', 'pwl': '--agent'}
KEYWORDS = SKIP | {'if', 'while', 'until', 'elif', 'sudo', 'xargs'}
RE_ASSIGN = re.compile(r'[A-Za-z_]\w*=')


def shell_words(cmd: str) -> list:
    """The command's words: (end offset, unquoted text, at command position), outside quotes' insides, heredoc bodies
    and comments. Command position: the line's start, after ; & | ( { ` $( or a newline, after keywords and X=1."""
    i, n, l_w, cmd_pos, l_heredoc, redirect = 0, len(cmd), [], True, [], False
    while i < n:
        c = cmd[i]
        if c == '\n':
            i += 1
            for tag, strip in l_heredoc:  # skip each heredoc body, up to its tag line
                while i < n:
                    j = cmd.find('\n', i)
                    j = n if j < 0 else j
                    line, i = cmd[i:j], j + 1
                    if (line.lstrip('\t') if strip else line) == tag:
                        break
            l_heredoc, cmd_pos = [], True
            continue
        if c in ' \t':
            i += 1
            continue
        if c == '\\' and cmd[i + 1:i + 2] == '\n':
            i += 2
            continue
        if c == '#':
            j = cmd.find('\n', i)
            i = n if j < 0 else j
            continue
        if cmd.startswith('$(', i):
            i, cmd_pos = i + 2, True
            continue
        if c in ';&|({`':
            i, cmd_pos = i + 1, True
            continue
        if c in ')}':
            i += 1
            continue
        if c in '<>':
            m = re.match(r'<<(-?)\s*([\'"]?)(\w+)\2', cmd[i:])
            if m and not cmd.startswith('<<<', i):
                l_heredoc.append((m.group(3), bool(m.group(1))))
                i += m.end()
                continue
            while i < n and cmd[i] in '<>&':
                i += 1
            redirect = True   # the next word is a file
            continue
        buf = []
        while i < n and cmd[i] not in ' \t\n;&|()<>`':
            ch = cmd[i]
            if ch == '\\':
                buf.append(cmd[i + 1:i + 2])
                i += 2
            elif ch == "'":
                j = cmd.find("'", i + 1)
                j = n if j < 0 else j
                buf.append(cmd[i + 1:j])
                i = j + 1
            elif ch == '"':
                j = i + 1
                while j < n and cmd[j] != '"':
                    if cmd.startswith('$(', j):   # "…$(agent-chrome …)…": the substitution's words, at their offsets
                        k, depth = j + 2, 1
                        while k < n and depth:
                            depth += {'(': 1, ')': -1}.get(cmd[k], 0)
                            k += 1
                        l_w.extend((j + 2 + e, w, pos) for e, w, pos in shell_words(cmd[j + 2:k - 1]))
                        j = k
                        continue
                    j += 2 if cmd[j] == '\\' else 1
                buf.append(cmd[i + 1:j])
                i = j + 1
            elif cmd.startswith('$(', i):
                break
            else:
                buf.append(ch)
                i += 1
        word = ''.join(buf)
        if redirect:
            redirect = False
            continue
        l_w.append((min(i, n), word, cmd_pos))
        cmd_pos = cmd_pos and (word in KEYWORDS or bool(RE_ASSIGN.match(word)))
    return l_w


def with_agent(cmd: str, aid: str) -> str:
    """cmd with ` --agent-id <aid>` after each agent-chrome (` --agent <aid>` after pwl, and after `python… pwlayer.py`)
    the shell runs as a command; unchanged when there is none or it already has it."""
    l_w = shell_words(cmd)
    l_at = []
    for k, (end, word, pos) in enumerate(l_w):
        base = word.rsplit('/', 1)[-1]
        nxt = l_w[k + 1][1] if k + 1 < len(l_w) else ''
        if pos and base in PROGS:
            opt = PROGS[base]
        elif base == 'pwlayer.py' and k and l_w[k - 1][2] and l_w[k - 1][1].rsplit('/', 1)[-1].startswith('python'):
            opt = '--agent'
        else:
            continue
        if nxt != opt:
            l_at.append((end, f' {opt} {aid}'))
    for end, ins in sorted(l_at, reverse=True):
        cmd = cmd[:end] + ins + cmd[end:]
    return cmd


def tab_ids(x) -> set:
    """Every tabId in a tool's input (browser_batch: in its actions too)."""
    if isinstance(x, dict):
        return {int(v) for k, v in x.items() if k == 'tabId' and str(v).isdigit()} | {t for v in x.values() for t in tab_ids(v)}
    if isinstance(x, list):
        return {t for v in x for t in tab_ids(v)}
    return set()


def main():
    raw = sys.stdin.read()
    if os.environ.get('CHROME_HOOK_DEBUG'):
        with open(os.environ['CHROME_HOOK_DEBUG'], 'a') as f:
            f.write(raw.strip() + '\n')
    d_in = json.loads(raw)
    event, tool, sid = d_in.get('hook_event_name'), d_in.get('tool_name') or '', d_in.get('session_id')
    d_inp, cwd = d_in.get('tool_input') or {}, d_in.get('cwd') or ''
    try:   # the key: (session, agent); agent_id is in the input only inside a subagent
        aid = kit.agent_id(d_in.get('agent_id'))
    except ValueError:
        aid = ''

    if event == 'PreToolUse' and tool == 'Bash':  # first: every Bash call pays this, so nothing is read but one stat
        cmd = str(d_inp.get('command', ''))
        if visible_launch(cmd):
            deny('Refused by the Chrome hook: a Chrome window started from the shell appears in front of the user and no '
                 'agent tool can see or close it (CLAUDE.md "Chrome profiles"). Use a headless Chrome from a script '
                 '(skill chrome; ~/opt/my-setup/chrome/launch_headless.py), or, to show the human a page, Claude in '
                 'Chrome in the right profile; if that profile is not connected, open its window in the background with '
                 f'`{CLAIM} open-profile-window` (the one sanctioned way: no focus, only when the profile has no window).')
        d_out = {}
        if aid and ('chrome' in cmd or 'pwl' in cmd):
            new = with_agent(cmd, aid)
            if new != cmd:
                d_out['updatedInput'] = {**d_inp, 'command': new}
        if sid and (txt := take_notices(sid, aid)):
            d_out['additionalContext'] = txt
        if d_out:
            out({'hookSpecificOutput': {'hookEventName': event, **d_out}})
        return
    if not sid:
        return

    d_sess = kit.session(sid, aid)
    d_main = kit.session(sid) if aid else d_sess   # the browser: one per session, its subagents share it
    pending = kit.comments_pending(sid, aid)
    notices = NOTICES[0] = take_notices(sid, aid)
    if event == 'UserPromptSubmit' and not pending and not notices:  # the usual case: three stats, nothing else
        return
    d_open = kit.read_open()
    sess_tabs = {t: e for t, e in d_open.items() if e.get('session_id') == sid}
    mine = {t: e for t, e in sess_tabs.items() if kit.owner(e) == (sid, aid)}

    def ctx_of(a: str, d: dict) -> dict:
        return dict(session_id=sid, agent_id=a or None, cwd=cwd, job=os.environ.get('JR_JOB'), project=d.get('project'),
                    purpose=d.get('purpose'), visibility=visibility(d), visibility_reason=reason(d), mode=d.get('mode'),
                    needs_human=d.get('needs_human'))
    ctx = ctx_of(aid, d_sess)

    def say(l_ctx: list):  # these lines, the kit's notices and the user's unread comments, next to the tool result or the prompt
        txt = '\n'.join([x for x in [notices] + l_ctx if x] + ([comments_text(kit.take_comments(sid, aid, d_open), aid)] if pending else []))
        if txt.strip():
            out({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': txt}})

    if event == 'UserPromptSubmit':
        say([])
        return

    if event == 'PreToolUse' and tool.startswith(CHROME):
        name = tool[len(CHROME):]
        for t in sorted(tab_ids(d_inp)):   # a tab of another key of this session (its subagents share one tab group)
            e = sess_tabs.get(str(t))
            if not e or kit.owner(e) == (sid, aid):
                continue
            if not aid and name == 'tabs_close_mcp':
                continue   # the main agent may close its subagents' tabs (cleanup), nothing more
            deny(f'Refused by the Chrome hook: tab {t} belongs to {kit.who(e.get("agent_id") or "")} of this session '
                 f'(purpose: {e.get("purpose")!r}); you are {kit.who(aid)}. Drive only your own tab'
                 + (': ask that subagent (SendMessage) to act in it, or close it with tabs_close_mcp once it is done.'
                    if not aid else (f' (yours: {", ".join(mine)})' if mine else ': open one with tabs_create_mcp') + '.'))
        if name in ('select_browser', 'switch_browser'):
            dev = str(d_inp.get('deviceId') or '')
            if dev.startswith(DEFAULT_PREFIX):
                deny("Refused by the Chrome hook: Chrome's Default profile is the user's own (password vault): no agent ever "
                     'selects it. Pick an agent profile by deviceId (CLAUDE.md "Chrome profiles").')
            if name == 'select_browser' and dev not in D_DEVICE:
                deny(f'Refused by the Chrome hook: deviceId {dev[:8]}… is not one of the agent profiles in CLAUDE.md '
                     '"Chrome profiles". Ask the user; never pick another browser yourself.')
            fixed = d_main.get('device_id')
            if fixed and (name == 'switch_browser' or dev != fixed):  # one profile per session (user, 1 Nov 2026)
                have = D_DEVICE.get(fixed, (fixed[:8],))[0]
                want = D_DEVICE.get(dev, ('another profile',))[0] if name == 'select_browser' else 'another profile'
                deny(f'Refused by the Chrome hook: this session uses "{have}"; a session uses one Chrome profile for its '
                     'whole life (its subagents too), so it never reaches two accounts (LinkedIn and a general site) at '
                     f'once. Keep working in "{have}", or ask the user to start another Claude session for {want}.')
            l_ok = D_DEVICE[dev][1] if dev in D_DEVICE else None   # the authorized project, else the folder
            if l_ok and not (d_sess['project'] in kit.projects_of(l_ok) if d_sess.get('project') else any(x in cwd for x in l_ok)):
                deny(f'Refused by the Chrome hook: "{D_DEVICE[dev][0]}" is only for {" or ".join(sorted(kit.projects_of(l_ok)))} '
                     f'(CLAUDE.md "Chrome profiles"; this session: project {d_sess.get("project") or kit.project_of(cwd)}). '
                     'Use "Claude - general".')
            say([])
            return
        new_tab = name == 'tabs_create_mcp' or (name == 'tabs_context_mcp' and d_inp.get('createIfEmpty'))
        opens = new_tab or name == 'navigate' or (
            name == 'browser_batch' and any(x.get('name') == 'navigate' for x in d_inp.get('actions') or []))
        if opens and not d_sess.get('purpose') and os.environ.get('CHROME_PURPOSE'):  # a job without Bash: its environment says why
            vis = os.environ.get('CHROME_VISIBILITY') or 'unfocused'
            if vis not in kit.VISIBILITIES:
                deny(f'Chrome hook: CHROME_VISIBILITY={vis!r}: use one of {", ".join(kit.VISIBILITIES)}.')
            mode = os.environ.get('CHROME_MODE') or 'single'
            if mode not in kit.MODES:
                deny(f'Chrome hook: CHROME_MODE={mode!r}: use one of {", ".join(kit.MODES)}.')
            # CHROME_VISIBLE_BECAUSE: the old name of the reason, accepted until 2026-11-08 (job-applications)
            d_sess = kit.update_session(sid, aid, purpose=os.environ['CHROME_PURPOSE'], needs_human=None, visibility=vis, mode=mode,
                                        visibility_reason=os.environ.get('CHROME_VISIBILITY_REASON')
                                        or os.environ.get('CHROME_VISIBLE_BECAUSE'))
            ctx.update(purpose=d_sess['purpose'], visibility=vis, visibility_reason=d_sess['visibility_reason'], mode=mode)
            kit.record([{'event': 'claim'}], ctx)
        if opens and not d_sess.get('purpose'):
            deny(f'Chrome hook: before {"you open" if aid else "this session opens"} a page, say why and how visible, in one '
                 'Bash call' + (' (a subagent authorizes for itself)' if aid else '') + ':\n' + CLAIM_HELP + '\nThen retry.')
        if opens and visibility(d_sess) == 'invisible':
            deny(f'Chrome hook: this session authorized invisible: no Claude in Chrome tab. Use the launcher (a headless '
                 f'Chrome: ~/opt/my-setup/chrome/launch_headless.py, skill chrome), or authorize-tab again with '
                 f'--visibility unfocused: {CLAIM} authorize-tab "<why>" --visibility unfocused --visibility-reason "<why>" --mode single.')
        if new_tab and not reason(d_sess):
            deny('Chrome hook: this session\'s authorization has no visibility reason (a job: set CHROME_VISIBILITY_REASON). '
                 'Authorize again:\n' + CLAIM_HELP + '\nThen retry.')
        if name == 'tabs_create_mcp' and mine:
            l_t = [f'tab {t} ({(e.get("url") or "")[:60]})' for t, e in mine.items()]
            deny(f'Chrome hook: {"you" if aid else "this session"} already {"have" if aid else "has"} {", ".join(l_t)} open: '
                 f'one tab per {"subagent" if aid else "session"}. Reuse it (navigate with its tabId), or close it first with '
                 'tabs_close_mcp. If it no longer exists, call tabs_context_mcp once (that corrects the record) and retry. '
                 f'What your project has open: {CLAIM} status --mine.')
        say([])
        return

    if event == 'PostToolUse' and tool.startswith(CHROME):
        name = tool[len(CHROME):]
        if name in ('select_browser', 'switch_browser'):  # the first one fixes the session's profile
            dev = str(d_inp.get('deviceId') or '')
            if name == 'switch_browser':  # the user picked it in Chrome: its id is in the answer, if anywhere
                resp = json.dumps(d_in.get('tool_response'))
                dev = next((d for d in D_DEVICE if d in resp), '')
            if dev in D_DEVICE and not d_main.get('device_id'):
                kit.update_session(sid, device_id=dev, profile=D_DEVICE[dev][0])
            say([])
            return
        dev = d_main.get('device_id')
        profile = D_DEVICE.get(dev, (None,))[0]
        resp = d_in.get('tool_response')  # the MCP content list: [{"type": "text", "text": …}, …]
        text = '\n'.join(x.get('text', '') for x in resp if isinstance(x, dict)) if isinstance(resp, list) else \
            resp if isinstance(resp, str) else json.dumps(resp)
        if 'Available tabs:' not in text and name != 'tabs_close_mcp':
            say([])
            return
        # The caller's tab group, as Chrome sees it now. Closing the group's last tab: no list = none left. A new tab is
        # the caller's; a known one stays its owner's. Only the caller's own tabs (and a tab it just closed) can be
        # found closed here: a subagent may have its own group (live, 2 Nov 2026: a subagent's tabs_context_mcp
        # createIfEmpty made a new group that did not list the main agent's tab), so a tab missing from its list is not
        # a closed tab.
        d_now = {int(t): u for t, u in RE_TAB.findall(text.split('Available tabs:', 1)[-1])}
        d_ev, l_new = {}, []   # owner's agent id -> events
        for t, url in d_now.items():
            e = sess_tabs.get(str(t))
            if not e:
                l_new.append(t)
                d_ev.setdefault(aid, []).append({'event': 'open', 'profile': profile, 'device_id': dev, 'tab_id': t, 'url': url})
            elif url and url != e.get('url'):
                d_ev.setdefault(e.get('agent_id') or '', []).append(
                    {'event': 'navigate', 'profile': profile, 'device_id': dev, 'tab_id': t, 'url': url})
        s_closed = tab_ids(d_inp) if name == 'tabs_close_mcp' else set()
        for t, e in sess_tabs.items():  # a tab of this browser the group no longer has: closed, by an agent or the user
            if e.get('device_id') == dev and int(t) not in d_now and (t in mine or int(t) in s_closed):
                d_ev.setdefault(e.get('agent_id') or '', []).append(
                    {'event': 'close', 'profile': profile, 'device_id': dev, 'tab_id': int(t), 'url': e.get('url')})
        for a, l_ev in d_ev.items():
            kit.record(l_ev, ctx if a == aid else ctx_of(a, kit.session(sid, a)))
        if l_new:
            kit.correct(ctx)  # a new tab: also drop what a browser restart left in open.json
        say([(f'Chrome kit: tab {", ".join(map(str, l_new))} recorded for {"you" if aid else "this session"} (purpose: '
              f'{d_sess.get("purpose")!r}). Close it with tabs_close_mcp when done; if a human must act in it: {CLAIM} '
              'mark-as-needing-human "<what>".' + (f' The human answers in its side panel: {CLAIM} wait-for-human.'
                                                    if d_sess.get('mode') == 'subagents' else ''))
             if l_new else ''])
        return

    if event in ('Stop', 'SubagentStop'):
        txt = '\n'.join(x for x in [notices, comments_text(kit.take_comments(sid, aid, d_open), aid) if pending else ''] if x)
        if txt:
            out({'decision': 'block', 'reason': txt})
        left = dict(mine)
        if event == 'Stop':   # the main agent also cleans up after its finished subagents
            left.update({t: e for t, e in sess_tabs.items() if e.get('agent_id') and kit.session(sid, e['agent_id']).get('stopped')})
        left = {t: e for t, e in left.items() if not e.get('needs_human')}
        if left and not d_in.get('stop_hook_active'):
            l_t = [f'{t} ({(e.get("url") or "")[:60]}' + (f', {kit.who(e["agent_id"])}' if e.get('agent_id') else '') + ')'
                   for t, e in left.items()]
            out({'decision': 'block', 'reason':
                 f'Chrome kit: {"you" if aid else "this session"} still {"have" if aid else "has"} tab(s) {", ".join(l_t)} '
                 'open. Close them with tabs_close_mcp and check with tabs_context_mcp, or, if a human must act in one, '
                 f'run {CLAIM} mark-as-needing-human "<what>" and name the tab in your answer.'})
        if event == 'SubagentStop':
            kit.update_session(sid, aid, stopped=True)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # never break the user's tool call over a bug here: log it, let the call through
        kit.STATE.mkdir(parents=True, exist_ok=True)
        with open(kit.STATE / 'hook-errors.log', 'a') as f:
            f.write(f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {traceback.format_exc()}\n')
