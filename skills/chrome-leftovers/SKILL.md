---
name: chrome-leftovers
description: Find the Chrome windows, tabs and processes that agents or scheduled jobs left open on this Mac, say who opened each one and whether it still waits for the user, then close the leftovers with the user's OK and check they are closed. Use when the user finds Chrome windows they did not open, asks who opened a window or tab, or asks to clean up Chrome.
---

# Chrome leftovers: who opened what, and close it

The user runs this by hand when they find windows they did not open (17 Oct 2026: a "Claude - general" window opened by auto-job-apply at 02:47 and a "Claude - Facebook" window an agent opened from the shell the day before; neither waited for anything). A scheduled job comes only if it keeps happening. The rules agents must follow are in skill `chrome-headless`; this skill finds what slipped through.

## 1. Report (read-only)

**First `chrome-who`** (Chrome kit, 2026-11-01): every tab opened through Claude in Chrome or the launcher since then, with when, which session (UUID), which project, why, and whether the user must act; every Chrome process and whether the kit started it; `BLIND` when several visible Chromes run (then AppleScript below may list the wrong one's windows: deal with the orphan first). `chrome-who --since 24h` for what was opened and closed.

Then, only for windows and tabs `chrome-who` does not know (opened before the kit, or from the shell), the older report:

```bash
python3 -I ~/.claude/skills/chrome-leftovers/scripts/leftovers.py --hours 24 > /tmp/leftovers.md 2>&1; cat /tmp/leftovers.md
```

| Section | What it shows | How |
|---|---|---|
| Chrome processes | every Chrome main process, visible or headless, and its data folder | `ps` |
| Open windows and tabs | window id, tab id, URL, **who opened it** | AppleScript; its tab ids are the ids Claude in Chrome uses, matched to Claude Code transcripts |
| Sessions owning an open tab | the session's folder, last activity, its last words | a last line ending in "?" may mean it waits for the user |
| Profiles with windows in the period | when each profile's current windows were opened | the `Sessions/Session_<time>` file name (Chrome time: µs since 1601) |
| Chrome started from the shell | visible launches (`open -na`, `--profile-directory`, the Chrome binary without `--headless`) found in transcripts | some rows only mention Chrome in an edit: read the command |
| Scheduled jobs' `chrome:` lines | what jobs logged about their windows (auto-job-apply: `chrome: opened…` / `closed… (checked)`) | `~/opt/job-runner/logs/*/*/*.log` |

A window with no agent seen: match its profile's "windows opened" time with a shell launch or a job log at that minute; nothing matches → the user's own, never touch it.

## 2. Decide, then close with the user's OK

| Finding | Do |
|---|---|
| a visible Chrome with a temporary data folder, running for hours | an orphan of a test: `kill <pid>` (one pid at a time), then check `pgrep -f "user-data-dir=<folder>"` prints nothing. **Do this first**: with several visible Chromes, AppleScript may list the wrong one's windows (17 Oct 2026: 0 windows seen) |
| a tab of a session that has ended, or is idle and its last words ask nothing | close it |
| a tab of a session whose last words ask the user something | keep it; tell the user which tab and which session |
| a window a job or a shell launch opened, holding only `chrome://newtab` or that run's page | close it |
| a tab the user may have opened (no agent seen, e.g. their own claude.ai page) | never close it, even inside an agent's window: close only the other tabs |

Close by id (AppleScript talks to the user's Chrome; it never needs the window in front):

```bash
osascript -e 'tell application "Google Chrome" to close window id <window id>'
osascript -e 'tell application "Google Chrome" to close (every tab of window id <window id> whose URL starts with "chrome://newtab")'
osascript -e 'tell application "Google Chrome" to close tab id <tab id> of window id <window id>'
```

Check: run the report again; the closed ids must be gone. Say "closed (checked)" with the ids.

## 3. Then fix the opener

A leftover is a bug in what opened it: report it to the user with the opener's file and line, and fix it in its repo if they agree (skill `chrome-headless`: headless by default, close and check what you open). Tested on 17 Oct 2026 on this Mac.
