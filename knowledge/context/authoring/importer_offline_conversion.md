# Offline import: existing content files to factory YAML (`import-local`)

`python3 -m vcfcf_extractor import-local` converts a tree of existing VCF
Operations content files to factory YAML, one file per object, into a target
layout the factory loaders read. No live instance, no network. Use it to port
a third-party pak or a lab export into the factory, or to bring existing
content under factory management.

Code: `src/vcfcf_core/importer/` (scan, per-type mapping, conversion plan,
comparison: location-agnostic) and `src/vcfcf_extractor/importer.py` (CLI,
writing, stock-id guard, verification through the real loaders). Tests:
`tests/test_import_local.py`.

## Which command

| Command | Use it for |
|---|---|
| `import-local` | Whole content trees: every view (referenced or not), dashboard, report template, alert, symptom, recommendation and super metric, every field of the current schema, explicit id and naming decisions, verification |
| `reverse-local` | One dashboard JSON and the views it references, with the old output shape (kept for its users, unchanged) |
| `extract dashboard` (`/extract`) | A dashboard from a live lab, with its dependency walk and enablements (unchanged) |

`import-local` is a sibling rather than an extension of `reverse-local`:
that command's contract (one dashboard per run, only referenced views, its
YAML shape and its diff report) has users, and changing what it writes
would change their output for the same input.

## Inputs

Any number of files, directories (walked recursively) and archives. Files
are classified by content, never by folder name:

- view XML (`<ViewDef>`, one or many per file, any nesting);
- dashboard JSON: a bare dashboard or an `{entries, dashboards[]}` envelope
  of one or many dashboards (a pak `dashboards/<Folder>/dashboard.json`
  becomes a Summary page with `summary_for: VMWARE:<Folder>`);
- report template XML (`<ReportDef>`);
- `alertContent` XML: alert definitions, symptom definitions (standalone or
  inline) and recommendations;
- super metric JSON (pak `supermetrics/*.json`, export `supermetrics.json`);
- content-export zips, packed `.pak` files and their nested zips.

Archives are read with the stock-id guard's limits and "cannot check"
discipline (`stock_id_guard.md`): more than 6 nested archives, a member over
512 MB, an encrypted member, an unreadable compression method or a zip that
does not open is `CANNOT READ`, and the run exits 1 whatever else happens
(`--allow-partial` does not cover it). Everything else that is not a content
definition (an XSD, `configuration.json`, the marker file, a pak's
`files/solutionconfig/*.xml` check lists, `.properties` bundles, policy
exports) is listed as *passed over* with the reason. Every definition the
stock-id guard's own scanner finds must be one the converter read, or the run
reports `MISSED` and exits 1.

The same id in several files is one object when the copies are the same once
renumbered ids and whitespace are set aside (`merged:` lines). When copies
differ the object fails, naming every file, until `--prefer-source
<path fragment>` names the copy that wins (repeatable, first match wins).

## Command and options

```
python3 -m vcfcf_extractor import-local INPUT... \
  --out DIR --layout content|third-party|pak \
  --ids keep|mint | --id-map TSV [--id-map TSV ...] \
  --naming unprefixed|factory-prefixed \
  [--rename TSV] [--drop TSV ...] [--target-min 8.18.7|9.0.2|9.1.1] \
  [--prefer-source FRAGMENT ...] [--project-name NAME] [--report-dir DIR] \
  [--verify] [--allow-partial] [--force] [--dry-run]
```

| Layout | Writes | Loader `--verify` uses |
|---|---|---|
| `content` | `<out>/{supermetrics,views,dashboards,reports,symptoms,recommendations,alerts}/` (a factory `content/` tree; every name must carry `[VCF CF] `) | the factory per-type loaders |
| `third-party` | the same folders plus a `PROJECT.yaml` (`factory_native: false`), i.e. a `third_party/<project>/` | the factory bundle loader on `PROJECT.yaml` |
| `pak` | the same folders relative to an SDK adapter project, plus `import-report/bundled_content.yaml` to merge into `adapter.yaml`; its header names the other settings the content needs (`content_naming: unprefixed` for unprefixed names, `content_foreign_adapter_kinds` for symptoms and alerts on another adapter kind) | `sdk_builder._load_bundled_content`, then the pak version-floor and reference checks |

Output: one YAML per object, named from the object's name, each with a
comment naming its source file. `--report-dir` (default
`<out>/import-report/`) receives `report.json` (everything below, per
object), `id_map.tsv` (type, old id, new id, name, file for every object) and,
for a pak, the `bundled_content` snippet.

Exit status: 0 success; 1 a failure, a loss, a verification difference
(`--allow-partial` accepts these) or an unreadable input (never accepted);
2 a usage or safety refusal; 3 the stock-id guard refused the result; 4
`--verify` compared nothing. Nothing is written on 2 or 3.

## Ids: an explicit decision

One of these is required:

- `--ids keep`: the source ids. Right only for content that never shipped
  under someone else's id.
- `--ids mint`: a new UUID for every object (a recommendation gets
  `Recommendation-<uuid>`); every reference is rewritten consistently,
  including super metric wire keys inside dashboard widgets and ids in
  `view_details`, TextDisplay HTML and metric links. `id_map.tsv` records old
  to new. An old id that survives anywhere in the output (free text the
  converter does not rewrite) is a `WARNING` naming the file.
- `--id-map TSV` (repeatable): `old_id<TAB>new_id` rows (a header row and
  extra columns are allowed) for some objects; the rest keep their ids. An
  entry that matches nothing is a warning.

Whatever the mode, the stock-id guard runs on the result before anything is
written: a definition under a VCF Operations stock id fails the run (exit 3),
listing each id with the hint to mint, map or drop. So `--ids keep` on content
that copied product ids fails loudly, which is the correct result. The guard
runs again on the loaded tree under `--verify`.

`--drop TSV` (repeatable): ids (first column) not to emit, so the content can
reference the product object in place instead of shipping a copy. References
to a dropped view or dashboard stay raw ids (`view: <uuid>`, report
`view_id:` / `dashboard_id:`, navigation `dashboard_id:`). An alert cannot
name a symptom or recommendation by raw id, so an alert whose symptom is
dropped or absent fails with that reason.

A symptom, alert or recommendation whose source id is the one the renderer
derives from its adapter kind and name (`AlertDefinition-<kind>-<slug>`,
factory content without `id:`) is written without `id:`; with a rename or the
prefix that derived id changes, so such an object needs `--ids mint`.

## Names

- `--naming unprefixed`: names as in the source.
- `--naming factory-prefixed`: `[VCF CF] ` on every name (the legacy
  `[VCF Content Factory] ` is replaced), and every by-name reference follows.
  Each dashboard's name length is printed; a prefixed dashboard name over 50
  characters fails (the factory loader refuses it) with the hint to rename.
- `--rename TSV`: `old name<TAB>new name` rows, applied before `--naming` to
  names and references alike. A row keyed by an id renames that one object,
  which is how two objects sharing a name are told apart.

Cross-references inside the set are by NAME (the factory convention): a
dashboard View widget's `view:`, report sections, navigation targets, alert
symptoms and recommendations, `supermetric:"<name>"` in view columns and
additional columns, `@supermetric:"<name>"` in formulas. Outside the set, by
raw id where the schema has a raw-id form (a note names each one: it must
exist on the target). Dashboard widget metric keys keep the wire form
`Super Metric|sm_<uuid>` (the dashboard schema has no name form; dashboard
fidelity doc). Two objects of one type with the same final name both fail,
naming both sources.

## What is read, per type

Every field of the current YAML schema, including the 2026-11-12 fidelity
fields; the wire-format docs are the mapping: views
(`../wire-formats/view_fidelity_wire_format.md`, `view_column_wire_format.md`),
dashboards (`dashboard_fidelity_wire_format.md`), report templates
(`template_fidelity_wire_format.md`), alerts, symptoms and recommendations
(`alert_fidelity_wire_format.md`). In short:

- **Views**: list, distribution, trend; subjects and `types:`, the subject
  filter, `group_by`, `usage`, every column Property (property and string
  flags, sort, roll-up type, unit and count, bounds and `ascending_range`,
  `use_symptom_thresholds`, timestamps, transformations with `percentile`,
  `transform_expression` and the TIME_POINT siblings, instanced-group
  drivers, time segments), `omit:` wherever the source leaves out a Property
  the renderer writes, summary rows, buckets (ranges, `is_sum`, count, calc
  function), `additional_columns`, `distribution_color`, `top_n`,
  `page_size`, `max_points_count`, `include_resource_creation_time`,
  `forecast_days`. Instanced-group member columns are written as plain
  columns with their sampled key; the render is the same.
- **Dashboards**: `name_path`, `hidden`, `shared`, `disabled`, `summary_for`,
  `time_range`, `edit_allowed`, `doc_center_key`, column layout, `omit:`,
  interactions, navigations; every widget type the schema has (View,
  TextDisplay, Scoreboard in both metric modes, MetricChart, HealthChart,
  ParetoAnalysis, Heatmap, ResourceRelationshipAdvanced, AlertList,
  ProblemAlertsList, PropertyList, ResourceList, AlertVolume, Section) with
  `ui:` (states with `{self}`, height, the editor residue keys), `description`,
  `title_localized`, `collapsed`, `view_details`, and the per-type fidelity
  fields.
- **Report templates**: subject types (an empty list written explicitly),
  sections by name or `view_id` / `dashboard_id`, CoverPage formatting,
  `omit: [formatting]`, orientation, settings.
- **Alerts / symptoms / recommendations**: explicit ids, names,
  `disable_in_base_policy`, wait and cancel cycles, impact, symptom sets
  (`ANY` / `ALL` aggregation), recommendations with priority; symptom
  conditions (static metric, property, dynamic), `symptom_def_type`,
  `omit:`.
- **Super metrics**: id, name, formula, description, unit, resource kinds.

## What is not converted, and how it is reported

- **A documented loss** converts, and the loss is listed (`LOSS ...`): the
  features the fidelity docs list as deliberately not modeled, which are the
  `localizationKey` on a Title or Description (no localization bundle ships
  with the YAML; DEF-018), an empty `preferredUnitId`, a buckets-control on a
  list view, subject-filter `values` lists and `conditionId`, different
  filters per SubjectType, `startSubUnit`, `BlacklistResourceKind`,
  `includeNotExistingResources`, `cellLink`, related-object columns,
  `objectType=POLICY` and the absolute-date dashboard time range. The list is
  `vcfcf_core.importer.model.DOCUMENTED_NOT_MODELED`.
- **Anything else the schema cannot carry stops that object** with the
  reason and a `TOOLSET GAP` block; everything else converts. Examples seen
  on a 9.1.1 export: a time selector without `count`, a column without
  `isStringAttribute`, a fractional `percentile` (99.9), text and image
  views, a SymptomSet `aggregationOperator`.
- **A written YAML a loader refuses** is not written: each object is staged
  and loaded with the layout's loader first; one it refuses fails with the
  loader's message, and so does every object that names it.
- A reference to an object that failed fails the referencing object (named
  as a cascade, never downgraded to a raw id).

## Target versions

Without `--target-min` the source is reproduced exactly, and every `omit:`
entry whose proven floor is above 8.18.7 (the oldest export read) or unknown
is a `VERSION:` warning, as is every widget that needs a newer product
(Section needs 9.1.1). With `--target-min <version>` an `omit:` entry whose
floor is above the target is not emitted (the key renders, as on every
export of that version), and each such deviation is listed as `TARGET`;
`folder_in_name` has no known floor, so dropping it also puts the folder back
into the dashboard name. Widgets needing a newer product are reported, never
converted away. Floors: `widget_versions.py`, `reports/loader.py`,
`symptoms/loader.py` (dashboard fidelity doc §Omit version floors).

## Verification (`--verify`) and its limits

After writing, the tree is loaded through the real loader of the layout
(table above; if that loader refuses the tree as a whole, verification stops
and says so), each object is rendered with the factory renderer, and the
render is compared semantically with the source object after the intended
changes (new ids and names) are applied to the source. Per object:
identical, or the list of differences. The summary states how many objects
and fields were compared, per type how many are identical and how many differ
only where the object lists a documented loss, and every difference class
with the objects and occurrences it covers. A key, attribute, Property or
element present on one side only is always a difference. Exit 4 when nothing
was compared.

Set aside, each counted and printed as a documented non-difference: ids the
product renumbers (view control, data-provider and column Item ids;
dashboard widget ids mapped by position, entries-table ids, extModel ids,
the pin's Ext resource id; dashboard creation and update times and user ids;
super metric `modificationTime` / `modifiedBy`), `adapterName`, navigation
entries keyed by a widget that is not on the dashboard, whitespace
(collapsed, which also hides a whitespace-only change), number spelling, and
attribute / Property / JSON-key order.

Limits: the SDK pak build's owning-SubjectType injection on views is not
rendered (a pak build adds one SubjectType per view; view fidelity doc), nor
is the pak builder's `adapterName`; verification says nothing about how an
instance imports the content (install and look); the staged load and the
layout loader do not run the factory's repo-wide checks, so validate the
written tree as any authored content: the seven-package chain for `content/`
and a third-party project (whose views and dashboards it walks, including the
project-boundary check that refuses a super metric the project does not
ship), the bundle loader for a project's reports, alerts and symptoms (which
`--verify` uses), and `validate-sdk` for a pak.

## Results on real content (2026-11-13)

Third-party pak (not in the repo): 255 ViewDef copies of 189 unique views,
52 dashboards (one file of 34), 16 report templates, 4 alerts, 10 symptoms
(9 inline, 2 standalone, one shared), 1 recommendation, 2 super metrics; 22
files passed over (6 check-list XML, 2 XSD, 14 empty markers).

- Same id defined differently: one view (two view files) and one symptom (the
  alert file and the standalone symptom file give it different names); both
  stop, naming the files, until `--prefer-source`.
- `--ids keep`: refused by the stock-id guard, 120 view ids (117 stock on
  every version, 3 on 9.1.1), nothing written.
- With the 101-entry id map and the 19-entry drop list, pak layout,
  `--target-min 8.18.7`, `--verify`: 255 objects, 32,499 fields compared;
  249 identical, and the other 6 (views) differ only at their listed
  documented losses (5 list views with a buckets-control, 1 empty
  `preferredUnitId` that also carries a Title / Description
  `localizationKey`). Dashboards 52 of 52 with `adapterName` (34) and 5 stale
  navigation entries set aside. Target deviations: `temporary` on 11
  dashboards, `widget_interactions` on 1, `folder_in_name` on 1 (its name
  then carries the folder). Two dashboards with Section widgets are
  reported; `validate-sdk` refuses exactly those two (version floor), and
  nothing else once the snippet's settings are applied.
- The same as a third-party project without a target: the same 249 + 6. The
  seven-package chain passes except the project-boundary check on the two
  dashboards that reference a super metric the pack does not ship (the
  converter's note names them).
- `content/` layout with `--naming factory-prefixed`: 4 dashboards fail the
  50-character limit with the prefix (named, with the `--rename` hint), and
  one report that has one of them as a section fails with it; the rest
  verify as above and the chain passes.

9.1.1 built-in export, views and report templates (851 + 62), `--ids mint`,
third-party layout: 757 views and 58 templates converted, all 815 identical
(59) or different only at their listed documented losses (mostly the
`localizationKey`); 94 views stop on a named gap (12 text or image views, 25
time selectors without `count`, 21 columns without `isStringAttribute`, 7
metadata controls without `hideObjectNameColumn`, 6 fractional percentiles,
the rest smaller classes and loader refusals) and 4 templates fail because a
section names one of them. The chain passes on the written project.
