---
name: config-ownership
description: This machine's ownership map for ~/.claude/settings.json keys, and the managed-config-block convention used across its dotfiles. Use before hand-editing ~/.claude/settings.json, or before hand-editing a block inside ~/.zshrc, ~/.bashrc, or ~/.tmux.conf.
---

## `~/.claude/settings.json` key ownership

No single tool owns this whole file — each owner manages specific keys and leaves the rest alone:

- `respondToBashCommands`, `theme`, `statusLine`, `cleanupPeriodDays`, `claudeMdExcludes`, `autoMemoryEnabled`, `skillOverrides`, `pluginConfigs`, `permissions`, `remoteControlAtStartup` — owned by `my-setup` (`modules/claude_config.sh`); `statusLine` is the chain `agent-tracker tick | bash $HOME/.claude/statusline-command.sh` when agent-tracker is installed, the display alone otherwise
- `hooks` — shared: `agent-tracker`'s own `install.sh` (`src/merge_claude_hooks.py`) owns the `SessionStart`/`SessionEnd` groups whose command contains `agent-tracker hook `; `agent-resume`'s own `install.sh` owns the `SessionStart` group `opt/agent-resume/session_start.py` and the `SessionEnd` group `opt/agent-resume/session_end.sh` (asm's `lifecycle_generation.sh` groups are gone since 2026-11-07); agent-notify's hooks come from its Claude plugin, not from this file; `my-setup` (`modules/claude_config.sh`) owns the groups whose command contains `opt/my-setup/chrome/hook.py` (the Chrome kit: PreToolUse ×2, PostToolUse, UserPromptSubmit, Stop). Each replaces only its own groups.
- `env` → `CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_LOGS_EXPORTER`, `OTEL_METRICS_EXPORTER`, `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_EXPORTER_OTLP_ENDPOINT` only — owned by `agent-tracker`'s own `install.sh` (`src/merge_claude_env.py`; was agent-usage-tracker until 2026-11-07); other `env` keys have no owner
- `enabledPlugins`, `extraKnownMarketplaces` — owned by `notify`'s own `install.sh`

Don't hand-edit a key outside the tool that owns it. Fix it in that tool's install/config script instead, so the fix survives the next bootstrap run instead of being silently overwritten.

## Managed config block convention

`~/.zshrc`, `~/.bashrc` (via `my-setup`), and `~/.tmux.conf` (via `notify`'s tmux-hook injection) each contain a box-delimited section marked `DO NOT EDIT`, carrying a `sha256:` hash of its own content in the closing marker. If that block is hand-edited, the owning tool's next managed write detects the hash mismatch, prints a diff, and aborts touching that file rather than clobbering the edit.

If a block needs to change, edit the source that generates it (`my-setup`'s `files/configure_shellrc.sh` for shell rc, `notify`'s own script for the tmux block) and let the tool redeploy it — don't hand-edit inside the block markers.
