#!/bin/bash
# tm - open the tmux session of a project folder: attach to it if it exists,
# create it (started in that folder) if not. Session name = folder name.
#
# Usage:
#   tm                  # the current folder
#   tm robotics-radar   # ~/dev/robotics-radar (a bare name is looked up in ~/dev)
#   tm ~/some/path      # any folder (an argument with a "/" or ".", or an existing folder)
#
# Inside tmux it switches the client to the session instead of nesting one.
# New panes and windows stay in the project folder: the session starts there,
# and files/tmux.conf opens splits and windows in the current pane's folder.
# Deployed by bootstrap.sh ("own binaries") to ~/opt/my-setup/bin/tm,
# linked from ~/.local/bin/tm.
set -euo pipefail

arg="${1:-.}"
if [[ "$arg" != */* && "$arg" != .* && ! -d "$arg" ]]; then
    arg="$HOME/dev/$arg"
fi
[ -d "$arg" ] || { echo "tm: no such folder: $arg" >&2; exit 1; }
dir="$(cd "$arg" && pwd)"

# tmux forbids "." and ":" in session names.
name="$(basename "$dir" | tr '.:' '__')"

if ! tmux has-session -t "=$name" 2>/dev/null; then
    tmux new-session -d -s "$name" -c "$dir"
fi

if [ -n "${TMUX:-}" ]; then
    exec tmux switch-client -t "=$name"
else
    exec tmux attach-session -t "=$name"
fi
