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

## Supportability caveat

These are **unsupported internal UI endpoints** — not part of any
public API contract. They can change between VCF Ops releases without
notice. Tested against VCF Operations 9.0.2.0 build 25137838.
