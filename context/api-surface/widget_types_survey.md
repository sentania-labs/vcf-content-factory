# VCF Ops Dashboard Widget Types Survey

**Date:** 2026-04-09
**Source:** Live instance export (231 dashboards, 2,019 widgets) + reference repos

NOTE: used inline scripts for `/api/content/operations/export` and zip parsing
because `vcfops_dashboards.client` has no `export_dashboards` convenience method.

---

## Summary table — all widget types found

| Type | Live count | Live dashboards | In reference repos | Category |
|---|---|---|---|---|
| View | 1,063 | 196 | yes | Supported (renderer v1) |
| Scoreboard | 245 | 89 | yes | Not supported |
| HealthChart | 132 | 37 | yes | Not supported |
| TextDisplay | 106 | 55 | yes | Not supported |
| MetricChart | 82 | 34 | yes | Not supported — **chart** |
| ResourceList | 75 | 44 | yes | Supported (renderer v1) |
| Heatmap | 70 | 38 | yes | Not supported |
| ParetoAnalysis | 65 | 25 | yes | Not supported |
| PropertyList | 47 | 23 | yes | Not supported |
| ResourceRelationshipAdvanced | 34 | 34 | yes | Not supported |
| AlertList | 24 | 18 | yes | Not supported |
| ProblemAlertsList | 19 | 9 | yes | Not supported |
| LogAnalysis | 14 | 7 | no | Not supported |
| ResourceRelationship | 6 | 5 | yes | Not supported |
| MetricPicker | 5 | 5 | yes | Not supported |
| Skittles | 4 | 4 | no | Not supported |
| TopologyGraph | 4 | 4 | no | Not supported |
| SparklineChart | 4 | 3 | yes | Not supported — **chart** |
| IntSummaryHealth | 3 | 3 | no | Not supported — IntSummary family |
| IntSummaryStress | 3 | 3 | no | Not supported — IntSummary family |
| IntSummaryCapacity | 3 | 2 | yes | Not supported — IntSummary family |
| IntSummaryRisk | 2 | 2 | no | Not supported — IntSummary family |
| IntSummaryEfficiency | 2 | 2 | no | Not supported — IntSummary family |
| Geo | 1 | 1 | no | Not supported |
| IntSummaryAlertVolume | 1 | 1 | no | Not supported — IntSummary family |
| ScoreboardHealth | 1 | 1 | no | Not supported |
| TagPicker | 1 | 1 | no | Not supported |
| MashupChart | 1 | 1 | no | Not supported — **chart** |
| ContainerOverview | 1 | 1 | no | Not supported |
| ContainerDetails | 1 | 1 | no | Not supported |

**Reference-repo-only types (not on live instance):**

| Type | Seen in | Notes |
|---|---|---|
| IntSummaryTimeRemaining | brockpeterson + dalehassinger | same config shape as IntSummaryCapacity |
| IntSummaryWorkload | dalehassinger | same config shape as IntSummaryStress |

---

## Top-level widget JSON structure (all types)

Every widget in `dashboard.dashboards[*].widgets[]` has this envelope regardless of type:

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

`states` is optional (present on some types, absent on others). It encodes user
UI preferences as percent-encoded key/value pairs — not required for import.

Widget interactions live in `dashboard.widgetInteractions[]`:

```json
{
  "widgetIdProvider": "<uuid of sender widget>",
  "type": "resourceId",
  "widgetIdReceiver": "<uuid of receiver widget>"
}
```

---

## Per-type representative config objects

### MetricChart (82 widgets, 34 dashboards)

Line/area chart of one or more metrics over time. Can be self-provider
(pinned resource) or receive a resource from an interaction.

Config keys: `metric`, `refreshContent`, `refreshInterval`, `relationshipMode`,
`resInteractionMode`, `selfProvider`, `title`

The chart type (line, area, bar) is NOT in the config object — it appears to
be a UI-only state persisted in `states[]` via `permMetricChart_widget_...` keys
that encode strings like `"o%3A"` (URL-encoded serialised UI state). The default
rendering is a line chart with area fill.

`config.metric` structure:
- `mode`: `"resource"` (specific named resource) or `"resourceKind"` (all
  resources of a kind, subject to depth/filter)
- `resourceMetrics[]`: one entry per metric when mode=resource; each has
  `resourceId` (internalId from the entries dict), `metricKey`, `metricName`,
  `resourceKindId`, `colorMethod`, `metricUnitId`, `unit`
- `resourceKindMetrics[]`: one entry per metric when mode=resourceKind; same
  fields minus `resourceId`, adds `resourceKindId`

```json
{
  "collapsed": false,
  "id": "5bde0e82-b8b8-4c7c-b546-bad845879b1b",
  "gridsterCoords": { "w": 4, "x": 1, "h": 6, "y": 4 },
  "type": "MetricChart",
  "title": "Reclaimable Memory Trend (Last 30 Days)",
  "config": {
    "metric": {
      "mode": "resource",
      "resourceMetrics": [
        {
          "metricUnitId": null,
          "resourceId": "resource:id:2_::_",
          "unit": null,
          "metricName": "Summary|Reclaimable Memory (TB)",
          "metricKey": "summary|reclaimable_memory_tb",
          "isStringMetric": false,
          "resourceName": "Aggregator World",
          "id": "extModel8085-1",
          "resourceKindId": "002016FederatedAdapterFederationWorld",
          "colorMethod": 2
        }
      ],
      "resourceKindMetrics": []
    },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": false },
    "relationshipMode": 0,
    "selfProvider": { "selfProvider": true },
    "title": "Reclaimable Memory Trend (Last 30 Days)",
    "resInteractionMode": null
  },
  "height": 324
}
```

---

### SparklineChart (4 widgets, 3 dashboards)

Sparkline-per-row list: shows a table where each row is a resource with
small inline sparkline graphs for one or more metrics. Receives a resource
via interaction, then shows all descendants of a given kind.

Config keys: `columnSequence`, `customFilter`, `depth`, `metric`,
`refreshContent`, `refreshInterval`, `relationshipMode`, `resInteractionMode`,
`resource`, `selfProvider`, `showDT`, `showResourceName`, `title`

Notable: `metric.subMode` = `"resourceKindAll"` means all instances of the
kind. `customFilter.filter[]` allows property-value filtering.
`columnSequence.columnSequence` = `"graphFirst"` or `"tableFirst"`.

```json
{
  "collapsed": false,
  "id": "09f8deb0-01a4-4d38-a2bc-dfd8b3294a5f",
  "gridsterCoords": { "w": 4, "x": 9, "h": 5, "y": 11 },
  "type": "SparklineChart",
  "title": "SDDC Manager Sparkline Chart",
  "config": {
    "refreshInterval": 300,
    "resource": [],
    "showDT": { "showDT": true },
    "refreshContent": { "refreshContent": false },
    "relationshipMode": { "relationshipMode": 0 },
    "title": "SDDC Manager Sparkline Chart",
    "showResourceName": { "showObjectName": false },
    "depth": 1,
    "columnSequence": { "columnSequence": "graphFirst" },
    "metric": {
      "mode": "resourceKind",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "guest|contextSwapRate_latest",
          "metricName": "Guest|CPU Context Switch Rate",
          "label": "CPU Context Rate",
          "resourceKindName": "Virtual Machine",
          "resourceKindId": "resourceKind:id:3_::_",
          "colorMethod": 1,
          "isStringMetric": false
        }
      ],
      "subMode": "resourceKindAll"
    },
    "customFilter": {
      "filter": [
        {
          "resourceKind": "002006VMWAREVirtualMachine",
          "filterTypes": [
            {
              "condition": "EQUALS",
              "metricKey": "summary|config|productName",
              "metricValue": { "isStringMetric": true, "value": "SDDC-Manager" },
              "filterType": "properties"
            }
          ]
        }
      ],
      "excludedResources": null,
      "includedResources": null
    },
    "selfProvider": { "selfProvider": false },
    "resInteractionMode": null
  },
  "height": 267
}
```

---

### MashupChart (1 widget, 1 dashboard)

Object Health Timeline — shows a combined health/alert timeline for the
selected object and its descendants. Minimal config; most display settings
are in `states[]` as URL-encoded preferences. Self-provider or receives
from interaction.

Config keys: `refreshContent`, `refreshInterval`, `selfProvider`, `title`

```json
{
  "collapsed": false,
  "id": "d59330da-cc6c-400a-a400-760fcc1cec95",
  "gridsterCoords": { "w": 6, "x": 1, "h": 6, "y": 14 },
  "type": "MashupChart",
  "title": "Object Health Timeline",
  "config": {
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": true },
    "selfProvider": { "selfProvider": false },
    "title": "Object Health Timeline"
  },
  "height": 324
}
```

---

### Scoreboard (245 widgets, 89 dashboards)

Grid of metric value badges — shows current or delta values for multiple
metrics. Supports sparkline insets (`showSparkline`), configurable visual
themes (0–5), fixed or auto layout modes.

Config keys: `boxColumns`, `boxHeight`, `customFilter`, `depth`, `labelSize`,
`maxCellCount`, `metric`, `mode`, `oldMetricValues`, `periodLength`,
`refreshContent`, `refreshInterval`, `relationshipMode`, `resInteractionMode`,
`resource`, `roundDecimals`, `selfProvider`, `showDT`, `showMetricName`,
`showMetricUnit`, `showResourceName`, `showSparkline`, `title`, `valueSize`,
`visualTheme`

`config.metric` follows the same `mode` / `resourceMetrics` /
`resourceKindMetrics` structure as MetricChart.
`config.mode.layoutMode` = `"fixedView"` or `"floatingView"`.
`config.visualTheme` = integer 1–5 (color/style preset).

```json
{
  "type": "Scoreboard",
  "config": {
    "maxCellCount": 100,
    "oldMetricValues": false,
    "relationshipMode": { "relationshipMode": 0 },
    "valueSize": 24,
    "labelSize": 12,
    "mode": { "layoutMode": "fixedView" },
    "selfProvider": { "selfProvider": true },
    "visualTheme": 5,
    "showMetricName": { "showMetricName": true },
    "showMetricUnit": { "showMetricUnit": true },
    "showResourceName": { "showResourceName": false },
    "showDT": { "showDT": true },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": true },
    "depth": 1,
    "metric": {
      "mode": "resourceKind",
      "resourceMetrics": [],
      "resourceKindMetrics": [
        {
          "metricKey": "summary|total_number_hosts",
          "metricName": "Summary|Total Number of Hosts",
          "label": "Host Count",
          "resourceKindName": "vSphere World",
          "resourceKindId": "resourceKind:id:1_::_",
          "colorMethod": 2
        }
      ]
    },
    "resource": [],
    "customFilter": { "filter": [], "excludedResources": null, "includedResources": null }
  }
}
```

---

### ScoreboardHealth (1 widget, 1 dashboard)

Single-resource health badge (circle or square image). Shows health/risk/
efficiency badge icon for the currently selected object.

Config keys: `imageType`, `metricType`, `metricValue`, `refreshContent`,
`refreshInterval`, `resources`, `selfProvider`, `title`

```json
{
  "type": "ScoreboardHealth",
  "config": {
    "metricType": { "metricType": "health" },
    "refreshInterval": 300,
    "metricValue": "",
    "refreshContent": { "refreshContent": false },
    "resources": [],
    "selfProvider": { "selfProvider": false },
    "title": "Object health",
    "imageType": "circle"
  }
}
```

---

### HealthChart (132 widgets, 37 dashboards)

Horizontal bar chart ranking resources by a single metric value, with
colour thresholds (yellow/orange/red bounds). Typically receives a resource
from an interaction (e.g. a View picker) and shows descendants at `depth`.

Config keys: `chartHeight`, `customFilter`, `depth`, `filterMode`,
`metricFullName`, `metricKey`, `metricLabel`, `metricName`, `metricType`,
`metricUnit`, `mode`, `orangeBound`, `paginationNumber`, `redBound`,
`refreshContent`, `refreshInterval`, `relationshipMode`, `resource`,
`resourceKindId`, `selectFirstRow`, `selfProvider`, `showMetricLabel`,
`showResourceName`, `sortBy`, `sortByDir`, `tagFilter`, `title`, `yellowBound`

```json
{
  "type": "HealthChart",
  "config": {
    "yellowBound": 0.1,
    "orangeBound": 1,
    "redBound": 2,
    "metricKey": "net:physical|droppedPct",
    "metricName": "Network:physical|Packets Dropped (%)",
    "metricFullName": "Network:Physical|Packets Dropped (%)",
    "metricLabel": "",
    "metricType": { "metricType": "custom" },
    "metricUnit": { "metricUnitId": -1, "metricUnitName": "Default Unit" },
    "chartHeight": 135,
    "paginationNumber": 15,
    "mode": "all",
    "filterMode": "tagPicker",
    "tagFilter": null,
    "sortBy": "metricValue",
    "sortByDir": { "orderByDir": "asc" },
    "showResourceName": { "showResourceName": false },
    "showMetricLabel": { "showMetricLabel": false },
    "resourceKindId": "resourceKind:id:0_::_",
    "depth": 1,
    "selfProvider": { "selfProvider": false },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": false },
    "customFilter": { "filter": [], "excludedResources": null, "includedResources": null },
    "selectFirstRow": { "selectFirstRow": false },
    "relationshipMode": { "relationshipMode": 0 },
    "resource": []
  }
}
```

---

### Heatmap (70 widgets, 38 dashboards)

2-D heatmap grid colouring resources by one metric, optionally grouping by
another resource kind.

Config keys: `configs`, `depth`, `mode`, `refreshContent`, `refreshInterval`,
`relationshipMode`, `resource`, `selfProvider`, `title`, `value`

`config.configs[]` is an array of heatmap layer definitions, each with:
- `colorBy`: `{ "metricKey": "...", "value": "Display Name" }`
- `sizeBy`: same shape (can be empty string for uniform size)
- `groupBy`: resource kind to group tiles into swim-lanes
- `color.thresholds`: `{ "values": [...], "colors": [...] }` — one more color than value
- `solidColoring`: boolean
- `resourceKind`: internalId string of the subject resource kind
- `filterMode`: `"tagPicker"` | `"customFilter"`

```json
{
  "type": "Heatmap",
  "config": {
    "mode": "all",
    "depth": 10,
    "selfProvider": { "selfProvider": true },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": false },
    "resource": [],
    "relationshipMode": { "relationshipMode": [1, -1, 0] },
    "configs": [
      {
        "colorBy": {
          "metricKey": "OnlineCapacityAnalytics|capacityRemainingPercentage",
          "value": "Capacity Analytics Generated|Capacity Remaining Percentage (%)"
        },
        "sizeBy": { "metricKey": null, "value": "" },
        "groupBy": {
          "originalText": "Cluster Compute Resource",
          "typeId": "resourceKind:id:0_::_",
          "id": "004null002006VMWAREClusterComputeResource",
          "text": "Cluster Compute Resource",
          "type": "resourceKind",
          "parentText": "vCenter Adapter",
          "parentId": "VMWARE"
        },
        "color": {
          "minValue": 0,
          "maxValue": 100,
          "thresholds": {
            "values": [0, 5, 10, 80],
            "colors": ["#DE3F30", "#ED891F", "#ECC33E", "#74B43B", "#8D8B8D"]
          }
        },
        "solidColoring": true,
        "resourceKind": "resourceKind:id:2_::_",
        "relationalGrouping": false,
        "filterMode": "tagPicker",
        "mode": { "mode": false },
        "attributeKind": { "value": "" },
        "thenBy": null,
        "name": "Capacity Remaining",
        "focusOnGroups": true
      }
    ]
  }
}
```

---

### ParetoAnalysis (65 widgets, 25 dashboards)

Top-N bar chart showing the best or worst resources ranked by a metric or
badge score. Self-provider only (no incoming interactions observed).

Config keys: `additionalColumns`, `additionalColumns_resource`, `barsCount`,
`depth`, `filterMode`, `filterOldMetrics`, `metricOption`, `mode`,
`refreshContent`, `refreshInterval`, `regenerationTime`, `roundDecimals`,
`selfProvider`, `tagOption`, `title`

```json
{
  "type": "ParetoAnalysis",
  "config": {
    "barsCount": 5,
    "regenerationTime": 15,
    "mode": "metric",
    "filterMode": "tagFilter",
    "depth": 10,
    "roundDecimals": 1,
    "filterOldMetrics": { "filterOldMetrics": false },
    "selfProvider": { "selfProvider": true },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": true },
    "tagOption": {
      "tagFilter": null,
      "value": { "tagOption": "leastHealthyApplications" }
    },
    "metricOption": {
      "tagFilter": null,
      "resourceKindId": ["resourceKind:id:0_::_"],
      "metricInfo": {
        "path": ["/source/GROUP_OnlineCapacityAnalytics/OnlineCapacityAnalytics|capacityRemainingPercentage"],
        "value": "OnlineCapacityAnalytics|capacityRemainingPercentage"
      },
      "value": { "metricOption": "metricsLowestUtilization" }
    },
    "additionalColumns": [],
    "additionalColumns_resource": []
  }
}
```

---

### TextDisplay (106 widgets, 55 dashboards)

HTML/text label widget. Used for section headers, instructions, and inline
documentation. Supports rich HTML via `editorData` or a URL via `locationUrl`.

Config keys: `editorData`, `locationFile`, `locationUrl`, `refreshContent`,
`refreshInterval`, `title`, `titleLocalized`, `viewModeHTML`

```json
{
  "type": "TextDisplay",
  "config": {
    "locationFile": "",
    "locationUrl": "",
    "editorData": "<br>",
    "refreshInterval": 300,
    "titleLocalized": "Cluster Settings",
    "refreshContent": { "refreshContent": false },
    "title": "Cluster Settings",
    "viewModeHTML": true
  }
}
```

---

### PropertyList (47 widgets, 23 dashboards)

Vertical list of metric values for the selected resource. Similar to
Scoreboard but vertical and single-resource oriented. Receives from
interaction.

Config keys: `customFilter`, `depth`, `metric`, `refreshContent`,
`refreshInterval`, `relationshipMode`, `resInteractionMode`, `resource`,
`selfProvider`, `showMetricFullName`, `title`, `visualTheme`

`config.metric` follows same structure as MetricChart/Scoreboard.

---

### ResourceRelationshipAdvanced (34 widgets, 34 dashboards)

Object relationship tree using a traversal spec. Shows parent/child hierarchy.
Receives a resource from a picker and displays the full tree for it.

Config keys: `customFilter`, `depth`, `filterMode`, `refreshContent`,
`refreshInterval`, `resourceId`, `resourceName`, `selfProvider`, `tagFilter`,
`title`, `traversalSpecId`

```json
{
  "type": "ResourceRelationshipAdvanced",
  "config": {
    "filterMode": "tagPicker",
    "tagFilter": { "path": [...], "value": { "kind": [...], ... } },
    "resourceId": null,
    "resourceName": null,
    "depth": "1,1",
    "traversalSpecId": "vSphere Hosts and Clusters-VMWARE-vSphere World",
    "selfProvider": { "selfProvider": false },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": false },
    "customFilter": { "filter": [], "excludedResources": null, "includedResources": null }
  }
}
```

---

### ResourceRelationship (6 widgets, 5 dashboards)

Simpler topology/relationship widget (older widget generation). Shows
parent/child graph for selected object.

Config keys: `autoZoom`, `nodeSize`, `refreshContent`, `refreshInterval`,
`resourceName`, `selfProvider`, `tagFilter`, `title`

---

### AlertList (24 widgets, 18 dashboards)

List of active alerts for selected resources. Filtered by criticality,
alert type codes, status, and impact.

Config keys: `alertAction`, `alertImpact`, `criticalityLevel`, `customFilter`,
`depth`, `filterMode`, `mode`, `refreshContent`, `refreshInterval`,
`relationshipMode`, `resource`, `selfProvider`, `state`, `status`, `tagFilter`,
`title`, `type`

Alert type codes are strings like `"15_19"` (category_subtype integers).
Criticality: 2=Warning, 3=Major, 4=Critical.

---

### ProblemAlertsList (19 widgets, 9 dashboards)

Shows top alerts impacting a specific badge (health/risk/efficiency) for
descendants of the selected resource.

Config keys: `impactedBadge`, `refreshContent`, `refreshInterval`, `resource`,
`selfProvider`, `title`, `triggeredObject`

```json
{
  "type": "ProblemAlertsList",
  "config": {
    "impactedBadge": "health",
    "triggeredObject": { "triggeredObject": "children" },
    "resource": { "resourceId": "resource:id:1_::_", "resourceName": "Universe" },
    "selfProvider": { "selfProvider": true },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": true }
  }
}
```

---

### LogAnalysis (14 widgets, 7 dashboards)

Integrates a VCF Operations log query (from Log Insight / vRealize Log
Insight integration) as a chart or table in the dashboard. References
queries by UUID (`liQueryId`).

Config keys: `chartType`, `depth`, `liAggregationFunction`, `liOverTime`,
`liQueryConfig`, `liQueryId`, `liQueryMode`, `liViewMode`, `mode`,
`queryFilter`, `queryFilter_searchtext`, `refreshContent`, `refreshInterval`,
`relationshipMode`, `resource`, `selfProvider`, `title`

`config.chartType` values observed: `"scalar"`.
`config.liViewMode` values observed: `"chart"`.

---

### MetricPicker (5 widgets, 5 dashboards)

Picker widget that broadcasts a chosen metric to other widgets via
interactions. Config is empty (`{}`).

---

### TagPicker (1 widget, 1 dashboard)

Picker widget for filtering by object tags. Config contains only
`refreshInterval` and `refreshContent`.

---

### Skittles (4 widgets, 4 dashboards)

Badge summary grid — shows health/risk/efficiency badges for a set of
resource kinds in one compact widget.

Config keys: `badge`, `custom`, `mode`, `refreshContent`, `refreshInterval`,
`selfProvider`, `title`

```json
{
  "type": "Skittles",
  "config": {
    "mode": "custom",
    "badge": [
      { "badgeKey": "health", "badgeName": "Health", "show": true, "label": null },
      { "badgeKey": "risk", "badgeName": "Risk", "show": true, "label": null },
      { "badgeKey": "efficiency", "badgeName": "Efficiency", "show": true, "label": null }
    ],
    "custom": [
      { "resourceKindName": "Cluster Node", "resourceKindId": "resourceKind:id:43_::_" }
    ],
    "selfProvider": { "selfProvider": false },
    "refreshInterval": 300,
    "refreshContent": { "refreshContent": false }
  }
}
```

---

### TopologyGraph (4 widgets, 4 dashboards)

NSX-specific network topology graph with custom relationship traversal specs
(`lightWeightRelationships`). Complex config.

Config keys: `custom`, `depth`, `filterMode`, `mode`, `refreshContent`,
`refreshInterval`, `resInteractionMode`, `resource`, `resources`,
`selfProvider`, `title`, `treeType`

---

### Geo (1 widget, 1 dashboard)

Geographic map showing resource locations. Used in Sustainability dashboard.

Config keys: `customFilter`, `filterMode`, `refreshContent`, `refreshInterval`,
`selfProvider`, `tagFilter`, `title`

---

### MashupChart (1 widget, 1 dashboard)

Object Health Timeline chart — combined metric + alert timeline view.
All display state is in `states[]` URL-encoded preferences; `config` has
only the four standard fields: `refreshInterval`, `refreshContent`,
`selfProvider`, `title`.

---

### IntSummary* family (15 widgets across 8 types)

A family of badge/summary widgets that show a single Ops score (Health,
Risk, Efficiency, Capacity, Stress, TimeRemaining, Workload, AlertVolume)
for the selected resource or environment. Used in "summary page" style
dashboards.

All share the same config shape:

```json
{
  "refreshInterval": 300,
  "resource": { "resourceId": "resource:id:1_::_", "resourceName": "Universe" },
  "refreshContent": { "refreshContent": true },
  "selfProvider": { "selfProvider": true },
  "title": "Environment Health"
}
```

Some (IntSummaryHealth, IntSummaryRisk, IntSummaryEfficiency) add a
`badgeMode` field: `{ "badgeMode": false }`.

Types observed on instance: Health, Risk, Efficiency, Capacity, Stress,
AlertVolume.
Types in reference repos only: TimeRemaining, Workload.

---

### ScoreboardHealth (1 widget)

Single-resource health/risk/efficiency badge as an icon (circle or square).

Config keys: `imageType`, `metricType`, `metricValue`, `refreshContent`,
`refreshInterval`, `resources`, `selfProvider`, `title`

---

### ContainerOverview / ContainerDetails (1 each)

vRNI-specific widgets for Application/Tier containers. Not relevant to
vSphere/VCF content authoring in this factory.

---

## Chart type determination — MetricChart

The MetricChart renders as a time-series line/area chart by default. There
is no `chartType` field in `config`. The chart style appears to be controlled
entirely by user-persisted `states[]` preferences — specifically a state key
matching `permMetricChart_widget_<dashboard-id>_<widget-id>` whose value is
a URL-encoded object. This means authors cannot force a bar chart vs. line
chart at import time; the default rendering is the line/area combination.

The LogAnalysis widget DOES have a `config.chartType` field (observed value:
`"scalar"`), but this is a different widget for log data, not metric time-series.

## selfProvider vs interaction-driven

Across all chart/visualization widget types, `config.selfProvider.selfProvider`
is a boolean:
- `true` — widget fetches its own data (pinned to a specific resource or
  resource kind, independent of other widget selections)
- `false` — widget receives its subject resource via a `widgetInteractions[]`
  entry from a provider widget (ResourceList, View, MetricPicker, TagPicker)

Self-provider widgets must have their data source specified in `config.metric`
or `config.resource`. Interaction-driven widgets can have empty `resource: []`
and rely on the runtime interaction to supply context.

## Resource ID encoding

Resources referenced in `config` use internalId strings from the `entries`
section of the dashboard JSON:

```
"resource:id:<N>_::_"      — specific resource (the <N> is an index into entries.resource[])
"resourceKind:id:<N>_::_"  — resource kind (index into entries.resourceKind[])
```

The `entries` section maps these internalIds to adapter kind + resource kind
keys and (for resources) actual resource names/identifiers. This encoding is
instance-specific — the same resource will have a different internalId on a
different instance.

`resourceKindId` fields in metric configs follow a different encoding:
`"<6-digit-adapter-prefix><adapter-kind><resource-kind>"` — e.g.
`"002006VMWAREVirtualMachine"` where `002006` is the VMWARE adapter prefix.

## What renderer v1 (this repo) currently supports

From `vcfops_dashboards/loader.py` (line 87) and `render.py`:

- **ResourceList** — fully supported
- **View** — fully supported (including self-provider + pin)
- **Everything else** — rejected at load time with:
  `"unsupported type <X> (v1 supports ResourceList, View)"`

To add a new widget type, the `tooling` agent needs to:
1. Add the type to the allowlist in `loader.py` line 145
2. Add a render function in `render.py` returning the appropriate JSON dict
3. Update the YAML schema in `loader.py` to capture any type-specific fields

The most impactful additions (by live usage count) would be, in order:
1. **Scoreboard** (245 widgets) — static metric value badges, no render
   complexity; config is self-contained
2. **HealthChart** (132 widgets) — horizontal bar chart, single metric,
   thresholds; commonly receives interactions from View
3. **TextDisplay** (106 widgets) — pure HTML/text label; trivial config
4. **MetricChart** (82 widgets) — time-series line chart; `metric.mode`
   determines data source
5. **Heatmap** (70 widgets) — most complex config; `configs[]` array with
   groupBy + colorBy
6. **ParetoAnalysis** (65 widgets) — top-N bar chart; self-provider only
