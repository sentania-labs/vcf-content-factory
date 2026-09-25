# [VCF Content Factory] Synology NFS and iSCSI

- **Type:** dashboard (bundled in the pak)
- **Slug:** synology-nfs-iscsi
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-nfs-iscsi.yaml
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/synology-nfs-iscsi.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- **Why an admin wants it:** The vSphere-facing page: which shares and LUNs back which datastores, how full the shares are against quota, who is mounting them, and how hard vSphere drives each LUN.
- Pick a DiskStation; see NFS service load and latency, every NFS export with quota use and client count, every iSCSI LUN with IOPS and throughput, and for the selected share or LUN its trend and the VMware datastore it backs.
- Audience: the vSphere admin who consumes the NAS as datastores.
- The datastore link comes from the pack's cross-adapter stitch (Datastore is the foreign parent of a LUN or export).
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist on the instance or in the repo.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Keys

All keys from `content/sdk-adapters/synology/describe.xml`. Stitch behavior from `content/sdk-adapters/synology/docs/overview.md`. Every key below is cited exactly as `<ResourceGroup key>|<ResourceAttribute key>`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | DiskStation | ResourceList | 1, 1, 3, 8 | `synology_diskstation` `SynologyDiskstation` | Picker, name only. Drives W2, W3, W5, W6 |
| W2 | NFS Service | Scoreboard | 4, 1, 5, 4 | driven by W1 | `NFS\|nfs_total_ops`, `NFS\|nfs_max_latency` (orange 50, red 200 ms), `NFS\|nfs_client_count`, `NFS\|nfs_write_ops` |
| W3 | NFS Service Trend | MetricChart | 4, 5, 5, 4 | driven by W1 | `NFS\|nfs_total_ops`, `NFS\|nfs_max_latency`, 7 days |
| W4 | Backing Datastore | ResourceRelationshipAdvanced | 9, 1, 4, 8 | driven by W5 and W6 | depth `"2,0"`: the selected export or LUN with its volume and its foreign VMware Datastore parent |
| W5 | NFS Exports | View | 1, 9, 12, 7 | driven by W1, `SynologyNfsExport` | View `Synology NFS Exports`. Row select drives W4, W7 |
| W6 | iSCSI LUNs | View | 1, 16, 12, 4 | driven by W1, `SynologyIscsiLun` | View `Synology iSCSI LUNs`. Row select drives W4, W8 |
| W7 | Export Trend: vcf9 | MetricChart | 1, 20, 6, 7 | driven by W5 | `Capacity\|size_used_mib`, `Capacity\|quota_usage_pct`, `Clients\|active_client_count`, 30 days |
| W8 | LUN IOPS and Throughput: vcf-lab-wld01-cl01 | MetricChart | 7, 20, 6, 7 | driven by W6 | `IO\|read_iops`, `IO\|write_iops`, `IO\|read_throughput`, `IO\|write_throughput`, 7 days |

Interactions: W1 drives W2, W3, W5, W6. W5 row selection drives W4 and W7. W6 row selection drives W4 and W8. W5 and W6 auto-select their first row, so W4 shows whichever fired last on load (see constraints).

## Views (authored before the dashboard)

- `Synology NFS Exports`: `knowledge/designs/views/synology-nfs-exports.md`
- `Synology iSCSI LUNs`: `knowledge/designs/views/synology-iscsi-luns.md`

## Known constraints

- #177: per DiskStation.
- #175: exports open in default order; click Quota used % to sort.
- W4 has two upstream widgets. Both auto-select on load, so which one W4 shows first is not deterministic. If that is confusing in practice, set `select_first_row: false` on W6 so W4 opens on the first export.
- `NFS|nfs_max_latency` is a max, not an average (447 ms in the v1 baseline with 4 ops/s), so the red tile may be noisy. Thresholds to tune after a week of data.
- `IO|read_latency` / `IO|write_latency` removed: 0 on every sample while IOPS move (live recon 2026-09-25). `NFS|nfs_max_latency` on the DiskStation is a different key and was not flagged.
