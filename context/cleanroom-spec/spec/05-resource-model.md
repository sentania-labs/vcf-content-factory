# 05 — Resource Model

**Status**: DRAFT (pass 3 evidence — mongodb is the first adapter with a substantive resource model)
**Evidence base**: mongodb describe.xml; SDK `ResourceKindDescribe` + `ResourceAttributeDescribe` + related classes

## Concept

A **resource kind** is a class of monitored thing (e.g., `mongod`,
`cluster`, `replica_set`). Each resource kind declares:

1. **Identifiers** — the tuple that uniquely names instances of this
   kind
2. **Attributes** (metrics + properties) — typed values pushed by the
   adapter on each collection cycle
3. **Computed metrics** — derived values calculated by the platform
   from primary attributes
4. **Resource groups** — hierarchical buckets for organizing
   attributes
5. **Relationships** to other resource kinds (via traversal specs
   and resource paths — see § 07 when added)
6. **Capacity model** — supplied vs. used capacity declarations

The runtime instance of a resource kind is a **ResourceKey** (the
SDK type) whose stable identity is determined by the resource kind +
identifier values.

## `<ResourceKind>` element

```xml
<ResourceKind key="<unique-key>"
              nameKey="<i18n-int>"
              type="<int>"
              isSingleton="true|false (optional)"
              isCredentialRequired="true|false (optional, observed)"
              monitoringInterval="<int> (optional)"
              monitoringIntervalTimeUnit="..."
              dynamic="true|false (optional)"
              capacityModel="<key> (optional)"
              policyModel="..."
              subType="<int> (optional)">

    <ResourceIdentifier .../>
    <ResourceIdentifier .../>
    ...

    <ResourceGroup .../>
    ...

    <ComputedMetrics>
        <ComputedMetric .../>
    </ComputedMetrics>

    <ResourcePath .../>          <!-- relationship paths -->

    <PowerState>...</PowerState>
    <Icon>...</Icon>
    <!-- ... -->
</ResourceKind>
```

### `<ResourceKind>` attributes

- **`key`** — stable identifier; unique within the adapter kind.
  Naming conventions observed: lowercase_with_underscores (mongodb,
  e.g., `mongo_database`, `replica_set`); UPPER_SNAKE_CASE for adapter
  instance resource kinds (`VMWARE_INFRA_MANAGEMENT_INSTANCE`,
  `ManagementPackBuilderAdapterInstance`).
- **`nameKey`** — integer → entry in `resources/resources*.properties`
  for localized display name.
- **`type`** — integer flag. Observed values:
  - `7` — adapter instance container (the per-configured-instance
    resource representing the adapter itself)
  - (other values not yet inventoried; pass 4+)
- **`isSingleton`** (optional) — when `true`, exactly one instance
  per appliance. Observed in vim's `VMWARE_INFRA_MANAGEMENT_INSTANCE`.
- **`isCredentialRequired`** (per `ResourceKindDescribe` API) — whether
  user must supply a credential.
- **`monitoringInterval`** + **`monitoringIntervalTimeUnit`** — per-kind
  monitoring interval override.
- **`dynamic`** — boolean flag; semantics TBD.
- **`capacityModel`** — references a `<CapacityDefinition>` key.
- **`subType`** — integer; semantics TBD (per SDK getter).

## `<ResourceIdentifier>` element

```xml
<ResourceIdentifier
    key="<id-key>"
    nameKey="<int>"
    dispOrder="<int>"
    required="true|false"
    type="string|integer|..."
    length="" (optional)
    identType="<int> (optional)"
    enum="false|true (optional)"
    default="" (optional)
    hidden="true|false (optional)"
    readOnly="true|false (optional)"/>
```

- **`key`** — stable identifier name.
- **`required`** — must be set at instance creation. Note: for
  multi-identifier kinds, the SET of required identifiers is the
  effective primary key.
- **`type`** — primitive type for the identifier value (`string`
  observed; integer presumably valid).
- **`identType`** — integer flag. Observed value: `1` (mongodb).
  Likely a category code; pass 4+ to enumerate.
- **`hidden`** + **`readOnly`** — UI hints. `hidden="true"` keeps the
  field out of the user form (used for system-supplied identifiers
  like `COLLECTOR_UUID`).
- **`enum`** + nested `<enum>` — fixed-choice dropdown (same as
  `<CredentialField>` enum pattern).

### Composite identifiers

A ResourceKind may declare multiple `<ResourceIdentifier>` elements.
The full identifier tuple uniquely names instances. mongodb's
`cluster` kind has one identifier (`server_address_list`); other
kinds may have many.

The SDK's `ResourceKey` value type is the runtime representation.
`ResourceConfig.getResourceIdentifiers()` returns
`List<ResourceIdentifierConfig>`.

## `<ResourceGroup>` element

```xml
<ResourceGroup key="<group-key>"
               nameKey="<int>"
               instanced="false|true">
    <ResourceGroup key="..." ...>      <!-- nestable -->
        <ResourceAttribute .../>
        ...
    </ResourceGroup>
    <ResourceAttribute .../>
    ...
</ResourceGroup>
```

**Resource groups are hierarchical buckets that organize attributes
into a tree.** They:

- Nest arbitrarily (mongodb has depth ≥ 3:
  `aggregated_mongod_metrics > Opcounters > opcounters_delete`)
- Have no functional effect on data — purely organizational
- Map to the UI's metric tree view
- Contribute to a metric's **fully-qualified key**: the concatenation
  of all enclosing group keys + the attribute key, separated by `|`
  (e.g., `aggregated_mongod_metrics|Opcounters|opcounters_delete`)

### `instanced="false"` vs `instanced="true"`

- `instanced="false"` — the group is a static category; one set of
  attributes for the resource.
- `instanced="true"` — semantics TBD; likely means multiple instances
  of the group's attributes can exist (e.g., per-disk metrics where
  the disk identity is in the group instance key).

## `<ResourceAttribute>` element

```xml
<ResourceAttribute
    key="<attr-key>"
    nameKey="<int>"
    dashboardOrder="<int>"
    dataType="float|integer|string"
    defaultMonitored="true|false"
    isDiscrete="true|false"
    keyAttribute="true|false"
    isRate="true|false"
    isProperty="true|false"
    hidden="true|false"
    unit="<unit-code> (optional)"/>
```

### Attributes

- **`key`** — stable name; unique within the enclosing ResourceGroup
  (or ResourceKind if at top level).
- **`dataType`** — primitive value type. Observed: `float`, `integer`,
  `string`.
- **`defaultMonitored`** — included in the default monitoring policy
  (controls whether the platform's default policy collects this
  attribute).
- **`isDiscrete`** — discrete vs. continuous numeric value. Observed
  `false` for most; semantics suggest the platform treats discrete
  attributes (e.g., state codes) differently from continuous metrics
  (e.g., bytes/sec).
- **`keyAttribute`** — likely marks the attribute as "important" or
  "key" for display/dashboard ordering. Mongodb sets this for primary
  metrics like `opcounters_delete`, `mem_resident`. Pass 4+ to
  confirm semantics.
- **`isRate`** — boolean. Observed `false` on metrics with `unit="perSec"`.
  **Interpreted hypothesis**: the metric *is* a per-second value that
  the adapter pushes directly; the platform should NOT auto-derive a
  rate. (`isRate="true"` would presumably mean: the adapter pushes a
  cumulative counter and the platform should derive a rate via
  `RatedMetricsCalculator`.) Confirm with future evidence.
- **`isProperty`** — boolean. **THIS IS THE METRIC vs PROPERTY DISCRIMINATOR.**
  `false` → metric (time series, latest value matters); `true` →
  property (versioned; latest write wins; change events generated on
  change). This explains the SDK's overloaded
  `addMetricData(ResourceConfig, List<MetricData>, boolean isProperty)`.
- **`unit`** — unit code from the platform's unit catalog (e.g.,
  `perSec`, `byteps`, `MB`, `Bytes`, `%`). See § 06 for unit model.
- **`hidden`** — when `true`, attribute is not surfaced in default UI
  (still collected and queryable).
- **`dashboardOrder`** — order in the metric tree UI display.

### Metric vs. property

The `isProperty` flag is **the** distinction:

| `isProperty` | Semantics | SDK push |
|---|---|---|
| `false` | Metric — time-series numeric/discrete value; one value per collection cycle; platform keeps history | `addMetricData(rc, [data])` (default) |
| `true` | Property — versioned attribute; platform tracks change events; current-value-wins semantics; may be non-numeric (e.g., a string identifier) | `addMetricData(rc, [data], true)` (isProperty=true overload) |

Properties commonly hold: resource state names, version strings,
configuration values, child relationships (mongodb's `mongos_child`
property in the cluster's Children group).

## `<ComputedMetrics>` and `<ComputedMetric>`

Container element + child for declaring **platform-computed derived metrics**.

```xml
<ComputedMetrics>
    <ComputedMetric
        key="<full-key-with-pipes>"
        expression="<expression>"/>
    ...
</ComputedMetrics>
```

The `expression` uses the platform's metric-expression language (see § 06).

Computed metrics are **calculated by the platform**, not pushed by
the adapter. The adapter declares them; the platform evaluates the
expression at query time (or on a schedule, TBD).

## `<ResourcePath>`

Declares **relationship traversal paths** between resource kinds.
Used by:
- Computed metrics (to aggregate across related resources, e.g.,
  "sum of mongod opcounters_delete across all mongods under this
  cluster")
- UI navigation
- Symptom evaluation

Schema not yet captured; pass 4+ to inventory.

## `<TraversalSpec>` (top-level under `<AdapterKind>`)

Top-level traversal definitions. Different from `<ResourcePath>`
(which is per-ResourceKind) — TraversalSpec defines the overall
relationship structure visible in the UI.

Pass 4+.

## Identifier-based runtime identity

The SDK uses `ResourceKey` (in `com.integrien.alive.common.adapter3`)
as the runtime identity of a resource instance:

```
ResourceKey identifies a resource by:
    - adapter kind
    - resource kind
    - resource name
    - tuple of (identifier-key, identifier-value) pairs
```

`AdapterBase.getMonitoringResource(ResourceKey | Integer | ResourceConfig)`
looks up the runtime `ResourceConfig` for an identified resource.

## ResourceCollection (aria-ops-core)

Adapters using the `aria-ops-core` framework (mongodb and probably
other BlueMedora-derived marketplace adapters) build a higher-level
`ResourceCollection` (in `com.vmware.tvs.vrealize.adapter.core.data`)
during collection, which the framework translates to the SDK's
`CollectResult` on the way out. The high-level type collects metrics,
events, and relationships separately in a clean builder-style API.

Adapters extending `AdapterBase` directly call SDK helpers
(`addMetricData`, `addEvent`, etc.) inline during `onCollect`.

VCF-CF Tier 2 should adopt the ResourceCollection-style abstraction
in `vcfcf-adapter-base.jar`.

## Open / pass 4+

1. Full `<ResourceKind type>` enumeration (only `7` observed).
2. Full `<ResourceIdentifier identType>` enumeration.
3. `<ResourceKind dynamic>` semantics.
4. `<ResourceGroup instanced="true">` semantics — likely per-instance
   metric groups (e.g., per-disk, per-CPU-core).
5. `<ResourceAttribute keyAttribute>` semantics.
6. `<ResourceAttribute isRate>` confirm semantics (counter vs.
   already-derived rate).
7. `<ResourcePath>` and `<TraversalSpec>` schemas.
8. `<State>` element semantics (enum values for stateful
   properties / discrete attributes).
9. Property change-event delivery and ordering guarantees.
