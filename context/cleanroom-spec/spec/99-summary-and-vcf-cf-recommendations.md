# Summary and VCF-CF Recommendations

**Date**: 2026-05-15
**Status**: Final summary of the cleanroom investigation. Synthesis across all 39 KEEP-C paks (7 deep-analyzed, 32 bulk-surveyed) + 12 ELIMINATE-B paks + SDK + MPB runtime.

## TL;DR

The VCF Operations native adapter ecosystem is a **layered onion** of
APIs spanning 15+ years of evolution. The legacy Integrien `adapter3`
SDK is the ABI everything still compiles against, but three
parallel-track modernization layers have grown around it:

1. **`com.broadcom.ops.data.*`** (stream/subscriber data SDK) — observed in vSphere
2. **`com.vmware.vrops.nmp.task.*`** (modern task protocol) — observed in vim
3. **`com.vmware.ops.api.model.resource.ResourceDto`** (foreign-resource bridge) — observed in VCFAutomation

A clean third-party abstraction framework (`aria-ops-core` from
BlueMedora) decomposes the SDK contract into a Tester / Discoverer /
LiveCollector / HistoricalCollector pattern. **VCF-CF's planned
`vcfcf-adapter-base.jar` should adopt this pattern directly** — it's
proven prior art used by every BlueMedora-derived marketplace adapter.

The MPB runtime jar (`mpb_adapter-9.0.1-patch-1.jar`, 15,440 classes,
Kotlin) contains **its own code-generation subsystem**
(`com.vmware.mpb.generation.*`) capable of emitting `adapter.properties`
and dashboard JSON from a design model. **VCF-CF Tier 1 should
strongly consider reusing this rather than reimplementing**.

## What we know with high confidence

| Area | What's documented | Section |
|---|---|---|
| Adapter contract | `AdapterInterface3` (9 methods) + `AdapterBase` (template-method, with on*() hooks + ~70 helper methods) | § 01 |
| Adapter registration | `adapter.properties` file at entry-jar root: `ENTRYCLASS=` + `KINDKEY=`. 3 independent corroborations across Broadcom-internal, marketplace, and third-party adapters. | § 01 |
| Packaging shapes | Two-layer wrapper-and-inner-archive. Three sub-shapes (C1 rich-lib, C1-light, C2 SDK-on-classpath) | § 01 |
| Optional SDK pinning | Bundle `vrops-adapters-sdk-*.jar` in `lib/` (Tomcat classloader prefers local) | § 01 |
| Two task protocols | Legacy `ActionableAdapterInterface` (poll-async, describe.xml-declared) **and** modern NMP `TaskHandler`/`AsyncTaskHandler` (callback-async, runtime-dispatched) | § 04 |
| describe.xml root | AdapterKind / ResourceKinds / CredentialKinds / Actions / TraversalSpecKinds + many more elements | § 02, § 05, § 07 |
| Resource model | ResourceKind > ResourceGroup (nestable) > ResourceAttribute. Hierarchical. | § 05 |
| Metric keys | Pipe-delimited paths matching ResourceGroup hierarchy: `Opcounters\|opcounters_delete` | § 06 |
| Metric vs property | `isProperty="true"` for versioned attributes; metrics are time-series. SDK overload `addMetricData(rc, list, isProperty)`. | § 05, § 06 |
| Computed metrics | Expression language: `sum(${adapterkind=X, resourcekind=Y, metric=Z\|W, depth=N})` | § 06 |
| Adapter abstraction frameworks | `aria-ops-core` / `UnlicensedAdapter` SPI with Tester / Discoverer / LiveCollector / HistoricalCollector. **Three-axis collection split** (metrics / events / relationships). | § 01 |
| Topology — two modes | (A) declarative `<TraversalSpec>` with `ADAPTER_KIND::ResourceKind::child` paths; (B) runtime-pushed via SDK `Relationships`. Both coexist. | § 07 |
| Cross-MP topology | Foreign edges in ResourcePath (`STORAGE_DEVICES::Mount::child`); 14 paks declaratively reference VMWARE::VirtualMachine | § 07 |
| Cross-MP metric attachment | Construct `ResourceKey(adapterKind=foreign, resourceKind=foreign, identifiers=matching)` and push via `addMetricData`. Platform de-duplicates by identity. **No special API.** Foreign-resource lookup via `com.vmware.ops.api.model.resource.ResourceDto`. | § 07 |
| VirtualMachine identifier shape | `(VMEntityName, VMEntityObjectID, VMEntityVCID, VMEntityInstanceUUID)` | § 07 |
| Adapter instance lifecycle | Reuse-the-instance across collect() cycles (confirmed by NSX's heavy state caching) | § 01 |
| MPB runtime | Kotlin, 15,440 classes, built on aria-ops-core, has its own code-generation subsystem | mpb-adapter-insights-for-vcf-cf.md |

## What we know less well

| Area | Status |
|---|---|
| ~~Concurrency model of `collect()`~~ | **RESOLVED — Pass 21 + 23**: per-instance `Semaphore(1)` empirically confirmed; platform does NOT retry failed collect cycles. See `spec/01` § Pass 23 confirmations. |
| ~~Full SDK Relationships API surface~~ | **RESOLVED — Pass 21**: 18 method signatures across 3 axes documented in `spec/07`. |
| Full set of `BuilderFunction` enum values (MPB design DSL) | Only BASE64 + NONE observed |
| Full set of computed-metric aggregation functions | Only `sum()` observed |
| `<Unit>` / `<UnitType>` schema + canonical unit catalog | Skeleton only |
| ~~`<Symptom>` / `<Condition>` / `<AlertDefinition>` / `<Recommendation>` schemas~~ | **RESOLVED — Pass 8**: full grammar (10 condition types, 20 operators, compound boolean symptoms, applyOn-scoping) in `spec/08`. |
| ~~`<CapacityDefinition>` + Workload/Stressed/Idle/Waste/etc. Settings~~ | **RESOLVED — Pass 18**: full ladder in `spec/09`. |
| ~~`<PowerState>` / `<Icon>` / `<Condition>` decision-tree elements~~ | **RESOLVED — Pass 20**: multi-level Icon decision tree + PowerState alias mapping in `spec/14`. |
| ~~`<Policy>` / `<PolicyMetric>` model~~ | **RESOLVED — Pass 19**: full Policy + OOTBPolicy + PolicySettings ladder in `spec/09`. |
| `<State>` element semantics for discrete attributes | Not started |
| OpenAPI extension subsystem | Not started |
| `com.broadcom.ops.data.*` (modern data SDK) | Surface inventoried, semantics characterized as Reactive-Streams middleware for vCenter stats (Pass 9 — NOT a successor SDK). See `analysis/per-adapter/vcf-ops-data-sdk.md`. |
| `com.vmware.ops.api.*` (mid-layer API) | One class (ResourceDto) observed; full surface TBD |
| ~~Platform install pipeline behavior~~ | **RESOLVED — Pass 23**: two-layer CASA→Python 7-phase state machine documented in `spec/16`. |
| ~~Pak signing-validation policy~~ | **RESOLVED — Pass 23**: unsigned-accept + skip-dates + opt-in checkSignature documented in `spec/16` § Signature validation. |
| `<CustomGroupMetrics>` runtime usage example | Schema documented in `spec/02a`; parser-class evidence confirms runtime contract is real; no in-corpus adapter uses it (Pass 23 confirmed-negative across 2 lab appliances). Needs external pak. |

## VCF-CF Tier 2 recommendations (Native Java adapter generator)

### 1. Adopt the `aria-ops-core` decomposition for `vcfcf-adapter-base.jar`

Don't reinvent the abstraction layer. Mirror the SPI:

```
abstract class VcfCfAdapter extends AdapterBase {
    abstract Tester             getTester(...);
    abstract Discoverer         getDiscoverer(...);
    abstract LiveCollector      getLiveDataCollector(...);
    abstract HistoricalCollector getHistoricalDataCollector(...);  // optional
}

interface LiveCollector {
    ResourceCollection getCurrentMetrics(...);
    ResourceCollection getEvents(...);
    ResourceCollection getRelationships(...);
    boolean shouldForceUpdateRelationships();
}
```

The three-axis split (metrics / events / relationships as separate
methods) produces clean generated code and clear error boundaries.

### 2. Generate adapter.properties at the entry-jar root

Two lines: `ENTRYCLASS=` (fully-qualified Adapter class) and
`KINDKEY=` (matches `<AdapterKind key="...">`). Mandatory.

### 3. Use NMP task protocol for actions (not legacy ActionableAdapterInterface)

When generating an adapter that needs actions:
- Implement `com.vmware.vrops.nmp.task.{TaskHandler, AsyncTaskHandler}`
- Define `TaskParam`/`TaskResult` subclasses for each action type
- Dispatch on `instanceof` in `onTask`

The legacy interface remains supported but the NMP protocol is the
documented future direction (corroborated by VMware's modernization
trajectory: NMP tasks + `vcf-ops-data-sdk` are both Broadcom-namespaced).

### 4. First-class cross-MP attachment in the design language

The most common foreign-attachment target is `VMWARE::VirtualMachine`
(14/39 paks declare it). The generator should let users say "this
metric attaches to a VirtualMachine identified by these fields"
without writing the lookup code.

Recommended approach: emit code that uses
`com.vmware.ops.api.model.resource.ResourceDto` for foreign-resource
lookups (the bridge type VCFAutomation uses). The generator should
support the common identifier shapes (VM, HostSystem, Datastore,
NSX kinds — to be inventoried) as built-in attachment targets.

### 5. Bundle the SDK in lib/ for ABI stability

Generated adapters should bundle a pinned `vrops-adapters-sdk-*.jar`
in their `lib/` directory. The Tomcat-style classloader prefers local
jars. This insulates the generator's output from platform upgrades
that might break SDK ABI.

### 6. describe.xml: pick declarative vs runtime topology per-adapter

Two valid modes (§ 07):
- **Static target system** (databases, hardware) → declarative
  TraversalSpec — UI navigation is "free"
- **Dynamic target system** (Kubernetes, NSX, anything user-creates-objects-in)
  → runtime-pushed via Relationships API

Generator should ask the user or infer from the target-system shape.

### 7. Test the C2 sub-shape

`SupervisorAdapter` and `mpforaggregator` adapters use the
SDK-on-classpath pattern (no `lib/` directory). This is the leanest
deployment — fewer megabytes to ship. Use it when the adapter only
depends on the platform's runtime classpath.

## VCF-CF Tier 1 recommendations (MPB design generator)

### 8. Strongly consider REUSING the MPB runtime's existing generation subsystem

`mpb_adapter-9.0.1-patch-1.jar` contains
`com.vmware.mpb.generation.*` — a code-generator that emits
`adapter.properties` (`AdapterProperties` class implements
`IWritableFile`), dashboard JSON (`DashboardJson.DashboardBuilder`),
and likely `describe.xml`. The input is `com.vmware.mpb.model.BuilderFile`
(MPB's in-memory design representation).

**Recommended architecture**:
```
User design spec (UI or YAML)
    ↓
VCF-CF design transformer (produces BuilderFile)
    ↓
mpb-adapter's existing generation subsystem
    ↓
Deployable .pak
```

This is dramatically cheaper than reimplementing.

### 9. Match the MPB design DSL exactly

What MPB designs natively express:
- HTTP-driven collection (REST/SOAP/arbitrary HTTP) — `HttpCollector`
- Chained / hierarchical requests — `HttpChainedRequestUtils`
- Value transformations (limited set — `BuilderFunction` enum: BASE64, NONE, …)
- Per-instance configuration params — `BuilderConfigParam.DataType`: STRING, INTEGER, SINGLE_SELECTION
- Cross-MP property attachment — `HttpExternalResourcePropertyAdder`
- Unit conversion — `CommonUnits` / `ConvertableUnit`

The generator's design language should be opinionated about matching
this DSL. **Don't expose features the runtime can't execute.**

### 10. Validation: gate generated designs through `BuilderFileValidation`

The MPB runtime ships a validator. Use it in the generator's CI to
fail-fast on invalid designs before deployment.

### 11. Tier 1→Tier 2 promotion: clear triggers

Promote to Tier 2 (native Java) when MPB's design language can't express:

| Trigger | Why MPB can't |
|---|---|
| Non-HTTP collection protocol | No gRPC/JDBC/binary protocol support in `mpb.impl.collect` |
| Persistent connections / subscriptions | MPB is request/response only |
| User-invokable actions | No action subsystem in MPB runtime visible |
| Custom relationship inference (beyond identifier match) | No equivalent of BlueMedora's `ExternalRelationship` join-rule visible |
| Stateful transformations across collect cycles | BuilderFunction is stateless string→string |
| Auth flows beyond basic / token | Not yet observed; investigate |

For Tier 2 promotion targets, the recommended generator output is a
plain Track C adapter atop `vcfcf-adapter-base.jar` (recommendation
#1).

## What was learned about MPB specifically (Scott's ask)

See `analysis/per-adapter/mpb-adapter-insights-for-vcf-cf.md` for the deep dive.

Key points:

1. **MPB runtime is Kotlin**, 15,440 classes, built on aria-ops-core.
2. **The MPB runtime contains a complete code-generation subsystem** that VCF-CF can reuse.
3. **Cross-MP attachment is named explicitly**: `HttpExternalResourcePropertyAdder`. Built-in MPB capability.
4. **HTTP-chained requests are first-class**: list-then-detail patterns with async fan-out.
5. **Hierarchical data extraction is supported**: `DataModelList.parentListId` allows nested resources (cluster → replica → member).
6. **The design DSL is small**: STRING/INTEGER/SINGLE_SELECTION params; BASE64-style value transforms. Match it exactly to avoid generating un-executable designs.
7. **Track B (Integration SDK) paks use the SAME describe.xml schema as Track C**. The platform doesn't care where the runtime lives. This means a unified describe.xml output path can target both Track A (MPB-runtime) and Track B (container).

## What was learned about Track B (Integration SDK)

Investigated for completeness (Scott's invitation):

- Same describe.xml schema as Track C. Inner pak ships **zero jars** — implementation is a container image pulled by Cloud Proxy from an external registry.
- Manifest is iSDK template format with placeholders (`DISPLAY_NAME`, `VENDOR`, etc.) left in production paks.
- Adapter-instance identifiers include Cloud-Proxy deployment knobs like `container_memory_limit`, `log_level`, `info_events` flags.
- Indistinguishable from Track A at the pak-file level — runtime dispatch is by external adapter_kind registry.

**Implication**: a generator producing Track B output would emit:
- The same describe.xml as for Track A/C
- A container image (built separately) and registry coordinates
- Cloud-Proxy-specific identifiers in the adapter-instance kind

VCF-CF's Tier 1 (MPB) is the more natural target than Track B for most
use cases — Track B carries container-build complexity that Tier 1
sidesteps entirely.

## Open work items (prioritized)

Highest leverage if pursued in another pass:

1. **Verify mpb-generation emits describe.xml** (currently inferred). If yes, document the full input-`BuilderFile` schema.
2. **Inventory `<SymptomDefinition>`/`<Condition>` expression grammar** — alert authoring is a major describe.xml surface (214 in mongodb).
3. **Characterize `com.broadcom.ops.data.*` data SDK** — likely the future, worth understanding before VCF-CF commits to legacy SDK.
4. **Inventory `<Unit>` / `<UnitType>` canonical catalog** — for matching declared metric units to platform-known categories.
5. **Document NSX, HostSystem, Datastore identifier shapes** — additional cross-MP attachment targets.
6. **Test cross-MP push end-to-end** in a dev environment: construct a foreign ResourceKey, push a metric, confirm it lands on the foreign resource.
7. **Full `BuilderFunction` enumeration** — what value transforms are actually available in MPB designs.

## Coverage by-the-numbers

- 51 unique paks triaged (after dedupe), 39 KEEP-C in scope
- 7 deep-analyzed adapters: mpb-adapter, vim, mongodb, vSphere (vmwarevi_adapter3), NSXTAdapter3, VCFAutomation, AppOSUCPAdapter3 (light)
- 32 bulk-surveyed adapters (devel + marketplace)
- 12 ELIMINATE-B paks classified + 1 spot-checked (Indevops Brocade Switches)
- 1 SDK jar (`vrops-adapters-sdk-2.2.jar`) inventoried at the API-surface level
- 1 MPB runtime jar (`mpb_adapter-9.0.1-patch-1.jar`) inventoried at the package + key-class level
- 5 distinct API/SDK packages identified across the Operations ecosystem
- 8 SPEC sections drafted (00-07) + this summary
- 7 per-adapter analysis files + 1 bulk-survey + this summary
- 9 local commits, full theory pan-out/disprove ledger preserved

## Self-assessment

For VCF-CF generator-ready completeness:

- **Tier 2 (native adapter generation) SPEC**: ~50% complete. Lifecycle, packaging, resource model, metric model, cross-MP, and abstraction-framework recommendation are solid. Missing: relationship/runtime-push API, alert framework, capacity model, policy, classloading details.
- **Tier 1 (MPB design generation) recommendations**: ~70% complete on the strategic side. The recommendation to reuse the existing MPB generation subsystem changes the problem shape significantly — much less reimplementation needed than initially assumed. Missing: full BuilderFile schema, BuilderFunction enum, validator rules.

**Highest-leverage single follow-up**: verify the MPB generation subsystem emits describe.xml and document the BuilderFile schema. If both confirmed, Tier 1 implementation cost drops dramatically.

---

## Pass 7 update (2026-05-16) — Tier 1 path de-risked

The Pass 6 highest-leverage open question — "does MPB generation emit describe.xml?" — is now **CONFIRMED YES**.

`com.vmware.mpb.generation.describe.DescribeXml` exists, is constructed from a `BuilderFile` + `DescribeResourcesProperties`, runs XSD validation, and writes the file. The MPB runtime implements exactly **6 `IWritableFile` classes** that together produce the full deployable artifact set from a single `BuilderFile`:

1. `DescribeXml` → `conf/describe.xml`
2. `DescribeResourcesProperties` → `conf/resources/resources.properties`
3. `AdapterProperties` → `adapter.properties`
4. `Manifest` → `manifest.txt`
5. `PakResourcesProperties` → pak-level `resources.properties`
6. `Version` → `version.txt`

Plus `DashboardJson.File` for dashboards. **A `BuilderFile` fully determines a deployable pak.**

### Revised Tier 1 recommendation

VCF-CF's Tier 1 should be implemented as:

1. **Authoring layer**: VCF-CF receives a design (UI form, YAML, API)
2. **Translation layer**: produces a `BuilderFile` Kotlin object (or its JSON equivalent — they are 1:1, deserializer is in-jar)
3. **Validation**: `BuilderFile`-side via `BuilderFileValidation`, then `DescribeXml.validateSchema()` on the emitted describe
4. **Emission**: load `mpb_adapter-*.jar` in-process, call the 6+1 `IWritableFile` writers
5. **Pak**: zip the result with the binary icon → deployable Track A `.pak`

This replaces the previous "or just build it ourselves" fallback with "use the shaded runtime jar". Implementation cost for Tier 1 is now dominated by the **authoring UX**, not the artifact generation.

### Tier 1 promotion-to-Tier-2 triggers — now empirically bounded

Based on the Pass 7 enumeration, a design needs to be promoted to Tier 2 if any of these hold:

**Source-side**:
- Non-HTTP collection (`IBuilderSource.Type` has only HTTP)
- Authentication beyond SESSION_TOKEN / BASIC / CUSTOM (no OAuth2, Kerberos, mTLS with cert refresh, etc.)
- Stateful collection (persistent connections, subscriptions, streaming)

**Transform-side**:
- Any value transform other than BASE64 (`BuilderFunction` is `{BASE64, NONE}` only)

**Describe-side** (cannot be expressed in `DescribeAdapterKind`):
- `<CapacityDefinitions>` (capacity/time-remaining model)
- `<Policies>` / `<PolicyMetrics>` (OOTB policy badges/thresholds)
- `<CustomGroupMetrics>` (custom-group rollups)
- `<Actions>` / `<Methods>` (user-invokable actions)
- `<LicenseConfig>` / `<HAConfig>` (platform integration)
- `<ProblemDefinitions>` (legacy alert surface — superseded by Symptoms in MPB)
- Metric-threshold symptoms (MPB symptoms are `eventMsg`-only)
- Multi-state alerts (MPB `DescribeAlertDefinition` is single-state)

**Config-side**:
- Config-param types other than STRING / INTEGER / SINGLE_SELECTION (no BOOLEAN, no FILE, no ENCRYPTED_STRING beyond credentials)

These are now **objective tests**: VCF-CF can statically determine "is this design Tier 1 expressible" by checking against this list before emission.

### Updated coverage estimate

- **Tier 1 (MPB design generation)**: ~85% strategic / ~70% executable. The architecture is now de-risked; remaining work is the BuilderRelationship + BuilderEvent + BuilderQuery details (the parts of the BuilderFile not enumerated in Pass 7).
- **Tier 2 (native adapter generation)**: ~50% (unchanged; alert/capacity/policy still untouched on the describe side).

---

## Pass 8 update (2026-05-16) — alert framework grammar enumerated

The Pass 6 #2 priority — "inventory `<SymptomDefinition>`/`<Condition>` expression grammar" — is now **DONE**. Full grammar documented in `spec/08-alerts-symptoms-recommendations.md`.

**Key takeaways**:

- 6 Condition types: `metric` (static + dynamic-via-reference via `targetKey`/`thresholdType`), `dtmetric`, `htmetric`, `property`, `msg_event` (regex-able), `fault`.
- 5 severities: `Info`, `Warning`, `Immediate`, `Critical`, `Automatic` (case-insensitive on wire).
- 11 operators: `=`, `!=`, `<`, `<=`, `>`, `>=`, `above`, `below`, `contains`, `equals`, `regex`. Plus `and`/`or` at the SymptomSet level only.
- Compound symptom logic via `<SymptomSets operator="and|or">` wrapping multiple `<SymptomSet>` — full two-level boolean over named symptoms with relationship-scoped evaluation (`applyOn=self|child|descendant`).
- AlertDefinition.state is singular in practice (0 multi-state alerts across 631 inspected). Authors emit multiple AlertDefinitions with different ids for severity ladders. **Matches the MPB-runtime emission model** (Pass 7).
- AlertDefinition `type` and `subType` are platform-owned int codes (not in describe.xml). Default unknown to (15, 22).
- **Adapters NEVER programmatically raise alerts** — the entire framework is declarative. Adapters push metrics/properties/events; the platform evaluates declared symptoms. This means VCF-CF can fully generate alert frameworks at SPEC time — no per-adapter alert code beyond data emission.

### Updated Tier 1 → Tier 2 promotion-trigger list (alert axis)

Adds to the Pass 7 list:

- Metric-threshold symptoms (`type="metric"`) — Tier 2
- Property comparisons (`type="property"`) — Tier 2
- Dynamic-threshold-via-reference (`thresholdType="metric|property"`) — Tier 2
- Hard-threshold capacity (`type="htmetric"`) — Tier 2
- Fault-event symptoms (`type="fault"`) — Tier 2
- Compound boolean (`<SymptomSets>` or multi-`<Symptom>` `<SymptomSet>`) — Tier 2
- Relationship-scoped (`applyOn="child"|"descendant"`) — Tier 2
- Per-instance evaluation (`instanced="true"`) — Tier 2

### Coverage delta

- **Tier 2 SPEC**: ~50% → ~62% (alert framework fully documented; still missing capacity/policy/classloading).
- **Tier 1 recommendations**: unchanged (~85%).

---

## Pass 9 update (2026-05-16) — `vcf-ops-data-sdk` characterized; legacy SDK is still the universal contract

The Pass 6 #3 priority — "characterize `com.broadcom.ops.data.*` data SDK BEFORE VCF-CF commits its Tier 2 abstraction layer" — is now **DONE**. Full analysis in `analysis/per-adapter/vcf-ops-data-sdk.md`.

**Key takeaway — reassuring**: the SDK is NOT the modern successor to `vrops-adapters-sdk.jar`. It's a narrow specialty middleware — **a Reactive-Streams subscriber for vCenter PerformanceManager stats streams** — that sits IN THE MIDDLE of the data pipeline. The adapter still egresses through the legacy SDK at the end of each collection cycle. Evidence:

- Shipped in only **1 of 39 KEEP-C paks** (vSphere only) across both Broadcom-internal and marketplace adapters.
- Version stuck at **`1.0-SNAPSHOT` since April 2022** — 4 years stale.
- The "abstract" `SdkClient` base carries `VcResource` + `VcBindingsManager` fields — vCenter-shaped from the start.
- Uses legacy `com.integrien.alive.common.adapter3.Logger` everywhere.
- Pushes results via legacy `addMetricData(ResourceKey, ...)` after draining its in-memory store.

### What the SDK DOES signal about platform direction

Despite its narrow scope, the architectural patterns visible are clearly the **platform's internal data infrastructure direction**:

1. **Reactive Streams** as the in-process data-flow primitive.
2. **Multi-destination routing** (`Routes` enum: ops / database / kafka) — Operations has a Kafka backplane for stats.
3. **Pre-aggregated `Value`** (min/max/avg/sum/count per bucket) — 10-100× smaller wire than raw samples.
4. **Declarative `QuerySpec` JSON** loaded from classpath — collection is configuration, not code.

### Revised recommendation for `vcfcf-adapter-base.jar`

**De-risk #4 from the original "what we know less well" list**:

- **Do** build the Tier 2 abstraction atop the legacy `vrops-adapters-sdk-2.2.jar` (aria-ops-core decomposition, Pass 3).
- **Don't** bundle `vcf-ops-data-sdk` in the shared base jar (40MB; appliance classpath doesn't carry it universally; only vSphere needs it).
- **Do** leave a subscription hook in `LiveCollector` so a generated adapter can implement `getCurrentMetrics()` as "drain-from-buffer" rather than only "pull". Future stream-based sources plug in cleanly without architectural refactoring.
- **Do** treat `vcf-ops-data-sdk` as a per-adapter optional dep that gets bundled only when the target source is vCenter stats.
- **Re-evaluate in 6-12 months**: if a `vcf-ops-data-sdk-2.x.jar` ships and starts appearing in non-vSphere paks, the calculus changes.

### Removed risk

Pass 6 noted: "**Risk: building atop the legacy SDK just as VMware completes a migration**". The Pass 9 evidence says **the migration is not underway** — the legacy SDK remains the universal contract that all 39 KEEP-C paks compile against. **This risk is now eliminated** for the foreseeable horizon.

### Coverage delta

- **Tier 2 SPEC**: ~62% → ~67% (modern-SDK direction characterized; abstraction-layer-choice de-risked).
- **Tier 1 recommendations**: unchanged.

### Remaining priorities for further passes

After Passes 7-9, the next-highest leverage open items (out of the original Pass 6 list and items surfaced during 7-9):

1. **Capacity model** — `<CapacityDefinition>` + Workload/Stressed/Idle/Waste/UsableCapacity/Reclaimable/TimeRemaining settings. Surfaces snuck in during Pass 8 (mongodb has the full ladder). Major describe.xml surface; needed for Tier 2 completeness on the "feed the capacity pages" axis.
2. **Policy model** — `<Policies>`, `<PolicyMetrics>`, `<OotbPolicy>`. Needed for adapters that ship default policy badges.
3. **MPB `BuilderEvent` / `BuilderAlert` / `BuilderQuery` schemas** — the parts of `BuilderFile` not enumerated in Pass 7. Needed for full Tier 1 generation completeness.
4. **`DescribeAttributeDataType` enum values + `DescribeUnitType` catalog** — to know what metric data types and units Tier 1 can declare.
5. **Platform's alert `type` / `subType` int → category lookup table** (from Pass 8 open follow-ups).
6. **`PowerState` + `Icon` decision-tree elements** — UI affordance.

Tier 2 SPEC self-assessment at ~67% complete after Pass 9. Three more passes (capacity, policy, MPB BuilderEvent/Alert) would push it to ~80% — likely sufficient for generator-ready VCF-CF design work.
