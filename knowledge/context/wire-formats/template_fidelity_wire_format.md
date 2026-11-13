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
- A field the renderer cannot honour is a load error naming the file and
  section index.
- Evidence: 16 third-party templates and the 9.0.2, 8.18.7 and 9.1.1
  built-in exports (63, 62, 62 templates). Snippets are composed here.

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
verbatim. No walker can check offline that a built-in id exists on the
target.

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

## Round trip

16 third-party templates (34 Dashboard sections and 11 View sections
resolved by name against the mapped dashboards and the pak's views, 5 with
CoverPage formatting, 5 without SubjectType): **16 identical**. 62 built-in
9.1.1 templates (every View section by `view_id`): 1 identical, 61 differ
only by the two localizationKey attributes. XML compared as an ordered
element tree, attributes unordered, text whitespace-collapsed; the
comparator detected all 843 single-attribute, text and element mutations.
