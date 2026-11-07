#!/bin/bash
# Removes what modules/agent_links.sh deploys: the skill links
# in ~/.claude/skills and ~/.agents/skills
# (only links that point into ~/opt/my-setup), then the read-only copies
# they point to; what modules/my_context.sh links (its copy and history.git are kept); the remote control LaunchAgent (modules/remote_control.sh), and the links of cc-map and cc-rc if an older deploy left them (parked since 2026-11-07, parked/README.md); the Hammerspoon config link (modules/hammerspoon.sh); the Chrome kit (modules/chrome_kit.sh: its code, chrome-claim, chrome-who, the Agent tab notes extension and its native host manifest, and its hook groups in ~/.claude/settings.json; its record in ~/opt/my-setup/state/chrome/ is kept).
# Dotfiles, the shell rc block, git config and the tools are left alone.
#
# Usage: bash uninstall.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

OPT_DIR="$HOME/opt/my-setup"

_remove_link() {
    local link="$1" target="$2"
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
        rm "$link"
        installed "removed $link"
    fi
}

step "agent links"
for dst in "$OPT_DIR"/skills/*/; do
    [ -d "$dst" ] || continue
    for home in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
        _remove_link "$home/$(basename "$dst")" "${dst%/}"
    done
done
for copy in "$OPT_DIR/home_AGENTS.md" "$OPT_DIR/skills"; do
    if [ -e "$copy" ]; then
        chmod -R u+w "$copy" && rm -r "$copy"
        installed "removed $copy"
    fi
done

step "my-context"
_ctx="$OPT_DIR/context"
if [ "$(uname)" = Darwin ]; then
    _cs_label="com.jeanlescut.my-setup.context-sync"
    launchctl bootout "gui/$(id -u)/$_cs_label" 2>/dev/null && installed "stopped $_cs_label"
    _remove_link "$HOME/Library/LaunchAgents/$_cs_label.plist" "$OPT_DIR/$_cs_label.plist"
    for f in "$OPT_DIR/$_cs_label.plist" "$OPT_DIR/context-sync.sh" "$OPT_DIR/context-sync.conf"; do
        [ -f "$f" ] && rm "$f" && installed "removed $f"
    done
fi
_remove_link "$HOME/.claude/CLAUDE.md" "$_ctx/AGENTS.md"
_remove_link "$HOME/.codex/AGENTS.md" "$_ctx/AGENTS.md"
_remove_link "$HOME/.local/bin/context-sync" "$_ctx/context-sync"
_remove_link "$HOME/.local/bin/context-history" "$_ctx/context-history"
for dst in "$_ctx"/snapshot/skills/*/; do
    [ -d "$dst" ] || continue
    for home in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
        _remove_link "$home/$(basename "$dst")" "${dst%/}"
    done
done
warn "kept $_ctx (the local copy and history.git): agents now start without the machine-wide rules"

step "chrome kit"
if [ "$(uname)" = Darwin ]; then
    # hook groups first, so no session calls a hook whose file is gone (the command also checks the file)
    SETTINGS="$HOME/.claude/settings.json" python3 - <<'PYEOF' && installed "removed the Chrome kit hook groups"
import json, os
path, ID = os.environ['SETTINGS'], 'opt/my-setup/chrome/hook.py'
with open(path) as f:
    data = json.load(f)
hooks = data.get('hooks', {})
for ev in list(hooks):
    hooks[ev] = [g for g in hooks[ev] if not any(ID in h.get('command', '') for h in g.get('hooks', []))]
    if not hooks[ev]:
        del hooks[ev]
with open(path + '.tmp', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
os.replace(path + '.tmp', path)
PYEOF
    _remove_link "$HOME/.local/bin/agent-chrome" "$OPT_DIR/chrome/agent_chrome.py"
    _remove_link "$HOME/.local/bin/chrome-claim" "$OPT_DIR/chrome/chrome_claim.py"
    _remove_link "$HOME/.local/bin/chrome-who" "$OPT_DIR/chrome/chrome_who.py"
    _nmh="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.jeanlescut.agent_tab_notes.json"
    grep -q "$OPT_DIR/chrome/native_host.py" "$_nmh" 2>/dev/null && rm "$_nmh" && installed "removed $_nmh"
    for f in hook.py chrome_kit.py agent_chrome.py chrome_claim.py chrome_who.py launch_headless.py native_host.py; do
        [ -f "$OPT_DIR/chrome/$f" ] && rm "$OPT_DIR/chrome/$f" && installed "removed $OPT_DIR/chrome/$f"
    done
    for f in manifest.json background.js push.js note.js sidepanel.html sidepanel.js; do
        [ -f "$OPT_DIR/chrome/extension/$f" ] && rm "$OPT_DIR/chrome/extension/$f" && installed "removed $OPT_DIR/chrome/extension/$f"
    done
    [ -d "$OPT_DIR/chrome/extension" ] && rmdir "$OPT_DIR/chrome/extension" 2>/dev/null && installed "removed $OPT_DIR/chrome/extension"
    [ -d "$OPT_DIR/chrome" ] && rmdir "$OPT_DIR/chrome" 2>/dev/null && installed "removed $OPT_DIR/chrome"
    warn "kept $OPT_DIR/state/chrome (the record of what agents opened)"
fi

step "hammerspoon"
if [ "$(uname)" = Darwin ]; then
    _remove_link "$HOME/.hammerspoon/init.lua" "$OPT_DIR/hammerspoon/init.lua"
    [ -f "$OPT_DIR/hammerspoon/init.lua" ] && rm "$OPT_DIR/hammerspoon/init.lua" && installed "removed $OPT_DIR/hammerspoon/init.lua"
    warn "kept /Applications/Hammerspoon.app (brew uninstall --cask hammerspoon removes it)"
fi

step "remote control service"
if [ "$(uname)" = Darwin ]; then
    _rc_label="com.jeanlescut.my-setup.remote-control"
    launchctl bootout "gui/$(id -u)/$_rc_label" 2>/dev/null && installed "stopped $_rc_label"
    _remove_link "$HOME/Library/LaunchAgents/$_rc_label.plist" "$OPT_DIR/$_rc_label.plist"
    for f in "$OPT_DIR/$_rc_label.plist" "$OPT_DIR/remote_control.sh"; do
        [ -f "$f" ] && rm "$f" && installed "removed $f"
    done
    _remove_link "$HOME/.local/bin/cc-map" "$OPT_DIR/bin/cc-map"
    _remove_link "$HOME/.local/bin/cc-rc" "$OPT_DIR/bin/cc-rc"
elif [ "$(uname)" = Linux ]; then
    _rc_name="com.jeanlescut.my-setup.remote-control.service"
    systemctl --user disable --now "$_rc_name" 2>/dev/null && installed "stopped $_rc_name"
    _remove_link "$HOME/.config/systemd/user/$_rc_name" "$OPT_DIR/$_rc_name"
    for f in "$OPT_DIR/$_rc_name" "$OPT_DIR/remote_control.sh"; do
        [ -f "$f" ] && rm "$f" && installed "removed $f"
    done
    systemctl --user daemon-reload 2>/dev/null
fi
