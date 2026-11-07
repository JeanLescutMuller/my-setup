#!/bin/bash
# Deploys the personal tool repos - each ships its own idempotent
# install.sh.
#
# ~/dev/<name> only exists on the MacBook (the one machine development happens
# on). Elsewhere install.sh runs from a scratch clone deleted right after: every
# install.sh deploys what it needs into ~/opt/<name>/ (skills included), so
# nothing points back into the clone.
step "tools"

TOOLS=(agent-tracker agent-resume agent-notify agent-statusline)   # agent-tracker first: agent-resume reads its files (2026-11-07)

for name in "${TOOLS[@]}"; do
    if [ "$INSTALL" = "false" ]; then
        skip "$name install.sh"
        continue
    fi

    repo_dir="$HOME/dev/$name"
    url="https://github.com/JeanLescutMuller/$name.git"
    scratch_dir=""

    if [ -d "$repo_dir" ]; then
        ok "$name (using existing ~/dev checkout)"
    else
        scratch_dir="$(mktemp -d)"
        repo_dir="$scratch_dir/$name"
        if ! git clone -q "$url" "$repo_dir"; then
            fail "$name (clone failed)"
            rm -rf "$scratch_dir"
            continue
        fi
        installed "$name (from a scratch clone, not kept)"
    fi

    if bash "$repo_dir/install.sh" >/dev/null 2>&1; then
        installed "$name install.sh"
    else
        fail "$name install.sh"
    fi

    if [ "$name" = "agent-notify" ]; then
        # notify owns its own tmux-hooks injection via `notify init`
        # (agent-notify's release/notify, guarded by the "# ┌─ AGENT-NOTIFY BLOCK ─"
        # marker) - this is deliberately not part of the tmux.conf dotfile.
        NOTIFY_BIN="$HOME/opt/agent-notify/app/notify"
        if command -v tmux >/dev/null 2>&1 && grep -qF "# ┌─ AGENT-NOTIFY BLOCK" "$HOME/.tmux.conf" 2>/dev/null; then
            ok "notify init (tmux hooks)"
        elif [ -x "$NOTIFY_BIN" ]; then
            "$NOTIFY_BIN" init && installed "notify init (tmux hooks)" || fail "notify init (tmux hooks)"
        else
            fail "notify init (tmux hooks) - $NOTIFY_BIN not found, install.sh may have failed"
        fi
    fi

    [ -n "$scratch_dir" ] && rm -rf "$scratch_dir"

done
