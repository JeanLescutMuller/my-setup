#!/usr/bin/env python3
"""The Drive folder Personal/my-context/ through the Drive API (gws), for context-sync (files/context_sync.sh).

  newer COPY SINCE  bring COPY (a copy of the local snapshot) up to date with the files that are newer in the Drive (or new
                 there), Google Docs/Sheets/Slides and from_repos/ left out; never deletes. Used when macOS forbids reading
                 ~/gdrive (a LaunchAgent's bash gets "Operation not permitted" on ~/Library/CloudStorage, tested 2026-10-19).
                 Only newer files: the API lags behind ~/gdrive until Drive for Desktop has uploaded a local edit, so a full
                 download would bring back the version before it (seen 2026-10-19). A file missing from COPY is taken only
                 if the Drive changed it after SINCE (epoch of the last copy through ~/gdrive): else it is one deleted or
                 moved here and not uploaded yet. A deletion reaches the agents at the next context-sync that reads ~/gdrive. Exit 1 if anything fails (COPY is then thrown away).
  repo-copies    copy the other repos' files that Gemini needs (REPO_FILES) to from_repos/<repo>/<path> in the folder:
                 one way, repo -> Drive, a header saying where to edit; uploaded only when the content changed.
                 Gemini cannot read GitHub (user, 2026-10-19: "Gemini needs to know those skills").

Deployed by modules/my_context.sh to ~/opt/my-setup/context/context-drive. Reads: the Drive (gws, logged in on the Mac),
~/dev/<repo>/<path>. Writes: TARGET; the Drive Personal/my-context/from_repos/.
"""
import hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime
from pathlib import Path

FOLDER = "application/vnd.google-apps.folder"
COPIES = "from_repos"
REPO_FILES = [("tasks", "skills/tasks/SKILL.md"),
              ("job-applications", "skills/application-writing/SKILL.md"),
              ("job-applications", "skills/application-writing/references/rules.md"),     # SKILL.md: "read it first"
              ("job-applications", "skills/application-writing/references/html-cv.md"),
              ("learning-german", "README.md")]
HEADER = ("> Copy of `{path}` in the GitHub repo `JeanLescutMuller/{repo}`, for Gemini, made by context-sync (my-setup). "
          "Never edit it here: edit the repo; the next sync replaces this copy.\n\n")


def gws(*args, params=None, body=None, upload=None, output=None, cwd=None):
    cmd = ["gws", "drive", "files", *args]
    if params: cmd += ["--params", json.dumps(params)]
    if body: cmd += ["--json", json.dumps(body)]
    if upload: cmd += ["--upload", upload, "--upload-content-type", "text/markdown"]   # gws uploads only below its cwd
    if output: cmd += ["-o", output]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
    if out.returncode:
        sys.exit(f"gws failed ({' '.join(args)}): {(out.stderr or out.stdout).strip()[-300:]}")
    text = out.stdout[out.stdout.find("{"):] if "{" in out.stdout else ""
    return json.loads(text) if text else {}


def children(folder_id):
    files, page = [], None
    while True:
        res = gws("list", params={"q": f"'{folder_id}' in parents and trashed = false", "pageSize": 1000,
                                  "fields": "nextPageToken,files(id,name,mimeType,md5Checksum,modifiedTime)", **({"pageToken": page} if page else {})})
        files += res.get("files", [])
        page = res.get("nextPageToken")
        if not page:
            return files


def subfolder(parent_id, name, create=False):
    hits = [f for f in children(parent_id) if f["name"] == name and f["mimeType"] == FOLDER]
    if len(hits) == 1:
        return hits[0]["id"]
    if not hits and create:
        return gws("create", body={"name": name, "mimeType": FOLDER, "parents": [parent_id]})["id"]
    sys.exit(f"Drive: {len(hits)} folders named {name!r} (expected 1)")


def my_context():
    return subfolder(subfolder("root", "Personal"), "my-context")


def newer(folder_id, copy, since, top=True):
    """Downloads into COPY each Drive file newer than COPY's (by more than 60 s, the mount's rounding), with the Drive's time."""
    n = 0
    for f in children(folder_id):
        if f["mimeType"] == FOLDER:
            if not (top and f["name"] == COPIES):
                n += newer(f["id"], copy / f["name"], since, top=False)
        elif not f["mimeType"].startswith("application/vnd.google-apps."):
            drive_ts = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00")).timestamp()
            local = copy / f["name"]
            if drive_ts <= (local.stat().st_mtime if local.exists() else since) + 60:
                continue
            copy.mkdir(parents=True, exist_ok=True)
            if local.exists():
                local.chmod(0o644)
            gws("get", params={"fileId": f["id"], "alt": "media"}, output=f["name"], cwd=copy)
            os.utime(local, (drive_ts, drive_ts))
            print(f"newer in the Drive: {f['name']}")
            n += 1
    return n


def repo_copies():
    root = my_context()
    for repo, path in REPO_FILES:
        src = Path.home() / "dev" / repo / path
        if not src.exists():
            print(f"WARN: {src} missing: its copy left as it is")
            continue
        body = HEADER.format(repo=repo, path=path) + src.read_text()
        folder = subfolder(root, COPIES, create=True)
        for part in [repo, *Path(path).parent.parts]:
            folder = subfolder(folder, part, create=True)
        name = Path(path).name
        old = [f for f in children(folder) if f["name"] == name]
        if old and old[0].get("md5Checksum") == hashlib.md5(body.encode()).hexdigest():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / name).write_text(body)
            if old:
                gws("update", params={"fileId": old[0]["id"]}, upload=name, cwd=tmp)
            else:
                gws("create", body={"name": name, "parents": [folder]}, upload=name, cwd=tmp)
        print(f"repo copy: {COPIES}/{repo}/{path}")


def main():
    if sys.argv[1:2] == ["newer"] and len(sys.argv) == 4 and Path(sys.argv[2]).is_dir():
        print(f"{newer(my_context(), Path(sys.argv[2]), float(sys.argv[3]))} files newer in the Drive")
    elif sys.argv[1:] == ["repo-copies"]:
        repo_copies()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
