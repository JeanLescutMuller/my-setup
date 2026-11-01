#!/bin/bash
# The Chrome kit (macOS only): every agent's Chrome use recorded and its rules enforced.
#
#   chrome/*.py (not tests/)  ->  ~/opt/my-setup/chrome/      hook.py, chrome_kit.py, chrome_claim.py, chrome_who.py,
#                                                             launch_headless.py
#   ~/.local/bin/chrome-claim ->  ~/opt/my-setup/chrome/chrome_claim.py
#   ~/.local/bin/chrome-who   ->  ~/opt/my-setup/chrome/chrome_who.py
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
    _ck_bins=("chrome_claim.py:chrome-claim" "chrome_who.py:chrome-who")

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

    if $_ck_same; then
        ok "$_ck_dst, chrome-claim, chrome-who"
    elif [ "$INSTALL" = "false" ]; then
        skip "$_ck_dst, chrome-claim, chrome-who"
    else
        mkdir -p "$_ck_dst" "$_ck_state" "$HOME/.local/bin"
        for f in "$_ck_dst"/*.py; do                                   # left chrome/: removed, one by one
            [ -e "$f" ] && [ ! -f "$_ck_src/${f##*/}" ] && rm "$f" && installed "removed $f"
        done
        # copy to a temporary name, then rename: a hook running right now never reads half a file
        for f in "$_ck_src"/*.py; do
            cp "$f" "$_ck_dst/.${f##*/}.tmp" && mv "$_ck_dst/.${f##*/}.tmp" "$_ck_dst/${f##*/}"
        done
        chmod +x "$_ck_dst"/hook.py "$_ck_dst"/chrome_claim.py "$_ck_dst"/chrome_who.py "$_ck_dst"/launch_headless.py
        for entry in "${_ck_bins[@]}"; do
            ln -sfn "$_ck_dst/${entry%%:*}" "$HOME/.local/bin/${entry#*:}"
        done
        installed "$_ck_dst, chrome-claim, chrome-who"
    fi
fi
