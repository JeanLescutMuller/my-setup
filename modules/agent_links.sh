#!/bin/bash
# Skills, deployed like everything else: a read-only copy
# under ~/opt/my-setup/, linked from where the agents look. An edit through
# a link fails (read-only): edit the source in ~/dev/my-setup, then
# re-run `INSTALL=true bash bootstrap.sh agent_links`. uninstall.sh undoes it.
# The machine-wide rules (~/.claude/CLAUDE.md, ~/.codex/AGENTS.md) and the life skills: modules/my_context.sh.
#   skills/<name>/       -> ~/opt/my-setup/skills/<name>/ <- ~/.claude/skills/<name>, ~/.agents/skills/<name>
step "agent links"

OPT_DIR="$HOME/opt/my-setup"
OPT_SKILLS="$OPT_DIR/skills"
SKILL_HOMES=("$HOME/.claude/skills" "$HOME/.agents/skills")

# $1 (file or folder) -> read-only copy $2, replaced whole when it differs.
_deploy_readonly() {
    local src="$1" dst="$2"
    if [ -e "$dst" ] && [ ! -w "$dst" ] && diff -rq "$src" "$dst" >/dev/null 2>&1; then
        ok "$dst"
        return
    fi
    if [ "$INSTALL" = "false" ]; then
        skip "$dst"
        return
    fi
    mkdir -p "$(dirname "$dst")"
    [ -e "$dst" ] && chmod -R u+w "$dst" && rm -r "$dst"
    cp -R "$src" "$dst" && chmod -R a-w "$dst"
    installed "$dst"
}

# Link $2 -> $1. A real folder at $2 is replaced only when it is an old copy of
# $3 (identical but for *.bak); anything else is preserved, with a warning.
_deploy_link() {
    local target="$1" link="$2" src="${3:-}"
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
        ok "$link"
        return
    fi
    if [ -d "$link" ] && [ ! -L "$link" ] && ! diff -rq -x '*.bak' "$link" "$src" >/dev/null 2>&1; then
        warn "$link is a real folder that differs from $src - preserving it, not linked"
        return
    fi
    if [ "$INSTALL" = "false" ]; then
        skip "$link"
        return
    fi
    mkdir -p "$(dirname "$link")"
    if [ -d "$link" ] && [ ! -L "$link" ]; then
        rm -r "$link"
    elif [ -f "$link" ] && [ ! -L "$link" ]; then
        _backup_before_overwrite "$link"
        rm "$link"
    fi
    ln -sfn "$target" "$link"
    installed "$link -> $target"
}

# $OPT_DIR/home_AGENTS.md was the deployed machine-wide rules file,
# moved out on 2026-10-16 (today files/AGENTS_LOCAL.md). Removed once no link points to it.
_old="$OPT_DIR/home_AGENTS.md"
if [ -e "$_old" ]; then
    if [ "$(readlink "$HOME/.claude/CLAUDE.md")" = "$_old" ] || [ "$(readlink "$HOME/.codex/AGENTS.md")" = "$_old" ]; then
        warn "$_old still linked - run the my_context module first (it relinks ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md)"
    elif [ "$INSTALL" = "false" ]; then
        skip "remove old copy $_old"
    else
        chmod u+w "$_old" && rm "$_old"
        installed "removed old copy $_old"
    fi
fi

# A skill gone from skills/ (moved or renamed): its links and copy go too.
for dst in "$OPT_SKILLS"/*/; do
    [ -d "$dst" ] || continue
    dst="${dst%/}"; name=$(basename "$dst")
    [ -d "$SCRIPT_DIR/skills/$name" ] && continue
    if [ "$INSTALL" = "false" ]; then
        skip "remove old skill $name"
        continue
    fi
    for home in "${SKILL_HOMES[@]}"; do
        [ -L "$home/$name" ] && [ "$(readlink "$home/$name")" = "$dst" ] && rm "$home/$name"
    done
    chmod -R u+w "$dst" && rm -r "$dst" && installed "removed old skill $name"
done

for src in "$SCRIPT_DIR"/skills/*/; do
    src="${src%/}"; name=$(basename "$src")
    _deploy_readonly "$src" "$OPT_SKILLS/$name"
    for home in "${SKILL_HOMES[@]}"; do
        _deploy_link "$OPT_SKILLS/$name" "$home/$name" "$src"
    done
done

# --- Migrations from earlier layouts ---

# ~/AGENTS.md was this project's deployed copy of the machine-wide rules (now files/AGENTS_LOCAL.md), replaced
# by the links above. Removed only while it still matches.
_copy="$HOME/AGENTS.md"
if [ -f "$_copy" ] && [ ! -L "$_copy" ]; then
    if ! diff -q "$_copy" "$SCRIPT_DIR/files/AGENTS_LOCAL.md" >/dev/null 2>&1; then
        warn "$_copy differs from files/AGENTS_LOCAL.md - preserving it (merge it there, then delete it)"
    elif [ "$INSTALL" = "false" ]; then
        skip "remove old copy $_copy"
    else
        rm "$_copy"
        installed "removed old copy $_copy"
    fi
fi

# The dev-wide instructions were merged into the home instructions. Remove only
# the exact file this project used to deploy and its matching compatibility
# link; preserve anything customized or independently created at those paths.
LEGACY_DEV_AGENTS_SHA256="2844c72ab7f1943c8e02e14b131dad11f9746e50586ee06d6e6a31e925b505c5"
_agents="$HOME/dev/AGENTS.md"
_claude="$HOME/dev/CLAUDE.md"
_hash=""
[ -f "$_agents" ] && [ ! -L "$_agents" ] && _hash="$(_sha256 < "$_agents")"
if [ "$_hash" = "$LEGACY_DEV_AGENTS_SHA256" ]; then
    if [ "$INSTALL" = "false" ]; then
        skip "legacy ~/dev agent instructions"
    else
        _backup_before_overwrite "$_agents"
        rm "$_agents"
        [ -L "$_claude" ] && [ "$(readlink "$_claude")" = "$_agents" ] && rm "$_claude"
        installed "merged ~/dev agent instructions into the home instructions"
    fi
elif [ -e "$_agents" ] || [ -L "$_agents" ]; then
    warn "legacy dev instructions were customized - preserving $_agents and $_claude"
fi

# Skills that were renamed: remove the old deployed folder, but only when it
# holds nothing but the SKILL.md (and its .bak) this project put there.
RENAMED_SKILLS=(todoist-tasks taskforce gws-people services claude-config-ownership gws)
for _old in "${RENAMED_SKILLS[@]}"; do
    for _dir in "$HOME/.claude/skills/$_old" "$HOME/.agents/skills/$_old"; do
        [ -d "$_dir" ] && [ ! -L "$_dir" ] || continue
        if [ -n "$(cd "$_dir" && ls -A | grep -v -x -e SKILL.md -e SKILL.md.bak)" ]; then
            warn "renamed skill folder has extra files - preserving $_dir"
        elif [ "$INSTALL" = "false" ]; then
            skip "renamed skill $_dir"
        else
            rm -r "$_dir"
            installed "removed renamed skill $_dir"
        fi
    done
done
