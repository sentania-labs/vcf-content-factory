# VCF Operations API surface — authoritative map

Drained 2026-04-17 against `vcf-lab-operations.int.sentania.net`
(VCF Operations 9.0.2.0 build 25137838, "VCF Operations" edition
`ENTERPRISE`, auth source `VCF SSO` / `VIDB` with a local shadow).

Supersedes URL-prefix claims in `context/pak_install_api_exploration.md`,
`context/pak_uninstall_api_exploration.md`, `context/pak_ui_upload_investigation.md`,
`context/struts_import_endpoints.md`, and the `project_vcf_operations_url_structure.md`
memory note, in cases where the earlier docs assumed `/vcf-operations/plug/ops/*.action`
is a live alias for `/ui/*.action`. **It is not, on this lab, for local-account auth.**
See §"Superseded docs" at the bottom for the exact corrections needed.

---

## Executive summary

1. **There is no single "VCF Operations" URL surface.** The hostname
   `vcf-lab-operations.int.sentania.net` exposes four distinct
   HTTP surfaces sitting behind a single Apache reverse proxy:
   - `/ui/*` — legacy ExtJS 6 SPA + its Struts backend (`*.action`,
     `secureToken` CSRF in form body, `OPS_SESSION` cookie carries
     CSRF as base64-JSON, `JSESSIONID` scoped to `/ui` and
     `/vcf-operations/plug/ops`). Accepts local-account login at
     `POST /ui/login.action`.
   - `/admin/*` — Clarity-based admin SPA + its Struts backend
     (`*.action`, `secureToken` from
     `/admin/commonJS.action?mainAction=getApplicationGlobalData`,
     separate JSESSIONID scoped to `/admin`). Accepts local-account
     login at `POST /admin/login.action`.
   - `/suite-api/api/*` and `/suite-api/internal/*` — REST (public
     and unsupported), authenticated with an `OpsToken` bearer
     token. This is the contract the OpenAPI specs in `docs/*.json`
     describe.
   - `/vcf-operations/*` — the new "VCF merged console" root. On
     this lab it is an Apache reverse-proxy alias for the Ops
     backend **gated by VCF SSO (VIDB) OAuth2**. Local-account
     credentials alone are NOT sufficient to reach any path under
     this prefix — a browser-driven federation flow through
     `vcf-lab-vcenter-mgmt.int.sentania.net/acs/t/CUSTOMER/authorize`
     is required.

2. **`/vcf-operations/plug/ops/*.action` is NOT a live sibling of `/ui/*.action`
   for programmatic clients.** Every unauthenticated hit on
   `/vcf-operations/*` 302s to `/ui/login.action?vcf=1`, and every
   authenticated hit using a `/ui/`-obtained JSESSIONID returns an
   empty HTTP 400 with Set-Cookie headers that actively DELETE the
   `/ui/` session. Scott's browser captures that show URLs under
   `/vcf-operations/plug/ops/*.action` working came from a session
   that had completed VIDB SSO — an OIDC auth_code handshake that a
   headless client can't replicate without IdP creds and the OAuth
   client secret.

3. **Auth mechanism matrix:**

   | Surface | Cookies required | CSRF mechanism | Credentials |
   |---|---|---|---|
   | `/ui/*.action` | `JSESSIONID` path=`/ui` + `OPS_SESSION` path=`/vcf-operations` | `secureToken` form field | `POST /ui/login.action` username+password |
   | `/admin/*.action` | `JSESSIONID` path=`/admin` | `secureToken` from `/admin/commonJS.action mainAction=getApplicationGlobalData` | `POST /admin/login.action` username+password |
   | `/suite-api/api/*` | none (token) | not applicable | `OpsToken` bearer from `POST /suite-api/api/auth/token/acquire` |
   | `/suite-api/internal/*` | none (token) | not applicable | same token, PLUS `X-Ops-API-use-unsupported: true` header |
   | `/vcf-operations/*` (this lab) | VIDB OIDC session cookies from `vcf-lab-vcenter-mgmt.int.sentania.net` | unknown without interactive SSO | OAuth2 authorization_code flow via `/acs/t/CUSTOMER/authorize` — not reproducible with local creds alone |

4. **`/ui/solution.action`, `/ui/utility.action`, `/ui/clusterManagement.action`,
   and `/ui/stateManager.action` are live Struts handlers** the 2026-04-11
   enumeration missed. `/ui/resource.action` and `/ui/resourceKind.action`
   are also registered (only `getResourceKinds` returns JSON; the rest
   errorPanel-out). Confirmed mainAction surface for each is catalogued below.

5. **Pak lifecycle is fully scriptable via the `/ui/` Struts layer**, not
   under `/vcf-operations/`. The `vcfops_managementpacks/installer.py`
   URL choices (all `/ui/` or `/suite-api/`) are correct. No URL-prefix
   rewrite is needed.

6. **The MP Builder REST API exists and responds to token auth at
   `/suite-api/internal/mpbuilder/designs`** (NOT `/vcf-operations/rest/
   ops/internal/mpbuilder/*`). Zero `mpbuilder` paths in either
   OpenAPI spec — it's entirely undocumented. The `designs` resource
   has a status/source/events/install sub-surface plausibly sufficient
   to generate an installable pak from a declarative design, but an
   INCOMPLETE design is the only existing data point on this lab and
   going further requires mutation (create → populate → build →
   install → poll), which Scott has not authorized yet. See §MPB deep
   dive and §ADAPTER_JAR_GAP below.

7. **Recon goldmines discovered or confirmed:**
   - `/ui/solution.action mainAction=getIntegrations` (592 KB JSON) —
     full installed+available MP catalogue, every field `ops-recon`
     could ever need for "is this MP installed", "is it removable",
     "who provides it", "what adapter kind does it register".
   - `/ui/solution.action mainAction=getAdapterTypes` (44 KB JSON) —
     `integratedAccountTypes[]` with `adapterKindName`, `configurable`,
     `isCloudProxyRequired`, per-adapter licence/flag info.
   - `/ui/solution.action mainAction=getGroupedAccounts` (16 KB JSON) —
     per-adapter instance count / grouping.
   - `/ui/solution.action mainAction=getDetectedAdapterKinds`,
     `mainAction=getOverview`.
   - `/ui/resourceKind.action mainAction=getResourceKinds` — subset
     of `/suite-api/api/adapterkinds` but accessible from UI session.
   - `/ui/clusterManagement.action mainAction=getNodes` — node list
     (minimal shape: `nodeName`, `nodeAddress`, `id`, `webServer` bool).
   - `/ui/clusterManagement.action mainAction=isPakInstalling` —
     one-shot `{isPakInstalling, isPakUninstallActive}` boolean.
     Cleaner than polling `solution.action` `getLatestInstalledSolutionStatuses`
     when all we need is "is ANY pak op in flight".

8. **`/suite-api/internal/*` paths that the OpenAPI spec claims, but
   DO NOT EXIST on 9.0.2:** `/internal/adapterkinds`,
   `/internal/credentials`, `/internal/supermetrics`,
   `/internal/customgrouptypes`, `/internal/resources/properties` all
   return 404. Presumably later-version additions the internal spec
   is tracking ahead of the implementation, or moved-elsewhere. Not
   currently a blocker.

9. **`/suite-api/api/events` returns 500 on a simple GET** against
   this lab. Not pursued (likely needs query params `resourceId` /
   `startTime`). Flagging as a recon rough edge.

10. **`/suite-api/api/dashboards` returns 404** — as already known
    (`content_api_surface.md`), dashboards have no public REST CRUD
    endpoint; content-zip is the only route. Confirmed still true.

---

## Authentication flows (exact reproducible sequences)

### /ui/ session — local account

```python
s = requests.Session(); s.verify = False
# 1. Seed cookies
s.get(f"https://{HOST}/ui/login.action?vcf=1")
# 2. POST credentials (no CSRF needed on this call)
r = s.post(f"https://{HOST}/ui/login.action", data={
    "mainAction": "login",
    "userName":   USER,
    "password":   PWD,
    "authSourceId":   "localItem",      # for a local VCF Ops account
    "authSourceName": "Local Account",
    "authSourceType": "",
    "forceLogin":     "false",
    "timezone":       "0",              # minutes offset from UTC
    "languageCode":   "us",
})
assert r.text.strip() == "ok"
# 3. Extract CSRF + OPS_SESSION cookie
s.get(f"https://{HOST}/ui/index.action", allow_redirects=False)
ops_session = s.cookies.get("OPS_SESSION", path="/vcf-operations")
data = json.loads(base64.b64decode(ops_session))
csrf = data["csrfToken"]
# Session state per cookie jar:
#   JSESSIONID=<hex> path=/ui
#   JSESSIONID=<hex> path=/vcf-operations/plug/ops  (same value)
#   OPS_SESSION=<base64-json> path=/vcf-operations
# The OPS_SESSION payload decodes to:
#   { isDark, timePreference, ipfOptIn, opsPlatformSessionId,
#     hostTimezoneOffset, userName, locale, userId,
#     opsTrackerId, inactivityTimeout, csrfToken,
#     allowChangePassword, opsUISessionId }
# csrfToken goes as a `secureToken` form field on every *.action POST.
```

**Logout:** `GET /ui/login.action?mainAction=logout` (returns 302).
Also releases the JSESSIONID the Apache proxy issued.

### /admin/ session — local account (admin privilege required)

```python
s = requests.Session(); s.verify = False
s.get(f"https://{HOST}/admin/login.action")   # seed
r = s.post(f"https://{HOST}/admin/login.action", data={
    "mainAction": "login",
    "userName":   ADMIN,                 # must be the `admin` local user
    "password":   ADMIN_PW,
})
assert r.text.strip() == "ok"
g = s.get(f"https://{HOST}/admin/commonJS.action",
          params={"mainAction": "getApplicationGlobalData"})
csrf = g.json()["secureToken"]
# Session state: JSESSIONID scoped to /admin ONLY.
```

### /suite-api/ REST — bearer token

```python
r = requests.post(f"https://{HOST}/suite-api/api/auth/token/acquire",
    json={"username": USER, "password": PWD, "authSource": "Local"},
    headers={"Content-Type": "application/json",
             "Accept":       "application/json"},
    verify=False)
token = r.json()["token"]
# Use:
headers = {"Authorization": f"OpsToken {token}",
           "Accept":        "application/json"}
# For /internal/* endpoints, ADD:
headers["X-Ops-API-use-unsupported"] = "true"
# Release when done:
requests.post(f"https://{HOST}/suite-api/api/auth/token/release",
              headers=headers, verify=False)
```

`authSource` values on this lab:
- `Local` — the local VCF Ops user store (`id=localItem`, name "Local Account")
- `VCF SSO` — the VIDB federation (`id=841fafcb-445e-4b16-9634-f09480f1836b`, sourceType.id `VIDB`)

### /vcf-operations/* — VIDB OAuth2 (NOT automated here)

The auth flow the SPA drives:

```
1. User → GET https://vcf-lab-operations.int.sentania.net/vcf-operations/
         → 302 /ui/login.action?vcf=1
2. SPA loads /ui/login.action?vcf=1 with the "VCF SSO" login button
3. User clicks SSO → AJAX POST /ui/login.action mainAction=getVIDBRedirectUrl
   → response: {"success":true, "vidbRedirectURL":
       "https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/t/CUSTOMER/authorize
        ?response_type=code
        &client_id=22177924-c638-4350-a336-6941ca5161eb
        &redirect_uri=https://vcf-lab-operations.int.sentania.net/ui/vidbClient/vidb/
        &state=<base64(host)>"}
4. Browser → ACS authorize URL
   → 302 /federation/t/CUSTOMER/auth/login?dest=...
5. Browser → /vidb/login HTML form (user enters SSO creds)
   → POST form → federation sets cookies and issues OAuth code
6. Browser → redirect_uri with `?code=...&state=...`
   → /ui/vidbClient/vidb/ (Struts handler) exchanges code for token
7. Struts handler sets VCF-OPERATIONS auth cookies scoped to /vcf-operations/*
   that the Apache proxy validates on subsequent hits.
```

Completing this **headlessly** requires:
- SSO account credentials (possibly different from the local Ops user)
- The OAuth2 client_secret for client `22177924-c638-4350-a336-6941ca5161eb`
  (client_secret_basic or _post auth per the OIDC discovery document at
  `/acs/.well-known/openid-configuration`)
- Or cookie injection of a browser-established session (fragile).

**None of the above is present in env vars or the repo.** Every
capability that exists under `/vcf-operations/*` is also available
under `/suite-api/*` or `/ui/*.action` (confirmed by verifying the
MPB API at `/suite-api/internal/mpbuilder/designs` — the same path
Scott's captures showed under `/vcf-operations/rest/ops/internal/`).
So the `/vcf-operations/` prefix is currently a **UI-routing
convenience, not a distinct API contract.**

---

## `/ui/` Struts — registered handlers and mainAction surface

Probed 2026-04-17 with an authenticated `/ui/` session.

Registration check: garbage mainAction (`mainAction=__INVALID_ACTION__`):
- HTTP 200, ~1 KB `errorPanel` HTML: **registered, unknown mainAction**
- HTTP 200, empty body: **registered, silent fallthrough**
- HTTP 404: unregistered

### Live handlers (post-2026-04-17 remap)

| Action | Registered? | Notes |
|---|---|---|
| `/ui/dashboard.action` | yes (errorPanel) | content mgmt (list, config, clone, deleteTab, saveTab) |
| `/ui/alert.action` | yes (errorPanel) | most mainActions are stubs; probe per need |
| `/ui/resource.action` | yes (errorPanel) | **new find 2026-04-17** — mainActions unknown, all tested return errorPanel |
| `/ui/resourceKind.action` | yes (errorPanel) | **new find 2026-04-17** — `getResourceKinds` returns JSON |
| `/ui/superMetric.action` | yes (silent) | `getSuperMetrics` returns the full list |
| `/ui/customGroup.action` | yes (silent) | no live `getCustomGroups` found; `saveCustomGroup` is a no-op stub |
| `/ui/policy.action` | yes (silent) | `importPolicy` returns `{"success":false}` on empty body |
| `/ui/solution.action` | yes (silent) | full pak lifecycle + recon goldmine |
| `/ui/utility.action` | yes (silent) | `prepareFileUpload` |
| `/ui/clusterManagement.action` | yes (silent) | `isPakInstalling`, `getNodes` |
| `/ui/stateManager.action` | yes (silent) | `storeState` returns literal `ok` (not JSON) |
| `/ui/contentManagement.action` | yes (silent) | all tested mainActions empty |
| `/ui/index.action` | yes (HTML) | seeds OPS_SESSION cookie |
| `/ui/login.action` | yes (302) | login / logout / getVIDBRedirectUrl / getSsoRedirectUrl |
| `/ui/commonJS.action` | yes (JS) | serves a 116 KB JS bundle; `mainAction=getApplicationGlobalData` returns `{secureToken, isLoggedIn, ...}` — mirror of the `/admin/` helper |

### Unregistered (HTTP 404)

`view`, `viewDefinition`, `report`, `reportTemplate`, `alertDefinition`,
`symptom`, `symptomDefinition`, `recommendation`, `supermetric` (case),
`customgroup` (case), `integration`, `marketplace`, `repository`, `pak`,
`managementPack`, `softwareUpdate`, `upgrade`, `user`, `group`, `role`,
`privilege`, `license`, `licensing`, `adapter`, `adapterKind`, `collector`,
`node`, `content`, `uploadFile`, `importContent`, `import`, `export`,
`search`, `metric`, `property`, `scoreboard`, `topology`, `heatmap`,
`logout`, `common`, `session`, `administration`, `config`, `configuration`,
`settings`, `task`, `tasks`, `notification`, `notifications`,
`alertNotification`, `adapter-kind`, `adapterkind`, `solutionPack`,
`solutionpack`.

Many of these map to Ext.Direct controllers (`/ui/vcops/services/router`)
or to `/suite-api/` REST paths instead.

### mainAction inventory (verified 2026-04-17)

Only mainActions that return non-empty JSON are listed as **JSON**.
Empty-body returns are marked **EMPTY** (registered but either a no-op
or unknown mainAction). Returns listed in **ERRPANEL** are unknown
mainAction (the action is registered but this specific mainAction
isn't).

#### /ui/solution.action

| mainAction | Status | Response shape / notes |
|---|---|---|
| `getIntegrations` | JSON, 592 KB | `{availableMPs[], totalIntegrationsCount, installedMPs[], installationState, isUnsignedPakInstallationAllowed}`. Each MP has ~27 fields: `name, pakId, adapterKind, adapterKindName, version, isUnremovable, isInstalled, pakCategory, providedBy, description, icon, hasActionPrivilege, hasStatus, isAutoIntegrated, isCloudAccount, isConfigurable, isConfiguredByVmc, isContentOnly, isIntegration, isUCP, isUnsupported, isUpgradeAvailable, licenseConfigured, ootb, configuredAdaptersCount`. |
| `getGroupedAccounts` | JSON, 16 KB | `{groupedAccounts[], totalAccountCount, totalCount}` — per-adapter instance count breakdown. |
| `getAdapterTypes` | JSON, 44 KB | `{integratedAccountTypes[], installationState}`. Each entry: `{adapterKindName, configurable, hasLicense, icon, id, isCloudProxyRequired, isInstalled, pakCategory, showAdvanceLicenceMsg, showEnterpriseLicenceMsg, text, type}`. |
| `getDetectedAdapterKinds` | JSON | `{adapterKinds: [], allAdapterKindsInstalled: true}`. |
| `getOverview` | JSON, ~1 KB | `{metric: [], content: [{contentType:"Dashboards", content:[]}, {contentType:"Views"...}, ...]}` — lists content types + item counts from the last installed pak only. |
| `getPreview` | JSON | `{installationState, isUnsignedPakInstallationAllowed}`. |
| `getInstallStatus` | JSON | `{statuses[], completed}`. |
| `getLicenseAgreement` | JSON, needs `pakId=` | `{licenseText, errorMsg}`. |
| `getReleaseInfo` | EMPTY without `pakId=`; JSON with one | release notes. |
| `getLatestInstalledSolutionStatuses` | EMPTY without state | returns status JSON when pak is in flight. |
| `getSolutionVersion` | JSON, needs `solutionName=` | `{solutionVersion, success}`. |
| `getSolutionInfo` | JSON | `{success, errorMsg}`. |
| `getSolutionPakId` | JSON, needs `solutionName=` | `{}` on miss. |
| `loadSolution` | JSON | `{}` on empty; used in marketplace wizard. |
| `isInProgress` / `isPakInstalling` | EMPTY | poll boolean; same as `clusterManagement.action isPakInstalling` but marked EMPTY here — use that endpoint instead. |
| `installingPakDetail` | JSON | `{}` on idle. |
| `install` | — | start install, needs `pakId=`. |
| `remove` | — | uninstall, needs `pakId=` (short form) + `version=`. |
| `enable` / `disable` | — | solution enable/disable, needs `pakId=`. |
| `reinstall` / `cancel` / `finishStage` / `resetSolutionUninstallState` | — | lifecycle helpers. |
| `getSolutionsAndAdaptersList` (with `mode=solution` etc) | JSON, 1.5 KB | returns `{groupTypes, metricInstanceGroupType}` — **NOT the rich inventory Scott's captures may have suggested**; `mode` param seems to not alter the shape. Small and not particularly useful. **Revise expectations**: this mainAction on `/ui/solution.action` is not the recon-friendly endpoint the brief hypothesised. `getIntegrations` is what you want. |
| `getContent` | ERRPANEL | likely needs mode/filter params. |
| `getOrgDetails` / `isPakDownloading` / `checkSolutionAdapterInstancesExist` | ERRPANEL | |
| `getReclaimableVms` / `getRightsizingVMs` | EMPTY | need context. |

#### /ui/utility.action

| mainAction | Status | Notes |
|---|---|---|
| `prepareFileUpload` | JSON `{"success":true}` | idempotent; call before multipart upload. |
| `updateTelemetryAccess` | EMPTY | accepted, no response body. |

#### /ui/clusterManagement.action

| mainAction | Status | Notes |
|---|---|---|
| `isPakInstalling` | JSON | `{"isPakInstalling":false,"isPakUninstallActive":false}` — the preferred polling endpoint. |
| `getNodes` | (text/html but JSON body) | `[{"nodeName":"vcf-lab-operations","webServer":true,"id":"<uuid>","nodeAddress":"<fqdn>"}]`. |
| `isClusterStateInTransition`, `getLCMNodeStatus`, `getClusterState`, `getNodeStatus`, `getMasterInfo`, `getClusterInfo`, `isMaintenanceMode` | EMPTY | registered but empty on bare request; may need params. |

#### /ui/resourceKind.action

| mainAction | Status | Notes |
|---|---|---|
| `getResourceKinds` | JSON, 23 bytes | `{"resourceKindList":[]}` — empty on this lab, shape confirmed. |

#### /ui/superMetric.action

| mainAction | Status | Notes |
|---|---|---|
| `getSuperMetrics` | JSON, 43 KB | `{superMetrics[], totalCount}`. |

#### /ui/dashboard.action

| mainAction | Status | Notes |
|---|---|---|
| `getDashboardList` | JSON, 104 KB | `{dashboards[]}` |
| `getDashboardConfig` | JSON, 880 KB | `{interactionTypes, dashboardConfig}` |
| `deleteTab`, `saveTab`, `cloneDashboard` | — | already documented in `context/dashboard_delete_api.md`. |
| `uploadDashboard` | — | dead stub (see `struts_import_endpoints.md`). |

#### /ui/stateManager.action

| mainAction | Status | Notes |
|---|---|---|
| `storeState` | 2-byte `ok` (text/html) | UI preference persistence. Not JSON. |

### Callable only with parameters (not probed bare)

`install`, `remove`, `enable`, `disable`, `getLicenseAgreement`, etc.
Documented in `pak_install_api_exploration.md` and
`pak_uninstall_api_exploration.md`; no URL-prefix change needed.

---

## `/admin/` Struts — registered handlers

Probed with admin session:

- `/admin/index.action` — SPA shell (HTML)
- `/admin/login.action` — login / logout
- `/admin/commonJS.action` — `getApplicationGlobalData` returns `{secureToken, isLoggedIn, ...}` + the commonJS bundle
- `/admin/solution.action` — pak lifecycle (same mainAction surface as `/ui/solution.action`; SPA code is literally the same)
- `/admin/utility.action` — `prepareFileUpload`
- `/admin/softwareUpdate.action` — registered, mainActions unexplored
- `/admin/clusterManagement.action` — registered, mainActions unexplored

Unregistered (HTTP 404 on `/admin/*.action`): `dashboard`, `view`,
`report`, `alert`, `superMetric`, `customGroup`, `policy`, `resource`,
`resourceKind`, `stateManager`, `contentManagement`, and the long tail.

The admin SPA is a stripped-down "cluster & solution admin only"
console — it does not own content management.

---

## `/suite-api/` REST — verified coverage

From the OpenAPI specs in `docs/operations-api.json` (250 paths) and
`docs/internal-api.json` (180 paths). The specs both declare base
URL `/suite-api` — so paths are `/suite-api/api/*` (public) and
`/suite-api/internal/*` (unsupported).

### Public spec — coverage by prefix

```
api/resources              46  (CRUD, relationships, stats, properties)
api/auth                   33  (token acquire/release, users/groups/roles)
api/applications           20
api/integrations           13  (adapter/plugin mgmt)
api/policies               10
api/alerts                 10
api/optimization            8
api/deployment              8
api/chargeback              8
api/content                 8  (content import/export/operations)
api/adapterkinds            8
api/alertplugins            7
api/adapters                7
api/logs                    5
api/alertdefinitions        5
api/reportdefinitions       4
api/notifications           4
api/credentials             4
api/collectors              4
api/events                  4
api/collectorgroups         3
api/reports                 3
api/actions                 3
api/solutions               3
api/product                 3
api/symptomdefinitions      2
api/supermetrics            2
api/recommendations         2
api/symptoms                2
api/versions                2
api/tasks                   2
api/maintenanceschedules    1
api/costconfig              1
api/certificate             1
api/credentialkinds         1
api/configurations          1
api/audit                   1
api/actiondefinitions       1
```

### Internal spec — coverage by prefix

```
internal/costdrivers          36
internal/resources            17
internal/license-manager      10
internal/auth                  9
internal/cloudproxies          8
internal/actions               8
internal/integrations          7
internal/vcenterlinking        6
internal/proxies               6
internal/licenses              6
internal/applications          6
internal/tagmanagement         5
internal/metering              5
internal/solutions             5
internal/policies              5
internal/optimization          5
internal/datastreams           4
internal/whatif                3
internal/supermetrics          3   (includes /internal/supermetrics/assign)
internal/vmc                   3
internal/adapterkinds          3
internal/symptomdefinitions    2
internal/service               2
internal/physicaldatacenters   2
internal/loginsight            2
internal/adapters              2
internal/costcalculation       2
internal/alertplugins          2
internal/management            1
internal/servertag             1
internal/agent                 1
internal/views                 1
internal/product               1
internal/events                1
```

**`mpbuilder` is in NEITHER spec.** It's fully undocumented.

### Sample endpoints verified live

| Method | Path | Result |
|---|---|---|
| GET | `/suite-api/api/versions/current` | 200, `{releaseName:"VCF Operations 9.0.2.0", major:2, minor:2, buildNumber:25137838}` |
| GET | `/suite-api/api/auth/currentuser` | 200, user object |
| GET | `/suite-api/api/auth/sources` | 200, `{sources:[{Local Account VIDB ACTIVE...}, {VCF SSO VIDB ACTIVE...}]}` |
| GET | `/suite-api/api/solutions` | 200, 17 solutions |
| GET | `/suite-api/api/adapterkinds` | 200, 26 adapter kinds |
| GET | `/suite-api/api/resources?pageSize=1` | 200, totalCount=2742 |
| GET | `/suite-api/api/supermetrics` | 200, totalCount=61 |
| GET | `/suite-api/api/symptomdefinitions` | 200, totalCount=2217 |
| GET | `/suite-api/api/alertdefinitions` | 200, totalCount=1491 |
| GET | `/suite-api/api/reportdefinitions` | 200, totalCount=89 |
| GET | `/suite-api/api/policies` | 200, 10+ policies |
| GET | `/suite-api/api/collectors` | 200, 1 internal collector |
| GET | `/suite-api/api/collectorgroups` | 200, "Default collector group" |
| GET | `/suite-api/api/product/licensing/edition` | 200, `{"productLicensingEdition":"ENTERPRISE"}` |
| GET | `/suite-api/api/dashboards` | 404 (no public dashboards endpoint — known) |
| GET | `/suite-api/api/actions` | 404 (moved/renamed; `actiondefinitions` exists instead) |
| GET | `/suite-api/api/events?pageSize=1` | 500 "Internal Server error" (needs query params) |
| GET | `/suite-api/internal/mpbuilder/designs` | 200, 1 design summary — **undocumented, MPB API** |
| GET | `/suite-api/internal/solutions/preinstalled` | 200, preinstalled solution catalog |
| GET | `/suite-api/internal/adapterkinds` | 404 (spec lists it but it doesn't exist on 9.0.2) |
| GET | `/suite-api/internal/credentials` | 404 (spec claims it exists but doesn't on 9.0.2) |
| GET | `/suite-api/internal/supermetrics` | 404 (only `/internal/supermetrics/assign` POST exists) |
| GET | `/suite-api/internal/customgrouptypes` | 404 (use `/api/resources/groups` for live custom groups) |
| GET | `/suite-api/internal/resources/properties` | 404 |
| GET | `/vcf-operations/rest/ops/api/versions/current` | 302 → `/ui/login.action?vcf=1` (VIDB gated) |

**X-Ops-API-use-unsupported header is case-insensitive** — both
`x-ops-api-use-unsupported: true` and `X-Ops-API-use-unsupported: true`
work. Use the canonical capitalisation in code for clarity.

---

## MP Builder deep dive (`/suite-api/internal/mpbuilder/*`)

### Endpoints

| Method | Path | Result |
|---|---|---|
| GET | `/suite-api/internal/mpbuilder/designs` | list of design summaries |
| GET | `/suite-api/internal/mpbuilder/designs/{id}` | compact design metadata |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/status` | section-by-section status + errors |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/source` | full design source (422 if not yet populated) |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/events` | `{eventSummaries:[]}` |
| POST | `/suite-api/internal/mpbuilder/designs` | create a new design (POST body `{id:null, name, description}` per Scott's captures) |
| POST | `/suite-api/internal/mpbuilder/designs/{id}/install` | install the design's resulting pak (500 on incomplete design) |
| POST/PUT/PATCH | various | per design section editing — not probed (requires mutation) |
| GET | `/suite-api/internal/mpbuilder` (root) | 404 (no listing) |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/build` | 404 |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/pak` | 404 |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/export` | 404 |
| GET | `/suite-api/internal/mpbuilder/designs/{id}/validate` | 404 |
| OPTIONS | any mpbuilder path | 403 (method not reflected) |

### Design schema (from `/designs/{id}/status`)

```
{
  "status": "INCOMPLETE",
  "installStatus": "DRAFT",        // DRAFT|STAGED|INSTALLED|REMOVED?
  "designInfo":     { errors[], itemCount },
  "source":         { errors[], itemCount },   // the REST data source spec
  "requests":       { errors[], itemCount },   // HTTP request templates
  "objects":        { errors[], itemCount },   // resource-kind schema + metrics/props
  "events":         { errors[], itemCount },   // event mapping
  "relationships":  { errors[], itemCount },   // parent-child mapping
  "configuration":  { errors[], itemCount }    // adapter instance config schema
}
```

The "my MP" design on this lab is INCOMPLETE with one error:
`{"error":"Design must contain configured source"}` in `source.errors`.

### Lifecycle (inferred from the SPA route + status schema)

```
1. POST /mpbuilder/designs        → create empty design, returns {id}
                                    SPA route: /ui/developer-center/pack-builder/designs/{id}/source
2. PUT/POST .../designs/{id}/source        → configure the data source
                                              (host, port, path, auth, TLS, sample req/resp)
3. PUT/POST .../designs/{id}/requests      → define HTTP request templates
4. PUT/POST .../designs/{id}/objects       → map responses to resource kinds with metrics/props
5. PUT/POST .../designs/{id}/relationships → define parent/child relationships
6. PUT/POST .../designs/{id}/events        → map conditions to events
7. PUT/POST .../designs/{id}/configuration → adapter instance config schema
8. POST .../designs/{id}/install           → build and install the generated pak
   Status transitions: INCOMPLETE → COMPLETE (build OK) → DRAFT → STAGED → INSTALLED
```

Editing endpoints (steps 2-7) not probed — requires write access.
The `SPA route` key in the developer center routes config is
`ui/developer-center/pack-builder`, confirming this is the
Management Pack Builder feature (requires `ui.vcf_developercenter.mpbuilder`
privilege, admin-gated).

### ADAPTER_JAR_GAP — verdict

**Strong indication (not yet confirmed by end-to-end build):** the MPB
API produces a declarative-REST-poll MP whose runtime adapter is
generic and bundled into the pak. It does NOT require a hand-coded
Java JAR.

Evidence:
- Design schema fields are HTTP-centric (`source`, `requests`) —
  meant for REST/JSON data sources.
- The `install` endpoint directly installs the generated pak
  (no separate "export JAR" step, no "upload JAR" step).
- An existing MP-Builder-authored community pack on this lab —
  `iSDK_VCFOperationsvCommunity` with adapter kind
  `VCFOperationsvCommunity` — is installed and runs without the
  operator providing a JAR. (It may still have been built with a
  JAR offline, but the installation path doesn't require one.)
- The pak naming convention `mpb_synology_dsm-X.Y.pak` used by the
  factory mirrors MPB output, suggesting MPB is the production path
  for "poll a REST API → Ops resource kinds" MPs.

**What's still unknown without mutation:**
- Whether an MPB-built pak bundles a generic adapter runtime JAR
  (same one for all MPB designs) or generates a bespoke one per design.
- Whether the MPB-built pak format matches `dist/mpb_synology_dsm.1.0.0.1.pak`
  byte-for-byte or has a different manifest structure.
- Whether Scott's existing YAML content (views, dashboards, super metrics)
  can be injected into an MPB design as-is, or needs re-authoring in the
  MPB design's `objects`/`relationships` sections.

**Recommended next experiment (requires Scott's authorization):**
create a minimal MPB design for Synology (delete before committing
to the repo), exercise the full lifecycle to the `INCOMPLETE → COMPLETE`
transition, and document the POST body shapes + pak output. Do NOT
install it; only verify the build step produces a valid artifact.

---

## Pak lifecycle — confirmed URLs and call shapes

All paths are under `/ui/` or `/admin/`, not `/vcf-operations/`.
This section supersedes `context/pak_install_api_exploration.md`
§"`/ui/*` Struts — dead stub" (which has already been corrected
there) and confirms the install+uninstall flows implemented in
`vcfops_managementpacks/installer.py`.

### Upload URL — confirmed by SPA bundle grep

Both SPAs (Clarity `/admin/` and ExtJS `/ui/`) bundle the same
upload code. The relative URL `admin/services/solution/upload`
resolves against whichever SPA context is serving, so:

```
POST /ui/admin/services/solution/upload?uploadId=<epoch_ms>
     &ignoreSignatureChecking=<true|false>   (on query string, NOT form body)
  multipart/form-data:
    solution=@<file>.pak
    forceUpload=<true|false>
    forceContent=<true|false>
    secureToken=<csrf>        (injected by Ext.form.Panel formActionHandler)

POST /admin/admin/services/solution/upload?uploadId=<epoch_ms>
  multipart/form-data:                  (admin-side; `ignoreSignatureChecking`
    solution=@<file>.pak                 here is in the FORM BODY, not query)
    forceUpload=false
    ignoreSignatureChecking=false
    currentComponentInfo=TODO
    secureToken=<csrf>
```

### Full lifecycle (using /ui/ session — what installer.py does today)

```
1. POST /ui/login.action             (+ seed via GET /ui/login.action?vcf=1)
2. GET  /ui/index.action             → OPS_SESSION cookie → decode for csrf
3. POST /ui/utility.action            mainAction=prepareFileUpload
4. POST /ui/admin/services/solution/upload?uploadId=<ms>&ignoreSignatureChecking=<bool>
        (multipart upload) → response { pakId (compressed), solutionName,
                                        solutionVersion, signingStatus, ... }
5. POST /ui/solution.action           mainAction=getLicenseAgreement pakId=<compressed>
6. POST /ui/solution.action           mainAction=install pakId=<compressed> forceContent=true
7. (poll) POST /ui/clusterManagement.action mainAction=isPakInstalling
                     → {"isPakInstalling":true/false, "isPakUninstallActive":true/false}
   OR
   (poll) POST /ui/solution.action   mainAction=getLatestInstalledSolutionStatuses
                     → richer state (per-node, per-solution)
8. (uninstall) POST /ui/solution.action mainAction=getIntegrations
                     → find installedMPs[entry] where name matches target
                     → **HARD GUARD**: refuse if entry.isUnremovable=true (server does NOT enforce)
9.  POST /ui/solution.action           mainAction=remove pakId=<short form> version=<ver>
10. (poll) step 7 repeated until pak disappears from grid
11. GET /ui/login.action?mainAction=logout
```

`<compressed>` and `<short form>` are two different spellings of the
pak identity (e.g. `BroadcomSecurityAdvisories-1016` vs
`Broadcom Security Advisories`) — see `pak_uninstall_api_exploration.md`.
The upload endpoint returns `<compressed>`; `getIntegrations` is the
authoritative source for `<short form>`.

---

## Recon enablement — mapping endpoints to `ops-recon` questions

`ops-recon` routinely answers: "does X already exist", "is X
enabled", "does adapter Y exist on this instance", "what pak provides
Z". Below is the minimum endpoint set that answers each cheaply,
without REST-token indirection where an easier UI-session call
exists.

| Question | Best endpoint | Response key / field |
|---|---|---|
| What MPs are installed? | `/ui/solution.action mainAction=getIntegrations` | `installedMPs[].{name, pakId, version, adapterKind, isUnremovable, pakCategory, providedBy, configuredAdaptersCount}` |
| What MPs are available (not installed) in the marketplace? | same endpoint | `availableMPs[].{name, pakId, version, description}` |
| What adapter kinds exist on the instance? | `/suite-api/api/adapterkinds` | `adapter-kind[].{key, name, adapterKindType, ...}` |
| What adapter kinds does a given MP register? | correlation: `getIntegrations` → `installedMPs[].adapterKind` |
| Pak install/uninstall in progress? | `/ui/clusterManagement.action mainAction=isPakInstalling` | `{isPakInstalling, isPakUninstallActive}` (fast boolean) |
| Full pak lifecycle state per node? | `/ui/solution.action mainAction=getLatestInstalledSolutionStatuses` | richer grid; use when `isPakInstalling=true` to drill in |
| Adapter instances grouped by type | `/ui/solution.action mainAction=getGroupedAccounts` | `groupedAccounts[]` |
| Adapter type catalogue (licence / cloud-proxy needs) | `/ui/solution.action mainAction=getAdapterTypes` | `integratedAccountTypes[]` |
| Cluster node list | `/ui/clusterManagement.action mainAction=getNodes` | `[{nodeName, nodeAddress, id, webServer}]` |
| Product edition + licence? | `/suite-api/api/product/licensing/edition` | `{productLicensingEdition:"ENTERPRISE"}` |
| Auth sources configured? | `/suite-api/api/auth/sources` | `sources[].{id, name, sourceType.id}` |
| Dashboards present? | `/ui/dashboard.action mainAction=getDashboardList` | `dashboards[]` |
| Super metrics present? | `/ui/superMetric.action mainAction=getSuperMetrics` OR `/suite-api/api/supermetrics` | both work |
| Resource kinds on instance? | `/suite-api/api/adapterkinds` → `.adapter-kind[].resourceKinds[]` OR adapter-describe per-kind |
| Policy list? | `/suite-api/api/policies` | `policySummaries[]` |
| MPB designs in progress? | `/suite-api/internal/mpbuilder/designs` | `designSummaries[]` |

**The install-flow-friendly `isPakInstalling` endpoint is a recent
addition.** `installer.py` currently polls `getLatestInstalledSolutionStatuses`
which returns 100KB+ JSON. For status-only checks (install/uninstall
in flight vs complete), switching to `isPakInstalling` (~50 bytes
response) is a cheap optimization — log it as a potential tooling
improvement, non-urgent.

---

## Open gaps (items requiring mutation to settle)

1. **MPB full lifecycle end-to-end.** The read-only drain
   established the endpoint shape but not the full create →
   populate → build → install flow. Needs a trivial design
   creation and cleanup to map the POST/PUT bodies on
   `/designs/{id}/source`, `/requests`, `/objects`,
   `/relationships`, `/configuration`.

2. **`/vcf-operations/*` programmatic auth.** Currently an open
   question whether there's a machine-friendly VIDB grant or
   whether it truly requires interactive SSO. Relevant only if
   Broadcom discontinues the `/ui/` and `/admin/` Struts layers
   in a future release. Today, avoid.

3. **`/ui/solution.action mainAction=install` via one-shot upload+install.**
   The SPA wires upload → getLicenseAgreement → user-accept →
   install. Whether `mainAction=install` can accept a multipart
   body with the pak file inline (atomic upload+install) is
   unknown; the SPA path is always two-step. Current CLI is
   two-step and works — non-urgent.

4. **`/ui/resource.action` mainAction surface.** Registered
   (errorPanel), but no `get*` tried returned JSON. Probably
   parameter-specific (`getResource` presumably needs an `id`).
   Not blocking; `/suite-api/api/resources` covers the same ground.

5. **`/suite-api/api/events` returns 500.** Probably needs
   specific query params. Not blocking anything today but worth
   fixing if events-based recon is ever needed.

6. **Internal REST 404s.** `/internal/adapterkinds`,
   `/internal/credentials`, `/internal/supermetrics`,
   `/internal/customgrouptypes`, `/internal/resources/properties`
   all return 404 despite appearing in the internal spec. Either
   implementation lags spec, or these are compile-time routed to
   public `/api/*` equivalents. Use the public paths instead.

---

## Superseded docs (tooling routing list)

The following existing docs have URL claims that need updating in
light of this drain. Corrections are trivial but route through the
`tooling` agent to keep `context/` hygiene consistent.

1. **`memory/project_vcf_operations_url_structure.md`** — the user
   memory claim that `/vcf-operations/plug/ops/*.action` is a live
   alias for `/ui/*.action` with local-account auth is **false** on
   this lab. It's VIDB-gated. Memory should be updated to say
   "`/vcf-operations/*` paths exist on VCF 9 but require the VCF
   merged console SSO (VIDB/OAuth2 auth_code flow); for programmatic
   access, use `/ui/*.action`, `/admin/*.action`, and
   `/suite-api/*`, all of which accept local-account credentials and
   cover every capability `/vcf-operations/rest/ops/*` exposes." Route
   to Dalinar for memory update, not tooling.

2. **`context/struts_import_endpoints.md`** §"Struts action
   registration probe" — the 2026-04-11 enumeration missed
   `solution`, `utility`, `clusterManagement`, `stateManager`,
   `resource`, `resourceKind`. The 2026-04-17 correction block
   at line 93-114 of that file already mentions the first four but
   not `resource` / `resourceKind` — add those two.

3. **`context/pak_install_api_exploration.md`** §"Endpoints probed"
   — still says "/admin/* — the actual pak-install path (THIS IS
   THE ANSWER)" as the section title, though the code has moved to
   `/ui/`. Retrofit the summary to clarify both `/ui/` and `/admin/`
   work equivalently (already partially done in the 2026-04-17
   correction).

4. **`context/pak_ui_upload_investigation.md`** — status quo is
   correct as of the 2026-04-16 second pass. No changes needed;
   add a cross-reference pointer back to this file for the broader
   URL-surface context.

5. **`context/content_api_surface.md`** (not re-read) — if it claims
   anything about `/vcf-operations/rest/ops/*` being a reachable
   REST prefix on arbitrary VCF 9 instances, it should be softened
   to "reachable via VCF SSO only; use `/suite-api/*` for
   programmatic code".

6. **`vcfops_managementpacks/installer.py`** — **no URL changes
   needed**. The installer's `_UISession` uses `/ui/*` and
   `/suite-api/*`, both confirmed working. The module docstring
   line 3-6 already reflects current state.

Items 2 and 3 are micro-edits. Item 1 is a memory update. Item 5 is
a read-and-assess task. Item 4 is a documentation pointer addition.

---

## Clean-up verified

All scratch files from this investigation live under
`/tmp/vcfops_surface/` (probe Python scripts, downloaded SPA JS
bundles, captured JSON responses, cookie jars, login-page HTML).
**Size: 12 MB.** Deleted after this doc is written; see next section.

No state mutations against the lab. All `POST` calls that reached a
backend handler were either `mainAction=get*` reads or
`mainAction=prepareFileUpload` (idempotent no-op). No pak uploaded,
no design created, no content modified. Admin session not used
except for registration probing on `/admin/*.action` — no mutating
mainActions invoked.

Login sessions logged out at the end of each probe run
(`GET /ui/login.action?mainAction=logout`, `GET /admin/login.action?mainAction=logout`,
`POST /suite-api/api/auth/token/release`).
