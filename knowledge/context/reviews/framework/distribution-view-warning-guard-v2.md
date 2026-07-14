# Framework review v2 — DEF-012 distribution-view guard, partial-fix gap close

- **Date:** 2026-07-14
- **Reviewer:** framework-reviewer (pre-PR, RULE-013 blanket gate)
- **Area:** `src/vcfops_dashboards/loader.py` (`ViewDef.validate()`)
- **Base:** `83f4b59` (the v1-APPROVEd guard) → **Head:** `e30bd1f`
- **Scope:** the *delta only* (`git diff 83f4b59 e30bd1f`), not the whole guard.
  v1 record: `distribution-view-warning-guard-v1.md` (APPROVE).
- **Change:** Restructure the guard so it suppresses the warning **only** on the
  fully-fixed shape (`c.is_property AND buckets is dynamic DISCRETE`) and warns —
  naming the missing piece(s) — on either partial fix. Closes Codex PR #57 P2:
  the original guard's outer bucket-gate and column-level `is_property: continue`
  each independently suppressed on a *partial* fix that still renders "No data".
- **Verdict:** **APPROVE (0 BLOCKING)**

## Diff reviewed

- `src/vcfops_dashboards/loader.py` — the guard block (`+51/-26`), read in the
  full load→validate→render flow. Hint tuple, `BucketsConfig`, and the
  distribution buckets default (`loader.py:1504-1506`) are **unchanged** by this
  delta (confirmed via `git diff --stat`: only the guard block + the test file).
- `tests/test_distribution_view_no_data_warning.py` — `+132` lines, T9–T12 added.
- Renderer (`render.py`): **not in the diff.** `validate()` still does not mutate
  the `ViewDef`. No wire-format / template / builder surface touched.

## Checks re-run independently

- **Validate chain (all 7 packages):** every package exit 0. No exit-code change.
- **Test suite:** `574 passed, 4 skipped, 162 deselected` (v1 was 569 → +5, the
  new T9–T12 plus an extra). Guard file alone: **20 passed** (v1 had 15).
- **Render regression:** CLEAN — `render.py` untouched, validate() non-mutating,
  guard is `warnings.warn`-only. Byte-identical rendered output.
- **pak-compare:** n/a — no builder/template/render surface touched.

## Brief items — independently verified (not trusted from T9–T12)

I constructed each scenario from scratch via `load_view` and inspected the actual
emitted warning string, rather than trusting the shipped tests.

1. **Codex partial-fix #1 (dynamic DISCRETE buckets present, `is_property`
   missing):** WARNS. Missing-piece text = `is_property: true` (correct).
2. **Codex partial-fix #2 (`is_property: true`, buckets fixed/non-dynamic):**
   WARNS. Missing-piece text = `buckets: {dynamic: true, calc_function: DISCRETE}`
   (correct). Also tested the adjacent trap — **dynamic but non-DISCRETE**
   (`dynamic: true, calc_function: AVG`) + `is_property: true`: WARNS, names
   buckets. Correct: `buckets_dynamic_discrete` requires `calc_function ==
   "DISCRETE"`, so a dynamic-AVG partial is not mistaken for fixed.
3. **Both missing:** WARNS, names both, joined `" and "`.
4. **Fully-fixed shape stays silent** — real corpus,
   `content/sdk-adapters/vcommunity-vsphere/views/`: 109 views loaded
   (`enforce_framework_prefix=False`, as T8 does), **51 distribution views, 0
   DEF-012 warnings**, including the **2** `is_property: true +
   is_string_attribute: false + dynamic DISCRETE` vendor-exception views — both
   silent. `is_string_attribute` is provably not in the suppression condition.
5. **No new false positives on numeric distributions:** a property-*absent*
   attribute (`cpu|usage_average`, `cpu|demandmhz`) stays silent regardless of
   `is_property`/buckets combination — the `_DISTRIBUTION_PROPERTY_ATTR_HINTS`
   gate short-circuits first (`if not any(hint ...): continue`). Confirmed.
6. **buckets-is-None edge (brief item #3):** the distribution buckets default
   (`loader.py:1504-1506`, `BucketsConfig()`, `is_dynamic=False`) guarantees
   non-None for the *normal* path. For the one path where buckets **can** be None
   — a malformed non-dict `buckets:` value (`buckets: "weird"`, `true`, `123`) on
   a distribution view falls through the `isinstance(...,dict)` branch and skips
   the `elif` — I confirmed `self.buckets is None` and the guard **warns, does not
   crash**: `buckets_dynamic_discrete = (self.buckets is not None and ...)` short-
   circuits to `False` → treated as broken. Brief item #3 satisfied.
   *(Note: the brief describes a "fixed BucketsConfig default / assert" at
   `loader.py:~1479`; no `assert` was added in this delta — the default at
   `:1504-1506` predates it. Non-blocking; behavior is correct either way.)*

## Missing-piece enumeration — cannot be wrong (brief item #6 hunt)

The warn is reached only when `NOT (c.is_property AND buckets_dynamic_discrete)`,
so at least one of the two conditions is false. `missing` appends `is_property`
iff `not c.is_property` and `buckets` iff `not buckets_dynamic_discrete` — the
enumeration is the exact negation of each half of the suppression predicate. It
can never name a piece that is present, nor omit a piece that is absent. Verified
empirically across scenarios A/B/C/H above.

## Silent-downgrade / masking audit (brief item #6)

The restructured block is still `warnings.warn(..., UserWarning)` inside `if
self.data_type == "distribution":`, with **no early return and no try/except**.
Time-window validation and every later check still run. The restructure changed
*which shapes warn*, not control flow — it cannot mask or swallow a real
validation error, and it does not raise. No masking introduced.

## Vendor-control positive check

Unfixed vendor original `content/sdk-adapters/vcommunity/views/` (gitignored):
50 distribution views, **20 still warn** — matches v1's positive control. The
restructure did not blunt detection of genuinely-broken views.

## Dimension walk (delta)

1. Global-default / pak-specific leak (00d3382): guard only *reads* existing
   fields inside `validate()`; inert on render + standalone-import paths. PASS.
2. Key/label collision (6c59f6b): no derivation. N/A.
3. Wire-format conformance: no emission changed. PASS.
4. Loader/validator correctness: buckets default unchanged; SM-ref exemption
   (`startswith("supermetric:")`) intact; UUID/prefix untouched. PASS.
5. Render regression: CLEAN. PASS.
6. Builder/pak structure: untouched. PASS.
7. Corpus regression: full validate chain + 574-test suite green. PASS.
8. Silent capability change: the change *adds* signal (partial fixes now warn);
   removes none. Not a downgrade. PASS.
9. Stale-zip discipline: `loader.py` only — NOT templates/builder.py/render.py,
   and output is byte-identical. No dist-zip rebuild owed.
10. Test coverage: T9 (buckets-ok/is_property-missing), T10 (is_property-ok/
    buckets-fixed), T11 (is_string_attribute:false fully-fixed silent), T12
    (vendor-control still warns) directly cover the restructure. PASS.

## Findings

### BLOCKING — none.
### WARNING — none.
### NIT
- Carried from v1 and **resolved in this delta**: the operator-facing warning now
  cites **DEF-012** as root cause (v1 flagged a DEF-011 mis-citation). Good.
- Residual (unchanged from v1, do not "fix" here): generic hint substrings
  (`name`, `type`, `mode`, `level`, `state`, `status`, `allow`, `available`) can
  false-positive on a future genuinely-numeric distribution. Acceptable only
  while the guard stays WARNING-only (exit 0, self-documenting "can be ignored").
  If ever escalated to a validation error, re-review.

## If shipped as-is

Authors now get the DEF-012 nudge on **both** partial-fix shapes (was silently
suppressed), with the message naming exactly which piece — `is_property: true`
and/or `buckets: {dynamic: true, calc_function: DISCRETE}` — is missing. No
existing content stops validating, no exit code changes, renderer output is
byte-identical, and all 51 fixed vcommunity-vsphere distribution views (including
the two `is_string_attribute:false` exceptions) stay silent.
