#!/usr/bin/env bash
# version_line_guard.sh — RULE-014 / RULE-012 pre-tag guard.
#
# Spec: memory/environment/TODO-top-level-reorg.md "New HOOKS" §1;
# durable-output map: STRUCTURE.md (vcfops_*/, scripts/, context/).
#
# Refuses a `v*` tag / push on an SDK adapter repo checkout when:
#   (a) RULE-014 — adapter.yaml is still on the 0.x version line. 0.x is the
#       dev-preview line and is NEVER tagged; only a `<version>.<build>`
#       where <version> is 1.x+ may carry a v* tag.
#   (b) RULE-012 — the factory's defect gate refuses the named pak because
#       an open blocking defect names it in context/defects.md.
# It also emits an INFORMATIONAL (non-blocking) warning if a locally-built
# 1.x+ pak filename is sitting in dist/ — that pak did not necessarily come
# from CI (the real release path), but this cannot be proven from a local
# checkout alone, so it is a warning, not a refusal.
#
# This script does not (yet) run automatically — see CLAUDE.md RULE-013/
# RULE-014 and the reorg TODO's "New HOOKS" section for how it will be
# wired into settings.json / a real git hook. Until then, invoke it by
# hand, or from a CI step, before pushing a v* tag.
#
# Usage:
#   scripts/version_line_guard.sh [options]
#
# Options:
#   --version <ver>     adapter.yaml version to check (e.g. 1.2.0). If
#                        omitted, read from --repo-dir/adapter.yaml.
#   --tag <tagname>      the tag being pushed/created (e.g. v1.2.0). If
#                        omitted, read from stdin in pre-push hook format
#                        ("<local-ref> <local-sha> <remote-ref> <remote-sha>"
#                        lines) looking for a refs/tags/v* entry.
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
#   1   usage error / could not determine version or tag.
#   2   RULE-014 violation — 0.x line tagged with a v* tag.
#   3   RULE-012 violation — defect-gate refused the pak.

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
}

VERSION=""
TAG=""
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

# --- Determine the tag being created/pushed -------------------------------
if [[ -z "${TAG}" ]]; then
  if [[ ! -t 0 ]]; then
    # Non-interactive stdin: try to parse pre-push hook format.
    while IFS=' ' read -r local_ref _local_sha remote_ref _remote_sha; do
      [[ -z "${local_ref:-}" ]] && continue
      if [[ "${remote_ref:-}" == refs/tags/v* ]]; then
        TAG="${remote_ref#refs/tags/}"
        break
      fi
      if [[ "${local_ref:-}" == refs/tags/v* ]]; then
        TAG="${local_ref#refs/tags/}"
        break
      fi
    done
  fi
fi

if [[ -z "${TAG}" ]]; then
  echo "${SCRIPT_NAME}: no tag given (--tag) and none found on stdin in pre-push hook format." >&2
  echo "Nothing to guard — pass --tag <name> explicitly, or pipe pre-push ref lines in." >&2
  exit 1
fi

if [[ "${TAG}" != v* ]]; then
  echo "${SCRIPT_NAME}: '${TAG}' is not a v* tag — nothing to guard. Exiting clean." >&2
  exit 0
fi

# --- Determine adapter.yaml version ---------------------------------------
if [[ -z "${VERSION}" ]]; then
  ADAPTER_YAML="${REPO_DIR%/}/adapter.yaml"
  if [[ ! -f "${ADAPTER_YAML}" ]]; then
    echo "${SCRIPT_NAME}: --version not given and ${ADAPTER_YAML} not found." >&2
    echo "Pass --version <adapter.yaml version> explicitly, or run from an adapter checkout." >&2
    exit 1
  fi
  VERSION="$(grep -E '^version:' "${ADAPTER_YAML}" | head -n1 | sed -E 's/^version:[[:space:]]*"?([^"[:space:]]+)"?.*/\1/')"
  if [[ -z "${VERSION}" ]]; then
    echo "${SCRIPT_NAME}: could not parse a 'version:' field out of ${ADAPTER_YAML}." >&2
    exit 1
  fi
fi

echo "${SCRIPT_NAME}: checking tag '${TAG}' against adapter.yaml version '${VERSION}'."

# --- RULE-014: 0.x is never tagged -----------------------------------------
if [[ "${VERSION}" =~ ^0(\.|$) ]]; then
  cat >&2 <<EOF
${SCRIPT_NAME}: REFUSED (RULE-014).
  adapter.yaml version '${VERSION}' is on the 0.x dev-preview line.
  0.x paks are never tagged, never released, never attached to a
  GitHub Release. Bump adapter.yaml's version to 1.x+ before tagging
  '${TAG}'. See rules/pak-version-lines.md.
EOF
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
    ADAPTER_KIND="$(grep -E '^adapter_kind:' "${REPO_DIR%/}/adapter.yaml" | head -n1 | sed -E 's/^adapter_kind:[[:space:]]*"?([^"[:space:]]+)"?.*/\1/')"
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

# --- RULE-012: defect gate --------------------------------------------------
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
  if ! ( cd "${FACTORY_ROOT}" && python3 -m vcfops_packaging defect-gate --pak "${PAK_NAME}" ); then
    echo "${SCRIPT_NAME}: REFUSED (RULE-012) — open blocking defect(s) affect pak '${PAK_NAME}'." >&2
    echo "See context/defects.md. Fix or legitimately close the named defect(s) first." >&2
    exit 3
  fi
fi

echo "${SCRIPT_NAME}: clear — '${TAG}' may proceed (version '${VERSION}', pak '${PAK_NAME:-n/a}')."
exit 0
