# Synology dev pak 0.0.0.32 on devel_9_1: install and proof

Date: 2026-10-16, all times America/Chicago (CDT). Instance: devel_9_1 (vcf-lab-operations-devel-91,
VCF Operations 9.1.1.0), Cloud Proxy collector 2 (172.27.10.11, group factory-cloud-proxy). Approval:
knowledge/context/approvals/2026-10-15-all-devel-dev-paks.md. Account: factory-synology-b31
(6faae084-ed9b-428e-af7c-1dc6f70c5b3e, adapter instance 1505 in the collector logs, credential
f292fd6e-..., host storage.int.sentania.net:5001, allowInsecure=false), kept, not edited. NAS: DS1520+,
DSM 7.4.1-90080, 4 cores, 20 GB RAM.

## Verdict

Install and collection PASS. Items 1, 2, 3, 5, 8, 9 PASS. Item 4 PARTIAL: the unit and names changed as
built, but the values are DSM's x100 and are not "a few units" (they read 65 to 473 for a real 0.65 to
4.73 on a 4-core NAS). Item 6 PASS for what ran, with three paths NOT EXERCISED (NFS off, datastore
paging, Suite API explicit path). Item 7 PASS for the count (one session from the Cloud Proxy), NOT
CHECKED for the name in DSM (its connection list does not show session names; the name is in the adapter
log). No build 32 regression found. Two findings for the author (load scale, README menu path) below.

## Install

- Pak dist/vcfcf_sdk_synology_diskstation.0.0.0.32.pak, sha256 787a40eb...123ee (matches the brief; no
  rebuild). Previous version 0.0.0.31.
- `python3 -m vcfcf_managementpacks install ... --profile devel_9_1 --skip-ssl-verify`, 3:24:59 PM to
  3:28:03 PM: "Install completed and verified: VCF Content Factory Synology DiskStation 0.0.0.32".
- Race lesson reproduced: account resourceState FAILED, no message, at 3:28:06 PM. collector.log 3:27:11 PM
  ERROR "Unknown adapter type is specified in collector configuration. (Type = synology_diskstation)",
  3:27:21 PM adapter loaded, version 0.0.0.0.0.32. `PUT /api/adapters/{id}/monitoringstate/start` at
  3:28:10 PM returned 200; first collection 3:28:15 to 3:28:19 PM; STARTED, then DATA_RECEIVING and
  GREEN by 3:43 PM.
- Snapshot before install (3:24 PM, build 31): 31 resources, 628 metric keys, 313 property keys, latest
  value per key, saved in the session scratchpad (not committed).

## Checklist

| # | Result | Evidence |
|---|---|---|
| 1 | PASS | Collection at 3:28:19, 3:33:16, 3:38:15, 3:43:15 PM (4 cycles, 5 min). 31 resources before and after, identical per kind: NFS export 16, disk 7, iSCSI LUN 2, pool 1, volume 1, SSD cache 1, world 1, diskstation 1, adapter instance 1. Metric and property key sets per kind identical (0 added, 0 removed). 623 of 628 metric keys have a newer timestamp at 3:44 PM; the other 5 are the HDD `Health|remain_life` keys build 32 stopped publishing (last sample 3:23:53 PM, value 0.0, build 31's fabricated value, still returned by `stats/latest`). Instance `collected_metrics` 151 to 146 (the same 5). |
| 2 | PASS | `Memory|memory_total` 20328568 to 20816453632 (exactly x1024). At 3:38:15 PM Ops `memory_available` = 191033344 and DSM `avail_real` at 3:38:16 PM = 186556 KB (x1024 = 191033344, exact). DSM `total_real` 20328568 KB = 19.4 GiB against 20480 MB installed (ram_size), plausible kernel-visible RAM. `memory_usage_pct` 12 = DSM `real_usage` 12. `memory_cached`, `swap_usage`, `swap_total` exist in describe (unit bytes) but are defaultMonitored=false, so the Default Policy does not store them: UNPROVEN, needs a policy change (outside the approval). |
| 3 | PASS | DSM's `total` row equals the sum of eth0..eth3 exactly (10788309 rx at 3:32 PM), so build 31 summing all rows would read 2x. At 3:38:15 PM Ops `net_rx_bytes` 3511803 and `net_tx_bytes` 612781 equal DSM's total row at 3:38:16 PM (3511803 / 612781). Not zero. A same-instant build 31 comparison is impossible (no build 31 sample at that instant); the proof is the exact match to the single total row. |
| 4 | PARTIAL | Describe: `CPU|cpu_load_1m/5m/15m` names "Load Average (1 min)", "(5 min)", "(15 min)", unit none (was %). PASS as built. Values equal DSM's raw fields exactly (3:38:15 PM Ops 68 / 215 / 158, DSM 68 / 215 / 158), and DSM scales by 100: peak seen 473 / 280 / 138 at 3:33 PM with CPU total load 98 % on a 4-core box means real load 4.73. So the "few units at most" check FAILS until the adapter divides by 100 (the CHANGELOG left this open, "not divided until devel compares"; devel now confirms the x100). No change from build 31 in value, only label and unit. |
| 5 | PASS | Volume 1: `free_bytes` 14165415559168 (was 0), `usage_pct` 50.79 (was 100), `total_bytes` 28788161249280; DSM at 3:32 PM total 28788160495616, used 14622739697664, so free = total - used within live drift, used/total 50.7943 %. Disks: Cache device 1 `remain_life` 77, Cache device 2 78, equal to DSM `remain_life.value` 77 / 78; the 5 SATA HDDs report -1 in DSM and publish nothing (was fabricated 0). iSCSI LUN latency non-zero: `read_latency` 11 / 22 and `write_latency` 18 / 20 at 3:33 PM, 28 / 111 and 19 / 22 at 3:43 PM, tracking DSM's `read_avg_latency` / `write_avg_latency` (DSM at 3:43:19 PM: 0 / 30 and 5 / 23, noisy per-sample, same order). Latency scale (ms or us) still unconfirmed: describe unit is none, DSM's own Resource Monitor was not read. Volume `Cache|cache_read_hit_rate` 84 (DSM hit_rate 84), `cache_write_hit_rate` 99. SSD cache `Hardware|total_capacity` "1863.0 GiB" (was "1863.0 GB"; 2000381018112 / 1024^3 = 1863.0), `Capacity|total_bytes` 2000381018112. Pool: no free key is published; `used_bytes` = `total_bytes` 29987679764480, 100 % (allocation, as designed). The "no 0.0 GiB placeholder" case needs a NAS without cache size data: NOT EXERCISED (this NAS sends all of it). |
| 6 | PASS (partial coverage) | Source: admin UI Support Logs backend (read-only), UNIFIED_CLOUD_PROXY, adapters/SynologyAdapter/SynologyAdapter_1505.log (whole file, 1806 lines, 10-15 12:52 PM to 10-16 3:33 PM) and collector.log lines containing "ynology" (249 lines, to 3:39:51 PM). Zero hits for `principal=`, `token=`, `_sid`, `passwd`, `password=`, `account=`, `username`, `automationAdmin` in either. Build 32 window: one WARN, the known FIPS openPlatformConnection notice (3:28:19 PM, once per configure; build 31 logs it too); no other WARN or ERROR except the install race ERROR above. Build 31 baseline in the same file: 252 WARN on 10-15 (a login-failure episode with the cached-failure back-off lines, "Synology login failed: error code N (no such account or incorrect password)"), 1 WARN on 10-16 (FIPS). "SYNO.API.Info read: every API at its desired version" once per client (3:28:12 PM instance, 3:39:49 PM Test Connection). The Suite API INFO line is "Datastore cross-link: ambient Suite API path (localhost / maintenance user)", identical to build 31's, so the account is on the ambient path and the explicit-path username line is NOT EXERCISED. NFS-off path: NOT EXERCISED, NFS is on (`enable_nfs` true, 16 exports collecting, no "dropped until NFS" line); turning NFS off is a NAS config change outside the approval. Datastore paging: NOT EXERCISED in effect, 12 datastores in one page ("12 datastores loaded, 2 LUN matches, 3 NFS matches" every cycle, as build 31); no paging line at INFO. |
| 7 | PASS (count), NOT CHECKED (name) | DSM `SYNO.Core.CurrentConnection list` (read-only, via the loader helpers) at 3:47 PM: exactly one HTTP/HTTPS session from 172.27.10.11 (the Cloud Proxy), user claude, first login 3:28:15 PM (the build 32 login). DSM shows `descr` "DiskStation Manager" for every session, never the session name, so the name cannot be read there. The adapter log carries it: `session=VCFContentFactory-1505` (instance 1505; build 31 logged `session=VCFContentFactory` three times). Test Connection used `VCFContentFactory-test-4c4958ac` and is absent from DSM's list afterwards (logged out). Other entries are not the Cloud Proxy: 172.27.10.15 (claude, since 10-15 2:30 PM, not identified), 172.27.8.53 (bkdr), SMB and NFS clients, and my own probe. |
| 8 | PASS | `POST /api/adapters/testConnection` (same identifiers and credential id, group a15053eb-...) 3:39:47 PM: 201 with an `adapter-certificates` entry (the NAS certificate, CN=int.sentania.net 2026), same shape as the compliance record. The test ran on the Cloud Proxy: collector.log 3:39:51 PM "Test OK: connected to storage.int.sentania.net (model=DS1520+)". |
| 9 | PASS (rendered) | chrome-devtools-axi on 1600x1000. Screenshots (scratchpad, not committed): p32/nas-summary.png and p32/nas-metrics.png, both viewed 3:36 PM. Inventory object tree: Synology World, Diskstation (DS1520+, health green, Normal 1), 16 NFS exports, 1 pool, 2 LUNs, 1 volume, 1 SSD cache, 7 disks; Summary / Metrics / Logs / Alerts / Topology tabs render. The metric chart itself was not captured: the shared axi bridge was taken over by another session mid-pass (see side effects). |

## Findings for the author

1. Load averages are DSM's x100 (item 4). Suggest dividing by 100 and keeping "Load Average" names; devel
   evidence: DSM 1min_load 68 / 5min 215 / 15min 158 at 3:38:16 PM equal the Ops values, and a CPU 98 % moment
   showed 473 on 4 cores.
2. README and CHANGELOG say the 9.1.1 path is "Data Sources > Integrations > Repository / Accounts"
   (checked live 2026-10-16). In this devel_9_1 UI (3:35 PM, admin, login page `?vcf=1`) the left
   navigation has no "Data Sources" item; Integrations and Cloud Proxies sit under Administration (Administration
   > Configurations, Integrations, Cloud Proxies, SDDC Manager, Control Panel, Global Settings). The unifi
   record found "Data Sources" keys in the UI bundle, so the two may differ by UI mode; unresolved, worth a
   second look before the docs are called verified.
3. HDD `remain_life` last samples (0.0, 3:23:53 PM) stay readable through `stats/latest` after the upgrade; a
   dashboard reading "latest" shows a stale 0 on HDDs until the data ages out. Cosmetic.
4. The adapter instance carried 1 critical alert before the install (`alert_count_critical` 1, health 25 at
   3:24 PM); after the restart it is 0 and health 100. Not investigated.

## Side effects and cleanup status

- Credential exposure by me: while probing the admin UI login over HTTP I printed a redirect `Location`
  header that echoed the form-encoded login (user admin and its password, the devel_9_1 profile) into the
  session transcript, about 3:25 PM. It is a lab devel instance, but treat that password as exposed and
  rotate it at your discretion. Everything after used a path that never prints credentials (password
  redacted from tool output, injected from the loader). Nothing was written to a file or the repo.
- Admin UI sessions: my first browser session was taken over by another user of the shared default
  axi bridge; I logged my session out through a separate tab and a
  login/logout probe succeeded at about 3:38 PM. A second isolated session (CHROME_DEVTOOLS_AXI_SESSION=syn32)
  logged in at about 3:45 PM and was logged out by a fetch to `mainAction=logout` and the browser stopped, yet
  admin UI logins answered `concurrentSessionDetected` from about 3:46 PM through at least 3:48 PM. That may be
  my session not ending or someone else's login; I cannot tell which. No forced login used.
- DSM: five short logins named `proof32-probe` from the workstation (read-only reads), each logged out.
- Ops writes: the install, one `monitoringstate/start`, and one Test Connection POST. No credential, policy,
  log level, or global setting changed; nothing deleted. Support Logs access was read-only.
- Not exercised, need a decision to prove: NFS off (turn NFS off on the NAS), datastore paging (>1000
  datastores), Suite API explicit path (an account with vrops_* fields), `memory_cached` / swap keys (policy
  change), remain_life on a NAS with failing wear, LUN latency scale (read DSM's Resource Monitor).

Source commit for the installed pak: not recorded at proof time. Its sha256 (787a40eb...) differs from the pak the build 32 review record names (ef6b065c...), so the installed build includes the commits that merged after review round 2 (see the review record's closing note).
