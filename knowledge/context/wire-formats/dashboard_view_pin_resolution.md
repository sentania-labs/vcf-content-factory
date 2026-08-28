# Self-provider View pin: the importer binds by resource DISPLAY NAME

- Date: 2026-08-26, tooling. Instance: devel (VCF Operations 9.1.1.0,
  profile `devel`, admin, disposable). One throwaway content-zip import,
  deleted afterwards. Resource listing cross-checked on qa (9.2.0.0).
- Question: a pinned View widget carries `config.resource.resourceId:
  "resource:id:N_::_"` plus `entries.resource[N].name`. Does the importer
  resolve `name` against the resource kind key or the resource display
  name? `render.py` wrote the kind key for world singletons while its own
  comment said the importer matches display names.

## Method

One zip, one throwaway list view on `NSXTAdapter / NSXT World`, two
otherwise identical dashboards, each with one `selfProvider: true` View
widget pinned to that kind. `NSXT World` is the kind key; the single
resource of that kind is displayed as `NSX World` on both devel and qa
(`GET /api/resources?adapterKind=NSXTAdapter&resourceKind=NSXT World`).

| Dashboard | `entries.resource[].name` / `config.resource.resourceName` |
|---|---|
| A | `NSXT World` (kind key, the renderer's fallback) |
| B | `NSX World` (display name) |

Import: `FINISHED`, `VIEW_DEFINITIONS imported=1`, `DASHBOARDS imported=2
failed=0`. Both dashboards then polled on `POST /ui/dashboard.action`
(`getDashboardList.isLoading`, `getWidgetConfigs&tabId=`) every 30 s.

## Result

| t | A (kind key) | B (display name) |
|---|---|---|
| 0 s | `isLoading: true`, skeleton (`{"title": "View"}`) | same |
| ~125 s | unchanged | `isLoading: false`; full config; `config.resource.resourceId` = the real resource UUID (`7fded7a8-...`, identical to the `/api/resources` identifier), `resourceName: "NSX World"` |
| 9.5 min | still `isLoading: true`, skeleton | unchanged |

Verdict: **the importer resolves `entries.resource[].name` against resource
display names.** A pin whose name is a kind key that is not also a display
name never binds; the import still reports success, and the dashboard sits
in the "genuinely stuck-deferred" state (`isLoading: true` indefinitely,
the failure mode `knowledge/lessons/dashboard-import-deferred-materialization.md`
rule 3 describes). Materialization of a well-formed dashboard took about
two minutes on this build, not the ~20 minutes observed on 2026-07-22.

## Consequence for the renderer (`render._resolve_view_pin`)

Resolution order is now: explicit `pin.name` > leaf-kind redirect table
(`_VIEW_PIN_CONTAINER`, e.g. HostSystem -> vSphere World) > world
display-name table (`_WORLD_DISPLAY_NAME`) > kind key.

`_WORLD_DISPLAY_NAME` seeds: `NSXTAdapter/NSXT World -> NSX World`
(live-verified 9.1.1 and 9.2), `CASAdapter/CAS World -> Automation World`
and `VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD -> License Usage` (both from
the public VCF License Consumption Overview export's `entries.resource[]`
and the VCFAutomation reference dashboard; neither kind has an instance on
devel or qa today, so those two are export-evidenced, not live-verified).
Kinds whose display name equals the kind key (vSphere World,
ComplianceWorld) are unchanged, so existing content renders byte-identical.

YAML override for any other kind:

```yaml
pin:
  adapter_kind: SomeAdapter
  resource_kind: Some World
  name: Some World Display Name   # what the instance shows in the object browser
```

**Unverified: `pin.name` on a leaf kind.** Everything above was proven on
world singletons (one resource per kind). Pinning a single leaf resource by
name (e.g. `VMWARE/HostSystem`, name `esx01.lab`) has never been imported
live; if the importer also matches on kind, or the resolved entry does not
bind, it is a fresh route to the stuck-deferred state in
`knowledge/lessons/dashboard-import-deferred-materialization.md`. The loader
therefore rejects `pin.name` for any kind in `render._VIEW_PIN_CONTAINER`
until a probe (same method as above, one throwaway dashboard) shows it
materializing with a concrete `resourceId`. To lift the block: run the
probe, record it here, remove the loader check.

The reverse path (`reverse.py`) emits `pin.name` only when
`entries.resource[].name` differs from what the renderer would derive, so
reversed YAML stays minimal.

## Follow-ups (not done here)

- `ops-recon` should confirm the `CAS World` and `LICENSE_USAGE_WORLD`
  display names on the 8.x target before the License Consumption rebuild
  installs (5.5 of the 2026-08-26 inventory flags that 8.x may name them
  differently).
- A validate-time WARNING for pins to kinds outside both tables was
  considered and not added: it would fire on every ComplianceWorld pin in
  the repo. Revisit if a second stuck-deferred pin shows up.
