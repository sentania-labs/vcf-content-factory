# Dashboard + view delete via UI action endpoints

Dashboards and views have no public or internal REST DELETE endpoint.
The only delete path is through the Struts/Ext.Direct UI action layer
that backs the VCF Operations web console.

## Authentication flow

The UI uses a separate session from the Suite API. Three steps:

### 1. Get an initial JSESSIONID

```
GET https://{host}/ui/login.action?vcf=1
```

Response sets a `JSESSIONID` cookie scoped to `/ui`.

### 2. Login (local account)

```
POST https://{host}/ui/login.action
Content-Type: application/x-www-form-urlencoded
Cookie: JSESSIONID=<from step 1>

mainAction=login
userName=<user>
password=<password>
authSourceId=localItem
authSourceName=Local Account
authSourceType=
forceLogin=false
timezone=0
languageCode=us
```

Auth source IDs come from
`GET /ui/login.action?mainAction=getAuthSources` (returns JSON array;
`localItem` is always the local-account entry). For SSO/LDAP sources,
use the UUID `id` from that response.

Success: HTTP 200, body is the literal string `ok`.
The response updates the `JSESSIONID` cookie (same path `/ui`).

### 3. Load index.action to get the CSRF token

```
GET https://{host}/ui/index.action
Cookie: JSESSIONID=<from step 2>
```

Response is an HTTP 302 redirect (to `/vcf-operations/ui/`).
The response sets an `OPS_SESSION` cookie (path `/vcf-operations`).
This cookie is **base64-encoded JSON** containing:

```json
{
  "csrfToken": "<uuid>",
  "userId": "<uuid>",
  "userName": "...",
  "opsUISessionId": "<JSESSIONID value>",
  ...
}
```

Decode `OPS_SESSION` and extract `csrfToken`. This is the
`secureToken` that all subsequent UI action calls require.

**Do not follow the 302 redirect.** Following it invalidates the
`OPS_SESSION` cookie (the response to the redirected URL sets
`OPS_SESSION=x` with an expiry in the past).

## Dashboard delete

```
POST https://{host}/ui/dashboard.action
Content-Type: application/x-www-form-urlencoded
Cookie: JSESSIONID=<from step 2>

mainAction=deleteTab
tabIds=[{"tabId":"<dashboard-uuid>","tabName":"<dashboard-name>"}]
secureToken=<csrfToken from OPS_SESSION>
currentComponentInfo=TODO
globalDate={"dateRange":"last6Hour"}
```

- `tabIds` is a JSON array (URL-encoded as a form value). Each entry
  has `tabId` (dashboard UUID) and `tabName` (display name).
- Multiple dashboards can be deleted in one call.
- Deleting a non-existent UUID is a silent no-op (HTTP 200, returns
  the full dashboard config).
- Success: HTTP 200, body is the full dashboard configuration JSON
  (same as `mainAction=getDashboardConfig`).

## Dashboard list

```
POST https://{host}/ui/dashboard.action
Content-Type: application/x-www-form-urlencoded
Cookie: JSESSIONID=<from step 2>

mainAction=getDashboardList
secureToken=<csrfToken>
currentComponentInfo=TODO
globalDate={"dateRange":"last6Hour"}
```

Returns JSON: `{"dashboards":[...]}`. Each entry has `id`, `name`,
`description`, `locked`, `owner`, `shared`, `editable`, etc.

## View delete

Views have no Struts `.action` endpoint. View delete is exposed via
**Ext.Direct RPC** at:

```
POST https://{host}/ui/vcops/services/router
Content-Type: application/json
Cookie: JSESSIONID=<from step 2>
secureToken: <csrfToken>     <-- HTTP header, not form param

[{
  "action": "viewServiceController",
  "method": "deleteView",
  "data": ["<view-uuid>"],
  "type": "rpc",
  "tid": 1
}]
```

- `tid` is a transaction ID (monotonically increasing integer per
  session; any positive integer works).
- `secureToken` goes as an **HTTP request header** (not in the JSON
  body and not as a query parameter).
- Success: HTTP 200, body is a JSON array with one result object.
- Deleting a non-existent view returns
  `{"type":"exception","message":"Internal server error."}`.
- Multiple calls can be batched in one request (standard Ext.Direct
  batching).

Other useful Ext.Direct methods on `viewServiceController`:
`getGroupedViewDefinitionThumbnails` (len 0, lists all views),
`saveOrUpdateViewDefinition` (len 1, create/update),
`getView` (params: resourceRef, viewDefinitionId, controls, isAsc,
columnIndex).

## Dashboard lock and delete behavior (empirically verified 2026-04-10)

### deleteTab vs lock state

- `deleteTab` on a **locked** dashboard is a **silent no-op**: HTTP 200,
  returns the full dashboard config, dashboard not deleted.
- `deleteTab` on an **unlocked** dashboard owned by the calling user
  succeeds (confirmed with clone-created dashboards).
- There is **no unlockTab, setDashboardLock, or equivalent
  mainAction** in the Struts layer. Tested: `setDashboardLock`,
  `lockTab`, `unlockTab`, `manageTab`, `editTab`, `modifyTab`,
  `updateTab`, `shareTab` — all return error pages (invalid action).

### saveDashboardConfig cannot unlock

`mainAction=saveDashboardConfig` with `isLocked: false` in the
config JSON returns an HTML error page (not JSON). The Struts layer
rejects the full-config save. `mainAction=saveTab` accepts the
request (returns `{}`) but does not change lock state.

### Ext.Direct has no dashboardServiceController

`dashboardServiceController.unlockDashboard`,
`dashboardServiceController.deleteDashboard`, etc. all return
`{"type":"exception"}` — the controller does not exist.

### cloneDashboard creates unlocked, caller-owned copies

```
mainAction=cloneDashboard
tabId=<dashboard-uuid>
```

Returns JSON: `{"tabId":"<new-uuid>","tabName":"<name> 1"}`.
The clone is **unlocked** and **owned by the calling user**, regardless
of the original's lock/owner state. The clone can be deleted via
`deleteTab`. The original is unaffected.

### Content-zip import always assigns owner=admin

Tested: reimporting dashboards via `POST /api/content/operations/import`
with `usermappings.json` mapping to `userName: "claude"` — the
imported dashboards still show `owner: "admin"` in `getDashboardList`.
The content operations importer **ignores usermappings.json for
ownership assignment on UPDATE** and always assigns to admin.

This contradicts the earlier hypothesis in `wire_formats.md` that
`usermappings.json` controls ownership. It may control ownership only
for **new** dashboards (not tested), or it may be entirely ignored by
the content operations import path (which differs from the internal
content management import path the old Flash UI used).

### Content-zip import always forces locked=true

Confirmed: even when the dashboard.json payload contains
`"locked": false`, the server sets `locked: true` after import.
This is consistent across both new and updated dashboards.

### getDashboardList response fields

Each dashboard entry includes:
- `id`, `name`, `description`
- `locked` (bool) — server-enforced, always true after import
- `owner` (string) — username of owner, always "admin" after import
- `editable` (bool) — false if caller is not the owner
- `shared`, `sharedPublicly` (bools)
- `reportUsageCount` (int)
- `autoswitchEnabled`, `autoswitchDelay` (scheduling)

### getDashboardConfig tab fields

Per-tab (dashboard) config includes `isLocked`, `isShared`,
`name`, `nameOriginal`, `id`, `columnCount`, `columnProportion`,
`description`, `widgets[]`. Does **not** include `owner` or
`userId` — ownership is only visible in `getDashboardList`.

### No delete path for admin-owned locked dashboards from non-admin user

**Confirmed dead end.** A non-admin user (even with Administrator
role) cannot delete dashboards that are `locked: true` and
`owner: admin`. All attempted paths fail:

1. `deleteTab` — silent no-op (lock blocks it)
2. `saveDashboardConfig` / `saveTab` — cannot change lock state
3. Content reimport with modified usermappings — ownership not reassigned
4. No Ext.Direct unlock/delete controller exists
5. No REST API delete endpoint exists (public or internal)

**Only viable paths:**
- Login as the `admin` account (requires admin password)
- Use the VCF Operations web console as admin to manually unlock/delete
- Accept that imported dashboards are permanent until admin intervenes

### Implication for the content factory

The packager's `usermappings.json` with `userName: "admin"` is not
the root cause of the ownership problem — the importer assigns
admin ownership regardless. However, the `[VCF Content Factory]`
prefix on dashboard names makes them identifiable for manual cleanup.

Future work: if the framework needs autonomous delete, it must
either (a) use admin credentials for the import, (b) find an
alternate import path that respects usermappings, or (c) implement
a pre-delete step that logs in as admin via the UI.

## Gotchas

1. **Two session systems.** The Suite API (`/suite-api/`) uses bearer
   tokens from `/api/auth/token/acquire`. The UI (`/ui/`) uses
   `JSESSIONID` cookies + CSRF tokens. They are completely
   independent. A Suite API token cannot authenticate to `*.action`
   endpoints.

2. **OPS_SESSION is fragile.** It is set on the 302 response from
   `GET /ui/index.action` but cleared if you follow the redirect.
   Capture it from the 302 response headers without following.

3. **SSL verification.** Lab instances use self-signed certs;
   disable SSL verification.

4. **secureToken placement differs.** Struts `.action` endpoints
   take `secureToken` as a **form POST parameter**. Ext.Direct
   (`/ui/vcops/services/router`) takes it as an **HTTP header**.
   Getting this wrong returns HTTP 400 (empty body) for Struts or
   200 with an auth error for Ext.Direct.

5. **Logout.** `GET /ui/login.action?mainAction=logout` invalidates
   the session. Returns 302.

6. **Content operations import vs raw `requests.post`.** The import
   endpoint requires `Content-Type: None` override (let requests
   set multipart boundary) and the form field name `contentFile`
   (not `file`). The `VCFOpsClient.import_content_zip` handles
   this correctly; raw requests calls need the override explicitly.

7. **Export/import are not symmetric.** `GET /api/content/operations/
   export/zip` produces a zip that `POST /api/content/operations/import`
   accepts, but only when using `contentFile` as the form field name
   and `force=true`. Using `file` as the field name returns 500.

6. **No view list action endpoint.** There is no Struts action for
   listing views. Use either the Ext.Direct
   `viewServiceController.getGroupedViewDefinitionThumbnails` or
   the content export zip path to enumerate views.

## Python snippet (requests library)

```python
import base64, json, requests

def ui_login(host, user, password, verify_ssl=False):
    """Authenticate to the VCF Ops UI and return (session, csrf_token)."""
    s = requests.Session()
    s.verify = verify_ssl

    # Step 1: get initial JSESSIONID
    s.get(f"https://{host}/ui/login.action", params={"vcf": "1"})

    # Step 2: login
    resp = s.post(f"https://{host}/ui/login.action", data={
        "mainAction": "login",
        "userName": user,
        "password": password,
        "authSourceId": "localItem",
        "authSourceName": "Local Account",
        "authSourceType": "",
        "forceLogin": "false",
        "timezone": "0",
        "languageCode": "us",
    })
    assert resp.text == "ok", f"Login failed: {resp.text!r}"

    # Step 3: hit index.action to get OPS_SESSION (do NOT follow redirect)
    resp = s.get(f"https://{host}/ui/index.action", allow_redirects=False)
    ops_cookie = resp.cookies.get("OPS_SESSION") or s.cookies.get("OPS_SESSION")
    assert ops_cookie, "OPS_SESSION cookie not set"
    ops_data = json.loads(base64.b64decode(ops_cookie))
    csrf_token = ops_data["csrfToken"]

    return s, csrf_token


def delete_dashboards(s, host, csrf_token, dashboards, verify_ssl=False):
    """Delete dashboards by list of (uuid, name) tuples."""
    tab_ids = [{"tabId": uid, "tabName": name} for uid, name in dashboards]
    resp = s.post(f"https://{host}/ui/dashboard.action", data={
        "mainAction": "deleteTab",
        "tabIds": json.dumps(tab_ids),
        "secureToken": csrf_token,
        "currentComponentInfo": "TODO",
        "globalDate": json.dumps({"dateRange": "last6Hour"}),
    })
    resp.raise_for_status()
    return resp.json()


def delete_view(s, host, csrf_token, view_uuid, verify_ssl=False):
    """Delete a view by UUID via Ext.Direct."""
    resp = s.post(
        f"https://{host}/ui/vcops/services/router",
        json=[{
            "action": "viewServiceController",
            "method": "deleteView",
            "data": [view_uuid],
            "type": "rpc",
            "tid": 1,
        }],
        headers={"secureToken": csrf_token},
    )
    resp.raise_for_status()
    result = resp.json()
    if result[0].get("type") == "exception":
        raise RuntimeError(f"deleteView failed: {result[0].get('message')}")
    return result


def list_dashboards(s, host, csrf_token):
    """List all dashboards visible to the authenticated user."""
    resp = s.post(f"https://{host}/ui/dashboard.action", data={
        "mainAction": "getDashboardList",
        "secureToken": csrf_token,
        "currentComponentInfo": "TODO",
        "globalDate": json.dumps({"dateRange": "last6Hour"}),
    })
    resp.raise_for_status()
    return resp.json()["dashboards"]


def logout(s, host):
    """Invalidate the UI session."""
    s.get(f"https://{host}/ui/login.action", params={"mainAction": "logout"},
          allow_redirects=False)
```

## Stranded test artifacts

The investigation on 2026-04-10 created one dashboard that cannot be
deleted by the `claude` service account:

- `15b78a67-29f0-4066-bdb4-8a89d14c3c9b` — `__test_dash__`
  (locked=true, owner=admin). Requires admin login to delete.
- Test view `__test_view__` was successfully cleaned up via
  `viewServiceController.deleteView`.

## View delete limitation (VCF Ops 9.0.2 server bug)

Views cannot be deleted programmatically on VCF Ops 9.0.2 builds.
Both `viewServiceController.deleteView` (Ext.Direct) and
`DELETE /internal/viewdefinitions/{uuid}` return HTTP 500
"Internal Server error."

**The previous "duplicate subjects" explanation in this file was
wrong.** The 2026-04-11 follow-up investigation in
`context/view_report_delete_investigation.md` empirically falsified
it by (a) healing the duplicate via content-zip force-reimport with a
single `<SubjectType>` (which did normalize the `subjects` field to
one entry) and then still getting HTTP 500 on delete, and (b)
observing the same HTTP 500 when deleting the **nil UUID**
(`00000000-0000-0000-0000-000000000000`), proving the route handler
crashes before it even looks up the target.

**Actual root cause:** unknown, but the server's view-delete handler
is fundamentally broken on 9.0.2 builds. Every mutating method on
the Ext.Direct `viewServiceController`
(`deleteView`, `saveOrUpdateViewDefinition`, `getViewDataById`)
returns `type: "exception"` for all inputs, while read-only methods
(`getGroupedViewDefinitionThumbnails`, `getViewDefinitionThumbnails`)
continue to work.

**What the SPA UI calls — verified.** The SPA's Manage > Views page
calls the same Ext.Direct `viewServiceController.deleteView` RPC
that install.py's `UIClient.delete_view` already uses. There is no
secret "SPA-only" view delete endpoint hiding anywhere on the REST or
Ext.Direct surface — the 2026-04-11 investigation exhaustively
probed `DELETE|POST` against
`/suite-api/api/views/{id}`, `/suite-api/api/viewdefinitions/{id}`,
`/suite-api/api/view-definitions/{id}`, `/suite-api/internal/views/{id}`,
`/suite-api/internal/view-definitions/{id}`,
`/suite-api/internal/viewdefinitions/{id}` (+ `?id=…` query form),
`POST /…/delete` batch variants, and
`POST /suite-api/{api,internal}/content/operations/delete`, with
every plausible unsupported-header variant and flag
(`force|cascade|ignoreConstraints|ignoreErrors=true`). Only the
routes at `/suite-api/internal/viewdefinitions/{id}` and its Ext.Direct
equivalent are live — and both return 500 on every input.

**Workaround (unreliable):** delete views manually via the VCF
Operations web console (Environment → Views → right-click → Delete).
Whether this actually works on any given 9.0.2 build is unverified
from this investigation because the SPA itself is 404 on the lab
instance we test against. On builds where the web UI's delete button
works, it is hitting the same broken `deleteView` RPC — so if you
reproduce the 500 there, you're stuck until VMware ships a patch.

**Impact on install scripts:** The uninstall phase reports a WARN
for each view that cannot be deleted and exits with code 2 (partial
failure). SM, dashboard, custom group, symptom, and alert deletion
still succeed. The install scripts document this limitation in their
output. See the "Report delete" note below for the equivalent
situation on `reportdefinitions`.

**Impact on CLI sync:** The `vcfops_dashboards` sync handler imports
views via the same content-zip path. Views synced this way will also
be undeletable via the API. Manual cleanup through the web console
is required when removing synced views, subject to the caveat above.

## Report delete limitation (VCF Ops 9.0.2 server bug)

Same build, same shape of bug. Report definitions cannot be deleted
programmatically.

- `DELETE /api/reportdefinitions/{id}` — **500** (also 500 for the
  nil UUID, confirming route-handler crash). This is the only live
  REST delete route for reports on the public surface; there is no
  `/internal/reportdefinitions/*` route (404 on every probe).
- `POST /api/reportdefinitions/delete` and
  `DELETE /api/reportdefinitions?id=…` — both 500 (also live).
- Ext.Direct `reportServiceController.deleteReportDefinitions` —
  returns `type: "exception", message: "Internal server error."`.
- The entire `reportServiceController` is broken on this build:
  `getReportDefinitionThumbnails` also 500s for every parameter
  shape, which means the SPA's Manage > Reports list view itself
  likely renders empty or errors out. Data still reachable via
  `GET /api/reportdefinitions` (public REST read works fine).

**What the SPA calls.** If the SPA's Manage > Reports page renders
at all, the "Delete" button calls
`reportServiceController.deleteReportDefinitions` — the same broken
RPC. There is no secret REST path (exhaustively probed 11 candidates
in the 2026-04-11 investigation).

**install.py has no `_uninstall_reports` helper.** Reports are
install-only in the current distribution packaging. A future tooling
change to add report uninstall would call a broken endpoint and must
log it as a WARN, not a hard fail. See the code pattern in
`context/view_report_delete_investigation.md`.

**Workaround:** manual cleanup via web console — but only if the
Manage > Reports page in the SPA even renders on your build. On the
9.0.2.0 build tested here it is unlikely to, because the backing
Ext.Direct list RPC is also 500.

**See also:** `context/view_report_delete_investigation.md` for the
full endpoint survey, duplicate-subjects hypothesis falsification,
heal-via-reimport side finding, and the 4 stranded test artifacts
on the lab instance.

## Supportability caveat

These are **unsupported internal UI endpoints** — not part of any
public API contract. They can change between VCF Ops releases without
notice. Tested against VCF Operations 9.0.2.0 build 25137838.
