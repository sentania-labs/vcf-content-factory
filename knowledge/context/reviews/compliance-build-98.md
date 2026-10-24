# Compliance build 98 install proof (devel, devel_9_1, devel_8_18)

- **Operator:** content-installer. **Date:** 2026-10-24, America/Chicago (CDT), 12:52 AM to 1:30 AM.
- **Pak:** vcfcf_sdk_compliance.0.0.0.98.pak, sha256 cba3927be628281cbad0d564f183e58c101c0d11e7344a63297bd679d661b71b (matches the brief).
- **Authorization:** knowledge/context/approvals/2026-10-15-all-devel-dev-paks.md ("we need to verify funcationality against all 3 versions in devel"). Devel only; prod not touched.
- **Installer:** worktree fix-installer-200-244-242-shims-159, PYTHONPATH=src, `--profile <p> --skip-ssl-verify`. The worktree had no .env, so a symlink to the main checkout .env was created in it (gitignored; never read).

## Verdict

| Instance | Install | Summary rebind (#200) | Materialization (#244) | Collecting | Overall |
|---|---|---|---|---|---|
| devel 9.0.2 | installed, exit 3 | FAILED (server Internal Server Error), copy still loading | OK 5 of 5 | yes | NOT PROVEN, #200 repair does not work |
| devel_9_1 9.1.1 | installed, exit 0 | not needed, installer copy finished | OK 5 of 5 | NO, collector down since 10-18 | install PASS, collection not provable |
| devel_8_18 8.18.7 | installed, exit 3 | FAILED (same error), copy still loading | OK 5 of 5 | yes, after a manual monitoring start | NOT PROVEN, same #200 failure as 9.0.2 |

## Per-instance record

| | devel | devel_9_1 | devel_8_18 |
|---|---|---|---|
| Previous version | 0.0.0.95 | 0.0.0.96 | 0.0.0.96 |
| Install window (local) | 12:52:45 to 12:57:38 AM | 12:58:01 AM to 1:11:09 AM | 1:11:22 to 1:16:55 AM |
| Exit code | 3 | 0 | 3 |
| Installed version read back (/api/solutions) | 0.0.0.98 | 0.0.0.98 (installer line) | 0.0.0.98 |
| Summary copy before install | "Compliance World Summary 6", isLoading true, 7 of 7 widgets loading | "... 3", finished (7 of 7 false) | "... 1", isLoading true, 7 of 7 loading |
| Summary copy after install | "... 7" 45dd9218-0c2d-4c1e-9dcd-46a81534ea0e, isLoading true, 7 of 7 loading (still, at 1:30 AM) | "... 4" a5078a7a-4539-4a09-ae0d-da3a29429c03, isLoading false, 7 of 7 finished | "... 2" 2c51c9c6-7ff4-4f00-a1fc-104477686ba1, isLoading true, 7 of 7 loading (still, at 1:30 AM) |
| Previous Summary copy left behind | "... 6" 1680c6bc-51da-4947-9aa8-7a00a25f558a, still exists, loading | "... 3" 9deb9705-14bc-46b5-b3af-f20419a5e2a1, still exists, finished | "... 1" 8b64ddb0-67ae-47a5-876a-def1edb713aa, still exists, loading |
| vCenter kind (VMWARE:VMwareAdapter Instance) Summary | getSummaryTabId {} (built-in page, not bound by this pak) | {isDashboard: false} (same) | {} (same) |
| Adapter instances | 3 of 3 STARTED / DATA_RECEIVING, GREEN, cycles 12.9 to 16.9 s, last 1:25 AM | 3 of 3 STARTED / COLLECTOR_DOWN, GREY, last sample 10-18 10:15 PM | 1 instance STARTED / DATA_RECEIVING, GREEN, cycle 11.6 s at 1:29 AM |

## Verbatim installer lines

**devel (exit 3):**

    OK: Install completed and verified: VCF Content Factory Compliance 0.0.0.98 (adapterKind='vcfcf_compliance' isInstalled=true version='0.0.0.98')
    MATERIALIZATION OK: 5 of 5 dashboard(s) finished building
    WARNING: SUMMARY UNCHECKED: vcfcf_compliance:ComplianceWorld: could not check or repair the Summary tab for '[VCF Content Factory] Compliance World Summary': associateResourceKindDashboards failed: '\n   \n      \n      \n   \n\n   <script type="text/javascript">\n      Ext.onReady(function() {\n\n         Ext.QuickTips.init();\n\n         var errorPanel = new Ext.Panel({\n            region: \'center\',\n     '

No MATERIALIZATION WAIT line (all five dashboards were already finished at the first read). No SUMMARY OK or SUMMARY REBOUND line.

**devel_9_1 (exit 0):**

    OK: Install completed and verified: VCF Content Factory Compliance 0.0.0.98 (adapterKind='vcfcf_compliance' isInstalled=true version='0.0.0.98')
    MATERIALIZATION WAIT: 4 dashboard(s) still building; re-checking every 30 s for up to 660 s
    MATERIALIZATION OK: 5 of 5 dashboard(s) finished building
    SUMMARY OK: vcfcf_compliance:ComplianceWorld shows a finished copy of '[VCF Content Factory] Compliance World Summary' (a5078a7a-4539-4a09-ae0d-da3a29429c03)

**devel_8_18 (exit 3):**

    OK: Install completed and verified: VCF Content Factory Compliance 0.0.0.98 (adapterKind='vcfcf_compliance' isInstalled=true version='0.0.0.98')
    MATERIALIZATION WAIT: 5 dashboard(s) still building; re-checking every 30 s for up to 660 s
    MATERIALIZATION OK: 5 of 5 dashboard(s) finished building
    WARNING: SUMMARY UNCHECKED: vcfcf_compliance:ComplianceWorld: could not check or repair the Summary tab for '[VCF Content Factory] Compliance World Summary': associateResourceKindDashboards failed: (identical HTML error-panel text as devel)

## Findings that did not go as expected

1. **The #200 rebind does not work on 9.0.2 or 8.18.7.** The repair step reached the finished source dashboard (4e2c777e-9c6c-4c6a-bc16-ab55b6110f33, isLoading false) and called associateResourceKindDashboards. Both instances answered HTTP 200 with the generic error panel, message "Internal Server Error". A repeat of the exact call by hand on devel (1:19 AM region, one attempt) gave the same body and left getSummaryTabId unchanged (45dd9218...), so nothing was written. The Summary tab on both still shows the installer's unfinished copy, which is the state #200 set out to fix. 9.1.1 never needed the repair. Cause not determined: server logs were not reachable (the Support Logs backend rejected my getLogTree parameters; no SSH path is documented for devel). The 9.0.2 and 8.18 failure shapes match, so it is probably the server action itself on pre-9.1 builds, not the CLI. Needs tooling plus a log read.
2. **Exit 3 is the correct code here.** The pak installed; no reinstall was done on either instance.
3. **Old Summary copies are not removed.** The pak installer leaves the previous copy on every install (devel has 6 and 7, 9.1 has 3 and 4, 8.18 has 1 and 2). This is the documented orphan behaviour, and the old ones on devel and 8.18 are loading, not blank-and-new. No new blank orphan came from the rebind, because the rebind never wrote.
4. **devel_9_1 is not collecting, for a reason older than this install.** Collector "vcf-lab-operations-devel-91-collector" (172.27.10.11) reports DOWN, last heartbeat 10-18 10:20 PM. All three accounts show COLLECTOR_DOWN with their last sample at 10:15 PM that day. Build 98 on 9.1 is therefore installed and materialized but unexercised. Not remediated (outside the standing scope).
5. **devel_8_18 landed in resourceState FAILED with an empty message after the install**, the known post-install race. One PUT /api/adapters/dc959326-d14a-4906-9b4c-ffdf6bf71e67/monitoringstate/start at 1:18 AM returned 200; DATA_RECEIVING and a 11.6 s cycle at 1:29 AM. devel did not need it.
6. **Instance log tails were not read.** No documented log path for devel; the Support Logs call failed. WARN/ERROR content of the instance logs is UNKNOWN, not clean. Status, health and cycle time come from the Suite API only.
7. The pak binds only ComplianceWorld. There is no vCenter Summary binding, so the vCenter row in the brief is the built-in page on all three.

## On-screen check (build 97 review warning 4), devel 9.0.2

Browser: chrome-devtools-axi with --ignore-certificate-errors. The lab session was not signed in; I logged in as the profile admin user with the password taken from the env profile (never printed) and stopped the browser afterwards. Dashboard route: /vcf-operations/ui/operations/dashboards/dashboards;tabId=155743b0-15e0-40e4-acd3-05f68f8684d4 (the "operate" path sends you to Home).

- **Loads and renders:** Environment Compliance 74.8 percent, 142 non-compliant, 178 scored, three vCenter rows, trend, alert list. Open Compliance Alerts is grouped by alert definition with LOAD MORE (6 groups per click).
- **Does the list show every compliance alert on load with no vCenter selected? NO, not reliably.** Load 1 (1:2x AM): 28 groups, 636 alerts after clicking LOAD MORE to the end. Load 2 (1:28 AM): 34 groups, 708 alerts. API at 1:28 AM: 36 active definitions, 721 active alerts. Definitions never listed in either load but present in the API: vm.deactivate-non-essential-3d-features (14), dvpg.network-vgt (8), esx.account-lockout-max-attempts (1), vm.log-enable (1). With vCenter wld01 selected, 3d-features (14) and network-vgt (4) do appear, so the unselected list drops groups that exist. Counts per group also differ from the API (vm.vmotion-encrypted 84 in the UI against 92 in the API). Alert state was moving between reads, so exact equality is not expected, but a missing definition across two loads is a defect, not skew. Cause not determined (widget row cap is the first suspect).
- **Does it narrow when a vCenter row is clicked? YES.** Clicking a score cell of the vcf-lab-wld01 row changed the list to 31 groups, 147 alerts (per-definition counts of 1 to 14). Clicking the vCenter name instead navigates to that vCenter's Inventory Summary page; the interaction is on the other cells.
- **vCenter Summary tab (vcf-lab-mgmt, resourceId 5aa31ee3-39f2-4239-bf4f-840eb0bdc99d):** built-in page renders (counts, alerts, capacity tables), no compliance widget, as expected.

Screenshots (scratchpad, not committed):
- /tmp/claude-1004/-home-scott-claude-vcf-content-factory/6083a17c-1ec3-4253-80c9-c0d2d1bedd55/scratchpad/p98/shots/envoverview-devel-initial.png (on load, first 6 groups)
- /tmp/claude-1004/-home-scott-claude-vcf-content-factory/6083a17c-1ec3-4253-80c9-c0d2d1bedd55/scratchpad/p98/shots/envoverview-devel-all-loaded-no-vcenter.png (load 1, all 28 groups loaded, nothing selected)
- /tmp/claude-1004/-home-scott-claude-vcf-content-factory/6083a17c-1ec3-4253-80c9-c0d2d1bedd55/scratchpad/p98/shots/envoverview-devel-all-loaded-second-load.png (load 2, 34 groups)
- /tmp/claude-1004/-home-scott-claude-vcf-content-factory/6083a17c-1ec3-4253-80c9-c0d2d1bedd55/scratchpad/p98/shots/envoverview-devel-wld01-selected.png (vcf-lab-wld01 row selected, narrowed)
- /tmp/claude-1004/-home-scott-claude-vcf-content-factory/6083a17c-1ec3-4253-80c9-c0d2d1bedd55/scratchpad/p98/shots/vcenter-summary-devel-mgmt.png (vCenter Summary tab)

Not screenshotted: the ComplianceWorld Summary tab on devel (its copy is unfinished per the API).

## Housekeeping

- No credentials, policy, log level or global setting changed. One monitoring start on devel_8_18 (finding 5). One failed manual rebind call on devel (finding 1).
- Orphan Summary copies and the .env symlink in the worktree (gitignored) remain. Saved read-back scripts and raw snapshots: /tmp/claude-1004/-home-scott-claude-vcf-content-factory/6083a17c-1ec3-4253-80c9-c0d2d1bedd55/scratchpad/p98/ (scratchpad).
