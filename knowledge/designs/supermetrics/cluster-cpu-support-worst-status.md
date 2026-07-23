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
  value. 0=all supported … 3=at least one host discontinued.

> **Correction (2026-07-22, Codex review P1 on bundles PR):** the
> upstream host-level SM originally emitted 3=discontinued-from-9.2
> and 2=discontinued, which is inverted (discontinued-now is strictly
> worse). This max() roll-up masked a currently-discontinued host
> behind a future-discontinued one in the same cluster. Fixed at the
> host-level SM (`cpu_support_status_kb318697.yaml`); this SM's
> formula (`max(...)`) is unchanged — see
> `knowledge/designs/supermetrics/cpu-support-status.md` for the
> corrected tier table. Legend is now: 0=all hosts supported,
> 1=worst host deprecated, 2=worst host discontinued-from-9.2,
> 3=worst host discontinued.
- Formula shape (numeric only, no string dialect risk):
  `max(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric|sm_<host-sm-uuid>, depth=1})`
  referencing the host SM (`cpu_support_status_kb318697.yaml`, UUID
  a7becc4c-22f4-4946-acf9-6cb559672544) via the repo's cross-SM
  resolution.
- Consumed by the v2 dashboard's cluster view as a color-thresholded
  column (1 yellow / 2 orange / 3 red).
