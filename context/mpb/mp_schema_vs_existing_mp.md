# MPB Schema Comparison: Our YAML vs. Scott's Existing DSM MP

**Inputs**
- **Our authored YAML** — `managementpacks/synology_dsm.yaml` (aspirational, Phase 3
  output; 7 object types, 7 relationships, 9 events, full metric coverage)
- **Existing MP JSON** (authoritative wire format, build 8, working on instance) —
  `references/sentania_aria_operations_dsm_mp/Management Pack JSON/Synology DSM MP.json`
- **Postman collection** (API-exploration artifact) —
  `references/sentania_aria_operations_dsm_mp/API Exploration/Synology.postman_collection.json`
- **Research baseline** — `docs/reference-mpb-research.md`
- **Our loader schema** — `vcfops_managementpacks/loader.py`

**Cross-check reference MPs used**
- Rubrik — `references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json`
  (the only reference MP with events AND relationships populated)
- FastAPI, GitHub, Security Advisories — Dale Hassinger's
  `references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/Management-Packs/`

Existing MP top-level totals: **9 requests, 4 object types, 1 relationship, 0
events, 0 content**. Our YAML plans: **9 top-level requests (de-duplicated count
across object types is ~13), 7 object types, 7 relationships, 9 events, 0
content**.

---

## 1. Summary Table

| Section | In existing MP | In our YAML | Alignment | Notes |
|---|---|---|---|---|
| `design` | yes (`design.design.{name, type, author, version, description}` + `design.buildNumber`) | yes (flat `name, version, build_number, author, description`) | **ALIGNED** (renderer must nest) | Existing uses two-level nesting under `design` key; our YAML is flat. Mechanical to render. `type` is hard-coded `"HTTP"`. |
| `source` | yes (`source.source.{configuration, testRequest, globalHeaders, authentication}` + `source.configuration[]`) | yes (flat `source.{port, ssl, base_path, timeout, max_retries, max_concurrent, auth, test_request}`) | **WIRE-SURPRISE** | Existing has TWO sections named `source` at different depths and a sibling `configuration` array. Our YAML collapses them. Renderer must split into the split-brain layout. See §2. |
| `requests` | yes (9, per-adapter-kind, not per-object-type) | yes (embedded per-object-type) | **WIRE-SURPRISE** | Existing stores requests as a flat top-level array keyed by random `id`; object metricSets reference that `requestId`. Our YAML nests requests inside each object_type with no cross-object sharing. See §3. |
| `objects` | yes (4) | yes (7) | **ALIGNED structurally** | Structure matches conceptually; fields differ (see §4). Our YAML has 7 vs 4 because we went broader than Scott's build 8. |
| `relationships` | yes (1) | yes (7 including dual-parent Disk) | **WIRE-SURPRISE** | Existing schema carries `childExpression`/`parentExpression` — metric-value join predicates, not just ID references. Our YAML has `{parent, child}` only. See §5. |
| `events` | empty (`[]`) | yes (9) | **GAP-EXISTING / GAP-OURS** | No event sample in Synology MP; Rubrik MP has 1 event showing the full shape, which does NOT match our YAML's DSL-expression format at all. See §6. |
| `content` | empty (`[]`) | empty | **ALIGNED** | Both empty. Security Advisories MP shows the populated shape (a top-level list of `{content: {id, name, type:"DASHBOARD", content: {...}, internalId}}` wrappers), should we need to bundle. |

---

## 2. Authentication / Session Handling (DEEP DIVE)

This is the single largest wire-format divergence in the entire schema.

### 2a. What our YAML proposes

```yaml
source:
  auth:
    type: SESSION
    session:
      login:
        method: GET
        path: "/webapi/entry.cgi"
        params:
          api: "SYNO.API.Auth"
          version: "7"
          method: "login"
          session: "VCFOpsMP"
          format: "sid"
      logout:
        method: GET
        path: "/webapi/entry.cgi"
        params: {api: "SYNO.API.Auth", version: "7", method: "logout", session: "VCFOpsMP"}
      session_token_key: "data.sid"
      token_param: "_sid"
```

Assumes: `format=sid`, token extracted from JSON body `data.sid`, injected as
`_sid` query parameter on subsequent requests, logout via same endpoint as
login.

### 2b. What the existing MP actually does

**All findings below from `source.source.authentication` in the MP JSON.**

#### Login request (`sessionSettings.getSession`)

```json
{
  "path": "auth.cgi",          // NOT entry.cgi; NOT prefixed with /webapi
  "method": "GET",
  "params": [
    {"key": "api",     "value": "SYNO.API.Auth"},
    {"key": "version", "value": "3"},                      // NOT "7"
    {"key": "method",  "value": "login"},
    {"key": "account", "value": "${authentication.credentials.username}"},
    {"key": "passwd",  "value": "${authentication.credentials.passwd}"},
    {"key": "session", "value": "FileStation"},            // NOT "VCFOpsMP"
    {"key": "format",  "value": "cookie"}                  // CRITICAL: NOT "sid"
  ],
  "headers": [
    {"key": "Content-Type", "type": "REQUIRED", "value": "application/json"}
  ]
}
```

Key differences vs our YAML:
- **Base path is `webapi` (no leading slash), login path is `auth.cgi`.** The
  MPB configuration field is `"baseApiPath": "webapi"` and request paths are
  relative (`auth.cgi`, `entry.cgi`). Our YAML writes `"/webapi/entry.cgi"` for
  every path, which the renderer will need to normalize. **GAP-OURS**: our
  `base_path` plus `path` together form a doubled prefix.
- **`format=cookie` — NOT `sid`.** The whole auth model is cookie-based, not
  token-based. Body-field extraction (`data.sid`) is not used.
- **API version `3`** on auth (not `7`).
- **Session name `FileStation`** (a built-in Synology session bucket, not
  arbitrary like `VCFOpsMP`). Scott tested this against the live DSM and it
  works; using a custom session name may or may not.
- **Username credential key is `account`**, not `username`. Password is
  `passwd`, not `password`.
- **Login params use a list-of-objects shape** (`[{key, value}, ...]`), not a
  dict. Applies to every `params` field in the document.

`params` shape in MPB wire format is ALWAYS an ordered list of `{key, value}`
objects — never a dictionary. Our YAML uses dicts (`params: {api: ..., method: ...}`).
**GAP-OURS**: dict-to-list conversion needed; order may matter for some APIs.

#### Session token extraction (`sessionSettings.sessionVariables`)

```json
[
  {
    "id": "sMGhQynF4MH1KLv4b4uwSi",
    "key": "Set-Cookie",
    "path": ["Set-Cookie"],
    "usage": "${authentication.session.set_cookie}",
    "example": null,
    "location": "HEADER"          // extracted from RESPONSE HEADERS, not body
  }
]
```

**WIRE-SURPRISE — this field has no equivalent in our YAML.** The existing MP
pulls the session token out of the HTTP response header `Set-Cookie` (not
the JSON body) and binds it to the variable
`${authentication.session.set_cookie}`. Our YAML's `session_token_key:
"data.sid"` field implies body extraction, which the MPB engine either can't
do or Scott didn't use.

`location` is an enum — at minimum `HEADER` is supported; the OpenAPI research
doc didn't enumerate others.

#### Token injection on subsequent requests (`source.source.globalHeaders`)

```json
[
  {"key": "Content-Type", "type": "REQUIRED", "value": "application/json"},
  {"key": "id",          "type": "CUSTOM",   "value": "${authentication.session.set_cookie}"}
]
```

**WIRE-SURPRISE.** The session cookie is injected as an HTTP **HEADER**
literally named `"id"` (not `Cookie`, not `_sid` query param). This is how
DSM's `webapi/entry.cgi` actually accepts the session when `format=cookie`
is used. Our YAML's `token_param: "_sid"` (query-string injection) is the
*wrong mechanism* for Scott's working MP.

Header `type` values observed: `REQUIRED`, `IMMUTABLE`, `CUSTOM`. The research
doc mentioned only `REQUIRED`/`IMMUTABLE`; `CUSTOM` is new.

#### Logout (`sessionSettings.releaseSession`)

```json
{
  "path": "auth.cgi",
  "method": "DELETE",            // not GET as our YAML assumed
  "params": [
    {"key": "method",  "value": "logout"},
    {"key": "version", "value": "3"},
    {"key": "api",     "value": "SYNO.API.Auth"}
  ]
}
```

**GAP-OURS**: logout uses HTTP DELETE, not GET. (DSM tolerates both at
runtime, but MPB's rendered request is DELETE.) Also no `session` param —
the cookie header alone identifies which session to release.

#### Credential schema (`authentication.creds` + `credentialType`)

```json
{
  "credentialType": "CUSTOM",     // NOT "SESSION", NOT "BASIC"
  "creds": [
    {
      "id": "8sQ2iJdSnBHjubpD8HQqgy",
      "label": "username",        // lowercase, no spaces
      "usage": "${authentication.credentials.username}",
      "value": null,
      "editable": true,           // note: true in Scott's MP
      "sensitive": false,
      "description": "Synology Username"
    },
    {
      "id": "j6r18fwfK3DBrxbr2ispCB",
      "label": "passwd",          // same variable name as the API uses
      "usage": "${authentication.credentials.passwd}",
      "value": null,
      "editable": true,
      "sensitive": true,
      "description": "Synology Password"
    }
  ]
}
```

**WIRE-SURPRISE.** The Synology MP uses `credentialType: "CUSTOM"` with two
arbitrarily-named fields, NOT `credentialType: "SESSION"`. Our loader has
`VALID_AUTH_TYPE = {"BASIC", "TOKEN", "SESSION", "NONE"}` — there is no
`CUSTOM`. The MPB's `CUSTOM` credentialType is what enables freeform auth
flows using sessionSettings; `SESSION` as a top-level credential type
appears to be a fiction of our schema. **GAP-OURS**: credential type vocab
mismatch; renderer will need to emit `CUSTOM` when `auth.type == SESSION`
in our YAML.

The cred field `label` ("passwd") directly determines the `${authentication.credentials.passwd}`
variable name used elsewhere in the document — so the `label` is semantically
load-bearing (not just display text) and must match the params that reference
it. This is not modeled in our YAML.

### 2c. Implications

Authentication is the section where our YAML diverges most from reality. Before
the renderer emits a working JSON, **Scott's existing MP should be treated as
the ground truth for the wire format**, and our YAML will need either a
richer auth model (cookie-header binding, header-based token injection, list-of-
key-value params, CUSTOM credentialType) or mp-designer needs to tighten the
YAML to map cleanly onto this model. The current gap is bigger than a
renderer can paper over with assumptions.

---

## 3. Requests

### 3a. Structural differences

- **Existing MP**: requests live at the **top level** as
  `requests: [{request: {...}}, ...]`, keyed by random 22-char IDs. Each
  object type's metricSets reference those IDs via `requestId`. Requests are
  shared across multiple object types when they return data for several
  levels (e.g., `Utilization` feeds both Diskstation and Volume metrics in
  Scott's MP; the `Storage Pool` pool data and disk data come from different
  requests).
- **Our YAML**: requests are nested **inside each object_type**
  (`object_types[*].requests[]`). Multiple object types that use the same API
  call will duplicate the request definition.

**GAP-OURS**: the renderer must deduplicate requests across object_types,
generate a stable ID per unique request, and rewrite per-object metric
sources to reference the deduplicated request.

### 3b. Request shape (per `requests[].request`)

```json
{
  "id": "oUVG9A48uCY1BXrWcyHBcC",        // random 22-char alphanumeric
  "body": null,
  "name": "Utilization",                  // human-readable
  "path": "entry.cgi",                    // relative to baseApiPath
  "method": "GET",
  "paging": null,                         // always null in all ref MPs
  "params": [                             // list of {key, value}
    {"key": "api",     "value": "SYNO.Core.System.Utilization"},
    {"key": "version", "value": "1"},
    {"key": "method",  "value": "get"}
  ],
  "headers": [],                          // per-request headers (usually empty)
  "designId": null,
  "response": {
    "id": "...",
    "log": "Imported request, execute to get accurate log",
    "result": {
      "body": "Imported request, execute to get accurate body",
      "headers": [],
      "responseCode": 200,
      "dataModelLists": [...]            // see §3c
    },
    "status": "COMPLETED",
    "endTime": 0, "duration": "NA", "startTime": 0,
    "toolkitId": "...",
    "errorMessage": ""
  },
  "chainingSettings": null               // always null in all ref MPs
}
```

**GAPs-OURS**:
- `chainingSettings` is not modeled in our YAML, and defaults to null in every
  reference MP — fine for renderer to always emit null, but we have zero
  evidence for what populated chaining looks like. **TOOLSET GAP**.
- `paging` is always null. Our YAML has no pagination concept; no evidence
  forces us to add one. Note Scott uses `limit=-1&offset=0` as a Synology
  idiom to ask for all rows in one call, avoiding paging entirely.
- The whole `response.{id, log, result.body, result.headers, status, endTime,
  duration, startTime, toolkitId, errorMessage}` envelope is **MPB-UI
  scratchpad** — it records the last-seen test-execution metadata. The renderer
  can emit defaults: `status: "COMPLETED"`, `endTime: 0`, `duration: "NA"`,
  etc. The semantically important child is `result.responseCode` (always 200
  in ref MPs) and `result.dataModelLists`.

### 3c. Response mapping (`result.dataModelLists`)

Each `dataModelList` is one JSON path through the response. They chain via
`parentListId`:

```json
{
  "id": "data.volumes.*",      // label of this list (wildcard = iterate array)
  "key": ["data", "volumes"],  // JSON path segments to reach the array
  "label": "data.volumes.*",
  "attributes": [              // each attribute is a field extractable from a list item
    {
      "id": "s3T27RK1ACggGgCVje7pZk-data.volumes.*-pool_path",
      "key": ["pool_path"],    // nested path relative to the list item
      "label": "pool_path",
      "example": ""
    },
    {
      "id": "s3T27RK1ACggGgCVje7pZk-data.volumes.*-@@@id",
      "key": ["@@@id"],        // SPECIAL: synthetic per-item identifier (index or MPB-generated)
      "label": "@@@id",
      "example": ""
    }
  ],
  "parentListId": "base"       // "base" = top-level response object (not an array iteration)
}
```

Attribute `id` follows a strict naming convention:
`<request-id>-<list-id>-<dotted-key-path>`. For example
`iveRmy7WTSbNCWm2LpJFZb-base-data.cpu_clock_speed`. **Metrics reference
attributes via this composite ID** (see §4).

**WIRE-SURPRISE: MPB generates wildcard-path duplicates.** For the `Get Storage
Pools` request, the existing MP emits BOTH `data.*.*` (wildcard path) and
`data.pools.*` (explicit path) as separate dataModelLists with identical
attributes. Scott's Storage Pool object picks `data.*.*`. The existing MP's
`Get Disks` request similarly carries `data.*.*` AND `data.disks.*` with all
84 attributes mirrored. This doubles the dml count for free; the renderer
probably doesn't need to replicate this — but it means that MPB-UI-authored
JSONs are MUCH bigger than a minimal renderer would produce, and the
duplicates may affect what Scott's live MP is actually collecting.
**GAP-OURS: unclear whether picking the explicit path (`data.pools.*`) vs
wildcard path (`data.*.*`) changes collection behavior.** Worth flagging for
tooling agent / mp-designer.

The `@@@id` and `@@@rawValue` special attributes are documented in the research
doc. They appear as literal attribute keys in dataModelLists in addition to
the actual response fields. Not every dml carries them — `@@@id` is always
present on wildcard list iterations (`data.items.*`, `data.pools.*`); `@@@rawValue`
appears when the array is primitive (e.g., `data.support_virtual_protocol.*`
which is an array of strings).

### 3d. Request catalog — existing MP

| Name | Method | Path | Key params (api, method, version) | dml count | Used by objects |
|---|---|---|---|---|---|
| Utilization | GET | entry.cgi | SYNO.Core.System.Utilization / get / 1 | 11 | Diskstation |
| FileStation | GET | entry.cgi | SYNO.FileStation.Info / get / 1 | 2 | Diskstation |
| LUNs | GET | entry.cgi | SYNO.Core.ISCSI.LUN / list / 1 | 6 | (unused — present but no object references it) |
| System | GET | entry.cgi | SYNO.Core.System / info / 3 | 1 (base only) | Diskstation |
| Storage Info | GET | entry.cgi | SYNO.Core.System / info / 1 (type=storage) | 5 | (unused) |
| Network Info | GET | entry.cgi | SYNO.Core.System / info / 1 (type=network) | 3 | (unused) |
| Get Volumes | GET | entry.cgi | SYNO.Core.Storage.Volume / list / 1 | 2 | Volume |
| Get Disks | GET | entry.cgi | SYNO.Core.Storage.Disk / list / 1 | 4 | Disks |
| Get Storage Pools | GET | entry.cgi | SYNO.Core.Storage.Pool / list / 1 | 24 | Storage Pool |

Notes:
- Several requests are authored but unused. MPB-UI keeps request definitions
  even if no object binds to them. The renderer must decide whether to emit
  unreferenced requests (existing MP does; our YAML's nested model naturally
  won't unless we choose to).
- Our YAML's `Diskstation` uses `SYNO.DSM.Info / getinfo / 2`, but the existing
  MP doesn't call this endpoint at all. It sources `Serial`, `Model`,
  `Firmware Ver`, `RAM Size`, `Sys Temp` from `SYNO.Core.System / info / 3`
  (the `System` request) and `Hostname` from the `FileStation` request.
  **Finding**: Scott's built MP and our YAML overlap on intent but diverge on
  which endpoint backs each metric. Neither is necessarily wrong; both
  provide the same data — DSM exposes a lot of redundancy. The renderer
  should respect our YAML's choice but the tooling agent should know that
  the existing MP is proof that the alternative source works too.
- Our YAML has request names like `core_system`, `utilization` (snake_case),
  while the existing MP uses Title Case (`System`, `Utilization`,
  `Get Storage Pools`). Cosmetic.

### 3e. Postman collection cross-check

The Postman collection shows 15 requests, a superset of the 9 in the MP JSON.
It includes several not in the MP JSON (`Get Shared Folders`,
`Get Storage Volume` [single], `Query API`, `Working Query`, `Get DSM Info`,
`Get FileStation Info`) — these are the pre-authoring exploration artifacts
Scott used to characterize the API before deciding which to bake into the MP.

The Postman collection's auth flow confirms the MP JSON:
- Login calls `/webapi/auth.cgi?...&format=cookie` and captures `Set-Cookie`
  from response headers via a Postman test script:
  ```js
  pm.collectionVariables.set("session-cookie", pm.response.headers.get("Set-Cookie"));
  ```
- Subsequent calls send `id: {{session-cookie}}` as a header.

Both the Postman collection and the MP JSON use `format=cookie` +
`Set-Cookie` header extraction + `id` header injection. Our YAML's
`format=sid` + `data.sid` body extraction + `_sid` query-param injection
pattern is **a different (also valid) DSM auth mode** that Scott experimented
with earlier but did NOT choose for the shipped MP. The Postman and MP JSON
are fully consistent with each other.

The Postman collection includes `Get iSCSI LUN` (SYNO.Core.ISCSI.LUN) — this
appears in the MP JSON as the `LUNs` request but no object type binds to it,
so iSCSI LUN is a roadmap item Scott stubbed but hadn't finished at build 8.
Our YAML's iSCSI LUN object type is new work beyond Scott's build 8.

The Postman collection has no Docker or UPS requests — those endpoints
(`SYNO.Docker.Container`, `SYNO.Core.ExternalDevice.UPS`) are new in our
YAML and have no existing-MP precedent.

---

## 4. Objects / Metrics

### 4a. Per-object summary (existing MP)

| Object | id (MPB) | type | isListObject | icon | identifierIds count | metricSets count | PROPERTY / METRIC counts |
|---|---|---|---|---|---|---|---|
| Synology Diskstation | `hspa5JaB3DYA29rUueJDri` | INTERNAL | **false** | media-changer.svg | 1 (Serial) | 3 (System base, FileStation base, Utilization base) | 14 PROP / 17 METRIC (on 31 total across 3 sets) |
| Volume | `rXgTBrRXXWjY3WPAbxQxiT` | INTERNAL | true | hard-drive-disks.svg | 2 (Volume Path + Pool Path) | 1 (Get Volumes data.volumes.*) | 10 metrics total; PROPERTY-dominant |
| Disks | `nsNGPbLJh4iv6jzBKbe9QA` | INTERNAL | true | storage.svg | 1 (Serial) | 1 (Get Disks data.disks.*) | 11 metrics total |
| Storage Pool | `sUGYc98T832GjwGaXjzgy4` | INTERNAL | true | data-cluster.svg | 2 (ID + Pool Path) | 1 (Get Storage Pools data.*.*) | 6 metrics total |

### 4b. Full object shape

```json
{
  "object": {
    "id": "hspa5JaB3DYA29rUueJDri",          // random 22-char
    "type": "INTERNAL",
    "designId": null,
    "metricSets": [ ... ],
    "ariaOpsConf": null,                      // always null for INTERNAL
    "isListObject": false,                    // <-- critical: world object = false
    "internalObjectInfo": {
      "id": "oV4YqV6t7eVJfp6BdEmvwd",        // SECOND id, separate from object.id
      "icon": "media-changer.svg",
      "identifierIds": ["cnjBegvs4ncDzxCxfjqGy3"],
      "objectTypeLabel": "Synology Diskstation",
      "nameMetricExpression": { ... }
    }
  }
}
```

**GAP-OURS**: Our YAML has `is_world: true` for the Diskstation. The existing
MP encodes this as `isListObject: false` — it's the inverse boolean. The
Diskstation is the NON-list (1-per-adapter-instance) object; every other
object type is a list. The renderer must translate `is_world: true` →
`isListObject: false` + `listId: "base"` throughout the metricSets.

**WIRE-SURPRISE**: there are TWO `id` fields per object (`object.id` AND
`object.internalObjectInfo.id`). Both are random 22-char strings. They are
NOT equal and appear to be independently generated by MPB-UI.

### 4c. `nameMetricExpression` — single-part expression, not a template

**This is a major finding for the renderer.**

Our YAML uses shell-style template strings:
```yaml
name_expression: "${model} (${hostname})"
name_expression: "Pool ${num_id} (${device_type})"
name_expression: "${display_name}"
```

The existing MP's `nameMetricExpression` is NOT a template. Every example
observed is a single-part expression pointing at ONE metric by `originId`,
with `originType: METRIC`:

```json
{
  "id": "7aRivS9a2r1DkthAE1UTGX",
  "expressionText": "@@@MPB_QUOTE k7uavtAL15R3edkcrjsLo5 @@@MPB_QUOTE",
  "expressionParts": [
    {
      "id": "k7uavtAL15R3edkcrjsLo5",
      "label": "Hostname",
      "regex": null,
      "example": "",
      "originId": "wE3wzuBpRreBnQJKPkQMeX",       // = metric "Hostname".id
      "originType": "METRIC",                      // NOT ATTRIBUTE
      "regexOutput": ""
    }
  ]
}
```

In Scott's MP:
- Diskstation name = the Hostname metric's string value (plain passthrough)
- Volume name = the Display Name metric's string value
- Disks name = the Name metric's string value
- Storage Pool name = the ID metric's string value

**GAP-OURS**: `"${model} (${hostname})"` cannot be rendered as a single-part
expression. Two possibilities:

1. MPB's `expressionText` actually supports multi-part concatenation with
   literal text segments (the `@@@MPB_QUOTE <part-id> @@@MPB_QUOTE` pattern
   would naturally interleave: `"@@@MPB_QUOTE <model-id> @@@MPB_QUOTE (@@@MPB_QUOTE <hostname-id> @@@MPB_QUOTE)"`).
   **No reference MP demonstrates this** — all reference MPs use single-part
   name expressions. The capability may exist but is unverified.
2. Scott's MP explicitly settled on single metric values for name display.
   If renderer emits multi-part templates and they don't actually work, the
   MP will fail to import or will ship with broken name display.

**RECOMMENDED FOR RENDERER** (escalation material, not my call to resolve):
when our YAML's `name_expression` is a single `${var}`, emit a single-part
expression pointing at that metric. When it contains literals + multiple
vars, escalate to `api-explorer` for wire-format verification OR fall back
to the first `${var}` and warn.

### 4d. Metric shape

```json
{
  "id": "8SkCmRATxWDm9ZhEdBDvnL",          // random 22-char
  "unit": "",                                // empty in ~98% of cases; one example = "gigabyte"
  "isKpi": false,                            // FALSE in 100% of cases observed
  "label": "CPU Clock Speed",
  "usage": "PROPERTY",                       // PROPERTY or METRIC
  "groups": [],                              // EMPTY in 100% of cases observed
  "dataType": "NUMBER",                      // STRING or NUMBER
  "expression": {
    "id": "...",
    "expressionText": "@@@MPB_QUOTE aJZuG9PFc613JdhXmq1pT2 @@@MPB_QUOTE",
    "expressionParts": [
      {
        "id": "aJZuG9PFc613JdhXmq1pT2",
        "label": "data.cpu_clock_speed",
        "regex": null,
        "example": "",
        "originId": "iveRmy7WTSbNCWm2LpJFZb-base-data.cpu_clock_speed",
        "originType": "ATTRIBUTE",
        "regexOutput": ""
      }
    ]
  },
  "timeseries": null                         // NULL in 100% of cases observed
}
```

Scan across all 5 reference MPs (176 metrics total):

| Field | Observed populated? | Count |
|---|---|---|
| `isKpi: true` | never | 0 / 176 |
| `groups: [non-empty]` | never | 0 / 176 |
| `timeseries: non-null` | never | 0 / 176 |
| `expressionParts[].regex: non-null` | never (in metrics) | 0 / 176; Rubrik uses it in ONE event |
| `expressionParts[].originType: METRIC` | never (in metrics, outside nameMetricExpression) | — |
| `expressionParts[].originType: ARIA_OPS_METRIC` | never (in metrics, outside relationships) | — |
| `unit: non-empty` | rarely | 4 / 176 (one is `gigabyte`) |

**GAP-OURS**: our YAML has `kpi: true` on 5 metrics and `unit: "%"`, `"bytes"`,
`"IOPS"`, etc. on dozens. The renderer should emit these, but we have **zero
existing-MP evidence that `isKpi: true` or non-default `unit` values do
anything at collection or presentation time**. The `unit: "gigabyte"` string
in Scott's MP is a long-form word, not a short code — **our `unit: "bytes"`,
`"%"`, `"ms"` may not match MPB's expected vocabulary**. TOOLSET GAP: we
don't have the MPB UI-generated unit vocabulary; tooling agent may need to
emit units empty or route to api-explorer for the unit enum.

**WIRE-SURPRISE: `expressionText` encoding.** The expression text is not human
text — it is LITERALLY the string `@@@MPB_QUOTE <part-id> @@@MPB_QUOTE` with
an ID-pointer in the middle. Multi-part expressions (seen in Rubrik's event
recommendations, not in any metric) concatenate multiple `@@@MPB_QUOTE ... @@@MPB_QUOTE`
segments. The `@@@MPB_QUOTE` markers are the MPB syntactic delimiter,
flagging that the enclosed text is an ID reference rather than a literal.
Arbitrary literal text appears OUTSIDE the `@@@MPB_QUOTE ... @@@MPB_QUOTE`
wrappers — i.e., an expression like `"Hello @@@MPB_QUOTE X @@@MPB_QUOTE"`
would render as `Hello <X's value>`.

### 4e. `originId` composition

The attribute origin ID is a composite string:
`<request-id>-<list-id>-<dotted-key-path>`.

Examples from Scott's MP:
- `iveRmy7WTSbNCWm2LpJFZb-base-data.cpu_clock_speed` (System request, base list, `data.cpu_clock_speed` field)
- `s3T27RK1ACggGgCVje7pZk-data.volumes.*-pool_path` (Get Volumes request, data.volumes.* list, `pool_path` field)
- `4Qh3BBFG2e8c16MPTmaJuv-data.disks.*-serial` (Get Disks request, data.disks.* list, `serial` field)
- `bzEaQyyiXJXgEKaEQhJaRH-data.*.*-id` (Get Storage Pools request, wildcard list, `id` field)

The renderer must construct these consistently. Our YAML's `source:
"request:storage_load_info.id"` must be translated into the composite form
once the request-ID and list-ID are assigned.

### 4f. Metric usage / datatype quirks

Scott's MP classifications that diverge from our YAML:
- `Up Time` → `PROPERTY / STRING` in existing (our YAML: `uptime` is `METRIC /
  NUMBER` with unit `seconds`). DSM returns uptime as a formatted string
  (`"123 days, 4:56:78"`), not a number. **GAP-OURS**: our YAML assumes
  numeric uptime that DSM doesn't return in that form.
- `CPU Clock Speed`, `CPU Cores`, `RAM Size` → `PROPERTY / NUMBER` in existing.
  Our YAML matches on Cores/RAM (PROPERTY/NUMBER), differs on Cores (we say
  PROPERTY/STRING) — a small mismatch.
- Scott's Disk identifier is `serial` only; our YAML's is `disk_id`. Both are
  valid unique keys; mp-designer's call on whether this matters.

### 4g. Identifier semantics

`identifierIds` is an array of metric IDs. Each referenced metric must
(a) have `usage: PROPERTY` and (b) have `dataType: STRING`. When there are
multiple, object identity is the tuple of those metric values (composite key).

Observed multi-identifier objects:
- Volume: `[Volume Path, Pool Path]` — both PROPERTY/STRING
- Storage Pool: `[ID, Pool Path]` — both PROPERTY/STRING

Our YAML's `identifiers: [pool_id, pool_path]` matches structurally.

---

## 5. Relationships (DEEP DIVE)

### 5a. What our YAML proposes

Seven flat `{parent, child}` tuples, including dual-parent (Disk appears as a
child of BOTH `storage_pool` AND `synology_diskstation`):

```yaml
relationships:
  - {parent: synology_diskstation, child: storage_pool}
  - {parent: storage_pool,          child: volume}
  - {parent: volume,                child: iscsi_lun}
  - {parent: storage_pool,          child: disk}
  - {parent: synology_diskstation,  child: disk}      # dual-parent for Disk
  - {parent: synology_diskstation,  child: docker_container}
  - {parent: synology_diskstation,  child: ups}
```

### 5b. What the existing MP has

ONE relationship. Full wire format:

```json
{
  "relationship": {
    "id": "3V9HBw4cBdCqSZdJn5dpb1",                 // random 22-char
    "name": "Storage Pool -> Volume",               // human-readable
    "designId": null,
    "caseSensitive": true,                          // configurable
    "childObjectId": "rXgTBrRXXWjY3WPAbxQxiT",      // = Volume.object.id
    "parentObjectId": "sUGYc98T832GjwGaXjzgy4",     // = Storage Pool.object.id
    "childExpression": {                            // <-- VALUE PREDICATE
      "id": "6WnU4V6L1HZqMUZE5JGrXK",
      "expressionText": "@@@MPB_QUOTE nNAEjQTQrKmoGdW9NUmCdh @@@MPB_QUOTE",
      "expressionParts": [
        {
          "id": "nNAEjQTQrKmoGdW9NUmCdh",
          "label": "Pool Path",
          "regex": null,
          "originId": "cA1ZReJWms1ECBnKVBq8od",     // Volume's Pool Path metric ID
          "originType": "METRIC",
          "regexOutput": ""
        }
      ]
    },
    "parentExpression": {                           // <-- MATCHES childExpression
      "id": "uURz2BkxmM4LjfvzWFPoZ2",
      "expressionText": "@@@MPB_QUOTE 6KQcyj3u7qU3CVreAqg9mU @@@MPB_QUOTE",
      "expressionParts": [
        {
          "id": "6KQcyj3u7qU3CVreAqg9mU",
          "label": "ID",
          "regex": null,
          "originId": "py8ghbVD7Bz7m3rjYyoHoT",     // Storage Pool's ID metric
          "originType": "METRIC",
          "regexOutput": ""
        }
      ]
    }
  }
}
```

### 5c. WIRE-SURPRISE: relationships are VALUE JOINS, not parent/child edges

**This is the second-biggest schema divergence after auth.**

The MPB relationship isn't a simple "A is parent of B" edge. It's a
**value-based join predicate**: "a Volume `V` is child of Storage Pool `P` **if
and only if** V's Pool Path metric value == P's ID metric value". The MPB
engine evaluates this at collection time to link discovered objects.

Implications for our YAML:
1. **GAP-OURS: our YAML's `{parent, child}` tuple is missing the join keys.**
   Our loader has no way to specify which child metric matches which parent
   metric. The renderer cannot emit a working relationship without that
   information.
2. Every relationship we ship must have the join metrics pre-identified. For
   the existing `Storage Pool → Volume` edge, Scott used Volume's `pool_path`
   property as the FK and Storage Pool's `id` property as the PK. For our
   proposed `Storage Pool → Disk` edge, we'd need to identify what disk field
   references a pool — likely `used_by` (pool name) or some pool-id field in
   the disk response.
3. **Dual-parent for Disk is achievable** in this model IF we can specify two
   distinct relationship rows, each with its own join predicates:
   - `synology_diskstation → disk`: predicate likely matches all disks
     (e.g., always true, OR some world-level property match). Needs
     investigation.
   - `storage_pool → disk`: predicate matches disk's `used_by` against pool's
     `id` or name. Needs investigation.
   The schema SUPPORTS two relationship rows with the same child. The
   Rubrik MP has `Rubrik Cluster → Rubrik Job` AND `Virtual Machine → Rubrik
   Job` (two separate rows, same child `Rubrik Job`). **Proof that dual-parent
   works.**
4. **GAP-OURS**: `relationships[].caseSensitive` is a config knob (true/false)
   for how the value comparison is done. Our YAML has no way to express it.
   Both true and false are observed across reference MPs.

### 5d. Aria-Ops-anchored relationships (from Rubrik)

Rubrik's `Virtual Machine → Rubrik Job` relationship joins Rubrik's discovered
Job objects to pre-existing vCenter VM objects. The parentExpression's
originType is `ARIA_OPS_METRIC` with a hard-coded ID:

```json
{
  "originId": "aria-VMWARE-VirtualMachine-VMEntityName",
  "originType": "ARIA_OPS_METRIC"
}
```

Not relevant to our Synology MP (all INTERNAL objects) but good to document for
future MP work.

---

## 6. Events (DEEP DIVE)

### 6a. What our YAML proposes

Nine per-object-type events with a custom DSL-like condition string and a
template message:

```yaml
events:
  - name: "High Temperature"
    severity: CRITICAL
    condition: "sys_temp > 70"
    message: "System temperature is critically high (${sys_temp}C). Check airflow..."
```

### 6b. What the existing MP has

`events: []` — ZERO events. GAP-EXISTING: no Synology-specific event sample.

### 6c. Cross-reference: Rubrik event shape (only ref example)

Rubrik's event definition (full wire format at §1 cross-check above):

```json
{
  "event": {
    "id": "e4E3onB9U4orGCSeSsDaSo",
    "label": "Rubrik Events",
    "listId": "data.events.*",                 // dml binding
    "requestId": "cNgKy86jrteekPyVsw4tfq",     // source request
    "matchMode": "ALL",                         // enum
    "defaultSeverity": "LOG",                   // fallback severity
    "unmatchedEventBehavior": "ATTACH_TO_ADAPTER",   // enum

    "alert": {
      "type": "APPLICATION",                    // alert type enum
      "badge": "HEALTH",                        // badge enum
      "subType": "AVAILABILITY",                // alert subtype enum
      "waitCycle": 1,
      "cancelCycle": 1,
      "recommendation": null
    },

    "message": {                                // expression — regex-extracted from eventInfo field
      "id": "...",
      "expressionText": "@@@MPB_QUOTE 6fNQyBBfnAodZ3E7SrD2qu @@@MPB_QUOTE",
      "expressionParts": [
        {
          "id": "6fNQyBBfnAodZ3E7SrD2qu",
          "label": "eventInfo",
          "regex": "\"message\":\"(.*?)\"",     // REGEX extraction!
          "originId": "cNgKy86jrteekPyVsw4tfq-data.events.*-eventInfo",
          "originType": "ATTRIBUTE",
          "regexOutput": ""
        }
      ]
    },

    "severity": {                               // expression — severity value from eventSeverity field
      "id": "...",
      "expressionText": "@@@MPB_QUOTE 67qcUGN7BFDtLCSu23i3e5 @@@MPB_QUOTE",
      "expressionParts": [
        {
          "label": "eventSeverity",
          "originId": "cNgKy86jrteekPyVsw4tfq-data.events.*-eventSeverity",
          "originType": "ATTRIBUTE"
        }
      ]
    },

    "severityMap": [                            // raw-value → Aria-severity mapping
      {"rawSeverity": "Critical",      "ariaOpsSeverity": "CRITICAL"},
      {"rawSeverity": "Warning",       "ariaOpsSeverity": "WARNING"},
      {"rawSeverity": "Informational", "ariaOpsSeverity": "INFO"}
    ],

    "eventMatchers": [                          // object-binding predicates
      {
        "objectId": "54tJ6sXdEBsR23mdQmjemb",
        "objectName": "vCenter Virtual Machine",
        "caseSensitive": false,
        "eventExpression": {                    // event-side field
          "expressionParts": [{"originId": "...-objectName", "originType": "ATTRIBUTE"}]
        },
        "objectExpression": {                   // object-side field (can be ARIA_OPS_METRIC)
          "expressionParts": [{"originId": "aria-VMWARE-VirtualMachine-VMEntityName", "originType": "ARIA_OPS_METRIC"}]
        }
      }
    ]
  }
}
```

### 6d. GAP-OURS: events model is completely different

Our YAML's event model is an **alert-threshold DSL** pattern: "when metric X
crosses threshold Y, emit severity Z with message W". This is how alert
definitions work in standalone VCF Ops content, NOT how MPB events work.

MPB events are a different concept: **pulling event records from an API list
endpoint and materializing them as VCF Ops events, binding each event record
to a discovered object via value-join matchers.** The source must be an API
list (like Rubrik's `/api/events` → `data.events[]`) where each element is
an event record with its own message, severity, and object-identity fields.

Scott's DSM doesn't have such an endpoint readily — there's `SYNO.Core.Notification.Log`
or `SYNO.Core.SyslogClient`, but neither is in our YAML's request catalog.
**The 9 events in our YAML cannot be emitted as MPB events against the MP's
current request set.** They would have to be authored as standalone VCF Ops
symptoms/alerts referencing the MP's metrics AFTER the MP is installed, using
our existing `symptom-author` / `alert-author` pipeline.

### 6e. Implications

- **GAP-OURS**: `managementpacks/synology_dsm.yaml` events are semantically
  mismatched with MPB. The renderer cannot produce valid MPB event definitions
  from them.
- If we keep the events in the YAML: either (a) render them to `events: []`
  and document that MP events aren't populated, or (b) pivot the events to
  the standalone symptom/alert pipeline after MP install.
- If we want true MPB events, mp-designer needs to redesign the events block
  around a list-endpoint + matchers model (probably DSM notification log),
  with severity mapping.

This is non-trivial; flagging for orchestrator/Scott decision.

---

## 7. Content (Bundled Dashboards/Views)

Existing MP: `content: []`. **ALIGNED** with our YAML (which also ships empty).

For future reference, the populated shape (from Broadcom Security Advisories):

```json
{
  "content": {
    "id": "<uuid>",
    "name": "DBH | Security Advisories | VCF",
    "type": "DASHBOARD",
    "content": {
      "entries": {"resource": [ ... ]},
      "dashboards": [ ... ]
    },
    "designId": null,
    "internalId": "2c90e3a0-..."
  }
}
```

The embedded `content.content` matches the VCF Ops dashboard-export JSON
shape that our `vcfops_dashboards` package already emits. When we decide to
bundle content with the MP, the renderer can re-use existing dashboard/view
exports wrapped in this envelope.

---

## 8. `@@@` Special Literals

Confirmed patterns used by MPB:

| Marker | Location | Meaning |
|---|---|---|
| `@@@MPB_QUOTE` | `expressionText` field only | Expression delimiter — surrounds a part-ID reference. Content between two `@@@MPB_QUOTE` tokens is the ID of an expressionPart. Anything outside pairs is literal text. |
| `@@@id` | dataModelList attribute `key` and `label` | Synthetic per-list-item identifier (array index). Auto-generated on any wildcard-iteration dml. |
| `@@@rawValue` | dataModelList attribute `key` and `label` | Synthetic "the value itself" — used when iterating an array of primitives (e.g., strings, numbers). Example: `data.support_virtual_protocol.*` carries `@@@id` AND `@@@rawValue` because each item is a string. |

**The renderer MUST emit `expressionText` in the exact form
`@@@MPB_QUOTE <part-id> @@@MPB_QUOTE`** (note the single spaces) for every
single-part expression. Multi-part expressions (literal-plus-reference mixing)
are plausible but unverified — see §4c.

**The renderer MUST populate `@@@id` attributes on every wildcard-iteration
dataModelList** (existing MP does this unconditionally).

---

## 9. Identifier Randomness

### 9a. ID format

Every `id` field in the existing MP follows one of these shapes:

| Shape | Example | Usage |
|---|---|---|
| Random 22-char alphanumeric | `oUVG9A48uCY1BXrWcyHBcC` | MPB-generated IDs for requests, objects, metrics, expressions, expressionParts, relationships, events, credentials, session vars, name expressions |
| `mpb_<word>` | `mpb_hostname`, `mpb_port`, `mpb_ssl_config` | Adapter-instance-config fields (fixed MPB UI convention) |
| Composite `<req-id>-<list-id>-<key-path>` | `iveRmy7WTSbNCWm2LpJFZb-base-data.cpu_clock_speed` | dataModelList attribute IDs |
| Path-literal | `data.volumes.*`, `base` | dataModelList `id` field (the list's "name" is its JSON path pattern) |

The 22-char format appears to be MPB-UI's base62 random generator. 1031 `id`
fields in the Synology MP, 669 of which contain non-alnum chars (mostly the
composite `-` and `.` chars in attribute IDs).

### 9b. GAP-OURS: renderer ID-generation strategy

Our existing content (dashboards, views, super metrics) uses deterministic
**UUID5** derived from the content name. That gives cross-instance
portability.

For MPB management packs, the `id` fields appear to be **MPB-UI random**.
However, nothing in the wire format strictly requires randomness — all IDs
are internal document-relative references; the MPB engine doesn't care about
their stability across MP exports.

Options for the renderer (**NOT a decision to make here, flagging for tooling
agent**):

1. **UUID5-derived 22-char**: hash the YAML's natural key (object_type.name +
   metric.key, etc.) with UUID5, then base62-encode the first 128 bits to 22
   chars. Deterministic across rebuilds, compatible with our other content
   tooling, diff-friendly.
2. **Random each build**: matches MPB-UI but makes git diffs noisy.
3. **Derive composite IDs from names**: e.g. `synology_diskstation` becomes
   the object ID literally. Risks collisions with MPB-UI-reserved prefixes.

Option 1 is closest to how our other builders work. Tooling agent's call.

Composite `originId`s MUST be constructed from whatever IDs the renderer
chose for requests and dmls — they are internally consistent strings.

---

## 10. Postman Cross-Check

Summary already in §3e. Key points:

- Postman collection is an **earlier-stage artifact** (15 requests; the MP
  JSON has 9, a subset).
- For the 9 requests that survived into the MP JSON, paths, methods, params,
  and headers match Postman byte-for-byte.
- Session auth in Postman (Set-Cookie extraction + `id` header injection)
  matches the MP JSON's `sessionVariables` + `globalHeaders` wiring.
- Postman uses collection variables (`{{fqdn}}`, `{{username}}`, `{{passwd}}`,
  `{{session-cookie}}`) which map cleanly to MPB's
  `${configuration.mpb_hostname}`, `${authentication.credentials.username}`,
  `${authentication.credentials.passwd}`, and `${authentication.session.set_cookie}`
  respectively.
- Postman includes `Get Shared Folders` (SYNO.FileStation.List /
  list_share), which is **absent from the MP JSON** — Scott built the
  Postman exploration broader than the MP's current scope. Not authoritative
  for MPB wiring.

**No divergence between Postman and MP JSON**, consistent with Scott having
authored both.

---

## Headline GAPs (quick reference for tooling / mp-designer)

1. **GAP-OURS — auth model mismatch.** Our `type: SESSION` + `session.login/logout/session_token_key/token_param` YAML does not map to MPB's `credentialType: CUSTOM` + `sessionSettings.getSession/releaseSession/sessionVariables[{key, path, location, usage}]` + cookie-header injection via `globalHeaders`. Largest delta. mp-designer should review before renderer build.
2. **GAP-OURS — params shape.** YAML uses dict, MPB uses ordered list of `{key, value}`. Renderer must translate.
3. **GAP-OURS — base_path prefix.** MPB wants `baseApiPath: "webapi"` (no leading slash), request paths relative (`entry.cgi`). Our YAML has leading slashes and full paths in every request.
4. **GAP-OURS — name_expression template strings.** `"${model} (${hostname})"` has no reference-MP precedent. Either MPB supports this via multi-part interleaved `@@@MPB_QUOTE` (unverified) or it doesn't and the renderer must fall back to a single metric reference. TOOLSET GAP for api-explorer.
5. **GAP-OURS — relationship join keys missing.** MPB relationships need `childExpression`/`parentExpression` value predicates (which metric of child == which metric of parent). Our YAML has only `{parent, child}`. Schema evolution required.
6. **GAP-OURS — events model mismatch.** MPB events are API-list-pull + severity-map + object-matcher, not metric-threshold DSL. Our 9 events either need redesign, or render to `events: []` and migrate to post-install symptom/alert authoring.
7. **GAP-OURS — isKpi / unit / groups / timeseries.** Our YAML uses these; all are default-empty in every reference MP. Effect at runtime unclear. Probably safe to emit, but don't expect them to do anything visible until verified.
8. **WIRE-SURPRISE — is_world semantics.** Our `is_world: true` = MPB's `isListObject: false` (inverse). Plus every world-object metricSet uses `listId: "base"`.
9. **WIRE-SURPRISE — `@@@MPB_QUOTE` is LITERAL.** Not a description; the renderer must emit the string `@@@MPB_QUOTE <part-id> @@@MPB_QUOTE` verbatim in every `expressionText` field.
10. **WIRE-SURPRISE — dual id fields per object.** `object.id` AND `object.internalObjectInfo.id` are independent random strings.
11. **WIRE-SURPRISE — MPB-UI emits duplicate wildcard paths** (`data.*.*` alongside `data.pools.*`). Unclear if this matters; renderer likely doesn't need to replicate.
12. **GAP-EXISTING — no Synology event sample.** The only event wire-format evidence is Rubrik's. Renderer will have to invent from one example.
