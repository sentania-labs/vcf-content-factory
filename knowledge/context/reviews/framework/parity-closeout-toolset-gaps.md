# Framework review — `fix/parity-closeout-toolset-gaps`

- Date: 2026-07-10
- Reviewer: framework-reviewer (read-only, pre-PR)
- Range: `main..HEAD` (4 commits)
  - `fea0023` fix(alerts): translate REST INFO severity to XML "info" token
  - `f6fc7c1` feat(dashboards): SubjectType metric filter for views (`subject.filter:`)
  - `f42432d` fix(managementpacks): sdk_builder bundled reports resolve `views_dir`/`dashboards_dir` against `project_dir`
  - `b7b5d3c` context: document internal view-render REST endpoint (docs only)
- Surface touched: `src/vcfops_alerts/render.py`, `src/vcfops_dashboards/loader.py`,
  `src/vcfops_dashboards/render.py`, `src/vcfops_managementpacks/sdk_builder.py`
- Verdict: **APPROVE** (0 BLOCKING)

## Gates re-run (independently)

- Path audit: only `src/vcfops_*/`, `tests/`, `knowledge/context/` touched. No content YAML,
  designs, `.claude/`, `.github/` in the diff. Clean.
- validate x7 (supermetrics, dashboards, customgroups, symptoms, alerts, reports,
  managementpacks): **all pass**.
- pytest `-m ""` (full, incl. slow markers), `-n auto --dist=loadgroup`:
  **673 passed, 4 skipped, 677 collected** in 850s. Matches tooling's claimed
  673-passed exactly (the 4 skips are environment-gated, not failures).
- New tests: `test_view_subject_filter.py` (12), `test_emit_fidelity_bugs.py`
  Bug-4 additions (severity), `test_sdk_builder_bundled_reports_dirs.py` (2) —
  all green.
- Render regression, views: rendered all 213 repo+adapter views with main-code
  vs HEAD-code against identical content → **byte-identical, zero diff.** The
  filterless `<SubjectType>` path is provably unchanged (empty `filter_attr`).
- Render regression, symptoms: rendered all 25 repo+adapter symptoms main vs
  HEAD → **exactly one line changed**, the INFO symptom
  (`esxi-host-license-remaining-days-info.yaml`):
  `severity="information"` → `severity="info"`. warning/critical/immediate
  unchanged. This is precisely the intended fix and nothing else.

## Dimension walk

1. **Global-default / pak-specific leak (anchor `00d3382`)** — clear on all
   three fixes:
   - Fix 1 severity map applied on the XML content-import renderer only
     (`_render_symptom_definition`); the REST path (`vcfops_symptoms` loader,
     `SEVERITY_MAP`) is untouched and still emits `INFORMATION`. Verified
     `_xml_severity` maps every `SEVERITY_MAP` value to an accepted lowercase
     content-import token (critical/immediate/warning/info), never
     "information".
   - Fix 2 emits `filter="..."` only when `view.subject_filter` is set;
     otherwise the attribute is absent and output is byte-identical to main
     (proven across 213 views). No standalone-import-path behavior change.
   - Fix 3 changes `views_dir`/`dashboards_dir` **only** in
     `sdk_builder._load_bundled_content` (the SDK-pak build path). The
     standalone `vcfops_reports.loader.load_file` default (`content/views`,
     `content/dashboards`) is unchanged — the global report path is inert.
2. **Key / label collision (anchor `6c59f6b`)** — N/A. No key/label derivation
   added; the `localizationKey` path is untouched.
3. **Wire-format conformance** — Fix 2 `filter=` rendered output is
   **byte-exact against the actual vendor file**
   `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/View - Collection01.xml:7`
   (VM Network Top Talkers), not merely against the hand-transcribed test
   constant — confirmed by extracting the vendor attribute and diffing.
   `<SubjectType>` attribute order (adapterKind, filter, resourceKind, type)
   matches vendor. Fix 1 token matches
   `knowledge/context/wire-formats/symptomdef_severity_import.md` (accepted set
   `critical|immediate|warning|info|automatic`; "information" rejected).
4. **Loader / validator correctness** — `SubjectFilterCondition.validate`
   fail-closes on unproven `filter_type`/`condition`/`transform`, bare-boolean
   `value`, and empty groups; each rejection is exercised by a test and points
   at the vendor corpus. `is_string_metric` derived from `value` type per the
   wire doc. No UUID/prefix/cross-ref regression.
5. **Render regression vs known-good** — views byte-identical (213/213);
   symptoms drift confined to the single intended INFO line (1 of 25). No
   silent drift.
6. **Builder / pak structure** — Fix 3 is scoped to report cross-ref
   resolution inside `_load_bundled_content`; no `template.json`/`describe.xml`
   emission change, so `pak-compare` is n/a. The hermetic test builds a
   synthetic `tmp_path` project (views/ + reports/), does not depend on the
   gitignored vcommunity-vsphere adapter repo, and covers both the positive
   (resolves against project_dir) and fail-closed (missing view → SdkBuildError)
   cases. Adapter repo `content/sdk-adapters/vcommunity-vsphere` working tree is
   clean — tooling's temporary adapter.yaml registration was reverted.
7. **Corpus regression** — validate x7 clean; full suite green.
8. **Silent capability change / downgrade** — none. All three changes are
   additive or a bugfix; every new rejection path raises loudly with a
   doc/corpus pointer. Fix 1 turns a silent server-side skip into a correct
   import (a capability *restoration*, not a downgrade).
9. **Stale-zip discipline** — `src/vcfops_dashboards/render.py` is a trigger
   path (CLAUDE.md "After tooling changes"), so dist zips are mechanically
   stale. See NIT below — impact is provably nil for currently-shipped content.
10. **Test coverage** — every fix ships accompanying tests, including a
    regression guard (`TestNoSymptomXmlEverEmitsRejectedInformationToken`) that
    iterates all `SEVERITY_MAP.values()` and fails if any renders "information".

## Findings

BLOCKING: none.

WARNING: none.

NIT:
- [`src/vcfops_dashboards/render.py`] CLAUDE.md "After tooling changes" —
  touching `render.py` marks all `dist/` zips stale; a `content-packager`
  rebuild should be flagged. Impact is **proven nil**: all 213 views render
  byte-identical, and no factory bundle carries an INFO-severity symptom (only
  the vcommunity-vsphere SDK adapter does, and SDK paks are built by their own
  CI, not factory dist zips). A rebuild will produce byte-identical factory
  zips. Flag for discipline, not for drift.

## If shipped as-is

Operators gain a working SubjectType metric filter (`subject.filter:`, byte-exact
to the vendor VM Network Top Talkers view), and INFO-severity symptoms — plus
the alerts that depend on them — stop silently vanishing on content-import. No
existing view or factory-bundled symptom changes on the wire. Downstream:
`content-packager` should still be run per stale-zip discipline before any
affected release, though the rebuild is a formality here.

---

## Addendum — `916cd9b` (Codex P2 on PR #47, 2026-07-10)

- Commit: `916cd9b` fix(dashboards): subject_filter loader must not coerce
  fields before `validate()` runs
- Surface: `src/vcfops_dashboards/loader.py` (`load_view._load_filter_condition`)
  + `tests/test_view_subject_filter.py`
- Verdict: **APPROVE** (0 BLOCKING)

### The bug being fixed

`_load_filter_condition` did `bool(raw["business_hours"])` and blind
`str(...)` coercion on the string fields **before**
`SubjectFilterCondition.validate()` ran. Because `bool("false")` is `True`,
a quoted `business_hours: "false"` in YAML was silently coerced to `True` and
the renderer emitted `"businessHours":true` — the fail-closed `isinstance(bool)`
gate built for exactly this field was bypassed by coercion ordering. This is a
real fail-closed-bypass (dimension 4/8), correctly rated P2, and correctly
fixed here.

### Independent verification

- **Coercion genuinely gone.** Grepped the filter-condition load path: the only
  `bool(...)`/`str(raw...)` occurrences remaining are inside the explanatory
  comment. Live path now passes `value` and `business_hours` through with type
  preserved; `_str_field()` does an `isinstance(str)` check and raises a
  named-field error *before* any `.strip()/.upper()`. `validate()`'s
  `isinstance(bool)` check is the sole authority for `business_hours`.
- **Quoted-string rejection works.** Directly exercised: quoted
  `business_hours: "false"` and `"true"` both raise `DashboardValidationError`
  naming `business_hours` (no silent coercion to `True`). Non-string
  `transform`/`condition` also rejected with the field named.
- **Happy path unchanged / byte-exact.** Unquoted `business_hours: false`
  renders byte-exact against the actual vendor file
  `View - Collection01.xml:7` (re-extracted and compared, not the test
  constant). Unquoted `true` renders `"businessHours":true`.
- **No existing-content behavior change.** validate ×7 pass. View render
  regression re-run against `main` over all 213 repo+adapter views →
  **byte-identical, zero diff** (nothing in the corpus uses `subject.filter`).
- **Path audit clear** — only `src/vcfops_dashboards/loader.py` + the test file.
- **Tests.** `test_view_subject_filter.py` now 18 (12 + 6 new); the 6 cover
  quoted true/false rejected, unquoted true/false accepted, non-string
  transform/condition rejected. Full suite `-m ""` (incl. slow),
  `-n auto --dist=loadgroup`: **679 passed, 4 skipped** in 883s — matches
  tooling's claim exactly (683 collected = 679 + 4).

### Findings

BLOCKING: none. WARNING: none. NIT: the stale-zip NIT above is unchanged (this
addendum touches only `loader.py`, not a trigger path, so it adds no new
stale-zip obligation beyond the render.py one already noted).

### If shipped as-is

A quoted `"true"`/`"false"` for `subject_filter.business_hours` now fails loudly
at load with a field-named error instead of silently becoming `true` on the
wire. No change to any currently-shipped content (none uses `subject.filter`);
the unquoted-boolean happy path stays byte-exact against the vendor fixture.
