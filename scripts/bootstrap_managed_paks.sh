#!/usr/bin/env bash
# bootstrap_managed_paks.sh — Clone or update independently-versioned SDK paks.
#
# Reads knowledge/context/managed_paks.md for repo remotes and target paths, clones any
# that are missing under content/sdk-adapters/, and optionally updates existing
# clones with git pull. Each target is an independent git repo that the factory
# gitignores — cloning them never dirties the factory tree.
#
# Usage:
#   scripts/bootstrap_managed_paks.sh          # clone missing, refresh on the daily throttle
#   scripts/bootstrap_managed_paks.sh --update # force the refresh sweep now
#
# Update policy (knowledge/designs/bootstrap-update-and-report-v1.md):
# fast-forward only what is clean and behind; report ahead, dirty and
# diverged clones rather than touching them. The network sweep is
# throttled to once a day so an ordinary session opens fast; the free
# local work (state probes, core.hooksPath) runs every session.
#
# core.hooksPath is set on EVERY registered clone, including ones this
# run skips. That is what makes the RULE-012 pre-push gate retrofit
# itself onto existing checkouts with no migration step.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/repo_state.sh
. "${SCRIPT_DIR}/lib/repo_state.sh"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAKS_DIR="${REPO_ROOT}/content/sdk-adapters"
REGISTRY_FILE="${REPO_ROOT}/knowledge/context/managed_paks.md"

# Record this run for the preflight doctor (contract: src/vcfops_common/doctor.py
# header). Called at EVERY exit path, including the early ones: an empty registry
# and a missing registry file are both real, reportable outcomes, and a script
# that exits without recording leaves the doctor with a delta nothing can clear.
# Replaces this script's own line rather than appending, so the file stays
# bounded at one line per script and neither script can evict the other.
# Extra key=value fields are additive: the doctor's parser is generic
# key=value (read_bootstrap_status), so old lines stay valid and new keys
# need no version bump. `-` is the empty-list sentinel, matching failures.
write_status() {
    local c="${1:-0}" u="${2:-0}" f="${3:-0}" fl="${4:--}"
    local sk="${5:-0}" ah="${6:--}" dt="${7:--}" dv="${8:--}" hk="${9:--}" ck="${10:-yes}"
    local sf="${REPO_ROOT}/.bootstrap-status"
    local line tmp
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) bootstrap_managed_paks cloned=$c updated=$u failed=$f failures=$fl skipped=$sk ahead=$ah dirty=$dt diverged=$dv hooks=$hk checked=$ck"
    RECORDED=true
    tmp="${sf}.tmp"
    { grep -v " bootstrap_managed_paks " "$sf" 2>/dev/null || true; echo "$line"; } > "$tmp" 2>/dev/null \
      && mv "$tmp" "$sf" 2>/dev/null || true
}

# A run killed part-way (the SessionStart `timeout`, Ctrl-C) used to write
# nothing at all, leaving the PREVIOUS run's line in place for the doctor to
# replay in present tense as this session's work: reports-green-while-broken,
# the exact failure mode knowledge/designs/bootstrap-update-and-report-v1.md
# names. Record the truncation instead, so the doctor can say it could not
# check rather than repeating what a different run once did.
RECORDED=false
on_abort() {
    # Fires for TERM and again for EXIT; only the first firing may write.
    # `if` rather than `$RECORDED && ...` because a false short-circuit is a
    # non-zero status, which `set -e` treats as fatal inside a trap handler.
    if $RECORDED; then return 0; fi
    trap - EXIT TERM INT
    write_status "${cloned:-0}" "${updated:-0}" "${failed:-0}" "interrupted" \
        "${skipped:-0}" - - - - "no"
    # Exit, do not return. Returning ABSORBS the delivered signal: the script
    # would run on past its `timeout`, and its normal end-of-run write would
    # overwrite the interrupted record with a clean one, which is the very
    # replay this trap exists to prevent. 143 = 128 + SIGTERM.
    exit 143
}
trap on_abort EXIT TERM INT

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
ahead_list=()
dirty_list=()
diverged_list=()
hooks_list=()

HOOKS_DIR="${REPO_ROOT}/.githooks"
THROTTLE_STAMP="${REPO_ROOT}/.bootstrap-status.throttle"
THROTTLE_SECONDS=86400   # once a day; --update forces it

if $UPDATE_EXISTING || throttle_due "$THROTTLE_STAMP" "$THROTTLE_SECONDS"; then
    REFRESH=true
else
    REFRESH=false
fi
checked="yes"
$REFRESH || checked="throttled"

# Point a clone at the factory's one tracked hooks directory. Absolute,
# because relative core.hooksPath resolution has historically differed on
# what it resolves against. Idempotent and network-free, so it runs for
# every registered pak whether or not this run refreshed it.
install_hooks() {
    local target="$1" name="$2" current=""
    [ -d "$HOOKS_DIR" ] || return 0
    current="$(git -C "$target" config --local --get core.hooksPath 2>/dev/null)" || current=""
    [ "$current" = "$HOOKS_DIR" ] && return 0
    if git -C "$target" config --local core.hooksPath "$HOOKS_DIR" 2>/dev/null; then
        hooks_list+=("$name")
    fi
}

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    name="${PATHS[$i]}"
    target="${PAKS_DIR}/${name}"

    # A clone killed partway (hook timeout, Ctrl-C) can leave a directory
    # containing a .git that git itself rejects; a bare -d test would call
    # that "Exists" forever and never repair it (issue #91).
    if git -C "$target" rev-parse --git-dir >/dev/null 2>&1; then
        install_hooks "$target" "$name"

        if ! $REFRESH; then
            echo "  Exists:   $name (refresh throttled; --update to force)"
            skipped=$((skipped + 1))
            continue
        fi

        if ! repo_fetch "$target"; then
            echo "    WARNING: git fetch failed for $name (not checked)" >&2
            skipped=$((skipped + 1))
            checked="no"
            continue
        fi

        case "$(repo_state "$target")" in
            behind:*)
                echo "  Updating: $name"
                if repo_ff_pull "$target"; then
                    updated=$((updated + 1))
                else
                    echo "    WARNING: fast-forward pull failed for $name" >&2
                    failed=$((failed + 1))
                    failures+=("${name}")
                fi
                ;;
            ahead:*)
                st="$(repo_state "$target")"
                echo "  Ahead:    $name (${st#ahead:} local commit(s); not updated)"
                ahead_list+=("${name}:${st#ahead:}")
                skipped=$((skipped + 1))
                ;;
            diverged:*)
                st="$(repo_state "$target")"; st="${st#diverged:}"
                echo "  Diverged: $name (${st%%:*} ahead, ${st##*:} behind; not updated)"
                diverged_list+=("${name}:${st}")
                skipped=$((skipped + 1))
                ;;
            dirty)
                echo "  Dirty:    $name (uncommitted changes; not updated)"
                dirty_list+=("${name}")
                skipped=$((skipped + 1))
                ;;
            *)
                echo "  Current:  $name"
                skipped=$((skipped + 1))
                ;;
        esac
    else
        echo "  Cloning:  $name <- $url"
        if git clone --quiet "$url" "$target" 2>/dev/null; then
            cloned=$((cloned + 1))
            install_hooks "$target" "$name"
        else
            echo "    WARNING: git clone failed for $name" >&2
            failed=$((failed + 1))
            failures+=("${name}")
        fi
    fi
done

# Stamp only a sweep that actually reached the network, so a firewalled
# session retries next time instead of going quiet for a day.
if $REFRESH && [ "$checked" = "yes" ]; then
    : > "$THROTTLE_STAMP" 2>/dev/null || true
fi

echo ""
echo "Done: cloned=$cloned updated=$updated skipped=$skipped failed=$failed checked=$checked"

fl="$(csv_or_dash "${failures[@]+"${failures[@]}"}")"
write_status "$cloned" "$updated" "$failed" "$fl" "$skipped" \
    "$(csv_or_dash "${ahead_list[@]+"${ahead_list[@]}"}")" \
    "$(csv_or_dash "${dirty_list[@]+"${dirty_list[@]}"}")" \
    "$(csv_or_dash "${diverged_list[@]+"${diverged_list[@]}"}")" \
    "$(csv_or_dash "${hooks_list[@]+"${hooks_list[@]}"}")" \
    "$checked"
