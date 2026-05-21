# Auth-source wire formats — VCF Ops 9.0.2

Captured 2026-04-28 against `vcf-lab-operations-devel.int.sentania.net`
and `vcf-lab-operations.int.sentania.net`. Companion to
`context/auth_vidb_oauth_flow.md` (VIDB-specific deep-dive) and
the design plan `designs/auth-source-support-v1.md`.

This file documents the **wire formats** for auth-source
discovery, Suite-API token acquisition, and UI session login.
For the VIDB OAuth flow (which this file does NOT duplicate) see
`auth_vidb_oauth_flow.md`.

## Canonical taxonomy: `GET /suite-api/api/auth/sourcetypes`

Anonymous-token-required. Returns the full list of sourceTypes
the platform supports, regardless of which are currently
configured on the cluster.

```
GET /suite-api/api/auth/sourcetypes
Authorization: OpsToken <any-valid-token>
Accept: application/json
```

Response (verbatim, both labs):

```json
{
  "sourceTypes": [
    {"id": "VC", ...},
    {"id": "OPEN_LDAP", ...},
    {"id": "ACTIVE_DIRECTORY", ...},
    {"id": "SSO_SAML", ...},
    {"id": "VIDM", ...},
    {"id": "CSP", ...},
    {"id": "VIDB", ...}
  ]
}
```

`Local` and `VC_GROUP` do not appear. `Local` is synthesized by
the UI as `{id: "localItem", name: "Local Account", type: null}`.
`VC_GROUP` is materialized server-side when 2+ VC sources are
configured (the "All vCenters" aggregate); it appears in
`/api/auth/sources` but not in `/api/auth/sourcetypes`.

## Configured sources: `GET /suite-api/api/auth/sources`

```
GET /suite-api/api/auth/sources
Authorization: OpsToken <token>
Accept: application/json
```

Response shape (one element per configured source):

```json
{
  "sources": [
    {
      "id": "<uuid>",
      "name": "<operator-chosen name>",
      "sourceType": {"id": "<TYPE>", "name": "<TYPE>"},
      "created": 0, "lastModified": 0,
      "links": [{"href": "/suite-api/api/auth/sources/<uuid>", "rel": "SELF"}],
      "property": [
        {"name": "host", "value": "..."},
        {"name": "domain", "value": "..."},
        {"name": "common-name", "value": "userPrincipalName"},
        ...
      ],
      "certificates": []
    }
  ]
}
```

`property` is sourceType-specific. AD sources expose `host`,
`port`, `domain`, `base-domain`, `user-name` (the bind user),
`user-search-criteria`, `member-attribute`, `common-name`
(typically `userPrincipalName`), etc. VC sources have an empty
`property` array. VIDB sources expose `issuer-url`, `host`,
`tenant`. **No source response includes credentials.**

Single-source detail at `GET /api/auth/sources/{id}` returns the
same shape (one element, not wrapped in `sources`).

## UI dropdown source list: `/ui/login.action?mainAction=getAuthSources`

**Anonymous** — no token required. Used by the login page JS
to populate the auth-source combo box. Returns a different,
**flatter** shape than `/api/auth/sources`, with two
modifications:

1. Adds a synthesized `Local Account` entry (always first):
   `{"id": "localItem", "name": "Local Account", "description": null, "type": null}`.
2. Renames `sourceType.id` to `type` (string-valued) and drops
   the wrapper.

```bash
curl -sk "https://<host>/ui/login.action?mainAction=getAuthSources"
```

Response (devel example):

```json
[
  {"id": "localItem", "name": "Local Account", "description": null, "type": null},
  {"id": "3cf94d2a-...1f82", "name": "ad", "description": null, "type": "ACTIVE_DIRECTORY"},
  {"id": "5f7e628e-...5586", "name": "All vCenters", "description": null, "type": "VC_GROUP"},
  {"id": "5aa31ee3-...c99d", "name": "vcf-lab-mgmt", "description": null, "type": "VC"},
  {"id": "5827d79e-...0484", "name": "vcf-lab-wld01", "description": null, "type": "VC"}
]
```

This is the right endpoint for an install script to discover the
`(authSourceId, authSourceName, authSourceType)` triplet that
the `/ui/login.action` form expects. Anonymous, fast, no
chicken-and-egg with token acquisition.

## Suite-API password grant: `POST /suite-api/api/auth/token/acquire`

```
POST /suite-api/api/auth/token/acquire
Content-Type: application/json
Accept: application/json

{"username": "<user>", "password": "<pwd>", "authSource": "<source-name>"}
```

Three observed outcome classes:

### Outcome A — token minted (200)

```json
{
  "token": "<id>::<id>",
  "validity": <epoch-ms>,
  "expiresAt": "Wednesday, April 29, 2026 at 12:31:12 AM Eastern Daylight Time",
  "roles": []
}
```

`roles` is the **server's** view of the user's effective roles
at token-mint time, which is `[]` for any first-time federated
principal until an admin assigns one. Token is still usable —
authorization happens per-call, not at mint time.

Confirmed for: `Local`, `VC`, `VC_GROUP`. Empirically expected
for `OPEN_LDAP` and `ACTIVE_DIRECTORY` when the principal is
provided in NETBIOS or DN form (devel-AD specifics not
verified end-to-end; see Outcome B' below).

Token is used as `Authorization: OpsToken <token>` on subsequent
`/suite-api/` calls.

### Outcome B — server refuses password, advertises challenge (401 HTML)

```
HTTP/1.1 401
WWW-Authenticate: OpsToken, VCToken, SSO2Token, CSPToken, VIDBToken
Content-Type: text/html

<!DOCTYPE html>...<title>Not Authorized</title>...
We apologize. You are not authorized for the request.
```

Server **did not attempt** password verification — it advertised
the auth schemes it would accept instead. The `WWW-Authenticate`
list is *generic* (same five schemes regardless of source) and
does NOT identify a single "right" pre-mint flow. You must infer
from `sourceType`:

| sourceType | Implied pre-mint |
|---|---|
| `VIDB` | OAuth code exchange via `/acs/*` (requires `client_secret` we don't have) |
| `SSO_SAML` | SAML2 bearer assertion against an external IdP STS, header `Authorization: SSO2Token <saml>` |
| `VIDM` | VIDM OAuth (similar shape to VIDB) |
| `CSP` | VMware Cloud Services token, header `Authorization: CSPToken <token>` |
| `ACTIVE_DIRECTORY` (UPN form) | unexpected — see "Server-side surprises" below |

Confirmed for: `VIDB` (prod, both this probe and Jasnah's
2026-04-23 probe), `ACTIVE_DIRECTORY` with UPN-form principal
(devel).

### Outcome B' — server attempted password, returned JSON refusal (401 JSON)

```json
{
  "type": "Error",
  "message": "The provided username/password or token is not valid. Please try again.",
  "httpStatusCode": 401, "apiErrorCode": 401
}
```

No `WWW-Authenticate` challenge. Server validated the password
against the auth source's bind path and rejected. Distinguishable
from Outcome B by:

1. `Content-Type: application/json` (vs. `text/html`).
2. No `WWW-Authenticate` header.
3. Body is JSON with `apiErrorCode`.

Confirmed for: `ACTIVE_DIRECTORY` with NETBIOS-form (`int\vcf`)
or DN-form (`CN=vcf,...`) principal on devel.

## UI session login: `POST /ui/login.action`

The framework's UI session client lives at
`vcfops_packaging/templates/install.py:937-981`. The full form
contract:

```
POST /ui/login.action
Content-Type: application/x-www-form-urlencoded
Cookie: JSESSIONID=<seeded by prior GET /ui/login.action?vcf=1>

mainAction=login
&userName=<user>
&password=<pwd>
&authSourceId=<id>
&authSourceName=<name>
&authSourceType=<type>
&forceLogin=false
&timezone=0
&languageCode=us
```

Field source: the page's own JS in
`/ui/login.action` body. The `authSourceType` value comes from
`/ui/login.action?mainAction=getAuthSources`'s `type` field; for
the synthesized `Local Account` entry the `type` is null and the
form sends an empty string (`""`).

The response is a tiny string body. Observed values:

| body | meaning | next step |
|---|---|---|
| `ok` | auth and role check passed | `GET /ui/index.action` (no redirect-follow) to receive `OPS_SESSION` cookie |
| `role` | password verified, principal has zero Ops roles | UI declines session; assign a role and retry |
| `forceLogin` | session conflict (another active session for same user) | retry with `forceLogin=true` |
| `?` | opaque — observed when the JS branches the form away (VIDB/SSO_SAML/VIDM redirect paths driven via form-POST instead of the proper redirect) and for AD NETBIOS form on devel |
| (HTML page) | not yet observed for `/ui/login.action` itself, but `/ui/index.action` returns HTML on success |

**JS dispatch logic** (excerpted from the live page):

```js
var authSourceType = "LOCAL";
var source = this.authStore.getById(authSourceId);
if (source && !Ext.isEmpty(source.data.type)) {
    authSourceType = source.data.type;
}

if (authSourceType == 'SSO_SAML') { this.logInSSOUser(); return; }
if (authSourceType == 'VIDM')     { this.logInVidmUser(); return; }
if (authSourceType == 'VIDB')     { this.loginVIDBUser(); return; }

// else -- form POST with the triplet above
```

Key takeaway: **VC, VC_GROUP, ACTIVE_DIRECTORY, OPEN_LDAP, and
Local all use the same form-POST path**. Only SAML/VIDM/VIDB
divert to redirect handlers we cannot drive headlessly. The
form-POST path's `body=='ok'` is the only successful response;
anything else is a failure mode.

## OPS_SESSION cookie + CSRF token

After `body=='ok'`, fetch `/ui/index.action` **without following
redirects** (the cookie is set on the 302 itself and gets cleared
if you follow):

```
GET /ui/index.action HTTP/1.1
-> 302 / 
Set-Cookie: OPS_SESSION=<base64>; Path=/ui; Secure; HttpOnly
Set-Cookie: JSESSIONID=...
```

Decode the `OPS_SESSION` value (base64 → JSON) to extract
`csrfToken` for subsequent Struts/Ext.Direct calls. This part of
the protocol is identical regardless of authSourceType; the
hardcoded Local triplet is the only source-specific bit and
becomes a configurable input per `designs/auth-source-support-v1.md`.

## Server-side surprises worth flagging

1. **VC password grant works without SAML pre-mint.** The Ops
   server proxies the password to vCenter SSO server-side and
   mints an OpsToken on success. We do not need a vCenter STS
   SOAP client to support `sourceType=VC` for either install or
   uninstall flows.

2. **VC_GROUP is a real, queryable source.** The synthesized
   "All vCenters" aggregate (`sourceType=VC_GROUP`) accepts both
   Suite-API password grant AND UI form-POST login. Operators
   with multiple vCenters federated to one Ops cluster should
   prefer it (single source name, validates against any
   constituent vC).

3. **AD UPN-form vs. NETBIOS-form routing inside Ops.** When the
   UPN suffix matches the AD source's configured `domain`
   property, the Suite-API token-acquire endpoint routes the
   request to a token-required SSO-bridge code path and returns
   Outcome B (refusal + WWW-Authenticate challenge). NETBIOS
   form lands on the standard LDAP-bind path. The UI form does
   not exhibit this routing — it accepts UPN and dispatches to
   AD-bind directly. This is observed behavior on devel; not
   yet confirmed against another AD source with a non-matching
   domain config.

4. **`roles=[]` at first login is normal**, not a credential
   problem. New federated principals show `roleNames=[]` in
   `/api/auth/users` until an admin assigns a role. The token is
   still issued; subsequent privileged calls return 403.

5. **Federated logins create user records as a side-effect.**
   Each `(authSource, principal)` pair gets its own user UUID in
   `/api/auth/users` on first authentication. This is consistent
   with how the UI works — opening a VCF Ops console for the
   first time as a federated user creates the same record.
   Probes against an AD/VIDB/VC source therefore generate
   user-record side-effects that are not "garbage" — they are
   the platform's normal record of who has authenticated.

## Cleanup notes

`POST /suite-api/api/auth/token/release` with the token in the
`Authorization` header invalidates a token. Probes during this
investigation released all minted tokens at the end of the run
(verified `200 OK` from the release endpoint). User records
created by federated authentication were **not** deleted — they
are legitimate side-effects of the auth contract and present
identically when an admin opens the UI.
