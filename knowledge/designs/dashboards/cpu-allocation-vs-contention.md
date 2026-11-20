# [VCF CF] CPU Allocation vs Contention

- **Type:** dashboard
- **Slug:** cpu-allocation-vs-contention
- **Authored YAML:** content/dashboards/cpu_allocation_vs_contention.yaml
- **Date:** 2026-11-20
- **Status:** drafted (wireframe approved in plan mode 2026-11-20, with the single highlight column split in two)

## Initial prompt

> Hello I'd like to do the following combination sof things:
> 1> Identify any built in dashboards for capacity, vCPU : pvCPU allocation, contention etc;
> 2> if none exist author some examples that show capacity based on vCPU: pCPU guidlines (https://blogs.vmware.com/cloud-foundation/2025/06/04/vcpu-to-pcpu-ratio-guidelines/)
> https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations/8-18/vmware-aria-operations-configuration-guide-8-18/optimizing-capacity-and-improving-performance/capacity-optimization-concepts/allocation-and-demand-model-in-workload-optimization.html
>
> We may have some that exist, but i'd like somethign fresh that is maybe a bit more tailor to the customer.  I'm a little blind on this meeting, but want something prepared.

Follow-up, same session:

> So regarding that guidance - perhaps some sort of conditional highlighting of the CPU ratio when Contention is above "good"
>
> this customer is insistent on allocation, so make sure our recon takes that into account

## Vision

- Audience: a customer who plans capacity by allocation (vCPU:pCPU ratio).
  The dashboard meets them on their number and puts the evidence beside it.
- Core message, from the June 2025 VCF blog (Achtemichuk): no fixed ratio is
  right; start conservative against physical cores and let contention decide
  how far the ratio can grow.
- Per cluster: the ratio (against cores, and against cores after HA), the
  ratio the policy plans for, and contention evidence (share of VMs facing
  ready, worst VM ready and co-stop, average contention).
- The ratio is highlighted only when contention is above "good". A clean
  cluster at a high ratio stays quiet; a contended one lights up.
- Hosts and VMs of the selected cluster as drill-downs.
- Not covered by stock content: recon found the ratio on the stock Cluster
  Capacity dashboard and contention on the stock Cluster Performance
  dashboard, never together. The factory's Demand-Driven Capacity Planning
  v2 shows both in one list with fixed ratio bounds; this is the fresh,
  allocation-first take the user asked for.

## Wireframe (12-column grid)

Mock: `cpu-allocation-vs-contention.html` (what is approved). This table is
its twin.

| Band | Widget | Type | x | y | w | h | Subject / source |
|---|---|---|---|---|---|---|---|
| A | Fleet Allocation | Scoreboard | 1 | 1 | 12 | 3 | vSphere World, self-provider, pinned |
| B | Cluster CPU Allocation vs Contention | View (new list) | 1 | 4 | 12 | 7 | ClusterComputeResource, self-provider pinned to vSphere World. Primary selector |
| C-1 | Clusters: size = ratio, colour = contention | Heatmap | 1 | 11 | 6 | 5 | ClusterComputeResource, fleet-wide |
| C-2 | Hosts: size = vCPUs placed, colour = contention | Heatmap | 7 | 11 | 6 | 5 | HostSystem, grouped by cluster, fleet-wide |
| D | Hosts in Selected Cluster | View (new list) | 1 | 16 | 12 | 5 | HostSystem, driven by B |
| E | VMs in Selected Cluster | View (new list) | 1 | 21 | 12 | 5 | VirtualMachine, driven by B |
| F | Overcommit Ratio Trend, Selected Cluster | View (stock, by id) | 1 | 26 | 12 | 4 | Stock `Capacity \| Cluster Allocation`, id `3b7bba92-680c-42ba-b8a9-aa9202f0cc71`, driven by B |

### Interaction wiring

- B selection drives D, E and F.
- A, C-1 and C-2 are fleet-wide and not driven.

### Band A tiles (vSphere World)

`summary|total_number_clusters`, `summary|total_number_hosts`,
`summary|total_number_vms`, `cpu|corecount_provisioned`,
`cpu|vcpus_allocated_on_all_powered_on_vms`,
`cpu|vcpus_to_cores_allocation_ratio` (bounds 2/4/8, the stock Capacity
Summary scoreboard's). Author all three bounds or none (lesson
`scoreboard-partial-bounds-render-unknown.md`). Height 3 so labels show.

### Band B columns (view `[VCF CF] Cluster CPU Allocation vs Contention`, 7-day window)

| Column | Key | Transform | Bounds |
|---|---|---|---|
| Hosts | `summary|number_running_hosts` | current | |
| Cores | `cpu|corecount_provisioned` | current | |
| Cores After HA | `cpu|haCorecount_provisioned` | current | |
| vCPUs On | `cpu|vcpus_allocated_on_all_powered_on_vms` | current | |
| vCPU:pCore | `cpu|vcpus_to_cores_allocation_ratio` | current | none |
| vCPU:pCore After HA | SM `[VCF CF] Cluster - vCPU-to-pCore Ratio After HA` | current | none |
| Planned Ratio | property `System Properties|cpu|alloc|overcommitRatioSetting` | current | |
| Ratio if VMs Ready (was "Ratio While Ready-Contended") | SM `[VCF CF] Cluster - vCPU-to-pCore Ratio While Ready-Contended` | current | 0.01 / 3 / 6, sort desc |
| Ratio if Contention (was "Ratio While Contention High") | SM `[VCF CF] Cluster - vCPU-to-pCore Ratio While Contention High` | current | 0.01 / 3 / 6 |
| % VMs Facing Ready | `cpu|percentage_of_vms_facing_cpu_ready` | current | 2.5 / 5 / 10 |
| Worst VM Ready % | `cpu|max_cpu_ready` | max | 2.5 / 5 / 10 |
| Worst VM Co-stop % | `cpu|max_cpu_costop` | max | 2.5 / 5 / 10 |
| CPU Contention % | `cpu|capacity_contentionPct` | current | none |
| Alloc Remaining % | SM `[VCF CF] Cluster - CPU Allocation Remaining %` (the native percentage key never carries a value; see `knowledge/context/api-surface/policy_capacity_allocation_model.md`) | current | 40 / 30 / 20 descending |

### Band C heatmaps

- C-1: size `cpu|vcpus_to_cores_allocation_ratio`, colour
  `cpu|percentage_of_vms_facing_cpu_ready`, thresholds 2.5 / 5 / 10.
- C-2: size `cpu|vcpus_allocated_on_all_powered_on_vms`, colour
  `cpu|percentage_of_vms_facing_cpu_ready`, thresholds 2.5 / 5 / 7.5,
  grouped by parent cluster.
- Where there is no grouping the YAML writes `group_by: {}` and the
  renderer expands it to the 9-key self-grouping block; the rendered JSON
  must never carry an empty `groupBy` (lesson
  `heatmap-empty-groupby-crashes-renderer.md`).

### Band D columns (view `[VCF CF] Host CPU Allocation vs Contention`, 7-day window)

`cpu|corecount_provisioned`, property `config|hyperThread|active`,
`summary|number_running_vms`, `cpu|vcpus_allocated_on_all_powered_on_vms`,
SM `[VCF CF] Host - vCPU-to-pCore Ratio`,
`cpu|percentage_of_vms_facing_cpu_ready` (avg, 2.5/5/7.5),
`cpu|max_cpu_ready` (max, 2.5/5/7.5), `cpu|max_cpu_costop` (max),
`cpu|capacity_contentionPct` (avg).

### Band E columns (view `[VCF CF] VM vCPU Allocation vs Contention`, 7-day window)

`config|hardware|num_Cpu`, `cpu|demandPct` (avg), `cpu|readyPct` (avg),
`cpu|readyPct` (P95, 2.5/5/10, sort desc), `cpu|20_sec_peak_readyPct`
(max), `cpu|costopPct` (P95), `cpu|capacity_contentionPct` (avg).

Changed after approval, 2026-11-20 (transform only, pre-PR review): the two
trigger metrics are shown as current values, not 7-day averages, so each
row agrees with its own highlight columns, which are current. The two
Worst VM columns stay 7-day maximums and carry the history.

### Heatmap colour scaling (found in the browser pass, 2026-11-20)

Heatmap colour is a continuous gradient spread evenly from `min_value` to
`max_value` (or to the observed maximum when `max_value` is unset);
`thresholds.values` do not act as band edges. To make the top threshold
the end colour, `max_value` is set equal to it: CPU contention cluster 0
to 10, CPU contention host 0 to 7.5, allocation remaining 0 to 40 (red to
green). So the bands in this note are approximate on the heatmaps: the
colour ramps between the end points instead of stepping at each bound.

## Known constraints

- **A list-view cell is coloured only by its own value.** Recon checked the
  loaders, the wire-format docs and 1025 stock views: no cross-metric
  colouring exists. Hence two super metrics that republish the ratio only
  while the cluster is contended, and 0 otherwise, so their own bounds do
  the highlighting. The heatmap C-1 is the native expression of the same
  idea (colour by one metric, size by another).
- **"Contended" has two definitions, one column each** (owner, 2026-11-20:
  "1 + 4; maybe seperate metrics/columns"):
  `cpu|percentage_of_vms_facing_cpu_ready` above 2.5 (the green limit of
  the stock Cluster Performance scoreboard, bounds 2.5/5/10), and
  `cpu|capacity_contentionPct` above 5 (the factory's band; the product
  has none for this key). The ratio bands 3/6 on both highlighted columns
  are the stock Cluster Capacity scoreboard's (3/6/9).
- **Ratio denominator is physical cores**, hyperthreads not counted,
  powered-on VMs only (recon verified vCPUs on / `cpu|corecount_provisioned`
  on every cluster of four instances). That matches the blog's framing.
- **No host ratio key exists**, so the host ratio is a super metric.
- **Allocation model was enabled on no lab instance at recon time.** Owner
  decision 2026-11-20: "set it 3:1 in all instances. they all monitor the
  same hosts". Planned Ratio and Alloc Remaining % populate after that
  change and an analytics cycle.
- **Lab shape:** prod has the spread (ratio 1.98 to 7.14, real contention on
  wld01); devel_9_1 tops out at 3.17.
- The synthetic `cluster-0x` clusters have no `cpu|capacity_contentionPct`
  value; that column is blank for them.

## Notes

Recon: `knowledge/context/investigations/recon_log.md`, 2026-11-20 entry.
Vendor sources: the VCF blog post named in the prompt (no ratio
recommended, 1:1 against cores as a safe start, "drive by contention") and
the 8.18 allocation and demand model page (allocation model optional per
policy; Capacity Remaining goes to zero when the ratio is exceeded).
