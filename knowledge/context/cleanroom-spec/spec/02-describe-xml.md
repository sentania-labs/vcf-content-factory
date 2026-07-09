# 02 — `describe.xml` Declarative Model

**Status**: DRAFT (skeleton — pass 1 evidence is limited; expand in pass 2)
**Schema**: `http://schemas.vmware.com/vcops/schema`
**Schema definition**: `<adapter>/conf/describeSchema.xsd` (per-adapter copy, observed identical bytes across adapters; treat as the canonical schema reference)
**SDK in-memory model**: `com.integrien.alive.common.adapter3.describe.*` (161 classes)

## Purpose

`describe.xml` is the **declarative manifest** for an adapter kind.
It registers with the platform:

- The adapter's identity (`AdapterKind`)
- All resource kinds the adapter manages, with their identifiers,
  attributes (metrics + properties), relationships, icons, capacity
  models, policy models
- Credential kinds the adapter accepts
- Discovery descriptors
- Actions the adapter exposes
- Methods the actions are bound to
- Computed metrics
- Symptom / problem / recommendation definitions
- Alert transmission rules
- Capacity calculation rules
- Workload automation settings
- Policy badges
- License config
- HA config
- Traversal specs (UI navigation tree)
- OpenAPI extension declarations

Most of these are **optional**. A minimum-viable describe.xml needs
only `AdapterKind` + at least one `ResourceKind` (the adapter
instance).

## Root structure (skeleton)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind key="<adapter-kind>"
             nameKey="<localization-int>"
             version="<schema-version>"
             xmlns="http://schemas.vmware.com/vcops/schema"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xsi:schemaLocation="http://schemas.vmware.com/vcops/schema http://schemas.vmware.com/vcops/schema">

    <ResourceKinds>
        <ResourceKind .../>
        ...
    </ResourceKinds>

    <CredentialKinds>
        <CredentialKind .../>
    </CredentialKinds>

    <DiscoveryDescribes>
        <DiscoveryDescribe .../>
    </DiscoveryDescribes>

    <Actions>
        <Action .../>
    </Actions>

    <Methods>
        <Method .../>
    </Methods>

    <SymptomDefinitions>...</SymptomDefinitions>
    <ProblemDefinitions>...</ProblemDefinitions>
    <Recommendations>...</Recommendations>
    <CapacityDefinitions>...</CapacityDefinitions>
    <Policies>...</Policies>
    <CustomGroupMetrics>...</CustomGroupMetrics>
    <LicenseConfig>...</LicenseConfig>
    <!-- ... others as needed ... -->

</AdapterKind>
```

## `<AdapterKind>` attributes

- `key` — the adapter kind's stable identifier. Used by the platform
  to route everything (configure, collect, actions). Must be unique
  across all installed paks.
- `nameKey` — integer pointing into `resources/resources*.properties`
  for the localized display name.
- `version` — schema version; integer. Observed values:
  - `8` — mpb-adapter
  - `9` — vim

  Schema is versioned. Adapters can target a specific schema version.
  Schema diffs across versions not yet inventoried; the `isSingleton`
  ResourceKind attribute observed on a schema-v9 adapter (vim) may
  be a v9 addition.

## `<ResourceKind>` (skeleton; expand in pass 3+)

```xml
<ResourceKind key="<kind-key>"
              nameKey="<int>"
              type="<int>"
              isSingleton="true|false (optional)">
    <ResourceIdentifier
        dispOrder="<int>"
        key="<id-key>"
        nameKey="<int>"
        required="true|false"
        type="string|integer|..."
        hidden="true|false (optional)"
        readOnly="true|false (optional)"/>
    <!-- ... ResourceAttribute, ComputedMetrics, Icon, PowerState, ResourceGroup, etc. ... -->
</ResourceKind>
```

### `type` attribute values (observed)

- `7` — adapter instance resource (the per-configured-instance container)
- Other values to be inventoried in pass 3+ (likely: regular resource,
  container, computed, etc.)

### `isSingleton` (observed in vim)

When `true`, the platform enforces exactly one instance of this
resource kind per appliance. Used for adapter-instance resource
kinds when a single configured instance suffices (e.g., vim's
`VMWARE_INFRA_MANAGEMENT_INSTANCE`, which represents the appliance's
own integration with the VCF infrastructure).

Absent or `false` — multiple instances allowed (e.g., mpb-adapter's
`ManagementPackBuilderAdapterInstance`).

### Identifier attributes

- `dispOrder` — display order in UI
- `key` — stable identifier name (often UPPERCASE for adapter-instance
  identifiers, e.g., `COLLECTOR_UUID`)
- `required` — whether the identifier must be set
- `type` — primitive type for the identifier value
- `hidden` (optional) — when `true`, the identifier is not shown in
  the configuration UI form (used for system-supplied identifiers
  like `COLLECTOR_UUID`)
- `readOnly` (optional) — when `true`, the identifier value cannot
  be edited after creation

## `<CredentialKind>` — see § 03

## `<DiscoveryDescribe>` — pass 2

Declares parameters the platform passes to `onDiscover()`. Mapped to
the SDK's `DiscoveryDescribe` and `DiscoveryParamDescribe`. Not
exercised by mpb-adapter (no `<DiscoveryDescribes>` block observed).

## `<Action>` and `<Method>` — see § 04

## Major declarative surfaces (not yet exercised — pass 2+ for evidence)

The SDK's `describe.*` package contains 161 classes covering far more
than the minimum surface. Inventoried by topic in
`analysis/sdk-survey/v2.2-public-api.md`. The major ones likely to
appear in production adapters:

- **Computed metrics** (`ComputedMetricDescribe`) — derived metrics
  calculated by the platform from collected primaries.
- **Capacity model** (`CapacityDefinitionDescribe`, plus 13+ settings
  types for buffer, time-remaining, idle, stressed, density, etc.) —
  feeds the Capacity / Demand pages.
- **Workload automation** (`WorkloadAutomationSettingsDescribe` + 8
  sub-types) — the DRS-equivalent algorithm settings consumed by
  Operations' workload-automation engine.
- **Policy** (`PolicyDescribe`, `PolicyPackageDescribe`,
  `PolicyMetricDescribe`, `OotbPolicyDescribe`) — out-of-the-box
  policy badges, metric thresholds, etc.
- **Symptoms / problems / recommendations / alerts** — the alert
  framework. Adapter declares symptom definitions; the platform
  evaluates them and triggers alerts.
- **Traversal specs** (`TraversalSpecKindDescribe`,
  `TraversalSpecExtensionKindDescribe`) — UI navigation tree
  definitions.
- **Icons** (`IconDescribe`, `IconConditionDescribe`, `IconCaseDescribe`)
  — per-state visual indication on resources in the UI.
- **OpenAPI** (`OpenAPIAdapterDescribe`) — declarative REST API
  extension surface (purpose TBD).

Each will be documented when first observed in an analyzed adapter.

## Describe-xml in-memory model — the MPB-runtime emission pipeline (Pass 7)

The MPB runtime jar (`mpb_adapter-9.0.1-patch-1.jar`) contains a
**complete describe.xml emission pipeline** that builds an in-memory
representation, validates it against the XSD, and serializes. This is
**the canonical reference** for what the schema actually accepts —
class names mirror element names 1:1, so the in-memory model
exhaustively documents the element tree.

### Root entry point

```kotlin
class DescribeXml(
    builderFile: BuilderFile,                          // the design
    properties: DescribeResourcesProperties,           // i18n strings
) : IWritableFile {
    fun validateSchema()                               // XSD validation
    override fun write(directory: String)              // serialize to disk
}
```

`DescribeXml` builds a `DescribeAdapterKind` from the `BuilderFile`,
delegates to per-element `Describe*` components, runs XSD validation
via shaded `com.sun.msv` (Multi-Schema Validator), and writes out the
XML.

### `DescribeAdapterKind` — root element model

```kotlin
class DescribeAdapterKind(
    adapterKindKey: String,
    adapterKindName: String,
    adapterInstanceResourceKind: DescribeAdapterInstanceResourceKind,
    credentialKinds: List<DescribeCredentialKind>,
    resourceKinds: List<DescribeResourceKind>,
    relativeTagKind: DescribeRelativeTagResourceKind,    // tagging support
    worldTagKind: DescribeWorldTagResourceKind,
    discoveries: List<DescribeDiscovery>,
    symptoms: List<IDescribeSymptomDefinition>,          // interface — extensible
    alerts: List<IDescribeAlertDefinition>,              // interface — extensible
    recommendations: List<IDescribeRecommendationDefinition>,
    traversalSpecs: List<DescribeTraversalSpec>,
    unitTypes: List<DescribeUnitType>,
)
```

### Component classes (one per describe.xml element)

In `com.vmware.mpb.generation.describe.components`:

| Class | XML element |
|---|---|
| `DescribeAdapterKind` | `<AdapterKind>` root |
| `DescribeAdapterInstanceResourceKind` | adapter-instance `<ResourceKind type="7">` (special-cased — wires credentialKind dependency) |
| `DescribeCredentialKind` / `DescribeCredentialField` | `<CredentialKind>` / `<CredentialField>` |
| `DescribeResourceKind` | `<ResourceKind>` |
| `DescribeResourceGroup` | `<ResourceGroup>` (metric grouping) |
| `DescribeResourceAttribute` | `<ResourceAttribute>` (metric or property) |
| `DescribeResourceIdentifier` | `<ResourceIdentifier>` |
| `DescribeAttributeDataType` | `dataType` enum (Companion `valueOf` mapping) |
| `DescribeComputedMetric` + `DescribeComputedMetricOperation` | `<ComputedMetric>` + its operation |
| `DescribeUnit` / `DescribeUnitType` | `<Unit>` / `<UnitType>` |
| `DescribeTraversalSpec` | `<TraversalSpec>` with nested `Path`/`PathMember`/`RelationType`/`RelationModifier` enums |
| `DescribeDiscovery` | `<DiscoveryDescribe>` |
| `DescribeRelativeTagResourceKind`, `DescribeWorldTagResourceKind` | tag-related resource kinds the platform synthesizes |
| `DescribeAlertDefinition` + `DescribeAlertState` + `DescribeAlertSymptomSet` + `DescribeAlertImpact` + `DescribeAlertRecommendation` | `<AlertDefinition>` and its children |
| `DescribeSymptomDefinition` + `DescribeSymptomState` + `DescribeSymptomStateCondition` | `<SymptomDefinition>` and its children |
| `DescribeRecommendationDefinition` + `DescribeRecommendationDescription` | `<Recommendation>` |

The common contract is `DescribeXmlObject.getXml(properties: DescribeResourcesProperties, indent: Int): String` — each component knows how to render itself.

### What this means

- **The in-memory model is the canonical reference** for the describe.xml schema as actually consumed. If something doesn't exist as a `Describe*` component in the runtime jar, the platform does not consume it via this path (note: legacy Track C adapters do not go through this path — they ship a hand-written describe.xml).
- **XSD validation is built-in** (`validateSchema()` + shaded MSV). VCF-CF's generator can reuse it.
- **The root element list above is exhaustive for what `DescribeAdapterKind` accepts as children**. Notable absences from the MPB-runtime emission path: `<ProblemDefinitions>`, `<CapacityDefinitions>`, `<Policies>`, `<CustomGroupMetrics>`, `<LicenseConfig>`. These are valid in the schema (legacy adapters emit them) but the MPB runtime doesn't generate them — Tier 1 designs can't express them. Tier 2 (hand-written or fully generated describe.xml) is required for those surfaces.
- **Alert framework via MPB is event-based only** (see § alert/symptom limits below).

### MPB-emission alert/symptom limits

- `DescribeSymptomStateCondition` has a **single field**: `eventMsg`.
  MPB-generated symptoms are **event-message-driven** only — there is
  no metric-threshold condition in the MPB emission model. Compare to
  mongodb's 214 metric-threshold symptoms (those were authored
  directly in describe.xml without going through MPB).
- `DescribeAlertDefinition` carries `state: DescribeAlertState`
  (singular). The platform schema permits multiple alert states; the
  MPB runtime emits one state per alert.
- Tier 1 designs needing metric-threshold symptoms or multi-state
  alerts must promote to Tier 2.

### Companion file emitters (the deployable artifact set)

The MPB runtime implements **6 `IWritableFile` classes** in total,
which together produce every deployable artifact except dashboards
(which have their own `DashboardJson.File` emitter, also from
`BuilderFile`):

| Class | File produced | Input |
|---|---|---|
| `DescribeXml` | `conf/describe.xml` | BuilderFile + DescribeResourcesProperties |
| `DescribeResourcesProperties` | `conf/resources/resources.properties` (the integer→string map for describe nameKeys) | BuilderFile (populated as describe components register strings) |
| `AdapterProperties` | `adapter.properties` | BuilderFile |
| `Manifest` | `manifest.txt` (pak-level) | BuilderFile |
| `PakResourcesProperties` | pak-level `resources.properties` | BuilderFile |
| `Version` | `version.txt` | BuilderFile |

All take `BuilderFile` as the sole input. **A single `BuilderFile`
fully determines a deployable pak**, modulo binary assets (icon PNGs).

## Resources / localization

- `<adapter>/conf/resources/resources.properties` — base
- `<adapter>/conf/resources/resources_<locale>.properties` —
  per-locale (10 locales observed in mpb-adapter: de, es, fr, ja,
  ko, zh_CN, zh_TW, plus base)

Keys are integers (`nameKey` values from describe.xml). The platform
selects the locale-appropriate file via `Dictionary` (the SDK's
localization resolver).

## Open questions / pass 2+

- Full inventory of `<ResourceKind type="N">` valid values
- Schema for `<ResourceAttribute>` and its sub-elements (instances,
  rollups, units)
- Schema for `<ResourceIdentifier>` `type` field values
- Schema for `<DiscoveryDescribe>` (mpb-adapter has none)
- Relationship declarations (parent/child, traversal extensions)
- Computed metric expression language
- Symptom definition expression language
