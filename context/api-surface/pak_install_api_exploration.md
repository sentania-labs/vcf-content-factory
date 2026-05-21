# .pak install API exploration (VCF Ops 9.0.2)

Investigation log and documentation for programmatic management pack
(`.pak`) install against VCF Operations 9.0.2.0 build 25137838.

## Executive summary

**Scripted `.pak` install IS achievable.** The VCF Ops admin UI
(`https://<host>/admin/`) drives pak install through a Struts action at
`/admin/solution.action` plus a dedicated multipart upload endpoint at
`/admin/admin/services/solution/upload`. Both are reachable with a
`/admin` JSESSIONID and an `secureToken` CSRF value obtained from
`GET /admin/commonJS.action?mainAction=getApplicationGlobalData`.
The entire install lifecycle (prepare → upload → EULA → release info →
finishStage → install → poll) is scriptable end-to-end against
**admin-account credentials only** (non-admin users can't hit `/admin/`).

**Pak uninstall is NOT exposed via the admin UI in 9.0.2.** The admin
SPA bundles contain no `uninstall`, `remove`, `removePak`, or
equivalent `solution.action` mainAction — only `install`, `cancel`
(in-progress only), and status queries. The `/casa/deployment/slice/pak*`
family of endpoints exists but every JSON body tested returns
`"Operation failed"` — CaSA is the legacy cluster-admin service, not
the pak-install path in this build, and its pak endpoints' schema is
opaque without a browser capture. Uninstall is out of scope for this
investigation — Scott will need a separate capture if uninstall is
required.

**The REST API (`/suite-api/*`) has no pak install endpoint.** Verified
by grepping both OpenAPI specs and by live probing — confirms the
passive finding in `docs/reference-mpb-research.md`. The install path
is admin-UI-session-based, not REST-token-based.

## Endpoints probed (full table)

Probed 2026-04-16 against `vcfops.example.com` using the
`VCFOPS_ADMIN` service account and the standard `VCFOPS_USER` service
account (for Suite API token acquisition). Auth column: `token` =
Suite API bearer token; `admin` = `/admin/` JSESSIONID; `ui` =
`/ui/` JSESSIONID; `casa` = HTTP Basic with admin.

### Suite API (`/suite-api/*`) — no pak endpoints

| Method | Path | Auth | Status | Interpretation |
|---|---|---|---|---|
| POST | `/suite-api/api/solutions` | token | 500 generic | No POST handler; `HEAD` shows GET works, OPTIONS 403. Not the install path. |
| POST | `/suite-api/api/solutions/install` | token | 500 generic | No handler (falls through to generic 500). |
| POST | `/suite-api/api/solutions/upload` | token | 500 generic | No handler. |
| POST | `/suite-api/api/solutions/import` | token | 500 generic | No handler. |
| GET  | `/suite-api/api/pak` | token | 404 | Does not exist. |
| POST | `/suite-api/api/pak` | token | 404 | Does not exist. |
| POST | `/suite-api/api/paks` | token | 404 | Does not exist. |
| POST | `/suite-api/internal/solutions` | token + unsupported | 404 | Does not exist (only `/preinstalled` subtree exists). |
| POST | `/suite-api/internal/solutions/install` | token + unsupported | 404 | Does not exist. |
| POST | `/suite-api/internal/solutions/upload` | token + unsupported | 404 | Does not exist. |
| POST | `/suite-api/internal/solutions/pakupload` | token + unsupported | 404 | Does not exist. |
| POST | `/suite-api/internal/adapterkinds/pakupload` | token + unsupported | 404 | Does not exist (only `describeupload` does). |
| POST | `/suite-api/internal/pak*` (many variants) | token + unsupported | 404 | None exist. |

**Zero pak references in either OpenAPI spec.** Grepped
`docs/operations-api.json` and `docs/internal-api.json` for
`pak|uploadPak|managementpack|management_pack` → only one match in a
docstring for a widget config enum that mentions "Management Packs
Configuration" as a folder name; no endpoints.

### CaSA (`/casa/*`) — alive but pak-install path is opaque

CaSA (Cluster and Slice Administrator) is the legacy VCF Ops
cluster-admin HTTP service. Auth = HTTP Basic with the admin account.
It exists on this build but the pak endpoints are not behaving like
pak install.

| Method | Path | Status | Response | Interpretation |
|---|---|---|---|---|
| GET | `/casa/node/status` | 200 | `{"name":"vcf-lab-operations","role":"MASTER","state":"CONFIGURED",...}` | Alive, minimal node metadata. |
| GET | `/casa/sysadmin/cluster/status` | 200 | Cluster state JSON | Alive, cluster status. |
| GET | `/casa/deployment/slice` | 200 | HATEOAS with `role status` + `online state` links | Alive. |
| PUT | `/casa/deployment/slice/pak` | 415 (no CT) / 500 (JSON `{}`) | `{"error_message":"Operation failed"}` on any JSON | **Endpoint exists; schema unknown.** Every JSON body tested (pak_name, filename, pakFile, url, pakUrl, sources, action/filename) returned generic "Operation failed" — cannot elicit a structured error. |
| PUT | `/casa/deployment/slice/paks` | 415 / 500 | same | same behavior, same result |
| PUT | `/casa/deployment/slice/pakFile` | 415 / 500 | same | same behavior, same result |
| PUT | `/casa/deployment/slice/pakFile/upload` | 405 | (405 on all methods) | Generic 405 trap — no real handler. |
| PUT | `/casa/deployment/slice/pak/list` | 405 | (405 on all methods) | Generic 405 trap. |
| DELETE | `/casa/deployment/slice/pak*` | 500 | `{"error_message":"Operation failed"}` | Handler exists but schema unknown. |

The `/casa/deployment/slice/pak*` endpoints that return 500 are
**real handlers** — they accept JSON content-type but reject every
payload schema I tried with a generic error. Broadcom does not
publish a CaSA swagger or schema reference for this build, and the
admin SPA bundles we have access to do NOT call these endpoints for
pak install — so they appear to be vestigial or used by a different
internal service. **Not a recommended automation path.**

### `/ui/*` Struts (`/ui/solution.action`) — CORRECTION: live handler, not a dead stub

**2026-04-17 correction.** The claim below — that `/ui/solution.action` is a
dead stub — was WRONG.  It was never actually tested against `solution.action`
specifically; it was extrapolated from the general pattern that many `/ui/*.action`
paths are silent in 9.0.2.  Subsequent live work disproved it:

- **2026-04-16 uninstall investigation** (`context/pak_uninstall_api_exploration.md`)
  proved `/ui/solution.action` is a live Struts handler with a rich mainAction
  surface (`remove`, `getIntegrations`, `getLatestInstalledSolutionStatuses`,
  `install`, `enable`, `disable`, `reinstall`, `resetSolutionUninstallState`,
  `cancel`, `finishStage`, etc.).
- **2026-04-16 static-asset investigation** (`context/pak_ui_upload_investigation.md`
  §"Live-source findings") confirmed the `/ui/` SPA bundles contain the full
  install wizard (`Ext.vcops.initialConfiguration.solutions.{ConfigurationWizard,
  Select,Eula,Install,...}`) and proved the upload endpoint is
  `/ui/admin/services/solution/upload` (relative-URL POST that resolves under
  the `/ui/` servlet context, backed by the same Java handler as the `/admin/`
  side).
- The 2026-04-11 `/ui/*.action` enumeration in `context/struts_import_endpoints.md`
  did not probe `solution.action` at all; the "dead stub" conclusion was
  extrapolated without evidence.

**Current state as of 2026-04-17:**  `vcfops_managementpacks/installer.py` uses
`/ui/solution.action` for the full pak lifecycle (install + uninstall + status
polling).  `/admin/solution.action` is no longer used by this codebase.

**Original (wrong) note preserved for search history:**

> `/ui/solution.action` returns HTTP 200 with zero-byte body for every
> `mainAction` tried (real ones like `getSolutions`, fake ones like
> `FAKE_BOGUS_NAME`). This is the Struts default for an unregistered
> action — confirmed by comparison with `/ui/dashboard.action`.  The
> pak-install Struts handler lives at `/admin/solution.action`, not
> `/ui/solution.action`.

This was incorrect.  The mainActions tried in the original probe did not include
any of the valid solution lifecycle actions (`getIntegrations`, `remove`, etc.),
so the empty-200 responses were "unknown mainAction" fallthrough, not "unregistered
action" — two different Struts behaviors that look identical on the wire.

### `/ui/vcops/services/router` Ext.Direct — no solution controller

Enumerated the full Ext.Direct API (`GET /ui/vcops/services/api.js`
with `/ui` session). Only 5 controllers exist:
`viewFilterController`, `reportServiceController`, `viewServiceController`,
`reportScheduleController`, `reportController`, `uploadContentController`.
**No `solutionServiceController`, `pakServiceController`, or
`adapterServiceController`.** Ext.Direct is not the pak-install path.

### `/admin/*` — the actual pak-install path (THIS IS THE ANSWER)

`/admin/` is a separate Clarity-based SPA UI that the admin account
drives for solution / pak management. It authenticates via its own
Struts form-post login (separate JSESSIONID scoped to `/admin`) and
has its own secureToken (CSRF) pulled from
`GET /admin/commonJS.action?mainAction=getApplicationGlobalData`.

| Method | Path | Auth | Status | Notes |
|---|---|---|---|---|
| GET | `/admin/` | anon | 302 → `/admin/login.action` | SPA landing. |
| POST | `/admin/login.action` | anon | 200 `"ok"` | Struts login. Form: `mainAction=login&userName=<u>&password=<p>`. Sets `JSESSIONID; Path=/admin`. |
| GET | `/admin/commonJS.action?mainAction=getApplicationGlobalData` | admin | 200 JSON | Returns `{secureToken, isLoggedIn, loggedInUserName, bundle, ...}`. **This is how the SPA obtains its CSRF token.** |
| POST | `/admin/utility.action` | admin + secureToken | 200 `{"success":true}` | `mainAction=prepareFileUpload` — called immediately before the multipart upload. |
| POST | `/admin/admin/services/solution/upload?uploadId=<epoch_ms>` | admin + secureToken (form field) | 200 | **The actual pak upload endpoint.** Multipart body with `solution=@<file>.pak`, plus form fields `forceUpload`, `ignoreSignatureChecking`, `secureToken`, `currentComponentInfo=TODO`. Returns JSON with `pakId`, `solutionName`, `solutionVersion`, `solutionDescription`, `estimatedInstallTime`, `signingStatus`, `clusterBringOffline`, `clusterRestartRequired`, `adminRestartRequired`, `osRestartRequired`. On rejection returns `{"success":true,"errorMsg":"PAK Manager: ..."}`. (Note the nested `/admin/admin/` in the URL — the first `/admin` is the servlet context, the second `/admin/services/solution/upload` is the REST sub-path.) |
| GET | `/admin/admin/services/solution/upload?uploadId=<id>&progress=true` | admin | 200 JSON | Upload progress polling. Returns `{uploadId, uploadInProgress, percentComplete, bytesRead, totalBytes, message, isRestarting, restartingMessage, seconds}`. |
| POST | `/admin/solution.action` | admin + secureToken | varies | **The pak-install lifecycle Struts handler.** See mainAction table below. |

Full `/admin/solution.action` `mainAction` table observed:

| mainAction | Required params | Returns | Purpose |
|---|---|---|---|
| `getLatestInstalledSolutionStatuses` | — | Full status JSON (`pakId`, `solutionName`, `solutionVersion`, `solutionStatuses[]`, `pakInstalling`, `installationFailed`, ...) | Grid data: what's installed, what's in progress, node-level install state. |
| `getSolutionVersion` | `solutionName=<key>` | `{"solutionVersion":"<ver>","success":true}` | Check currently-installed version of a named solution (needed for version-mismatch warnings in the install wizard). |
| `getLicenseAgreement` | `pakId` | EULA text | Retrieve EULA for display in the install wizard's EULA step. |
| `getReleaseInfo` | `pakId` | Release info | Retrieve release notes for display. |
| `getInstallStatus` | `pakId`? | Status JSON | Poll install progress. |
| `isInProgress` | — | `{installing:bool}` | Boolean progress flag. |
| `isPakInstalling` | — | same | Boolean progress flag (duplicate of above, UI calls both). |
| `isClusterStateInTransition` | — | Boolean | Whether cluster state is changing. |
| `getLCMNodeStatus` | — | Lifecycle status | Per-node LCM status. |
| `getPreUpdateValidationLog` | `pakId`, `nodeIpAddress` | Validation log text | Per-node pre-install validation output. |
| `finishStage` | `pakId` | `{success:true}` or `{errorMsg:...}` | Advance a staged pak through validation. Called by the install wizard on the final card when `restart=true`. |
| `install` | `pakId`, `forceContent` (bool) | `{success:true}` or `{errorMsg:...}` | **Trigger the actual install.** |
| `cancel` | `pakId` | `{success:true}` or `{errorMsg:...}` | Cancel an in-progress install (only valid while `canCancelOrFinish:true`). |

**No `uninstall`, `remove`, `removeSolution`, `removePak`,
`deleteSolution`, or `deletePak` mainAction exists** — probed every
plausible name, all returned the Struts empty-200 stub.

## The full working install flow

From `admin/js/components/initialConfiguration/solutions/Select.js` +
`ConfigurationWizard.js` + empirical verification:

```
1. POST /admin/login.action
    form: mainAction=login&userName=<admin>&password=<pw>
    response: "ok", sets JSESSIONID (path /admin)

2. GET /admin/commonJS.action?mainAction=getApplicationGlobalData
    response: { secureToken: "<csrf>", isLoggedIn: true, ... }

3. POST /admin/utility.action
    form: mainAction=prepareFileUpload
         &currentComponentInfo=TODO
         &secureToken=<csrf>
    response: {"success":true}

4. POST /admin/admin/services/solution/upload?uploadId=<epoch_ms>
    multipart:
       solution=@<file>.pak        (the pak file)
       forceUpload=false
       ignoreSignatureChecking=false
       currentComponentInfo=TODO
       secureToken=<csrf>
    response on success:
       { "success": true,
         "pakId": "<solutionName>-<version>",
         "solutionName": "<display>",
         "solutionDescription": "...",
         "solutionVersion": "X.Y.Z.B",
         "solutionFilename": "<original>.pak",
         "signingStatus": "NotSigned" | "SignatureValid" | ...,
         "clusterBringOffline": bool,
         "clusterRestartRequired": bool,
         "adminRestartRequired": bool,
         "osRestartRequired": bool,
         "estimatedInstallTime": "...",
         ...
       }
    response on rejection:
       { "success": true, "errorMsg": "PAK Manager: ..." }
    — NOTE: "success":true even on rejection; check errorMsg.

5. (optional) GET /admin/admin/services/solution/upload?uploadId=<id>&progress=true
    poll until uploadInProgress:false
    response: { uploadId, uploadInProgress, percentComplete,
                bytesRead, totalBytes, message, isRestarting, ... }

6. POST /admin/solution.action
    form: mainAction=getLicenseAgreement&pakId=<pakId>&secureToken=<csrf>&currentComponentInfo=TODO
    response: EULA text (to display + user accepts out-of-band or auto-accept)

7. POST /admin/solution.action
    form: mainAction=getReleaseInfo&pakId=<pakId>&secureToken=<csrf>&currentComponentInfo=TODO
    response: release info (similar)

8. POST /admin/solution.action
    form: mainAction=finishStage&pakId=<pakId>&secureToken=<csrf>&currentComponentInfo=TODO
    response: {success:true} or {errorMsg:...}
    (per ConfigurationWizard.js, only needed when wizard is re-opened
     mid-stage — for a fresh install, not strictly required)

9. POST /admin/solution.action
    form: mainAction=install&pakId=<pakId>&forceContent=true&secureToken=<csrf>&currentComponentInfo=TODO
    response: {success:true} or {errorMsg:...}

10. (poll) POST /admin/solution.action
    form: mainAction=getLatestInstalledSolutionStatuses&secureToken=<csrf>&currentComponentInfo=TODO
    until solutionStatuses[].state reaches "Applied and Cleaned"
          AND status="Completed"
          AND pakInstalling=false

11. POST /admin/login.action?mainAction=logout  (cleanup)
```

### Reference Python snippet (minimal, not committed to vcfops_*/)

```python
import base64, json, os, time, requests, urllib3
urllib3.disable_warnings()

HOST = os.environ['VCFOPS_HOST']
ADMIN = os.environ['VCFOPS_ADMIN']
ADMIN_PW = os.environ['VCFOPS_ADMINPASSWORD']

def admin_login():
    s = requests.Session()
    s.verify = False
    # initial JSESSIONID
    s.get(f"https://{HOST}/admin/login.action")
    r = s.post(f"https://{HOST}/admin/login.action", data={
        "mainAction": "login", "userName": ADMIN, "password": ADMIN_PW,
    })
    assert r.text == "ok", f"login failed: {r.text!r}"
    g = s.get(f"https://{HOST}/admin/commonJS.action",
              params={"mainAction": "getApplicationGlobalData"})
    csrf = g.json()["secureToken"]
    return s, csrf

def common_form(csrf, **extra):
    d = {"currentComponentInfo": "TODO", "secureToken": csrf}
    d.update(extra)
    return d

def install_pak(pak_path):
    s, csrf = admin_login()
    try:
        # Step 3: prepare
        r = s.post(f"https://{HOST}/admin/utility.action",
                   data=common_form(csrf, mainAction="prepareFileUpload"))
        assert r.json().get("success"), r.text

        # Step 4: upload
        upload_id = str(int(time.time() * 1000))
        with open(pak_path, "rb") as f:
            files = {"solution": (os.path.basename(pak_path), f, "application/octet-stream")}
            data = {
                "forceUpload": "false",
                "ignoreSignatureChecking": "false",
                "currentComponentInfo": "TODO",
                "secureToken": csrf,
            }
            r = s.post(
                f"https://{HOST}/admin/admin/services/solution/upload",
                params={"uploadId": upload_id},
                files=files, data=data,
            )
        up = r.json()
        if up.get("errorMsg"):
            raise RuntimeError(f"upload rejected: {up['errorMsg']}")
        pak_id = up["pakId"]
        print(f"[upload] pakId={pak_id} name={up['solutionName']}")

        # Step 9: install
        r = s.post(f"https://{HOST}/admin/solution.action",
                   data=common_form(csrf, mainAction="install",
                                    pakId=pak_id, forceContent="true"))
        inst = r.json()
        if inst.get("errorMsg"):
            raise RuntimeError(f"install failed: {inst['errorMsg']}")

        # Step 10: poll
        while True:
            r = s.post(f"https://{HOST}/admin/solution.action",
                       data=common_form(csrf,
                                        mainAction="getLatestInstalledSolutionStatuses"))
            st = r.json()
            if not st.get("pakInstalling"):
                break
            time.sleep(15)
        print(f"[install] completed: {st.get('solutionStatuses')}")
    finally:
        s.get(f"https://{HOST}/admin/login.action",
              params={"mainAction": "logout"}, allow_redirects=False)
```

### Reference curl invocation (upload only, for sanity-check)

```bash
# 1. login, save cookies
curl -sk -c cj.txt -b cj.txt "https://$VCFOPS_HOST/admin/login.action" >/dev/null
curl -sk -c cj.txt -b cj.txt -X POST "https://$VCFOPS_HOST/admin/login.action" \
    -d "mainAction=login&userName=$VCFOPS_ADMIN&password=$VCFOPS_ADMINPASSWORD" \
    -o /dev/null

# 2. get CSRF
CSRF=$(curl -sk -c cj.txt -b cj.txt \
    "https://$VCFOPS_HOST/admin/commonJS.action?mainAction=getApplicationGlobalData" \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['secureToken'])")

# 3. prepare
curl -sk -c cj.txt -b cj.txt -X POST "https://$VCFOPS_HOST/admin/utility.action" \
    --data-urlencode "mainAction=prepareFileUpload" \
    --data-urlencode "currentComponentInfo=TODO" \
    --data-urlencode "secureToken=$CSRF"

# 4. upload
UID=$(date +%s%3N)
curl -sk -c cj.txt -b cj.txt -X POST \
    "https://$VCFOPS_HOST/admin/admin/services/solution/upload?uploadId=$UID" \
    -F "solution=@dist/mpb_synology_dsm.1.0.0.1.pak" \
    -F "forceUpload=false" \
    -F "ignoreSignatureChecking=false" \
    -F "currentComponentInfo=TODO" \
    -F "secureToken=$CSRF"

# 5. install (do NOT run this yet — requires real pak with working adapter JAR)
# curl -sk -c cj.txt -b cj.txt -X POST "https://$VCFOPS_HOST/admin/solution.action" \
#     --data-urlencode "mainAction=install" \
#     --data-urlencode "pakId=<from-step-4>" \
#     --data-urlencode "forceContent=true" \
#     --data-urlencode "secureToken=$CSRF" \
#     --data-urlencode "currentComponentInfo=TODO"
```

## Live verification evidence (2026-04-16)

Probed against `vcfops.example.com` using the admin service
account. No real pak was installed. All artifacts listed below were
either generated-and-verified-cleaned-up or were read-only queries.

1. **Admin login works**: `POST /admin/login.action` with admin
   credentials returns `"ok"` and sets JSESSIONID.
2. **CSRF acquisition works**: `GET /admin/commonJS.action?mainAction=
   getApplicationGlobalData` returned a valid UUID for `secureToken`.
3. **Prepare upload works**: `POST /admin/utility.action
   mainAction=prepareFileUpload` returned `{"success":true}`.
4. **Upload endpoint works end-to-end**: Uploaded a 29-byte bogus
   file named `bogus.pak` via
   `POST /admin/admin/services/solution/upload?uploadId=1776374780701`.
   Server responded HTTP 200 with
   `{"success":true,"errorMsg":"PAK Manager: PAK file
   reservedTemp_17875419202013056149.pak is not in zip format"}`. This
   proves (a) the endpoint exists, (b) it accepts our multipart shape,
   (c) the `secureToken` form field is accepted for CSRF, and (d) the
   server's PAK Manager component actually ran validation on the
   uploaded bytes.
5. **Status query works**: `POST /admin/solution.action mainAction=
   getLatestInstalledSolutionStatuses` returned the full in-progress
   status JSON for the PCI Compliance pak (the last-touched real pak),
   confirming the bogus upload did NOT leave ghost state on the
   cluster. Post-probe status matched pre-probe status exactly
   (`solutionStatuses[0].state="Applied and Cleaned"`,
   `pakInstalling:false`).
6. **Solutions list unchanged**: `GET /suite-api/api/solutions` via
   the Suite API returned the same 17 solutions before and after
   probing. The bogus upload did not create a phantom solution.

### Cleanup verified

- Bogus file rejected server-side before any persistent state
  (including staging area) was created.
- Admin UI and UI sessions were logged out at the end of probing.
- No files or cookies left on the filesystem (deleted `/tmp/bogus.pak`,
  cookie jars).
- No new solutions, paks, or staging artifacts visible in the
  admin UI status grid or the Suite API solutions list.

## Hypothesis results summary

From the original task brief, each hypothesis and its verdict:

1. **`POST /api/solutions`** — ruled out. Returns 500 generic regardless
   of body; GET works, HEAD works, POST has no handler on the business
   layer. Not the install path.

2. **`/internal/solutions/*` POST variants** — ruled out. `/internal/
   solutions` (without `/preinstalled`) returns 404. Only
   `/internal/solutions/preinstalled/*` exists, and it only
   activates/deactivates already-installed preinstalled paks.

3. **`/internal/adapterkinds/pakupload`** — ruled out. Returns 404. Only
   `describe`/`describeupload` exist under `/internal/adapterkinds/`.

4. **`/admin/*` or `/ui/*` Struts-style endpoints** — **confirmed for
   both `/admin/` and `/ui/`.** See correction block above: the original
   "dead stub" conclusion about `/ui/solution.action` was wrong.
   Both `/admin/solution.action` and `/ui/solution.action` are live
   handlers; they are backed by the same Java code and share the same
   mainAction surface.  The `/ui/` path is now the preferred path in
   this codebase (single session for full lifecycle).

5. **`/suite-api/api/pak/*`** — ruled out. All variants 404.

6. **SPA JS discovery** — confirmed. The admin SPA bundles at
   `/admin/js/components/initialConfiguration/solutions/*.js` and
   `/admin/dist/js/app.part{0,1,2}.min.js` contain the full endpoint
   wire format, verified line-by-line against `Select.js` and
   `ConfigurationWizard.js`.

## Recommended automation path for the repo

If the user wants the factory to install its own `.pak` bundles, the
cleanest path is:

1. **Add a `vcfops_managementpacks` pak-install command** that:
   - Requires admin credentials (`VCFOPS_ADMIN` / `VCFOPS_ADMINPASSWORD`
     — same envs the QA uninstall path already uses)
   - Runs steps 1–5 above (login → CSRF → prepare → upload → poll)
   - On a successful upload, prompts the user with the EULA text
     (step 6) and waits for explicit "I agree"
   - Runs step 9 (install) and polls step 10 until the solution
     reaches `Applied and Cleaned` / `Completed`
   - Logs out cleanly (step 11)

2. **The existing UI-session code in
   `context/dashboard_delete_api.md`** is a good model — the
   `ui_login()` function there establishes the identical session
   pattern (Struts form-post login + CSRF from a secondary page) but
   against `/ui/` instead of `/admin/`. A sibling `admin_login()`
   function in the same shape is all we need.

3. **Do NOT commit an auto-install for the Synology MP yet.** The
   current `dist/mpb_synology_dsm.1.0.0.1.pak` carries the stand-in
   adapter JAR documented in `context/pak_wire_format.md` (ADAPTER_JAR_GAP).
   Installing that pak would land a broken adapter. Automation should
   wait for the real adapter JAR.

## Install/uninstall parity — uninstall is the gap

Scripted install is achievable. **Scripted uninstall is not, via the
paths probed here**:

- No `/admin/solution.action` mainAction named `uninstall`, `remove`,
  `removeSolution`, `removePak`, `deleteSolution`, `deletePak`, or
  `forceRemove` — all tested, all return the Struts empty-200 stub
  meaning "unknown action".
- The admin SPA bundles (`app.part{0,1,2}.min.js` +
  `softwareUpdates/Content.js` + `SolutionStatusGrid.js`) contain no
  UI wiring for pak removal — only `install`, `cancel` (in-progress
  only), and status queries.
- The `/casa/deployment/slice/pak` endpoints return 500 "Operation
  failed" on every schema tried (including DELETE with body), so
  CaSA's pak subtree is a potential candidate but is not accessible
  without a reference request shape.
- The Suite API has no pak uninstall endpoint (grepped both specs).

**Recommended follow-up if uninstall automation is needed:** ask Scott
to capture a browser network trace of a manual pak removal from the
admin UI's solution status grid (if such UI exists in 9.0.2 — I did
not visually confirm it does), and analyze the captured request. The
alternative is the CLI tool on the appliance itself (`$VMWARE_PYTHON_BIN
/usr/lib/vmware-vcops/user/plugins/inbound/.../removePak.py` style) —
but that requires SSH, not an HTTP endpoint.

For 9.0.2 as observed, **treat pak uninstall as a manual operator step**:
Admin UI > Software Updates > Solutions grid > (context menu, if
present). The framework can install its own pak; removing it is the
operator's responsibility.

## Unsupportability caveat

All `/admin/*` and `/casa/*` endpoints documented here are
**undocumented internal surfaces**. They are not part of any public
contract. They will change between VCF Ops releases without notice.
The X-Ops-API-use-unsupported header does NOT apply here — these
aren't `/internal/` REST endpoints, they are Struts handlers and
servlets that back the admin web console. Tested against VCF
Operations 9.0.2.0 build 25137838 only.

## References

- `docs/reference-mpb-research.md` §"VCF Ops API Surface for
  Management Pack Lifecycle" — the passive finding this investigation
  corroborates (no REST pak install).
- `context/dashboard_delete_api.md` — the UI-session auth pattern this
  builds on (different path `/admin` vs `/ui`, but same model:
  Struts form-post login + CSRF from a secondary action).
- `context/ui_import_formats.md` — earlier exploration of `/ui/*.action`
  dead-ends; confirms the empty-200 pattern is the Struts default for
  unregistered actions, which is what `/ui/solution.action` returns.
- `memory/project_vcf_ops_902_ui_deadends.md` — prior catalog of UI
  import dead stubs.
- Live admin SPA sources (read during investigation, not reproduced
  in repo): `/admin/js/components/initialConfiguration/solutions/{
  Select,ConfigurationWizard,Eula,ReleaseInfo,FinalStep}.js` and
  `/admin/js/components/softwareUpdates/{Content,SolutionStatusGrid}.js`.
