# Framework Review — buildkit `--release` flag parity (PR #32)

- **Area:** `vcfops_managementpacks/buildkit.py` (`_KIT_MAIN` template) + `tests/managementpacks/test_buildkit_release_flag.py`
- **Change:** Add `--release` to the generated `sdk_buildkit` CLI's `build-sdk` subparser + inlined `_apply_release_flag` (sets `VCFCF_RELEASE_BUILD=1`), closing the PR #32 BLOCKING where every CI `v*` release build `argparse`-exited on `unrecognized arguments: --release`.
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT
- **Date:** 2026-07-02
- **Branch:** `feat/cross-mp-stitch-cp-identity`

## Checks re-run (independently)

- **validate chain:** PASS — all 7 packages green (24 SM, 16 views/6 dashboards, 3 groups, 17 symptoms, 9 alerts/10 recs, 1 report, 5 Tier 1 + 6 Tier 2 MP).
- **tests:** 460 passed / 4 skipped (162 deselected) — matches expected. New file: 3 passed.
- **render-regression:** n/a (no renderer/loader/builder-output surface touched).
- **pak-compare:** n/a (no pak structural change; version-line stamp is the intended, guardrailed behavior).

## Verification of the four review-focus claims

1. **Inline-vs-import is justified (not lazy).** Confirmed `_FACTORY_SOURCES` (buildkit.py:81-97) does **not** contain `cli.py` — only `sdk_builder.py`, `sdk_project.py`, `pak_compare.py`, the flattened `provenance.py`, and the `vcfops_dashboards/supermetrics/symptoms/alerts/reports` loaders/renderers. `cli.py` is genuinely absent from the kit tarball manifest, so a kit `__main__.py` that did `from ...cli import _apply_release_flag` would raise `ModuleNotFoundError` on a clean CI checkout. The duplication is contractually required by the kit's self-containment boundary. Not a WARNING.

2. **Parity is exact.**
   - `cli.py:414-424` — `if getattr(args, "release", False): os.environ["VCFCF_RELEASE_BUILD"] = "1"`.
   - kit `_KIT_MAIN` (buildkit.py:354-364) — `if getattr(args, "release", False): os.environ["VCFCF_RELEASE_BUILD"] = "1"`.
   - Same env var (`VCFCF_RELEASE_BUILD`), same value (`"1"`), same only-when-passed `getattr(..., False)` truthiness. The only textual difference is `import os as _os` (cli.py, function-local) vs the kit's module-level `import os` (already present at `_KIT_MAIN` header) — semantically identical.
   - Consumer parity: `sdk_builder._is_release_build()` (sdk_builder.py:299-301) accepts `_RELEASE_BUILD_TRUE_VALUES = {"1","true","yes"}`, so `"1"` flips the stamp. Confirmed.

3. **Test proves the STRONG property.** `test_buildkit_release_flag_stamps_declared_version` asserts `version stamp -> release build -> 1.2.3.42` is on the assembled kit's subprocess stderr — i.e. `VCFCF_RELEASE_BUILD=1` propagated through the kit's own `_apply_release_flag` into `sdk_builder._is_release_build()` and flipped the version line — not merely that argparse accepted the flag. The default-build test asserts the inverse (`dev preview -> 0.0.0.42`, and `release build` absent). Host-env leakage is guarded (`env.pop("VCFCF_RELEASE_BUILD", None)`). The stamp log lands before `_ensure_framework_jar()`, so it is reliably present despite the expected downstream no-SDK-jar failure.

4. **No collateral.** The `_KIT_MAIN` edit adds only the `--release` argument to the `build-sdk` subparser and one `_apply_release_flag(args)` call inside the `build-sdk` branch of `main()`. `validate-sdk`, `pak-compare`, the mutually-exclusive reference-pak group, and the `_apply_sdk_jar` path are untouched. `test_buildkit_isolated_build.py` (which assembles the same template) still passes in the full suite. CI template `knowledge/designs/sdk-template-scaffold/build-pak-on-tag.yml:144-145` already passes `--release`; the kit parser now matches it.

## Dimension walk

- **Global-default / pak-specific leak (00d3382):** N/A. `--release` defaults to `False` (explicit opt-in); no default, coordinate, or flag leaks onto any global path. The dev-preview `0.0.0.N` stamp is the safe default — a hand/local build is never version-indistinguishable from a release.
- **Key/label collision (6c59f6b):** N/A.
- **Wire-format conformance:** The change enforces the pak version-line guardrail (RULE-014 / `knowledge/rules/pak-version-lines.md`) on the CI path that was previously crashing. Conforms.
- **Loader/validator, render regression, builder structure:** N/A — no loader/renderer/builder-output surface touched.
- **Corpus regression:** None — validate chain clean, 460 passed.
- **Silent capability change:** This is a *restoration*, not a downgrade — release builds were crashing at argparse; they now succeed. No silent drop.
- **Stale-zip discipline (dimension 9):** Not triggered. `buildkit.py` is not `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or `vcfops_dashboards/render.py`, so `dist/` zips are not stale. (Separate, expected: the published `sdk-buildkit` tarball is stale relative to this fix until a new buildkit release is cut — see "if shipped as-is".)
- **Test coverage:** 3 new tests covering parse + both stamp outcomes via the assembled kit. Strong coverage of the exact escape.

## NIT

- [tests/managementpacks/test_buildkit_release_flag.py:184,200,217] `@pytest.mark.timeout(60)` is an unregistered mark (no `pytest-timeout` plugin / no marker registration) — it is a silent no-op emitting `PytestUnknownMarkWarning`. The real guard is `subprocess.run(..., timeout=55)` in `_run_kit_build_sdk`, so behavior is fine, and this mirrors the pre-existing sibling `test_buildkit_isolated_build.py`. Non-blocking; if desired, register the marker or drop the decorators for consistency.

## If shipped as-is

CI `v*` release builds now parse `--release` and stamp the real `adapter.yaml` version line instead of dying at argparse — the PR #32 BLOCKING is genuinely closed. Operationally note: the fix lives in the `sdk_buildkit` kit template, so it only reaches adapter CI once a **new buildkit release** (`sdk-buildkit-v*`) is published from this branch; existing adapter CI pulling the old kit tarball stays broken until then. That is expected release mechanics, not a defect in this diff.
