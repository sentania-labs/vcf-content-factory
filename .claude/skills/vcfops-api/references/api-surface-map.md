# VCF Ops content-management API surface

## Surface map

| Content type | Public CRUD | Bulk import/export | Enable/assign |
|---|---|---|---|
| Super metrics | `/api/supermetrics` — **rejects caller-supplied id** | `/api/content/operations/{export,import}` with `SUPER_METRICS` — **preserves UUIDs** | `PUT /internal/supermetrics/assign/default` (internal) |
| Alert definitions | `/api/alertdefinitions` full CRUD | content-zip | `PUT /api/alertdefinitions/{id}/{enable,disable}` **(public)** |
| Symptom definitions | `/api/symptomdefinitions` full CRUD | content-zip | realtime toggle via `/internal/symptomdefinitions/{id}/realtimemonitoring/{enable,disable}` |
| Recommendations | `/api/recommendations` full CRUD | content-zip | linked via alert definitions |
| Notification rules & templates | `/api/notifications/{rules,templates}` full CRUD | content-zip (`NOTIFICATION_RULES`) | — |
| Dashboards | **no REST CRUD** — delete via UI Struts action | content-zip (`DASHBOARDS`) — **only create/update path** | — |
| Views | **no REST CRUD** — delete via Ext.Direct RPC | content-zip (`VIEW_DEFINITIONS`) — **only create/update path** | — |
| Report definitions | read-only | content-zip (`REPORT_DEFINITIONS`) — **only create path** | — |
| Policies | `/api/policies` full CRUD | `/api/policies/{export,import}` (separate from content ops) | — |
| Actions | read-only (`/api/actiondefinitions`) | — | not authorable |

## Custom groups (REST, not content-zip)

```
GET/POST/PUT  /api/resources/groups
GET/DELETE    /api/resources/groups/{id}
GET           /api/resources/groups/{id}/members
GET/POST      /api/resources/groups/types
```

Custom groups do NOT ride `/api/content/operations/import`. Sync
identity is `resourceKey.name`, not UUID — server assigns `id`.

Internal extras (unsupported):
```
POST    /internal/resources/groups/static
PUT/POST /internal/resources/groups/{id}/{included,excluded}Resources
GET/POST/DELETE /internal/resources/grouptype[/{name}]
```

## Dashboard + view delete (UI action endpoints)

No REST DELETE. Delete only via Struts/Ext.Direct UI layer.
Requires JSESSIONID + CSRF token from `OPS_SESSION` cookie
(not the Suite API bearer token).

## Super metric enable endpoint

**Use `PUT /internal/supermetrics/assign/default`**, NOT
`PUT /internal/supermetrics/assign?policyIds=<id>`.

The `/default` variant targets the Default Policy directly. The
`?policyIds=` variant silently fails for non-default policies and
can return 200 without actual enablement.

Both require `X-Ops-API-use-unsupported: true`.

Request body:
```json
{
  "superMetricId": "<uuid>",
  "resourceKindKeys": [
    { "adapterKind": "VMWARE", "resourceKind": "VirtualMachine" }
  ]
}
```

Note: body uses `adapterKind`/`resourceKind` (not the `*Key` suffix
form the loader stores).

## Undocumented fields are real

The OpenAPI spec for `POST /api/supermetrics` does not list
`resourceKinds`, but the field is accepted and persisted. Treat the
spec as a floor, not a ceiling.
