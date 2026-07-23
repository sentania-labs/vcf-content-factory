# View: CPU Support Status by Cluster

## Initial prompt (verbatim)

> Vsphere world/vcenter drives - cluster based view; and host based
> view.
>
> Cluster view drives host view. …
>
> Cluster has roll up metric of hosts compatibility?

(Full v2 request + choices: knowledge/designs/supermetrics/cluster-cpu-support-worst-status.md.)

## Vision

- ClusterComputeResource list view
  `[VCF Content Factory] CPU Support Status by Cluster`
  (`content/views/cpu_support_status_by_cluster.yaml`).
- Columns: cluster name; supermetric `[VCF Content Factory] Cluster CPU
  Support Worst Status (KB318697)` as a color-thresholded "Worst CPU
  Support Status" column (yellow 1 / orange 2 / red 3; 0 uncolored).
- Legend (0-3 + KB 318697) in description.
- Row 2 of the v2 dashboard: receives World/vCenter selection from the
  scope picker; its row selection drives the host view (Row 3).
- Template: content/views/cpu_support_status_by_host.yaml (SM column
  shape).
