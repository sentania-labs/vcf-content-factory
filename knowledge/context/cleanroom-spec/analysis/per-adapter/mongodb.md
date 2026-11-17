# mongodb — per-adapter analysis

**Adapter kind**: `MONGODB_ADAPTER` (per `adapter.properties` KINDKEY + `describe.xml` AdapterKind)
**Source pak**: `inputs/from-marketplace/mongodb_9.0.0.0.24730517.pak`
**Decompiled at**: `analysis/decompiled/mongodb/` (extracted from pak's inner `adapters.zip`)
**Analysis date**: 2026-05-15
**Origin**: BlueMedora (package `com.bluemedora.vrealize.adapter.mongodb`), built atop the **aria-ops-core 8.2.0** adapter framework (package `com.vmware.tvs.vrealize.adapter.core`)

## Structure

```
mongodb_adapter3.jar                                     # entry-point — 12 classes, NOT obfuscated
mongodb_adapter3/
    conf/
        describe.xml                                     # 1947 lines — heavy declarative model
        describeSchema.xsd
    lib/                                                 # 18 jars
        aria-ops-core-8.2.0.jar                          # ← BlueMedora adapter framework
        mongo-java-driver-3.11.0.jar                     # ← MongoDB vendor SDK
        mongodb-dp-1.3.6.jar                             # BlueMedora MongoDB-specific helpers
        excavator-2.1.0.jar                              # BlueMedora data-extraction lib
        licensecheck-1.1.5.jar                           # (unused — see below)
        4-4.6.5.jar                                      # (cryptic name; likely a transitive dep)
        kotlin-stdlib-*.jar                              # parts of aria-ops-core are in Kotlin
        gson, httpclient, commons-codec, commons-logging, annotations, java-ipv6
```

Sub-shape **C1 rich-lib** with a clear vendor SDK (`mongo-java-driver`) and a third-party adapter framework (`aria-ops-core`).

## adapter.properties

```
ENTRYCLASS=com.bluemedora.vrealize.adapter.mongodb.MongoDBAdapter
KINDKEY=MONGODB_ADAPTER
```

**CONFIRMS the registration mechanism generalizes to marketplace adapters.** Three adapters now corroborate the pattern (mpb-adapter Broadcom, vim Broadcom internal, mongodb third-party BlueMedora).

## Vendor lineage

The `com.bluemedora.vrealize.adapter.mongodb` package gives away the
adapter's origin: BlueMedora was a VMware partner specializing in
vROps management packs. BlueMedora was acquired into VMware's TVS
(Technology Vertical Solutions) team — the `com.vmware.tvs.vrealize`
package on `aria-ops-core` reflects the post-acquisition rehousing.

This means many marketplace adapters likely share `aria-ops-core` as
their abstraction layer.

## BIG FIND — adapter abstraction framework (`aria-ops-core`)

MongoDBAdapter extends **`com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter`**, NOT `AdapterBase` directly. `UnlicensedAdapter` itself extends `AdapterBase` and provides a cleaner SPI for adapter authors:

```
abstract class UnlicensedAdapter extends AdapterBase {
    // Final/concrete in UnlicensedAdapter (implements AdapterBase's on*() hooks)
    public AdapterDescribe onDescribe();
    public boolean         onTest(TestParam);
    public DiscoveryResult onDiscover(DiscoveryParam);
    public void            onDiscard();
    public void            onConfigure(ResourceStatus, ResourceConfig);

    // Subclasses must supply:
    protected abstract String getAdapterDirectory();
    protected abstract boolean needRediscovery(ResourceConfig, Collection<ResourceConfig>);
    public abstract void configure(ResourceStatus, ResourceConfig);  // (note: NOT onConfigure)
    public abstract Tester getTester(ResourceStatus, ResourceConfig);
    public abstract Discoverer getDiscoverer(ResourceStatus, ResourceConfig);
    public abstract HistoricalCollector getHistoricalDataCollector(ResourceStatus, ResourceConfig);
    public abstract LiveCollector getLiveDataCollector(ResourceStatus, ResourceConfig);
    public abstract boolean getAutoDiscoveryEnabled(ResourceStatus, ResourceConfig);

    // Available to subclass
    protected MetricDataCache metricDataCache;
    protected SuiteAPIClient suiteAPIClient;
    protected int maximumRelationshipsPerCollection;
    protected int maximumEventsPerCollection;
}
```

The framework decomposes a Track C adapter into clean roles:

| Role | Interface | Methods |
|---|---|---|
| **Tester** | `com.vmware.tvs.vrealize.adapter.core.test.Tester` | `test(TestParam) throws TestException` |
| **Discoverer** | `com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer` | `getResources(DiscoveryParam) → ResourceCollection` |
| **LiveCollector** | `com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector` | `getCurrentMetrics(ResourceConfig, ResourceCollection)`, `getEvents(ResourceConfig, ResourceCollection)`, `getRelationships(ResourceConfig, ResourceCollection)`, `shouldForceUpdateRelationships()` |
| **HistoricalCollector** | `com.vmware.tvs.vrealize.adapter.core.collection.historical.HistoricalCollector` | `getHistoricMetrics(ResourceConfig, ResourceCollection, long start, long end)` |

`ResourceCollection` (in `aria-ops-core.data.*`) is a higher-level
adapter-author-friendly aggregate; the framework translates it to the
SDK's `CollectResult` / `MetricData` / etc.

**Note** the three-axis collection decomposition:
1. Current metrics (`getCurrentMetrics`)
2. Events (`getEvents`)
3. Relationships (`getRelationships`)

Each as its own method — much cleaner than dumping everything into a
single `onCollect()`. And **historical** is a separate SPI on top —
the framework supports backfill / catch-up that the raw SDK doesn't
elevate.

mongodb_adapter3.jar's 12 classes implement these roles cleanly:
`MongoDBAdapter` (entry), `MongoDBDiscoverer`, `MongoDBLiveCollector`,
`MongoDBTester`, `MongoDBConstants`, `MongoDBProperties`,
`CollectionResultCache`, `CounterMetricCache`, `ExUnoUtils` (with
nested `ExternalRelationship` and `ConditionalReplacementMetric`),
`VRealizeLogger`.

## Theories — pan-out / disprove ledger

### CONFIRMED — `adapter.properties` generalizes to marketplace adapters

Three independent adapters (Broadcom internal × 2, BlueMedora third-party) all use the same ENTRYCLASS/KINDKEY convention.

### CONFIRMED — VCF-CF's `vcfcf-adapter-base.jar` plan has prior art

The hypothetical `vcfcf-adapter-base.jar` mentioned in CLAUDE.md is the same idea as BlueMedora's `aria-ops-core`. The Discoverer / Tester / LiveCollector / HistoricalCollector decomposition is a proven, clean pattern that VCF-CF should adopt directly. The three-axis collection split (metrics / events / relationships) is particularly important.

### CONFIRMED — describe.xml's resource model is hierarchical and rich

The metric/property model is layered:

```
<ResourceKind>
    <ResourceIdentifier .../>
    <ResourceGroup key="..." instanced="false">
        <ResourceGroup key="...">           ← nests freely
            <ResourceAttribute key="..." dataType="float" unit="perSec" .../>
            ...
        </ResourceGroup>
        ...
    </ResourceGroup>
    <ComputedMetrics>
        <ComputedMetric key="..." expression="sum(${adapterkind=X, resourcekind=Y, metric=Z, depth=N})" />
    </ComputedMetrics>
</ResourceKind>
```

A metric's **fully-qualified key** is the pipe-separated path of group keys + attribute key (e.g., `aggregated_mongod_metrics|Opcounters|opcounters_delete`). This is the same `MetricKey.NodeList` structure I'd guessed at in pass 1 from the SDK survey.

### CONFIRMED — computed-metric expression language

```
sum(${adapterkind=MONGODB_ADAPTER, resourcekind=mongod, metric=Opcounters|opcounters_delete, depth=5})
```

`${...}` is a resource-selector. Keys: `adapterkind`, `resourcekind`, `metric` (with `|`-paths), `depth` (relationship traversal limit). Aggregation function `sum(...)` wraps it. SPEC § 06 documents this.

### NEW — describe.xml has at least 31 distinct element types

By inventory of `<Foo` in mongodb describe.xml: ResourceAttribute (513), State (226), SymptomDefinition (214), Condition (214), Unit (206), ComputedMetric (189), ResourceGroup (110), UnitType (75), Recommendation (23), ResourceIdentifier (18), ResourcePath (17), ApplicableResourceContainer (14), Recommendations (13), SymptomSet (12), Impact (12), AlertDefinition (12), ResourceKind (11), Description (11), CredentialField (7), ComputedMetrics (6), PolicySettings (4), WorkloadSettings (2), WasteSettings (2), Usage (2), UsableCapacitySettings (2), UnderusedSettings (2), UnUsedSettings (2), TimeSettings (2), StressedSettings (2), ResourceContainer (2). Plus the singletons (CapacityDefinition, CredentialKinds wrapper, etc.).

So mongodb declares: 11 resource kinds, 513 resource attributes (metrics + properties), 189 computed metrics, 214 symptom definitions, 12 alert definitions, 23 recommendations, and a full capacity model.

### NEW — `<State>` elements (226 observed)

Likely enum values for stateful properties (e.g., `replica_state` would have states like `PRIMARY`, `SECONDARY`, `ARBITER`). Not yet inspected; flag for SPEC § 05.

### NEW — `<SymptomDefinition>` / `<Condition>` pair (214 each)

Symptom definitions appear to be 1:1 with conditions. Each symptom probably has a single primary condition. Will inspect in next pass.

### NEW — `<Unit>` and `<UnitType>` (206 + 75)

Units of measure are a first-class declarative concept. Examples seen: `perSec`, `byteps`, `MB`, `Bytes`, `%`. The `<UnitType>` element probably defines a dimension (Time, Bytes, Rate) and `<Unit>` defines instances within a type.

### NEW — `<ResourcePath>` (17 occurrences)

Likely declares relationship-traversal paths (e.g., cluster → shard → mongod → replica). Plus the 2 `<TraversalSpec>` already noted. Will inspect.

### NEW THEORY — third-party marketplace adapters likely build on `aria-ops-core`

Other marketplace database adapters (mysql, postgresql, oracledatabase, servicenow, ms-sqlserver) all use `*_adapter3.jar` naming and are similar size. Hypothesis: they share BlueMedora's `aria-ops-core` framework. Validate by inspecting another in a future pass.

### PARTIALLY DISPROVEN — "all Track C adapters extend AdapterBase directly"

Two of three adapters analyzed (mpb-adapter, vim) extend AdapterBase. mongodb extends `UnlicensedAdapter` (which extends AdapterBase). VCF-CF Tier 2 SPEC should not assume direct inheritance — generated adapters may extend an abstraction framework class instead.

### NEW — describe.xml `<ResourceIdentifier>` has more attributes than catalogued

Observed new attribute: `identType="1"` (mongodb's `server_address_list` identifier). Also `length=""`, `default=""`, `enum="false"`. Schema version 7 (older than mpb-adapter's 8 or vim's 9 — mongodb is a mature pak from 2025).

## Tier 2 implications (VCF-CF native adapter SPEC)

1. **`vcfcf-adapter-base.jar` should follow the aria-ops-core pattern**:
   - Subclass-supplied SPIs for Tester, Discoverer, LiveCollector, HistoricalCollector
   - Three-axis collection (metrics, events, relationships) as separate methods
   - Optional historical collection as a separate SPI
   - Provided MetricDataCache, SuiteAPIClient, max-events/max-relationships limits

2. **Resource model** in describe.xml is hierarchical: `ResourceKind` > `ResourceGroup` (nestable) > `ResourceAttribute`. Generator must support arbitrary nesting depth.

3. **Metric keys are pipe-delimited paths** matching the group/attribute hierarchy.

4. **Computed metrics use an expression language** with `${...}` selectors. Generator should support emitting computed-metric expressions for derived/aggregate metrics.

5. **CredentialKind can have enum-typed fields** (`enum="true"` with nested `<enum value="X" default="true|false">`). Used for auth-method selection (e.g., mongodb's `auth_mongos` field offers Default / LDAP SASL).

6. **Multiple CredentialKinds per adapter** are supported — mongodb has both `mongodb_credentials` (with auth) and `mongodb_no_credentials` (placeholder for unauthenticated MongoDB). The platform presumably lets the user pick at adapter-instance creation time.

## Open / pass 4+

1. **Full ResourceAttribute attribute schema** — observed: `key`, `nameKey`, `dashboardOrder`, `dataType` (`float`, `integer`, `string`), `defaultMonitored`, `isDiscrete`, `keyAttribute`, `isRate`, `isProperty`, `hidden`, `unit`. Need to find docs for `keyAttribute`, `isRate` semantics, `isDiscrete` vs `dataType=string`.

2. **`<State>` element** — enum values for stateful attributes. Inspect in pass 4.

3. **Symptom definition expression language** — 214 SymptomDefinitions in mongodb. Each has a Condition. The condition is presumably an expression over metrics. Inspect.

4. **`<Unit>` / `<UnitType>` schema** — the units-of-measure model.

5. **TraversalSpec declaration** — how parent/child relationships are declared in describe.xml.

6. **`aria-ops-core.data.ResourceCollection`** API — the high-level data-building model. Worth javap'ing for the SPEC if VCF-CF will adopt this framework shape.

7. **Does the platform's SuiteAPIClient (built into aria-ops-core) differ from mpb-adapter's `vcops-suiteapi-client-2.2-all.jar`?** Probably yes; aria-ops-core wraps it. Will check if relevant later.

8. **describe.xml schema version 7 (mongodb) vs 8 (mpb-adapter) vs 9 (vim)** — mongodb is older. The schema is backwards-compatible (vim's v9 schema is run by the same platform that runs mongodb's v7). Need a version diff inventory.

## Confidence

- Adapter abstraction framework pattern: **High** — clean and well-formed in mongodb.
- Resource/metric model hierarchy: **High** — observed in 11 ResourceKinds with deeply nested ResourceGroups.
- Computed metric expression language: **Medium** — syntax confirmed from one example; need more examples and an authoritative grammar reference.
- Generalization to other third-party adapters: **High but unverified** — pattern consistent with mongodb's history but needs corroboration from another marketplace adapter in pass 4+.
