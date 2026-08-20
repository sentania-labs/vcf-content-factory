#!/usr/bin/env bash
# bootstrap_managed_paks.sh — Clone or update independently-versioned SDK paks.
#
# Reads knowledge/context/managed_paks.md for repo remotes and target paths, clones any
# that are missing under content/sdk-adapters/, and optionally updates existing
# clones with git pull. Each target is an independent git repo that the factory
# gitignores — cloning them never dirties the factory tree.
#
# Usage:
#   scripts/bootstrap_managed_paks.sh          # clone missing only
#   scripts/bootstrap_managed_paks.sh --update # also git pull existing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAKS_DIR="${REPO_ROOT}/content/sdk-adapters"
REGISTRY_FILE="${REPO_ROOT}/knowledge/context/managed_paks.md"

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
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) bootstrap_managed_paks cloned=$c updated=$u failed=$f failures=$fl"
    tmp="${sf}.tmp"
    { grep -v " bootstrap_managed_paks " "$sf" 2>/dev/null || true; echo "$line"; } > "$tmp" 2>/dev/null \
      && mv "$tmp" "$sf" 2>/dev/null || true
}

UPDATE_EXISTING=false
if [[ "${1:-}" == "--update" ]]; then
    UPDATE_EXISTING=true
fi

if [[ ! -f "$REGISTRY_FILE" ]]; then
    echo "ERROR: $REGISTRY_FILE not found" >&2
    write_status 0 0 1 "registry-file-missing"
    exit 1
fi

mkdir -p "$PAKS_DIR"

# Parse remote + target pairs from the registry markdown.
# Format:
#   - **Remote:** https://github.com/<owner>/<repo>
#   - **Target:** `content/sdk-adapters/<name>/`
# Lines inside HTML comments (the entry template) are skipped.
declare -a URLS=()
declare -a PATHS=()

current_url=""
in_comment=false
while IFS= read -r line; do
    # Skip the documentation/template block enclosed in <!-- ... -->
    if [[ "$line" == *"<!--"* ]]; then
        in_comment=true
    fi
    if $in_comment; then
        if [[ "$line" == *"-->"* ]]; then
            in_comment=false
        fi
        continue
    fi

    if [[ "$line" =~ \*\*Remote:\*\*[[:space:]]+(https://[^[:space:]]+) ]]; then
        current_url="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ \*\*Target:\*\*[[:space:]]+\`content/sdk-adapters/([^/\`]+)/?\` ]]; then
        if [[ -n "$current_url" ]]; then
            URLS+=("$current_url")
            PATHS+=("${BASH_REMATCH[1]}")
            current_url=""
        fi
    fi
done < "$REGISTRY_FILE"

if [[ ${#URLS[@]} -eq 0 ]]; then
    echo "No managed paks registered in $REGISTRY_FILE"
    write_status 0 0 0 -
    exit 0
fi

echo "Found ${#URLS[@]} managed pak(s) in $REGISTRY_FILE"
echo ""

cloned=0
updated=0
skipped=0
failed=0
failures=()

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    name="${PATHS[$i]}"
    target="${PAKS_DIR}/${name}"

    # A clone killed partway (hook timeout, Ctrl-C) can leave a directory
    # containing a .git that git itself rejects; a bare -d test would call
    # that "Exists" forever and never repair it (issue #91).
    if git -C "$target" rev-parse --git-dir >/dev/null 2>&1; then
        if $UPDATE_EXISTING; then
            echo "  Updating: $name"
            if git -C "$target" pull --quiet 2>/dev/null; then
                updated=$((updated + 1))
            else
                echo "    WARNING: git pull failed for $name" >&2
                failed=$((failed + 1))
                failures+=("${name}")
            fi
        else
            echo "  Exists:   $name (use --update to pull)"
            skipped=$((skipped + 1))
        fi
    else
        echo "  Cloning:  $name <- $url"
        if git clone --quiet "$url" "$target" 2>/dev/null; then
            cloned=$((cloned + 1))
        else
            echo "    WARNING: git clone failed for $name" >&2
            failed=$((failed + 1))
            failures+=("${name}")
        fi
    fi
done

echo ""
echo "Done: cloned=$cloned updated=$updated skipped=$skipped failed=$failed"

fl="-"
[[ ${#failures[@]} -gt 0 ]] && fl="$(IFS=,; echo "${failures[*]}")"
write_status "$cloned" "$updated" "$failed" "$fl"
