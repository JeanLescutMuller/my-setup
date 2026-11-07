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

# $1 = key; $2 (optional) = the wanted value as JSON, else files/claude_settings.json's.
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
    want=$(KEY="$key" DESIRED="$DESIRED" WANT="${2:-}" python3 -c '
import json, os
key = os.environ["KEY"]
if os.environ["WANT"]:
    print(json.dumps(json.loads(os.environ["WANT"]), sort_keys=True))
else:
    with open(os.environ["DESIRED"]) as f:
        print(json.dumps(json.load(f)[key], sort_keys=True))
')

    if [ "$have" = "$want" ]; then
        ok "$key"
    elif [ "$INSTALL" = "false" ]; then
        skip "$key (want $want, have ${have:-<unset>})"
    else
        KEY="$key" SETTINGS="$SETTINGS" WANT="$want" python3 -c '
import json, os
key = os.environ["KEY"]
settings_path = os.environ["SETTINGS"]
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
try:
    with open(settings_path) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}
data[key] = json.loads(os.environ["WANT"])
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
# Allow rules: an agent adds, edits, completes or deletes its own Todoist tasks with the `task` command without
# asking (user, 2026-11-03: auto mode's classifier had blocked them as external writes).
# remoteControlAtStartup: every interactive session turns on Remote Control (/rc) by itself, so it
# shows in the Claude app (user, 2026-10-22).
for key in respondToBashCommands theme cleanupPeriodDays autoMemoryEnabled skillOverrides pluginConfigs permissions remoteControlAtStartup; do
    _check_or_set_json "$key"
done

# statusLine: agent-statusline's display, fed by agent-tracker when it is installed (its bin exists):
# `(agent-tracker tick 2>/dev/null || cat) | bash $HOME/.claude/statusline-command.sh`: if agent-tracker is ever
# missing, the command fails without reading stdin and cat passes the payload on, so the display never goes blank. tick records the payload and copies it to
# stdout unchanged; owning the chain here means reinstalling or rewriting the display cannot drop the tracking
# (agent-tracker's DESIGN.md §6). Without agent-tracker: the display alone. refreshInterval stays from the file.
_sl_want=$(TRACKER="$([ -e "$HOME/.local/bin/agent-tracker" ] && echo 1)" DESIRED="$DESIRED" python3 -c '
import json, os
want = json.load(open(os.environ["DESIRED"]))["statusLine"]
if os.environ["TRACKER"]:
    want["command"] = "(agent-tracker tick 2>/dev/null || cat) | " + want["command"]
print(json.dumps(want))
')
_check_or_set_json statusLine "$_sl_want"

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

# The Chrome kit's hook groups under "hooks" (macOS only, once modules/chrome_kit.sh deployed hook.py).
# "hooks" is shared: agent-session-manager's install.sh owns its SessionStart/SessionEnd groups; this module owns
# only the groups whose command contains opt/my-setup/chrome/hook.py, replaces just those, keeps everything else
# (the same rule asm follows). The command checks the file first: a missing script would make python exit 2, which
# Claude Code reads as "block this tool call"; `|| true` keeps the hook failing open.
_ck_hook="$HOME/opt/my-setup/chrome/hook.py"
if [ "$(uname)" = Darwin ] && [ -f "$_ck_hook" ]; then
    _ck_state=$(INSTALL="$INSTALL" SETTINGS="$SETTINGS" python3 - <<'PYEOF'
import json, os
ID = 'opt/my-setup/chrome/hook.py'
CMD = '[ ! -f "$HOME/opt/my-setup/chrome/hook.py" ] || python3 -I "$HOME/opt/my-setup/chrome/hook.py" || true'
hook = {'type': 'command', 'command': CMD, 'timeout': 10}
WANT = {  # event -> matchers
    'PreToolUse': ['mcp__claude-in-chrome__.*', 'Bash'],
    'PostToolUse': ['mcp__claude-in-chrome__.*'],
    'UserPromptSubmit': [''],
    'Stop': [''],
    'SubagentStop': [''],
}
path = os.environ['SETTINGS']
with open(path) as f:
    data = json.load(f)
hooks = data.setdefault('hooks', {})
mine = lambda g: any(ID in h.get('command', '') for h in g.get('hooks', []))
same = all([g for g in hooks.get(ev, []) if mine(g)] == [{'matcher': m, 'hooks': [hook]} for m in l_m] for ev, l_m in WANT.items()) \
    and not any(mine(g) for ev, l_g in hooks.items() if ev not in WANT for g in l_g)
if same:
    print('ok')
elif os.environ['INSTALL'] != 'true':
    print('skip')
else:
    for ev in list(hooks):
        hooks[ev] = [g for g in hooks[ev] if not mine(g)]
        if not hooks[ev]:
            del hooks[ev]
    for ev, l_m in WANT.items():
        hooks.setdefault(ev, []).extend({'matcher': m, 'hooks': [hook]} for m in l_m)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)
    print('installed')
PYEOF
)
    case "$_ck_state" in
        ok) ok "hooks: Chrome kit groups" ;;
        skip) skip "hooks: Chrome kit groups" ;;
        installed) installed "hooks: Chrome kit groups (PreToolUse x2, PostToolUse, UserPromptSubmit, Stop, SubagentStop)" ;;
        *) fail "hooks: Chrome kit groups ($_ck_state)" ;;
    esac
elif [ "$(uname)" = Darwin ]; then
    skip "hooks: Chrome kit groups ($_ck_hook not deployed: run the chrome_kit module first)"
fi
