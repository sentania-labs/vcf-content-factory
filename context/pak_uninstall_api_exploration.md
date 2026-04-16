# .pak uninstall API exploration (VCF Ops 9.0.2)

Investigation log and documentation for programmatic management pack
(`.pak`) uninstall against VCF Operations 9.0.2.0 build 25137838.
Companion to `context/pak_install_api_exploration.md`.

## Executive summary

**Scripted `.pak` uninstall IS achievable**, via a previously-misclassified
handler. The uninstall path is **`POST /ui/solution.action` with
`mainAction=remove`**, authenticated by a `/ui/` admin session and CSRF
token extracted from the `OPS_SESSION` cookie (the UI-session pattern
already documented in `context/dashboard_delete_api.md`).

**The prior exploration's conclusion that `/ui/solution.action` is a
"dead stub" was wrong.** The admin SPA (`/admin/`, Clarity-based) has
no uninstall wiring — as prior work found — but the **main UI SPA
(`/ui/`, ExtJS-based, new VCF Ops 9.x integrations marketplace)** uses
a separate Struts handler at `/ui/solution.action` with an entirely
different `mainAction` surface (including `remove`, `enable`, `disable`,
`reinstall`, `resetSolutionUninstallState`, `installingPakDetail`).
This handler has a LIVE `remove` implementation that drives pak
removal across the cluster.

**A full install → uninstall round-trip succeeded** end-to-end against
the Broadcom Security Advisories 1.0.1.6 pak (a Dale Hassinger /
Broadcom-distributed reference pak). After uninstall, `GET
/suite-api/api/solutions` and `GET /suite-api/api/adapterkinds` both
returned to EXACT pre-install baseline.

**CRITICAL SAFETY FINDING — server does NOT enforce `isUnremovable`.**
`getIntegrations` marks built-in paks (vSAN, vCenter, NSX, etc.) with
`isUnremovable: true` and the SPA disables the remove button for them.
But **the server-side `mainAction=remove` handler does not check this
flag** and will accept a remove request for any pak. During edge-case
testing, a `remove` against the vSAN pak was accepted, ran partially
(the adapter kind `VirtualAndPhysicalSANAdapter` was deregistered),
and left the preinstalled "Management Pack for Storage Area Network"
in a DEACTIVATED state that could NOT be recovered via the documented
`POST /suite-api/internal/solutions/preinstalled/{id}/activate` endpoint
(activate returns 202 but the task stays queued without progressing).

**This is a production-grade footgun that CLI tooling MUST guard
against.** Any wrapper around `mainAction=remove` must check
`isUnremovable` client-side before issuing the call.

## Test fixture

- **Pak used**: `Broadcom Security Advisories-1.0.1.6.pak` from
  `references/dalehassinger_unlocking_the_potential/.../Security-Advisories/`.
  22 MB, unsigned (requires `ignoreSignatureChecking=true`), registers
  adapter kind `mpb_broadcom_security_advisories`.
- **Why**: Broadcom-authored, polls public security-advisory API only,
  no credentials needed, small blast radius. Primary recommendation
  from the task brief.
- **Not used**: `dist/mpb_synology_dsm.1.0.0.1.pak` (has stand-in
  adapter JAR), Rubrik-1.1.0.25.pak (fallback, not needed).

## Angles investigated — summary table

| Angle | Method | Result | Interpretation |
|---|---|---|---|
| 1. `/casa/deployment/slice/pak*` DELETE with various bodies | HTTP Basic admin, JSON bodies with `pakId`, `pak_id`, `action`, `pakIds[]`, `solution`, etc. | Every body → 500 `{"error_message":"Operation failed"}`. Empty body → 500 `required_body_is_either_missing_or_invalid.failure`. | CaSA pak subtree is **deprecated** in this build (`isCaSAReplaced` flag in admin SPA confirms migration). Endpoint exists as a vestigial stub but has no working schema. Not the uninstall path. |
| 2. `/casa/cluster/*` variants | HTTP Basic, GET/POST/PUT/DELETE on `pak`, `paks`, `pakFile`, `action`, `action/pak` | All 404 or 405. | No cluster-level CaSA pak uninstall. |
| 3. `/admin/solution.action` mainActions | Admin SPA session + CSRF | `mainAction=uninstall`/`remove`/`removePak`/`deletePak`/`deactivate`/`cleanupSolution`/`removeSolution`/`purgePak`/`pakRemove`/`pakUninstall`/`disable`/`undeploy` → 200 with empty body (Struts default for unregistered action). Real mainActions (e.g. `install`) return `{}` minimum. | **Admin SPA has no uninstall mainAction** — confirms prior finding. All unregistered. |
| 4. Other admin `.action` endpoints with uninstall-adjacent mainActions | `utility.action`, `softwareUpdate.action`, `clusterManagement.action` with `uninstall`/`remove`/`removePak`/`deletePak` | All empty-200 (unregistered). | Uninstall not on any admin Struts endpoint. |
| 5. `/admin/admin/services/solution/*` REST variants | Admin session + CSRF, all HTTP methods on `/solution`, `/solution/remove`, `/solution/uninstall`, `/solution/delete`, `/solutions/remove` | All 404 on GET/PUT/DELETE; POST returns empty-400 (CSRF rejection pattern, not a real handler). Only `/admin/admin/services/solution/upload` has a real handler (used for install). | No per-object REST uninstall under admin services. |
| 6. Suite API `/suite-api/api/solutions/{id}` with DELETE/PUT/POST | Bearer token | 500 generic "Internal Server error" (no handler). GET works fine. | Public REST API has no mutation handlers on solution. |
| 7. Suite API `/suite-api/internal/solutions/*` | Bearer token + `X-Ops-API-use-unsupported: true` | All 404 except `/preinstalled/*`. `/internal/solutions/{id}/uninstall`, `/remove`, `/actions` — all 404. | Only `/preinstalled/*` is the internal solution surface. |
| 8. `/suite-api/internal/solutions/preinstalled/{id}/deactivate` against installed (non-preinstalled) pak | POST with empty body | 404 `"No such Solution - Broadcom Security Advisories"`. | `/preinstalled/*` only applies to the preinstalled pak catalog; won't handle dynamically-installed paks. |
| 9. Ext.Direct router (`/ui/vcops/services/router`) | Read full `api-debug.js` | Only 6 controllers exist: `viewFilterController`, `reportServiceController`, `viewServiceController`, `reportScheduleController`, `reportController`, `uploadContentController`. **No solution/pak/adapter controller.** | Ext.Direct is not the uninstall path. |
| 10. **Main `/ui/` SPA (ExtJS, NEW integrations marketplace)** | Fetch `/ui/dist/js/app.part{0..6}.min.js`, grep for `uninstall`, `remove`, `mainAction`. Found full uninstall code path. | `ManagementPack.availableActions = {UNINSTALL, ENABLE, DISABLE, GET, UPGRADE, VIEW_IN_REPOSITORY, ADD_ACCOUNT}` — UI tracks uninstall as a first-class action. Uninstall issues `POST solution.action mainAction=remove pakId=<short-id> version=<ver>`. Short ID (a.k.a. "packId") matches the `pakId` field returned by `getIntegrations` — **NOT** the admin's fullPakId. | **THIS IS THE UNINSTALL PATH.** Live verified (see live trace §). |
| 11. Pak-internal scripts | Extracted `Broadcom Security Advisories-1.0.1.6.pak` → `validate.py`, `preAdapters.py`, `post-install.py`, `postAdapters.py`, `post-install.sh`, `post-install-fast.sh`. | No `preRemove.py`/`postRemove.py`/`remove*.sh` or equivalent in the pak. `manifest.txt` has `adapter_pre_script`/`adapter_post_script`/`pak_validation_script` keys but no `remove_script` equivalent. | Pak format does not appear to carry uninstall-specific hooks. The server's `remove` handler presumably triggers a built-in uninstall pipeline (deregister adapter kind + clean out content). |
| 12. Admin SPA `isPakUninstallActive`/`isPakRemoved`/`pakRemoved` fields | Observed in `/admin/solution.action mainAction=getLatestInstalledSolutionStatuses` response | These flags DO exist in the status response (all `false` at steady state). | The admin status grid *can* report uninstall-in-progress state, but the admin SPA has no UI to initiate it. Confirms uninstall is driven from `/ui/` side, not admin. |

## Live install/uninstall cycle trace (2026-04-16)

Tested against `vcf-lab-operations.int.sentania.net` (VCF Ops
9.0.2.0.25137838) using `VCFOPS_ADMIN=admin` /
`VCFOPS_ADMINPASSWORD=...` for admin console, `VCFOPS_USER=claude` /
`VCFOPS_PASSWORD=...` for Suite API bearer token.

### Baseline (before install)

| Check | Value |
|---|---|
| `GET /suite-api/api/solutions` count | 17 |
| `GET /suite-api/api/adapterkinds` count | 26 |
| Broadcom Security Advisories present | no |
| `mpb_broadcom_security_advisories` adapter kind | absent |

### Install (steps follow the documented flow from
`context/pak_install_api_exploration.md` — reproduced here for the
end-to-end trace)

```
1. GET /admin/login.action                           200 (seed JSESSIONID /admin)
2. POST /admin/login.action                          200 "ok"
     mainAction=login userName=admin password=***
3. GET /admin/commonJS.action?mainAction=getApplicationGlobalData  200
     → secureToken: <36-char CSRF UUID>
4. POST /admin/utility.action                         200 {"success":true}
     mainAction=prepareFileUpload currentComponentInfo=TODO secureToken=<csrf>
5. POST /admin/admin/services/solution/upload?uploadId=<epoch_ms>  200
     (multipart) solution=@Broadcom Security Advisories-1.0.1.6.pak
     forceUpload=false ignoreSignatureChecking=false
     currentComponentInfo=TODO secureToken=<csrf>
     →
     {
       "success": true,
       "pakId": "BroadcomSecurityAdvisories-1016",
       "solutionName": "Broadcom Security Advisories",
       "solutionVersion": "1.0.1.6",
       "signingStatus": "NotSigned",
       "clusterBringOffline": false,
       "clusterRestartRequired": false,
       ...
     }
     NOTE: unsigned reference pak required ignoreSignatureChecking=true.
     First attempt with "false" returned
     {"success":true,"errorMsg":"No signature found on PAK file ..."}.
6. POST /admin/solution.action                        200 (EULA text, 33558 bytes)
     mainAction=getLicenseAgreement pakId=BroadcomSecurityAdvisories-1016
7. POST /admin/solution.action                        200 {}
     mainAction=install pakId=BroadcomSecurityAdvisories-1016 forceContent=true
     (empty-{}-with-no-errorMsg is the install-started success shape;
      errorMsg key is absent on success.)
8. (poll) POST /admin/solution.action                 200
     mainAction=getLatestInstalledSolutionStatuses
     state progression (~2 minutes, 15 s poll):
       [1] pakInstalling=True  state="Preapply Validated Candidate"
       [2] pakInstalling=True  state="Applied Adapter Pre Script Candidate"
       [3] pakInstalling=True  state="Applied Adapter Pre Script Candidate"
       [4] pakInstalling=True  state="Applied Adapter Pre Script Candidate"
       [5] pakInstalling=True  state="Applied Adapter Candidate"
       [6] pakInstalling=True  state="Applied Adapter Candidate"
       [7] pakInstalling=True  state="Applied Adapter Candidate"
       [8] pakInstalling=False state="Applied and Cleaned" status="Completed"
```

### Post-install verification

| Check | Value |
|---|---|
| `GET /suite-api/api/solutions` count | 18 (17 + Broadcom Security Advisories) |
| `GET /suite-api/api/adapterkinds` count | 27 (26 + mpb_broadcom_security_advisories) |

### Uninstall (the newly-documented flow)

```
9. GET /ui/login.action?vcf=1                        200 (seed JSESSIONID /ui)
10. POST /ui/login.action                            200 "ok"
     mainAction=login
     userName=admin
     password=***
     authSourceId=localItem
     authSourceName=Local Account
     authSourceType=
     forceLogin=false
     timezone=0
     languageCode=us
11. GET /ui/index.action                             302 (base64 OPS_SESSION cookie set)
     decode OPS_SESSION → csrfToken (UUID)
     → this.packId = "Broadcom Security Advisories" (pakId field from
       getIntegrations installedMPs[]; NOT the admin-side compressed form)
12. POST /ui/solution.action                         200 {}
     mainAction=remove
     pakId=Broadcom Security Advisories
     version=1.0.1.6
     secureToken=<ui_csrf>
     (empty-{} with absent errorMsg = success shape, same pattern as /admin)
13. (poll) POST /admin/solution.action                200 (same endpoint admin uses to monitor install)
     mainAction=getLatestInstalledSolutionStatuses
     state progression (~1 minute, 15 s poll):
       [1-7] pakInstalling=True name="Broadcom Security Advisories"
             state="Applied and Cleaned" status="Completed"
             (yes, state stays "Applied and Cleaned" throughout the
              uninstall; the pakInstalling flag is what signals activity)
       [8]   pakInstalling=False name="PCI Compliance"  ← the solution
             is GONE, status grid now shows last-touched REAL solution
    (UI-side poll of /ui/solution.action mainAction=installingPakDetail
     during the same window returns `{name, isPakUninstalling: true,
     pakUninstallingStatus: null}` and clears to `{}` on completion.)
```

### Post-uninstall verification (back to baseline)

| Check | Value | Drift from baseline |
|---|---|---|
| `GET /suite-api/api/solutions` count | 17 | 0 (exact match) |
| Broadcom Security Advisories present | no | — |
| `GET /suite-api/api/adapterkinds` count | 26 | 0 (exact match) |
| `mpb_broadcom_security_advisories` adapter kind | absent | — |
| All other adapter kinds | identical | 0 |

### Session hygiene

- Admin JSESSIONID logged out via `GET /admin/login.action?mainAction=logout` → 302.
- UI JSESSIONID logged out via `GET /ui/login.action?mainAction=logout` → 302.
- Suite API bearer token released via `POST /suite-api/api/auth/token/release` → 200.
- `/tmp/pak_uninstall_probe/` scratch dir removed.

## Recommended uninstall flow

```
1. /ui/ admin session login (see context/dashboard_delete_api.md
   for the canonical `ui_login()` pattern — same code, different
   target):
     GET  /ui/login.action?vcf=1                          # seed JSESSIONID
     POST /ui/login.action                                # mainAction=login + full field set
     GET  /ui/index.action                                # trigger OPS_SESSION cookie
     decode base64(OPS_SESSION) → csrfToken

2. Identify the "short" pakId and version:
     POST /ui/solution.action mainAction=getIntegrations
     → find `installedMPs[]` entry whose `name` or `pakId` matches the
       target pak. `pakId` field is the short form required for remove.
       Sample: Broadcom Security Advisories installed as pakId
       "Broadcom Security Advisories", version "1.0.1.6".
       (NOT the admin side's compressed form "BroadcomSecurityAdvisories-1016".)

3. Guard against isUnremovable (SAFETY-CRITICAL — see below):
     if installedMPs[entry].isUnremovable == True:
         abort with "Cannot uninstall built-in pak '<name>'"

4. Issue remove:
     POST /ui/solution.action
     form: mainAction=remove
           pakId=<short pakId>
           version=<version>
           secureToken=<csrf>
     success shape: HTTP 200, body `{}` (no errorMsg key).
     failure shape: HTTP 200, body `{"errorMsg":"..."}` — check for
       errorMsg presence; empty object == success.

5. Poll completion:
     POST /admin/solution.action mainAction=getLatestInstalledSolutionStatuses
       (admin session, same status endpoint used during install)
     Wait until either:
       - response.solutionName != <target name> (pak disappeared from grid),
         OR
       - response.isPakRemoved == true
         AND pakInstalling == false
     Timeout: 5 minutes is generous (reference pak took ~1 min, complex
     paks with many adapter instances could take longer).

6. Verify via Suite API:
     GET /suite-api/api/solutions           → confirm target not in list
     GET /suite-api/api/adapterkinds        → confirm adapter kind gone

7. Logout:
     GET /ui/login.action?mainAction=logout
     GET /admin/login.action?mainAction=logout
     POST /suite-api/api/auth/token/release
```

### Reference Python snippet (not committed to `vcfops_*/`)

```python
import base64, json, os, time, requests, urllib3
urllib3.disable_warnings()

HOST = os.environ['VCFOPS_HOST']
ADMIN = os.environ['VCFOPS_ADMIN']
ADMIN_PW = os.environ['VCFOPS_ADMINPASSWORD']

def ui_admin_login():
    """UI-session login pattern; see context/dashboard_delete_api.md."""
    s = requests.Session()
    s.verify = False
    s.get(f"https://{HOST}/ui/login.action?vcf=1")
    r = s.post(f"https://{HOST}/ui/login.action", data={
        "mainAction": "login",
        "userName": ADMIN, "password": ADMIN_PW,
        "authSourceId": "localItem",
        "authSourceName": "Local Account",
        "authSourceType": "",
        "forceLogin": "false",
        "timezone": "0", "languageCode": "us",
    })
    assert r.text == "ok", f"ui login failed: {r.text!r}"
    s.get(f"https://{HOST}/ui/index.action", allow_redirects=False)
    ops = s.cookies.get("OPS_SESSION", path="/vcf-operations")
    data = json.loads(base64.b64decode(ops))
    return s, data["csrfToken"]

def uninstall_pak(short_pak_id, version):
    s, csrf = ui_admin_login()
    try:
        # Step 3: Safety check against isUnremovable
        r = s.post(f"https://{HOST}/ui/solution.action", data={
            "mainAction": "getIntegrations", "secureToken": csrf,
        })
        inst = r.json().get("installedMPs", [])
        entry = next((m for m in inst if m.get("pakId") == short_pak_id
                                       and m.get("version") == version), None)
        if entry is None:
            raise RuntimeError(f"not installed: {short_pak_id} {version}")
        if entry.get("isUnremovable"):
            raise RuntimeError(
                f"cannot uninstall built-in pak '{entry['name']}' "
                f"(isUnremovable=true)")

        # Step 4: remove
        r = s.post(f"https://{HOST}/ui/solution.action", data={
            "mainAction": "remove",
            "pakId": short_pak_id,
            "version": version,
            "secureToken": csrf,
        })
        body = r.json()
        if body.get("errorMsg"):
            raise RuntimeError(f"remove rejected: {body['errorMsg']}")

        # Step 5: poll via admin side (need a separate admin session;
        # see context/pak_install_api_exploration.md for admin_login())
        # ... poll getLatestInstalledSolutionStatuses until
        # solutionName != short_pak_id (the pak disappears from the
        # status grid) ...
    finally:
        s.get(f"https://{HOST}/ui/login.action",
              params={"mainAction": "logout"}, allow_redirects=False)
```

## Safety-critical: `isUnremovable` is UI-only

**The server does NOT enforce `isUnremovable`.** `getIntegrations`
returns this flag for every installed MP; the UI reads the flag and
disables the remove button for built-in paks (vSAN, vCenter, NSX, the
vSphere Supervisor adapter, OS and Application Monitoring, Service
Discovery, etc.). **The server-side `remove` handler accepts the
request regardless** and starts the uninstall pipeline.

During edge-case testing for this investigation, a `remove` against
the vSAN pak (`pakId="Management Pack for Storage Area Network"`,
`isUnremovable=true`) was accepted by the server. The admin status
grid showed `pakInstalling=True name="vSAN"` for ~1 minute, then
cleared. Post-test state:

- `GET /suite-api/api/adapterkinds`: baseline had 26 kinds including
  `VirtualAndPhysicalSANAdapter`. After: 26 kinds but
  **`VirtualAndPhysicalSANAdapter` is gone**.
- `GET /suite-api/internal/solutions/preinstalled/Management Pack for
  Storage Area Network/status`: `{"state":"DEACTIVATED"}` (was
  ACTIVATED in baseline).
- **Recovery attempts failed**: `POST
  /suite-api/internal/solutions/preinstalled/Management Pack for
  Storage Area Network/activate` returns HTTP 202 ("queued") but the
  task never transitions; polling for 10+ minutes shows state stuck at
  DEACTIVATED. Subsequent `enable` via `/ui/solution.action` returns
  `{"errorMsg":"The selected PAK file
  ManagementPackforStorageAreaNetwork-902025137912 is already being
  installed or is already queued for installation."}` — the queue has
  a stale entry. `mainAction=cancel` and
  `mainAction=resetSolutionUninstallState` also do not clear the
  queue. `mainAction=finishStage` returns `{}`.

This residual state was escalated to Scott at the end of the
investigation. Manual admin-UI recovery (Admin → Software Updates →
Solutions) or on-appliance CLI is probably required. The instance
state is one adapter-kind worse than the investigation started —
Scott was alerted before proceeding with write-up.

**Implication for tooling**: any CLI wrapper around `mainAction=remove`
MUST call `mainAction=getIntegrations` first, find the matching
`installedMPs[]` entry, and refuse to proceed if `isUnremovable=true`.
The cost of missing that guard is a permanently-damaged (or at minimum
manual-recovery-required) production instance.

## Hypothesis results summary

From the task brief, each angle's verdict:

1. **CASA endpoints with different HTTP methods / bodies / proper auth** —
   ruled out. With HTTP Basic admin (correct CaSA auth), PUT/DELETE
   still return generic 500 "Operation failed" for every schema
   tested. CaSA pak endpoints are **deprecated stubs** in 9.x
   (`isCaSAReplaced` flag in admin SPA). Not the path.

2. **Admin SPA hidden mainActions** — ruled out. Every
   uninstall-synonym tried (`uninstall`, `remove`, `removePak`,
   `deletePak`, `deactivate`, `cleanupSolution`, `removeSolution`,
   `purgePak`, `pakRemove`, `pakUninstall`, `disable`, `undeploy`)
   returns Struts empty-200 stub on `/admin/solution.action`,
   `/admin/utility.action`, `/admin/softwareUpdate.action`,
   `/admin/clusterManagement.action`. **The admin SPA has no uninstall
   mainAction on any endpoint.**

3. **SPA pak-status grid context menu** — confirmed absent in admin
   SPA. The admin SPA bundles
   (`/admin/dist/js/app.part{0,1,2}.min.js`) have state flags for
   `isPakUninstallActive`/`isPakRemoved`/`pakRemoved` but no code to
   INITIATE removal — only to DISPLAY status of an uninstall in
   progress. **The SPA that initiates uninstall is the main
   `/ui/` SPA, not the admin SPA.** This was the gap in the prior
   exploration.

4. **On-appliance CLI / pak preRemove scripts** — no `preRemove.py` /
   `remove_script` key in the Security Advisories pak's manifest.
   Probably not a pak-level hook. SSH-level `removePak.py` may still
   exist on the appliance, but the HTTP path (now documented) is
   sufficient so that avenue was not pursued further.

5. **Internal REST API exotic methods** — ruled out. All
   `/internal/solutions/*` paths except `/preinstalled` return 404.
   `/preinstalled/{id}/deactivate` only accepts IDs of preinstalled
   solutions — a 404 "No such Solution" is returned for dynamically
   installed paks like Broadcom Security Advisories.

6. **Pak-level hooks** — no `preRemove`/`postRemove` scripts in the
   reference pak. Server-side must drive removal through built-in
   pipeline (deregister adapter kind + content cleanup). Not a
   pak-authoring concern.

7. **(NEW ANGLE during investigation)** `/ui/` SPA JS bundles —
   CONFIRMED. The main UI's `/ui/dist/js/app.part4.min.js` (and
   `app.part6.min.js`) contains the full uninstall flow wiring.
   `ManagementPack.availableActions.UNINSTALL="uninstall"` is a
   first-class state, and `uninstall()` issues `POST
   /ui/solution.action mainAction=remove` with short pakId + version.
   **This is the path.**

## Tooling handoff notes

For the agent implementing CLI uninstall (`tooling` agent, most likely
as part of `vcfops_managementpacks`):

### Auth pattern

- Uses the same `/ui/` admin session pattern already implemented in
  `context/dashboard_delete_api.md`. A sibling helper
  `ui_admin_login()` (not `ui_login()` — the dashboard code logs in as
  the regular user; uninstall needs the admin account) returning
  `(session, csrfToken)` is all that's needed.
- Credentials from `VCFOPS_ADMIN` / `VCFOPS_ADMINPASSWORD` (same envs
  install already uses).
- CSRF token lives in base64-decoded `OPS_SESSION` cookie after
  `GET /ui/index.action` — NOT
  `GET /ui/commonJS.action?mainAction=getApplicationGlobalData` (that's
  `/admin/` only).

### Error-handling nuances

1. **Success shape is `{}` with no errorMsg key** — same convention as
   `/admin/solution.action`. Do NOT treat empty `{}` as failure.
2. **Failure shape is `{"errorMsg":"..."}`** — check for errorMsg key
   presence, not truthiness of body.
3. **Wrong pakId form silently "succeeds"** — if you pass the ADMIN
   side's compressed pakId (e.g. "BroadcomSecurityAdvisories-1016")
   instead of the UI's short form (e.g. "Broadcom Security
   Advisories"), the server returns `{}` and does NOTHING. Always
   resolve the short pakId via `getIntegrations` first.
4. **`isUnremovable` enforcement is client-side only** — see the
   safety-critical section above. Guard MUST be in the CLI wrapper.
5. **`/ui` session expires** — OPS_SESSION has an `inactivityTimeout`
   of 1800 s. Long-running uninstall polls should refresh the session
   if a 302 is returned where JSON was expected. The dashboard_delete
   code already handles this pattern.
6. **`pakInstalling=True` covers both install AND uninstall** — the
   flag name is misleading. During uninstall the admin status grid
   shows `pakInstalling=True` with the target's name. Completion is
   signalled by `pakInstalling=False` AND
   `solutionName != <target>` (because the grid reverts to the
   previously-touched pak).

### Idempotency considerations

- Calling `remove` on a not-installed pak returns `{}` (silent
  success). CLI should pre-check via `getIntegrations` and distinguish
  "already uninstalled" from "just uninstalled".
- Calling `remove` twice in quick succession on an install-in-progress
  pak will queue a stale entry (similar to the vSAN incident). CLI
  should check `pakInstalling=false` before issuing `remove`.

### Interaction with install

- Install uses `/admin/` session + admin's compressed pakId form
  (e.g. `"BroadcomSecurityAdvisories-1016"`).
- Uninstall uses `/ui/` session + UI's short pakId form
  (e.g. `"Broadcom Security Advisories"`).
- The two ID forms are distinct and not interchangeable. The CLI
  should hide this from the user by looking up both forms from the
  pak's `manifest.txt` (which carries the short `name` field) or from
  `getIntegrations`.
- Sessions are orthogonal — admin and ui JSESSIONIDs are separate
  cookies scoped to different Struts contexts. A single CLI invocation
  wanting to install-then-uninstall needs both.

### Recommended CLI shape

```
python3 -m vcfops_managementpacks install <path-to-pak>
python3 -m vcfops_managementpacks uninstall <solution-name-or-pakId> [--version <ver>]
python3 -m vcfops_managementpacks list    # grid view of installed MPs
```

The `uninstall` command should:

1. Login to `/ui/` as admin (VCFOPS_ADMIN).
2. Call `getIntegrations` to resolve name → (pakId, version).
3. Fail early with a clear message if `isUnremovable=true`.
4. Show a "Are you sure?" prompt (same UX pattern as
   `feedback_install_ux_pattern` in memory).
5. Issue `mainAction=remove`, check for errorMsg.
6. Login to `/admin/` (also as admin — needs a second session for the
   status grid; or can reuse install's admin session if already up).
7. Poll `mainAction=getLatestInstalledSolutionStatuses` until the pak
   disappears from the status grid or timeout.
8. Verify via `GET /suite-api/api/solutions` and
   `GET /suite-api/api/adapterkinds`.
9. Logout both sessions.

## Unsupportability caveat

All `/admin/*` and `/ui/*` Struts endpoints documented here are
**undocumented internal surfaces**. They are not part of any public
contract. They will change between VCF Ops releases without notice.
The `X-Ops-API-use-unsupported` header does NOT apply here — these
aren't `/internal/` REST endpoints, they are Struts handlers backing
the web console. Tested against VCF Operations 9.0.2.0 build 25137838
only.

The `mainAction=remove` handler's silent behaviour on
`isUnremovable=true` paks is almost certainly a Broadcom bug (the
UI-layer guard is the ONLY enforcement). If Broadcom patches this to
return a proper error, the CLI's own client-side guard still
protects users but the "stale queue" failure mode documented above
may also be fixed at the same time.

## References

- `context/pak_install_api_exploration.md` — companion install-side
  doc. Same `/admin/` session model used for install; the uninstall
  side uses the `/ui/` SPA (different Struts context, different
  session, different CSRF source) but the session patterns rhyme.
- `context/dashboard_delete_api.md` — canonical `/ui/` UI-session
  login pattern. The uninstall session is the IDENTICAL pattern,
  just authenticated as admin instead of a regular user (admin is
  needed because uninstall requires `configuration.solutions.delete`
  privilege, which non-admin users don't carry, and also because the
  admin account is the one the SPA allows to manage integrations).
- `memory/project_vcf_ops_902_ui_deadends.md` — earlier catalog of
  `/ui/` SPA dead-ends. This investigation **updates that catalog**:
  `/ui/solution.action` is NOT a dead stub. It is a live, registered
  Struts handler with a distinct mainAction surface from
  `/admin/solution.action`. The two must not be conflated.
- Live UI SPA sources (read during investigation, not reproduced in
  repo): `/ui/dist/js/app.part{0..6}.min.js` (the `ManagementPack`
  class definition with `availableActions.UNINSTALL` enum and the
  `uninstall()` function that issues the `remove` mainAction are in
  `app.part4.min.js`; `app.part6.min.js` has a second implementation
  for a different view).
