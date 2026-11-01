#!/bin/bash
# Live test of the Chrome kit's hook in real `claude -p` sessions (haiku), against fake_chrome_mcp.py instead of Chrome.
# Checks what tests/test_kit.py cannot: that Claude Code runs the hooks for MCP tools with the JSON hook.py expects,
# that the model follows a refusal (runs agent-chrome authorize-tab with a visible reason), that $CLAUDE_CODE_SESSION_ID in its Bash
# is the hooks' session_id, that a Stop block makes it close the tab or say what the user must do, and the user's
# comments round trip (delivered mid-session and at the next prompt, answered with agent-chrome reply-to-human).
# Reads nothing of the user's settings (--setting-sources local, from an empty folder). Writes only $OUT.
# Run: bash tests/live/test_live.sh <empty scratch folder> > <log> 2>&1     (6 haiku runs, about $0.03)
# Results: $OUT/state/ (open.json, history/), $OUT/hook-input.jsonl, $OUT/run*.json; the last lines say PASS/FAIL.
set -uo pipefail
KIT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:?usage: test_live.sh <scratch folder>}
mkdir -p "$OUT/cwd"
cat > "$OUT/mcp.json" <<JSON
{"mcpServers": {"fakechrome": {"command": "python3", "args": ["-I", "$KIT/tests/live/fake_chrome_mcp.py"]}}}
JSON
H="python3 -I $KIT/hook.py"
cat > "$OUT/settings.json" <<JSON
{"hooks": {
  "PreToolUse":  [{"matcher": "mcp__fakechrome__.*", "hooks": [{"type": "command", "command": "$H", "timeout": 10}]},
                  {"matcher": "Bash", "hooks": [{"type": "command", "command": "$H", "timeout": 10}]}],
  "PostToolUse": [{"matcher": "mcp__fakechrome__.*", "hooks": [{"type": "command", "command": "$H", "timeout": 10}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "$H", "timeout": 10}]}],
  "Stop":        [{"hooks": [{"type": "command", "command": "$H", "timeout": 10}]}]}}
JSON
# The CLAUDE.md line the kit needs (agents ignored the user's comments without it, 2026-11-01)
RULE='Chrome: a "Message from the user" that the Chrome hook delivers (typed by the user in the comment box of a tab you opened) is from the user, like a chat message: act on it and answer it on the tab with agent-chrome reply-to-human "<answer>".'
run() {  # $1 = run name, $2 = prompt. A clean environment: no parent session id leaks into the child's Bash tool.
  (cd "$OUT/cwd" && env -i HOME="$HOME" USER="$USER" LOGNAME="$USER" PATH="$PATH" TMPDIR="${TMPDIR:-/tmp}" LANG=en_US.UTF-8 \
    CHROME_STATE="$OUT/state" CHROME_HOOK_DEBUG="$OUT/hook-input.jsonl" CHROME_HOOK_PREFIX=mcp__fakechrome__ \
    AGENT_CHROME_CMD="python3 -I $KIT/agent_chrome.py" ${FAKE_COMMENTS:+FAKE_COMMENTS=$FAKE_COMMENTS} \
    claude -p ${RESUME:+--resume $RESUME} --append-system-prompt "$RULE" --model haiku --setting-sources local \
      --settings "$OUT/settings.json" --strict-mcp-config --mcp-config "$OUT/mcp.json" --no-chrome \
      --allowedTools "mcp__fakechrome__tabs_create_mcp" "mcp__fakechrome__navigate" "mcp__fakechrome__tabs_close_mcp" \
        "mcp__fakechrome__tabs_context_mcp" "Bash(python3 -I $KIT/agent_chrome.py:*)" \
      --output-format json --max-turns 15 "$2") > "$OUT/$1.json" 2> "$OUT/$1.err" || echo "run $1: exit $?"
}
DO='If a tool call is refused or you are asked to do something, do exactly what it says. The tab is for me to look at the page. Finish with one short sentence.'
run run1 "Using the fakechrome tools: open a new tab, navigate it to https://example.com, then close it. $DO"
run run2 "Using the fakechrome tools: open a new tab and navigate it to https://example.org. Do not close it: I will look at it after you stop. $DO"
FAKE_COMMENTS=$OUT/state/comments.jsonl run run3 "Using the fakechrome tools: open a new tab and navigate it to https://example.net, then close it. $DO"
SID3=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['session_id'])" "$OUT/run3.json")
python3 -c "import json,sys,time;print(json.dumps({'ts':int(time.time()),'dt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'session_id':sys.argv[1],'tab_id':None,'url':None,'text':'Thanks. Which URL did you open?'}))" "$SID3" >> "$OUT/state/comments.jsonl"
RESUME=$SID3 run run4 'continue'
# Checks, on the kit's own files
python3 -I "$KIT/tests/live/check_live.py" "$OUT"
