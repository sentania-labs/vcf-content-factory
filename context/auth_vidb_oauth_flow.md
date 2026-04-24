# VCF Identity Broker (VIDB / "VCF SSO") — programmatic auth flow

Empirical investigation 2026-04-23, primary lab
`vcf-lab-operations.int.sentania.net`. Test account was a real
VIDB-federated user. Credentials are NOT persisted anywhere in
this repo — substitute `<username>` / `<password>` below.

## TL;DR

**There is no supported programmatic VIDB login flow against VCF
Ops 9.0.2.** The public + internal OpenAPI specs expose only
`POST /suite-api/api/auth/token/acquire` for token acquisition,
which takes `username + password + authSource`. That endpoint
**explicitly refuses password auth against the `VCF SSO`
(sourceType `VIDB`) auth source**; it responds with HTTP 401 and
`WWW-Authenticate: OpsToken, VCToken, SSO2Token, CSPToken,
VIDBToken` — i.e. "don't send me a password, send me a
pre-minted token."

The interactive browser flow does yield a token (delivered inside
an opaque OAuth2 `code` to the Ops server's `/ui/vidbClient/vidb/`
Struts callback), but:

1. Exchanging that code for an OAuth2 access token at
   `/acs/token` requires the confidential OAuth client's
   `client_secret`, which lives only on the Ops server
   (`token_endpoint_auth_methods_supported = [client_secret_basic,
   client_secret_post]`; no public-client grant).
2. The Ops Struts callback performs the exchange server-side,
   then **either** issues private VCF-OPERATIONS session cookies
   (success) **or** redirects to `/ui/login.action?skipSSO=true&vcf=1`
   **without setting any session cookie** (failure). In this lab,
   with this user, the callback consistently picks path (2) — the
   Ops server accepted the IdP code but declined to seat a
   session.
3. The `HZN` JWT that WS1 Access / VIDB leaves in the browser is
   only valid against `/acs/*`, `/federation/*`, and
   `/vcf-operations/plug/*` (Apache-proxied). It is **rejected**
   as a `VIDBToken` / `SSO2Token` / `CSPToken` / `Bearer` /
   `OpsToken` at `/suite-api/`.

**Practical recommendation:** for programmatic access
(install scripts, `vcfops_common` client, CI/QA), require a
Local-authSource service account. Document that VIDB-federated
users are **UI-only** on this platform version. The Local-account
flow is already what devel lab and existing tooling use.

For the content factory's install scripts, treat this as a hard
limitation: prompt the user for a Local account when the
configured `authSource` returns `VIDB` from `GET /api/auth/sources`
and either no Local source exists in parallel, or the user insists
on the VIDB identity.

---

## Discovered endpoints (primary lab)

| Role | URL | Notes |
|---|---|---|
| OIDC discovery | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/.well-known/openid-configuration` | Anonymous GET, 200 JSON |
| Authorization endpoint | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/authorize` (and tenant form `/acs/t/CUSTOMER/authorize`) | OAuth2 authorization_code only |
| Token endpoint | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/token` (and `/acs/t/CUSTOMER/token`) | `client_secret_basic` or `client_secret_post` — **no public client** |
| JWKS | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/jwks` | |
| Userinfo | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/userinfo` | |
| Revocation | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/revoke` | |
| End-session | `https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/openid/logout` | |
| Federation login form (SPA) | `https://vcf-lab-vcenter-mgmt.int.sentania.net/vidb/login?tenant=CUSTOMER&state=<uuid>` | HTML only; field names `userIdentifier`, `password` |
| Federation credential POST | `https://vcf-lab-vcenter-mgmt.int.sentania.net/federation/t/CUSTOMER/ldap/authorize?state=<uuid>&client_id=<cid>&nonce=<n>` | Returns 302 to `/acs/.../authorize` on success, 500 on bad request |
| Ops client_id (Struts SPA client) | `22177924-c638-4350-a336-6941ca5161eb` | Captured from prior `getVIDBRedirectUrl` reconnaissance |
| Ops redirect URI | `https://vcf-lab-operations.int.sentania.net/ui/vidbClient/vidb/` | Struts handler; does the server-side code→token exchange |
| `/SAAS/*` WS1 Access endpoints | n/a | All return 404 via nginx — VIDB does not expose the legacy WS1 Access `/SAAS/` REST surface |

## Supported OIDC capabilities (from discovery document)

- `response_types_supported`: `code`, `id_token token`, `id_token`,
  `code token`, `code id_token`, `code id_token token`
- `token_endpoint_auth_methods_supported`: `client_secret_basic`,
  `client_secret_post`
- `scopes_supported`: `openid`, `user`, `admin`, `profile`,
  `email`, `group`
- No `grant_types_supported` field. `grant_type=password`
  returns `401 invalid_client`, which means ROPC is refused at
  client-auth time before grant-type evaluation.

## Observed behaviours

### 1. Authorization-code flow reaches redirect_uri successfully

```
GET  /acs/t/CUSTOMER/authorize?response_type=code&client_id=<cid>
     &redirect_uri=https%3A%2F%2Fvcf-lab-operations...%2Fui%2FvidbClient%2Fvidb%2F
     &state=<s>&scope=openid&nonce=<n>
 -> 302 /federation/t/CUSTOMER/auth/login?dest=<encoded authorize URL>
 -> 302 /vidb/login?tenant=CUSTOMER&state=<uuid>   (sets AUTH_STATE_ID cookie)
 -> 200 HTML login SPA
```

Login SPA (`/vidb/login/js/login-1.js`) submits:

```
POST /federation/t/CUSTOMER/ldap/authorize?state=<uuid>&client_id=<cid>&nonce=<n>
Content-Type: application/x-www-form-urlencoded
userIdentifier=<username>&password=<password>
```

Field name is **`userIdentifier`**, not `username`. Using the
wrong field name returns HTTP 500 with an opaque "VCF Identity
Broker encountered an issue during authentication" page —
there is no useful error text. If the form POST succeeds the
response is 302 back to `/acs/.../authorize`, which then 302s
to the Ops redirect URI carrying `?code=...&state=...&nonce=...`.

### 2. Code exchange requires `client_secret` (we don't have it)

```
POST /acs/t/CUSTOMER/token
grant_type=authorization_code&code=<code>&redirect_uri=<...>&client_id=<cid>
 -> 401 {"error":"invalid_client",
         "error_description":"oauth2.authorization.credentials.invalid"}
```

The Ops Struts SPA client is confidential. The secret is server-side.
There is no public-client or PKCE pathway enabled on this IdP.

### 3. Ops-side callback performs exchange but does NOT seat a session for this user

Driving the full chain through the Ops redirect URI (so that the
Ops server does the code exchange) **consistently** yielded:

```
302 /ui/vidbClient/vidb/?code=...  -> 302 /ui/login.action?skipSSO=true&vcf=1
```

No `Set-Cookie` on the callback response. The Ops-side handler
decided not to seat a session. The same behaviour was observed
with and without a warmed `JSESSIONID`, with a browser-like
User-Agent, and whether the chain was initiated from
`/vcf-operations/` or directly from `/acs/.../authorize`.

Hypothesis: the test user authenticates at the IdP but does
not map to an Ops-side identity (role/group/scope missing, or
the `/ui/` Struts VIDB client is only valid for specific
provisioning states). Scott confirmed interactive UI login
works, so the mapping does exist somewhere — possibly the
interactive flow carries additional cookie context
(`HZN` scoped to the IdP + specific XSRF value) we're not
replicating. Could not reproduce headlessly.

### 4. `/suite-api/api/auth/token/acquire` refuses VIDB passwords

```
POST /suite-api/api/auth/token/acquire
{"username":"vcf@int.sentania.net","password":"<pwd>","authSource":"VCF SSO"}
 -> 401  (text/html "Not Authorized" page, no JSON)
    WWW-Authenticate: OpsToken, VCToken, SSO2Token, CSPToken, VIDBToken
```

Other `authSource` strings behaved differently:

| `authSource` value | Status | Body |
|---|---|---|
| `VCF SSO` (correct) | 401 HTML "Not Authorized" | server refuses password auth against VIDB source |
| `VIDB`, `vidb`, `vcf-sso`, `Local` | 401 JSON `"provided username/password or token is not valid"` | endpoint did attempt password verification, rejected credentials |

Signal: when the `authSource` is the configured VIDB source, the
server does **not even attempt** a password check — it advertises
the acceptable auth schemes and returns the HTML refusal page.
This matches the documented behaviour: VIDB users must arrive
with a pre-minted bearer token.

### 5. HZN JWT is rejected at `/suite-api/`

The `/acs` login flow seats an `HZN` cookie on the IdP domain.
Decoded header/payload (header: `{"typ":"JWT","alg":"RS256"}`;
payload fields include `sub`, `prn="vcf@CUSTOMER"`,
`iss="https://.../SAAS/t/CUSTOMER/auth"`, `domain`, `exp`).
Presenting it to `/suite-api/api/versions/current`:

| `Authorization` scheme | Status | Meaning |
|---|---|---|
| `VIDBToken <HZN>` | 401 | `"The provided token for auth scheme \"VIDBToken\" is either invalid or has expired."` (handler recognizes scheme; this is not the right token) |
| `CSPToken <HZN>` | 500 | `"Internal Server error, cause unknown."` (handler exists; crashed on the payload shape) |
| `SSO2Token <HZN>` | 500 | same |
| `Bearer <HZN>` | 401 | generic HTML refusal |
| `OpsToken <HZN>` | 401 | `"The provided token for auth scheme \"OpsToken\" is either invalid or has expired."` |

Interpretation: the real `VIDBToken` the Ops server expects is a
**different** token that the vidbClient Struts handler receives
via its back-channel code exchange (using client_secret). That
token is not exposed to the browser and cannot be extracted
from the cookie jar.

### 6. `/vcf-operations/*` is gated on Apache-proxied cookies

`/vcf-operations/` unauthenticated → 302 `/ui/login.action?vcf=1`.
Even with a valid `HZN` cookie on the IdP domain and a live Ops
JSESSIONID, hitting `/vcf-operations/rest/ops/api/versions/current`
still 302s to the login page. The cookies that gate the
`/vcf-operations/plug/*` paths (`VRNI-JSESSIONID`, a second
`JSESSIONID`, `session`, etc. — cleared with `x` expiry on
unauthenticated hits) are only issued by the successful
`/ui/vidbClient/vidb/` callback, which this probe could not
trigger.

## Working request shapes (diagnostic only — do NOT expect the token to authorize `/suite-api/`)

### OIDC discovery

```bash
curl -sk https://vcf-lab-vcenter-mgmt.int.sentania.net/acs/.well-known/openid-configuration | jq
```

### Drive the SPA login and obtain an `HZN` JWT (Python)

```python
import requests, urllib.parse
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

IDP = "vcf-lab-vcenter-mgmt.int.sentania.net"
OPS = "vcf-lab-operations.int.sentania.net"
CLIENT_ID = "22177924-c638-4350-a336-6941ca5161eb"   # Ops Struts SPA client
REDIRECT = f"https://{OPS}/ui/vidbClient/vidb/"

s = requests.Session(); s.verify = False

authorize = (f"https://{IDP}/acs/t/CUSTOMER/authorize"
             f"?response_type=code&client_id={CLIENT_ID}"
             f"&redirect_uri={urllib.parse.quote(REDIRECT,safe='')}"
             f"&state=probe&scope=openid&nonce=n1")
r = s.get(authorize, allow_redirects=True)
federation_state = dict(urllib.parse.parse_qsl(
    urllib.parse.urlparse(r.url).query))["state"]

# Submit credentials — field name is userIdentifier, not username
r = s.post(
    f"https://{IDP}/federation/t/CUSTOMER/ldap/authorize"
    f"?state={federation_state}&client_id={CLIENT_ID}&nonce=n1",
    data={"userIdentifier": "<username>", "password": "<password>"},
    allow_redirects=True,
)
# After this, the session has HZN + XSRF-TOKEN on the IdP domain,
# AND the Ops server has fired its server-side code exchange.
# If the user is fully provisioned in Ops, the session will also
# carry VCF-OPERATIONS-scoped cookies; in our probe it did not.
```

### `/suite-api/api/auth/token/acquire` — Local account (baseline that works)

```python
r = requests.post(
    f"https://{OPS}/suite-api/api/auth/token/acquire",
    json={"username": "<local-username>",
          "password": "<local-password>",
          "authSource": "Local"},
    headers={"Accept":"application/json"},
    verify=False,
)
token = r.json()["token"]
# Authorize suite-api with:
headers = {"Authorization": f"OpsToken {token}",
           "Accept":        "application/json"}
```

Use this for CI, install scripts, and every programmatic flow.
VIDB-federated users cannot acquire tokens via this endpoint.

## Token validity, refresh, logout

- **Token validity**: `/api/auth/token/acquire` doc string —
  "extended after each call, set to 6 hours from last call."
  No refresh_token concept; re-authenticate or keep calling.
- **Release**: `POST /api/auth/token/release` with the token in
  the `Authorization` header.
- **VIDB token lifecycle**: unreachable from this investigation
  because we never obtained one. The `HZN` JWT `exp` field
  showed a ~4-hour lifetime (`iat` → `exp` gap of 14400 s).

## Gotchas

- **TLS**: lab certs aren't client-trusted; use `verify=False`
  in requests or install the CA. Don't copy `verify=False` into
  production code.
- **SPA login field name is `userIdentifier`, not `username`.**
  This was the difference between a useless 500 and a working
  auth-code response.
- **IdP has a tenant path**: `/acs/t/CUSTOMER/...` — the bare
  `/acs/token` also works for the token endpoint but
  `invalid_client` against ROPC (confirming client is confidential).
- **Ops SPA client_id is `22177924-c638-4350-a336-6941ca5161eb`**
  on this lab. Might be stable across VCF 9.0.2 installs but not
  guaranteed — recover by calling
  `POST /ui/login.action mainAction=getVIDBRedirectUrl` on a live
  Ops (but note: on this lab that mainAction returns an
  `errorPanel` HTML page, suggesting it's dead or renamed in
  9.0.2 — capture from the SPA network trace instead).
- **No `grant_types_supported` in discovery.** Don't rely on
  discovery to tell you ROPC is off; probe it directly.
- **VIDB ≠ WS1 Access.** Despite the JWT `iss` claim referencing
  `/SAAS/t/CUSTOMER/auth`, the `/SAAS/*` API surface returns 404
  on this lab. Treat VIDB as its own thing.
- **UI flow is admin-bound for OPS session seating.** Memory note
  `project_ui_only_pak_lifecycle` and
  `feedback_admin_uninstall` both point at this: VCF Ops' UI
  session behaviour is tightly scoped. If even a headless VIDB
  login succeeded, only operations permitted for the mapped
  VIDB identity would work — dashboard/view delete requires
  `admin`.

## Same flow with Local / VC-type sources

Confirmed mutually exclusive with this path:

- **Local**: `/api/auth/token/acquire` with `authSource=Local`
  works (already in use by existing tooling). Does NOT go
  through `/acs/*` or `/federation/*` at all.
- **VC-type (SSO2Token)**: `/suite-api/` would accept an
  `Authorization: SSO2Token <token>` header if a vCenter SSO
  SAML token were obtained from vCenter STS. Not probed here —
  needs a vCenter host + STS endpoint. Orthogonal to VIDB.
- **CSP**: applicable to VMware Cloud Services; not relevant to
  an on-prem lab.

## Dead ends encountered (with evidence)

1. **Direct ROPC at `/acs/token`** — 401 `invalid_client`
   regardless of tenant variant. Client is confidential.
2. **JWT-bearer assertion grant** (`grant_type=
   urn:ietf:params:oauth:grant-type:jwt-bearer`) at
   `/SAAS/t/CUSTOMER/auth/oauthtoken` — 404 (nginx). Path not
   present on VIDB.
3. **Legacy WS1 Access `/SAAS/API/1.0/REST/auth/system/login`** — 404.
4. **Submitting the Ops-minted auth `code` to `/acs/token` without
   `client_secret`** — 401 `invalid_client`.
5. **Presenting the `HZN` JWT as a `VIDBToken` / `CSPToken` /
   `SSO2Token` / `Bearer` at `/suite-api/`** — all rejected
   (401 or handler-crash 500).
6. **`POST /suite-api/api/auth/token/acquire` with
   `username+password+authSource=VCF SSO`** — 401, server
   refuses password auth for VIDB sources and returns the
   `WWW-Authenticate` challenge list.
7. **`POST /ui/login.action mainAction=getVIDBRedirectUrl`** on
   this 9.0.2 lab returns Struts errorPanel HTML — the mainAction
   is dead. This is consistent with the "VCF Ops 9.0.2 UI
   endpoints are dead" memory note.

## Implications for the content factory

- Keep `vcfops_common` and install scripts on the Local authSource
  path. The existing `VCFOPS_USER` / `VCFOPS_PASSWORD` /
  optional `VCFOPS_AUTH_SOURCE` (default `"Local"`) contract is
  correct and should stay.
- When a deployment has **only** the `VCF SSO` auth source (no
  Local), programmatic install is **not currently supported** by
  this framework. Flag this at env-validation time: if
  `GET /api/auth/sources` returns only a `VIDB`-type source,
  emit a clear error telling the operator to create a Local
  service account for CI/automation use.
- Update `context/vcf_operations_api_surface.md` §`/vcf-operations/*`
  to point here instead of re-enumerating the dead-end list.
- No change needed to `content-installer` logic. The dead ends
  above confirm the existing architecture choices.

## Follow-up questions (not pursued)

1. **Why does the Ops vidbClient callback refuse to seat a session
   for this federated user headlessly when interactive UI login
   works?** Candidates: a UA / Accept-Encoding whitelist on the
   Struts handler; a pre-auth XSRF check bound to a cookie we
   can't replicate; a `Referer` check; or the interactive flow
   goes through a different path (e.g. `/vcf-operations/rest/ops/`
   SPA initialization that pre-registers a session token). Would
   need a live Chrome DevTools capture from Scott to resolve.
2. **Is the Ops Struts client_secret extractable from an admin-
   session endpoint?** `/admin/` or
   `/suite-api/internal/auth/sources/export` might carry it in
   the VIDB source config JSON. Not probed (would require
   admin-level access on primary, which is read-only).
3. **vCenter SSO STS path for SSO2Token** — documented in the
   public spec at a high level; full probing requires a vCenter
   credential and an STS endpoint, out of scope for the primary
   lab pass.
