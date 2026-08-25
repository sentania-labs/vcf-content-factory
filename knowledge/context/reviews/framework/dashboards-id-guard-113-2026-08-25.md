# Framework review: dashboards id-stability guard (issue #113)

- Branch: fix/113-dashboard-id-guard, commits 557d446 + 99f2660 + 89af0f5 + 47d5adb + dc2f957 + 799955a vs origin/main
- Files: src/vcfops_dashboards/id_guard.py (new), src/vcfops_dashboards/cli.py
  (validate hook), tests/test_dashboard_id_guard.py (new, 9 tests)
- Reviewer: framework-reviewer, 2026-08-25 (delta re-check of 99f2660 same day)
- Verdict: **APPROVE** after the dc2f957/799955a round (0 BLOCKING / 2 WARNING open / 3 NIT open). The delta-2 BLOCKING (baseline substituted instead of widened) and the delta-2 ci.yml NIT are resolved; see Delta re-check 3.

## What the change does

Validate-time guard: each working-tree dashboard YAML's (name, id) is
compared against `git show HEAD:<path>`; a changed id under an unchanged
name fails validation (rc 1, `ID-STABILITY:` on stderr). A HEAD-wide
name scan (`git ls-tree -r` + per-file `git show`, lazy) catches
file-rename-plus-re-id. Git failure modes degrade to printed warnings,
never silent pass. Baseline is offline git HEAD, per issue #113 and
RULE-007 (dashboard import identity is the NAME; a re-id under a kept
name silently orphans the installed UUID, evidence in
knowledge/context/api-surface/content_import_skip_semantics.md).

## Independent verification

- Targeted tests: 9/9 pass. Full suite minus targeted: 996 passed,
  4 skipped, 185 deselected (996+9 = author's claimed 1005). Green.
- Validate chain (RULE-005 seven-package): green. Note: an initial
  chain run timed out at 120s; isolated timing showed the stall is
  `vcfops_managementpacks validate` (220s, Tier 2 SDK validation),
  pre-existing and untouched by this diff. Dashboards validate itself:
  ~1.4s on branch vs ~1.4s on main (guard cost is in the noise; 8
  corpus dashboards, at most 9 git subprocesses, no per-item explosion
  of the #112 class).
- Real-corpus mutation probe: mutated `id:` in
  content/dashboards/vm_snapshot_inventory.yaml with name kept; default
  `python3 -m vcfops_dashboards validate` returned rc 1 with one
  ID-STABILITY error naming both UUIDs. Reverted; tree clean. This also
  proves the RULE-005 chain's default invocation executes the guard.
- No escape hatch: no env var, flag, or config read in id_guard.py or
  the cli.py hook (grep for environ/getenv/skip: none). Guard runs
  unconditionally in cmd_validate for both default and explicit-path
  invocations.
- Adversarial probes (temp git repos, function-level):
  - Subdirectory re-id under content/dashboards/: caught (rglob and
    `ls-tree -r` are both recursive).
  - Move-to-subdir + re-id: caught by the name scan.
  - Staged-but-uncommitted re-id: caught (HEAD still holds baseline).
  - Dashboards dir outside any repo while process CWD is inside this
    repo: warns "could not run", does NOT compare against the wrong
    repo (`rev-parse --show-toplevel` runs with cwd = dashboards dir).
  - Repurposed file (name AND id both changed): passes, as intended;
    a genuinely-new-dashboard-replacing-an-old-file workflow is not
    blocked.
  - New file, name-only rename, missing name/id keys, unparseable
    YAML: all pass to the loader without guard noise (matches tests).

## WARNING


RESOLVED by 99f2660 (was WARNING 1): locale-dependent stderr fragment
matching. Presence-in-HEAD is now decided from ``git ls-tree HEAD --
<path>`` stdout under rc 0 (non-empty = committed, empty = absent,
rc != 0 = enumerated could-not-run warning); no verdict reads stderr
wording, and _run_git pins LC_ALL=C/LANG=C on every call. Independently
verified in temp repos: ls-tree returns rc 0 + non-empty for a committed
path, rc 0 + empty for an absent path, rc 128 for unborn HEAD and
no-repo (both land in the enumerated warning branch). Tooling correctly
rejected my ``git cat-file -e`` suggestion with evidence I reproduced:
cat-file -e returns rc 128 for BOTH an absent path and a broken rev,
so rc alone cannot enumerate absence (the unenumerated-verdict trap,
knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md). New
test test_localized_git_stderr_still_fails_hard Germanizes all git
stderr and asserts rename+re-id still hard-fails and LC_ALL=C is pinned
on every guard call.

1. [design] Post-commit blindness, verified (probe P4): once a re-id
   is committed, HEAD carries the new baseline and validation is green
   forever after; the baseline is HEAD of the current checkout, not the
   merge base with main. A commit-first-validate-later agent slips
   through, with only PR review left to catch it. Acceptable for the
   stated validate-before-install workflow (RULE-005), but worth either
   a doc note or a future CI check against the merge base.
2. [src/vcfops_dashboards/id_guard.py:_parse_identity] Name comparison
   is case-sensitive (id is lowercased, name is not). A case-only name
   change combined with a re-id passes the guard (probe P7). Whether
   the VCF Ops importer matches dashboard names case-insensitively is
   unverified; if it does, this is a residual orphaning path. Fix:
   verify on the lab once; if case-insensitive, fold case in the name
   compare.

## NIT

1. [_head_dashboard_names] Duplicate dashboard names committed in HEAD
   collapse last-wins in the name->id dict; probed a false failure on
   an identity-preserving file rename in that state. The precondition
   (two committed dashboards with one name) is itself broken per #113,
   and neither loader nor slug checks currently forbid it; harmless in
   practice, but the dict silently discards information.
2. [_head_dashboard_names] `ls-tree` output is parsed line-wise without
   `-z`; a non-ASCII dashboard filename would come back quoted under
   default `core.quotepath` and silently skip the name scan for that
   file. Slug filename conventions make this theoretical.

## Dimensions not applicable

Wire-format conformance, render regression, pak-compare, stale-zip /
CURRENT_TEMPLATE_VERSION: the diff emits nothing and touches neither
render.py nor any packaging path. Test coverage: present and
branch-complete, including the author's own mutation check
(guard stubbed -> failing scenario passes), which I reproduced in
spirit via the real-corpus probe.

## If shipped as-is

An author who re-ids a dashboard under a kept name is stopped at
validate with a message naming both UUIDs and the committed path;
legitimate renames, new dashboards, and repurposed files pass. Residual
exposure: localized-git environments and case-only renames degrade to
warnings or passes (WARNING 1 and 3).

## Delta re-check: 99f2660 (2026-08-25)

- Targeted tests: 10/10 pass (9 original + localized-stderr test).
- Real-corpus mutation probe repeated: mutated one dashboard id with
  name kept; default validate rc 1, one ID-STABILITY error; reverted,
  tree clean.
- Clean dashboards validate: rc 0, ~1.1s; the extra ls-tree per file
  (now ~2 git calls per committed dashboard, 8 files) is in the noise.
- ls-tree three-way enumeration and cat-file rc-128 evidence verified
  first-hand (see resolved item above).
- WARNINGs 1 and 2 (post-commit blindness; case-sensitive name compare
  vs unverified importer case semantics) are untouched by 99f2660 and
  remain follow-ups, not blockers: neither regresses a working path,
  both degrade loudly or require an unusual author action, and the
  fix for each is a doc/CI note or a one-time lab verification.
- Verdict after delta: **APPROVE**.

## Delta re-check 2: 89af0f5 + 47d5adb (baseline rev for CI, 2026-08-25)

Addresses the Codex P1 on PR #133 (my carried post-commit-blindness
WARNING). Verified first-hand in temp repos and against the 13-test
suite (13/13 pass):

- Committed re-id on a feature branch, baseline = merge-base: caught
  (errors=1), where the default HEAD baseline is blind (errors=0).
  The CI blindspot is closed for the simple re-id case.
- Baseline equal to HEAD (sha) behaves identically to the default on
  both a clean and a mutated tree (same errors, same warnings).
- Non-ancestor baseline: hard validation error naming the rev, guard
  refuses to run narrowed. Unresolvable baseline: loud warning,
  falls back to HEAD, states exactly what is not covered.
- ci.yml: merge-base resolution only on pull_request with
  GITHUB_BASE_REF; checkout uses fetch-depth 0 (ci.yml line 28) so
  origin/<base> and the merge-base are resolvable; empty BASE falls
  back to the plain invocation; shell quoting and `|| true` fallbacks
  are sound.

### BLOCKING (new)

1. [src/vcfops_dashboards/id_guard.py: baseline handling; also the
   --id-guard-baseline help text and module docstring] The claimed
   invariant "a baseline can only widen the comparison, never narrow
   or disable it" is false: the baseline SUBSTITUTES the reference
   rev, it is not unioned with HEAD, and the ancestor check constrains
   which rev is used, not the comparison's strength. Two reproduced
   counterexamples (temp-repo probes E1/E2):
   - E1, the default CI path: a PR that renames a dashboard (id kept,
     legitimate) in one commit and re-ids it under the new name in a
     later commit passes `validate --id-guard-baseline <merge-base>`
     with zero errors. The merge-base tree holds the old name, so the
     path comparison sees a name change and the name scan finds no
     collision. CI reports green on exactly the orphaning class the
     gate exists to catch (issue #113, RULE-007), for consumers who
     cannot see the repo: the reports-green-while-broken class.
   - E2, local narrowing: with a rename committed since the merge-base
     and an uncommitted re-id in the tree, default validate fails
     (HEAD catches it) but `--id-guard-baseline <merge-base>` passes.
     The flag can suppress an error the default catches, which is the
     escape-hatch property the design forswears.
   Smallest correct fix: when a baseline is supplied and resolves to a
   commit different from HEAD, run the per-file comparison (and name
   scan) against BOTH revs and union the errors. That makes "widen"
   literally true, closes E1 and E2, and costs one extra pass only in
   CI. Docstring/help text then match behavior.

### NIT (new)

3. [.github/workflows/ci.yml validate step] The comment and commit
   message claim "the guard itself warns loudly" when the merge base
   is unresolvable, but the empty-BASE branch runs the plain
   invocation with no baseline argument, so nothing warns anywhere:
   the narrowed comparison is silent in the CI log. Reachable only if
   merge-base fails despite the fetch-depth-0 clone, hence NIT. Fix:
   `echo` a warning in the empty-BASE branch.

### Status of carried findings

- Original WARNING 2 (post-commit blindness): resolved in principle by
  89af0f5/47d5adb, but the residual E1 compound case above is the new
  BLOCKING; fully resolved once the union fix lands.
- Original WARNING 3 (case-sensitive name compare, unverified importer
  case semantics): still open, still a follow-up, not a blocker.
- Verdict after delta 2: **CHANGES REQUESTED** until the union fix
  (or an equivalent that restores the widen-only invariant) lands;
  then re-review.

## Delta re-check 3: dc2f957 + 799955a (widen via baseline..HEAD scan, 2026-08-25)

Resolves the delta-2 BLOCKING. The working tree is now compared against
HEAD, the baseline, and every commit in ``git rev-list baseline..HEAD``,
findings unioned and deduped on the full message string (which carries
file, name, both ids, and the committed path, so distinct findings can
never collapse). 799955a adds the echo warning in ci.yml's empty-BASE
PR branch (delta-2 NIT 3: resolved).

Independently verified (15/15 targeted tests, temp-repo probes):

- E1 (rename commit then re-id commit): full scan catches it (1 error).
  I also reproduced tooling's deviation evidence first-hand: scanning
  only the two endpoints via _scan_rev(HEAD) + _scan_rev(merge-base)
  yields ZERO errors: the working tree equals HEAD, and against the
  merge-base both name and id differ, indistinguishable from
  delete-plus-new. My prescribed two-rev union was insufficient;
  tooling's intermediate-commit scan is the correct strict superset.
  Deviation accepted, evidence confirmed.
- E2 no-narrowing re-confirmed: uncommitted re-id after a committed
  rename fails identically with and without the baseline flag (1, 1).
- Dedup: same dashboard re-id'd twice across the range surfaces BOTH
  distinct old ids (2 errors); an identical finding visible from three
  revs dedupes to one. Distinct findings are not swallowed.
- Non-ancestor still hard-fails; unresolvable baseline still degrades
  loudly to HEAD-only (re-confirmed on the real corpus with a bogus
  rev: warning present).
- Cost: synthetic 50-commit PR range with 8 dashboards: 7.2s, 821 git
  subprocess calls (~16 per rev). Real corpus with the actual 7-commit
  merge-base range: 3.2s vs 1.1s without the flag. Default local
  validate is unchanged (HEAD-only, ~17 calls). Acceptable: the
  per-commit cost exists only in CI on PR events and is linear in
  range x corpus.

### WARNING (new, open)

- [id_guard.py intermediate scan, by design] Revert-in-range false
  failure, reproduced: a PR that commits a re-id mistake and then
  reverts it has a clean tip (working tree == HEAD == baseline
  identity) but still hard-fails, because the intermediate commit
  published the name under the other id; worse, the error's advice is
  inverted in this case ("Fix: restore the original id (<the bad
  id>)"). This is the irreducible price of the E1 coverage (offline,
  the guard cannot know which committed state was installed), and the
  factory's install-per-round workflow justifies treating every
  committed state as possibly installed. Recovery is squash/rebase of
  the PR branch. Fix: when the working tree matches both endpoints,
  reword the error to say an intermediate commit is the source and
  name history rewrite as the remediation; document in the flag help.

### NIT (new, open)

- [id_guard.py rev-list] The scanned range is unbounded: a stale PR
  branch that merged main mid-PR pulls main's commits into
  baseline..HEAD, scaling CI cost linearly (extrapolated ~70s at 500
  commits) and exposing the guard to findings originating in merged-in
  main history. Consider --first-parent or a capped range with a loud
  could-not-cover warning.

### Ledger after delta 3

- BLOCKING: none open (delta-2 BLOCKING resolved by dc2f957).
- WARNING open: revert-in-range false failure with inverted advice
  (above); case-sensitive name compare vs unverified importer case
  semantics (carried, follow-up).
- NIT open: unbounded rev-list range (above); duplicate names in a
  committed tree collapse last-wins (carried); ls-tree parsed without
  -z / quotepath (carried).
- Resolved this round: delta-2 BLOCKING (substitute-not-widen);
  delta-2 ci.yml silent-fallback NIT (799955a).
- Verdict after delta 3: **APPROVE**.
