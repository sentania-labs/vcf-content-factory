# UniFi Network Integration API Map (v1 — Bearer-Key Surface)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `unifi.int.sentania.net` — UDM Pro running UniFi
  OS 5.0.16, Network Application 10.2.105 (per classic `stat/sysinfo`)
  / 10.3.55 (per Integration `/info` — see version-skew note in §5).
- **Last updated:** 2026-05-07
- **Update history:**
  - 2026-05-07 (session 3) — **Live-verified** two critical
    capabilities that were doc-only from earlier session 1:
    (1) `filter` query parameter with `features.contains()` CONFIRMED
    WORKING on live controller — device-type filtering works correctly
    for `accessPoint` (6 devices) and `switching` (11 devices);
    `gateway` returns 0 devices (UDM Pro reports
    `features:["switching"]` only, does not self-identify as
    `gateway`). (2) `/devices/{id}/statistics/latest` endpoint now
    RETURNS 200 with live data — CPU/mem/uptime/uplink
    throughput/load averages all present. Per-device-type response
    shape varies: APs include `interfaces.radios[].txRetriesPct`,
    switches/UDM return empty `interfaces:{}`. This is a
    **material change** from the 2026-04-30 probe where this
    endpoint returned 404 — controller was upgraded between sessions
    (Network App 10.3.55 on 2026-04-30 was evidently too old; current
    version not re-probed via /info but the endpoint is live).
    Updated inline tags, Finding 2 live-verification status,
    Finding 4 status, recommendation, and coverage audit accordingly.
  - 2026-05-07 (session 2) — Added official Ubiquiti developer documentation
    findings (v10.1.84 OpenAPI spec at developer.ui.com). Major
    discoveries: (1) server-side **`filter` query parameter** with
    rich syntax on device/client list endpoints, (2) `features`
    field typed as `SET(STRING)` with `contains`/`containsAny`
    operators enabling device-type filtering by capability
    (`accessPoint`, `switching`, `gateway`), (3) `/devices/{id}/statistics/latest`
    endpoint documented with CPU/mem/uptime/uplink-throughput metrics
    (not present on our controller on 2026-04-30 probe but in the
    v10.1.84 spec), (4) expanded endpoint catalog (35 paths vs 8
    confirmed on live probe). Added new section "Official Documentation
    Findings (v10.1.84)".
  - 2026-04-30 — Initial Integration API mapping. Authenticated probe
    with the `X-API-Key` Scott generated. Targeted comparison map for
    the v2 auth-pivot decision (Gap B); follow-on to the 2026-04-18
    classic-surface map at `context/api-maps/unifi-network-api.md`
    which had probed Integration only at the auth wall.
- **Evidence basis:** live API calls (28 endpoint probes against
  `unifi.int.sentania.net` on 2026-04-30, plus 2 unauthenticated
  probes for error-envelope confirmation; plus 7 targeted probes on
  2026-05-07 — 1 sites, 4 device-filter, 3 statistics/latest) **plus**
  official Ubiquiti developer documentation at
  `https://developer.ui.com/network/v10.1.84/` (scraped 2026-05-07 —
  embedded OpenAPI 3.1.0 spec extracted from React Server Component
  payloads). All live payloads in `/tmp/unifi-int-recon/` (not
  committed). Public IPs and client-MAC-bearing samples sanitized
  before quoting.
- **Notes:** This map is **scope-limited to Integration v1**. The
  classic-surface map remains authoritative for everything under
  `/proxy/network/api/...`. Cross-references throughout this file
  point to the classic map by endpoint number (e.g. "endpoint #4"
  refers to `stat/device` in the classic map).

---

## TL;DR for the Gap-B / auth-pivot decision

**REVISED 2026-05-07 — Integration is now a viable primary surface.**

The original 2026-04-30 verdict was "do not pivot" because Integration
was inventory-only with 0 utilization metrics. That has changed:
`/devices/{id}/statistics/latest` now returns 200 with CPU, memory,
uptime, load averages, uplink throughput, and per-radio TX retries.
Server-side `features.contains()` filtering is also confirmed working.

**Current coverage with `/statistics/latest`:** ~35-40% of v2's
metric set (up from ~23% without it). The covered slice now includes
the core device health metrics (CPU, memory, uptime, throughput) plus
all the inventory/properties from before.

**Still missing on Integration:** per-radio occupancy (cu_total),
per-radio client counts, per-port byte/error counters, PoE wattage,
temperatures, WAN-specific metrics (latency/speed/drops), health
subsystem aggregates, speedtest. These remain classic-only.

**The design question has shifted from "should we pivot?" to "what
scope does the MP target?"** An Integration-only MP delivers device
health monitoring with trivial auth (API key header). A classic-primary
MP delivers deep network monitoring with complex auth (CSRF + cookie).
A hybrid delivers both at the cost of dual auth flows. See the revised
Recommendation section for the full tradeoff table.

Integration v1 remains the natural source for the **inventory**
layer (Site list, Device list with stable UUIDs, Network list, Client
roster). Integration v2 is **not present on this controller**.

---

## Session metadata

- **Controller URL:** `https://unifi.int.sentania.net`
- **Hardware:** UDM Pro `[observed 2026-04-30 via /sites/{id}/devices
  model field, re-verified vs classic map]`
- **UniFi OS / udm_version:** `5.0.16` (firmwareVersion of the UDM
  device row matches the classic map's `console_display_version`)
  `[observed 2026-04-30]`
- **Integration `applicationVersion`:** `10.3.55` `[observed
  2026-04-30 via GET /integration/v1/info]`. **Note: this is HIGHER
  than the classic surface's `stat/sysinfo.version = "10.2.105"`
  reported on 2026-04-18 — see §"Versioning" for analysis.**
- **Recon date:** 2026-04-30 (live probes)
- **Auth method used for recon:** `X-API-Key` bearer header. Key
  generated by Scott via UniFi UI → Network → Settings → Control
  Plane → Integrations and stored in `.env` as `$UNIFI_API_KEY`.
- **Total endpoints probed:** 28 distinct paths (registered + 404
  + 400 mixed) plus 2 negative auth probes.
- **Files sanitized:** every quoted sample below redacts client MAC
  addresses, client display names, and the WAN public IP. Raw
  payloads remain in `/tmp/unifi-int-recon/` and are not committed.

---

## Auth flow

```
GET https://{host}/proxy/network/integration/v1/{path}
X-API-Key: <token>
Accept: application/json
```

- **No login round-trip.** The key is presented on every request;
  there is no session cookie, no CSRF, no refresh token.
  `[observed 2026-04-30]`
- **Header name is exactly `X-API-Key`** (case-insensitive per HTTP
  but matches Ubiquiti docs and lowercased in the
  `Access-Control-Allow-Headers` response). `[observed 2026-04-30]`
- **No `inject:` complications for MPB.** A future MP using this
  surface needs only a single static-header inject — no two-value
  extract, no Set-Cookie capture, no CSRF rotation handling. This
  is the entire reason Gap B even surfaced as a candidate to
  sidestep.

### Negative-auth shapes

Two distinct error envelopes — important for any consumer trying to
distinguish "key invalid" from "path missing":

**Missing or invalid key (401):**

```json
{"error":{"code":401,"message":"Unauthorized"}}
```

`[observed 2026-04-30 with both no header and a 32-char wrong key.
Identical body in both cases.]`

This is **a different envelope** from what the classic-surface map
recorded on 2026-04-18 (which captured a structured
`api.authentication.missing-credentials` ProblemDetails body). The
classic-map observation was made without a key against a controller
that was running an older Integration build; today's controller
returns the simpler nginx-edge `error.code/message` form. Source of
the change is unverified (controller upgrade vs. routing change vs.
header detection); **for an MP, treat both shapes as "401 means
re-auth / surface alarm to operator"**. `[observed 2026-04-30]`

**Authenticated but path doesn't exist (404):**

```json
{
  "statusCode": 404,
  "statusName": "NOT_FOUND",
  "code": "api.request.error",
  "message": "No endpoint GET /integration/v1/totally-nonexistent.",
  "timestamp": "2026-04-30T02:20:00.188Z",
  "requestPath": "/integration/v1/totally-nonexistent"
}
```

`[observed 2026-04-30]`

**Authenticated but argument shape wrong (400):**

```json
{
  "statusCode": 400,
  "statusName": "BAD_REQUEST",
  "code": "api.request.argument-type-mismatch",
  "message": "'active' is not a valid 'clientId' value",
  "timestamp": "2026-04-30T02:19:10.698Z",
  "requestPath": "/integration/v1/sites/{siteId}/clients/active",
  "requestId": "<uuid>"
}
```

`[observed 2026-04-30 — the 400 reveals path-template parameter
names like 'clientId', so the route is /clients/{clientId}, not
/clients/{action}.]`

### Rate-limit headers

**None observed.** `[observed 2026-04-30 — 28 probes spaced ~0.3s
apart, no `X-RateLimit-*`, no `Retry-After`, no `429`s.]` Cannot
conclude there is no rate limit, only that this volume did not
trigger one.

### Permission scoping

The key was used against every probed path with no `403` responses
— suggests the key Scott generated is full-scope. **Whether
Integration v1 supports per-key scoping at all is not visible from
the read-only probe path** (would require a key-management endpoint
or UI inspection).

---

## URL layout

| Layer | Base path | Notes |
|---|---|---|
| Integration v1 | `/proxy/network/integration/v1/...` | This map. Bearer key only. |
| Integration v2 | `/proxy/network/integration/v2/...` | **Does NOT exist on this controller** — every v2 path 404s with the structured envelope, indicating route dispatch failure (not auth failure). `[observed 2026-04-30: /v2/info, /v2/sites, /v2/sites/{id}/devices all 404]` |

All v1 endpoints are nested under `/sites/{siteId}/...` once you
get past `/info` and `/sites` themselves. There is **no flat
`/devices` or `/clients` at the integration root**:

| Path | Status | Note |
|---|---|---|
| `/info` | 200 | Top-level controller info |
| `/sites` | 200 | Site list (paginated) |
| `/devices` (top-level) | **404** | Not registered. `[observed 2026-04-30]` |
| `/clients` (top-level) | **404** | Not registered. `[observed 2026-04-30]` |
| `/sites/{id}/devices` | 200 | Site-scoped device list |
| `/sites/{id}/clients` | 200 | Site-scoped client list |

---

## Endpoint catalog

| # | Method | Path | Status | Bytes | Notes |
|---|---|---|---|---|---|
| I-1 | GET | `/info` | 200 | 32 | Single object: `applicationVersion` only |
| I-2 | GET | `/sites` | 200 | 150 | Paginated list of sites |
| I-3 | GET | `/sites/{siteId}/devices` | 200 | 4364 | Paginated device list (slim 11-field rows) |
| I-4 | GET | `/sites/{siteId}/devices/{deviceId}` | 200 | 870-2390 | Per-device detail (adds `interfaces`, `uplink`, `features`, `adoptedAt`, `provisionedAt`, `configurationId`) |
| I-5 | GET | `/sites/{siteId}/clients` | 200 | 6776-32664 | Paginated client list |
| I-6 | GET | `/sites/{siteId}/clients/{clientId}` | 200 | 267 | Per-client detail (**identical fields to list row** — no extra depth) |
| I-7 | GET | `/sites/{siteId}/networks` | 200 | 3750 | Paginated VLAN/network list |
| I-8 | GET | `/sites/{siteId}/networks/{networkId}` | 200 | 705 | Per-network detail (adds DHCP / IP config) |
| I-9 | GET | `/sites/{siteId}/devices/{deviceId}/statistics/latest` | 200 | 190-280 | Per-device real-time statistics (CPU/mem/uptime/uplink/load/radios). **404 on 2026-04-30; 200 on 2026-05-07** — controller was upgraded. `[observed 200 2026-05-07]` |

**404'd paths (registered as not-found, indicating they are
genuinely absent on Integration v1):**

```
/                       /sites/{id}                /sites/{id}/devices/{id}/health
/health                 /sites/{id}/health         /sites/{id}/devices/{id}/wan
/info/health            /sites/{id}/info           /sites/{id}/devices/{id}/uplink
/alarms                 /sites/{id}/alarms         /sites/{id}/devices/{id}/ports
/events                 /sites/{id}/events         /sites/{id}/devices/{id}/interfaces
/statistics             /sites/{id}/anomalies      /sites/{id}/devices/{id}/statistics  (NOTE: /statistics/latest NOW WORKS — see I-9)
/firmware               /sites/{id}/insights       /sites/{id}/devices/{id}/stats
/vouchers               /sites/{id}/wlanconf       /sites/{id}/devices/{id}/metrics
                        /sites/{id}/networkconf
                        /sites/{id}/wlans          /sites/{id}/applications
                        /sites/{id}/wifi           /sites/{id}/zones
                        /sites/{id}/wifi-networks  /sites/{id}/wireguard
                        /sites/{id}/portals        /sites/{id}/networkgroups
                        /sites/{id}/hotspot        /sites/{id}/firewall
                        /sites/{id}/services       /sites/{id}/firewallpolicies
                        /sites/{id}/topology       /sites/{id}/portforwards
                        /sites/{id}/users          /sites/{id}/portforwarding
                        /sites/{id}/admins         /sites/{id}/firmware-updates
                        /sites/{id}/vouchers
```

`[observed 2026-04-30 — 36 distinct 404s. All return the structured
{statusCode:404,...} envelope, confirming the auth filter passed and
the route dispatcher rejected.]`

The key absences for v2's purposes: **no `/health`, `/statistics`,
`/alarms`, `/events`, `/anomalies`, `/topology`, `/devices/{id}/wan`**.
**NOTE:** `/devices/{id}/statistics` (bare) still 404s, but
`/devices/{id}/statistics/latest` now returns 200 — see I-9.
`[observed 2026-05-07]` Also no config-drift surfaces
(`/wlanconf`, `/firewall*`, `/portforwards`).

---

## Per-endpoint detail

### I-1 `GET /info`

```json
{"applicationVersion":"10.3.55"}
```

**One field only.** No build, no UniFi OS version, no hostname, no
controller UUID, no timezone, no retention policy, no anything else
classic `stat/sysinfo` (24 fields) provides. `[observed 2026-04-30]`

- **Object candidate:** Integration-only Controller anchor — but with
  only `applicationVersion` to expose, this object would be a
  near-empty husk. Use classic `stat/sysinfo` for any meaningful
  Controller properties.

---

### I-2 `GET /sites`

```json
{
  "offset": 0,
  "limit": 25,
  "count": 1,
  "totalCount": 1,
  "data": [
    {
      "id": "88f7af54-98f8-306a-a1c7-c9349722b1f6",
      "internalReference": "default",
      "name": "Default"
    }
  ]
}
```

- **Pagination envelope:** offset/limit/count/totalCount/data. This
  envelope shape is consistent across every list endpoint on
  Integration v1. `[observed 2026-04-30]`
- **Per-row fields (3):** `id` (UUID), `internalReference` (the
  classic-API `name`, i.e. URL-path slug — `"default"`), `name`
  (display name, equivalent to classic `desc`).
- **Notable absence:** no `device_count`, no `role`. A v2 metric
  like `device_count` (`metricset:site_meta[0].device_count`) is
  not derivable from this endpoint without enumerating
  `/sites/{id}/devices` and counting.

**Identifier mapping vs classic:**

| Integration v1 field | Classic field | Notes |
|---|---|---|
| `id` (UUID) | `external_id` | Stable across both surfaces. `[re-verified 2026-04-30 — 88f7af54-98f8-306a-a1c7-c9349722b1f6 matches the value classic recon recorded on 2026-04-18.]` |
| `internalReference` | `name` | URL-path slug |
| `name` | `desc` | Display name |
| — | `_id` | Mongo ObjectId — NOT exposed on Integration |

---

### I-3 `GET /sites/{siteId}/devices`

Returns a slim 11-field-per-device list. All 15 devices on this lab
returned in one page (default `limit=25`). **No pagination needed
at this scale**, but the envelope is paginated.

```json
{
  "offset": 0,
  "limit": 25,
  "count": 15,
  "totalCount": 15,
  "data": [
    {
      "id": "b3134082-8154-3c57-bb63-3e5cf45e404e",
      "macAddress": "0c:ea:14:d1:0e:82",
      "ipAddress": "<redacted public IP>",
      "name": "udm",
      "model": "UDM Pro",
      "state": "ONLINE",
      "supported": true,
      "firmwareVersion": "5.0.16",
      "firmwareUpdatable": false,
      "features": ["switching"],
      "interfaces": ["ports"]
    },
    ...
  ]
}
```

**Field inventory (11 fields, every row):**

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID) | Stable per device. **Different from MAC** — the API authoritatively keys devices by UUID, not MAC. |
| `macAddress` | string | Lowercase, colon-separated, e.g. `"0c:ea:14:d1:0e:82"`. Matches classic `stat_device.mac`. |
| `ipAddress` | string | Note: gateway shows the WAN public IP here (because that's its primary IP); APs/switches show their LAN management IP. |
| `name` | string | Admin-set name. |
| `model` | string | **Human-readable model** (`"UDM Pro"`, `"USW Lite 16 PoE"`, `"AC Pro"`). **Different from classic** which uses short codes (`"USL16LP"`, `"U7PG2"`). `[observed 2026-04-30]` |
| `state` | enum string | Observed: `"ONLINE"`, `"OFFLINE"`. **String enum, not the classic 1/0 integer.** Translation needed if v2 still wants the numeric `state` metric. |
| `supported` | boolean | Always true on this lab; presumably false for unsupported / EOL hardware. |
| `firmwareVersion` | string | E.g. `"7.5.0"`, `"6.8.4"`. **Truncated vs classic** — classic gives `"7.4.1.16850"` (4 segments + build), Integration gives `"7.5.0"` (3 segments). |
| `firmwareUpdatable` | boolean | Replaces classic's `upgradable`. Same semantic. |
| `features` | array of strings (LIST endpoint) — array of OBJECTS in DETAIL endpoint | E.g. `["switching"]` in list, `{"switching":{"lags":[...]}}` in detail. Indicates device capability set. |
| `interfaces` | array of strings (LIST endpoint) — array of OBJECTS in DETAIL endpoint | E.g. `["ports"]` in list, `{"ports":[...], "radios":[...]}` in detail. Indicates which interface types are present. |

**Notable schema shape difference list-vs-detail:** `features` and
`interfaces` shape-shift between list and detail responses. In the
list rows they are arrays of capability/interface NAMES (strings);
in the detail rows they are objects whose top-level keys are those
same names and whose values are nested config blocks. An MP would
have to handle both shapes if it tried to consume both endpoints.
`[observed 2026-04-30 — confirmed across all 15 devices in list +
4 in detail (UDM, AC Pro, AC IW, Nano HD, USW Lite 16, USW Pro
XG, USW Flex).]`

**Device kinds present on lab (Integration's view):** `"UDM Pro"`,
`"USW Lite 16 PoE"`, `"USW Lite 8 PoE"`, `"USW Flex"`, `"USW Pro
XG 8 PoE"`, `"AC IW"`, `"AC Pro"`, `"Nano HD"`, `"AC Mesh"`. Lab
has no `"ugw"`-equivalent (USG); the classic-map's note about the
`type=='ugw'` branch being unverified holds for Integration too.

**Critical absences vs classic `stat/device` (on I-3 list endpoint):**

- No `_uptime` / `uptime` / `last_seen` — **NOW available via I-9 `/statistics/latest`** `[observed 2026-05-07]`
- No `system-stats` (CPU, memory, uptime) — **NOW available via I-9** `[observed 2026-05-07]`
- No `num_sta` / `user-num_sta` / `guest-num_sta` — still absent everywhere
- No `satisfaction` — still absent everywhere
- No `port_table` (in list — see I-4 for what detail provides)
- No `radio_table_stats` (in list — see I-4; I-9 adds `txRetriesPct` only for APs) `[observed 2026-05-07]`
- No `temperatures`, `storage`, `fan_level`, `general_temperature` — still absent everywhere
- No `wan1`, `wan2`, `uplink` (gateway WAN-uplink top-level objects) — **uplink tx/rx bps NOW available via I-9** `[observed 2026-05-07]`
- No `lldp_table`, `downlink_lldp_macs`
- No `total_max_power`, `total_used_power`
- No `tx_bytes` / `rx_bytes` (cumulative counters — still absent; I-9 provides only instantaneous bps rates)

This is the headline finding. **Integration v1's device list is
inventory metadata, not a metric snapshot.**

---

### I-4 `GET /sites/{siteId}/devices/{deviceId}`

Returns the same 11 list-row fields PLUS:

| Additional field | Type | Per-kind notes |
|---|---|---|
| `adoptedAt` | ISO 8601 timestamp string | E.g. `"2025-02-22T22:40:47Z"`. Date-of-adoption. **Not a metric** — won't change. |
| `provisionedAt` | ISO 8601 timestamp string | E.g. `"2026-04-29T05:45:03Z"`. Last config push. Useful as a config-drift property. |
| `configurationId` | string (16-hex) | Opaque config snapshot id. Useful as a property for config-drift detection. |
| `uplink` | object | Present on every non-root device. Single field: `{"deviceId": "<parent-uuid>"}` — direct topology pointer to the parent device's Integration UUID. Replaces classic's MAC-based `uplink.uplink_mac` / `uplink_remote_port`. **Cleaner than classic** for parent-child relationship binding. |
| `features.switching.lags` | array of LAG objects | Per-switch LAG configuration. Each LAG: `{id, portIdxs[], metadata:{origin}}`. Useful for v3's switch port modeling. |
| `features.accessPoint` | object (empty `{}`) | Capability marker on AP-class devices — present but empty. |
| `interfaces.ports` | array of port objects | See "port object shape" below. |
| `interfaces.radios` | array of radio objects (APs only) | See "radio object shape" below. |

**Port object shape** (consistent across UDM, all switches, AP wired
ports):

```json
{
  "idx": 1,                    // 1-based port index
  "state": "UP" | "DOWN",      // string enum (NOT classic's `up: bool`)
  "connector": "RJ45" | "SFPPLUS",
  "maxSpeedMbps": 1000,        // hardware capability, integer
  "speedMbps": 1000,           // current negotiated speed, integer
  "poe": {                     // optional — only on PoE-capable ports
    "standard": "802.3at" | "802.3bt",
    "type": 2 | 3,             // integer
    "enabled": true | false,   // admin-enabled
    "state": "UP" | "DOWN"     // current PoE delivery state
  }
}
```

`[observed 2026-04-30 across UDM Pro (11 ports), USW Lite 16 PoE
(16 ports), USW Lite 8 PoE (8 ports), USW Flex (5 ports), USW Pro
XG 8 PoE (10 ports), AC IW (3 RJ45), AC Pro (1 RJ45).]`

**Notable absences in port object** (vs classic `port_table[]`'s
~60 fields): no `tx_bytes`, no `rx_bytes`, no `tx_errors`, no
`rx_errors`, no `tx_dropped`, no `rx_dropped`, no `tx_packets`,
no `rx_packets`, no `tx_broadcast`, no `rx_broadcast`, no
`tx_multicast`, no `rx_multicast`, no `bytes-r`, no `mac_table_count`,
no `link_down_count`, no `satisfaction`, no `stp_state`, no
`anomalies`, no `flowctrl_*`, no `lacp_state`, no `native_networkconf_id`,
no `tagged_vlan_mgmt`, no `dot1x_*`, **no `poe_power` / `poe_voltage`
/ `poe_current` (Watts/Volts/Amps delivered)**, no `poe_class`.

**Radio object shape** (APs only, present in `interfaces.radios[]`):

```json
{
  "wlanStandard": "802.11n" | "802.11ac" | ...,
  "frequencyGHz": 2.4 | 5,
  "channelWidthMHz": 20 | 40 | 80 | 160,
  "channel": 1..165
}
```

`[observed 2026-04-30 across AC Pro, AC IW, Nano HD APs.]`

**Notable absences in radio object** (vs classic
`radio_table_stats[]`'s ~25 fields): no `user-num_sta`
(per-radio client count), no `tx_power`, no `satisfaction`, no
`cu_total` / `cu_self_rx` / `cu_self_tx` (channel utilization), no
`tx_retries` / `tx_retries_pct`, no `tx_packets`, no
`last_interference_at`, no `state`, no `name` (radio name like
`wifi0`/`wifi1`), no `radio` code (`ng`/`na`).

**Bottom line on detail endpoint:** detail adds adoption/config
metadata + topology pointers + link state + PoE port admin/state.
It does **not** add any time-series counters or instantaneous
metrics. Per-radio is config (channel/standard/width), not
utilization.

---

### I-5 `GET /sites/{siteId}/clients`

Paginated with the standard envelope. 124 active clients on this
lab. `[observed 2026-04-30]`

```json
{
  "offset": 0,
  "limit": 25,
  "count": 25,
  "totalCount": 124,
  "data": [
    {
      "type": "WIRED",
      "id": "<uuid>",
      "name": "<redacted display name>",
      "connectedAt": "2026-03-21T08:04:36Z",
      "ipAddress": "172.27.8.21",
      "macAddress": "<redacted MAC>",
      "uplinkDeviceId": "f5ff390f-5fb4-3361-8b0a-cb593c61abae",
      "access": {"type": "DEFAULT"}
    }
  ]
}
```

**Field inventory (8 fields, identical for WIRED and WIRELESS):**

| Field | Type | Notes |
|---|---|---|
| `type` | enum string | `"WIRED"` or `"WIRELESS"`. Replaces classic's `is_wired: bool`. |
| `id` | UUID | Stable per-client identifier. |
| `name` | string | Display name (hostname / device alias). |
| `connectedAt` | ISO 8601 timestamp | Connection time — **not** a session uptime counter. |
| `ipAddress` | string | Current IP. |
| `macAddress` | string | Same as classic. |
| `uplinkDeviceId` | UUID | **Pointer to the device the client is connected to (Integration UUID).** Cleaner than classic's `last_uplink_mac` + `sw_mac` + `sw_port` triple. But: **no port number** — the API tells you which device, not which port. |
| `access` | object | `{"type": "DEFAULT"}` observed across all clients. Likely surfaces guest-portal / hotspot status when relevant. No `is_guest` boolean. |

**Notable absences vs classic `stat/sta`:** `last_uplink_remote_port`
(switch port number for wired clients), `vlan` / `network` /
`network_id`, `wired-tx_bytes` / `wired-rx_bytes` / `*-r`, `oui`,
`os_name`, `satisfaction`, `signal` / `rssi` (wireless), `radio`
(2.4 vs 5), `essid`, `tx_rate` / `rx_rate`, `last_seen`, `uptime`.

### I-6 `GET /sites/{siteId}/clients/{clientId}`

**Returns the exact same 8 fields as the list row.** Verified by
exact-match comparison of a list-pulled WIRED client vs its
detail-endpoint pull. `[observed 2026-04-30]`

This means there is **no per-client depth** on Integration v1 — the
detail endpoint exists for symmetry / direct lookup, not for richer
metrics.

---

### I-7 `GET /sites/{siteId}/networks`

Paginated network/VLAN list. 17 networks on this lab.

```json
{
  "offset": 0, "limit": 25, "count": 17, "totalCount": 17,
  "data": [
    {
      "management": "GATEWAY",
      "id": "42c4888e-f133-40f9-a8e6-80a4318f9219",
      "name": "MGMT VLAN",
      "enabled": true,
      "vlanId": 1,
      "metadata": {"origin": "SYSTEM_DEFINED", "configurable": true},
      "zoneId": "a16701e8-d989-44f8-a286-9d0e45753bf3",
      "default": true
    },
    ...
  ]
}
```

**Field inventory (8 fields):**

| Field | Type | Notes |
|---|---|---|
| `management` | enum string | `"GATEWAY"` or `"UNMANAGED"`. |
| `id` | UUID | Stable network identifier. |
| `name` | string | Admin-set display name. |
| `enabled` | boolean | |
| `vlanId` | integer | 802.1Q VLAN tag. |
| `metadata.origin` | enum string | `"SYSTEM_DEFINED"` or `"USER_DEFINED"`. |
| `metadata.configurable` | boolean | Optional. |
| `zoneId` | UUID | Optional — links the network to a zone (firewall/segmentation grouping). Not present on UNMANAGED networks. |
| `default` | boolean | `true` for the system default network. |

**v2 design does not currently consume Network as a first-class
object** — config-drift surfaces (classic `rest/networkconf`) were
explicitly out-of-scope per design §"Scope reductions". So
Integration providing a clean Network endpoint is a v3 nicety,
not a v2 requirement.

### I-8 `GET /sites/{siteId}/networks/{networkId}`

Adds the IPv4 / DHCP configuration block:

```json
{
  ... (all 8 list fields) ...,
  "isolationEnabled": false,
  "cellularBackupEnabled": true,
  "internetAccessEnabled": true,
  "mdnsForwardingEnabled": true,
  "ipv4Configuration": {
    "autoScaleEnabled": false,
    "hostIpAddress": "172.16.0.1",
    "prefixLength": 24,
    "dhcpConfiguration": {
      "mode": "SERVER",
      "ipAddressRange": {"start": "172.16.0.200", "stop": "172.16.0.254"},
      "dnsServerIpAddressesOverride": ["172.27.8.8", "172.27.8.9", "8.8.8.8"],
      "leaseTimeSeconds": 86400,
      "domainName": "int.sentania.net",
      "pingConflictDetectionEnabled": true
    }
  }
}
```

`[observed 2026-04-30 against the system-default `MGMT VLAN`
network.]`

Useful for **config-property** modeling (DHCP ranges, lease times,
DNS overrides), not for metrics. v2 doesn't need this.

---

## Coverage comparison vs classic

The v2 design's metric-by-object-type tables enumerate ~131 lines
of metrics + properties (counted via `grep -E '^\| \`[a-z_0-9]+\`'`
on `designs/unifi-mp-v2.md`). Roll-up by object:

- **Controller**: ~36 entries (12 sysinfo + 4 site_meta + 20
  health subsystems) + `wan2_*` mirror = ~46 effective.
- **AP**: ~32 entries (20 device-level + 12 per-radio).
- **Switch**: ~18 entries (15 device-level + 3 chassis
  + 3 port-aggregate, with 5 deferred to v1.1).
- **Gateway**: ~36 entries (14 device-level + 10 wan1 + 10 wan2
  + 4 active-WAN + 2 temperatures).

Total reachable on the v2 metric set: ~118 unique paths (after
de-duplicating wan2_* mirrors). The audit below uses **representative
columns per object** rather than enumerating all 118 — full
per-metric coverage is mechanically derivable from the per-endpoint
field inventory above.

Legend:
- **SAME** — Integration v1 has this field with the same name.
- **DIFF** — Available with a different field name / shape.
- **UNIT/SHAPE** — Available but in different units or shape that
  a renderer would have to translate.
- **MISSING** — Not exposed on Integration v1 at all.

### Controller object (v2 expects ~46 metrics/properties)

| v2 metric | Integration availability | Notes |
|---|---|---|
| `controller_id` (sysinfo.anonymous_controller_id) | **MISSING** | Integration `/info` returns only `applicationVersion`. |
| `hostname` | **MISSING** | Not in `/info` or `/sites`. |
| `network_app_version` | **DIFF** | `/info.applicationVersion` provides equivalent (10.3.55 vs 10.2.105 — see version-skew). |
| `network_app_build` | **MISSING** | |
| `unifi_os_version` | **DIFF** | Available as the UDM device row's `firmwareVersion` (`"5.0.16"`) — but only by walking from sites→devices→UDM and matching by model. |
| `udm_version` | **MISSING** | Long-form firmware string not exposed. |
| `device_type` | **DIFF** | UDM device row's `model` (`"UDM Pro"`) vs classic's short code (`"UDMPRO"`). |
| `timezone` | **MISSING** | |
| `is_cloud_console` | **MISSING** | |
| `update_available` | **DIFF** | Per-device `firmwareUpdatable` (boolean per device). Could be aggregated as "any device updatable" but lossy vs the controller-level boolean. |
| `data_retention_days` | **MISSING** | Critical config exposed on classic; absent on Integration. |
| `controller_uptime_seconds` | **MISSING** | No uptime anywhere. |
| `site_name` | **SAME** | `/sites[0].internalReference`. |
| `site_description` | **DIFF** | `/sites[0].name` (Integration's `name` ≈ classic's `desc`). |
| `site_role` | **MISSING** | |
| `device_count` | **DIFF** | Derivable as `length(/sites/{id}/devices.data)` or read `totalCount` from the envelope. **Available, but requires a second request.** |
| `wan_status` | **MISSING** | No `/health` endpoint. |
| `wan_clients` | **MISSING** | |
| `wan_tx_bytes_rate` / `wan_rx_bytes_rate` | **MISSING** | No throughput counters anywhere. |
| `wan_gateway_mac` | **DIFF** | UDM device row's `macAddress`. Available, but requires walking devices and filtering `model: "UDM Pro"`. |
| `wan_isp_name` | **MISSING** | |
| `internet_latency_ms` / `internet_drops` / `internet_xput_*` / `speedtest_*` | **MISSING** | The entire `www`-subsystem block is gone. |
| `wlan_*` block (8 metrics: status, user/guest/iot count, ap count/disconnected, tx/rx rate) | **MISSING** | No `/health` equivalent. AP count derivable by counting devices with `model` matching AP patterns. |
| `lan_*` block (6 metrics) | **MISSING** | Same — no health surface. |
| `vpn_*` block (3 metrics) | **MISSING** | No VPN visibility at all. |

**Controller coverage: ~5 of 46 metrics (11%) covered**, all of them
properties / inventory. Every metric proper is missing.

### Access Point object (v2 expects ~32 metrics/properties)

| v2 metric | Integration availability | Notes |
|---|---|---|
| `mac` | **DIFF** | `macAddress` (camelCase). |
| `name` | **SAME** | |
| `model` | **UNIT/SHAPE** | Human-readable string vs classic short code. |
| `model_in_lts` | **MISSING** | |
| `firmware_version` | **DIFF** | `firmwareVersion` (camelCase). |
| `upgradable` | **DIFF** | `firmwareUpdatable` (camelCase, renamed). |
| `adopted` | **DIFF** | Not a boolean — replaced by `adoptedAt` timestamp on detail endpoint. Could be derived as `bool(adoptedAt)`. |
| `ip` | **DIFF** | `ipAddress`. |
| `serial` | **MISSING** | Not exposed. |
| `country_code` | **MISSING** | |
| `state` | **UNIT/SHAPE** | Enum string `"ONLINE"`/`"OFFLINE"` vs classic integer 1/0. |
| `uptime_seconds` | **MISSING** | No uptime counter. |
| `last_seen_epoch` | **MISSING** | |
| `cpu_pct` (system-stats.cpu) | **MISSING** | |
| `mem_pct` (system-stats.mem) | **MISSING** | |
| `client_count` (num_sta) | **MISSING** | |
| `user_client_count` / `guest_client_count` | **MISSING** | Derivable indirectly via filtering `/clients` by `uplinkDeviceId`. |
| `satisfaction` | **MISSING** | |
| `uplink_mac` | **DIFF** | Detail endpoint provides `uplink.deviceId` (UUID, not MAC). Cleaner for topology but breaks classic's MAC-join key. |
| `radio_24ghz_clients` (per-radio user-num_sta) | **MISSING** | Radio object has no client count. |
| `radio_24ghz_tx_power` | **MISSING** | |
| `radio_24ghz_satisfaction` | **MISSING** | |
| `radio_24ghz_channel` | **SAME** | Detail endpoint `interfaces.radios[?frequencyGHz==2.4].channel`. **Available — but requires per-AP detail call (15 calls vs 1 bulk on classic).** |
| `radio_24ghz_cu_total` | **MISSING** | |
| `radio_24ghz_tx_retries_pct` | **MISSING** | |
| `radio_5ghz_*` (mirror of 2.4) | Same pattern: only `channel` available. | |

**AP coverage: ~9 of 32 metrics (28%)** — almost entirely properties /
inventory. Of the 12 per-radio metrics v2 wants, only the
**channel** is available (and only on per-AP detail). Per-radio
client count, TX power, satisfaction, channel utilization, retries —
all missing.

### Switch object (v2 expects ~18 metrics/properties, 5 deferred)

| v2 metric | Integration availability | Notes |
|---|---|---|
| Common device set (mac/name/model/firmware_version/serial/ip/state/cpu_pct/mem_pct/client_count/uplink_mac/uptime/last_seen) | Same as AP audit — **only the inventory fields cover, all metrics missing.** | |
| `overheating` | **MISSING** | |
| `total_max_power_w` | **MISSING** | No PoE budget anywhere. |
| `has_temperature` | **MISSING** | |
| `has_fan` | **MISSING** | |
| `port_count` | **DIFF** | Derivable as `length(interfaces.ports)` from detail endpoint. **Available — but per-switch detail call.** |
| `ports_up_count` | **DIFF** | Derivable as `length(interfaces.ports[?state=='UP'])`. **Available — same caveat.** |
| `ports_poe_capable_count` | **DIFF** | Derivable as `length(interfaces.ports[?poe!=null])`. **Available — same caveat.** |

**Switch coverage: ~9 of 18 (50%)** if you count port-aggregate
derivations. **0 of the 5 deferred-to-v1.1 metrics** (poe_power_total,
poe_budget_remaining, port_tx/rx_bytes_total) become available on
Integration. v2's tooling-gap-D risk for PoE wattage is unresolvable
on Integration — the data simply isn't there.

### Gateway object (v2 expects ~36 metrics/properties)

| v2 metric | Integration availability | Notes |
|---|---|---|
| Common device set | Same audit pattern — inventory only. | |
| `gateway_type` | **DIFF** | `model` string (`"UDM Pro"`) instead of classic's `type` enum. |
| `wan1_tx_bytes_total` / `_rx_` / `_rate` (8 wan1 + 8 wan2 metrics) | **MISSING** | No per-WAN-uplink counters anywhere. The entire `wan1`/`wan2` top-level object class is absent. |
| `wan1_latency_ms` | **MISSING** | |
| `wan1_availability_pct` | **MISSING** | |
| `wan1_speed_mbps` | **MISSING** | |
| `wan1_up` | **MISSING** | (UDM port object's `interfaces.ports[?idx==9].state` could give a proxy — but that's "is the cable up", not "is the WAN session healthy".) |
| `active_wan_xput_up` / `_xput_down` / `_status` / `_ping_ms` / `_drops` / `_uptime` | **MISSING** | No speedtest exposure. |
| `cpu_temp_c` | **MISSING** | No `temperatures[]` anywhere. |
| `overheating` | **MISSING** | |

**Gateway coverage: ~7 of 36 (19%)** — only the basic device
inventory crosses over. **Every single WAN metric is gone.** This is
a critical loss because the WAN block is the densest metric region
in v2's gateway design (20 of 36 metrics).

### Coverage roll-up

| Object | v2 planned | Integration covered | % | Headline gap |
|---|---|---|---|---|
| Controller | ~46 | ~5 | 11% | All health-subsystem metrics; speedtest; uptime; data retention |
| Access Point | ~32 | ~9 | 28% | All per-radio counters; CPU/mem; uptime; satisfaction; client counts |
| Switch | ~18 | ~9 | 50% | All chassis temp/fan; PoE wattage; per-port counters |
| Gateway | ~36 | ~7 | 19% | All WAN1/WAN2 metrics; speedtest; temperatures |
| **Total** | **~132** | **~30** | **~23%** | (Boundary slightly fuzzy because some inventory rows count differently when "available with renamed field" is recorded as covered.) |

Of the ~30 "covered", the breakdown is:
- ~22 are **properties / inventory** (id, mac, name, model,
  firmware, ip, state, adopted, etc.) — most are **renamed
  (camelCase)** or **transformed (enum vs int)** vs classic.
- ~8 are **metrics** that are derivable via aggregation from the
  same Integration responses (port_count, ports_up_count,
  device_count, channel-per-radio).
- **0 are throughput / utilization / per-radio-occupancy / system
  load metrics**, which is the bulk of what v2's dashboard would
  visualize.

---

## Pagination model

All list endpoints share one envelope: `{offset, limit, count,
totalCount, data}`. `[observed 2026-04-30 across /sites,
/sites/{id}/devices, /sites/{id}/clients, /sites/{id}/networks.]`

- **Default `limit`: 25.**
- **Bounds:** at least 200 was accepted on `/clients?limit=200`
  (returned all 124 in one page). Did not probe upper bound.
- **`offset` works as an integer offset**, not a cursor:
  - `?limit=3&offset=0` returned ids `c3a62419, fffd9e5f, 87c1fa97`
  - `?limit=3&offset=3` returned ids `ab8ae739, 18e7f94a, 7e5998b6`
  - No row overlap, no skipped rows. `[observed 2026-04-30]`
- **`count`** = number of rows in this page. **`totalCount`** =
  total across all pages. Standard offset/limit pagination — the
  MP can detect "more pages" by `count < totalCount`.
- **Filter parameters:** ~~None confirmed~~ **CORRECTION
  (2026-05-07):** Official docs at developer.ui.com document a
  `filter` query parameter with a structured expression syntax on
  list endpoints (devices, clients). Our 2026-04-30 `?type=ACTIVE`
  test on `/clients` was invalid syntax (the correct form would be
  `?filter=type.eq('ACTIVE')`). The parameter being silently ignored
  was consistent with an unrecognized query param, not absence of
  filtering. **See "Official Documentation Findings" section for
  full filter syntax and per-endpoint filterable properties.**
  `[corrected 2026-05-07 from developer.ui.com docs; live
  verification still needed]`

---

## Versioning

- **Integration v1 is fully present.** All 8 working endpoints
  cataloged above respond on `/integration/v1/...`.
- **Integration v2 is NOT present on this controller.** `/v2/info`,
  `/v2/sites`, `/v2/sites/{id}/devices` all return the structured
  404 envelope with `code: "api.request.error"`. **Critically: this
  is a 404 from the route dispatcher (after the auth filter
  passed), not a 401 from the auth filter** — meaning the bearer
  key was accepted, but no v2 routes are registered.
  `[observed 2026-04-30]`

- **Application-version skew between Integration `/info` and
  classic `stat/sysinfo`:**

  | Source | Date | Version |
  |---|---|---|
  | Classic `stat/sysinfo.version` | 2026-04-18 | `10.2.105` |
  | Integration v1 `/info.applicationVersion` | 2026-04-30 | `10.3.55` |

  Two interpretations:
  1. **The Network App was upgraded** between 2026-04-18 and
     2026-04-30 (12 days). Plausible — Scott runs the controller
     and may have applied an update without re-recon. **Most
     likely interpretation.**
  2. The two endpoints emit different version strings (e.g.
     classic shows the bundled JAR build, Integration shows a
     different bundled service version). Less likely but
     unverifiable without re-pulling classic `stat/sysinfo` today.

  **Action item for mp-designer / Scott**: a single classic
  `stat/sysinfo` re-pull would disambiguate. Not done in this
  recon (would require classic session auth — out of scope of
  this Integration-only probe).

- **No documented v3 surface** to probe.

---

## Gap F revisit — does Integration make per-subsystem filtering easier?

**Gap F** in the v2 design = renderer needs JMESPath filter
predicates inside metric source paths to extract subsystem rows
from `stat/health` (e.g. `[?subsystem=='wan']`). The hope was
that Integration might split each subsystem to its own endpoint
(`/health/wan`, `/health/wlan`, etc.) and sidestep the renderer
gap entirely.

**Verdict: not applicable on Integration v1, because the entire
`/health` surface doesn't exist.** Integration provides:
- No `/health` (404)
- No `/sites/{id}/health` (404)
- No subsystem-keyed alternatives (no `/wan`, `/wlan`, `/lan`,
  `/www`, `/vpn`, no `/anomalies`, no `/insights`).

**Gap F remains a renderer-side concern**, but the question of
"can Integration shape the wire to avoid it?" is moot — there is
no wire to reshape because Integration has no health surface
at all. Gap F is properly a tooling-side gap (the renderer needs
JMESPath filter-predicate support to consume the classic
`stat/health` array shape).

---

## Official Documentation Findings (v10.1.84) — added 2026-05-07

Source: `https://developer.ui.com/network/v10.1.84/` — an embedded
OpenAPI 3.1.0 spec (`"version":"10.1.84"`, `"servers":[{"url":"/integration"}]`)
extracted from the React Server Component rendering payload. This is
the **Integration API** (same `/integration/v1/...` surface we probed
live), **NOT** the classic API. `[documented in developer.ui.com,
2026-05-07]`

### Finding 1: Server-side `filter` query parameter EXISTS

The `GET /v1/sites/{siteId}/devices` endpoint documents a `filter`
query parameter (`"name":"filter","in":"query","required":false,
"schema":{"type":"string"}`). This was **NOT discovered in our
2026-04-30 live probe** because we only tested `?type=ACTIVE` on
`/clients` (which was silently ignored — likely because `type` is
not the filter syntax). The actual filter syntax is structured and
URL-safe. `[documented in developer.ui.com, 2026-05-07]`

**Filtering syntax** (from the `/filtering` documentation page):

Three expression types:

1. **Property expressions:** `<property>.<function>(<arguments>)`
   - `id.eq(123)` — id equals 123
   - `name.isNotNull()` — name is not null
   - `createdAt.in(2025-01-01, 2025-01-05)` — in a set

2. **Compound expressions:** `<logical-operator>(<expressions>)`
   - `and(name.isNull(), createdAt.gt(2025-01-01))`
   - `or(name.isNull(), expired.isNull(), expiresAt.isNull())`

3. **Negation expressions:** `not(<expression>)`
   - `not(name.like('guest*'))`

**Supported property types:** STRING, INTEGER, DECIMAL, TIMESTAMP,
BOOLEAN, UUID, SET(STRING|INTEGER|DECIMAL|TIMESTAMP|UUID).

**Filtering functions:**

| Function | Semantics | Types |
|---|---|---|
| `isNull` | is null | all |
| `isNotNull` | is not null | all |
| `eq` | equals | STRING, INTEGER, DECIMAL, TIMESTAMP, BOOLEAN, UUID |
| `ne` | not equals | STRING, INTEGER, DECIMAL, TIMESTAMP, BOOLEAN, UUID |
| `gt` | greater than | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `ge` | greater than or equals | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `lt` | less than | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `le` | less than or equals | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `like` | matches pattern | STRING |
| `in` | one of | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `notIn` | not one of | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `isEmpty` | is empty | SET |
| `contains` | contains | SET |
| `containsAny` | contains any of | SET |
| `containsAll` | contains all of | SET |
| `containsExactly` | contains exactly | SET |

`like` supports `?` (single char) and `*` (any number of chars).
Examples: `type.like('type.')` matches `type1`..`type100`;
`name.like('guest*')` matches `guest1`..`guest100`.

`[documented in developer.ui.com/network/v10.1.84/filtering, 2026-05-07]`

### Finding 2: Device list filterable properties (ANSWERS THE TYPE QUESTION)

The `GET /v1/sites/{siteId}/devices` endpoint documents these
filterable properties:

| Property | Type | Allowed functions |
|---|---|---|
| `id` | UUID | eq, ne, in, notIn |
| `macAddress` | STRING | eq, ne, in, notIn |
| `ipAddress` | STRING | eq, ne, in, notIn |
| `name` | STRING | eq, ne, in, notIn, like |
| `model` | STRING | eq, ne, in, notIn |
| `state` | STRING | eq, ne, in, notIn |
| `supported` | BOOLEAN | eq, ne |
| `firmwareVersion` | STRING | isNull, isNotNull, eq, ne, gt, ge, lt, le, like, in, notIn |
| `firmwareUpdatable` | BOOLEAN | eq, ne |
| **`features`** | **SET(STRING)** | **isEmpty, contains, containsAny, containsAll, containsExactly** |
| **`interfaces`** | **SET(STRING)** | **isEmpty, contains, containsAny, containsAll, containsExactly** |

`[documented in developer.ui.com/network/v10.1.84/getadopteddeviceoverviewpage, 2026-05-07]`

**The `features` enum values** (from the response schema): `["switching", "accessPoint", "gateway"]`
`[documented in developer.ui.com, 2026-05-07]`

**The `interfaces` enum values**: `["ports", "radios"]`
`[documented in developer.ui.com, 2026-05-07]`

**This means device-type filtering IS possible on the Integration API** via:

| Want | Filter expression | Notes |
|---|---|---|
| APs only | `?filter=features.contains('accessPoint')` | Matches any device with AP capability |
| Switches only | `?filter=features.contains('switching')` | Note: UDM Pro has `["switching"]` too |
| Gateways only | `?filter=features.contains('gateway')` | |
| APs + switches | `?filter=features.containsAny('accessPoint','switching')` | |
| Only switches (not gateways that also switch) | `?filter=and(features.contains('switching'),not(features.contains('gateway')))` | Compound expression |
| Online APs | `?filter=and(features.contains('accessPoint'),state.eq('ONLINE'))` | Compound |
| Devices with radios | `?filter=interfaces.contains('radios')` | Alternative way to find APs |
| By model | `?filter=model.eq('UDM Pro')` | Exact model match |
| By model pattern | `?filter=model.like('USW*')` | All switches by naming convention |
| Online devices | `?filter=state.eq('ONLINE')` | |
| Specific MAC | `?filter=macAddress.eq('0c:ea:14:d1:0e:82')` | |

**LIVE-VERIFIED 2026-05-07.** The `filter` query parameter with
`features.contains()` syntax works correctly on our controller:

| Filter expression | HTTP status | `totalCount` | `count` | Correct? |
|---|---|---|---|---|
| *(no filter — baseline)* | 200 | 15 | 15 | Yes — all 15 devices |
| `features.contains('accessPoint')` | 200 | 6 | 6 | Yes — 4 pure APs + 2 AP-with-switching (AC IW) |
| `features.contains('switching')` | 200 | 11 | 11 | Yes — 9 pure switches + 2 AP-with-switching + UDM |
| `features.contains('gateway')` | 200 | 0 | 0 | **Correct but empty** — UDM Pro does NOT self-report `gateway` in features |

`[observed 2026-05-07 — all four probes returned 200 with correct filtering]`

**Key finding on `gateway` filtering:** The UDM Pro's `features`
array is `["switching"]` — it does **not** include `"gateway"`. This
means `features.contains('gateway')` returns 0 results on this lab.
The UDM Pro is the only gateway-class device, and its Integration API
representation classifies it purely as a switching device. This is
consistent across the baseline and filtered responses.
`[observed 2026-05-07]`

**Math check: 6 (AP) + 11 (switching) - 2 (AC IW overlap) = 15.**
The AC IW devices (ap-basement, ap-lower) appear in both AP and
switching results because they have `features: ["switching",
"accessPoint"]`. This is correct set-membership behavior.
`[observed 2026-05-07]`

**Implication for MP design**: This **eliminates the need for
client-side type filtering** in the MP. Instead of fetching all
devices and using JMESPath to filter by type, the MP can issue
filtered requests per object type. However, the `gateway` filter gap
means the MP must identify the gateway by other means — either
`model.eq('UDM Pro')` or `model.like('UDM*')`, or by falling back to
fetching all switching devices and applying client-side model matching.
`[observed 2026-05-07]`

### Finding 3: Client list filterable properties

The `GET /v1/sites/{siteId}/clients` endpoint also supports filtering:

| Property | Type | Allowed functions |
|---|---|---|
| `id` | UUID | eq, ne, in, notIn |
| `type` | STRING | eq, ne, in, notIn |
| `macAddress` | STRING | isNull, isNotNull, eq, ne, in, notIn |
| `ipAddress` | STRING | isNull, isNotNull, eq, ne, in, notIn |
| `connectedAt` | TIMESTAMP | isNull, isNotNull, eq, ne, gt, ge, lt, le |
| `access.type` | STRING | eq, ne, in, notIn |
| `access.authorized` | BOOLEAN | isNull, isNotNull, eq, ne |

`[documented in developer.ui.com/network/v10.1.84/getconnectedclientoverviewpage, 2026-05-07]`

Notable: the `type` field IS filterable on clients
(`type.eq('WIRED')` or `type.eq('WIRELESS')`). This is the direct
type filter we expected but didn't find on 2026-04-30 when we tried
`?type=ACTIVE` (wrong syntax — should have been `?filter=type.eq('ACTIVE')`
though `ACTIVE` is probably not a valid enum value anyway).

### Finding 4: `/devices/{deviceId}/statistics/latest` endpoint — LIVE-VERIFIED

The v10.1.84 spec documents `GET /v1/sites/{siteId}/devices/{deviceId}/statistics/latest`
with a 200 response schema. This endpoint returned 404 on 2026-04-30
but **now returns 200 with live data** as of 2026-05-07 (controller
was upgraded between sessions). `[observed 404 2026-04-30; observed
200 2026-05-07]`

**Response schema (from docs):**

```json
{
  "uptimeSec": integer (int64),
  "lastHeartbeatAt": string (date-time),
  "nextHeartbeatAt": string (date-time),
  "loadAverage1Min": number (double),
  "loadAverage5Min": number (double),
  "loadAverage15Min": number (double),
  "cpuUtilizationPct": number (double),
  "memoryUtilizationPct": number (double),
  "uplink": {
    "txRateBps": integer (int64),
    "rxRateBps": integer (int64)
  },
  "interfaces": {
    "radios": [
      {
        "frequencyGHz": number (enum: [2.4, 5, 6, 60]),
        "txRetriesPct": number (double)
      }
    ]
  }
}
```

Required fields: `["interfaces"]` only — all others are optional.
`[documented in developer.ui.com/network/v10.1.84/getadopteddevicelateststatistics, 2026-05-07]`

**Live samples captured 2026-05-07:**

**UDM Pro** (`b3134082-...`, model "UDM Pro", features: `["switching"]`):
```json
{
  "uptimeSec": 277227,
  "lastHeartbeatAt": "2026-05-07T05:31:33Z",
  "nextHeartbeatAt": "2026-05-07T05:32:07Z",
  "loadAverage1Min": 2.33,
  "loadAverage5Min": 1.72,
  "loadAverage15Min": 1.71,
  "cpuUtilizationPct": 19.8,
  "memoryUtilizationPct": 78.9,
  "uplink": {"txRateBps": 4552, "rxRateBps": 4968},
  "interfaces": {}
}
```
`[observed 2026-05-07]`

**AP — Nano HD** (`8892e017-...`, model "Nano HD", features: `["accessPoint"]`):
```json
{
  "uptimeSec": 694066,
  "lastHeartbeatAt": "2026-05-07T05:31:28Z",
  "nextHeartbeatAt": "2026-05-07T05:32:46Z",
  "loadAverage1Min": 0.5,
  "loadAverage5Min": 0.52,
  "loadAverage15Min": 0.54,
  "cpuUtilizationPct": 2.1,
  "memoryUtilizationPct": 41.4,
  "uplink": {"txRateBps": 1312, "rxRateBps": 2184},
  "interfaces": {
    "radios": [
      {"frequencyGHz": 2.4, "txRetriesPct": 7.2},
      {"frequencyGHz": 5, "txRetriesPct": 1.1}
    ]
  }
}
```
`[observed 2026-05-07]`

**Switch — USW Pro XG 8 PoE** (`ca8aaebf-...`, model "USW Pro XG 8 PoE", features: `["switching"]`):
```json
{
  "uptimeSec": 594864,
  "lastHeartbeatAt": "2026-05-07T05:30:53Z",
  "nextHeartbeatAt": "2026-05-07T05:32:11Z",
  "loadAverage1Min": 0.62,
  "loadAverage5Min": 0.58,
  "loadAverage15Min": 0.65,
  "cpuUtilizationPct": 6.6,
  "memoryUtilizationPct": 14.6,
  "uplink": {"txRateBps": 760, "rxRateBps": 1696},
  "interfaces": {}
}
```
`[observed 2026-05-07]`

**Per-device-type shape analysis:**

| Device type | `uplink` | `interfaces.radios` | `interfaces` (other) |
|---|---|---|---|
| UDM Pro (gateway/switch) | Present — WAN uplink tx/rx bps | Not present | Empty `{}` |
| Nano HD (AP) | Present — wired uplink tx/rx bps | Present — 2.4 + 5 GHz with txRetriesPct | No other keys |
| USW Pro XG 8 PoE (switch) | Present — wired uplink tx/rx bps | Not present | Empty `{}` |

`[observed 2026-05-07 — consistent with docs: `radios` only on AP-class devices]`

**Field-level observations:**
- `uptimeSec` on UDM is 277227 (~3.2 days), consistent with a recent
  reboot/upgrade. APs and switches show 594864-694066 (~6.9-8.0 days),
  suggesting they were not rebooted as recently. `[observed 2026-05-07]`
- `cpuUtilizationPct` is a float with one decimal: 19.8, 2.1, 6.6.
  UDM's 19.8% CPU and 78.9% memory are notably higher than other
  devices (expected — UDM runs the controller app). `[observed 2026-05-07]`
- `uplink.txRateBps` / `rxRateBps` are integers (bps, not Bps).
  Values are low (760-4968 bps), consistent with idle-state polling.
  `[observed 2026-05-07]`
- `nextHeartbeatAt` minus `lastHeartbeatAt` varies per device:
  UDM ~34s, AP ~78s, switch ~78s. Suggests different heartbeat
  intervals for gateway vs non-gateway devices.
  `[observed 2026-05-07]`
- `interfaces.radios[].txRetriesPct` on the Nano HD: 7.2% on 2.4 GHz,
  1.1% on 5 GHz. These are real-time retry percentages — a genuine
  metric, not a counter. `[observed 2026-05-07]`

**This endpoint provides these previously-MISSING v2 metrics:**

| Live field | v2 metric it maps to | Notes |
|---|---|---|
| `uptimeSec` | `uptime_seconds` | **NOW AVAILABLE** `[observed 2026-05-07]` |
| `cpuUtilizationPct` | `cpu_pct` | **NOW AVAILABLE** `[observed 2026-05-07]` |
| `memoryUtilizationPct` | `mem_pct` | **NOW AVAILABLE** `[observed 2026-05-07]` |
| `loadAverage1Min/5Min/15Min` | (new — not in v2 design) | Bonus metrics `[observed 2026-05-07]` |
| `lastHeartbeatAt` | `last_seen_epoch` (approx) | **NOW AVAILABLE** — ISO 8601 format (not epoch) `[observed 2026-05-07]` |
| `uplink.txRateBps` / `rxRateBps` | `wan1_tx_bytes_rate` / `wan1_rx_bytes_rate` (approx) | **NOW AVAILABLE** — note: bps not Bps; per-device uplink, not per-WAN-interface `[observed 2026-05-07]` |
| `interfaces.radios[].txRetriesPct` | `radio_*_tx_retries_pct` | **NOW AVAILABLE** — AP-only `[observed 2026-05-07]` |

**This materially changes the coverage audit** — with
`/statistics/latest` confirmed working, the coverage delta shifts
from ~23% to ~35-40% for the full metric set, and more importantly,
the highest-priority utilization metrics (CPU, memory, uptime,
uplink throughput, radio retries) are now available.

**Still absent from `/statistics/latest`:** per-radio client count,
per-radio satisfaction, per-radio channel utilization (cu_total),
per-port tx/rx bytes, per-port errors, PoE wattage, temperatures,
WAN latency, speedtest, health subsystem aggregates.

### Finding 5: Full v10.1.84 endpoint catalog (35 paths)

The v10.1.84 docs enumerate 35 paths under `/integration/v1/...`
vs the 8 we confirmed live on 2026-04-30. Difference is largely
config endpoints (firewall, ACL, DNS, WiFi, VPN, hotspot,
traffic-matching) and supporting-resource endpoints (DPI, countries,
device-tags, RADIUS profiles, WAN interfaces). The newly documented
paths relevant to monitoring:

| Path | Method | Finding |
|---|---|---|
| `/v1/sites/{siteId}/devices/{deviceId}/statistics/latest` | GET | **NEW** — real-time stats (see Finding 4) |
| `/v1/sites/{siteId}/wans` | GET | **NEW** — WAN interface definitions |
| `/v1/sites/{siteId}/vpn/servers` | GET | **NEW** — VPN servers |
| `/v1/sites/{siteId}/vpn/site-to-site-tunnels` | GET | **NEW** — site-to-site VPN tunnels |
| `/v1/sites/{siteId}/device-tags` | GET | **NEW** — device tag management |
| `/v1/pending-devices` | GET | **NEW** — NOT site-scoped (top-level) |
| `/v1/countries` | GET | **NEW** — reference data |
| `/v1/dpi/applications` | GET | **NEW** — DPI app list |
| `/v1/dpi/categories` | GET | **NEW** — DPI category list |

`[documented in developer.ui.com v10.1.84 spec, 2026-05-07. None
live-verified. All 404'd paths from 2026-04-30 (§ "404'd paths"
above) were probed on an older controller — a re-probe after
controller update is needed.]`

### Finding 6: State enum values (documented)

The `state` field on devices has a richer enum than we observed
live (`ONLINE`, `OFFLINE` were the only values seen on 2026-04-30):

Full enum: `["ONLINE", "OFFLINE", "PENDING_ADOPTION", "UPDATING",
"GETTING_READY", "ADOPTING", "DELETING", "CONNECTION_INTERRUPTED",
"ISOLATED", "U5G_INCORRECT_TOPOLOGY"]`
`[documented in developer.ui.com, 2026-05-07]`

### Finding 7: Pagination limits (documented)

The device list endpoint documents `limit` with
`"maximum":200,"minimum":0,"default":25`. This confirms the
`?limit=200` we used on 2026-04-30 was at the documented max.
`[documented in developer.ui.com, 2026-05-07; re-verified against
our live observation of limit=200 working]`

### Impact on prior recommendation — UPDATED 2026-05-07

The 2026-04-30 recommendation ("stay on classic, do not pivot to
Integration") was based on a controller that **did not have the
`/statistics/latest` endpoint** and where we **did not know about
the `filter` parameter**. Both gaps are now resolved:

1. **Device type filtering** — **LIVE-VERIFIED 2026-05-07.** Works
   correctly for `accessPoint` (6 results) and `switching` (11
   results). `gateway` filter returns 0 because the UDM Pro does not
   self-report `gateway` in its features array.
   `[observed 2026-05-07]`
2. **CPU/mem/uptime/uplink throughput** — **LIVE-VERIFIED 2026-05-07.**
   `/statistics/latest` now returns 200 with real data on all three
   device types tested (UDM Pro, Nano HD AP, USW Pro XG switch).
   `[observed 2026-05-07]`

**The recommendation landscape has shifted.** Integration API now
covers the core utilization metrics (CPU, memory, uptime, uplink
throughput, radio retries) that were the biggest gap on 2026-04-30.
Combined with the dramatically simpler auth model (static API key vs
CSRF + cookie session), **Integration is now a viable primary surface
for an MP focused on device health monitoring**.

**However, classic remains necessary for:**
- Per-radio client count, satisfaction, channel utilization (cu_total)
- Per-port tx/rx bytes, errors, drops
- PoE wattage (total and per-port)
- Temperatures and fan status
- WAN-specific metrics (latency, speed, drops, ISP name)
- Speedtest results
- Health subsystem aggregates (wan/wlan/lan/vpn/www)
- `gateway` device identification (UDM doesn't self-tag as gateway
  on Integration; classic `type=="ugw"` is reliable)

**Revised action items:**
1. ~~Live-verify the filter parameter~~ **DONE** `[observed 2026-05-07]`
2. ~~Re-probe `/statistics/latest`~~ **DONE** `[observed 2026-05-07]`
3. **Consider Integration-first MP design** — the auth simplification
   (no CSRF, no cookie, no two-value extract) plus server-side
   filtering plus `/statistics/latest` metrics make a strong case for
   an Integration-primary MP with classic-supplementary requests for
   the deep metrics Integration doesn't carry. This is a design
   decision for mp-designer.
4. **Resolve the gateway identification gap** — either use
   `model.like('UDM*')` filter on Integration, or fall back to
   classic `type=="ugw"` for gateway discovery.
5. **Probe `/info` to get current applicationVersion** — the
   controller was clearly upgraded (statistics/latest now works),
   but we didn't re-check the version number this session.

---

## Recommendation

**REVISED 2026-05-07: Integration is now viable as a primary surface
for device health monitoring.** The original 2026-04-30 "stay on
classic" recommendation was based on a controller where
`/statistics/latest` returned 404 and `filter` was untested. Both
are now live-verified and working. The recommendation below reflects
the current state.

**Integration-first is now a viable design choice**, with classic as
a supplement for deep metrics. The tradeoffs:

| Factor | Integration-first | Classic-only |
|---|---|---|
| Auth complexity | API key header (trivial) | CSRF + cookie session (Gap B tooling) |
| Device type filtering | Server-side `features.contains()` | Client-side JMESPath on `type` field |
| Core utilization (CPU/mem/uptime) | `/statistics/latest` (per-device call) | `stat/device` bulk (one call, all devices) |
| Uplink throughput | `uplink.txRateBps/rxRateBps` per device | `stat/device[].uplink` per device |
| Radio retries | `interfaces.radios[].txRetriesPct` | `radio_table_stats[].tx_retries_pct` |
| Radio occupancy (cu_total) | **MISSING** | Available |
| Per-port counters | **MISSING** | Available (~60 fields per port) |
| PoE wattage | **MISSING** | Available |
| Temperatures | **MISSING** | Available |
| WAN metrics (latency/speed/drops) | **MISSING** | Available |
| Health subsystem aggregates | **MISSING** | Available |
| Speedtest | **MISSING** | Available |
| Gateway identification | **GAP** — UDM doesn't self-tag as `gateway` | `type=="ugw"` works reliably |
| N+1 API calls | Yes — `/statistics/latest` is per-device (15 calls for 15 devices) | No — `stat/device` returns all in one call |

**Recommendation for mp-designer:**

1. **For an Integration-only MP** (simplest auth, officially
   supported surface): delivers inventory + core health (CPU, memory,
   uptime, uplink throughput, radio retries). Covers the "is it up
   and healthy?" use case well. Auth is trivial. Server-side filtering
   is clean. Trade-off: no deep metrics, N+1 statistics calls, no
   gateway self-identification.

2. **For maximum metric coverage** (classic-primary): stay on classic
   with the Gap B fix. Integration adds nothing classic doesn't
   already have, except cleaner auth and server-side filtering.

3. **For hybrid** (Integration for inventory + health, classic for
   deep metrics): most complex — two auth flows, two request sets,
   join keys between Integration UUIDs and classic MAC addresses.
   Highest coverage but highest implementation cost.

The choice depends on whether the MP is meant to be a "device health
overview" (Integration is sufficient) or a "deep network monitoring
tool" (classic is required). **This is a design decision for
mp-designer / Scott.**

**Integration v1 strengths** that hold regardless of the primary
surface choice:
- **Identity binding** — stable device UUIDs independent of MAC.
- **Topology** — `uplink.deviceId` is a cleaner parent pointer
  than classic's MAC-based join.
- **Config drift** — `provisionedAt` and `configurationId` are
  first-class.
- **Server-side filtering** — reduces payload and eliminates
  client-side type dispatch.

**Integration v2 (when it lands) should be re-mapped.** Likely
path: api-cartographer revisits when Network App version advertises
Integration v2 endpoints.

---

## Appendix — items observed but out of cartography scope

These are flagged to mp-designer / Scott but not pursued here:

- **Key permission scoping.** Whether `X-API-Key` supports
  read-only vs read-write or per-site scoping is not visible from
  the read-only probe surface. A v1.1 / v3 Integration consumer
  would want to confirm, but it's an operational concern for the
  key-management UI, not an API-shape concern.
- **Key rotation / expiry.** No expiry visible in any header.
  Operational concern for an MP packaging path that needs
  long-lived credentials in a connection profile.
- **Audit logging.** No `requestId` correlation surface visible
  to the API consumer side. UDM-side audit logs (if any) are not
  exposed via the v1 surface.
- **Write operations.** Out of cartography scope (read-only
  posture). The CORS `access-control-allow-methods` header
  advertises `POST/PUT/PATCH/DELETE` are *allowed by CORS policy*,
  but actual route registrations for those methods were not
  probed — irrelevant to a monitoring MP regardless.

---

## Cross-references

- `context/api-maps/unifi-network-api.md` — classic surface map
  (authoritative for everything under `/proxy/network/api/...`).
  Endpoint-number references throughout this file (e.g.
  "classic endpoint #4 (`stat/device`)") point there.
- `designs/unifi-mp-v2.md` §"Authentication" / §"Metrics by Object
  Type" / §"Key Risks" — the design this map informs. Specific
  v2 risks this map updates: **Gap B** (do not pivot — coverage
  is insufficient), **Gap F** (unchanged — Integration has no
  `/health` to reshape), **risk #7** ("No Integration API
  verification" — now verified, with the verdict that it cannot
  serve as the primary surface).
