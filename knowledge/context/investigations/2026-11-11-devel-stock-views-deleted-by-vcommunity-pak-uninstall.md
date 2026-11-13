# devel (9.0.2): 64 stock views deleted by the vCommunity vSphere pak uninstall, 2026-10-15

Forensic read of `devel` (`vcf-lab-operations-devel`, VCF Operations 9.0.2.0
build 25429562, vSphere adapter 9.0.2.0200 build 25430359), 2026-11-11.
Read-only: Suite API GETs, root SSH (`sshpass -e`, password never on argv)
for `/storage/log/vcops/log/` and `/storage/db/pakRepoLocal/`. Nothing on the
instance was changed. Times are UTC in log quotes, America/Chicago (CDT) in
prose. Follows `2026-11-11-stock-content-ships-dangling-refs-migrator-false-missing.md`
§Q5 (9.0.2 section), which found the dangling views.

## Answer

One event. At **1:33:49 PM CDT on 2026-10-15** the factory removed its own
**VCF Content Factory vCommunity vSphere** pak (version 0.0.0.13) from devel,
with Scott's approval (`2026-10-15-devel-inventory-sync.md`, first row). Two
minutes later the product's pak-removal job deleted every view the pak had
shipped, by id, in one call: 109 views. **64 of those ids are VMware stock
views.** The pak carried copies of them under the stock UUIDs, inherited
verbatim from the upstream vmbro/VCF-Operations-vCommunity content it was
ported from. When the pak was installed on 2026-07-16, those copies overwrote
the stock definitions. When it was removed, the product deleted them as pak
content. The stock dashboards that use them stayed.

Cause: a factory defect (a factory-built pak shipped content under ids it
does not own), set off by a factory-run, approved uninstall, and carried out by
the product. Certainty: high. Every link except the client of the remove call
is a verbatim audit line. The factory's own name-based delete paths (bundle
uninstall, `delete-view`, probe cleanups) played no part. Every
`VIEW_DEFINITION_DELETE` they produced on devel since install names a
`[VCF Content Factory]`, `[IDPS]` or IDPS Planner view.

## Evidence

### The 64 ids

Regenerated (the earlier `classified.json` holds the customer worklist, not
this list). There are 63 distinct view ids that devel's stock dashboards
reference but devel lacks. 62 of them exist on both 8.18.7 and 9.1.1. Two more
stock views are on both labs and missing from devel without any dashboard
reference: `41127d01` "Configuration | ESXi CPU Socket" and `7d0d858d` "VMs
with Snapshots". That makes 64 stock views missing from devel. The 63rd
referenced id, `42194e98` (used by "(DEP) Provider \ Simplify it?"), is on no
lab. It is a shipped dangling reference, not part of this loss.

Every one of the 64 was imported by devel's first-boot content load on
2026-04-17 (audit below), so on devel they were stock.

### Audit timeline (`analytics.audit-0ad8f158-...log` and `.log.1`)

The audit pair covers 2026-04-17T02:17Z (first boot) to now. Nothing has
rotated past the event. The other logs that might name a view id (analytics,
web, pakManager) do not reach back to October with that detail: the oldest
`analytics-*.log.35` starts 2026-04-21 but holds no view ids, and a recursive
grep for a lost id across `/storage/log/vcops/log` matched only the two audit
files. For each view-import burst that touched the 64:

| UTC | Who / client | Event | Views imported | Of the 64 |
|---|---|---|---|---|
| 2026-04-17 02:22 | maintenanceAdmin, n/a | first-boot built-in content | 769 | 64 |
| 2026-07-16 20:43 | maintenanceAdmin, n/a, right after `SOLUTION_INSTALL` "VCFContentFactoryvCommunityvSphere-00013" by admin from 172.16.3.13 | pak install | 109 | 64 |
| 2026-10-14 15:57 | maintenanceAdmin, n/a, after the 9.0.2.0200 upgrade (pakManager `vRealizeOperationsManagerEnterprise-902020025431133`, 10:18 to 10:52 CDT) | built-in content re-applied | 701 | 64 |
| 2026-10-15 18:35 | maintenanceAdmin, n/a | pak removal job | delete of 109 | 64 |

The install overwrote stock definitions, and the upgrade put them back. For 60
of the 64 the name changes from the stock name to the pak's name on 07-16 and
back on 10-14. For example, `2788178d`: "Configuration | Resource Pool" on
04-17, "vSphere Resource Pool Configuration" on 07-16, "Configuration |
Resource Pool" on 10-14. `fcab0100`: "Configuration | Cluster DRS Enabled",
then "vSphere Cluster DRS Status", then "Configuration | Cluster DRS Enabled".

The removal, verbatim (thread, userId and the long id and name lists trimmed):

```
2026-10-15T18:33:49.101Z INFO  audit 7021 [ops@4413 ... username="admin" authSource="LOCAL" session=... clientIP="172.16.3.13" auditID="SOLUTION_REMOVE"] [AuditLog.log] - Triggering remove succeeded. "PakId: VCF Content Factory vCommunity vSphere, Version: 0.0.0.13".
2026-10-15T18:35:53.389Z INFO  audit 7021 [ops@4413 ... username="maintenanceAdmin" authSource="LOCAL" session=... clientIP="n/a" auditID="REPORT_TEMPLATE_DELETE"] [AuditLog.log] - Deleting report template(s) succeeded. ID(s): [771756d2-..., (11 ids)]
2026-10-15T18:35:55.183Z INFO  audit 7021 [ops@4413 ... username="maintenanceAdmin" authSource="LOCAL" session=... clientIP="n/a" auditID="VIEW_DEFINITION_DELETE"] [AuditLog.log] - Deleting view definition(s) succeeded. ID(s): [8f46e7de-d976-45c4-b7ad-b2477cc96da3, fc20d8a6-9f74-4b78-9022-7441c6d877e9, c92c7819-bd0c-4ba7-94ab-f6c0980da959, da229455-b8ec-440b-a890-48db49fcf57e, ccfc42fb-aaf3-439e-8111-3a0f1bf7713a, 49b13b68-dee2-483d-8df8-1b6d7957d01c, ... (109 ids)], Name(s): [VM Memory Allocation Trend, vSphere VM Network Top Talkers, VM Shares by RP, Report: Distributed Switch for CSV export, Configuration | VM vCPU, Configuration | Distributed Port Group, ... (109 names)].
2026-10-15T18:35:55.210Z ... auditID="DASHBOARD_DELETE"] ... Deleting dashboard(s). ID(s): [c80749d8-..., (12 ids)]
2026-10-15T18:35:56.531Z ... auditID="ALERT_DEFINITION_DELETE"] ... ID(s): [AlertDefinition-VMWARE-ESXi_Host_NIC_Disconnected, AlertDefinition-VMWARE-ESXi_Host_License_Expiring].
2026-10-15T18:35:56.734Z ... auditID="SYMPTOM_DEFINITION_DELETE"] ... (5 ids)
2026-10-15T18:35:56.941Z ... auditID="SUPER_METRIC_DELETE"] ... (37 ids)
```

All 64 missing ids are in the 18:35:55 delete, and none of the 701 views from
the 10-14 re-import is missing for any other reason. The other 45 deleted views
are vCommunity's own: they exist only on prod, where the upstream vCommunity
pak is installed.

The full id lists are in the session scratchpad
(`sv/logs/decisive.txt`, `sv/logs/deleted_by_type.json`). They are not
committed, because they are working data, not knowledge.

### Pak content carried the stock ids

- The local build `tmp/ref_vsphere_b1/vcfcf_sdk_vcommunity_vsphere.1.0.0.1.pak`
  (a local build, not in the repo)
  (later than the 0.0.0.13 that was removed) has 95 ViewDefs in
  `adapters.zip:vcfcf_vcommunity_vsphere/conf/views/views.zip`. All 95 have
  ids found on the 9.1.1 or 8.18.7 labs, 63 of them among the 64. Its
  content does not use the factory prefix.
- The upstream `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/`
  (`reports/View - Set 1..4.xml`, `View - Collection01.xml`, and the 2.0
  dashboards) contains all 64 stock ids. So the stock ids came from upstream,
  and the port kept them.

### Who sent the remove (inferred)

The remove came from 172.16.3.13 over an admin session that logged in with
`Origin: "UI"` at 18:33:36. That matches `vcfcf_managementpacks uninstall`
(`installer.uninstall_pak`: `/ui/` login, `solution.action mainAction=remove`).
The same address sent the three adapter-instance deletes at 18:33:09 (`Origin:
"REST_API"`) and every factory-prefixed delete on record, and the
2026-10-15 note records content-installer doing exactly this sequence. The
client is the factory toolchain: high confidence, inferred.

## Q3. Is anything else stock missing?

The loss is limited to views, as far as cheap checks reach.

- **Dashboards.** One dashboard is on both 8.18.7 and 9.1.1 and absent from
  devel: `ff9493eb` "Cost/Consumer Layer/Chargeback (Business Application
  Price)". No audit line ever deleted it. Probably it never shipped on 9.0.2
  (inferred). The 12 dashboards the removal deleted exist on neither 8.18.7
  nor the 9.1.1 lab (`devel_9_1`). They are vCommunity's own (prod has them
  through upstream vCommunity).
- **Super metrics, reports, alerts, symptoms.** None of the 37 SMs, 11 report
  templates, 2 alert definitions or 5 symptom definitions the removal deleted
  exists on `devel_8_18` or `devel_9_1` (`GET /api/<type>/{id}`, all 404). The
  alert and symptom ids use the `VMWARE` adapter prefix, but their conditions
  are `vCommunity|` keys. They are pak content, not stock.
- **Other delete events.** Across the whole audit history, every other
  content delete on devel is factory, IDPS, Rubrik/MPB or probe content.
- **Side observation, not stock.** The 5 vCommunity symptom ids still answer
  `GET /api/symptomdefinitions/{id}` with 200 on devel, while
  `GET /api/symptomdefinitions?id=<id>` returns `totalCount: 0`. A stale
  by-id read after the delete. Not investigated.

## Q2. Recovery options (option (a) executed 2026-11-11, see "Restore performed")

**Are the definitions identical across versions?** For the 64, the 8.18.7
and 9.1.1 XML matches for 10 ids. The other 54 differ only in `Description`
text (8.18.7 appends "Source: vSphere Adapter" and some dashboard lists), except
for 2 that differ in content: `4d9b6ad6` and `524d0468` use `summary|version`
on 8.18.7 and `summary|version_4d` on 9.1.1. The 9.0.2 vSphere `describe.xml`
on devel defines `version_4d`, so the 9.1.1 key resolves on 9.0.2 (defined, but not populated on devel's hosts; see "Restore performed"). **9.0.2.0200's
own definitions differ from both:** the names in the delete line (the
definitions put back by the 10-14 upgrade) differ from the 8.18.7/9.1.1 titles
for 10 ids. Some of those are renames
(`23b3812d` "Configuration | VM Memory Share" against "Configuration | Complex
| VM Memory Share", `fcab0100` "Configuration | Cluster DRS Enabled" against
"DRS Enabled?"). One may be a different view (`9e427b59` "Configuration |
Cluster DRS Migration Threshold" against "Distribution of clusters by DRS
Automation Level"). So the views are version-specific in titles, and
possibly in content for a few. No 9.0.2 copy of the XML was found off the
instance.

**(a) Re-import from a 9.1.1 export.** A content-zip import of exactly the 64
ViewDefs, keeping their ids. This brings back every widget the stock
dashboards reference, because widgets bind by id. Risks:
- 10 views get the 9.1.1 title and maybe the 9.1.1 query, not 9.0.2.0200's.
- The 54 descriptions are the 9.1.1 text.
- The next 9.0.2 patch overwrites them with exact stock, as on 10-14.
- Reversible: delete those 64 ids again, or revert the snapshot taken first.

A recovery zip (sha256 `ed37b4fd...`, 64 ViewDefs; working data, not
retained in the repo) was built by a session script, `build_recovery.py`,
from the prod 9.1.1 export: the ViewDef elements are
copied byte for byte, the en/es/fr/ja property bundles are filtered to
`view.<id>.*`, the marker is devel's admin UUID, and `configuration.json` is
`{"type":"CUSTOM","views":64}`. It references no super metrics. prod carries
upstream vCommunity, but its copies of the 64 match 8.18.7 apart from the
differences above, so they are stock. A fresh export from `devel_9_1` (never
had vCommunity) would be the cleaner source.

**(b) The product's own restore.** Nothing found:
- `reference/docs/operations-api.json` and `internal-api.json` have no
  default-content reset (only the deprecated `/api/content/restore` for a
  user's uploaded backup), and `reference/docs/vcf9/` documents none.
- On the appliance the stock views are not plain files. They are not under
  `plugins/inbound/vmwarevi_adapter3/conf/` (no views directory) and not in
  any `*.xml`, `*.json` or `*.zip` under `/usr/lib/vmware-vcops` or
  `/storage/db/pakRepoLocal`. A recursive grep for a lost id found only UI
  JavaScript and a CEIP record. These searches had time limits, so a
  location they did not reach is not ruled out.
- The only mechanism seen to restore them is the core upgrade re-applying
  built-in content (10-14). Running an upgrade or reinstall to get that is a
  platform operation with far more reach than 64 views. Reaching it by
  removing the vSphere solution is ruled out: `pak-isunremovable-vendor-bug.md`.
- A UI "Reset Default Content" was not checked in the browser on 9.0.2. If it
  exists, what it would overwrite is unknown (inferred: all of the solution's
  content, including any edits to stock views).

**(c) Snapshot.** The devel VM's snapshot list, read from prod's VMWARE
resource properties and not checked in vCenter, has three entries, all named
2026-10-14: `pre-move-reip-20261014-1118`, `pre-move-offline-20261014-1123`
(cluster offline) and `post-move-reip-20261014-1350`. By name they sit after
the 10:57 CDT stock re-import and before the 10-15 removal, so they hold
exact 9.0.2.0200 stock. But `diskspace|snapshot|oldestSnapshotTimestamp`
reads 2026-11-11 16:30 UTC, which contradicts the names, so check creation
times in vCenter first. Reverting rolls devel back almost four weeks: Compliance
95 to 104, UniFi, Synology, the forks, accounts and everything since. Booting
it on the side to export the 64 views is possible but brings up a second copy
of the same cluster identity. Both are far more risk than the views are worth.

**Recommendation: (a).** devel exists to test function on 9.0.2. What is
broken is widgets that bind views by id. (a) fixes that in one reversible
import, and the next 9.0.2 patch writes exact stock over it. Steps as planned
(already run once on devel, see "Restore performed"; do not repeat there):

1. Snapshot the devel VM (lab rule).
2. Build the import zip. Either export ALL from `devel_9_1` and rebuild with
   `build_recovery.py <export_dir> ids-64.json 6844548499441080431L.v1
   <devel admin uuid> <out.zip>`, or build from a prod export as above. Confirm the marker
   name against a fresh devel export (issue #166).
3. `POST /api/content/operations/import?force=true`, multipart field
   `contentFile`. Poll `GET /api/content/operations/import` to `FINISHED`.
   Expect `VIEW_DEFINITIONS` imported 64, skipped 0
   (`api-surface/content_upload_methodology.md` §3).
4. Verify at the API: an ALL export shows `views: 851` (787 + 64), and the
   migrator `tree --json` walk of it drops from 63 distinct missing views to
   1 (`42194e98`, shipped dangling). The audit log shows a
   `VIEW_DEFINITION_IMPORT` of the 64 ids.
5. Verify rendered (done means seen working): open Configuration > Overview
   > Cluster / VM / ESXi / Network Configuration New, Performance > Provider >
   Cluster Performance New, Capacity > VM Capacity and Performance > Consumer
   > VM Performance. Select an object so the View widgets populate. No widget
   says "The view does not exist.".
6. Note the import in devel's baseline doc.

## Q4. Could it happen again?

Yes, by the same path, and it is not limited to devel:

- **Gap 1, at build time.** `vcfcf_managementpacks` `build-sdk` /
  `validate-sdk` loads bundled views, dashboards, reports and SMs with
  `enforce_framework_prefix=False` (`sdk_builder.py`, bundled-content loader,
  around lines 2075 to 2260). `content_naming: unprefixed` (#229) is allowed
  for ports. Nothing checks who owns a content **id**. A port can ship VMware's
  UUIDs, and the product treats them as the pak's.
- **Gap 2, at install and uninstall time.** `vcfcf_managementpacks install`
  does not check whether a bundled id already exists on the target and is
  owned by something else. That existing object is the overwrite on install
  and the deletion on uninstall. `uninstall_pak` guards `isUnremovable` and
  nothing else, and its docstring warns about built-in paks, not built-in
  content inside a custom pak.
- **The upstream pak has the same exposure.** prod (9.1.1) has upstream
  vmbro vCommunity installed. Its content carries the same 64 stock ids
  (verified in the reference copy). Uninstalling it from prod would delete
  those 64 stock views there too (inferred, same mechanism). Its install will
  also have replaced the stock definitions with vCommunity's until the next
  upgrade.
  (Correction 2026-11-12: the upstream pack carries 117 built-in view
  ids, not 64; 64 is the subset the factory's port shipped. See
  `2026-11-12-vcommunity-upstream-builtin-view-ids.md`.)
- **Name-based factory deletes (latent, not involved here).**
  `_uninstall_views` (`templates/install.py`), `ViewsHandler.delete`
  (`vcfcf_dashboards/handler.py`) and `cmd_delete_view` resolve by display
  name with no ownership check. They also keep one id per name, so with
  duplicate names the last one listed wins. A bundle whose view name equals a
  stock view's name, for example a `/extract` of a stock dashboard kept under
  stock names, would delete the stock view on uninstall. Not observed:
  every factory view delete on devel is prefixed.

Guards to add (tooling, then framework-reviewer):

1. `validate-sdk`/`build-sdk` refuse any bundled view, dashboard, report or
   SM id that appears in a stock-id manifest. Build the manifest from clean
   lab exports (8.18.7, 9.0.2, 9.1.1 first-boot), commit it as generated data
   under `knowledge/context/`, and refresh it per version. Allowed only with
   an explicit per-id waiver.
2. Pre-install collision check: for each bundled content id, `GET` it on the
   target. Refuse if it exists and was not installed by an earlier version of
   the same pak.
3. Pre-uninstall check: list the pak's bundled content ids from its pak file
   or registry entry. Refuse, or require `--accept-content-loss <ids>`, if
   any is in the stock manifest.
4. The name-based view/dashboard deletes skip anything that lacks the
   factory prefix or is not in the bundle's own id list.

## Restore performed (2026-11-11)

The recovery zip described in Q2, built from the `prod` export (9.1.1.0, which
runs upstream vCommunity; its copies of the 64 match 8.18.7 apart from
descriptions, per Q2), was imported on devel 9.0.2 with `force=true`: `imported=64, skipped=0, failed=0`, view
count 787 to 851, all 64 ids present, and every View widget on the 29 stock
dashboards that use them resolves again. All 64 render server-side
(`/internal/views/{id}/data/export`, HTTP 200).

What was not done, against the plan above: no VM snapshot was taken (the
safeguard was a pre-import content export of all 787 views, kept off-repo);
step 5, the browser pass over the named dashboards, was not done, so the
dashboards are verified at the API only and not seen working; no separate
baseline doc entry was written, this section is the record.

The definitions are the 9.1.1 ones, not the 9.0.2 originals, so the restore is
not exact:

- `9e427b59` is a different view in 9.1.1 ("Distribution of clusters by DRS
  Automation Level"; 9.0.2 had "Configuration | Cluster DRS Migration
  Threshold"). The "DRS Migration Threshold" widget on "Cluster Configuration
  New" now shows the automation-level distribution.
- `4d9b6ad6` and `524d0468` use host property `summary|version_4d`, which
  9.0.2 hosts do not carry (they have `summary|version`): one column is null,
  one distribution is empty.
- Nine ids carry their 9.1.1 names (for example `fcab0100` "DRS Enabled?"
  where 9.0.2 had "Configuration | Cluster DRS Enabled").
- Eleven views return a valid but empty result. Five are rule-violation
  distributions, plausibly empty because nothing violates; six trend views
  returning no series are unexplained.

An exact restore needs a 9.0.2 export of the same ids, which was not available.
