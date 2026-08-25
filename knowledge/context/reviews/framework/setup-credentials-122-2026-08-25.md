# Framework review: setup-credentials, issue #122 (branch fix/122-not-a-repo-walk, 3769e9b)

Reviewer: framework-reviewer. Base: origin/main (85bdbb1). Verdict: **APPROVE**.

## Change under review

`src/vcfops_common/setup_credentials.py` `_gitignore_status`: on `git
check-ignore` rc=128, a new filesystem walk (`_no_git_above`) restores the
confident "its directory is not a git repo, so nothing there could commit it"
wording only when no `.git` entry exists from the env file's directory up to
the filesystem root. `.git` present anywhere above, or any exception during
the walk, keeps "could not determine". Tests updated/added in
`tests/test_common_setup.py`.

## Checks re-run (independent)

- Validate chain (canonical seven packages, skill s.Validation commands):
  supermetrics, dashboards, customgroups, symptoms, alerts, reports,
  managementpacks: all PASS.
- `tests/test_common_setup.py`: 87 passed. Full suite: 998 passed, 4 skipped.
  Both match tooling's claims.
- Mutation check A: forced `_no_git_above` to always-True via a pytest plugin
  (src untouched);
  `test_a_fatal_git_check_ignore_in_a_repo_is_reported_as_unknown_not_as_safe`
  FAILED as intended. Mutation check B: always-False;
  `test_a_128_with_no_git_anywhere_above_reads_as_not_a_repo` FAILED as
  intended. Both directions of the walk are test-covered.
- Allowed-phrase list (`tests/test_common_setup.py`,
  `test_the_prompt_states_the_gitignore_status_of_the_file_found`): the
  revived "not a git repo" entry is a live substring of the new wording;
  the assertion executes and passes on the real-git path (parent `.env`
  outside any repo now yields the confident wording end to end).

## False-confidence hunt (rc=128 with a REAL repo)

Probed by direct execution against the built module:

- **Worktree/submodule `.git` FILE**: `_no_git_above` treats a `.git` file as
  present (`Path.exists()` is type-agnostic); verdict stays unknown. Safe.
- **Broken `.git` symlink**: walk reports no repo, confident wording. Git
  itself also sees no repository through a dangling `.git` symlink, so
  "nothing there could commit it" is accurate for that environment. Safe.
- **Permission-denied ancestor hiding a real `.git`**: `Path.exists()` on
  Python 3.12 raises `PermissionError` (EACCES is not in pathlib's ignored
  errno set); the caller's `except Exception` catches it and the verdict
  degrades to "could not determine". Verified end to end. Safe direction.
- **Symlink loop in the path**: `resolve()` raises `RuntimeError`, caught by
  the caller; verdict "could not determine", no crash. Verified.
- **GIT_DIR pointing at a valid repo from a plain directory**: check-ignore
  returns 0/1 (verified rc=1), so the walk is never consulted and the
  operator gets the commit-risk warning. **GIT_DIR pointing at garbage**:
  rc=128, walk says not a repo; accurate, since git cannot commit through a
  bogus GIT_DIR either. The only theoretical miss is GIT_DIR naming a repo
  that itself fatals on check-ignore for a non-discovery reason; at that
  moment the repo is broken for the operator too. **Assessed acceptable**:
  every reachable combination either warns or degrades to unknown; nothing
  reachable prints confident wording over a functioning repo.
  GIT_CEILING_DIRECTORIES errs the other way (walk sees `.git`, git does
  not) which lands on unknown, the safe direction.
- **Bare repo above**: a bare repo has no `.git` entry and no work tree;
  check-ignore fatals there and the walk reports no repo. Nothing can commit
  a file under a bare repo without attaching a worktree, so the wording holds.

## Other dimensions

- RULE-008: argv still carries only paths/filenames; no secret introduced.
- Timeout (`_GIT_CHECK_TIMEOUT`), rc 0/1 verdicts, default-No prompt:
  untouched, confirmed in diff and by the unchanged
  `test_git_check_ignore_exit_codes_zero_and_one_keep_their_verdicts`.
- Stale-zip / template-version: files touched are not in the staleness
  trigger set (no packaging templates, builders, or dashboards render);
  no rebuild or `CURRENT_TEMPLATE_VERSION` bump owed.
- Wire formats, renderers, pak structure: not touched; n/a.

## Findings

BLOCKING: none. WARNING: none.

NIT:
1. [src/vcfops_common/setup_credentials.py:_no_git_above] GIT_DIR /
   GIT_WORK_TREE can define a repo the ancestor walk cannot see. All
   reachable combinations were shown safe above, but bailing to unknown when
   either variable is set in the environment would close the theoretical
   window at zero cost.
2. [tests/test_common_setup.py:test_a_128_with_no_git_anywhere_above_reads_as_not_a_repo]
   assumes pytest's tmp base has no `.git` ancestor; true under any normal
   TMPDIR, fragile only if TMPDIR is placed inside a checkout.

## If shipped as-is

An operator whose `.env` sits in an ordinary non-repo directory again sees
the honest confident wording instead of "could not determine"; every
broken-repo, worktree, and permission edge still reads as unknown or as an
explicit commit-risk warning, never as safe.
