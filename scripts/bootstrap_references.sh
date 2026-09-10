#!/usr/bin/env bash
# bootstrap_references.sh — Clone or update allowlisted reference repos.
#
# Reads knowledge/context/reference_sources.md for repo URLs and local paths,
# clones any that are missing under reference/references/, and
# optionally updates existing clones with git pull.
#
# Usage:
#   scripts/bootstrap_references.sh          # clone missing only
#   scripts/bootstrap_references.sh --update # force the refresh sweep now
#
# Update policy (knowledge/designs/bootstrap-update-and-report-v1.md):
# fast-forward only what is clean and behind; report ahead, dirty and
# diverged clones rather than touching them. References are read-only
# vendor material, but a user may still have local edits or a pinned
# checkout, and losing those to a background hook is exactly the failure
# this policy exists to prevent. The sweep is throttled to once a day.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/repo_state.sh
. "${SCRIPT_DIR}/lib/repo_state.sh"

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
    local sk="${5:-0}" ah="${6:--}" dt="${7:--}" dv="${8:--}" ck="${9:-yes}" un="${10:--}"
    local sf="${REPO_ROOT}/.bootstrap-status"
    local line tmp
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) bootstrap_references cloned=$c updated=$u failed=$f failures=$fl skipped=$sk ahead=$ah dirty=$dt diverged=$dv checked=$ck unknown=$un"
    RECORDED=true
    tmp="${sf}.tmp"
    { grep -v " bootstrap_references " "$sf" 2>/dev/null || true; echo "$line"; } > "$tmp" 2>/dev/null \
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
    # references write_status has no hooks field: 9 args, not 10.
    write_status "${cloned:-0}" "${updated:-0}" "${failed:-0}" "interrupted" \
        "${skipped:-0}" - - - "no"
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

THROTTLE_STAMP="${REPO_ROOT}/.bootstrap-status.refs-throttle"
THROTTLE_SECONDS=86400

if $UPDATE_EXISTING || throttle_due "$THROTTLE_STAMP" "$THROTTLE_SECONDS"; then
    REFRESH=true
else
    REFRESH=false
fi
checked="yes"
$REFRESH || checked="throttled"

ahead_list=()
dirty_list=()
diverged_list=()
unknown_list=()

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    slug="${PATHS[$i]}"
    target="${REFERENCES_DIR}/${slug}"

    # A clone killed partway (hook timeout, Ctrl-C) can leave a directory
    # containing a .git that git itself rejects; a bare -d test would call
    # that "Exists" forever and never repair it (issue #91).
    if git -C "$target" rev-parse --git-dir >/dev/null 2>&1; then
        if ! $REFRESH; then
            echo "  Exists:   $slug (refresh throttled; --update to force)"
            skipped=$((skipped + 1))
            continue
        fi

        if ! repo_fetch "$target"; then
            echo "    WARNING: git fetch failed for $slug (not checked)" >&2
            skipped=$((skipped + 1))
            checked="no"
            continue
        fi

        case "$(repo_state "$target")" in
            behind:*)
                echo "  Updating: $slug"
                if repo_ff_pull "$target"; then
                    updated=$((updated + 1))
                else
                    echo "    WARNING: fast-forward pull failed for $slug" >&2
                    failed=$((failed + 1))
                    failures+=("${slug}")
                fi
                ;;
            ahead:*)
                st="$(repo_state "$target")"
                echo "  Ahead:    $slug (${st#ahead:} local commit(s); not updated)"
                ahead_list+=("${slug}:${st#ahead:}")
                skipped=$((skipped + 1))
                ;;
            diverged:*)
                st="$(repo_state "$target")"; st="${st#diverged:}"
                echo "  Diverged: $slug (${st%%:*} ahead, ${st##*:} behind; not updated)"
                diverged_list+=("${slug}:${st}")
                skipped=$((skipped + 1))
                ;;
            dirty)
                echo "  Dirty:    $slug (local changes; not updated)"
                dirty_list+=("${slug}")
                skipped=$((skipped + 1))
                ;;
            no-upstream)
                # A detached (pinned) checkout or a branch with no tracking
                # ref: behind-ness cannot be known, so it is reported as
                # unknown rather than rendered as current.
                echo "  Unknown:  $slug (no upstream tracking; alignment not checked)"
                unknown_list+=("${slug}")
                skipped=$((skipped + 1))
                ;;
            current)
                echo "  Current:  $slug"
                skipped=$((skipped + 1))
                ;;
            *)
                echo "  Unknown:  $slug (unrecognised repo state; not updated)"
                unknown_list+=("${slug}")
                skipped=$((skipped + 1))
                ;;
        esac
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
    "$checked" \
    "$(csv_or_dash "${unknown_list[@]+"${unknown_list[@]}"}")"
