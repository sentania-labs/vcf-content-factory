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
  fields nor the `omit:` and feature version gates (§Feature version
  floors) reach an official pak release until a newer kit is tagged and the
  pak bumps its pin.

## Section attributes audited

| Section | Children seen | Factory YAML |
|---|---|---|
| CoverPage | `ContentType, ContentKey` (built-ins); `+ ContentFormatting(ColorizeListView, FontColor)` (5 third-party) | `colorize:` and `font_color:` (new; `font_color` floor 9.0.2, §Feature version floors) |
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

### Feature version floors (CoverPage `font_color`, 2026-11-14)

The inverse of an `omit:` floor: an element the renderer emits only when
the YAML sets it, and that an older product's report schema refuses.

**Measured** (fresh pak install, one pak of 16 templates, 5 of them with
`<ContentFormatting><ColorizeListView>false</ColorizeListView><FontColor>000000</FontColor></ContentFormatting>`
on the CoverPage, 2026-11-15 UTC):

| Build | Result |
|---|---|
| Aria Operations 8.18.7 | the 5 refused, 11 imported. Analytics log, once per template: `cvc-complex-type.2.4.d: Invalid content was found starting with element 'FontColor'. No child element is expected at this point.`, then `SolutionManagerDistributedTask.installReportContent - importSolutionContent failed to import reports. Error: JAXB unmarshalling exception`. The install reported success; the post-install content check named the 5 missing. The upstream pack they were converted from shows the same 5 missing on 8.18.7. |
| VCF Operations 9.0.2 | all 16 imported; the instance's own REPORT_DEFINITIONS export carries the element back (2026-11-12 and 2026-11-13 runs) |
| VCF Operations 9.1.1 | all 16 imported; its export carries it back (2026-11-11 and 2026-11-12 runs) |
| Aria Operations 8.18.7, opt-in output | Measured 2026-11-15: a pak whose five cover pages carry `ColorizeListView` and no `FontColor` (the `feature_fallback: {font_color: omit}` output) imported all five on 8.18.7 with no schema error in the appliance logs; one of them generated a PDF whose cover page renders. The same pak one build earlier, with `FontColor`, lost those five on the same instance. |

"No child element is expected" after `ColorizeListView` means the 8.18.7
`ContentFormatting` type ends at `ColorizeListView`: a CoverPage with
`colorize` alone is inferred to pass the schema there (the error position
shows it was accepted), but no 8.18.7 import of that shape has been
observed. Evidence (read-only, lab share):
`backups/vcommunity-java-p9-2026-11-14/devel_8_18/` (install log, appliance
log excerpts) and the per-instance REPORT_DEFINITIONS exports under
`backups/*-2026-11-1[123]-*/`.

**Other report elements.** The built-in exports of 8.18.7, 9.0.2 and 9.1.1
(62, 63, 62 templates) carry the same element and attribute paths; counts
differ only with the template count, and none carries a CoverPage
`ContentFormatting`. No report element is on the 9.x exports and absent
from 8.18.7, so there is no other unmeasured-suspect element today.

**Table:** `reports/loader.REPORT_FEATURE_MEASURED` (imported and refused
builds per feature); the floor `REPORT_FEATURE_MIN_OPS_VERSION` is the
lowest imported build. `font_color`: floor **9.0.2**, refused on 8.18.7 and
taken as refused below it; 8.18.8 to 9.0.1 unmeasured. A measurement there
lowers it by editing the one table.

**Semantics.** `FontColor` sits in the CoverPage section's formatting, so it
is the text colour of the generated PDF's cover page (six hex digits,
`000000` black in every observed case). No product doc names the field, so
this is read from its placement, not stated by the vendor. Without it the
cover page renders as every built-in template's does (none sets it): the
product default. Leaving it out costs the cover-page text colour only; no
section, view, dashboard or data is lost, and the CoverPage `colorize` is
kept.

**The opt-in: `feature_fallback`.** A report-level mapping of feature to
`omit`, the same vocabulary as the dashboard key `section_fallback: omit`:

```yaml
feature_fallback: {font_color: omit}
sections:
  - {type: CoverPage, colorize: false, font_color: "000000"}
```

One committed source: where the output's lowest target is below the
feature's floor the report ships without the element, and every omission
prints `FEATURE OMITTED: report '<name>': font_color (<FontColor> in the
CoverPage <ContentFormatting>, <n> section(s)) left out (feature_fallback:
font_color: omit): <reason>.`; at or above the floor it ships with it, so
retiring the old line restores the element with no content edit. An unknown
feature, a value other than `omit`, or a listed feature that no section
sets (as `section_fallback` on a dashboard without a Section) is a load
error. A report without the key is never changed.

| Door | Target | With `feature_fallback` | Without |
|---|---|---|---|
| `load_file` (every validate) | none | warning saying where the key applies | warning naming the key |
| `import-local --target-min` | below 9.0.2 | n/a: the importer never writes the key | not emitted; `TARGET` deviation at `ReportDef/Sections/Section[i]/ContentFormatting/FontColor` (missing); status "identical apart from forced target keys" |
| `import-local` | 9.0.2 or later, or none | n/a | carried (none: a `VERSION:` warning) |
| Tier 2 `build-sdk` / `validate-sdk` | oldest supported line, 8.18.7 | shipped without it, `FEATURE OMITTED` printed | build fails naming the report, section, element, floor and the key |
| same, oldest line `9.0` | read as 9.0.0, below 9.0.2 | omitted | fails |
| same, oldest line 9.1.1 | 9.1.1 | shipped with it | shipped with it |
| live sync (`vcfcf_reports sync`, bundle sync) | the instance version | below 9.0.2, or unreadable: omitted | 8.18.7 or below: refused before anything is sent (bundle sync: before any type imports); 8.18.8 to 9.0.1 or unreadable: warning, imported |
| content bundles, distribution installers | none declared | shipped with it | shipped with it |

The `9.0` row is conservative: the platform line includes builds below the
proven 9.0.2. The pak layout of `import-local` checks the pak floor too, so
at `--target-min 9.0.2` or with no target a source carrying `FontColor`
writes nothing in that layout (`--allow-partial` does not change that; the
run prints a `PAK CHECK, what to do` line); convert at 8.18.7, then restore `font_color`
and add `feature_fallback` to the written YAML where the full form is
wanted (the `TARGET` line names the value). Code:
`ReportDef.feature_version_problems`, `ReportDef.feature_fallback_variant`,
`loader.apply_feature_fallback`, `loader.feature_import_check`,
`sdk_builder.apply_bundled_report_fallback`,
`vcfcf_reports.client.plan_report_import`. Tests:
`tests/test_report_feature_floors.py`.

**Not covered.** The distribution installers (`install.py`, `install.ps1`)
import the report XML the release builder rendered with no target, so a
bundle report carrying `font_color` is lost on an 8.18.7 instance whatever
its `feature_fallback`. Version-aware variants there are an installer
template change (every distribution zip goes stale): a follow-up, issue
#369. A content
import sends every report in one `content.xml`; whether the 8.18.7 schema
check then refuses the whole batch or the one template is unmeasured, which
is why live sync refuses rather than warns.

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
- Leading or trailing whitespace on the `Description` (11 vCommunity
  templates): the report loader strips it. `import-local` records it as a
  loss, accepted only where the render is the source stripped; interior
  whitespace is carried.

CoverPage and TableOfContents `ContentKey` is the renderer's constant
(`COVER_PAGE`, `TABLE_OF_CONTENTS`; `reports.loader._STATIC_CONTENT_KEYS`);
`import-local` stops a template carrying another value with a TOOLSET GAP.

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
