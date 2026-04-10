#!/usr/bin/env bash
# bootstrap_references.sh — Clone or update allowlisted reference repos.
#
# Reads context/reference_sources.md for repo URLs and local paths,
# clones any that are missing under references/, and optionally
# updates existing clones with git pull.
#
# Usage:
#   scripts/bootstrap_references.sh          # clone missing only
#   scripts/bootstrap_references.sh --update # also git pull existing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REFERENCES_DIR="${REPO_ROOT}/references"
SOURCES_FILE="${REPO_ROOT}/context/reference_sources.md"

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
#   - **Local path:** `references/<slug>/`
declare -a URLS=()
declare -a PATHS=()

current_url=""
while IFS= read -r line; do
    if [[ "$line" =~ \*\*URL:\*\*[[:space:]]+(https://[^[:space:]]+) ]]; then
        current_url="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ \*\*Local\ path:\*\*[[:space:]]+\`references/([^/\`]+)/?\` ]]; then
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

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    slug="${PATHS[$i]}"
    target="${REFERENCES_DIR}/${slug}"

    if [[ -d "$target/.git" ]]; then
        if $UPDATE_EXISTING; then
            echo "  Updating: $slug"
            if git -C "$target" pull --quiet 2>/dev/null; then
                ((updated++))
            else
                echo "    WARNING: git pull failed for $slug" >&2
                ((failed++))
            fi
        else
            echo "  Exists:   $slug (use --update to pull)"
            ((skipped++))
        fi
    else
        echo "  Cloning:  $slug <- $url"
        if git clone --quiet "$url" "$target" 2>/dev/null; then
            ((cloned++))
        else
            echo "    WARNING: git clone failed for $slug" >&2
            ((failed++))
        fi
    fi
done

echo ""
echo "Done: cloned=$cloned updated=$updated skipped=$skipped failed=$failed"
