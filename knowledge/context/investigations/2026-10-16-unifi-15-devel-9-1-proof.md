# UniFi dev pak 0.0.0.15 on devel_9_1: install and proof

Date: 2026-10-16 (all times America/Chicago, CDT). Instance: devel_9_1
(vcf-lab-operations-devel-91, VCF Operations 9.1.1.0 build 25795063).
Approval: knowledge/context/approvals/2026-10-15-all-devel-dev-paks.md.
Account: factory-unifi-b14 (adapter id fa7cf6c6-e67f-4a45-9eee-4c5bf7fee994,
collector 2 = Cloud Proxy 172.27.10.11, group factory-cloud-proxy), kept; no
new account created.

## Verdict

Install and collection PASS. Items 1, 2 (except the Radio probe, which is
answered: absent), 4, 5, 7 PASS. Item 3 PARTIAL (camera key unproven, NVR key
PASS). Item 6 PARTIAL (every negative check clean; the expected positive INFO
line was NOT observed). Item 8 FAIL as written (README menu path is wrong for
9.1.1).

## Install

- Pak: /home/scott/claude/vcf-content-factory/dist/vcfcf_sdk_unifi_controller.0.0.0.15.pak,
  sha256 797f74c40fbac60d2502a97d0ecf515708251e1eb2eba0da04eec65a38bc92cf
  (matches the merged head 6c3c66d per the brief; unifi checkout at 6c3c66d,
  clean). No rebuild needed.
- `python3 -m vcfcf_managementpacks install dist/...0.0.0.15.pak --profile devel_9_1 --skip-ssl-verify`
  11:04:50 AM to 11:07:24 AM. Result: "Install completed and verified: VCF
  Content Factory UniFi Controller 0.0.0.15 (adapterKind='unifi_controller'
  isInstalled=true)". Previous version: 0.0.0.14 (same-line upgrade).
- Baseline before install (11:04 AM): 147 resources, same kinds as below.
- Race lesson reproduced exactly. Collector.log (UTC stamps converted):
  11:06:50 AM ERROR "Unknown adapter type is specified in collector
  configuration. (Type = unifi_controller)"; 11:06:58 AM "Loaded adapter entry
  class com.vcfcf.adapters.unifi.UniFiAdapter ... 'unifi_controller' adapter
  version: 0.0.0.0.0.15". Account read resourceState FAILED at 11:07 AM and
  still at 11:09 AM. `PUT /api/adapters/fa7cf6c6-.../monitoringstate/start`
  at 11:09:30 AM returned 200; first collection 11:09:33 AM; collection every
  5 minutes since (11:14, 11:19, 11:24, 11:29, 11:34, 11:39, 11:44, 11:49 AM).
  All 147 resources resourceState STARTED.

## Checklist

### 1. Account collecting, object count: PASS
147 resources via `GET /api/resources?adapterKind=unifi_controller`, equal to
build 14 (147): SwitchPort 99, Radio 12, Camera 12, Switch 10, AccessPoint 6,
WanInterface 2, WirelessAggregate 1, Gateway 1, Nvr 1, World 1, Site 1,
adapter instance 1. Stats timestamps advance every 5 minutes.

### 2. New keys: PASS (Radio answered: absent)
- Status|state (metric, `stats/latest`) = 1.0 on the Gateway (1 of 1), all 10
  Switches and all 6 APs, stamped 11:14:33 AM and later.
- Status|state_code (property) = "connected" on all 17 of them.
- WanInterface: Traffic|tx_rate and rx_rate present on both (WAN 1: tx 16026,
  rx 42979; WAN 2: 0.0 and 0.0, see item 7).
- SwitchPort: Traffic|tx_rate and rx_rate present on 99 of 99 (e.g. Port 15
  tx 7871120, rx 6705014.5).
- Radio: Traffic|tx_rate and rx_rate are described (defaultMonitored true) but
  ABSENT on 12 of 12 radios; only Traffic|tx_bytes and rx_bytes are present.
  The controller does not appear to send a rate field for radios (adapter
  uses metricIfPresent), so the field stays unproven-as-available. Report as
  "does not appear".

### 3. Renamed keys: PARTIAL
- NVR Configuration|recording_retention_days = 14.0 (property): PASS.
  Configuration|recording_retention_mode = 1209600000 is also there (14 days
  in ms; an odd value for a "mode", noted, not judged).
- Camera Status|seconds_since_last_motion: UNPROVEN. It is in the describe
  (unit Second(s)) but defaultMonitored=false (REFERENCE.md lists it as not
  default-monitored), so the Default Policy does not store it and
  `stats/latest` shows 16 keys per camera without it. Proving it needs a
  policy change to monitor the key, which is outside the approval (global or
  policy settings). Camera Status|state = CONNECTED and is_recording = true on
  12 of 12.

### 4. WAN Traffic|tx_bytes unit: PASS
`GET /api/adapterkinds/unifi_controller/resourcekinds/UniFiWanInterface/statkeys`:
Traffic|tx_bytes and Traffic|rx_bytes unit "bytes". Live values: WAN 1
tx_bytes 119070408704, rx_bytes 558775664640. (UI rendering not viewed.)

### 5. Site properties: PASS
Site "Default": Configuration|version = 10.6.106, timezone = America/Chicago,
device_count = 17, description = Default. Gateways 1 + switches 10 + APs 6 = 17.

### 6. Adapter log: PARTIAL
Source: admin UI Support Logs backend (`POST /ui/supportLogs.action`
getLogTree, getLogFileContents, searchLogFileContents; read-only). Files:
UNIFIED_CLOUD_PROXY / adapters / UniFiAdapter / UniFiAdapter_1358.log and
collector.log. Build 15 window = 11:06:58 AM (jar load) onward.
- "vmnic stitch: read properties of N hosts in M bulk request(s)": NOT
  OBSERVED. Searched both logs for "vmnic stitch", "bulk request", "read
  properties": 0 hits, over the first fetch at 11:09:33 AM and the 15-minute
  refresh cycles after it. What IS logged each cycle: "vmnic->port stitch: 18
  edges (10 hosts, 18 vmnics w/ LLDP, 0 ambiguous, 0 unmatched, 0 conflicted)",
  so the stitch itself works and read 10 hosts. The line is emitted by
  UniFiStitcher.java:238 through componentLogger(UniFiStitcher.class), and no
  line from UniFiStitcher or SuiteApiStitcher (any level) appears for
  instance 1358 in either log, so either component-logger INFO output does not
  reach the instance log or the bulk path did not run. Not determined here.
  This is the one item that needs a follow-up (see below).
- No fallback WARN ("bulk properties read ... failed", "refresh failed",
  "properties fetch failed"): none. PASS.
- No sysinfo WARN: 0 hits for "sysinfo" in collector.log. PASS.
- "skipped with no identity": 0 hits. PASS (count not logged at all, so also
  not above 0).
- Re-login every cycle: no. "UniFi session acquired" appears once in the
  build 15 window (11:09:32 AM, after the start); earlier ones are the
  existing two-hourly refresh. PASS.
- Other WARN/ERROR in the window: one WARN at 11:09:33 AM
  "VcfCfAdapter.openPlatformConnection: FIPS-approved-only mode detected but
  the vendor's useClusterTruststore mirror is not implemented ... (DEF-005
  FIPS branch)", a known notice, once per configure. The 11:06:50 AM ERROR is
  the race above.

### 7. No 0.0 for fields the controller does not send: PASS
All 17 devices are connected, so there is no offline device to spot-check.
Absent-stays-absent holds: Radio rates absent (not 0.0); SwitchPort
PoE|poe_power absent on the 56 ports that are not PoE capable (present on 43,
including 38 reading 0.0 on ports with no PoE draw, which the controller sends
as a string and the adapter parses); Gateway Temperature|temp_phy and WAN
Health|speed absent. WAN 2 reads 0.0 for every traffic and health metric, but
it has no IP, no netmask and Health|availability 0.0, so it is an unplugged
second WAN and the zeros are the controller's. 28 ports report rate 0.0 while
Status|up is false, consistent.
Also absent and not in the checklist: NVR Storage|used_bytes, usage_pct and
total_bytes (described, defaultMonitored true, not present on the NVR). Cause
not investigated.

### 8. README menu path: FAIL as written
README.md lines 11 and 15 say "Administration > Integrations > Repository" and
"Administration > Integrations > Accounts" for 9.x (and "Data Sources >
Integrations ..." for 8.x). The 9.1.1 UI bundle (fetched from /ui/ after an
admin login, read-only) defines the primary nav as a "Data Sources" group
(bundle keys navigation.dataSources.title, children
navigation.dataSources.integrations.title -> route data-sources/integrations
and navigation.dataSources.cloudProxies.title -> data-sources/cloud-proxies),
with Administration (navigation.administration.title) a separate top-level
item. The old routes administration/solutions-cloudaccounts,
-monitoringaccounts and -configure redirect to data-sources/integrations;
Repository and Accounts are tabs at data-sources/integrations/repository and
data-sources/integrations/accounts. So on 9.1.1 the path is Data Sources >
Integrations > Repository / Accounts, not Administration. The English label
text was not read (no browser); the keys and routes are. 9.0.2 was not checked.

## Visual verification
VISUAL VERIFICATION: SKIPPED. The Playwright MCP server failed to connect
("Connection closed") in this session. Everything above is API, Support Logs
backend and UI bundle evidence; no rendered page was viewed.

## Side effects to know about
- My first Support Logs probe left an admin UI session open, and so did two
  later login checks; the instance answered `concurrentSessionDetected` to
  further `admin` UI logins from about 11:17 AM until the sessions aged out
  (11:48 AM). A person logging into the UI as `admin` in that window would
  have hit the same wall or ended up in a forced-login prompt. All sessions
  are now logged out cleanly. No forced login was used.
- No config writes beyond the install and the one monitoringstate/start.
  No policy, log level, or other setting was changed.

## Open items
1. Item 6 stitch line: decide whether UniFiStitcher / SuiteApiStitcher
   component-logger output is supposed to land in the instance log on a Cloud
   Proxy (compare with another pak's componentLogger lines there), or whether
   the bulk path is not taken. Needs the adapter author or tooling.
2. Camera seconds_since_last_motion needs a policy decision to prove.
3. README menu path wording for 9.1.1 (and a 9.0.2 check).
4. NVR Storage|* metrics absent: cause unknown.
5. Radio Traffic|tx_rate / rx_rate: described but never sent; consider
   dropping from describe or documenting it.
6. Lesson addition candidate: the Support Logs UI session leaks on a failed
   probe; log in once per script and always log out.
