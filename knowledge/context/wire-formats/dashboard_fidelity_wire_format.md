# Dashboard fidelity: wire format and YAML (2026-11-12)

The dashboard YAML fields that let an existing VCF Operations dashboard be
re-expressed as factory YAML and render the same. Sibling of
`view_fidelity_wire_format.md`. Code: `src/vcfcf_core/dashboards/loader.py`
(dataclasses `TagFilterSpec`, `HeatmapFilterGroup`, `ParetoAdditionalColumn`,
`WidgetUi`, the vocabulary tables beside them, and the fidelity fields on
`Widget`, `MetricSpec`, `ScoreboardConfig`, `ParetoAnalysisConfig`,
`HeatmapTab`, `Dashboard`) and `src/vcfcf_core/dashboards/render.py`
(`_apply_widget_fidelity`, `_apply_metric_entry_fidelity`, `_tag_filter_json`
and the per-type renderers). Tests: `tests/test_dashboard_fidelity.py`.

## Contract

- **Every field is optional and its absence renders exactly what the
  renderer emitted before.** Proven by a byte-for-byte render of every
  dashboard in `content/`, `third_party/*/`, `tests/fixtures/` and the four
  registered paks (content-import path and SDK pak path with an owning
  adapter), plus every view, report, alert, symptom and recommendation:
  192 renders, identical before and after.
- **Keys an older loader silently ignored now render or fail to load.**
  The dashboard loader does not reject unknown keys, so every key below was
  read as nothing before this change. Full list: §Keys an older loader
  ignored. No YAML in the repo or the registered paks sets any of them (the
  regression above); a clone that does sees them take effect.
- **A field the renderer cannot honour is a load error naming the file,
  the dashboard and the widget**, and so is a value no product export
  carries. `omit:` entries that contradict a field the YAML also sets are
  load errors. `load_dashboard` prefixes every widget-level error with
  `<path>: dashboard '<name>': `.
- **Closed vocabularies hold only values seen in product exports**: the
  9.0.2, 8.18.7 and 9.1.1 built-in dashboard exports of clean labs (180,
  163 and 179 dashboards) and one third-party pak's 52 dashboards. Counts
  below are from those corpora.
- **SDK-adapter paks need a newer buildkit.** The kit vendors `loader.py`
  and `render.py`. Kit 1.0.28 and earlier silently ignore almost all of
  these fields (their loader does not reject unknown keys; only `collapsed`
  on a non-Section widget, `relationship_mode` on HealthChart, Pareto or
  Heatmap and navigation `widget_ids` were load errors there), so a pak
  built with such a kit renders
  without them and reports no error. Pak CI pins the kit by tag, so neither
  these fields nor the Section and `omit:` version gates reach an official
  pak release until a newer kit is tagged and the pak bumps its pin.
- Snippets are composed for this page; keys are generic.

## Dashboard level

| YAML | Wire | Notes |
|---|---|---|
| `time_range: last7Days` | `states: [{"key": "permDashboardTime_dashboard_<id>", "value": <product string>}]` | Values: `last10Minutes`, `lastHour`, `last6Hour`, `last12Hour`, `last24Hour`, `last7Days`, `last30Days`, `last90Days`, `currentMonth`. The renderer writes the product's verbatim value (for example `o%3AdateRange%3Ds%253Alast7Days%5EdateRangeText%3Ds%253A7D`); 20 of the 52 third-party dashboards and 46 to 67 built-ins per version carry one. Not modeled: the absolute-date form (one built-in per version) and `ext-element-<n>` UI residue |
| `disabled: true` | `disabled: true` | default false. 40 of 52 third-party, 25 to 51 built-ins. Effect on import not tested: on the built-ins it marks retired dashboards (every disabled 8.18.7 and 9.0.2 built-in is also `hidden`, 17 of 25 are `(DEP)` or described as deprecated), so it is the dashboard list's disabled state, which keeps the dashboard from users. Only to reproduce a source dashboard |
| `edit_allowed: true` | `editAllowed: true` | only true seen (every 9.1.1 built-in; absent on 8.18.7 and 9.0.2) |
| `doc_center_key: vcom_522` | `docCenterKey` | `vcom_<digits>` |
| `column_proportion: "1-1"` | `columnProportion` | legacy layout; values seen `1`, `1-1`, `0.5`, `0.5-0.5`, `0.333-0.334-0.333`, `0.95`, `0` |
| `column_count: 0` | `columnCount` | values seen -1, 0, 1, 2, 3 |
| `omit: [temporary]` | no `temporary` | 9.1.1 exports drop it. Floor 9.1.1 (§Omit version floors): a Tier 2 pak build fails on it |
| `name_path: ""` | `namePath: ""`, `name` without a folder prefix | no folder, whatever the entry point's default (below) |
| `omit: [name_path]` | no `namePath` | needs `name_path: ""` written in the YAML: an absent `name_path` is a load error, as is a non-empty one. Floor 8.18.7: passes the Tier 2 pak gate |
| `omit: [folder_in_name]` | `name` without the `<name_path>/` prefix, `namePath` kept | needs a non-empty `name_path` written in the YAML. One third-party dashboard; such a dashboard is not placed in the folder. No product export shows it: a Tier 2 pak build fails on it |
| `omit: [widget_interactions]` | no `widgetInteractions` | error with `interactions:` set. Floor 9.1.1: a Tier 2 pak build fails on it |

**`name_path`: absent versus empty.** A string, `""` included, is the
author's folder and is never replaced. Only an absent (or `null`)
`name_path` takes the entry point's default folder, and the defaults differ:
`VCF Content Factory` for factory validate, a factory-provenance file in a
bundle, a discrete or release build of factory content, and every dashboard
a pak's `_load_bundled_content` loads (the buildkit's vendored copy
included); `""` for a third-party file in a bundle and the corpus walkers.
So the two folder omits are checked against the YAML alone, never the
default: the same file loads the same way through every entry point. Before
2026-11-12 (Codex P2 on PR 356) an explicit `""` fell back to the default,
so `name_path: "", omit: [name_path]` failed in a pak and a factory load
and only loaded where the default happened to be `""`. Product exports
never write `namePath: ""`: in every export read (the built-in corpora,
the third-party paks) a folderless dashboard leaves the key out. The renderer has always written
`namePath: ""` for a folderless dashboard and still does for `name_path: ""`
without the omit. That shape is the factory's long-standing folderless
render, not one copied from an export; add `omit: [name_path]` to match an
export exactly.

`hidden` and `summary_for` already existed and round-trip: 30 hidden
third-party dashboards and the six per-folder Summary dashboards render
`hidden` exactly, and `summary_for: VMWARE:VMFolder` (and the other five
folder kinds) passes the Summary-page rule (no pinned widget) and is bound
by the pak builder's `content/dashboards/dashboards.properties`
(`<dir>=VMWARE:VMFolder`, the directory being the dashboard's slug, not the
source's folder name; the installer keys on the directory, so the binding is
the same). A source file that carries several dashboards (the third-party
`Input dashboards.json` holds 34) is expressed as one YAML file per
dashboard; each renders alone, and the shared `entries` table is rebuilt per
dashboard with only the kinds it uses.

Not modeled: leading or trailing whitespace on the dashboard `description`
(the loader strips it); `import-local` records it as a loss, accepted only
where the render is the source stripped.

Not modeled: `adapterName`. Exports write the owning solution's name
(`VMware vSphere` on 84 built-ins; our own compliance pak, built with
`adapterName: vcfcf_compliance`, comes back as `VCF Content Factory
Compliance`), so it records install ownership. The pak builder sets it from
the owning adapter (`render_dashboards_bundle_json(owning_adapter_kind=)`);
YAML cannot claim it.

## Widget fields common to every type

| YAML | Wire | Notes |
|---|---|---|
| `description:` | `config.description` | the widget's info text (Section: replaces the fixed `""`) |
| `title_localized:` | `config.titleLocalized` | Section: replaces the default (the title) |
| `collapsed: true` | widget `collapsed` | TextDisplay, View, MetricChart, Scoreboard, ResourceList, AlertList (the types an export carries it on); Section keeps its own |
| `view_details: ""` | `config.viewDetails: ""` | the empty string every 9.x export writes is accepted |
| `omit:` | drops a default key | per type, see below |

Not modeled: leading or trailing whitespace on the display strings the
dashboard loader strips. `import-local` records each as a loss at its key,
accepted only where the render is exactly the source stripped (an interior
change is a difference), in three classes: the widget `title` (and
`config.title`, which is the title); labels, meaning a Scoreboard,
MetricChart or PropertyList metric entry's `label`, `metricName` and `unit`
(11 Scoreboard labels on 2 third-party dashboards, `"Read Latency "`; 9
9.1.1 built-ins carry some, 7 labels on the 2 of them that convert), a HealthChart `metricName` / `metricFullName`, a
ParetoAnalysis `metricName` / `metric.name`, and a Heatmap tab's
`colorBy.value`, `sizeBy.value` and `groupBy.text` / `originalText`; and the
TextDisplay HTML (`config.editorData`). `labelLocalized`, `labelOrig`,
`description` and `titleLocalized` are kept verbatim by the loader. Strings
the loader strips that are keys or references (metric keys, kinds, a pinned
resource's name, a view name, `viewDetails` routes, enumerations) are not
covered: stripping one changes what it names, so it stays a difference.

Not modeled: a `config.widgetId` that names no widget of its own dashboard
(23 widgets on 3 third-party dashboards, none of the 179 9.1.1 built-ins,
which write the widget's own id on 123 widgets and nothing else). 22 of the
23 ids are on no dashboard of the pack and one is a widget of a sibling
dashboard the page was copied from; none is referenced anywhere else in its
dashboard (no interaction, navigation or state), so it is clone residue
with no effect. `ui.widget_id: true` renders the widget's own id instead.
`import-local` records it as a loss at that key only when the id is none of
the dashboard's widget ids; one naming another widget of the same dashboard
stays a TOOLSET GAP (no export shows one).

### `ui:` (UI persistence the product writes)

Carried for fidelity. An author writing new content leaves `ui:` out.

| YAML (`ui:`) | Wire | Notes |
|---|---|---|
| `states: [{key: perm_toolbarVisible_, value: "b%3A0"}]` | widget `states[]`, key `<key>widget_<dashboard id>_<widget id>` | every state key in all four corpora has exactly that form, so YAML names only the prefix. Prefixes are a closed list per type (`WIDGET_STATE_PREFIXES`). The value is the product's URL-encoded ExtJS state string, verbatim (`b%3A`, `s%3A`, `o%3A`, `n%3A`, `a%3A`, or `o%25` for the grid). A list view's table state embeds the widget's own key in its column ids; write that part as `{self}` and the renderer expands it to `widget_<dashboard id>_<widget id>`, so the value follows the widget's id |
| `height: 324` | widget `height` | default 600; exports carry 0 or the pixel height |
| `state: ""` | widget `state` | only `""` seen |
| `tab_id: true` | widget `tabId` = the dashboard id | |
| `widget_id: true` | `config.widgetId` = the widget id | |
| `config_key: true` | `config.key` = the widget type | |
| `legacy_xy: {x: 1, y: 2}` | widget `x`, `y` | View widgets in older exports |
| `view_type: LIST` | `config.viewType` (View) | only LIST; it appears only beside `config.widgetId` (the newer editor) and only on widgets whose view is a list view (18 third-party, 43 to 45 built-ins, never on another view type). A cache of the view's presentation type; built-in list-view widgets without it work. Load error beside a factory view that is not a list view |
| `undefined: [{id: percent, name: "%"}]` | `config.undefined` (HealthChart) | the 9.x HealthChart editor's unit combo saved under a key that evaluated to `undefined`; `metricUnit` stays `Default Unit` beside it, so the widget does not read it. Carried for fidelity, not authored (24 third-party, 2 built-in) |
| `custom_filter_mode: tagPicker` | `config.customFilter.filterMode` | HealthChart, ResourceRelationshipAdvanced, AlertList |
| `gauge_switches: true` | `showRemaining`, `showPercentText`, `focusOnPercent` on a non-gauge Scoreboard | the component ignores them on themes other than 9; error on a gauge (which always emits them) |
| `blank_relationship_mode: true`, `visual_theme_false: true` | `relationshipMode: ""`, `visualTheme: false` (ResourceRelationshipAdvanced) | editor residue |
| `empty_navigations: true` | `dashboardNavigations: {"<widget id>": []}` | error beside `navigations:` |

```yaml
- id: hosts
  type: View
  title: Hosts
  view: "[VCF Content Factory] Host List"
  description: "Hosts in the selected cluster."
  ui:
    height: 324
    widget_id: true
    view_type: LIST
    states:
      - {key: perm_toolbarVisible_, value: "b%3A0"}
      - {key: perm_isDashboardTime_, value: "b%3A1"}
```

## Per type

**View.** `traversal_spec_id:` (string or null) sets `config.traversalSpecId`
(historically null; exports carry `""` on most widgets, or a spec name).
`pin.traversal_spec:` sets the pinned resource's nested `traversalSpecId`
(historically `""`), self-provider View only, authored explicitly and never
inferred (see the note above `render._resolve_view_pin`).

**Scoreboard / MetricChart.** Scoreboard: `old_metric_values:` (historically
true; every third-party Scoreboard carries false), `layout_mode: fixedSize`
(six third-party Scoreboards), `pin_resource: true` with `self_provider:
true` and `pin:` renders `config.resource: [{name, id}]` plus an
`entries.resource` row (a self-provider Scoreboard pinned to vSphere World;
off by default because repo Scoreboards carry a pin the renderer has never
emitted), `omit: [sub_mode]`. MetricChart: `refresh_content:` (historically
true). Metric entries (`metrics:`):

| YAML | Wire |
|---|---|
| `link:` | entry `link` (default `""`) |
| `label_localized:`, `label_orig:` | `labelLocalized`, `labelOrig` |
| `metric_unit:` | `metricUnit` (the older editor's unit key, beside or instead of `unit`) |
| `def_unit:` | `defUnit` |
| `resource_kind_name:` | `resourceKindName` (exports write the display name, for example `Cluster Compute Resource`; cosmetic) |
| `unit: ""` | `unit: ""` (an absent unit stays null) |
| `unit_id: -1` | `metricUnitId: -1` (the product's Auto unit id, an integer) |
| string bounds | with `is_string_metric: true` and `color_method: 0`, `yellow_bound: "1"`, `orange_bound: "1"`, `red_bound: "false"` render as strings (string-property match coloring, 18 to 50 built-in entries per version). All three strings, never a mix |
| `omit: [label, max_value, handle_old_coloring, unit, link]` | drops those keys; `unit` drops `unit` and `metricUnitId` together (they never appear apart) |

**HealthChart.** `relationship_mode: children` renders `relationshipMode: -1`
(the only non-default value seen). `tag_filter:` renders `config.tagFilter`
(historically null), the same object a ResourceList builds:

```yaml
tag_filter:
  resource_kinds: [{adapter_kind: VMWARE, resource_kind: ClusterComputeResource}]
  states: ["2"]       # only "2" seen
  statuses: ["4"]     # only "4" seen
```

Kinds get `entries.resourceKind` rows; `path` lists kinds, then
`/source/state/state:<v>`, then `/source/status/status:<v>`.

**ParetoAnalysis.** `refresh_content:` (historically true; every third-party
Pareto carries false), `relationship_mode: children` (scalar -1; historically
`[-1, 0]`), `max_value:` (number or null, emitted when written),
`metric_label:` (`config.metricName`, which defaults to `metric_name`;
exports carry a different or empty label), `metric_unit: {id, name}`
(historically `{-1, Auto}`), `yellow_bound`/`orange_bound`/`red_bound`
(all three or none), `percentile_value:` with `top_option: percentile`, and
`additional_columns:`:

```yaml
additional_columns:
  - metric_key: summary|total_number_vms
    metric_name: Summary|Total Number of VMs
    label: VMs                         # boxLabel
    adapter_kind: VMWARE               # default: the widget's kind
    resource_kind: ClusterComputeResource
```

`metric_key` passes through verbatim, like every other widget metric
surface (a Scoreboard metric, a HealthChart key): `supermetric:"<name>"` is
not resolved here, because the dashboard renderer has no super metric map
(only the view renderer does). Write a super metric as its wire key,
`Super Metric|sm_<uuid>`; the `supermetric:"<name>"` form would render a
blank column and the walkers would read it as a built-in key.

**Heatmap.** Widget: `relationship_mode: children`, `selected_tab:` (`value`,
historically 0). Tab: `name_localized`, `name_orig`, `model_id: true` (the
tab's `extModel` id), `tag_filter:` (or null), `filter_mode: customFilter`,
`custom_filter:` (or null), `group_by.parent_text:` (historically the
adapter kind key; exports carry `vCenter` or `vCenter Adapter`), and
`omit: [tag_filter, custom_filter, group_by_kind_keys, color_min_value]`.
Not modeled: leading or trailing whitespace on a tab `name` (one
third-party tab, `"CPU "`): the dashboard loader strips it. `import-local`
records it as a loss, accepted only where the render is the source name
stripped.

```yaml
custom_filter:
  - adapter_kind: VMWARE
    resource_kind: Datastore           # rendered 002006VMWAREDatastore
    conditions:
      - {filter_type: properties, metric_key: summary|isLocal, metric_name: Summary|Is Local,
         condition: EQUALS, value: "false", string_metric: true, metric_unit: null}
```

`filter_type`: `properties`, `metrics`; `condition`: `EQUALS`, `GREATER_THAN`
(the values seen). A custom filter may sit beside `filter_mode: tagPicker`
(saved but not active), as exports show.

**ResourceRelationshipAdvanced.** `tag_filter: null` (no kind filter, error
with `resource_kinds`), `omit: [pagination_number, select_first_row]`.

**AlertList.** `omit: [alert_definitions]` (exports leave the key out).

**Section.** `description:` and `ui.widget_id: true` render as above.

**Navigations.** `dashboard_id:` targets may name receiving widgets by raw
UUID with `widget_ids: [<uuid>]` (a product-shipped dashboard's widget ids
are fixed content; 28 third-party navigations do this); `widgets:` stays
local ids on a named target. `ui.empty_navigations: true` renders an empty
list for the widget (exports carry them; no effect); `navigations: []` keeps
rendering nothing, as it always has. Not modeled: navigation entries keyed by a widget that is not on the
dashboard (102 built-in, 4 third-party): they do nothing.

## Dependency walkers

ParetoAnalysis `additional_columns` and Heatmap `custom_filter` conditions
name metric keys outside the fields the walkers read before. One helper,
`loader.widget_extra_metric_refs(widget)`, returns them, and every walker
over loaded YAML that reads widget metric keys calls it:
`common/dep_walker.py` (`extract_refs_from_dashboards`, the live
pre-flight, and `collect_deps`, which bundles a super metric named only
there) and `packaging/deps.py` (`_refs_from_widgets`, the describe-cache
audit). The exception is the `vcfcf_extractor` enablement walk
(`extractor.py`, the dashboard widget metric-ref loop): its widgets come
from `reverse.py`, which never fills these two fields, so it does not call
the helper and loses nothing. Tag-filter kinds are resource kinds, not
dependencies. The staged-bundle audit's dashboard
reader (`packaging/audit.py` `_refs_from_dashboard_json`) expects a
`dashboardList`/`widgetList` layout the renderer has never written, so it
reads no dashboard keys at all; that predates this change.

## Section and the oldest targeted build (issue #199)

`Section` needs VCF Operations 9.1.1 or later; on 9.0.x the importer aborts
the whole dashboard. Tier 2 paks declare their targets: RULE-019 and the
SDK compat lines (`sdk_builder._SDK_COMPAT_LINES`: 8.18.7, 9.0, 9.1.1.0100).
The pak build therefore fails a bundled dashboard whose widget types the
oldest line (`sdk_builder._oldest_supported_line()`, 8.18.7) cannot import,
naming the file, the dashboard, the widget ids and the consequence. Content
bundles declare no target; validate and bundle builds warn, naming the
file, the dashboard and the consequence.
`Dashboard.widget_version_problems(target)` is the check.

The gate runs after the bundled content loads, in
`sdk_builder.check_bundled_version_floors`, beside the `omit:` gate below:
`build-sdk` fails on it, and `validate-sdk` reports each problem as
`version floor: ...` next to the naming, bundled-content, stock-id and
localization checks instead of stopping them.

## Omit version floors

An `omit:` entry removes a key the renderer always writes. The 9.0.2
importer reads dashboard JSON with strict getters, so a key an older build
expects can abort the whole dashboard while install reports success (lesson
`unknown-widget-type-aborts-pak-dashboard-import.md`). Each entry's floor is
the oldest VCF Operations version whose own built-in export (the 8.18.7,
9.0.2 and 9.1.1 scope-ALL exports above) shows the key absent. A floor
records that the product wrote that shape on that version; import of the
shape there is not separately tested. Tables:
`widget_versions.DASHBOARD_OMIT_MIN_OPS_VERSION`,
`WIDGET_OMIT_MIN_OPS_VERSION`, `METRIC_OMIT_MIN_OPS_VERSION`,
`HEATMAP_TAB_OMIT_MIN_OPS_VERSION`.

| Entry | Floor | Absent on (8.18.7 / 9.0.2 / 9.1.1) |
|---|---|---|
| dashboard `temporary` | **9.1.1** | 0 of 163 / 0 of 180 / 179 of 179 |
| dashboard `widget_interactions` | **9.1.1** | 0 of 163 / 0 of 180 / 37 of 179 |
| dashboard `folder_in_name` | **none** | no export (one third-party dashboard, target build not stated) |
| dashboard `name_path` | 8.18.7 | 14 / 15 / 15 |
| AlertList `alert_definitions` | 8.18.7 | 8 of 14 / 10 of 22 / 8 of 28 |
| ResourceRelationshipAdvanced `pagination_number` | 8.18.7 | 30 of 30 / 23 of 28 / 22 of 30 |
| ResourceRelationshipAdvanced `select_first_row` | 8.18.7 | 29 of 30 / 20 of 28 / 20 of 30 |
| Scoreboard `sub_mode` | 8.18.7 | 20 of 173 / 22 of 198 / 21 of 235 |
| MetricChart `sub_mode` | 8.18.7 | 12 of 71 / 22 of 91 / 12 of 115 |
| metric entry `label` | 8.18.7 | 268 of 1,536 entries |
| metric entry `max_value` | 8.18.7 | 1,516 of 1,536 |
| metric entry `handle_old_coloring` | 8.18.7 | 379 of 1,536 |
| metric entry `unit` | 8.18.7 | 285 of 1,536 |
| metric entry `link` | 8.18.7 | 242 of 1,536 |
| Heatmap tab `tag_filter` | 8.18.7 | 20 of 77 tabs |
| Heatmap tab `group_by_kind_keys` | 8.18.7 | 51 of 77 |
| Heatmap tab `color_min_value` | 8.18.7 | 15 of 77 |
| Heatmap tab `custom_filter` | 8.18.7 | 27 of 77 |

`Dashboard.omit_version_problems(target)` is the check. A Tier 2 pak build
(`check_bundled_version_floors`, target the oldest supported line, 8.18.7)
fails on an entry whose floor is above the target or unknown, naming the
file, the dashboard, the widget, metric or tab, and the entry. With no
target (content bundles, discrete and release builds, `validate`)
`Dashboard.validate()` warns for an entry whose floor is above 8.18.7, the
oldest export read, or unknown. The same tables exist for report sections
(`template_fidelity_wire_format.md`) and symptoms
(`alert_fidelity_wire_format.md`); alerts have no `omit:`.

## Raw view ids on View widgets

A View widget whose `view:` is a UUID that names no loaded view is the
external-view passthrough (a product-shipped or other-pak view); nothing
checked it before. `vcfcf_dashboards validate` now warns when the id is not
in the stock-id baseline (`src/vcfcf_core/stock_ids/stock_ids_baseline.json`):
a typo renders a blank widget, but the id may be another pak's view, so it
is never an error. In a Tier 2 pak (`validate-sdk`, `build-sdk`) a stock id
the baseline shows absent on a supported line is also a warning naming
the lines. Check: `Dashboard.external_view_references()` and
`stock_ids.guard.reference_warnings`. Navigation `dashboard_id:` targets
are raw dashboard ids too and are still unchecked.

The dependency walker `common/dep_walker.collect_deps` (the third-party
project-boundary check in `vcfcf_dashboards validate`, discrete builds, the
bundle composer, navigation targets) records such an id as external
(`DepGraph.external_views`, `(content_type, id, where)`): nothing to bundle
and no error. Before 2026-11-13 it reported it as an unknown view name, so a
third-party project could not use the passthrough at all (found running the
validation chain on `import-local` output). A raw id that is one of the
corpus's own views is an error there: reference it by name so it is bundled.
Every caller that builds something deliverable (the bundle builder, the
discrete builder and so the release builder, the composer, the navigation
closure) prints a `PREREQUISITE:` line per external view and runs the same
stock-id baseline check as validate and the report `view_id` check
(`vcfcf_packaging.navigation.print_external_view_prerequisites`): a warning
when the id is not a known product view, or is absent on a supported line.

## Shapes found by `import-local` (2026-11-13)

Read off the 9.1.1 built-in export and the 52 third-party dashboards with the
offline converter's source accounting (`authoring/importer_offline_conversion.md`);
none has a YAML form today, so a dashboard carrying one stops with a TOOLSET
GAP rather than converting changed:

- AlertList `config.alertDefinitions` as bare id strings
  (`["AlertDefinition-..."]`, "License Server Health", "vSAN Snapshots and
  Replica"); the renderer writes `[{"id": ...}]` objects.
- MetricChart `config.relationshipMode.relationshipMode` as a list
  (`[1, -1, 0]`, "vSAN Performance"); the renderer writes a scalar.
- Values other than the renderer's constants: `refreshContent: true` on 18
  View widgets and on AlertLists, a HealthChart `metricUnit` other than
  `{-1, "Default Unit"}`, `relationshipMode` other than 0 on a Scoreboard, a
  ParetoAnalysis pinned through `config.resource[]`, a `config.widgetId`
  naming another widget of the same dashboard (none seen; one naming no
  widget of the dashboard is a recorded loss, §Widget fields common to
  every type).
- A `namePath` with leading or trailing whitespace: the loader strips it.
  It is the dashboard's folder (a name, not display text), and it is not
  recorded as a rename, so it stays a GAP (none seen).

## Keys an older loader ignored

Each key below was read as nothing by the loader before 2026-11-12 (it does
not reject unknown keys), and now renders or is a load error. Riskiest on an
existing YAML: **`disabled: true`**, which used to do nothing and now
ships the dashboard disabled (above), and, on alerts and recommendations,
**`id:`**, which now re-keys the object on the content-import XML path (see
`alert_fidelity_wire_format.md`). Report and alert keys:
`template_fidelity_wire_format.md`, `alert_fidelity_wire_format.md`.

- Dashboard: `time_range`, `disabled`, `edit_allowed`, `doc_center_key`,
  `column_proportion`, `column_count`, `omit`; and `name_path: ""`, which
  took the entry point's default folder and now means no folder.
- Widget, any type: `description`, `title_localized`, `ui` (and under it
  `states`, `height`, `state`, `tab_id`, `widget_id`, `config_key`,
  `legacy_xy`, `view_type`, `undefined`, `custom_filter_mode`,
  `gauge_switches`, `blank_relationship_mode`, `visual_theme_false`,
  `empty_navigations`), `omit`.
- Widget, per type: View `traversal_spec_id`; `pin.traversal_spec`;
  HealthChart and ResourceRelationshipAdvanced `tag_filter`; Scoreboard
  `old_metric_values`, `pin_resource`; MetricChart `refresh_content`;
  ParetoAnalysis `refresh_content`, `max_value`, `yellow_bound`,
  `orange_bound`, `red_bound`, `percentile_value`, `metric_label`,
  `metric_unit`, `additional_columns`; Heatmap `selected_tab`.
- Metric entry (Scoreboard, MetricChart): `link`, `label_localized`,
  `label_orig`, `metric_unit`, `def_unit`, `resource_kind_name` (a load
  error on a `metric_mode: resource` Scoreboard, whose entries carry no
  `resourceKindName`), `omit`; and `unit: ""`, which rendered null and now
  renders `""`.
- Heatmap tab: `name_localized`, `name_orig`, `model_id`, `tag_filter`,
  `filter_mode`, `custom_filter`, `omit`, `group_by.parent_text`.

Newly accepted rather than newly read (a load error before, valid now):
`collapsed` on TextDisplay, View, MetricChart, Scoreboard, ResourceList and
AlertList, `relationship_mode: children` on HealthChart, ParetoAnalysis
and Heatmap, and navigation `widget_ids` (navigation entries reject
unknown keys).

## Round trip (52 third-party dashboards)

Mechanical JSON-to-YAML mapping of all 52, each loaded and rendered alone
by the factory and compared with its source (ignoring ids the product
renumbers, mapped by position: widget ids also inside state keys,
interactions, navigations, Section members, `config.widgetId`, `tabId`;
synthetic `entries` ids, resolved to adapter/kind/name; `extModel` ids;
creation and update times and user ids; whitespace; key order; unused
`entries` rows): **18 identical**. 31 more differ only by `adapterName`
(pak ownership, above), and 3 by stale navigation entries (5 entries).
Whitespace is normalized before comparing (`" ".join(text.split())`), which
also hides a change that only adds or removes whitespace. The comparator
was checked by mutation over **12 of the 52** dashboards: 3,770
single-key deletions and value changes to their renders, all detected. The
companion XML mutation check covered the 16 report templates only, not the
alerts or symptoms (`template_fidelity_wire_format.md` §Round trip).

Version gates on the same 52 (2026-11-12): 11 use an `omit:` entry above
8.18.7 (all 11 `temporary`, one also `widget_interactions`, one also
`folder_in_name`; two of them also carry a Section). In a content bundle all
52 build and those 11 warn. In a Tier 2 pak those 11 fail the build, so 41
are pak-eligible as round-tripped: 11 of the 18 identical, 39 of the 49
with `adapterName` set aside. A pak that wants the other 11 drops the
entry (the render then carries `temporary: false`, which every 8.18.7 and
9.0.2 export has) and accepts that one-key difference.
