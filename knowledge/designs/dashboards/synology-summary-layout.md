# [VCF Content Factory] Synology Summary dashboards (shared layout)

- **Type:** dashboard layout (one design, instantiated as one summary dashboard per resource kind, bundled in the pak)
- **Slug:** synology-summary-layout
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-<kind>.yaml (one per kind, see the per-kind intent files)
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Every Synology object's Summary tab shows one familiar page: who it is, whether it is healthy, its alerts, two trends that matter for that kind, what hangs off it, and where it sits in the tree.
- One layout, so an admin learns it once; the keys in each slot are chosen per kind so the page says something real about the object, which was Scott's condition for a shared layout.
- Audience: the admin who clicked through to an object from a general dashboard, an alert, or the inventory tree.
- Out of scope: new super metrics, symptoms or alerts (listed as open questions), and any change to the adapter.
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist anywhere (instance or repo). Author is required.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Binding

Each kind gets its own dashboard YAML with `summary_for: ["synology_diskstation:<ResourceKind>"]`; the SDK builder writes one `content/dashboards/dashboards.properties` line per dashboard directory (`knowledge/context/api-surface/summary_dashboard_pak_binding.md`). `summary_for` can list several kinds on one dashboard, but every widget here binds kind-specific keys, so a shared *layout* means 9 dashboards built from this one design. Every widget is `self_provider: false` with no pinned resource (loader rule for `summary_for`).

**Adapter instance excluded.** `synology_diskstation:synology_diskstation` keeps the product's native Summary page (coordinator default 2026-09-25, Scott can override). Binding a dashboard there would replace the native collection-status page every adapter instance shares, and the collection-health keys it could show (`Instance Attributes|*`) are already on that page. So this layout covers 9 kinds, not 10.

Names: `[VCF Content Factory] Synology <Kind> Summary`. Suggested folder (`namePath`): `VCF Content Factory/Synology/Summary`.

## Shared slot grid (12 columns)

| Slot | Widget | Type | Grid (col, row, w, h) | What fills it |
|---|---|---|---|---|
| S1 | Identity | PropertyList (TextDisplay on keys-less kinds) | 1, 1, 4, 8 | The object's key properties, most decision-relevant first. Kinds with no properties get a TextDisplay that says what the object is. |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 (4, 8 when S3 is dropped) | `badge|health`, `System Attributes|alert_count_critical`, `System Attributes|alert_count_immediate`, `System Attributes|alert_count_warning`. Identical on every kind; bound per kind. |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | Two to four current values that answer 'is this object OK'. Dropped on kinds with no metrics. |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active alerts, criticality Warning and up. Scope: own only on leaf kinds, own and descendants on kinds with children. |
| S5 | Trend A | MetricChart | 1, 9, 6, 7 (12 wide when S6 is dropped) | The primary trend for the kind. On container kinds, a per-child chart (`relationship_mode: children`). |
| S6 | Trend B | MetricChart | 7, 9, 6, 7 | The secondary trend. Dropped when the kind has no second monitored series. |
| S7 | Related Objects / Details | View, PropertyList, MetricChart or Heatmap | 1, 16, 8, 9 (row moves up to 9 when S5 and S6 are both dropped) | Kinds with children: a list View of the children (two half-width Views when there are two primary child kinds). Leaf kinds: the remaining properties as a PropertyList, or a third chart if no properties are left. Containers whose children have no metrics: a device Heatmap. Dropped when nothing is left. |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 (12 wide when S7 is dropped) | Parents and children of the page object, including foreign parents from the cross-adapter stitches (ESXi host on a switch port, VMware datastore on a LUN or NFS export). |

Interactions: none. Every widget receives the Summary page object.

## Per-kind fill

Keys are `<ResourceGroup key>|<ResourceAttribute key>` from `content/sdk-adapters/synology/describe.xml`, exactly as the adapter emits them. Grid is (col, row, w, h).

### Synology World (`synology_diskstation:SynologyWorld`)

Intent file: `knowledge/designs/dashboards/synology-summary-world.md`. Layout: container: S1 is a TextDisplay (the World carries no keys), S3 dropped, S5 and S6 are per-child MetricCharts over DiskStations.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | About this World | TextDisplay | 1, 1, 4, 8 | Static text: what this object is and where to go instead (no keys exist on this kind) |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 8 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Temperature per DiskStation | MetricChart | 1, 9, 6, 7 | `relationship_mode: children`, child kind `SynologyDiskstation`, `System\|system_temp`, 7 d |
| S6 | Memory Used per DiskStation | MetricChart | 7, 9, 6, 7 | `relationship_mode: children`, child kind `SynologyDiskstation`, `Memory\|memory_usage_pct`, 7 d |
| S7 | DiskStations | View | 1, 16, 8, 9 | View `Synology DiskStations` (subject `SynologyDiskstation`), design `knowledge/designs/views/synology-diskstations.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"0,2"` (ancestors, descendants) |

Key notes: Only platform keys on the World itself.

### Synology Diskstation (`synology_diskstation:SynologyDiskstation`)

Intent file: `knowledge/designs/dashboards/synology-summary-diskstation.md`. Layout: standard.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | DiskStation | PropertyList | 1, 1, 4, 8 | `System\|model`, `System\|hostname`, `System\|firmware_version`, `System\|firmware_date`, `Fan\|fan_status`, `Fan\|fan_speed_mode`, `NFS\|nfs_enabled`, `NFS\|nfs_v4_enabled`, `System\|uptime` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `System\|system_temp`, `CPU\|cpu_load_5m`, `Memory\|memory_usage_pct`, `NFS\|nfs_client_count` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | CPU, Memory, Temperature | MetricChart | 1, 9, 6, 7 | `CPU\|cpu_load_1m`, `CPU\|cpu_load_5m`, `Memory\|memory_usage_pct`, `System\|system_temp`, 7 d |
| S6 | Network and NFS | MetricChart | 7, 9, 6, 7 | `Network\|net_rx_bytes`, `Network\|net_tx_bytes`, `NFS\|nfs_total_ops`, `NFS\|nfs_max_latency`, 7 d |
| S7 | Storage Pools | View | 1, 16, 8, 9 | View `Synology Storage Pools` (subject `SynologyStoragePool`), design `knowledge/designs/views/synology-storage-pools.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"1,1"` (ancestors, descendants) |

Key notes: CPU|cpu_total_load, cpu_user_pct and cpu_system_pct read 0 in the v1 baseline while cpu_load_* did not, so the design uses cpu_load_*. Memory byte keys looked like KiB in v1 (memory_total=20328576 on a 20 GB box); the design uses Memory|memory_usage_pct only.

### Synology Storage Pool (`synology_diskstation:SynologyStoragePool`)

Intent file: `knowledge/designs/dashboards/synology-summary-storage-pool.md`. Layout: standard (S6 is a per-child MetricChart over member disks).

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Pool | PropertyList | 1, 1, 4, 8 | `Configuration\|status`, `Configuration\|device_type`, `Configuration\|raid_type`, `Configuration\|pool_path` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | **BLOCKED on adapter fix (Synology issue to be filed).** Intended keys `Capacity\|usage_pct`, `Capacity\|used_bytes`, `Capacity\|total_bytes`; the adapter reports used = total and free = 0 while status is normal (live recon 2026-09-25). Author the slot as a TextDisplay stating this until the fix lands, then swap in the widget |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Capacity Used | MetricChart | 1, 9, 6, 7 | **BLOCKED on adapter fix (Synology issue to be filed).** Intended keys `Capacity\|usage_pct`, `Capacity\|used_bytes`; the adapter reports used = total and free = 0 while status is normal (live recon 2026-09-25). Author the slot as a TextDisplay stating this until the fix lands, then swap in the widget |
| S6 | Member Disk Temperature | MetricChart | 7, 9, 6, 7 | `relationship_mode: children`, child kind `SynologyDisk`, `Health\|temperature`, 7 d |
| S7 | Disks | View | 1, 16, 8, 9 | View `Synology Disks` (subject `SynologyDisk`), design `knowledge/designs/views/synology-disks.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): Capacity|used_bytes equals Capacity|total_bytes on every sample for 6 h while Configuration|status reads normal, so usage_pct is a constant 100 from an adapter mapping bug. S3 and S5 keep their slots, greyed and BLOCKED on an adapter fix (Synology issue to be filed); no capacity colors or trends until then. Configuration|disk_count is defaultMonitored=false; left out.

### Synology Volume (`synology_diskstation:SynologyVolume`)

Intent file: `knowledge/designs/dashboards/synology-summary-volume.md`. Layout: standard, S7 split into two half-width Views (NFS exports | iSCSI LUNs) because a volume has two primary child kinds.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Volume | PropertyList | 1, 1, 4, 8 | `Configuration\|volume_path`, `Configuration\|fs_type`, `Configuration\|status`, `Configuration\|description`, `Cache\|cache_enabled`, `Cache\|cache_status` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `IO\|utilization_pct`, `IO\|read_iops`, `IO\|write_iops`, `Cache\|cache_read_hit_rate` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Capacity | MetricChart | 1, 9, 6, 7 | **BLOCKED on adapter fix (Synology issue to be filed).** Intended keys `Capacity\|usage_pct`, `Capacity\|free_bytes`, `Capacity\|total_bytes`; the adapter reports used = total and free = 0 while status is normal (live recon 2026-09-25). Author the slot as a TextDisplay stating this until the fix lands, then swap in the widget |
| S6 | IO | MetricChart | 7, 9, 6, 7 | `IO\|read_iops`, `IO\|write_iops`, `IO\|read_bytes`, `IO\|write_bytes`, `IO\|utilization_pct`, 7 d |
| S7a | NFS Exports | View | 1, 16, 4, 9 | View `Synology NFS Exports` (subject `SynologyNfsExport`), design `knowledge/designs/views/synology-nfs-exports.md` |
| S7b | iSCSI LUNs | View | 5, 16, 4, 9 | View `Synology iSCSI LUNs` (subject `SynologyIscsiLun`), design `knowledge/designs/views/synology-iscsi-luns.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): Capacity|free_bytes is 0 on every sample for 6 h while IO is active and status is normal, so usage_pct is a constant 100 from an adapter bug. Capacity tiles are off S3; S5 keeps its slot greyed and BLOCKED on an adapter fix (Synology issue to be filed). Cache|cache_write_hit_rate is left to the SSD cache page.

### Synology Disk (`synology_diskstation:SynologyDisk`)

Intent file: `knowledge/designs/dashboards/synology-summary-disk.md`. Layout: leaf: S7 is a PropertyList (remaining hardware properties).

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Drive | PropertyList | 1, 1, 4, 8 | `Hardware\|display_name`, `Hardware\|slot_id`, `Health\|smart_status`, `Hardware\|model`, `Hardware\|disk_type`, `Hardware\|size_bytes` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Health\|temperature`, `Health\|unc_sectors`, `IO\|utilization_pct` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Health Trend | MetricChart | 1, 9, 6, 7 | `Health\|temperature`, `Health\|unc_sectors`, 30 d |
| S6 | IO | MetricChart | 7, 9, 6, 7 | `IO\|read_iops`, `IO\|write_iops`, `IO\|read_bytes`, `IO\|write_bytes`, 7 d |
| S7 | Hardware | PropertyList | 1, 16, 8, 9 | `Hardware\|vendor`, `Hardware\|serial`, `Hardware\|firmware`, `Hardware\|is_ssd`, `Hardware\|disk_code` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,0"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): Health|remain_life is 0 on every disk, SATA and NVMe, for 6 h (never populated), so it is removed. Health|unc_sectors carries real values on SATA and a flat -1 no-data sentinel on NVMe cache drives: display rule, -1 shows as n/a and is uncolored (an NVMe page shows n/a in the tile and a flat line at -1 in S5, noted under the chart).

### Synology iSCSI LUN (`synology_diskstation:SynologyIscsiLun`)

Intent file: `knowledge/designs/dashboards/synology-summary-iscsi-lun.md`. Layout: leaf: S7 is a PropertyList (iSCSI target).

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | LUN | PropertyList | 1, 1, 4, 8 | `Configuration\|name`, `Configuration\|type`, `Configuration\|size_bytes`, `Configuration\|location`, `Configuration\|target_enabled` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `IO\|read_iops`, `IO\|write_iops`, `IO\|read_throughput`, `IO\|write_throughput` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | IOPS | MetricChart | 1, 9, 6, 7 | `IO\|read_iops`, `IO\|write_iops`, 7 d |
| S6 | Throughput | MetricChart | 7, 9, 6, 7 | `IO\|read_throughput`, `IO\|write_throughput`, 7 d |
| S7 | iSCSI Target | PropertyList | 1, 16, 8, 9 | `Configuration\|target_iqn`, `Configuration\|network_portals` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,0"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): IO|read_latency and IO|write_latency are 0 on every sample for 6 h while write IOPS reached 1112, so the adapter does not populate them. Removed from tiles and charts; IOPS and throughput kept.

### Synology NFS Export (`synology_diskstation:SynologyNfsExport`)

Intent file: `knowledge/designs/dashboards/synology-summary-nfs-export.md`. Layout: leaf: S7 is a PropertyList (access rules).

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Export | PropertyList | 1, 1, 4, 8 | `Configuration\|export_path`, `Configuration\|volume_path`, `Configuration\|description`, `Configuration\|quota_value_mib` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Capacity\|size_used_mib`, `Capacity\|quota_usage_pct`, `Clients\|active_client_count` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Used and Quota | MetricChart | 1, 9, 6, 7 | `Capacity\|size_used_mib`, `Capacity\|quota_usage_pct`, 30 d |
| S6 | Active Clients | MetricChart | 7, 9, 6, 7 | `Clients\|active_client_count`, 7 d |
| S7 | Access | PropertyList | 1, 16, 8, 9 | `Access\|allowed_clients`, `Access\|rule_count`, `Access\|cow_enabled`, `Access\|compress_enabled` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,0"` (ancestors, descendants) |

Key notes: Capacity|size_logical_mib is defaultMonitored=false; left out. A share with no quota reports quota_usage_pct 0.

### Synology UPS (`synology_diskstation:SynologyUps`)

Intent file: `knowledge/designs/dashboards/synology-summary-ups.md`. Layout: leaf: S7 dropped (no keys left), S8 widens to 12. UNVERIFIED: no UPS in the lab.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | UPS | PropertyList | 1, 1, 4, 8 | `Status\|status`, `Status\|mode`, `Status\|connected` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Battery\|charge_pct`, `Battery\|runtime_seconds` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Battery Charge | MetricChart | 1, 9, 6, 7 | `Battery\|charge_pct`, 30 d |
| S6 | Runtime | MetricChart | 7, 9, 6, 7 | `Battery\|runtime_seconds`, 30 d |
| S8 | Relationships | ResourceRelationshipAdvanced | 1, 16, 12, 9 | depth `"2,0"` (ancestors, descendants) |

Key notes: UNVERIFIED, ships as such (coordinator default 2026-09-25, Scott can override): recon found zero SynologyUps objects, so this page cannot be seen working in the lab; the release notes must say so. Charge and runtime are lower-is-worse and ship uncolored (#176). Status and mode values illustrative.

### Synology SSD Cache (`synology_diskstation:SynologySsdCache`)

Intent file: `knowledge/designs/dashboards/synology-summary-ssd-cache.md`. Layout: standard.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | SSD Cache | PropertyList | 1, 1, 4, 8 | `Configuration\|mode`, `Configuration\|status`, `Configuration\|device_type`, `Configuration\|mount_volume`, `Configuration\|skip_seq_io`, `Hardware\|total_capacity`, `Hardware\|disk_members`, `Hardware\|disk_count`, `Hardware\|disk_failure_count` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `HitRate\|read_hit_rate`, `HitRate\|write_hit_rate`, `Capacity\|occupied_bytes`, `Capacity\|total_bytes` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Hit Rates | MetricChart | 1, 9, 6, 7 | `HitRate\|read_hit_rate`, `HitRate\|write_hit_rate`, 7 d |
| S6 | Occupancy | MetricChart | 7, 9, 6, 7 | `Capacity\|occupied_bytes`, `Capacity\|total_bytes`, 30 d |
| S7 | Disks | View | 1, 16, 8, 9 | View `Synology Disks` (subject `SynologyDisk`), design `knowledge/designs/views/synology-disks.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: Capacity|reusable_bytes and Capacity|memory_used are defaultMonitored=false; left out. Hardware|disk_failure_count is a string property, so it displays but cannot be colored.

## Views this layout needs (authored before the dashboards)

- `Synology DiskStations`: `knowledge/designs/views/synology-diskstations.md`
- `Synology Storage Pools`: `knowledge/designs/views/synology-storage-pools.md`
- `Synology Disks`: `knowledge/designs/views/synology-disks.md`
- `Synology NFS Exports`: `knowledge/designs/views/synology-nfs-exports.md`
- `Synology iSCSI LUNs`: `knowledge/designs/views/synology-iscsi-luns.md`

## Known constraints

- First use of `summary_for` in this repo (recon 2026-09-25). The loader and SDK builder support it, but the install-time bind has only been exercised by the HostSystem smoke dashboard on a disposable build. Verify on qa with `getSummaryTabId` per kind before release.
- The installer binds a SUMMARY-template *copy* of each dashboard; editing the visible dashboard later does not change the Summary tab, reinstalling with force creates another template copy, and uninstall leaves the binding in place (clear with Manage Summary Dashboards, Use Default). Same doc as above.
- Each summary dashboard also appears in the Dashboards list. `disabled: true` hides it there without affecting the Summary tab (binding doc). Proposed: set it, so the list shows only the general dashboards.
- #177 does not apply here (no pickers). #175 applies to every S7 View: embedded views open in product default order; sort by clicking the header.
- #176: lower-is-worse keys (satisfaction, availability, remaining PoE, free bytes, remaining life, charge, runtime, hit rates) ship uncolored on Scoreboards and MetricCharts. Heatmaps are not affected: their color scale is set per tab, so red-at-low works there.
- `relationship_mode: children` on MetricChart is supported by the loader but not used by any shipped content yet; first use is here (Site, World, Storage Pool pages).
- ResourceRelationshipAdvanced (S8) is supported by the loader and renderer and ships in the vcommunity dashboards; it is not in the nine-widget list the brief named, so it is called out here. Fallback if rejected: drop S8 and widen S7 to 12.
- #173 (who authors content under `content/sdk-adapters/<name>/dashboards/`) is open and must be resolved, or carved out for this task as with compliance-v3, before dashboard-author spawns.

## Open questions for Scott

1. **Resolved by live recon 2026-09-25: pool and volume capacity keys are wrong in the adapter** (used = total, free = 0, status normal). Capacity slots stay in the layout, greyed and marked BLOCKED; no capacity colors or trends. **Action:** file the Synology adapter issue (not filed by this design pass).
2. **Resolved: `Health|remain_life` is never populated** (0 on every disk); removed everywhere. `Health|unc_sectors` = -1 on NVMe is a no-data sentinel; display rule: show n/a, uncolored. File an adapter issue for remain_life?
3. **Resolved: iSCSI latency is never populated** (0 while IOPS move); removed. Same adapter issue could cover it.
4. **Default applied: adapter instance keeps its native Summary page.** Override if you want the collection-health page.
5. **Default applied: UPS summary ships marked unverified** (no UPS in the lab). Override to hold it.
6. **Alerts.** As with UniFi, health stays green until symptoms and alerts exist. Candidate follow-on: pool or volume status not normal, SMART not normal, unc_sectors increasing, disk temperature, SSD cache member failed, NFS quota near full. File as an issue?
