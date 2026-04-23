# Synology API Map: Storage (Storage Pool, Volume, Disk Objects)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `$SYNO_HOST:$SYNO_PORT` — DS1520+ running DSM
  7.3.2-86009 Update 1 (credentials from repo `.env`)
- **Last updated:** 2026-04-21
- **Update history:**
  - 2026-04-21 — KISS-unblock refresh. Captured full verbatim
    `volumes[0]` from `SYNO.Storage.CGI.Storage load_info`.
    Documented several 2026-04-16 field errors superseded by
    today's observations (volume `pool_path` is bare
    `reuse_1`, not `/pool/reuse_1`; `size.{total,used}` are
    strings). Added Provenance block. Nailed down per-volume
    and per-disk filter semantics on
    `SYNO.Core.System.Utilization` (including `resource` +
    `interfaces` form-POST format, current-vs-history
    differential, and the `location=` legacy param being a
    silent no-op). Added new section **Utilization endpoint
    filter contract**.
  - 2026-04-16 — Initial mapping (backfilled from git mtime).
    Captured load_info + utilization per-disk/per-volume IO;
    drafted object model + identifier chains.
- **Evidence basis:** live API calls this session (auth, load_info,
  several filter permutations against `Utilization get`); prior
  map content inherited from 2026-04-16 session.
- **Notes:** Any bare claim without an inline tag is either
  trivially obvious (e.g., "GET against this path") or inherited
  from 2026-04-16 without re-verification — treat as
  `[unchanged since 2026-04-16]` unless another tag appears.

## Endpoints

### SYNO.Storage.CGI.Storage (load_info)

- **Path**: `/webapi/entry.cgi` `[re-verified 2026-04-21]`
- **Method**: GET
- **Params**: `api=SYNO.Storage.CGI.Storage&version=1&method=load_info&_sid=<session>`
- **Auth**: Session ID required (admin)

This is the primary storage API. A single call returns the entire
storage topology: volumes, storage pools, physical disks, SSD
caches, and SMART basics.

#### Top-level response keys `[observed 2026-04-21]`

```
data: {
  detected_pools, disks, env, missing_pools, overview_data,
  ports, sharedCaches, ssdCaches, storagePools, volumes
}
```

The full response is ~30 KB. The abridged schema in the
2026-04-16 map captured the useful fields but omitted many
siblings. Full `volumes[0]` is now captured below verbatim as
the canonical reference for KISS decisions.

#### Response Schema — `volumes[]` (full verbatim entry) `[observed 2026-04-21]`

```json
{
  "atime_checked": true,
  "atime_opt": "relatime",
  "cache": {
    "id": "alloc_cache_1_1",
    "status": "normal"
  },
  "cacheStatus": "",
  "cache_advisor_running": false,
  "cache_disks": [],
  "can_assemble": false,
  "can_do": {
    "delete": true,
    "raid_cross": true
  },
  "container": "internal",
  "dedup_info": {
    "btn_alert": "",
    "last_run_time": 0,
    "show": false,
    "show_config_btn": false,
    "status": "disable",
    "total": 0,
    "used": 0
  },
  "device_type": "raid_6",
  "disk_failure_number": 0,
  "disks": [],
  "drive_type": 0,
  "fs_type": "btrfs",
  "id": "volume_1",
  "is_acting": false,
  "is_actioning": false,
  "is_backgroundbuilding": false,
  "is_encrypted": false,
  "is_inode_full": false,
  "is_locked": false,
  "is_scheduled": false,
  "is_vault_contain_key": false,
  "is_writable": true,
  "last_done_time": 0,
  "limited_disk_number": 24,
  "max_fs_size": "1152921504606846976",
  "metadata_cache_hard_lower_bound_byte": 228222566400,
  "metadata_cache_option_show": true,
  "missing_drives": [],
  "next_schedule_time": 0,
  "notes": [],
  "num_id": 1,
  "pool_path": "reuse_1",
  "progress": {
    "cur_step": 0,
    "is_resync_speed_limited": false,
    "percent": "-1",
    "remaining_time": 0,
    "step": "none",
    "total_step": 0
  },
  "raidType": "multiple",
  "repair_action": "none",
  "scrubbingStatus": "",
  "show_assemble_btn": false,
  "size": {
    "free_inode": "0",
    "total": "28788160495616",
    "total_device": "29987667181568",
    "total_inode": "0",
    "used": "7632707117056"
  },
  "space_status": {
    "detail": "pool_normal",
    "show_attention": false,
    "show_danger": false,
    "show_flag_detail": "",
    "status": "fs_normal",
    "summary_status": "normal"
  },
  "ssd_trim": {
    "support": "not support"
  },
  "status": "normal",
  "suggestions": [],
  "summary_status": "normal",
  "timebackup": false,
  "used_by_gluster": false,
  "uuid": "jyWfYY-Mnoy-rjML-Y3cD-CrIS-tFeJ-UCL6N6",
  "vol_attribute": "generic",
  "vol_desc": "",
  "vol_path": "/volume1",
  "vspace_can_do": { "...": "omitted-vol-capabilities-tree" }
}
```

**Superseded fields (old map was wrong):** `[superseded 2026-04-21 — see below]`

| Field | 2026-04-16 documented | 2026-04-21 observed |
|---|---|---|
| `volumes[].pool_path` | `/pool/reuse_1` | `reuse_1` (bare, **no `/pool/` prefix**) |
| `volumes[].size.total` | number `28776813199360` | **string** `"28788160495616"` |
| `volumes[].size.used` | number | **string** |
| `volumes[].raid_type` | `raid_type` | field name is `raidType` (camelCase), value was `multiple` here |

**New fields worth noting:** `[observed 2026-04-21]`

- `volumes[].uuid` — DSM-internal stable UUID (format:
  `XXXXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXXXX`). Candidate for a
  stable identifier alternative to the more human `id`.
- `volumes[].cache.id` — links a volume to its SSD/NVMe cache
  (`alloc_cache_1_1` matches `ssdCaches[0].id`). Clean join
  key for a future Volume -> Cache relationship.
- `volumes[].size.total_device` — full provisioned size before
  RAID overhead.
- `volumes[].fs_type`, `is_encrypted`, `is_locked` — property
  candidates for alert logic.

#### Response Schema — `storagePools[]` (structural) `[observed 2026-04-21]`

Full key set on this NAS's single pool:

```
cacheStatus, cache_disks, can_assemble, can_do, compatibility,
container, data_scrubbing, desc, device_type, disk_failure_number,
disks, drive_type, has_full_child_vol, id, is_actioning,
is_backgroundbuilding, is_hcl_migrated, is_scheduled, is_writable,
last_done_time, limited_disk_number, maximal_disk_size,
minimal_disk_size, minimal_spare_size, missing_drives,
next_schedule_time, notes, num_id, pool_child, pool_path,
progress, raidType, raids, repair_action, scrubbingStatus,
show_assemble_btn, size, space_path, space_status, spares,
status, suggestions, summary_status, timebackup, uuid,
vspace_can_do
```

Identifier-relevant subset:

```json
{
  "id": "reuse_1",
  "num_id": 1,
  "pool_path": "reuse_1",
  "space_path": "/dev/vg1",
  "device_type": "raid_6",
  "raidType": "multiple",
  "status": "normal",
  "summary_status": "normal",
  "disks": ["sata1","sata2","sata3","sata4","sata5"],
  "uuid": "dpnkmM-poXs-iBeU-MDOv-Smu2-Fot0-Pg7bsw",
  "size": { "total": "29987679764480", "used": "29987679764480" }
}
```

**Supersedes 2026-04-16:** `[superseded 2026-04-21 — see below]`

- `storagePools[].pool_path` was documented as `/pool/reuse_1`
  but **actual value is bare `reuse_1`**, matching
  `volumes[].pool_path` verbatim. This means the 2026-04-16
  "Pool -> Volume join via pool_path" assertion actually works —
  the old map had both sides wrong in the same direction, so
  the join logic accidentally survived. Documenting correctly
  now.
- `storagePools[].size.{total,used}` are **strings**, not
  numbers.
- Pool has a `uuid` field (not previously surfaced).

#### Response Schema — `disks[]` (first entry, verbatim) `[observed 2026-04-21]`

```json
{
  "action": { "alert": true, "allow_binding": true, "allow_ma_create": true, "notification": false, "selectable": true, "show_lifetime_chart": true },
  "action_status": { "action_name": "idle", "action_progress": "" },
  "action_status_category": "processing",
  "action_status_key": "idle",
  "adv_progress": "",
  "adv_status": "normal",
  "allocation_role": "reuse_1",
  "below_remain_life_mail_notify_thr": false,
  "below_remain_life_show_thr": false,
  "below_remain_life_thr": false,
  "compatibility": "not_in_support",
  "container": { "order": 0, "str": "DS1520+", "supportPwrBtnDisable": false, "type": "internal" },
  "container_id": 0,
  "device": "/dev/sata1",
  "disable_secera": false,
  "diskType": "SATA",
  "disk_code": "ironwolf",
  "disk_location": "Main",
  "drive_status_category": "health",
  "drive_status_key": "normal",
  "erase_time": 862,
  "firm": "SC60",
  "firmware_status": "-",
  "has_system": true,
  "hide_info": [],
  "i18nNamingInfo": "[\"dsm:volume:volume_disk\",\" \",\"4\"]",
  "id": "sata1",
  "ihm_testing": false,
  "is4Kn": false,
  "isSsd": false,
  "isSynoDrive": false,
  "isSynoPartition": true,
  "is_bundle_ssd": false,
  "is_erasing": false,
  "longName": "Drive 4",
  "m2_pool_support": false,
  "model": "ST10000VN0004-1ZD101",
  "name": "Drive 4",
  "num_id": 4,
  "order": 4,
  "overview_status": "normal",
  "pciSlot": -1,
  "perf_testing": false,
  "portType": "normal",
  "remain_life": { "trustable": true, "value": -1 },
  "remain_life_danger": false,
  "remote_info": { "compatibility": "disabled", "unc": 0 },
  "sb_days_left": 0,
  "sb_days_left_below_show_thres": false,
  "sb_days_left_critical": false,
  "sb_days_left_warning": false,
  "serial": "ZA250QA8",
  "size_total": "10000831348736",
  "slot_id": 4,
  "smart_progress": "",
  "smart_status": "normal",
  "smart_test_limit": 0,
  "smart_test_support": true,
  "smart_testing": false,
  "ssd_unhealth_reason": "none",
  "status": "normal",
  "summary_status_category": "health",
  "summary_status_key": "normal",
  "temp": 35,
  "testing_progress": "",
  "testing_type": "idle",
  "tray_status": "join",
  "ui_serial": "ZA250QA8",
  "unc": 0,
  "used_by": "reuse_1",
  "vendor": "Seagate",
  "wcache_force_off": true,
  "wcache_force_on": false,
  "wdda_support": false
}
```

**Supersedes 2026-04-16:** `[superseded 2026-04-21 — see below]`

- `disks[].remain_life` is an **object** `{trustable: bool,
  value: number}`, not a scalar number. The HDD sentinel is
  `value: -1`.
- `disks[].size_total` is a **string**.
- Disk order in the response is not sorted by id — `sata1` has
  `name: "Drive 4"` and `num_id: 4`. Don't assume
  `id` ordinality matches `name`/`num_id`.

All 7 disks on this NAS (ID | name | type | used_by):
```
sata1   | Drive 4          | SATA     | reuse_1
sata2   | Drive 5          | SATA     | reuse_1
sata3   | Drive 1          | SATA     | reuse_1
sata4   | Drive 2          | SATA     | reuse_1
sata5   | Drive 3          | SATA     | reuse_1
nvme0n1 | Cache device 2   | M.2 NVMe | shared_cache_1
nvme1n1 | Cache device 1   | M.2 NVMe | shared_cache_1
```

Note: NVMe disks have `used_by="shared_cache_1"`, NOT a pool id.
Downstream MP authoring must handle the shared-cache used_by case
or those two disks lose their parent relationship.
`[observed 2026-04-21]`

#### Response Schema — `sharedCaches[]` + `ssdCaches[]`

- `sharedCaches[0]` exists on this NAS: `id: "shared_cache_1"`,
  `device_type: "raid_1"`, `disks: ["nvme0n1","nvme1n1"]`,
  `size.total` = ~2 TB (string). `[observed 2026-04-21]`
- `ssdCaches[0]` is the **allocated cache** for volume 1:
  `id: "alloc_cache_1_1"`, `mountSpaceId: "volume_1"`,
  `path: "/volume1"`, `mode: "write"`, plus a **`hit_rates` object**
  with per-interval hit counts (`Minutely`, `Current`, `Daily`,
  `Weekly`, `Monthly`, `HalfYearly`, `Yearly`). Each interval
  entry has `io_hit`, `io_need_acceleration`, `data_size`. These
  could feed a future SSD-Cache metric set without needing a
  separate endpoint. `[observed 2026-04-21]`

---

## Utilization endpoint filter contract `[observed 2026-04-21]`

This is net-new this session. Full details of parameter behavior
on `SYNO.Core.System.Utilization version=1 method=get`.

### Three filter mechanisms tested

| Mechanism | Behavior on **current values** | Behavior on **history** (`type=history`) |
|---|---|---|
| No filter | Returns all resources (`cpu, disk, lun, memory, network, nfs, smb, space, time`). | n/a — history requires `resource` selector. |
| `location=<id>` (legacy) | **Silently ignored.** Same payload as no-filter. Tried `volume_1`, `sata1`, and `bogusdiskid` — all produced identical full payloads. | Not tested for history mode; no reason to prefer it over `resource`/`interfaces`. |
| `resource=["space"]` + `interfaces={"space":["<device>"]}` (form POST) | Trims top-level keys to the selected resource(s); the `interfaces` inner list filters the array entries within that resource. **Works for `space` (volumes).** Does NOT filter for `disk` on current-values — all 7 disks come back even when `interfaces.disk=["sata1"]`. | Works for both `space` and `disk`; returns 10,081-point time-series arrays (`read_access`, `read_byte`, `write_access`, `write_byte`, `utilization`) plus `interval: 60`, `data_size: 10081`, and a unix epoch `time` end-of-series marker. |

### Filter value — what identifier does it expect?

**Critical finding for KISS decision.** The `interfaces.space[]`
value is **NOT** the volume `id` from `load_info.volumes[].id`. It
is the kernel device-mapper name (e.g., `dm-4`) that appears as
`space.volume[].device` in the Utilization response. Attempted
values:

| Value tried | Result |
|---|---|
| `volume_1` (load_info id) | `[{device: "volume_1", success: false}]` — accepted, empty. |
| `volume1` (display_name) | `[{device: "volume1", success: false}]` — same. |
| `/volume1` (vol_path) | `[{device: "/volume1", success: false}]` — same. |
| `dm-4` (Utilization `device` field) | **Success** — full history arrays returned. |

**Implication for a KISS (auto-join) Volume object model:** the
two metricSets we'd want on a Volume (capacity from `load_info`,
IO from `Utilization`) identify volumes by **different keys**.
They can be joined, but the join is **Utilization.display_name
(e.g., "volume1")** ↔ **load_info.vol_path (e.g., "/volume1")
with the leading `/` stripped**, NOT by verbatim id.

If the MP framework auto-joins metricSets on identical identifier
values, it will NOT auto-join these two — a derivation step is
required.

### Resource-selector trims top-level keys

Adding `resource=["space"]` removes `cpu, disk, lun, memory,
network, nfs, smb` from the response. `resource=["space","disk"]`
keeps both. Noticeable response-size win for high-frequency
collection. Mixing with `type=history` shapes the payload as
time-series arrays per interface.

### Form-POST vs. GET query string

Both `-X POST --data-urlencode` and `?key=<url-encoded-json>` GET
forms accepted; the sibling-repo curl capture that used POST form
is not strictly required, but POST sidesteps URL-length concerns
when filtering many interfaces at once. Confirming Scott's
captured curl session's shape works as expected.

---

## Field -> Object Mapping: Storage Pool

**Source**: `data.storagePools[]` `[re-verified 2026-04-21]`
**Identifier**: `id` (e.g., "reuse_1"); `pool_path` happens to
equal `id` on this NAS. `uuid` also available for a stable key.
`[observed 2026-04-21]`
**Display name**: Pool {num_id} ({device_type})

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `id` | pool_id | IDENTIFIER | STRING | | Primary key `[re-verified 2026-04-21]` |
| `pool_path` | pool_path | IDENTIFIER | STRING | | `[superseded 2026-04-21]` Bare `reuse_1`, not `/pool/reuse_1`; matches `volumes[].pool_path` verbatim |
| `uuid` | pool_uuid | IDENTIFIER | STRING | | `[observed 2026-04-21]` DSM-internal UUID, new |
| `num_id` | num_id | PROPERTY | NUMBER | | Numeric pool index |
| `device_type` | device_type | PROPERTY | STRING | | e.g., `raid_6` `[observed 2026-04-21]` |
| `status` | status | PROPERTY | STRING | | "normal", "degraded", "crashed" |
| `summary_status` | summary_status | PROPERTY | STRING | | `[observed 2026-04-21]` |
| `raidType` | raid_type | PROPERTY | STRING | | On this NAS returned `multiple` (SHR layout) `[observed 2026-04-21]` |
| `disks[]` | (relationship) | | ARRAY[STRING] | | List of disk IDs -- builds Pool->Disk relationship |
| `disks[].length` | disk_count | PROPERTY | NUMBER | | Derived: count of member disks |
| `size.total` | total | METRIC | NUMBER | bytes | `[superseded 2026-04-21]` Returned as **string**; MP must cast |
| `size.used` | used | METRIC | NUMBER | bytes | `[superseded 2026-04-21]` Returned as **string** |
| (calculated) | usage_pct | METRIC | NUMBER | % | `size.used / size.total * 100` |

---

## Field -> Object Mapping: Volume

**Source**: `data.volumes[]` `[re-verified 2026-04-21]`
**Identifier**: `id` (e.g., "volume_1"). Alternative stable key:
`uuid`. `vol_path` available for iSCSI join.
**Display name**: no `display_name` field in `volumes[]` this
session (`vol_desc` was empty). The 2026-04-16 schema showed a
`display_name`, but the 2026-04-21 verbatim capture does NOT
contain that field on this NAS. MPs should compute a display
name from `vol_path` or `num_id` rather than depending on
`display_name`. `[superseded 2026-04-21 — see below]`

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `id` | volume_id | IDENTIFIER | STRING | | Primary key (e.g., `volume_1`) `[re-verified 2026-04-21]` |
| `vol_path` | volume_path | IDENTIFIER | STRING | | Mount path (e.g., `/volume1`) `[re-verified 2026-04-21]` |
| `uuid` | volume_uuid | IDENTIFIER | STRING | | `[observed 2026-04-21]` DSM-internal UUID, new |
| `num_id` | num_id | PROPERTY | NUMBER | | 1 here |
| `vol_desc` | description | PROPERTY | STRING | | Empty on this NAS |
| `status` | status | PROPERTY | STRING | | "normal" |
| `summary_status` | summary_status | PROPERTY | STRING | | `[observed 2026-04-21]` |
| `fs_type` | fs_type | PROPERTY | STRING | | "btrfs" here |
| `pool_path` | pool_path | PROPERTY | STRING | | `[superseded 2026-04-21]` Bare `reuse_1`; **join key** to `storagePools[].pool_path` |
| `raidType` | raid_type | PROPERTY | STRING | | `[superseded 2026-04-21]` Field is `raidType` (camelCase), value `multiple` |
| `device_type` | device_type | PROPERTY | STRING | | `raid_6` `[observed 2026-04-21]` |
| `is_encrypted` | is_encrypted | PROPERTY | BOOLEAN | | `[observed 2026-04-21]` |
| `is_locked` | is_locked | PROPERTY | BOOLEAN | | `[observed 2026-04-21]` |
| `cache.id` | cache_id | PROPERTY | STRING | | `[observed 2026-04-21]` Join to `ssdCaches[].id` |
| `cache.status` | cache_status | PROPERTY | STRING | | `[observed 2026-04-21]` |
| `size.total` | size_total_byte | METRIC | NUMBER | bytes | `[superseded 2026-04-21]` Returned as **string** |
| `size.used` | size_used_byte | METRIC | NUMBER | bytes | `[superseded 2026-04-21]` Returned as **string** |
| `size.total_device` | size_total_device_byte | METRIC | NUMBER | bytes | `[observed 2026-04-21]` Pre-RAID overhead size, string |
| (calculated) | usage_pct | METRIC | NUMBER | % | `size.used / size.total * 100` |
| (calculated) | size_free_byte | METRIC | NUMBER | bytes | Derived: `size.total - size.used` |

### Volume IO (from SYNO.Core.System.Utilization) `[re-verified 2026-04-21]`

**Source**: `data.space.volume[]` in the Utilization response.

Sample entry (unfiltered call, 2026-04-21):
```json
{
  "device": "dm-4",
  "display_name": "volume1",
  "read_access": 2,
  "read_byte": 47211,
  "utilization": 1,
  "write_access": 97,
  "write_byte": 4360084
}
```

Aggregate entry at `data.space.total`:
```json
{
  "device": "total",
  "read_access": 0,
  "read_byte": 186,
  "utilization": 0,
  "write_access": 61,
  "write_byte": 2821026
}
```

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `device` | (filter key for history) | | STRING | | Kernel device-mapper name (`dm-4`). **This is the value you pass in `interfaces.space[]` for history queries.** `[observed 2026-04-21]` |
| `display_name` | (join key) | | STRING | | Matches `volumes[].vol_path` with leading `/` stripped (e.g., `volume1` ↔ `/volume1`) `[re-verified 2026-04-21]` |
| `read_byte` | io_read_bytes | METRIC | NUMBER | bytes/s | `[re-verified 2026-04-21]` |
| `write_byte` | io_write_bytes | METRIC | NUMBER | bytes/s | `[re-verified 2026-04-21]` |
| `read_access` | io_read_access | METRIC | NUMBER | IOPS | `[re-verified 2026-04-21]` |
| `write_access` | io_write_access | METRIC | NUMBER | IOPS | `[re-verified 2026-04-21]` |
| `utilization` | utilization | METRIC | NUMBER | % | `[re-verified 2026-04-21]` |

**KISS implication:** the IO metricSet is keyed by `dm-4`
(kernel) or `volume1` (display_name). Neither matches the
capacity metricSet's identifier `volume_1` verbatim. Any
auto-join MP runtime that binds metricSets by exact identifier
match WILL NOT join these two automatically — the adapter must
derive a canonical key (e.g., strip underscores + leading `/`,
or pin to `display_name` on the capacity side).
`[observed 2026-04-21]`

---

## Field -> Object Mapping: Disk

**Source**: `data.disks[]` `[re-verified 2026-04-21]`
**Identifier**: `id` (e.g., "sata1", "nvme0n1")
**Display name**: `name` (e.g., "Drive 4") — unreliable as a
key; `name` orders by physical slot, `id` orders by controller
position; they're uncorrelated. Use `id`. `[observed 2026-04-21]`

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `id` | disk_id | IDENTIFIER | STRING | | Primary key `[re-verified 2026-04-21]` |
| `name` | name | PROPERTY | STRING | | e.g., "Drive 4"; NOT in slot order |
| `longName` | long_name | PROPERTY | STRING | | Mirrors `name` this session `[observed 2026-04-21]` |
| `device` | device | PROPERTY | STRING | | e.g., "/dev/sata1" |
| `model` | model | PROPERTY | STRING | | e.g., "ST10000VN0004-1ZD101" |
| `serial` | serial | PROPERTY | STRING | | Drive serial |
| `vendor` | vendor | PROPERTY | STRING | | e.g., "Seagate" |
| `firm` | firm | PROPERTY | STRING | | Firmware version |
| `diskType` | disk_type | PROPERTY | STRING | | "SATA", "M.2 NVMe" on this NAS `[observed 2026-04-21]` |
| `disk_code` | disk_code | PROPERTY | STRING | | Drive family tag (e.g., `ironwolf`) `[observed 2026-04-21]` |
| `disk_location` | disk_location | PROPERTY | STRING | | `Main` on internal drives `[observed 2026-04-21]` |
| `isSsd` | is_ssd | PROPERTY | BOOLEAN | | Present in response; helpful for NVMe vs SATA filters `[observed 2026-04-21]` |
| `temp` | temp | METRIC | NUMBER | C | Current drive temperature |
| `smart_status` | smart_status | PROPERTY | STRING | | "normal", "abnormal" |
| `unc` | unc_sectors | METRIC | NUMBER | count | Uncorrectable sectors lifetime counter |
| `remain_life.value` | remain_life | METRIC | NUMBER | % | `[superseded 2026-04-21]` Field is **object** `{trustable, value}`, not a scalar; `-1` sentinel for HDD |
| `remain_life.trustable` | remain_life_trustable | PROPERTY | BOOLEAN | | `[observed 2026-04-21]` |
| `size_total` | size_total | PROPERTY | NUMBER | bytes | `[superseded 2026-04-21]` Returned as **string** |
| `slot_id` | slot_id | PROPERTY | NUMBER | | Physical slot number |
| `num_id` | num_id | PROPERTY | NUMBER | | Ordinal that matches the human `name` suffix `[observed 2026-04-21]` |
| `used_by` | used_by | PROPERTY | STRING | | Pool id OR shared-cache id (e.g., `reuse_1`, `shared_cache_1`). `[superseded 2026-04-21]` — Not always a pool id. |
| `container.type` | container_type | PROPERTY | STRING | | `internal` on internal-bay drives `[observed 2026-04-21]` |
| `wcache_force_off` | wcache_force_off | PROPERTY | BOOLEAN | | |

### Disk IO (from SYNO.Core.System.Utilization) `[re-verified 2026-04-21]`

**Source**: `data.disk.disk[]` in the Utilization response.

Sample entry (unfiltered, 2026-04-21):
```json
{
  "device": "sata1",
  "display_name": "Drive 4",
  "read_access": 0,
  "read_byte": 23831,
  "type": "internal",
  "utilization": 1,
  "write_access": 4,
  "write_byte": 582097
}
```

Aggregate entry at `data.disk.total` is unchanged in shape from
2026-04-16.

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `device` | (join key + history filter key) | | STRING | | Matches `disks[].id` (e.g., `sata1`, `nvme0n1`). **Also the value you pass in `interfaces.disk[]` for history.** `[re-verified 2026-04-21]` |
| `display_name` | (display) | | STRING | | `Drive 4`, `Cache device 1` etc. `[re-verified 2026-04-21]` |
| `read_byte` | io_read_bytes | METRIC | NUMBER | bytes/s | `[re-verified 2026-04-21]` |
| `write_byte` | io_write_bytes | METRIC | NUMBER | bytes/s | `[re-verified 2026-04-21]` |
| `read_access` | io_read_access | METRIC | NUMBER | IOPS | `[re-verified 2026-04-21]` |
| `write_access` | io_write_access | METRIC | NUMBER | IOPS | `[re-verified 2026-04-21]` |
| `utilization` | utilization | METRIC | NUMBER | % | `[re-verified 2026-04-21]` |
| `type` | disk_io_type | PROPERTY | STRING | | "internal" for all observed disks (both HDD and NVMe cache) |

**Disk current-value filter quirk:** `resource=["disk"]` trims
top-level keys, but `interfaces.disk=["sata1"]` is **NOT honored
for current values** — all 7 disks still come back. The filter
IS honored on `type=history`, so for live-current metricSets the
MP must post-filter client-side. `[observed 2026-04-21]`

---

## Identifier Chains (Relationships)

### Diskstation -> Storage Pool `[re-verified 2026-04-21]`
- `storagePools[]` are direct children of the Diskstation (world object)
- No explicit join field needed; all pools belong to the one NAS

### Storage Pool -> Volume `[re-verified 2026-04-21]`
- **Join key**: `volumes[].pool_path` == `storagePools[].pool_path` == `storagePools[].id` (all three equal the bare pool id, e.g. `reuse_1`)
- **Correction vs 2026-04-16:** the old map said
  `/pool/reuse_1` but the actual string is just `reuse_1`. Join
  still works because both sides were wrong identically.

### Storage Pool -> Disk `[re-verified 2026-04-21]`
- **Join key**: `storagePools[].disks[]` contains disk IDs matching `disks[].id`
- `reuse_1` has `disks: ["sata1","sata2","sata3","sata4","sata5"]`

### Shared Cache -> Disk `[observed 2026-04-21]`
- **Join key**: `sharedCaches[].disks[]` contains disk IDs
  (`nvme0n1`, `nvme1n1`)
- NVMe disks have `used_by="shared_cache_1"` — so these two
  disks do NOT appear under any storage pool.

### Volume -> Cache `[observed 2026-04-21]`
- **Join key**: `volumes[].cache.id` == `ssdCaches[].id`
- e.g., `volume_1.cache.id = "alloc_cache_1_1"` links to
  `ssdCaches[0]` which has `mountSpaceId: "volume_1"` confirming
  reverse direction.

### Diskstation -> Disk (dual parent) `[unchanged since 2026-04-16]`
- All `disks[]` are also direct children of the Diskstation
- Design artifact specifies dual parent: Diskstation + Storage Pool / Shared Cache
- MPB may or may not support dual-parent relationships -- flagged as Key Risk #1

### Utilization capacity -> IO joins `[observed 2026-04-21]`

| Capacity side (load_info) | IO side (Utilization) | Join rule |
|---|---|---|
| `volumes[].vol_path` = `/volume1` | `space.volume[].display_name` = `volume1` | Strip leading `/` |
| `volumes[].id` = `volume_1` | `space.volume[].device` = `dm-4` | **No direct equivalence** — requires running query against `load_info` then map id↔vol_path↔display_name |
| `disks[].id` = `sata1` | `disk.disk[].device` = `sata1` | **Equal verbatim** ← clean auto-join |

---

## Collection Strategy

- **Requests per cycle (5-min interval)**: 1
  - `SYNO.Storage.CGI.Storage` `load_info` -- full storage topology, capacity, health

- **Note**: Per-disk and per-volume IO metrics come from `SYNO.Core.System.Utilization` `get` (documented in synology-system.md), which is already in the 5-min cycle. No additional request needed for IO.

- **Pagination**: None `[unchanged since 2026-04-16]`
- **Known quirks / reconfirmed + new this session**:
  - `remain_life` is an object `{trustable, value}` — always drill into `.value`; `-1` sentinel for HDD `[observed 2026-04-21]`
  - `size.total`, `size.used`, `size.total_device`, `size_total`, `max_fs_size` are all returned as **JSON strings**, not numbers `[observed 2026-04-21]`
  - `unc` (uncorrectable sectors) is a lifetime counter, not a rate
  - `pool_path` is the **bare pool id** (e.g., `reuse_1`), not `/pool/reuse_1` `[superseded 2026-04-21]`
  - SSD cache may appear in `ssdCaches[]` or `sharedCaches[]` depending on cache type (dedicated vs. shared); both can coexist — this NAS has `shared_cache_1` (physical RAID1 of the two NVMes) AND `alloc_cache_1_1` (volume-mounted cache) `[observed 2026-04-21]`
  - All storage data is returned in one response regardless of how many pools/volumes/disks exist -- no pagination needed
  - The `disks[]` array has both HDD and NVMe; `diskType` values observed are `SATA` and `M.2 NVMe` (with a space) `[observed 2026-04-21]`
  - Disk `used_by` is NOT always a pool id — can be a `shared_cache_*` id for NVMe cache disks `[observed 2026-04-21]`
  - `volumes[]` did **not** contain a `display_name` field on this DSM 7.3.2 run, despite 2026-04-16 notes documenting one; use `vol_path`/`num_id` for display `[superseded 2026-04-21]`

---

## New surfaces observed this session

Adjacent endpoints / fields encountered but intentionally not
explored deeply this refresh (per the scope boundary). Listed
here as backlog for a future cartography session:

- `SYNO.Storage.CGI.Storage load_info` response also contains
  `detected_pools`, `missing_pools`, `overview_data`, `env`,
  `ports`. Could feed Diskstation-level environment/health
  metrics.
- `ssdCaches[].hit_rates` object (7 interval entries) is a
  fully-formed metric source for an SSD Cache object type —
  no additional endpoint needed.
- `SYNO.Core.System.Utilization` supports `type=history` with
  `time_range=week` returning 10,081-point arrays at 60-second
  intervals (~7 days × 24 h × 60 m = 10,080 + 1). Other
  `time_range` values (`day`, `hour`, `month`, `year`) are
  likely supported but not tested this session — good for
  MP backfill logic.
