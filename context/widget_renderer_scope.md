# Dashboard widget renderer scoping

**Purpose.** Plan the next wave of widget-type support in
`vcfops_dashboards/render.py`. Inventory every widget type still
unsupported, categorize each by engineering value, and propose an
implementation order with draft YAML schemas.

**Source data.**
- Live-instance survey from 2026-04-09 in
  `context/widget_types_survey.md` (231 dashboards, 2,019 widgets).
- Reference-repo resurvey run 2026-04-11 over 131 `dashboard.json`
  files extracted from `references/` (AriaOperationsContent,
  brockpeterson_operations_dashboards, tkopton_aria_operations_content,
  dalehassinger_unlocking_the_potential) + 2 `dashboard.json` files
  from a fresh lab export via
  `POST /api/content/operations/export` with
  `{"scope":"ALL","contentTypes":["DASHBOARDS"]}`.
- Loader/renderer source: `vcfops_dashboards/loader.py`,
  `vcfops_dashboards/render.py`.

**Scope.** Research and planning only. No `vcfops_*/` or content
YAML edits. A follow-up `tooling` agent invocation will implement
the recommendations.

---

## Current coverage

`render.py::_build_dashboard_obj()` dispatches on `w.type` for
exactly these ten types (line 968):

1. `ResourceList`      - `_resource_list_widget`
2. `View`              - `_view_widget` (incl. self-provider+pin)
3. `TextDisplay`       - `_text_display_widget`
4. `Scoreboard`        - `_scoreboard_widget`
5. `MetricChart`       - `_metric_chart_widget`
6. `HealthChart`       - `_health_chart_widget`
7. `ParetoAnalysis`    - `_pareto_analysis_widget`
8. `AlertList`         - `_alert_list_widget`
9. `ProblemAlertsList` - `_problem_alerts_list_widget`
10. `Heatmap`          - `_heatmap_widget`

Live-instance observed coverage: **1,881 / 2,019 widgets = 93%**
(from `status.md` table). Everything else is rejected at load time.

Shared infrastructure these renderers depend on:

- **`kind_index`** - `(adapter_kind, resource_kind) -> int`, emits
  `entries.resourceKind[]` with `internalId` values like
  `resourceKind:id:<N>_::_`.
- **`resource_index`** - `(adapter_kind, resource_kind) -> int`,
  emits `entries.resource[]` for pinned self-provider widgets,
  produces `resource:id:<N>_::_` ids.
- **`MetricSpec`** (`loader.py:131`) - 1:1 maps to one
  `resourceKindMetrics[]` entry. Reused by Scoreboard and
  MetricChart. **PropertyList and SparklineChart will reuse this
  directly.**
- **`_render_metric_spec()`** (`render.py:412`) - produces the JSON
  dict for one metric entry.

---

## Survey results - unsupported widget types

Merged view of the 2026-04-09 live survey and the 2026-04-11
reference-repo resurvey. Live counts are authoritative (larger
sample, real-world usage distribution); reference counts confirm
that the repo dashboards exercise the same types.

| Widget type | Live (2,019w sample) | Live dashboards | Reference (134d sample) | Category |
|---|---|---|---|---|
| **PropertyList**                 | **47** | **23** | 67 | **HIGH - recommended #1** |
| ResourceRelationshipAdvanced     | 34     | 34     | 41 | MEDIUM - recommended #2 |
| **SparklineChart**               | 4      | 3      | 12 | **MEDIUM - recommended #3** |
| LogAnalysis                      | 14     | 7      | 15 | LOW - deferred |
| ResourceRelationship             | 6      | 5      | 10 | WON'T DO - deprecated |
| MetricPicker                     | 5      | 5      | 8  | LOW - deferred (rare use, interaction-only) |
| IntSummaryCapacity               | 3      | 2      | 7  | LOW - IntSummary family (batchable) |
| IntSummaryHealth                 | 3      | 3      | 3  | LOW - IntSummary family |
| IntSummaryStress                 | 3      | 3      | 3  | LOW - IntSummary family |
| IntSummaryRisk                   | 2      | 2      | 0  | LOW - IntSummary family |
| IntSummaryEfficiency             | 2      | 2      | 0  | LOW - IntSummary family |
| IntSummaryAlertVolume            | 1      | 1      | 2  | LOW - IntSummary family |
| IntSummaryTimeRemaining          | 0 (ref only) | -  | 3 | LOW - IntSummary family |
| IntSummaryWorkload               | 0 (ref only) | -  | 1 | LOW - IntSummary family |
| Skittles                         | 4      | 4      | 4  | LOW - batchable with IntSummary |
| TopologyGraph                    | 4      | 4      | 4  | WON'T DO - NSX-specific + XML config file reference |
| TagPicker                        | 1      | 1      | 1  | LOW - trivial but rare |
| ScoreboardHealth                 | 1      | 1      | 1  | LOW - niche single-object badge |
| MashupChart                      | 1      | 1      | 1  | WON'T DO - state is persisted UI prefs only |
| Geo                              | 1      | 1      | 1  | WON'T DO - geo-adapter dependent |
| ContainerOverview / Details      | 2      | 2      | 2  | WON'T DO - vRNI / Application discovery only |

**Totals.** 20 unsupported types in the live survey (138 widgets
total); 22 in the combined live+ref set. Status.md's "Other (14
types) = 91" excluded a handful of 1-count types the earlier table
grouped together - the real number is 20 live types / 138 widgets.

**Implementing PropertyList alone lifts coverage to 1,928 / 2,019 =
95.5%.** Adding ResourceRelationshipAdvanced and SparklineChart on
top brings it to 1,966 / 2,019 = **97.4%**.

---

## Per-type analysis

### PropertyList (HIGH VALUE - recommended #1)

**Count.** 47 live widgets across 23 dashboards; 67 ref widgets
across 35 dashboards. Ubiquitous in "<Object> Details" style
dashboards where a View picker broadcasts a resource and the
PropertyList shows that resource's key properties.

**Wire format.** Structural sibling of Scoreboard - the `config`
uses the same `metric.resourceKindMetrics[]` envelope as Scoreboard
and MetricChart.

```json
{
  "id": "<uuid>",
  "type": "PropertyList",
  "title": "Properties (for selected VM)",
  "gridsterCoords": {"x":1,"y":0,"w":4,"h":6},
  "config": {
    "visualTheme": 2,
    "depth": 1,
    "refreshInterval": 300,
    "relationshipMode": 0,
    "resInteractionMode": null,
    "resource": [],
    "selfProvider": {"selfProvider": false},
    "showMetricFullName": {"showMetricFullName": true},
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "title": "Properties (for selected VM)",
    "metric": {
      "mode": "resourceKind",
      "subMode": "resourceKindAll",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "summary|parentVcenter",
          "metricName": "Summary|Parent vCenter",
          "label": "Parent vCenter",
          "resourceKindName": "Virtual Machine",
          "resourceKindId": "resourceKind:id:0_::_",
          "isStringMetric": true,
          "colorMethod": 2,
          "unit": "",
          "metricUnitId": null,
          "yellowBound": null, "orangeBound": null, "redBound": null
        },
        { ... up to ~8-10 property keys ... }
      ]
    }
  }
}
```

**Variance across samples.** 20/20 reference samples use
`metric.mode = "resourceKind"` and `selfProvider = false`
(interaction-driven). None pin to a specific resource. This
homogeneity means the first cut can ignore the `resource` mode
entirely and always emit `resourceKindMetrics[]`.

**Referenced content.** Metric/property keys - mostly string
properties (`summary|parentVcenter`, `config|guestFullName`,
`config|hardware|numCpu`, `config|hardware|memoryKB`). Keys resolve
against the existing recon_metric_keys / adapter describe path;
loader can keep the same "trust the author to pass valid keys"
posture as Scoreboard today.

**Renderer complexity.** **CHEAP.** Reuses
`_render_metric_spec()` almost verbatim. One new function
`_property_list_widget(w, kind_index) -> dict` following the exact
pattern of `_scoreboard_widget`. Kind index contribution is
identical to Scoreboard (each metric's `(adapter_kind,
resource_kind)` joins the shared `kind_index`).

**Proposed YAML schema.**

```yaml
- local_id: vm_properties
  type: PropertyList
  title: "Properties (for selected VM)"
  coords: {x: 1, y: 0, w: 4, h: 6}
  property_list:
    visual_theme: 2            # 1-5, default 2
    depth: 1                   # default 1
    show_metric_full_name: true
    properties:
      - adapter_kind: VMWARE
        resource_kind: VirtualMachine
        metric_key: "summary|parentVcenter"
        metric_name: "Summary|Parent vCenter"
        label: "Parent vCenter"
        is_string_metric: true
      - adapter_kind: VMWARE
        resource_kind: VirtualMachine
        metric_key: "config|hardware|numCpu"
        metric_name: "Configuration|Hardware|Number of virtual CPUs"
        label: "vCPU"
        is_string_metric: false
      # ... more properties
```

Interaction wiring uses the existing top-level `interactions:`
block on the dashboard (`from_local_id` = View widget, `to_local_id`
= this widget, `type: resourceId`).

**Dependencies.**
- Add `PropertyListConfig` dataclass to `loader.py` mirroring
  `ScoreboardConfig`. Properties list is effectively a
  `List[MetricSpec]` plus three display flags.
- Extend `Widget` dataclass with `property_list_config:
  PropertyListConfig | None = None` field.
- Extend `loader.py::_supported_types` tuple (currently line
  389/449-ish) to include `"PropertyList"`.
- Add `elif w.type == "PropertyList": ...` branch to
  `_build_dashboard_obj()`.
- Add kind_index contribution branch in
  `render_dashboards_bundle_json()` (line 1060) mirroring the
  Scoreboard block.
- Note: `MetricSpec.is_string_metric` - the dataclass currently has
  no `is_string_metric` field. `_render_metric_spec` in render.py
  hard-codes this to `False`. PropertyList authoring needs string
  property support (`is_string_metric: true`), so the MetricSpec
  should gain an `is_string_metric: bool = False` field and
  `_render_metric_spec` should honour it. This is a small change
  touching Scoreboard/MetricChart too, and is backwards compatible
  (existing YAMLs get the default).

**Estimated size.** ~120 lines of Python across loader/render +
small dataclass change. Tests: one fixture dashboard with a
PropertyList widget + golden JSON comparison. ~half a day of
tooling work.

---

### ResourceRelationshipAdvanced (MEDIUM VALUE - recommended #2)

**Count.** 34 live / 41 ref. Interesting because live shows
one-per-dashboard (34 widgets / 34 dashboards) - it's the "put a
topology box on the details dashboard" pattern.

**Wire format.**

```json
{
  "type": "ResourceRelationshipAdvanced",
  "config": {
    "traversalSpecId": "vSphere Hosts and Clusters-VMWARE-vSphere World",
    "depth": "1,1",
    "filterMode": "tagPicker",
    "tagFilter": null,
    "paginationNumber": 5,
    "resourceId": null,
    "resourceName": null,
    "selfProvider": {"selfProvider": false},
    "visualTheme": false,
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": true},
    "relationshipMode": "",
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "selectFirstRow": {"selectFirstRow": true}
  }
}
```

**Referenced content.** `traversalSpecId` is a string name like
`"vSphere Hosts and Clusters-VMWARE-vSphere World"`. Survey of 41
ref widgets: 36 use empty-string / default (no explicit traversal
spec - the widget shows the whole inventory graph), 4 use `vSphere
Hosts and Clusters-VMWARE-vSphere World` (the OOTB vSphere
hierarchy), 1 blank/missing. So the traversal spec ID is almost
always the default and only the vSphere OOTB one appears as
override. This means authors don't need a traversal-spec catalog -
the renderer defaults to empty and accepts an optional string.

**Renderer complexity.** **CHEAP.** No metric references, no kind
index contribution, no interaction complications beyond the
standard `interactions:` block. Config is mostly constants.

**Proposed YAML schema.**

```yaml
- local_id: vm_topology
  type: ResourceRelationshipAdvanced
  title: "Topology (for selected VM)"
  coords: {x: 8, y: 0, w: 4, h: 6}
  resource_relationship:
    depth: "1,1"                              # string, default "1,1"
    traversal_spec_id: ""                     # empty = default
    pagination_number: 5
    select_first_row: true
```

**Dependencies.**
- `ResourceRelationshipAdvancedConfig` dataclass with 4 fields.
- `_resource_relationship_advanced_widget()` render function -
  literally a config-dict builder with defaults.
- No kind_index contribution.

**Estimated size.** ~60 lines. Maybe a quarter day.

---

### SparklineChart (MEDIUM VALUE - recommended #3)

**Count.** 4 live / 12 ref. Lower absolute count but structurally
almost free (reuses Scoreboard/MetricChart metric infrastructure
and adds `columnSequence` + `customFilter`). High value on
detail-page dashboards: it's the only widget that gives per-row
small time-series charts with a resource name column.

**Wire format.** Structural sibling of Scoreboard. Config has the
same `metric.resourceKindMetrics[]` envelope plus:

- `columnSequence.columnSequence`: `"graphFirst"` or `"tableFirst"`
- `customFilter.filter[]`: optional property-value filters
- `showDT`, `showResourceName`, `depth`

```json
{
  "type": "SparklineChart",
  "config": {
    "depth": 1,
    "refreshInterval": 300,
    "showDT": {"showDT": true},
    "showResourceName": {"showObjectName": false},
    "columnSequence": {"columnSequence": "graphFirst"},
    "selfProvider": {"selfProvider": false},
    "relationshipMode": {"relationshipMode": 0},
    "resource": [],
    "customFilter": {"filter": [], ...},
    "metric": {
      "mode": "resourceKind",
      "subMode": "resourceKindAll",
      "resourceMetrics": [],
      "resourceKindMetrics": [ ... same as Scoreboard ... ]
    }
  }
}
```

**Renderer complexity.** **MODERATE** due to the optional
`customFilter` block. If we ship initially without customFilter
support (pass through an empty filter) and require authors to
specify metrics like Scoreboard, it drops to CHEAP.

**Proposed YAML schema.**

```yaml
- local_id: vm_disk_sparklines
  type: SparklineChart
  title: "Disk Metrics for VM"
  coords: {x: 5, y: 0, w: 5, h: 5}
  sparkline:
    column_sequence: graphFirst   # or tableFirst
    show_dt: true
    show_resource_name: false
    depth: 1
    metrics:
      - adapter_kind: VMWARE
        resource_kind: VirtualMachine
        metric_key: "virtualDisk:Aggregate of all instances|totalReadLatency_average"
        metric_name: "Virtual Disk:Aggregate of all instances|Read Latency"
        label: "Read Latency"
        unit: "ms"
        unit_id: "msec"
```

**Dependencies.**
- `SparklineChartConfig` - sibling of `ScoreboardConfig`, reuses
  `MetricSpec`.
- `_sparkline_chart_widget()` render function - copies the
  `_scoreboard_widget` pattern, swaps in the 3 distinct display
  flags. ~80 lines.
- Kind index contribution block identical to Scoreboard.

**Estimated size.** ~80 lines. Quarter to half day.

---

### LogAnalysis (LOW VALUE - deferred)

**Count.** 14 live / 15 ref. Moderate usage but **structurally
incompatible with our portable-YAML model**: `liQueryId` refers to
a Log Insight / Log Forwarding query defined in a separate product
(vRealize Log Insight / VCF Operations for Logs). Query IDs are
UUIDs that only exist on a specific instance.

Observed config variants:

- `chartType`: `"scalar"`, `"column"`
- `liQueryMode`: `0` (inline `queryFilter`) or `1` (reference a
  `liQueryId`)
- `liViewMode`: `"all"`, `"chart"`

Mode 0 (inline query) is theoretically portable - the `queryFilter`
is an Elasticsearch-style JSON query. Mode 1 (liQueryId) is not.

**Recommendation.** Defer. When a user asks for a LogAnalysis
dashboard widget, surface it as a known limitation and ask whether
a MetricChart against `logs|*` metric keys can satisfy the intent
instead. If real demand appears later, support mode-0 inline
queries first.

---

### MetricPicker (LOW VALUE - deferred)

**Count.** 5 live / 8 ref. Config is effectively empty:

```json
{"refreshInterval": 300, "refreshContent": {"refreshContent": true}, "title": "..."}
```

MetricPicker is an **interaction provider** - it lets a user pick a
metric in the UI and broadcasts it (`type: metricId`) to receiver
widgets (usually a MetricChart). This works the moment we:

1. Add `"MetricPicker"` to the supported types list
2. Add a render function that emits the empty config
3. Allow `interactions:` entries with `type: metricId` (currently
   the loader hard-codes `type: resourceId`)

**Complexity.** CHEAP for the widget itself; the interaction-type
extension is also small. The reason to defer: the receiver widgets
that consume a broadcast `metricId` - MetricChart, HealthChart,
Scoreboard - would need renderer updates to handle the
"null metric spec until runtime" mode, which is a non-trivial
change to their current always-populate-metrics contract.

**Recommendation.** Defer until we have a concrete user request
that needs metric picker semantics. Note in the known-limitations
section of `CLAUDE.md`.

---

### IntSummary family - 8 types (LOW VALUE - batchable)

**Count.** 16 widgets total across 8 types (Health, Risk,
Efficiency, Stress, Capacity, TimeRemaining, Workload, AlertVolume).

**Structure.** All 8 types share a single config shape:

```json
{
  "refreshInterval": 300,
  "refreshContent": {"refreshContent": true},
  "selfProvider": {"selfProvider": true},
  "resource": {"resourceId": "resource:id:N_::_", "resourceName": "Universe"},
  "title": "Environment Health"
}
```

Three types (Health, Risk, Efficiency) add a `badgeMode` field.

**Renderer complexity.** CHEAP. A single `_int_summary_widget(w,
resource_index)` function serves all 8 types - the widget `type`
field is the only thing that distinguishes them, and they all use
self-provider + pin semantics via the existing `resource_index`.

**Proposed YAML schema.**

```yaml
- local_id: env_health
  type: IntSummaryHealth     # or IntSummaryRisk / ... / IntSummaryAlertVolume
  title: "Environment Health"
  coords: {x: 0, y: 0, w: 2, h: 2}
  self_provider: true
  pin:
    adapter_kind: Container
    resource_kind: Universe
  int_summary:
    badge_mode: false         # only for Health/Risk/Efficiency
```

**Dependencies.**
- Single dataclass `IntSummaryConfig` with one optional bool.
- Loader accepts all 8 type strings in the supported list and
  dispatches them to the same render function.
- Loader permits `self_provider: true` + `pin:` on IntSummary
  widgets (the existing View-widget pin machinery already
  populates `resource_index`).
- **Caveat.** These widgets commonly pin to
  `Container/Universe` (the Aggregator World root), which has
  resourceKindKey `FederationWorld` on the FederatedAdapter. The
  existing pin infra pins to a `(adapter_kind, resource_kind)`
  pair; verify that `(FederatedAdapter, FederationWorld)` or
  `(Container, Universe)` emits a valid internalId.

**Estimated size.** ~120 lines once, covers 8 types at once. Half
a day.

**Recommendation.** Worth doing as a batch after the top 3, since
the marginal cost is low and it retires 8 types at once. But the
16-widget payoff is small, so it's LOW until a user asks for a
summary-page dashboard.

---

### Skittles (LOW VALUE - batchable with IntSummary)

**Count.** 4 live / 4 ref. Badge-grid widget showing health/risk/
efficiency for a custom list of resource kinds.

**Wire format.** `config.custom[]` is a list of
`{resourceKindName, resourceKindId}` pairs, where
`resourceKindId` is a `resourceKind:id:N_::_` internalId. Kind
index contribution needed for each entry.

**Renderer complexity.** CHEAP. Each entry in `custom[]` maps to a
`(adapter_kind, resource_kind)` pair the author specifies. Reuses
`kind_index` exactly like ResourceList.

**Proposed YAML schema.**

```yaml
- local_id: env_skittles
  type: Skittles
  title: "Environment Overview"
  coords: {x: 0, y: 0, w: 4, h: 3}
  skittles:
    badges: [health, risk, efficiency]
    kinds:
      - {adapter_kind: VMWARE, resource_kind: ClusterComputeResource}
      - {adapter_kind: VMWARE, resource_kind: HostSystem}
      - {adapter_kind: VMWARE, resource_kind: VirtualMachine}
```

**Recommendation.** Bundle with the IntSummary wave - they share
the badge-rendering style of widget and both are "summary page"
components.

---

### TagPicker (LOW VALUE - trivial but rare)

**Count.** 1 live / 1 ref. Config is a single line:

```json
{"refreshInterval": 300, "refreshContent": {"refreshContent": false}, "title": "..."}
```

Broadcasts `tagFilter` to receiver widgets. Same "downstream
receivers need runtime-filter support" problem as MetricPicker -
useful only if receiver widgets accept the broadcast.

**Recommendation.** Defer. One-line config would be free to
render, but there's no value without receiver-side support.

---

### ScoreboardHealth (LOW VALUE - niche)

**Count.** 1 live / 1 ref. Single-resource health badge image.
Rarely used - the IntSummaryHealth widget covers the same
functional need with a more standard look.

**Recommendation.** Defer. If a user wants a single-object health
indicator, IntSummaryHealth is the better answer.

---

## WON'T DO - document as limitations

### ResourceRelationship (legacy)

**Count.** 6 live / 10 ref. This is the pre-
ResourceRelationshipAdvanced generation of the topology widget.
Config has `autoZoom`, `nodeSize`, `tagFilter` but no
`traversalSpecId` (it infers the graph from context). Since its
successor `ResourceRelationshipAdvanced` is already on the MEDIUM
list and all new dashboards should use the advanced variant, there
is no reason to add renderer support for the old one. New content
from this framework will use `ResourceRelationshipAdvanced`.

### TopologyGraph

**Count.** 4 live / 4 ref. NSX-specific network topology widget.
Config references `selectedConfigFile:
"defaultTopologyGraphConfig.xml"` - an XML file the widget reads
from the Ops server, which is not portable and implies the widget
is tied to NSX-adapter-installed assets. The
`lightWeightRelationships` field encodes custom relationship
traversal types. Structurally tractable but **only useful inside
NSX content**, which this framework does not target.

### MashupChart

**Count.** 1 live / 1 ref. "Object Health Timeline" widget. The
`config` object has only the four standard envelope fields
(`refreshInterval`, `refreshContent`, `selfProvider`, `title`) -
all of the rendering settings (chart type, which metrics, which
alerts, time window) live in `states[]` as URL-encoded UI
preference strings like `permMashupChart_widget_...`. The
persisted state is opaque UI-serialized preferences, not a
documented wire format. Authoring one in YAML would produce a
blank, unconfigured widget that the user would then have to
manually configure in the UI on every install - defeating the
framework's purpose. Not worth supporting.

### Geo

**Count.** 1 live / 1 ref. Geographic map widget that plots
resources on a world map by lat/long coordinates. Requires
per-resource `geoLocation` property tags, which in turn requires a
Sustainability pack or a geo-adapter, plus instance-specific tag
data. Non-portable by construction.

### ContainerOverview / ContainerDetails

**Count.** 1 + 1 live. vRealize Network Insight (vRNI) integration
widgets for Application containers. Require the vRNI adapter and
the vRNI application discovery feature. Out of scope.

---

## Recommended implementation order

1. **PropertyList** - 47 live widgets, cheap, reuses MetricSpec
   infrastructure almost verbatim. Highest marginal coverage
   (1,928/2,019 = 95.5% after this alone).
2. **ResourceRelationshipAdvanced** - 34 live widgets, trivial
   config, no metric machinery needed. Adds "topology box" to the
   detail-page dashboard idiom. (96.5%)
3. **SparklineChart** - 4 live / 12 ref widgets. Structurally free
   after PropertyList (reuses the same shared
   `_render_metric_spec` extension), and gives a distinct
   "per-row time series" presentation the existing 10 types
   cannot produce. (97.4%)

**Optional batch 2** - IntSummary family (8 types) + Skittles in
one pass if a user asks for a summary-page dashboard. Would bring
coverage to ~98.4%.

**Do not pursue unless asked** - LogAnalysis (portability
problem), MetricPicker (downstream complications), TagPicker
(same), ScoreboardHealth (redundant with IntSummaryHealth).

**Document as hard limitations** - ResourceRelationship (legacy,
superseded), TopologyGraph (NSX-only), MashupChart (UI-state-only
config), Geo (instance data dependency), ContainerOverview/Details
(vRNI-only).

---

## Tooling brief stub (next hand-off)

**Task.** Add PropertyList widget support to
`vcfops_dashboards/loader.py` and `vcfops_dashboards/render.py`.

**Wire format.** See "PropertyList" section above. The config is
structurally identical to Scoreboard but with three additional
display flags (`visualTheme`, `depth`, `showMetricFullName`) and
always uses `metric.mode = "resourceKind"`. PropertyList is always
interaction-driven (`selfProvider: false`) in all 20 surveyed
samples.

**Loader changes.**

1. Add `PropertyListConfig` dataclass in `loader.py`:

    ```python
    @dataclass
    class PropertyListConfig:
        properties: List[MetricSpec] = field(default_factory=list)
        visual_theme: int = 2
        depth: int = 1
        show_metric_full_name: bool = True
    ```

2. Add `is_string_metric: bool = False` field to `MetricSpec`
   (backwards compatible - existing YAMLs default to numeric).
   `_render_metric_spec` must honour it; update Scoreboard/
   MetricChart call sites (no behavioural change when false).

3. Extend `Widget` dataclass with `property_list_config:
   PropertyListConfig | None = None`.

4. Add `"PropertyList"` to `Dashboard.validate()`'s
   `_supported_types` tuple.

5. Extend `_parse_widget()` (wherever widget-type-specific YAML
   parsing lives) to populate `property_list_config` from the
   YAML `property_list:` block.

**Render changes.**

1. Add `_property_list_widget(w: Widget, kind_index) -> dict` in
   `render.py` modeled on `_scoreboard_widget`. Emits:

    ```python
    {
      "id": w.widget_id,
      "type": "PropertyList",
      "title": w.title,
      "gridsterCoords": {...},
      "collapsed": False,
      "config": {
        "visualTheme": cfg.visual_theme,
        "depth": cfg.depth,
        "refreshInterval": 300,
        "relationshipMode": 0,
        "resInteractionMode": None,
        "resource": [],
        "selfProvider": {"selfProvider": False},
        "showMetricFullName": {"showMetricFullName": cfg.show_metric_full_name},
        "customFilter": {"filter": [], "excludedResources": None, "includedResources": None},
        "title": w.title,
        "metric": {
          "mode": "resourceKind",
          "subMode": "resourceKindAll",
          "resourceMetrics": [],
          "resourceKindMetrics": [_render_metric_spec(p, kind_index) for p in cfg.properties],
        }
      }
    }
    ```

2. Add dispatch branch in `_build_dashboard_obj()`:

    ```python
    elif w.type == "PropertyList":
        widgets_json.append(_property_list_widget(w, kind_index))
    ```

3. Add kind_index contribution block in
   `render_dashboards_bundle_json()`:

    ```python
    elif w.type == "PropertyList" and w.property_list_config:
        for spec in w.property_list_config.properties:
            key = (spec.adapter_kind, spec.resource_kind)
            if key not in kind_index:
                kind_index[key] = len(kind_index)
    ```

**Test harness.**

- Add a fixture YAML under `dashboards/_test/property_list.yaml`
  (or use whatever fixture convention exists) with a PropertyList
  widget referencing 3-4 VM properties.
- Capture the rendered JSON as a golden file and assert
  structural equality (ignoring UUIDs and timestamps) against a
  handcrafted reference built from the sample JSON in the
  PropertyList section above.
- Run `python3 -m vcfops_dashboards validate` and confirm the
  fixture loads and renders without errors.

**Verification on instance.** After implementation:

1. Author a test dashboard that uses a PropertyList widget receiving
   from an existing List view picker.
2. Content-packager rebuild + QA tester install.
3. Open the dashboard in the UI, click a row in the View picker,
   confirm the PropertyList populates with the expected property
   values.

**Follow-up.** Once PropertyList lands and the shared
`is_string_metric` field is in place, ResourceRelationshipAdvanced
and SparklineChart are straightforward copy-forwards of the same
pattern (config-dict builder + kind_index contribution).

---

## Appendix - evidence files (regeneratable)

Survey scripts and sample captures live under `/tmp/dashboard_survey/`
on the machine that ran this scoping:

- `/tmp/dashboard_survey/extracted/` - 131 extracted reference
  dashboard.json files
- `/tmp/dashboard_survey/lab_dash/` - 2 lab-exported dashboards
- `/tmp/dashboard_survey/unsupported_samples.json` - aggregated
  counts + 3 sample widget objects per unsupported type

These are not checked into the repo (tmp-only). To regenerate, run
the extraction loop in this scoping session's bash history or
re-export from the lab via `POST
/suite-api/api/content/operations/export` with `{"scope":"ALL",
"contentTypes":["DASHBOARDS"]}` followed by `GET
/suite-api/api/content/operations/export/zip`. The live survey in
`context/widget_types_survey.md` (dated 2026-04-09) is the
authoritative canonical dataset for widget-type counts.
