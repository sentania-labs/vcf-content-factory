# Compliance build 89: World Summary Summary-tab clone has no widget config (devel, 2026-10-13)

**Answer:** the SUMMARY template clone was taken before the server had
finished importing the source dashboard's widget config, and nothing ever
finishes it for templates. On 9.0.2 the dashboard importer does not store a
widget's config directly. It parks the raw config (still holding import
placeholders such as `resourceKind:id:0_::_`) in a side field
(`WidgetDTONew.configKey`) and leaves `config` empty. A background
`DashboardImporter` thread, one per user, swaps the resolved config in later.
On devel that thread runs every 10 minutes. The pak installer clones the
dashboard into a SUMMARY template a few seconds after the import, so the
clone copies six widgets that still have `config = null`. The template lives
under the templates key (user `null`), which only the admin's importer
thread ever looks at, so the clone stays unresolved. Every widget then
renders with its type defaults, all six of them, the PropertyList included.
The "resource-kind-scoped config vs default config" idea is ruled out: a
9.0.2 widget has exactly one config JSON, with no branch per resource kind.
**No change to the dashboard YAML or the renderer can fix this.** The
smallest fix is to re-bind after the source has resolved (`bind-summary`),
which runs the same clone on configured widgets.

**Instance:** devel, VCF Operations 9.0.2.0 Build 25137845. Pak:
`dist/vcfcf_sdk_compliance.0.0.0.89.pak` (its World Summary `dashboard.json`
is byte-identical to the scratch copy that was read, sha256 prefix
`aa9fc7de58061141`).

**Posture:** read only. UI Struts reads (`getDashboardConfig`,
`getWidgetConfigs`, `getWidgetConfig`, `getSummaryTabId`, `getDashboardList`)
and root SSH for `grep` of the logs. Classes were copied off-box with
`unzip -p`/`cat` and disassembled with `javap`: `DashboardManager`,
`DashboardImporter`, `DashboardCache` and `WidgetUtils` from
`controller/plugins/vcops-bridge-server-1.0-SNAPSHOT.jar`, `WidgetDTONew`
from `common/lib/vcops-bridge-client-1.0-SNAPSHOT.jar`,
`ui/WEB-INF/classes/.../DashboardAction.class` and `ui/js/dashboard/Dashboard.js`.
`ImportExportManager` was reused from the 2026-10-12 scratch. Nothing was
created, changed or deleted. These are unsupported UI endpoints (the same
tier as `X-Ops-API-use-unsupported`), with no Suite API equivalent.

## Timeline (America/Chicago, 2026-10-13)

The audit log (`analytics.audit-*.log`) and `vcops-bridge.log` are stamped
in UTC. The local times are:

| Local time | Event |
|---|---|
| 9:08:54 AM | `SOLUTION_INSTALL` PakId `VCFContentFactoryCompliance-00089` (admin) |
| 9:09:52 AM to 9:10:50 AM | five `DASHBOARD_IMPORT` (ForceByName true) by `maintenanceAdmin`, each followed by a share |
| **9:10:17 AM** | `DASHBOARD_ADD_TEMPLATE` TemplateName "[VCF Content Factory] Compliance World Summary", SourceTabId `4e2c777e-...`. This is the `dashboards.properties` binding clone. |
| 9:12:30 AM | the `DashboardImporter` thread (`Thread-274401`, the only importer thread in the log) runs its 10-minute tick. Earlier ticks ran at 9:02 AM, and later ones at 9:22 AM. |
| **9:12:31 AM** | that tick logs `keysByEntryType = {adapterKind=[vcfcf_compliance], resourceKind=[ComplianceWorld]}`, the World Summary's exact `entries`, and resolves the **source**. It does not show up again, so the source is now import-complete. |
| 9:30 AM | re-read: the clone's six widgets still have `isLoading: true` and no `widgetConfig`. Two importer ticks have passed since the install, and the clone is still untouched. |

The clone was taken 2 minutes 14 seconds before the source's config was
resolved.

## What the clone carries versus the source

`getSummaryTabId(002016vcfcf_complianceComplianceWorld)` returns
`{"tabId": "4cfb2eb2-261e-4142-8467-f1de963a533e"}`.

`getDashboardConfig` was called for the source with `isTemplate=false` and
for the clone with `isTemplate=true` (the clone returns no tab with
`isTemplate=false`):

| Field | Source `4e2c777e` | Clone `4cfb2eb2` |
|---|---|---|
| name, description, `isHidden_`, `isShared`, `mpName` | same | same |
| widget ids, keys, titles, gridster x/y/w/h, height | same six widgets | **same six ids** (`219a6a78`, `3cc87c7f`, `1b391233`, `d80fdcf8`, `63879fa9`, `2a7eeaee`) |
| `tabInteractions` (View `3cc87c7f` to AlertList `d80fdcf8`) | present | present, same ids |
| per-widget `isLoading` | `false` on all six | **`true` on all six** |
| per-widget `widgetConfig` / `isPreconfigured` | not emitted (user dashboard path) | **absent** on all six |
| tab `isLoading` | `false` | `true` |

How to read that (from the disassembled `DashboardAction.loadDashboardConfig`):

- `isLoading` is set to `widget.getConfigKey() != null`.
- For a template tab (`tab.getUserId() == null`) or an OOTB template id, the
  action emits `widgetConfig: <config>` plus `isPreconfigured: true`
  **whenever `widget.getConfig() != null`**. The clone is a template and
  emits neither, so for every clone widget `config == null` and
  `configKey != null`.

The SPA (`Dashboard.js getWidgetConfig`) treats `isLoading` widgets as
"configuration not finished". That is the hourglass beside every widget
title in the screenshot (bundle key `dashboard.config.widgetLoadingTip`,
"widget configuration is not complete"). With no `widgetConfig`, it falls
back to `{title: bundle['widgetTitle_' + key]}`, so each widget renders its
type's defaults:

| Widget | Source config (resolved) | Clone renders |
|---|---|---|
| Scoreboard "Environment Compliance" | 4 `Rollup\|Environment\|*` metrics, `resourceKindId 002016vcfcf_complianceComplianceWorld` | stock badges plus the object's default KPI set |
| MetricChart "Environment Score Trend" | `avg_score`, `non_compliant` | Total Anomalies, Badge\|Compliance (defaults) |
| View x2 | `viewDefinitionId` e4838292... / 32491ab8... | "The widget is not configured. Select a view to render." |
| AlertList "Open Compliance Alerts" | `type: ["15_21"]`, `depth: 4`, criticality 2,3,4 | unfiltered adapter alerts |
| PropertyList "Scan" | one row, `Summary\|last_scan_timestamp` labelled "Last Scan" | **also defaulted**: three property rows (Su..., VC..., VC...), not the one configured row, and the label "Last Scan" is gone |

The brief's reading that the PropertyList kept its config is wrong: it lost
it like the others. It happens to show a `Summary|...` property because the
default PropertyList lists the object's properties.

`getWidgetConfig` (singular) on each clone widget returns only the empty
fallback (`{"title": "Scoreboard"}`, `{"title": "View"}`,
`{"title": "Metric Chart"}`, `{"title": "Alert List"}`,
`{"title": "Property List"}`). The source returns the full config.

**Caution for future probes:** `getWidgetConfigs` / `getWidgetConfig` look
the tab up under the *session user's* dashboards
(`getUserId()`, overridden only for locked shared tabs through
`sharedTabInfoMap`). A template tab lives under the templates key
(`dashboardTemplates`, user `null`), so these two endpoints return `{}` or
the fallback for **any** template, configured or not. The evidence that
holds up is `getDashboardConfig?isTemplate=true`: there `isLoading` and the
presence of `widgetConfig` tell you directly.

## Why the config drops (bytecode)

1. **Import parks config in `configKey`.** In `ImportExportManager.importDashboard`
   (per widget, around bytecode offset 1552 to 1735), the widget's
   `config` JSON goes to `widgetConfig`. If it is non-null, non-empty and not
   `"{}"`, the code calls `widget.setConfigKey(widgetConfig)`. Otherwise it
   calls `widget.setConfig(widgetConfig)`. Any real config therefore goes
   to `configKey` with its import placeholders still in it
   (`resourceKind:id:0_::_` and so on), and `config` stays null.
2. **Resolution is deferred to a per-user thread.** After `addDashboardTabs`,
   `ImportExportManager` looks up `dashboardImporterMap[userId]`. If that
   thread is alive it calls `update(true)`, and if not it starts a new
   `DashboardImporter(…, userId, …)`. `DashboardImporter.run` loads
   `getDashboardDTO(userId)` (with `userId` null or `"0"` it reads the
   templates key instead). For each tab with `entryKeys` and
   `!isImportComplete()`, it maps internal ids to real ids
   (`fromEntryKeys`), rewrites each widget that has a `configKey` into
   `config`, sets `configKey = null` and `importComplete = true`, then
   sleeps `600000` ms (10 minutes). `update()` does not interrupt the sleep.
3. **The installer clones immediately.** `SolutionManagerDistributedTask`
   imports the directory, shares it, then calls `saveDashboardAsTemplate`.
   On 9.0.2 that is `DashboardManager.saveDashboardAsTemplate(tabId, name,
   TemplateSection, userId)`, 4 args, audited `DASHBOARD_ADD_TEMPLATE`.
   The private worker gives the tab a new tab id and a unique name, sets
   `userId = null`, gives each widget a new id, remaps interactions and
   stores the result under `getTemplatesKey()`. It copies the
   `WidgetDTONew` objects as they are, with `config` null and `configKey`
   pending.
4. **Nothing resolves templates.** The only importer thread is the admin's,
   and it processes the admin's dashboards. A templates-key importer is
   started only when an import runs with `userId = null`. In the pak
   installer that is a directory named `GenericTemplates*`. The bridge log
   since 7:42 AM shows only `Thread-274401`.

Side observation: `saveDashboardAsTemplate` gives the clone's widgets fresh
UUIDs, yet the source and the clone report identical widget ids today. The
likely explanation is that the clone was built from the same cached
`WidgetDTONew` objects as the source tab, and the importer later persisted
the source with those mutated ids. This is an inference, not verified.
Either way, the documented "new widget ids" behavior in
`summary_dashboard_pak_binding.md` cannot be seen from the outside on this
build.

## The resource-kind-scoped config idea: ruled out

The rendered World Summary JSON in pak 89 has one `config` object per
widget. Metric rows name their kind through
`resourceKindId: "resourceKind:id:0_::_"`, a placeholder resolved through
the dashboard-level `entries.resourceKind` block. There is no per-kind or
"default" branch in the factory output, and none in the 9.0.2 server code
that reads widget config (`WidgetDTONew` holds one `config` string and one
`configKey` string). Emitting a second copy under a resource-kind key would
be ignored, and it would still be parked in `configKey` at import. Writing
real ids instead of placeholders would not help either, because the parking
is unconditional for any non-empty config.

The stock SUMMARY templates were not read. They are OOTB ids
(`DataRetrieverUtils.ootbDashboardTemplateIds`), take the same
`widgetConfig` inline branch, and are installed with resolved config, so
they do not hit this. The HostSystem smoke dashboard
("[VCF Content Factory] Summary Widget Smoke (HostSystem)") is not installed
on devel (`getDashboardList`, 181 dashboards; HostSystem has no summary
binding). Per `2026-08-25`, it was bound on qa 9.2 with `bind-summary`, a UI
`associateResourceKindDashboards` call made long after import. By then the
source was resolved, which is consistent with it rendering correctly.

## Smallest fix, and the evidence that would prove it

**No YAML or renderer change helps.** The race is between the installer's
synchronous clone and the server's 10-minute config resolution, and a pak
cannot reorder them.

1. **Re-bind after resolution (one action, needs Scott's go because it is a
   write):** first confirm that every source widget reports
   `isLoading: false` in `getDashboardConfig?tabId=4e2c777e-...`. It does
   now. Then run `python3 -m vcfcf_dashboards bind-summary --profile devel
   --dashboard "[VCF Content Factory] Compliance World Summary"`. That calls
   `associateResourceKindDashboards`, which runs the same
   `saveDashboardAsTemplate`, but now on widgets whose `config` is resolved.
   Per the 2026-08-25 decompile (9.2, not re-checked on 9.0.2), the UI
   action also deletes the template previously bound to that kind, which
   would remove the dead clone `4cfb2eb2`.
   **Proof:** `getSummaryTabId` returns a new tabId. Then
   `getDashboardConfig?tabId=<new>&isTemplate=true` must show `isLoading:
   false`, `isPreconfigured: true` and a `widgetConfig` carrying the
   source's metrics, `viewDefinitionId`s and `type: ["15_21"]` on all six
   widgets. Finally, the rendered Summary tab must show no hourglasses, the
   four Rollup tiles, both views and only compliance alerts.
2. **Make it durable (tooling):** either (a) keep `dashboards.properties`
   but have the install flow run `bind-summary` once the bound dashboard's
   widgets all report `isLoading: false` (poll, up to about 10 minutes plus
   margin), or (b) drop `dashboards.properties` for 9.0.x targets and bind
   only after install. (a) keeps a pak-only install from regressing, and
   the cost is an orphan template per install, the same as today. Either
   way, `bind-summary` should refuse to bind while the source has any
   `isLoading: true` widget.
3. **Not recommended, untested, and since ruled out:** the 9.0.2 installer
   has no `GenericTemplates*` branch at all
   (`2026-10-13-dashboard-import-deferral-trigger.md`). Shipping a `GenericTemplates*` directory
   would start a templates-key importer, which *might* resolve the clone if
   the clone kept the source's `entryKeys` and `importComplete=false`.
   It depends on directory order and the 10-minute sleep, and it was not
   checked.

Open: whether a node or service restart starts a templates-key importer
(the `restoreAttempts` / `allDashboardsTransferred` logic hints at a startup
path). Whether pak installs on 9.1/9.2 lose the same race also needs one
install with a bound dashboard, followed by the `isTemplate=true` read above.
