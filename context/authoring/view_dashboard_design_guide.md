# View & Dashboard Design Guide

Comprehensive reference for authoring views and dashboards in the
VCF Content Factory. Consolidates wire format findings, supported
capabilities, and design patterns.

Last updated: 2026-05-27

---

## View types

The factory supports three view types, covering all fundamental data
presentation patterns.

### List views (`data_type: list`)

Flat tabular views. One row per resource, columns show metrics or
properties. Two presentations:

- `list` — sortable table (default)
- `summary` — table with footer aggregation row (SUM/AVG/MIN/MAX/COUNT)

### Distribution views (`data_type: distribution`)

Group resources into buckets. Three presentations:

- `bar-chart` — fixed numeric histogram (`is_dynamic: false`, set
  min/max/bucket-count)
- `pie-chart` — discrete string grouping (`is_dynamic: true`,
  `calc_function: DISCRETE`)
- `donut-chart` — same as pie-chart, different visual

### Trend views (`data_type: trend`)

Time-series line charts. One presentation:

- `line-chart` — stacks NONE + TREND + optional FORECAST

Optional forecast horizon via `forecast_days`.

---

## Column transformations

Each column in a view can apply one transformation to its metric.
The full confirmed enum (ops-recon 2026-05-27, 13.6 MB live export):

| Transform | Live uses | Sibling properties | Notes |
|---|---|---|---|
| `CURRENT` | 2814 | none | Latest poll value. Default for list views. |
| `LAST` | 138 | none | Most-recent stored sample. Distinct from CURRENT. |
| `AVG` | 98 | none | Average over time window. |
| `MAX` | 235 | none | Maximum over time window. |
| `MIN` | 15 | none | Minimum over time window. |
| `SUM` | 59 | none | Sum over time window. |
| `PERCENTILE` | 148 | `percentile: N` (1–99) | Nth percentile over time window. |
| `TIMESTAMP` | 24 | none | Shows timestamp instead of value. For property columns. |
| `TIME_POINT` | 12 | 3 fields (see below) | Timestamp when a related metric hit its extreme. |
| `NONE` | 306 | none | Raw data points. Trend/distribution views only. |
| `TREND` | 57 | none | Trend line. Trend views only, stacked with NONE. |
| `FORECAST` | 57 | none | Linear projection. Trend views, stacked. |
| `TRANSFORM_EXPRESSION` | 10 | `transform_expression: "<expr>"` | Arbitrary formula. Only `avg` is bound. |

**Confirmed absent:** `STDDEV`, `HIGH_WATER_MARK` — zero hits in live
export. Do not use. The UI may show labels for these but they don't
export or import.

### TIME_POINT sibling properties

When `transformation: TIME_POINT`, three fields are required:

```yaml
- attribute: summary|createDate
  display_name: "Time of Max CPU Contention"
  transformation: TIME_POINT
  metric_to_relate_with: "cpu|capacity_contentionPct"
  localized_metric_to_relate_with: "CPU Contention (%)"
  operator_to_relate_with: MAX    # MAX or MIN
```

### TRANSFORM_EXPRESSION

Server-side formula where `avg` is the column's rolled-up value:

```yaml
- attribute: mem|usage_average
  transformation: TRANSFORM_EXPRESSION
  transform_expression: "avg * 100"    # convert 0–1 ratio to percent
```

Only `avg` is bound. Supported operators: `*`, `/`, `+`, `-`,
parentheses, integer/float literals.

### Design rule: percentiles are view transforms, not super metrics

Statistical rollups over time (95th percentile, average over 6 months)
are column transforms. Don't author super metrics for single-metric
rollups. Super metrics are for computing **across objects**.

---

## Time window

All aggregating columns (AVG, MAX, MIN, SUM, PERCENTILE,
TRANSFORM_EXPRESSION) share a single view-level time window:

```yaml
time_window:
  unit: MONTHS    # MONTHS, WEEKS, DAYS, HOURS, MINUTES, YEARS
  count: 6
```

**Per-column time windows are not supported.** If you need different
windows for different columns, create separate views.

Default (if unset): 24 hours. The loader warns if any column uses
an aggregating transform without an explicit time window.

---

## Instance breakdown

VCF Ops handles instanced metrics (per-disk, per-NIC, per-CPU) via
colon notation in the attribute key:

```
<group>:<instance>|<metric>
```

Examples:
- `virtualDisk:scsi0:0|totalReadLatency_average` — specific disk
- `virtualDisk:Aggregate of all instances|totalReadLatency_average` — rolled-up
- `net:vmnic0|usage_average` — specific NIC

### Recommendations

- **Use `:Aggregate of all instances|` for cross-resource list views.**
  Different resources have different instance layouts (scsi0:0 vs
  scsi0:1 vs scsi1:0). The aggregate form works across all.
- **Use specific instances only** when the view is scoped to a single
  resource kind with uniform instance layout (rare).
- **Bare keys have no data** for instanced families. `virtualDisk|totalReadLatency_average`
  (without an instance) returns nothing. Always include the instance or
  aggregate qualifier.

### Ground truth procedure

When unsure about instance layout, query a representative resource:

```
GET /api/resources/{id}/stats?begin=<now-3600000>&end=<now>
```

Inspect `values[].stat-list.stat[].statKey.key` for actual keys.

---

## Per-column color thresholds

Three color bands per column: yellow, orange, red.

```yaml
columns:
  - attribute: cpu|usage_average
    display_name: "CPU Usage"
    transformation: AVG
    yellow_bound: 60
    orange_bound: 75
    red_bound: 90
    ascending_range: false    # false = higher is worse (default)
```

- `ascending_range: true` — lower is worse (e.g., free space)
- Bounds can be numeric or string (for property match, e.g.,
  `red_bound: "Powered Off"`)
- Thresholds are static literals, not symptom-driven
- Color method defaults to "no color" when no bounds set

### Unit handling

`unit` on a column does actual conversion (KB → GB, MHz → GHz),
not just relabeling. Server-side via the VCF Ops unit registry:

```yaml
- attribute: config|hardware|memoryKB
  display_name: "Memory"
  unit: gb    # auto-converts from KB
```

---

## Dashboard widget types

### Supported (11 types, ~95.5% live coverage)

| Widget | YAML key | Use case |
|---|---|---|
| **ResourceList** | `resource_kinds:` | Picker/filter for interactions |
| **View** | `view:` | Embed a list/distribution/trend view |
| **TextDisplay** | `text_display:` | Static HTML/text block |
| **Scoreboard** | `scoreboard:` | Metric tiles (KPIs) |
| **MetricChart** | `metric_chart:` | Time-series line charts |
| **HealthChart** | `health_chart:` | Bar ranking by health score |
| **ParetoAnalysis** | `pareto_analysis:` | Top-N analysis |
| **AlertList** | `alert_list:` | Active alerts for scope |
| **ProblemAlertsList** | `problem_alerts_list:` | Problem-specific alerts |
| **Heatmap** | `heatmap:` | Grid with color-by/size-by metrics |
| **PropertyList** | `property_list:` | Vertical property/metric details panel |

### Priority gaps (not yet supported)

| Widget | Live count | Effort | Notes |
|---|---|---|---|
| ResourceRelationshipAdvanced | 34 | ~0.25 day | Topology box on detail pages |
| SparklineChart | 4 live / 12 ref | ~0.5 day | Per-row inline time-series |
| IntSummary family (8 types) | 16 total | ~0.5 day batch | Health/Risk/Efficiency/etc. badges |

### Won't-support

| Widget | Reason |
|---|---|
| LogAnalysis | Instance-specific query UUID — not portable |
| MashupChart | UI-persisted state only — authors blank on import |
| Geo | Requires instance-specific geo-adapter + lat/long tags |
| TopologyGraph | NSX-specific, references external XML config |

---

## PropertyList widget

New as of 2026-05-27. Displays a vertical list of key-value pairs
for the selected resource. Always interaction-driven (receives a
resource from a ResourceList or View picker).

```yaml
- id: vm_properties
  type: PropertyList
  title: "VM Properties"
  coords: {x: 1, y: 0, w: 4, h: 6}
  property_list:
    visual_theme: 0          # 0–5, default 0
    depth: 1                 # default 1
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
```

Key differences from Scoreboard:
- Always interaction-driven (`selfProvider: false`)
- Supports string properties via `is_string_metric: true`
- Uses `show_metric_full_name` for verbose display
- No self-provider/pin mode observed in any live or reference instance

---

## Dashboard interaction patterns

### Provider → Receiver model

A ResourceList or View widget broadcasts the selected resource to
downstream widgets:

```yaml
interactions:
  - from: vm_picker        # ResourceList local_id
    to: vm_health           # HealthChart local_id
    type: resourceId
```

### Self-provider (pin) mode

Widgets that fetch data independently, ignoring interactions:

```yaml
- id: cluster_scoreboard
  type: Scoreboard
  pin:
    adapter_kind: VMWARE
    resource_kind: ClusterComputeResource
  scoreboard:
    metrics: [...]
```

Supported on: ResourceList, View, Scoreboard, MetricChart,
HealthChart, ParetoAnalysis.

**Gotcha:** `selfProvider: true` with no pinned resource renders blank.
Always specify the pin target.

### Relationship traversal

MetricChart and Heatmap support parent/child traversal:

```yaml
- id: vm_metrics
  type: MetricChart
  relationship_mode: -1    # -1=children, 0=none, 1=parents
```

MetricChart uses a scalar; Heatmap and AlertList accept array form.

---

## Dashboard layout conventions

### Grid system

Coordinates use a 12-column grid:

```yaml
coords: {x: 0, y: 0, w: 12, h: 4}    # full-width, 4 rows tall
```

- `x`: column (0–11)
- `y`: row (0-based, grows downward)
- `w`: width in columns (1–12)
- `h`: height in rows

### Common layout patterns

**Picker + detail (L-R split):**
```
[ResourceList w:3] [View/PropertyList w:9]
```

**Picker + multi-panel:**
```
[ResourceList w:12, h:3]
[Scoreboard w:4] [MetricChart w:4] [HealthChart w:4]
```

**KPI row + detail area:**
```
[Scoreboard w:3] [Scoreboard w:3] [Scoreboard w:3] [Scoreboard w:3]
[View w:12, h:8]
```

---

## What views and dashboards cannot do

| Capability | Status | Workaround |
|---|---|---|
| Per-column time windows | Not supported | Create separate views |
| Bucket interval / rollup period | Not exposed | Server uses ~5-min buckets |
| Group-by / pivot rows | Not supported | Use Distribution view for grouping |
| Dynamic / symptom coloring | Not supported | Use HealthChart widget |
| Initial sort order in YAML | Not configurable | User sets in UI |
| Force chart type (bar vs line) | UI-persisted only | Default is line/area |
| Per-instance breakdown rows | Partial | Requires uniform instance layout |

---

## Quick reference: cross-reference syntax

| From → To | YAML syntax | Resolved by |
|---|---|---|
| View column → super metric | `supermetric:"<name>"` in `attribute:` | validate → `sm_<uuid>` |
| Dashboard → view | `view: "<name>"` | validate → view UUID |
| Dashboard → dashboard (interaction) | `from:` / `to:` local IDs | render → widget UUIDs |

---

## File locations

| What | Where |
|---|---|
| View/dashboard YAML | `content/views/`, `content/dashboards/` |
| Loader (dataclasses + parsing) | `vcfops_dashboards/loader.py` |
| Renderer (wire format emission) | `vcfops_dashboards/render.py` |
| Wire format spec | `context/wire-formats/view_column_wire_format.md` |
| Widget type survey | `context/api-surface/widget_types_survey.md` |
| Widget renderer scope | `context/api-surface/widget_renderer_scope.md` |
