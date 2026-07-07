#!/usr/bin/env bash
# immutability_guard.sh — RULE-010 generalization, pre-commit shape.
#
# Spec: memory/environment/TODO-top-level-reorg.md "New HOOKS" §2;
# durable-output map: STRUCTURE.md's authorship x mutability grid — reference/
# (which holds docs/ and references/, now reference/docs/ and
# reference/references/) is "vendor / third-party, immutable (never edit;
# RULE-010)". This script hardens that boundary at commit time: it does
# NOT relax RULE-010, it enforces it mechanically.
#
# Refuses MODIFICATIONS or DELETIONS (not additions) of tracked files
# under reference/. New files landing under that path (fresh vendor
# extracts, newly-bootstrapped reference repos force-added, etc.) are
# allowed — only touching or removing what's already there is blocked.
#
# Rename policy (RULE-016: immutability is about bytes, not tree
# layout — dead-path detection after a move is path_reference_audit.sh's
# job, not this guard's):
#   - ALLOWED:  pure renames (similarity index R100, i.e. zero content
#               change AND unchanged file mode) whose DESTINATION is
#               under reference/ — whether the source was outside
#               reference/ (a move IN, additive) or already inside it
#               (restructuring within the immutable root). Git reports
#               these as "R100\t<old>\t<new>".
#   - REFUSED:  any rename with content modification (R<100, e.g. R087)
#               touching reference/ on either side; plain modifications
#               (M) of tracked files under reference/; deletions (D) of
#               tracked files under reference/; renames whose SOURCE is
#               under reference/ but whose destination is NOT — that's
#               a deletion from the immutable root wearing a rename
#               mask; and R100 renames touching reference/ whose file
#               MODE changed (e.g. a chmod riding along with a `git mv`)
#               — R100 only certifies byte-identical content, not an
#               unchanged mode, so a mode change there is a modification
#               wearing a rename mask and is refused just like a plain M.
#   All `git diff` invocations below use --raw --find-renames (not
#   --name-status) so the src/dst file modes are available for the
#   R100 mode check above; --find-renames is passed explicitly — this
#   policy does NOT rely on the ambient `diff.renames` git config. With
#   that config false, an unpatched invocation would show a pure
#   in-reference/ rename as D+A and falsely refuse it.
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
#   0   no modifications/deletions under reference/.
#   1   usage error.
#   2   at least one offending path found — refused.

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'
}

IMMUTABLE_DIRS=("reference/")

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
  DIFF_OUTPUT="$(git diff --find-renames --raw "${RANGE}")"
elif [[ $# -eq 2 ]]; then
  DIFF_OUTPUT="$(git diff --find-renames --raw "$1" "$2")"
elif [[ $# -eq 0 ]]; then
  DIFF_OUTPUT="$(git diff --find-renames --cached --raw)"
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

# --raw lines look like:
#   :100644 100644 <sha1> <sha2> M\tpath
#   :100644 100755 <sha1> <sha2> R100\told\tnew
# i.e. a space-separated meta field, then a tab, then path(s).
while IFS=$'\t' read -r meta path path2; do
  [[ -z "${meta}" ]] && continue

  # meta = ":srcmode dstmode srcsha dstsha status[score]"
  read -r src_mode dst_mode _srcsha _dstsha status <<< "${meta#:}"

  code="${status:0:1}"

  case "${code}" in
    A)
      # Pure addition — allowed, even under reference/.
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
      # status carries a similarity score, e.g. "R100" (pure rename,
      # byte-identical content) or "R087" (renamed AND edited).
      similarity="${status:1}"
      src_immutable=0
      dst_immutable=0
      under_immutable "${path}" && src_immutable=1
      if [[ -n "${path2}" ]] && under_immutable "${path2}"; then
        dst_immutable=1
      fi

      if [[ "${similarity}" == "100" ]]; then
        # Pure rename, zero content change. Immutability is about
        # bytes, not tree layout (RULE-016) — allow moves/restructures
        # whose destination lands under reference/, whether the
        # source came from outside (addition-shaped) or from inside
        # it (restructuring within the immutable root).
        if [[ "${src_immutable}" -eq 1 && "${dst_immutable}" -eq 0 ]]; then
          # Source under reference/, destination is not: a deletion
          # from the immutable root wearing a rename mask. Refuse.
          OFFENDERS+=("R100 (moved out of reference/, deletion in disguise)	${path} -> ${path2}")
        elif [[ "${src_immutable}" -eq 1 || "${dst_immutable}" -eq 1 ]] && [[ "${src_mode}" != "${dst_mode}" ]]; then
          # R100 only certifies byte-identical content — it says
          # nothing about file mode. A chmod riding along with the
          # rename is a modification of tracked reference/ material
          # wearing a rename mask. Refuse.
          OFFENDERS+=("R100 (mode change ${src_mode} -> ${dst_mode} under reference/ is a modification)	${path} -> ${path2}")
        fi
        # dst_immutable (src outside or inside) with dst under
        # reference/, mode unchanged: allowed, no offense recorded.
      else
        # Rename with content modification. Refuse if either side
        # touches reference/ — same bar as a plain M/D.
        if [[ "${src_immutable}" -eq 1 ]]; then
          OFFENDERS+=("${status} (renamed away, content changed)	${path}")
        fi
        if [[ "${dst_immutable}" -eq 1 ]]; then
          OFFENDERS+=("${status} (renamed in, content changed)	${path2}")
        fi
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
  echo "${SCRIPT_NAME}: clear — no modifications/deletions under reference/."
  exit 0
fi

echo "${SCRIPT_NAME}: REFUSED (RULE-010)." >&2
echo "The following changes modify or delete tracked files under reference/." >&2
echo "That path is immutable vendor/third-party material —" >&2
echo "corrections belong in context/ (cite the source path), never here." >&2
echo >&2
for o in "${OFFENDERS[@]}"; do
  printf '  %s\n' "${o}" >&2
done
exit 2
