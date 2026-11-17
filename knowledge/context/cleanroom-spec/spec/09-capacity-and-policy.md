# 09 — Capacity Model + Policy Framework

**Status**: Pass 18 + 19 (2026-05-16). Combined because the two surfaces are tightly bound — `<CapacityDefinitions>` declares the resource-container axes; `<PolicySettings>` configures how they're analyzed.
**Scope**: `<CapacityDefinitions>` + `<BasePolicyAnalysisSettings>` + `<OOTBPolicies>` + `<PolicySettings>` + the full settings ladder (Stressed, UsableCapacity, Workload, CapacityTimeRemaining, Time, Reclaimable, Waste, Idle, PoweredOff, Underused, UnUsed, Density, Risk, WorkloadAutomation, WorkloadOptimization). Plus `<PackageSettings>`.
**Evidence**: vSphere (`vmwarevi_adapter3` — 11 CapacityDefinitions, 16 OOTBPolicies, 16 PolicySettings, 1 BasePolicyAnalysisSettings, 9 WorkloadSettings, 9 CapacityTimeRemainingSettings, 15 PackageSettings, 2 RiskLevelSettings, 1 WorkloadAutomationSettings, 1 WorkloadOptimizationSettings); mongodb_adapter3 (3 + 2 + 5 + full reclaimable ladder); VirtualAndPhysicalSANAdapter3 (6 + 2 + 9); vcops_adapter3 (5 + 0 + 5); VCFAutomation (3 + 0 + 4).

## Two-layer architecture

```
<CapacityDefinitions>          ← declares what's MEASURABLE for a resource kind
        │                        (cpu, mem, disk, network, custom-stat-X axes — each as a ResourceContainer)
        ▼ referenced by
        │
<ResourceKind capacityModel="…">  ← binds a resource kind to a CapacityDefinition by key
        │
        ▼ analyzed per
        │
<BasePolicyAnalysisSettings>   ← the default policy's analysis settings
        OR
<PolicySettings>               ← named alternative settings (OOTB or admin-supplied)
        OR
<OOTBPolicies>                 ← bundles of named policies an admin can choose from
        │
        ▼ both contain
        │
<StressedSettings>            ← when does the resource count as "stressed"?
<UsableCapacitySettings>      ← how much capacity is actually usable (HA reserves, buffers, overcommit)
<WorkloadSettings>            ← which containers feed the workload-automation engine
<CapacityTimeRemainingSettings> ← projection of time-until-out-of-capacity
<TimeSettings>                ← which hours/days/datarange the analysis covers
<ReclaimableCapacitySettings> ← wraps Waste / Idle / PoweredOff / Underused / UnUsed
<DensitySettings>             ← consolidation-ratio analysis
<RiskLevelSettings>           ← (vSphere only) per-risk-category thresholds
<WorkloadAutomationSettings>  ← (vSphere only) DRS-equivalent algorithm settings
<WorkloadOptimizationSettings> ← (vSphere only) workload-optimization tuning
```

This is the **capacity-and-policy** subsystem of Aria Operations — the data model that feeds the Capacity / Stress / Time-Remaining / Reclaim-Opportunity badges and pages.

## `<CapacityDefinition>` — the resource-axes declaration

```xml
<CapacityDefinitions>
    <CapacityDefinition key="CapacityModel-VM">
        <ResourceContainer key="cpu" displayOrder="1"
                           model="default"
                           unit="Mhz"
                           nameKey="8014"
                           enableForCustomProfile="true">
            <Capacity alias="cpu|vm_capacity_provisioned"/>
            <Usage alias="cpu|usagemhz_average"/>
            <Demand alias="cpu|demandmhz"/>
            <Reservation alias="cpu|reservation_used"/>
            <PowerState alias="sys|poweredOn"/>
            <Limit alias="cpu|effective_limit"/>
            <CapacityConsumptionUnitCount alias="config|hardware|num_Cpu"/>
            <ConsumptionCountUnit unitNameKey="7004"/>
        </ResourceContainer>
        <!-- more ResourceContainer blocks: mem, mem-host, mem-alloc, diskspace, ... -->
    </CapacityDefinition>
</CapacityDefinitions>
```

### `<CapacityDefinition>` attributes

- `key` (required) — referenced by `<ResourceKind capacityModel="…">` to bind a resource kind to this capacity model. One CapacityDefinition can serve multiple kinds (e.g., VM and Pod share `CapacityModel-VM` in vSphere).

### `<ResourceContainer>` — one axis of capacity

| Attribute | Purpose |
|---|---|
| `key` (required) | Unique within the CapacityDefinition (`cpu`, `mem`, `diskspace`, `mongod-connections_capacity`). Referenced from PolicySettings via `resourceContainerKey`. |
| `displayOrder` | Integer; UI ordering. |
| `model` | `default` or `alloc` (allocation-model variant — used in custom profiles / sizing recommendations). |
| `unit` | String unit code (`Mhz`, `KB`, `GB`, `byteps`, `perSec`, etc.). |
| `unitNameKey` / `physicalUnitNameKey` | Int → resources.properties for localized unit names. |
| `nameKey` / `namekey` | Localized display name (both casings observed — emit canonical). |
| `enableForCustomProfile` | bool. Whether the container participates in custom sizing-profile calculations. |
| `enableOnlineAnalytics` | bool. Whether the platform's online analytics engine processes this axis. Some helper containers exist only for sizing math and disable online analytics. |
| `minimumSizeRecommendation` | Integer in container `unit`. Smallest recommendation the sizing engine emits. |
| `modularityForSizeRecommendation` | Integer in container `unit`. Sizing increments (round up to multiples). |
| `bufferSupported` | bool. Whether the container can have a capacity buffer applied. |
| `whatIfApplicable` | bool. Whether the container is included in what-if scenarios. |
| `workloadInstanced` | bool. Whether to instance per-workload for analysis. |
| `floorCR` | Floor value for Consolidation Ratio calculations. |
| `consumer` / `provider` | bool flags marking the container as a workload consumer or capacity provider in the placement graph. |
| `consumerResourceContainerKey` / `providerResourceContainerKey` | Linkage to the corresponding container on the partner side (e.g., a VM's `cpu` consumer links to a Host's `cpu` provider). |
| `computeFromConsumers` / `computeFromProviders` | bool. Indicates the container's value is computed from related-resource containers rather than directly measured. |
| `customProfileConsumer` / `customProfileResourceContainerKey` / `computeFromCustomProfileConsumer` | Custom-profile linkage. |
| `usableCapacityConsumer` / `computeFromUsableCapacityConsumer` | Usable-capacity computation linkage. |

### `<ResourceContainer>` child elements

Each child is a `alias=` pointer to a `ResourceAttribute` key (using the standard `<group>|<key>` metric path):

| Element | Meaning |
|---|---|
| `<Usage alias=…/>` | What the container reports as "currently used." |
| `<Demand alias=…/>` | What the container reports as "demanded" (often higher than usage — pending demand). |
| `<Capacity alias=…/>` | What the container reports as "total available." |
| `<Reservation alias=…/>` | Reserved-but-not-necessarily-used portion. |
| `<Limit alias=…/>` | Hard ceiling (e.g., a VM-set memory limit). |
| `<PowerState alias=…/>` | Which metric/property represents the on/off state (so analytics know to exclude powered-off resources). |
| `<PowerStateValue>` | (rarer) inline power-state value declaration. |
| `<CapacityConsumptionUnitCount alias=…/>` | How many "units" of capacity are consumed (e.g., # of vCPUs). Used for per-unit cost models. |
| `<ConsumptionCountUnit unitNameKey=…/>` | The unit-name key for the consumption count (e.g., "vCPUs"). |
| `<BufferPercent>` | Buffer percentage spec. |
| (nested `<CapacityDefinition>` / `<CapacityDefinitions>`) | Rare; for composite definitions. |
| `<CapacityTimeRemainingSettings>` | Container-specific time-remaining override. |

## `<PolicySettings>` — the analysis-settings ladder

PolicySettings carries the full ladder of settings that drive the capacity/risk/reclaim engines. Has 3 placements:

1. **`<BasePolicyAnalysisSettings>`** — the appliance-wide default analysis settings (per adapter-kind + resource-kind).
2. **Inline in `<OOTBPolicies><Policy>`** — bundled named policies the admin can opt into.
3. **Both** — OOTB policies typically `inheritPolicySettings="<base-key>"` and override only differences.

```xml
<PolicySettings key="default_policy-mongod" adapterKind="MONGODB_ADAPTER" resourceKind="mongod">
    <StressedSettings stressedPercentThreshold="1" logicOperator="OR">
        <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity"
                                     enabled="true" threshold="1"
                                     slaEntireRange="true" slaDuration="1"/>
    </StressedSettings>
    <UsableCapacitySettings useHA="false" capacityCalculationRule="LAST_KNOWN">
        <CapacityBuffer/>
        <OverCommit/>
    </UsableCapacitySettings>
    <WorkloadSettings>
        <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity" enabled="true"/>
    </WorkloadSettings>
    <CapacityTimeRemainingSettings capacityDetermination="TOTAL"
                                   provisioningTimeThreshold="30"
                                   useStress="true"
                                   includeCommittedProjects="true">
        <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity"
                                     enabled="true" threshold="30"/>
    </CapacityTimeRemainingSettings>
    <TimeSettings allHoursAndDays="true" dataRange="30"/>
    <ReclaimableCapacitySettings>
        <WasteSettings>
            <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity" enabled="true"/>
        </WasteSettings>
        <IdleSettings filterThreshold="90" logicOperator="AND">
            <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity"
                                         enabled="true" threshold="90"/>
        </IdleSettings>
        <PoweredOffSettings filterThreshold="90"/>
        <UnderusedSettings underusedPercentThreshold="1" logicOperator="OR"
                           recommendedSizePercentThreshold="50"/>
        <UnUsedSettings>
            <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity"
                                         enabled="true" threshold="180.0"/>
        </UnUsedSettings>
    </ReclaimableCapacitySettings>
    <DensitySettings>
        <ApplicableResourceContainer resourceContainerKey="mongod-connections_capacity" enabled="true"/>
    </DensitySettings>
</PolicySettings>
```

### `<PolicySettings>` attributes

- `key` (required) — stable identifier; referenced by OOTBPolicy.PolicySettings via `inheritPolicySettings`.
- `adapterKind`, `resourceKind` (required) — scopes the settings to a specific resource kind.
- `inheritPolicySettings` (optional) — references another PolicySettings.key to inherit from. Override only what differs.

### Per-setting block reference

#### `<StressedSettings>`

Defines when a resource counts as "stressed."

- `stressedPercentThreshold` (int %) — threshold above which a single sample counts toward stress.
- `logicOperator` — `AND` / `OR`. Combination across applicable containers.
- Child `<ApplicableResourceContainer>` (one per container that participates):
  - `resourceContainerKey` (required) — points to the container in CapacityDefinition
  - `enabled` (bool)
  - `threshold` (int %)
  - `slaEntireRange` (bool) — whether the SLA window applies to the entire data range
  - `slaDuration` (int hours) — SLA window duration

#### `<UsableCapacitySettings>`

How much capacity is actually usable for placement (after HA reserves, buffers, overcommit allowances).

- `useHA` (bool) — subtract HA-failover reserve from capacity
- `capacityCalculationRule` (`LAST_KNOWN` / other values TBD) — algorithm choice
- Child `<CapacityBuffer/>` — buffer percentage spec (typically empty in samples; nested attributes possible)
- Child `<OverCommit/>` — overcommit allowance spec

#### `<WorkloadSettings>`

Which containers feed the workload-automation / placement engine.

- Child `<ApplicableResourceContainer>`:
  - `resourceContainerKey`
  - `enabled` (bool)
  - `hidden` (bool, optional) — observed in vSphere; hides from UI without disabling

#### `<CapacityTimeRemainingSettings>`

Time-until-out-of-capacity projection. The Capacity > Time Remaining badge data.

- `capacityDetermination` (`TOTAL` / others) — how to compute the projection
- `provisioningTimeThreshold` (int days) — warning threshold
- `useStress` (bool) — factor stress samples into the projection
- `includeCommittedProjects` (bool) — count planned-but-not-deployed work
- Child `<ApplicableResourceContainer>` per axis with per-container `threshold`

#### `<TimeSettings>`

Which time window the analysis covers.

- `allHoursAndDays` (bool) — analyze 24x7 or restrict to business hours
- `dataRange` (int days) — analysis lookback window
- (richer time/day specifications possible — not observed)

#### `<ReclaimableCapacitySettings>` (wraps 5 sub-settings)

The Reclaim-Opportunity badge data. Wraps:

**`<WasteSettings>`** — over-provisioned containers. Just `<ApplicableResourceContainer enabled>` per axis.

**`<IdleSettings filterThreshold logicOperator>`** — idle resources.
- `filterThreshold` (int %)
- `logicOperator` (AND/OR)
- Child `<ApplicableResourceContainer threshold>` per axis

**`<PoweredOffSettings filterThreshold>`** — powered-off resources count as reclaimable.
- `filterThreshold` (int days — how long powered-off before reclaimable)
- Child applicable-containers if applicable

**`<UnderusedSettings>`** — chronically underused resources.
- `underusedPercentThreshold` (int %)
- `logicOperator` (AND/OR)
- `recommendedSizePercentThreshold` (int %) — sizing-recommendation factor
- No applicable-containers child (settings apply globally per resource)

**`<UnUsedSettings>`** — never-used resources.
- Child `<ApplicableResourceContainer threshold>` — threshold here is in days (e.g., `180.0` = "not touched in 180 days").

#### `<DensitySettings>`

Consolidation-ratio analysis. Just `<ApplicableResourceContainer enabled>` per axis.

#### `<RiskLevelSettings>` (vSphere-only observed)

Per-risk-category thresholds for risk-badge scoring. Two instances in vSphere; structure not fully sampled here.

#### `<WorkloadAutomationSettings>` / `<WorkloadOptimizationSettings>` (vSphere-only observed)

The DRS-equivalent settings — algorithm tuning for workload automation. vSphere has one of each; mongodb does not. These tie into the vCenter DRS / Cloud-Optimization engine integration. Detailed schema not enumerated here (vSphere-specific authoring).

#### `<BasePolicyAnalysisSettings>` (wrapper)

```xml
<BasePolicyAnalysisSettings>
    <PolicySettings key="..." adapterKind="..." resourceKind="...">
        <!-- ladder above -->
    </PolicySettings>
    <!-- more PolicySettings for other resource kinds -->
</BasePolicyAnalysisSettings>
```

Wraps the appliance's default analysis behavior. One per adapter (the implicit "Base Settings" policy that everything inherits unless overridden).

## `<OOTBPolicies>` — pre-bundled policies admins can opt into

```xml
<OOTBPolicies vendorNameKey="10000">
    <Policy key="62639a37-...-9064f9badcb7" nameKey="10042"
            parentPolicy="40578135-...-602b8e538f97">
        <PackageSettings>
            <Alerts adapterKind="VMWARE" resourceKind="VirtualMachine">
                <Alert id="AlertDefinition-VMWARE-VMWriteLatency" enabled="false"/>
                <Alert id="AlertDefinition-VMWARE-GuestOutOfDiskSpace" enabled="true"/>
                <!-- ... per-alert enable toggles ... -->
            </Alerts>
            <!-- more <Alerts> blocks per resource kind ... -->
        </PackageSettings>
        <!-- or instead: PolicySettings inheriting from base -->
        <PolicySettings key="ootb-..." adapterKind="..." resourceKind="..."
                        inheritPolicySettings="default_policy-..."/>
    </Policy>
</OOTBPolicies>
```

### `<OOTBPolicies>` attributes

- `vendorNameKey` (required, int → resources.properties) — vendor display string for the policy bundle (e.g., "VMware", "Broadcom").

### `<Policy>` attributes

- `key` (required) — UUID-style identifier in vSphere; descriptive string in mongodb.
- `nameKey` (required, int) — localized display name.
- `parentPolicy` (optional) — UUID of another OOTB policy to inherit from. Layered inheritance chains observed in vSphere.

### `<PackageSettings>`

Two observed shapes:

1. **Alert-enable toggles** (vSphere): inline `<Alerts adapterKind resourceKind>` containing per-alert `<Alert id enabled/>` toggles. Allows the policy to ship "enable these alerts, disable those" without restating the entire alert definition.
2. **Empty** (mongodb): the policy inherits everything from `parentPolicy` and PolicySettings.

PackageSettings is OPTIONAL. A Policy can have only PolicySettings (inherit-and-override) or only PackageSettings (alert-enable-overrides) or both.

## Cross-cutting concepts

### `<ApplicableResourceContainer>` (the per-axis applicability)

The most-repeated element in the settings ladder. Common attributes:

| Attribute | Setting blocks that use it |
|---|---|
| `resourceContainerKey` (required) | All settings — points to the `<ResourceContainer key>` |
| `enabled` (bool) | All settings — toggle the axis on/off for this setting |
| `threshold` (int — units depend on setting) | Stressed, CapacityTimeRemaining, Idle, UnUsed |
| `slaEntireRange` (bool) | Stressed |
| `slaDuration` (int hours) | Stressed |
| `hidden` (bool) | Workload (observed in vSphere) |

### Container linkage between resource kinds

The `consumer` / `provider` / `consumerResourceContainerKey` / `providerResourceContainerKey` attributes on `<ResourceContainer>` build a graph of capacity flow. E.g., a VM's `cpu` container is a CONSUMER of a Host's `cpu` PROVIDER container. The placement engine uses this graph for what-if calculations.

This is mostly relevant for adapters modeling resources that consume capacity from other resources (VMs from Hosts, containers from Nodes, etc.). Standalone adapters can ignore.

### The aria-ops 3-badge model maps to settings

| Aria Operations badge | Settings that feed it |
|---|---|
| **Health** | (not capacity-side; comes from KPI metrics + Anomalies — see spec/02a `ResourceAttribute.isKpi`) |
| **Risk** | StressedSettings + CapacityTimeRemainingSettings + RiskLevelSettings |
| **Efficiency** | ReclaimableCapacitySettings (Waste/Idle/PoweredOff/Underused/UnUsed) + DensitySettings + UsableCapacitySettings |

## Tier 2 generator implications

### Authoring complexity

The capacity+policy model is the LARGEST describe.xml authoring surface — easily 80% of a complex adapter's describe.xml volume goes here. VCF-CF should expose this as a structured authoring surface, not free-text XML.

### Templated authoring (recommended)

Most resource kinds need a SIMILAR settings ladder. VCF-CF should provide templates like:

- **"Simple metric-bag" template**: one StressedSettings + WorkloadSettings + TimeSettings per container; no Reclaimable; no Density. Suitable for adapters that just want to feed metrics + emit alerts.
- **"Full capacity-aware" template**: full ladder (the mongodb pattern). For adapters where users care about capacity planning.
- **"Placement-participant" template**: full ladder + consumer/provider linkage to a sibling kind. For adapters where the modeled resource interacts with vSphere placement (VMs, containers).

### Required vs optional decisions

Per the XSD enumeration in spec/02a, ALL setting blocks under PolicySettings are OPTIONAL except `<TimeSettings>` (which appears effectively required in practice — no PolicySettings observed without it). VCF-CF should:

1. Always emit `<TimeSettings allHoursAndDays="true" dataRange="30"/>` as a safe default.
2. Make WorkloadSettings + CapacityTimeRemainingSettings the next defaults if any container has capacity semantics.
3. Make StressedSettings / Reclaimable / Density opt-in.

### Container linkage requires graph awareness

If an adapter has cross-kind capacity flow (VMs consume from Hosts), VCF-CF's authoring layer needs a graph view, not just per-kind forms. The `consumer/provider` / `consumerResourceContainerKey` / `providerResourceContainerKey` attributes form a graph that must be consistent: if VM.cpu has `provider=true` and `providerResourceContainerKey="hostsystem-cpu"`, then Host's `cpu` container must exist with `consumer=true` and reciprocal linkage. Validate.

### OOTB policy hierarchy

vSphere ships 16 OOTBPolicies with a `parentPolicy` chain. VCF-CF should:

1. Always emit at least one base policy as `<BasePolicyAnalysisSettings>` so analysis works out of the box.
2. Allow users to ship named OOTB policies as variants (e.g., "Aggressive Reclaim", "Conservative Sizing").
3. Default `parentPolicy` to a base UUID the user must declare or auto-generate; never leave dangling parent references.

### Alert-enable PackageSettings is a powerful affordance

vSphere's pattern of shipping OOTBPolicies that toggle per-alert enable/disable is a clean way to ship multiple "tuning profiles" without duplicating alert definitions. VCF-CF should expose this as "ship N policy variants that differ only in which alerts are loud-by-default."

## Surfaces NOT enumerated in this pass

- **`<RiskLevelSettings>`** — vSphere-only; nested schema not sampled here. Two instances exist; structure deferred.
- **`<WorkloadAutomationSettings>` / `<WorkloadOptimizationSettings>`** — vSphere-only DRS-tuning. Deferred; ties into vCenter DRS integration that's out of scope for most adapter authors.
- **`<CapacityBuffer>` / `<OverCommit>` nested content** — observed as empty (`<CapacityBuffer/>` / `<OverCommit/>`). Likely has nested per-percent or per-strategy attributes; not sampled.
- **`<TimeSettings>` rich form** — only the simple `allHoursAndDays="true"` form observed. The schema likely permits per-day-of-week / per-hour-of-day overrides.
- **`<CustomGroupMetrics>`** — declared in XSD (spec/02a) but absent from all in-corpus adapters. **Would need a custom-groups adapter sample from Navani to characterize.**

## Open follow-ups

1. **`capacityCalculationRule` enum values beyond `LAST_KNOWN`** — only one observed; XSD likely lists more.
2. **`capacityDetermination` enum values beyond `TOTAL`** — same.
3. **`<CapacityBuffer>` and `<OverCommit>` schemas** — observed empty; need an adapter that uses them.
4. **`RiskLevelSettings` schema** — vSphere has 2; not sampled.
5. **Workload Automation vs Workload Optimization** — the distinction between the two vSphere-only settings types.
6. **CustomGroupMetrics** — Navani-gap (not in corpus).
