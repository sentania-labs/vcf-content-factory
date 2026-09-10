#!/usr/bin/env bash
# version_line_guard.sh — RULE-014 / RULE-012 pre-tag guard.
#
# Spec: the (since-deleted) local reorg TODO's "New HOOKS" §1;
# durable-output map: STRUCTURE.md (vcfops_*/, scripts/, knowledge/context/).
#
# Refuses a `v*` tag / push on an SDK adapter repo checkout when:
#   (a) RULE-014 — adapter.yaml is still on the 0.x version line. 0.x is the
#       dev-preview line and is NEVER tagged; only a `<version>.<build>`
#       where <version> is 1.x+ may carry a v* tag.
#   (b) RULE-012 — the factory's defect gate refuses the named pak because
#       an open blocking defect names it in knowledge/context/defects.md.
# It also emits an INFORMATIONAL (non-blocking) warning if a locally-built
# 1.x+ pak filename is sitting in dist/ — that pak did not necessarily come
# from CI (the real release path), but this cannot be proven from a local
# checkout alone, so it is a warning, not a refusal.
#
# This script RUNS AUTOMATICALLY on a pak clone: .githooks/pre-push is a
# thin dispatcher that hands it the pre-push stdin, and
# scripts/bootstrap_managed_paks.sh points every registered clone at
# that hooks directory via core.hooksPath. See
# knowledge/designs/defect-isolation-v1.md. It remains directly
# invokable by hand or from a CI step; the hook adds no policy of its
# own, so both paths reach the same verdict.
#
# Every v* tag on stdin is checked, and each one is checked against the
# adapter.yaml AT THE COMMIT THE TAG POINTS TO, not the working tree: a
# tag on an old 0.x commit is still a 0.x release however far the tree
# has moved on since. Tag deletions (all-zero local sha) are ignored.
#
# Usage:
#   scripts/version_line_guard.sh [options]
#
# Options:
#   --version <ver>     adapter.yaml version to check (e.g. 1.2.0). If
#                        omitted, read from the tagged commit (stdin mode)
#                        or from --repo-dir/adapter.yaml (--tag mode).
#   --tag <tagname>      the tag being pushed/created (e.g. v1.2.0). If
#                        omitted, read from stdin in pre-push hook format
#                        ("<local-ref> <local-sha> <remote-ref> <remote-sha>"
#                        lines); every refs/tags/v* entry is checked.
#   --ref <object>       with --tag: the commit or tag object to read
#                        adapter.yaml from instead of the working tree.
#   --repo-dir <path>    SDK adapter repo checkout (default: cwd). Must
#                        contain adapter.yaml unless --version is given.
#   --pak <name>         override the pak name passed to `defect-gate
#                        --pak`. Default: derived from the repo's `origin`
#                        remote URL the same way CI derives it
#                        (vcf-content-factory-sdk-<name> -> <name>).
#   --dist-dir <path>    where to look for locally-built pak files for the
#                        informational dist warning (default:
#                        <factory-root>/dist if this checkout is inside the
#                        factory tree, else skipped).
#   --skip-defect-gate    skip the RULE-012 defect-gate check (diagnostics
#                        only — do not use this to get around a refusal).
#   -h, --help            show this help and exit.
#
# Exit codes:
#   0   clear to tag/push.
#   1   usage error / could not determine version or tag, or at least one
#       tag's commit had no readable adapter.yaml. Returned only after
#       every readable tag and the defect gate were checked, so a refusal
#       elsewhere in the same push still wins (exit 2 or 3).
#   2   RULE-014 violation — 0.x line tagged with a v* tag.
#   3   RULE-012 violation — defect-gate refused the pak.
#   4   the defect gate could not run (no interpreter, package import
#       failed, registry unreadable): NO verdict. The pre-push hook treats
#       this as "not guarded" and allows the push, per RULE-012's fail-safe
#       contract. Only 2 and 3 are refusals.

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  sed -n '2,69p' "$0" | sed 's/^# \{0,1\}//'
}

VERSION=""
TAG=""
REF=""
REPO_DIR="$(pwd)"
PAK_NAME=""
DIST_DIR=""
SKIP_DEFECT_GATE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"; shift 2 ;;
    --tag)
      TAG="${2:-}"; shift 2 ;;
    --ref)
      REF="${2:-}"; shift 2 ;;
    --repo-dir)
      REPO_DIR="${2:-}"; shift 2 ;;
    --pak)
      PAK_NAME="${2:-}"; shift 2 ;;
    --dist-dir)
      DIST_DIR="${2:-}"; shift 2 ;;
    --skip-defect-gate)
      SKIP_DEFECT_GATE=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "${SCRIPT_NAME}: unknown argument: $1" >&2
      usage >&2
      exit 1 ;;
  esac
done

# --- Determine the tag(s) being created/pushed -----------------------------
# Parallel arrays: TAGS[i] is checked against the adapter.yaml at REFS[i]
# (empty = working tree).
TAGS=()
REFS=()
if [[ -n "${TAG}" ]]; then
  TAGS+=("${TAG}")
  REFS+=("${REF}")
elif [[ ! -t 0 ]]; then
  # Non-interactive stdin: parse pre-push hook format. A line whose local
  # sha is all zeros is a deletion, not a release; skip it.
  while IFS=' ' read -r local_ref local_sha remote_ref _remote_sha; do
    [[ -z "${local_ref:-}" ]] && continue
    if [[ "${local_sha:-}" =~ ^0+$ ]]; then continue; fi
    if [[ "${remote_ref:-}" == refs/tags/v* ]]; then
      TAGS+=("${remote_ref#refs/tags/}")
      REFS+=("${local_sha:-}")
    elif [[ "${local_ref:-}" == refs/tags/v* ]]; then
      TAGS+=("${local_ref#refs/tags/}")
      REFS+=("${local_sha:-}")
    fi
  done
fi

if [[ ${#TAGS[@]} -eq 0 ]]; then
  echo "${SCRIPT_NAME}: no tag given (--tag) and none found on stdin in pre-push hook format." >&2
  echo "Nothing to guard — pass --tag <name> explicitly, or pipe pre-push ref lines in." >&2
  exit 1
fi

# --- Read adapter.yaml's version, from a git object or the working tree ----
# read_version <ref> -> prints the version, or returns 1 with a message.
read_version() {
  local ref="$1" text=""
  if [[ -n "${ref}" ]]; then
    # <object>^{commit}:path peels an annotated tag to its commit first.
    if ! text="$(git -C "${REPO_DIR}" show "${ref}^{commit}:adapter.yaml" 2>/dev/null)"; then
      echo "${SCRIPT_NAME}: adapter.yaml not readable at ${ref} in ${REPO_DIR}." >&2
      return 1
    fi
  else
    local adapter_yaml="${REPO_DIR%/}/adapter.yaml"
    if [[ ! -f "${adapter_yaml}" ]]; then
      echo "${SCRIPT_NAME}: --version not given and ${adapter_yaml} not found." >&2
      echo "Pass --version <adapter.yaml version> explicitly, or run from an adapter checkout." >&2
      return 1
    fi
    text="$(cat "${adapter_yaml}")"
  fi
  local ver
  ver="$(printf '%s\n' "${text}" | grep -E '^version:' | head -n1 | sed -E "s/^version:[[:space:]]*[\"']?([^\"'[:space:]]+)[\"']?.*/\\1/" || true)"
  if [[ -z "${ver}" ]]; then
    echo "${SCRIPT_NAME}: could not parse a 'version:' field out of adapter.yaml${ref:+ at ${ref}}." >&2
    return 1
  fi
  printf '%s\n' "${ver}"
}

# --- RULE-014: 0.x is never tagged, checked per tag ------------------------
RULE014_HITS=0
UNREADABLE=()
for i in "${!TAGS[@]}"; do
  tag="${TAGS[$i]}"
  ref="${REFS[$i]}"
  if [[ "${tag}" != v* ]]; then
    echo "${SCRIPT_NAME}: '${tag}' is not a v* tag: nothing to guard for it." >&2
    continue
  fi
  if [[ -n "${VERSION}" ]]; then
    ver="${VERSION}"
  else
    # An unreadable adapter.yaml at one tag is recorded and the loop goes
    # on: bailing here would drop a RULE-014 verdict already reached for
    # another tag in the same push and skip the defect gate entirely.
    if ! ver="$(read_version "${ref}")"; then
      UNREADABLE+=("${tag}")
      continue
    fi
  fi
  echo "${SCRIPT_NAME}: checking tag '${tag}' against adapter.yaml version '${ver}'${ref:+ at ${ref}}."
  if [[ "${ver}" =~ ^0(\.|$) ]]; then
    cat >&2 <<EOM
${SCRIPT_NAME}: REFUSED (RULE-014).
  adapter.yaml version '${ver}'${ref:+ at ${ref}} is on the 0.x dev-preview line.
  0.x paks are never tagged, never released, never attached to a
  GitHub Release. Bump adapter.yaml's version to 1.x+ before tagging
  '${tag}'. See knowledge/rules/pak-version-lines.md.
EOM
    RULE014_HITS=$((RULE014_HITS + 1))
  fi
done
if [[ ${RULE014_HITS} -gt 0 ]]; then
  exit 2
fi

# --- Informational: locally-built 1.x+ pak sitting in dist/ ----------------
if [[ -z "${DIST_DIR}" ]]; then
  # Best-effort: look for a dist/ alongside this checkout, or at the
  # factory root if this script is running from inside the factory tree.
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  CANDIDATE_DIST="$(cd "${SCRIPT_DIR}/.." && pwd)/dist"
  if [[ -d "${CANDIDATE_DIST}" ]]; then
    DIST_DIR="${CANDIDATE_DIST}"
  elif [[ -d "${REPO_DIR%/}/dist" ]]; then
    DIST_DIR="${REPO_DIR%/}/dist"
  fi
fi

if [[ -n "${DIST_DIR}" && -d "${DIST_DIR}" ]]; then
  ADAPTER_KIND=""
  if [[ -f "${REPO_DIR%/}/adapter.yaml" ]]; then
    ADAPTER_KIND="$(grep -E '^adapter_kind:' "${REPO_DIR%/}/adapter.yaml" | head -n1 | sed -E 's/^adapter_kind:[[:space:]]*"?([^"[:space:]]+)"?.*/\1/' || true)"
    ADAPTER_KIND="${ADAPTER_KIND#vcfcf_}"
  fi
  if [[ -n "${ADAPTER_KIND}" ]]; then
    shopt -s nullglob
    HITS=("${DIST_DIR}"/vcfcf_sdk_"${ADAPTER_KIND}".[1-9]*.pak)
    shopt -u nullglob
    if [[ ${#HITS[@]} -gt 0 ]]; then
      echo "${SCRIPT_NAME}: WARNING (informational, not blocking) — found locally-present 1.x+ pak file(s):" >&2
      printf '  %s\n' "${HITS[@]}" >&2
      echo "  These MAY be CI-released artifacts fetched/copied locally, or they may be" >&2
      echo "  hand-built (RULE-014 violation if so). This cannot be proven from a local" >&2
      echo "  checkout — verify against the pak's GitHub Releases before trusting one." >&2
    fi
  fi
fi

# --- RULE-012: defect gate (once per pak; it is per artifact, not per tag) --
if [[ "${SKIP_DEFECT_GATE}" == true ]]; then
  echo "${SCRIPT_NAME}: --skip-defect-gate set; skipping RULE-012 check (diagnostics only)." >&2
else
  if [[ -z "${PAK_NAME}" ]]; then
    ORIGIN_URL="$(git -C "${REPO_DIR}" config --get remote.origin.url 2>/dev/null || true)"
    if [[ -n "${ORIGIN_URL}" ]]; then
      BASE="$(basename "${ORIGIN_URL}")"
      BASE="${BASE%.git}"
      PAK_NAME="${BASE#vcf-content-factory-sdk-}"
    fi
  fi

  if [[ -z "${PAK_NAME}" ]]; then
    echo "${SCRIPT_NAME}: could not derive a pak name (no --pak, no origin remote to derive from)." >&2
    echo "Pass --pak <name> explicitly." >&2
    exit 1
  fi

  FACTORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  echo "${SCRIPT_NAME}: running RULE-012 defect gate for pak '${PAK_NAME}'."
  # vcfops_packaging lives under src/ (see pyproject.toml src-layout) and is
  # never pip-installed — resolve it via PYTHONPATH explicitly, since this
  # script runs standalone (by hand or from a pre-push hook), outside both
  # Claude Code's .claude/settings.json env and CI's workflow-level env.
  #
  # The gate's own exit codes are the verdict: 0 clean, 2 blocked. Anything
  # else (1 = registry unreadable, 127 = no python3, an import traceback)
  # means it could not run, and that is exit 4 here, never 3: refusing a
  # push because the gate's own plumbing broke is exactly the outage
  # coupling RULE-012's fail-safe clause forbids.
  #
  # Exit 2 alone is not proof of a verdict: argparse also exits 2 on a usage
  # error. It counts as a refusal only when the gate printed its own
  # "Refused by RULE-012" line; any other exit 2 is a gate that did not run.
  gate_rc=0
  gate_out="$( ( cd "${FACTORY_ROOT}" && PYTHONPATH="${FACTORY_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" python3 -m vcfops_packaging defect-gate --pak="${PAK_NAME}" ) 2>&1 )" || gate_rc=$?
  [[ -n "${gate_out}" ]] && printf '%s\n' "${gate_out}"
  if [[ "${gate_rc}" == 2 && "${gate_out}" != *"Refused by RULE-012"* ]]; then
    gate_rc=4
  fi
  case "${gate_rc}" in
    0) ;;
    2)
      echo "${SCRIPT_NAME}: REFUSED (RULE-012): open blocking defect(s) affect pak '${PAK_NAME}'." >&2
      echo "See knowledge/context/defects.md. Fix or legitimately close the named defect(s) first." >&2
      exit 3
      ;;
    *)
      echo "${SCRIPT_NAME}: defect gate could not run (exit ${gate_rc}); no RULE-012 verdict for pak '${PAK_NAME}'." >&2
      echo "  This is an infrastructure problem (interpreter, package import, registry), not a defect." >&2
      exit 4
      ;;
  esac
fi

if [[ ${#UNREADABLE[@]} -gt 0 ]]; then
  echo "${SCRIPT_NAME}: WARNING: no RULE-014 verdict for ${UNREADABLE[*]}: adapter.yaml unreadable at the tagged commit." >&2
  if [[ ${#UNREADABLE[@]} -lt ${#TAGS[@]} ]]; then
    echo "  Every other tag in this push passed both checks." >&2
  fi
  exit 1
fi

echo "${SCRIPT_NAME}: clear: ${TAGS[*]} may proceed (pak '${PAK_NAME:-n/a}')."
exit 0
