# VCF Content Factory Synology DiskStation — Reference

Complete metric, property, and traversal spec reference.
Generated from `describe.xml` and `resources.properties` for build 1.0.0.10.

## Adapter

| Field | Value |
|---|---|
| Adapter Kind | `synology_diskstation` |
| Tier | 2 (Java SDK) |
| Monitoring Interval | 5 minutes |
| License Required | No |

### Credentials

| Field | Key | Type |
|---|---|---|
| Username | `username` | string |
| Password | `password` | string (masked) |

### Connection Settings

| Field | Key | Default | Required |
|---|---|---|---|
| Host / IP Address | `host` | — | Yes |
| Port (HTTPS) | `port` | 5001 | No |
| Allow Insecure SSL | `allowInsecure` | true | No |

---

## Object Types

### Synology World

Global aggregation root. One singleton shared across all adapter instances.

**Identifier**: `world_id` (fixed value `synology_world`)

No metrics or properties. Serves as the top-level hierarchy entry point.

---

### Synology Diskstation

The NAS device. One per adapter instance. Named `<model> <serial>` (e.g., "DS1520+ 20B0RYRXRF3KF").

**Identifier**: `serial`

#### System

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `system_temp` | System Temperature | metric | C | yes |
| `uptime` | Uptime | metric | sec | yes |
| `model` | Model | property | — | — |
| `hostname` | Hostname | property | — | — |
| `firmware_version` | Firmware Version | property | — | — |
| `firmware_date` | Firmware Date | property | — | — |

#### CPU

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `cpu_load_1m` | CPU Load (1 min) | metric | % | yes |
| `cpu_load_5m` | CPU Load (5 min) | metric | % | yes |
| `cpu_load_15m` | CPU Load (15 min) | metric | % | yes |
| `cpu_user_pct` | CPU User % | metric | % | yes |
| `cpu_system_pct` | CPU System % | metric | % | yes |
| `cpu_total_load` | CPU Total Load | metric | % | yes |

#### Memory

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `memory_available` | Memory Available | metric | bytes | yes |
| `memory_total` | Memory Total | metric | bytes | yes |
| `memory_usage_pct` | Memory Usage % | metric | % | yes |
| `memory_cached` | Memory Cached | metric | bytes | no |
| `swap_usage` | Swap Usage | metric | bytes | no |
| `swap_total` | Swap Total | metric | bytes | no |

#### Network

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `net_rx_bytes` | Network RX | metric | bytes/s | yes |
| `net_tx_bytes` | Network TX | metric | bytes/s | yes |
| `nic_count` | NIC Count | metric | — | no |

#### Fan

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `fan_status` | Fan Status | property | — | — |
| `fan_speed_mode` | Fan Speed Mode | property | — | — |

#### NFS Service

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `nfs_enabled` | NFS Enabled | property | — | — |
| `nfs_v4_enabled` | NFS v4 Enabled | property | — | — |
| `nfs_total_ops` | NFS Total OPS | metric | ops/s | yes |
| `nfs_read_ops` | NFS Read OPS | metric | ops/s | yes |
| `nfs_write_ops` | NFS Write OPS | metric | ops/s | yes |
| `nfs_max_latency` | NFS Max Latency | metric | ms | yes |
| `nfs_client_count` | NFS Client Count | metric | — | yes |

---

### Synology Storage Pool

RAID group containing volumes and disks. Named "Storage Pool N" from DSM `num_id`.

**Identifier**: `pool_id` (e.g., `reuse_1`)

#### Capacity

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `total_bytes` | Total | metric | bytes | yes |
| `used_bytes` | Used | metric | bytes | yes |
| `usage_pct` | Usage % | metric | % | yes |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `raid_type` | RAID Type | property | — | — |
| `status` | Status | property | — | — |
| `pool_path` | Pool Path | property | — | — |
| `device_type` | Device Type | property | — | — |
| `disk_count` | Disk Count | property | — | — |

---

### Synology Volume

Filesystem volume. Named "Volume N" from DSM `num_id`. IO metrics joined from Utilization API.

**Identifier**: `volume_id` (e.g., `volume_1`)

#### Capacity

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `total_bytes` | Total | metric | bytes | yes |
| `free_bytes` | Free | metric | bytes | yes |
| `usage_pct` | Usage % | metric | % | yes |

#### IO

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `read_bytes` | Read Throughput | metric | bytes/s | yes |
| `write_bytes` | Write Throughput | metric | bytes/s | yes |
| `read_iops` | Read IOPS | metric | ops/s | yes |
| `write_iops` | Write IOPS | metric | ops/s | yes |
| `utilization_pct` | Utilization | metric | % | yes |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `volume_path` | Volume Path | property | — | — |
| `fs_type` | Filesystem Type | property | — | — |
| `status` | Status | property | — | — |
| `description` | Description | property | — | — |

#### Cache

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `cache_enabled` | Cache Enabled | property | — | — |
| `cache_status` | Cache Status | property | — | — |
| `cache_read_hit_rate` | Cache Read Hit Rate | metric | % | yes |
| `cache_write_hit_rate` | Cache Write Hit Rate | metric | % | yes |

---

### Synology Disk

Physical drive (SATA or NVMe). Named from DSM `name` field (e.g., "Drive 4", "Cache device 1").
IO metrics joined from Utilization API.

**Identifier**: `disk_id` (e.g., `sata1`, `nvme0n1`)

#### Health

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `temperature` | Temperature | metric | C | yes |
| `smart_status` | SMART Status | property | — | — |
| `unc_sectors` | Uncorrectable Sectors | metric | — | yes |
| `remain_life` | Remaining Life | metric | % | yes |

#### IO

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `read_bytes` | Read Throughput | metric | bytes/s | yes |
| `write_bytes` | Write Throughput | metric | bytes/s | yes |
| `read_iops` | Read IOPS | metric | ops/s | yes |
| `write_iops` | Write IOPS | metric | ops/s | yes |
| `utilization_pct` | Utilization | metric | % | yes |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `display_name` | Display Name | property | — | — |
| `model` | Model | property | — | — |
| `firmware` | Firmware | property | — | — |
| `serial` | Serial Number | property | — | — |
| `vendor` | Vendor | property | — | — |
| `disk_type` | Disk Type | property | — | — |
| `disk_code` | Drive Family | property | — | — |
| `is_ssd` | Is SSD | property | — | — |
| `slot_id` | Slot ID | property | — | — |
| `size_bytes` | Size | property | — | — |

---

### Synology iSCSI LUN

iSCSI Logical Unit. Named from DSM LUN name. IO metrics joined from Utilization API.

**Identifier**: `lun_uuid`

#### IO

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `read_iops` | Read IOPS | metric | ops/s | yes |
| `write_iops` | Write IOPS | metric | ops/s | yes |
| `read_throughput` | Read Throughput | metric | bytes/s | yes |
| `write_throughput` | Write Throughput | metric | bytes/s | yes |
| `read_latency` | Read Latency | metric | ms | yes |
| `write_latency` | Write Latency | metric | ms | yes |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `name` | Name | property | — | — |
| `size_bytes` | Size | property | — | — |
| `location` | Location | property | — | — |
| `type` | Type | property | — | — |
| `target_iqn` | Target IQN | property | — | — |

---

### Synology NFS Export

Shared folder with NFS rules. Named by share name (e.g., "vcf-lab-mgmt01-nfs").

**Identifier**: `share_name`

#### Capacity

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `size_used_mib` | Size Used | metric | MiB | yes |
| `size_logical_mib` | Size Logical | metric | MiB | no |
| `quota_usage_pct` | Quota Usage % | metric | % | yes |

#### Clients

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `active_client_count` | Active Client Count | metric | — | yes |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `export_path` | Export Path | property | — | — |
| `volume_path` | Volume Path | property | — | — |
| `description` | Description | property | — | — |
| `quota_value_mib` | Quota Value | property | — | — |
| `cow_enabled` | CoW Enabled | property | — | — |
| `compress_enabled` | Compression Enabled | property | — | — |
| `rule_count` | Rule Count | property | — | — |
| `allowed_clients` | Allowed Clients | property | — | — |

---

### Synology UPS

Uninterruptible power supply (when connected via USB). Only discovered if physically present.

**Identifier**: `ups_model`

#### Battery

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `charge_pct` | Charge | metric | % | yes |
| `runtime_seconds` | Runtime | metric | sec | yes |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `status` | Status | property | — | — |
| `mode` | Mode | property | — | — |
| `connected` | Connected | property | — | — |

---

### Synology SSD Cache

NVMe/SSD cache allocation mounted on a volume.

**Identifier**: `cache_id` (e.g., `alloc_cache_1_1`)

#### Hit Rate

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `read_hit_rate` | Read Hit Rate | metric | % | yes |
| `write_hit_rate` | Write Hit Rate | metric | % | yes |

#### Capacity

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `total_bytes` | Total | metric | bytes | yes |
| `occupied_bytes` | Occupied | metric | bytes | yes |
| `reusable_bytes` | Reusable | metric | bytes | no |
| `memory_used` | Metadata Memory | metric | bytes | no |

#### Properties

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `mode` | Mode | property | — | — |
| `status` | Status | property | — | — |
| `mount_volume` | Mount Volume | property | — | — |
| `disk_failure_count` | Disk Failure Count | property | — | — |

---

## Traversal Spec

**Name**: Synology DiskStation Storage Tree

Hierarchical navigation paths from the adapter instance root:

```
Adapter Instance (synology_diskstation, type=7)
└── Synology World
    └── Synology Diskstation
        ├── Synology Storage Pool
        │   ├── Synology Volume
        │   │   ├── Synology iSCSI LUN
        │   │   ├── Synology NFS Export
        │   │   └── Synology SSD Cache
        │   └── Synology Disk
        └── Synology UPS
```

### Resource Paths

| Path | Description |
|---|---|
| `...SynologyWorld::child\|\|...SynologyDiskstation::child\|\|...SynologyStoragePool::child\|\|...SynologyVolume::child\|\|...SynologyIscsiLun::child` | World → DiskStation → Pool → Volume → iSCSI LUN |
| `...SynologyWorld::child\|\|...SynologyDiskstation::child\|\|...SynologyStoragePool::child\|\|...SynologyVolume::child\|\|...SynologyNfsExport::child` | World → DiskStation → Pool → Volume → NFS Export |
| `...SynologyWorld::child\|\|...SynologyDiskstation::child\|\|...SynologyStoragePool::child\|\|...SynologyVolume::child\|\|...SynologySsdCache::child` | World → DiskStation → Pool → Volume → SSD Cache |
| `...SynologyWorld::child\|\|...SynologyDiskstation::child\|\|...SynologyStoragePool::child\|\|...SynologyDisk::child` | World → DiskStation → Pool → Disk |
| `...SynologyWorld::child\|\|...SynologyDiskstation::child\|\|...SynologyUps::child` | World → DiskStation → UPS |

---

## Cross-Adapter Stitching

iSCSI LUNs and NFS exports are linked to existing **VMWARE Datastore** objects
via the `DataStrorePath` resource identifier.

### iSCSI LUN → Datastore

Transform: Synology LUN UUID → ESXi NAA identifier.

```
UUID:  3ea293f1-e18f-4cb2-929d-b0aff7ea43c2
NAA:   naa.60014053ea293f1de18f4cb292
Match: VMFS:|naa.60014053ea293f1de18f4cb292|
```

Algorithm: `naa.6001405` + UUID parts joined with `d`, truncated to 25 hex characters.

### NFS Export → Datastore

Match: `<nas_ip>/<volume_path_no_slash>/<share_name>` against Datastore `DataStrorePath`.

```
Export:    /volume1/vcf-lab-mgmt01-nfs
NAS IP:   10.0.30.4
Match:    10.0.30.4/volume1/vcf-lab-mgmt01-nfs
```

All connected NAS IPs are tried (from `SYNO.Core.Network.Interface`).

---

## API Endpoints

| # | API | Method | Objects Fed | Cycle |
|---|---|---|---|---|
| 1 | `SYNO.API.Auth` | `login` | (session) | on-demand |
| 2 | `SYNO.DSM.Info` | `getinfo` | Diskstation | 5 min |
| 3 | `SYNO.Core.System` | `info` | Diskstation | 5 min |
| 4 | `SYNO.Core.System.Utilization` | `get` | Diskstation, Disk, Volume, iSCSI LUN | 5 min |
| 5 | `SYNO.Storage.CGI.Storage` | `load_info` | Storage Pool, Volume, Disk, SSD Cache | 5 min |
| 6 | `SYNO.Core.Hardware.FanSpeed` | `get` | Diskstation | 5 min |
| 7 | `SYNO.Core.Network.Interface` | `list` | Diskstation, stitching | 5 min |
| 8 | `SYNO.Core.ISCSI.LUN` | `list` | iSCSI LUN | 5 min |
| 9 | `SYNO.Core.ISCSI.Target` | `list` | iSCSI LUN | 5 min |
| 10 | `SYNO.Core.FileServ.NFS` | `get` | Diskstation | 5 min |
| 11 | `SYNO.Core.Share` | `list` | NFS Export | 5 min |
| 12 | `SYNO.Core.FileServ.NFS.SharePrivilege` | `load` | NFS Export | 5 min (N calls) |
| 13 | `SYNO.Core.CurrentConnection` | `get` | NFS Export, Diskstation | 5 min |
| 14 | `SYNO.Core.ExternalDevice.UPS` | `get` | UPS | 5 min |

Requests per cycle: 13 + N (one `SharePrivilege` call per shared folder with NFS rules).
