# TVS datastore-stitch: the BINDING VALUE (bytecode-verified)

**Question (one sentence):** What value do the TVS datastore-stitching
paks write/match to bind their volume/LUN to a `VMWARE::Datastore`, and
could an NAA id (or path/url) serve as that value instead of the
datastore's friendly name?

**Method:** `unzip` of each pak → `adapters.zip` → adapter jar + DP jar
+ `aria-ops-core-7.1.0.jar`; `javap -p -c` bytecode disassembly of the
relationship engine and each vendor's stitch config. Extraction to
scratchpad only; `references/` untouched (git clean, verified); no live
calls (the live Oracle evidence is already captured in
`context/investigations/recon_log.md` / prior maps). Builds on
`tvs-cross-mp-stitching.md` (jar layer) and `tvs-declarative-stitching.md`
(descriptor layer) — this file adds the **value layer**: the exact string
constructed and the exact foreign attribute it is matched against.

**Evidentiary discipline (user-mandated):** every mechanical claim quotes
a named class+method (and constant-pool string / bytecode op) in a named
pak. Anything else is tagged **INFERENCE**.

---

## TL;DR

- **Binding value the vendors write = a datastore PATH string derived
  from storage-side facts, NOT the datastore's friendly name.** For block
  volumes it is `VMFS:|naa.<id>|` built from the volume/LUN NAA/WWN/UID;
  for VVOLs `VVOL:<pod-uuid-parts>`; for NFS `<nas-ip>/<export-path>`.
  One pak (Nimble) instead matches a datastore **property**
  (`|serial_number`) with the volume serial. **No storage pak in the set
  binds the datastore by `VMEntityName` (friendly name).**
- **Platform matches on = the `VMWARE::Datastore` identifier
  `DataStrorePath`** (misspelled in the source, `identType="2"`,
  non-unique) for Pure/FAS-AFF/Isilon/VNX-Block/E-Series, or a datastore
  **property** for Nimble. The aria-ops-core engine offers exactly two
  built-in datastore matchers: `VMWARE_DATASTORE_BY_NAME` (identifier
  `VMEntityName`) and `VMWARE_DATASTORE_BY_PATH` (identifier
  `DataStrorePath`) — **only BY_PATH is used by the corpus.**
- **The resolution is always a Suite API READ** (`SuiteAPIClient` →
  `ResourceQuery` / `getResources`). The NAA-derived value is only a
  *search key*; the platform returns the full datastore DTO (carrying its
  true unique identity) and the edge is made to that. **There is no
  lookup-free datastore binder in any of these jars.**
- **NAA-only binding WITHOUT a Suite API read = not viable via any
  vendor-proven path, UNDETERMINED via the platform property-correlation
  path.** The value is fully CP-derivable, but every vendor mechanism that
  turns it into an edge is a Suite API read (CP-403 off-primary), and the
  one *proven* CP-immune mechanism (Oracle's `relationships|<Kind>_parent`
  property correlation, recon 2026-07-02) was **name**-valued, not
  path/NAA-valued. Whether a path-valued `Datastore_parent` correlates
  CP-side is an untested experiment.

---

## The engine: what a datastore matcher is (aria-ops-core-7.1.0)

`com.vmware.tvs.vrealize.adapter.core.extensions.relationships.RelationshipConstants`
static initializer (javap -c) defines the only two datastore matchers,
each a `RelationshipInfo(adapterKind, resourceKind, key, KEY_TYPE)`:

```
VMWARE_DATASTORE_BY_NAME = RelationshipInfo("VMWARE","Datastore","VMEntityName",   KEY_TYPE.IDENTIFIER)
VMWARE_DATASTORE_BY_PATH = RelationshipInfo("VMWARE","Datastore","DataStrorePath", KEY_TYPE.IDENTIFIER)
```

`RelationshipInfo$KEY_TYPE` enum = `{METRIC, PROPERTY, RESOURCE_NAME,
IDENTIFIER}`. Both datastore constants use **IDENTIFIER** — i.e. the value
is matched against a datastore *resourceIdentifier*, not an arbitrary
property or the resourceName.

`ResourceDtoClient.getResourcesFromSuiteApi(RelationshipInfo, String value)`
(javap -c) branches on `KEY_TYPE`:

| KEY_TYPE | how the foreign resource is found (Suite API) |
|---|---|
| `PROPERTY` | `ResourceQuery.setPropertyName(key)` + `setPropertyValue(value)` |
| `METRIC` | `ResourceQuery.setStatKey(key)` + bounds |
| `RESOURCE_NAME` | `ResourceQuery.setRegex("(?i)^" + Pattern.quote(value) + "$")` |
| `IDENTIFIER` | query all of `adapterKind`+`resourceKind`, then in-memory filter: `RelationshipUtils.getIdentifierValue(convertedResource, key).equalsIgnoreCase(value)` |

**All four branches call `getResourcesFromSuiteApi(ResourceQuery)` = a
Suite API read.** For `IDENTIFIER` (the datastore case) it fetches every
`VMWARE::Datastore` and filters by the `DataStrorePath` (or `VMEntityName`)
identifier equalling the search value. `getResources(...)` first consults
a local `ResourceDtoCache`; on a miss (`indexIsComplete==false`) it hits
Suite API. Cache, not lookup-free.

Value flow (`ExternalRelationshipCollection.createRelationships`, javap -c):
```
localInfo.getRawValue(volumeResource)            // pull volume's own value (NAA/serial/…)
  → transform(def, rawValue)                     // valueTransformations: NAA→VMFS path, etc.
  → externalInfo.addParent/addChild/addMultiple*(client, volumeResource, transformedValues)
      → ResourceDtoClient.getResources(externalInfo, value)   // Suite API resolve of the datastore
      → ResourceDtoClient.addRelationship(volumeResource, datastoreDto)  // additive edge
```
So the **local** RelationshipInfo picks the value off the volume; the
**external** RelationshipInfo (`VMWARE_DATASTORE_BY_PATH`) says "match it
against the datastore's `DataStrorePath` identifier."

---

## Per-pak binding-value table (bytecode-quoted)

| Pak (build) | binding value written | where the value comes from | matched against (foreign attr) | evidence |
|---|---|---|---|---|
| PureStorage FlashArray 4.3.0 | VMFS: `"VMFS:|" + naaId + '|'`  ·  VVOL: `"VVOL:" + <podId split on '-'>` | `Volume.Metric.NaaId` / `Volume.Metric.PodId` (array-reported, target data) | `VMWARE_DATASTORE_BY_PATH` → Datastore identifier `DataStrorePath` | `VolumeConfigurationKt$getVolumeConfiguration$1` (two `ExternalRelationshipByMetric`, both `VMWARE_DATASTORE_BY_PATH`, `CHILD_OF_EXTERNAL`); transforms `$1$1` (`ldc "VMFS:|"`, `bipush 124`='\|') and `$1$2` (`ldc "VVOL:"`) |
| NetApp FAS-AFF 4.3.0 | block: `VMFS:|naa.600a0980…` (from LUN WWN)  ·  NFS: full-path form | LUN WWN/serial · NFS path (target data) | `VMWARE_DATASTORE_BY_PATH` → `DataStrorePath` | `ManagementPackConfigurationHolder` refs `VMWARE_DATASTORE_BY_PATH`; inner classes `…$datastoreRelationshipByWwn$1` (embedded literal `VMFS:|naa.600a0980`) and `…$datastoreRelationshipByFullPath$1` |
| Dell EMC Isilon 4.3.2 (NFS) | candidate paths `<clusterIP>[/]<exportPath>` | own cluster `Details\|external_ips` + NFS `Details\|paths` (self-collected) | Datastore identifier `DataStrorePath` (`DATASTORE_PATH="DataStrorePath"`) | `custom.CustomExternalRelationshipLogic.addDatastoreToNfs` / `getPossiblePaths` / `getPathToDatastoreMap`; log strings "Creating relationship between nfs [ %s ] and datastores [ %s ]" |
| Dell EMC VNX Block 4.1.0 | VMFS path from `parseLunUID(configuration\|lun_uid)` (LUN WWN/UID) | LUN UID / `logical_unit::wwn` (target data) | Datastore identifier `DataStrorePath` (`DATASTORE_PATH` const) | `EMCVNXBlockLiveCollector.addLunToDatastores` / `parseLunUID`; reads `Datastore.getIdentifierValue("DataStrorePath")` |
| NetApp E-Series 6.1.0 | path/serial from LUN (`lun::…`) | LUN serial/UID (target data) | Datastore identifier `DataStrorePath` (present in `NetAppESeriesLiveCollector`, `addGeneralParentRelationship`) | `NetAppESeriesLiveCollector` refs `DataStrorePath` + `addGeneralParentRelationship`; exact transform not decompiled — **INFERENCE** it mirrors VNX Block |
| HPE Nimble 5.2.0 | volume serial (`volume::serial_number`) | Nimble volume serial (target data) | Datastore **property** `\|serial_number` (backing SCSI device serial), NOT DataStrorePath, NOT name | `NimbleStorageLiveCollector`: `ldc "volume::serial_number"`, `ldc "|serial_number"`, `SuiteAPIClient.getResources(...)` over kind `Datastore`, `addGeneralParentRelationship`; logs "Made relationship between volume < > and datastore < >" |

**Concrete VMFS `DataStrorePath` value form (confirmed):**
`VMFS:|naa.<hexid>|` — Pure builds prefix `VMFS:|` + naa + `|` (bipush
124); FAS-AFF ships the literal `VMFS:|naa.600a0980` (600a0980 = NetApp's
NAA/IEEE OUI, i.e. the value is the LUN's own exported NAA rendered as the
VMFS datastore path).

**Uniformities:** (1) not one pak uses `VMWARE_DATASTORE_BY_NAME` — a
corpus-wide grep for `VMWARE_DATASTORE_BY_NAME` outside `aria-ops-core`
returns **0**. (2) Every value is derived from **storage/NAS-side facts**
the adapter already collects (NAA, WWN, LUN UID, volume serial, NFS
export path, NAS IP) — never the datastore's vCenter display name, never
an operator-supplied mapping. (3) Every path ends in a
`SuiteAPIClient.getResources` / `ResourceQuery` call — a Suite API read.

---

## Q2 — what the platform matcher accepts (spec + engine reconciliation)

`~/specs/mp-java-sdk/spec/07-relationships-cross-mp.md` describes **two**
binding mechanisms; they key differently:

1. **SDK self-constructed `ResourceKey` (Mode B push).** Spec/07 is
   emphatic: the foreign key MUST carry the datastore's
   *uniqueness-bearing* identifiers and only those — `(VMEntityObjectID,
   VMEntityVCID)`, both `identType="1"`. `VMEntityName` and
   `DataStrorePath` are `identType="2"` (NON-unique). A key built from a
   non-unique identifier is **un-bindable — the platform silently drops
   the edge** (spec/07 §"CRITICAL", confirmed on 9.0.2). So you cannot
   self-construct a datastore key from NAA/path/name.

2. **TVS aria-ops-core Suite-API-resolve (this corpus).** The vendor does
   **not** construct the key. It *searches* Suite API by a non-unique
   attribute (`DataStrorePath` identifier, or a property), gets back the
   full `ResourceDto` with the real unique identity, and makes the edge to
   that resolved resource. This is why matching on `DataStrorePath`
   (non-unique) is legal here but illegal in mechanism 1 — the search key
   need not be unique; the resolved resource carries the uniqueness. Cost:
   a Suite API read.

3. **Platform property-correlation (Oracle, live-proven CP-immune).**
   recon 2026-07-02: Oracle's instance reports the string property
   `relationships|VirtualMachine_parent = oracledemo` (the VM's **name**)
   and the platform creates the VM edge with **zero adapter API calls**.
   The describe.xml `Datastore_parent`/`VirtualMachine_parent`
   `isProperty="true"` placeholder + a `<TraversalSpecKind>` hop is the
   declarative half; the reported property value is the binder. **Proven
   for a VM matched by NAME. Not tested for a datastore, and not tested
   for a non-name (path/NAA) value.**

**On whether a non-name value can bind:** YES for mechanisms 1 and 2 in
the sense that the engine keys on `DataStrorePath` (a path, not a name) —
`VMWARE_DATASTORE_BY_PATH` is real and is what the whole corpus uses. But
mechanism 2 pays a Suite API read, and mechanism 1 can't use it at all
(non-unique). For mechanism 3 (the CP-immune one) there is **no evidence**
a path/NAA value binds — the only proof is name. Gap labeled.

---

## Q3 — NAA feasibility verdict (evidence order)

Target: a CP-resident Synology adapter that knows only NAS-side facts
(the NAA/serial it exported, its NFS export path, its own IP) and makes
**no Suite API read**.

**(a) NAA directly.** No pak binds a raw NAA. Pure/FAS-AFF wrap it as the
VMFS *path* `VMFS:|naa.<id>|` and match `DataStrorePath`. So the useful
form is the path, not the bare NAA. The Synology adapter *can* compute
`VMFS:|naa.<exported-naa>|` entirely CP-side (it knows the NAA it
presented). **Deriving the value: viable. Binding it without a read:** the
only binder that consumes `DataStrorePath` in evidence is the Suite-API
resolve (not CP-safe). Whether a reported `relationships|Datastore_parent
= VMFS:|naa…|` property auto-correlates CP-side (mechanism 3) is
**UNDETERMINED — untested**.

**(b) Datastore url/path.** The `VMWARE::Datastore` *does* expose the path
as the `DataStrorePath` identifier, and the platform matches it — that is
exactly `VMWARE_DATASTORE_BY_PATH`. For NFS the matchable form is
`<nas-ip>/<export>` (Isilon's `getPossiblePaths` builds precisely this
from its own IPs + export paths). A Synology NFS adapter knows both its IP
and its export path → can build the same candidate value CP-side. Again:
value derivable CP-side; the vendor binder is a Suite API read.

**(c) name-via-config.** No pak takes an operator-supplied datastore name.
The credential model across the corpus is a single target-system
credential, no vROps field, no datastore-mapping field (confirmed prior in
`tvs-cross-mp-stitching.md`). **No vendor precedent for an operator
datastore-name mapping.**

**Verdict:** NAA-only binding **without any Suite API read is not viable
through any vendor-proven path** (every one resolves via Suite API), and
**UNDETERMINED through the platform property-correlation path** (proven
only for a name value, mechanism 3). Self-constructing a datastore key
from NAA/path is **not viable** (non-unique → silently dropped, spec/07).
The value itself is trivially CP-derivable; the missing proof is a
zero-API binder that accepts a path/NAA value.

---

## Q4 — the "ask for the name" fallback

If mechanism 3 turns out to be name-only (i.e. a path value does not
correlate), Synology needs the datastore NAME. Evidence on how names are
obtained:

- **No pak obtains a datastore name from config.** Zero
  `VMWARE_DATASTORE_BY_NAME` usage; no datastore-name config field in any
  credential/connection parameter set inspected.
- **No pak obtains a datastore name from the target array either** — the
  array doesn't know the vCenter datastore name; that is precisely why
  they match on path/serial derived from what the array *does* know.

So there is **no vendor precedent** for an operator-supplied
datastore-name mapping. If Synology needs a name and wants to stay
CP-immune, it would be introducing a pattern the TVS corpus never used
(an adapter config field mapping export→datastore-name). The alternative —
discovering the name via a Suite API read — reintroduces the CP-403.

---

## Recommended Synology binding strategy (per evidence)

Ranked by CP-safety, then by evidence strength:

1. **Experiment first — path-valued property correlation (potential
   CP-immune win, UNDETERMINED).** Mirror Oracle's proven mechanism but
   with a path value: have the Synology volume report the property
   `relationships|Datastore_parent` valued with the CP-derivable path —
   `VMFS:|naa.<exported-naa>|` for block, `<synology-ip>/<export>` for NFS
   — and declare the describe.xml `Datastore_parent` `isProperty`
   placeholder + a `synology_volume::child||VMWARE::Datastore::~child`
   traversal (clone Pure/Nimble, per `tvs-declarative-stitching.md`).
   Then check on a **Cloud Proxy** whether the edge appears with zero
   Suite API calls (as Oracle's name-based edge does). This is the only
   path that is both CP-immune *and* name-free — but it hinges on the
   platform correlating a path value, which is unproven. **Run this before
   committing to anything heavier.**

2. **Vendor-proven, name-free, but NOT CP-safe: copy the TVS idiom
   verbatim.** `SuiteAPIClient.getResources` over `VMWARE::Datastore`,
   match by `DataStrorePath = VMFS:|naa…|` (block) or `<ip>/<export>`
   (NFS), then additive `addParent`/`addGeneralParentRelationship`. This
   is exactly Pure/FAS-AFF/Isilon/VNX. Works **creds-free on the
   primary/data node**; **403s on a Cloud Proxy** (empty-roles maintenance
   identity — see `tvs-cross-mp-stitching.md`). Use only if Synology
   collection runs on-appliance.

3. **CP-safe but heavier: vCenter-cred path (no TVS precedent).** Add a
   vCenter credential, read the datastore's backing-device NAA +
   `(VMEntityObjectID, VMEntityVCID)` directly, and push an SDK key with
   the **true unique identifiers** (spec/07 mechanism 1). Bypasses Suite
   API entirely, so CP-safe — but it is the vSAN idiom, not the storage-MP
   idiom, and requires a credential field the storage corpus never has.

**Do NOT** try to self-construct a datastore `ResourceKey` from the NAA,
path, or name — all three are `identType="2"` non-unique; the platform
silently drops the edge (spec/07, live-confirmed 9.0.2). The NAA is a
*search key* or a *correlation property value*, never a key identifier.

---

## Corrections logged against prior maps

- `tvs-cross-mp-stitching.md` per-pak matrix says storage "identity
  matched = Volume NAA / serial → Datastore" via "SuiteAPI property
  search." **Refined:** the modern paks (Pure, FAS-AFF, Isilon, VNX
  Block) match the datastore's **`DataStrorePath` IDENTIFIER** with an
  NAA/WWN/UID-derived **VMFS path string** (`VMFS:|naa…|`) or NFS
  `<ip>/<export>` — an `IDENTIFIER`-type resolve (fetch-all-then-filter),
  not a `PROPERTY`-name search. Only **Nimble** uses a genuine property
  search (datastore `|serial_number`). None uses the datastore name.
- `tvs-declarative-stitching.md` open follow-up #3 ("what value must the
  volume's `Datastore_parent` property carry") — **answered for the vendor
  binder:** the value is the VMFS path `VMFS:|naa.<id>|` (block) or
  `<ip>/<export>` (NFS), matched against `DataStrorePath`. The
  descriptor's `Datastore_parent` `isProperty` placeholder is the
  reporting slot; whether the *platform* (not the jar) will correlate that
  reported path value CP-side is the untested experiment in strategy #1.

## Flags / limits

- No decompiler; `javap -c` bytecode + constant-pool `strings` only. No
  obfuscation — class/method names intact throughout.
- E-Series transform not fully decompiled; its `DataStrorePath` +
  `addGeneralParentRelationship` refs make it structurally identical to
  VNX Block, but the exact path-format lambda was not disassembled
  (**INFERENCE**).
- The exact vCenter-side string stored in a datastore's `DataStrorePath`
  identifier is taken to be `VMFS:|naa.<id>|` from the vendor transforms
  that target it (Pure builds it; FAS-AFF ships the literal). Not
  cross-checked against a live datastore's identifier dump — a 1-minute
  recon (`GET /suite-api/api/resources?resourceKind=Datastore` →
  resourceIdentifiers) would confirm the exact stored form and is the
  recommended pre-work for strategy #1.

---
**CORRECTION (2026-07-02):** any residual implication that a declarative /
property-driven binder exists is disproven: the platform has NO property→edge
code path, TraversalSpecKind never creates edges, and edge creation requires
uniqueness-identifier ResourceKey resolution
(`context/investigations/platform-edge-engine-2026-07-02.md`). The CP-viable
identity for the vendor-style Suite API read is the platform-injected
per-instance credential (`per-instance-suiteapi-credential-contract.md`),
proven live by synology build 26 (DEF-006 closing evidence).
