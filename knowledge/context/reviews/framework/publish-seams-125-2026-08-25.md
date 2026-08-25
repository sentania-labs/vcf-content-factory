# Framework review: publish() test seams (issue #125)

- Branch: fix/125-publish-test-speed, commit 1974c9a vs origin/main
- Reviewer: framework-reviewer, 2026-08-25
- Verdict: **APPROVE** (0 BLOCKING, 0 WARNING, 2 NIT)

## Change under review

`publish()` in `src/vcfops_packaging/publish.py` gains two keyword-only
test seams (`validator`, `build_one_release`) defaulting to `None` and
resolved at call time inside `_publish_inner` to the real
`_run_validators` / `_build_one_release`. New `tests/publish_seam_stubs.py`
and `tests/test_publish_seams.py`; `test_publish_pr_mode_v4.py` fully
stubbed; `test_publish_phase3.py` stubbed with two carve-outs
(`test_real_run_zip_lands` fully real, slow+real_corpus;
`TestPolicyCaveatInReadme` real builder, real_corpus). `tests/README.md`
marker tables updated.

## Silent-downgrade hunt (dimension 8, the priority)

- **Call sites.** `grep` over `src/`, `scripts/`, `.claude/`: the only
  production caller is `cmd_publish` in `src/vcfops_packaging/cli.py:1388`,
  which passes neither seam. No env var, no config key, no partial
  application, no other importer of `publish` in `src/`. The only way to
  skip validation is an explicit keyword at a call site.
- **Default timing.** Defaults are `None`; resolution to the module
  globals happens inside `_publish_inner` at call time, so no stale
  def-time capture and monkeypatching the real functions still works.
  No import cycle introduced (`typing.Callable` only).
- **Proof defaults are real.**
  `test_publish_seams.py::TestDefaultsAreReal` monkeypatches the module
  globals and calls `publish()` uninjected: both hooks fire. Guards the
  drift-to-stub failure mode with an executing branch, not a string check.
- **Stub helper is test-only.** `tests/publish_seam_stubs.py` is not a
  package and not importable from `src/`; `stubbed_publish` uses
  `setdefault` so explicit real-builder injection (TestPolicyCaveatInReadme)
  works.

## Behavior assertions on failure paths (executing branches)

`test_publish_seams.py` asserts, by executing the branch:
- failing injected validator: PublishError raised, builder never called
  (abort ordering), commit count unchanged, `.publish.lock` released;
- failing injected builder: PublishError, no commit, lock released;
- injected validator invoked exactly once with the resolved factory repo.

Verified pass in 2.95s.

## Anti-drift end-to-end

`test_publish_phase3.py::test_real_run_zip_lands` imports the real
`publish`, runs the real eight-validator chain and real zip builder, and
now asserts the landed zip is genuine multi-member builder output
(`"stub.txt" not in names`, `len(names) >= 2`). The stub routes dest
subdirs/filenames through the real `release_builder` private helpers
(`_artifact_dest_subdir`, `_is_sdk_adapter_source`, `_zip_filename`), so a
rename there breaks the stub loudly rather than silently diverging.
Zip-internal README assertions (TestPolicyCaveatInReadme) inject the real
`_build_one_release`, so no stub content is ever load-bearing for a README
assertion.

## Independent re-runs (this machine)

| Run | Result | Time |
|---|---|---|
| `tests/test_publish_seams.py` | 4 passed | 2.95s |
| 3 publish files, default markers | 62 passed, 1 deselected | 20.9s |
| 3 publish files, `-m "" --override-ini=addopts=` | 63 passed | 209s (was 2h+) |
| Mutation probe: `retired` -> `withdrawn` in commit subject | TestCommitMessageShape fails 2 (pr_mode + direct_push) in 7.9s; reverted, tree clean | pass |
| Full default suite `pytest tests/ -q` | 1058 passed, 4 skipped, 127 deselected | 104s |

The end-to-end run also exercises the full eight-validator chain against
the real corpus (it is step 2 of `test_real_run_zip_lands`), so corpus
validation is confirmed green on this branch.

Author's timing claims confirmed within machine variance (author 294s for
`-m ""`, observed 209s). Mutation-teeth claim confirmed: subject mutation
caught by the stubbed tests in both pr_mode and direct_push
parameterizations (author observed only direct_push failing for the
force-block mutation; my probe hit the shared subject string, both fail,
consistent).

## Marker / README accuracy (dimension 10, f)

- `pyproject.toml` default `addopts = -m "not slow"`; only
  `test_real_run_zip_lands` carries slow now, correctly deselected (62/1).
- `TestPolicyCaveatInReadme` in default loop: real builder, validator
  stubbed, within the 21s three-file total; acceptable, matches README's
  "~3s/test" claim.
- `tests/README.md` table removals and the new paragraph match the code
  exactly.
- Stale-zip discipline (dimension 9): `publish.py` is not in the
  templates/builder/render stale set; `CURRENT_TEMPLATE_VERSION` correctly
  untouched, production behavior is bit-identical when uninjected.

## Findings

BLOCKING: none.
WARNING: none.
NIT:
1. `tests/publish_seam_stubs.py` docstring says "seven-package validator
   chain" in the opening paragraph but "eight `python3 -m <pkg> validate`
   subprocesses" later; `_VALIDATORS` has eight entries. Cosmetic
   inconsistency inherited from the issue text.
2. `tests/test_publish_seams.py` docstring claims "Nothing here reads ...
   the real content/ corpus"; the release manifest points at a real
   `content/dashboards/...yaml` path (existence-checked during enumerate).
   No concurrency hazard (stub builder never opens it), but the sentence
   is slightly overbroad.

## If shipped as-is

Production `/publish` behavior is unchanged; the developer loop for
publish orchestration changes drops from 2h+ to under 4 minutes under
`-m ""` with the real end-to-end path still guarded.
