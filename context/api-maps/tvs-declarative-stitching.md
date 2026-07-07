# TVS declarative (descriptor-layer) cross-MP stitching

**Question (one sentence):** Do the TVS paks declare their cross-MP
stitch to VMWARE-owned resources (VirtualMachine / Datastore) in the
**descriptor layer** (describe.xml / `.sdm` / content), and if so, what
element/attribute performs the match — and does that give us a
descriptor-declared, Cloud-Proxy-immune way to stitch Synology volumes
to `VMWARE::Datastore`?

**Method:** static `unzip` of pak → `adapters.zip` → `conf/describe.xml`
+ `conf/scripts/*.sdm` for **every** pak in `reference/references/tvs/` (48 paks).
Extraction to scratchpad only. No live instance touched, nothing in
`reference/references/` modified. Companion to `context/api-maps/tvs-cross-mp-stitching.md`
(which read the **jars**); this file reads the **declarative layer** that
prior RE under-examined. Grammar cross-checked against
`~/specs/07-relationships-cross-mp.md`, `~/specs/02a-describe-xsd-canonical.md`,
and `context/mpb/mpb_pak_structural_reference.md`.

**Evidentiary discipline (user-mandated):** every mechanical claim below
is a verbatim quote from a named file inside a named pak. Anything not so
backed is tagged **INFERENCE**.

---

## TL;DR

1. **Oracle's declarative VM stitch is a `<TraversalSpecKind>` /
   `<ResourcePath>` in `describe.xml` whose last hop is
   `VMWARE::VirtualMachine::~child`, plus an `isProperty="true"`
   placeholder attribute `VirtualMachine_parent` in a `relationships`
   ResourceGroup.** In 7.0 it additionally ships a `.sdm` that *groups*
   an already-present VM parent. **No descriptor artifact contains a
   field-level match predicate** — grep for match / geneology /
   matcher / identifierType / eventMatchers on the describe.xml = **0
   hits**. The descriptor declares the relationship **shape**, never the
   identity **rule**.

2. **The storage paks carry the SAME declarative mechanism, pointed at
   `VMWARE::Datastore`.** This **corrects** the framing in
   `tvs-cross-mp-stitching.md` that implied storage stitch was
   runtime-SuiteAPI-only. Every storage pak (Pure, Isilon, VNX Block,
   E-Series, Nimble, FAS-AFF, plus VMAX / XtremIO / 3PAR / HCI-SolidFire /
   Nutanix / Unity) declares a `<ResourcePath>` ending
   `…volume::child||VMWARE::Datastore::~child` (often
   `||VMWARE::VirtualMachine::~child` after it), a `Datastore_parent`
   relationship-property placeholder, and — for Pure and FAS-AFF —
   `<TraversalSpecExtensionKind>` blocks that extend VMWARE's own
   `vSphere Storage` / `vSphere Hosts and Clusters` traversals down into
   the storage volume. **The declarative Datastore stitch is real and
   ubiquitous; nobody "hasn't done it for datastore identity" — they all
   have.**

3. **The match field is nowhere in any descriptor** for either VM or
   Datastore. The `<ResourcePath>` grammar (per spec/07 + observed
   corpus) is `ADAPTER_KIND::ResourceKind[::child|::~child][/mod]`
   chained by `||` — there is **no attribute for "match on property X"**.
   Identity binding happens outside the descriptor (jar / platform
   correlation), so the descriptor **cannot** tell us *which* field
   (name / IP / NAA / DataStorePath) is matched.

4. **Synology answer:** the observed grammar treats `VMWARE::Datastore`
   **identically** to `VMWARE::VirtualMachine` — a foreign kind named as
   an opaque `||`-hop in a `<ResourcePath>`. A Synology adapter can
   therefore declare `…synology_volume::child||VMWARE::Datastore::~child`
   **verbatim** the way Pure/Nimble/E-Series do. **But the grammar has no
   element to declare matching "on `DataStorePath` / NAA / serial" — no
   pak declares its match field either.** Whether that declaration yields
   a CP-immune edge depends on the out-of-descriptor edge creator, which
   for Oracle's structurally-identical construct is live-proven CP-immune
   (recon 2026-07-01). See final section for the strict yes/no.

---

## Q1 — Oracle's declarative stitch, exactly

### 9.1.0 (`OracleDatabase-9.1.0_b20240520.165914.pak`)

`adapters.zip → oracledatabase_adapter_3/conf/describe.xml`. There are
**no `.sdm` files** in this pak (`find … -iname '*.sdm'` = 0). Three
descriptor facts, verbatim:

**(a) The traversal path referencing the foreign VM** — line 1624,
inside `<TraversalSpecKind name="Oracle Database" …>`:

```xml
<ResourcePath path="OracleDBAdapter::oracle_database_traversal_tag||OracleDBAdapter::oracle_database_oracle_database_database::child||OracleDBAdapter::oracle_database_oracle_database_instance::child||VMWARE::VirtualMachine::~child"></ResourcePath>
```

The foreign hop is `VMWARE::VirtualMachine::~child` — `~child` = inverse
(child→parent) per spec/07 `<ResourcePath>` grammar. This is the exact
element the prod probe attributed the stitch to.

**(b) The relationship-property placeholder** — line 549, inside
`<ResourceKind key="oracle_database_oracle_database_instance">`, in a
`<ResourceGroup key="relationships" … instanced="false">`:

```xml
<ResourceAttribute key="VirtualMachine_parent" nameKey="364" dataType="string" isProperty="true" defaultMonitored="true" isDiscrete="false" keyAttribute="false" isRate="false" hidden="false"></ResourceAttribute>
```

and the reciprocal, line 807, inside a **dynamic tag** resource kind
`<ResourceKind key="oracle_database_vms_tag" nameKey="440" type="4" showTag="true" dynamic="true">`:

```xml
<ResourceAttribute key="VirtualMachine_child" nameKey="441" dataType="string" isProperty="true" …></ResourceAttribute>
```

These are `dataType="string" isProperty="true"` — **reporting
properties, not identifiers**. They carry no match expression.

**(c) The instance's OWN identity** (what the platform keys the Oracle
resource on) — lines 244-245:

```xml
<ResourceIdentifier dispOrder="1" key="adapter_instance_id" … identType="1"></ResourceIdentifier>
<ResourceIdentifier dispOrder="2" key="instance_id" … type="integer" identType="1"></ResourceIdentifier>
```

Neither identifier references a VM. The VM's `host_name` is only a plain
property (line 202-region: `key="host_name" dataType="string" isProperty="true"`).
**The describe.xml never states "match VirtualMachine WHERE name = host_name".**
That predicate is absent from the descriptor.

### 7.0 (`OracleDatabase-7.0_3.0.0_b20200917.104035.pak`) — contrast

Same traversal construct (`ax/oracledb_adapter3/conf/describe.xml` line 825):

```xml
<ResourcePath path="OracleDBAdapter::oracledb_environment_tag||OracleDBAdapter::database::child||OracleDBAdapter::instance::child||VMWARE::VirtualMachine::~child"/>
```

**Plus** a `.sdm` the 9.1 pak dropped —
`ax/oracledb_adapter3/conf/scripts/oracle-instance-vm.sdm` (full file):

```
instance {
    (addRelationship (container "Oracle Instances Virtual Machines" "oracledb_tag" "OracleDBAdapter") (parents this "VirtualMachine"))
    (addRelationship (container "Oracle Instances Logical Partition" "oracledb_tag" "OracleDBAdapter") (parents this "ibm_hmc_bm_exuno_ibmhmc_logical_partition"))
    (addRelationship (container "Oracle Instances PowerVM" "oracledb_tag" "OracleDBAdapter") (parents this "ibm_powervc_bm_exuno_ibmpowervc_virtual_machine"))
}
```

**Critical:** `(parents this "VirtualMachine")` reads "**the parents of
this instance that are of kind VirtualMachine**". It **presupposes the
instance already has a VM parent** and merely re-groups it under a tag
container. The `.sdm` is a grouping/UI layer over a **pre-existing**
edge; it does **not** create the base edge and carries **no** match
field. So even the 7.0 `.sdm` layer is not the matcher.

**Q1 finding:** Oracle's declarative stitch = `<TraversalSpecKind>` /
`<ResourcePath>` hop to `VMWARE::VirtualMachine::~child` + string
relationship-property placeholders (+ a grouping `.sdm` in 7.0). **The
field the foreign VM is matched against is NOT declared in any
descriptor artifact.** (Prior jar RE attributes the runtime match to
`addVmParentByNames/Ip`; per recon 2026-07-01 the live 9.1 edge is
created with zero Suite API calls — that discrepancy is a jar/runtime
question, not a descriptor one, and is out of scope here.)

---

## Q2 — Do storage paks carry the same declarative mechanism? YES.

The decisive answer is **yes — quoted below**, not "runtime API only."

**PureStorage FlashArray 4.3.0**
(`purestorageflasharray_adapter_3/conf/describe.xml`), `<TraversalSpecKind name="Pure Storage FlashArray" …>`, line 723:

```xml
<ResourcePath path="PURESTORAGEFLASHARRAY_ADAPTER::pure_storage_flasharray_purestorage_flasharray_array||PURESTORAGEFLASHARRAY_ADAPTER::pure_storage_flasharray_volumes_tag::child||PURESTORAGEFLASHARRAY_ADAPTER::pure_storage_flasharray_purestorage_flasharray_volume::child||VMWARE::Datastore::~child||VMWARE::VirtualMachine::~child"></ResourcePath>
```

Plus `<TraversalSpecExtensionKind>` extending VMWARE's own traversals
(lines 734-737):

```xml
<TraversalSpecExtensionKind name="VMWare Datastores to Pure Volumes on vSphere Storage" parentTraversalSpecName="vSphere Storage" parentAdapterKind="VMWARE">
  <ResourcePath path="VMWARE::vSphere World||VMWARE::VMwareAdapter Instance::child||VMWARE::Datacenter::child||VMWARE::StoragePod::child/recursive/preferred||VMWARE::Datastore::child||PURESTORAGEFLASHARRAY_ADAPTER::pure_storage_flasharray_purestorage_flasharray_volume::child"></ResourcePath>
```

Plus the `Datastore_parent` placeholder (line 225) inside
`<ResourceKind key="pure_storage_flasharray_purestorage_flasharray_volume">`
→ `<ResourceGroup key="relationships" … instanced="false">`:

```xml
<ResourceAttribute key="Datastore_parent" nameKey="81" dataType="string" isProperty="true" …></ResourceAttribute>
```

The volume's OWN identity (lines 187-188) is `adapter_instance_id` +
`serial` (both `identType="1"`); the NAA match keys are properties, not
identifiers — no match predicate here either.

**Dell EMC Isilon 4.3.2** (`dellemcisilon_adapter3/conf/describe.xml`) line 9297:

```xml
<ResourcePath path="DELLEMCISILON_ADAPTER::dell_emc_isilon_cluster||DELLEMCISILON_ADAPTER::dell_emc_isilon_access_zone::child||DELLEMCISILON_ADAPTER::dell_emc_isilon_nfs::child||VMWARE::Datastore::~child"/>
```
(+ `key="Datastore_parent"` property, line 455.) **No `.sdm`.**

**Dell EMC VNX Block 4.1.0** (`emcvnxblock_adapter3/conf/describe.xml`) lines 757, 764:

```xml
<ResourcePath path="EMCVNXBLOCK_ADAPTER::vnx_container||VMWARE::Datastore::child||*::*::*"/>
<ResourcePath path="EMCVNXBLOCK_ADAPTER::vnx_container||VMWARE::vSphere World::child||…||VMWARE::Datastore::child||EMCVNXBLOCK_ADAPTER::logical_unit::child"/>
```
(+ `key="datastore_parent"` property, line 495) and a grouping `.sdm`
`conf/scripts/hosted_on_block.sdm`, e.g.:

```
logical_unit {
    (addRelationship (container "Hosted on VNX Block" "vnx_container" "EMCVNXBLOCK_ADAPTER") (parents (parents this "Datastore") "VirtualMachine"))
    …
}
```
Again `(parents this "Datastore")` — walks a **pre-existing** Datastore
parent; no match field.

**NetApp E-Series 6.1.0** (`netappeseries_adapter3/conf/describe.xml`) line 1633:

```xml
<ResourcePath path="NETAPPESERIES_ADAPTER::netappeseries_tag||NETAPPESERIES_ADAPTER::array::child||NETAPPESERIES_ADAPTER::volume_group::child||NETAPPESERIES_ADAPTER::volume::child||VMWARE::Datastore::~child||VMWARE::VirtualMachine::~child"/>
```
`.sdm` `conf/scripts/virtual_machines.sdm`:
```
volume {
    (addRelationship (container "VMs Hosted on E-Series" "eseries_vm_tag" "NETAPPESERIES_ADAPTER") (parents (parents this "Datastore") "VirtualMachine"))
}
```

**HPE Nimble 5.2.0** (`nimblestorage_adapter3/conf/describe.xml`) lines 1748, 1751:

```xml
<ResourcePath path="NIMBLESTORAGE_ADAPTER::nimble_tag||NIMBLESTORAGE_ADAPTER::nimble_group::child||NIMBLESTORAGE_ADAPTER::nimble_pool::child||NIMBLESTORAGE_ADAPTER::nimble_volume::child||VMWARE::Datastore::~child"/>
```
`.sdm` `conf/scripts/Nimble-Volume-VMS.sdm` explicitly groups the
Datastore parent itself:
```
nimble_volume {
    (addRelationship (container "Nimble Volume Datastores" "nimble_volume_tag" "NIMBLESTORAGE_ADAPTER") (parents this "Datastore"))
}
```

**NetApp FAS-AFF 4.3.0** (`netappocum_adapter_3/conf/describe.xml`) line 874:

```xml
<ResourcePath path="NETAPPOCUM_ADAPTER::netapp_ocum_bm_exuno_netappocum_cluster||…||NETAPPOCUM_ADAPTER::netapp_ocum_bm_exuno_netappocum_lun::child||VMWARE::Datastore::~child||VMWARE::VirtualMachine::~child"></ResourcePath>
```
Plus a dedicated `<TraversalSpecKind name="VMware Datastores to NetApp" …>`
and `<TraversalSpecExtensionKind name="Datastores to NetApp Extension" …>`
(lines 882, 887) whose paths **start from `VMWARE::Datastore::child`** and
descend into NetApp kinds. `key="Datastore_parent"` (line 256) and
`key="Datastore_child"` (line 569) placeholders. **No `.sdm`** (compiled).

**Files checked per storage pak (inventory):** each pak's
`conf/describe.xml` (TraversalSpecKinds, TraversalSpecExtensionKinds,
`relationships` ResourceGroups, ResourceIdentifiers) + every file under
`conf/scripts/*.sdm`. No pak has a `content/*.sdm`, `resourceTag`
match element, or `geneology` declaration; grep for
`match|geneolog|matcher|eventMatch|identifierType` on the storage
describe.xml files = **0 hits**.

**Q2 finding:** storage paks **do** carry the declarative volume→Datastore
stitch — the same `<TraversalSpecKind>`/`<ResourcePath>` + `Datastore_parent`
placeholder (+ `.sdm` grouping + `TraversalSpecExtensionKind`) construct
Oracle uses for VM. The match field is **not** declared in any of them —
identical to Oracle.

---

## Q3 — Corpus catalog (declarative cross-MP to VMWARE kinds)

`declarative` column = distinct `VMWARE::<Kind>::[~]child` hops found in
`<ResourcePath>` strings in that pak's `describe.xml`; `ext` = count of
`<TraversalSpecExtensionKind>`; `sdm` = count of `conf/scripts/*.sdm`.
`runtime-API stitch` / `identity matched` columns are carried from the
jar RE in `tvs-cross-mp-stitching.md` (labeled where that file is the
source). All 48 paks were scanned; VMware-stitching ones shown.

| Pak (build) | declarative VMWARE hops (describe.xml) | ext | sdm | runtime-API stitch (jar RE) | identity matched |
|---|---|---|---|---|---|
| OracleDatabase 9.1.0 | `VirtualMachine::~child` | 0 | 0 | SuiteAPI `addVmParentByNames/Ip` (jar RE); live=0 SuiteAPI calls (recon 07-01) | VM name / IP (jar RE) |
| OracleDatabase 7.0 | `VirtualMachine::~child` | 0 | 1 | (older) | VM (name/IP) |
| PureStorage FlashArray 4.3.0 | `Datastore::~child`, `VirtualMachine::~child`, + full vSphere chain | 2 | 0 | SuiteAPI property search (jar RE) | Volume NAA / serial → Datastore (jar RE) |
| DellEMC Isilon 4.3.2 | `Datastore::~child` | 0 | 0 | SuiteAPI (jar RE) | NFS export / identity → Datastore (jar RE) |
| DellEMC VNX Block 4.1.0 | `Datastore::child`, `VirtualMachine::child`, vSphere chain | 0 | 1 | SuiteAPI; `.sdm` transitive (jar RE) | LUN serial → Datastore (jar RE) |
| DellEMC VNX File 7.0 | `Datastore::child`, `VirtualMachine::child`, vSphere chain | 0 | 1 | (7.0-era) | file/LUN → Datastore |
| DellEMC VMAX 7.0 | `Datastore::child`, `Datastore::~child`, `HostSystem::~child`, `VirtualMachine::~child` | 0 | 4 | (7.0-era) | device → Datastore |
| DellEMC XtremIO 7.0 | `Datastore::child`, `Datastore::~child`, `DatastoreFolder::child` | 0 | 4 | (7.0-era) | volume → Datastore |
| DellEMC Unity 4.2.0 | `HostSystem::child`, `VirtualMachine::child/~child`, cluster chain | 1 | 0 | SuiteAPI (jar RE family) | host / VM |
| HPE 3PAR StoreServ 7.0 | `Datastore::~child`, `VirtualMachine::~child` | 0 | 0 | (7.0-era) | volume → Datastore |
| HPE Nimble 5.2.0 | `Datastore::child`, `Datastore::~child`, `Datacenter::child` | 0 | 2 | SuiteAPI; 2 `.sdm` (jar RE) | volume IQN/serial → Datastore (jar RE) |
| NetApp E-Series 6.1.0 | `Datastore::child`, `Datastore::~child`, `VirtualMachine::~child` | 0 | 2 | SuiteAPI; 2 `.sdm` (jar RE) | volume/chassis serial → Datastore (jar RE) |
| NetApp FAS-AFF 4.3.0 | `Datastore::child`, `Datastore::~child`, `VirtualMachine::~child` | 1 | 0 | SuiteAPI (WWN/full-path, jar RE) | WWN / datastore full-path (jar RE) |
| NetApp HCI & SolidFire 7.0 | `Datastore::child/~child`, `VirtualMachine::child/~child`, cluster chain | 1 | 0 | (7.0-era) | volume → Datastore |
| Nutanix 7.0 | `Datastore::child/~child`, `VirtualMachine::child/~child`, cluster chain | 0 | 1 | (7.0-era) | container/VM → Datastore/VM |
| CiscoHyperFlex 7.0 | `Datastore::child`, `VirtualMachine::child`, cluster chain | 2 | 0 | (7.0-era) | host/VM |
| CiscoUCS 7.0 | `HostSystem::child`, `VirtualMachine::child`, cluster chain | 1 | 1 | (7.0-era) | host |
| MicrosoftSQLServer 7.0 | `Datastore::child`, `VirtualMachine::child/~child`, cluster chain | 1 | 3 | `addVmParentByNamesWithIpLookup` (jar RE) | SQL host name / IP → VM (jar RE) |
| MongoDB 7.0 | `VirtualMachine::child` | 0 | 1 | `addVmParentByNames/Ip` (jar RE) | Mongo host name / IP → VM (jar RE) |
| MySQL 7.0 | `Datastore::child`, `HostSystem::~child`, `VirtualMachine::~child` | 0 | 0 | (jar RE family) | host name / IP → VM |
| IBM Db2 7.0 | `Datastore::child`, `HostSystem::~child`, `VirtualMachine::~child` | 0 | 0 | (7.0-era) | host name / IP |
| OracleEnterpriseManager 9.0.0 | `DataStore::child`, `HostSystem::~child`, `VirtualMachine::child/~child` | 0 | 3 | SuiteAPI (jar RE family) | host / VM |
| SAPHANA / SolarWindsNPM / TAS / HPEProLiant / HPEOneView / DellEMC OME / NetworkDevices / F5 / Cohesity / Citrix* / Docker / ApacheHadoop / ApacheTomcat / CitrixVAD | `HostSystem`/`VirtualMachine` (and `Datastore` for F5/CitrixVAD) hops | 0-3 | 0-1 | host/VM name/IP (jar RE family) | host name / IP |
| AristaEOS / CareSystemsAnalytics / MEDITECH / MicrosoftAzureSQL / ServiceNow / TVSManager | **none** (no VMWARE hop) | 0 | 0 | n/a | n/a (no VMware stitch) |

**Uniform pattern:** every VMware-stitching pak in the corpus declares
its cross-MP edge as a `VMWARE::<Kind>::[~]child` hop in a
`<ResourcePath>`. **`Datastore` appears as such a hop in 12+ paks.** The
declarative construct for Datastore is not rare — it is the storage-pak
norm. No pak, in any generation, declares the match field.

---

## Q4 — Synology: can a `VMWARE::Datastore` be matched declaratively?

**Strictly from the observed descriptor grammar:**

**What the grammar DOES allow (quotable):** naming `VMWARE::Datastore` as
a hop in a `<ResourcePath>`, in either direction:
- as a downstream inverse hop from your own volume:
  `…nimble_volume::child||VMWARE::Datastore::~child` (Nimble line 1748);
- as an upstream forward hop into your volume, via
  `<TraversalSpecExtensionKind parentAdapterKind="VMWARE">`:
  `…VMWARE::Datastore::child||PURESTORAGEFLASHARRAY_ADAPTER::…_volume::child`
  (Pure line 737);
- plus an `isProperty="true"` `Datastore_parent` placeholder in a
  `relationships` ResourceGroup (Pure line 225).

A Synology adapter can emit **all three verbatim**, substituting its own
adapter/kind keys. Nothing in the grammar treats Datastore differently
from VirtualMachine — both are opaque `ADAPTER_KIND::ResourceKind`
tokens in the path string.

**What the grammar does NOT allow (quotable absence):** there is **no
attribute on `<ResourcePath>`, `<TraversalSpecKind>`, or the
`relationships` `<ResourceAttribute>` to declare "match on `DataStorePath`
/ NAA / serial / export-path".** The `<ResourcePath>` `path` grammar
(spec/07) is strictly `ADAPTER_KIND::ResourceKind[::child|::~child][/recursive|/preferred]`
chained by `||` — no predicate slot. Confirmed empirically: no pak
declares a foreign `VMWARE` `<AdapterKind>` or `VMWARE::Datastore`
`<ResourceKind>` stub anywhere (grep = 0), so there is **no descriptor
site** where a Datastore identifier (`VMEntityObjectID`, `VMEntityVCID`,
`DataStorePath`, or an NAA property) could be bound to a match value.
The mpb structural reference (`context/mpb/mpb_pak_structural_reference.md`)
shows `<TraversalSpecKinds/>` empty for Gen-2 and lists no match
attribute; `eventMatchers` exists only for ARIA_OPS objects, not for
Datastore path stitching. Datastore's true identity per spec/07 is
`(VMEntityObjectID, VMEntityVCID)` — **both default-unique** — with
`DataStorePath` marked `identType="2"` (NOT uniqueness-bearing); a
declarative path hop does not, and cannot, encode a value for these.

**INFERENCE (labeled):** because the descriptor for Oracle's VM stitch
and for every storage pak's Datastore stitch is the *same* construct with
*no* match field, and the Oracle construct is live-proven to produce a
CP-immune edge (recon 2026-07-01, 0 Suite API calls), the descriptor
layer alone is **necessary but not sufficient**: declaring
`synology_volume::child||VMWARE::Datastore::~child` reproduces exactly
what the working paks declare, but the actual identity binding (volume →
the correct Datastore) is performed by a mechanism *outside* the
descriptor. This report cannot, from descriptors alone, prove that
mechanism is CP-immune for Datastore — it can only prove the declarative
scaffolding is identical to Oracle's proven-CP-immune VM scaffolding.
Confirming the binder for Datastore (SDK-native relationship push vs.
platform correlation of the reported `Datastore_parent` property vs.
Suite API read) is a **jar/runtime** question and a follow-up.

---

## Final answer — is there a descriptor-declared, CP-immune datastore stitch?

**Descriptor-declared: YES, unambiguously.** The volume→`VMWARE::Datastore`
relationship is declared in the descriptor layer by 12+ TVS paks, via
`<TraversalSpecKind>`/`<ResourcePath>` hops (`VMWARE::Datastore::~child`),
`<TraversalSpecExtensionKind>` (Pure, FAS-AFF), a `Datastore_parent`
`isProperty` placeholder, and (VNX/E-Series/Nimble) grouping `.sdm`
scripts. Synology can copy this verbatim. Quotes above.

**CP-immune: NOT PROVABLE FROM DESCRIPTORS, but the scaffolding is
identical to the proven case.** No descriptor artifact — in any pak, any
generation — declares the identity **match field** for either VM or
Datastore. The descriptor pre-registers the relationship **shape** only;
the edge's identity binding is created outside the descriptor. Oracle's
VM version of this exact scaffolding is live-proven CP-immune; the
storage/Datastore version is structurally identical in the descriptor but
its binder was **not** determined here (descriptor-only scope). So: the
declarative layer is a **prerequisite you can and should author for
Synology by cloning Pure/Nimble/E-Series**, but "CP-immune" hinges on the
out-of-descriptor binder, which needs the jar/runtime follow-up before we
claim it.

**Correction logged against `tvs-cross-mp-stitching.md`:** that file's
per-pak matrix lists storage "foreign-resolve = SuiteAPI property search"
and does not record that the **same** paks *also* ship a full declarative
`VMWARE::Datastore` traversal in describe.xml. Both layers coexist:
declarative shape (this file) + runtime binder (that file). Neither file
has yet proven which layer creates the live edge on 9.x — that is the
open reconciliation.

---

## Follow-up questions

1. **Which layer actually creates the live edge on 9.x** — the declarative
   `<ResourcePath>` + reported `Datastore_parent` property (platform
   correlation), or the jar's SDK relationship push? Oracle 9.1 shows 0
   Suite API calls, which rules out the Suite-API-read binder the jar RE
   assumed. Determine this for a storage pak (Pure/Nimble) too.
2. **Does the platform auto-stitch from the reported
   `relationships|<Kind>_parent` property value alone** (descriptor
   placeholder + collected value), with the TraversalSpec only providing
   UI navigation? If so, the "match field" is the runtime value written
   to that property — the closest thing to a descriptor-adjacent binder.
3. **For Synology specifically:** what value must the volume's
   `Datastore_parent` property (or the pushed ResourceKey) carry to bind
   the correct `VMWARE::Datastore` by its real identity
   `(VMEntityObjectID, VMEntityVCID)` — and can that be derived on a CP
   without a Suite API read? (Ties into `lessons/`-level CP-403 work.)
