#!/bin/bash
# Check a project's documentation against the documentation-writing skill.
#
# Usage: bash check_docs.sh [project-root]      (default: current directory)
# Prints one line per finding (FAIL must be fixed, WARN should be looked at),
# then a summary. Exits 1 if any FAIL. Read-only: never changes a file.
set -uo pipefail

ROOT="$(cd "${1:-.}" && pwd)" || exit 2
AGENTS_WARN_WORDS=400
AGENTS_FAIL_WORDS=600
CHAIN_WARN_WORDS=1900

n_fail=0
n_warn=0
fail() { echo "FAIL  ${1#"$ROOT"/}: $2"; n_fail=$((n_fail + 1)); }
warn() { echo "WARN  ${1#"$ROOT"/}: $2"; n_warn=$((n_warn + 1)); }

# The file list, built once. In a git repo: tracked + untracked files that
# .gitignore does not exclude (fast, and skips data folders); otherwise find,
# skipping vendored and generated trees.
ALL_FILES="$(mktemp)"
trap 'rm -f "$ALL_FILES"' EXIT
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$ROOT" ls-files -co --exclude-standard | grep -vxF -f <(git -C "$ROOT" ls-files -d) |
        awk -v r="$ROOT" '{ print r "/" $0 }' > "$ALL_FILES"
else
    find "$ROOT" \( -name .git -o -name node_modules -o -name .venv -o -name venv \
        -o -name __pycache__ -o -name .ipynb_checkpoints \) -prune -o \( -type f -o -type l \) -print > "$ALL_FILES"
fi

# Words of an AGENTS.md, not counting its "## Vocabulary" section: the
# vocabulary must never be pushed out by budget pressure.
budget_words() {
    awk '/^## /{ v = ($0 ~ /^## Vocabulary/) } !v' "$1" | wc -w | tr -d ' '
}

# Every listed file whose basename matches the regex $1.
find_named() {
    grep -E "/$1\$" "$ALL_FILES"
}

# Prints the file with fenced code blocks and HTML comments blanked out,
# keeping one output line per input line so line numbers stay true.
strip_fences() {
    awk '
        /^[[:space:]]*```/ { f = !f; print ""; next }
        f { print ""; next }
        {
            line = $0; out = ""
            while (line != "") {
                if (c) { i = index(line, "-->"); if (!i) { line = ""; break } line = substr(line, i + 3); c = 0 }
                else { i = index(line, "<!--"); if (!i) { out = out line; break } out = out substr(line, 1, i - 1); line = substr(line, i + 4); c = 1 }
            }
            print out
        }' "$1"
}

if [ ! -f "$ROOT/AGENTS.md" ]; then
    warn "$ROOT/." "no AGENTS.md at the project root"
elif ! grep -q '^## Vocabulary' "$ROOT/AGENTS.md"; then
    warn "$ROOT/AGENTS.md" "no '## Vocabulary' table — the project's words belong here"
fi

# --- AGENTS.md: budgets, README beside it ---
while IFS= read -r agents; do
    dir="$(dirname "$agents")"
    words="$(budget_words "$agents")"
    if [ "$words" -gt "$AGENTS_FAIL_WORDS" ]; then
        fail "$agents" "$words words (> $AGENTS_FAIL_WORDS): move explanations to doc/"
    elif [ "$words" -gt "$AGENTS_WARN_WORDS" ]; then
        warn "$agents" "$words words, not counting ## Vocabulary (aim ≤ $AGENTS_WARN_WORDS)"
    fi

    chain=0
    p="$dir"
    while :; do
        [ -f "$p/AGENTS.md" ] && chain=$((chain + $(budget_words "$p/AGENTS.md")))
        { [ "$p" = "$ROOT" ] || [ "$p" = "/" ]; } && break
        p="$(dirname "$p")"
    done
    [ "$chain" -gt "$CHAIN_WARN_WORDS" ] && warn "$agents" "loaded chain is $chain words (aim ≤ $CHAIN_WARN_WORDS)"

    if [ -f "$dir/README.html" ] && [ -f "$dir/README.md" ]; then
        fail "$dir/README.md" "one README per folder: fold it into README.html, then delete it"
    elif [ ! -f "$dir/README.md" ] && [ ! -f "$dir/README.html" ]; then
        warn "$dir/." "has AGENTS.md but no README.html / README.md"
    fi

    # A paired README holds entities only: no imperatives, no tunable numbers.
    if [ -f "$dir/README.md" ]; then
        while IFS= read -r hit; do
            warn "$dir/README.md" "line ${hit%%:*} looks like a rule or a tunable number (belongs in AGENTS.md)"
        done < <(strip_fences "$dir/README.md" |
            grep -nE "\b(do not|don't|must not|never edit|always run)\b|\b[0-9]+ ?(s|ms|min|%|GB|MB|bps)\b")
    fi
done < <(find_named 'AGENTS\.md')

# --- no CLAUDE.md: Claude and Codex both read AGENTS.md ---
while IFS= read -r claude; do
    if [ -L "$claude" ]; then
        warn "$claude" "remove it (git rm): Claude reads AGENTS.md directly"
    else
        fail "$claude" "a real CLAUDE.md: merge it into AGENTS.md, then git rm it"
    fi
done < <(find_named 'CLAUDE\.md')

# --- doc/ folders never hold a README ---
while IFS= read -r readme; do
    [ "$(basename "$(dirname "$readme")")" = "doc" ] &&
        fail "$readme" "a doc/ folder never holds a README.md — index it from the parent README"
done < <(find_named 'README\.md')

# --- relative Markdown links resolve (templates are skipped: their links
# are meant for the project they get copied into) ---
while IFS= read -r md; do
    case "$md" in *.template.md) continue ;; esac
    dir="$(dirname "$md")"
    while IFS=$'\t' read -r lineno target; do
        case "$target" in
            http:* | https:* | mailto:* | \#* | *'<'* | '~'*) continue ;;
        esac
        target="${target%% *}"
        target="${target%%#*}"
        [ -z "$target" ] && continue
        [ -e "$dir/$target" ] || fail "$md" "line $lineno: broken link → $target"
    done < <(strip_fences "$md" |
        awk '{ line = $0; gsub(/`[^`]*`/, "", line); while (match(line, /\]\([^)]+\)/)) { print NR "\t" substr(line, RSTART + 2, RLENGTH - 3); line = substr(line, RSTART + RLENGTH) } }')
done < <(find_named '[^/]+\.md')

echo "---"
echo "$n_fail FAIL, $n_warn WARN  ($ROOT)"
[ "$n_fail" -eq 0 ]
