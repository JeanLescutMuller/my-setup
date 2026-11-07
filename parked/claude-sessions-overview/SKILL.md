---
name: claude-sessions-overview
description: Show every tmux session on this Mac and the Claude sessions running in each, with agent-notify's color icon, then turn on Remote Control (/rc) in the ones the user picks, so they show up in the Claude app. Use when the user types /claude-sessions-overview, asks to see, list or map their Claude or tmux sessions, or asks to turn on Remote Control (/rc) in a running session, especially from the phone.
---

# Claude sessions overview

1. Run `cc-map` (`~/.local/bin/cc-map`, from `~/dev/my-setup/files/cc_map.py`) and reply with its output exactly as printed, as Markdown, **never inside a code block**. After it, one line: `📱 = Remote Control on`.
2. Run `cc-rc --candidates`: up to 4 session names with Remote Control off, most recent first. If there are any, ask with AskUserQuestion, `multiSelect: true`: "Turn on Remote Control for which session?", one option per name (description: its tmux session from the map); with only one name, add a second option `None`. The buttons are only a shortcut: the user may as well answer in words, or type another name under "Other".
3. For each session picked, run `cc-rc "<name>"` and reply with the line it prints (✅ or ❌ and why).

When the user names a session directly ("turn on rc in X"), skip to step 3. `cc-rc` also takes a session UUID (or its first 8 characters) or a tmux pane (`%20`).

Never type into a tmux pane yourself (`tmux send-keys`): `cc-rc` (`~/dev/my-setup/files/cc_rc.py`) types `/rc` only when the session is idle, its prompt box is empty and Remote Control is off; if it refuses, report why and do not work around it.

If `cc-map` or `cc-rc` is not found, say so in one line: they are installed by `INSTALL=true bash ~/dev/my-setup/bootstrap.sh`.

What the icons mean, if asked: 🔵 working · 🟡 waiting for the user · 🟢 done, not seen yet · ⚪ done, seen · 🟣 on hold · ⚫ no icon in agent-notify (acknowledged, or not tracked).
