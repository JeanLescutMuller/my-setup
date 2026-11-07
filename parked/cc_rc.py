#!/usr/bin/env python3
"""cc-rc: turn on Remote Control (/rc) in a Claude session running in tmux on this Mac.

Usage: cc-rc <session name | session UUID or its start | tmux pane like %20>
       cc-rc --candidates   up to 4 names of sessions in tmux with Remote Control off, most recent first
Types `/rc` + Enter into the session's tmux pane, only when it is idle, its prompt box is empty
(Claude's grey suggested text aside) and Remote Control is off; otherwise prints why and types nothing.
Run by an agent, e.g. from the phone through the skill claude-sessions-overview.
Reads tmux, ~/.claude/sessions/*.json, agent-notify's state; writes ~/opt/my-setup/logs/cc-rc.log
(one line per call). Exit 0 when Remote Control is on, 1 otherwise.
"""
import getpass, glob, json, os, re, subprocess, sys, time

LOG = os.path.expanduser("~/opt/my-setup/logs/cc-rc.log")


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{int(time.time())}\t{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\t{msg}\n")


def tmux(*args):
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def sessions():
    """Live Claude sessions running in a tmux pane, most recent first."""
    out = []
    for f in glob.glob(os.path.expanduser("~/.claude/sessions/*.json")):
        try:
            d = json.load(open(f))
            os.kill(d["pid"], 0)
        except (OSError, ValueError, KeyError):
            continue
        if d.get("tmux"):
            out.append(d)
    return sorted(out, key=lambda d: -d.get("updatedAt", 0))


def pane_of(c):
    return c["tmux"].split(".")[-1]


def find(arg):
    for c in sessions():
        if arg in (c.get("name"), pane_of(c)) or (len(arg) >= 8 and c["sessionId"].startswith(arg)):
            return c
    return None


def notify_state(pane_id):
    pid = tmux("display", "-p", "-t", pane_id, "#{pane_pid}").stdout.strip()
    try:
        return dict(l.strip().split("=", 1) for l in open(f"/tmp/agent-notify-{getpass.getuser()}/{pid}/state.env") if "=" in l)
    except OSError:
        return {}


def prompt_text(pane_id):
    """What is typed in the prompt box: the text after the last '❯' on screen, without the grey (dim) text
    Claude shows in an empty box (an example, or its suggested next message). None if no prompt box is found."""
    lines = [l for l in tmux("capture-pane", "-e", "-p", "-t", pane_id).stdout.splitlines() if "❯" in l]
    if not lines:
        return None
    typed = re.sub(r"\x1b\[2m.*?(\x1b\[0m|$)", "", lines[-1].split("❯", 1)[1])
    return re.sub(r"\x1b\[[0-9;]*m", "", typed).replace("\xa0", " ").strip()


def turn_on(arg):
    """Returns (ok, message)."""
    c = find(arg)
    if not c:
        return False, f"no Claude session in tmux named {arg!r} (see cc-map)"
    pane_id, name = pane_of(c), c.get("name") or c["sessionId"][:8]
    if c.get("bridgeSessionId"):
        return True, f"{name}: Remote Control was already on"
    if c.get("status") != "idle" or notify_state(pane_id).get("AGENT_STATE") == "WaitingForUser":
        return False, f"{name} is busy or waiting for an answer: try again when it is idle"
    typed = prompt_text(pane_id)
    if typed is None or typed:
        return False, f"{name}: its prompt box is not empty ({typed!r}), so nothing was typed"
    tmux("send-keys", "-t", pane_id, "-l", "/rc")
    time.sleep(0.5)
    tmux("send-keys", "-t", pane_id, "Enter")
    for _ in range(20):
        time.sleep(0.5)
        if (find(c["sessionId"]) or {}).get("bridgeSessionId"):
            return True, f"{name}: Remote Control is on, it is now in the app's session list"
    return False, f"{name}: /rc sent, but Remote Control did not show up within 10 s"


if len(sys.argv) != 2:
    sys.exit(__doc__)
if sys.argv[1] == "--candidates":
    for c in [c for c in sessions() if not c.get("bridgeSessionId")][:4]:
        print(c.get("name") or c["sessionId"][:8])
    sys.exit(0)
ok, msg = turn_on(sys.argv[1])
log(f"{sys.argv[1]}\t{'ok' if ok else 'refused'}\t{msg}")
print(("✅ " if ok else "❌ ") + msg)
sys.exit(0 if ok else 1)
