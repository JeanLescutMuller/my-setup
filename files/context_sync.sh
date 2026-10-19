#!/bin/bash
# context-sync: makes what every agent loads from the Drive folder Personal/my-context/ (the only source of the user's
# facts, shared rules and life skills, since 2026-10-19), and keeps its history. Deployed by modules/my_context.sh to
# ~/opt/my-setup/context/context-sync (on the PATH); run by agents right after an edit there, and every 15 min by the
# job my-setup.context-sync (files/context-sync.entrypoint.sh).
# Reads:  ~/gdrive/Personal/my-context/ (Google Drive for Desktop; else the Drive API through context-drive-pull),
#         ~/opt/my-setup/context/AGENTS_LOCAL.md
# Writes: ~/opt/my-setup/context/snapshot/  read-only copy of the Drive folder: what agents load (kept when the Drive is unreachable)
#         ~/opt/my-setup/context/AGENTS.md  AGENTS_LOCAL.md + snapshot/AGENTS_SHARED.md, read-only (~/.claude/CLAUDE.md, ~/.codex/AGENTS.md)
#         ~/.claude/skills/<name>, ~/.agents/skills/<name> -> snapshot/skills/<name>/
#         ~/opt/my-setup/context/history.git  a commit per change (its work tree: snapshot/), pushed to GitHub my-context
#         the VM, from the Mac: snapshot/, then context-sync there (it has no Drive: it builds from that copy)
# Usage:  context-sync [-m "what changed and why"] [--agent "claude-code (claude-opus-5-5)"]
#         without -m, a change found is committed as "unattributed".
# Exit:   0 done; 3 the Drive folder unreachable: the last copy kept and loaded; 1 an error (AGENTS.md left as it was).
set -uo pipefail

CTX="$HOME/opt/my-setup/context"
SRC="${CONTEXT_SRC:-$HOME/gdrive/Personal/my-context}"
SNAP="$CTX/snapshot"
VM=H-Frank-1
MSG="" AGENT=""
while [ $# -gt 0 ]; do
    case "$1" in
        -m) MSG="${2:-}"; shift 2 ;;
        --agent) AGENT="${2:-}"; shift 2 ;;
        *) echo "usage: context-sync [-m MESSAGE] [--agent AGENT]" >&2; exit 1 ;;
    esac
done
[ -s "$CTX/AGENTS_LOCAL.md" ] || { echo "ERROR: $CTX/AGENTS_LOCAL.md missing: INSTALL=true bash bootstrap.sh my_context (my-setup)" >&2; exit 1; }

# This machine's name: skill "machine-name" (copy it identically)
m=${JR_MACHINE_NAME:-$(if [ "$(uname)" = Darwin ]; then scutil --get HostName; else cat /etc/hostname; fi 2>/dev/null)} || :
m=${m%%.*}; [[ $m =~ ^[A-Za-z0-9-]+$ ]] || { echo "no machine name: macOS sudo scutil --set HostName <name>; Linux sudo hostnamectl set-hostname <name>" >&2; exit 1; }

# "$@" with a time limit of $1 seconds: a stopped Drive app must not hang an agent (SIGALRM survives exec).
_limit() { perl -e 'alarm shift; exec @ARGV or exit 127' "$@"; }

# The Drive folder -> $SNAP.new: through ~/gdrive, else through the Drive API (gws): macOS forbids ~/Library/CloudStorage
# to a scheduled job's bash ("Operation not permitted", 2026-10-19).
_copy_from_drive() {
    rm -rf "$SNAP.new"
    if _limit 30 test -s "$SRC/AGENTS_SHARED.md" \
        && _limit 300 rsync -rlt --prune-empty-dirs --exclude='.DS_Store' --exclude='*.gdoc' --exclude='*.gsheet' --exclude='*.gslides' \
               --exclude='.tmp*' --exclude='Icon?' "$SRC/" "$SNAP.new/" 2>/dev/null; then
        return 0
    fi
    rm -rf "$SNAP.new"
    [ -z "${CONTEXT_SRC:-}" ] && [ -x "$CTX/context-drive-pull" ] && _limit 300 "$CTX/context-drive-pull" "$SNAP.new" >/dev/null \
        && echo "~/gdrive not readable here: read through the Drive API"
}

# --- 1. The Drive folder -> snapshot/ (a new copy, swapped in whole; files read-only)
rc=0
if [ -z "${CONTEXT_SRC:-}" ] && [ ! -e "$HOME/gdrive" ]; then
    # No Drive on this machine (the VM): snapshot/ is what the Mac sent.
    [ -d "$SNAP" ] && find "$SNAP" -type f -perm -u+w -exec chmod a-w {} +
    echo "no Drive here: agents load the copy sent by the Mac"
elif _copy_from_drive && [ -s "$SNAP.new/AGENTS_SHARED.md" ]; then
    find "$SNAP.new" -type f -exec chmod a-w {} +
    if [ -d "$SNAP" ]; then rm -rf "$SNAP.old" && mv "$SNAP" "$SNAP.old"; fi
    mv "$SNAP.new" "$SNAP" && rm -rf "$SNAP.old"
    echo "copied $(find "$SNAP" -type f | wc -l | tr -d ' ') files from the Drive"
else
    rm -rf "$SNAP.new"
    echo "WARN: the Drive folder $SRC is unreachable: agents keep the last copy"
    rc=3
fi

# --- 2. AGENTS.md: this machine's rules, then the shared ones (rewritten only when it changes)
{
    cat "$CTX/AGENTS_LOCAL.md"
    if [ -s "$SNAP/AGENTS_SHARED.md" ]; then
        printf '\n---\n\n<!-- Below: AGENTS_SHARED.md, the local copy of the Drive folder Personal/my-context/ made by context-sync. Edit it in the Drive, never here. -->\n\n'
        cat "$SNAP/AGENTS_SHARED.md"
    fi
} > "$CTX/AGENTS.md.new" || { echo "ERROR: could not write $CTX/AGENTS.md.new" >&2; exit 1; }
if cmp -s "$CTX/AGENTS.md.new" "$CTX/AGENTS.md"; then
    rm -f "$CTX/AGENTS.md.new"
else
    chmod a-w "$CTX/AGENTS.md.new" && mv -f "$CTX/AGENTS.md.new" "$CTX/AGENTS.md" && echo "rebuilt $CTX/AGENTS.md"
fi
[ -s "$SNAP/AGENTS_SHARED.md" ] || echo "WARN: no AGENTS_SHARED.md yet: agents load AGENTS_LOCAL.md only"

# --- 3. The life skills: links into snapshot/skills/ (never over another project's skill)
for home in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
    mkdir -p "$home"
    for link in "$home"/*; do
        [ -L "$link" ] || continue
        case "$(readlink "$link")" in "$SNAP/skills/"*) [ -e "$link" ] || { rm "$link" && echo "removed $link (skill gone)"; } ;; esac
    done
    for dir in "$SNAP"/skills/*/; do
        [ -d "$dir" ] || continue
        dir="${dir%/}"; link="$home/$(basename "$dir")"
        if [ -L "$link" ]; then
            target=$(readlink "$link")
            [ "$target" = "$dir" ] && continue
            case "$target" in "$HOME/opt/my-context/"*) ;; *) echo "WARN: $link points to $target (another project's skill): not linked"; continue ;; esac
        elif [ -e "$link" ]; then
            echo "WARN: $link is a real file or folder: not linked"; continue
        fi
        ln -sfn "$dir" "$link" && echo "linked $link"
    done
done

# --- 4. History (where history.git exists: the Mac): a commit when snapshot/ changed, then a push
if [ -d "$CTX/history.git" ] && [ -d "$SNAP" ]; then
    export GIT_DIR="$CTX/history.git" GIT_WORK_TREE="$SNAP"
    git add -A
    if git diff --cached --quiet; then
        [ -n "$MSG" ] && echo "history: nothing changed"
    else
        session=${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-none}}
        if [ -z "$AGENT" ]; then
            if [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then AGENT=claude-code
            elif [ -n "${CODEX_THREAD_ID:-}" ]; then AGENT=codex
            else AGENT="none: found by context-sync"; fi
        fi
        git commit -q -m "${MSG:-unattributed change, found by context-sync}" -m "Agent: $AGENT
Machine: $m
Session: $session" && echo "history: $(git log -1 --format='%h %s')"
    fi
    _limit 60 git push -q origin HEAD:main 2>/dev/null || echo "WARN: history not pushed to GitHub (it will be at the next run)"
    unset GIT_DIR GIT_WORK_TREE
fi

# --- 5. The VM, from the Mac: the same copy, then its own AGENTS.md
if [ "$m" = chan-lescut-macbook-pro ] && [ -d "$SNAP" ] && [ -z "${CONTEXT_NO_VM:-}" ]; then
    if _limit 120 rsync -rlt --delete -e 'ssh -o BatchMode=yes -o ConnectTimeout=10' "$SNAP/" "$VM:opt/my-setup/context/snapshot/" >/dev/null 2>&1 \
        && _limit 60 ssh -o BatchMode=yes -o ConnectTimeout=10 "$VM" 'bash ~/opt/my-setup/context/context-sync' >/dev/null 2>&1; then
        echo "VM: updated"
    else
        echo "WARN: VM not updated (offline, or my-setup's my_context module not installed there)"
    fi
fi
exit $rc
