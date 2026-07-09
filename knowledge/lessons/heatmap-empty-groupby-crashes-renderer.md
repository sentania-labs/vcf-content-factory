# Heatmap empty groupBy crashes renderer (JSONException on dashboard load)

## Symptom

Dashboard load produces an "Internal Server Error" popup.  The Heatmap
widget is blank.  `catalina.out` contains:

```
org.json.JSONException: JSONObject["type"] not found.
    at org.json.JSONObject.getString(JSONObject.java:858)
    at com.vmware.vcops.ui.action.HeatMapAction.initParam(HeatMapAction.java:339)
```

The exception fires once per dashboard load (POST `/vcf-operations/plug/ops/heatMap.action`
returns HTTP 200 with a ~519-byte error JSON body).  Access log confirms the
action was called but returned an error, not tile data.

## Root cause

`src/vcfops_dashboards/render.py` — the Heatmap renderer — previously emitted
`groupBy: {}` when the YAML tab had no explicit `group_by_kind`.  The Java
`HeatMapAction.initParam` calls `groupBy.getString("type")` unconditionally;
an empty object has no `"type"` key, so it throws before fetching any data.

Across all 24+ Heatmap widgets surveyed in the corpus (idps-planner, VCF90,
vSAN, capacity), **no widget has an empty `groupBy`**.  The field is always
fully populated even when `focusOnGroups: false`.

## Fix (build 29)

`render.py` — the `else: group_by = {}` branch was replaced with a
**self-grouping** block that uses the tab's own `adapter_kind` /
`resource_kind` as both subject and group.  This produces a single swim-lane
(one group = all cells of that resource kind) and satisfies Java's expectation.

Required shape (all 9 keys must be present):

```json
{
  "resourceKind": "<resource_kind>",
  "adapterKind": "<adapter_kind>",
  "typeId": "resourceKind:id:N_::_",
  "type": "resourceKind",
  "text": "<resource_kind>",
  "originalText": "<resource_kind>",
  "id": "004null<6-digit-prefix><adapterKind><resourceKind>",
  "parentText": "<adapterKind>",
  "parentId": "<adapterKind>"
}
```

`typeId` and `id` use the same `_ADAPTER_KIND_PREFIX` and `kind_index` tables
as explicit groupBy entries.  The self-grouping path is hit only when
`group_by_kind` is empty; explicit `group_by_kind` in YAML is unchanged.

Corpus reference: idps-planner "VM by Host PPS" tab — HostSystem subject with
HostSystem groupBy (`typeId: "resourceKind:id:1_::_"`,
`id: "004null002006VMWAREHostSystem"`).

## Related: AlertList selfProvider:true + resource:[] silently never queries

A separate but related bug: an `AlertList` widget with
`selfProvider: true` + `resource: []` + `alertDefinitions: [...]` +
`criticalityLevel: [2,3,4]` emits zero backend queries.  The access log shows
no `alertList.action` calls during dashboard load — the widget stays blank.

This combination is unobserved in the 24 AlertList widgets surveyed across
18 corpus dashboards.

**Fix:** added `pin_to_world: bool` to `AlertListConfig` (loader) and the
renderer (`_alert_list_widget`).  When `pin_to_world: true`:

- emits `selfProvider: {"selfProvider": false}`
- emits `resource: [{"resourceId": "resource:id:0_::_", "resourceName": "vSphere World"}]`

This mirrors the sdwan `ProblemAlertsList` corpus pattern (line 738–741 of
`/tmp/app_osucp/content/dashboards/sdwan/dashboard.json`) — the only corpus
widget observed to combine a definition filter with a vSphere World resource
binding.  The `selfProvider`, `pin`, `mode`, `depth`, and `criticality`
fields in YAML remain present and consistent; `pin_to_world` is an alternate
**emission mode**, not a replacement for the other fields.

## Files changed (build 29)

- `src/vcfops_dashboards/render.py` — Heatmap `else: group_by = {}` replaced
  with self-grouping block (lines ~1197–1240); `_alert_list_widget` updated
  to handle `pin_to_world`.
- `src/vcfops_dashboards/loader.py` — `AlertListConfig` dataclass: new
  `pin_to_world: bool = False` field; loader parses `w.get("pin_to_world", False)`.
- `dashboards/compliance-overview.yaml` — `fleet_alerts` widget: added
  `pin_to_world: true`.
- `content/sdk-adapters/compliance/adapter.yaml` — `build_number` 28 → 29.

## Investigation source

`context/investigations/2026-05-29-compliance-dashboard-render-failures.md`
