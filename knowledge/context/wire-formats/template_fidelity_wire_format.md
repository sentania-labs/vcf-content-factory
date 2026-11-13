# Report template (ReportDef) fidelity: wire format and YAML (2026-11-12)

The report YAML fields that let an existing report template (`ReportDef` in
`content.xml`) be re-expressed as factory YAML and render the same. Code:
`src/vcfcf_core/reports/loader.py` (`Section`, `ReportDef`, `load_file`) and
`src/vcfcf_core/reports/render.py`. Tests:
`tests/test_report_alert_fidelity.py`. API surface:
`../api-surface/reports_api_surface.md`.

## Contract

- Every field is optional; without it the renderer emits exactly what it did
  before (render regression over every report YAML in the repo: identical).
- A field the renderer cannot honour is a load error naming the file, the
  report and the section index (`<path>: report '<name>': sections[<i>]:
  ...`); `ReportDef.validate()` errors are prefixed with the path too.
- Evidence: 16 third-party templates and the 9.0.2, 8.18.7 and 9.1.1
  built-in exports (63, 62, 62 templates). Snippets are composed here.
- Keys the older loader silently ignored (it does not reject unknown keys)
  that now render: CoverPage `colorize` and `font_color`, and section
  `omit`. One now fails to load: `colorize` on a Dashboard section ("not
  rendered on a Dashboard section"). `view_id` / `dashboard_id` and
  `subject_types: []` were load errors before, not ignored. The riskiest
  newly read keys across the branch are dashboard `disabled: true` and
  alert or recommendation `id:` (`dashboard_fidelity_wire_format.md`
  §Keys an older loader ignored, `alert_fidelity_wire_format.md`).
- SDK-adapter paks: buildkit 1.0.28 and earlier vendor the older loader,
  which ignores those keys, so a pak built with such a kit renders without
  them and reports no error. Pak CI pins the kit by tag, so neither these
  fields nor the `omit:` version gate reach an official pak release until a
  newer kit is tagged and the pak bumps its pin.

## Section attributes audited

| Section | Children seen | Factory YAML |
|---|---|---|
| CoverPage | `ContentType, ContentKey` (built-ins); `+ ContentFormatting(ColorizeListView, FontColor)` (5 third-party) | `colorize:` and `font_color:` (new) |
| TableOfContents | `ContentType, ContentKey` | unchanged |
| View | `ContentType, ContentKey, ContentOrientation` (79 of 92 built-in); `+ ContentFormatting(ColorizeListView)` | `orientation`, `colorize`; `omit: [formatting]` (new) for no ContentFormatting |
| Dashboard | `ContentType, ContentKey, ContentOrientation` | `orientation` |

```xml
<Section><ContentType>CoverPage</ContentType><ContentKey>COVER_PAGE</ContentKey>
  <ContentFormatting><ColorizeListView>false</ColorizeListView><FontColor>000000</FontColor></ContentFormatting></Section>
```

```yaml
sections:
  - {type: CoverPage, colorize: false, font_color: "000000"}   # six hex digits, quoted
  - {type: View, view: "<project view name>", orientation: Portrait, omit: [formatting]}
```

`font_color` and the CoverPage `colorize` are rejected on other section
types; `omit: [formatting]` is View only and contradicts `colorize`.

### Omit version floor

`omit: [formatting]` has floor **8.18.7**: 77 of 91 View sections in the
8.18.7 built-in export carry no ContentFormatting (79 of 92 on 9.0.2, 78 of
90 on 9.1.1). Table: `reports/loader.SECTION_OMIT_MIN_OPS_VERSION`; check:
`ReportDef.omit_version_problems(target)`. A Tier 2 pak build
(`sdk_builder.check_bundled_version_floors`) fails on an entry whose floor
is above its oldest supported line, and `load_file` warns for one above
8.18.7 with no target, the same rule as dashboards
(`dashboard_fidelity_wire_format.md` §Omit version floors). Nothing trips
it today.

## Built-in (product-shipped) views and dashboards by id

A View or Dashboard section names exactly one of `view:` / `dashboard:` (the
project's own object, by exact name, as before) or `view_id:` /
`dashboard_id:` (a raw UUID for a product-shipped or other-pak object, the
same convention as a dashboard View widget's raw-UUID passthrough):

```yaml
  - {type: View, view_id: 3d4e5f60-7182-4930-a4b5-c6d7e8f9a0b1, orientation: Landscape}
  - {type: Dashboard, dashboard_id: 4e5f6071-8293-4a41-b5c6-d7e8f9a0b1c2}
```

Rules: a UUID; an id that is one of the project's own views or dashboards
(the `views_dir` / `dashboards_dir` index) is a load error that names the
object, so own content is always referenced by name and gets bundled.
Such a section is `Section.external`. Dependency walkers: the discrete
release builder (`discrete_builder._resolve_report_deps`) skips external
sections (nothing to bundle), and the SDK pak report embedding
(`sdk_builder`, which embeds only views bundled in the pak) leaves the id
verbatim.

The ids are checked against the stock-id baseline
(`src/vcfcf_core/stock_ids/stock_ids_baseline.json`, 8.18.7, 9.0.2 and
9.1.1 exports). `vcfcf_reports validate` warns, naming the file, report and
section, when an id is not a known stock view or dashboard id: a typo
renders a blank section, but the id may be another pak's object, so it is
never an error. In a Tier 2 pak (`validate-sdk`, `build-sdk`) a stock id the
baseline shows absent on a supported line (for example a view stock only
in 9.0.2 and 9.1.1) is a warning naming the lines it is missing on.
Check: `ReportDef.external_references()` and
`stock_ids.guard.reference_warnings`. An id that exists only on the target
instance (another pak installed there) cannot be checked offline.

## Reports with no SubjectType

`subject_types: []` written explicitly renders no `<SubjectType>` (5
third-party templates). An absent or null `subject_types` is still the
"at least one subject_type" error.

## Not modeled

- `localizationKey="title"` / `"desc"` on `Title` and `Description` (every
  built-in template). They point at the localization bundles
  (`resources/content_*.properties`) the product ships beside its own
  templates; the factory's reports zip ships none, and a dangling
  `localizationKey` fails import on 8.18 (DEF-018). With these two
  attributes set aside, all 62 built-in 9.1.1 templates round-trip.

CoverPage and TableOfContents `ContentKey` is the renderer's constant
(`COVER_PAGE`, `TABLE_OF_CONTENTS`; `reports.loader._STATIC_CONTENT_KEYS`);
`import-local` stops a template carrying another value with a TOOLSET GAP,
and one whose `Description` has leading or trailing whitespace (the report
loader strips it; 11 vCommunity templates).

## Round trip

16 third-party templates (34 Dashboard sections and 11 View sections
resolved by name against the mapped dashboards and the pak's views, 5 with
CoverPage formatting, 5 without SubjectType): **16 identical**. 62 built-in
9.1.1 templates (every View section by `view_id`): 1 identical, 61 differ
only by the two localizationKey attributes. XML compared as an ordered
element tree, attributes unordered, text whitespace-collapsed
(`" ".join(text.split())`, which also hides a whitespace-only text change).
The comparator detected all 843 single-attribute, text and element
mutations; that mutation check ran over the 16 third-party report templates
only, not over the alert or symptom XML.
