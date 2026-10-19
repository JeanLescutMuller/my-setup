#!/bin/bash
# context-history: git on the history of the Drive folder Personal/my-context/, kept by context-sync (files/context_sync.sh).
# Deployed by modules/my_context.sh to ~/opt/my-setup/context/context-history (on the PATH). Examples:
#   context-history log --format='%h %ad %s%n  %b' --date=short -- skills/      who changed a skill, when
#   context-history show <commit>:facts/health.md > ~/gdrive/Personal/my-context/facts/health.md   a rollback, then context-sync -m "…"
exec git --git-dir="$HOME/opt/my-setup/context/history.git" --work-tree="$HOME/opt/my-setup/context/snapshot" "$@"
