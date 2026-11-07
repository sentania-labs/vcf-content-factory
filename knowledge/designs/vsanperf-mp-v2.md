# Design Artifact: vSAN Performance Management Pack v2 (Build 2, Tier 2, Java SDK)

**Status.** Build 2 design revision, for review before `sdk-adapter-author`
starts. `knowledge/designs/vsanperf-mp-v1.md` stays the Build 1 record
(released as `v1.0.0.9`) and is authoritative for everything this file does
not change. Disk-tier and VM-tier parser code is blocked on prerequisite P2
(two verbatim captures, §Prerequisite P2); host-tier and cluster-tier code is
not blocked. One decision is open for Scott before the first scale-release
tag: key-tree alignment (§Key tree alignment, Q1).

**Supersedes in v1** (v1 carries a forward pointer to this file):
- v1 §Build 2 (orientation), tier table, disk row: target was the built-in
  vSAN disk kinds matched on `VSANID` + host, emitting only the keys that do
  not overlap the built-in `vSAN|Performance|*` names. Now (B6): HostSystem,
  instanced by disk uuid, all 31 keys when the tier is on (Q4).
- v1 §Build 2 (orientation), cluster row: "Q6" is answered here
  (ClusterComputeResource, B4); the note on `vsan-direct-cluster`,
  `vsan-file-service`, `ioinsight` entity ids is replaced by the runtime
  landing rule (§Identity).
- v1 §Settings, "Build 2 additions": `tiers` (one multi-value setting) and
  `exclude_groups` are replaced by `tier_host`, `tier_cluster`, `tier_disk`,
  `tier_vm` and `exclude_types`; `vm_tier_every_n_cycles` stays, now
  staggered by cluster.
- v1 §Collector shape, "Learned types": "An empty echo ... is recorded as
  'empty this cycle', not learned" is replaced for Build 2 by the
  learned-empty rule (B7, §Failure handling).
- v1 §Value selection, "newest non-`None` token" per series: replaced by the
  one bucket rule in §Sizing requirement 2 (every bucket in the window newer
  than the per-(entity, label) mark is pushed), for all tiers.
- v1 §Build 2 (orientation), VM row: `virtual-disk` instanced by bus
  position (B5), not by disk; `vscsi` by device as before.

**MP display name:** `VCF Content Factory vSAN Performance` (unchanged).
**adapter_kind:** `vcfcf_vsanperf` (unchanged).
**Repo:** `sentania-labs/vcf-content-factory-sdk-vsanperf` (unchanged; cloned
to `content/sdk-adapters/vsanperf/`; official `.pak` from that repo's CI on a
`v*` tag). Bundled views and dashboards, when they come, live in that repo.
**Replaces:** the Python Integration SDK pack `vsanhostmetrics` 2.0.0 at its
default "dashboard" scope.

**Grounding.** Every API fact here comes from these sources. Numbers are
quoted from them, not restated from memory.

| Ref | Source |
|---|---|
| V1 | `knowledge/designs/vsanperf-mp-v1.md` (both addenda, Build 2 orientation, Decisions D1 to D9, Q6, Q7) |
| MAP | `knowledge/context/api-maps/vsan-performance-service.md`, especially "Build 2 entity types (measured 2026-11-06)", "Join keys per target object", "Cross-Request Join Keys" |
| PROV2 | `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-06-build2.md` and the 24 per-type captures it lists |
| PROV1 | `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-06-evening.md` (the three Build 1 captures: 9,130 B wire, 131,577 B decoded, 390 series) |
| PLAN | `knowledge/context/investigations/2026-11-06-vsanhostmetrics-scale-plan.md` (§1 worked example, §3 call budget, §4 tiers) |
| INV | `knowledge/context/investigations/2026-11-06-vsan-adapter-inventory.md` (§3 disk overlap, §4 identifiers) |
| T5-9 | `knowledge/context/reviews/vsanperf-t5-devel-9.0-build-9.md` (measured `PERF push`: 390 stat values, ~33,360 bytes, 45 ms) |
| PAK | `content/sdk-adapters/vsanperf/REFERENCE.md`, `README.md`, `src/.../EntityType.java`, `Watermarks.java`, `CappedBody.java`, `OpsHostMap.java` (Build 1 key grammar, settings, collector shape, caps) |
| PY | `content/sdk-adapters/vsanhostmetrics/app/metric_scope.py` (COVERED), `metric_labels.py` (LABELS, UNITS), `perfsvc_model.py` + `perfsvc_model_extra.py` (kind to type, identity), `perfsvc.py` (`KIND_SUFFIX`, `PERMILLE`) |
| VMW | `knowledge/context/cleanroom-spec/analysis/per-adapter/vmwarevi_adapter3.md` (VMWARE `VirtualMachine` identifiers, including `VMEntityInstanceUUID`) |

---

## Original Request

Build 2 = metric parity with the Python vsanhostmetrics pack's default
"dashboard" scope (451 keys over 33 entity types, PY COVERED) on the Build 1
object model: no objects of the pak's own beyond the adapter instance and its
collector object; every vSAN metric stitched onto the vCenter adapter's
objects. Build 1 delivered 61 keys over 3 types; Build 2 adds the remaining
**390 keys over 30 types** (MAP "Build 2 entity types").

## Tier decision (recorded, not re-evaluated)

Tier 2, Java SDK, as V1 §Tier decision. Same repo
(`vcf-content-factory-sdk-vsanperf`); no new repo to instantiate.

## Decisions taken before this revision (brief, 2026-11-06)

| # | Decision |
|---|---|
| B1 | Build 1 keys and identity stay as released in `v1.0.0.9`: `vSAN Perf\|<group>[:<instance>]\|<metric><UnitSuffix>`, collector object identity (`vcenter`, `cluster_scope`), account identity (`vcenter_host`, `cluster_include`). Build 2 adds keys only. |
| B2 | Key-tree alignment with the vsanhostmetrics 2.0.0 `cptvsan\|` grammar is open for the user. Tables here use the current grammar; §Key tree alignment makes a switch a table change. |
| B3 | Tiers are settings: cluster, host (the remaining host types), disk, VM. Defaults recommended for a 70-cluster customer and justified from measured costs. |
| B4 | Cluster-tier keys land on VMWARE `ClusterComputeResource`, keyed (MoRef, VCID), resolved like hosts (recommended; the built-in vSAN Cluster alternative is noted). |
| B5 | VM-tier keys land on VMWARE `VirtualMachine`, keyed on `config.instanceUuid` (30/30 verified), resolved through the Suite API VirtualMachine list. `virtual-disk` and `vscsi` are instanced on the VM: instance = bus position for both (`scsi0:0`; for `virtual-disk` from the device read, §VirtualMachine), `deviceInfo.label` being the stated alternative (Q5). |
| B6 | Disk tier: ESA disk types instanced on the host by disk uuid; host found by a per-host `QueryDisksForVsan` (7 to 10 ms, key on non-empty `vsanUuid`), cached per identity refresh. OSA `cache-disk` / `capacity-disk` stay as entity types that are empty on ESA and learned-skipped. |
| B7 | Empty types learned per cluster for 24 h. (Build 1 learns only faults; an empty echo is "empty this cycle", PAK `LearnedTypes`. Build 2 extends learning to empty echoes, with the complete rule in §Failure handling: 3 consecutive empties, immediate re-learn on an empty re-probe, per-VM-run counting for VM types, core types and `ioinsight` exempt.) |
| B8 | The 4 `NIOPS*` virtual-disk labels that are always `None` on the lab stay requested and are documented. |
| B9 | Cluster-level DOM Owner and DOM Client are the cluster-wide totals of the host roles (the owner-vs-client reading from the v1 REFERENCE). |

## Interview Answers

| Question | Answer |
|---|---|
| Monitoring scope | The 451-key default scope: Build 1's 61 plus the 390 below. |
| Object granularity | No first-class vSAN objects. Host-, disk- and network-scoped types are key groups on HostSystem; cluster types on ClusterComputeResource; VM types on VirtualMachine. Multi-entity-per-object types are instanced groups. |
| Cross-adapter stitching | Yes: VMWARE HostSystem (Build 1), ClusterComputeResource, VirtualMachine. Nothing on the built-in vSAN adapter's objects. |
| Collection interval | 5 minutes; VM tier every Nth cycle, staggered by cluster (default N = 3 when the tier is on). |

---

## Scope and totals per tier

"Core" is Build 1 (always on). Lab = one 5-host ESA cluster, 30 vSAN VMs,
1 ESA disk per host, 2 vSAN pNICs per host, one vSAN netstack and one vSAN
vmknic per host (MAP). Calls per cluster are one wildcard spec per type, the
API floor (MAP test 4); "steady" is after the empty types are learned,
"first" is the first cycles and the daily re-probe. Wire / decoded bytes and
serial ms are the sums of the measured per-type rows (PROV2 for Build 2
types, PROV1 for core); "serial ms (steady)" leaves out the empty types.

| Tier | Types | Keys | Lab entities | Lab series | Lab series with a value | Calls / cluster steady (first) | Serial ms, lab, steady (first) | Wire / decoded B, lab |
|---|---|---|---|---|---|---|---|---|
| core (Build 1) | 3 | 61 | 20 | 390 | 390 | 3 (3) | 591 (591) | 9,130 / 131,577 |
| host | 13 | 149 | 60 | 705 | 705 | 12 (13) | 1,570 (1,699) | 19,145 / 245,509 |
| cluster | 10 | 189 | 7 | 91 | 91 | 8 (10) | 1,189 (1,447) | 3,805 / 31,844 |
| disk | 4 | 31 | 10 | 50 | 50 | 2 (4) on ESA | 360 (631) | 1,926 / 18,994 |
| vm | 3 | 21 | 326 | 2,400 | 1,808 | 3 (3) | 613 (613) | 48,554 / 852,153 |
| **Build 2 (host+cluster+disk+vm)** | **30** | **390** | **403** | **3,246** | **2,654** | **25 (30)** | **3,732 (4,390)** | **73,430 / 1,148,500** |
| **All (core + Build 2)** | **33** | **451** | **423** | **3,636** | **3,044** | **28 (33)** | **4,323 (4,981)** | **82,560 / 1,280,077** |

- The Build 2 totals reproduce PROV2's totals (30 calls, 73,430 B wire, 1,148,500 B decoded, 403 entities, 3,246 series). PROV2's 4.395 s is **wall time** (one timer
  around the serial loop); the per-call sum of its 30 rows is 4,389.5 ms
  (column above: per-tier sums rounded, 4,390). 27 of 33
  types non-empty matches MAP "Design answers" (~27 after learned skips).
- Empty on the lab (wildcard echo, 81 to 153 ms and ~120 B each): cluster
  tier `vsan-direct-cluster`, `vsan-file-service`, `ioinsight`; host tier
  `vsan-direct-host`; disk tier `cache-disk`, `capacity-disk` (MAP). On an
  OSA cluster the disk tier inverts: `cache-disk` and `capacity-disk` carry
  data and the two `vsan-esa-disk-*` types are expected empty (inferred, no
  OSA lab).
- "Series with a value": the VM tier's 592 `NIOPS*` series (148 vdisks x 4)
  were all `None` and push nothing (MAP; B8).
- Lab per-unit ratios used for projections: core 78 series per host (2
  pNICs); host tier 141 per host; cluster tier 91 per cluster; disk tier 10
  per disk; VM tier 80 requested / 60.3 with a value per VM (148 vdisks and
  148 vSCSI devices over 30 VMs, 4.93 each).

---

## Object Model

```
VCF Content Factory vSAN Performance (adapter kind vcfcf_vsanperf)
 └── vSAN Performance Adapter Instance              (own kind; self-metrics Collection|*)
      └── VCF Content Factory vSAN Performance Collector  (own kind VsanPerfCollector, one per instance, no metrics; V1 addendum, build 7)

Stitched (ARIA_OPS, no describe.xml entry for the target kinds, pushed through the Suite API):

VMWARE ClusterComputeResource  (cluster tier; new in Build 2)
 ├── vSAN Perf|Capacity|*                    5 keys
 ├── vSAN Perf|DOM Client|*                 11
 ├── vSAN Perf|DOM Comp Mgr|*               12
 ├── vSAN Perf|DOM Owner|*                  23
 ├── vSAN Perf|ESA Dedup DOM Client|*       24
 ├── vSAN Perf|RDT Latency|*                 9
 ├── vSAN Perf|ZDOM Top Stats|*              7
 ├── vSAN Perf|vSAN Direct Cluster|*         8   (landing decided per entity, see Identity)
 ├── vSAN Perf|File Service|*                8   (same)
 └── vSAN Perf|IOInsight|*                  82   (same)

VMWARE HostSystem  (Build 1 core, plus host and disk tiers)
 ├── vSAN Perf|DOM Owner|*  vSAN Perf|DOM Client|*  vSAN Perf|pNIC:<vmnic>|*       (Build 1, 61 keys)
 ├── vSAN Perf|CMMDS Network|*              10
 ├── vSAN Perf|CPU|*                         7
 ├── vSAN Perf|vSAN Direct|*                 8
 ├── vSAN Perf|DOM Comp Mgr|*               16
 ├── vSAN Perf|ESA Dedup DOM Client|*       24
 ├── vSAN Perf|Host Network|*                8
 ├── vSAN Perf|ZDOM Top Stats|*             11
 ├── vSAN Perf|Memory|*                     12
 ├── vSAN Perf|RDT Latency|*                11
 ├── vSAN Perf|TCP/IP:<stack>|*             12 per netstack
 ├── vSAN Perf|vNIC:<vmk>|*                 10 per vSAN vmknic
 ├── vSAN Perf|vNIC RDT Latency:<vmk>|*     10 per vSAN vmknic
 ├── vSAN Perf|ZDOM VTX|*                   10
 ├── vSAN Perf|Cache Disk:<disk uuid>|*      8 per OSA cache disk        (disk tier)
 ├── vSAN Perf|Capacity Disk:<disk uuid>|*  13 per OSA capacity disk     (disk tier)
 ├── vSAN Perf|ESA Disk Layer:<disk uuid>|*  5 per ESA disk              (disk tier)
 └── vSAN Perf|ESA Disk SCSI:<disk uuid>|*   5 per ESA disk              (disk tier)

VMWARE VirtualMachine  (VM tier; new in Build 2)
 ├── vSAN Perf|VM|*                          6
 ├── vSAN Perf|Virtual Disk:<busN:M>|*      7 per VMDK (bus position, e.g. scsi0:0)
 └── vSAN Perf|vSCSI:<scsiN:M>|*             8 per virtual SCSI device
```

New objects: **0** (the adapter instance and the collector object exist
since Build 1). Lab comparison: the Python pack holds 460 objects for this
cluster (PLAN §1); the built-in vSAN adapter 11 (PLAN §5).

### Relationships

1. None created. Every key rides on an object already in vCenter's tree.
2. Adapter instance to collector object, as in Build 1 (V1 addendum, build 7).

### Group names and key grammar

- Grammar unchanged (B1): `vSAN Perf|<group>|<leaf>` or
  `vSAN Perf|<group>:<instance>|<leaf>`. Group names come from PY
  `KIND_SUFFIX` where it has one; the seven types it lacks get six new
  names: `ESA Dedup DOM Client` (both dedup types), `vSAN Direct Cluster`,
  `vSAN Direct`, `File Service`, `IOInsight`, `vSCSI`.
- **Group names are unique per target object**, including the three
  cluster-tier types whose landing is decided at run time: if `ioinsight`
  turns out host-keyed, its keys land on HostSystem under `IOInsight` and
  collide with nothing (`vSAN Direct Cluster` is named apart from the host
  type's `vSAN Direct` for this reason).
- Characters in segments: `TCP/IP` and the vSCSI instance `scsi0:0` follow
  existing Ops precedents on the same lab (built-in `DiskI/O|*` on Storage
  Pool; VMWARE `virtualDisk:scsi0:0|*` and `guestfilesystem:/boot|*` on
  VirtualMachine, INV Appendix A). Spaces in segments were accepted in the
  Build 1 push test (V1, PUSH). A disk uuid as an instance is new; the T5
  browser pass checks how each instanced group renders.

### Leaf rule, extended for Build 2 (Build 1 leaves unchanged)

V1's rule, applied as is: per-mille labels (PY `PERMILLE`) are divided by 10
and get `Pct`; microsecond labels get `Us` and byte-rate labels
`BytesPerSec`, unless the label already ends `Us`, `Sec` or `Bps`; everything
else unchanged. Build 1's 61 labels have no other units, so the following
extension changes none of them:

- byte sizes (PY unit `DATA_SIZE.BYTE`) get `Bytes` (25 labels), except
  `deleteCongestion` on `capacity-disk`: PY says bytes, but congestion is a
  unitless score everywhere else (Build 1 `congestion`, "none stated"), so it
  stays unsuffixed (R3b);
- milliseconds get `Ms` and non-per-mille percent gets `Pct` unless already
  there. The one millisecond label and all 8 percent labels already end that
  way, so no leaf changes today; the rule is stated for future types.

Result for the 390: 70 labels get `Us` (3 more already end in it), 44 get
`BytesPerSec`, 17 per-mille labels get `Pct`, 25 get
`Bytes`; the rest are verbatim. Units are still PY's (harvested from HCIBench,
V1 R3); the capture magnitudes agree where checked (`total`
20,166,389,152,256 bytes = ~20 TB on the lab's capacity type; `vsan-memory`
sizes in the MB to GB range; `vsan-cpu` percentages 0 to 9).

---

## Identity and resolution per target

All targets follow the Build 1 rule: a foreign object is addressed by MoRef
**plus** vCenter `about.instanceUuid` (`VMEntityObjectID` + `VMEntityVCID`),
never by MoRef or name alone (`knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`).
Nothing unresolved is ever pushed under a guess; it is counted, logged once
per refresh, and dropped (V1).

### HostSystem (core, host tier, disk tier)

| Type(s) | entityRefId after the first `:` | Join | Status |
|---|---|---|---|
| `cmmds-net`, `vsan-cpu`, `host-domcompmgr`, `host-esa-dedup-domclient-io`, `vsan-host-net`, `host-zdom-top-stats`, `vsan-memory`, `rdt-network-latency`, `zdom-vtx` | `<nodeUuid>` | nodeUuid = host `config.vsanHostConfig.clusterInfo.nodeUuid` (R2 read, Build 1) to MoRef to Ops id (Build 1 `OpsHostMap`) | **verified**: 5/5 node uuids for each of the 12 non-empty host types, no extras (MAP) |
| `vsan-tcpip-stats` | `<nodeUuid>\|<stack>` | node as above; instance = stack | grammar verified; one stack per host only, multi-stack **unobserved** |
| `vsan-vnic-net` | `<nodeUuid>\|<stack>\|<vmk>` | node as above; instance = vmk (stack dropped from the key) | grammar verified; one vmk per host only, multi-vmk **unobserved** |
| `vnic-rdt-network-latency` | `<nodeUuid>\|<vmk>` | node as above; instance = vmk | grammar verified; one vmk per host only |
| `vsan-direct-host` | **unobserved** (empty on the lab; PY models `host_uuid`, provisional) | node as above when the id is exactly one uuid matching a node | **unverified** |
| `vsan-esa-disk-layer`, `vsan-esa-disk-scsifw` | `<vsan disk uuid>` (no host in the id) | disk map: per host, `QueryDisksForVsan` (`POST /sdk/vim25/<rel>/HostVsanSystem/<configManager.vsanSystem moId>/QueryDisksForVsan`, body `{}`); entries with non-empty `vsanUuid` map that uuid to the host the call was made against; instance = the disk uuid | **verified**: 5/5 for both ESA types (MAP). Needs `configManager.vsanSystem` added to the R2 host pathSet (MAP), added only when the disk tier is on |
| `cache-disk`, `capacity-disk` | **unobserved** (OSA; empty on ESA); PY `disk_uuid` | same disk map; on OSA the in-use disks are expected to carry `vsanUuid` too | **unverified** (no OSA lab) |

- Disk map alternative, measured but not chosen: `QueryVsanManagedDisks`
  (31 to 79 ms, ~860 B per host, ESA-native, what the Python pack uses).
  `QueryDisksForVsan` is 7 to 10 ms and ~1.6 KB per host (MAP). On this ESA
  cluster in-use disks report `state: "ineligible"`, so the key is non-empty
  `vsanUuid`, never `state` (MAP).
- Disk-map cadence: built at the first disk-tier cycle, then with the Build 1
  identity refresh (every 12th cycle, on a change in a cluster's host set),
  and for one cluster on the next cycle after an unmapped disk uuid shows up
  in that cluster's response (at most once per 12 cycles per cluster, so a
  permanently unmappable disk cannot drive a refresh every cycle). Cost per
  refresh: one call per in-scope host (420 at the 70-cluster example, ~3 to 4 s
  serial at 7 to 10 ms), run on the pool, one host per task.
- The built-in vSAN adapter's `Vsan2Disk` is **not** the target (B6): it is
  matched only on `VSANID` plus host (VSANID is not unique, INV §4), it
  exists only where the built-in adapter collects, and 24 of the disk tier's
  31 names already exist on it (INV §3). Keys on the host keep everything in
  one place, at the price of the name overlap (R10).

### ClusterComputeResource (cluster tier)

| Step | Source | Status |
|---|---|---|
| entityRefId suffix = vSAN cluster uuid | MAP grammar table | **verified**, 7/7 non-empty cluster types |
| vSAN cluster uuid to cluster MoRef | the Build 1 R2 read: the cluster's member hosts' `config.vsanHostConfig.clusterInfo.uuid` (Build 1 rule: majority of enabled members); equal to `configurationEx.vsanConfigInfo.defaultConfig.uuid` on 5/5 hosts | **verified** (MAP). No new vCenter call |
| (MoRef, VCID) to Ops resource id | Suite API `GET /api/resources?adapterKind=VMWARE&resourceKind=ClusterComputeResource` (same paging and VCID filter as `OpsHostMap`), identifiers `VMEntityObjectID` + `VMEntityVCID` | **assumed, unverified**: the Ops map is written on `VMEntityObjectID` + `VMEntityVCID` by analogy with HostSystem; INV §4 names MoRef + VCID as the key and the built-in cluster ID string embeds the MoRef, but no read of a ClusterComputeResource's identifiers is recorded. Confirmed by P2 item 3; gated at T5 step 1 (no cluster-tier push before it passes); Q9 |
| Pushing stats to a ClusterComputeResource | Suite API batch push, as for hosts | **unverified for this kind** (PUSH proved HostSystem only) |

Refresh with the host map (every 12th cycle, on a change in the in-scope
cluster set). A miss (cluster MoRef not in Ops) is counted in the new
`Collection|clusters_unresolved` and triggers only an Ops map refresh,
rate-limited to once per 12 cycles per vCenter (the disk map's guard); the
cluster is skipped until that refresh or the next scheduled one finds it.

**Runtime landing for the three unobserved cluster-tier types**
(`vsan-direct-cluster`, `vsan-file-service`, `ioinsight`; MAP Gaps: "whether
[they] key on the cluster uuid or a host nodeUuid ... is still open"). Each
entity is classified when it arrives:
1. id is exactly the cluster's vSAN uuid: ClusterComputeResource;
2. id is exactly one node uuid of that cluster: HostSystem, same group name;
3. anything else (extra `|` parts, an unknown uuid): skipped, counted in
   `Collection|entities_unparsed`, WARN once per type per day with the type
   and the part count (not the id).
No instanced form is guessed. The first real capture of any of these three
types becomes a T1 fixture and settles its row in this design.

**Alternative target, not recommended:** the built-in vSAN adapter's
`VirtualSANDCCluster`. Its unique ID is the string
`vSAN Cluster(<domain-cNNN>, <datacenter name>)` (INV §4), so matching means
parsing a display string that changes when the datacenter is renamed; the
object exists only where the built-in vSAN adapter is configured; and its
`vsan|performance|*` keys share names with ours (`iopsRead`, `congestion`)
at a different layer (INV §3 note), which reads as duplication beside them.
ClusterComputeResource is always present when hosts are, and is keyed the
way Build 1 already resolves hosts.

### VirtualMachine (VM tier)

| Type | entityRefId after the first `:` | Join | Status |
|---|---|---|---|
| `virtual-machine` | `<VM config.instanceUuid>` | instanceUuid to VM MoRef (vCenter VM read below) to Ops id by (MoRef, VCID) from the Suite API VirtualMachine list | instanceUuid **verified** 30/30 (`config.uuid` matched 0/30) (MAP). Ops side **assumed, unverified**: `VMEntityObjectID` + `VMEntityVCID` per the VMWARE describe (VMW), no VirtualMachine identifier read recorded; P2 item 3, T5 step 1, Q9 |
| `vscsi` | `<instanceUuid>\|<controller>:<unit>` | as above; instance = `scsiN:M` | **verified** 148/148 refs over 30 VMs; controllers seen `scsi0` (132), `scsi1` (16) |
| `virtual-disk` | datastore path without `[datastore] `, sometimes with a leading `/` | strip the leading `/`; match `VirtualDisk.backing.fileName` minus `[<datastore>] ` from the device read; gives VM MoRef and the disk's bus position (the instance) | **verified** 148/148, no collisions after stripping (MAP) |

- **The VM read.** PropertyCollector `RetrievePropertiesEx` over a
  ContainerView of `VirtualMachine`, pathSet `config.instanceUuid` always,
  plus `config.hardware.device` only when `virtual-disk` is in scope.
  **Measured cost** (MAP): `name`, `config.instanceUuid`, `config.uuid`,
  `config.hardware.device` over a root-folder view, 45 VMs vCenter-wide (30
  on vSAN): **149 KB wire / 1.09 MB decoded / 70 ms per read**, almost all of
  it `config.hardware.device`. That is ~3.3 KB wire and ~24 KB decoded per VM;
  linear projection to the 70-cluster example (16,800 VMs, PLAN §1) is ~56 MB
  wire and ~407 MB decoded for one full read (projection, not measured).
- **Scoping.** One view per in-scope vSAN cluster (a ComputeResource is a
  valid ContainerView container per vim25, but **scoping the view to a
  cluster was not tested**, MAP), so VMs outside vSAN clusters are never
  read (15 of 45 on the lab). Fallback if the per-cluster view misbehaves:
  the measured root-folder view, filtered client side.
- **Paging and memory.** `RetrieveOptions.maxObjects` = 50 VMs per page
  (~1.2 MB decoded per page at 24 KB per VM), `ContinueRetrievePropertiesEx`
  while a `token` returns (the Build 1 loop). Each page is parsed and reduced
  at once to compact rows and discarded: instanceUuid to VM index; normalized
  vdisk path, hashed to 64 bits, to (VM index, packed bus position: prefix
  code, bus number, unit number in one `int`), held in sorted primitive
  arrays (~16 B per vdisk; 82,880 vdisks at the example is ~1.3 MB). Paging
  with `maxObjects` over JSON is **unverified** (the Build 1 loop only ever
  saw one page on the lab).
- **Bus position (the `virtual-disk` instance, B5).** From the same
  `config.hardware.device` array: the `VirtualDisk`'s `controllerKey` is
  looked up among the array's controller devices by `key`; the controller's
  `busNumber` and the disk's `unitNumber` give `<prefix><bus>:<unit>`. Prefix
  by controller `_typeName` (vim25 type names): the SCSI controller types
  (`ParaVirtualSCSIController`, `VirtualLsiLogicController`,
  `VirtualLsiLogicSASController`, `VirtualBusLogicController`) give `scsi`,
  `VirtualNVMEController` gives `nvme`, `VirtualAHCIController` gives `sata`,
  `VirtualIDEController` gives `ide` (`scsi0:0`, `nvme0:0`, `sata0:0`,
  `ide0:0`). An unknown controller type: the disk is skipped and counted in
  `vdisks_unresolved`, never guessed. Only `scsi` is observed on the lab
  (vscsi refs `scsi0`, `scsi1`); whether the `vscsi` entity type reports
  NVMe or SATA devices at all, and under which prefix, is unverified (Q9).
  The stated alternative is `deviceInfo.label` (`Hard disk 1`), a display
  string (R17, Q5).
- **Device-list caching (B5 question).** Not per cycle. The device map is
  read: (a) on the first VM-tier run of a cluster; (b) again for that
  cluster every 12th VM-tier run of that cluster (at the default cadence
  N = 3 that is every 3 hours); (c) for one cluster on its next VM-tier run
  when its `virtual-machine` response names an instanceUuid not in the map
  (VM set change, detected for free from the perf response) or its
  `virtual-disk` response has a path not in the map (disk added, storage
  vMotion), rate-limited to once per 12 cycles per cluster (the disk map's
  guard; a missing VM or path is skipped until then). Steady-state
  cost is therefore (b) plus changes: at the example, 70 cluster reads spread
  over 36 cycles, ~2 per cycle, ~0.8 MB wire and ~5.8 MB decoded each
  (240 VMs x 3.3 / 24 KB, projection). A light read (`config.instanceUuid`
  only, no devices) is all that `virtual-machine` and `vscsi` need; it is
  used when `virtual-disk` is excluded. Incremental `WaitForUpdatesEx` is
  the next step if `PERF identity` lines show the reads matter; not in
  Build 2.
- **Ops side.** Suite API `GET /api/resources?adapterKind=VMWARE&resourceKind=VirtualMachine`,
  same filter as `OpsHostMap`, **page size 500** (not the host map's 5,000:
  a VM resource's JSON size is unmeasured and 5,000 per page could put
  several MB through a full-tree parse), refreshed every 12th VM-tier run,
  or on a VM-set change. A VM MoRef not in Ops triggers only an Ops map
  refresh, rate-limited to once per 12 cycles per vCenter, and is skipped
  until a refresh finds it; it never triggers a vCenter re-read.
  `VMEntityInstanceUUID` is a VMWARE
  VirtualMachine identifier (identType 2, optional, VMW), so the instanceUuid
  could resolve directly; whether it is populated on live 9.x Ops is
  **unverified**, so it is read and compared as a T5 cross-check only, and
  resolution stays on (MoRef, VCID) like hosts.
- Misses: instanceUuid with no VM in the map, `Collection|vms_unresolved`;
  vdisk path with no device, `Collection|vdisks_unresolved`; VM MoRef with no
  Ops VM (for example a VM the vCenter adapter does not collect), counted in
  `vms_unresolved`. All dropped, never guessed.
- **Compute elsewhere, storage here (unverified).** A VM whose disks are on
  this cluster's vSAN datastore but which runs on hosts of another cluster
  (HCI Mesh client, or a non-vSAN cluster mounting the datastore) may appear
  in this cluster's `virtual-machine` / `vscsi` / `virtual-disk` responses
  while the per-cluster VM read (scoped to this cluster's VMs) does not list
  it. Such a VM would show as an instanceUuid miss on every run; the 12-cycle
  rate limit bounds the re-reads, and it stays in `vms_unresolved`. Not
  observable on the lab (one cluster); Q9.

---

## Metric tables (390 keys)

Columns as V1: the "vSAN label" column is exactly the spec's `labels` array
for the type (every requested label came back on every non-empty type, and
no others; PROV2). Checked by script against PY COVERED and, for the 24
non-empty types, against the label set of each verbatim capture: all equal.
"Python label" is PY `LABELS`; "Unit" is PY `UNITS` rendered (`none stated`
where PY has none); transform is `per-mille / 10` for PY `PERMILLE`, else
none. A "name matches built-in" note marks the 24 disk-tier names that also
exist as `vSAN|Performance|*` on the built-in disk objects (INV §3, name
match only, no value comparison).

### Cluster tier: 10 types, 189 keys (lands on ClusterComputeResource)

#### `vsan-cluster-capacity` (Python kind `VsanClusterCapacity`): 5 keys per cluster

vSAN datastore capacity and space efficiency for the cluster. `dedupRatio` is served as ratio x 100 (Python label "100 = 1.00x"; 145 on the lab) and pushed as served.

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 5 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `dedupRatio` | `vSAN Perf\|Capacity\|dedupRatio` | Space Efficiency Ratio (100 = 1.00x) | none stated | none; ratio x 100 (Python label: 100 = 1.00x); pushed as served |
| `free` | `vSAN Perf\|Capacity\|freeBytes` | Free Capacity | bytes | none |
| `savedByDedup` | `vSAN Perf\|Capacity\|savedByDedupBytes` | Saved Capacity | bytes | none |
| `total` | `vSAN Perf\|Capacity\|totalBytes` | Total Capacity | bytes | none |
| `used` | `vSAN Perf\|Capacity\|usedBytes` | Used Capacity | bytes | none |

#### `cluster-domclient` (Python kind `VsanClusterDomclient`): 11 keys per cluster

The cluster-wide total of the hosts' DOM Client role: the I/O the cluster's VMs issued, as the clients saw it (the host-level reading is in the v1 REFERENCE "DOM Client" text).

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 11 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `congestion` | `vSAN Perf\|DOM Client\|congestion` | Congestions | none stated | none |
| `iopsRead` | `vSAN Perf\|DOM Client\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|DOM Client\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|DOM Client\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|DOM Client\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `oio` | `vSAN Perf\|DOM Client\|oio` | Outstanding IO | none stated | none |
| `readCongestion` | `vSAN Perf\|DOM Client\|readCongestion` | Read Congestions | none stated | none |
| `throughputRead` | `vSAN Perf\|DOM Client\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|DOM Client\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |
| `unmapCongestion` | `vSAN Perf\|DOM Client\|unmapCongestion` | Unmap congestion | none stated | none |
| `writeCongestion` | `vSAN Perf\|DOM Client\|writeCongestion` | Write Congestions | none stated | none |

#### `cluster-domcompmgr` (Python kind `VsanClusterDomcompmgr`): 12 keys per cluster

Cluster-level counterpart of the host DOM Comp Mgr group (component manager I/O, including recovery writes and resync reads per its labels).

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 12 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `congestion` | `vSAN Perf\|DOM Comp Mgr\|congestion` | Congestions | none stated | none |
| `iopsRead` | `vSAN Perf\|DOM Comp Mgr\|iopsRead` | Read IOPS | IO/s | none |
| `iopsRecWrite` | `vSAN Perf\|DOM Comp Mgr\|iopsRecWrite` | Recovery Write IOPS | IO/s | none |
| `iopsResyncRead` | `vSAN Perf\|DOM Comp Mgr\|iopsResyncRead` | Resync Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|DOM Comp Mgr\|iopsWrite` | Write IOPS | IO/s | none |
| `latAvgResyncRead` | `vSAN Perf\|DOM Comp Mgr\|latAvgResyncReadUs` | Resync Read Latency | microseconds | none |
| `latencyAvgRead` | `vSAN Perf\|DOM Comp Mgr\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgRecWrite` | `vSAN Perf\|DOM Comp Mgr\|latencyAvgRecWriteUs` | Recovery Write Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|DOM Comp Mgr\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `oio` | `vSAN Perf\|DOM Comp Mgr\|oio` | Outstanding IO | none stated | none |
| `throughputRecWrite` | `vSAN Perf\|DOM Comp Mgr\|throughputRecWriteBytesPerSec` | Recovery Write Throughput | bytes/s | none |
| `tputResyncRead` | `vSAN Perf\|DOM Comp Mgr\|tputResyncReadBytesPerSec` | Resync Read Throughput | bytes/s | none |

#### `cluster-domowner` (Python kind `VsanClusterDomowner`): 23 keys per cluster

The cluster-wide total of the hosts' DOM Owner role: owner-side I/O for every object in the cluster, whichever host's VMs issued it (the host-level reading is in the v1 REFERENCE "DOM Owner" text), plus the cluster's resync job counters.

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 23 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `avgResyncParallelism` | `vSAN Perf\|DOM Owner\|avgResyncParallelism` | Resync parallelism (average) | none stated | none |
| `congestion` | `vSAN Perf\|DOM Owner\|congestion` | Congestions | none stated | none |
| `iopsRead` | `vSAN Perf\|DOM Owner\|iopsRead` | Read IOPS | IO/s | none |
| `iopsRecWrite` | `vSAN Perf\|DOM Owner\|iopsRecWrite` | Recovery Write IOPS | IO/s | none |
| `iopsResyncRead` | `vSAN Perf\|DOM Owner\|iopsResyncRead` | Resync Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|DOM Owner\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|DOM Owner\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|DOM Owner\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `numCompleteFullResyncOps` | `vSAN Perf\|DOM Owner\|numCompleteFullResyncOps` | Num complete full resync ops | none stated | none |
| `numCompleteResyncOps` | `vSAN Perf\|DOM Owner\|numCompleteResyncOps` | Num complete resync ops | none stated | none |
| `numInflightPriorityResyncJobs` | `vSAN Perf\|DOM Owner\|numInflightPriorityResyncJobs` | Num inflight priority resync jobs | none stated | none |
| `numInflightSharedResyncJobs` | `vSAN Perf\|DOM Owner\|numInflightSharedResyncJobs` | Num inflight shared resync jobs | none stated | none |
| `numPendingDecomResyncJobs` | `vSAN Perf\|DOM Owner\|numPendingDecomResyncJobs` | Num pending decom resync jobs | none stated | none |
| `numPendingFullResyncJobs` | `vSAN Perf\|DOM Owner\|numPendingFullResyncJobs` | Num pending full resync jobs | none stated | none |
| `numPendingResyncJobs` | `vSAN Perf\|DOM Owner\|numPendingResyncJobs` | Num pending resync jobs | none stated | none |
| `numRunningFullResyncJobs` | `vSAN Perf\|DOM Owner\|numRunningFullResyncJobs` | Num running full resync jobs | none stated | none |
| `numRunningResyncJobs` | `vSAN Perf\|DOM Owner\|numRunningResyncJobs` | Num running resync jobs | none stated | none |
| `numSuspendedResyncJobs` | `vSAN Perf\|DOM Owner\|numSuspendedResyncJobs` | Num suspended resync jobs | none stated | none |
| `oio` | `vSAN Perf\|DOM Owner\|oio` | Outstanding IO | none stated | none |
| `readCongestion` | `vSAN Perf\|DOM Owner\|readCongestion` | Read Congestions | none stated | none |
| `tputRead` | `vSAN Perf\|DOM Owner\|tputReadBytesPerSec` | Read Throughput | bytes/s | none |
| `tputWrite` | `vSAN Perf\|DOM Owner\|tputWriteBytesPerSec` | Write Throughput | bytes/s | none |
| `writeCongestion` | `vSAN Perf\|DOM Owner\|writeCongestion` | Write Congestions | none stated | none |

#### `cluster-esa-dedup-domclient-io` (Python kind `VsanClusterEsaDedupDomclientIo`): 24 keys per cluster

ESA global deduplication I/O seen from the DOM client (chunk, engine and hash object reads and writes). Live on the lab's 9.1.1 ESA cluster, although the Python pack carries it only in its provisional `perfsvc_model_extra.py`.

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 24 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `dedupChunkReadCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupChunkReadCount` | Deduplication Chunk Object Read IO Count | none stated | none |
| `dedupChunkWriteCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupChunkWriteCount` | Deduplication Chunk Object Write IO Count | none stated | none |
| `dedupEngineReadCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupEngineReadCount` | Deduplication Read IO Count | none stated | none |
| `dedupEngineWriteCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupEngineWriteCount` | Deduplication Write IO Count | none stated | none |
| `dedupHashReadCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupHashReadCount` | Deduplication Hash Object Read IO Count | none stated | none |
| `dedupHashWriteCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupHashWriteCount` | Deduplication Hash Object Write IO Count | none stated | none |
| `iopsDedupChunkObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupChunkObjRead` | Deduplication Chunk Object Read IOPS | IO/s | none |
| `iopsDedupChunkObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupChunkObjWrite` | Deduplication Chunk Object Write IOPS | IO/s | none |
| `iopsDedupEngineRead` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupEngineRead` | Deduplication Read IOPS | IO/s | none |
| `iopsDedupEngineWrite` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupEngineWrite` | Deduplication Write IOPS | IO/s | none |
| `iopsDedupHashObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupHashObjRead` | Deduplication Hash Object Read IOPS | IO/s | none |
| `iopsDedupHashObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupHashObjWrite` | Deduplication Hash Object Write IOPS | IO/s | none |
| `latencyAvgDedupChunkObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupChunkObjReadUs` | Deduplication Chunk Object Read Latency | microseconds | none |
| `latencyAvgDedupChunkObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupChunkObjWriteUs` | Deduplication Chunk Object Write Latency | microseconds | none |
| `latencyAvgDedupEngineRead` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupEngineReadUs` | Deduplication Read Latency | microseconds | none |
| `latencyAvgDedupEngineWrite` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupEngineWriteUs` | Deduplication Write Latency | microseconds | none |
| `latencyAvgDedupHashObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupHashObjReadUs` | Deduplication Hash Object Read Latency | microseconds | none |
| `latencyAvgDedupHashObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupHashObjWriteUs` | Deduplication Hash Object Write Latency | microseconds | none |
| `tputDedupChunkObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupChunkObjRead` | Deduplication Chunk Object Read Throughput | none stated | none |
| `tputDedupChunkObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupChunkObjWrite` | Deduplication Chunk Object Write Throughput | none stated | none |
| `tputDedupEngineRead` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupEngineRead` | Deduplication Read Throughput | none stated | none |
| `tputDedupEngineWrite` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupEngineWrite` | Deduplication Write Throughput | none stated | none |
| `tputDedupHashObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupHashObjRead` | Deduplication Hash Object Read Throughput | none stated | none |
| `tputDedupHashObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupHashObjWrite` | Deduplication Hash Object Write Throughput | none stated | none |

#### `cluster-rdt-network-latency` (Python kind `VsanClusterRdtLatency`): 9 keys per cluster

Reliable Datagram Transport latency and socket-buffer figures for the cluster.

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 9 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `avgLatency` | `vSAN Perf\|RDT Latency\|avgLatencyUs` | RDT Network VNIC Average Latency | microseconds | none |
| `kaReset` | `vSAN Perf\|RDT Latency\|kaReset` | Keepalive reset | none stated | none |
| `maxLatency` | `vSAN Perf\|RDT Latency\|maxLatencyUs` | RDT Network Cluster Max Latency | microseconds | none |
| `minLatency` | `vSAN Perf\|RDT Latency\|minLatencyUs` | RDT Network Cluster Min Latency | microseconds | none |
| `numReadyDelay` | `vSAN Perf\|RDT Latency\|numReadyDelay` | Num ready delay | none stated | none |
| `rxSbSpaceMin` | `vSAN Perf\|RDT Latency\|rxSbSpaceMinBytes` | RDT Network Socket Min Inbound Bytes | bytes | none |
| `txCtxQMax` | `vSAN Perf\|RDT Latency\|txCtxQMaxBytes` | RDT Network Max Outbound Context Bytes | bytes | none |
| `txQLatAvg` | `vSAN Perf\|RDT Latency\|txQLatAvgUs` | RDT Network Average Outbound Queueing Latency | microseconds | none |
| `txSbSpaceMin` | `vSAN Perf\|RDT Latency\|txSbSpaceMinBytes` | RDT Network Socket Min Outbound Bytes | bytes | none |

#### `cluster-zdom-top-stats` (Python kind `VsanClusterZdomTopStats`): 7 keys per cluster

ESA zDOM top-level I/O for the cluster.

- Lands on: ClusterComputeResource. Instance: none. Lab: 1 entity, 7 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsRead` | `vSAN Perf\|ZDOM Top Stats\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|ZDOM Top Stats\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|ZDOM Top Stats\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|ZDOM Top Stats\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `oio` | `vSAN Perf\|ZDOM Top Stats\|oio` | Outstanding IO | none stated | none |
| `throughputRead` | `vSAN Perf\|ZDOM Top Stats\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|ZDOM Top Stats\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |

#### `vsan-direct-cluster` (Python kind `VsanDirectCluster`): 8 keys per cluster

vSAN Direct. Empty on the lab (not configured); entity id form unobserved.

- Lands on: ClusterComputeResource, or HostSystem (decided per entity at run time, see Identity). Instance: none. Lab: empty on the lab (wildcard echo).

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsDevRead` | `vSAN Perf\|vSAN Direct Cluster\|iopsDevRead` | Physical-layer Read IOPS | IO/s | none |
| `iopsDevWrite` | `vSAN Perf\|vSAN Direct Cluster\|iopsDevWrite` | Physical-layer Write IOPS | IO/s | none |
| `latencyDevRead` | `vSAN Perf\|vSAN Direct Cluster\|latencyDevReadUs` | Physical-layer Read Latency | microseconds | none |
| `latencyDevWrite` | `vSAN Perf\|vSAN Direct Cluster\|latencyDevWriteUs` | Physical-layer Write Latency | microseconds | none |
| `oioDevRead` | `vSAN Perf\|vSAN Direct Cluster\|oioDevRead` | Read Outstanding IO | none stated | none |
| `oioDevWrite` | `vSAN Perf\|vSAN Direct Cluster\|oioDevWrite` | Write Outstanding IO | none stated | none |
| `throughputDevRead` | `vSAN Perf\|vSAN Direct Cluster\|throughputDevReadBytesPerSec` | Physical-layer Read Throughput | bytes/s | none |
| `throughputDevWrite` | `vSAN Perf\|vSAN Direct Cluster\|throughputDevWriteBytesPerSec` | Physical-layer Write Throughput | bytes/s | none |

#### `vsan-file-service` (Python kind `VsanFileService`): 8 keys per cluster

vSAN File Service. Empty on the lab (not enabled); entity id form unobserved.

- Lands on: ClusterComputeResource, or HostSystem (decided per entity at run time). Instance: none. Lab: empty on the lab (wildcard echo).

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `readLatency` | `vSAN Perf\|File Service\|readLatencyUs` | Read latency | microseconds | none |
| `readOpTotal` | `vSAN Perf\|File Service\|readOpTotal` | IOPS for read operations | IO/s | none |
| `readRequested` | `vSAN Perf\|File Service\|readRequestedBytesPerSec` | Requested bytes for read | bytes/s | none |
| `readTransferred` | `vSAN Perf\|File Service\|readTransferredBytesPerSec` | Actual transferred bytes for read | bytes/s | none |
| `writeLatency` | `vSAN Perf\|File Service\|writeLatencyUs` | Write latency | microseconds | none |
| `writeOpTotal` | `vSAN Perf\|File Service\|writeOpTotal` | IOPS for write operations | IO/s | none |
| `writeRequested` | `vSAN Perf\|File Service\|writeRequestedBytesPerSec` | Requested bytes for write | bytes/s | none |
| `writeTransferred` | `vSAN Perf\|File Service\|writeTransferredBytesPerSec` | Actual transferred bytes for write | bytes/s | none |

#### `ioinsight` (Python kind `VsanIoinsight`): 82 keys per cluster

IOInsight capture results. Empty on the lab (no capture running); entity id form unobserved. 82 of the cluster tier's 189 keys.

- Lands on: ClusterComputeResource, or HostSystem (decided per entity at run time). Instance: none. Lab: empty on the lab (wildcard echo).

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `aligned4kRatio` | `vSAN Perf\|IOInsight\|aligned4kRatio` | 4K Aligned IO | none stated | none |
| `aligned4kReadRatio` | `vSAN Perf\|IOInsight\|aligned4kReadRatio` | 4K Aligned Read IO | none stated | none |
| `aligned4kWriteRatio` | `vSAN Perf\|IOInsight\|aligned4kWriteRatio` | 4K Aligned Write IO | none stated | none |
| `iopsRead` | `vSAN Perf\|IOInsight\|iopsRead` | Read IOPS | IO/s | none |
| `iopsTotal` | `vSAN Perf\|IOInsight\|iopsTotal` | Total IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|IOInsight\|iopsWrite` | Write IOPS | IO/s | none |
| `randomRatio` | `vSAN Perf\|IOInsight\|randomRatio` | Random IO | none stated | none |
| `randomReadRatio` | `vSAN Perf\|IOInsight\|randomReadRatio` | Random Read IO | none stated | none |
| `randomWriteRatio` | `vSAN Perf\|IOInsight\|randomWriteRatio` | Random Write IO | none stated | none |
| `readRatio` | `vSAN Perf\|IOInsight\|readRatio` | Read IO | none stated | none |
| `riosz0_4k` | `vSAN Perf\|IOInsight\|riosz0_4k` | ReadSize<4K | none stated | none |
| `riosz128k` | `vSAN Perf\|IOInsight\|riosz128k` | ReadSize=128K | none stated | none |
| `riosz128k_256k` | `vSAN Perf\|IOInsight\|riosz128k_256k` | 128K<ReadSize<256K | none stated | none |
| `riosz16k` | `vSAN Perf\|IOInsight\|riosz16k` | ReadSize=16K | none stated | none |
| `riosz16k_32k` | `vSAN Perf\|IOInsight\|riosz16k_32k` | 16K<ReadSize<32K | none stated | none |
| `riosz1_m` | `vSAN Perf\|IOInsight\|riosz1_m` | ReadSize>1M | none stated | none |
| `riosz1m` | `vSAN Perf\|IOInsight\|riosz1m` | ReadSize=1M | none stated | none |
| `riosz256k` | `vSAN Perf\|IOInsight\|riosz256k` | ReadSize=256K | none stated | none |
| `riosz256k_512k` | `vSAN Perf\|IOInsight\|riosz256k_512k` | 256K<ReadSize<512K | none stated | none |
| `riosz32k` | `vSAN Perf\|IOInsight\|riosz32k` | ReadSize=32K | none stated | none |
| `riosz32k_64k` | `vSAN Perf\|IOInsight\|riosz32k_64k` | 32K<ReadSize<64K | none stated | none |
| `riosz4k` | `vSAN Perf\|IOInsight\|riosz4k` | ReadSize=4K | none stated | none |
| `riosz4k_8k` | `vSAN Perf\|IOInsight\|riosz4k_8k` | 4K<ReadSize<8K | none stated | none |
| `riosz512k` | `vSAN Perf\|IOInsight\|riosz512k` | ReadSize=512K | none stated | none |
| `riosz512k_1m` | `vSAN Perf\|IOInsight\|riosz512k_1m` | 512K<ReadSize<1M | none stated | none |
| `riosz64k` | `vSAN Perf\|IOInsight\|riosz64k` | ReadSize=64K | none stated | none |
| `riosz64k_128k` | `vSAN Perf\|IOInsight\|riosz64k_128k` | 64K<ReadSize<128K | none stated | none |
| `riosz8k` | `vSAN Perf\|IOInsight\|riosz8k` | ReadSize=8K | none stated | none |
| `riosz8k_16k` | `vSAN Perf\|IOInsight\|riosz8k_16k` | 8K<ReadSize<16K | none stated | none |
| `rlat0_1us` | `vSAN Perf\|IOInsight\|rlat0_1us` | 0<ReadLatency<1(us) | none stated | none |
| `rlat100_500us` | `vSAN Perf\|IOInsight\|rlat100_500us` | 100<ReadLatency<500(us) | none stated | none |
| `rlat100_ms` | `vSAN Perf\|IOInsight\|rlat100_ms` | ReadLatency>100(ms) | none stated | none |
| `rlat10_100us` | `vSAN Perf\|IOInsight\|rlat10_100us` | 10<ReadLatency<100(us) | none stated | none |
| `rlat10_25ms` | `vSAN Perf\|IOInsight\|rlat10_25ms` | 10<ReadLatency<25(ms) | none stated | none |
| `rlat1_10us` | `vSAN Perf\|IOInsight\|rlat1_10us` | 1<ReadLatency<10(us) | none stated | none |
| `rlat1_5ms` | `vSAN Perf\|IOInsight\|rlat1_5ms` | 1<ReadLatency<5(ms) | none stated | none |
| `rlat25_50ms` | `vSAN Perf\|IOInsight\|rlat25_50ms` | 25<ReadLatency<50(ms) | none stated | none |
| `rlat500us_1ms` | `vSAN Perf\|IOInsight\|rlat500us_1ms` | 500us<ReadLatency<1ms | none stated | none |
| `rlat50_100ms` | `vSAN Perf\|IOInsight\|rlat50_100ms` | 50<ReadLatency<100(ms) | none stated | none |
| `rlat5_10ms` | `vSAN Perf\|IOInsight\|rlat5_10ms` | 5<ReadLatency<10(ms) | none stated | none |
| `sequentialRatio` | `vSAN Perf\|IOInsight\|sequentialRatio` | Sequential IO | none stated | none |
| `sequentialReadRatio` | `vSAN Perf\|IOInsight\|sequentialReadRatio` | Sequential Read IO | none stated | none |
| `sequentialWriteRatio` | `vSAN Perf\|IOInsight\|sequentialWriteRatio` | Sequential Write IO | none stated | none |
| `throughputRandom` | `vSAN Perf\|IOInsight\|throughputRandomBytesPerSec` | Random Throughput | bytes/s | none |
| `throughputRead` | `vSAN Perf\|IOInsight\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputSequential` | `vSAN Perf\|IOInsight\|throughputSequentialBytesPerSec` | Sequential Throughput | bytes/s | none |
| `throughputTotal` | `vSAN Perf\|IOInsight\|throughputTotalBytesPerSec` | Total Throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|IOInsight\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |
| `unaligned4kRatio` | `vSAN Perf\|IOInsight\|unaligned4kRatio` | 4K Unaligned IO | none stated | none |
| `unaligned4kReadRatio` | `vSAN Perf\|IOInsight\|unaligned4kReadRatio` | 4K Unaligned Read IO | none stated | none |
| `unaligned4kWriteRatio` | `vSAN Perf\|IOInsight\|unaligned4kWriteRatio` | 4K Unaligned Write IO | none stated | none |
| `wiosz0_4k` | `vSAN Perf\|IOInsight\|wiosz0_4k` | WriteSize<4K | none stated | none |
| `wiosz128k` | `vSAN Perf\|IOInsight\|wiosz128k` | WriteSize=128K | none stated | none |
| `wiosz128k_256k` | `vSAN Perf\|IOInsight\|wiosz128k_256k` | 128K<WriteSize<256K | none stated | none |
| `wiosz16k` | `vSAN Perf\|IOInsight\|wiosz16k` | WriteSize=16K | none stated | none |
| `wiosz16k_32k` | `vSAN Perf\|IOInsight\|wiosz16k_32k` | 16K<WriteSize<32K | none stated | none |
| `wiosz1_m` | `vSAN Perf\|IOInsight\|wiosz1_m` | WriteSize>1M | none stated | none |
| `wiosz1m` | `vSAN Perf\|IOInsight\|wiosz1m` | WriteSize=1M | none stated | none |
| `wiosz256k` | `vSAN Perf\|IOInsight\|wiosz256k` | WriteSize=256K | none stated | none |
| `wiosz256k_512k` | `vSAN Perf\|IOInsight\|wiosz256k_512k` | 256K<WriteSize<512K | none stated | none |
| `wiosz32k` | `vSAN Perf\|IOInsight\|wiosz32k` | WriteSize=32K | none stated | none |
| `wiosz32k_64k` | `vSAN Perf\|IOInsight\|wiosz32k_64k` | 32K<WriteSize<64K | none stated | none |
| `wiosz4k` | `vSAN Perf\|IOInsight\|wiosz4k` | WriteSize=4K | none stated | none |
| `wiosz4k_8k` | `vSAN Perf\|IOInsight\|wiosz4k_8k` | 4K<WriteSize<8K | none stated | none |
| `wiosz512k` | `vSAN Perf\|IOInsight\|wiosz512k` | WriteSize=512K | none stated | none |
| `wiosz512k_1m` | `vSAN Perf\|IOInsight\|wiosz512k_1m` | 512K<WriteSize<1M | none stated | none |
| `wiosz64k` | `vSAN Perf\|IOInsight\|wiosz64k` | WriteSize=64K | none stated | none |
| `wiosz64k_128k` | `vSAN Perf\|IOInsight\|wiosz64k_128k` | 64K<WriteSize<128K | none stated | none |
| `wiosz8k` | `vSAN Perf\|IOInsight\|wiosz8k` | WriteSize=8K | none stated | none |
| `wiosz8k_16k` | `vSAN Perf\|IOInsight\|wiosz8k_16k` | 8K<WriteSize<16K | none stated | none |
| `wlat0_1us` | `vSAN Perf\|IOInsight\|wlat0_1us` | 0<WriteLatency<1(us) | none stated | none |
| `wlat100_500us` | `vSAN Perf\|IOInsight\|wlat100_500us` | 100<WriteLatency<500(us) | none stated | none |
| `wlat100_ms` | `vSAN Perf\|IOInsight\|wlat100_ms` | WriteLatency>100(ms) | none stated | none |
| `wlat10_100us` | `vSAN Perf\|IOInsight\|wlat10_100us` | 10<WriteLatency<100(us) | none stated | none |
| `wlat10_25ms` | `vSAN Perf\|IOInsight\|wlat10_25ms` | 10<WriteLatency<25(ms) | none stated | none |
| `wlat1_10us` | `vSAN Perf\|IOInsight\|wlat1_10us` | 1<WriteLatency<10(us) | none stated | none |
| `wlat1_5ms` | `vSAN Perf\|IOInsight\|wlat1_5ms` | 1<WriteLatency<5(ms) | none stated | none |
| `wlat25_50ms` | `vSAN Perf\|IOInsight\|wlat25_50ms` | 25<WriteLatency<50(ms) | none stated | none |
| `wlat500us_1ms` | `vSAN Perf\|IOInsight\|wlat500us_1ms` | 500us<WriteLatency<1ms | none stated | none |
| `wlat50_100ms` | `vSAN Perf\|IOInsight\|wlat50_100ms` | 50<WriteLatency<100(ms) | none stated | none |
| `wlat5_10ms` | `vSAN Perf\|IOInsight\|wlat5_10ms` | 5<WriteLatency<10(ms) | none stated | none |
| `writeRatio` | `vSAN Perf\|IOInsight\|writeRatio` | Write IO | none stated | none |

### Host tier: 13 types, 149 keys (lands on HostSystem)

#### `cmmds-net` (Python kind `VsanCmmdsNet`): 10 keys per host

CMMDS (cluster membership directory) traffic on the host: group and RDT receive/transmit counts and throughput.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 50 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `groupRx` | `vSAN Perf\|CMMDS Network\|groupRx` | Group Inbound | none stated | none |
| `groupRxThroughput` | `vSAN Perf\|CMMDS Network\|groupRxThroughputBytesPerSec` | Group Inbound Throughput | bytes/s | none |
| `groupTxMcast` | `vSAN Perf\|CMMDS Network\|groupTxMcast` | Group Outbound Multicast | none stated | none |
| `groupTxMcastThroughput` | `vSAN Perf\|CMMDS Network\|groupTxMcastThroughputBytesPerSec` | Group Outbound Multicast Throughput | bytes/s | none |
| `groupTxUcast` | `vSAN Perf\|CMMDS Network\|groupTxUcast` | Group Outbound Unicast | none stated | none |
| `groupTxUcastThroughput` | `vSAN Perf\|CMMDS Network\|groupTxUcastThroughputBytesPerSec` | Group Outbound Unicast Throughput | bytes/s | none |
| `rdtRx` | `vSAN Perf\|CMMDS Network\|rdtRx` | Read Inbound | none stated | none |
| `rdtRxThroughput` | `vSAN Perf\|CMMDS Network\|rdtRxThroughputBytesPerSec` | Read Inbound Throughput | bytes/s | none |
| `rdtTx` | `vSAN Perf\|CMMDS Network\|rdtTx` | Read Outbound | none stated | none |
| `rdtTxThroughput` | `vSAN Perf\|CMMDS Network\|rdtTxThroughputBytesPerSec` | Read Outbound Throughput | bytes/s | none |

#### `vsan-cpu` (Python kind `VsanCpu`): 7 keys per host

CPU used by vSAN worlds on the host.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 35 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `avgRunPct` | `vSAN Perf\|CPU\|avgRunPct` | Run percent (average) | percent | none |
| `avgUsedPct` | `vSAN Perf\|CPU\|avgUsedPct` | Used percent (average) | percent | none |
| `maxRunPct` | `vSAN Perf\|CPU\|maxRunPct` | Run percent (max) | percent | none |
| `maxUsedPct` | `vSAN Perf\|CPU\|maxUsedPct` | Used percent (max) | percent | none |
| `readyPct` | `vSAN Perf\|CPU\|readyPct` | Percentage of Ready CPU Time | percent | none |
| `runPct` | `vSAN Perf\|CPU\|runPct` | Percentage of Running CPU Time | percent | none |
| `usedPct` | `vSAN Perf\|CPU\|usedPct` | Percentage of Used CPU Time | percent | none |

#### `vsan-direct-host` (Python kind `VsanDirectHost`): 8 keys per host

vSAN Direct on the host. Empty on the lab; entity id form unobserved (Python pack models it on `host_uuid`, provisional).

- Lands on: HostSystem. Instance: none (if an observed id carries a second part, it is skipped and counted, see Failure handling). Lab: empty on the lab (wildcard echo).

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsDevRead` | `vSAN Perf\|vSAN Direct\|iopsDevRead` | Physical-layer Read IOPS | IO/s | none |
| `iopsDevWrite` | `vSAN Perf\|vSAN Direct\|iopsDevWrite` | Physical-layer Write IOPS | IO/s | none |
| `latencyDevRead` | `vSAN Perf\|vSAN Direct\|latencyDevReadUs` | Physical-layer Read Latency | microseconds | none |
| `latencyDevWrite` | `vSAN Perf\|vSAN Direct\|latencyDevWriteUs` | Physical-layer Write Latency | microseconds | none |
| `oioDevRead` | `vSAN Perf\|vSAN Direct\|oioDevRead` | Read Outstanding IO | none stated | none |
| `oioDevWrite` | `vSAN Perf\|vSAN Direct\|oioDevWrite` | Write Outstanding IO | none stated | none |
| `throughputDevRead` | `vSAN Perf\|vSAN Direct\|throughputDevReadBytesPerSec` | Physical-layer Read Throughput | bytes/s | none |
| `throughputDevWrite` | `vSAN Perf\|vSAN Direct\|throughputDevWriteBytesPerSec` | Physical-layer Write Throughput | bytes/s | none |

#### `host-domcompmgr` (Python kind `VsanHostDomcompmgr`): 16 keys per host

DOM component manager role on the host: the layer that serves component I/O, including resync reads and recovery writes.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 80 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `componentCongestion` | `vSAN Perf\|DOM Comp Mgr\|componentCongestion` | Component congestion | none stated | none |
| `iopsRead` | `vSAN Perf\|DOM Comp Mgr\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|DOM Comp Mgr\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|DOM Comp Mgr\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|DOM Comp Mgr\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `latencyMaxRead` | `vSAN Perf\|DOM Comp Mgr\|latencyMaxReadUs` | Latency (max, read) | microseconds | none |
| `latencyMaxWrite` | `vSAN Perf\|DOM Comp Mgr\|latencyMaxWriteUs` | Latency (max, write) | microseconds | none |
| `latencyStddevWrite` | `vSAN Perf\|DOM Comp Mgr\|latencyStddevWriteUs` | Latency standard deviation (write) | microseconds | none |
| `namespaceDispatchedCostWrite` | `vSAN Perf\|DOM Comp Mgr\|namespaceDispatchedCostWriteBytesPerSec` | Namespace dispatched cost (write) | bytes/s | none |
| `oio` | `vSAN Perf\|DOM Comp Mgr\|oio` | Outstanding IO | none stated | none |
| `resyncReadCongestion` | `vSAN Perf\|DOM Comp Mgr\|resyncReadCongestion` | Resync read congestion | none stated | none |
| `sharedCongestion` | `vSAN Perf\|DOM Comp Mgr\|sharedCongestion` | Shared congestion | none stated | none |
| `throughputRead` | `vSAN Perf\|DOM Comp Mgr\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|DOM Comp Mgr\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |
| `vmdiskDispatchedCostWrite` | `vSAN Perf\|DOM Comp Mgr\|vmdiskDispatchedCostWriteBytesPerSec` | VM disk dispatched cost (write) | bytes/s | none |
| `vmdiskQueueDepthWrite` | `vSAN Perf\|DOM Comp Mgr\|vmdiskQueueDepthWrite` | VM disk queue depth (write) | none stated | none |

#### `host-esa-dedup-domclient-io` (Python kind `VsanHostEsaDedupDomclientIo`): 24 keys per host

ESA global deduplication I/O seen from this host's DOM client.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 120 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `dedupChunkReadCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupChunkReadCount` | Deduplication Chunk Object Read IO Count | none stated | none |
| `dedupChunkWriteCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupChunkWriteCount` | Deduplication Chunk Object Write IO Count | none stated | none |
| `dedupEngineReadCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupEngineReadCount` | Deduplication Read IO Count | none stated | none |
| `dedupEngineWriteCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupEngineWriteCount` | Deduplication Write IO Count | none stated | none |
| `dedupHashReadCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupHashReadCount` | Deduplication Hash Object Read IO Count | none stated | none |
| `dedupHashWriteCount` | `vSAN Perf\|ESA Dedup DOM Client\|dedupHashWriteCount` | Deduplication Hash Object Write IO Count | none stated | none |
| `iopsDedupChunkObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupChunkObjRead` | Deduplication Chunk Object Read IOPS | IO/s | none |
| `iopsDedupChunkObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupChunkObjWrite` | Deduplication Chunk Object Write IOPS | IO/s | none |
| `iopsDedupEngineRead` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupEngineRead` | Deduplication Read IOPS | IO/s | none |
| `iopsDedupEngineWrite` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupEngineWrite` | Deduplication Write IOPS | IO/s | none |
| `iopsDedupHashObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupHashObjRead` | Deduplication Hash Object Read IOPS | IO/s | none |
| `iopsDedupHashObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|iopsDedupHashObjWrite` | Deduplication Hash Object Write IOPS | IO/s | none |
| `latencyAvgDedupChunkObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupChunkObjReadUs` | Deduplication Chunk Object Read Latency | microseconds | none |
| `latencyAvgDedupChunkObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupChunkObjWriteUs` | Deduplication Chunk Object Write Latency | microseconds | none |
| `latencyAvgDedupEngineRead` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupEngineReadUs` | Deduplication Read Latency | microseconds | none |
| `latencyAvgDedupEngineWrite` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupEngineWriteUs` | Deduplication Write Latency | microseconds | none |
| `latencyAvgDedupHashObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupHashObjReadUs` | Deduplication Hash Object Read Latency | microseconds | none |
| `latencyAvgDedupHashObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|latencyAvgDedupHashObjWriteUs` | Deduplication Hash Object Write Latency | microseconds | none |
| `tputDedupChunkObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupChunkObjRead` | Deduplication Chunk Object Read Throughput | none stated | none |
| `tputDedupChunkObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupChunkObjWrite` | Deduplication Chunk Object Write Throughput | none stated | none |
| `tputDedupEngineRead` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupEngineRead` | Deduplication Read Throughput | none stated | none |
| `tputDedupEngineWrite` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupEngineWrite` | Deduplication Write Throughput | none stated | none |
| `tputDedupHashObjRead` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupHashObjRead` | Deduplication Hash Object Read Throughput | none stated | none |
| `tputDedupHashObjWrite` | `vSAN Perf\|ESA Dedup DOM Client\|tputDedupHashObjWrite` | Deduplication Hash Object Write Throughput | none stated | none |

#### `vsan-host-net` (Python kind `VsanHostNet`): 8 keys per host

vSAN network traffic of the host as a whole (all vSAN vmknics).

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 40 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `portRxDrops` | `vSAN Perf\|Host Network\|portRxDropsPct` | Inbound Packet Drop Rate of vSwitch Port | percent | per-mille / 10 |
| `portTxDrops` | `vSAN Perf\|Host Network\|portTxDropsPct` | Outbound Packet Drop Rate of vSwitch Port | percent | per-mille / 10 |
| `rxPackets` | `vSAN Perf\|Host Network\|rxPackets` | Inbound Packets Per Second | none stated | none |
| `rxPacketsLossRate` | `vSAN Perf\|Host Network\|rxPacketsLossRatePct` | Inbound Packet Discard Rate | percent | per-mille / 10 |
| `rxThroughput` | `vSAN Perf\|Host Network\|rxThroughputBytesPerSec` | Throughput Inbound | bytes/s | none |
| `txPackets` | `vSAN Perf\|Host Network\|txPackets` | Outbound Packets Per Second | none stated | none |
| `txPacketsLossRate` | `vSAN Perf\|Host Network\|txPacketsLossRatePct` | Outbound Packet Discard Rate | percent | per-mille / 10 |
| `txThroughput` | `vSAN Perf\|Host Network\|txThroughputBytesPerSec` | Throughput Outbound | bytes/s | none |

#### `host-zdom-top-stats` (Python kind `VsanHostZdomTopStats`): 11 keys per host

ESA zDOM top-level I/O on the host.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 55 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsRead` | `vSAN Perf\|ZDOM Top Stats\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|ZDOM Top Stats\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|ZDOM Top Stats\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|ZDOM Top Stats\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `oio` | `vSAN Perf\|ZDOM Top Stats\|oio` | Outstanding IO | none stated | none |
| `oioWrite` | `vSAN Perf\|ZDOM Top Stats\|oioWrite` | Outstanding IO (write) | none stated | none |
| `readLatencyMaxUs` | `vSAN Perf\|ZDOM Top Stats\|readLatencyMaxUs` | Read latency max us | microseconds | none |
| `throughputRead` | `vSAN Perf\|ZDOM Top Stats\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|ZDOM Top Stats\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |
| `unmapLatencyMaxUs` | `vSAN Perf\|ZDOM Top Stats\|unmapLatencyMaxUs` | Unmap latency max us | microseconds | none |
| `writeLatencyMaxUs` | `vSAN Perf\|ZDOM Top Stats\|writeLatencyMaxUs` | Write latency max us | microseconds | none |

#### `vsan-memory` (Python kind `VsanMemory`): 12 keys per host

Memory reserved and consumed by the vSAN kernel modules and daemons on the host.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 60 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `clomdConsumedSize` | `vSAN Perf\|Memory\|clomdConsumedSizeBytes` | Clomd consumed size | bytes | none |
| `clomdReservedSize` | `vSAN Perf\|Memory\|clomdReservedSizeBytes` | Clomd reserved size | bytes | none |
| `cmmdsdConsumedSize` | `vSAN Perf\|Memory\|cmmdsdConsumedSizeBytes` | Cmmdsd consumed size | bytes | none |
| `cmmdsdReservedSize` | `vSAN Perf\|Memory\|cmmdsdReservedSizeBytes` | Cmmdsd reserved size | bytes | none |
| `epdConsumedSize` | `vSAN Perf\|Memory\|epdConsumedSizeBytes` | Epd consumed size | bytes | none |
| `kernelConsumedSize` | `vSAN Perf\|Memory\|kernelConsumedSize` | Kernel consumed size | none stated | none |
| `kernelReservedSize` | `vSAN Perf\|Memory\|kernelReservedSizeBytes` | Kernel Reserved Memory Size | bytes | none |
| `osfsdConsumedSize` | `vSAN Perf\|Memory\|osfsdConsumedSizeBytes` | Osfsd consumed size | bytes | none |
| `uwConsumedSize` | `vSAN Perf\|Memory\|uwConsumedSizeBytes` | Uw consumed size | bytes | none |
| `uwReservedSize` | `vSAN Perf\|Memory\|uwReservedSizeBytes` | User world Reserved Memory Size | bytes | none |
| `vsandevicemonitordConsumedSize` | `vSAN Perf\|Memory\|vsandevicemonitordConsumedSizeBytes` | Vsandevicemonitord consumed size | bytes | none |
| `vsanmgmtdConsumedSize` | `vSAN Perf\|Memory\|vsanmgmtdConsumedSizeBytes` | Vsanmgmtd consumed size | bytes | none |

#### `rdt-network-latency` (Python kind `VsanRdtLatency`): 11 keys per host

RDT latency and socket-buffer figures for the host.

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 55 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `avgLatency` | `vSAN Perf\|RDT Latency\|avgLatencyUs` | RDT Network VNIC Average Latency | microseconds | none |
| `kaReset` | `vSAN Perf\|RDT Latency\|kaReset` | Keepalive reset | none stated | none |
| `maxLatency` | `vSAN Perf\|RDT Latency\|maxLatencyUs` | RDT Network Cluster Max Latency | microseconds | none |
| `minLatency` | `vSAN Perf\|RDT Latency\|minLatencyUs` | RDT Network Cluster Min Latency | microseconds | none |
| `numReadyDelay` | `vSAN Perf\|RDT Latency\|numReadyDelay` | Num ready delay | none stated | none |
| `rxSbSpaceMax` | `vSAN Perf\|RDT Latency\|rxSbSpaceMaxBytes` | RDT Network Socket Max Inbound Bytes | bytes | none |
| `rxSbSpaceMin` | `vSAN Perf\|RDT Latency\|rxSbSpaceMinBytes` | RDT Network Socket Min Inbound Bytes | bytes | none |
| `txCtxQMax` | `vSAN Perf\|RDT Latency\|txCtxQMaxBytes` | RDT Network Max Outbound Context Bytes | bytes | none |
| `txQLatAvg` | `vSAN Perf\|RDT Latency\|txQLatAvgUs` | RDT Network Average Outbound Queueing Latency | microseconds | none |
| `txQLatMax` | `vSAN Perf\|RDT Latency\|txQLatMaxUs` | RDT Network Max Outbound Queueing Latency | microseconds | none |
| `txSbSpaceMin` | `vSAN Perf\|RDT Latency\|txSbSpaceMinBytes` | RDT Network Socket Min Outbound Bytes | bytes | none |

#### `vsan-tcpip-stats` (Python kind `VsanTcpIp`): 12 keys per netstack

TCP/IP stack statistics for the stack carrying vSAN, one instance per stack.

- Lands on: HostSystem. Instance: `<stack>` = the netstack name from the entity id (`defaultTcpipStack` on the lab). Lab: 5 entities, 60 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `tcpErrs` | `vSAN Perf\|TCP/IP:<stack>\|tcpErrsPct` | TCP Errors | percent | per-mille / 10 |
| `tcpHalfopenDropRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpHalfopenDropRatePct` | Half Open Drop Rate | percent | per-mille / 10 |
| `tcpRcvdupackRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpRcvdupackRatePct` | Received Duplicate Acknowledge Rate | percent | per-mille / 10 |
| `tcpRcvduppackRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpRcvduppackRatePct` | Received Duplicate Packets Rate | percent | per-mille / 10 |
| `tcpRcvoopackRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpRcvoopackRatePct` | Received Out-of-order Packets Rate | percent | per-mille / 10 |
| `tcpRxErrRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpRxErrRate` | TCP RX errors (rate) | none stated | none |
| `tcpSackRcvBlocksRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpSackRcvBlocksRatePct` | Sack Received Blocks Rate | percent | per-mille / 10 |
| `tcpSackRexmitsRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpSackRexmitsRatePct` | Sack Rexmits Rate | percent | per-mille / 10 |
| `tcpSackSendBlocksRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpSackSendBlocksRatePct` | Sack Send Blocks Rate | percent | per-mille / 10 |
| `tcpSndZeroWin` | `vSAN Perf\|TCP/IP:<stack>\|tcpSndZeroWin` | TCP Send Zero Window | none stated | none |
| `tcpTimeoutDropRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpTimeoutDropRatePct` | Timeout Drop Rate | percent | per-mille / 10 |
| `tcpTxRexmitRate` | `vSAN Perf\|TCP/IP:<stack>\|tcpTxRexmitRate` | TCP TX retransmit (rate) | none stated | none |

#### `vsan-vnic-net` (Python kind `VsanVnic`): 10 keys per vSAN vmknic

vSAN traffic per vSAN vmknic.

- Lands on: HostSystem. Instance: `<vmk>` = the vmknic name (`vmk2` on the lab); the stack part of the id is dropped from the key because a vmknic name is unique on its host (ESXi naming, inferred; the lab has one stack). Lab: 5 entities, 50 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `portRxDrops` | `vSAN Perf\|vNIC:<vmk>\|portRxDropsPct` | Inbound Packet Drop Rate of vSwitch Port | percent | per-mille / 10 |
| `portRxpkts` | `vSAN Perf\|vNIC:<vmk>\|portRxpkts` | Port RX packets | none stated | none |
| `portTxDrops` | `vSAN Perf\|vNIC:<vmk>\|portTxDropsPct` | Outbound Packet Drop Rate of vSwitch Port | percent | per-mille / 10 |
| `portTxpkts` | `vSAN Perf\|vNIC:<vmk>\|portTxpkts` | Port TX packets | none stated | none |
| `rxPackets` | `vSAN Perf\|vNIC:<vmk>\|rxPackets` | Inbound Packets Per Second | none stated | none |
| `rxPacketsLossRate` | `vSAN Perf\|vNIC:<vmk>\|rxPacketsLossRatePct` | Inbound Packet Discard Rate | percent | per-mille / 10 |
| `rxThroughput` | `vSAN Perf\|vNIC:<vmk>\|rxThroughputBytesPerSec` | Throughput Inbound | bytes/s | none |
| `txPackets` | `vSAN Perf\|vNIC:<vmk>\|txPackets` | Outbound Packets Per Second | none stated | none |
| `txPacketsLossRate` | `vSAN Perf\|vNIC:<vmk>\|txPacketsLossRatePct` | Outbound Packet Discard Rate | percent | per-mille / 10 |
| `txThroughput` | `vSAN Perf\|vNIC:<vmk>\|txThroughputBytesPerSec` | Throughput Outbound | bytes/s | none |

#### `vnic-rdt-network-latency` (Python kind `VsanVnicRdtLatency`): 10 keys per vSAN vmknic

RDT latency per vSAN vmknic.

- Lands on: HostSystem. Instance: `<vmk>` = the vmknic name. Lab: 5 entities, 50 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `avgLatency` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|avgLatencyUs` | RDT Network VNIC Average Latency | microseconds | none |
| `kaReset` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|kaReset` | Keepalive reset | none stated | none |
| `maxLatency` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|maxLatencyUs` | RDT Network Cluster Max Latency | microseconds | none |
| `minLatency` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|minLatencyUs` | RDT Network Cluster Min Latency | microseconds | none |
| `numReadyDelay` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|numReadyDelay` | Num ready delay | none stated | none |
| `rxSbSpaceMin` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|rxSbSpaceMinBytes` | RDT Network Socket Min Inbound Bytes | bytes | none |
| `txCtxQMax` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|txCtxQMaxBytes` | RDT Network Max Outbound Context Bytes | bytes | none |
| `txQLatAvg` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|txQLatAvgUs` | RDT Network Average Outbound Queueing Latency | microseconds | none |
| `txQLatMax` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|txQLatMaxUs` | RDT Network Max Outbound Queueing Latency | microseconds | none |
| `txSbSpaceMin` | `vSAN Perf\|vNIC RDT Latency:<vmk>\|txSbSpaceMinBytes` | RDT Network Socket Min Outbound Bytes | bytes | none |

#### `zdom-vtx` (Python kind `VsanZdomVtx`): 10 keys per host

ESA zDOM transaction layer (cache references, bank flushes, transaction latency).

- Lands on: HostSystem. Instance: none. Lab: 5 entities, 50 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `checkpointWorkerWakeupMs` | `vSAN Perf\|ZDOM VTX\|checkpointWorkerWakeupMs` | Checkpoint worker wakeup ms | milliseconds | none |
| `latAvgTotalOpIO` | `vSAN Perf\|ZDOM VTX\|latAvgTotalOpIOUs` | Latency avg total op IO | microseconds | none |
| `latAvgTxnBank` | `vSAN Perf\|ZDOM VTX\|latAvgTxnBankUs` | Latency avg transaction bank | microseconds | none |
| `maxDiscUsedPct` | `vSAN Perf\|ZDOM VTX\|maxDiscUsedPct` | Disc used percent (max) | percent | none |
| `rateBankFlushTotalCacheRef` | `vSAN Perf\|ZDOM VTX\|rateBankFlushTotalCacheRef` | Bank flush total cache ref (rate) | none stated | none |
| `rateSegCleaningCtxDataTotalCacheRef` | `vSAN Perf\|ZDOM VTX\|rateSegCleaningCtxDataTotalCacheRef` | Seg cleaning context data total cache ref (rate) | none stated | none |
| `rateTotalCacheRef` | `vSAN Perf\|ZDOM VTX\|rateTotalCacheRef` | Cache ref (rate, total) | none stated | none |
| `rateTxnLookupCacheRef` | `vSAN Perf\|ZDOM VTX\|rateTxnLookupCacheRef` | Transaction lookup cache ref (rate) | none stated | none |
| `rateTxnPrefetchTotalCacheRef` | `vSAN Perf\|ZDOM VTX\|rateTxnPrefetchTotalCacheRef` | Transaction prefetch total cache ref (rate) | none stated | none |
| `rateTxnReadWrite` | `vSAN Perf\|ZDOM VTX\|rateTxnReadWrite` | Transaction (read, write, rate) | none stated | none |

### Disk tier: 4 types, 31 keys (lands on HostSystem, instanced by disk uuid)

#### `cache-disk` (Python kind `VsanCacheDisk`): 8 keys per disk

OSA cache-tier disk. Empty on ESA; learned-skipped after three empty cycles. 8 of 8 names match built-in OSA disk keys (INV §3, name match only).

- Lands on: HostSystem (the host the disk map read it from). Instance: `<disk uuid>` = the vSAN disk uuid from the entity id. Lab: empty on the lab (wildcard echo).

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsDevRead` | `vSAN Perf\|Cache Disk:<disk uuid>\|iopsDevRead` | Physical-layer Read IOPS | IO/s | none; name matches built-in `vSAN\|Performance\|iopsDevRead` |
| `iopsDevWrite` | `vSAN Perf\|Cache Disk:<disk uuid>\|iopsDevWrite` | Physical-layer Write IOPS | IO/s | none; name matches built-in `vSAN\|Performance\|iopsDevWrite` |
| `latencyDevDAvg` | `vSAN Perf\|Cache Disk:<disk uuid>\|latencyDevDAvgUs` | Device Average Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevDAvg` |
| `latencyDevGAvg` | `vSAN Perf\|Cache Disk:<disk uuid>\|latencyDevGAvgUs` | Guest Average Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevGAvg` |
| `latencyDevRead` | `vSAN Perf\|Cache Disk:<disk uuid>\|latencyDevReadUs` | Physical-layer Read Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevRead` |
| `latencyDevWrite` | `vSAN Perf\|Cache Disk:<disk uuid>\|latencyDevWriteUs` | Physical-layer Write Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevWrite` |
| `throughputDevRead` | `vSAN Perf\|Cache Disk:<disk uuid>\|throughputDevReadBytesPerSec` | Physical-layer Read Throughput | bytes/s | none; name matches built-in `vSAN\|Performance\|throughputDevRead` |
| `throughputDevWrite` | `vSAN Perf\|Cache Disk:<disk uuid>\|throughputDevWriteBytesPerSec` | Physical-layer Write Throughput | bytes/s | none; name matches built-in `vSAN\|Performance\|throughputDevWrite` |

#### `capacity-disk` (Python kind `VsanCapacityDisk`): 13 keys per disk

OSA capacity-tier disk. Empty on ESA; learned-skipped. 8 of 13 names match built-in keys (INV §3).

- Lands on: HostSystem. Instance: `<disk uuid>`. Lab: empty on the lab (wildcard echo).

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `deleteCongestion` | `vSAN Perf\|Capacity Disk:<disk uuid>\|deleteCongestion` | vSAN Layer Delete Congestion | bytes | none; Python unit says bytes; left unsuffixed (Key risks R3b) |
| `iopsDevRead` | `vSAN Perf\|Capacity Disk:<disk uuid>\|iopsDevRead` | Physical-layer Read IOPS | IO/s | none; name matches built-in `vSAN\|Performance\|iopsDevRead` |
| `iopsDevWrite` | `vSAN Perf\|Capacity Disk:<disk uuid>\|iopsDevWrite` | Physical-layer Write IOPS | IO/s | none; name matches built-in `vSAN\|Performance\|iopsDevWrite` |
| `iopsRead` | `vSAN Perf\|Capacity Disk:<disk uuid>\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|Capacity Disk:<disk uuid>\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyDevDAvg` | `vSAN Perf\|Capacity Disk:<disk uuid>\|latencyDevDAvgUs` | Device Average Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevDAvg` |
| `latencyDevGAvg` | `vSAN Perf\|Capacity Disk:<disk uuid>\|latencyDevGAvgUs` | Guest Average Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevGAvg` |
| `latencyDevRead` | `vSAN Perf\|Capacity Disk:<disk uuid>\|latencyDevReadUs` | Physical-layer Read Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevRead` |
| `latencyDevWrite` | `vSAN Perf\|Capacity Disk:<disk uuid>\|latencyDevWriteUs` | Physical-layer Write Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevWrite` |
| `latencyRead` | `vSAN Perf\|Capacity Disk:<disk uuid>\|latencyReadUs` | vSAN Layer Read Latency | microseconds | none |
| `latencyWrite` | `vSAN Perf\|Capacity Disk:<disk uuid>\|latencyWriteUs` | vSAN Layer Write Latency | microseconds | none |
| `throughputDevRead` | `vSAN Perf\|Capacity Disk:<disk uuid>\|throughputDevReadBytesPerSec` | Physical-layer Read Throughput | bytes/s | none; name matches built-in `vSAN\|Performance\|throughputDevRead` |
| `throughputDevWrite` | `vSAN Perf\|Capacity Disk:<disk uuid>\|throughputDevWriteBytesPerSec` | Physical-layer Write Throughput | bytes/s | none; name matches built-in `vSAN\|Performance\|throughputDevWrite` |

#### `vsan-esa-disk-layer` (Python kind `VsanEsaDiskLayer`): 5 keys per disk

vSAN-layer I/O per ESA disk. 4 of 5 names match built-in `Vsan2Disk` `vSAN|Performance|*` keys (INV §3).

- Lands on: HostSystem. Instance: `<disk uuid>`. Lab: 5 entities, 25 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `avgLatReadCapacity` | `vSAN Perf\|ESA Disk Layer:<disk uuid>\|avgLatReadCapacity` | vSAN Layer Average Read Latency of vSAN ESA Disk | none stated | none; name matches built-in `vSAN\|Performance\|avgLatReadCapacity` |
| `avgLatWriteCapacity` | `vSAN Perf\|ESA Disk Layer:<disk uuid>\|avgLatWriteCapacity` | vSAN Layer Average Write Latency of vSAN ESA Disk | none stated | none; name matches built-in `vSAN\|Performance\|avgLatWriteCapacity` |
| `avgLatWritePerf` | `vSAN Perf\|ESA Disk Layer:<disk uuid>\|avgLatWritePerf` | Latency write perf (average) | none stated | none |
| `iopsReadCapacity` | `vSAN Perf\|ESA Disk Layer:<disk uuid>\|iopsReadCapacity` | vSAN Layer Read IOPS of vSAN ESA Disk | IO/s | none; name matches built-in `vSAN\|Performance\|iopsReadCapacity` |
| `iopsWriteCapacity` | `vSAN Perf\|ESA Disk Layer:<disk uuid>\|iopsWriteCapacity` | vSAN Layer Write IOPS of vSAN ESA Disk | IO/s | none; name matches built-in `vSAN\|Performance\|iopsWriteCapacity` |

#### `vsan-esa-disk-scsifw` (Python kind `VsanEsaDiskScsifw`): 5 keys per disk

Device (SCSI framework) latency per ESA disk. 4 of 5 names match built-in `Vsan2Disk` keys (INV §3).

- Lands on: HostSystem. Instance: `<disk uuid>`. Lab: 5 entities, 25 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `latencyDevDAvg` | `vSAN Perf\|ESA Disk SCSI:<disk uuid>\|latencyDevDAvgUs` | Device Average Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevDAvg` |
| `latencyDevGAvg` | `vSAN Perf\|ESA Disk SCSI:<disk uuid>\|latencyDevGAvgUs` | Guest Average Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevGAvg` |
| `latencyDevKAvg` | `vSAN Perf\|ESA Disk SCSI:<disk uuid>\|latencyDevKAvgUs` | Latency dev k (average) | microseconds | none |
| `latencyDevRead` | `vSAN Perf\|ESA Disk SCSI:<disk uuid>\|latencyDevReadUs` | Physical-layer Read Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevRead` |
| `latencyDevWrite` | `vSAN Perf\|ESA Disk SCSI:<disk uuid>\|latencyDevWriteUs` | Physical-layer Write Latency | microseconds | none; name matches built-in `vSAN\|Performance\|latencyDevWrite` |

### VM tier: 3 types, 21 keys (lands on VirtualMachine)

#### `virtual-machine` (Python kind `VsanVirtualMachine`): 6 keys per VM

vSAN I/O per VM, as the VM's DOM client saw it.

- Lands on: VirtualMachine. Instance: none. Lab: 30 entities, 180 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsRead` | `vSAN Perf\|VM\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|VM\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyRead` | `vSAN Perf\|VM\|latencyReadUs` | vSAN Layer Read Latency | microseconds | none |
| `latencyWrite` | `vSAN Perf\|VM\|latencyWriteUs` | vSAN Layer Write Latency | microseconds | none |
| `throughputRead` | `vSAN Perf\|VM\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|VM\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |

#### `virtual-disk` (Python kind `VsanVirtualDisk`): 7 keys per VMDK

Per-VMDK normalized IOPS and IOPS limit. The 4 `NIOPSRead*`/`NIOPSWrite*` labels were `None` for all 148 entities on the lab (map); they stay requested and documented, and push nothing while `None`.

- Lands on: VirtualMachine. Instance: `<busN:M>` = the VMDK's bus position from the device read (`scsi0:0`; derivation in §VirtualMachine; `deviceInfo.label` is the alternative, Q5). Lab: 148 entities, 1036 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `NIOPS` | `vSAN Perf\|Virtual Disk:<busN:M>\|NIOPS` | Normalized IOPS | IO/s | none |
| `NIOPSDelayed` | `vSAN Perf\|Virtual Disk:<busN:M>\|NIOPSDelayed` | Delayed Normalized IOPS | IO/s | none |
| `NIOPSRead` | `vSAN Perf\|Virtual Disk:<busN:M>\|NIOPSRead` | Niops (read) | IO/s | none; all `None` on the lab (148/148); requested, nothing pushed |
| `NIOPSReadDelayed` | `vSAN Perf\|Virtual Disk:<busN:M>\|NIOPSReadDelayed` | Niops read delayed | IO/s | none; all `None` on the lab (148/148); requested, nothing pushed |
| `NIOPSWrite` | `vSAN Perf\|Virtual Disk:<busN:M>\|NIOPSWrite` | Niops (write) | IO/s | none; all `None` on the lab (148/148); requested, nothing pushed |
| `NIOPSWriteDelayed` | `vSAN Perf\|Virtual Disk:<busN:M>\|NIOPSWriteDelayed` | Niops write delayed | IO/s | none; all `None` on the lab (148/148); requested, nothing pushed |
| `iopsLimit` | `vSAN Perf\|Virtual Disk:<busN:M>\|iopsLimit` | Normalized IOPS Limit | IO/s | none |

#### `vscsi` (Python kind `VsanVscsi`): 8 keys per virtual SCSI device

I/O per virtual SCSI device.

- Lands on: VirtualMachine. Instance: `<scsiN:M>` = the device part of the entity id (`scsi0:0`), same shape as the vCenter adapter's own `virtualDisk:scsi0:0`. Lab: 148 entities, 1184 series.

| vSAN label | Ops stat key | Python label | Unit | Transform |
|---|---|---|---|---|
| `iopsRead` | `vSAN Perf\|vSCSI:<scsiN:M>\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|vSCSI:<scsiN:M>\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyRead` | `vSAN Perf\|vSCSI:<scsiN:M>\|latencyReadUs` | vSAN Layer Read Latency | microseconds | none |
| `latencyWrite` | `vSAN Perf\|vSCSI:<scsiN:M>\|latencyWriteUs` | vSAN Layer Write Latency | microseconds | none |
| `readCount` | `vSAN Perf\|vSCSI:<scsiN:M>\|readCount` | Read count | none stated | none |
| `throughputRead` | `vSAN Perf\|vSCSI:<scsiN:M>\|throughputReadBytesPerSec` | Read throughput | bytes/s | none |
| `throughputWrite` | `vSAN Perf\|vSCSI:<scsiN:M>\|throughputWriteBytesPerSec` | Write throughput | bytes/s | none |
| `writeCount` | `vSAN Perf\|vSCSI:<scsiN:M>\|writeCount` | Write count | none stated | none |

---

## Key tree alignment (open decision, Q1)

The question (B2): keep `vSAN Perf|<group>[:<instance>]|<metric><UnitSuffix>`,
or align with the vsanhostmetrics 2.0.0 tree
`cptvsan|<group>[:<instance>]|<metric>` (Scott's SCOTTSREADME tree).

**The 2.0.0 group names could not be filled in.** The brief points at the
Python pack's `app/metric_tree.py`. It is not in the fork clone: absent from
`content/sdk-adapters/vsanhostmetrics/app/` on the checked-out branch
(`tuneup/upstream-2026-10`) and from every local branch, the string
`cptvsan` occurs in no tracked file of the clone, and neither
`nickfirefoot/vsanhostmetrics` (`main`, `agent/beta-vsan-host-metrics`) nor
`sentania-labs/vsanhostmetrics` (6 branches) has a `metric_tree.py` or a
SCOTTSREADME on GitHub (read-only listing, 2026-11-06). The one factory
mention is `knowledge/context/managed_paks.md` §vsanperf ("key-tree alignment
with the vsanhostmetrics `cptvsan|` grammar"). **The mapping needs that file**;
the last column below is left for it, and the rest of the table is what a
switch would edit.

What a switch changes, mechanically: `EntityType.ROOT` (`vSAN Perf` to
`cptvsan`), the group column per type, and possibly the leaf rule (whether
the 2.0.0 tree keeps unit suffixes is unknown without the file). Instance
segments and the identity rules do not change. Build 1's three rows are
included because a switch only makes sense for all 33 types at once; that
renames the 61 released keys, which contradicts B1 and orphans the lab's
existing `vSAN Perf|` history on HostSystem (no per-key delete, V1). It is
safe only before a customer installs `v1.0.0.9` or later.

| Tier | Entity type | Python kind | PY `KIND_SUFFIX` | Group, current grammar (this design) | Instance | 2.0.0 `cptvsan\|` group |
|---|---|---|---|---|---|---|
| core | `host-domowner` | VsanHostDomowner | DOM Owner | `DOM Owner` | none | needs `app/metric_tree.py` |
| core | `host-domclient` | VsanHostDomclient | DOM Client | `DOM Client` | none | needs `app/metric_tree.py` |
| core | `vsan-pnic-net` | VsanPnic | pNIC | `pNIC` | `<vmnic>` | needs `app/metric_tree.py` |
| cluster | `vsan-cluster-capacity` | VsanClusterCapacity | Capacity | `Capacity` | none | needs `app/metric_tree.py` |
| cluster | `cluster-domclient` | VsanClusterDomclient | DOM Client | `DOM Client` | none | needs `app/metric_tree.py` |
| cluster | `cluster-domcompmgr` | VsanClusterDomcompmgr | DOM Comp Mgr | `DOM Comp Mgr` | none | needs `app/metric_tree.py` |
| cluster | `cluster-domowner` | VsanClusterDomowner | DOM Owner | `DOM Owner` | none | needs `app/metric_tree.py` |
| cluster | `cluster-esa-dedup-domclient-io` | VsanClusterEsaDedupDomclientIo | (none) | `ESA Dedup DOM Client` | none | needs `app/metric_tree.py` |
| cluster | `cluster-rdt-network-latency` | VsanClusterRdtLatency | RDT Latency | `RDT Latency` | none | needs `app/metric_tree.py` |
| cluster | `cluster-zdom-top-stats` | VsanClusterZdomTopStats | ZDOM Top Stats | `ZDOM Top Stats` | none | needs `app/metric_tree.py` |
| cluster | `vsan-direct-cluster` | VsanDirectCluster | (none) | `vSAN Direct Cluster` | none | needs `app/metric_tree.py` |
| cluster | `vsan-file-service` | VsanFileService | (none) | `File Service` | none | needs `app/metric_tree.py` |
| cluster | `ioinsight` | VsanIoinsight | (none) | `IOInsight` | none | needs `app/metric_tree.py` |
| host | `cmmds-net` | VsanCmmdsNet | CMMDS Network | `CMMDS Network` | none | needs `app/metric_tree.py` |
| host | `vsan-cpu` | VsanCpu | CPU | `CPU` | none | needs `app/metric_tree.py` |
| host | `vsan-direct-host` | VsanDirectHost | (none) | `vSAN Direct` | none | needs `app/metric_tree.py` |
| host | `host-domcompmgr` | VsanHostDomcompmgr | DOM Comp Mgr | `DOM Comp Mgr` | none | needs `app/metric_tree.py` |
| host | `host-esa-dedup-domclient-io` | VsanHostEsaDedupDomclientIo | (none) | `ESA Dedup DOM Client` | none | needs `app/metric_tree.py` |
| host | `vsan-host-net` | VsanHostNet | Host Network | `Host Network` | none | needs `app/metric_tree.py` |
| host | `host-zdom-top-stats` | VsanHostZdomTopStats | ZDOM Top Stats | `ZDOM Top Stats` | none | needs `app/metric_tree.py` |
| host | `vsan-memory` | VsanMemory | Memory | `Memory` | none | needs `app/metric_tree.py` |
| host | `rdt-network-latency` | VsanRdtLatency | RDT Latency | `RDT Latency` | none | needs `app/metric_tree.py` |
| host | `vsan-tcpip-stats` | VsanTcpIp | TCP/IP | `TCP/IP` | `<stack>` | needs `app/metric_tree.py` |
| host | `vsan-vnic-net` | VsanVnic | vNIC | `vNIC` | `<vmk>` | needs `app/metric_tree.py` |
| host | `vnic-rdt-network-latency` | VsanVnicRdtLatency | vNIC RDT Latency | `vNIC RDT Latency` | `<vmk>` | needs `app/metric_tree.py` |
| host | `zdom-vtx` | VsanZdomVtx | ZDOM VTX | `ZDOM VTX` | none | needs `app/metric_tree.py` |
| disk | `cache-disk` | VsanCacheDisk | Cache Disk | `Cache Disk` | `<disk uuid>` | needs `app/metric_tree.py` |
| disk | `capacity-disk` | VsanCapacityDisk | Capacity Disk | `Capacity Disk` | `<disk uuid>` | needs `app/metric_tree.py` |
| disk | `vsan-esa-disk-layer` | VsanEsaDiskLayer | ESA Disk Layer | `ESA Disk Layer` | `<disk uuid>` | needs `app/metric_tree.py` |
| disk | `vsan-esa-disk-scsifw` | VsanEsaDiskScsifw | ESA Disk SCSI | `ESA Disk SCSI` | `<disk uuid>` | needs `app/metric_tree.py` |
| vm | `virtual-machine` | VsanVirtualMachine | VM | `VM` | none | needs `app/metric_tree.py` |
| vm | `virtual-disk` | VsanVirtualDisk | Virtual Disk | `Virtual Disk` | `<busN:M>` | needs `app/metric_tree.py` |
| vm | `vscsi` | VsanVscsi | (none) | `vSCSI` | `<scsiN:M>` | needs `app/metric_tree.py` |

Authoring note: the author keeps ROOT and the group column as one table in
`EntityType` (as Build 1 does), with `EntityTypeTest` checking it row for row
against this design, so the switch is one table edit plus this design's
tables, and no code path builds a group name any other way.

---

## Settings (describe.xml, adapter instance kind)

Build 1 settings are unchanged (`vcenter_host` and `cluster_include` stay
the identity; PAK REFERENCE §Settings). New, all `identType="2"` (Advanced,
not part of identity, so they can change later without recreating accounts):

| Key | Label | Type / default | Notes |
|---|---|---|---|
| `tier_host` | Host tier (extra host groups) | enum `true`/`false`, **default `true`** | the 13 host types beyond Build 1's core; core (DOM owner, DOM client, pNIC) is always on |
| `tier_cluster` | Cluster tier | enum, **default `true`** | 10 cluster types onto ClusterComputeResource |
| `tier_disk` | Disk tier | enum, **default `false`** | 4 disk types onto HostSystem; adds the per-host disk map read |
| `tier_vm` | VM tier | enum, **default `false`** | 3 VM types onto VirtualMachine; adds the VM read and the Suite API VM list |
| `vm_tier_every_n_cycles` | VM tier every N cycles | int, **default 3**, range 1 to 12 | staggered: cluster *c* runs its VM types on cycles where `(cycle + stableHash(cluster MoRef)) mod N == 0`, so 1/N of the clusters do VM calls each cycle instead of all of them every Nth cycle |
| `exclude_types` | Entity types to exclude | string, default empty | comma list of entity type ids (`ioinsight,vsan-file-service`) applied after the tier switches; may name core types; unknown ids are a configure-time WARN, not an error; if nothing is left in scope, Test Connection says so |

Unchanged but re-advised: `max_parallel_clusters` stays default 4 (the knee
under the per-vCenter hypothesis, MAP test 7); raise it to 8 only if
`PERF cycle` shows calls/s scaling with workers (per-cluster ceiling, D9).

Internal constants (not settings): identity refresh every 12 cycles (Build
1); VM-type calls limited to **one in flight across all workers** (a
semaphore; Sizing); VM read page 50 objects; Suite API VM page 500;
empty-echo learning threshold 3 cycles. Tier switches apply from the first
cycle after the account is saved; `perf_timing_logging` keeps its Build 9
behaviour (re-read every cycle).

### Recommended defaults for a 70-cluster vCenter, and why

Inputs: PLAN §1 worked example (70 clusters x 6 hosts, 40 VMs per host =
16,800 VMs; 2 pNICs per host), lab per-unit ratios above, 7 calls/s
sustained ceiling (MAP test 7, both transports), 240 s cycle deadline (V1).

- **host on, cluster on** (23 calls per cluster steady, 1,610 per cycle):
  the two tiers add 65,590 series per cycle (host 59,220 + cluster 6,370) on
  top of core's 32,760, all on objects that already exist, at ~3.4 KB wire
  and ~31 KB decoded per cluster for the cluster tier and ~22 KB / ~288 KB
  for the host tier. If the ceiling is per vCenter, 1,610 calls take ~230 s,
  inside the 240 s deadline with ~10 s spare; if it is per cluster, ~60 s at
  4 workers. This is the most that fits the per-vCenter case.
- **disk off:** 2 calls per cluster (+140 per cycle) push the per-vCenter
  case to ~250 s, past the deadline; 24 of its 31 names already exist on
  the built-in disk objects (INV §3); and it adds 420 host calls per
  refresh. Turn it on for small vCenters or after the ceiling is known.
- **vm off; N = 3 when on:** the call cost is small (3 per cluster; +70 per
  cycle staggered at N = 3), but the series are not: ~1.01 million with a
  value per VM cycle at the example (1.34 million requested), ~86 MB of push
  payload at the measured ~85.5 B per stat value (T5-9: 33,360 B for 390),
  against Suite API ingest that is unmeasured at any volume above Build 1's
  (PLAN §1 "a Build 2 question"); plus the device read (~56 MB wire / ~407
  MB decoded for a full read at 16,800 VMs, projection). Staggered N = 3
  averages ~338,000 series per cycle. Recommend enabling it only after the
  default tiers have run a day on the customer's vCenter with
  `perf_timing_logging` on, and on a cluster subset first (`cluster_include`
  on a second account).
- **One instance, not sharded, to start.** Sharding through
  `cluster_include` splits heap and collector CPU across instances, but if
  the ceiling is per vCenter it does not add calls per second: every shard
  talks to the same vsan-health. Shard when `PERF cycle` heap or the
  collector says so, not for wall time.

---

## Per-cycle call plan

### Steps

| Step | Calls | When | Change from Build 1 |
|---|---|---|---|
| 0. Release id + login + about | 0 to 3 | as Build 1 | none |
| 1. Cluster + host inventory (R2) | 1 `RetrievePropertiesEx` (+ pages) | every cycle | host pathSet gains `configManager.vsanSystem` when `tier_disk` is on |
| 2a. Ops HostSystem map | Suite API pages | as Build 1 | none |
| 2b. Ops ClusterComputeResource map | 1 page | with 2a's cadence | new, `tier_cluster` |
| 2c. Ops VirtualMachine map | `ceil(VMs / 500)` pages (34 at 16,800 VMs) | every 12th VM-tier run, VM-set change, miss (at most once per 12 cycles per vCenter) | new, `tier_vm` |
| 3. Disk map | 1 `QueryDisksForVsan` per in-scope host (7 to 10 ms each) | identity refresh; one cluster after an unmapped disk | new, `tier_disk` |
| 4. VM read | per cluster view: create (once per session), `RetrievePropertiesEx` + pages of 50 | per §Device-list caching | new, `tier_vm` |
| 5. Perf queries | per cluster: 3 core + 13 host + 10 cluster + 4 disk + 3 VM (on its cadence cycle), minus learned skips | every cycle | +up to 30 types |
| 6. Stats push | per target kind, per sample time, batches of up to 100 resources and ~1 MB | every cycle | cluster and VM batches added |

Order inside a cluster task: core (DOM owner, DOM client, pNIC), cluster
tier, host tier, disk tier, VM tier. A deadline cut loses the tail first:
the VM types, which are also the ones on a cadence.

### Perf calls per tier combination

Steady = after the lab's empty types are learned (28 of 33 calls: the 27
non-empty types plus `ioinsight`, which is never learned);
first = before learning and on the daily re-probe. Serial seconds per
cluster are the lab's measured per-type sums (steady); per-call latency at
6 hosts and 240 VMs per cluster is not measured, and the VM calls in
particular will be slower than the lab's 111 to 253 ms because their
payload scales with VM count. "Per vCenter" divides calls by 7/s; "per
cluster" runs ceil(70 / workers) rounds of the per-cluster serial time.
Wall times exclude inventory, identity refreshes and push.

| Tiers on (core always) | Calls / cluster steady (first) | Serial s / cluster, lab | 1 cluster wall, serial | 70 clusters: calls steady (first) | 70: per-vCenter 7 calls/s, steady (first) | 70: per-cluster, 4 workers | 70: per-cluster, 8 workers |
|---|---|---|---|---|---|---|---|
| core | 3 (3) | 0.59 | 0.6 s | 210 (210) | 30 s (30 s) | 11 s | 5 s |
| core + host | 15 (16) | 2.16 | 2.2 s | 1,050 (1,120) | 150 s (160 s) | 39 s | 19 s |
| core + cluster | 11 (13) | 1.78 | 1.8 s | 770 (910) | 110 s (130 s) | 32 s | 16 s |
| core + disk | 5 (7) | 0.95 | 1.0 s | 350 (490) | 50 s (70 s) | 17 s | 9 s |
| core + vm | 6 (6) | 1.20 | 1.2 s | 420 (420) | 60 s (60 s) | 22 s | 11 s |
| **core + host + cluster (recommended default)** | **23 (26)** | **3.35** | **3.3 s** | **1,610 (1,820)** | **230 s (260 s)** | **60 s** | **30 s** |
| core + host + disk | 17 (20) | 2.52 | 2.5 s | 1,190 (1,400) | 170 s (200 s) | 45 s | 23 s |
| core + host + vm | 18 (19) | 2.77 | 2.8 s | 1,260 (1,330) | 180 s (190 s) | 50 s | 25 s |
| core + cluster + disk | 13 (17) | 2.14 | 2.1 s | 910 (1,190) | 130 s (170 s) | 39 s | 19 s |
| core + cluster + vm | 14 (16) | 2.39 | 2.4 s | 980 (1,120) | 140 s (160 s) | 43 s | 22 s |
| core + disk + vm | 8 (10) | 1.56 | 1.6 s | 560 (700) | 80 s (100 s) | 28 s | 14 s |
| core + host + cluster + disk | 25 (30) | 3.71 | 3.7 s | 1,750 (2,100) | 250 s (300 s) | 67 s | 33 s |
| core + host + cluster + vm | 26 (29) | 3.96 | 4.0 s | 1,820 (2,030) | 260 s (290 s) | 71 s | 36 s |
| core + host + disk + vm | 20 (23) | 3.13 | 3.1 s | 1,400 (1,610) | 200 s (230 s) | 56 s | 28 s |
| core + cluster + disk + vm | 16 (20) | 2.75 | 2.8 s | 1,120 (1,400) | 160 s (200 s) | 50 s | 25 s |
| core + host + cluster + disk + vm (all) | 28 (33) | 4.32 | 4.3 s | 1,960 (2,310) | 280 s (330 s) | 78 s | 39 s |

With the VM tier staggered at N = 3, its row cost is 1/3 of the VM column
per cycle: recommended default + VM = 1,610 + 70 = **1,680 calls, ~240 s**
per vCenter, the deadline itself; all tiers = 1,750 + 70 = 1,820, ~260 s,
over the deadline. The 70 x 33 = 2,310 first-cycle floor matches MAP "Design
answers"; the steady 70 x 28 = 1,960 is one call per cluster above MAP's
70 x ~27 = 1,890 because `ioinsight` is never learned.

Reading the table: **under the per-vCenter hypothesis no combination beyond
core + host + cluster fits a 5-minute cycle at 70 clusters, and the first
cycles of that one do not either** (260 s). The deadline path (push what
finished, rotate the start, V1) absorbs the first cycles; learning brings it
to 230 s. Under the per-cluster hypothesis everything fits with 4 workers.
The answer is still D9's; `PERF cycle` gives it from the first multi-cluster
run.

**Re-probe spread.** Learned types re-probe at 24 h plus a per-(cluster,
type) offset of `stableHash mod 60` minutes, so the clusters learned in the
same first cycle do not all re-probe in one cycle the next day (otherwise
the 260 s first-cycle cost recurs daily).

### Non-perf calls per cycle at 70 clusters (projection)

| Read | Steady per cycle | On refresh |
|---|---|---|
| R2 inventory | 1 (+ pages; paging at 70 clusters unmeasured, MAP) | n/a |
| Ops host + cluster maps | 0 | every 12th cycle: host pages as Build 1, + 1 cluster page |
| Disk map (`tier_disk`) | 0 | 420 calls, ~3 to 4 s serial, on the pool |
| VM read (`tier_vm`) | ~2 cluster reads (b), plus changes (c) | first run of each cluster: 70 reads, ~5 pages each |
| Ops VM map (`tier_vm`) | 0 | 34 pages |
| Push | default tiers: ~98,350 values, ~8.4 MB at 85.5 B/value, ~8 host batches (core 78 + host 141 = 219 series x 85.5 B = ~18.7 KB per host, so ~53 hosts per 1 MB batch) + 1 cluster batch, per sample time | VM tier at N = 3: + ~338,000 values, ~29 MB, ~56 VM batches of 100 VMs (5,600 VMs per cycle; ~0.5 MB each) |

---

## Sizing

### Series and bytes

| Tier | Series / cycle, lab (1 cluster) | Series / cycle, 70-cluster example | Perf wire / decoded per cycle, example (projection) |
|---|---|---|---|
| core | 390 | 32,760 (420 hosts x 78) | 0.8 MB / 11.1 MB |
| host | 705 | 59,220 (420 x 141) | 1.6 MB / 20.6 MB |
| cluster | 91 | 6,370 (70 x 91) | 0.2 MB / 2.2 MB |
| disk | 50 | 4,200 x disks per host (lab: 1; real ESA hosts usually carry more) | 0.1 MB / 1.6 MB per disk per host |
| vm | 2,400 requested, 1,808 with a value | 1,344,000 requested, ~1,012,000 with a value (16,800 VMs x 80 / 60.3) per VM cycle; ~338,000 per cycle at N = 3 | 27 MB / 477 MB per VM cycle (~9 MB / ~159 MB per cycle at N = 3) |
| **default (core + host + cluster)** | **1,186** | **98,350** | **2.6 MB / 34 MB** |

Projections scale the lab's per-host, per-cluster and per-VM bytes and
series linearly (PROV1, PROV2); nothing above one cluster is measured. The
decoded column is allocation churn, processed one response at a time, not
retained; it matters for collector GC, which the JVM sizing report found
already under pressure on the 9.0.2 node (V1 JVM).

### Heap against the 65 MB budget (D6)

Estimates for the example; object overheads are assumed (64-bit JVM,
compressed oops, compact strings), not measured. **T4 is the gate**; this
table says which design choices keep it passable.

| Component | Build 1 today | Default tiers | + disk | + VM (N = 3) |
|---|---|---|---|---|
| Duplicate-bucket marks, **Build 1 scheme** (one `String` key + boxed `Long` per entity and label, ~160 B) | ~5 MB (32,760) | ~16 MB (98,350) | ~16 MB | ~200 MB more for the VM series: **not viable** |
| Same marks, **Build 2 compact scheme** (per entity: 64-bit hash of `entityRefId` to an `int[]` of bucket indices by catalog position; ~64 B + 4 B per label) | (Build 1 scheme in use) | ~0.9 MB (7,210 entities) | ~1.0 MB | + ~17 MB (182,560 VM, vdisk and vSCSI entities x ~64 B + 1,344,000 labels x 4 B) |
| Inventory, Ops host and cluster maps | < 0.2 MB | < 0.3 MB | < 0.3 MB | < 0.3 MB |
| Disk map | 0 | 0 | < 0.1 MB | < 0.1 MB |
| Ops VM map (16,800 VMs, ~250 B each) | 0 | 0 | 0 | ~4 MB |
| VM index + compact vdisk map (82,880 vdisks, ~16 B each) | 0 | 0 | 0 | ~3 MB |
| In-flight non-VM perf responses (largest: host-domowner, 64,463 B decoded at 5 hosts, ~77 KB at 6; 4 workers; tree overhead up to 10x) | < 3 MB | < 3 MB | < 3 MB | < 3 MB |
| In-flight VM perf responses, **full-tree parse** (vscsi ~3.3 MB and virtual-disk ~3.0 MB decoded at 240 VMs per cluster; 5 to 10x tree; 4 in flight) | n/a | n/a | n/a | 66 to 133 MB: **not viable** |
| Same, **streaming parse and one VM call in flight** (gzip wire buffer ~0.2 MB + one entity) | n/a | n/a | n/a | < 1 MB |
| Cluster results queue (depth = workers; ~140 B per row; default ~1,405 rows per cluster, VM ~14,470) | < 1 MB | < 1 MB | < 1 MB | ~8 MB |
| VM read page (50 VMs x ~24 KB decoded, full-tree parse 5 to 10x) | 0 | 0 | 0 | 6 to 12 MB, one page at a time |
| Push batch body | ~1 MB | ~1 MB | ~1 MB | ~1 MB |
| **Total** (Build 1 column as built: marks ~5 + maps 0.2 + responses 3 + queue 1 + push 1; the others with the Build 2 choices) | **~10 MB** | **~6 MB** | **~6 MB** | **~44 to 50 MB** |

Design consequences (requirements on the author, all checked by T4):
1. **Compact marks** replace `Watermarks`' string-keyed map for every tier.
   At default tiers the Build 1 scheme alone would spend a quarter of the
   budget. The per-label semantics stay exactly as Build 1 (a lagging label
   or entity is never skipped; a mark is recorded only after a clean push).
   A 64-bit hash collision at ~10^4 to 10^5 entities is negligible
   (~10^-10); the mark is still compared per label.
2. **One bucket rule for every tier and every N.** Every non-`None` bucket
   in the window that is newer than the per-(entity, label) mark is pushed,
   and the mark moves only after a clean push (Build 1's mark semantics). A
   bucket that is pushed again anyway (a failed batch, a lost mark after a
   restart) carries the same timestamp and value: a harmless self-overwrite,
   which Build 1 already accepts after a failed batch (PAK REFERENCE). The VM
   tier keeps marks like every other tier (~17 MB at the example, in the
   table); with them, the VM column stays under the 65 MB budget only with
   requirements 1 and 3 to 5. This replaces Build 1's "newest non-`None`
   token per series" selection (Supersedes list).
3. **Streaming parse of `VsanPerfQueryPerf` responses** (one
   `VsanPerfEntityMetricCSV` at a time from the gzip stream; the shape is
   fixed and fully listed in MAP "Response shape") for all perf calls, not
   only VM types, so there is one parser and T4 measures it. The VM types'
   decoded size also passes the current `DECODED_CAP` of 8 MB at ~580 VMs
   per cluster (vscsi ~13.8 KB decoded per VM); streamed, only a wire cap
   applies: keep 4 MB for non-VM types, **16 MB for VM types** (~20,000 VMs
   per cluster at ~0.8 KB wire per VM for vscsi, far past any cluster).
4. **One VM-type call in flight** across the pool (semaphore), so VM
   responses never stack per worker. Under the per-cluster hypothesis this
   serializes ~23 clusters x 3 calls per cycle at N = 3, ~14 s at the lab's
   latency.
5. **Small pages** for the VM read (50) and the Ops VM list (500), parsed and
   reduced page by page.

### Cycle time

From the call-plan table: at 70 clusters, default tiers take ~230 s of perf
calls if the ~7 calls/s ceiling is per vCenter (deadline 240 s), ~60 s if it
is per cluster with 4 workers (~30 s with 8). Add per cycle: inventory
(~20 ms on the lab, MAP; at 70 clusters unmeasured), push (45 ms for 390
values on the lab, T5-9; ~98,350 values at the example unmeasured), and on
refresh cycles the identity reads (disk map ~3 to 4 s serial, VM reads
~5.8 MB decoded per cluster read). On the lab (1 cluster), default tiers are ~3.3
s of serial calls; all tiers ~4.3 s steady, ~5.0 s first.

---

## Failure handling deltas (V1 §Failure handling still applies)

| Failure | Behaviour | Cycle outcome |
|---|---|---|
| Empty echo for a learnable type | counted "empty this cycle"; after **3 consecutive** empty results on that cluster, learned for 24 h plus the re-probe offset (B7). For VM-run types (`virtual-machine`, `virtual-disk`, `vscsi`) the count is consecutive empty **VM runs** of that cluster, not cycles. A **re-probe that comes back empty re-learns at once** (no second 3-run count); a re-probe with data clears the state. **Exempt, never learned on an empty echo:** the 3 core types (expected on every vSAN cluster; a transient empty must not blind DOM owner/client for a day) and `ioinsight` (queried every cycle, ~120 ms and ~120 B when empty, MAP; a capture is started and stopped by users at any time, so it is best-effort by nature) | succeeds |
| ClusterComputeResource not in Ops | `clusters_unresolved`, WARN once per refresh, cluster-tier rows skipped; triggers only an Ops map refresh, at most once per 12 cycles per vCenter | succeeds |
| Unobserved-grammar entity that classifies as neither cluster nor node | `entities_unparsed`, WARN once per type per day (type and part count, not the id) | succeeds |
| `vsan-tcpip-stats` / `vsan-vnic-net` / `vnic-rdt-network-latency` id with the wrong part count | skipped and counted (`entities_unparsed`), as Build 1 does for pNIC | succeeds |
| `QueryDisksForVsan` faults or times out for a host | that host's disks unresolved this refresh; WARN once; retried at the next refresh | succeeds |
| Disk uuid not in the disk map | `disks_unresolved`; that cluster's disk map re-read next cycle, at most once per 12 cycles per cluster | succeeds |
| VM read faults, over a cap, or a page fails | `virtual-disk` dropped for that cluster this run (needs the device map); `virtual-machine` and `vscsi` still pushed if the cached instanceUuid map covers them; WARN once | succeeds |
| instanceUuid not in the VM map | `vms_unresolved`; cluster's VM read re-run on its next VM run, at most once per 12 cycles per cluster; skipped until then | succeeds |
| VM MoRef not in Ops | `vms_unresolved`; Ops VM map refresh only (no vCenter re-read), at most once per 12 cycles per vCenter; skipped until a refresh finds it | succeeds |
| vdisk path not in the device map, or disk on an unknown controller type | `vdisks_unresolved`; path miss: same re-read trigger and rate limit as an instanceUuid miss | succeeds |
| VM-type response over the 16 MB wire cap | failed call for that type and cluster, WARN with the cap | succeeds |
| Tier switched off | its calls stop next cycle; its compact marks age out under Build 1's 24 h retention; nothing is deleted from Ops (pushed keys cannot be) | succeeds |
| `exclude_types` leaves nothing in scope | configure WARN and Test Connection message | instance error |

---

## Logging deltas (V1 §Logging still applies)

Always on: the INFO cycle summary gains per-tier series pushed and the new
unresolved counts: `...; series pushed=.. (core .. host .. cluster .. disk ..
vm ..); unresolved hosts=.. clusters=.. disks=.. vms=.. vdisks=..; unparsed=..;
learned skips=..`. WARN once per refresh for each new unresolved class.

With `perf_timing_logging=true` (INFO, `PERF` prefix, `key=value`):

| Line | Change |
|---|---|
| `PERF call` | adds `tier=core\|host\|cluster\|disk\|vm` and `parse=stream`; one line per perf call, as Build 1 |
| `PERF cluster` | adds `calls_by_tier=core:3,host:12,cluster:8,disk:0,vm:0` and `vm_run=yes\|no` (the cadence decision) |
| `PERF tier` (new) | per cycle per tier: `calls`, `call_ms_sum`, `wire_bytes`, `decoded_bytes`, `entities`, `series_kept`, `series_pushed`, `unresolved`, `learned_skips` |
| `PERF identity` (new) | per identity read: `read=ops_clusters\|ops_vms\|disk_map\|vm_read`, cluster (for per-cluster reads), `calls`, `pages`, `ms`, `wire_bytes`, `decoded_bytes`, `count`, `trigger=refresh\|change\|miss`. Never the ContainerView moId (V1) |
| `PERF pool` | adds `vm_permit_wait_ms_max` (time a worker waited for the one VM-call permit) |
| `PERF push` | adds `kind=HostSystem\|ClusterComputeResource\|VirtualMachine` |
| `PERF cycle` | adds per-tier call counts and `marks_entities`, `marks_bytes_est` (so T4's heap reading has a production twin) |

**Reading the ceiling (D9) with tiers.** Same rule as V1 (calls/s over the
perf phase against workers), now readable per tier: if `PERF tier` call_ms
for the VM tier grows with VM count while the other tiers stay flat, the
VM calls are payload-bound, not ceiling-bound.

---

## Prerequisite P2 (blocks disk-tier and VM-tier parser code only)

PROV2 says of the join reads "they were not saved here; they are summarized
in the digest", so there is no verbatim vendor fixture for the shapes the
disk and VM tiers parse. Before that code is written, the orchestrator
should brief `api-cartographer` (vCenter reads) and `ops-recon` (Suite API
reads) to save, under `reference/docs/extracted/vsan-perfsvc-json/` with a
provenance file (RULE-016):

1. `RetrievePropertiesEx` for `VirtualMachine` with `config.instanceUuid`
   and `config.hardware.device`, **over a ContainerView whose container is
   the cluster** (tests the scoping MAP did not), with
   `RetrieveOptions.maxObjects` small enough (for example 10) to return a
   `token`, plus the `ContinueRetrievePropertiesEx` page. Also one light read
   (`config.instanceUuid` only) for its size.
2. The R2 read with `configManager.vsanSystem` added to the host pathSet
   (**untested over JSON**: MAP names the addition but did not run it), then
   `QueryDisksForVsan` on the returned moId for one host (and
   `QueryVsanManagedDisks` for the same host, for the record).
3. Suite API `GET /api/resources` for `VMWARE` `ClusterComputeResource` and
   one page of `VirtualMachine` from the lab vCenter: the identifier names
   (confirms the assumed `VMEntityObjectID` + `VMEntityVCID` for both kinds)
   and whether `VMEntityInstanceUUID` is populated. Device read item 1 should
   include at least one VM whose disks are on a non-SCSI controller if the
   lab has one (bus prefix check).

Host-tier and cluster-tier code needs none of this: its fixtures exist
(PROV2) and its resolution is Build 1's R2 read and Ops map.

---

## Test plan

**T1. Offline unit tests** (`ci/run_java_tests.sh`, no SDK, no network):
- **Catalog**: the 390 rows of this design, table-driven, row for row
  against `EntityType` (key, vSAN label, per-mille flag), as Build 1 does
  for 61; the labels array per type equals the vSAN label column; the leaf
  rule reproduces every leaf (incl. the `deleteCongestion` exception).
- **Parser fixtures**: the 24 verbatim PROV2 captures, copied into the pak
  with their provenance, never edited. Assert per file the entity and
  series counts from PROV2's table (for example `virtual-disk` 148 / 1,036,
  `vscsi` 148 / 1,184, `vsan-memory` 5 / 60) and that the streaming parser
  and a whole-document parse give identical rows.
- **Grammar**: every row of MAP's entityRefId table from the captures:
  cluster uuid suffix; node suffix; `|defaultTcpipStack`;
  `|defaultTcpipStack|vmk2`; `|vmk2`; disk uuid; VM instanceUuid;
  `|scsi1:0`; virtual-disk paths incl. the 3 leading-slash refs and the
  nested `_003e/_000e` refs; no two refs collide after stripping.
- **`None`**: the 592 `NIOPS*` series of `queryperf-virtual-disk` yield zero
  values; the one-bucket VM, vdisk and vscsi entities in the captures push
  their single bucket.
- **Empty echo and learning**: the echo body quoted in PROV2; learned on the
  3rd consecutive empty (VM types: 3rd consecutive empty VM run); an empty
  re-probe re-learns at once; never for a core type or `ioinsight`; re-probe
  at 24 h plus the per-(cluster, type) offset.
- **Bucket rule**: a window with two buckets newer than the mark pushes both;
  a repeated bucket is pushed with the same timestamp and value.
- **Bus position**: controllerKey to busNumber and the prefix per controller
  `_typeName`; unknown controller type skipped (synthetic device arrays,
  labelled so, until the P2 device capture exists).
- **Runtime landing**: cluster uuid to cluster, node uuid to host, other to
  `entities_unparsed` (these ids are synthetic and labelled so in the test;
  no vendor capture exists for these types).
- **Stagger**: over N cycles every cluster runs its VM types exactly once.
- **Compact marks**: the Build 1 lagging-label and lagging-host cases still
  pass on the new structure.
- **Disk and VM maps**: from the P2 captures once they exist (blocked until
  then).

**T2. Fake-server tests (JDK `HttpServer`)**: VM read paging with `token`;
Suite API VM list paging at 500; streaming parse over a gzip body truncated
mid-entity (call fails cleanly, no partial push for that entity); VM-type
16 MB wire cap; one VM permit under 4 workers (a second VM call waits);
`QueryDisksForVsan` fault for one host of five; device-read fault with
`virtual-machine` and `vscsi` still pushed.

**T3. Replay harness** (pak issue #6, **prerequisite for the scale
release**): Build 1's plan extended to every Build 2 type: rewrite cluster
uuid, node uuids, NIC, stack and vmk names, disk uuids, VM instanceUuids,
vdisk namespace uuids and vSCSI devices per synthetic cluster; multipliers
for hosts per cluster, VMs per host, disks per host, NICs per host; both
throttle models (D9); a fake vCenter for R2, `QueryDisksForVsan` and the VM
read seeded from the P2 captures; a recording stitcher.

**T4. Heap and deadline gate** (pak issue #6, **prerequisite for the scale
release**), on every change, at 70 clusters x 6 hosts x 2 pNICs x 1 disk x
40 VMs per host:
- (a) default tiers: peak heap delta < 65 MB; series pushed = 98,350 per
  completed cycle; under the per-vCenter model with 0.19 s calls and 4
  workers, **cycles 1 to 3 take the deadline path** (26 calls per cluster
  before learning, ~260 s: completed clusters pushed, the rest counted timed
  out, rotation) and **from cycle 4 on the perf phase is < 240 s** (23 calls
  per cluster after learning, 1,610 per cycle, ~230 s).
- (b) all tiers, VM N = 3: peak heap < 65 MB; under the per-vCenter model
  the deadline path is exercised (completed clusters pushed, rotation next
  cycle), wall time is not asserted; under the per-cluster model the cycle
  completes.
- (c) VM N = 1: heap only.

**T5. Live proof, three platforms** (RULE-019; devel 8.18, 9.0.2, 9.1.1,
against `vcf-lab-vcenter-mgmt` / `vcf-lab-mgmt-cl01`):
- in-place upgrade from `v1.0.0.9` (same adapter kind, Java to Java): the
  account and collector object survive, the new settings show their
  defaults, Build 1 keys continue without a gap;
- step 1, gating the cluster and VM tiers: read the ClusterComputeResource
  and VirtualMachine identifiers and confirm (MoRef, VCID) resolution; read back one key per new group on hosts, on the
  cluster, on one VM; compare to the cycle's `PERF` log;
- disk and VM tiers switched on for the run (5 disks, 30 VMs);
- browser pass: how `TCP/IP:defaultTcpipStack`, `vNIC:vmk2`,
  `ESA Disk Layer:<uuid>`, `Virtual Disk:scsi0:0`, `vSCSI:scsi0:0` render;
- value spot-check against the vSphere client's vSAN performance charts for
  cluster DOM client IOPS and latency and one VM (R3);
- `VMEntityInstanceUUID` populated or not (feeds Q9).

Gate order unchanged (V1): `validate-sdk`, `build-sdk`,
`sdk-adapter-reviewer`, pak-compare zero BLOCKING, T5, `v*` tag through the
repo CI and the defect gate (RULE-012). The scale release additionally
requires T3 and T4 green.

---

## Migration

**From Build 1 (`v1.0.0.9`).** Same adapter kind, Java pak to Java pak: an
in-place pak upgrade, not the cross-runtime case of
`knowledge/lessons/cross-runtime-pak-upgrade-split-brain.md` (T5 checks it).
Nothing is renamed: the 61 Build 1 keys, the account identity and the
collector object identity are unchanged (B1). New keys only. Visible effects
after the upgrade, with the recommended defaults: host and cluster tiers
switch on, so the lab goes from 390 to 1,186 series and from 3 to 23 perf
calls per cycle (26 for the first cycles), and ClusterComputeResource gains
`vSAN Perf|*` keys. An admin who wants Build 1 behaviour sets `tier_host`
and `tier_cluster` to false. Duplicate-bucket marks are in memory and the
compact scheme starts empty, so the first cycle after the upgrade may push
the newest bucket again (a self-overwrite).

**From the Python pack.** Unchanged from V1 D7: side by side while
comparing, then uninstall the Python pack; no history carries over. At
Build 2 the comparison is like for like across the 451-key scope.

---

## Request Mapping

| # | Request | API | Feeds | Notes |
|---|---|---|---|---|
| 1 | Login / about | vim25 JSON | session, VCID | Build 1 |
| 2 | Cluster + host inventory (R2, + `configManager.vsanSystem` with disk tier) | vim25 JSON | cluster uuid to MoRef, node to host, vsanSystem moId | every cycle |
| 3 | `GET /api/resources` HostSystem, ClusterComputeResource, VirtualMachine | Suite API | Ops resource ids | refresh cadence |
| 4 | `QueryDisksForVsan` per host | vim25 JSON | disk uuid to host | disk tier, refresh |
| 5 | `RetrievePropertiesEx` VirtualMachine per cluster | vim25 JSON | instanceUuid to MoRef, vdisk path to (MoRef, label) | VM tier, cached |
| 6 | `VsanPerfQueryPerf <type>:*`, one per type per cluster | vSAN JSON | the 33 groups | every cycle; VM types on cadence |
| 7 | `POST /api/resources/stats` | Suite API | HostSystem, ClusterComputeResource, VirtualMachine | batched per kind and sample time |

## Events

None (V1: pak-runtime events are stripped from SDK paks). Alerting is
factory symptoms and alerts on HostSystem, ClusterComputeResource and
VirtualMachine in a later content round.

## Bundled Dashboard

None in this design. Build 2 content (PLAN §5: Object List to Metric Chart,
host-centric, Scoreboards following dashboard time) is a separate round in
the pak repo under `views/` and `dashboards/`, through the RULE-011
wireframe gate, after the key tree (Q1) is settled, since views reference
key names.

---

## Key Risks (V1 R1 to R9 still apply)

- **R10 The ceiling decides the default's fit (D9).** Default tiers at 70
  clusters are ~230 s of calls under the per-vCenter hypothesis, ~10 s
  inside the deadline; first cycles ~260 s. Sharding does not help that
  case. Mitigation: deadline path, rotation, re-probe spread, `PERF tier`.
- **R11 Suite API ingest at Build 2 volume is unmeasured** (PLAN §1).
  Default tiers push ~98,350 values (~8.4 MB) per cycle at the example;
  the VM tier ~1 million per VM cycle. Build 1's only number is 390 values
  in 45 ms. Mitigation: VM tier off by default, staggered when on;
  `PERF push` per kind.
- **R12 Two new stitch targets are unproven.** ClusterComputeResource
  identifiers and push, VirtualMachine instanced keys: no read or push
  recorded (PUSH proved HostSystem only). Mitigation: P2 item 3, T5 first
  step.
- **R13 VM read cost and scoping are projected.** Per-cluster ContainerView
  scoping and `maxObjects` paging over JSON are untested; the full-read
  projection at 16,800 VMs is ~56 MB wire / ~407 MB decoded. Mitigation:
  P2 item 1, caching per §VirtualMachine, `PERF identity`.
- **R14 Heap with the VM tier depends on streaming parse and one VM call
  in flight.** Without them the estimate is 66 to 133 MB for in-flight VM
  responses alone. Mitigation: requirements 1 to 5 under Sizing, T4.
- **R15 Disk-tier name overlap.** 24 of 31 disk keys repeat built-in
  `vSAN|Performance|*` names on the built-in disk objects (INV §3, name
  match, no value comparison). Two places for one number confuse users.
  Mitigation: tier off by default; Q4.
- **R3b Units, Build 2 additions.** `deleteCongestion` left unsuffixed
  against PY's "bytes"; `dedupRatio` pushed as ratio x 100; byte-size
  `Bytes` suffix rests on PY units like the rest. Spot-check in T5. Leaves
  are permanent.
- **R16 Unobserved grammars.** `vsan-direct-cluster`, `vsan-direct-host`,
  `vsan-file-service`, `ioinsight`, `cache-disk`, `capacity-disk` were
  empty on the lab; multi-stack and multi-vmk instancing unobserved (MAP
  Gaps). Mitigation: runtime landing, `entities_unparsed`, a capture from
  any customer cluster that has the feature becomes a fixture.
- **R17 Virtual-disk instance stability.** Decided: bus position
  (`scsi0:0`), which changes only when a disk is moved to another slot (a new
  instance; the old one's history stays stranded). The alternative,
  `deviceInfo.label` (`Hard disk 1`), is a display string whose localization
  and renumbering after a disk removal are not checked. Non-SCSI prefixes
  unobserved. Q5.
- **R18 Empty-echo learning can hide a feature turned on.** A type learned
  empty stays unqueried for up to 24 h plus the offset after File Service or
  vSAN Direct is enabled (an OSA/ESA disk type likewise after a conversion).
  Accepted: the daily re-probe bounds it. `ioinsight` is exempt from learning
  and queried every cycle (~120 ms, ~120 B when empty), because captures are
  started and stopped by users and are best-effort by nature.
- **R19 `NIOPS*` always `None` here.** 592 series per lab cycle parsed for
  nothing; whether they fill under an IOPS-limit policy is unverified (MAP).
  Kept (B8).

---

## Open questions for the user

Each has a recommendation; the design is written on it unless noted.

1. **Q1 Key tree: stay `vSAN Perf|...` or switch to the 2.0.0
   `cptvsan|...` tree.** Blocked on input: `app/metric_tree.py` (or the
   SCOTTSREADME tree) is not in the fork clone or on either GitHub repo, so
   the 2.0.0 group names are not mapped yet; the §Key tree alignment table
   has the slot. **Recommendation:** stay with `vSAN Perf|`, unless 2.0.0
   content (views, symptoms) is to be ported by key name. The 2.0.0 keys sit
   on the Python pack's own objects, so no 2.0.0 view or symptom works on
   HostSystem by key alone; a switch buys familiar names at the price of
   renaming the 61 released keys and orphaning the lab's history. Either
   way, decide before the first scale-release tag.
2. **Q2 Cluster-tier target (V1 Q6).** Recommended: VMWARE
   ClusterComputeResource keyed (MoRef, VCID), resolved like hosts.
   Alternative: the built-in `VirtualSANDCCluster` (parsed display ID,
   depends on the built-in adapter). Identifiers and push to be confirmed in
   P2 and T5.
3. **Q3 VM tier default.** Recommended: off; `vm_tier_every_n_cycles` = 3,
   staggered, when on. Enable at the 70-cluster customer only after a day of
   default tiers with timing logging, and on a cluster subset first.
4. **Q4 Disk tier default and the built-in overlap.** Recommended: off by
   default; when on, emit all 31 keys (parity with the Python pack), not
   only the 7 names the built-in disk objects lack. Alternative: emit only
   those 7.
5. **Q5 Virtual-disk instance (decided: bus position).** The tables, B5
   and the heap model use the bus position (`scsi0:0`; `nvme0:0`, `sata0:0`,
   `ide0:0` for other controllers), the same instance as our `vSCSI` group
   and vCenter's own `virtualDisk:scsi0:0`. Stated alternative:
   `deviceInfo.label` (`Hard disk 1`). Permanent once pushed; confirm before
   the first VM-tier push.
6. **Q6 Leaf rule extension.** Recommended: `Bytes` on byte sizes (25
   leaves), `Ms` and `Pct` rules stated but changing nothing today,
   `deleteCongestion` unsuffixed, `dedupRatio` pushed as served (x 100).
   Alternative: divide `dedupRatio` by 100 and name it `dedupRatioX`.
7. **Q7 Empty-echo learning rule (decided).** Learn after 3 consecutive
   empties (VM types: 3 consecutive empty VM runs); an empty re-probe
   re-learns at once; never for the 3 core types or `ioinsight`; re-probe at
   24 h plus a per-(cluster, type) offset.
8. **Q8 Supported vCenter range (V1 Q7, still open).** Recommended: vCenter
   8.0 U3 and later; needs the target customer's vCenter version.
9. **Q9 Unverified by the captures, to close before the scale release:**
   VM read scoped to a cluster and paged over JSON; ClusterComputeResource
   Ops identifiers (the cluster-tier Ops map is written on the assumed
   `VMEntityObjectID` + `VMEntityVCID`) and push; VirtualMachine Ops
   identifiers (same assumption), instanced push, and whether
   `VMEntityInstanceUUID` is populated; `configManager.vsanSystem` in the R2
   pathSet over JSON; entity id forms of the six empty types; OSA disk
   mapping through `QueryDisksForVsan`; multi-stack and multi-vmk instancing;
   bus prefixes other than `scsi` in `vscsi` and the device read; the
   "compute elsewhere, storage here" VM case (HCI Mesh or a non-vSAN
   cluster mounting the datastore); whether `deviceInfo.label` is localized
   or renumbered (alternative only); `NIOPS*` under an IOPS-limit policy. Recommended: P2 capture
   round now (lab), T5 for the Ops side, and a capture request to the
   customer for the feature types.
10. **Q10 Throughput ceiling (D9).** Still the deciding unknown for 70
    clusters. Recommended: before promising the customer anything beyond
    default tiers, get one multi-cluster measurement (their vCenter with
    `perf_timing_logging` on for an hour, or the T3 simulator once it
    exists).

## Addendum 2026-11-06: P2 measured (VM and disk joins, Ops targets)

The P2 round ran the same day (API map "P2: VM and disk joins over JSON, Ops
cluster and VM targets (measured 2026-11-06)"; verbatim bodies listed in
`reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-06-p2.md`).
Corrections and confirmations to the body above:

- **VM inventory**: a container view rooted at the cluster returns its VMs
  (42 on the lab, of which exactly the 30 powered-on ones appear in the perf
  data; 10 of the 12 others are templates). Light read 4.3 KB wire / 51 KB
  decoded / 9 ms; with `config.hardware.device` 142 KB / 1.04 MB / 60 ms
  (~3.4 KB wire, ~25 KB decoded per VM, up to ~31 KB on a 10-VM page). The
  device array cannot be narrowed by path (`.backing` faults
  `InvalidProperty`); filter client-side to `VirtualDisk` plus the
  controllers they reference. Paging with `maxObjects` works (10/10/10/10/2,
  new token per page, a reused token faults `InvalidArgument`). Cap pages at
  about 50 VMs (~1.6 MB decoded) given the streaming parser.
- **Joins confirmed**: `vscsi` instance = `scsi` + controller `busNumber` +
  `:` + `unitNumber`, 148/148; `virtual-disk` by backing path 148/148; every
  vdisk bus position is also a `vscsi` id on the same VM (Q5 holds). Only
  PVSCSI and LSI Logic controllers observed; the SATA/NVMe/IDE prefixes
  remain unobserved.
- **`QueryDisksForVsan`**: `POST .../HostVsanSystem/<configManager.vsanSystem moId>/QueryDisksForVsan`
  with `{}`; bare array of `VsanHostDiskResult`; key on non-empty `vsanUuid`
  (`state` is `ineligible` for in-use disks too); 8 to 11 ms, ~1.6 KB wire per
  host. All 5 ESA disk ids matched one host each. `configManager.vsanSystem`
  reads fine in the PropertyCollector pathSet (Q9 item closed).
- **Ops targets**: ClusterComputeResource and VirtualMachine carry
  `VMEntityObjectID` (MoRef) and `VMEntityVCID`, both part of uniqueness;
  (MoRef, VCID) matched 45/45 VMs. `VMEntityInstanceUUID` is empty on exactly
  the 30 powered-on vSAN VMs on devel (filled on the other 15 and on the
  workload vCenters' VMs; cause unknown), so it is **not** usable as a
  cross-check; resolution stays on (MoRef, VCID). A test push of
  `VCFCF Test|Build2|clusterKey` onto the cluster and the instanced
  `VCFCF Test|Build2|vdisk:scsi0:0|probe` onto a VM both read back with the
  pushed timestamp; the VM key within ~42 s, the cluster key only after
  ~343 s. **T5 waits at least 6 min before reading cluster keys.** The Ops VM
  list is ~2.9 KB per VM, not gzipped (~1.45 MB at 500 per page); Ops drops
  an idle keep-alive after ~30 s, so reconnect between cycles.
- **Netstacks / vmknics**: hosts carry 8 stacks and 6 to 7 vmknics but only
  `vmk2` is vSAN-tagged; the perf data reports `defaultTcpipStack` and
  `vmk2` only. Multi-stack / multi-vmk instancing is still unobserved.
