# Synology API Map: iSCSI (iSCSI LUN Object)

## Endpoints

### SYNO.Core.ISCSI.LUN (list)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.ISCSI.LUN&version=1&method=list&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

```json
{
  "success": true,
  "data": {
    "luns": [
      {
        "name": "vcf-lab-wld01-cl01",
        "uuid": "d023e190-...",
        "size": 8796093022208,
        "location": "/volume1",
        "type_str": "BLUN",
        "dev_attribs": { ... }
      },
      {
        "name": "vcf-lab-mgmt01-cl01-lun0",
        "uuid": "...",
        "size": 8804682956800,
        "location": "/volume1",
        "type_str": "BLUN"
      },
      {
        "name": "vcf-lab-wld02-cl01",
        "uuid": "...",
        "size": 8796093022208,
        "location": "/volume1",
        "type_str": "BLUN"
      }
    ]
  }
}
```

#### Field -> Object Mapping

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `name` | name | PROPERTY / IDENTIFIER | STRING | | LUN name; also display name |
| `uuid` | lun_uuid | IDENTIFIER | STRING | | Primary key for iSCSI LUN object |
| `size` | size | METRIC | NUMBER | bytes | LUN provisioned size |
| `location` | location | PROPERTY | STRING | | Volume mount path -- **join key** to Volume object |
| `type_str` | type_str | PROPERTY | STRING | | "BLUN" (block-level LUN), "THIN", etc. |

---

### SYNO.Core.ISCSI.Target (list)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.ISCSI.Target&version=1&method=list&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

```json
{
  "success": true,
  "data": {
    "targets": [
      {
        "name": "vcf-lab-wld01-cl01",
        "iqn": "iqn.2000-01.com.synology:storage.vcf-lab-wld01-cl01.cfb45402d27",
        "is_enabled": true,
        "network_portals": ["172.16.3.51:3260", "172.16.3.52:3260"]
      }
    ]
  }
}
```

#### Field -> Object Mapping

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `name` | target_name | PROPERTY | STRING | | Target name; **join key** to LUN by naming convention |
| `iqn` | iqn | PROPERTY | STRING | | iSCSI Qualified Name -- ESXi stores this in its iSCSI adapter config |
| `is_enabled` | is_enabled | PROPERTY | BOOLEAN | | |
| `network_portals` | network_portals | PROPERTY | STRING | | Comma-separated list of portal IPs |

---

### iSCSI LUN IO (from SYNO.Core.System.Utilization)

Per-LUN IO metrics come from the Utilization endpoint (documented in synology-system.md).

**Source**: `data.lun[]` in the `SYNO.Core.System.Utilization` `get` response.

```json
{
  "lun_name": "vcf-lab-wld01-cl01",
  "uuid": "d023e190-...",
  "read_iops": 0,
  "write_iops": 164,
  "read_throughput": 0,
  "write_throughput": 867388,
  "read_avg_latency": 0,
  "write_avg_latency": 71,
  "total_iops": 164,
  "total_throughput": 867388,
  "total_io_latency": 66
}
```

#### Field -> Object Mapping (IO Metrics)

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `lun_name` | (join key) | | STRING | | Matches `SYNO.Core.ISCSI.LUN` `name` |
| `uuid` | (join key) | | STRING | | Matches `SYNO.Core.ISCSI.LUN` `uuid` |
| `read_iops` | read_iops | METRIC | NUMBER | IOPS | |
| `write_iops` | write_iops | METRIC | NUMBER | IOPS | |
| `total_iops` | total_iops | METRIC | NUMBER | IOPS | Derived: read + write |
| `read_throughput` | read_throughput | METRIC | NUMBER | bytes/s | |
| `write_throughput` | write_throughput | METRIC | NUMBER | bytes/s | |
| `total_throughput` | total_throughput | METRIC | NUMBER | bytes/s | Derived: read + write |
| `read_avg_latency` | read_latency | METRIC | NUMBER | ms | |
| `write_avg_latency` | write_latency | METRIC | NUMBER | ms | |
| `total_io_latency` | total_io_latency | METRIC | NUMBER | ms | Combined average |

---

## Identifier Chains (Relationships)

### Volume -> iSCSI LUN
- **Join key**: `SYNO.Core.ISCSI.LUN` `location` (e.g., "/volume1") matches `volumes[].vol_path` from `SYNO.Storage.CGI.Storage`
- All three LUNs on this NAS have `location: "/volume1"` -> they are children of volume_1

### iSCSI LUN -> Target
- **Join key**: Target `name` matches LUN `name` (by naming convention on this NAS)
- The actual LUN-to-target mapping may also be available via `SYNO.Core.ISCSI.LUN` `map_target` method (referenced in the brief but not live-tested)
- The IQN embeds the LUN name in the format: `iqn.2000-01.com.synology:<hostname>.<lun_name>.<suffix>`

### iSCSI LUN IO -> iSCSI LUN metadata
- **Join keys**: `lun_name` in the Utilization `lun[]` array matches `name` in the ISCSI.LUN response; `uuid` also matches
- Both keys are present in both responses, providing redundant join capability

## Cross-Request Dependencies

The iSCSI LUN object requires data from three sources:

1. **`SYNO.Core.ISCSI.LUN` `list`** -- LUN metadata (name, uuid, size, location, type)
2. **`SYNO.Core.System.Utilization` `get`** -- Per-LUN IO metrics (`data.lun[]`)
3. **`SYNO.Core.ISCSI.Target` `list`** -- Target IQN (for ESXi correlation)

MPB must merge these three responses by matching on `name` and/or `uuid`.

---

## Collection Strategy

- **Requests per cycle (5-min interval)**: 0 additional
  - LUN IO comes from `SYNO.Core.System.Utilization` `get` (already in 5-min cycle)

- **Requests per cycle (15-min interval)**: 2
  - `SYNO.Core.ISCSI.LUN` `list` -- LUN metadata refresh
  - `SYNO.Core.ISCSI.Target` `list` -- target IQN refresh

- **Pagination**: None -- all LUNs/targets returned in single response
- **Known quirks**:
  - Not all LUNs may have a matching target (the brief shows one LUN without a target)
  - Not all targets may have a mapped LUN (one target exists with no LUN)
  - `location` is the volume mount path, not the pool path -- join to Volume, not Pool
  - LUN `size` is provisioned size (thin provisioning), not actual used space
  - Per-LUN IO is current-state (instantaneous), not averaged
  - The `lun[]` array in Utilization only appears when iSCSI LUNs exist and have IO activity -- may be empty or absent if no LUNs are configured
