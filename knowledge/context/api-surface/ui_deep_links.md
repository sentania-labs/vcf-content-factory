# VCF Ops UI — deep links to dashboards and views

**Source:** `qa-tester` visual pass, 2026-07-27, devel (VCF Operations 9.1),
navigated with Playwright `browser_navigate`.

**Why this file exists:** finding an installed dashboard or view in the 9.x
UI has cost **multiple sessions** of failed navigation. The failure is not
subtle-and-rare, it is systematic: the obvious affordance (global search)
does not do what everyone assumes it does. Recording the working route and
the direct URLs so no future session re-derives them.

## The trap: global search is a category picker, NOT a deep-linker

Two separate sessions burned time driving the global search box expecting it
to jump to a dashboard or view by name. **It does not deep-link.** It
resolves to categories//object types, not to a specific dashboard or view
definition. Do not use it for this.

## Working route (click path)

```
left nav → Infrastructure Operations → Dashboards & Reports
           (/vcf-operations/ui/operations/dashboards)
        → 3-pane picker, use the Search box inside the picker
        → click the tree item  → deep-links to the object
```

The Search box **inside** the Dashboards & Reports picker is the one that
works. The global one at the top of the shell is not.

## Direct URLs (tested on devel 9.1)

```
Dashboard:  /vcf-operations/ui/operations/dashboards/dashboards;tabId=<dashboard-uuid>
View:       /vcf-operations/ui/operations/dashboards/views;viewDefId=<view-uuid>
```

Note the **matrix-parameter** syntax (`;tabId=`, `;viewDefId=`) — a
semicolon, not a `?` query string. Both were confirmed navigable directly.
The UUIDs are the same ones `validate` assigns and the content-zip preserves,
so a factory-authored object can be linked straight from its YAML `id:`.

## First open triggers materialization — expect a delay

A freshly imported dashboard is a **skeleton** (`importComplete:false`); its
widget config materializes only when the dashboard is first opened. In this
session `getDashboardList.isLoading` flipped `false` roughly **3 minutes**
after first open — versus **up to ~20 minutes** when left to the background
worker.

So: opening the dashboard is itself the fastest way to force materialization.
If a QA pass needs a dashboard renderable promptly, open it and wait ~3 min
rather than waiting on the background job.

This is the same deferred-materialization mechanism behind the DEF-014
stale-binding defect — see
`knowledge/context/investigations/def014-view-binding-loss-2026-07-22.md` §4
for the full model (widget bindings resolve to the view's *internal identity*
at materialization time, not per-render from the UUID).

## Caveats

- **Unsupported/UI surface.** These are Angular app routes, not an API.
  They carry no compatibility guarantee and may change between releases.
  Tracked working on devel 9.1 (VCF Operations), 2026-07-27.
- Only the two route shapes above were tested. Reports, alert definitions
  and other object types were **not** probed — do not assume the
  `;<param>=<uuid>` pattern generalises without checking.
- Requires an authenticated UI session (see
  `knowledge/context/api-surface/vcf_operations_api_surface.md`
  §"Authentication flows" for the `/ui/` session recipe).
