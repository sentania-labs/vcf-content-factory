# Design Artifact: Synology DSM Management Pack v1

## Original Request

Build a management pack capability for the VCF Content Factory, using the
Synology DS1520+ NAS MP as the learning project. Scott has an existing
bare-bones MP (`sentania/Aria-Operations-DSM-Management-Pack`, build 8) with
4 object types, 9 requests, 1 relationship, and session auth working. Evolve
it into a full-featured MP while building the factory tooling.

## Design revisions

- **2026-04-16** — incorporated Phase 4.1 sanity-check decisions: auth switched
  from SESSION to CUSTOM cookie-header (aligned with Scott's build-8);
  relationships gained explicit `child_expression` / `parent_expression`
  join predicates; events split into two tiers (threshold alerting migrates
  to factory symptoms/alerts, DSM notification events remain as in-MP MPB
  events pending 4.1.7); name expressions collapsed to single-metric
  passthrough for v1. See sections below for details.

## Interview Answers

| Question | Answer |
|---|---|
| Monitoring scope | Storage + compute + UPS + Docker |
| iSCSI LUNs | First-class objects (for ESXi correlation) |
| Network interfaces | Metrics on Diskstation (not separate objects) |
| Disk parent | Dual relationship: child of Diskstation AND Storage Pool |
| Events | Two-tier: threshold conditions via factory symptoms/alerts, DSM notification events via MPB |
| Bundled content | Basic dashboard in .pak + rich factory dashboard separately |

## Object Model

```
Synology Diskstation (world object, keyed by serial)
|
+-- Storage Pool          1:N   (keyed by pool_id + pool_path)
|   +-- Volume            1:N   (keyed by volume_id + volume_path)
|   |   +-- iSCSI LUN    1:N   (keyed by lun_uuid)
|   +-- Disk              1:N   (keyed by disk_id) <-- also child of Diskstation
|
+-- Disk                  1:N   (dual parent: Diskstation + Storage Pool)
+-- Docker Container      1:N   (keyed by container_name)
+-- UPS                   0:1   (keyed by model)
```

### Relationships (7)

Each relationship now carries an explicit **join predicate** — a
`child_expression` / `parent_expression` metric pair whose values must match
for the MPB engine to link a child instance to its parent instance at
collection time. This is the MPB wire-format reality (see
`context/mp_schema_vs_existing_mp.md` §5) — relationships are value joins,
not bare parent/child edges.

| # | Parent | Child | child_expression (child metric) | parent_expression (parent metric) | Source evidence |
|---|---|---|---|---|---|
| 1 | Synology Diskstation | Storage Pool | `(adapter-instance trivial match)` | `(adapter-instance trivial match)` | `synology-storage.md` §"Identifier Chains" — all pools belong to the one NAS; no explicit join field needed. Implementation note: for adapter-instance-scoped joins the convention is to match child and parent on the Diskstation's `serial` (world object identifier). mp-author to confirm with tooling whether a degenerate always-match predicate is supported; otherwise emit both sides as the Diskstation `serial` metric reference. |
| 2 | Storage Pool | Volume | Volume `pool_path` | Storage Pool `pool_path` | `synology-storage.md` Volume field table (`pool_path` noted as join key) and §"Identifier Chains" — `volumes[].pool_path == storagePools[].pool_path`. Direct equality, no transformation. |
| 3 | Volume | iSCSI LUN | iSCSI LUN `location` | Volume `volume_path` (`vol_path`) | `synology-iscsi.md` §"Identifier Chains" + `synology-storage.md` — LUN `location: "/volume1"` matches Volume `vol_path: "/volume1"`. Both sides carry the leading `/`, so this is a direct string equality in v1. **Normalization note**: if any DSM firmware revision returns `location` without the leading slash (observed on some builds), mp-author should flag this for tooling to add a `regex` strip on the child_expression rather than silently mismatching. |
| 4 | Storage Pool | Disk | Disk `used_by` | Storage Pool `pool_id` | `synology-storage.md` Disk field table (`used_by` noted as join key) and §"Identifier Chains" — `storagePools[].disks[]` array lists disk IDs, AND `disks[].used_by` carries the pool ID (e.g., `reuse_1`) for the pool that owns the disk. `used_by` is the cleaner single-value join; the `disks[]` array form would require iteration on the parent side. |
| 5 | Synology Diskstation | Disk (dual parent) | Disk `disk_id` | Diskstation `serial` | `synology-storage.md` §"Identifier Chains" — "all disks are direct children of the Diskstation". No field on the disk references the NAS serial directly, so the predicate is an adapter-instance-scoped join: all disks belong to the one NAS. Same implementation caveat as relationship #1 — mp-author to confirm wire-format support for adapter-instance-trivial matches; fall back to joining on the Diskstation's `serial` (parent side) and a synthetic adapter-instance identifier on the child side if needed. **Dual-parent pattern is supported** per Rubrik MP reference (`mp_schema_vs_existing_mp.md` §5c). |
| 6 | Synology Diskstation | Docker Container | (adapter-instance trivial match) | (adapter-instance trivial match) | `synology-docker.md` §"Identifier Chains" — "all containers are direct children of the Diskstation; no explicit join field needed". Same implementation pattern as #1 and #5. |
| 7 | Synology Diskstation | UPS | (adapter-instance trivial match) | (adapter-instance trivial match) | `synology-ups.md` §"Identifier Chains" — "0:1 relationship; direct child of Diskstation; no explicit join field needed". Same pattern; additionally UPS object is only instantiated when `usb_ups_connect: true` so the parent always has at most one UPS child. |

**Open question for mp-author (task 4.1.8)**: the MPB wire format requires
every relationship to have a non-null `childExpression` / `parentExpression`.
For the four "adapter-instance trivial match" cases (#1, #5, #6, #7) there is
no single shared field between child and parent. Two resolution paths — pick
one once the renderer story is clearer:

- **Option A — synthetic `@@@adapterInstance` identifier**: emit a
  metric/attribute that resolves to the adapter-instance ID on both sides.
  Need to confirm MPB supports this; no reference MP demonstrates it
  explicitly.
- **Option B — synthesize a constant match field per object type**: author a
  derived PROPERTY metric (e.g., `diskstation_serial` copied onto every
  child) on each child object type, joining to the Diskstation's `serial`.
  Costs one extra property per child but is wire-format-valid and
  human-auditable.

Flag for Phase 4.1.8 — mp-author should raise this to the tooling agent
before authoring to avoid a build-stall.

## Authentication

**Model: CUSTOM credentialType with cookie-header session.** This is the
pattern Scott's build-8 MP uses and that the Postman collection
independently confirms (see `context/mp_schema_vs_existing_mp.md` §2b, §3e).
The earlier design assumed SESSION type with `format=sid` / `data.sid`
body-token extraction / `_sid` query-param injection; that is a different
(also valid) DSM auth mode Scott experimented with but did NOT ship.

### v1 auth wiring

- **credentialType**: `CUSTOM` (two arbitrary fields, not the loader's
  current SESSION/BASIC/TOKEN/NONE vocab)
- **Credential fields**: `username` (label "username", not sensitive),
  `passwd` (label "passwd", sensitive). Field labels are load-bearing —
  they determine the `${authentication.credentials.<label>}` variable name
  used elsewhere in the document.
- **Login**: `GET /webapi/auth.cgi` with `api=SYNO.API.Auth`, `version=3`,
  `method=login`, `session=FileStation`, `format=cookie`,
  `account=${authentication.credentials.username}`,
  `passwd=${authentication.credentials.passwd}`. Params are emitted as an
  ordered list of `{key, value}` objects (not a dict).
- **Session variable extraction**: from HTTP response **header**
  `Set-Cookie` (not JSON body), bound to
  `${authentication.session.set_cookie}`. Extraction `location: HEADER`.
- **Token injection**: via `globalHeaders` — a request header literally named
  `"id"` with `type: CUSTOM` and
  `value: ${authentication.session.set_cookie}`. Not `Cookie`, not
  `_sid` query param.
- **Logout**: `DELETE /webapi/auth.cgi` (not GET) with `api=SYNO.API.Auth`,
  `version=3`, `method=logout`. No `session` param — the cookie header alone
  identifies which session to release.
- **Base path**: `webapi` (no leading slash); every request path is relative
  (`entry.cgi`, `auth.cgi`). Earlier design's `/webapi/entry.cgi` absolute
  paths are wrong.

**Why this choice**: aligned with Scott's working build-8 MP and Postman
collection, which are byte-for-byte consistent. Shipping the SESSION/sid
pattern instead would fork from the one known-working example with no
offsetting benefit.

**TOOLSET GAP**: the factory loader's `VALID_AUTH_TYPE` does not include
`CUSTOM`. Tooling agent must extend the schema in Phase 4.1.5 before
mp-author can write the YAML; this design presumes a `type: CUSTOM` (or
equivalent) option exists on the loader when 4.1.8 starts.

## Metrics by Object Type

### Synology Diskstation (world)

- Identifier: `serial`
- **Name expression (v1)**: single-metric passthrough — `model`
  (e.g. "DS1520+"). Single-metric choice keeps the renderer aligned with
  every reference MP observed; composites like `"${model} (${hostname})"`
  have no verified wire format yet. See "Name expressions" section.

Existing (33 from current MP):
- CPU: Clock Speed, Cores, Family, Series, Vendor
- System: Firmware Date/Ver, Model, RAM Size, Serial, Sys Temp, Hostname
- NTP: Enabled, Server, Time Zone
- CPU Load: 1/5/15min, User, System, Other
- Memory: Avail Real, Total Real, Real Usage, Cached, Buffer
- Swap: Usage, Total, Avail, Si Disk, So Disk
- Uptime (currently PROPERTY STRING -- should be METRIC NUMBER from SYNO.DSM.Info)

New:
- memory_usage_pct (METRIC) -- direct from `data.memory.real_usage`
- cpu_total_load (METRIC) -- calculated: user + system
- fan_status (PROPERTY) -- from SYNO.Core.Hardware.FanSpeed (`cool_fan`)
- net_rx_bytes (METRIC) -- aggregated from Utilization `network[]`
- net_tx_bytes (METRIC) -- aggregated from Utilization `network[]`
- nic_count (PROPERTY) -- derived from SYNO.Core.Network.Interface length

### Storage Pool

- Identifier: `pool_id` + `pool_path`
- **Name expression (v1)**: single-metric passthrough — `pool_path`
  (e.g. "/pool/reuse_1"). Rationale: `pool_path` is unique per pool,
  always populated, and mirrors how Scott's build-8 MP picks the `ID`
  metric for pool naming. Alternative `num_id` (1, 2, ...) is terser but
  less human-meaningful on multi-pool NAS. Composite
  `"Pool ${num_id} (${device_type})"` is deferred to a future revision
  once composite names are verified to render.

Existing (6): Device Type, ID, Num ID, Pool Path, Total, Used
New: usage_pct (METRIC), status (PROPERTY), raid_type (PROPERTY), disk_count (PROPERTY)

### Volume

- Identifier: `volume_id` + `volume_path` (`vol_path`)
- **Name expression (v1)**: single-metric passthrough — `display_name`
  (e.g. "Volume 1"). Matches Scott's build-8 choice.

Existing (10): Description, Display Name, Fs Type, Pool Path, RAID Type,
Size Free Byte, Size Total Byte, Status, Volume ID, Volume Path
New: usage_pct (METRIC), io_read_bytes (METRIC), io_write_bytes (METRIC),
io_read_access (METRIC, IOPS), io_write_access (METRIC, IOPS),
utilization (METRIC, %)

**Note**: IO metrics come from `SYNO.Core.System.Utilization` `data.space.volume[]`,
joined by `display_name` (volume1) ↔ `vol_path` (/volume1) with a leading-
slash strip. Confirmed field names are `read_byte`/`write_byte` (throughput)
and `read_access`/`write_access` (IOPS equivalent), not the original
`read_iops`/`write_iops`.

### iSCSI LUN (NEW)

- Identifier: `lun_uuid`
- **Name expression (v1)**: single-metric passthrough — `name`
  (e.g. "vcf-lab-wld01-cl01"). Matches the natural display key.

- name (PROPERTY), uuid (PROPERTY), size (METRIC), location (PROPERTY),
  type_str (PROPERTY)
- IO (from `SYNO.Core.System.Utilization` `data.lun[]`):
  read_iops, write_iops, read_throughput, write_throughput,
  read_avg_latency, write_avg_latency, total_iops, total_throughput,
  total_io_latency (all METRIC). Join on `lun_name`/`uuid`.

### Disk

- Identifier: `disk_id` (e.g. "sata1", "nvme0n1")
- **Name expression (v1)**: single-metric passthrough — `name`
  (e.g. "Drive 1"). Matches Scott's build-8 choice.

Existing (11): Device, Firm, Model, Name, Serial, Size Total, Slot ID,
Smart Status, Used By, Vendor, Wcache Force Off
New: temp (METRIC), unc_sectors (METRIC), remain_life (METRIC),
io_read_bytes (METRIC), io_write_bytes (METRIC),
io_read_access (METRIC, IOPS), io_write_access (METRIC, IOPS),
utilization (METRIC, %), disk_type (PROPERTY)

**Note**: `remain_life` is -1 for HDDs (spec-level meaningless for spinning
media); only meaningful on SSD/NVMe. `unc` (uncorrectable sectors) is a
lifetime counter, not a rate.

### Docker Container (NEW)

- Identifier: `container_name`
- **Name expression (v1)**: single-metric passthrough — `container_name`
  (e.g. "immich_server"). Identifier and display key are identical on DSM.

- name (PROPERTY), container_id (PROPERTY), image (PROPERTY),
  status (PROPERTY), state (PROPERTY), health (PROPERTY),
  started_at (PROPERTY), is_running (PROPERTY), oom_killed (PROPERTY),
  exit_code (METRIC)
- Resource (from SYNO.Docker.Container.Resource): cpu_usage (METRIC, %),
  memory_usage (METRIC, bytes), memory_usage_pct (METRIC, %).
- Compose metadata: compose_project, compose_service (PROPERTY).
- Uptime derived from `State.StartedAt` (ISO-8601); no direct uptime field.

### UPS (NEW)

- Identifier: `model`
- **Name expression (v1)**: single-metric passthrough — `model`
  (e.g. "Back-UPS 1500"). Only one UPS per NAS, so uniqueness holds.

- model (PROPERTY), vendor (`manufacture`, PROPERTY), status (PROPERTY)
- battery_charge (`charge`, METRIC, %), runtime (METRIC, seconds)
- ups_enabled (`enable`, PROPERTY), ups_connected (`usb_ups_connect`, PROPERTY),
  ups_mode (PROPERTY), delay_time (PROPERTY), shutdown_device (PROPERTY)

**Note**: create UPS object only when `usb_ups_connect: true`. No `ups_load`
field is available from the REST API; load would require SNMP (out of scope
for v1).

## Name expressions

**v1 uses single-metric passthrough for every object type** — one metric per
object, its string value is the display name, emitted as a single-part
`nameMetricExpression` with `originType: METRIC`. This matches every
reference MP observed (including Scott's build-8) and is the one pattern
we can confidently render.

Multi-metric composites (e.g. `"${model} (${hostname})"`) are plausibly
supported by MPB via interleaved `@@@MPB_QUOTE <part-id> @@@MPB_QUOTE`
segments interspersed with literal text, but no reference MP demonstrates
this and live verification is still pending. When we can test a composite
against a real instance, v2 of this design can revisit.

Single-metric name expression per object type:

| Object type | Name metric | Rationale |
|---|---|---|
| Synology Diskstation | `model` | e.g. "DS1520+". Static, unique per NAS. |
| Storage Pool | `pool_path` | e.g. "/pool/reuse_1". Unique per pool; more human-friendly than `pool_id` alone. |
| Volume | `display_name` | e.g. "Volume 1". Matches Scott's build-8. |
| iSCSI LUN | `name` | e.g. "vcf-lab-wld01-cl01". Matches natural LUN naming. |
| Disk | `name` | e.g. "Drive 1". Matches Scott's build-8. |
| Docker Container | `container_name` | e.g. "immich_server". Identifier doubles as display. |
| UPS | `model` | e.g. "Back-UPS 1500". 0:1 per NAS. |

## Events

v1 splits the original event list into two tiers based on the MPB wire-
format realities uncovered in `context/mp_schema_vs_existing_mp.md` §6:

- **Threshold conditions** (compare a metric/property against a constant and
  emit an alert) are *not* how MPB events work. Those are alert-threshold
  DSL patterns, which in the VCF Content Factory belong to `vcfops_symptoms` /
  `vcfops_alerts` — standalone symptom and alert definitions that reference
  the MP's adapter kind and resource kinds after the MP is installed.
- **MPB events** pull event records from an API list endpoint and
  materialize each record as a VCF Ops event, binding it to a discovered
  object via value-join matchers. For DSM this means surfacing the
  notification/log/security feeds — data scrubbing started/stopped, backup
  completed, DSM out-of-date, security advisory published, etc.

### Tier 1 — threshold conditions (migrated to factory symptoms/alerts)

All 10 events from the original design **move out of the MP entirely** and
are authored via the factory's existing symptom-author and alert-author
pipelines. They install alongside the MP (same bundle), referencing the
MP's adapter kind (`mpb_synology_dsm`) and the resource kinds it introduces.

| Original event | Severity | Condition | Object kind | Status |
|---|---|---|---|---|
| Disk Failure | CRITICAL | smart_status=failing OR status=crashed | Disk | **MIGRATED → factory symptom + alert** |
| RAID Degraded | CRITICAL | status=degraded OR crashed | Storage Pool | **MIGRATED → factory symptom + alert** |
| Volume Critical | CRITICAL | usage_pct > 95 | Volume | **MIGRATED → factory symptom + alert** |
| Volume Low | WARNING | usage_pct > 85 | Volume | **MIGRATED → factory symptom + alert** |
| High Temp | CRITICAL | sys_temp > 70 | Diskstation | **MIGRATED → factory symptom + alert** |
| Elevated Temp | WARNING | sys_temp > 60 | Diskstation | **MIGRATED → factory symptom + alert** |
| UPS On Battery | CRITICAL | status=OB or LB | UPS | **MIGRATED → factory symptom + alert** |
| Fan Failure | CRITICAL | fan_status=failed or stopped | Diskstation | **MIGRATED → factory symptom + alert** |
| Disk UNC | WARNING | unc_sectors > 0 | Disk | **MIGRATED → factory symptom + alert** |
| SSD Life Low | WARNING | remain_life < 20 | Disk | **MIGRATED → factory symptom + alert** |

These are authored in Phase 4.2+ via the existing symptom-author / alert-
author workflow, not by mp-author. No MPB-side work required.

### Tier 2 — DSM notification events (remain as MPB events)

High-value operational events that DSM emits natively through its
notification/log/security feeds. These stay in the MP as API-pull MPB
events — one request against a DSM notification/log/security endpoint,
objects materialized per event record, bound back to the Diskstation (or
a more specific object where possible) via `eventMatchers`.

**Endpoints pending api-cartographer task 4.1.7** — the specific
`SYNO.Core.Notification.*` / `SYNO.Core.SyslogClient` / security-advisory
endpoints that surface these events are being mapped in parallel. The
table below enumerates the events we want to surface; mp-author will bind
them to concrete endpoint paths once 4.1.7 lands.

| Event | Expected source API (TBD) | Target object | Notes |
|---|---|---|---|
| Data scrubbing started | DSM notification log | Storage Pool (or Diskstation) | Per-pool scrub; bind via pool name/id if emitted |
| Data scrubbing stopped | DSM notification log | Storage Pool (or Diskstation) | Pair with start event |
| Backup completed | DSM notification log | Diskstation | Hyper Backup / Snapshot Replication |
| DSM out of date | DSM security/update feed | Diskstation | Correlate with `upgrade_ready` property |
| Security advisory published | DSM security-advisory feed | Diskstation | Broadcom-style advisory feed if DSM exposes one |

Everything in this tier is **TBD pending api-cartographer 4.1.7**. mp-author
should not block on Tier 2 for the initial 4.1.8 build — if the 4.1.7 map
isn't ready, ship v1 with MPB `events: []` and add Tier 2 in a v1.1 revision
once endpoints are confirmed.

**Wire-format reminder** (for mp-author, from §6 of the sanity-check doc):
each MPB event carries `listId`, `requestId`, `message` expression (regex-
extractable from an attribute), `severity` expression + `severityMap`,
`eventMatchers` (object-binding predicates). Rubrik's MP is the only
reference example of a populated event block.

## Agent Architecture

Three new agents for MP development:

1. **api-cartographer** -- general-purpose REST API explorer for unknown APIs
2. **mp-designer** -- object model designer (wizard + plan mode mockup)
3. **mp-author** -- YAML source spec author

Workflow: api-cartographer -> mp-designer -> USER APPROVAL -> mp-author -> tooling -> qa

## Key Risks

1. **Dual-parent relationships** (Disk with parents Diskstation + Storage
   Pool) — schema supports two relationship rows with the same child
   (proven by Rubrik MP's dual-parent Rubrik Job), but the
   adapter-instance-trivial-match predicate pattern for the Diskstation
   parent side still needs mp-author + tooling alignment (see open question
   under Relationships).
2. **Per-object IO mapping from Utilization response** requires cross-
   request identifier matching — Volume IO joins on `display_name` ↔
   `vol_path` (with slash strip), Disk IO joins on `device` ↔ `disk_id`,
   LUN IO joins on `lun_name`/`uuid` ↔ LUN list `name`/`uuid`. MPB's
   cross-request merge capability for `dataModelList` bindings needs
   verification during rendering.
3. **Docker/UPS APIs** may not be available if the Docker package isn't
   installed (error 102) or if no UPS is connected. v1 handles no-UPS
   gracefully (object not instantiated); Docker API errors should short-
   circuit container collection without failing the entire cycle.
4. **Auth schema extension** — the factory loader's `VALID_AUTH_TYPE` must
   gain `CUSTOM` (or equivalent) before mp-author can write the YAML. This
   is Phase 4.1.5 work, a blocker for 4.1.8.
5. **Adapter-instance-trivial relationship predicates** (relationships
   #1, #5, #6, #7) have no single shared metric between child and parent
   at the API level. Resolution is one of the two options in the
   Relationships section; decision needed before 4.1.8 authoring begins.
6. **Tier 2 events depend on api-cartographer 4.1.7** — if the
   notification/log endpoint map isn't ready when 4.1.8 starts, ship v1
   with MPB `events: []` and add in v1.1.
7. **Composite name expressions** are unverified against a real MPB
   instance; v1 intentionally ducks the issue by using single-metric
   passthroughs only.
