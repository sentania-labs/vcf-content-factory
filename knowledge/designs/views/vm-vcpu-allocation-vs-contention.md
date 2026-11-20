# [VCF CF] VM vCPU Allocation vs Contention

- **Type:** view
- **Slug:** vm-vcpu-allocation-vs-contention
- **Authored YAML:** content/views/vm_vcpu_allocation_vs_contention.yaml
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

- VMs of the selected cluster: vCPU count next to ready, co-stop and
  contention, worst ready first, so the reader can see which VMs carry the
  contention and how big they are.
- Columns: Band E list in the parent dashboard design. 7-day window.

## Notes

Parent dashboard design: `knowledge/designs/dashboards/cpu-allocation-vs-contention.md`
(wireframe, column tables, known constraints). Recon:
`knowledge/context/investigations/recon_log.md`, 2026-11-20 entry.
