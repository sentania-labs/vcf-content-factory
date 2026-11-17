# Dashboard widgets: Alert Volume, Section, `viewDetails`, Scoreboard gauge

**Date:** 2026-08-25
**Instance:** devel (VCF Operations 9.1.1.0).
**Method:** enumerated every dashboard on the instance through the UI
Struts layer (`/ui/dashboard.action` `getDashboardList` ->
`getDashboardConfig` + `getWidgetConfigs` per tab), pulled a Suite API
content export (`POST /api/content/operations/export`, scope ALL,
`DASHBOARDS`) for the export form, and read the un-minified widget sources
that ship on the appliance under
`/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/js/widgets/` (widget,
`editors/`, `components/gridster/GridsterPanel.js`). No content was created
on the instance; nothing to clean up.

Verbatim samples (RULE-017): `reference/docs/extracted/dashboard-widgets/`
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
component and the chart always shows all criticalities. The vendor Home
template stores the same keys.

`getWidgetConfigs` entry, self provider ON, pinned to vSphere World
(illustrative, not a capture):

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
resource id is symbolized to an `entries.resource` placeholder;
illustrative, not a capture):

```json
{
  "tabId": "<dashboard uuid>",
  "collapsed": false,
  "id": "<widget uuid>",
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
- On devel 9.1.1 exactly one dashboard populates it (built-in
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

The 9.1.1 Angular bundle defines the dashboard route as
`/ui/operate/dashboards/dashboards;tabId=...` and the object page as
`/ui/operate/inventory;mode=hierarchy;resourceId=...;tab=...`. The earlier
`ui_deep_links.md` recorded `/ui/operations/dashboards/...`; only
`operate/` appears in the bundle, and the one vendor-populated value on
devel 9.1.1 uses `operate/`. Prefer `operate/`.

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
factory assigns in YAML `id:`; illustrative, not a capture):

```json
"config": {
  "title": "License Server",
  "viewDetails": "/ui/operate/dashboards/dashboards;tabId=<dashboard uuid>",
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

Illustrative, not a capture:

```json
{"tabId": "...", "isLoading": false, "collapsed": true, "gridsterX": 1,
 "gridsterY": 6, "gridsterW": 12, "gridsterH": 1, "id": "<section uuid>",
 "title": "Section A", "key": "Section", "height": 0}
```

`Ext.vcops.dashboard.widget.Section` declares statics `gridsterH: 1,
gridsterW: 12`; every Section observed on devel 9.1.1 is exactly 12 x 1,
`height: 0`. `collapsed` is the persisted expand/collapse state.

### It DOES have a widget-config entry

`getWidgetConfigs` returns `widget_<id>` for Sections just like any other
widget, and it is not decorative: it carries the **explicit membership
list** (illustrative, not a capture):

```json
"widget_<section uuid>": {
  "title": "Section A",
  "titleLocalized": "Section A",
  "description": "",
  "widgets": ["<child uuid 1>", "<child uuid 2>", "<child uuid 3>"]
}
```

Export form (illustrative, not a capture):

```json
{
  "tabId": "<dashboard uuid>",
  "collapsed": false,
  "id": "<section uuid>",
  "gridsterCoords": {"w": 12, "x": 1, "h": 1, "y": 21},
  "state": "",
  "type": "Section",
  "title": "Section B",
  "config": {
    "title": "Section B",
    "titleLocalized": "Section B",
    "description": "",
    "widgets": ["<child uuid 1>", "<child uuid 2>"]
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

The factory renderer fans `resourceKindMetrics[]` out per kind for a
dashboard bound to several resource kinds. The server-side behaviour this
relies on (the widget's metric lookup keeps only the entries whose
`resourceKindId` matches the page object's kind, with no wildcard form)
is not recorded on a released version in this repo and needs
re-verification on one.

### Renderer behaviour (implemented)

`vcfcf_dashboards/render.py::_fan_out_summary_specs`, applied to
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
kind's page, not an error.

---

## Parity and caveats

- A Suite API export with `scope: ALL` carries every listed dashboard on
  8.18.7, 9.0.2 and 9.1.1
  (`../investigations/2026-11-11-stock-content-ships-dangling-refs-migrator-false-missing.md`;
  contrast the deferred-import note in
  `dashboard_selfprovider_pin_wire_format.md`; that caveat is about freshly
  imported, un-materialized dashboards, not the export in general).
- The export zip nests: outer `dashboards/<uuid>` is itself a zip whose
  `dashboard/dashboard.json` holds `{uuid, entries, dashboards[]}`.

---

## Changelog

- 2026-08-25: `src/vcfcf_dashboards/render.py` gained the Section, Alert
  Volume, gauge and `viewDetails` emitters. Rendered output for all
  existing `content/` dashboards is byte-identical to `main`
  (`PYTHONHASHSEED=0`), so no `CURRENT_TEMPLATE_VERSION` bump; the
  distribution zips under `dist/` are still stale by the CLAUDE.md
  "After tooling changes" rule and need a `content-packager` rebuild of
  every manifest in `bundles/`.
- 2026-08-25 (review follow-up): Section `x` must be 1 and no other
  widget may share a Section's row (loader errors); `summary_for` is
  stored normalized and must be unique across a dashboard set.
- 2026-08-26: added "Widgets bound to many resource kinds" (per-kind entries).
- 2026-08-26: "Renderer behaviour (implemented)" under that section: multi-kind `summary_for` fan-out of `resourceKindMetrics[]` in `render.py`.
- 2026-11-16: samples and statements limited to the released version (9.1.1); the multi-kind server behaviour is pending re-verification on a released version.
