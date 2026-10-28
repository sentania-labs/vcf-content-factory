# Vanished objects: how a Tier 2 adapter says "this no longer exists"

Investigated 2026-10-28 by `api-explorer`. Trigger: a UniFi camera removed
from the controller in September stays in VCF Ops as `DATA_RECEIVING` with
frozen properties, and a new alert fired on them. Evidence only; every claim
carries its source. UNKNOWN means not established.

**Answer in one line.** The vSphere adapter and every other Broadcom adapter
checked mark a vanished object with
`AdapterBase.changeResourceState(rc, DiscoveryResult.StateChangeEnum.NOTEXIST)`
from inside `onCollect`. The platform shows it as `resourceState=NOT_EXISTING`,
health GREY, no collection status, and deletes it after the
`DELETED_OBJECTS_RETENTION_IN_HOURS` global setting. Our framework never makes
that call.

## Provenance of the binaries (RULE-015)

Local-only artifacts, not redistributable. The findings are summarized here in
full, so the citations are not needed to use this document.

- SDK jars: `vrops-adapters-sdk-2.2.jar` (9.0 line, the compile target),
  `vrops-adapters-sdk-8.18.7.jar`, `vrops-adapters-sdk-9.1.1.0100.jar`. Hashes
  and sources: `src/vcfcf_managementpacks/adapter_runtime/PROVENANCE.md`.
- Broadcom adapters: copied read-only from the 9.0 devel appliance
  (`/usr/lib/vmware-vcops/user/plugins/inbound/`), plus the platform jars
  `/usr/lib/vmware-vcops/common/lib/alive_platform.jar`,
  `/usr/lib/vmware-vcops/collector/lib/vcops-collector-1.0-SNAPSHOT.jar` and
  `/usr/lib/vmware-vcops/collector/lib/dockerized-adapter-plugin/v1_0/`.
  Every VCF Ops 9.x appliance has them. Method: `javap -c -p`
  (call sites and constants only; no decompiled source is reproduced here).

## 1. The SDK contract

All signatures are from `javap` and are identical in 8.18.7, 2.2 and
9.1.1.0100. The only `javap` delta across the classes below is three
`AdapterBase` members (`getCertificateRenewalUrls`, `registerInterface`,
`queryInterface`) that 8.18.7 lacks, and none of those is involved here.

### The call: `changeResourceState` with `NOTEXIST`

```
// com.integrien.alive.common.adapter3.AdapterBase
public void changeResourceState(ResourceConfig, DiscoveryResult$StateChangeEnum);
public void changeResourceState(ResourceConfig, DiscoveryResult$StateChange);

// com.integrien.alive.common.adapter3.DiscoveryResult
public void changeResourceState(ResourceConfig, DiscoveryResult$StateChange);

// DiscoveryResult$StateChangeEnum
NOTEXIST, START, STOP, START_MAINTENANCE, STOP_MAINTENANCE

// DiscoveryResult$StateChange
public StateChange(StateChangeEnum);
public StateChange(StateChangeEnum, Long, Long);
```

What `AdapterBase.changeResourceState(rc, StateChange)` does, from its bytecode.
The control flow is the same in all three jars:

1. It refuses and logs ERROR when `rc` is null, `rc.getResourceId()` is null
   (`"Could not change resource state for adapter '%s', resource config or
   resource id is null."`), or the state is null. **The `ResourceConfig` must be
   the platform's own copy that carries a resource id**: the one passed to
   `onCollect` or returned by `getMonitoringResource(...)`, not a freshly
   built one.
2. On the adapter instance itself, `STOP` and `START_MAINTENANCE` only log a
   WARN. It still records them.
3. It writes the change into the cycle's embedded discovery result:
   `collectResult.getDiscoveryResult(true).changeResourceState(rc, change)`.
   **So it works from `onCollect`.** It does not depend on `onDiscover`, which
   9.0.2 never calls for adapter3 adapters (see `VcfCfAdapter.java`
   `discoverOnCollect` Javadoc).
4. It increments `InstanceGeneratedMetrics.numberOfNotExistingResources`,
   whatever the enum value is.
   `AdapterBase.collectAdapterInstanceMetrics` reports that counter on the
   adapter instance.

The enum pairs with `CommonConstants$ResourceStateEnum.RESOURCE_STATE_NOTEXISTING`
(state code 14, label `"Not Existing"`, from the enum's static initializer).
The Suite API calls it `NOT_EXISTING` (`operations-api.json`, schema
`resource-status-state.resourceState`).

### Things that are not the mechanism

| Candidate | Signature | Why not |
|---|---|---|
| `ResourceStatusEnum` | `NONE, ERROR, UNKNOWN, DOWN, DATA_RECEIVING, OLD_DATA_RECEIVING, NO_DATA_RECEIVING, NO_PARENT_MONITORING, COLLECTOR_DOWN` | It has no "gone" value. On a child object the SDK accepts only `NONE`, `DATA_RECEIVING` and `NO_DATA_RECEIVING` (`cleanroom-spec/spec/19-adapterbase-behavioral-contract.md` §"Correction 2026-10-26"). |
| `ResourceConfig.setState(ResourceStateEnum)` | `public void setState(CommonConstants$ResourceStateEnum)` | No Broadcom adapter checked uses it for removal; every one uses `changeResourceState`. Whether a setter on the adapter-side copy reaches the platform is UNKNOWN. |
| `CollectResult.removeResourceCollectResult(Integer)` | `public void removeResourceCollectResult(java.lang.Integer)` | It drops this cycle's data for a resource. Nothing shows it changes the resource's state (UNKNOWN). |
| `AdapterBase.onRemoveResources(AdapterStatus, Collection<ResourceConfig>)` | callback | This is the platform telling the adapter that resources were removed. The adapter cannot use it to report a removal. |

## 2. What the Broadcom adapters do

The appliance jars were searched for `changeResourceState`, `NOTEXIST`,
`RESOURCE_STATE_NOTEXISTING`, `removeResourceCollectResult` and
`onRemoveResources`. Every hit below calls
`changeResourceState(rc, StateChangeEnum.NOTEXIST)`, and **every one is reached
from `onCollect`**.

| Adapter (kind) | Class.method | How "gone" is decided | Guard against marking on a bad read |
|---|---|---|---|
| vCenter (`VMWARE`), `vmwarevi_adapter3.jar` | `com.integrien.adapter.vmware.VMwareAdapter.tagEntities()`, called from `onCollect` (offset 1065) | Puts every resource from `adapterCache.getMonitoringResources()` and `getStoppedResources()` in a map as a candidate. Clears the flag for every object in this cycle's vCenter inventory cache (`getMonitoringResource(key)` / `getStoppedResource(key)`). Marks the rest `NOTEXIST`. Skips kinds the adapter does not source from vCenter (`VM Entity Status`, `CustomDatacenter`, `PhysicalDatacenter`). | `skipNonExistenceMarkingForIncompleteWcpObjects`: Supervisor (WCP) kinds are not marked until `WCPCollector.isFirstCollectionCompleted()`. |
| vSAN (`VirtualAndPhysicalSANAdapter`) | `com.vmware.adapter3.vsan.DiscoveryEngine.removeDeletedResources(monitoring, stopped)` → `handleResource`, from `VsanStorageAdapter.discover(rc)`, from `onCollect`. The two arguments are `adapterCache.getMonitoringResources()` and `getStoppedResources()`. | A monitored or stopped resource whose key is not in this cycle's inventory DTO set is marked `NOTEXIST`. | Keys of resources belonging to vCenters that failed this cycle (`InventoryDto.getVcFailedResources()`) are added to the present set, so a failed read never marks them. |
| NSX (`NSXTAdapter`) | `com.vmware.adapter3.nsxt.NSXTAdapter.markResourceNonExisting`, from `processMonitoringResources`, from `onCollect`. The set comes from `RelationshipProcessor.getNotExistingEntities()`, which returns `getAllResourceConfigs()` (monitoring plus stopped) minus this cycle's entities. | Diff of known resources against this cycle's entities. | The whole step is skipped when the adapter instance's `ResourceStatus.isDown()`. |
| VCF (`VcfAdapter.jar`) | `com.vmware.vrops.adapter.vcf.VcfAdapter.purgeDeletedResources` lambda, from `onCollect` | Uses the source's own deleted list (`DataResponse.getDeletedResources()`). The first cycle writes the property `summary\|ResourceStatus = "DELETED PARENT RESOURCE"`. A later cycle that finds that value already set calls `NOTEXIST`. | Two cycles. |
| vSphere infra management (`VMWARE_INFRA_MANAGEMENT`, `vim.jar`) | `com.vmware.adapter.management.core.A.A.A(Set, Endpoint)` (obfuscated) | An endpoint whose UUID is not in the current set is marked `NOTEXIST`. | Not traced. |
| MPB runtime (`mpb_adapter-9.0.1-patch-1.jar`) | `com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter.processDataForResource` | Calls `changeResourceState(rc, NOTEXIST)`. MPB-built paks therefore have the path. | Not traced. |
| Integration SDK container runtime (`alive_platform.jar`) | `com.integrien.alive.common.adapters.dockerized.DockerizedAdapterWrapper` (extends `AdapterBase`) `.processResult` → `processImplicitNotExistingResources`, `processExplicitNotExistingResources` | **Explicit:** every key in the container's `notExistingObjects` list is marked `NOTEXIST` at once. **Implicit:** a known resource (monitoring plus stopped) missing from the result accrues a miss count in `notExistingCandidates`, and once it reaches `implicitNotExistingMissedCycles` it is marked `NOTEXIST`. A resource that comes back is cleared from the candidates. | Implicit marking runs only when the result's `resourceResult` map is non-null and non-empty and the threshold is > 0. The threshold is the collector property `implicitNotExistingMissedCycles`: default `12` (`CollectorProperties` bytecode), set to `12` in devel's `/usr/lib/vmware-vcops/user/conf/collector/collector.properties:86`. |

The Dockerized wrapper is Broadcom's generic runtime for third-party
(Integration SDK) adapters. Of everything checked, it is the closest analogue
to our framework.

**Distinct case, not removal.** `VMwareAdapter.checkForUnprocessedObject` and
`publishData` set `RESOURCE_STATUS_NO_DATA_RECEIVING` on objects that **are**
in the inventory but produced no data. vSphere keeps `NO_DATA_RECEIVING` for
"present, no data" and `NOTEXIST` for "gone".

### Python Integration SDK

- Wire contract: `CollectResult.notExistingObjects: ObjectKey[]`, described as
  "Collection of not existing objects."
  (`reference/references/vmware-vcf-operations-integration-sdk/images/base-python-adapter/swagger_server/swagger/swagger.yaml:336`;
  `images/combined.json:328`). The platform's Gson model reads
  `@SerializedName("notExistingObjects")`
  (`io.swagger.client.model.CollectResult` in
  `vrops-dockerized-adapter-1.0.0-client.jar`), and
  `DockerizedAdapterApiConverter.convertNotExistingObjectsResult` maps it into
  the explicit path above.
- The `aria.ops` library never fills it, and spells the key differently. It
  always emits `"nonExistingObjects": []`
  (`lib/python/src/aria/ops/result.py:335`). The Kotlin library does the same
  (`lib/java/AdapterLibrary/src/main/kotlin/com/vmware/aria/operations/Result.kt:402`).
  The library has no API to populate it. `nonExistingObjects` appears nowhere in
  the platform client classes, so a Python pack built on the library can only
  reach `NOT_EXISTING` through the platform's implicit 12-cycle path.
- Live confirmation: `knowledge/context/python_integration_sdk.md` notes that
  our `vsanhostmetrics` fork has no not-existing code. Even so, 52 of its
  objects are `NOT_EXISTING` on devel 9.1 and 28 on devel 8.18, and the
  adapter instance (`a41ef1c9-…`) still exists (§3). The implicit path did that.

### vmbro reference paks

`reference/references/vmbro_vcf_operations_vcommunity/` and
`…_hardware_vcommunity/` contain no not-existing handling. A grep of their
`*.py` for not_exist, nonexist, notExist, stale and vanish returns only
guest-file and session cleanup. They push data onto vSphere-owned objects, so
the vCenter adapter owns those objects' lifecycle.

## 3. Live evidence (GET only)

Auth was the factory client's token acquire; Basic auth returned "Not
Authorized" on 9.0 devel.

### Global settings (`GET /api/deployment/config/globalsettings`)

The key names are mapped in `operations-api.json`,
`/api/deployment/config/globalsettings/metadata`: "Deleted Objects -
DELETED_OBJECTS_RETENTION_IN_HOURS, Deletion Scheduling Interval -
DELETION_SCHEDULING_INTERVAL_IN_HOURS, … Deleted Objects -
DELETED_OBJECTS_RETENTION_IN_HOURS_EXPANSION".

| Key | 9.0 devel | 9.1 devel | 8.18 devel | Doc default |
|---|---|---|---|---|
| `DELETED_OBJECTS_RETENTION_IN_HOURS` | `6` | `168` | `168` | 168 hours |
| `DELETION_SCHEDULING_INTERVAL_IN_HOURS` | `1` | `24` | `24` | 24 hours |
| `DELETED_OBJECTS_RETENTION_IN_HOURS_EXPANSION` | `[]` | not read | not read | (per-object-type overrides) |
| `DELETED_INSTANT_CLONES_RETENTION_IN_HOURS` | `168` | not read | not read | n/a |

**What these settings act on.** They act on objects the adapter has marked
not existing. VCF 9.0 doc, Global Settings, Table 1193
(`reference/docs/vmware-cloud-foundation-9-0.pdf`, page 4182; same text in
the 9.1 PDF, page 5353):

> An object deleted from an adapter data source is identified by VCF
> Operations as not existing and VCF Operations can no longer collect data
> about the object. Whether VCF Operations identifies deleted objects as not
> existing depends on the adapter. This feature is not implemented in some
> adapters. … This setting applies to objects deleted from the data source or
> server, not to any objects you delete from VCF Operations on the Inventory
> page.

> [Deletion Scheduling Interval] works with the Deleted Objects setting to
> remove objects that no longer exist in the environment. VCF Operations
> transparently marks objects for removal that have not existed for the length
> of time specified under Deleted Objects.

So an object the adapter never marks `NOT_EXISTING` is never removed by these
settings. The UniFi camera is in that state.

### A vCenter-reported deleted VM (9.1 devel)

`GET /api/resources?resourceState=NOT_EXISTING&pageSize=1000` returned 0 on
9.0 devel (retention 6 h), 540 on 9.1 devel and 30 on 8.18 devel. On 9.1:
483 `SupervisorAdapter`, 52 `VsanHostMetrics`, 4 `VMWARE` VirtualMachine and
1 `VMWARE` Pod. All 540 had health `GREY` and status states that carry
`resourceState` only.

`GET /api/resources/b6790099-cb8c-45cf-adf1-3da51de51f99` (VMWARE
VirtualMachine `vcf-lab-services-runtime-9x76k`, `VMEntityObjectID=vm-31456`):

```
resourceStatusStates: [{"adapterInstanceId": "752b566a-…", "resourceState": "NOT_EXISTING"}]
resourceHealth: GREY, resourceHealthValue: -1.0
```

The JSON has no `resourceStatus` key at all: neither `DATA_RECEIVING` nor
`NO_DATA_RECEIVING`. `GET …/stats/latest` returned 358 stats, newest at
2026-10-21 03:16Z. `GET /api/alerts?resourceId=…` returned 11 alerts, all
`CANCELED`. Whether the `NOT_EXISTING` mark itself cancelled them is
UNKNOWN: the API does not say when the mark was set.

### The UniFi camera (9.0 devel)

`GET /api/resources?adapterKind=unifi_controller&resourceKind=UniFiCamera`
returns two cameras named "Backyard". `23de209e-bc9b-4241-8ea9-b52f213cf217`
(MAC `18E829CFAE3F`) is the removed one:

```
resourceStatusStates: [{"resourceStatus": "DATA_RECEIVING", "resourceState": "STARTED", "statusMessage": ""}]
resourceHealth: RED
properties: Status|state = DISCONNECTED, Status|is_connected = false
active alert: [VCF Content Factory] UniFi Camera Offline, ACTIVE since 2026-10-27 19:45Z
stats/latest: Status|uptime last at 2026-09-12 19:07Z; the 14 platform keys
  (System Attributes|*, badge|*) stamped 2026-10-28 05:06Z,
  System Attributes|availability = 1.0
```

The adapter's last data point is 2026-09-12. Because the status is
`DATA_RECEIVING`, the platform still computes availability 1.0 and the alert
evaluates against the frozen property. The cause is in the framework and the
adapter: `UniFiAdapter.collectCamera` logs `"collect: camera <mac> absent from
snapshot"` and returns normally
(`content/sdk-adapters/unifi/src/com/vcfcf/adapters/unifi/UniFiAdapter.java:1356-1362`).
`VcfCfAdapter.onCollect` then sets `RESOURCE_STATUS_DATA_RECEIVING` on any
collect that does not throw
(`src/vcfcf_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java`,
line 1004, the "§1: REQUIRED per-resource status every cycle" block). Nothing in the
framework calls `changeResourceState`. The only mention is the
`VcfCfDiscoverer` Javadoc, which points at `DiscoveryResult` on the
`onDiscover` path.

## 4. Recommendation

**To match vSphere and Broadcom behavior, the framework should mark a resource
gone with `AdapterBase.changeResourceState(rc,
DiscoveryResult.StateChangeEnum.NOTEXIST)` from `onCollect`, using the
platform's `ResourceConfig` for that resource. It should never use a
`ResourceStatusEnum` value (`NO_DATA_RECEIVING` means "present, no data" in
vSphere), `setResourceDown` (refused on children), or a Suite API DELETE.**
Deletion is then the platform's job, on `DELETED_OBJECTS_RETENTION_IN_HOURS`
and `DELETION_SCHEDULING_INTERVAL_IN_HOURS`.

What every Broadcom adapter agrees on, and so what the framework must do:

1. **Diff against the platform's known set.** Use
   `adapterCache.getMonitoringResources()` plus `getStoppedResources()`
   (`AdapterCache` public API, identical in all three jars; the `adapterCache`
   field is `protected final` on `AdapterBase`) or `getAllMonitoringResources()`.
   Compare it with the `ResourceKey`s the adapter enumerated this cycle. In the
   framework that enumeration is `enumerateResources` under
   `discoverOnCollect()`.
2. **Mark only on a complete, successful read.** Every adapter checked has a
   guard: vSAN treats failed-vCenter resources as present, vSphere waits for
   the first full WCP collection, NSX skips when the instance is down, and the
   Dockerized wrapper skips empty results. For the framework this means no
   marking when `enumerateResources` throws (today `discoveryFailure`), when
   the cycle is cut, or when the instance is in failure.
3. **Mark only the adapter's own source-backed kinds.** vSphere excludes kinds
   it does not source from vCenter, and NSX excludes the instance. The adapter
   instance and synthetic or aggregate objects must never be marked.

Where the Broadcom adapters differ, so the framework has to pick (evidence for
each, no single answer):

- **Debounce.** vSphere, vSAN and NSX mark in the same cycle. VCF uses two
  cycles. The Dockerized wrapper, Broadcom's generic third-party runtime, uses
  an explicit list (immediate) plus an implicit count of 12 consecutive misses
  (collector property `implicitNotExistingMissedCycles`). The Dockerized model
  is the nearest precedent for a generic framework: an adapter SPI that can
  declare "gone now", plus an implicit N-miss default.
- **Optional sub-trees.** UniFi's Protect read is "genuinely optional … a
  Protect failure is logged INFO and the NVR/camera resources are simply
  absent" (`UniFiAdapter.java:111-112`). A naive diff would mark every camera
  `NOTEXIST` on one Protect outage. The adapter needs a way to say "this kind
  was not read this cycle". It is the same guard vSAN applies per failed
  vCenter.

### What is missing (UNKNOWN, needs an experiment the brief did not allow)

- **Recovery after a false mark.** Whether a `NOTEXIST` resource re-registered
  through `collectResult.addNewResource` (the framework's
  `registerNewResource`) or sent `StateChangeEnum.START` returns to `STARTED`.
  Nothing checked shows a Broadcom adapter sending `START` for this.
- **What `onCollect` receives afterwards.** Whether `NOT_EXISTING` resources
  still arrive in its `resources` argument before deletion.
- **Alerts.** Whether marking `NOT_EXISTING` cancels active alerts on the
  object (the 9.1 VM's alerts were all cancelled, but their timing does not
  settle it).
- All of these can be tested on devel by marking one throwaway object, but
  that is a state change and needs the orchestrator's approval.
