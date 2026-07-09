# Compliance Fleet Overview dashboard render failures (v28 pak)

Date: 2026-05-29
Profile: `devel` (vcf-lab-operations-devel.int.sentania.net)
Dashboard: `[VCF Content Factory] Compliance Fleet Overview` (id `51ed9773-aa5b-4c2d-87f3-3934fed34f4b`)
Source: `/tmp/v28dash/content/dashboards/VCF_Content_Factory_Compliance_Fleet_Overview/dashboard.json`

## Server-side stack trace (verbatim)

From `/storage/log/vcops/log/product-ui/catalina.out-2026-05-29-00`, lines 6-21:

```
org.json.JSONException: JSONObject["type"] not found.
	at org.json.JSONObject.get(JSONObject.java:571)
	at org.json.JSONObject.getString(JSONObject.java:858)
	at com.vmware.vcops.ui.action.HeatMapAction.initParam(HeatMapAction.java:339)
	at com.vmware.vcops.ui.action.HeatMapAction.getHeatMapData(HeatMapAction.java:273)
	at com.vmware.vcops.ui.action.HeatMapAction.execute(HeatMapAction.java:216)
```

The exception fires three times in today's log, once per dashboard load
(11:37:44.153, 11:39:03.309, 11:39:33.181). Access log confirms:
`POST /vcf-operations/plug/ops/heatMap.action HTTP/2.0 200 519` — Struts
catches the exception and returns an error JSON body (~519 bytes), which
the browser surfaces as the "Internal Server Error" popup.

No other server-side exceptions correlate with the dashboard load.

## Widget config diff vs working corpus

### Heatmap

Compared to `/tmp/idps/bundles/idps-planner/content/dashboard.json` widget
`5c2a30b1-…` ("Cluster Host Heatmap") and the canonical capacity Heatmap
in `knowledge/context/api-surface/widget_types_survey.md` §Heatmap.

| Field | Ours (v28) | Working corpus | Verdict |
|---|---|---|---|
| `selfProvider` | `{selfProvider: true}` | `{selfProvider: false}` | Tolerable (both forms seen) |
| `mode` | `"all"` | `"all"` | Match |
| `resourceKind` | `"resourceKind:id:1_::_"` | `"resourceKind:id:1_::_"` | Match |
| `colorBy` | `{metricKey, value}` | `{metricKey, value}` | Match |
| **`groupBy`** | **`{}`** (empty object) | **`{resourceKind, adapterKind, typeId, type: "resourceKind", text, originalText, id, parentText, parentId}`** (9 keys) | **MISMATCH — root cause** |
| `relationshipMode` | `[1,-1,0]` | `[1,-1,0]` | Match |

`HeatMapAction.initParam` calls `groupBy.getString("type")` unconditionally.
With `groupBy: {}` the key is missing and the action throws before any data
is fetched, so the heatmap returns no tiles and surfaces the Internal Server
Error popup.

Across all surveyed corpus dashboards (idps-planner, capacity, vSAN samples
in `knowledge/context/api-surface/widget_types_survey.md`), **no** Heatmap has an empty
`groupBy`. The pattern is always populated even when `focusOnGroups: false`.

### AlertList

Compared to `/tmp/app_osucp/content/dashboards/ucp/dashboard.json` widget
`325ba1e6-…` ("4. Alerts on the selected objects").

| Field | Ours (v28) | UCP corpus | Notes |
|---|---|---|---|
| `selfProvider` | `{selfProvider: true}` | `{selfProvider: false}` | Different — ours is self-provider |
| `mode` | `"all"` | `"all"` | Match |
| `resource` | `[]` | `[]` | Match |
| `criticalityLevel` | `[2,3,4]` | `[]` | Differs (ours filters; corpus shows all) |
| `alertDefinitions` | `[{id: "AlertDefinition-vcfcf_compliance-vcfcf_compliance_score_degraded"}]` | not present (defaults `[]`) | Ours pins; corpus filters by client |
| `status` | `[]` | `[0]` (active only) | Differs |
| `state` | `[]` | `[]` | Match |
| `relationshipMode` | `[-1, 0]` | `[-1, 0]` | Match |

Access log for today shows zero calls to any AlertList backend action
(no `alertList.action`, `getAlerts.action`, or equivalent). `problemalerts.action`
entries belong to a different widget surface (ProblemAlertsList / inline
problem chips). The AlertList widget is **never issuing a backend query**.

`alertDefinitions: [{id: "AlertDefinition-…"}]` is documented in the survey
(line 634) as the pin filter. The format we emit matches the documented
shape exactly. The widget pin format itself looks correct.

The combination `selfProvider:true + mode:"all" + resource:[]` is the
"show me all alerts of this definition across the world" pattern, but the
UI may bind this to context that requires either:
- a populated `resource` array (resource:id:0 like the ProblemAlertsList
  in sdwan dashboard line 738-741), or
- an empty `alertDefinitions` filter (let the user pick)

I cannot confirm from logs whether the UI is filtering client-side and
discarding all matches, or never firing the query. Either way, the
self-provider AlertList with both a definition pin AND a criticality
filter is a configuration combination **not observed in any corpus
dashboard surveyed** (24 AlertList widgets across 18 dashboards).

### View

Compared to `/tmp/idps/bundles/idps-planner/content/dashboard.json` widgets
`d6f1c4d3-…`, `e494889e-…`, `2ca53219-…` (three self-provider Views pinned
to vSphere World).

| Field | Ours (v28) | IDPS corpus | Verdict |
|---|---|---|---|
| `resource.resourceId` | `"resource:id:0_::_"` | `"resource:id:0_::_"` | Match |
| `resource.resourceName` | `"vSphere World"` | `"vSphere World"` | Match |
| `resource.resourceKindId` | `"002006VMWAREvSphere World"` | `"002006VMWAREvSphere World"` | Match |
| `resource.id` | `"Ext.vcops.chrome.model.Resource-1"` | `"Ext.vcops.chrome.model.Resource-1"` | Match |
| `resource.traversalSpecId` | `""` | `""` | Match |
| `selfProvider` | `{selfProvider: true}` | `{selfProvider: true}` | Match |
| `isUpdatedView` | `true` | `true` | Match |

The View widget config is byte-identical in shape to the corpus reference
that demonstrably renders. The `Ext.vcops.chrome.model.Resource-N` id
form is correct in this context — it appears in 4 of 4 self-provider
Views in the idps corpus and renders. The concern about it being a
"UI-only Ext JS model ID" was a false alarm; the Suite API tolerates and
expects it for the self-provider Views pinned to vSphere World.

## Root causes (per issue)

1. **Internal Server Error popup on dashboard load**
   Caused by the Heatmap widget. `HeatMapAction.initParam` throws
   `JSONObject["type"] not found` because the renderer emits
   `groupBy: {}` when no group-by kind is configured. Java code path
   always reads the `type` key; empty object is not a valid omit signal.

2. **`Compliance Score by Host` Heatmap blank**
   Same root cause as #1. The action throws before fetching any data,
   so the widget renders an empty grid.

3. **`Fleet Compliance Alerts` AlertList blank**
   Configuration combination (`selfProvider: true` + `mode: "all"` +
   `resource: []` + `alertDefinitions: [{...}]` + `criticalityLevel: [2,3,4]`)
   is unobserved in the corpus and apparently does not trigger a backend
   query. The access log shows zero AlertList action invocations during
   dashboard loads. The widget definition itself does not crash; it
   just never fetches.

## Proposed fixes (DO NOT APPLY HERE — orchestrator's call)

### Fix 1+2 — Heatmap renderer (`vcfops_dashboards/render.py:1224-1225`)

The `else: group_by = {}` branch is wrong. Either:

- **(A) Renderer fix.** When no group-by is configured, emit the **subject
  resource kind itself** as the groupBy (a self-grouped heatmap where every
  tile is in one swim-lane). This matches the v28 author's intent ("color
  by metric across all hosts of this kind"). Requires populating the same
  9-key shape using `tab.adapter_kind` and `tab.resource_kind`.
- **(B) YAML/author requirement.** Make `group_by_kind` mandatory in
  `HeatmapTabConfig` and have the author specify HostSystem (which would
  produce a single-lane heatmap). Fails fast at validation rather than at
  install.

Recommended: **(A)** — keep the current author UX (group_by optional) and
fix the renderer to emit the self-grouped shape. The corpus capacity
Heatmap in `widget_types_survey.md` line 464-471 uses ClusterComputeResource
as the groupBy when subject is also clusters — same shape, just same kind.

### Fix 3 — AlertList

Two viable paths:

- **(A) Drop the `alertDefinitions` pin and the `criticalityLevel` filter.**
  Make the widget show "all alerts on relevant HostSystem resources of
  whatever criticality". Closer to UCP corpus shape. Lose the visual
  scoping to compliance-only alerts.
- **(B) Set `resource: [{resourceId: "resource:id:0_::_", resourceName: "vSphere World"}]`
  and `selfProvider: false`** — mimic the sdwan ProblemAlertsList pattern
  (line 738-741) where the widget is pinned to vSphere World and shows all
  matching alerts under it. The `alertDefinitions` filter and
  criticality filter could remain.

Recommended: **(B)**. The compliance dashboard's intent is "show our
compliance alerts firing on the fleet" — pinning to vSphere World is the
correct scoping and matches a working corpus pattern.

Both fixes require an author-side YAML change for the AlertList widget
(probably a new field `pin_to_world: bool` in `AlertListConfig`) plus a
renderer change to emit the pinned resource array when set.

## Validation step (for whoever applies the fix)

After fixes are applied and rebuilt:
1. Tail `catalina.out-*` on devel during reload — `JSONException` should
   not recur.
2. Access log should show `heatMap.action` returning 1000+ bytes (real
   tile data) and a new `alertList.action` (or equivalent) call from the
   AlertList widget.
3. Heatmap should render 4 HostSystem tiles, AlertList should list the
   4 CRITICAL alerts.
