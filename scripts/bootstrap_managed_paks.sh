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

UPDATE_EXISTING=false
if [[ "${1:-}" == "--update" ]]; then
    UPDATE_EXISTING=true
fi

if [[ ! -f "$REGISTRY_FILE" ]]; then
    echo "ERROR: $REGISTRY_FILE not found" >&2
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
    exit 0
fi

echo "Found ${#URLS[@]} managed pak(s) in $REGISTRY_FILE"
echo ""

cloned=0
updated=0
skipped=0
failed=0

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    name="${PATHS[$i]}"
    target="${PAKS_DIR}/${name}"

    if [[ -d "$target/.git" ]]; then
        if $UPDATE_EXISTING; then
            echo "  Updating: $name"
            if git -C "$target" pull --quiet 2>/dev/null; then
                updated=$((updated + 1))
            else
                echo "    WARNING: git pull failed for $name" >&2
                failed=$((failed + 1))
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
        fi
    fi
done

echo ""
echo "Done: cloned=$cloned updated=$updated skipped=$skipped failed=$failed"
