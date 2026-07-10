# View column wire format — transformations, colors, unit scaling

## Research date and scope

- Date: 2026-04-11
- Agent: api-explorer
- Driving question: what does the VCF Ops content-zip / view-XML wire
  format look like for per-column metric transformations, per-column
  color thresholds, and per-column unit scaling on list views?
- Sources used (no lab traffic required — all evidence found in
  existing artifacts):
  - `knowledge/context/exports/working_views.xml` — prior lab export, 4828
    lines, 928 views' worth. Contains one hand-crafted view that
    happens to exercise `PERCENTILE`, `AVG`, and `TRANSFORM_EXPRESSION`.
  - `reference/references/brockpeterson_operations_dashboards/*.zip` — extracted
    to `/tmp/view_research/extracted_views/` during investigation.
    Three bundles examined: `Cluster Capacity Details v6.1`,
    `ESXi Host Capacity Details v6`, `VM Details v4.2` (from the VM
    Rightsizing Details v5 distribution), plus Environment Capacity v2.
  - `reference/references/AriaOperationsContent/**/*.zip` — extracted to
    `/tmp/view_research/aria_extracted/`. The
    `[Custom] Performance Datastore` view is a particularly rich
    threshold example.

**All three capabilities the operator asked for are supported by the
wire format. None require an unsupported/internal API.** Current
`vcfops_dashboards` can't express any of them because `ViewColumn`
has no fields for transformation, thresholds, percentile value, or
transform expression, and `_xml_attribute_item()` emits a view-level
transformation block for every column.

## Per-column transformations

### Wire format shape

Each column lives in `//Controls/Control[@type='attributes-selector']
/Property[@name='attributeInfos']/List/Item/Value` as a flat bag of
`<Property name="..." value="..."/>` elements. The transformation is
**inside the per-column `<Value>` block** (not on the attribute key,
not as a sibling of `<Value>`, not at the view level). Structure:

```xml
<Item>
  <Value>
    <Property name="objectType" value="RESOURCE"/>
    <Property name="attributeKey" value="cpu|usage_average"/>
    <Property name="preferredUnitId" value="percent"/>
    <Property name="isStringAttribute" value="false"/>
    <Property name="adapterKind" value="VMWARE"/>
    <Property name="resourceKind" value="VirtualMachine"/>
    <Property name="rollUpType" value="NONE"/>
    <Property name="rollUpCount" value="0"/>
    <Property name="transformations">
      <List>
        <Item value="MAX"/>
      </List>
    </Property>
    <Property name="isProperty" value="false"/>
    <Property name="displayName" value="Max CPU Usage (6 months)"/>
    ...
  </Value>
</Item>
```

The `transformations` Property holds a `<List>` of `<Item value="..."/>`
children. In all observed per-column use, the list has **exactly one
item**. Multi-item lists are only used at the view level for trend
views (`NONE` + `TREND` + `FORECAST` stacked together).

The transformation applies to the column. The **time window over
which the transformation evaluates is view-wide**, encoded in a
separate `time-interval-selector` control at the top of the
`<Controls>` block:

```xml
<Control id="time-interval-selector_id_1011" type="time-interval-selector" visible="false">
  <Property name="advancedTimeMode" value="false"/>
  <Property name="unit" value="MONTHS"/>
  <Property name="count" value="6"/>
</Control>
```

So "Max CPU over 6 months" = column with `transformations=[MAX]` + view
with `time-interval-selector` set to MONTHS/6. All aggregated columns
in a view share the same window. The `unit` enum values observed in
this control include at least `MONTHS`; VCF Ops UI also supports
`DAYS`, `HOURS`, `WEEKS`, `YEARS` for the time-interval-selector (not
yet seen in a captured export, but the UI exposes them — treat them
as valid for loader input and pass through verbatim).

### Supported function enum values (full observed list)

From `working_views.xml` + brockpeterson + AriaOperationsContent extracts
plus ops-recon against live 13.6 MB export (2026-05-27):

| Value | Meaning | Notes |
|---|---|---|
| `CURRENT` | Latest sample | Default for list views. Ignores time window. |
| `NONE` | Raw data points | Trend/distribution views, stacked with TREND/FORECAST. |
| `AVG` | Average over window | Per-column use: `working_views.xml:2610`. |
| `MAX` | Max over window | Per-column use: `VM_Details_v4.2/content.xml:316, 460`. |
| `MIN` | Minimum over window | 15 uses confirmed in live export. Analogous to MAX, no extra sibling properties. |
| `SUM` | Sum over window | 59 uses confirmed in live export. Analogous to AVG/MAX, no extra sibling properties. |
| `LAST` | Most-recent stored sample | 138 uses confirmed in live export. Distinct from CURRENT: CURRENT is the latest polled value; LAST is the most recent stored data-point in the time series. No extra sibling properties. |
| `PERCENTILE` | Nth percentile over window | Requires sibling `<Property name="percentile" value="N"/>` where N is an integer 1..99. See `working_views.xml:2562, 2568`. |
| `TIMESTAMP` | Display value as a timestamp | 24 uses confirmed. Typically on property columns (`isProperty=true`) e.g. `config|createDate`. No extra sibling properties. |
| `TIME_POINT` | Timestamp when related metric hit its extreme | 12 uses confirmed. Requires THREE sibling properties — see below. |
| `TREND` | Trend line | Trend/distribution views only, stacked. |
| `FORECAST` | Forecast projection | Trend views only, stacked, requires `forecastDays` on each column. |
| `TRANSFORM_EXPRESSION` | Arbitrary formula | Requires sibling `<Property name="transformExpression" value="<expr>"/>`. See `working_views.xml:4070, 4076`. Expression is a formula evaluated server-side where `avg` is the bound symbol for the column's rolled-up value. |

**Confirmed absent from live export (zero hits in 13.6 MB):** `STDDEV`,
`HIGH_WATER_MARK`. Do not add these to the whitelist without fresh recon.

### TIME_POINT sibling properties

When `transformation == TIME_POINT`, three additional sibling `<Property>`
elements must appear **before** the `transformations` block:

```xml
<Property name="metricToRelateWith" value="cpu|capacity_contentionPct"/>
<Property name="localizedMetricToRelateWith" value="CPU Contention (%)"/>
<Property name="operatorToRelateWith" value="MAX"/>
<Property name="transformations">
  <List><Item value="TIME_POINT"/></List>
</Property>
```

- `metricToRelateWith` — the metric key whose extreme this column timestamps.
- `localizedMetricToRelateWith` — display label for that metric.
- `operatorToRelateWith` — `MAX` or `MIN` (which extreme to find).

In YAML:

```yaml
- attribute: summary|createDate
  display_name: "Time of Max CPU Contention"
  transformation: TIME_POINT
  metric_to_relate_with: "cpu|capacity_contentionPct"
  localized_metric_to_relate_with: "CPU Contention (%)"
  operator_to_relate_with: MAX
```

### Example XML from real files

- **PERCENTILE** — `knowledge/context/exports/working_views.xml:2542-2584`

  ```xml
  <Item>
    <Value>
      <Property name="objectType" value="RESOURCE"/>
      <Property name="attributeKey" value="cpu|usagemhz_average"/>
      <Property name="preferredUnitId" value="auto"/>
      <Property name="isStringAttribute" value="false"/>
      <Property name="adapterKind" value="VMWARE"/>
      <Property name="resourceKind" value="ClusterComputeResource"/>
      <Property name="rollUpType" value="NONE"/>
      <Property name="rollUpCount" value="0"/>
      <Property name="percentile" value="95"/>
      <Property name="transformations">
        <List><Item value="PERCENTILE"/></List>
      </Property>
      <Property name="isProperty" value="false"/>
      <Property name="displayName" value="95th %"/>
      ...
    </Value>
  </Item>
  ```

  Note the `percentile` Property appears **before** the
  `transformations` Property. Order of Property siblings inside the
  `<Value>` block probably doesn't matter to the parser, but
  consistent order matches exported files.

- **TRANSFORM_EXPRESSION** — `knowledge/context/exports/working_views.xml:4050-4090`

  ```xml
  <Property name="attributeKey" value="Super Metric|sm_a747b3d3-..."/>
  ...
  <Property name="transformExpression" value="avg * 100"/>
  <Property name="transformations">
    <List><Item value="TRANSFORM_EXPRESSION"/></List>
  </Property>
  ```

  The expression syntax is the server-side post-processing formula.
  `avg` is the column's rolled-up value (what the aggregator would
  have produced without the expression). Operators confirmed working:
  `*`, `/`, `+`, `-`, parentheses, integer literals, float literals.
  This is the **single mechanism for per-column unit scaling** (see
  §Per-column unit scaling below) and also the way to do things
  like "CPU headroom = 100 - avg".

- **MAX over 6 months** —
  `/tmp/view_research/extracted_views/VM_Details_v4.2/content.xml:312-318`

  ```xml
  <Property name="transformations">
    <List><Item value="MAX"/></List>
  </Property>
  ```

  Plus view-level `<Control type="time-interval-selector">` with
  `unit="MONTHS"` `count="6"`.

### Implementation notes for tooling

- Add `transformation: str = "CURRENT"` to `ViewColumn` (default
  matches today's behavior — `CURRENT` for list views).
- Add `percentile: int | None = None` to `ViewColumn`. Require
  `1 <= percentile <= 99` and `transformation == "PERCENTILE"` when
  set (validator should reject `percentile=95, transformation=AVG`).
- Add `transform_expression: str | None = None` to `ViewColumn`.
  When set, force `transformation="TRANSFORM_EXPRESSION"` (loader
  can auto-set it so authors don't have to write both).
- In `_xml_attribute_item()`, drop the view-level
  `_xml_transformations_block(view)` call and emit a **per-column**
  transformations block derived from `col.transformation` (or the
  view-level list if `view.data_type == "trend"` and the column
  doesn't override — trend views need the stacked
  `[NONE, TREND, FORECAST]` list). Insert
  `<Property name="percentile" ...>` or
  `<Property name="transformExpression" ...>` **before** the
  transformations Property, matching exported order.
- Add a view-level `time_window:` block (optional): `{unit: MONTHS,
  count: 6}`. If any column uses `MAX`/`AVG`/`PERCENTILE`/
  `TRANSFORM_EXPRESSION` and no `time_window` is set, validator
  should warn (the columns will aggregate over the default window,
  which is the view's configured "last N units" — often 24 hours
  — and that may not be what the author meant). Render as a
  `time-interval-selector` Control inside `<Controls>`.
- Whitelist accepted transformation values at load:
  `{CURRENT, NONE, AVG, MAX, MIN, SUM, LAST, PERCENTILE, TIMESTAMP,
  TIME_POINT, TREND, FORECAST, TRANSFORM_EXPRESSION}`. Reject anything
  else with a clear error pointing at this doc.

## Per-column color thresholds

### Wire format shape

Per-column color thresholds are encoded as three sibling Property
elements inside the column's `<Value>` block, plus a direction flag:

```xml
<Property name="yellowBound" value="70"/>
<Property name="orangeBound" value="80"/>
<Property name="redBound"    value="90"/>
<Property name="ascendingRange" value="false"/>
```

- `yellowBound`, `orangeBound`, `redBound` — the three breakpoint
  values as strings. They are parsed as floats for numeric columns
  but can be **literal strings** for property columns (see below).
- `ascendingRange` — boolean-as-string:
  - `false` → higher is worse. Yellow < orange < red. Values below
    `yellowBound` are neutral/green; values at or above `redBound`
    get the red cell background. Examples: CPU usage %, memory
    usage %, disk latency, error count.
  - `true` → lower is worse. Yellow > orange > red. Values above
    `yellowBound` are neutral/green; values at or below `redBound`
    get the red cell background. Examples: free capacity %, free
    memory headroom, availability %.

The order of bounds relative to `ascendingRange` is:

| `ascendingRange` | Direction | Example bounds |
|---|---|---|
| `false` | Higher is worse | yellow=70, orange=80, red=90 |
| `true`  | Lower is worse  | yellow=30, orange=20, red=10 |

The three bands are hard-coded — there is no `greenBound` and no
knob for more than three bands. The color enum is fixed: green
(implicit), yellow, orange, red. This matches the Scoreboard widget
semantics. **There is no concept of dynamic/symptom-driven coloring
on list view columns** — the bounds are static literal values
baked into the XML. Operators who need dynamic coloring (e.g.,
colored based on a HT symptom) have to use a widget, not a list
view column.

**String thresholds.** When the column is a property (not a metric),
`redBound` can hold a literal string value. Observed examples:

- `redBound="Powered Off"` on `summary|runtime|powerState`
  (ESXi_Host_Capacity_Details_v6:154)
- `redBound="inMaintenance"` on `summary|runtime|connectionState`
  (ESXi_Host_Capacity_Details_v6:196)
- `redBound="false"` on boolean properties
  (ESXi_Host_Capacity_Details_v6:434, 476)

For string-valued bounds: only `redBound` is set in the examples
(the other bounds are omitted entirely, not set to empty). Semantics
are "cell is red if value equals `redBound`, neutral otherwise".
The `ascendingRange` Property is irrelevant for string matches and
is not emitted on these columns.

#### ascending_range derivation (reverse-parser)

Some source XMLs omit `ascendingRange` even when all three numeric bounds are
present (observed in vCommunity View - Set 3.xml and View - Set 4.xml, 4 total
columns).  When the reverse parsers (`reverse.py` and `reverse_local.py`)
encounter this, they derive `ascending_range` from the bound ordering — the
same ordering that the forward renderer encodes and the loader's validation
check (line ~351) enforces:

| Bound ordering | Derived value | Semantics |
|---|---|---|
| `yellow < orange < red` | `False` | Higher is worse (CPU%, latency) |
| `yellow > orange > red` | `True` | Lower is worse (free capacity, headroom) |
| Ambiguous | `False` + WARN | Review reversed YAML |

This is the canonical reverse-parser rule.  If a third case surfaces
(e.g., non-strictly-ordered bounds), a UserWarning is emitted and the
default `False` is used; the YAML author should correct after review.

The bounds Property elements sit **after** `isProperty` and
**before** `displayName` in the observed emission order:

```xml
<Property name="isProperty" value="false"/>
<Property name="yellowBound" value="70"/>
<Property name="orangeBound" value="80"/>
<Property name="redBound" value="90"/>
<Property name="ascendingRange" value="false"/>
<Property name="displayName" value="CPU Used after vSphere HA"/>
```

### Example XML from real files

- **Three-band numeric, higher-is-worse** —
  `/tmp/view_research/extracted_views/Cluster_Capacity_Details_v6.1/content.xml:170-216`

  ```xml
  <Property name="attributeKey" value="Super Metric|sm_8f1a8..."/>
  ...
  <Property name="transformations"><List><Item value="CURRENT"/></List></Property>
  <Property name="isProperty" value="false"/>
  <Property name="yellowBound" value="70"/>
  <Property name="orangeBound" value="80"/>
  <Property name="redBound" value="90"/>
  <Property name="ascendingRange" value="false"/>
  <Property name="displayName" value="CPU Used after vSphere HA"/>
  ```

- **Three-band numeric, lower-is-worse** —
  `Cluster_Capacity_Details_v6.1/content.xml:220-266`

  ```xml
  <Property name="yellowBound" value="30"/>
  <Property name="orangeBound" value="20"/>
  <Property name="redBound" value="10"/>
  <Property name="ascendingRange" value="true"/>
  <Property name="displayName" value="CPU Free after vSphere HA"/>
  ```

- **Sub-integer floats** —
  `Cluster_Capacity_Details_v6.1/content.xml:520-524`
  ```xml
  <Property name="yellowBound" value=".1"/>
  <Property name="orangeBound" value=".2"/>
  <Property name="redBound" value="1"/>
  ```
  (parsed as floats by the server; leading decimal point works)

- **String-valued red bound, no yellow/orange** —
  `ESXi_Host_Capacity_Details_v6/content.xml:148-158`
  ```xml
  <Property name="isProperty" value="true"/>
  <Property name="redBound" value="Powered Off"/>
  ```

- **MAX-aggregated column with thresholds on the aggregated value** —
  `/tmp/view_research/extracted_views/VM_Details_v4.2/content.xml:312-334`
  Confirms transformations and color bounds compose. The server
  applies the aggregation first, then colors the resulting cell
  value.

### Implementation notes for tooling

- Add four optional fields to `ViewColumn`:
  - `yellow_bound: str | float | None = None`
  - `orange_bound: str | float | None = None`
  - `red_bound: str | float | int | bool | None = None`
  - `ascending_range: bool | None = None`
- Coerce to string at render time. Floats like `0.1` become `"0.1"`;
  booleans become lowercase `"true"`/`"false"` (observed in
  ESXi_Host_Capacity_Details_v6 for `redBound="false"`).
- Validation rules:
  - If any of the three bounds is set, emit all set ones and
    `ascendingRange`. If only `red_bound` is set (string-match
    case), do NOT emit `ascendingRange`.
  - If all three numeric bounds are set, require `ascending_range`
    to be explicitly set (force the author to think about
    direction). The error message should cite the table above.
  - Warn if `ascending_range=false` and `yellow >= orange` or
    `orange >= red`; warn on the mirror case for `ascending_range=
    true`. These aren't server errors but they're authoring bugs.
- Emit the four properties between `isProperty` and `displayName`
  in the order: yellow, orange, red, ascendingRange (matches
  exports).
- Reuse the `MetricSpec` threshold vocabulary for consistency:
  `MetricSpec` already has `yellow_bound`/`orange_bound`/`red_bound`
  on widget metrics. The meanings are equivalent. Consider
  extracting a mixin so the two code paths share validation.

## Per-column unit scaling

### Wire format shape

**`preferredUnitId` DOES convert**, not just relabel. Evidence:

- `VM_Details_v4.2/content.xml:348-354` — attribute
  `config|hardware|memoryKB` with `preferredUnitId="gb"`. This is a
  raw KB integer property being displayed as GB on a widely-used
  community reference dashboard. If `preferredUnitId` were label-only
  this view would ship broken for everyone (displaying "67108864 GB"
  for a 64 GB VM). The fact that brockpeterson's bundle is usable
  means the server interprets the unit enum as a conversion target.
- `ESXi_Host_Capacity_Details_v6/content.xml:372-374` — attribute
  `hardware|memorySize` with `preferredUnitId="gb"`. Same pattern,
  different attribute.
- `Cluster_Capacity_Details_v6.1/content.xml:276-280` — attribute
  `cpu|usagemhz_average` with `preferredUnitId="ghz"`. MHz→GHz
  conversion (divide by 1000).

Observed `preferredUnitId` values in real exports:

| Value | Meaning |
|---|---|
| `auto` | Server picks a display unit automatically. Default for numeric columns. |
| `percent` | Display as percent. |
| `gb` | Gigabytes. Server converts from KB/MB/bytes. |
| `tb` | Terabytes. |
| `ghz` | Gigahertz. Server converts from Hz/KHz/MHz. |
| `none` | No unit label. Observed on dimensionless super metric columns (`working_views.xml:4058`). |
| `7004` | Numeric unit ID — custom / registered unit. Observed on `config|hardware|num_Cpu` (VM_Details_v4.2:50). The UI's unit catalog assigns numeric IDs to custom/named units; `7004` appears to be the "count" unit used for things like vCPU count. Treat as pass-through. |

The `preferredUnitId` string is the VCF Ops unit registry key. The
full enum is larger than the above — the UI exposes bytes/kb/mb/gb/
tb/pb, hz/khz/mhz/ghz, bit/kb/mb/gb, percent, ms/s/min/hour/day,
etc. Any string the UI accepts should work. The loader should pass
the value through verbatim without a whitelist (the server will
reject unknown IDs at import time with a clear error).

**There is no `scaleFactor`, `divisor`, `multiplier`, or `unitScale`
attribute on view columns.** I grepped every reference export plus
`working_views.xml` — those tokens don't appear. The server does
not accept a raw numeric scale on a column. The **two mechanisms**
for changing the displayed numeric value are:

1. `preferredUnitId` — for standard unit conversions (KB→GB,
   MHz→GHz, bytes→TB, etc.). Server does the math using its unit
   registry.
2. `TRANSFORM_EXPRESSION` with `transformExpression` — for
   arbitrary formulas (`avg * 100`, `avg / 1024`, `100 - avg`,
   etc.). The server evaluates the expression with `avg` bound to
   the column's rolled-up value.

### Example XML from real files

- **KB attribute displayed as GB** —
  `/tmp/view_research/extracted_views/VM_Details_v4.2/content.xml:342-360`

  ```xml
  <Item>
    <Value>
      <Property name="objectType" value="RESOURCE"/>
      <Property name="attributeKey" value="config|hardware|memoryKB"/>
      <Property name="preferredUnitId" value="gb"/>
      <Property name="isStringAttribute" value="false"/>
      <Property name="adapterKind" value="VMWARE"/>
      <Property name="resourceKind" value="VirtualMachine"/>
      <Property name="rollUpType" value="NONE"/>
      <Property name="rollUpCount" value="0"/>
      ...
    </Value>
  </Item>
  ```

  **This is the exact shape the operator needs** for the "Current
  Memory" column that currently ships in KB: point the column at
  `config|hardware|memoryKB` with `preferredUnitId="gb"` and the
  server does the conversion. No SM needed.

- **Transform expression doing arithmetic conversion** —
  `knowledge/context/exports/working_views.xml:4052-4080`

  ```xml
  <Property name="attributeKey" value="Super Metric|sm_a747..."/>
  <Property name="preferredUnitId" value="none"/>
  ...
  <Property name="transformExpression" value="avg * 100"/>
  <Property name="transformations"><List><Item value="TRANSFORM_EXPRESSION"/></List></Property>
  ```

  This column takes a super metric that's a 0.0–1.0 ratio and
  displays it as a 0–100 percent, via server-side math.

### Implementation notes for tooling

- `ViewColumn.unit` already maps to `preferredUnitId`. No change
  needed to the field itself — but the authoring guide in
  `context/supermetric_authoring.md` /
  `context/chart_widget_formats.md` should call out that setting
  `unit: "gb"` on a KB attribute **converts, not just relabels**.
  Today nobody's using this because the authoring prompt doesn't
  tell author agents it's available.
- The new `transform_expression: str` field (proposed above under
  transformations) covers the scale-factor case for attributes that
  don't fit a registry-unit conversion. Document the `avg` binding
  and the supported operators (`*`, `/`, `+`, `-`, `(`, `)`, numeric
  literals) in the authoring prompt so authors don't try to use
  variable names or function calls.
- **No new scale/divisor field on `ViewColumn` is needed or
  possible.** The wire format does not support one. If an author
  reaches for a scale field, redirect them to one of the two
  mechanisms above.
- Fix the operator's immediate complaint: the capacity view's
  "Current Memory" column should be emitted with
  `attributeKey="config|hardware|memoryKB"` and `unit="gb"`. No SM
  arithmetic required, and the result stays consistent with the
  SM-driven Target Memory columns that already divide in their
  formulas.

## displayName and localizationKey

**Real exports do NOT carry a `localizationKey` attribute on the `displayName`
Property.** This was confirmed by exhaustive grep across every brockpeterson
reference pack (80+ inner zips) and the AriaOperationsContent extracts: every
reference uses the plain form:

```xml
<Property name="displayName" value="CPU Demand Max"/>
```

Never:

```xml
<Property localizationKey="..." name="displayName" value="CPU Demand Max"/>
```

The factory renderer formerly emitted `localizationKey` derived from the
metric attribute key (e.g. `cpu_demandPct`), which caused a three-way
collision when the same metric appeared in AVG, MAX, and P95 columns — all
three shared `localizationKey="cpu_demandPct"`, making them indistinguishable
in any environment that resolves the key over the value attribute.

The factory's `content.properties` files are shipped empty, so the key never
resolved to anything in practice. The fix (2026-06-10, Codex P2 / PR #15
finding): drop `localizationKey` from `displayName` entirely, matching real
exports. The `_attribute_to_localization_key()` helper in `render.py` is now
unreferenced on this code path (it still applies to `<Title>` and
`<Description>` at view level, which use static `"title"` / `"desc"` keys
that do not collide).

## Limitations

Things VCF Ops does NOT support on list view columns, documented so
authors don't try to express them:

1. **Per-column time windows.** The time window (`MONTHS/6` etc.)
   is view-wide via `time-interval-selector`. A single view cannot
   have "Max CPU over 6 months" and "Avg CPU over 1 day" in
   different columns — they'd both evaluate against the same window.
   Workaround: two separate views.
2. **Dynamic / symptom-driven coloring.** Bounds are static literal
   values. A column cannot color based on a HT symptom firing.
   Workaround: use a health/badge column, or put the data in a
   widget that supports symptom visualization.
3. **More than three color bands.** Fixed at yellow/orange/red +
   implicit green. No custom band count, no gradient.
4. **`greenBound`.** Doesn't exist. Values better than `yellowBound`
   (in the direction set by `ascendingRange`) are uncolored.
5. **Arbitrary scaleFactor/divisor on a column without an
   expression.** You need either `preferredUnitId` (for registry
   conversions) or `TRANSFORM_EXPRESSION` (for custom math). There's
   no shorthand.
6. **Named variables in `transformExpression`.** Only `avg` is
   bound. You can't reference another column's value, another
   metric, or a constant by name. It's strictly a scalar → scalar
   post-process of the column's own rolled-up value.
7. **Multi-aggregation columns.** The `transformations` List holds
   exactly one aggregation per column for list views. The
   multi-item list pattern (`[NONE, TREND, FORECAST]`) is only
   used by trend-presentation views where all items apply together
   to the same metric for different chart overlays.

## Tooling recommendation

Concrete changes for the `tooling` agent to make:

### `src/vcfops_dashboards/loader.py::ViewColumn`

Add fields (all optional, all default to current behavior):

```python
@dataclass
class ViewColumn:
    attribute: str
    display_name: str
    unit: str = ""                         # preferredUnitId (already present)
    # NEW:
    transformation: str = "CURRENT"        # CURRENT|NONE|AVG|MAX|PERCENTILE|TREND|FORECAST|TRANSFORM_EXPRESSION
    percentile: int | None = None          # required when transformation == PERCENTILE, 1..99
    transform_expression: str | None = None  # required when transformation == TRANSFORM_EXPRESSION
    yellow_bound: str | float | None = None
    orange_bound: str | float | None = None
    red_bound:    str | float | int | bool | None = None
    ascending_range: bool | None = None    # required when >=2 numeric bounds set
```

Add a view-level optional block (matches `time-interval-selector`):

```python
@dataclass
class ViewTimeWindow:
    unit: str   # MONTHS|WEEKS|DAYS|HOURS|MINUTES|YEARS
    count: int  # positive integer

@dataclass
class ViewDef:
    ...
    time_window: ViewTimeWindow | None = None
```

Validation rules in `loader.py`:

- Whitelist `transformation` against the 8 known values; reject
  others with a message pointing at `context/view_column_wire_format.md`.
- If `transformation == "PERCENTILE"`, require `1 <= percentile <= 99`.
  Reject `percentile` set on any other transformation.
- If `transformation == "TRANSFORM_EXPRESSION"`, require
  `transform_expression` non-empty. Conversely, if
  `transform_expression` is set, force `transformation =
  "TRANSFORM_EXPRESSION"` (convenience).
- If any aggregating transformation is used (`AVG`, `MAX`,
  `PERCENTILE`, `TRANSFORM_EXPRESSION`) on any column, warn if
  `view.time_window` is unset.
- If the column has numeric bounds (`yellow_bound`, `orange_bound`,
  and `red_bound` all numeric), require `ascending_range`
  explicitly. If only `red_bound` is set and is a string/bool,
  `ascending_range` must NOT be set.
- Warn on inverted band ordering (`ascending_range=false` with
  `yellow >= orange` or `orange >= red`; mirror for `true`).

### `src/vcfops_dashboards/render.py::_xml_attribute_item()`

1. Drop the view-level `_xml_transformations_block(view)` call
   unless `view.data_type == "trend"` (the stacked
   NONE/TREND/FORECAST list is still view-level for trend views).
2. For list/distribution views, emit a per-column transformations
   block built from `col.transformation`:
   ```python
   def _xml_column_transformation(col: ViewColumn) -> str:
       return (
           f'<Property name="transformations">'
           f'<List><Item value="{col.transformation or "CURRENT"}"/></List>'
           f'</Property>'
       )
   ```
3. When `col.percentile is not None`, emit
   `<Property name="percentile" value="{N}"/>` **before** the
   transformations Property (matches exported order).
4. When `col.transform_expression` is set, emit
   `<Property name="transformExpression" value="{escaped}"/>`
   before the transformations Property. Escape `&`, `<`, `>`,
   `"` using the existing property-value escaping path.
5. After the existing `isProperty` Property and before
   `displayName`, emit any set threshold properties in the
   order yellow, orange, red, ascendingRange. Coerce values to
   strings (`True`→`"true"`, floats via `str()`, ints via
   `str()`).
6. Add a new helper `_xml_time_interval_selector(view)` that emits
   the `time-interval-selector` Control at the top of `<Controls>`
   when `view.time_window` is set:
   ```xml
   <Control id="time-interval-selector_id_{N}" type="time-interval-selector" visible="false">
     <Property name="advancedTimeMode" value="false"/>
     <Property name="unit"  value="{window.unit}"/>
     <Property name="count" value="{window.count}"/>
   </Control>
   ```
7. The `rollUpType` emitted for metric attributes is currently
   `"AVG"` (fallback path line 127). Per-column transformation
   authors probably want this to stay `"AVG"` (the time-bucket
   rollup is independent of the column-level aggregation — the
   server rolls each 5-minute window to AVG, then the column
   aggregation computes AVG/MAX/PERCENTILE of those 5-min
   averages). Do not change `rollUpType` as part of this work.

## Instanced-group columns (`isInstancedGroup` / `instanceGroupName`)

- Date: 2026-07-09
- Agent: tooling (`feat/view-instanced-group-columns`)
- Driving question: how does a view column select an attribute across
  ALL instances of a colon-syntax metric group — one row/column set
  per instance — rather than a single hardcoded instance?
- Sources (RULE-016, read-only vendor reference, no lab traffic
  required):
  - `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/ESXi Host License Information vCommunity.xml`
    (licensing, `vCommunity|Licensing:<name>|*`)
  - `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/ESXi Packages.xml`
    (packages, `vCommunity|Configuration|Packages:<name>|*`)
  - `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/Windows Services vCommunity.xml`
    (guest services, `vCommunity|Guest OS|Services:<name>|*`)
  - `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/View - Set 3.xml`
    and `View - Set 4.xml` — VMware's own built-in instanced groups
    (`GROUP_net`, `GROUP_cpu`, `GROUP_disk`, `GROUP_diskio`,
    `GROUP_config`, `GROUP_storageAdapter`, `GROUP_diskspace`,
    `GROUP_virtualDisk`, `GROUP_host`, `GROUP_guestfilesystem`),
    surveyed to confirm the construct's shape is not vCommunity-specific.

### Wire format shape

The first `Item` in `attributeInfos/List` is a "driver" column that turns
on instanced-group mode for the whole view. It carries a literal sentinel
`attributeKey`, not a real metric/property key:

```xml
<Item><Value>
  <Property name="objectType" value="RESOURCE"/>
  <Property name="attributeKey" value="Instance Name"/>
  <Property name="rollUpCount" value="0"/>
  <Property name="isInstancedGroup" value="true"/>
  <Property name="showInstanceName" value="true"/>
  <Property name="instanceGroupName" value="GROUP_vCommunity"/>
  <Property name="keepInstanceSummary" value="true"/>
  <Property name="displayName" value="Instance"/>  <!-- omitted in the
       License view, present in Packages/Windows Services — both
       accepted, so the factory always emits it -->
</Value></Item>
```

Every subsequent Item is a normal-looking column whose `attributeKey`
embeds one *representative* instance name in the colon segment:

```xml
<Property name="attributeKey" value="vCommunity|Licensing:Evaluation Mode|Edition Key"/>
```

Pattern: `<group-prefix>:<sample-instance>|<attribute-suffix>`. VCF Ops
expands this into one row per instance actually present on the resource
at render time — the embedded instance name is a *sample* used to
identify the `prefix`+`suffix` pattern, not a filter that restricts
rendering to only that one instance.

`instanceGroupName` (`GROUP_vCommunity`) is the **same literal string**
for every one of the vCommunity pak's own user-defined instanced groups
(Licensing, Packages, Guest OS Services) despite them being unrelated
metric families — confirmed identical across all three cited files.
VMware's built-in instanced groups use distinct per-family tokens
(`GROUP_net`, `GROUP_cpu`, ...). This strongly suggests `instanceGroupName`
is closer to a UI label / opaque grouping token than a server-validated
enum keyed to the metric family — but this was not confirmed against a
live instance. Treat it as an author-supplied opaque string; the loader
does not validate it against a known set.

### Member column property emission — differs from generic columns

Property member columns (`isProperty=true`) **omit `rollUpType`
entirely**; metric member columns (`isProperty=false`) carry
`rollUpType="NONE"` **unconditionally, regardless of transformation**
(not the generic renderer's `"AVG"` fallback for non-CURRENT
transforms — see the non-CURRENT-transformations subsection below for
the evidence). Order otherwise matches the generic column shape:
objectType, attributeKey, isStringAttribute, adapterKind, resourceKind,
[rollUpType], rollUpCount="0" (not "1" — differs from the generic
default), [transformExpression], transformations, isProperty, [color
bounds], displayName, addTimestampAsColumn, isShowRelativeTimestamp.

**AMBIGUITY (not resolved here):** whether the rollUpType omission for
property columns is specific to instanced-group columns, or a broader
vCommunity-pak-wide convention. `ESXi Host Details vCommunity.xml:44-76`
shows the same omission on a **non-instanced** property column
(`Install Date|UTC`), which suggests the latter — but this was out of
scope for the instanced-group capability and was not investigated
further. The factory's generic (non-instanced) column renderer
(`_xml_attribute_item`) was deliberately left untouched; only the new
`_xml_instanced_group_item()` path mirrors this vendor behavior, scoped
to instanced-group columns only. If a future port needs the generic
renderer to match this pattern too, that's a separate change — flag to
api-explorer for live confirmation first.

### Non-CURRENT transformations on member columns (2026-07-10 follow-up)

- Date: 2026-07-10
- Agent: tooling (Codex P2 review finding on PR #46)
- Driving question: the original instanced-group implementation only
  emitted the `transformations` list for member columns, with no
  companion sibling properties. The generic (non-instanced) column path
  emits `percentile` (before `transformations`) for `PERCENTILE`,
  `transformExpression` (before `transformations`) for
  `TRANSFORM_EXPRESSION`, and three sibling properties for `TIME_POINT`.
  Does any vendor instanced-group member column actually use a
  transformation that needs one of these companions — and if so, what's
  the wire shape?

**Method:** parsed every `<ViewDef>` in every `reference/references/vmbro_*/
**/content/reports/*.xml` file, found every `attributes-selector` Control
whose `attributeInfos` List contains an `isInstancedGroup=true` driver
Item, and inspected every *other* Item in that same List (i.e. every
member column of an actual instanced-group view) for its
`transformations` value and any companion sibling properties.

**Findings:**

- **MAX, TRANSFORM_EXPRESSION, TIMESTAMP: vendor evidence found.**
  `View - Set 4.xml` (same `vmbro_vcf_operations_vcommunity` pak as the
  three files already cited above) bundles several further
  instanced-group views beyond Licensing/Packages/Guest OS Services:
  - `"Windows CPU Usage"` — member `cpu:0|Percent.DPC.Time`,
    `transformations=[MAX]`, `rollUpType="NONE"`, plus
    `yellowBound`/`orangeBound`/`redBound`/`ascendingRange` color bounds
    (a shape this renderer already supported before this follow-up).
  - `"Linux Disk Performance"` — member `diskio:dm-0|read.time`,
    `transformations=[TRANSFORM_EXPRESSION]`, with
    `<Property name="transformExpression" value="(current-first)/60000"/>`
    emitted as a sibling **immediately before** the `transformations`
    Property (same ordering as the generic column path),
    `rollUpType="NONE"`.
  - `"VM Snapshots List"` — member
    `diskspace:262|snapshot:snapshot-1|accessTime`,
    `transformations=[TIMESTAMP]`, `rollUpType="NONE"`, no extra sibling
    properties (matches the generic path's TIMESTAMP handling — "No
    extra sibling properties" per the enum table above).
  All three examples confirmed `rollUpType="NONE"` — same as every
  `CURRENT`-transform instanced member column already documented. This
  **contradicts** the original implementation's `"AVG"` fallback for
  non-CURRENT/NONE transforms on instanced member columns (that fallback
  was never vendor-evidenced; it has been removed — `rollUpType="NONE"`
  is now unconditional for non-property instanced member columns,
  regardless of transformation).
- **PERCENTILE, TIME_POINT: no vendor evidence found**, despite both
  transformations appearing on plenty of *non*-instanced columns in the
  same files (`View - Set 2.xml`/`View - Set 3.xml`/`View - Set 4.xml`
  all contain `PERCENTILE` Items; none are inside an
  `isInstancedGroup`-bearing attributes-selector alongside a member
  column). Per the framework's no-silent-downgrade posture,
  `ViewDef._validate_column` now **rejects** `PERCENTILE` and
  `TIME_POINT` on `instanced_group` member columns (not the driver —
  driver columns never render a transformation) with a pointer to this
  section. If a live/vendor example of either surfaces later, route to
  api-explorer to confirm the wire shape before lifting the rejection.

Implementation: `src/vcfops_dashboards/render.py::_xml_instanced_group_item`
(emission + docstring citations) and
`src/vcfops_dashboards/loader.py::ViewDef._validate_column` (rejection).
Tests: `tests/test_view_instanced_group_columns.py`
(`TestInstancedGroupMemberTransformEmission`,
`TestInstancedGroupMemberUnprovenTransformationsRejected`).

**Separate finding, NOT fixed here (documented per hard rule, out of
scope for this follow-up):** the same three `View - Set 4.xml` examples
above also carry `<Property name="preferredUnitId" value="percent|min|
auto"/>` on their member columns (right after `attributeKey`, matching
the generic path's ordering) — `_xml_instanced_group_item()` does not
emit `preferredUnitId` at all (`ViewColumn.unit` is read by the generic
path but ignored by the instanced-group path). This is unrelated to the
Codex P2 companion-fields finding (it's not transformation-dependent —
even the CURRENT-transform vendor examples in this file could plausibly
carry a unit) and was left alone to keep this fix scoped. Flag for a
future tooling pass if an instanced-group column needs unit display.

### Factory YAML syntax

```yaml
columns:
  - display_name: "Instance"
    instanced_group:
      name: "GROUP_vCommunity"          # -> instanceGroupName (opaque token)
      show_instance_name: true          # default true
      keep_instance_summary: true       # default false
      # no prefix/suffix => this is the driver column

  - display_name: "Edition"
    is_property: true
    is_string_attribute: true
    instanced_group:
      name: "GROUP_vCommunity"          # must match a driver's name in this view
      prefix: "vCommunity|Licensing"    # group prefix before ":"
      suffix: "Edition Key"             # attribute name after "<instance>|"
      sample_instance: "Evaluation Mode"  # required, no default — see below
```

Implementation: `src/vcfops_dashboards/loader.py` (`InstancedGroupSpec`,
`ViewColumn.instanced_group`, `_load_column` synthesis, `ViewDef.validate`
driver cross-check) and `src/vcfops_dashboards/render.py`
(`_xml_instanced_group_item`).

### Loader validation

- A column with `instanced_group` set must NOT also set `attribute`
  (hardcoding a literal attributeKey defeats the abstraction and is
  exactly the bug this capability fixes — see the shipped-but-broken
  `content/sdk-adapters/vcommunity-vsphere/views/ESXi Host License
  Information vCommunity.yaml`, which hardcodes
  `vCommunity|Licensing:Evaluation Mode|*` in every column with no
  `isInstancedGroup` driver at all).
- `prefix` and `suffix` must both be set (member column) or both unset
  (driver column) — one without the other is rejected.
- Member columns require `sample_instance` — no default is synthesized.
  This is a deliberate "require, don't guess" choice per CLAUDE.md's
  no-silent-downgrade posture: whether the sample value affects server
  behavior is unverified (see AMBIGUITY above), so the loader forces
  the author to make the choice explicitly and visibly in YAML/review
  rather than picking an arbitrary placeholder.
- Every member column's `instanced_group.name` must match a driver
  column present in the same view, or validation fails with a
  pointer to add the driver.

### `context/` updates the tooling agent should also make

- Cross-link this file from `context/chart_widget_formats.md` (which
  documents widget-level color thresholds) so the two color-threshold
  systems are discoverable from each other.
- Update `context/supermetric_authoring.md` and the
  `view-author` / `dashboard-author` agent prompts to mention that
  `preferredUnitId="gb"` on a KB attribute CONVERTS — do not
  author an SM just to divide by 1024.
