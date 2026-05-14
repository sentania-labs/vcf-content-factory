# MPB template.json Schema Specification

Reverse-engineered from the working Synology NAS template.json
(`vcfops_managementpacks/adapter_runtime/mpb_synology_nas_template.json`)
and validated against `BuilderFileParseException` errors from failed
UniFi Integration pak installs (rounds 1-5, 2026-05-08 through 2026-05-09).

The template.json lives at `conf/template.json` inside a `.pak` file
and is parsed by `BuilderFile.Companion.read()` in the MPB adapter
runtime JAR. It is **not** the same format as the MPB UI
export/design.json -- the schemas are substantially different despite
carrying the same logical content.

---

## 1. Top-level structure

```json
{
  "id": "<uuid>",
  "name": "<string>",
  "pakSettings": { ... },
  "source": { ... },
  "constants": [],
  "relationships": [ ... ]
}
```

**Key difference from design.json:** template.json has NO top-level
`"version"` field. Design.json has `"version": 1`.

---

## 2. pakSettings

### template.json (REQUIRED)

```json
{
  "author": "Management Pack Builder",
  "name": "Synology NAS",
  "adapterKind": "mpb_synology_nas",
  "version": "1.0.0.1",
  "description": "...",
  "icon": "default.svg",
  "collectionInterval": 5
}
```

### design.json (our render output)

```json
{
  "adapterKind": "mpb_vcf_content_factory_unifi_integration",
  "author": "VCF Content Factory",
  "name": "VCF Content Factory UniFi Integration",
  "version": "1.0.0",
  "description": "...",
  "icon": "default.png"
}
```

### Differences

| Field | template.json | design.json | Notes |
|-------|---------------|-------------|-------|
| `version` | `"1.0.0.1"` (4-part) | `"1.0.0"` (3-part) | **BREAKING.** Parser requires `Major.Minor.Patch.Build` format. Must be 4-part. |
| `collectionInterval` | `5` (integer, minutes) | ABSENT | Required by template. Our YAML has this field; renderer must emit it. |
| `icon` | `"default.svg"` | `"default.png"` | Likely cosmetic, but SVG is correct for MPB adapter runtime icons. |

---

## 3. source (top level)

### template.json

```json
{
  "basePath": "webapi",
  "testRequestId": "<uuid>",
  "authentication": { ... },
  "configuration": [ ... ],
  "requests": { ... },
  "resources": [ ... ],
  "externalResources": [],
  "events": [],
  "type": "HTTP"
}
```

### design.json

```json
{
  "type": "HTTP",
  "basePath": "",
  "testRequestId": "<uuid>",
  "authentication": { ... },
  "configuration": [ ... ],
  "globalHeaders": [ ... ],
  "requests": { ... },
  "resources": [ ... ],
  "externalResources": [],
  "events": []
}
```

### Differences

| Field | template.json | design.json | Notes |
|-------|---------------|-------------|-------|
| `globalHeaders` | ABSENT | Present | **BREAKING (extra field).** Error message: `SOURCE error: Extra field: 'globalHeaders'`. Headers must be moved into `authentication.headers`. |
| `type` | Present at end (`"HTTP"`) | Present at start | Same value, position irrelevant for JSON. |

---

## 4. source.authentication

### template.json (SESSION_TOKEN type)

```json
{
  "credentials": [
    {
      "id": "<uuid>",
      "key": "username",
      "label": "username",
      "sensitive": false,
      "description": "username for authentication"
    }
  ],
  "headers": [
    {
      "id": "Content-Type",
      "enabled": true,
      "key": "Content-Type",
      "value": "application/json"
    },
    {
      "id": "id",
      "enabled": true,
      "key": "id",
      "value": "${authentication.session.set_cookie}"
    }
  ],
  "token": {
    "getSession": { <request object> },
    "releaseSession": { <request object> },
    "responseFields": [
      {
        "id": "<uuid>",
        "key": "set_cookie",
        "path": ["Set-Cookie"],
        "location": "HEADER"
      }
    ],
    "credentialType": "CUSTOM"
  },
  "type": "SESSION_TOKEN"
}
```

### design.json

```json
{
  "creds": [ ... ],
  "credentialType": "CUSTOM",
  "sessionSettings": { ... } | null
}
```

### Differences (LARGEST GAP)

| Field | template.json | design.json | Notes |
|-------|---------------|-------------|-------|
| `type` | `"SESSION_TOKEN"` | ABSENT | **BREAKING (missing).** Required. Values: `SESSION_TOKEN`, `BASIC`, likely others. |
| `credentials` | Array of `{id, key, label, sensitive, description}` | `creds` | **BREAKING (missing key name).** template calls it `credentials`, design calls it `creds`. |
| `headers` | Array of `{id, enabled, key, value}` | ABSENT (in `globalHeaders` instead) | **BREAKING (missing).** Global headers in design.json must become `authentication.headers` in template. |
| `token` | Object with `{getSession, releaseSession, responseFields, credentialType}` | `sessionSettings` + `credentialType` at auth level | **BREAKING structure.** template nests `credentialType` inside `token`, not at auth root. |
| `token.getSession` | template request format | design request format | Different request schemas (see section 5). |
| `token.responseFields` | `[{id, key, path, location}]` | `sessionVariables` `[{id, key, path, usage, example, location}]` | Different key name AND different field set. |

### Credential object mapping

| template.json | design.json |
|---------------|-------------|
| `credentials[].id` | `creds[].id` |
| `credentials[].key` | (derive from `creds[].label`) |
| `credentials[].label` | `creds[].label` |
| `credentials[].sensitive` | `creds[].sensitive` |
| `credentials[].description` | `creds[].description` |
| (no `usage` field) | `creds[].usage` |
| (no `editable` field) | `creds[].editable` |
| (no `value` field) | `creds[].value` |

### Authentication type mapping

The template.json `authentication.type` field is the auth strategy
discriminator. Known values:
- `SESSION_TOKEN` -- login/logout flow (Synology, cookie_session preset)
- `CUSTOM` -- stateless header-based auth (http_header preset). **Inferred
  from design.json equivalents** (jcox UniFi, HoL GitLab-Basic both use
  `credentialType: "CUSTOM"` + `sessionSettings: null`); no template.json
  ground truth for this case has been captured yet.

We have NO template.json ground truth for stateless API-key auth. The
only template.json we possess (Synology) uses `SESSION_TOKEN`. All
other references (jcox UniFi, HoL GitLab-Basic, phpIPAM, Rubrik) are
in design.json (UI export) format, which uses
`credentialType: "CUSTOM"` + `sessionSettings: null` -- but that's a
different schema.

The factory currently emits `"type": "CUSTOM"` for the `http_header`
preset (see `render_template.py:_convert_authentication()`). This has
not been confirmed against a live MPB-built pak with stateless auth;
if collection fails on first cycle, capturing a live MPB stateless-auth
template.json is the next diagnostic step.

**Confirmed describe.xml credential pattern** (2026-05-09):
All MPB-built reference paks (GitHub, Broadcom, Rubrik, Synology) emit
exactly two credential fields: `password="false"` at nameKey=3 and
`password="true"` at nameKey=4. The adapter instance ResourceKind
(type=7) starts at nameKey=5 (immediately sequential).

The `http_header` preset emits one credential field (`api_key`,
`password="true"`) at nameKey=3, making the adapter instance kind
start at nameKey=4. This deviates from the reference two-field pattern;
whether VCF Ops requires two credential fields for the credential dialog
to render correctly is **unconfirmed**. If the credential dialog shows
the credential form but no fields, adding a synthetic non-sensitive field
is the fallback fix.

**Confirmed bug (2026-05-09)**: The committed version of
`builder.py:_append_credential_kinds()` did NOT include `http_header`
in its preset handling. The `http_header` preset fell through all
`if/elif` branches, emitting an empty `<CredentialKind>` container with
NO `<CredentialField>` elements. This caused the credential dialog to
show with no input fields. Fix: add `"http_header"` to the
`("basic_auth", "cookie_session", "http_header")` preset check.

**Confirmed bug (2026-05-09)**: The nameKey counter for ResourceKinds
was hardcoded to start at 10, creating a gap from the last credential
field nameKey (e.g., 3→10 for single-credential adapters). All
MPB-built reference paks use sequential nameKeys with no gaps. Fix:
start `name_key_counter` at `max(labels.keys()) + 1` after
`_append_credential_kinds` populates the labels dict.

---

## 5. source.requests

### template.json request format

```json
{
  "<uuid>": {
    "id": "<uuid>",
    "name": "storage_info",
    "path": "entry.cgi",
    "method": "GET",
    "headers": [],
    "body": "",
    "params": [
      {
        "id": "api",
        "key": "api",
        "value": "SYNO.Core.System"
      }
    ],
    "parentRequest": null | {
      "id": "<uuid>",
      "requestId": "<parent-request-uuid>",
      "parameters": [
        {
          "id": "volume_id",
          "listExpression": "${@@@MPB_QUOTE_BODY data.volumes.* @@@MPB_QUOTE}",
          "attributeExpression": "${@@@MPB_QUOTE_BODY volume_id @@@MPB_QUOTE}"
        }
      ]
    },
    "paging": null | {
      "id": "<uuid>",
      "type": "OFFSET",
      "pagingParam": "offset",
      "limitParam": "limit",
      "limitValue": 100,
      "pagingStart": 0,
      "listPath": ["data", "hdd_info"]
    }
  }
}
```

### design.json request format

```json
{
  "<uuid>": {
    "id": "<uuid>",
    "body": null,
    "name": "sites",
    "path": "/proxy/network/integration/v1/sites",
    "method": "GET",
    "paging": null,
    "params": [
      {
        "key": "filter",
        "value": "features.contains('accessPoint')"
      }
    ],
    "headers": [],
    "designId": null,
    "response": {
      "id": "<uuid>",
      "log": "Imported request, execute to get accurate log",
      "result": { ... },
      "status": "COMPLETED",
      ...
    },
    "chainingSettings": null | {
      "id": "<uuid>",
      "parentRequestId": "<uuid>",
      "baseListId": "data.*",
      "params": [
        {
          "id": "<uuid>",
          "key": "site_id",
          "label": "site_id",
          "usage": "${requestParameters.site_id}",
          "listId": "data.*",
          "example": "",
          "attributeExpression": { ... }
        }
      ]
    }
  }
}
```

### Differences

| Field | template.json | design.json | Notes |
|-------|---------------|-------------|-------|
| `designId` | ABSENT | Present (always null) | **BREAKING (extra).** Must be omitted. |
| `response` | ABSENT | Present (full response mock) | **BREAKING (extra).** Must be omitted. |
| `chainingSettings` | ABSENT | Present | **BREAKING (extra).** Must be converted to `parentRequest` format. |
| `parentRequest` | Present (chaining info) | ABSENT | Must be synthesized from `chainingSettings`. |
| `body` | `""` (empty string) | `null` | Template uses empty string, not null. |
| `params[].id` | Present (same as `key`) | ABSENT | **BREAKING (missing `id`).** Each param needs `"id": "<same-as-key>"`. Error: `QUERY_PARAMETER error: Missing field: 'id'`. |
| `paging` | Complex object when present | Always null in design | Template has full paging config; design.json never emits it. |

### Chaining format conversion

Template `parentRequest`:
```json
{
  "id": "<uuid>",
  "requestId": "<parent-request-uuid>",
  "parameters": [
    {
      "id": "volume_id",
      "listExpression": "${@@@MPB_QUOTE_BODY data.volumes.* @@@MPB_QUOTE}",
      "attributeExpression": "${@@@MPB_QUOTE_BODY volume_id @@@MPB_QUOTE}"
    }
  ]
}
```

Design `chainingSettings`:
```json
{
  "id": "<uuid>",
  "parentRequestId": "<uuid>",
  "baseListId": "data.*",
  "params": [
    {
      "id": "<uuid>",
      "key": "site_id",
      "label": "site_id",
      "usage": "${requestParameters.site_id}",
      "listId": "data.*",
      "example": "",
      "attributeExpression": {
        "id": "<uuid>",
        "expressionText": "@@@MPB_QUOTE <uuid> @@@MPB_QUOTE",
        "expressionParts": [ ... ]
      }
    }
  ]
}
```

The conversion is:
- `chainingSettings.parentRequestId` -> `parentRequest.requestId`
- `chainingSettings.params[].key` -> `parentRequest.parameters[].id`
- `chainingSettings.baseListId` -> `listExpression` in `@@@MPB_QUOTE_BODY` format
- `chainingSettings.params[].attributeExpression.expressionParts[0].label` -> `attributeExpression` in `@@@MPB_QUOTE_BODY` format

**Critical: `attributeExpression` is the field name from the parent response,
NOT the parameter name.**

`parameters[].id` is the request parameter name (used in the URL path, e.g.
`${requestParameters.device_id}`). `attributeExpression` is the JSON field to
extract from each row of the parent response body (e.g. `id`). These are the
same only when `YAML bind.name == bind.from_attribute` (e.g. Synology's
`volume_id == volume_id`). When they differ (e.g. UniFi's
`name=device_id, from_attribute=id`), using `parameters[].id` in
`attributeExpression` causes the runtime to look for a non-existent field,
yielding empty substitution → broken URLs → zero devices discovered.

The correct source is `chainingSettings.params[].attributeExpression.expressionParts[0].label`.

**Confirmed bug and fix (2026-05-09):** `render_template.py:_convert_chaining_settings()`
was incorrectly using `cp["key"]` (the param name) instead of
`cp["attributeExpression"]["expressionParts"][0]["label"]` (the field name).
Fixed in this commit. The Synology MP was unaffected because `volume_id == volume_id`
masked the bug.

---

## 6. source.resources (LARGEST STRUCTURAL GAP)

### template.json resource format

```json
{
  "id": "<uuid>",
  "label": "Storage Pool",
  "resourceKind": "mpb_synology_nas_storage_pool",
  "name": {
    "id": "<uuid>",
    "type": "PROPERTY",
    "refId": "<metric-uuid-that-provides-the-name>"
  },
  "identifiers": [
    {
      "id": "<uuid>",
      "key": "id",
      "propertyKey": "id"
    }
  ],
  "isListResource": true,
  "icon": "data-cluster.svg",
  "requestedMetrics": [
    {
      "id": "<uuid>",
      "requestId": "<request-uuid>",
      "metrics": [
        {
          "id": "<uuid>",
          "expression": "${@@@MPB_QUOTE_BODY device_type @@@MPB_QUOTE}",
          "key": "device_type",
          "label": "Device Type",
          "dataType": "STRING",
          "property": true,
          "kpi": false,
          "groups": [],
          "unit": null,
          "timeseries": null
        }
      ],
      "objectBinding": null,
      "listExpression": "${@@@MPB_QUOTE_BODY data.pools.* @@@MPB_QUOTE}"
    }
  ],
  "metricGroups": {}
}
```

### design.json resource format

```json
{
  "id": "<uuid>",
  "type": "INTERNAL",
  "designId": null,
  "metricSets": [
    {
      "id": "<uuid>",
      "listId": "data.*",
      "requestId": "<request-uuid>",
      "metrics": [
        {
          "id": "<uuid>",
          "unit": "",
          "isKpi": false,
          "label": "Device ID",
          "usage": "PROPERTY",
          "groups": [],
          "dataType": "STRING",
          "expression": {
            "id": "<uuid>",
            "expressionText": "@@@MPB_QUOTE <uuid> @@@MPB_QUOTE",
            "expressionParts": [
              {
                "id": "<uuid>",
                "label": "id",
                "regex": null,
                "example": "",
                "originId": "<request-uuid>-data.*-id",
                "originType": "ATTRIBUTE",
                "regexOutput": ""
              }
            ]
          },
          "timeseries": null
        }
      ],
      "objectBinding": null | { ... }
    }
  ],
  "ariaOpsConf": null,
  "isListObject": true,
  "internalObjectInfo": {
    "id": "<uuid>",
    "icon": "wireless-access-point.svg",
    "identifierIds": ["<metric-uuid>"],
    "objectTypeLabel": "Access Point",
    "nameMetricExpression": { ... }
  }
}
```

### Field-by-field mapping

| template.json field | design.json field | Conversion |
|---------------------|-------------------|------------|
| `label` | `internalObjectInfo.objectTypeLabel` | Direct copy |
| `resourceKind` | ABSENT | Synthesize: `{adapterKind}_{snake_case(objectTypeLabel)}` |
| `name` | `internalObjectInfo.nameMetricExpression` | Convert expression to `{id, type:"PROPERTY", refId}` |
| `identifiers` | `internalObjectInfo.identifierIds` | For each id, look up the metric to get key/propertyKey |
| `isListResource` | `isListObject` | Direct rename |
| `icon` | `internalObjectInfo.icon` | Direct copy |
| `requestedMetrics` | `metricSets` | Deep conversion (see below) |
| `metricGroups` | ABSENT | Always `{}` |
| ABSENT | `type` ("INTERNAL") | **Extra -- must omit** |
| ABSENT | `designId` | **Extra -- must omit** |
| ABSENT | `ariaOpsConf` | **Extra -- must omit** |
| ABSENT | `isListObject` | Rename to `isListResource` |
| ABSENT | `internalObjectInfo` | Decompose into `label`, `name`, `identifiers`, `icon` |

### Metric format conversion (requestedMetrics.metrics)

| template.json | design.json | Notes |
|---------------|-------------|-------|
| `expression` (string) | `expression` (object) | Template: `"${@@@MPB_QUOTE_BODY field @@@MPB_QUOTE}"`. Design: `{id, expressionText, expressionParts}`. Must flatten. |
| `key` | ABSENT | Synthesize from expression label. Must be lower-case snake_case (e.g. `"tx_rate_bps"`). No camelCase, no `\|`, no `:`. The `_derive_key()` helper enforces this. |
| `property` (bool) | `usage` ("PROPERTY" or "METRIC") | Convert: `usage == "PROPERTY"` -> `property: true` |
| `kpi` (bool) | `isKpi` (bool) | Rename |
| `dataType` | `dataType` | Values differ: template uses `"STRING"`, `"DECIMAL"`. Design uses `"STRING"`, `"NUMBER"`. `NUMBER` -> `DECIMAL`. |
| `unit` (null or string) | `unit` (string, often empty `""`) | Convert empty string to null. |

### objectBinding conversion

**Rule:** At most ONE `requestedMetrics[]` entry per resource may have
`objectBinding: null`. That one must be the primary/chain-parent metricSet.
Every chained secondary metricSet (those with a `parentRequest` in the
corresponding request) MUST carry a non-null `objectBinding`.

`BuilderFile.Companion.read()` raises:
> "Multiple groups of metrics from 'metricRequests' were not given an
> object binding. Only one per resource can be null."
if this rule is violated.

Additionally, `resourceMatchers` must be a non-empty array (at least one
entry). An empty `resourceMatchers: []` triggers:
> "OBJECT_BINDING error: Field requires at least one value in the array."

#### Type 1 — null (primary / chain-parent)
```json
null
```

#### Type 2 — ATTRIBUTE_TO_PROPERTY (chained secondary, N+1 pattern)
This is the shape for stats requests that fire once per device
(e.g. UniFi `/statistics/latest` per device, Synology volume-stats per volume).

Template format (confirmed from prod error analysis, round 5, 2026-05-09):
```json
{
  "type": "ATTRIBUTE_TO_PROPERTY",
  "id": "<uuid5-seeded-from-http-ob-{matchExpression.id}>",
  "requestMatchIdExpression": "${@@@MPB_QUOTE_BODY id @@@MPB_QUOTE}",
  "resourceMatcherExpression": "${<matcher-uuid>}",
  "resourceMatchers": [
    {
      "id": "<matcher-uuid>",
      "type": "IDENTIFIER",
      "key": "<prop_key>",
      "regex": null
    }
  ]
}
```

**Critical cross-reference contract:**
- `requestMatchIdExpression` uses `@@@MPB_QUOTE_BODY` format — it is the
  JSON attribute path in the secondary response (from
  `design.matchExpression.expressionParts[0].label`, e.g. `"id"`).
- `resourceMatcherExpression` uses **`${<uuid>}` format only** — the UUID
  inside `${...}` must exactly match `resourceMatchers[0].id`. Do NOT use
  `@@@MPB_QUOTE_BODY` here. Using `@@@MPB_QUOTE_BODY` causes:
  > "fields referenced in the resource expression but do not have a
  > matching ID in match identifiers: [@@@MPB_QUOTE_BODY id @@@MPB_QUOTE]"
  because the parser treats the entire `@@@MPB_QUOTE_BODY id @@@MPB_QUOTE`
  string as the identifier name to look up in `resourceMatchers[].id`.
- `resourceMatchers[0].id` is a stable UUID5 (`_make_id("http-ob-matcher-{matchExpression.id}")`).
- `resourceMatchers[0].key` is the derived snake_case property key (from
  `_derive_key(_get_metric_expr_label(referenced_metric))`).

This `${uuid}` vs `${@@@MPB_QUOTE_BODY}` distinction mirrors the
relationships format exactly (see section 8): relationship
`expression` fields also use `${<uuid>}` to reference `matchIdentifiers[].id`.

**Fields from design.json to omit:**
- `matchExpression` and `objectMatchExpression` are design-time objects.
  The template parser does not accept them; they drive only the renderer logic.

**Derivation of `resource_prop` (the property key):**
1. From `design.objectMatchExpression.expressionParts[0].originId`, look up
   the metric in `metrics_by_id`.
2. Extract `expressionParts[0].label` from that metric's expression.
3. Apply `_derive_key()` to get the snake_case key.
4. Fallback: if the metric is not found, apply `_derive_key(request_attr)`
   (same attribute as `requestMatchIdExpression`).

#### Type 3 — CHAINED_REQUEST
```json
{
  "type": "CHAINED_REQUEST",
  "id": "<uuid5>"
}
```
Rare; used when the binding type in the design is already CHAINED_REQUEST.

---

## 7. source.configuration

### template.json

```json
{
  "id": "<uuid>",
  "key": "mpb_hostname",
  "label": "Hostname",
  "advanced": false,
  "default": "",
  "description": "The hostname used to connect to the target API.",
  "type": "STRING"
}
```

### design.json

```json
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
  "description": "Host name or IP address of the target device.",
  "defaultValue": null
}
```

### Differences

| Field | template.json | design.json | Notes |
|-------|---------------|-------------|-------|
| `key` | `"mpb_hostname"` | `"hostname"` | Template uses the mpb_ prefixed key. |
| `type` | Present (`"STRING"`, `"INTEGER"`, `"SINGLE_SELECTION"`) | `configType` | **BREAKING (missing `type`).** Must rename `configType` -> `type`. Also: `"NUMBER"` -> `"INTEGER"`. |
| `default` | Present (string) | `defaultValue` | Must rename and convert. In template, all defaults are strings (even numbers: `"30"`, `"2"`). |
| `options` | Present on SINGLE_SELECTION items | Present | Same structure. |
| ABSENT | `usage` | Extra -- must omit. |
| ABSENT | `value` | Extra -- must omit. |
| ABSENT | `editable` | Extra -- must omit. |
| ABSENT | `defaultValue` | Rename to `default`. |

### SINGLE_SELECTION default requirement

`SINGLE_SELECTION` config params must have a non-empty `default` value.
If `design.defaultValue` is null/empty, the renderer falls back to:
1. `"Verify"` if that string is in the `options` list (matches Synology ground truth)
2. Otherwise, `options[0]`

An empty-string default on a SINGLE_SELECTION param causes a parse error.

### Required configuration fields

The parser mandates these `key` values exist:
- `mpb_hostname`
- `mpb_port`
- `mpb_connection_timeout`
- `mpb_concurrent_requests`
- `mpb_max_retries`
- `mpb_ssl_config`
- `mpb_min_event_severity`

Our renderer already emits all seven, but with wrong field names
(e.g., `configType` instead of `type`).

---

## 8. relationships

### template.json

```json
{
  "id": "<uuid>",
  "parent": {
    "id": "<uuid>",
    "resourceKind": "mpb_synology_nas_storage_pool",
    "adapterKind": "mpb_synology_nas",
    "resourceKindName": "Storage Pool",
    "expression": "${<match-id>}",
    "matchIdentifiers": [
      {
        "id": "<uuid>",
        "type": "IDENTIFIER",
        "key": "pool_path",
        "regex": null
      }
    ]
  },
  "child": {
    "id": "<uuid>",
    "resourceKind": "mpb_synology_nas_volume",
    "adapterKind": "mpb_synology_nas",
    "resourceKindName": "Volume",
    "expression": "${<match-id>}",
    "matchIdentifiers": [
      {
        "id": "<uuid>",
        "type": "PROPERTY",
        "key": "pool_path",
        "regex": null
      }
    ]
  },
  "caseSensitive": true
}
```

### design.json

```json
{
  "id": "<uuid>",
  "name": "storage_pool -> volume",
  "designId": null,
  "caseSensitive": true,
  "childObjectId": "<uuid>",
  "parentObjectId": "<uuid>",
  "childExpression": {
    "id": "<uuid>",
    "expressionText": "@@@MPB_QUOTE <uuid> @@@MPB_QUOTE",
    "expressionParts": [ ... ]
  },
  "parentExpression": { ... }
}
```

### Differences

Completely different structure. Template uses `parent`/`child` objects
with `resourceKind`, `adapterKind`, `resourceKindName`,
`matchIdentifiers`. Design uses `parentObjectId`/`childObjectId`
references + expression objects.

The conversion requires:
1. Resolve `parentObjectId`/`childObjectId` to resource objects
2. Derive `resourceKind` and `adapterKind` from the resource
3. Build `matchIdentifiers` from the expression parts
4. Wrap in `parent`/`child` containers

---

## 9. Complete field inventory

### Fields present in template but absent from design (must ADD)

| Section | Field | Source |
|---------|-------|--------|
| (top) | (no `version` key) | Omit from output |
| pakSettings | `collectionInterval` | From YAML `collection_interval` |
| pakSettings.version | 4-part format | Append `.0` or `.BUILD` |
| source.authentication | `type` | `"SESSION_TOKEN"` or determine from YAML auth config |
| source.authentication | `credentials` (not `creds`) | Rename from `creds` |
| source.authentication | `headers` | Move from `globalHeaders` |
| source.authentication.token | `getSession`, `releaseSession`, `responseFields`, `credentialType` | Restructure from `sessionSettings` |
| source.requests[].params[] | `id` (on each param) | Set `id = key` |
| source.requests[] | `parentRequest` | Convert from `chainingSettings` |
| source.resources[] | `label` | From `internalObjectInfo.objectTypeLabel` |
| source.resources[] | `resourceKind` | Synthesize from adapterKind + objectTypeLabel |
| source.resources[] | `name` | From `internalObjectInfo.nameMetricExpression` |
| source.resources[] | `identifiers` | From `internalObjectInfo.identifierIds` |
| source.resources[] | `isListResource` | Rename from `isListObject` |
| source.resources[] | `icon` | From `internalObjectInfo.icon` |
| source.resources[] | `requestedMetrics` | Convert from `metricSets` |
| source.resources[] | `metricGroups` | Always `{}` |
| source.resources[].requestedMetrics[].metrics[] | `key` | Synthesize from expression |
| source.resources[].requestedMetrics[].metrics[] | `property` | From `usage` |
| source.resources[].requestedMetrics[].metrics[] | `expression` (string form) | Flatten from expression object |
| source.resources[].requestedMetrics[] | `listExpression` | From metricSet `listId` |
| source.configuration[] | `type` | Rename from `configType` |
| source.configuration[] | `default` | Rename from `defaultValue`, stringify |

### Fields present in design but absent from template (must OMIT)

| Section | Field |
|---------|-------|
| (top) | `version` |
| source | `globalHeaders` |
| source.authentication | `creds` (rename to `credentials`) |
| source.authentication | `sessionSettings` (restructure to `token`) |
| source.requests[] | `designId` |
| source.requests[] | `response` |
| source.requests[] | `chainingSettings` (convert to `parentRequest`) |
| source.resources[] | `type` |
| source.resources[] | `designId` |
| source.resources[] | `metricSets` (convert to `requestedMetrics`) |
| source.resources[] | `ariaOpsConf` |
| source.resources[] | `isListObject` (rename to `isListResource`) |
| source.resources[] | `internalObjectInfo` (decompose) |
| source.resources[].metricSets[].metrics[] | `usage` (convert to `property`) |
| source.resources[].metricSets[].metrics[] | `isKpi` (rename to `kpi`) |
| source.resources[].metricSets[].metrics[] | `expression` (object form; flatten) |
| source.configuration[] | `usage` |
| source.configuration[] | `value` |
| source.configuration[] | `editable` |
| source.configuration[] | `configType` (rename to `type`) |
| source.configuration[] | `defaultValue` (rename to `default`) |
| relationships[] | `name` |
| relationships[] | `designId` |
| relationships[] | `childObjectId` (restructure) |
| relationships[] | `parentObjectId` (restructure) |
| relationships[] | `childExpression` (restructure) |
| relationships[] | `parentExpression` (restructure) |

---

## 10. Recommended implementation approach

**Option A: Transform design.json to template.json** (recommended)

The design.json contains all the semantic information needed. A
`render_template_json()` function should:

1. Start from the existing `render()` output (design.json)
2. Apply section-by-section transformations:
   - Strip `version` from top level
   - Fix `pakSettings.version` to 4-part, add `collectionInterval`
   - Restructure `authentication` (rename fields, move headers, restructure token)
   - Transform each request (strip response/designId/chainingSettings, add parentRequest, add param ids)
   - Transform each resource (decompose internalObjectInfo, rename fields, flatten metric expressions)
   - Transform configuration (rename fields, stringify defaults)
   - Transform relationships (restructure to parent/child containers)
3. Output as the `conf/template.json` in the pak build

**Option B: Render from YAML directly to template format**

More work but avoids the design.json intermediate. Only worthwhile if
the design.json format is also changing. Not recommended given current
codebase maturity.

### Conversion priority (by error severity)

1. **pakSettings.version** -- trivial fix, append `.0`
2. **source.requests[].params[].id** -- trivial, set `id = key`
3. **source.requests[] extra fields** -- strip `designId`, `response`, `chainingSettings`
4. **source.authentication** -- moderate: restructure `creds`->`credentials`, add `type`/`headers`, restructure `token`
5. **source.resources[]** -- HARDEST: full structural transformation
6. **source.configuration[].type** -- trivial rename
7. **source globalHeaders** -- move to auth headers, remove from source
8. **relationships** -- moderate: restructure to parent/child format

---

## 11. Expression format conversion

Template.json uses the `@@@MPB_QUOTE_BODY` string-interpolation format:
```
"${@@@MPB_QUOTE_BODY data.cpu_clock_speed @@@MPB_QUOTE}"
```

Design.json uses structured expression objects:
```json
{
  "id": "<uuid>",
  "expressionText": "@@@MPB_QUOTE <uuid> @@@MPB_QUOTE",
  "expressionParts": [
    {
      "id": "<uuid>",
      "label": "data.cpu_clock_speed",
      "originId": "<request-uuid>-base-data.cpu_clock_speed",
      "originType": "ATTRIBUTE"
    }
  ]
}
```

To convert: extract `expressionParts[0].label` and wrap it:
`"${@@@MPB_QUOTE_BODY " + label + " @@@MPB_QUOTE}"`

For list expressions, the same pattern applies:
- design `listId: "data.pools.*"` -> template `listExpression: "${@@@MPB_QUOTE_BODY data.pools.* @@@MPB_QUOTE}"`

---

## 12. Synology render-vs-template comparison

Running `render` on `synology_nas.yaml` produces a design.json that
exhibits ALL the same structural differences as UniFi. This confirms the
gap is in the renderer's output format, not in any YAML-specific issue.
Key Synology render-vs-template diffs (same as all above):

- `pakSettings.version`: `"1.0.0"` (render) vs `"1.0.0.1"` (template)
- `globalHeaders` present in render, absent in template
- `creds` in render, `credentials` in template
- `sessionSettings` in render, `token` in template
- Resources use `metricSets`/`internalObjectInfo` in render, `requestedMetrics`/`label`/`name`/`identifiers` in template
- All requests have `designId`, `response`, `chainingSettings` in render; absent in template
- Configuration uses `configType`/`defaultValue` in render, `type`/`default` in template
