# 07 — Relationships, Topology, and Cross-MP Attachment

**Status**: DRAFT (pass 4 evidence — vSphere TraversalSpec, mongodb ExternalRelationship pattern)
**Evidence base**: vmwarevi_adapter3 describe.xml; mongodb's `ExUnoUtils$ExternalRelationship` class; SDK `ResourceKey`, `Relationships`, `ResourceRelationship`

## TL;DR

VCF Operations stitches a single topology graph across all installed management packs. Cross-MP edges are declared declaratively in describe.xml; cross-MP metric/property attachment is emergent from the **identity-based `ResourceKey`** — no special "external resource" API is required.

## Two modes of topology declaration

VCF Operations supports **two patterns** for declaring the topology
graph; adapters can use either or both.

### Mode A: Declarative `TraversalSpec` (compile-time)

The adapter declares its relationship structure in `describe.xml` via
`<TraversalSpec>` / `<ResourcePath>`. The platform stitches the topology
based on the declared shape + matched resource identities at runtime.

**When to use**: stable hierarchical structures that mirror the target
system's static object model.

**Used by**: vSphere (`vSphere World > Datacenter > Cluster > Host > VM`)

### Mode B: Runtime-pushed relationships (collection-time)

The adapter pushes relationship objects via the SDK's `Relationships`
API during `collect()`. The describe.xml does NOT declare any
`<TraversalSpec>` / `<ResourcePath>`; the topology is built entirely from
what the adapter pushes each collection cycle.

**When to use**: dynamic topologies where the shape changes based on
user-created objects (logical routers, segments, services, projects).

**Used by**: NSX (41 ResourceKinds with **zero declarative topology**;
the entire graph is built at runtime)

### Full `Relationships` API surface (Pass 21)

`com.integrien.alive.common.adapter3.Relationships` operations:

```java
class Relationships implements Serializable {
    // Standard (unlabeled) parent → children
    void addRelationships(ResourceKey parent, Collection<ResourceKey> children);
    void removeRelationships(ResourceKey parent, Collection<ResourceKey> children);
    void setRelationships(ResourceKey parent, Collection<ResourceKey> children);
    void setRelationships(ResourceKey parent, Collection<ResourceKey> children, Set<String> filters);
    void setRelationships(ResourceKey parent, Collection<ResourceKey> children, String label);

    // Generic (labeled/namespaced) — for typed relationships beyond plain parent/child
    void addGenericRelationship(ResourceKey parent, Collection<ResourceKey> children, String label);
    void addGenericRelationship(ResourceKey parent, Collection<ResourceKey> children, String label, String namespace);
    void removeGenericRelationships(ResourceKey parent, Collection<ResourceKey> children, String label);
    void removeGenericRelationships(ResourceKey parent, Collection<ResourceKey> children, String label, String namespace);
    void setGenericRelationships(ResourceKey parent, Collection<ResourceKey> children, String label);
    void setGenericRelationships(ResourceKey parent, Collection<ResourceKey> children, String label, String namespace);
    void setGenericRelationships(ResourceKey parent, Collection<ResourceKey> children, Set<String> filters, String label);
    void setGenericRelationships(ResourceKey parent, Collection<ResourceKey> children, Set<String> filters, String label, String namespace);

    // Bulk operations
    void addRelationships(Relationships other);    // merge another Relationships into this one
    void clear();

    // Inspection
    Collection<RelationshipItem> getRelationshipItems();
    boolean isEmpty();
    Long getTimestamp();
    void setTimestamp(Long timestamp);

    // Inner class
    static class RelationshipItem { ... }
}
```

**Three semantic axes**:

1. **add / remove / set** — the three operation modes:
   - `add` is incremental (additive)
   - `remove` deletes the named edges
   - `set` is REPLACEMENT (sets the parent's children to exactly this collection; not-in-this-set children get removed)

2. **standard vs generic** — unlabeled vs typed:
   - Standard relationships are simple parent/child (no name)
   - Generic relationships carry a `label` (relationship type, e.g., "depends_on", "connected_to") and optionally a `namespace` (for cross-adapter relationship-type disambiguation)

3. **bulk merge** — `addRelationships(Relationships other)` merges another whole Relationships object in. Useful when an adapter builds relationships in multiple stages and combines.

**Filter `Set<String>`** in the `set...` variants: limits the set-replacement to specific relationship labels — e.g., `setRelationships(parent, newChildren, Set.of("depends_on"))` only replaces the "depends_on" edges, leaving other labels untouched.

**Timestamps**: relationships carry a timestamp; the platform can age out stale relationships if not refreshed.

### Tier 2 generator guidance for Relationships API usage

- **For Mode B (runtime-pushed) adapters**: generate `set...` calls per collection cycle for stable relationship sets (the platform diffs); use `add`/`remove` only for incremental updates between cycles.
- **For mixed Mode A + Mode B**: declared relationships from `<TraversalSpec>` form the base; pushed `Relationships` augment with dynamic edges (the union).
- **For cross-MP relationships**: pass a `ResourceKey(adapterKind="VMWARE", resourceKind="VirtualMachine", identifiers=...)` as parent or child — **either direction persists** (confirmed below). Platform de-dupes by identity — same recipe as cross-MP metric attachment. **The foreign `ResourceKey` MUST carry the resource's real _uniqueness-bearing_ identifier set:** propagate each identifier's actual `isPartOfUniqueness` flag (from `resourceKey.resourceIdentifiers[].identifierType.isPartOfUniqueness`); **never hardcode all identifiers to unique.** Over-marking a non-uniqueness identifier (e.g. a VMWARE `Datastore`'s `DataStrorePath`/`VMEntityName` — only `VMEntityObjectID`+`VMEntityVCID` are uniqueness-bearing) yields a key that cannot bind, and the edge is **silently dropped** (emitted every cycle, processed by analytics, never persisted, zero log trace). See `lessons/cross-mp-foreign-key-uniqueness-flags.md`.
- **For labeled relationships** (e.g., your adapter models a graph with distinct edge types): use `Generic` variants with a label namespace specific to your adapter kind, to avoid collision with other adapters using similar labels.

### Practical guidance

- A declarative TraversalSpec is also what powers UI navigation
  panels (the "hierarchical view" trees). If your adapter wants
  custom UI navigation, you need at least some TraversalSpecKinds
  even if you also push relationships at runtime.
- Runtime-pushed relationships are the only mechanism for cross-MP
  edges discovered at collection time (e.g., NSX TransportNode → its
  hosting ESXi HostSystem, where the pairing is found by querying
  NSX's ComputeManager list).
- Cross-MP edges declared in TraversalSpec (e.g., vSphere's
  `STORAGE_DEVICES::Mount::child`) only stitch when both adapters
  actually have matching ResourceKey identities — declaration is
  pre-registration of the shape, not the actual relationship.

> **EMPIRICALLY CONFIRMED (VCF-CF, 2026-06-29, VCF Ops 9.0.2).** A runtime-pushed
> cross-MP edge persists **in either direction** (foreign resource as parent OR
> child) — direction is a non-constraint. The binding requirement is that the
> foreign `ResourceKey` carry the resource's real *uniqueness-bearing* identifier
> set (see the cross-MP relationships bullet above); a key that over-marks
> non-uniqueness identifiers is silently dropped. A declarative `<ResourcePath>`
> is **not** required for the runtime edge to persist (TraversalSpec is
> UI-navigation only). This resolves the parent-or-child question and open
> questions #3 (cardinality) and #7 (no per-MP security gate). Positive control:
> first-party `VirtualAndPhysicalSANAdapter` (vSAN) holds VMWARE
> `Datastore`/`HostSystem` as both parents and children on the same appliance.
> Evidence: synology `1.0.0.19`, `context/reviews/synology-build-19.md`;
> `lessons/cross-mp-foreign-key-uniqueness-flags.md`.

## Concepts

### Resource identity (recap from § 05)

Every resource in the platform is uniquely identified by:

```
ResourceKey = (adapterKind, resourceKind, resourceName, identifier tuple)
```

The adapter kind is **not scope** — it's part of the identity. Any
adapter can construct a ResourceKey targeting any (adapter kind,
resource kind) so long as it knows the identifier shape.

### Relationships

The platform tracks **parent/child relationships** between resources.
Relationships:

- Are typed by **edge kind**: `child` (parent → child) and inverse
  variants
- Can cross adapter-kind boundaries
- Are declared **declaratively** via `<TraversalSpec>` / `<ResourcePath>`
  in describe.xml
- Are populated **at runtime** when adapters push resources with
  matching identities

## `<TraversalSpec>` / `<TraversalSpecKind>` + `<ResourcePath>`

### Top-level structure

```xml
<TraversalSpecKinds>
    <TraversalSpecKind name="<friendly-name>"
                       description="<UI tooltip>"
                       filterType="GENERIC_RELATION"
                       iconName="<icon-file>"
                       nameKey="<int>"
                       rootAdapterKind="<adapter-kind>"
                       rootResourceKind="<resource-kind>"
                       usedFor="ALL">
        <ResourcePath path="<path-expression>"/>
        <ResourcePath path="<path-expression>"/>
        ...
    </TraversalSpecKind>
</TraversalSpecKinds>
```

A `TraversalSpecKind` defines a single navigable view in the UI — a
named perspective on the topology (e.g., "vSphere Hosts and Clusters",
"vSphere Storage", "vSphere Networking"). Each contains one or more
`ResourcePath`s; together they define the reachable nodes from the
root.

### `<TraversalSpecKind>` attributes

- **`name`** — UI display name
- **`description`** — UI tooltip
- **`filterType`** — observed: `GENERIC_RELATION`; other values TBD
- **`iconName`** — file in the adapter's `conf/images/TraversalSpec/`
- **`nameKey`** — i18n integer
- **`rootAdapterKind`** + **`rootResourceKind`** — the topology root
  for this traversal
- **`usedFor`** — observed: `ALL`; other values TBD (likely `UI`,
  `POLICY`, etc.)

### `<ResourcePath>` `path` syntax

The path is a `||`-delimited chain of levels:

```
ADAPTER_KIND::ResourceKind[::edge-modifier][/path-modifier]||ADAPTER_KIND::ResourceKind[...]
```

Per level (between `||`s):
- **`ADAPTER_KIND::ResourceKind`** — required; may name a foreign adapter kind
- **`::child`** — (optional, after the kind) — parent→child traversal
- **`::~child`** — (optional, after the kind) — **inverse** (child→parent)
- **`/recursive`** — (optional, end of segment) — descend recursively at this level
- **`/preferred`** — (optional, end of segment) — prefer this segment when multiple paths are available

### Example: intra-MP path

```
VMWARE::vSphere World
  ||VMWARE::VMwareAdapter Instance::child
  ||VMWARE::Datacenter::child
  ||VMWARE::HostFolder::child/recursive/preferred
  ||VMWARE::ClusterComputeResource::child
  ||VMWARE::HostSystem::child
  ||VMWARE::VirtualMachine::child
  ||VMWARE::Datastore::child
```

### Example: cross-MP path (foreign edge)

```
VMWARE::vSphere World
  ||VMWARE::VMwareAdapter Instance::child
  ||VMWARE::Datacenter::child
  ||VMWARE::StoragePod::child/recursive/preferred
  ||VMWARE::Datastore::child
  ||STORAGE_DEVICES::Mount::child            ← foreign adapter kind
```

The last segment references the `STORAGE_DEVICES` adapter kind. The
platform stitches the edge by **identity-matching** the Datastore
ResourceKey with whatever ResourceKey the STORAGE_DEVICES adapter has
declared as its parent (i.e., a `STORAGE_DEVICES::Mount`'s parent
identifiers must align with a `VMWARE::Datastore`'s identifiers, OR
both adapters push a relationship between them).

### Example: inverse-edge for join-style traversal

```
VMWARE::Datastore::child||VMWARE::VirtualMachine::~child
```

From a Datastore, traverse to VMs that USE the datastore (opposite of
the normal parent→child direction).

## Runtime relationship model — SDK side

The SDK provides:

- **`Relationships`** (in `com.integrien.alive.common.adapter3`) — collection of relationship items the adapter pushes per collection
- **`Relationships.RelationshipItem`** — individual relationship
- **`ResourceRelationship`** — single relationship value type

An adapter typically pushes relationships during `onCollect()` for the
resources it owns (the parent side) referencing child resources by
`ResourceKey`. For cross-MP relationships, the same applies — the
ResourceKey simply references a foreign adapter kind.

The aria-ops-core framework (mongodb's abstraction layer) wraps this
behind its `LiveCollector.getRelationships(ResourceConfig,
ResourceCollection)` method, which builds a `ResourceCollection`
including cross-resource relationship items.

## Cross-MP attachment — the answer

### How to push metrics/properties onto a foreign resource

A non-owning adapter (e.g., a database MP) attaches metrics to a
foreign resource (e.g., a vSphere VM) by:

1. **Discovering at collection time the foreign resource's identifier values.** For a vSphere VM, this means determining at least:
   - `VMEntityName` — vCenter's name for the VM
   - `VMEntityObjectID` — vCenter's MoRef ID (e.g., `vm-1234`)
   - and ideally `VMEntityVCID` (vCenter UUID) and `VMEntityInstanceUUID` (VM instance UUID)

2. **Constructing a `ResourceKey` targeting the foreign adapter kind**:
   ```
   ResourceKey vmKey = new ResourceKey(
       adapterKind = "VMWARE",
       resourceKind = "VirtualMachine",
       resourceName = vmName,
       identifiers = [
           ("VMEntityName",          vmName),
           ("VMEntityObjectID",      vcMoRef),
           ("VMEntityVCID",          vcInstanceUuid),
           ("VMEntityInstanceUUID",  vmInstanceUuid),
       ]);
   ```

3. **Obtaining the `ResourceConfig` (or its DTO equivalent) for this key.**
   - `AdapterBase.getMonitoringResource(ResourceKey)` returns the config for resources that **this adapter** is monitoring; not for foreign resources.
   - For foreign resources, query the platform's SuiteAPI to get a **`com.vmware.ops.api.model.resource.ResourceDto`** representing the foreign resource. *Observed in VCFAutomation: lookup maps from local IDs to `Map<String, ResourceDto>` populated at collection time.*
   - The `ResourceDto` is the runtime bridge between local adapter state and foreign-resource identity.

4. **Pushing metrics**:
   ```
   addMetricData(foreignResourceConfig, metricDataList);
   addMetricData(foreignResourceConfig, propertyList, true);  // isProperty=true
   ```

The platform de-duplicates resources by ResourceKey identity. The
metric/property data lands on the same physical resource record as the
owning adapter's collected data.

### How to declare a relationship (not just attach metrics)

In describe.xml, add a `<ResourcePath>` with a level that targets the
foreign adapter kind. At runtime, push the foreign resource's
ResourceKey as a relationship item (via SDK Relationships or
framework equivalent). The platform's topology engine then has both:

- The declarative shape (this MP's resources CAN relate to that
  foreign kind)
- The runtime identity-matched pairing (this specific resource
  relates to that specific foreign resource)

### Matching the foreign identity — the hard part

The non-owning adapter must compute the matching identifier tuple
from data it already has. Approaches observed:

- **BlueMedora's `ExternalRelationship` pattern** (see below) — a
  declarative join-rule applied at runtime against properties the
  adapter collects (typically IP and hostname).
- **Via SuiteAPI** — query the platform itself for resources matching
  some criterion (e.g., "give me the VM whose IP is X"). The
  `vcops-suiteapi-client-*.jar` (and the internal variant) provides
  the REST client.
- **Direct supply from the target system** — a backup/replication
  product might know the VM's UUID directly from its own metadata.

### BlueMedora's `ExternalRelationship` (proven pattern for IP/name matching)

`com.bluemedora.vrealize.adapter.mongodb.ExUnoUtils$ExternalRelationship` is a struct that declaratively pairs:

```java
class ExternalRelationship {
    String  kind;                // local resource kind that holds the join keys
    String  metric;              // local metric/property carrying the match value
    boolean kindIsParent;        // direction
    String  externalKind;        // foreign resource kind (e.g., VirtualMachine)
    String  externalPropertyKey; // property on foreign resource to match against
    boolean isVMRelationship;    // special-case the foreign adapter is VMWARE
    boolean isEpOpsRelationship; // special-case the foreign adapter is EpOps (older agent MP)
    String  ipMetric;            // local metric carrying IP for IP-match
    boolean ipMetricIsKey;
    String  nameMetric;          // local metric carrying hostname for name-match
    boolean nameMetricIsKey;
    boolean isResourceIdentifier;
}
```

The BlueMedora runtime (`com.bluemedora.exuno.*`) reads these rules,
queries for matching foreign resources at collection time, and
constructs the relationship + attaches metrics accordingly.

VCF-CF Tier 2 could adopt a similar declarative join-rule mechanism
in its design language.

## Identifier shapes for common foreign attachment targets

### `VMWARE::VirtualMachine` (vSphere VM)

| Identifier | Required | Length | Description |
|---|---|---|---|
| `VMEntityName` | yes | 100 | VM display name |
| `VMEntityObjectID` | yes | 100 | vCenter MoRef ID |
| `VMEntityVCID` | no | 256 | vCenter instance UUID |
| `VMEntityInstanceUUID` | no | 100 | VM instance UUID (cross-vCenter stable) |

(More foreign-kind identifier shapes will be inventoried in pass 5+
once we look at other broadly-referenced kinds like HostSystem,
Datastore, NSX Tier-0/Tier-1, etc.)

## Open / pass 5+

1. **Mechanism for synthesizing a `ResourceConfig` for a foreign ResourceKey** that this adapter doesn't own. Likely a SuiteAPI lookup or a static constructor — needs confirmation.
2. **Behavior when the foreign resource isn't yet discovered** by its owning adapter — does the metric attach to an orphan record, queue, or get dropped?
3. **Cross-MP relationship cardinality** — can a single child have parents in multiple adapter kinds simultaneously? **RESOLVED (2026-06-29): yes** — a VMWARE Datastore retained its VMWARE host/VM parents and simultaneously gained a synology parent. See the *EMPIRICALLY CONFIRMED* note in §"Tier 2 generator guidance".
4. **`filterType` values beyond `GENERIC_RELATION`**
5. **`usedFor` values beyond `ALL`**
6. **Whether ResourcePath can express more than two-level joins** (the observed paths are linear chains of `||` segments; n-way joins TBD).
7. **Security model** — are there any per-MP capability gates on cross-MP push? **RESOLVED (2026-06-29): no** — the only constraint on a cross-MP relationship write is identity correctness (the uniqueness-bearing identifier set); no per-MP capability gate observed.
8. **HostSystem, Datastore, NSX kinds** — inventory their identifier shapes (next-priority foreign-attachment targets).
