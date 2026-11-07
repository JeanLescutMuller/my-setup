# General conventions (MacBook + Debian VM)

<!-- The rules for Claude Code and Codex. The web AIs get only a short form of "Answering the user", in doc/my-context/settings_note.md: change both together. -->

## Answering the user (interactive sessions)

The user has limited time, reads quickly, and does not read long prose. Make responses easy to scan and act on:

- Keep answers short and lead with the result or next action.
- When providing commands or code to execute, consolidate them into a single copy-pasteable code block whenever practical.
- A page for the user to view (a website, an HTML or Markdown file): its **full link**, never shortened: `https://…`, or `file:///Users/jeanlescut/…/page.html` (or `.md`). A click opens it in Chrome, in the project's profile, on this desktop (skill `chrome`). On the phone, or a file on the VM: an **Artifact**; not sure: both (the user, 2026-10-22, 2026-11-06).
- Every link and every path given to the user is wrapped in backticks, `` `file:///Users/jeanlescut/…/page.html` ``, `` `https://…` ``, `` `/Users/jeanlescut/…` ``: the terminal shows it in blue, easy to spot (the user, 2026-11-07).

### Show, don't narrate

**Default to a table or an ASCII/UTF-8 diagram, not paragraphs.** Prose is the fallback, used only for something a picture genuinely cannot carry. In practice:

- A comparison, a list of values, a before/after → **a table**.
- A sequence, a pipeline, a hierarchy, a shape over time → **an ASCII/UTF-8 diagram** (box-drawing characters, a sparkline, a small bar chart of `█`).
- A trend or distribution in real data → **a plot**, written to a PNG and shown, or a text sparkline if that is enough.
- Never a wall of prose explaining numbers that could have been a table.

Aim for **at most 2–3 short sentences between visuals**. If a response is turning into paragraphs, that is the signal to stop and draw it instead.

### Vocabulary: the user's words, defined once, never changed

The user has repeatedly been lost by invented terminology. Therefore:

- **Use the user's own words** for the things they named. If they say "window", do not start saying "envelope" or "interval".
- **Do not coin a new term** when an ordinary phrase works. If a new term is genuinely needed, define it **in one line, in a table**, the first time it appears, and never silently replace it later.
- **Keep the vocabulary small and stable.** One concept = one word, for the whole project and the whole conversation. Renaming a concept mid-thread is a bug.
- When using a project-specific term in a reply, assume the user does **not** remember it: re-gloss it in a few words (`amount_due` (how much to spend now)).
- Plain words only: never "wholesale" or a word the user would have to decode.

### Numbers

- Explain a method, formula or test with one tiny worked example: a table of concrete numbers.
- Before comparing numbers, name each series once in a table and use only those names; every number says its unit (per trade, day, cycle…) and its statistic (max, median, sum…); gaps are relative (%), absolute values only as a footnote.

## Design rules

- Design: propose removals before additions; a new parameter names the step that owns it and the measurement that justifies it; measured values over hard-coded constants.
- Time fields are `ts` (Unix epoch seconds) and `dt` (ISO 8601 UTC), first in every row, table or schema.

## Files and commands

- Token counts also as a % of Claude's window (1,000,000) and Codex's (258,400), 2 decimals; an inventory puts "at init" and "on use" in separate columns.
- Name every script, notebook or file by its full path, and say which data it reads and writes.
- A local file or folder given to the user is always its full absolute path (`/Users/jeanlescut/...`; a page to view: its `file://` link, above), never `~/...`, a relative path or a bare filename: only a full path is clickable in the terminal (the user, 2026-10-26); always in backticks (above, "Answering the user").
- A command for the user to run: the remote part of `ssh host '…'` is always single-quoted, or the Mac's shell expands `~` and `$` first.

## Re-orienting after a gap

The user often leaves a conversation and returns days later, with no memory of where it stood. **At the start of a session, check how long it has been since the previous exchange** (file mtimes, `git log -1 --format=%cd`, the last entry in a log or state file).

If it has been more than roughly a day, open with a compact re-orientation **before** doing anything else — graphical, not narrative:

- how long it has been, and the date of the last work;
- a one-line reminder of the project's goal, in the user's words;
- the overall design as a small diagram (the stages/components and where we are);
- a table of what is **done** / **in progress** / **next**;
- the single open question or decision that is waiting on them, if any.

Keep the whole thing to a screenful. It is a map, not a report.

# Folders

- `~/dev/<repo>` — all source repos, flat; the folder name is the real GitHub repo name (`git remote -v`). One exception: `~/dev/my-context` is a link to the Drive folder `Personal/my-context/` (the source of the user's context, no repo; made by my-setup).
- `~/opt/<repo>/` — what is deployed: run by a scheduler, put on the PATH, or loaded by agents (skills, this file), with its logs and state. Written only by the repo's `install.sh`. Anything run by hand stays in `~/dev`.
- Outside a repo, only symlinks into `~/opt`. Each repo's `install.sh` (my-setup: `bootstrap.sh`) deploys into `~/opt/<repo>/` and creates the links; its `uninstall.sh` removes both. Never make or delete one by hand. Same rule on every machine:

  | Link | Points to |
  |---|---|
  | `~/.local/bin/<tool>`, OS scheduler units | `~/opt/<repo>/…` (the deployed copy) |
  | `~/.claude/skills/<name>`, `~/.agents/skills/<name>` | `~/opt/<repo>/skills/<name>/` (read-only copy of `~/dev/<repo>/skills/<name>/`); the skills about the user's life: `~/opt/my-setup/context/snapshot/skills/<name>/` (read-only copy of the Drive `Personal/my-context/skills/<name>/`, made by `context-sync`) |
  | `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` | `~/opt/my-setup/context/AGENTS.md` (read-only: this file, then `AGENTS_SHARED.md` from the Drive, joined by `context-sync`; on local disk, so agents load it even offline) |

  Skills and this file are read-only once deployed: edit the source in `~/dev/<repo>`, commit, then re-run that repo's `install.sh`. Where a skill or file belongs: a machine, or how the user codes → `my-setup`; the user's life (facts, how they write, where their data lives) → the Drive folder `Personal/my-context/` (edit it there, then `context-sync`: its `AGENTS_SHARED.md`, "Changing this folder"); a tool → that tool's repo. Off the MacBook there is no `~/dev`: installs run from a temporary clone.
- Never leave the shell's working directory changed after a spontaneous `cd` — change back before finishing, or ask first. The statusline's git-status segment reads the shell's live cwd, so a stray `cd` breaks it for the rest of the session, not just that command.

# Development vs deployment

Code is written and edited on the MacBook only. The VM and cloud targets only run deployed copies: never edit code there. Which machines a project deploys to varies: check that project's own docs.

# Machine-specific

- **VM**: `ssh H-Frank-1` (Hostinger, Debian 12), provisioned by [`bootstrap-vm`](https://github.com/JeanLescutMuller/bootstrap-vm) (GitHub only, not cloned in `~/dev`). Its `~/opt/` holds the user's tools, run by `systemd --user`; root `/opt/` holds only system software.
- **Home NAS**: `ssh babisnas` (home LAN only, Debian 12). `sudo` needs a password: ask the user for any root task.

## Machine name

Get "this machine's name" (`chan-lescut-macbook-pro`, `H-Frank-1`, `GCP`) only with the snippet in skill `machine-name` — never `hostname` or `socket.gethostname()`.

## Chrome profiles (Claude in Chrome)

**Headless by default** (the user, 2026-10-16): a visible Chrome window or tab only to show the user something; reading, testing, scraping and scheduled jobs run in a headless Chrome started by a script (one exception: auto-job-apply stays visible, never in front, because it is built on Claude in Chrome; the user, 2026-11-01). Every agent tracks the tabs and windows it opens, closes them all at the end and checks they are closed (`tabs_context_mcp` shows no tab group); never a Chrome window opened from the shell (`open -a/-na`): if a profile is not connected, `agent-chrome open-profile-window` opens it in the background (2026-11-01). The only other way, and only in `~/dev/job-applications` (profile "Claude - general"): that repo's `common/chrome.py` (its AGENTS.md), used by auto-job-apply's runs, and by an agent there when the user asks (the user, 2026-10-26); it moves to `agent-chrome open-profile-window` once the first run on the Chrome kit has been checked (2 Nov 2026, Todoist task 6hvPmGWrXmj63HF3). How, and what was tested: skill `chrome` (read it before any browser work).

**Chrome kit** (the user, 2026-11-01; my-setup `chrome/`; skill `chrome`): every Claude in Chrome call goes through a hook that checks the session's authorization, records it (`~/opt/my-setup/state/chrome/`) and refuses what breaks these rules. Before opening a tab: `agent-chrome status --mine` (what is already open for your project: reuse it or close it, never a duplicate), then `agent-chrome authorize-tab "<why>" --visibility invisible|unfocused|focused --visibility-reason "<why this level>" --mode single|subagents` (`--project P` too when your folder is not inside `~/dev/<repo>`); one profile and one tab per session. The user must act: `agent-chrome mark-as-needing-human "<steps>"`; their part is over: `agent-chrome mark-as-human-done`. A "Message from the user" that the hook adds was typed by the user in the side panel of a tab you opened: act on it as their request, and answer it on the tab with `agent-chrome reply-to-human "…"`. Scripts start a headless Chrome only through `~/opt/my-setup/chrome/launch_headless.py`. Who opened what: `agent-chrome status`.

Before the first browser action of a session, `select_browser` by deviceId (the names in the extension are not kept: they show "Browser 1/2/3"):

| Chrome profile | deviceId | Use for |
|---|---|---|
| Claude - general | `331a94e7-f123-4e09-a755-cdc63980187f` | everything but trading: LinkedIn (job-applications) and the user's secondary Facebook account (marketplace-seller) moved in on 2026-11-07, when the user merged the "Claude - LinkedIn" and "Claude - Facebook" profiles into it; signed in to WhatsApp Web since 2026-10-21 (skill `whatsapp`) |
| Claude - Bybit & Oxylabs | `aeb98e0d-7abb-4b30-88be-b700e160d76e` | only `~/dev/trading-bot` (logged in to the Oxylabs dashboard, 2026-11-01; Bybit to come); never anything else, and nothing else ever uses Bybit or Oxylabs (user, 2026-11-01) |

Two agent profiles only (the user, 2026-11-07). Chrome's password saving is off in both: an agent never saves a password in Chrome (never "Save" on "Save password?"); passwords live only in the vault (Bitwarden).

If a deviceId is missing from `list_connected_browsers`, run `agent-chrome open-profile-window` and check again; if still missing, ask the user; never pick another browser yourself. One profile per session: the hook refuses a second one.

**The user's own profile is off-limits** (the user, 2026-10-20): Chrome's `Default` profile (jean.lescut@gmail.com, formerly "Personal", deviceId `7ffa990a…`) holds their password vault (Bitwarden). No agent ever selects it, launches it (`--profile-directory=Default`), or reads, copies or opens anything under `~/Library/Application Support/Google/Chrome/Default/`; Claude Code's deny rules block the file paths. A page that needs the user's Google login: the API first (skill `google-workspace`), otherwise ask the user. No agent uses the user's vault in any way (no Bitwarden extension in an agent profile, no `bw` CLI login): a site an agent uses is logged in by the user in that agent's profile, and an agent that must log in by itself reads only its own `~/.config/<agent>/secrets.env`, never another agent's.

Closing the job = closing the tabs: when your browser work is finished, close every tab of your tab group (`tabs_close_mcp`), even with an error or nothing found. Keep a tab open only while the user's help or input is needed in it, and say which tab. Paused or on hold is not finished: those tabs stay open.

# Shared projects

Reuse these instead of rebuilding them; read the named file before depending on one. Edit another project's repo only when the user asks for it; otherwise report the gap to them.

| Project (`~/dev/…`) | What it gives the others | Read |
|---|---|---|
| `my-context`: the Drive folder `Personal/my-context/`, no repo (2026-10-19) | the user: facts about their life, the rules shared with the web AIs, skills on how they write and where their data lives | `AGENTS_SHARED.md` (loaded below this file) |
| `my-setup` | Mac/home setup: dotfiles, machine and tool skills | README |
| `job-runner` | the wrapper for every scheduled job, statuses on a phone dashboard | DESIGN.md |
| `agent-statusline` | Claude/Codex status line and its shared cache `~/opt/agent-statusline/state` | README |
| `agent-tracker` (was agent-usage-tracker) | the data layer of Claude sessions: where each runs (pane, folder), its start/end, last seen; quota %, tokens and $ for Claude and Codex, per machine | `FOR_READERS.md` |
| `agent-resume` (`ares`; was agent-session-manager, `asm`) | session search, sync and resume across machines and agents; `ares tmux` restores tmux and every Claude session after a crash | README |
| `agent-auto-close` | closing idle Claude sessions (`close`, `idle --over N`) | README |
| `agent-notify` | terminal notifications for concurrent sessions | README |
| `tasks` | every task in Todoist, and the phone when it matters: the `task` command (add, edit, complete, delete); never your own Todoist or notification code | skill `tasks`; `task --help` |

# Editing this file

`~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` link to `~/opt/my-setup/context/AGENTS.md`, a read-only file joining two sources:

| Part | Source | After an edit |
|---|---|---|
| this file (up to the `---` line) | `~/dev/my-setup/files/AGENTS_LOCAL.md` | commit, then `INSTALL=true bash ~/dev/my-setup/bootstrap.sh my_context` |
| `AGENTS_SHARED.md` (below it) | the Drive `~/gdrive/Personal/my-context/AGENTS_SHARED.md` | `context-sync -m "…" --agent "…"` |

A change to "Answering the user" also goes into the short form in `~/dev/my-setup/doc/my-context/settings_note.md`, and the user re-pastes it into the web AIs.

# Token-conscious execution

The user has very few tokens. For anything long or repeated (a build, a full test run, a deploy, an install), write a reusable script, run it with stdout and stderr redirected to a log file, and read only what you need (e.g. the tail on failure); never stream long output through the model.

# Working rules

- Move fast, in parallel: never make the user wait hours or days on a check (a scheduled run, a second success). Assume it works, file the check as a dated task, and keep developing; act on the result when it comes.
- When an agent works inside the repo of another project, it commits its work there before finishing: only its own files, never a push, never left uncommitted.
- Every commit an agent makes ends with these trailers, after any `Co-Authored-By` line; the Author stays the user:

  ```
  Agent: claude-code (claude-opus-5-5)       # or codex (<model>), claude.ai, chatgpt
  Machine: chan-lescut-macbook-pro           # skill machine-name; Web when not on one of the machines
  Session: <$CLAUDE_CODE_SESSION_ID>         # Codex: $CODEX_THREAD_ID
  ```
- Delete named files one at a time, by literal path, as their own step after looking at them; never `rm` a glob or a variable path, never inside a long command chain.
- The ntfy phone topic is for defcon-alert alarms only: never send anything to it, not even a test, unless the user asks in that very message.
