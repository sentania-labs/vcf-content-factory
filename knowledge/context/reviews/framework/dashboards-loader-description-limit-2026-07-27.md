# Framework review (incremental) — view `description` 1024-char validate gate + prior-warning fixes

- **Date:** 2026-07-27
- **Reviewer:** `framework-reviewer` (RULE-013 blanket pre-PR gate)
- **Area:** `src/vcfops_dashboards/loader.py` (new logic),
  `src/vcfops_dashboards/render.py` (comment only)
- **Baseline:** the previously APPROVED diff in
  `knowledge/context/reviews/framework/dashboards-render-preferred-unit-instanced-2026-07-27.md`.
  This review covers only what changed on top of it.
- **Verdict:** **APPROVE** (0 BLOCKING / 2 WARNING / 3 NIT)

## Incremental change under review

1. `render.py:455-470` — the comment on the `preferredUnitId` emission is
   replaced with the real vendor citation (`View - Set 4.xml:22141-22150`,
   `attributeKey="diskspace:262|snapshot:snapshot-1|used"`,
   `preferredUnitId="gb"`, plus the deliberately-omitted vendor `id`).
   **No executable change** — verified: the only non-comment line in the
   `render.py` diff is the pre-approved `if col.unit:` block.
   → prior **WARNING 1 resolved**.
2. `loader.py:421-431` — `ViewDef.validate()` now raises
   `DashboardValidationError` when `len(self.description) > 1024`.
   **New logic, not covered by the prior verdict.**
3. `tests/test_view_description_length_limit.py` (new, 2 cases: 1024 pass /
   1025 fail) and `test_property_member_column_with_unit_omits_rolluptype`
   in `tests/test_view_instanced_group_columns.py` → prior **NIT 4 resolved**.
4. `knowledge/context/wire-formats/view_column_wire_format.md` "Instanced-group
   columns" section rewritten from "NOT fixed here / flag for a future tooling
   pass" to "implemented", plus a new "View-level field limits" section; new
   `known_limitations.md` §14. → prior **WARNING 2 resolved**.

## Gates re-run (independently)

| Gate | Result |
|---|---|
| validate chain ×7 (`supermetrics`…`managementpacks`) | all **exit 0** |
| full pytest | **614 passed, 4 skipped, 162 deselected** (matches claim; +3 vs the 611 of the prior review) |
| new/changed test files run explicitly (`-m ""` deselect check) | **21 passed** (2 description + 19 instanced) |
| render regression, all 19 tracked views, `HEAD` src vs working-tree src | **18 byte-identical; 1 expected delta** |
| corpus description scan (253 view/bundle docs) | max **918** chars (`content/views/vm_snapshot_inventory.yaml`); **zero** over 1024 → no previously-good content newly rejected |
| vendor reference XML `<Description>` scan (458 elements) | 6 over 1024, **all in policy XML** (`SampleDefaultPolicy.xml`, `autoscale-policy.xml`), **zero** in view definitions → reverse-import blast radius nil |
| pak-compare | n/a — no builder/template change |

Render-regression method: extracted `HEAD`'s `src/` via `git archive` to a
scratch tree, rendered every `content/views/*.yaml` through
`load_view`+`render_views_xml` under both trees, diffed. (First harness run
silently `ERR`'d on all 19 views — `load_view` takes a `Path`; corrected and
re-run. Recorded because a green-looking "byte-identical" from an all-error
harness is exactly the false negative this gate exists to avoid.) The single
delta is one line on `vm_snapshot_inventory.yaml`:

```
 <Property name="attributeKey" value="diskspace:356893|snapshot:snapshot-16|used"/>
+<Property name="preferredUnitId" value="gb"/>
 <Property name="isStringAttribute" value="false"/>
```

— the already-approved feature, in the vendor-exact position. Nothing else moved.

## Dimension walk (incremental)

**1. Global-default / pak-specific leak (anchor `00d3382`).** The
description check is unconditioned — it does not read `bundle_context`,
`sm_scope`, `factory_native`, or pak-vs-standalone, so it cannot introduce
path-divergent behavior. It is, however, a limit measured on exactly one
output path applied to all of them — see WARNING 2. Direction is fail-closed,
which is the safe direction for this anchor.

**2. Key/label derivation (anchor `6c59f6b`).** N/A — no key or
localization-key derivation touched. `<Description localizationKey="desc">`
emission (`render.py:734-737`) is unchanged; render regression byte-confirms it.

**3. Wire-format conformance.** `render.py:735` emits
`escape(view.description)` with **no prefixing, templating, or attribution**
anywhere on any path (grepped `src/vcfops_packaging/`, `packager.py`,
`sdk_builder.py`). So the string `validate()` measures **is** the rendered
`<Description>` text, modulo XML escaping — the brief's "rendered vs raw"
question resolves in the check's favor, with the escaping caveat in WARNING 1.

**4. Loader/validator correctness — scope is right.** The check lives in
`ViewDef.validate()` only. No analogous check was added to `DashboardDef`,
report, symptom, alert, customgroup, or supermetric loaders (diff is two
files; `loader.py` hunk is the only logic). It does not touch `name`/`Title`.
`self.description` is always a `str` on every construction path
(`loader.py:1623` `str(...).strip()`; `reverse.py:220` defaults `""`;
`extractor.py:1298` and `reverse_local.py:526` pass `""`), so `len()` cannot
`TypeError`. No UUID/prefix impact (RULE-006/RULE-007 untouched).

**5. Render regression — clean** (table above).

**6. Builder / pak structure — untouched.**

**7. Corpus regression — clean.** Validate chain exit 0 with the new content
present; corpus max 918 chars against a 1024 ceiling.

**8. Silent capability change — the good direction.** This converts a silent
server-side failure (`state=FAILED, skipped=1, errorMessages=[]`) into a
loud local error, which is the "unreadable is not compliant" principle
applied to the framework. It *can* newly refuse to build content that
previously built — but that content could not import, so refusing is
correct. Zero corpus impact today.

**9. Stale-zip discipline.** `render.py` is in the diff (comment only, and
the render regression proves 18/19 views byte-identical), so the formal
rebuild obligation from prior WARNING 3 still stands; the orchestrator has
scheduled `content-packager` after this review. Carried forward, not re-raised.

**10. Test coverage.** Boundary is tested at exactly 1024 and 1025, matching
the empirical bisect. Missing only a scope-guard test — NIT 3.

## Findings

### WARNING

1. **[`src/vcfops_dashboards/loader.py:421`] — `knowledge/context/known_limitations.md`
   §14 "Scope notes" / `view_column_wire_format.md` "View-level field limits"
   (Unverified).** The check counts **Python `str` length = Unicode code
   points**, while both docs record that bytes-vs-characters "was not probed
   with multi-byte content; the bisect used ASCII, where the two coincide."
   This is not hypothetical for this corpus: existing descriptions already
   contain non-ASCII (`vm_rightsizing_candidates.yaml`: 699 chars / **701
   bytes** / **709 XML-escaped chars**; `cluster_vm_count.yaml`: 676 / 678 /
   682). A house-style 1020-char description with a handful of em-dashes and
   one `&` renders to ~1030 bytes / ~1035 escaped — it would **pass** validate
   and still hit the silent import failure the check exists to prevent, if the
   server counts either bytes or the on-wire escaped text. The gate is
   fail-open in exactly the region where the evidence stops, while the error
   string asserts a flat "1024-character limit" as settled.
   → **Fix (smallest):** keep the hard error on code-point length, and add a
   short comment stating the check is code-point-based and that bytes/escaped
   length are unverified per §14; optionally emit a `warnings.warn` (not an
   error) when `len(description.encode("utf-8")) > 1024` or
   `len(escape(description)) > 1024` while code points are ≤1024, so the
   ambiguous band is loud rather than silent. Do **not** hard-fail on bytes —
   that would over-reject if the limit is genuinely characters.

2. **[`src/vcfops_dashboards/loader.py:421`] — evidence scope vs enforcement
   scope.** The bisect is `VIEW_DEFINITIONS` **content-zip import on VCF Ops
   9.1** (one path, one version). `ViewDef.validate()` gates **every** consumer
   of a view: the standalone content-import zip (`vcfops_dashboards/packager.py`),
   pak builds (`vcfops_packaging/builder.py`, `discrete_builder.py`), SDK paks
   (`vcfops_managementpacks/sdk_builder.py`), and any target running 8.x/9.0.
   Whether the pak import path or a pre-9.1 server carries the same ceiling is
   unmeasured. Enforcing globally is the right fail-closed call and has zero
   corpus impact today, but neither doc records that the *enforcement* is
   broader than the *evidence* — so a future "why did my pak build refuse this
   description?" will be misdiagnosed.
   → **Fix:** one sentence in the "Unverified — do not extrapolate" block of
   `view_column_wire_format.md` (and §14) stating enforcement is deliberately
   applied to all view output paths and all Ops versions, fail-closed, on
   single-path 9.1 evidence.

### NIT

3. **[`tests/test_view_description_length_limit.py`]** No scope-guard case
   asserting a **dashboard**/report description over 1024 chars still validates.
   The "does not over-reach" property is currently proven only by corpus
   absence and by reading the diff — a 3-line negative test would pin it, which
   is the same shape as the driver-non-leak guard `tooling` correctly wrote for
   `preferredUnitId`.

4. **[`src/vcfops_dashboards/loader.py:421`]** The check sits between the
   framework-prefix check and the `adapter_kind`/`resource_kind` check, so a
   view missing required subject kinds *and* carrying a long description
   reports the description first. Harmless ordering, noted only because
   cheap-structural errors usually read better before prose-length errors.

5. **[carried forward, unchanged]** `BUILDKIT_VERSION` still `1.0.9` in
   `src/vcfops_managementpacks/buildkit.py:76` while `render.py` (vendored as
   `dashboard_render.py` into the published sdk-buildkit tarball) has changed
   again. Pre-existing systemic pattern, still out of scope for this diff,
   still worth a dedicated tooling pass.

## If shipped as-is

Authors get a loud `validate`-time error instead of a
`FAILED / skipped=1 / errorMessages=[]` server envelope with no field name —
the single highest-value class of fix this repo makes. No existing content is
newly rejected (corpus max 918 chars), no rendered view changes by a byte
except the already-approved `preferredUnitId="gb"` line, and the two prior
WARNINGs about doc/comment drift are properly closed. The residual risk is a
narrow fail-open band: a description at 1000-1024 code points that exceeds
1024 **bytes** (non-ASCII, already present in this corpus) or 1024 **escaped**
characters would still silently fail import, and neither the code nor the docs
warn about that band.
