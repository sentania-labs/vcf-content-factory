# [VCF CF] Cluster - vCPU-to-pCore Ratio While Contention High

- **Type:** supermetric
- **Slug:** cluster-vcpu-to-pcore-ratio-while-contention-high
- **Authored YAML:** content/supermetrics/cluster_vcpu_to_pcore_ratio_while_contention_high.yaml
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

- On ClusterComputeResource: emits the native ratio
  `cpu|vcpus_to_cores_allocation_ratio` when `cpu|capacity_contentionPct`
  (average CPU contention of the cluster's VMs) is above 5, and 0
  otherwise.
- Sibling of the Ready-Contended metric; same purpose, second definition of
  "contended". 5 % is the factory's own band (the product has none for this
  key); the existing `[VCF CF] Cluster Demand & Capacity Overview v2` view
  uses 5/10/20 on it.
- Some lab clusters (the synthetic `cluster-0x`) have no
  `cpu|capacity_contentionPct` value. Say in the report what the metric
  does there (no data, or 0) and why.

## Notes

Parent dashboard design: `knowledge/designs/dashboards/cpu-allocation-vs-contention.md`
(wireframe, column tables, known constraints). Recon:
`knowledge/context/investigations/recon_log.md`, 2026-11-20 entry.
