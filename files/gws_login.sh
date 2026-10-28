#!/bin/bash
# gws-login: log one Google account in to gws (the Google Workspace CLI), saying first which account to click.
# gws opens a Google page that lists several accounts: the user must pick the one this login is for (user, 2026-10-28).
# After the login it checks the account really logged in (Gmail profile) and says so.
# Usage: gws-login [jean.lescut | contact.lescut | jean.lescut.muller]    (default: jean.lescut)
# Writes: the token in that account's gws config folder (skill google-workspace, "Setup on this Mac").
set -euo pipefail

account="${1:-jean.lescut}"
case "$account" in
    jean.lescut)        dir="$HOME/.config/gws" ;;
    contact.lescut)     dir="$HOME/.config/gws-contact" ;;
    jean.lescut.muller) dir="$HOME/.config/gws-jlm" ;;
    *) echo "unknown account: $account (jean.lescut, contact.lescut or jean.lescut.muller)" >&2; exit 2 ;;
esac
email="$account@gmail.com"

# gws 0.22.5 ignores a client file without installed.project_id (skill google-workspace): stop before a useless login
if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["installed"].get("project_id") else 1)' "$dir/client_secret.json" 2>/dev/null; then
    echo "$dir/client_secret.json has no installed.project_id: see skill google-workspace before logging in" >&2
    exit 1
fi

scopes=$(printf 'https://www.googleapis.com/auth/%s,' contacts contacts.other.readonly gmail.modify gmail.settings.basic \
    calendar drive documents spreadsheets presentations tasks)

cat <<EOF

  ┌─────────────────────────────────────────────────────────────┐
     In the Google page that opens, choose this account:

         >>>  $email  <<<

     not any other one, even if it is listed first.
  └─────────────────────────────────────────────────────────────┘

EOF
GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$dir" gws auth login --scopes "${scopes%,}"

got=$(GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$dir" gws gmail users getProfile --params '{"userId":"me"}' 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("emailAddress",""))' 2>/dev/null || true)
if [ "$got" = "$email" ]; then
    echo "OK: gws is logged in as $email"
else
    echo "WRONG ACCOUNT or login failed: expected $email, got '${got:-nothing}'. Run gws-login $account again and choose $email." >&2
    exit 1
fi
