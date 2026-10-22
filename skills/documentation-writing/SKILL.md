---
name: documentation-writing
description: Personal documentation conventions for every project on this machine — one README for humans (README.html preferred, or README.md; never both), AGENTS.md for agents (Claude and Codex both read it; no CLAUDE.md), doc/ companion files, the project vocabulary (always in AGENTS.md), the design-stage files (CONSIDERATIONS.md, REQUIREMENTS.md, DESIGN.md), and Markdown formatting (one paragraph = one line). Use when writing or editing any .md file or HTML README, when designing or scoping a new project, when setting up or reorganising a project's documentation.
---

# Documentation writing

This file holds only what every documentation task needs. Tasks, open work and to-do lists are not documentation: they belong to skill `tasks`, never to a file described here. **Read a reference file only when your task matches its row below** — the rest is not for you.

## Always: how to write

- **One paragraph, one physical line — never hard-wrap mid-sentence**, not even to stay under 80 columns: some Markdown viewers render every newline as a line break, so a wrapped paragraph appears chopped. No trailing double-space breaks either; a real break is a blank line. Headings, table rows, list items (one line each), fenced code and horizontal rules keep their own lines. Before finishing, join any paragraph that spans several source lines.
- **Show, don't narrate.** A comparison or set of values is a table; a sequence or hierarchy is a diagram; prose is the fallback. Explain with a worked numeric example.
- **Mermaid only in a README**; everywhere else ASCII/UTF-8 box-drawing, because agents read those files as plain text.
- **Use the project's words exactly as defined in the `## Vocabulary` table of `AGENTS.md`** — in files and in what you say to the user. Never a synonym, never a word from its "never say" column, never a newly coined term. A new word is added to that table first, with the user's agreement. Renaming a concept is a bug.
- **Cite the primary source** (the code file, the platform's own docs) by its full repo path. **State what was verified and how** ("verified 2026-10-07 against `7f1479d`"); dates are absolute.

## The files, and which reference to read

| File | For | In one line | Read when your task is… |
|---|---|---|---|
| `AGENTS.md` (never a `CLAUDE.md`) | agents | rules and the project vocabulary — **loaded by every session**, so kept small | writing or editing one, or adding a word → [`references/agents_md.md`](references/agents_md.md) |
| `README.html` (preferred) or `README.md`, **never both** | humans | diagrams of what exists and what calls what; no rules; may repeat what `AGENTS.md` says | writing or editing one → [`references/readme.md`](references/readme.md) |
| `CONSIDERATIONS.md` → `REQUIREMENTS.md` → `DESIGN.md` | both | what might matter → what the user gets → what we build and how | designing or scoping a project → [`references/design_files.md`](references/design_files.md) |
| `doc/` | both | companion files for the production code | setting up a project's docs, adding a `doc/` file, moving or renaming files → [`references/project_layout.md`](references/project_layout.md) |

Choosing a Mermaid diagram type → [`references/mermaid_playground.md`](references/mermaid_playground.md) (what the viewers on this machine actually render). A file from scratch → copy it from [`templates/`](templates/) (`<NAME>.template.md`, `README.template.html`).

## Before finishing a structural change

After creating, moving or renaming documentation files, run the checker and fix every `FAIL`:

```bash
bash ~/.claude/skills/documentation-writing/check_docs.sh <project-root>
```
