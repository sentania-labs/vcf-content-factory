# VCF Operations mini-app / Extensions framework (VGL-63149)

**Provenance:** `api-explorer`, 2026-09-25. HTTPS pass 09:19 to 09:35 CDT
(Suite API GETs, UI-session GETs, static JS bundles). SSH pass 10:13 to 11:05
CDT after the coordinator confirmed and reopened prod SSH: root over
`sshpass`, strictly read-only (`cat`, `ls`, `find`, `javap`, `tar -cf - ... |`
streamed to the local scratchpad; jars and classes disassembled locally),
against **prod** `vcf-lab-operations.int.sentania.net`. That name is a
round-robin A record over two nodes: `vcf-lab-operations01` (172.27.8.42) and
`vcf-lab-operations02` (172.27.8.43); the SSH pass pinned node 01. Suite API
reports VCF Operations 9.1.1.0 build 25679751; the appliance
`lastbuildversion.txt` and the mini-app manifests report build 25679623.
Nothing was created, changed, restarted, uploaded, synced, activated, or
registered. Appliance `/tmp` and `/storage/db/casa/pak/mini_apps` verified
unchanged (the latter does not exist, since nothing has ever been uploaded).

Secondary source: an internal Broadcom QE test plan for epic VGL-63149 (not in
the repo, not to be committed). Where it disagrees with the shipped 9.1.1
build, the build wins and the difference is noted.

## Verdict

**We cannot install our own mini-app on this appliance, and the wall is now
confirmed as two independent gates, either of which stops us.** Building the
*code* is open (a plain ES module exporting `bootstrap()`, no Module
Federation). Installing is not:

1. **Hardcoded allow-list.** The UI webapp
   (`ESPluginUpdater.allowedMiniAppPluginKeys`) is a compiled
   `Set.of("app-observability","content-builder","via","acc")`. Upload reads
   the `pluginKey` from the pak's `manifest.json` and rejects anything not in
   that set (or not already installed) with `statusCode:1` = "No supported
   extension found", **before** the pak is ever handed to the signature check.
   A novel plugin key cannot pass, full stop.
2. **Broadcom signature.** If the key were allowed, CaSA then verifies a
   `signature.mf` / `signature.cert` pair inside the `.pak` using the **same
   Python signature validator as product and management-pack paks**, requiring
   the signing certificate's public key to match the platform truststore alias
   `vmwarespc` (or `vmwarespc_test`), or to chain to `vcops-cluster-ca`. There
   is **no unsigned bypass** on the mini-app path: the MP-pak escape hatches
   (`ignoreSignatureChecking` and `/storage/db/casa/unsigned_pak_allowed`) do
   not apply here; `verifySignature()` throws unconditionally on any invalid
   result.

The Developer Center "Plugin Registration" path is not a way around this:
server-side it only runs when the appliance is **not** in production mode
(`MainFilter` gates `registerPlugin` on `!AppConstants.isProduction()`), prod
is production, so the handler is skipped entirely regardless of privilege. Even
where it does run it does not set `isMiniApp`, so it would never surface under
Extensions.

Realistic paths to shipping a mini-app: get Broadcom to sign and marketplace
it under one of the reserved keys (their program, their apps), or use the
supported factory surfaces (dashboards, the TextDisplay HTML/URL widget).

## 1. Version and feature state (prod)

| Item | Value | Evidence | Confidence |
|---|---|---|---|
| Version | 9.1.1.0 build 25679751 | `GET /suite-api/api/versions/current` | confirmed |
| Feature flag | `fss_extensions_management_ui` = `true` | `featureFlags` in `GET /vcf-operations/getUserBaseInfo` | confirmed |
| Flag default in UI | UI forces the flag to `true` if the backend omits it (`featureFlags[EXTENSIONS_MANAGEMENT_FLAG] ??= true`) | shell chunk (user service, `getUserBaseInfo` handler) | confirmed |
| Where the flag is set server-side | Served to the UI by `com.vmware.vcops.FeatureFlagClient.getAll()` from within the vcf-operations webapp (`ActionExecutor.processGetUserBaseInfo`); the flag name appears only inside product jars, not in any editable file under `user/conf` or `common/conf`, so the default is compiled into the feature-flag subsystem. It reports `true` on prod. | `javap` of `ActionExecutor`; appliance grep | high (backing store not opened) |
| Privileges | `extensions.management.manage` (Extensions Management page) and `extensions.management.usage`, both held by the factory's prod user | `userPrivileges` in `getUserBaseInfo` | confirmed |
| License | `licenseEnterprise: true` (VCF) | `licenseInfo` in `getUserBaseInfo` | confirmed |
| Tab visible | Yes: header nav item `Extensions` (`path: "extensions"`) with child `Extensions Management`, gated by the flag plus `extensions.management.manage` | shell nav config; flag and privilege both true for this user | high (not viewed in a browser) |

URLs:
- Management page: `/vcf-operations/ui/extensions/extensions-management`
- A mini-app: `/vcf-operations/ui/extensions/<plugin-key>` (route guard only
  admits keys whose service-type `metaData.isMiniApp === true`)

## 2. What is installed / pre-shipped

`GET /vcf-operations/getMiniAppPlugins` (UI session) returns 4 entries, all
Broadcom, all version 1.0.0, **none active**:

| pluginKey | name | installed | active |
|---|---|---|---|
| `acc` | Advanced Configuration | true | false |
| `via` | VMware Intelligent Assist | true | false |
| `content-builder` | Content Builder | true | false |
| `app-observability` | Platform Observability | **false** (catalog entry, offered for INSTALL) | false |

Entry fields: `installed, incomplete, author, name, description, active,
pluginKey, icons{thumbnail (data: SVG), screenshots[]}, version,
i18n{<locale>{name, description}}` with locales `en-US, ja, fr, es`. **No
`category` or `compatibility` field** in 9.1.1 (the test plan's cards show
both).

On-disk layout (confirmed by SSH, node 01):

- **Pre-shipped inner bundles:**
  `/usr/lib/vmware-vcops/user/plugins/ui/mini-apps/{acc,app-observability,content-builder,via}.zip`
  (2 to 5 MB each, dated 2026-08-13). These are the inner `<pluginKey>.zip`
  UI bundles, not full signed paks: each contains `<key>/config.json`
  (`{pluginKey, pluginName, globalMenu}`) plus `<key>/dist/` with the runtime
  `manifest.json`, the entry file, styles, and `assets/mini-app/{dark,light}/`.
  No `signature.mf` / `signature.cert` inside (those live in the outer `.pak`,
  which is not retained on disk after extraction).
- **Extracted / served:**
  `/usr/lib/vmware-vcops/tomcat-web-app/webapps/vcf-operations/plugins/<key>/dist/`,
  each with a `<key>-backup` sibling. Only `acc`, `content-builder`, `via` are
  extracted (`app-observability` is catalog-only, matching `installed:false`).
- **Upload staging** `/storage/db/casa/pak/mini_apps` is created on first
  upload; it does not exist on prod (nothing has been uploaded).

Runtime `manifest.json` fields (from `acc`):
`styleMapping{<file>:<file>}, entryFile ("main.mjs" or "main.js"),
distName ("dist"), noCache, version, buildNumber, versionCheckURL, author,
isMiniApp, name, description, i18n{<locale>{name, description}}`.

Entry module exports **`bootstrap`** and **`destroy`** (verified: `acc`
`main.mjs` re-exports them; `via` `main.js` ends `export{...as bootstrap,...as
destroy}`). Mini-apps are **UI-only**: no backend files in any bundle, and their
service-type records carry no `rootURL` / `proxy-config`, so nothing runs behind
`plug/<key>/`.

## 3. Signature (confirmed from backend code)

The `.pak` container (from the signature validator's own docstring and the
extract code):

- Outer ZIP with, at its root: `manifest.json` (carries `pluginKey` plus the
  i18n / version metadata), `<pluginKey>.zip` (the inner UI bundle that ends up
  under `plugins/<key>/dist/`), and `signature.mf` + `signature.cert`.
- Same `signature.mf` / `signature.cert` scheme as product and management-pack
  paks. The difference: a mini-app pak has only `manifest.json`, no
  `manifest.txt`, which is why it uses a dedicated `query_mini_app_signature`
  action instead of the product `QueryPakSignature` (that one requires
  `manifest.txt`).

Verification call chain (UI upload -> install):

1. `ESPluginUpdater.uploadMiniAppPlugin()` (in the vcf-operations webapp):
   parse multipart (field `file`), save to
   `/storage/db/casa/pak/mini_apps/<epoch>`, then `readPluginKeyFromPak()`
   reads `manifest.json`'s `pluginKey` from the pak.
2. **Allow-list gate** `isPluginAllowed(pluginKey)`: true only if the key is an
   already-installed mini-app **or** is in the compiled
   `allowedMiniAppPluginKeys = Set.of("app-observability","content-builder","via","acc")`.
   If not: response `{status:false, statusCode:"1"}` = "No supported extension
   found", and the pak is discarded. **This runs before any signature check.**
3. `DataProvider.syncMiniApp(fileName, force)` -> Suite API
   `POST /rest/internal/ui-extensions/sync` -> CaSA
   `MiniAppService.syncMiniApp` / `extractLocally`.
4. `MiniAppService.verifySignature()` -> `PakCommand.checkMiniAppPakSignature()`
   -> `sudo python3 .../pakManager/bin/vcopsPakManager.py --action
   query_mini_app_signature --pak <file> --json` -> class
   `QueryMiniAppSignature` -> `Signature.check_signature()` in
   `vcopsPakSignatureValidation.py`.

`Signature.check_signature()` (identical to the product-pak path): requires
both signature files; verifies the signed hash of `signature.mf` against the
cert via `openssl dgst -verify`; runs `verify_certificate_trust`; then
`verify_hashes` (every pak file listed in `signature.mf`, all present, none
extra, each hash matching). Any exception is treated as invalid.

**Trust anchor** (`verify_certificate_trust` and `getExpectedCertificates`):
the pak cert's public key must byte-match a certificate exported from the
platform truststore `$STORAGE/user/conf/ssl/tcserver.truststore` under alias
`vmwarespc` or `vmwarespc_test` (the VMware Software Publishing Certificate). If
the public key does not match, it falls back to X.509 chain verification against
alias `vcops-cluster-ca` (this sets `is_mpb=true`, the management-pack-builder
signing path). So an installable mini-app must be signed either by VMware's
software-publishing key or by a cert chaining to this cluster's CA.

Failure to error mapping (CaSA `verifySignature` throws
`CasaLocalizableException`): not signed -> `PAK_MANAGER_NO_SIGNATURE`; untrusted
cert -> `PAK_MANAGER_UNTRUSTED_CERTIFICATE` (the "invalid or untrusted
signature" text); otherwise -> `PAK_MANAGER_INVALID_SIGNATURE`. Surfaces to the
UI as `statusMessage`.

**Bypass: none on the mini-app path.** `verifySignature()` throws whenever
`isSignatureValid()` is false, unconditionally. `syncMiniApp`'s `force` flag
only controls whether an already-extracted target directory is overwritten, not
whether signing is checked. The MP-pak escape hatches do **not** reach here:
`ignoreSignatureChecking` is a parameter of the solution/MP upload endpoint
(`/admin/admin/services/solution/upload`, see `pak_install_api_exploration.md`),
and the `/storage/db/casa/unsigned_pak_allowed` gate in the pak manager governs
only solution/product paks. Neither is consulted for mini-apps.

Comparison with MP paks: MP paks can be installed unsigned (with
`ignoreSignatureChecking=true` plus the `unsigned_pak_allowed` gate, giving a
`signingStatus:"NotSigned"` warning). Mini-app paks have no such affordance and
add the hardcoded key allow-list on top. Mini-apps are the stricter of the two.

No EULA prompt strings and no content-scan/malware/size-limit code were found in
the shipped 9.1.1 Extensions UI or in these classes (the test plan lists them;
they are not present in this build). All signature logic is server-side.

### The other door: Developer Center "Plugin Registration"

Route `/vcf-operations/ui/build/developer-center/plugin-registration`
(component `vcf-plugin-registration`). It `POST`s multipart to
`/vcf-operations/registerPlugin` with `serviceKey, serviceName, rootURL,
metaData{global-menu:true, title, module-config{type, csrf-check:false}}` and,
for ES-module type, a `.zip` file. Types: "ES Module" (zip) or "iFrame" (root
URL). Links to Broadcom-internal sample zips (`dummy-angular.zip`,
`dummy-react.zip` on `github-vcf.devops.broadcom.net`, not publicly reachable).
On success it sends you to `/vcf-operations/ui/operate/plugin/<key>`, a generic
route with **no** `isMiniApp` guard.

UI gate: `isAccessible: superAdmin && !isOnPremProduction`. On prod
`isOnPremProduction: true` and `superAdmin: false`, so the page is hidden.
**Server-side gate confirmed (from `MainFilter` bytecode):** a request whose
path ends in `/registerPlugin` is dispatched to
`PluginPlayground.registerPlugin()` **only when `AppConstants.isProduction()` is
false**. On a production appliance `isProduction()` is true (set from
`isOnPremProduction` during `getUserBaseInfo`), so the branch is skipped and the
request falls through to `ActionExecutor`, which has no `registerPlugin` action.
There is no super-admin check on the server side; production mode alone disables
it. So on prod `registerPlugin` is inert regardless of privilege. Even in a
non-production deployment where it runs, `PluginPlayground.processESModule`
writes only `serviceKey / serviceName / rootURL / metaData` and does not set
`isMiniApp`, so a plugin registered this way would not appear under the
Extensions sidebar.

## 4. How the host loads a mini-app (the contract)

Not Webpack Module Federation. No `remoteEntry`, share scope, or
`loadRemoteModule` anywhere in the shell. "Federated" in the test plan
means independently built ES modules.

- Shell: Angular (esbuild output) at `/vcf-operations/ui/`, base href
  `/vcf-operations/`. The legacy ExtJS Ops UI is itself plugin `ops`
  (`module-config.type: iframe`).
- Plugin types: `es-module` or `iframe` (enum `ESM="es-module"`,
  `IFRAME="iframe"`). All mini-apps are `es-module`, as are built-ins
  `netops`, `ops-pais-chat`, `unifiedshell`, `vodap`, `lcm`, `ops-ni`.
- Plugin dir: `/vcf-operations/plugins/<key>/<path>/` (`path` defaults to
  `""`, so `/plugins/<key>//`).
- Load sequence: fetch `<dir>/manifest.json?noCache=true`; read
  `entryFile` (default `main.mjs`), `styleMapping` (css files linked into the
  host element), `version`, `buildNumber`, `versionCheckURL`, `noCache`;
  `import(entryFile)`; call
  `module.bootstrap(shadowRoot, sdk, pluginDir, apiPrefix, baseUrl, options)`;
  on teardown `module.destroy(stickyId)`. Missing `bootstrap` fails with
  `"bootstrap" function is not defined in plugin module`.
- The plugin renders into an **open shadow root**, brings its own framework
  (Angular or React per the sample names), and shares nothing with the host
  except what the SDK passes. Shell CSS is `@cds` / Clarity; a plugin wanting
  the look must ship or reference it.
- SDK init data passed to the plugin: `pluginId, config{key, path, options},
  apiPrefix` (`plug/<key>/`), `customProperties, csrfToken, userInfo, theme,
  locale, timezone(+offset), isSsoUser, isVcfEntitlement, plugins,
  featureFlags, opsApiPrefix` (`/vcf-operations/` + ops API prefix). SDK
  functions include `showLoading, showFloatingAlert/Error, addBanner,
  removeBanner, getCspNonce, getNgZone, getTheme, getLocale, reload,
  isFeatureEnabled, fireEvent/addListener/removeListener`, plus navigation.
- Backend calls: through the shell's reverse proxy `/vcf-operations/plug/<key>/`
  to the service-type `rootURL`. Mini-apps have no `rootURL`, so their data
  path is the Ops proxy (`opsApiPrefix`) on the user's browser session with the
  `Csrf-Token` header from the SDK. Browser session plus CSRF, not a Suite API
  token. Exact ops proxy path to Suite API not confirmed (a plain GET to
  `/vcf-operations/plug/ops/suite-api/...` returned 400).
- CSP on the shell: `script-src 'nonce-...' 'strict-dynamic'`, so dynamically
  imported plugin modules run, inline script needs the SDK nonce;
  `default-src https: 'self' data: blob:` (no `connect-src`), so fetches to any
  HTTPS origin are CSP-allowed (CORS still applies).
- Sidebar: `populateMiniAppExtensions()` adds one child under the
  `Extensions` header per service type with `metaData.isMiniApp === true`
  (title from `metaData.i18n[locale].name`, path = `serviceKey`, icon
  `plugin`). There is no manifest-driven placement elsewhere in the menu in
  9.1.1.

## 5. Endpoints (GET results on prod)

| Endpoint | Auth | Result |
|---|---|---|
| `GET /suite-api/internal/ui-extensions` | Suite API token **plus `X-Ops-API-use-unsupported: true`** (403 without) | `{"uiExtensions":[{serviceKey, serviceName, metaData (JSON string), rootURL, certificate, serviceSource}]}` for all 14 registered UI service types (mini-apps and built-ins). Accepts `?serviceKey=`. |
| `GET /suite-api/internal/ui-extensions/{key}` | same | **405**: the `{key}` path maps only **DELETE** (`UIExtensionsController.deleteUIExtension(String)`), so GET is not allowed. |
| `GET /vcf-operations/getMiniAppPlugins` | UI session | the 4-entry catalog above |
| `GET /vcf-operations/getUserBaseInfo` | UI session | `featureFlags`, `userPrivileges`, `serviceTypes[]` (drives menus and routes), `isOnPremProduction`, `superAdmin` |
| `GET /vcf-operations/getPluginStatuses` | UI session | `[]` |
| `GET /vcf-operations/getGlobalExtensions` | UI session | `[]` (vSphere-client-style remote plugin extension points) |
| `GET /vcf-operations/getBackendInfosForAllPlugins` | UI session | proxy map for vSphere-sourced plugins (SDDC Manager, Fleet) |

Write actions seen in the shell/code, **not called**:
`POST uploadMiniAppPlugin` (multipart `file`), `POST installMiniAppPlugin`,
`POST activateMiniAppPlugin`, `POST deactivateMiniAppPlugin` (JSON
`{pluginKey}`), `POST registerPlugin`, and
`POST /rest/internal/ui-extensions/sync` (CaSA cluster distribution, confirmed
in `DataProvider.syncMiniApp`). The Suite API `UIExtensionsController` also
exposes `saveUIExtension` (POST body), `updateUIExtension` (PUT body),
`deleteUIExtension` (DELETE `/{key}`), and `syncMiniApp` (POST `.../sync`);
`getUIExtensions` is the GET read used above.

> **Unsupported-API warning:** every `/suite-api/internal/...` call here needs
> `X-Ops-API-use-unsupported: true`. None of these endpoints is in
> `reference/docs/internal-api*.json` or in the live
> `/suite-api/doc/openapi/v3/internal-api.json` on 9.1.1. The `/vcf-operations/*`
> actions are UI-private.

UI session recipe: `GET /ui/login.action?vcf=1`, `POST /ui/login.action`
(form, see `struts_import_endpoints.md`), `GET /ui/index.action?vcf=1`
(sets `OPS_SESSION`, redirects to `../vcf-operations/ui`), then
`GET /vcf-operations/ui/` with `Accept: text/html`. Without the `vcf=1` hop,
`/vcf-operations/*` returns 404 or 302 to login.

## 6. Lifecycle and cluster

- Registry: every UI extension, mini-app or not, is a **service type**
  record (`serviceKey`, `metaData`, optional `rootURL`/`certificate`).
  Activation state lives in service-type properties (test plan); on prod the
  `configured` flag is `false` for all four mini-apps, which matches
  "inactive", but `configured` is also false for built-ins like `netops`, so it
  is not a clean active flag.
- Distribution (confirmed in code): upload saves the pak under
  `/storage/db/casa/pak/mini_apps`, then `DataProvider.syncMiniApp` calls
  `POST /rest/internal/ui-extensions/sync` on the Suite API, which reaches CaSA
  `MiniAppService.syncMiniApp`. That verifies the signature, distributes the
  pak to every data slice
  (`/private/upgrade/slice/pak/mini_app/operation/distribute`, multipart), then
  each node extracts the inner `<key>.zip` into
  `.../webapps/vcf-operations/plugins/<key>/`. `syncMiniAppsToNewSlices`
  re-syncs installed mini-apps when a node is added. A `plugin_processed`
  xattr marks extracted bundles.
- "Incomplete" state exists (UI tooltip: "Please re-upload the extension to
  resolve the incomplete installation state."), meaning metadata without files
  is a known failure mode.
- Upgrade/backup: the test plan flags both directories as a risk for
  backup/restore and upgrade; no stated guarantee. Unverified.
- Each activate/deactivate/upload shows a "reload page" modal: changes need a
  browser reload, not a service restart.

## 7. What building our own would take

The mini-app **code** is buildable today with no Broadcom involvement:
1. An ES module (`main.mjs` or `main.js`) exporting
   `bootstrap(shadowRoot, sdk, pluginDir, apiPrefix, baseUrl, options)` and
   `destroy(id)`, bundling its own framework (Angular or React, as the shipped
   ones do), rendering into the shadow root.
2. A runtime `manifest.json`: `entryFile`, `styleMapping`, `distName`,
   `version`, `buildNumber`, `versionCheckURL`, `noCache`, `author`,
   `isMiniApp`, `name`, `description`, `i18n{en-US|es|fr|ja:{name,description}}`.
3. A `config.json` at the bundle root: `{pluginKey, pluginName, globalMenu}`.
4. Packaged as `<pluginKey>.zip` (the inner UI bundle), which the installer
   extracts to `plugins/<key>/dist/`. Data access is the user's browser session
   plus the SDK `Csrf-Token`; no new auth.

Two confirmed walls, both blocking, on the supported install:
1. **Hardcoded allow-list.** `pluginKey` must be one of
   `acc`, `via`, `content-builder`, `app-observability` (or an already-installed
   mini-app). Ours would not be, so upload returns "No supported extension
   found" before signing is even checked. This is compiled into the webapp; an
   admin cannot change it.
2. **Broadcom signature.** The outer `.pak` needs valid `signature.mf` /
   `signature.cert` whose cert matches the `vmwarespc` software-publishing key
   in the platform truststore (or chains to this cluster's `vcops-cluster-ca`).
   We cannot produce the first; the second is an internal CA. No unsigned or
   ignore-signature bypass exists on this path.

`registerPlugin` is not an escape: it is disabled server-side in production and
does not set `isMiniApp` anyway. The only real route to a shipped mini-app is
Broadcom signing and marketplacing it under a reserved key.

Fallbacks that work now:
- Dashboard **TextDisplay** widget (HTML via `editorData`, or a URL via
  `locationUrl`); see `widget_types_survey.md`. An iframe-style panel inside a
  dashboard, no sidebar entry, subject to the target page's framing and CSP.
- Regular factory content (dashboards, views, MPs) remains the supported
  surface. A management pack, not a mini-app, is our lever for new backend data.

## Open questions (reduced)

1. Exact backing store and change mechanism for `fss_extensions_management_ui`
   (served by `FeatureFlagClient.getAll()`, true on prod; the name lives only
   inside jars, not in an editable conf file). Low value: even flipping it off
   would only hide the tab, not remove the allow-list or signature gates.
2. Public doc content for UI help key `vcom_1052` (Extensions Management); the
   techdocs `gethidpage` link returned an empty body on 2026-09-25.
3. Whether the allow-list or the `vmwarespc` truststore alias is identical on
   other releases (checked only on 9.1.1 build 25679751 / appliance 25679623).

Questions 1 to 5 from the prior HTTPS-only pass are now closed:
signature format and validator (section 3), pak/bundle layout (section 2),
the flag source (section 1 table), the `{key}` verb (DELETE, section 5), and
the `registerPlugin` server gate (production-mode only, section 3 subsection).

## Side effects of this pass

HTTPS pass: four GETs returned HTTP 500 and invalidated the UI session (each
followed by a fresh login): `/vcf-operations/plugins/ops-ni//manifest.json`,
`/vcf-operations/plugins/app-observability//manifest.json`,
`/vcf-operations/plugins/sample/build/manifest.json`, and
`/vcf-operations/getRemotePluginNavigationMap`. They appear in prod web logs
around 09:25 to 09:33 CDT. SSH pass (root, node 01, 10:13 to 11:05 CDT): reads
only (`cat`, `ls`, `find`, `tar -cf - | ` streamed off-box, `javap` on local
copies). Nothing was written on the appliance; `/tmp` and the (absent)
`mini_apps` staging dir were verified unchanged. Several UI sessions and Suite
API tokens were opened and left to expire.
