# Deploy of agent-tracker v1: what this Mac must lose (a list, not run)

Written 2026-11-07 on branch `agent-tracker-v1` (agent-tracker's `IMPLEMENTATION.md`, `DESIGN.md` §7). Nothing below has been done on the live Mac. Seen on the Mac (read-only, 2026-11-07, 14:30): every path below exists unless marked otherwise.

## Order

```
1. agent-tracker installed (~/.local/bin/agent-tracker exists)      its own install.sh
2. INSTALL=true bash ~/dev/my-setup/bootstrap.sh                     rows marked "bootstrap" below happen here
3. agent-tracker check                                              "all good": statusLine chain + hooks
4. ares tmux --dry-run works (agent-resume)                         then the crash-restore leftovers go, by hand (rows 7-11)
```

`bootstrap.sh` must run **after** agent-tracker's install: the `statusLine` chain is written only when `~/.local/bin/agent-tracker` exists. A later bootstrap run without it writes the display alone back.

## my-setup

| # | Path on this Mac | What it is | Who removes it |
|---|---|---|---|
| 1 | `~/.claude/settings.json` → `statusLine.command` | today `bash $HOME/.claude/statusline-command.sh`; becomes `(agent-tracker tick 2>/dev/null \|\| cat) \| bash $HOME/.claude/statusline-command.sh` | bootstrap (`modules/claude_config.sh`) |
| 2 | `~/.local/bin/cc-map`, `~/.local/bin/cc-rc` (links) | parked commands (`parked/README.md`) | bootstrap (`RETIRED_BINS`) |
| 3 | `~/opt/my-setup/bin/cc-map`, `cc-map.bak`, `cc-rc` | their deployed copies | bootstrap (`RETIRED_BINS`) |
| 4 | `~/.claude/skills/claude-sessions-overview`, `~/.agents/skills/claude-sessions-overview` (links), `~/opt/my-setup/skills/claude-sessions-overview/` (read-only copy) | parked skill | bootstrap (`modules/agent_links.sh`: a skill gone from `skills/` loses its copy and links) |
| 5 | `~/opt/my-setup/logs/cc-rc.log` | cc-rc's log | by hand, after a look |
| 6 | `~/.tmux.conf` lines 128–138 (resurrect + continuum block) | loads the plugins | bootstrap (`files/tmux.conf` redeployed; the old one kept as `~/.tmux.conf.bak`; the live server is reloaded, which resets `status-right` and so stops continuum's 5-min save) |
| 7 | the live tmux server: key bindings prefix + Ctrl-s / Ctrl-r (resurrect) | stay until the server restarts; pressing them after step 8 only prints an error | by hand if wanted: `tmux unbind C-s; tmux unbind C-r` (the user's server: their OK first) |
| 8 | `~/opt/my-setup/tmux/plugins/` (`tmux-resurrect`, `tmux-continuum`, cloned 2026-11-07) | plugin code, no data | by hand, after step 6 |
| 9 | `~/opt/my-setup/state/tmux/resurrect/` (`last` + `tmux_resurrect_*.txt`, every 5 min since 2026-11-07 11:49) | resurrect snapshots | by hand, once `ares tmux` has restored a real crash (or a killed test tmux) |
| 10 | `~/.tmux/plugins/` (`tpm`, `tmux-resurrect`, dated 2026-08-22) | an older manual tpm install, loaded by nothing (no `~/.tmux.conf` line reads it) | by hand, after a look |
| 11 | `~/.local/state/terminal-snapshot/` (4 files: `*_restore.sh`, `latest_restore.sh`, from 2026-11-01) | output of the removed `tools/terminal_snapshot.py` (run by hand, never scheduled: no LaunchAgent, job or crontab line found) | by hand |

## agent-statusline (its own `install.sh`)

| # | Path | What it is | Who removes it |
|---|---|---|---|
| 12 | `~/opt/agent-statusline/state/heartbeat/` (`claude`, `codex`) | the old heartbeat; no longer written or read (agent-tracker's quota jobs read `last_seen.json`) | `bash uninstall.sh && bash install.sh` in agent-statusline (its `install.sh` carries no migration), or by hand |

## Not in this list

The rename agent-usage-tracker → agent-tracker (repo, `~/opt`, launchd labels, the VM, `modules/tools.sh`), agent-resume's hooks and `data/lifecycles/`, agent-notify's `/tmp` copies: each repo's own deploy notes (agent-tracker's `DESIGN.md` §9 step 1b).
