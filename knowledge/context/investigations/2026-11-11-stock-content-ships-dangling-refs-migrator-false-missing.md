# Stock content ships dangling references; exports carry them as they are (vcf-cf-migrator false "missing")

Date: 2026-11-11. Instances: `devel_8_18` (Aria Operations 8.18.7), `devel` (VCF Operations
9.0.2) and `prod` (VCF Operations 9.1.1). `devel_9_1` (9.1.1) was stopped for
the export work and was read later, read-only, for the loading-state question
in §Q4. Content export jobs (`POST /api/content/operations/export`, scope
`ALL`) on all three; zips stayed in the session scratchpad. One authorized
write experiment on `devel` (§Q4, E1): five throwaway probe dashboards imported
by content zip and deleted, with the deletion checked against a
pre-experiment snapshot.

Tool under study: `sentania-labs/vcf-cf-migrator` at `7dead31`
(`src/vcfcf_migrator/graph.py`, `navigation.py`). It refuses to build a bundle
when a dashboard names a view, a navigation target dashboard, or a navigation
widget id that is not in the export. On a customer's full export it flagged 50
views, 43 navigation targets and 32 navigation widget ids, mostly from
pak-supplied dashboards. The ids below are content uuids. Some belong to
product content; some are of customer-authored dashboards and views (classes
D below). None is a name, owner or other customer-identifying string.

## Answer in one paragraph

The hypothesis that content exports leave product or pak views out is wrong.
A scope-`ALL` export carried every view the UI view list shows, and every
dashboard `getDashboardList` shows plus more, on 8.18.7, 9.0.2 and 9.1.1. No
attribute excludes stock or pak content. Two documented exceptions apply to
dashboards: one export was seen with no dashboards at all, and a dashboard
whose import has not completed is exported hollow. So "absent from the export"
nearly always means "absent from the source" (§Export completeness). What the
tool hits is stock content that **ships with dangling references**. Live stock
dashboards on 8.18.7 and 9.1.1 target dashboard ids that do not exist, key
`dashboardNavigations` on widget ids that are not on the dashboard, and point a
View widget at a view that does not exist. The other 43 views come from stock
dashboards whose ids are on no lab instance. That is inferred, with two
candidate explanations: older-generation stock kept through upgrades, or stock
views deleted on the customer's instance, as happened on `devel` (§Q1).
Content-zip import of a dashboard with each dangling kind completed normally
on 9.0.2 (verified, §Q4). The stock dashboards that do stay loading on 9.1.1
wait on uninstalled adapter kinds or missing resources, not on their
navigation targets (verified from importer logs, §Q4). A dangling view renders "The view does not exist.";
a dangling navigation target is silently left out of the drill menu. On 8.18.7
and 9.1.1 lab exports, with no customer content, the tool already reports 67
and 148 blocking "missing" edges from VMware-shipped content.

## Export completeness

### Views (verified on all three)

| Instance | Views in UI list (`getGroupedViewDefinitionThumbnails`) | `<ViewDef>` in export `views.zip/content.xml` | In UI list, not in export |
|---|---|---|---|
| 8.18.7 | 778 | 778 | 0 |
| 9.0.2 | 787 | 787 | 0 |
| 9.1.1 | 1030 | 1030 | 0 |

The export's `configuration.json` `"views": N` matched the UI count on all three
instances. The 9.1.1 export with more content types also carried 1646 alert
definitions, 2618 symptoms, 1317 recommendations and 97 reports, so stock
content of those types is exported too. That is not the whole of it: symptoms and
alerts of adapter kind `ALL` and symptoms on badge or capacity time-remaining
keys are never exported (`2026-11-11-alert-symptom-export-completeness.md`). Custom groups (18) and super metrics
(75) are custom ones only, but those are custom by nature.

The comparison is against the UI view list, not an independent store. It is
the most complete view inventory found; no export exception for views is
documented.

### Dashboards (export is a superset of the only inventory available)

There is no authoritative live dashboard inventory to compare against. Neither
OpenAPI spec has a dashboard list endpoint. `getDashboardList`
(`/ui/dashboard.action`) is per user and omits non-listed dashboards (Self
dashboards, Summary Pages, some pak content, other users' unshared
dashboards). The other `dashboard.action` list actions the UI script uses
(`getDashboardTabs`, `getDashboardTabsHierarchy`, `getUserDashboards`) returned
nothing usable. `vcopsdb` on the 9.0.2 appliance (both Postgres instances, 5432
and 5433) has no dashboard table, so the dashboards live in another store. The
instance count is therefore unknown, and this is the comparison:

| Instance | `getDashboardList` (admin) | Export (`configuration.json` and documents) | In list, not in export | In export, not in list |
|---|---|---|---|---|
| 8.18.7 | 163 | 163 (one owner) | 0 | 0 |
| 9.0.2 | 180 | 180 (one owner) | 0 | 0 |
| 9.1.1 | 266 | 301 (296 admin, 5 a second owner) | 0 | 35: 26 `adapterName: null` (Self, Summary Pages, License Server Health, Recommendations; 8 of them disabled), 5 vCommunity pak, 4 of the second owner |

Disabled dashboards are exported (all 25 on 8.18.7, 25 on 9.0.2 and 81 on
9.1.1). `hidden` is `true` on most stock dashboards (149 of 163 on 8.18.7, 241
of 301 on 9.1.1) and does not mean invisible.

When a dashboard that exists on the instance can be absent or hollow in an
export:

1. **Hollow while import has not completed.** A dashboard with
   `importComplete: false` is exported with its `entryKeys` and with `config:
   {}` on every widget still waiting for an entry
   (`../api-surface/dashboard_selfprovider_pin_wire_format.md` §"Why binding is
   browser-only observable", item 2). Present in these lab exports: 8 on 8.18.7,
   8 on 9.0.2, 6 on 9.1.1, all stuck on missing adapter kinds or resources
   (Cost/Chargeback/Showback, MSSQL, Oracle, Rubrik, DSM, Valkey). A hollow
   widget's view and super metric references are not in the export, so the
   migrator under-reports them rather than over-reporting. Navigation stays
   readable, because `dashboardNavigations` is at dashboard level.
2. **Absent: one observed whole-export case.** A scope-`ALL` `DASHBOARDS`
   export on 2026-07-22 came back with an empty `dashboards/` folder right
   after dashboards were re-imported
   (`def014-view-binding-loss-2026-07-22.md` §4;
   `../api-surface/dashboard_selfprovider_pin_wire_format.md`, "scope=ALL
   DASHBOARDS exported zero dashboard bodies"). The same build later exported
   all 228 dashboards (`../api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
   §Parity and caveats). The trigger was not isolated. A migrator that sees a
   zip with zero dashboards should treat it as a failed export, not as an
   instance with none.
3. **Not seen:** a single dashboard silently missing from an otherwise
   populated export. Not tested: dashboards of users from other auth sources,
   unshared dashboards of non-admin users exported by admin, and exports taken
   while an import was running. The 9.0.2 probe export in §Q4 was taken after
   completion and carried full config.

The migrator's own message ("an export carries custom content only") is
therefore false for views and dashboards.

## Q1. Missing views

None of the 50 exists on any lab instance (8.18.7, 9.0.2, 9.1.1). By how the
referencing dashboard relates to live stock:

| Class | Count | Ids (first 8) | Evidence |
|---|---|---|---|
| A. Ships dangling in the live stock dashboard | 2 | `42194e98` (from `abb3cadf` "(DEP) Provider \ Simplify it?", live on 8.18.7 and 9.1.1 with the same ref); `dd7bbb72` (from `559a9658` "VCF MP Capacity", same ref live on 8.18.7, gone from the 9.1.1 revision) | verified |
| B. Referenced by a stock-named dashboard whose id is on no lab instance | 43 | all others with `source_adapterName` set; referencing dashboards `67ae00e5` VM Configuration, `9ddaaf3b` Capacity Allocation Overview, `30a902ab` second "(DEP) Provider \ Simplify it?", `aa7b4ca2` Capacity Overview, `259e0301` Cluster Configuration, `eeab8718` Datastore Capacity, `28df0923` Datastore Performance, `a23edd61` Troubleshoot a VM, `e1ebd69e` ESXi Configuration, `d01d7ba0` Heavy Hitter VMs, `b4862971` Network Configuration, `a7575481` Optimization History, `b29ed707` Optimize Performance, `ad52daa1` Troubleshoot a Host, `a165a8b4` VM Usage | inferred, two explanations below |
| B2. Admin-owned, no `adapterName`, not on any lab | 2 | `1ce5ef41`, `bc76a1ca` (from `12e8f660` an admin-owned host compliance dashboard) | not explained |
| D. Customer-authored dashboard only | 3 | `bd9798e9`, `e3af5015`, `6c4d07f7` (from `bdf18c02`) | not explained (customer content) |

Two of the class B views (`0eb5e828`, `3017670b`) are also named by a
customer-owned copy of the same stock dashboard. A user-owned copy of a stock
dashboard keeps `adapterName` (`1371103f` is user-owned and says
`VMware vSphere`), so `adapterName` means "pak-supplied or copied from
pak-supplied", not "admin-owned".

Class B, two explanations, neither verified on the customer's instance:

- **Older-generation stock kept through upgrades.** The lab instances carry
  current stock dashboards with the same names under different ids (VM
  Configuration `a4a25364` against the customer's `67ae00e5`; Datastore
  Performance `bd1803ca`, which the customer also has as "Datastore
  Performance New", against `28df0923`; ESXi Configuration `d3a307f9`; Cluster
  Configuration `92102441`; Network Configuration `98e47b7e`; Datastore
  Capacity `338e22d0`). `a23edd61` "Troubleshoot a VM" is still a navigation
  target of the shipped "Troubleshoot SD-WAN" dashboard on 8.18.7 and 9.1.1, so
  it was a stock id once. Not reproduced: no old build in the lab.
- **Stock views deleted on the instance.** On `devel` (9.0.2), 62 stock views
  that 8.18.7 and 9.1.1 carry have been deleted, and the stock dashboards that
  use them are still in place, still `importComplete: true`, with a dangling
  `viewDefinitionId` (§Q5, 9.0.2 section). The same could have happened on the
  customer's instance.

Either way, because the export carries every view, those dashboards already
render "The view does not exist." in the affected widgets on the customer's
instance (inferred from the §Q4 render result).

## Q2. Missing navigation target dashboards

None of the 43 exists on any lab instance, except `f79ad44f` (vSAN
Performance, on 9.0.2 and 9.1.1 but not 8.18.7). Disabled and hidden dashboards
are exported (§Export completeness). So a target absent from a populated
export is absent from the source.

| Class | Count | Ids (first 8) |
|---|---|---|
| A. Live stock dashboard on 8.18.7 and/or 9.1.1 still targets it, and it is absent there too | 12 | `836cc887` (SD-WAN Gateway, Orchestrator), `90b3551f` (10 Cost/Chargeback/Showback and three vRA 8.x project dashboards), `a64a48ae`, `e5481902`, `d5a11c85` (Cluster Performance; also vSAN OSA/ESA Capacity), `a175a889`, `5909491f` (Live! vSphere VM Changes, vSphere VM Inventory, vSphere Daily Check), `5ddbfb63`, `69f2ed78` (vSphere Inventory (Compute), Daily Check), `fd5adf68` (Troubleshoot SD-WAN), `95fd15b2`, `0c181ab7` (vSphere Inventory (Storage)) |
| B. Only referencing dashboard is pak content not installed on any lab | 2 | `8146b6de`, `f79ad44f` (both from `0706d3ca` "TAM Insights - Performance Insights", TAM pak) |
| D. Customer-authored dashboards only | 29 | `562b38db` (from `ac3c8b7b`) and 28 targets of `806ae20c` |

Live 9.1.1 dashboards target more absent dashboards than the worklist shows
(e.g. SD-WAN Gateway also targets `30a2564a`, `103d80ba`, `4b5c602a`).

## Q3. Stale navigation widget ids

Of the 29 records on pak-supplied dashboards, 23 are on dashboards present on
8.18.7 and 9.1.1 under the same id, and **all 23 are byte-for-byte present in
the live copies** (verified on both). The other 6 are on dashboards not on any
lab (`8e424387` Kubernetes Application Performance x1, `0706d3ca` TAM Insights
x4, `00ca92f0` an older vSAN OSA Performance id x1; the lab one is
`90bdd1da`). `00ca92f0`'s record is the same `584b09f3` destination seen in
five live dashboards, so it is the same pattern (inferred). 3 records are
customer-only.

What the shipped defects are:

- **Orphan source keys** (15 distinct on 9.1.1): `dashboardNavigations` keyed
  on a widget id that is not a widget on the dashboard, e.g. `91b49069` on both
  Telegraf dashboards, `0ef9b034`/`8da03898`/`09d6487f` on Cluster Performance,
  `8ba77bdc`/`04b7516c` shared by Live! VM Changes, VM Inventory and Daily
  Check (copy-paste between dashboards). Same as the Oracle pak finding in
  `../wire-formats/dashboard_navigations.md`.
- **Destination widget ids absent on the target**: `584b09f3` names a widget
  on `a10e7aaa` "Performance/Consumer/VM Performance", and `7c2a4c54` one on
  `69ab9c94` "Capacity/VM Capacity". Both targets exist (pak-supplied,
  `hidden: true`, enabled); neither has that widget.
- **A double-encoded destination id** in "Troubleshoot SD-WAN" (`3800758d`):
  `widgets[].id` is the JSON string
  `{"interactionType":"resourceId","id":"fb047a68-..."}`, not a uuid. Same on
  the entry to `fd5adf68`. A product serialization bug, shipped.

Tool misread ruled out: `navigation.widget_ids` already walks every `widgets`
list at any depth, skipping only `dashboardNavigations`. None of the orphan ids
is a widget anywhere in the 8.18.7 or 9.1.1 export. They occur only as
navigation keys in other stock dashboards or in vCommunity copies of them.

## Q4. Does the import care?

### E1: controlled content-zip import on 9.0.2 (verified)

`devel`, 9.0.2, 2026-11-11 17:18 to 17:44 UTC. One throwaway factory dashboard
per variant, `[VCF Content Factory] EXP-DANGLE Probe Dashboard[ <v>]` (ids
`5e7a0e0e-0000-4000-8000-0000000ded01`, `...ded0a`, `...ded0b`, `...ded0c`,
`...ded0f`), plus probe view `...de001`. Each dashboard is a ResourceList of
`VMwareAdapter Instance` driving a View widget on the probe view. Built with
`load_all` + `packager.build_import_zip`, then the rendered `dashboard.json`
was post-processed in the scratchpad to inject the defect (the renderer refuses
dangling navigation targets by design). Imported through
`vcfcf_dashboards.client.import_content_zip` (`force=true`), one zip per
variant. The injected values were read back from a `DASHBOARDS` export after
completion and survived import verbatim.

| Variant | Defect injected | Envelope | `isLoading` timeline | Export after completion |
|---|---|---|---|---|
| K (control) | none | FINISHED, `NONE`; VIEW_DEFINITIONS 1/0/0, DASHBOARDS 1/0/0 (imported/skipped/failed) | true 17:19:22 to 17:29:11, false 17:29:41 | `importComplete: true`, `importAttempts: 0`, `entryKeys: null`, both widgets with config |
| a | View widget `viewDefinitionId` = `...dbad1` (exists nowhere) | same | true from import (17:31:51) to 17:39:03, false 17:39:35 | complete, attempts 0; `viewDefinitionId` still `...dbad1` |
| b | navigation from the picker to dashboard `...ddd01` (exists nowhere) | same | as a | complete, attempts 0; navigation kept |
| c | orphan key `...dee98` (no such widget) to Cluster Performance `533e14ed`; picker to `533e14ed` naming receiver `...dee99` (not on it) | same | as a | complete, attempts 0; both entries kept |
| ALL | a + b + c | same | as a | complete, attempts 0; all three kept |

Decisive log evidence (`vcops-bridge.log`, logger
`com.vmware.vcops.bridge.server.DashboardImporter.processDashboardsImport`):

- One importer pass at 17:39:11-12 logged four `keysByEntryType =
  {resourceKind=[{"resourceKindKey":"VMwareAdapter Instance",...}]}` and
  `internalIdToTransferredIdMap = {resourceKind:id:0_::_=002006VMWAREVMwareAdapter Instance}`
  pairs, one per probe. The four flipped to `isLoading: false` by the next
  poll (17:39:35).
- In both windows, every `Entry info didn't found for dashboard: ...` line
  names other dashboards (Cost/Chargeback/Showback, MSSQL, Oracle, Rubrik).
  None names a probe. No ERROR line names one either.
- `view-bridge.log` per import: `restoreData: Views import started...`,
  `Dashboards import started...`, `Dashboard Sharings import passed`.
- The control needed two passes: its entry resolved at 17:19:06 but it stayed
  loading until the 17:29:09 pass. The variants rode the existing 10-minute
  cycle and completed on its first pass after import. So completion time is
  set by the pass schedule, not by the defects.

Cleanup: all five dashboards deleted (`deleteTab`), the probe view deleted
(`viewServiceController.deleteView`). Pre and post `getDashboardList` /
`getGroupedViewDefinitionThumbnails` snapshots are identical (180 dashboards,
787 views). The browser pass below opened stock Cluster Performance (read
only) and added the probes to the admin's Recents list until deletion.

### Render (verified on 9.0.2, browser `chrome-devtools-axi`, after completion)

- **a, dangling view:** selecting a vCenter drives the View widget, which shows
  **"The view does not exist."** (Control: in b, the same selection rendered
  the probe view's row, `vcf-lab-wld02-cl01`, 2 hosts.)
- **b, dangling target as the only navigation:** no drill menu is offered.
  Selection goes straight to the internal interaction. The dangling target is
  silently dropped.
- **c and ALL:** the drill menu lists exactly `Cluster Performance` and
  `Internal interaction`. The orphan key has no widget to fire it. In ALL the
  dangling `...ddd01` entry is not listed. Choosing Cluster Performance in c
  navigated to `tabId=533e14ed-...` and the target rendered. Whether the absent
  receiver caused any visible effect on the target was not inspected.
- In ALL, the scripted "Internal interaction" menu click did not reach the
  View widget, which stayed on its "Select the widget source..." prompt. The
  missing-view render is covered by a, not by ALL.

### Summary, with labels

| Kind | Import completion | Render | Label |
|---|---|---|---|
| View widget whose view is absent | Completes. Views are not phase-2 entries: `fromEntryKeys` resolves adapter kinds, resource kinds, resources, collectors, maintenance schedules and attribute keys (`2026-10-13-dashboard-import-deferral-trigger.md`, `processDashboardsImport` paragraph) | Widget shows "The view does not exist." | Verified, content-zip import and render, 9.0.2. Also observed: installed stock dashboards on 8.18.7 and 9.1.1 read `importComplete: true` with a dangling view (does not show the view was missing at import time) |
| Navigation target dashboard absent | Completes | Entry silently left out of the drill menu | Verified, content-zip import and render, 9.0.2. Other versions inferred |
| Orphan source key / absent destination widget | Completes | Orphan key: nothing can fire it. Absent receiver: the jump works | Verified, content-zip import, 9.0.2. Receiver effect on the target not inspected |

8.18.7 and 9.1.1 content-zip import: not run; inferred the same.

Timing against the `devel` service restart (analytics, collector and API,
about 10:32 to 10:34 CST, 16:32 to 16:34 UTC): every E1 run was after it.
K ran 17:18 to 17:30 UTC and a, b, c and ALL ran 17:31 to 17:44 UTC. The
`devel` live inventory (about 16:47 UTC) and the 9.0.2 export (16:50 to 17:10
UTC) were after it too. Nothing was rerun.

### What does hold a stock dashboard in the loading state (9.1.1, read-only)

On `devel_9_1` (9.1.1) `getDashboardList` shows four stock dashboards with
`isLoading: true`: Chargeback (VM Price) `f9362710`, Showback (VM Cost)
`1844b814`, VM Cost vs. Price `2f8f4b00` and Data Services View `215259eb`.
The same four are `isLoading: true` on `prod` (9.1.1), so the two instances do
not differ on these. `prod` additionally has Rubrik Overview and Valkey
Overview loading (MPB paks), and `devel_9_1` one customer-imported dashboard.

What they wait on, from `vcops-bridge-<node>.log` on `devel_9_1` over SSH
(logger `com.vmware.vcops.bridge.server.DashboardImporter`, method
`processDashboardsImport`). Every pass today logs the same not-found entries
for these four (passes at 17:17, 17:27, 17:37, 17:39 and 17:47 UTC), and
nothing else:

```
Dashboard Import: Entry info didn't found for dashboard: Chargeback (VM Price), widget: Select a Group, entry: {"resourceKindKey":"Project","internalId":"resourceKind:id:30_::_","adapterKindKey":"CASAdapter"}
Dashboard Import: Entry info didn't found for dashboard: Chargeback (VM Price), widget: Select a Group, entry: {"resourceKindKey":"Organization","internalId":"resourceKind:id:35_::_","adapterKindKey":"CASAdapter"}
Dashboard Import: Entry info didn't found for dashboard: Chargeback (VM Price), widget: Select a Group, entry: {"resourceKindKey":"CloudZone","internalId":"resourceKind:id:39_::_","adapterKindKey":"CASAdapter"}
(same three for "Showback" and "VM Cost vs. Price", widget "Select a Group")
Dashboard Import: Entry info didn't found for dashboard: Data Services View, widget: DSM Inventory, entry: {"resourceKindKey":"dsmworld","internalId":"resource:id:0_::_","adapterKindKey":"APPOSUCP","identifiers":[],"name":"DSM World"}
```

- The three Cost dashboards wait on resource kinds of the `CASAdapter`
  (Aria Automation 8.x) adapter kind, bound by their "Select a Group" widget.
  `GET /api/adapterkinds` has no `CASAdapter` on either 9.1.1 instance.
- Data Services View waits on the `DSM World` resource of `APPOSUCP`. The
  adapter kind is installed, but `GET /api/resources` finds 0 `dsmworld`
  objects on either instance. Data Services View has no navigation targets.
- `prod` SSH is closed (port 22 refused), so `prod` was read from its export:
  the three Cost dashboards carry the same three `CASAdapter` kinds in
  `entryKeys`, and all their widgets export with empty config.

The control group settles it. On `prod`, nine stock or copied Cost dashboards
carry the **same dangling navigation target** `90b3551f`. Six of them, with
no `CASAdapter` kinds in `entryKeys`, are `importComplete: true`: Business
Applications Cost vs. Price, Chargeback (Business Application Price), Showback
(Business Application Cost), Showback (vSphere Pod Cost), VCF Automation VM
Cost vs Price, and a custom Showback copy. Only the three with `CASAdapter`
kinds are loading. No not-found line anywhere names a view or a navigation
target.

**Answer: a navigation target or view reference does not hold a dashboard in
the loading state.** The stock dashboards that stay loading are waiting on
widget-bound resource kinds or resources that do not exist on the instance: an
adapter kind that is not installed, or a resource with no instance. This
matches E1 and the mechanism in
`2026-11-11-devel-9-1-ui-import-dashboard-skip-and-gemfire-503.md` §Q3.

## Q5. False-positive baseline (migrator `tree --json`, no customer content)

| Export | Missing edges, all blocking | From VMware-shipped content | Kinds (VMware-shipped) |
|---|---|---|---|
| 8.18.7, views + dashboards | 77 | 67 (37 source dashboards) | 37 nav-target edges (17 distinct target ids), 15 nav source ids, 11 nav destination ids, 3 views, 1 super metric (type not exported) |
| 9.1.1, views, dashboards, SMs, groups, reports, alerts, symptoms, recommendations | 162 | 148 (143 from dashboards, 5 from a stock alert and report) | 108 nav-target edges (25 distinct target ids), 20 nav source ids, 11 nav destination ids, 3 super metrics, 1 view, 4 symptom refs, 1 report-to-dashboard ref |

The rest on 9.1.1 is third-party pak content (vCommunity, an MPB pak). On 8.18.7
the other 10 are super metrics, which that export did not include. Neither
instance is a fresh install: `prod` carries third-party paks and custom super
metrics, and both carry factory content. A fresh install would show the same
VMware-shipped edges, because they come from the stock dashboards themselves
(inferred, not measured on a fresh install). Every unfiltered selection that
touches these stock dashboards is refused.

### 9.0.2 (`devel`) export: a lab-state warning

The 9.0.2 export is complete in the sense above (787 of 787 views, 180 of 180
listed dashboards), and the per-item classification is unchanged with it
added. But its walk reports 256 missing edges, 100 of them views (63
distinct). 62 of those 63 views exist on 8.18.7 and 9.1.1 and are referenced by
the same stock dashboards there ("Cluster Configuration New", "VM Configuration
New", "ESXi Configuration New", "Network Configuration New", "Cluster
Performance New", "VM Capacity", ...). They have been deleted from devel at
some point. That is a lab-state defect, not a product one, so devel is not a
baseline. It does show the mechanism live: deleting a stock view leaves the
stock dashboards that use it in place, still importComplete, with a dangling
`viewDefinitionId`.

## Classification rule for the tool

Scope: this rule is for the migrator reading other people's exports. It does
not apply to factory packaging, which deliberately refuses dangling navigation
targets so that every import path ships or names each target
(`../wire-formats/dashboard_navigations.md` §Wire format, "Dangling targets
install without error", and §Packaging).

Evidence available **in the zip alone**:

1. Views: the export carries every view (§Export completeness), so an absent
   view is absent from the source. Dashboards: same, except a zip with zero
   dashboards (treat as a failed export) and hollow dashboards
   (`importComplete: false`; their widget references are missing, not extra).
2. The referencing dashboard's `adapterName` non-null means pak-supplied (or a
   copy of pak-supplied). `null` does **not** mean customer-built: besides
   content-zip imports and user dashboards, core product dashboards carry
   `null` ("vRealize Operations/Self Health" and the other Self dashboards,
   "vCenter Adapter Details", "vSphere Dashboards Library/Recommendations", and
   on 9.1.1 the "Summary Pages/..." set; 38 of 301 null on 9.1.1, 12 of 163 on
   8.18.7). That is probably why an admin-owned host compliance dashboard (`12e8f660`,
   admin-owned, `null`) looks customer-ish while likely being an older built-in
   (inferred).
3. Navigation source key in the same document: present as a widget or not.

Rule:

- **Inert** (warn, never block): an orphan navigation source key; a
  destination widget id absent from an existing target (including a non-uuid
  id); a navigation target absent from the export (it is dropped from the drill
  menu); any reference whose source dashboard is an original pak-supplied
  dashboard, because the source instance already runs with it broken and the
  target gets that dashboard from the pak, not from the bundle.
- **Stock content, expected on the target**: an original pak-supplied
  dashboard. Default it out of bundles; the pak installs it on the target.
  Carrying it would be a uuid-keyed replace of the target's own copy.
  **`adapterName` alone does not establish this.** A user-owned copy of a
  stock dashboard keeps the field (Q1: `1371103f` is such a copy with
  `adapterName: VMware vSphere`), and a copy is customer content the pak
  cannot restore, so it must stay selectable and be migrated. Nothing in
  the export was shown to separate an original from a copy: a different id
  from the stock dashboard of the same name, and an owner other than the
  admin, each point to a copy, but neither was tested as a rule, and an
  admin can own a copy. Treat `adapterName` as "stock or derived from
  stock", label it, and leave the choice to the person; do not exclude on
  it.
- **Truly missing** (block, or warn loudly): a view named by a dashboard with
  `adapterName: null` and absent from the export. The widget will show "The
  view does not exist." on the target, as it already does on the source. The
  message is "already broken on the source", not "export it as well". That set
  includes a few core product dashboards, so the residue is "not pak-supplied",
  not provably customer-built.

Needs a live target: whether a stock dashboard id, view or navigation target
named by customer content exists there (a pak version that has it, e.g.
`f79ad44f`). That is the only case where "absent from source, present on
target" happens. For views, `getGroupedViewDefinitionThumbnails` on the
target answers it (it matched the export exactly on all three versions).
For dashboards, `getDashboardList` only confirms presence: it is per user
and omits Self dashboards, Summary Pages, some pak content and other users'
unshared dashboards (35 dashboards in the 9.1.1 export are not in it). An
id found there exists; an id absent from it is **unknown**, not missing.
A definite "absent" for a dashboard needs a target export or a per-id
lookup, and no per-id dashboard endpoint was found on these builds.

## Method and artefacts

- Live inventories: `VCFOpsUIClient.list_views()` / `list_dashboards()`
  (unsupported UI endpoints) per profile.
- Exports: `POST /api/content/operations/export` `{"scope":"ALL","contentTypes":[...]}`.
  `contentTypes` is honoured under scope `ALL`: only the listed types were
  written. VIEW_DEFINITIONS took about 90 s on 9.1.1, 13 min on 8.18.7, and
  20 min on 9.0.2.
- Walk: `vcfcf_migrator tree <zip> --json` from the pinned venv.
- E1: harness, probe YAML, variant zips, envelopes, poll logs, exports, log
  extracts and screenshots in the session scratchpad only; probe content
  deleted and verified (§Q4).
