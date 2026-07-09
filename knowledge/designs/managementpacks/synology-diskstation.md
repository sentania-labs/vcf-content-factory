# Synology DiskStation Management Pack — Design Intent

**Status:** Resume — cartographer gap-fill in progress, architecture decision pending
**Author of intent:** orchestrator (this session)
**Date:** 2026-05-18

> **Resume note (2026-05-18).** This is NOT a greenfield ask. A prior
> workstream (2026-04-15 → 2026-04-29) produced an approved design
> (`designs/synology-mp-v1.md`, Strategy C, 5 INTERNAL kinds), a built
> pak (`dist/mpb_synology_nas.1.0.0.1.pak`, since uninstalled), and a
> dead-end on per-volume IO chaining (`SYNO.Core.System.Utilization`
> doesn't echo the chain key — MPB cannot bind it). The session ended
> with two paths: drop the chain and ship thin MPB, or pivot to the
> Operations Adapter SDK. The MP YAML source was never committed; only
> the pak survives.
>
> **Two facts have changed since that session that re-open MPB as a
> viable path:**
>
> 1. The repo now contains `content/managementpacks/vsphere_storage_paths.yaml`
>    — a pure ARIA_OPS stitching MP that pushes metrics directly onto
>    VMWARE HostSystem and VMWARE Datastore objects. That pattern
>    sidesteps the chaining wall: instead of attaching Synology-side IO
>    to a Synology Volume (chained, no echo, MPB blocks), we push IO
>    onto the VCF Ops Datastore (ARIA_OPS, no chain needed).
> 2. The user's current request explicitly asks for **stitching to
>    ESXi hosts and VMs using the NAS** — which is precisely what
>    ARIA_OPS objects are for. The original 2026-04 design treated
>    stitching as deferred v3 scope; it is now v1 scope.

## Initial Prompt

User (verbatim):

> I would like to monitor my synology disk station with VCF Operations.
> I use it in my home lab as an iscsi target for a number of hosts, as
> well as a NFS backend for some shared datastores across all of them.
> I also use it as an SMB/nfs mount of windows and linux systems.  It'd
> be nice to pull key performance and capacity metrics into VCF Ops, and
> provide a unified view against some of the hosts using it and the
> virtual machines runnning on it.

### Clarifying answers

| Question | Answer |
|---|---|
| DSM version | DSM 7.2.x (live target is DS1520+ on DSM 7.3.2 per existing API maps) |
| Data source | DSM Web API (`/webapi/entry.cgi`, session auth) — NOT SNMP, NOT Prometheus |
| Metric priorities | Volume/pool capacity + health; iSCSI LUN performance; NFS share performance; Disk SMART + RAID health; system CPU + memory (nice-to-have) |
| Stitching | Full topology: Synology Volume/LUN/Export → VMware Datastore → ESXi Host → VM (lights up VCF Ops built-in storage-path tracing) |

## Vision

A management pack that gives the home-lab operator one place in VCF
Operations to see:

1. **Is the NAS healthy?** Pool state, RAID state, disk SMART, fan, UPS
   (if attached), system temperature, CPU/memory headroom.
2. **Is the NAS fast enough for what's running on it?** Per-volume,
   per-LUN, and per-NFS-share IOPS, throughput, and latency.
3. **What's running on this NAS, and is it suffering?** The killer
   feature — clicking a Synology volume or LUN should surface the
   ESXi datastores backed by it, the hosts mounting those datastores,
   and the VMs running on them, with their performance metrics
   alongside the Synology-side numbers.

The "unified view" is the differentiator. SNMP cards and the DSM UI
already show health and performance in isolation. What VCF Ops can
uniquely add is the **storage path** — answering "my VM is slow, is
my NAS the cause?" with one click instead of three tools.

## Candidate architectures (decision pending)

### A. INTERNAL-only (resurrect 2026-04 design as-is)

Take `knowledge/designs/synology-mp-v1.md`'s 5-kind topology (Diskstation
singleton, Storage Pool, Volume, Disk, SSDCache, iSCSI LUN), drop
the chained `volume_util` metricSet (the showstopper), accept lost
per-volume IO. Add NFS Share once cartography returns. **No
stitching to VMware objects.** User opens the Synology adapter tree
and the VMware tree separately and correlates by eye.

- Pros: closest to prior design, fastest to ship.
- Cons: loses per-volume / per-LUN IO. No "VM slow, is NAS at
  fault?" path. Does not satisfy the user's verbatim ask for a
  unified view.

### B. ARIA_OPS-only (vsphere_storage_paths pattern)

Two ARIA_OPS object kinds. No INTERNAL kinds. Push Synology-side
metrics directly onto:

- `VMWARE HostSystem` (Synology-derived: capacity exposed to host,
  per-LUN IO, NFS share IO if available, fan/temp/health summary
  for the NAS this host depends on).
- `VMWARE Datastore` (Synology-derived: backing volume status,
  pool health, disk SMART summary, per-export IO for NFS, per-LUN
  IO for iSCSI).

- Pros: zero new objects in the VCF Ops tree, full integration
  with built-in storage-path views, sidesteps the chain problem.
- Cons: NAS health metrics (system temp, fan, UPS, disk SMART)
  have no natural home — they'd land on every Host/Datastore in
  duplicate, which is wrong. Doesn't fit the "monitor the
  Synology" half of the ask.

### C. Hybrid (recommended)

INTERNAL kinds for what's intrinsic to the NAS itself + ARIA_OPS
kinds for stitching.

**INTERNAL side** (six kinds, all bound to the adapter instance):
- Synology Diskstation (singleton — system health, CPU, memory,
  temp, fan, uptime)
- Storage Pool (capacity + RAID health)
- Volume (capacity only — no chained IO; IO goes via ARIA_OPS)
- Disk (SMART + temp + health)
- iSCSI LUN (metadata + capacity only — IO goes via ARIA_OPS)
- NFS Export (metadata + capacity only — IO goes via ARIA_OPS,
  pending cartographer confirmation that per-share IO is available)
- UPS (optional, lab has one)

**ARIA_OPS side** (two kinds, push to existing VMware objects):
- VMWARE Datastore stitch — receives per-datastore IO derived from
  the Synology LUN or NFS export backing it (read/write IOPS,
  throughput, latency, plus volume_status / pool_status enums).
  Join: Synology LUN naa-derived serial ↔ Datastore VMFS extent
  diskName; Synology NFS export path ↔ Datastore NAS remotePath.
- VMWARE HostSystem stitch — receives aggregate IO + NAS-health
  rollup for the NAS this host depends on. Join via host's
  mounted iSCSI target IQN or NFS mount path.

- Pros: fully expresses the user's intent. NAS-intrinsic metrics
  live on Synology objects; storage-path linkage lives on VMware
  objects. Sidesteps the chain problem (Volume IO is no longer on
  Volume).
- Cons: largest authoring surface. Stitching join keys need
  empirical confirmation (cartographer task #4).

## Cartographer findings (2026-05-18) — resolve open gaps

### NFS (`knowledge/context/api-maps/synology-nfs.md`)

- ✅ NFS service status alertable (`SYNO.Core.FileServ.NFS get` v3).
- ✅ NFS export inventory: 11 shares, 9 NFS-exported. `SYNO.Core.Share list` + `SYNO.Core.FileServ.NFS.SharePrivilege load` per-share. Empty `rule[]` → exists but not NFS-exported.
- ✅ Per-export client count: `SYNO.Core.CurrentConnection get` filtered by `descr == share_name`.
- ❌ **Per-share NFS IO is NOT exposed.** Only aggregate server-wide row in `Utilization`. Fallback: per-volume IO via `space.volume[]` (already mapped) attributed to the parent volume's exports.
- 🎯 Cartographer recommends: NFS Export as a first-class object type, child of Volume.

### Stitching (`knowledge/context/api-maps/synology-vcfops-stitching.md`)

- ✅ **iSCSI key:** `lun.uuid` → NAA via deterministic transform → match Datastore `resourceIdentifiers.DataStrorePath = "VMFS:|naa.6001405<25-hex>|"`. Verified live (2 LUN/Datastore pairs).
- ✅ **NFS key:** `<nas-ip>/<vol_path-no-slash>/<share-name>` → match Datastore `DataStrorePath`. Emit one row per (NIC IP × share) pair. Verified live (3 NFS datastores).
- ✅ **Topology free:** Datastore → Host and Datastore → VM edges already encoded by VMWARE adapter. MP declares `relationships: []`.
- ⚠️ **Tooling check needed:** does YAML grammar support computing `lun.uuid → NAA` string, or does renderer need a `compute_field:` knob? Flagged as §4.2 in the stitching map. May become a TOOLSET GAP.

## Scope decisions

### Architecture: **Hybrid (C) — LOCKED pending user confirmation**

Both cartographer outputs confirm the Hybrid architecture is fully
viable. The April per-volume IO blocker is structurally avoided: IO
goes onto VMware Datastore via ARIA_OPS (one Utilization request per
cycle, multiple rows stitched by export path / NAA), not chained onto
a Synology Volume.

### In scope (v1)

**INTERNAL kinds** (NAS-intrinsic, 7 total):

| Object type | Source | Carries |
|---|---|---|
| Synology Diskstation (`is_singleton: true`) | DSM.Info + Core.System + Utilization (root) + FanSpeed + Interface + System.Status + FileServ.NFS | Model, serial, firmware, CPU/mem, sys temp, fan, uptime, NFS service status |
| Storage Pool | Storage.CGI.Storage load_info | Pool capacity, RAID type, status |
| Volume | Storage.CGI.Storage load_info | **Capacity only** (no chained IO — IO goes via ARIA_OPS to Datastore) |
| Disk | Storage.CGI.Storage load_info | SMART status, temp, remain_life, model, slot |
| iSCSI LUN | Core.ISCSI.LUN + Core.ISCSI.Target | Metadata, capacity, target IQN — **no chained IO** |
| NFS Export *(new, per cartographer rec)* | Core.Share list + FileServ.NFS.SharePrivilege load + CurrentConnection | Metadata, capacity, NFS rules, active client count |
| UPS | ExternalDevice.UPS | Battery, runtime, mode (optional, present in lab) |

**ARIA_OPS kinds** (stitch to existing VMware Datastores, 2 total):

| Object type | Bind | Source | Carries |
|---|---|---|---|
| Synology iSCSI Datastore Health *(new)* | `VMFS:\|naa.6001405<hex>\|` → VMWARE Datastore `DataStrorePath` | Core.ISCSI.LUN + Utilization (lun[]) | Per-LUN IOPS/throughput/latency, LUN status, backing volume/pool health rollup |
| Synology NFS Datastore Health *(new)* | `<nas-ip>/<vol_path>/<share>` → VMWARE Datastore `DataStrorePath` | Core.Share + Utilization (space.volume[] attributed) | Per-volume IOPS/throughput, share status, kerberos required flag, active NFS client count, backing volume/pool health rollup |

No explicit `relationships:` — Datastore→Host and Datastore→VM
already encoded by the VMware adapter. The unified view is one click:
Datastore → its Synology-side health and IO appears alongside the
built-in datastore metrics.

### Out of scope (v1 — defer to v2)

- Docker containers on the NAS (already mapped, but unrelated to the
  storage-for-vSphere story). Keep YAML stub so v2 only needs to flip
  a flag.
- SMB share performance for non-VMware mounts (Windows/Linux SMB
  consumers). User mentioned but didn't prioritize. Reachable via
  the same SMB endpoints if v1 succeeds.
- SSD Cache as a separate object (deferred per existing map note).
- Events (Synology notifications). Pak builder currently strips events
  per `context/mpb_pak_structural_reference.md` — TOOLSET GAP exists.
  Health/state derived from polling metrics instead.

## Key Design Risks

1. **Dual-parent for Disk** — Disk should be a child of both Storage
   Pool and Diskstation. Flagged in the existing overview map (#6).
   MPB support for dual parents needs validation during MPB Verify.
   Fallback: pick Pool as the canonical parent, surface Diskstation
   linkage as a property.

2. **Stitching identifier mapping** *(blocking — cartographer task #4)*.
   For iSCSI: we need a stable join key between the Synology side
   (LUN UUID / target IQN / LUN serial) and the VCF Ops side
   (HostSystem mounted iSCSI target IQN, VMFS datastore naa
   identifier). For NFS: Synology export path (e.g.
   `/volume1/nfs-share`) needs to match the VCF Ops NFS datastore's
   remote path field. Both need to be empirically confirmed before
   the designer commits to a stitching strategy.

3. **NFS share metric availability** *(blocking — cartographer task #3)*.
   The existing maps don't cover NFS. If Synology doesn't expose
   per-export IO via the Web API, v1 may have to fall back to
   per-volume IO (already mapped) and skip the per-share dimension.

4. **Hard Rule 8: adapter_kind from display name.** MP display name
   will be `VCF Content Factory Synology DiskStation` (prose prefix,
   no brackets per CLAUDE.md MP carve-out). Derived adapter_kind:
   `mpb_vcf_content_factory_synology_diskstation`. The prior pak's
   `mpb_synology_nas` is non-conformant with the current factory
   convention; the dist artifact is stale.

5. **Per-volume / per-LUN / per-share IO via chaining is dead.**
   The 2026-04-29 empirical investigation proved that
   `SYNO.Core.System.Utilization` doesn't echo the chain key, and
   MPB's objectBinding requires self-reference. The hybrid
   architecture sidesteps this by pushing IO via ARIA_OPS to VMware
   objects instead — but a v2 Synology-side IO view (per Volume,
   per LUN, per Share) is therefore NOT exposed in VCF Ops. If the
   user later wants that, the SDK pivot path (or a custom adapter)
   is the only route.

## Adapter kind reconciliation (3 candidates floating around)

| adapter_kind | Origin | Status |
|---|---|---|
| `mpb_synology_nas` | Built into `dist/mpb_synology_nas.1.0.0.1.pak` (uninstalled). | **Retire.** Predates factory display-name convention. |
| `mpb_synology_dsm` | 23 orphan symptom/alert/recommendation files in `content/`. | **Retire.** Never matched any built pak. Was authored against an assumption. |
| `mpb_vcf_content_factory_synology_diskstation` | Derived from new factory display name per Hard Rule 8. | **Adopt.** |

The pak in `dist/` will be regenerated under the new adapter_kind
during build. The 23 orphan content files will be re-bound to the
new adapter_kind during the "reconcile orphan content" step (task #8).

## Reconciliation with existing repo content

There are pre-existing standalone files under `content/` (symptoms,
alerts, recommendations) prefixed `synology_*`. ops-recon task #1
will determine what object type they bind to. Outcomes:

- **If they reference object types matching this MP's design** —
  promote them into the MP-namespaced symptom/alert set during
  authoring.
- **If they reference different/phantom types** — note as orphans;
  the user can decide whether to delete or rebind them after the
  MP is installed.

## Implementation outcome (2026-05-19)

**Architecture pivot:** The design started as Hybrid (C) with MPB
ARIA_OPS stitching, but was built as a **Tier 2 native Java SDK
adapter** instead. The Synology API's cross-endpoint joining
requirement (trigger #2) and the NAA transform (trigger #9) made
Tier 1/MPB unviable. See `knowledge/context/tier_decision_framework.md`.

**Final object model (build 1.0.0.9, 23 objects on devel):**

| Object type | Count | Metrics | Relationships |
|---|---|---|---|
| SynologyDiskstation | 1 | 41 (CPU, memory, network, NFS, fan, temp) | → StoragePool |
| SynologyStoragePool | 1 | 3 (capacity) | → Volume, → 7 Disks |
| SynologyVolume | 1 | 9 (capacity, IO, cache hit rates) | → iSCSI LUNs, → NFS Exports, → SSD Cache |
| SynologyDisk | 7 | 5 IO + 4 health each | ← StoragePool (incl 2 NVMe cache) |
| SynologyIscsiLun | 3 | 6 IO each | ← Volume, → VMWARE Datastore (1 of 3 stitched) |
| SynologyNfsExport | 8 | 4 each | ← Volume, → VMWARE Datastore (2 of 8 stitched) |
| SynologySsdCache | 1 | 6 (hit rates, capacity) | ← Volume |

**Cross-MP stitching confirmed (3 relationships):**
- iSCSI LUN `d023e190` → `vcf-lab-wld01-cl01-iscsi` (via NAA)
- NFS Export `wld01` → `vcf-lab-nfs-wld01` (via export path)
- NFS Export `vcf9` → `vcf-lab-mgmt01-nfs` (via export path)

**Deferred to v2:** Docker containers, SMB shares, events, UPS
(no UPS available in current lab config).

**Lessons learned:** `context/lessons_synology_sdk_2026_05_19.md`
(21 numbered lessons across pak structure, runtime, stitching, icons).

**Framework components built:** ForeignResourceResolver,
RelationshipBuilder, SimpleJson — all in `vcfcf-adapter-base.jar`.

This file is the prompt-of-record. Author agents may read it; they
may not rewrite the user's verbatim prompt above.
