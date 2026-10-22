# Design-stage files in detail

`CONSIDERATIONS.md`, `REQUIREMENTS.md` and `DESIGN.md` are written while a project is designed or scoped, before (and while) it is built. Each answers one question; the danger is letting one file answer another's question.

```
              abstract ◀──────────────────────────────────────▶ concrete
CONSIDERATIONS.md           REQUIREMENTS.md             DESIGN.md
"something to keep          "what the user gets"        "what we build, how,
 in mind, investigate"                                   and why this way"
        │                          │                           │
        └── an answer found ──▶ becomes a requirement ──▶ or a design choice
            (marked answered,      (R<n>)                   (§<n>, with its reason)
             with a pointer)
```

## Where they live

At the project root while there is one of each. When `DESIGN.md` splits per stage, move them into `design/`: `design/DESIGN.md` for the whole, `design/<NN>_<stage>/DESIGN.md` per stage, with a per-stage `CONSIDERATIONS.md` beside it where needed. Templates: `../templates/{CONSIDERATIONS,REQUIREMENTS,DESIGN}.template.md`.

## `CONSIDERATIONS.md`

**Test: could we act on it today?** If not — because we do not yet know what it means for the user or for what we would build — it is a consideration.

- Abstract, unclear points: things to investigate, problems that might arise, risks, unknowns, fragile assumptions, interactions with other projects.
- Grouped by theme in numbered sections (`## 1. Detecting that a session is paused`), one bullet per point, each opening with a bold label.
- A context section and a worked numeric example are welcome when they show *why* a point matters.
- It may end with "what any design must decide" — the questions, not the answers.
- **States no design choice, on purpose.** Say so in the opening paragraph.
- **An answered point is kept and marked**: `→ answered in REQUIREMENTS.md R4` or `→ answered in DESIGN.md §3 (2026-10-09)`. An open point stays unmarked, so the open ones are easy to scan.
- If the whole project is dropped, keep the file with an **Obsolete (date)** banner at the top saying why.

Examples: `~/dev/agent-auto-resume/CONSIDERATIONS.md` (15 themes, "lists no design choice on purpose"), `~/dev/agent-quota-maximizer/design/04_start_windows/CONSIDERATIONS.md` (context, a worked example in numbers, then what the service must decide).

## `REQUIREMENTS.md`

**Test: would the user notice if it were missing?** A requirement is a benefit for whoever uses the thing — the end user, or the developer using the tool — never a mechanism.

- Opens with the **goal** in the user's own words, in the first person if the user wrote it that way.
- **No vocabulary table of its own**: new words go into the `## Vocabulary` table of the root `AGENTS.md` (create it now if the project has none), and this file uses them.
- Requirements numbered `R1`, `R2`…, grouped under user-facing headings ("When a job runs", "Seeing what happened"), as a table: `| # | Requirement |`.
- **Primary** vs **secondary (nice to have, later)** requirements.
- **Out of scope**: what the user explicitly does not want, so it is not built by accident.
- **Decided questions**: questions the user has answered, with the answer, so they are not asked again.
- **Never**: an architecture, a file name, a language, a data format, an exit code, an interval, a number. If one creeps in, move it to `DESIGN.md` and list it there under "Moved out of the requirements".

Example: `~/dev/job-runner/REQUIREMENTS.md` ("from the user's point of view only: the benefit, never the mechanism").

## `DESIGN.md`

**Test: does it choose?** A design document makes choices about what to build and how to structure it so that every requirement is met. It is not the implementation yet.

- Opens with a **header table** for a component: command, reads, writes, acts (yes/no, cost), consumed by.
- One section per decision: **the choice, the reason, the rejected alternatives and why** they lost. A choice without its reason will be undone by the next agent.
- **Pseudo-code is welcome** for the core rule or algorithm, in a fenced `text` block.
- Cite which requirement each choice serves (`serves R3`).
- Mark what is measured vs assumed: **[verified]**, **[assumed]**.
- **Acceptance**: how we will know it works.
- **Open points**: decisions not yet made.
- Prefer one `DESIGN.md` updated in place, with a short "Superseded decisions" section, over `DESIGN_v1.md` / `DESIGN_v2.md` side by side; git keeps the old versions.
- When the design splits per stage, one `design/<NN>_<stage>/DESIGN.md` per stage plus an overall `design/DESIGN.md`. A per-stage `CONSIDERATIONS.md` may sit beside it.

Examples: `~/dev/agent-quota-maximizer/design/04_start_windows/DESIGN.md` (header table, a pseudo-code rule, "why always rather than only when needed", acceptance, open points), `~/dev/job-runner/DESIGN.md` (with "Superseded decisions": what was decided, then replaced, and why).

## Once the code exists

| What the design file holds | Where it ends up |
|---|---|
| a rule an agent must follow when editing the code | `AGENTS.md`, as a one-line rule pointing at the design section |
| the reason for a choice, the rejected alternatives | stays in `DESIGN.md` |
| how the built thing actually works now | `doc/` beside the code |
| an unanswered consideration | stays in `CONSIDERATIONS.md`, or becomes a task (skill `tasks`) when it is actionable |
