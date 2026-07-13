# Framework Review — buildkit vendored-import rewrite (render_view_def_fragments)

- **Branch / commit:** `fix/buildkit-vendored-import` — single commit `2084887`
- **Base:** `main` @ `0a49183`
- **Area:** `src/vcfops_managementpacks/buildkit.py` (+ `tests/managementpacks/test_buildkit_isolated_build.py`)
- **Reviewer:** framework-reviewer (read-only, pre-PR gate, RULE-013 blanket)
- **Date:** 2026-07-12
- **Verdict:** APPROVE (0 BLOCKING)

## What changed

Adds the missing `_IMPORT_REWRITES["sdk_builder.py"]` rule rewriting the inline
`from vcfops_dashboards.render import render_view_def_fragments`
→ `from .dashboard_render import render_view_def_fragments`. This import was
introduced by PR #49 (`0a49183`, co-bundled-reports feature) and was left
un-rewritten in the published sdk-buildkit-1.0.8 tarball, so
`sdk_builder._write_outer_pak` raises `ModuleNotFoundError: vcfops_dashboards`
on a factory-less CI runner the moment an adapter bundles a report that embeds
a referenced view. Plus two isolated-kit regression tests (one exercising the
report+embedded-view path via `_write_outer_pak`, one canary proving failure
without the rule).

## Independent verification (all re-run by me, not taken from tooling's block)

### 1. `_apply_rewrites` must-match contract — CONFIRMED
`buildkit.py:614-632`: `re.subn` with `if n == 0: raise AssertionError(...)`. A
rule that stops matching fails the kit build loudly. The new rule is subject to
this contract, and the whole kit assembled without assertion (see check 4),
proving every rule — including the new one — matched at least once.

### 2. Import-sweep completeness — CONFIRMED (the load-bearing claim)
- Diff `58c42f1..0a49183` over every kit-vendored source file: **exactly ONE**
  newly-added cross-package import — `sdk_builder.py`'s
  `from vcfops_dashboards.render import render_view_def_fragments`. Nothing else.
- Current-state sweep of every real (`from`/`import` at line start) `vcfops_*`
  or package-relative import across all 13 `_FACTORY_SOURCES` files: every one
  maps to a rewrite rule. Duplicate import sites (e.g. `render_views_xml` at
  sdk_builder.py:1019/1919/3271; `provenance_from_path` twice in dashboard_loader)
  are covered by single rules because `re.subn` is global — must-match `n>=1`
  still holds.
- The only two residual `import vcfops_managementpacks…` grep hits in the
  assembled kit (`pak_compare.py:14`, `docs_gen.py:19`) are inside module
  docstrings (usage examples), not runtime imports. All kit `.py` files
  `py_compile` cleanly.

### 3. Regression tests — CONFIRMED genuine
- `_make_isolated_env` strips BOTH `repo_root` AND `repo_root/src` from
  PYTHONPATH via `Path(e).resolve()` set membership (handles relative `src`,
  trailing slashes, symlinks), prepends only the kit parent, and the subprocess
  runs `cwd=/tmp`. Matches the phase-1-era src/ stripping rigor exactly; the new
  `_write_outer_pak` test reuses the same `_make_isolated_env` /
  `_assemble_kit_python_only` helpers as the pre-existing isolation tests.
- The `_write_outer_pak` call is a faithful reproduction: line 2146 (the buggy
  import) lives inside `_write_outer_pak` (starts sdk_builder.py:1617), reached
  with `views=[view], reports=[report]` — the same shape the real inner build
  passes. Line 2146 is only reachable after a successful javac compile in a real
  `build-sdk`, which JDK-less CI never reaches — the direct `_write_outer_pak`
  call is the correct way to exercise the seam without Java.
- Canary `test_kit_isolated_reports_with_embedded_views_fails_without_rewrite`
  programmatically reverts the new rule (filters it out of `_IMPORT_REWRITES`)
  and asserts `ModuleNotFoundError` + `vcfops_dashboards` appears. It PASSES,
  i.e. the error genuinely reproduces without the fix — the guard is meaningful.
- All 4 tests in the file pass (`147 passed, 4 skipped` for the whole
  `tests/managementpacks/` subset in 3.67s).

### 4. Kit rebuild + from-tarball spot-check — CONFIRMED
- `assemble_buildkit()` produced `sdk-buildkit-0.2.1.tgz` with no assertion →
  every rewrite rule matched.
- Extracted tarball: `sdk_builder.py:2146` = `from .dashboard_render import
  render_view_def_fragments` (rewritten). `render_view_def_fragments` is defined
  in the kit's `dashboard_render.py:738`.
- With kit-only `PYTHONPATH` and `cwd=/tmp`: `from sdk_buildkit.dashboard_render
  import render_view_def_fragments` resolves; `inspect.getsource(_write_outer_pak)`
  shows the rewritten relative import present and **no** residual `from vcfops_`.
- Running the real vcommunity-vsphere adapter (11 report subdirs) through
  `_write_outer_pak` in the isolated env got PAST the import and deep into
  `render_view_def_fragments` internals (dashboard_render.py:842/821/603) before
  failing on an unrelated supermetric-resolution issue — an artifact of my naive
  harness not wiring the SM map, NOT an import failure. The DEF-009
  `ModuleNotFoundError` did not occur. Adapter repo left clean (`git status`
  empty).

### 5. Gates
- **Path audit:** commit touches only `src/vcfops_managementpacks/buildkit.py`
  and `tests/managementpacks/test_buildkit_isolated_build.py`. Within
  framework-reviewer scope; no content/design/config drift.
- **validate ×7:** supermetrics, dashboards, customgroups, symptoms, alerts,
  reports, managementpacks — all PASS.
- **Full pytest `-m ""`:** **703 passed, 4 skipped** (0 failed) in 1096s.
  707 collected = 703 + 4, matching tooling's claim exactly. (18-min runtime is
  this machine's real javac SDK compile-check tests, unrelated to this change.)
- **render-regression / pak-compare:** N/A — this is a vendoring import-path
  rewrite, not a renderer/wire-format/builder-output change. No emitted
  JSON/XML wire format is altered; `render_view_def_fragments`'s output is
  unchanged, only the module it's imported from inside the kit.

## Regression-anchor checks

- **`00d3382` (global-default / pak-specific leak):** N/A. No default, coordinate
  convention, or flag added; a pure module-path rewrite that is inert on every
  path except making the kit's import resolvable. The factory path (real
  `vcfops_dashboards.render`) is untouched.
- **`6c59f6b` (key/label derivation):** N/A. No key/label derivation touched.

## Stale-zip discipline
Commit touches none of the dist-zip stale-trigger paths
(`vcfops_packaging/templates/`, `vcfops_packaging/builder.py`,
`vcfops_dashboards/render.py`). No `content-packager` rebuild owed. The intended
downstream action is a buildkit republish (1.0.9) via the tag-triggered
`publish-buildkit.yml` — that is the change's explicit purpose, not a `dist/`
content-zip rebuild.

## Findings

### BLOCKING
None.

### WARNING
None.

### NIT
- `[buildkit.py:141]` — the new rule's comment cross-references "sdk_builder.py's
  `_build_sdk_pak_inner` reports loop", but the import actually lives in
  `_write_outer_pak` (starts sdk_builder.py:1617; import at 2146), which the
  inner build calls. The test docstring gets this right. Doc imprecision only.
- `[buildkit.py:76]` — `BUILDKIT_VERSION = "0.2.1"` not bumped despite a
  meaningful kit-content change (the comment says "bump when kit contents change
  in a meaningful way"). Harmless for the release: the CI release version is
  tag-driven (`--version` from `sdk-buildkit-v*`, see cli.py:463 +
  publish-buildkit.yml:75/86), so the constant only names hand-built local-dev
  tarballs. Cosmetic.
- `[test_buildkit_isolated_build.py:374,446,586,666]` — `@pytest.mark.timeout(N)`
  is an unregistered mark (no `pytest-timeout` plugin installed → PytestUnknownMark
  warning); the decorators are no-ops. Harmless here because each subprocess call
  passes an explicit `timeout=25` which does enforce a hard cap. Consider
  registering the mark or removing the decorators.

## If shipped as-is
buildkit 1.0.9 ships with the render_view_def_fragments import correctly
vendored; a CI runner building any adapter that bundles a report-with-embedded-
view (vcommunity-vsphere's exact shape, 11 report subdirs) succeeds instead of
dying with `ModuleNotFoundError: vcfops_dashboards` at sdk_builder.py:2146. This
unblocks the DEF-009 closure path. No operator-visible regression on any other
path.

---

## Addendum — follow-up commit `a2dd6c2` (BUILDKIT_VERSION bump)

- **Commit:** `a2dd6c2` on `fix/buildkit-vendored-import`
- **Change:** `BUILDKIT_VERSION "0.2.1" → "1.0.9"` (buildkit.py:76) — implements this
  review's NIT-2, also Codex P2 on PR #52 (default-invocation tarballs were
  emitting changed payloads under the same `sdk-buildkit-0.2.1.tgz` name).
- **Verdict:** APPROVE (0 BLOCKING)

### Independent verification
- **Diff is exactly one line, nothing rides along:** `git show a2dd6c2 --stat` =
  `buildkit.py | 2 +-` (1 insertion, 1 deletion); the hunk is solely the constant.
- **No pin on the literal:** repo-wide grep of `src/ tests/ .github/` for `0.2.1`
  returns zero hits after the bump; the only `BUILDKIT_VERSION` references are its
  own definition, `assemble_buildkit(version=BUILDKIT_VERSION)` default param, and
  `cli.py:463` (`version = args.version or BUILDKIT_VERSION`) + its help text.
  Confirms tooling's "no test pins the literal" claim.
- **"1.0.9" is sane given cli.py's use:** the constant is only the *local-dev
  default* tarball version — used when `build-buildkit` is invoked without
  `--version`. The CI release path passes `--version` from the `sdk-buildkit-v*`
  git tag (publish-buildkit.yml:75/86), so this constant never drives a real
  release. Aligning the local default with the next release tag makes local
  tarballs self-describing; no coupling risk.
- **Tests:** `test_buildkit_isolated_build.py` + `test_buildkit_release_flag.py`
  → **7 passed**. (Those files reference only unrelated adapter-fixture version
  strings, not `BUILDKIT_VERSION`.)

### Findings
- BLOCKING: none. WARNING: none. NIT: none — this commit resolves NIT-2 from the
  primary review; the remaining NIT-1 (comment cross-ref) and NIT-3 (unregistered
  `pytest.mark.timeout`) are untouched and remain cosmetic.

### If shipped as-is
A default `python3 -m vcfops_managementpacks build-buildkit` now stamps
`sdk-buildkit-1.0.9.tgz` (self-describing) instead of re-emitting a
`0.2.1` name over changed contents. No behavior change to the CI release path.
