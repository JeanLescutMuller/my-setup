# `AGENTS.md`

## Every session loads it, so keep it small

Every session that works in a folder is given **every `AGENTS.md` on the path from the repo root down to that folder, parents first**, before it does anything. A word in `AGENTS.md` is paid for on every turn of every session, whether the task needs it or not. A word in `doc/` is paid for only when an agent decides to open that file.

```
editing src/pipeline/ingest/ loads, in order:
    ./AGENTS.md                       project-wide rules
    ./src/AGENTS.md                   all source code
    ./src/pipeline/ingest/AGENTS.md   this folder
```

| Budget | |
|---|---|
| one `AGENTS.md`, not counting its `## Vocabulary` section | aim ≤ 400 words, never above ~600 |
| the whole chain loaded in the deepest folder | ≤ ~1,900 words |

**Over budget?** Find the longest passage that is *explaining* rather than *instructing* and move it to `doc/`. No rule needs to be dropped.

**AGENTS.md or a skill?** A rule that most sessions in that folder need goes in `AGENTS.md`. A rule only some tasks need (a code snippet, a procedure, one tool's usage) becomes a skill: only its one-line description is loaded at startup, and that line must say *when* to use it ("Use when…"), with the words the user says. The machine-wide rules (`~/.claude/CLAUDE.md`, source `my-context/init/AGENTS_LOCAL.md`) follow the same rule. Never add a "load skill X" line or a summary of the skill to any `AGENTS.md`: the description is the skill's only trigger, and the section it replaces is deleted.

## What it holds

- **Rules, not evidence.** A rule is one or two imperative sentences plus a pointer (`→ doc/pnl.md §3`). The table, measurement or worked example proving it lives in `doc/`.
- **Never repeat a parent.** Put each rule once, at the level that owns it; a pointer to a parent's rule is fine, a copy drifts and then contradicts. The chain is path-based: if a folder's work routinely touches a sibling (a shared library), say so and link there.
- **Self-sufficient.** An agent reading only the `AGENTS.md` chain, and never a README, must have every rule it needs.
- **Contents, in order:** the purpose in one line, in the user's words · the rules and traps · what must not be touched · the commands to test and deploy · the vocabulary table (below) · a "where to look" table pointing at `doc/` and the design files.
- Once code exists, rules derived from `DESIGN.md` go here as one-line rules pointing back at the design section that explains them.

## The vocabulary lives here, and only here

Agents using the wrong word with the user is a recurring, costly failure, so the project's words are in the one file every session is guaranteed to read. There is no separate vocabulary file.

| Word | Means | Never say |
|---|---|---|
| **window** | one 5-hour quota meter | envelope, interval, bucket |

- **One concept, one word**, in every file and in conversation. Use the user's own words for what they named; do not coin a term when an ordinary phrase works.
- **The "never say" column** holds the synonyms an agent drifts to and the words removed by past renames. That is what stops the drift.
- **A new word is added here first**, with the user's agreement, before it appears anywhere else. A rename is done everywhere in one commit, lower level first, with the old word moved to "never say".
- **One line per word.** A measured quantity names its unit (`week_used_pct`: percent of the 7-day meter).
- **At the level that owns it**: project-wide words in the root `AGENTS.md`, a stage's own words in that stage's. Never repeated in a child, and no copy in `REQUIREMENTS.md` or `DESIGN.md`: they point here.
- **The `## Vocabulary` section does not count toward the word budget** (`check_docs.sh` skips it), so budget pressure never pushes a word out. It is still kept tight: words used with the user and across files, not every column name. A data format's field-by-field description (a CSV's columns, a JSON's keys) is a `doc/` file about that format.

Template: [`../templates/AGENTS.template.md`](../templates/AGENTS.template.md).

## No `CLAUDE.md`

Codex and Claude Code (v2.1.277 and later) both read `AGENTS.md` directly, at every level, so a project has **no `CLAUDE.md`, not even a symlink**. By default, one `CLAUDE.md` anywhere on the path makes Claude ignore every `AGENTS.md` (https://code.claude.com/docs/en/memory#agents-md); this machine's setting (Project instructions = `claude-md-and-agents-md`, set by my-setup) softens that, but the rule stays: no `CLAUDE.md`.

If a real `CLAUDE.md` exists, merge its content into `AGENTS.md`, then `git rm CLAUDE.md`. The only `CLAUDE.md` on the machine is the global `~/.claude/CLAUDE.md` (→ `~/AGENTS.md`).
