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
| CPU | Remaining % | `OnlineCapacityAnalytics|cpu|alloc|capacityRemainingPercentage` | 40/30/20 descending, sort asc |
| CPU | Days Left | `OnlineCapacityAnalytics|cpu|alloc|timeRemaining` | |
| CPU | Recommended (cores) | `OnlineCapacityAnalytics|cpu|alloc|recommendedSize` | |
| Memory | Planned | property `System Properties|mem|alloc|overcommitRatioSetting` | |
| Memory | Actual | `mem|virtual_to_physical_memory_allocation_ratio` | |
| Memory | Remaining % | `OnlineCapacityAnalytics|mem|alloc|capacityRemainingPercentage` (confirm) | 40/30/20 descending |
| Memory | Days Left | `OnlineCapacityAnalytics|mem|alloc|timeRemaining` (confirm) | |
| Disk | Planned | property `System Properties|diskspace|alloc|overcommitRatioSetting` | |
| Disk | Actual | `diskspace|diskspace_overcommit_ratio` | |
| Disk | Remaining % | `OnlineCapacityAnalytics|diskspace|alloc|capacityRemainingPercentage` (confirm) | 40/30/20 descending |
| Disk | Days Left | `OnlineCapacityAnalytics|diskspace|alloc|timeRemaining` (confirm) | |
| Demand | Remaining % | see constraint below | |
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
| C-1 | `cpu|corecount_provisioned` | `OnlineCapacityAnalytics|cpu|alloc|capacityRemainingPercentage` | 40/30/20 |
| C-2 | `mem|haTotalCapacity_average` | `OnlineCapacityAnalytics|mem|alloc|capacityRemainingPercentage` (confirm) | 40/30/20 |
| C-3 | `diskspace|total_capacity` | `OnlineCapacityAnalytics|diskspace|alloc|capacityRemainingPercentage` (confirm) | 40/30/20 |

Never `groupBy: {}` (lesson `heatmap-empty-groupby-crashes-renderer.md`).

## Known constraints

- **The allocation model was enabled on no lab instance at recon time**
  (effective policy on all four: only `poweredOffVmsConsidered: false`, no
  ratios). Owner decision 2026-11-20: "set it 3:1 in all instances. they
  all monitor the same hosts", applied as CPU 3:1 only. So the memory and
  disk Planned and Alloc cells stay empty in the lab; the CPU ones
  populate after an analytics cycle.
- **Keys marked (confirm)**: recon listed the CPU alloc family key by key
  from live statkeys and reported that memory and disk have "the same
  shape". The view author confirms each memory and disk key against the
  live statkey listing; a key that does not exist is a dropped column
  reported back, never a guess (RULE-002).
- **Demand Remaining %**: the per-resource demand key
  (`OnlineCapacityAnalytics|cpu|demand|capacityRemaining`) is in MHz. The
  column is either a view expression against `cpu|demand|usableCapacity`
  or the overall `OnlineCapacityAnalytics|capacityRemainingPercentage`
  (most constrained resource). Author picks what the view schema supports
  and says which.
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
