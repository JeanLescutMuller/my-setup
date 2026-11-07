# parked/

Code kept for reference, **not deployed**: `bootstrap.sh` does not install anything from this folder, and removes what an older deploy left (the `cc-map` and `cc-rc` copies in `~/opt/my-setup/bin/` and their links in `~/.local/bin/`; the skill's copy and links, as for any skill gone from `skills/`). Parked on 2026-11-07 (agent-tracker v1, its `DESIGN.md` §10, decided by the user).

| Parked | Was | Built |
|---|---|---|
| `cc_map.py` (`cc-map`) | every tmux session and the Claude session in each pane, with agent-notify's icon and 📱 where Remote Control is on | 2026-10-17 |
| `cc_rc.py` (`cc-rc`) | turned Remote Control on in one running Claude session, by typing `/rc` into its tmux pane when idle; log `~/opt/my-setup/logs/cc-rc.log` | 2026-10-17 |
| `claude-sessions-overview/` (skill) | from the phone: print `cc-map`, offer the sessions as buttons, run `cc-rc` on the ones picked | 2026-10-17 |

**Why parked:** they existed to turn /rc on one Claude session at a time from the phone. Since 2026-10-22 (commit `ae5a3ae`, `remoteControlAtStartup = true` in `files/claude_settings.json`, written by `modules/claude_config.sh`) every interactive Claude session turns Remote Control on by itself and shows in the Claude app's Code tab: nothing is left to turn on. Seeing what runs where is now agent-tracker's `agent-tracker now`.

**To bring one back:** move it to `files/` (or the skill to `skills/`), add `cc_map.py:cc-map` / `cc_rc.py:cc-rc` back to `OWN_BINS` in `bootstrap.sh` and take it out of `RETIRED_BINS`. `cc_rc.py` reads `~/.claude/sessions/*.json` and agent-notify's state directly; a revived version should read agent-tracker's `data/sessions/` instead.
