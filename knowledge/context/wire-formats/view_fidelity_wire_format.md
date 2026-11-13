# View schema fidelity: wire format and YAML (2026-11-12)

The view YAML fields that let an existing list, distribution or trend
ViewDef be expressed at full fidelity: the values the renderer used to fix
on every view, and the ViewDef features the schema could not express.
Code: `src/vcfcf_core/dashboards/loader.py` (`ViewColumn`, `ViewDef`,
`BucketsConfig`, `SubjectFilterCondition`) and
`src/vcfcf_core/dashboards/render.py`. Tests:
`tests/test_view_schema_fidelity.py`, `tests/test_view_column_sort.py`.
Companion docs: `view_column_wire_format.md` (columns, transformations,
bounds, units, instanced groups, subject filter) and
`dashboard_sort_color_default_summary_rows.md` (sort, summary rows).

## Contract

- **Every field is optional and its absence renders exactly what the
  renderer emitted before.** Proven by a byte-for-byte render of every view
  YAML in `content/views/`, `third_party/*/views/`, the registered paks'
  views and `tests/fixtures/views/` (plain and with the SDK owning-subject
  injection), plus 189 views written in the old schema by the base
  importer: identical before and after.
- **Two keys that existed before now render.** `count:` on a `dynamic:
  true` buckets block and `calc_function:` on a `dynamic: false` one were
  silently ignored by the old renderer; both now emit (`bucketCount`,
  `dynamicCalcFunction`), and fixed-mode `calc_function` must be
  `SIMPLEMAXMIN`. No YAML in the repo set either at the time of the
  change; a clone that does sees those two Properties appear. Nothing
  else changes for YAML that already existed.
- **A field the renderer cannot honour for that view type is a load
  error**, never ignored. So is a value no vendor export carries (for
  example `use_symptom_thresholds: true`), and so is an `omit:` entry that
  contradicts a field the YAML also sets.
- Column Items (attributeInfos and distributionAdditionalColumns) and the
  metadata control follow vendor Property order. The buckets-control keeps
  its historical order (`isDynamic` first; in dynamic mode `bucketCount`
  after `dynamicCalcFunction`), which differs from the vendor's
  (`dynamicCalcFunction, isDynamic, isSum`, `bucketCount` first in dynamic
  mode). Harmless: the product reads Properties by name.
- **SDK-adapter paks need a newer buildkit.** The buildkit vendors
  `loader.py` and `render.py`, and pak CI builds with the kit pinned by
  tag. Kit 1.0.28 and earlier carry the old loader, which rejects every
  field on this page, so a pak view that uses any of them fails pak CI
  until the pak pins a kit cut after this change.

## Evidence

Surveyed 2026-11-12, every ViewDef in three corpora: the 9.1.1 and 8.18.7
built-in view exports of clean labs (851 and 778 ViewDefs) and the
vCommunity 0.8.1 Python pak (189 unique ViewDefs). These three are
local-only artifacts, not reproducible from a fresh clone (the built-ins
come from a lab content export; the pak is third-party content under its
own license and is not copied here); the findings are summarized here in
full. Most features also appear in the registry-fetchable ancestor pak,
`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/`
(`View - Set 1..4.xml`, `View - Collection01.xml`): distributionAdditionalColumns,
bucketInfos, isSum, bucketCount, rollUpUnit, useSymptomThresholds,
SubjectsGroupBy, isShowRelativeTimestamp=true, listTopResultSize,
includeResourceCreationTime, distributionColor. `NOT_CONTAINS` and the
other widened filter comparators come from the built-in exports only.

Snippets below are composed for this doc; metric keys are generic VMWARE
keys, not copies of any one view.

## 1. Distribution views

### Additional columns (`additional_columns:`)

The extra columns a distribution view lists for the objects in a bucket.
They live in the **metadata** control, not the attributes-selector:

```xml
<Control id="metadata_id_1" type="metadata" visible="false">
  <Property name="maxPointsCount" value="5000"/>
  <Property name="hideObjectNameColumn" value="false"/>
  <Property name="listTopResultSize" value="-1"/>
  <Property name="includeResourceCreationTime" value="false"/>
  <Property name="distributionAdditionalColumns"><List>
    <Item><Value>
      <Property name="objectType" value="RESOURCE"/>
      <Property name="attributeKey" value="cpu|usage_average"/>
      <Property name="preferredUnitId" value="percent"/>
      <Property name="localizedAttributeName" value="CPU|Usage"/>
      <Property name="isStringAttribute" value="false"/>
      <Property name="adapterKind" value="VMWARE"/>
      <Property name="resourceKind" value="HostSystem"/>
      <Property name="rollUpType" value="NONE"/>
      <Property name="rollUpCount" value="0"/>
      <Property name="percentile" value="95"/>
      <Property name="transformations"><List><Item value="PERCENTILE"/></List></Property>
      <Property name="sortCriteria" value="true"/>
      <Property name="isProperty" value="false"/>
      <Property name="displayName" value="CPU at 95th"/>
      <Property name="isShowRelativeTimestamp" value="false"/>
    </Value></Item>
  </List></Property>
</Control>
```

```yaml
data_type: distribution
additional_columns:
  - attribute: cpu|usage_average
    display_name: CPU at 95th
    localized_name: CPU|Usage        # required: localizedAttributeName
    unit: percent
    transformation: PERCENTILE       # optional; no transformations Property when absent
    percentile: 95
    roll_up_type: NONE               # optional; no rollUpType when absent
    roll_up_count: 0                 # optional; default 0, the only vendor value
    sort: asc                        # optional
    show_relative_timestamp: false   # optional; no Property when absent
    is_property: false
    is_string_attribute: false
```

Rules: distribution views only. `localized_name` is required (every vendor
Item carries it; it is the metric's own label, never invent it, RULE-002).
No color bounds, ascending_range, transform expression, time-point
siblings, instanced group, time segment, column `subject:`, roll_up_unit,
use_symptom_thresholds or add_timestamp_as_column (none appear in the
vendor shape). `omit:` may only name `display_name` (one vendor Item has no
displayName). A super metric is named as `supermetric:"<name>"`, as in
`columns:`; the renderer resolves it to `Super Metric|sm_<uuid>` the same
way (no rollUpType is added; set `roll_up_type:` if the source has one).
The raw key (`Super Metric|sm_<uuid>`, any case, or any `sm_<uuid>`) is
a load error that points at the name form (cross-reference convention: by
name, never raw UUID). Every dependency walker and audit reads
`additional_columns` alongside `columns`: the build audit
(`packaging/deps.py`), the staged-bundle audit (`packaging/audit.py`, which
walks every column Item), the dependency walker (`common/dep_walker.py`:
live pre-flight, `supermetrics_used_by`, `collect_deps`), the discrete
release builder and the validate/sync column check
(`SmColumnResolver.column_problems`). So a super metric named only in an
additional column is bundled, and a typo'd built-in key there fails the
describe-cache audit. The source vCommunity 0.8.1 pak has one such column
(1 of 189 views). Column binding follows `columns:` (the view's kind on a
single-subject view).

### `distribution_color:`

```xml
<Property name="maxPointsCount" value="5000"/>
<Property name="distributionColor" value="37B3EB"/>
<Property name="hideObjectNameColumn" value="false"/>
```

`distribution_color: "37B3EB"`: six hex digits, quoted, no `#`. Emitted
only when set. Accepted on every view type: the product's own exports carry
it on list views too (137 of the 9.1.1 built-in list views), where it is
residue of the UI and has no visible effect.

## 2. Buckets

Historical shapes (unchanged): dynamic emits `isDynamic=true` and
`dynamicCalcFunction`; fixed emits `isDynamic=false`, `minValue`,
`maxValue`, `bucketCount`. The new fields only add Properties when set:

| YAML (under `buckets:`) | Wire | Notes |
|---|---|---|
| `ranges: [{start, end, color}]` | `bucketInfos` List, one Item of `startValue`, `endValue`, optional `bucketColor` | fixed mode only; renders `dynamicCalcFunction=SIMPLEMAXMIN` (every vendor `bucketInfos` pairs with it) and drops the implicit `bucketCount` (vendor shape) |
| `count:` in dynamic mode | `bucketCount` | emitted only when `count` is written; dynamic mode never emitted it before |
| `count:` with `ranges` | `bucketCount` | kept when written explicitly |
| `calc_function:` in fixed mode | `dynamicCalcFunction` | emitted only when written (vendor fixed controls carry it); only `SIMPLEMAXMIN` accepted |
| `is_sum: true\|false` | `isSum` | emitted only when set; vendor values true and false |

```xml
<Control id="buckets-control_id_1" type="buckets-control" visible="false">
  <Property name="isDynamic" value="false"/>
  <Property name="minValue" value="0.0"/><Property name="maxValue" value="0.0"/>
  <Property name="dynamicCalcFunction" value="SIMPLEMAXMIN"/>
  <Property name="bucketInfos"><List>
    <Item><Value><Property name="startValue" value="0"/><Property name="endValue" value="25"/>
      <Property name="bucketColor" value="74B43B"/></Value></Item>
    <Item><Value><Property name="startValue" value="25"/><Property name="endValue" value="100"/>
      <Property name="bucketColor" value="DE3F30"/></Value></Item>
  </List></Property>
  <Property name="isSum" value="false"/>
</Control>
```

```yaml
buckets:
  dynamic: false
  min_value: 0
  max_value: 0
  is_sum: false
  ranges:
    - {start: 0, end: 25, color: "74B43B"}
    - {start: 25, end: 100, color: "DE3F30"}
```

Rules: `ranges` needs `dynamic: false`; in fixed mode `calc_function`, if
written, must be `SIMPLEMAXMIN` (every fixed buckets-control in the three
corpora, 73 / 72 / 33, carries it and nothing else); each `start` below its
`end`, and the ranges ascending and non-overlapping (each `start` at or
above the previous `end`): every vendor `bucketInfos` list (68 / 67 / 29)
is, most contiguous, some with gaps, none overlapping or unordered;
numbers, not strings; `color` six hex digits. Ranges, `is_sum`, an explicit dynamic `count` or a
fixed `calc_function` on a non-distribution view is a load error. Integer
range bounds render integral (`25`, not `25.0`). Vendor calc functions
seen: DISCRETE, SIMPLEMAXMIN, LOGMAGNITUDE (one 9.1.1 view).

## 3. Sort

`sort: asc | desc` (sortCriteria true / false) is now accepted on:

- **several columns of one view**: the vendor shape (9.1.1 built-in list
  views carry up to 17 sortCriteria columns, most of them `false`).
  Which column takes precedence is the product's behaviour; unverified
  live.
- **distribution views**: on the attributes-selector column and on
  `additional_columns` entries (16 built-in and 14 vCommunity distribution
  views).
- **instanced-group driver columns**: `sortCriteria` sits right after
  `rollUpCount`, before `isInstancedGroup`:
  `<Property name="rollUpCount" value="0"/><Property name="sortCriteria" value="true"/><Property name="isInstancedGroup" value="true"/>`
- **instanced-group member columns**: same position as a generic column,
  after `transformations`, before `isProperty` (9.1.1 built-in instanced
  views).

Still rejected: sort on a **trend** view (no surveyed export carries
sortCriteria on a trend column) and any sort beside a `time_segment`
column (no export shows one).

## 4. Roll-up

```xml
<Property name="rollUpType" value="AVG"/>
<Property name="rollUpUnit" value="HOURS"/>
<Property name="rollUpCount" value="1"/>
```

| YAML (column) | Wire | Default when absent |
|---|---|---|
| `roll_up_type: AVG\|NONE` | `rollUpType` | generic: AVG, NONE for super metrics; instanced member: NONE, none on a property |
| `roll_up_unit: MINUTES\|HOURS\|DAYS\|WEEKS\|MONTHS` | `rollUpUnit`, between rollUpType and rollUpCount | not emitted |
| `roll_up_count: <int >= 0>` | `rollUpCount` | generic 1, instanced member 0 |
| `omit: [roll_up_type]` | no rollUpType | |

Vendor values: rollUpType AVG or NONE; rollUpUnit only beside
`rollUpType=AVG` (pairs seen: AVG/MINUTES/5, AVG/HOURS/1, AVG/DAYS/1,
AVG/WEEKS/1, AVG/MONTHS/1), so `roll_up_unit` requires an explicit
`roll_up_type: AVG`. Absent rollUpType is common: most property columns in
the vCommunity pak have none, which is what `omit: [roll_up_type]`
reproduces. Not accepted on an instanced-group driver or a time-segment
column (fixed wire shapes).

## 5. `use_symptom_thresholds`

`<Property name="useSymptomThresholds" value="false"/>` after the color
bounds and ascendingRange, before displayName. YAML
`use_symptom_thresholds: false`. Only `false` is accepted: it is the only
value in any surveyed export (four vCommunity columns, none in the
built-ins), so the effect of `true` is unknown.

## 6. Top N, page size, max points, resource creation time

| YAML (view) | Wire | Default | View types |
|---|---|---|---|
| `top_n: <int > 0>` | metadata `listTopResultSize` | -1 | list (every non -1 vendor value is on a list view) |
| `page_size: <int > 0>` | pagination-control `size` | 500 | list, trend; on distribution it adds a pagination control between buckets and metadata (20 built-in distribution views carry one) |
| `max_points_count: <int > 0>` | metadata `maxPointsCount` | 5000 | all |
| `include_resource_creation_time: true\|false` | metadata `includeResourceCreationTime` | false | all |

## 7. Timestamp display

`add_timestamp_as_column: true|false` -> `addTimestampAsColumn`,
`show_relative_timestamp: true|false` -> `isShowRelativeTimestamp`.
Both default to the historical `false`; both appear `true` in vendor
exports (relative timestamps on a TIMESTAMP column, for example
`config|createDate`). Not on instanced-group drivers or time segments.

## 8. Subject filter comparators

`subject.filter` `condition` now accepts every comparator in the
built-in exports (1,161 conditions audited across the three corpora):
`EQUALS`, `NOT_EQUALS`, `GREATER_THAN`, `LESS_THAN`, `CONTAINS`,
`NOT_CONTAINS`, `EXISTS`, `NOT_EXISTS`. `transform` accepts `CURRENT`,
`AVG`, `LAST`, `SUM`, `MAX`. The 8.18.7 built-ins carry an EXISTS with a
null value:

```
{"condition":"EXISTS","transform":"CURRENT","metricKey":"summary|vmfs_version",
 "metricValue":{"isStringMetric":true,"value":null},"filterType":"properties"}
```

```yaml
- filter_type: properties
  metric_key: summary|vmfs_version
  condition: EXISTS
  value: null
  string_metric: true      # required with value: null, rejected otherwise
  transform: CURRENT
```

Not modeled (seen only on alert-oriented built-in views):
`metricValue: {"values": [...]}` and `conditionId`. JSON key order varies
in vendor exports and is not significant; the renderer keeps its fixed
order.

## 9. `group_by:` (SubjectsGroupBy)

```xml
<SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine" type="descendant"/>
<SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine" type="self"/>
<SubjectsGroupBy adapterKind="VMWARE" resourceKind="ClusterComputeResource"/>
<Usage>dashboard</Usage>
```

`group_by: {adapter_kind: VMWARE, resource_kind: ClusterComputeResource}`.
List views only (all 14 built-in and the one vCommunity occurrence are
list views); one element. The SDK pak owning-subject injection inserts its
SubjectType before `<SubjectsGroupBy>` so every SubjectType stays ahead of
it.

## 10. SubjectType sets and Usage

Each subject kind historically rendered a `descendant` then a `self`
SubjectType. `types:` sets the list per kind, in emission order:

```yaml
subject:
  adapter_kind: VMWARE
  resource_kind: VirtualMachine
  types: [descendant]          # default [descendant, self]
# or, per kind:
subjects:
  - {adapter_kind: VMWARE, resource_kind: HostSystem, types: [self, descendant]}
  - {adapter_kind: VMWARE, resource_kind: Datastore}       # default pair
```

On `subjects:` a `subject.types` list is the default for entries without
their own. Values: `descendant`, `self`, distinct, non-empty. The vendor
shapes seen are descendant only (about a quarter of built-in views and half
of the vCommunity views), descendant+self, self only, and self+descendant.
The subject filter applies to every SubjectType element, as before.

`usage: [dashboard, report, content]` renders that subset of `<Usage>`,
always in the product's order (dashboard, report, details, content).
Default all four. Only the sets the corpora carry are accepted (YAML order
free):

| Set | 9.1.1 | 8.18.7 | vCommunity 0.8.1 |
|---|---|---|---|
| dashboard, report, details, content (default) | 757 | 696 | 154 |
| dashboard, report, content | 77 | 68 | 33 |
| report, content | 7 | 6 | 0 |
| dashboard, content | 9 | 7 | 2 |

Any other set (`details` alone, `dashboard` alone, a set without
`content`, and so on) is a load error. `analysis:compliance` (one built-in
view in each built-in export, beside all four) is not accepted. A
dashboard View widget that names a view whose `usage` leaves out
`dashboard` fails `Dashboard.validate` (what the product does with such a
widget is unverified). The matching report-side check is not implemented.

## `omit:` (presence fidelity)

The product's own exports leave many Properties out of some columns and
controls (absent rollUpType on property columns, no transformations or
timestamps on distribution columns, no metadata control on trend views).
`omit:` reproduces an absence exactly; it names YAML fields, not wire
names.

Column `omit:`

| Entry | Drops | Notes |
|---|---|---|
| `roll_up_type` | rollUpType | error with roll_up_type/roll_up_unit set, or on a property instanced member (emits none) |
| `transformation` | transformations | error with transformation, percentile, transform_expression or time-point fields set; error on a trend view (the Property is the view-level TREND/FORECAST stack, and none of the 586 vendor trend columns lacks it) |
| `add_timestamp_as_column` | addTimestampAsColumn | error with the field set |
| `show_relative_timestamp` | isShowRelativeTimestamp | error with the field set |
| `ascending_range` | ascendingRange, and waives the "all three numeric bounds need ascending_range" rule | needs a numeric bound; error with ascending_range set |
| `display_name` | displayName | `display_name` must then be absent |
| `is_property` | isProperty | error with `is_property: true` |
| `subject` | adapterKind and resourceKind | single-subject views; on a multi-subject view columns are unbound already (error) |

An instanced-group driver can omit only `display_name`; a time-segment
column cannot use `omit:`; an additional column can omit only
`display_name`.

View `omit:`: `metadata` (the whole control; error if any metadata field
is also set, including `hide_object_name: true`), `pagination` (the whole
control; error on a distribution view or with `page_size`),
`include_resource_creation_time` (that Property; error with the field
set).

## String red bound with ascending_range

A column whose only bound is a string `red_bound` (property-match coloring,
e.g. `red_bound: "true"`) may now set `ascending_range: true`; it renders
`ascendingRange=true`. The earlier rule (never set it) came from a small
sample: the vendor majority carries it (22 vCommunity columns and 59
9.1.1 built-in columns with, 2 and 3 without). `false` is not accepted on
such a column, no export carries it.

## SDK pak owning SubjectType (not changed)

`render_view_def_fragments(owning_adapter_kind=..., owning_resource_kind=...)`
appends `<SubjectType adapterKind="<pak kind>" resourceKind="<World>"
type="descendant"/>` to every bundled ViewDef (`sdk_builder.py`). Origin:
commit d11f202 (2026-05-27, compliance build 18), implementing
`knowledge/context/cleanroom-spec/spec/18-pak-content-bundle.md` §A2: the
importer files a pak view under the adapter named by one of its
SubjectTypes and drops a view without one, and §A2 states the requirement
explicitly for views whose subjects are all foreign kinds (pure-stitching
paks). That reason applies to all-VMWARE views, so there is no opt-out.
Two caveats for whoever revisits it: A1 to A4 shipped together in build 18,
so A2 was never isolated (the localization bundles that arrived in
compliance v22 were the later, proven fix for silently dropped content;
`investigations/sdk_pak_content_import_gap.md`); and the vCommunity Python
pak ships its views with only foreign SubjectTypes. Settling it needs one
calibration pak build with a view lacking the injection, installed on a
lab. Until then a round trip of a ported view differs from its source by
exactly this one SubjectType.

## Not modeled

- A buckets-control on a **list** view (5 vCommunity list views, 6
  built-ins): residue of a view type change in the UI, no effect on a
  list; emitting it would be a field the renderer honours for a view type
  that ignores it.
- `preferredUnitId=""` (empty): the loader treats `unit: ""` as no unit;
  one vCommunity column, 219 built-in columns.
- Per-SubjectType filters that differ (5 built-in views), filter
  `values` lists and `conditionId`, `startSubUnit` on the time selector,
  `BlacklistResourceKind`, `includeNotExistingResources`, column
  `cellLink`, related-object columns, `objectType=POLICY`, text and
  image presentations: none occur in the vCommunity pak.
- Per-column transformations on a trend view: trend columns still take
  the view-level `transformations:` list (all vCommunity trend columns
  carry `[NONE]`, which `transformations: [NONE]` expresses).
- `localizationKey` on a column or summary-row `displayName` Property (545
  of the 756 9.1.1 built-in views that convert, 9 vCommunity views): the renderer deliberately
  writes none (`render.py`, the displayName note: keys collide between
  transformed columns, and no localization bundle ships;
  `tests/test_renderer_regression_phase16.py` B). An additional column's
  `displayName` is not covered.
- A second `displayName` Property in one column (one view, "Windows Network
  Adapter", in both vCommunity and the 9.1.1 built-ins: the two carry the
  same value, the second with a `localizationKey`). The first is rendered
  and the second dropped; which one the product shows when they differ is
  not known. A repeat of any other Property, or in a summary row, is not
  covered.
- Leading or trailing whitespace on the `Description` (54 vCommunity views,
  22 of the converted 9.1.1 built-in views): the view loader strips it. Interior whitespace is
  carried.

`import-local` records each as a loss at its exact path: the whitespace one
only where the render is the source stripped, nothing else.

## Found by `import-local` (2026-11-13)

The offline converter classifies every ViewDef attribute and text
(`authoring/importer_offline_conversion.md`). It found three classes with no
YAML form: a column or summary-row `displayName` `localizationKey`, a
second column `displayName` and Description surrounding whitespace. They
stopped views as TOOLSET GAPs until they were ruled not modeled
(2026-11-13, §Not modeled). The Title gets the same strip, which the
converter records as a rename.

Control `visible` is a renderer constant per control type (`false` on the
time selector, attributes selector, buckets and metadata controls, `true` on
pagination); any other value is a GAP.

## Round-trip result (vCommunity 0.8.1, 189 unique ViewDefs)

Mechanical XML-to-YAML mapping of all 189, loaded and rendered by the
factory, compared semantically with the source (ignoring ids, whitespace,
attribute and Property order, the export-time column Item `id`, numeric
formatting, filter JSON key order): **183 identical**. The 6 others are
the two "not modeled" classes above (5 list views with a buckets-control,
1 empty preferredUnitId). With the SDK owning-subject injection every
view additionally differs by that one SubjectType. The comparator was
checked by mutation: each of 28,626 single-Property deletions or value
changes to the renders was detected.
