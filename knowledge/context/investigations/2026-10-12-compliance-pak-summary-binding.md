# Compliance build 88: World Summary did not bind (devel, 2026-10-12)

**Answer:** the World Summary dashboard never imported, so there was nothing
to bind. Devel's dashboard importer does not know the `Section` widget type;
when it meets an unknown type it tries to log a "widget will not be imported"
message, and that log line itself throws (`JSONObject["Title"] not found`),
which aborts the whole dashboard. The `dashboards.properties` binding step
runs after the import, so it never ran. Upgrade path, properties key, resource
kind id form, `hidden` flag and the share step are all ruled out.

**Instance:** devel, `lastbuildversion.txt` = VMware vCenter Operations Manager
9.0.2.0 Build 25137845 (`vrops-init-9.0.2.0-25137860`). Note that
`dashboard_widgets_alertvolume_section_viewdetails.md` recorded devel as 9.1.1
on 2026-08-25, so the lab has changed builds since then.

**Posture:** read only. UI Struts reads (`getDashboardList`,
`getDashboardConfig`, `getWidgetConfigs`, `getSummaryTabId`,
`getResourceKindList`, `solution.action getIntegrations`), root SSH for
`grep`/`sed` of logs, and one class pulled off-box for `javap`. Nothing was
created, changed or deleted. These are unsupported UI endpoints (the same tier
as `X-Ops-API-use-unsupported`), with no Suite API equivalent.

## Timeline (America/Chicago, 2026-10-12)

The install ran at 5:07 to 5:11 PM, not 5:15 PM. From
`analytics.audit-*.log`, `analytics-*.log` and `vcops-bridge.log` (stamped UTC
in the files):

| Local time | Event |
|---|---|
| 5:06:55 PM | `SOLUTION_INSTALL` "Triggering install succeeded. PakId: VCFContentFactoryCompliance-00088" (admin, UI) |
| 5:07:29 PM | `DistributedTaskInstallUninstallAdapters` "isForceInstall = true, isForceUpdateContent = true" |
| 5:08:32 to 5:08:39 PM | 8 report views imported (`VIEW_DEFINITION_IMPORT` succeeded) |
| 5:08:39 PM | `DASHBOARD_IMPORT` (ForceByName true), then `DASHBOARD_GROUP` (share) at 5:09:43 PM |
| 5:09:43 PM | `DASHBOARD_IMPORT`, **no share follows**; bridge ERROR at 5:09:44 PM (below) |
| 5:09:44 PM, 5:10:03 PM, 5:10:06 PM | three more `DASHBOARD_IMPORT`, each followed by `DASHBOARD_GROUP` |
| 5:11:10 PM | installer session logout |

That is five imports and four shares: one dashboard failed.

The failure (`vcops-bridge.log`, thread `DistTaskSolutionManagerDistributedTask`):

```
2026-10-12T22:09:44.105Z ERROR ... ImportExportManager.importDashboard - JSONObject["Title"] not found.
org.json.JSONException: JSONObject["Title"] not found.
  at org.json.JSONObject.getString(JSONObject.java:855)
  at com.vmware.vcops.bridge.server.ImportExportManager.importDashboard(ImportExportManager.java:1009)
  ...
  at com.vmware.vcops.bridge.server.DataRetrieverServer.importDashboard(DataRetrieverServer.java:7473)
  at com.vmware.vcops.bridge.plugin.server.SolutionManagerDistributedTask.installDashboardContent(SolutionManagerDistributedTask.java:1300)
  at ...SolutionManagerDistributedTask.installContent(SolutionManagerDistributedTask.java:821)
```

## Root cause (bytecode)

`ImportExportManager.class` was pulled from
`controller/plugins/vcops-bridge-server-1.0-SNAPSHOT.jar` and disassembled.
In the private
`importDashboard(JSONObject, String, List, boolean, boolean, boolean, boolean)`,
line 1009 is inside the per-widget loop:

```
type = WidgetDTONew.WidgetType.fromKey(widget.getString("type"))
if (type == null)
    logger.error("The widget with id" + id + " and title" + widget.getString("Title")
                 + " will not be imported in the \"" + tab.getName()
                 + "\" dashboard will as the widget type" + widget.getString("Type") + " is not found.")
```

The intent is to skip an unknown widget. But the message reads `"Title"` and
`"Type"` with capital letters, and the dashboard JSON only has `title` and
`type`, so `getString` throws. The exception escapes the dashboard, and the
installer moves on to the next directory without sharing or binding.

`WidgetDTONew$WidgetType` (in `common/lib/vcops-bridge-client-1.0-SNAPSHOT.jar`)
on this build has no `Section` entry. It has 47 constants, including Scoreboard,
PropertyList, View, MetricChart, AlertList and IntSummaryAlertVolume; zero
strings match "section". World Summary is the only one of the five dashboards
with a `Section` widget (widget `7b1f2093`, the 12-wide row 1 container). The
other four use only types the enum knows, and they imported.

## Evidence per question

1. **Did it import?** No. `getDashboardList` (180 dashboards, admin) returns
   four "[VCF Content Factory] Compliance ..." dashboards. World Summary
   (pak id `4e2c777e-9c6c-4c6a-bc16-ab55b6110f33`) is missing, and
   `getDashboardConfig?tabId=4e2c777e-...` returns `tabConfigs: []` with both
   `isTemplate=false` and `isTemplate=true`. The other four are hidden in the
   pak too and still appear, so the `hidden` flag is not the reason. No
   SUMMARY clone could exist, because the installer clones only after a
   successful import.
2. **getSummaryTabId(`002016vcfcf_complianceComplianceWorld`)** returned
   exactly `{}`: no `tabId`, so null, and no binding. `getResourceKindList`
   shows `ComplianceWorld` with `resourceKindTemplate: "Summary Detail"` (the
   default) and confirms the resource kind id
   `002016vcfcf_complianceComplianceWorld` (16 = len("vcfcf_compliance")).
3. **Why:** the unknown-widget crash above. Ruled out:
   - **Upgrade path:** the content step ran with force on (`isForceUpdateContent = true`), and the four other dashboards were re-imported with build 88 content. The live vCenter & Networking AlertList (`cc250d66`) has `type: ["15_21"]`, `depth: 4`, `alertDefinitions: []`, which matches pak 88. Pak 87 had `type: []`, `depth: 1` and pinned definitions.
   - **Properties key:** the file is plain LF ASCII, and the key `VCF_Content_Factory_Compliance_World_Summary` matches the directory name exactly. It was never reached.
   - **Share step:** it was never reached for this dashboard.

   `solution.action getIntegrations` shows the pak installed at version
   0.0.0.88. `getLatestInstalledSolutionStatuses` returned an empty body,
   which matches the known 9.0.2 behavior noted in `installer.py`.
4. **Fixes (none run):**
   - **bind-summary:** will not work, because there is no source dashboard to bind (it resolves by name). A content-zip import of the same JSON first would probably fail the same way. That is unverified: the content-import path may reach the same `importDashboard`, and checking would require a write.
   - **Fresh install (uninstall, then install 88):** will not work. The same parser rejects the same `Section` widget. It costs an uninstall, the adapter instances and their config, and the collection history.
   - **Smallest fix:** remove the `Section` widget from World Summary, or flatten it into plain widgets, then rebuild as build 89 and upgrade-install over 88. The upgrade path does import and bind (`forceUpdateContent` is true on upgrade, as shown above). Cost: one rebuild and one upgrade install, with the installer's content phase taking about 4 minutes. The other option is to target only builds whose enum has `Section`, which is not checked here. The 2026-08-25 smoke used qa 9.2 through bind-summary.

## Side observations

- The live "[VCF Content Factory] Compliance ESX Hosts" reports `shared: false` (`isShared: false`) while the other three report `true`. The installer shares every dashboard with Everyone, so this needs its own look and is not part of this defect.
- At 5:04:55 PM, two minutes before the install was triggered, a `maintenanceAdmin` session imported a dashboard (ForceByID false, ForceByName false) and deleted tab `3d84205c-45c8-4708-9a94-161a18443796`. It appears to be part of the upload phase. Not investigated.
