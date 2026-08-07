# Framework review — drop `localizationKey` from view `<Title>`/`<Description>` (DEF-018)

- **Date:** 2026-08-06
- **Reviewer:** `framework-reviewer` (pre-PR gate, RULE-013)
- **Area:** `src/vcfops_dashboards/render.py` (`_render_view_def_fragment`),
  `src/vcfops_managementpacks/sdk_builder.py` (comment only),
  `knowledge/context/defects.md` (DEF-018, registered closed)
- **Verdict:** **CHANGES REQUESTED** — 2 BLOCKING / 3 WARNING / 2 NIT

## Change under review

`_render_view_def_fragment()` now emits plain `<Title>` and `<Description>`
elements with no `localizationKey` attribute, unconditionally. Rationale
(DEF-018): content-import zips ship no localization bundle, so the dangling
key hard-fails view import on VCF Ops 8.18
(`ViewDefinitionDataServiceImpl.validate`); 9.1 tolerates it.

## Independent verification (re-run, not taken on faith)

| Check | Result |
|---|---|
| 7-package `validate` chain | **pass** (7/7 exit 0) |
| Test suite (default, `-m "not slow"`) | **631 passed, 4 skipped**, 177 deselected (slow) |
| Targeted slow subsets: `test_sdk_content_emit.py`, `test_renderer_regression_phase16.py` | 40 passed |
| Targeted slow subsets: discrete/release/sdk-bundled-reports builders | 51 passed |
| `tests/test_defect_gate.py` (`-m ""`) | 46 passed |
| `vcfops_packaging defect-gate --all` | exit 2 — **DEF-004 only** (pre-existing, unrelated pak). DEF-018 closed, does not block |
| Render regression, old vs new renderer over all 19 `content/views/*.yaml` | **clean** — new output is byte-identical to old output after stripping exactly `localizationKey="title"` / `localizationKey="desc"`; no other drift. `localizationKey` count 38 → 0 |
| `pak-compare` | n/a — no builder/template change, no pak built |

Method for the render regression: `git show HEAD:src/vcfops_dashboards/render.py`
staged into a scratch copy of `src/`, both renderers driven over the same
corpus via `render_views_xml()`, outputs diffed. Read-only; nothing in the
repo was modified.

### Consumer sweep of `_render_view_def_fragment()`

- **Standalone content-import path** — `vcfops_dashboards/packager.py:98`,
  `vcfops_packaging/builder.py:664/777/789`,
  `vcfops_packaging/discrete_builder.py:738/889/900`. All write
  `Views.zip` as *content.xml at zip root only* (`builder.py:231`
  "Build Views.zip: inner content.xml at zip root") and
  `content/views_content.xml`. **No properties bundle on any of these
  paths** — the dangling-key premise is confirmed by code, and the shipped
  artifact confirms it (below). Fix is correct and global here.
- **SDK-pak path** — `sdk_builder.py:1019/1934/2176`. These subdirectories
  *do* ship `content/reports/<slug>/resources/content.properties`. Removing
  the key leaves those entries unreferenced, which is inert: the importer's
  failure mode is *key absent from bundle* (`ERROR: Localization for key
  <suffix> is absent`, `knowledge/lessons/pak-content-localization-bundles.md`),
  not *bundle entry unused*. The directory stays non-empty per spec A3.
- **XML back-parsers** — `vcfops_dashboards/reverse.py:230/232` and
  `vcfops_extractor/extractor.py:542/544` read `Title`/`Description`
  **element text only**, never attributes. `vcfops_packaging/audit.py`
  parses `views_content.xml` for metric references only. No consumer
  depended on the attribute being present.
- **`src/vcfops_reports/render.py:90-91`** already emitted plain
  `<Title>`/`<Description>`. Confirmed, not affected.

### Reference-corpus ground truth (scanned, not asserted)

Across every `.zip` under `reference/references/` (including nested zips):
**934 `<Title>`/`<Description>` elements, 14 carry `localizationKey`.**
Every one of those 14 lives in an import unit that also ships
`resources/content.properties`:

- `brockpeterson_operations_dashboards/VMware Tools Summary v2 Dashboard and Views.zip::{VM Details (NSX),VMware Tools Version on VMs,VMware Tools State,VMware Tools on Virtual Machines}.zip`
- `AriaOperationsContent/VM Encryption Reporting/Views.zip`
- `AriaOperationsContent/Cost Reporting/Cost Reporting.zip::Views.zip`

**Zero** vendor units carry the key *without* a bundle. That is a stronger
justification for the fix than the one the change wrote down — and it also
falsifies the claim the change wrote down (WARNING-1).

## Findings

### BLOCKING

**B1 — No regression test guards the removed behavior.**
`src/vcfops_dashboards/render.py:751-754`; `tests/test_renderer_regression_phase16.py`.
Authority: escape anchor **`6c59f6b`** (same file, same attribute family,
same silent validate-passing drift class), review dimension 10, and that
test file's own contract: *"These tests must fail if either pre-fix behavior
is re-introduced."* Nothing in the suite asserts the new shape — grep for
an assertion on `<Title>`/`<Description>` `localizationKey` returns nothing,
and `tooling` states the existing tests "required no changes," which is
precisely the exposure: the 631-test suite is green **both** before and
after the fix. A live 8.18-hard-reject defect with zero test protection is
the exact profile of the two escapes this gate exists for.
**Smallest correct fix:** add a "Test C" to
`tests/test_renderer_regression_phase16.py` — render a view via
`render_views_xml()` and assert (a) the `<Title>` and `<Description>`
elements carry no `localizationKey` attribute, and (b) the standalone
rendered document contains zero `localizationKey` attributes at all.
tmp_path-local fixtures like Tests A/B; no content YAML, no install.

**B2 — Precedence-2 lesson now instructs the opposite of the shipped code.**
`knowledge/lessons/pak-content-localization-bundles.md`. That lesson's "Fix"
section still reads: *"The view XML `<Description localizationKey="desc">`
and the properties entry `view.<uuid>.desc=...` must use the same suffix …
pick one and enforce it across both the XML renderer and the properties
generator,"* and its Reference section names
`src/vcfops_dashboards/render.py — localizationKey="title" and
localizationKey="desc" on <Title> and <Description>` as the renderer of
record. Per `CLAUDE.md` knowledge precedence, lessons outrank context and
code comments; an agent heeding this lesson re-introduces the 8.18 hard
reject, and (per B1) nothing would fail. Leaving a fixed defect's *primary
written instruction* pointing back at the defect is not shippable.
**Smallest correct fix:** add a DEF-018 supersede note to that lesson —
`localizationKey` on `<Title>`/`<Description>` is emitted **only** when a
`content.properties` bundle ships in the same import unit; the factory's
content-import zips ship none, so the renderer emits plain elements. Keep
the suffix-alignment rule scoped to bundle-shipping (pak) units. (Lesson
edits are orchestrator-owned, not `tooling`'s write scope.)

### WARNING

**W1 — Reference-corpus claim in the comment and in DEF-018 is false as
written.** `src/vcfops_dashboards/render.py:733-736`; duplicated in
`knowledge/context/defects.md` DEF-018 *Summary*. The comment asserts vendor
UI exports *"(reference/references/AriaOperationsContent/\*/Views.zip,
brockpeterson_operations_reports/\*.zip) never carry localizationKey on
Title/Description in a bare content.xml either."*
`AriaOperationsContent/VM Encryption Reporting/Views.zip` matches that exact
glob and **does** carry it on both elements (as does
`AriaOperationsContent/Cost Reporting/Cost Reporting.zip::Views.zip`, and
four `brockpeterson_operations_dashboards` view zips). RULE-001 / RULE-002
(source of truth / no fabrication): a durable comment asserting a corpus
fact the corpus contradicts invites a future reader to "verify," find the
counterexample, and revert a correct fix. **Fix:** restate as the
bundle-coupled invariant that the corpus actually supports — *14/934 vendor
Title/Description elements carry `localizationKey`; all 14 ship
`resources/content.properties` in the same import unit; zero carry it
without a bundle* — and name the two `AriaOperationsContent` counterexamples.

**W2 — DEF-018 is marked `closed` while every shipped artifact still
reproduces it.** `knowledge/context/defects.md` DEF-018 *Status* /
*Closing-evidence*. Verified: `dist/dashboards/vm-snapshot-inventory-dashboard.zip`
→ `bundles/vm-snapshot-inventory/Views.zip` still contains
`<Title localizationKey="title">` / `<Description localizationKey="desc">`
with no `resources/` entry — an 8.18 operator downloading today still hits
the blocking defect. All six `dist/dashboards/*.zip` (plus `dist/reports/`,
`dist/bundles/`) are stale per `CLAUDE.md` "After tooling changes" —
`src/vcfops_dashboards/render.py` is on the named trigger list. The entry
*does* flag the rebuild (dimension 9 satisfied), but as prose inside a
closed entry, so there is no tracked item left. **Fix:** either keep DEF-018
open until `content-packager` rebuilds every `bundles/` manifest, or split
the artifact rebuild into its own open entry. The rebuild must land before
any `/publish`.

**W3 — `sdk-buildkit` tarball parity.** `src/vcfops_managementpacks/buildkit.py:138-147`
vendors `render.py` into the kit as `dashboard_render.py` at kit-build time.
Any already-published buildkit tarball still emits the attributes, so an SDK
pak released off it diverges from the factory. Benign in effect (SDK paks
ship the matching bundle), but it is real factory/kit drift. **Fix:** note
it explicitly and re-cut the kit on the next release, or record why the
divergence is acceptable.

### NIT

**N1 —** `tests/managementpacks/test_sdk_content_emit.py:1597-1600` docstring
is now false: *"its `localizationKey="title"/"desc"` attrs need a
resources/content.properties in the SAME subdirectory."* The assertion is
still correct (spec A3 wants the bundle) but the stated reason no longer
exists. Reword to the spec A3 rationale.

**N2 —** `_validate_localization_key_contract()`
(`sdk_builder.py:3238-3310`) is now vacuous on the view path: its XML→props
scan finds zero keys (verified: 0 `localizationKey` in the full corpus
render). Same for `_cap_localization_key` / `_attribute_to_localization_key`
on the view-XML side. Keeping them as dormant trip-wires is right — the
`render.py:219-224` docstring already says so for the column case; add the
same one-liner to the validator so a future reader does not mistake a green
check for coverage.

## If shipped as-is

The renderer fix itself is correct and provably inert everywhere except the
intended attribute (byte-exact regression diff). But it ships with no test,
and with `knowledge/lessons/` still telling the next agent to emit the key —
so the 8.18 hard-reject can silently return on the next renderer touch with
a fully green suite. Separately, every zip an operator can download today
still carries the defect while the registry calls it closed.
