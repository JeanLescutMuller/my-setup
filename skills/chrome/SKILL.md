---
name: chrome
description: How an agent uses Chrome on this Mac - the 5 questions to answer first (may I open a tab, which profile, headless or visible, which window, focus), the agent-chrome command (authorize-tab, mark-as-needing-human, mark-as-human-done, reply-to-human, status, open-profile-window), the headless launcher for scripts, what was tested, and how to find and close Chrome windows and tabs left open. Use before any browser work, any Claude in Chrome tool, any Playwright/CDP script or test that starts Chrome, before opening a Chrome window or tab, and when the user asks who opened a window or tab or asks to clean up Chrome.
---

# Chrome for agents

**The rules (the user, 2026-10-16 to 2026-11-01):** headless by default; a visible tab only when a human must act or only a logged-in profile can do it; every tab says who opened it, when, for which project and why; nothing left open; never in front of the user. The Chrome kit (my-setup `chrome/`, deployed in `~/opt/my-setup/chrome/`) enforces them:

| Piece | Role |
|---|---|
| **the hook** | runs on every Claude in Chrome call (Claude Code starts it, the agent cannot skip it): checks the session's authorization, records each open, navigation and close in `~/opt/my-setup/state/chrome/` (`open.json` = open now, `history/YYYY-MM.jsonl` = every event), refuses what breaks a rule and says which command to run |
| **`agent-chrome`** | the agent gets its authorization, tells what the hook cannot guess (needs human, done, its reply), asks what is open |
| **the launcher** | `~/opt/my-setup/chrome/launch_headless.py`: the only way a script starts a headless Chrome (recorded, reused, closed and checked) |
| **the extension "Agent tab notes"** | in the 3 agent profiles: a 30 px bar on each agent tab (opened at, session, project, why, "NEEDS HUMAN: …"), a badge, a side panel where the user writes to the agent; puts each session's tab in its project's window |

## The 5 questions

### 1. May I open a tab? (security)

Only after `agent-chrome authorize-tab "<why>" --visibility invisible|unfocused|focused --visibility-reason "<why this level>" --mode single|subagents` (`--project P` too when your folder is not inside `~/dev/<repo>`). Until then the hook refuses to open a page. The authorization belongs to this session only (read from `$CLAUDE_CODE_SESSION_ID`, which Claude Code sets in every agent shell; the hook gets the same id), for its whole life. **Always name your project**: inside `~/dev/<repo>` it is that repo (another value is refused); anywhere else `--project` is required, and it decides which profiles you may use.

| `--visibility` | Means | The kit enforces |
|---|---|---|
| `invisible` | headless Chrome through the launcher only | the hook refuses any Claude in Chrome tab; the launcher requires this level inside a session |
| `unfocused` | a Claude in Chrome tab in your project's window, never in front | the default for visible work |
| `focused` | the same, and the window comes to the front once | only after `mark-as-needing-human`, never without a need | Never start a Chrome from the shell (`open -a/-na "Google Chrome"`, the Chrome binary): the hook refuses it, nobody could see or close that window.

It does not limit sites or actions inside the tab: stay on what the user asked for (job-applications has its own site list, `common/browser_policy.py`).

### 2. Which profile? (security)

The table in CLAUDE.md ("Chrome profiles"): Claude - general → any project; Claude - LinkedIn → only job-applications; Claude - Facebook → only marketplace-seller; the user's own profile → never (their password vault). `select_browser` by deviceId; **the first profile you select is fixed for the session**: the hook refuses another one. LinkedIn and a general site need two sessions. Profiles stop honest mistakes, not a malicious agent: no vault in any agent profile, each job's secrets only in its own `~/.config/<agent>/`.

### 3. Headless, invisible? (the user's comfort)

Yes, unless a human must act or only a logged-in visible profile can do it:

```
need a browser
 ├─ to SHOW the user something, or a site only the visible logged-in profile can reach
 │      → Claude in Chrome, right profile, ONE tab (questions 4 and 5)
 └─ anything else: read a page, test, scrape, fill and submit forms, scheduled jobs, every test run
        → a headless Chrome started by your script through the launcher (below)
           ├─ public pages: a temporary data folder
           └─ a site that needs a login: the tool's own ~/opt/<repo>/chrome/, logged in ONCE by the user
              in a visible window (tools/chrome_login.sh style), then headless forever
```

The launcher (Python; Playwright attaches to the Chrome it starts):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / 'opt/my-setup/chrome'))
from launch_headless import headless                  # standard library only
from playwright.sync_api import sync_playwright       # playwright==1.55.0, attaches to the Mac's Chrome, no download

with headless(Path.home() / 'opt/<repo>/chrome', purpose='…', url='https://example.com') as h, sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{h['port']}")
    page = next(pg for pg in browser.contexts[0].pages   # the launcher's tab, by its CDP target id
                if pg.context.new_cdp_session(pg).send('Target.getTargetInfo')['targetInfo']['targetId'] == h['target_id'])
    page.goto('https://example.com')                  # a reused tab keeps its old page: navigate it yourself
    page.screenshot(path='/tmp/look.png')             # look at the file, not at a window
```

| `headless(…)` | |
|---|---|
| `data_dir`, `purpose` | required |
| `url`, `keep=False`, `needs_human=None`, `flags=()` | optional. `keep=True`: leave Chrome and the tab for the next run of the same job or project. `flags`: extra Chrome options (`'--disk-cache-size=…'`) |

Inside a Claude session, `headless()` first requires `agent-chrome authorize-tab "<why>" --visibility invisible --visibility-reason "…"`. A killed caller never leaves Chrome running (a watcher quits it and records the close, unless `keep=True`); a data folder a visible Chrome already uses is refused. CLI for tests: `launch_headless.py --data-dir D --purpose P --url U [--keep] | --close`. LinkedIn headless (job-applications): `tools/chrome_login.sh` once (the user logs in), then `tools/check_linkedin_headless.py` says logged in / logged out / blocked (bot check). Logging a tool's Chrome in once: open the same data folder **without** headless at the site's login page, the user logs in and quits with cmd+Q; from then on a login form on the page = logged out: ask the user again, never type a password.

### 4. If visible: which window? (the user's comfort)

1. `agent-chrome status --mine`: the tabs open for your project, by any session or job. Reuse yours; another session's tab cannot be driven by you: if it does not need a human, close it; if it does, leave it and tell the user. Never a duplicate.
2. Profile **not connected** in `list_connected_browsers`: `agent-chrome open-profile-window` opens its window in the background (only if it has none; first tab names the project) and gives the focus back. It refuses when Chrome is not running or the profile is another project's: then ask the user.
3. One tab per session: `tabs_create_mcp` (or `tabs_context_mcp createIfEmpty`); a second is refused ("reuse tab N"). The extension moves your tab into your project's agent window by itself; the user places each project's window on its macOS desktop by hand (no program can move a window between desktops on macOS 26).

### 5. If visible: focus? (the user's comfort)

Never in front of the user. Claude in Chrome actions (create a tab, navigate, click, screenshot) never bring Chrome forward (tested 2026-11-01). Opening a window always takes the focus for a moment, so only `open-profile-window` does it, and it gives the focus back at once. Never use side-panel or notification actions.

## Two modes: where the human answers

| `--mode` | Who has the tab | Where the human answers | How the agent hears it |
|---|---|---|---|
| `single` | the main agent | **in the session's terminal**; the side panel says "Answer in the terminal: session <id> (tmux …)", no comment box | the human's next prompt |
| `subagents` | each subagent authorizes for itself and owns **one** tab (e.g. 10–20 subagents, one account each) | **in that tab's side panel**: the comment box talks to that tab's subagent | the subagent loops on `agent-chrome wait-for-human --timeout 60` (exit 0 = a comment, printed; 2 = none) and checks its page between calls |

In subagents mode the tab, its needs-human, comments and expiry belong to (session, subagent id): the hook refuses another agent on a tab ("tab N belongs to subagent X") and adds `--agent-id <id>` to each `agent-chrome` command a subagent runs (its shell cannot see its id). The main agent may only close its subagents' tabs; to change what one does, it messages that subagent. Claude in Chrome itself is unreliable with subagents (the tab group is sometimes shared, a closed tab can make others unreachable): each subagent starts with `tabs_context_mcp createIfEmpty`, never closes its own tab, and the main agent closes them all at the end. The password layer (secrets-and-account-migration `pwl`) works the same way: each site belongs to the subagent that started it, others are refused.

## While working, and at the end

| When | Do |
|---|---|
| the user must act (log in, captcha, upload, check before sending): right after opening the tab, or later | `agent-chrome mark-as-needing-human "<exact steps, full file paths>"`: red bar "NEEDS HUMAN: …" on the tab, badge "!"; say in chat which tab and what to do |
| their part is over | `agent-chrome mark-as-human-done` |
| nobody acts within 2 h after `mark-as-needing-human` | the kit closes the tab, the record says "expired", your next hook call tells you: tell the user; reopen only if they ask |
| the hook adds "Message from the user" | the user typed it in the tab's side panel: act on it as their request, answer with `agent-chrome reply-to-human "<text>"` (shown on the tab) |
| end of the work (done, failed or nothing found) | `tabs_close_mcp` on every tab of your group; check with `tabs_context_mcp` (no `createIfEmpty`) that no group is left; say "tabs closed (checked)". The hook reminds you once at the end of a turn that leaves a tab open with no human needed |
| keeping a tab | only while a human is needed in it (marked with `mark-as-needing-human`) |
| a scheduled job without Bash | it sets `CHROME_PURPOSE`, `CHROME_VISIBILITY` (default `unfocused`), `CHROME_VISIBILITY_REASON` and `CHROME_MODE` (default `single`) in its environment instead of `authorize-tab`; `JR_JOB` names the job |

## `agent-chrome`

| Subcommand | Required | Optional | Does |
|---|---|---|---|
| `authorize-tab "<why>"` | `--visibility invisible\|unfocused\|focused`, `--visibility-reason "…"`, `--mode single\|subagents`; `--project P` outside a repo folder | `--project P` inside a repo (must match it) | the session's authorization; its reason shows on its tabs |
| `wait-for-human` | | `--timeout S` (default 30, max 300) | subagents mode: waits for the human's comment on this agent's tab; exit 0 = comment (printed), 2 = timeout |
| `mark-as-needing-human "<what to do>"` | | | red "NEEDS HUMAN: …" bar, badge "!" |
| `mark-as-human-done` | | | clears it: "✓ done, you may close" |
| `reply-to-human "<text>"` | | | the agent's answer in the tab's thread |
| `status` | | `--mine`, `--since 7d`, `--project P`, `--json` | open agent tabs (when, session, project, why, needs human), running Chromes, BLIND warning; history with `--since` |
| `open-profile-window` | | `--project P` | the project's profile window, in the background |

The 4 session commands work only inside a Claude Code session. `chrome-claim` and `chrome-who` are the old names, kept until 2026-11-08. Options table: `~/dev/my-setup/doc/chrome-visibility/agent-chrome-options.html`.

## Leftovers: who opened what, and close it

When the user finds windows they did not open, or asks to clean up Chrome:

1. `agent-chrome status --since 24h`: every agent tab and Chrome since the kit (1 Nov 2026), who opened it and why, and every Chrome process and whether the kit started it. **BLIND** = several visible Chromes run: macOS window scripts may see the wrong one's windows; deal with the extra Chrome first (a test orphan with a temporary data folder: `kill <pid>`, one pid at a time, then check `pgrep -f "user-data-dir=<folder>"` prints nothing).
2. Only for windows and tabs the kit does not know (opened before the kit, or from the shell): `python3 -I ~/.claude/skills/chrome/scripts/leftovers.py --hours 24 > /tmp/leftovers.md 2>&1` (AppleScript windows and tabs matched to Claude Code transcripts, profiles' window times, shell launches, scheduled jobs' `chrome:` lines).
3. Decide, then close **with the user's OK**:

| Finding | Do |
|---|---|
| a tab of a session that has ended, or no human needed | close it |
| a tab that needs a human | keep it; tell the user which tab and which session |
| a window a job or a shell launch opened, holding only `chrome://newtab` or that run's page | close it |
| a tab the user may have opened (no agent seen) | never close it |

Close by id, never bringing a window to the front: `osascript -e 'tell application "Google Chrome" to close tab id <tab id> of window id <window id>'` (or `close window id <id>`). Check: run the report again, the ids must be gone; say "closed (checked)". A leftover is a bug in what opened it: report the opener's file and line to the user.

## What was tested (this Mac)

| Way | Window on screen? | Pages, clicks | Screenshot | `navigator.webdriver` |
|---|---|---|---|---|
| **headless + `--disable-blink-features=AutomationControlled` + normal user agent** (the launcher) | **none** | ✅ | ✅ | **false** |
| headless alone | none | ✅ | ✅ | true: pages see automation |
| Playwright `launch_persistent_context` | yes | ✅ | ✅ | true |
| `open -n -g -j` (macOS "launch hidden") | **windows still appeared** | ✅ | ✅ | false |
| `--window-position=-3000,-3000` | macOS moves it back on screen | ✅ | ✅ | false |

A login made in a visible window works in the same data folder headless (Facebook, 2026-10-16). Sites with bot checks may still block a headless Chrome: then a visible tab with `--needs-human`. Chrome ≥ 136 ignores remote debugging on its default data folder: scripts only drive their own data folders. 2026-11-01: Claude in Chrome keeps control of a tab group moved to another window; a new window opens on the desktop the user is looking at; opening a window takes the focus for a moment (both `open -g` and the binary).
