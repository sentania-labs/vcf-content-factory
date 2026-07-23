# Supermetric: Cluster CPU Support Worst Status (KB318697)

## Initial prompt (verbatim)

> I just worry that in a large environment cluster could get two
> lengthy. Maybe a secondary/alternate picker
>
> Does that make sense?
>
> Vsphere world/vcenter drives - cluster based view; and host based
> view.
>
> Cluster view drives host view. Maybe host drives back to cluster view
> (is that allowed?)
>
> Cluster has roll up metric of hosts compatibility?

Follow-up choice: roll-up column = worst status only (AskUserQuestion,
2026-07-22).

## Vision

- ONE supermetric on VMWARE ClusterComputeResource:
  `[VCF Content Factory] Cluster CPU Support Worst Status (KB318697)`.
- Rolls up the host-level coded SM to the cluster: worst (max) child
  value. 0=all supported … 3=at least one host discontinued-from-9.2.
- Formula shape (numeric only, no string dialect risk):
  `max(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric|sm_<host-sm-uuid>, depth=1})`
  referencing the host SM (`cpu_support_status_kb318697.yaml`, UUID
  a7becc4c-22f4-4946-acf9-6cb559672544) via the repo's cross-SM
  resolution.
- Consumed by the v2 dashboard's cluster view as a color-thresholded
  column (1 yellow / 2 orange / 3 red).
