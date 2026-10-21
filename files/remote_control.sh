#!/bin/bash
# Run by com.jeanlescut.my-setup.remote-control (macOS LaunchAgent / Linux systemd --user service, modules/remote_control.sh):
# keeps `claude remote-control` running in ~/dev (or ~/opt where there is no ~/dev: the VM), so a session can be started
# from the phone (Claude app or claude.ai/code) at any time.
# Writes ~/opt/my-setup/logs/remote-control.log: one line per start and exit, plus stderr.
# Its screen (redrawn about once a second) goes to /dev/null: in the log it would add ~30 MB a day.
set -uo pipefail

# launchd's PATH is /usr/bin:/bin:/usr/sbin:/sbin; the sessions need claude, brew's tools and ~/.local/bin.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOG="$HOME/opt/my-setup/logs/remote-control.log"
mkdir -p "${LOG%/*}"
# Keep the log small: a login that keeps failing restarts this once a minute.
[ "$(wc -l < "$LOG" 2>/dev/null || echo 0)" -gt 2000 ] && tail -n 1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
log() { printf '%s\t%s\t%s\n' "$(date +%s)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >> "$LOG"; }

cd "$HOME/dev" 2>/dev/null || cd "$HOME/opt" || { log "no ~/dev nor ~/opt"; exit 1; }
log "start $(claude --version 2>/dev/null | head -1)"

# On launchctl bootout, pass the TERM on so claude closes its sessions cleanly.
trap 'kill -TERM "$child" 2>/dev/null' TERM INT
# Claude in Chrome is off by default for spawned sessions, whatever the /chrome setting says: turn it on.
# On the VM too: its sessions reach the Mac's Chrome profiles through bridge.claudeusercontent.com (same account).
claude remote-control --permission-mode auto --chrome >/dev/null 2>>"$LOG" &
child=$!
rc=0
while kill -0 "$child" 2>/dev/null; do wait "$child"; rc=$?; done
log "exit $rc"
exit "$rc"
