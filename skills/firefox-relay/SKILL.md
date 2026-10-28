---
name: firefox-relay
description: The user's Firefox Relay email masks (…@mozmail.com addresses that forward to their real inbox) through Relay's REST API - list them with their creation date, create one for a sign-up, tag each with how long it is needed (temporary, until a date, keep), and when the free limit (50) is reached delete the oldest temporary one first. Use whenever the user or a task needs a new or throwaway email address, a mozmail / Relay mask, or asks about their masks.
---

# Firefox Relay (mozmail masks)

| Word | Means |
|---|---|
| **mask** | one `…@mozmail.com` address; mail to it is forwarded to the user's real inbox (read it with skill `google-workspace`) |
| **label** | Relay's own note on a mask (the API field `description`, "Label" in the dashboard): what it is for, then ` · ` and the tag |
| **tag** | how long the mask is needed: the table below |

## Tags (the user, 2026-10-28)

Every mask's label ends with ` · <tag>`, e.g. `Tuya IoT Developer Platform 1 · until 2027-01-28`.

| Tag | Means | When the limit is reached |
|---|---|---|
| `temporary` | made for one login or sign-up | deleted first, **oldest first** (by creation date) |
| `until YYYY-MM-DD` | needed until that date | after that date: ask the user, then retag `temporary` or delete |
| `keep` | in continuous use | never deleted |
| (none) | a mask made elsewhere (dashboard, extension) | ask the user for its tag, then add it |

## How

Free plan: **50 masks** (Mozilla raised it from 5 in May 2026; the API's `runtime_data` gives the live number, `MAX_NUM_FREE_ALIASES`). Account: the user's Mozilla account, on the free plan. API key: `~/.config/firefox-relay/secrets.env` (`RELAY_API_KEY=…`, mode 600, from relay.firefox.com/accounts/settings/); never print it, never put it in git.

```bash
R=~/.claude/skills/firefox-relay/scripts/relay.py
$R list                                                       # oldest first: created, address, tag, emails forwarded, last used, label
$R create "Tuya IoT Developer Platform 1" "until 2027-01-28" platform.tuya.com   # label, tag, site (optional)
$R tag mcgscgwkx@mozmail.com temporary                        # set or change a tag
$R delete-oldest-temporary                                    # says which one it would delete; add --yes to delete it
$R delete <address>                                           # one named mask
```

API (what the script calls): `https://relay.firefox.com/api/v1/relayaddresses/` with `Authorization: Token <key>`; GET lists, POST creates, PATCH `<id>/` changes the label, DELETE `<id>/` deletes. Each mask has `created_at`, `last_used_at`, `num_forwarded`, `generated_for` (the site).

## Rules

- **Create** a mask whenever the user asks for one, always with a label and a tag; a number when there are several for the same service (`WisprFlow 1…5`).
- **Delete** cannot be undone, and mail to a deleted mask is lost. Without asking, only one case (the user, 2026-10-28): the limit is reached and a new mask is needed → `delete-oldest-temporary --yes`, then tell the user which mask was deleted. Every other delete needs the user's OK for that mask; a `keep` mask is never deleted.
- After a create, tag or delete, `list` to check, and tell the user the address and its label.
- A repo that uses a mask for an account names the address in its own docs (which account, which service); the tag stays only in Relay.

## History

| Date | What |
|---|---|
| 2026-10-28 | API key saved; the 6 existing masks tagged with the user (WisprFlow 1–5 `keep`, Amazon Anonym `temporary`); `zzn7dcdcb@mozmail.com` created for a new Tuya IoT Developer Platform account (smart-home) |
