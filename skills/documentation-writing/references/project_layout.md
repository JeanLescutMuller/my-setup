# Project layout — which files, in which folders

## The file set

| File | Reader | Loaded |
|---|---|---|
| `README.html` or `README.md`, never both | a human only | when a person opens the folder |
| `AGENTS.md` | an agent only | **automatically, by every session** |
| `doc/` | both | on demand |
| `lib/` | — | code scoped to this folder |

The project root always carries `README` and `AGENTS.md` (never a `CLAUDE.md`). A subfolder gets its own set only when it is a **scope with rules of its own** — a stage, a shared library, a deployable unit — never just because it is a folder. During the design stage, the root (or `design/`) also holds `CONSIDERATIONS.md`, `REQUIREMENTS.md`, `DESIGN.md` → [`design_files.md`](design_files.md).

Setting up a new project: copy each file from [`../templates/`](../templates/), drop the `.template` part of the name.

## `doc/` — companion files for the production code

Everything an agent or a human may need about how the code works that is too long or too rarely needed for `AGENTS.md`: algorithms, data formats, endpoint notes, measurements, the evidence behind a rule.

- **One subject per file**, named after the subject (`pnl_computation.md`, not `notes2.md`).
- **Beside the code it describes.** The test: if you can only know it by looking in one folder, it belongs in that folder's `doc/`. Anything broader moves up a level.
- **No `README.md` inside a `doc/` folder.** Its index is the parent folder's README diagram, plus a pointer in the parent `AGENTS.md` where the choice between two files is not obvious.
- **No size budget**: it costs nothing until opened.
- **Work artifacts are not code documentation.** An audit, a handoff note or migration scaffolding is about a piece of work and is deleted when the work ends; keep it out of the code's `doc/` folders.

## After moving or renaming files

- Path citations and links go stale silently. Run `check_docs.sh` (it checks relative Markdown links), and `grep` for the old name in backticked paths, which it does not check.
- Check whether a README diagram names the moved file.
- Line-number citations (`framework.py:120`) shift after any insertion: re-locate the cited content rather than assuming an offset.

## What `check_docs.sh` checks

| FAIL | WARN |
|---|---|
| a real `CLAUDE.md` (merge it into `AGENTS.md`) | `AGENTS.md` over 400 words, or its loaded chain over 1,900 (`## Vocabulary` sections are not counted) |
| `AGENTS.md` over 600 words | no README beside an `AGENTS.md`; a `CLAUDE.md` symlink (remove it); a root `AGENTS.md` with no `## Vocabulary` table |
| a `README.html` and a `README.md` in the same folder (fold the Markdown into the page, delete it) | a README line that looks like a rule or a tunable number |
| a `README.md` inside a `doc/` folder | a task list in any file (tasks: skill `task-management`) |
| a broken relative Markdown link | |

In a git repo it lists files with `git ls-files`, so `.gitignore`d data folders are skipped.
