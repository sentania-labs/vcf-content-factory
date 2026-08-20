#!/usr/bin/env bash
# bootstrap_references.sh — Clone or update allowlisted reference repos.
#
# Reads knowledge/context/reference_sources.md for repo URLs and local paths,
# clones any that are missing under reference/references/, and
# optionally updates existing clones with git pull.
#
# Usage:
#   scripts/bootstrap_references.sh          # clone missing only
#   scripts/bootstrap_references.sh --update # also git pull existing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REFERENCES_DIR="${REPO_ROOT}/reference/references"
SOURCES_FILE="${REPO_ROOT}/knowledge/context/reference_sources.md"

UPDATE_EXISTING=false
if [[ "${1:-}" == "--update" ]]; then
    UPDATE_EXISTING=true
fi

if [[ ! -f "$SOURCES_FILE" ]]; then
    echo "ERROR: $SOURCES_FILE not found" >&2
    exit 1
fi

mkdir -p "$REFERENCES_DIR"

# Parse URL and local path pairs from the sources file.
# Format in the markdown:
#   - **URL:** https://github.com/<owner>/<repo>
#   - **Local path:** `reference/references/<slug>/`
declare -a URLS=()
declare -a PATHS=()

current_url=""
while IFS= read -r line; do
    if [[ "$line" =~ \*\*URL:\*\*[[:space:]]+(https://[^[:space:]]+) ]]; then
        current_url="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ \*\*Local\ path:\*\*[[:space:]]+\`reference/references/([^/\`]+)/?\` ]]; then
        if [[ -n "$current_url" ]]; then
            URLS+=("$current_url")
            PATHS+=("${BASH_REMATCH[1]}")
            current_url=""
        fi
    fi
done < "$SOURCES_FILE"

if [[ ${#URLS[@]} -eq 0 ]]; then
    echo "No reference sources found in $SOURCES_FILE"
    exit 0
fi

echo "Found ${#URLS[@]} reference source(s) in $SOURCES_FILE"
echo ""

cloned=0
updated=0
skipped=0
failed=0
failures=()

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    slug="${PATHS[$i]}"
    target="${REFERENCES_DIR}/${slug}"

    if [[ -d "$target/.git" ]]; then
        if $UPDATE_EXISTING; then
            echo "  Updating: $slug"
            if git -C "$target" pull --quiet 2>/dev/null; then
                updated=$((updated + 1))
            else
                echo "    WARNING: git pull failed for $slug" >&2
                failed=$((failed + 1))
                failures+=("${slug}")
            fi
        else
            echo "  Exists:   $slug (use --update to pull)"
            skipped=$((skipped + 1))
        fi
    else
        echo "  Cloning:  $slug <- $url"
        if git clone --quiet "$url" "$target" 2>/dev/null; then
            cloned=$((cloned + 1))
        else
            echo "    WARNING: git clone failed for $slug" >&2
            failed=$((failed + 1))
            failures+=("${slug}")
        fi
    fi
done

echo ""
echo "Done: cloned=$cloned updated=$updated skipped=$skipped failed=$failed"

# Summary line for the preflight doctor (contract documented in
# src/vcfops_common/doctor.py header). Local state; gitignored.
# Each script REPLACES its own line rather than appending, so the file
# stays bounded at one line per script and neither script can ever
# evict the other's health from the doctor's view.
STATUS_FILE="${REPO_ROOT}/.bootstrap-status"
fl="-"
[[ ${#failures[@]} -gt 0 ]] && fl="$(IFS=,; echo "${failures[*]}")"
status_line="$(date -u +%Y-%m-%dT%H:%M:%SZ) bootstrap_references cloned=$cloned updated=$updated failed=$failed failures=$fl"
status_tmp="${STATUS_FILE}.tmp"
{ grep -v " bootstrap_references " "$STATUS_FILE" 2>/dev/null || true; echo "$status_line"; } > "$status_tmp" 2>/dev/null \
  && mv "$status_tmp" "$STATUS_FILE" 2>/dev/null || true
