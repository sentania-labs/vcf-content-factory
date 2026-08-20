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

# Record this run for the preflight doctor (contract: src/vcfops_common/doctor.py
# header). Called at EVERY exit path, including the early ones: an empty registry
# and a missing registry file are both real, reportable outcomes, and a script
# that exits without recording leaves the doctor with a delta nothing can clear.
# Replaces this script's own line rather than appending, so the file stays
# bounded at one line per script and neither script can evict the other.
write_status() {
    local c="${1:-0}" u="${2:-0}" f="${3:-0}" fl="${4:--}"
    local sf="${REPO_ROOT}/.bootstrap-status"
    local line tmp
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) bootstrap_references cloned=$c updated=$u failed=$f failures=$fl"
    tmp="${sf}.tmp"
    { grep -v " bootstrap_references " "$sf" 2>/dev/null || true; echo "$line"; } > "$tmp" 2>/dev/null \
      && mv "$tmp" "$sf" 2>/dev/null || true
}

UPDATE_EXISTING=false
if [[ "${1:-}" == "--update" ]]; then
    UPDATE_EXISTING=true
fi

if [[ ! -f "$SOURCES_FILE" ]]; then
    echo "ERROR: $SOURCES_FILE not found" >&2
    write_status 0 0 1 "registry-file-missing"
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
    write_status 0 0 0 -
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

fl="-"
[[ ${#failures[@]} -gt 0 ]] && fl="$(IFS=,; echo "${failures[*]}")"
write_status "$cloned" "$updated" "$failed" "$fl"
