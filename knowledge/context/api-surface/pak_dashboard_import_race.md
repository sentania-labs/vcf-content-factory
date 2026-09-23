# Pak install: a bundled dashboard is created, then silently lost (compliance build 67, ESXi Hosts)

Investigated 2026-09-23 on `devel` (VCF Operations 9.0.x,
`vcf-lab-operations-devel`). **Posture: read-only.** Getting evidence
took `getDashboardList` + `getWidgetConfigs` (UI Struts, read), reading
the pak on local disk, and `grep` over appliance logs via SSH (evidence
only, nothing changed on the host). No import, no delete, no edit.

> **UNSUPPORTED ENDPOINTS.** `POST /ui/dashboard.action`
> (`getDashboardList`, `getWidgetConfigs`) is the Struts UI layer and
> has no back-compat promise. Neither `operations-api.json` nor
> `internal-api.json` documents the pak-content dashboard importer, its
> `ForceByName` mode, or `importComplete`/`entryKeys` (both specs
> grepped: they list only `/api/solutions*` and
> `/internal/solutions/preinstalled*`). Pak install itself goes through
> `/suite-api/internal/solution/install`, which needs
> `X-Ops-API-use-unsupported: true`.

## The answer

**The ESXi Hosts dashboard was created, and then lost about 5 seconds
later, with no delete.** Its content was not rejected. The Heatmap and
every other field fall inside the known-good pak-installed shape (see
§Content is exonerated). The loss lines up to the second with a
background dashboard materializer pass (`DashboardImporter`, the
phase-2 worker in
`dashboard_import_two_phase_materialization.md`). That pass started
**during** the ESXi import and saved another dashboard right after the
ESXi import finished. **Most likely cause (inference): a lost-update race
between the pak's sequential dashboard import and the concurrent
phase-2 pass.** The pass read state before ESXi Hosts committed, then
wrote it back, and the ESXi record was dropped.

No wire change fixes this. It is a platform timing defect. Neither the
dashboard YAML (`dashboard-author`) nor the renderer (`tooling`) is at
fault.

## Evidence (observed)

All times are America/Chicago (CDT) on 2026-09-23. The raw log stamps
are UTC; the conversion is +5 h.

**1. Install and import order.** From the `analytics.audit-*.log`
entries on the solution-manager thread (`threadId="78483"`, user
`maintenanceAdmin`):

| CDT | Audit event |
|---|---|
| 11:46:07 | `SOLUTION_INSTALL` "PakId: VCFContentFactoryCompliance-00067" |
| 11:46:40 to 11:46:41 | 8 × `VIEW_DEFINITION_IMPORT` (all 8 pak views, incl. Host Detail `17b8d01a`) |
| 11:46:41.651 | `DASHBOARD_IMPORT` ForceByID `false`, ForceByName `true` (#1, vCenter & Networking) |
| 11:46:43.663 | `DASHBOARD_IMPORT` ForceByName `true` (#2, **ESXi Hosts**) |
| 11:46:45.844 | `DASHBOARD_ADD_TAB` ... `"[VCF Content Factory] Compliance ESXi Hosts"` |
| 11:46:48.931 | `DASHBOARD_IMPORT` ForceByName `true` (#3, Environment Overview) |
| 11:46:53.319 | `DASHBOARD_IMPORT` ForceByName `true` (#4, VMs) |
| 11:46:55.3 to 55.4 | 4 × `SUPER_METRIC_IMPORT` |
| 11:46:55.465 | `VIEW_DEFINITION_DELETE` old "Compliance Host Overview" (`a9a4a2bc`) |
| 11:46:55.516 | `DASHBOARD_DELETE` `51ed9773` (build 56's retired Fleet Overview) |

The pak imports dashboards in on-disk order, not zip order. The zip
order is Environment Overview, ESXi, VMs, vCenter.

**2. ESXi Hosts existed, then disappeared.** After every dashboard
import, the importer writes one `DASHBOARD_ADD_TAB` audit line for
every dashboard in maintenanceAdmin's tab set. That gives a full
snapshot of the set after each import. The snapshots, diffed:

| After import | Count | Change from previous snapshot |
|---|---|---|
| #1 vCenter & Networking | 178 | (baseline) |
| #2 ESXi Hosts | 179 | **+ ESXi Hosts** |
| #3 Environment Overview | 179 | **− ESXi Hosts**, + Environment Overview |
| #4 VMs | 180 | + VMs |

Then Fleet Overview is deleted (audited), leaving 179, which matches the
live `getDashboardList` count now (179). **Between 11:46:45.844 and
11:46:50.69 there is no `DASHBOARD_DELETE` audit line.** The only
audited deletes in the whole install window are `51ed9773` and the
unrelated `3d84205c` loop (see §Noise).

**3. A concurrent writer ran in exactly that window.** In
`vcops-bridge.log`, a new `DashboardImporter.processDashboardsImport`
thread (`threadId="78550"`, `Thread-21714`) started at **11:46:45.467**.
That is inside import #2, which ran from 11:46:43.663 to 11:46:45.844.
The pass walked every pending dashboard (MSSQL, Oracle, Rubrik,
chargeback and so on) and at **11:46:46.596** resolved and saved
vCenter & Networking (its `internalIdToTransferredIdMap` is the
2-kind table, `vSphere World` + `VMwareAdapter Instance` +
`adapterKind vcfcf_compliance`). The pass then repeats every 10 minutes
on the same thread:

```
16:45 UTC thread 78460   9 dashboards   (triggered by an unrelated import at 11:45:49 CDT)
16:46 UTC thread 78550  10 dashboards   (+ vCenter & Networking)
16:56 UTC thread 78550  11 dashboards   (+ Environment Overview, + VMs)
17:06 UTC thread 78550   9 dashboards   (the three completed and left the queue)
```

**No pass ever handled ESXi Hosts.** Its 4-kind table (World, VMwareAdapter
Instance, Cluster, HostSystem, and no VirtualMachine) appears in no
`keysByEntryType` / `internalIdToTransferredIdMap` line today. It left
the store before the 11:56 pass.

**4. No error anywhere.** Neither the import thread `78483` (analytics
log) nor the bridge log shows an exception or ERROR for our content in
the window. The only bridge ERRORs are the known unresolvable-kind lines
for other dashboards (AZURE_*, SqlServer, mpb_rubrik). The pakManager
`apply_adapter` / `post_apply_adapter` logs have no dashboard lines.

## Inference (not proven)

Mechanism: thread `78550` loaded the pending set, or the per-user
dashboard container, at about 11:46:45.47. That was before ESXi Hosts
committed at about 11:46:45.84. At about 11:46:46.6 it wrote vCenter &
Networking back through a replace, carrying the stale snapshot. That
dropped ESXi Hosts without a delete audit. The timing is exact and
nothing else wrote dashboards in the window. But no log line states the
write-back, so the mechanism is inferred.

The alternative, that the ESXi import's own transaction rolled back after
its audit line, has no supporting evidence. No exception appears on
thread `78483`, and the post-import `DASHBOARD_GROUP` /
`DASHBOARD_SHARE_INTERNAL` steps for it were audited normally.

**Why ESXi Hosts and not the others (inference):** it was the
dashboard whose import straddled the materializer thread's start. It was
also the slowest import (2.2 s, against 1.0 to 1.8 s for the others).
Which dashboard gets hit depends on timing, not content. A reinstall
could lose a different one, or none.

## Content is exonerated (field-by-field)

- **Heatmap groupBy:** 9 keys, `type: resourceKind`,
  `typeId: resourceKind:id:2_::_` → `ClusterComputeResource` in the
  dashboard's own `entries` table, `id:
  004null002006VMWAREClusterComputeResource`. This is the same shape as the
  vCommunity pak's "vSphere Cluster Configuration 2.0" (HostSystem layer
  grouped by `resourceKind:id:1_::_` Cluster, 9 keys), which is
  pak-installed and live on devel. It is also near-identical to live "IDPS
  Planner" (HostSystem by Cluster, `selfProvider:false`,
  `relationshipMode [1,-1,0]`) and "GPU Overview" (same, `sizeBy.metricKey:
  null` like ours). Devel has **67 live Heatmap widgets**, 60+ of them with
  9- or 7-key `groupBy`. Build 56's pak-installed Fleet Overview, which
  also carried a Heatmap, was created fine.
- **Token integrity:** every `resourceKind:id:N_::_` used in the ESXi
  dashboard (0 to 3) is defined in its `entries`, and none is undefined.
  The same holds for the other three. The unused `adapterKind:id:0_::_`
  is present in all four, so it does not distinguish ESXi.
- **Envelope vs VMs** (which installed): ResourceList, View, MetricChart
  and PropertyList differ only in ids, titles, coords, kind index (3 vs
  4) and metric keys. Dashboard-level keys are identical (`namePath`,
  `adapterName`, `shared`, `hidden`, `rank`, `userId`, `importComplete`).
  No widget id repeats across the four dashboards.
- **AlertList:** all 87 `alertDefinitions` exist in the pak's
  `describe.xml` (151 defs); the same holds for the other three lists.
- **Pak folder:** `content/dashboards/<dir>/dashboard.json` +
  `resources/resources.properties`, the same structure and naming as the
  other three. The ESXi properties file carries the dashboard name plus
  all six widget titles.
- **Only cosmetic outlier:** the ESXi description contains JSON-escaped
  double quotes (`"Which controls fail"`). This is valid JSON. The
  Environment Overview description is the one that mentions "ESXi Hosts",
  and the ForceByName match cannot be the cause, because it did not remove
  vCenter & Networking, which shares the same `namePath`.

## What to do

1. **Recovery (needs orchestrator + Scott's go, not done here):**
   import the one ESXi dashboard again. That is either a factory content
   import of the rendered dashboard, or a pak reinstall. It is also the
   discriminating experiment: if the identical bytes are created and
   **survive the next 10-minute materializer pass**, content is
   definitively ruled out. A content import is a uuid-keyed replace that
   touches only this dashboard.
2. **Verification rule for pak installs (tooling/installer, not
   content):** after a pak install, poll until the **count** of
   pak-bundled dashboards on the instance equals the count in
   `content/dashboards/`. Do not trust `FINISHED` + `errorMessages: []`.
   A missing one is re-imported singly. The pak `FINISHED` envelope
   cannot report this loss. It happened after the importer's own
   success audit.
3. **Do not change the Heatmap, the renderer, or the YAML** for this
   symptom.

## Noise seen in the window (not causal)

- `DASHBOARD_IMPORT` (ForceByName `false`) then `DASHBOARD_DELETE`
  `3d84205c-45c8-4708-9a94-161a18443796` by maintenanceAdmin from the
  appliance's own IP repeats about every 30 s from 11:49:50 CDT onward,
  plus one at 11:45:49. None falls between 11:46:41 and 11:46:56.
  Something on devel is looping an import of that dashboard. Unrelated
  to this pak, and worth a separate look.
- `PolicyAttributePackageService` WARNs at 11:46:35 for retired
  ComplianceWorld `summary|*` attributes: upgrade residue from build 56.

## Method log

- Pak: `dist/vcfcf_sdk_compliance.0.0.0.67.pak` unzipped to scratch,
  inner `adapters.zip` for `describe.xml`.
- Live: `VCFOpsUIClient.from_env("devel")`, `getDashboardList` (179),
  `getWidgetConfigs` for all 179. Heatmaps are identified by
  `configs[0].groupBy`. Note: with `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`
  set in the shell, `requests` overrides `session.verify=False`. Unset
  them for the lab's self-signed chain.
- Logs (SSH, read-only):
  `/storage/log/vcops/log/analytics.audit-*.log` (the decisive source:
  `DASHBOARD_IMPORT`/`ADD_TAB`/`DELETE` with ForceBy flags),
  `vcops-bridge.log` (`DashboardImporter` phase-2 passes),
  `analytics-*.log.1`, `api.log`, `pakManager/*`.

## Clean-up verified: yes

Nothing was created or modified on devel. Local scratch was under the
session scratchpad. No temp files were left on the appliance.

## Cross-references

- `dashboard_import_two_phase_materialization.md`: phase 1 / phase 2
  model, which this adds a failure mode to (phase 2 racing a multi-dashboard
  phase 1).
- `knowledge/lessons/dashboard-import-deferred-materialization.md`
- `knowledge/lessons/pak-content-bundling.md`: the older silent
  non-import class (`isEntityFound()=false`), which is **not** this.
  Here the record was created.
- `knowledge/context/investigations/2026-05-29-compliance-dashboard-render-failures.md`:
  the empty-`groupBy` Heatmap crash, which is also not this. That one
  created the dashboard and failed at render.
