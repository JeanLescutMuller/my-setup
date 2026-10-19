---
name: code-minimization
description: Minimize a project's code without changing its behavior or making it hard to read. Measure the cost in code tokens (comments, docstrings and messages are free; client code is weighted for twice as many clients), then many agents in parallel (the user picks how many: the more, the better) each try a different strategy in their own worktree, checked by the same tests and an equivalence check, and the coordinator merges the best ideas. Use when the user asks to minimize, shrink, simplify or cut down a project's code, to measure its token cost, or to compare the size of two versions.
---

# Code minimization

Proven on job-runner on 2026-10-10 (session `86413088…` in `~/.claude/projects/-Users-jeanlescut-dev/`, job-runner commit `52b75be`, its `DESIGN.md` §12): cost 7294 → 5114 (−30 %, today's counter), the same 36 + 28 tests, 84 scenarios identical to the version before. Invoking this skill is the user's request for the agents it starts. **First, ask the user how many agents to run** (AskUserQuestion; options such as 5, 8, 12): the point is to try as many different ideas as possible, and the merge picks the best of them, so more agents is better.

| Word | Means |
|---|---|
| **token** | a word or one symbol of code, as `count_cost.py` counts it |
| **shared code** | written once: a library, a server, a dashboard |
| **client code** | written or copied once per client: a job's entrypoint, the `viewer.html` in each project |
| **cost** | 1 × the shared code's tokens + 2 × the client code's tokens |
| **attempt** | one agent's try at a lower cost, in its own worktree |

## 1. What is minimized, and what never is

**Minimized: code tokens only.** Comments, docstrings, log, status and error messages, clear names and blank lines are free, and they stay: never delete or shorten one to save tokens. An attempt may add comments, and the merge should add some wherever code got denser.

These rules go in the brief **before** any agent starts (on 2026-10-10 the first two arrived late and voided two attempts):

| Rule | In practice |
|---|---|
| No behavior change | same decisions, timings, outputs, texts, files and exit codes; a cut feature is a proposal for the user, never applied |
| Tests unchanged | every test still passes, checking exactly what it checked; the equivalence check (§3) says identical |
| Still readable | the user: "not a complete cryptic dense compacted piece of code like the famous fork bomb"; no clever one-liners; tokens per code line must not rise |
| No hiding | logic stays in counted files; every file the product runs is counted (job-runner's `ops.sh`, split from `lib.sh` after the count was set up, went uncounted until 2026-10-13) |
| The user's decisions | an earlier decision of the user is reversed only as a flagged proposal, with the cost it saves |

## 2. The cost

**cost = 1 × shared tokens + 2 × client tokens.** The 2 plans for twice as many clients as today. A file copied into every client is passed once per copy, so each copy counts: this pushes repeated code into the shared part.

| Part (job-runner, 2026-10-13) | Tokens | Weight | Cost |
|---|---|---|---|
| shared: `lib.sh` 3341, `dashboard.py` 3204, `install.sh` 1258, `ops.sh` 432… (8 files) | 9221 | ×1 | 9221 |
| client: 10 entrypoints + their 9 `.conf` | 869 | ×2 | 1738 |
| **total** | | | **10959** |
| task-management (an example): `viewer.html` copied in 4 projects, 80 tokens each | 320 | ×2 | 640 |

**What counts**, from `count_cost.py`'s header:

| Counts | Free |
|---|---|
| each word and each symbol of code: `2>/dev/null` = 5 tokens, with or without spaces | comments, docstrings, blank lines |
| the code inside a string: `$x`, `${…}`, `$(…)`, an f-string's `{…}`, a JS `${…}` | a string's text (a message, a path): the whole string counts 1 |
| a string that is code: read by awk, sed, jq, perl, sh, bash, ssh or python; holding a newline, `;`, `\|` or `$(`; an HTML `on…="…"`; markup in a Python string (a page template: its tags, CSS and JS) | the length of a name: `$JR_SYNC_ENV` costs the same as `$e` |
| a settings file: 1 per line | |

```bash
python3 ~/.claude/skills/code-minimization/count_cost.py [-v] --shared FILE… --client FILE…   # reads the files, writes nothing
```

Each project keeps a short wrapper that picks its own files: count every file the product ships, leave out only tests and tools. Example: `~/dev/job-runner/tools/token_cost.sh`.

## 3. The process

```
 ask how many ─► baseline ─► equivalence check ─► brief ─► N attempts (parallel, worktrees) ─► re-check each alone ─► merge ─► readability pass ─► report ─► user's OK ─► commit
```

1. **Baseline:** the cost, the tests' results, logged to a file.
2. **Equivalence check, built first by the coordinator:** one script that runs the same scenarios on the original and on a folder and compares every output (statuses, texts, files, exit codes). It writes only into a folder given as an argument. On 2026-10-10 the attempts shared one output folder and overwrote each other's results.
3. **Brief,** one file in the scratchpad, read by every attempt: the project's files to read, the rules of §1, the counter's command, the test and check commands (output to a log; read the tail only), the deliverable.
4. **N agents** (the number the user chose), in the background, one strategy each from the pool below (with more agents than strategies, give two agents the same strategy with different limits, e.g. one free to add helpers, one not), each in its own git worktree (`isolation: "worktree"`). Client files from other repos are copied into the worktree, never edited in place. Each agent writes only in its worktree: no `~/opt`, no deploy, no network; its tests run from a script file into its own log. Its final message is the report, because sub-agents cannot write report files.
5. **The coordinator re-checks each attempt alone,** one after another: cost, tests, equivalence.
6. **Merge:** pick the best ideas across all attempts, not one winner: on 2026-10-10, attempt 2's library with attempt 5's helpers, plus attempt 4's equivalence check. Then a readability pass: undo the densest tricks, add comments.
7. **Report (§4),** then, on the user's OK: commit. Changes to another repo's client files only with the user's OK for that repo.

The strategy pool. The first 5 ran on job-runner (old counter: baseline 3498); the others are ideas for more agents:

| # | Strategy (the agent's brief, in one line) | Cost | Kept |
|---|---|---|---|
| 1 | the shared code takes over what the clients repeat (one helper per pattern written in several clients) | 2607 | |
| 2 | the shared code in the fewest tokens, same API: merge parallel code paths (one runner for every env), fewer functions | **2165** | its library |
| 3 | cut what no requirement needs, each cut a proposal | 3121 | |
| 4 | the shortest clients with today's shared code | 3236 | its equivalence check |
| 5 | conventions over code: rethink the API so a client needs the fewest tokens | 2326 | its helpers and entrypoints |
| 6 | data over code: tables, loops or one config read replace repeated branches | | |
| 7 | the standard library or a tool already on the machines replaces hand-written code | | |
| 8 | merge or split files and functions where the call chain gets shorter | | |
| 9 | delete dead code: settings no client sets, branches no test or scenario reaches (each one shown) | | |
| 10 | flatten: early exits instead of nested branches, one code path instead of special cases | | |

## 4. The report to the user

One table, before → after, shared and client, with: cost, tokens, code lines, file lines, tokens per code line. The user judges by what the screen shows: on 2026-10-10 the code shrank by a third, but `lib.sh` lost only 10 % of its lines because its comments almost doubled. Say so, and say that it is wanted.

Then one row per attempt (cost, tests, equivalence), and the proposals waiting on the user (a cut feature, a reversed decision), each with the cost it saves.
