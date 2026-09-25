# [VCF Content Factory] Synology Storage Pools

- **Type:** view (bundled in the pak)
- **Slug:** synology-storage-pools
- **Authored YAML:** content/sdk-adapters/synology/views/synology-storage-pools.yaml
- **Subject:** `synology_diskstation` `SynologyStoragePool`
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

- One row per pool: status, RAID, capacity used.
- Embedded by: `knowledge/designs/dashboards/synology-storage-capacity.md`, `knowledge/designs/dashboards/synology-summary-diskstation.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Pool | name (object name) |  |
| Status | `Configuration\|status` |  |
| RAID | `Configuration\|device_type` |  |
| RAID type | `Configuration\|raid_type` |  |
| Path | `Configuration\|pool_path` |  |
| Total | `Capacity\|total_bytes` |  |

Summary row: None.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Used and Used % columns (Capacity|used_bytes, Capacity|usage_pct) are BLOCKED on an adapter fix (Synology issue to be filed): live recon 2026-09-25 shows used = total on every sample while status is normal. Add them back after the fix.
