# Design Artifact: Synology DSM Management Pack (v2 — Strategy C)

**Status.** APPROVED 2026-04-21. Supersedes all prior iterations of this
file (v1 Option A/C chaining design, 12-axis framework review, multi-
request enrichment sketches). Those materials were design-time exploration
that led to the decisions below; the final architecture captured here is
what `mp-author` builds against.

**Target MP filename:** `managementpacks/synology_nas.yaml`
**Adapter kind:** `mpb_synology_nas`
**Bundled content:** none in v2 (factory dashboards ship separately).

---

## Original Request

Build a management pack for the VCF Content Factory, using a Synology
DS1520+ NAS as the learning project. Evolve Scott's hand-built reference
MP (`sentania/Aria-Operations-DSM-Management-Pack`, build 8 — 4 objects,
9 requests, 1 relationship) into a full-featured MP while the factory
tooling matures alongside.

## Decision history (compact)

| Date | Decision |
|---|---|
| 2026-04-18 | Grammar settled on Option C (top-level `requests:` + explicit `metricSets:`). Implementation is tooling's; authoring uses this grammar going forward. |
| 2026-04-18 | Auth settled on `cookie_session` preset with explicit flow-based grammar. |
| 2026-04-21 | Architecture settled on **Strategy C** — sidecar world object + rich peer relationships. Rejected Strategy A (Rubrik's dual-root pattern) because same-name root-level duplication is unusable; rejected Strategy B (Unifi's no-root-metrics pattern) because Synology exposes real root-device metrics. |
| 2026-04-21 | iSCSI Targets deferred from v2 (properties on LUN if we need them later). NFS Share included **pending cartographer pass on `SYNO.Core.Share`** — see §"Gaps before mp-author". |

---

## Strategy C — the architectural essence

Three design principles drive everything below.

1. **The world object is a sidecar**, not a tree parent.
   The Diskstation (`is_world: true`) carries CPU/memory/temp/uptime/model/
   serial. It has **no explicit `relationships:` to any child**. Its
   display name is deliberately distinct from the adapter instance name
   (e.g., `"System Health"`) to avoid the same-name root-level duplication
   failure mode.

2. **Peer objects use explicit `field_match` relationships.**
   Pool/Volume/Disk/SSDCache/LUN/Share all discover from their own list
   requests, then join by value to their peer parents. This is the
   dominant dual-parent peer graph pattern — exactly how VMs appear
   under both Host and Resource Pool in vSphere content.

3. **Chained metricSets are for same-object enrichment only.**
   Volume IO comes from `SYNO.Core.System.Utilization` as a chained
   metricSet on Volume, so the IO metrics live on the same Volume
   instance as the capacity metrics. No new object type needed.

See [`context/mpb_relationships.md`](../context/mpb_relationships.md) for
the full design-pattern reasoning. Everything below is a concrete
application of those patterns.

---

## Object Model

```
Adapter Instance (auto-materialized by MPB; implicit parent of everything)
│
├── Synology Diskstation    (is_world: true — SIDECAR)
│   └── 3 metricSets: system, filestation, utilization
│       (~17 root-device metrics — NO children edges from here)
│
└── [peer graph, all objects parent the Adapter Instance implicitly]
    │
    ├── Storage Pool   (list, from load_info.storagePools[])
    │     │
    │     ├──(field_match pool_path == pool_path)──→  Volume
    │     ├──(field_match id        == mountedPool)──→ SSDCache
    │     └──(field_match id        == used_by)────→  Disk     [sata*]
    │
    ├── SSDCache       (list, from load_info.sharedCaches[] + ssdCaches[])
    │     │
    │     └──(field_match id == used_by)──────────→  Disk     [nvme*]
    │
    ├── Volume         (list, from load_info.volumes[])
    │     │
    │     ├──(field_match vol_path == location)──→ iSCSI LUN
    │     └──(field_match vol_path == vol_path)──→ NFS Share    [§gap]
    │
    ├── Disk           (list, dual-parented by Pool + SSDCache — PEER LEVEL, NORMAL)
    ├── iSCSI LUN      (list)
    └── NFS Share      (list — pending SYNO.Core.Share cartography)
```

**Dual-parent decisions.**
- Disk has two parents (Pool + SSDCache) at **peer level** — normal, useful
  navigation. See `mpb_relationships.md` §2.
- The Diskstation world object deliberately does NOT parent anything.
  Implicit adapter-instance parentage gives every object its root edge for
  free; explicit edges from Diskstation would duplicate-render the tree.

---

## Relationships (full list, 7 explicit)

| # | Parent (key) | Child (key) | Scope | `parent_expression` | `child_expression` | Join semantics |
|---|---|---|---|---|---|---|
| 1 | `storage_pool` | `volume` | `field_match` | `pool_path` | `pool_path` | Direct string equality; both sides equal the bare pool id (e.g., `reuse_1`) |
| 2 | `storage_pool` | `ssd_cache` | `field_match` | `id` | `mounted_pool` | Direct string equality; SSDCache `mountedPool` field carries parent pool id |
| 3 | `storage_pool` | `disk` | `field_match` | `id` | `used_by` | Direct string equality on **SATA disks** — their `used_by` value is the pool id |
| 4 | `ssd_cache` | `disk` | `field_match` | `id` | `used_by` | Direct string equality on **NVMe disks** — their `used_by` value is the cache id (e.g., `shared_cache_1`) |
| 5 | `volume` | `iscsi_lun` | `field_match` | `vol_path` | `location` | Both sides carry the leading `/` (e.g., `/volume1`) |
| 6 | `volume` | `nfs_share` | `field_match` | `vol_path` | `vol_path` | **Unverified — pending SYNO.Core.Share cartography** |
| — | `diskstation` | (anything) | — | — | — | **Deliberately absent.** Implicit adapter-instance edge carries every child. |

**Dual-parent note for Disk (relationships #3 and #4):** each disk has
exactly one `used_by` value, so at any given collection cycle each disk
belongs to exactly one of (Pool or SSDCache). The peer-level dual-parent
*capability* exists in MPB and is the expected pattern; no disk actually
lives under both simultaneously in the data, but the MP must support both
join paths so that both sata and nvme disks display correctly in their
respective parent trees.

---

## Requests

All responses use `response_path: "data"` so metric paths strip the outer
`data` key.

| # | Request name | API | Purpose | Consumers |
|---|---|---|---|---|
| 1 | `system` | `SYNO.Core.System version=3 method=info` | Diskstation system metadata (model, serial, CPU, RAM, temp) | Diskstation |
| 2 | `filestation` | `SYNO.FileStation.Info version=1 method=get` | Diskstation hostname | Diskstation |
| 3 | `utilization` | `SYNO.Core.System.Utilization version=1 method=get` | Root-device CPU/mem + per-volume IO | Diskstation, Volume (chained) |
| 4 | `load_info` | `SYNO.Storage.CGI.Storage version=1 method=load_info` | All storage topology: pools, volumes, disks, sharedCaches, ssdCaches | Storage Pool, Volume, Disk, SSDCache |
| 5 | `iscsi_luns` | `SYNO.Core.ISCSI.LUN version=1 method=list` | iSCSI LUN metadata | iSCSI LUN |
| 6 | `nfs_shares` | `SYNO.Core.Share version=1 method=list` **[unverified]** | NFS share metadata | NFS Share (pending cartography) |

**Total per-cycle requests:** 5 on the normal path (request #6 deferred
until cartographer run lands). The Utilization chain fires the
`utilization` request once per Volume row — so at steady state with N
volumes, that's `5 + N` HTTP calls per cycle.

**Pagination:** none observed on any of these endpoints; Synology returns
the full list in a single response. Flag as a collection-strategy
assumption — if a customer has a much larger NAS, we may need to revisit.

---

## Object Type Details

### 1. Synology Diskstation (world, sidecar)

```yaml
- name: "Synology Diskstation"
  key: diskstation
  type: INTERNAL
  icon: "media-changer.svg"
  is_world: true

  identifiers:
    - key: serial
      source: "metricset:system.serial"

  identity:
    tier: system_issued
    source: "metricset:system.serial"

  name_expression:
    parts:
      - metric: model
      # Optional future enhancement: add literal " System Health" for clarity
      # once multi-part name expressions are wire-tested end-to-end.

  metricSets:
    - {from_request: system,       list_path: ""}
    - {from_request: filestation,  list_path: ""}
    - {from_request: utilization,  list_path: ""}
```

**Metrics (~20 total).** From `system`: model (prop), serial (prop, ID),
firmware_ver (prop), firmware_date (prop), up_time (prop), cpu_cores
(prop), cpu_clock_speed (prop), cpu_family (prop), cpu_series (prop),
cpu_vendor (prop), ram_size (prop, GB), sys_temp (metric, °C),
time_zone_desc (prop), enabled_ntp (prop), ntp_server (prop).
From `filestation`: hostname (prop). From `utilization.cpu`: load_1min,
load_5min, load_15min, cpu_other_load, cpu_system_load, cpu_user_load
(all METRIC, %). From `utilization.memory`: memory_size, memory_available
(METRIC, bytes), memory_cached, memory_swap_used (METRIC, bytes).

### 2. Storage Pool (list)

```yaml
- name: "Storage Pool"
  key: storage_pool
  type: INTERNAL
  icon: "data-cluster.svg"
  is_world: false

  identifiers:
    - key: id
      source: "metricset:load_info.id"

  name_expression:
    parts:
      - metric: id

  metricSets:
    - from_request: load_info
      primary: true
      list_path: "storagePools.*"
```

**Metrics (~10).** From `load_info.storagePools[]`: id (prop, ID),
pool_path (prop — join field for Volume), num_id (prop), device_type
(prop — e.g., `raid_5`), status (prop), size.total (metric, bytes),
size.used (metric, bytes), size.total_device (metric, bytes), disks[]
(count-style property derivation deferred), raid_type (prop).

### 3. Volume (list, with chained IO enrichment)

```yaml
- name: "Volume"
  key: volume
  type: INTERNAL
  icon: "hard-drive-disks.svg"
  is_world: false

  identifiers:
    - key: vol_path
      source: "metricset:load_info.vol_path"

  name_expression:
    parts:
      - metric: vol_path

  metricSets:
    # PRIMARY — capacity + metadata
    - from_request: load_info
      primary: true
      list_path: "volumes.*"
    # CHAINED — per-volume IO from the utilization endpoint
    - from_request: utilization
      as: volume_io
      chained_from: load_info
      list_path: "space.volume.*"
      bind:
        - name: volume_id
          from_attribute: device
      # Note: the filter mechanism tested 2026-04-21 shows resource=space +
      # interfaces.space=[<device>] is the only working filter. Authors
      # must wire this into the request's params. See §"Request params".
```

**Metrics (~12).** Capacity (from `load_info`): vol_path (prop, ID),
pool_path (prop — join to Pool), num_id (prop), size_free_byte (metric),
size_total_byte (metric), status (prop), raid_type (prop), cache
(prop, object → `cache.id` for SSDCache join flagged as future enrichment),
fs_type (prop), atime_option (prop). IO (chained from `utilization`):
read_access (metric, IOPS), write_access (metric, IOPS), read_byte
(metric, B/s), write_byte (metric, B/s), utilization (metric, %).

### 4. Disk (list, dual-parented at peer level)

```yaml
- name: "Disk"
  key: disk
  type: INTERNAL
  icon: "storage.svg"
  is_world: false

  identifiers:
    - key: id
      source: "metricset:load_info.id"

  name_expression:
    parts:
      - metric: id

  metricSets:
    - from_request: load_info
      primary: true
      list_path: "disks.*"
```

**Metrics (~12).** id (prop, ID — e.g., `sata1`, `nvme0n1`), name (prop),
device (prop), model (prop), firm (prop — firmware version), vendor
(prop), serial (prop), size_total (metric, bytes), slot_id (metric),
smart_status (prop), used_by (prop — **join field for BOTH Pool and
SSDCache**), temp (metric, °C). `remain_life.value` as
`remain_life_pct` (metric, %) — drill through the object; see
`synology-storage.md` quirks.

### 5. SSDCache (list)

```yaml
- name: "SSDCache"
  key: ssd_cache
  type: INTERNAL
  icon: "cache.svg"   # confirm icon availability with MPB
  is_world: false

  identifiers:
    - key: id
      source: "metricset:load_info.id"

  name_expression:
    parts:
      - metric: id

  metricSets:
    - from_request: load_info
      primary: true
      # IMPORTANT: The SSDCache object draws from TWO sub-paths of the
      # same request response: sharedCaches[] (physical RAID of NVMes)
      # and ssdCaches[] (volume-allocated caches). They represent distinct
      # cache kinds and both have `id`, both expose `mountedPool`/equivalent.
      # v2 authoring decision: use `sharedCaches.*` as the primary list
      # (matches the NVMe-disk-parent case). If customer SSD cache layout
      # differs, revisit under a v3 cartographer pass.
      list_path: "sharedCaches.*"
```

**Metrics (~6).** id (prop, ID), mounted_pool (prop — ↔ Pool.id; named
`mountedPool` in API, normalized in YAML), device_type (prop — e.g.,
`raid_1`), size_total (metric, bytes), hit rates from `ssdCaches[].hit_rates.Current`
— deferred to v3, see §gaps.

**Gap.** The SSDCache object as authored v2 covers only sharedCaches[].
`ssdCaches[]` (volume-allocated caches with rich hit-rate telemetry per
interval) is documented in the api-map but not modeled in v2 — flag as
follow-up. Authors should add a comment in the YAML noting this.

### 6. iSCSI LUN (list)

```yaml
- name: "iSCSI LUN"
  key: iscsi_lun
  type: INTERNAL
  icon: "block-storage.svg"
  is_world: false

  identifiers:
    - key: uuid
      source: "metricset:iscsi_luns.uuid"

  name_expression:
    parts:
      - metric: name

  metricSets:
    - from_request: iscsi_luns
      primary: true
      list_path: "luns.*"
```

**Metrics (~5).** uuid (prop, ID), name (prop), size (metric, bytes),
location (prop — join to Volume.vol_path), type_str (prop — e.g., BLUN,
THIN). Per-LUN IO from `utilization.lun[]` is available but deferred from
v2 to keep the chain count low; add in v3 as a chained metricSet
analogous to Volume IO if customer demand warrants.

### 7. NFS Share (list — BLOCKED on cartography)

```yaml
# PENDING: api-cartographer pass on SYNO.Core.Share version=1 method=list
# Known from the build-8 reference MP, but response schema not captured in
# api-maps as of 2026-04-21. mp-author should STOP at this object and ask
# the orchestrator whether to proceed with placeholder fields or defer
# NFS Share to a v2.1 after cartographer fills the schema.
```

Expected fields (from the reference MP's inference, NOT verified):
`name` (prop, ID candidate), `vol_path` (prop, join to Volume),
`description`, `enabled` flags.

---

## Auth (cookie_session preset)

```yaml
source:
  port: 5001
  ssl: NO_VERIFY
  base_path: "webapi"
  timeout: 30
  max_retries: 2
  max_concurrent: 15

  auth:
    preset: cookie_session
    credentials:
      - {key: username, label: username, sensitive: false}
      - {key: passwd,   label: passwd,   sensitive: true}
    login:
      method: GET
      path: "auth.cgi"
      params:
        - {key: api,     value: "SYNO.API.Auth"}
        - {key: version, value: "3"}
        - {key: method,  value: "login"}
        - {key: account, value: "${credentials.username}"}
        - {key: passwd,  value: "${credentials.passwd}"}
        - {key: session, value: "FileStation"}
        - {key: format,  value: "cookie"}
    extract:
      location: HEADER
      name: "Set-Cookie"
      bind_to: session.set_cookie
    inject:
      - type: header
        name: "id"
        value: "${session.set_cookie}"
    logout:
      method: DELETE
      path: "auth.cgi"
      params:
        - {key: method,  value: "logout"}
        - {key: version, value: "3"}
        - {key: api,     value: "SYNO.API.Auth"}

  test_request:
    method: GET
    path: "entry.cgi"
    params:
      - {key: api,     value: "SYNO.FileStation.Info"}
      - {key: method,  value: "get"}
      - {key: version, value: "2"}
```

---

## Request params — chain substitution for Volume IO

The `utilization` request fires at MP scope once for the Diskstation
sidecar (unfiltered), then AGAIN once per Volume row (chained, filtered).
These are NOT the same call — the chained version needs per-row
substitution:

```yaml
# The ONE top-level utilization request declaration. The chained metricSet
# on Volume applies the per-row filter via the ${chain.volume_id} token.
- name: utilization
  method: GET
  path: "entry.cgi"
  params:
    - {key: api,     value: "SYNO.Core.System.Utilization"}
    - {key: version, value: "1"}
    - {key: method,  value: "get"}
    # Filter params — only applied when fired via chain (token resolution
    # substitutes nothing when fired by Diskstation's non-chained metricSet)
    - {key: resource,   value: "space"}
    - {key: interfaces, value: "${chain.volume_id}"}
  response_path: "data"
```

**⚠ Critical:** this assumes MPB is OK emitting the `resource`/`interfaces`
params on BOTH the unfiltered (Diskstation) and filtered (Volume) firings.
If it isn't — if MPB omits chain-substituted params when there's no chain
context — Scott's 2026-04-21 curl evidence says the unfiltered call with
`resource=space` still returns the full `data.space.volume[]` array, so
the chained filter acts as a trim; the unfiltered fire still works for
root-device CPU/memory extraction via the Diskstation metricSet.

If MPB instead drops unfilled tokens (e.g., renders `interfaces=` with
empty value), this causes a problem — flag as api-explorer test item.

**ALTERNATE PATH** (safer, costs one more request): split into two
separate top-level requests, `utilization_root` (no filter, Diskstation
consumer only) and `utilization_volume` (filtered, Volume chain only).
mp-author should default to the split if any ambiguity about
chain-token-unsubstituted behavior exists.

---

## Gaps before mp-author

1. **`SYNO.Core.Share` api-map missing.** NFS Share can't be authored
   accurately without cartography on the `list` response schema. Options:
   (a) run cartographer for 5 minutes on this one endpoint and update the
   api-map; (b) defer NFS Share to v2.1 and ship v2 with 6 object types.
   Recommendation: **(a)** — it's a small cartography ask and the v2
   design is meaningfully better with it.

2. **Chain-token substitution behavior when the chain doesn't fire.**
   See §"Request params" above. Two paths: one-request with shared params
   (cleaner, needs verification), two-requests with no shared templating
   (safer, costs one more HTTP call per cycle). mp-author should ship the
   **two-request variant** by default unless a tooling-side test has
   already confirmed the one-request variant is safe; revisit after first
   successful install.

3. **SSDCache `ssdCaches[]` sub-list** (volume-allocated cache w/ hit
   rates) is known in the api-map but not modeled in v2. Flag in YAML
   comments; defer rich modeling to v3.

4. **iSCSI Target** (IQN, network_portals) — known useful for ESXi
   correlation but intentionally deferred to v3. If customer demand
   appears, add as a peer object type joining LUN by name.

5. **Name expression multi-part rendering.** `management_pack_authoring.md`
   notes the renderer currently emits a "not yet implemented" error for
   multi-part name expressions. Single-metric expressions throughout this
   design; no blocker.

---

## Events

**None in v2.** Threshold-style events (Volume utilization > 85%, disk
SMART degraded, pool status != healthy) will be authored as **factory
symptoms + alerts** referencing `mpb_synology_nas` adapter metrics after
the MP ships. This decision was settled 2026-04-18: the old top-level
`events:` key is retired from MP YAML, and factory symptoms compose with
repo-wide alerting better than MP-native events would.

DSM notification-log events (as distinct from threshold fires) can be
added later as `mpb_events:` — requires cartography on the notification
endpoint first.

---

## Bundled content

**None in v2.** Dashboards for Synology monitoring will be authored as
factory content bundles under the `[VCF Content Factory]` prefix
convention. Keeping dashboard authoring out of the .pak simplifies v2
and lets dashboards iterate without MP re-installs.

---

## Key Risks

1. **Chain-token substitution on non-chained firing.** Gap #2 above.
   Default to two separate requests to de-risk.

2. **MPB dual-parent rendering.** Both relationships #3 (Pool→Disk) and
   #4 (SSDCache→Disk) exist. This is the peer-level dual-parent pattern
   confirmed as standard in reference MPs (GitLab, Unifi). If MPB
   renders the Disk tree awkwardly (e.g., listing each sata disk under
   every pool even when only one owns it), fall back to a match-time
   narrowing on `used_by` prefix (`sata*` vs `nvme*`) — flag as tooling
   follow-up.

3. **Icon names.** `media-changer.svg`, `storage.svg`, `data-cluster.svg`,
   `hard-drive-disks.svg` confirmed in references. `cache.svg` and
   `block-storage.svg` are assumed — if MPB rejects, fall back to
   `storage.svg` and `hard-drive-disks.svg` respectively.

4. **Collection-cycle size.** With 6 explicit requests + N-per-Volume
   chained Utilization calls, steady-state load on a typical 2-4 volume
   NAS is 8-10 HTTP calls per 5-minute cycle. Well within the
   `max_concurrent: 15` budget. Flag if a bigger NAS lands in customer
   scope.

5. **NFS Share schema unverified.** Gap #1. If mp-author ships without
   cartography, the NFS Share object will carry placeholder field names
   that may not match the real response — authorship should STOP and
   require cartography first.

---

## Agent architecture reminder (for mp-author)

- Read `context/management_pack_authoring.md` first — it's the YAML spec.
- Read `context/mpb_relationships.md` next — it's the design-pattern doc.
- Read `context/api-maps/synology-storage.md`, `synology-iscsi.md`,
  `synology-auth.md`, `synology-system.md` for JSON paths.
- For NFS Share: STOP and ask the orchestrator before authoring (Gap #1).
- For Utilization chain params: default to the **two-request** variant
  (Gap #2) unless tooling or api-explorer has already confirmed the
  one-request variant works.
- Validate with `python3 -m vcfops_managementpacks validate` before
  returning.
