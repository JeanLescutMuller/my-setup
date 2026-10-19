#!/bin/bash
# Ensures ~/dev, ~/opt, ~/.local/bin exist.
# ~/opt here always means the user-level dir - see files/AGENTS_LOCAL.md for the
# distinction from the root-owned system /opt on Linux.
step "directory layout"

DIRS=("$HOME/dev" "$HOME/opt" "$HOME/.local/bin")

for d in "${DIRS[@]}"; do
    if [ -d "$d" ]; then
        ok "$d"
    elif [ "$INSTALL" = "false" ]; then
        skip "$d"
    else
        mkdir -p "$d"
        installed "$d"
    fi
done

# ~/gdrive -> My Drive, as mounted by the Google Drive app (stream mode).
# macOS fixes the mount at ~/Library/CloudStorage/GoogleDrive-<email>/; the
# link is made only when exactly one account is signed in.
if [ "$(uname)" = "Darwin" ]; then
    link="$HOME/gdrive"
    mounts=("$HOME"/Library/CloudStorage/GoogleDrive-*/"My Drive")
    if [ ${#mounts[@]} -ne 1 ] || [ ! -d "${mounts[0]}" ]; then
        warn "$link (Google Drive app not signed in, or more than one account)"
    elif [ -L "$link" ] && [ "$(readlink "$link")" = "${mounts[0]}" ]; then
        ok "$link"
    elif [ -e "$link" ] && [ ! -L "$link" ]; then
        warn "$link is a real file or folder - preserving it, not linked"
    elif [ "$INSTALL" = "false" ]; then
        skip "$link"
    else
        ln -sfn "${mounts[0]}" "$link"
        installed "$link -> ${mounts[0]}"
    fi
fi
