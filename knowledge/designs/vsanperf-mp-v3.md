# Design Artifact: vSAN Performance Management Pack v3 (Build 3, `metric_scope`, Tier 2, Java SDK)

**Status.** Build 3 design, for review before `sdk-adapter-author` starts.
Version line **1.2.0** (build numbers continue from 19). Extends
`knowledge/designs/vsanperf-mp-v2.md` (V2, shipped as `v1.1.0.18`); V2 and
`vsanperf-mp-v1.md` (V1) stay authoritative for everything not changed here.
Catalog and setting code is not blocked; parser fixtures and the T3/T4 `all`
rows are blocked on prerequisite P3 (§P3).

**Supersedes in V2:** nothing is replaced. Additions only: one setting
(§Setting), 36 entity types and 1,144 keys reachable only under
`metric_scope=all` (§New types, Appendix A), an extension of V2 §Leaf rule
for new labels (§Units), call-plan and T4 rows for `all` (§Call plan).

**MP display name / adapter kind / repo:** unchanged (`VCF Content Factory
vSAN Performance`, `vcfcf_vsanperf`, `sentania-labs/vcf-content-factory-sdk-vsanperf`).

**Grounding.**

| Ref | Source |
|---|---|
| V1, V2 | `knowledge/designs/vsanperf-mp-v1.md`, `knowledge/designs/vsanperf-mp-v2.md` (incl. P2 addendum) |
| MAP | `knowledge/context/api-maps/vsan-performance-service.md` (tests 4 to 7, "JSON API transport", "Build 2 entity types") |
| PROV2 | `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-06-build2.md` (dashboard-scope JSON captures, labels filtered) |
| REC | `/mnt/holding/vsan-perfsvc-recording-2026-11-06/` (manifest.json, perf/<type>.json): pyVmomi SOAP, 73 prefixes, 15-min window, no labels, vCenter 9.1.1.0100 build 25784172, ESA cluster `domain-c6004`, 5 hosts, 30 VMs; 58 ok, 41 with objects, 15 faults. **Local-only artifact (RULE-015), not reproducible from a clone; every figure used here is summarized in full in this file, and P3 replaces it with committed JSON captures.** |
| NICK | `nickfirefoot/vsanhostmetrics-java`, branch `scotts-readme`, commit `39db58d` (2026-11-07), `SCOTTSREADME.md`: §3 entityRefId grammar, §4.3/4.4 ownership, §6 units, §7 catalog (1,638 rows, V mark = 451), §8 feature gating. Treated as data |
| PY | fork `content/sdk-adapters/vsanhostmetrics/` (registry `managed_paks.md`) at tag `v2.0.0-rc.2`: `app/perfsvc_model.py` + `perfsvc_model_extra.py` (ENTITIES, 69 types, 1,636 labels), `app/metric_scope.py` (COVERED, 451; "1595 metrics defined; 451 referenced by views; 1144 not"), `app/metric_labels.py` (UNITS), `app/perfsvc.py` (PERMILLE, KIND_SUFFIX, `metrics_for`) |
| PAK | `content/sdk-adapters/vsanperf/` at `v1.1.0.18`: `EntityType.java`, `PerfParser.java`, `CycleEngine.java`, `describe.xml`, `REFERENCE.md`, `README.md` (T4 table, push model), `CHANGELOG.md` 1.1.0.18 |

All counts below were computed by script from PY, PAK `EntityType.java` and
REC; "lab" means REC unless marked MAP/PROV2.

---

## Original Request

Scott, 2026-11-07: add a `metric_scope` toggle. `dashboard` (default, today's
behaviour, 451 keys over 33 types) and `all` (every metric the vSAN
Performance Service exposes for the 69 entity types the vsanhostmetrics
Python pack models). A toggle, not a change of default. Version 1.2.0.
Design only.

## Tier decision (recorded, not re-evaluated)

Tier 2 Java SDK, as V1 §Tier decision. Same repo, no new repo.

## Decisions taken in this design

| # | Decision | Source |
|---|---|---|
| C1 | `all` = the PY model's 69 types with `Actual` twins dropped: **1,595 keys** (451 dashboard + 1,144 new). NICK §7's 1,638 rows = 1,595 + 41 `Actual` twins (identical values, PY `metrics_for`, "201 such pairs, 201 identical values") + 2 Python-side derived metrics (NICK §2.5). This pak pushes service values only; the two derived ones are super-metric material. Q1 | PY `metric_scope.py` docstring; NICK §7 header; computed |
| C2 | Keys are added, never renamed. The 451 released keys keep their leaves; a label already released on any type reuses that leaf on every type (one leaf per label, 0 conflicts in the 451) | V2 B1; PAK `EntityType.java` |
| C3 | Under `all` the `labels` filter is not sent, for every type. The parser keeps only catalog labels (it already does: `PerfParser` skips a label with no catalog row) and counts the rest | MAP test 5 (filter trims bytes, not wall time); PAK `PerfParser.java` |
| C4 | No new object kinds. Every new type lands on VMWARE HostSystem, ClusterComputeResource or VirtualMachine through the V2 joins, or is counted unresolved | V2 §Identity |
| C5 | New types join the existing four tiers; `metric_scope` composes with tiers, never replaces them | brief |
| C6 | Remote (HCI Mesh) types resolve only to objects of the queried cluster; anything else is counted in `*_unresolved`, never landed cross-cluster | NICK §4.4 (double-collection risk) |
| C7 | Leaves are frozen at design time from PY UNITS (rc.2); unknown or disputed unit = no suffix, permanently | V2 §Leaf rule; NICK §6 |
| C8 | Within each tier, dashboard types run first, new types after, `host-cpu` and `dom-world-cpu` last (deadline cut loses the new, high-volume tail first) | V2 §Steps ordering rule |

## Interview Answers

| Question | Answer |
|---|---|
| Monitoring scope | Toggle: `dashboard` (451) or `all` (1,595) per account |
| Object granularity | Unchanged: key groups on HostSystem / ClusterComputeResource / VirtualMachine; multi-entity types instanced |
| Stitching | Unchanged (V2) |
| Interval | Unchanged: 5 min, VM tier every N |

## Count reconciliation

| Item | Brief | Computed | Note |
|---|---|---|---|
| Keys under `all` | 1,638 | **1,595** | C1; Q1 |
| Shared types that gain keys | 20 | **21** | the 21 rows of §Shared types; the other 12 shared types already carry their whole model at dashboard scope (`cmmds-net`, `vsan-cpu`, `vsan-direct-host`, `host-esa-dedup-domclient-io`, `vsan-direct-cluster`, `vsan-file-service`, `ioinsight`, `cluster-esa-dedup-domclient-io`, `cache-disk`, `capacity-disk`, `virtual-disk`, `vscsi`) |
| New types | 36 | 36 | cluster 9, host 21, disk 3, VM 3 |
| New keys | n/a | 1,144 = 686 on shared types + 458 on new types | matches PY "1144 not" |

Keys per tier under `all` (dashboard in brackets): core 407 (61), cluster 390
(189), host 634 (149), disk 126 (31), VM 38 (21). Types per tier: 3, 19, 34, 7, 6.

---

## Object Model

```
Unchanged kinds (V2): adapter instance + VsanPerfCollector; nothing new.

Stitched, metric_scope=all adds (instance syntax as V2 grammar):

VMWARE ClusterComputeResource
 ├── existing 10 groups (+43 keys on 6 of them)
 ├── vSAN Perf|ESA Dedup DOM Comp Mgr|*   24     ├── vSAN Perf|PMem|*                      8
 ├── vSAN Perf|ESA Dedup DOM Owner|*      24     ├── vSAN Perf|Remote DOM Client|*         8
 ├── vSAN Perf|ESA Dedup Chunk Service|*  27     ├── vSAN Perf|Compute Remote DOM Client|* 8
 ├── vSAN Perf|ESA Dedup Hash Service|*   34     ├── vSAN Perf|Resync|*                   24
 └── vSAN Perf|Data Protection|*           1

VMWARE HostSystem
 ├── existing 20 groups (+641 keys on 14 of them: core +346, host tier +251, disk tier +44; §Shared types)
 ├── vSAN Perf|pCPU|*  and  vSAN Perf|pCPU:<cpu>|*            3 each (aggregate + per physical CPU)
 ├── vSAN Perf|DOM World:<world>-<id>|*                       3 per DOM world
 ├── vSAN Perf|LSOM World:<world>-<id>|*                      2 per LSOM world (OSA)
 ├── vSAN Perf|ESA Dedup DOM Comp Mgr|* 24, ESA Dedup DOM Owner|* 24, ESA Dedup Chunk Service|* 27, ESA Dedup Hash Service|* 34
 ├── vSAN Perf|vSAN Sparse|* 21, RDT Network|* 1, System Memory|* 3, Distribution|* 5, CLOM|* 2, CMMDS Workload|* 23
 ├── vSAN Perf|Remote DOM Client|* 11, Compute Remote DOM Client|* 11, PMem|* 8, iSCSI|* 10
 ├── vSAN Perf|Heap:<heap>|* 1, Slab:<slab>|* 1, iSCSI Target:<target>|* 10, iSCSI LUN:<target>/<lun>|* 10
 └── disk tier: Disk Group:<disk uuid>|* 38, CLOM Disk:<disk uuid>|* 3, Disk Health:<disk uuid>|* 10

VMWARE VirtualMachine
 ├── existing 3 groups (+2 keys on VM)
 └── vSAN Perf|Remote VM|* 6, Remote Virtual Disk:<busN:M>|* 3, Remote vSCSI:<scsiN:M>|* 6
```

### Relationships

None created (V2).

---

## Setting: `metric_scope`

describe.xml, adapter instance kind, after `vm_tier_every_n_cycles`:

| Key | Label (resources.properties) | Type / default | identType | dispOrder | nameKey |
|---|---|---|---|---|---|
| `metric_scope` | Metric scope | enum `dashboard` (displayOrder 1), `all` (2); **default `dashboard`** | 2 (Advanced) | 14 | 43 (next free after 42) |

An account saved before 1.2.0 has no stored value and gets `dashboard`, so an
in-place upgrade changes nothing. Re-read on reconfigure exactly like the
tiers: a saved settings change builds a new `CycleEngine` (PAK CHANGELOG
1.1.0.18, observed on devel), applied from the next cycle.

**Composition** (applied in this order):

| Step | Rule | Source |
|---|---|---|
| 1. Tiers | `tier_host`, `tier_cluster`, `tier_disk`, `tier_vm` pick tiers; core always on | V2 §Settings |
| 2. Scope picks types | `dashboard`: the 33 types. `all`: the 69 (each new type belongs to one tier, §New types) | C5 |
| 3. Scope picks labels | `dashboard`: COVERED labels sent as the `labels` filter (unchanged). `all`: no filter; catalog labels kept, others dropped and counted (`PERF tier labels_dropped`) | C3 |
| 4. `exclude_types` | applied last; may name any of the 69 ids under either scope; an id outside the 69 stays a configure WARN; naming a new-type id under `dashboard` is silent (known id, not in scope). Useful under `all`: `exclude_types=dom-world-cpu,host-cpu` cuts 297 series per host on the lab (1,271 to 974) | V2 §Settings |
| 5. Learned state | learned-empty, learned-fault and dedup marks live in the `CycleEngine`, so **any scope change resets them** (a new engine). First cycle after a switch re-probes every type and re-sends both window buckets (self-overwrite, as V2 §Migration). Requirement: a T1 test pins this | PAK CHANGELOG 1.1.0.18 ("5,988 values = 2 x 2,994", "26 + 3 VM-tier calls = 29") |
| 6. `vm_tier_every_n_cycles` | unchanged; covers all 6 VM-tier types under `all` (the 3 remote types ride the cadence) | V2 |

Core under `all` with every tier off still grows: 448 series per host on the
lab (host-domowner 288, host-domclient 78, pNIC 41 x 2).

---

## Shared types under `all` (21 that gain keys)

Columns: keys at dashboard / all; leaves with a suffix among the new ones;
`Actual` twins dropped; lab entities; lab series dashboard / all (catalog
labels only) [REC].

| Type | Tier | Group | Dash | All | New | Suffixed | Twins | Lab ent. | Lab series dash | Lab series all |
|---|---|---|---|---|---|---|---|---|---|---|
| `host-domowner` | core | `DOM Owner` | 38 | 288 | +250 | 52 | 0 | 5 | 190 | 1,440 |
| `host-domclient` | core | `DOM Client` | 6 | 78 | +72 | 22 | 0 | 5 | 30 | 390 |
| `vsan-pnic-net` | core | `pNIC` | 17 | 41 | +24 | 4 | 24 | 10 | 170 | 410 |
| `vsan-cluster-capacity` | cluster | `Capacity` | 5 | 6 | +1 | 1 | 0 | 1 | 5 | 6 |
| `cluster-domclient` | cluster | `DOM Client` | 11 | 14 | +3 | 0 | 0 | 1 | 11 | 14 |
| `cluster-domcompmgr` | cluster | `DOM Comp Mgr` | 12 | 15 | +3 | 2 | 0 | 1 | 12 | 15 |
| `cluster-domowner` | cluster | `DOM Owner` | 23 | 46 | +23 | 6 | 0 | 1 | 23 | 46 |
| `cluster-rdt-network-latency` | cluster | `RDT Latency` | 9 | 17 | +8 | 8 | 0 | 1 | 9 | 17 |
| `cluster-zdom-top-stats` | cluster | `ZDOM Top Stats` | 7 | 12 | +5 | 2 | 0 | 1 | 7 | 12 |
| `host-domcompmgr` | host | `DOM Comp Mgr` | 16 | 82 | +66 | 24 | 0 | 5 | 80 | 410 |
| `vsan-host-net` | host | `Host Network` | 8 | 16 | +8 | 0 | 0 | 5 | 40 | 80 |
| `host-zdom-top-stats` | host | `ZDOM Top Stats` | 11 | 19 | +8 | 2 | 0 | 5 | 55 | 95 |
| `vsan-memory` | host | `Memory` | 12 | 50 | +38 | 14 | 0 | 5 | 60 | 250 |
| `rdt-network-latency` | host | `RDT Latency` | 11 | 17 | +6 | 6 | 0 | 5 | 55 | 85 |
| `vsan-tcpip-stats` | host | `TCP/IP:<stack>` | 12 | 22 | +10 | 4 | 10 | 5 | 60 | 110 |
| `vsan-vnic-net` | host | `vNIC:<vmk>` | 10 | 57 | +47 | 13 | 7 | 5 | 50 | 285 |
| `vnic-rdt-network-latency` | host | `vNIC RDT Latency:<vmk>` | 10 | 17 | +7 | 7 | 0 | 5 | 50 | 85 |
| `zdom-vtx` | host | `ZDOM VTX` | 10 | 71 | +61 | 6 | 0 | 5 | 50 | 355 |
| `vsan-esa-disk-layer` | disk | `ESA Disk Layer:<disk uuid>` | 5 | 38 | +33 | 0 | 0 | 5 | 25 | 190 |
| `vsan-esa-disk-scsifw` | disk | `ESA Disk SCSI:<disk uuid>` | 5 | 16 | +11 | 4 | 0 | 5 | 25 | 80 |
| `virtual-machine` | vm | `VM` | 6 | 8 | +2 | 0 | 0 | 30 | 180 | 240 |
| **21 types** | | | **244** | **930** | **+686** | **177** | **41** | | **1,187** | **4,615** |

REC returned every model label on every non-empty shared type and none
missing; extra labels beyond the model came back only on the ESA dedup
types (§Uncataloged labels).

**Payload growth from dropping the filter** (33 shared types, one lab
cluster, JSON, 7-min window) [observed MAP "Comparison, SOAP vs JSON"]:
labels 83 KB wire / 1.28 MB decoded, no labels **153 KB / 2.56 MB** (x1.84
wire, x2.0 decoded); series 3,636 to **7,497** returned, of which **7,064**
are kept (433 twin or uncataloged series dropped) [REC]. Wall time
unchanged within noise [observed MAP test 5]. The request body loses the
label array (288 names for `host-domowner`).

---

## New types (36)

Every type keeps its wire prefix as the query (`<type>:*`, one wildcard per
call, MAP test 4). "Lab" = REC on the 9.1.1 ESA cluster. Ref grammar marked
`[observed]` comes from REC ids; `[inferred]` is NICK §3 "inferred" (from the
entity name, never seen). Resolution columns use V2 §Identity joins: node
uuid via R2 `clusterInfo.nodeUuid` to host MoRef, cluster uuid = the queried
cluster's vSAN uuid, disk uuid via the per-host `QueryDisksForVsan` map, VM
via the cluster's VM read; Ops object by (`VMEntityObjectID`, `VMEntityVCID`).
Feature column: NICK §8 `FEATURE_ENTITIES` ("gated") or its silent,
not-gated list ("silent"); "expected empty" = learned-empty (or
fault-learned) on most clusters.

### Cluster tier (9 types, 158 keys, ClusterComputeResource)

| Type | Ref after `:` | Resolves to | Instance | Group | Keys | Feature | Lab |
|---|---|---|---|---|---|---|---|
| `cluster-esa-dedup-domcompmgr-io` | `<vsan cluster uuid>` [observed] | queried cluster | none | `ESA Dedup DOM Comp Mgr` | 24 | gated (ESA dedup) | 1 entity, cluster uuid; 42 labels returned, 24 kept |
| `cluster-esa-dedup-domowner-io` | `<vsan cluster uuid>` [observed] | queried cluster | none | `ESA Dedup DOM Owner` | 24 | gated | 1 entity; 82 returned, 24 kept |
| `cluster-esa-dedup-store-chunksvc` | `<vsan cluster uuid>` [observed] | queried cluster | none | `ESA Dedup Chunk Service` | 27 | gated | 1 entity; 33 returned, 27 kept |
| `cluster-esa-dedup-store-hashsvc` | `<vsan cluster uuid>` [observed] | queried cluster | none | `ESA Dedup Hash Service` | 34 | gated | 1 entity; 39 returned, 34 kept |
| `vsan-dp-historical-stats` | `<vsan cluster uuid>` [observed] | queried cluster | none | `Data Protection` | 1 | none listed | 1 entity, `totalSnapshotCapacity` 64,257,117,696 |
| `cluster-resync` | `<vsan cluster uuid>` [inferred] | runtime landing (V2): cluster uuid to cluster, one node uuid to that host, else `entities_unparsed` | none | `Resync` | 24 | silent; expected empty except during a resync [inferred] | empty echo |
| `cluster-pmem` | `<vsan cluster uuid>` [inferred] | runtime landing | none | `PMem` | 8 | gated (PMem) | fault `NotSupported` `pmemisunavailable` (fault-learned) |
| `cluster-remotedomclient` | `<vsan cluster uuid>` [inferred; server cluster per NICK §4.4, an assumption] | remote rule (§Remote) | none | `Remote DOM Client` | 8 | gated (HCI Mesh) | empty echo |
| `computeCluster-remotedomclient` | `<cluster uuid>` [inferred; client or server ambiguous, NICK §4.4] | remote rule | none | `Compute Remote DOM Client` | 8 | gated (HCI Mesh) | empty echo |

### Host tier (21 types, 234 keys, HostSystem)

| Type | Ref after `:` | Resolves to | Instance | Group | Keys | Feature | Lab |
|---|---|---|---|---|---|---|---|
| `host-cpu` | `<nodeUuid>\|cpu-<n>` and `<nodeUuid>` (aggregate) [observed: 160 + 5] | host by node uuid | `cpu-<n>`; the 1-part aggregate has **no instance** (group `pCPU`, not NICK's `(all)`) | `pCPU[:<cpu>]` | 3 | not gated | 165 entities, 32 CPUs + 1 aggregate per host, node uuids 5/5 |
| `dom-world-cpu` | `<nodeUuid>\|<world name>\|<world id>` [observed] | host | `<world name>-<world id>` (e.g. `VSAN_0x432abcf22c40_CompServer-2099225`) | `DOM World:<world>-<id>` | 3 | not gated | 330 entities = 66 per host (48 CompServer, 6 Owner, 6 OwnerHlpr0, 6 Client); no duplicate name per host; node uuids 5/5 |
| `host-esa-dedup-domcompmgr-io` | `<nodeUuid>` [observed] | host | none | `ESA Dedup DOM Comp Mgr` | 24 | gated | 5 entities; 42 returned, 24 kept |
| `host-esa-dedup-domowner-io` | `<nodeUuid>` [observed] | host | none | `ESA Dedup DOM Owner` | 24 | gated | 5; 82 returned, 24 kept |
| `host-esa-dedup-store-chunksvc` | `<nodeUuid>` [observed] | host | none | `ESA Dedup Chunk Service` | 27 | gated | 5; 33 returned, 27 kept |
| `host-esa-dedup-store-hashsvc` | `<nodeUuid>` [observed] | host | none | `ESA Dedup Hash Service` | 34 | gated | 5; 39 returned, 34 kept |
| `host-vsansparse` | `<nodeUuid>` [observed] | host | none | `vSAN Sparse` | 21 | not gated | 5 entities |
| `rdt-net` | `<nodeUuid>` [observed] | host | none | `RDT Network` | 1 | not gated | 5 entities |
| `system-mem` | `<nodeUuid>` [observed] | host | none | `System Memory` | 3 | not gated | 5 entities; `totalMbMemUsed` 135,857 to 144,622 |
| `lsom-world-cpu` | `<nodeUuid>\|<world name>\|<world id>` [inferred] | host | `<world name>-<world id>` | `LSOM World:<world>-<id>` | 2 | silent (OSA) | empty echo (ESA) |
| `heap-memory` | `<nodeUuid>\|<heap name>` [inferred] | host | `<heap name>` | `Heap:<heap>` | 1 | silent | fault `InvalidArgument: entityRefId` |
| `slab-memory` | `<nodeUuid>\|<slab name>` [inferred] | host | `<slab name>` | `Slab:<slab>` | 1 | silent | fault `InvalidArgument` |
| `clom-host` | `<nodeUuid>` [inferred] | host | none | `CLOM` | 2 | silent | fault `InvalidArgument` |
| `cmmds-workload` | `<nodeUuid>` [inferred] | host | none | `CMMDS Workload` | 23 | silent | fault `InvalidArgument` |
| `vsan-distribution` | `<nodeUuid>` [inferred] | host | none | `Distribution` | 5 | silent | empty echo |
| `host-pmem` | `<nodeUuid>` [inferred] | host | none | `PMem` | 8 | gated (PMem) | fault `NotSupported` |
| `host-remotedomclient` | `<nodeUuid>` [inferred; client host per NICK §4.4] | remote rule | none | `Remote DOM Client` | 11 | gated (HCI Mesh) | empty echo |
| `computeHost-remotedomclient` | `<nodeUuid>` [inferred; ambiguous] | remote rule | none | `Compute Remote DOM Client` | 11 | gated (HCI Mesh) | empty echo |
| `vsan-iscsi-host` | `<nodeUuid>` [inferred] | host | none | `iSCSI` | 10 | gated (iSCSI) | empty echo |
| `vsan-iscsi-target` | `<nodeUuid>\|<target>` [inferred] | host | `<target>` (IQN; `:` kept, V2 `scsi0:0` precedent) | `iSCSI Target:<target>` | 10 | gated | empty echo |
| `vsan-iscsi-lun` | `<nodeUuid>\|<target>\|<lun>` [inferred] | host | `<target>/<lun>` | `iSCSI LUN:<target>/<lun>` | 10 | gated | empty echo |

### Disk tier (3 types, 51 keys, HostSystem instanced by disk uuid)

| Type | Ref after `:` | Resolves to | Instance | Group | Keys | Feature | Lab |
|---|---|---|---|---|---|---|---|
| `disk-group` | `<disk uuid>` [inferred; which disk names the group is unrecorded, NICK §4.3] | disk map (`QueryDisksForVsan`, OSA unverified, V2 Q9) | `<disk uuid>` | `Disk Group:<disk uuid>` | 38 | silent (OSA) | empty echo (ESA) |
| `clom-disk` | `<disk uuid>` [inferred] | disk map | `<disk uuid>` | `CLOM Disk:<disk uuid>` | 3 | silent | fault `InvalidArgument` |
| `ddh-disk` | `<disk uuid>` [inferred] | disk map | `<disk uuid>` | `Disk Health:<disk uuid>` | 10 | silent | fault `InvalidArgument` |

### VM tier (3 types, 15 keys, VirtualMachine)

| Type | Ref after `:` | Resolves to | Instance | Group | Keys | Feature | Lab |
|---|---|---|---|---|---|---|---|
| `remote-virtual-machine` | `<VM uuid>` [inferred] | remote rule: VM in the queried cluster's VM read | none | `Remote VM` | 6 | gated (HCI Mesh) | fault `InvalidArgument` |
| `remote-virtual-disk` | path or disk id [inferred; NICK names it `disk_uuid` but resolves it as a path] | treated as `virtual-disk` PATH form against the device map; a non-path id is `vdisks_unresolved` | bus position `<busN:M>` | `Remote Virtual Disk:<busN:M>` | 3 | gated | fault `InvalidArgument` |
| `remote-vscsi` | `<VM uuid>\|<device>` [inferred] | remote rule | `scsiN:M` | `Remote vSCSI:<scsiN:M>` | 6 | gated | fault `InvalidArgument` |

**Lab summary for the 36:** 14 return entities, 11 empty echo, 11 fault
(9 `InvalidArgument: entityRefId`, 2 `NotSupported`). The 9
`InvalidArgument` types fault the same way MAP test 4 records, which is also
what an unknown prefix returns, so on 9.1.1 they may have no working wildcard
prefix at all (Q5). They cost one ~40 ms call per cluster per day each
(fault learning, V2).

**Group names** are unique per target object; no new name equals an existing
group on the same kind except where V2 B9 already does it on purpose
(`PMem`, `Remote DOM Client`, the dedup groups exist on both cluster and
host as cluster-wide totals and per-host parts). Names come from PY
`KIND_SUFFIX` where it has one (`Resync`, `Data Protection`, `vSAN Sparse`,
`RDT Network`, `System Memory`, `Disk Group`); the rest are new, in V2's
short style. `pCPU` sits apart from the existing `CPU` (`vsan-cpu`, vSAN's
own CPU use), mirroring `pNIC`.

**Instanced plus aggregate in one group** (`host-cpu`): `vSAN Perf|pCPU|<leaf>`
for the per-host aggregate and `vSAN Perf|pCPU:cpu-8|<leaf>` per CPU. Each is
its own entity for dedup marks. T5 browser pass checks the rendering.

**Part-count rule** (V2): an id whose part count differs from the type's
form is skipped and counted in `entities_unparsed` (one WARN per type per
day with the count, not the id). `host-cpu` accepts 1 or 2 parts.

### Remote types (HCI Mesh, compute-only)

| Type | Lands when | Otherwise |
|---|---|---|
| `cluster-remotedomclient`, `computeCluster-remotedomclient` | id equals the queried cluster's vSAN uuid: that ClusterComputeResource | another cluster's uuid, a compute-only cluster's id, any uuid not of this cluster: **`clusters_unresolved`**, dropped |
| `host-remotedomclient`, `computeHost-remotedomclient` | id is one node uuid of the queried cluster: that HostSystem | a host of another cluster or vCenter: **`hosts_unresolved`**, dropped |
| `remote-virtual-machine`, `remote-vscsi` | VM uuid is in the queried cluster's VM read (V2 §VirtualMachine) | **`vms_unresolved`** (the V2 "compute elsewhere, storage here" case), dropped |
| `remote-virtual-disk` | path matches the queried cluster's device map | **`vdisks_unresolved`**, dropped |

Never landed on another in-scope cluster even if its uuid is known: two
clusters' queries can return the same ref (NICK §4.4 "possible double
collection"), and a per-cluster rule cannot double-write. A compute-only
cluster is queried at all only if it passes the vSAN-enabled filter
(unverified, Q6). Cross-vCenter mesh is always unresolved.

### Uncataloged labels

Under `all`, labels outside the catalog are parsed and dropped. On the lab
these are the 41 `Actual` twin labels (24 on `vsan-pnic-net`,
10 on `vsan-tcpip-stats`, 7 on `vsan-vnic-net`) and **210 labels on the 10 ESA
dedup types that the PY model lacks** (18 each on both `*-domclient-io` and
both `*-domcompmgr-io`, 58 each on both `*-domowner-io`, 6 each on both
`*-store-chunksvc`, 5 each on both `*-store-hashsvc`; e.g.
`dedupChunkReadCongestion`, `iopsDedupChunkObjUnmap`,
`latencyAvgDedupChunkReadLeafOwnerLocal`) [observed REC]. They are not keys
in 1.2.0 (C1: the catalog is PY's). Adding them later is additive and safe
(Q3). `PERF tier` reports `labels_dropped`; one INFO line per (type, day)
lists the uncataloged label names (names only, no ids) to feed that decision.

---

## Units: leaf rule for new labels

Precedence, first match wins. Frozen into the catalog (Appendix A), never
computed at run time (V2):

| # | Rule | New leaves |
|---|---|---|
| 1 | **Disputed: label verbatim, no suffix, no transform.** `cluster-pmem`/`host-pmem` `latencyRead`, `latencyWrite` (PY µs vs schema `time_ns`, unadjudicated); `ddh-disk` `avgReadLatency`, `avgWriteLatency` (PY ns vs schema `time_ms`); `disk-group` `outstandingBytesSched` (bytes vs `rate_bytes`); `system-mem` `pctMemUsed` (PY PERMILLE, but REC shows 52 to 56 beside `totalMbMemUsed` 135,857 to 144,622 MB, which reads as percent on a ~256 GB host, not 5.2 %; Q4) | 8 |
| 2 | Label already released on any type: reuse that leaf and its transform (C2). Covers the µs latency family where NICK §6.6 ruled the schema's `time_ms` wrong, the RDT socket-buffer bytes family (`rxSbSpace*`, `txSbSpace*`, `txCtxQ*`, NICK §6.6), `tcpErrs` on `vsan-vnic-net` (released `tcpErrsPct` on TCP/IP despite NICK §6.6's open contradiction) | 301 (106 carry a suffix) |
| 3 | PY `PERMILLE`: value / 10, `Pct` | 4 |
| 4 | PY unit none, `unit unknown`, or schema-only unit (NICK §6.1: the schema unit belongs to a graph, not a series; e.g. `tputDedup*` on the new dedup types, `totalSnapshotCapacity`, `avgPctTimeToPeak`): **no suffix** | 494 |
| 5 | IOPS: no suffix (as released `iopsRead`) | 66 |
| 6 | µs `Us`, B/s `BytesPerSec`, bytes `Bytes`, ms `Ms`, s `Sec`, ns `Ns`, percent `Pct`; **skipped when the label already contains the token as a camelCase word** (`Us`/`USec`/`Sec`/`Bps` for time and rate as V2, `Ms`, `Bytes`, `Pct`/`Percent`), so `highOIODurationMsRead` and `iopsDelayPctSched` stay verbatim. V2 matched only the label's end; the word match reproduces all 451 released leaves (only exception: V2's named `deleteCongestion`) | appended: Us 96, BytesPerSec 75, Bytes 30, Pct 7, Sec 4, Ms 0, Ns 0; verbatim because already named: 58 |
| 7 | Named exception: `totalMbMemUsed` (MB, unit already in the name) verbatim | 1 |

Total new: 1,144 leaves, 322 with a suffix. **A unit settled later never
changes a key**; it goes into REFERENCE.md's Unit column only. `dedupRatio`
stays as served (V2 Q6).

---

## Call plan and budget under `all`

### Per cluster (lab, one 5-host ESA cluster)

Learning as V2: faults learned at once for 24 h; empty echoes after 3
consecutive empties (VM types: 3 VM runs); core types never learned from
empty; `ioinsight` never learned. Serial ms = REC per-call seconds (SOAP;
MAP: JSON per-call p50 is the same or lower).

| Tiers | Scope | Cycle 1 | Cycles 2 to 3 | Steady (cycle 4+) | Serial s steady (cycle 1) |
|---|---|---|---|---|---|
| default (core+host+cluster) | dashboard | 26 | 26 | **23** | 3.6 (4.1) |
| default | **all** | 56 | 50 | **37** | 5.9 (7.9) |
| all four, no VM run | dashboard | 30 | 30 | 25 | 3.9 (4.7) |
| all four, no VM run | **all** | 63 | 55 | **39** | 6.2 (8.8) |
| all four, VM run | dashboard | 33 | 33 | 28 | 4.9 (5.7) |
| all four, VM run | **all** | 69 | 58 | **42** | 7.2 (9.9) |

Steady `all` on the lab = 41 non-empty types + `ioinsight`; 11 fault-learned,
16 empty-learned (list in T5). Daily re-probe spread unchanged (V2).

### 70 clusters x 6 hosts (V2 worked example), 0.19 s per call

| Case | Calls / cycle steady (cycle 1) | Per vCenter 7 calls/s | Per cluster, 4 workers (18 rounds) | Per cluster, 8 workers |
|---|---|---|---|---|
| dashboard, default tiers (today; T4 (a)/(a')) | 1,610 (1,820) | 230 s (260 s) | 79 s | 39 s |
| **all, default tiers** | **2,590 (3,920)** | **370 s (560 s): deadline path every cycle** | **127 s (192 s)** | 63 s (96 s) |
| all, all tiers, VM N=3 (avg 40 per cluster) | 2,800 (~4,550: 63 per cluster, 69 on the third doing a VM run) | 400 s | 137 s | 68 s |

Under the per-vCenter ceiling `all` never fits 240 s at 70 clusters: ~1,680
calls per cycle complete ~45 clusters, rotation gives each cluster data on
about 2 cycles in 3, and a skipped cycle's bucket falls outside the 7-minute
window (a gap, not a delay; R21). Under the per-cluster ceiling it fits with
4 workers. Sharding does not add calls/s under the per-vCenter hypothesis
(V2); what does help is scope per account: `all` on a second account whose
`cluster_include` names a few clusters, `dashboard` on the first with those
clusters in `cluster_exclude`. D9 (Q7) still decides.

### Push volume (70 x 6 example, steady, one bucket per series)

Lab ratios [REC]: per host 1,271 series requested / 1,177 with a value; per
cluster 244 / 243; per ESA disk 54; per VM 82 / 62.3.

| Case | Values / cycle | Bytes at 85.5 B/value (T5-9) | Batches (~1 MB, <= 100 resources) | Push time: 60 ms/call + 1.5 ms/resource (PAK build 18 model) |
|---|---|---|---|---|
| dashboard, default (V2) | 98,350 | 8.4 MB | ~9 | 1.6 s (harness reading) |
| **all, default tiers** | **~511,000 with a value** (550,900 requested) | **~43.7 MB** | ~42 host (10 hosts each, ~101 KB per host) + 2 cluster = **~44** | ~3.4 s; **~26 s if push time scales with bytes** (devel: 97 KB in ~58 ms) [inferred bound] |
| all, all tiers, VM N=3 | ~883,000 (+22,680 disk at 1 disk/host, +~348,700 VM) | ~75 MB | ~44 + ~2 disk + ~56 VM (V2) | unmeasured; the VM share is ~V2's |

Suite API ingest at ~44 MB per cycle is unmeasured (R11 extended, Q9).

### Wire and decode (projection)

Default tiers under `all`, one lab cluster: REC SOAP 15-min sums 130,650 B
wire / 1,424,653 B XML; converted to JSON 7-min with MAP's measured ratios
(x1.20 wire, x1.85 decoded: SOAP 15-min no labels 128 KB / 1.38 MB vs JSON
7-min 153 KB / 2.56 MB) **~157 KB / ~2.6 MB** per cycle, against 32 KB /
409 KB measured at dashboard scope (PROV1+PROV2) [inferred conversion]. At
70 x 6: ~13 MB wire / ~219 MB decoded per cycle (V2: 2.6 / 34 MB). Decoded
bytes are streamed churn, not retained (V2 Sizing req. 3); the GC load on the
collector is the cost (R22). Largest single response stays far under the
4 MB wire cap: `host-domowner` ~5 KB per host unfiltered, ~320 KB at a 64-host
cluster [inferred from REC].

### Heap (estimate; T4 measures)

| Component | dashboard default (measured T4 (a)) | all default (estimate) |
|---|---|---|
| Peak heap delta | 6.3 MB | ~18 MB [inferred] |
| Compact marks: ~64 B per entity + 4 B per label | ~0.9 MB (7,210 entities) | ~5.5 MB (~52,000 entities: 122 per host incl. 66 worlds and 33 CPU entities; 550,900 labels) |
| Result queue: 16 `TypeDone` messages (`max(8, 4 x workers)`, PAK `CycleEngine`), ~140 B per row | < 1 MB | up to ~8 MB (largest message `host-domowner` at 6 hosts: 3,456 rows over 2 buckets) |

### T4 rows to add (pak issue #6 harness, CI-asserted)

| Case | Assertions |
|---|---|
| (d) `all`, default tiers, per vCenter | deadline path every cycle; every cluster completes at least once in any 2 consecutive cycles (rotation); completed clusters push 6 x 1,271 + 244 = 7,870 series each; peak heap < 65 MB (D6) and retained < 35 MB; regression ceiling = 2x the first reading, committed in the same build (build 16 practice) |
| (d') `all`, default tiers, per cluster, 4 workers | all 70 done every cycle; perf phase <= 200 s at cycle 1 (56 calls, model 192 s) and <= 135 s from cycle 4 (37 calls, model 127 s); 2,590 calls at cycle 7; `PERF push` per cycle reported |
| (e) `all`, all tiers, VM N=3, per cluster | all done every cycle; perf phase < 240 s; heap < 65 MB and VM-case ceilings (50 / 35 MB) |

Fixtures: P3 captures, rewritten per synthetic host like the V2 harness
(node uuid, world name and id, cpu ids).

---

## Ops storage impact (the cost of the toggle)

Series per object under `all` vs `dashboard`, lab topology (2 pNICs, 1
stack, 1 vSAN vmk, 32 pCPUs, 66 DOM worlds, 1 ESA disk per host) [REC]:

| Object | dashboard | all | Factor | Shape |
|---|---|---|---|---|
| HostSystem (core + host tier) | 219 | **1,271** | 5.8x | 796 fixed + 41 per pNIC + 22 per stack + 74 per vSAN vmk + 3 per pCPU (+3 aggregate) + 3 per DOM world |
| HostSystem, disk tier, per ESA disk | 10 | **54** | 5.4x | OSA per disk group 38, cache 8, capacity 13 (unobserved) |
| ClusterComputeResource | 91 | **244** | 2.7x | ESA with the dedup types live |
| VirtualMachine | 80 | **82** | 1.03x | `virtual-machine` +2 |
| 70 x 6 example, default tiers | 98,350 | **550,900** | 5.6x | samples/day x288 at 5 min: 28.3 M to 158.7 M |

Plainly: switching an account to `all` multiplies the pak's footprint on
every host by about six and on every cluster by about three; VMs barely move.
Of the per-host growth, 297 series come from `host-cpu` and `dom-world-cpu`,
which scale with core count and DOM worlds, not with storage; on a reboot
`dom-world-cpu` instances (kernel address and world id in the name) are
expected to be replaced by new ones, stranding the old series (no per-key
delete) [inferred; Q8]. What a series costs on the Ops cluster (disk,
memory, node sizing) is in no source here (Q10). Keys pushed under `all` stay
in Ops after a switch back; they stop receiving data.

---

## Failure handling and logging deltas

| Case | Behaviour |
|---|---|
| Label not in catalog (`all`) | dropped; `PERF tier labels_dropped`; INFO once per (type, day) with label names |
| Remote type outside the queried cluster | `clusters_unresolved` / `hosts_unresolved` / `vms_unresolved` / `vdisks_unresolved` (§Remote), dropped |
| New type faults `InvalidArgument: entityRefId` or `NotSupported` | fault-learned 24 h, as V2; not counted in `optional_calls_failed` beyond V2's existing rule |
| Wrong part count on a new type | `entities_unparsed`, WARN once per type per day |
| Scope switched | new engine: learned state and marks reset (§Setting step 5) |

Logging: cycle summary gains `scope=dashboard|all`; `PERF tier` gains
`scope`, `labels_dropped`; `PERF cluster` `calls_by_tier` unchanged in form.
No new `Collection|*` stat.

---

## Prerequisite P3 (blocks parser fixtures and T3/T4 `all` rows only)

REC is pyVmomi SOAP and local-only (RULE-015). Brief `api-cartographer` to
save, under `reference/docs/extracted/vsan-perfsvc-json/` with
`PROVENANCE-<date>-all.md` (RULE-016): one JSON `VsanPerfQueryPerf` per type
for all 69 prefixes, no `labels`, 7-min window, same lab cluster, verbatim
(faults and empty echoes included); plus one read of a lab host's
`hardware.memorySize` (settles Q4). Record per type: labels returned vs PY
model (the 210 dedup extras), entity counts, ref forms.

---

## Test plan deltas

**T1 (offline):** catalog table-driven, 1,595 rows against V2's 451 plus
Appendix A (label, leaf, per-mille flag, scope); one leaf per label across
types; rule 1 to 7 reproduce Appendix A; `labels` present in the request
under `dashboard`, absent under `all`; parser keeps catalog labels and counts
the rest (P3 dedup fixtures: 42 returned, 24 kept); new grammars from P3
(`host-cpu` 1 and 2 parts, `dom-world-cpu` 3 parts, dedup); `exclude_types`
accepts all 69 ids; scope change gives empty learned state and marks; remote
rule with synthetic ids, labelled synthetic.

**T2:** unchanged plus an unfiltered gzip body at the 4 MB cap boundary.

**T3/T4:** rows (d), (d'), (e) above; existing rows unchanged.

**T5 acceptance on devel** (9.0.2 instance against `vcf-lab-mgmt-cl01`,
all four tiers on, N = 3, `perf_timing_logging=true`; then 8.18 and 9.1 per
RULE-019):

| Step | Expected |
|---|---|
| 1. Upgrade from 1.1.0.18 | account keeps `dashboard`; perf_calls 25 / 28, series as before |
| 2. Set `metric_scope=all`, save | cycle 1: `perf_calls` 63 (69 on the VM run); cycles 2 to 3: 55 (58); from cycle 4: **39 (42)** |
| 3. Learned (lab) | fault-learned at cycle 1 (11): `cluster-pmem`, `host-pmem` (NotSupported); `clom-disk`, `clom-host`, `cmmds-workload`, `ddh-disk`, `heap-memory`, `slab-memory`, `remote-virtual-disk`, `remote-virtual-machine`, `remote-vscsi` (InvalidArgument). Empty-learned after 3 cycles (16): `cache-disk`, `capacity-disk`, `disk-group`, `vsan-direct-cluster`, `vsan-direct-host`, `vsan-file-service`, `cluster-resync`, `cluster-remotedomclient`, `computeCluster-remotedomclient`, `host-remotedomclient`, `computeHost-remotedomclient`, `lsom-world-cpu`, `vsan-distribution`, `vsan-iscsi-host`, `vsan-iscsi-target`, `vsan-iscsi-lun`. `ioinsight` every cycle. (`cluster-resync` fills during a resync) |
| 4. `series_pushed` | first cycle ~2x steady (both buckets, marks reset); steady **~6,400** (no VM run) / **~8,270** (VM run), +-5 % [REC with-value counts]; `labels_dropped` ~955 on a VM run (433 shared + 522 dedup); `entities_unparsed`, `*_unresolved` 0 |
| 5. Read-back (wait >= 6 min for the cluster key, V2 P2) | host `vSAN Perf\|System Memory\|totalMbMemUsed` (~135,000 to 145,000); cluster `vSAN Perf\|Data Protection\|totalSnapshotCapacity` (~6.4e10); instanced `vSAN Perf\|pCPU:cpu-0\|pcpuUsedPct` and the aggregate `vSAN Perf\|pCPU\|pcpuUsedPct`; each equal to the cycle's `PERF` log and a same-window JSON query |
| 6. Browser pass | rendering of `pCPU` beside `pCPU:cpu-0`, `DOM World:VSAN_0x..._CompServer-<id>` |
| 7. Set back to `dashboard` | next cycle `perf_calls` 30 (33 on VM run), steady 25 / 28 from cycle 4; series ~2 x 2,994 then ~2,994 (PAK CHANGELOG 1.1.0.18 devel figures); the three read-back keys get no sample newer than the switch; `answered empty` INFO lines reappear at cycle 3 for the 5 dashboard empties (learned state reset) |

Gate order unchanged (V2): validate-sdk, build-sdk, sdk-adapter-reviewer,
pak-compare zero BLOCKING, T5, `v1.2.0.<build>` tag via repo CI and the defect
gate (RULE-012, RULE-014).

---

## REFERENCE.md, docs-gen, CHANGELOG

- **REFERENCE.md:** header "69 entity types, 1,595 keys (451 at dashboard
  scope)"; Settings table gains `metric_scope`; "Collection per cycle" gains
  the `all` rows of §Call plan; every key table gains a **Scope** column
  (`dashboard` for the 451, `all` for the 1,144); the 21 shared sections grow;
  36 new sections in the existing per-tier chapters (lands on, instance,
  lab evidence, feature); "Where keys land" gains the remote rule and the
  `pCPU` aggregate; a Units paragraph lists the 8 disputed leaves and states
  that leaves never change.
- **docs-gen:** `REFERENCE.generated.md` picks up the setting from
  describe.xml + resources.properties (`43=Metric scope`) with no code
  change. `adapter.yaml`: `version: "1.2.0"`, description mentions the
  scope, `stitch_targets.key_groups` gains the new group prefixes (exact
  prefixes, REFERENCE.md carries the scope), HostSystem `instanced_by` gains
  `<cpu>`, `<world>-<id>`, `<heap>`, `<slab>`, `<target>`, `<target>/<lun>`.
- **CHANGELOG 1.2.0.<build>:** "feat(adapter): `metric_scope` (Advanced,
  default `dashboard`, unchanged behaviour). `all` collects every metric of
  the 69 vSAN Performance Service entity types modelled by vsanhostmetrics
  2.0.0: 1,595 keys (+1,144: 686 on 21 existing types, 458 on 36 new types
  onto HostSystem, ClusterComputeResource and VirtualMachine), no labels
  filter. Keys only added. Switching scope restarts learned types and dedup
  marks. Cost under `all`: ~5.8x series per host, ~2.7x per cluster."

## Migration

From 1.1.0.18: in-place, same kind; default `dashboard` means no visible
change and no key renamed. From the Python pack 2.0.0 (which collects
"everything" by default, NICK §8): `all` is the like-for-like comparison,
minus the 2 derived metrics and the 210 uncataloged dedup labels Python also
does not model.

## Request Mapping (delta)

Request 6 of V2 (`VsanPerfQueryPerf <type>:*`) covers 69 types under `all`,
with no `labels`. No new request kinds.

## Events

None (V2).

## Bundled Dashboard

None. `all` keys are for ad-hoc metric browsing and later content.

---

## Key Risks (V1 R1 to R9, V2 R10 to R19 still apply)

- **R20 Volume.** ~5.6x series and ~5x push bytes at the example; Ops-side
  cost unknown (Q10). Mitigation: default stays `dashboard`; scope per
  account; `exclude_types` for `host-cpu` / `dom-world-cpu`.
- **R21 `all` over the deadline under the per-vCenter ceiling** (370 s at 70
  clusters): permanent rotation with gaps. Mitigation: per-account scope on a
  cluster subset; D9 field data.
- **R22 Collector GC churn** ~219 MB decoded per cycle at the example (V1 JVM
  finding on the 9.0.2 node). Mitigation: streaming parse (V2), T4 (d).
- **R23 Unobserved identities.** 22 of 36 new types have inferred ref forms;
  9 fault on 9.1.1. Mitigation: part-count rule, `entities_unparsed`,
  `*_unresolved`; first customer capture becomes a fixture.
- **R24 Instance churn** on `dom-world-cpu` (and `lsom-world-cpu`) across
  host reboots [inferred]. Q8.
- **R25 Units frozen on PY authority** (HCIBench-derived): a later correction
  changes REFERENCE text, never keys; 494 new leaves carry no unit at all.
- **R26 Catalog lags the service:** 210 dedup labels returned on 9.1.1 are
  not keys (Q3).

---

## Open questions

1. **Key count 1,595 vs 1,638.** The design excludes the 41 `Actual` twins
   (identical values) and the 2 Python-derived metrics. Settled by Scott: confirm,
   or name either set to add (twins would be 41 more keys with duplicate
   values; derived would be the pak's first computed metrics).
2. **20 vs 21 shared types.** The count from PY COVERED against the model is
   21 (§Shared types). Settled by Scott naming the type he left out, if any.
3. **The 210 ESA dedup labels the PY model lacks** but 9.1.1 returns. Add to
   the catalog (more keys on the 10 dedup types) or leave out as now.
   Settled by Scott, with P3's committed capture as the source.
4. **`pctMemUsed` per-mille or percent.** Designed verbatim, no transform.
   Settled by P3's `hardware.memorySize` read: if 135,857 MB is ~52 % of the
   host, it is percent and the verbatim key is correct as is.
5. **The 9 types faulting `InvalidArgument: entityRefId` on 9.1.1**
   (`clom-*`, `cmmds-workload`, `ddh-disk`, `heap-memory`, `slab-memory`,
   `remote-*`): no working prefix, or explicit refs needed, or version-bound?
   Settled by an api-cartographer run on an 8.0 U3 or 9.0 vCenter and an
   explicit-ref probe.
6. **HCI Mesh identity.** Which cluster's uuid `*remotedomclient` refs
   carry, and whether a compute-only cluster passes the vSAN-enabled filter.
   Settled by a capture on a mesh (server and client cluster in one vCenter).
7. **Per-vCenter vs per-cluster ceiling (D9)** decides whether `all` fits at
   70 clusters (370 s vs 127 s). Settled by `PERF cycle` from a
   multi-cluster vCenter.
8. **`dom-world-cpu` instance stability.** Keep per-world instances (NICK
   parity, churn on reboot) or exclude the type by default under `all`.
   Settled by comparing world names before and after a lab host reboot.
9. **Suite API ingest at ~44 MB per cycle.** Settled by `PERF push` on
   devel at T5 (one cluster) and field data at scale.
10. **Ops-side cost per series** (disk, memory, node capacity) for
    550,900 series. Settled by ops-recon of devel's per-node metric load
    against the Ops sizing guidance before `all` is recommended to the
    70-cluster customer.

---

## Appendix A: catalog delta (1,144 keys)

Generated by script from PY rc.2 (model minus `Actual` twins, minus COVERED)
and the §Units rules. Format: `label` when the leaf equals the label,
`label→leaf` otherwise. Key = `vSAN Perf|<group>[:<instance>]|<leaf>`.
Released (dashboard) rows are in V2's metric tables and REFERENCE.md and are
not repeated. This list is the contract `EntityTypeTest` checks.

**Per-mille transform (value / 10)** applies to exactly these 15 new keys
(rule 3, or rule 2 reusing a released per-mille row with its transform):
`vsan-pnic-net` `rxPacketsLossRate`, `txPacketsLossRate`; `vsan-tcpip-stats`
`ip6Errs`, `ipErrs`; `vsan-vnic-net` `ip6Errs`, `ipErrs`, `tcpErrs`,
`tcpHalfopenDropRate`, `tcpRcvdupackRate`, `tcpRcvduppackRate`,
`tcpRcvoopackRate`, `tcpSackRcvBlocksRate`, `tcpSackRexmitsRate`,
`tcpSackSendBlocksRate`, `tcpTimeoutDropRate` (NICK §6.4: per-mille on
`vsan-vnic-net` is an assumption carried from the TCP/IP type). No other
new key is transformed.

- **`host-domclient`** (`DOM Client`, core, shared, +72): IOPSWithinBursts, IOPSWithinBurstsExclFirstObj, IOPSWithinBurstsMultiObj, avgBurstArrivalTime→avgBurstArrivalTimeUs, avgBurstArrivalTimeMultiObj, avgBurstCompletionTime→avgBurstCompletionTimeUs, avgBurstCompletionTimeMultiObj, avgBurstPeakOIO, avgBurstPeakOIOMultiObj, avgBurstPeakOutstandingKb, avgBurstPeakOutstandingKbMultiObj, avgBurstTotalTime→avgBurstTotalTimeUs, avgBurstTotalTimeMultiObj, avgPctTimeToPeak, avgPctTimeToPeakMultiObj, bandwidthWithinBursts, bandwidthWithinBurstsExclFirstObj, bandwidthWithinBurstsMultiObj, burstsPerSecond, burstsPerSecondMultiObj, clientCacheHitRate, clientCacheHits, ioCount, iops, iopsSegCleanerUnmap, iopsUnmap, latencyAvg→latencyAvgUs, latencyAvgSegCleanerUnmap→latencyAvgSegCleanerUnmapUs, latencyAvgUnmap→latencyAvgUnmapUs, latencyMaxRead→latencyMaxReadUs, latencyMaxSegCleanerUnmap→latencyMaxSegCleanerUnmapUs, latencyMaxUnmap→latencyMaxUnmapUs, latencyMaxWrite→latencyMaxWriteUs, latencyStddev→latencyStddevUs, latencyStddevRead→latencyStddevReadUs, latencyStddevSegCleanerUnmap→latencyStddevSegCleanerUnmapUs, latencyStddevUnmap→latencyStddevUnmapUs, latencyStddevWrite→latencyStddevWriteUs, lessSkewedMultiBurstsPerSecond, numBurstStatsSkipped, numOio, oioRead, oioRecoveryWrite, oioResyncRead, oioWrite, rateClientOpsBadParam, rateClientOpsChecksumMismatch, rateClientOpsIoError, rateClientOpsLimitExceed, rateClientOpsNoConnect, rateClientOpsNoMem, rateClientOpsNoSpace, rateClientOpsNotSupported, rateClientOpsRetry, rateOtherClientOpsFailure, readCongestion, readCount, segCleanerUnmapCongestion, segCleanerUnmapLeafOwnerLatency→segCleanerUnmapLeafOwnerLatencyUs, segCleanerUnmapLeafOwnerMaxLatencyAvgUs, serverSwitchAvglatency→serverSwitchAvglatencyUs, serverSwitchCount, serverSwitchLatencyMaxUs, throughput→throughputBytesPerSec, throughputRead→throughputReadBytesPerSec, throughputSegCleanerUnmap→throughputSegCleanerUnmapBytesPerSec, throughputUnmap→throughputUnmapBytesPerSec, throughputWrite→throughputWriteBytesPerSec, unmapCongestion, unmapCount, writeCongestion, writeCount
- **`host-domowner`** (`DOM Owner`, core, shared, +250): avgDeltaCreationDomActiveLatency→avgDeltaCreationDomActiveLatencySec, avgDeltaCreationDomCreationLatency→avgDeltaCreationDomCreationLatencySec, avgResyncParallelism, congestion, deltaLeafGTEs, deltaSourceChanges, ecCachedWriteCount, ecCachedWriteHits, ecFswCount, ecStridedWriteCount, ecStridedWriteHits, ecWriteCount, highOIOAvgDurationMs, highOIOAvgDurationMsRead, highOIOAvgDurationMsWrite, highOIOAvgIOCount, highOIOAvgIOCountRead, highOIOAvgIOCountWrite, highOIOAvgOIO, highOIOAvgOIORead, highOIOAvgOIOWrite, highOIOBytes, highOIOBytesRead, highOIOBytesWrite, highOIOCount, highOIOCountPercent, highOIOCountPercentRead, highOIOCountPercentWrite, highOIOCountRead, highOIOCountWrite, highOIODurationMs, highOIODurationMsRead, highOIODurationMsWrite, highOIODurationPercent, highOIODurationPercentRead, highOIONumTimes, highOIONumTimesRead, highOIONumTimesWrite, highOIOThroughput→highOIOThroughputBytesPerSec, highOIOThroughputRead→highOIOThroughputReadBytesPerSec, highOIOThroughputWrite→highOIOThroughputWriteBytesPerSec, ioCount, iopsRead, iopsRecUnmap, iopsRecWrite, iopsResyncRead, iopsWrite, latencyAvg→latencyAvgUs, latencyAvgRecUnmap→latencyAvgRecUnmapUs, latencyAvgRecWrite→latencyAvgRecWriteUs, latencyAvgResyncRead→latencyAvgResyncReadUs, latencyAvgServiceVMRead→latencyAvgServiceVMReadUs, latencyAvgServiceVMWrite→latencyAvgServiceVMWriteUs, latencyStddev→latencyStddevUs, latencyStddevRead→latencyStddevReadUs, latencyStddevRecoveryWrite→latencyStddevRecoveryWriteUs, latencyStddevResyncRead→latencyStddevResyncReadUs, latencyStddevUnmap→latencyStddevUnmapUs, leafGTEs, netSchedAvgCompRecoveryWriteDelayMs, netSchedAvgCompResyncReadDelayMs, netSchedAvgOwnerRecoveryWriteDelayMs, netSchedAvgOwnerResyncReadDelayMs, netSchedBWDiscoveredPerDiscoverySession→netSchedBWDiscoveredPerDiscoverySessionBytesPerSec, netSchedBWDiscoveryActions, netSchedBWDiscoveryAvgIntervalsUs, netSchedBWDiscoverySessions, netSchedBWDiscoveryStopsDueToGainsFromGuestPct, netSchedBWDiscoveryStopsDueToHighLatencyPct, netSchedBWDiscoveryStopsDueToLowUtilizationPct, netSchedBWDiscoveryUtilizationPct, netSchedBWReallocatedPerReallocationSession→netSchedBWReallocatedPerReallocationSessionBytesPerSec, netSchedBWReallocationActions, netSchedBWReallocationAvgIntervalsUs, netSchedBWReallocationSessions, netSchedBWReallocationStopsDueToHighSharePct, netSchedBWReallocationStopsDueToLowUtilizationPct, netSchedBWReallocationUtilizationRatio→netSchedBWReallocationUtilizationRatioPct, netSchedBWReallocationUtilizationRatioAbove, netSchedBWReallocationUtilizationRatioBelow, netSchedBandwidthDiscoveryBps, netSchedGuestIopsDecreasePerDiscoverySession, netSchedGuestIopsIncreasePerReallocationSession, netSchedLatencyIncreaseFromResyncPerDiscoverySessionPct, netSchedResyncGainsFromGuestCount, netSchedResyncIopsDecreasePerReallocationSession, netSchedResyncIopsIncreasePerDiscoverySession, netSchedUnderUtilCount, netSchedUnderUtilGuestBps, netSchedUnderUtilTtlBps, numBlockedDeltaToBaseResyncJobs, numBlockedFullResyncJobs, numBlockedPriorityResyncJobs, numBlockedResyncJobs, numBlockedSharedResyncJobs, numBlockedSiblingToDeltaResyncJobs, numCompleteDeltaToBaseResyncOps, numCompleteFullResyncOps, numCompleteResyncOps, numCompleteResyncRwrBatches, numCompleteRwrOps, numCompleteSiblingToDeltaResyncOps, numInflightDedupResyncJobs, numInflightPriorityResyncJobs, numInflightSharedResyncJobs, numNetSchedCompIops, numNetSchedCompIopsLimit, numNetSchedCompRecoveryWriteIops, numNetSchedCompRecoveryWriteIopsLimit, numNetSchedCompRecoveryWriteTpThrottled→numNetSchedCompRecoveryWriteTpThrottledBytesPerSec, numNetSchedCompResyncReadIops, numNetSchedCompResyncReadIopsLimit, numNetSchedCompResyncReadTpThrottled→numNetSchedCompResyncReadTpThrottledBytesPerSec, numNetSchedCompTpThrottled→numNetSchedCompTpThrottledBytesPerSec, numNetSchedControllerActivations, numNetSchedHighBand, numNetSchedHighBandHighShare, numNetSchedHighBandLowLimit, numNetSchedHighBandSec, numNetSchedHighToLowBand, numNetSchedHighToMidBand, numNetSchedLowBandHighLimit, numNetSchedLowToHighBand, numNetSchedMidBandHighLimit, numNetSchedMidBandLowShare, numNetSchedMidToHighBand, numNetSchedOwnerIops, numNetSchedOwnerIopsLimit, numNetSchedOwnerRecoveryWriteIops, numNetSchedOwnerRecoveryWriteIopsLimit, numNetSchedOwnerRecoveryWriteTpThrottled→numNetSchedOwnerRecoveryWriteTpThrottledBytesPerSec, numNetSchedOwnerResyncReadIops, numNetSchedOwnerResyncReadIopsLimit, numNetSchedOwnerResyncReadTpThrottled→numNetSchedOwnerResyncReadTpThrottledBytesPerSec, numNetSchedOwnerTpThrottled→numNetSchedOwnerTpThrottledBytesPerSec, numNetSchedRecoveryWriteTpThrottled, numNetSchedResyncReadTpThrottled, numNetSchedResyncTotalSharePercent, numNetSchedSeenResyncTpBps, numOio, numPendingDecomResyncJobs, numPendingDedupResyncJobs, numPendingDeltaToBaseResyncJobs, numPendingFullResyncJobs, numPendingResyncJobs, numPendingSiblingToDeltaResyncJobs, numRunningDeltaToBaseResyncJobs, numRunningFullResyncJobs, numRunningResyncJobs, numRunningSiblingToDeltaResyncJobs, numSuspendedDedupResyncJobs, numSuspendedDeltaToBaseResyncJobs, numSuspendedFullResyncJobs, numSuspendedPriorityResyncJobs, numSuspendedResyncChangemaps, numSuspendedResyncJobs, numSuspendedSharedResyncJobs, numSuspendedSiblingToDeltaResyncJobs, oioRead, oioRecoveryWrite, oioResyncRead, oioWrite, ownerECCacheHitMissRatio→ownerECCacheHitMissRatioPct, ownerECCacheNumCachedObjects, ownerECCacheNumFailedAllocs, ownerECCacheNumSuccessAllocs, rateOtherOwnerOpsFailure, rateOwnerOpsBadParam, rateOwnerOpsChecksumMismatch, rateOwnerOpsIoError, rateOwnerOpsLimitExceed, rateOwnerOpsNoConnect, rateOwnerOpsNoMem, rateOwnerOpsNoSpace, rateOwnerOpsNotSupported, rateOwnerOpsRetry, readCongestion, readCount, readECLeafOwnerMaxLatencyAvgUs, readECLeafOwnerMaxLatencyUs, readLeafOwnerIops, readLeafOwnerLatency→readLeafOwnerLatencyUs, readLeafOwnerMaxLatencyAvgUs, readLeafOwnerRetriesPerOp, readLeafOwnerThroughput→readLeafOwnerThroughputBytesPerSec, readOwnerRetriesPerOp, recUnmapCount, recWriteCount, recoveryUnmapCongestion, recoveryUnmapLeafOwnerLatency→recoveryUnmapLeafOwnerLatencyUs, recoveryWriteLeafOwnerLatency→recoveryWriteLeafOwnerLatencyUs, recoveryWriteLeafOwnerLatencyLocal→recoveryWriteLeafOwnerLatencyLocalUs, recoveryWriteLeafOwnerLatencyRemote→recoveryWriteLeafOwnerLatencyRemoteUs, resyncReadCount, resyncReadLeafOwnerLatency→resyncReadLeafOwnerLatencyUs, resyncReadLeafOwnerLatencyLocal→resyncReadLeafOwnerLatencyLocalUs, resyncReadLeafOwnerLatencyRemote→resyncReadLeafOwnerLatencyRemoteUs, resyncsEndedAsDeltaToBase, resyncsStartedAsDeltaToBase, segCleanerUnmapLeafOwnerLatency→segCleanerUnmapLeafOwnerLatencyUs, serverSwitchAvglatency→serverSwitchAvglatencyUs, serverSwitchLatencyMaxUs, serverSwitchlatencyStddev→serverSwitchlatencyStddevUs, throughput→throughputBytesPerSec, totalDeltaCreationDomActiveLatency→totalDeltaCreationDomActiveLatencyUs, totalDeltaCreationDomCreationLatency→totalDeltaCreationDomCreationLatencyUs, totalDeltasCreatedCount, tputRead→tputReadBytesPerSec, tputRecUnmap→tputRecUnmapBytesPerSec, tputRecWrite→tputRecWriteBytesPerSec, tputResyncRead→tputResyncReadBytesPerSec, tputServiceVMRead→tputServiceVMReadBytesPerSec, tputServiceVMWrite→tputServiceVMWriteBytesPerSec, tputUnmap→tputUnmapBytesPerSec, tputWrite→tputWriteBytesPerSec, twoPCBatchCommitBlockedByGuestIOPS, twoPCBatchCommitBlockedByOtherIOPS, twoPCBatchCommitBlockedByResyncIOPS, twoPCBatchCommitBlockedBySyncIOPS, twoPCBatchCommitGuestIOPS, twoPCBatchCommitOtherIOPS, twoPCBatchCommitResyncIOPS, twoPCBatchCommitSyncIOPS, twoPCCommitCount, twoPCCommitSize, twoPCPrepareLimitRetryGuestAvgTimeMs, twoPCPrepareLimitRetryGuestIOPS, twoPCPrepareLimitRetryOtherAvgTimeMs, twoPCPrepareLimitRetryOtherIOPS, twoPCPrepareLimitRetryResyncAvgTimeMs, twoPCPrepareLimitRetryResyncIOPS, twoPCPrepareRetryCount, twoPCReservedLSNExhaustedCount, twoPCReservedLSNUnusedCount, twoPCReservedLSNUsedCount, unmapCongestion, unmapECLeafOwnerMaxLatencyAvgUs, unmapECLeafOwnerMaxLatencyUs, unmapLeafOwnerLatency→unmapLeafOwnerLatencyUs, unmapLeafOwnerMaxLatencyAvgUs, writeCongestion, writeCount, writeECLeafOwnerMaxLatencyAvgUs, writeECLeafOwnerMaxLatencyUs, writeLeafOwnerIops, writeLeafOwnerLatency→writeLeafOwnerLatencyUs, writeLeafOwnerMaxLatencyAvgUs, writeLeafOwnerRetriesPerOp, writeLeafOwnerThroughput→writeLeafOwnerThroughputBytesPerSec, writeOwnerRetriesPerOp
- **`vsan-pnic-net`** (`pNIC`, core, shared, +24, 24 Actual twins dropped): pauseCountRaw, pfcCount, portRxpkts, rxDrp, rxErrRaw, rxFifoErrRaw, rxFrmErr, rxLgtErr, rxOvErrRaw, rxPackets, rxPacketsLossRate→rxPacketsLossRatePct, rxPktRaw, rxThroughput→rxThroughputBytesPerSec, txAbortErr, txCarErrRaw, txDrp, txErrRaw, txFifoErr, txHeartErr, txPackets, txPacketsLossRate→txPacketsLossRatePct, txPktRaw, txThroughput→txThroughputBytesPerSec, txWinErr
- **`cluster-domclient`** (`DOM Client`, cluster, shared, +3): numOio, readCount, writeCount
- **`cluster-domcompmgr`** (`DOM Comp Mgr`, cluster, shared, +3): numOio, throughputRead→throughputReadBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`cluster-domowner`** (`DOM Owner`, cluster, shared, +23): avgDeltaCreationDomActiveLatency→avgDeltaCreationDomActiveLatencySec, avgDeltaCreationDomCreationLatency→avgDeltaCreationDomCreationLatencySec, latencyAvgRecWrite→latencyAvgRecWriteUs, latencyAvgResyncRead→latencyAvgResyncReadUs, numCompleteDeltaToBaseResyncOps, numCompleteResyncRwrBatches, numCompleteRwrOps, numCompleteSiblingToDeltaResyncOps, numOio, numPendingDeltaToBaseResyncJobs, numPendingSiblingToDeltaResyncJobs, numRunningDeltaToBaseResyncJobs, numRunningSiblingToDeltaResyncJobs, numSuspendedDeltaToBaseResyncJobs, numSuspendedFullResyncJobs, numSuspendedPriorityResyncJobs, numSuspendedResyncChangemaps, numSuspendedSharedResyncJobs, numSuspendedSiblingToDeltaResyncJobs, totalDeltasCreatedCount, tputRecWrite→tputRecWriteBytesPerSec, tputResyncRead→tputResyncReadBytesPerSec, unmapCongestion
- **`cluster-rdt-network-latency`** (`RDT Latency`, cluster, shared, +8): rxSbSpaceAvg→rxSbSpaceAvgBytes, rxSbSpaceMax→rxSbSpaceMaxBytes, txCtxQAvg→txCtxQAvgBytes, txCtxQMin→txCtxQMinBytes, txQLatMax→txQLatMaxUs, txQLatMin→txQLatMinUs, txSbSpaceAvg→txSbSpaceAvgBytes, txSbSpaceMax→txSbSpaceMaxBytes
- **`cluster-zdom-top-stats`** (`ZDOM Top Stats`, cluster, shared, +5): iopsUnmap, latencyAvgUnmap→latencyAvgUnmapUs, oioRead, oioWrite, throughputUnmap→throughputUnmapBytesPerSec
- **`vsan-cluster-capacity`** (`Capacity`, cluster, shared, +1): totalDpOverhead→totalDpOverheadBytes
- **`vsan-dp-historical-stats`** (`Data Protection`, cluster, new, +1): totalSnapshotCapacity
- **`cluster-esa-dedup-domcompmgr-io`** (`ESA Dedup DOM Comp Mgr`, cluster, new, +24): dedupChunkReadCount, dedupChunkWriteCount, dedupEngineReadCount, dedupEngineWriteCount, dedupHashReadCount, dedupHashWriteCount, iopsDedupChunkObjRead, iopsDedupChunkObjWrite, iopsDedupEngineRead, iopsDedupEngineWrite, iopsDedupHashObjRead, iopsDedupHashObjWrite, latencyAvgDedupChunkObjRead→latencyAvgDedupChunkObjReadUs, latencyAvgDedupChunkObjWrite→latencyAvgDedupChunkObjWriteUs, latencyAvgDedupEngineRead→latencyAvgDedupEngineReadUs, latencyAvgDedupEngineWrite→latencyAvgDedupEngineWriteUs, latencyAvgDedupHashObjRead→latencyAvgDedupHashObjReadUs, latencyAvgDedupHashObjWrite→latencyAvgDedupHashObjWriteUs, tputDedupChunkObjRead, tputDedupChunkObjWrite, tputDedupEngineRead, tputDedupEngineWrite, tputDedupHashObjRead, tputDedupHashObjWrite
- **`cluster-esa-dedup-domowner-io`** (`ESA Dedup DOM Owner`, cluster, new, +24): dedupChunkReadCount, dedupChunkWriteCount, dedupEngineReadCount, dedupEngineWriteCount, dedupHashReadCount, dedupHashWriteCount, iopsDedupChunkObjRead, iopsDedupChunkObjWrite, iopsDedupEngineRead, iopsDedupEngineWrite, iopsDedupHashObjRead, iopsDedupHashObjWrite, latencyAvgDedupChunkObjRead→latencyAvgDedupChunkObjReadUs, latencyAvgDedupChunkObjWrite→latencyAvgDedupChunkObjWriteUs, latencyAvgDedupEngineRead→latencyAvgDedupEngineReadUs, latencyAvgDedupEngineWrite→latencyAvgDedupEngineWriteUs, latencyAvgDedupHashObjRead→latencyAvgDedupHashObjReadUs, latencyAvgDedupHashObjWrite→latencyAvgDedupHashObjWriteUs, tputDedupChunkObjRead, tputDedupChunkObjWrite, tputDedupEngineRead, tputDedupEngineWrite, tputDedupHashObjRead, tputDedupHashObjWrite
- **`cluster-esa-dedup-store-chunksvc`** (`ESA Dedup Chunk Service`, cluster, new, +27): latencyChangeRefCount→latencyChangeRefCountUs, latencyDeleteChunkExtent→latencyDeleteChunkExtentUs, latencyDeletedObjCleanup→latencyDeletedObjCleanupUs, latencyGetChunkEntries→latencyGetChunkEntriesUs, latencyReserveMba→latencyReserveMbaUs, numChangeRefCount, numDeleteChunkExtent, numDeletedObjCleanup, numGetChunkEntries, numObjsReported, numReserveMba, rateBlocksInChunkDeleted, rateBlocksInChunkWritten, rateChangeRefCount, rateChunkRefEntAdded, rateChunkRefEntRemoved, rateChunksDeleted, rateChunksInChangeRefCount, rateChunksInDeleteChunkExtent, rateChunksInGetChunkEntries, rateChunksWritten, rateDeleteChunkExtent, rateDeletedObjCleanup, rateGetChunkEntries, rateReserveMba, totalNumBlks, totalNumRefCnt
- **`cluster-esa-dedup-store-hashsvc`** (`ESA Dedup Hash Service`, cluster, new, +34): currentGenNum, currentStaleGenNum, latencyDeleteChunksReq→latencyDeleteChunksReqUs, latencyNewDupReq→latencyNewDupReqUs, latencyReadLockWait→latencyReadLockWaitUs, latencyUniqueHashReq→latencyUniqueHashReqUs, latencyWriteLockWait→latencyWriteLockWaitUs, numDeleteChunksReq, numNewDupReq, numObjsReported, numReadLockWait, numUniqHashReq, numWriteLockWait, rateChunkInDeleteChunksReq, rateChunkInNewDupReq, rateChunkInUniqHashReq, rateDedupHashEntryAdded, rateDedupHashEntryRemoved, rateDedupHashEntryUpdated, rateDeleteChunksReq, rateDeletedChunks, rateHashKeyRemovalEntriesPerGen, rateHashKeyRemovalEntriesToScanInStep, rateHashKeyRemovalStepsDone, rateNewDupChunks, rateNewDupReq, rateOldDupChunks, rateReadLockWait, rateRetryChunks, rateSentriesAdded, rateSentriesRemoved, rateUniqChunks, rateUniqHashReq, rateWriteLockWait
- **`cluster-pmem`** (`PMem`, cluster, new, +8): bandwidthRead→bandwidthReadBytesPerSec, bandwidthTotal→bandwidthTotalBytesPerSec, bandwidthWrite→bandwidthWriteBytesPerSec, iopsRead, iopsTotal, iopsWrite, latencyRead, latencyWrite
- **`cluster-remotedomclient`** (`Remote DOM Client`, cluster, new, +8): congestion, iopsRead, iopsWrite, latencyAvgRead→latencyAvgReadUs, latencyAvgWrite→latencyAvgWriteUs, oio, throughputRead→throughputReadBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`cluster-resync`** (`Resync`, cluster, new, +24): iopsResyncReadDecom, iopsResyncReadFixComp, iopsResyncReadPolicy, iopsResyncReadRebalance, iopsResyncWriteDecom, iopsResyncWriteFixComp, iopsResyncWritePolicy, iopsResyncWriteRebalance, latResyncReadDecom→latResyncReadDecomUs, latResyncReadFixComp→latResyncReadFixCompUs, latResyncReadPolicy→latResyncReadPolicyUs, latResyncReadRebalance→latResyncReadRebalanceUs, latResyncWriteDecom→latResyncWriteDecomUs, latResyncWriteFixComp→latResyncWriteFixCompUs, latResyncWritePolicy→latResyncWritePolicyUs, latResyncWriteRebalance→latResyncWriteRebalanceUs, tputResyncReadDecom→tputResyncReadDecomBytesPerSec, tputResyncReadFixComp→tputResyncReadFixCompBytesPerSec, tputResyncReadPolicy→tputResyncReadPolicyBytesPerSec, tputResyncReadRebalance→tputResyncReadRebalanceBytesPerSec, tputResyncWriteDecom→tputResyncWriteDecomBytesPerSec, tputResyncWriteFixComp→tputResyncWriteFixCompBytesPerSec, tputResyncWritePolicy→tputResyncWritePolicyBytesPerSec, tputResyncWriteRebalance→tputResyncWriteRebalanceBytesPerSec
- **`computeCluster-remotedomclient`** (`Compute Remote DOM Client`, cluster, new, +8): congestion, iopsRead, iopsWrite, latencyAvgRead→latencyAvgReadUs, latencyAvgWrite→latencyAvgWriteUs, oio, throughputRead→throughputReadBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`dom-world-cpu`** (`DOM World:<world>-<id>`, host, new, +3): readyPct, runPct, usedPct
- **`host-cpu`** (`pCPU[:<cpu>]`, host, new, +3): coreUtilPct, pcpuUsedPct, pcpuUtilPct
- **`host-domcompmgr`** (`DOM Comp Mgr`, host, shared, +66): congestion, ioCount, iops, iopsRecUnmap, iopsRecWrite, iopsResyncRead, iopsUnmap, latAvgResyncRead→latAvgResyncReadUs, latencyAvg→latencyAvgUs, latencyAvgRecUnmap→latencyAvgRecUnmapUs, latencyAvgRecWrite→latencyAvgRecWriteUs, latencyAvgServiceVMRead→latencyAvgServiceVMReadUs, latencyAvgServiceVMWrite→latencyAvgServiceVMWriteUs, latencyAvgUnmap→latencyAvgUnmapUs, latencyMaxUnmap→latencyMaxUnmapUs, latencyStddev→latencyStddevUs, latencyStddevRead→latencyStddevReadUs, latencyStddevUnmap→latencyStddevUnmapUs, metadataDispatchedCostRead→metadataDispatchedCostReadBytesPerSec, metadataDispatchedCostWrite→metadataDispatchedCostWriteBytesPerSec, metadataQueueDepthRead, metadataQueueDepthWrite, namespaceDispatchedCostRead→namespaceDispatchedCostReadBytesPerSec, namespaceQueueDepthRead, namespaceQueueDepthWrite, numOio, oioRead, oioRecoveryWrite, oioResyncRead, oioWrite, rateCompmgrOpsBadParam, rateCompmgrOpsChecksumMismatch, rateCompmgrOpsIoError, rateCompmgrOpsLimitExceed, rateCompmgrOpsNoConnect, rateCompmgrOpsNoMem, rateCompmgrOpsNoSpace, rateCompmgrOpsNotSupported, rateCompmgrOpsRetry, rateOtherCompmgrOpsFailure, readCongestion, readCount, recUnmapCongestion, recUnmapCount, recWriteCongestion, recWriteCount, regulatorIopsRead, regulatorIopsWrite, resyncDispatchedCostRead→resyncDispatchedCostReadBytesPerSec, resyncDispatchedCostWrite→resyncDispatchedCostWriteBytesPerSec, resyncQueueDepthRead, resyncQueueDepthWrite, resyncReadCount, throughput→throughputBytesPerSec, throughputRecUnmap→throughputRecUnmapBytesPerSec, throughputRecWrite→throughputRecWriteBytesPerSec, throughputUnmap→throughputUnmapBytesPerSec, tputResyncRead→tputResyncReadBytesPerSec, tputServiceVMRead→tputServiceVMReadBytesPerSec, tputServiceVMWrite→tputServiceVMWriteBytesPerSec, unmapCongestion, unmapCount, vmdiskDispatchedCostRead→vmdiskDispatchedCostReadBytesPerSec, vmdiskQueueDepthRead, writeCongestion, writeCount
- **`host-vsansparse`** (`vSAN Sparse`, host, new, +21): cacheAllocFails, cacheEntries, cacheEvictAttempts, cacheHitRate, cacheInserts, cacheLockContentions, cacheRemoves, cacheUpdateLatency→cacheUpdateLatencyUs, iopsGwe, iopsRead, iopsRmw, iopsWrite, iopsWriteConflicts, latencyCacheLookup→latencyCacheLookupUs, latencyGwe→latencyGweUs, latencyRead→latencyReadUs, latencyWrite→latencyWriteUs, lruLockContentions, readsToLayer, throughputRead→throughputReadBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`host-zdom-top-stats`** (`ZDOM Top Stats`, host, shared, +8): ioCount, iopsUnmap, latencyAvgUnmap→latencyAvgUnmapUs, oioRead, readCount, throughputUnmap→throughputUnmapBytesPerSec, unmapCount, writeCount
- **`rdt-net`** (`RDT Network`, host, new, +1): checksumMismatchCount
- **`rdt-network-latency`** (`RDT Latency`, host, shared, +6): rxSbSpaceAvg→rxSbSpaceAvgBytes, txCtxQAvg→txCtxQAvgBytes, txCtxQMin→txCtxQMinBytes, txQLatMin→txQLatMinUs, txSbSpaceAvg→txSbSpaceAvgBytes, txSbSpaceMax→txSbSpaceMaxBytes
- **`system-mem`** (`System Memory`, host, new, +3): overcommitRatio→overcommitRatioPct, pctMemUsed, totalMbMemUsed
- **`vnic-rdt-network-latency`** (`vNIC RDT Latency`, host, shared, +7): rxSbSpaceAvg→rxSbSpaceAvgBytes, rxSbSpaceMax→rxSbSpaceMaxBytes, txCtxQAvg→txCtxQAvgBytes, txCtxQMin→txCtxQMinBytes, txQLatMin→txQLatMinUs, txSbSpaceAvg→txSbSpaceAvgBytes, txSbSpaceMax→txSbSpaceMaxBytes
- **`vsan-host-net`** (`Host Network`, host, shared, +8): ioChainRxdrops, ioChainTxdrops, portRxpkts, portTxpkts, tcpRxErrRate, tcpRxPackets, tcpTxPackets, tcpTxRexmitRate
- **`vsan-memory`** (`Memory`, host, shared, +38): clomdMemAllocMax, clomdMemAllocMin, cmmdsTimeMachineConsumedSize→cmmdsTimeMachineConsumedSizeBytes, cmmdsTimeMachineMemAllocMax, cmmdsTimeMachineMemAllocMin, cmmdsTimeMachineReservedSize→cmmdsTimeMachineReservedSizeBytes, cmmdsdMemAllocMax, cmmdsdMemAllocMin, epdMemAllocMax, epdMemAllocMin, epdReservedSize→epdReservedSizeBytes, osfsdMemAllocMax, osfsdMemAllocMin, osfsdReservedSize→osfsdReservedSizeBytes, uwMemAllocMax, uwMemAllocMin, vitdConsumedSize→vitdConsumedSizeBytes, vitdMemAllocMax, vitdMemAllocMin, vitdReservedSize→vitdReservedSizeBytes, vsandevicemonitordMemAllocMax, vsandevicemonitordMemAllocMin, vsandevicemonitordReservedSize→vsandevicemonitordReservedSizeBytes, vsanmgmtdMemAllocMax, vsanmgmtdMemAllocMin, vsanmgmtdReservedSize→vsanmgmtdReservedSizeBytes, vsanmgmtdWatchdogConsumedSize→vsanmgmtdWatchdogConsumedSizeBytes, vsanmgmtdWatchdogMemAllocMax, vsanmgmtdWatchdogMemAllocMin, vsanmgmtdWatchdogReservedSize→vsanmgmtdWatchdogReservedSizeBytes, vsanobserverConsumedSize→vsanobserverConsumedSizeBytes, vsanobserverMemAllocMax, vsanobserverMemAllocMin, vsanobserverReservedSize→vsanobserverReservedSizeBytes, vsantracedConsumedSize→vsantracedConsumedSizeBytes, vsantracedMemAllocMax, vsantracedMemAllocMin, vsantracedReservedSize→vsantracedReservedSizeBytes
- **`vsan-tcpip-stats`** (`TCP/IP`, host, shared, +10, 10 Actual twins dropped): arpDropRate, ip6Errs→ip6ErrsPct, ip6Total, ipErrs→ipErrsPct, ipTotal, tcpEcnCe, tcpRxPackets, tcpRxThroughput→tcpRxThroughputBytesPerSec, tcpTxPackets, tcpTxThroughput→tcpTxThroughputBytesPerSec
- **`vsan-vnic-net`** (`vNIC`, host, shared, +47, 7 Actual twins dropped): arpDropRate, ioChainDrops, ioChainRxdrops, ioChainTxdrops, ip6Errs→ip6ErrsPct, ip6Total, ipErrs→ipErrsPct, ipTotal, tcpBadrst, tcpBadsyn, tcpConndrops, tcpConnects, tcpDrops, tcpEcnCe, tcpErrs→tcpErrsPct, tcpHalfopenDropRate→tcpHalfopenDropRatePct, tcpKeepdrops, tcpKeeptimeo, tcpPersisttimeo, tcpRcvackpack, tcpRcvbadoff, tcpRcvbadsum, tcpRcvdupack, tcpRcvdupackRate→tcpRcvdupackRatePct, tcpRcvduppack, tcpRcvduppackRate→tcpRcvduppackRatePct, tcpRcvmemdrop, tcpRcvoopack, tcpRcvoopackRate→tcpRcvoopackRatePct, tcpRcvshort, tcpRexmttimeo, tcpRxErrRate, tcpRxPackets, tcpRxThroughput→tcpRxThroughputBytesPerSec, tcpSackRcvBlocks, tcpSackRcvBlocksRate→tcpSackRcvBlocksRatePct, tcpSackRexmits, tcpSackRexmitsRate→tcpSackRexmitsRatePct, tcpSackSendBlocks, tcpSackSendBlocksRate→tcpSackSendBlocksRatePct, tcpSndZeroWin, tcpSndacks, tcpTimeoutDropRate→tcpTimeoutDropRatePct, tcpTimeoutdrop, tcpTxPackets, tcpTxRexmitRate, tcpTxThroughput→tcpTxThroughputBytesPerSec
- **`zdom-vtx`** (`ZDOM VTX`, host, shared, +61): allOpCacheMaxGetLatUSec, cacheMissPerLookupTxn, cacheMissPerPrefetchTxn, cacheMissPerSegCleaningCtxDataTxn, iopsCacheMissRate→iopsCacheMissRatePct, latAvgCacheGet→latAvgCacheGetUs, latAvgTxnBankTotalIO→latAvgTxnBankTotalIOUs, latAvgTxnUnmap→latAvgTxnUnmapUs, latAvgTxnUnmapTotalIO→latAvgTxnUnmapTotalIOUs, missesPerIO, prefetchCacheMaxGetLatUs, rateTotDirtyCachePage, rateTotalBitmapCacheMiss, rateTotalCacheMiss, rateTotalLogicalTreeCacheMiss, rateTotalMiddleTreeCacheMiss, rateTotalSnapTreeCacheMiss, rateTotalSutCacheMiss, rateTxnBankLogicalTreeCacheMiss, rateTxnBankLogicalTreeCacheRef, rateTxnBankMiddleTreeCacheMiss, rateTxnBankMiddleTreeCacheRef, rateTxnBankSutCacheMiss, rateTxnBankSutCacheRef, rateTxnBankTotalCacheMiss, rateTxnBankTotalCacheRef, rateTxnLookupCacheMiss, rateTxnLookupLogicalTreeCacheMiss, rateTxnLookupLogicalTreeCacheRef, rateTxnLookupMiddleTreeCacheMiss, rateTxnLookupMiddleTreeCacheRef, rateTxnPrefetchLogicalTreeCacheMiss, rateTxnPrefetchLogicalTreeCacheRef, rateTxnPrefetchMiddleTreeCacheMiss, rateTxnPrefetchMiddleTreeCacheRef, rateTxnPrefetchSutCacheMiss, rateTxnPrefetchSutCacheRef, rateTxnPrefetchTotalCacheMiss, rateTxnSegCleaningCtxDataLogicalTreeCacheMiss, rateTxnSegCleaningCtxDataLogicalTreeCacheRef, rateTxnSegCleaningCtxDataMiddleTreeCacheMiss, rateTxnSegCleaningCtxDataMiddleTreeCacheRef, rateTxnSegCleaningCtxDataSutCacheMiss, rateTxnSegCleaningCtxDataSutCacheRef, rateTxnSegCleaningCtxDataTotalCacheMiss, rateTxnSegCleaningCtxDataTotalCacheRef, rateTxnUnmapLogicalTreeCacheMiss, rateTxnUnmapMiddleTreeCacheMiss, rateTxnUnmapSutCacheMiss, rateTxnUnmapTotalCacheMiss, tputCacheMissRate→tputCacheMissRatePct, txnBankMaxLatUs, txnCacheFlushMaxLatUs, txnDLogMaxLatUs, txnDelExtMiddleTreeMaxLatUs, txnLookupMaxLatUs, txnPrefetchMaxLatUs, txnSegCtxDataMaxLatUs, txnSegCtxLLPMaxLatUs, txnUnmapMaxLatUs, txnVatWriteSegMaxLatUs
- **`clom-host`** (`CLOM`, host, new, +2): nodeCompCntRatio, nodeDataCompCntRatio
- **`cmmds-workload`** (`CMMDS Workload`, host, new, +23): agentBatchesSent, checkPointBatchesSent, masterBatchesRecved, rxAccept, rxAgentUpdateRequest, rxHeartbeatRequest, rxMasterUpdate, rxMisc, rxRetransmitRequest, rxSnapshot, totalUpdInBatchCkpt, totalUpdInMasterBatches, totalUpdSentInAgentBatch, txAgentUpdateRequest, txHeartbeatRequest, txMasterCheckpoint, txMasterCkptTried, txMasterUpdate, txMasterUpdateTried, txRetransmitRequest, txSnapshot, txSnapshotBytes, txSnapshotTried
- **`computeHost-remotedomclient`** (`Compute Remote DOM Client`, host, new, +11): congestion, iopsRead, iopsUnmap, iopsWrite, latencyAvgRead→latencyAvgReadUs, latencyAvgUnmap→latencyAvgUnmapUs, latencyAvgWrite→latencyAvgWriteUs, oio, throughputRead→throughputReadBytesPerSec, throughputUnmap→throughputUnmapBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`heap-memory`** (`Heap:<heap>`, host, new, +1): heapUtil→heapUtilPct
- **`host-esa-dedup-domcompmgr-io`** (`ESA Dedup DOM Comp Mgr`, host, new, +24): dedupChunkReadCount, dedupChunkWriteCount, dedupEngineReadCount, dedupEngineWriteCount, dedupHashReadCount, dedupHashWriteCount, iopsDedupChunkObjRead, iopsDedupChunkObjWrite, iopsDedupEngineRead, iopsDedupEngineWrite, iopsDedupHashObjRead, iopsDedupHashObjWrite, latencyAvgDedupChunkObjRead→latencyAvgDedupChunkObjReadUs, latencyAvgDedupChunkObjWrite→latencyAvgDedupChunkObjWriteUs, latencyAvgDedupEngineRead→latencyAvgDedupEngineReadUs, latencyAvgDedupEngineWrite→latencyAvgDedupEngineWriteUs, latencyAvgDedupHashObjRead→latencyAvgDedupHashObjReadUs, latencyAvgDedupHashObjWrite→latencyAvgDedupHashObjWriteUs, tputDedupChunkObjRead, tputDedupChunkObjWrite, tputDedupEngineRead, tputDedupEngineWrite, tputDedupHashObjRead, tputDedupHashObjWrite
- **`host-esa-dedup-domowner-io`** (`ESA Dedup DOM Owner`, host, new, +24): dedupChunkReadCount, dedupChunkWriteCount, dedupEngineReadCount, dedupEngineWriteCount, dedupHashReadCount, dedupHashWriteCount, iopsDedupChunkObjRead, iopsDedupChunkObjWrite, iopsDedupEngineRead, iopsDedupEngineWrite, iopsDedupHashObjRead, iopsDedupHashObjWrite, latencyAvgDedupChunkObjRead→latencyAvgDedupChunkObjReadUs, latencyAvgDedupChunkObjWrite→latencyAvgDedupChunkObjWriteUs, latencyAvgDedupEngineRead→latencyAvgDedupEngineReadUs, latencyAvgDedupEngineWrite→latencyAvgDedupEngineWriteUs, latencyAvgDedupHashObjRead→latencyAvgDedupHashObjReadUs, latencyAvgDedupHashObjWrite→latencyAvgDedupHashObjWriteUs, tputDedupChunkObjRead, tputDedupChunkObjWrite, tputDedupEngineRead, tputDedupEngineWrite, tputDedupHashObjRead, tputDedupHashObjWrite
- **`host-esa-dedup-store-chunksvc`** (`ESA Dedup Chunk Service`, host, new, +27): latencyChangeRefCount→latencyChangeRefCountUs, latencyDeleteChunkExtent→latencyDeleteChunkExtentUs, latencyDeletedObjCleanup→latencyDeletedObjCleanupUs, latencyGetChunkEntries→latencyGetChunkEntriesUs, latencyReserveMba→latencyReserveMbaUs, numChangeRefCount, numDeleteChunkExtent, numDeletedObjCleanup, numGetChunkEntries, numObjsReported, numReserveMba, rateBlocksInChunkDeleted, rateBlocksInChunkWritten, rateChangeRefCount, rateChunkRefEntAdded, rateChunkRefEntRemoved, rateChunksDeleted, rateChunksInChangeRefCount, rateChunksInDeleteChunkExtent, rateChunksInGetChunkEntries, rateChunksWritten, rateDeleteChunkExtent, rateDeletedObjCleanup, rateGetChunkEntries, rateReserveMba, totalNumBlks, totalNumRefCnt
- **`host-esa-dedup-store-hashsvc`** (`ESA Dedup Hash Service`, host, new, +34): currentGenNum, currentStaleGenNum, latencyDeleteChunksReq→latencyDeleteChunksReqUs, latencyNewDupReq→latencyNewDupReqUs, latencyReadLockWait→latencyReadLockWaitUs, latencyUniqueHashReq→latencyUniqueHashReqUs, latencyWriteLockWait→latencyWriteLockWaitUs, numDeleteChunksReq, numNewDupReq, numObjsReported, numReadLockWait, numUniqHashReq, numWriteLockWait, rateChunkInDeleteChunksReq, rateChunkInNewDupReq, rateChunkInUniqHashReq, rateDedupHashEntryAdded, rateDedupHashEntryRemoved, rateDedupHashEntryUpdated, rateDeleteChunksReq, rateDeletedChunks, rateHashKeyRemovalEntriesPerGen, rateHashKeyRemovalEntriesToScanInStep, rateHashKeyRemovalStepsDone, rateNewDupChunks, rateNewDupReq, rateOldDupChunks, rateReadLockWait, rateRetryChunks, rateSentriesAdded, rateSentriesRemoved, rateUniqChunks, rateUniqHashReq, rateWriteLockWait
- **`host-pmem`** (`PMem`, host, new, +8): bandwidthRead→bandwidthReadBytesPerSec, bandwidthTotal→bandwidthTotalBytesPerSec, bandwidthWrite→bandwidthWriteBytesPerSec, iopsRead, iopsTotal, iopsWrite, latencyRead, latencyWrite
- **`host-remotedomclient`** (`Remote DOM Client`, host, new, +11): congestion, iopsRead, iopsUnmap, iopsWrite, latencyAvgRead→latencyAvgReadUs, latencyAvgUnmap→latencyAvgUnmapUs, latencyAvgWrite→latencyAvgWriteUs, oio, throughputRead→throughputReadBytesPerSec, throughputUnmap→throughputUnmapBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`lsom-world-cpu`** (`LSOM World:<world>-<id>`, host, new, +2): readyPct, usedPct
- **`slab-memory`** (`Slab:<slab>`, host, new, +1): slabUtil→slabUtilPct
- **`vsan-distribution`** (`Distribution`, host, new, +5): components, domClients, domColocated, domOwners, ioComponents
- **`vsan-iscsi-host`** (`iSCSI`, host, new, +10): bandwidthRead→bandwidthReadBytesPerSec, bandwidthTotal→bandwidthTotalBytesPerSec, bandwidthWrite→bandwidthWriteBytesPerSec, iopsRead, iopsTotal, iopsWrite, latencyRead→latencyReadUs, latencyTotal→latencyTotalUs, latencyWrite→latencyWriteUs, queueDepth
- **`vsan-iscsi-lun`** (`iSCSI LUN:<target>/<lun>`, host, new, +10): bandwidthRead→bandwidthReadBytesPerSec, bandwidthTotal→bandwidthTotalBytesPerSec, bandwidthWrite→bandwidthWriteBytesPerSec, iopsRead, iopsTotal, iopsWrite, latencyRead→latencyReadUs, latencyTotal→latencyTotalUs, latencyWrite→latencyWriteUs, queueDepth
- **`vsan-iscsi-target`** (`iSCSI Target:<target>`, host, new, +10): bandwidthRead→bandwidthReadBytesPerSec, bandwidthTotal→bandwidthTotalBytesPerSec, bandwidthWrite→bandwidthWriteBytesPerSec, iopsRead, iopsTotal, iopsWrite, latencyRead→latencyReadUs, latencyTotal→latencyTotalUs, latencyWrite→latencyWriteUs, queueDepth
- **`vsan-esa-disk-layer`** (`ESA Disk Layer`, disk, shared, +33): avgLatReadPerf, avgLatUnmapCapacity, avgLatUnmapPerf, iopsReadPerf, iopsUnmapCapacity, iopsUnmapPerf, iopsWritePerf, maxReadTimeCapacity, maxReadTimePerf, maxUnmapTimeCapacity, maxUnmapTimePerf, maxWriteTimeCapacity, maxWriteTimePerf, minReadTimeCapacity, minReadTimePerf, minUnmapTimeCapacity, minUnmapTimePerf, minWriteTimeCapacity, minWriteTimePerf, readCountCapacity, readCountPerf, tputReadCapacity, tputReadDiskCapacity, tputReadDiskPerf, tputReadPerf, tputUnmapCapacity, tputUnmapPerf, tputWriteCapacity, tputWritePerf, unmapCountCapacity, unmapCountPerf, writeCountCapacity, writeCountPerf
- **`vsan-esa-disk-scsifw`** (`ESA Disk SCSI`, disk, shared, +11): ioCountDevRead, ioCountDevUnmap, ioCountDevWrite, iopsDevRead, iopsDevUnmap, iopsDevWrite, latencyDevUnmap→latencyDevUnmapUs, outstandingCmdCount, throughputDevRead→throughputDevReadBytesPerSec, throughputDevUnmap→throughputDevUnmapBytesPerSec, throughputDevWrite→throughputDevWriteBytesPerSec
- **`clom-disk`** (`CLOM Disk:<disk uuid>`, disk, new, +3): diskCompCntRatio, diskDataCompCntRatio, diskgrpDataCompCntRatio
- **`ddh-disk`** (`Disk Health:<disk uuid>`, disk, new, +10): avgReadIOPS, avgReadLatency, avgReadTPut→avgReadTPutBytesPerSec, avgUnmapIOPS, avgUnmapLatency→avgUnmapLatencyUs, avgUnmapTPut, avgWriteIOPS, avgWriteLatency, avgWriteTPut, logCongestion
- **`disk-group`** (`Disk Group:<disk uuid>`, disk, new, +38): componentCongestionReadSched, componentCongestionWriteSched, diskgroupCongestionReadSched, diskgroupCongestionWriteSched, iopsDelayPctSched, iopsDirectSched, iopsResyncRead, iopsResyncReadDecom, iopsResyncReadFixComp, iopsResyncReadPolicy, iopsResyncReadRebalance, iopsResyncWrite, iopsResyncWriteDecom, iopsResyncWriteFixComp, iopsResyncWritePolicy, iopsResyncWriteRebalance, latResyncRead→latResyncReadUs, latResyncReadDecom→latResyncReadDecomUs, latResyncReadFixComp→latResyncReadFixCompUs, latResyncReadPolicy→latResyncReadPolicyUs, latResyncReadRebalance→latResyncReadRebalanceUs, latResyncWrite→latResyncWriteUs, latResyncWriteDecom→latResyncWriteDecomUs, latResyncWriteFixComp→latResyncWriteFixCompUs, latResyncWritePolicy→latResyncWritePolicyUs, latResyncWriteRebalance→latResyncWriteRebalanceUs, latencySched→latencySchedUs, outstandingBytesSched, tputResyncRead→tputResyncReadBytesPerSec, tputResyncReadDecom→tputResyncReadDecomBytesPerSec, tputResyncReadFixComp→tputResyncReadFixCompBytesPerSec, tputResyncReadPolicy→tputResyncReadPolicyBytesPerSec, tputResyncReadRebalance→tputResyncReadRebalanceBytesPerSec, tputResyncWrite→tputResyncWriteBytesPerSec, tputResyncWriteDecom→tputResyncWriteDecomBytesPerSec, tputResyncWriteFixComp→tputResyncWriteFixCompBytesPerSec, tputResyncWritePolicy→tputResyncWritePolicyBytesPerSec, tputResyncWriteRebalance→tputResyncWriteRebalanceBytesPerSec
- **`virtual-machine`** (`VM`, vm, shared, +2): readCount, writeCount
- **`remote-virtual-disk`** (`Remote Virtual Disk:<busN:M>`, vm, new, +3): NIOPS, NIOPSDelayed, iopsLimit
- **`remote-virtual-machine`** (`Remote VM`, vm, new, +6): iopsRead, iopsWrite, latencyRead→latencyReadUs, latencyWrite→latencyWriteUs, throughputRead→throughputReadBytesPerSec, throughputWrite→throughputWriteBytesPerSec
- **`remote-vscsi`** (`Remote vSCSI:<scsiN:M>`, vm, new, +6): iopsRead, iopsWrite, latencyRead→latencyReadUs, latencyWrite→latencyWriteUs, throughputRead→throughputReadBytesPerSec, throughputWrite→throughputWriteBytesPerSec

---

## Addendum: Decisions 2026-11-07 (orchestrator, Scott's toggle decision)

Resolutions of §Open questions. Where a decision differs from the body, the
decision wins; the body is not edited.

| Q | Decision |
|---|---|
| Q1 | 1,595 keys: no `*Actual` twins, no pack-computed metrics |
| Q2 | 21 shared types; the design's count stands |
| Q3 | The 210 lab-returned ESA dedup labels are **in scope under `all`**, catalogued from the P3 capture (api-cartographer: `reference/docs/extracted/vsan-perfsvc-json/all-<type>.json`, `PROVENANCE-2026-11-07-all.md`, and a P3 section in the vSAN API map). They are added to the 1,595 of Q1 (210 on the lab, final count from P3); their leaves follow §Units |
| Q4 | `pctMemUsed` pushed as served (verbatim, no transform) until P3's arithmetic settles it |
| Q5 | The 9 types faulting `InvalidArgument: entityRefId` are **optional types**: fault isolated, counted in `optional_calls_failed`, learned-empty after **three consecutive faults** with the re-probe spread (replaces "fault-learned at once" for these 9 in §New types, §Call plan and T5 step 3). P3 retries them by explicit entityRefId and on the 9.0 and 8.18 vCenters |
| Q6 | Remote types resolve **only to an in-scope cluster uuid**; otherwise skipped and counted in `clusters_unresolved`, WARN once per refresh (replaces the per-kind counters in §Remote types) |
| Q7, Q9, Q10 | Field and T5 measurements |
| Q8 | `dom-world-cpu` per-world instances and their churn on reboot accepted; documented in REFERENCE.md and README |

---

## 1.2.1: Performance Service disabled (2026-11-08)

Scott, 2026-11-08: "If the performance service is disabled we should cleanly
skip it and there should be an alert." Version **1.2.1**, build **24**
(`v1.2.1.24`). Additive to 1.2.0; earlier sections stand. Grounding:
`knowledge/context/api-maps/vsan-osa-host-side.md` §1 (OSA-MAP),
`knowledge/context/reviews/vsanperf-t5-devel-9.0-build-22-all-scope-all-tiers.md`
(T5-22: the probe cluster costs 26 calls at `dashboard`, 61 to 67 at `all`,
every cycle, pins `clusters_failed=1` and occupies `last_error`).

| # | Decision |
|---|---|
| D1 Detection | One `VsanClusterGetConfig` (`/sdk/vim25/<release>/vsan/VsanVcClusterConfigSystem/vsan-cluster-config-system/VsanClusterGetConfig`, same namespace and session as the perf call) per in-scope cluster per cycle, first thing in the cluster task, over the existing JSON transport and session, under `call_timeout_seconds` and the cycle deadline. **Enabled iff `perfsvcConfig.enabled == true`.** Absent key or `false` = disabled (both shapes, since enable-then-disable is unverified, OSA-MAP §1). Call failure or unparseable body = **unknown**: proceed exactly as 1.2.0, push no state value (no guess). Not cached: every cycle (12 to 48 ms, ~0.7 KB, OSA-MAP; 70 clusters x 48 ms is ~3.4 s of worker time spread over `max_parallel_clusters`), so an enable or disable shows within one cycle. Not counted in `perf_calls` |
| D2 Skip | A disabled cluster makes **zero perf calls** and none of the tier inventory reads that only serve perf (`QueryDisksForVsan`, VM ContainerView). It is a fourth outcome beside ok / failed / timed out: not in `clusters_ok`, `clusters_failed` or `clusters_timed_out`; does not set `last_error`; is never `lastAttempted`, `restartAt` or in `cutLastCycle` (does not consume rotation order). New self-metric **`Collection\|clusters_perfsvc_disabled`** (count). `clusters_in_scope` still counts it. INFO once on each transition ("Performance Service disabled on <moid> (<name>); perf collection skipped" / "...enabled; collecting"), never per cycle. On a disabled-to-enabled transition the cluster's learned state and dedup marks are cleared so its first enabled cycle re-probes. Cycle summary gains `perfsvc_disabled=N` |
| D3 masternotfound | Unchanged on a cluster D1 reads as enabled or unknown: counted failed, `last_error` set, not learned. A stats-primary re-election (OSA-MAP §1, unverified) stays visible; the config read, not the fault, decides "disabled" |
| D4 Cluster key | One metric, **`vSAN Perf\|Performance Service\|enabled`**, 1 = enabled, 0 = disabled, no unit suffix (unitless flag), pushed every cycle on every in-scope ClusterComputeResource whose D1 read was definite, both states, so the symptom can cancel. Own group, not `Collection`: `Collection\|*` means adapter-instance self-metrics in this pak (README, REFERENCE), and a cluster-side `Collection` group would read as one. Grammar kept (`vSAN Perf\|<group>\|<metric>`). Cost: one series per cluster, one value per cycle (70 clusters = 70 values against ~2,994 to ~8,270 per cycle): accepted |
| D5 No property | The brief's companion property `Performance Service = enabled/disabled` is **dropped for 1.2.1**. The push path is stats-only (`CycleEngine` `pushStats`; the only string push, `pushStringProperty`, targets the adapter instance's `last_error`); a property onto a VMWARE object needs a new Suite API call and test surface for a value the metric already carries. Revisit if a user wants it in Summary |
| D6 Symptom key | Metric, not property: a metric symptom re-evaluates on each pushed value and cancels on the next 1. A property symptom holds the last string indefinitely. Whether a metric symptom cancels when values stop (pak removed, cluster out of scope) is **unverified**; T5 step 4 checks it |
| D7 Cluster map | The cluster-object map (`refreshClusterMap`) is today read only with `tier_cluster` on (`CycleEngine` line 694). From 1.2.1 it is read whenever a cluster is in scope (same 12-cycle cadence), so D4 lands with `tier_cluster=false`. A cluster with no Ops object counts in `clusters_unresolved`, as the cluster tier does |

**Content shipped in the pak** (`content/sdk-adapters/vsanperf/symptoms/`,
`alerts/`, `recommendations/`, listed under `bundled_content:` in
`adapter.yaml` as the Synology pak does). `ops-recon` first (RULE-003):
**does a native vSAN alert already cover "performance service disabled"**
(vSAN adapter health-check alerts land on the vSAN cluster object, not
ClusterComputeResource)? If one exists and is on by default, report it to
Scott before authoring; his decision stands either way. Then
`symptom-author`, then `alert-author`, serially.

| Item | Spec |
|---|---|
| Symptom | `[VCF Content Factory] vSAN Performance Service Disabled`; adapter kind `VMWARE`, resource kind `ClusterComputeResource`; metric static, `vSAN Perf\|Performance Service\|enabled` `<` 1; severity WARNING; `wait_cycles: 2` (one Ops cycle of slack for the ~6 min cluster read-back, T5-22/V2 P2), `cancel_cycles: 1` (clear on the first 1) |
| Alert | `[VCF Content Factory] vSAN Performance Service Is Disabled on Cluster`; criticality **WARNING**: nothing is broken in the workload, the cluster just loses its performance history; Immediate would rank it beside capacity and component faults. Impact **RISK**: a monitoring gap is a future-problem exposure (degradation would go unseen), not current health; vSAN's own health check rates it yellow, which agrees. Type/subtype: storage / configuration (alert-author picks the codes); wait/cancel 1/1 (the symptom carries the debounce) |
| Recommendation | `[VCF Content Factory] Enable the vSAN Performance Service`: "In the vSphere Client select the cluster, then Configure > vSAN > Services > Performance Service > Edit, and enable it. Until it is enabled, VCF Content Factory vSAN Performance collects no vSAN performance metrics for this cluster or its hosts and VMs; collection starts on the first cycle after it is enabled." |

**Test plan.**

T1 (offline, `EngineTest` on `T.CLOCK`; replay fixtures
`tests/fixtures/vsan-perfsvc-json/vsanclustergetconfig-{enabled,absent}.json`
copied verbatim from `reference/docs/extracted/vsan-osa-probe/01-esa-` and
`01-osa-vsanclustergetconfig.json`, plus a synthetic, labelled
`vsanclustergetconfig-false.json` for `{"enabled": false}`):
- absent and false: zero perf calls for that cluster, `clusters_perfsvc_disabled` 1,
  `clusters_failed`/`clusters_timed_out` 0, `last_error` none, value 0 pushed on its cluster
  resource, `lastAttempted`/`restartAt` never that cluster (two-cluster rotation case);
- enabled: perf calls as 1.2.0, value 1 pushed;
- config fault / timeout / bad JSON: perf calls as 1.2.0, no value pushed, not counted disabled;
- enabled + `masternotfound` on every type: failed, `last_error` set (D3);
- disabled then enabled: learned state and marks cleared for that cluster only, INFO once per transition;
- `tier_cluster=false`: cluster map still read, value still pushed (D7);
- `ReplayBudgetTest`: config call outside `perf_calls`, inside the deadline.

T5 on devel 9.0.2 (`dashboard`, tier_host/cluster true, disk/vm false, N 3,
as T5-22 pre-state). Scope: `vcf-lab-mgmt-cl01` (on) and
`vcf-lab-osa-probe-cl01` (off).

| Step | Expected |
|---|---|
| 1. Upgrade from build 22 | new engine: cl01 26 for cycles 1 to 3, then **`perf_calls` 23** (not 49), `clusters_failed` 0, `clusters_perfsvc_disabled` 1, `last_error` none, no probe `masternotfound` WARN |
| 2. Read-back (>= 6 min) | `vSAN Perf\|Performance Service\|enabled` 0 on the probe cluster, 1 on cl01 |
| 3. Alert | active on the probe cluster within 2 Ops cycles of the first 0; none on cl01 |
| 4. Scott enables the service on the probe (vCenter write, his) | next cycle INFO transition line, value 1, alert cancels within 1 cycle; `perf_calls` 49 (23 + 26) on cycles 1 to 3 after, then ~46 if the OSA probe learns the same 3 dashboard empties as cl01 (OSA `disk-group`/`cache-disk`/`capacity-disk` may answer data where ESA is empty, OSA-MAP §2; the steady figure is recorded, not gated); probe hosts receive keys |
| 5. Optional, Scott disables again | capture the `VsanClusterGetConfig` body to settle absent vs `enabled:false` after enable-then-disable (api-cartographer, RULE-016); value 0, alert back. Also remove the probe from `cluster_include` and record whether the alert cancels when values stop (D6) |

Then 8.18 and 9.1 per RULE-019 (no disabled cluster there: check
`clusters_perfsvc_disabled` 0, value 1, no alert).

**Describe / docs / version.**
- `describe.xml`: `Collection` group gains `clusters_perfsvc_disabled`,
  `nameKey="44"`, dataType float; `resources.properties` `44=Clusters with Performance Service disabled`.
  The cluster key is stitched (ARIA_OPS onto VMWARE): no describe entry, no label/unit.
- `adapter.yaml`: `version: "1.2.1"`, `bundled_content:` symptoms/alerts/recommendations,
  `stitch_targets.key_groups` gains `vSAN Perf|Performance Service`.
- CHANGELOG `1.2.1.24`: "feat(adapter): a cluster whose vSAN Performance Service is disabled is
  skipped (one `VsanClusterGetConfig` per cycle, no perf calls, not failed); new
  `Collection|clusters_perfsvc_disabled`; new cluster key `vSAN Perf|Performance Service|enabled`
  (0/1); bundled symptom, alert and recommendation."
- README: acceptance **check 8** = the T5 table above.
- REFERENCE.md: adapter-instance table gains `clusters_perfsvc_disabled`; a new
  "ClusterComputeResource: Performance Service (always on)" section with one row,
  `vSAN Perf|Performance Service|enabled`, source `VsanClusterGetConfig`, unit none,
  Scope **both**; "Collection per cycle" notes disabled clusters make 0 perf calls;
  a Bundled content section names the three items. (One key, not two: D5.)

**D8 (added 2026-11-08): a server fault is isolated to its type.** Live on devel 9.0.2: with the probe's service now on, `cluster-rdt-network-latency` faults every call (HTTP 500 `SystemError`, "no such column: kaReset", a vSAN stats-DB defect on this OSA 9.0 cluster), and the account showed `clusters_failed=1`, 43 calls (not 46) and 1,633 series (not ~1,934).
- **Verified from the adapter log (devel 9.0.2, build 22, 2026-11-08 13:29Z to 13:54Z; extract sections A, B, E):** what fails the probe every cycle is the **core** type `vsan-pnic-net`: "vSphere fault SystemError: A general system error occurred: RuntimeError('no such column: pfcCountRaw. DB error code: 1, please check log file for details') (HTTP 500)". `clusterTask` (~1700 to 1740) sets FAILED on a core-tier fault but does not break, so the rest is still pushed (1,633 series). The `kaReset` fault (same text with `kaReset`) hits three **optional** types: `cluster-rdt-network-latency`, `rdt-network-latency`, `vnic-rdt-network-latency`. They are isolated today but never learned (only `faultStrikes` types strike out), so the trio of WARNs repeats every hourly refresh and the calls repeat every cycle. Both are Performance Service SQLite schema errors on this OSA 9.0 cluster, server-side. The 3 calls the probe makes fewer than cl01 are `cluster-zdom-top-stats`, `host-zdom-top-stats` and `zdom-vtx` learned empty (OSA has no zDOM), not faults. The probe makes 20 calls at `dashboard`, cl01 23: 43 total. Only four things abort a cluster's remaining calls: `NotAuthenticated` twice, `ManagedObjectNotFound`, a timeout, and a stop.
- **Rule (any tier):** a server fault (HTTP 500 vSAN fault, unparseable fault body, or `IOException` other than a timeout) on any type is a **type fault**. The cluster continues. After 3 consecutive faulting cycles (VM tier: VM runs) the type is learned-skipped on that cluster for 24 h and re-probed with the existing spread. WARN at the first fault, INFO at learn, both once per cluster and type per refresh. `faultStrikes` becomes the default for every type except `ioinsight` (exempt) and `isTypeUnavailable` (learned at once, as today). `last_error` = "cluster <moid>: <type>: <fault>" while the type is being called. It reads `none` from the cycle after learning, because a skipped type has no error to report and the learned-skips count plus the INFO line carry it.
- **Not type faults (unchanged):** `masternotfound` on an enabled or unknown cluster (D3: cluster failed, not learned), timeouts (TIMED_OUT, abort), `NotAuthenticated`, `ManagedObjectNotFound`, batching-fault keys (ERROR, a pack defect, cluster failed).
- **A cluster counts as failed only when:** the session fails (`NotAuthenticated` after a fresh login), its MoRef is gone (`ManagedObjectNotFound`), `masternotfound` per D3, every perf call it made this cycle failed (W1 rule, kept; config call excluded, zero calls = OK), or the post-call path throws. The vCenter login and the inventory read stay cycle failures, as today. A config-call failure alone is never a cluster failure (D1: unknown).
- **Counters (1.2.0 semantics kept):** `optional_calls_failed` keeps its meaning (non-core type faults). New `Collection|required_calls_failed` (nameKey 45, `45=Required (core) type calls failed`) counts core-type faults, which no longer fail the cluster.
- **T1 (EngineTest, `T.CLOCK`):** cluster-tier `SystemError` with later types still called, counted, cluster OK; learned at fault 3, call count -1 from cycle 4, `last_error` none, re-probed after 24 h simulated; core-type fault counted in `required_calls_failed`, cluster OK; an answer between faults resets the strikes; every-call-failed is still FAILED; `masternotfound` and timeout paths unchanged. Fixtures `queryperf-fault-systemerror-pfccountraw.json` (core) and `queryperf-fault-systemerror-kareset.json` (optional) under `tests/fixtures/vsan-perfsvc-json/`: class `SystemError` and faultstring **verbatim from the log lines** (the log carries the fault text, not the raw body), in the HTTP 500 JSON envelope of `reference/docs/extracted/vsan-osa-probe/05-osa-queryperf-disk-group.json`; the provenance line says exactly that. api-cartographer may still capture the raw bodies (RULE-016).
- **T5 (probe on, `dashboard`, both clusters):** build 22 today: 43 calls, `clusters_failed` 1. 1.2.1, cycles 1 to 3 after learned state settles: `clusters_failed` 0, `required_calls_failed` 1 (`vsan-pnic-net`), `optional_calls_failed` 5 (`vsan-cpu`, `vsan-memory` and the three RDT latency types; measured on build 24), `last_error` names one of them. From cycle 4: both counters 0, steady **37 calls** (43 - 6; cl01 23, probe 14), learned skips +6, `last_error` none. The probe's hosts lose those six types' keys while learned; accepted, they never answer. README check 8 gains: "A type that faults on the server (devel: `cluster-rdt-network-latency` on the OSA probe) is counted, named in `last_error` for three cycles, then skipped for 24 h; the cluster is never counted failed for it."

**1.2.1 amendments, 2026-11-08, after build 23 review** (`knowledge/context/reviews/vsanperf-build-23-review.md`). Orchestrator decisions 2026-11-08 under Scott's direction ("If the performance service is disabled we should cleanly skip it and there should be an alert"); the B1 narrowing (parsed faults only, strikes commit only on an OK cluster) is to be confirmed by Scott. These supersede the D2, D3 and D8 text above where they differ.
- **D8, what strikes:** only a server-side vSphere fault with a fault class (`SystemError`, `InvalidArgument`, `NotFound`, ...) strikes its type. A transport `IOException` never strikes and keeps 1.2.0 handling: a 5xx with no fault body (`StatusException`), a connection reset, a read error, or an over-cap body (`OverCapException`).
- **D8, when strikes commit:** at the end of the cluster task, and only when the cluster ends OK with at least one successful call. A cluster where every call failed is FAILED and learns nothing; that cycle's strikes are dropped, because a fault on every call is not a type fault (review B1: a 3-cycle 503 outage learned every type and went silent-OK).
- **D8, all learned:** a cluster whose types are all learned-skipped makes zero calls. It WARNs once per refresh and `last_error` reads "cluster <moid>: all types learned-skipped; no perf call this cycle". Only zero calls triggers that. **Deliberate:** a cluster whose core types are all learned-skipped but whose other types answer counts `clusters_ok` (the OSA schema-fault probe is exactly that case).
- **D3 (changed from "unchanged"):** `masternotfound` fails the cluster on **any** tier (1.2.0 failed it on core only) and **breaks** the cluster loop, so a disabled cluster whose config read was unknown makes 1 failing call, not 26 to 67. CHANGELOG says so.
- **D2, re-enable:** dedup marks are **not** cleared on a disabled-to-enabled transition. They are keyed by entity and label and only suppress buckets already pushed; newer buckets supersede. Only the cluster's learned types and its disk-map and VM-read state are reset.
- **Alert content, names as authored:** alert `[VCF Content Factory] vSAN Performance Service disabled on cluster (vSAN Perf collection paused)`, recommendation `[VCF Content Factory] vSAN Enable Performance Service`. Alert type **storage** (18), replacing build 23's `type: 16` (Virtualization/Hypervisor, review N5). Record both in `knowledge/designs/alerts/vsanperf-performance-service-disabled.md`.
- **Tests added by the review:** the verbatim `05-osa-queryperf-disk-group.json` capture as a fixture, asserting `VsanFault.parse(...).isMasterNotFound()` plus one engine cycle through it (W1). Engine cases: a 3-cycle 503 outage then recovery (no learning, FAILED throughout, data on the first good cycle); masternotfound on a non-core type gives FAILED with the loop broken; all types learned gives `last_error` set.
