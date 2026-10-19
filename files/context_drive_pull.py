#!/usr/bin/env python3
"""Download the Drive folder Personal/my-context/ through the Drive API (gws), for context-sync when macOS forbids reading
~/gdrive: a LaunchAgent's bash gets "Operation not permitted" on ~/Library/CloudStorage (tested 2026-10-19).

Deployed by modules/my_context.sh to ~/opt/my-setup/context/context-drive-pull; run by context-sync (files/context_sync.sh).
Reads:  the Drive (gws, logged in on the Mac): every file under Personal/my-context/ that is not a Google Doc/Sheet/Slide
Writes: TARGET/<same path>, a new folder (it must not exist)
Exit:   0 done; 1 the folder or a file could not be read (TARGET then incomplete: context-sync throws it away)

Usage: context-drive-pull TARGET
"""
import json, subprocess, sys
from pathlib import Path

FOLDER = "application/vnd.google-apps.folder"


def gws(*args, params, cwd=None):
    out = subprocess.run(["gws", "drive", "files", *args, "--params", json.dumps(params)],
                         capture_output=True, text=True, cwd=cwd, timeout=120)
    text = out.stdout[out.stdout.find("{"):] if "{" in out.stdout else ""
    if out.returncode:
        sys.exit(f"gws failed ({' '.join(args)}): {(out.stderr or out.stdout).strip()[-300:]}")
    return json.loads(text) if text else {}


def children(folder_id):
    files, page = [], None
    while True:
        res = gws("list", params={"q": f"'{folder_id}' in parents and trashed = false", "pageSize": 1000,
                                  "fields": "nextPageToken,files(id,name,mimeType)", **({"pageToken": page} if page else {})})
        files += res.get("files", [])
        page = res.get("nextPageToken")
        if not page:
            return files


def find(parent_id, name):
    hits = [f for f in children(parent_id) if f["name"] == name and f["mimeType"] == FOLDER]
    if len(hits) != 1:
        sys.exit(f"Drive: {len(hits)} folders named {name!r} (expected 1)")
    return hits[0]["id"]


def pull(folder_id, target):
    for f in children(folder_id):
        if f["mimeType"] == FOLDER:
            pull(f["id"], target / f["name"])
        elif not f["mimeType"].startswith("application/vnd.google-apps."):
            target.mkdir(parents=True, exist_ok=True)   # only folders holding a file, as rsync --prune-empty-dirs
            subprocess.run(["gws", "drive", "files", "get", "--params", json.dumps({"fileId": f["id"], "alt": "media"}),
                            "-o", f["name"]], cwd=target, capture_output=True, text=True, timeout=120, check=True)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    target = Path(sys.argv[1])
    if target.exists():
        sys.exit(f"{target} exists")
    pull(find(find("root", "Personal"), "my-context"), target)


if __name__ == "__main__":
    main()
