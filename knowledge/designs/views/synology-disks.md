# [VCF Content Factory] Synology Disks

- **Type:** view (bundled in the pak)
- **Slug:** synology-disks
- **Authored YAML:** content/sdk-adapters/synology/views/synology-disks.yaml
- **Subject:** `synology_diskstation` `SynologyDisk`
- **Date:** 2026-09-25
- **Status:** drafted; follows approval of the dashboards that embed it

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

Derived from the dashboard designs that embed this view (below).

## Vision

- One row per drive: slot, SMART status, temperature, uncorrectable sectors, remaining life and busy.
- Embedded by: `knowledge/designs/dashboards/synology-disk-health.md`, `knowledge/designs/dashboards/synology-summary-storage-pool.md` (S7), `knowledge/designs/dashboards/synology-summary-ssd-cache.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Slot | `Hardware\|slot_id` |  |
| Disk | `Hardware\|display_name` |  |
| Model | `Hardware\|model` |  |
| Type | `Hardware\|disk_type` |  |
| SMART | `Health\|smart_status` |  |
| Temp C | `Health\|temperature` | orange >= 50, red >= 55 |
| Unc. sectors | `Health\|unc_sectors` | orange > 0, red >= 50. Display rule: -1 (NVMe no-data sentinel) shows n/a, uncolored |
| Busy % | `IO\|utilization_pct` |  |
| Serial | `Hardware\|serial` |  |
| Firmware | `Hardware\|firmware` |  |

Summary row: Sum of Unc. sectors.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Names, models and serials as observed in the v1 golden baseline (2026-06-10); values simulated. HDD firmware and the Drive 1 serial illustrative. Health|remain_life removed: 0 on every disk, never populated (live recon 2026-09-25). Summary-row sum of Unc. sectors must exclude -1 rows (the sentinel would subtract); if the view cannot filter the sum, drop the sum.
