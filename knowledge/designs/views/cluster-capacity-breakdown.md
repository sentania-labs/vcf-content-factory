# Design — [VCF Content Factory] Cluster Capacity Breakdown (view)

Part of the **Fleet Capacity & Rightsizing** dashboard (see
`knowledge/designs/dashboards/fleet-capacity-rightsizing.md`). This is Band B — the
primary per-cluster capacity table that also acts as the dashboard's selector.

## Initial prompt
See dashboard design note. User wants "a breakdown of capacity by CPU, memory
and storage" across the VCF fleet.

## Vision
A list view, one row per `ClusterComputeResource`, with columns grouped by
resource (CPU, then Memory, then Storage) plus an overall most-constrained
summary. Built-in metrics only, demand model.

## View spec
- **Type:** list view
- **Subject (resource kind):** `ClusterComputeResource` (VMWARE adapter)
- **Sort:** by `OnlineCapacityAnalytics|capacityRemainingPercentage` ascending (most-constrained first)

### Columns (in order)
| Column label | Source key | Notes |
|---|---|---|
| Cluster | resource name | |
| CPU Remaining (MHz) | `OnlineCapacityAnalytics|cpu|demand|capacityRemaining` | metric |
| CPU Usable (MHz) | `cpu|demand|usableCapacity` | metric |
| CPU Usage % | `cpu|capacity_usagepct_average` | metric |
| CPU Time Remaining (days) | `OnlineCapacityAnalytics|cpu|demand|timeRemaining` | metric |
| Mem Remaining | `OnlineCapacityAnalytics|mem|demand|capacityRemaining` | KB — format GB if possible |
| Mem Usable | `mem|demand|usableCapacity` | KB |
| Mem Usage % | `mem|host_usagePct` | metric |
| Mem Time Remaining (days) | `OnlineCapacityAnalytics|mem|demand|timeRemaining` | metric |
| Disk Remaining (GB) | `OnlineCapacityAnalytics|diskspace|demand|capacityRemaining` | metric |
| Disk Total (GB) | `diskspace|total_capacity` | metric |
| Disk Used (GB) | `diskspace|total_usage` | metric |
| Disk Time Remaining (days) | `OnlineCapacityAnalytics|diskspace|demand|timeRemaining` | metric |
| Capacity Remaining % | `OnlineCapacityAnalytics|capacityRemainingPercentage` | most-constrained |
| Time Remaining (days) | `OnlineCapacityAnalytics|timeRemaining` | most-constrained |

## Constraints
- Demand model only (alloc not collecting).
- No super metrics — all keys are built-in and confirmed live by recon.
