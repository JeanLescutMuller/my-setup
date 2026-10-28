# Where my-context lives: three designs

Three designs for the same goal, with no choice made yet (user, 2026-10-18). §1 is design A, §2 is design B, §3 compares them, §4 is the test (passed by all 3 web AIs, 2026-10-19), and §5 is design C, written after the user rejected both A and B (2026-10-19).

## Decision (2026-10-19)

The user chose design B ("Okay, let's just go with B"), with two conditions: "Make sure your available offline trick works … agents will never start without their rules … Even offline", and, from the same day, the fear that "nothing is really tracked". What was built, B plus the history of design C:

| Part | Where | Answers |
|---|---|---|
| the source: facts, `AGENTS_SHARED.md`, life skills (personal-context, writing-for-others, data-organization), this file | Drive `Personal/my-context/`, plain `.md` | B1, B2 |
| `AGENTS_LOCAL.md`, the coding skills (python-coding, shell-scripting, jupyter-notebooks, documentation-writing, code-minimization) | `~/dev/my-setup` (`files/AGENTS_LOCAL.md`, `skills/`) | B3, B4 |
| `context-sync`: Drive → read-only local copy `~/opt/my-setup/context/snapshot/`; builds `~/opt/my-setup/context/AGENTS.md` = AGENTS_LOCAL + AGENTS_SHARED, linked as `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`; links the life skills; sends the copy to the VM | my-setup, job `my-setup.context-sync` every 15 min, and by agents after an edit | "never start without their rules, even offline": agents load only local files; an unreachable Drive keeps the last copy. Replaces "Available offline" (B6), which still needs the Drive app running. Codex loads everything too (fixes B5) |
| history: a commit per change with the agent's Agent/Machine/Session lines, the rest as "unattributed"; pushed to GitHub `my-context` | `~/opt/my-setup/context/history.git`, work tree = the local copy | C2–C4, C6 |
| robotics documents (vision dossier, Meta Zurich research) | Drive `Professional/Robotics/` | A2 |
| removed: the repo `~/dev/my-context`, `init/copy_to_drive.py`, `init/build_agents_web.py`, `tests/`, the Google Docs copy | | B1 |

Moved on 2026-10-28 (user): this file and `settings_note.md`, which explain the project rather than being context, left the Drive folder for `~/dev/my-setup/doc/my-context/`, next to the scripts; the Drive folder now holds only what the AIs load.

The sections below are kept as they were written before the decision.

The goal, in the user's words (2026-10-17): "I'm just not a big fan of having both a repo and a GDrive copy. The different agents working on different platforms might modify different files from different environments, and we might end up with some kind of conflict... Also a lot of my life context is on my Gdrive anyways (Health, Robotics, Job search...) and I don't see this moving at all."

| Word | Meaning |
|---|---|
| **design A** | keep the git repo: `~/dev/my-context` stays the only source, and the Drive holds a copy |
| **design B** | everything on the Drive: the Drive is the only source, and there is no repo |
| **design C** | the Drive is the only source, and git keeps its history from outside the Drive (§5) |
| **history** | design C only: the git record of every change in the Drive folder `Personal/my-context/`, kept on the Mac |
| **AGENTS_SHARED** | design B only: the one file on the Drive that every agent reads, both local and web (the user's name) |
| **local agents** · **web AIs** | Claude Code and Codex on the machines · ChatGPT, Claude.ai and Gemini (as in `AGENTS.md`) |

## 0. Today (2026-10-18)

```
~/dev/my-context (git = the only source)
 ├─ init/AGENTS_LOCAL.md ─► ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md   every local session
 ├─ skills/ (8)          ─► ~/.claude/skills/…, ~/.agents/skills/…    triggered automatically
 ├─ topics/              ─► read when needed
 └─ install.sh ─┬─► GitHub ─────────────────────► ChatGPT, Claude.ai ┐ start: settings note
                └─► Drive Personal/my-context/ ─► Gemini ────────────┘  → init/AGENTS_WEB
                    (as Google Docs, by init/copy_to_drive.py)
```

What the repo holds (bytes, 2026-10-18):

| Part | Size | Read by | About |
|---|---|---|---|
| `init/AGENTS_LOCAL.md`: answering, design, working rules | ~6 KB | local agents | the user |
| `init/AGENTS_LOCAL.md`: Folders, Machines, Chrome profiles | ~5 KB | local agents | the machines |
| skills writing-for-others, data-organization, personal-context | 29 KB | local agents + web AIs | the user |
| skills python-coding, shell-scripting, jupyter-notebooks, documentation-writing, code-minimization | ~100 KB | local agents | how the user codes |
| `topics/` about-me, health, administrative, home | 4 KB | both | facts |
| `topics/robotics/` (robotics-vision, meta-zurich + its 138 KB json, robotics, html) | 195 KB (52% of the repo) | rarely | research documents, already partly in the Drive `Professional/Robotics/` |

Two problems: the web AIs come in **two ways** (GitHub, and the Drive for Gemini), and the robotics files are in the repo **and** next to their documents in the Drive.

## 1. Design A: keep the git repo

```
~/dev/my-context (git = the only source)
 ├─ init/AGENTS_LOCAL.md ─► ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md
 ├─ skills/ (life only)  ─► ~/.claude/skills/…
 ├─ topics/ (small facts; robotics: a pointer to the Drive)
 └─ install.sh ─► Drive Personal/my-context/ (Google Docs, read-only copy) ─► all 3 web AIs
```

| # | Choice | Reason | Rejected, and why |
|---|---|---|---|
| A1 | the repo is the only source; the Drive copy is one way, written only by `install.sh` | git gives diffs, commits by agents, `tests/`, and the VM installs from a clone | none |
| A2 | `topics/robotics/` moves to the Drive `Professional/Robotics/`, and `topics/` keeps one line pointing to it | research documents belong next to their documents (skill data-organization); this halves the repo and the copy | keeping both: the duplication the user saw |
| A3 | the Drive copy becomes the **only** web way in: ChatGPT and Claude.ai read it through their Google Drive connectors, as Gemini does | one settings note instead of two, and the GitHub connectors can go | GitHub for ChatGPT and Claude.ai: a second way in |
| A4 | later, maybe: the machine sections of `AGENTS_LOCAL.md` move to my-setup | a machine belongs in my-setup (the "Folders" rule) | doing it now: Codex cannot include a file, so `install.sh` would have to join two files |

Conflicts: the web AIs never write (they add a Todoist task instead), and the only writers are local agents through git, which refuses a clash instead of losing it. A hand edit made in the Drive copy is overwritten at the next `install.sh`: a known rule, with no conflict.

## 2. Design B: everything on the Drive

```
my-setup (git)      AGENTS_LOCAL: machines, folders, Chrome, commits, tokens ─► ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md
                    coding skills (python, shell, jupyter, docs, code-minimization) ─► ~/.claude/skills/
                    mounts ~/gdrive, links the life skills below into ~/.claude/skills/
                    CLAUDE.md: @~/gdrive/…/AGENTS_SHARED.md (Codex: "read it")
Drive (~/gdrive)    AGENTS_SHARED.md: how to answer, the index        ◄─ local agents and all 3 web AIs
                    skills: writing-for-others, data-organization, personal-context
                    facts: next to their documents (Health, Robotics, Job search)
```

| # | Choice | Reason | Rejected, and why |
|---|---|---|---|
| B1 | the Drive is the only source; the my-context repo, `init/copy_to_drive.py`, `init/build_agents_web.py`, `tests/` and the settings-note fingerprint are deleted | one copy of everything, nothing to keep in step | the repo plus a copy: the user does not want both |
| B2 | the shared files are plain `.md` files in the Drive, not Google Docs | through the mount, a Google Doc is only a link: `~/gdrive/Personal/my-context/init/AGENTS_WEB.gdoc` holds `{"doc_id": "1AsE…"}`, not the text [verified 2026-10-18] | Google Docs: local agents cannot read them, and skills cannot load from them |
| B3 | `AGENTS_LOCAL` moves to my-setup | it is mostly about the machines | |
| B4 | the coding skills move to my-setup, not the Drive | they are about code, not the user's life | |
| B5 | Claude Code loads AGENTS_SHARED with `@~/gdrive/…/AGENTS_SHARED.md` in CLAUDE.md; Codex gets an instruction to read it | `@` loads it into every session; Codex has no include, so there it can be skipped [assumed] | |
| B6 | `~/gdrive` already links to the Drive for Desktop folder [verified 2026-10-18]; my-setup makes that link and checks the app is running | | |

Conflicts: the web AIs never write, so the only writers are local agents on the Mac. Drive does not merge: on a clash it keeps both files [assumed], and nothing warns anyone.

## 3. Comparison

| | Design A: keep the git repo | Design B: everything on the Drive |
|---|---|---|
| sources of a fact | 1 (the repo) plus a generated copy | **1** |
| ways in for the web AIs | 1 (the Drive copy, after A3) | 1 (the Drive) |
| conflict between two writers | git refuses it, and the agent merges | Drive keeps both files, silently [assumed] |
| hand edit in the Drive | lost at the next `install.sh` | **kept** (it is the source) |
| history | git: diffs, commit messages, the agent trailers | Drive versions, about 30 days, no diffs [assumed]; the NAS backup of the Drive |
| code to keep working | `copy_to_drive.py` (6 KB), `build_agents_web.py` (5 KB), `tests/`, fingerprint | **none here**; my-setup gains the skill links and the `@` line |
| loading in Claude Code | automatic (symlink) | automatic (`@` import) |
| loading in Codex | automatic (symlink) | an instruction only |
| the VM (loads `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` today [verified 2026-10-18]) | works: installs from a clone | **no Drive there**, no rclone [verified 2026-10-18]: needs rclone, or the VM gets only AGENTS_LOCAL |
| without the Drive app (offline, logged out) | works | the life skills and AGENTS_SHARED are missing |
| robotics, health, job-search facts | small facts in the repo, documents in the Drive (after A2) | **all in the Drive**, next to their documents |
| web AIs read | Google Docs (Gemini: tested 2026-10-16) | `.md` files: **untested** for all 3 |
| breaks the current rules | no | yes: my-setup, data-organization ("never a source") and this `AGENTS.md` are rewritten |

```
                 simpler  ◄────────────────────────────►  safer
design B: 1 place, no copy code          design A: git, the VM, Codex, offline all keep working
```

## 4. What decides

| Test | Needed by | Pass → | Fail → |
|---|---|---|---|
| T1: from its settings note alone, each web AI opens a **Google Doc** in the Drive by its path | A3 | A3 holds | ChatGPT and Claude.ai keep GitHub (two ways in, as today) |
| T2: same with a plain **`.md` file** in the Drive | B2 | design B is possible | design B would need a Drive → disk copy for the local agents: the same machinery as A, reversed, so A wins |

Results (2026-10-19): a test file `Personal/2026_10_19_agent_read_test/agent_read_test.md` holding a random code word, written through `~/gdrive`, and the Google Doc `Personal/my-context/init/AGENTS_WEB`. The question "Use Google Drive to open … and tell me the code word / quote its first heading" was asked in a chat, not yet through the settings note.

| Web AI | T1 Google Doc | T2 `.md` |
|---|---|---|
| Gemini (Personal profile) | ✅ quoted the heading | ✅ gave the code word |
| ChatGPT (Personal profile, Plus) | ✅ quoted the heading | ✅ gave the code word |
| Claude.ai (Personal profile, Max) | ✅ quoted the heading (after the user connected Google Drive, 2026-10-19) | ✅ gave the code word |

How to choose: if T2 passes for all 3 web AIs and the VM can do without the shared part (or gets rclone), design B; otherwise design A.

## 5. Design C: the Drive is the source, git keeps its history

Why (user, 2026-10-19): "my whole drive is my context in the end"; "I don't like having a repository which is separate from the drive and pretends to hold the source of truth"; against B: "nothing is really tracked … I will not be able to roll back or to investigate who did that".

```
Drive Personal/my-context/  (the only source; plain .md)
 ├─ AGENTS_LOCAL.md ◄── ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md (links, made by my-setup)
 ├─ AGENTS_WEB.md   ◄── settings note of all 3 web AIs (Google Drive connector, §4)
 ├─ skills/<name>/  ◄── ~/.claude/skills/<name>, ~/.agents/skills/<name> (links)
 └─ facts with no document of their own (about-me); the others live next to their documents
        │ watched by
        ▼
~/opt/my-context/history.git  (on the Mac, never in the Drive)
 ├─ an agent that edits commits at once, with its Agent/Machine/Session trailers  → who did it
 ├─ a job every hour commits what is left as "unattributed" (a hand edit, a web AI)
 └─ pushed to the private GitHub repo my-context: off-Mac copy of the history, read by the VM
```

| # | Choice | Reason | Rejected, and why |
|---|---|---|---|
| C1 | the Drive folder `Personal/my-context/` is the only source; the files are plain `.md` | all 3 web AIs read `.md` in the Drive (§4), and local agents read them through `~/gdrive` (B2) | Google Docs: local agents cannot read them (B2) |
| C2 | the git folder lives on the Mac, outside the Drive, with the Drive folder as its work tree (`GIT_DIR=~/opt/my-context/history.git GIT_WORK_TREE=~/gdrive/Personal/my-context`) | history, diffs and rollback without putting `.git` in the Drive: commit, diff and `checkout HEAD~1 -- <file>` back into the Drive worked, and nothing appeared in the Drive folder [verified 2026-10-19, on a test folder] | `.git` inside the Drive: Drive for Desktop syncing git's many small files can corrupt it [assumed]; design B: no history |
| C3 | an agent commits right after it edits, with the trailers of `AGENTS_LOCAL.md` | answers "who did that": the Session trailer leads to the session (asm) | only the hourly job: a change would have a time but no author |
| C4 | an hourly job (job-runner) commits whatever is left | catches edits made by hand or by a web AI | |
| C5 | the links are symlinks into the Drive, so Claude Code **and Codex** load the rules every session | fixes B5 (Codex only "told to read it") | |
| C6 | the history is pushed to the existing private GitHub repo my-context, and the VM installs from it read-only | the VM has no Drive; GitHub keeps the history off the Mac and keeps today's commits | rclone on the VM |
| C7 | removed: `~/dev/my-context` as a source, `init/copy_to_drive.py`, `init/build_agents_web.py`, `tests/`, the settings-note fingerprint, the `~/opt` read-only copies; `AGENTS_WEB.md` is written by hand | one place, nothing to keep in step | |

| Risk | Way around it |
|---|---|
| the Drive app stopped or logged out: `~/.claude/CLAUDE.md` points to nothing, and agents run without rules | mark the folder "Available offline"; a check (job or status line) that the link resolves |
| any agent can change a skill (nothing is read-only any more) | that is the point; every change is in the history and can be rolled back |
| two edits at once: Drive keeps both files | the history shows the stray copy |
| facts next to their documents (Health…) are outside the history | Drive's own versions and the NAS backup; or keep them in `Personal/my-context/` |

Against the user's three complaints:

| Complaint | A | B | C |
|---|---|---|---|
| a repo that pretends to be the source | ❌ | ✅ | ✅ |
| two or three places that can conflict | ❌ repo + Drive facts + Drive copy | ✅ | ✅ (the history is a record, not a source) |
| no versioning, no "who did that" | ✅ | ❌ | ✅ |

## Open points

- T1 and T2 were asked in a chat, not through the settings note: check once after the switch.
- Design C: which facts stay in `Personal/my-context/` (tracked) and which go next to their documents (not tracked).
- Design B: do the facts live next to their documents (Health, Robotics, Job search), or in one Drive folder with pointers?
- Design B: the other repos' skills in the index today (tasks, application-writing, learning-german): stay on GitHub, or move to the Drive?
