# Synology API Map: Storage (Storage Pool, Volume, Disk Objects)

## Endpoints

### SYNO.Storage.CGI.Storage (load_info)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Storage.CGI.Storage&version=1&method=load_info&_sid=<session>`
- **Auth**: Session ID required (admin)

This is the primary storage API. A single call returns the entire storage topology: volumes, storage pools, physical disks, SSD caches, and SMART basics.

#### Response Schema

```json
{
  "success": true,
  "data": {
    "volumes": [
      {
        "id": "volume_1",
        "vol_path": "/volume1",
        "status": "normal",
        "display_name": "Volume 1",
        "description": "",
        "fs_type": "btrfs",
        "pool_path": "/pool/reuse_1",
        "raid_type": "...",
        "size": {
          "total": 28776813199360,
          "used": 6147123789824
        }
      }
    ],
    "storagePools": [
      {
        "id": "reuse_1",
        "status": "normal",
        "raidType": "shr_with_multiple_disktype",
        "device_type": "...",
        "num_id": 1,
        "pool_path": "/pool/reuse_1",
        "disks": ["sata1", "sata2", "sata3", "sata4", "sata5"],
        "size": {
          "total": 28776813199360,
          "used": 6147123789824
        }
      }
    ],
    "disks": [
      {
        "id": "sata1",
        "name": "Drive 1",
        "device": "/dev/sata1",
        "model": "ST10000VN0004-1ZD101",
        "serial": "...",
        "vendor": "Seagate",
        "firm": "SC62",
        "diskType": "SATA",
        "temp": 35,
        "smart_status": "normal",
        "unc": 0,
        "remain_life": -1,
        "size_total": 10000831348736,
        "slot_id": 1,
        "used_by": "reuse_1",
        "wcache_force_off": false
      },
      {
        "id": "nvme0n1",
        "name": "NVMe 1",
        "model": "Samsung SSD 990 PRO 2TB",
        "serial": "...",
        "diskType": "NVMe",
        "temp": 38,
        "smart_status": "normal",
        "unc": 0,
        "remain_life": 81,
        "size_total": 2000398934016
      }
    ],
    "ssdCaches": [],
    "sharedCaches": [
      {
        "id": "shared_cache_1",
        "status": "normal",
        "raidType": "raid_1",
        "disks": ["nvme0n1", "nvme1n1"]
      }
    ]
  }
}
```

---

## Field -> Object Mapping: Storage Pool

**Source**: `data.storagePools[]`
**Identifier**: `id` (e.g., "reuse_1") + `pool_path` (e.g., "/pool/reuse_1")
**Display name**: Pool {num_id} ({device_type})

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `id` | pool_id | IDENTIFIER | STRING | | Primary key |
| `pool_path` | pool_path | IDENTIFIER | STRING | | Secondary key; also join key from Volume |
| `num_id` | num_id | PROPERTY | NUMBER | | Numeric pool index |
| `device_type` | device_type | PROPERTY | STRING | | |
| `status` | status | PROPERTY | STRING | | "normal", "degraded", "crashed" |
| `raidType` | raid_type | PROPERTY | STRING | | "shr_with_multiple_disktype", "raid_1", "raid_5", etc. |
| `disks[]` | (relationship) | | ARRAY[STRING] | | List of disk IDs -- builds Pool->Disk relationship |
| `disks[].length` | disk_count | PROPERTY | NUMBER | | Derived: count of member disks |
| `size.total` | total | METRIC | NUMBER | bytes | Pool total capacity |
| `size.used` | used | METRIC | NUMBER | bytes | Pool used capacity |
| (calculated) | usage_pct | METRIC | NUMBER | % | `size.used / size.total * 100` |

---

## Field -> Object Mapping: Volume

**Source**: `data.volumes[]`
**Identifier**: `id` (e.g., "volume_1") + `vol_path` (e.g., "/volume1")
**Display name**: `display_name`

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `id` | volume_id | IDENTIFIER | STRING | | Primary key |
| `vol_path` | volume_path | IDENTIFIER | STRING | | Mount path; also join key for iSCSI LUN `location` |
| `display_name` | display_name | PROPERTY | STRING | | Human-readable name |
| `description` | description | PROPERTY | STRING | | |
| `status` | status | PROPERTY | STRING | | "normal", "degraded", "crashed" |
| `fs_type` | fs_type | PROPERTY | STRING | | "btrfs", "ext4" |
| `pool_path` | pool_path | PROPERTY | STRING | | **Join key**: links Volume to Storage Pool via `storagePools[].pool_path` |
| `raid_type` | raid_type | PROPERTY | STRING | | RAID type at volume level |
| `size.total` | size_total_byte | METRIC | NUMBER | bytes | |
| `size.used` | size_used_byte | METRIC | NUMBER | bytes | |
| (calculated) | usage_pct | METRIC | NUMBER | % | `size.used / size.total * 100` |
| `size.total - size.used` | size_free_byte | METRIC | NUMBER | bytes | Derived |

### Volume IO (from SYNO.Core.System.Utilization)

Volume-level IO comes from the Utilization endpoint, not from load_info.

**Source**: `data.space.volume[]` in the Utilization response.

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `data.space.volume[].read_iops` | io_read_iops | METRIC | NUMBER | IOPS | SOURCE: NOT CONFIRMED -- exact field names in `space.volume[]` need live verification |
| `data.space.volume[].write_iops` | io_write_iops | METRIC | NUMBER | IOPS | SOURCE: NOT CONFIRMED |

**Note**: The live brief mentions `space.volume[]` in the Utilization response but does not provide the detailed field list. The exact field names for per-volume IO need live API exploration to confirm.

---

## Field -> Object Mapping: Disk

**Source**: `data.disks[]`
**Identifier**: `id` (e.g., "sata1", "nvme0n1")
**Display name**: `name` (e.g., "Drive 1")

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `id` | disk_id | IDENTIFIER | STRING | | Primary key |
| `name` | name | PROPERTY | STRING | | e.g., "Drive 1" |
| `device` | device | PROPERTY | STRING | | e.g., "/dev/sata1" |
| `model` | model | PROPERTY | STRING | | e.g., "ST10000VN0004-1ZD101" |
| `serial` | serial | PROPERTY | STRING | | Drive serial number |
| `vendor` | vendor | PROPERTY | STRING | | e.g., "Seagate" |
| `firm` | firm | PROPERTY | STRING | | Firmware version |
| `diskType` | disk_type | PROPERTY | STRING | | "SATA", "SSD", "NVMe" |
| `temp` | temp | METRIC | NUMBER | C | Current drive temperature |
| `smart_status` | smart_status | PROPERTY | STRING | | "normal", "abnormal" |
| `unc` | unc_sectors | METRIC | NUMBER | count | Uncorrectable sectors (>0 = warning) |
| `remain_life` | remain_life | METRIC | NUMBER | % | SSD/NVMe wear indicator; -1 for HDDs |
| `size_total` | size_total | PROPERTY | NUMBER | bytes | Drive capacity |
| `slot_id` | slot_id | PROPERTY | NUMBER | | Physical slot number |
| `used_by` | used_by | PROPERTY | STRING | | Pool ID that owns this disk -- **join key** for Disk->Pool relationship |
| `wcache_force_off` | wcache_force_off | PROPERTY | BOOLEAN | | |

### Disk IO (from SYNO.Core.System.Utilization)

Per-disk IO comes from the Utilization endpoint.

**Source**: `data.disk[]` in the Utilization response.

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `data.disk[].device` | (join key) | | STRING | | Disk device name -- matches `disks[].id` |
| `data.disk[].read_byte` | io_read | METRIC | NUMBER | bytes/s | SOURCE: NOT CONFIRMED -- exact field names need live verification |
| `data.disk[].write_byte` | io_write | METRIC | NUMBER | bytes/s | SOURCE: NOT CONFIRMED |
| `data.disk[].utilization` | utilization | METRIC | NUMBER | % | SOURCE: NOT CONFIRMED |

**Note**: The live brief confirms per-disk IO exists in the Utilization response but does not provide the exact field names. The community Prometheus exporter mentions per-disk utilization percentages. Exact field names need live API exploration.

---

## Identifier Chains (Relationships)

### Diskstation -> Storage Pool
- `storagePools[]` are direct children of the Diskstation (world object)
- No explicit join field needed; all pools belong to the one NAS

### Storage Pool -> Volume
- **Join key**: `volumes[].pool_path` == `storagePools[].pool_path`
- Example: volume_1 has `pool_path: "/pool/reuse_1"` -> belongs to pool `reuse_1`

### Storage Pool -> Disk
- **Join key**: `storagePools[].disks[]` contains disk IDs matching `disks[].id`
- Example: pool `reuse_1` has `disks: ["sata1", "sata2", "sata3", "sata4", "sata5"]`

### Diskstation -> Disk (dual parent)
- All `disks[]` are also direct children of the Diskstation
- Design artifact specifies dual parent: Diskstation + Storage Pool
- MPB may or may not support dual-parent relationships -- flagged as Key Risk #1

### SSD Cache
- `sharedCaches[]` or `ssdCaches[]` contain cache disk IDs
- Cache disks (NVMe) are in the `disks[]` array with `diskType: "NVMe"`
- Cache is not a separate object in the v1 design -- cache disks are Disk objects

---

## Collection Strategy

- **Requests per cycle (5-min interval)**: 1
  - `SYNO.Storage.CGI.Storage` `load_info` -- full storage topology, capacity, health

- **Note**: Per-disk and per-volume IO metrics come from `SYNO.Core.System.Utilization` `get` (documented in synology-system.md), which is already in the 5-min cycle. No additional request needed for IO.

- **Pagination**: None -- single response contains all storage objects
- **Known quirks**:
  - `remain_life` returns `-1` for HDDs (not applicable); only meaningful for SSD/NVMe
  - `unc` (uncorrectable sectors) is a lifetime counter, not a rate
  - `pool_path` format differs between pools and volumes: pools use `/pool/reuse_1`, volumes reference the same path
  - SSD cache may appear in `ssdCaches[]` or `sharedCaches[]` depending on cache type (dedicated vs. shared)
  - All storage data is returned in one response regardless of how many pools/volumes/disks exist -- no pagination needed
  - The response includes both HDD and NVMe (cache) disks in the same `disks[]` array; differentiate by `diskType`
