# [VCF Content Factory] Synology Volumes

- **Type:** view (bundled in the pak)
- **Slug:** synology-volumes
- **Authored YAML:** content/sdk-adapters/synology/views/synology-volumes.yaml
- **Subject:** `synology_diskstation` `SynologyVolume`
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

- One row per volume: capacity, busy, IOPS and SSD cache state.
- Embedded by: `knowledge/designs/dashboards/synology-storage-capacity.md`.
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Volume | name (object name) |  |
| Path | `Configuration\|volume_path` |  |
| Status | `Configuration\|status` |  |
| FS | `Configuration\|fs_type` |  |
| Total | `Capacity\|total_bytes` |  |
| Busy % | `IO\|utilization_pct` | orange >= 70, red >= 90 |
| Read IOPS | `IO\|read_iops` |  |
| Write IOPS | `IO\|write_iops` |  |
| Cache | `Cache\|cache_status` |  |
| Cache read hit % | `Cache\|cache_read_hit_rate` | uncolored, lower is worse (#176) |

Summary row: None.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Free and Used % columns (Capacity|free_bytes, Capacity|usage_pct) are BLOCKED on an adapter fix (Synology issue to be filed): live recon 2026-09-25 shows free = 0 on every sample while IO is active and status is normal. Add them back after the fix.
