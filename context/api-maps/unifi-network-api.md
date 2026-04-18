# UniFi Network API Map (Classic Controller Surface)

## Session metadata

- **Controller URL**: `https://unifi.int.sentania.net`
- **Hardware**: UDM Pro (`UDMPRO`)
- **UniFi OS / udm_version**: `5.0.16.30692`
  (surface at `stat/sysinfo.udm_version` and
  `stat/sysinfo.console_display_version = "5.0.16"`)
- **Network Application version**: `10.2.105` (`stat/sysinfo.version`)
  and `build = atag_10.2.105_33556`
- **Previous Network App version**: `10.1.89`
  (`stat/sysinfo.previous_version`)
- **Recon date**: 2026-04-18 (live probes) + 2026-04-17 cached dumps
  from `/tmp/unifi-recon/net-*.json` reused where endpoint data is
  stable between days.
- **Auth method used for recon**: classic session
  (`POST /api/auth/login` → `TOKEN` cookie + `x-csrf-token` header).
  GET-only, per orchestrator brief.
- **Total endpoints probed live**: 25
  (7 primary + 17 event-path-discovery probes + 1 Protect scoping)
- **Files sanitized**: response samples in this map redact WAN public
  IPs, ISP details, and camera MACs where relevant. Raw JSON remains
  in `/tmp/unifi-recon/` (not committed).

### Why Network App version ambiguity resolved

Briefing §5 flagged Navani's "5.0.16" as probably a conflation.
**Direction of the flag was right; the specifics were not.**

- **`5.0.16` is the UniFi OS / console display version** — shown in
  the UniFi OS appliance UI as "Console 5.0.16" and emitted by
  `stat/sysinfo.console_display_version` and
  `stat/sysinfo.udm_version = "UDMPRO.al324.v5.0.16.238fde6.260227.0037"`.
  It is NOT the Network App version.
- **`10.2.105` is the Network Application version** — emitted by
  `stat/sysinfo.version` and `stat/sysinfo.build = atag_10.2.105_33556`.
  This is what Khriss expected based on release cadence (current
  stable is 10.3.55 per briefing, and 10.2.105 is one minor behind).
- **Implication for auth decision**: 10.2.105 > 9.3.43, so the
  Official Network Integration API is available. Confirmed by live
  probe — see "Integration API probe" below.

Navani's "Network app 5.0.16 on UniFi OS 5.0.16" was the conflation
the briefing suspected. The correct phrasing for any public / Explore
talk is: "UniFi OS 5.0.16 running Network Application 10.2.105."

---

## Auth flow

### Classic session (used for this recon)

```
POST https://{host}/api/auth/login
Content-Type: application/json
Body: {"username": "<user>", "password": "<pw>", "rememberMe": false}

Response 200:
  Set-Cookie: TOKEN=<JWT>; ...
  x-csrf-token: <36-char token>
```

Every subsequent call sends the `TOKEN` cookie (HTTP stack handles
automatically) and `x-csrf-token: <token>` as a request header.

**CSRF rotation on GETs — CONFIRMED does NOT rotate.** None of the 7
primary GET probes returned an `X-Updated-CSRF-Token` response
header; the initial CSRF from login remained valid across every GET
in the session. The `Access-Control-Expose-Headers` response header
*lists* `X-Updated-Csrf-Token` as an exposable header (so the UI
knows to look for it), but the header is not emitted on GETs —
matching the briefing's §5 claim and supplement §10.

**Implication for MP design**: the briefing's read-only-MP-compatible-
with-MPB claim holds. An MP that only issues GETs against the
classic surface can use MPB session auth method 3 or 5 with a single
CSRF token captured at login.

### Integration API (not exercised — key not yet generated)

```
GET https://{host}/proxy/network/integration/v1/info
X-API-Key: <token>
```

Probed without the key to verify the surface exists on this
controller — see Integration API Probe section below.

---

## URL layout (mirroring Navani's recon)

| Layer | Base path | Notes |
|-------|-----------|-------|
| UniFi OS | `/api/...` | console-level (auth, users, system) |
| Network app (classic) | `/proxy/network/api/...` | site-scoped data and config |
| Network app (integration v1) | `/proxy/network/integration/v1/...` | official X-API-Key surface; requires Network App v9.3.43+ |
| Protect app | `/proxy/protect/api/...` | NVR + cameras (v1.1 scope) |

Site-scoped classic paths:
`/proxy/network/api/s/{site}/<area>/<resource>` where `<area>` is
`stat` (read), `rest` (CRUD on config), `cmd` (imperative, POST).

---

## Endpoint catalog

All endpoints below were exercised live against
`unifi.int.sentania.net` as the `claude` service account. Envelope
is `{"meta": {"rc": "ok"|"error"}, "data": [...]}` unless noted.

### 1. `GET /proxy/network/api/s/default/stat/sysinfo`

- **Auth**: session cookie + `x-csrf-token`
- **Response envelope**: `{meta:{rc:"ok"}, data:[{...}]}` — single-
  element array, not a top-level object.
- **Response bytes**: ~1.5 KB

```json
{
  "meta": {"rc": "ok"},
  "data": [{
    "timezone": "America/Chicago",
    "autobackup": false,
    "build": "atag_10.2.105_33556",
    "version": "10.2.105",
    "previous_version": "10.1.89",
    "update_available": false,
    "update_downloaded": false,
    "hostname": "udm",
    "name": "udm",
    "inform_port": 8080,
    "https_port": 8443,
    "portal_http_port": 8880,
    "uptime": 503712,
    "anonymous_controller_id": "<redacted UUID>",
    "ubnt_device_type": "UDMPRO",
    "udm_version": "UDMPRO.al324.v5.0.16.238fde6.260227.0037",
    "console_display_version": "5.0.16",
    "is_cloud_console": false,
    "data_retention_days": 90,
    "data_retention_time_in_hours_for_5minutes_scale": 24,
    "data_retention_time_in_hours_for_hourly_scale": 168
  }]
}
```

- **Object candidates**: UniFi Site (this is the per-site controller
  info — retention policy + version).
- **Properties (not metrics)**: `version`, `build`, `udm_version`,
  `console_display_version`, `hostname`, `timezone`,
  `is_cloud_console`, `update_available`, `update_downloaded`,
  `data_retention_days`, `ubnt_device_type`.
- **Metric candidates**: `uptime` (seconds since controller boot).

### 2. `GET /proxy/network/api/self/sites`

- **Response envelope**: `{meta:{rc:"ok"}, data:[{...},...]}`
- **Response bytes**: ~300 B, 1 site ("default")

```json
{
  "meta": {"rc": "ok"},
  "data": [{
    "_id": "67ba522dda21a4461c2db3f8",
    "name": "default",
    "desc": "Default",
    "external_id": "88f7af54-98f8-306a-a1c7-c9349722b1f6",
    "anonymous_id": "<redacted UUID>",
    "attr_no_delete": true,
    "attr_hidden_id": "default",
    "role": "admin",
    "role_hotspot": false,
    "device_count": 15
  }]
}
```

- **Object candidates**: UniFi Site (root object).
- **Identifier**: `name` is the site URL-path identifier (literally
  `"default"` here); `_id` is the Mongo object id; `desc` is the
  display name.
- **Site count on this controller**: 1.
- **Device count per site property** (`device_count: 15`) confirms
  the device inventory total observed in `stat/device` (8 USW +
  6 UAP + 1 UDM = 15). **Briefing said 13 devices (6 switches +
  6 APs + 1 UDM). Lab actually has 8 switches — briefing drifted.**
- **Properties**: `name`, `desc`, `role`, `device_count`.

### 3. `GET /proxy/network/api/s/default/stat/health`

- **Response envelope**: `{meta:{rc:"ok"}, data:[{...},...]}` — array
  of 5 subsystem rows: `wlan`, `wan`, `www`, `lan`, `vpn`.
- **Response bytes**: ~2.4 KB

```json
{
  "meta": {"rc": "ok"},
  "data": [
    {
      "subsystem": "wlan",
      "status": "ok",
      "num_user": 21,
      "num_guest": 0,
      "num_iot": 1,
      "tx_bytes-r": 62600,
      "rx_bytes-r": 9173,
      "num_ap": 6,
      "num_adopted": 6,
      "num_disabled": 0,
      "num_disconnected": 0,
      "num_pending": 0
    },
    {
      "subsystem": "wan",
      "status": "ok",
      "num_gw": 1,
      "num_adopted": 1,
      "num_disconnected": 0,
      "num_pending": 0,
      "wan_ip": "<redacted public IP>",
      "gateways": [],
      "netmask": "<redacted>",
      "nameservers": [],
      "num_sta": 128,
      "tx_bytes-r": 16164,
      "rx_bytes-r": 3344,
      "gw_mac": "0c:ea:14:d1:0e:82",
      "gw_name": "udm",
      "gw_system-stats": {"cpu": "26.6", "mem": "75.7", "uptime": "503819"},
      "gw_version": "5.0.16.30692",
      "isp_name": "<redacted ISP>",
      "isp_organization": "<redacted>",
      "asn": 0,
      "uptime_stats": {"WAN": {...}, "WAN2": {...}}
    },
    {
      "subsystem": "www",
      "status": "ok",
      "tx_bytes-r": 16164,
      "rx_bytes-r": 3344,
      "latency": 5,
      "uptime": 929,
      "drops": 12,
      "xput_up": 0.0,
      "xput_down": 0.0,
      "speedtest_status": "Error",
      "speedtest_lastrun": 1776507641,
      "speedtest_ping": 0,
      "gw_mac": "0c:ea:14:d1:0e:82"
    },
    {
      "subsystem": "lan",
      "status": "error",
      "lan_ip": null,
      "num_user": 107,
      "num_guest": 0,
      "num_iot": 1,
      "tx_bytes-r": 918,
      "rx_bytes-r": 20952,
      "num_sw": 10,
      "num_adopted": 11,
      "num_disconnected": 1,
      "num_pending": 0
    },
    {
      "subsystem": "vpn",
      "status": "ok",
      "remote_user_enabled": true,
      "remote_user_num_active": 0,
      "remote_user_num_inactive": 0,
      "remote_user_rx_bytes": 0,
      "remote_user_tx_bytes": 0,
      "remote_user_rx_packets": 0,
      "remote_user_tx_packets": 0,
      "site_to_site_enabled": false
    }
  ]
}
```

- **Object candidates**: UniFi Site (5 subsystem rows provide site-
  level aggregate metrics). Wireless Client Aggregate candidate
  sources from the `wlan` row.
- **Response shape is an ARRAY OF OBJECTS** keyed by `subsystem`
  string — NOT a dict keyed by subsystem name. Design's JMESPath
  `data[?subsystem=='wan']` matches this exactly. See Renderer-gap
  findings #1 below.
- **Byte-rate field naming: hyphen not underscore.** Design YAML
  references `rx_bytes_r` / `tx_bytes_r` in the Site metrics table;
  live response uses `rx_bytes-r` / `tx_bytes-r`. Every object-ish
  `subsystem` row that reports throughput uses the hyphen form.
- **Subsystem row schemas are heterogeneous** — each subsystem has
  different keys. The full key list per subsystem:
  - `wlan` (12): num_user, num_guest, num_iot, tx_bytes-r,
    rx_bytes-r, status, num_ap, num_adopted, num_disabled,
    num_disconnected, num_pending, subsystem.
  - `wan` (21): status, gw_mac, gw_name, gw_system-stats,
    gw_version, wan_ip, gateways, netmask, nameservers, num_gw,
    num_adopted, num_disconnected, num_pending, num_sta,
    tx_bytes-r, rx_bytes-r, asn, isp_name, isp_organization,
    uptime_stats, subsystem.
  - `www` (13): status, tx_bytes-r, rx_bytes-r, latency, uptime,
    drops, xput_up, xput_down, speedtest_status, speedtest_lastrun,
    speedtest_ping, gw_mac, subsystem.
  - `lan` (12): status, lan_ip, num_user, num_guest, num_iot,
    tx_bytes-r, rx_bytes-r, num_sw, num_adopted, num_disconnected,
    num_pending, subsystem.
  - `vpn` (10): status, remote_user_enabled, remote_user_num_active,
    remote_user_num_inactive, remote_user_rx_bytes,
    remote_user_tx_bytes, remote_user_rx_packets,
    remote_user_tx_packets, site_to_site_enabled, subsystem.

### 4. `GET /proxy/network/api/s/default/stat/device`

- **Response envelope**: `{meta:{rc:"ok"}, data:[{...},...]}` — one
  row per device. All 15 devices returned in one payload.
- **Response bytes**: ~385 KB. **The firehose.**
- **Not re-pulled live today** — the 2026-04-17 cached dump in
  `/tmp/unifi-recon/net-device.json` is reused for this map. The
  `/stat/device` schema is stable across minor Network App revisions
  per briefing §5 — any drift between the cached data and today's
  reality is in counter values, not field shape.

**Device type breakdown (on this controller):**

| `type` | Count | Model(s) | Notes |
|--------|-------|----------|-------|
| `uap` | 6 | U7PG2, U7IW, U7NHD, U7MSH | Access Points |
| `usw` | 8 | USL16LP, USL8LP, USF5P, USWED76 | Switches (briefing said 6; actual is 8) |
| `udm` | 1 | UDMPRO | Combined gateway/controller/NVR |

**Design assumed gateway `type` values**: `ugw` (USG) or `udm`
(Dream Machines). This lab has only `type=udm` — `ugw` was not
exercised live. Briefing §3 gateway predicate
`list_path: "data[?type=='ugw' || type=='udm']"` is correct in
shape; only `udm` branch can be verified on this lab.

#### Device-level field verification (common across all 3 types)

Checked against an AP (`ap-livingroom`), Switch (`usw-lite-16-nuc`),
and UDM (`udm`).

| Design-proposed path | Live-observed | Match? | Notes |
|----------------------|---------------|--------|-------|
| `stat_device.state` | `state` (integer, 1=connected, 0=disconnected) | YES | Observed `state=1` on all adopted devices. |
| `stat_device._uptime` | `_uptime` (seconds, int) | YES | Underscore-prefixed variant. `uptime` (no underscore) also exists, observed to be identical in value. |
| `stat_device.upgradable` | `upgradable` (boolean) | YES | No current devices have upgrades pending, so all observed as `false`. |
| `stat_device.upgrade_to_firmware` | MISSING | **DRIFT** | Field only present when `upgradable: true`. Zero upgradable devices in this lab => zero devices with this field. MP must not rely on the field always being present. |
| `stat_device.system-stats.cpu` | `system-stats.cpu` (string-or-number) | YES-BUT | AP returns number (`4.9`); UDM returns STRING (`"23.8"`). Renderer must coerce. |
| `stat_device.system-stats.mem` | `system-stats.mem` | YES-BUT | Same string/number drift. UDM: `"75.1"`, AP: `44.2`. |
| `stat_device.last_seen` | `last_seen` (epoch seconds) | YES | |
| `stat_device.type` | `type` | YES | Values confirmed: `uap`, `usw`, `udm`. |
| `stat_device.model` | `model` | YES | |
| `stat_device.mac` | `mac` | YES | |
| `stat_device.name` | `name` | YES | Some devices may have blank `name`; none observed here. |
| `stat_device.adopted` | `adopted` (boolean) | YES | |
| `stat_device.version` | `version` | YES | e.g. AP `6.8.4.15604`, USW `7.4.1.16850`, UDM `5.0.16.30692`. |
| `stat_device.ip` | `ip` | YES | |
| `stat_device.uplink.uplink_mac` | `uplink.uplink_mac` | YES | Present on all non-root devices. |
| `stat_device.uplink.uplink_remote_port` | `uplink.uplink_remote_port` | YES | Number, not string. |
| `stat_device.model_in_lts` | `model_in_lts` | YES | Boolean. |

**Topology observation**: on this lab, `ap-lower` has
`uplink.uplink_mac` pointing to `ap-basement` (another AP, in mesh-
bridge mode). v1.1's proposed AP → Switch relationship via
`uplink_mac` / `mac` join needs to tolerate AP-parented APs and
daisy-chained switches, not assume the parent is always a switch.

#### Access Point — per-radio nested fields

Live shape sampled from `ap-livingroom` (`type=uap`, model `U7PG2`,
2 radios).

| Design-proposed path | Live-observed | Match? | Notes |
|----------------------|---------------|--------|-------|
| `radio_table[].channel` | `radio_table[].channel` | YES | Integer. |
| `radio_table[].tx_power` | **Not in `radio_table`** — present in `radio_table_stats[].tx_power` | DRIFT | Per-radio TX power is in the STATS table, not the CONFIG table. `radio_table[]` has `tx_power_mode` (e.g. `"auto"`) and `max_txpower`/`min_txpower` bounds, but no current `tx_power`. |
| `radio_table_stats[].user-num_sta` | `radio_table_stats[].user-num_sta` | YES | Integer. Hyphen between `user` and `num_sta`. Design's hyphen form is correct. |
| `radio_table_stats[].tx-bytes` | **MISSING** | **DRIFT** | Not in `radio_table_stats[]` at all. Per-radio bytes live in the device-level `stat.ap.{wifi0,wifi1}-tx_bytes` / `-rx_bytes` scalar keys (hyphen-separated, prefixed by radio NAME not radio CODE). |
| `radio_table_stats[].rx-bytes` | **MISSING** | **DRIFT** | Same. Radio name (`wifi0`, `wifi1`) not radio code (`ng`, `na`). |
| `radio_table_stats[].tx-errors` | **MISSING** | **DRIFT** | Not in radio stats. Per-VAP errors live in `vap_table[].tx_errors` (underscore). Device-level errors in `stat.ap.{wifi0}-rx_errors`. |
| `radio_table_stats[].rx-errors` | **MISSING** | **DRIFT** | Same as above. |
| `radio_table_stats[].satisfaction` | `radio_table_stats[].satisfaction` | YES | Integer, observed -1 (no data) or 0-100. |

**Keys actually present in `radio_table_stats[]`** (union across all
APs observed): `ast_be_xmit`, `ast_cst`, `ast_txto`, `bw`, `channel`,
`cu_self_rx`, `cu_self_tx`, `cu_total`, `extchannel`, `gain`,
`guest-num_sta`, `last_channel`, `last_interference_at`, `name`,
`num_sta`, `radio`, `satisfaction`, `state`, `tx_packets`,
`tx_power`, `tx_retries`, `tx_retries_pct`, `user-num_sta`.

**Mapping of design-intent fields to where they actually live:**

| Design intent | Actual path | Type |
|---------------|-------------|------|
| per-radio TX power | `radio_table_stats[?radio=='ng'].tx_power` | number |
| per-radio client count | `radio_table_stats[?radio=='ng'].user-num_sta` | integer |
| per-radio satisfaction | `radio_table_stats[?radio=='ng'].satisfaction` | integer (-1 when no data) |
| per-radio TX bytes (cumulative) | `stat.ap.wifi0-tx_bytes` (for `radio=='ng'`) / `stat.ap.wifi1-tx_bytes` (for `radio=='na'`) | float |
| per-radio RX bytes | `stat.ap.wifi0-rx_bytes` / `stat.ap.wifi1-rx_bytes` | float |
| per-radio TX errors | `stat.ap.wifi0-tx_errors` / `stat.ap.wifi1-tx_errors` | float |
| per-SSID traffic/errors/clients | `vap_table[]` (per `(radio, bssid)` VAP row); fields `tx_bytes`, `rx_bytes`, `tx_errors`, `rx_errors`, `num_sta`, `satisfaction` (ALL UNDERSCORE) | — |

**Radio-name-to-code mapping** on a U7PG2:
- `radio_table[0].name = "wifi0"`, `radio_table[0].radio = "ng"` (2.4 GHz)
- `radio_table[1].name = "wifi1"`, `radio_table[1].radio = "na"` (5 GHz)

WiFi 6/6E APs would add `"wifi2" / "ax"` or `"6e"` rows — not
present on this lab's U7PG2/U7IW/U7NHD/U7MSH hardware.

#### Switch — per-port nested fields

Live shape sampled from `usw-lite-16-nuc` (`type=usw`, model
`USL16LP`, 16 ports, `total_max_power: 45`).

| Design-proposed path | Live-observed | Match? | Notes |
|----------------------|---------------|--------|-------|
| `port_table[].up` | `port_table[].up` (boolean) | YES | |
| `port_table[].speed` | `port_table[].speed` (int, Mbps) | YES | 1000/100/10/auto. |
| `port_table[].tx_bytes` | `port_table[].tx_bytes` | YES | Underscore. Cumulative. |
| `port_table[].rx_bytes` | `port_table[].rx_bytes` | YES | Underscore. Cumulative. |
| `port_table[].poe_power` | `port_table[].poe_power` — **STRING, only on PoE-capable ports** | DRIFT | See "PoE findings" below. |
| `port_table[].tx_errors` | `port_table[].tx_errors` | YES | Integer. |
| `port_table[].rx_errors` | `port_table[].rx_errors` | YES | Integer. |
| `stat_device.total_max_power` | `total_max_power` | YES-BUT | Integer on PoE switches; `null` on non-PoE switches (e.g. `usw-lite-16-r740`). |
| `stat_device.num_port` | **MISSING** | **DRIFT** | Field doesn't exist. Design should derive port count from `len(port_table[])` instead, or read `total_ports` from the computed switch stats. Actually observed: the `uplink` sub-object sometimes carries `num_port` but it's the uplink port count, not the switch port count. |
| `stat_device.general_temperature` | **MISSING** | **DRIFT** | Field doesn't exist on USL16LP. A `has_temperature` boolean is present. Temperatures are reported only when the hardware has thermal sensors; for USL16LP / USWED76 `has_temperature: false`. Gateway (UDM) has `temperatures[]` (plural, array of `{name, type, value}` objects). |
| `stat_device.overheating` | `overheating` (boolean) | YES | Present on switches. |
| `stat_device.fan_level` | **MISSING** | **DRIFT** | Field doesn't exist on these switches. `has_fan: false` — these switches are fanless. Fan-level metric is only meaningful for larger PoE switches. |

**Keys actually present in `port_table[]`** (union across first
switch's 16 ports): `aggregate_members`, `aggregate_num_ports`,
`aggregated_by`, `anomalies`, `autoneg`, `bytes-r`, `custom_anomalies`,
`dot1x_mode`, `dot1x_status`, `egress_rate_limit_kbps_enabled`,
`enable`, `enabled`, `flowctrl_rx`, `flowctrl_tx`, `forward`,
`full_duplex`, `is_uplink`, `jumbo`, `lacp_state`, `lag_idx`,
`lag_member`, `last_connection`, `link_down_count`, `mac_table_count`,
`masked`, `media`, `name`, `native_networkconf_id`, `op_mode`,
`partner_system_id`, `poe_caps`, `poe_class`, `poe_current`,
`poe_enable`, `poe_good`, `poe_mode`, `poe_power`, `poe_voltage`,
`port_idx`, `port_poe`, `port_security_enabled`,
`port_security_mac_address`, `rx_broadcast`, `rx_bytes`, `rx_bytes-r`,
`rx_dropped`, `rx_errors`, `rx_multicast`, `rx_packets`, `satisfaction`,
`satisfaction_reason`, `service_mac_table`, `setting_preference`,
`speed`, `speed_caps`, `stp_edge_port`, `stp_pathcost`, `stp_state`,
`stp_state_change_count`, `tagged_vlan_mgmt`, `tx_broadcast`,
`tx_bytes`, `tx_bytes-r`, `tx_dropped`, `tx_errors`, `tx_multicast`,
`tx_packets`, `up`.

**PoE findings (renderer-gap-critical):**

Across the 8 switches in the lab:

| Switch | `total_max_power` | Ports | `poe_enable=true` | Has `poe_power` key | `poe_power>0` |
|--------|-------------------|-------|-------------------|---------------------|---------------|
| usw-lite-16-nuc | 45 | 16 | 0 | 8 | 0 |
| usw-lite-16-r740 | **null** | 16 | 0 | 0 | 0 |
| usw-lite-8-attic | 52 | 8 | 4 | 4 | 4 |
| Backyard Flex | 20 | 5 | 2 | 4 | 2 |
| usw-xg-8-ms | 150 | 10 | 0 | 8 | 0 |
| GarageFlex | 20 | 5 | 4 | 4 | 4 |
| usw-lite-16-central | 45 | 16 | 4 | 8 | 4 |
| AtticFlex | 46 | 5 | 4 | 4 | 4 |

- **`total_max_power` is `null` on non-PoE switches** (e.g.
  USL16LP-r740 variant). Design's PoE-budget-remaining computation
  must handle null gracefully.
- **`poe_power` is a STRING** (e.g. `"4.22"`, `"0.00"`), not a
  number. A `sum()` aggregate needs numeric coercion.
- **`poe_power` is only present on PoE-capable ports** (where
  `port_poe: true`). On the 16-port USL16LP, only 8 ports have
  `port_poe: true` (so 8 have `poe_power` key). On the USWED76
  (10G uplink / no PoE on 10G), 8 of 10 ports have `poe_power` key
  but none deliver power.
- **Correct aggregate predicate**: `port_table[?port_poe==true].poe_power`
  (filter to PoE-capable ports) or just `port_table[*].poe_power`
  with the renderer skipping missing entries. Either way the
  renderer must handle strings.

#### Gateway (UDM) — differentiating WAN from LAN ports

The UDM Pro's `port_table[]` carries 11 entries. The design asked
"how does UDM differentiate WAN vs LAN port entries?" — the answer:

- **Per-port `network_name` string**: `"lan"` for LAN-side ports,
  `"wan"` for WAN ports (eth8 on this lab, port_idx 9), `"wan2"`
  for the second WAN uplink (SFP+, eth9, port_idx 10).
- **Top-level `wan1` and `wan2` objects**: alongside `port_table[]`,
  the UDM emits `wan1` and `wan2` top-level objects that carry the
  WAN uplink's full port state PLUS WAN-specific fields
  (`uplink_ifname`, `latency`, `availability`, `is_uplink`,
  `mac_table[]`). These are the UDM's canonical WAN metric surfaces.
- **Top-level `uplink` object**: the "current active WAN" — has
  `comment: "WAN"`, `uptime`, `drops`, `xput_up`/`xput_down`,
  `speedtest_status`, `speedtest_ping`.

| Design-proposed UDM field | Live-observed path | Notes |
|---------------------------|--------------------|-------|
| WAN TX/RX bytes | `wan1.tx_bytes` / `wan1.rx_bytes` (cumulative, number) OR `port_table[?network_name=='wan'].tx_bytes` | `wan1` is cleaner; single scalar per WAN. |
| WAN errors | `wan1.tx_errors` / `wan1.rx_errors` (number, 0 observed) | |
| WAN speedtest | `uplink.speedtest_status`, `uplink.xput_up`, `uplink.xput_down`, `uplink.speedtest_lastrun` | On `uplink` (current active WAN), not per-WAN. |
| WAN latency | `wan1.latency` (ms) | Also on `uplink.latency`. |
| WAN availability | `wan1.availability` (0-100) | NOT duplicated on `uplink`. |
| `temperatures[?name=='CPU'].value` | `temperatures[?name=='CPU'].value` (number, e.g. 45.75) | YES. UDM has 3 temperature sensors: CPU, Local (board), PHY (board). |
| `temperatures[?name=='System'].value` | **DRIFT** | The named sensor is `"Local"` not `"System"`. Design predicate `[?name=='System']` would miss it. Correct: `[?name=='Local']` or `[?type=='board']`. |
| `stat_device.storage.used / storage.size` | `storage[]` (array of objects, one per mountpoint) | DRIFT. It's an array, not a single-object dot-path. Observed: `storage[?mount_point=='/persistent'].used / storage[?mount_point=='/persistent'].size`. Two mountpoints: `/persistent` (eMMC, 2 GB) and `/tmp` (1 GB). |

**UDM `system-stats` is strings**: `cpu: "23.8"`, `mem: "75.1"`,
`uptime: "434438"`. Needs numeric coercion in the renderer.

#### Off-target device fields discovered (noteworthy for v1+ design)

- `lldp_table[]`: every device reports its LLDP neighbor table as
  an array of `{chassis_id, local_port_idx, port_id, is_wired}`
  objects. This is a higher-fidelity topology source than
  `uplink.uplink_mac` — the physical mesh is reconstructable.
  Recommend flagging for v2 topology work.
- `downlink_lldp_macs[]`: array of MAC strings for LLDP-visible
  downstream devices — inverse of `uplink_mac`. Could replace or
  supplement the uplink-direction relationship if the renderer
  supports "child collects a set of parent MACs" joins.
- `stat.ap.*`, `stat.usw.*`, `stat.udm.*`: the device-level `stat`
  object holds high-cardinality per-radio / per-interface
  counters flat-prefixed by radio/interface name. Rich source for
  throughput and error metrics if the renderer supports path
  templates like `stat.ap.${radio_name}-rx_bytes`.
- `satisfaction` at the device level (not just per-radio) — a
  site-wide rollup metric UniFi's own UI uses.

### 5. `GET /proxy/network/api/s/default/stat/sta`

- **Response envelope**: `{meta:{rc:"ok"}, data:[{...},...]}` — one
  row per currently-connected client (wired + wireless combined).
- **Response bytes**: ~200 KB with 128 clients.
- **Cardinality warning**: 128 clients on this lab; MSP / guest-
  heavy deployments could see thousands. v1 design's "Wireless
  Client Aggregate" object deliberately does NOT materialize per-
  client objects from this endpoint — this is correct.

Client row sample (abbreviated):
```json
{
  "site_id": "67ba522dda21a4461c2db3f8",
  "mac": "<redacted>",
  "ip": "172.27.8.21",
  "is_wired": true,
  "is_guest": false,
  "oui": "VMware, Inc.",
  "os_name": 1,
  "satisfaction": 100,
  "uptime": 503797,
  "last_seen": 1776550307,
  "last_uplink_name": "usw-xg-8-ms",
  "last_uplink_mac": "38:05:25:34:e3:19",
  "last_uplink_remote_port": 7,
  "sw_mac": "38:05:25:34:e3:19",
  "sw_port": 7,
  "vlan": 180,
  "network": "VCF 9 MGMT VMs",
  "network_id": "<mongo id>",
  "wired-tx_bytes": 58774546,
  "wired-rx_bytes": 563283,
  "wired-tx_bytes-r": 0.0,
  "wired-rx_bytes-r": 0.0
}
```

- **Wireless-client-aggregate metrics** can be computed via
  `length(data[?!is_wired])` / `length(data[?is_guest])` JMESPath
  expressions, OR more cheaply via the `wlan` subsystem row in
  `stat/health` which already carries `num_user`, `num_guest`,
  `num_iot`, `num_ap`, `num_disconnected`. Design's decision to
  use `stat/health[?subsystem=='wlan']` for this singleton is
  correct and minimizes collection cost vs. a full `stat/sta` pull.
- **Hybrid wired/wireless byte-rate field names**: `wired-rx_bytes`
  and `wired-rx_bytes-r` are hyphenated. Wireless equivalents
  (`wifi-rx_bytes`, etc.) were not sampled but follow the same
  pattern on aiounifi reference.

### 6. Integration API probe — `/proxy/network/integration/v1/*`

**Probed without `X-API-Key`** to distinguish "endpoint exists but
requires auth" (401) from "endpoint not registered" (404).

| Path | Status (no auth) | Error body code | Interpretation |
|------|------------------|-----------------|----------------|
| `/proxy/network/integration/v1/info` | 401 | `api.authentication.missing-credentials` | **Endpoint registered.** Integration API is enabled on this controller. |
| `/proxy/network/integration/v1/sites` | 401 | same | Endpoint registered. |
| `/proxy/network/integration/v1/devices` | 401 | same | Endpoint registered. |
| `/proxy/network/integration/v1/clients` | 401 | same | Endpoint registered. |
| `/proxy/network/integration/v1/does-not-exist` | 401 | same | **Auth filter runs before route dispatch**, so all paths return 401 whether registered or not. Cannot enumerate endpoints without a key. |
| `/proxy/network/integration/v2/info` | 401 | same | Can't distinguish v1 from v2 registration without a key. |

**Error response body shape** (structured, from first probe):

```json
{
  "statusCode": 401,
  "statusName": "UNAUTHORIZED",
  "code": "api.authentication.missing-credentials",
  "message": "Missing Credentials",
  "timestamp": "2026-04-18T22:11:44.571115810Z",
  "requestPath": "/integration/v1/info",
  "requestId": "<uuid>"
}
```

The envelope is **entirely different** from the classic API's
`{meta:{rc:"error"}, data:[]}` shape — Integration API uses a flat
ProblemDetails-style error object. An MP targeting this surface
needs separate error-parsing from the classic surface.

**Verdict**: briefing §1b / §2 recommendation to prefer
`X-API-Key` on v9.3.43+ holds. The lab controller (Network App
10.2.105) is eligible. Scott can generate the key via UniFi UI →
Network → Settings → Control Plane → Integrations. The MP's
connection profile should still support the classic session
fallback for any older controllers a user might point it at.

### 7. Event / alarm endpoints — discovery probe

The briefing (§3, §5, and supplement §9) references
`/api/s/{site}/stat/event` with a 3,000-result cap as the canonical
event endpoint. **On Network App 10.2.105 this path returns 404.**

Probed 17 candidate paths; summary:

| Path | Status | `meta.rc` | Data |
|------|--------|-----------|------|
| `/s/{site}/stat/event?_limit=3` | 404 | error (`api.err.NotFound`) | — |
| `/s/{site}/stat/alarm?_limit=3` | 200 | ok | **0 rows** (no active alarms on this lab) |
| `/s/{site}/rest/alarm?_limit=3` | 200 | ok | **0 rows** (same — `/rest/alarm` is the alarm endpoint) |
| `/s/{site}/rest/event?_limit=3` | 400 | error | Exists but requires required query params we didn't supply |
| `/s/{site}/stat/event/list?_limit=3` | 404 | error | — |
| `/s/{site}/stat/sessions` | 404 | error | — |
| `/s/{site}/stat/admin` | 404 | error | — |
| `/s/{site}/stat/anomalies` | 200 | ok | **2 rows** — per-device satisfaction/anomaly counts |
| `/s/{site}/stat/rogueap?_limit=3` | 200 | ok | 3 rows — rogue AP list |
| `/s/{site}/stat/report/hourly.site` | 200 | ok | 168 rows — hourly historical site stats (7 days × 24 hours) |
| `/s/{site}/list/event?_limit=3` | 400 | error | Exists, needs params |
| `/s/{site}/list/alarm?_limit=3` | 200 | ok | 0 rows — alternative alarm path |
| `/s/{site}/rest/event-log?_limit=3` | 400 | error | Exists, needs params |
| `/api/events?_limit=3` | 401 | error | Exists outside `/proxy/network/api/s/{site}` — is at console level |
| `/s/{site}/stat/hourly.ap` | 404 | error | — |
| `/s/{site}/stat/daily.site` | 404 | error | — |
| `/s/{site}/get/setting/super_events` | 200 | ok | 1 row — event notification setting |

**Implications for v1.1 events scope:**

1. The classic `stat/event` endpoint documented in ubntwiki and
   referenced by briefing §3 **does not exist on Network App
   10.2.105**. The briefing (and supplement §1) cites it as if
   current; the briefing drifted with the Network App major version
   bump.
2. **`rest/alarm` and `list/alarm` both exist and return the same
   envelope** — the replacement for `stat/alarm` / `stat/event`.
   Both return `{meta:{rc:"ok"}, data:[]}` when empty.
3. **`rest/event` and `list/event` exist but require query
   parameters** — 400 errors with `_limit` alone suggest at least
   `time_gt` / time-window parameter is mandatory. Needs a targeted
   follow-up probe with candidate params.
4. **`stat/anomalies` is a real current surface** — returns per-
   device satisfaction/anomaly rows. Usable for Tier-1 alerts
   without needing the event stream.
5. **`stat/rogueap` is a useful security-adjacent surface** —
   returns rogue AP detections.
6. **`stat/report/*` is the historical surface** — 168 rows at
   `hourly.site` is 7 days × 24 hours = the 7-day hourly roll-up.
   Design's "config-drift polling" doesn't use this but it's
   relevant for a historical-metrics MP extension.

**Briefing drift called out**: claim "`stat/event` has a 3000-result
cap" — on Network App 10.2.105 it's not a cap, it's a 404. v1.1
events scope must re-discover the actual event endpoint shape on
current Network App versions (probably `list/event` or `rest/event`
with mandatory window params).

---

## Object model candidates

### UniFi Site

- **Source endpoints**: `self/sites` (identity), `stat/sysinfo`
  (controller version + retention), `stat/health` (per-subsystem
  aggregates — wan, lan, wlan, www, vpn).
- **Identifier**: `self/sites[].name` (URL-path identifier, e.g.
  `"default"`; NOT `desc`).
- **Display name**: `self/sites[].desc`.
- **Secondary identifier**: `self/sites[]._id` (Mongo ID, may be
  useful for cross-referencing but not URL-addressable).
- **Properties**: `name`, `desc`, `role`, `device_count`,
  `version` (from sysinfo), `build`, `console_display_version`,
  `udm_version`, `hostname`, `timezone`, `is_cloud_console`,
  `data_retention_days`.
- **Metrics (from `stat/sysinfo`)**: `uptime` (seconds).
- **Metrics (from `stat/health[?subsystem=='wan']`)**: `num_sta`,
  `tx_bytes-r`, `rx_bytes-r`, `num_gw`, `num_adopted`,
  `num_disconnected`.
- **Metrics (from `stat/health[?subsystem=='www']`)**: `latency`,
  `uptime` (seconds up on the www path — different from site
  uptime), `drops`, `xput_up`, `xput_down`, `speedtest_status`,
  `speedtest_ping`.
- **Metrics (from `stat/health[?subsystem=='wlan']`)**: `num_user`,
  `num_guest`, `num_iot`, `num_ap`, `num_adopted`,
  `num_disconnected`, `tx_bytes-r`, `rx_bytes-r`.
- **Metrics (from `stat/health[?subsystem=='lan']`)**: `num_user`,
  `num_guest`, `num_iot`, `num_sw`, `num_adopted`,
  `num_disconnected`, `tx_bytes-r`, `rx_bytes-r`.
- **Metrics (from `stat/health[?subsystem=='vpn']`)**:
  `remote_user_num_active`, `remote_user_tx_bytes`,
  `remote_user_rx_bytes`.
- **Relationships (parents)**: none (root).
- **Relationships (children)**: AP, Switch, Gateway (all by
  `scope: adapter_instance` per design).

### Access Point

- **Source endpoint**: `stat/device` with filter
  `data[?type=='uap']`.
- **Identifier**: `mac` (device-level, stable across adoption).
- **Secondary identifier**: `_id` (Mongo ID).
- **Display name**: `name` (admin-set, may be blank).
- **Properties**: `mac`, `name`, `model`, `model_in_lts`, `version`,
  `upgradable`, `adopted`, `ip`, `serial`, `type`, `uplink.uplink_mac`,
  `uplink.uplink_device_name`, `uplink.uplink_remote_port`,
  `uplink.uplink_source`, `country_code`.
- **Metrics (device-level)**: `state`, `_uptime`, `last_seen`,
  `system-stats.cpu` (string→number), `system-stats.mem`
  (string→number), `num_sta`, `user-num_sta`, `guest-num_sta`,
  `satisfaction`.
- **Metrics (per-radio, from `radio_table_stats[?radio=='ng'|'na']`)**:
  `user-num_sta`, `tx_power`, `satisfaction`, `channel`,
  `tx_retries`, `tx_retries_pct`, `cu_total`, `cu_self_rx`,
  `cu_self_tx`.
- **Metrics (per-radio throughput, from `stat.ap.wifi0-*` /
  `wifi1-*` scalar keys)**: `wifi0-rx_bytes`, `wifi0-tx_bytes`,
  `wifi0-rx_errors`, `wifi0-tx_errors`, `wifi0-rx_dropped`, etc.
  Prefixed by radio NAME (`wifi0` / `wifi1`), not radio CODE
  (`ng` / `na`).
- **Relationships (parents)**: UniFi Site (`adapter_instance`).

### Switch

- **Source endpoint**: `stat/device` with filter
  `data[?type=='usw']`.
- **Identifier**: `mac`.
- **Properties**: same common device set as AP, plus `has_temperature`,
  `has_fan`, `overheating`, `total_max_power`
  (nullable on non-PoE), `total_max_effective_power`,
  `total_used_power` (observed to exist — not in Navani's recon).
- **Metrics (device-level)**: same as AP.
- **Metrics (per-port, from `port_table[]`)**: `up`, `speed`,
  `tx_bytes`, `rx_bytes`, `tx_errors`, `rx_errors`, `tx_dropped`,
  `rx_dropped`, `rx_broadcast`, `rx_multicast`, `rx_packets`,
  `tx_packets`, `satisfaction`, `mac_table_count`,
  `link_down_count`, `stp_state`, `anomalies`. Plus PoE-only:
  `poe_power` (string), `poe_voltage` (string), `poe_current`
  (string), `poe_class`.
- **Relationships (parents)**: UniFi Site.

### Gateway (UDM / USG)

- **Source endpoint**: `stat/device` with filter
  `data[?type=='udm' || type=='ugw']`. Lab lacks a `ugw` instance.
- **Identifier**: `mac`.
- **Properties**: common device set + `network_table[]`
  (networks served), `wan_magic_subscription`,
  `release_channel`, `active_geo_info`.
- **Metrics (device-level)**: `state`, `_uptime`, `last_seen`,
  `system-stats.cpu`, `system-stats.mem`, `num_sta`,
  `overheating`.
- **Metrics (per-temperature, from `temperatures[]`)**: filter by
  `name` — on UDM Pro the three sensors are `"CPU"`, `"Local"`,
  `"PHY"`. **Design's `[?name=='System']` filter does not match
  the actual sensor name.**
- **Metrics (storage, from `storage[]`)**: filter by
  `mount_point=='/persistent'` for the main storage volume.
  `size` and `used` are numbers in bytes.
- **Metrics (WAN, from `wan1` and `wan2` top-level objects)**:
  `tx_bytes`, `rx_bytes`, `tx_errors`, `rx_errors`, `tx_rate`,
  `rx_rate`, `tx_rate-max`, `rx_rate-max`, `tx_bytes-r`,
  `rx_bytes-r`, `latency`, `availability`, `speed`, `max_speed`,
  `up`, `is_uplink`.
- **Metrics (active WAN, from `uplink` top-level object)**:
  `speedtest_status`, `speedtest_ping`, `speedtest_lastrun`,
  `xput_up`, `xput_down`, `drops`, `uptime`, `latency`.
- **Relationships (parents)**: UniFi Site.

### Wireless Client Aggregate (singleton)

- **Source endpoint**: `stat/health` with filter
  `data[?subsystem=='wlan']` (single row).
- **Identifier**: piggybacks site name (one aggregate per site).
- **Metrics**: `num_user`, `num_guest`, `num_iot`, `num_ap`,
  `num_adopted`, `num_disconnected`, `tx_bytes-r`, `rx_bytes-r`.
- **Relationships (parents)**: UniFi Site (1:1, scope
  `adapter_instance`).

---

## Cross-request join keys

| Key | Source A | Source B | Binds |
|-----|----------|----------|-------|
| `mac` | `stat_device[type=='uap'].mac` | `stat_device[type=='usw'].uplink.uplink_mac` | AP ↔ parent Switch/AP (topology, v1.1) |
| `mac` | `stat_device[type=='usw'].mac` | `stat_device[type=='usw'].uplink.uplink_mac` | Switch ↔ parent Switch (daisy-chain, v1.1) |
| `mac` | `stat_device.mac` | `stat/sta.last_uplink_mac` | Client ↔ uplink device (v2 per-client) |
| `sw_mac` + `sw_port` | `stat/sta.sw_mac` + `stat/sta.sw_port` | `stat_device[type=='usw'].mac` + `port_table[].port_idx` | Wired client ↔ switch port (v2) |
| `gw_mac` | `stat/health[?subsystem=='wan'].gw_mac` | `stat_device[type=='udm'\|\|'ugw'].mac` | Bind WAN health row to Gateway device |
| `network_id` | `stat_device.connection_network_id` | `rest/networkconf[]._id` | Device → Network VLAN (v2 config drift) |
| `native_networkconf_id` | `stat_device.port_table[].native_networkconf_id` | `rest/networkconf[]._id` | Switch port → Network VLAN (v2) |

---

## Renderer-gap wire-shape findings (design axis 5 validation)

The design flagged three renderer-gap-motivating patterns. Verdict:

### Finding 1 — JMESPath filter predicates (e.g. `[?subsystem=='wan']`)

**Wire shape confirmed matches design assumption.**

- `stat/health` returns a flat **array** of subsystem objects where
  `subsystem: "<name>"` discriminates the row. Exactly what the
  design's `data[?subsystem=='wan']` assumes.
- The response is NOT a dict keyed by subsystem (e.g.
  `{wan: {...}, lan: {...}}`). If the renderer doesn't support
  JMESPath filter predicates, the fallback would be to index into
  `data[0]`, `data[1]`, ... but subsystem ordering is not documented
  as stable — today's order was `wlan, wan, www, lan, vpn` but this
  cannot be relied on.
- **Renderer requirement**: JMESPath filter predicate support
  (`[?key=='value']`) is required for site health metrics.
  Alternative: the MP could iterate `data[]` in the adapter and
  route each row to its subsystem-specific metrics — but this
  pushes conditional logic out of the YAML into a built-in adapter
  helper.

### Finding 2 — Array aggregates (`sum(port_table[*].poe_power)`, `count()`)

**Wire shape has complications the design didn't anticipate.**

- `port_table[]` **is** a JSON array of per-port objects — design
  assumption correct at the structural level.
- **But `poe_power`**:
  - Is a STRING, not a number (`"4.22"`, `"0.00"`).
  - Is only present on PoE-capable ports (`port_poe: true`).
    Non-PoE ports omit the key entirely.
  - A naive `sum(port_table[*].poe_power)` JMESPath expression
    would emit `null` because JMESPath `sum()` requires numbers.
- **Correct aggregate expression**:
  `sum(to_number(port_table[?port_poe==true].poe_power))` — but
  JMESPath `to_number` is a type-coercion function that not every
  implementation supports.
- **Renderer requirement**: either (a) support JMESPath's
  `to_number` extension AND filter predicates AND aggregate
  functions; or (b) implement a renderer-side helper that pulls
  the array, coerces strings to numbers, and aggregates. Option
  (b) is what Synology's renderer does today.
- **Design metric `ports_up` via `port_table[?up==true].idx` with
  `aggregate: count`**: should be `port_idx` not `idx` (the field
  is `port_idx`). Minor correction.

### Finding 3 — Compose operators (`poe_budget_remaining = total_max_power - sum(poe_power)`)

**Wire shape validates design assumption, but null handling needed.**

- `total_max_power` exists at the `stat_device` (switch) root level
  as expected. Integer or null depending on whether the switch is
  PoE-capable.
- **Four switches (usw-lite-16-r740, usw-lite-16-nuc, usw-xg-8-ms,
  Backyard Flex variants) report `total_max_power=null` OR have
  no PoE-enabled ports.** The compose expression must:
  - Return `null` (or omit the metric) when `total_max_power` is
    null.
  - Treat missing `poe_power` entries as 0 when summing.
  - Coerce string `"0.00"` to numeric 0.
- **Renderer requirement** (in addition to Finding 2): compose
  expressions with null-propagation semantics. `a - b` where
  either operand is null should yield null, not 0 or an error.

### Summary for mp-designer

The three renderer-gap axes flagged in the design **are all real
and warranted**. The live wire doesn't invalidate any of them. But
the design's expressions need three specific refinements:

1. JMESPath expressions work AS WRITTEN for Site health (no
   change).
2. PoE aggregates need string coercion and should filter on
   `port_poe==true` to avoid over-emitting rows.
3. Compose expressions need explicit null-propagation semantics.

The design's Option A fallbacks (non-array scalars in v1,
first-class Port object in v1.1) remain the correct safety nets
until the renderer work lands.

---

## v1.1 scoping notes

### Protect (v1.1 camera scope)

The `GET /proxy/protect/api/bootstrap` endpoint returns 200 against
session auth (no separate Protect login required — the UniFi OS
session covers Protect). Response is ~230 KB; top-level keys:
`nvr`, `cameras` (12 items on this lab), `chimes` (2), `lights`
(0), `sensors` (0), `sirens`, `speakers`, `fobs`, `hubs`,
`viewers`, `users`, `groups`, `cameraGroups`, `agreements`,
`liveviews`, `ringtones`, `aiports`, `aiprocessors`, `readers`,
`relays`, `linkstations`, `deviceGroups`, `bridges`,
`lastUpdateId`.

Camera records carry the design's referenced fields:
`state` (enum: `CONNECTED`/`DISCONNECTED`/`UPDATING`),
`fwUpdateState` (enum: `upToDate`/`updateAvailable`/`updating`),
`latestFirmwareVersion`, `firmwareVersion`, `isAdopted`,
`isConnected`, `lastMotion` (epoch ms), `lastRing`, `uptime`
(ms, not seconds — differs from Network API's seconds!),
`isWireless` (nullable), `wiredConnectionState.phyRate`,
`channels[]` (per-stream config).

Key deltas from design expectations:
- **`uptime` is milliseconds** in Protect, not seconds like Network
  API. Renderer must either normalize or emit labeled as ms.
- **`isWireless` is null on wired cameras** (not false) — need
  explicit null-check or default.
- **`wiredConnectionState.phyRate` is null when camera is wireless
  or disconnected**; design should treat null as "no wired link".
- **`lastUpdateId`**: UUID cursor for the Protect WebSocket
  `/proxy/protect/ws/updates?lastUpdateId=<id>` stream. MPB
  doesn't support WS, so v1.1 is still polling-based.

No sidecar file written; the Protect scope fits in this paragraph.

### Events / alarms (v1.1)

Covered in Endpoint 7 above. Summary:

- Classic `stat/event` is 404 on Network App 10.2.105.
- `rest/alarm` and `list/alarm` return an empty array and appear
  to be the replacement alarm endpoints.
- `rest/event` and `list/event` exist but need query parameters
  we didn't discover (returned 400 with `_limit` alone).
- `stat/anomalies` and `stat/rogueap` are real surfaces for
  Tier-1-alert-adjacent data.
- **Briefing §3's "3000-result cap on event/alarm endpoints" is
  unverifiable on this controller**; the primary endpoint is 404.
  v1.1 event scoping needs a follow-up recon against the current
  event path shape (probably `list/event` with `time_gt` or a
  similar window param).

No sidecar file written; v1.1 events recon needs a larger probe
than fits in this map.

---

## Gaps and risks

### Endpoint-level surprises

1. **Event endpoint path changed in Network App 10.x.** Briefing and
   supplement both cite `stat/event` — that's 404 now. v1.1 event
   integration is blocked until the current path and query shape
   are re-discovered.
2. **Integration API is available but unverified end-to-end.** The
   probe without a key confirmed endpoints exist; the actual
   response shapes were not captured (we have no valid key). Scott
   should generate a key via Network → Settings → Control Plane →
   Integrations and re-run a targeted Integration API probe to
   capture response shapes before mp-designer commits to the
   Integration API path in v1.
3. **`stat/sysinfo` version field exposes the UniFi OS /
   Network App confusion.** Both `version` (Network App, `10.2.105`)
   and `udm_version` / `console_display_version` (`5.0.16`) are
   emitted. An MP reporting "Controller Version" should use
   `version`, not `console_display_version` — but that's counter-
   intuitive to anyone who only knows UniFi from the UI.

### Pagination / cardinality observations

- **`self/sites`**: no pagination; single-response for all sites
  the user can see. MSP scenarios at 100+ sites uncorroborated
  here (this lab has 1 site).
- **`stat/device`**: single response for all 15 devices; ~385 KB
  today. Linear scaling with device count; no pagination param
  observed. At a 100-device MSP deployment this would be
  ~2.5 MB — still fine.
- **`stat/sta`**: 128 clients today, ~200 KB. At thousands of
  clients could become large. No pagination param exercised. The
  design's choice to not materialize per-client objects and
  instead aggregate via `stat/health.wlan` is correct for cost.
- **`stat/report/hourly.site`**: 168 rows = 7 days × 24 hours, i.e.
  7-day window. Daily and monthly variants expected to exist; not
  probed further. Historical metrics are out of v1 scope.
- **`stat/alarm`** and **`rest/alarm`**: both return empty arrays
  today. Pagination shape not testable until alarms are present.

### Rate-limit observations

- 25 probes issued across this recon with ~0.3s to 1s spacing.
- **No 429 responses observed.**
- **No 403 responses observed.**
- **No CSRF rotation on GETs** (consistent with briefing).
- `Access-Control-Expose-Headers` lists `X-Connection-Type`,
  `X-Csrf-Token`, `X-File-Id`, `X-Token-Expire-Time`,
  `X-Updated-Csrf-Token` — but none of the write-specific headers
  (`X-Updated-Csrf-Token`) were emitted on any read.

### Briefing / supplement drift (to flag to PKA team)

1. **Briefing §3 device count ("6 switches")** is wrong for Scott's
   lab — actual is 8 switches. Briefing asserted "1 UDM Pro +
   6 switches + 6 APs" (13 devices); actual is 1 UDM + 8 switches +
   6 APs = 15 devices. Source: `self/sites[].device_count = 15`
   plus `stat/device` enumeration.
2. **Briefing §5 version claim "Network app is probably 8.x-10.x"
   is correct in range, confirms as 10.2.105.** The briefing's
   prediction of "UniFi OS 5.x ships Network App 8.x-10.x" was
   on the money.
3. **Briefing §3's reference to `stat/event` as an active metric
   source** is stale — 404 on Network App 10.2.105. v1.1 events
   work must re-discover the current path.
4. **Supplement §1a's statement that `/api/s/{site}/stat/event`
   is a current endpoint** is also stale for 10.x.
5. **Briefing §3's `radio_table_stats[].tx-bytes` claim**: these
   fields are not in `radio_table_stats[]`. Per-radio bytes are in
   device-level `stat.ap.wifi0-tx_bytes` (by radio name) or in
   per-SSID `vap_table[].tx_bytes` (underscore form). The
   supplement (§7 UnPoller catalog) says "Wi-Fi TX/RX bytes per
   radio" without citing a specific field name, which is safer.
6. **Briefing §3's `system-stats.cpu` typing**: the field is a
   string on the UDM and a number on APs — inconsistent across
   device types. MP renderer must coerce.
7. **Briefing §3's `total_max_power` minus sum-of-`poe_power`
   formula for PoE budget**: the formula is right but both
   operands have null / string gotchas detailed in Finding 3.

### Unanswered / deferred

- **Integration API response shapes** — can't be captured until
  Scott generates an API key.
- **Protect WebSocket** — out of MPB scope per briefing §2, not
  probed.
- **Config-drift endpoints (`rest/networkconf`, `rest/wlanconf`,
  `rest/firewallrule`)** — data cached in
  `/tmp/unifi-recon/net-*.json` but not mapped here (out of v1
  scope per design scope-reduction table).
- **Per-client-MAC objects from `stat/sta`** — endpoint shape
  captured; object modeling deferred to v2 per design.
- **`ugw` gateway type** — not exercised (lab has no USG). Design
  filter `[?type=='ugw' || type=='udm']` structurally correct;
  `ugw`-specific fields not verified.
