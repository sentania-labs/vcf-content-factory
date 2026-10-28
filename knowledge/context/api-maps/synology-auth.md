# Synology API Map: Authentication

> **Request method (2026-10-28, Synology build 35, synology#16).** Build 35
> calls every authenticated DSM API, login and logout included, as an
> HTTPS form POST to `/webapi/<cgi>` with `api`, `version`, `method`, the
> parameters and `_sid` (login: `account`, `passwd`) in an
> `application/x-www-form-urlencoded` body, so the password and session id
> never reach DSM's access log or a proxy log. DSM still accepts GET with the
> same parameters in the query string. Only the session-less
> `SYNO.API.Info` query (`/webapi/query.cgi`) stays GET. Where a section
> below says "Method: GET" or shows `?api=...&_sid=...`, read it as the
> parameter set; send it as POST. Checked live on DS1520+ / DSM 7.4.1-90080,
> 2026-10-28: GET and POST both succeed for `SYNO.DSM.Info`,
> `SYNO.Core.Hardware.FanSpeed` and `SYNO.Storage.CGI.Storage load_info`;
> `SYNO.API.Info` GET on `query.cgi` succeeds; Auth v7 login and logout as
> POST succeed. Build 35 itself verified all 14 of its data APIs as POST
> on DSM 7.3.2 (pak CHANGELOG 0.0.0.35, #16).

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `$SYNO_HOST:$SYNO_PORT` — DS1520+ running DSM
  7.3.2-86009 Update 1 (credentials from repo `.env`)
- **Last updated:** 2026-04-21
- **Update history:**
  - 2026-04-21 — Re-verified login / logout flow against the live
    NAS; added Provenance block; tagged pre-existing observations
    with `[re-verified 2026-04-21]` or
    `[unchanged since 2026-04-16]`.
  - 2026-04-16 — Initial mapping (backfilled from file mtime;
    original author session did not capture a Provenance block).
- **Evidence basis:** live API calls (GET `login` + `logout` this
  session); vendor error code table is upstream Synology docs.

## Endpoints

### SYNO.API.Info

- **Path**: `/webapi/query.cgi` `[unchanged since 2026-04-16]`
- **Method**: GET (session-less; stays GET in build 35)
- **Params**: `api=SYNO.API.Info&version=1&method=query&query=all`
- **Auth**: None required (public endpoint) `[unchanged since 2026-04-16]`

#### Response Schema

```json
{
  "success": true,
  "data": {
    "SYNO.API.Auth": {
      "path": "entry.cgi",
      "minVersion": 1,
      "maxVersion": 7,
      "requestFormat": "JSON"
    },
    "SYNO.Core.System.Utilization": {
      "path": "entry.cgi",
      "minVersion": 1,
      "maxVersion": 1
    }
  }
}
```

#### MPB Notes

- Returns 674 APIs on DSM 7.3.2 `[unchanged since 2026-04-16]`
- Each entry has `path`, `minVersion`, `maxVersion`
- Use this at adapter startup to validate available APIs and version ranges
- This is the only endpoint that uses `query.cgi`; all others use `entry.cgi`

---

### SYNO.API.Auth (login)

- **Path**: `/webapi/entry.cgi` `[re-verified 2026-04-21]`
- **Method**: POST form body with `account` and `passwd` in the body (build 35, synology#16). Mapped as GET `[re-verified 2026-04-21]`, which DSM still accepts, but a GET puts the password in the URL and DSM's access log: do not use it.
- **Params**: `api=SYNO.API.Auth&version=7&method=login&account=<USER>&passwd=<PASS>&session=<SESSION_NAME>&format=sid`
- **Auth**: None (this IS the auth endpoint)
- **Version range**: 1-7 on DSM 7.3.2 (use v7; v6 as fallback)
  `[unchanged since 2026-04-16]`

#### Request Parameters

| Parameter | Required | Description |
|---|---|---|
| `account` | yes | Username |
| `passwd` | yes | Password |
| `session` | yes | Arbitrary session name (e.g., `VCFOpsMonitoring`) |
| `format` | yes | `sid` (return session ID in JSON) or `cookie` (set HTTP cookie) |
| `otp_code` | conditional | Required if 2FA is enabled on the account |
| `enable_syno_token` | no | Set to `yes` to get CSRF token |

#### Response Schema `[re-verified 2026-04-21]`

```json
{
  "success": true,
  "data": {
    "sid": "abcdef1234567890",
    "synotoken": "..."
  }
}
```

The 2026-04-21 re-verify hit `format=sid` and received `success:
true` with a populated `data.sid`. No 2FA challenge returned for
the lab account. `synotoken` was not requested and not returned
(only appears when `enable_syno_token=yes` is set).
`[observed 2026-04-21]`

#### Session Maintenance

- Pass `_sid=<SESSION_ID>` on all subsequent requests: in the POST form body (build 35, synology#16; with no `_sid` in the body DSM answers 119). ~~as a query parameter~~ superseded 2026-10-28; DSM still accepts it there, and also as the `id` cookie.
  `[re-verified 2026-04-21]`
- Session lifetime: **7 days** (default) `[unchanged since 2026-04-16]`
- Re-authenticate on error codes: `[unchanged since 2026-04-16]`
  - `106` = session timeout
  - `107` = session interrupted by duplicate login
  - `119` = session ID not found / invalid
- MPB should use `format=sid` (simpler than cookies for REST adapter)

---

### SYNO.API.Auth (logout)

- **Path**: `/webapi/entry.cgi` `[re-verified 2026-04-21]`
- **Method**: POST form body with `_sid` in the body (build 35, synology#16). Mapped as GET, which DSM still accepts.
- **Params**: `api=SYNO.API.Auth&version=7&method=logout&session=<SESSION_NAME>&_sid=<SESSION_ID>`
- **Auth**: Active session

#### Response Schema `[re-verified 2026-04-21]`

```json
{
  "success": true
}
```

---

## Error Codes (Common) `[unchanged since 2026-04-16]`

| Code | Meaning | MPB Action |
|---|---|---|
| 100 | Unknown error | Log and retry |
| 101 | Missing API/method/version param | Fix request (bug) |
| 102 | API does not exist | Skip endpoint, log warning |
| 103 | Method does not exist | Check API version |
| 104 | Version not supported | Fall back to lower version |
| 105 | No permission | Check account is admin |
| 106 | Session timeout | Re-authenticate |
| 107 | Session interrupted (duplicate login) | Re-authenticate |
| 119 | Session ID not found | Re-authenticate |

## MPB Configuration Notes

- **Auth type**: SESSION (login endpoint returns sid, pass as `_sid` in the POST form body; ~~query param~~ superseded 2026-10-28, still accepted)
  `[re-verified 2026-04-21]`
- **Admin account required**: Most `SYNO.Core.*` and `SYNO.Storage.CGI.*` APIs require admin privileges
  `[unchanged since 2026-04-16]`
- **2FA consideration**: If the monitoring account has 2FA enabled, MPB cannot provide TOTP codes dynamically. Recommendation: use a dedicated monitoring account without 2FA, or use device token mechanism after initial manual 2FA setup
- **Session name**: Use a unique session name (e.g., `VCFOpsMP`) to avoid collisions with other integrations
- **Re-auth strategy**: On any 106/107/119 error, re-authenticate before retrying the failed request
- **Base URL**: `https://<NAS_IP>:5001/webapi/entry.cgi` (HTTPS on port 5001; HTTP on 5000)
  `[unchanged since 2026-04-16]`
- **All API calls go to the same path** (`/webapi/entry.cgi`, except `SYNO.API.Info` on `query.cgi`) differentiated only by the `api`/`version`/`method` parameters (form body under build 35; ~~query parameters~~ superseded 2026-10-28)
