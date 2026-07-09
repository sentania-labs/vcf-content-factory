# Synology DSM API Map: Overview

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `$SYNO_HOST:$SYNO_PORT` — DS1520+ running DSM
  7.3.2-86009 Update 1
- **Last updated:** 2026-05-19
- **Update history:**
  - 2026-05-19 — SSD cache deep dive by api-explorer. Closed
    gap #8: captured full verbatim `sharedCaches[]` and
    `ssdCaches[]` from `load_info` with complete field
    references. Documented `storagePools[].cache_disks` as the
    pool-to-cache link. Added NVMe disk distinguishing fields.
    Confirmed NVMe IO works in Utilization (current + history).
    Dead-ended `Flashcache`, `Cache.Protection`,
    `Core.Storage.Volume` APIs (no valid methods on DSM 7.3.2).
    Updated `synology-storage.md` with all findings.
  - 2026-05-18 — Added `synology-vcfops-stitching.md` entry to
    the file index. That map documents how to bind Synology
    iSCSI LUNs and NFS exports onto existing VMWARE Datastores
    in VCF Ops (ARIA_OPS pattern). Includes the empirically
    verified Synology LUN UUID → ESXi NAA transform. No changes
    to the Synology endpoint inventory or object summary in this
    overview file beyond the new row in the map index.
  - 2026-05-18 — Added NFS Export object type. New rows in
    Object Inventory, Endpoint Inventory, Cross-Request Join
    Keys, and Object Model Summary. Linked `synology-nfs.md` in
    the map file index. Bumped collection-strategy headers for
    the new per-share `SharePrivilege` and `CurrentConnection`
    calls.
  - 2026-04-16 — Original overview content (storage, iSCSI,
    docker, UPS, system, events).
- **Evidence basis:** synthesized from sibling map files
  (`synology-*.md`); the 2026-05-18 stitching entry was authored
  from live API calls against both Synology
  (`storage.int.sentania.net:5001`) and VCF Ops
  (`vcf-lab-operations.int.sentania.net`, profile `prod`).

## Target System

| Property | Value |
|---|---|
| Model | DS1520+ |
| DSM Version | 7.3.2-86009 Update 1 |
| Base URL | `https://<host>:5001/webapi/entry.cgi` |
| Auth type | SESSION (SYNO.API.Auth v7, `_sid` query parameter) |
| Total APIs available | 674 |
| Admin account required | Yes (for all Core.* and Storage.CGI.* APIs) |

## API Map Files

| File | Scope |
|---|---|
| `synology-auth.md` | Authentication flow, session management, error codes |
| `synology-system.md` | Diskstation object: system info, CPU, memory, network, fan |
| `synology-storage.md` | Storage Pool, Volume, Disk objects: capacity, health, IO |
| `synology-iscsi.md` | iSCSI LUN object: metadata, IO metrics, target IQN |
| `synology-nfs.md` | NFS Export object: per-share inventory, rules, client tallies; NFS service properties on Diskstation `[2026-05-18]` |
| `synology-docker.md` | Docker Container object: status, resource usage |
| `synology-ups.md` | UPS object: status, battery, load |
| `synology-events.md` | DSM notifications / events: SyslogClient.Log, Upgrade.Server.check, SecurityAdvisor.LoginActivity -- for MPB events section |
| `synology-vcfops-stitching.md` | ARIA_OPS stitching — joining Synology iSCSI LUNs / NFS exports to existing VMWARE Datastores in VCF Ops via the `DataStrorePath` resource identifier; includes the empirically-verified Synology LUN UUID → ESXi NAA transform `[2026-05-18]` |

## Endpoint Inventory

| # | API | Method | Object(s) Fed | Interval | Notes |
|---|---|---|---|---|---|
| 1 | `SYNO.API.Auth` | `login` | (session) | On-demand | Re-auth on 106/107/119 |
| 2 | `SYNO.DSM.Info` | `getinfo` | Diskstation | 5 min | Model, serial, temp, uptime, version |
| 3 | `SYNO.Core.System.Utilization` | `get` | Diskstation, Disk, Volume, iSCSI LUN | 5 min | CPU, memory, network, per-disk IO, per-LUN IO |
| 4 | `SYNO.Storage.CGI.Storage` | `load_info` | Storage Pool, Volume, Disk | 5 min | Full storage topology in one call |
| 5 | `SYNO.Core.System` | `info` | Diskstation | 15 min | CPU details, firmware, NTP, timezone |
| 6 | `SYNO.Core.Hardware.FanSpeed` | `get` | Diskstation | 15 min | Fan status |
| 7 | `SYNO.Core.Network.Interface` | `list` | Diskstation | 15 min | NIC inventory |
| 8 | `SYNO.Core.ISCSI.LUN` | `list` | iSCSI LUN | 15 min | LUN metadata |
| 9 | `SYNO.Core.ISCSI.Target` | `list` | iSCSI LUN | 15 min | Target IQN for ESXi correlation |
| 10 | `SYNO.Core.ExternalDevice.UPS` | `get` | UPS | 15 min | UPS status (if connected) |
| 11 | `SYNO.Core.System.Status` | `get` | Diskstation | 30 min | Crash flag, upgrade flag |
| 12 | `SYNO.Docker.Container` | `list` | Docker Container | 30 min | Container inventory and status |
| 13 | `SYNO.Core.FileServ.NFS` | `get` | Diskstation (NFS service props) | 5 min | NFS server enabled, v4 settings `[2026-05-18]` |
| 14 | `SYNO.Core.Share` | `list` | NFS Export | 5 min | All shares + capacity; with `additional` array `[2026-05-18]` |
| 15 | `SYNO.Core.FileServ.NFS.SharePrivilege` | `load` | NFS Export | 5 min (or 30) | Per-share NFS rules; **N+1 calls** keyed by `share_name=` — consider caching at 30-min cycle `[2026-05-18]` |
| 16 | `SYNO.Core.CurrentConnection` | `get` | NFS Export, Diskstation | 5 min | Active NFS client list; tally by `descr` for per-export counts `[2026-05-18]` |

**Total unique endpoints**: 16 (including auth) `[2026-05-18]`
**Requests per 5-min cycle**: 3 + 3 + N_shares = 6 + N (auth cached; DSM.Info + Utilization + Storage.load_info + NFS get + Share list + CurrentConnection get + 1 SharePrivilege call per share) — on this NAS with 11 shares: 17 requests `[2026-05-18]`
**Requests per 15-min cycle**: 17 + 5 = 22 (add System.info, FanSpeed, Interface, ISCSI.LUN, ISCSI.Target, UPS)
**Requests per 30-min cycle**: 22 + 2 = 24 (add System.Status, Docker.Container)

## Object Model Summary

| Object Type | Identifier | Parent | Source Endpoints | Metrics | Properties |
|---|---|---|---|---|---|
| Diskstation | serial | (world) | DSM.Info, Core.System, Utilization, FanSpeed, Interface, System.Status | 18 | 16 |
| Storage Pool | pool_id | Diskstation | Storage.load_info | 3 | 5 |
| Volume | volume_id + vol_path | Storage Pool | Storage.load_info, Utilization (space.volume[]) | 5 | 6 |
| Disk | disk_id | Storage Pool + Diskstation | Storage.load_info, Utilization (disk[]) | 6 | 10 |
| iSCSI LUN | lun_uuid | Volume | ISCSI.LUN, ISCSI.Target, Utilization (lun[]) | 10 | 5 |
| NFS Export `[2026-05-18]` | name (alt: uuid) | Volume | Share.list, FileServ.NFS.SharePrivilege.load, CurrentConnection.get | 4 | 10 |
| Docker Container | container_name | Diskstation | Docker.Container | 3 | 4 |
| UPS | model | Diskstation | ExternalDevice.UPS | 3 | 2 |

**Totals**: 8 object types, ~52 metrics, ~58 properties `[2026-05-18]`

## Cross-Request Join Keys

| Field A | Endpoint A | Field B | Endpoint B | Relationship |
|---|---|---|---|---|
| `storagePools[].pool_path` | Storage.load_info | `volumes[].pool_path` | Storage.load_info | Pool -> Volume |
| `storagePools[].disks[]` | Storage.load_info | `disks[].id` | Storage.load_info | Pool -> Disk |
| `disks[].used_by` | Storage.load_info | `storagePools[].id` | Storage.load_info | Disk -> Pool (reverse) |
| `volumes[].vol_path` | Storage.load_info | `luns[].location` | ISCSI.LUN | Volume -> iSCSI LUN |
| `luns[].name` | ISCSI.LUN | `lun[].lun_name` | Utilization | LUN metadata -> LUN IO |
| `luns[].uuid` | ISCSI.LUN | `lun[].uuid` | Utilization | LUN metadata -> LUN IO (redundant join) |
| `targets[].name` | ISCSI.Target | `luns[].name` | ISCSI.LUN | Target -> LUN (by naming convention) |
| `disks[].id` | Storage.load_info | `disk[].device` | Utilization | Disk metadata -> Disk IO |
| `volumes[].vol_path` (strip "/") | Storage.load_info | `space.volume[].display_name` | Utilization | Volume metadata -> Volume IO |
| `shares[].vol_path` | Share.list | `volumes[].vol_path` | Storage.load_info | NFS Export -> Volume (parent) `[2026-05-18]` |
| `shares[].name` | Share.list | `share_name` (query param) | FileServ.NFS.SharePrivilege.load | Drives per-share rule fetch `[2026-05-18]` |
| `shares[].name` | Share.list | `items[].descr` (filter `protocol='NFS'`) | CurrentConnection.get | NFS Export -> active client list `[2026-05-18]` |
| derived `vol_path + "/" + name` | local | ESXi NFS datastore mount `host:/volume1/<share>` | vSphere | NFS Export -> Datastore (cross-MP stitch) `[2026-05-18]` |
| `containers[].name` | Docker.Container list | `resources[].name` | Docker.Container.Resource get | Container metadata -> Container resource metrics |

## Coverage Matrix: Design Artifact vs. API Sources

### Diskstation (33 existing + 6 new = 39 total)

| Metric/Property | Source | Status |
|---|---|---|
| CPU Clock Speed, Cores, Family, Series, Vendor | Core.System info | CONFIRMED |
| Model, RAM Size, Serial, Hostname | DSM.Info / Core.System info | CONFIRMED |
| Firmware Date/Ver | Core.System info | CONFIRMED |
| Sys Temp | DSM.Info / Core.System info | CONFIRMED |
| NTP Enabled/Server, Time Zone | Core.System info | CONFIRMED |
| CPU Load 1/5/15min | Utilization cpu | CONFIRMED |
| CPU User, System, Other | Utilization cpu | CONFIRMED |
| Memory Avail/Total Real, Real Usage, Cached, Buffer | Utilization memory | CONFIRMED |
| Swap Usage/Total/Avail/Si/So | Utilization memory | CONFIRMED |
| Uptime | DSM.Info (numeric seconds) | CONFIRMED |
| **memory_usage_pct** (NEW) | Utilization memory.real_usage | CONFIRMED (pre-calculated by API) |
| **cpu_total_load** (NEW) | Utilization cpu (user + system) | CONFIRMED (calculated) |
| **fan_status** (NEW) | Hardware.FanSpeed cool_fan | CONFIRMED ("yes"/"no"; no RPM available via REST) |
| **fan_speed_mode** (NEW) | Hardware.FanSpeed dual_fan_speed | CONFIRMED ("coolfan" etc.; policy not RPM) |
| **net_rx_bytes** (NEW) | Utilization network[].rx | CONFIRMED |
| **net_tx_bytes** (NEW) | Utilization network[].tx | CONFIRMED |
| **nic_count** (NEW) | Network.Interface list (array length) | CONFIRMED |

### Storage Pool (6 existing + 4 new = 10 total)

| Metric/Property | Source | Status |
|---|---|---|
| Device Type, ID, Num ID, Pool Path | Storage.load_info storagePools[] | CONFIRMED |
| Total, Used | Storage.load_info storagePools[].size | CONFIRMED |
| **usage_pct** (NEW) | Calculated from size.used/total | CONFIRMED |
| **status** (NEW) | Storage.load_info storagePools[].status | CONFIRMED |
| **raid_type** (NEW) | Storage.load_info storagePools[].raidType | CONFIRMED |
| **disk_count** (NEW) | Storage.load_info storagePools[].disks.length | CONFIRMED |

### Volume (10 existing + 3 new = 13 total)

| Metric/Property | Source | Status |
|---|---|---|
| Description, Display Name, Fs Type, Pool Path | Storage.load_info volumes[] | CONFIRMED |
| RAID Type, Status, Volume ID, Volume Path | Storage.load_info volumes[] | CONFIRMED |
| Size Free/Total Byte | Storage.load_info volumes[].size | CONFIRMED |
| **usage_pct** (NEW) | Calculated from size.used/total | CONFIRMED |
| **io_read_bytes** (NEW) | Utilization space.volume[].read_byte | CONFIRMED (bytes/s) |
| **io_write_bytes** (NEW) | Utilization space.volume[].write_byte | CONFIRMED (bytes/s) |
| **io_read_access** (NEW) | Utilization space.volume[].read_access | CONFIRMED (IOPS) |
| **io_write_access** (NEW) | Utilization space.volume[].write_access | CONFIRMED (IOPS) |
| **utilization** (NEW) | Utilization space.volume[].utilization | CONFIRMED (%) |

### Disk (11 existing + 7 new = 18 total)

| Metric/Property | Source | Status |
|---|---|---|
| Device, Firm, Model, Name, Serial | Storage.load_info disks[] | CONFIRMED |
| Size Total, Slot ID, Smart Status | Storage.load_info disks[] | CONFIRMED |
| Used By, Vendor, Wcache Force Off | Storage.load_info disks[] | CONFIRMED |
| **temp** (NEW) | Storage.load_info disks[].temp | CONFIRMED |
| **unc_sectors** (NEW) | Storage.load_info disks[].unc | CONFIRMED |
| **remain_life** (NEW) | Storage.load_info disks[].remain_life | CONFIRMED (-1 for HDD) |
| **io_read_bytes** (NEW) | Utilization disk.disk[].read_byte | CONFIRMED (bytes/s) |
| **io_write_bytes** (NEW) | Utilization disk.disk[].write_byte | CONFIRMED (bytes/s) |
| **io_read_access** (NEW) | Utilization disk.disk[].read_access | CONFIRMED (IOPS) |
| **io_write_access** (NEW) | Utilization disk.disk[].write_access | CONFIRMED (IOPS) |
| **utilization** (NEW) | Utilization disk.disk[].utilization | CONFIRMED (%) |
| **disk_type** (NEW) | Storage.load_info disks[].diskType | CONFIRMED |

### iSCSI LUN (NEW -- 12 total)

| Metric/Property | Source | Status |
|---|---|---|
| name, uuid, size, location, type_str | ISCSI.LUN list | CONFIRMED |
| read_iops, write_iops | Utilization lun[] | CONFIRMED (live-tested) |
| read_throughput, write_throughput | Utilization lun[] | CONFIRMED (live-tested) |
| read_latency, write_latency | Utilization lun[] | CONFIRMED (live-tested) |

### NFS Export (NEW 2026-05-18 -- 14 total)

| Metric/Property | Source | Status |
|---|---|---|
| name, uuid, vol_path, desc | Share.list shares[] | CONFIRMED `[observed 2026-05-18]` |
| export_path (vol_path + "/" + name) | derived | CONFIRMED (derivable) |
| quota_value, encryption, hidden | Share.list shares[] | CONFIRMED `[observed 2026-05-18]` |
| enable_share_cow, enable_share_compress | Share.list shares[] | CONFIRMED `[observed 2026-05-18]` |
| share_size_used, share_size_logical | Share.list shares[] | CONFIRMED `[observed 2026-05-18]` (units inferred MiB) |
| quota_usage_pct | derived | CONFIRMED (derivable) |
| rule_count, allowed_clients (joined) | NFS.SharePrivilege.load data.rule[] | CONFIRMED `[observed 2026-05-18]` |
| has_kerberos_required, has_root_squash, has_readonly_clients | derived from rules | CONFIRMED (derivable) |
| active_client_count | CurrentConnection.get filter protocol=NFS, group by descr | CONFIRMED `[observed 2026-05-18]` |
| per-share NFS IO (bytes/OPS/latency) | (none) | CONFIRMED NOT AVAILABLE — fall back to parent Volume IO `[observed 2026-05-18]` |

### Diskstation NFS service (NEW 2026-05-18 -- adds 11 to Diskstation total)

| Metric/Property | Source | Status |
|---|---|---|
| nfs_enabled, nfs_v4_enabled, nfs_active_minor_ver | FileServ.NFS.get | CONFIRMED `[observed 2026-05-18]` |
| nfs_read_size, nfs_write_size | FileServ.NFS.get | CONFIRMED `[observed 2026-05-18]` |
| nfs_total_ops, nfs_read_ops, nfs_write_ops | Utilization nfs[0] | CONFIRMED `[observed 2026-05-18]` |
| nfs_total_max_latency | Utilization nfs[0] | CONFIRMED `[observed 2026-05-18]` (units inferred ms) |
| nfs_total_client_count | derived from CurrentConnection | CONFIRMED `[observed 2026-05-18]` |
| nfs_export_count | derived | CONFIRMED (derivable) |

### Docker Container (NEW -- 10 total)

| Metric/Property | Source | Status |
|---|---|---|
| name, status, image | Docker.Container list | CONFIRMED |
| health | Docker.Container list State.Health.Status | CONFIRMED |
| **cpu** | Docker.Container.Resource get | CONFIRMED (float, %) |
| **memory** | Docker.Container.Resource get | CONFIRMED (bytes) |
| **memoryPercent** | Docker.Container.Resource get | CONFIRMED (float, % of NAS RAM) |
| **State.StartedAt** | Docker.Container list | CONFIRMED (ISO 8601; derive uptime from this) |
| **up_time** | Docker.Container list | CONFIRMED NOT AVAILABLE (always null) |
| compose_project, compose_service | Docker.Container list Labels | CONFIRMED |
| is_ddsm, is_package | Docker.Container list | CONFIRMED |

### UPS (NEW -- 8 total)

| Metric/Property | Source | Status |
|---|---|---|
| model | ExternalDevice.UPS get | CONFIRMED (empty string when no UPS) |
| status | ExternalDevice.UPS get | CONFIRMED ("usb_ups_status_unknown" when no UPS; NUT codes when connected) |
| **charge** | ExternalDevice.UPS get | CONFIRMED (was assumed to be `battery_charge`; returns 0 when no UPS) |
| **runtime** | ExternalDevice.UPS get | CONFIRMED (seconds; returns 0 when no UPS) |
| **manufacture** | ExternalDevice.UPS get | CONFIRMED (was assumed to be `vendor`) |
| **usb_ups_connect** | ExternalDevice.UPS get | CONFIRMED (boolean: UPS physically present) |
| **mode** | ExternalDevice.UPS get | CONFIRMED ("MASTER"/"SLAVE") |
| load | ExternalDevice.UPS get | NOT AVAILABLE -- no load field in response (may require SNMP) |

## Gaps and Open Questions

### Closed via live API exploration (2026-04-16)

1. **Per-disk IO field names** -- CONFIRMED. Fields are `read_byte`, `write_byte`, `read_access`, `write_access`, `utilization` in `data.disk.disk[]`. Also includes `display_name` and `type`. Aggregate totals at `data.disk.total`.

2. **Per-volume IO field names** -- CONFIRMED. Same field schema as per-disk: `read_byte`, `write_byte`, `read_access`, `write_access`, `utilization` in `data.space.volume[]`. Join key is `display_name` (e.g., "volume1") matching `vol_path` sans leading "/".

3. **Docker Container resource metrics** -- CONFIRMED. CPU/memory are NOT in the `list` response. They come from a separate API: `SYNO.Docker.Container.Resource` method `get` (version 1). Returns `cpu` (float %), `memory` (bytes), `memoryPercent` (float %) for all running containers in one call. Uptime (`up_time`) is always `null` -- derive from `State.StartedAt` timestamp.

4. **UPS response fields** -- CONFIRMED (no-UPS case). Field names corrected: `charge` (not `battery_charge`), `runtime` (confirmed), `manufacture` (not `vendor`). No `load` field observed. New fields discovered: `usb_ups_connect`, `mode`, `enable`, `delay_time`, `shutdown_device`. Connected-UPS response structure inferred but not directly testable.

5. **Fan speed numeric value** -- CONFIRMED NOT AVAILABLE. `SYNO.Core.Hardware.FanSpeed` returns fan policy/mode only: `cool_fan` ("yes"/"no"), `dual_fan_speed` ("coolfan"), `fan_type` (numeric code). No RPM value. RPM readings require SNMP.

### Design considerations

6. **Dual-parent relationship for Disk** (child of both Diskstation and Storage Pool) -- flagged as Key Risk #1. MPB support for dual parents needs validation.

7. **Network aggregation** -- the Utilization `network[]` array has per-NIC data. The design puts net_rx/tx on the Diskstation object. MPB needs to either sum across NICs or pick one.

8. **SSD cache as separate object vs. property** -- FULLY MAPPED
   2026-05-19. `ssdCaches[]` provides a complete SSD Cache object:
   `hit_rate` (83% read), `hit_rate_write` (99%), `hit_rates`
   per-interval breakdown (7 intervals with `io_hit` /
   `io_need_acceleration`), `size.{total,occupied,reusable}`,
   `memory` (metadata cache RAM), `mode` (read/write), `status`,
   `space_status`. Cache disks are in `disks[]` with
   `portType:"cache"`, `isSsd:true`, `diskType:"M.2 NVMe"`.
   `storagePools[].cache_disks` provides the pool-to-cache-disk
   link. Full verbatim schemas in `synology-storage.md`.
   No additional endpoint needed -- `load_info` has everything.

9. **LUN-to-Target mapping method** -- current join is by naming convention. `SYNO.Core.ISCSI.LUN` may have a `map_target` method for authoritative mapping. Needs investigation.
