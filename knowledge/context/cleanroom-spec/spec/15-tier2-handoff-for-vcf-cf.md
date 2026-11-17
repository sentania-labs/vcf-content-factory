# Tier 2 → VCF-CF Handoff

**Audience**: VCF-CF Tier 2 (Native Java adapter generator) implementers.
**Source of authority**: cleanroom RE across 9 deep-analyzed adapters + 32 bulk-surveyed + SDK + 3 MPB designs. 17 documented passes.
**Date**: 2026-05-16.
**Companion specs** (look here for full enumerations):
- `spec/01-adapter-lifecycle.md` — `AdapterInterface3` + `AdapterBase` + packaging + concurrency
- `spec/02-describe-xml.md` + `spec/02a-describe-xsd-canonical.md` — describe.xml schema (authoritative)
- `spec/03-credential-model.md` — CredentialKind / CredentialField
- `spec/04-actions.md` — legacy ActionableAdapterInterface + modern NMP TaskHandler
- `spec/05-resource-model.md` — ResourceKind / Group / Attribute / Identifier
- `spec/06-metrics-units-expressions.md` — metric keys, units, computed-metric expressions
- `spec/07-relationships-cross-mp.md` — TraversalSpec + Relationships API + cross-MP attachment
- `spec/08-alerts-symptoms-recommendations.md` — Symptom/Alert/Condition grammar
- `spec/09-capacity-and-policy.md` — CapacityDefinitions + PolicySettings ladder
- `spec/13-classloading-and-classpath.md` — appliance classpath + per-pak isolation
- `spec/14-ui-and-operational-surfaces.md` — Methods/Actions/Faults/LaunchConfig/PowerState/Icon
- `spec/99-summary-and-vcf-cf-recommendations.md` — full investigation synthesis

This handoff stands alone for the strategic picture. Cross-references are lookups.

---

## TL;DR (12 takeaways)

1. **The legacy SDK (`com.integrien.alive.common.adapter3.*`) is the universal Track C foundation.** Every native Java adapter — Broadcom-internal classic, BlueMedora-derived marketplace, MPB-generated — extends `AdapterBase` directly or via the `aria-ops-core` wrapper. The "modern" `vcf-ops-data-sdk` is narrow vCenter-stats middleware, not a successor SDK.

2. **`vcfcf-adapter-base.jar` has TWO valid architectural choices, both produce valid Track C adapters**:
   - **Option A**: extend `AdapterBase` directly (Broadcom-internal pattern; max flexibility, write your own helpers)
   - **Option B**: extend `UnlicensedAdapter` from `aria-ops-core` (cleaner SPI pre-built: Tester / Discoverer / LiveCollector / HistoricalCollector). Used by ~half the ecosystem. **Recommended** because the SPI is cleaner and MPB Tier 1 paks already use it.
   - Whichever you pick, the **three-axis collection split** (separate `getCurrentMetrics` / `getEvents` / `getRelationships`) is good design.

3. **The platform classpath provides only the SDK + platform API + logging.** Every other dependency (Jackson, HTTP client, vendor SDKs, aria-ops-core, Kotlin runtime, log4j) **must be bundled per-pak in `<adapter>/lib/`**. Per-pak classloader isolation means version conflicts don't cascade (same library can ship at different versions in different paks).

4. **Three pak shape patterns** (spec/13 § 3): C2 lean (no lib/, ~150KB), C1 light (~5MB), C1 rich (~25MB with full HTTP/Kotlin/vendor stacks). Default to C1 rich for safety; expose pak-shape as a deployment knob.

5. **`describe.xml` is much richer than any single adapter uses.** The XSD permits 19 top-level children under `<AdapterKind>`; most adapters use 5-10. Tier 2 SHOULD expose the full surface — the schema admits substantial UI/operational richness most teams don't author.

6. **`<CapacityDefinition>` + `<PolicySettings>` is 80% of any complex adapter's describe.xml.** Two-layer model: CapacityDefinitions declare resource-container axes; PolicySettings ladder configures how they're analyzed (Stressed / UsableCapacity / Workload / CapacityTimeRemaining / Reclaimable {Waste/Idle/PoweredOff/Underused/UnUsed} / Density / Time). Templated authoring is the only sane UX.

7. **Methods + Actions = a fully-declarative UI invocation framework.** Adapter declares method signatures + UI bindings; platform builds the form, collects parameters, calls `onAction()`. The adapter writes ZERO UI code. Multi-context Actions (one action exposed on VM, Host, AND Cluster — vSphere PowerOffVM pattern) are first-class. Adapter expression language has its own SpEL-like DSL (`identifier`, `attribute`, `parents/descendants`, `value('invalid')` as skip-sentinel).

8. **Alerts have TWO declarative paths**: (a) the Symptom + AlertDefinition framework (rich condition grammar: metric / dtmetric / property / fault / msg_event / htmetric — `spec/08`); (b) the `<Faults>` framework for pair-based event-driven alerts (multi-severity ProblemEvent → ClearEvent — `spec/14`). Different adapters use both; choose based on whether the source system emits trigger/clear event pairs.

9. **Cross-MP attachment is identity-based, no special API.** Construct `ResourceKey(adapterKind="VMWARE", resourceKind="VirtualMachine", identifiers=...)` and push via `addMetricData` or `Relationships.addRelationships`. Platform de-dupes by identity. Foreign-resource lookup uses `com.vmware.ops.api.model.resource.ResourceDto` (Pass 6 finding). vSphere VM is the most-cross-referenced foreign kind (14 paks declaratively reference it).

10. **Relationships API has 18 method signatures across 3 axes** (spec/07): add/remove/set × standard/generic × single-edge/bulk-merge. `set` is REPLACEMENT semantics (with optional Set<String> label filter for scoped replacement). Generic variants carry a label + optional namespace for typed edges.

11. **`AdapterBase` enforces at-most-one `collect()` per instance via `Semaphore locker`** — scope is **per-instance** (Pass 23 empirical confirmation: same-kind different-instance adapters parallel; different-kind adapters parallel; same-instance never overlaps). Single-threaded within a cycle. **Platform does NOT retry failed `collect()` cycles** — errors swallow-and-log, next scheduled cycle proceeds. Adapter authors must implement own retry in `onCollect()` if needed.

12. **Pak installs through a CASA→Python 7-phase pipeline; signing is permissive** (`spec/16` for the full appliance behavior, `analysis/pak-signing-chain.md` for the on-disk cryptographic format). Empirical findings: appliance **accepts unsigned paks and installs them in full with no admin override** (42 records observed), **does NOT enforce cert validity dates** (expired-2026-01-03 cert still trusted on paks built 2025-12-30), `checkSignature` is **opt-in at the API layer**. **VCF-CF decision**: ship unsigned is the path-of-least-resistance for any internal-deployment MVP; marketplace distribution requires re-signing with VMware's private key on the marketplace side. Design signing as pluggable strategy.

---

## 1. The Track C native adapter foundation

### `AdapterInterface3` — the universal contract

8 abstract methods + 1 default:

```java
interface AdapterInterface3 {
    AdapterStatus configure(AdapterConfig config);
    AdapterDescribe describe();
    DiscoveryResult discover(DiscoveryParam param);
    CollectResult collect();                                        // ← the main loop
    boolean changePassword(PasswordParam param);
    boolean test(TestParam param);                                  // ← Test Connection UI
    AdapterStatus discard();                                        // ← shutdown
    CheckCertificateResult checkCertificate(CheckCertificateParam param);
    default void stopCollection() { }                               // ← cancel in-flight (added later)
}
```

### `AdapterBase` — the template-method base

`AdapterBase implements AdapterInterface3` with ~70 helper methods including:
- `protected final Semaphore locker` — serializes collect() (at-most-one per instance)
- `protected CollectResult collectResult` — the per-cycle result bucket
- `protected final AdapterCache adapterCache` — per-instance state cache
- `getMonitoringInterval()`, `getMonitoringIntervalInSec()` — schedule access
- `getAllMonitoringResources()`, `getMonitoringResource(...)`, `isMetricMonitoring(...)` — config introspection
- `CertificateChecker` — outbound SSL trust management
- `AdapterInterfaceLogger` — structured logging

Adapters extend `AdapterBase` (rather than implementing `AdapterInterface3` directly) for almost all observed cases. Direct interface implementation is theoretically possible but no observed examples.

### Adapter instance lifecycle

```
APPLIANCE INSTALL TIME
    └→ Platform reads <adapter>/adapter.properties → loads ENTRYCLASS via per-pak classloader
    └→ Platform reads <adapter>/conf/describe.xml → registers AdapterKind + ResourceKinds

USER CREATES ADAPTER INSTANCE (one-per-credentialed-connection)
    └→ Platform instantiates the ENTRYCLASS once (per adapter instance)
    └→ Platform calls configure(AdapterConfig) — adapter reads its instance-specific config
    └→ Platform calls test(TestParam) when user clicks "Test Connection"

ON COLLECTION SCHEDULE (per monitoringInterval — typically 5 minutes)
    └→ Platform calls collect() on the SAME instance reused from previous cycle
        └→ collect() fills CollectResult: metrics, properties, events, relationships, status
        └→ collect() returns; platform pushes data through to TSDB / alerting / topology
    └→ Repeat
    (Semaphore locker ensures at-most-one collect() per instance at a time)

ON-DEMAND
    └→ User clicks Test → test()
    └→ User invokes discovery → discover(DiscoveryParam)
    └→ User invokes Action → onAction(ActionParam) [if implements ActionableAdapterInterface]
    └→ Password change UI → changePassword(PasswordParam)
    └→ Cert renewal → checkCertificate(CheckCertificateParam)

ON SHUTDOWN / UNINSTALL
    └→ Platform calls discard() — adapter releases connections / threads / caches
    └→ Per-pak classloader discarded
```

### Packaging shape (spec/13)

| Shape | When to use | Bundled lib/ size |
|---|---|---|
| **C2 lean** | Adapter uses only legacy SDK + platform API (e.g., SuiteAPI-only internal adapters) | None (~150 KB total pak) |
| **C1 light** | A few HTTP/JSON jars + maybe a vendor SDK | ~5 MB |
| **C1 rich** | Full HTTP stack + Jackson + vendor SDKs + (optionally) aria-ops-core + Kotlin runtime | ~22-25 MB |

VCF-CF default: **C1 rich** for safety. Expose shape as a deployment knob; let users opt down to C1 light or C2 when they know their dep footprint.

### Always-available platform classes (don't bundle)

- `com.integrien.alive.common.adapter3.*` (SDK contract)
- `com.integrien.alive.common.adapter3.{config,action,describe}.*`
- `com.integrien.alive.common.util.*`
- `com.vmware.ops.api.*` (platform API including `ResourceDto` — the foreign-resource bridge)
- `com.vmware.ops.api.client.Client` (SuiteAPI client)
- `com.vmware.vrops.logging.*` (`AdapterLoggerFactory`)
- `com.vmware.vrops.secure.connection.*` (trust manager — Noop and Ndc)

### MUST bundle if used

- `aria-ops-core-X.Y.Z.jar` — if Option B (aria-ops-core wrapper). Not on shared classpath.
- HTTP client: Apache HTTPClient OR Ktor OR OkHttp — pick one, pin a version.
- JSON/XML: Jackson, woodstox. Pin versions.
- Kotlin runtime (stdlib + reflect + coroutines) — if codegen emits Kotlin.
- log4j-{api,core} — most adapters bundle log4j 2.x for structured logging.
- gRPC / vendor SDKs.
- `licensecheck-1.1.5.jar` — if using `license_type: "adapter:<kindkey>"` in manifest.

---

## 2. The describe.xml authoring surface

19 top-level elements under `<AdapterKind>` per the canonical XSD (`spec/02a`). Required vs commonly-used:

| Required | Element | Spec section | VCF-CF priority |
|---|---|---|---|
| ✅ | `<ResourceKinds>` | spec/05 | P0 — every adapter needs this |
| | `<CredentialKinds>` | spec/03 | P0 — almost every adapter |
| | `<Discoveries>` | spec/02 | P1 — manual-discovery UI |
| | `<Methods>` + `<Action>` | spec/14 | P1 — actionable adapters |
| | `<Recommendations>` | spec/08 | P1 — used by every alerting adapter |
| | `<CapacityDefinitions>` | spec/09 | P0 for capacity-aware adapters (most) |
| | `<BasePolicyAnalysisSettings>` + `<OOTBPolicies>` | spec/09 | P0 if CapacityDefinitions present |
| | `<SymptomDefinitions>` + `<AlertDefinitions>` | spec/08 | P1 — most alerting adapters |
| | `<TraversalSpecKinds>` | spec/07 | P2 — declarative topology |
| | `<Faults>` | spec/14 | P2 — when source emits trigger/clear pairs |
| | `<LaunchConfigurations>` | spec/14 | P2 — UI deep-links |
| | `<UnitDefinitions>` | spec/06 | P3 — custom units beyond stdlib |
| | `<TraversalSpecExtensionKinds>` | spec/02a | P3 — extending other MPs' topology |
| | `<CustomGroupMetrics>` | spec/02a | P3 — custom-group rollups (no in-corpus example) |
| | `<FavoriteGroups>` | spec/02a | P3 — UI metric grouping (6.3.0+ schema) |
| | `<LicenseConfig>` / `<HAConfig>` | spec/02 | P3 — platform-integration deep cuts |
| | `<Names>` / `<ProblemDefinitions>` | spec/02a | (rare) |

The bold story for VCF-CF: **prioritize ResourceKinds + CredentialKinds + CapacityDefinitions + PolicySettings + Symptom/Alert + Recommendations**. That covers ~95% of authoring volume.

### Schema versioning

3 XSD variants observed in corpus: 6.1.0 (two non-identical variants) and 6.3.0 (vim). **Target 6.3.0**. The 6.3.0 vs 6.1.0 delta is `<FavoriteGroups>` addition.

### XSD validation is built-in but lenient

The MPB runtime's `DescribeXml.validateSchema()` runs XSD validation via shaded MSV. **BUT**: the XSD has `xsd:assert` cross-attribute consistency rules **commented out**. Ill-formed conditions (wrong type+operator+value combinations) pass XSD validation; the appliance catches them at runtime. **VCF-CF should add its own cross-attribute validation** that the XSD lacks — better UX than appliance-side runtime failures.

---

## 3. The resource model (spec/05 + spec/02a)

### `<ResourceKind>` — the foundational unit

```xml
<ResourceKind key="MyResource"
              nameKey="100"
              type="1"
              subType="1"
              credentialKind="myadapter_credentials,myadapter_certauth"
              capacityModel="MyResource_capacity"
              monitoringInterval="5"
              dynamic="false"
              isCredentialRequired="true">
    <ResourceIdentifier dispOrder="1" key="host" nameKey="101" required="true" type="string"/>
    <ResourceIdentifier dispOrder="2" key="port" nameKey="102" required="true" type="integer"/>
    <ResourceGroup nameKey="103" instanced="false" key="CPU">
        <ResourceAttribute nameKey="104" key="usage" dataType="float" unit="%"
                           defaultMonitored="true" isKpi="true"/>
        <ResourceAttribute nameKey="105" key="load" dataType="float"
                           isProperty="true"/>
    </ResourceGroup>
    <ComputedMetrics>
        <ComputedMetric key="CPU|avg_load"
                        expression="avg(${this, metric=CPU|load, depth=0})"/>
    </ComputedMetrics>
    <PowerState alias="status|powered">
        <PowerStateValue key="ON" value="running"/>
        <PowerStateValue key="OFF" value="stopped"/>
    </PowerState>
    <Icon>
        <Condition property="status|powered">
            <Case suffix="up" value="running"/>
            <Case suffix="down" value="stopped"/>
        </Condition>
    </Icon>
</ResourceKind>
```

### ResourceKind `type` enum (full set)

| Code | Meaning |
|---|---|
| 1 | General resource (default) |
| 2 | Business Service |
| 3 | Tier |
| 4 | Tag (synthetic) |
| 7 | Adapter Instance (the per-instance container) |
| 8 | Group (with subType 4=adapter-managed, 5=rules-managed) |

### `ResourceKind.dynamic`

`dynamic="true"` for resource kinds CREATED IN CODE (not declared in describe.xml). Dynamic kinds are NOT reconciled at re-describe time — DB state preserved. **This is the mechanism behind NSX's runtime-pushed-topology pattern** (Pass 5 finding).

### `ResourceAttribute` — much richer than spec/05 first documented

Full attribute surface (from spec/02a XSD reading):

```
key (required), nameKey (required)
dataType: string | integer | long | float | double          ← 5 values, NOT 3
unit, unitNameKey, dashboardOrder
isProperty (bool, default false)
isPropertyHistoryEnabled (bool) — historical property values
isRate (bool) — computed from diff of last 2 samples
isDiscrete (bool) — discrete vs continuous (UI rendering)
isKpi (bool) — feeds Self-Health-Score → Anomalies badge
isImpact (bool) — never considered root cause in alert analysis
defaultMonitored (bool) — collected by default in OOTB policy
dtType — dynamic-threshold algorithm hint (e.g., "multinomial" for strings)
keyAttribute (bool) — appears in badge widgets
favoriteGroups (";"-delimited) — UI grouping
favoriteInstances (";"-delimited) — per-instance grouping
```

**VCF-CF should expose all these** — they meaningfully shape UI behavior, alert analysis, and OOTB policy defaults. Many adapter authors leave them at defaults; that's fine but make the option discoverable.

### Metric keys (spec/06)

Pipe-delimited path matching ResourceGroup nesting: `CPU|usage_average`. ResourceGroup keys CANNOT contain `|` or `:`. Nested groups produce keys like `Subsystem|SubGroup|metric_name`.

### Computed metric expression language

```xml
<ComputedMetric key="result_metric"
                expression="sum(${this, metric=CPU|usage, depth=0}) + ${this, metric=MEM|usage, depth=1}"/>
```

Functions observed: `sum`, `avg`, `min`, `max`. Selectors:
- `${this, metric=X|Y}` — read a metric on the same resource
- `${this, metric=X|Y, depth=N}` — descend the topology N levels and aggregate
- `${adapterkind=X, resourcekind=Y, metric=Z|W, depth=N}` — cross-resource/cross-MP

---

## 4. Credentials (spec/03)

```xml
<CredentialKinds>
    <CredentialKind key="myadapter_basic" nameKey="200">
        <CredentialField key="username" nameKey="201" type="string" required="true"/>
        <CredentialField key="password" nameKey="202" type="string" required="true" password="true"/>
    </CredentialKind>
    <CredentialKind key="myadapter_certauth" nameKey="210">
        <CredentialField key="cert_pem" nameKey="211" type="string" required="true"/>
        <CredentialField key="key_pem" nameKey="212" type="string" required="true" password="true"/>
        <CredentialField key="passphrase" nameKey="213" type="string" required="false" password="true"/>
    </CredentialKind>
</CredentialKinds>
```

A ResourceKind references one or more credential kinds via `credentialKind="name1,name2"` (comma-delimited). Multi-credential support is first-class (multi-auth scenarios).

Field types: `string`, `integer`, `host`, `ip`. `password="true"` masks UI input. `enum="true"` makes it a dropdown (with `<enum value=...>` children).

---

## 5. Capacity + Policy (spec/09 — the BIG describe surface)

```
<CapacityDefinitions>                          ← declare the AXES
    <CapacityDefinition key="My-CapacityModel">
        <ResourceContainer key="cpu" unit="Mhz" ...>
            <Capacity alias="cpu|provisioned"/>
            <Usage alias="cpu|used"/>
            <Demand alias="cpu|demand"/>
            <PowerState alias="status|powered"/>
        </ResourceContainer>
        <ResourceContainer key="mem" unit="MB" .../>
        ...
    </CapacityDefinition>
</CapacityDefinitions>

<BasePolicyAnalysisSettings>                   ← declare DEFAULT analysis behavior
    <PolicySettings key="default-MyKind" adapterKind="MY" resourceKind="MyKind">
        <StressedSettings stressedPercentThreshold="80" logicOperator="OR">
            <ApplicableResourceContainer resourceContainerKey="cpu" enabled="true"
                                         threshold="80" slaEntireRange="true" slaDuration="1"/>
        </StressedSettings>
        <WorkloadSettings>...</WorkloadSettings>
        <CapacityTimeRemainingSettings .../>
        <TimeSettings allHoursAndDays="true" dataRange="30"/>
        <ReclaimableCapacitySettings>
            <WasteSettings>...</WasteSettings>
            <IdleSettings filterThreshold="90" logicOperator="AND">...</IdleSettings>
            <PoweredOffSettings filterThreshold="90"/>
            <UnderusedSettings underusedPercentThreshold="1" .../>
            <UnUsedSettings>...</UnUsedSettings>
        </ReclaimableCapacitySettings>
        <DensitySettings>...</DensitySettings>
        <UsableCapacitySettings useHA="false" capacityCalculationRule="LAST_KNOWN">
            <CapacityBuffer/>
            <OverCommit/>
        </UsableCapacitySettings>
    </PolicySettings>
</BasePolicyAnalysisSettings>

<OOTBPolicies vendorNameKey="999">             ← declare OPT-IN named policies (tuning profiles)
    <Policy key="aggressive-reclaim" nameKey="500" parentPolicy="default">
        <PolicySettings key="aggressive-reclaim-MyKind" adapterKind="MY" resourceKind="MyKind"
                        inheritPolicySettings="default-MyKind">
            <!-- override only what differs from parent -->
        </PolicySettings>
        <PackageSettings>
            <Alerts adapterKind="MY" resourceKind="MyKind">
                <Alert id="AlertDefinition-MY-CapacityHigh" enabled="true"/>
            </Alerts>
        </PackageSettings>
    </Policy>
</OOTBPolicies>
```

### Recommended VCF-CF templates

Most resource kinds need a similar settings ladder. Don't make users hand-author all of this:

| Template | When to use |
|---|---|
| **Simple metric-bag** | One StressedSettings + WorkloadSettings + TimeSettings; no Reclaimable; no Density. For adapters that just want to feed metrics + emit alerts. |
| **Full capacity-aware** | Full ladder. For adapters where users care about capacity planning. |
| **Placement-participant** | Full ladder + consumer/provider linkage to a sibling kind. For adapters whose resources interact with vSphere placement (VMs, containers). |

### Default minimum

Always emit `<TimeSettings allHoursAndDays="true" dataRange="30"/>` — observed in every PolicySettings.

---

## 6. Alerts (spec/08)

```xml
<SymptomDefinitions>
    <SymptomDefinition id="cpu_high" nameKey="600"
                       adapterKind="MY" resourceKind="MyKind"
                       waitCycle="3" cancelCycle="2">
        <State severity="Warning">
            <Condition type="metric" key="CPU|usage" operator=">" value="90"
                       valueType="numeric" thresholdType="static"/>
        </State>
    </SymptomDefinition>
</SymptomDefinitions>

<AlertDefinitions>
    <AlertDefinition id="alert_cpu_high" nameKey="700"
                     adapterKind="MY" resourceKind="MyKind"
                     type="15" subType="22"
                     waitCycle="1" cancelCycle="1"
                     allowMultipleAlertsPerResource="false"
                     disableInBasePolicy="false">
        <State severity="Warning">
            <Impact type="badge" key="health"/>
            <SymptomSet applyOn="self" operator="and">
                <Symptom ref="cpu_high"/>
            </SymptomSet>
            <Recommendations>
                <Recommendation ref="ScaleUpCPU" priority="1"/>
            </Recommendations>
        </State>
    </AlertDefinition>
</AlertDefinitions>

<Recommendations>
    <Recommendation key="ScaleUpCPU">
        <Description nameKey="800"/>
        <Action actionAdapterKey="MY" targetResourceKind="MyKind" actionKey="ScaleCPU"/>
    </Recommendation>
</Recommendations>
```

### Condition `type` values (6 in use)

| Type | When |
|---|---|
| `metric` | Static or dynamic-via-reference threshold (`thresholdType=static|metric|property`, optional `targetKey`) |
| `dtmetric` | Platform-computed dynamic baseline (`operator=above|below`, no value) |
| `htmetric` | Hard-threshold capacity metric (deprecated per XSD; still in use) |
| `property` | Property comparison |
| `msg_event` | Event-message match (with `eventMsg`, `eventType`, `eventSubType`, regex supported) |
| `fault` | Fault-event match (via `faultevent` class name) |

Plus XSD-permitted but unobserved: `htsuper`, `dtsuper`, `metric_event` (with `exists` operator), `smart` (VMware-internal).

### Operator vocabulary (full XSD set)

`=`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `above`, `below`, `abnormal`, `contains`, `notcontain`, `regex`, `notregex`, `startswith`, `notstartwith`, `endswith`, `notendwith`, `equals`, `exists`. Boolean `and`/`or` at SymptomSet level only.

### Alert `type` / `subType` int codes (RESOLVED Pass 21)

`type`:
- 15 = APPLICATION
- 16 = VIRTUALIZATION
- 17 = HARDWARE
- 18 = STORAGE
- 19 = NETWORK
- 20 = (Tier 2-only category, vSphere uses)

`subType`:
- 18 = AVAILABILITY
- 19 = PERFORMANCE
- 20 = CAPACITY
- 21 = COMPLIANCE
- 22 = CONFIGURATION
- 6, 28, 29 = (Tier 2-only categories, vSphere uses)

Default for unknown: `(15, 22)`.

### Recommendations can trigger automated actions

```xml
<Recommendation key="ScaleUpCPU">
    <Description nameKey="800"/>
    <Action actionAdapterKey="MY" targetResourceKind="MyKind" actionKey="ScaleCPU"/>
</Recommendation>
```

The `<Action>` element on a recommendation links it to an Action declaration. When the operator accepts the recommendation in UI, the platform invokes the named Action. **Cross-adapter** — the action can be in a different adapter than the recommendation source.

### Faults framework (alternative — spec/14)

For source systems that emit trigger/clear event pairs:

```xml
<Faults>
    <FaultState key="ResourceUnhealthy" resourceKind="MyKind" nameKey="900"
                autoGenerateAlertDefs="true">
        <ProblemEvent key="ResourceUnhealthyTurnYellow" faultScore="30" nameKey="901"/>
        <ProblemEvent key="ResourceUnhealthyTurnRed" faultScore="100" nameKey="902"/>
        <ClearEvent key="ResourceHealthyAgain"/>
    </FaultState>
</Faults>
```

Multi-severity ProblemEvent chains sharing one ClearEvent (vSAN's standard pattern — 477 FaultStates). `autoGenerateAlertDefs="true"` shortcuts the Symptom+AlertDefinition boilerplate.

---

## 7. Actions + UI (spec/14)

Adapter declares Methods (the callable contract) + Actions (the UI bindings). Platform builds the UI form and calls `onAction()`.

```xml
<Methods>
    <Method key="ScaleCPU" nameKey="950">
        <Parameter key="resourceId" isRequired="true" nameKey="951">
            <SimpleMethodInfoList dataType="String"/>
        </Parameter>
        <Parameter key="newCpuCount" isRequired="true" nameKey="952">
            <SimpleMethodInfoList dataType="Integer"/>
        </Parameter>
    </Method>
</Methods>

<Action key="ScaleCPU" actionType="update"
        adapterEndpointExpression="attribute('endpoint')"
        resourceEndpointExpression="resourceUuid">
    <ResourceContext key="ScaleCPUOnResource" adapterKind="MY" resourceKind="MyKind" nameKey="960"
                     resourceTarget="resourceUuid"/>
    <ActionContext key="ScaleCPU" methodKey="ScaleCPU" helpId="actions.scale.cpu">
        <ActionContextField key="ResourceID" hidden="true" parameter="resourceId"
                            value="identifier('id')"/>
        <ActionContextField key="New CPU Count" component="textfield" dispOrder="1"
                            parameter="newCpuCount" nameKey="961"
                            value="attribute('CPU|provisioned')"/>
    </ActionContext>
</Action>
```

Adapter implements `ActionableAdapterInterface.onAction(ActionParam)` to receive the invocation. The platform handles the entire UI flow (form rendering, validation, parameter collection) declaratively.

VCF-CF should expose this as two authoring tiers:
1. **Simple action**: user declares "expose method M on resources of kind K" → VCF-CF generates Method + Action + ActionContext + ActionContextField stubs with sensible defaults
2. **Rich action**: user writes the SpEL expressions for resourceTarget, ActionContextField.value, etc. directly

### The expression language (adapter SpEL-like DSL)

Used throughout: `Action.resourceEndpointExpression`, `ResourceContext.resourceTarget`, `ActionContextField.value`, `LaunchConfig.active`, `LaunchConfig.Variable`, `<Condition>` `Case.value`. Helper functions:

- `identifier('KEY')` — read a ResourceIdentifier value
- `attribute('metric|path')` — read an attribute value
- `parents(adapterKind, resourceKind)`, `children(...)`, `descendants(...)` — relationship traversal
- `contextResources`, `contextResourcesCache` — the current selection
- `value('literal')` — literal value (and `value('invalid')` as skip-sentinel)
- `localizedString(nameKey, adapterKind, fallback)` — i18n
- `resourceNameAndIcon`, `resourceAttributeFormat(...)` — UI formatting
- `isAttributeDisabledFromPolicy(...)`, `isVCenterVersionEqualOrNewerThan(...)` — policy/version aware

Adapters can presumably register custom helpers (extension surface; not directly observable from describe.xml alone).

---

## 8. Relationships (spec/07)

Two modes (declarative + runtime-pushed) — both supported, often combined.

### Mode A: Declarative TraversalSpec

```xml
<TraversalSpecKinds>
    <TraversalSpecKind key="MyDiagram" nameKey="1000">
        <ResourcePath name="self-to-children">
            <PathMember adapterKindKey="MY" resourceKindKey="MyKind" relation="self"/>
            <PathMember adapterKindKey="MY" resourceKindKey="MyChildKind" relation="child"/>
        </ResourcePath>
    </TraversalSpecKind>
</TraversalSpecKinds>
```

### Mode B: Runtime-pushed via Relationships API (spec/07 full surface)

```java
Relationships rels = collectResult.getRelationships();
rels.setRelationships(parentKey, childKeys);                        // replace
rels.addRelationships(parentKey, additionalChildKeys);              // additive
rels.addGenericRelationship(parentKey, childKeys, "depends_on");    // labeled
rels.setGenericRelationships(parentKey, childKeys, "depends_on", "myadapter-namespace");
```

18 method signatures across 3 axes: add/remove/set × standard/generic × single/bulk. `set` is REPLACEMENT (with optional `Set<String>` filter for label-scoped replacement). Generic variants carry label + optional namespace.

### Cross-MP attachment recipe

```java
ResourceKey vmwareVMKey = new ResourceKey(
    "VMWARE",                                      // foreign adapter kind
    "VirtualMachine",                              // foreign resource kind
    Arrays.asList(                                 // identifiers must match vSphere's shape
        new ResourceIdentifierConfig("VMEntityName", "my-vm"),
        new ResourceIdentifierConfig("VMEntityObjectID", "vm-123"),
        new ResourceIdentifierConfig("VMEntityVCID", "vc-uuid"),
        new ResourceIdentifierConfig("VMEntityInstanceUUID", "uuid")
    )
);

// Then push metrics / relationships TO this foreign key:
collectResult.addMetricData(vmwareVMKey, myMetricData, false);
relationships.setRelationships(myResourceKey, Arrays.asList(vmwareVMKey));
```

Platform de-dupes by identity. No special "external resource" API needed.

vSphere VM is the most-cross-referenced foreign kind (14 paks declaratively reference it). VirtualMachine identifier shape is what enables this — pin to the (VMEntityName, VMEntityObjectID, VMEntityVCID, VMEntityInstanceUUID) tuple.

---

## 9. Pak structure + manifest (spec/01 + analysis/pak-signing-chain.md)

```
<pak-name>.pak                                [outer zip]
├── signature.cert                             [optional — see signing § below]
├── signature.mf
├── manifest.txt                               [pak-level]
├── eula.txt
├── default.png                                [icon]
├── post-install-fast.sh                       \
├── post-install.sh                             \
├── post-install.py                              ├─ install hooks
├── postAdapters.py                             /
├── preAdapters.py                             /
├── validate.py                               /
├── resources/resources.properties
├── content/                                   [emitted declarative content]
│   ├── dashboards/*.json
│   ├── supermetrics/customSuperMetrics.json
│   └── (reports/, views/, files/ — optional)
└── adapters.zip                               [inner archive]
    ├── manifest.txt                           [inner manifest]
    ├── default.png
    ├── eula.txt
    ├── resources/resources.properties
    └── <adapter-folder>/                      [conventionally <kindkey> or <kindkey>_adapter3]
        ├── <adapter-folder>.jar               [entry jar]
        │   ├── adapter.properties             (KINDKEY + ENTRYCLASS)
        │   └── com/...                        (entry class + adapter code)
        ├── conf/
        │   ├── describe.xml
        │   ├── describeSchema.xsd
        │   ├── <adapter>.properties
        │   └── resources/resources.properties
        ├── doc/
        └── lib/                               [bundled deps — varies by pak shape]
            └── *.jar
```

### Pak-level `manifest.txt`

```json
{
    "display_name": "My MP Display Name",
    "name": "My MP",
    "description": "...",
    "version": "1.0.0",
    "run_scripts_on_all_nodes": "true",
    "vcops_minimum_version": "7.5.0",
    "disk_space_required": 500,
    "eula_file": "eula.txt",
    "platform": ["Windows", "Linux Non-VA", "Linux VA"],
    "vendor": "My Vendor",
    "pak_icon": "default.png",
    "license_type": "adapter:mykindkey",
    "pak_validation_script": {"script": "python validate.py"},
    "adapter_pre_script":  {"script": "python preAdapters.py"},
    "adapter_post_script": {"script": "python postAdapters.py"},
    "adapters": ["adapters.zip"],
    "adapter_kinds": ["mykindkey"]
}
```

**Don't leave `display_name` and `vendor` as `"DISPLAY_NAME"` / `"VENDOR"` placeholders** (the iSDK / MPB template anti-pattern). Fill these in.

`vcops_minimum_version`: pin to the lowest version VCF-CF supports. `disk_space_required`: in MB. `platform`: deployment-target whitelist.

### Inner archive `manifest.txt`

```
ENTRYCLASS=com.mycompany.adapter.MyAdapter
KINDKEY=mykindkey
relationship_sync_interval=8                  (optional — MPB-generated paks use)
max_relationships_per_collection=             (optional)
max_events_per_collection=                    (optional)
```

### Install hooks

Install hooks run during the appliance's CASA-orchestrated install pipeline (full pipeline documented in `spec/16-platform-install-and-signing.md`). They do NOT validate signatures (that happens platform-side). Typical use: confirm `$VCOPS_BASE` env var set, run dashboard imports, etc. Keep these MINIMAL — anything substantial belongs in the adapter, not in install scripts.

**Filenames are conventional, not contractual** — the appliance routes by `pak_validation_script` / `adapter_pre_script` / `adapter_post_script` keys in `manifest.txt`, not by the literal `validate.py` / `preAdapters.py` / `postAdapters.py` filenames. VCF-CF-generated paks can use any filenames so long as `manifest.txt` references them.

### Pak signing — empirically permissive

**On-disk cryptographic format** lives in `analysis/pak-signing-chain.md`. **Appliance-side enforcement behavior** lives in `spec/16-platform-install-and-signing.md`. Summary:

- One self-signed VMware cert signs everything (Broadcom-internal + marketplace re-signed third-party). SHA-1 + RSA exp-3 (cryptographically deprecated). Cert expired 2026-01-03.
- **Appliance accepts unsigned paks and installs them in full** — confirmed empirically across 42 install records, no admin override required.
- **Appliance does NOT enforce cert validity dates** — paks signed with the expired cert continue to install cleanly. Behavior is "skip dates" — either explicit bypass or fingerprint-pinning that never consults the cert's validity window.
- `checkSignature` is opt-in at the API layer; the common case is `null` (no check requested).

**VCF-CF decision** (pick one):
1. **Unsigned** — **path of least resistance**. No admin override needed; the appliance accepts unsigned paks by default. Recommended for internal-deployment MVP.
2. **Customer-supplied cert** — would require confirming the appliance accepts non-VMware-fingerprinted certs (not empirically verified — the cert pin behavior may exclude this).
3. **Marketplace re-sign** — submit to internal-only Broadcom pipeline. Required for marketplace distribution but unnecessary for internal use.

Design signing as a **pluggable strategy** so it's easy to switch later if Broadcom hardens enforcement. Format is trivial (~10 lines of shell to compute SHA-1 manifest + RSA sign).

---

## 10. The expression language sub-DSL

Used across Methods/Actions/LaunchConfigurations/Conditions/Icons/CapacityDefinitions. It's a SpEL-like expression syntax with adapter-specific helper functions. Major helpers:

| Context | Helpers |
|---|---|
| Identifiers/attributes | `identifier('K')`, `attribute('K|...')`, `attributeInt(...)` |
| Traversal | `parents(adapterKind, kind)`, `children(...)`, `descendants(adapterKind, kind, depth)`, `getDescendantsAndCheckAttributes(...)` |
| Resource selection | `contextResources`, `contextResourcesCache`, `resourceUuid`, `resourceKindKey` |
| Adapter introspection | `adapterInstance('KIND')`, `adapterResourceKindKey(adapterKind, kind)` |
| Literals + control | `value('literal')`, `value('invalid')` (skip-sentinel) |
| UI formatting | `resourceNameAndIcon`, `resourceAttributeFormat(key, type, suffix?)`, `localizedString(nameKey, adapterKind, fallback)` |
| Policy/license | `isAttributeDisabledFromPolicy(...)`, `isAutomationAllowedByLicense()`, `isActionsEnabled(...)` |
| String ops | `?.trim()`, `.replaceAll(regex, replacement)`, `+` concat |
| Conditionals | `ternary ? if : else`, `&&`, `||`, `!` |
| Collection ops | `.![field]` (projection), `.?[filter]` (selection), `.size()` |
| Version checks (adapter-specific) | `isVCenterVersionEqualOrNewerThan(version)`, `isVCenterVersionEqualOrNewerThan(adapterInstance('K'), version)` |

VCF-CF Tier 2 has three options:
1. **Pass through** — give users a raw expression editor; document the helpers
2. **Pattern templates** — common patterns (e.g., "apply action to selected resource of kind X") generate the expression
3. **Both** — pattern-generate 80% of cases, raw-edit for the long tail

---

## 11. Recommended `vcfcf-adapter-base.jar` shape

The architectural choice from § 1, expanded:

### Option B (recommended): aria-ops-core wrapper

```java
public abstract class VcfCfAdapter extends com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter {
    // Concrete from UnlicensedAdapter:
    //   - Semaphore-locked collect() orchestration
    //   - Tester / Discoverer / LiveCollector / HistoricalCollector wiring
    //   - SuiteAPIClient lifecycle
    //   - Standard logging setup
    //   - HistoricalCollectionExecutor, LiveCollectionExecutor

    // VCF-CF generated subclasses override:
    public abstract Tester getTester(ResourceStatus status, ResourceConfig config);
    public abstract Discoverer getDiscoverer(ResourceStatus status, ResourceConfig config);
    public abstract LiveCollector getLiveDataCollector(ResourceStatus status, ResourceConfig config);
    public HistoricalCollector getHistoricalDataCollector(...) { return null; }  // optional

    // VCF-CF adds these helpers on top:
    protected <T> T getCachedValue(String key, Supplier<T> compute);    // caching helper
    protected void emitMetric(ResourceKey key, String metricKey, double value); // ergonomic helper
    protected void attachToForeign(String adapterKind, String resourceKind,
                                   List<ResourceIdentifierConfig> ids,
                                   String metricKey, double value);    // cross-MP helper
    // etc.
}

// Per-pak generated subclass:
public class MyAdapter extends VcfCfAdapter {
    @Override public Tester getTester(...) { return new MyTester(); }
    @Override public Discoverer getDiscoverer(...) { return new MyDiscoverer(); }
    @Override public LiveCollector getLiveDataCollector(...) { return new MyLiveCollector(); }
}

class MyLiveCollector implements LiveCollector {
    @Override public Collection<MetricData> getCurrentMetrics(...) { /* user code */ }
    @Override public Collection<Event> getEvents(...) { /* user code */ }
    @Override public Relationships getRelationships(...) { /* user code */ }
}
```

**Bundle `aria-ops-core-X.Y.Z.jar`** in every adapter's lib/. Pin the version (currently 8.0.0 in MPB-generated paks, 8.2.0 in mongodb's pak — verify Broadcom's current).

### Hook for future stream-based collection

Leave room in `LiveCollector.getCurrentMetrics()` for a **drain-from-subscription** implementation pattern:

```java
class StreamingLiveCollector implements LiveCollector {
    private final BlockingQueue<MetricData> buffer = new LinkedBlockingQueue<>();
    private Subscription subscription;

    public void onConfigure() {
        subscription = source.subscribe(this::onData);  // long-lived subscription
    }
    private void onData(SourceEvent event) {
        buffer.offer(translate(event));
    }
    @Override public Collection<MetricData> getCurrentMetrics(...) {
        List<MetricData> drained = new ArrayList<>();
        buffer.drainTo(drained);
        return drained;
    }
    public void onDiscard() { subscription.cancel(); }
}
```

If/when Broadcom modernizes the data SDK (or `vcf-ops-data-sdk` matures), VCF-CF can switch the underlying implementation without changing the SPI.

---

## 12. Tier 2 → Tier 1 promotion (when to RECOMMEND MPB instead)

If VCF-CF supports both Tier 1 (MPB-based) and Tier 2 (native Java), users often have a choice. Recommend MPB (Tier 1) when:

- Source is an HTTP API with simple auth (Basic / SessionToken)
- No complex value transforms beyond BASE64
- No actions / no faults / no custom capacity model / no policy customization
- Metric data types are STRING / DECIMAL only
- No threshold-condition symptoms (event-message-only)

Recommend Tier 2 (native) when ANY of:

- Non-HTTP collection (gRPC, JDBC, SNMP, etc.)
- Stateful collection (persistent connections, subscriptions)
- OAuth2 / Kerberos / AWS SigV4 / HMAC / mTLS-with-renewal
- Custom transforms beyond BASE64
- Actions / Methods / user-invokable operations
- `<CapacityDefinitions>` / `<Policies>` / `<Faults>` / `<LaunchConfigurations>`
- Metric-threshold symptoms, compound boolean symptoms, applyOn=child|descendant
- Per-attribute KPI/Impact/defaultMonitored/dtType/etc.

VCF-CF should auto-detect Tier 1 expressibility at design-validation time and prompt the user. See `spec/12 § 6` for the full testable list.

---

## 13. Open questions VCF-CF should track

The investigation has covered the static spec thoroughly. Most live-instance questions were resolved in Pass 23 via cross-workspace request to Navani (lab-admin); a few remain:

1. **Action result handling end-to-end** — what does `onAction()` return and how does the platform render that? `MethodResultType` exists in XSD but unsampled. (Static.)
2. **The expression-language full grammar** — partially inferable from examples; an authoritative reference would help. Could be RE'd against the platform's SpEL evaluator implementation. (Static.)
3. **`adapter.properties` keys beyond `ENTRYCLASS`/`KINDKEY`** — Pass 7 found a few more (`relationship_sync_interval`, `max_relationships_per_collection`, `max_events_per_collection`); full key catalogue TBD. (Static.)
4. **`<CustomGroupMetrics>` runtime usage example** — declared in XSD but absent from all in-corpus adapters AND from Navani's two lab ops appliances (Pass 23 confirmed-negative; 22 devel + 30 prod describe.xml files grepped, zero matches). Parser-class evidence proves the contract is real (`CustomGroupMetricsDescribe` + `CustomGroupMetrics` + `CustomGroupMetricDescriber` confirmed via clean-room-safe `unzip -l`). A runtime usage example would need a fresh pak from outside the lab corpus (ServiceNow MP or similar).
5. **Schema `Severity="Automatic"` portability** — vSphere uses it but not in the XSD enum. Either appliance accepts schema-non-compliant values, or there's a 6.4+ schema we don't have. (Static.)
6. ~~**Live install/scan logs from an appliance**~~ — **RESOLVED in Pass 23**. Install pipeline is a two-layer CASA→Python 7-phase state machine (STAGE → PREAPPLY_VALIDATE → VALIDATE → APPLY_ADAPTER_PRE_SCRIPT → APPLY_ADAPTER → APPLY_ADAPTER_POST_SCRIPT → CLEANUP). `describe.xml` is parsed during the `apply_adapter` phase. **Platform does NOT retry failed `collect()` cycles** — errors swallow-and-log. Semaphore scope is per-instance. Full writeup in `spec/16-platform-install-and-signing.md`.
7. ~~**The pak signing-validation policy**~~ — **RESOLVED in Pass 23**. Appliance accepts unsigned paks and installs them in full (42 records observed), does NOT enforce cert validity dates, `checkSignature` is opt-in at the API layer. Full writeup in `spec/16-platform-install-and-signing.md` § Signature validation.
8. **Cloud Proxy install pipeline cross-confirmation** (new follow-up arising from Pass 23) — `spec/16` documents appliance-side install. Cloud Proxy may use a different pipeline for the paks it consumes; out of current corpus.

---

## 14. Quick reference — crossref index

For full enumerations and evidence:

- **Adapter lifecycle + SDK contract + AdapterBase concurrency**: `spec/01-adapter-lifecycle.md`
- **describe.xml overview**: `spec/02-describe-xml.md`
- **describe.xml canonical XSD grammar**: `spec/02a-describe-xsd-canonical.md`
- **Credential model**: `spec/03-credential-model.md`
- **Legacy + Modern Actions protocols**: `spec/04-actions.md`
- **Resource model**: `spec/05-resource-model.md`
- **Metrics + units + computed expressions**: `spec/06-metrics-units-expressions.md`
- **Relationships + cross-MP attachment + full Relationships API**: `spec/07-relationships-cross-mp.md`
- **Alert framework (full grammar) + RESOLVED type/subType int codes**: `spec/08-alerts-symptoms-recommendations.md`
- **Capacity + Policy ladder**: `spec/09-capacity-and-policy.md`
- **MPB BuilderFile schema** (Tier 1 vocabulary — also informs Tier 2's understanding of what Tier 1 can do): `spec/10-mpb-builderfile-schema.md`
- **MPB designer wire format + pak generation pipeline + Track-C-shape revelation**: `spec/11-mpb-designer-wire-format.md`
- **MPB → VCF-CF Tier 1 Handoff (consolidated)**: `spec/12-mpb-handoff-for-vcf-cf.md`
- **Classloading + appliance runtime classpath**: `spec/13-classloading-and-classpath.md`
- **UI + Operational surfaces (Methods/Actions/Faults/LaunchConfig/PowerState/Icon)**: `spec/14-ui-and-operational-surfaces.md`
- **THIS DOC (Tier 2 → VCF-CF Handoff consolidated)**: `spec/15-tier2-handoff-for-vcf-cf.md`
- **Platform install pipeline + empirical signing behavior**: `spec/16-platform-install-and-signing.md`
- **Framework design guidance for `vcfcf-adapter-base.jar`** (how to build the framework that Tier 2 adapters extend, minimizing per-pak code work): `spec/17-vcfcf-framework-design-guidance.md`
- **Investigation journey (chronological audit ledger)**: `audit-log.md`
- **Pak signing chain analysis (on-disk cryptographic format)**: `analysis/pak-signing-chain.md`
- **Final investigation synthesis**: `spec/99-summary-and-vcf-cf-recommendations.md`
- **Per-adapter analyses** (reference detail for specific adapters): `analysis/per-adapter/*.md`
