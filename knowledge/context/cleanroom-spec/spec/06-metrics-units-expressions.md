# 06 — Metrics, Units, and the Expression Language

**Status**: DRAFT (pass 3 evidence — mongodb)
**Evidence base**: mongodb describe.xml; SDK `MetricData`, `MetricKey`, `MetricPattern`, `RollUpType`, `RatedMetricsCalculator`

## Metric key paths

A metric's **fully-qualified key** is the pipe-delimited path of:

```
<group-key-outer>|<group-key-inner>|...|<attribute-key>
```

reflecting the `<ResourceGroup>` nesting in describe.xml.

Examples (from mongodb cluster ResourceKind):

```
aggregated_mongod_metrics|Opcounters|opcounters_delete
aggregated_mongod_metrics|Network|network_bytes_out
Children|mongos_child           (property)
```

The SDK's `MetricKey` type implements this via the nested
`MetricKey.Node` / `NodeList` structure. To construct one
programmatically the SDK provides node-list-builder API (signatures
yet to be inventoried; pass 4+ for full `MetricKey` API).

## Runtime push: `addMetricData`

Adapters push data into the `CollectResult` via `AdapterBase`:

```
addMetricData(ResourceConfig rc, MetricData data);
addMetricData(ResourceConfig rc, List<MetricData> data);
addMetricData(ResourceConfig rc, List<MetricData> data, boolean isProperty);
```

Each `MetricData` carries:
- The target `MetricKey`
- Value(s) + timestamp(s) (the SDK's `MetricDataList` /
  `MetricChunkList` types handle bulk + chunked pushes)
- A `RollUpType` declaring aggregation policy (sum / avg / max / min /
  latest — exact enum members not yet inventoried)

## Metric vs. property

The `boolean isProperty` parameter on `addMetricData` toggles between
two semantics. Declaratively, the same is set via the
`<ResourceAttribute isProperty="true|false">` flag.

| Mode | Use for | Storage | Change semantics |
|---|---|---|---|
| **Metric** (default) | Time-series numeric values | Historical series | Per-collection values appended |
| **Property** (`isProperty=true`) | Versioned attributes (state names, version strings, identifiers, child relationships) | Latest-value + change history | Change events generated on value change |

A property whose `dataType` is `string` is common — e.g., mongodb's
`mongos_child` property under the `Children` group, which presumably
tracks a related-resource reference.

## Rate semantics: `isRate`

The `<ResourceAttribute isRate>` attribute flags whether the
*pushed value* is already a rate.

**Hypothesis (pass 3, needs confirmation)**:

| `isRate` | Adapter pushes | Platform behavior |
|---|---|---|
| `false` (observed in mongodb counters with `unit="perSec"`) | The current per-second value, computed adapter-side | Stores as-is; reports as-is |
| `true` | A cumulative counter (monotonically increasing) | Differentiates between samples to derive a rate; uses `RatedMetricsCalculator` |

Most mongodb counter-style metrics are declared `isRate="false"` with
`unit="perSec"`, suggesting the adapter pushes already-derived rates.
Pass 4+ should find an `isRate="true"` example to confirm the inverse
semantics.

## Unit model

### `<Unit>` and `<UnitType>` elements

mongodb declares 206 `<Unit>` and 75 `<UnitType>` elements in
describe.xml. **The unit catalog is per-adapter** — adapters declare
the units their metrics use.

Schema not yet fully captured. Inferred from `<ResourceAttribute
unit="perSec">` references that match a `<Unit>` declaration:

```xml
<!-- Speculative structure — to confirm in pass 4 -->
<UnitTypes>
    <UnitType key="<type-key>" nameKey="<int>" />
</UnitTypes>
<Units>
    <Unit key="<unit-code>"
          unitType="<type-key>"
          nameKey="<int>"
          baseUnit="..." />
</Units>
```

SDK classes `UnitDescribe`, `UnitTypeDescribe`, `BaseUnitDescribe`,
`ConsumptionCountUnitDescribe` (in the describe package) are the
in-memory models — pass 4+ to javap and document.

### Common unit codes (observed in mongodb)

- `perSec` — events/operations per second (rate)
- `byteps` — bytes per second
- `MB` — megabytes
- `Bytes` — bytes
- `%` — percent

Adapter authors should prefer the platform's existing unit catalog
(pass 4+ to find an authoritative list).

## Computed metrics — expression language

```xml
<ComputedMetrics>
    <ComputedMetric
        key="aggregated_mongod_metrics|Opcounters|opcounters_delete"
        expression="sum(${adapterkind=MONGODB_ADAPTER,
                          resourcekind=mongod,
                          metric=Opcounters|opcounters_delete,
                          depth=5})" />
</ComputedMetrics>
```

### Syntax (observed)

```
<expression>     ::= <aggfn>(<selector>)
                  |  <arithmetic-expression>           (not yet observed; expected)
                  |  ...

<aggfn>          ::= "sum" | "avg" | "max" | "min" | ...    (full set TBD)

<selector>       ::= "${" <selector-clauses> "}"

<selector-clauses>::= <clause> ("," <clause>)*

<clause>         ::= "adapterkind=" <adapter-key>
                  |  "resourcekind=" <resource-key>
                  |  "metric=" <metric-path>           // pipe-delimited
                  |  "depth=" <integer>                 // relationship-traversal depth limit
```

### Selector clauses observed

- **`adapterkind`** — scope to a specific adapter kind
- **`resourcekind`** — scope to a specific resource kind within that
  adapter
- **`metric`** — the pipe-delimited metric key path
- **`depth`** — traversal depth (presumably the parent→child
  relationship depth limit when aggregating across related resources)

### Aggregation functions

Observed: `sum(…)`. Others (`avg`, `max`, `min`, etc.) presumably
supported; pass 4+ to inventory.

### Semantics (inferred)

The platform evaluates the expression at query time (or on a
schedule). For each instance of the resource kind declaring the
computed metric, the selector resolves to a set of related resources
(within `depth` hops); the aggregation function reduces their `metric`
values to a single number stored under the computed metric's key on
the declaring resource.

mongodb's `cluster` kind declares aggregated metrics like
`aggregated_mongod_metrics|Opcounters|opcounters_delete` that sum
across all `mongod` instances reachable within 5 traversal hops —
producing a cluster-level "total deletes per second" derived from
per-mongod primary metrics.

## Symptom-condition language (placeholder — pass 4)

214 `<SymptomDefinition>` + 214 `<Condition>` in mongodb describe.xml.
Symptoms presumably evaluate metric-expression-language conditions
(threshold crossings, comparisons) and feed the alert framework.

To inventory in pass 4.

## Open / pass 4+

1. Full `RollUpType` enum values
2. Full `addMetricData` semantics across the three overloads
3. Full `<Unit>` / `<UnitType>` schema + the platform's canonical unit
   catalog
4. `isRate="true"` examples — confirm the cumulative-counter
   hypothesis
5. Full set of aggregation functions in the expression language
6. Whether the expression language supports arithmetic (`a + b`,
   `a / b`), conditionals, or only selector + aggregator
7. Symptom-condition expression syntax
8. `MetricPattern` semantics (the SDK type, suggesting pattern-matched
   metric selection alongside or instead of literal keys)
9. The `<State>` element — enum values for discrete attributes
