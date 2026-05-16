# MPB pak insights for VCF-CF — deep-dive

**Date**: 2026-05-15
**Source**: `analysis/decompiled/mpb-adapter/mpb-adapter/lib/mpb_adapter-9.0.1-patch-1.jar` — the **MPB runtime engine**, 15,440 classes.

This document captures findings specifically useful for the **VCF-CF
Tier 1 (MPB design generator)** initiative. The MPB runtime is much
deeper than I initially assumed in pass 1 — there's substantial prior
art VCF-CF can leverage rather than reinvent.

## Top-line: VCF-CF can REUSE the MPB runtime's existing subsystems

The MPB runtime jar contains:

1. **A complete design-execution engine** (Kotlin)
2. **A code-generation subsystem** (`com.vmware.mpb.generation.*`) that emits dashboard JSON, `adapter.properties`, and other artifacts from a design
3. **A validation engine** (`com.vmware.mpb.impl.validation.BuilderFileValidation`)
4. **An HTTP-chained-request engine** for sequencing dependent HTTP calls
5. **An external-resource-property-pusher** (cross-MP attachment to foreign resources)
6. **A unit-conversion system**
7. **A BuilderFunction transformation system** (BASE64, etc.)

VCF-CF Tier 1 should evaluate **using mpb_adapter-*.jar as a library**
rather than rebuilding parallel implementations.

## Runtime architecture

MPB's entry point (`com.vmware.mpb.MPBAdapter` in the runtime jar — different from the thin shim in `mpb-adapter.jar` at root) **uses `aria-ops-core` internally** — confirmed by the presence of `getLiveDataCollector` method (the Discoverer/Tester/LiveCollector/HistoricalCollector SPI). The MPB runtime IS a BlueMedora-pattern adapter, with the design JSON acting as a runtime-supplied "implementation".

```
mpb-adapter (deployment)
├── mpb-adapter.jar       — thin shim implementing AdapterInterface3 (40 classes)
└── lib/
    ├── mpb_adapter-9.0.1-patch-1.jar (15,440 classes)
    │   ├── com.vmware.mpb.MPBAdapter           ← runtime adapter (extends UnlicensedAdapter from aria-ops-core)
    │   ├── com.vmware.mpb.BuilderFunction      ← value-transform enum
    │   ├── com.vmware.mpb.BuilderFunctionPart  ← composable design parts
    │   ├── com.vmware.mpb.model.BuilderConfigParam — design param model
    │   ├── com.vmware.mpb.impl.AdapterConfiguration
    │   ├── com.vmware.mpb.impl.collect.http.HttpCollector
    │   ├── com.vmware.mpb.impl.collect.http.HttpChainedRequestUtils
    │   ├── com.vmware.mpb.impl.collect.http.HttpEventMapper
    │   ├── com.vmware.mpb.impl.collect.http.HttpExternalResourcePropertyAdder
    │   ├── com.vmware.mpb.impl.collect.http.RequestOrderer
    │   ├── com.vmware.mpb.impl.validation.BuilderFileValidation
    │   ├── com.vmware.mpb.generation.IWritableFile
    │   ├── com.vmware.mpb.generation.metadata.AdapterProperties
    │   ├── com.vmware.mpb.generation.dashboards.DashboardJson
    │   └── + Kotlin stdlib, jackson, woodstox, log4j, msv shaded in
    └── vcops-suiteapi-client-2.2-all.jar
```

## What an MPB design declares (by the runtime's model classes)

### `BuilderConfigParam` — per-adapter-instance config parameters

The design declares config parameters the platform's UI renders in
the "create adapter instance" form. Fields:

```kotlin
class BuilderConfigParam(
    val id: String,
    val key: String,
    val label: String,
    val type: DataType,        // STRING | INTEGER | SINGLE_SELECTION
    val advanced: Boolean,     // hidden under "Advanced Settings"
    val default: String,
    val description: String,
)
```

Only **three data types** observed (STRING, INTEGER, SINGLE_SELECTION).
Notable: no BOOLEAN type — booleans are presumably handled as
SINGLE_SELECTION enums.

### `BuilderFunction` — value transformations

An enum of built-in value transforms. So far observed members:
`BASE64` (decode), `NONE`. Each has a `Function1<String, String>`.

Implication: MPB designs can declare "apply BASE64 decoding to this
field before storing it as a metric". The set of available transforms
is bounded by the runtime's enum — VCF-CF's Tier 1 generator must
respect this set.

### `BuilderFunctionPart` — composable design fragments

The "parts" model suggests designs are built from reusable composable
pieces (each Part declares a function, resolved at design time). The
`resolveFunctions` and `sanitizeFunction` methods imply a static
analysis pass over the design before execution.

### `DataModelList` + `DataModelAttribute` — extracted-data model

```kotlin
record DataModelList(
    id: String,
    label: String,
    key: List<String>,         // pipe-path components
    attributes: List<DataModelAttribute>,
    parentListId: String,      // hierarchical reference!
)

record DataModelAttribute(
    id: String,
    label: String,
    key: List<String>,         // pipe-path components
    example: String,           // sample value for UI preview
)
```

**Key insight**: `parentListId` makes `DataModelList` **hierarchical**.
A design can declare nested data extraction — e.g.,
"MongoDB cluster → its replica sets → each replica set's members".
The runtime sequences HTTP requests accordingly via `HttpChainedRequestUtils`.

The `example` field on attributes is a UI affordance — the designer
captures a sample value to display in the design preview.

## HTTP collection model

### `HttpCollector` orchestrates collection

Collects from HTTP endpoints; `collectResources(...)`, `addEvents(...)`,
`extendResources(...)`. Kotlin coroutines visible in the suspend
function names. Supports async-flat-map for parallel request fan-out.

### `HttpChainedRequestUtils` — chained requests

**This is the most important runtime capability for design authors**.
Designs can express:

```
Step 1: GET /api/clusters       → list of cluster IDs
Step 2: for each cluster:
    GET /api/clusters/{id}/stats  → metrics for that cluster
Step 3: for each cluster:
    GET /api/clusters/{id}/members → child resources
```

The runtime handles:
- Parameter substitution from step N response into step N+1 URL
  (per `generateParamSubstitutionKey` method)
- Async fan-out (per `asyncFlatMap` / `asyncMap` extensions)
- Result aggregation

**Implication for VCF-CF**: any system whose API requires multi-step
collection (list → detail per item) is naturally expressible in MPB.
The Tier 1 generator should produce designs that use chained requests
when the underlying API has list/detail structure.

### `HttpExternalResourcePropertyAdder` — cross-MP attachment, named explicitly

The runtime has a class named **`HttpExternalResourcePropertyAdder`**
in `com.vmware.mpb.impl.collect.http`. This is the **MPB-side
implementation** of "stitch metrics/properties onto resources owned
by other MPs".

The class exists, has dependencies on `HttpCollector` and result
mappers, and is part of the standard collection flow. MPB designs
can:

1. Declare a "this attribute should be attached to a foreign resource of kind X identified by Y"
2. The runtime resolves the foreign resource at collection time
3. Pushes the property to the foreign ResourceKey

**This is built-in MPB capability**. VCF-CF Tier 1's design language
must expose this — the generated designs can attach to vSphere VMs
(or any other foreign kind) declaratively.

### `RequestOrderer` — collection sequencing

Determines the order HTTP requests are issued. Critical for designs
where some requests must complete before others (dependency graph).

## Validation engine — `BuilderFileValidation`

The runtime has a `BuilderFileValidation` class + `BuilderFileValidationException`. **Designs are validated at install / scan time**. VCF-CF Tier 1 should:

1. Use this validator to gate generated designs before deployment
2. Mirror its rules in the generator to fail-fast on invalid designs

The validator is in `com.vmware.mpb.impl.validation` — exposed for
external callers.

## Generation engine — `com.vmware.mpb.generation.*`

This is a **complete code-generation subsystem inside the MPB runtime
jar**. Classes observed:

- `IWritableFile` — interface for any generated file (`getFileName`,
  `getFileString`, `write(path)`)
- `AdapterProperties` (implements `IWritableFile`) — **generates the
  `adapter.properties` file from a `BuilderFile`** (the in-memory
  design representation)
- `dashboards/DashboardJson` — generates dashboard JSON files from
  design metric declarations:
  - `DashboardJson.Dashboard`, `DashboardJson.DashboardBuilder` —
    builder pattern for dashboards
  - `DashboardJson.Column`, `Coords`, `Entries`, `Widget`,
    `InteractionType` — dashboard widget model
  - `withMetrics(...)`, `withAdditionalColumns(...)` — fluent API
  - Lots of inlined lambda classes (Kotlin functional style)

**This means**: given an in-memory `BuilderFile` (the design), the
MPB runtime can generate adapter.properties + dashboards directly.
VCF-CF Tier 1 doesn't need to rewrite these — it can call into this
existing subsystem.

It's strongly likely (though not yet verified) that the generation
subsystem also produces `describe.xml`. If so, **VCF-CF Tier 1 can
effectively be: produce a `BuilderFile` representation of the design,
then call mpb-generation to emit the deployable native MP**.

## Unit conversion — `CommonUnits` + `ConvertableUnit`

A unit-conversion infrastructure. Designs declare metric units
abstractly; the runtime handles display conversions (bytes ↔ MB ↔
GB ↔ TB, etc.).

VCF-CF generator should use these unit codes (not hardcoded strings)
when emitting metric declarations.

## Implications for VCF-CF Tier 1 (MPB design generation)

### What MPB designs naturally express well

✅ **HTTP-driven collection** — REST/SOAP/arbitrary HTTP is first-class.
✅ **Chained / hierarchical extraction** — list/detail patterns,
   parent-child resource trees.
✅ **Cross-MP attachment** — `HttpExternalResourcePropertyAdder` is
   built-in.
✅ **Per-instance configuration** — STRING / INTEGER / SINGLE_SELECTION
   params via `BuilderConfigParam`.
✅ **Value transformations** — limited set (BASE64, etc.) via
   `BuilderFunction`.
✅ **Auto-generated dashboards** — designs declare metrics; runtime
   emits dashboard JSON.
✅ **Unit conversion** — declare units; runtime handles display.

### What MPB designs DON'T naturally express well

❌ **Non-HTTP collection** — no evidence of gRPC, JDBC, native binary
   protocols in the runtime. If the target system requires non-HTTP,
   MPB is the wrong tool — generate a Track C adapter directly.
❌ **Complex stateful logic** — the BuilderFunction set is small.
   Anything beyond text transformation requires going to Track C.
❌ **Custom relationship inference** — relationship declarations are
   pre-canned. Complex pairing logic (BlueMedora's ExternalRelationship
   IP-and-name match) is not visible in the BuilderFunction surface;
   may not be expressible.
❌ **Actions** — no evidence the MPB runtime supports user-invokable
   actions on the monitored system. Designs are collection-only.

### Recommended VCF-CF Tier 1 architecture

```
User design specification (UI or YAML)
    │
    ▼
VCF-CF design transformer  ──── normalizes to ──→  BuilderFile (MPB's in-memory representation)
    │
    ▼
mpb-generation.AdapterProperties + DashboardJson + (likely) describe.xml
    │
    ▼
Deployable native .pak (Track A content pack)
    │
    ▼ deploys onto appliance with mpb-adapter installed
    │
    └─ executed at scan time by mpb_adapter-*.jar runtime
       which calls back into VCF-CF design via HttpCollector / HttpChainedRequestUtils / HttpExternalResourcePropertyAdder / etc.
```

**Strongly recommended**: have VCF-CF target the existing `BuilderFile`
model class as its output. The generation subsystem in mpb-adapter
runtime is the cheapest path to a working .pak.

If `BuilderFile` is unstable / unfit, the fallback is to generate
adapter.properties + describe.xml + dashboards directly from VCF-CF
templates. Either way, the `BuilderFunction` and `BuilderConfigParam`
DSL is the canonical vocabulary — Tier 1 should be opinionated about
matching it.

### Recommended VCF-CF Tier 2 boundary

If the user's target system can't be expressed in MPB (non-HTTP,
needs complex state, custom auth flows, actions, etc.), promote
to Tier 2 (native Java adapter generation). The trigger conditions
to promote are now empirically clear:

- Non-HTTP collection protocol → Tier 2
- Stateful collection (e.g., must maintain a connection / subscription) → Tier 2
- User-invokable actions required → Tier 2 (via NMP TaskHandler or legacy ActionableAdapterInterface)
- Complex relationship inference (foreign-resource lookup beyond simple identifier match) → Tier 2

## Other notable findings

- **MPB runtime ships shaded copies** of Jackson (JSON), Woodstox (XML), Kotlin stdlib, log4j, Apache MSV (Multi-Schema Validator). It does NOT rely on platform-provided versions of these libs.
- **Kotlin coroutines** are used heavily (visible in suspend lambdas). MPB collection is async.
- **`com.bluemedora.vropscertificatechecker` is bundled** — the runtime can validate cert chains using BlueMedora's cert-checker library.
- **fastdoubleparser** (ch.randelshofer.fastdoubleparser) is bundled — for fast numeric parsing in metric values.

## Open questions for further investigation

1. **Does `mpb-generation` emit `describe.xml`?** Suspected yes (since adapter.properties + dashboards are both emitted; describe.xml is the third leg of the deployable trio). Confirm by listing all `IWritableFile` implementations.
2. **What's the full `BuilderFunction` enum set?** Only BASE64 and NONE observed in javap output; likely more (URL encode/decode, regex, JSONPath, XPath probably).
3. **What's the relationship between MPB's runtime `BuilderFile` model and the design JSON wire format (`builderJson` parameter)?** Probably 1:1 (the JSON is the serialized form of BuilderFile). If so, VCF-CF can target the JSON directly.
4. **Does the MPB runtime emit a `describe.xml` per design at install time, or is it lazy at scan time?** Affects deployment ergonomics — if eager, the design must be present at install; if lazy, the design can be updated post-install.
5. **Authentication flows**: only HTTP credential schemes visible. Does the runtime support OAuth2 / Kerberos / mTLS / token refresh? Need to check.

---

## Pass 7 update (2026-05-16) — open questions resolved

### Q1 resolved: YES — mpb-generation emits describe.xml (CONFIRMED)

`com.vmware.mpb.generation.describe.DescribeXml` exists and is constructed directly from `BuilderFile`:

```kotlin
class DescribeXml(builderFile: BuilderFile,
                  properties: DescribeResourcesProperties) : IWritableFile {
    fun validateSchema()                    // built-in XSD validation
    override fun write(directory: String)
}
```

The entire describe.xml element tree is represented as `Describe*` classes under `com.vmware.mpb.generation.describe.components` (24 classes — one per top-level element). See `spec/02-describe-xml.md § Describe-xml in-memory model` for the full mapping. **This is the highest-leverage finding from the investigation, now fully confirmed.**

The deployable artifact set is produced by exactly **6 `IWritableFile` implementations**, all taking `BuilderFile` as the sole input: `DescribeXml`, `DescribeResourcesProperties`, `AdapterProperties`, `Manifest`, `PakResourcesProperties`, `Version`. Plus `DashboardJson.File` for dashboards. Together: a `BuilderFile` fully determines a deployable pak.

### Q2 resolved: BuilderFunction is exactly {BASE64, NONE}

`javap -p com.vmware.mpb.BuilderFunction` confirms — the enum has only two values:

```kotlin
enum class BuilderFunction(val key: String, val run: (String) -> String) {
    BASE64,    // decode
    NONE,
}
```

**Major Tier 1 constraint**: any transformation beyond a base64-decode requires Tier 2 promotion. No URL encode/decode, no regex extraction, no JSONPath, no XPath, no concatenation — at the `BuilderFunction` layer. Some of that may exist in other layers (`BuilderQuery*` for response parsing, `BuilderFunctionPart` for composition) but the value-transform vocabulary itself is tiny.

### Q3 partially resolved: BuilderFile IS the wire format (Jackson deserializer present)

`BuilderFileDeserializer` exists and is Jackson-based. `BuilderFile.toJsonString()` is a public method. The JSON wire format and the in-memory model are 1:1.

**Implication**: VCF-CF can target either the JSON string directly OR the Kotlin object — same artifact. Targeting the object (and serializing with `toJsonString()`) is safer because the deserializer enforces validation.

### Q5 partially resolved: HTTP auth has exactly 3 types

`BuilderHttpAuthentication.AuthenticationType` is `{SESSION_TOKEN, BASIC, CUSTOM}`. CUSTOM is the escape hatch (presumably accepts a raw header map), but token refresh / OAuth2 / Kerberos / mTLS are not first-class.

### Pass 7 — new findings beyond the open questions

#### Full `BuilderFile` schema (the input to all generators)

```kotlin
data class BuilderFile(
    id: String,
    name: String,
    pakSettings: BuilderPakSettings,
    source: IBuilderSource,                       // currently only HTTP variant exists
    constants: List<BuilderConstant>,
    relationships: List<BuilderRelationship>,
)
```

The 6 top-level fields. Notice **relationships are top-level** (not nested under source) — they cross-reference resources from multiple sources potentially. Constants are also top-level — shared substitution values across requests.

#### `BuilderPakSettings` — pak-level metadata

```kotlin
data class BuilderPakSettings(
    adapterFolder: String, propertiesFile: String,
    adapterInstanceResourceKind: String, substitutionValue: String,
    entryClass: String, classPathAddition: String,
    tagRelativeKind: String, tagRelativeLabel: String,
    tagWorldKind: String, tagWorldLabel: String,
    worldAggregateMetricGroupKey: String, worldAggregateMetricGroupLabel: String,
    author: String, name: String, adapterKind: String, version: String,
    description: String, icon: String,
    collectionInterval: Int,
)
```

**Key fields VCF-CF must populate**: `adapterKind` (the kind key), `version`, `author`, `description`, `icon` (path), `collectionInterval`. **Tag-related fields** are first-class — every MPB pak gets relative-tag and world-tag synthetic resource kinds; the runtime auto-generates these from the design.

#### `HttpBuilderSource` — the only concrete `IBuilderSource` implementation

`IBuilderSource.Type` enum has exactly **one value: HTTP**. MPB v1 is HTTP-only at the source level. **This is a definitive Tier 1 bound** — non-HTTP collection (JDBC, gRPC, SNMP, syslog tail, file-watching, etc.) is Tier 2 territory, no exceptions.

```kotlin
class HttpBuilderSource(
    basePath: String, testRequestId: String,
    authentication: BuilderHttpAuthentication,
    configuration: List<BuilderConfigParam>,           // per-instance config UI
    requests: Map<String, BuilderRequest>,             // keyed catalogue
    resources: List<BuilderHttpResource>,
    externalResources: List<BuilderHttpExternalResource>,    // cross-MP attachment
    events: List<BuilderEvent>,
)
```

Notable:
- `testRequestId` — a specific request the platform calls during the
  test-connection / `Tester` SPI step. Designs declare which request
  is the health check.
- `requests` is a **map keyed by ID**, not a list — request IDs are
  the addressable handles other parts of the design reference.
- `externalResources` are first-class — declaring a foreign-resource
  reference is a separate concern from declaring own resources.

#### `DescribeAdapterKind`'s child list IS the entire Tier 1 surface

The MPB-runtime `DescribeAdapterKind` accepts these children — and only these:

```
adapterInstanceResourceKind     (special-cased)
credentialKinds                 (List)
resourceKinds                   (List)
relativeTagKind, worldTagKind   (synthetic tag kinds)
discoveries                     (List)
symptoms, alerts, recommendations    (Lists; each via I* interface)
traversalSpecs                  (List — declarative topology)
unitTypes                       (List)
```

**Notable absences vs. the full describe.xml schema** (these CANNOT be expressed in a Tier 1 design and force Tier 2 promotion):

- `<ProblemDefinitions>` — older alert-evaluation surface
- `<CapacityDefinitions>` — capacity / time-remaining model (vSphere uses heavily)
- `<Policies>` / `<PolicyPackages>` — out-of-the-box policy badges, thresholds
- `<CustomGroupMetrics>` — for custom-group rollups
- `<LicenseConfig>`, `<HAConfig>` — platform integration
- `<Actions>` / `<Methods>` — user-invokable actions
- `<ResourceAttribute isProperty>` mixed with metrics in arbitrary order (Tier 1 may impose its own ordering)

These define the **Tier 1 → Tier 2 promotion triggers** at the describe-surface level (in addition to the runtime-side triggers like non-HTTP collection, stateful sessions, complex transformations).

#### Alert framework via MPB is event-driven only

`DescribeSymptomStateCondition` has a single field: `eventMsg: String`. MPB-generated symptoms fire on **event matches**, not metric thresholds. The full describe.xml schema supports metric-threshold conditions (mongodb has 214 of them) but the MPB emission path doesn't expose them.

Designs needing metric-threshold symptoms must promote to Tier 2.

#### Validation is callable

`DescribeXml.validateSchema()` runs XSD validation using shaded MSV. VCF-CF should make this the final gate before emitting a pak — it's free, it's authoritative, and it's the same check the appliance runs at install time.

### Revised Tier 1 architecture (post-Pass 7)

```
User design (UI form OR YAML OR API call)
    │
    ▼  VCF-CF builds a BuilderFile  ──→  BuilderFile.toJsonString()
    │                                    written to <pak>/conf/builder/<id>.json
    │
    ▼  Optional: call mpb_adapter-*.jar's emission pipeline IN-PROCESS
    │  to produce describe.xml / adapter.properties / manifest.txt /
    │  resources.properties / version.txt / dashboards from the BuilderFile
    │  (in-process: VCF-CF service loads the jar via classloader, calls IWritableFile.write)
    │
    ▼  Or simpler: ship the BuilderFile JSON in the pak and let the
    │  appliance's mpb-adapter generate at install/scan time
    │
    ▼
Deployable .pak (Track A content pack — declarative-only inner archive)
    │
    ▼ install onto appliance
    ▼ scan time: mpb-adapter loads the BuilderFile, executes via HttpCollector
```

**Two valid paths**:
1. **Pre-emit at build time** (in VCF-CF): VCF-CF loads `mpb_adapter-*.jar`, builds a `BuilderFile`, calls each `IWritableFile.write()`, packages the result. Pak ships fully-generated describe.xml and the appliance treats it like any other Track A pak. Pros: appliance doesn't need to be running mpb-adapter at the version VCF-CF generated against; the pak is self-describing.
2. **Defer to install time**: VCF-CF ships only the `BuilderFile` JSON; appliance's installed `mpb-adapter` does the emission. Pros: smaller pak, generated artifacts always match the runtime version. Cons: appliance must have a compatible mpb-adapter installed.

Recommend path 1 for predictability + auditable artifacts. Use shaded `mpb_adapter-*.jar` in VCF-CF's build pipeline.

### New open questions (Pass 7 → future work)

1. **Does `DescribeXml` actually emit dashboards too, or is that a separate orchestrator?** `DashboardJson.File` is a separate `IWritableFile`; need to find the orchestrator that calls all 6+1 emitters in sequence (a `PakBuilder`-style class — not yet found in this enumeration; may not exist as a single class, may be the caller's responsibility).
2. **`BuilderRelationship` schema** — top-level relationships were not enumerated this pass.
3. **`BuilderEvent` / `BuilderEventMatcher` / `BuilderAlert` schema** — the alert/event side of the design. The MPB emission supports event-driven symptoms; full event-matcher grammar TBD. (Will be touched in Pass 8.)
4. **`DescribeAttributeDataType` enum values** — the in-memory data-type enum mapped from describe.xml's `dataType` attribute. Needs enumeration to know what metric data types Tier 1 can declare.
5. **`DescribeUnitType` enum vs. legacy unit strings** — does MPB use the same unit catalogue as legacy adapters, or its own?
