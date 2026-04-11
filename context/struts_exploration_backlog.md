# Struts / Ext.Direct exploration backlog

Purpose: document the reverse-engineering work needed to let
`qa-tester` exercise the **native admin user experience** (drag-drop
imports via the UI) rather than the REST surface the installer uses.
Structured so api-explorer can pick items off this list one at a
time.

**Posture reminder** (see
`memory/feedback_struts_priority.md`): the framework code prefers
REST/content-zip paths; Struts/Ext.Direct is last-ditch. But **QA**
inverts this — to catch real-world quirks, qa-tester should drive
the UI via the same endpoints an admin's browser hits, not via the
installer's REST calls. Anything listed here is needed for QA
realism, not for the framework itself.

## Already mapped

| Action | Endpoint(s) | Documented in |
|---|---|---|
| UI login (3-step: JSESSIONID → creds → OPS_SESSION+csrfToken) | `/ui/login.action`, `/ui/index.action` | `context/dashboard_delete_api.md` |
| Dashboard list (by user) | `/ui/dashboard.action` action=`getDashboardList` | `context/dashboard_delete_api.md` |
| Dashboard delete | `/ui/dashboard.action` action=`deleteTab` | `context/dashboard_delete_api.md` |
| View list (thumbnails, grouped) | `/ui/vcops/services/router` Ext.Direct RPC `viewServiceController.getGroupedViewDefinitionThumbnails` | `context/dashboard_delete_api.md` |
| View delete | `/ui/vcops/services/router` Ext.Direct RPC `viewServiceController.deleteView` | `context/dashboard_delete_api.md` |
| Ext.Direct controller catalog (api.js) | `/ui/vcops/services/api.js` — 6 controllers listed | `context/struts_import_endpoints.md` |
| Struts action URL survey (which `*.action` slugs are registered) | 6 slugs registered; most are stubs | `context/struts_import_endpoints.md` |
| **Dashboard import (UI drag-drop)** | `/ui/dashboard.action?mainAction=uploadDashboard` is a **dead stub** (returns `{"success":false, "msg":"resultDto is null"}` for every input). `uploadContentController.uploadFile` Ext.Direct also dead (500). **No viable UI endpoint in 9.0.2.** | `context/struts_import_endpoints.md`, `context/ui_import_formats.md` |
| **Alert/Symptom/Recommendation import (UI drag-drop)** | No Struts handler. `/ui/alert.action` is a stub. No `alertDefinition.action`, `symptom.action`, or `recommendation.action` registered. Goes through REST envelope path only. | `context/struts_import_endpoints.md`, `context/ui_import_formats.md` |
| **Super Metric import (UI drag-drop)** | `/ui/superMetric.action` only implements `getSuperMetrics` (read). No upload mainAction. Goes through REST envelope path (which preserves UUIDs — confirmed by the installer's content-zip path). | `context/struts_import_endpoints.md`, `context/ui_import_formats.md` |
| **View import (UI drag-drop)** | No `/ui/view.action` or `/ui/viewDefinition.action` registered. `viewServiceController.saveOrUpdateViewDefinition` exists but takes JSON payload, not a file. Only REST envelope path. | `context/struts_import_endpoints.md` |
| **Custom Group import (UI drag-drop)** | `/ui/customGroup.action?mainAction=saveCustomGroup` returns a fake `{result: "ok"}` but **does not persist** anything — stub. Real creation goes through `POST /suite-api/api/resources/groups`. | `context/struts_import_endpoints.md` |
| **Report import (UI drag-drop)** | No `/ui/report.action` registered. `reportServiceController.saveOrUpdateReportDefinition` takes JSON, not a file. REST envelope path only. | `context/struts_import_endpoints.md`, `context/ui_import_formats.md` |

## Backlog — not yet mapped

Each item is scoped as an api-explorer task. Mark items done by
moving them to the "Already mapped" table above with a pointer to
the context file the exploration wrote. Do not batch these — one
action per api-explorer invocation keeps the findings tight.

## Resolution of items #1, #3, #5 (the original top-priority work) — 2026-04-11

The 2026-04-11 investigation (both the companion api-explorer thread
working on content-zip wire formats and the track focused on Struts
endpoints) converged on a single conclusion:

**There are no working per-object UI import dialog endpoints in
VCF Ops 9.0.2.** Every Struts `*.action` upload mainAction either
returns the Ext error panel (not registered), an empty body (stub),
or a JSON error that persists regardless of input (`uploadDashboard`
and `uploadContentController.uploadFile` are both dead). The entire
Ext.Direct controller catalog only has ONE formHandler upload
(`uploadContentController.uploadFile`), and it returns HTTP 500 on
every tested input combination.

**The UI's drag-drop dialogs — to the extent they exist in the
SPA at all — must wrap the dropped file in a bulk content-zip
envelope and call `POST /api/content/operations/import`.** This is
the same REST endpoint `install.py` already uses. qa-tester's "UI
realism" mode should therefore call the same REST client helpers,
with a test-report note that UI endpoints are dead stubs and REST
envelope is the only live import path on 9.0.2.

See `context/struts_import_endpoints.md` for the full action
enumeration, endpoint dead-end catalog, and the qa-tester code
pattern. See `context/ui_import_formats.md` for the content-zip
envelope wire format, user-ID rewriting, adapterKind semantics,
and Reports.zip flat form details.

Items #1–#6 in the backlog below are superseded by the mapping
entries added above. They remain here only as the historical
scoping document so future readers can understand what was asked
and why the answer was "the question was wrong — there is no
separate UI import path".

### 1. Dashboard import (drag-drop zip)  — RESOLVED, NO UI ENDPOINT EXISTS

**UI path:** Manage > Dashboards > actions menu > Import (or
similar). Admin picks a `.zip` containing `dashboard/dashboard.json`
plus resource `.properties` files. See reference zips under
`references/AriaOperationsContent/*/Dashboard*.zip` for the
format our `Dashboard.zip` drop-in is supposed to match.

**Need to learn:**
- Endpoint URL and HTTP method
- Multipart form field names (file param, CSRF token placement)
- Response shape on success and on failure (parse error, duplicate
  name, missing view reference, permission denial)
- Whether the server silently rewrites `lastUpdateUserId` and
  `userId` in the uploaded JSON to the importing user (the 130-
  dashboard corpus survey strongly implies this but doesn't prove
  it)
- Whether dashboards imported this way land as `locked=true admin`
  the same way content-zip imports do — if not, manual-import
  dashboards may be easier to uninstall than content-zip-imported
  ones

**Evidence to collect:** HAR capture of a real browser import on
the lab instance, plus the import of one reference dashboard to
confirm UUID-rewrite behavior.

### 2. View import  — RESOLVED, NO UI ENDPOINT EXISTS

**UI path:** Manage > Views > actions menu > Import. Admin picks a
`.zip` containing `content.xml` at root.

**Need to learn:**
- Endpoint, method, multipart shape
- Whether view import accepts a bare `content.xml` or requires the
  zip wrapper
- Response handling: success envelope, parse errors, duplicate IDs,
  missing supermetric references
- Ownership and sharing defaults — do manually-imported views
  avoid the VCF Ops 9.0.2 delete-500 server bug
  (`project_view_delete_server_bug.md`) that affects content-zip-
  imported views?

### 3. Super Metric import  — RESOLVED, NO UI ENDPOINT EXISTS

**UI path:** Administration > Super Metrics > (gear / actions) >
Import. Admin picks a bare `.json` file keyed by UUID.

**Need to learn:**
- Endpoint, method, multipart or raw-JSON body
- Whether the UI import preserves the UUIDs in the file or
  reassigns them (UUID preservation is the entire reason we use
  the content-zip path from install.py — if the UI import
  preserves UUIDs, it could become an alternate supported path)
- Response shape and how duplicate detection reports back
- Whether the import implicitly runs `/internal/supermetrics/
  assign` (resource-kind wiring) or leaves that to the operator

### 4. Custom Group import  — RESOLVED, NO UI ENDPOINT EXISTS

**UI path:** Environment > Custom Groups > Import. Admin picks a
bare `.json` file.

**Need to learn:**
- Endpoint, method, body shape
- Whether it accepts the same wire shape as `POST /api/resources/
  groups` (what we currently use) or wants an export-format
  wrapper
- Behavior on duplicate name, missing group type, missing
  supermetric reference inside membership rules

### 5. Alert/Symptom/Recommendation import (the combined `<alertContent>` XML path)  — RESOLVED, NO UI ENDPOINT EXISTS

**UI path:** Alerts > Definitions > (actions) > Import. Admin picks
a `.xml` file with `<alertContent>` root.

**Need to learn:**
- Endpoint, method, multipart shape
- Which sub-sections (`SymptomDefinitions`, `AlertDefinitions`,
  `Recommendations`) the UI accepts in one file vs. requires
  separate uploads
- Whether cross-reference IDs (`ref=`) are resolved by exact string
  match or by some stable hash of name — and whether a ref that
  points at a symptom not present in the same XML import causes a
  failure or a deferred link
- Behavior with `adapterKind="VMWARE"` (key form) vs
  `adapterKind="vCenter Operations Adapter"` (display name form)
  — tied to the Part 2 serializer verification task

### 6. Report import  — RESOLVED, NO UI ENDPOINT EXISTS

**UI path:** Administration > Reports > Import (if it exists).

**Need to learn first:**
- Whether a per-object Reports UI import dialog exists at all —
  unknown from the reference corpus we have so far
- If yes: zip shape, endpoint, method
- If no: "reports have no per-object UI import path" becomes a
  documented limitation and manual-import admins are told to use
  install.py for reports specifically

### 7. Native content export (Admin > Content export to zip)

Relevant because one very common admin workflow is **export your
own content to share with a colleague**. If we can learn what
shape the UI export path produces, we can make our `bundles/<slug>/
*.zip`/`*.json` drop-in files byte-for-byte indistinguishable from
UI-exported ones, which removes any "is this real?" friction for
admins who grep through them.

**Scope intentionally broad:** HAR-capture one export of each
content type the UI supports (dashboard, view, SM, custom group,
alert definition, symptom definition, recommendation, report,
policy). Save representative samples under `references/` so they're
available for future reference-grounding work like the 130-
dashboard user-ID survey.

### 8. Policy import via UI

We currently use `POST /api/policies/import?forceImport=true` from
install.py to round-trip policy XML for SM enablement. The UI has
its own policy import dialog. Worth mapping both because:

- Any discrepancy between the two paths (e.g. UI does additional
  server-side validation the REST endpoint skips) is a source of
  install/manual-import divergence bugs
- If the UI path is strictly more reliable, it's a candidate for
  the last-ditch framework fallback

## Prioritization for qa-tester realism

The first qa-tester bundle-path run can proceed without any of
these being mapped — it will fall back to REST for anything it
can't drive via Struts, and emit a test-report note flagging the
gap. After that first run, the three highest-value mappings for
"native admin experience" are:

1. **Dashboard import (#1)** — because `Dashboard.zip` drop-in is
   the most visually obvious drag-drop path, and the one most
   likely to surface UUID-rewrite and ownership surprises.
2. **Alert/symptom/recommendation import (#5)** — because our
   `AlertContent.xml` synthesizer is brand new and the adapterKind
   form question is unverified.
3. **Super Metric import (#3)** — because it's the only content
   type where the installer already uses the content-zip path
   specifically for UUID preservation; if the UI import preserves
   UUIDs, our whole install-path story could simplify.

The remaining items (#2, #4, #6, #7, #8) are valuable but can wait
until a qa-tester run actually finds a quirk the REST path
sidesteps, at which point we'll know exactly which Struts path
needs mapping first.
