#!/usr/bin/env bash
# Non-blocking CI reminder for the framework-review gate (P4).
#
# When a PR's diff touches framework Python (src/vcfops_*/) but adds no
# matching review doc under knowledge/context/reviews/framework/, emit a GitHub
# Actions ::warning::. This is a NUDGE, never a failure — the real gate
# is the orchestrator spawning `framework-reviewer` before the PR
# (CLAUDE.md). A doc-existence CI check would be rubber-stampable and
# could wedge legitimate hotfixes, so we deliberately do not fail here.
#
# Exit code is always 0. Usage:
#   scripts/check_framework_review.sh [BASE_REF]
# BASE_REF defaults to origin/main.

set -uo pipefail

BASE_REF="${1:-origin/main}"

# Resolve a merge-base diff range; fall back to a plain diff if the
# base isn't fetched (e.g. shallow checkout without the base).
if git rev-parse --verify --quiet "${BASE_REF}" >/dev/null; then
  RANGE="${BASE_REF}...HEAD"
else
  echo "check-framework-review: base ref '${BASE_REF}' not available; skipping (no diff range)."
  exit 0
fi

CHANGED="$(git diff --name-only "${RANGE}" 2>/dev/null || true)"
if [ -z "${CHANGED}" ]; then
  echo "check-framework-review: no changed files in ${RANGE}; nothing to check."
  exit 0
fi

# Did the change touch framework Python? The ten vcfops_* packages live
# under src/ (see pyproject.toml src-layout).
FRAMEWORK_HITS="$(printf '%s\n' "${CHANGED}" | grep -E '^src/vcfops_[^/]+/' || true)"
if [ -z "${FRAMEWORK_HITS}" ]; then
  echo "check-framework-review: no vcfops_*/ changes; framework review not required."
  exit 0
fi

# Did the same change leave a framework review doc in place? A diff lists
# DELETED/renamed-away report paths too, so a PR that deletes or renames a
# report would otherwise satisfy this check via the stale old path. Count
# only review docs that still EXIST in the post-change tree. [Codex PR-17]
REVIEW_HITS=""
for f in $(printf '%s\n' "${CHANGED}" | grep -E '^knowledge/context/reviews/framework/.+\.md$' | grep -v '/README\.md$' || true); do
  [ -f "${f}" ] && REVIEW_HITS="${REVIEW_HITS} ${f}"
done
REVIEW_HITS="${REVIEW_HITS# }"

if [ -n "${REVIEW_HITS}" ]; then
  echo "check-framework-review: vcfops_*/ change has a framework review doc:"
  printf '  %s\n' ${REVIEW_HITS}
  exit 0
fi

# Touched framework Python, no review doc — warn (non-blocking).
PKGS="$(printf '%s\n' "${FRAMEWORK_HITS}" | cut -d/ -f2 | sort -u | tr '\n' ' ')"
MSG="vcfops_*/ changed (${PKGS}) with no knowledge/context/reviews/framework/ doc. Per CLAUDE.md, tooling changes need a framework-reviewer pass before merge (RULE/P4). This is a reminder, not a failure."
echo "::warning title=Framework review missing::${MSG}"
echo "check-framework-review: WARN — ${MSG}"
exit 0
