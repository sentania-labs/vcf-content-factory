# Server-side view render — `GET /internal/views/{id}/data/export`

**Question that produced this file (2026-07-10):** how do you render a
VCF Ops list-view *server-side* against a specific object, to see the
actual cell values a view produces — without a browser and without the
Ext.Direct `viewServiceController.getView` RPC (which returned only
`{"type":"exception","message":"Internal server error."}` for every
payload shape tried).

## Headline: there IS a REST render endpoint (internal spec)

`reference/docs/internal-api.json` exposes:

```
GET /suite-api/internal/views/{id}/data/export
    ?resourceId=<object-uuid>          (required; array, only first item used)
    &traversalSpec=<name>              (optional)
    &page=0 &pageSize=1000             (optional)
Header: X-Ops-API-use-unsupported: true
Auth:   vRealizeOpsToken (normal Suite API bearer — NOT a UI session)
```

- `id` is the **view definition UUID** (the same UUID
  `content-installer`/validate resolve view cross-refs to).
- `resourceId` is the object the view is executed against. Despite the
  `array` type in the spec, **only the first element is honored.**
- Returns HTTP 200 with `Content-Type: application/json`; the body is a
  JSON **string-shaped** object (spec calls it a serialized string, but
  on 9.0.2 it deserializes directly) of the form:

```json
{"viewsData":[{
  "name": "...", "description": "...", "type": "list-view",
  "startTime": <ms>, "endTime": <ms>,
  "columns": [{"key":"objId","label":"Name","unit":null},
              {"key":"1","label":"Instance",...}, ...],
  "rows": [{"cells": {"objId":"...", "1":"...", "2":"...", "5":123.0,
                      "objUUID":"<uuid>", "summary":false, ...}}]
}]}
```

- Column `key`s are `objId`, then `"1"`,`"2"`,… per data column in
  definition order, plus synthetic `summary`, `grandTotal`, `groupUUID`,
  `objUUID`. Each `cells` dict is keyed by those same column keys.
- This is the **Suite API bearer** path — reuse
  `vcfops_common.client.VCFOpsClient` directly; no `/ui/` session, no
  CSRF, no OPS_SESSION dance. Much cheaper than the UI route in
  `dashboard_delete_api.md`.

**Warning (RULE / unsupported):** `/internal/*` endpoints require the
`X-Ops-API-use-unsupported: true` header and carry **no backwards-
compatibility guarantee** — they can change or vanish between VCF Ops
releases. Tracked working on devel (VCF Operations, 9.x lab) 2026-07-10.

## Why the Ext.Direct `getView` RPC kept 500-ing

Not re-solved — made moot. The internal REST endpoint renders the same
data without touching `viewServiceController.getView`. If a future task
still needs the RPC (e.g. to capture control state the REST path omits),
the 500 is a deserialization failure on the `resourceRef`/`controls`
bean shape; the REST endpoint is the recommended path instead.

## Worked result — instanced-group column EXPANDS (settles the parity question)

Rendered the rewritten **"ESXi Host License Information vCommunity"**
view (`810958f4-e511-4e44-afaa-c04956768daf`) against three VMWARE
HostSystem objects on devel. The view's instanced-group columns bake
`sample_instance: "Evaluation Mode"` into their member attributeKeys,
but devel hosts carry exactly one license instance named **"VMware
Cloud Foundation (cores)"** — not the baked-in name.

Every host rendered a row for the *actual* license instance:

| objId (host) | col "1" Instance | col "2" Edition | col "5" Days |
|---|---|---|---|
| esx01 | VMware Cloud Foundation (cores) | esx.vcf.entitlement.cpuCoreMin | null |
| esx02 | VMware Cloud Foundation (cores) | esx.vcf.entitlement.cpuCoreMin | null |
| mgmt-esx03 | VMware Cloud Foundation (cores) | esx.vcf.entitlement.cpuCoreMin | 136.0 |

**Verdict: EXPANDS.** The `sample_instance` value in the member
attributeKeys is **design-time only** — it seeds the column definition
but does NOT constrain which instances render. The instanced-group
column expands to whatever license instance(s) exist on the object at
render time, regardless of the baked-in sample name. (LITERAL would have
shown empty rows or an Evaluation-Mode-only row; it did not.)

Consequence for the vcommunity-vsphere parity closeout: the licensing
**view/report leg proceeds as-is** — no need to rethink the instanced
column keys. (Days-to-Expire is null where the 8.x/perpetual-style key
carries no expiry and populated where the 9.x subscription key does —
consistent with the collector's design of emitting no Remaining Days on
null expiration; see the closeout design note.)

## Reuse recipe

```python
import sys; sys.path.insert(0, "src")
from vcfops_common.client import VCFOpsClient
c = VCFOpsClient.from_env(profile="devel", default_profile="devel")
c.authenticate()
r = c._request("GET", f"/internal/views/{VIEW_UUID}/data/export",
               params={"resourceId": OBJECT_UUID},
               headers={"X-Ops-API-use-unsupported": "true"})
data = r.json()["viewsData"][0]        # columns + rows
```

Find a target object with e.g.
`GET /api/resources?resourceKind=HostSystem&adapterKind=VMWARE`.

## Cross-reference

- `knowledge/context/api-surface/dashboard_delete_api.md` — the UI-session
  route (needed for delete; NOT needed for render).
- `knowledge/context/wire-formats/view_column_wire_format.md` — how view
  columns/attributeKeys are authored and rendered into the definition.
