# Self-provider widget pin wire format (View traversalSpecId, HealthChart resource)

**Investigation date:** 2026-07-13. **Instance:** devel
(`vcf-lab-operations-devel.int.sentania.net`, VCF Operations 9.x lab,
self-signed cert). **Trigger:** vcommunity-vsphere pak dashboards render
with unbound self-provider pins — "Cluster Performance 2.0"
(`a3df3248-2016-4fbc-a532-e51b05211ded`) pinned View shows "Select the
widget source…" and the two vSphere-World HealthCharts list all ~493
resources; "ESXi Host Details" (`d6c4fc3f-...`) distribution Views show
"No data".

**Reference (known-working vendor export):**
`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/dashboards/Cluster Performance 2.0.json`.

> **UNSUPPORTED ENDPOINTS.** This work used `/ui/*.action`,
> `/ui/vcops/services/router` (Ext.Direct), and
> `/suite-api/internal/views/{id}/data/export` (needs
> `X-Ops-API-use-unsupported: true`). No back-compat guarantee; may
> change between releases.

---

## Headline verdicts

| # | Hypothesis | Verdict |
|---|---|---|
| 1 | Adding a valid `traversalSpecId` to the pinned View widget's `resource` object makes the pin bind | **Wire-format delta confirmed & mechanism proven; final visual binding needs a browser pass (see "Why binding is browser-only").** All server-side prerequisites verified. |
| 2 | Adding `resource:[{name,id}]` (+ envelope `entries.resource`) to a self-provider HealthChart binds it to the single world object instead of all resources | **Bug root-caused in renderer; format imports cleanly; final visual binding needs a browser pass.** |
| 3 | Distribution-view "No data" is the same root cause as (1) | **PARTIAL / NOT the same.** The pin is missing (same class of bug) but the referenced distribution/resource-pool views return **0 rows or HTTP 400 when rendered against vSphere World** — they are scoped to cluster/resource-pool context, not the world root. Fixing the pin alone will not populate them. |

Plus two prerequisite checks (both green):
- Traversal spec **"vSphere Hosts and Clusters" EXISTS as a built-in** on
  devel — pak-shipped traversal specs are **NOT** required.
- All three raw-UUID view refs in Cluster Performance 2.0 resolve to real
  view definitions.

---

## The precise wire-format delta (this is the tooling brief input)

Read from `src/vcfops_dashboards/render.py` at HEAD, compared to the
vendor export. **Note the installed pak (0.0.0.10) is OLDER than HEAD**
— its cloned export shows the View widget with `selfProvider:false,
resource:null` and HealthCharts with `resource:[]` (no pin emitted at
all). The premise in the brief describes **current HEAD** output, which
does emit a pin but with an empty traversalSpecId. Both are wrong vs the
vendor; HEAD is closer.

### View widget (`_view_widget`, render.py ~955-1005)

Current HEAD emits, for `self_provider and pin`:
```json
"resource": {
  "resourceId": "resource:id:0_::_",
  "traversalSpecId": "",                          // ← BUG (empty)
  "resourceName": "vSphere World",
  "resourceKindId": "002006VMWAREvSphere World",  // already correct
  "id": "Ext.vcops.chrome.model.Resource-1"
},
"traversalSpecId": null,                          // matches vendor (see correction below)
```
Vendor (working):
```json
"resource": {
  "resourceId": "resource:id:0_::_",
  "traversalSpecId": "vSphere Hosts and Clusters-VMWARE-vSphere World",
  "resourceName": "vSphere World",
  "resourceKindId": "002006VMWAREvSphere World",
  "id": "Ext.vcops.chrome.model.Resource-140"
},
"traversalSpecId": null,
```
> **CORRECTION (post-framework-review, 2026-07-13):** the "two places"
> claim below was a transcription error against the vendor export,
> caught by `framework-reviewer`'s byte-compare of the actual JSON
> (`reference/references/vmbro_vcf_operations_vcommunity/Management
> Pack/content/dashboards/Cluster Performance 2.0.json`, widget id
> `46a74d94-9562-4532-b54b-9a7274406b8f`, "vSphere Clusters"). The vendor's
> top-level `config.traversalSpecId` is **`null`**, even on this
> fully-bound pin — the spec string lives **only** in the nested
> `config.resource.traversalSpecId`. `refreshContent` is also `false` on
> this widget, not `true`. `src/vcfops_dashboards/render.py` was corrected
> to match (commit on `fix/dashboard-selfprovider-pin-wire-format`): the
> `_VIEW_PIN_TRAVERSAL_SPEC` enrichment now applies to the nested site
> only; top-level `traversalSpecId` is unconditionally `null` and
> `refreshContent` unconditionally `false` for View widgets. Treat the
> paragraph and "two places" language immediately below as historical —
> retained for the record of how the delta was originally (incorrectly)
> characterized, not as current guidance.

**Original (incorrect) characterization — superseded by the correction
above:** "Exact delta = the `traversalSpecId` string, in two places:
`config.resource.traversalSpecId` and top-level `config.traversalSpecId`."
Everything else (resourceId placeholder, `resourceKindId`,
`selfProvider:true`, `entries.resource[0]`) already matches the vendor.
The string format is `<specName>-<rootAdapterKindKey>-<rootResourceKindKey>`.

### HealthChart widget (`_health_chart_widget`, render.py ~1191-1250)

Current HEAD **hard-codes `"resource": []`** with no pin branch at all,
even when `selfProvider:{"selfProvider": w.self_provider}` is true, and it
never registers the container in `resource_index` (so `entries.resource`
gets no entry from a HealthChart).

Vendor (working self-provider HealthChart):
```json
"selfProvider": {"selfProvider": true},
"resource": [{"name": "vSphere World", "id": "resource:id:0_::_"}]
```
plus the envelope carries:
```json
"entries": {"resource": [
  {"resourceKindKey": "vSphere World", "internalId": "resource:id:0_::_",
   "adapterKindKey": "VMWARE", "identifiers": [], "name": "vSphere World"}
]}
```
**Fix:** when `self_provider and pin`, emit
`resource: [{"name": c_name, "id": f"resource:id:{res_idx}_::_"}]` and
register `(c_adapter, c_kind)` in `resource_index` so the shared
`entries.resource` block includes it (identical container-resolution to
`_view_widget` via `_resolve_view_pin`). Non-self-provider HealthCharts
keep `resource: []`.

---

## Prerequisite check 1 — traversal spec exists (built-in, not pak-shipped)

`GET /suite-api/api/auth/traversalspecs` (public API) on devel returns 26
specs including:
```json
{"name": "vSphere Hosts and Clusters",
 "rootAdapterKindKey": "VMWARE",
 "rootResourceKindKey": "vSphere World",
 "adapterInstanceAssociation": false}
```
The widget `traversalSpecId` string `"vSphere Hosts and Clusters-VMWARE-vSphere World"`
is exactly `name-rootAdapterKindKey-rootResourceKindKey`. It is an
**out-of-the-box** spec present on any instance with the VMWARE adapter —
**the source pak's `traversalspecs/` content dir is NOT a prerequisite**;
we do not need to ship one. (The source pak ships some; they are
redundant with the built-in for this reference.)

## Prerequisite check 2 — the three raw-UUID view refs resolve

Enumerated via Ext.Direct `viewServiceController.getGroupedViewDefinitionThumbnails`
(787 views on devel). All three built-in refs in Cluster Performance 2.0
exist:

| UUID | View name |
|---|---|
| `d8a3767e-9d5e-4bf2-b613-9e3bef977502` | vSphere Cluster Performance List |
| `12fd58e7-82bf-402d-a173-60702566a124` | Performance \| Resource Pool CPU Shares |
| `421ac1e1-91a0-4752-a0fd-5cebad574041` | Performance \| Resource Pool Memory Shares |

(NB: the Ext.Direct thumbnail id field is `viewDefinitionKey`, not `id`.)

## Mechanism proof — the pinned view renders against vSphere World

`GET /suite-api/internal/views/{id}/data/export?resourceId=<world>`
(`X-Ops-API-use-unsupported: true`). vSphere World resource on devel =
`ba1fe374-23fa-4584-9ca5-705cf1c637b0`.

- Pinned View `d8a3767e` (vSphere Cluster Performance List) →
  **HTTP 200, 3 rows** (the 3 clusters). So the pinned View *has* data to
  show once a resource is bound; the empty pin is exactly why the UI shows
  "Select the widget source".
- Distribution views (hypothesis 3): `40c5bbc9` (CPU Shares Distribution)
  and `23b3812d` (Memory Shares Distribution) → **200 but 0 rows** against
  the world; resource-pool share views `12fd58e7` / `421ac1e1` →
  **HTTP 400 "Invalid input format."** against the world. These views are
  scoped to cluster / resource-pool objects, not the world singleton —
  binding the pin to vSphere World will not populate them. Hypothesis 3 is
  therefore a *different* root cause (wrong pin target / view scope), only
  superficially the same "unbound pin" symptom.
- Passing `traversalSpec=<name>` to this **internal render** endpoint
  returns 400 ("Invalid traversal") — the endpoint's `traversalSpec` query
  param is a different contract from the widget's `traversalSpecId` config
  string; do not conflate them.

## Import round-trip — the vendor format imports cleanly

Built a content-import zip (structure below), imported the vendor CP2 as
`APIX-CP2-vendor` and a current-renderer-format copy as `APIX-CP2-current`
(new UUIDs, `APIX-` names, never overwriting the pak). `POST
/api/content/operations/import?force=true` → **state FINISHED, no errors**.
So the vendor `traversalSpecId` string + HealthChart `resource:[{name,id}]`
+ `entries.resource` are a **valid, importable** format (necessary
condition for the fix). Both APIX dashboards deleted afterward (verified).

### Content-import zip structure (for dashboards)

Outer zip:
```
<marker>L.v1                      # per-instance fingerprint; devel = 6844548499441080431L.v1
dashboards/                       # dir entry
dashboardsharings/                # dir entry
dashboards/<ownerUserId>          # NESTED zip (see below)
dashboardsharings/<ownerUserId>   # JSON: [{"groupName":"Everyone","sourceType":"LOCAL","dashboards":[]}]
usermappings.json                 # {"sources":[],"users":[{"userName":"admin","userId":"<uuid>"}]}
configuration.json                # {"dashboardsByOwner":[{"owner":"<uuid>","count":N}],"type":"CUSTOM","dashboards":N}
```
Nested `dashboards/<ownerUserId>` is itself a zip containing:
```
dashboard/dashboard.json                     # {"entries":{...}, "dashboards":[...], "uuid":"..."}
dashboard/resources/resources.properties     # localization stub
```
devel admin `userId` = `29c1613f-3bbe-4aa0-8236-2c74db22c661`.
`import_content_zip()` in `src/vcfops_dashboards/client.py` handles the
`contentFile` field + `Content-Type: None` override + poll.

## Why binding is browser-only observable (important)

There is **no server-side endpoint that reveals self-provider pin
binding**, so hypotheses 1 and 2 cannot be *visually* confirmed without a
browser. Evidence:

1. `mainAction=getDashboardConfig` (`/ui/dashboard.action`) returns **tab
   layout only** — widgets carry `id`, `key` (type), gridster coords, but
   **no `config`**.
2. Content **export of a freshly content-imported dashboard is deferred**:
   the dashboard comes back with `importComplete: false`, and every widget
   is a skeleton — `title` equals the type string ("View"/"HealthChart")
   and `config` is `{}`. The full widget config (and thus any pin
   resolution) **materializes only when the dashboard is first opened in
   the UI**. So a re-export immediately after import shows nothing useful.
3. A server-side **clone** (`mainAction=cloneDashboard`) of an
   already-materialized dashboard *does* export full widget config — but
   the export **re-symbolizes** resources back to the `resource:id:N_::_`
   placeholder + `entries.resource`, so it shows the *authored* format, not
   the runtime-resolved concrete resource id. (This is how the installed
   0.0.0.10 pak's exact broken wire format was captured.)
4. Neither OpenAPI spec exposes a dashboard/widget **data/render** endpoint
   (only `/internal/views/{id}/data/export` for bare views).

**Conclusion:** confirm the actual pin bind with a **qa-tester / Playwright
browser pass** after the renderer fix ships. Do not claim visual binding
from server-side evidence alone.

## Confidence summary for the renderer fix

- View `traversalSpecId` (hypothesis 1): **high confidence** the fix is
  correct — the only delta vs a known-working vendor widget is the
  traversalSpecId string; the spec exists built-in; the view renders
  against the world; the format imports.
- HealthChart `resource` entry (hypothesis 2): **high confidence** — same
  reasoning; the renderer currently emits an impossible self-provider
  widget (`selfProvider:true` + `resource:[]`, which the vendor never
  does).
- Distribution "No data" (hypothesis 3): **do not bundle with the pin
  fix** — those views need a cluster/resource-pool pin target, not vSphere
  World; treat as a separate content-design issue.

## Cross-references
- `knowledge/context/api-surface/dashboard_delete_api.md` — UI auth flow,
  clone/list/delete, deferred-import ownership notes.
- `knowledge/context/api-surface/view_render_internal_endpoint.md` — the
  internal view render endpoint used for the mechanism proof.
- `knowledge/context/api-surface/widget_renderer_scope.md` — widget-type
  renderer inventory (ResourceRelationshipAdvanced also uses
  `traversalSpecId`).
