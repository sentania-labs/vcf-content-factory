# [VCF CF] Cluster - Disk Allocation Remaining %

- **Type:** supermetric
- **Slug:** cluster-disk-allocation-remaining-pct
- **Authored YAML:** content/supermetrics/cluster_disk_allocation_remaining_pct.yaml
- **Date:** 2026-11-20
- **Status:** drafted

## Initial prompt

> Hello I'd like to do the following combination sof things:
> 1> Identify any built in dashboards for capacity, vCPU : pvCPU allocation, contention etc;
> 2> if none exist author some examples that show capacity based on vCPU: pCPU guidlines (https://blogs.vmware.com/cloud-foundation/2025/06/04/vcpu-to-pcpu-ratio-guidelines/)
> https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations/8-18/vmware-aria-operations-configuration-guide-8-18/optimizing-capacity-and-improving-performance/capacity-optimization-concepts/allocation-and-demand-model-in-workload-optimization.html
>
> We may have some that exist, but i'd like somethign fresh that is maybe a bit more tailor to the customer.  I'm a little blind on this meeting, but want something prepared.

Follow-ups, same session:

> So regarding that guidance - perhaps some sort of conditional highlighting of the CPU ratio when Contention is above "good"
>
> this customer is insistent on allocation, so make sure our recon takes that into account

On which signal defines "contended" (options 1 = more than 2.5 % of VMs facing CPU ready, 4 = average contention above 5 %):

> 1 + 4; maybe seperate metrics/columns

## Vision

- On ClusterComputeResource: `OnlineCapacityAnalytics|diskspace|alloc|capacityRemaining` / `diskspace|alloc|usableCapacity` x 100. Both in GB.
- Why: the product's per-resource `capacityRemainingPercentage` keys exist
  in the statkey listing but never carry a value, for the allocation or
  the demand model (api-explorer, 2026-11-20,
  `knowledge/context/api-surface/policy_capacity_allocation_model.md`
  section "Computing a remaining percent yourself"). Only the overall
  most-constrained percentage populates. This is the same formula the
  engine uses for that overall key.
- Use the engine's remaining figure as it is (it is not simply usable
  minus allocated, and it floors at 0).
- Both keys exist on 8.18.7, 9.0.2 and 9.1.1 but carry no value in the lab, because no disk ratio is set there. Do not use `diskspace|usable_capacity` (absent on 8.18.7).
- When usable capacity is 0 or absent the metric must produce no value,
  not 0: 0 means "full", and an unconfigured resource is not full.

## Notes

Parent dashboard design: `knowledge/designs/dashboards/allocation-capacity-by-cluster.md`.
