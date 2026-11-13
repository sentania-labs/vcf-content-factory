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
- **Keys the old parser silently ignored now render**: widget
  `description`; `refresh_content` on MetricChart and ParetoAnalysis;
  ParetoAnalysis `max_value`, the three bounds and `percentile_value`;
  metric-entry `link`. No YAML in the repo or the registered paks set any
  of them (the regression above); a clone that does sees them appear.
- **A field the renderer cannot honour is a load error naming the file and
  field**, and so is a value no product export carries. `omit:` entries
  that contradict a field the YAML also sets are load errors.
- **Closed vocabularies hold only values seen in product exports**: the
  9.0.2, 8.18.7 and 9.1.1 built-in dashboard exports of clean labs (180,
  163 and 179 dashboards) and one third-party pak's 52 dashboards. Counts
  below are from those corpora.
- **SDK-adapter paks need a newer buildkit** for any field on this page
  (the kit vendors `loader.py` and `render.py`; kit 1.0.28 rejects them).
- Snippets are composed for this page; keys are generic.

## Dashboard level

| YAML | Wire | Notes |
|---|---|---|
| `time_range: last7Days` | `states: [{"key": "permDashboardTime_dashboard_<id>", "value": <product string>}]` | Values: `last10Minutes`, `lastHour`, `last6Hour`, `last12Hour`, `last24Hour`, `last7Days`, `last30Days`, `last90Days`, `currentMonth`. The renderer writes the product's verbatim value (for example `o%3AdateRange%3Ds%253Alast7Days%5EdateRangeText%3Ds%253A7D`); 20 of the 52 third-party dashboards and 46 to 67 built-ins per version carry one. Not modeled: the absolute-date form (one built-in per version) and `ext-element-<n>` UI residue |
| `disabled: true` | `disabled: true` | default false. 40 of 52 third-party, 25 to 51 built-ins |
| `edit_allowed: true` | `editAllowed: true` | only true seen (every 9.1.1 built-in; absent on 8.18.7 and 9.0.2) |
| `doc_center_key: vcom_522` | `docCenterKey` | `vcom_<digits>` |
| `column_proportion: "1-1"` | `columnProportion` | legacy layout; values seen `1`, `1-1`, `0.5`, `0.5-0.5`, `0.333-0.334-0.333`, `0.95`, `0` |
| `column_count: 0` | `columnCount` | values seen -1, 0, 1, 2, 3 |
| `omit: [temporary]` | no `temporary` | 9.1.1 exports drop it |
| `omit: [name_path]` | no `namePath` | needs `name_path: ""` |
| `omit: [folder_in_name]` | `name` without the `<name_path>/` prefix, `namePath` kept | one third-party dashboard; such a dashboard is not placed in the folder |
| `omit: [widget_interactions]` | no `widgetInteractions` | error with `interactions:` set |

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

**Heatmap.** Widget: `relationship_mode: children`, `selected_tab:` (`value`,
historically 0). Tab: `name_localized`, `name_orig`, `model_id: true` (the
tab's `extModel` id), `tag_filter:` (or null), `filter_mode: customFilter`,
`custom_filter:` (or null), `group_by.parent_text:` (historically the
adapter kind key; exports carry `vCenter` or `vCenter Adapter`), and
`omit: [tag_filter, custom_filter, group_by_kind_keys, color_min_value]`.

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
that reads widget metric keys calls it: `common/dep_walker.py`
(`extract_refs_from_dashboards`, the live pre-flight, and `collect_deps`,
which bundles a super metric named only there) and `packaging/deps.py`
(`_refs_from_widgets`, the describe-cache audit). Tag-filter kinds are
resource kinds, not dependencies. The staged-bundle audit's dashboard
reader (`packaging/audit.py` `_refs_from_dashboard_json`) expects a
`dashboardList`/`widgetList` layout the renderer has never written, so it
reads no dashboard keys at all; that predates this change.

## Section and the oldest targeted build (issue #199)

`Section` needs VCF Operations 9.1.1 or later; on 9.0.x the importer aborts
the whole dashboard. Tier 2 paks declare their targets: RULE-019 and the
SDK compat lines (`sdk_builder._SDK_COMPAT_LINES`: 8.18.7, 9.0, 9.1.1.0100).
The pak build therefore fails a bundled dashboard whose widget types the
oldest line (`sdk_builder._oldest_supported_line()`, 8.18.7) cannot import,
naming the dashboard, the widget ids and the consequence. Content bundles
declare no target; validate and bundle builds warn, naming the file, the
dashboard and the consequence. `Dashboard.widget_version_problems(target)`
is the check.

## Round trip (52 third-party dashboards)

Mechanical JSON-to-YAML mapping of all 52, each loaded and rendered alone
by the factory and compared with its source (ignoring ids the product
renumbers, mapped by position: widget ids also inside state keys,
interactions, navigations, Section members, `config.widgetId`, `tabId`;
synthetic `entries` ids, resolved to adapter/kind/name; `extModel` ids;
creation and update times and user ids; whitespace; key order; unused
`entries` rows): **18 identical**. 31 more differ only by `adapterName`
(pak ownership, above), and 3 by stale navigation entries (5 entries). The
comparator was checked by mutation: 3,770 single-key deletions and value
changes to renders were all detected.
