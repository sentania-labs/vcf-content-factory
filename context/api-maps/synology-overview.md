# Synology DSM API Map: Overview

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
| `synology-docker.md` | Docker Container object: status, resource usage |
| `synology-ups.md` | UPS object: status, battery, load |

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

**Total unique endpoints**: 12 (including auth)
**Requests per 5-min cycle**: 3 (auth cached; DSM.Info + Utilization + Storage.load_info)
**Requests per 15-min cycle**: 3 + 5 = 8 (add System.info, FanSpeed, Interface, ISCSI.LUN, ISCSI.Target, UPS)
**Requests per 30-min cycle**: 8 + 2 = 10 (add System.Status, Docker.Container)

## Object Model Summary

| Object Type | Identifier | Parent | Source Endpoints | Metrics | Properties |
|---|---|---|---|---|---|
| Diskstation | serial | (world) | DSM.Info, Core.System, Utilization, FanSpeed, Interface, System.Status | 18 | 16 |
| Storage Pool | pool_id | Diskstation | Storage.load_info | 3 | 5 |
| Volume | volume_id + vol_path | Storage Pool | Storage.load_info, Utilization (space.volume[]) | 5 | 6 |
| Disk | disk_id | Storage Pool + Diskstation | Storage.load_info, Utilization (disk[]) | 6 | 10 |
| iSCSI LUN | lun_uuid | Volume | ISCSI.LUN, ISCSI.Target, Utilization (lun[]) | 10 | 5 |
| Docker Container | container_name | Diskstation | Docker.Container | 3 | 4 |
| UPS | model | Diskstation | ExternalDevice.UPS | 3 | 2 |

**Totals**: 7 object types, ~48 metrics, ~48 properties

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
| **fan_status** (NEW) | Hardware.FanSpeed | CONFIRMED |
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
| **io_read_iops** (NEW) | Utilization space.volume[] | NEEDS VERIFICATION -- field names not confirmed |
| **io_write_iops** (NEW) | Utilization space.volume[] | NEEDS VERIFICATION -- field names not confirmed |

### Disk (11 existing + 7 new = 18 total)

| Metric/Property | Source | Status |
|---|---|---|
| Device, Firm, Model, Name, Serial | Storage.load_info disks[] | CONFIRMED |
| Size Total, Slot ID, Smart Status | Storage.load_info disks[] | CONFIRMED |
| Used By, Vendor, Wcache Force Off | Storage.load_info disks[] | CONFIRMED |
| **temp** (NEW) | Storage.load_info disks[].temp | CONFIRMED |
| **unc_sectors** (NEW) | Storage.load_info disks[].unc | CONFIRMED |
| **remain_life** (NEW) | Storage.load_info disks[].remain_life | CONFIRMED (-1 for HDD) |
| **io_read** (NEW) | Utilization disk[] | NEEDS VERIFICATION -- field names not confirmed |
| **io_write** (NEW) | Utilization disk[] | NEEDS VERIFICATION -- field names not confirmed |
| **utilization** (NEW) | Utilization disk[] | NEEDS VERIFICATION -- field names not confirmed |
| **disk_type** (NEW) | Storage.load_info disks[].diskType | CONFIRMED |

### iSCSI LUN (NEW -- 12 total)

| Metric/Property | Source | Status |
|---|---|---|
| name, uuid, size, location, type_str | ISCSI.LUN list | CONFIRMED |
| read_iops, write_iops | Utilization lun[] | CONFIRMED (live-tested) |
| read_throughput, write_throughput | Utilization lun[] | CONFIRMED (live-tested) |
| read_latency, write_latency | Utilization lun[] | CONFIRMED (live-tested) |

### Docker Container (NEW -- 7 total)

| Metric/Property | Source | Status |
|---|---|---|
| name, status, image | Docker.Container list | CONFIRMED |
| health | Docker.Container list | CONFIRMED |
| cpu_usage | Docker.Container list/get | NEEDS VERIFICATION -- not confirmed in list response |
| memory_usage | Docker.Container list/get | NEEDS VERIFICATION -- not confirmed in list response |
| uptime | Docker.Container list/get | NEEDS VERIFICATION -- not confirmed in list response |

### UPS (NEW -- 5 total)

| Metric/Property | Source | Status |
|---|---|---|
| model, status | ExternalDevice.UPS get | NEEDS VERIFICATION -- no UPS connected on test NAS |
| battery_charge | ExternalDevice.UPS get | NEEDS VERIFICATION |
| load | ExternalDevice.UPS get | NEEDS VERIFICATION |
| runtime | ExternalDevice.UPS get | NEEDS VERIFICATION |

## Gaps and Open Questions

### Must verify via live API exploration

1. **Per-disk IO field names** in `SYNO.Core.System.Utilization` `data.disk[]` -- field names for read/write bytes and utilization % are not captured in any of the source docs. Community Prometheus exporter confirms they exist but does not document exact names.

2. **Per-volume IO field names** in `SYNO.Core.System.Utilization` `data.space.volume[]` -- mentioned in the brief but no field-level detail.

3. **Docker Container resource metrics** -- `list` response confirmed to include name/image/state/health. CPU/memory/uptime fields need verification: may require per-container `get` calls instead of being in the `list` response.

4. **UPS response fields** -- no UPS connected on test NAS. All field names are inferred from SNMP MIB patterns and NUT conventions.

5. **Fan speed numeric value** -- the brief confirms `SYNO.Core.Hardware.FanSpeed` `get` works but does not capture whether RPM is returned in addition to status string.

### Design considerations

6. **Dual-parent relationship for Disk** (child of both Diskstation and Storage Pool) -- flagged as Key Risk #1. MPB support for dual parents needs validation.

7. **Network aggregation** -- the Utilization `network[]` array has per-NIC data. The design puts net_rx/tx on the Diskstation object. MPB needs to either sum across NICs or pick one.

8. **SSD cache as separate object vs. property** -- the v1 design does not have SSD Cache as a separate object type. Cache disks (NVMe) are just Disk objects with `diskType: "NVMe"`. The `sharedCaches[]` response data is unused in v1 but available for v2.

9. **LUN-to-Target mapping method** -- current join is by naming convention. `SYNO.Core.ISCSI.LUN` may have a `map_target` method for authoritative mapping. Needs investigation.
