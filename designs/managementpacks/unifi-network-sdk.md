# UniFi Network SDK Adapter — Design

## Initial prompt

User: "Let's create a second UniFi pak using the Java SDK. Replace the
existing Tier 1 packs with a single Tier 2 adapter. Full scope: switch
ports, AP radios, PoE, LLDP→ESXi stitching, plus everything the Tier 1
packs already do. Classic API (username/password). Client tracking is
lower priority unless we can tie to VMs. Lab: UDM Pro + 8 switches +
6 APs."

Decision: MPB is not the preferred track for non-trivial APIs.

## Vision

A single Tier 2 SDK management pack that replaces both existing Tier 1
UniFi packs (`unifi_network` and `unifi_network_integration`). Uses the
classic UniFi Network API (`/proxy/network/api/...`) with session cookie
auth for maximum data richness.

Key differentiators over the Tier 1 packs:
1. **Per-switch-port objects** with tx/rx, errors, PoE, link state
2. **Per-AP-radio objects** with channel utilization, client count, retries
3. **LLDP→ESXi Host stitching** (click a host, see its switch port)
4. **PoE budget tracking** per switch
5. **Gateway WAN interfaces** as first-class objects
6. **Protect cameras + NVR** via same session (zero extra auth cost)
7. **Wire topology** via uplink_mac (adapts on re-cable)

## Proposed object hierarchy

```
UniFi World (singleton)
└── UniFi Site (multi-site: all discovered from one instance)
    ├── UniFi Gateway (UDM/USG)
    │   └── UniFi WAN Interface (wan1, wan2)
    ├── UniFi Switch ──→ [parent/child via uplink_mac; adapts on re-cable]
    │   └── UniFi Switch Port
    │       └── [stitches to: VMWARE HostSystem via LLDP]
    ├── UniFi Access Point
    │   └── UniFi Radio (2.4GHz, 5GHz, 6GHz)
    ├── UniFi NVR (Protect — peer of Gateway under Site)
    │   └── UniFi Camera
    └── UniFi Wireless Aggregate (singleton per site)
```

**11 object types.** Design decisions:
- Wire topology: switches parent/child via `uplink.uplink_mac` (adapts on re-cable)
- Multi-site: all sites discovered from one adapter instance
- Gateway temperatures: metrics on gateway (temp_cpu, temp_local, temp_phy), not separate objects
- NVR as peer of Gateway under Site (works for both UDM Pro built-in and standalone UNVR)
- Cameras as children of NVR
- Protect API uses same UniFi OS session cookie — zero extra auth cost

## Object types

### UniFi World
- Purpose: top-down traversal entry point
- Identifier: `world_id` = `unifi_world` (fixed)
- No metrics or properties

### UniFi Site
- Source: `self/sites` + `stat/sysinfo`
- Identifier: `site_name` (e.g., "default")
- Properties: description, version, timezone, device_count
- Metrics: none (aggregates live on the Wireless Aggregate child)

### UniFi Gateway
- Source: `stat/device[?type=='udm' || type=='ugw']`
- Identifier: `mac`
- Display name: `name` field or model + MAC suffix
- **System group** (metrics): cpu_pct, mem_pct, uptime
- **System group** (properties): model, firmware, serial, ip, mac
- **Temperature group** (metrics): temp_cpu, temp_local, temp_phy (from `temperatures[]`, filter by name)
- **Speedtest group** (metrics): xput_up, xput_down, latency
- Note: `system-stats` fields are STRINGS on UDM — must coerce
- Note: `temperatures[]` sensor names are "CPU", "Local", "PHY" (NOT "System")
- Note: some gateway models don't have temperature sensors — handle gracefully

### UniFi WAN Interface
- Source: `stat/device[type=='udm'].wan1` / `wan2`
- Identifier: `wan_name` (e.g., "wan1")
- Parent: Gateway
- **Traffic group** (metrics): tx_bytes, rx_bytes, tx_errors, rx_errors
- **Health group** (metrics): latency, availability, speed
- **Configuration group** (properties): type, ip, netmask, gateway, dns

### UniFi Switch
- Source: `stat/device[?type=='usw']`
- Identifier: `mac`
- Display name: `name` field or model + MAC suffix
- **System group** (metrics): cpu_pct, mem_pct, uptime, num_sta, satisfaction
- **System group** (properties): model, firmware, serial, ip, mac, has_fan, overheating
- **PoE group** (metrics): total_max_power, poe_consumption (sum of port poe_power), poe_budget_remaining (computed)
- **PoE group** (properties): poe_capable (derived from total_max_power != null)
- Note: total_max_power is null on non-PoE switches — handle gracefully

### UniFi Switch Port
- Source: `stat/device[type=='usw'].port_table[]`
- Identifier: `port_key` = `{switch_mac}_{port_idx}`
- Display name: `name` field if set, else "Port {port_idx}"
- Parent: Switch
- **Traffic group** (metrics): tx_bytes, rx_bytes, tx_errors, rx_errors
- **Status group** (metrics): satisfaction, mac_table_count
- **Status group** (properties): up, speed, duplex, is_uplink, media, stp_state
- **PoE group** (metrics): poe_power (coerce from string!), poe_voltage, poe_current
- **PoE group** (properties): poe_enable, poe_class, poe_mode
- **LLDP group** (properties): lldp_system_name, lldp_port_id, lldp_chassis_id
- Note: PoE fields only present on ports where `port_poe: true`
- Note: LLDP data from `lldp_table[]` — key for ESXi stitching

### UniFi Access Point
- Source: `stat/device[?type=='uap']`
- Identifier: `mac`
- Display name: `name` field or model + MAC suffix
- **System group** (metrics): cpu_pct, mem_pct, uptime, num_sta, satisfaction
- **System group** (properties): model, firmware, serial, ip, mac

### UniFi Radio
- Source: `stat/device[type=='uap'].radio_table_stats[]`
- Identifier: `radio_key` = `{ap_mac}_{radio}` (e.g., `aa:bb:cc_ng`)
- Display name: "2.4 GHz" / "5 GHz" / "6 GHz" (derived from radio code)
- Parent: Access Point
- **RF group** (metrics): channel, tx_power, cu_total (channel utilization %), satisfaction, tx_retries_pct
- **Clients group** (metrics): user_num_sta
- **Traffic group** (metrics): tx_bytes, rx_bytes (from device-level stat.ap.{radioName}-tx_bytes)
- **Configuration group** (properties): radio_type (ng/na/6e), ht, min_txpower, max_txpower
- Note: throughput metrics use radio NAME (wifi0/wifi1), not radio CODE (ng/na) — must map

### UniFi Wireless Aggregate
- Source: `stat/health[?subsystem=='wlan']`
- Identifier: `site_name` + `_wlan_aggregate`
- Parent: Site
- **Clients group** (metrics): num_user, num_guest, num_iot, num_disconnected
- **Performance group** (metrics): num_ap, tx_bytes_r, rx_bytes_r (rate fields)
- Purpose: lightweight client/wireless health without materializing 100+ client objects

### UniFi NVR
- Source: `/proxy/protect/api/bootstrap` → `nvr` object
- Identifier: `nvr_mac` (NVR MAC address)
- Display name: `name` field (e.g., "UDM Pro") or model
- Parent: Site (peer of Gateway, Switch, AP)
- **System group** (metrics): uptime (NOTE: milliseconds, not seconds!), cpu_pct, mem_pct
- **Storage group** (metrics): used_bytes, total_bytes, usage_pct, retention_days
- **Configuration group** (properties): model, firmware, host_type, recording_retention_mode
- Note: on UDM Pro, the NVR runs on the same hardware as the gateway.
  On standalone UNVR/UNVR-Pro, it's a separate device. The `host_type`
  property distinguishes them. A future enhancement could add a
  relationship link between NVR and Gateway when they share a MAC.
- Note: Protect API uses the same UniFi OS session cookie — no extra auth

### UniFi Camera
- Source: `/proxy/protect/api/bootstrap` → `cameras[]`
- Identifier: `camera_mac` (camera MAC address)
- Display name: `name` field (e.g., "Front Door", "Garage")
- Parent: NVR
- **Status group** (metrics): uptime_ms (milliseconds!), last_motion_epoch
- **Status group** (properties): state (CONNECTED/DISCONNECTED/UPDATING), is_connected, is_adopted
- **Hardware group** (properties): model, firmware, firmware_build, type, is_wireless
- **Network group** (properties): ip, mac, phy_rate (wired link speed, null if wireless)
- **Recording group** (properties): is_recording, last_ring_epoch
- Note: `uptime` is MILLISECONDS (Protect), not seconds (Network API) — normalize to seconds
- Note: `isWireless` is null on wired cameras (not false) — coerce to "false"
- Note: `wiredConnectionState.phyRate` is null when wireless or disconnected

## Cross-adapter stitching

### Switch Port → ESXi Host (via LLDP)

The `lldp_table[]` on switch ports contains neighbor info including
`lldp_system_name` and `lldp_chassis_id`. ESXi hosts advertise their
hostname via LLDP/CDP.

Transform:
1. Read `port_table[].lldp_table[].lldp_system_name` from each switch port
2. Match against `VMWARE HostSystem` resources by hostname
3. Create parent/child or peer relationship

This gives: click ESXi host → see UniFi switch port → see port health,
errors, PoE. The killer feature.

### Gateway → VMWARE vCenter (optional, v2)

Could stitch gateway WAN metrics to a vCenter object for unified
infrastructure view. Low priority.

## API endpoints (per collection cycle)

| # | Endpoint | Objects fed | Notes |
|---|---|---|---|
| 1 | `POST /api/auth/login` | (session) | On-demand |
| 2 | `GET /api/self/sites` | Site | 1 call |
| 3 | `GET /api/s/{site}/stat/device` | Gateway, Switch, AP + all children | 1 call per site, returns ALL devices |
| 4 | `GET /api/s/{site}/stat/health` | Wireless Aggregate | 1 call per site |
| 5 | `GET /proxy/protect/api/bootstrap` | NVR, Camera | 1 call (same session) |

Total: 4-5 API calls per cycle. Very efficient — one `stat/device` call
returns all network devices with full port/radio/LLDP data.

## Auth flow

1. `POST /api/auth/login` with `{"username":"...","password":"..."}`
2. Response sets `TOKEN` cookie (UniFi OS) or `unifises` cookie (classic controller)
3. All subsequent requests include the cookie
4. Re-auth on 401

## Credential config

| Field | Key | Type |
|---|---|---|
| Host / IP | `host` | string |
| Port | `port` | string (default: 443) |
| Username | `username` | string |
| Password | `password` | string (masked) |
| Site | `site` | string (default: "default") |
| Allow Insecure SSL | `allowInsecure` | string (default: "true") |

## Scope decisions

### In scope (v1)
- All 11 object types above
- LLDP→ESXi stitching
- PoE budget tracking
- Device topology (uplink parent/child via `uplink.uplink_mac`)
- Protect cameras + NVR
- Multi-site discovery

### Deferred (v2)
- Per-SSID objects (from `vap_table[]`)
- Client objects (from `stat/sta`) — unless VM MAC matching proves viable
- Event/alarm ingestion (`rest/alarm`)
- Multi-site (v1 targets single site from connection config)
- Gateway storage metrics
- DPI traffic categories

## Resolved questions

1. **Device topology**: YES — wire topology via `uplink.uplink_mac`.
   Adapts on re-cable (relationships rebuilt every cycle).

2. **Multiple sites**: All sites in one instance. World → Site → Devices.

3. **Gateway temperatures**: Metrics on gateway (temp_cpu, temp_local,
   temp_phy), not separate sensor objects.

4. **NVR placement**: Peer of Gateway under Site. Property notes host
   type (UDM Pro built-in vs standalone UNVR).

## Open questions

1. **Radio throughput join**: radio stats don't include bytes — those live
   in device-level `stat.ap.wifi0-tx_bytes`. Need to map radio code
   (ng/na) → radio name (wifi0/wifi1) via `radio_table[].name`. Extra
   join step — implement in v1 or defer?

2. **NVR-Gateway link**: When the NVR runs on a UDM Pro (same MAC), should
   we add a peer relationship between the NVR and Gateway objects?
   Nice-to-have for topology visualization.
