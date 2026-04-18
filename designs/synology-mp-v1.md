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
- **2026-04-18** — added "Chaining grammar design" and "Synology restructure
  under chain grammar" sections in response to the 2026-04-18 0400
  object-binding gap. MPB's multi-metricSet list-object model is
  request-to-request chaining (not peer enrichment); the factory YAML needs
  a grammar that lets authors declare chain relationships without hand-
  writing the `chainingSettings` wire block. This is a design-only update —
  implementation is tooling's job in the next round.
- **2026-04-18 (evening)** — swapped the chaining grammar recommendation
  from Option A (chain-on-child-request, with the "one-request-per-object
  first-wins-primary" implicit convention preserved) to **restructured
  Option C**: top-level `requests:` at the MP scope, explicit
  `metricSets:` on each object_type with explicit `primary:` selection and
  `chained_from:` naming the parent metricSet. Scott's guidance: the
  Synology MP is the exercise, the framework is the product; Option A
  preserved backwards-compat at the cost of composition-correctness and
  foreclosed request reuse across object_types. The Synology restructure
  sections and Diskstation treatment are rewritten under Option C; the
  "Known gaps" list and the outstanding questions carry over (question #1
  is moot, others remain). Added a top-level **Framework-vs-Synology
  review (2026-04-18)** pass auditing every major design choice against
  "framework-general vs. Synology-convenient" and flagging shortcut items
  for Scott's decision.

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

## Chaining grammar design

### Context and problem

The 2026-04-18 0400 gap report established that MPB's BuilderFile validator
rejects our Synology design with "Only one per resource can be null and it
must be referenced by another request." The validator fires on every
list object (`isListObject: true`) with more than one metricSet.
`context/mpb_chaining_wire_format.md` (2026-04-18) now documents the wire
format: MPB's model is **request-to-request chaining** (the child request
carries a `chainingSettings` block pointing at its parent), and the
per-metricSet `objectBinding` field MPB composes from that chain state is
not a standalone author-facing concept.

The current factory YAML has **no explicit grammar** for expressing a
parent/child relationship between requests. It uses an implicit convention:
under an `object_type`, every entry in the `requests:` block becomes one
metricSet. For a singleton (world) object that is fine — MPB accepts N
unchained metricSets on a singleton. For a list object, it is invalid —
exactly one metricSet may be the primary; the others must declare a chain
back to the primary.

(Note: `object_binding:` already exists in the YAML, but only on `mpb_events`
entries — it binds an event record to an object type. It is not used for
metricSet wiring. The orchestrator's handoff referenced "peer metricSets"
because that was the *conceptual* problem; mechanically the YAML just
listed multiple requests and the renderer inferred peer metricSets without
any join information.)

### Design goal

Let an author declare, in readable YAML:

1. **Which request is the primary** for a list object (the one that
   defines list membership).
2. **Which request(s) are chained** off another, and what parent row each
   iteration binds against.
3. **Which parent-row attributes** are exposed as per-row substitution
   values, with a simple name.
4. **Where in the child request** each substitution is consumed (path,
   query param, header, body).

Hide from the author: UUID generation, the `@@@MPB_QUOTE` tokenizer, the
composite `originId` format, the `expressionParts[]` structure, the choice
of base62 vs. RFC-4122, and any of the per-param `id` / `attributeExpression.id`
identity fields — all of that is render-time mechanism.

### Three grammar options considered

I considered three placements for the chain declaration. All three express
the same wire-level output; the trade-off is which YAML surface carries
the intent, how local the related fields are, and what the grammar makes
possible vs. precludes at the framework level.

**The earlier iteration of this section recommended Option A** (chain
declared on the child request, existing implicit "one-request-per-object,
first-wins-primary" convention preserved). That recommendation has been
withdrawn — see "Why Option A was rejected" below — and replaced with
**restructured Option C** (requests promoted to MP scope, explicit
`metricSets:` on each object_type). Option A and Option B sketches are
retained as rejected alternatives for the record.

#### Option A — chain declared on the child request (rejected)

The child request itself declares that it is chained and from where.

```yaml
# inside an object_type
requests:
  - name: "storage_load_info"       # primary by implicit first-wins convention
    method: GET
    ...
  - name: "volume_util"              # chained child
    method: GET
    params:
      - {key: location, value: "${chain.volume_id}"}
    chained_from:
      request: storage_load_info
      for_each: "data.volumes.*"
      bind:
        - name: volume_id
          from_attribute: id
```

Pros: high locality, minimal refactor of existing YAML. Cons: see "Why
Option A was rejected" below.

#### Option B — chain declared as a separate `chains:` block (rejected)

```yaml
requests:
  - name: "storage_load_info"
    ...
  - name: "volume_util"
    ...
chains:
  - child: volume_util
    parent: storage_load_info
    bind:
      - name: volume_id
        from_attribute: id
```

Pros: request entries stay shape-identical. Cons: substitution names live
in two places separated by YAML distance; retains the implicit
request-becomes-metricSet convention; same scoping limitation as Option A.

#### Option C (restructured) — requests at MP scope, explicit metricSets per object_type (RECOMMENDED)

This is the form we are adopting. Two shape changes from the earlier YAML:

1. **Requests are promoted to the top level of the MP.** They live as a
   sibling of `object_types:`, not nested inside an individual object_type.
   Each request has a globally-unique name within the MP.
2. **Each object_type declares an explicit `metricSets:` block.** Each
   entry names a `from_request`, flags exactly one as `primary: true` on
   every list object, and optionally declares a `chained_from:` binding
   to another metricSet on the same object_type.

```yaml
# MP document
name: synology-dsm
...

# NEW — requests at top level, addressable by name from any object_type
requests:
  - name: storage_load_info
    method: GET
    path: "entry.cgi"
    params:
      - {key: api,     value: "SYNO.Storage.CGI.Storage"}
      - {key: version, value: "1"}
      - {key: method,  value: "load_info"}
    response_path: "data"       # response root; object_types select sub-lists

  - name: volume_util
    method: GET
    path: "entry.cgi"
    params:
      - {key: api,      value: "SYNO.Core.System.Utilization"}
      - {key: version,  value: "1"}
      - {key: method,   value: "get"}
      - {key: location, value: "${chain.volume_id}"}
    response_path: "data"

  - name: disk_util
    ...  # another request; no chain decl here either

object_types:
  - name: "Volume"
    key: "volume"
    is_world: false
    identifiers: [volume_id]
    name_expression: display_name

    metricSets:
      - from_request: storage_load_info
        primary: true
        list_path: "volumes"         # sub-path under parent request's response_path
      - from_request: volume_util
        chained_from: storage_load_info   # parent metricSet on THIS object_type
        list_path: "space.volume"
        bind:
          - name: volume_id
            from_attribute: id

    metrics:
      - {key: volume_id,    source: "metricset:storage_load_info.id"}
      - {key: display_name, source: "metricset:storage_load_info.display_name"}
      - {key: io_read_iops, source: "metricset:volume_util.read_access"}
      ...

  - name: "Disk"
    key: "disk"
    identifiers: [disk_id]
    metricSets:
      - from_request: storage_load_info
        primary: true
        list_path: "disks"            # same request as Volume, different sub-list
      - from_request: disk_util
        chained_from: storage_load_info
        list_path: "disk.disk"
        bind:
          - name: disk_id
            from_attribute: id
    metrics: [...]
```

Note the important property: `storage_load_info` is a single request
emitted once per cycle, and **both** Volume and Disk object_types consume
it — Volume selects `data.volumes[]`, Disk selects `data.disks[]`. Under
Option A this was impossible (requests were scoped under one object_type);
under Option C the same request feeds as many metricSets as need it.

### Why Option A was rejected

Scott's guidance: the Synology MP is the exercise, the framework is the
product. Option A preserved backwards-compat and locality at the cost of:

1. **Request reuse across object_types is foreclosed.** MPB's wire model
   supports it — a single `dataModels[]` request whose `dataModelLists[]`
   feeds multiple resource kinds. Scoping requests under one object_type
   forces us to redeclare (and re-fire) the same HTTP call for every
   consumer. For Synology's `SYNO.Storage.CGI.Storage load_info` — a
   single call that returns pools, volumes, AND disks — this would mean
   firing it up to three times per cycle. The wire format and MPB support
   one-fire, many-consumer; the author grammar should not block it.
2. **"First request wins" as primary is an implicit convention, not an
   author-auditable contract.** Re-ordering the `requests:` list in the
   YAML silently changes which metricSet is `isPrimary: true` on the wire,
   which changes which metricSet defines list membership. That is an
   action-at-a-distance foot-gun. Option C forces `primary: true` to be
   written explicitly; diffs surface the change.
3. **Multi-hop chain composition is not expressible without grammar
   extensions.** Option A's `chained_from:` names a **request**, which at
   depth-2+ becomes ambiguous when a request has multiple metricSet
   consumers. Option C's `chained_from:` names a **metricSet** (on the
   same object_type) — depth-N composes cleanly because each metricSet
   has exactly one parent metricSet in the chain.
4. **MetricSet is MPB's actual unit of composition, not request.** A
   single wire request can produce multiple metricSets, each at a
   different list path. Option A's one-request-one-metricSet implicit
   mapping hides this; Option C exposes it, because that's the level at
   which chaining, primary selection, and list membership actually live.
5. **One grammar for all cases.** Under Option A, unchained singletons
   use the implicit convention, chained list objects use the explicit
   `chained_from:` block — two grammars, one YAML. Under Option C, every
   object_type writes a `metricSets:` block the same way; the only
   per-object variation is whether `chained_from:` is populated.

**Cost acknowledged.** Simple singletons (Diskstation with its three
independent requests) now require three explicit metricSet entries
instead of being inferred from a flat `requests:` list. That is the
price of composition-correctness: everything — singleton, primary,
chained, reused — is written the same way. We are paying explicitness
once to avoid special-case rules forever.

### Option C grammar in full

**Top-level `requests:` block** (new, sibling of `object_types:`):

- `name` — globally unique within the MP.
- `method`, `path`, `params[]`, `headers[]`, `body` — as today.
- `response_path` — JSON path to the response root consumed by metricSets;
  usually `data` for DSM. MetricSets further narrow via `list_path`.
- **No `chained_from` here.** Requests are agnostic to how they are
  consumed. A request does not know whether any consumer treats it as a
  chain parent or child — that wiring lives on the metricSet.
- Param/path/body templates may reference `${chain.<name>}` for
  substitutions provided by a consuming chained metricSet. If the request
  is consumed as a chain parent it is fired once per cycle with no
  substitution; if consumed as a chain child the `${chain.<name>}` tokens
  are filled from the per-row bind on the child metricSet. The request
  YAML is identical either way — the context of how it is consumed is a
  metricSet-level concern.
- If a request has `${chain.<name>}` tokens but **no** consuming metricSet
  declares `chained_from:` on it, the validator errors.

**Per-object_type `metricSets:` block** (replaces implicit request-is-
metricSet inference):

- Each metricSet has:
  - `from_request: <top-level-request-name>` — which request this
    metricSet consumes. Required.
  - `primary: true` on exactly one metricSet per list object_type (the
    one defining list membership). Absent or `false` on the others.
    Singleton (world) objects may have zero or one primary — validator
    tolerates both; singletons don't require a primary because
    `isListObject: false` drops the MPB validator's "one null
    objectBinding" rule.
  - `list_path` — sub-path below the request's `response_path` that
    selects the list of rows this metricSet iterates. Example: for
    `storage_load_info` with `response_path: "data"`, Volume's metricSet
    writes `list_path: "volumes"` and Disk's writes `list_path: "disks"`.
    For scalar per-row chained calls, `list_path` is the scalar-containing
    sub-path (e.g., `"space.volume"` for volume_util's per-volume reply).
  - `chained_from: <sibling-metricset-name>` — optional; names the
    **parent metricSet** on the same object_type. Parent metricSet is
    addressed by its `from_request` name, which must be unique within
    the object_type's `metricSets[]`. (If a future MP needs two
    metricSets against the same request on one object_type, the grammar
    will grow a per-metricSet `name:` field; Synology doesn't need this.)
  - `bind[]` — per-row substitution declarations (only meaningful when
    `chained_from:` is present). Each entry:
    - `name` — factory-facing substitution key, referenced as
      `${chain.<name>}` in the chained request's templates.
    - `from_attribute` — attribute label on the parent metricSet's rows.
      Renderer uses this to emit the `originId` composite and ensures
      the parent's `dataModelLists[].attributes[]` includes it.
    - `example` — optional sample value for MPB UI.

**Substitution scope `${chain.<name>}`** stays as the author-surface
substitution token; renderer rewrites to `${requestParameters.<name>}`
at emit. Same as Option A proposed — the renaming is a
factory-vocabulary choice independent of whether the chain is declared
on the request or on the metricSet.

**Metric source syntax** becomes `metricset:<metricset-from-request>.<path>`
(replacing Option A's `request:<request-name>.<path>`) because a given
object_type may consume a request that feeds other object_types too; the
metric is sourced from this object_type's consumption of it, not from
the request in the abstract. For Synology v1 the identifier on both
sides happens to be the request name (every object_type with a Volume
metricSet binds it from `volume_util`), so authors won't feel the
difference; the syntax is framework-general.

### Known gaps / tooling implications under Option C

These carry forward from the Option A gap list, re-anchored to the new
grammar. Tooling scope is larger than the Option A proposal; see risk #8.

1. **Multi-attribute / regex `attributeExpression` in bind.**
   `from_attribute: <single-string>` does not express multi-attribute
   concatenation or regex extraction from a parent attribute. If a future
   MP needs this, `bind[].expression:` grows a richer shape (parts list,
   optional `regex`/`regex_output` per part). Not in Synology v1 scope;
   flag for whichever MP first hits it.
2. **`params[].listId` divergence from `baseListId`.** Wire format §2.3
   notes a param's `listId` may differ from the chain's `baseListId` when
   a bound attribute comes from a deeper nested list than the one the
   chain iterates. No captured example. Renderer must assert equality and
   warn if an author setup would require divergence.
3. **Session-state + chain interaction.** Wire format §9 gap 4: no
   captured example of `${authentication.session.*}` on a chained request.
   Synology's `globalHeaders` cookie injection should fire on chained
   requests regardless (verified at live-test time).
4. **Auto-derive `list_path` vs. write it explicitly.** For singletons
   with one flat request, `list_path` is often omissible (metricSet
   consumes the whole response). For list objects, `list_path` is
   required. Grammar: `list_path` optional; default is empty (root of
   `response_path`). Validator errors if two metricSets on different
   object_types bind the same request with identical empty `list_path` —
   that would mean two object_types claim the same rows.
5. **Auto-add parent attributes to `dataModelLists[].attributes[]`.**
   Every attribute named in a child metricSet's `bind[].from_attribute`
   must be present on the parent metricSet's DML. If the author didn't
   declare a metric sourced from it, the renderer synthesizes the
   attribute entry. Render-time, no grammar surfacing.
6. **Primary validation.** Validator enforces: on every list object_type
   (`is_world: false` and the object represents a list), exactly one
   metricSet has `primary: true`. Singletons (`is_world: true` or
   single-instance) may have zero or one; if zero, the renderer emits
   the world-object metricSet group without `isPrimary` on any of them
   (matches §7 of the wire format for `isListObject: false`).
7. **Chain-graph walker.** The renderer must topologically sort
   metricSets on each object_type so chain parents render before
   children (originId composites resolve parent UUIDs). Cycle detection
   is a validator duty. Depth-2+ is permitted by the grammar but
   unverified against MPB — flag for live-test when a first multi-hop
   MP appears.
8. **Same request, different object_types, different list_paths.**
   Core scaling win over Option A. Renderer emits the request once in
   `dataModels[]`; each object_type's metricSet gets its own
   `dataModelList` with the appropriate list path. This is the
   one-fire-many-consumer pattern MPB supports natively and Option A
   precluded.
9. **Cross-object-type chain.** Grammar scopes `chained_from:` to
   sibling metricSets on the same object_type — cross-object-type chain
   is not expressible. That matches MPB's model: chains produce rows in
   a single object_type's list; a cross-kind chain would be a
   relationship, not a metricSet binding. If a capture ever shows
   otherwise, revisit.

## Synology restructure under chain grammar (Option C)

Applying restructured Option C to all five object types. Under Option C
every object_type — singletons included — writes an explicit
`metricSets:` block. Requests live at the MP top level and may be
consumed by any number of object_types.

### Top-level `requests:` block (MP scope)

All HTTP requests the MP makes, addressable by name from any metricSet.
No `primary` / `chained_from` on the request itself; those are metricSet
properties.

| Request name | Method / path | Purpose | Consumed by |
|---|---|---|---|
| `system_info` | `GET entry.cgi api=SYNO.DSM.Info` | NAS hostname, model, serial, firmware, uptime | Diskstation |
| `system_util` | `GET entry.cgi api=SYNO.Core.System.Utilization` (unparameterized) | CPU/memory/network aggregate for the NAS | Diskstation |
| `hardware_fan` | `GET entry.cgi api=SYNO.Core.Hardware.FanSpeed` | Fan status | Diskstation |
| `storage_load_info` | `GET entry.cgi api=SYNO.Storage.CGI.Storage method=load_info` | Pools, volumes, disks, hot-spares (all in one response) | Storage Pool, Volume, Disk |
| `volume_util` | `GET entry.cgi api=SYNO.Core.System.Utilization location=${chain.volume_id}` | Per-volume IO when chained off Volume | Volume (chained) |
| `disk_util` | `GET entry.cgi api=SYNO.Core.System.Utilization <disk-filter-TBD>=${chain.disk_id}` | Per-disk IO when chained off Disk | Disk (chained) |
| `iscsi_lun_list` | `GET entry.cgi api=SYNO.Core.ISCSI.LUN method=list` | LUN inventory | iSCSI LUN |
| `lun_util` | `GET entry.cgi api=SYNO.Core.System.Utilization <lun-filter-TBD>=${chain.lun_name}` | Per-LUN IO when chained off iSCSI LUN | iSCSI LUN (chained) |
| `docker_container_list` | `GET entry.cgi api=SYNO.Docker.Container method=list` | Container inventory | Docker Container |
| `docker_resource` | `GET entry.cgi api=SYNO.Docker.Container.Resource` (unparameterized) | All-container CPU/memory resource | Docker Container (chained; narrowed per-fire) |
| `ups_info` | `GET entry.cgi api=SYNO.Core.ExternalDevice.UPS.Info` | UPS model, status, charge, runtime | UPS |

Note the reuse: `storage_load_info` is declared once and consumed by
three object_types (Storage Pool, Volume, Disk), each selecting a
different `list_path` under its `response_path`. Under Option A this
would have required redeclaring the request three times; Option C
makes it a single top-level entry and the renderer emits it once in
`dataModels[]`.

### Diskstation (singleton, 3 unchained metricSets)

`is_world: true`, `isListObject: false`. Under Option C, Diskstation
writes three explicit metricSets — one per independent request — with
**no primary flag** (singletons don't require primary; wire format §7).
This is the explicitness-cost Option C makes us pay over Option A: three
metricSet entries where before a flat `requests:` list would have sufficed.

```yaml
- name: "Synology Diskstation"
  key: "diskstation"
  is_world: true
  identifiers: [serial]
  name_expression: model

  metricSets:
    - from_request: system_info
      list_path: ""            # consume whole response
    - from_request: system_util
      list_path: ""
    - from_request: hardware_fan
      list_path: ""
  metrics:
    - {key: serial,   source: "metricset:system_info.serial"}
    - {key: model,    source: "metricset:system_info.model"}
    - {key: hostname, source: "metricset:system_info.hostname"}
    # ... all 33 existing + 6 new metrics, each sourced from the
    # metricSet whose list_path resolves where they live
    - {key: memory_usage_pct, source: "metricset:system_util.memory.real_usage"}
    - {key: fan_status,       source: "metricset:hardware_fan.cool_fan"}
    ...
```

### Storage Pool (primary-only, 1 metricSet)

`is_world: false`, list object. One metricSet against
`storage_load_info` selecting `data.storagePools[]`. No chain — pools
carry their own metadata in the primary response.

```yaml
- name: "Storage Pool"
  key: "storage_pool"
  identifiers: [pool_id, pool_path]
  name_expression: pool_path

  metricSets:
    - from_request: storage_load_info
      primary: true
      list_path: "storagePools"
  metrics:
    - {key: pool_id,    source: "metricset:storage_load_info.id"}
    - {key: pool_path,  source: "metricset:storage_load_info.pool_path"}
    - {key: device_type, source: "metricset:storage_load_info.device_type"}
    ...
```

### Volume (primary + chain, 2 metricSets)

- **Primary metricSet**: consumes `storage_load_info` at
  `list_path: "volumes"`. Defines list membership.
- **Chained metricSet**: consumes `volume_util` (per-volume IO), chained
  off the primary. Parent-row attribute `id` bound as `volume_id`; the
  chained request's `location=${chain.volume_id}` param narrows the call
  to one volume per fire.
- **Per-row API support confirmed** — DSM's Utilization endpoint accepts
  `location` to narrow to one volume (verified in
  `context/api-maps/synology-storage.md` and Scott's Postman collection).

```yaml
- name: "Volume"
  key: "volume"
  identifiers: [volume_id, volume_path]
  name_expression: display_name

  metricSets:
    - from_request: storage_load_info
      primary: true
      list_path: "volumes"
    - from_request: volume_util
      chained_from: storage_load_info     # parent metricSet on THIS object_type
      list_path: "space.volume"           # chained response carries data.space.volume[0]
      bind:
        - name: volume_id
          from_attribute: id
  metrics:
    # From primary
    - {key: volume_id,    source: "metricset:storage_load_info.id"}
    - {key: display_name, source: "metricset:storage_load_info.display_name"}
    ...
    # From chained
    - {key: io_read_iops, source: "metricset:volume_util.read_access"}
    - {key: io_write_iops, source: "metricset:volume_util.write_access"}
    ...
```

**Trade-off acknowledged**: the original design's single-sweep
Utilization call is replaced by N fires (one per volume) per collection
cycle. For a 5-volume NAS at 5-minute cadence that is 5 extra requests
per cycle per NAS — bounded and tolerable.

### Disk (primary + chain, 2 metricSets; dual-parent to both Diskstation and Storage Pool)

- **Primary metricSet**: consumes `storage_load_info` at
  `list_path: "disks"`.
- **Chained metricSet**: consumes `disk_util` at
  `list_path: "disk.disk"`, chained off the primary.
- **Per-row API support UNCONFIRMED** for disk narrowing on Utilization.
  Three outcomes, all compatible with Option C:
  1. **API accepts a filter param** (like volumes do for `location`).
     Chain works as written above, payload shrinks to one disk per call.
  2. **API returns the full `data.disk.disk[]` list regardless.**
     Renderer fires the request once per disk; the chained metricSet's
     `list_path: "disk.disk"` plus the bound substitution still lets MPB
     attribute the right row back to the parent-row-source disk row.
     Wasteful bandwidth, correct semantics.
  3. **API refuses the chained-form call.** Unlikely given outcome 2 is
     reachable; escalate if observed.
- **api-cartographer task to confirm filter-param name** (likely `device`
  or `id`). If unconfirmed at mp-author time, ship v1 as outcome 2 and
  narrow to outcome 1 in v1.1.

```yaml
- name: "Disk"
  key: "disk"
  identifiers: [disk_id]
  name_expression: name

  metricSets:
    - from_request: storage_load_info
      primary: true
      list_path: "disks"
    - from_request: disk_util
      chained_from: storage_load_info
      list_path: "disk.disk"
      bind:
        - name: disk_id
          from_attribute: id
  metrics:
    - {key: disk_id, source: "metricset:storage_load_info.id"}
    - {key: name,    source: "metricset:storage_load_info.name"}
    ...
    - {key: io_read_iops, source: "metricset:disk_util.read_access"}
    ...
```

### iSCSI LUN (primary + chain, 2 metricSets; `iqn` dropped from v1)

- **Primary metricSet**: consumes `iscsi_lun_list` at
  `list_path: "luns"`.
- **Chained metricSet**: consumes `lun_util` per-LUN.
- **`iqn` property dropped for v1.** Target-LUN is many-to-many in DSM
  (one target exposes multiple LUNs; one LUN maps to multiple targets
  via `mapped_targets[]`), and a first-class Target object + LUN-Target
  relationship is the correct v2 model. Under Option C, the Target
  object is a future top-level entry with its own metricSet; for v1 we
  simply omit the property and its underlying request (`iscsi_target_list`
  disappears from the top-level `requests:` block for v1 — it would have
  been declared once and consumed twice if we were modeling Target, but
  we are not).
- **Per-row API support UNCONFIRMED** same as Disk. Same fallback model.

```yaml
- name: "iSCSI LUN"
  key: "iscsi_lun"
  identifiers: [lun_uuid]
  name_expression: name

  metricSets:
    - from_request: iscsi_lun_list
      primary: true
      list_path: "luns"
    - from_request: lun_util
      chained_from: iscsi_lun_list
      list_path: "lun"
      bind:
        - name: lun_name
          from_attribute: name
  metrics: [...]
```

### Docker Container (primary + chain, 2 metricSets)

- **Primary metricSet**: consumes `docker_container_list` at
  `list_path: "containers"`.
- **Chained metricSet**: consumes `docker_resource` per-container.
- **Per-row API support LIKELY NO** — current evidence says
  `SYNO.Docker.Container.Resource` returns all running containers in
  one payload with no filter param. Under Option C this still works:
  the chained metricSet narrows per-fire to the row matching
  `${chain.container_name}` via its `list_path` + bind. Highest
  per-cycle request cost (one fire per container); acceptable for
  typical NAS Docker counts (low tens).

```yaml
- name: "Docker Container"
  key: "docker_container"
  identifiers: [container_name]
  name_expression: container_name

  metricSets:
    - from_request: docker_container_list
      primary: true
      list_path: "containers"
    - from_request: docker_resource
      chained_from: docker_container_list
      list_path: "containers"          # narrowed per-fire
      bind:
        - name: container_name
          from_attribute: name
  metrics: [...]
```

### UPS (primary-only, 1 metricSet, 0:1 instantiation)

Single metricSet; UPS has no chained per-row call because it is
effectively already singleton (0:1 per NAS).

```yaml
- name: "UPS"
  key: "ups"
  identifiers: [model]
  name_expression: model

  metricSets:
    - from_request: ups_info
      primary: true
      list_path: ""                # unparameterized; whole response
  metrics: [...]
```

### Summary table — all 7 object_types under Option C

| Object | MetricSets | Primary | Chained | Parent-row attr | Consumer template | API per-row support |
|---|---|---|---|---|---|---|
| Synology Diskstation | 3 (unchained) | none (singleton) | none | — | — | N/A |
| Storage Pool | 1 | `storage_load_info` (`list_path: storagePools`) | none | — | — | N/A |
| Volume | 2 | `storage_load_info` (`list_path: volumes`) | `volume_util` | `id` | `location=${chain.volume_id}` | **Confirmed** |
| Disk | 2 | `storage_load_info` (`list_path: disks`) | `disk_util` | `id` | filter param TBD | **Unconfirmed** — fallback outcome-2 (full-list payload, per-fire narrow) |
| iSCSI LUN | 2 | `iscsi_lun_list` (`list_path: luns`) | `lun_util` | `name` | filter param TBD | **Unconfirmed** |
| Docker Container | 2 | `docker_container_list` (`list_path: containers`) | `docker_resource` | `name` | filter param TBD | **Likely no filter**; per-fire narrow is the shipping path |
| UPS | 1 | `ups_info` | none | — | — | N/A |

### Request-reuse scaling win (Option C vs. Option A)

Under Option A, `storage_load_info` would have been declared and fired
**three times per cycle** (once under Storage Pool's request list, once
under Volume's, once under Disk's). Under Option C, it is declared once
at top level and fired **once per cycle**, with three metricSets
selecting their respective list_paths from the response. Net: 2 fewer
HTTP calls per NAS per collection cycle on a core request. This is the
scaling property the grammar change is paying for.

### Questions for Scott before tooling picks this up

(Question #1 from the prior revision — Option A vs. B choice — is moot
under the Option C swap.)

1. **Disk / LUN / Container per-row filter capture.** Do we route an
   api-cartographer task to confirm filter-param names on
   `SYNO.Core.System.Utilization` and `SYNO.Docker.Container.Resource`
   before mp-author writes the YAML, or do we ship v1 with fallback
   behavior (per-row fire, full-list payload, metricSet narrows by
   list_path) and improve in v1.1?
2. **iSCSI `iqn` drop for v1.** Confirm that dropping the target-IQN
   property from iSCSI LUN v1 is acceptable. The alternative is modeling
   Target as a first-class object and a LUN-to-Target many-to-many
   relationship, which is a larger v2 scope expansion.
3. **Request efficiency ceiling.** The chain model multiplies requests
   per cycle by list cardinality. For a typical Synology NAS this is
   bounded (low double digits of volumes/disks/LUNs/containers); for a
   future MP targeting a system with thousands of list items per object
   type, this would need a different approach. Is there a cardinality
   threshold we want to call out for future MP designs?
4. **Option C refactor blast radius on the existing YAML.** The current
   bare-bones MP has requests nested under object_types (implicit
   request-is-metricSet). Migration to Option C requires every
   object_type to gain a `metricSets:` block and all requests to be
   lifted to MP top level. mp-author will do this during the 4.1.8
   authoring pass, but Scott should confirm that rewriting (not
   surgically patching) the existing YAML is acceptable.

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
2. **Per-object IO mapping from Utilization response** — superseded by the
   chaining grammar design above. Resolution: chain the `utilization`
   request off each list object's primary request, with per-row attribute
   binding. Risk shifts to "per-row-filter API support confirmation"
   (disk, LUN, container) and "per-cycle request count at scale".
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
8. **Option C grammar unimplemented** (updated 2026-04-18 evening) — the
   restructured grammar is a design proposal; the loader
   (`vcfops_managementpacks/loader.py`) and renderer (`render.py` +
   `render_export.py`) need substantially more work than the prior
   Option A proposal required. Tooling scope:
   (a) **Loader**: add a top-level `requests:` block at MP scope
       (currently requests are parsed under each object_type); each
       request has a globally-unique name validated across the document.
   (b) **Loader**: add a `metricSets:` block on each object_type
       replacing the implicit request-is-metricSet inference; parse
       `from_request`, `primary`, `list_path`, `chained_from`, `bind[]`.
   (c) **Validator**: enforce exactly one `primary: true` per list
       object_type; allow zero-or-one on singletons. Enforce
       `chained_from` names a sibling metricSet on the same object_type.
       Detect cycles in the chain graph. Error if two metricSets on
       different object_types bind the same request with identical empty
       `list_path`.
   (d) **Renderer**: emit each top-level request once in `dataModels[]`;
       emit one `dataModelList` per consuming metricSet, using the
       metricSet's `list_path` to compute the wire-level list identity.
   (e) **Renderer**: emit `chainingSettings` on each chained metricSet's
       `dataModelList` per wire format §2-§8, rewriting
       `${chain.<name>}` to `${requestParameters.<name>}` in param / path
       / header templates on the chained request's wire emission.
   (f) **Renderer**: auto-synthesize parent-metricSet DML attribute
       entries so `originId` composites resolve when a bind names an
       attribute the author didn't declare as a metric source.
   (g) **Renderer**: chain-graph walker — topologically sort metricSets
       per object_type so chain parents render before children; resolve
       parent metricSet UUIDs for `originId` composites; flag cycles.
   (h) **Metric source parser**: accept `metricset:<name>.<path>` syntax
       resolving to the consuming object_type's metricSet (not a
       global-request path).
   This is a larger refactor than adding a `chained_from:` field to a
   request dataclass — it is a grammar rework. Flag for tooling's next
   round; may split into loader-change and renderer-change tickets.
9. **Per-row filter API uncertainty** (new) — the chain grammar works
   whether or not the child API supports per-row filtering, but request
   volume differs by an order of magnitude. api-cartographer round
   needed to resolve Disk, LUN, and Container filter-param questions
   before declaring v1 "shipped".

## Framework-vs-Synology review (2026-04-18)

Scott's framing: the Synology MP is the exercise, the framework is the
product. This section goes back through every major design choice in
this document and asks, for each: **did we pick this because it's right
for the framework in general, or because it was convenient for Synology
specifically?** Where the choice was Synology-convenient, the framework-
general alternative is proposed and the trade-off flagged.

Shortcut count: **10 axes reviewed, 8 shortcuts identified, 2 choices
confirmed as framework-general**. Open questions requiring Scott's
decision are collected at the end of this section.

### Axis 1 — Auth model (`CUSTOM credentialType`)

**Current choice**: CUSTOM credentialType with cookie-header session,
SESSION/BASIC/TOKEN/NONE/CUSTOM as loader enum (`VALID_AUTH_TYPE`).
Aligned with Scott's build-8 MP and Postman collection.

**Assessment**: **Shortcut.** The `VALID_AUTH_TYPE` enum is the wrong
abstraction for the framework, even if it is correct for Synology. MPB's
own wire surface exposes the five named types, but the MPs we want to
ship span OAuth2 bearer-refresh, Digest, HMAC-signed, SAML-assertion,
and refresh-token patterns — none of which map cleanly onto one of those
five names, and several of which MPB's `CUSTOM` already handles by
letting the author hand-wire the flow. What `CUSTOM` tells us is that
MPB's type system is **descriptive of the type tag**, not
**prescriptive of the flow**; the factory should model auth the same
way MPB actually composes it: as a generic flow with typed steps.

**Framework-general alternative**: model auth as a flow rather than a
type tag. Five independent elements:
1. **Credential schema** — declared list of fields (name, label,
   sensitive bool). Free-form; MPB already allows this under CUSTOM.
2. **Login request** (optional) — a standalone request-shaped object
   (method, path, params, headers, body) rendered once at
   session-establishment.
3. **Token extraction** — a list of extractor rules: source
   (HEADER / JSON-body / XML-body), path/key, bind to
   `${authentication.session.<name>}`.
4. **Token injection** — a list of injector rules: scope
   (globalHeaders / per-request-params / per-request-body), name, value
   (referencing `${authentication.session.<name>}` or
   `${authentication.credentials.<name>}`).
5. **Logout request** (optional) — same shape as login, fired at
   teardown.

On top of this flow, the framework offers **named presets** (`BASIC`,
`TOKEN`, `SESSION`, `NONE` as shortcuts) that expand to canonical
extractor+injector configurations. Authors pick a preset for common
cases; those who need something weird write the flow by hand. MPB's own
`credentialType` string on the wire becomes a renderer concern (which
MPB-known type tag best matches the resolved flow), not an author
concern.

**Cost to adopt now**: Phase 4.1.5 tooling scope grows — the loader's
`auth` block becomes a nested flow instead of a `type:` enum. mp-author's
work does not change meaningfully (CUSTOM Synology auth expands to the
same five-element flow under the hood); Scott's build-8 YAML would be
rewritten to the flow form.

**Cost to defer**: every future MP's auth capture will hit this same
abstraction choice, and the loader grows a new `VALID_AUTH_TYPE` entry
each time we encounter a new flow shape. `VALID_AUTH_TYPE` becomes a
catalog of accidental name choices rather than a type system.

**Recommendation**: **Adopt the flow model now, in 4.1.5.** The
refactor is cheapest while only Synology exists; every MP added later
forecloses the simple transition. Synology keeps working because its
CUSTOM cookie-header flow is already the fully-specified form.

**Blocking question for Scott**: is the flow-model refactor in scope
for 4.1.5, or is it a v1.1 deferral with a documented TOOLSET GAP on
every future MP that doesn't fit the five-name enum?

### Axis 2 — Relationship join predicates (adapter-instance trivial match)

**Current choice**: four relationships use "adapter-instance trivial
match" with two candidate renderings (Option A synthetic
`@@@adapterInstance`, Option B per-child synthesized constant property).
Deferred to mp-author + tooling.

**Assessment**: **Shortcut deferred, not taken — but the framework has
no answer yet.** Every future MP with a world object plus N children
will hit this exact problem: the child's API response carries no field
identifying which adapter-instance collected it, because the adapter
instance is implicit (the NAS is the whole world from DSM's point of
view). MPB requires a non-null join predicate on every relationship.

**Framework-general alternative**: promote "adapter-instance scope" to
a first-class relationship kind in the factory grammar. Example:

```yaml
relationships:
  - parent: "Synology Diskstation"
    child: "Docker Container"
    scope: adapter_instance     # framework-declared; no child/parent_expression needed
```

Under this kind, the renderer synthesizes whichever wire pattern MPB
actually accepts (candidate A or B); the author simply declares intent.
The factory documents the kind once; every future MP reaches for
`scope: adapter_instance` instead of hand-writing the synthetic predicate.

Additionally expose `scope: field_match` with `child_expression` /
`parent_expression` for the value-join case (the other three Synology
relationships: Pool→Volume, Volume→LUN, Pool→Disk). Each relationship
declares its kind; the renderer chooses the wire pattern.

**Cost to adopt now**: modest. Loader parses a `scope:` field; renderer
handles two pattern emissions. mp-author's work simplifies — authors
don't pick between Option A and Option B per relationship; the renderer
does.

**Cost to defer**: every future MP re-litigates the same question at
design time, and every mp-author invocation carries the Option A / B
toggle as an open decision.

**Recommendation**: **Adopt `scope:` relationship kinds in 4.1.5
tooling**, with `adapter_instance` and `field_match` as the two named
kinds. Renderer implementation for `adapter_instance` may start as
"whichever of Option A or B tooling gets working first"; that is a
renderer detail, not a grammar concern.

**Blocking question for Scott**: adopt relationship kinds now, or ship
v1 with per-relationship hand-wiring and promote to a kind in v2?

### Axis 3 — Name expressions (single-metric only)

**Current choice**: single-metric passthrough for every object type.
Multi-metric composites (`"${model} (${hostname})"`) are deferred
because no reference MP exercises them.

**Assessment**: **Shortcut** — but honestly framed as a capture gap,
not a principled restriction. The design doc already flags this
("live verification is still pending"); the framework should not bake
single-metric as a contract.

**Framework-general alternative**: expose a composite grammar in the
loader from day one, even if the only verified emission path is the
single-metric case.

```yaml
name_expression:
  parts:
    - metric: model
    - literal: " ("
    - metric: hostname
    - literal: ")"
```

Loader accepts this shape. Renderer for v1 errors if `parts` has more
than one non-literal entry (until live verification confirms the
composite wire form); Synology uses the single-metric form which
degenerates to `parts: [{metric: <name>}]`. Once composites are
verified, only the renderer changes — the YAML surface is already in
place.

**Cost to adopt now**: small. Loader parses a parts list; renderer
emits single-part composites (matches single-metric wire). Authors who
want composites get a clear "unverified, blocked" error until verified,
rather than silently downgrading.

**Cost to defer**: when composites are verified, every existing MP's
`name_expression: <single-string>` needs migration to the parts grammar.

**Recommendation**: **Adopt the parts grammar now, with composite
rendering gated on verification.** Synology's YAML uses the
single-element form; composite verification becomes an api-explorer
task against a real MPB instance (depends on Scott's MPB UI
availability on devel).

**Blocking question for Scott**: none — this is a grammar-now-render-later
pattern the framework can implement without further input. Ship as
part of 4.1.5.

### Axis 4 — Events split (tier 1 to factory symptoms/alerts, tier 2 as MPB events)

**Current choice**: threshold conditions migrate to
`vcfops_symptoms` / `vcfops_alerts`; DSM notification events remain as
MPB events.

**Assessment**: **Framework-general, but the principle needs to be
written down explicitly.** The split is defensible: symptoms/alerts own
metric-threshold alerting across the entire factory (consistency with
built-in VCF Ops adapter kinds), MPB events are specifically for
API-pulled event records. MPB does technically support threshold-shaped
events via `severity` expressions; the framework is deliberately
routing around that capability in favor of factory symptoms/alerts.

**Articulated principle** (add to framework doctrine):
> **Threshold alerting is never MPB territory.** Any condition that
> compares a collected metric or property against a constant and emits
> an alert is authored via `vcfops_symptoms` / `vcfops_alerts`, not as
> an MPB event, regardless of whether MPB can express the threshold.
> MPB events are reserved for **API-pulled event records** — data the
> system emits as discrete events, not derived from collected metric
> values.

Rationale for the principle:
1. Factory symptoms/alerts already exist, are tested, and apply to any
   adapter kind. MPs that ship with threshold logic would duplicate an
   existing capability.
2. MPB threshold events are not uniformly supported across MPB
   versions; factory symptoms/alerts are supported by every VCF Ops
   version the factory targets.
3. Separation lets operators tune thresholds (ack, suppress, adjust)
   without rebuilding the MP.

**Cost to adopt**: zero incremental — this is already the v1 split.
Codifying the principle saves future MPs from re-litigating.

**Recommendation**: **Add the principle to `context/`** as part of
framework doctrine. No design change.

**Blocking question for Scott**: none.

### Axis 5 — Metric source syntax (dotted-path form)

**Current choice**: `source: "request:volume_util.space.volume.read_access"`
(or under Option C, `source: "metricset:volume_util.space.volume.read_access"`).
Single-scalar-path assumed; array-of-objects, regex extraction,
multi-attribute composition not expressible.

**Assessment**: **Shortcut** — Synology's responses happen to be all
scalar-field-path consumable. A future MP with array-indexed responses
or regex extraction will stress the grammar.

**Framework-general alternative**: model `source` as a structured
expression, not a dotted string.

```yaml
metrics:
  # Simple scalar (most common)
  - key: volume_usage
    source:
      metricset: volume_util
      path: "space.volume.usage_pct"

  # Array-indexed
  - key: first_fan_rpm
    source:
      metricset: hardware_fan
      path: "fans[0].rpm"

  # Array-wildcard with aggregation (for "sum of all fan rpms" style)
  - key: total_fan_rpm
    source:
      metricset: hardware_fan
      path: "fans[*].rpm"
      aggregate: sum

  # Regex extraction from a string field
  - key: firmware_major
    source:
      metricset: system_info
      path: "firmware_ver"
      extract:
        regex: "^(\\d+)\\."
        group: 1

  # Composite from multiple sources
  - key: total_load
    source:
      compose:
        - metricset: system_util.cpu.user
        - operator: add
        - metricset: system_util.cpu.system
```

Shorthand: if `source` is a string, loader expands it to
`{metricset: <first-segment>, path: <rest>}` so Synology's simple cases
stay terse.

**Cost to adopt now**: moderate. Loader parses either form (string
shorthand or structured). Renderer supports only the scalar-path form
in v1 (Synology doesn't exercise anything more complex); the structured
grammar exists so future MPs have a place to put richer sources
without grammar change.

**Cost to defer**: scalar-only is a hard ceiling. First MP that needs
array-wildcard or regex extraction forces a grammar change that breaks
Synology's simple-string YAML.

**Recommendation**: **Adopt the structured form with string shorthand
in 4.1.5.** Renderer implements scalar-path only; `aggregate`, `extract`,
`compose` variants fail with "unverified" errors until needed and
verified.

**Blocking question for Scott**: accept the structured `source` grammar
now, or keep scalar-only and refactor when a future MP needs more?

### Axis 6 — Identifier schema (multi-part identifiers)

**Current choice**: multi-part identifiers like
`identifiers: [pool_id, pool_path]` expressed as a list of metric
keys. Ordering implicit; types not declared; missing-part semantics
undefined.

**Assessment**: **Shortcut**, but small. Synology's identifiers are all
strings from primary-response fields; the simple list works. The
framework contract is under-specified:
- Does ordering matter? MPB's identity hash depends on deterministic
  serialization, so yes.
- What if a part is missing on a given row? Drop the object, or emit
  with empty-string? Undefined.
- What if a part's type is integer vs. string? MPB treats identifiers
  as strings; coercion rules undefined.
- What if the identifier is derived (e.g., a regex extraction from
  another field)? Not expressible.

**Framework-general alternative**: structured identifier declarations.

```yaml
identifiers:
  - key: volume_id              # matches a metric key on this object_type
    required: true              # row dropped if missing
    order: 1                    # explicit; defaults to list position
  - key: volume_path
    required: true
    order: 2
```

Or, when the identifier is computed:

```yaml
identifiers:
  - derive:
      parts:
        - metric: serial
        - literal: "-"
        - metric: slot_id
    order: 1
```

Shorthand: `identifiers: [volume_id, volume_path]` expands to the
structured form with `required: true` and order-by-list-position.

**Cost to adopt now**: small. Loader accepts either shorthand or
structured. Renderer implements the simple-keys case for v1; `derive`
is a grammar placeholder.

**Cost to defer**: a future MP with a union-type identifier (integer
or string depending on API version) or a derived identifier (concat
of two fields because the API gives no single unique one) will have to
synthesize a metric just to be referenced by identifiers — wasteful
and hides the relationship.

**Recommendation**: **Adopt the structured form with shorthand in
4.1.5.** Renderer implements shorthand-only; derived identifiers wait
for a needing MP.

**Blocking question for Scott**: as with axis 5, do we pay the loader
cost now to avoid a grammar-change later, or stay terse?

### Axis 7 — World-object identity

**Current choice**: Diskstation uses `serial` as world-object identifier.
Selected because DSM happens to expose a unique serial.

**Assessment**: **Shortcut** — Synology has a unique serial; vCenter
uses instance UUID; a storage array might use system ID or management
IP. The framework has no stated convention for world-object identity.

**Framework-general alternative**: document a convention hierarchy and
let authors pick from it, falling back to adapter-instance-configuration
fields when the target exposes no natural identifier.

Ordered preference:
1. **Stable system-issued identifier** (serial, UUID, system ID) — use
   when the target exposes one unique per-instance and stable across
   reconfigurations. Synology, vCenter, Rubrik fit here.
2. **User-declared connection URL / hostname** — the value the operator
   enters in the adapter-instance configuration. Use when (1) isn't
   available or when the same instance can be reconfigured without
   losing identity (appliances that rotate serials on factory reset).
3. **User-provided display name** — last resort. Operators can rename;
   identity risks drifting.

The framework exposes this as a grammar attribute on the world
object_type:

```yaml
- name: "Synology Diskstation"
  is_world: true
  world_identity:
    kind: system_issued           # or connection_address, or user_display_name
    metric: serial                # for system_issued; the metric key
    # for connection_address: no metric, value is adapter-instance URL
    # for user_display_name: field: <adapter-instance config field>
```

**Cost to adopt now**: small. Loader parses a structured
`world_identity` block. Renderer matches Synology's `serial` case.

**Cost to defer**: future MPs adopt ad-hoc conventions; reference MPs
diverge on identity patterns.

**Recommendation**: **Adopt the `world_identity` grammar and
preference-hierarchy doctrine in 4.1.5.** Documents the convention
explicitly and leaves room for all three forms. Synology uses
`kind: system_issued, metric: serial`.

**Blocking question for Scott**: agree with the three-tier preference
hierarchy, or propose a different ordering?

### Axis 8 — Request param ordering (ordered list of `{key, value}`)

**Current choice**: params emitted as an ordered list of `{key, value}`
objects, not a dict. Noted in the auth section.

**Assessment**: **Framework-general** (the ordering-matters contract
applies everywhere DSM-CGI-style semantics show up, and MPB's wire
format is list-shaped regardless), **but the placement is wrong**.
Burying the rule in the auth section is Synology-specific bookkeeping
— it belongs in the framework grammar spec.

**Framework-general articulation**: add to the framework grammar
doctrine (likely in `context/` once written):

> All request param, header, and parameter-like collections in the
> factory YAML are **ordered lists of `{key, value}` entries**, not
> dicts. Ordering is preserved on emission to the MPB wire format.
> Authors who write a dict form will be accepted by YAML parsing but
> rejected by the loader — the ambiguity of insertion order in
> older YAML libraries makes dict forms non-portable.

**Cost to adopt**: zero — this is already the v1 behavior. Documentation
only.

**Recommendation**: **Document the contract in framework doctrine.**
No design change.

**Blocking question for Scott**: none.

### Axis 9 — Bundled content split (basic .pak + rich factory dashboard)

**Current choice**: basic dashboard bundled in the `.pak`, rich
factory dashboard shipped separately via existing
`vcfops_dashboards` pipeline.

**Assessment**: **Framework-general principle, under-documented.** The
split is defensible: `.pak`-bundled content is what MPB ships to the
operator on first install; factory dashboards layer on top and can be
replaced/updated without republishing the `.pak`. The pattern applies
to every future MP.

**Articulated principle** (add to framework doctrine):
> MPs ship the **minimum viable bundled content** in the `.pak` — one
> or two basic dashboards that confirm the adapter is collecting and
> give an operator a jump-off point. **Rich dashboards, symptoms,
> alerts, reports, and views ship via the factory content pipeline**,
> not the `.pak`. This keeps the MP binary stable across content
> iterations and lets operators update content without reinstalling
> the adapter.

**Cost to adopt**: zero incremental.

**Recommendation**: **Codify the principle in framework doctrine.**

**Blocking question for Scott**: none — but confirm the principle as
stated, particularly the "minimum viable bundled content" phrase.

### Axis 10 — Phase-naming (4.1.5, 4.1.7, 4.1.8 references throughout)

**Current state**: references to "Phase 4.1.5", "4.1.7", "4.1.8" are
scattered throughout the design doc.

**Assessment**: **Shortcut.** These are Synology-project phase numbers,
not framework-capability numbers. A reusable design-artifact convention
should separate two concerns:
1. **Framework capability required** — e.g., "CUSTOM auth in loader",
   "chaining grammar in loader+renderer", "MPB event grammar in
   loader+renderer".
2. **Synology phase when that capability lands** — the
   project-management timeline.

**Framework-general alternative**: rewrite all "Phase X.Y" references
as "framework capability: `<capability-name>`", and list the mapping
from capability to Synology phase in one place (a table at the end of
the doc, or in the design artifact frontmatter).

**Cost to adopt now**: the present design doc is mid-revision; a
wholesale sweep of phase references is outside this pass. Flag as a
structural revision for the next design-doc update.

**Recommendation**: **Defer the sweep** — too much churn in one pass.
Next design revision, or a follow-on `context/design-artifact-conventions.md`
pass, should normalize phase vs. capability language across the doc.
For future design artifacts (starting with the NEXT MP), adopt the
capability-first convention from day one.

**Blocking question for Scott**: none — this is a documentation-
convention cleanup, not a design decision.

### Axis 11 — Primary selection semantics (new under Option C)

**Current choice**: Option C requires exactly one `primary: true` per
list object_type; singletons may have zero or one.

**Assessment**: **Framework-general.** This was the whole point of the
Option A → Option C swap. Explicit primary selection, no implicit
"first wins," one grammar for all cases.

**Framework articulation** (captured above in the Option C section):
- List object_types: validator enforces exactly one primary metricSet.
- Singleton (world) object_types: zero-or-one primary; if zero, the
  renderer emits with no `isPrimary: true` on the wire (matches
  `isListObject: false` rule).

**Cost**: paid in the Option C refactor. No further framework cost.

**Recommendation**: **Already adopted.** Included here for completeness.

**Blocking question for Scott**: none.

### Axis 12 — Request reuse across object_types (new under Option C)

**Current choice**: Option C allows a single top-level request to feed
metricSets on multiple object_types (Synology's `storage_load_info` is
consumed by Storage Pool, Volume, and Disk).

**Assessment**: **Framework-general** — this is one of Option C's
primary scaling properties over Option A.

**Framework articulation**: requests are MP-scope entities;
object_types name which requests feed their metricSets. A single
request emits once per cycle on the wire, and any number of
object_types consume it via their `metricSets[].from_request`.

**Cost**: paid in the Option C refactor.

**Recommendation**: **Already adopted.** Included for completeness.

**Blocking question for Scott**: none.

### Summary of shortcuts vs. framework-general

| Axis | Current | Assessment | Proposal | Blocking Q for Scott |
|---|---|---|---|---|
| 1. Auth model | CUSTOM via `VALID_AUTH_TYPE` enum | Shortcut | Generic flow with named presets | Adopt flow model in 4.1.5, or defer? |
| 2. Relationship predicates | Per-relationship Option A/B deferred | Shortcut | `scope:` relationship kinds | Adopt kinds in 4.1.5, or defer? |
| 3. Name expressions | Single-metric only | Shortcut (capture gap) | Parts grammar with render-gated composites | None — adopt |
| 4. Events split | Threshold → symptoms/alerts; API-pulled → MPB | Framework-general | Codify principle | None — document |
| 5. Metric source syntax | Dotted-path string | Shortcut | Structured with string shorthand | Adopt structured form, or defer? |
| 6. Identifier schema | Flat list of metric keys | Shortcut | Structured with shorthand | Adopt structured form, or defer? |
| 7. World-object identity | Ad-hoc (serial) | Shortcut | Three-tier preference grammar | Agree with hierarchy? |
| 8. Request param ordering | Ordered `{key,value}` list | Framework-general | Codify contract | None — document |
| 9. Bundled content split | Basic in .pak, rich via factory pipeline | Framework-general | Codify principle | Confirm wording |
| 10. Phase-naming convention | Synology phase numbers throughout | Shortcut | Capability-first language | None — cleanup |
| 11. Primary selection | Explicit, one per list object | Framework-general (new via Option C) | Already adopted | None |
| 12. Request reuse across object_types | Supported at MP scope | Framework-general (new via Option C) | Already adopted | None |

**Shortcut count**: 8 of 12 axes are shortcuts (axes 1, 2, 3, 5, 6, 7,
10 explicitly; axis 10 is a documentation shortcut, not a design one).
Of the 8, five (axes 1, 2, 3, 5, 6, 7) propose loader-level framework
changes that would expand 4.1.5 tooling scope. The remaining two
(axes 10 and the documentation items) are cleanup work.

### Open questions requiring Scott's decision before mp-author or tooling proceeds

1. **Auth flow model (axis 1)** — adopt flow-based auth grammar in
   4.1.5, or keep `VALID_AUTH_TYPE` enum with CUSTOM as escape hatch?
   Blocks: 4.1.5 tooling scope, and implicitly every future MP's auth
   design.
2. **Relationship kinds (axis 2)** — adopt `scope: adapter_instance` /
   `scope: field_match` kinds in 4.1.5, or leave per-relationship
   hand-wiring for v1? Blocks: mp-author's 4.1.8 work on the four
   adapter-instance-trivial relationships; framework convention for
   every future MP.
3. **Composite-grammar adoption for name / source / identifiers
   (axes 3, 5, 6)** — adopt structured shapes with string shorthand in
   4.1.5 (loader-only; renderers implement the simple cases), or ship
   Synology v1 with flat-string forms and refactor later? All three
   share the same trade-off: loader cost now vs. grammar migration
   later.
4. **World-object identity hierarchy (axis 7)** — agree with the
   three-tier preference (system-issued → connection address → user
   display name), or propose a different ordering? Blocks: framework
   doctrine; Synology uses `kind: system_issued` regardless.
5. **4.1.5 tooling scope envelope** — if axes 1, 2, 3, 5, 6, 7 all
   adopt now, the tooling scope in 4.1.5 expands significantly beyond
   "add CUSTOM auth + chain grammar." Scott should decide whether to
   (a) do the full framework-general pass in one 4.1.5 sweep, (b) split
   into 4.1.5 (grammar) and 4.1.5.5 (renderer follow-ons), or (c)
   defer the non-blocking axes (3, 5, 6) to v2 of the framework.
6. **Option C refactor blast radius on existing YAML (carried from
   the chain grammar section)** — mp-author will rewrite, not
   surgically patch, the existing bare-bones MP during 4.1.8. Confirm
   acceptable.

All five trade-offs in the list above are **"adopt now while only
Synology exists" vs. "defer and refactor when a second MP forces it."**
The framework-is-the-product framing argues for "adopt now" across the
board; the shipping-Synology framing argues for "defer the non-
blocking items." Scott's call.
