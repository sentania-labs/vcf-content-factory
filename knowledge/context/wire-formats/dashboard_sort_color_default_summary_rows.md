# Dashboard and view wire formats: default sort, lower-is-worse color, show-all-then-narrow, multiple summary rows

- Date: 2026-10-23 (api-explorer). Read-only research for issues #175,
  #176, #177, #168.
- Instances: profile `devel` = VCF Operations 9.0.2.0 (UI build
  `9.0.2.0200.25431135`); profile `devel_9_1` = 9.1.1.0 (Suite API only,
  see "Not done" at the end). Versions read from `GET /api/versions/current`
  on 2026-10-23.
- Nothing was created, changed, or deleted on any instance. Calls used:
  a CUSTOM content export of `VIEW_DEFINITIONS` (the factory's own
  `vcfcf_extractor` export helper), `GET /internal/views/{id}/data/export`,
  `POST /ui/dashboard.action` (`getDashboardConfig`, `getWidgetConfigs`),
  `POST /ui/utility.action getTopImportantMetrics`, `POST
  /ui/widgetScoreboard.action getMetricValues`, and `GET` of the UI's own
  JavaScript (`/ui/js/widgets/*.js`, `/ui/dist/js/app.part*.min.js`).

> **UNSUPPORTED ENDPOINTS.** `/internal/views/{id}/data/export` needs the
> `X-Ops-API-use-unsupported: true` header and Broadcom may change it
> without notice. The `/ui/*.action` calls are the web console's private
> Struts layer (UI session plus `secureToken`), not part of any API
> contract. Both were used here only to read; nothing in the factory
> should depend on them at install time.

## Summary

| Issue | Answer | Where the setting lives | Confidence |
|---|---|---|---|
| #175 View widget sort | The dashboard View widget has **no** sort key. Default sort is a per-column `sortCriteria` Property in the **view definition** XML (`true` ascending, `false` descending, absent none). | View XML, `attributes-selector` column Item | seen in export, plus live server render on 9.0.2 |
| #176 Lower-is-worse Scoreboard color | No flag exists. Write the three bounds in **descending** order (`yellowBound > orangeBound > redBound`) and the server colors lower values worse. The factory renderer already passes the triple through unchanged. | Widget `metric.resourceKindMetrics[]` entry | seen in export, plus live server replay on 9.0.2 |
| #177 Show all, narrow on selection | No "default resource plus receiver" mode exists on any widget. But an **AlertList** receiver with `selfProvider: false` already shows every matching alert until an interaction arrives, so setting the **provider** View widget's `selectFirstRow` to `false` gives exactly "all on load, narrow on click". This is the vendor's own `Cluster Performance` pattern. A **View** receiver does not fall back (it shows "resource not selected"). | Provider widget `config.selectFirstRow.selectFirstRow` | seen in export (vendor dashboard) plus UI source; on-screen render not checked |
| #168 Multiple summary rows | `summaryInfos` is a `List` of `Item`s, one per row, each with its own `displayName`, `aggregation`, and `attributeIndexes`. | View XML, `attributes-selector` Control | seen in export (summary and list presentations; list multi-row in vendor paks) plus live server render of the summary presentation; on-screen list multi-row not observed |

## #175: default sort for a View widget

### Finding

The dashboard View widget config carries no sort. The keys of all 407
View widgets in `reference/references/` (including inside zips) are
`viewDefinitionId, title, selfProvider, resource, traversalSpecId,
selectFirstRow, refreshInterval, refreshContent, isUpdatedView,
chartViewItems` plus occasional `widgetId, viewDetails, titleLocalized,
description, viewType`. None is a sort key. The only widget type with
`sortBy` / `sortByDir` in the whole corpus is HealthChart (35 of 35),
which matches what `render.py` emits today (line 1798).

The UI source confirms it. `Ext.vcops.dashboard.widget.View`
(`/ui/js/widgets/View.js`, 9.0.2) builds the data request in
`prepareRequestParams(controlsData, sortObj)` with `isAsc` and
`columnIndex` taken only from `sortObj`, and `sortObj` is set only by the
renderer's `updateview` event (the user clicking a header). On first load
both are sent as empty strings, so the server falls back to the view
definition.

The default sort is set in the **view editor**, per column: a "Sorting"
combo with three values, wired in `app.part0.min.js` as

```
data:[t.SORTING_NONE,{sortCriteria:!0,title:bundle["view.workspace.data.grid.column.metric.sorting.ascending"]},
      {sortCriteria:!1,title:bundle["view.workspace.data.grid.column.metric.sorting.descending"]}]
```

and saved as `metricData.sortCriteria = null` for None. So on the wire:
`sortCriteria="true"` is **ascending**, `"false"` is **descending**, and
the Property is absent for no sort.

### Verbatim wire fragment

From `reference/references/vmbro_vcf_operations_vcommunity/Management
Pack/content/reports/View - Collection01.xml`, view `ESXi on Maintenance
Mode` (`6d865efb-5dcd-496f-9a07-ced99f530142`), the one column with a sort
(whitespace collapsed, otherwise verbatim):

```xml
<Item><Value><Property name="objectType" value="RESOURCE"/><Property name="attributeKey" value="summary|parentCluster"/><Property name="isStringAttribute" value="true"/><Property name="adapterKind" value="VMWARE"/><Property name="resourceKind" value="HostSystem"/><Property name="rollUpCount" value="0"/><Property name="transformations"><List><Item value="CURRENT"/></List></Property><Property name="sortCriteria" value="true"/><Property name="isProperty" value="true"/><Property name="displayName" value="Cluster"/><Property name="addTimestampAsColumn" value="false"/><Property name="isShowRelativeTimestamp" value="false"/></Value></Item>
```

The Property sits after `transformations` and before `isProperty` /
`displayName`. Corpus counts for list views: 24 views with one sorted
column, 19 with two, 6 with three (the priority between several sorted
columns was not tested; column order is the likely tiebreak).

### Live confirmation (devel, 9.0.2, 2026-10-23)

The CUSTOM view export from devel contains `VM Cost Details v2.1`
(`8bdadca7-84e3-4a74-8bff-3be29f6d8e83`), whose column 0 `Monthly
Projected Cost` (`cost|effectiveProjectedTotalCost`) carries
`sortCriteria="false"`. `GET /internal/views/8bdadca7-.../data/export
?resourceId=<vSphere World>` returned 104 data rows; the 95 numeric values
are monotonically descending (440.30, 148.49, 130.88, ...), the 9 rows
with no value come last, and the summary row follows. So the server
applies the view-definition sort with no widget input.

### What the factory needs

- Renderer: emit `<Property name="sortCriteria" value="true|false"/>` on
  the chosen column Item(s) in `_xml_attribute_item`, in the position
  above. Today only the time-segment pseudo-column emits `sortCriteria`
  (always `false`, `render.py` line 636); regular columns never do.
- Loader: there is no column-level sort key today. The widget-level YAML
  keys `sort_by_column` / `sort_by_dir` named in #175 are not parsed
  anywhere in `src/` (they appear only in YAML comments under `content/`),
  and the dashboard loader has no unknown-key check on widgets, so they
  are silently ignored. Because the product stores sort on the view, the
  natural YAML home is the view column (for example `sort: asc|desc`);
  a widget-level key would have to be translated into the view, which
  breaks when one view is reused by several widgets.
- Consequence: an embedded view opens sorted for every dashboard that
  uses it. Two dashboards wanting different default orders need two views.

## #176: lower-is-worse colors on Scoreboard and MetricChart

### Finding

The Scoreboard / MetricChart per-metric entry has no direction flag. The
keys seen across 619 Scoreboard and 44 MetricChart metric entries in the
corpus are `colorMethod, handleOldColoring, id, isStringMetric, label,
labelLocalized, labelOrig, link, maxValue, metricKey, metricName,
metricUnit, metricUnitId, defUnit, orangeBound, redBound, resourceKindId,
resourceKindName, unit, yellowBound`. No `ascendingRange`, no invert key.

Direction is expressed by bound order alone. 15 corpus entries use
`colorMethod: 0` with descending bounds, all on lower-is-worse metrics
(certificate days remaining, free memory, health badge, host counts).

### Verbatim wire fragments

Broadcom community pack, `reference/references/vmbro_vcf_operations_vcommunity/Management
Pack/content/dashboards/VM Performance 2.0.json` (repo commit `0e534e5`),
Scoreboard `Memory Performance`:

```json
{
 "yellowBound": 512,
 "metricUnitId": "mb",
 "metricName": "Guest|Free Memory",
 "metricKey": "guest|mem.free_latest",
 "handleOldColoring": false,
 "link": "",
 "isStringMetric": false,
 "resourceKindName": "Virtual Machine",
 "label": "Free Memory",
 "resourceKindId": "resourceKind:id:0_::_",
 "orangeBound": 256,
 "unit": "MB",
 "id": "extModel93496-3",
 "redBound": 128,
 "colorMethod": 0
}
```

Community export, `reference/references/tkopton_aria_operations_content/SSLCheckFiles/tkopton-certificate-expiring-dashboard.zip`
(`dashboard/dashboard.json`), Scoreboard `SSL/TLS Remaining Validity in
Days`: `"colorMethod": 0, "yellowBound": 60, "orangeBound": 30,
"redBound": 15` on `UTILIZATION|ResultValue` (days until expiry).

### Live confirmation (devel, 9.0.2, 2026-10-23)

Replayed the widget's own two calls (`utility.action
getTopImportantMetrics`, then `widgetScoreboard.action getMetricValues`,
request shape from `/ui/js/widgets/Scoreboard.js` lines 87-96 and
294-305) for `cpu|usage_average` on HostSystem
`vcf-lab-mgmt-esx06.int.sentania.net`, latest value 7.68, with bounds
placed around that value:

| Bounds y / o / r | Order | Server `state` | `colorHex` |
|---|---|---|---|
| 17.68 / 27.68 / 37.68 | ascending | Normal | `#8ABF5B` |
| -12.32 / -2.32 / 17.68 | ascending | Immediate | `#EB953F` |
| -2.32 / -12.32 / -22.32 | descending | Normal | `#8ABF5B` |
| 17.68 / -2.32 / -12.32 | descending | Warning | `#EACC58` |
| 37.68 / 27.68 / 17.68 | descending | Critical | `#ED665A` |

With descending bounds the server colors a value at or below `yellow` as
Warning, at or below `orange` as Immediate, at or below `red` as Critical:
the mirror of the ascending rule in lesson
`scoreboard-partial-bounds-render-unknown`. Exact-boundary inclusivity in
the descending direction was not tested.

The same idea exists for list-view columns, where the editor derives the
flag from bound order: `boundChanged` sets `ascendingRange =
yellow > orange && orange > red` and disables the checkbox when all three
numeric bounds are set (`app.part0.min.js`). Widgets simply skip the flag.

### What the factory needs

- Renderer: nothing. `render.py` lines 1473-1476 and 1540-1543 copy
  `yellow_bound` / `orange_bound` / `red_bound` verbatim for
  `color_method: 0`, so a descending triple already renders correctly.
- Loader: already accepts a descending triple (the only checks are
  all-or-none on method 0 and no bounds on method 3). What is missing is
  intent and safety: the `MetricSpec` docstring (loader.py around line
  1028) says "Thresholds are ascending", which steers authors away from the
  working form. A cheap improvement is to document descending triples as
  lower-is-worse and reject a non-monotonic triple (for example
  `70 / 50 / 90`), whose behavior is undefined. An `ascending_range` /
  `invert_colors` YAML key is optional sugar that would only reorder
  nothing on the wire; it is not needed for the product.
- MetricChart: carries the same per-entry keys (12 corpus entries on
  `colorMethod: 0`). The descending replay was done on Scoreboard only;
  MetricChart threshold coloring in the descending direction is inferred.

## #177: show everything by default, narrow on an upstream selection

### Finding

There is no widget-level "default resource while also a receiver". Every
widget's `interactionChange` starts with `if (!this.selfProvider ||
this.skipSelfProvider)`, so a self-provider widget ignores in-dashboard
interactions, and a non-self-provider widget never reads `config.resource`
(View.js `widgetLoaded`: `configuredResource` is set only when
`selfProvider` is true).

`skipSelfProvider` is runtime state, not config. It becomes true only on
**dashboard-to-dashboard navigation**: `navigateDashboard` delivers
`[null, interactionType, arg1, arg2, null, !0]` to the target widgets,
and `preInteractionChange` calls `setSkipSelfProvider(arg4)`. In-dashboard
interactions pass through `proceedFireInteractionChange(e,t,i,a)`, which
forwards only four arguments, so `arg4` is always undefined there. So a
pinned (self-provider) widget does narrow when another dashboard navigates
to it, but never from a widget on the same dashboard.

What does work in-dashboard is the **receiver's own fallback** when no
interaction has arrived. `Ext.vcops.dashboard.widget.AlertList`
(`/ui/js/widgets/AlertList.js` lines 716-750, 9.0.2) `loadData` does not
check `selfProvider`. With no stored interaction and `mode` not `resource`,
it sends no `resourceIds` and only the widget's own filters (criticality,
type, status), so the list shows every matching alert. The only thing that
stops this initial load is `expectAutoSelectInteraction`, which the server
sets on the widget (`autoSelectInteraction`) when its provider will
auto-select. The list also has a "reset interaction" toolbar button that
clears the selection and goes back to all.

`autoSelectInteraction` on devel (from `getDashboardConfig`, 1622 widgets,
88 flagged): set only on receivers of **ResourceList** providers that
auto-select. It was not set on any receiver of a View provider, even where
the View has `selectFirstRow: true`. With a View provider, the narrowing
on load comes from the provider's `selectFirstRow` firing a real
interaction after the list has already loaded.

So the outcome #177 wants is reachable with keys the factory already
emits: provider View `selectFirstRow: false`, receiver AlertList
`selfProvider: false`, `mode: all`.

A **View** receiver has no such fallback: with no selected resource its
`validateWidget` shows `view.widget.resourceNotSelected` (View.js line
591). The pattern is per receiver type; it holds for AlertList, not View.

### Verbatim wire fragment

The vendor's `Cluster Performance` dashboard on devel (tab
`533e14ed-2796-4ead-a644-468beb6396f8`), read with `getWidgetConfigs` on
2026-10-23. Provider View `vSphere Clusters`:

```json
{"selfProvider": {"selfProvider": true}, "selectFirstRow": {"selectFirstRow": false}, "viewDefinitionId": "cd6c06c5-7ac5-4edc-a2c8-5b8777512d59", "resource": {"resourceId": "ba1fe374-23fa-4584-9ca5-705cf1c637b0", "traversalSpecId": "vSphere Hosts and Clusters-VMWARE-vSphere World", "resourceName": "vSphere World", "id": "Ext.vcops.chrome.model.Resource-2", "resourceKindId": "002006VMWAREvSphere World"}}
```

Receiver AlertList `Performance Alerts` (interaction `resourceId` from the
View above):

```json
{"alertAction": [], "alertImpact": [], "criticalityLevel": [2, 3, 4], "customFilter": {"excludedResources": null, "filter": [], "includedResources": null}, "depth": 1, "filterMode": "tagPicker", "mode": "all", "refreshContent": {"refreshContent": false}, "refreshInterval": 300, "relationshipMode": {"relationshipMode": [-1, 0]}, "resource": [], "selfProvider": {"selfProvider": false}, "state": [], "status": [], "tagFilter": null, "title": "Performance Alerts", "titleLocalized": "Performance Alerts", "type": ["15_19", "16_19", "17_19", "18_19", "19_19"]}
```

The factory's `[VCF Content Factory] Compliance Environment Overview`
(tab `155743b0-15e0-40e4-acd3-05f68f8684d4`) has the same AlertList shape
(`mode: all`, `selfProvider: false`, `type: ["15_21"]`, `depth: 4`); the
only difference is its provider View `Compliance by vCenter and Object
Type` has `selectFirstRow: {"selectFirstRow": true}`, which is why it
opens on the first vCenter's alerts.

### What the factory needs

- Renderer: nothing new. `selectFirstRow` is emitted from
  `w.select_first_row` (render.py lines 1268, 1361, 2288).
- Loader: already accepts `select_first_row` (bool, default `true`,
  loader.py line 2811). For the compliance case the change is content, not
  framework: `select_first_row: false` on `vcenter_object_type_view` in
  `content/sdk-adapters/compliance/dashboards/compliance-environment-overview.yaml`.
  The YAML comment there ("instead of sitting blank") predicts a blank
  list; the UI source says the AlertList loads all matching alerts instead.
- Optional framework guard: a validate-time warning when a View receiver
  is fed by a provider with `select_first_row: false`, since that View
  will open on "resource not selected".
- Not achievable on the wire: a self-provider widget that also narrows on
  a same-dashboard interaction. If a pinned View must narrow, the only
  product path is dashboard navigation (`dashboardNavigations`, see
  `dashboard_navigations.md`).

## #168: more than one summary row on a view

### Finding

`summaryInfos` is already a list in the product. Each `Item` is one
summary row with its own label, aggregation, and column subset. The view
editor's summary grid (`app.part0.min.js`) builds it with
`getValue: {summaryInfos: []}` and one push per grid row of
`{displayName, aggregation, attributeIndexes}`, and the same component is
used whether the presentation is `list` or `summary`.

### Verbatim wire fragments

Three rows, `reference/references/vmbro_vcf_operations_vcommunity/Management
Pack/content/reports/View - Set 2.xml`, view `VM Configured Size Summary`
(`69ec6689-a037-447b-926d-6efc4b1ba6db`, repo commit `cab88506`),
presentation `summary`:

```xml
<Property name="summaryInfos">
    <List>
        <Item>
            <Value>
                <Property name="displayName" value="Average"/>
                <Property name="aggregation" value="AVG"/>
                <Property name="attributeIndexes">
                    <List>
                        <Item value="0"/>
                        <Item value="1"/>
                        <Item value="2"/>
                        <Item value="3"/>
                    </List>
                </Property>
            </Value>
        </Item>
        <Item>
            <Value>
                <Property name="displayName" value="Largest"/>
                <Property name="aggregation" value="MAX"/>
                <Property name="attributeIndexes">
                    <List>
                        <Item value="0"/>
                        <Item value="1"/>
                        <Item value="2"/>
                        <Item value="3"/>
                    </List>
                </Property>
            </Value>
        </Item>
        <Item>
            <Value>
                <Property name="displayName" value="Smallest"/>
                <Property name="aggregation" value="MIN"/>
                <Property name="attributeIndexes">
                    <List>
                        <Item value="0"/>
                        <Item value="1"/>
                        <Item value="2"/>
                        <Item value="3"/>
                    </List>
                </Property>
            </Value>
        </Item>
    </List>
</Property>
```

(Indentation normalized; elements and attribute values verbatim.)

Two rows, `View - Set 3.xml`, view `vSphere Performance Profiling`
(`9911f98d-0e2a-4d4f-aefe-973e28ecf1cc`), presentation `summary`, inside
`<Control id="attributes-selector_id_390" type="attributes-selector"
visible="false">`, directly before the `pagination-control`:

```xml
<Property name="summaryInfos"><List><Item><Value><Property name="displayName" value="Average of all VMs"/><Property name="aggregation" value="AVG"/><Property name="attributeIndexes"><List><Item value="0"/><Item value="1"/><Item value="2"/></List></Property></Value></Item><Item><Value><Property name="displayName" value="Worst of all VMs"/><Property name="aggregation" value="MAX"/><Property name="attributeIndexes"><List><Item value="0"/><Item value="1"/><Item value="2"/></List></Property></Value></Item></List></Property></Control>
```

Corpus inventory (all of `reference/references/`, including the views
inside the `tvs/` vendor paks, corrected 2026-10-23 by the framework
review of #168; the first pass looked at loose files only and found 14):
78 distinct views carry `summaryInfos`. 14 of them are presentation
`list` views with several summary rows, in the Citrix XenDesktop, Oracle
EM, HPE and IBM Db2 paks under `reference/references/tvs/`; for example
`Citrix XenDesktop Desktop Instances List View`
(`CitrixVirtualAppsAndDesktops-7.0_4.0.0_b20200925.190422.pak`, three
rows SUM, AVG, MAX) and `Oracle Databases Overview`
(`OracleEnterpriseManager-9.0.0_b20231005.113304.pak` -> `adapters.zip`
-> `oem_adapter3/conf/reports/Oracle Database Instance Bottlenecks
Report.xml`, four rows MIN, MAX, AVG, DEVIATION). Aggregations across the
78: SUM 58, AVG 29, MAX 15, MIN 9, DEVIATION 1, COUNT 0.

### Live confirmation (devel, 9.0.2, 2026-10-23)

`vSphere Performance Profiling` is a built-in view on devel (used by the
`vSphere Performance Profiling` dashboard, widget `Summary of VM
Performance SLA`). `GET /internal/views/9911f98d-.../data/export
?resourceId=<vSphere World>` returned columns `1: "Average of all VMs"`
and `2: "Worst of all VMs"`, one per summary Item, with one row per
metric. A presentation `summary` view transposes: each summary row
becomes a column.

For a presentation `list` view, the single-row case renders as an extra
row with `"summary": true` and `objId` equal to the `displayName` (seen in
the `VM Cost Details v2.1` render above: `{"summary": true, "1":
3813.00..., "objId": "Total"}`). Several Items on a list view are seen in
vendor pak exports (inventory above); that they render as several such
rows is inferred from the shared editor component, not observed on
screen.

### What the factory needs

- Renderer: `_render_summary_infos` (render.py line 866) emits exactly one
  `<Item>`. It needs to loop over a list of specs, one `<Item><Value>` per
  spec with the three Properties in the order `displayName`,
  `aggregation`, `attributeIndexes`, all inside the single
  `<Property name="summaryInfos"><List>...</List></Property>`.
- Loader: `SummaryRow` is one dataclass and `ViewDef.summary` is
  `SummaryRow | None` (loader.py lines 260 and 477); `summary:` in YAML
  accepts `true` or one mapping (line 2637). It needs to accept a list of
  mappings, each with its own `display_name`, `aggregation`, `columns`.
  Keeping the single-mapping form as shorthand for a one-item list stays
  byte-identical to today's output.
- `COUNT` was not seen in any export's `aggregation`; the values seen are
  `SUM`, `AVG`, `MIN`, `MAX` and `DEVIATION` (one view, Oracle EM pak,
  "Standard Deviation" row).

## Not done, and why

- **9.1.1 (`devel_9_1`) replays.** The Scoreboard replay ran on 9.0.2
  only. The first 9.1 attempt logged in to the UI, then failed before
  logging out, which left an orphan UI session. Later logins returned
  `concurrentSessionDetected`. Forcing the login (`forceLogin=true`) would
  end any other session of that account, so it was not used. The session
  times out on its own; re-run the replay on 9.1 after that.
- **On-screen check of #177.** The AlertList fallback is read from the UI
  source and the vendor dashboard config, not from a rendered page. A
  30-second look at the vendor `Cluster Performance` dashboard on devel
  (does `Performance Alerts` list alerts before any cluster is clicked?)
  would confirm it.
- **On-screen render of a list view with two summary rows, and
  multi-column sort priority.** The XML shape is seen in vendor paks;
  confirming the rendered rows, or which sorted column wins, needs a
  throwaway view import, which this read-only brief did not allow.
