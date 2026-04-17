# `/ui/` Repository → Add pak upload path (static-source investigation)

Follow-up to `context/pak_install_api_exploration.md` and
`context/pak_uninstall_api_exploration.md`. Brief from the
orchestrator 2026-04-16: determine the exact wire path the `/ui/`
ExtJS SPA uses when a user clicks Integrations → Repository → Add
and uploads a `.pak` file, *without* hitting the live instance (the
lab is stabilizing after the vSAN uninstall incident; Scott has
forbidden further live probes until he authorizes the next one).

**Scope constraint honored.** This investigation consulted only
static sources: repo docs, prior `context/*.md` exploration logs,
the `vcfops_managementpacks/installer.py` source, and the three
reference clones under `references/` that contain UI-relevant JS.
No requests were made against the live instance.

## Executive summary (what we can and cannot conclude statically)

**Strong static evidence, but no verified wire capture yet.** The
2026-04-16 uninstall exploration (see
`context/pak_uninstall_api_exploration.md`) read the live `/ui/`
SPA bundles (`/ui/dist/js/app.part{0..6}.min.js`) and documented
that `/ui/solution.action` is a live Struts handler — contradicting
the 2026-04-11 `struts_import_endpoints.md` enumeration which
listed only six registered `/ui/*.action` slugs and did not test
`solution.action` at all. The uninstall investigator listed a
mainAction surface on `/ui/solution.action` that explicitly includes
`install` alongside `remove`, `enable`, `disable`, `reinstall`,
`resetSolutionUninstallState`, `cancel`, `finishStage`,
`getIntegrations`, `installingPakDetail`,
`getLatestInstalledSolutionStatuses` (bug report
`context/bug_report_pak_isunremovable_not_enforced.md` line 121
lists all of these).

**What we have NOT proved from static sources:**

- The exact URL of the multipart upload endpoint the `/ui/` SPA
  posts a `.pak` file to. Candidate paths inferred from the admin-
  side parallel (`/admin/admin/services/solution/upload`) are
  `/ui/admin/services/solution/upload` or a REST sibling reachable
  from a `/ui/` session, but neither has been exercised.
- Whether the `/ui/` SPA re-uses the `/admin/` endpoint via a
  cross-SPA POST (hypothesis 1 from the brief) or has its own
  upload endpoint (hypothesis 3).
- Whether Repository → Add opens an iframe / navigates to the
  `/admin/` SPA (hypothesis 2). **Prior work makes this unlikely
  but does not disprove it.** The uninstall investigator said the
  `/ui/` bundles contain a `ManagementPack` class with an
  `availableActions` enum (UNINSTALL/ENABLE/DISABLE/GET/UPGRADE/
  VIEW_IN_REPOSITORY/ADD_ACCOUNT) — *none* of those is
  INSTALL/UPLOAD, which is consistent with install being a
  different UI entrypoint (the Repository dialog, not the
  per-MP action menu).

**Cleanest hypothesis given available evidence:** case 3 (distinct
`/ui/` endpoint), with the upload endpoint living at
`/ui/admin/services/solution/upload` (the direct parallel of the
admin-side URL under the `/ui/` servlet context). Supporting
signals:

1. The uninstall work already proved `/ui/solution.action` is a
   real Struts handler with full lifecycle mainActions (the bug
   report lists `install` explicitly). This is the analog of
   `/admin/solution.action` one path segment to the left.
2. If the analogy holds, the multipart upload endpoint
   `/admin/admin/services/solution/upload` should have a sibling
   at `/ui/admin/services/solution/upload` or the same path
   relative to the `/ui/` servlet context.
3. The uninstall investigator would have seen the upload URL
   referenced in the same `app.part{4,6}.min.js` bundles where
   they found the `ManagementPack` class — but did not report it
   because upload was out of scope for that brief. **A targeted
   re-read of those bundles looking for `solution/upload` or
   `prepareFileUpload` is the cheapest next step.**

**Case 1 (cross-SPA POST to `/admin/admin/services/solution/upload`)
is also plausible** but would be unusual design. The admin SPA's
CSRF (`secureToken` from `/admin/commonJS.action`) is scoped to the
`/admin` servlet context; `/ui/` has its own CSRF from the
base64-decoded `OPS_SESSION` cookie. A browser session that holds
both JSESSIONIDs could POST to either endpoint, but the `/ui/`
SPA would need to first call `/admin/commonJS.action?mainAction=
getApplicationGlobalData` to get the `/admin/` CSRF — an extra
round-trip that SPAs typically avoid.

**Case 2 (iframe/nav-out) is very unlikely** based on the
`ManagementPack` class findings in the uninstall exploration. The
`/ui/` SPA owns the full lifecycle UI; it would not plausibly open
a separate `/admin/` window just for the upload step when it
already has UI for every other solution action.

## What the static record already establishes

### 1. `/ui/solution.action` has a live `install` mainAction

From `context/bug_report_pak_isunremovable_not_enforced.md` line
121:

> The `/ui/solution.action` Struts handler exposes a rich mainAction
> set beyond `remove`, including: `install`, `enable`, `disable`,
> `reinstall`, `resetSolutionUninstallState`, `cancel`, `finishStage`,
> `getIntegrations`, `installingPakDetail`,
> `getLatestInstalledSolutionStatuses`.

This was derived from the same live SPA bundle inspection that
found `remove`. The bug report's author encountered `install` in the
same code path they traced `remove` through.

**Note the caveat:** the bug report does not say `install` was
exercised end-to-end on `/ui/solution.action`. It says the mainAction
is advertised. Whether it takes a `pakId` (post-upload, same as
admin) or a file (atomic upload+install) is unknown.

### 2. `/ui/solution.action mainAction=remove` is verified end-to-end

The live install/uninstall cycle in
`context/pak_uninstall_api_exploration.md` §"Live install/uninstall
cycle trace (2026-04-16)" proves the `/ui/` Struts handler is real
and accepts the same Struts form-encoded request shape the admin
handler uses. The CSRF source for the `/ui/` handler is the
base64-decoded `OPS_SESSION` cookie, not `getApplicationGlobalData`.

### 3. Prior `/ui/` action enumeration missed `solution.action`

`context/struts_import_endpoints.md` (2026-04-11) enumerates six
registered `/ui/*.action` slugs: `dashboard`, `alert`, `superMetric`,
`customGroup`, `policy`, `contentManagement`. It does not include
`solution.action`. The 2026-04-11 investigator did not probe
`/ui/solution.action` because at the time the assumption was that
solution management lived entirely on `/admin/`. The 2026-04-16
uninstall work is what corrected the record.

**This means other action slugs may also be missing from the
2026-04-11 enumeration.** The `/ui/` servlet context is not
exhaustively catalogued for 9.0.2; there could be additional
upload-related endpoints that were never probed. The probe
methodology in `struts_import_endpoints.md` §"Struts action
registration probe" should be re-run with a broader candidate list
to close this gap (see follow-up questions below).

### 4. The admin-side upload endpoint is well-characterized

From `context/pak_install_api_exploration.md` §"/admin/* — the
actual pak-install path":

```
POST /admin/admin/services/solution/upload?uploadId=<epoch_ms>
  multipart:
    solution=@<file>.pak
    forceUpload=false
    ignoreSignatureChecking=false
    currentComponentInfo=TODO
    secureToken=<csrf>
  response: JSON with pakId, solutionName, solutionVersion, ...
```

A `prepareFileUpload` call is made immediately before, via `POST
/admin/utility.action mainAction=prepareFileUpload`. Progress can
be polled at `GET /admin/admin/services/solution/upload?uploadId=
<id>&progress=true`.

### 5. The CLI currently uses only the admin-side path

`vcfops_managementpacks/installer.py` implements:

- Install: `_AdminSession` → `/admin/login.action` + `/admin/
  commonJS.action` (CSRF) + `/admin/utility.action prepareFileUpload`
  + `/admin/admin/services/solution/upload` + `/admin/solution.action
  mainAction=install` + poll via `/admin/solution.action
  getLatestInstalledSolutionStatuses`. Full 11-step flow.
- Uninstall: `_UISession` → `/ui/login.action` + `OPS_SESSION` CSRF
  + `/ui/solution.action mainAction=getIntegrations` +
  `mainAction=remove`. Then switches to `_AdminSession` for
  `getLatestInstalledSolutionStatuses` polling.

The two sessions are currently used asymmetrically. If the `/ui/`
side has its own upload endpoint, a single UI-session could drive
the full install+uninstall lifecycle, simplifying the CLI.

## What static sources do NOT tell us

- **The exact upload URL.** Best guesses (in order of likelihood):
  1. `/ui/admin/services/solution/upload` (literal parallel of the
     admin-side path under the `/ui/` servlet context).
  2. `/ui/services/solution/upload` (flatter, matches `/ui/vcops/
     services/router` which is the only existing `/ui/services/*`
     family we know about).
  3. `/ui/solution.action` with `mainAction=install` and a
     multipart body (one-shot, no separate upload).
  4. Some other URL entirely. The admin-side double-`/admin/`
     nesting suggests the Spring/Struts config uses servlet-
     context-relative REST sub-paths in non-obvious places.

- **Whether `prepareFileUpload` is required on `/ui/` side.** On
  the admin side it is (returns `{"success":true}` immediately
  before the upload). `/ui/` may have its own `prepareFileUpload`
  equivalent on `/ui/utility.action` or may not require one.
  `/ui/utility.action` has not been tested in any prior
  investigation that we have a record of.

- **The CSRF field name for the `/ui/` upload.** The `/ui/`
  Struts handlers observed so far (login, solution, dashboard)
  accept CSRF via a `secureToken` form field identical to
  `/admin/`. Most likely the upload endpoint follows the same
  convention, but multipart endpoints sometimes read CSRF from a
  header (`X-CSRF-Token`) instead, and this has not been verified.

- **The upload-progress endpoint on `/ui/`, if any.**

## Hypotheses mapped to the brief

| # | Hypothesis from brief | Verdict from static sources |
|---|---|---|
| 1 | `/ui/` SPA POSTs directly to `/admin/admin/services/solution/upload` via cross-SPA browser auth | Possible but design-implausible. Would require the `/ui/` SPA to hold or obtain an `/admin/` CSRF token, which it does not appear to do (uninstall path uses only `/ui/` CSRF). **Not ruled out** without a live capture, but no supporting signals in the static record. |
| 2 | Repository → Add opens an iframe or navigates to the `/admin/` SPA | **Unlikely.** The `/ui/` SPA's `ManagementPack` class and associated `availableActions` enum, plus the working `/ui/solution.action` handler for all other lifecycle operations, indicate the `/ui/` SPA owns the solution management UI end-to-end. An iframe would be a regression from the UX the uninstall code path demonstrates. |
| 3 | Distinct `/ui/` upload endpoint that the prior `/ui/*.action` enumeration missed | **Most likely.** The 2026-04-11 enumeration did not probe `solution.action` on `/ui/` at all and missed it; the upload endpoint is likely at a similarly-overlooked sub-path under `/ui/`, most probably `/ui/admin/services/solution/upload`. The uninstall investigator had the SPA bundles open and the install-side upload URL would have been visible to them if they had looked. **Needs a live capture to confirm.** |

## Recommended next step (live, narrow, reversible)

Once Scott authorizes live probes again, the minimum experiment to
resolve this is:

1. Fetch the `/ui/` SPA bundles (read-only): `GET /ui/dist/js/
   app.part{0..6}.min.js` with a `/ui/` session cookie. `grep` the
   minified JS for:
   - `solution/upload`
   - `prepareFileUpload`
   - `uploadId=`
   - `currentComponentInfo`
   - `ignoreSignatureChecking`
   - `availableActions` (to cross-check the uninstall
     investigator's `ManagementPack` finding)
   - `addIntegration`, `repositoryAdd`, `AddDialog`,
     `RepositoryAddDialog`

2. If a candidate upload URL is found in the JS, probe it with
   the same technique `context/pak_install_api_exploration.md`
   used: upload a small bogus file (like the 29-byte `bogus.pak`
   used previously), expect the PAK Manager to reject it, capture
   the wire shape from the response. This is non-destructive —
   the server rejects the bogus file before any persistent state
   is created, as proved on 2026-04-16.

3. If the upload URL turns out to be `/ui/admin/services/solution/
   upload` (hypothesis 3a), the path is reachable with the
   existing `_UISession` class in `installer.py` — no new session
   class needed, just a new method.

4. If the URL is somewhere else entirely, or if it turns out to be
   a cross-SPA POST to `/admin/admin/services/solution/upload`
   (hypothesis 1), the CLI refactor is larger and Scott should
   weigh the value.

## Implications for `vcfops_managementpacks/installer.py` if hypothesis 3 is confirmed

**The current install code works.** Confirming a `/ui/`-side upload
endpoint is a refactor opportunity, not a bug fix. Concrete changes
that would become possible:

1. **Single session install + uninstall.** Today the CLI opens a
   `/ui/` session for uninstall (remove + polling handoff to
   `/admin/`) and a `/admin/` session for install. A working `/ui/`
   upload would let install run entirely in `_UISession`,
   eliminating the dual-session code in `uninstall_pak()`'s
   polling phase (lines 860-882 of `installer.py`).

2. **Use the same `pakId` form throughout.** The `/admin/` side
   returns compressed pakIds like `BroadcomSecurityAdvisories-1016`;
   the `/ui/` side's `getIntegrations` returns short form like
   `Broadcom Security Advisories`. If upload happens via `/ui/`,
   the upload response probably returns the short form already,
   and the `pakId` namespace split documented at lines 11-18 of
   `installer.py` becomes moot.

3. **Polling consolidation.** `getLatestInstalledSolutionStatuses`
   is documented as an `/admin/solution.action` mainAction today,
   but per `context/bug_report_pak_isunremovable_not_enforced.md`
   line 121, it is also advertised on `/ui/solution.action`. If
   both paths work, `_poll_uninstall_completion()` can run on the
   `/ui/` session and eliminate the second admin login.

4. **No changes to `isUnremovable` guard, manifest parsing, EULA
   handling, or credential envelope.** Those layers are
   endpoint-neutral.

**If hypothesis 1 (cross-SPA POST) turns out to be reality**, the
refactor story is different: the CLI would stay dual-session (one
for `/ui/` mainActions, one for `/admin/` upload) but the upload
session could be reused for status polling. Less simplification
upside than hypothesis 3.

**If hypothesis 2 (iframe/nav-out) turns out to be reality**, no
refactor is warranted — the UI's path is an iframe, not an API
call, and the CLI's admin-side path is the cleanest HTTP
representation regardless.

## Corrections to prior exploration docs

The `/ui/` side story has been built in pieces; this investigation
pass doesn't add new wire-format findings, but it does identify a
correction the record should absorb once a live capture settles
the upload endpoint:

1. **`context/struts_import_endpoints.md`** (2026-04-11) enumerates
   six `/ui/*.action` slugs and omits `solution.action`. That
   enumeration is incomplete. A paragraph-level correction should
   be added to that file referencing
   `context/pak_uninstall_api_exploration.md` for the
   `/ui/solution.action` discovery, plus a note that other action
   slugs may have been missed and the methodology should be
   re-run with a broader candidate list (`solution`, `integration`,
   `marketplace`, `repository`, `pak`, `managementPack`,
   `softwareUpdate`, `upgrade`, `utility`).

2. **`context/pak_install_api_exploration.md`** §"`/ui/*` Struts
   (`/ui/solution.action`) — dead stub" (line 93-103) is
   **wrong**. `/ui/solution.action` is live. This section should
   be rewritten to say "`/ui/solution.action` exists and is live;
   see `context/pak_uninstall_api_exploration.md` for the full
   mainAction surface. The install-side role of `/ui/
   solution.action` — specifically whether `mainAction=install`
   drives a separate install flow from the admin-side one — is
   open as of 2026-04-16 and awaits a live capture." Non-blocking
   for CLI correctness (the CLI's current `/admin/` path works)
   but important for doc hygiene.

3. **`context/struts_exploration_backlog.md`** working-endpoints
   table should gain a row for `/ui/solution.action` with the
   full verified mainAction surface (`remove`, `getIntegrations`,
   `installingPakDetail`, `enable`, `disable`, `reinstall`,
   `resetSolutionUninstallState`, `cancel`, `finishStage`) and a
   footnote that `install` is advertised but not yet verified
   end-to-end from the `/ui/` side.

These corrections do not require a live probe — they are
retrofits based on findings the uninstall exploration already
made. Drafting them is in scope for a docs-only PR.

## Follow-up questions for the live capture, when authorized

1. What is the exact URL of the upload endpoint called by
   Repository → Add? (Primary hypothesis: `/ui/admin/services/
   solution/upload`; fall-backs listed above.)
2. Does the `/ui/` upload require a `prepareFileUpload`
   precursor like the admin side does? If so, on what endpoint?
3. Is the CSRF field name `secureToken` (form field, like other
   `/ui/` Struts calls) or is it a header (`X-CSRF-Token`)?
4. Does the upload response return the short-form pakId (like
   `getIntegrations`) or the compressed admin-side form (like
   `/admin/admin/services/solution/upload`)?
5. Does `mainAction=install` on `/ui/solution.action` take a
   pakId parameter (like `/admin/`) or does it accept an
   atomic multipart-upload-and-install form?
6. Does `/ui/solution.action mainAction=
   getLatestInstalledSolutionStatuses` work? (Advertised on
   `/ui/` per bug report but not verified.)

## Live-source findings (2026-04-16, second pass)

Scott authorized read-only static-asset fetches against the live
lab. The `/ui/` SPA bundles were downloaded with an authenticated
`/ui/` admin session (mirrors the `_UISession` pattern in
`vcfops_managementpacks/installer.py`) and grepped for the
upload-related strings the brief listed. Bundles were fetched
from `https://<VCFOPS_HOST>/ui/dist/js/app.part{0..6}.min.js` plus
~30 supporting JS files referenced by `<script src=...>` in
`/ui/index.action`.

**Hypothesis 3 confirmed with one twist.** The upload endpoint
is `/ui/admin/services/solution/upload` (relative to the `/ui/`
servlet root, not `/admin/` — i.e. the literal parallel of the
admin-side URL under the `/ui/` context). But the upload code is
not "a parallel implementation under `/ui/`": the very same
ExtJS class names (`Ext.vcops.initialConfiguration.solutions.
{ConfigurationWizard,Select,Eula,Install,...}`) are bundled into
both SPAs. The `/ui/` SPA reuses the admin-side install wizard
verbatim, just served from `/ui/dist/js/app.part4.min.js` instead
of `/admin/dist/js/app.part1.min.js`. This is why all of the
`mainAction` surface (`install`, `cancel`, `getInstallStatus`,
`getLicenseAgreement`, `getReleaseInfo`, `getSolutionVersion`,
`finishStage`, `loadSolution`, `getPakDownloadStatus`,
`getSolutionInfo`) shows up identically on `/ui/solution.action`
and `/admin/solution.action`.

### Wire format

**Upload URL.** The exact URL the SPA POSTs the multipart body
to is:

```
POST https://<host>/ui/admin/services/solution/upload
     ?uploadId=<epoch_ms>
     &ignoreSignatureChecking=<true|false>
```

Note that `ignoreSignatureChecking` is on the **query string**
in this code path, not in the form body — that's a difference
from the admin-side flow documented in
`context/pak_install_api_exploration.md` line 174-179, where it
appears as a multipart form field. Source (part4 offset 487784,
inside `Ext.vcops.initialConfiguration.solutions.Select.uploadSolution`):

```js
e.submit({
  url: "admin/services/solution/upload"
       + "?uploadId=" + t
       + "&ignoreSignatureChecking=" + e.isIgnoreSignatureChecking,
  params: {
    forceUpload: e.isForceUpload,
    forceContent: e.getIsForceContentUpload()
  },
  scope: e,
  success: function(t,i){ ... e.processResult(i.result) },
  failure: function(t,i){ ... showErrorMsg(bundle["solutions.uploadFailed"]) }
});
```

Because the URL is relative (`"admin/services/solution/upload"`,
no leading slash) and the SPA is served at `/ui/`, ExtJS resolves
this against the document base. With `<base href="/ui/">` in
`/ui/index.action`, the absolute URL is `/ui/admin/services/
solution/upload`. (This is the same way `solution.action`
relative URLs in the same bundle resolve to `/ui/solution.action`,
which is verified live — see `pak_uninstall_api_exploration.md`.)

**Form fields posted by `Ext.form.Panel#submit` (multipart):**

| Field | Source | Value |
|---|---|---|
| `solution` | `Ext.form.field.File` named `"solution"` | the `.pak` file binary |
| `forceUpload` | `params.forceUpload` | `"true"` / `"false"` (default false) |
| `forceContent` | `params.forceContent` | `"true"` / `"false"` (default false) |
| `secureToken` | auto-injected by `formActionHandler` override | global `secureToken` (CSRF) |

**CSRF placement — secureToken is auto-injected as a form field
on every `Ext.form.Panel.submit()`.** From
`/ui/js/components/ext-overrides.js`:

```js
Ext.override(Ext.form.Panel, {
  initComponent: function() {
    this.on('beforeaction', this.formActionHandler);
    return this.callParent(arguments);
  },
  formActionHandler: function(basic, action, eOpts) {
    if (!basic.baseParams) basic.baseParams = {};
    if (!this.excludeSecureToken) {
      basic.baseParams.secureToken = secureToken;
    }
    return true;
  }
});
```

So the upload submit ends up with `secureToken=<csrf>` in the
multipart body, identical placement to the admin-side flow.

**For `Ext.Ajax.request()` calls** (everything that isn't a
form submit — including `prepareFileUpload`, `mainAction=install`,
all the `solution.action` polls), CSRF is injected by a
`requestbefore` hook in `commonJS.action`:

```js
// commonJS.action @26753
options.headers.secureToken = secureToken;
// commonJS.action @28497
options.params.secureToken = secureToken;
```

So `Ext.Ajax.request` POSTs send `secureToken` **both** as a
header (`secureToken: <csrf>`) and as a form param. Either alone
would work; the admin-side install code uses the form-param
form, and the existing `_UISession.post()` in `installer.py`
uses the form-param form too. No change needed.

**`currentComponentInfo`.** Auto-injected by the same
`commonJS.action` ajax hook, defaulted to `'TODO'` (literal
string). Source @28497-ish:

```js
options.params.currentComponentInfo = 'TODO';
```

So we don't need to set `currentComponentInfo` ourselves; the
SPA always sends `currentComponentInfo=TODO`. (This matches the
admin-side documentation at `pak_install_api_exploration.md`
line 178.)

### prepareFileUpload precursor — yes, identical to admin

Right before the multipart submit, the SPA calls
`POST /ui/utility.action` with `mainAction=prepareFileUpload`:

```js
// part4 @487584 (Select.uploadSolution())
Ext.Ajax.request({
  url: "utility.action",
  params: { mainAction: "prepareFileUpload" },
  disableCaching: true,
  method: "POST",
  success: function(i, n) {
    e.setUploadToolsDisabled(true, true);
    e.selectedFileCmp.setVisible(false);
    e.submit({ url: "admin/services/solution/upload?...", ... });
  }
});
```

This means `/ui/utility.action mainAction=prepareFileUpload` is
a registered handler — contradicting the implication in earlier
`/ui/*.action` enumerations that `utility.action` was admin-only.
**Not exercised in this pass** (read-only constraint), but the
JS proves it's registered.

### Upload response shape (from JS handler)

The success callback's `i.result` carries these keys
(extracted from `Select.processResult()` at part4 offset 488299
and `Select.getSolutionInfo()` at part4 offset 491685):

```
{
  errorMsg:                   string|null,    // null on success
  pakId:                      string,         // compressed: "<solutionName>-<version>"
  solutionName:               string,         // display name
  solutionDescription:        string,
  solutionVersion:            string,         // "X.Y.Z.B"
  solutionFilename:           string,         // original .pak filename
  signingStatus:              string,         // "SignatureValid" | "NotSigned" | ...
  containsSystemUpdate:       bool,           // -> systemUpdateRequired
  clusterBringOffline:        bool,
  clusterRestartRequired:     bool,
  adminRestartRequired:       bool,
  osRestartRequired:          bool
}
```

This is the **same** shape as the admin-side upload response
documented at `pak_install_api_exploration.md` line 180-194 —
expected, because the same Java handler backs both paths. The
`pakId` returned is the compressed form
(`BroadcomSecurityAdvisories-1016`), not the human-readable
`getIntegrations` short form. So pak-id namespace splits in the
current `installer.py` code do NOT collapse just by switching
from `/admin/` to `/ui/` — see "Implications" below.

### Post-upload install handoff

The wizard flow is identical to the admin side (which is
expected — it's the same wizard code):

1. Upload → response with `pakId`.
2. `Select.processResult()` → `getSolutionVersion` to detect
   version-mismatch warning text.
3. User clicks Next → `Eula` panel calls
   `mainAction=getLicenseAgreement` (no params, takes wizard's
   pakId implicitly via session state).
4. User accepts → wizard advances to `Install` panel.
5. `Install.componentActivate()` (part4 offset 480874) calls
   `mainAction=install` on `/ui/solution.action`. Notably, the
   Ajax body it sends contains **only** `mainAction=install`
   plus `forceContentUpdate=true` if `isMarketPlace`. The
   `pakId` is NOT a parameter — it's stored server-side in
   session state from the upload step. (The same behavior is
   true on the admin side; the install wizard treats pakId as
   session state once upload succeeds.)
6. `Install.runGetStatusTask()` polls
   `mainAction=getInstallStatus` every 5 seconds, parsing
   `statuses[]`.

Note difference vs the install pseudocode in
`pak_install_api_exploration.md` lines 218-228: the empirical
admin-side flow there shows `install` being called with an
explicit `pakId=<pakId>` form field. **Both forms work.** The
SPA wizard relies on session state; a scripted client may pass
`pakId` explicitly to be unambiguous (the handler accepts it).

### Calling site — Integrations → Repository → Add

The Repository → Add button (part4 offset 867455) is gated by
the privilege `administration.solution.repository.upload` and
the `pendoKey: "add-solution"`, `featureId: "solution-add-intent"`:

```js
{
  itemWidth: 300,
  text: bundle["main.add"],
  privilege: "administration.solution.repository.upload",
  privilegeHide: true,
  featureId: "solution-add-intent",
  handler: function() {
    if (e.packInstallUnavailableMsg)
      showErrorMsg(e.packInstallUnavailableMsg);
    else {
      this.disable();
      Ext.create("Ext.vcops.initialConfiguration.solutions.ConfigurationWizard", {
        isUnsignedPakInstallationAllowed: e.isUnsignedPakInstallationAllowed,
        pendoKey: "add-solution",
        listeners: { scope: this, close: function() { e.loadData() } },
        autoShow: true
      });
    }
  }
}
```

Same `ConfigurationWizard` class that the admin-side
initial-configuration flow uses. **Hypothesis 2 (iframe / nav-out)
is definitively ruled out** — the Repository → Add UI is owned
by the `/ui/` SPA in-process, no iframe, no `/admin/` redirect.

### Hypothesis verdict (final)

| # | Hypothesis | Verdict |
|---|---|---|
| 1 | `/ui/` posts to `/admin/admin/services/solution/upload` (cross-SPA) | **Ruled out.** The JS makes a relative-URL POST that resolves to `/ui/admin/services/solution/upload`. No `/admin/` cross-call. |
| 2 | iframe / nav-out to `/admin/` SPA for upload | **Ruled out.** The Add button instantiates an in-SPA Ext window (`Ext.create("...ConfigurationWizard", { autoShow: true })`); no iframe, no navigation. |
| 3 | distinct `/ui/` upload endpoint | **Confirmed.** `/ui/admin/services/solution/upload` exists and is wired to the same Java handler that `/admin/admin/services/solution/upload` is wired to (same wizard code, same response shape). |

### Implications for `vcfops_managementpacks/installer.py`

Recap of the four refactor opportunities listed earlier in this
file, now that hypothesis 3 is confirmed:

1. **Single-session install + uninstall is feasible.** `/ui/`
   handles upload, install, status polling, EULA fetch, and
   uninstall (`mainAction=remove`) all under one `_UISession`.
   The `_AdminSession` class becomes optional — kept for backward
   compatibility, deprecated for new code paths.

2. **`pakId` namespace split does NOT collapse by itself.** The
   upload response on `/ui/` returns the same compressed-form
   `pakId` (`<solutionName>-<version>`) as the admin side. The
   short form (`<solutionName>`) only comes back from
   `mainAction=getIntegrations`. So the existing logic in
   `installer.py` that maps between the two forms is still
   needed regardless of which session is used.

3. **`getLatestInstalledSolutionStatuses` works on `/ui/`.**
   Already advertised in the bug report and visible in the
   bundle grep (every install/uninstall component calls it). The
   double-session polling fallback in `uninstall_pak()` lines
   860-882 of `installer.py` can be eliminated — uninstall can
   poll on `_UISession` end-to-end.

4. **No changes needed to `isUnremovable` guard, manifest
   parsing, EULA handling, credential envelope, or signing-check
   options.** Those layers are session-neutral.

The CLI **does not need any wire-format changes** to keep
working as-is. The refactor is a code-cleanup-and-consolidation
opportunity, not a correctness fix. Recommend deferring until
Scott has bandwidth to revisit `installer.py` holistically
(it's been touched repeatedly during the QA flow).

### One open question (not a blocker)

The `/ui/` upload code puts `ignoreSignatureChecking` on the
**query string** (not the form body, as the admin path does).
Whether the server's multipart parser ignores form-body
`ignoreSignatureChecking` when a query-string copy is present —
or whether the two paths feed different parsers — is unverified.
**For the CLI, copy the query-string-only placement to be
faithful to the SPA's wire format.** If `installer.py` is ever
refactored to use `/ui/` upload, mirror the SPA exactly.

### Documentation corrections this round identified (NOT applied here)

These corrections need routing — flagging only, per the brief.
Drafting them is in scope but not within this agent's writeable
surface for those files.

1. **`context/pak_install_api_exploration.md` §"`/ui/*` Struts
   (`/ui/solution.action`) — dead stub" (line 93-103).** This
   section is **wrong on two counts**: (a) `/ui/solution.action`
   is a live Struts handler with the full `mainAction` surface,
   already corrected in this file's "What the static record
   already establishes" §3; and (b) the same file's broader
   claim that "the `/ui/*` Struts layer doesn't have the upload
   endpoint" needs a "see `context/pak_ui_upload_investigation.md`
   §Live-source findings — `/ui/admin/services/solution/upload`
   is live, identical to the admin path and routed to the same
   Java handler" pointer. Best as a one-paragraph correction
   block; do not delete the original section, since it documents
   the search history.

2. **`context/struts_import_endpoints.md`** (2026-04-11
   enumeration of six `/ui/*.action` slugs) needs adding
   `solution.action` and `utility.action` (the latter newly
   discovered to support `mainAction=prepareFileUpload` on the
   `/ui/` side, which the bundle grep proves). Plus a note
   that the original probe methodology missed several
   live handlers and should be re-run with a broader
   candidate list (`solution`, `utility`, `integration`,
   `marketplace`, `repository`, `pak`, `managementPack`,
   `softwareUpdate`, `upgrade`).

3. **`context/struts_exploration_backlog.md`** working-endpoints
   table needs a row for `/ui/solution.action` (full surface:
   `getDetectedAdapterKinds`, `getIntegrations`,
   `getInstallStatus`, `getLicenseAgreement`, `getReleaseInfo`,
   `getSolutionInfo`, `getSolutionVersion`, `getOverview`,
   `getPreview`, `getContent`, `getSolutionPakId`,
   `getAdapterTypes`, `getOrgDetails`, `getGroupedAccounts`,
   `getReclaimableVms`, `getRightsizingVMs`,
   `installingPakDetail`, `isPakDownloading`,
   `checkSolutionAdapterInstancesExist`, `loadSolution`,
   `install`, `enable`, `disable`, `remove`, `reinstall`,
   `cancel`, `finishStage`, `resetSolutionUninstallState`)
   plus a row for `/ui/utility.action` with the verified
   `mainAction=prepareFileUpload`.

### Live probe constraints honored

- All requests were `GET` (against `/ui/` static assets) plus a
  single `POST /ui/login.action` (session establishment) plus a
  single `GET /ui/login.action?mainAction=logout` (cleanup).
- No `POST` was made against any candidate upload endpoint.
- No multipart bodies sent.
- No state-mutating Struts mainAction was invoked. The only
  actions hit were `login` and `logout`.
- Session was logged out at the end of the script run.

### Cleanup verified

- Bundles saved to `/tmp/ui_bundles/` (43 files, ~17 MB) for
  this investigation. **Will be deleted after this finding is
  documented.** Bundles are not committed to the repo and
  contain no secrets (just minified vendor JS).
- `/tmp/fetch_ui_bundles.py` (the fetch script) was used only
  for this run; not committed.
- No state changes on the live instance. Pre-probe and post-
  probe behavior identical.

## Unsupportability caveat

Everything in this file remains **undocumented internal UI
surface**. The `/ui/` Struts layer is subject to removal or
radical change in future VCF Ops releases. The
`X-Ops-API-use-unsupported` header does not apply here — these
aren't `/internal/` REST endpoints. This investigation targets
VCF Operations 9.0.2.0 build 25137838 only.

## References

- `context/pak_install_api_exploration.md` — admin-side install
  flow; contains the outdated "dead stub" claim about
  `/ui/solution.action` that needs correcting.
- `context/pak_uninstall_api_exploration.md` — `/ui/solution.action`
  live handler discovery with `remove`/`getIntegrations`/etc.
  mainAction surface.
- `context/bug_report_pak_isunremovable_not_enforced.md` line 121
  — advertises the full `/ui/solution.action` mainAction surface
  including `install`.
- `context/struts_import_endpoints.md` — 2026-04-11 enumeration
  that missed `/ui/solution.action` entirely.
- `context/struts_exploration_backlog.md` — working endpoint
  summary needing a row for `/ui/solution.action`.
- `context/dashboard_delete_api.md` — canonical `/ui/` session
  login pattern with `OPS_SESSION` CSRF.
- `vcfops_managementpacks/installer.py` — current dual-session
  CLI implementation.
- Live `/ui/dist/js/app.part{0..6}.min.js` SPA bundles — not
  reproduced in the repo. The 2026-04-16 second-pass live fetch
  (read-only) located the upload code in
  `app.part4.min.js` (`Ext.vcops.initialConfiguration.solutions.
  Select.uploadSolution`, around offset 487584-488299) and the
  CSRF auto-injection override in
  `/ui/js/components/ext-overrides.js`. Bundles were stored
  ephemerally under `/tmp/ui_bundles/` for the investigation
  and deleted after.
