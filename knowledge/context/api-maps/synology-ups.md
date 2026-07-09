# Synology API Map: UPS (UPS Object)

## Endpoints

### SYNO.Core.ExternalDevice.UPS (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
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

#### Response Schema (UPS connected -- inferred from no-UPS response)

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
    "status": "OL",
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
- `status` uses NUT-style codes but the no-UPS value is `"usb_ups_status_unknown"` (not empty or null)
- `usb_ups_connect` (BOOLEAN) is the definitive "is a UPS present" flag
- `enable` (BOOLEAN) indicates whether UPS support is enabled in DSM settings
- `mode` (STRING) indicates MASTER (USB-connected) or SLAVE (network UPS) mode

#### Field -> Object Mapping

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `model` | model | IDENTIFIER / PROPERTY | STRING | | Primary key; also display name. Empty string when no UPS connected. |
| `manufacture` | vendor | PROPERTY | STRING | | UPS manufacturer (was assumed to be `vendor`) |
| `status` | status | PROPERTY | STRING | | NUT status codes when connected: "OL", "OB", "LB", "OB LB"; "usb_ups_status_unknown" when not connected |
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
  - Status values follow NUT conventions, not plain English ("OL" not "Online")
  - Battery runtime is estimated, not guaranteed

## Gaps (partially closed 2026-04-16)

- **Field names**: CONFIRMED from no-UPS response. `charge` (not `battery_charge`), `runtime` (confirmed), `manufacture` (not `vendor`). No `ups_load` field observed -- load percentage may only appear when a UPS is actually connected, or may not be exposed by this API at all.
- **Response structure when UPS is connected**: Partially confirmed. The no-UPS response reveals the complete field set. The connected-UPS response is expected to populate the same fields but cannot be verified without a connected UPS. The inferred connected-state schema above is based on the observed field names + logical values.
- **UPS model as identifier**: Still valid design choice. The `model` field exists (empty string when no UPS). Only one UPS can be connected per NAS (USB or network, controlled by `mode`).
- **Load metric**: NOT AVAILABLE in the observed response. No `load`, `ups_load`, or similar field. This may be a limitation of the REST API vs. SNMP, or it may only appear with a connected UPS. Flagged as remaining gap.
- **Status value enumeration**: The no-UPS value is `"usb_ups_status_unknown"` (not a NUT code). Connected-state values are still assumed to follow NUT conventions but cannot be verified without a UPS.
