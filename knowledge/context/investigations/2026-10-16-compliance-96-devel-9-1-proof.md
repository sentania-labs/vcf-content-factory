# Compliance dev pak 0.0.0.96 on devel_9_1: install and proof

Date: 2026-10-16, all times America/Chicago (CDT). Instance: devel_9_1 (vcf-lab-operations-devel-91,
VCF Operations 9.1.1.0), Cloud Proxy collector 2 (group factory-cloud-proxy). Approval:
knowledge/context/approvals/2026-10-15-all-devel-dev-paks.md. Accounts: compliance-mgmt
(9ff2d09f-c85f-46a4-abd9-461200979f50), compliance-wld01 (4051a2fd-c0f5-415d-a08d-0a5b4bc4def2),
compliance-wld02 (a6fa8ad4-d846-4692-bb1f-cfb0461276de); all three use credential 556a5519-... .

## Verdict

Items 1, 2, 3, 4, 5, 9 PASS. Item 6 PASS with the Suite API line at WARN (not INFO). Item 7 NOT
EXERCISED. Item 8 PASS for rendering, with a note on the legend. Score diff: none (0 of 547 keys).

## Install

- Pak dist/vcfcf_sdk_compliance.0.0.0.96.pak, sha256 4c8b4631...a10a8 (matches the brief; no rebuild).
- `python3 -m vcfcf_managementpacks install ... --profile devel_9_1 --skip-ssl-verify`, 12:47:19 to
  12:50:31. "Install completed and verified: VCF Content Factory Compliance 0.0.0.96". Previous 0.0.0.95.
- Race lesson reproduced: all three accounts resourceState FAILED, no message, at 12:50. `PUT
  /api/adapters/{id}/monitoringstate/start` for each at 12:50:43 returned 200; first collection 12:50:43
  to 12:51:03; STARTED / DATA_RECEIVING since.

## Item 2 first: score diff versus build 95

Snapshot taken 12:46 to 12:48 (build 95), compared at 13:06 (4 cycles) and again at 13:28 (after item 5).
Key names: the brief's `Summary|score` does not exist. Real keys (docs/data-reference.md):
`VCF-CF Compliance|score`, `|total_count` (= controls_evaluated), `|pass_count` (= controls_passed).
Objects: 183 (106 VM, 58 portgroup, 10 host, 3 cluster, 3 DVS, 3 vCenter), 547 keys compared, 0 differences,
at both times. Clusters: only 1 of 3 has a score (the two wld clusters have no score, same as build 95).
3 VMs (w22wg, w25probe, w11-template-test) have their latest sample from 10-15 9:47 AM in both builds
(not collected by either; not a change).

## Checklist

1. PASS. Accounts STARTED and collecting every 5 min. 1548 resources total before and after (identical
   per adapterKind/resourceKind counts); compliance adapter kind 3 account objects + 1 ComplianceWorld.
2. PASS (above).
3. PASS. Rollup|incomplete = 0 on all three vCenters in every normal cycle (12:51, 12:56, 13:01, 13:06, and
   13:11 to 13:36 for mgmt and wld01). All 218 Rollup keys on the vCenters identical to build 95.
   Rollup|Environment (ComplianceWorld, engine computed): pass_rate 75.54296875, scored 178,
   controls_evaluated 3177, controls_passed 2400, non_compliant 142, avg_score 79.7491, unchanged.
4. PASS. Source: admin UI Support Logs backend (read-only getLogFileContents), UNIFIED_CLOUD_PROXY,
   adapters/ComplianceAdapter/ComplianceAdapter_896.log (mgmt), _898 (wld01), _899 (wld02).
   - "Cycle limits: time budget 285 s (95% of the 300 s interval, the collection interval from the
     platform); a cycle also ends after 5 vCenter calls in a row time out": once per account at
     12:50:43 (3 lines). A later reconfigure with the same text does not repeat it (code compares to
     the last logged line, ComplianceAdapter.java:910), so wld02's two reconfigures (item 5) did not log it.
   - Zero hits for "cut by cycle budget", "host not answering", "Stale-control cleanup stopped", "returned
     an empty list", "ENDED EARLY", "Cycle ended early", "cycle abandoned" in normal cycles.
   - Only WARN in normal cycles: the known FIPS openPlatformConnection notice, once per account.
   - Cycle times 15.1 to 22.3 s (build 95: 17 to 25 s). 11 cycles mgmt/wld01, 9 wld02 through 13:41.
   - Stale-control cleanup line every cycle: mgmt 51 objects, wld01 30, wld02 41, each in 5 requests, 0
     Compliant values returned, 0 set to -1, 0 retired keys re-pushed, 0 skipped, 0 carried. Sane for an
     estate with no retired-control keys; identical to build 95's counts (the new fields read 0).
5. PASS. Method: created throwaway credential a50cb119-10a9-45fc-b06a-948628336563 ("proof96-wrongpw-wld02
   (throwaway)", same username as 556a5519-..., random wrong password, never printed) and swapped it onto
   wld02 only with `PUT /api/adapters` (the real credential was never edited, so no password was needed).
   Swap 13:08:20. Failing cycles 13:10:44 to 13:10:50 (5.7 s) and 13:15:44 to 13:15:49 (4.3 s): "Login failed
   (no response / SOAP fault)", one login attempt per cycle, far inside the 285 s budget. Rollup|incomplete =
   1.0 at 13:10:50 and 13:15:49; alert "Compliance data not collected (vCenter)" ACTIVE on the wld02 vCenter
   object (81abc680-d677-4ac3-97aa-6d95c9539df1) from 13:12:35. Restore (original credential id) 13:17:02;
   first cycle after 13:20:45 to 13:21:01 read incomplete 0.0 (recovery in one cycle); alert CANCELED 13:22:35.
   mgmt and wld01 unaffected throughout. Scores equal build 95 afterwards (0 diffs at 13:28).
6. PASS, WARN on the Suite API line. `POST /api/adapters/testConnection` with compliance-mgmt's identifiers
   and credential id (collector group a15053eb-...), run 4 times 12:53 to 12:55. The API answers 201 with
   an `adapter-certificates` entry and a temporary id that 404s at once; `PATCH /api/adapters/testConnection`
   cannot accept it (404). The test itself still ran on the Cloud Proxy: collector.log 12:53:53 PM
   "Test OK: connected to vcf-lab-vcenter-mgmt.int.sentania.net (REST and vSphere SOAP), 6 host(s) visible".
   Suite API check logged at WARN: "Test Connection: the local VCF Operations Suite API did not answer from
   where this test ran (Suite401Exception: ... /api/auth/token/acquire returned 401 ... mechanism=ambient
   principal=automationAdmin) ... The test still passes". Preceded by ERROR "Crypt.decrypt_impl_v2: Error
   finalising cipher data: pad block corrupted" (the ambient automation credential on the Cloud Proxy). Collection
   pushes work, so this is test-path only. Worth a look by the adapter author: INFO was expected on a healthy
   path, and the 401 is real on a Cloud Proxy.
7. NOT EXERCISED. Every cleanup read returned 0 Compliant values on all objects in all cycles, so no object
   holds a key outside its SCG, and nothing carries a retired control to cancel.
8. PASS (rendered). Browser: chrome-devtools-axi with --ignore-certificate-errors (Playwright MCP failed to
   connect). Screenshots (scratchpad, not committed): p96/esx-hosts.png, p96/env-overview.png, viewed 14:04.
   ESX Hosts: 10 hosts, scores 64.58 to 72.92 match the API; Not Read 0; heatmap tiles all yellow, legend
   0 to 80 yellow, 80 to 95 green, 95+ black, so yellow is correct for every score below 80. Environment
   Overview: 75.5% controls passing, 142 non-compliant, 0 without benchmark, 178 scored, per-vCenter
   73.33 / 79.04 / 75.35, totals 2,400 / 3,177 (match the API). "Objects by SCG" shows 63 / 62 / 55 (180) while
   Rollup scored is 63 / 61 / 54 (178); not a build 96 change (unexamined here).
9. PASS. `GET /api/resources/43d35e7b-e07c-4848-9fca-b08b7df4ab2c/stats/latest?maxSamples=5` (VM) returns 5
   samples per key with timestamps (12:33:02, 12:38:03, 12:43:01, 12:48:06 build 95; 12:50:57 build 96).
   The log does not print the samples; the cleanup line shows 5 requests per cycle.

## Side effects and cleanup status

- Throwaway credential a50cb119-10a9-45fc-b06a-948628336563 still exists (no delete without instruction).
  wld02 is back on 556a5519-... (verified by GET).
- Admin UI sessions: my browser attempts left orphaned sessions twice (a failed deep link drops the browser
  cookie so the logout never reaches the server). `concurrentSessionDetected` blocked `admin` UI logins from
  about 13:28 to 13:44 and 13:46 to 14:00 (they age out in about 15 min). No forced login used. Final state:
  logged out cleanly, verified by a login/logout probe at 14:04. Working dashboard route on 9.1.1 after login
  and /ui/index.action: /vcf-operations/ui/operate/dashboards/dashboards;tabId=<dashboard id>.
- No policy, log level or global setting changed.
