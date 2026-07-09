# Synology API Map: Events / Notifications

## Purpose

Maps the DSM API surface that the MP renders as **MPB events** — the
messages a Synology admin would see in the DSM UI "notifications"
area. Threshold-based alerting (temp high, CPU high, disk nearly
full) is handled by **factory symptoms + alerts** against the
collected metrics; only discrete admin-visible notifications live
in this file.

Live-tested on DS1520+ / DSM 7.3.2-86009 Update 1.

## Summary: Primary Endpoint per Target Scenario

| Scenario | Primary Endpoint | Filter | Object |
|---|---|---|---|
| 1. Data / filesystem scrubbing (start + finish) | `SYNO.Core.SyslogClient.Log` | `keyword=scrubbing` | Storage Pool or Volume (parsed from `descr`) |
| 2. Backup completion (Active Backup for Business) | `SYNO.Core.SyslogClient.Log` | `keyword=Active Backup` | Diskstation (ABB tasks are not modeled as MP objects) |
| 3. DSM out-of-date (update available) | `SYNO.Core.Upgrade.Server` v4 `check` | (none — scalar state) | Diskstation |
| 4. Security advisories (brute-force, login anomalies) | `SYNO.SecurityAdvisor.LoginActivity` v1 `list` | (none) | Diskstation |

Secondary / supplementary endpoints:

| Supplementary feed | Endpoint | Use |
|---|---|---|
| Disk overheat / health transitions | `SYNO.Core.SyslogClient.Log` `keyword=Disk` | Disk object |
| Failed DSM sign-ins (individual) | `SYNO.Core.SyslogClient.Log` `logtype=connection` + `keyword=failed` | Diskstation |
| System booted from improper shutdown | `SYNO.Core.SyslogClient.Log` `keyword=improper` | Diskstation |
| Host auto-blocked by AutoBlock | `SYNO.Core.SyslogClient.Log` `keyword=blocked` | Diskstation |
| Link up / link down | `SYNO.Core.SyslogClient.Log` `keyword=link` | Diskstation (no NIC object in v1 model) |
| Package install/update/repair failures | `SYNO.Core.SyslogClient.Log` `keyword=Package` + `level=err` | Diskstation |
| Volume / pool creation + deletion | `SYNO.Core.SyslogClient.Log` (Storage Pool / Volume text) | Storage Pool or Volume |

## Endpoint Reconnaissance

Error code legend (observed):

- **103** = method does not exist for that API/version. Frequently
  gates read access — many `SYNO.Core.Notification.*` and
  `SYNO.Core.DSMNotify` APIs return 103 for every public verb.
- **102** = API does not exist on this instance (e.g.,
  `SYNO.ActiveBackup.Activity` on our 9.0.2 box).
- **114** = missing required parameter.
- **117** = invalid input.

### APIs probed and rejected (toolset gap candidates)

| API | Methods tried | Result | Notes |
|---|---|---|---|
| `SYNO.Core.DSMNotify` | `list`, `get`, `enum`, `query`, `hit`, `receive`, `poll`, `read`, `clear`, `listsince`, `subscribe`, `pull` | All 103 | Public verbs are gated. This is the DSM UI's notification drawer backend but not exposed to third-party sessions. |
| `SYNO.Core.Notification.Sysnotify` | `list`, `get`, `enum`, `hit`, `receive`, `poll`, `read`, `fetch`, `count` | All 103 | Same behavior. |
| `SYNO.Core.PersonalNotification.Event` | `list`, `get`, `enum`, `hit`, `receive`, `poll`, `read`, `fetch`, `clear`, `listsince`, `count` | All 103 | Personal (per-user) notification store; no read verb reachable via session. |
| `SYNO.Core.AppNotify` | `list`, `get`, `hit`, `receive`, `poll`, `read`, `fetch`, `count` | 103 / 117 | App-scoped notifications; no read verb. |
| `SYNO.LogCenter.Log` v2 | `list` with many param permutations | `{items: [], total: 0}` | Log Center package not installed on this instance. Returns empty shell, does not error. |
| `SYNO.Storage.CGI.Scrubbing` | `list`, `status`, `get` | All 103 | Not introspectable — scrubbing state must be read from syslog. |
| `SYNO.Btrfs.Replica` | `list`, `get`, `enum`, `info` | 103 / 1001 | Snapshot Replication package not active. No events to read. |
| `SYNO.SecurityAdvisor.Report` | `list`, `get` | 117 / 103 | Requires a pre-generated report; not a live feed. |
| `SYNO.ResourceMonitor.Log` | `list` | `{logs: [], total: 0}` | Resource Monitor threshold-log feature exists but is empty on this box. Moved to "future" — factory symptoms/alerts replace this. |
| `SYNO.ActiveBackup.Log` | `list`, `get`, `enum` (v1 + v2) | All 103 | Package-internal; not readable over REST. |
| `SYNO.ActiveBackup.Activity` | `list`, `get`, `list_done` | All 102 | Not present on this DSM build. |
| `SYNO.ActiveBackup.Report` | `list` (with and without `task_id`) | `{reports: [], total: 0}` | Probably task-scoped but our ABB task reports are pruned. Requires task run within retention window. |

**Verdict**: the only read-accessible admin-visible event feed on
DSM 7.3.2 is the **classic syslog reader** at
`SYNO.Core.SyslogClient.Log`. The dedicated notification APIs
(`DSMNotify`, `Notification.Sysnotify`, `PersonalNotification.Event`)
reject every read verb with error 103. Scott's "DSM notifications
bell" UI *does* use these APIs, but only inside a privileged
JSUI-bound session path our monitoring account cannot traverse.

## Primary Endpoint Detail

### SYNO.Core.SyslogClient.Log

- **Path**: `/webapi/entry.cgi`
- **Method**: GET (query string)
- **Version**: 1
- **Method name**: `list`
- **Auth**: session `_sid`, admin account
- **Endpoint total row count (this instance)**: 4660 system + 9904
  connection entries retained on the box.

#### Request parameters

| Parameter | Type | Required | Effect |
|---|---|---|---|
| `start` | integer | yes | Offset for pagination (0 = most recent). Items are ordered newest-first. |
| `limit` | integer | yes | Page size. 1000 per page is safe; larger values return full pages. |
| `logtype` | string | no | `system` (default), `connection`, `filetransfer`, `backup`, plus protocol-specific (`win`, `ftp`, `webdav`, `afp`) — most are empty on this instance. |
| `level` | string | no | `info` / `warning` / `error` — note: observed behaviour is loose; passing `error` still returned info rows in our testing. Use in combination with post-filter by `item.level` to be safe. |
| `keyword` | string | no | Server-side substring match against `descr`. Confirmed functional (`keyword=scrubbing` → exactly 60 hits). |
| `datefrom` / `date_from` | integer | no | Attempted several names; `date_from` is rejected as type-invalid; other forms silently accepted but **not honoured** (total row count unchanged). **Conclusion**: server-side time filtering is not exposed. MP must use client-side time watermarking. |

#### Response schema

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "time": "2026/04/06 06:23:51",
        "level": "info",
        "logtype": "System",
        "orginalLogType": "system",
        "descr": "System successfully finished filesystem scrubbing on [Volume 1].",
        "who": "SYSTEM"
      }
    ],
    "total": 4660,
    "infoCount": 1,
    "warnCount": 0,
    "errorCount": 0
  }
}
```

#### Item field mapping (→ MPB event attributes)

| Source field | MPB event attribute | Notes |
|---|---|---|
| `time` | `event.timestamp` | Format: `YYYY/MM/DD HH:MM:SS` in NAS local time. Parse + convert to epoch ms. **There is no unique numeric ID** — use the `(time, descr, who)` tuple as the dedup key in the MP renderer's seen-events cache. |
| `level` | `event.severity` | Map: `info` → INFORMATION, `warn` → WARNING, `err` → CRITICAL. Typo intentional: the API uses `err` (3 letters). |
| `logtype` | `event.category` | Human form: `System`, `Connection`. `orginalLogType` is the lowercase machine form (`system`, `connection`). Use `orginalLogType` for programmatic routing. Yes, `orginalLogType` is spelled without an "i" — verbatim from the API. |
| `descr` | `event.message` | Human-readable. Objects referenced are wrapped in `[square brackets]`, e.g. `[Volume 1]`, `[Storage Pool 1]`, `[/dev/vg1]`, `[LAN 4]`, `[Drive 1]`, `[Active Backup for Business]`. |
| `who` | `event.actor` | Username or `SYSTEM`. |

#### Object-matching strategy

`descr` is free-form English, but a small set of well-known patterns
covers all Scott-requested scenarios. The MP renderer should define
per-event regex or prefix rules and bind the captured identifier to
the target object:

| Pattern fragment | Target object type | Match field |
|---|---|---|
| `on [Storage Pool <N>]`, `on [/dev/vg<N>]` | Storage Pool | `pool_path` = `/dev/vg<N>` (need a lookup table from pool-number text) |
| `on [Volume <N>]`, `[Volume <N>]` | Volume | `display_name` = `Volume <N>` (join to Storage.load_info `volumes[].display_name`) |
| `Disk [...]`, `disk [...]`, `Cache device <N>`, `Drive <N>` | Disk | `name` matches Storage.load_info `disks[].name` (e.g., "Drive 1", "Cache device 2") |
| `[LAN <N>]` | Diskstation (no NIC object in v1) | attach to world object |
| Anything else | Diskstation | attach to world object |

The renderer must not fail the whole cycle if a referenced object
can't be resolved — fall back to attaching the event to the
Diskstation and log a warning.

#### Collection frequency guidance

- **Cumulative feed** (not a queue — does not clear-on-read). Poll
  periodically and track watermark.
- **Polling cadence**: every 5 min aligned with the Diskstation
  collection cycle. Ask for `start=0&limit=200` — 200 rows covers a
  5-min window with margin on a busy box.
- **Watermarking**: keep the latest `(time, descr, who)` hash
  observed in the previous cycle. On next poll, iterate `items` from
  index 0 downwards, stop when the tuple matches. Rows above the
  match are new and become events this cycle.
- **Cold-start**: on first adapter run, ingest **only the 10 newest
  rows** as a backfill floor. Do not emit 4,660 events as a welcome
  gift.
- **Retention**: DSM retains tens of thousands of rows over many
  years (our instance has entries back to 2021). The watermark
  tuple always resolves; no "row rolled off" risk within a normal
  polling interval.

#### Live evidence

Scrubbing sequence (start + finish, pool-level and volume-level):

```
2026/04/06 00:00:03 info  System starts data scrubbing on [/dev/vg1].
2026/04/06 00:00:07 info  System starts filesystem scrubbing on [Volume 1].
2026/04/06 06:23:51 info  System successfully finished filesystem scrubbing on [Volume 1].
2026/04/08 22:28:43 info  System successfully finished data scrubbing on [Storage Pool 1].
```

Note asymmetry: the "starts data scrubbing" message carries the raw
device path (`/dev/vg1`) not the friendly pool name, while the
"finished" message carries the friendly name (`Storage Pool 1`).
The renderer needs both path styles in its Pool lookup.

Backup package lifecycle (Active Backup for Business, package state
transitions observed during a package update):

```
2026/04/15 19:21:15 info  System successfully stopped [Active Backup for Business].
2026/04/15 19:21:28 info  Package [Active Backup for Business] has been successfully updated.
2026/04/15 19:21:28 info  System successfully started [Active Backup for Business].
```

Individual ABB **task completion** events do not appear in
SyslogClient.Log on this instance (the package writes to its own
internal DB, exposed via the `SYNO.ActiveBackup.Report` endpoint
which currently returns empty). The available signal is:
**package-level started / stopped / updated / failed** events.

Download task for DSM update (useful "update is available and
downloaded" signal):

```
2026/02/24 08:18:24 info  Download task for [DSM 7.3.2-86009 Update 1] finished.
2025/10/02 07:08:00 info  Download task for [DSM 7.2.2-72806 Update 4] finished.
```

Security — auto-blocked hosts (this is the "SSH brute-force"
notification that also appears in Security Advisor):

```
2025/11/04 13:33:04 warn  Host [172.27.8.62] was blocked via [SSH].
2025/10/30 14:56:17 warn  Host [172.27.8.62] was blocked via [SSH].
```

Security — failed sign-ins (raw events that Security Advisor
aggregates):

```
2026/04/16 10:42:34 warn  User [claude] from [172.16.3.13] failed to sign in to [DSM] via [password] due to authorization failure.
```

System boot / improper shutdown (useful "restart happened" signal):

```
2026/04/16 08:22:26 info  System started to boot up.
2026/02/13 08:29:36 warn  System booted up from an improper shutdown.
```

Disk overheat (old archival example confirming disk object binding):

```
2023/01/22 00:52:48 warn  Disk overheat: Disk [Cache device 2], serial [S59ANM0T103531T], had reached 70°C, shutdown system now.
2023/01/22 00:52:43 warn  Internal disk Cache device 2, serial [S59ANM0T103531T], [Samsung SSD 970 EVO Plus 1TB] is not within the operating temperature.
```

Package install/start failures (historical):

```
2022/06/09 13:43:21 err  System failed to start [Snapshot Replication].
2021/08/31 21:09:15 err  Failed to repair package [Plex Media Server].
2021/08/31 21:09:15 err  System failed to start [Plex Media Server].
2021/08/31 21:08:27 err  Failed to install package [Plex Media Server].
```

---

### SYNO.Core.Upgrade.Server

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Version**: 4 (minVersion 1, maxVersion 4)
- **Method name**: `check`
- **Auth**: session `_sid`, admin account

#### Response schema (update available)

```json
{
  "success": true,
  "data": {
    "update": {
      "available": true,
      "reboot": "now",
      "restart": "some",
      "rss_result": "success",
      "type": "nano",
      "version": "DSM 7.3.2-86009 Update 3",
      "version_details": {
        "buildnumber": 86009,
        "isSecurityVersion": true,
        "major": 7,
        "minor": 3,
        "micro": 2,
        "nano": 3,
        "os_name": "DSM"
      }
    }
  }
}
```

#### Field mapping (→ MPB event for DSM update availability)

| Source field | MPB event attribute | Notes |
|---|---|---|
| `data.update.available` | (gate) | If `false`, suppress emission. |
| `data.update.version` | `event.message` | Human string, e.g. `"DSM 7.3.2-86009 Update 3"`. |
| `data.update.type` | `event.subcategory` | `nano` = minor point-update. `smart_*` / `critical` values observed in community sources — treat as string tag only. |
| `data.update.version_details.isSecurityVersion` | `event.severity_hint` | `true` → WARNING, `false` → INFORMATION. |
| `data.update.reboot` | `event.detail` | `now` / `no` / `later`. |
| `data.update.restart` | `event.detail` | Services that will restart: `all` / `some` / `none`. |

#### Object-matching

Binds to the **Diskstation** world object. No sub-object context.

#### Collection strategy

- **State-derived event**, not a log row. Poll every 30 min.
- Emit a "DSM update available" event **once** when `available`
  transitions from false → true, or when the `version` string
  changes. Store the last-seen version in the renderer cache.
- Supplement with the SyslogClient "Download task for [DSM ...]
  finished" row for a "update downloaded" event — but the
  `Upgrade.Server.check` call is the authoritative "there is a new
  version" signal and runs even if the box has no Internet access
  for downloads.

#### Live evidence

Captured during this exploration:

```
update.available = true
update.version = "DSM 7.3.2-86009 Update 3"
update.version_details.isSecurityVersion = true
update.reboot = "now"
update.restart = "some"
```

---

### SYNO.SecurityAdvisor.LoginActivity

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Version**: 1
- **Method name**: `list`
- **Auth**: session `_sid`, admin account
- **Parameters**: `limit`, `start` (pagination; confirmed working with `limit=20&start=0`)

#### Response schema

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "create_time": "2025/11/04 13:33:04",
        "severity": "medium",
        "str_id": "brute_force_attack",
        "str_section": "loganalyzer",
        "user": "bkup",
        "str_args": {
          "attempt_count": 10,
          "thresh_minutes": 5,
          "protocol_list": ["SSH"],
          "src_ip_list": ["172.27.8.62"],
          "country_code_list": [],
          "has_any_public_src_ip": false,
          "user": "bkup"
        }
      }
    ],
    "total": 2
  }
}
```

#### Field mapping (→ MPB event for security advisory)

| Source field | MPB event attribute | Notes |
|---|---|---|
| `create_time` | `event.timestamp` | Same `YYYY/MM/DD HH:MM:SS` format. |
| `severity` | `event.severity` | Observed: `medium`. Expected vocabulary (per Security Advisor UI): `low` / `medium` / `high`. Map: low→INFORMATION, medium→WARNING, high→CRITICAL. |
| `str_id` | `event.subcategory` | Machine advisory code. Observed: `brute_force_attack`. Community docs list others: `ddos_attack`, `improper_privilege`, `local_login_anomaly`, `untrusted_ip`. Pass verbatim to MPB. |
| `str_section` | `event.category` | `loganalyzer` (login activity), `file_activity`, `system_activity` — observed from Security Advisor docs; only `loganalyzer` seen on this box. |
| `user` | `event.actor` | Target account name. |
| `str_args.src_ip_list[]` | `event.detail.source_ip` | Join with comma when rendering. |
| `str_args.attempt_count` | `event.detail.attempts` | Integer. |
| `str_args.thresh_minutes` | `event.detail.window_minutes` | Integer. |
| `str_args.protocol_list[]` | `event.detail.protocols` | e.g. `["SSH"]`. |

#### Object-matching

Binds to the **Diskstation** world object. The `user` field does
not resolve to any modeled object; carry it as event metadata only.

#### Collection strategy

- **Cumulative list**, not a queue. Poll every 15 min.
- Watermark on `create_time` (it has second resolution and is
  unique enough for this feed — this box has accumulated 2 entries
  over 6 months).
- On cold-start, emit only the latest row as backfill — these
  advisories are per-incident and not time-sensitive in backfill.

#### Live evidence

Captured directly:

```
create_time=2025/11/04 13:33:04 severity=medium str_id=brute_force_attack
  user=bkup src_ip=172.27.8.62 protocol=SSH attempts=10 window_min=5
create_time=2025/10/30 14:56:18 severity=medium str_id=brute_force_attack
  user=bkdr src_ip=172.27.8.62 protocol=SSH attempts=10 window_min=5
```

Note: the underlying "Host [...] was blocked via [SSH]" appears in
SyslogClient.Log (as a warn). Security Advisor groups multiple
blocks per IP into one advisory with `attempt_count`. We should
emit only the advisory, not both — otherwise the MP double-reports.

## Recommended MPB Events for the Synology MP

The initial events section should register these 8 events. Object
binding is noted per event; where the event attaches to a
non-Diskstation object, the renderer must parse the identifier from
the named field before emitting. If parsing fails, fall back to the
Diskstation.

| # | Event key | Source | Match rule | Target object | Severity |
|---|---|---|---|---|---|
| 1 | `syno_scrub_started` | SyslogClient.Log `keyword=scrubbing` | `descr` matches `^System starts (data|filesystem) scrubbing on \[(.+?)\]\.$` | Storage Pool (if `/dev/vg*` or "Storage Pool *") or Volume (if "Volume *") | INFORMATION |
| 2 | `syno_scrub_finished` | SyslogClient.Log `keyword=scrubbing` | `descr` matches `^System successfully finished (data|filesystem) scrubbing on \[(.+?)\]\.$` | Storage Pool or Volume (same rule) | INFORMATION |
| 3 | `syno_abb_package_transition` | SyslogClient.Log `keyword=Active Backup` | `descr` contains `Active Backup for Business` **and** starts with `System successfully` or `Package`, plus `err`-level matches | Diskstation | INFORMATION / CRITICAL (by `level`) |
| 4 | `syno_dsm_update_available` | Upgrade.Server.check | `data.update.available == true` and version differs from cached | Diskstation | WARNING if `isSecurityVersion`, else INFORMATION |
| 5 | `syno_security_advisory` | SecurityAdvisor.LoginActivity.list | any new `items[]` entry | Diskstation | by `severity` field (low/med/high → INFO/WARN/CRITICAL) |
| 6 | `syno_host_autoblocked` | SyslogClient.Log `keyword=blocked` | `descr` matches `^Host \[(.+?)\] was blocked via \[(.+?)\]\.$` | Diskstation | WARNING |
| 7 | `syno_improper_shutdown` | SyslogClient.Log `keyword=improper` | `descr == "System booted up from an improper shutdown."` | Diskstation | WARNING |
| 8 | `syno_disk_overheat` | SyslogClient.Log `keyword=Disk overheat` | `descr` matches `^Disk overheat: Disk \[(.+?)\], serial \[(.+?)\]` | Disk (match on serial or on name) | CRITICAL |

**Deferred** (nice-to-have; author in a v2 of the events section):

- `syno_link_up` / `syno_link_down` — need a NIC object type first.
- `syno_package_install_failed` — low value outside of admin
  manual ops.
- `syno_abb_task_completed` — blocked until
  `SYNO.ActiveBackup.Report` returns data again (empty on this
  instance; may populate after a task runs). Scott should confirm
  whether to chase this once a live ABB task has executed.

## Toolset Gaps

1. **No access to the DSM notification bell feed.** The canonical
   API backing the DSM UI's notification drawer
   (`SYNO.Core.DSMNotify` / `SYNO.Core.Notification.Sysnotify` /
   `SYNO.Core.PersonalNotification.Event`) rejects every public
   read verb with error 103 from a normal admin session. This is
   the "first-class" notification stream but is **not reachable**.
   The SyslogClient feed is a reasonable substitute — every
   notification we validated (scrub, backup, update, security,
   boot) appears in syslog as a clearly-templated row. Impact:
   low-medium. Document for the user as "MP reads DSM system log,
   not the notification drawer".

2. **No server-side time filter on SyslogClient.Log.** Parameter
   names `time_from`, `start_time`, `datefrom`, `from` are silently
   accepted and silently ignored. The MP must do client-side time
   watermarking. This is fine for a 5-minute poll cadence, but
   prevents efficient historical backfill. Impact: low.

3. **Hyper Backup & Snapshot Replication not installed on this
   NAS**, so their package-specific logs could not be probed. The
   SyslogClient feed's package-level events (`System successfully
   started [Snapshot Replication]`, `System failed to start
   [Snapshot Replication]`, `Package [Hyper Backup] has been
   successfully updated`) are the only universally available
   backup-event signals without those packages. Impact: medium —
   if a user runs Hyper Backup and expects per-job completion
   notifications, we currently only emit package-lifecycle events.
   Follow-up: explore `SYNO.Backup.App.*` on a box with Hyper
   Backup installed.

4. **ActiveBackup task-level reports return empty** on this
   instance even though 2 tasks are defined. Either reports are
   pruned (retention setting) or the account lacks per-task report
   read permission. `SYNO.ActiveBackup.Report.list` with a valid
   `task_id` still returns `{reports: [], total: 0}`. Follow-up
   needed to verify schema. Does not block the initial event set.

## Notes for the MP Author

- Every event ultimately attaches to the Diskstation as a fallback.
  Prefer narrower binding where the `descr` parse is deterministic.
- The MP renderer needs a simple **object-name lookup table** built
  from the Storage collection so that `[Volume 1]` and `[Storage
  Pool 1]` and `[/dev/vg1]` all resolve to their respective object
  identifiers. Storage.load_info already returns these — the
  lookup is `{display_name, pool_path, vol_path, /dev/vg<num>}` →
  internal identifier.
- Watermarking for SyslogClient.Log: the renderer should dedup on
  the tuple `(time, level, logtype, descr, who)` to be bullet-proof
  — events with the same human text can occur milliseconds apart
  (we observed six `Domain [INT] is online.` rows in the same
  second after a NIC link-up).
- Do not poll at a higher cadence than 5 min. SyslogClient.Log
  scans the server log files synchronously; the call takes
  noticeable wall time at high `limit` values.
