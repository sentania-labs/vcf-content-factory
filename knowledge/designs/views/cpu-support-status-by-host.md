# View: CPU Support Status by Host

## Initial prompt (verbatim)

> I'd like the dashboard to have a scoping tier, that then lists all
> hosts in the scope with: hostname, model, CPU model, deprecated,
> discontinued, discontinued 9.2, supported.

(Full request + clarification thread:
knowledge/designs/supermetrics/cpu-support-status.md.)

## Vision

- HostSystem list view `[VCF Content Factory] CPU Support Status by Host`
  (`content/views/cpu_support_status_by_host.yaml`).
- Columns: host name; `hardware|vendorModel` ("Model"); `cpu|cpuModel`
  ("CPU Model"); supermetric `[VCF Content Factory] CPU Support Status
  (KB318697)` as ONE color-thresholded "CPU Support Status" column
  (0 green / 1 yellow / 2 orange / 3 red → yellow_bound: 1,
  orange_bound: 2, red_bound: 3). The user's original four flag columns
  collapsed to one coded column by their explicit choice (1-SM design).
- Legend "0=supported, 1=deprecated, 2=discontinued, 3=discontinued
  starting 9.2 (per Broadcom KB 318697)" in the view description.
- Templates: content/views/host_contention_outliers.yaml (column/threshold
  shape), content/sdk-adapters/vcommunity-vsphere/views/ESXi CPU Models.yaml
  (cpu|cpuModel property column).
- Designed to receive a cluster-selection interaction from the dashboard
  scope tier.
