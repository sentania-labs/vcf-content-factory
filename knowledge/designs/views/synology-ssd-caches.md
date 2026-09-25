# [VCF Content Factory] Synology SSD Caches

- **Type:** view (bundled in the pak)
- **Slug:** synology-ssd-caches
- **Authored YAML:** content/sdk-adapters/synology/views/synology-ssd-caches.yaml
- **Subject:** `synology_diskstation` `SynologySsdCache`
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

- One row per SSD cache: mode, member drives and failures, hit rates and occupancy.
- Embedded by: `knowledge/designs/dashboards/synology-storage-capacity.md`.
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Cache | name (object name) |  |
| Mode | `Configuration\|mode` |  |
| Status | `Configuration\|status` |  |
| RAID | `Configuration\|device_type` |  |
| Volume | `Configuration\|mount_volume` |  |
| Members | `Hardware\|disk_members` |  |
| Failed | `Hardware\|disk_failure_count` |  |
| Capacity | `Hardware\|total_capacity` |  |
| Occupied | `Capacity\|occupied_bytes` |  |
| Read hit % | `HitRate\|read_hit_rate` | uncolored, lower is worse (#176) |
| Write hit % | `HitRate\|write_hit_rate` |  |

Summary row: None.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
