#!/bin/bash
# my-context: the Drive folder Personal/my-context/ (the only source of the user's facts, shared rules and life skills,
# since 2026-10-19; why: its design/DESIGN.md), made loadable by every agent even offline, with its history:
#   files/AGENTS_LOCAL.md        -> ~/opt/my-setup/context/AGENTS_LOCAL.md (read-only)
#   files/context_sync.sh        -> ~/opt/my-setup/context/context-sync     <- ~/.local/bin/context-sync
#   files/context_history.sh     -> ~/opt/my-setup/context/context-history  <- ~/.local/bin/context-history
#   files/context_drive_pull.py  -> ~/opt/my-setup/context/context-drive-pull (context-sync's way in when ~/gdrive is forbidden)
#   context-sync, run here: snapshot/ (read-only copy of the Drive folder), AGENTS.md (AGENTS_LOCAL.md + AGENTS_SHARED.md),
#                           the life skills' links in ~/.claude/skills and ~/.agents/skills
#   ~/opt/my-setup/context/AGENTS.md <- ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md
#   the Mac only (it has the Drive): history.git (a bare clone of GitHub my-context) and the job my-setup.context-sync
#   (files/context-sync.entrypoint.sh -> ~/opt/my-setup/context-sync.sh, LaunchAgent every 15 min, job-runner)
# Then the old deploy of the repo my-context (~/opt/my-context/) goes, once nothing links into it. uninstall.sh undoes it.
step "my-context (the Drive folder Personal/my-context/)"

CTX="$HOME/opt/my-setup/context"

# files/$1 -> $2, mode $3, when it differs.
_ctx_copy() {
    local src="$SCRIPT_DIR/files/$1" dst="$2" mode="$3"
    if [ -f "$dst" ] && diff -q "$src" "$dst" >/dev/null 2>&1; then ok "$dst"; return; fi
    if [ "$INSTALL" = "false" ]; then skip "$dst"; return; fi
    mkdir -p "$(dirname "$dst")"
    [ -e "$dst" ] && chmod u+w "$dst"
    cp "$src" "$dst" && chmod "$mode" "$dst" && installed "$dst"
}

# Link $1 -> $2 (a real file there is kept as .bak).
_ctx_link() {
    local link="$1" target="$2"
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then ok "$link"; return; fi
    if [ "$INSTALL" = "false" ]; then skip "$link -> $target"; return; fi
    mkdir -p "$(dirname "$link")"
    [ -f "$link" ] && [ ! -L "$link" ] && mv "$link" "$link.bak" && warn "$link was a real file - kept as $link.bak"
    ln -sfn "$target" "$link" && installed "$link -> $target"
}

_ctx_copy AGENTS_LOCAL.md "$CTX/AGENTS_LOCAL.md" a-w
_ctx_copy context_sync.sh "$CTX/context-sync" 555
_ctx_copy context_history.sh "$CTX/context-history" 555
_ctx_copy context_drive_pull.py "$CTX/context-drive-pull" 555
_ctx_link "$HOME/.local/bin/context-sync" "$CTX/context-sync"
_ctx_link "$HOME/.local/bin/context-history" "$CTX/context-history"

# The history, where the Drive is (the Mac).
if [ -e "$HOME/gdrive" ]; then
    if [ -d "$CTX/history.git" ]; then
        ok "$CTX/history.git"
    elif [ "$INSTALL" = "false" ]; then
        skip "$CTX/history.git"
    elif git clone -q --bare https://github.com/JeanLescutMuller/my-context.git "$CTX/history.git"; then
        installed "$CTX/history.git (bare clone of GitHub my-context)"
    else
        fail "$CTX/history.git: git clone failed - context-sync keeps no history until it exists"
    fi
fi

# What agents load: built now, then linked (never a link to a file that is not there).
if [ "$INSTALL" = "true" ]; then
    CONTEXT_NO_VM=1 "$CTX/context-sync" -m "${CONTEXT_SYNC_MSG:-sync by the bootstrap of my-setup}" --agent "my-setup bootstrap.sh" | sed 's/^/    /'
    case "${PIPESTATUS[0]}" in
        0) installed "context-sync" ;;
        3) warn "context-sync: the Drive folder is unreachable - agents load the last copy" ;;
        *) fail "context-sync failed" ;;
    esac
fi
if [ -s "$CTX/AGENTS.md" ]; then
    _ctx_link "$HOME/.claude/CLAUDE.md" "$CTX/AGENTS.md"
    _ctx_link "$HOME/.codex/AGENTS.md" "$CTX/AGENTS.md"
else
    fail "$CTX/AGENTS.md missing - ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md left as they are"
fi

# The job, on the Mac (with job-runner): context-sync every 15 min.
if [ "$(uname)" = Darwin ] && [ -e "$HOME/gdrive" ]; then
    _cs_label="com.jeanlescut.my-setup.context-sync"
    _cs_entry="$HOME/opt/my-setup/context-sync.sh"
    _cs_plist="$HOME/opt/my-setup/$_cs_label.plist"
    _cs_link="$HOME/Library/LaunchAgents/$_cs_label.plist"
    _cs_body="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\"><dict>
  <key>Label</key><string>$_cs_label</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$_cs_entry</string></array>
  <key>StartInterval</key><integer>900</integer><key>RunAtLoad</key><true/><key>AbandonProcessGroup</key><true/>
</dict></plist>"
    _ctx_copy context-sync.conf "$HOME/opt/my-setup/context-sync.conf" 644
    if diff -q "$SCRIPT_DIR/files/context-sync.entrypoint.sh" "$_cs_entry" >/dev/null 2>&1 \
        && [ "$(cat "$_cs_plist" 2>/dev/null)" = "$_cs_body" ] \
        && [ -L "$_cs_link" ] && [ "$(readlink "$_cs_link")" = "$_cs_plist" ] \
        && launchctl print "gui/$(id -u)/$_cs_label" >/dev/null 2>&1; then
        ok "LaunchAgent $_cs_label"
    elif [ "$INSTALL" = "false" ]; then
        skip "LaunchAgent $_cs_label"
    else
        [ -f "$HOME/opt/job-runner/lib.sh" ] || warn "job-runner not installed (~/opt/job-runner/lib.sh): every check fails until it is"
        mkdir -p "$HOME/Library/LaunchAgents"
        cp "$SCRIPT_DIR/files/context-sync.entrypoint.sh" "$_cs_entry"
        printf '%s\n' "$_cs_body" > "$_cs_plist"
        ln -sfn "$_cs_plist" "$_cs_link"
        [ -f "$HOME/opt/job-runner/put-conf.sh" ] && { bash "$HOME/opt/job-runner/put-conf.sh" my-setup.context-sync "$HOME/opt/my-setup/context-sync.conf" >/dev/null 2>&1 || warn "dashboard settings not sent"; }
        launchctl bootout "gui/$(id -u)/$_cs_label" 2>/dev/null || true
        if launchctl bootstrap "gui/$(id -u)" "$_cs_link"; then
            installed "LaunchAgent $_cs_label (every 15 min)"
        else
            fail "LaunchAgent $_cs_label: launchctl bootstrap failed"
        fi
    fi
fi

# --- Migration: the repo my-context deployed to ~/opt/my-context/ until 2026-10-19. Removed once nothing links into it.
_old="$HOME/opt/my-context"
if [ -d "$_old" ]; then
    _still=""
    for _l in "$HOME/.claude/CLAUDE.md" "$HOME/.codex/AGENTS.md" "$HOME/.claude/skills"/* "$HOME/.agents/skills"/*; do
        [ -L "$_l" ] && case "$(readlink "$_l")" in "$_old"/*) _still="$_still $_l" ;; esac
    done
    if [ -n "$_still" ]; then
        warn "$_old still linked from:$_still - kept"
    elif [ "$INSTALL" = "false" ]; then
        skip "remove old deploy $_old"
    else
        chmod -R u+w "$_old" && rm -r "$_old" && installed "removed old deploy $_old"
    fi
fi
