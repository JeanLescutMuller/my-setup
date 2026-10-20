#!/bin/bash
# Ensures specific top-level ~/.claude/settings.json keys match
# files/claude_settings.json, merged in via python3 (already a required
# dependency of agent-session-manager's own install.sh) without touching
# any other key in the file.
#
# Deliberately does NOT manage "hooks" (agent-session-manager's own job -
# its install.sh registers those) or "enabledPlugins"/"extraKnownMarketplaces"
# (notify's own job - its install.sh registers those). Each tool that owns
# a piece of this file manages it itself - this module only owns the keys
# nothing else does.
step "claude config"

SETTINGS="$HOME/.claude/settings.json"
DESIRED="$SCRIPT_DIR/files/claude_settings.json"

_check_or_set_json() {
    local key="$1"
    local have want

    have=$(KEY="$key" SETTINGS="$SETTINGS" python3 -c '
import json, os
key = os.environ["KEY"]
try:
    with open(os.environ["SETTINGS"]) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}
print(json.dumps(data.get(key), sort_keys=True))
')
    want=$(KEY="$key" DESIRED="$DESIRED" python3 -c '
import json, os
key = os.environ["KEY"]
with open(os.environ["DESIRED"]) as f:
    data = json.load(f)
print(json.dumps(data[key], sort_keys=True))
')

    if [ "$have" = "$want" ]; then
        ok "$key"
    elif [ "$INSTALL" = "false" ]; then
        skip "$key (want $want, have ${have:-<unset>})"
    else
        KEY="$key" SETTINGS="$SETTINGS" DESIRED="$DESIRED" python3 -c '
import json, os
key = os.environ["KEY"]
settings_path = os.environ["SETTINGS"]
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
try:
    with open(settings_path) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}
with open(os.environ["DESIRED"]) as f:
    desired = json.load(f)
data[key] = desired[key]
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
'
        installed "$key"
    fi
}

# autoMemoryEnabled false: durable facts go in an AGENTS.md or a skill, never in
# Claude's private memory files.
# pluginConfigs: Claude reads every AGENTS.md even if a CLAUDE.md sits on the
# path (default: one CLAUDE.md hides them all); projects keep no CLAUDE.md.
# skillOverrides: hides skills that only work elsewhere (Anthropic's
# google-workspace needs claude.ai's Google connector, here our own google-workspace skill does it;
# built-in-browser and computer-use need the desktop app; chrome-browser repeats
# the built-in claude-in-chrome; docs needs the Claude Docs MCP, off here; docx/pptx/xlsx: no Microsoft
# Office on this machine; whatsapp-cli's own skill sends by bringing WhatsApp to the
# front, our whatsapp skill replaces it).
# permissions: deny rules that keep every agent out of the user's own Chrome profile (Default), which holds their
# password vault (user, 2026-10-20); the agents' rule is in files/AGENTS_LOCAL.md "Chrome profiles".
for key in respondToBashCommands theme statusLine cleanupPeriodDays autoMemoryEnabled skillOverrides pluginConfigs permissions; do
    _check_or_set_json "$key"
done

# Keys this module set before and no longer wants: removed. claudeMdExcludes
# skipped ~/AGENTS.md, a copy of ~/.claude/CLAUDE.md that no longer exists.
for key in claudeMdExcludes; do
    if ! KEY="$key" SETTINGS="$SETTINGS" python3 -c 'import json, os, sys; sys.exit(os.environ["KEY"] not in json.load(open(os.environ["SETTINGS"])))' 2>/dev/null; then
        ok "$key (unset)"
    elif [ "$INSTALL" = "false" ]; then
        skip "remove retired $key"
    else
        KEY="$key" SETTINGS="$SETTINGS" python3 -c '
import json, os
path = os.environ["SETTINGS"]
with open(path) as f:
    data = json.load(f)
del data[os.environ["KEY"]]
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
'
        installed "removed retired $key"
    fi
done
