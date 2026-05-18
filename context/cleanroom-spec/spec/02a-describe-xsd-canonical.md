# 02a — describeSchema.xsd: the authoritative grammar (Pass 10)

**Status**: Pass 10 (2026-05-16) — reading the XSD directly.
**Source**: 3 variants observed in corpus:

| Schema version | Variant md5 | Lines | Adapters |
|---|---|---|---|
| 6.3.0 | `77e07585...` | 4629 | vim, VMwareInfrastructureHealthAdapter |
| 6.1.0 | `73140b85...` | 4547 | VrAdapter |
| 6.1.0 | `6e6d8323...` | 4561 | SupervisorAdapter |

**The CLAUDE.md "schemas are identical across adapters" assumption was wrong** — they're not. 6.3.0 adds `FavoriteGroups` types. The two 6.1.0 variants differ from each other in undocumented ways (file-size delta with same advertised version). **Treat 6.3.0 (vim) as canonical**; VCF-CF generator should target 6.3.0.

This document captures the **schema-permitted** surface — what's legal, not what's commonly authored. Several elements / attributes / enum values exist in the schema but were not observed in any analyzed adapter (or were observed and tagged in our notes as unsupported).

## Top-level `<AdapterKind>` children (19, all optional except ResourceKinds)

The schema uses `xs:all` so children may appear in **any order, each at most once**:

| Element | Required | Documented surface so far |
|---|---|---|
| `ResourceKinds` | ✅ required | spec/05 |
| `Names` | optional | **NEVER DOCUMENTED** |
| `CredentialKinds` | optional | spec/03 |
| `Discoveries` | optional | spec/02 (wrong name — was "DiscoveryDescribes") |
| `Methods` | optional | spec/04 |
| `Actions` | optional | spec/04 |
| `Recommendations` | optional | spec/08 |
| `CapacityDefinitions` | optional | **NOT YET DRAFTED** |
| `LaunchConfigurations` | optional | **NEW — NEVER DOCUMENTED** |
| `CustomGroupMetrics` | optional | **NEW** |
| `SymptomDefinitions` | optional | spec/08 |
| `AlertDefinitions` | optional | spec/08 |
| `TraversalSpecKinds` | optional | spec/07 |
| `TraversalSpecExtensionKinds` | optional | **NEW** |
| `Faults` | optional | **NEW — distinct from Condition type="fault"** |
| `BasePolicyAnalysisSettings` | optional | **NEW** |
| `UnitDefinitions` | optional | partial in spec/06 |
| `OOTBPolicies` | optional | **NEW** |
| `LicenseConfig` | optional | mentioned in spec/02 |
| `FavoriteGroups` | optional (6.3.0+) | **NEW** |

**`AdapterKind` attributes**:
- `key` (string, required)
- `nameKey` (int, required)
- `version` (xs:integer, required) — **THE VERSION IS AN INTEGER**, not a semver string. The MPB-runtime `BuilderPakSettings.version: String` may serialize an int as a string here, or there's a wire-format conversion. Verify.
- `handleMultiCollection` (bool, optional, default false) — VMware-internal

## Things the schema permits but the MPB runtime cannot emit (Tier 1→Tier 2 promotion triggers, expanded)

Adding to the Pass 7 / Pass 8 lists:

- **`<Names>`**: ad-hoc names not tied to ResourceKinds. Schema-allowed but never observed in analyzed adapters.
- **`<LaunchConfigurations>` + `<ConfigMapping>`**: declarative UI deep-links. Tier 2 only.
- **`<CustomGroupMetrics>`**: synthetic metrics on Custom Groups based on `ResourceAttribute.expression`. Tier 2 only. *(Pass 23 update: still unobserved in any installed adapter on either lab ops appliance — Navani grepped 22 devel + 30 prod `conf/describe.xml` files with zero matches. **Parser-class evidence confirms the runtime contract is real**: `com/integrien/alive/common/adapter3/describe/CustomGroupMetricsDescribe.class` ships in `vrops-adapters-sdk-1.0.jar`, and `com/vmware/statsplatform/persistence/metadata/CustomGroupMetrics.class` + `CustomGroupMetricDescriber.class` ship in `persistence-1.0-SNAPSHOT.jar` — both confirmed clean-room safe via `unzip -l` entry listings only. A runtime usage example would need a fresh pak from outside the lab corpus (e.g., ServiceNow MP).)*
- **`<Faults>`**: pair-based event-driven alerts (separate framework from Symptoms). Tier 2 only.
- **`<BasePolicyAnalysisSettings>`** + **`<OOTBPolicies>`**: declarative policy definitions with inheritance. Tier 2 only.
- **`<TraversalSpecExtensionKinds>`**: extending another adapter's TraversalSpecs. Tier 2 only.
- **`<FavoriteGroups>`** (6.3.0+): metric grouping for the UI. Tier 2 only.

## Major findings vs. existing SPEC sections

### vs. § 02 (describe-xml overview)

- Element name is **`<Discoveries>`** containing **`<Discovery>`** — not `<DiscoveryDescribes>` / `<DiscoveryDescribe>` as drafted. The MPB emission class is `DescribeDiscovery` but the emitted element tag is `<Discovery>`. **Correct spec/02 § Open questions.**
- The XSD comment at `ConditionType` line 2783 shows a `<!--xsd:assert ... -->` (commented out) — the schema *intended* to enforce inter-attribute consistency (`@type AND @key AND @operator NOT(@uri)`) but the assertion is disabled. Validators do not catch ill-formed conditions; the appliance does.
- `AdapterKind.version` is `xs:integer`. The two observed adapter values (mpb-adapter=8, vim=9) are content-version integers; both fit. Schema-version (6.1.0/6.3.0) is a separate concept on `<xs:schema version=>`.

### vs. § 05 (resource model) — major expansion

`<ResourceKind>` attributes (XSD-authoritative, with all defaults/enums):

```
key:        string, REQUIRED
nameKey:    int, REQUIRED
showTag:    bool, optional (default false)
type:       int enum {1,2,3,4,7,8}, optional (default 1)
              1 = general
              2 = Business Service
              3 = Tier
              4 = Tag (synthetic)
              7 = Adapter Instance
              8 = Group
subType:    int enum {1,2,3,4,5,6}, optional (default 1)
              1 = general
              2 = geo
              3 = Enterprise
              4 = adapter-managed group (only when type=8)
              5 = rules-managed group (only when type=8)
              6 = world objects
credentialKind: COMMA-DELIMITED LIST of CredentialKind keys, optional
                (a single ResourceKind can accept multiple credential kinds)
capacityModel:    string, references CapacityDefinition.key, optional
monitoringInterval: int (minutes), optional
                    — DEFAULT MONITORING INTERVAL for adapter-instance kind
worldObjectName:  string, optional
dynamic:    bool, optional
              — TRUE if created in CODE (not describe.xml).
              — DYNAMIC kinds are NOT reconciled at re-describe time
                — DB state for them is preserved.
              — THIS EXPLAINS the NSX "runtime-pushed topology" pattern:
                NSX declares 41 kinds in describe.xml but creates additional
                ones at runtime as dynamic=true so they survive re-describes.
isSingleton:        bool, VMware-internal
isUnmovable:        bool, VMware-internal
isCredentialRequired: bool, optional (default true)
              — if false, user can omit credential at create time
```

**Previously I had only `type=7` documented.** All 6 type values are first-class, each with platform-specific UI behavior. Notably `type=8` (Group) + `subType=4|5` distinguishes adapter-managed vs rules-managed groups — relevant for any Tier 2 adapter that aggregates resources into groups.

### vs. § 05/06 (resource attribute / metric model) — MAJOR expansion

`<ResourceAttribute>` full attribute set (XSD-authoritative):

```
key:                  string, REQUIRED (no '|' or ':' allowed in key value!)
nameKey:              int, REQUIRED
unit:                 string, optional (e.g., "MB", "GHz")
unitNameKey:          int, optional (localized unit display)
dashboardOrder:       int, optional (UI ordering)
dataType:             enum {string, integer, long, float, double}, optional (default float)
                      — 5 values, NOT 3 as previously assumed
isProperty:           bool, default false
isPropertyHistoryEnabled: bool, default false
                      — when true, property changes are stored historically;
                        when false, only the last value is kept
isRate:               bool, optional (computed from diff of last 2 measurements)
isDiscrete:           bool, optional (discrete vs continuous numbers — UI rendering hint)
isKpi:                bool, default false
                      — KPI metrics feed the Self-Health-Score → Anomalies badge
isImpact:             bool, optional
                      — impact attributes are NEVER considered root cause in alert analysis
defaultMonitored:     bool, optional (collected by default in OOTB policy)
dtType:               string, optional (preferred dynamic-thresholding algorithm,
                                        e.g., "multinomial" for string metrics)
keyAttribute:         bool, optional (appears in badge widgets)
favoriteGroups:       ";"-delimited string (UI metric grouping)
favoriteInstances:    ";"-delimited string (per-instance grouping)

— deprecated (do not emit):
defLowThreshold, defaultAlertLevel, defHighThreshold, maxVal, minVal

— VMware-internal (Tier 1/2 generators should NOT emit):
expression, derived, hidden
```

**Implication for VCF-CF**: the metric/property declaration surface is **substantially richer than the legacy SPEC § 05 covered**. `isKpi`, `isImpact`, `defaultMonitored`, `dtType`, `favoriteGroups` are all first-class authoring concerns that affect UI behavior, alert analysis, and OOTB policy.

There's a SEPARATE enum `PropertyDatatypeType` with 17 values (String / SInt32 / UInt32 / SInt64 / UInt64 / Decimal / Double / Boolean / DateTime / Binary / Byte / Enum / TypeName / Any / Integer / SnapshotData / ProcessesData). Used by method parameter declarations, NOT by ResourceAttribute (which uses the smaller dataType enum). Document where each applies.

### vs. § 08 (alert framework) — significant expansion

**Condition `type` values: 10 in schema, 6 observed in data**:

| value | observed in data | notes |
|---|---|---|
| `metric` | ✅ | static + dynamic-via-reference |
| `htmetric` | ✅ | **DEPRECATED in schema** — "use metric instead" |
| `dtmetric` | ✅ | platform dynamic threshold |
| `htsuper` | not observed | **DEPRECATED in schema** — "use metric instead" |
| `dtsuper` | not observed | dynamic-threshold-super (related to dtmetric; details TBD) |
| `fault` | ✅ | |
| `property` | ✅ | |
| `msg_event` | ✅ | |
| `metric_event` | not observed | "exists" operator only; one-shot metric-arrival check |
| `smart` | not observed | "VMware internal use only" |

**Operator vocabulary: 20 in schema, 11 observed**:

| operator | applies to | observed |
|---|---|---|
| `>`, `>=`, `<`, `<=`, `=`, `==`, `!=` | numeric metric / numeric property | most observed (`==` and `=` are aliases — schema accepts both) |
| `startswith`, `notstartwith`, `endswith`, `notendwith` | string property | **NOT observed** — schema allows them |
| `contains`, `notcontain` | string property + msg_event | `contains` observed; `notcontain` not |
| `regex`, `notregex` | string property + msg_event | `regex` observed; `notregex` not |
| `above`, `below`, `abnormal` | dtmetric/dtsuper | `above`/`below` observed; **`abnormal`** never observed |
| `exists` | metric_event | not observed |
| `equals` | msg_event | observed once |

**Severity enum (XSD): {info/Info, warning/Warning, immediate/Immediate, critical/Critical}** — 4 canonical values, accepted in both cases. **`Automatic` was observed in vSphere but is NOT in the schema enum.** Either (a) the platform accepts schema-non-compliant values, (b) vSphere uses a non-standard schema extension, or (c) there's a newer schema (6.4+) that adds it. **Treat as a finding worth flagging** — schema-Automatic is not portable.

### `<Recommendation>` can trigger AUTOMATED ACTIONS — never observed, but supported

```xml
<Recommendation key="ReclaimMemoryFromVM">
    <Description nameKey="9099"/>
    <Action actionAdapterKey="VMWARE"
            targetResourceKind="VirtualMachine"
            actionKey="MemoryHotAdd"/>
</Recommendation>
```

A recommendation can carry an `<Action>` element with `actionAdapterKey` + `targetResourceKind` + `actionKey`. When the operator accepts the recommendation in the UI, the platform invokes the named Action on the target resource. **Cross-adapter** — the action can be in a different adapter than the recommendation source. This is a fully-fledged remediation framework that vSphere and mongodb don't use (both emit text-only Recommendations); other adapters may. Tier 2 generator should expose this.

## Newly-documented surfaces

### `<Faults>` — pair-based event-driven alerts (Tier 2 only)

```xml
<Faults>
    <FaultState key="vm.disk.full" resourceKind="VirtualMachine" autoGenerateAlertDefs="true" nameKey="...">
        <ProblemEvent key="DISK_FULL_TRIGGER" faultScore="80" nameKey="..."/>
        <ClearEvent   key="DISK_FULL_CLEAR" nameKey="..."/>
    </FaultState>
</Faults>
```

A `<FaultState>` declares a pair: when an event with `eventId="DISK_FULL_TRIGGER"` arrives, the platform fires the fault alert; when `eventId="DISK_FULL_CLEAR"` arrives, the alert clears. `faultScore` (1-100) drives badge impact severity. **`autoGenerateAlertDefs="true"`** tells the describe processor to auto-create the SymptomDefinition + AlertDefinition for the fault — a shortcut for the common case.

**This is a parallel alert mechanism to Symptoms/AlertDefinitions** — useful when the source system already emits trigger/clear event pairs and you want them mapped directly to alerts.

### `<LaunchConfigurations>` — declarative UI deep-links (Tier 2 only)

```xml
<LaunchConfigurations>
    <LaunchConfig key="vCenterUI" adapterKindKey="VMWARE" resourceKindKey="HostSystem" nameKey="...">
        <HostProtocol>https://${vcHost}</HostProtocol>
        <UriTemplate>/ui/#?extensionId=vsphere.core.host.summary&objectId=${moid}</UriTemplate>
        <Variable name="vcHost"/>
        <Variable name="moid"/>
    </LaunchConfig>
    <ConfigMapping uiConfigKey="resource-detail" launchConfigKey="vCenterUI" dispOrder="1"/>
</LaunchConfigurations>
```

LaunchConfig declares a URL template (`HostProtocol` + `UriTemplate`) with `Variable`s (substituted from resource/alert context). The matching attributes (`adapterKindKey`, `resourceKindKey`, `alertType`, `alertSubType`, `active`) are **all regex patterns** — flexible binding. ConfigMapping declares which UI page renders the link (`uiConfigKey` ∈ {`resource-detail`, `environment-overview`, `alerts-overview`, ...}).

Tier 2 adapters can ship a deep-link integration into the source system's native UI as a first-class capability.

### `<BasePolicyAnalysisSettings>` + `<OOTBPolicies>` — declarative policy framework

Adapters declare:
- Default analysis settings (`BasePolicyAnalysisSettings`) — base behavior
- Named out-of-the-box policies (`OOTBPolicies`) — pre-canned policy variants users can assign

`OOTBPolicy` supports **inheritance via `parentPolicy`** — only override the differences from the parent.

Each `PolicySettings` is keyed by adapter-kind + resource-kind combination. Allows the OOTB policy to span multiple adapters.

Skeleton:
```xml
<OOTBPolicies vendorNameKey="...">
    <Policy key="MongoDB-Performance" parentPolicy="MongoDB-Base" nameKey="...">
        <PolicySettings ...>
            <!-- per adapter-kind / resource-kind settings -->
        </PolicySettings>
        <PackageSettings>...</PackageSettings>
    </Policy>
</OOTBPolicies>
```

Detailed schema for `<PolicySettings>` and `<PackageSettings>` not unpacked here — pull when Policy pass lands.

### `<Discoveries>` — manual discovery UI surface

```xml
<Discoveries>
    <Discovery key="ScanIPRange" nameKey="...">
        <DiscoveryParam key="ipRange" dispOrder="1" type="string"
                        required="true" password="false" nameKey="..."
                        regexp="^\d+\.\d+\.\d+\.\d+(/\d+)?$"/>
        <DiscoveryParam key="snmpCommunity" dispOrder="2" type="string"
                        required="false" password="true" nameKey="..."/>
    </Discovery>
</Discoveries>
```

`DiscoveryParam.type` ∈ {`string`, `integer`, `host`, `ip`} (4 values; same enum as `CredentialField.type` — but DIFFERENT from `ResourceAttribute.dataType`'s 5-value enum). Supports `password` (mask input), `regexp` (client-side validation), `default`, `enum` (for combo-box rendering).

This is the UI surface for `adapter.discover(DiscoveryParam)` invocation. mpb-adapter had no `<Discoveries>` element; some adapters do.

## Findings summary — what this pass changes about VCF-CF

1. **Target schema 6.3.0** (vim copy). The "schemas are identical" assumption was wrong; pick the newest.
2. **Tier 2 must expose 7+ describe surfaces not previously in the SPEC**: Faults, LaunchConfigurations, OOTBPolicies, BasePolicyAnalysisSettings, CustomGroupMetrics, TraversalSpecExtensionKinds, FavoriteGroups, Names.
3. **ResourceAttribute is ~3× richer than spec/05 documents** — KPI/Impact/defaultMonitored/dtType/favoriteGroups are first-class. Update spec/05 and spec/06.
4. **ResourceKind type/subType enums are fully bounded** — 6 type values, 6 subType values, each with documented platform meaning. `dynamic=true` is the mechanism behind runtime-pushed kinds.
5. **Condition has 10 types and 20 operators** (vs 6/11 observed in data). `htmetric` and `htsuper` are deprecated; `metric_event` and `dtsuper` are exotic but real.
6. **Recommendations can trigger automated actions** (cross-adapter). Major remediation-framework capability never observed in data — generator should expose.
7. **Faults are a parallel alert mechanism** to Symptoms — event-pair-driven, simpler. Worth exposing for adapters whose source system already emits trigger/clear pairs.
8. **Severity `Automatic` is non-schema** — observed in vSphere but absent from XSD. Flag as portability risk.
9. **`<ConditionType>` had a commented-out xsd:assert** — the schema lacks inter-attribute consistency enforcement. Bad combinations of type+operator+value get through validation; the appliance handles them. VCF-CF should add its OWN cross-attribute validation that the XSD doesn't.

## Open follow-ups (Pass 11+)

1. The `CapacityDefinitionType` lives at lines 1745-2149 — detailed pass needed for capacity model SPEC section.
2. `ActionType` + `MethodType` (lines 1645/1371) — refine spec/04 against XSD.
3. `TraversalSpecExtensionKindType` (line 3418) — refine spec/07.
4. Verify what value the platform substitutes for `Automatic` severity, and whether 6.4+ schema exists somewhere.
5. The schema version progression: 6.1.0 → 6.3.0 (FavoriteGroups added); what's in 6.2.0 and 6.4.0+? Source: appliance schema directory may have it.
