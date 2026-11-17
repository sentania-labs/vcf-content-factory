# vmwarevi_adapter3 (the vSphere adapter) — per-adapter analysis

**Adapter kind**: `VMWARE` (per describe.xml and adapter.properties)
**Source pak**: `inputs/from-devel/paks/VMwarevSphere-902025137897.pak`
**Decompiled at**: `analysis/decompiled/vmwarevi_adapter3/` (from `inputs/from-devel/installed/vmwarevi_adapter3-installed.tar.gz`)
**Analysis date**: 2026-05-15
**Note**: This is the **first-party Broadcom vSphere adapter that owns the canonical VM/Host/Datastore/Cluster/Datacenter resource kinds** that all other MPs reference.

## Why this adapter is special

vSphere owns **the VirtualMachine ResourceKind** (and Host, Datastore, Cluster, ResourcePool, etc.). Cross-MP metric attachment to a VM happens by constructing a `ResourceKey` with `adapterKind=VMWARE, resourceKind=VirtualMachine` plus matching identifier values — so this adapter's identifier shape is the foreign-MP attachment contract for the rest of the ecosystem.

## adapter.properties

```
ENTRYCLASS=com.integrien.adapter.vmware.VMwareAdapter
KINDKEY=VMWARE
```

**Note the package**: `com.integrien.adapter.vmware` (old Integrien Alive namespace, continuously maintained). The class is *455 classes* in the entry-point jar — large but not vim-size; the lib/ does the heavy lifting (72 jars).

## What VMwareAdapter implements

```
public class VMwareAdapter extends AdapterBase
    implements VcCommunication,                              // ← NEW: vCenter-specific interface
               VcManagement,                                 // ← NEW: vCenter-specific interface
               compatibility.CompatibilityChecker,           // ← NEW: version-compat hook
               action.ActionableAdapterInterface {           // legacy actions

    // standard AdapterBase overrides (configure, describe, discover, collect, test, discard)
    // many vSphere-specific helper getters (TagRetriever, WCPCollector, HostNameResolver,
    //   PingStatisticsRetriever, VmcConfigLimitsRetriever, StatsMetaData, ...)
    // action methods: onAction(ActionParam), checkActionStatus(...)
    // cross-VC migration event: addCrossVcVmMigratedEvent(CrossVcVmMigratedEvent)
}
```

Three SDK interfaces I hadn't seen before are visible here:
- **`VcCommunication`** + **`VcManagement`** (in `com.integrien.alive.common.adapter3`) — the platform can query the vSphere adapter for its vCenter connection / management surface. Other adapters likely consume these via reflection/`queryInterface()`.
- **`CompatibilityChecker`** (in `.compatibility`) — declares the adapter's version-compat behavior.

## Resource model — 25 ResourceKinds, 13,279-line describe.xml

The full vSphere object inventory. Hierarchy (extracted from TraversalSpecs):

```
vSphere World (root)
└── VMwareAdapter Instance
    └── Datacenter / PhysicalDatacenter / CustomDatacenter
        ├── HostFolder, VMFolder, NetworkFolder, DatastoreFolder
        │   └── ClusterComputeResource
        │       ├── HostSystem (ESXi)
        │       │   ├── ResourcePool (recursive)
        │       │   │   └── VirtualMachine
        │       │   └── VirtualMachine
        │       └── VmwareDistributedVirtualSwitch
        │           └── DistributedVirtualPortgroup
        │               └── VirtualMachine
        ├── StoragePod (datastore cluster)
        │   └── Datastore
        │       ├── VirtualMachine     (~child = reverse traversal)
        │       └── STORAGE_DEVICES::Mount  ← FOREIGN-MP edge!
        └── Container resources:
            └── SupervisorCluster
                └── Namespace, NamespaceV2
                    ├── GuestCluster
                    │   └── VirtualMachine
                    └── Pod
```

### VirtualMachine — the canonical resource kind

```xml
<ResourceKind key="VirtualMachine" capacityModel="CapacityModel-VM" nameKey="100" showTag="true">
    <ResourceIdentifier key="VMEntityName"         identType="2" type="string" length="100" required="true"  dispOrder="1"/>
    <ResourceIdentifier key="VMEntityObjectID"                   type="string" length="100" required="true"  dispOrder="2"/>
    <ResourceIdentifier key="VMEntityVCID"                       type="string" length="256" required="false" dispOrder="3"/>
    <ResourceIdentifier key="VMEntityInstanceUUID" identType="2" type="string" length="100" required="false" dispOrder="4" default=""/>
    <ResourceIdentifier key="VMServiceMonitoringEnabled" identType="2" enum="true" hidden="true" .../>
    <ResourceIdentifier key="isPingEnabled"              identType="2" enum="true"              .../>

    <PowerState alias="summary|runtime|powerState">
        <PowerStateValue key="ON" value="Powered On"/>
        <PowerStateValue key="OFF" value="Powered Off"/>
        <PowerStateValue key="SUSPENDED" value="Suspended"/>
        <PowerStateValue key="UNKNOWN" value="Unknown"/>
    </PowerState>

    <!-- conditional Icon, 905 lines of attributes/groups/computed metrics ... -->
</ResourceKind>
```

**The VirtualMachine identity tuple** (for foreign-MP attachment):

| Identifier | Required | Length | Purpose |
|---|---|---|---|
| `VMEntityName` | yes | 100 | VM name as known to vCenter |
| `VMEntityObjectID` | yes | 100 | vCenter MoRef ID (e.g., `vm-1234`) |
| `VMEntityVCID` | no | 256 | vCenter instance UUID — disambiguates across multiple vCenters |
| `VMEntityInstanceUUID` | no | 100 | VM's platform-independent instance UUID |

A foreign adapter that wants to attach metrics to a specific VM must populate at least `VMEntityName` + `VMEntityObjectID` matching the VM's vCenter identity. `VMEntityInstanceUUID` is more stable across vMotion/re-registration; `VMEntityObjectID` is convenient (queryable from vCenter API) but tied to a particular vCenter.

### Other canonical ResourceKinds

All under adapter kind `VMWARE`:
`HostSystem`, `Datastore`, `StoragePod`, `ClusterComputeResource`,
`ResourcePool`, `Datacenter`, `PhysicalDatacenter`, `CustomDatacenter`,
`VmwareDistributedVirtualSwitch`, `DistributedVirtualPortgroup`,
`Folder`, `VMFolder`, `HostFolder`, `NetworkFolder`, `DatastoreFolder`,
`SupervisorCluster`, `Namespace`, `NamespaceV2`, `Pod`, `GuestCluster`,
`vSphere World`, `vSphere Private World`, `VMwareAdapter Instance`,
`VM Entity Status`

### TraversalSpec/ResourcePath syntax (the topology declaration)

```xml
<TraversalSpecKinds>
    <TraversalSpecKind name="vSphere Hosts and Clusters"
                       filterType="GENERIC_RELATION"
                       iconName="2.png"
                       rootAdapterKind="VMWARE"
                       rootResourceKind="vSphere World"
                       usedFor="ALL">
        <ResourcePath path="VMWARE::vSphere World
                            ||VMWARE::VMwareAdapter Instance::child
                            ||VMWARE::Datacenter::child
                            ||VMWARE::HostFolder::child/recursive/preferred
                            ||VMWARE::ClusterComputeResource::child
                            ||VMWARE::HostSystem::child
                            ||VMWARE::VirtualMachine::child
                            ||VMWARE::Datastore::child"/>
        ...
    </TraversalSpecKind>
</TraversalSpecKinds>
```

Syntax (now finally captured):
- `||` separates path levels
- `::` separates within a level: `ADAPTER_KIND::ResourceKind` or `ResourceKind::edge-modifier`
- Edge modifiers:
  - `::child` — parent→child traversal
  - `::~child` — INVERSE (child→parent)
- Path modifiers:
  - `/recursive` — descend recursively at this level
  - `/preferred` — preferred when multiple paths exist
- Cross-MP edges: an `ADAPTER_KIND` other than the declaring adapter's
  references foreign resources (e.g., `STORAGE_DEVICES::Mount::child`
  in vSphere's storage traversal points into the `STORAGE_DEVICES`
  adapter kind)

This is the **mechanism for cross-MP topology stitching**.

## ANSWER: How to stitch metrics/properties onto a foreign VM

Combined evidence from pass 3 mongodb + pass 4 vSphere:

### The fundamental mechanism

The SDK's **`ResourceKey` is identity-based**, not adapter-scoped. An adapter constructs a ResourceKey with `adapterKind` set to a foreign adapter (e.g., `VMWARE`) plus matching identifiers. When the adapter pushes data via `addMetricData(rc, MetricData)` where `rc` references that ResourceKey, **the platform de-duplicates by identity and stitches the metric onto the existing VM resource**.

There is **no `ExternalResource` class in the SDK** — the cross-MP capability is emergent from the `ResourceKey` identity model.

### The matching problem

The hard part is constructing the right ResourceKey for a foreign VM. A non-vSphere adapter has to discover at collection time:
- The VM's `VMEntityName`
- The VM's `VMEntityObjectID` and/or `VMEntityInstanceUUID`
- (Optionally) the vCenter's `VMEntityVCID`

…from data it already has (e.g., a database's `serverStatus` reports the host's IP; the adapter then has to map IP → VM identity).

### BlueMedora's `ExternalRelationship` (proven pattern)

mongodb's `ExUnoUtils$ExternalRelationship` is a declarative join-rule struct:

```java
class ExternalRelationship {
    String  kind;                  // my (local) resource kind
    String  metric;                // my metric/property carrying the match value
    boolean kindIsParent;          // direction of the resulting relationship
    String  externalKind;          // foreign resource kind (e.g., "VirtualMachine")
    String  externalPropertyKey;   // foreign property to match against
    boolean isVMRelationship;      // special-case the foreign adapter is VMWARE
    boolean isEpOpsRelationship;   // special-case the foreign adapter is EpOps
    String  ipMetric;              // IP match metric
    boolean ipMetricIsKey;
    String  nameMetric;            // name match metric
    boolean nameMetricIsKey;
    boolean isResourceIdentifier;
}
```

The pattern declaratively says "my local metric/property carries an IP and a name; pair it with the foreign VirtualMachine kind by IP+name". BlueMedora's runtime (`com.bluemedora.exuno.*`) reads these rules, queries the platform for matching foreign resources, constructs the ResourceKey, and pushes the relationship and any local-side metrics tied to it.

### describe.xml-level evidence

mongodb's describe.xml literally contains `VMWARE::VirtualMachine` references (its resource paths). The cross-MP topology declaration is done in the same way as intra-MP — the path just references a foreign `ADAPTER_KIND::ResourceKind`.

### Practical recipe for VCF-CF Tier 2 generated adapters

To attach metrics from a generated adapter (call it `MY_DB`) to a vSphere VM:

1. **In describe.xml**: declare a TraversalSpecKind / ResourcePath that includes `||VMWARE::VirtualMachine::child` (or `~child`) as the foreign-MP edge to the VM resource kind.
2. **At collection time**:
   a. Discover from your data source the VM-distinguishing properties (instance UUID, hostname, IP, VC UUID).
   b. Construct a `ResourceKey` with adapterKind=`VMWARE`, resourceKind=`VirtualMachine`, identifier values populated.
   c. Push a metric via `addMetricData(rc_for_that_key, MetricData)`.
3. **Identity caveats**:
   - The foreign VM must already be discovered by the vSphere adapter — push to a non-discovered key likely creates an orphan record (behavior under-evidenced; verify).
   - The matching identifier(s) you supply must MATCH vSphere's identifier values exactly — case-sensitive, length-bounded.
   - `VMEntityInstanceUUID` is the most stable cross-vCenter identifier; prefer it when available.
4. **For relationships** (not just metrics): the platform stitches the topology from the union of all adapters' ResourcePath declarations + matching ResourceKey instances. No additional API call is needed.

### Security note

There is no permission model on cross-MP attachment. Any adapter that can construct a matching ResourceKey can push metrics/properties to any resource. The "VC UUID" portion of the VM identity is the only effective scope boundary.

## NEW SDK layer — `vcf-ops-data-sdk-1.0-SNAPSHOT.jar` (Broadcom-namespaced)

Discovered in vSphere's lib/. Top-level packages:

- `com.broadcom.ops.data.{common, config, metrics, model, observer, specs, stream, subscriber}` — generic data-pipeline layer
- `com.broadcom.ops.data.common.{auth, collect, model, util}`
- `com.broadcom.ops.data.vc.{auth, collect, lookupservice, metrics.converter, model}` — vCenter-specific

This is **a new SDK parallel to the legacy `com.integrien.alive.common.adapter3.*`**:
- Broadcom-namespaced (post-acquisition naming)
- Stream/subscriber/observer architecture (event-driven)
- Built-in vCenter integration (lookupservice, metrics.converter)
- A `specs/` subsystem (description / schema?)

`StatsData` signature:

```java
class StatsData {
    Map<ResourceIds, Map<String, Value>> values;   // resource → metric name → Value
    Calendar timestamp;
}
```

The `ResourceIds` type (separate from the legacy `ResourceKey`) suggests a **different identity model** in this SDK. Likely the future direction; not used by the adapter contract (yet).

Flag for **dedicated pass**: this SDK probably hosts the next-gen adapter API VMware is building toward. Worth understanding before VCF-CF settles its abstraction layer.

## Action subsystem — vSphere ships a LOT of actions

`com.integrien.adapter.vmware.actions.*` packages:

| Subpackage | Action |
|---|---|
| `modifydrsconfig` | Modify DRS settings |
| `movevm` | Migrate VM (vMotion / storage vMotion) |
| `rebalance` | Trigger DRS rebalance |
| `reconfigurevm.allocationconfig` | Reconfigure VM CPU/memory allocation |
| `reconfigurevm.cpumemoryvalue` | Set CPU/memory raw values |
| `removesnapshot` | Delete VM snapshots |
| `resourcekindobjects` | (generic resource-kind operation) |
| `scripts.dispatch` | Dispatch a script execution |
| `scripts.guestoperation.impl` | Execute commands inside guest OS |
| `scripts.guestoperation.validators` | Validate guest operations |
| `states` | Power on / off / suspend, etc. |

Each action subpackage typically has `param/` and `request/` subdirs —
ActionParam → outbound request model. This is the **largest action
surface in the corpus** and the de-facto reference for legacy
`ActionableAdapterInterface` usage.

## Theories — pan-out / disprove ledger

### CONFIRMED — describe.xml ResourcePath uses `ADAPTER_KIND::ResourceKind` notation with cross-MP support

The `STORAGE_DEVICES::Mount::child` path entry in vSphere's `vSphere Storage` traversal is the smoking gun: ResourcePath references foreign adapter kinds without ceremony.

### CONFIRMED — `~child` is the inverse-edge modifier in ResourcePath

```
VMWARE::Datastore::child||VMWARE::VirtualMachine::~child
```

This traverses from Datastore "outward" to VirtualMachines that USE the datastore (going against the normal child-of direction). Pattern lets a single traversal spec combine forward and reverse edges.

### CONFIRMED — cross-MP metric attachment is via `ResourceKey` identity matching

No special SDK API. Adapters push to a ResourceKey targeting a foreign adapter kind; the platform de-duplicates by identity. mongodb does this via BlueMedora's ExUno; the same is achievable by any adapter that knows the foreign identifier shape.

### NEW — three vSphere-specific SDK interfaces

- `VcCommunication`, `VcManagement` (in `.adapter3.*`) — vCenter-connection contracts the platform / other adapters query for
- `CompatibilityChecker` (in `.adapter3.compatibility`) — version-compat hook

These are not in the SDK survey (pass 1). The pattern of "per-adapter-kind extra interfaces" is worth noting for VCF-CF — generated adapters typically won't need these, but the SDK supports them.

### NEW — `vcf-ops-data-sdk` is a parallel modern SDK

Broadcom-namespaced (`com.broadcom.ops.data.*`), stream/subscriber/observer architecture, with vCenter-integrated metric-converter subpackages. Distinct from the legacy adapter3 SDK. Likely the future direction. Needs a dedicated pass to characterize its public API.

### NEW THEORY — VMware is migrating to a new adapter SDK

Two pieces of evidence:
1. `vcf-ops-data-sdk` (Broadcom-namespaced, stream-based) in lib/ alongside the legacy adapter3 SDK
2. NMP task system (`com.vmware.vrops.nmp.task` — pass 2) is also a parallel modern interface

Hypothesis: there is an in-progress migration from the Integrien adapter3 / actions model to a stream-based Broadcom-namespaced data-SDK + NMP task model. VCF-CF Tier 2 should track this. For now, the legacy SDK is what adapters compile against.

### CONFIRMED — vSphere action surface is the canonical reference for legacy actions

Eleven categorized action subpackages; matches the breadth of operations vSphere admins expect from the UI. mpb-adapter (pass 1) showed the action declaration pattern minimally; vSphere shows it at production scale.

## Tier 2 implications

1. **Foreign-MP metric attachment is supported by default** via ResourceKey identity. Tier 2 generator should expose this in its design language (e.g., "this metric attaches to a VirtualMachine identified by (name, instance UUID)").
2. **TraversalSpec syntax is fully specified** — generator can emit topology declarations.
3. **`VMWARE::VirtualMachine` identifier shape** documented; generators producing adapters that attach to VMs should target `(VMEntityName, VMEntityObjectID, VMEntityVCID, VMEntityInstanceUUID)` tuples.
4. **`vcf-ops-data-sdk` should be characterized before VCF-CF freezes its abstraction layer** — it may be more future-proof to target than the legacy adapter3 SDK.
5. **Action subsystem at scale is rich and Java-heavy** — declaration-only action generation likely isn't feasible for non-trivial actions; generated adapters needing actions will require user-provided Java per-action.

## Open / pass 5+

1. Full `vcf-ops-data-sdk` public API survey
2. `VcCommunication` / `VcManagement` interface signatures
3. `CompatibilityChecker` interface
4. Confirm orphan-metric behavior when foreign ResourceKey doesn't yet exist on the platform
5. `<PowerState>` / `<Icon>` / `<Condition>` / `<Case>` element schemas (rich evidence in vSphere; not yet documented in SPEC)
6. `<CapacityModel>` / `<CapacityDefinition>` schema (vSphere references `CapacityModel-VM`)
7. How `<ResourcePath>` references resolve when the foreign adapter kind isn't installed — graceful degradation?

## Confidence

- ResourcePath / TraversalSpec syntax (including cross-MP edges): **High**
- Cross-MP ResourceKey mechanism: **High** — corroborated by mongodb's ExternalRelationship code and vSphere's `STORAGE_DEVICES::Mount` reference in describe.xml
- vcf-ops-data-sdk significance: **Medium** — surface seen, semantics inferred but not validated
- Specific identifier values needed to construct a foreign VM ResourceKey: **High** — directly read from vSphere describe.xml
