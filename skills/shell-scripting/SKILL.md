---
name: shell-scripting
description: Personal bash/shell scripting conventions. Use when writing or editing a .sh script, especially an install/bootstrap-style script, for this user.
---

## `install.sh` scripts

Every personal tool's `install.sh` must be:
- **Idempotent** — safe to blind re-run any time, including on a fresh machine.
- **Self-migrating** — if it detects a stale prior layout (old paths, old naming), move it to the current layout automatically rather than requiring manual cleanup.
- **Skills deployed read-only** — each folder `skills/<name>/` of the repo is copied to `~/opt/<repo>/skills/<name>/`, made read-only (`chmod -R a-w`), and linked from `~/.claude/skills/<name>` and `~/.agents/skills/<name>`; a skill removed from `skills/` loses its copy and links. `uninstall.sh` removes the links that point into `~/opt/<repo>/skills/`, then the copies. A real folder already at the link path is replaced only if identical (ignoring `*.bak`); otherwise it is kept, with a warning. Working model: the skills block of `~/dev/my-context/install.sh`.

## Bash habits

- Prefer `printf -v` over `eval` for dynamic variable assignment.
- `jq`'s `//` operator treats `false` (and `null`, `0`, `""`) as falsy — when checking whether a key is merely *present*, use `has("key")` instead of `.key // default`.
