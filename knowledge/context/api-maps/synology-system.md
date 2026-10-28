# Synology API Map: System (Diskstation Object)

> **Correction 2026-10-28 (Synology build 35, review B2).**
> - `SYNO.Core.Hardware.FanSpeed` `cool_fan` is **not** fan health. It
>   lists which fan speed modes the model offers (`no`, `single`, `yes`).
>   The claim that `"no"` means a failed fan is **SUPERSEDED 2026-10-28**.
> - Fan failure is visible only through `SYNO.Core.System.SystemHealth`
>   (new section below), as message keys `widget:fan_fail`,
>   `widget:cpu_fan_fail`, `widget:eunit_fan_fail`. DSM returns only its
>   top-ranked problem, so while another problem outranks a failed fan the
>   fan state is not visible.
> - Pool, volume and SMART status vocabularies, failure versus
>   in-progress: section "DSM status vocabularies" below.
> - Live firmware is now **DSM 7.4.1-90080** (DS1520+, read 2026-10-28).
>   The `7.3.2-86009` samples below are from earlier sessions.
>
> Evidence: Synology pak (`content/sdk-adapters/synology`, branch
> `build-35`, commit `2ffd1ed`): `SystemHealth.java`, CHANGELOG 0.0.0.35,
> REFERENCE.md (Fan, Health, Bundled alerts);
> `knowledge/context/reviews/synology-build-35.md` (B2, W1, N1); and a
> read-only probe of the lab NAS on 2026-10-28 (POST login, logout),
> recorded inline below.

## Endpoints

### SYNO.DSM.Info

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.DSM.Info&version=2&method=getinfo&_sid=<session>`
- **Auth**: Session ID required (works with non-admin accounts too)

#### Response Schema

```json
{
  "success": true,
  "data": {
    "model": "DS1520+",
    "ram": 20480,
    "serial": "<serial>",
    "temperature": 42,
    "temperature_warn": false,
    "uptime": 4320000,
    "version": "7.3.2-86009 Update 1",
    "version_string": "DSM 7.3.2-86009 Update 1"
  }
}
```

Live 2026-10-28 (after the NAS upgrade): `"version": "90080"`,
`"version_string": "DSM 7.4.1-90080"`. Note `version` is now the bare build
number, not the dotted string shown above.

#### Field -> Object Mapping

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data.model` | Diskstation | model | PROPERTY | STRING | | e.g., "DS1520+" |
| `data.ram` | Diskstation | ram_size | PROPERTY | NUMBER | MB | Total installed RAM |
| `data.serial` | Diskstation | serial | IDENTIFIER | STRING | | World object key |
| `data.temperature` | Diskstation | sys_temp | METRIC | NUMBER | C | System temperature |
| `data.temperature_warn` | Diskstation | temp_warning | PROPERTY | BOOLEAN | | Temperature warning flag |
| `data.uptime` | Diskstation | uptime | METRIC | NUMBER | seconds | Should be METRIC NUMBER (design notes existing MP has it as PROPERTY STRING -- fix) |
| `data.version_string` | Diskstation | firmware_ver | PROPERTY | STRING | | DSM version string |

---

### SYNO.Core.System (info)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.System&version=3&method=info&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

```json
{
  "success": true,
  "data": {
    "cpu_clock_speed": 2000,
    "cpu_cores": "4",
    "cpu_family": "x86_64",
    "cpu_series": "Celeron",
    "cpu_vendor": "Intel",
    "firmware_date": "2025-...",
    "firmware_ver": "7.3.2-86009",
    "model": "DS1520+",
    "ram_size": 20480,
    "serial": "<serial>",
    "sys_temp": 42,
    "time": "...",
    "timezone": "...",
    "ntp_enabled": true,
    "ntp_server": "...",
    "up_time": "50 days, ..."
  }
}
```

#### Field -> Object Mapping

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data.cpu_clock_speed` | Diskstation | cpu_clock_speed | PROPERTY | NUMBER | MHz | |
| `data.cpu_cores` | Diskstation | cpu_cores | PROPERTY | STRING | | Returns as string |
| `data.cpu_family` | Diskstation | cpu_family | PROPERTY | STRING | | e.g., "x86_64" |
| `data.cpu_series` | Diskstation | cpu_series | PROPERTY | STRING | | e.g., "Celeron" |
| `data.cpu_vendor` | Diskstation | cpu_vendor | PROPERTY | STRING | | e.g., "Intel" |
| `data.firmware_date` | Diskstation | firmware_date | PROPERTY | STRING | | |
| `data.firmware_ver` | Diskstation | firmware_ver | PROPERTY | STRING | | Overlaps with SYNO.DSM.Info |
| `data.model` | Diskstation | model | PROPERTY | STRING | | Overlaps with SYNO.DSM.Info |
| `data.serial` | Diskstation | serial | IDENTIFIER | STRING | | Overlaps with SYNO.DSM.Info |
| `data.sys_temp` | Diskstation | sys_temp | METRIC | NUMBER | C | Overlaps with SYNO.DSM.Info |
| `data.ntp_enabled` | Diskstation | ntp_enabled | PROPERTY | BOOLEAN | | |
| `data.ntp_server` | Diskstation | ntp_server | PROPERTY | STRING | | |
| `data.timezone` | Diskstation | timezone | PROPERTY | STRING | | |
| `data.up_time` | Diskstation | uptime_str | PROPERTY | STRING | | Human-readable uptime; use SYNO.DSM.Info for numeric uptime |

---

### SYNO.Core.System.Utilization (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.System.Utilization&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema (Diskstation-level fields)

```json
{
  "success": true,
  "data": {
    "cpu": {
      "user_load": 5,
      "system_load": 3,
      "other_load": 0,
      "1min_load": 12,
      "5min_load": 8,
      "15min_load": 6
    },
    "memory": {
      "total_real": 20971520,
      "avail_real": 15728640,
      "real_usage": 25,
      "cached": 8388608,
      "buffer": 524288,
      "total_swap": 20971520,
      "avail_swap": 20971520,
      "si_disk": 0,
      "so_disk": 0
    },
    "network": [
      {
        "device": "eth0.131",
        "rx": 123456,
        "tx": 654321
      }
    ],
    "disk": [],
    "space": { "volume": [] },
    "lun": [],
    "nfs": {},
    "smb": {}
  }
}
```

#### Field -> Object Mapping (Diskstation-level)

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data.cpu.user_load` | Diskstation | cpu_user_load | METRIC | NUMBER | % | |
| `data.cpu.system_load` | Diskstation | cpu_system_load | METRIC | NUMBER | % | |
| `data.cpu.other_load` | Diskstation | cpu_other_load | METRIC | NUMBER | % | |
| `data.cpu.1min_load` | Diskstation | cpu_1min_load | METRIC | NUMBER | | Load average |
| `data.cpu.5min_load` | Diskstation | cpu_5min_load | METRIC | NUMBER | | Load average |
| `data.cpu.15min_load` | Diskstation | cpu_15min_load | METRIC | NUMBER | | Load average |
| (calculated) | Diskstation | cpu_total_load | METRIC | NUMBER | % | user_load + system_load |
| `data.memory.total_real` | Diskstation | mem_total_real | METRIC | NUMBER | KB | |
| `data.memory.avail_real` | Diskstation | mem_avail_real | METRIC | NUMBER | KB | |
| `data.memory.real_usage` | Diskstation | memory_usage_pct | METRIC | NUMBER | % | Direct from API |
| `data.memory.cached` | Diskstation | mem_cached | METRIC | NUMBER | KB | |
| `data.memory.buffer` | Diskstation | mem_buffer | METRIC | NUMBER | KB | |
| `data.memory.total_swap` | Diskstation | swap_total | METRIC | NUMBER | KB | |
| `data.memory.avail_swap` | Diskstation | swap_avail | METRIC | NUMBER | KB | |
| `data.memory.si_disk` | Diskstation | swap_si_disk | METRIC | NUMBER | | Swap in from disk |
| `data.memory.so_disk` | Diskstation | swap_so_disk | METRIC | NUMBER | | Swap out to disk |

#### Field -> Object Mapping (Network -- aggregated to Diskstation)

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data.network[].device` | Diskstation | (iterator key) | | STRING | | NIC name, e.g., "eth0.131" |
| `data.network[].rx` | Diskstation | net_rx_bytes | METRIC | NUMBER | bytes/s | Sum across all NICs or per-NIC |
| `data.network[].tx` | Diskstation | net_tx_bytes | METRIC | NUMBER | bytes/s | Sum across all NICs or per-NIC |

**Note**: The design artifact maps net_rx_bytes and net_tx_bytes to the Diskstation object. MPB can either sum across all NICs or report the primary NIC. The `network[]` array has one entry per NIC (4 NICs on this NAS).

---

### SYNO.Core.Hardware.FanSpeed (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.Hardware.FanSpeed&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (works with non-admin too per live testing)

#### Response Schema

**CONFIRMED 2026-04-16 via live API call.**

```json
{
  "success": true,
  "data": {
    "all_disk_temp_fail": "no",
    "cool_fan": "yes",
    "dual_fan_speed": "coolfan",
    "fan_support_adjust_by_ext_nic": "no",
    "fan_type": 11
  }
}
```

#### Field -> Object Mapping

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data.cool_fan` | Diskstation | fan_status | PROPERTY | STRING | | Fan speed modes the model offers: `no`, `single`, `yes` (`yes` on the DS1520+, also on DSM 7.4.1-90080, 2026-10-28). Not fan health. Build 35 display name "Fan Mode Support". ~~"yes" = fan running normally; likely "no" = failed. Maps to fan_status "normal"/"failed" in the design.~~ **SUPERSEDED 2026-10-28.** |
| `data.dual_fan_speed` | Diskstation | fan_speed_mode | PROPERTY | STRING | | Fan speed mode: "coolfan" (cool mode), possibly "fullfan" (full speed), "quietfan" (quiet mode). This is the speed POLICY, not an RPM reading. |
| `data.fan_type` | Diskstation | fan_type | PROPERTY | NUMBER | | Numeric fan type code (11 observed on DS1520+). Meaning not documented. |
| `data.all_disk_temp_fail` | Diskstation | disk_temp_fail | PROPERTY | STRING | | "no" = all disk temps OK; "yes" = thermal warning. String "yes"/"no", not boolean. |
| `data.fan_support_adjust_by_ext_nic` | Diskstation | fan_adjust_ext_nic | PROPERTY | STRING | | "no" on this model. Whether fan speed adjusts based on expansion NIC temperature. |

**Note**: This API does NOT return a numeric RPM value. ~~The response contains fan policy/mode information only: whether the fan is running (`cool_fan`), what speed mode it's in (`dual_fan_speed`), and disk thermal status.~~ **SUPERSEDED 2026-10-28:** the response is fan-mode configuration only: which modes the model offers (`cool_fan`), the selected mode (`dual_fan_speed`), and disk thermal status. Nothing here says whether a fan works. For actual RPM readings, SNMP (`synoDiskFanSpeed` / `synoCPUFanSpeed` OIDs) would be needed.

**What `cool_fan` drives (DSM UI code).** DSM's Fan Speed Mode panel
(`/webman/modules/AdminCenter/admin_center.js`, re-read from the NAS on
DSM 7.4.1-90080, 2026-10-28) uses it to pick radio buttons:
`"no"===t.data.cool_fan` shows the high-fan and low-fan buttons;
`"single"===t.data.cool_fan` shows full and quiet, gated on `fan_type`
bits (`FAN_MODE_ENUM`). (Other branches not read.) A model that answers
`"no"` is healthy; the old reading would raise a permanent false Critical
on it and never fire on a real failure (build 35 review B2).

**No polled API carries per-fan state on a desktop model** (DS1520+,
checked 2026-10-28 by the build 35 work on DSM 7.3.2): not FanSpeed,
`SYNO.Core.System info`, `SYNO.Core.System.Status`,
`SYNO.Storage.CGI.Storage load_info` (no fans in
`env.storageMachineInfo`), nor `SYNO.Storage.CGI.Enclosure` (rack and
expansion enclosures only; error 103 on this model). Use
`SYNO.Core.System.SystemHealth`.

---

### SYNO.Core.System.SystemHealth (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: POST (form body, `_sid` in the body), as the build 35 adapter
  calls every DSM API
- **Params**: `api=SYNO.Core.System.SystemHealth&version=1&method=get&_sid=<session>`
- **API info** (`SYNO.API.Info query`, live 2026-10-28): `minVersion` 1,
  `maxVersion` 1, `path` `entry.cgi`, `requestFormat` `JSON`
- **Auth**: Session ID required (tested with the lab admin account only)

This is what DSM's System Health widget polls
(`webman/modules/SystemInfoApp/SystemHealthWidget.js`, per the build 35
work). The widget renders `rule.description` through the `[widget]` string
table.

#### Response Schema

**CONFIRMED 2026-10-28 via live API call** (DS1520+, DSM 7.4.1-90080;
`interfaces` trimmed to one entry):

```json
{
  "success": true,
  "data": {
    "hostname": "storage",
    "interfaces": [ { "id": "eth0.13", "ip": "172.16.3.51", "type": "lan" } ],
    "rule": {
      "description": {
        "description_format": "{0}",
        "description_params": ["widget:system_ok"],
        "description_use_formatted": false
      },
      "id": "system_health",
      "priority": 40,
      "type": 2
    },
    "uptime": "1064:4:13"
  }
}
```

#### Reading the rule

- `rule.type`: 0 danger, 1 attention, 2 normal (the widget's
  `RuleMappingUtil`, per build 35 `SystemHealth.java`).
- `rule.id`: DSM's rule id. `system_health` seen live; the pak's
  REFERENCE.md also names `ups_status_abnormal` and
  `disk_health_status_error` (from UI code, not seen live).
- Message keys: when `description_use_formatted` is true,
  `description_format` itself is the key; otherwise each entry of
  `description_params` is one. Keys are `section:key`.
- **Fan failure** keys, verified in the NAS's own
  `/webman/texts/enu/strings` `[widget]` table on DSM 7.4.1-90080
  (2026-10-28):
  - `widget:fan_fail`: "The fan of your _DISKSTATION_ has failed. ..."
  - `widget:cpu_fan_fail`: "The CPU fan of your _DISKSTATION_ has failed. ..."
  - `widget:eunit_fan_fail`: "The fan of Synology Expansion Unit has failed. ..."
  - Healthy: `widget:system_ok`, "Your _DISKSTATION_ is working well."
  - `[beep]` also has `fan_fail` / `eunit_fan_fail` (the beep path, not this API).
- **Only the top-ranked problem is returned.** One `rule`, not a list.
  While another problem (UPS on battery, a degraded volume) outranks a fan
  failure, the fan is invisible. A consumer must therefore treat a
  non-normal rule that is not a fan key as "fan state unknown", never as
  "fan normal". The build 35 adapter publishes `Fan|fan_health` =
  `failed` / `normal` (type 2) / `unknown` on exactly that rule.
- **Gap:** never seen with a failed fan (the lab NAS has none). The
  failure shape is the live healthy shape with the string-table keys.

#### Field -> Object Mapping (build 35 adapter)

| Response Field | Object Type | MP Key | Usage | Type | Notes |
|---|---|---|---|---|---|
| `data.rule.type` | Diskstation | Health\|system_health | PROPERTY | STRING | `normal` / `attention` / `danger` |
| `data.rule.id` | Diskstation | Health\|system_health_rule | PROPERTY | STRING | |
| message keys | Diskstation | Health\|system_health_message | PROPERTY | STRING | `widget:system_ok` when healthy |
| derived | Diskstation | Fan\|fan_health | PROPERTY | STRING | `failed` / `normal` / `unknown`; skipped when the rule was not read |

---

### DSM status vocabularies (pool, volume, SMART)

Recorded here because the build 35 alerts depend on them; the endpoint
shapes live in `synology-storage.md`. Source: DSM UI code on the lab NAS
(Storage Manager `storage_panel.js` and the `[volume]` / `[smart]` string
tables), via build 35 REFERENCE.md "Bundled alerts". The earlier design
used "status != normal", which **is superseded 2026-10-28**: it also
matches in-progress states and a blank read (review W1, N1).

- **Pool status, failure:** `degrade`, `crashed`, `deverr`,
  `pool_crashed`, `pool_error`.
- **Volume status, failure:** `degrade`, `crashed`, `deverr`, `ro`,
  `pool_crashed`, `pool_error`.
- **SSD cache status, failure:** `degrade`, `crashed`, `deverr`, `ro`.
- **Not failures** (pool/volume): `normal` and the in-progress states
  `background`, `repair`, `resync`, `raid_sync`, `scrubbing`, `expand`,
  `expand_fs`, `add_disk`, `create`, `creating`, `create_fs`, `delete`,
  `deleting`, `deactivating`, `defrag`, `optimize`, `paritycount`,
  `running_fsck`, `running_btrfs_balance`, `upgrade`, `replace`,
  `waiting`, `activating`, `initializing`.
- **Disk `smart_status`:** `normal` healthy; `failing`, `degraded`,
  `access_err` failure (Storage Manager: "Replace the drive
  immediately"); `unknown` means DSM cannot read the drive's SMART
  (Storage Manager disables Health Info for it, like a disconnected
  drive), neither healthy nor failed.
- DSM can omit or blank these fields; publish nothing rather than `""`.

Verified on DSM 7.4.1-90080 (2026-10-28, NAS string table):
`[volume]` `volume_status_degrade` "Degraded", `volume_status_crashed`
"Crashed", `volume_status_deverr` "Unknown Error", `volume_status_ro`
"Read Only", `volume_status_normal` "Healthy". The pool-only states and
the SMART values come from `storage_panel.js` on DSM 7.3.2 and were not
re-read on 7.4.1. Only `normal` has been seen live for each.


---

### SYNO.Core.System.Status (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.System.Status&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

```json
{
  "success": true,
  "data": {
    "is_system_crashed": false,
    "upgrade_ready": false
  }
}
```

#### Field -> Object Mapping

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data.is_system_crashed` | Diskstation | is_system_crashed | PROPERTY | BOOLEAN | | Overall system health flag |
| `data.upgrade_ready` | Diskstation | upgrade_ready | PROPERTY | BOOLEAN | | DSM update available |

---

### SYNO.Core.Network.Interface (list)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.Network.Interface&version=1&method=list&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

```json
{
  "success": true,
  "data": [
    {
      "ifname": "eth0.131",
      "ip": "172.16.3.51",
      "mask": "255.255.255.0",
      "speed": 1000,
      "status": "connected"
    }
  ]
}
```

#### Field -> Object Mapping

| Response Field | Object Type | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|---|
| `data[].ifname` | Diskstation | (nic enumeration) | PROPERTY | STRING | | |
| `data[].speed` | Diskstation | (nic detail) | PROPERTY | NUMBER | Mbps | |
| `data[].status` | Diskstation | (nic detail) | PROPERTY | STRING | | "connected" or other |
| (count of entries) | Diskstation | nic_count | PROPERTY | NUMBER | | Derived: array length |

**Note**: The design artifact does not make NICs separate objects. NIC details are properties/context for the Diskstation object. The count and aggregate throughput (from Utilization) are the Diskstation-level metrics.

---

## Collection Strategy

- **Requests per cycle (5-min interval)**: 2
  - `SYNO.Core.System.Utilization` `get` -- CPU, memory, network, plus disk/LUN IO (shared with storage/iSCSI maps)
  - `SYNO.DSM.Info` `getinfo` -- model, serial, temp, uptime, version

- **Requests per cycle (15-min interval)**: 4
  - `SYNO.Core.System` `info` -- CPU details, firmware, timezone, NTP
  - `SYNO.Core.Hardware.FanSpeed` `get` -- fan mode support and speed mode (~~fan status~~, superseded 2026-10-28)
  - `SYNO.Core.System.SystemHealth` `get` -- DSM's top health verdict; the only fan-failure signal (build 35, optional read)
  - `SYNO.Core.Network.Interface` `list` -- NIC inventory

- **Requests per cycle (30-min interval)**: 1
  - `SYNO.Core.System.Status` `get` -- crash flag, upgrade flag

- **Pagination**: None for these endpoints
- **Known quirks**:
  - `SYNO.DSM.Info` and `SYNO.Core.System` overlap on model, serial, temp, version. Use SYNO.DSM.Info for the 5-min collection (lighter weight, works without admin) and SYNO.Core.System for the 15-min property refresh.
  - `cpu_cores` returns as string, not integer.
  - `up_time` from SYNO.Core.System is human-readable string; use `uptime` from SYNO.DSM.Info for numeric seconds.
  - `memory.real_usage` is pre-calculated percentage -- no need for MPB to calculate.
  - Network array has one entry per NIC; aggregation to Diskstation-level is an MPB design choice.
