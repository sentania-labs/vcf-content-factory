# Dashboard + view + report delete via UI action endpoints

## 2026-04-11 update: corrected data shapes; view and report delete confirmed working

**This section supersedes the "server bug" findings in
`context/view_report_delete_investigation.md` and
`context/view_delete_dependency_protocol.md`.**
Both of those files incorrectly concluded that view and report delete are
fundamentally broken at the server level. The root cause was wrong data shapes
in our client code, not a broken server handler.

### What actually happened

The prior investigation was calling `deleteView` with `"data": ["<uuid>"]` —
a bare UUID string in an array. That shape causes a handler crash returning
`{"type":"exception","message":"Internal server error."}`.

The correct shape, confirmed by the operator from browser network capture and
empirically verified 2026-04-11 by actually deleting 4 stranded items on the
lab instance, is:

```
"data": [{"viewDefIds": "[{\"id\":\"<uuid>\",\"name\":\"<name>\"}]"}]
```

`viewDefIds` is a JSON-stringified array of `{id, name}` objects, nested inside
a dict, inside the outer data array. The `name` field is required — the handler
uses it (presumably for audit/display).

### URL: the legacy path is correct

The operator's hypothesis was that `/ui/vcops/services/router` is dead and the
live SPA context is at `/vcf-operations/plug/ops/vcops/services/router`.
Empirical testing shows the opposite on the lab instance:

- `/ui/vcops/services/router` — **works** for all operations (list, delete views,
  list reports, delete reports). JSESSIONID cookie scoped to `/ui` is sent here.
- `/vcf-operations/plug/ops/vcops/services/router` — returns **HTTP 400** (empty
  body). The JSESSIONID cookie is scoped to `/ui`, not `/vcf-operations/`, so
  this context rejects the request. The session does contain a second JSESSIONID
  scoped to `/vcf-operations/plug/ops` (set by the login flow) but it carries
  different credentials and the Ext.Direct handler requires a valid UI session.

**Conclusion: keep using `/ui/vcops/services/router`. Do not change the URL.**

### Confirmed working data shapes (2026-04-11)

#### View delete — `viewServiceController.deleteView`

```json
POST /ui/vcops/services/router
secureToken: <csrf>

[{
  "action": "viewServiceController",
  "method": "deleteView",
  "data": [{"viewDefIds": "[{\"id\":\"<uuid>\",\"name\":\"<name>\"}]"}],
  "type": "rpc",
  "tid": <n>
}]
```

- `data` is an **array** containing one dict
- `viewDefIds` value is a **JSON-stringified** array of `{id, name}` objects
- Supports batch delete by putting multiple `{id, name}` entries in the inner array
- Success response: `{"type":"rpc","result":[]}` (empty result list = success)
- Not-found response: also `{"type":"rpc","result":[]}` (silent no-op)
- Wrong shape (bare UUID): `{"type":"exception","message":"Internal server error."}`

#### View list — `viewServiceController.getGroupedViewDefinitionThumbnails`

Shape unchanged. The prior code was already correct for this method.

#### Report delete — `reportServiceController.deleteReportDefinitions`

```json
POST /ui/vcops/services/router
secureToken: <csrf>

[{
  "action": "reportServiceController",
  "method": "deleteReportDefinitions",
  "data": {"reportDefIds": "[{\"id\":\"<uuid>\",\"name\":\"<name>\"}]"},
  "type": "rpc",
  "tid": <n>
}]
```

**Critical difference from view delete:** `data` is a **bare dict**, NOT wrapped
in an array. Compare:
- Views: `"data": [{"viewDefIds": "..."}]`  (array of one dict)
- Reports: `"data": {"reportDefIds": "..."}`  (bare dict)

Success response: `{"type":"rpc"}` — no `"result"` key at all.

#### Report list — `reportServiceController.getReportDefinitionThumbnails`

```json
[{
  "action": "reportServiceController",
  "method": "getReportDefinitionThumbnails",
  "data": [{
    "contentFilter": {"isTenant": false},
    "resourceContext": null,
    "page": 1, "start": 0, "limit": 500,
    "sort": [{"property": "creationTime", "direction": "DESC"}]
  }],
  "type": "rpc",
  "tid": <n>
}]
```

Response structure:
```json
{"type":"rpc","result":{"records":[{"id":"...","name":"..."},...], "total": N, ...}}
```

Parse as `result[0]["result"]["records"]`.

### Header case

`secureToken` (camelCase) and `securetoken` (lowercase) both work. HTTP headers
are case-insensitive per RFC 7230. The code uses `secureToken` — leave it.

### Stranded items cleaned up

The 4 stranded views and reports from prior api-explorer investigations were
deleted successfully using the fixed client on 2026-04-11:
- View `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a` — DELETED
- View `36ff8c15-e47d-4285-b0f3-3ce9dda00ae6` — DELETED
- Report `02fb7e8e-e14e-4cdb-853f-367ce097bc47` — DELETED
- Report `f524e76b-67aa-4092-a49b-6c742e45ad4f` — DELETED

---

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
  "data": [{"viewDefIds": "[{\"id\":\"<uuid>\",\"name\":\"<name>\"}]"}],
  "type": "rpc",
  "tid": 1
}]
```

**IMPORTANT (2026-04-11 correction):** The `data` field is an array containing
one dict. The dict has key `viewDefIds` whose value is a **JSON-stringified**
array of `{id, name}` objects. Both `id` and `name` are required. Sending a
bare UUID string (the shape the prior code used) causes the handler to crash
and return `{"type":"exception","message":"Internal server error."}`.

- `tid` is a transaction ID (monotonically increasing integer per
  session; any positive integer works).
- `secureToken` goes as an **HTTP request header** (not in the JSON
  body and not as a query parameter).
- Success: HTTP 200, body is `[{"type":"rpc","result":[]}]` (empty result list).
- Deleting a non-existent UUID is a **silent no-op** (same success response).
- Wrong data shape returns `{"type":"exception","message":"Internal server error."}`.
- Multiple views can be batched by putting more `{id, name}` entries in the
  inner `viewDefIds` array.

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

Confirmed at the time of the original investigation: even when the
dashboard.json payload contains `"locked": false`, the server sets
`locked: true` after import. This was consistent across both new and
updated dashboards in earlier builds.

**2026-04-11 update:** During qa-tester acceptance of the multi-bundle
refactor, a dashboard imported via content-zip was observed with
`locked: false` in the post-install `getDashboardList` response —
contradicting the above. Delete succeeded regardless (via the
corrected `deleteTab` shape in the 2026-04-11 correction). The
`locked` state may vary by VCF Ops build, by import envelope details,
or by whether the calling user matches the stamped owner UUID.
**Do not trust `locked` as an absolute signal for troubleshooting** —
check empirically. The admin-user guard for UI-session delete still
applies as a safety baseline regardless of the observed lock state.

### getDashboardList response fields

Each dashboard entry includes:
- `id`, `name`, `description`
- `locked` (bool) — historically server-enforced true after content-zip
  import, but see 2026-04-11 note above — may be false in newer builds
- `owner` (string) — username of owner, typically "admin" after import
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


def delete_view(s, host, csrf_token, view_uuid, view_name, verify_ssl=False):
    """Delete a view by UUID+name via Ext.Direct.

    IMPORTANT: data shape requires viewDefIds with JSON-stringified {id,name}.
    Sending a bare UUID causes "Internal server error." exception response.
    """
    json_payload = json.dumps([{"id": view_uuid, "name": view_name}])
    resp = s.post(
        f"https://{host}/ui/vcops/services/router",
        json=[{
            "action": "viewServiceController",
            "method": "deleteView",
            "data": [{"viewDefIds": json_payload}],
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

## View delete — working as of 2026-04-11 correction

**The "view delete is broken" finding from prior investigations was WRONG.**
See the correction section at the top of this file for the full story.

`viewServiceController.deleteView` on `/ui/vcops/services/router` works when
the correct data shape is used (see "Confirmed working data shapes" above).

`DELETE /internal/viewdefinitions/{uuid}` and REST paths remain broken (HTTP
500) — these were correctly identified as dead ends. But the Ext.Direct path
is the right one and it works.

**Impact on install scripts:** `_uninstall_views` now works end-to-end.
The uninstall phase will delete views via the admin UI session. Requires
`--user admin`.

## Report delete — working as of 2026-04-11 correction

**The "report delete is broken" finding from prior investigations was also WRONG.**

- `reportServiceController.deleteReportDefinitions` on `/ui/vcops/services/router`
  **works** with the correct data shape (bare dict, not array — see above).
- `reportServiceController.getReportDefinitionThumbnails` also works.
- The REST routes `DELETE /api/reportdefinitions/{id}` etc. remain 500 — those
  are dead ends on this build but the Ext.Direct path works.

**install.py `_uninstall_reports` has been added** in the 2026-04-11 tooling
fix. Reports are now uninstallable via the admin UI session alongside views
and dashboards.

**See also:** `context/view_report_delete_investigation.md` for the original
(now-corrected) endpoint survey and the stranded item cleanup notes.

## Supportability caveat

These are **unsupported internal UI endpoints** — not part of any
public API contract. They can change between VCF Ops releases without
notice. Tested against VCF Operations 9.0.2.0 build 25137838.
