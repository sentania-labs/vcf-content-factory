# DEF-014 — CPU Support Status dashboard: View widget loses its binding after whole-repo re-sync

**Date:** 2026-07-22 · **Instance:** devel (VCF Operations 9.x lab) · **Posture:** read-only (GETs, documented internal read endpoints, one cloned-then-deleted dashboard). No imports/deletes/edits to the tracked content. `content/` and `src/` untouched.

**Question (one sentence):** After a whole-repo views+dashboards re-sync, why does the "[VCF Content Factory] CPU Support Status" dashboard's View widget render "The widget is not configured. Select a view to render." when the identical content rendered correctly on its first install the same day?

## TL;DR

The rendered content is **provably correct** and the target view is **healthy with the same UUID it has in the repo**. The binding loss is **not** a render/`src/vcfops_dashboards/` defect and **not** a UUID mismatch. It is a **stale lazily-materialized widget binding**: a dashboard's View widget resolves its `viewDefinitionId` to the view's internal identity only when the dashboard is first *opened* (deferred import — `importComplete:false` until then), and re-importing the referenced view churns that internal identity. Updating the dashboard content in place does not force re-materialization, so the previously-materialized widget keeps a dangling binding.

**Fix owner: content re-sync procedure (content-installer), not tooling.** Concrete remediation below. An optional tooling enhancement exists but must be gated on an import experiment that this read-only pass could not run.

## What was verified (facts, not hypotheses)

### 1. The live view is healthy and keeps the repo UUID (Q2 answered)

`viewServiceController.getGroupedViewDefinitionThumbnails` (via `VCFOpsUIClient.list_views()`) returns exactly one match:

```
viewDefinitionKey: 160c5756-1b39-4376-888b-00fad13f1123
name:              [VCF Content Factory] CPU Support Status by Host
viewType:          LIST
```

This is **byte-identical to the repo UUID** (`content/views/cpu_support_status_by_host.yaml`). **Re-import preserved the UUID; it did NOT mint a new one.** The content-zip importer's documented UUID-preservation held.

Server-side render of that view against a live host
(`GET /internal/views/160c5756…/data/export?resourceId=<host>` with `X-Ops-API-use-unsupported: true`) returns HTTP 200 with the correct columns and a live row:

```
columns: Name, Model, CPU Model, CPU Support Status, (summary/grandTotal/groupUUID/objUUID)
row:     esx01 | "To Be Filled By O.E.M. …" | "12th Gen Intel(R) Core(TM) i7-1260P" | CPU Support Status = 0.0
```

The view definition, its SM column, and its data are all intact. **The problem is isolated to the dashboard widget's runtime binding, not the view.**

### 2. The rendered dashboard references the view by its stable UUID, correctly (Q3 answered)

Local read-only render (`render_dashboards_bundle_json`) of `content/dashboards/cpu_support_status.yaml` emits the View widget as:

```json
{
  "id": "6d843552-ef97-54e4-98c1-257a63e18588",
  "type": "View",
  "config": { "viewDefinitionId": "160c5756-1b39-4376-888b-00fad13f1123",
              "selfProvider": {"selfProvider": false}, "resource": null, ... }
}
```

- Binding is **by UUID** (`config.viewDefinitionId = view.id`; `render.py:1079`/`1140`), the stable identity — not by name, not by an internal PK.
- The rendered widget `id` `6d843552-…` **exactly matches** the live dashboard's View-widget `id` (see Q1 below). The widget id is content-derived and deterministic.
- The DEF-013 changes (gridster floor clamp + 0→1-based coords) do not touch `viewDefinitionId` — v1 and v2 render the *same* binding bytes.

So the content the importer received in v2 was correct and pointed at a UUID that exists on the instance. **A render bug is ruled out.**

### 3. The live dashboard exists with the correct widgets and interaction (Q1 answered — with a caveat)

`mainAction=getDashboardConfig` (`/ui/dashboard.action`, dashboard `b6796122-…`) returns the tab layout:

```
widgets:
  - id f9c1e72c-…  key ResourceList  "vSphere Clusters"   (gridster 1,1,12,3)
  - id 6d843552-…  key View          "CPU Support Status…" (gridster 1,4,12,12)
tabInteractions:
  - resourceId  provider f9c1e72c-…  receiver 6d843552-…
```

The View widget is present, correctly placed, and the `resourceId` interaction is wired provider→receiver. **Caveat that turns out to be the whole story:** `getDashboardConfig` returns **tab layout only** — widgets carry `id`, `key`, gridster coords, and `title`, but **no `config` block and hence no `viewDefinitionId`**. This is documented in `dashboard_selfprovider_pin_wire_format.md` §"Why binding is browser-only observable" and was re-confirmed here.

### 4. Widget config is materialized *lazily*, on first UI open (the mechanism)

Two independent confirmations that the per-widget config (including the view binding) does not exist server-side until the dashboard is opened:

- `getDashboardConfig` never returns widget `config` (above).
- A read-only `POST /api/content/operations/export {scope:ALL, contentTypes:[DASHBOARDS]}` → `GET /export/zip` produced a zip whose `dashboards/` folder is **empty** (only `dashboardsharings/`, `usermappings.json`, `configuration.json` present). Freshly (re)imported dashboards export as skeletons with `importComplete:false`; the full widget config materializes only when the dashboard is first opened. This matches the prior finding in `dashboard_selfprovider_pin_wire_format.md` items #1–#2.

So the resolution `viewDefinitionId (UUID) → view's internal identity → bound, renderable widget` happens **at first-open (materialization) time**, and the result is cached in the dashboard's materialized state.

## Why v1 worked and v2 broke (Q4)

Putting the verified facts together:

- **v1 (first install):** view imported fresh → dashboard imported fresh (`importComplete:false`) → dashboard opened → widget **materialized against the then-current view identity** → bound, rendered live rows (Playwright screenshot v1). The materialized binding was cached.
- **v2 (DEF-013 closure whole-repo re-sync):** the **view was re-imported** (same UUID, but its internal/DB identity churns on re-import) **and** the dashboard content was re-imported (coords-only delta). The dashboard's **already-materialized** widget binding still points at the **v1 view identity**, which the view re-import invalidated → the widget resolves to nothing → "The widget is not configured." Updating the dashboard *content* in place did **not** force the widget to re-materialize against the new view identity.

The decisive discriminator: the binding is resolved to the view's **internal identity at materialization time**, not re-resolved from the UUID on every render. If it re-resolved from the UUID each render, the preserved UUID (verified in §1) would have kept it working — and it did not. That is the fingerprint of a **stale materialized binding invalidated by view re-import**.

Note the sync path bundles **views and dashboards into a single content-zip** (`build_import_zip(views, dashboards, …)` in `vcfops_dashboards/cli.py:cmd_sync`), so intra-import ordering is the platform importer's job, not the factory's. The factory did everything right: stable-UUID reference, correct bytes, both artifacts in one envelope.

### Precise statement of the cause

> View re-import churns the view's instance-side internal identity (UUID preserved, internal binding target not). A dashboard that has *already materialized* its View-widget binding caches the old internal identity and is **not** repaired by an in-place content update of the dashboard. Re-importing the dashboard's (correct) bytes is insufficient because materialization is deferred and the stale materialized state survives the update.

## Fix owner and remediation

**Owner: content re-sync procedure (content-installer).** This is not a `src/vcfops_dashboards/` render or sync-bytes defect — the rendered content is correct and references the view by its stable UUID.

**Deterministic remediation (what makes v2 look like v1):** force the dashboard to re-materialize against the *final* view identity. The cheapest reliable way, given deferred materialization:

1. Complete the views import first (they are already correct on the instance).
2. **Delete the dashboard and re-import it** (rather than update-in-place). A freshly created dashboard re-enters the deferred state and materializes its binding on next open against the current view identity — reproducing the v1 success path.
3. Open the dashboard once (or let qa-tester's Playwright pass open it) to trigger materialization, then verify live host rows render.

For any future whole-repo re-sync where a referenced view changes: **treat referencing dashboards as needing delete+reimport, not in-place update**, whenever an upstream view was re-imported in the same run.

**Optional tooling enhancement (needs an import experiment first — not run here, read-only):** `vcfops_dashboards` sync could, when it detects that a referenced view was (re)imported, delete+recreate the dependent dashboard instead of relying on the importer's in-place update, forcing fresh materialization. This is a `src/vcfops_dashboards/` change and would go through the `framework-reviewer` gate. **Do not implement on this evidence alone** — it hinges on confirming (a) that in-place dashboard update leaves materialized state stale and (b) that delete+reimport clears it, both of which require write/import access to prove. Recommend the orchestrator authorize a small import experiment before committing tooling.

## Closure gate (unchanged)

View widget renders live host rows again on devel after the delete+reimport remediation, Playwright-verified. The underlying view is already healthy (§1), so the gate is purely about the dashboard's materialized binding.

## Method log (reproducible)

- Auth: `VCFOpsClient.from_env(profile="devel")` (Suite API bearer) and `VCFOpsUIClient.from_env(profile="devel")` (UI session) — per `vcfops-api` skill.
- Views list: `viewServiceController.getGroupedViewDefinitionThumbnails` via `list_views()`.
- View render: `GET /internal/views/{id}/data/export` (`X-Ops-API-use-unsupported: true`).
- Dashboard layout: `mainAction=getDashboardConfig` (`/ui/dashboard.action`).
- Materialization probe: `cloneDashboard` → clone `63163977-3174-410e-bf3f-99ae649fe10a` created, then **deleted via `deleteTab`** and verified absent (`list_dashboards` shows only the original `b6796122-…`). Also `POST /api/content/operations/export` → `GET /export/zip` (empty `dashboards/` folder confirms deferred export).
- Local render: `render_dashboards_bundle_json` on the checked-in YAML (read-only, no file writes).

## Clean-up verified: yes

Cloned dashboard `63163977-3174-410e-bf3f-99ae649fe10a` deleted; `list_dashboards()` confirms only the original `b6796122-…` remains. No other objects created. No tracked files modified.

## Cross-references

- `knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md` — deferred materialization; getDashboardConfig is layout-only; clone/export behavior.
- `knowledge/context/api-surface/view_render_internal_endpoint.md` — server-side view render endpoint used to prove the view is healthy.
- `knowledge/context/api-surface/dashboard_delete_api.md` — UI-session auth, cloneDashboard, deleteTab.
- `knowledge/context/defects.md` §DEF-013 — the gridster floor clamp / coords change that framed v1→v2.

---

# ROUND 2 — 2026-07-22 (authorized write experiments on devel)

**Posture this round:** controlled writes on devel, scoped to XPROBE-prefixed
probe artifacts I created plus read-only inspection of the two named broken
dashboards (CPU `b6796122-…`, Fleet `762fc025-…`). Trigger: the installer had
already done delete+reimport of the CPU dashboard and a whole views+dashboards
re-sync per Round 1's remediation, and the widget was STILL "not configured" —
and Fleet `762fc025-…` now showed EVERY widget unconfigured, including Heatmaps
(which bind metrics, not views), suggesting whole-widget materialization
failure rather than view-id resolution.

## TL;DR (Round 2 supersedes Round 1's mechanism)

**Round 1's "stale / dangling / unmaterialized binding" mechanism is REFUTED.**
The two "broken" dashboards are, right now, **fully materialized server-side
with correct config**, and are **structurally indistinguishable from a
presumed-working factory dashboard**. There is **no server-side signal that
marks them broken.** If the "not configured" symptom is still real after
materialization, it is a **browser / modern-SPA render-only** phenomenon that
leaves no server fingerprint — a *verification* gap (needs Playwright), not a
`vcfops_dashboards` render-bytes defect on this evidence.

## What was verified (facts)

### 1. The "broken" dashboards are fully materialized and correct

Read via `POST /ui/dashboard.action` (UI session; unsupported endpoints —
carry the `X-Ops-API-use-unsupported` caveat class for all `/ui/*.action` and
Ext.Direct calls):

- **`mainAction=getDashboardList` → `isLoading: false`** for both CPU and Fleet.
  `isLoading` is the deferred-import / materialization flag (see model below).
  `false` = materialization complete.
- **`mainAction=getWidgetConfigs&tabId=<id>`** returns the COMPLETE per-widget
  config store, not a skeleton:
  - CPU View widget `6d843552-…`: `viewDefinitionId = 160c5756-1b39-4376-888b-00fad13f1123`
    (the exact repo UUID), `selfProvider:false`, `resource:null` — which is the
    **correct** shape for an interaction-fed View (it receives a `resourceId`
    from the ResourceList provider; it is not a self-provider pin).
  - Fleet Heatmaps carry full `configs[]` (colorBy/sizeBy/groupBy metric keys);
    the Scoreboard carries its `metric` block; Fleet's self-provider View
    `87769840-…` is bound to vSphere World (`resource.resourceId = ba1fe374-…`).
- **The CPU view renders HTTP 200 with data** via
  `GET /internal/views/160c5756-…/data/export?resourceId=<host|cluster>`
  (default JSON `Accept`). *Caveat that cost time:* passing `Accept: text/csv`
  to this endpoint returns HTTP 500 "Internal Server error, cause unknown" —
  a CSV-path bug, **not** a view-health signal. Use the default JSON accept.
- No duplicate view definition for `160c5756` (single LIST record).

### 2. No server-side signal distinguishes working from broken

CAPACITY (`46f75705-…`, presumed working) and Fleet (`762fc025-…`, broken) have
**byte-for-byte-equivalent** materialized widget shapes: both have self-provider
Views bound to `resource.resourceId = ba1fe374-…` (vSphere World) and
self-provider Scoreboards/Heatmaps with `resource: []` (empty list). So the
empty self-provider `resource` list is **NOT** the differentiator — CAPACITY
carries it too. Nothing readable server-side flags one dashboard as broken and
the other as fine.

### 3. Deferred-import materialization model (newly mapped)

Two distinct server-side stores, populated at different times:

| Store | Endpoint | At import (deferred) | After materialization |
|---|---|---|---|
| Layout | `getDashboardConfig` | FULL immediately (real titles, coords, `tabInteractions`) — but **never** carries per-widget `config`/`importComplete` (layout-only surface) | unchanged |
| Widget config | `getWidgetConfigs` | **SKELETON**: `nkeys=1`, bare-type `title` ("View"/"Object List"), **no** `viewDefinitionId` | **FULL**: complete config incl. `viewDefinitionId` |
| — | `getDashboardList.isLoading` | `true` | `false` |

- A freshly content-imported dashboard lands **deferred**: `isLoading:true`,
  `getWidgetConfigs` skeleton, and the content-ops **export omits the dashboard
  body** (scope=ALL DASHBOARDS exported **zero** dashboard bodies — so export is
  not a usable per-dashboard signal on this build).
- The flip to `isLoading:false` + full `getWidgetConfigs` happens on **first UI
  open OR via a background job over time** — the XPROBE dashboard (imported via
  API, **never** browser-opened) flipped from `isLoading:true` to
  `isLoading:false` on its own **~20 minutes** after import.
- The flip is **not** triggered by any legacy `/ui/dashboard.action` mainAction I
  could call: `openTab`, `loadTab`, `selectTab`, `getTab`, `getDashboard`,
  `refreshWidget`, `materializeTab`, `saveTab`, `saveDashboardConfig`,
  `getDashboardConfig`, `getWidgetConfigs`, and `cloneDashboard` all leave
  `isLoading:true`. `dashboardServiceController.*` (Ext.Direct) does not exist
  (all methods return `Internal server error`). Cloning a skeleton yields a
  skeleton clone. The materializer therefore lives in the modern SPA path
  and/or a timed background worker, not in a callable legacy action.

### 4. Two OTHER factory dashboards are genuinely stuck-deferred

`getDashboardList.isLoading` across all factory dashboards: **MSSQL Query
Performance** and **Oracle Query Performance** are still `isLoading:true`
(never materialized); every other factory dashboard — including the "broken"
CPU and Fleet — is `isLoading:false`. So a *real* stuck-deferred state exists
and is readable; CPU/Fleet are **not** in it. (Worth a follow-up: why MSSQL /
Oracle never materialized — they may be the genuine "unmaterialized" case the
user's mental model is generalizing from.)

## Server-side health signal (for the installer / future triage)

A factory dashboard is **materialized and server-side-healthy** when BOTH:
1. `getDashboardList` entry has `isLoading: false`, AND
2. `getWidgetConfigs&tabId=<id>` returns full config for every widget — View
   widgets carry a non-empty `viewDefinitionId`, Heatmaps a non-empty
   `configs[]`, Scoreboards a `metric` block (NOT `nkeys=1` bare-type skeletons).

Both CPU (`b6796122`) and Fleet (`762fc025`) currently PASS this signal. This is
the fingerprint to check before assuming a re-sync left a dashboard broken.

## Refutation of Round 1, precisely

Round 1 concluded the View widget's binding was a **stale materialized
identity** invalidated by view re-import, and that in-place dashboard update
left it dangling. Round 2's direct reads contradict this: the widget config is
present, complete, and points at the **correct, live, renderable** view UUID;
`isLoading:false`; and a Heatmap (no view dependency) on Fleet shows the same
symptom, which a view-identity mechanism cannot explain. Whatever the browser is
rendering as "not configured", it is **not** reading a stale or empty server-side
widget binding — that store is correct.

## Open question — DEFERRED pending browser re-check

The single decisive experiment — **does an in-place UPDATE re-import
de-materialize a completed dashboard** (flip `isLoading` back to `true` / revert
`getWidgetConfigs` to skeleton)? — was **NOT run this pass.** The orchestrator
took decision (b): a Playwright re-check of both dashboards is running
separately. If that re-check shows CPU and Fleet **render fine** (plausible —
they are now `isLoading:false` and config-complete, and the earlier "broken"
report may have been observed pre-materialization / against browser cache), the
update-de-materialization experiment may be unnecessary. Hold until re-briefed.

If the browser re-check shows them STILL broken despite passing the server-side
health signal above, that **confirms a browser/modern-SPA render-only defect
with no server fingerprint** — at which point the actionable next step is a
Playwright/network-capture pass to find what the modern UI reads that
`getWidgetConfigs` does not, not further tooling changes to `vcfops_dashboards`
render (whose emitted bytes and resulting server state are correct).

## Fix-owner implication (revised)

On Round 2 evidence, **there is no confirmed `src/vcfops_dashboards/` render or
sync-bytes defect** — the bytes and the resulting materialized server state are
correct. Round 1's "content-installer must delete+reimport referencing
dashboards" remediation neither helped (installer already did it) nor is
justified by the mechanism, since the mechanism it targeted is refuted. Do not
brief a `vcfops_dashboards` tooling change on this evidence; gate any further
work on the Playwright re-check outcome.

## Method log (Round 2, reproducible)

- Auth: `VCFOpsUIClient.from_env(profile="devel")` (UI session) and
  `VCFOpsClient.from_env(profile="devel")` (Suite API bearer).
- Materialization/health reads: `mainAction=getDashboardList` (isLoading),
  `mainAction=getWidgetConfigs&tabId=<id>` (per-widget config store),
  `mainAction=getDashboardConfig&tabId=<id>` (layout-only).
- View render: `GET /internal/views/{id}/data/export?resourceId=<id>` with
  `X-Ops-API-use-unsupported: true`, **default JSON Accept** (csv → spurious 500).
- Probe artifacts: view `[VCF Content Factory] XPROBE Host List`
  (`b1ff8c8a-64ce-4b2e-ada5-4b7beec26229`) + dashboard
  `[VCF Content Factory] XPROBE Dashboard` (`65327f04-64ab-40eb-ad7f-be852e534c59`)
  mirroring the CPU ResourceList→View interaction pattern; imported combined via
  `build_import_zip` + `import_content_zip`; used to establish the fresh-import
  skeleton baseline and observe the ~20-min background materialization flip. One
  transient clone (`fb5a6b1d-…`) created + deleted during trigger-hunting.

## Clean-up verified: yes (Round 2)

XPROBE dashboard `65327f04-64ab-40eb-ad7f-be852e534c59` and view
`b1ff8c8a-64ce-4b2e-ada5-4b7beec26229` deleted via UI session; `getDashboardList`
and `getGroupedViewDefinitionThumbnails` confirm both absent. Transient clone
`fb5a6b1d-…` deleted. CPU (`b6796122`) and Fleet (`762fc025`) were READ-ONLY —
not modified. No tracked repo files changed (`content/`, `src/` untouched).
