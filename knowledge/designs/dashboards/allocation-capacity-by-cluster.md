# [VCF CF] Allocation Capacity by Cluster

- **Type:** dashboard
- **Slug:** allocation-capacity-by-cluster
- **Authored YAML:** content/dashboards/allocation_capacity_by_cluster.yaml
- **Date:** 2026-11-20
- **Status:** drafted (wireframe approved in plan mode 2026-11-20)

## Initial prompt

> Hello I'd like to do the following combination sof things:
> 1> Identify any built in dashboards for capacity, vCPU : pvCPU allocation, contention etc;
> 2> if none exist author some examples that show capacity based on vCPU: pCPU guidlines (https://blogs.vmware.com/cloud-foundation/2025/06/04/vcpu-to-pcpu-ratio-guidelines/)
> https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations/8-18/vmware-aria-operations-configuration-guide-8-18/optimizing-capacity-and-improving-performance/capacity-optimization-concepts/allocation-and-demand-model-in-workload-optimization.html
>
> We may have some that exist, but i'd like somethign fresh that is maybe a bit more tailor to the customer.  I'm a little blind on this meeting, but want something prepared.

Follow-up, same session:

> this customer is insistent on allocation, so make sure our recon takes that into account

## Vision

- Audience: a customer who insists on the allocation model. This is their
  lens, built on the product's own allocation-model capacity metrics.
- Per cluster, for CPU, memory and disk: the overcommit ratio the policy
  plans, the ratio the cluster actually runs at, and the allocation
  capacity and time remaining that follow.
- The demand model's answer sits in the last two columns, so the gap
  between "full by allocation" and "plenty left by demand" (or the reverse)
  is visible on one row.
- Not covered by stock content: the stock `Capacity Overcommit Ratios` view
  shows planned vs current ratios but no stock dashboard uses it, and
  nothing stock or factory shows the `alloc` capacity family.

## Wireframe (12-column grid)

Mock: `allocation-capacity-by-cluster.html` (what is approved). This table
is its twin.

| Band | Widget | Type | x | y | w | h | Subject / source |
|---|---|---|---|---|---|---|---|
| A | Cluster Allocation: Planned vs Actual | View (new list) | 1 | 1 | 12 | 7 | ClusterComputeResource, self-provider pinned to vSphere World. Primary selector |
| B | Selected Cluster: Overcommit Ratios | Scoreboard | 1 | 8 | 12 | 3 | ClusterComputeResource, driven by A |
| C-1 | CPU Allocation Remaining | Heatmap | 1 | 11 | 4 | 5 | ClusterComputeResource, fleet-wide |
| C-2 | Memory Allocation Remaining | Heatmap | 5 | 11 | 4 | 5 | ClusterComputeResource, fleet-wide |
| C-3 | Disk Allocation Remaining | Heatmap | 9 | 11 | 4 | 5 | ClusterComputeResource, fleet-wide |
| D | Overcommit Ratio Trend, Selected Cluster | View (stock, by id) | 1 | 16 | 12 | 4 | Stock `Capacity \| Cluster Allocation`, id `3b7bba92-680c-42ba-b8a9-aa9202f0cc71`, driven by A |

### Interaction wiring

- A selection drives B and D.
- C-1 to C-3 are fleet-wide and not driven.

### Band A columns (view `[VCF CF] Cluster Allocation Planned vs Actual`)

| Group | Column | Key | Bounds |
|---|---|---|---|
| CPU | Planned | property `System Properties|cpu|alloc|overcommitRatioSetting` | |
| CPU | Actual | `cpu|vcpus_to_cores_allocation_ratio` | |
| CPU | Usable (vCPUs) | `cpu|alloc|usableCapacity` | |
| CPU | Remaining (vCPUs) | `OnlineCapacityAnalytics|cpu|alloc|capacityRemaining` | |
| CPU | Remaining % | SM `[VCF CF] Cluster - CPU Allocation Remaining %` | 40/30/20 descending, sort asc |
| CPU | Days Left | `OnlineCapacityAnalytics|cpu|alloc|timeRemaining` | |
| CPU | Recommended (cores) | `OnlineCapacityAnalytics|cpu|alloc|recommendedSize` | |
| Memory | Planned | property `System Properties|mem|alloc|overcommitRatioSetting` | |
| Memory | Actual | `mem|virtual_to_physical_memory_allocation_ratio` | |
| Memory | Remaining % | SM `[VCF CF] Cluster - Memory Allocation Remaining %` | 40/30/20 descending |
| Memory | Days Left | `OnlineCapacityAnalytics|mem|alloc|timeRemaining` | |
| Disk | Planned | property `System Properties|diskspace|alloc|overcommitRatioSetting` | |
| Disk | Actual | `diskspace|diskspace_overcommit_ratio` | |
| Disk | Remaining % | SM `[VCF CF] Cluster - Disk Allocation Remaining %` | 40/30/20 descending |
| Disk | Days Left | `OnlineCapacityAnalytics|diskspace|alloc|timeRemaining` | |
| Demand | CPU Remaining % | SM `[VCF CF] Cluster - CPU Demand Remaining %` | |
| Demand | Days Left | `OnlineCapacityAnalytics|cpu|demand|timeRemaining` | |

All columns current value.

### Band B tiles (selected cluster)

`cpu|vcpus_to_cores_allocation_ratio` (3/6/9),
`mem|virtual_to_physical_memory_allocation_ratio` (1/2/3),
`diskspace|diskspace_overcommit_ratio` (2/3/4),
`cpu|vcpus_allocated_on_all_powered_on_vms`, `cpu|haCorecount_provisioned`.
Bounds are the stock Cluster Capacity dashboard's Overcommit Ratio
scoreboard. All three bounds or none per tile.

### Band C heatmaps

| Heatmap | size_by | color_by | Thresholds |
|---|---|---|---|
| C-1 | `cpu|corecount_provisioned` | SM `[VCF CF] Cluster - CPU Allocation Remaining %` | 40/30/20 |
| C-2 | `mem|haTotalCapacity_average` | SM `[VCF CF] Cluster - Memory Allocation Remaining %` | 40/30/20 |
| C-3 | `diskspace|total_capacity` | SM `[VCF CF] Cluster - Disk Allocation Remaining %` | 40/30/20 |

The YAML writes `group_by: {}` and the renderer expands it to the
self-grouping block; the rendered JSON must never carry an empty `groupBy`
(lesson `heatmap-empty-groupby-crashes-renderer.md`).

### Heatmap colour scaling (found in the browser pass, 2026-11-20)

Heatmap colour is a continuous gradient spread evenly from `min_value` to
`max_value` (or to the observed maximum when `max_value` is unset);
`thresholds.values` do not act as band edges. To make the top threshold
the end colour, `max_value` is set equal to it: CPU contention cluster 0
to 10, CPU contention host 0 to 7.5, allocation remaining 0 to 40 (red to
green). So the bands in this note are approximate on the heatmaps: the
colour ramps between the end points instead of stepping at each bound.

## Known constraints

- **The allocation model was enabled on no lab instance at recon time**
  (effective policy on all four: only `poweredOffVmsConsidered: false`, no
  ratios). Owner decision 2026-11-20: "set it 3:1 in all instances. they
  all monitor the same hosts", applied as CPU 3:1 only. So the memory and
  disk Planned and Alloc cells stay empty in the lab; the CPU ones
  populate after an analytics cycle.
- **Remaining % is computed, not native** (change after approval,
  2026-11-20; metric swap only, no layout change). api-explorer found the
  per-resource `capacityRemainingPercentage` keys exist but never carry a
  value, for allocation or demand, even with the model on. Four super
  metrics compute remaining / usable x 100 from keys verified on 8.18.7,
  9.0.2 and 9.1.1: see
  `knowledge/context/api-surface/policy_capacity_allocation_model.md`.
  The memory and disk keys named in this note were confirmed in the same
  pass.
- **The overall `OnlineCapacityAnalytics|capacityRemainingPercentage` now
  follows allocation** wherever allocation is the tighter limit, so it
  cannot serve as the demand contrast column; the CPU demand super metric
  does.
- The Planned properties exist only on some clusters (absent on the
  synthetic `cluster-0x` ones) and read -1.0 when unset.
- Datacenter, vSphere World and HostSystem carry no alloc capacity keys, so
  there is no fleet scoreboard of allocation remaining; the page is
  cluster-first by necessity.
- 40/30/20 remaining bands are the stock `VCF Cluster Capacity` view's.

## Notes

Recon: `knowledge/context/investigations/recon_log.md`, 2026-11-20 entry.
The stock view `Capacity Overcommit Ratios`
(`4017670c-d158-348d-87ec-89869004fe37`) covers planned vs current ratios
and could be embedded instead of Band A; it lacks the remaining, time and
demand columns, which is why Band A is a new view.
