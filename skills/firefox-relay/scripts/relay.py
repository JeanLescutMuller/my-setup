#!/usr/bin/env python3
"""Firefox Relay masks (…@mozmail.com) through Relay's REST API: list, create, tag, delete.

Reads the API key from ~/.config/firefox-relay/secrets.env (RELAY_API_KEY=...). Writes nothing locally.
Usage (see ../SKILL.md):
  relay.py list
  relay.py create "<label>" <tag> [<site>]        tag: temporary | keep | until YYYY-MM-DD
  relay.py tag <address> <tag>
  relay.py delete <address>
  relay.py delete-oldest-temporary [--yes]        without --yes: only says which one it would delete
"""
import json, re, sys, urllib.request
from datetime import date
from pathlib import Path

URL = "https://relay.firefox.com/api/v1/relayaddresses/"
SEP = " · "  # between the label and the tag, in Relay's own "description" field
key = re.search(r"RELAY_API_KEY=(\S+)", (Path.home() / ".config/firefox-relay/secrets.env").read_text()).group(1)


def call(url, method="GET", body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Token {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or "null")  # DELETE answers 204 with no body


def check_tag(tag):
    if tag in ("temporary", "keep") or re.fullmatch(r"until \d{4}-\d{2}-\d{2}", tag):
        return tag
    sys.exit(f"bad tag {tag!r}: temporary | keep | 'until YYYY-MM-DD'")


def masks():
    # Oldest first, with the tag split off the label ("" when the mask has none)
    l_masks = sorted(call(URL), key=lambda m: m["created_at"])
    for m in l_masks:
        label, _, tag = (m["description"] or "").rpartition(SEP)
        m["label"], m["tag"] = (label, tag) if label else (m["description"] or "", "")
    return l_masks


def find(address):
    return next((m for m in masks() if m["full_address"] == address), None) or sys.exit(f"no mask {address}")


cmd, l_args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("list", [])
if cmd == "list":
    l_masks = masks()
    limit = call("https://relay.firefox.com/api/v1/runtime_data/")["MAX_NUM_FREE_ALIASES"]
    print(f"{len(l_masks)} masks, limit {limit} (free plan)")
    print("created     | address                   | tag              | fwd | last used  | label")
    for m in l_masks:
        expired = m["tag"].startswith("until ") and m["tag"][6:] < date.today().isoformat()
        print(f"{m['created_at'][:10]}  | {m['full_address']:25} | {(m['tag'] or '(none)') + (' EXPIRED' if expired else ''):16} "
              f"| {m['num_forwarded']:3} | {(m['last_used_at'] or '-')[:10]:10} | {m['label']}")
elif cmd == "create" and len(l_args) in (2, 3):
    label, tag = l_args[0], check_tag(l_args[1])
    m = call(URL, "POST", {"enabled": True, "description": label + SEP + tag, "generated_for": l_args[2] if len(l_args) == 3 else ""})
    print(m["full_address"], "|", m["description"])
elif cmd == "tag" and len(l_args) == 2:
    m = find(l_args[0])
    m = call(f"{URL}{m['id']}/", "PATCH", {"description": m["label"] + SEP + check_tag(l_args[1])})
    print(m["full_address"], "|", m["description"])
elif cmd == "delete" and len(l_args) == 1:
    m = find(l_args[0])
    call(f"{URL}{m['id']}/", "DELETE")
    print("deleted", m["full_address"], "|", m["description"], "| created", m["created_at"][:10])
elif cmd == "delete-oldest-temporary":
    m = next((m for m in masks() if m["tag"] == "temporary"), None) or sys.exit("no temporary mask: ask the user")
    if "--yes" in l_args:
        call(f"{URL}{m['id']}/", "DELETE")
    print("deleted" if "--yes" in l_args else "would delete", m["full_address"], "|", m["description"], "| created", m["created_at"][:10])
else:
    sys.exit(__doc__)
