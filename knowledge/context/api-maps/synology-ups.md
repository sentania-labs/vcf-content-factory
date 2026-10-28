# Synology API Map: UPS (UPS Object)

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

> **Correction 2026-10-28 (Synology build 35, review B1).** `status` is a
> DSM string-table key, not a NUT status code. Every NUT claim below
> (`OL`, `OB`, `LB`, `OB LB`, "follows NUT conventions") is
> **SUPERSEDED 2026-10-28**. The values are:
>
> | `status` | DSM label (`[ups]` string table) | Meaning |
> |---|---|---|
> | `usb_ups_status_online` | Connected | On mains |
> | `usb_ups_status_battery` | On Battery | Power lost, running on battery |
> | `usb_ups_status_low_batt` | Low Battery | Battery low |
> | `usb_ups_status_off` | Off | UPS off |
> | `usb_ups_status_unknown` | (no `[ups]` entry; admin_center.js shows `_T("common","not_support")`) | No UPS / not detected |
>
> None of these contains `OB` or `LB`, so a `CONTAINS "OB"` condition never
> fires. Match with `EQ` on the full key.
>
> Evidence:
> - Live NAS, read-only, 2026-10-28: DS1520+, **DSM 7.4.1-90080**. POST login,
>   `SYNO.Core.ExternalDevice.UPS get` returned `status: usb_ups_status_unknown`,
>   `usb_ups_connect: false`, `enable: false`, `mode: SLAVE`. Logged out.
> - The NAS's own `/webman/texts/enu/strings`, fetched the same day: `[ups]`
>   holds exactly `usb_ups_status_online` "Connected",
>   `usb_ups_status_battery` "On Battery", `usb_ups_status_low_batt`
>   "Low Battery", `usb_ups_status_off` "Off" (plus the
>   `usb_ups_status_title` label). `[widget]` also carries
>   `usb_ups_status_battery` and `usb_ups_status_low_batt` as System Health
>   messages (see `synology-system.md`, SYNO.Core.System.SystemHealth).
> - `/webman/modules/AdminCenter/admin_center.js` `onClickStatusButton`
>   renders `_T("ups", this.UPSInfo.status)` and special-cases
>   `usb_ups_status_online` (plain label) and `usb_ups_status_unknown`
>   (`common:not_support`); every other status is drawn in red.
> - Synology pak (`content/sdk-adapters/synology`, branch `build-35`,
>   commit `2ffd1ed`): CHANGELOG 0.0.0.35 and REFERENCE.md "Bundled alerts"
>   (UPS On Battery: `EQ usb_ups_status_battery` Warning,
>   `EQ usb_ups_status_low_batt` Critical);
>   `knowledge/context/reviews/synology-build-35.md` B1.
>
> **Still a gap:** the lab has no UPS. The connected values come from DSM's
> own UI code and string table; none has been seen on a live UPS.

## Endpoints

### SYNO.Core.ExternalDevice.UPS (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: POST form body, `_sid` in the body (build 35, synology#16); DSM still accepts GET
- **Params**: `api=SYNO.Core.ExternalDevice.UPS&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema (No UPS connected -- confirmed 2026-04-16)

**CONFIRMED 2026-04-16 via live API call.** No UPS is connected to this NAS. The API returns the full configuration structure even when no UPS is present.

```json
{
  "success": true,
  "data": {
    "ACL_enable": false,
    "ACL_list": [],
    "charge": 0,
    "delay_time": -1,
    "enable": false,
    "manufacture": "",
    "mode": "SLAVE",
    "model": "",
    "net_server_ip": "",
    "runtime": 0,
    "shutdown_device": false,
    "snmp_auth": false,
    "snmp_auth_key": false,
    "snmp_auth_type": "",
    "snmp_community": "",
    "snmp_mib": "",
    "snmp_privacy": false,
    "snmp_privacy_key": false,
    "snmp_privacy_type": "",
    "snmp_server_ip": "",
    "snmp_user": "",
    "snmp_version": "",
    "status": "usb_ups_status_unknown",
    "usb_ups_connect": false
  }
}
```

#### Response Schema (UPS connected -- inferred from no-UPS response; `status` value corrected 2026-10-28, was `"OL"`)

When a UPS is connected, the same fields are expected to be populated:
```json
{
  "success": true,
  "data": {
    "charge": 100,
    "runtime": 3600,
    "enable": true,
    "manufacture": "APC",
    "model": "Back-UPS 1500",
    "mode": "MASTER",
    "status": "usb_ups_status_online",
    "usb_ups_connect": true,
    "delay_time": 300,
    "shutdown_device": true
  }
}
```

**Note**: The no-UPS response reveals the actual field names. Key corrections from the original assumptions:
- `battery_charge` is actually `charge` (NUMBER, %)
- `battery_runtime` is actually `runtime` (NUMBER, seconds)
- `ups_load` does NOT appear in the response -- no load field observed. Load may require SNMP or may only appear when a UPS is actually connected.
- `vendor` is actually `manufacture` (STRING)
- ~~`status` uses NUT-style codes but the no-UPS value is `"usb_ups_status_unknown"` (not empty or null)~~ **SUPERSEDED 2026-10-28:** `status` is always a DSM `usb_ups_status_*` key (see the correction at the top); `usb_ups_status_unknown` with no UPS
- `usb_ups_connect` (BOOLEAN) is the definitive "is a UPS present" flag
- `enable` (BOOLEAN) indicates whether UPS support is enabled in DSM settings
- `mode` (STRING) indicates MASTER (USB-connected) or SLAVE (network UPS) mode

#### Field -> Object Mapping

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `model` | model | IDENTIFIER / PROPERTY | STRING | | Primary key; also display name. Empty string when no UPS connected. |
| `manufacture` | vendor | PROPERTY | STRING | | UPS manufacturer (was assumed to be `vendor`) |
| `status` | status | PROPERTY | STRING | | DSM key: `usb_ups_status_online` / `_battery` / `_low_batt` / `_off`; `usb_ups_status_unknown` when not connected. (~~NUT codes "OL", "OB", "LB", "OB LB"~~ superseded 2026-10-28.) |
| `charge` | battery_charge | METRIC | NUMBER | % | Battery charge level (was assumed to be `battery_charge`). Returns 0 when no UPS connected. |
| `runtime` | runtime | METRIC | NUMBER | seconds | Estimated battery runtime (confirmed field name). Returns 0 when no UPS connected. |
| `enable` | ups_enabled | PROPERTY | BOOLEAN | | Whether UPS support is enabled in DSM |
| `usb_ups_connect` | ups_connected | PROPERTY | BOOLEAN | | Whether a UPS is physically detected |
| `mode` | ups_mode | PROPERTY | STRING | | "MASTER" (USB) or "SLAVE" (network UPS server) |
| `delay_time` | delay_time | PROPERTY | NUMBER | seconds | Shutdown delay after power loss; -1 when not configured |
| `shutdown_device` | shutdown_device | PROPERTY | BOOLEAN | | Whether NAS should shut down on UPS low battery |

---

## Identifier Chains (Relationships)

### Diskstation -> UPS
- 0:1 relationship (one UPS per Diskstation, or none)
- Direct child of Diskstation
- UPS object only exists when a UPS is connected and detected
- No explicit join field needed

---

## Collection Strategy

- **Requests per cycle (15-min interval)**: 1
  - `SYNO.Core.ExternalDevice.UPS` `get` -- UPS status and metrics

- **Pagination**: None -- single UPS response
- **Known quirks**:
  - If no UPS is connected, the API returns successfully but with minimal data (just `enabled: false` or similar)
  - MPB should handle the no-UPS case gracefully: do not create a UPS object if no UPS data is present
  - UPS metrics depend on the UPS model's capability -- basic UPS devices may only report status and charge, not load or runtime
  - ~~Status values follow NUT conventions, not plain English ("OL" not "Online")~~ **SUPERSEDED 2026-10-28:** status values are DSM string-table keys (`usb_ups_status_*`), neither NUT codes nor plain English. Match the whole key with `EQ`.
  - DSM omits or blanks `status` on some reads; the build 35 adapter skips the property then rather than publishing `""` (review W1).
  - Battery runtime is estimated, not guaranteed

## Gaps (partially closed 2026-04-16)

- **Field names**: CONFIRMED from no-UPS response. `charge` (not `battery_charge`), `runtime` (confirmed), `manufacture` (not `vendor`). No `ups_load` field observed -- load percentage may only appear when a UPS is actually connected, or may not be exposed by this API at all.
- **Response structure when UPS is connected**: Partially confirmed. The no-UPS response reveals the complete field set. The connected-UPS response is expected to populate the same fields but cannot be verified without a connected UPS. The inferred connected-state schema above is based on the observed field names + logical values.
- **UPS model as identifier**: Still valid design choice. The `model` field exists (empty string when no UPS). Only one UPS can be connected per NAS (USB or network, controlled by `mode`).
- **Load metric**: NOT AVAILABLE in the observed response. No `load`, `ups_load`, or similar field. This may be a limitation of the REST API vs. SNMP, or it may only appear with a connected UPS. Flagged as remaining gap.
- **Status value enumeration**: CLOSED from vendor UI code 2026-10-28 (DSM 7.4.1-90080 string table and admin_center.js): `usb_ups_status_online`, `_battery`, `_low_batt`, `_off`, `_unknown`. ~~Connected-state values are still assumed to follow NUT conventions~~ (superseded 2026-10-28). Remaining gap: not yet seen on a live connected UPS.
