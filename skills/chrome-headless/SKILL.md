---
name: chrome-headless
description: Chrome on this Mac without disturbing the user - headless by default, a visible window only to show the user something; with Claude in Chrome, track every tab and window you open, close them all at the end and check they are closed. Which way to drive Chrome (a headless Chrome from a script, or Claude in Chrome in the user's visible windows), the launch snippet, how to log a headless Chrome in to a site once, and what was tested. Use before any browser work, any Claude in Chrome tool, any Playwright/CDP script, any test that starts Chrome, and before opening a Chrome window or tab.
---

# Chrome without disturbing the user: headless by default

**The rule (the user, 2026-10-16):** "only use visible windows when you have to show me something". Every window or tab that appears on the user's screen interrupts their work; on 2026-10-16 test runs opened windows again and again ("Windows keep popping up in front of me").

## Which way

```
need a browser
 ├─ to SHOW the user something (a page to check, a form for them to finish, a login they must type)
 │      → Claude in Chrome, in the right profile (CLAUDE.md "Chrome profiles"): ONE tab in your tab group,
 │        say in chat which tab and why, close it as soon as they are done
 └─ anything else: read a page, test, scrape, fill and submit forms, scheduled jobs, every test run
        → a headless Chrome started by your script (below): no window, no Dock-visible window, nothing on screen
           ├─ public pages: a temporary data folder
           └─ a site that needs a login: the tool's own data folder in ~/opt/<repo>/chrome/, logged in ONCE by the
              user in a visible window (tools/chrome_login.sh style), then headless forever
```

| Never | Why |
|---|---|
| `open -a "Google Chrome"`, `open -na … --profile-directory=…`, a non-headless Playwright launch, for anything but showing the user | a window in front of them |
| a test that starts Chrome visibly "just to see" | same; test headless, look at a screenshot file |
| Claude in Chrome to read or scrape pages the user does not need to see | its tabs live in the user's visible windows |
| driving the user's normal profiles from a script | Chrome ≥ 136 ignores `--remote-debugging-port` on its default data folder (all usual profiles): only an own data folder works |

## Claude in Chrome: track every tab and window, close them, check they are closed

The user, 2026-10-16: "every agent should keep track of which windows and tabs it opens and always close them at the end, making sure they're closed" (they had to close two windows an agent opened with `open -na … --profile-directory=…` and never closed).

| Step | Do |
|---|---|
| Before | `select_browser` by deviceId (CLAUDE.md table), then `tabs_context_mcp`; if the profile is **not connected**, ask the user to open that Chrome profile: **never open a window from the shell** (`open -a/-na "Google Chrome"`, the hook refuses it): Claude in Chrome cannot see or close it. One exception (user, 2026-10-26): when the user asks for it, an agent working in `~/dev/job-applications` opens and closes "Claude - LinkedIn" itself with that repo's `.venv/bin/python -m common.chrome open` / `close`, which records the window and closes it (checked) |
| What is open already | `chrome-claim open` (`--json`): the tabs open for your project, by any session or job, with who, when and why. Reuse yours; another session's tab cannot be driven by you (Claude in Chrome shows each session only its own group): if nobody waits on it (`needs_human` empty), close it before opening yours; if someone does, leave it and tell the user |
| Say why | `chrome-claim --purpose "…"` plus `--needs-human "what the user must do"` (captcha, login, upload…) or `--visible-because "why headless can't do it"` (a logged-in profile…). The hook refuses to open a page without it. Shown on the tab by the extension "Agent tab notes" |
| One profile per session | your first `select_browser` fixes the session's profile; another one is refused: LinkedIn and a general site need two sessions |
| Open | only with `tabs_create_mcp` (or `tabs_context_mcp createIfEmpty`, which opens a new window holding your tab group): **one tab per session**, the hook refuses a second ("reuse tab N"); note its id |
| The user's part | `chrome-claim --needs-human "…"` when it starts (red bar on the tab), `chrome-claim done` when it is over |
| A "Message from the user" from the hook | typed in the tab's comment box: act on it, answer with `chrome-claim --message "…"` (shown on the tab) |
| A tab you did not open | never close, reuse or navigate it, unless the user asked |
| End of the work (done, failed or nothing found) | `tabs_close_mcp` on **every** tab id of your group; closing the last one removes the group and its window |
| Check | call `tabs_context_mcp` (without `createIfEmpty`) for that browser: it must report no tab group. Say in your answer "tabs closed (checked)" |
| A headless Chrome you started | `terminate()` it, then check no process holds its data folder: `pgrep -f "user-data-dir=<folder>"` prints nothing |
| Keeping a tab open | only while the user must act in it; name the tab and what they must do; close it as soon as they say they are done |
| Several browsers in one session | the check above for each browser you selected |
| A script or scheduled job that must load a profile for Claude in Chrome (the extension runs only in a loaded profile) | only when a run needs it; note the window ids before and after (AppleScript `get id of every window`), close that window when the run is done (process exit; kept only while the user must act in it), check, and log one `chrome: opened…` / `closed… (checked)` line. Model: `~/dev/job-applications/common/chrome.py` (17 Oct 2026: it used to leave one window open every night) |

## The launch: the kit's launcher (Python, Playwright attached)

Every script starts its headless Chrome through `~/opt/my-setup/chrome/launch_headless.py` (my-setup, 2026-11-01): it records the tab like the hook does (`chrome-who` shows it), reuses the Chrome and tab the previous run of the same job or project left with `keep=True`, and otherwise closes Chrome and checks no process is left.

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
# keep=True: leave Chrome and the tab for the next run (needs_human='…' if the user must act in it)
```

A temporary data folder (`tempfile.mkdtemp()`) for public pages; the tool's own `~/opt/<repo>/chrome/` for a site that needs a login. Flags it uses (tested below): `--headless`, `--disable-blink-features=AutomationControlled`, a normal user agent. Extra Chrome options: `flags=('--disk-cache-size=…',)`. A killed caller never leaves Chrome running: a watcher quits it and records the close (unless `keep=True`). A data folder a visible Chrome already uses is refused. CLI for tests: `launch_headless.py --data-dir D --purpose P --url U [--keep] | --close`.

Logging a tool's Chrome in once: open the same data folder **without** `--headless` and with the site's login page, tell the user to log in and quit it with cmd+Q; check from then on with a headless run (a login form on the page = logged out: ask the user again, never type a password).

## What was tested (2026-10-15/16, this Mac)

| Way | Window on screen? | Pages, clicks | Screenshot | `navigator.webdriver` |
|---|---|---|---|---|
| **`--headless` + `--disable-blink-features=AutomationControlled` + normal user agent** | **none** | ✅ | ✅ | **false** (normal brands) |
| `--headless` alone | none | ✅ | ✅ | true: pages see automation |
| Playwright `launch_persistent_context` (even without `--enable-automation`) | yes | ✅ | ✅ | true |
| own Chrome + `connect_over_cdp`, visible | yes | ✅ | ✅ | false |
| `open -n -g -j` (macOS "launch hidden") | **windows still appeared** for the user | ✅ | ✅ | false |
| `--window-position=-3000,-3000` | macOS moves it back on screen | ✅ | ✅ | false |
| minimized through CDP right after start | flashes, then in the Dock | ✅ | ❌ times out | false |

A login made in a visible window works in the same data folder headless (Facebook, 2026-10-16). Sites with bot checks (Cloudflare "Just a moment…") may still block a headless Chrome: then show the user, or use Claude in Chrome on a visible tab with their OK.

Who opened what: `chrome-who` (open now, `--since 7d`, `--project`). Windows or tabs left open anyway: skill `chrome-leftovers`.
