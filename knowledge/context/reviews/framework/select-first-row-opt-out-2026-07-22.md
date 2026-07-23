# Framework Review — `select_first_row` opt-out (dashboards)

- **Date:** 2026-07-22
- **Reviewer:** `framework-reviewer` (pre-PR, RULE-013 blanket gate)
- **Area:** `src/vcfops_dashboards/loader.py`, `src/vcfops_dashboards/render.py`, `tests/test_select_first_row_opt_out.py`
- **Change:** add an author-facing `select_first_row: bool` YAML field (default `True`) to dashboard widgets; `_view_widget`, `_resource_list_widget`, and `_resource_relationship_advanced_widget` emit `w.select_first_row` instead of hardcoded `True`.
- **Scope note:** the working tree also carries the already-APPROVED DEF-013 gridster floor-clamp (`_clamp_gridster_floor`, see `def013-gridster-floor-2026-07-22.md`). That is **out of scope** for this review; only the `select_first_row` addition is reviewed here.
- **Verdict:** APPROVE *(round 2 — all round-1 findings resolved; supersedes the CHANGES REQUESTED below)*

## Round 2 re-review (2026-07-22, after tooling fixes)

All three round-1 findings verified fixed and re-run independently:

1. **BLOCKING (corpus test reds the suite) → RESOLVED.** `tests/test_select_first_row_opt_out.py:172-190` is now opt-out-aware: it builds `authored_by_id = {w.widget_id: w.select_first_row for w in dashboard.widgets}` per dashboard and asserts each emitted `selectFirstRow` **equals the authored value** (default `True` when omitted). No whitelist, no all-true corpus assumption. Passes with the co-landing `cpu_support_status.yaml` opt-out present.
2. **WARNING (RRA no opt-out) → RESOLVED.** `_resource_relationship_advanced_widget` (render.py:1843) now emits `w.select_first_row`. Default `True`; no RRA content authors the field, so output is byte-identical corpus-wide — confirmed by the passing opt-out-aware corpus test.
3. **NIT (silent non-bool coercion) → RESOLVED.** Loader (loader.py:1635-1640) now raises `DashboardValidationError` (a real `ValueError` subclass, loader.py:27) on a non-bool `select_first_row`, before Widget construction. Spot-checked: `select_first_row: "false"` (string) is now rejected with a clear message instead of silently coercing to `True`. `self_provider` coercion left untouched (loader.py:1911), as intended.

**Round-2 checks re-run (independently):**
- validate chain: **PASS** (`vcfops_dashboards validate` green; full chain green).
- tests: `test_select_first_row_opt_out.py` **7 passed**; full suite **595 passed / 4 skipped** (the previously-red corpus test now passes).
- render regression: **clean** — byte-identical for all content that does not author the field; only `cpu_support_status.yaml` opts out, as intended.
- wire conformance: unchanged — `{"selectFirstRow": {"selectFirstRow": <bool>}}` matches `knowledge/context/wire-formats/wire_formats.md:572`.

Regression anchors `00d3382` (global-default leak) and `6c59f6b` (key collision) remain CLEAR (see below). Zero BLOCKING → **APPROVE**, PR unblocked.

---

## Round 1 (2026-07-22) — CHANGES REQUESTED (historical, superseded)

### Checks re-run (independently)

- **validate chain:** PASS (all seven `vcfops_*` validate commands green; 7 dashboards, 18 views, MPs, etc.).
- **tests:** `tests/test_select_first_row_opt_out.py` — **6 passed / 1 FAILED**. Full suite: **594 passed / 1 failed / 4 skipped**.
- **render regression:** clean for all content **except** the co-landing new consumer (see below). The default (`True`) is byte-identical for every existing dashboard that does not author the field — verified: `grep -rln select_first_row content/dashboards/` returns **only** `cpu_support_status.yaml` (the concurrent dashboard-author's untracked work).
- **pak-compare:** n/a (no packaging/template/builder surface touched).
- **wire conformance:** emitted `{"selectFirstRow": {"selectFirstRow": <bool>}}` matches `knowledge/context/wire-formats/wire_formats.md:572` exactly. Reference corpus (`reference/references/`) confirms the nested shape and the motivation: **246 `false` vs 17 `true`** — opt-out is the norm on multi-tier drill dashboards.

### Findings

#### BLOCKING (resolved in round 2)

- **[tests/test_select_first_row_opt_out.py:146-192]** *Dimension 7 (corpus regression — reds the suite is BLOCKING).* `test_all_content_dashboards_still_select_first_row_true` asserted an **all-`True` corpus invariant** (`assert w.select_first_row is True` for every widget of every `content/dashboards/*.yaml`). The feature's *own motivating first consumer* — `content/dashboards/cpu_support_status.yaml`, co-landing in this same working tree — authors `select_first_row: false`, so the assertion failed and **redded the test suite** (`1 failed, 594 passed`). The framework *code* (loader/render) was correct; the defect was that tooling shipped a regression test whose premise ("no shipped dashboard opts out") was already false in the tree that would become the PR. → **Fix (applied):** make the corpus assertion opt-out-aware — assert emitted `selectFirstRow` equals authored `select_first_row` (default `True`), filtering rather than hardcoding all-true.

#### WARNING (resolved in round 2)

- **[src/vcfops_dashboards/render.py:1843]** *Dimension 8.* `_resource_relationship_advanced_widget` hardcoded `selectFirstRow: True` and was not wired to `w.select_first_row`; an RRA widget used as an intermediate drill tier would reproduce the auto-select-repin bug with no opt-out. → **Fix (applied):** wired to `w.select_first_row`. *(`_pareto_analysis_widget` at render.py:1395 already emits `False` and is not tier-capable — no change needed, still correct.)*

#### NIT (resolved in round 2)

- **[src/vcfops_dashboards/loader.py]** `bool(w.get("select_first_row", True))` silently coerced a non-bool YAML value (e.g. `"false"` → `True`). → **Fix (applied):** loader now raises `DashboardValidationError` on non-bool.

## Regression-anchor clearance

- **`00d3382` (global-default / pak-specific leak):** CLEAR. The default (`True`) is the historical value; the opt-out is per-widget, author-controlled, and travels through the single shared `render_dashboards_bundle_json` path — identical on the pak path and the standalone content-import path. No pak-local default leaks global.
- **`6c59f6b` (key/label derivation collision):** N/A. `select_first_row` is a boolean config value, not a derived key or label; no derivation, no collision surface.

## If shipped as-is (round 2)

The renderer behaves correctly, every existing dashboard renders byte-identical, the opt-out dashboard emits `selectFirstRow: false` as intended, a mistyped non-bool value is rejected at load with a clear error, and the full test suite is green (595 passed / 4 skipped). Nothing blocks the PR.
