# Platform edge-creation engine + storage-pak degraded path (bytecode autopsy)

**Question (one sentence):** Platform-side, what code actually creates
resource-to-resource (cross-MP) edges, what identity does it demand, is
there any reported-property→edge path, what does the TraversalSpec
declaration really do, and what do the vendor storage paks do when their
lookup fails — i.e. the full menu of edge-creation mechanisms Synology
must pick from.

**Domain boundary (explicit):** this is the PLATFORM-jar + storage-pak +
devel-appliance counterpart to a parallel Oracle-live/prod-CP autopsy
owned by another agent. **Nothing here touches prod.** All platform
bytecode was read on the devel appliance
(`vcf-lab-operations-devel.int.sentania.net`, key-based root SSH,
read-only); all vendor-pak bytecode was read from local `references/tvs/`
copies. No config changed anywhere (not even log levels). No lab objects
created.

**Method:** `scp` five platform jars off devel to scratchpad; local
`javap -p -c` (bytecode, JDK 17). Vendor paks unpacked from
`references/tvs/` to scratchpad; `javap -c` on `aria-ops-core-7.1.0.jar`
and the Nimble collector. Jars read:

| jar (devel path `/usr/lib/vmware-vcops/common/lib/`) | role |
|---|---|
| `vcops-collector-controller-1.0-SNAPSHOT.jar` | the edge WRITER (`RelationshipManager`, `DiscoveryProcessor`, `ResourceKeyIdCacheUtil`) |
| `persistence-1.0-SNAPSHOT.jar` | `ResourceKey` identity semantics, `ResourceCache`, describe/TraversalSpec metadata |
| `vcops-analytics-1.0-SNAPSHOT.jar` | correlation / relationship cache |
| `alive_platform.jar` | `RelationshipParam`, `TraversalSpecQualifier`, view/query params |
| `vcops-suiteapi-internal-client-2.2.jar` | Suite API client (no relationship classes) |

**Evidentiary discipline (user-mandated):** every mechanical claim quotes
a named file / class+method / bytecode offset / log-string / log line.
Anything else is tagged **INFERENCE**.

---

## TL;DR

1. **There is exactly one edge-writer entrypoint reachable from an
   adapter's CollectResult:** `DiscoveryProcessor.handleDiscovery()` →
   `RelationshipManager.updateRelationshipsInXDB(Integer)` →
   per-`RelationshipItem` `ResourceKeyIdCacheUtil.getResourceUuidFromLocalCache(ResourceKey)`.
   **If the parent's ResourceKey does not resolve to an existing resource
   UUID, the whole relationship item is silently dropped** (`aload 7;
   ifnull 260` in `updateRelationshipsInXDB`). No foreign resource is
   created, no fuzzy/name match is attempted.

2. **The resolve is a full-ResourceKey hash lookup, and for any kind that
   declares uniqueness identifiers the key is
   `(adapterKind, resourceKind, {uniqueness identifiers})` with the
   resourceName IGNORED.** `ResourceKey.hashCode()`/`equals()` branch on
   `getUniquenessIdentifierCount()`: name is used **only** when the kind
   has zero uniqueness identifiers. `VMWARE::Datastore` has two
   (`VMEntityObjectID`, `VMEntityVCID`, both `identType="1"`), so a
   name-only or `DataStrorePath`-only key **cannot** hash to it → null →
   dropped. **This is the mechanical reason build-25 created no edge.**

3. **There is NO reported-property→edge path in the edge-writer stack.**
   The literal `relationships|` appears in **zero** classes across all
   five jars; the only edge-creation API,
   `RelationshipManager.addRelationship(RelationshipParam)`, takes a
   `RelationshipParam` whose fields are `UUID parent` + `Set<UUID>
   children` — it structurally **cannot** be handed a name or a
   `Datastore_parent` property value. Confirms the negative result:
   the platform does not consume a `relationships|<Kind>_parent` REPORTED
   property to build an edge.

4. **`<TraversalSpecKind>` is describe METADATA + a VIEW/QUERY navigation
   descriptor. It never creates edges.** It is parsed by
   `TraversalSpecKindDescriber.updateTraversalSpecTypes()` into a
   `ResourcePathKind` bean (a path string + wildcard-propagation level)
   and consumed by the view engine via `TraversalSpecQualifier`
   (`maxHops`, `HierarchyType`). `RelationshipManager` references
   `TraversalSpec` **zero** times. This is why build-25's describe.xml
   traversal (present since build 18) produced no edge.

5. **The vendor storage degraded path = silent no-op.**
   `RelationshipInfo.addParent` iterates the Suite-API lookup result; an
   **empty** result (offset 55 `ifeq 85`) skips to the next candidate,
   and exhaustion falls to `iconst_0; ireturn` — no edge, no partial-key
   push, no cache, no exception. `getResourcesFromSuiteApi` wraps the
   Suite API call in `catch(Exception)` (exception table
   `24 472 475 Class java/lang/Exception`), logs `Logger.error`, and
   returns the empty accumulator — so a CP 403 is swallowed into "found
   nothing" → no edge. **On a Cloud Proxy the storage paks are de-facto
   primary-only: they silently no-stitch, identical to our build-25
   result.**

6. **The full menu (Q4): every platform edge-creation mechanism requires
   a resolved target UUID or a full uniqueness-identifier ResourceKey.**
   No mechanism accepts a name/path/NAA value as an edge endpoint. The
   only difference between them is *where the UUID resolution happens*
   (adapter-supplied full key vs. Suite-API read vs. platform-API caller
   supplies UUID). None of them is a property→edge path.

---

## Q1(a) — the CollectResult relationship consumer, and what it does with partial keys

### The chain

`references`: all in
`vcops-collector-controller-1.0-SNAPSHOT.jar`.

```
adapter CollectResult (adapter3.Relationships: parent+children ResourceKeys)
  → com.vmware.vcops.platform.common.InternalDiscoveryResult
  → com.integrien.alive.controller.persistence.DiscoveryProcessor.handleDiscovery()
  → new RelationshipManager(adapter3.Relationships)
  → RelationshipManager.updateRelationshipsInXDB(Integer)
  → RelationshipManager.manageRelationships(Collection<RelationshipInfo>, Integer, Date)
  → persist edge
```

`DiscoveryProcessor` holds
`private final com.vmware.vcops.platform.common.InternalDiscoveryResult
discoveryResult;` and its ctor is
`DiscoveryProcessor(InternalDiscoveryResult, boolean, ResourceKindIdentsCache)`
— i.e. the adapter's collected result (resources + relationships) is the
input. `DiscoveryProcessor` and `RelationshipManager` are the **only**
classes in the five jars that call `updateRelationshipsInXDB`.

### The identity gate (verbatim bytecode)

`RelationshipManager.updateRelationshipsInXDB(java.lang.Integer)`, per
`RelationshipItem`:

```
 69: ... Relationships$RelationshipItem.getParent()  → adapter3.ResourceKey
 76: invokestatic ResourceKeyIdCacheUtil.getResourceUuidFromLocalCache(ResourceKey) : java.util.UUID
 81: astore 7
...
139: aload 7
141: ifnull 260          // parent UUID null → SKIP this whole item
144: ... getChildren() ...
156: ...stream().map(<getResourceUuidFromLocalCache>).filter(<non-null>).collect(toList)  // children that don't resolve are filtered out
```

**Finding:** the consumer resolves the parent ResourceKey to a UUID
against the local resource cache; **null parent → the item is skipped
(no edge)**; children that fail to resolve are filtered out of the child
set before persisting. There is no "create the missing resource",
no name-fallback, no queue-for-later.

### What "resolve" means (the decisive semantics)

`ResourceKeyIdCacheUtil.getResourceUuidFromLocalCache(ResourceKey)` →
`getInternalIdFromLocalCache(ResourceKey)`:

```
18: ResourceDataConversionUtil.convertToPersResourceKey(adapter3.ResourceKey) : persistence.ResourceKey
24: IResourceCachingService.getIntIdByResourceKey(persistence.ResourceKey, true) : Integer
```

`ResourceCachingService.getIntIdByResourceKey(ResourceKey, boolean)` is a
one-liner: `ResourceCache.getCachedResourceData(resourceKey, flag)`.
`ResourceCache.getCachedResourceData(ResourceKey, boolean)` is
`resourceKeyToDataMap.get(resourceKey)` — an **in-memory HashMap lookup**
keyed by the `ResourceKey`. On miss it logs (named log line):

```
"resource: {} does not exist in resourceKeyToDataMap, this could be a new resource"
```

and returns null. **No DB fallthrough in this path** — it is the
collector's in-memory inventory map. So "resolve" = "is a resource with
this exact ResourceKey already in this node's inventory map".

`persistence.ResourceKey.hashCode()` (bytecode):

```
adapterKind (hashStringIgnoreCase) * 31
+ resourceKind (hashStringIgnoreCase) * 31
if getUniquenessIdentifierCount() == 0:    // offset 28 ifne 51
    + resourceName (hashStringIgnoreCase)  // NAME-based key
else:
    for each getIdentifyingIdentifiers():  // identType=1 identifiers
        + ResourceIdentifier.hashCode()    // IDENTIFIER-based key; resourceName NOT hashed
```

`equals()` mirrors it (offsets 150/157 `getUniquenessIdentifierCount(); ifne 225`):
name compared only when **both** keys have zero uniqueness identifiers;
otherwise `getIdentifyingIdentifiers()` compared.
`getUniquenessIdentifierCount()` counts `resourceIds` where
`ResourceIdentifier.isPartOfUniqueness()==true`; `getIdentifyingIdentifiers()`
returns exactly those.

**Answer to Q1(a):** the CollectResult relationship consumer **requires a
fully-formed ResourceKey that carries the foreign resource's uniqueness
identifiers.** For `VMWARE::Datastore` that is `(VMEntityObjectID,
VMEntityVCID)`. A partial/name-only key resolves to null (kinds with
uniqueness identifiers never key on name) and the relationship is
**silently dropped**. This is the mechanical explanation of build-25's
byte-perfect `VMFS:|naa…|` value producing no edge: that value is a
`DataStrorePath` (`identType="2"`, `isPartOfUniqueness()==false`) — it is
not part of the key, so it cannot make the key hash to the datastore.

---

## Q1(b) — is there a reported-property → edge path? NO.

Three independent negatives:

1. **No literal.** `unzip -p '*.class' | strings | grep 'relationships|'`
   over all five jars = **0 hits**. The property key
   `relationships|Datastore_parent` is assembled at describe-parse time
   from the `relationships` ResourceGroup key + the `Datastore_parent`
   attribute key; **no class in the edge stack hard-keys on it.**

2. **No `_parent`/`_child` consumer.** Across all five jars only one class
   references those tokens —
   `com.integrien.alive.dbaccess.AnalyticsDBUtil` — and its strings are
   the DB column names `id_parents` / `id_children` (and aspectj
   `reflect`), not a describe property key. No edge-creation code reads a
   `<Kind>_parent` property value.

3. **The only edge API is UUID-typed.**
   `RelationshipManager.addRelationship(RelationshipParam)` and
   `setParentChildRelationship(RelationshipParam)` are the sole public
   edge-write methods; `RelationshipParam`'s fields are
   `public final java.util.UUID parent;` and
   `public final java.util.Set<java.util.UUID> children;`. A property
   string can never enter here without prior UUID resolution.

**Answer to Q1(b):** confirmed — there is **no property→edge path** in the
platform edge-writer stack. A reported `relationships|<Kind>_parent`
value is inert as far as edge creation is concerned. (This is fully
consistent with the user's fact (2): those name-form properties are a
REFLECTION of pre-existing edges, not an input to them.)

**INFERENCE (labeled) — the reflection writer (Q1(c)):** the edge→property
"reflection" writer is **not** in the five relationship jars, and a fast
class-name scan of *every* jar under `/usr/lib/vmware-vcops` for
`genealog|geneolog|RelationshipProperty|ReflectRelationship|ParentProperty`
returned **zero** distinctly-named classes. So the reflection is computed
by a generically-named property/inventory component (candidate: the
property-population path that materialises describe-declared
`relationships` ResourceGroup attributes from a resource's existing edge
set). I could not pin the exact class within the read-only,
bytecode-only budget — **labeled INFERENCE**, corroborated by (i) the
user's empirical prod observation that name-form `Datastore_parent`
properties pre-existed any adapter emitting them, and (ii) the total
absence of a property→edge consumer above. **Boundary:** a full-content
`grep` across all jars for the writer timed out (SIGTERM at 200s over
~hundreds of jars, exit 143) and was not retried, per read-only/no-cost
discipline; pinning the writer class is a bounded follow-up if it ever
becomes load-bearing (it is not, for the Synology menu).

---

## Q1(d) — tag / RESOURCE_LOCATION / container attach-by-name mechanisms

- **aria-ops-core `RelationshipDefinition$RESOURCE_LOCATION` is just an
  enum `{LOCAL, EXTERNAL}`** — a flag distinguishing the adapter's own
  resource from a foreign one. It is **not** a location/name attach
  mechanism.
- **Platform tag/app/group containers go through the SAME
  `RelationshipManager`** (and therefore the same UUID gate):
  `GeoLocationTagMgmtUtil`, `RuleBasedAppCreator`, `GroupManagerUtil`,
  `PlatformServer`, `ControllerServer` all reference `RelationshipManager`.
  These attach resources to **local** tag/app/group container resources;
  none is a name-based foreign-resource attach that bypasses UUID
  resolution.
- The vendor `.sdm` "container" grouping (`nimble_volume_tag`, etc.,
  documented in `tvs-declarative-stitching.md`) likewise gathers foreign
  nodes under a **local** tag kind and only ever walks **already-present**
  edges (`(parents this "Datastore")`) — it presupposes the base edge.

**Answer to Q1(d):** no attach-by-name/identifier foreign mechanism
exists at the platform layer. Every container/tag/geo path is UUID-gated
through `RelationshipManager`.

---

## Q2 — Pure / storage degraded path (bytecode-quoted failure branch)

Source: `references/tvs/PureStorageFlashArray-4.3.0_…pak` →
`aria-ops-core-7.1.0.jar`; and
`references/tvs/HPENimble-5.2.0_…pak` → `nimblestorage_adapter3.jar`.

### The lookup (aria-ops-core `ResourceDtoClient.getResources(RelationshipInfo, String)`)

```
 1: resourceCache.getResources(info, value)          // ResourceDtoCache
16: ifne 95                                           // cache hit → use it
20: resourceCache.indexIsComplete(info); ifne 95      // index complete → trust empty
41: [log] "Calling getResourcesFromSuiteApi on ... (key type: ...)"
88: getResourcesFromSuiteApi(info, value)             // Suite API READ
99: [log] "Got cached values on ..."
```

### The 403/exception swallow (`DtoClient.getResourcesFromSuiteApi(ResourceQuery)`)

```
35: ResourcesClient.lookupResources(ResourceQuery, PageInfo)  // the Suite API call
...
509: Logger.error(...)                 // in the catch block
523: Logger.debug(msg, Throwable)
528: areturn                           // returns the (empty) accumulator
Exception table:
   24  472  475   Class java/lang/Exception
```

The Suite API read is wrapped in `catch(Exception)`; on failure (CP 403,
timeout, etc.) it logs an error and returns whatever it accumulated —
**empty** on a failed lookup.

### The degraded no-op (`RelationshipInfo.addParent(ResourceDtoClient, Resource, Collection<String>)`)

```
 1: <values>.iterator()
15: ifeq 88                     // no candidate values → return false
34: ResourceDtoClient.getResources(info, value)      // resolve datastore
41: <result>.iterator()
55: ifeq 85                     // result EMPTY → skip to next value (NO edge)
74: ResourceDtoClient.addRelationship(local, foreignDto)   // only when a DTO was found
77: ifeq 82
80: iconst_1; ireturn           // edge made
88: iconst_0; ireturn           // all values exhausted, nothing resolved → NO edge
```

**Finding:** when the Suite API lookup returns nothing — including the CP
403 case, which `getResourcesFromSuiteApi` turns into an empty result —
`addParent` iterates an empty collection, calls `addRelationship`
**never**, and returns `false`. **No partial-key push, no cache of a
pending edge, no exception surfaced to collection.** The collection cycle
completes "successfully" with no stitch.

### Nimble (explicit-collector variant, same shape)

`NimbleStorageLiveCollector` (its relationship method):
`SuiteAPIClient.getResources(...)` over `ldc "Datastore"`, match
`ldc "volume::serial_number"` against `ldc "|serial_number"`, then inside
the result loop `SuiteAPIClient.addGeneralParentRelationship(dto, resource)`
and log `"Made relationship between volume < ... > and datastore < ... >"`.
An empty `getResources` list means the loop body never runs → no
`addGeneralParentRelationship`, no "Made relationship" log — the same
silent no-op. (Method carries its own `catch` blocks, consistent with
the aria-ops-core swallow.)

**Answer to Q2:** the vendor storage paks, on lookup failure/unavailable
(the CP condition), **skip the edge silently** — no partial key, no
cache, no error. This settles that the storage corpus is **de-facto
primary-only**: on a Cloud Proxy their behaviour is identical to our
build-25 result (collection succeeds, no stitch appears). They are not a
CP-safe creds-free stitch; they are an in-appliance stitch that quietly
degrades to no-stitch off-primary.

---

## Q3 — what `<TraversalSpecKind>` actually does at runtime

Two consumers, neither an edge-creator:

1. **Describe metadata parse (`persistence` jar).**
   `TraversalSpecKindDescriber.updateTraversalSpecTypes()` (its only
   public method besides the ctor) reads the describe `TraversalSpecKind`
   collection and produces `ResourcePathKind` beans. `ResourcePathKind` is
   a plain serializable bean:
   `String resourcePathString; String targetResources; int
   maxPropogationLevelOfWildCard;`. That is a **navigation path
   definition** (the `||`-chained path string + a wildcard-propagation
   bound), stored as metadata. Sibling classes:
   `TraversalSpecKind`, `TraversalSpecExtensionKind`,
   `ContentDescribeProcessor`, `DescribeConversionUtil`,
   `AuthorizationUtils` — all describe/metadata, none writes edges.

2. **View / query navigation (`alive_platform` jar).**
   `TraversalSpecQualifier` (`int maxHops; HierarchyType hierarchyType;
   Map<String,String> variableToMetricKey;`) is used by the view search
   params — `ListViewSearchParam`, `TrendViewSearchParam`,
   `DistributionViewSearchParam`, `RollupViewSearchParam`,
   `ViewSearchParams`. This is the machinery that **walks existing edges**
   N hops to populate list/trend/distribution/rollup views and the
   inventory navigation tree.

3. **`RelationshipManager` (the only edge-writer) references
   `TraversalSpec` ZERO times** (`grep -c` on the class = 0).

**Answer to Q3:** `<TraversalSpecKind>`/`<ResourcePath>` is a
**navigation-tree / view-query descriptor over edges that already exist**;
it declares the *shape/path* the UI and view engine may traverse and how
far a wildcard propagates. It does **not** participate in edge creation.
This is load-bearing and confirms the build-25 negative: shipping the
traversal in describe.xml (since build 18) can never, by itself, cause an
edge to form — the traversal is consumed by the view/navigation layer,
not the edge writer.

---

## Q4 — Synthesis: the full menu of platform edge-creation mechanisms

Every mechanism that can create a resource-to-resource edge, with its
identity requirement. **All are UUID/full-key gated; none accepts a
name/path/NAA as an endpoint; none is a property→edge path.**

| # | Mechanism (class·method) | Endpoint identity it demands | CP-safe? | Evidence |
|---|---|---|---|---|
| 1 | **SDK CollectResult push** — adapter returns `adapter3.Relationships`; `DiscoveryProcessor` → `RelationshipManager.updateRelationshipsInXDB` | A ResourceKey that resolves in the node's in-memory `resourceKeyToDataMap` = `(adapterKind, resourceKind, {uniqueness identifiers})`. For Datastore: `(VMEntityObjectID, VMEntityVCID)`. Name/path key → null → dropped. | **Yes IF the adapter can construct the true uniqueness-identifier key** (resolution is a local map, not a Suite API read). But the array cannot know `(VMEntityObjectID, VMEntityVCID)` without help. | `updateRelationshipsInXDB` `ifnull 260`; `ResourceKey.hashCode/equals`; `ResourceCache.getCachedResourceData` map.get |
| 2 | **Platform relationship API** — `RelationshipManager.addRelationship / setParentChildRelationship(RelationshipParam)` (what Suite API `POST resources/{id}/relationships` and vendor `addParent`/`addGeneralParentRelationship` ultimately hit) | `RelationshipParam{UUID parent; Set<UUID> children}` — endpoints must **already be resolved UUIDs**. | Only as CP-safe as the UUID-resolution step feeding it. Vendors resolve via a **Suite API read** → **403 on CP**. | `RelationshipParam` fields; `addParent` → `getResources`(Suite API) → `addRelationship` |
| 3 | **Local tag / app / group container** — `GeoLocationTagMgmtUtil`, `RuleBasedAppCreator`, `GroupManagerUtil` | Same UUID gate via `RelationshipManager`; attaches to a **local** container resource, not a foreign name-attach. | Same as #1/#2. | classes reference `RelationshipManager`; `RESOURCE_LOCATION{LOCAL,EXTERNAL}` is a flag only |
| — | **Reported `relationships|<Kind>_parent` property** | *(none — not an edge input)* | n/a | Q1(b): no consumer; edge→property reflection only |
| — | **`<TraversalSpecKind>` describe declaration** | *(none — navigation/view only)* | n/a | Q3: `ResourcePathKind`/`TraversalSpecQualifier`, 0 refs in `RelationshipManager` |

**The single hard invariant across the whole menu:** a cross-MP edge to
`VMWARE::Datastore` requires, somewhere in the chain, the datastore's
**uniqueness identifiers `(VMEntityObjectID, VMEntityVCID)`** — either
supplied directly in a CollectResult ResourceKey (mechanism 1, local-map
resolve, CP-safe *if you can build the key*) or obtained by resolving a
non-unique search value (name / `DataStrorePath` / serial) to the full
DTO via a **Suite API read** (mechanism 2, the vendor path, **403 on
CP**). `DataStrorePath` / NAA / name are `identType="2"` non-unique — they
can only ever be **search keys** for mechanism 2, never edge endpoints.

**What this means for Synology (the menu Synology must pick from):**

- **Mechanism 1 is the only CP-safe SDK-native edge**, and it requires the
  adapter to produce a Datastore ResourceKey carrying `(VMEntityObjectID,
  VMEntityVCID)`. The Synology array does not know those values. Getting
  them CP-side without a Suite API read means reading vCenter directly
  (a vCenter credential + the datastore's backing-device NAA →
  MoRef/instance-UUID) — the vSAN-style idiom the storage corpus never
  uses (cross-ref `tvs-datastore-binding-value.md` strategy #3).
- **Mechanism 2 (copy the TVS idiom verbatim) works only on the
  primary/data node**; on a CP the Suite API read 403s and, per Q2, the
  stitch silently no-ops.
- **The reported-property route (build-25) is a dead end for edge
  creation** — Q1(b)/Q3 show no property→edge and no traversal→edge path;
  the property is a reflection of edges that some *other* mechanism
  already made. (Whether the Oracle-live edge on prod is made by
  mechanism 1 with a name-keyed VM — VM's own identity can be name-based
  if it lacks uniqueness identifiers, unlike Datastore — is the parallel
  Oracle/prod agent's domain; note the asymmetry: a **VM** matched by
  name can key on `resourceName` **iff** its kind declares zero uniqueness
  identifiers, whereas **Datastore** always has two, so the name/path
  route that could conceivably work for VM cannot work for Datastore.)

---

## Corrections / reconciliations against prior maps

- `tvs-datastore-binding-value.md` open item — "whether a path-valued
  `Datastore_parent` correlates CP-side is an untested experiment":
  **now answered NO at the platform layer.** There is no property→edge
  consumer and no traversal→edge consumer in the edge-writer stack
  (Q1(b), Q3). The build-25 negative was not a value-format problem; it
  is architectural — the platform has no code path from a reported
  `relationships|Datastore_parent` value to an edge. Any working
  correlation must run through mechanism 1 or 2 (UUID/full-key), i.e.
  through the datastore's `(VMEntityObjectID, VMEntityVCID)`.
- `tvs-cross-mp-stitching.md` / `tvs-declarative-stitching.md` framed the
  descriptor traversal as "necessary but not sufficient." **Sharpened:**
  the traversal is *navigation-only* (Q3), so it is not even part of the
  edge-creation sufficiency question — it neither helps nor hinders edge
  formation; it only renders/queries edges that already exist.

## Flags / limits

- `javap -c` bytecode only; no decompiler. No obfuscation — class/method
  names intact throughout platform jars and aria-ops-core.
- **Reflection-property writer (edge→property, Q1(c)) not pinned to a
  class** — labeled INFERENCE; the full-jar content scan timed out (SIGTERM
  200s) and was not retried under read-only/no-cost discipline. The
  *negative* (no property→edge consumer) is solid across the five core
  jars; the *positive* writer is a bounded follow-up, not load-bearing.
- Devel DNS was stable this session (no backup-internet flakiness hit);
  all five jars transferred and disassembled locally.
- Prod untouched; no config/log-level changes anywhere; no lab objects
  created. Scratchpad copies of jars/paks are session-isolated and
  ephemeral.

## Follow-up questions

1. **(Owner: Oracle/prod agent)** Given no property→edge and no
   traversal→edge path platform-side, which mechanism makes Oracle's
   live VM edge on prod — mechanism 1 (CollectResult push with a
   name-keyed VM ResourceKey, viable *only if* the VM kind declares zero
   uniqueness identifiers) or mechanism 2 (Suite API resolve)? The VM's
   `getUniquenessIdentifierCount()` on prod decides it.
2. **(Bounded, optional)** Pin the reflection-property writer class to
   fully close Q1(c) — a targeted content grep of the inventory/property
   webapp jars, not the whole tree.
3. **(Synology design)** Can a CP-resident adapter obtain a datastore's
   `(VMEntityObjectID, VMEntityVCID)` without a Suite API read — i.e. via
   a vCenter credential (mechanism 1 CP-safe path)? That is the only
   menu item that is both CP-safe and edge-producing.
