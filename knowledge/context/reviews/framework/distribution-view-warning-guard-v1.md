# Framework review — distribution-view "no data" validate-time WARNING guard

- **Date:** 2026-07-14
- **Reviewer:** framework-reviewer (pre-PR, RULE-013 blanket gate)
- **Area:** `src/vcfops_dashboards/loader.py` (`ViewDef.validate()`)
- **Change:** New validate-time WARNING for the DEF-012-class distribution-view
  "No data to display" footgun — fires when a `data_type: distribution` column
  is not `is_property: true`, the resolved `buckets` are non-dynamic, and the
  attribute key matches a curated property-hint substring list
  (`_DISTRIBUTION_PROPERTY_ATTR_HINTS`); supermetric attributes exempt.
- **Verdict:** APPROVE (0 BLOCKING)

## Scope of diff reviewed

- `src/vcfops_dashboards/loader.py` — hint tuple + WARNING block in
  `ViewDef.validate()`. Read in the context of the full load→validate→render
  data flow.
- `tests/test_distribution_view_no_data_warning.py` — new, 15 tests (T1–T8,
  T4 parametrized ×8).
- `knowledge/context/api-surface/distribution_view_no_data.md` — doc addendum
  (citations sanity-checked; not code).

## Checks re-run (independently, not trusted from the result block)

- **Validate chain (all 7 packages):** PASS — SM/dash/CG/sym/alert/report/MP all
  exit 0. No exit-code change; purely additive claim holds.
- **Test suite:** 569 passed, 4 skipped, 162 deselected. New file: 15 passed.
- **Render regression:** CLEAN. `render.py` is NOT in the diff; `validate()` does
  not mutate the `ViewDef`. The emit-fidelity suite (renders 96 views,
  byte-level assertions) passes unchanged → renderer output is byte-identical
  pre/post. Claim #4 confirmed.
- **pak-compare:** n/a — no builder/template/render surface touched.
- **Calibration (claim #2), independently reproduced:**
  - `content/sdk-adapters/vcommunity-vsphere/views/`: 51 distribution views,
    **0** warnings (matches test T8).
  - `content/sdk-adapters/vcommunity/` (gitignored positive control): **20**
    property-shaped broken views warn; the non-warning remainder are genuinely
    numeric (CPU GHz, Core Counts, Memory Size, NIC Count, reservations,
    latencies) — correct true negatives — plus the one *documented* accepted
    false negative `vSphere Cluster DRS Automation Level`
    (`configuration|drsconfig|vmotionRate`). Calibration claim holds.
  - Factory-native `content/dashboards/views/` corpus: **0** new warnings — the
    orchestrator's routine validate chain gains no noise.

## Dimension walk

1. **Global-default / pak-specific leak (anchor 00d3382):** No defaults, no
   coordinate/flag additions to any render or standalone-import path. The guard
   only *reads* existing fields (`is_property`, `buckets.is_dynamic`,
   `attribute`) inside `validate()`. Provably inert on every output path,
   including the standalone content-import zip path. PASS.
2. **Key / label collision (anchor 6c59f6b):** No key or label derivation. N/A.
3. **Wire-format conformance:** No JSON/XML emission changed; `render.py`
   untouched. PASS.
4. **Loader / validator correctness:** Buckets defaulting (`loader.py:1468-1481`)
   unchanged — distribution views with no `buckets:` still default to a
   non-dynamic `BucketsConfig()`, which is exactly the condition the guard keys
   on (`buckets is not None and not buckets.is_dynamic`). SM-ref exemption
   (`startswith("supermetric:")`) verified live (T6). UUID stability /
   prefix enforcement untouched. PASS.
5. **Render regression vs known-good:** CLEAN (see checks). PASS.
6. **Builder / pak structure:** Untouched. PASS.
7. **Corpus regression:** Full validate chain + full suite green. No
   previously-good content newly fails or newly errors. PASS.
8. **Silent capability change / downgrade:** The change *adds* a signal and
   removes nothing. No downgrade. PASS.
9. **Stale-zip discipline:** The diff touches `loader.py` only — NOT
   `src/vcfops_packaging/templates/`, `builder.py`, or
   `src/vcfops_dashboards/render.py`, and it provably does not alter rendered
   output. **No dist-zip rebuild is owed.** (Noted explicitly because `loader.py`
   is adjacent to the render surface.)
10. **Test coverage:** Strong — 15 tests including a real-repo regression (T8)
    pinning the fixed vcommunity-vsphere corpus silent, an explicit false-positive
    guard (T4, 8 numeric attributes), SM-exemption (T6), and data_type scoping
    (T7). PASS.

## Silent-downgrade / masking audit (brief item #3)

The WARNING is emitted via `warnings.warn(..., UserWarning)`, is non-raising,
and sits mid-`validate()` with **no early return and no surrounding
try/except** — every subsequent check (time-window, etc.) still runs. It cannot
mask or swallow a real validation error. The CLI (`cli.py:63-101`) records
warnings with `simplefilter("always")` and re-emits non-time-window warnings to
**stderr**; structured stdout tokens (`OK:`, `  view`, `SLUG-COLLISION:`,
`INVALID:`) and the exit code are unaffected, so nothing that machine-parses
validate output regresses (brief item #3, warning-noise). No config
(`pytest.ini`/`setup.cfg`/`pyproject.toml`) escalates `UserWarning` to an error.

## Findings

### BLOCKING
None.

### WARNING
None.

### NIT

- **[loader.py — warning message + comment, ×4; also test docstring + doc
  addendum] Mis-citation of DEF-011.** The operator-facing warning string and the
  code comments cite the root cause as "DEF-011 / DEF-012". Per
  `knowledge/context/defects.md`, **DEF-011** is the unrelated *version-line /
  release-gate incident* ("0.x dev-preview pak attached to GitHub Release …
  RULE-014"); the distribution-view "No data" footgun is **DEF-012** alone
  (DEF-011 is only tangentially linked as the "4/4 DISCRETE" verification scope
  that let DEF-012 slip). An operator who reads the shipped warning and looks up
  DEF-011 lands on a versioning defect. → Cite **DEF-012** as the root cause
  (optionally "see DEF-012; slipped past DEF-011's verification scope") in the
  warning text, the four comment references, the test docstring, and the doc
  addendum.

- **[coverage location] The guard does not fire in the orchestrator's routine
  `vcfops_dashboards validate` for the content that actually motivated it.**
  `DEFAULT_VIEWS` covers `content/dashboards/views/` + `third_party/`, not
  `content/sdk-adapters/`; the DEF-012 defect lives in an SDK adapter. The guard
  is still correct — it fires wherever `load_view` runs (build-sdk / pak build /
  the T8 test) — but an author editing an SDK-adapter distribution view will see
  the signal at build/pak-compare time, not during the factory validate chain.
  No code change requested; recorded so the orchestrator knows where the signal
  surfaces.

- **[residual design risk — do not "fix", re-review if escalated] Future
  false-positive on generic hint substrings.** `name`, `type`, `mode`, `level`,
  `state`, `status`, `allow`, `available` are generic enough that a future
  *genuinely numeric* distribution whose attribute key contains one will warn.
  This is acceptable **only because the guard is WARNING-only (exit 0) and the
  message self-documents "can be ignored"** — calibrated against the current
  vcommunity-vsphere corpus, not future content. **If this guard is ever
  escalated to a validation error or a blocking gate, it must be re-reviewed** —
  at that point the accepted-noise tradeoff no longer holds. The allowlist-of-
  suspicion design and the one accepted false negative are documented in the doc
  addendum (satisfies brief item #3's "is the accepted false negative
  documented?").

## If shipped as-is

Authors get a helpful, non-blocking nudge whenever a distribution column looks
like a string property but is bucketed as a numeric histogram — the exact
DEF-012 footgun — surfaced at SDK build / pak-compare time. No existing content
stops validating, no exit code changes, renderer output is byte-identical, and
the only operator-visible rough edge is a warning that name-drops the wrong
defect id (DEF-011 instead of DEF-012).
