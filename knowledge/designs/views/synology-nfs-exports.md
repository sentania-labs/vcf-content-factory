# [VCF Content Factory] Synology NFS Exports

- **Type:** view (bundled in the pak)
- **Slug:** synology-nfs-exports
- **Authored YAML:** content/sdk-adapters/synology/views/synology-nfs-exports.yaml
- **Subject:** `synology_diskstation` `SynologyNfsExport`
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

- One row per NFS share: path, used size against quota, active clients and access rules.
- Embedded by: `knowledge/designs/dashboards/synology-nfs-iscsi.md`, `knowledge/designs/dashboards/synology-summary-volume.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Share | name (object name) |  |
| Export path | `Configuration\|export_path` |  |
| Volume | `Configuration\|volume_path` |  |
| Used MiB | `Capacity\|size_used_mib` |  |
| Quota MiB | `Configuration\|quota_value_mib` | 0 = no quota |
| Quota used % | `Capacity\|quota_usage_pct` | orange >= 80, red >= 90 |
| Clients | `Clients\|active_client_count` |  |
| Allowed clients | `Access\|allowed_clients` |  |
| Compression | `Access\|compress_enabled` |  |

Summary row: Sum of Used MiB and Clients.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Share names as observed in the v1 golden baseline; values simulated; the lab now has 15 exports.
