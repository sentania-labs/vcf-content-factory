# Management Pack Builder (MPB) Research

Research document for building VCF Operations management packs using the
Management Pack Builder tool. Findings sourced from workspace docs, API specs,
and reference MP examples (Dale Hassinger's GitHub, Security Advisories, and
FastAPI management packs).

## What MPB Is

Management Pack Builder (MPB) is a built-in tool within VCF Operations
(formerly Aria Operations / vRealize Operations) that allows users to create
**REST adapter management packs** without writing Java code. It provides a
visual designer that:

1. Connects to a REST API endpoint
2. Maps JSON response fields to VCF Ops object types, metrics, and properties
3. Packages the result as a `.pak` file for installation on any VCF Ops instance
4. Optionally bundles dashboards and views with the management pack

MPB management packs use the **OPENAPI adapter kind** internally — the REST
adapter framework built into VCF Ops that handles HTTP collection, JSON
parsing, and object lifecycle. The MPB UI is a design-time tool; at runtime,
the standard REST adapter engine does the collection.

## MPB JSON Schema (Design-Time Format)

The MPB design is stored as a single JSON file. This is the format you import
into the MPB UI and what the MPB UI exports. It is NOT the `.pak` file — the
`.pak` is a built artifact.

### Top-Level Structure

```json
{
  "design": { ... },       // MP metadata (name, version, author)
  "source": { ... },       // Connection config, auth, test connection
  "requests": [ ... ],     // Collection HTTP requests (one per endpoint)
  "objects": [ ... ],      // Object type definitions (metrics, properties, identifiers)
  "relationships": [ ... ],// Parent-child relationships between object types
  "events": [ ... ],       // Event definitions (map API data to VCF Ops events)
  "content": [ ... ]       // Bundled content (dashboards, views)
}
```

### `design` Section

```json
{
  "design": {
    "design": {
      "id": null,
      "name": "GitHub",
      "type": "HTTP",
      "author": "",
      "version": "1.0.0",
      "description": "Management Pack designed with VMware Aria Operations Management Pack Builder"
    },
    "buildNumber": 2
  }
}
```

| Field | Purpose |
|---|---|
| `name` | MP name — becomes the adapter kind key prefix (`mpb_<lowercase_name>`) |
| `type` | Always `"HTTP"` for REST adapter MPs |
| `version` | Semantic version (major.minor.patch) |
| `buildNumber` | Auto-incremented by MPB UI on each build |
| `author` | Optional string |
| `description` | Shown in the Solutions UI |

**Naming convention**: MPB generates the adapter kind key as
`mpb_<name_lowercased_underscored>`. For example, "Broadcom Security
Advisories" → `mpb_broadcom_security_advisories`. The "world" object (adapter
instance container) gets key `mpb_<name>_world`.

### `source` Section

Contains the connection configuration and authentication settings.

#### `source.source.configuration` — HTTP Connection Settings

```json
{
  "port": 443,
  "hostname": null,
  "maxRetries": 2,
  "sslSetting": "NO_VERIFY",
  "baseApiPath": "api/v2/summary.json",
  "customConfigs": [],
  "minEventSeverity": "WARNING",
  "connectionTimeout": 30,
  "maxConcurrentRequests": 15
}
```

| Field | Purpose |
|---|---|
| `hostname` | Default hostname (null = user-provided at adapter instance creation) |
| `port` | Default port |
| `baseApiPath` | Base URL path prepended to all request paths |
| `sslSetting` | `NO_VERIFY`, `VERIFY`, or `NO_SSL` |
| `connectionTimeout` | Seconds |
| `maxRetries` | Retry count for failed requests |
| `maxConcurrentRequests` | Concurrency limit |
| `customConfigs` | Array of additional custom configuration fields |
| `minEventSeverity` | Minimum severity for event collection |

#### `source.source.authentication` — Credential Schema

```json
{
  "credentialType": "BASIC",
  "sessionSettings": null,
  "creds": [
    {
      "id": "...",
      "label": "Username",
      "usage": "${authentication.credentials.username}",
      "value": null,
      "editable": false,
      "sensitive": false,
      "description": "The username used to connect to the target API"
    },
    {
      "id": "...",
      "label": "Password",
      "usage": "${authentication.credentials.password}",
      "value": null,
      "editable": true,
      "sensitive": true,
      "description": "The password used to connect to the target API"
    }
  ]
}
```

Supported `credentialType` values: `BASIC`, `TOKEN`, `NONE` (at minimum; MPB
UI may offer others).

The `usage` field contains a variable expression that the REST adapter engine
resolves at runtime. For BASIC auth, the global header
`"Authorization": "Basic ${authentication.basic}"` injects the Base64-encoded
credentials.

#### `source.source.globalHeaders` — Default HTTP Headers

```json
[
  {"key": "Content-Type", "type": "REQUIRED", "value": "application/json"},
  {"key": "Authorization", "type": "IMMUTABLE", "value": "Basic ${authentication.basic}"}
]
```

Header `type` values: `REQUIRED` (always sent), `IMMUTABLE` (always sent,
user cannot change).

#### `source.source.testRequest` — Test Connection Endpoint

Defines the request used when clicking "Test Connection" in the adapter
instance configuration UI. Same structure as a collection request but
typically a lightweight health-check endpoint.

#### `source.configuration` — Adapter Instance Configuration Fields

Array of fields presented to the user when creating an adapter instance:

```json
[
  {
    "id": "mpb_hostname",
    "key": "hostname",
    "label": "Hostname",
    "usage": "${configuration.mpb_hostname}",
    "value": null,
    "options": null,
    "advanced": false,
    "editable": false,
    "configType": "STRING",
    "description": "The hostname or IP address...",
    "defaultValue": "www.githubstatus.com"
  }
]
```

| Field | Purpose |
|---|---|
| `key` | Internal identifier |
| `label` | UI display name |
| `configType` | `STRING`, `NUMBER`, `SINGLE_SELECTION` |
| `defaultValue` | Pre-populated value |
| `advanced` | If true, hidden under "Advanced Settings" in UI |
| `editable` | Whether user can change the value (false = MPB-managed) |
| `options` | For `SINGLE_SELECTION`: array of allowed values |
| `usage` | Variable expression for referencing in requests |

Standard MPB-generated config fields (always present):
- `hostname` — target API host
- `port` — target API port
- `connection_timeout_s` — connection timeout
- `max_concurrent_requests` — concurrency limit
- `maximum_retries` — retry count
- `ssl` — SSL mode selection
- `minimum_vmware_aria_operations_severity` — event severity filter

### `requests` Section

Array of HTTP requests that the adapter executes on each collection cycle.

```json
{
  "request": {
    "id": "oqVJW4aRWkv695oysapu8r",
    "body": null,
    "name": "components",
    "path": null,
    "method": "GET",
    "paging": null,
    "params": [],
    "headers": [],
    "designId": null,
    "response": {
      "result": {
        "responseCode": 200,
        "dataModelLists": [ ... ]
      }
    },
    "chainingSettings": null
  }
}
```

| Field | Purpose |
|---|---|
| `name` | Descriptive name for the request |
| `method` | HTTP method (`GET`, `POST`, etc.) |
| `path` | URL path appended to `baseApiPath` (null = use baseApiPath directly) |
| `body` | Request body (for POST/PUT) — can include `${configuration.*}` variables |
| `params` | Query parameters array |
| `headers` | Per-request headers (override globals) |
| `paging` | Pagination configuration (if the API paginates) |
| `chainingSettings` | Request chaining config (output of one request feeds into another) |

#### `response.result.dataModelLists` — Response Data Mapping

This is the core of how MPB maps JSON responses to VCF Ops objects. Each
`dataModelList` represents a path through the JSON response that yields a list
of objects.

```json
{
  "id": "components.*",
  "key": ["components"],
  "label": "components.*",
  "attributes": [
    {
      "id": "...-components.*-id",
      "key": ["id"],
      "label": "id",
      "example": ""
    },
    {
      "id": "...-components.*-name",
      "key": ["name"],
      "label": "name",
      "example": ""
    }
  ],
  "parentListId": "base"
}
```

| Field | Purpose |
|---|---|
| `id` / `label` | JSON path pattern (e.g. `components.*` = iterate over `components` array) |
| `key` | Array of JSON keys forming the path to the list |
| `attributes` | Fields available within each list item |
| `parentListId` | Parent list (for nested structures); `"base"` = root, `null` = top level |

The `base` dataModelList represents top-level (non-array) response fields.

Special attribute `@@@id` is an auto-generated identifier for list items.

### `objects` Section

Defines VCF Ops object types that the MP creates. Each object maps to a
`dataModelList` from a request response.

```json
{
  "object": {
    "id": "jSUk6Xc37GrEgWaDiesohy",
    "type": "INTERNAL",
    "designId": null,
    "metricSets": [ ... ],
    "ariaOpsConf": null,
    "isListObject": true,
    "internalObjectInfo": {
      "id": "...",
      "icon": "ci-cd.svg",
      "identifierIds": ["p4WUtyHcKpR3y8MRZmLxbA"],
      "objectTypeLabel": "components",
      "nameMetricExpression": { ... }
    }
  }
}
```

#### Object `type` Values

| Type | Meaning |
|---|---|
| `INTERNAL` | Custom object type created by this MP — the REST adapter creates and manages these objects |
| `ARIA_OPS` | Maps data onto existing VCF Ops object types (e.g., VirtualMachine, HostSystem) — enriches built-in objects with additional metrics/properties |

**`INTERNAL` is the standard choice** for custom integrations (like Synology).
`ARIA_OPS` is used when augmenting existing monitored objects with data from
an external API (e.g., the FastAPI MP maps tiered memory data onto existing
VMs).

#### `internalObjectInfo`

| Field | Purpose |
|---|---|
| `objectTypeLabel` | Object type display name in VCF Ops |
| `icon` | Icon filename (from MPB's built-in icon set) |
| `identifierIds` | Array of metric IDs that uniquely identify each object instance |
| `nameMetricExpression` | Expression that produces the display name for each object |

#### `metricSets` — Metric/Property Definitions

Each metric set binds a request's `dataModelList` to metrics and properties:

```json
{
  "id": "...",
  "listId": "components.*",
  "requestId": "oqVJW4aRWkv695oysapu8r",
  "metrics": [ ... ],
  "objectBinding": null
}
```

#### Individual Metric Definition

```json
{
  "id": "p4WUtyHcKpR3y8MRZmLxbA",
  "unit": "",
  "isKpi": false,
  "label": "ID",
  "usage": "PROPERTY",
  "groups": [],
  "dataType": "STRING",
  "expression": {
    "expressionText": "@@@MPB_QUOTE 7ci8... @@@MPB_QUOTE",
    "expressionParts": [
      {
        "id": "...",
        "label": "id",
        "regex": null,
        "example": "",
        "originId": "...-components.*-id",
        "originType": "ATTRIBUTE",
        "regexOutput": ""
      }
    ]
  },
  "timeseries": null
}
```

| Field | Purpose |
|---|---|
| `label` | Display name in VCF Ops |
| `usage` | `PROPERTY` (string metadata) or `METRIC` (numeric, time-series) |
| `dataType` | `STRING` or `NUMBER` |
| `isKpi` | Whether this metric is a Key Performance Indicator |
| `unit` | Unit of measure (e.g., `%`, `MB`, `ms`) — empty string = no unit |
| `groups` | Metric groups for organization in the UI |
| `expression` | Maps to a response attribute via `originId` reference |
| `expression.expressionParts[].regex` | Optional regex to extract/transform the raw value |
| `expression.expressionParts[].originType` | `ATTRIBUTE` (from response) or `METRIC` (from another metric) |
| `timeseries` | Time-series configuration (null = default collection interval) |

### `relationships` Section

Defines parent-child relationships between object types:

```json
[
  {
    "relationship": {
      "parentObjectId": "<parent-object-id>",
      "childObjectId": "<child-object-id>"
    }
  }
]
```

All three reference MPs have `relationships: []` — they define flat object
models. For a hierarchical model (e.g., NAS → Volumes → Shares), relationships
would define the tree structure. The relationship IDs reference the `object.id`
fields.

### `events` Section

Maps API response data to VCF Ops events (informational, warning, critical):

```json
[]
```

All three reference MPs have `events: []`. When populated, events allow the MP
to generate VCF Ops events based on API response data — for example, creating
a warning event when a disk health status changes.

### `content` Section

Bundles VCF Ops content (dashboards, views) with the MP:

```json
[
  {
    "content": {
      "id": "...",
      "name": "DBH | Security Advisories | VCF",
      "type": "DASHBOARD",
      "content": {
        "entries": { "resource": [ ... ] },
        "dashboards": [ ... ]
      },
      "designId": null,
      "internalId": "2c90e3a0-..."
    }
  }
]
```

Content is embedded as full dashboard/view JSON within the MP design. The
Security Advisories MP demonstrates this — it bundles a dashboard with a View
widget. Content is exported into the `.pak` file under `content/dashboards/`.

## .pak File Structure

The `.pak` file is a ZIP archive that VCF Ops installs as a solution. MPB
builds this from the JSON design. Structure from the GitHub MP example:

```
/
├── manifest.txt              # MP metadata (JSON)
├── eula.txt                  # License text
├── default.png               # Solution icon
├── adapters.zip              # The REST adapter bundle (bulk of the file)
├── validate.py               # Pre-install validation script
├── preAdapters.py            # Pre-adapter-install script
├── post-install.py           # Post-install script (creates describe.xml, etc.)
├── post-install-fast.sh      # Fast post-install hook
├── postAdapters.py           # Post-adapter-install script
├── content/
│   ├── supermetrics/
│   │   └── customSuperMetrics.json   # Bundled super metrics (empty = "[]" in example)
│   ├── dashboards/
│   │   └── overview.json             # Bundled dashboards
│   ├── reports/                      # Bundled reports
│   ├── views/                        # Bundled views
│   └── files/
│       └── reskndmetric/             # Resource kind metric definitions
└── resources/
    └── resources.properties          # Localization strings
```

### manifest.txt

```json
{
  "display_name": "DISPLAY_NAME",
  "name": "GitHub",
  "description": "Management Pack designed with...",
  "version": "1.0.0.2",
  "run_scripts_on_all_nodes": "true",
  "vcops_minimum_version": "7.5.0",
  "disk_space_required": 500,
  "eula_file": "eula.txt",
  "platform": ["Windows", "Linux Non-VA", "Linux VA"],
  "vendor": "VENDOR",
  "pak_icon": "default.png",
  "license_type": "adapter:mpb_github",
  "pak_validation_script": { "script": "python validate.py" },
  "adapter_pre_script": { "script": "python preAdapters.py" },
  "adapter_post_script": { "script": "python post-install.py" },
  "adapters": ["adapters.zip"],
  "adapter_kinds": ["mpb_github"]
}
```

Key fields:
- `name` — solution name (matches `design.name`)
- `version` — four-part version (`major.minor.patch.buildNumber`)
- `adapter_kinds` — array of adapter kind keys this pak registers
- `license_type` — license key pattern (`adapter:mpb_<name>`)
- `vcops_minimum_version` — minimum VCF Ops version required

## VCF Ops API Surface for Management Pack Lifecycle

### Public API (`/api/`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/solutions` | GET | List all installed solutions (management packs) |
| `/api/solutions/{solutionId}` | GET | Get solution details |
| `/api/solutions/{solutionId}/adapterkinds` | GET | Get adapter kinds for a solution |
| `/api/adapterkinds` | GET | List all adapter types |
| `/api/adapterkinds/{id}` | GET | Get adapter kind details |
| `/api/adapterkinds/{key}/resourcekinds` | GET | List object types for an adapter kind |
| `/api/adapterkinds/{key}/resourcekinds/{rk}/statkeys` | GET | List metric keys for an object type |
| `/api/adapterkinds/{key}/resourcekinds/{rk}/properties` | GET | List property keys for an object type |
| `/api/adapterkinds/{key}/resourcekinds/{rk}/resources` | GET | List resources of a specific kind |
| `/api/adapters` | GET | List all adapter instances |
| `/api/adapters` | POST | Create an adapter instance |
| `/api/adapters` | PUT | Update an adapter instance |
| `/api/adapters` | PATCH | Patch an adapter instance (certificate acceptance) |
| `/api/adapters/{id}` | GET | Get adapter instance details |
| `/api/adapters/{id}` | DELETE | Delete an adapter instance |
| `/api/adapters/testConnection` | POST | Test adapter instance connection |
| `/api/adapters/{id}/monitoringstate/start` | PUT | Start monitoring |
| `/api/adapters/{id}/monitoringstate/stop` | PUT | Stop monitoring |
| `/api/adapters/{id}/resources` | GET | List resources discovered by adapter |
| `/api/resources/adapterkinds/{key}` | POST | Create a resource under an adapter kind |
| `/api/resources/adapters/{id}` | POST | Create a resource under an adapter instance |
| `/api/resources/stats/adapterkinds/{key}` | POST | Push metric data for an adapter kind |
| `/api/resources/properties/adapterkinds/{key}` | POST | Push property data for an adapter kind |
| `/api/collectors` | GET | List collectors |
| `/api/collectors/{id}/adapters` | GET | List adapters on a collector |
| `/api/collectorgroups` | GET/POST/PUT | Manage collector groups |
| `/api/credentials/{id}/adapters` | GET | List adapters using a credential |
| `/api/events/adapterkinds/{key}` | POST | Push events for an adapter kind |

### Internal API (`/internal/`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/internal/adapterkinds/describe` | POST | Upload describe.xml (as string) and trigger Describe operation — **OPENAPI type adapters only** |
| `/internal/adapterkinds/describeupload` | POST | Upload describe.xml (as file) and trigger Describe — **OPENAPI type adapters only** |
| `/internal/adapterkinds/{key}/resourcekinds` | POST | Create a new resource kind under an adapter kind |
| `/internal/solutions/preinstalled` | GET | List preinstalled (bundled) solutions |
| `/internal/solutions/preinstalled/{id}` | GET | Get preinstalled solution details |
| `/internal/solutions/preinstalled/{id}/activate` | POST | Activate a preinstalled solution |
| `/internal/solutions/preinstalled/{id}/deactivate` | POST | Deactivate a preinstalled solution |
| `/internal/solutions/preinstalled/{id}/status` | GET | Get preinstalled solution status |

**Key insight**: The `/internal/adapterkinds/describe` endpoint explicitly
states it works with **OPENAPI type** adapters. This is the adapter kind type
that MPB creates. The describe.xml document defines the adapter's object model
(resource kinds, metrics, properties, relationships) and is what the
`post-install.py` script in the `.pak` file uploads after installation.

### API Workflow for Adapter Instance Lifecycle

From `docs/vcf9/suite-api.md`, the documented workflow for configuring an
adapter instance:

1. **`GET /api/solutions`** — find the installed solution and its adapter kind keys
2. **`GET /api/adapterkinds/{key}/resourcekinds`** — identify object types, find the `ADAPTER_INSTANCE` resource kind and its `resourceIdentifierTypes`
3. **`POST /api/adapters`** — create the adapter instance with:
   - `name`, `description`
   - `collectorId` (which collector node runs collection)
   - `adapterKindKey` (e.g., `mpb_github`)
   - `resourceIdentifiers` (adapter-specific settings like hostname)
   - `credential` (authentication details)
4. **`PATCH /api/adapters`** — accept SSL certificates presented by the target
5. **`PUT /api/adapters/{id}/monitoringstate/start`** — start data collection

### What the API Does NOT Expose

- **No `.pak` install endpoint in the REST API.** Management pack installation
  is done through the VCF Ops UI (Administration → Solutions → Install) or
  via the `$VMWARE_PYTHON_BIN uploadPak.py` CLI on the appliance. The Suite
  API has no `POST /api/solutions` or similar upload endpoint.
- **No MPB design import/export API.** The MPB JSON design file is managed
  exclusively through the MPB UI. There is no REST endpoint to upload a design
  JSON and trigger a build.
- **No `.pak` build API.** Building a `.pak` from a design is done within the
  MPB UI only.

## Workspace Doc Coverage Gaps

### What exists

- `docs/vcf9/suite-api.md` — Documents adapter instance configuration
  workflow with examples (vCenter adapter). Covers solutions, adapter kinds,
  resource kinds, adapter instances, monitoring state.
- `docs/vcf9/policies.md` — Mentions management packs in context of policy
  overrides for specific adapter solutions.
- `docs/vcf9/metrics-properties.md` — References adapter instances in context
  of collection intervals and metric availability.
- `docs/vcf9/dashboards.md` — References "Management Packs Configuration"
  page for adapter-specific XML config files.
- `docs/vcf9/alerts-actions.md` — References management pack adapters in
  symptom definitions.

### What's missing

- **No dedicated MPB documentation** in `docs/vcf9/`. The VCF 9.0 docs cover
  adapter instance management but not the Management Pack Builder tool itself.
- **No describe.xml schema reference.** The internal API mentions describe.xml
  but the full schema (resource kinds, stat keys, property keys) is not
  documented in the workspace.
- **No REST adapter collection engine documentation.** How the adapter engine
  executes requests, maps JSON to objects, handles pagination, manages object
  lifecycle (create/update/delete) is not covered.
- **No `.pak` file format specification.** The manifest schema, required
  scripts, and content structure are only inferable from the reference examples.
- **The VCF 9.0 PDF (`docs/vmware-cloud-foundation-9-0.pdf`) is 8285 pages
  and too large for text extraction.** It likely contains MPB documentation
  but cannot be searched with current tooling.

## Reference MP Comparison

Three MPB examples from Dale Hassinger's repository:

| MP | API Target | Auth | Requests | Object Types | Has Content | Has Relationships |
|---|---|---|---|---|---|---|
| GitHub | githubstatus.com `api/v2/summary.json` | BASIC (unused) | 1 GET | 1 INTERNAL (components) | No (in JSON; Yes in .pak) | No |
| Security Advisories | support.broadcom.com security advisory API | BASIC | 2 POST (VCF, Tanzu) | 2 INTERNAL (VCF, Tanzu) | Yes (1 dashboard) | No |
| FastAPI | Custom FastAPI server | BASIC | 2 GET (tieredVM, tieredHost) | 2 INTERNAL + 2 ARIA_OPS | No | No |

### Patterns Observed

1. **Simple flat object models** — all three MPs create independent object
   types with no parent-child relationships. The relationship and event
   features exist in the schema but none of the examples use them.

2. **PROPERTY vs METRIC distinction** — properties are string metadata
   (status, name, description); metrics are numeric time-series data. The
   GitHub MP uses only properties. The FastAPI MP uses numeric metrics
   (memory sizes in MB). The distinction matters for charting — only METRIC
   values can be graphed over time.

3. **Object identity** — each object type needs at least one metric/property
   designated as the identifier (`identifierIds`). This uniquely identifies
   each object instance across collection cycles. A separate
   `nameMetricExpression` defines the display name.

4. **Multiple requests → multiple object types** — the Security Advisories MP
   uses two POST requests with different request bodies to create two separate
   object types (VCF advisories and Tanzu advisories) from the same API
   endpoint.

5. **ARIA_OPS type for enrichment** — the FastAPI MP demonstrates mapping
   external API data onto existing VCF Ops objects (VMs and Hosts). This
   requires the external API to provide identifiers that match existing
   objects.

6. **Bundled content** — dashboards and views can be embedded directly in the
   MPB JSON design and are exported into the `.pak` under `content/`. The
   Security Advisories MP bundles a dashboard with a View widget.

## Synology MP Handoff Checklist

The following must be resolved before building a Synology DS1520+ management
pack:

### 1. Synology API Documentation

- [ ] **Identify the Synology DSM API endpoints** to collect from. The
  DS1520+ runs DSM (DiskStation Manager) which exposes a REST-like API.
  Key API groups to investigate:
  - `SYNO.DSM.Info` — system info, uptime, temperature
  - `SYNO.Storage.CGI.Storage` — volume/pool/disk status, usage
  - `SYNO.Core.System` — CPU, memory utilization
  - `SYNO.Core.System.Utilization` — real-time resource utilization
  - `SYNO.Core.Share` — shared folder info
  - `SYNO.FileStation.Info` — file station status
  - `SYNO.Core.Network` — network interface info
  - `SYNO.Core.SNMP` — SNMP configuration (alternative data source)

- [ ] **Document authentication flow.** Synology DSM API typically uses:
  1. `POST /webapi/auth.cgi` with `api=SYNO.API.Auth&method=login` → returns
     `sid` (session ID)
  2. Subsequent requests include `_sid=<session_id>` as a parameter
  
  Determine if MPB supports session-based auth (the `sessionSettings` field in
  the auth schema exists but is `null` in all examples). If not, investigate
  whether DSM supports API tokens or whether a token-refresh wrapper is needed.

- [ ] **Verify API availability and version** on the DS1520+ running current
  DSM. Use `GET /webapi/query.cgi?api=SYNO.API.Info&version=1&method=query`
  to enumerate available APIs and their paths/versions.

### 2. Object Model Design

- [ ] **Define the object type hierarchy.** Proposed model:

  ```
  Synology NAS (adapter instance / world object)
  ├── System                    (1:1 — CPU, memory, temp, uptime)
  ├── Volume                    (1:N — each storage volume)
  │   └── Disk                  (1:N — physical disks in volume)
  ├── Network Interface         (1:N — each NIC)
  └── Shared Folder             (1:N — each share)
  ```

- [ ] **Decide which model elements are INTERNAL vs ARIA_OPS.** All should be
  INTERNAL since these are new object types not mapping onto existing VCF Ops
  objects.

- [ ] **Define parent-child relationships.** Unlike the reference MPs (all
  flat), a NAS object model benefits from hierarchy: NAS → Volumes → Disks.
  This requires using the `relationships` section.

### 3. Metrics and Properties Per Object Type

- [ ] **System object**: CPU usage (%), memory usage (%), memory total,
  temperature (°C), uptime (seconds/days), DSM version, model name,
  serial number

- [ ] **Volume object**: total size, used size, usage percentage, status
  (normal/degraded/crashed), volume type (SHR/RAID5/etc.), file system type

- [ ] **Disk object**: model, serial, firmware version, temperature,
  S.M.A.R.T. status (healthy/warning/failing), size, disk type (HDD/SSD/NVMe),
  allocation status

- [ ] **Network Interface object**: name, MAC address, link status, speed,
  bytes sent/received (counters → rate metrics)

- [ ] **Shared Folder object**: name, path, total size, used size, usage
  percentage, encryption status

- [ ] **Classify each as METRIC (numeric, chartable) or PROPERTY (string,
  metadata).** Rule of thumb: if you'd graph it over time, it's a METRIC.

### 4. Credential Schema

- [ ] **Determine credential type.** Options:
  - BASIC (username/password) — straightforward if DSM API supports basic auth
    or if MPB can do session auth
  - TOKEN — if using API tokens
  - Custom credential fields may be needed for Synology 2FA scenarios

- [ ] **Test whether MPB's session auth feature works** with Synology's
  `SYNO.API.Auth` login flow. The `sessionSettings` field in the auth schema
  may support cookie/token-based sessions.

### 5. Collection Strategy

- [ ] **Define collection intervals.** Consider:
  - System metrics (CPU, memory, temp): 5-minute default
  - Volume/disk status: 5-minute (status changes are important)
  - Network counters: 5-minute (rate calculation needs consistent intervals)
  - Shared folder sizes: 15-30 minute (less volatile)

- [ ] **Pagination** — determine if any Synology API responses are paginated
  and configure the `paging` settings accordingly.

- [ ] **Request count** — plan the minimum number of HTTP requests per
  collection cycle. Each API group may need a separate request. Minimize
  request count for collection efficiency.

### 6. Build and Test Plan

- [ ] **Build the MPB JSON design** — author the design JSON with all object
  types, metrics, requests, and relationships.
- [ ] **Import into MPB UI** — load the JSON and test connection against the
  DS1520+.
- [ ] **Validate collection** — verify all object types are discovered and
  metrics are populated.
- [ ] **Build .pak** — export from MPB as a .pak file.
- [ ] **Test installation** — install .pak on a test VCF Ops instance.
- [ ] **Build dashboards/views** — create monitoring dashboards (can be done
  in MPB or via the VCF Content Factory's existing tooling).
- [ ] **Define alerts/symptoms** — create symptom definitions and alert
  definitions for critical conditions (disk failure, volume degraded, high
  temp, low space).

### 7. Open Questions

- [ ] Can MPB JSON designs be authored programmatically (outside the UI) and
  imported? The reference examples suggest yes — the JSON format is
  self-contained.
- [ ] Does the MPB UI exist in VCF Ops 9.0.2, or was it deprecated/removed
  in the Broadcom transition? Need to verify on the lab instance.
- [ ] Is there a way to build `.pak` files without the MPB UI (CLI tooling,
  scripting the ZIP assembly)?
- [ ] Can the VCF Content Factory's existing content tooling (views,
  dashboards, super metrics) work with MPB adapter kind objects, or does the
  adapter kind key format (`mpb_*`) require special handling?
- [ ] What is the maximum collection frequency supported by MPB adapters?
  Real-time monitoring is likely not available for REST adapters.
