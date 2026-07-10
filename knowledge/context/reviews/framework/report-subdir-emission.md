# Framework review — report subdir emission + SM modifiedBy fix

Branch: `fix/report-subdir-emission` (commit 9fa1752), reviewed 2026-07-10.
(Reviewer's file write was blocked in-session; this report was persisted
verbatim by the orchestrator from the reviewer's final message.)

```
FRAMEWORK REVIEW
  area: src/vcfops_managementpacks/sdk_builder.py, src/vcfops_dashboards/render.py
  change: SDK-pak bundled reports emit as content/reports/<slug>/ subdirs with
          co-bundled inline ViewDefs (TVS vendor shape); render_view_def_fragments
          extracted as shared emitter; slug-collision guard; SM modifiedBy "" ->
          all-zero factory UUID
  verdict: APPROVE
  findings: 0 BLOCKING / 0 WARNING / 3 NIT
  checks re-run: validate-chain pass (x7); tests 701 passed / 4 skipped (exit 0);
                 render-regression clean (205/205 corpus views byte-identical);
                 pak-compare n/a — verified by direct rebuild-extract instead
```

All seven verification items independently confirmed:

1. **Vendor TVS shape** — extracted `SolarWindsNPM-7.0_3.0.0`: 18 report
   subdirs, 0 flat; sampled subdir is one
   `<Content><Views><ViewDef id="11cb51b6-…">…</Views><Reports><ReportDef>…
   <ContentKey>11cb51b6-…</ContentKey></Reports></Content>`, embedded
   ViewDef id == Section ContentKey byte-verified; vendor ships no
   per-report resources bundle. Our emitted shape matches structurally.
2. **render_views_xml refactor** — main's render.py loaded alongside HEAD's,
   every corpus view rendered through both: **205 renderable views, 0
   mismatches** (18 raise the identical unscoped-SM ValueError on both).
   The extraction is pure; the standalone import path is provably inert.
3. **Co-bundle** — rebuilt vcommunity-vsphere; embedded ViewDef `5bf51a21-…`
   byte-identical (35426==35426) to its standalone subdir emission; all 11
   reports audited: exactly 1 matched embed each, 0 phantom, 0 bare, 0
   not-bundled; bare-cross-instance path covered by
   `test_report_referencing_view_outside_bundle_left_verbatim`.
4. **Slug-collision guard** — shared `_content_reports_used_slugs`, `-2`
   suffix on collision; covered by test.
5. **modifiedBy** — 37/37 SM JSONs carry the all-zero UUID, 0 empty; the
   single line `"modifiedBy": ""` -> `_FACTORY_SYSTEM_UUID` is the only
   SM-field delta.
6. **3 updated tests** — all three previously asserted the flat (broken)
   contract and now assert subdir with equal-or-stronger assertions.
7. **Gates** — path audit clean; validate x7 pass; pytest 701 passed;
   rebuild-extract: **120 subdirs / 0 flat / 11 report subdirs / 109 view
   subdirs / 37 SM UUIDs**; adapter repo left clean.

Regression anchors: `00d3382` NOT re-opened (co-bundle confined to
sdk_builder; shared renderer byte-identical corpus-wide). `6c59f6b` NOT
re-opened (no change to `_attribute_to_localization_key`; duplicate
`view.<uuid>.<key>` properties live in separate import units).

NIT:
- [render.py] Stale-zip discipline mechanically triggered, but the change
  is a proven-inert extraction (205/205 byte-identical) — packager rebuild
  is a formality.
- [sdk_builder.py] ReportDef body sliced via
  `.split("<Reports>",1)[1].rsplit("</Reports>",1)[0]` — safe today (XML
  text-escaping), but couples to renderer output text; consider a fragment
  helper like views now use. Robustness only.
- [sdk_builder.py] Per-report `resources/content.properties` diverges from
  vendor TVS (which ships none) but is correctly justified: our embedded
  ViewDef fragments carry `localizationKey` attrs that must resolve within
  the report subdir's own import unit
  (`knowledge/lessons/pak-content-localization-bundles.md`). Intentional.

if shipped as-is: SDK-pak installs land all bundled ReportDefinitions
(was 0/11, silently un-walked flat files) with companion ViewDefs
co-imported, and SM imports stop emitting 37 `Invalid UUID string:` ERROR
lines per install; no regression on the standalone content-import path.
