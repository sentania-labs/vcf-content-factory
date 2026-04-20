# MPB (Management Pack Builder) API Surface

**Namespace**: `/suite-api/internal/mpbuilder/*` on VCF Ops 9.0.2.

**Auth**: bearer token `Authorization: vRealizeOpsToken <token>`. All
endpoints require the unsupported header:

    X-Ops-API-use-unsupported: true

Missing header → 404. Wrong header → same. Treat this entire
namespace as `/internal/*` per CLAUDE.md §7.

**OpenAPI coverage**: neither `docs/internal-api.json` nor
`docs/operations-api.json` documents any of this. The MPB API is
undocumented in the shipped specs. Everything below is empirically
confirmed on `vcf-lab-operations-devel.int.sentania.net` on
2026-04-17.

## Endpoint catalog

| Method | Path                                                             | Purpose                                | Status     |
|--------|------------------------------------------------------------------|----------------------------------------|------------|
| GET    | `/suite-api/internal/mpbuilder/designs`                          | List all designs (summaries)           | CONFIRMED  |
| POST   | `/suite-api/internal/mpbuilder/designs/import`                   | Import a design from export.json       | CONFIRMED  |
| DELETE | `/suite-api/internal/mpbuilder/designs?id={uuid}`                | Delete a design (**query-param**)      | CONFIRMED  |
| DELETE | `/suite-api/internal/mpbuilder/designs/{id}` (path-param)        | **BROKEN** — always 500 NPE            | BUG        |
| GET    | `/suite-api/internal/mpbuilder/designs/export?id={uuid}&userWillVerifySensitiveInfo=true` | Download design export JSON | CONFIRMED (requires VALID status) |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}`                     | Get full design detail                 | CONFIRMED  |
| PUT    | `/suite-api/internal/mpbuilder/designs/{id}`                     | Update design (full replace)           | CONFIRMED (422 if id missing) |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/status`              | Get design status breakdown            | CONFIRMED  |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/source`              | Get source (connection) config         | CONFIRMED  |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/requests`            | List HTTP requests in design           | CONFIRMED  |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/objects`             | List object types in design            | CONFIRMED  |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/objects/{objId}`     | Get object detail (metrics/properties) | CONFIRMED  |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/relationships`       | List relationship types                | CONFIRMED  |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/events`              | List event types                       | CONFIRMED  |
| POST   | `/suite-api/internal/mpbuilder/designs/{id}/install`             | **Build + install** the pak            | CONFIRMED (requires VALID design) |

**No endpoints found for:**
- Standalone pak build-without-install (checked `/build`, `/package`,
  `/pak`, `/export?asPak=1`, `/install?exportOnly=true`). Query
  params on `/install` are silently ignored.
- Separate pak download (`/pak`, `/paks`, `/artifact`, `/artifacts`,
  `/downloadPak`, `/installers`, `/pakManager`).
- Build history / async job inspection (`/builds`, `/deployments`,
  `/{id}/deployments/{depId}`). The `DEPLOYMENT_STATUS` object the
  install endpoint returns has no follow-up GET surface.
- Source environment test (`/source/test`, `/designs/{id}/test`).
  Yet the design stays INVALID until a "source test" happens —
  this is evidently UI-only and gates `/install` and `/export`.
- API docs / OpenAPI self-description (`/swagger.json`,
  `/openapi.json` both 403).

## Request/response shapes

### `POST /designs/import`

- **Request body**: JSON matching `export.json` format. Top-level
  keys: `type`, `design`, `source`, `objects`, `relationships`,
  `events`, `requests`. (This is the same envelope the MPB UI's
  Export button produces — see
  `tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json`
  for a working reference.)
- **Sanitization**: design name is stripped of whitespace,
  punctuation, and non-alphanumerics. "api-explorer-probe-20260418"
  became "apiexplorerprobe20260418" server-side.
- **Response**: `201 Created` + `{"id": "<design-uuid>"}`. The
  returned UUID is different from any UUID embedded in the import
  body (server assigns fresh IDs).
- **Errors**: empty or malformed body → 400
  `{"type":"Error","message":"Invalid input format.",...}`.

### `GET /designs/export?id={uuid}&userWillVerifySensitiveInfo=true`

- Returns the same envelope shape accepted by `/designs/import`.
- **Requires `designStatus.status == "VALID"`**, otherwise 403:
  `{"message":"This operation cannot be run on a design that is not valid.", "apiErrorCode": 1518}`.
- `userWillVerifySensitiveInfo=true` is mandatory — 400 if missing.

### `POST /designs/{id}/install`

- **Request body**: empty `{}` is accepted.
- **Response**: `201 Created` + async envelope:
  ```json
  {
    "type": "DEPLOYMENT_STATUS",
    "id": "<deployment-uuid>",
    "status": "IN_PROGRESS",
    "startTime": <epoch-ms>,
    "endTime": 0,
    "result": {}
  }
  ```
- **Observed behavior**: on an INVALID design, `/install` returns
  201 but the deployment is silently a no-op — design remains
  `installed: false`, `installStatus: null/DRAFT`. No 422, no
  error. The call does not leave artifacts.
- **Unknown**: on a VALID design, does `/install` produce a pak
  alongside deploying it? Could not test end-to-end because
  Scott's Synology design on devel is INVALID (needs source test
  the API doesn't expose). **This is the critical gap for Phase 3.**

### `GET /designs/{id}/status`

Returns counts + errors per section:

```json
{
  "status": "VALID|INVALID|...",
  "installStatus": "DRAFT|INSTALLED|...",
  "designInfo":    {"errors":[], "itemCount":N},
  "source":        {"errors":[{"refId","error"}], "itemCount":1},
  "requests":      {"errors":[], "itemCount":N},
  "objects":       {"errors":[], "itemCount":N},
  "events":        {"errors":[], "itemCount":N},
  "relationships": {"errors":[], "itemCount":N},
  "configuration": {"errors":[], "itemCount":N}
}
```

Each section's errors block carries `refId` (the offending
sub-object UUID) and `error` (human text).

**This is the validation-errors dump the MPB UI's red-dot indicators
are derived from.** Confirmed 2026-04-18 on Synology DSM design on
devel: every UI-visible issue appears here verbatim, keyed by
element UUID. Join against `/objects`, `/events`, `/relationships`,
`/requests` summaries to resolve `refId` → display name.

Alternative: `GET /designs/{id}` embeds the identical `designStatus`
block at the top level of the full design response (plus
`id`/`name`/`version`/`description`/`status`/`installed`). Use
`/status` when you only need validation state — it's the leaner
payload.

**No dedicated `/validate`, `/errors`, `/validation` endpoint exists.**
All three return 404 (both GET and POST) on 9.0.2. Validation runs
implicitly on import/update; `/status` just returns the persisted
result.

**Validation error vocabulary observed so far** (by section, from
the Synology design probe):

- `objects`: `"Request <reqname> did not return attributes required
  to make metrics on this object. Ensure the request runs correctly,
  remove affected metrics from this object, or remove the object."`
  Means: the request ran (in the last source-test) but its response
  didn't carry the fields the object's metrics/properties
  reference — a mismatch between declared attribute path and actual
  response structure. refId is the **object** id, not the request id
  (request name is interpolated into the error text).
- `events`: `"Connection to object references a property that does
  not exist."` Means: the event matcher's anchor property (the one
  that ties the event to an object instance, typically `name` or a
  unique identifier on the object) is not declared on the target
  object's property list. refId is the **event** id.
- `relationships`: two errors per broken relationship, one
  `"Child property used in relationship does not exist."` and one
  `"Parent property used in relationship does not exist."` Means:
  the join-key properties on the parent and/or child objects that
  the relationship uses to match instances aren't declared on those
  objects' property lists. refId is the **relationship** id.
- `source`, `designInfo`, `requests`, `configuration`: no error
  vocabulary surfaced in this sample (all clean). Future probes
  can extend this list.

### `DELETE /designs?id={uuid}`

- Query-param form. Returns 200 with empty body on success.
- Path-param `DELETE /designs/{id}` returns 500 NPE regardless of
  whether the ID exists — this is a **server bug** in the
  path-based handler. Always use the query-param form.

## Auth / session notes

- Bearer token from `/suite-api/api/auth/token/acquire` works for
  all these endpoints. No CSRF/session cookie needed.
- UI session (JSESSIONID from `/ui/login.action`) is a separate
  path — MPB UI at `/ui/mpbuilder/` does its own VCF-SSO login
  flow and could not be driven headlessly during this
  investigation. The suite-api path is the right plumbing for
  programmatic use.

## What this means for Phase 3 tooling

**Achievable with this API:**
1. Programmatically import an MPB design from a local JSON file
   (`POST /designs/import`).
2. Get that design's status / validation errors (`GET /designs/{id}/status`).
3. Delete the design when done (`DELETE /designs?id={uuid}`).
4. If the design is already VALID (e.g. source test previously
   passed through the UI), trigger `POST /designs/{id}/install` to
   build + install on the same cluster.

**Not achievable with this API (blockers):**
1. **No pak download.** The "build a signed pak and hand it back
   as a file" workflow does not exist as an API endpoint. Install
   is the only build-trigger, and it deploys directly to the
   cluster it ran on. If Phase 3 requires a transferable signed
   pak, MPB API alone isn't enough — the UI's "Save Pak" button
   (if it exists) hasn't been located, and may be purely a
   client-side bundle of the import-envelope (not a signed pak).
2. **No source-test API.** Designs stay INVALID after import until
   something runs the source environment test. No
   `/source/{id}/test` or `/designs/{id}/test` endpoint responded.
   This test is likely UI-only in 9.0.2, blocking a pure-API
   import-then-build pipeline unless pre-tested designs are
   imported via other means or the test can be stubbed.

## Open questions / follow-ups

- **Does `POST /install` on a VALID design produce a pak byte
  stream somewhere?** Couldn't test without a VALID design on
  devel.
- **Can the source-test be triggered headlessly?** May require
  sniffing actual MPB UI XHR traffic while a user clicks "Test
  Connection" — this investigation did not capture UI traffic.
- **Is the DELETE path-param 500 fixable on 9.0.2 or server-side-only?**
  Bug exists but is working around via query-param form. Not
  worth chasing.
- **Does `/install` on a design with a local (non-HTTP) source
  type behave differently?** Only tested HTTP adapter type.

## Exchange format — flat vs. nested (2026-04-18)

The factory's `render_mp_design_json()` produces the **flat Rubrik format**
(same as `adapters.zip/conf/template.json`). The MPB UI Import/Export API
(`POST /designs/import`) requires the **exchange format** (`export.json`).

These two formats share the same internal schemas (authentication, metricSets,
expressions, dataModelLists) but differ in top-level organization:

| Flat (template.json)              | Exchange (export.json)                              |
|-----------------------------------|-----------------------------------------------------|
| `.version`, `.id`, `.constants`   | (dropped)                                           |
| `.pakSettings.name/version/desc`  | → `.design.design.{name,type,description,version}`  |
| `.source.type`                    | → `.type` (top-level) + `.design.design.type`       |
| `.source.basePath`                | → `.source.source.configuration.baseApiPath`        |
| `.source.authentication`          | → `.source.source.authentication` (same schema)     |
| `.source.configuration`           | → `.source.configuration` (same position)           |
| `.source.requests` (dict)         | → `.requests` (list of `{"request": ...}`)          |
| `.source.resources` (list)        | → `.objects` (list of `{"object": ...}`)            |
| `.relationships` (list)           | → `.relationships` (list of `{"relationship": ...}`) |
| `.source.events` (list)           | → `.events` (flat list, `designId` stripped)        |
| test request (from requests dict) | → `.source.source.testRequest`                      |
| `_render_global_headers()`        | → `.source.source.globalHeaders`                    |

The `source.source.id` field is MPB-server-minted (UUID4) in the reference export;
the factory derives a stable UUID5 from `adapter_kind` per CLAUDE.md §6.

**Factory support**: `python3 -m vcfops_managementpacks render-export <mp.yaml> --out <output.json>`
implemented in `vcfops_managementpacks/render_export.py` (2026-04-18).

## Pak conf/ layout — both design.json AND export.json required (2026-04-18)

**Root cause of Synology silent adapter-kind registration failure (2026-04-18).**

The MPB adapter runtime requires BOTH files to be present in `adapters.zip/<adapter_dir>/conf/`:

| File | Format | Read by | Purpose |
|---|---|---|---|
| `conf/design.json` | Flat factory-grammar (version/id/name/pakSettings/source/constants/relationships) | Internal MPB tooling / template engine | Design persistence / template |
| `conf/export.json` | Exchange format (type/design/source/objects/relationships/events/requests) | Adapter runtime at init (post-install redescribe) | **Adapter kind registration** |

The factory was previously writing only `design.json` (flat format, correct content).
`export.json` was entirely absent. The adapter runtime silently skipped registration —
pak installed in ~35s vs Rubrik's 100-200s, and `getIntegrations` never showed the adapter kind.

**Confirmed from Rubrik-1.1.0.25.pak (mpb_rubrik_adapter3/conf/):**
Both files are present. `design.json` uses the flat format; `export.json` uses the exchange format.
The two files are structurally different — they are NOT the same content in two formats.

**Fix applied 2026-04-18**: `vcfops_managementpacks/builder.py` `build_pak()` now calls
`render_mpb_exchange_json()` and writes the result to `conf/export.json` alongside the existing
`conf/design.json`. Both files are required.

**Structural divergences from Rubrik export.json (benign)**:
- `type` key appears at top level in our output; absent in Rubrik's. Does not break import.
- `design.design` lacks `id: null` and `author: ""` null/empty placeholders. Equivalent.
- `source.source` lacks `designId: null`. We strip it as a flat-format-only field. Equivalent.
- `content: []` key present in Rubrik, absent in ours. Empty list; not required for registration.

## Source Test Endpoint (2026-04-18 sniffing attempt — NOT FOUND)

**Status**: Source-test endpoint **not located on `/suite-api/`**. Headless
Playwright sniffing of the MPB UI is blocked by VCF-SSO on
`/vcf-operations/*` (per `project_vcf_operations_url_structure.md`).
Designs imported via `POST /designs/import` stay INVALID with
`"Source requires environment test response after import."` and cannot
be transitioned to VALID via any endpoint reachable by bearer auth.

### Playwright blocker

- `/ui/login.action` accepts local auth and returns a JSESSIONID.
- MPB UI lives ONLY under `/vcf-operations/rest/ops/...` and `/vcf-operations/plug/ops/...`,
  which are SSO-gated. Every `/vcf-operations/*` path 302s to
  `login.action?vcf=1&uri=<b64>` for any non-SSO session.
- SSO unlock requires full OAuth2 auth_code flow through
  `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/t/CUSTOMER/authorize`
  — cannot be driven by env-var headless Playwright.
- `/ui/mpbuilder/` returns 404; there is no legacy Struts mpb entry point.
- Bearer token against `/vcf-operations/rest/ops/internal/mpbuilder/*` → 302 (SSO).
- To sniff the actual "Test Connection" XHR, a human-in-the-loop
  Chrome DevTools capture during Scott's SSO'd browser session is
  required. Playwright cannot replicate.

### Endpoint enumeration done (all 404/405 on devel)

Exhaustive probe of bearer-auth-reachable paths on `/suite-api/internal/mpbuilder/`
for an INVALID design with known `{designId}`, `{sourceId}`, `{testRequestId}`:

- `/designs/{id}/test`, `/designs/{id}/testConnection`, `/designs/{id}/test-connection`
- `/designs/{id}/validate`, `/designs/{id}/check`, `/designs/{id}/checkSource`
- `/designs/{id}/environmentTest`, `/designs/{id}/environment-test`,
  `/designs/{id}/environment`, `/designs/{id}/runTest`, `/designs/{id}/connect`
- `/designs/{id}/source/test`, `/designs/{id}/source/validate`,
  `/designs/{id}/source/run`, `/designs/{id}/source/send`,
  `/designs/{id}/source/execute`, `/designs/{id}/source/invoke`,
  `/designs/{id}/source/discover`, `/designs/{id}/source/testRequest`,
  `/designs/{id}/source/testResponse`, `/designs/{id}/source/response`,
  `/designs/{id}/source/environment`, `/designs/{id}/source/run-test`,
  `/designs/{id}/source/{sourceId}/test`
- `/designs/{id}/testRequest/...`, `/designs/{id}/testResponse`,
  `/designs/{id}/responses/{testRequestId}`, `/designs/{id}/sourceResponse`
- `/designs/{id}/requests/{reqId}/run|send|execute|invoke|test|response`
- `/sources/*`, `/sources/{id}/test`, `/source/{id}/test`
- `/test`, `/testSource`, `/validate`, `/validation/*`, `/environmentTest`
- `/suite-api/api/mpbuilder/*`, `/suite-api/internal/mpb/*`,
  `/suite-api/internal/contentauthoring/*`, `/suite-api/internal/mpauthoring/*`
- Query-string commands: `?action=test|testConnection|environmentTest`,
  `?test=true`, `?cmd=test`, `?operation=test`, `?verify=true` on
  `/designs/{id}` and `/designs/{id}/source` (200/400/500 but all
  behaviour-invariant vs. no query)
- Body-command POST to `/designs/{id}`: `{"action":"test"}`,
  `{"operation":"test"}` → 500 (generic handler error, not a dispatch hit)

**Only distinct live sub-routes under `/designs/{id}/` found:**
`/source` (GET/PUT; POST returns "already exists"),
`/status`, `/requests`, `/objects`, `/relationships`, `/events`,
`/install`. None trigger source test.

### Pre-tested import does not bypass INVALID

Re-importing `tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json`
(which originated from a VALID UI-tested design, with
`source.source.testRequest.response.result.responseCode = 200`)
still lands INVALID with the same error. The exported response
payload is stripped during round-trip, and/or the server
requires a server-side execution of the test, not a client-supplied
response.

### Verdict for Phase 3

**Pure-API end-to-end MPB automation (import → source-test → install)
is NOT achievable on VCF Ops 9.0.2 with currently-known endpoints.**
The remaining options:

1. **Human-in-the-loop**: Scott clicks Test Connection in the MPB UI
   after a factory-driven import. Unblocks `/install` immediately after.
2. **Sniff from Scott's browser**: one-time capture of Chrome DevTools
   network log during Test Connection click, share HAR with api-explorer.
   If the call goes to `/suite-api/internal/mpbuilder/*` with bearer,
   we win. If it goes to `/vcf-operations/rest/ops/*` with SSO session,
   we're blocked headlessly regardless.
3. **Punt to a future VCF Ops release** where `/suite-api/` may gain
   the test endpoint.

### Collateral note — import may collide on `source.source.id`

During the probe, re-importing a design whose `source.source.id`
matches an existing design appears to have caused the existing
design to disappear from the listing (reproduced once, not
conclusively). When the factory renders export.json it mints a
stable UUID5 per-adapter, so two factory-driven imports of the
same adapter will collide. **Hypothesis (NOT confirmed)**: the
importer dedupes by `source.source.id` silently, overwriting
prior designs. Needs dedicated follow-up investigation before
relying on back-to-back import behaviour.

## Exchange format — field-level diff (2026-04-17 investigation)

Structural diff of `tmp/synology_mpb_import.json` vs
`tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json`.
Confirmed via binary-substitution live-import tests (requests/objects
pass; events fail).

### Fields present in flat format that MPB's import parser rejects

These cause HTTP 400 "Invalid input format" when present anywhere in
the payload:

| Field | Location | Flat format value | Fix |
|---|---|---|---|
| `example` | expressionParts, dataModelList attributes, session variables | `""` or `None` | Stripped globally by `_strip_flat_only_fields()` |
| `regex` | expressionParts | `null` | Stripped globally |
| `regexOutput` | expressionParts | `""` | Stripped globally |
| `_renderer_note` | relationships, expressionParts | string | Stripped globally |
| `value` | `authentication.creds[]` | `null` | Stripped in `_strip_cred()` |
| `internalObjectInfo.id` | objects | string ID | Stripped in `_strip_internal_object_info()` |
| `metricSets[].objectBinding` | objects | `null` | Stripped in `_strip_metric_set()` |
| `metricSets[].metrics[].timeseries` | objects | `null` | Stripped in `_strip_metric()` |
| `dataModelLists` | auth session requests (getSession/releaseSession) and testRequest response | list | Dropped in `_strip_session_request()` — these three use `{responseCode: N}` only |

### Events wire format — RESOLVED 2026-04-18

**Fix**: each item in `events[]` must be wrapped in `{"event": {...}}`,
matching the wrapping convention used by `objects[]` (`{"object": {...}}`),
`relationships[]` (`{"relationship": {...}}`), and `requests[]`
(`{"request": {...}}`).

The factory currently emits **bare** event objects at the top of
`events[]`, inherited from the flat-format layout where `source.events`
is a flat list. The export exchange format disagrees: all four arrays
use singular-key wrappers.

**Verification on devel 2026-04-18** (api-explorer probe):
- `tmp/synology_export.json` (factory output, 8 events bare) →
  `POST /suite-api/internal/mpbuilder/designs/import` returns HTTP 400
  `{"message":"Invalid input format.","moreInformation":[{"name":"errorMessage","value":"Unknown error when executing request"}]}`.
  Removing the events array (`events: []`) flips to 201 Created.
  Wrapping each event as `{"event": <original>}` also flips to 201 Created.
- The content of each event (`id`, `alert.{type,badge,subType,waitCycle,cancelCycle,recommendation}`,
  `label`, `listId`, `message`, `severity`, `matchMode`, `requestId`,
  `severityMap[]`, `eventMatchers[]`, `defaultSeverity`,
  `unmatchedEventBehavior`) is accepted verbatim — none of those
  fields need stripping. Only the list-item wrapping is wrong.

**Earlier line-199 entry in this doc — correct for flat format, wrong
for exchange format**. Update when rewriting the flat-vs-exchange table:
events in exchange format are `events → list of {"event": ...}` like
the other three sections, not "flat list".

**Tooling fix location**: `vcfops_managementpacks/render_export.py`.
Wherever it builds the `events` list, wrap each item:
`{"event": <current>}` — same pattern as the existing `{"object": ...}`,
`{"request": ...}`, `{"relationship": ...}` emitters.

**Also note**: the import endpoint never returns field-level diagnostics
for schema mismatches — it returns the generic
`{"type":"Error","message":"Invalid input format.","moreInformation":[{"name":"errorMessage","value":"Unknown error when executing request"}]}`
envelope. The only way to diagnose a 400 on this endpoint is
bisection/binary-substitution against a known-good payload. Keep
`/tmp/mpb_bisect.py`-style probes handy.

## References

- CLAUDE.md §7 (`X-Ops-API-use-unsupported`)
- `tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json`
  — working export envelope reference
- `tmp/vcf_operations_mp_designs_export.zip` — MPB UI Export output (byte-for-byte identical to above)
- Memory `project_vcf_operations_url_structure.md` — URL structure
  for VCF Ops 9.0.2 (MPB UI is behind `/vcf-operations/*` SSO)

## 2026-04-18 — UI-path MPB job endpoints (from Scott's DevTools capture)

The MPB UI talks to a **separate namespace** from `/suite-api/internal/mpbuilder/*`. Host-relative URLs:

### POST `/vcf-operations/rest/ops/internal/mpbuilder/designs/{designId}/jobs`
Triggers async source-test jobs. Two observed `testType` values:
- `GET_SESSION` — just the auth step; tests `sessionSettings.getSession` in isolation
- `TEST_CONNECTION` — full connection test; requires prior GET_SESSION response to be embedded under `sessionSettings.getSession.response` in the body (MPB carries state forward between the two calls)

Request body shape:
```json
{
  "jobType": "TEST_SOURCE",
  "type": "HTTP",
  "testType": "GET_SESSION" | "TEST_CONNECTION",
  "source": { ... full source block ... },
  "additionalTrustedCertificates": []
}
```

Response: action id (for polling).

### GET `/vcf-operations/rest/ops/api/actions/{actionId}/status?detail=true`
Polls job status. Detail flag returns full result body including test-response and dataModelLists.

### Auth model for `/vcf-operations/rest/ops/*`
- Session cookie: `JSESSIONID` (obtained via VCF-SSO OAuth flow or local UI login)
- `csrf-token` header (required)
- `x-requested-with: XMLHttpRequest` (required)
- `x-ops-api-use-unsupported: true` (for internal endpoints)
- Cookie-based, not bearer. To script this headlessly: full VCF-SSO OAuth2 flow through `/acs/t/CUSTOMER/authorize`, OR local admin login via `/ui/login.action` if the same JSESSIONID carries over (untested).

### Open question — is `/suite-api/` a proxy or parallel API?
`/suite-api/internal/mpbuilder/designs/*` handles CRUD (import, export, install). `/vcf-operations/rest/ops/internal/mpbuilder/designs/{id}/jobs` handles test-source. They may be one behind the other, or parallel. If `/jobs` is available at `/suite-api/` under bearer auth, Phase 3 full-auto unlocks. Untested — needs a careful probe with existing bearer creds.

### Session variable key rules — revisit
Validator on import path (`POST /designs/import`) rejects sessionVariable keys containing hyphens (e.g. `Set-Cookie`) — see earlier notes. **Runtime path `/jobs` accepts `Set-Cookie` with hyphen** per Scott's capture. Different code paths, different validators. Worth factoring into `render_export.py` decision: do we emit `Set-Cookie` (works at runtime, rejected by import validator) or `set_cookie` (accepted at import, unclear at runtime)? Needs concrete test before deciding.
