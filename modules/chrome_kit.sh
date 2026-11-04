#!/bin/bash
# The Chrome kit (macOS only): every agent's Chrome use recorded and its rules enforced.
#
#   chrome/*.py (not tests/)  ->  ~/opt/my-setup/chrome/      hook.py, chrome_kit.py, agent_chrome.py, launch_headless.py,
#                                                             native_host.py, desktops.py (macOS desktops, for agent-chrome show), chrome_claim.py + chrome_who.py (old names)
#   chrome/extension/         ->  ~/opt/my-setup/chrome/extension/   the "Agent tab notes" extension: the user loads
#                                                             it once per agent profile (chrome://extensions, Load unpacked)
#   ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.jeanlescut.agent_tab_notes.json
#                                                             lets that extension (fixed id) start native_host.py; Chrome's
#                                                             own folder, read by every profile: no profile is touched
#   ~/.local/bin/agent-chrome ->  ~/opt/my-setup/chrome/agent_chrome.py
#   ~/.local/bin/chrome-claim ->  ~/opt/my-setup/chrome/chrome_claim.py   old names of agent-chrome (renamed 1 Nov
#   ~/.local/bin/chrome-who   ->  ~/opt/my-setup/chrome/chrome_who.py     2026): aliases until 2026-11-08
#   ~/opt/my-setup/state/chrome/                              open.json, history/, comments.jsonl, sessions/ (kept on
#                                                             reinstall and uninstall: it is the record)
# The hook groups in ~/.claude/settings.json are registered by modules/claude_config.sh, which runs after this.
# A file that left chrome/ is removed from the deployed copy.

step "chrome kit"

if [ "$(uname)" != Darwin ]; then
    ok "not macOS - skipped (Chrome runs on the Mac only)"
else
    _ck_src="$SCRIPT_DIR/chrome"
    _ck_dst="$HOME/opt/my-setup/chrome"
    _ck_state="$HOME/opt/my-setup/state/chrome"
    _ck_bins=("agent_chrome.py:agent-chrome" "chrome_claim.py:chrome-claim" "chrome_who.py:chrome-who")
    _ck_ext_id="hfnfcdbehfbggjaccimmnolmhdkbfdie"      # from the "key" in chrome/extension/manifest.json
    _ck_nmh="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.jeanlescut.agent_tab_notes.json"
    _ck_nmh_text="$(printf '{\n  "name": "com.jeanlescut.agent_tab_notes",\n  "description": "Agent tab notes: the Chrome kit record on the tab",\n  "path": "%s",\n  "type": "stdio",\n  "allowed_origins": ["chrome-extension://%s/"]\n}' "$_ck_dst/native_host.py" "$_ck_ext_id")"

    _ck_same=true
    for f in "$_ck_src"/*.py; do
        diff -q "$f" "$_ck_dst/${f##*/}" >/dev/null 2>&1 || _ck_same=false
    done
    for f in "$_ck_dst"/*.py; do
        [ -e "$f" ] && [ ! -f "$_ck_src/${f##*/}" ] && _ck_same=false
    done
    for entry in "${_ck_bins[@]}"; do
        [ "$(readlink "$HOME/.local/bin/${entry#*:}" 2>/dev/null)" = "$_ck_dst/${entry%%:*}" ] || _ck_same=false
    done
    [ -d "$_ck_state" ] || _ck_same=false
    for f in "$_ck_src"/extension/*; do
        diff -q "$f" "$_ck_dst/extension/${f##*/}" >/dev/null 2>&1 || _ck_same=false
    done
    for f in "$_ck_dst"/extension/*; do
        [ -e "$f" ] && [ ! -f "$_ck_src/extension/${f##*/}" ] && _ck_same=false
    done
    [ "$(cat "$_ck_nmh" 2>/dev/null)" = "$_ck_nmh_text" ] || _ck_same=false

    if $_ck_same; then
        ok "$_ck_dst, agent-chrome, extension, native host"
    elif [ "$INSTALL" = "false" ]; then
        skip "$_ck_dst, agent-chrome, extension, native host"
    else
        mkdir -p "$_ck_dst" "$_ck_state" "$HOME/.local/bin"
        for f in "$_ck_dst"/*.py; do                                   # left chrome/: removed, one by one
            [ -e "$f" ] && [ ! -f "$_ck_src/${f##*/}" ] && rm "$f" && installed "removed $f"
        done
        # copy to a temporary name, then rename: a hook running right now never reads half a file
        for f in "$_ck_src"/*.py; do
            cp "$f" "$_ck_dst/.${f##*/}.tmp" && mv "$_ck_dst/.${f##*/}.tmp" "$_ck_dst/${f##*/}"
        done
        chmod +x "$_ck_dst"/hook.py "$_ck_dst"/agent_chrome.py "$_ck_dst"/chrome_claim.py "$_ck_dst"/chrome_who.py "$_ck_dst"/launch_headless.py \
            "$_ck_dst"/native_host.py
        mkdir -p "$_ck_dst/extension"
        for f in "$_ck_dst"/extension/*; do                         # left chrome/extension/: removed, one by one
            [ -e "$f" ] && [ ! -f "$_ck_src/extension/${f##*/}" ] && rm "$f" && installed "removed $f"
        done
        for f in "$_ck_src"/extension/*; do
            cp "$f" "$_ck_dst/extension/.${f##*/}.tmp" && mv "$_ck_dst/extension/.${f##*/}.tmp" "$_ck_dst/extension/${f##*/}"
        done
        mkdir -p "${_ck_nmh%/*}"
        printf '%s\n' "$_ck_nmh_text" > "$_ck_nmh.tmp" && mv "$_ck_nmh.tmp" "$_ck_nmh"
        for entry in "${_ck_bins[@]}"; do
            ln -sfn "$_ck_dst/${entry%%:*}" "$HOME/.local/bin/${entry#*:}"
        done
        installed "$_ck_dst, agent-chrome, extension, native host"
        warn "new extension code: reload \"Agent tab notes\" in chrome://extensions of each agent profile (first time: Load unpacked $_ck_dst/extension)"
    fi
fi
