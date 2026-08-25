# Framework review: publish commit subject / PR title counts-only

- **Area:** `src/vcfops_packaging/publish.py` (+ `tests/test_publish_pr_mode_v4.py`, two design docs)
- **Branch:** `fix/publish-commit-subject-counts-only` (`9a805a6`, `c8fe6f9`) vs `main` @ `eb82d77`
- **Date:** 2026-08-24
- **Reviewer:** framework-reviewer (RULE-013 blanket gate)
- **Verdict:** APPROVE (0 BLOCKING, 1 WARNING, 3 NIT)

## Change under review

Commit subject and PR title become counts-only; release names move to the
commit body and to a new unconditional `## Released in this batch` PR-body
section. New `_commit_message_args()` helper builds repeated `-m` args;
`_git_commit()` gains an optional `body`.

## Checks re-run (independent)

| Check | Result |
|---|---|
| Seven-package validate chain (RULE-005) | exit 0 |
| `pytest tests/` (default markers) | 996 passed, 4 skipped, 183 deselected |
| New/changed publish tests, `-m ""` | 6 passed (7m26s) |
| Mutation probe of the force-path pin | pin **fails** as designed (see below) |
| `release-publish:` consumer sweep (repo, `.claude/skills`, `.claude/commands`, `.github`, `scripts`, `../vcf-content-factory-bundles`) | no external consumer |
| `pak-compare` / render regression | n/a (no renderer, builder or template change) |

## Claim-by-claim

### 1. All commit-construction paths use the helper — CONFIRMED

There are **four** commit call sites in `publish.py`, not three, and all four
are converted:

- `publish.py:344` `_git_commit()` (`*_commit_message_args(message, body)`)
- `publish.py:1317-1322` PR-mode `--allow-empty` force path
- `publish.py:1333` PR-mode normal path
- `publish.py:1394-1399` direct-push `--allow-empty` force path
- `publish.py:1410` direct-push normal path

`grep` for `"commit"` in `src/` finds no other unconverted site in
`publish.py`. `cli.py:953` / `cli.py:1309` emit `release: <slug> <version>`
for the `/release` materialize flow, a different command, untouched and out
of scope.

`test_force_path_matches_normal_path` compares **subject and body** across
the two paths, not merely that both succeed. I did not take that on faith:
I ran the test against a runtime mutation that strips the body `-m` pair
from any `commit --allow-empty` (exactly "the force path was never fixed").
The test failed with:

```
AssertionError: Force path body diverged:
  'Built releases:\n- demand-driven-capacity-v2\n\n' vs '\n'
```

The pin has teeth. (Mutation applied via an out-of-tree pytest plugin;
no framework source was modified.)

### 2. The PR-body hole was real and is closed — CONFIRMED

At `eb82d77`, `_assemble_pr_body` emitted a release name only inside the
notes loop, gated on `r.release_notes and r.release_notes.strip()`. The
files-changed section lists only files git reports changed, and
`_copy_if_changed` (`publish.py:162-179`) returns `False` for a semantically
identical rebuild, so it contributes no entry. A notes-less, byte-identical
release was therefore visible **only in the title**; once names left the
title it would have vanished from the PR entirely.

The new section (`publish.py:487-496`) is gated on `built_names` alone,
sits above and outside the notes loop, is sorted for stable diffs, and
`test_body_lists_built_names_without_release_notes` pins name presence,
version presence, exclusion of unbuilt releases, and sort order.
`r.version` is already dereferenced for built releases at the pre-existing
line 505, so the new `version_by_name` comprehension adds no new attribute
risk.

### 3. No caller parses these strings — CONFIRMED

`release-publish` appears only in `publish.py:1283`, the new test regex,
one design-doc line (updated in `c8fe6f9`), and stale agent worktrees under
`.claude/worktrees/` (throwaway). The dist repo
`../vcf-content-factory-bundles` has no `.github/` and no match for the
subject, title, or count phrasing. `.claude/skills/`, `.claude/commands/`,
`.github/`, and `scripts/` have no match. Nothing greps the subject for
names.

### 4. No `template_version` bump required — CORRECT

`template_version.py`'s docstring enumerates four bump triggers:
`templates/install.py`, `templates/install.ps1`, `builder.py` output
structure, `render.py` wire format. The diff touches none of them. Nothing
in the change alters zip contents: it changes only the git commit message
and the `gh pr create` title/body arguments. `_copy_if_changed` and all
builders are untouched. No `content-packager` rebuild is triggered
(CLAUDE.md "After tooling changes" list does not include `publish.py`).

### 5. 72-character budget — HOLDS (claimed figures slightly off)

Measured: `release-publish: 13 built, 0 retired, 0 legacy deleted` = **54**
chars (tooling said 53). Three-digit worst case
`release-publish: 999 built, 999 retired, 999 legacy deleted` = **59**
(tooling said 56). Both comfortably under 72, and the test asserts
`len(subject) <= 72` directly, so the budget is pinned regardless.

## Findings

### WARNING

- **[`src/vcfops_packaging/publish.py:1394-1410` / `tests/test_publish_pr_mode_v4.py:1226`]**
  Direct-push mode (`use_pr=False`, i.e. `/publish --push`) has **no**
  commit-subject or commit-body assertion anywhere in `tests/`
  (`test_publish_phase3.py` and `test_third_party_routing.py` exercise
  `use_pr=False` extensively but never inspect the commit message). The
  new pin exercises PR mode only, so the very divergence class it exists
  to catch is unguarded on the other of the two duplicated force blocks.
  I verified the two blocks are currently identical by reading, which is
  why this is not blocking. → Smallest fix: parametrize
  `TestCommitMessageShape._publish_local` over `use_pr` in
  `test_force_path_matches_normal_path` (four publishes), or factor the
  duplicated force block into one helper so there is only one site to
  diverge.

### NIT

- **[`knowledge/designs/release-lifecycle-v1.md:503`]** The corrected line
  says the `version:` field is used for "the publish commit **body** and
  the PR body ... the names, with versions, go in the body below." The
  commit body emits names only (`publish.py:1287`, `f"- {n}"`); versions
  appear in the **PR** body only. This doc line was corrected because it
  was stale, and it is still not quite what the code does. → Reword to
  "the PR body" or add the version to the commit body line.
- **[claim accuracy]** Subject length claimed 53/56, measured 54/59. No
  behavioral impact.
- **[claim accuracy]** Suite claimed 974 passed / 4 skipped / 183
  deselected; my run reports 996 passed / 4 skipped / 183 deselected on
  the same branch. Identical deselect count with 22 more passes suggests
  the claimed figure predates something already on the branch. Green
  either way; flagged only because unverified numbers were reported as
  verification.

## Dimension walk

1. **Global-default / pak-specific leak (`00d3382`)** — n/a. No renderer,
   no default, no coordinate or flag on any content-import path. The
   change cannot reach emitted content.
2. **Key/label derivation collision (`6c59f6b`)** — n/a. No key or label
   derivation touched. The one derived string (`built_unique`) is now
   *more* deterministic than before (`sorted(set(...))` replaced
   `list(set(...))` for the PR body).
3. **Wire-format conformance** — n/a. No JSON/XML emission changed. Verified
   the change is confined to git argv and `gh` argv.
4. **Loader / validator correctness** — untouched; validate chain exit 0.
5. **Render regression** — n/a, `render.py` untouched.
6. **Builder / pak structure** — n/a, no builder or template touched.
7. **Corpus regression** — validate chain exit 0, suite green.
8. **Silent capability change / downgrade** — this is a *deliberate*
   relocation, not a downgrade, and it is loud: every name that left the
   subject is now in the commit body, and every built name is now in the
   PR body **including** cases the old code silently omitted. Net
   information available to an operator increases.
9. **Stale-zip discipline / version stamp** — correctly not triggered;
   see claim 4.
10. **Test coverage** — five new tests plus one tightened, covering helper
    unit behavior, subject shape, 72-char budget, body content, force/normal
    parity, and the notes-less PR body. Gap noted in the WARNING above.

## If shipped as-is

The next `/publish` produces a 54-character commit subject readable in
`git log --oneline` and in GitHub's PR list, with the 13 release names in
the commit body and in a `## Released in this batch` PR section. An
operator loses nothing and gains visibility for notes-less releases that
previously appeared in the PR title only. `--push` and `--force` publishes
produce the identical shape.

## Side note (not a finding): the 2h test file

`tests/test_publish_pr_mode_v4.py` under `-m ""` costs over two hours
because nearly every test drives a real `publish()`: real git, real zip
builds, and a real seven-package validator subprocess per call. My own
single-test run measured ~100s per `publish()` invocation, almost all of it
validator + build, not git. The `slow` marker keeps this out of the default
developer loop, which is the local half of the problem; CI runs `-m ""` and
pays the full two hours, and in practice nobody can re-run the file locally
to check a message-shape change. That is worth its own issue: tests that
only assert on message or body shape should not be paying for a full corpus
validation and real zip builds. The marker split mitigates, it does not
solve.
