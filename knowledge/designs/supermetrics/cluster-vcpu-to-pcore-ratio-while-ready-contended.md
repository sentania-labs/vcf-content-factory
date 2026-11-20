# [VCF CF] Cluster - vCPU-to-pCore Ratio While Ready-Contended

- **Type:** supermetric
- **Slug:** cluster-vcpu-to-pcore-ratio-while-ready-contended
- **Authored YAML:** content/supermetrics/cluster_vcpu_to_pcore_ratio_while_ready_contended.yaml
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
  `cpu|vcpus_to_cores_allocation_ratio` when
  `cpu|percentage_of_vms_facing_cpu_ready` is above 2.5, and 0 otherwise.
- Why: a list-view cell can only be coloured by its own value. This metric
  exists so a view column can highlight the ratio only while the cluster is
  contended (bounds on the column: 0.01 yellow, 3 orange, 6 red).
- 2.5 is the green limit of the stock Cluster Performance scoreboard on
  that key (bounds 2.5/5/10).
- A clean cluster must read 0, not "no data", so the column sorts and
  shows a value on every row.

## Notes

Parent dashboard design: `knowledge/designs/dashboards/cpu-allocation-vs-contention.md`
(wireframe, column tables, known constraints). Recon:
`knowledge/context/investigations/recon_log.md`, 2026-11-20 entry.
