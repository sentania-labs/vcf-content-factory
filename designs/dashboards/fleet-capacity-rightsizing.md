# Design — [VCF Content Factory] Fleet Capacity & Rightsizing (dashboard)

## Initial prompt

> I'd like to build a dashboard to review the capaity of my VCF fleet. The
> dashboard should include a breakdown of capacity by CPU< memory and storage.
>
> I'd also like it to include some highlights for rightsizing opporutnities.

Clarifications (AskUserQuestion):
- **Drill depth:** Fleet summary + per-cluster capacity + VM rightsizing list.
- **Rightsizing focus:** Oversized VMs (reclaimable vCPU/mem), Undersized VMs,
  Snapshots & orphaned disk. (Idle/powered-off not emphasized.)
- **Data source:** Built-in metrics only — fully portable, no super-metric dependency.

## Vision

A single fleet-capacity dashboard, built entirely on built-in VCF Ops
capacity-analytics metrics (demand model — the `alloc` model is not enabled on
this instance). Top-down: a fleet summary scoreboard, a per-cluster CPU/memory/
storage capacity table that doubles as the primary selector, three capacity-
pressure heatmaps (CPU/Mem/Storage), then rightsizing highlights — oversized and
undersized VM lists plus a datastore reclaimable-space list (snapshots + orphaned
disk). Selecting a cluster in the capacity table filters the VM and datastore
lists. No super metrics, custom groups, or symptoms required.

Recon: ops-recon agent a64d3889c4a779a10. Fleet = 1 vSphere World, 2 clusters,
6 hosts, 54 VMs, 8 datastores. No built-in or repo dashboard covers this.

## Wireframe (12-column grid) — APPROVED

```
┌───────────────────────────────────────────────────────────────────────────┐
│ BAND A · Scoreboard — "Fleet Summary"          x0 w12  h2   (subject: World)│
│  Clusters | Hosts | VMs | Powered-off VMs | Reclaimable vCPU |              │
│  Reclaimable Mem (GB) | Potential $ Savings (oversized)                     │
├───────────────────────────────────────────────────────────────────────────┤
│ BAND B · View embed — "Cluster Capacity Breakdown" (LIST) x0 w12 h4         │
│  ★ PRIMARY SELECTOR. One row per cluster. Columns grouped CPU|Mem|Storage:  │
│  Cluster | CPU rem(MHz) | CPU usable | CPU use% | CPU days |                │
│          | Mem rem | Mem usable | Mem use% | Mem days |                     │
│          | Disk rem(GB) | Disk total | Disk use% | Disk days |              │
│          | Most-constrained rem% | Most-constrained days                    │
├──────────────────────┬──────────────────────┬─────────────────────────────┤
│ BAND C-1 Heatmap CPU │ BAND C-2 Heatmap Mem  │ BAND C-3 Heatmap Storage     │
│  x0 w4 h4            │  x4 w4 h4             │  x8 w4 h4                    │
│  subj Cluster        │  subj Cluster        │  subj Cluster               │
│  size cpu usable     │  size mem usable     │  size disk total            │
│  color CPU use%      │  color Mem use%      │  color Disk use%            │
├──────────────────────┴───────────┬──────────┴─────────────────────────────┤
│ BAND D-1 View "Oversized VMs"     │ BAND D-2 View "Undersized VMs"          │
│  x0 w6 h4                         │  x6 w6 h4                               │
│  VM | Cluster | vCPU to remove |  │  VM | Cluster | vCPU to add |           │
│  Mem to remove (GB)              │  Mem to add (GB)                        │
├───────────────────────────────────────────────────────────────────────────┤
│ BAND E · View "Datastore Reclaimable Space" (LIST)   x0 w12 h4              │
│  Datastore | Total | Used% | Free | Snapshot space | Orphaned disk          │
└───────────────────────────────────────────────────────────────────────────┘
```

### Widget types
- Band A: Scoreboard (metrics bound directly in dashboard YAML, subject = vSphere World, pinned to world).
- Band B: View embed (list view `[VCF Content Factory] Cluster Capacity Breakdown`).
- Band C: 3× Heatmap (ClusterComputeResource).
- Band D: 2× View embed (`Oversized VMs — Reclaimable`, `Undersized VMs — Add Resources`).
- Band E: View embed (`Datastore Reclaimable Space`).

### Interaction wiring
- Band B selection → drives Bands D-1, D-2, E (filter to selected cluster). No selection = fleet-wide.
- Bands A and C are self-providing / fleet-wide (not driven by selection).

## Metric keys (built-in, demand model — confirmed live)

**vSphere World (Band A):**
`summary|total_number_clusters`, `summary|total_number_hosts`, `summary|total_number_vms`,
`summary|number_poweredOff_vms`, `compute_reclaimable|oversized|oversized_vcpus_toberemoved`,
`compute_reclaimable|oversized|oversized_memory_toberemoved`, `cost|potential_savings|oversized_vms`.

**ClusterComputeResource (Bands B, C):** see view note `cluster-capacity-breakdown.md`.

**VirtualMachine (Band D):** `summary|oversized(|vcpus|memory)`, `summary|undersized(|vcpus|memory)`.

**Datastore (Band E):** `capacity|total_capacity`, `capacity|usedSpacePct`, `capacity|available_space`,
`diskspace|snapshot`, `reclaimable|orphaned_disk|diskspace`.

## Known constraints
- **Demand model only** — `OnlineCapacityAnalytics|*|alloc|*` NOT collecting.
- **Heatmap empty-groupBy crashes renderer** (lesson `heatmap-empty-groupby-crashes-renderer.md`):
  emit the 9-key self-grouping block per heatmap, never `groupBy:{}`.
- Storage heatmap color: confirm a cluster disk usage % key; else color by
  `diskspace|total_usage` sized by `diskspace|total_capacity`.
- At 2 clusters heatmaps show 2 tiles each — thin now, scales with the fleet. By design.
