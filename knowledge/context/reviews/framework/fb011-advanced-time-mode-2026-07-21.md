# Framework Review — FB-011 advanced-time-mode startPeriod/endPeriod

- **Date:** 2026-07-21
- **Reviewer:** framework-reviewer (pre-PR, RULE-013 blanket gate)
- **Area:** `src/vcfops_dashboards/{loader,render}.py`, `src/vcfops_extractor/{extractor,reverse_local}.py`
- **Change:** View time-window model gains optional free-form
  `start_period`/`end_period`; renderer emits `startPeriod`/`endPeriod`
  Properties when `advanced_time_mode` is true (defaulting PREVIOUS/NOW when
  unset), omitted entirely otherwise; extractor + reverse_local round-trip
  the new fields.
- **Verdict: APPROVE** (0 BLOCKING)

## Checks re-run (independent)

| Check | Result |
|---|---|
| FB-011 tests (`tests/test_fb011_advanced_time_mode_range.py`) | 9 passed |
| Full test suite | 583 passed / 4 skipped / 0 failed (matches tooling claim) |
| Validate chain (all 7 packages) | all OK |
| Corpus `advancedTimeMode=true` survey | exactly 1 (XML) + 0 (JSON refs are URL-encoded `false`); carries `startPeriod=PREVIOUS`/`endPeriod=NOW` only — claim confirmed |
| Emitted Control property order vs vendor | exact match: `advancedTimeMode, unit, count, startPeriod, endPeriod`, `visible="false"` (vendor View - Set 3.xml ViewDef fc64c67a…, lines 11245-11253) |
| Render regression (non-advanced path) | byte-identical (proven from code, below) |

## Dimension walk

1. **Global-default / pak-specific leak (anchor 00d3382):** CLEAR. The
   PREVIOUS/NOW default is strictly gated on `tw.advanced_time_mode` being
   true. The non-advanced path (`else` branch) and the no-`time_window` path
   both hard-set `start_period=end_period=None`, and `period_props` is only
   built when `adv == "true"`. The default cannot bleed into the global /
   standalone content-import path. Covered by tests T4 (non-advanced omits)
   and the no-window test.

2. **Key/label collision (anchor 6c59f6b):** N/A — no key/label derivation
   in this change.

3. **Wire-format conformance:** CONFIRMED against known-good vendor value.
   Emitted order and values match the sole vendor `advancedTimeMode=true`
   control (View - Set 3.xml, ViewDef fc64c67a-d5b0-4a03-a10b-767b9b247120).
   Property ordering is correct and verified empirically.

4. **Loader/validator correctness:** CLEAR. Parsing is defensive
   (`str(x).strip().upper() if x else None`); empty string → None. No new
   validation that could red previously-good content (full validate chain
   green).

5. **Render regression vs known-good:** CLEAN. On the `adv=="false"` path
   `period_props` is unconditionally `""`, and the only change to the return
   string is the single `f'{period_props}'` insertion → byte-identical output
   for all 252 non-advanced corpus controls. The one advanced control
   (vcommunity target view, DAYS/7) now correctly gains PREVIOUS/NOW.

6. **Builder/pak structure:** N/A (no packaging/builder change).

7. **Corpus regression:** CLEAN — full validate chain + full suite green.

8. **Silent downgrade:** None. Change is purely additive; no capability
   removed or defaulted-off. The previous behavior (dropping start/end
   period) was itself the defect being fixed.

9. **Stale-zip discipline:** `render.py` is touched → all dist zips are
   nominally stale (CLAUDE.md "After tooling changes"). Because non-advanced
   content renders byte-identically, only the vcommunity pak (the sole
   advanced-mode view) has changed output. The FB-011 queue entry correctly
   flags the vcommunity pak rebuild + Playwright re-verify in its "Not yet
   done" section. Satisfied. (See NIT-1.)

10. **Test coverage:** Good — loader, renderer (explicit + default + two
    omission paths), extractor, and reverse_local are all exercised (9 tests).

## Round-trip symmetry

Extractor and reverse_local use identical parse logic
(`props.get("startPeriod","").strip().upper() or None`) and identical write
logic (emit only when truthy, after `advanced_time_mode`). extract→YAML→render
is lossless in both directions and the two extractors mirror each other. No
asymmetry found.

## Doc sanity-check

`knowledge/context/feedback_queue.md` FB-011 entry accurately describes the
landed change (fields added, PREVIOUS/NOW defaulting, files touched, survey
evidence, and the still-open pak-side rebuild). Matches the code.

## Non-blocking findings

- **NIT-1** [orchestrator] — Per the blanket "render.py touched → rebuild"
  rule, `content-packager` should still be run; functionally only the
  vcommunity pak's output differs (all other content is byte-identical), and
  its rebuild is already flagged in the FB-011 queue entry.
- **NIT-2** [tests/test_fb011_advanced_time_mode_range.py] — the emitted
  *property order* (load-bearing vs the vendor shape) is verified only by
  dict-membership (`_props`), which discards order. Order is currently correct
  (verified empirically this review); a future refactor could reorder without
  a red test. Consider asserting the raw substring order.
- **NIT-3** [reverse_local] — extractor has a "no-period → None" test (T5b)
  but reverse_local's mirror lacks the equivalent none-case test. Low value;
  logic is identical to extractor.
- **NIT-4** [render.py] — a hand-authored view with `start_period` set but
  `advanced_time_mode: false` would have its period silently dropped by the
  renderer (period_props gated on adv). This is a nonsensical combination the
  vendor never emits, so low risk, but it is an author-set field silently
  ignored. Optional: warn on that combination.

## If shipped as-is

An operator's advanced-time-mode views (currently only vcommunity's "HA
Admission Control status") gain the correct `startPeriod=PREVIOUS`/
`endPeriod=NOW` range, resolving the "View request timed out" symptom once the
vcommunity pak is rebuilt; all other views are unaffected (byte-identical).
