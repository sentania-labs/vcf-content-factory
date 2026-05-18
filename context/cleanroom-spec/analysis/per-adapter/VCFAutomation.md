# VCFAutomation — per-adapter analysis

**Adapter kind**: `VCFAutomation`
**Source pak**: `inputs/from-devel/paks/VCFAutomation-902025137921.pak`
**Decompiled at**: `analysis/decompiled/VCFAutomation/`
**Analysis date**: 2026-05-15
**Purpose**: Cross-pak relationship reference — VCFAutomation aggregates views across vSphere and SupervisorAdapter, declaring foreign-kind edges in **every single ResourcePath**.

## adapter.properties

```
ENTRYCLASS=com.integrien.adapter3.automation.AutomationAdapter
KINDKEY=VCFAutomation
```

## Resource model — 10 local kinds, all cross-MP wiring

10 ResourceKinds, 144 attributes, 2 TraversalSpecKinds, 9 ResourcePaths, 661-line describe.xml. **Schema version 49**.

**Local kinds**: `Automation World`, `AutomationAdapter Instance`, `Organization`, `VCFAOrganization`, `Project`, `ProjectAssignment`, `Region`, `RegionQuota`, `RegionQuotaStorageClass`, `RegionVMClass`.

**Foreign-kind references in describe.xml (9/9 ResourcePaths have foreign edges)**:
- `VMWARE::NamespaceV2`, `VMWARE::ResourcePool`, `VMWARE::VirtualMachine`, `VMWARE::Pod`
- `SupervisorAdapter::GuestCluster`, `SupervisorAdapter::KubernetesNode`, `SupervisorAdapter::KubernetesNamespace`, `SupervisorAdapter::KubernetesDeployment`, `SupervisorAdapter::KubernetesDaemonset`, `SupervisorAdapter::KubernetesStatefulset`

Example path:
```
VCFAutomation::Automation World
  ||VCFAutomation::AutomationAdapter Instance::child
  ||VCFAutomation::VCFAOrganization::child
  ||VCFAutomation::RegionQuota::child
  ||VMWARE::NamespaceV2::child
  ||SupervisorAdapter::GuestCluster::child
  ||SupervisorAdapter::KubernetesNamespace::child
  ||SupervisorAdapter::KubernetesDeployment::child
```

VCFAutomation acts as a **view-aggregator**: it owns lightweight
business-domain resources (Org / Project / Quota) and connects them
into vSphere's infrastructure topology AND SupervisorAdapter's
Kubernetes topology.

## BIG FINDING — foreign-resource lookup mechanism

The entry-class exposes:

```java
Map<String, Set<com.vmware.ops.api.model.resource.ResourceDto>> getProjectUUIDToVCNamespaceResourceDTOs();
Map<String, Set<com.vmware.ops.api.model.resource.ResourceDto>> getRegionQuotaUUIDToVCNamespaceResourceDTOs();
Map<String, com.vmware.ops.api.model.resource.ResourceDto>      getRegionQuotaUUIDToNSXTProjectResourceDTOs();
Map<String, Map<String, com.vmware.ops.api.model.resource.ResourceDto>> getNamepsaceVCFAReftoVCNamespaceResourceDTOs();
Table<String, String, String> getRegionOrgMapToRegionQuota();
Map<String, String> getNsxtURNToNSXTClusterID();
Map<String, String> getRegionToNSXTClusterID();
```

**`com.vmware.ops.api.model.resource.ResourceDto`** is a NEW API
package (not seen before). It represents **foreign resources at the
platform API level** — exactly the bridge an adapter needs to refer
to resources owned by other MPs.

Pattern (inferred): VCFAutomation queries the platform's SuiteAPI at
collection time for VC Namespaces (matching by some VCF Automation
ID), gets back `ResourceDto`s for those foreign vSphere resources,
and uses those DTOs to construct cross-MP relationships (and likely
to push metrics/properties at the foreign ResourceKeys those DTOs
represent).

**This answers the pass-4 open question**: how to synthesize a
`ResourceConfig` (or its equivalent) for a foreign ResourceKey. The
mechanism is: query the platform's API for matching foreign
resources, receive `ResourceDto`s, use those.

## AutomationAdapter signature highlights

```java
class AutomationAdapter extends AdapterBase {

    // Foreign-resource lookup state
    Map<ResourceKey, Collection<ResourceKey>> getLastRelationships();  // pushed-relationship cache
    Map<String, ResourceDto> getRegionQuotaUUIDToNSXTProjectResourceDTOs();
    Map<String, Set<ResourceDto>> getProjectUUIDToVCNamespaceResourceDTOs();
    Map<String, String> getNsxtURNToNSXTClusterID();
    // ...

    // Concurrency
    Queue<Future<?>> getMetricCollectorTasks();
    Queue<Future<?>> getRelationshipCollectorTasks();
    ExecutorService getMetricCollectTaskExecutor();

    // HTTP
    CxfClientSecurityContext getCxfClientSecurityContext();
    String getConnectionURL(AdapterConfig);
    Set<String> getCertificateRenewalUrls();
}
```

Notable patterns:

- **Explicit relationship cache** (`getLastRelationships()`): keeps the previous cycle's relationship set to detect deltas
- **Two-task-queue concurrency model**: separate executors for metrics and relationships, run in parallel during collect
- **Apache CXF** as the REST client framework (not the SDK-provided clients)
- **`oauth2-oidc-sdk-6.5.jar` in lib**: OAuth2/OIDC for authenticating to VCF Automation (modern auth flow)

## Lib inventory (38 jars, notable subset)

- `vrops-adapters-sdk.jar` (pinned, unversioned)
- `vcops-suiteapi-internal-client-2.2-all.jar` (internal Suite API — fits the Broadcom-internal pattern)
- `oauth2-oidc-sdk-6.5.jar` (OAuth2 client)
- CXF / SOAP/REST stack (transitive, presumably)

## Theories — pan-out / disprove ledger

### CONFIRMED — declarative cross-MP topology declaration generalizes

VCFAutomation declares 9 ResourcePaths and EVERY ONE crosses into a foreign adapter (VMWARE and/or SupervisorAdapter). The pattern from pass 4 (vSphere's single foreign edge to STORAGE_DEVICES::Mount) is the LIGHT version; VCFAutomation is the HEAVY version.

### NEW BIG FINDING — `com.vmware.ops.api.model.resource.ResourceDto` is the foreign-resource bridge type

The platform exposes a `ResourceDto` model class (in `com.vmware.ops.api.*`) that adapters use to refer to ANY platform-managed resource — local or foreign. VCFAutomation looks up foreign vSphere/NSXT resources by their UUIDs and gets back `ResourceDto`s. This is the **runtime API surface for cross-MP foreign-resource lookups** — a missing piece from pass 4.

`com.vmware.ops.api.*` is yet another new API package (alongside `com.broadcom.ops.data.*` from pass 4) — Operations has a layered API ecosystem with at least three identity models now visible:
- Legacy SDK: `ResourceKey` + `ResourceConfig` (`com.integrien.alive.common.adapter3`)
- Mid-layer: `ResourceDto` (`com.vmware.ops.api.model.resource`)
- New data SDK: `ResourceIds` (`com.broadcom.ops.data.model`)

### CONFIRMED — aggregator adapters are a valid pattern

VCFAutomation is the canonical "aggregator" / "view-builder" adapter — small native footprint, lots of relationship work, mostly busy looking up and joining resources from other MPs. This is a useful template for VCF-CF: simple adapters that just stitch a business-domain view over existing infrastructure resources can be generated easily.

### NEW — explicit relationship cache pattern

`getLastRelationships() / setLastRelationships()` returning `Map<ResourceKey, Collection<ResourceKey>>` — the adapter caches its own previous relationship set so it can detect added/removed edges and push deltas. This is a useful pattern for VCF-CF generator output (cheap to compute, helps the platform's topology delta-tracking).

## Tier 2 implications

1. **VCF-CF should expose foreign-resource references as first-class in its design language**. VCFAutomation's value is almost entirely in declaring cross-MP topology — generators producing aggregator-style adapters need a clean syntax for "I reference these foreign kinds".
2. **`com.vmware.ops.api.model.resource.ResourceDto` is the recommended type for foreign-resource handles**. Tier 2 generator should emit code that consumes this type when adapters need to push to foreign keys.
3. **Concurrency model** (parallel metric + relationship collectors) is a useful template for generated adapters with non-trivial work.

## Open / pass 7+ (final passes)

1. Full `com.vmware.ops.api.*` API surface
2. The path from `ResourceDto` → `ResourceConfig` → `addMetricData()` push
3. Identifier shape for `SupervisorAdapter::GuestCluster` and other K8s kinds (next-priority foreign attachment targets)

## Confidence

- Cross-MP declarative topology is real and widely used: **High** (corroborated by 3 adapters now — vSphere, mongodb, VCFAutomation)
- ResourceDto bridge: **High** — clean class name, plural usage, obvious purpose
- ResourceDto-to-push semantics: **Medium** — not yet traced end-to-end
