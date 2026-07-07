#!/usr/bin/env bash
# immutability_guard.sh — RULE-010 generalization, pre-commit shape.
#
# Spec: memory/environment/TODO-top-level-reorg.md "New HOOKS" §2;
# durable-output map: STRUCTURE.md's authorship x mutability grid — docs/
# and references/ are "vendor / third-party, immutable (never edit;
# RULE-010)". This script hardens that boundary at commit time: it does
# NOT relax RULE-010, it enforces it mechanically.
#
# Refuses MODIFICATIONS or DELETIONS (not additions) of tracked files
# under docs/ and references/. New files landing under those paths
# (fresh vendor extracts, newly-bootstrapped reference repos force-added,
# etc.) are allowed — only touching or removing what's already there is
# blocked.
#
# This script does not (yet) run automatically as a git hook — see
# CLAUDE.md RULE-010/RULE-013 and the reorg TODO's "New HOOKS" section
# for how it will be wired into .git/hooks/pre-commit. Until then,
# invoke it by hand or from CI.
#
# Usage:
#   scripts/immutability_guard.sh                  # git diff --cached (staged)
#   scripts/immutability_guard.sh REF1 REF2         # git diff REF1 REF2
#   scripts/immutability_guard.sh --range REF1..REF2
#
# Options:
#   --range <ref1>..<ref2>   diff a ref range instead of the staged index.
#   -h, --help                show this help and exit.
#
# Exit codes:
#   0   no modifications/deletions under docs/ or references/.
#   1   usage error.
#   2   at least one offending path found — refused.

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
}

IMMUTABLE_DIRS=("docs/" "references/")

RANGE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --range)
      RANGE="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    --)
      shift; break ;;
    -*)
      echo "${SCRIPT_NAME}: unknown option: $1" >&2
      usage >&2
      exit 1 ;;
    *)
      break ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "${SCRIPT_NAME}: not inside a git repository." >&2
  exit 1
}
cd "${REPO_ROOT}"

if [[ -n "${RANGE}" ]]; then
  DIFF_OUTPUT="$(git diff --name-status "${RANGE}")"
elif [[ $# -eq 2 ]]; then
  DIFF_OUTPUT="$(git diff --name-status "$1" "$2")"
elif [[ $# -eq 0 ]]; then
  DIFF_OUTPUT="$(git diff --cached --name-status)"
else
  echo "${SCRIPT_NAME}: expected 0 or 2 positional refs, or --range REF1..REF2." >&2
  usage >&2
  exit 1
fi

if [[ -z "${DIFF_OUTPUT}" ]]; then
  echo "${SCRIPT_NAME}: no changes to check."
  exit 0
fi

under_immutable() {
  local p="$1"
  local d
  for d in "${IMMUTABLE_DIRS[@]}"; do
    [[ "${p}" == "${d}"* ]] && return 0
  done
  return 1
}

declare -a OFFENDERS=()

while IFS=$'\t' read -r status path path2; do
  [[ -z "${status}" ]] && continue

  # Renames/copies are reported as "R100\told\tnew" (tab-separated old/new).
  code="${status:0:1}"

  case "${code}" in
    A)
      # Pure addition — allowed, even under docs/ or references/.
      continue
      ;;
    C)
      # Copy — creates a new path from an existing one; the existing
      # (source) path is untouched, so this is addition-shaped. Allowed.
      continue
      ;;
    M|D|T|U)
      if under_immutable "${path}"; then
        OFFENDERS+=("${code}	${path}")
      fi
      ;;
    R)
      # Rename: old path effectively disappears, new path appears.
      # Treat as a modification of the OLD path if it was immutable —
      # renaming/moving a vendor file out from under its committed path
      # is exactly the kind of drift RULE-010 exists to prevent.
      if under_immutable "${path}"; then
        OFFENDERS+=("R (renamed away)	${path}")
      fi
      if [[ -n "${path2}" ]] && under_immutable "${path2}"; then
        OFFENDERS+=("R (renamed in, content changed)	${path2}")
      fi
      ;;
    *)
      # Unknown status code — be conservative and flag it under an
      # immutable dir rather than silently pass it.
      if under_immutable "${path}"; then
        OFFENDERS+=("${code}	${path}")
      fi
      ;;
  esac
done <<< "${DIFF_OUTPUT}"

if [[ ${#OFFENDERS[@]} -eq 0 ]]; then
  echo "${SCRIPT_NAME}: clear — no modifications/deletions under docs/ or references/."
  exit 0
fi

echo "${SCRIPT_NAME}: REFUSED (RULE-010)." >&2
echo "The following changes modify or delete tracked files under docs/ or" >&2
echo "references/. Those paths are immutable vendor/third-party material —" >&2
echo "corrections belong in context/ (cite the source path), never here." >&2
echo >&2
for o in "${OFFENDERS[@]}"; do
  printf '  %s\n' "${o}" >&2
done
exit 2
