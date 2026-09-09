#!/usr/bin/env bash
# repo_state.sh — shared repo-state detection for the bootstrap scripts.
#
# Design of record: knowledge/designs/bootstrap-update-and-report-v1.md.
#
# One rule for reference clones, managed pak clones and the factory
# itself: update only what is clean and behind, report everything else
# rather than touching it. This is the rule the factory already applied
# to itself ("never auto-pull, never touch a dirty tree", CLAUDE.md
# first-run concierge); these helpers extend it to the other repos.
#
# Sourced, not executed. Callers run under `set -euo pipefail`, so every
# git call here is guarded: a state probe must never abort a session hook.

# repo_state <dir> -> one of
#   not-a-repo
#   no-upstream
#   dirty
#   diverged:<ahead>:<behind>
#   ahead:<n>
#   behind:<n>
#   current
#
# Reports dirty ahead of everything else: uncommitted work is the state
# most likely to be destroyed by a well-meaning pull, so it wins the
# report even when the branch is also behind.
repo_state() {
    local dir="$1" porcelain counts ahead behind
    git -C "$dir" rev-parse --git-dir >/dev/null 2>&1 || { echo "not-a-repo"; return 0; }

    porcelain="$(git -C "$dir" status --porcelain 2>/dev/null)" || porcelain=""
    if [ -n "$porcelain" ]; then echo "dirty"; return 0; fi

    git -C "$dir" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1 || { echo "no-upstream"; return 0; }

    # left = ahead of upstream, right = behind upstream
    counts="$(git -C "$dir" rev-list --left-right --count 'HEAD...@{u}' 2>/dev/null)" || counts=""
    [ -n "$counts" ] || { echo "no-upstream"; return 0; }
    ahead="${counts%%[[:space:]]*}"
    behind="${counts##*[[:space:]]}"
    [ -n "$ahead" ] || ahead=0
    [ -n "$behind" ] || behind=0

    if [ "$ahead" -gt 0 ] && [ "$behind" -gt 0 ]; then echo "diverged:${ahead}:${behind}"
    elif [ "$ahead" -gt 0 ]; then echo "ahead:${ahead}"
    elif [ "$behind" -gt 0 ]; then echo "behind:${behind}"
    else echo "current"
    fi
}

# repo_fetch <dir> -> 0 on success, 1 on failure (never aborts the caller).
# Without a fetch, "behind" cannot be known; a failure here is reported as
# "not checked" rather than silently rendered as current.
repo_fetch() {
    git -C "$1" fetch --quiet --prune 2>/dev/null || return 1
}

# repo_ff_pull <dir> -> 0 on success, 1 on failure.
# --ff-only so a background session hook can never create a merge commit
# the user did not ask for.
repo_ff_pull() {
    git -C "$1" pull --quiet --ff-only 2>/dev/null || return 1
}

# throttle_due <stamp_file> <max_age_seconds> -> 0 when a refresh is due.
# Keeps the ordinary session fast: the expensive network sweep runs once a
# day, while every session still does the free local work (state probes,
# core.hooksPath). Missing or unreadable stamp = due, because not checking
# is the bug and checking twice is cheap.
throttle_due() {
    local stamp="$1" max_age="$2" now mtime
    [ -f "$stamp" ] || return 0
    now="$(date -u +%s 2>/dev/null)" || return 0
    mtime="$(date -u -r "$stamp" +%s 2>/dev/null)" || return 0
    [ $(( now - mtime )) -ge "$max_age" ]
}

# csv_or_dash <items...> -> comma-joined, or "-" when empty.
# Matches the existing `failures=-` sentinel in .bootstrap-status so the
# doctor's key=value parser needs no new empty-value case.
csv_or_dash() {
    if [ "$#" -eq 0 ]; then printf -- '-'; else local IFS=,; printf '%s' "$*"; fi
}
