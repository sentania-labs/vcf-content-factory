# Unsigned pak policy on VCF Operations 9.1.1 (2026-10-14)

**Question.** Why does every factory pak upload to devel_9_1 (9.1.1.0 build
25795063) fail with `Pak upload rejected by PAK Manager:
unsigned_pak_installation.not.allowed`, even though the installer sends
`ignoreSignatureChecking=true`, when prod (9.1.1.0 build 25679751) accepts
the same kind of pak?

**Answer.** A cluster-wide CaSA toggle, **Allow unsigned PAK installation**,
gates it. It is not a per-upload flag and it is not a hard policy of the
build. The toggle is off on a fresh install. It was on for prod and devel
because someone switched it on. On devel the CaSA audit log records an
admin-UI enable at 2026-04-17 17:07:54 local, the day after deployment.
`ignoreSignatureChecking=true` only works once the toggle is on. While the
toggle is off, CaSA refuses the request. Customers on any fresh install
(9.0.x or 9.1.x) will hit this until an admin enables the toggle.

All times below are America/Chicago.

## 1. The setting

| Aspect | Value |
|---|---|
| UI label | Admin UI (`https://<node>/admin`), Administrator Settings, Security Settings panel, "Allow unsigned PAK installation" (status Activated/Deactivated; button "Activate Unsigned PAK Installation" on 9.1.1, "Enable ..." on 9.0.2) |
| Scope | Cluster-wide (CaSA). Fan-out per node: the cluster GET reports `node_states[]` |
| Backing store | Marker file `/storage/db/casa/unsigned_pak_allowed` on each node (present = allowed). From `casa-beans.xml` bean property `unsignedPakInstallationEnabledFilePath` |
| Default on fresh install | Off. devel_9_1 (fresh 2026-10-14) read `false`. devel (9.0.2) had no marker until the 2026-04-17 enable |
| Suite API global settings | **Not there.** None of the 61 keys in `GET /api/deployment/config/globalsettings` matches, on either devel_9_1 or prod |
| OpenAPI specs | **Not there.** No unsigned or pak-signing endpoint in `operations-api-9.1.json` or `internal-api-9.1.json` (nor the 9.0 specs). The only pak-related public paths are read-only `/api/solutions*` and `/internal/solutions/preinstalled*` |

Error key source: CaSA
`WEB-INF/classes/errors.properties` line 107 (read on devel 9.0.2):

```
unsigned_pak_installation.action.failed = Failed to change unsigned pak installation state.
unsigned_pak_installation.verification.all_slices_responsive = Unable to change unsigned pak installation rules while not all slices are responsive.
unsigned_pak_installation.not.allowed = Unsigned pak installation is not allowed.
```

The product UI bundle (`GET /ui/utility.action?mainAction=getMessageBundle`,
17338 keys, the same count on both 9.1.1 builds) has no entry for this key.
That is why the raw key `unsigned_pak_installation.not.allowed` appears
after `PAK Manager:` instead of readable text. This is cosmetic. The
behavior is the same on both builds.

Related bundle strings (product UI, 9.1.1):

```
solutions.ignoreSignatureChecking = Ignore the PAK file signature checking.
pak_manager.pakfile.no_signature = No signature found on PAK file
pak_manager.pakfile.invalid_signature = Signature on PAK file '%1s' is not valid
pak_manager.pakfile.signature_checkbox_misused = Ignore the signature checkbox shouldn't be used with product pak
```

Admin UI bundle (9.1.1, from `GET /admin/commonJS.action?mainAction=getApplicationGlobalData`, key `bundle`):

```
unsignedPakInstallation.status = Allow unsigned PAK installation
unsignedPakInstallation.info = This option permits the installation of PAK files without signature verification. ...
unsignedPakInstallation.action.button.DISABLED = Activate Unsigned PAK Installation
unsignedPakInstallation.action.button.ENABLED = Deactivate Unsigned PAK Installation
```

## 2. Global toggle, not a per-upload flag

How the SPA wires it (product UI `app.part3/part4.min.js` and admin UI
`app.part1.min.js`, 9.1.1):

- `solution.action mainAction=getIntegrations` (Repository page load)
  returns `isUnsignedPakInstallationAllowed`. The Add wizard is constructed
  with that value.
- In `Ext.vcops.initialConfiguration.solutions.Select`, the "Ignore the
  PAK file signature checking" checkbox is created with
  `hidden: !this.isUnsignedPakInstallationAllowed`. When the toggle is off,
  the UI never offers the override.
- The upload sends `ignoreSignatureChecking` (query string on `/ui/`, form
  field on `/admin/`). Our installer matches the `/ui/` wire format. **The
  installer is sending the flag correctly.** The flag only works once the
  cluster toggle is on. While it is off, CaSA rejects the request with
  `unsigned_pak_installation.not.allowed`.

Read paths for the toggle (all verified 2026-10-14):

| Path | Auth | Response |
|---|---|---|
| `POST /ui/solution.action mainAction=getIntegrations` | any product UI user with repository access (works as `claude` on prod) | `isUnsignedPakInstallationAllowed: true/false` (plus ~590 KB of pack list) |
| `POST /admin/clusterManagement.action mainAction=getUPIStatus` | admin UI session (built-in `admin`; `claude` refused) + `secureToken` | `{"status":"true"}` / `{"status":"false"}` |
| `POST /admin/clusterManagement.action mainAction=isPakInstalling` | same | includes `isUnsignedPakInstallationAllowed` (the `/ui/` variant of this call does **not** include it) |
| `GET /casa/upgrade/cluster/pak/allow_unsigned_pak` | HTTP Basic, `admin` | `{"node_states":[{"address":"<node>","status":"true"}],"cluster_state":true}` |
| `GET /casa/upgrade/slice/pak/allow_unsigned_pak` | HTTP Basic, `admin` | `true` / `false` (this node only) |

Write paths (documented, **not exercised** in this investigation):

- Admin UI: `POST /admin/clusterManagement.action mainAction=enableUPI` /
  `disableUPI` (what the Security Settings button calls).
- CaSA: `POST /casa/upgrade/cluster/pak/allow_unsigned_pak`, JSON body
  `{"action":"ENABLE"}` or `{"action":"DISABLE"}`, HTTP Basic admin. The
  on-appliance CaSA API guide (`/usr/lib/vmware-casa/casa-webapp/webapps/casa/api-guide.html`,
  section "Change vROps unsigned PAK installation status") documents it.
  It fails with `unsigned_pak_installation.verification.all_slices_responsive`
  unless every node is responsive.

CaSA is an internal, unpublished admin surface (not in either OpenAPI
spec). If this is ever automated, treat it like an unsupported endpoint
and gate it behind an explicit user decision. It weakens a security
control for the whole cluster.

## 3. Customer path and Broadcom's position on third-party signing

Documented customer path (VCF 9.1 docs, `reference/docs/vmware-cloud-foundation-9-1.pdf`,
"Converting Content Packs to Management Packs", doc page 4488 to 4489):

> You must enable the setting. Unsigned Pack File Installation in VCF
> Operations. This is to prevent the error message, No signature found on
> pack file which is displayed during installation. Log in to the VMware
> Cloud Foundation Operations Administration UI and activate the Allow
> Unsigned PAK Installation under Administrator Settings.
> ...
> 4. Install the pack file even if it is already installed and ignore
> signature checking.

So the supported order for a customer installing a third-party unsigned
pak is:

1. `https://<primary-node>/admin`, log in as `admin`, Administrator
   Settings, Security Settings, Activate Unsigned PAK Installation.
2. Operate, Administration, Integrations, Repository, Add, Browse.
3. Tick "Ignore the PAK file signature checking" (now visible), Upload,
   accept the unsigned warning, EULA, install.
4. Optionally deactivate the toggle again afterwards.

This is the only place the 9.1 docs name the toggle, and it sits in the
Log content pack converter section. The general "Adding a Management Pack"
pages (doc pages 4175 and 5682 to 5683) only mention the "The PAK file is
unsigned" warning. They do not say the install is blocked unless the
toggle is on. The 9.0 PDF does not name the toggle anywhere, although the
9.0.2 appliance has it.

Third-party signing: the 9.1 docs say only that the warning appears "if the
PAK file is not signed with a digital signature that VMware provides", and
advise confirming with the distributor that the pack "is signed and
certified". There is no documented process for a third party to sign a
pak, no way to import a trust anchor for pak signatures, and no mention of
who can sign. The only "package signing certificate" in the 9.1 PDF
(doc page 7729) is the VCF Operations
orchestrator's package export signer, which has nothing to do with paks.
Conclusion: a pak counts as signed only with a VMware/Broadcom signature.
In practice, third-party paks are installed unsigned through the toggle.
The factory's "self-signed" roadmap step (tier2_architecture.md) would
still read as untrusted and would not avoid the toggle.

## 4. Prod vs devel vs devel_9_1

| Instance | Build | Install history | Toggle | Evidence |
|---|---|---|---|---|
| prod | 9.1.1.0 build 25679751 | upgraded appliance | **on** | `getIntegrations` as `claude`: `isUnsignedPakInstallationAllowed: true` (2026-10-14 ~14:30) |
| devel | 9.0.2.0 build 25137845 (lastbuildversion 25429562) | deployed 2026-04-16 21:10 | **on, enabled by hand** | marker `/storage/db/casa/unsigned_pak_allowed` mtime 2026-04-17 17:07:54; CaSA audit log `Category : ALLOW_UNSIGNED_PAK - Enable/Disable unsigned pak installation` at 2026-04-17 17:07:54, preceded and followed by admin-ui GETs of `allow_unsigned_pak` (the status-load, click, reload pattern of the Security Settings button) |
| devel_9_1 | 9.1.1.0 build 25795063 (9.1.1.0100 UI) | fresh 2026-10-14 | **off at first read, on by 14:34** | off: admin `getUPIStatus` `{"status":"false"}` (~14:29) and `getIntegrations` `false` (~14:30). On: CaSA GET `cluster_state: true` at 14:34:16, admin `getUPIStatus` `true` at 14:34:24, with `isPakInstalling: true` (someone else's install was then running, and a `/ui/` admin login returned `concurrentSessionDetected`). This investigation made no write calls. Someone else turned the toggle on between ~14:30 and 14:34 |

The "upgrade keeps an old default" theory is not supported. devel never
had the toggle on by default: a human switched it on the day after
deployment, and devel_9_1 came up with it off. Prod's enable event could
not be read directly. There is no admin-UI credential for prod in `.env`
(the profile user `claude` is refused by `/admin` login), and SSH to prod
failed host-key verification (key changed since it was last recorded;
deliberately not overridden). The most likely explanation is the same
manual enable at some earlier date, but that is **unverified**.
Upgrades preserve `/storage/db/casa`, so whatever state an appliance has
carries across upgrades.

**Customer impact.** Any customer on a fresh 9.0.x or 9.1.x install
(and any upgraded appliance where nobody ever enabled it) gets
`unsigned_pak_installation.not.allowed` for every factory pak until an
admin activates the toggle. This needs to be in install docs and in the
installer's error handling, not treated as a lab quirk.

## Method

- Grep: both 9.1 OpenAPI specs and both 9.0 specs (no hits); text of
  `vmware-cloud-foundation-9-1.pdf` and `-9-0.pdf` via `pdftotext`.
- Live, read-only: Suite API global settings (devel_9_1, prod); product UI
  `getIntegrations`, `getMessageBundle`, SPA JS; admin UI `getUPIStatus`,
  `isPakInstalling`, global data bundle, SPA JS; CaSA GET
  `allow_unsigned_pak` (devel_9_1, devel).
- On-appliance, read-only (devel 9.0.2 only, key-based root SSH):
  `casa-beans.xml`, `errors.properties`, `api-guide.html`, marker file
  stat, CaSA logs. No writes, no service changes.
- Not tested: the actual effect of `ignoreSignatureChecking=false` vs `true`
  with the toggle off (that would need an upload), and the 9.1.1 on-disk
  files (no SSH credential for devel_9_1).

## Implications for code (for `tooling`, not done here)

- `src/vcfcf_managementpacks/installer.py`: preflight with
  `getIntegrations` (already used) and read `isUnsignedPakInstallationAllowed`.
  When it is false and the pak is unsigned, abort before upload with a
  clear message that names the Admin UI path above, instead of surfacing
  the raw key.
- Map the raw `unsigned_pak_installation.not.allowed` error to the same
  message, since the appliance UI bundle does not translate it.
- Do not auto-enable the toggle. It is a cluster-wide security control.
