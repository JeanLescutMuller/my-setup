---
name: google-workspace
description: Google Workspace from the shell with Google's `gws` CLI - Gmail, Calendar, Drive, Docs, Sheets, Slides, Tasks and Contacts - read, search, create, update, delete. Use in Claude Code or Codex for any Google data (an email, an event, a file, a Doc or Sheet, a contact).
---

# Google Workspace with `gws`

One CLI for every Google service, already logged in on this Mac. Merged from the skills `gws generate-skills` (v0.22.5) writes (`gws-shared` + one per service): regenerating would split them again, so merge new output back into this file. Anthropic's skill of the same name (claude.ai web, through its Google connector) is hidden in Claude Code by `skillOverrides` (my-setup): this one replaces it here.

## Auth and syntax

```bash
gws auth login                                  # browser OAuth, once
gws <service> <resource> <method> --params '{…}' --json '{…}' [--format json|table|yaml|csv] [--page-all] [--dry-run]
gws <service> --help                            # services: gmail calendar drive docs sheets slides tasks people
gws schema <service>.<resource>.<method>        # required params, types - read before a first call
gws gmail users messages list --params '{"userId": "me", "q": "from:x newer_than:7d"}'
```

- `--params` = URL/query parameters, `--json` = request body; wrap both in **single** quotes.
- `--page-all` auto-paginates (NDJSON), `--page-limit N` (default 10).

## Rules

- **Confirm with the user before any write or delete**, and above all before sending an email or a calendar invite; try it with `--dry-run` first.
- Never print tokens or keys.
- Mutations for one user must be sent **one at a time** (parallel calls fail or slow down).
- Before `searchContacts` / `otherContacts.search`, send a warm-up search with an empty query, or results are stale.
- `get` / `getBatchGet` return 400 without `personFields`. `updateContact` needs `person.metadata.sources` (the etag) and an `updatePersonFields` mask; only the masked fields are replaced.

## Contacts (`people`) resources

| Resource | Methods |
|---|---|
| `people` | `get` (`people/me` = the user), `getBatchGet`, `searchContacts`, `createContact`, `updateContact`, `batchCreateContacts`, `batchUpdateContacts`, `updateContactPhoto`, `deleteContactPhoto`, `connections list` (all contacts), `listDirectoryPeople`, `searchDirectoryPeople` |
| `contactGroups` | `list`, `get`, `batchGet`, `create`, `update`, `delete`, `members modify` |
| `otherContacts` | `list`, `search` (auto-created from interactions), `copyOtherContactToMyContactsGroup` |

## Setup on this Mac (gotchas)

- `gws` = brew `googleworkspace-cli`. OAuth client in GCP project `contacts-cleanup-510610`, still in **Testing mode → re-login every 7 days**. `~/.config/gws/client_secret.json` is a symlink to `~/.config/contacts-cleanup/client_secret.json`.
- Log in with explicit scopes (contacts, contacts.other.readonly, gmail.modify, gmail.settings.basic (Gmail filters: gmail.modify alone gets 403 "insufficient authentication scopes"), calendar, drive, documents, spreadsheets, presentations, tasks); never add the Keep scope (personal accounts get `invalid_scope` and the whole login fails).
- "insufficient authentication scopes" right after a re-login = a stale `~/.config/gws/token_cache.json`: remove it.
- One config folder per account: `~/.config/gws` (jean.lescut), `~/.config/gws-contact` (contact.lescut), `~/.config/gws-jlm` (jean.lescut.muller). Log in the others with the full path, never `~`: `GOOGLE_WORKSPACE_CLI_CONFIG_DIR=/Users/jeanlescut/.config/gws-jlm gws auth login --scopes <comma-separated scope URLs>`; a plain `gws auth login` overwrites jean.lescut's login.
- "No OAuth client configured" while `client_secret.json` is there = the file has no `installed.project_id`: gws 0.22.5 ignores a client file without it. Add `"project_id": "contacts-cleanup-510610"` and keep it (2026-10-28). Never remove it again after the login: sessions on 19, 20 and 26 Oct did, and every next login failed the same way.
- gws charges every call to that `project_id`, so each account needs the role `roles/serviceusage.serviceUsageConsumer` on `contacts-cleanup-510610` (else 403 "Caller does not have required permission to use project"). The user grants it (an agent can't change IAM): `gcloud projects add-iam-policy-binding contacts-cleanup-510610 --member=user:<email> --role=roles/serviceusage.serviceUsageConsumer --condition=None`.
