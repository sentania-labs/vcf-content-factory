# Legacy /ui/ Struts + Ext.Direct import endpoint reconnaissance (VCF Ops 9.0.2)

**Scope:** the backlog in `context/struts_exploration_backlog.md` asked
for UI-dialog import endpoints for Dashboard, AlertContent, Super
Metric, View, Custom Group, and Report drop-ins, with the goal that
`qa-tester` could drive the same endpoints a real admin's browser
would hit. This file is the empirical survey of the
`/ui/*.action` Struts layer and the `/ui/vcops/services/router`
Ext.Direct layer on `vcfops.example.com` (VCF Ops
9.0.2.0 build 25137838) run 2026-04-11.

**The headline finding** also appears in `context/ui_import_formats.md`
(written by a sibling investigation): **there are no working per-
object UI import dialog endpoints in VCF Ops 9.0.2**. The classic
`/ui/*.action` layer is mostly stubbed out, the Ext.Direct form-handler
`uploadContentController.uploadFile` returns HTTP 500, and the new
SPA under `/vcf-operations/ui/` is a 404 on this instance. Every UI
import dialog that exists in 9.0.2 ultimately wraps its file into a
bulk content-zip envelope and calls `POST /api/content/operations/
import` — the same REST endpoint `install.py` already uses.

This file complements `context/ui_import_formats.md` by documenting
**the endpoint survey methodology and raw results**, so future
investigations can confirm the "nothing works" finding quickly
without retreading all the same dead ends. `ui_import_formats.md`
covers the **wire-format side** (what the envelope looks like, how
user IDs are rewritten, which adapter keys to emit).

## Authenticated probing recipe (reusable)

The probes below all assume a UI session obtained via the three-step
flow from `context/dashboard_delete_api.md`:

```python
import base64, json, os, requests
requests.packages.urllib3.disable_warnings()
HOST = os.environ["VCFOPS_HOST"]
USER = os.environ["VCFOPS_USER"]
PWD  = os.environ["VCFOPS_PASSWORD"]

def ui_login():
    s = requests.Session(); s.verify = False
    s.get(f"https://{HOST}/ui/login.action", params={"vcf": "1"})
    r = s.post(f"https://{HOST}/ui/login.action", data={
        "mainAction": "login", "userName": USER, "password": PWD,
        "authSourceId": "localItem", "authSourceName": "Local Account",
        "authSourceType": "", "forceLogin": "false",
        "timezone": "0", "languageCode": "us"})
    assert r.text.strip() == "ok", r.text
    r = s.get(f"https://{HOST}/ui/index.action", allow_redirects=False)
    ops = r.cookies.get("OPS_SESSION") or s.cookies.get("OPS_SESSION")
    csrf = json.loads(base64.b64decode(ops))["csrfToken"]
    return s, csrf
```

## Struts action registration probe

Struts dispatches by URL segment (`*.action`). To enumerate which
action classes are registered without guessing `mainAction` values,
hit the URL with a garbage `mainAction`:

- **Registered action, unknown mainAction** → HTTP 200 with body
  length 1125 bytes containing an `Ext.onReady` `errorPanel`
  HTML fragment.
- **Registered action, silent fallthrough** → HTTP 200 with body
  length 0 (action receives the request but has no case for the
  mainAction and returns nothing).
- **Unregistered URL** → HTTP 404 with the 49690-byte Tomcat 404 page.

The following enumeration was run across the obvious candidate names:

| URL | 200/404 | Notes |
|---|---|---|
| `/ui/dashboard.action` | 200 errorPanel | Only partial mainActions work (see below). |
| `/ui/alert.action` | 200 errorPanel | All tested mainActions return errorPanel — stubbed. |
| `/ui/superMetric.action` | 200 silent/empty | Only `getSuperMetrics` returns real JSON. |
| `/ui/customGroup.action` | 200 silent/empty | Only `saveCustomGroup` (stub) and `deleteCustomGroup` respond. |
| `/ui/policy.action` | 200 silent/empty | Only `importPolicy` returns JSON (`{"success":false}`). |
| `/ui/contentManagement.action` | 200 silent/empty | Every tested mainAction is empty — appears dead. |
| `/ui/supermetric.action` (lowercase) | 404 | Case-sensitive. |
| `/ui/view.action`, `/ui/viewDefinition.action` | 404 | No Struts view import URL. |
| `/ui/report.action`, `/ui/reportTemplate.action` | 404 | No Struts report import URL. |
| `/ui/symptom.action`, `/ui/symptomDefinition.action` | 404 | No Struts symptom URL. |
| `/ui/alertDefinition.action`, `/ui/recommendation.action` | 404 | No separate alertdef/recommendation URLs. |
| `/ui/content.action`, `/ui/uploadFile.action`, `/ui/importContent.action` | 404 | No general content upload action. |

**So six URL slugs are registered** — `dashboard`, `alert`, `superMetric`,
`customGroup`, `policy`, `contentManagement` — but most of them are
stubs. Of those six, only `dashboard.action` has a non-trivial set
of working mainActions (the ones documented in
`context/dashboard_delete_api.md`).

**2026-04-17 correction — the original probe methodology missed at least two
live handlers:** `/ui/solution.action` and `/ui/utility.action`.  These were not
in the candidate list probed in the 2026-04-11 run because the assumption at the
time was that solution management lived entirely on `/admin/`.  They are both
live:

- `/ui/solution.action` — full pak lifecycle mainAction surface (`install`,
  `remove`, `getIntegrations`, `getLatestInstalledSolutionStatuses`, `enable`,
  `disable`, `reinstall`, `resetSolutionUninstallState`, `cancel`, `finishStage`,
  and more).  Proven live by the 2026-04-16 uninstall investigation
  (`context/pak_uninstall_api_exploration.md`) and confirmed by SPA bundle grep
  (`context/pak_ui_upload_investigation.md` §"Live-source findings").
- `/ui/utility.action` — supports at minimum `mainAction=prepareFileUpload`,
  which the SPA calls immediately before the multipart upload
  (`context/pak_ui_upload_investigation.md` §"prepareFileUpload precursor").
  Proven from JS source; not yet exercised live.

The probe methodology in §"Struts action registration probe" should be re-run
with a broader candidate list that includes at minimum: `solution`, `utility`,
`integration`, `marketplace`, `repository`, `pak`, `managementPack`,
`softwareUpdate`, `upgrade`.  Other live slugs may still be missing from the
2026-04-11 enumeration.

## Dashboard action working-mainAction inventory

Based on the probes run here and the earlier results in
`dashboard_delete_api.md`:

| mainAction | Status | Notes |
|---|---|---|
| `getDashboardList` | JSON | Returns `{dashboards: [...]}`. See `list_dashboards()` in install.py. |
| `getDashboardConfig` | JSON | Per-dashboard config. |
| `deleteTab` | JSON | Silent no-op on locked dashboards (see delete bug). |
| `saveTab` | JSON `{}` | Accepts, doesn't meaningfully persist. |
| `cloneDashboard` | JSON | Creates unlocked copy owned by caller. |
| `uploadDashboard` | JSON `{"success":false, "msg":"Unable to import dashboard resultDto is null."}` | **Dead stub** — returns the same error for every permutation of file field name, query/form parameter placement, content type, and body shape tested. Probed 15+ variants. |
| `exportTab`, `getExportDashboard`, `doExport`, `doImport`, `importTab`, `importDashboard` | HTML errorPanel | Not wired — return the Ext.JS unknown-action page. |
| `saveDashboardConfig`, `setDashboardLock`, `lockTab`, `unlockTab`, `manageTab`, `shareTab` | HTML errorPanel | Not wired. |

## Ext.Direct controller catalog

The full Ext.Direct API is exposed at `/ui/vcops/services/api.js`
(requires a logged-in session). Parsed 2026-04-11:

| Controller | Methods | Import-relevant? |
|---|---|---|
| `viewFilterController` | `getFilterMetadata` | No. |
| `reportServiceController` | 14 methods — `getReportDefinitionThumbnails`, `saveOrUpdateReportDefinition`, `runReport`, `deleteReportDefinitions`, etc. | `saveOrUpdateReportDefinition` is the only creation path and it takes a JSON body, not a file. |
| `reportController` | `reGenerateReport`, `getReports`, `deleteReportInstances` | No. |
| `reportScheduleController` | `getTimeZones`, `getById`, `getByReportId`, `saveOrUpdate`, `deleteSchedule` | No. |
| `viewServiceController` | 24 methods — CRUD on views, thumbnails, chart rendering. Includes `uploadImage (formHandler=true)` for view background images and `saveOrUpdateViewDefinition` for JSON save. | No per-file view import. |
| `uploadContentController` | `uploadFile (formHandler=true)`, `setMaxUploadSize` | **Present but broken.** `uploadFile` returns HTTP 200 with an `<textarea>`-wrapped `{"type":"exception","message":"Internal server error."}` for every tested invocation. `setMaxUploadSize` returns `true`. |

**There are no controllers named `dashboardServiceController`, `super
MetricController`, `customGroupController`, `alertServiceController`,
`symptomController`, or `policyController`.** The Ext.Direct RPC
surface on this instance is limited to views, reports, and a single
dead upload endpoint.

## `uploadContentController.uploadFile` — tested and dead

This is the only formHandler-flagged upload endpoint in the entire
Ext.Direct catalog. The call shape for a formHandler is:

```python
files = {"file": ("Dashboard.zip", zip_bytes, "application/zip")}
resp = s.post(f"https://{HOST}/ui/vcops/services/router",
    data={
        "extType": "rpc",
        "extTID": "1",
        "extAction": "uploadContentController",
        "extMethod": "uploadFile",
        "extUpload": "true",
    },
    files=files,
    headers={"secureToken": csrf},
)
```

Response is always:

```
HTTP 200
Content-Type: text/html;charset=UTF-8
Body:
<html><body><textarea>{"type":"exception","message":"Internal server error.","tid":1,"action":"uploadContentController","method":"uploadFile","result":{"success":false}}</textarea></body></html>
```

Tested permutations — all returned the same error:

- File field names: `file`, `upload`, `fileData`, `content`,
  `dashboardFile`, `dashboardZip`, `dashboard`, `data`, `contentFile`,
  `uploadFile`, `importFile`, `tab`, `tabFile`.
- Additional selector params: `contentType=DASHBOARD|VIEW|SUPERMETRIC|
  CUSTOMGROUP|ALERT|POLICY|REPORT|CONTENT_PACK`, same list under
  `type`, `fileType`, `resourceType`, `importType`.
- With and without `extUpload=true`.
- `setMaxUploadSize()` was called first to see if a 0-byte limit
  was blocking uploads — it returned `true`, so the limit is not
  the problem.
- The caller is `claude`, a full `Administrator` on the scope —
  not a permission issue.

The action is **physically present** in the Ext.Direct router
(it responds with a well-formed `action`/`method`/`tid` envelope)
but its implementation throws an exception before doing anything
meaningful. This matches the pattern where Struts `uploadDashboard`
returns `resultDto is null` — both upload paths are present-but-dead
in 9.0.2.

## `policy.action?mainAction=importPolicy`

The one Struts endpoint that had a JSON response with a plausible
error message:

```python
resp = s.post(f"https://{HOST}/ui/policy.action",
    data={"mainAction": "importPolicy", "secureToken": csrf})
# -> 200 {"success":false}
```

Not exercised with a real policy XML file because the backlog
de-scoped policy import (item #8, low priority) and the REST path
at `POST /api/policies/import` already works for install.py's
SM-enablement flow. Confirming whether this Struts handler is
actually alive or another stub would require a follow-up experiment.

## SaveCustomGroup stub behavior

`customGroup.action?mainAction=saveCustomGroup` returns the literal
string `{result: "ok"}` (note: not valid JSON — no quotes on
`result`) regardless of payload. Tested with form fields `group`,
`data`, `customGroup`, `payload`, all containing a valid minimal
group JSON. In every case:

1. The response was identical (`{result: "ok"}`).
2. No group was actually created on the instance (verified by
   `GET /suite-api/api/resources/groups` — no `__probe_cg__` in
   the result).

So `saveCustomGroup` is **also a stub** that returns fake success
without persisting anything. Real custom group creation goes through
`POST /suite-api/api/resources/groups` (what the installer uses).

## What this means for qa-tester

`qa-tester`'s goal of "replicate what a real admin experiences when
they drag-drop a file into a UI import dialog" cannot be satisfied
against VCF Ops 9.0.2 via any distinct UI endpoint, because **there
is no distinct UI endpoint to hit**. The options are:

1. **Drive the REST envelope path directly** — exactly what
   `install.py` already does via
   `POST /suite-api/api/content/operations/import`. This is the
   truthful representation of what the UI layer does under the
   hood in 9.0.2, and `ui_import_formats.md` confirms the envelope
   wire format is stable. **Recommendation:** qa-tester's UI-realism
   mode should call the same client helpers install.py uses,
   documenting in test output that "UI dialog endpoints are dead
   stubs in 9.0.2; REST envelope is the only live path".
2. **Drive a headless browser** (Playwright against the legacy
   `/ui/` or the new SPA if it's actually reachable on any test
   instance) — more faithful to the "drag-drop" user journey but
   an order of magnitude more complex and not warranted given
   finding #1.

Option 1 is the right call. The framework's current install path
and the hypothetical "UI driver" converge to the same REST call,
so qa-tester's test report should simply note that the distribution
package's drop-in files are not directly consumable by any 9.0.2 UI
dialog — they are inputs to `install.py`'s envelope builder, and
that's the supported path.

## qa-tester code pattern

Because no UI import endpoint works, qa-tester should reuse the
existing REST client code in `install.py` and in the
`vcfops_dashboards`, `vcfops_supermetrics`, `vcfops_alerts`,
`vcfops_reports`, `vcfops_customgroups`, `vcfops_symptoms` packages.
The minimal pattern for a "UI realism" mode of qa-tester is:

```python
# qa-tester's UI-realism driver — thin wrapper over install.py
# bundles/<slug>/<artifact> files are NOT consumed by any real
# UI dialog in VCF Ops 9.0.2. Install them via the same
# content-zip envelope path the installer uses, and record in the
# test report that "no per-object UI endpoint exists in 9.0.2".

from vcfops_packaging.templates.install import (
    UIClient,                    # for dashboard/view delete cleanup
    _build_sm_zip,               # SM envelope builder
    _build_views_inner_zip,      # views inner content.xml
    _build_dashboard_inner_zip,  # dashboard inner JSON
    # etc.
)
from vcfops_dashboards.client import VCFOpsClient  # for REST import

client = VCFOpsClient.from_env()
# Upload the same content-zip envelope the real install does.
client.import_content_zip(envelope_bytes, force=True)
```

For cleanup after a QA run, the `UIClient` from `install.py`
already handles dashboard delete (`deleteTab`) and view delete
(`viewServiceController.deleteView`). Note the known server bugs:

- Content-zip-imported views cannot be deleted (500 on both
  delete paths — see `context/dashboard_delete_api.md` §View delete
  limitation).
- Admin-owned locked dashboards cannot be deleted by a non-admin
  user (see `dashboard_delete_api.md` §No delete path).
- Report definitions cannot be deleted (500 on both
  `DELETE /api/reportdefinitions/{id}` and Ext.Direct
  `reportServiceController.deleteReportDefinitions`).

qa-tester should log these as expected WARN/partial-failure states,
not as test failures, until the server bugs are resolved.

## Cross-reference

- `context/ui_import_formats.md` — content-zip envelope wire format,
  user-ID rewriting, adapterKind semantics, Reports.zip flat form.
  **Read this first** for anything wire-format related.
- `context/dashboard_delete_api.md` — UI session auth flow, working
  `/ui/dashboard.action` mainActions, Ext.Direct `viewService
  Controller` delete, view-delete server bug.
- `context/content_api_surface.md` — the REST endpoints the framework
  actually uses.
- `context/wire_formats.md` — per-content-type wire formats for
  the envelope importer.

## Investigation artifacts and cleanup

All experiments ran against the lab instance with no test objects
left behind on the server:

- `uploadDashboard` probes never completed a successful import
  (the action returns the same error regardless of input), so no
  dashboards were created.
- `uploadContentController.uploadFile` probes all returned HTTP 500
  before reaching any persistence layer, so no content was stored.
- `saveCustomGroup` returned fake success without persisting, so
  no custom groups were created.
- Dashboard list and custom group list queried after the run
  showed zero probe objects (no entries with `__probe` or
  `__struts` in the name).

Local scratch files under `/tmp/struts-probe/` (probe-dashboard.zip,
api.js, default-policy.xml, exported-dashboard.zip) are throwaway
and were not committed.

## Supportability caveat

Everything in this file is **unsupported internal UI surface**.
The legacy `/ui/` Struts layer is one release away from being
removed entirely; the fact that `dashboard.action` still works for
`deleteTab` / `getDashboardList` / `cloneDashboard` is a 9.0.2-
specific accident that future VCF Operations versions are likely
to break. Track this layer as load-bearing **only** for cleanup
operations (delete paths), not for anything imports-related.
