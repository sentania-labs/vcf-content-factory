# Synology API Map: UPS (UPS Object)

## Endpoints

### SYNO.Core.ExternalDevice.UPS (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Core.ExternalDevice.UPS&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema (UPS connected)

```json
{
  "success": true,
  "data": {
    "model": "APC Back-UPS 1500",
    "status": "OL",
    "battery_charge": 100,
    "battery_runtime": 3600,
    "ups_load": 25,
    "vendor": "APC",
    "firmware": "..."
  }
}
```

#### Response Schema (No UPS connected -- current state of this NAS)

```json
{
  "success": true,
  "data": {
    "enabled": false
  }
}
```

**Note**: The exact response schema for a connected UPS is based on the design artifact and SNMP MIB field patterns. The live brief confirms `SYNO.Core.ExternalDevice.UPS` `get` works but notes "not connected on this NAS", so the connected-state response fields are NOT CONFIRMED from live testing. The UPS status values are derived from NUT (Network UPS Tools) conventions used by Synology: "OL" (online), "OB" (on battery), "LB" (low battery), "OB LB" (on battery + low battery).

#### Field -> Object Mapping

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `model` | model | IDENTIFIER / PROPERTY | STRING | | Primary key; also display name |
| `status` | status | PROPERTY | STRING | | NUT status codes: "OL", "OB", "LB", "OB LB" |
| `battery_charge` | battery_charge | METRIC | NUMBER | % | SOURCE: NOT CONFIRMED -- field name assumed from SNMP MIB pattern |
| `battery_runtime` | runtime | METRIC | NUMBER | seconds | SOURCE: NOT CONFIRMED -- field name assumed |
| `ups_load` | load | METRIC | NUMBER | % | SOURCE: NOT CONFIRMED -- field name assumed |
| `vendor` | vendor | PROPERTY | STRING | | SOURCE: NOT CONFIRMED |

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

## Gaps

- **All metric field names**: SOURCE: NOT CONFIRMED. No live testing was possible because no UPS is connected to this NAS. Field names are inferred from SNMP MIB patterns and NUT conventions.
- **Response structure when UPS is connected**: Needs live verification on a NAS with UPS attached.
- **UPS model as identifier**: The design artifact uses `model` as the identifier. If multiple UPS devices could be connected (e.g., via USB + network), the identifier strategy may need revision. This is unlikely for most home/SMB NAS deployments.
- **Status value enumeration**: Full set of NUT status codes that Synology passes through needs verification. Common values: OL (online/AC power), OB (on battery), LB (low battery), RB (replace battery), CHRG (charging), DISCHRG (discharging), BYPASS, CAL (calibrating), OFF, OVER (overloaded), TRIM, BOOST.
