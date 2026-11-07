#!/bin/bash
# Sandbox test of my-setup's statusLine chain (modules/claude_config.sh). Never the real HOME or tmux server.
# Usage: bash tests/test_claude_config.sh [<my-setup checkout>]   (default: this one)
set -uo pipefail
REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
S=$(mktemp -d)
export HOME=$S/home CLAUDE_CONFIG_DIR=$S/home/.claude AGENT_TRACKER_HOME=$S/home/opt/agent-tracker TMUX_TMPDIR=$S/tmux
unset TMUX TMUX_PANE
mkdir -p "$HOME/.claude" "$TMUX_TMPDIR"
case "$HOME" in /Users/jeanlescut|/Users/jeanlescut/) echo "refusing: real HOME"; exit 2 ;; esac
pass=0 fail=0
check() { if [ "$2" = "$3" ]; then pass=$((pass+1)); echo "ok   $1"; else fail=$((fail+1)); echo "FAIL $1: want [$2] have [$3]"; fi; }
sl() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["statusLine"][sys.argv[2]])' "$HOME/.claude/settings.json" "$1"; }
run() { INSTALL="${1:-true}" bash "$REPO/bootstrap.sh" claude_config > "$S/run.log" 2>&1; }

printf '%s\n' '{"hooks":{"SessionStart":[{"matcher":"","hooks":[{"type":"command","command":"other"}]}]},"env":{"X":"1"}}' > "$HOME/.claude/settings.json"
run
check "no agent-tracker: display alone" 'bash $HOME/.claude/statusline-command.sh' "$(sl command)"
check "refreshInterval 10" 10 "$(sl refreshInterval)"
check "other keys kept (hooks)" other "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hooks"]["SessionStart"][0]["hooks"][0]["command"])' "$HOME/.claude/settings.json")"
check "other keys kept (env)" 1 "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["env"]["X"])' "$HOME/.claude/settings.json")"

mkdir -p "$HOME/.local/bin"; printf '#!/bin/bash\ncat\n' > "$HOME/.local/bin/agent-tracker"; chmod +x "$HOME/.local/bin/agent-tracker"
run false
check "check mode reports the change, writes nothing" 'bash $HOME/.claude/statusline-command.sh' "$(sl command)"
check "check mode says skip" 1 "$(grep -c 'statusLine (want' "$S/run.log")"
run
check "agent-tracker installed: the chain" 'agent-tracker tick | bash $HOME/.claude/statusline-command.sh' "$(sl command)"
check "refreshInterval still 10" 10 "$(sl refreshInterval)"
run
check "re-run: ok, unchanged" 1 "$(sed 's/\x1b\[[0-9;]*m//g' "$S/run.log" | grep -c '\[ok\] statusLine$')"
check "re-run: same command" 'agent-tracker tick | bash $HOME/.claude/statusline-command.sh' "$(sl command)"

# the chain itself runs: a fake display echoes what it got
printf '#!/bin/bash\ncat\n' > "$HOME/.claude/statusline-command.sh"
cmd="$(sl command)"
check "chain passes stdin through" '{"a":1}' "$(printf '{"a":1}' | PATH="$HOME/.local/bin:$PATH" bash -c "$cmd")"

rm "$HOME/.local/bin/agent-tracker"
run
check "agent-tracker removed: back to the display alone" 'bash $HOME/.claude/statusline-command.sh' "$(sl command)"
check "no write to the real tmux server or HOME: sandbox only" "$S/home" "$HOME"
echo "passed $pass, failed $fail (sandbox $S)"
[ "$fail" -eq 0 ]
