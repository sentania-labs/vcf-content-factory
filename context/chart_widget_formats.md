# Chart widget wire formats

Reverse-engineered from live instance export (2,019 widgets across
231 dashboards) plus reference repos (brockpeterson, tkopton,
AriaOperationsContent, dalehassinger). Updated 2026-04-09 with
live-instance validation of all field frequencies and cross-reference
patterns.

## Widget type catalog

| Type string | Live count | Self-provider? | Data source | Use case |
|---|---|---|---|---|
| `View` | 1,063 | varies | viewDefinitionId | List view (supported in renderer v1) |
| `Scoreboard` | 245 | 54 yes, 191 no | `metric.resourceKindMetrics[]` | KPI tiles with optional sparkline |
| `HealthChart` | 132 | 29 yes, 103 no | flat `metricKey` + `resourceKindId` | Single-metric health bars with thresholds |
| `TextDisplay` | 106 | N/A | `editorData` (HTML) or `locationUrl` | Static HTML text/instructions |
| `MetricChart` | 82 | 30 yes, 50 no | `metric.resourceKindMetrics[]` | Time-series line chart |
| `ResourceList` | 75 | varies | resourceKind | Resource list (supported in renderer v1) |
| `Heatmap` | 70 | 24 yes, 41 no | `configs[].colorBy/sizeBy/groupBy` | Treemap visualization |
| `ParetoAnalysis` | 65 | 36 yes, 29 no | flat `metric` or `metricOption` | Top-N bar chart |
| `PropertyList` | 47 | 18 yes, 29 no | `metric.resourceKindMetrics[]` | Key-value property/metric grid |
| `ResourceRelationshipAdvanced` | 34 | 7 yes, 26 no | `traversalSpecId` | Object topology tree |
| `AlertList` | 24 | 0 yes, 22 no | type/status/criticality filters | Alert grid |
| `ProblemAlertsList` | 19 | 12 yes, 7 no | `impactedBadge` + `triggeredObject` | Top problem alerts |
| `LogAnalysis` | 14 | varies | `liQueryId` | Log search/chart |
| `ResourceRelationship` | 6 | 0 yes | interaction | Object topology graph (older) |
| `MetricPicker` | 5 | N/A | interaction | Interactive metric browser |
| `Skittles` | 4 | 2 yes, 2 no | `badge[]` + `custom[]` | Badge summary grid |
| `TopologyGraph` | 4 | varies | NSX traversal | NSX network topology |
| `SparklineChart` | 4 | 0 yes, 4 no | `metric.resourceKindMetrics[]` | Tabular sparkline rows |
| `IntSummaryHealth` | 3 | 3 yes | `resource` | Health gauge |
| `IntSummaryStress` | 3 | 0 yes, 3 no | `resource` | Stress gauge |
| `IntSummaryCapacity` | 3 | 0 yes, 3 no | `resource` | Capacity donut |
| `IntSummaryRisk` | 2 | 2 yes | `resource` | Risk gauge |
| `IntSummaryEfficiency` | 2 | 2 yes | `resource` | Efficiency gauge |
| `Geo` | 1 | varies | tag/filter | Geographic map |
| `IntSummaryAlertVolume` | 1 | 1 yes | `resource` | Alert volume bar |
| `ScoreboardHealth` | 1 | 0 yes, 1 no | `metricType` | Single health badge icon |
| `TagPicker` | 1 | N/A | interaction | Tag filter picker |
| `MashupChart` | 1 | 0 yes, 1 no | interaction | Object health timeline |
| `ContainerOverview` | 1 | varies | vRNI | Container overview (not relevant) |
| `ContainerDetails` | 1 | varies | vRNI | Container details (not relevant) |

## Top-level widget envelope (all types)

Every widget in `dashboard.dashboards[*].widgets[]`:

```json
{
  "id": "<uuid>",
  "type": "<TypeString>",
  "title": "Widget Title",
  "collapsed": false,
  "height": 324,
  "gridsterCoords": { "x": 1, "y": 0, "w": 4, "h": 6 },
  "config": { ... },
  "states": [ ... ]
}
```

`states` is optional. Encodes user UI preferences (URL-encoded
key/value pairs). Not required for import. `height` is optional
(Ops computes from `gridsterCoords.h`).

## Shared config fields

Every widget (non-TextDisplay) shares these fields. All are present
in 95%+ of specimens:

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

### `selfProvider`

`{selfProvider: true}` = widget fetches its own data (pinned to a
resource or resource kind). `{selfProvider: false}` = widget
receives its subject via a `widgetInteractions[]` entry from
another widget.

### `resource`

For self-provider widgets in `mode: "resource"`, this contains a
pinned `[{name: "...", id: "resource:id:N_::_"}]`. For
self-provider widgets in `mode: "all"` or `mode: "metric"`, this
is an empty array `[]`. The `resource:id:N_::_` references
`entries.resource[]` by internalId.

### `resInteractionMode`

Usually `null`. Non-null values observed are XML filenames or
dashboard names that link to built-in content-pack navigation.
Not relevant for custom content authoring.

## Interaction types

Only two `widgetInteractions[].type` values exist:
- `resourceId` -- passes selected resource identity (dominant)
- `metricId` -- passes selected metric key (MetricPicker only)

### Common interaction patterns

```
View/ResourceList --resourceId--> MetricChart       (116+16 instances)
View             --resourceId--> Scoreboard          (32 instances)
View             --resourceId--> HealthChart         (27 instances)
View             --resourceId--> ParetoAnalysis      (29 instances)
View             --resourceId--> PropertyList        (19 instances)
View             --resourceId--> AlertList           (9 instances)
View             --resourceId--> SparklineChart      (4 instances)
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

### `metric.mode` values

| Value | Meaning | Live count |
|---|---|---|
| `resourceKind` | Metric defined by resource kind (widget scopes via entries) | 90%+ |
| `resource` | Metric pinned to a specific named resource | rare (3 MetricChart, 1 Scoreboard, 3 PropertyList) |

When `mode: "resource"`, the `resourceMetrics[]` array is populated
instead of `resourceKindMetrics[]`. Each entry adds:
- `resourceId`: `"resource:id:N_::_"` (references `entries.resource[]`)
- `resourceName`: display name of the pinned resource
- `resourceKindId`: full adapter-prefixed kind ID (e.g.
  `"002006VMWAREVirtualMachine"`, NOT the `resourceKind:id:N_::_`
  form)

### `metric.subMode`

Always `"resourceKindAll"` when present (225/245 Scoreboards). Some
widgets omit it entirely (20/245). Safe to always include.

### Fields in `resourceKindMetrics[]` entries

| Field | Required | Notes |
|---|---|---|
| `metricKey` | yes | Ops stat key, e.g. `cpu\|usage_average`, `Super Metric\|sm_<uuid>` |
| `metricName` | yes | Display name |
| `resourceKindId` | yes | `resourceKind:id:N_::_` -- MUST exist in `entries.resourceKind[]` |
| `resourceKindName` | no | Display name of resource kind (informational) |
| `metricUnitId` | no | Unit ID string (e.g. `"percent"`, `"kbps"`, `"currencymonth"`). Null = auto. |
| `unit` | no | Display unit string (e.g. `"%"`, `"KBps"`). Null = auto. |
| `isStringMetric` | no | `true` for string properties (PropertyList). Default false. |
| `colorMethod` | yes | 0=custom thresholds, 1=no color, 2=dynamic thresholds |
| `yellowBound` | no | Threshold when colorMethod=0. Null otherwise. |
| `orangeBound` | no | Threshold when colorMethod=0. Null otherwise. |
| `redBound` | no | Threshold when colorMethod=0. Null otherwise. |
| `handleOldColoring` | no | Always false in all specimens. Safe to omit or set false. |
| `id` | yes | Unique per-widget: `extModel<N>-<seq>`. Any unique string works on import. |
| `label` | no | Display label override. Scoreboard uses for short tile names. |
| `link` | no | URL for click-through. Only observed in Scoreboard. |
| `maxValue` | no | Scale maximum. Rarely used. |

## Per-type wire format details

---

### TextDisplay

Static HTML content. No data source, no interaction, no
`selfProvider`. The simplest widget type.

**Live count:** 106 widgets across 55 dashboards.

Two content modes:
1. **`editorData` mode** (18 specimens): inline HTML in the `editorData` field
2. **`locationUrl` mode** (54 specimens): reference to a content-pack HTML page
3. **Placeholder** (31 specimens): `editorData: "<br>"` with empty `locationUrl`

For custom content authoring, only `editorData` mode is relevant.

#### Config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `title` | 106/106 | yes | Widget title |
| `locationFile` | 106/106 | yes | Always `""`. Must be present. |
| `locationUrl` | 106/106 | yes | URL to content-pack page, or `""` for inline HTML |
| `editorData` | 79/106 | yes | HTML content. Set to `"<br>"` or `""` when using locationUrl |
| `viewModeHTML` | 106/106 | yes | Always `true` |
| `refreshInterval` | 106/106 | yes | Usually 300 |
| `refreshContent` | 106/106 | yes | `{"refreshContent": false}` |
| `titleLocalized` | 57/106 | no | Localized title string. Can omit. |

#### Minimum viable TextDisplay

```json
{
  "type": "TextDisplay",
  "title": "Section Header",
  "config": {
    "editorData": "<h2>Cluster Overview</h2><p>Select a cluster from the list.</p>",
    "locationFile": "",
    "locationUrl": "",
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": false},
    "title": "Section Header",
    "viewModeHTML": true
  }
}
```

**Gotcha:** `locationFile` and `locationUrl` must be present as
empty strings even when using `editorData`. Omitting them may
cause rendering issues.

---

### MetricChart

Time-series line chart. Default rendering is line with area fill.
No `chartType` field exists -- chart style (line/bar/stacked) is
controlled entirely by `states[]` UI preferences, not importable
config.

**Live count:** 82 widgets across 34 dashboards.

#### Config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `metric` | 73/82 | yes* | Standard metric spec object. *9 widgets omit it (empty metrics, MetricPicker-driven). |
| `refreshInterval` | 80/82 | yes | Usually 300 |
| `refreshContent` | 80/82 | yes | `{"refreshContent": true}` |
| `selfProvider` | 80/82 | yes | `{"selfProvider": false}` or `true` |
| `title` | 80/82 | yes | Widget title |
| `resInteractionMode` | 80/82 | no | Usually `null` |
| `relationshipMode` | 73/82 | yes | `{"relationshipMode": 0}` (most common) or `{"relationshipMode": -1}` |
| `depth` | 67/82 | yes | Usually 1 |
| `resource` | 67/82 | yes | `[]` for interaction-driven or resourceKind mode |
| `customFilter` | 67/82 | yes | Standard filter object |

**`relationshipMode` values observed:** `{"relationshipMode": 0}`
(57), `{"relationshipMode": -1}` (9), bare `0` (6),
`{"relationshipMode": [-1, 0]}` (1). All work on import.

#### Self-provider patterns

1. **`mode: "resourceKind"` with `selfProvider: true`** (common,
   ~27 specimens): widget charts metrics for all resources of the
   specified kind. `resource: []`, no pin needed.

2. **`mode: "resource"` with `selfProvider: true`** (rare, 3
   specimens): widget pinned to a specific resource via
   `metric.resourceMetrics[].resourceId` referencing
   `entries.resource[]`. Note: `resourceKindId` in
   `resourceMetrics[]` uses the full adapter-prefixed form
   (e.g. `"002016FederatedAdapterFederationWorld"`), NOT the
   `resourceKind:id:N_::_` form.

3. **Empty metrics** (9 specimens): MetricPicker-driven charts.
   Widget config has empty `resourceKindMetrics[]` and
   `resourceMetrics[]`. Receives metric identity via `metricId`
   interaction.

#### Minimum viable MetricChart (interaction-driven, resourceKind mode)

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

#### Self-provider MetricChart (resourceKind mode)

Same config but `selfProvider: {"selfProvider": true}`. No
`resource` pin needed. The `resourceKindId` in metric entries
tells Ops which kind to enumerate.

---

### Scoreboard

KPI tiles showing current metric values with color-coded
thresholds. Most common non-View widget type.

**Live count:** 245 widgets across 89 dashboards.

#### Config fields

All fields below appear in 245/245 specimens unless noted:

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `metric` | 245/245 | yes | Standard metric spec object |
| `visualTheme` | 245/245 | yes | 1-9. Theme 8 most common (141/245). |
| `mode` | 245/245 | yes | `{"layoutMode": "fixedView"}` (213) or `{"layoutMode": "fixedSize"}` (32) |
| `showResourceName` | 245/245 | yes | `{"showResourceName": true/false}` |
| `showMetricName` | 245/245 | yes | `{"showMetricName": true/false}` |
| `showMetricUnit` | 245/245 | yes | `{"showMetricUnit": true/false}` |
| `showSparkline` | 245/245 | yes | `{"showSparkline": true/false}` |
| `valueSize` | 245/245 | yes | Font size px. 24 (206), 14 (25), others rare. |
| `labelSize` | 245/245 | yes | Font size px. Usually 12 or 16. |
| `boxHeight` | 245/245 | yes | Fixed tile height or `null` for auto. |
| `boxColumns` | 245/245 | yes | Columns in tile grid. 1-10 observed. |
| `roundDecimals` | 245/245 | yes | Decimal places or `null` for auto. |
| `periodLength` | 245/245 | yes | Sparkline period: `null`, `"dashboardTime"`, `"last24Hour"`, `"last7Days"`, `"last30Days"`, `"last90Days"` |
| `selfProvider` | 245/245 | yes | `{"selfProvider": true/false}` |
| `refreshInterval` | 245/245 | yes | Usually 300 |
| `refreshContent` | 245/245 | yes | `{"refreshContent": true/false}` |
| `resInteractionMode` | 245/245 | no | Usually `null` |
| `showDT` | 234/245 | yes | `{"showDT": true/false}` -- show data timestamp |
| `maxCellCount` | 238/245 | yes | Max tiles. Usually 100. |
| `oldMetricValues` | 231/245 | yes | Include stale values. Bool. |
| `relationshipMode` | 238/245 | yes | `{"relationshipMode": 0}` |
| `customFilter` | 231/245 | yes | Standard filter object |
| `resource` | 231/245 | yes | `[]` for resourceKind mode |
| `depth` | 231/245 | yes | Usually 1 |

#### `visualTheme` values

| Theme | Count | Description |
|---|---|---|
| 8 | 141 | Most common. Modern flat tiles (dark text on colored bg). |
| 4 | 52 | Older colored tile style. |
| 5 | 22 | Compact modern style. |
| 6 | 11 | Flat modern (light bg). |
| 7 | 11 | Rounded tile style. |
| 9 | 3 | Minimal outline style. |
| 3 | 2 | Classic large-number style. |
| 2 | 2 | Badge-like style. |
| 1 | 1 | Original basic style. |

**Correction from prior docs:** themes go to 9, not 6. Theme 8
is the most popular, not theme 6.

#### `periodLength` and `showSparkline` correlation

When `showSparkline: true`, `periodLength` controls the sparkline
time range. Most common combo: `showSparkline: true` +
`periodLength: "dashboardTime"` (102 specimens). When sparkline
is off, `periodLength` is typically `null`.

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
    "visualTheme": 8,
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
    "labelSize": 12,
    "boxHeight": null,
    "boxColumns": 4,
    "periodLength": null
  }
}
```

---

### ParetoAnalysis (Top-N)

Horizontal bar chart ranking resources by a single metric. Two
distinct config shapes exist.

**Live count:** 65 widgets across 25 dashboards.

#### Two config shapes

**Shape 1: flat `metric` + `resourceKind[]`** (53 specimens,
modes `all` and `resource`)

```json
"metric": {"metricKey": "cpu|usage_average", "name": "CPU|Usage (%)"},
"resourceKind": [{"id": "resourceKind:id:0_::_"}],
"topOption": "metricsHighestUtilization",
"mode": "all"
```

**Shape 2: `metricOption` + `tagOption`** (12 specimens, mode
`metric`)

```json
"metricOption": {
  "tagFilter": null,
  "metricInfo": {
    "path": ["/source/GROUP_OnlineCapacityAnalytics/OnlineCapacityAnalytics|capacityRemainingPercentage"],
    "value": "OnlineCapacityAnalytics|capacityRemainingPercentage"
  },
  "resourceKindId": ["resourceKind:id:0_::_"],
  "value": {"metricOption": "metricsLowestUtilization"}
},
"tagOption": {
  "tagFilter": null,
  "value": {"tagOption": "leastHealthyApplications"}
},
"mode": "metric"
```

**Correlation:** `mode: "all"` or `mode: "resource"` uses Shape 1.
`mode: "metric"` uses Shape 2. The two shapes are mutually
exclusive (0 specimens have both).

#### `mode` values

| Value | Count | Shape | Meaning |
|---|---|---|---|
| `all` | 33 | 1 | All resources of the kind |
| `resource` | 20 | 1 | Descendants of a pinned resource |
| `metric` | 12 | 2 | Uses metricOption/tagOption selectors |

When `mode: "resource"`, `config.resource[]` contains a pinned
`[{name: "...", id: "resource:id:N_::_"}]` entry.

#### Config fields (Shape 1 -- recommended for authoring)

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `metric` | 53/53 | yes | `{metricKey: "...", name: "..."}` -- flat, NOT the array pattern |
| `resourceKind` | 53/53 | yes | `[{id: "resourceKind:id:N_::_"}]` |
| `topOption` | 53/53 | yes | `"metricsHighestUtilization"` or `"metricsLowestUtilization"` |
| `barsCount` | 65/65 | yes | 5, 10, 15 common |
| `regenerationTime` | 65/65 | yes | Refresh cycle minutes. Usually 15. |
| `mode` | 65/65 | yes | `"all"` for resourceKind scope, `"resource"` for pinned |
| `filterMode` | 65/65 | yes | `"tagPicker"` or `"tagFilter"` |
| `depth` | 65/65 | yes | Usually 10 |
| `selfProvider` | 65/65 | yes | `{"selfProvider": true/false}` |
| `filterOldMetrics` | 65/65 | yes | `{"filterOldMetrics": false}` |
| `refreshInterval` | 65/65 | yes | Usually 300 |
| `refreshContent` | 65/65 | yes | `{"refreshContent": true/false}` |
| `additionalColumns` | 62/65 | yes | Array of extra metric columns (see below). `[]` if none. |
| `roundDecimals` | 62/65 | yes | Decimal places. Usually 1. |
| `metricName` | 52/65 | no | Display name for metric |
| `metricUnit` | 52/65 | no | `{"metricUnitId": -1, "metricUnitName": "Auto"}` |
| `relationshipMode` | 53/65 | yes | `{"relationshipMode": [-1, 0]}` (array form common) |
| `tagFilter` | 53/65 | yes | `null` |
| `customFilter` | 53/65 | yes | Standard filter object |
| `percentileValue` | 53/65 | no | `null` or number |
| `resource` | 53/65 | yes | `[]` or pinned resource for mode=resource |
| `yellowBound`/`orangeBound`/`redBound` | 35/65 | no | Threshold values |
| `maxValue` | 39/65 | no | Scale max. Usually `null`. |
| `periodLength` | 5/65 | no | Usually absent |

#### `additionalColumns[]` format

Extra columns shown alongside the primary metric bars:

```json
[
  {
    "boxLabel": "Hosts",
    "metricName": "Summary|Total Number of Hosts",
    "metricKey": "summary|total_number_hosts",
    "resourceKindId": "resourceKind:id:0_::_",
    "boxLabelOrig": "Hosts",
    "boxLabelLocalized": "Hosts"
  }
]
```

`boxLabelOrig` and `boxLabelLocalized` are optional display fields.

#### Minimum viable ParetoAnalysis (self-provider, Shape 1)

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

---

### HealthChart

Single-metric health bars per resource with red/yellow/green
thresholds. Different metric spec from MetricChart (flat fields,
not `metric.resourceKindMetrics[]` array).

**Live count:** 132 widgets across 37 dashboards.

**Correction from prior docs:** 29 self-provider specimens exist
on live instance (prior reference-repo analysis found 0).

#### Config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `metricKey` | 127/132 | yes* | Ops stat key. *5 widgets use `metricType: "health"` instead. |
| `metricName` | 132/132 | yes | Display name |
| `metricFullName` | 124/132 | yes | Full display name with unit |
| `resourceKindId` | 127/132 | yes | `resourceKind:id:N_::_` |
| `metricUnit` | 129/132 | yes | `{"metricUnitId": -1, "metricUnitName": "Default Unit"}` |
| `metricType` | 132/132 | yes | `{"metricType": "custom"}` (127) or `{"metricType": "health"}` (5) |
| `chartHeight` | 129/132 | yes | Sparkline height px. 135 (97), 190 (27). |
| `sortBy` | 132/132 | yes | Always `"metricValue"` |
| `sortByDir` | 132/132 | yes | `{"orderByDir": "asc"}` or `{"orderByDir": "desc"}` |
| `paginationNumber` | 132/132 | yes | Page size. Usually 15. |
| `showResourceName` | 129/132 | yes | `{"showResourceName": true/false}` |
| `showMetricLabel` | 129/132 | yes | `{"showMetricLabel": true/false}` |
| `metricLabel` | 129/132 | no | Custom label string. Usually `""`. |
| `selectFirstRow` | 130/132 | yes | `{"selectFirstRow": true/false}` |
| `mode` | 132/132 | yes | `"all"` (103), `"resource"` (25), `"self"` (2) |
| `filterMode` | 128/132 | yes | `"tagPicker"` |
| `tagFilter` | 132/132 | yes | `null` |
| `yellowBound` | 120/132 | yes | Threshold value (positive). -2 for DT thresholds. |
| `orangeBound` | 120/132 | yes | Threshold value |
| `redBound` | 120/132 | yes | Threshold value |
| `selfProvider` | 132/132 | yes | `{"selfProvider": true/false}` |
| `refreshInterval` | 132/132 | yes | Usually 300 |
| `refreshContent` | 132/132 | yes | `{"refreshContent": false}` |
| `customFilter` | 128/132 | yes | Standard filter object |
| `resource` | 128/132 | yes | `[]` or pinned resource |
| `depth` | 128/132 | yes | Usually 1 |
| `relationshipMode` | 128/132 | yes | `{"relationshipMode": 0}` |
| `periodLength` | 3/132 | no | Rarely used |

#### `mode` values

| Value | Count | Meaning |
|---|---|---|
| `all` | 103 | All resources at depth (interaction-driven) |
| `resource` | 25 | Descendants of a pinned resource (self-provider) |
| `self` or `{"mode": "self"}` | 4 | Show metric for the selected resource only |

When `mode: "resource"` with `selfProvider: true`, the
`config.resource[]` contains a pinned
`[{name: "...", id: "resource:id:N_::_"}]`.

#### Minimum viable HealthChart (interaction-driven)

```json
{
  "type": "HealthChart",
  "title": "CPU Health",
  "config": {
    "refreshInterval": 300,
    "resource": [],
    "refreshContent": {"refreshContent": false},
    "relationshipMode": {"relationshipMode": 0},
    "selfProvider": {"selfProvider": false},
    "title": "CPU Health",
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
    "yellowBound": 70,
    "orangeBound": 80,
    "redBound": 90,
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

---

### SparklineChart

Tabular sparkline -- one row per metric with mini chart and current
value. Always interaction-driven on live instance (0 self-provider).

**Live count:** 4 widgets across 3 dashboards.

Uses the same `metric.resourceKindMetrics[]` structure as
MetricChart.

#### SparklineChart-specific config fields

| Field | Values | Required | Notes |
|---|---|---|---|
| `columnSequence` | `{"columnSequence": "graphFirst"}` | yes | Show sparkline before value |
| `showResourceName` | `{"showObjectName": true/false}` | yes | Note: key is `showObjectName`, not `showResourceName` |
| `showDT` | `{"showDT": true/false}` | yes | Show timestamp |

#### `customFilter.filter[]` for SparklineChart

SparklineChart supports property-value filtering to narrow the
resource scope. Example from live instance:

```json
"customFilter": {
  "filter": [
    {
      "resourceKind": "002006VMWAREVirtualMachine",
      "filterTypes": [
        {
          "condition": "EQUALS",
          "metricKey": "summary|config|productName",
          "metricValue": {"isStringMetric": true, "value": "SDDC-Manager"},
          "filterType": "properties"
        }
      ]
    }
  ]
}
```

Note: `resourceKind` in the filter uses the full adapter-prefixed
form (`002006VMWAREVirtualMachine`), not `resourceKind:id:N_::_`.

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

---

### Heatmap

Treemap visualization with metric-driven color and sizing,
optionally grouped by parent resource kind. Supports multiple
tabs via `configs[]` array.

**Live count:** 70 widgets across 38 dashboards.

#### Config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `configs` | 70/70 | yes | Array of tab definitions (see below) |
| `value` | 70/70 | yes | Selected tab index. Usually 0. |
| `title` | 70/70 | yes | Widget title |
| `refreshInterval` | 70/70 | yes | Usually 300 |
| `refreshContent` | 70/70 | yes | `{"refreshContent": false}` |
| `mode` | 65/70 | yes | `"all"` |
| `depth` | 65/70 | yes | Usually 10 |
| `resource` | 65/70 | yes | `[]` |
| `relationshipMode` | 65/70 | yes | `{"relationshipMode": [1, -1, 0]}` (array form) |
| `selfProvider` | 65/70 | yes | `{"selfProvider": true/false}` |

#### `configs[]` tab definition

Each entry in `configs[]` defines one heatmap view:

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Tab name |
| `resourceKind` | yes | `"resourceKind:id:N_::_"` -- subject resource kind |
| `colorBy` | yes | `{"metricKey": "...", "value": "Display Name"}` |
| `sizeBy` | yes | Same shape as colorBy, or `{"metricKey": null, "value": ""}` for uniform |
| `groupBy` | yes | Resource kind grouping (see below) |
| `color` | yes | Threshold colors (see below) |
| `focusOnGroups` | yes | `true` or `false` |
| `relationalGrouping` | yes | `false` |
| `solidColoring` | yes | `true` = flat colors, `false` = gradient |
| `mode` | yes | `{"mode": false}` |
| `attributeKind` | yes | `{"value": ""}` |
| `filterMode` | yes | `"tagPicker"` |
| `tagFilter` | no | `null` |
| `thenBy` | no | `null` |
| `customFilter` | yes | Standard filter object |

#### `groupBy` object

```json
{
  "resourceKind": "ClusterComputeResource",
  "adapterKind": "VMWARE",
  "typeId": "resourceKind:id:N_::_",
  "type": "resourceKind",
  "text": "Cluster Compute Resource",
  "originalText": "Cluster Compute Resource",
  "id": "004null002006VMWAREClusterComputeResource",
  "parentText": "vCenter Adapter",
  "parentId": "VMWARE"
}
```

**`groupBy.id` format:** `004null<adapterPrefix><adapterKind><resourceKind>`.
The `004null` prefix is fixed. The 6-digit adapter prefix is the
same `_ADAPTER_KIND_PREFIX` value used in other renderer code
(e.g. `002006` for VMWARE).

**`groupBy.typeId`** uses `resourceKind:id:N_::_` form and MUST
exist in `entries.resourceKind[]`.

#### `color` threshold object

```json
{
  "minValue": 0,
  "maxValue": 100,
  "thresholds": {
    "values": [0, 50, 100],
    "colors": ["#8ABF5B", "#EACC58", "#E4695E"]
  }
}
```

Color count distribution: 3 colors (59), 5 colors (18), 6 colors
(10), 4 colors (7). The `colors` array should have one more
element than `values` when using ranges, OR the same count for
exact boundaries.

#### Tabs per widget

54/70 have 1 tab. Up to 4 tabs observed (3 specimens).

#### Minimum viable Heatmap (self-provider, single tab)

```json
{
  "type": "Heatmap",
  "title": "VM CPU Heatmap",
  "config": {
    "mode": "all",
    "depth": 10,
    "selfProvider": {"selfProvider": true},
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": false},
    "resource": [],
    "relationshipMode": {"relationshipMode": [1, -1, 0]},
    "title": "VM CPU Heatmap",
    "configs": [
      {
        "name": "CPU Usage",
        "resourceKind": "resourceKind:id:0_::_",
        "colorBy": {"metricKey": "cpu|usage_average", "value": "CPU|Usage (%)"},
        "sizeBy": {"metricKey": null, "value": ""},
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
            "colors": ["#74B43B", "#ECC33E", "#DE3F30"]
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
}
```

---

### PropertyList

Key-value property/metric display for a selected resource.
Uses the same `metric.resourceKindMetrics[]` structure as
MetricChart, but metrics are often `isStringMetric: true`.

**Live count:** 47 widgets across 23 dashboards.

#### PropertyList-specific config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `visualTheme` | 44/47 | yes | 0 (10) or 2 (34). Theme 2 = modern. |
| `showMetricFullName` | 44/47 | no | `{"metricFullName": true/false}` |
| `resInteractionMode` | 47/47 | no | Usually `null` |

Uses standard `metric`, `selfProvider`, `resource`, `depth`,
`refreshInterval`, `refreshContent`, `relationshipMode`,
`customFilter` fields.

#### isStringMetric distribution

194 string metrics vs 139 numeric metrics across all PropertyList
widgets. PropertyList is the primary widget for displaying string
properties (VM names, versions, UUIDs, parent names).

#### Minimum viable PropertyList

```json
{
  "type": "PropertyList",
  "title": "VM Properties",
  "config": {
    "visualTheme": 2,
    "depth": 1,
    "metric": {
      "mode": "resourceKind",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "summary|config|name",
          "metricName": "Summary|Configuration|Name",
          "isStringMetric": true,
          "resourceKindId": "resourceKind:id:0_::_",
          "resourceKindName": "Virtual Machine",
          "colorMethod": 1,
          "id": "extModel1-1"
        }
      ],
      "subMode": "resourceKindAll"
    },
    "resource": [],
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": false},
    "relationshipMode": {"relationshipMode": 0},
    "selfProvider": {"selfProvider": false},
    "title": "VM Properties",
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "showMetricFullName": {"metricFullName": false},
    "resInteractionMode": null
  }
}
```

---

### AlertList

Alert grid filtered by type, criticality, status, and impact.
Always interaction-driven on live instance.

**Live count:** 24 widgets across 18 dashboards.

#### Config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `type` | 23/24 | yes | Array of alert type codes (see below) |
| `criticalityLevel` | 23/24 | yes | Array of ints: 2=Warning, 3=Major, 4=Critical |
| `status` | 23/24 | yes | Array of ints. `[]` = all. `[0]` = active only. |
| `state` | 23/24 | yes | Array. Usually `[]`. |
| `alertImpact` | 23/24 | yes | Array. `[]` = all. `["health"]`, etc. |
| `alertAction` | 23/24 | yes | Array. Usually `[]`. |
| `mode` | 23/24 | yes | `"all"` |
| `filterMode` | 22/24 | yes | `"tagPicker"` |
| `tagFilter` | 24/24 | yes | Usually `null` |
| `depth` | 22/24 | yes | Usually 1 |
| `selfProvider` | 22/24 | yes | `{"selfProvider": false}` |
| `resource` | 22/24 | yes | `[]` |
| `refreshInterval` | 23/24 | yes | 300 |
| `refreshContent` | 23/24 | yes | `{"refreshContent": false}` |
| `relationshipMode` | 22/24 | yes | `{"relationshipMode": [-1, 0]}` (array form) |
| `customFilter` | 21/24 | yes | Standard filter object |
| `alertDefinitions` | 8/24 | no | Array of specific alert definition IDs to filter by |

#### Alert type codes

Format: `"<category>_<subtype>"`. Common codes:

| Code prefix | Meaning |
|---|---|
| 15 | Application |
| 16 | Virtualization/Hypervisor |
| 17 | Hardware/Physical |
| 18 | Storage |
| 19 | Network |
| 20 | Other |

| Code suffix | Meaning |
|---|---|
| 18 | Availability |
| 19 | Performance |
| 20 | Capacity |
| 21 | Compliance |
| 22 | Configuration |

Most common pattern: `["15_19", "16_19", "17_19", "18_19", "19_19"]`
= all categories, performance subtype only.

#### Minimum viable AlertList

```json
{
  "type": "AlertList",
  "title": "Active Alerts",
  "config": {
    "refreshInterval": 300,
    "resource": [],
    "refreshContent": {"refreshContent": false},
    "relationshipMode": {"relationshipMode": [-1, 0]},
    "selfProvider": {"selfProvider": false},
    "title": "Active Alerts",
    "mode": "all",
    "filterMode": "tagPicker",
    "tagFilter": null,
    "depth": 1,
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "criticalityLevel": [2, 3, 4],
    "type": ["15_19", "16_19", "17_19", "18_19", "19_19"],
    "status": [],
    "state": [],
    "alertImpact": [],
    "alertAction": []
  }
}
```

---

### ProblemAlertsList

Top problem alerts impacting a badge (health/risk/efficiency)
for the selected resource or its descendants.

**Live count:** 19 widgets across 9 dashboards.

#### Config fields

| Field | Frequency | Required | Notes |
|---|---|---|---|
| `impactedBadge` | 19/19 | yes | `"health"`, `"risk"`, `"efficiency"`, or `""` (all) |
| `triggeredObject` | varies | yes | `{"triggeredObject": "children"}` or `{"triggeredObject": "self"}` |
| `resource` | varies | yes | `{"resourceId": "resource:id:N_::_", "resourceName": "..."}` for self-provider |
| `selfProvider` | 19/19 | yes | `{"selfProvider": true/false}` |
| `refreshInterval` | 19/19 | yes | 300 |
| `refreshContent` | 19/19 | yes | `{"refreshContent": true}` |
| `title` | varies | no | Widget title |
| `topIssuesDisplayLimit` | 7/19 | no | Max alerts to show. 5 observed. |
| `relationshipMode` | varies | no | Present on some |

#### Minimum viable ProblemAlertsList (self-provider)

```json
{
  "type": "ProblemAlertsList",
  "title": "Top Health Alerts",
  "config": {
    "impactedBadge": "health",
    "triggeredObject": {"triggeredObject": "children"},
    "resource": {"resourceId": "resource:id:0_::_", "resourceName": "vSphere World"},
    "selfProvider": {"selfProvider": true},
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": true},
    "title": "Top Health Alerts"
  }
}
```

---

### IntSummary* family

Badge/summary widgets showing Ops scores (Health, Risk, Efficiency,
Capacity, Stress, AlertVolume, TimeRemaining, Workload).

**Live count:** 15 widgets across 8 types.

All share the same minimal config:

```json
{
  "refreshInterval": 300,
  "resource": {"resourceId": "resource:id:N_::_", "resourceName": "..."},
  "refreshContent": {"refreshContent": true},
  "selfProvider": {"selfProvider": true},
  "title": "..."
}
```

Types with `badgeMode` field: IntSummaryHealth, IntSummaryRisk,
IntSummaryEfficiency. Value: `{"badgeMode": false}`.

Non-self-provider IntSummary widgets set `resource: null` and
`selfProvider: false`.

---

### ScoreboardHealth

Single-resource health/risk/efficiency badge icon.

**Live count:** 1 widget.

```json
{
  "type": "ScoreboardHealth",
  "config": {
    "metricType": {"metricType": "health"},
    "refreshInterval": 300,
    "metricValue": "",
    "refreshContent": {"refreshContent": false},
    "resources": [],
    "selfProvider": {"selfProvider": false},
    "title": "Object health",
    "imageType": "circle"
  }
}
```

`imageType`: `"circle"` or `"square"`.
`metricType.metricType`: `"health"`, `"risk"`, or `"efficiency"`.

---

### ResourceRelationshipAdvanced

Object relationship tree with traversal spec.

**Live count:** 34 widgets across 34 dashboards.

Key config fields:
- `traversalSpecId`: string like `"vSphere Hosts and Clusters-VMWARE-vSphere World"`
- `depth`: string `"1,1"` (parent depth, child depth)
- `resourceId`: `null` (interaction-driven) or specific ID
- `tagFilter`: optional tag filter object
- `visualTheme`: present in some specimens
- `paginationNumber`: present in some
- `selectFirstRow`: present in some

---

### Skittles

Badge summary grid showing health/risk/efficiency for resource kinds.

**Live count:** 4 widgets.

```json
{
  "type": "Skittles",
  "config": {
    "mode": "custom",
    "badge": [
      {"badgeKey": "health", "badgeName": "Health", "show": true, "label": null},
      {"badgeKey": "risk", "badgeName": "Risk", "show": true, "label": null},
      {"badgeKey": "efficiency", "badgeName": "Efficiency", "show": true, "label": null}
    ],
    "custom": [
      {"resourceKindName": "Cluster Node", "resourceKindId": "resourceKind:id:43_::_"}
    ],
    "selfProvider": {"selfProvider": false},
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": false}
  }
}
```

---

### MashupChart

Object Health Timeline. Minimal config (4 standard fields only).
All display state in `states[]` UI preferences.

**Live count:** 1 widget.

```json
{
  "type": "MashupChart",
  "config": {
    "refreshInterval": 300,
    "refreshContent": {"refreshContent": true},
    "selfProvider": {"selfProvider": false},
    "title": "Object Health Timeline"
  }
}
```

---

### MetricPicker

Interactive metric browser. Config is effectively empty.

**Live count:** 5 widgets. Broadcasts `metricId` interaction to
MetricChart widgets.

---

## colorMethod values

| Value | Meaning | Count across all metric entries |
|---|---|---|
| 0 | Custom thresholds: `yellowBound`/`orangeBound`/`redBound` apply | ~150 |
| 1 | No coloring (neutral) | ~105 |
| 2 | Dynamic thresholds (Ops auto-computes color) | ~216 |

## `entries.resourceKind[]` cross-reference

**Critical finding:** Every `resourceKind:id:N_::_` reference in
ANY widget config field MUST have a corresponding entry in
`entries.resourceKind[]`. Verified: 2,533 references across all
widgets, 0 mismatches. This includes:

- `metric.resourceKindMetrics[].resourceKindId`
- HealthChart `config.resourceKindId`
- ParetoAnalysis `config.resourceKind[].id`
- ParetoAnalysis `config.metricOption.resourceKindId[]`
- Heatmap `configs[].resourceKind`
- Heatmap `configs[].groupBy.typeId`
- Skittles `custom[].resourceKindId`

The `entries.resourceKind[]` array contains objects like:

```json
{
  "resourceKindKey": "VirtualMachine",
  "internalId": "resourceKind:id:0_::_",
  "adapterKindKey": "VMWARE"
}
```

The renderer must collect all `resourceKind:id:N_::_` references
from all widgets (not just View/ResourceList) and include them in
the entries table.

## `entries.resource[]` cross-reference

Resources referenced via `resource:id:N_::_` (in `config.resource[]`
or `metric.resourceMetrics[].resourceId`) must also exist in
`entries.resource[]`:

```json
{
  "resourceKindKey": "vSphere World",
  "internalId": "resource:id:0_::_",
  "adapterKindKey": "VMWARE",
  "identifiers": [],
  "name": "vSphere World"
}
```

## `customFilter.filter[]` format

When widgets use property-value filtering:

```json
{
  "resourceKind": "002006VMWAREVirtualMachine",
  "filterTypes": [
    {
      "condition": "EQUALS",
      "metricKey": "summary|config|productName",
      "metricValue": {"isStringMetric": true, "value": "SDDC-Manager"},
      "filterType": "properties"
    }
  ]
}
```

Note: `resourceKind` in `filter[]` uses the full adapter-prefixed
form, not `resourceKind:id:N_::_`.

## Self-provider chart widgets do NOT need `entries.resource`

Unlike View widgets, self-provider chart widgets in
`mode: "all"` or `mode: "resourceKind"` use `resourceKind[]`
references to scope their data, not a pinned `resource:id:N_::_`.
They set `selfProvider: true` and `resource: []` (empty array).
No `entries.resource` entry is needed.

Only `mode: "resource"` self-provider widgets (ParetoAnalysis,
HealthChart, MetricChart) need a pinned resource in
`entries.resource[]`.

## Implementation priority (by live usage count)

1. **TextDisplay** (106) -- zero data source, trivial config
2. **Scoreboard** (245) -- same metric spec as MetricChart
3. **MetricChart** (82) -- workhorse time-series chart
4. **HealthChart** (132) -- different (flat) metric spec
5. **ParetoAnalysis** (65) -- different (flat) metric spec
6. **PropertyList** (47) -- same metric spec as MetricChart
7. **SparklineChart** (4) -- same metric spec
8. **Heatmap** (70) -- unique complex config
9. **AlertList** (24) -- filter-oriented, no metric spec
10. **ProblemAlertsList** (19) -- badge filter, minimal config
11. **IntSummary\*** (15) -- trivial config
12. **ScoreboardHealth** (1) -- trivial config

## Gotchas

1. **`relationshipMode` wrapping varies.** Some widgets use
   `{"relationshipMode": 0}` (int), others use
   `{"relationshipMode": [-1, 0]}` (array). ParetoAnalysis,
   AlertList, and Heatmap tend to use the array form. Both
   import correctly.

2. **Scoreboard wraps all booleans.** `showResourceName`,
   `showMetricName`, etc. are all `{fieldName: value}` -- never
   bare booleans.

3. **ParetoAnalysis has TWO config shapes.** Shape 1 (flat
   `metric` + `resourceKind[]`) for `mode: "all"/"resource"`.
   Shape 2 (`metricOption` + `tagOption`) for `mode: "metric"`.
   They are mutually exclusive.

4. **ParetoAnalysis `metric` is flat**, not the
   `{mode, resourceKindMetrics[]}` structure. Just
   `{metricKey, name}`.

5. **HealthChart `metricType`** -- use `"custom"` for specific
   metrics (127/132). `"health"` (5/132) shows badge health
   score instead of a specific metric.

6. **HealthChart has self-provider instances** (29/132 on live
   instance). Prior reference-repo analysis found 0. Self-provider
   HealthCharts use `mode: "resource"` with a pinned resource.

7. **Heatmap `groupBy.id`** format is
   `004null<6-digit-prefix><adapterKind><resourceKind>`.

8. **TextDisplay requires `locationFile` and `locationUrl`** as
   empty strings even when using `editorData`.

9. **Scoreboard `visualTheme` goes to 9** (not 5 or 6 as some
   docs state). Theme 8 is most common (141/245).

10. **`resource` mode vs `resourceKind` mode**: When a metric
    entry uses `mode: "resource"`, the `resourceKindId` switches
    to the full adapter-prefixed form (e.g.
    `"002006VMWAREVirtualMachine"`). In `mode: "resourceKind"`,
    it uses `"resourceKind:id:N_::_"`.

11. **SparklineChart `showResourceName`** wraps as
    `{"showObjectName": bool}`, not `{"showResourceName": bool}`.

12. **AlertList `type` codes** are `"<category>_<subtype>"`
    strings, not integers. Categories: 15-20. Subtypes: 18-22.
