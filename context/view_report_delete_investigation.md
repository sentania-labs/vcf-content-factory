# View and Report delete investigation (VCF Ops 9.0.2)

> **SEE `context/dashboard_delete_api.md` §"2026-04-11 update" for the
> correction to this investigation.** The "server-side handler crash" conclusion
> below is WRONG. The real issue was the data shape sent by our client:
> `deleteView` requires `"data": [{"viewDefIds": "[{\"id\":\"...\",\"name\":\"...\"}]"}]`,
> not a bare UUID. With the correct shape both view and report delete work on
> the legacy `/ui/vcops/services/router` URL. All 4 stranded items from this
> investigation have since been deleted via the corrected client.

Empirical investigation 2026-04-11 against `vcf-lab-operations.int.sentania.net`
(VCF Operations 9.0.2.0 build 25137838) to answer: does the SPA UI call a
different delete endpoint that actually works, or is the server-side bug
unavoidable?

**Short answer: unavoidable.** On this 9.0.2 build, view delete and
report delete are completely broken at the server level. Every candidate
REST path either returns HTTP 404 (no route) or HTTP 500 (route exists,
handler crashes). The bug is **not** specific to content-zip-imported
items, and **not** specific to duplicate-subjects. Even attempting to
delete a *nonexistent* UUID via the live delete routes returns HTTP 500,
proving the route handlers crash before reaching any persistence logic.
The 4 stranded test items from the previous investigation could not be
deleted. **Manual web-console cleanup is the only workaround**, and even
that is unreliable because the Ext.Direct methods the SPA relies on are
themselves broken (500 on every call, including listing).

## Background

Previous api-explorer work (see `context/ui_import_formats.md`,
`context/dashboard_delete_api.md`, and memory
`project_view_delete_server_bug.md`) documented that view delete returns
HTTP 500 for content-zip-imported views, hypothesized that the root cause
was a duplicate `subjects` entry in the server's backing store, and
recommended manual cleanup via the web console. That hypothesis is now
falsified: fresh probing shows the delete handlers fail for any input,
and even healing the duplicate subjects does not make delete succeed.

The 4 items the previous investigation left stranded on the lab were:

| Type | UUID | Name |
|---|---|---|
| View | `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a` | ESXi Host Active Alerts |
| View | `36ff8c15-e47d-4285-b0f3-3ce9dda00ae6` | VM Snapshot Details List |
| Report | `02fb7e8e-e14e-4cdb-853f-367ce097bc47` | ESXi Host Active Alerts |
| Report | `f524e76b-67aa-4092-a49b-6c742e45ad4f` | VM Snapshot Details Report |

All 4 still exist at the end of this investigation.

## Method

Auth flows used (both verified working as `admin`):

- **Suite API token** — `POST /suite-api/api/auth/token/acquire` →
  `Authorization: OpsToken <token>`. Required for `/suite-api/api/*`
  and `/suite-api/internal/*` REST calls.
- **UI session** — 3-step flow from `context/dashboard_delete_api.md`
  (get `JSESSIONID`, `POST /ui/login.action`, `GET /ui/index.action`
  → capture `OPS_SESSION` without following the 302, decode base64 →
  `csrfToken`). Required for `/ui/*.action` and
  `/ui/vcops/services/router` (Ext.Direct RPC).

Investigation ran as `admin` (not `claude`), so permission is not a
variable. The SPA UI itself is unreachable on this instance (`/vcf-
operations/ui/` → 404), so browser-level observation wasn't possible;
instead every plausible REST and Ext.Direct surface was probed directly.

## Finding 1 — View delete REST endpoint survey

Target: `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a`.

| Method | Path | Result |
|---|---|---|
| DELETE | `/suite-api/api/views/{id}` | 404 (no route) |
| DELETE | `/suite-api/api/viewdefinitions/{id}` | 404 (no route) |
| DELETE | `/suite-api/api/view-definitions/{id}` | 404 (no route) |
| DELETE | `/suite-api/internal/viewdefinitions/{id}` | **500 Internal Server error** (with `X-vRealizeOps-API-use-unsupported: true`) |
| DELETE | `/suite-api/internal/view-definitions/{id}` | 404 |
| DELETE | `/suite-api/internal/views/{id}` | 404 |
| POST | `/suite-api/api/views/delete` | 404 |
| POST | `/suite-api/api/viewdefinitions/delete` | 404 |
| POST | `/suite-api/internal/viewdefinitions/delete` | **500 Internal Server error** |
| POST | `/suite-api/api/content/operations/delete` | 404 |
| POST | `/suite-api/internal/content/operations/delete` | 404 |
| DELETE | `/suite-api/api/viewdefinitions?id=…` | 404 |
| DELETE | `/suite-api/internal/viewdefinitions?id=…` | 500 |

**Only `/suite-api/internal/viewdefinitions/{id}` (DELETE and POST-to-
`/delete`) has a live route. It returns HTTP 500 on every call,
including for nonexistent UUIDs** (confirmed by sending the nil UUID
`00000000-0000-0000-0000-000000000000`). That rules out "duplicate
subjects crash the delete handler" — the handler crashes before it
even loads the target. The bug is in the route implementation itself.

Unsupported-header variants tested (all still 500):
`X-vRealizeOps-API-use-unsupported`, `X-Ops-API-use-unsupported`,
`X-vrealizeOps-API-use-unsupported` (lowercase v), both together.
`X-use-unsupported-api` returns 403 Forbidden, which means it's not
the right header name. Query flags tested on the live DELETE route
(`force=true`, `cascade=true`, `ignoreConstraints=true`,
`ignoreErrors=true`): all still 500.

### Ext.Direct view delete — what the SPA actually uses

```json
POST /ui/vcops/services/router
secureToken: <csrfToken>

[{"action":"viewServiceController","method":"deleteView",
  "data":["<view-uuid>"],"type":"rpc","tid":1}]
```

Result, as admin, for all 3 target UUIDs (2 stranded + 1 nonexistent):

```json
[{"type":"exception","message":"Internal server error.",
  "tid":1,"action":"viewServiceController","method":"deleteView"}]
```

Also broken: `viewServiceController.saveOrUpdateViewDefinition`
(returns the same exception when passed the thumbnail shape),
`viewServiceController.getViewDataById` (same). Live and working on
the same controller: `getGroupedViewDefinitionThumbnails` (list all
views), `getViewDefinitionThumbnails` (list subset by UUID list).
Reading the view still works, but **every mutating method on
`viewServiceController` is broken** on this build.

The Ext.Direct delete path and the internal REST delete path appear to
call the same underlying server implementation, because both produce
identical "Internal Server error" messages and both repro the crash
for nonexistent UUIDs.

## Finding 2 — Report delete REST endpoint survey

Target: `02fb7e8e-e14e-4cdb-853f-367ce097bc47`.

| Method | Path | Result |
|---|---|---|
| DELETE | `/suite-api/api/reportdefinitions/{id}` | **500** |
| DELETE | `/suite-api/api/report-definitions/{id}` | 404 |
| DELETE | `/suite-api/api/reports/definitions/{id}` | 404 |
| DELETE | `/suite-api/internal/reportdefinitions/{id}` | 404 (route does not exist on internal surface) |
| DELETE | `/suite-api/internal/report-definitions/{id}` | 404 |
| POST | `/suite-api/api/reportdefinitions/delete` | **500** |
| POST | `/suite-api/internal/reportdefinitions/delete` | 404 |
| POST | `/suite-api/api/content/operations/delete` | 404 |
| POST | `/suite-api/internal/content/operations/delete` | 404 |
| DELETE | `/suite-api/api/reportdefinitions?id=…` | **500** |
| DELETE | `/suite-api/internal/reportdefinitions?id=…` | 404 |

Unlike view delete, report delete is on the **public** surface
(`/api/reportdefinitions/{id}`), not `/internal/`. Also unlike view
delete, there's no documented report delete in either OpenAPI spec:
grep of `docs/operations-api.json` lists only `GET`/`DELETE` for
`/api/reportdefinitions/{id}/schedules/{scheduleId}` (schedules, not
definitions), and `GET`/`DELETE` for `/api/reports/{id}` (generated
report instances, not definitions). Report *definition* delete is an
undocumented legacy route that exists at runtime but is broken.

Same smoking gun as views: `DELETE /api/reportdefinitions/{nil-uuid}`
returns **500** (not 404), proving the handler crashes before even
looking up the target. The previous investigation's assertion that
"report delete API is broken in 9.0.2" is confirmed, and moreover the
breakage is fundamental, not per-item.

### Ext.Direct report delete — what the SPA would use

```json
[{"action":"reportServiceController","method":"deleteReportDefinitions",
  "data":[["<report-uuid>"]],"type":"rpc","tid":1}]
```

Result: `[{"type":"exception","message":"Internal server error."...}]`
for every invocation. Scalar `data` (single UUID instead of list) —
same 500.

**The entire `reportServiceController` is unusable** on this build.
Even `getReportDefinitionThumbnails` (list reports — what the SPA's
Manage > Reports page would call to populate its list) returns
`Internal server error` for every parameter shape tested
(`[{}]`, `[""]`, `[None]`, `[{"type":"ALL"}]`, `[{"filter":""}]`).
This means an admin loading the Manage > Reports page in the web
console would see an empty list or an error — so even the "manual
cleanup via web console" workaround is likely unreliable for reports
on this build. Report definitions *do* still return valid data via
the public REST `GET /api/reportdefinitions` (91 reports listed,
including all 4 stranded and `[VCF Content Factory]` items), so the
data layer is fine; only the Ext.Direct service layer is broken.

## Finding 3 — Duplicate-subjects hypothesis falsified

The previous investigation hypothesized that the view delete 500 was
caused by duplicate `subjects` entries produced by the content-zip
importer. Direct read of `/suite-api/internal/viewdefinitions/{id}`
confirmed the duplication:

```json
{"name":"ESXi Host Active Alerts","subjects":["alert","alert"],...}
{"name":"VM Snapshot Details List","subjects":["VirtualMachine","VirtualMachine"],...}
```

And the exported XML (via `POST /api/content/operations/export` with
`{"scope":"CUSTOM","contentTypes":["VIEW_DEFINITIONS"]}`) confirmed
the wire cause: both ViewDef blocks contain **two** `<SubjectType>`
elements, one `type="descendant"` and one `type="self"`, which is
what the documented wire format mandates. The importer stores both.

**I attempted to heal this**: re-imported both stranded views via
`POST /api/content/operations/import?force=true` with a content.xml
containing **only one** `<SubjectType type="descendant"/>` per
ViewDef (the `type="self"` element removed). The import finished with
`errorCode=NONE`, and re-reading the internal viewdefinitions showed:

```json
{"subjects":["alert"], "owner":"admin"}       # was ["alert","alert"]
{"subjects":["VirtualMachine"], "owner":"admin"}
```

The subjects field was successfully deduped in the server's store.
**Delete still fails with 500** on both the Ext.Direct path and the
internal REST path. The dedup did not change the failure mode.

Interesting side effect: the heal-import flipped both views' owner
from `claude` (original importer) to `admin` (the re-importer), which
matches the prior finding that content-zip imports always rewrite
owner to the authenticated admin user regardless of `usermappings.json`.

**Conclusion:** the duplicate-subjects diagnosis in
`project_view_delete_server_bug.md` and the previous
`dashboard_delete_api.md` section was a red herring. The actual bug is
deeper in the delete implementation, affecting all views and all
reports on this 9.0.2 build.

## Finding 4 — Supermetric and custom group delete (question 5)

These were checked briefly to confirm install.py's existing paths work.

| Path | Method | Nonexistent UUID response | Verdict |
|---|---|---|---|
| `/suite-api/api/supermetrics/{id}` | DELETE | **204 No Content** (silent success) | Live, works as install.py uses it |
| `/suite-api/api/resources/groups/{id}` | DELETE | **404 "No such CustomGroup"** | Live, works, returns sensible 404 |
| `/suite-api/internal/supermetrics/{id}` | DELETE | 404 (no route) | Not an alternative path |

Both `DELETE /api/supermetrics/{id}` and
`DELETE /api/resources/groups/{id}` are alive and functional on this
build. No change needed to install.py for those content types.

One oddity worth noting: `DELETE /api/supermetrics/{nil-uuid}` returns
204, not 404. The endpoint silently succeeds for nonexistent UUIDs —
install.py should not interpret 204 as proof the named super metric
actually existed.

## Comparison — install.py vs SPA per content type

| Content type | install.py currently uses | SPA (Ext.Direct or REST) uses | Same endpoint? | Both work? |
|---|---|---|---|---|
| Super metric | `DELETE /api/supermetrics/{id}` (204) | same | yes | yes |
| Custom group | `DELETE /api/resources/groups/{id}` (404 on miss) | same | yes | yes |
| Dashboard | `ui/dashboard.action?mainAction=deleteTab` (Struts) | same | yes | yes (for unlocked caller-owned; locked admin-owned silent no-op) |
| **View** | `viewServiceController.deleteView` (Ext.Direct) | same | yes | **no — both 500** |
| **Report** | *(not implemented)* | `reportServiceController.deleteReportDefinitions` (Ext.Direct) | n/a | **no — SPA path is 500 too** |
| Symptom | `DELETE /api/symptomdefinitions/{id}` | same | yes | yes |
| Alert | `DELETE /api/alertdefinitions/{id}` | same | yes | yes |

**The SPA has no secret delete path for views or reports.** install.py
is already calling the same underlying implementation the SPA calls
(for views) and would call the same broken endpoint for reports if it
ever implemented report uninstall. Swapping endpoints is not a fix.

## Attempted cleanup of stranded items — result

Outcome: **0 of 4 items deleted; all 4 still stranded.**

| Item | Endpoints tried | Result |
|---|---|---|
| View `c192d4d6` | Ext.Direct deleteView, REST DELETE /internal/viewdefinitions/{id}, POST /internal/viewdefinitions/delete, after heal-import also | All 500 |
| View `36ff8c15` | Same | All 500 |
| Report `02fb7e8e` | Ext.Direct deleteReportDefinitions ([id] and scalar), DELETE /api/reportdefinitions/{id}, POST /api/reportdefinitions/delete | All 500 |
| Report `f524e76b` | Same | All 500 |

Final state on the instance (verified via GET after all probes):

- Views: both still present, now with `owner=admin` and deduped
  `subjects` (side effect of the heal-import experiment — this is a
  *cleaner* state than before). Still undeletable.
- Reports: both still present, unchanged (no update probe touched them).

Only remaining remediation path is an admin session in the VCF Ops
web console, if the Manage > Reports page renders at all given that
`getReportDefinitionThumbnails` also 500s. Manage > Views is more
likely to work because `getGroupedViewDefinitionThumbnails` (the list
call) is alive and returning real data. A `qa-tester` run with a real
browser against this lab instance could confirm whether the SPA can
visually delete these items or whether they're permanently stuck until
VCF Ops is patched.

## Side finding — heal-via-reimport actually works for subjects dedup

A useful operational trick fell out of this investigation: when the
server has a view with duplicated `subjects` entries caused by the
content-zip importer, you can **repair the server's state** (reduce
the duplicates to a single entry) by re-importing the view with
`POST /api/content/operations/import?force=true` carrying a modified
`content.xml` that contains **only one** `<SubjectType>` element
instead of the documented two. The importer accepts the single-element
form, the state is normalized, and (in this experiment) the view's
owner is also re-attributed to the authenticated admin user.

This does NOT unblock delete — but it's a potentially useful
workaround for other downstream tools that might choke on the
duplicate subjects. Worth documenting in case someone later finds a
tool that fails on the duplication and needs a repair recipe.

## Implications for install.py — what should change

1. **View uninstall (`_uninstall_views`):** no endpoint change helps.
   install.py's current call to `viewServiceController.deleteView` is
   already the same path the SPA uses. Both are broken. Keep the
   existing WARN-on-500 behavior. Consider adding a retry against
   `DELETE /suite-api/internal/viewdefinitions/{id}` as a secondary
   attempt purely so the install log shows both paths were tried and
   both failed with the same 500 — this makes the triage-on-failure
   message more explanatory to admins than a single Ext.Direct error.
2. **Report uninstall: still not implemented and there is no endpoint
   to implement it against.** Do not add a `_uninstall_reports`
   helper calling `DELETE /api/reportdefinitions/{id}` — it will only
   return 500 and generate noise in install logs. Document in install
   output that report cleanup is manual (web console), same as views.
3. **Documentation:** update the uninstall docs and agent prompts to
   reflect the newer finding that the bug is not duplicate-subjects.
   The current note implies that a format fix in the renderer could
   dodge the problem. It can't — the server-side delete handler
   crashes on any input.

## Code pattern for a future tooling patch (if desired)

```python
# vcfops_packaging/templates/install.py::_uninstall_views
# Improved: call both delete paths so the log captures both failure
# modes when the server is on a 9.0.2-era build with broken delete.

def _delete_view_best_effort(ui_client, suite_client, view_uuid, view_name):
    """Try Ext.Direct then internal REST; log both responses."""
    try:
        ui_client.delete_view(view_uuid)
        return "deleted"
    except RuntimeError as ext_exc:
        try:
            r = suite_client._session.delete(
                f"{suite_client.base}/suite-api/internal/viewdefinitions/{view_uuid}",
                headers={"X-vRealizeOps-API-use-unsupported": "true",
                         "Accept": "application/json"},
            )
            if r.status_code in (200, 204):
                return "deleted (via internal REST)"
            return (f"both paths failed: extdirect={ext_exc}; "
                    f"rest=HTTP {r.status_code}")
        except Exception as rest_exc:
            return (f"both paths failed: extdirect={ext_exc}; "
                    f"rest={rest_exc}")
```

Even this is only cosmetic — the outcome on a 9.0.2 build is still a
WARN. A real fix requires VMware to patch the server. Do not consider
this a blocker for shipping; the existing WARN-on-500 behavior is
already the right call.

## Environmental caveats

- Tested exclusively against VCF Operations 9.0.2.0 build 25137838
  on `vcf-lab-operations.int.sentania.net`. A later 9.0.x patch or
  9.1.x release may fix these bugs.
- The SPA at `/vcf-operations/ui/` is a 404 on this instance, so
  browser-level observation of what the SPA sends on a "Delete"
  click is not possible here. Inferred SPA behavior from the
  Ext.Direct catalog at `/ui/vcops/services/api.js` plus the fact
  that the catalog's `viewServiceController.deleteView` and
  `reportServiceController.deleteReportDefinitions` are the only
  mutating delete RPCs available.
- All testing done as `admin` (local account). Permission is ruled
  out as a variable.

## Cross-references

- `context/dashboard_delete_api.md` — UI session auth flow, working
  Struts `.action` endpoints, prior (incorrect) duplicate-subjects
  explanation for view delete. Update pending to reflect new findings.
- `context/ui_import_formats.md` — content-zip envelope wire format,
  documents the same 4 stranded items this investigation tried and
  failed to clean up.
- `context/struts_import_endpoints.md` — Ext.Direct controller
  catalog (parsed from `/ui/vcops/services/api.js`).
- `context/reports_api_surface.md` — previously noted that
  `DELETE /api/reportdefinitions/{id}` is broken; this file confirms
  the bug is fundamental, not per-item.
- `memory/project_view_delete_server_bug.md` — needs update: the
  duplicate-subjects diagnosis is wrong; the bug is deeper.
