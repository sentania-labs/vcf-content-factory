# Dashboard widgets: Alert Volume, Section, `viewDetails`, Scoreboard gauge

**Date:** 2026-08-25
**Instances:** qa (VCF Operations 9.2.0.0) primary; devel (9.1.1.0) parity check.
**Method:** enumerated every dashboard on both instances through the UI
Struts layer (`/ui/dashboard.action` `getDashboardList` ->
`getDashboardConfig` + `getWidgetConfigs` per tab), pulled a Suite API
content export (`POST /api/content/operations/export`, scope ALL,
`DASHBOARDS`) for the export form, and read the un-minified widget sources
that ship on the appliance under
`/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/js/widgets/` (widget,
`editors/`, `components/gridster/GridsterPanel.js`). No content was created
on either instance; nothing to clean up.

Verbatim samples (RULE-017): `reference/docs/extracted/dashboard-widgets/`
- `qa-9.2.0-export-alertvolume-section-viewdetails.json`: Suite API export
  of four qa dashboards (Alert Volume, Section, `viewDetails` populated);
  four widgets describing unreleased features were removed from the
  built-in health dashboard, see the directory README.
- `vendor-template-Home.json`, `vendor-template-ComputeOps-dashboard.json`:
  Broadcom's own dashboard templates shipped on the appliance
  (`webapps/ui/dashboards/templates/`), which use all three features.

**Supportability:** everything below is UI-layer / content-zip wire format,
not a public API contract. The `/ui/*.action` endpoints need a UI session
and `X-Requested-With: XMLHttpRequest`; they are unsupported and may change
between releases. Nothing here needs `X-Ops-API-use-unsupported` (that is
the Suite API internal-endpoint header); the export endpoint is public.

---

## 1. Alert Volume widget (`IntSummaryAlertVolume`)

### Identity

| Surface | Value |
|---|---|
| Add Widget palette | "Alert Volume" |
| Layout `key` (getDashboardConfig) / export `type` | `IntSummaryAlertVolume` |
| Ext class | `Ext.vcops.dashboard.widget.IntSummaryAlertVolume` (extends `WidgetBase`) |
| Editor class | `Ext.vcops.dashboard.widget.editor.IntSummaryAlertVolume` |
| Interaction registry | receives `resourceId` (incoming only); provides nothing |
| Data call at render | `POST alertVolume.action` `mainAction=getAlertsCount`, `resourceId`, `traversalSpecId`, `dateRange=last7Days` (hard-coded in `Ext.vcops.alert.AlertVolume`) |

### Config shape (the whole thing)

There is **no time window, no severity filter, no chart option** in the
stored config. The editor exposes exactly: title, description, refresh
content on/off, refresh interval, self provider on/off, and (when self
provider is ON) a single-object picker. The 7-day window is fixed in the
component and the chart always shows all criticalities. This was the same
on qa 9.2 and devel 9.1, and the vendor Home template stores the same keys.

`getWidgetConfigs` entry (qa, built-in "Environment Health Summary",
self provider ON, pinned to vSphere World):

```json
{
  "title": "Alert Volume in the Environment",
  "titleLocalized": "Alert Volume in the Environment",
  "refreshContent": {"refreshContent": true},
  "refreshInterval": 300,
  "selfProvider": {"selfProvider": true},
  "resource": {"resourceId": "<resource uuid>", "resourceName": "vSphere World"}
}
```

Resource binding is a **single object literal**, not an array, and only
the `resourceId` / `resourceName` keys (compare Scoreboard/View which use
`resource: []` lists). When self provider is OFF the editor writes
`"resource": null` and the key may be omitted entirely (vendor Home
template: `refreshContent`, `refreshInterval`, `selfProvider`, `title`
only).

Export form (content zip `dashboard/dashboard.json`, same widget; note the
resource id is symbolized to an `entries.resource` placeholder):

```json
{
  "tabId": "36fc9547-60b9-40ae-bf53-b19c921788b0",
  "collapsed": false,
  "id": "8789982e-628a-4755-a959-fbe98500baa7",
  "gridsterCoords": {"w": 12, "x": 1, "h": 10, "y": 12},
  "state": "",
  "type": "IntSummaryAlertVolume",
  "title": "Alert Volume in the Environment",
  "config": {
    "refreshInterval": 300,
    "resource": {"resourceId": "resource:id:0_::_", "resourceName": "vSphere World"},
    "refreshContent": {"refreshContent": true},
    "selfProvider": {"selfProvider": true},
    "title": "Alert Volume in the Environment"
  },
  "height": 0
}
```

with the matching `entries.resource[]` item
`{"name": "vSphere World", "internalId": "resource:id:0_::_", "resourceKind": ..., "adapterKind": ...}`.

Minimal authoring example, self provider OFF (fed by an Object List / View
selection):

```json
{
  "collapsed": false,
  "id": "<uuid>",
  "gridsterCoords": {"w": 4, "x": 1, "h": 6, "y": 1},
  "state": "",
  "type": "IntSummaryAlertVolume",
  "title": "Alert Volume",
  "config": {
    "title": "Alert Volume",
    "refreshContent": {"refreshContent": false},
    "refreshInterval": 300,
    "selfProvider": {"selfProvider": false}
  },
  "height": 0
}
```

Dashboard-level layout entry as `getDashboardConfig` returns it (gridster
fields are flat here, nested under `gridsterCoords` in the export):

```json
{"tabId": "...", "isLoading": false, "collapsed": false, "gridsterX": 1,
 "gridsterY": 12, "gridsterW": 12, "gridsterH": 10, "id": "...",
 "title": "Alert Volume in the Environment", "key": "IntSummaryAlertVolume",
 "height": 0}
```

### Self Provider OFF behaviour (confirmed from source)

`interactionChange` in the widget: when `selfProvider` is false and an
incoming `resourceId` interaction arrives with exactly one resource, the
widget sets `this.resource = {resourceId, resourceName}` and reloads.
Zero or more than one selected resources are ignored (no reload). With
self provider ON, `widgetLoaded` reads `config.resource` and ignores
interactions. So yes, it inherits the page object through the standard
interaction wiring (`widgetInteractions` / `tabInteractions`), and the
receiving side type is `resourceId`. The Home template uses exactly this:
Alert Volume with `selfProvider:false` fed by a Datacenter picker.

---

## 2. `viewDetails` ("Details URL", the VIEW DETAILS link)

### Where it lives

- Every widget config carries `viewDetails` (`EditorBase.getWidgetConfig`
  trims and writes it whenever the editor has the field; default `""`).
- `getDashboardConfig` layout entries also surface it (`"viewDetails": "..."`
  next to `key`/gridster fields) when non-empty, and the Section widget
  config carries it too (GridsterPanel copies `title`, `description`,
  `viewDetails` into each section config).
- On qa and devel exactly one dashboard populates it (built-in
  "VCF Operations Health", Scoreboard "License Server").

### Rendering / click behaviour (`WidgetBase.createViewDetailsBottomBar`)

A bottom toolbar (`itemId: viewDetailsBottomBar`) with a link-styled
button "View Details" is added to **every** widget and hidden unless
`viewDetails` is truthy. The click handler is the entire syntax contract:

```js
if (key.startsWith('http') || key.startsWith('https')) {
    window.open(key);                       // absolute URL: new window/tab
} else {
    Ext.vcops.alert.Utility.navigateToRelativePath(event, key);
}
// Utility:
navigateToRelativePath: function (event, url) {
    if (vcfClientSdk) {
        event.preventDefault();
        const path = url.startsWith('/vcf-operations/') ? url.replace('/vcf-operations', '') : url;
        vcfClientSdk.navigate(path);         // Angular shell router, same tab
        return false;
    }
}
```

Consequences:

1. **Two accepted forms only.** Absolute `http(s)://...` (opens a new
   window) or a **relative Angular shell route** starting with `/ui/...`
   (navigates in place). An optional `/vcf-operations` prefix is stripped,
   so `/vcf-operations/ui/...` and `/ui/...` are equivalent. Anything else
   (`dashboard.action?...`, `#/dashboard/...`, bare `ui/...`) is handed to
   the router verbatim and will not resolve.
2. **No placeholder substitution.** The value is stored trimmed and used
   as-is; there is no `%resourceId%`, `{resourceId}` or `${...}` expansion
   anywhere in `js/widgets` or the Angular bundle (grepped both). A link to
   "the current object" is therefore impossible; links are static.
3. The relative branch depends on `window.vcfClientSdk`, which the Angular
   host (`webapps/vcf-operations`, `vcf-client-sdk.js`) injects into the
   legacy iframe via `initializeClientSdk` on normal standalone product
   UI. Outside that host (raw `/ui/index.action` in a bare browser) a
   relative link is a no-op.

### Route prefix: `operate`, not `operations`

The 9.2 and 9.1 Angular bundles both define the dashboard route as
`/ui/operate/dashboards/dashboards;tabId=...` and the object page as
`/ui/operate/inventory;mode=hierarchy;resourceId=...;tab=...`. The earlier
`ui_deep_links.md` recorded `/ui/operations/dashboards/...`; only
`operate/` appears in either bundle, and the one vendor-populated value on
both labs uses `operate/`. Prefer `operate/`.

Vendor-shipped values (from the appliance templates), for reference:

```
/ui/operate/dashboards/dashboards;tabId=<tabId>
/vcf-operations/ui/operate/dashboards/dashboards;tabId=<tabId>
/vcf-operations/ui/operate/alerts;tab=alerts
/vcf-operations/ui/operate/inventory;mode=tree;ts=vSphere%20Hosts%20and%20Clusters-VMWARE-vSphere%20World;tab=summary
/vcf-operations/ui/observe/diagnostics/vcf-health/esx?resourceId=software-defined-datacenters
```

### Worked examples

Link to another dashboard by tabId (the value is the dashboard UUID the
factory assigns in YAML `id:`):

```json
"config": {
  "title": "License Server",
  "viewDetails": "/ui/operate/dashboards/dashboards;tabId=2061bfa9-b20e-404a-8ef3-4f094539ebed",
  ...
}
```

Link to a specific object's Alerts tab (static object; the Angular
inventory route accepts `tab=alerts`, seen as `{tab:"alerts"}` in the
bundle, alongside `tab=summary`):

```json
"config": {
  "title": "Cluster alerts",
  "viewDetails": "/ui/operate/inventory;mode=hierarchy;resourceId=<cluster resource uuid>;tab=alerts",
  ...
}
```

Because the resource UUID is instance-specific and the value is a plain
string (not re-symbolized through `entries` on export/import), a
resourceId-bearing `viewDetails` does **not** survive a move between
instances. For portable content use the dashboard-by-tabId form or the
global alerts page `/ui/operate/alerts;tab=alerts`. The `tab=alerts` object
form is derived from the route table, not clicked through in a browser;
treat it as high-confidence but unverified visually.

---

## 3. Section widget

### Layout entry (`getDashboardConfig`)

```json
{"tabId": "...", "isLoading": false, "collapsed": true, "gridsterX": 1,
 "gridsterY": 6, "gridsterW": 12, "gridsterH": 1, "id": "<section uuid>",
 "title": "Ingestion", "key": "Section", "height": 0}
```

`Ext.vcops.dashboard.widget.Section` declares statics `gridsterH: 1,
gridsterW: 12`; every Section observed on both labs is exactly 12 x 1,
`height: 0`. `collapsed` is the persisted expand/collapse state.

### It DOES have a widget-config entry

`getWidgetConfigs` returns `widget_<id>` for Sections just like any other
widget, and it is not decorative: it carries the **explicit membership
list**.

```json
"widget_b5a33f68-4988-4644-b5aa-45df86875dbe": {
  "title": "Ingestion",
  "titleLocalized": "Ingestion",
  "description": "",
  "widgets": ["39f107d7-...", "1cca7c43-...", "640a2f84-...", "..."]
}
```

Export form:

```json
{
  "tabId": "<dashboard uuid>",
  "collapsed": false,
  "id": "<section uuid>",
  "gridsterCoords": {"w": 12, "x": 1, "h": 1, "y": 21},
  "state": "",
  "type": "Section",
  "title": "VCF Health",
  "config": {
    "title": "VCF Health",
    "titleLocalized": "VCF Health",
    "description": "",
    "widgets": ["0a6e7792-0259-4e03-81b6-8d220b537462", "44d4360f-acfe-4cfa-827d-4ae499a76c1f"]
  },
  "height": 0
}
```

Some entries also carry `widgetId` (the section's own id) and, when set,
`viewDetails`; cloned dashboards were seen with a stale `widgetId` that no
longer matches `id`, and the UI does not care, so treat `widgetId` as
optional noise.

### Which widgets a Section collapses (`GridsterPanel.js`)

- **Initial load:** membership is read from `config.widgets` only. Each
  listed widget gets `relativeGridsterY = widget.y - section.y` and is
  hidden/shown with the section. A widget not in the list is not affected
  by collapse, wherever it sits.
- **After any layout change in the editor** (`syncSectionWidgets` / the
  non-initial branch): the list is **recomputed** as "every non-hidden
  widget below this Section, in `gridsterY` order, until the next Section"
  and written back to `config.widgets`. A collapsed Section keeps its
  saved list (it is skipped during recomputation because its children are
  hidden).
- So the answer to "everything until the next Section?" is: **that is how
  the UI populates the list, but the stored list is authoritative at
  load.** When authoring, put the Section at 12 x 1 above its children, and
  list every child id in `config.widgets`; do not rely on position alone.
  An empty or missing `widgets` list gives a Section that collapses
  nothing.
- Collapsing shifts the children up under the Section bar
  (`collapseSection`/`expandSection` re-derive child `y` from the section's
  `y` plus `relativeGridsterY`), which is why exported `gridsterCoords.y`
  values of children of a collapsed Section overlap with rows of the next
  Section in the saved layout. That is expected, not corruption.

Adding a Section from the palette posts `widgetConfig` `{"title": "..."}`
only; the editor (`editors/Section.js`) writes `widgets` back on save. The
editor exposes title + description only, plus the base "Details URL".

Minimal authoring example:

```json
{
  "collapsed": false,
  "id": "<section uuid>",
  "gridsterCoords": {"w": 12, "x": 1, "h": 1, "y": 1},
  "state": "",
  "type": "Section",
  "title": "CPU",
  "config": {"title": "CPU", "description": "", "widgets": ["<child uuid 1>", "<child uuid 2>"]},
  "height": 0
}
```

---

## 4. Scoreboard: `visualTheme: 9` is the gauge

From `editors/Scoreboard.js`: the Visual Theme combo is
`1 Original, 2 Solid, 3 Default, 4 Simple, 5 Pastel, 6 Shadow, 7 Outline,
8 Gradient`, and when `allowGauge` (true for the dashboard Scoreboard)
`9 Gauge` is appended. The editor's Score/Gauge toggle is literally
`viewMode = (visualTheme == 9) ? 'gauge' : 'score'`; choosing Gauge forces
`visualTheme = 9`. `widgets/Scoreboard.js` resets anything outside 1..9 to
3. This corrects `widget_types_survey.md`, which listed the range as 1..5.

Gauge-specific config keys (all top-level, all default `false`):
`showRemaining`, `showPercentText`, `focusOnPercent`. They are pushed into
each `board.gauge` and ignored by non-gauge themes.

`maxValue` lives **per metric** in
`metric.resourceKindMetrics[].maxValue` (string, `""` when unset). The gauge
component (`components/Scoreboard.js`) uses
`maxV = this.maxValue || (unit == '%' ? 100 : 1)`, so for percentage
metrics leaving `maxValue` empty is fine; for anything else set it or the
gauge is drawn against 1.

`mode.layoutMode`: `"fixedView"` (default when absent) stretches the board
rows to fill the widget height (`setBordHeight` adds the leftover
height / rowCount to each board, and on resize resets to 0 and re-fits);
`"floatingView"` leaves boards at their natural `boxHeight` and lets the
body scroll. Unrelated to gauge vs score.

Minimal gauge Scoreboard config (the rest of the Scoreboard keys as in
`widget_types_survey.md`):

```json
"config": {
  "title": "Memory Usage (for selected VM)",
  "visualTheme": 9,
  "mode": {"layoutMode": "fixedView"},
  "boxColumns": 1, "labelSize": 16, "valueSize": 24,
  "showRemaining": false, "showPercentText": false, "focusOnPercent": false,
  "selfProvider": {"selfProvider": false},
  "refreshContent": {"refreshContent": true}, "refreshInterval": 300,
  "showMetricName": {"showMetricName": false},
  "showMetricUnit": {"showMetricUnit": true},
  "showResourceName": {"showResourceName": true},
  "showDT": {"showDT": true},
  "showSparkline": {"showSparkline": false},
  "resource": [], "depth": 1, "maxCellCount": 100, "roundDecimals": null,
  "metric": {
    "mode": "resourceKind", "subMode": "resourceKindAll", "resourceMetrics": [],
    "resourceKindMetrics": [{
      "resourceKindId": "002006VMWAREVirtualMachine", "resourceKindName": "Virtual Machine",
      "metricKey": "mem|usage_average", "metricName": "Memory|Usage",
      "maxValue": "100", "unit": "Auto", "defUnit": "%",
      "yellowBound": 85, "orangeBound": 90, "redBound": 95, "colorMethod": 0,
      "label": "", "labelOrig": "", "labelLocalized": "", "link": "",
      "isStringMetric": false, "handleOldColoring": false, "metricUnitId": -1,
      "id": "extModel1-1"
    }]
  }
}
```

---

## Widgets bound to many resource kinds

**Date:** 2026-08-26. **Instance:** qa (9.2.0.0 pre-release lab build).
**Question:** when one summary dashboard is bound (via
`associateResourceKindDashboards`, see `summary_dashboard_assignment.md`)
to several resource kinds, how does a Scoreboard / PropertyList whose
`metric.resourceKindMetrics[]` entries carry a `resourceKindId` behave on
a page object of another kind, and is there an "any kind" form?

**Method:** replayed the exact two calls the widgets issue on render
(`utility.action getTopImportantMetrics`, then
`widgetScoreboard.action getMetricValues`), taken verbatim from
`webapps/ui/js/widgets/Scoreboard.js` (lines 280-330 and 405-445) and
`widgets/PropertyList.js` (`getResourceMetricsByResourceKind`), with a
hand-built `resourceKindMetrics` list against live VMWARE objects
(`resourceStatus=DATA_RECEIVING`), then confirmed the client-side rules
from those sources. A throwaway dashboard carrying the same entries was
also imported and deleted (three ids, all confirmed gone), but its widget
configs never landed on this build (see the "Import regression" note at
the end), so the replay is the evidence.

### 1. Selection is server-side, by the page object's kind

The widget JS does **no** filtering. It sends the whole
`resourceKindMetrics` array plus the object(s) in context to
`getTopImportantMetrics` and renders exactly the `resourceMetrics` rows
that come back. The server keeps only the entries whose `resourceKindId`
equals the object's kind id and drops the rest silently.

Entry list sent (one key, once per kind; `resourceKindId` is
`"0020" + len(adapterKind) as 2 digits + adapterKind + resourceKind`):

```json
[{"metricKey": "cpu|usage_average", "resourceKindId": "002006VMWAREVirtualMachine",
  "resourceKindName": "VirtualMachine", "label": "VM CPU Usage",
  "colorMethod": 0, "yellowBound": 70, "orangeBound": 85, "redBound": 100,
  "id": "x-VirtualMachine", "isStringMetric": false, "handleOldColoring": false,
  "link": "", "maxValue": "", "metricName": "CPU Usage", "metricUnitId": null, "unit": null},
 {"metricKey": "cpu|usage_average", "resourceKindId": "002006VMWAREHostSystem",
  "resourceKindName": "HostSystem", "label": "Host CPU Usage",
  "colorMethod": 0, "yellowBound": 70, "orangeBound": 85, "redBound": 100,
  "id": "x-HostSystem", "isStringMetric": false, "handleOldColoring": false,
  "link": "", "maxValue": "", "metricName": "CPU Usage", "metricUnitId": null, "unit": null}]
```

Request (form-encoded POST, UI session, `X-Requested-With: XMLHttpRequest`):
`mainAction=getTopImportantMetrics`, `resourceKindMetrics=<json above>`,
`resources=[{"id":"<object uuid>"}]`, `relationshipMode=0`, `depth=1`,
`xmlConfigFileName=` (empty; that is `resInteractionMode: null`),
`limit=100`, `secureToken=<csrf>`. PropertyList sends the same plus
`propertyMetricsOnly=true` and `limit=10000`.

| Page object | `resourceProcessed/Total` | `metricProcessed/Total` | `resourceMetrics` returned |
|---|---|---|---|
| VirtualMachine (`vcfops-arm-m01-w01`) | 1/1 | 1/1 | one row: `002006VMWAREVirtualMachine` / `cpu\|usage_average`, label `VM CPU Usage` |
| HostSystem (`10.161.121.16`) | 1/1 | 1/1 | one row: `002006VMWAREHostSystem` / `cpu\|usage_average`, label `Host CPU Usage` |
| Datastore (kind not in the list) | 0/0 | 0/0 | `[]` |

`getMetricValues` on each returned row produced a real tile: VM
`value "11.5"`, Host `value "3.3"`, both `state Normal`, `colorHex
#8ABF5B`, bounds echoed as strings (`"70"/"85"/"100"`). So on a
multi-kind bound dashboard a Scoreboard gets **exactly its own kind's
tile(s), with values**; the other kinds' entries produce nothing, and an
object whose kind has no entry gets an empty widget (the JS path for an
empty `resourceMetrics` clears the container and fires `widgetLoad`
without calling `getMetricValues`).

PropertyList behaves identically (`propertyMetricsOnly=true`, entries
`config|version` for VirtualMachine and `summary|version` /
`config|hyperThread|active` for HostSystem): VM object returns only the
VM row (`isPropertyMetric: true`), Host only the Host row, Datastore
nothing.

Note the `metricTotalCount` is the count **after** kind filtering (1, not
2), so the "showing N of M metrics" warning in PropertyList never fires
for dropped foreign-kind entries.

### 2. Non-matching entries are hidden, not "?" tiles, and there is no wildcard

- **Hidden.** Tiles are created only from `getMetricValues` rows, which
  are created only from `getTopImportantMetrics` rows. A foreign-kind
  entry never reaches the client's tile loop (`Scoreboard.js`
  `loadScoreBoardPanel` -> `applyScoreboardConfig`). The `?` / `Unknown`
  grey tile is a different mechanism (a returned row whose `colorMethod: 0`
  bounds are incomplete; see the lesson
  `scoreboard-partial-bounds-render-unknown`). The only client-side use
  of `resourceKindId` is a cosmetic re-apply of `colorMethod` on rows
  whose `(resourceKindId, metricKey)` matches a config entry
  (`Scoreboard.js` line 355), which is why per-kind duplicates of the
  same key with different `colorMethod` are safe: each row matches its
  own kind's entry.
- **No wildcard.** Every "any kind" form of `resourceKindId` tried on the
  Host object made `getTopImportantMetrics` return the Struts ERRPANEL
  page (HTTP 200, HTML body, `Internal Server Error`) instead of JSON, so
  the widget's `success` handler would throw on decode and the widget
  would stay blank: `""`, `"*"`, `null`, key omitted, and the adapter-only
  prefix `"002006VMWARE"`. A syntactically valid but wrong kind id is the
  silent `resourceMetrics: []` case above. There is no
  `adapterKindKey`/`resourceKindKey` alternative in the entry, and the
  `metric.subMode: "resourceKindAll"` value seen in stored configs is the
  editor's interaction mode 2 ("all objects of this kind" for
  self-provider widgets: `widgets/editors/Scoreboard.js` lines 553-565),
  not an any-kind switch; the render path checks `selfProvider` before
  it looks at `subMode`, so it is inert on inherited-object widgets.
- The Suite API and both OpenAPI specs have nothing for this layer
  (no `dash` paths); the server-side filter lives in the UI webapp's
  `UtilityAction.getTopImportantMetrics`, whose jars are not readable on
  the appliance without a decompiler (no `javap`/`unzip` shipped).

### 3. What Broadcom does

`getResourceKindList?appendDetailPageMappings=true` across every adapter
kind on qa (96 distinct `resourceKindTemplate` values): every
dashboard-backed kind maps to a template name bound to **exactly one
kind**. Broadcom's own summary dashboards are one dashboard per kind
(for example `Host System Summary`, `Datastore Summary`, `Cluster Compute
Resource Summary` as native pages). The
only template name shared across kinds is the generic default `Summary
Detail`. When a factory dashboard is bound to N kinds the server
materializes N template copies and the list shows them as `<name>`,
`<name> 1`, `<name> 2`, ... (`resourceKindTemplate` is a plain name here,
not `name_::_uuid`).

### Recommendation for `summary_for` lists

Per-kind entries. A widget on a dashboard whose `summary_for` lists K
kinds should carry each metric once per kind (K entries with the same
`metric_key`, each with its own `adapter_kind`/`resource_kind`); the
server picks the one matching the page object and hides the rest, and
`getWidgetConfigs` stores them verbatim. A wildcard does not exist
(server error), and one dashboard per kind is what Broadcom does but
multiplies content K-fold for no rendering gain. The remaining cost of
per-kind entries is authoring bulk (K x metrics), which is a renderer
concern: a `resource_kinds:` list or an "expand over `summary_for`" flag
on `MetricSpec` would let YAML stay single-entry while the emitted
`resourceKindMetrics[]` fans out per kind. Non-metric widgets (Section,
View, AlertVolume, TextDisplay) have no `resourceKindMetrics` and need
nothing.

### Renderer behaviour (implemented)

`vcfops_dashboards/render.py::_fan_out_summary_specs`, applied to
Scoreboard, MetricChart and PropertyList. When a dashboard's `summary_for`
lists more than one kind and the widget has `self_provider: false`
(PropertyList always does), every `MetricSpec` whose
`adapter_kind:resource_kind` is one of the listed kinds is emitted once
per listed kind of the same adapter kind, in `summary_for` order,
differing only in `resourceKindId` / `resourceKindName` (the `label`
and everything else is copied). The YAML stays single-entry. A spec on
a kind that is not listed (a child kind, say) is author-pinned and
emitted once, untouched. Single-kind and non-summary dashboards render
byte-identical to before.

Wire shape is the existing one: `resourceKindId` is the
`resourceKind:id:N_::_` reference into `entries.resourceKind[]` (every
fanned kind gets its own slot there; the importer rewrites it to the
`0020…` id), `resourceKindName` is the bare resource kind key, and the
`extModel<hash>-<seq>` id runs over the expanded list so ids stay unique.

Validation note: the loader does not check that a metric key exists on
every listed kind. A key missing on one kind is a hidden entry on that
kind's page (server-side drop, section 1 above), not an error.

### Import regression on the 9.2 pre-release lab build (qa, 2026-08-26)

Three content-zip dashboard imports on this build (two factory-rendered,
one re-import of the server's **own** `POST /api/content/operations/export`
output of an existing dashboard under a new id and name) all reported
`imported=1 failed=0 FINISHED`, created the tab with the right widgets,
titles and coordinates, yet every widget's stored config was empty:
`getWidgetConfigs` returned `{"title": "Scoreboard"}` /
`{"title": "Property List"}` (default titles) per widget, and a fresh
export showed `"config": {}` for each, while the pre-existing dashboards
on the same instance (imported on an earlier lab build) still export and read
back full configs. The renderer output was verified intact in the zip
(`dashboard/dashboard.json` `widgets[].config` populated,
`entries.resourceKind` placeholders `resourceKind:id:N_::_` present).
Treat any content-installer run against this build as suspect until a
newer lab build is checked; `bind-summary` of such a dashboard would bind
empty widgets.

---

## Parity and caveats

- devel 9.1.1: identical `IntSummaryAlertVolume` config keys and identical
  Section `config.widgets` shape; same single `viewDetails` value on the
  same built-in dashboard; same `operate/` routes in the bundle.
- The Suite API export with `scope: ALL` returned all 228 qa dashboards
  this time (contrast the deferred-import note in
  `dashboard_selfprovider_pin_wire_format.md`; that caveat is about freshly
  imported, un-materialized dashboards, not the export in general).
- The export zip nests: outer `dashboards/<uuid>` is itself a zip whose
  `dashboard/dashboard.json` holds `{uuid, entries, dashboards[]}`.

---

## Changelog

- 2026-08-25: `src/vcfops_dashboards/render.py` gained the Section, Alert
  Volume, gauge and `viewDetails` emitters. Rendered output for all
  existing `content/` dashboards is byte-identical to `main`
  (`PYTHONHASHSEED=0`), so no `CURRENT_TEMPLATE_VERSION` bump; the
  distribution zips under `dist/` are still stale by the CLAUDE.md
  "After tooling changes" rule and need a `content-packager` rebuild of
  every manifest in `bundles/`.
- 2026-08-25 (review follow-up): Section `x` must be 1 and no other
  widget may share a Section's row (loader errors); `summary_for` is
  stored normalized and must be unique across a dashboard set.
- 2026-08-26: added "Widgets bound to many resource kinds": server-side kind selection in `getTopImportantMetrics`, no wildcard `resourceKindId`, per-kind entry recommendation, and the widget-config import regression seen on the 9.2 pre-release lab build.
- 2026-08-26: "Renderer behaviour (implemented)" under that section: multi-kind `summary_for` fan-out of `resourceKindMetrics[]` in `render.py`.
