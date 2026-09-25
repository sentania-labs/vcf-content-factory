# [VCF Content Factory] Synology Disk Health

- **Type:** dashboard (bundled in the pak)
- **Slug:** synology-disk-health
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-disk-health.yaml
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/synology-disk-health.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- **Why an admin wants it:** Answers 'which drive is going to fail next': every drive's SMART status, temperature and uncorrectable sectors in one map and one list, with trends for the one you pick.
- Pick a DiskStation; a heatmap of every drive grouped by pool (tabs for sectors, temperature, busy), the drive list, then a drive's health and IO trend and hardware details for an RMA.
- Audience: the admin deciding whether to order a replacement drive.
- Uncorrectable sectors growing over time is the lead indicator; the trend chart is there to show growth, not just the current count.
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist on the instance or in the repo.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Keys

All keys from `content/sdk-adapters/synology/describe.xml`. Drive names, models, serials from the v1 golden baseline; values simulated. Every key below is cited exactly as `<ResourceGroup key>|<ResourceAttribute key>`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | DiskStation | ResourceList | 1, 1, 3, 9 | `synology_diskstation` `SynologyDiskstation` | Picker, name only. Drives W2, W3 |
| W2 | Drive Health Map | Heatmap | 4, 1, 9, 9 | driven by W1, `SynologyDisk` | Group by `SynologyStoragePool`, fixed size. Tabs: Uncorrectable sectors `Health\|unc_sectors` (grey below 0 for the NVMe -1 sentinel, green 0, orange 1, red 50); Temperature `Health\|temperature` (green 30, yellow 45, red 55); Busy `IO\|utilization_pct` (green 0, yellow 70, red 90) |
| W3 | Drives | View | 1, 10, 12, 8 | driven by W1, `SynologyDisk` | View `Synology Disks`. Row select drives W4, W5, W6 |
| W4 | Health Trend: Drive 2 | MetricChart | 1, 18, 5, 7 | driven by W3 | `Health\|unc_sectors`, `Health\|temperature`, 30 days |
| W5 | Drive IO: Drive 2 | MetricChart | 6, 18, 4, 7 | driven by W3 | `IO\|read_iops`, `IO\|write_iops`, `IO\|utilization_pct`, 7 days |
| W6 | Drive Details: Drive 2 | PropertyList | 10, 18, 3, 7 | driven by W3 | `Hardware\|model`, `Hardware\|vendor`, `Hardware\|serial`, `Hardware\|firmware`, `Hardware\|disk_type`, `Hardware\|size_bytes`, `Hardware\|slot_id`, `Health\|smart_status` |

Interactions: W1 drives W2 and W3. W3 row selection drives W4, W5, W6. W3 auto-selects its first row.

## Views (authored before the dashboard)

- `Synology Disks`: `knowledge/designs/views/synology-disks.md`

## Known constraints

- #177: per DiskStation.
- #175: the drive list opens in default order; click Unc. sectors to sort worst first.
- `Health|remain_life` removed everywhere: 0 on every disk, SATA and NVMe, never populated (live recon 2026-09-25).
- Cache NVMe drives are children of both the pool and the SSD cache; the heatmap groups by pool so they appear once.
- `Health|unc_sectors` = -1 is the NVMe no-data sentinel (live recon 2026-09-25). Display rule: n/a in the view, a grey band below 0 on the heatmap. If a Heatmap scale cannot start below 0, the NVMe cells paint green; accept or drop the cache drives from the tab via the view filter.
