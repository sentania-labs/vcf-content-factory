# devel (9.0.2) brought current, 2026-10-15

Approval: `approvals/2026-10-15-all-devel-dev-paks.md` (Scott: "we need to
verify funcationality against all 3 versions in devel"; addendum "uninstall
vcommunity vsphere from devel 9.0.2"). Agent: content-installer, API only,
no browser. Times America/Chicago.

| Step | Result |
|---|---|
| vCommunity vSphere uninstall (1:33 to 1:36 PM) | three instances deleted (204 each), pak uninstalled, adapter kind 404, zero resources left |
| Compliance 0.0.0.94 to 0.0.0.95 (1:36 to 1:40 PM) | three instances DATA_RECEIVING, no restart needed; pass_rate mgmt 73.3, wld01 74.3, wld02 75.4; five dashboards imported with widgets (Environment Overview 7, ESX Hosts 6, vCenter and Networking 6, VMs 5, World Summary 7) |
| UniFi 0.0.0.11 to 0.0.0.14 | SKIPPED on purpose: the dist pak's sha256 (47e93b80, the post-review rebuild) no longer matched the brief (afa85e4e). Installed after the Codex-round pak lands. |
| Synology 0.0.0.26 to 0.0.0.31 (1:45 to 1:47 PM) | 32 resources DATA_RECEIVING; the existing instance stores no allowInsecure value (only host and port), so it now validates at the new default and still collects |
| Python fork accounts | devel has a Cloud Proxy (collector 2, 172.27.10.13, UP). `POST /api/collectorgroups` returns HTTP 500 on 9.0.2 for every body shape tried, so no factory-cloud-proxy group; both accounts pinned to collector 2 directly. cpr-devel (ClusterPerfRisk, 13 objects) and vsan-mgmt (VsanHostMetrics, 584 objects, credential vsan-vc-cred) came up STOPPED, started, now DATA_RECEIVING |

Seen but not touched: the stock SupervisorAdapter instance wld01-cl01-supervisor
reads ERROR (Broadcom pak, outside the approval, no baseline for whether it
was already in error).

Open: 9.0.2 collector-group creation through the API fails with 500 (works on
9.1.1); worth a note in the API surface doc if it recurs.

## Afternoon follow-through

- UniFi 0.0.0.14 (merged main cdf0476, sha b7ac9e9b) installed on devel
  2:06 to 2:08 PM; the account stayed DATA_RECEIVING through the upgrade and
  collected at 2:18 PM. Reinstalled on devel_9_1 2:21 to 2:24 PM (same
  version over this morning's build); the account went FAILED, was started at
  2:34 PM per the race lesson, DATA_RECEIVING by 2:39 PM.
- Synology 0.0.0.31 (merged main 804203f, sha 8ea76f21) same-version
  reinstall on both: in progress at the time of writing.
