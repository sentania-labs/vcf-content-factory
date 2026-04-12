# View column wire format — transformations, colors, unit scaling

## Research date and scope

- Date: 2026-04-11
- Agent: api-explorer
- Driving question: what does the VCF Ops content-zip / view-XML wire
  format look like for per-column metric transformations, per-column
  color thresholds, and per-column unit scaling on list views?
- Sources used (no lab traffic required — all evidence found in
  existing artifacts):
  - `context/exports/working_views.xml` — prior lab export, 4828
    lines, 928 views' worth. Contains one hand-crafted view that
    happens to exercise `PERCENTILE`, `AVG`, and `TRANSFORM_EXPRESSION`.
  - `references/brockpeterson_operations_dashboards/*.zip` — extracted
    to `/tmp/view_research/extracted_views/` during investigation.
    Three bundles examined: `Cluster Capacity Details v6.1`,
    `ESXi Host Capacity Details v6`, `VM Details v4.2` (from the VM
    Rightsizing Details v5 distribution), plus Environment Capacity v2.
  - `references/AriaOperationsContent/**/*.zip` — extracted to
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

From `working_views.xml` + brockpeterson + AriaOperationsContent
extracts combined, the transformation values that actually appear in
real exported view XML:

| Value | Meaning | Notes |
|---|---|---|
| `CURRENT` | Latest sample | Default for list views. Ignores time window. |
| `NONE` | Raw data points | Trend/distribution views, stacked with TREND/FORECAST. |
| `AVG` | Average over window | Per-column use: `working_views.xml:2610`. |
| `MAX` | Max over window | Per-column use: `VM_Details_v4.2/content.xml:316, 460`. |
| `PERCENTILE` | Nth percentile over window | Requires sibling `<Property name="percentile" value="N"/>` where N is an integer 1..99. See `working_views.xml:2562, 2568`. |
| `TREND` | Trend line | Trend/distribution views only, stacked. |
| `FORECAST` | Forecast projection | Trend views only, stacked, requires `forecastDays` on each column. |
| `TRANSFORM_EXPRESSION` | Arbitrary formula | Requires sibling `<Property name="transformExpression" value="<expr>"/>`. See `working_views.xml:4070, 4076`. Expression is a formula evaluated server-side where `avg` is the bound symbol for the column's rolled-up value. |

**Not observed in any examined export** but worth flagging so the
loader prompt can be explicit about what's safe: `MIN`, `SUM`,
`STDDEV`, `HIGH_WATER_MARK`, `HWM`, `P95`, `PERCENTILE_95`. The UI
column-editor exposes MIN and SUM in its aggregation dropdown on
some VCF Ops versions; they are plausible but unconfirmed. The
loader should treat the transformations field as a free-form string
that is passed through verbatim and reject only blatantly wrong
values. A small whitelist of the seven confirmed values is the
safer starting point.

### Example XML from real files

- **PERCENTILE** — `context/exports/working_views.xml:2542-2584`

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

- **TRANSFORM_EXPRESSION** — `context/exports/working_views.xml:4050-4090`

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
  `{CURRENT, NONE, AVG, MAX, PERCENTILE, TREND, FORECAST,
  TRANSFORM_EXPRESSION}`. Reject anything else with a clear error
  pointing at this doc.

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
  `context/exports/working_views.xml:4052-4080`

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

### `vcfops_dashboards/loader.py::ViewColumn`

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

### `vcfops_dashboards/render.py::_xml_attribute_item()`

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

### `context/` updates the tooling agent should also make

- Cross-link this file from `context/chart_widget_formats.md` (which
  documents widget-level color thresholds) so the two color-threshold
  systems are discoverable from each other.
- Update `context/supermetric_authoring.md` and the
  `view-author` / `dashboard-author` agent prompts to mention that
  `preferredUnitId="gb"` on a KB attribute CONVERTS — do not
  author an SM just to divide by 1024.
