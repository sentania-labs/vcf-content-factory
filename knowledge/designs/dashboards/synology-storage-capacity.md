# [VCF Content Factory] Synology Storage Capacity and Health

- **Type:** dashboard (bundled in the pak)
- **Slug:** synology-storage-capacity
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-storage-capacity.yaml
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/synology-storage-capacity.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- **Why an admin wants it:** Answers 'is anything degraded, and (once the adapter is fixed) how full is the NAS': pool and volume status, SSD cache state, volume IO, NAS vitals and alerts on one page.
- Pick a DiskStation; see its vitals and alerts, every pool and volume with status, SSD cache health, then a volume's IO trend. The two capacity trends keep their slots, greyed, until the adapter reports capacity correctly.
- Audience: the storage or vSphere admin who owns the NAS.
- Disk-level SMART detail lives on the Disk Health dashboard; datastore-facing shares on NFS and iSCSI.
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist on the instance or in the repo.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Keys

All keys from `content/sdk-adapters/synology/describe.xml`; `badge|health` is a platform key. Every key below is cited exactly as `<ResourceGroup key>|<ResourceAttribute key>`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | DiskStation | ResourceList | 1, 1, 3, 8 | `synology_diskstation` `SynologyDiskstation` | Picker, name only. Drives W2, W3, W4, W5, W6, W7 |
| W2 | Vitals | Scoreboard | 4, 1, 5, 4 | driven by W1 | `System\|system_temp` (orange 55, red 65), `CPU\|cpu_load_5m`, `Memory\|memory_usage_pct` (orange 80, red 90), `NFS\|nfs_client_count` |
| W3 | Active Alerts | AlertList | 9, 1, 4, 8 | driven by W1, DiskStation and descendants | Active, Warning and up |
| W4 | Pool Capacity Used | MetricChart | 4, 5, 5, 4 | driven by W1, `relationship_mode: children`, child kind `SynologyStoragePool` | **BLOCKED on adapter fix (Synology issue to be filed).** Intended: `Capacity\|usage_pct`, 30 days, one line per pool. Adapter reports used = total (live recon 2026-09-25). Author as a TextDisplay stating this until fixed |
| W5 | Storage Pools | View | 1, 9, 12, 4 | driven by W1, `SynologyStoragePool` | View `Synology Storage Pools` |
| W6 | Volumes | View | 1, 13, 12, 4 | driven by W1, `SynologyVolume` | View `Synology Volumes`. Row select drives W8, W9 |
| W7 | SSD Cache | View | 1, 17, 12, 4 | driven by W1, `SynologySsdCache` | View `Synology SSD Caches` |
| W8 | Volume Capacity: Volume 1 | MetricChart | 1, 21, 6, 7 | driven by W6 | **BLOCKED on adapter fix (Synology issue to be filed).** Intended: `Capacity\|usage_pct`, `Capacity\|free_bytes`, 30 days. Adapter reports free = 0 (live recon 2026-09-25). Author as a TextDisplay stating this until fixed |
| W9 | Volume IO: Volume 1 | MetricChart | 7, 21, 6, 7 | driven by W6 | `IO\|read_iops`, `IO\|write_iops`, `IO\|utilization_pct`, `Cache\|cache_read_hit_rate`, 7 days |

Interactions: W1 drives W2 to W7. W6 row selection drives W8 and W9. The picker and W6 auto-select their first row.

## Views (authored before the dashboard)

- `Synology Storage Pools`: `knowledge/designs/views/synology-storage-pools.md`
- `Synology Volumes`: `knowledge/designs/views/synology-volumes.md`
- `Synology SSD Caches`: `knowledge/designs/views/synology-ssd-caches.md`

## Known constraints

- #177: per DiskStation; with one NAS the auto-select makes that invisible.
- #175: views open in default order.
- #176: free bytes and cache hit rate are uncolored.
- Pool and volume capacity keys are wrong in the adapter (used = total, free = 0, status normal; live recon 2026-09-25). W4, W8 and the capacity columns are BLOCKED on an adapter fix (Synology issue to be filed); no capacity colors or trends until then. The dashboard still earns its place on status, cache, IO and alerts.
- W4 needs `relationship_mode: children` (first use in shipped content).
