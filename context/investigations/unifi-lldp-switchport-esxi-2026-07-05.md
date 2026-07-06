# UniFi switch-port → ESXi-host mapping: where the API exposes it

**Investigator:** api-cartographer
**Target:** `unifi.int.sentania.net` — UDM Pro, UniFi OS 5.0.16, Network App **10.2.105**
**Date:** 2026-07-05 (session cont. 2026-07-06 UTC)
**Auth used:** classic session (`POST /api/auth/login` → TOKEN cookie + x-csrf-token)
for the classic/v2 surfaces; `X-API-KEY` (env `UNIFI_API_KEY`, 32 chars) for the
Integration API. All GET, read-only.
**Raw captures:** `/tmp/unifi-statdevice.json`, `/tmp/unifi-probe.json` (not committed).

## Question
The adapter's LLDP cross-link (per-port `port_table[].lldp_table[].lldp_system_name`)
matches 0 hosts. The switch CLI (`show lldp neighbor` on usw-xg-8-ms) DOES see all
ESXi hosts with SysName = FQDNs. Where does the controller API expose that?

## Bottom line
- **The LLDP sysName/FQDN is NOT exposed by ANY controller API surface.** The switch's
  live LLDP daemon (visible via CLI) is not re-published. `stat/device`'s device-level
  `lldp_table[]` is filtered to UniFi/topology neighbors only; no key named
  `sysName`/`system_name`/`lldp_system_name` appears in any classic, v2, or integration
  response. So a name-based (sysName→HostSystem) join is impossible from the API.
- **Switch-port → ESXi-host IS recoverable, but via wired-client MAC+port, not LLDP.**
  `stat/sta` (classic) and `v2/api/site/{site}/clients/active` map every wired client
  MAC to `sw_mac` (switch MAC) + `sw_port` (port index). The ESXi physical uplink MACs
  (`38:05:25:34:*`) and vmkernel/VM MACs (`00:50:56:*`) appear there against
  `sw_mac=8c:30:66:a2:50:10` (usw-xg-8-ms). The join to VMWARE HostSystem must therefore
  be **MAC-based** (UniFi client MAC ↔ vSphere host vmnic/vmk MAC), not name-based.

## Endpoint-by-endpoint findings

### `GET /proxy/network/api/s/{site}/stat/device` (what the adapter reads today) — INSUFFICIENT
- Per-port `port_table[].lldp_table` key: **absent on all 81 switch ports** (Network App 10.2.105).
- Device-level `lldp_table[]` exists but only lists UniFi/topology neighbors
  (chassis_id = Ubiquiti MACs, mgmt_ips 172.16.0.x). No ESXi, no sysName field. Keys:
  `chassis_id, is_wired, local_port_idx, local_port_name, mgmt_ips, port_id`.

### `GET /proxy/network/api/s/{site}/stat/sta` (classic wired clients) — BEST SURFACE ✅
- Auth: classic session. Envelope `{meta,data[]}`, 134 rows.
- 62 wired clients report `sw_mac=8c:30:66:a2:50:10` (usw-xg-8-ms) with a concrete `sw_port`.
- Fields: `mac`, `is_wired`, `sw_mac`, `sw_port`, `last_uplink_name`, `last_uplink_mac`,
  `last_uplink_remote_port`, `ip`, `network`, `hostname` (null for the ESXi hosts).
- Verbatim (ESXi physical vmnic MACs the CLI LLDP showed on te-ports):
  ```json
  {"mac":"38:05:25:34:df:cc","is_wired":true,"sw_mac":"8c:30:66:a2:50:10","sw_port":3,"ip":"172.27.1.11","network":"VCF 9 Hosts","hostname":null}
  {"mac":"38:05:25:34:e3:19","is_wired":true,"sw_mac":"8c:30:66:a2:50:10","sw_port":7,"ip":"172.27.1.13","network":"VCF 9 Hosts","hostname":null}
  {"mac":"38:05:25:34:de:d0","is_wired":true,"sw_mac":"8c:30:66:a2:50:10","sw_port":5,"ip":"172.27.1.12","network":"VCF 9 Hosts","hostname":null}
  {"mac":"00:50:56:83:32:89","is_wired":true,"sw_mac":"8c:30:66:a2:50:10","sw_port":1,"ip":"172.27.8.164","network":"VCF 9 MGMT VMs","hostname":null}
  ```
- CAVEAT: the ESXi hypervisor hosts carry `hostname=null` (no FQDN). The only FQDN-ish
  hostnames present are NSX **edge nodes** (`vcf-lab-wld01-en01/en02`, `vcf-lab-wld02-*`),
  DHCP-learned VMs, not the esx01-04 hypervisors. So no FQDN for the physical hosts here.

### `GET /proxy/network/v2/api/site/{site}/clients/active` — SAME MAPPING, richer labels
- Auth: classic session. Bare JSON array, 121 rows.
- Fields: `mac`, `sw_port`, `uplink_mac` (= switch MAC), `is_wired`, `display_name`,
  `hostname`, `model_name`. ESXi hosts labeled `"VMWare ESXi xx:xx"` (OUI heuristic +
  MAC tail) — still **not the FQDN**. Same port numbers as `stat/sta`.
  ```json
  {"mac":"00:50:56:83:32:89","display_name":"VMWare ESXi 32:89","is_wired":true,"sw_port":1,"uplink_mac":"8c:30:66:a2:50:10","ip":"172.27.8.164"}
  ```

### `GET /proxy/network/v2/api/site/{site}/topology` — NO LLDP/sysName
- Auth: classic session. Keys `vertices` (149), `edges` (148), `has_unknown_switch`.
- Edges: `{downlinkMac, downlinkPortNumber, uplinkMac, uplinkPortNumber, rateMbps, duplex, networkId, type}`
  — UniFi-device↔UniFi-device topology only; ESXi hosts are CLIENT vertices, not edges.
- Vertices for ESXi = `{"mac":...,"name":"VMWare ESXi xx:xx","type":"CLIENT","unifiDevice":false}`.
  No FQDN, no port, no LLDP. `/v2/.../lldp` and `/v2/.../links` → 404.

### `GET /proxy/network/v2/api/site/{site}/device` — port_table has `lldp_table: null`
- Per-port objects carry stats/PoE only; `lldp_table` is explicitly null. No neighbor data.

### Integration API `GET /proxy/network/integration/v1/...` (X-API-KEY) — COARSER, no port
- Key works (header `X-API-KEY`, case-insensitive). Site id `88f7af54-98f8-306a-a1c7-c9349722b1f6`.
- `/sites/{site}/clients` → wired clients with `uplinkDeviceId` (which device) but **no port index**.
- `/sites/{site}/devices/{id}` → `interfaces.ports[]` is physical state/speed/PoE only
  (`{idx,state,connector,maxSpeedMbps,speedMbps,poe}`) — no connected-client, no neighbor.
- Verdict: Integration API cannot map port→host at all (no port on clients, no neighbor on ports).

## Recommendation for the adapter
Replace the non-functional per-port `lldp_table` read with a **wired-client MAC→port join**
off `stat/sta` (single existing endpoint the MP already can hit, classic session auth):
`stat/sta[?is_wired].{mac, sw_mac, sw_port}` → UniFiSwitchPort keyed `sw_mac + "_" + sw_port`.
Then bind to VMWARE HostSystem by matching the client `mac` against the vSphere host's
physical NIC (vmnic) / vmkernel MAC on the vCenter side — a MAC join, since the UniFi API
never carries the ESXi FQDN for the hypervisor hosts. The LLDP-sysName approach the adapter
was written for is not achievable against Network App 10.2.105's API at all.
