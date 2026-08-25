# Framework review: publish _git_commit collapse (#126)

- **Branch:** fix/126-git-commit-collapse (bebbbf3) vs base fix/125-publish-test-speed (5a4f8dd)
- **Scope:** src/vcfops_packaging/publish.py only (net -25 lines). #125 base reviewed separately (APPROVE); this review covers only the #126 delta.
- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 2 NIT)

## Change

`_git_commit()` gains `allow_empty: bool = False` which appends
`--allow-empty` to the git commit argv. The two duplicated ~14-line
force blocks (PR mode and direct-push mode in `_publish_inner`) are
deleted; all four commit sites collapse to
`_git_commit(dist_repo, commit_msg, commit_body, allow_empty=force)`.

## Independent verification (all re-run by reviewer)

| Check | Result |
|---|---|
| Validate chain (7 content packages + `vcfops_packaging validate`) | pass |
| Full default suite `pytest tests/` | 1058 passed, 4 skipped, 127 deselected (matches author claim) |
| Targeted `test_publish_pr_mode_v4.py` + `test_publish_phase3.py` | 58 passed, 1 deselected |
| Mutation probe: append name list to the single remaining subject-construction site (publish.py ~1329) | `TestCommitMessageShape::test_commit_subject_is_counts_only` FAILED in both parametrizations (pr_mode, direct_push); source restored, `git diff` clean afterward |

## Dimension walk (per orchestrator brief)

**(a) Force-block deletion, argv old vs new.** Byte-identical in both
modes: `git add -A -- :!.publish.lock` then
`git commit --allow-empty -m <subject> [-m <body>]` via the same
`_commit_message_args`. Same working dir (`_git(dist_repo, ...)`), no
env, no logging in the old blocks. Two behavior deltas, both cosmetic
or unreachable (see NITs).

**(b) "nothing to commit" None path.** Non-force behavior unchanged
(default `allow_empty=False`, argv identical to pre-change
`_git_commit`). Old force blocks set `result.commit_sha` inline and
returned no value; only consumer was `result.commit_sha`, which the new
code populates with the same shape (str, or None only if rev-parse
fails, identical to the old `r2.returncode` guard). Downstream gating
unchanged: PR mode never gated on `commit_sha` (old or new); direct-push
gates on `result.commit_sha and not no_push` exactly as before, and
`--allow-empty` guarantees a SHA in force mode, so force still pushes.

**(c) Subject and body construction.** Untouched by the delta; single
construction site remains at publish.py ~1329-1337.
`test_force_path_matches_normal_path` pins subject AND body equality in
both modes and stayed green; the counts-only pin (subject + body
content, per #127) caught the mutation in both modes. Force parity test
remaining green under mutation confirms force and normal share the one
site.

**(d) Other callers.** `grep` confirms exactly two `_git_commit` call
sites, both in `_publish_inner`, both passing `allow_empty=force`. No
test or other module references `_git_commit`. Default `False` preserves
every pre-existing caller's behavior.

**Test coverage (dim 10).** `allow_empty=True` is functionally covered:
`test_publish_phase3.py::test_force_commits_when_unchanged` publishes
byte-identical content with `force=True` and asserts a new commit;
dropping `--allow-empty` would return None ("nothing to commit") and
fail it.

**Stale-zip / template version (dim 9).** Delta touches neither
`src/vcfops_packaging/templates/`, `builder.py`, `discrete_builder.py`,
`release_builder.py`, `render.py`, nor `template_version.py`. No rebuild
or `CURRENT_TEMPLATE_VERSION` bump required. Confirmed via diff stat
(publish.py + one review doc only).

**Wire formats.** n/a; change is git plumbing, no emitted content
format touched.

## NITs

1. [publish.py:~365] The unified failure path now maps a force-mode
   commit failure whose output contains "nothing to commit" to a silent
   None instead of the old unconditional `PublishError`. Unreachable in
   practice (`git commit --allow-empty` does not fail with that text),
   but it is a theoretical error-swallow the old force block did not
   have. No action required.
2. [publish.py:~368] Error text lost the "(force)" tag
   ("git commit failed" vs "git commit (force) failed"). Cosmetic; no
   test pinned the old text.

## If shipped as-is

Operators see identical publish behavior in all four mode combinations;
force publishes still land an empty commit and push/PR exactly as
before, with 25 fewer lines and one commit path instead of three.
