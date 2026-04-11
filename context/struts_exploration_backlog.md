# Struts / Ext.Direct endpoint reference

VCF Ops 9.0.2 inventory of legacy `/ui/*` Struts actions and
Ext.Direct RPC methods that are empirically known to work or known
to be dead. This file started life as a backlog of api-explorer
tasks; the 2026-04-11 investigation closed every open item and
converged on a single finding — **there are no per-object UI import
endpoints in 9.0.2** — so this is now a permanent reference table
rather than a task list.

**Authoritative companion docs:**
- `context/dashboard_delete_api.md` — wire formats for working
  delete operations (the 2026-04-11 correction section has the
  view/report nested-JSON-string shapes)
- `context/ui_import_formats.md` — content-zip envelope wire format
  details, user-ID rewriting behavior, adapterKind semantics,
  Reports.zip flat shape
- `context/struts_import_endpoints.md` — full Ext.Direct controller
  catalog enumeration and dead-endpoint survey
- `memory/feedback_struts_priority.md` — when to use Struts vs REST
- `memory/project_vcf_ops_902_ui_deadends.md` — the UI import dead-end
  summary with traps to avoid

## What the framework actually uses

**Posture** (`feedback_struts_priority.md`): the framework prefers
REST / content-zip paths; Struts / Ext.Direct is last-ditch, only
used where no REST alternative exists. **QA inverts this** — to
catch real-world quirks, qa-tester drives the UI via the same
endpoints an admin's browser hits.

## Working endpoints (verified)

| Action | Endpoint | Data shape notes |
|---|---|---|
| UI login (3-step: JSESSIONID → creds → OPS_SESSION+csrfToken) | `/ui/login.action`, `/ui/index.action` | Form-encoded; see `dashboard_delete_api.md` |
| Dashboard list (by user) | `/ui/dashboard.action` `mainAction=getDashboardList` | Form-encoded |
| Dashboard delete | `/ui/dashboard.action` `mainAction=deleteTab` | `tabIds` = URL-encoded JSON `[{tabId, tabName}]` |
| View list (thumbnails, grouped) | `/ui/vcops/services/router` | Ext.Direct RPC `viewServiceController.getGroupedViewDefinitionThumbnails`, `data: null` |
| View delete | `/ui/vcops/services/router` | Ext.Direct RPC `viewServiceController.deleteView`, **`data: [{"viewDefIds": "[{\"id\":\"...\",\"name\":\"...\"}]"}]`** (JSON-stringified inside dict inside array) |
| Report list | `/ui/vcops/services/router` | Ext.Direct RPC `reportServiceController.getReportDefinitionThumbnails` with pagination filter |
| Report delete | `/ui/vcops/services/router` | Ext.Direct RPC `reportServiceController.deleteReportDefinitions`, **`data: {"reportDefIds": "[{\"id\":\"...\",\"name\":\"...\"}]"}`** (BARE DICT, not array — opposite of view delete) |
| Ext.Direct controller catalog (live session probe) | `/ui/vcops/services/api.js` | JS declaration of all controllers; 6 present in 9.0.2 |

## Dead / trap endpoints (do not use)

| Endpoint | Problem | Documented in |
|---|---|---|
| `/ui/dashboard.action?mainAction=uploadDashboard` | Dead stub — returns `{"success":false, "msg":"resultDto is null"}` for every input | `struts_import_endpoints.md` |
| `/ui/customGroup.action?mainAction=saveCustomGroup` | **Silent trap** — returns `{result: "ok"}` but does NOT persist anything. Use `POST /suite-api/api/resources/groups` instead. | `project_vcf_ops_902_ui_deadends.md` |
| `uploadContentController.uploadFile` (Ext.Direct, only formHandler upload in catalog) | Wired but throws HTTP 500 on every invocation | `struts_import_endpoints.md` |
| `/ui/alert.action`, no `alertDefinition.action`, `symptom.action`, `recommendation.action` | Not registered. Alert/symptom/recommendation import goes through content-zip envelope only. | `struts_import_endpoints.md` |
| `/ui/superMetric.action` | Only implements `getSuperMetrics` (read). No upload mainAction. Use content-zip. | `struts_import_endpoints.md` |
| `/ui/viewDefinition.action`, `/ui/view.action` | Not registered. View import only via content-zip envelope. | `struts_import_endpoints.md` |
| `/ui/report.action` | Not registered. Report import only via content-zip envelope. | `struts_import_endpoints.md` |
| `/suite-api/internal/viewdefinitions` | 404 on 9.0.2 builds (was present on older builds). Use Ext.Direct `viewServiceController.deleteView` with the corrected shape. | `dashboard_delete_api.md` |
| `/suite-api/internal/reportdefinitions` | 404 on 9.0.2 builds. Use REST `/api/reportdefinitions` for list or Ext.Direct `reportServiceController` for delete. | `ui_import_formats.md` |
| PS scriptblock for `ServerCertificateCustomValidationCallback` | Does NOT work on .NET Core 6+ / PS 7. Use `[System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator` static delegate. | `feedback_powershell_idioms.md` |

## The single finding that closed the backlog

From the 2026-04-11 investigation track (two parallel api-explorer
runs + the operator's browser HAR capture that gave us the winning
ground truth):

**There are no working per-object UI import dialog endpoints in
VCF Ops 9.0.2.** The SPA UI's drag-drop dialogs wrap the uploaded
file client-side into a bulk content-zip envelope and POST to
`/api/content/operations/import` — the same REST endpoint
`install.py` already uses. There is no distinct UI-layer API path
for qa-tester to instrument for drag-drop realism, because the SPA
itself isn't using one; it's calling the same REST path the
framework calls.

The `*.action` and Ext.Direct surface of 9.0.2 is for the **legacy
Flash / Ext JS UI**, most of which has been gutted in the SPA
transition. Delete and list operations survive; upload operations
do not. Expect this to change on a future build; re-run the
`/ui/vcops/services/api.js` catalog probe (requires an authenticated
UI session) on any Ops major version bump as a 30-second sanity
check for restored surface.
