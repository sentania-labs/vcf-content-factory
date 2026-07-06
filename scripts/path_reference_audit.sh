#!/usr/bin/env bash
# path_reference_audit.sh — the top-level-reorg migration safety net.
#
# Spec: memory/environment/TODO-top-level-reorg.md "New HOOKS" §3 +
# "Open holes to resolve during execution" #4 (agent-prompt path sweep);
# durable-output map: STRUCTURE.md (the map this script cross-checks the
# corpus against).
#
# Greps the governance corpus for repo-relative path references and
# reports any that do not exist in the current working tree. This is the
# safety net for the (future, not-yet-started) directory-move sequencing
# in the reorg TODO: run it before and after every move to catch a
# citation that silently went dead.
#
# Corpus scanned (fixed list, matching the TODO's "agent-prompt path
# sweep" hole):
#   CLAUDE.md, STRUCTURE.md, .claude/agents/*.md, .claude/skills/**/*.md,
#   rules/*.md, lessons/INDEX.md, context/README.md,
#   .github/workflows/*.yml, .gitignore
#
# Heuristic (tuned against the tree as it exists today; every rule below
# earned its place fixing a real false positive found by running this
# script against the actual corpus — see the header comments at each
# check for the concrete example that motivated it):
#
#   1. A candidate path token — backtick-quoted or bare — must start with
#      one of the repo's actual top-level entries immediately followed by
#      "/". This is the single biggest noise filter: it rejects API
#      endpoints (`/publish`, `/api/supermetrics`, ...), GitHub org/repo
#      refs (`sentania-labs/vcf-content-factory-sdk-template`), agent/CLI
#      identifiers (`tooling`, `build-sdk`), and doc-internal relative
#      section labels (context/README.md's own `` `mpb/` `` subdir
#      headers) — none of those start with a real top-level name.
#   2. A lone top-level-root FILE with no slash at all (`` `CLAUDE.md` ``)
#      is still a valid citation, checked against a small whitelist of
#      root files.
#   3. Tokens carrying placeholder/glob markup (`<`, `>`, `$`, `*`, `{`,
#      `}`) are skipped — documented patterns
#      (`content/sdk-adapters/<name>/`, `v*`, `bundles/*.zip`), not
#      literal citations.
#   4. A candidate immediately preceded by "e.g." on the same line is
#      skipped — illustrative examples ("e.g., `content/managementpacks/
#      synology_nas.yaml`") name a plausible file, not an asserted one.
#   5. Existence is checked several ways before a candidate is declared
#      dead, because "repo-relative" in this corpus sometimes means
#      relative to the CITING FILE's own directory, not the repo root:
#        a. literal path from the repo root
#        b. same, with a `.md` or `.py` extension appended (docs drop
#           extensions in prose; `vcfops_dashboards/render` for
#           `vcfops_dashboards/render.py` is a real example)
#        c. relative to the directory the citing file lives in (a
#           `.claude/skills/<skill>/SKILL.md` citing `references/foo.md`
#           means ITS OWN `references/` subdir, not the factory root's)
#        d. for `docs/`, `references/`, `dashboards/`, `views/` prefixes
#           specifically: also tried under every currently-cloned
#           `content/sdk-adapters/<pak>/` (agent prompts describing SDK-
#           adapter conventions use these bare names generically — e.g.
#           `docs/README.md` and `dashboards/compliance-overview.yaml`
#           are real inside a pak checkout, never at the factory root)
#   6. Two-segment candidates (`A/B`) that still fail all of #5 are
#      treated as a prose "A or B" idiom, not a path, and are NOT
#      reported, when either:
#        - both A and B independently name a real top-level entry
#          (`docs/tests`, `views/dashboards` — two real top-level dirs
#          joined by "/" instead of "or"), or
#        - B contains an uppercase letter (`views/SMs` — no real path in
#          this repo's naming convention looks like that)
#   7. Three-or-more-segment candidates that still fail #5 are checked
#      progressively: if any INTERMEDIATE segment (i.e. every prefix
#      except the final one) does not exist as a real directory, the
#      whole token is treated as an unparseable prose list
#      (`rules/lessons/context` — `rules/lessons` is not a directory)
#      rather than reported.
#   8. .gitignore is a special case: only its COMMENT lines (`#...`) are
#      scanned for citations. The ignore PATTERNS themselves (e.g.
#      `vcfops_managementpacks/adapter_runtime/`) are allowed to not
#      exist — that not-yet-existing is the entire point of a gitignore
#      pattern, not a dead reference.
#
# This heuristic is deliberately generous about NOT reporting ambiguous
# prose — the goal is signal, not noise. It will not catch every future
# dead reference; it is a net, not a prover.
#
# This script does not (yet) run automatically (no pre-push/CI wiring) —
# see the reorg TODO for how it graduates into a git hook or CI step.
#
# Usage:
#   scripts/path_reference_audit.sh [-h|--help]
#
# Exit codes:
#   0   no dead references found.
#   2   at least one dead reference found (listed as citing-file:line -> missing-path).

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  sed -n '2,90p' "$0" | sed 's/^# \{0,1\}//'
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "${SCRIPT_NAME}: not inside a git repository." >&2
  exit 1
}
cd "${REPO_ROOT}"

# --- Corpus: fixed list per the TODO's spec ---------------------------------
declare -a TARGET_FILES=()
[[ -f CLAUDE.md ]] && TARGET_FILES+=("CLAUDE.md")
[[ -f STRUCTURE.md ]] && TARGET_FILES+=("STRUCTURE.md")
[[ -f lessons/INDEX.md ]] && TARGET_FILES+=("lessons/INDEX.md")
[[ -f context/README.md ]] && TARGET_FILES+=("context/README.md")
[[ -f .gitignore ]] && TARGET_FILES+=(".gitignore")

while IFS= read -r -d '' f; do
  TARGET_FILES+=("${f#./}")
done < <(find .claude/agents -maxdepth 1 -type f -name '*.md' -print0 2>/dev/null | sort -z)

while IFS= read -r -d '' f; do
  TARGET_FILES+=("${f#./}")
done < <(find .claude/skills -type f -name '*.md' -print0 2>/dev/null | sort -z)

while IFS= read -r -d '' f; do
  TARGET_FILES+=("${f#./}")
done < <(find rules -maxdepth 1 -type f -name '*.md' -print0 2>/dev/null | sort -z)

while IFS= read -r -d '' f; do
  TARGET_FILES+=("${f#./}")
done < <(find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) -print0 2>/dev/null | sort -z)

if [[ ${#TARGET_FILES[@]} -eq 0 ]]; then
  echo "${SCRIPT_NAME}: no corpus files found — nothing to audit." >&2
  exit 0
fi

# --- Known top-level entries (what a path token is allowed to start with) --
declare -a TOPLEVEL=()
while IFS= read -r -d '' f; do
  TOPLEVEL+=("${f}")
done < <(find . -maxdepth 1 -mindepth 1 ! -name '.git' -printf '%f\0')

declare -A TOPLEVEL_SET=()
for t in "${TOPLEVEL[@]}"; do
  TOPLEVEL_SET["${t}"]=1
done

# Root-level FILES only (a subset of TOPLEVEL) — the whitelist for bare
# (no-slash) citations like `CLAUDE.md` or `STRUCTURE.md`. Bare single-word
# tokens that are NOT one of these (agent names like `tooling`, code
# identifiers like `additionalContext`, CLI verbs like `build-sdk`) are
# code/prose, not path citations, and must not be checked — rule #1/#2.
declare -A TOPLEVEL_FILE_SET=()
while IFS= read -r -d '' f; do
  TOPLEVEL_FILE_SET["${f}"]=1
done < <(find . -maxdepth 1 -mindepth 1 -type f -printf '%f\0')

# Build an alternation regex, escaping regex metacharacters (mainly '.').
TOPLEVEL_RE=""
for t in "${TOPLEVEL[@]}"; do
  esc="$(printf '%s' "${t}" | sed -e 's/[.[\*^$+?(){}|\\]/\\&/g')"
  if [[ -z "${TOPLEVEL_RE}" ]]; then
    TOPLEVEL_RE="${esc}"
  else
    TOPLEVEL_RE="${TOPLEVEL_RE}|${esc}"
  fi
done

# Currently-cloned SDK adapter checkouts (gitignored, bootstrap-cloned —
# see context/managed_paks.md). Used only for rule #5d.
declare -a SDK_ADAPTER_DIRS=()
if [[ -d content/sdk-adapters ]]; then
  while IFS= read -r -d '' d; do
    SDK_ADAPTER_DIRS+=("${d}")
  done < <(find content/sdk-adapters -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
fi

# --- Extraction + verification ----------------------------------------------
FOUND_DEAD=0

is_placeholder() {
  # Rule #3.
  case "$1" in
    *'<'*|*'>'*|*'$'*|*'*'*|*'{'*|*'}'*) return 0 ;;
    *) return 1 ;;
  esac
}

is_bare_non_path() {
  # Rule #2: a token with no "/" is only a real citation if it's a known
  # top-level root FILE.
  local tok="$1"
  case "${tok}" in
    */*) return 1 ;;
    *) [[ -n "${TOPLEVEL_FILE_SET[${tok}]:-}" ]] && return 1 || return 0 ;;
  esac
}

strip_trailing_punct() {
  local p="$1"
  p="${p%%,}"
  p="${p%%.}"
  p="${p%%;}"
  p="${p%%:}"
  p="${p%%)}"
  p="${p%%\'}"
  p="${p%%\"}"
  printf '%s' "${p}"
}

path_exists_anywhere() {
  # Rule #5: literal, extension-tolerant, citing-dir-relative, and
  # sdk-adapter-relative existence check. Args: candidate, citing_file.
  local cand="$1" citing_file="$2"
  local citing_dir
  citing_dir="$(dirname -- "${citing_file}")"

  local -a bases=("${REPO_ROOT}/${cand}")
  [[ -n "${citing_dir}" && "${citing_dir}" != "." ]] && bases+=("${REPO_ROOT}/${citing_dir}/${cand}")

  # Rule #5d: docs/references/dashboards/views prefixes also get tried
  # under every currently-cloned SDK adapter checkout (same suffix).
  case "${cand}" in
    docs/*|references/*|dashboards/*|views/*)
      local d
      for d in "${SDK_ADAPTER_DIRS[@]}"; do
        bases+=("${REPO_ROOT}/${d}/${cand}")
      done
      ;;
  esac

  local b
  for b in "${bases[@]}"; do
    [[ -e "${b}" ]] && return 0
    [[ -e "${b}.md" ]] && return 0
    [[ -e "${b}.py" ]] && return 0
  done

  return 1
}

looks_like_prose_list() {
  # Rules #6/#7: multi-segment candidates that are really an "A/B" or
  # "A/B/C" prose shorthand, not a literal path.
  local cand="$1"
  local -a segs=()
  IFS='/' read -r -a segs <<< "${cand}"
  local n="${#segs[@]}"

  if [[ "${n}" -eq 2 ]]; then
    local a="${segs[0]}" b="${segs[1]}"
    if [[ -n "${TOPLEVEL_SET[${a}]:-}" && -n "${TOPLEVEL_SET[${b}]:-}" ]]; then
      return 0
    fi
    if [[ "${b}" =~ [A-Z] ]]; then
      return 0
    fi
    return 1
  fi

  if [[ "${n}" -ge 3 ]]; then
    local i prefix=""
    for (( i = 0; i < n - 1; i++ )); do
      if [[ -z "${prefix}" ]]; then
        prefix="${segs[$i]}"
      else
        prefix="${prefix}/${segs[$i]}"
      fi
      if [[ ! -d "${REPO_ROOT}/${prefix}" ]]; then
        return 0
      fi
    done
    return 1
  fi

  return 1
}

preceded_by_example_marker() {
  # Rule #4: "e.g." (or "example") immediately before the match — on the
  # SAME line or the line just above it (a wrapped "(e.g.,\n  `path`)")
  # — marks an illustrative filename, not an asserted citation.
  local line="$1" prev_line="$2" cand="$3"
  local before="${line%%"${cand}"*}"
  local tail="${before}"
  [[ ${#before} -gt 12 ]] && tail="${before: -12}"
  case "${tail}" in
    *e.g.*|*example*|*Example*) return 0 ;;
  esac
  local prev_tail="${prev_line}"
  [[ ${#prev_line} -gt 12 ]] && prev_tail="${prev_line: -12}"
  case "${prev_tail}" in
    *e.g.*|*example*|*Example*) return 0 ;;
  esac
  return 1
}

truncated_by_placeholder() {
  # Rule #3b: the extraction regex deliberately stops before `<`, `*`,
  # `$`, `{`, `}` (disallowed chars). If one of those immediately follows
  # the matched candidate in the raw line, the FULL literal token was a
  # placeholder/glob pattern (`designs/supermetrics/<slug>.md`,
  # `context/api-maps/tvs-*.md`) and got truncated into something that
  # looks like a real (but missing) path. Treat as placeholder, not dead.
  local line="$1" cand="$2"
  local after="${line#*"${cand}"}"
  # Allow one intervening "/" — the extraction regex requires its final
  # char to be alnum, so a placeholder right after a path separator
  # (`designs/supermetrics/<slug>.md`) truncates the slash away too.
  case "${after}" in
    /'<'*|/'*'*|/'$'*|/'{'*|'<'*|'*'*|'$'*|'{'*|'}'*) return 0 ;;
    *) return 1 ;;
  esac
}

check_candidates() {
  # Args: file, line_no, raw_line, prev_line, candidates...
  local file="$1" lineno="$2" raw_line="$3" prev_line="$4"
  shift 4
  local cand
  for cand in "$@"; do
    [[ -z "${cand}" ]] && continue
    is_placeholder "${cand}" && continue
    cand="$(strip_trailing_punct "${cand}")"
    [[ -z "${cand}" ]] && continue
    is_bare_non_path "${cand}" && continue
    preceded_by_example_marker "${raw_line}" "${prev_line}" "${cand}" && continue
    truncated_by_placeholder "${raw_line}" "${cand}" && continue
    path_exists_anywhere "${cand}" "${file}" && continue
    looks_like_prose_list "${cand}" && continue
    echo "${file}:${lineno} -> ${cand}"
    FOUND_DEAD=1
  done
}

for file in "${TARGET_FILES[@]}"; do
  is_gitignore=0
  [[ "${file}" == ".gitignore" ]] && is_gitignore=1

  lineno=0
  prev_line=""
  # shellcheck disable=SC2094 # false positive: nothing in this loop body
  # writes to $file; check_candidates only reads its VALUE as an argument.
  while IFS= read -r line; do
    lineno=$((lineno + 1))

    # Rule #8: .gitignore — only comment lines are citations.
    if [[ "${is_gitignore}" -eq 1 ]]; then
      case "${line}" in
        \#*) : ;;
        *) continue ;;
      esac
    fi

    declare -a candidates=()

    if [[ -n "${TOPLEVEL_RE}" ]]; then
      # Rule #1: backtick-quoted OR bare, both anchored on a real
      # top-level name immediately followed by "/".
      while IFS= read -r m; do
        [[ -n "${m}" ]] && candidates+=("${m}")
      done < <(grep -oP "(?<![/A-Za-z0-9_.-])(?:${TOPLEVEL_RE})/(?:[A-Za-z0-9_.\/-]*[A-Za-z0-9_-])?" <<< "${line}" 2>/dev/null || true)
    fi

    # Rule #2: lone backtick-quoted root files (`CLAUDE.md`), no slash.
    # shellcheck disable=SC2016 # single-quoted on purpose: literal regex,
    # nothing here is meant to expand.
    while IFS= read -r m; do
      [[ -n "${m}" ]] && candidates+=("${m}")
    done < <(grep -oP '(?<=`)[A-Za-z0-9_.-]+(?=`)' <<< "${line}" 2>/dev/null || true)

    if [[ ${#candidates[@]} -gt 0 ]]; then
      # shellcheck disable=SC2094 # false positive: check_candidates only
      # reads $file's VALUE (a path string) as an argument, it never
      # touches the fd this loop is reading lines from.
      check_candidates "${file}" "${lineno}" "${line}" "${prev_line}" "${candidates[@]}"
    fi
    prev_line="${line}"
  done < "${file}"
done

if [[ "${FOUND_DEAD}" -eq 1 ]]; then
  echo >&2
  echo "${SCRIPT_NAME}: dead reference(s) found (citing-file:line -> missing-path, see above)." >&2
  exit 2
fi

echo "${SCRIPT_NAME}: clear — no dead path references found in the scanned corpus."
exit 0
