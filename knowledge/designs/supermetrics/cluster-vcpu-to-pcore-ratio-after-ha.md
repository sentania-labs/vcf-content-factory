# [VCF CF] Cluster - vCPU-to-pCore Ratio After HA

- **Type:** supermetric
- **Slug:** cluster-vcpu-to-pcore-ratio-after-ha
- **Authored YAML:** content/supermetrics/cluster_vcpu_to_pcore_ratio_after_ha.yaml
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

- On ClusterComputeResource: powered-on vCPUs divided by physical cores left
  after the HA reservation.
  `cpu|vcpus_allocated_on_all_powered_on_vms` / `cpu|haCorecount_provisioned`.
- Why: the native `cpu|vcpus_to_cores_allocation_ratio` divides by all cores
  (recon verified on every cluster of four instances), which understates
  the ratio the cluster runs at once a host fails. Sample from recon:
  158 vCPUs, 80 cores, 64 cores after HA, so 1.975 native and 2.47 after HA.
- No built-in or factory metric covers it (recon). Same formula as Brock
  Peterson's reference SM "Cluster CPU Overcommit Ratio after vSphere HA".
- Must not divide by zero when cores after HA is 0 or absent.

## Notes

Parent dashboard design: `knowledge/designs/dashboards/cpu-allocation-vs-contention.md`
(wireframe, column tables, known constraints). Recon:
`knowledge/context/investigations/recon_log.md`, 2026-11-20 entry.
