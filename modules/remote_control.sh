#!/bin/bash
# Remote Control service: a LaunchAgent (KeepAlive) on macOS, a systemd --user service (Restart=always) on Linux:
#
#   com.jeanlescut.my-setup.remote-control  ~/opt/my-setup/remote_control.sh (from files/)
#       keeps `claude remote-control` running, so a Claude session on this machine
#       can be started from the phone at any time. The Mac must be awake.
#
# Real plist / unit in ~/opt/my-setup/, linked from ~/Library/LaunchAgents/ or ~/.config/systemd/user/.
# Linux (the VM, no ~/dev): sessions start in ~/opt, which claude must trust once: run `cd ~/opt && claude` by hand
# and accept the trust dialog (an agent may not pre-trust it); until then the service restarts once a minute and logs why.
# Log: ~/opt/my-setup/logs/remote-control.log.
# Restarted only when its script or plist changed: a restart ends every
# session open from the phone (including the one running this, if any).
# Turning /rc on in a running session is cc-rc's job (files/cc_rc.py), run by an agent.

step "remote control service"

if [ "$(uname)" = Linux ]; then
    _rc_name="com.jeanlescut.my-setup.remote-control.service"
    _rc_script="$HOME/opt/my-setup/remote_control.sh"
    _rc_unit="$HOME/opt/my-setup/$_rc_name"
    _rc_link="$HOME/.config/systemd/user/$_rc_name"
    _rc_body="[Unit]
Description=my-setup: claude remote-control, start a Claude session on this machine from the phone
After=network-online.target

[Service]
ExecStart=/bin/bash $_rc_script
Restart=always
RestartSec=60

[Install]
WantedBy=default.target"

    if diff -q "$SCRIPT_DIR/files/remote_control.sh" "$_rc_script" >/dev/null 2>&1 \
        && [ "$(cat "$_rc_unit" 2>/dev/null)" = "$_rc_body" ] \
        && [ -L "$_rc_link" ] && [ "$(readlink "$_rc_link")" = "$_rc_unit" ] \
        && systemctl --user is-enabled "$_rc_name" >/dev/null 2>&1; then
        ok "systemd service $_rc_name"
    elif [ "$INSTALL" = "false" ]; then
        skip "systemd service $_rc_name"
    else
        mkdir -p "$HOME/opt/my-setup/logs" "${_rc_link%/*}"
        cp "$SCRIPT_DIR/files/remote_control.sh" "$_rc_script"
        printf '%s\n' "$_rc_body" > "$_rc_unit"
        ln -sfn "$_rc_unit" "$_rc_link"
        loginctl enable-linger "$USER" 2>/dev/null || true
        if systemctl --user daemon-reload && systemctl --user enable "$_rc_name" >/dev/null 2>&1 \
            && systemctl --user restart "$_rc_name"; then
            installed "systemd service $_rc_name"
        else
            fail "systemd service $_rc_name: systemctl enable/restart failed"
        fi
    fi
elif [ "$(uname)" != Darwin ]; then
    ok "not macOS or Linux - skipped"
else
    _rc_label="com.jeanlescut.my-setup.remote-control"
    _rc_script="$HOME/opt/my-setup/remote_control.sh"
    _rc_plist="$HOME/opt/my-setup/$_rc_label.plist"
    _rc_link="$HOME/Library/LaunchAgents/$_rc_label.plist"
    _rc_body="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\"><dict>
  <key>Label</key><string>$_rc_label</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$_rc_script</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>60</integer>
</dict></plist>"

    if diff -q "$SCRIPT_DIR/files/remote_control.sh" "$_rc_script" >/dev/null 2>&1 \
        && [ "$(cat "$_rc_plist" 2>/dev/null)" = "$_rc_body" ] \
        && [ -L "$_rc_link" ] && [ "$(readlink "$_rc_link")" = "$_rc_plist" ] \
        && launchctl print "gui/$(id -u)/$_rc_label" >/dev/null 2>&1; then
        ok "LaunchAgent $_rc_label"
    elif [ "$INSTALL" = "false" ]; then
        skip "LaunchAgent $_rc_label"
    else
        mkdir -p "$HOME/opt/my-setup/logs" "$HOME/Library/LaunchAgents"
        cp "$SCRIPT_DIR/files/remote_control.sh" "$_rc_script"
        printf '%s\n' "$_rc_body" > "$_rc_plist"
        ln -sfn "$_rc_plist" "$_rc_link"
        launchctl bootout "gui/$(id -u)/$_rc_label" 2>/dev/null || true
        # bootout returns before claude has closed its sessions; bootstrap before then fails with EIO (5).
        for _ in $(seq 30); do launchctl print "gui/$(id -u)/$_rc_label" >/dev/null 2>&1 || break; sleep 1; done
        if launchctl bootstrap "gui/$(id -u)" "$_rc_link"; then
            installed "LaunchAgent $_rc_label"
        else
            fail "LaunchAgent $_rc_label: launchctl bootstrap failed"
        fi
    fi
fi
