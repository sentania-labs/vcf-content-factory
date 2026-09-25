# [VCF Content Factory] Synology iSCSI LUNs

- **Type:** view (bundled in the pak)
- **Slug:** synology-iscsi-luns
- **Authored YAML:** content/sdk-adapters/synology/views/synology-iscsi-luns.yaml
- **Subject:** `synology_diskstation` `SynologyIscsiLun`
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

- One row per LUN: size, target, IOPS, throughput and latency.
- Embedded by: `knowledge/designs/dashboards/synology-nfs-iscsi.md`, `knowledge/designs/dashboards/synology-summary-volume.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| LUN | `Configuration\|name` |  |
| Type | `Configuration\|type` |  |
| Size | `Configuration\|size_bytes` |  |
| Location | `Configuration\|location` |  |
| Target on | `Configuration\|target_enabled` |  |
| Read IOPS | `IO\|read_iops` |  |
| Write IOPS | `IO\|write_iops` |  |
| Read B/s | `IO\|read_throughput` |  |
| Write B/s | `IO\|write_throughput` |  |

Summary row: Sum of Read IOPS and Write IOPS.

## Notes

- Keys cite `content/sdk-adapters/synology/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- LUN names as observed in the v1 golden baseline; values simulated; the lab now has 2 LUNs. IO|read_latency and IO|write_latency removed: 0 on every sample while IOPS move (live recon 2026-09-25).
