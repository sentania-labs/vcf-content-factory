# What makes an imported dashboard deferred, and can a pak bind a complete Summary clone on its own (devel 9.0.2, 2026-10-13)

**Answer:** on VCF Operations 9.0.2.0 Build 25137845, deferral is
**unconditional**. Every import parks every widget config that is not
empty or `{}`, whatever it references, and the dashboard JSON has no flag
or marker that skips this. Only a background importer thread, one per user
id, resolves parked config. The pak installer clones the bound dashboard
into a SUMMARY template within seconds of importing it, in the same loop
iteration, and nothing on an on-prem 9.0.2 instance ever starts the
importer for templates afterwards. **No change to the dashboard JSON or to
`dashboards.properties` can make the installer's clone complete on 9.0.2.**

The clone is not dead, only unresolved. `saveDashboardAsTemplate` copies
the parked config (`configKey`), the tab's `entryKeys` and
`importComplete=false` into the template, so a templates importer pass
would finish it. A pak could reach that state only through an
`adapter_post_script` that runs the server's summary-template import
(`vcopscliImportSummaryDashboard` -> `DashboardManager.addDashboardSummaryTemplates`).
That is the smallest in-pak change that could work. Three links in that
chain are unverified (see "Smallest change"), so it is a candidate, not a
finding.

**Instance:** devel, 9.0.2.0 Build 25137845. Pak:
`vcfcf_sdk_compliance.0.0.0.89.pak`, installed at 9:08:54 AM.

**Posture:** read only. Bytecode was disassembled with `javap -c -p` from
class files already copied off devel earlier today
(`ImportExportManager`, `DashboardImporter`, `DashboardManager`,
`DashboardCache`, `DashboardAction`, `WidgetDTONew`, and
`SolutionManagerDistributedTask`, `DataRetrieverServer`, `VCOPSCLIManager`
from the jars in scratch). `DataRetrieverUtils` was extracted from the
`vcops-bridge-client` jar that was already in scratch. Nothing new was
pulled from the appliance. One read-only UI session ran on devel at
10:56 AM (`getDashboardList`, `getSummaryTabId`,
`getDashboardConfig?isTemplate=true` on the clone). Nothing was created,
changed or deleted, so there was nothing to clean up. No decompiler was
available, so the Java below was reconstructed by hand from `javap`
output. Bytecode offsets are given so it can be checked.

## 1. The condition that parks widget config

`ImportExportManager` has a single dashboard JSON import path. Both public
`importDashboard(byte[] ...)` overloads parse the bytes and call the
private `importDashboard(JSONObject, userId, shareWith, shareNewOnly,
allowDuplicates, forceByName, forceById)`. A null byte array skips parsing
and only pokes the importer (see section 2).

```java
// private importDashboard(JSONObject ...), offsets 13-29, 2632
if (json.isNull("dashboards") || json.isNull("entries")) {
    addErrorToResult(..., _tr("Incorrect file uploaded."));   // no import at all
    ...
}
...
tab.setEntryKeys(entries != null ? entries.toString() : null);   // 947-963, always non-null here
...
// per widget, 1552-1732
String widgetConfig = widget.get("config").toString();
JSONObject cfg = null; String rim = null;
try { cfg = new JSONObject(widget.get("config").toString());
      rim = cfg.getString(RES_INTERACTION_MODE.getKey()); } catch (Exception ignored) {}
if (cfg != null && rim != null && (rim.contains("\\") || rim.contains("/"))) {
    cfg.put(RES_INTERACTION_MODE.getKey(), ""); widgetConfig = cfg.toString(); // log "Incorrect input..."
}
if (widgetConfig != null && !widgetConfig.isEmpty() && !widgetConfig.equals("{}")) {
    w.setConfigKey(widgetConfig);      // parked: config stays null, isLoading = true
} else {
    w.setConfig(widgetConfig);         // only "" or "{}" is stored directly
}
```

- `entries` is mandatory. Without it the file is rejected, so every
  imported tab gets a non-null `entryKeys`.
- The park/store choice tests only the config string's emptiness. It does
  not look at whether the config holds `{{...}}`-style or
  `resourceKind:id:0_::_` placeholders, resource ids, view ids, or nothing
  resolvable at all. A View widget whose only setting is a literal
  `viewDefinitionId` is parked exactly like a Scoreboard full of
  placeholders.
- `config: null` becomes the string `"null"` and is parked. A missing
  `config` key throws `JSONException` and aborts the whole dashboard.

`DashboardManager.addDashboardTabs` (called with `isImport = true` from
`importDashboardTabs`) then sets the tab flag. Offsets 834-879 of
`addDashboardTabs_aroundBody54`:

```java
if ((isImport || (userId == null && (templateSection == SUMMARY || templateSection == ADAPTER_DEFAULT)))
        && tab.getEntryKeys() != null) {
    tab.setImportComplete(false);
} else {
    tab.setImportComplete(true);
}
```

Every import is `isImport`, and every import has `entryKeys`, so every
imported tab starts with `importComplete = false`. The factory JSON's own
`"importComplete"` field is never read: `ImportExportManager` has no
reference to `ImportComplete` at all.

## 2. What the background thread resolves, and what starts it

`ImportExportManager.importDashboardTabs` (always called with
`scheduleImport = true` from the import path, offset 2566):

```java
result = dashboardManager.addDashboardTabs(tabs, states, true, userId, forceByName, forceById);
if (scheduleImport) synchronized (dashboardImporterMap) {
    DashboardImporter imp = dashboardImporterMap.get(userId);
    boolean newDashboardCreated = tabs != null && tabs.size() > 0;
    if (imp == null || !imp.isAlive()) {
        dashboardImporterMap.remove(userId);
        imp = new DashboardImporter(dashboardManager, this, globalKvStore, userId, newDashboardCreated);
        dashboardImporterMap.put(userId, imp);
        imp.start();                     // run() does its first pass immediately
    } else {
        imp.update(newDashboardCreated); // resets restoreAttempts; does NOT wake the sleep
    }
}
```

`DashboardImporter.run()`:

```java
while (!stop) {
    boolean isTemplate = userId == null || userId.equals("0");
    if (isTemplate) userId = null;
    allDashboardsTransferred = true;
    processDashboardsImport(dashboardManager.getDashboardDTO(userId, null), isTemplate);
    if (allDashboardsTransferred || !newDashboardCreated || restoreAttempts == 144) {
        stop = true; restoreAttempts = 0;            // thread exits
    } else {
        restoreAttempts++; Thread.sleep(600000);     // 10 minutes, up to 144 times (24 h)
    }
}
```

`processDashboardsImport` handles each tab with `entryKeys != null &&
!isImportComplete()`. It sends the tab's `entries` to
`ImportExportManager.fromEntryKeys` (adapter kinds, resource kinds,
resources, collectors, maintenance schedules, attribute keys, all by key
or name). It then string-replaces every `internalId` with the real id
inside each widget's `configKey`. If an internalId the config references
was not found, the widget stays parked, the tab stays incomplete,
`allDashboardsTransferred = false`, and a `DashboardImportErrorMap` entry is
written. Otherwise it calls `setConfig(resolved)` and `setConfigKey(null)`.
When every widget resolves, it calls `setImportComplete(true)` and
`setEntryKeys(null)`, then `storeDashboardDTO`.

**What this means:**

- The thread is per user id. The pak installer imports as the super
  admin (`getAdminUserId()` = `getVcopsSuperAdminUserId()`), so it shares
  the admin's thread.
- A thread stays alive as long as **any** tab under that user id cannot
  resolve, for up to 24 hours, and every new import resets the 24-hour
  counter. On devel at 10:56 AM, `getDashboardList` showed **9 admin
  dashboards with `isLoading: true`**: the two factory MSSQL/Oracle
  Query Performance dashboards, Rubrik Overview, and six cost/showback
  dashboards. That is why the admin thread ticks every 10 minutes
  indefinitely (the 9:02, 9:12 and 9:22 AM ticks in the earlier
  investigation), and why every pak dashboard import on devel waits up to
  10 minutes to resolve.
- On an instance with no stuck admin dashboards, the thread exits after a
  clean pass, so the next import starts a fresh thread that resolves
  immediately. Even then it runs asynchronously, racing the installer's
  share-and-clone of the same directory (next section). The outcome is
  not guaranteed on any instance.
- **No import flag skips parking.** `forceByName`, `forceById` and
  `allowDuplicates` only decide skip or replace in `addDashboardTabs`.
  The parking branch uses none of them. A template import (`userId`
  null or `"0"`) parks the same way, but it starts or pokes the
  **templates** importer (`getDashboardDTO(null)` reads the templates
  key).
- The UI action `scheduleImport` (`DashboardAction.execute`, offsets
  2302-2437) does call `importDashboard(null, true, false, "0", null)` and
  then the same for the super admin, which pokes both the templates and
  admin importers. It is gated on `WebConstants.isSaasMode()` and
  `UserContextSaaS`, so on-prem it does nothing.

## 3. The clone already carries the parked config. Nobody triggers its resolution

`SolutionManagerDistributedTask.installDashboardContent`, per directory
(offsets 261-562):

```java
String adminUserId = getAdminUserId();
ResultDto r = getDataRetriever().importDashboard(Zip.from(dir).getBytes(), true,
        forceUpdateContent, adminUserId, adapterKindKey != null ? adapterKindKey : pakId);
...
getDataRetriever().shareDashboards(singletonList(everyoneGroupId), idMap, true, adminUserId);
if (props != null && props.get(dir.getName()) != null)
    for (String objectType : props.get(dir.getName()).split(","))
        associateResourceKindDashboards(idMap.getTabIdMap().keySet().iterator().next(), objectType, adminUserId);
```

`associateResourceKindDashboards` (offsets 155-351):

```java
boolean ootb = DataRetrieverUtils.ootbDashboardTemplateIds.contains(tabId);
DashboardSummaryDTO s = getDataRetriever().getUserDashboardSummaries(ootb ? null : adminUserId, singletonList(tabId), false);
String templateId = ootb ? tabId
        : saveDashboardAsTemplate(tabId, s.getDashboardTabs().get(0).getName(), TemplateSection.SUMMARY, adminUserId).getfirst();
associationMap.put(IdGeneratorUtil.toID(adapterKind, resourceKind), templateId);
putGlobalValue("associationMap", new DashboardAssociationMap(associationMap));
```

The private `DashboardManager.saveDashboardAsTemplate(tab, name)` (offsets
0-282) sets a new tab id, a unique name, `userId = null`, a new id on each
widget, and remapped interactions, then calls `addDashboardTab` and
`storeDashboardDTO(..., getTemplatesKey())`. It **never touches
`configKey`, `config`, `entryKeys` or `importComplete`**. A clone taken
while the source is parked therefore keeps everything a templates importer
pass needs to finish it. Live confirmation at 10:56 AM: the clone
`4cfb2eb2-261e-4142-8467-f1de963a533e` is still the bound Summary tab, with
tab `isLoading: true` and all six widgets `isLoading: true` with no
`widgetConfig`, 1 hour 47 minutes after install.

So saveDashboardAsTemplate does not need to change. It already copies
the side field. What is missing is **a templates-key importer run after
the clone exists**. On on-prem 9.0.2 only one thing starts one: an
`ImportExportManager.importDashboard` call with `userId` null or `"0"`
and real bytes. `DashboardImporter` is constructed in exactly one place
(`importDashboardTabs`), so there is no startup or restart path. The
callers with a null user are:

| Caller | Reachable from a pak? |
|---|---|
| `DashboardManager.addDashboardSummaryTemplates(Map<resourceKindId, byte[]>, force)`, via `DataRetrieverServer.addDashboardSummaryTemplates` and the CLI method `VCOPSCLIManager.importSummaryDashboard` (`DataRetrieverServer.vcopscliImportSummaryDashboard`) | Only from a script (section 5) |
| `DashboardAction` `scheduleImport` kick | SaaS only |
| Installer `GenericTemplates*` directory | **Not on this build** (section 4) |

`addDashboardSummaryTemplates` is worth quoting because it is the
server's own complete binding path (offsets 136-362 of `_aroundBody56`):

```java
String previous = associationMap.get(resourceKindId);
DashboardIdMap r = importExportManager.importDashboard(bytes, null /*userId*/, null, false, false, force, null);
String templateTabId = r.getTabIdMap()...first().getfirst();
associationMap.put(resourceKindId, templateTabId);
if (previous != null) deleteDashboardTemplate(previous);
...
kvStoreManager.putGlobalValue("associationMap", new DashboardAssociationMap(associationMap));
```

It imports the dashboard **directly as a template**, with no clone. It
binds that template, deletes the previously bound template (this would
remove a broken installer clone), and because `userId` is null it starts
or pokes the templates importer. A fresh templates importer resolves that
template on its first pass. The same pass would also resolve any orphaned
installer clone still waiting under the templates key.

`DataRetrieverUtils.ootbDashboardTemplateIds` is a hard-coded set of seven
VMware ids (`"1"`, `ef513f5d-...`, `19ee88b7-...`, `3a34a9e7-...`,
`b29ed707-...`, `e8d72407-...`, `2c77ee7f-...`), filled in the static
initializer and never added to anywhere else. Borrowing one would hijack
a VMware template, and it would not work anyway, because the installer
imports under the admin key while the OOTB branch looks the tab up under
the templates key.

## 4. `GenericTemplates*` does not exist on 9.0.2 Build 25137845

`summary_dashboard_pak_binding.md` quotes an `isTemplate =
dir.getName().startsWith("GenericTemplates")` branch, from a 2026-08-25
CFR decompile of 9.2 pre-release and 9.0 pre-release builds. The 9.0.2 GA
`installDashboardContent` above has no such branch. It always passes
`getAdminUserId()`. The string `GenericTemplates` appears in **none** of
the four jars in scratch (`vcops-view-server`, `vcops-bridge-server`,
`vcops-bridge-client`, `vcops-platform`; byte search of every class). On
this build a `GenericTemplates*` directory is just another admin
dashboard, shared and bindable. Section 3 of the earlier
`2026-10-13-compliance-summary-clone-config-loss.md`, which said a
`GenericTemplates*` directory starts a templates importer in the pak
installer, does not hold for 9.0.2.

On builds that do have the branch (9.2 pre-release, per the 2026-08-25
note), a `GenericTemplates*` import would start a templates importer.
Whether it then resolves the clone depends on `File.listFiles()` order
(unsorted) and on whether that thread is still alive when the clone is
written. It works reliably only if the generic template is deliberately
left unresolvable so that the thread keeps ticking every 10 minutes for
24 hours, which is a hack. Untested, and not recommended.

## 5. Other in-pak mechanisms

- **`feature` / `feature.properties`:** the 9.0.2 `installContent` order
  is localization, reports, dashboards, alertdefs, symptomdefs,
  liqueryconfigs, recommendations, supermetrics, policies, customgroups,
  georegions, traversalspecs, txtwidgets, reskndwidgets, topowidgets,
  solutionconfigs, compliance scorecards. There is no feature step on
  this build, and no content type other than dashboards calls a dashboard
  API (full `DataRetrieverInterface` call list taken from the installer
  bytecode).
- **`adapter_post_script` (manifest.txt):** this is the only in-pak hook
  that runs code. Per `../cleanroom-spec/spec/16-platform-install-and-signing.md`
  (field-confirmed on devel 9.0.2), CASA runs `APPLY_ADAPTER` and then
  `APPLY_ADAPTER_POST_SCRIPT` as sequential, non-overlapping phases, and
  it does this for UI and API installs alike. The pak 89 manifest has
  `"adapter_post_script": {"script": ""}`. Older vendor paks used
  install scripts that called `ops-cli.py dashboard import admin <file>
  --share all --force` (`../api-surface/summary_dashboard_assignment.md`),
  which shows that ops-cli can be called from an install script without
  interactive credentials.

## Pak JSON versus the materialized source

Compared: the pak 89 World Summary `dashboard.json` widget `config`
objects against the source dashboard's resolved `getWidgetConfig` output
captured earlier today (`4e2c777e`, after the 9:12:31 AM importer tick).

| Widget | Difference |
|---|---|
| Scoreboard (4 metric rows) | `metric.resourceKindMetrics[*].resourceKindId`: pak `resourceKind:id:0_::_`, live `002016vcfcf_complianceComplianceWorld` |
| MetricChart | same placeholder-to-id swap in `metric.resourceKindMetrics` |
| PropertyList (1 row) | same placeholder-to-id swap |
| View x2, AlertList | none (no placeholders; `viewDefinitionId`, `type: ["15_21"]` are literal) |
| all six | live adds `titleLocalized` (server-generated) |

The only substantive difference is the placeholder-to-id swap that the
importer performs. Shipping the real id would change nothing, because
parking is unconditional (section 1). The View and AlertList widgets have
no placeholders and lost their config on the clone anyway, which is
direct evidence of that.

## Smallest change that could let the pak bind a complete Summary by itself

**Inside the installer's own `dashboards.properties` path: none exists on
9.0.2.** These five facts, all from the code above, close it off:

1. parking is unconditional, and the JSON has no opt-out;
2. the clone is taken synchronously in the same loop iteration as the
   import;
3. resolution is asynchronous. On any instance where the admin has one
   stuck dashboard (devel has nine), resolution waits up to 10 minutes,
   and on a clean instance it is still a race;
4. the clone keeps its parked state, but on on-prem 9.0.2 the installer
   never starts the templates importer that would finish it, and
   nothing else does;
5. `GenericTemplates*` and the OOTB-id bypass are not usable on this
   build.

**Smallest in-pak candidate (unverified): an `adapter_post_script` that
runs the server's summary-template import for the World Summary.** For
example, an ops-cli call reaching `vcopscliImportSummaryDashboard(bytes,
force=true, "vcfcf_compliance", "ComplianceWorld")`, with the World
Summary JSON shipped next to the script. That one call:

- imports the dashboard as a template under the templates key (no clone);
- rebinds `002016vcfcf_complianceComplianceWorld` to it and deletes the
  broken installer clone;
- starts the templates importer, which resolves the new template, and
  any stray clones, on its first pass.

The `dashboards.properties` line can then be dropped, or kept as a
harmless fallback. The script deletes whatever template it binds over.
This is still a rebind, but it ships inside the pak and runs during the
CASA pipeline, so a UI install gets it too.

Unverified links, each a cheap check before any build:

1. Whether the 9.0.2 `ops-cli.py` exposes a verb that maps to
   `vcopscliImportSummaryDashboard`, and its argument form. ops-cli is
   Python on the appliance and is not in scratch; reading it needs one
   read-only file copy.
2. Whether `APPLY_ADAPTER` finishes `installContent` (the dashboard
   imports) before `APPLY_ADAPTER_POST_SCRIPT` starts. The pak 89
   `casa_pak_history_VCFContentFactoryCompliance-00089.json` phase stamps
   against the 9:09:52 to 9:10:50 AM dashboard audit lines would answer
   it. This also needs one read-only appliance read.
3. Whether the template that `addDashboardSummaryTemplates` imports
   renders correctly on the Summary tab. It never calls
   `setTemplateSection(SUMMARY)`, unlike the clone path. One
   disposable-lab install, then `getDashboardConfig?isTemplate=true`
   showing `isLoading: false` and a `widgetConfig` on all six widgets,
   would prove it.

If any of these fails, the remaining options are outside the pak: the
factory `bind-summary` after materialization (already rejected by
Scott), or a Broadcom fix that makes the installer clone resolvable.
For example, start the templates importer after
`associateResourceKindDashboards`, or bind through
`addDashboardSummaryTemplates` instead of cloning.

All endpoints referenced here are unsupported internal surfaces (the UI
Struts tier and the bridge RMI/CLI), the same tier as
`X-Ops-API-use-unsupported`. There is no Suite API equivalent.
