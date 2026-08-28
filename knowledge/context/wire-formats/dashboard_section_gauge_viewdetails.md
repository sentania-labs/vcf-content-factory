# Dashboard widget wire shapes: Section, gauge scoreboard, viewDetails, AlertVolume

Learned 2026-08-25 from cached 9.1.1 / 9.2 UI captures
(`getDashboardConfig` and `getWidgetConfigs` for four vendor dashboards,
18 Section widgets, 15 gauge scoreboards). Structure only was lifted; no
vendor names or keys are reproduced here. Implemented in
`src/vcfops_dashboards/loader.py` and `render.py`; tests in
`tests/test_dashboard_section_widget.py`.

The captures are the UI's *runtime* representation (`key`, `gridsterX`,
...); the import-bundle form was later confirmed from Suite API export
samples (`reference/docs/extracted/dashboard-widgets/`). The factory
output has NOT yet been round-tripped through a live content-import;
treat "installs and renders" as unverified until qa-tester exercises it.

## Section (collapsible row header)

Authoritative source (from appliance JS and Suite API export samples):
`knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
§3. Summary of what the factory relies on:

- Dashboard-level runtime entry: `key: "Section"`, `title`, `collapsed`,
  `gridsterW: 12` / `gridsterH: 1` (class statics), `height: 0`.
- `getWidgetConfigs` DOES return an entry for a Section:
  `{"title", "titleLocalized", "description": "", "widgets": [<member uuid>, ...]}`.
  The list is **authoritative at load**: only listed widgets collapse.
  The UI recomputes it after any layout edit as "every non-hidden widget
  below this Section, in gridsterY order, until the next Section".
- Export / import form: `type: "Section"`, `gridsterCoords {w:12,h:1}`,
  `config {title, titleLocalized, description, widgets[]}` (plus optional
  `widgetId` / `state` noise), `height: 0`. No `isLoading`, no widget-level
  `description`.

Factory YAML: `type: Section`, `title`, optional `collapsed`, optional
`widgets: [<local id>, ...]`. When `widgets:` is omitted the loader applies
the UI's own rule by row: every non-Section widget with `coords.y`
strictly between this Section's row and the next Section's row, ordered
by (y, x). Author `widgets:` to override.

Factory render:

```json
{"collapsed": false, "id": "<uuid>", "gridsterCoords": {"x": 1, "y": 5, "w": 12, "h": 1},
 "type": "Section", "title": "...",
 "config": {"title": "...", "titleLocalized": "...", "description": "", "widgets": ["<uuid>", "..."]},
 "height": 0}
```

Validation: a Section must not carry metrics, views, resource kinds,
pins, `self_provider`, `view_details`, or interaction endpoints; Sections
do not nest.

## Gauge scoreboard (`visualTheme: 9`)

See the `ScoreboardConfig` docstring in `loader.py` for the recipe, and
`knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
§4 for the source-level facts (theme enum 1..9 with 9 = Gauge, the
`maxValue || (unit == '%' ? 100 : 1)` fallback, `showRemaining` /
`showPercentText` / `focusOnPercent` as gauge switches, `fixedView` vs
`floatingView` as a row-stretch setting unrelated to gauge). The factory
emits the three gauge switches only when `visual_theme` is 9. Field
observations across the 15 captured gauge widgets:

- `mode.layoutMode` is `"fixedView"` on all 15 (same as every non-gauge
  scoreboard captured), `showMetricName.showMetricName` true on all 15.
- Per-metric `maxValue` is either the integer `0` (38 entries, the
  UI's unset default) or a non-empty *string* (32 entries). Non-gauge
  scoreboards carry `""` or a string. The factory emits `""` when unset
  (unchanged) and the stringified number when `max_value` is authored.
- Bounds ride in the per-metric entry as `yellowBound` / `orangeBound` /
  `redBound` with `colorMethod: 0`, which the renderer already emitted.
  Replayed against the product's own Scoreboard `.action` calls on 9.2
  (2026-08-25, lesson `scoreboard-partial-bounds-render-unknown`): with
  `colorMethod: 0` the entry must carry **all three** numeric bounds. A
  partial set (only `redBound`, or yellow and orange without red) makes
  the server answer `value: "?"` / `state: Unknown` although the value
  exists. Thresholds are ascending and inclusive: `>= yellowBound`
  Warning, `>= orangeBound` Immediate, `>= redBound` Critical; "red at
  >= 1" is `(1, 1, 1)`, which is what the vendor's flag metrics use.
  The loader rejects a partial set on `color_method: 0`; none at all is
  an uncolored tile. `colorMethod: 3` (15 entries) is the same three
  bounds read as a percent of `maxValue`; that is a reading note for
  vendor exports only. The factory emits bounds solely for
  `color_method: 0` and nulls them for every other method (the
  partial-set behaviour on 3 is unverified server-side), and the loader
  rejects any bound supplied with `color_method: 3`.
- `oldMetricValues: false`, `roundDecimals: null` on all 15; the factory
  defaults (`true`, `1`) are left alone so existing output is untouched.
- `focusOnPercent`, `showPercentText`, `showRemaining` (all false) appear
  on 9 of 15 gauges AND on several non-gauge themes (4, 7, 8): the editor
  writes them whenever it has run, and only the gauge reads them.

## `viewDetails`

Every non-Section widget config in the captures carries `"viewDetails"`
(value `""` everywhere in this set; the dashboard-level entry carries a
mirror of it). The factory YAML field `view_details: <string>` is copied
verbatim (trimmed) into `config.viewDetails`; when the YAML omits it
nothing is emitted, so existing output is byte-identical.

Accepted forms (the product's click handler is the whole contract, see
`knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
§2): `http://` / `https://` absolute (new tab), or a relative Angular
route starting with `/ui/` or `/vcf-operations/ui/` (in-place
navigation; the `/vcf-operations` prefix is stripped by the product).
The loader rejects anything else. Links are static: no placeholder
expansion exists product-side, so "link to the current object" cannot be
expressed; the portable form is another dashboard by id,
`/ui/operate/dashboards/dashboards;tabId=<uuid>`.

Not built (TODO, see the tooling report of 2026-08-25): a helper field
`view_details_dashboard: "<dashboard name>"` resolved to that route from
the target dashboard's YAML `id`. Resolution needs the full dashboard
set (`load_all`), which the single-file `load_dashboard` path used by
the SDK pak builder does not have, so it is more than a small addition.

## AlertVolume (`IntSummaryAlertVolume`)

Source of truth: `knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
§1. Factory YAML `type: AlertVolume` renders wire `type:
"IntSummaryAlertVolume"`. Config is only `refreshInterval`,
`refreshContent`, `selfProvider`, `title`, plus (self provider ON) a
single-object `resource: {resourceId, resourceName}` bound through
`entries.resource` like a pinned View. With self provider OFF the
`resource` key is omitted (vendor Home template shape) and the widget
takes one incoming `resourceId` interaction. No window / severity /
chart options exist (7 days, all criticalities, hard-coded), so YAML keys
such as `criticality`, `time_window`, `date_range`, `alert_types`,
`metrics` are rejected at load.

## Determinism note (pre-existing, not from this change)

`render.py:_render_metric_spec` builds per-metric ids as
`extModel{abs(hash(widget_id)) % 100000}-{seq}`. `hash()` on a str is
PYTHONHASHSEED-randomized, so those ids differ per interpreter run. Every
other byte of a bundle is deterministic. Diff renders with those ids
normalized.
