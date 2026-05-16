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

**Provenance.** This catalog merges (a) empirical probing on
`vcf-lab-operations-devel.int.sentania.net` 2026-04-17 through
2026-05-15 — the source of every CONFIRMED / BUG / BEHAVIORAL note
below; and (b) a clean-room reference authored 2026-05-15 from
independent observation of a running VCF Operations 9.0.0.0 (build
24723247) appliance, contributing the broader endpoint coverage
(`POST /designs`, `/verifyDesign`, source split, `/default` forms,
ancillaries). Where the two diverged, empirical wins — specifically,
bearer + `X-Ops-API-use-unsupported: true` works for the entire
namespace (the clean-room note that bearer 403s omitted that header).

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET    | `/suite-api/internal/mpbuilder/designs` | List all designs (summaries) | CONFIRMED |
| **POST** | **`/suite-api/internal/mpbuilder/designs`** | **Create a new design from `Design` body. Returns `CreatedIdResponse` (201).** | clean-room ref |
| POST   | `/suite-api/internal/mpbuilder/designs/import` | Import a design from export.json | CONFIRMED |
| DELETE | `/suite-api/internal/mpbuilder/designs?id={uuid}` | Delete one or more designs (**query-param, repeatable**) | CONFIRMED |
| DELETE | `/suite-api/internal/mpbuilder/designs/{id}` (path-param) | **BROKEN** — always 500 NPE | BUG |
| GET    | `/suite-api/internal/mpbuilder/designs/export?id={uuid}&userWillVerifySensitiveInfo=true` | Download design export JSON | CONFIRMED (requires VALID status) |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}` | Get full design detail (`DesignInfo`) | CONFIRMED |
| PUT    | `/suite-api/internal/mpbuilder/designs/{id}` | Update name/description/type only (full replace of full envelope returns 500 — see §"PUT /designs/{id}/objects/{objId} is broken") | CONFIRMED |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/status` | Per-section validation + install state | CONFIRMED |
| **PUT** | **`/suite-api/internal/mpbuilder/designs/{id}/verifyDesign/{jobId}`** | **Mark a design VALID using the result of a prior COLLECTION_PREVIEW job. Returns `VerifyStatus` (200 sync, 202 async). The missing piece that closes the import → preview → verify → install loop.** | clean-room ref |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/source` | Get full `Source` object | CONFIRMED |
| **POST** | **`/suite-api/internal/mpbuilder/designs/{id}/source`** | **Attach a source (`HttpSource` body). Returns `CreatedIdResponse`.** | clean-room ref |
| PUT    | `/suite-api/internal/mpbuilder/designs/{id}/source` | Replace the source. POST returns "already exists" if one is bound; use PUT to swap. | CONFIRMED |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/source/summary`** | **Flattened summary for the UI's Source tab (`HttpSourceSummary`).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/source/configuration`** | **Configuration field + credential summaries (`ConfigurationSummaries`).** | clean-room ref |
| **PUT** | **`/suite-api/internal/mpbuilder/designs/{id}/source/configuration`** | **Write configuration field + credential definitions (`ConfigurationPayload`).** | clean-room ref |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/requests` | List HTTP requests (`HttpRequestSummaries`) | CONFIRMED |
| **POST** | **`/suite-api/internal/mpbuilder/designs/{id}/requests`** | **Create a request (`HttpRequest` body). Returns `CreatedIdResponse`.** | clean-room ref |
| **PUT** | **`/suite-api/internal/mpbuilder/designs/{id}/requests`** | **Update one request (id on the body).** | clean-room ref |
| **DELETE** | **`/suite-api/internal/mpbuilder/designs/{id}/requests?id={uuid}`** | **Bulk delete (repeatable `id` query param).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/requests/{requestId}`** | **`HttpRequestForm` (the request + the requests it could chain from).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/requests/default`** | **Defaults-filled form for creating a new request.** | clean-room ref |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/objects` | List object types (`ObjectSummaries`) | CONFIRMED |
| **POST** | **`/suite-api/internal/mpbuilder/designs/{id}/objects`** | **Create an object definition.** | clean-room ref |
| PUT    | `/suite-api/internal/mpbuilder/designs/{id}/objects` | Update objects in bulk | CONFIRMED |
| **DELETE** | **`/suite-api/internal/mpbuilder/designs/{id}/objects?id={uuid}`** | **Bulk delete (repeatable `id` query param).** | clean-room ref |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/objects/{objId}` | `ObjectForm` (object + the requests it can reference) | CONFIRMED |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/objects/default`** | **Defaults-filled form for new object.** | clean-room ref |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/relationships` | List relationship types (`RelationshipSummaries`) | CONFIRMED |
| **POST** | **`/suite-api/internal/mpbuilder/designs/{id}/relationships`** | **Create. Body: `RelationshipPayload` (relationship + foreign object types pulled in).** | clean-room ref |
| **PUT** | **`/suite-api/internal/mpbuilder/designs/{id}/relationships`** | **Update.** | clean-room ref |
| **DELETE** | **`/suite-api/internal/mpbuilder/designs/{id}/relationships?id={uuid}`** | **Bulk delete (repeatable).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/relationships/{relationshipId}`** | **`RelationshipForm` (relationship + candidate object set).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/relationships/default`** | **Defaults-filled form.** | clean-room ref |
| GET    | `/suite-api/internal/mpbuilder/designs/{id}/events` | List events (`EventSummaries`) | CONFIRMED |
| **POST** | **`/suite-api/internal/mpbuilder/designs/{id}/events`** | **Create. Body: `HttpEventPayload`.** | clean-room ref |
| **PUT** | **`/suite-api/internal/mpbuilder/designs/{id}/events`** | **Update.** | clean-room ref |
| **DELETE** | **`/suite-api/internal/mpbuilder/designs/{id}/events?id={uuid}`** | **Bulk delete (repeatable).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/events/{eventId}`** | **`EventForm` (event + referenceable requests and objects).** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/events/default`** | **Defaults-filled form.** | clean-room ref |
| POST   | `/suite-api/internal/mpbuilder/designs/{id}/jobs` | Submit a job. **`jobType ∈ {COLLECTION_PREVIEW, REQUEST, TEST_SOURCE}`**. Returns `AbstractJobResponse` (201) or `CollectionPreviewResponse` (202 async). | CONFIRMED (TEST_SOURCE empirically; COLLECTION_PREVIEW and REQUEST per clean-room ref) |
| **GET** | **`/suite-api/internal/mpbuilder/designs/{id}/jobs/collectionpreview/latest`** | **Id of the most recent preview job. Pair with `verifyDesign/{jobId}`.** | clean-room ref |
| POST   | `/suite-api/internal/mpbuilder/designs/{id}/install` | Build + install the pak (requires VALID design) | CONFIRMED |
| GET    | `/suite-api/internal/mpbuilder/designs/{designId}/install/{deploymentId}` | Poll install progress | CONFIRMED |
| **GET** | **`/suite-api/internal/mpbuilder/existingobjecttypes`** | **List every object type already declared by some installed adapter. This is the backend the MPB "Add New Object" picker queries.** | clean-room ref |
| **GET** | **`/suite-api/internal/mpbuilder/existingobjecttypes/details?adapterKindKey=...&resourceKindKey=...`** | **Details for one external object type. Useful for diffing what MPB sees of a given kind across environments.** | clean-room ref |
| **POST** | **`/suite-api/internal/mpbuilder/testregex`** | **UI helper: `{regex, sample}` → `{valid, output, error, duration_ms}`.** | clean-room ref |

**Bold rows** are endpoints added via the 2026-05-15 clean-room merge.
They are not yet empirically tested in this repo — the schemas and
paths are authoritative per the on-appliance OpenAPI spec at
`/usr/lib/vmware-vcops/tomcat-enterprise/webapps/suite-api/docs/openapi/v3/dev-api.json`
on a 9.0.0.0 (build 24723247) appliance.

**End-to-end "create from scratch" loop now possible** (untested but
endpoint-complete):

1. `POST /designs` — create empty design.
2. `POST /designs/{id}/source` — attach an HttpSource.
3. `POST /designs/{id}/requests` — add HTTP requests.
4. `POST /designs/{id}/objects` — add object definitions.
5. `POST /designs/{id}/relationships` — add relationships.
6. `POST /designs/{id}/events` — optional events.
7. `POST /designs/{id}/jobs` with `jobType=TEST_SOURCE` — runs source test.
8. `POST /designs/{id}/jobs` with `jobType=COLLECTION_PREVIEW` — runs preview, returns job id.
9. `GET /designs/{id}/jobs/collectionpreview/latest` — get the preview job id.
10. `PUT /designs/{id}/verifyDesign/{jobId}` — mark VALID using the preview result.
11. `POST /designs/{id}/install` — build + install the pak.

This is the closed loop the prior "Source Test Endpoint NOT FOUND"
section (below) said didn't exist. Steps 7-10 are the missing link
that the clean-room reference surfaced.

**Use case for the factory:** programmatically build a reference
design via this API, then `GET /designs/export` to dump the
"canonical" JSON that MPB itself would emit. Diff against factory
`render-export` output to find any field-level mismatches the
factory needs to fix. This is now the recommended way to learn
the wire format, replacing the older "import factory JSON and see
what breaks" bisection approach.

**No endpoints found for:**
- Standalone pak build-without-install (checked `/build`, `/package`,
  `/pak`, `/export?asPak=1`, `/install?exportOnly=true`). Query
  params on `/install` are silently ignored.
- Separate pak download (`/pak`, `/paks`, `/artifact`, `/artifacts`,
  `/downloadPak`, `/installers`, `/pakManager`).
- Build history / async job inspection (`/builds`, `/deployments`,
  `/{id}/deployments/{depId}`). The `DEPLOYMENT_STATUS` object the
  install endpoint returns has no follow-up GET surface.
- API docs / OpenAPI self-description (`/swagger.json`,
  `/openapi.json` both 403). The dev spec at
  `/usr/lib/vmware-vcops/.../openapi/v3/dev-api.json` is on-appliance
  filesystem, not API-served.

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

## Pak conf/ layout — both design.json AND export.json required (2026-04-18, reconfirmed 2026-05-15)

**Root cause of Synology silent adapter-kind registration failure (2026-04-18).**

The factory was previously writing only `design.json` (flat format, correct content).
`export.json` was entirely absent. The adapter runtime silently skipped registration —
pak installed in ~35s vs Rubrik's 100-200s, and `getIntegrations` never showed the adapter kind.

**Fix applied 2026-04-18**: added `conf/export.json` (MPB UI exchange format) alongside
the existing `conf/design.json`. Both files were present in Rubrik-1.1.0.25.pak at the
time, and requiring both matched empirical evidence from a working pak install.

**Attempted rescission 2026-05-15 — REVERTED**: MPB-built paks exported via the MPB UI
for UniFi and vSphere Storage Paths ship ONLY `conf/export.json`. Based on this
observation, `design.json` was removed from factory pak builds on 2026-05-15. This caused
"Applied Adapter (Failed)" on prod when vSphere Storage Paths 2.0.0.6 was installed
(first build lacking `design.json`). The 2.0.0.5 pak (which had `design.json`) installed
successfully. The removal has been reverted.

**Why MPB UI exports lack design.json**: the MPB designer's pak-build pipeline evidently
injects `design.json` via a separate mechanism (not via the UI export path). Factory
builds do not have access to that path and must include `design.json` explicitly.

**Rule**: both `design.json` and `export.json` are required in `conf/` for adapter-kind
registration on the 9.0.x runtime. Do not remove `design.json` without a confirmed
working prod install.

**Current layout** (`adapters.zip/<adapter_dir>/conf/`):

| File | Format | Read by | Purpose |
|---|---|---|---|
| `conf/design.json` | Flat factory-grammar format (same as template.json structure) | Adapter runtime at init (post-install redescribe) | **Adapter kind registration (required)** |
| `conf/export.json` | Exchange format (type/design/source/objects/relationships/events/requests) | Adapter runtime at init (post-install redescribe) | **Adapter kind registration (required)** |
| `conf/template.json` | Template format (requestedMetrics, converted auth, etc.) | Gen-2 adapter JAR (SHA256 validated at every collection) | **Collection runtime** |

See `context/mp_format_comparison_2026_05_15.md §item 8` (REVERTED).

**Structural divergences from Rubrik export.json (benign)**:
- `type` key appears at top level in our output; absent in Rubrik's. Does not break import.
- `design.design.id` and `design.design.author` are now stripped (2026-05-15 fix #3).
- `design.buildNumber` is now stripped (2026-05-15 fix #3).
- `source.source` lacks `designId: null`. We strip it as a flat-format-only field. Equivalent.
- `content: []` key present in Rubrik, absent in ours. Empty list; not required for registration.

## Source Test Endpoint (2026-04-18 sniffing attempt — NOT FOUND)

**STATUS UPDATE 2026-05-15:** This section is **historically accurate but
operationally superseded.** The closed loop has since been mapped:
- Source test is `POST /jobs` with `jobType=TEST_SOURCE` (confirmed
  2026-04-29 below — bearer-reachable at `/suite-api/`).
- Collection preview is `POST /jobs` with `jobType=COLLECTION_PREVIEW`.
- Mark VALID is `PUT /designs/{id}/verifyDesign/{jobId}` (clean-room
  reference, 2026-05-15 — see endpoint catalog).

The headless Playwright sniffing path and the exhaustive endpoint
enumeration below remain as historical record of *how the wrong
answer was reached*, not the current diagnostic. Leave for forensic
context; do not act on its "NOT FOUND" verdict.

---

**Original status (2026-04-18)**: Source-test endpoint **not located on `/suite-api/`**. Headless
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

## Schema reference (clean-room merge, 2026-05-15)

Field-level schema for the major types crossed by the API surface.
Empirical wire-format quirks (which fields must be stripped on
import, which sections wrap individual items, etc.) live in the
"Request/response shapes" and "Exchange format" sections above —
**read those first** before writing a payload. This section is
the field-list reference, not the formatting rulebook.

### Top-level design

**`Design`** (write-shape, `POST /designs` and `PUT /designs/{id}`):

| Field | Type | Notes |
|---|---|---|
| `name` | string | Becomes the `AdapterKind` key of the installed adapter; must be unique and stable for the life of the design. MPB sanitizes — strips whitespace and non-alphanumerics for the adapter-kind slug (visible design `name` may retain spaces, but the adapter-kind derivative will not). |
| `description` | string | Mirrors onto the adapter. |
| `type` | `DesignType` | Effectively "HTTP" in 9.0; HTTP is the only source kind exposed. |

**`DesignInfo`** (read-shape, `GET /designs/{id}`):

| Field | Type |
|---|---|
| `id` | uuid |
| `name` | string |
| `version` | string — flows to deployed adapter version |
| `description` | string |
| `installed` | boolean |
| `status` | `DesignValidationStatus` |
| `designStatus` | `DesignStatus` |

**`DesignStatus`** (read-shape, `GET /designs/{id}/status`):

| Field | Type | Notes |
|---|---|---|
| `installStatus` | `"DRAFT" \| "INSTALLED" \| "OUT_OF_DATE" \| "REMOVED"` | |
| `status` | `DesignValidationStatus` (`VALID`/`INVALID`/...) | Aggregate lint state. |
| `designInfo`, `source`, `requests`, `objects`, `events`, `relationships`, `configuration` | `DesignSectionInfo` (each: `{errors: [{refId, error}], itemCount: N}`) | Per-tab validation, drives UI section badges. |

**`VerifyStatus`** — `{verified: boolean, reason?: string}` returned by `PUT /verifyDesign/{jobId}`.

**`CreatedIdResponse`** — `{id: uuid}` returned by every creating POST.

### Source

**`HttpSource`** (write-shape, `POST/PUT /source`):

| Field | Type | Notes |
|---|---|---|
| `id?` | uuid | Null on creation. |
| `globalHeaders` | `HttpHeader[]` | Applied to every request **except** session-acquisition request when session-auth is in use. |
| `configuration` | `HttpDesignConfiguration` | hostname, port, baseApiPath, TLS. |
| `authentication` | `HttpDesignAuthentication` | auth mode + credential field definitions. |
| `testRequest` | `HttpRequest` | Canary request for connectivity validation. |

**`HttpSourceSummary`** (read-shape, `GET /source/summary`): `{id?, hostname, port, path, sslSetting, authenticationType, httpMethod}`.

**`ConfigurationSummaries`** — `{fields: ConfigurationFieldSummary[], credentials: CredentialFieldSummary[]}`.
**`ConfigurationPayload`** — write-shape mirror.

### Requests

**`HttpRequest`**:

| Field | Type | Notes |
|---|---|---|
| `id?` | uuid | Null on creation. |
| `name` | string | UI label. |
| `path?` | string | Appended to `source.configuration.baseApiPath`. Empty = call the base path. |
| `body?` | string | |
| `headers` | `HttpHeader[]` | Merged with source `globalHeaders`. |
| `params` | `HttpParameter[]` | Query parameters. |
| `method` | `HttpRequestMethod` | |
| `paging?` | `HttpPagingSettings` | For paged target APIs. |
| `chainingSettings?` | `HttpRequestChainParent` | Parent request whose response drives iteration. |
| `response?` | `HttpRequestResponsePayload` | Captured exemplar response — drives UI JSONPath/XPath pickers. |

**`HttpRequestForm`** — `{requestChains: HttpRequest[], request: HttpRequest}`. The form GET returns the candidate parents for chaining.

### Objects

**`ObjectDefinition`**:

| Field | Type | Notes |
|---|---|---|
| `id?` | uuid | |
| `isListObject` | boolean | True = produces N objects from a list response; false = singleton. |
| `metricSets` | `MetricSet[]` | Metric definitions per instance. |
| `type` | `ObjectType` | Type the design itself is creating. |
| `internalObjectInfo?` | `ObjectInfo` | When design-local type. |
| `existingObjectTypeDetails?` | `ExistingObjectTypeDetails` | When reusing a foreign-adapter type. Fields: `adapterType`, `objectType`, `adapterTypeLabel`, `objectTypeLabel`, `metricSet`. |

**`ObjectForm`** — `{requests: HttpRequest[], object: ObjectDefinition}`.

### Relationships

**`RelationshipPayload`** (write):

| Field | Type |
|---|---|
| `existingObjectTypeReferences` | `ExistingObjectTypeReference[]` — foreign object types pulled in for the relationship |
| `relationship` | `Relationship` |

**`RelationshipForm`** — `{objects: ObjectDefinition[], relationship: Relationship}`.

### Events

**`HttpEventPayload`** — `{existingObjectTypeReferences: ExistingObjectTypeReference[], event: HttpEvent}`.

**`EventForm`** — `{requests: HttpRequest[], objects: ObjectDefinition[], event: HttpEvent}`.

**Wire-format note**: in the export envelope, each item in `events[]`
must be wrapped `{"event": {...}}` — see "Events wire format —
RESOLVED 2026-04-18" above.

### Jobs

**`JobPayload`**:

| Field | Type | Notes |
|---|---|---|
| `jobType` | string | `COLLECTION_PREVIEW` \| `REQUEST` \| `TEST_SOURCE` |
| `additionalTrustedCertificates?` | string[] | PEM blobs trusted for TLS *for this job only*. |
| `type` (`TEST_SOURCE` only) | `"HTTP"` | |
| `testType` (`TEST_SOURCE` only) | `"GET_SESSION"` \| `"TEST_CONNECTION"` | Two-step source test; TEST_CONNECTION needs GET_SESSION result embedded in `source.sessionSettings.getSession.response`. |
| `source` (`TEST_SOURCE` only) | `HttpSource` | Full source block. |

**`AbstractJobResponse`** — `{id, startTime, endTime?, duration?, errorMessage?, type?, status}`. Type is `COLLECTION_PREVIEW | DEPLOYMENT_STATUS | HTTP_REQUEST_RESPONSE`.

**`LastSubmittedCollectionPreviewJob`** — `{jobId?: uuid}` returned by `GET /jobs/collectionpreview/latest`.

### Existing object types (picker backend)

**`ExistingObjectType`** — list entry.
**`ExistingObjectTypeDetails`** — `{objectType, objectTypeLabel, adapterType, adapterTypeLabel, metricSet}`.
**`ExistingObjectTypeReference`** — short pointer `{adapterKindKey, resourceKindKey}` used inside payloads.

Diagnostic use: `GET /existingobjecttypes/details?adapterKindKey=VMWARE&resourceKindKey=Datastore` answers "what does MPB think this object type looks like, right now, on this instance?" — useful for prod-vs-devel comparisons when a picker behaves oddly.

### Utilities

**`RegexTest`** — `{regex, sample}`. **`RegexResult`** — `{valid, output, error, duration}`.

### Import/export

**`HttpDesignContent`** — bundle accepted by `POST /designs/import`. HTTP-flavoured projection of the generic `DesignContent` envelope:

| Field | Type |
|---|---|
| `design` | `Design` |
| `source` | `HttpSource` |
| `requests` | `{request: HttpRequest}[]` (wrapped) |
| `objects` | `{object: ObjectDefinition}[]` (wrapped) |
| `relationships` | `{relationship: Relationship}[]` (wrapped) |
| `events` | `{event: HttpEvent}[]` (wrapped — see field-level diff section) |
| `configuration` | as in `HttpSource.configuration` |

`GET /designs/export` returns the same shape — opaque round-trip
JSON. Treat the export output as canonical; never hand-edit beyond
the renames documented in the test-design probes.

## Operational notes and caveats (clean-room merge)

1. **Internal namespace.** Everything is under `/suite-api/internal/…`. Per VMware's conventions and observed behaviour this surface is not part of the supported public Suite API contract. Plan for breakage between Operations major releases; pin to a known build.
2. **Authentication.** Bearer token from `POST /suite-api/api/auth/token/acquire` + `X-Ops-API-use-unsupported: true` works for the full namespace (empirically verified). UI session cookies also work (CSRF + `JSESSIONID` from the Operations UI login). The clean-room reference's note that bearer 403s was probing without the unsupported header.
3. **Bulk-delete semantics.** All bulk DELETEs (`designs`, `requests`, `objects`, `relationships`, `events`) take `id` as a **repeatable** query parameter — `?id=A&id=B&id=C`, not `?id=A,B,C`.
4. **Async vs sync jobs.** `POST /jobs` can return 201 with an immediate `AbstractJobResponse` or 202 with a `CollectionPreviewResponse`. Callers must handle both shapes and poll `.../jobs/collectionpreview/latest` plus `getDesign` / `getDesignStatus` for completion. `verifyDesign` has the same 200/202 pattern.
5. **Export gate.** `getExportedDesign` requires `userWillVerifySensitiveInfo=true` as an affirmation that the caller has scrubbed secrets. Server does NOT scrub on the caller's behalf.
6. **`name` is immutable in practice.** `DesignInfo.name` becomes the AdapterKind of the deployed adapter. Renaming a design after install is allowed by the API but does NOT rename the already-installed adapter — the next install would create a second adapter kind.
7. **Existing-object-type references** pull foreign adapter object types into a design (so relationships and events can bind to them). They are not copies — uninstalling the foreign adapter breaks the design.
8. **`DesignInfo.version`** flows directly to the deployed adapter and participates in the `OUT_OF_DATE` install status. Bump it on every reinstall.

## References

- CLAUDE.md §7 (`X-Ops-API-use-unsupported`)
- `tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json`
  — working export envelope reference
- `tmp/vcf_operations_mp_designs_export.zip` — MPB UI Export output (byte-for-byte identical to above)
- Memory `project_vcf_operations_url_structure.md` — URL structure
  for VCF Ops 9.0.2 (MPB UI is behind `/vcf-operations/*` SSO)
- On-appliance OpenAPI: `/usr/lib/vmware-vcops/tomcat-enterprise/webapps/suite-api/docs/openapi/v3/dev-api.json` on a VCF Ops 9.0.0.0 (build 24723247) appliance — source for the clean-room merge's endpoint catalog and schemas.

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

### CONFIRMED 2026-04-29: `/jobs` IS bearer-reachable at `/suite-api/`

`POST /suite-api/internal/mpbuilder/designs/{id}/jobs` accepts
the same body shape as the UI-path equivalent and dispatches
the source-test runner. Verified on devel against the existing
Synology design `a6b6877f-bfad-43af-84e7-aa56f209b8d9`:

- `jobType: TEST_SOURCE`, `testType: GET_SESSION` — runs auth
  step, returns 200 with session response embedded under
  `actionResult` (base64-encoded).
- `jobType: TEST_SOURCE`, `testType: TEST_CONNECTION` — runs
  the source's `testRequest` after the GET_SESSION response
  is carried forward in
  `body.source.sessionSettings.getSession.response`. Returns
  200 with the test-request response, including
  `dataModelLists` of attributes inferred from the response
  body.

**Action polling**: `GET /suite-api/api/actions/{actionId}/status?detail=true`
returns task state plus base64-encoded `actionResult` payload.
This is the SAME action-status endpoint the legacy resource-
action subsystem uses. Decoding `actionResult` yields a JSON
envelope with `responseCode`, `errorMessage`, `body`,
`headers`, `dataModelLists`.

**Install deployment polling** has its own path:
`GET /suite-api/internal/mpbuilder/designs/{designId}/install/{deploymentId}`.
The deployment id from `POST /install`'s response body works
as the path-tail. Returns final state + `errorMessage`.

**Source-test prerequisites** (failure modes captured):

- `configuration.collectorId` MUST be a valid collector UUID.
  Null returns 400 `"No collector found with UUID null"`. Pull
  via `GET /api/collectors` and inject before calling.
- `authentication.credentials[].value` MUST be the actual
  cleartext password for sensitive creds. The importer strips
  these via `_strip_cred()` on import; the server holds them
  internally for the design only after a UI password entry.
  Re-imported probe designs cannot pass source-test without
  manual UI credential re-entry.

**Phase 3 full-auto status**: source-test IS now scriptable
under bearer auth — but the per-resource builder-file parser
that produces verbose validation errors still has no located
trigger endpoint. Designs with valid source-test responses
still land INVALID if they have per-resource objectBinding
issues (see `mpb_object_binding_wire_format.md` §8). Best
guess: that parser runs as part of the UI Verify wizard's
final step, not as an isolatable REST call.

### `PUT /designs/{id}/objects/{objId}` is broken (2026-04-29)

Per-object PUT returns 500 ISE on both wrapped (`{"object":{...}}`)
and unwrapped body shapes against a known-good full-fidelity
GET payload. `PUT /designs/{id}` accepts only summary-shape
bodies (name/description/version), not the full export envelope
the UI uses for design editing. Conclusion: the only way to
modify a design's objects via REST is to re-import — and
re-import strips sensitive credentials, breaking source-test
for the new design. This is the primary blocker for headless
verify-time probing.

### Session variable key rules — revisit
Validator on import path (`POST /designs/import`) rejects sessionVariable keys containing hyphens (e.g. `Set-Cookie`) — see earlier notes. **Runtime path `/jobs` accepts `Set-Cookie` with hyphen** per Scott's capture. Different code paths, different validators. Worth factoring into `render_export.py` decision: do we emit `Set-Cookie` (works at runtime, rejected by import validator) or `set_cookie` (accepted at import, unclear at runtime)? Needs concrete test before deciding.
