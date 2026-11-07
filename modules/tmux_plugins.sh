#!/bin/bash
# tmux plugins, cloned at a pinned tag into ~/opt/my-setup/tmux/plugins/ and loaded by files/tmux.conf (no tpm):
#
#   tmux-resurrect   saves / restores every tmux session, window, pane, layout and folder
#                    (by hand: prefix + Ctrl-s / prefix + Ctrl-r)
#   tmux-continuum   runs resurrect's save every 5 min (files/tmux.conf); restores only by hand
#
# Snapshots: ~/opt/my-setup/state/tmux/resurrect/ (`last` = the newest). Why: doc/macbook_sudden_shutdowns.md
# (a crash loses every tmux session). A plugin dir that is not at its pinned tag is re-cloned.

step "tmux plugins (resurrect, continuum)"

_tp_dir="$HOME/opt/my-setup/tmux/plugins"
_tp_list=(
    "tmux-resurrect:https://github.com/tmux-plugins/tmux-resurrect:v4.0.0"
    "tmux-continuum:https://github.com/tmux-plugins/tmux-continuum:v3.1.0"
)
_tp_changed=false

for _tp in "${_tp_list[@]}"; do
    IFS=: read -r _tp_name _tp_proto _tp_rest _tp_tag <<< "$_tp"
    _tp_url="$_tp_proto:$_tp_rest"
    _tp_path="$_tp_dir/$_tp_name"
    if [ "$(git -C "$_tp_path" describe --tags --exact-match 2>/dev/null)" = "$_tp_tag" ]; then
        ok "$_tp_name $_tp_tag"
        continue
    fi
    if [ "$INSTALL" = "false" ]; then
        skip "$_tp_name $_tp_tag"
        continue
    fi
    mkdir -p "$_tp_dir"
    [ -d "$_tp_path" ] && rm -rf "$_tp_path"
    if git clone -q --depth 1 --branch "$_tp_tag" "$_tp_url" "$_tp_path" 2>/dev/null; then
        installed "$_tp_name $_tp_tag"
        _tp_changed=true
    else
        fail "$_tp_name $_tp_tag (git clone failed)"
    fi
done

mkdir -p "$HOME/opt/my-setup/state/tmux/resurrect"

if [ "$_tp_changed" = true ] && tmux info &>/dev/null; then
    tmux source-file "$HOME/.tmux.conf" 2>/dev/null && ok "tmux config reloaded (plugins loaded)"
fi
