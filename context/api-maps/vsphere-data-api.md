# API Map: vSphere Data API

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `vsphere-data-api.int.sentania.net` — custom REST
  API (FastAPI/Python) exposing vSphere storage path data for VCF
  Operations management pack consumption. Version 0.1.0 per OpenAPI spec.
  Three vCenters connected: `wld01`, `wld02`, `mgmt` (8 ESXi hosts total).
- **Last updated:** 2026-05-13
- **Update history:**
  - 2026-05-13 — Initial mapping. Full OpenAPI 3.1.0 spec analysis
    (`docs/vsphere-data-api-openapi.json`) combined with live response
    data provided by the orchestrator from same-day probes. All 4
    endpoints documented. Object model, metric/property classification,
    join keys, and gaps identified.
- **Evidence basis:** OpenAPI 3.1.0 spec at
  `docs/vsphere-data-api-openapi.json` (committed to repo) + live API
  responses provided by orchestrator (probed 2026-05-13 against
  `vsphere-data-api.int.sentania.net`). No direct live calls made by
  this agent session; all response data comes from the orchestrator's
  brief with verbatim payloads.
- **Notes:** This API serves cached vCenter data — it does not query
  vCenter live on each request. The `collection_timestamp` field
  indicates cache freshness. The API is purpose-built as an MP data
  source for VCF Operations.

## Connection

- **Base URL:** `https://vsphere-data-api.int.sentania.net` [observed 2026-05-13]
- **Auth type:** NONE [observed 2026-05-13] — no authentication required
- **Auth flow:** N/A — all endpoints are unauthenticated
- **Session maintenance:** N/A
- **OpenAPI spec:** Available (3.1.0), saved at `docs/vsphere-data-api-openapi.json` [observed 2026-05-13]
- **Framework:** FastAPI (Python), inferred from OpenAPI `openapi: 3.1.0` output, `422` validation error schemas, and `operationId` naming convention [inferred from pattern]

## Endpoints

### 1. Health Check

- **Method:** GET
- **Path:** `/api/v1/health`
- **Tags:** `health`
- **Parameters:** none
- **Description:** Returns overall API health and per-vCenter connection status. Used by VCF Operations adapter source tests to verify the API is reachable and vCenter connections are alive. [documented in OpenAPI spec]
- **Status rules:** `"collecting"` = any vCenter still in initial collection; `"degraded"` = all vCenters attempted, at least one errored; `"ok"` = all vCenters connected [documented in OpenAPI spec]
- **Response schema:**
  ```json
  {
    "status": "ok | degraded | collecting",    // enum: ["ok", "degraded", "collecting"]
    "vcenters": {                               // object: additionalProperties(string)
      "<vcenter_name>": "<status_string>"       // observed values: "connected"
    }
  }
  ```
- **Live sample (2026-05-13):**
  ```json
  {
    "status": "ok",
    "vcenters": {
      "wld01": "connected",
      "wld02": "connected",
      "mgmt": "connected"
    }
  }
  ```
- **Object candidates:** None — this is an API health/connectivity endpoint, not a data source for monitored objects.
- **MP relevance:** Adapter source test — call this to verify reachability before collecting data. [inferred from OpenAPI description]

---

### 2. List vCenters

- **Method:** GET
- **Path:** `/api/v1/vcenters`
- **Tags:** `health`
- **Parameters:** none
- **Description:** Returns configured vCenters with connection status and last collection time. [documented in OpenAPI spec]
- **Response schema (VCentersResponse):**
  ```json
  {
    "vcenters": [                              // array of VCenterStatusItem
      {
        "name": "string",                      // REQUIRED — vCenter short name (e.g., "wld01")
        "server": "string",                    // REQUIRED — FQDN of vCenter server
        "status": "string",                    // REQUIRED — connection status (observed: "connected")
        "last_collection": "datetime | null",  // OPTIONAL — ISO 8601 timestamp of last successful collection
        "host_count": 0                        // OPTIONAL — default 0; count of ESXi hosts managed
      }
    ]
  }
  ```
- **Live sample (2026-05-13):**
  ```json
  {
    "vcenters": [
      {
        "name": "wld01",
        "server": "vcf-lab-vcenter-wld01.int.sentania.net",
        "status": "connected",
        "last_collection": "2026-05-13T20:50:58.956464Z",
        "host_count": 2
      },
      {
        "name": "wld02",
        "server": "vcf-lab-vcenter-wld02.int.sentania.net",
        "status": "connected",
        "last_collection": "2026-05-13T20:50:59.204997Z",
        "host_count": 2
      },
      {
        "name": "mgmt",
        "server": "vcf-lab-vcenter-mgmt.int.sentania.net",
        "status": "connected",
        "last_collection": "2026-05-13T20:50:59.727241Z",
        "host_count": 4
      }
    ]
  }
  ```
- **Array cardinality:** 3 items [observed 2026-05-13]
- **Object candidates:** vCenter (candidate — see Object Model section)
- **Field classification:**
  | Field | Type | Classification | Notes |
  |---|---|---|---|
  | `name` | string | IDENTIFIER | Short name, unique across all vCenters [observed 2026-05-13] |
  | `server` | string | PROPERTY | FQDN of the vCenter server [observed 2026-05-13] |
  | `status` | string | PROPERTY | Connection status; observed value: `"connected"` [observed 2026-05-13] |
  | `last_collection` | datetime/null | METRIC (timestamp) | ISO 8601; tracks cache freshness [observed 2026-05-13] |
  | `host_count` | integer | METRIC | Number of ESXi hosts under this vCenter [observed 2026-05-13] |

---

### 3. Host Path Summary

- **Method:** GET
- **Path:** `/api/v1/storage/host-path-summary`
- **Tags:** `storage`
- **Parameters:**
  | Param | In | Required | Type | Description |
  |---|---|---|---|---|
  | `vcenter` | query | no | string or null | Filter by vCenter name [documented in OpenAPI spec] |
- **Description:** Flat per-host storage summary — one row per host. This is the primary shape consumed by MPB adapters. Each row maps directly to a host object in VCF Operations via the hostname field. [documented in OpenAPI spec]
- **Response schema (HostPathSummaryResponse):**
  ```json
  {
    "collection_timestamp": "datetime | null",  // cache freshness; null if not yet collected
    "vcenters_polled": ["string"],              // which vCenters contributed data
    "data": [                                   // array of HostStorageSummary
      {
        "vcenter": "string",                    // REQUIRED — vCenter short name
        "hostname": "string",                   // REQUIRED — ESXi host FQDN
        "host_moid": "string",                  // REQUIRED — vCenter managed object ID
        "total_luns": 0,                        // REQUIRED — integer
        "total_paths": 0,                       // REQUIRED — integer
        "active_paths": 0,                      // REQUIRED — integer
        "standby_paths": 0,                     // REQUIRED — integer
        "dead_paths": 0,                        // REQUIRED — integer
        "unknown_paths": 0,                     // REQUIRED — integer
        "path_health_pct": 0.0                  // REQUIRED — float, percentage (0-100)
      }
    ]
  }
  ```
- **Live sample (2026-05-13, truncated to 2 rows):**
  ```json
  {
    "collection_timestamp": "2026-05-13T20:45:57.836043Z",
    "vcenters_polled": ["mgmt", "wld01", "wld02"],
    "data": [
      {
        "vcenter": "wld01",
        "hostname": "vcf-lab-wld01-esx01.int.sentania.net",
        "host_moid": "host-20",
        "total_luns": 3,
        "total_paths": 5,
        "active_paths": 5,
        "standby_paths": 0,
        "dead_paths": 0,
        "unknown_paths": 0,
        "path_health_pct": 100.0
      },
      {
        "vcenter": "mgmt",
        "hostname": "vcf-lab-mgmt-esx03.int.sentania.net",
        "host_moid": "host-6011",
        "total_luns": 3,
        "total_paths": 3,
        "active_paths": 3,
        "standby_paths": 0,
        "dead_paths": 0,
        "unknown_paths": 0,
        "path_health_pct": 100.0
      }
    ]
  }
  ```
- **Array cardinality:** 8 items (one per ESXi host across 3 vCenters) [observed 2026-05-13]
- **Object candidates:** Host Storage Summary (primary MP object — see Object Model)
- **Field classification:**
  | Field | Type | Classification | Unit | Notes |
  |---|---|---|---|---|
  | `vcenter` | string | PROPERTY | — | Parent vCenter short name [observed 2026-05-13] |
  | `hostname` | string | IDENTIFIER | — | ESXi FQDN; globally unique across all vCenters [observed 2026-05-13] |
  | `host_moid` | string | PROPERTY | — | vCenter MOID; NOT globally unique (e.g., `host-20` in both wld01 and wld02) [observed 2026-05-13] |
  | `total_luns` | integer | METRIC | count | Total LUN devices visible to host [observed 2026-05-13] |
  | `total_paths` | integer | METRIC | count | Total storage paths across all LUNs [observed 2026-05-13] |
  | `active_paths` | integer | METRIC | count | Paths in active state [observed 2026-05-13] |
  | `standby_paths` | integer | METRIC | count | Paths in standby state [observed 2026-05-13] |
  | `dead_paths` | integer | METRIC | count | Paths in dead state — critical alert candidate [observed 2026-05-13] |
  | `unknown_paths` | integer | METRIC | count | Paths in unknown state [observed 2026-05-13] |
  | `path_health_pct` | float | METRIC | % (0-100) | Percentage of paths in active or standby state [observed 2026-05-13; unit confirmed in OpenAPI description] |

---

### 4. Host Paths (Detail)

- **Method:** GET
- **Path:** `/api/v1/storage/host-paths`
- **Tags:** `storage`
- **Parameters:**
  | Param | In | Required | Type | Description |
  |---|---|---|---|---|
  | `vcenter` | query | no | string or null | Filter by vCenter name [documented in OpenAPI spec] |
- **Description:** Full storage path detail for all hosts across all polled vCenters. Data is served from in-memory cache — no live vCenter query per request. [documented in OpenAPI spec]
- **Response schema (HostPathsResponse):**
  ```json
  {
    "collection_timestamp": "datetime | null",
    "vcenters_polled": ["string"],
    "data": [                                   // array of HostStorageDetail
      {
        "vcenter": "string",
        "hostname": "string",
        "host_moid": "string",
        "total_luns": 0,
        "total_paths": 0,
        "active_paths": 0,
        "standby_paths": 0,
        "dead_paths": 0,
        "unknown_paths": 0,
        "luns": [                               // array of LunDetail
          {
            "canonical_name": "string",         // device identifier (naa.xxx or eui.xxx per docs)
            "display_name": "string",           // vendor model string
            "datastore_name": "string | null",  // VMFS datastore name; null if raw/unmapped
            "psp": "string",                    // Path Selection Policy (e.g., VMW_PSP_RR, VMW_PSP_FIXED)
            "psp_config": "",                   // PSP config string, default ""
            "path_count": 0,
            "active_path_count": 0,
            "standby_path_count": 0,
            "dead_path_count": 0,
            "unknown_path_count": 0,            // default 0
            "paths": [                          // array of PathDetail
              {
                "name": "string",               // vmhba address (e.g., "vmhba64:C0:T0:L1")
                "state": "active | standby | dead | unknown",   // enum
                "is_working_path": true,        // boolean
                "adapter": "string",            // HBA identifier (e.g., "vmhba64")
                "transport": "string"           // iscsi | fc | fcoe | unknown
              }
            ]
          }
        ]
      }
    ]
  }
  ```
- **Live sample — single LUN entry from wld01 host (2026-05-13):**
  ```json
  {
    "canonical_name": "02000100006001405d023e190d8940d485ad8bf1d453746f726167",
    "display_name": "02000100006001405d023e190d8940d485ad8bf1d453746f726167",
    "datastore_name": null,
    "psp": "VMW_PSP_RR",
    "psp_config": "",
    "path_count": 3,
    "active_path_count": 3,
    "standby_path_count": 0,
    "dead_path_count": 0,
    "unknown_path_count": 0,
    "paths": [
      {"name": "vmhba64:C0:T0:L1", "state": "active", "is_working_path": true, "adapter": "vmhba64", "transport": "iscsi"},
      {"name": "vmhba64:C3:T0:L1", "state": "active", "is_working_path": true, "adapter": "vmhba64", "transport": "iscsi"},
      {"name": "vmhba64:C2:T0:L1", "state": "active", "is_working_path": true, "adapter": "vmhba64", "transport": "iscsi"}
    ]
  }
  ```
- **Array cardinality:** 8 host items (same as host-path-summary); 2-4 LUNs per host; 1-3 paths per LUN [observed 2026-05-13]
- **Nesting depth:** 3 levels — response.data[].luns[].paths[]
- **Object candidates:** Host Storage Detail, LUN, Path (see Object Model)
- **Host-level field classification:** Same as endpoint 3, minus `path_health_pct` (not present here) [observed 2026-05-13]
- **LUN-level field classification:**
  | Field | Type | Classification | Unit | Notes |
  |---|---|---|---|---|
  | `canonical_name` | string | IDENTIFIER | — | Device identifier; observed as hex-encoded (not typical `naa.xxx` format in this lab) [observed 2026-05-13] |
  | `display_name` | string | PROPERTY | — | Vendor model string; identical to `canonical_name` in lab data [observed 2026-05-13] |
  | `datastore_name` | string/null | PROPERTY | — | VMFS datastore name if LUN backs one; **all null in lab** (vSAN environment) [observed 2026-05-13] |
  | `psp` | string | PROPERTY | — | Path Selection Policy; observed: `"VMW_PSP_RR"` (round-robin), `"VMW_PSP_FIXED"` [observed 2026-05-13] |
  | `psp_config` | string | PROPERTY | — | PSP configuration; observed: `""` (empty) in all cases [observed 2026-05-13] |
  | `path_count` | integer | METRIC | count | Total paths for this LUN [observed 2026-05-13] |
  | `active_path_count` | integer | METRIC | count | Active paths [observed 2026-05-13] |
  | `standby_path_count` | integer | METRIC | count | Standby paths [observed 2026-05-13] |
  | `dead_path_count` | integer | METRIC | count | Dead paths — alert candidate at LUN level [observed 2026-05-13] |
  | `unknown_path_count` | integer | METRIC | count | Unknown paths [observed 2026-05-13] |
- **Path-level field classification:**
  | Field | Type | Classification | Notes |
  |---|---|---|---|
  | `name` | string | IDENTIFIER | vmhba address (e.g., `vmhba64:C0:T0:L1`) [observed 2026-05-13] |
  | `state` | string (enum) | PROPERTY | `active`, `standby`, `dead`, `unknown` [documented in OpenAPI spec] |
  | `is_working_path` | boolean | PROPERTY | Whether this is the currently active working path [observed 2026-05-13] |
  | `adapter` | string | PROPERTY | HBA identifier (e.g., `vmhba64`) [observed 2026-05-13] |
  | `transport` | string | PROPERTY | Transport type; observed: `"iscsi"`, `"unknown"` (local disks); spec also lists `"fc"`, `"fcoe"` [observed 2026-05-13; documented in OpenAPI spec] |

## Object Model Candidates

### 1. vCenter (optional/lightweight)

- **Source endpoint:** `/api/v1/vcenters`
- **Identifier:** `name` (short name, e.g., `"wld01"`) — unique [observed 2026-05-13]
- **Properties:**
  - `server` — FQDN [observed 2026-05-13]
  - `status` — connection status [observed 2026-05-13]
- **Metrics:**
  - `host_count` — number of managed hosts [observed 2026-05-13]
  - `last_collection` — timestamp of last data collection [observed 2026-05-13]
- **Relationships:** Parent of Host Storage objects (joined by `name` = `data[].vcenter`) [inferred from pattern]
- **MP recommendation:** Consider as a lightweight parent object for grouping hosts by vCenter. Not strictly necessary if hosts are the only monitored object type. [inferred from pattern]

### 2. Host Storage (primary)

- **Source endpoint(s):**
  - `/api/v1/storage/host-path-summary` — primary data source (flat, one row per host) [observed 2026-05-13]
  - `/api/v1/storage/host-paths` — enrichment source (same host-level fields plus nested LUN/path detail) [observed 2026-05-13]
- **Identifier:** `hostname` (ESXi FQDN) — globally unique across all vCenters [observed 2026-05-13]
  - **NOT** `host_moid` — this is scoped to a single vCenter and duplicates across vCenters (e.g., `host-20` appears in both wld01 and wld02) [observed 2026-05-13]
  - Composite key `(vcenter, host_moid)` is also unique but `hostname` alone is simpler and sufficient [observed 2026-05-13]
- **Metrics:**
  | Metric | Unit | Source | Alert-worthy |
  |---|---|---|---|
  | `total_luns` | count | host-path-summary | no |
  | `total_paths` | count | host-path-summary | no |
  | `active_paths` | count | host-path-summary | no |
  | `standby_paths` | count | host-path-summary | no |
  | `dead_paths` | count | host-path-summary | **yes** — dead_paths > 0 |
  | `unknown_paths` | count | host-path-summary | possibly |
  | `path_health_pct` | % (0-100) | host-path-summary | **yes** — path_health_pct < 100 |
- **Properties:**
  | Property | Source |
  |---|---|
  | `vcenter` | host-path-summary |
  | `host_moid` | host-path-summary |
- **Relationships:**
  - Child of vCenter (via `vcenter` field) [inferred from pattern]
  - Parent of LUN (via nesting in host-paths response) [observed 2026-05-13]

### 3. LUN (optional detail object)

- **Source endpoint:** `/api/v1/storage/host-paths` (nested under `data[].luns[]`)
- **Identifier:** Composite — `(hostname, canonical_name)`. The `canonical_name` alone is unique within a host but could theoretically appear on multiple hosts for shared storage. [observed 2026-05-13; uniqueness scope inferred from pattern]
- **Metrics:**
  | Metric | Unit | Alert-worthy |
  |---|---|---|
  | `path_count` | count | no |
  | `active_path_count` | count | no |
  | `standby_path_count` | count | no |
  | `dead_path_count` | count | **yes** |
  | `unknown_path_count` | count | possibly |
- **Properties:**
  | Property | Notes |
  |---|---|
  | `canonical_name` | Hex-encoded device ID in lab; spec says `naa.xxx` or `eui.xxx` [observed 2026-05-13; documented in OpenAPI spec] |
  | `display_name` | Vendor model string; identical to canonical_name in lab [observed 2026-05-13] |
  | `datastore_name` | VMFS datastore; all null in lab (vSAN) [observed 2026-05-13] |
  | `psp` | Path Selection Policy; observed: `VMW_PSP_RR`, `VMW_PSP_FIXED` [observed 2026-05-13] |
  | `psp_config` | PSP config string; empty in all observations [observed 2026-05-13] |
  | `transport` (from paths) | Dominant transport type of child paths; observed: `"iscsi"`, `"unknown"` [observed 2026-05-13] |
- **Relationships:**
  - Child of Host Storage (via nesting) [observed 2026-05-13]
  - Parent of Path (via nesting) [observed 2026-05-13]
- **MP recommendation:** Including LUN as a distinct object type is optional. For an initial MP, the host-level summary is likely sufficient. LUN-level objects add granularity for per-LUN dead-path alerting and PSP policy visibility. Consider for a v2 scope expansion. [inferred from pattern]

### 4. Path (deepest detail — probably not an MP object)

- **Source endpoint:** `/api/v1/storage/host-paths` (nested under `data[].luns[].paths[]`)
- **Identifier:** `name` (vmhba address, e.g., `vmhba64:C0:T0:L1`) — unique within a host [observed 2026-05-13]
- **Properties:** `state`, `is_working_path`, `adapter`, `transport`
- **MP recommendation:** Too granular for an MP object. Path state is better consumed as aggregate metrics at the LUN or Host level (which the API already computes). Do not model as a separate object type. [inferred from pattern]

## Cross-Request Join Keys

| Key | Endpoint A | Endpoint B | Binds |
|---|---|---|---|
| `hostname` | `host-path-summary.data[].hostname` | `host-paths.data[].hostname` | Host Storage Summary to Host Storage Detail (same host, different detail level) [observed 2026-05-13] |
| `vcenter` | `vcenters[].name` | `host-path-summary.data[].vcenter` | vCenter to Host Storage (parent-child) [observed 2026-05-13] |
| `vcenter` | `vcenters[].name` | `host-paths.data[].vcenter` | vCenter to Host Storage Detail (parent-child) [observed 2026-05-13] |
| `vcenter` | `health.vcenters.<key>` | `vcenters[].name` | Health status to vCenter metadata [observed 2026-05-13] |

**Join key notes:**
- `hostname` is the primary join key across storage endpoints. It is an FQDN and is globally unique. [observed 2026-05-13]
- `host_moid` is NOT a safe join key across vCenters — `host-20` appears in both wld01 and wld02. Within a single vCenter scope it is unique, but cross-vCenter it requires the `(vcenter, host_moid)` composite. [observed 2026-05-13]
- The `?vcenter=<name>` filter parameter on both storage endpoints uses the same `name` values as `/api/v1/vcenters` and the health endpoint's `vcenters` object keys. [observed 2026-05-13]

## Pagination

None. All endpoints return the full dataset in a single response. No `offset`, `limit`, `cursor`, or `page` parameters exist. [observed 2026-05-13; confirmed in OpenAPI spec]

Given the current scale (8 hosts, 3 vCenters), this is appropriate. If the API scales to hundreds of hosts, pagination may become necessary. The `?vcenter=` filter provides coarse partitioning. [inferred from pattern]

## Data Freshness Model

The API serves cached data, not live vCenter queries. [documented in OpenAPI spec]

- `collection_timestamp` on storage responses indicates when the cache was last populated [observed 2026-05-13]
- `last_collection` on the vCenters endpoint indicates per-vCenter collection time [observed 2026-05-13]
- Collection appears to run on a background schedule (observed timestamps ~5 minutes before the probe time) [inferred from timestamp comparison]
- If the cache has not yet been populated, `collection_timestamp` will be `null` [documented in OpenAPI spec]

## Recommended MP Object Hierarchy

Based on the API surface, the recommended MP object model for v1 is:

```
vCenter (optional parent)
  |
  +-- Host Storage Path Health
        identifier: hostname (FQDN)
        metrics: total_luns, total_paths, active_paths, standby_paths,
                 dead_paths, unknown_paths, path_health_pct
        properties: vcenter, host_moid
        source: /api/v1/storage/host-path-summary
```

**Adapter collection strategy:**
1. Call `/api/v1/health` for adapter source test (connectivity check) [inferred from OpenAPI description]
2. Call `/api/v1/storage/host-path-summary` for the primary data collection — one row per host, flat schema, directly maps to objects [documented in OpenAPI spec as "primary shape consumed by MPB adapters"]
3. Optionally call `/api/v1/storage/host-paths` for LUN-level detail if v2 scope includes LUN objects

**Key alert candidates:**
- `dead_paths > 0` — storage path failure, high severity [inferred from domain knowledge]
- `path_health_pct < 100` — degraded path health, medium severity [inferred from domain knowledge]
- `path_health_pct < 50` — critical path degradation, high severity [inferred from domain knowledge]

## Gaps / Questions

1. **All `datastore_name` values are null.** The lab uses vSAN, so no VMFS datastores back these LUNs. This field will only be populated in environments with VMFS-backed storage. The MP should handle null gracefully (display as "N/A" or omit). [observed 2026-05-13]

2. **`canonical_name` format mismatch.** OpenAPI spec documents this as `"naa.xxx or eui.xxx"` but observed values are long hex strings (e.g., `"02000100006001405d023e190d8940d485ad8bf1d453746f726167"`), not the expected `naa.` prefix format. This may be environment-specific or a data normalization issue in the API. The MP should treat this as an opaque string identifier. [observed 2026-05-13; documented in OpenAPI spec]

3. **`display_name` identical to `canonical_name`.** In all lab observations, `display_name` duplicates `canonical_name` rather than showing a human-friendly vendor model string. In production environments with enterprise storage arrays, this field may carry more descriptive values. [observed 2026-05-13]

4. **No historical data.** The API serves only the current snapshot. There is no endpoint for historical path state or trend data. VCF Operations will need to poll repeatedly and store history itself (which is the normal MP pattern). [observed 2026-05-13]

5. **No per-LUN identifier that is globally unique.** `canonical_name` is unique within a host, but shared LUNs may present the same `canonical_name` on multiple hosts. If LUN becomes an MP object, the identifier must be composite `(hostname, canonical_name)`. [inferred from storage domain knowledge]

6. **Health endpoint `vcenters` status values.** Only `"connected"` has been observed. Other possible values (per the API's status rules: `"error"`, `"collecting"`) have not been seen in live data. [observed 2026-05-13; documented in OpenAPI spec]

7. **`psp_config` always empty.** No non-empty `psp_config` values observed. In environments with custom PSP configurations (e.g., round-robin IOPS limit), this field may carry meaningful data. [observed 2026-05-13]

8. **Transport types limited.** Only `"iscsi"` and `"unknown"` observed. The OpenAPI spec also lists `"fc"` and `"fcoe"` as possible values, but these require Fibre Channel infrastructure not present in the lab. [observed 2026-05-13; documented in OpenAPI spec]
