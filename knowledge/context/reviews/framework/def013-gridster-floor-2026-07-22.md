# Framework Review — DEF-013 gridsterCoords floor clamp

- **Area:** `src/vcfops_dashboards/render.py` (+ `tests/test_gridster_coord_floor_def013.py`)
- **Change:** New `_clamp_gridster_floor(coords)` helper (`max(1,x)`/`max(1,y)`, w/h untouched) applied at all 12 `"gridsterCoords"` emission sites, so authored 0-based x/y no longer land out-of-grid and get UI-auto-placed (DEF-013 widget-order inversion).
- **Reviewer:** framework-reviewer (read-only, pre-PR gate; RULE-013 / CLAUDE.md step 9)
- **Date:** 2026-07-22
- **Verdict:** APPROVE (0 BLOCKING)

## Checks re-run independently

| Check | Result |
|---|---|
| Validate chain (all 7 packages) | PASS — 31 SM, 17 views / 7 dashboards, 3 groups, 17 symptoms, 9 alerts / 10 recs, 1 report, 5 Tier1 + 6 Tier2 MP all OK |
| Test suite (default, `-m "not slow"`) | 588 passed, 4 skipped, 140 warnings — matches tooling's claim |
| Test suite (`-m "slow"`) | PASS (ran separately) |
| Render regression vs pre-change render.py | **CLEAN** — byte-identical for all 7 content dashboards after scrubbing nondeterministic `extModel` IDs (the only diffs). See note below. |
| pak-compare | n/a — packaging/builder not touched |

Render-regression method: captured old (`git show HEAD:...render.py`) vs new render of every `content/dashboards/*.yaml`, restored working tree, diffed. Only per-run random `extModel*` IDs differ; zero `gridsterCoords` deltas.

## Verification of tooling's claims

- **Root cause (1-indexed wire format):** SUBSTANTIATED. Independent grep of `reference/references/` + `knowledge/context/exports/` found **519 `gridsterCoords` samples, 0 with x=0 or y=0**. Wire doc `knowledge/context/wire-formats/wire_formats.md:112` documents the 12-column grid; the corpus is uniformly `>= 1`. Clamping the floor to 1 is the correct target.
- **All-12-sites coverage:** CONFIRMED. `grep gridsterCoords` in render.py = exactly 12 emission sites, all wrapped. No 13th site — `reverse.py`'s `gridsterCoords` reference is the import (wire→YAML) direction, not emission; `loader.py` default `{x:1,y:1,w:6,h:6}` is already 1-based.
- **w/h untouched:** CONFIRMED by code (`c["x"]`/`c["y"]` only) and direct call (`_clamp_gridster_floor({x:0,y:3,w:12,h:12})` → `{x:1,y:3,w:12,h:12}`).
- **Not the banned 00d3382 +1 shift:** CONFIRMED. Helper is idempotent and a no-op for every coord `>= 1` (`max(1,v)==v`), so it cannot double-shift valid layouts. `tests/test_renderer_regression_phase16.py` Test A (the 00d3382 guard) is green in the full run.
- **6c59f6b (key collision):** N/A — no key/label derivation touched.
- **Global/standalone-import-path leak (00d3382 anchor):** CLEAR. The clamp is unconditional and identical on every path — there is no pak-conditional branch — so it cannot diverge the standalone content-import path from the pak path. This is the structural opposite of the 00d3382 pak-specific default.

## Findings

### WARNING

**W1 — [render.py:1010 `_clamp_gridster_floor`] Silent floor-clamp is not a coordinate-system translation; a fully 0-based authored layout can render with a 1-row widget overlap, with no author-facing signal.**
Authority: silent-downgrade review dimension + repo philosophy ("loud, documented" > silent normalization); loader has no coord-bound validation (`loader.py` — only the `{x:1,...}` default at :1884, no `x<1`/`y<1` check).
Detail: clamping *only* the sub-1 values (not the whole dashboard) shifts the zero-row down by one while leaving `y>=1` rows fixed, compressing the gap. Proven with the exact DEF-013 shape:
`picker {x:0,y:0,w:12,h:3}` → `{x:1,y:1,...}` occupies rows 1-3; `view {x:0,y:3,w:12,h:12}` → `{x:1,y:3,...}` occupies rows 3-14 → **overlap at row 3**. The pre-fix behavior (inversion / auto-place) was worse, so this is *not a regression* — hence WARNING not BLOCKING — but the fix under-delivers on its docstring goal of handling 0-based authoring transparently. The new test `test_declared_y_order_preserved_after_clamp` asserts only `picker.y < view.y`, so this overlap passes tests silently.
Smallest correct fix: add a loader-level validation WARNING (not a render-time rewrite) when any widget authors `x<1` or `y<1`, so the author corrects the source coordinate system (as the concurrent dashboard-author is already doing) rather than shipping a silently-overlapping layout. Keep the render clamp as a defensive floor, but make the authoring error loud at validate time.

**W2 — [render.py] Stale-zip discipline: render.py is in the trigger set; a `content-packager` rebuild must be flagged.**
Authority: CLAUDE.md "After tooling changes" (`src/vcfops_dashboards/render.py` → all dist zips stale). The tooling result block did not flag a rebuild. Mitigating fact I verified: rendered output is byte-identical for the entire current corpus (all content is already 1-based), so there is no functional delta in today's zips — the rebuild is a formality now, but the orchestrator must still run it per discipline, and it becomes load-bearing the moment any bundled dashboard is authored 0-based.

### NIT

**N1 — [render.py:1010] Floor-only clamp leaves the ceiling-overflow class (`x+w > 13`) unaddressed.** Out of scope for DEF-013 and pre-existing, but note that the sibling half of the 00d3382 symptom ("1-based coords overflow the 12-column grid") is not guarded here. Fine to defer; mentioning so it isn't assumed covered.

## If shipped as-is

Operators see the DEF-013 inversion fixed and every existing dashboard renders byte-identically. The only residual risk is cosmetic and non-regressive: a future dashboard authored fully 0-based would render with a one-row widget overlap and no validation warning — the reason W1 recommends moving the signal to validate time.
