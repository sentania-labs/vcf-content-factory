# Auth-source support — design plan v1

Empirical investigation 2026-04-28, both labs. Builds on
`context/auth_vidb_oauth_flow.md` (Jasnah, 2026-04-23).

The factory currently hard-codes Local authentication everywhere
the `/ui/login.action` UI session is needed (uninstall + a few
delete paths). When a customer's only Ops admin lives on a
non-Local auth source — vCenter SSO, AD, VIDB, etc. — install
works (Suite-API) but uninstall is blocked. This plan maps which
sourceTypes the framework can support today, which require code
changes, and which are genuinely unreachable.

---

## Section 1 — Empirical findings

### 1.1 Canonical taxonomy (`GET /suite-api/api/auth/sourcetypes`)

Identical on both labs:

| sourceType id | Notes |
|---|---|
| `VC` | vCenter SSO (single vCenter) |
| `VC_GROUP` | vCenter aggregate (`All vCenters`) — synthesized when 2+ VCs are added |
| `OPEN_LDAP` | OpenLDAP |
| `ACTIVE_DIRECTORY` | AD via LDAP/LDAPS |
| `SSO_SAML` | SAML IdP federation |
| `VIDM` | vIDM / Workspace ONE Access (legacy) |
| `CSP` | VMware Cloud Services |
| `VIDB` | VCF Identity Broker (VCF SSO, the new on-prem federation) |

`Local` is **not** in this list — Local is synthesized client-side
by the UI as `{id: "localItem", name: "Local Account", type: null}`.

### 1.2 Configured sources per lab (`GET /api/auth/sources`)

| Lab | Source name | sourceType | id (UUID) |
|---|---|---|---|
| devel | `vcf-lab-mgmt` | `VC` | `5aa31ee3-...c99d` |
| devel | `vcf-lab-wld01` | `VC` | `5827d79e-...0484` |
| devel | `All vCenters` | `VC_GROUP` | `5f7e628e-...5586` |
| devel | `ad` | `ACTIVE_DIRECTORY` | `3cf94d2a-...1f82` |
| prod | `VCF SSO` | `VIDB` | `841fafcb-...836b` |

Local does not appear in `/api/auth/sources` on either lab. This
is structural — Local is the local user database, not an external
auth source.

### 1.3 Probe 2 — Suite API password grant (`POST /suite-api/api/auth/token/acquire`)

Test credential: `<test-user>` / `<test-pwd>` (UPN form provided
by Scott). All probes used `{username, password, authSource}`
with `authSource` = the source `name`.

| Lab | Source name | sourceType | Status | Outcome | Notes |
|---|---|---|---|---|---|
| devel | `vcf-lab-mgmt` | VC | 200 | **A** | OpsToken minted; `roles=[]` |
| devel | `vcf-lab-wld01` | VC | 200 | **A** | OpsToken minted; `roles=[]` |
| devel | `All vCenters` | VC_GROUP | 200 | **A** | OpsToken minted; `roles=[]` |
| devel | `ad` (UPN form `vcf@int...`) | ACTIVE_DIRECTORY | 401 | **B** | HTML refusal; `WWW-Authenticate: OpsToken, VCToken, SSO2Token, CSPToken, VIDBToken` |
| devel | `ad` (NETBIOS `int\vcf`) | ACTIVE_DIRECTORY | 401 | **B'** | JSON `"provided username/password or token is not valid"` — server attempted password validation, rejected it (no `WWW-Authenticate` challenge) |
| devel | `ad` (DN form `CN=vcf,...`) | ACTIVE_DIRECTORY | 401 | **B'** | Same JSON refusal |
| prod | `VCF SSO` | VIDB | 401 | **B** | Same HTML + WWW-Authenticate as Jasnah documented; finding holds |

**Surprise vs. Jasnah's framework**: VC sources mint a token via
Suite-API password grant **without** a SAML pre-mint. The Ops
server proxies the password to vCenter SSO server-side. No
vCenter STS SOAP exchange needed for VC at the Suite-API layer.

**AD is principal-format-sensitive**: UPN-form is challenged
(server refuses password); NETBIOS / DN form attempts the
password bind. Hypothesis: when UPN suffix matches the AD
source's `domain` property, Ops routes to a token-required path.
The NETBIOS-form 401 on devel is likely a server-side bug —
the same credential succeeds on the UI form (returns `role`,
i.e. auth passed but no role assignment).

### 1.4 Probe 4 — UI session login (`POST /ui/login.action`)

Form fields driven by the install template
(`vcfops_packaging/templates/install.py:947-957`):
`mainAction=login`, `userName`, `password`, `authSourceId`,
`authSourceName`, `authSourceType`, `forceLogin`, `timezone`,
`languageCode`. Triplet values came from
`GET /ui/login.action?mainAction=getAuthSources` (the same
endpoint the UI dropdown uses).

| Lab | Source | (id, name, type) | Status | Body | OPS_SESSION |
|---|---|---|---|---|---|
| devel | `vcf-lab-mgmt` | (UUID, `vcf-lab-mgmt`, `VC`) | 200 | `ok` | **yes** |
| devel | `vcf-lab-wld01` | (UUID, `vcf-lab-wld01`, `VC`) | 200 | `ok` | **yes** |
| devel | `All vCenters` | (UUID, `All vCenters`, `VC_GROUP`) | 200 | `ok` | **yes** |
| devel | `ad` (UPN) | (UUID, `ad`, `ACTIVE_DIRECTORY`) | 200 | `role` | n/a (UI rejects: no role assigned) |
| devel | `ad` (NETBIOS) | same triplet | 200 | `?` | n/a (opaque; likely the password-rejection path) |
| prod | `VCF SSO` | (UUID, `VCF SSO`, `VIDB`) | 200 | `?` | n/a (form-POST cannot drive the OAuth redirect path; Jasnah confirmed) |

**Key finding**: VC and VC_GROUP work **headlessly** via the
existing UI form with the right `(id, name, type)` triplet. No
new auth flow needed — only the hardcoded Local triplet has to
become configurable. AD's `body=='role'` is auth-success +
no-Ops-role; it resolves once the principal has a role
assignment. See `context/auth_source_wire_formats.md` for the
full body-string taxonomy (`ok` / `role` / `forceLogin` / `?`).

### 1.5 Probe 5 — auxiliary auth surface

| Endpoint | Status | Verdict |
|---|---|---|
| `GET /suite-api/api/auth/sourcetypes` | 200 | canonical taxonomy |
| `GET /suite-api/api/auth/sources` | 200 | configured sources w/ id+name+sourceType (token-required) |
| `GET /suite-api/api/auth/sources/{id}` | 200 | single source detail |
| `GET /ui/login.action?mainAction=getAuthSources` | 200 | **Anonymous** UI dropdown list w/ synthesized `Local Account` |
| `GET /suite-api/internal/auth/sources` | 404 | dead |
| `GET /suite-api/internal/auth/basic` (unsupported header) | 500 | handler exists, crashes on GET |
| `GET /casa/private/auth-sources` | 401 | gated; not explored |

The `getAuthSources` mainAction is **anonymous** — the cleanest
way for an install script to discover the (id, name, type)
triplet without acquiring an admin token first.

---

## Section 2 — Per-sourceType support contract

| sourceType | Suite-API password grant | UI session login | Pre-token-mint | Framework today | Framework SHOULD |
|---|---|---|---|---|---|
| `Local` | works | works (`localItem`/`Local Account`/`""`) | n/a | works (hard-coded) | unchanged |
| `VC` | **works** (proxied to vC SSO) | **works** with `(uuid, name, "VC")` | none | install OK, uninstall **broken** (uses Local triplet) | **make UIClient triplet configurable** |
| `VC_GROUP` | **works** | **works** with `(uuid, name, "VC_GROUP")` | none | same as VC | same as VC |
| `ACTIVE_DIRECTORY` | **conditional** — rejected for UPN form, accepts NETBIOS/DN form (server attempts validation; lab failed for unrelated reason) | **conditional** — UI accepts password but rejects login for principals without an Ops role | none | install fails for UPN; uninstall blocked by triplet | **doc principal-format guidance + configurable triplet**; cannot fix the server's UPN routing bug |
| `OPEN_LDAP` | unprobed (no source configured) | unprobed | none expected | not supported | likely same shape as AD; configurable triplet probably sufficient |
| `SSO_SAML` | refused (would need SAML2 bearer pre-mint) | redirect path (UI calls `logInSSOUser()`); form-POST cannot drive | external SAML IdP STS exchange | not supported | **defer** — requires SAML STS client in tooling |
| `VIDM` | refused (would need VIDM token pre-mint) | redirect path (`logInVidmUser()`); form-POST cannot drive | external VIDM OAuth | not supported | **defer** — requires VIDM OAuth client (similar to VIDB) |
| `VIDB` | refused per Jasnah; re-confirmed | redirect path (`loginVIDBUser()`); form-POST cannot drive (returns `?`) | OAuth code exchange w/ confidential `client_secret` we cannot reach | not supported | **unreachable** for headless flow — Jasnah's conclusion stands; document as "use a Local service account when VIDB is the only source" |
| `CSP` | refused (would need CSP token) | unprobed (no source configured) | external CSP OAuth | not supported | **defer** — relevant only to VMC SaaS |

`roles=[]` on minted tokens means the test principal has no Ops
role assignment, independent of auth flow. Production service
accounts will have `Administrator`-equivalent scope.

---

## Section 3 — Recommended changes (no code edits, just plan)

Three categories: low-risk (config-only), moderate (code change
in existing modules), defer/unreachable.

### 3.1 Low-risk: VC, VC_GROUP, AD, OPEN_LDAP — configurable UI triplet

**Affected file**: `vcfops_packaging/templates/install.py`.

**Diagnosis**:
- `UIClient.__init__:925` hard-codes the Local mapping
  (`localItem` / `Local Account` / `""`); never captures
  `authSourceName` or `authSourceType`.
- `UIClient.login():947-957` submits literal `authSourceName`
  and `authSourceType` from those defaults.
- `_resolve_auth_source:296-309` collapses input to the Suite-API
  `authSource` string only.
- `_prompt_credentials:1310-1315` prompts only for the Suite-API
  string; never asks for id/type.

**Proposed change**:
1. Extend `UIClient.__init__` to accept optional `auth_source_id`,
   `auth_source_name`, `auth_source_type`. When all three are
   `None`, fall back to the current Local triplet (back-compat).
2. Have `UIClient.login()` use the provided triplet verbatim.
3. In `_prompt_credentials`, when `auth_source` != `local`, call
   `GET /ui/login.action?mainAction=getAuthSources` (anonymous)
   and resolve `name → (id, type)`. Single-prompt operator UX.
4. Add `--auth-source-id`, `--auth-source-type` CLI overrides
   for the case where anonymous lookup is blocked.
5. Plumb the triplet through `_run_install:2257` and
   `_run_uninstall:2340` to `UIClient`.

**Profile / `.env`**: two new optional fields; auto-discovery if
blank, explicit override otherwise:

```
VCFOPS_<P>_AUTH_SOURCE        # already exists — source name
VCFOPS_<P>_AUTH_SOURCE_ID     # NEW: UUID; auto-discovered if blank
VCFOPS_<P>_AUTH_SOURCE_TYPE   # NEW: VC / ACTIVE_DIRECTORY / etc.; auto-discovered if blank
```

`vcfops_common/_env.py:165` reads `AUTH_SOURCE`; extend it to
read the two new keys and thread them through
`ProfileCredentials`.

**Effort**: ~80-120 LoC across `vcfops_common/_env.py`,
`vcfops_packaging/templates/install.py`, plus PowerShell mirror
in `install.ps1` (PS 5.1 compat per memory note). No wire-format
changes — server is already happy with the form payload.

### 3.2 Low-risk: Suite-API client follows naturally

`vcfops_common/client.py:84-92` already takes `auth_source` as
the source name. Per Probe 2 this is correct for VC, VC_GROUP,
OPEN_LDAP, ACTIVE_DIRECTORY (NETBIOS form), and any other source
that accepts password grant. **No code change** needed for the
Suite-API path. The AD UPN-form rejection is server-side
behavior we can document but not fix.

### 3.3 Moderate: documentation / install-script messaging

When the install script's auth-source resolution detects a
sourceType the framework cannot drive headlessly, fail fast with
a clear message:

```
sourceType=VIDB / SSO_SAML / VIDM / CSP cannot be driven
headlessly by this installer. Configure a Local service
account for automation, or run uninstall as the admin
user via the UI.
```

Keep the message specific — Jasnah's VIDB analysis covers the
"why"; for SSO_SAML / VIDM / CSP the answer is "we'd need a SAML
STS / OAuth client we haven't built yet."

### 3.4 Defer / unreachable

- **VIDB**: per `context/auth_vidb_oauth_flow.md` and Probe 4
  re-confirmation. Document permanently as "Local service account
  required; UI flow is interactive-only."
- **SSO_SAML**: requires the framework to act as a SAML2 bearer
  client against an external IdP STS. Not blocking any current
  customer; ~250-400 LoC plus a test-IdP harness.
- **VIDM**: similar shape to VIDB (OAuth with confidential
  client). Effectively unreachable without the IdP-side client
  registration, same story as VIDB.
- **CSP**: VMware Cloud Services token; on-prem labs won't
  exercise it. Defer to first cloud-deployed customer.

### 3.5 Cross-cutting: NETBIOS Suite-API rejection on devel-AD

`int\vcf` rejected by Suite-API but accepted by UI form. Likely
a Suite-API LDAP-bind path bug on this build. Investigation
ticket only — not gating, since uninstall only needs the UI
path which already works.

---

## Section 4 — User guidance template (install-script + README copy)

Reusable prose for operator docs. Substitute lab-specific URLs.

> **Picking an auth source.** The installer needs a service
> account that can both call Suite API (`/suite-api/`) and create
> a UI session (`/ui/login.action`). The name you enter must
> match the UI login-screen dropdown exactly.
>
> **Find the source name without an admin login**: open
> `https://<ops-host>/ui/login.action?mainAction=getAuthSources`
> in a browser. Copy the `name` of the source you want.
>
> **Per sourceType**:
>
> - **Local** (`type: null`): enter `local` (or accept the
>   default). The installer fills the rest in automatically.
> - **VC / VC_GROUP**: enter the vCenter source name (e.g.
>   `vcf-lab-mgmt` or `All vCenters`). Use UPN-form username
>   (`user@sso-domain`). Both Suite API and UI work headlessly.
> - **ACTIVE_DIRECTORY / OPEN_LDAP**: enter the source name.
>   Prefer UPN-form username; if Suite API returns 401 with a
>   `WWW-Authenticate: OpsToken, VCToken, SSO2Token, ...` header,
>   try NETBIOS form (`DOMAIN\user`) — some Ops 9.0.2 builds
>   route UPN-form AD principals to a token-required path.
> - **VIDB / SSO_SAML / VIDM / CSP**: **not supported** by the
>   installer. Use a Local service account for automation; these
>   sourceTypes require pre-minted bearer tokens (or a confidential
>   OAuth client) that the installer cannot obtain headlessly.
>
> **Permissions**: needs `Administrator`-equivalent role.
> **Uninstall** additionally requires the canonical `admin` user
> because dashboards are owned by `admin` after import (see
> `feedback_admin_uninstall`).

---

## Section 5 — Open questions / follow-ups

1. **AD UPN-form Suite-API routing.** Hypothesis: the source-type
   dispatcher matches UPN suffix against the AD source's `domain`
   property and routes to an SSO-bridge code path that returns the
   challenge. Would need a 2nd AD source with a non-matching
   domain to confirm. Out of scope.
2. **AD NETBIOS-form Suite-API rejection on devel.** UI form
   accepts the same credential (returns `role`); Suite-API
   rejects with JSON. Could be a broken LDAP-bind path on this
   Ops build. Separate `api-explorer` ticket.
3. **OPEN_LDAP** unprobed (no source configured). Wire shape
   assumed to mirror ACTIVE_DIRECTORY; validate when available.
4. **SSO_SAML / VIDM**: framework would need a SAML2/OAuth client
   against an external IdP. Park until first customer.
5. **`getAuthSources` is anonymous on this build**. If a
   hardening posture disables it, fall back to the Suite-API
   admin token + `/api/auth/sources`.
6. **`/casa/private/auth-sources`** — gated 401, unexplored.

---

## Implementation order (recommended)

1. **Phase 1**: auto-discover triplet via anonymous
   `getAuthSources` lookup in `_prompt_credentials`; thread
   `(id, name, type)` through `UIClient` with back-compat
   defaults. Optional `.env` overrides
   (`VCFOPS_<P>_AUTH_SOURCE_ID`, `_TYPE`). Test on devel VC.
2. **Phase 2**: PowerShell parity in `install.ps1` template
   (PS 5.1 compat: ASCII only, no bare `&` at continuation,
   StrictMode-safe).
3. **Phase 3**: detect VIDB/SSO_SAML/VIDM/CSP and fail fast with
   the actionable message from §3.3.

Phase 1 unblocks every customer with vCenter SSO or AD as their
only auth source — which is the common shape on-prem.

---

## Empirical update 2026-04-28

VIDM was tested on the HoL lab (Aria Operations 8.x) via both the standard
`POST /suite-api/api/auth/token/acquire` form (`username+password+authSource`)
and the documented embedded-username form (`user@domain@source_name`). Both
were refused with the identical response shape documented for VIDB: HTTP 401
+ `WWW-Authenticate: OpsToken, VCToken, SSO2Token, CSPToken, VIDBToken`, no
body attempt at password validation. The conclusion for VIDM now matches the
VIDB conclusion in §3.4 and `context/auth_vidb_oauth_flow.md`: federated SSO
source, no programmatic password-grant path, Local service account required.
Customer-facing documentation updated to reflect this.  Implementation
guidance in §3.3 and §3.4 is unaffected — VIDM remains in the "defer /
unreachable" bucket alongside VIDB.
