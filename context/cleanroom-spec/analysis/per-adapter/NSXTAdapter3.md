# NSXTAdapter3 — per-adapter analysis

**Adapter kind**: `NSXTAdapter`
**Source pak**: `inputs/from-devel/paks/NSXTAdapter-902025137922.pak`
**Decompiled at**: `analysis/decompiled/NSXTAdapter3/`
**Analysis date**: 2026-05-15
**Origin**: Broadcom internal, modern (`com.vmware.adapter3.nsxt.*` namespace)

## Structure

```
NSXTAdapter3.jar                                  # 430 classes, clean architecture, NOT obfuscated
NSXTAdapter3/
    conf/describe.xml                             # 1958 lines, 41 ResourceKinds, 848 attributes
    lib/                                          # 13 jars
        nsx-java8-sdk-9.0.0.jar                   # Manager API vendor SDK
        nsx-policy-java8-sdk-9.0.0.jar            # Policy API vendor SDK
        vapi-runtime-2.56.0.jar                   # VMware API Infrastructure
        vapi-authentication-2.56.0.jar
        bc-fips-2.0.0.jar                         # BouncyCastle FIPS (crypto)
        bcpkix-fips-2.0.4.jar
        json-path-2.4.0.jar                       # JSONPath for response parsing
        json-smart-2.4.10.jar
        vcops-suiteapi-internal-client-2.2-all.jar  # internal Suite API
        vrops-adapters-sdk.jar                    # platform SDK (pinned)
```

## adapter.properties

```
ENTRYCLASS=com.vmware.adapter3.nsxt.NSXTAdapter
KINDKEY=NSXTAdapter
```

## Architecture (visible from package layout)

The NSX adapter has a **clean, modern architecture**:

```
com.vmware.adapter3.nsxt
├── NSXTAdapter                       # entry-point (extends AdapterBase only)
├── cache/                            # caching layer
├── client/                           # HTTP client wrappers
├── collector/                        # collection engine
│   ├── commonmetrics/                # shared metric helpers
│   ├── managercollector/             # NSX-T Manager API path
│   │   ├── metrics/, resource/, thread/
│   └── policycollector/              # NSX-T Policy API path (newer)
│       ├── metrics/, resource/, thread/
├── entity/                           # POJOs for in-memory state
├── exception/                        # custom exceptions
├── parser/                           # response parsing
│   └── pojo/
├── properties/                       # config
└── util/
    ├── central_api/                  # NSX Central API helpers
    └── mp2policy/                    # Manager→Policy migration helpers
```

**Dual collector mode** (`managercollector` + `policycollector`):
NSX-T exposes both a legacy "Manager" API and a newer "Policy" API.
The adapter has parallel collectors for each. The `mp2policy` package
is a utility for converting Manager-API objects to Policy-API
representations (NSX-T's official migration path).

## NSXTAdapter signature

```
public class NSXTAdapter extends AdapterBase {   // no additional mix-ins

    // Heavy state caching — instance fields persist across collect() calls
    public Map<String, StatisticsRecord> managerNodeInterfaceStatsHashMap;
    public Map<String, LogicalRouterStatistics> routerStatisticsHashMap;
    public Map<String, Map<String, TransportNodeInterfaceStatistics>> transportNodeInterfaceStats;
    public Map<String, StatisticsRecord> transitGatewayStatsHashMap;
    public Set<String> discoveredNsxtHost;
    public Map<String, Long> metricTime;
    public int collectionCycleCount;

    // Cross-MP integration: knows the vCenter-equivalent compute managers
    public Map<String, ComputeManager> getComputeManagerMap();
    public String getVCIdForComputeManager(String);

    // ... lifecycle overrides
}
```

Two notable patterns:

1. **State cached across collection cycles** — instance fields hold
   per-resource state maps (statistics records, last collection
   timestamps). The adapter instance is reused across many `collect()`
   invocations. Confirms pass 1 open question: adapter lifecycle is
   reuse-the-instance, not fresh-per-cycle.
2. **ComputeManager tracking** — NSX knows which vCenters it manages
   and can resolve `VC-id-of-compute-manager`. This is the runtime
   handle for cross-MP relationship pushing: NSX-managed TransportNodes
   on ESXi hosts are connected to vCenter-managed HostSystems, and the
   adapter has the lookup to bridge them.

## Resource model — 41 ResourceKinds, NO declared topology

41 resource kinds across NSX-T's surface:

**Core fabric / management plane**:
`NSXT World`, `NSXTAdapterInstance`, `ManagementCluster`,
`ManagementNode`, `ManagementAppliances`, `ManagementService`

**Routing / connectivity**:
`LogicalRouter` + `LogicalRouterGroup`,
`Tier0LogicalRouterGroup`, `Tier1LogicalRouterGroup`,
`TransitGateway`, `RouterService`,
`CentralizedConnectionGroup`, `DistributedConnectionGroup`,
`ExternalConnection` + `ExternalConnectionGroup`

**Switching**:
`LogicalSwitch` + `LogicalSwitchGroup`

**Fabric**:
`TransportNode`, `TransportZone` + `TransportZoneGroup`,
`EdgeCluster` + `EdgeClusterGroup`, `EdgeTransportNodeGroup`,
`HostTransportNodeGroup`

**Security / services**:
`FirewallSection` + `FirewallSectionGroup`,
`Group` + `Groups`,
`NSService` + `NSServiceGroup` + `NSServiceGroups`,
`Certificate` + `CertificateGroup`,
`LoadBalancerService`, `LoadBalancerPool`,
`LoadBalancerVirtualServer` + `LoadBalancerVirtualServerGroup`

**Multi-tenancy (NSX 4.x)**:
`NsxProject` + `NsxProjectGroup`, `NsxVirtualPrivateCloud`

### Schema version 47

The describe.xml schema `version="47"` is between mongodb's 7 and
vSphere's 978 — mid-range. Not a global sequence — each adapter
maintains its own per-adapter schema version.

## BIG FINDING — declarative vs runtime-pushed topology

**NSX describes 41 ResourceKinds and ZERO TraversalSpecs / ZERO ResourcePaths.**

vSphere had 5 TraversalSpecKinds with 24 ResourcePaths declaratively
mapping out the topology. NSX has nothing declarative. So **the
topology has to be pushed at runtime** through the SDK's
`Relationships` API during `collect()`.

This is a fundamentally different pattern. Two valid approaches to
topology declaration:

| Pattern | When to use | Used by |
|---|---|---|
| **Declarative TraversalSpec/ResourcePath** | Stable hierarchical view that mirrors the target system's static structure | vSphere (datacenter > cluster > host > VM) |
| **Runtime-pushed relationships** | Dynamic topology that changes shape based on user-created objects | NSX (logical routers, switches, segments dynamically created/destroyed) |

Both can coexist within a single adapter. TraversalSpec is for **UI
navigation views** (the hierarchical tree panels users navigate); the
runtime `Relationships` API populates the actual topology graph used
for impact analysis, alert correlation, etc.

For VCF-CF Tier 2: generators should support both. Declaration-time
mode for stable shapes; runtime mode for adapters whose target system
has dynamic topology.

## CredentialKinds — 5 distinct kinds

NSX has 5 CredentialKinds (most in the corpus so far). Likely covers
authentication variants:
- Basic auth (user/password)
- Token / certificate-based
- Principal identity certificate
- Service account
- (5th TBD without grepping further)

NSX-T supports multiple auth modes (vIDM, local accounts, principal
identities) — the adapter exposes the matching credential shapes
declaratively.

## Theories — pan-out / disprove ledger

### CONFIRMED — adapter instance lifecycle is reuse-the-instance

Pass 1 open question resolved. NSX's heavy state caching across
collection cycles (`managerNodeInterfaceStatsHashMap`, etc.) confirms
the adapter object is constructed once and `collect()` is called
repeatedly against the same instance. This is consistent with
`AdapterBase`'s `Semaphore locker` field (suggesting at-most-one
collect-in-flight per instance).

### NEW — declarative vs runtime-pushed topology is a real axis

NSX has 41 ResourceKinds and zero declarative topology. The
relationship graph is built at runtime via the SDK's `Relationships`
API. Pattern coexists with vSphere's heavy-declarative approach.

VCF-CF Tier 2 must support both modes.

### CONFIRMED — `vrops-adapters-sdk.jar` (NO version!) is a valid pinning approach

NSX bundles `vrops-adapters-sdk.jar` without a version suffix. The
classloader resolves by filename, so this is just a pinned copy of
the SDK (likely 2.2 from devel, same as the standalone
`inputs/from-devel/sdk/vrops-adapters-sdk-2.2.jar`). Bundle without
version-in-filename is another valid form of SDK pinning.

### NEW — `vcops-suiteapi-internal-client-2.2-all.jar` is what Broadcom internal adapters use

Versions 1.0 (vim) and 2.2 (NSX) of the *internal* Suite API client
have been observed. Public clients are
`vcops-suiteapi-client-2.2-all.jar` (mpb-adapter). All four
combinations exist; first-party adapters tend to internal.

### NEW — NSX is clean modern architecture; lots of structural reuse possible

Top-level package layout (cache, client, collector with manager+policy
modes, entity, exception, parser, properties, util) is a clean
template for a typical "REST-API-of-a-vendor-product" adapter. A VCF-CF
generator that produces adapters for similar systems (network gear,
load balancers, etc.) could emit this exact layout.

### NEW — `mp2policy` migration utility is a flavor of pattern

NSX-T's official transition from Manager API to Policy API motivates a
migration helper in the adapter. Other adapters dealing with deprecated
APIs may need similar utilities; pattern worth noting for the SPEC's
"common patterns" appendix later.

## Tier 2 implications

1. **Topology declaration is dual-mode**: TraversalSpec (declarative) and runtime push are both supported and used in production. Generator must support both; pick based on target-system characteristics.
2. **Adapter object reuse across cycles** is now confirmed — generators can rely on instance fields surviving between collect() calls (cache state, last-collection-time, derived rates, etc.).
3. **NSX's clean layered architecture** (collector + parser + cache + client + entity) is a strong reference for vendor-product adapter generation.

## Open / pass 6+

1. Full SDK `Relationships` push API surface (the runtime alternative to TraversalSpec)
2. NSX's identifier shapes for `LogicalSwitch`, `Tier0LogicalRouterGroup`, `TransportNode` — next-priority foreign-attachment targets (for adapters that want to attach to NSX entities)
3. Whether NSX pushes runtime cross-MP relationships to `VMWARE::HostSystem` (likely yes — TransportNode runs on ESXi)
4. The 5th CredentialKind shape — what auth modes NSX supports
5. `mp2policy` migration pattern — depth of helper API

## Confidence

- Architecture observation: **High** — clean layered, well-named packages
- Adapter lifecycle reuse hypothesis: **High** — confirmed by extensive state caching
- Topology dual-mode finding: **High** — direct evidence of zero declarative topology with 41 ResourceKinds
- Runtime cross-MP push: **Medium** — inferred from `ComputeManager` machinery; specific code path not yet inspected
