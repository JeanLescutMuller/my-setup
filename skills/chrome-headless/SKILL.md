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
| Before | `select_browser` by deviceId (CLAUDE.md table), then `tabs_context_mcp`; if the profile is **not connected**, ask the user to open that Chrome profile: **never open a window from the shell** (`open -a/-na "Google Chrome"`): Claude in Chrome cannot see or close it. One exception (user, 2026-10-26): when the user asks for it, an agent working in `~/dev/job-applications` opens and closes "Claude - auto-job-apply" itself with that repo's `.venv/bin/python -m common.chrome open` / `close`, which records the window and closes it (checked) |
| Open | only with `tabs_create_mcp` (or `tabs_context_mcp createIfEmpty`, which opens a new window holding your tab group): every tab you open is in your group, and you note its id |
| A tab you did not open | never close, reuse or navigate it, unless the user asked |
| End of the work (done, failed or nothing found) | `tabs_close_mcp` on **every** tab id of your group; closing the last one removes the group and its window |
| Check | call `tabs_context_mcp` (without `createIfEmpty`) for that browser: it must report no tab group. Say in your answer "tabs closed (checked)" |
| A headless Chrome you started | `terminate()` it, then check no process holds its data folder: `pgrep -f "user-data-dir=<folder>"` prints nothing |
| Keeping a tab open | only while the user must act in it; name the tab and what they must do; close it as soon as they say they are done |
| Several browsers in one session | the check above for each browser you selected |
| A script or scheduled job that must load a profile for Claude in Chrome (the extension runs only in a loaded profile) | only when a run needs it; note the window ids before and after (AppleScript `get id of every window`), close that window when the run is done (process exit; kept only while the user must act in it), check, and log one `chrome: opened…` / `closed… (checked)` line. Model: `~/dev/job-applications/common/chrome.py` (17 Oct 2026: it used to leave one window open every night) |

## The launch (Python, Playwright attached to a Chrome we start)

Working copy: `~/dev/marketplace-seller/src/engine_chrome.py` (a context manager with a busy check and screenshots). The core:

```python
import re, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright   # playwright==1.55.0, no browser download: it attaches to the Mac's Chrome
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
profile = Path.home() / "opt/<repo>/chrome"        # or tempfile.mkdtemp() for public pages
(profile / "DevToolsActivePort").unlink(missing_ok=True)
major = re.search(r"(\d+)\.", subprocess.run([CHROME, "--version"], capture_output=True, text=True).stdout).group(1)
ua = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
proc = subprocess.Popen([CHROME, "--headless", f"--user-data-dir={profile}", "--remote-debugging-port=0", "--no-first-run",
                         "--no-default-browser-check", f"--user-agent={ua}", "--lang=fr-CH", "--window-size=1440,900",
                         "--disable-blink-features=AutomationControlled", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
port_file = profile / "DevToolsActivePort"          # Chrome writes its random local port here
while not (port_file.exists() and port_file.read_text().strip()):
    time.sleep(0.25)
with sync_playwright() as p:
    page = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port_file.read_text().split()[0]}").contexts[0].pages[0]
    page.goto("https://example.com")
    page.screenshot(path="/tmp/look.png")           # look at the file, not at a window
proc.terminate(); proc.wait(30)                     # SIGTERM = a normal quit: cookies and logins stay
```

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

Windows or tabs left open anyway: skill `chrome-leftovers` finds who opened them and closes them.
