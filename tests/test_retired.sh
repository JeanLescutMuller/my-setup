#!/bin/bash
# Sandbox test: bootstrap.sh removes what agent-tracker v1 retired (cc-map, cc-rc, the skill claude-sessions-overview)
# and no longer deploys it, nor the tmux plugins. Never the real HOME or tmux server.
# Usage: bash tests/test_retired.sh [<my-setup checkout>]   (default: this one)
set -uo pipefail
REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
S=$(mktemp -d)
export HOME=$S/home CLAUDE_CONFIG_DIR=$S/home/.claude TMUX_TMPDIR=$S/tmux
unset TMUX TMUX_PANE
case "$HOME" in /Users/jeanlescut|/Users/jeanlescut/) echo "refusing: real HOME"; exit 2 ;; esac
mkdir -p "$TMUX_TMPDIR"
pass=0 fail=0
check() { if [ "$2" = "$3" ]; then pass=$((pass+1)); echo "ok   $1"; else fail=$((fail+1)); echo "FAIL $1: want [$2] have [$3]"; fi; }
gone() { [ -e "$1" ] || [ -L "$1" ] && echo present || echo gone; }

# What an older deploy left: the two bins (copy, .bak, link) and the skill (read-only copy, two links).
OPT=$HOME/opt/my-setup
mkdir -p "$OPT/bin" "$HOME/.local/bin" "$OPT/skills/claude-sessions-overview" "$HOME/.claude/skills" "$HOME/.agents/skills"
for b in cc-map cc-rc; do echo old > "$OPT/bin/$b"; ln -s "$OPT/bin/$b" "$HOME/.local/bin/$b"; done
echo old > "$OPT/bin/cc-map.bak"
echo skill > "$OPT/skills/claude-sessions-overview/SKILL.md"; chmod -R a-w "$OPT/skills/claude-sessions-overview"
for h in "$HOME/.claude/skills" "$HOME/.agents/skills"; do ln -s "$OPT/skills/claude-sessions-overview" "$h/claude-sessions-overview"; done
# A cc-map of someone else's: kept.
mkdir -p "$S/other"; echo mine > "$S/other/cc-rc"

INSTALL=false bash "$REPO/bootstrap.sh" agent_links > "$S/check.log" 2>&1
check "check mode removes nothing" present "$(gone "$HOME/.local/bin/cc-map")"
INSTALL=true bash "$REPO/bootstrap.sh" agent_links > "$S/run.log" 2>&1
for p in "$HOME/.local/bin/cc-map" "$HOME/.local/bin/cc-rc" "$OPT/bin/cc-map" "$OPT/bin/cc-map.bak" "$OPT/bin/cc-rc" \
         "$HOME/.claude/skills/claude-sessions-overview" "$HOME/.agents/skills/claude-sessions-overview" "$OPT/skills/claude-sessions-overview"; do
    check "removed ${p#$HOME/}" gone "$(gone "$p")"
done
check "get_host_color still deployed" present "$(gone "$HOME/.local/bin/get_host_color")"
check "a deployed skill still linked" present "$(gone "$HOME/.claude/skills/machine-name")"
INSTALL=true bash "$REPO/bootstrap.sh" agent_links > "$S/run2.log" 2>&1
check "re-run: retired bins reported absent" 2 "$(sed 's/\x1b\[[0-9;]*m//g' "$S/run2.log" | grep -c 'retired, absent')"

# A link to someone else's file is not ours: kept.
ln -s "$S/other/cc-rc" "$HOME/.local/bin/cc-rc"
INSTALL=true bash "$REPO/bootstrap.sh" agent_links > "$S/run3.log" 2>&1
check "a cc-rc link that is not ours is kept" "$S/other/cc-rc" "$(readlink "$HOME/.local/bin/cc-rc")"

grep -q tmux_plugins "$REPO/bootstrap.sh"; check "no tmux_plugins module" 1 "$?"
grep -q -i 'resurrect\|continuum' "$REPO/files/tmux.conf"; check "tmux.conf loads no plugin" 1 "$?"
check "no plugins cloned" gone "$(gone "$OPT/tmux")"
echo "passed $pass, failed $fail (sandbox $S)"
[ "$fail" -eq 0 ]
