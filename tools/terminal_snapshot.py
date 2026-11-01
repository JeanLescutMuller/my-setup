#!/usr/bin/env python3
"""Save the terminal setup (iTerm2 windows/tabs + tmux sessions/panes + Claude sessions) as a restore script.

Reads:  tmux (list-sessions/windows/panes/clients), iTerm2 (AppleScript, read-only), ps,
        ~/.claude/sessions/<pid>.json (Claude Code's pid -> sessionId + cwd files).
Writes: ~/.local/state/terminal-snapshot/<dt>_restore.sh and latest_restore.sh (same content).

After a reboot, open iTerm2 and run:  bash ~/.local/state/terminal-snapshot/latest_restore.sh
It recreates every tmux session with the same windows, pane layout and folders, resumes the
same Claude session in each pane (`claude --resume <id>`), then reopens the iTerm2 windows
and tabs, each attached to its tmux session. Other programs are not rerun: the script
prints what each pane was running, so you can restart them by hand.
"""
import datetime, json, os, shlex, shutil, subprocess

TMUX = shutil.which('tmux') or 'tmux'
DIR_OUT = os.path.expanduser('~/.local/state/terminal-snapshot')
DIR_CLAUDE_SESSIONS = os.path.expanduser('~/.claude/sessions')
SHELLS = {'zsh', '-zsh', 'bash', '-bash', 'sh', 'login'}


def run(*l_cmd):
    return subprocess.run(l_cmd, capture_output=True, text=True).stdout.strip()


# --- process tree: pid -> children, pid -> full command line ---------------------------------
d_children, d_args, d_tty = {}, {}, {}
for line in run('ps', '-A', '-o', 'pid=,ppid=,tty=,args=').splitlines():
    pid, ppid, tty, args = (line.split(None, 3) + [''])[:4]
    d_children.setdefault(int(ppid), []).append(int(pid))
    d_args[int(pid)] = args
    d_tty.setdefault('/dev/' + tty, []).append(int(pid))


def descendants(pid):
    l_out, l_todo = [], list(d_children.get(pid, []))
    while l_todo:
        p = l_todo.pop(0)
        l_out.append(p)
        l_todo += d_children.get(p, [])
    return l_out


def claude_of(l_pids):
    """First pid that Claude Code registered in ~/.claude/sessions -> (sessionId, cwd), else None."""
    for p in l_pids:
        f = os.path.join(DIR_CLAUDE_SESSIONS, f'{p}.json')
        if os.path.exists(f):
            d = json.load(open(f))
            return d['sessionId'], d['cwd']
    return None


def resume_or_note(l_pids, cwd):
    """Shell command to rerun in a pane, plus a human note of what else was running there."""
    claude = claude_of(l_pids)
    if claude:
        sid, ccwd = claude
        return f'cd {shlex.quote(ccwd)} && claude --resume {sid}', ''
    l_other = [d_args[p] for p in l_pids if d_args.get(p, '').split(' ')[0].split('/')[-1] not in SHELLS
               and not d_args[p].startswith('/usr/bin/login')]
    return '', ' | '.join(l_other)


l_lines = ['#!/bin/bash', f'# Terminal snapshot taken {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}',
           f'TMUX_BIN={shlex.quote(TMUX)}', '', '# ---- 1. tmux sessions ----']
l_notes = []  # what to restart by hand, printed at the end of the restore

# --- tmux: sessions -> windows (name, size, layout) -> panes (cwd, what runs) ----------------
for session in run(TMUX, 'list-sessions', '-F', '#{session_name}').splitlines():
    q = shlex.quote(session)
    l_lines += [f'if ! "$TMUX_BIN" has-session -t {q} 2>/dev/null; then']
    l_windows = run(TMUX, 'list-windows', '-t', session, '-F',
                    '#{window_index}\t#{window_name}\t#{window_width}\t#{window_height}\t#{window_layout}').splitlines()
    for i_win, w in enumerate(l_windows):
        widx, wname, width, height, layout = w.split('\t')
        l_panes = [p.split('\t') for p in run(TMUX, 'list-panes', '-t', f'{session}:{widx}', '-F',
                                               '#{pane_index}\t#{pane_current_path}\t#{pane_pid}').splitlines()]
        target = f'{q}:{widx}'
        # first pane comes with the session/window, the others are splits; the saved layout string then
        # puts every pane back at its exact position and size
        cwd0 = shlex.quote(l_panes[0][1])
        if i_win == 0:
            l_lines.append(f'  "$TMUX_BIN" new-session -d -s {q} -n {shlex.quote(wname)} -x {width} -y {height} -c {cwd0}')
        else:
            l_lines.append(f'  "$TMUX_BIN" new-window -d -t {target} -n {shlex.quote(wname)} -c {cwd0}')
        for _, cwd, _ in l_panes[1:]:
            l_lines.append(f'  "$TMUX_BIN" split-window -d -t {target} -c {shlex.quote(cwd)}')
        l_lines.append(f'  "$TMUX_BIN" select-layout -t {target} {shlex.quote(layout)}')
        for pidx, cwd, ppid in l_panes:
            cmd, note = resume_or_note(descendants(int(ppid)), cwd)
            if cmd:
                l_lines.append(f'  "$TMUX_BIN" send-keys -t {target}.{pidx} {shlex.quote(cmd)} Enter')
            if note:
                l_notes.append(f'{session}:{widx}.{pidx} ({cwd}) was running: {note}')
    l_lines += ['else', f'  echo "tmux session {session} already exists, left as is"', 'fi']

# --- iTerm2: windows (position) -> tabs -> tty; a tty is either a tmux client or a plain shell -
d_client = dict(l.split('\t') for l in run(TMUX, 'list-clients', '-F', '#{client_tty}\t#{session_name}').splitlines() if l)
iterm = run('osascript', '-e', '''tell application "iTerm2"
set out to ""
repeat with w in windows
  set b to bounds of w
  set out to out & "WIN " & (item 1 of b) & "," & (item 2 of b) & "," & (item 3 of b) & "," & (item 4 of b) & linefeed
  repeat with t in tabs of w
    set out to out & "TAB " & (tty of (item 1 of sessions of t)) & linefeed
  end repeat
end repeat
return out
end tell''')


def applescript_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


l_osa = ['tell application "iTerm2"']
n_tab = 0
for line in iterm.splitlines():
    kind, value = line.split(' ', 1)
    if kind == 'WIN':
        l_osa += ['  set w to (create window with default profile)', f'  set bounds of w to {{{value}}}']
        n_tab = 0
        continue
    if value in d_client:  # this tab shows a tmux session
        cmd = f'"$TMUX_BIN" attach -t {shlex.quote(d_client[value])}'.replace('"$TMUX_BIN"', shlex.quote(TMUX))
    else:  # plain tab: resume its Claude session, if any
        cmd, note = resume_or_note(d_tty.get(value, []), '')
        if note:
            l_notes.append(f'iTerm2 tab {value} was running: {note}')
    if n_tab > 0:
        l_osa.append('  tell w to create tab with default profile')
    if cmd:
        l_osa.append(f'  tell current session of w to write text {applescript_str(cmd)}')
    n_tab += 1
l_osa.append('end tell')

l_lines += ['', '# ---- 2. iTerm2 windows and tabs ----', "osascript <<'APPLESCRIPT'", *l_osa, 'APPLESCRIPT', '',
            '# ---- 3. what to restart by hand ----']
l_lines += [f'echo {shlex.quote(n)}' for n in l_notes]

os.makedirs(DIR_OUT, exist_ok=True)
text = '\n'.join(l_lines) + '\n'
dt = datetime.datetime.now(datetime.timezone.utc).strftime('%Y_%m_%dT%H%M%SZ')
for name in (f'{dt}_restore.sh', 'latest_restore.sh'):
    with open(os.path.join(DIR_OUT, name), 'w') as f:
        f.write(text)
print(os.path.join(DIR_OUT, 'latest_restore.sh'))
