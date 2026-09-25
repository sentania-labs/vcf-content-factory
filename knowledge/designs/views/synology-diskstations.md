# [VCF Content Factory] Synology DiskStations

- **Type:** view (bundled in the pak)
- **Slug:** synology-diskstations
- **Authored YAML:** content/sdk-adapters/synology/views/synology-diskstations.yaml
- **Subject:** `synology_diskstation` `SynologyDiskstation`
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

- One row per NAS: model, DSM version, temperature, load, memory, NFS clients and fan.
- Embedded by: `knowledge/designs/dashboards/synology-summary-world.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| DiskStation | name (object name) |  |
| Model | `System\|model` |  |
| DSM | `System\|firmware_version` |  |
| Temp C | `System\|system_temp` | orange >= 55, red >= 65 |
| CPU load 5m | `CPU\|cpu_load_5m` |  |
| Mem % | `Memory\|memory_usage_pct` | orange >= 80, red >= 90 |
| NFS clients | `NFS\|nfs_client_count` |  |
| Fan | `Fan\|fan_status` |  |
| Uptime | `System\|uptime` |  |

Summary row: None.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
