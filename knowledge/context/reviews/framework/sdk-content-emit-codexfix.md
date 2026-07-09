# Framework Review — SDK content-emit Codex-fix (P1 kit self-containment + P2 alert recommendations)

- **Date:** 2026-06-18
- **Reviewer:** framework-reviewer (RULE-013 blanket pre-PR gate)
- **Area:** `vcfops_managementpacks/buildkit.py`, `vcfops_managementpacks/sdk_builder.py` (+ `tests/managementpacks/test_bundled_reports_emit.py`)
- **Scope:** incremental Codex-fix diff on PR #24 only. The full content-emit pipeline was already APPROVED (`knowledge/context/reviews/framework/sdk-content-emit-consolidated.md`); this reviews only the P1/P2 increment.
- **Change:** P1 — packages 5 new modules into the buildkit (symptoms/alerts/reports loaders + alerts/reports renderers) and adds `_IMPORT_REWRITES` so `sdk_builder.py`'s `from vcfops_{symptoms,alerts,reports}.{loader,render}` (and the previously-missing `from vcfops_supermetrics.loader import load_file`) rewrite to flat kit names. P2 — `_load_bundled_content` 6→7-tuple (adds `recommendations`); `_write_outer_pak` threads referenced recs into `render_alert_content_xml` with fail-loud cross-ref validation.
- **Verdict:** **CHANGES REQUESTED** (1 BLOCKING)

## Checks re-run (independently)

- **validate-chain:** PASS (exit 0) — SM/views+dashboards/customgroups/symptoms/alerts+recs/reports/MP Tier1+Tier2 (incl. vcommunity `OK (Tier 2)`). Warnings are pre-existing advisory key-drift/window-lint, not errors.
- **tests:** 430 passed, 4 skipped, 162 deselected (unchanged from prior baseline). The new test asserts 7-tuple arity + `recommendations == []`. **No test exercises kit-isolated content load** (see BLOCKING + dimension-10 gap below).
- **buildkit assembly:** clean — `build-buildkit` produced `sdk-buildkit-0.2.0.tgz`, "sdk_builder.py (patched 14 import rule(s))", "alerts_render.py (2)", "reports_render.py (1)". Zero `_apply_rewrites` zero-match AssertionError; no rule suppressed.
- **kit build (factory ON sys.path):** content load passed — "96 view(s), 12 dashboard(s), 37 supermetric(s), 2 symptom(s), 2 alert(s), 0 report(s), 0 recommendation(s)"; failed only at Java compile (no SDK jar — expected/unrelated). **This run MASKED the bug** because cwd=repo-root leaked the factory onto sys.path.
- **kit build (factory OFF sys.path — the real CI-runner condition):** **FAILS.** `ERROR: bundled_content.supermetrics: failed to load .../esxi-bad-network-packets.yaml: No module named 'vcfops_common'`.

## Hunt results (every named failure mode)

1. **Kit-context correctness (P1, the whole point).** Buildkit assembles without zero-match. sdk_builder.py: all 14 `from vcfops_*` imports map to a rewrite rule and the kit copy has ZERO residual `from vcfops_*` (verified by grep over the extracted kit). The duplicated `render_alert_content_xml` import (sdk_builder lines 1814 + 1854) is handled correctly — `re.subn` rewrites both. **BUT** the newly-packaged renderers are not the whole transitive closure — see #2. **NOT CLEAR.**
2. **Transitive deps (BLOCKING per brief).** Traced every verbatim-copied kit module. symptoms_loader, alerts_loader, reports_loader, dashboard_yaml_utils, sdk_project = clean. **`sm_loader.py:211` retains executable `from vcfops_common.provenance import provenance_from_path` with NO rewrite block** — `vcfops_common` is not a package name in the kit (it is flattened to `provenance.py`, which the kit DOES contain and which `dashboard_loader.py` correctly imports as `from .provenance`). dashboard_loader's provenance import was rewritten (buildkit.py:202); sm_loader's identical import was missed. Reproduced live (factory off sys.path): any adapter bundling supermetrics cannot build through the kit. This is the exact P1 failure mode (`ModuleNotFoundError` on bundled-content load FROM THE KIT), one transitive level down. **BLOCKING.**
3. **7-tuple arity.** Both production sites unpack 7 (`sdk_builder.py:2850`, `:3096`); `test_bundled_reports_emit.py` updated to 7 + `recommendations`; `test_bundled_content_resolver.py` and `test_sdk_content_emit.py` use `*_` / never unpack directly. No latent `ValueError`. CLEAR.
4. **P2 correctness + no-regression.** `AlertDef.recommendations` is `List[RecommendationRef]` (loader.py:183), each `.name` (loader.py:162) — guard's `getattr`/`.name` access is valid. Fail-loud guard fires only for `[VCF Content Factory]`-prefixed unbundled refs (mirrors `resolve_alert_recommendations` policy: non-factory = built-in, not validated). vcommunity's 2 alerts reference no recommendations → `referenced_recs == []`, alert XML emits unchanged (confirmed by clean kit alert count). Empty `recommendations` key writes no `content/recommendations/` dir (recs flow inline into alert XML only). CLEAR.
5. **No regression to approved emit paths.** In-tree validate chain PASS, 430 tests pass, vcommunity Tier 2 OK. The approved SM(37)/view(96)/dashboard(12)/symptom(2)/solutionconfig(6) emit is untouched IN-TREE. CLEAR in-tree; the kit path is broken for SMs (#2).

## Findings

### BLOCKING
- **[`vcfops_managementpacks/buildkit.py` `_IMPORT_REWRITES` — missing `"sm_loader.py"` block]** — anchor: P1 kit self-containment; same class as `dashboard_loader.py` provenance rewrite (buildkit.py:202). The kit copy of `sm_loader.py` (`vcfops_supermetrics/loader.py`) keeps executable `from vcfops_common.provenance import provenance_from_path` at line 211. `vcfops_common` is absent from the kit (flattened to `provenance.py`), so loading ANY bundled supermetric through the kit raises `ModuleNotFoundError: No module named 'vcfops_common'`. **Reproduced** with the factory off `sys.path` (the real CI-runner condition) against vcommunity (37 bundled SMs). The in-tree test suite does not catch this because tests run with the factory ON `sys.path`. → **Smallest fix:** add an `"sm_loader.py"` block to `_IMPORT_REWRITES` with rule `(r"from vcfops_common\.provenance import provenance_from_path", "from .provenance import provenance_from_path")` — identical to the existing `dashboard_loader.py` rule. The `_apply_rewrites` zero-match assertion then guarantees it stays live. (sm_loader is currently copied verbatim with no rewrite block, which is why the import survived.)

### WARNING
- **[test coverage — dimension 10]** No test builds a content-bearing adapter through an *isolated* kit (factory off `sys.path`). The new test only checks 7-tuple arity. This is exactly the seam that let the BLOCKING escape `validate` + the suite. → Add a test that assembles the kit and runs `build-sdk` against a fixture adapter bundling ≥1 supermetric with the factory packages NOT importable (subprocess with scrubbed `sys.path`/`PYTHONPATH`), asserting content load succeeds (it may stop at the Java-compile step). Without it, the next transitive-dep regression escapes identically.
- **[process / CLAUDE.md "After tooling changes"]** This diff does NOT touch `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or `vcfops_dashboards/render.py`, so the stale-zip rule is not triggered by THIS increment. (The prior consolidated change already flagged the `dist/` rebuild for `render.py`; that obligation still stands from that review, not this one.)

### NIT
- None new.

## If shipped as-is

A CI runner building any SDK adapter that bundles supermetrics (vcommunity bundles 37) from the published buildkit tarball — i.e. the entire reason P1 exists — fails immediately with `ModuleNotFoundError: No module named 'vcfops_common'` the moment it loads the first SM YAML. The pak never builds. The in-tree `build-sdk` keeps working (factory on path), so the regression is invisible until the official `v*`-tag CI build on a clean runner — the most expensive place to discover it.

---

## RE-REVIEW — 2026-06-18 (Codex-fix for the single BLOCKING)

**Verdict: APPROVE (0 BLOCKING).** The single BLOCKING from the original
review is resolved and the guard is real.

### Fix under review
- `vcfops_managementpacks/buildkit.py:199-205` — new `"sm_loader.py"`
  `_IMPORT_REWRITES` block rewriting
  `from vcfops_common.provenance import provenance_from_path` →
  `from .provenance import provenance_from_path`. Pattern matches the live
  source line (`vcfops_supermetrics/loader.py:211`), so `_apply_rewrites`'
  zero-match assertion keeps it live.
- `tests/managementpacks/test_buildkit_isolated_build.py` (new, 2 tests).

### Independent verification (re-run the way the bug was found)

1. **Original repro now passes.** Assembled the kit and ran `build-sdk`
   against an SM-bundling fixture with the factory genuinely OFF
   `PYTHONPATH` (stripped) and `cwd=/tmp` (outside the repo) — the exact
   condition that produced `ModuleNotFoundError: No module named
   'vcfops_common'`. Result: `bundled content: ... 1 supermetric(s)`
   loads cleanly; the build fails only at the Java compile step (no SDK
   jar — expected/unrelated). The original error is gone.

2. **Class fully closed, not just the instance.** AST-walked EVERY
   assembled flat kit module (`*.py`) for any executable `from vcfops_*`
   / `import vcfops_*`. **Zero residual.** The author's AST-audit claim is
   confirmed independently.

3. **The new test genuinely guards the seam (cannot false-pass).** Proved
   the subprocess isolation is real by directly reverting the
   `sm_loader.py` rewrite and re-running isolated: the subprocess
   reproduces `bundled_content.supermetrics: ... No module named
   'vcfops_common'`. Because that error only appears when the factory is
   NOT importable in the subprocess, its appearance proves the env is
   genuinely isolated — the test cannot pass with the factory leaking onto
   `sys.path`. The in-repo revert-canary
   (`test_kit_isolated_build_fails_without_sm_rewrite`) asserts exactly
   this and PASSES; the primary test
   (`test_kit_isolated_build_no_vcfops_import_error`) PASSES with the fix.

4. **No regression.**
   - validate-chain: PASS (all 7 validators exit 0).
   - tests: **432 passed**, 4 skipped (was 430; +2 = the new isolated
     tests). No reds.
   - In-tree vcommunity emit unchanged: **96 view / 12 dashboard / 37
     supermetric / 2 symptom / 2 alert / 6 solutionconfig**; pak builds
     clean (`dist/vcfcf_sdk_vcommunity.1.0.0.7.pak`).

### Residual notes (non-blocking, do not block the PR)
- **NIT:** the new tests decorate with `@pytest.mark.timeout(60)` but
  `pytest-timeout` is not installed/registered (`PytestUnknownMarkWarning`)
  — the timeout is silently inert. The tests have an internal
  `subprocess.run(..., timeout=55)` so they cannot hang indefinitely, so
  this is cosmetic. Either register the mark or rely on the subprocess
  timeout and drop the decorator.
- The prior WARNINGs (process stale-zip obligation from the consolidated
  `render.py` change; that obligation stands from that review, not this
  increment) are unchanged by this fix.

### Checks re-run
validate-chain PASS; tests 432 passed / 0 failed; render-regression n/a
(no renderer touched); pak-compare n/a (structure unchanged from approved
consolidated review).

### If shipped as-is
A clean CI runner pulling the published buildkit tarball and building any
SM-bundling adapter (vcommunity bundles 37) now loads its supermetrics
successfully instead of dying with `ModuleNotFoundError: No module named
'vcfops_common'`. The escape class is closed and regression-guarded by an
isolated-subprocess test with a working revert-canary.
