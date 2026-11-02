#!/bin/bash
# configure_shellrc.sh - generates the my-setup managed block content
# for one shell. Organized by topic (PATH, ls/ll, history, prompt), not by
# shell - branches internally only where bash/zsh syntax genuinely differs.
# Usage: configure_shellrc.sh zsh|bash   (output -> the managed block body)
set -euo pipefail
TARGET_SHELL="$1"   # "zsh" or "bash"

# --- Greeting ---
echo "echo 'Loading ~/.${TARGET_SHELL}rc ...'"

# --- PATH ---
cat << 'EOF'
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
EOF

# --- ls / ll: colorized, ll always shows hidden files with human-readable
# sizes, regardless of which of these three cases applies. Same on every
# shell, so no branching here. ---
cat << 'EOF'

if command -v gls >/dev/null 2>&1 && command -v gdircolors >/dev/null 2>&1; then
    # GNU coreutils via Homebrew (macOS)
    if [[ -r "$HOME/.dircolors" ]]; then
        eval "$(gdircolors -b "$HOME/.dircolors")"
    else
        eval "$(gdircolors -b)"
    fi
    alias ls='gls --color=auto'
    alias ll='gls --color=auto -lAh'
elif command -v dircolors >/dev/null 2>&1; then
    # Native GNU coreutils (Linux)
    if [[ -r "$HOME/.dircolors" ]]; then
        eval "$(dircolors -b "$HOME/.dircolors")"
    else
        eval "$(dircolors -b)"
    fi
    alias ls='ls --color=auto'
    alias ll='ls --color=auto -lAh'
else
    # BSD ls fallback (macOS without Homebrew coreutils)
    export CLICOLOR=1
    export LSCOLORS='Exfxcxdxbxegedabagacad'
    alias ls='ls -G'
    alias ll='ls -lAhG'
fi
EOF

# --- History: large, deduplicated, timestamped everywhere. Syntax differs
# per shell (setopt vs. HISTCONTROL/shopt), so this is the first spot that
# actually branches. ---
if [ "$TARGET_SHELL" = "zsh" ]; then
    cat << 'EOF'

export HISTFILE="$HOME/.zsh_history"
export HISTSIZE=100000
export SAVEHIST=100000
setopt EXTENDED_HISTORY       # timestamps + duration
setopt INC_APPEND_HISTORY     # write immediately
setopt SHARE_HISTORY          # across terminals
setopt HIST_IGNORE_DUPS
setopt HIST_REDUCE_BLANKS
setopt HIST_VERIFY
EOF
elif [ "$TARGET_SHELL" = "bash" ]; then
    cat << 'EOF'

export HISTCONTROL=ignoredups:erasedups
export HISTSIZE=100000
export HISTFILESIZE=100000
export HISTTIMEFORMAT="%Y-%m-%d %T "
shopt -s histappend
# bash has no built-in cross-terminal live sharing like zsh's SHARE_HISTORY,
# so PROMPT_COMMAND writes after every command instead.
export PROMPT_COMMAND="history -a; ${PROMPT_COMMAND:-}"
EOF
fi

# --- Prompt: italic user (red if root, else cyan - whoami-based, no
# marker file needed), hashed host color, bold yellow workdir. Same color
# scheme on both shells, different escape syntax.
#
# Host color comes from the shared get_host_color binary (files/get_host_
# color.sh, deployed to ~/.local/bin by bootstrap.sh's "own binaries" step)
# instead of duplicating its SHA-256 -> mod 14 -> HOST_PALETTE algorithm
# here - one source of truth shared with the statusline script. Exported
# (not local) so other programs under this shell, the statusline in
# particular, can reuse the already-computed value instead of re-running
# the hash themselves. ---
if [ "$TARGET_SHELL" = "zsh" ]; then
    cat << 'EOF'

export HOST_COLOR="$(get_host_color)"
if [ "$(whoami)" = "root" ]; then
    _bh_user_color="red"
else
    _bh_user_color="cyan"
fi
autoload -U colors && colors
PS1="%{$fg[$_bh_user_color]%}%n%{$reset_color%}@%F{$HOST_COLOR}%m %{$fg[yellow]%}%~ %{$reset_color%}%% "
unset _bh_user_color
EOF
elif [ "$TARGET_SHELL" = "bash" ]; then
    cat << 'EOF'

export HOST_COLOR="$(get_host_color)"
if [ "$(whoami)" = "root" ]; then
    _bh_user_color="31"
else
    _bh_user_color="36"
fi
export PS1="\[\033[3;${_bh_user_color}m\]\u\[\033[m\]@\[\033[38;5;${HOST_COLOR}m\]\h:\[\033[1;33m\]\w\[\033[m\]\$ "
unset _bh_user_color
EOF
fi

# --- tm (files/tm.sh): Tab completes the folder names in ~/dev, or a path
# once the word has a "/" or starts with ".". zsh: compdef when compinit
# is loaded (on the Mac, nvm's bash_completion loads it above this block),
# else the old compctl, which needs nothing. ---
if [ "$TARGET_SHELL" = "zsh" ]; then
    cat << 'EOF'

_tm() {
    if [[ $PREFIX == */* || $PREFIX == .* ]]; then _path_files -/
    else _path_files -/ -W "$HOME/dev"; fi
}
if (( $+functions[compdef] )); then compdef _tm tm; else compctl -/ -W "$HOME/dev" tm; fi
EOF
elif [ "$TARGET_SHELL" = "bash" ]; then
    cat << 'EOF'

_tm() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $cur == */* || $cur == .* ]]; then COMPREPLY=($(compgen -d -- "$cur"))
    else COMPREPLY=($(cd "$HOME/dev" 2>/dev/null && compgen -d -- "$cur")); fi
}
complete -o filenames -F _tm tm
EOF
fi
