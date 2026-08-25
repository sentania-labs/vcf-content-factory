# Framework review: dashboards id-stability guard (issue #113)

- Branch: fix/113-dashboard-id-guard, commits 557d446 + 99f2660 vs origin/main
- Files: src/vcfops_dashboards/id_guard.py (new), src/vcfops_dashboards/cli.py
  (validate hook), tests/test_dashboard_id_guard.py (new, 9 tests)
- Reviewer: framework-reviewer, 2026-08-25 (delta re-check of 99f2660 same day)
- Verdict: **APPROVE** (0 BLOCKING / 2 WARNING open / 2 NIT; original WARNING 1 resolved by 99f2660)

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
