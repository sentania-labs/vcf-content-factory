# VCF Ops content-management API surface

A map of what exists on the public API (`docs/operations-api.json`),
the internal API (`docs/internal-api.json`), and the content
import/export zip mechanism.

## Two specs ship with Ops

- `docs/operations-api.json` — the supported public contract.
- `docs/internal-api.json` — `/internal/...` endpoints, require the
  `X-Ops-API-use-unsupported: true` header. Broadcom reserves the
  right to change these without notice.

**When answering "does the API support X?", grep BOTH specs.** Only
looking at the public one misses real endpoints, including
`PUT /internal/supermetrics/assign`, which is the one thing that can
enable a super metric in a policy in a single call.

## Surface map

| Content type | Public CRUD | Bulk import/export | Enable/assign |
|---|---|---|---|
| Super metrics | `/api/supermetrics` — **rejects caller-supplied id** | `/api/content/operations/{export,import}` with `SUPER_METRICS` — **preserves UUIDs** | `PUT /internal/supermetrics/assign` (internal) |
| Alert definitions | `/api/alertdefinitions` full CRUD | content-zip | `PUT /api/alertdefinitions/{id}/{enable,disable}` **(public)** |
| Symptom definitions | `/api/symptomdefinitions` full CRUD | content-zip | realtime toggle via `/internal/symptomdefinitions/{id}/realtimemonitoring/{enable,disable}` |
| Recommendations | `/api/recommendations` full CRUD | content-zip | linked via alert definitions |
| Notification rules & templates | `/api/notifications/{rules,templates}` full CRUD | content-zip (`NOTIFICATION_RULES`) | — |
| Dashboards | **no CRUD** | content-zip (`DASHBOARDS`) — **only path** | — |
| Views | **no CRUD** | content-zip (`VIEW_DEFINITIONS`) — **only path** | — |
| Report definitions | read-only | content-zip (`REPORT_DEFINITIONS`) — **only create path** | — |
| Policies | `/api/policies` full CRUD | `/api/policies/{export,import}` (separate from content ops) | `/assign` is for objects/groups, not for enabling content inside the policy |
| Actions | read-only (`/api/actiondefinitions`) | — | not authorable — action types are baked in |

## The unifying mechanism: `/api/content/operations/import`

All content that needs UUID stability across instances goes through
this path. The importer preserves UUIDs from the input zip. It is
exactly the mechanism `vcfops_dashboards` already uses. This is why
every new content type added to this repo should target the content
zip path first, not per-object CRUD.

## Undocumented fields are real

The OpenAPI spec for `POST /api/supermetrics` does not list
`resourceKinds`, but the field is accepted and persisted — verified
against an exported super metric. Treat the OpenAPI schema as a
floor, not a ceiling: exports sometimes reveal fields the docs omit.

## Highest-leverage unexplored extension

**Alert definitions + symptoms + recommendations + notification
rules**. Unlike super metrics, alert definitions have a supported
public enable/disable endpoint. The whole chain can be authored in
YAML and installed end-to-end on the supported public surface. No
internal-API hacks required.

## Custom groups (dynamic)

Public REST, **not** content-zip:

- `GET/POST/PUT /suite-api/api/resources/groups`
- `GET/DELETE   /suite-api/api/resources/groups/{id}`
- `GET          /suite-api/api/resources/groups/{id}/members`
- `GET/POST     /suite-api/api/resources/groups/types`

Internal extras (require `X-Ops-API-use-unsupported: true`,
unsupported):

- `POST /suite-api/internal/resources/groups/static`
- `PUT/POST /suite-api/internal/resources/groups/{id}/includedResources`
- `PUT/POST /suite-api/internal/resources/groups/{id}/excludedResources`
- `GET/POST/DELETE /suite-api/internal/resources/grouptype[/{name}]`

Custom groups do not ride `/api/content/operations/import`; there
is no `customgroups.json` in any content-export zip. Sync identity
is `resourceKey.name`, not UUID — the server assigns `id` on create.
Wire format and full round-trip notes: `context/wire_formats.md`
§"Custom groups (dynamic)". Authoring guidance:
`context/customgroup_authoring.md`.
