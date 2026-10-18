# Framework review: validator-installer batch (#203, #202, #198, #199)

- Branch: `fix/validator-installer-batch`, `c433366..be10168` (7 commits)
- Reviewer: framework-reviewer (RULE-013), 2026-10-18
- Verdict: **CHANGES REQUESTED** (1 BLOCKING / 2 WARNING / 3 NIT)

The four fixes do what they claim on every path I could exercise. What
blocks is one of the new tests: whether it passes depends on test order,
and it went red in one of my three runs shaped like CI.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (pak clones symlinked read-only) | all seven rc=0 |
| Full suite, xdist `-n 4 --dist=loadgroup`, no pak clones | 13 failed: 12 environmental (the same 12 fail on base `c433366`, not six) + **1 new: `test_validate_sdk_project_surfaces_the_error`** |
| Full suite `tests/`, xdist, clones linked, twice | 2251 passed both times |
| Plain `pytest tests/` (serial, not-slow) | 2120 passed |
| Render regression | n/a: no renderer, template, builder or assembly change, so no rendered output moves and no dist zip goes stale |
| pak-compare | n/a: no pak structure change |

The pak clones in the main checkout were unchanged before and after
(`git status` hash per clone), and the symlinks have been removed.

## BLOCKING

**B1. `tests/test_sdk_validate_symptomsets.py:129`: the test's result depends on run order.**
At module top the test imports `validate_sdk_project` from
`vcfcf_managementpacks.sdk_builder`.
`tests/test_release_builder_phase2.py:583` removes that module from
`sys.modules`. After that, the test's in-body
`import vcfcf_managementpacks.sdk_builder as sb` loads a second copy. The
monkeypatches go onto that copy, but `validate_sdk_project` still runs
against the first one. The real `load_sdk_project` then rejects
`name: probe`, the function returns early, and the assertion fails.
- Reproduced deterministically with
  `pytest tests/test_release_builder_phase2.py tests/test_sdk_validate_symptomsets.py`.
- It also failed in my first full xdist run. CI runs `-n auto --dist=loadgroup`
  (`.github/workflows/ci.yml:106`), so whether CI goes red depends on how
  tests are distributed across workers.
- Authority: reviewer dimension 7 (a framework change that turns the
  suite red).
- Fix: call `sb.validate_sdk_project(tmp_path)` inside the test, the same
  way the `build_sdk_pak` tests in the same file already reach through
  `sb`, and drop the module-top import of `validate_sdk_project`.

## WARNING

**W1. `src/vcfcf_managementpacks/installer.py:734` / `:811`: a missing `version` field counts as a version mismatch.**
- If the matched `installedMPs[]` entry has no `version`, or a blank one,
  it normalizes to `""`. The installer then re-reads for the full 30 s
  window and exits 1 with "the pak manager most likely failed to apply
  the adapter". I confirmed this with a scripted fake (both absent and
  empty: exit 1).
- Recorded shapes:
  - `vcf_operations_api_surface.md:306` (9.x field list includes `version`).
  - `pak_uninstall_api_exploration.md` §step 2 (sample `"1.0.1.6"`, equal
    to the pak version).
  - `vcommunity_upgrade_path_experiment.md` §5 (manifest 1.0.0, and
    getIntegrations reports 1.0.0).
- So on 9.x the field is present and carries the manifest version
  string. Same-version reinstalls pass, and trailing-`.0` differences
  pass.
- No 8.18 getIntegrations shape is recorded anywhere in `knowledge/`.
  "Cannot false-fail on 8.18" is therefore unproven, and under the
  skeptic default that makes it a finding.
- Fix: when the matched entry carries no version, WARN and print
  `OK: Install completed (version unverified)`, mirroring the existing
  no-expected-version branch. Abort only when the version is present and
  different. Add a test for the absent-field case.

**W2. `src/vcfcf_managementpacks/buildkit.py:85`: kit contents changed, but the version did not.**
- `BUILDKIT_VERSION` is still `1.0.11`, which was tagged and published on
  2026-10-07 (`sdk-buildkit-v1.0.11`, `802a517`). This batch changes what
  the kit contains: the SymptomSets gate in `sdk_builder.py`, the new
  `dashboard_widget_versions.py`, and new loader warnings.
- `publish-buildkit.yml` stamps the version from the tag, so a published
  tarball cannot carry the wrong label. A local `build-buildkit` run,
  however, would stamp 1.0.11 on different contents.
- More important operationally: nothing in the batch says that the #203
  guard reaches compliance release CI (`BUILDKIT_TAG: sdk-buildkit-v1`)
  only after a new buildkit tag is cut. Until then, a tagged compliance
  release still builds with the old kit, which has no check. This is the
  dimension 9 "signal, not just artifact" class, applied to the buildkit.
- Fix: bump `BUILDKIT_VERSION` to `1.0.12`, and say in the result block
  and the PR body that `sdk-buildkit-v1.0.12` must be tagged after merge.

## NIT

**N1. `knowledge/context/api-surface/pak_install_api_exploration.md:525`: the doc overstates what a version match proves.**
It says `version` is "the only field that distinguishes success from
that failure", and the success line still reads "verified".
`vcommunity_upgrade_path_experiment.md` §5 records a case where the
getIntegrations version moved to the new pak's version but the describe
was never applied. A version match is necessary but not sufficient. Add
one sentence citing that experiment.

**N2. `src/vcfcf_managementpacks/sdk_builder.py:915` and `:937`: every warning prints twice.**
Bundled dashboards are validated twice, so every #198 and #199 warning
appears twice per dashboard on `build-sdk` and `validate` (seen both in
the isolated kit and through the factory CLI). The double validate
existed before this branch, but this branch adds the first warnings that
fire routinely on good content. Fix: record and discard warnings around
the second `d.validate` call, or deduplicate by message.

**N3. `src/vcfcf_managementpacks/installer.py:398`: requests have no HTTP timeout.**
`solution_action` sets no HTTP timeout. The settle loop itself is bounded
by its time check (a 3 s window measured 3.0 s, so the overrun is at most
one poll interval of 5 s by default). But a single getIntegrations re-read
that hangs is unbounded, and the loop adds up to seven such reads. This
code predates the branch and the branch does not touch it, so per
delegation rule 9 it becomes a follow-up issue, not a fix here.

## Proven safe (independently)

- **#203, all three entry points fail the same way.** I built a fixture
  with the build-90 one-child shape (namespaced describe) and ran it
  through:
  - factory `validate-sdk`: rc 1;
  - factory `build-sdk`: rc 1;
  - the kit's own `python3 -m sdk_buildkit build-sdk --release`, using a
    kit assembled with `_assemble_kit_python_only`, `PYTHONPATH` set to
    the kit only, cwd `/tmp`: rc 1.

  All three print the identical message naming
  `vcfcf_compliance_overrides_vcenter`, and the check runs before the
  Java step.
- **#203, no false positives.**
  - All 7 pak clones that have a `describe.xml` produce 0 errors
    (compliance has 2 composites).
  - 63 describes extracted from the 58 vendor paks under `reference/`
    contain 512 `<SymptomSets>` composites and 0 flags. That is vendor
    ground truth that the two-child minimum holds.
  - The Tier 1 alert renderer (`vcfcf_core/alerts/render.py:410-418`)
    wraps only when there are 2 or more sets.
  - `describe.xml` is copied into the pak verbatim (`sdk_builder.py:1162`),
    so the file that gets checked is the file that ships.
- **#202.**
  - Build 90 over 89 aborts, and matching versions pass.
  - Same-version reinstall passes, and `1.0.0` matches `1.0.0.0`.
  - Manifest version takes precedence over the upload reply.
  - The settle window is bounded (see N3 for the per-request caveat).
  - No endpoint changes.
- **#198.**
  - All seven validates exit 0.
  - An independent YAML scan of `content/dashboards`, `third_party`,
    `bundles` and the pak clones finds exactly six names over 50
    characters: 4 factory (in `dashboards validate`) and 2 compliance (in
    `managementpacks validate`), and every one is listed.
  - No code path turns a `UserWarning` into an error (checked every
    `catch_warnings` / `w.message` consumer under `src/`).
- **#199.**
  - The isolated kit ships `dashboard_widget_versions.py` with the import
    rewritten, has no `vcfcf_` imports left, loads a bundled Section
    dashboard, raises the warning, and reaches the Java step.
  - `test_table_covers_every_type_the_validator_accepts` asserts that the
    table keys equal the loader's supported set, so the table cannot drift
    away from what the loader accepts.
  - An unknown type still hard-fails in the loader.
- **Global-default leak, key collision, silent downgrade.** None found.
  The batch changes no rendered output on any path: the import-zip, pak
  and extractor paths see warnings only, and no keys or labels are
  derived.
- **Em-dashes.** There are none in the added lines or in any of the seven
  commit messages.

## If shipped as-is

CI goes red intermittently on a test this branch added. On an instance
whose getIntegrations entry has no `version` field, a good pak install
reports failure. And a tagged compliance release keeps building without
the #203 guard until someone cuts a buildkit tag that nothing in this
batch asks for.

## Round 2 (re-review of dfb5db4, f080cc2, 044743e, 5bca10a)

- Diff reviewed: `git diff d81c730..HEAD` (11 commits on `c433366`)
- Verdict: **APPROVE** (0 BLOCKING / 0 WARNING / 0 NIT open)

Every round-1 finding except N3 is resolved, and I verified each fix
myself. N3 (no HTTP timeout in `solution_action`) is in code this branch
does not touch, so it is still a follow-up issue rather than a fix here,
per delegation rule 9.

### Checks re-run

| Check | Result |
|---|---|
| The pair `tests/test_release_builder_phase2.py tests/test_sdk_validate_symptomsets.py`, `-m "" --override-ini="addopts="`, xdist `-n 4`, 6 runs | 44 passed in all 6 |
| The same pair run serially, release_builder first (round 1's guaranteed failure) | 44 passed |
| Full `tests/`, xdist at `-n 4`, `-n 3`, `-n 2`, no pak clones | 2238 passed in each run. The 12 failures are the same 12 environmental tests that fail on base `c433366` (missing pak clones), with nothing new |
| Full `tests/`, xdist `-n 4`, pak clones linked read-only | 2256 passed, 0 failed |
| Seven-package validate chain (clones linked) | all seven exit 0. Managementpacks validate now prints exactly 2 `issue #198` warnings, one per over-length compliance dashboard, down from 4 |
| Pak clones in the main checkout before and after | unchanged. Links and scratch removed |

### Round-1 findings

- **B1, fixed.** The test now reaches `validate_sdk_project` through the
  in-body `sb` import, and only the pure `_validate_describe_symptom_sets`
  is still imported at module top. The test passed in every run above,
  including the serial order that failed every time in round 1.
- **W1, fixed.** I re-ran the round-1 scripted fake against both
  verification paths (adapter_kinds and name-only):
  - absent, empty or `None` version: `OK ... (version unverified)` plus a
    WARN that the entry "carries no version", after 1 call with no
    re-read wait;
  - same version, or a trailing `.0`: OK;
  - an older version (`1.0.0.89` against `1.0.0.90`): exit 1 after the
    3 s window (4 calls, 3.0 s).

  Four new tests cover this.
- **W2, fixed.** `BUILDKIT_VERSION = "1.0.12"`, and the assembled kit
  reports 1.0.12. The `tier2_architecture.md` changelog row states that
  the #203 guard reaches tagged pak releases only after
  `sdk-buildkit-v1.0.12` is tagged and `sdk-buildkit-v1` moves to it.
  **That tag is a post-merge step for the orchestrator. Until it exists,
  compliance tagged releases still build with 1.0.11.**
- **N1, fixed.** `pak_install_api_exploration.md` now says a version match
  is necessary but not sufficient. It cites
  `vcommunity_upgrade_path_experiment.md` §5 and records the
  missing-version case.
- **N2, fixed.** The second `d.validate` call in `_load_bundled_content`
  now runs with warnings ignored, and errors still raise. On the isolated
  kit build, each warning prints once (2 lines for 2 advisories).
- **N3.** Unchanged, as above: a follow-up issue.

### #203 kit path, re-checked

I re-assembled the kit with `_assemble_kit_python_only` and ran it with
`PYTHONPATH` set to the kit only and cwd `/tmp`.
- `sdk_buildkit build-sdk --release` on the one-child fixture exits 1 with
  the `vcfcf_compliance_overrides_vcenter` SymptomSets message.
- The valid fixture, which carries a Section widget and an over-length
  name, loads the dashboard, warns once per advisory, and reaches the Java
  step.
- Factory `validate-sdk` and `build-sdk` on the one-child fixture both
  exit 1 with the same message.

### New code in this round

- The settle loop now re-reads only on a known mismatch. If a re-read
  comes back with no version, the loop exits to "unverified", not to
  abort, which matches the W1 contract.
- The name-only path aborts on a known mismatch and only warns on a
  missing version.
- Rendered output, keys and the import-zip path are unchanged, so there
  is still nothing for render regression or pak-compare to check.
- Em-dashes: none in the added lines (`d81c730..HEAD`) and none in the
  four new commit messages.
