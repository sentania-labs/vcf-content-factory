# Chart widget wire formats

Reverse-engineered from 144+ MetricChart, 110 ParetoAnalysis, 65
Scoreboard, 31 HealthChart, 9 Heatmap, 8 SparklineChart, 20
PropertyList, 17 AlertList, and 16 TextDisplay widget specimens
across brockpeterson, tkopton, AriaOperationsContent, and
dalehassinger reference repos (2026-04-09).

## Widget type catalog

| Type string | Count | Self-provider? | Data source | Use case |
|---|---|---|---|---|
| `MetricChart` | 144 | 4 yes, 140 no | `metric.resourceKindMetrics[]` | Time-series line chart. Always line — no bar/area toggle in config. |
| `ParetoAnalysis` | 110 | 46 yes, 64 no | `metric.metricKey` + `resourceKind[]` | Top-N bar chart with ranked resources. |
| `Scoreboard` | 65 | 27 yes, 38 no | `metric.resourceKindMetrics[]` | KPI tiles with optional sparkline. |
| `HealthChart` | 31 | 0 yes, 31 no | `metricKey` + `resourceKindId` | Single-metric health sparkline with red/yellow/orange thresholds. |
| `PropertyList` | 20 | 0 yes, 20 no | `metric.resourceKindMetrics[]` | Key-value property grid (string metrics). |
| `AlertList` | 17 | varies | tag/resource filter | Alert grid filtered by kind/status. |
| `TextDisplay` | 16 | N/A | `editorData` (HTML) | Static HTML text/instructions. |
| `Heatmap` | 9 | 6 yes, 3 no | `configs[].colorBy/sizeBy/groupBy` | Treemap visualization with metric-driven color and size. |
| `SparklineChart` | 8 | 0 yes, 8 no | `metric.resourceKindMetrics[]` | Tabular sparkline rows, one per metric. |
| `ResourceRelationshipAdvanced` | 8 | 0 yes | interaction | Object topology tree (advanced variant). |
| `MetricPicker` | 5 | N/A | interaction | Interactive metric browser, feeds MetricChart. |
| `ResourceRelationship` | 4 | 0 yes | interaction | Object topology graph. |
| `IntSummaryCapacity` | 4 | varies | interaction | Built-in capacity donut/gauge. |
| `IntSummaryTimeRemaining` | 3 | varies | interaction | Built-in time-remaining gauge. |
| `IntSummaryAlertVolume` | 2 | 2 yes | `resource.resourceId` | Built-in alert volume stacked bar. |
| `IntSummaryWorkload` | 1 | 0 yes | interaction | Built-in workload gauge. |
| `ProblemAlertsList` | 1 | 0 yes | interaction | Top problem alerts. |
| `LogAnalysis` | 1 | 0 yes | interaction | Log search/chart. |

## Shared config structure

Every widget (non-TextDisplay) shares these top-level config fields:

```json
{
  "refreshInterval": 300,
  "refreshContent": {"refreshContent": true},
  "selfProvider": {"selfProvider": false},
  "title": "...",
  "resource": [],
  "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
  "depth": 1,
  "relationshipMode": {"relationshipMode": 0}
}
```

**`selfProvider`** — `{selfProvider: true}` means the widget
populates its own data. When false, widget depends on a
`widgetInteractions` `resourceId` event from another widget.

**`resource`** — for self-provider widgets, this either contains
a pinned `resource:id:N_::_` reference (like View widgets) or is
an empty array `[]` (most chart types scope via `resourceKind[]`
instead).

## Interaction types

Only two interaction `type` values exist:
- `resourceId` — passes selected resource identity (the dominant pattern)
- `metricId` — passes selected metric key (MetricPicker → MetricChart only)

### Common interaction patterns

```
View/ResourceList --resourceId--> MetricChart       (116+16 instances)
View             --resourceId--> ParetoAnalysis      (69 instances)
View             --resourceId--> Scoreboard          (32 instances)
View             --resourceId--> HealthChart         (27 instances)
View             --resourceId--> PropertyList        (19 instances)
View             --resourceId--> AlertList           (9 instances)
View             --resourceId--> SparklineChart      (8 instances)
View             --resourceId--> Heatmap             (3 instances)
MetricPicker     --metricId-->   MetricChart         (3 instances)
ParetoAnalysis   --metricId-->   MetricChart         (4 instances)
```

## The metric specification object

MetricChart, Scoreboard, SparklineChart, and PropertyList all use
the same `config.metric` structure:

```json
{
  "mode": "resourceKind",
  "resourceMetrics": [],
  "resourceKindMetrics": [
    {
      "metricKey": "cpu|usage_average",
      "metricName": "CPU|Usage",
      "metricUnitId": "percent",
      "unit": "%",
      "isStringMetric": false,
      "resourceKindId": "resourceKind:id:0_::_",
      "resourceKindName": "Virtual Machine",
      "yellowBound": 90,
      "orangeBound": 95,
      "redBound": 100,
      "colorMethod": 0,
      "handleOldColoring": false,
      "id": "extModel4107-1",
      "label": "",
      "link": "",
      "maxValue": ""
    }
  ],
  "subMode": "resourceKindAll"
}
```

### Fields explained

- **`mode`**: always `"resourceKind"` in all observed specimens.
  `"resourceMetrics"` mode exists conceptually but zero instances
  were found using it.
- **`resourceKindMetrics[]`**: the metric definitions the widget
  displays. Can be empty if the widget is purely interaction-
  driven (MetricPicker → MetricChart pattern).
- **`metricKey`**: the Ops stat key string, e.g. `cpu|usage_average`,
  `virtualDisk:Aggregate of all instances|totalReadLatency_average`,
  `Super Metric|sm_<uuid>`.
- **`metricName`**: display-friendly name.
- **`resourceKindId`**: references `entries.resourceKind[]` via
  `resourceKind:id:N_::_` synthetic id. Tells Ops which resource
  kind this metric belongs to.
- **`colorMethod`**: `0` = custom thresholds (yellow/orange/red
  bounds apply), `1` = no coloring, `2` = dynamic thresholds.
- **`yellowBound`/`orangeBound`/`redBound`**: threshold values
  when `colorMethod` is 0. Null when not applicable.
- **`id`**: unique per-widget internal id (`extModelNNNNN-N`).
  Format: `extModel<arbitrary_number>-<sequence>`. Ops assigns
  internally; any unique string works on import.
- **`label`**: optional display label override (Scoreboard uses
  this to show short names per tile).
- **`link`**: optional URL for click-through. Only seen in
  Scoreboard.
- **`maxValue`**: optional. Rarely used.

## Per-type wire format details

### MetricChart

Time-series line chart. The most common chart widget (144 specimens).

**No `chartType` field exists.** The visualization is always a line
chart. Users can toggle to stacked/area in the UI, but those
preferences live in `states[]` (URL-encoded UI state), not in
`config`. On import, the chart renders as a line chart.

#### Minimum viable config (interaction-driven)

```json
{
  "type": "MetricChart",
  "title": "CPU Usage",
  "config": {
    "refreshInterval": 300,
    "metric": {
      "mode": "resourceKind",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "cpu|usage_average",
          "metricName": "CPU|Usage",
          "metricUnitId": "percent",
          "unit": "%",
          "isStringMetric": false,
          "resourceKindId": "resourceKind:id:0_::_",
          "resourceKindName": "Virtual Machine",
          "yellowBound": null,
          "orangeBound": null,
          "redBound": null,
          "colorMethod": 2,
          "handleOldColoring": false,
          "id": "extModel1-1"
        }
      ],
      "subMode": "resourceKindAll"
    },
    "resource": [],
    "refreshContent": {"refreshContent": true},
    "relationshipMode": {"relationshipMode": 0},
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "selfProvider": {"selfProvider": false},
    "title": "CPU Usage",
    "depth": 1,
    "resInteractionMode": null
  }
}
```

When the widget receives a `resourceId` interaction from a
View/ResourceList, it charts the specified metrics for that
resource over time.

#### Self-provider MetricChart

Same config but `selfProvider: {selfProvider: true}`. The
`resourceKindId` in the metric entries tells Ops which kind to
enumerate. No `resource` pin needed (unlike View widgets). Rarely
used — only 4 of 144 specimens.

### Scoreboard

KPI tiles showing current metric values with color-coded thresholds.

#### Key Scoreboard-specific config fields

| Field | Values | Meaning |
|---|---|---|
| `visualTheme` | 1–9 | Tile styling. 6 = flat modern (most common, 29/65). |
| `mode.layoutMode` | `fixedView`, `fixedSize` | `fixedView` = auto-size tiles (54/65). |
| `showResourceName.showResourceName` | bool | Show resource name on tile. |
| `showMetricName.showMetricName` | bool | Show metric name. |
| `showMetricUnit.showMetricUnit` | bool | Show unit label. |
| `showDT.showDT` | bool | Show data timestamp. |
| `showSparkline.showSparkline` | bool | Embed mini sparkline in tile. |
| `roundDecimals` | int/null | Decimal places for value. |
| `valueSize` | int | Font size for value (px). |
| `labelSize` | int | Font size for label (px). |
| `boxHeight` | int/null | Fixed tile height. |
| `boxColumns` | int | Columns in tile grid. |
| `maxCellCount` | int | Max tiles. |
| `periodLength` | string | `lastWeek`, etc. Only for trend sparkline. |
| `oldMetricValues` | bool | Include stale values. |

#### Minimum viable Scoreboard (interaction-driven)

```json
{
  "type": "Scoreboard",
  "title": "VM KPIs",
  "config": {
    "refreshInterval": 300,
    "metric": {
      "mode": "resourceKind",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "cpu|usage_average",
          "metricName": "CPU|Usage",
          "metricUnitId": "percent",
          "unit": "%",
          "isStringMetric": false,
          "resourceKindId": "resourceKind:id:0_::_",
          "resourceKindName": "Virtual Machine",
          "yellowBound": 80,
          "orangeBound": 90,
          "redBound": 100,
          "colorMethod": 0,
          "handleOldColoring": false,
          "id": "extModel1-1"
        }
      ],
      "subMode": "resourceKindAll"
    },
    "resource": [],
    "refreshContent": {"refreshContent": true},
    "relationshipMode": {"relationshipMode": 0},
    "selfProvider": {"selfProvider": false},
    "title": "VM KPIs",
    "depth": 1,
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "resInteractionMode": null,
    "visualTheme": 6,
    "mode": {"layoutMode": "fixedView"},
    "showResourceName": {"showResourceName": false},
    "showMetricName": {"showMetricName": true},
    "showMetricUnit": {"showMetricUnit": true},
    "showDT": {"showDT": false},
    "showSparkline": {"showSparkline": false},
    "maxCellCount": 100,
    "oldMetricValues": true,
    "roundDecimals": 1,
    "valueSize": 24,
    "labelSize": 16,
    "boxHeight": null,
    "boxColumns": 6
  }
}
```

### ParetoAnalysis (Top-N)

Horizontal bar chart ranking resources by a single metric. Second
most common chart widget (110 specimens).

**Different metric spec from MetricChart/Scoreboard.** Uses
a flat `config.metric` object (not the `resourceKindMetrics[]`
array pattern):

```json
"metric": {
  "metricKey": "cpu|usage_average",
  "name": "CPU|Usage (%)"
}
```

Plus `config.resourceKind[]` to scope which resource kinds to rank:

```json
"resourceKind": [{"id": "resourceKind:id:0_::_"}]
```

#### Key ParetoAnalysis-specific config fields

| Field | Values | Meaning |
|---|---|---|
| `topOption` | `metricsHighestUtilization` (108), `metricsLowestUtilization` (2) | Rank direction. |
| `barsCount` | int (5, 10, 15 common) | Number of bars to show. |
| `regenerationTime` | int (usually 15) | Refresh cycle in minutes. |
| `roundDecimals` | int | Decimal places. |
| `metricName` | string | Display name for metric. |
| `metricUnit` | `{metricUnitId, metricUnitName}` | Unit override. `{-1, "Auto"}` = default. |
| `yellowBound`/`orangeBound`/`redBound` | number | Color thresholds for bars. |
| `additionalColumns[]` | array of `{boxLabel, metricName, metricKey, resourceKindId}` | Extra columns alongside bars. |
| `filterOldMetrics.filterOldMetrics` | bool | Exclude stale data. |
| `percentileValue` | null or number | Percentile mode. |
| `maxValue` | null or number | Scale max. |

#### Minimum viable ParetoAnalysis (self-provider)

```json
{
  "type": "ParetoAnalysis",
  "title": "Hottest VMs (CPU)",
  "config": {
    "refreshInterval": 300,
    "resource": [],
    "refreshContent": {"refreshContent": true},
    "relationshipMode": {"relationshipMode": [-1, 0]},
    "selfProvider": {"selfProvider": true},
    "title": "Hottest VMs (CPU)",
    "mode": "all",
    "filterMode": "tagPicker",
    "tagFilter": null,
    "depth": 10,
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "filterOldMetrics": {"filterOldMetrics": false},
    "topOption": "metricsHighestUtilization",
    "barsCount": 10,
    "roundDecimals": 1,
    "regenerationTime": 15,
    "percentileValue": null,
    "metricName": "CPU Usage",
    "metricUnit": {"metricUnitId": -1, "metricUnitName": "Auto"},
    "additionalColumns": [],
    "metric": {
      "metricKey": "cpu|usage_average",
      "name": "CPU|Usage (%)"
    },
    "resourceKind": [{"id": "resourceKind:id:0_::_"}]
  }
}
```

### HealthChart

Single-metric health sparkline per resource with red/yellow/green
thresholds. Always interaction-driven (0 self-provider specimens).

**Different metric spec from MetricChart.** Uses flat top-level
config fields instead of `metric.resourceKindMetrics[]`:

```json
{
  "metricKey": "cpu|usage_average",
  "metricName": "CPU|Usage",
  "metricFullName": "CPU|Usage (%)",
  "resourceKindId": "resourceKind:id:0_::_",
  "metricUnit": {"metricUnitId": -1, "metricUnitName": "Default Unit"},
  "metricType": {"metricType": "custom"},
  "yellowBound": -2,
  "orangeBound": -1,
  "redBound": 0
}
```

#### Key HealthChart-specific fields

| Field | Values | Meaning |
|---|---|---|
| `metricType.metricType` | `custom` (30), `health` (1) | `custom` = show specific metric. `health` = badge health. |
| `chartHeight` | int (usually 135) | Sparkline height. |
| `sortBy` | `metricValue` | Sort resources by. |
| `sortByDir.orderByDir` | `asc`, `desc` | Sort direction. |
| `paginationNumber` | int (usually 15) | Page size. |
| `showResourceName.showResourceName` | bool | Show resource name. |
| `showMetricLabel.showMetricLabel` | bool | Show metric label. |
| `selectFirstRow.selectFirstRow` | bool | Auto-select first row. |

#### Minimum viable HealthChart (interaction-driven)

```json
{
  "type": "HealthChart",
  "title": "CPU Health (for selected VM)",
  "config": {
    "refreshInterval": 300,
    "resource": [],
    "refreshContent": {"refreshContent": true},
    "relationshipMode": {"relationshipMode": 0},
    "selfProvider": {"selfProvider": false},
    "title": "CPU Health (for selected VM)",
    "mode": "all",
    "filterMode": "tagPicker",
    "tagFilter": null,
    "depth": 1,
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "metricKey": "cpu|usage_average",
    "metricName": "CPU|Usage",
    "metricFullName": "CPU|Usage (%)",
    "resourceKindId": "resourceKind:id:0_::_",
    "metricUnit": {"metricUnitId": -1, "metricUnitName": "Default Unit"},
    "metricType": {"metricType": "custom"},
    "chartHeight": 135,
    "yellowBound": -2,
    "orangeBound": -1,
    "redBound": 0,
    "sortBy": "metricValue",
    "sortByDir": {"orderByDir": "asc"},
    "paginationNumber": 15,
    "showResourceName": {"showResourceName": true},
    "showMetricLabel": {"showMetricLabel": false},
    "metricLabel": "",
    "selectFirstRow": {"selectFirstRow": false}
  }
}
```

### SparklineChart

Tabular sparkline — one row per metric with mini chart and current
value. Always interaction-driven (0 self-provider specimens).

Uses the same `metric.resourceKindMetrics[]` structure as
MetricChart. Additional config:

| Field | Values | Meaning |
|---|---|---|
| `columnSequence.columnSequence` | `graphFirst` | Show sparkline before value. |
| `showResourceName.showObjectName` | bool | Show object name. |
| `showDT.showDT` | bool | Show timestamp. |

#### Minimum viable SparklineChart

```json
{
  "type": "SparklineChart",
  "title": "Disk Performance",
  "config": {
    "refreshInterval": 300,
    "resource": [],
    "refreshContent": {"refreshContent": true},
    "relationshipMode": {"relationshipMode": 0},
    "selfProvider": {"selfProvider": false},
    "title": "Disk Performance",
    "depth": 1,
    "showDT": {"showDT": true},
    "showResourceName": {"showObjectName": false},
    "columnSequence": {"columnSequence": "graphFirst"},
    "metric": {
      "mode": "resourceKind",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "disk|read_average",
          "metricName": "Physical Disk|Read Throughput",
          "metricUnitId": "kbps",
          "unit": "KBps",
          "isStringMetric": false,
          "resourceKindId": "resourceKind:id:0_::_",
          "resourceKindName": "Virtual Machine",
          "yellowBound": null,
          "orangeBound": null,
          "redBound": null,
          "colorMethod": 1,
          "handleOldColoring": false,
          "label": "Read Throughput",
          "id": "extModel1-1"
        }
      ],
      "subMode": "resourceKindAll"
    }
  }
}
```

### Heatmap

Treemap with metric-driven color and sizing, optionally grouped by
parent resource. 6 self-provider, 3 interaction-driven.

**Unique config structure.** Uses `configs[]` array (not
`metric`), each entry defining one heatmap tab:

```json
{
  "configs": [
    {
      "name": "VM CPU Heatmap",
      "resourceKind": "resourceKind:id:2_::_",
      "colorBy": {"metricKey": "cpu|usage_average", "value": "CPU|Usage (%)"},
      "sizeBy": {"metricKey": "config|hardware|num_Cpu", "value": "Number of CPUs"},
      "groupBy": {
        "resourceKind": "ClusterComputeResource",
        "adapterKind": "VMWARE",
        "typeId": "resourceKind:id:1_::_",
        "type": "resourceKind",
        "text": "Cluster Compute Resource",
        "originalText": "Cluster Compute Resource",
        "id": "004null002006VMWAREClusterComputeResource",
        "parentText": "vCenter Adapter",
        "parentId": "VMWARE"
      },
      "thenBy": null,
      "color": {
        "minValue": 0,
        "maxValue": 100,
        "thresholds": {
          "values": [0, 50, 100],
          "colors": ["#8ABF5B", "#EACC58", "#E4695E"]
        }
      },
      "focusOnGroups": true,
      "relationalGrouping": false,
      "solidColoring": false,
      "mode": {"mode": false},
      "attributeKind": {"value": ""},
      "filterMode": "tagPicker",
      "tagFilter": null,
      "customFilter": {"filter": [], "excludedResources": null, "includedResources": null}
    }
  ],
  "value": 0
}
```

**`groupBy.id` format**: `004null<adapterPrefix><adapterKind><resourceKind>`.
The `004null` prefix and the 6-digit adapter prefix (same as
`_ADAPTER_KIND_PREFIX` in the renderer) are fixed.

### TextDisplay

Static HTML content. No data source, no interaction.

```json
{
  "type": "TextDisplay",
  "title": "Instructions",
  "config": {
    "editorData": "<p>HTML content here</p>",
    "locationFile": "",
    "locationUrl": "",
    "refreshContent": {"refreshContent": false},
    "refreshInterval": 300,
    "title": "Instructions",
    "viewModeHTML": true
  }
}
```

### PropertyList

Key-value property display for a selected resource. Uses the same
`metric.resourceKindMetrics[]` structure as MetricChart, but
metrics are typically `isStringMetric: true` (string properties
like version, UUID, parent name).

Additional field: `visualTheme` (int, usually 0).

### AlertList

Alert grid filtered by resource kind, status, and criticality.

Key config: `status` array (`[0]` = active), `state` array,
`alertImpact`, `alertAction`, `criticalityLevel`, `type`,
`alertDefinitions`, `depth`, `mode`.

### IntSummary* widgets

Built-in gauge/donut widgets (`IntSummaryCapacity`,
`IntSummaryTimeRemaining`, `IntSummaryWorkload`,
`IntSummaryAlertVolume`). Minimal config — mostly just
`selfProvider`, `resource`, `refreshInterval`. The visualization
is entirely server-side.

## colorMethod values

| Value | Meaning | Count (across all widget types) |
|---|---|---|
| 0 | Custom thresholds: `yellowBound`/`orangeBound`/`redBound` apply | 150 |
| 1 | No coloring (neutral) | 105 |
| 2 | Dynamic thresholds (Ops auto-computes color) | 216 |

## `entries.resourceKind[]` cross-reference

Chart widgets that reference a `resourceKindId` in their metric
entries or `resourceKind[]` array use the same
`resourceKind:id:N_::_` synthetic id system as View/ResourceList
widgets. The renderer must add these to the dashboard's
`entries.resourceKind[]` table.

For ParetoAnalysis and Heatmap, the `resourceKind` array and
`groupBy.typeId` fields also reference these synthetic ids.

## Implementation recommendations

### Priority order (most useful + simplest config)

1. **TextDisplay** — zero data source, trivial config. Useful for
   dashboard instructions/documentation panels.

2. **MetricChart** — the workhorse. Interaction-driven pattern is
   the common case (116 instances receive from View). Config
   structure is the shared `metric.resourceKindMetrics[]` pattern.
   Self-provider mode is straightforward.

3. **Scoreboard** — KPI tiles. Same `metric` structure as
   MetricChart. Extra visual config fields but no new data patterns.

4. **ParetoAnalysis** — Top-N. Different (simpler) metric spec.
   Self-provider is common. Very useful standalone.

5. **PropertyList** — same `metric` structure as MetricChart but
   for string properties. Useful for detail panels.

6. **SparklineChart** — same `metric` structure, just different
   visual fields.

7. **HealthChart** — different metric spec (flat, not array). Good
   for troubleshooting dashboards.

8. **AlertList** — useful but config is mostly filter-oriented,
   no metric spec.

9. **Heatmap** — unique and complex config structure. Most useful
   for capacity dashboards.

10. **IntSummary\*** — built-in, trivial config, low demand.

### What the renderer needs

For types 1-7, the renderer needs:

1. A new `metric_spec` or similar model to hold
   `resourceKindMetrics[]` entries with metricKey, unit, thresholds,
   colorMethod.
2. Extension of `entries.resourceKind[]` builder to include
   resource kinds referenced by chart widgets' metric entries.
3. Per-type rendering functions analogous to `_view_widget()` and
   `_resource_list_widget()`.
4. For ParetoAnalysis: different metric shape (flat object, not
   array) plus `resourceKind[]` array and `barsCount`/`topOption`.
5. For HealthChart: flat metric fields in config, not
   `metric.resourceKindMetrics[]`.
6. The `id` field in metric entries (`extModelN-N`) can be any
   unique string — the renderer can generate sequentially.

### Self-provider chart widgets do NOT need `entries.resource`

Unlike View widgets, self-provider chart widgets (MetricChart,
ParetoAnalysis, Scoreboard) use `resourceKind[]` references to
scope their data, not a pinned `resource:id:N_::_`. They set
`selfProvider: {selfProvider: true}` and `resource: []` (empty
array). No `entries.resource` entry is needed. This simplifies the
renderer significantly compared to self-provider View widgets.

### Gotchas

1. **`relationshipMode` wrapping varies.** Some widgets use
   `{"relationshipMode": 0}` (int), others use
   `{"relationshipMode": [-1, 0]}` (array). ParetoAnalysis and
   AlertList tend to use the array form. Both work on import.
2. **Scoreboard wraps all booleans.** `showResourceName`,
   `showMetricName`, etc. are all `{fieldName: value}` — never
   bare booleans.
3. **ParetoAnalysis `metric` is flat**, not the
   `{mode, resourceKindMetrics[]}` structure. Just
   `{metricKey, name}`. Easy to confuse.
4. **HealthChart `metricType`** — use `"custom"` for specific
   metrics, `"health"` for badge health. 30/31 specimens use
   `"custom"`.
5. **Heatmap `groupBy.id`** format is
   `004null<6-digit-prefix><adapterKind><resourceKind>`. The
   prefix is the same `_ADAPTER_KIND_PREFIX` value used elsewhere.
