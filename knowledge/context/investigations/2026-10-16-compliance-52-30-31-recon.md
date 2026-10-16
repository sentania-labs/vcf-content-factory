# Compliance issues #52, #30, #31: live recon on devel_9_1

Date: 2026-10-16, run 10:12 to 10:35 AM Central. Read-only (GET only). Profile
`devel_9_1` (VCF Operations 9.1.1, compliance pak 0.0.0.95, three vCenters,
collector is the Cloud Proxy). Instance resource ids used:
vCenters: vcf-lab-mgmt 752b566a, vcf-lab-wld02 81abc680, vcf-lab-wld01 81c75ece.
Clusters: vcf-lab-mgmt-cl01 a24c8d6b, vcf-lab-wld01-cl01 5fb4cf05, vcf-lab-wld02-cl01 22edbeae.

## Verdicts

- **#52: NOT REPRODUCED, and the symptom as described is the steady state for the two wld clusters, not an intermittent load failure.** The Suite API returned 3 of 3 clusters on every one of 31 queries. In 43.5 hours of stats history no cycle shows `Rollup|Cluster|unmatched` above 0 or `Rollup|incomplete` = 1, which is what a zero-cluster or held-back load would produce. wld01 and wld02 clusters read 0 evaluated and have no score in every cycle since 10-14 2:45 PM, because they are not vSAN and the only automatable cluster control in SCG 9.1 (`cluster.managed-disk-claim`) is vSAN only. The adapter log was not reachable without SSH, so the per-kind load line is unverified (INFERRED from the stats).
- **#30: the data is present and matches the widget's filter. There is no view with a Compliant=0 filter behind this panel; it is an AlertList widget (type 15_21, criticality 2,3,4, depth 1 on hosts and VMs).** Host and VM objects with failing controls carry one active 15/21 alert per failing control, on the object itself. Filter wrong: no. Data absent: no. Whether the binding delivers the selected row to the widget cannot be proven from the API (no browser pass, dashboards have no read endpoint). Needs one UI look on 0.0.0.95.
- **#31: alerts are active (716 ACTIVE pak alerts on 128 objects) and the widget filter (15_21, criticality 2,3,4, status all, depth 4) matches every one of them, and every alerted object is within depth 4 of its vCenter.** Filter wrong: no. Data absent: no. Same caveat as #30: rendering needs one UI look.

## #52 evidence

### a. Stitcher query and repeat runs

Stitcher query (ComplianceStitcher.java `fetchResources`, lines 291 to 345):
`GET /api/resources?adapterKind=VMWARE&resourceKind=ClusterComputeResource&pageSize=10000&page=0`
(`ComplianceDecisions.RESOURCE_PAGE_SIZE = 10000`; pages until pageInfo.totalCount rows are read; an unparseable body, a page with no resourceList and totalCount not 0, or a short list marks the kind failed and logs `fetchResources(<kind>) incomplete: ... this kind is held back this cycle`). A totalCount of 0 with an empty list would be COMPLETE with 0 rows, so every cluster would be counted unmatched, not held back (INFERRED from the code comment and the rollup description in data-reference.md; I did not read ComplianceDecisions.resourcePageOutcome).
The "smaller pageSize DEF-023 uses": no different value found in the stitcher (only 10000). I also ran pageSize=1000 as a comparison.

Run 1 (10:14:37 to 10:16:37 AM, 20 s apart, 8 queries): every one totalCount 3, returned 3.
Run 2 (23 queries, 20 s apart, 10:17:11 to 10:20:53 AM; 15 at pageSize 10000, 8 at 1000):
    10:17:11 pageSize 10000 totalCount 3 returned 3
    10:17:12 pageSize 1000 totalCount 3 returned 3
    10:17:32 pageSize 10000 totalCount 3 returned 3
    10:17:52 pageSize 10000 totalCount 3 returned 3
    10:17:52 pageSize 1000 totalCount 3 returned 3
    10:18:12 pageSize 10000 totalCount 3 returned 3
    10:18:32 pageSize 10000 totalCount 3 returned 3
    10:18:32 pageSize 1000 totalCount 3 returned 3
    10:18:52 pageSize 10000 totalCount 3 returned 3
    10:19:12 pageSize 10000 totalCount 3 returned 3
    10:19:12 pageSize 1000 totalCount 3 returned 3
    10:19:32 pageSize 10000 totalCount 3 returned 3
    10:19:52 pageSize 10000 totalCount 3 returned 3
    10:19:52 pageSize 1000 totalCount 3 returned 3
    10:20:12 pageSize 10000 totalCount 3 returned 3
    10:20:32 pageSize 10000 totalCount 3 returned 3
    10:20:33 pageSize 1000 totalCount 3 returned 3
    10:20:53 pageSize 10000 totalCount 3 returned 3
    10:21:13 pageSize 10000 totalCount 3 returned 3
    10:21:13 pageSize 1000 totalCount 3 returned 3
    10:21:33 pageSize 10000 totalCount 3 returned 3
    10:21:53 pageSize 10000 totalCount 3 returned 3
    10:21:53 pageSize 1000 totalCount 3 returned 3

Result: 31 of 31 queries, totalCount 3, returned 3. No empty page seen.

### b. Stats history (5 minute cycles, 10-14 2:45 PM to 10-16 10:13 AM, about 43.5 hours)

History starts 10-14 2:45 PM, when 0.0.0.94 was first collecting; there is nothing older to read. Keys read on each vCenter object: `VCF-CF Compliance|Rollup|Cluster|{scored,unmatched,no_benchmark,non_compliant,controls_evaluated,controls_passed}`, `Rollup|incomplete`, `Rollup|Host|{scored,unmatched}`, `Rollup|VM|unmatched`. Keys read on each cluster object: `VCF-CF Compliance|{score,total_count,pass_count,fail_count}`.

| vCenter | Cluster scored | Cluster unmatched | incomplete | Cluster controls_evaluated | Host scored |
|---|---|---|---|---|---|
| vcf-lab-mgmt | 1 in 521 of 521 cycles | 0 in 521 of 521 | 0 in 521 of 521 | 1 in all 488 pushed (key starts 10-14 5:35 PM, build 95) | 6 in all |
| vcf-lab-wld01 | 0 in 520 of 520 | 0 in 520 of 520 | 0 in 520 of 520 | 0 in all 488 pushed | 2 in all |
| vcf-lab-wld02 | 0 in 520 of 520 | 0 in 520 of 520 | 0 in 520 of 520 | 0 in all 488 pushed | 2 in all |

- Cycles where a cluster read 0 evaluated: every cycle for wld01 and wld02 (constant, not intermittent). Unmatched and incomplete in those cycles: 0 and 0. No cycle on any vCenter has unmatched above 0 or incomplete = 1.
- The cycles named in the issue, all read directly: mgmt Cluster scored 1, unmatched 0, incomplete 0 at 3:35, 3:40, 3:50, 5:35 and 5:45 PM on 10-14. wld01 scored 0, unmatched 0, incomplete 0 at 3:36, 3:41, 3:51, 5:35, 5:45 PM; wld02 same at 5:35 and 5:45 PM.
- Only gap: 10-14 5:21 to 5:35 PM (about 10 to 14 minutes with no points on any series), the 0.0.0.94 to 0.0.0.95 upgrade window.
- Cluster objects now (10-16 10:13 AM): vcf-lab-mgmt-cl01 score 100, total_count 1, pass 1, fail 0, has per-control key `cluster.managed-disk-claim|Compliant` = 1, profile_name VMware_SCG_9.1. wld01-cl01 and wld02-cl01: total_count 0, pass 0, fail 0, no score key, no per-control keys, profile_name VMware_SCG_9.1, no_benchmark 0, has_unreadable 0, collection_failed 0.
- Why 0 evaluated by design: `GET /api/resources/{id}/properties` shows `configuration|vsanEnabled = Enabled` on mgmt-cl01 only; the two wld clusters have no vSAN properties and only HostSystem and ResourcePool children (mgmt-cl01 has VirtualSANDCCluster and Vsan* children). In `profiles/canonical/scg_9.1.csv` the only ClusterComputeResource control with a `vim_property` read recipe that the pak can evaluate is `cluster.managed-disk-claim` (`vsanConfig.autoClaimStorage`); the rest are manual_audit or powercli_only. So a non-vSAN cluster has no scored control and cannot get a score. The mgmt cluster always shows 1 evaluated.
- Matching proof the clusters were loaded every cycle: wld clusters were matched (they carry freshly pushed total_count/pass/fail values with timestamps 10:13:03 and 10:13:04 AM today), which a zero-cluster load could not do.

### c. Adapter log

No Suite API path to read an adapter log. The public spec (`reference/docs/operations-api-9.1.json`) has only `/api/logs/configuration/{logtype}` (log levels), `/api/logs/forwarding*` and `/api/logs/queryconfigs`; `GET /api/logs` returns 404. Internal spec: `/internal/log-collection/status` (400, wants componentType), `/internal/cloudproxies/{id}/logassist/*` (enable/disable log assist, not a read). The known no-SSH read path is the admin UI Support Logs browser (`knowledge/lessons/remote-collector-upgrade-start-race.md`), which needs a browser session, and the 8.18 note in `2026-10-15-devel-8-18-recon.md` says the Cloud Proxy log needs a support bundle or SSH. Stopped at a and b as instructed. Also, 10-14 log lines are likely rotated.

### Verdict reasoning

Not an empty page (31 of 31 full pages) and not a failed page treated as zero (no cycle with unmatched above 0 or incomplete = 1 in 43.5 hours, on any vCenter). The observed symptom (wld01 and wld02 clusters with no score and 0 evaluated) is constant since collection began, and is explained by non-vSAN clusters having no evaluable control. If a true zero-cluster cycle happens, it is not in the retained history and would have shown as unmatched above 0, incomplete = 1, or the mgmt cluster dropping to scored 0. Suggested follow-up (not done): reword the cluster row so a non-vSAN cluster reads "no applicable controls" rather than blank, and consider closing #52 as not reproducible.

## #30 evidence

Widget: `dashboards/compliance-esxi-hosts.yaml` W4 `failing_controls`, type **AlertList** (not a View), title "Failing Controls on Selected Host", `criticality: [2,3,4]`, `mode: all`, `depth: 1`, `alert_types: ["15_21"]`, no status, state, impact or alert-definition pin. Driven by `host_compliance_view` via a `resourceId` interaction. VMs (`compliance-vms.yaml`, "Failing Controls on Selected VM") is the same with depth 1. vCenter & Networking (`compliance-vcenter-networking.yaml`, "Failing Controls on Selected Object") is the same with depth 4. The issue's hypotheses (a Compliant=0 filter, an instanced-metric binding) do not apply to the current YAML. Build 88 moved all of them to the 15_21 alert filter (`knowledge/context/reviews/compliance-open-issues-triage-2026-10-14.md` row 30: "likely fixed, never seen working on devel"). The issue was filed against build 79.

Alert definitions: 144 pak definitions found by name prefix `VCF Content Factory Compliance Alert` via `GET /api/alertdefinitions` (1322 total on the instance), all type 15, subType 21 (88 HostSystem, 24 VirtualMachine, 17 VMwareAdapter Instance, 8 DistributedVirtualPortgroup, 5 VmwareDistributedVirtualSwitch, 2 ClusterComputeResource).

Per-object check, `GET /api/resources/{id}/stats/latest` (control keys shaped `VCF-CF Compliance|<control_id>|Compliant`, value 0 = failing, flat metric, not instanced) against `GET /api/alerts?activeOnly=true` (10-16 about 10:25 AM):

| Object | Compliant=0 keys | Compliant=1 | Active pak alerts on the object | Failing controls without an active alert |
|---|---|---|---|---|
| vcf-lab-mgmt-esx01 (HostSystem) | 17 (fail_count 17, total 48, score 64.58) | 31 | 18 (12 CRITICAL, 2 IMMEDIATE, 4 WARNING) = 17 per-control + `compliance_score_degraded` | none |
| vcf-lab-mgmt-esx02 | 17 | 31 | 18 (same split) | none |
| vcf-lab-wld01-esx01 | 13 (score 72.92) | 35 | 14 (12 CRITICAL, 2 IMMEDIATE) = 13 + score_degraded | none |
| VM `ca` | 6 (total 22, score 72.73) | 16 | 6 (4 CRITICAL, 2 IMMEDIATE) | none |

So per-control alerts exist one for one with the failing keys, raised on the host or VM itself (depth 0), type "15", subType "21", severities WARNING, IMMEDIATE, CRITICAL (levels 2, 3, 4 by the widget's convention, INFERRED from `knowledge/context/api-surface/widget_types_survey.md`). The filter `15_21` plus criticality 2,3,4 admits all of them.
Side note: VM `w22wg` has 5 failing keys but only CANCELED alerts; the VM is `NOT_EXISTING` (deleted, GREY), its last stat is from 10-15 9:47 AM. Stale data, not a defect.

Not provable from the API: whether the interaction delivers the selected row to the AlertList and whether depth 1 on a selected host includes the host's own alerts in the widget (all alerts are on the host itself). The dashboards have no read endpoint (`/api/dashboards`, `/internal/dashboards` both 404), so the installed widget config was not read; the YAML above is what was authored (installed config unverified). One browser pass on 0.0.0.95 closes it.

## #31 evidence

Widget: `dashboards/compliance-environment-overview.yaml` `open_compliance_alerts`, AlertList, `criticality [2,3,4]`, `mode: all`, `depth: 4`, `alert_types ["15_21"]`, driven by `vcenter_object_type_view` (View "Compliance by vCenter and Object Type", subject VMWARE VMwareAdapter Instance, `select_first_row: true`) via `resourceId`.

`GET /api/alerts?activeOnly=true` (10-16 about 10:23 AM): 969 alerts total on the instance, of which 732 are from the pak's 144 definitions: 716 status ACTIVE, 16 status CANCELED (the activeOnly list still includes canceled ones). By level: 455 CRITICAL, 226 IMMEDIATE, 51 WARNING (these counts include the 16 canceled). All have type "15", subType "21". The other 237 are other products' alerts. Active alerts sit on 128 objects: VirtualMachine 524 alerts, HostSystem 162, DistributedVirtualPortgroup 21, VMwareAdapter Instance 6, VmwareDistributedVirtualSwitch 3.
Reachability from the selected vCenter, by BFS over `GET /api/resources/{id}/relationships?relationshipType=CHILD`: every alerted object is within depth 4 of its own vCenter (vCenter itself depth 0, port group, vDS and some hosts depth 2, hosts and most VMs depth 3, 22 wld01 VMs depth 4; the wld01 tree runs to depth 6 for other children, none carrying alerts). Depth 4 therefore covers all of them.
Tile cross-check: `Rollup|All|non_compliant` summed now is 56 (mgmt) + 48 (wld02) + 38 (wld01) = 142 (the issue saw 126 on 9-25).

Data present, filter matches. Again not provable without a browser: that the widget renders it. Both #30 and #31 were filed at build 79 against a config that build 88 replaced.

## Not done

No browser pass, no SSH, no adapter log, no write of any kind. Scratch scripts are in the session scratchpad, not the repo.
