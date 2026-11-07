# MacBook: sudden shutdowns ("everything was closed")

The MacBook (M2 Pro, macOS 26.6.2, FileVault on) sometimes switches itself off with no warning: every app is gone, Claude Remote Control is down, and the Mac waits at the FileVault password screen. It happened at least twice; the cause is **not found yet**. Next time it happens: add a row to "Cases", run "How to investigate", then compare.

## Cases

| # | Date | Where the user was | System log stops dead | Boot record (`Boot faults`) | Then | Dell S2722QC on USB-C? | Found by |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-13 (Mon) | in the kitchen; Mac busy (Shotcut export, Claude sessions) | 11:44:09 | `btn_rst, finger_reset force_off` | restarted by itself 11:44:55, off again 11:47:09, user turned it on 12:20 | unknown | Claude session `1449f335-82cd-4d1b-8229-b1c027a18b59` (`~/.claude/projects/-Users-jeanlescut/`) |
| 2 | 2026-11-07 (Sat) | asleep; Mac idle, asleep on battery 94 → 93 % all night | 11:12:16.8, mid-line | `btn_rst, finger_reset force_off`; `Boot failure count: 1` | restarted by itself 11:13:02, waited at the FileVault screen until 11:31 | yes (2 displays; USB-C "plug" woke the Mac at 11:02) | Claude session `cbf1952e-21d4-41ec-af21-d33f8a96cbba` |

Case 2, minute by minute:

```
07:55 … 11:02  asleep on battery, normal short wakes every ~15 min
11:02:03       USB-C "plug" + lid sensor → Mac wakes, battery → AC, 2 displays
11:02:11       last keyboard / mouse input (nobody at the Mac, user says)
11:12:11       10 min idle → screen saver + lock; USB-C port changes state (11:12:12)
11:12:16.8     last line in the system log, mid-activity: no shutdown, no panic, no button event
11:13:02       Mac starts again by itself → FileVault password screen
11:31:20       password typed → macOS loads
```

## What is known

| Possible cause | Status | Evidence |
|---|---|---|
| battery empty | ruled out | 93 % (case 2) |
| kernel panic, watchdog | ruled out | no panic report; boot record names no watchdog |
| macOS update, scheduled restart | ruled out | no restart request in the log |
| someone held the power button ~10 s | **unlikely** (both earlier sessions said "power button": that was wrong) | nobody at the Mac either time (user, 2026-11-07); no button press seen by macOS before the cut; a real long press leaves the Mac off, but it restarted by itself both times |
| hardware-level power cut or reset that the boot record labels `btn_rst … force_off` | **leading guess** | log cut mid-line; automatic restart; Apple does not document the code, so it is not proof of a finger |
| Dell S2722QC's USB-C (power + video + USB on one cable) | **suspect, not confirmed** | case 2: a USB-C event woke the Mac 10 min before, the port changed state 5 s before the cut; case 1: not checked |

Not a clue: `sh`/`bash … triggered unnest of … DYLD shared region` lines appear just before both cuts, but 40–50 a minute all the time (status-line scripts).

## How to investigate (next time)

Read-only, no sudo. `log` must be `/usr/bin/log` (zsh has its own `log`). Put big outputs in the session's scratchpad and grep them.

```
uptime; sysctl kern.boottime; last reboot | head -5; last shutdown | head -5
ls -lt /Library/Logs/DiagnosticReports/ | head          # ResetCounter-*.diag, *panic*, forceReset*
grep -E 'Date|Boot faults|Boot failure' /Library/Logs/DiagnosticReports/ResetCounter-*.diag
pmset -g log | grep -E 'Sleep  |DarkWake|Wake  |USB-C|Using (AC|BATT)' | tail -30
pmset -g log | grep AppleM68Buttons | grep Created     # real power-button presses (the "Summary" lines repeat every 15 min, ignore them)
/usr/bin/log show --start '<date> <hh:mm>' --end '<date> <hh:mm>' --style compact > <scratchpad>/cut.log
tail -3 <scratchpad>/cut.log                             # the exact moment the log stops
grep -E 'IOAccessoryManager|Port-USB-C|clamshell|LWScreenLock' <scratchpad>/cut.log | tail
system_profiler SPDisplaysDataType | grep -E 'Online|DELL'
```

Questions to answer for the new row: was the Dell plugged in? on battery or AC? what happened in the 10 s before the log stopped (USB-C, display, screen saver)? did the Mac restart by itself?

## Next steps (after the cause is confirmed, user, 2026-11-07)

1. The user watches whether the next cut happens with the Dell plugged in.
2. If it does: a few nights with the Dell unplugged, charging from the Apple charger.
3. Dell firmware update; another USB-C cable.
4. Apple Diagnostics: shut down, hold the power button until "Loading startup options", then ⌘D.

Offered, not done: a background logger of the USB-C, charger and display state every few seconds, to see what changed right before the next cut.
