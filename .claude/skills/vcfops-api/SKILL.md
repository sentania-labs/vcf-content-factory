---
name: vcfops-api
description: >
  How to authenticate and interact with the VCF Operations Suite API.
  Covers the public REST surface, the internal /internal/* endpoints,
  the content-zip import/export mechanism, authentication via env vars,
  token lifecycle, and common failure modes (import-task-busy, ghost
  state, marker files). Use this skill whenever working with VCF Ops
  API calls, building API clients, debugging import/export failures,
  or planning which endpoint to use for a content management task.
  Also use when asked about VCF Operations, Aria Operations, or vRealize
  Operations API capabilities.
---

# VCF Operations Suite API

## Authentication

Credentials flow via environment variables — never hardcoded, never
on disk:

```
VCFOPS_HOST           hostname (no scheme, e.g. ops.lab.local)
VCFOPS_USER           username
VCFOPS_PASSWORD       password
VCFOPS_AUTH_SOURCE    optional, default "Local"
VCFOPS_VERIFY_SSL     optional, "false" to disable TLS verification
```

Token acquisition: `POST /api/auth/token/acquire` with JSON body
`{"username": "...", "password": "...", "authSource": "..."}`.
Returns `{"token": "...", "validity": N, "expiresAt": "..."}`.
Use `Authorization: OpsToken <token>` on subsequent requests.

## Two API specs

VCF Ops ships two OpenAPI specs:

- **Public** (`operations-api.json`) — the supported contract.
- **Internal** (`internal-api.json`) — `/internal/*` endpoints.
  Require the `X-Ops-API-use-unsupported: true` header. Broadcom
  may change these without notice.

**Always grep BOTH specs** when answering "does the API support X?"
The internal spec contains endpoints the public one omits, including
the super metric enable path.

## Content-zip import/export

The unifying mechanism for content that needs UUID stability across
instances. For detailed zip layouts, read
`references/wire-formats.md`.

### Import flow

```
POST /api/content/operations/import
  Content-Type: multipart/form-data
  Field: contentFile (the zip)
  Returns: 202 + operation ID
```

Poll `GET /api/content/operations/import` until
`state == FINISHED`. Check `errorCode` and `errorMessages`.

### Import gotchas

1. **Marker file**: Every export includes a `<19-digit>L.v1` file
   unique to the instance. The importer rejects any other value.
   Discover it via a throwaway export.
2. **Marker contents**: The owner user UUID.
3. **Field name is `contentFile`**, not `file`. Wrong name → 500.
4. **One import at a time**: 403 "Task is already running" if an
   import is in progress. Retry with 30-second intervals, max 3.
5. **Imported nothing**: after import, `imported=0, skipped>0` in
   `operationSummaries` means the import finished without changing
   anything. Never report that as a successful install. For
   **SUPER_METRICS** this is the bisected "ghost state" signature
   (content readable by ID but invisible to list/assign) and the
   verified fix is re-importing the same zip, which the SM paths do
   automatically. That cause and that remedy are evidence **only for
   super metrics**: do not assume they generalize. Read
   `references/wire-formats.md` §"SM ghost state" for full details.

   For **dashboards and views** one cause was bisected 2026-08-21
   (issue #97) and it is not ghost state: the importer's create-only
   mode, produced by `force=false` on the import query string. There
   the pre-existing content survives (listed, readable, structurally
   intact, assignable — API-level probes only, no browser pass); only
   the new revision fails to land. The skip is **idempotent**, so
   re-importing is a guaranteed no-op and the SM remedy does not
   transfer. The factory warns and does not retry, and that is
   correct.

   **Do not read that as the meaning of the signature.** Every factory
   call site sends `force=true`, so a skip seen through factory code
   is unexplained by the bisected cause. UI-locked dashboards,
   non-admin import of another user's content, and pak-supplied
   solution content were never tested. Treat a `force=true` skip as a
   new finding. Full evidence:
   `knowledge/context/api-surface/content_import_skip_semantics.md`.
6. **`force` semantics are counter-intuitive**: `force=true`
   overwrites, `force` **omitted** also overwrites, only an explicit
   `force=false` skips existing content. All factory call sites
   hard-code `force=true`.
7. **`imported=N` means "written", not "changed".** There is no
   content comparison; an unchanged re-import still reports
   `imported=N`.
8. **Dashboard import identity is the NAME, not the UUID.** Importing
   a same-named dashboard under a new UUID replaces the existing one
   and silently orphans the old UUID, reporting `imported=1` with
   nothing in the envelope saying so. Changing `id:` in a dashboard
   YAML while keeping the name breaks every deep link and summary-tab
   association pinned to the old UUID. Views behave differently: they
   duplicate with a numeric suffix.

## API surface map

For the complete endpoint inventory by content type (CRUD, bulk,
enable/assign), read `references/api-surface-map.md`.

Quick reference for the most common operations:

| Operation | Endpoint | Notes |
|---|---|---|
| List super metrics | `GET /api/supermetrics` | Paginated |
| Import content | `POST /api/content/operations/import` | Multipart zip |
| Export content | `POST /api/content/operations/export` | Async, poll for zip |
| Enable SM (Default Policy) | `PUT /internal/supermetrics/assign/default` | Internal, unsupported |
| List custom groups | `GET /api/resources/groups` | Filter by `adapterKindKey=Container` |
| List symptoms | `GET /api/symptomdefinitions` | Hundreds of built-ins |
| List alerts | `GET /api/alertdefinitions` | Hundreds of built-ins |
| List stat keys | `GET /api/adapterkinds/{ak}/resourcekinds/{rk}/statkeys` | Authoritative metric vocabulary |
| Check live data | `GET /api/resources/{id}/stats/latest` | Proves metric is collecting |

## Python client pattern

Projects in this ecosystem use a shared client pattern:

```python
from vcfops_supermetrics.client import VCFOpsClient
c = VCFOpsClient.from_env()           # loads .env automatically
r = c._request('GET', '/api/supermetrics')
```

`from_env()` reads the env vars above. `_request()` handles token
refresh and SSL verification. For endpoints not covered by
convenience methods, use `c._request('GET', '<path>', params={...})`.

## Reference files

- `references/api-surface-map.md` — Full endpoint inventory by
  content type, including which support CRUD vs bulk import only.
- `references/wire-formats.md` — Exact zip layouts for super
  metrics, dashboards, views, policies. Import/export gotchas.
  Ghost state detection and recovery.
