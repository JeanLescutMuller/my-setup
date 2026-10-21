#!/bin/bash
# Hammerspoon (macOS only): 2-key shortcuts for the "Importants" Sheet's Blocks macro (files/hammerspoon_init.lua:
# ⌥B ⌥D ⌥R → ⌘⌥⇧1/2/3, only in that Sheet's Chrome window; user, 2026-10-21).
#
#   /Applications/Hammerspoon.app        brew install --cask hammerspoon
#   ~/opt/my-setup/hammerspoon/init.lua  copy of files/hammerspoon_init.lua  ← ~/.hammerspoon/init.lua (link)
#
# Once, by hand: System Settings › Privacy & Security › Accessibility › Hammerspoon on (macOS asks for it on the first
# start; without it the keys do nothing). The config reloads by itself when its copy changes.

step "hammerspoon"

if [ "$(uname)" != Darwin ]; then
    ok "not macOS - skipped"
else
    _hs_src="$SCRIPT_DIR/files/hammerspoon_init.lua"
    _hs_dst="$HOME/opt/my-setup/hammerspoon/init.lua"
    _hs_link="$HOME/.hammerspoon/init.lua"

    if [ -d /Applications/Hammerspoon.app ]; then
        ok "Hammerspoon.app"
    elif [ "$INSTALL" = "false" ]; then
        skip "Hammerspoon.app"
    elif brew install --cask hammerspoon >/dev/null 2>&1; then
        installed "Hammerspoon.app"
    else
        fail "Hammerspoon.app: brew install --cask hammerspoon failed"
    fi

    if diff -q "$_hs_src" "$_hs_dst" >/dev/null 2>&1 && [ -L "$_hs_link" ] && [ "$(readlink "$_hs_link")" = "$_hs_dst" ]; then
        ok "hammerspoon init.lua"
    elif [ "$INSTALL" = "false" ]; then
        skip "hammerspoon init.lua"
    else
        mkdir -p "${_hs_dst%/*}" "${_hs_link%/*}"
        cp "$_hs_src" "$_hs_dst"
        [ -e "$_hs_link" ] && [ ! -L "$_hs_link" ] && _backup_before_overwrite "$_hs_link" && rm "$_hs_link"
        ln -sfn "$_hs_dst" "$_hs_link"
        installed "hammerspoon init.lua"
    fi

    if [ "$INSTALL" != "false" ] && [ -d /Applications/Hammerspoon.app ] && ! pgrep -xq Hammerspoon; then
        open -g /Applications/Hammerspoon.app && installed "Hammerspoon started"
    fi
fi
