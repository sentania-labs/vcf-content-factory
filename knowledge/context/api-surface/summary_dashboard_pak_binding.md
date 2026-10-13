# Summary dashboard binding from a pak (`dashboards.properties`)

A management pack CAN bind one of its shipped dashboards to a resource
kind's Summary tab at install time. This corrects the hard negative in
`summary_dashboard_assignment.md` (2026-08-21), which was derived from
pak corpora and the UI layer only. The mechanism lives in the server-side
pak installer, not in `describe.xml`, not in `post-install.py`, and no
pak in the earlier 51-pak corpus happened to use it.

Established 2026-08-25 by decompiling the installer on three disposable
lab builds (CFR 0.152 run on the appliance JRE, output kept in the
session scratchpad, not committed):

| profile | build | `dashboards.properties` handling present |
|---|---|---|
| `qa`    | 9.2.0.0 pre-release build   | yes |
| `main`  | 9.2.0.0 pre-release build  | yes (same class list, plus one unrelated class) |
| `devel` | 9.0.0.0 pre-release build  | yes, `installDashboardContent` and `associateResourceKindDashboards` are byte-for-byte identical after decompilation |

So the feature exists at least since VCF Operations 9.0. Whether 8.x
had it was not checked (no 8.x appliance available; the 8.12-era HOL
paks in `reference/references/` do not ship the file, which proves
nothing either way).

## Where it lives

- Jar: `/usr/lib/vmware-vcops/controller/plugins/vcops-view-server-1.0-SNAPSHOT.jar`
- Class: `com.vmware.vcops.bridge.plugin.server.SolutionManagerDistributedTask`
  (methods `installContent`, `installDashboardContent`,
  `associateResourceKindDashboards`, `installFeatureContent`)
- Constant: `SolutionManagementConstants.DASHBOARDS_PATH_PROPERTIES = "dashboards.properties"`

`installSolution()` uploads the adapter zip(s) found at the pak root, waits
for ADAPTER_INSTALL to finish, and only if there were no errors extracts
the whole pak to a temp dir and calls `installContent(path, pakId)`. That
walks `content/` in a fixed order: localization, reports, **dashboards**,
alertdefs, symptomdefs, liqueryconfigs, liextractedfields, litemplates,
recommendations, supermetrics, policies, customgroups, georegions,
traversalspecs, txtwidgets, reskndwidgets, topowidgets, solutionconfigs,
feature. Installed ids are recorded in the KV store under
`SolutionContentNamespace` keyed by pak id, which is what uninstall and
`forceUpdateContent` use.

## File format (exact)

Path inside the pak: `content/dashboards/dashboards.properties`

Parsed with `java.util.Properties.load(FileReader)` (so `#` comments,
`key=value`, `key: value`, backslash escapes all apply; keys are
case-sensitive).

```
<dashboard-directory-name>=<AdapterKind>:<ResourceKind>[,<AdapterKind>:<ResourceKind>...]
```

- **Key** is the name of a subdirectory of `content/dashboards/`
  (`dashboards.getName()`), i.e. the same directory that holds the
  dashboard JSON and its `resources/`. It is not the dashboard's display
  name and not the JSON filename.
- **Value** is split on `,`; each part is split on `:` and must yield
  exactly two tokens or it is silently skipped (`objectTypes.size() != 2
  -> return`). Tokens are the raw adapter-kind key and resource-kind key
  as in `describe.xml` (`key` attributes), not display names.
- The `<dashboard-dir>=<AdapterKind>:<ResourceKind>` form is the
  documented one; the undocumented extra is that one directory can bind
  to several resource kinds via a comma list.

Decompiled core (9.2, identical on 9.0):

```java
File dashboardsPropertiesFile = new File(dashboardsDir + File.separator + "dashboards.properties");
...
boolean isTemplate = dashboards.getName() != null && dashboards.getName().startsWith("GenericTemplates");
ResultDto importResult = this.getDataRetriever().importDashboard(
    Zip.from(dashboards).getBytes(), true, this.forceUpdateContent,
    !isTemplate ? adminUserId : null,
    this.adapterKindKey != null ? this.adapterKindKey : solutionPakId);
...
this.getDataRetriever().shareDashboards(Collections.singletonList(everyoneGroupId), dashboardResult, true, adminUserId);
if (dashboardsProperties == null || dashboardsProperties.get(dashboards.getName()) == null) continue;
String[] split = dashboardsProperties.get(dashboards.getName()).split(",");
for (String objectType : objectTypes) {
    this.associateResourceKindDashboards(tabIdMap.keySet().iterator().next(), objectType, adminUserId);
}
```

## Install-time behavior, step by step

For every subdirectory of `content/dashboards/`:

1. The directory is zipped and imported as the **admin user's** dashboard
   (`importDashboard(..., adminUserId, adapterKindKey|pakId)`), with
   `force = this.forceUpdateContent`. Exception: a directory whose name
   starts with `GenericTemplates` is imported with `userId = null`, which
   the importer treats as "this is a template", and it is neither shared
   nor bound.
2. It is shared with the **Everyone** group.
3. If `dashboards.properties` has an entry for the directory name, then
   for each `AdapterKind:ResourceKind`:
   - `resourceKindId = IdGeneratorUtil.toID(adapterKind, resourceKind)`,
     which is the same `"0020" + %02d(len(adapterKind)) + adapterKind + resourceKind`
     id documented in `summary_dashboard_assignment.md`.
   - The **first** tab id of the directory's import result is used
     (`tabIdMap.keySet().iterator().next()`; a `HashMap`, so if one
     directory contains more than one dashboard the choice is not
     deterministic. Ship one dashboard per bound directory.)
   - Unless the id is an OOTB dashboard template, the installer calls
     `saveDashboardAsTemplate(tabId, name, TemplateSection.SUMMARY, adminUserId, true)`.
     That makes a **copy**: new tab id, new widget ids, `userId = null`,
     `templateSection = SUMMARY`, name de-duplicated against existing
     templates, widget state copied. The association map entry is
     `resourceKindId -> templateTabId` (the copy), persisted through
     `setDashboardAssociation(...)` on the controller.
   - The pak's imported dashboard (the one the user sees under
     Dashboards) is therefore NOT what renders on the Summary tab; a
     SUMMARY-section template clone of it is. Editing the visible
     dashboard afterwards does not change the Summary page. This is the
     same code the UI's `associateResourceKindDashboards` Struts action
     runs, so the two mechanisms produce identical state.

Unlike the UI action, the installer does **not** delete a previous
template that was bound to the same resource kind; it overwrites the map
entry and leaves the old SUMMARY template orphaned. Re-installing the
same pak with `forceUpdateContent` re-imports (force) and re-binds,
creating another template copy each time (`getUniqueTabName` appends a
suffix). Expect template clutter after repeated installs.

## Unknown widget type aborts the import, so the binding never runs

Seen live on devel (9.0.2.0 Build 25137845) on 2026-10-12. When
`WidgetType.fromKey` returns null, `ImportExportManager.importDashboard`
tries to log a skip message using `getString("Title")` and
`getString("Type")`, with capital letters, which a dashboard JSON does not
have. The resulting `JSONException` aborts the whole dashboard. There is no
share and no `dashboards.properties` binding, and the installer quietly
moves on to the next directory. The `Section` widget type does not exist on
that build. Any pak dashboard whose bound dashboard uses a widget type
unknown to the target build therefore fails silently. Evidence:
`../investigations/2026-10-12-compliance-pak-summary-binding.md`.

## The Summary clone can carry no widget config (9.0.2)

Seen live on devel (9.0.2.0 Build 25137845) on 2026-10-13 with compliance
pak 89. The binding ran, and the Summary tab showed the right layout and
titles, but every widget fell back to its defaults. The cause: the importer
parks each widget's non-empty config in `WidgetDTONew.configKey`, still
holding import placeholders, and a per-user `DashboardImporter` thread
resolves it into `config` on a 10-minute tick. The installer's
`saveDashboardAsTemplate` runs seconds after the import, so the SUMMARY
clone copies widgets that still have `config = null`. Nothing ever resolves
the templates key (user `null`). This also means the "widget state copied"
statement above holds only for a source that has already resolved. No
YAML or renderer change can fix it. Re-bind (`bind-summary`) once the source's widgets
all show `isLoading: false`. To check a clone, read
`getDashboardConfig?isTemplate=true`: `isLoading: true` with no
`widgetConfig` means it is unresolved. Do not rely on `getWidgetConfigs`,
which is scoped to the user and returns `{}` for every template. Evidence:
`../investigations/2026-10-13-compliance-summary-clone-config-loss.md`.

### 9.0.2 WidgetType keys (complete list)

Read on 2026-10-12 from `WidgetDTONew$WidgetType` in
`/usr/lib/vmware-vcops/common/lib/vcops-bridge-client-1.0-SNAPSHOT.jar`
on devel, VCF Operations 9.0.2.0 Build 25137845 (decompiled with `javap`,
key strings taken from the enum's static initializer). The enum has 47
constants, not the 48 the investigation note gives (48 is the count of
static fields including the synthetic `$VALUES` array). `fromKey` matches with case-sensitive
`String.equals` against the Key column, so the dashboard JSON widget
`type` field must match that string exactly. The enum name is the Java
constant and never appears in dashboard JSON.

| # | Key (dashboard JSON `type`) | Enum name |
|---|---|---|
| 1 | `ResourceList` | `RESOURCE` |
| 2 | `MetricPicker` | `METRIC_PICKER` |
| 3 | `MetricChart` | `METRIC_CHART` |
| 4 | `Scoreboard` | `SCOREBOARD` |
| 5 | `Heatmap` | `HEAT_MAP` |
| 6 | `HealthChart` | `HEALTH` |
| 7 | `ResourceRelationship` | `RESOURCE_RELATIONSHIP` |
| 8 | `ResourceRelationshipAdvanced` | `RESOURCE_RELATIONSHIP_ADVANCED` |
| 9 | `ProblemAlertsList` | `PROBLEM_ALERT_LIST` |
| 10 | `ParetoAnalysis` | `PARETO_ANALYSIS` |
| 11 | `TextDisplay` | `TEXT_DISPLAY` |
| 12 | `AlertList` | `ALERT` |
| 13 | `IntSummaryStress` | `INT_SUMMARY_STRESS` |
| 14 | `Skittles` | `SKITTLES` |
| 15 | `SparklineChart` | `SPARKLINE` |
| 16 | `ScoreboardHealth` | `SCOREBORD_HEALTH` |
| 17 | `View` | `VIEW` |
| 18 | `EnvironmentStatus` | `ENVIRONMENT_STATUS` |
| 19 | `TagPicker` | `TAG_PICKER` |
| 20 | `ParetoChart` | `PARETO_CHART` |
| 21 | `Forensics` | `FORENSICS` |
| 22 | `WeatherMap` | `WEATHER_MAP` |
| 23 | `ContainerOverview` | `APPLICATION_OVERVIEW` |
| 24 | `Geo` | `GEO` |
| 25 | `ContainerDetails` | `APPLICATION_DETAIL` |
| 26 | `RollingViewChart` | `ROLLING_VIEW_CHART` |
| 27 | `MashupChart` | `MASHUP_CHART` |
| 28 | `IntSummaryHealth` | `INT_SUMMARY_HEALTH` |
| 29 | `IntSummaryWorkload` | `INT_SUMMARY_WORKLOAD` |
| 30 | `IntSummaryAnomalies` | `INT_SUMMARY_ANOMALIES` |
| 31 | `IntSummaryFaults` | `INT_SUMMARY_FAULTS` |
| 32 | `IntSummaryRisk` | `INT_SUMMARY_RISK` |
| 33 | `IntSummaryTimeRemaining` | `INT_SUMMARY_TIME_REMAINING` |
| 34 | `IntSummaryCapacity` | `INT_SUMMARY_CAPACITY` |
| 35 | `IntSummaryEfficiency` | `INT_SUMMARY_EFFICIENCY` |
| 36 | `IntSummaryWaste` | `INT_SUMMARY_WASTE` |
| 37 | `IntSummaryDensity` | `INT_SUMMARY_DENSITY` |
| 38 | `IntSummaryAlertVolume` | `INT_SUMMARY_ALERT_VOLUME` |
| 39 | `IntSummaryCurrentPolicy` | `INT_SUMMARY_CURRENT_POLICY` |
| 40 | `IntSummaryEnvironment` | `INT_SUMMARY_ENVIRONMENT` |
| 41 | `ActionsResult` | `ACTIONS_RESULT` |
| 42 | `TopologyGraph` | `TOPOLOGY_GRAPH` |
| 43 | `PropertyList` | `PROPERTIES` |
| 44 | `WorkloadBalance` | `WORKLOAD_BALANCE` |
| 45 | `ClusterSettings` | `CLUSTER_SETTINGS` |
| 46 | `RecommendedActions` | `RECOMMENDED_ACTIONS` |
| 47 | `LogAnalysis` | `LOG_ANALYSIS` |

Not in this list, so rejected by the 9.0.2 importer: `Section`. Of the 14
widget types the factory renderer (`src/vcfcf_core/dashboards/render.py`)
can emit (ResourceList, View, TextDisplay, Section, Scoreboard,
MetricChart, HealthChart, ParetoAnalysis, AlertList, ProblemAlertsList,
IntSummaryAlertVolume, Heatmap, PropertyList,
ResourceRelationshipAdvanced), `Section` is the only one absent from
9.0.2. A dashboard targeting 9.0.x must not carry a Section widget.

## Uninstall behavior

`removeContent` deletes the tracked dashboard ids (`deleteDashboardTabs`
as admin and as template owner `null`) but the SUMMARY template copy has
a different id that is never recorded in `SolutionContent`, and the
association map is **not** touched for `dashboards.properties` bindings
(the `associationMapResourceKindIds` bookkeeping exists only for the
`feature.properties` mechanism below). After uninstall the resource kind
still points at the template clone. The UI's "Use Default" (Manage
Summary Dashboards) is the way to clear it; the installer never does.

## The `disabled: true` and summary-folder claims

- `disabled` is a plain per-tab flag persisted with the dashboard
  (`DashboardTabDTONew.isDisabled`), read by the dashboard list/search
  (`DashboardSearchEntity`) and by per-user shared-dashboard state. The
  Summary tab path never consults it: `getSummaryTabId` returns whatever
  id is in the association map and the SPA loads that id directly. The
  `disabled` therefore hides the source dashboard from the list without
  affecting Summary rendering, and doubly so because Summary renders the
  template clone, not the flagged source.
- `namePath` is honoured by the importer (`DashboardManager` prefixes
  the importing group's folder and appends the dashboard's own
  `namePath`), so the summary-dashboard folder path is a folder convention only.
  There is no such folder string anywhere in the server jars or the SPA:
  the folder name is a content convention, not code.

## Sibling mechanism: `content/feature/feature.properties`

Same class, `installFeatureContent`. Keys are `AdapterKind:ResourceKind`,
values are ignored. Each key's resource kind id is mapped in the same
association map to the **pak id** (spaces stripped) instead of a tab id.
On the read side, 9.2's `getSummaryTabId` now returns
`{tabId, isDashboard, pluginExist}`: `isDashboard` is true when the
value parses as a UUID; otherwise the SPA treats the value as a plugin
key and mounts an Angular plugin component (`addPluginComponent`) for
the Summary tab, falling back to the native `ResourceSummaryBuilder`
with a "deprecated page" toast when the plugin is absent. These ids ARE
tracked and removed on uninstall. This is how the new VCF-native
summary tabs ship; it is not a dashboard and is out of scope for the
factory. It exists on the 9.0 devel build too.

## 9.2 SPA delta vs the 9.1 notes

- `RESKND_ASSOCIATION` in `app.part4.min.js` is still static: 51
  entries on 9.2, same first keys (`002006VMWAREVirtualMachine` ...).
- `getSummaryTabId` moved from `app.part6` to `app.part4` and now
  branches three ways (dashboard UUID / plugin key / native), see above.
  The `002016AmazonAWSAdapter` prefix is hard-forced to `tabId = null`
  server-side.
- No `isTemplate` or `disabled` logic on the Summary path.

## Field check: no installed pak uses it yet

`find / -name dashboards.properties` on all three appliances: zero
hits. The installed solutions that ship `content/dashboards/`
(several Broadcom first-party packs) bind nothing. `feature.properties` is likewise absent.
The mechanism exists in the product, but no shipped 9.2 pak on these
builds exercises it.

## What this means for the factory

- A `.pak` (Tier 1 MPB or Tier 2 SDK) can carry the binding by adding
  `content/dashboards/<dir>/<dashboard>.json` plus
  `content/dashboards/dashboards.properties` with `<dir>=<AK>:<RK>`.
  The SDK builder (`sdk_builder.py`) emits exactly that line per bundled
  dashboard with `summary_for`; a dashboard bound to several kinds (YAML
  list or comma string, loader-normalized) gets the comma-joined value
  `<dir>=<AK>:<RK>,<AK>:<RK>`, which is the installer's own split shape
  (comma, then exactly two colon tokens each). The loader rejects
  whitespace-bearing or duplicate entries before they can reach the file.
  The content-import zip path (Suite API) still cannot: that path does
  not run `SolutionManagerDistributedTask`.
- Whether the MPB builder or the SDK pak template passes an arbitrary
  `content/dashboards/` tree through untouched is a separate question
  for `tooling` / `sdk-adapter-author`; the earlier
  `v20-step5-silent-drop.md` note about a SAN pak's `dashboards.properties`
  was a misread (that pak ships `resources.properties` files only; the
  local copy confirms it).
- Runtime not exercised: the code was read, not run. Before relying on
  it, repackage a small pak with one bound dashboard on `main`, install, read
  `getResourceKindList?appendDetailPageMappings=true` and
  `getSummaryTabId`, uninstall, then clear the binding via the UI
  because uninstall will not).
