# Design Artifact: vSphere Storage Paths Management Pack v1

**Status.** mp-author-ready.

**MP display name:** `VCF Content Factory vSphere Storage Paths`
(per CLAUDE.md hard rule #5 -- MPs use prose-form `VCF Content Factory
<name>`, no brackets; distinct from content's bracketed `[VCF Content
Factory]` form.)

**Target MP filename:** `content/managementpacks/vsphere_storage_paths.yaml`
**Adapter kind:** `mpb_vsphere_storage_paths`
**Bundled content:** none (factory dashboards ship separately).

---

## Original Request

Build a management pack for the vSphere Data API -- a custom FastAPI
service that caches vSphere storage path health data from multiple
vCenters and exposes it as flat REST endpoints. The MP monitors
host-level storage path health: dead paths, path health percentage,
LUN counts, and path counts. The API requires no authentication.

The goal is a minimal v1: one object type (Host Storage Health), flat
topology, events for path degradation, and a cross-adapter relationship
note for future investigation. This is the simplest possible MP the
factory has built -- one unauthenticated endpoint, one object type,
no chaining, no pagination.

---

## Interview Answers

| Question | Answer | Source |
|---|---|---|
| Monitoring scope | Host-level storage path health. Dead paths, path health percentage, LUN counts, path counts. Per-LUN and per-path detail are secondary. | Pre-answered by orchestrator. |
| Object granularity | Host Storage Health as the sole object type. LUN-level info folded into host as aggregated properties where useful (e.g., distinct PSP policies, iSCSI LUN count) -- but only if available from the primary endpoint. LUN as separate objects deferred to v1.1. | Pre-answered by orchestrator. |
| Relationship topology | Flat. One object type. Adapter instance is the implicit root (Mechanism 1 per mpb_relationships.md). No explicit relationships. | Pre-answered by orchestrator. |
| Cross-adapter relationships | Ideal: relate Host Storage Health objects to existing vCenter HostSystem objects in VCF Ops (ARIA_OPS type). Flagged for investigation -- may be a substrate gap. | Pre-answered by orchestrator. |
| Auth | None. The API is fully unauthenticated. Preset: `none`. | Pre-answered by orchestrator; confirmed in API map. |
| Events | Yes. `dead_paths > 0` as WARNING/CRITICAL; `path_health_pct < 100` as WARNING; API health `status != "ok"` as WARNING on adapter. | Pre-answered by orchestrator. |
| Bundled content | None. Factory dashboards ship separately. | Pre-answered by orchestrator. |
| Collection interval | Default adapter cadence. Single collection cycle. | Pre-answered by orchestrator. |
| Adapter test | GET /api/v1/health -- check `status` field. | Pre-answered by orchestrator. |

---

## Object Model

```
Adapter Instance (auto-materialized by MPB; implicit parent of all objects)
|
+-- Host Storage Health     (list object, is_world: false)
      identifier: hostname (ESXi FQDN -- globally unique across vCenters)
      source: GET /api/v1/storage/host-path-summary -> data[]
      7 metrics + 3 properties per host
```

**World object decision.** This MP has no world/sidecar object. The API
exposes no root-device metrics worth modeling -- `/api/v1/health` returns
only a status string and per-vCenter connection booleans, which are better
served as the adapter source test than as a world object's metrics. The
adapter instance is the implicit topology root. This matches the UniFi v2
pattern (zero `is_world: true` kinds).

**No explicit relationships.** All Host Storage Health objects inherit
implicit adapter-instance parentage (Mechanism 1). No `field_match` edges
needed since there is only one object type.

### Relationships

None for v1. The object model is flat.

**Future (v1.1 investigation):** Cross-adapter relationship to vCenter
`HostSystem` objects. The `hostname` field on Host Storage Health is the
ESXi FQDN, which matches the vCenter HostSystem's name. An `ARIA_OPS`
type binding could join them, enabling navigation from a vCenter host to
its storage path health. This requires investigation into whether the
`mpb_vsphere_storage_paths` adapter can declare an `ARIA_OPS` relationship
to the `VMWARE` adapter kind's `HostSystem` resource kind. See Key Risks
#3.

---

## Request Mapping

| # | Request Name | Method | Path | Objects Fed | Notes |
|---|---|---|---|---|---|
| 1 | `health_check` | GET | `/api/v1/health` | (none -- adapter source test only) | Returns `{"status": "ok|degraded|collecting", "vcenters": {...}}`. Used for test connection. Not a data collection request. |
| 2 | `host_path_summary` | GET | `/api/v1/storage/host-path-summary` | Host Storage Health | Returns `{"collection_timestamp": "...", "vcenters_polled": [...], "data": [...]}`. Each element of `data[]` becomes one Host Storage Health object. No pagination. 8 rows in current lab. |

**Request count per cycle:** 1 (only `host_path_summary`). The
`health_check` request fires only during adapter source test, not during
collection cycles.

**`response_path` strategy:** Set `response_path: ""` (empty) on
`host_path_summary`. The `list_path` on the metricSet will be `"data"`,
pointing at the `data[]` array. Metric paths are then relative to each
element of `data[]` (e.g., `hostname`, `dead_paths`, `path_health_pct`).

**Enrichment endpoint (deferred):** GET `/api/v1/storage/host-paths`
returns the same host-level fields plus nested `luns[]` arrays with
per-LUN detail. Not consumed in v1. Would be needed for v1.1 LUN objects
or for folding aggregated LUN properties (distinct PSP policies, transport
types) onto the host object via a chained metricSet. The `hostname` field
is the join key between both endpoints.

---

## Object Type Details

### Host Storage Health

- **Object key:** `host_storage_health`
- **Type:** `INTERNAL`
- **is_world:** `false` (list object)
- **Icon:** `server.svg` (ESXi host representation)
- **Identifier:** `hostname` (ESXi FQDN -- globally unique across all
  vCenters per API map observation 2026-05-13; stable across collection
  cycles)
- **Name expression:** `hostname` (shorthand -- the FQDN is the most
  useful display name for operators who work with ESXi hosts daily)
- **Source request:** `host_path_summary`
- **metricSet:** single primary metricSet consuming `host_path_summary`,
  `list_path: "data"`

#### Metrics and Properties

| Key | Label | Usage | Data Type | Unit | Source Path | Notes |
|---|---|---|---|---|---|---|
| `hostname` | Hostname | PROPERTY | STRING | -- | `hostname` | ESXi FQDN. **IDENTIFIER.** Globally unique across vCenters. Stable. [observed 2026-05-13] |
| `vcenter` | vCenter | PROPERTY | STRING | -- | `vcenter` | Parent vCenter short name (e.g., "wld01"). Useful for filtering/grouping. [observed 2026-05-13] |
| `host_moid` | Host MOID | PROPERTY | STRING | -- | `host_moid` | vCenter managed object ID. NOT globally unique (e.g., "host-20" in both wld01 and wld02). Informational only. [observed 2026-05-13] |
| `total_luns` | Total LUNs | METRIC | NUMBER | count | `total_luns` | Total LUN devices visible to this host. [observed 2026-05-13] |
| `total_paths` | Total Paths | METRIC | NUMBER | count | `total_paths` | Total storage paths across all LUNs. [observed 2026-05-13] |
| `active_paths` | Active Paths | METRIC | NUMBER | count | `active_paths` | Paths in active state. [observed 2026-05-13] |
| `standby_paths` | Standby Paths | METRIC | NUMBER | count | `standby_paths` | Paths in standby state. [observed 2026-05-13] |
| `dead_paths` | Dead Paths | METRIC | NUMBER | count | `dead_paths` | Paths in dead state. Primary alert candidate. KPI. [observed 2026-05-13] |
| `unknown_paths` | Unknown Paths | METRIC | NUMBER | count | `unknown_paths` | Paths in unknown state. [observed 2026-05-13] |
| `path_health_pct` | Path Health % | METRIC | NUMBER | % | `path_health_pct` | Percentage of paths in active or standby state (0-100). Primary health indicator. KPI. [observed 2026-05-13] |

**Total: 7 metrics, 3 properties.**

**KPI candidates:** `dead_paths` and `path_health_pct` are the two
key performance indicators for this object type. Both are directly
alert-worthy.

**Metric groups:** All metrics belong to a single group "Storage Paths".
No sub-grouping needed for v1.

---

## Source Configuration

```
source:
  port: 443
  ssl: NO_VERIFY          # lab environment; operator can override
  base_path: ""            # paths include /api/v1/ prefix explicitly
  timeout: 30
  max_retries: 2
  max_concurrent: 5        # low concurrency; only 1 collection request

  auth:
    preset: none           # API is unauthenticated

  test_request:
    method: GET
    path: "/api/v1/health"
    params: []
```

**No credentials, no session management.** The `preset: none` auth
block is the simplest possible configuration. No `credentials`,
`login`, `extract`, `inject`, or `logout` blocks.

**Test request behavior.** GET `/api/v1/health` returns
`{"status": "ok"}` when all vCenters are connected. Status values:
- `"ok"` -- all vCenters connected (pass)
- `"degraded"` -- at least one vCenter errored (pass with warning)
- `"collecting"` -- initial collection in progress (pass with warning)

The adapter source test should succeed on any non-error HTTP response
(200 OK). The `status` field value can inform the operator but should
not fail the test connection -- `"degraded"` and `"collecting"` are
transient states that still indicate the API is reachable.

---

## Events

MPB events (`mpb_events:` block) for conditions detected during
collection. These fire as VCF Ops events when the condition is true.

| # | Event Name | Severity | Object Type | Condition | Message Template | Notes |
|---|---|---|---|---|---|---|
| 1 | Dead Storage Paths Detected | CRITICAL | host_storage_health | `dead_paths` > 0 | "Host ${hostname}: ${dead_paths} dead storage path(s) detected" | Any dead path is an immediate operational concern -- storage failover may be compromised. CRITICAL because dead paths can cause I/O errors and VM unavailability. |
| 2 | Storage Path Health Degraded | WARNING | host_storage_health | `path_health_pct` < 100 | "Host ${hostname}: storage path health at ${path_health_pct}%" | Path health below 100% means at least one path is not in active/standby state. WARNING because the host may still have redundant paths. |

**Event design decisions:**

- **Dead paths as CRITICAL (not WARNING).** The orchestrator's brief
  suggested WARNING or CRITICAL. CRITICAL is chosen because dead storage
  paths represent an active fault -- the path has failed, and the host
  may be operating with reduced redundancy or no redundancy. Waiting for
  a WARNING-then-escalation cycle delays remediation.

- **Path health as WARNING.** A `path_health_pct < 100` condition
  overlaps with `dead_paths > 0` in most cases (dead paths reduce health
  percentage). The WARNING here catches edge cases where paths are in
  `unknown` state (which also reduces `path_health_pct` but does not
  increment `dead_paths`).

- **API health event deferred.** The brief requested an event for
  `health.status != "ok"`. This is tricky because the health endpoint
  is the adapter source test, not a collection request. MPB events fire
  against collection request responses, not test requests. To detect API
  degradation during collection, the MP would need to add `/api/v1/health`
  as a collection request (not just a test request) and bind an event to
  it. This adds complexity for marginal value in v1. **Deferred to v1.1.**
  Alternative: the operator can monitor the adapter instance's built-in
  collection health metrics (collection errors, response time) which VCF
  Ops provides automatically for all adapter instances.

**Factory symptoms vs mpb_events.** Per the authoring reference,
factory symptoms + alerts (authored separately in `symptoms/` and
`alerts/`) are usually a better fit than `mpb_events` because they
compose with repo-wide alert logic. For v1, we use `mpb_events` for
these two conditions because:
1. They are simple threshold checks on single metrics.
2. They fire against the collection response directly.
3. They demonstrate the `mpb_events` grammar for the framework.

Post-v1, these could be migrated to factory symptoms if more
sophisticated alert logic is needed (e.g., sustained dead paths over
multiple cycles, correlation with other symptoms).

---

## Bundled Dashboard

None. Factory dashboards for `mpb_vsphere_storage_paths` adapter kind
objects will be authored separately via the standard dashboard pipeline.

---

## Key Risks

1. **Single-endpoint dependency.** The entire MP depends on one API
   endpoint (`/api/v1/storage/host-path-summary`). If the vSphere Data
   API is down, the MP collects nothing. Mitigation: the API is
   purpose-built for this MP and runs in the same lab environment.
   The adapter source test (`/api/v1/health`) provides early detection.

2. **No auth is unusual for production.** The API being unauthenticated
   is fine for a lab but would be a security concern in production.
   Mitigation: the API is network-isolated (internal FQDN
   `vsphere-data-api.int.sentania.net`). If auth is added later, the
   MP's `source.auth` block changes from `preset: none` to the
   appropriate preset, and credentials are added. No object model
   changes needed.

3. **Cross-adapter HostSystem relationship is uninvestigated.** The
   ideal UX would link Host Storage Health objects to the corresponding
   vCenter HostSystem objects already in VCF Ops. This would require:
   (a) The MP to declare an `ARIA_OPS` type object or relationship
   referencing `VMWARE` adapter kind's `HostSystem` resource kind.
   (b) A join key: `hostname` (ESXi FQDN) on the MP side matching the
   HostSystem's name identifier in the VMWARE adapter. (c) Verification
   that the factory's renderer supports cross-adapter bindings.
   **This is a substrate gap to investigate in v1.1.** The reference
   FastAPI MP from Dale's examples demonstrates `ARIA_OPS` type objects
   that enrich existing VMs/Hosts, so the pattern exists in MPB -- but
   the factory's YAML grammar and renderer may not support it yet.

4. **Cached data freshness.** The API serves cached data, not live
   vCenter queries. The `collection_timestamp` field indicates cache
   freshness. If the API's internal collection stalls, the MP will
   continue reporting stale data without any indication of staleness.
   Mitigation for v1.1: add `collection_timestamp` as a PROPERTY on the
   host object, or compute a `data_age_seconds` derived metric.
   **v1 does not address this.** The `collection_timestamp` field is on
   the response envelope, not on individual `data[]` rows, so it cannot
   be trivially mapped as a per-host metric. Options: (a) sidecar world
   object carries the envelope-level timestamp, (b) a future
   `response_path` that captures envelope fields alongside list
   iteration. Both are out of scope for v1.

5. **Scale ceiling unknown.** The API has no pagination and returns all
   hosts in one response. At 8 hosts this is trivial. At hundreds of
   hosts the response size could be significant. The API offers a
   `?vcenter=<name>` filter parameter that could be used to partition
   collection, but MPB's request parameterization for this would need
   design work. Low risk for the current deployment.

6. **`preset: none` auth grammar untested.** The factory has built MPs
   with `cookie_session` (Synology, UniFi) auth presets. The `none`
   preset is documented in the authoring reference but may not have been
   exercised end-to-end through the renderer. If the renderer does not
   handle `preset: none` correctly, this is a small tooling fix (emit
   no credential schema, no session flow).

---

## v1.1 Roadmap (informational, not committed)

| Feature | Description | Dependency |
|---|---|---|
| LUN objects | Separate `Host LUN` object type sourced from `/api/v1/storage/host-paths` -> `data[].luns[]`. Composite identifier: `(hostname, canonical_name)`. Per-LUN dead path counts, PSP policy, transport type. Relationship: `field_match` Host Storage Health -> Host LUN on `hostname`. | Second collection request. |
| Cross-adapter HostSystem link | `ARIA_OPS` relationship binding Host Storage Health -> VMWARE HostSystem via hostname FQDN match. | Substrate investigation: renderer + loader support for ARIA_OPS cross-references. |
| Data freshness metric | Surface `collection_timestamp` from the response envelope as a property or derived metric. Possibly a world/sidecar object carrying envelope-level metadata. | Envelope-level metric binding (new metricSet pattern or sidecar). |
| API health event | Add `/api/v1/health` as a collection request (not just test request) and bind an mpb_event for `status != "ok"`. | Minor: add a second request that feeds no objects but carries an event binding. Needs investigation of whether mpb_events can fire against non-object-producing requests. |
| Factory symptoms | Migrate dead-paths and path-health events from `mpb_events` to factory symptoms + alerts for richer alerting logic (sustained conditions, notification actions). | Post-install: symptom + alert YAML authored against the `mpb_vsphere_storage_paths` adapter kind. |

---

## Design-Time Checklist (per mpb_relationships.md section 9)

- [x] World object decision: **no world object.** API exposes no
      root-device metrics worth modeling. Adapter instance is the
      implicit root. Matches UniFi v2 pattern.
- [x] Sidecar decision: **no sidecar.** No root-device metrics.
- [x] No explicit relationships declared (flat model, single object type).
- [x] No chained metricSets (single request, no per-row enrichment).
- [x] Tree depth: 1 level (host objects under adapter instance).
- [x] No dual-parent situations.
- [x] Identifier is stable across collection cycles (`hostname` FQDN).
- [x] All metrics/properties grounded in API map observations.
- [x] No fabricated endpoints or fields.
