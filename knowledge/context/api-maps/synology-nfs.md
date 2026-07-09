# Synology API Map: NFS File Service (NFS Export Object)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `$SYNO_HOST:$SYNO_PORT` — DS1520+ running DSM
  7.3.2-86009 Update 1 (credentials from repo `.env`)
- **Last updated:** 2026-05-18
- **Update history:**
  - 2026-05-18 — Initial mapping. Scoped to the v1 VMware-NFS-
    datastore use case. Live-tested NFS service surface
    (`SYNO.Core.FileServ.NFS`,
    `SYNO.Core.FileServ.NFS.AdvancedSetting`,
    `SYNO.Core.FileServ.NFS.SharePrivilege`), share inventory
    (`SYNO.Core.Share list`), and NFS client / connection
    surface (`SYNO.Core.CurrentConnection get`). Confirmed
    that `SYNO.Core.System.Utilization` does NOT expose
    per-share NFS IO — only one server-aggregate row. Captured
    verbatim responses for one NFS-exported share (`vcf9`),
    documented the share -> NFS-rule join, and added an SMB
    "Future v2" note. Added overview-level entries for NFS
    Export (object inventory, endpoint inventory, join keys).
- **Evidence basis:** live API calls this session against the
  DS1520+ NAS; no inherited content (this is a new map file).
- **Notes:** Every observation in this file is from a live call
  made during the 2026-05-18 session. Inline tags are
  `[observed 2026-05-18]` unless otherwise noted. Negative
  findings (per-share NFS IO not available) are intentional —
  they steer the MP designer away from a metric path that does
  not exist on DSM 7.3.

## Endpoints

### SYNO.Core.FileServ.NFS (get)

- **Path**: `/webapi/entry.cgi` `[observed 2026-05-18]`
- **Method**: GET
- **Params**: `api=SYNO.Core.FileServ.NFS&version=3&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)
- **Purpose**: NFS service-level configuration and on/off state.
  This is the canonical "is the NFS server enabled?" probe.

#### Response Schema `[observed 2026-05-18]`

```json
{
  "data": {
    "enable_nfs": true,
    "enable_nfs_v4": true,
    "enabled_minor_ver": 1,
    "nfs_v4_domain": "",
    "read_size": 32768,
    "support_encrypt_share": 1,
    "support_major_ver": 4,
    "support_minor_ver": 1,
    "unix_pri_enable": true,
    "write_size": 32768
  },
  "success": true
}
```

| Field | Type | Notes |
|---|---|---|
| `enable_nfs` | BOOLEAN | NFS service running (v3 + v4 baseline) `[observed 2026-05-18]` |
| `enable_nfs_v4` | BOOLEAN | NFS v4 enabled in addition to v3 `[observed 2026-05-18]` |
| `enabled_minor_ver` | NUMBER | Active NFS v4 minor version (1 here = NFS 4.1) `[observed 2026-05-18]` |
| `support_major_ver` | NUMBER | Highest major version supported (4 here) `[observed 2026-05-18]` |
| `support_minor_ver` | NUMBER | Highest minor version supported (1 here) `[observed 2026-05-18]` |
| `read_size` | NUMBER | NFS server `rsize` (bytes) `[observed 2026-05-18]` |
| `write_size` | NUMBER | NFS server `wsize` (bytes) `[observed 2026-05-18]` |
| `nfs_v4_domain` | STRING | Empty when default `[observed 2026-05-18]` |
| `unix_pri_enable` | BOOLEAN | UNIX-style permissions toggle `[observed 2026-05-18]` |
| `support_encrypt_share` | NUMBER | Encryption support flag `[observed 2026-05-18]` |

---

### SYNO.Core.FileServ.NFS.AdvancedSetting (get)

- **Path**: `/webapi/entry.cgi` `[observed 2026-05-18]`
- **Method**: GET
- **Params**: `api=SYNO.Core.FileServ.NFS.AdvancedSetting&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema `[observed 2026-05-18]`

```json
{
  "data": {
    "custom_port_enable": 0,
    "nfs_v4_domain": "",
    "nlm_port": 0,
    "read_size": 32768,
    "statd_port": 0,
    "unix_pri_enable": true,
    "write_size": 32768
  },
  "success": true
}
```

Mostly overlaps with `NFS get`. Adds:

| Field | Type | Notes |
|---|---|---|
| `custom_port_enable` | NUMBER (0/1) | Custom NFS port mode `[observed 2026-05-18]` |
| `nlm_port` | NUMBER | NLM lock-manager port (0 = default/auto) `[observed 2026-05-18]` |
| `statd_port` | NUMBER | rpc.statd port (0 = default/auto) `[observed 2026-05-18]` |

**Verdict**: Useful only if the MP wants to surface lock/statd
port info. The v1 MP scope can lean on `NFS get` alone for
service-level state.

---

### SYNO.Core.Share (list)

- **Path**: `/webapi/entry.cgi` `[observed 2026-05-18]`
- **Method**: GET
- **Params**: `api=SYNO.Core.Share&version=1&method=list&shareType=all&additional=<json-array>&_sid=<session>`
- **Auth**: Session ID required (admin)
- **Purpose**: Lists ALL shared folders (not just NFS). To
  identify the NFS-exported subset, cross-reference with
  `SYNO.Core.FileServ.NFS.SharePrivilege load` (next endpoint)
  per share.

#### Useful `additional` fields `[observed 2026-05-18]`

The `additional` query param is a URL-encoded JSON array. Asking
for `nfs_rules` was tried and **silently ignored** — the response
contains the requested capacity / encryption / quota fields but
no NFS-specific keys. A few values that DO populate:

```
"hidden", "encryption", "share_quota", "enable_share_cow",
"enable_recycle_bin", "quota_value", "enable_share_compress",
"name", "is_aclmode", "enable_aaa", "unite_permission",
"is_support_acl", "is_sync_share", "is_force_readonly",
"force_readonly_reason", "is_cluster_share", "is_exfat_share"
```

#### Response Schema — one share entry (`vcf9`, verbatim) `[observed 2026-05-18]`

```json
{
  "compression_ratio_tips": false,
  "desc": "",
  "disable_list": false,
  "enable_share_compress": false,
  "enable_share_cow": false,
  "enc_auto_mount": false,
  "encryption": 0,
  "force_readonly_reason": "",
  "hidden": false,
  "is_aclmode": true,
  "is_cluster_share": false,
  "is_exfat_share": false,
  "is_force_readonly": false,
  "is_support_acl": true,
  "is_sync_share": false,
  "is_usb_share": false,
  "name": "vcf9",
  "quota_value": 3145728,
  "share_quota_logical_size": 81090.3125,
  "share_quota_status": "v1",
  "share_quota_used": 81090.3125,
  "support_compression_ratio": false,
  "unite_permission": false,
  "uuid": "fdfa665f-1f7c-4870-b919-ee5827141d92",
  "vol_path": "/volume1"
}
```

| Field | Type | Notes |
|---|---|---|
| `name` | STRING | **Primary identifier**, e.g., `vcf9` `[observed 2026-05-18]` |
| `uuid` | STRING | DSM-internal stable UUID `[observed 2026-05-18]` |
| `vol_path` | STRING | Parent volume mount (e.g., `/volume1`) — **join to `volumes[].vol_path`** `[observed 2026-05-18]` |
| `desc` | STRING | Share description `[observed 2026-05-18]` |
| `quota_value` | NUMBER | Share quota target — units appear to be MiB (`3145728` ≈ 3 TiB on the `vcf9` share); 0 = no quota `[inferred from magnitude 2026-05-18]` |
| `share_quota_used` | NUMBER | Same unit as `quota_value`; 0..quota_value `[inferred from magnitude 2026-05-18]` |
| `share_quota_logical_size` | NUMBER | Pre-compression size (matches `used` when compression is off) `[inferred from magnitude 2026-05-18]` |
| `encryption` | NUMBER | 0 = unencrypted `[observed 2026-05-18]` |
| `enable_share_cow` | BOOLEAN | Btrfs CoW on/off `[observed 2026-05-18]` |
| `enable_share_compress` | BOOLEAN | Btrfs compression on/off `[observed 2026-05-18]` |
| `hidden` | BOOLEAN | Hidden in Windows browse list `[observed 2026-05-18]` |
| `is_usb_share` | BOOLEAN | USB-attached share `[observed 2026-05-18]` |

**Important**: this endpoint returns ALL shares regardless of
which protocols (NFS / SMB / AFP / WebDAV) are enabled on them.
Whether a given share is "an NFS export" is determined only by
calling `NFS.SharePrivilege load` per share — see below.

---

### SYNO.Core.FileServ.NFS.SharePrivilege (load)

- **Path**: `/webapi/entry.cgi` `[observed 2026-05-18]`
- **Method**: GET
- **Params**: `api=SYNO.Core.FileServ.NFS.SharePrivilege&version=1&method=load&share_name=<share>&_sid=<session>`
- **Auth**: Session ID required (admin)
- **Purpose**: Returns the per-client NFS export rules for one
  share (allowed hosts, privilege, squash, security). The
  presence-or-absence of rules is the canonical "is this share
  NFS-exported?" check.

#### Method discovery `[observed 2026-05-18]`

| Method | Result |
|---|---|
| `list` | error 103 (method not exists) |
| `enum` | error 103 |
| `info` | error 103 |
| `status` | error 103 |
| `query` | error 103 |
| `load` (no share_name) | error 2301 — missing required param |
| `load` with `name=<x>` | error 2301 |
| `load` with `share_name=<x>` | **success** |

**Only `load` works, and only with `share_name=`.** There is no
list-all-NFS-exports endpoint. The MP adapter must iterate the
shares from `SYNO.Core.Share list` and call this per share.

#### Response Schema — one NFS-exported share (`vcf9`, verbatim) `[observed 2026-05-18]`

```json
{
  "data": {
    "rule": [
      {
        "async": true,
        "client": "172.16.3.0/24",
        "crossmnt": false,
        "insecure": false,
        "privilege": "rw",
        "root_squash": "root",
        "security_flavor": {
          "kerberos": false,
          "kerberos_integrity": true,
          "kerberos_privacy": false,
          "sys": true
        }
      },
      {
        "async": true,
        "client": "172.27.1.0/24",
        "crossmnt": false,
        "insecure": false,
        "privilege": "rw",
        "root_squash": "root",
        "security_flavor": {
          "kerberos": false,
          "kerberos_integrity": false,
          "kerberos_privacy": false,
          "sys": true
        }
      }
    ]
  },
  "success": true
}
```

#### Response Schema — share with NFS disabled (e.g., `docker`, `homes`, `web_packages`) `[observed 2026-05-18]`

```json
{
  "data": {
    "rule": []
  },
  "success": true
}
```

**Decision rule**: `data.rule.length > 0` ⇒ share is an NFS
export. Empty array ⇒ share exists but NFS protocol is not
enabled on it.

| Rule field | Type | Notes |
|---|---|---|
| `client` | STRING | Allowed client expression: single IP (`172.16.3.13/32`), CIDR (`172.16.3.0/24`), or hostname pattern `[observed 2026-05-18]` |
| `privilege` | STRING | `rw` or `ro` (read-only). All observed rules this session were `rw` `[observed 2026-05-18]` |
| `root_squash` | STRING | `root` (default — squash root only), `all` (squash all), `none` (no squash; trusted) `[inferred from common Linux NFS semantics; only `root` observed live]` |
| `async` | BOOLEAN | NFS async write mode `[observed 2026-05-18]` |
| `crossmnt` | BOOLEAN | Allow client to cross filesystem boundaries `[observed 2026-05-18]` |
| `insecure` | BOOLEAN | Allow client from non-privileged source ports `[observed 2026-05-18]` |
| `security_flavor.sys` | BOOLEAN | AUTH_SYS allowed `[observed 2026-05-18]` |
| `security_flavor.kerberos` | BOOLEAN | krb5 (auth only) `[observed 2026-05-18]` |
| `security_flavor.kerberos_integrity` | BOOLEAN | krb5i (auth + integrity) `[observed 2026-05-18]` |
| `security_flavor.kerberos_privacy` | BOOLEAN | krb5p (auth + integrity + encryption) `[observed 2026-05-18]` |

#### NFS-enabled inventory captured this session `[observed 2026-05-18]`

Out of 11 shares on this NAS, 9 are NFS-exported:

| Share | NFS rules | Notes |
|---|---|---|
| `ActiveBackupforBusiness` | 13 | Per-host /32 rules — VMware-VM-level access |
| `backup` | 1 | Single /32 rule |
| `docker` | 0 | SMB only (no NFS) |
| `homes` | 0 | SMB only (no NFS) |
| `public` | 7 | Mix of /24 CIDR + /32 host rules |
| `vcf9` | 2 | /24 CIDRs — **this is the v1 target use case** |
| `vsphere_admin` | 5 | /24 CIDRs |
| `web` | 1 | Single /32 |
| `web_packages` | 0 | SMB only (no NFS) |
| `wld01` | 2 | /24 CIDRs — VMware workload domain 1 |
| `wld02` | 2 | /24 CIDRs — VMware workload domain 2 |

---

### SYNO.Core.System.Utilization — NFS section

- Already documented in `synology-storage.md` and
  `synology-system.md` for the cpu/memory/disk/space surfaces.
  This section covers the `nfs` resource only.
- **Path**: `/webapi/entry.cgi`
- **Method**: GET (or POST for the form-encoded filter variant)
- **Params**: `api=SYNO.Core.System.Utilization&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Server-aggregate NFS row `[observed 2026-05-18]`

When called with no filter, the response contains a single-element
`nfs` array:

```json
"nfs": [
  {
    "device": "nfs",
    "read_OPS": 2,
    "read_max_latency": 203,
    "total_OPS": 4,
    "total_max_latency": 315,
    "write_OPS": 2,
    "write_max_latency": 315
  }
]
```

| Field | Type | Unit | Notes |
|---|---|---|---|
| `device` | STRING | | Always `"nfs"`; there is no per-share identifier `[observed 2026-05-18]` |
| `read_OPS` | NUMBER | ops/s | Read operations per second, server-wide `[observed 2026-05-18]` |
| `write_OPS` | NUMBER | ops/s | Write operations per second, server-wide `[observed 2026-05-18]` |
| `total_OPS` | NUMBER | ops/s | `read_OPS + write_OPS` (verified by inspection: 2+2=4) `[observed 2026-05-18]` |
| `read_max_latency` | NUMBER | ms (probable) | Worst-case read latency in sample window; units NOT explicitly documented — values 50-450 are consistent with milliseconds `[inferred from magnitude 2026-05-18]` |
| `write_max_latency` | NUMBER | ms (probable) | As above for writes `[inferred from magnitude 2026-05-18]` |
| `total_max_latency` | NUMBER | ms (probable) | max(read_max_latency, write_max_latency) by inspection `[observed 2026-05-18]` |

#### Filter behavior `[observed 2026-05-18]`

| Variant | Result |
|---|---|
| `resource=["nfs"]` only | Trims top-level keys to just `nfs` + `time`; still single row. |
| `resource=["nfs"]` + `interfaces={"nfs":["vcf9"]}` | **Filter is silently ignored.** Same one-row response. Tried selectors `vcf9`, `/volume1/vcf9`, `share_vcf9`, `wld01` — identical output. |
| `type=history time_range=week resource=["nfs"] interfaces={"nfs":["nfs"]}` | **Works**: returns 10,081-point time-series arrays for `read_OPS`, `write_OPS`, `total_OPS`, `read_max_latency`, `write_max_latency`, `total_max_latency` at 60-second intervals. |
| `type=history time_range=day` / `hour` (with same filter) | Returns empty `data: {}` — quirk of the API, same shape as elsewhere. |

#### KEY FINDING — no per-share NFS IO `[observed 2026-05-18]`

**`SYNO.Core.System.Utilization` does NOT expose per-share NFS
IO metrics on DSM 7.3.2.** The `nfs` resource is a single server-
aggregate row identified only by `device: "nfs"`. The
`interfaces.nfs[]` filter is accepted by the API but produces no
filtering effect — the same aggregate row comes back regardless
of selector value.

**Fallback for "how busy is THIS export":** the share lives on a
specific volume (`vol_path`). The MP should attribute per-share
IO pressure to the parent **Volume**'s `space.volume[]` metrics
(already mapped in `synology-storage.md`: `read_byte`,
`write_byte`, `read_access`, `write_access`, `utilization`).
This is coarser than per-share IO would be — multiple shares on
the same volume blur together — but it is the only IO signal
DSM provides.

---

### SYNO.Core.CurrentConnection (get)

- **Path**: `/webapi/entry.cgi` `[observed 2026-05-18]`
- **Method**: GET
- **Params**: `api=SYNO.Core.CurrentConnection&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)
- **Purpose**: Lists every active connection to DSM regardless
  of protocol (HTTP/HTTPS, NFS, SMB, FTP, AFP, etc.). The NFS
  rows give us **per-export client counts and source IPs** —
  the closest thing DSM has to per-share NFS telemetry.

#### Method discovery `[observed 2026-05-18]`

| Method | Result |
|---|---|
| `get` | **success** |
| `list` | **success** (identical payload to `get`) |
| `info` | error 103 |
| `enum` | error 103 |

#### Response Schema — one NFS connection (verbatim) `[observed 2026-05-18]`

```json
{
  "can_be_kicked": false,
  "descr": "vcf9",
  "did": "",
  "first_login_time": "",
  "from": "172.27.1.14",
  "is_amfa": false,
  "is_current_connected": false,
  "is_otp_trusted": false,
  "location": "",
  "pid": 0,
  "protocol": "NFS",
  "time": "2026/05/08 11:40:25",
  "type": "NFS",
  "user_agent": "",
  "user_can_be_disabled": false,
  "who": ""
}
```

| Field | Type | Notes |
|---|---|---|
| `protocol` | STRING | Filter on `"NFS"` to isolate NFS connections `[observed 2026-05-18]` |
| `type` | STRING | Mirrors `protocol` for NFS rows `[observed 2026-05-18]` |
| `descr` | STRING | **NFS share name** for NFS rows (e.g., `vcf9`, `wld01`) — the join key back to share inventory. May be `"-"` for some NFS rows (see quirk below) `[observed 2026-05-18]` |
| `from` | STRING | Client IP address `[observed 2026-05-18]` |
| `time` | STRING | Timestamp formatted `YYYY/MM/DD HH:MM:SS` (DSM-local timezone) `[observed 2026-05-18]` |
| `who` | STRING | DSM username — always `""` for NFS rows (NFS uses host-based, not user-based auth) `[observed 2026-05-18]` |
| `pid` | NUMBER | Always 0 for NFS rows `[observed 2026-05-18]` |
| `can_be_kicked` | BOOLEAN | Always `false` for NFS rows `[observed 2026-05-18]` |

#### Sample tally for this NAS (12 total connections; 10 NFS) `[observed 2026-05-18]`

```
NFS connections by share descr:
  'vcf9'   -> 5  (172.27.1.14, 172.16.3.247, 172.16.3.254,
                  172.16.3.236, 172.16.3.110)
  'wld01'  -> 2  (172.16.3.102, 172.16.3.101)
  'wld02'  -> 2  (172.16.3.103, 172.16.3.104)
  '-'      -> 1  (172.16.3.13 -- this host's own NFS mount of 'backup')
```

#### Quirk: `descr='-'` on some NFS rows `[observed 2026-05-18]`

One NFS connection from `172.16.3.13` reported `descr='-'` with
`protocol='NFS'`. That IP has an NFS export rule on the `backup`
share (`172.16.3.13/32`). Hypothesis: DSM cannot resolve the
share descriptor when the connection is observed via an NFS
control op (lock, mount probe) rather than an active read/write
session; `descr` falls back to `'-'`. Cannot fully verify without
mutating server state. **Implication for the MP**: when tallying
clients-per-share, skip rows where `descr` is `"-"` or `""` — or
group them under an "unattributed" bucket. Don't fail the
collection.

---

## Object Model Candidates

### NFS Export

A first-class object representing one **NFS-exported shared
folder** on the DiskStation. Recommended for v1 because the
VMware-NFS-datastore use case is the entire reason for this MP —
operators need to see "which VMware datastore is this Synology
share?", and the export path is the unambiguous link to the ESXi
side.

| Aspect | Value |
|---|---|
| **Identifier** | `name` (e.g., `vcf9`). Alternative stable key: `uuid` from `SYNO.Core.Share list` `[observed 2026-05-18]` |
| **Parent** | Volume (joined via `vol_path`) `[observed 2026-05-18]` |
| **Source endpoints** | `SYNO.Core.Share list` (inventory + capacity), `SYNO.Core.FileServ.NFS.SharePrivilege load` (rules — N+1 calls), `SYNO.Core.CurrentConnection get` (client tallies) |
| **Existence rule** | A share is an NFS Export iff `SharePrivilege.load(share_name).data.rule.length > 0` |

#### Properties `[observed 2026-05-18]`

| MP Key | Source | Type | Notes |
|---|---|---|---|
| `name` | `Share list shares[].name` | STRING | Identifier |
| `uuid` | `Share list shares[].uuid` | STRING | Stable alternative ID |
| `vol_path` | `Share list shares[].vol_path` | STRING | Parent volume mount, e.g., `/volume1` |
| `export_path` | (derived) `vol_path + "/" + name` | STRING | The path an ESXi NFS datastore mounts (`/volume1/vcf9`) — **the stitching key into vSphere** |
| `desc` | `Share list shares[].desc` | STRING | Human description |
| `quota_value` | `Share list shares[].quota_value` | NUMBER (MiB) | 0 = no quota |
| `encryption` | `Share list shares[].encryption` | NUMBER | 0 = unencrypted |
| `enable_share_cow` | `Share list shares[].enable_share_cow` | BOOLEAN | Btrfs CoW |
| `enable_share_compress` | `Share list shares[].enable_share_compress` | BOOLEAN | Btrfs compression |
| `hidden` | `Share list shares[].hidden` | BOOLEAN | |
| `rule_count` | derived: `SharePrivilege.load.data.rule.length` | NUMBER | How many client expressions are configured |
| `allowed_clients` | derived: comma-joined `rule[].client` | STRING | Concatenated CIDR/IP list (for property display) |
| `has_kerberos_required` | derived: any rule with `security_flavor.kerberos*` and not `sys` | BOOLEAN | Sec posture |
| `has_root_squash` | derived: any rule with `root_squash != "none"` | BOOLEAN | Sec posture |
| `has_readonly_clients` | derived: any rule with `privilege == "ro"` | BOOLEAN | |

#### Metrics `[observed 2026-05-18]`

| MP Key | Source | Type | Unit | Notes |
|---|---|---|---|---|
| `share_size_used` | `Share list shares[].share_quota_used` | NUMBER | MiB | Actual consumed size |
| `share_size_logical` | `Share list shares[].share_quota_logical_size` | NUMBER | MiB | Pre-compression size |
| `quota_usage_pct` | derived: `share_quota_used / quota_value * 100` | NUMBER | % | Only meaningful when `quota_value > 0`; otherwise null/omit |
| `active_client_count` | derived: count of `CurrentConnection items[]` where `protocol == 'NFS' AND descr == name` | NUMBER | count | Number of distinct active NFS clients connected to this export |

#### No-go metrics (confirmed not available) `[observed 2026-05-18]`

The MP designer should NOT attempt to populate these from DSM:

| Wished-for metric | Why not |
|---|---|
| `read_bytes_per_share` | `Utilization nfs[]` returns only a server-aggregate row; `interfaces.nfs[]` filter is silently ignored |
| `write_bytes_per_share` | Same |
| `read_ops_per_share` | Same |
| `write_ops_per_share` | Same |
| `latency_per_share` | Same |

**Fallback**: attribute IO pressure to the parent Volume's
`space.volume[]` row (already mapped in `synology-storage.md`).

---

### Diskstation — NFS service properties (extends existing Diskstation object)

These are server-level NFS facts that belong on the existing
Diskstation object, not on per-Export objects.

| MP Key | Source | Type | Notes |
|---|---|---|---|
| `nfs_enabled` | `NFS get data.enable_nfs` | BOOLEAN | **Alert candidate** — service stopped |
| `nfs_v4_enabled` | `NFS get data.enable_nfs_v4` | BOOLEAN | |
| `nfs_active_minor_ver` | `NFS get data.enabled_minor_ver` | NUMBER | 1 = NFS 4.1 |
| `nfs_read_size` | `NFS get data.read_size` | NUMBER (bytes) | Server rsize |
| `nfs_write_size` | `NFS get data.write_size` | NUMBER (bytes) | Server wsize |
| `nfs_total_ops` | `Utilization nfs[0].total_OPS` | NUMBER | Aggregate OPS, server-wide |
| `nfs_read_ops` | `Utilization nfs[0].read_OPS` | NUMBER | |
| `nfs_write_ops` | `Utilization nfs[0].write_OPS` | NUMBER | |
| `nfs_total_max_latency` | `Utilization nfs[0].total_max_latency` | NUMBER (ms probable) | Worst latency this sample |
| `nfs_total_client_count` | derived: count of `CurrentConnection items[]` where `protocol == 'NFS'` | NUMBER | Server-wide active NFS connections (alert candidate: abnormal churn / drop-to-zero) |
| `nfs_export_count` | derived: count of NFS Exports under this Diskstation | NUMBER | |

---

## Cross-Request Join Keys

| Field A | Endpoint A | Field B | Endpoint B | Relationship |
|---|---|---|---|---|
| `shares[].vol_path` | `Share list` | `volumes[].vol_path` | `Storage.CGI.Storage load_info` | NFS Export -> Volume (parent) `[observed 2026-05-18]` |
| `shares[].name` | `Share list` | `share_name` query param | `NFS.SharePrivilege load` | Drives per-share rule fetch `[observed 2026-05-18]` |
| `shares[].name` | `Share list` | `CurrentConnection items[].descr` | `CurrentConnection get` (filter `protocol='NFS'`) | NFS Export -> active client list `[observed 2026-05-18]` |
| (derived) `vol_path + "/" + name` | local | `nfs.host:/volume1/<share>` | ESXi NFS datastore mount path | NFS Export -> vSphere Datastore (cross-MP stitch) `[inferred from VMware NFS mount syntax; not live-verified against vSphere this session]` |

---

## Collection Strategy

For each 5-minute collection cycle (proposed):

| Request | Endpoint | Per-cycle cost | Feeds |
|---|---|---|---|
| 1 | `SYNO.Core.FileServ.NFS get` | 1 | Diskstation service state |
| 2 | `SYNO.Core.Share list` (with `additional`) | 1 | NFS Export inventory + capacity |
| 3..N+2 | `SYNO.Core.FileServ.NFS.SharePrivilege load` | **1 per share** | NFS Export rules + existence flag |
| N+3 | `SYNO.Core.CurrentConnection get` | 1 | Per-share client counts |

On this NAS (11 shares), that is **14 requests per 5-minute
cycle** just for NFS. The N+1 per-share rule call is the dominant
cost. If that is too expensive at higher share counts, options:

1. **Cache NFS rules at the 30-minute cycle** — rules change
   rarely; only refresh quota/usage and client counts at 5 min.
2. **Probe only known-NFS shares after first cycle** — once an
   adapter has observed a share with `rule.length > 0`, it can
   continue polling only that subset until a config-change event
   forces a re-discover.

The MP designer should pick a strategy; both are valid.

---

## Coverage Matrix: Design Artifact vs. API Sources

### NFS Export (proposed — 14 fields)

| Metric/Property | Source | Status |
|---|---|---|
| name, uuid, vol_path, desc | Share list shares[] | CONFIRMED `[observed 2026-05-18]` |
| export_path (derived) | computed | CONFIRMED (derivable) |
| quota_value, encryption | Share list shares[] | CONFIRMED `[observed 2026-05-18]` |
| enable_share_cow, enable_share_compress, hidden | Share list shares[] | CONFIRMED `[observed 2026-05-18]` |
| share_size_used, share_size_logical | Share list shares[] | CONFIRMED `[observed 2026-05-18]` |
| quota_usage_pct (derived) | computed | CONFIRMED (derivable) |
| rule_count, allowed_clients | SharePrivilege load data.rule[] | CONFIRMED `[observed 2026-05-18]` |
| has_kerberos_required, has_root_squash, has_readonly_clients | derived from rules | CONFIRMED (derivable) |
| active_client_count | CurrentConnection items[].descr | CONFIRMED `[observed 2026-05-18]` |
| per-share IO bytes/OPS/latency | (none — DSM does not expose) | CONFIRMED NOT AVAILABLE `[observed 2026-05-18]` |

### Diskstation NFS service (proposed — 11 fields)

| Metric/Property | Source | Status |
|---|---|---|
| nfs_enabled, nfs_v4_enabled, nfs_active_minor_ver | FileServ.NFS get | CONFIRMED `[observed 2026-05-18]` |
| nfs_read_size, nfs_write_size | FileServ.NFS get | CONFIRMED `[observed 2026-05-18]` |
| nfs_total_ops, nfs_read_ops, nfs_write_ops | Utilization nfs[0] | CONFIRMED `[observed 2026-05-18]` |
| nfs_total_max_latency | Utilization nfs[0] | CONFIRMED `[observed 2026-05-18]` (units inferred ms) |
| nfs_total_client_count | derived from CurrentConnection | CONFIRMED `[observed 2026-05-18]` |
| nfs_export_count | derived from rule tally | CONFIRMED (derivable) |

---

## Gaps / Open Questions

1. **Per-share NFS IO (read/write bytes, OPS, latency)** —
   CONFIRMED NOT AVAILABLE via DSM REST on DSM 7.3.2. The
   `Utilization nfs[]` resource is server-aggregate only and
   the `interfaces.nfs[]` filter is silently ignored. Fallback:
   per-Volume IO from `Utilization space.volume[]` (already
   mapped in `synology-storage.md`). The MP designer should NOT
   attempt to model per-share IO. `[observed 2026-05-18]`

2. **Latency units** — `nfs.{read,write,total}_max_latency`
   values 50-450 are consistent with milliseconds but DSM does
   not explicitly document the unit. The Synology DSM UI labels
   these as ms in the Resource Monitor view. Treat as ms with
   `[inferred from magnitude]` until vendor docs confirm.

3. **NFS rule list — no bulk endpoint** — `SharePrivilege` only
   supports `load` with a single `share_name`. To enumerate
   exports across N shares the adapter must make N calls. No
   `list_all` or `enum` variant works (all return error 103).
   This is a real cost driver. `[observed 2026-05-18]`

4. **`descr='-'` quirk in CurrentConnection NFS rows** — at
   least one NFS row this session had `descr='-'` instead of a
   share name, from a client that DOES have an NFS export rule
   for a real share (`backup`). Likely a stale/control-op
   connection. The MP adapter should treat such rows as
   unattributed (still count them in the server-wide total but
   not in per-share tallies). Worth re-verifying behavior on a
   busier NFS server. `[observed 2026-05-18]`

5. **Quota units** — `Share list shares[].quota_value` value
   `3145728` on a 3 TiB-quota share is consistent with MiB
   (3,145,728 MiB = 3 TiB). Marked `[inferred from magnitude]`.
   Could be verified by setting a known quota via DSM UI and
   reading it back; not done this session.

6. **`SYNO.Snap.Usage.Share`** — not callable with any of the
   common method names tested (`get`, `list`, `query`, `enum`
   all returned error 103). Might require a specific method
   name documented elsewhere. Possibly redundant with
   `Share list` quota fields anyway. `[observed 2026-05-18]`

---

## Future v2 — SMB

Out of scope for v1, but the surface exists and the next
cartographer session should not have to re-enumerate:

- `SYNO.Core.FileServ.SMB` v3 `get` works and returns the SMB
  service config (~30 fields: protocol min/max, encryption,
  AD/workgroup, leases, etc.) `[observed 2026-05-18]`.
- `SYNO.Core.FileServ.SMB.Control` exists per `API.Info` but
  none of the obvious methods (`status`, `get_status`, `load`)
  responded — needs more probing.
- `SYNO.Core.FileServ.SMB.ConfBackup` and
  `SYNO.Core.FileServ.SMB.MSDFS` exist for completeness.
- **Per-share SMB IO**: `Utilization smb` resource returns
  `smb_cmd`, `smb_cpu`, `smb_rwpkt` — all empty arrays on
  this NAS this session. This may populate only when the SMB
  performance chart feature is explicitly enabled (the SMB
  `get` response shows `enable_perf_chart: false` on this NAS).
  Worth testing with that flag flipped on. `[observed 2026-05-18]`
- **Per-share SMB client list**: `CurrentConnection get` rows
  with `protocol == 'SMB'` exist by analogy with the NFS rows,
  but none were observed this session because no SMB sessions
  were active. Logic should mirror the NFS approach exactly.
