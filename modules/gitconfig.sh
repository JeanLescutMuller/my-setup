#!/bin/bash
# Ensures git identity, pull.rebase=false, and the right credential helper
# for this OS. On macOS, credential.helper usually already resolves to
# osxkeychain via the system-level gitconfig (Xcode Command Line Tools) -
# in that case this is a no-op check, nothing gets written to ~/.gitconfig.
# Also adds .DS_Store to the global gitignore (~/.config/git/ignore).
step "gitconfig"

GIT_NAME="Jean Lescut-Muller"
GIT_EMAIL="jean.lescut@gmail.com"

_check_or_set() {
    local key="$1" want="$2"
    local have
    have="$(git config --get "$key" 2>/dev/null)"

    if [ "$have" = "$want" ]; then
        ok "$key = $want"
    elif [ "$INSTALL" = "false" ]; then
        skip "$key (want '$want', have '${have:-<unset>}')"
    else
        git config --global "$key" "$want"
        installed "$key = $want"
    fi
}

_check_or_set "user.name" "$GIT_NAME"
_check_or_set "user.email" "$GIT_EMAIL"
_check_or_set "pull.rebase" "false"

if [[ "$(uname -s)" == "Darwin" ]]; then
    _check_or_set "credential.helper" "osxkeychain"
else
    _check_or_set "credential.helper" "store"
fi

# Global ignore: git's default path (no core.excludesfile needed). Lines are
# appended when missing; lines put there by other tools are kept.
GIT_IGNORE_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/git/ignore"
GIT_IGNORE_LINES=(".DS_Store")

for line in "${GIT_IGNORE_LINES[@]}"; do
    if [ -f "$GIT_IGNORE_FILE" ] && grep -qxF "$line" "$GIT_IGNORE_FILE"; then
        ok "global gitignore: $line"
    elif [ "$INSTALL" = "false" ]; then
        skip "global gitignore: $line (missing from $GIT_IGNORE_FILE)"
    else
        mkdir -p "$(dirname "$GIT_IGNORE_FILE")"
        printf '%s\n' "$line" >> "$GIT_IGNORE_FILE"
        installed "global gitignore: $line"
    fi
done
