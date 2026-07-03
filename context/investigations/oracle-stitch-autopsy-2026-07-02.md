# Oracle DB pak — cross-MP VM edge: end-to-end autopsy (caught in the act)

**Date:** 2026-07-02
**Author:** api-explorer
**Question (one sentence):** By exactly what mechanism does the Oracle
Database pak create its `oracle_database_oracle_database_instance "FREE"`
→ `VMWARE::VirtualMachine "oracledemo"` edge on a Cloud Proxy, and does
that mechanism transfer to a Synology `VMWARE::Datastore` stitch?

**Method:** (1) Static `unzip` + `javap -p -c` on
`references/tvs/OracleDatabase-9.1.0_b20240520.165914.pak` (contrast:
`OracleDatabase-7.0_3.0.0_b20200917.104035.pak`), scratchpad only,
`references/` untouched. (2) Live read-only Suite API dump on prod primary
`172.27.8.41`. (3) Live on prod CP `172.27.8.51` (collector, instance
`664864`): **one permitted write** — a scoped DEBUG logger added to
`.../conf/collector/log4j2.properties`, recorded, then removed (md5
restored). Caught two collection cycles at DEBUG and captured the stitch
in the act.

**Evidentiary discipline (user-mandated):** every claim quotes a named
file / class+method / log line. Anything else is tagged **INFERENCE**.

---

## TL;DR — the mechanism, NAMED

**Oracle's VM edge is NOT declarative describe.xml correlation and NOT a
lookup-free key push. It is the aria-ops-core additive external-relationship
stitch resolved by a per-cycle Suite API READ — the SAME idiom as the TVS
storage paks — and it works on the Cloud Proxy because the Suite API token
is acquired as the platform-injected per-adapter-instance principal
(username = the adapter instance UUID `48fb5d76-…`), which carries
resource-read RBAC. It is name/hostname-keyed.**

- **X (the creator):** `com.vmware.tvs.vrealize.adapter.core.extensions.relationships.ExternalRelationshipCollection.createRelationships(loggerFactory, SuiteAPIClient, ResourceCollection)`, invoked **every collection cycle** by `AdapterLiveCollector.getCurrentMetrics`. Additive `addRelationship` onto a Suite-API-resolved `ResourceDto`.
- **Y (the key it carries):** it does **not** construct a foreign `ResourceKey`. It **searches** Suite API for the VM two ways — (a) `RESOURCE_NAME` regex `(?i)^\Qoracledemo\E$`, and (b) property `config|name == oracledemo` — then makes the additive edge to the **resolved** VM DTO, which carries the VM's true unique identity (`VMEntityObjectID=vm-16043`, `VMEntityVCID=4ff53df1-…`). The search value is the Oracle instance's `General|host_name` metric = `oracledemo`.
- **Z (the data source):** the DB's own reported hostname (the `HostName` instance metric, from the Oracle target), **not** vCenter, **not** operator config.
- **W (why it works on a CP):** the token is acquired **as the adapter-instance principal** `48fb5d76-80f0-4062-b32b-c11ff824ee2b`, and the acquire + the VMWARE resource query both **succeed** on the CP. This is a different identity from `maintenanceuser.properties` (`cloudproxy_<uuid>`, empty roles → 403) that our `SynologyStitcher` hand-reads.

**This overturns the prior three investigations' shared conclusion** that
"OracleDBAdapter never calls the suite-api door" / "the stitch is a
describe.xml `VMWARE::VirtualMachine::~child` ResourcePath traversal
resolved by the platform" (`recon_log.md` 2026-07-01 §3;
`cp-auth-door-probe-2026-07-01.md` Q3; `tvs-datastore-binding-value.md`
TL;DR mechanism 3). That conclusion was a **log-level artifact**: every
stitch line is DEBUG, and the recon window fell on cycles where the Oracle
DB target was unreachable (`No route to host … 1521`), so the whole DB
collection — and with it the relationship phase — was skipped and nothing
was logged. Corrections logged at the end.

---

## Static path (9.1) — the complete code path to the edge

### 1. The config: two name-keyed external relationships on the instance

`oracledatabase_adapter_3.jar` →
`com/bluemedora/vrealize/adapter/oracle/database/ManagementPackConfigurationHolder$managementPackDefinition$8.class`,
method `invoke(ResourceDefinition)` (javap -c). It builds a 2-element
`ExternalRelationship[]` and calls `ResourceDefinition.withExternalRelationships([...])`.
Both elements are `com.bluemedora.vrops.compiler.execution.configuration.relationships.ExternalRelationshipByMetric`,
both sourced from the metric `OracleDatabase$Resource$Instance$Metric$HostName.INSTANCE`,
both `ExternalRelationshipType.CHILD_OF_EXTERNAL` (the Oracle instance is
the child; the VM is the parent):

- **Edge #1 (property):** `new RelationshipInfo("VMWARE", "VirtualMachine", "config|name", RelationshipInfo$KEY_TYPE.PROPERTY)` then `.withTagResourceParentOfExternalKind("Oracle Database Instances on VMware", "oracle_database_vms_tag", "Oracle Database Virtual Machines Tag")` (bytecode offsets 28–57).
- **Edge #2 (name):** `new RelationshipInfo("VMWARE", "VirtualMachine", null, RelationshipInfo$KEY_TYPE.RESOURCE_NAME)`, `CHILD_OF_EXTERNAL` (offsets 77–96).

So the descriptor's `oracle_database_vms_tag` and `VirtualMachine_parent`
placeholders (`describe.xml`, quoted in `tvs-declarative-stitching.md`) are
**reporting slots**; the *binding rule* lives here in bytecode:
`config|name` (PROPERTY) and resource-name (RESOURCE_NAME), valued from
`HostName`.

### 2. The bridge to aria-ops-core

`library-9.2.0.jar` →
`…relationships.ExternalRelationship$Companion.addToExternalRelationshipCollection(ExternalRelationship, String, ExternalRelationshipCollection)`
(javap -c) converts each bluemedora config into aria-ops-core:
`externalRelationshipCollection.withLocal(new RelationshipInfo(metricKey, getKeyType())).apply(valueManipulationFunction).childOfExternal(externalRelationshipInfo, multi)`.

### 3. The collector invokes it every cycle

`library-9.2.0.jar` →
`com.bluemedora.vrops.compiler.execution.AdapterLiveCollector.getCurrentMetrics(...)`
(javap -c) calls
`IDataProviderConfiguration.getExternalRelationshipCollection().createRelationships(AdapterLoggerFactory, suiteAPIClient, resourceCollection)`
(constant-pool method #712), passing the collector's `suiteAPIClient` field
(#34). Same call site is reused for `CustomResourceConfiguration`.

### 4. createRelationships = a Suite API read (aria-ops-core-7.1.1)

`aria-ops-core-7.1.1.jar` →
`…relationships.ExternalRelationshipCollection.createRelationships` (javap -c):
DEBUG log strings `"Coalescing Relationships"`, `"Creating ResourceDtoClient"`,
`"Starting Relationship Processing"`, INFO `"Processing relationships for
local resource kind"`, DEBUG `": Attempting to find parent ("` /
`": Attempting to find child ("`, `"   ==> Skipping computation for"`,
`"Finished Relationship Processing in"`. Flow per element:
`ResourceDtoClient.shouldAttemptRelationships(RelationshipInfo)` →
`RelationshipInfo.getRawValue(Resource)` → `transform(...)` →
`RelationshipInfo.addParent/addChild(ResourceDtoClient, Resource, values)`.

`shouldAttemptRelationships` (javap -c) = `getResourceCount(RelationshipInfo) > 0`,
and `getResourceCount` itself issues `new ResourceQuery()` +
`getResourcesFromSuiteApi(ResourceQuery)` — **a Suite API read** just to
gate. `ResourceDtoClient.getResources` consults a `ResourceDtoCache`
(`indexIsComplete`), logging `"Calling getResourcesFromSuiteApi on"`
(cache miss) vs `"Got cached values on"`. `getResourcesFromSuiteApi`
branches on `KEY_TYPE`: `RESOURCE_NAME` → `ResourceQuery.setRegex`;
`PROPERTY` → property name/value; `IDENTIFIER` → fetch-all + in-memory
filter (matches `tvs-datastore-binding-value.md`).

### 5. The credential the SuiteAPIClient uses

`aria-ops-core-7.1.1.jar` → `…extensions.suiteapi.SuiteAPIClient` wraps the
**real HTTP** `com.vmware.ops.api.client.Client` (fields/strings:
`UsernamePassword`, `AuthToken`, url literal `https://localhost/suite-api/`).
`…extensions.suiteapi.SuiteAPICredential.getSuiteApiAdapterCredential(AdapterConfig)`
(javap -c): if `AdapterConfig.getAdapterCredentials().getUserName()` is
present → `new SuiteAPICredential(userName, password)`; **else** →
`getSuiteAPIMaintenanceUserCredential()`, which `loadProperties(Constants.MAINTENANCE_CREDENTIALS_PATH)`.
`Constants` string constants confirm `MAINTENANCE_CREDENTIALS_PATH` =
`…/user/conf/maintenanceuser.properties` (keys `username`/`password`/`encrypted`,
`Crypt.getDefaultCrypt().decrypt`). **The live capture (below) shows the
first branch is taken — username = the adapter-instance UUID — so the
maintenance fallback is NOT used by Oracle.**

### 6. Contrast: 7.0

`OracleDatabase-7.0` `adapters.zip → oracledb_adapter3.jar` contains the
**same** stitch-core (`ExternalRelationshipCollection`,
`extensions/suiteapi/SuiteAPIClient` present) **plus** the older helper
`addVmParentByNames` (constant present in the jar). Same family: a Suite
API read; 7.0 uses the imperative `addVmParentByNames/Ip` helper, 9.1 uses
the declarative `ExternalRelationshipByMetric` config. Both name/IP-keyed.

---

## Live Suite API shape (prod primary 172.27.8.41, read-only)

- `oracle_database_vms_tag "Oracle Database Instances on VMware"`
  (`ccf3ab75-2aa2-4ce6-9d65-18a49f708ed0`): **`resourceIdentifiers: []`
  (EMPTY)** — its whole identity is its name; it holds a relationship to
  `VMWARE::VirtualMachine "oracledemo"`. It is the
  `withTagResourceParentOfExternalKind` grouping container, **not** the
  binder.
- Instance `"FREE"` (`34a66adc-e0e3-4211-b704-18e471db67f8`): unique
  identifiers `adapter_instance_id=664864`, `instance_id=1`. Its
  **PARENTS** include `VMWARE::VirtualMachine oracledemo` (and
  `oracle_database_oracle_database_database FREEPDB1`); it has **no VMWARE
  children** — i.e. the VM is the parent (consistent with
  `CHILD_OF_EXTERNAL`).
- VM `oracledemo` (`3fd10bba-41d8-4b4b-bafb-2c050544096a`): property
  `config|name = 'oracledemo'`, `summary|guest|hostName = 'oracledemo'`;
  resourceKey identifiers `VMEntityName='oracledemo'` (`isPartOfUniqueness=false`),
  **unique** `VMEntityObjectID='vm-16043'` + `VMEntityVCID='4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e'`.
  The name is the search key; the resolved DTO carries the unique identity.

---

## Live CP DEBUG capture — the stitch in the act

Prod CP `172.27.8.51`, collector PID 114336, instance 664864, cycle
`2026-07-02T14:35:58–14:36:28Z`, adapter log
`…/user/log/adapters/OracleDatabaseAdapter/OracleDatabaseAdapter_664864.log`.
Verbatim (logger class + message):

**Token — acquired as the adapter-instance principal, succeeds on the CP:**
```
SuiteAPIClient.<init> - Acquiring Suite API token for user "48fb5d76-80f0-4062-b32b-c11ff824ee2b"
SuiteAPIClient.getClientConfigBuilder - FIPS mode detected. Using cluster …
SuiteAPIClient.<init> - Suite API token acquired; creating token-authenticated client
SuiteAPIClient.<init> - Token-authentication client created
```
(`48fb5d76-…` = the OracleDBAdapter **instance** id per `recon_log.md`
2026-07-01. NOT the CP node's `cloudproxy_9017a996-…` maintenance
principal.)

**Relationship phase runs every DB-successful cycle:**
```
ExternalRelationshipCollection.createRelationships - Coalescing Relationships
ExternalRelationshipCollection.createRelationships - Creating ResourceDtoClient
ExternalRelationshipCollection.createRelationships - Starting Relationship Processing
ExternalRelationshipCollection.createRelationships - Processing relationships for local resource kind oracl…   [INFO]
ExternalRelationshipCollection.createRelationships -    Processing resource FREE
```

**Edge #1 — RESOURCE_NAME (name regex) Suite API read → additive edge:**
```
createRelationships -    ==> FREE: Attempting to find parent (VMWARE::[VirtualMachine](null)) using General|host_name == [oracledemo]
transform            -                  ==> Transformed values: [oracledemo]
DtoClient.getResources            - Calling getResourcesFromSuiteApi on VMWARE::[VirtualMachine …
DtoClient.getResourcesFromSuiteApi - Querying for RESOURCE_NAME with regex: (?i)^\Qoracledemo\E$
DtoClient.addRelationship         - Creating relationship from parent oracledemo (VirtualMachine) to child FREE (oracle_database_oracle_database_instance)
```

**Edge #2 — config|name PROPERTY, fetch-candidates-then-filter:**
```
createRelationships - ==> FREE: Attempting to find parent (VMWARE::[VirtualMachine](config|name)) using General|host_name == [oracledemo]
DtoClient.getResourcesFromSuiteApi - ==> Found 3 potential matches
DtoClient.getResourcesFromSuiteApi -     ==> Testing config|name for value oracledemo: oracledemo2
DtoClient.getResourcesFromSuiteApi -     ==> Testing config|name for value oracledemo: oracledemo
DtoClient.getResourcesFromSuiteApi -     ==> Testing config|name for value oracledemo: oracledemo3
DtoClient.addRelationship - Creating relationship from parent oracledemo (VirtualMachine) to child FREE (oracle_database_oracle_database_instance)
```
Note: it correctly disambiguates `oracledemo` from `oracledemo2`/
`oracledemo3` by **exact** `config|name` equality. Total:
```
createRelationships - Finished processing resource FREE in 28.366s
createRelationships - Finished Relationship Processing in 28.367s
```

**Why recon saw zero:** in the immediately prior cycles (14:25, 14:30) the
DEBUG lines present were only `SuiteAPIClient` token-acquire and
`DtoClient.getDto - Could not get dto resource for <{resName=SELECT …,
resKind=oracle_database_oracle_database_query, …}>` (own query resources).
No `ExternalRelationshipCollection` line at all until 14:35, because the
relationship phase runs **only when DB collection succeeds** — and Oracle's
target is intermittently unreachable (`No route to host … 1521` in the
current log). recon 2026-07-01 grepped at INFO (all stitch lines are DEBUG)
during such a window → 0 hits. The "0 suite-api calls" was an artifact,
not a fact.

---

## Mechanism, evidenced

> Oracle's VM edge is created by **X** = `ExternalRelationshipCollection.createRelationships`
> (aria-ops-core-7.1.1) running an additive `DtoClient.addRelationship`
> every DB-successful collection cycle, carrying **Y** = *no self-built
> key* — it resolves the VM by a Suite API search (`RESOURCE_NAME` regex
> `^oracledemo$` and property `config|name==oracledemo`) and edges to the
> resolved DTO's true identity (`vm-16043`/VCID), built from **Z** = the
> Oracle instance's `General|host_name`/`HostName` metric (`oracledemo`),
> working on a CP because **W** = the `SuiteAPIClient` token is acquired as
> the adapter-instance principal `48fb5d76-…` (which carries resource-read
> RBAC), not the empty-roles `cloudproxy_<uuid>` maintenance identity.

**INFERENCE (labeled):** that `48fb5d76-…` is a *platform-injected
per-instance service account provisioned with RBAC* is an inference from
(a) the live username = adapter-instance UUID, (b) the acquire+query
succeeding on the CP, and (c) the static first-branch of
`getSuiteApiAdapterCredential` (`AdapterConfig.getAdapterCredentials()`).
The wire facts (username, success) are quoted; the *characterization* is
inference. I did not read the injected credential's role bindings.

---

## Transfer analysis — can Synology replicate X for `VMWARE::Datastore`?

**The stitch mechanism X transfers directly** — it is literally the
storage-pak idiom (`tvs-cross-mp-stitching.md`,
`tvs-datastore-binding-value.md`). Two independent conclusions:

1. **The CP-403 barrier is an IDENTITY bug, not a transport/mechanism
   bug — and Oracle proves the fix live.** A Suite-API-read stitch runs
   and succeeds on **this exact CP** when the token is the aria-ops-core
   default per-instance principal. Our `SynologyStitcher` fails only
   because it hand-reads `maintenanceuser.properties` (`cloudproxy_<uuid>`).
   **INFERENCE:** a Synology adapter that resolves foreign resources
   through the aria-ops-core `SuiteAPIClient` (i.e. lets the platform
   supply `AdapterConfig.getAdapterCredentials()`), rather than reading
   `maintenanceuser.properties` itself, should get the same CP-working
   identity Oracle gets. Not directly tested for a Datastore query; tested
   for a VirtualMachine query on the CP (this report). This refines
   `cp-auth-door-probe` Q2's "use `automationAdmin`" — the *observed*
   working identity is the per-instance adapter principal, obtained by
   using the SDK's own credential path, not by manually selecting a
   properties file.

2. **The NAME-keyed match does NOT transfer; the PATH/IDENTIFIER match
   does.** Oracle's simplest working edge is `RESOURCE_NAME` (regex on the
   VM's friendly name) because a DB **knows its own hostname**, which
   equals the VM name. A NAS does **not** know the datastore's vCenter
   friendly name — so Synology **cannot** use Oracle's `RESOURCE_NAME`
   path. What a NAS *does* know (NAA/serial, NFS export path, its own IP)
   maps to the datastore's **`DataStrorePath` identifier**
   (`VMFS:|naa.<id>|` for block, `<ip>/<export>` for NFS), resolved via
   `KEY_TYPE.IDENTIFIER` — the fetch-all-`VMWARE::Datastore`-then-filter
   branch of `ResourceDtoClient.getResourcesFromSuiteApi`, which is
   **structurally identical** to the `config|name` PROPERTY branch we
   watched Oracle run ("Found 3 potential matches → Testing … → accepting").
   So Synology's transferable recipe = **X with `KEY_TYPE.IDENTIFIER` on
   `DataStrorePath`** (or a datastore property, à la Nimble's
   `|serial_number`), value CP-derived from the exported NAA/export path.

**Net:** the datastore stitch is achievable with the *same* creator X and
the *same* identity W that Oracle uses live on the CP — but keyed on
`DataStrorePath` (path/NAA), not on a name Synology cannot know. This is a
Suite API READ, and it is CP-safe **only** with the per-instance identity
(the whole point). It is **not** the "lookup-free property-correlation"
mechanism prior notes hoped for — that mechanism, as applied to Oracle, does
not exist; Oracle reads.

---

## Corrections logged against prior docs

1. **`recon_log.md` 2026-07-01 §3 / `cp-auth-door-probe-2026-07-01.md` Q3
   — REFUTED.** "OracleDBAdapter never calls the suite-api door … its VM
   stitch is a describe.xml ResourcePath traversal resolved by the
   platform, needs no token." Live DEBUG shows Oracle **acquires a token
   every cycle** (`SuiteAPIClient.<init>`) and **runs
   `getResourcesFromSuiteApi` against VMWARE::VirtualMachine** to create
   the edge (`DtoClient.addRelationship`). The describe.xml
   `VMWARE::VirtualMachine::~child` ResourcePath is UI/navigation +
   reporting placeholder; it is **not** the binder.
2. **`tvs-datastore-binding-value.md` TL;DR + Q2 mechanism 3 — REFUTED for
   Oracle.** Oracle's edge is **not** `relationships|<Kind>_parent`
   property correlation and is **not** CP-immune-because-lookup-free; it is
   a Suite API read that is CP-*safe-because-right-identity*. The
   "proven CP-immune property-correlation, name-valued" framing should be
   struck; the correct statement is "proven CP-working Suite-API-read
   stitch, name-keyed, under the per-instance identity."
3. **`tvs-declarative-stitching.md` follow-ups #1/#2 — ANSWERED.** The
   layer that creates the live 9.x edge is the **jar's aria-ops-core
   Suite-API read**, not the descriptor traversal and not platform
   auto-correlation of a reported property. Determined for Oracle; by the
   shared code path (`ExternalRelationshipCollection`) the same holds for
   Pure/Nimble/etc.
4. **`tvs-cross-mp-stitching.md` "TVS corpus does NOT demonstrate a CP-safe
   creds-free foreign stitch" — REFINED.** It demonstrates one now: Oracle,
   live on CP 172.27.8.51, via the per-instance adapter identity. The
   corpus's CP-403 stories were about adapters/our-code hand-reading
   `maintenanceuser.properties`, not about the aria-ops-core `SuiteAPIClient`
   default path.

---

## Clean-up

- **Live write (the one permitted):** added a scoped
  `logger.tvsstitchprobe.name = com.vmware.tvs.vrealize.adapter.core.extensions`
  / `.level = DEBUG` block to
  `/usr/lib/vmware-vcops/user/conf/collector/log4j2.properties` on the CP,
  then removed it. **Post-restore md5 `a8f144cea8a276a1b74f060f41b3d58b`,
  size 8575 — byte-identical to the pre-change snapshot** (saved at
  `scratchpad/log4j2.properties.orig`). 0 `com.vmware.tvs` loggers, 0
  probe markers remain. `monitorInterval = 60` reloads the restored file,
  returning the level to `rootLogger WARN`.
- **No resources created/modified/deleted** on either node. Suite API
  calls were read-only (`token/acquire`, GET resources/relationships/
  properties). Scratchpad extraction only; `references/` untouched.
- **Clean-up verified: yes.**

## Flags / limits

- No decompiler; `javap -c` bytecode + `strings` + live logs only. No
  obfuscation — class/method names intact.
- The per-instance credential's role bindings were not read (secret);
  RBAC sufficiency is inferred from the successful acquire + query.
- The Datastore-`DataStrorePath` IDENTIFIER path is proven by static
  bytecode (`getResourcesFromSuiteApi` KEY_TYPE branch) + Oracle's live
  PROPERTY-branch behavior, **not** live-tested for an actual datastore
  query. That is the recommended next experiment before Synology commits.
