# Summary dashboard assignment (object detail page)

How to bind a dashboard to an object type so it renders on that object's
Summary tab instead of the built-in detail page. The UI calls this
"Manage Summary Dashboards" (Dashboards & Reports > Dashboards > Manage >
(...) > Manage Summary Dashboards).

Established 2026-08-21 by dissecting 51 real vendor paks offline and by
tracing the live UI on devel (all mutations restored, verified against a
pre-experiment snapshot of all 363 resource kinds).

## Two things to know first

**There is no Suite API for this.** All four OpenAPI specs were searched
by path and by full body text (990 paths total): zero contain "dash". The
only body hit anywhere is the `DASHBOARDS` content-type enum on the
content-import endpoint. This is consistent with dashboards having no REST
CRUD at all (`content_api_surface.md`).

**A pak cannot ship the binding either.** This is a hard negative:

- `describeSchema.xsd` is byte-identical across the 7.0-era and 9.x-era
  paks. `ResourceKindType` has exactly eight attributes (`key`, `nameKey`,
  `showTag`, `type`, `subType`, `credentialKind`, `capacityModel`,
  `dynamic`) and none binds a dashboard.
- Two decoys in that schema: `dashboardOrder` is an integer on
  `ResourceAttributeType` that orders *metrics*; `DASHBOARD` in
  `TraversalSpecKindType/@usedFor` controls which traversals are offered
  when *building* a dashboard.
- The newer YAML-describe generation (`describe.yml`, `traversal.yml`,
  `alerts.yml`) has no dashboard concept at all.
- Pak content is a closed taxonomy: `content/{dashboards,views,reports,
  supermetrics,customgroups,files}` where `files` is only ever
  `reskndmetric`. No pak in the corpus contains a mapping file.
- `post-install.py` drives install, and its entire CLI surface corpus-wide
  is eight verb pairs: `file import`, `control redescribe`,
  `dashboard import`, `view import`, `supermetric import`,
  `report import`, `reskind configure`, `objtype configure`.
  `dashboard import` accepts only `admin <file> --share all --force`.
  The string "summary" appears in zero install scripts corpus-wide.
- The MPB-built Rubrik pak's `design.json` / `export.json` carry no
  binding; `export.json`'s `content` array is literally `[]`.

**Naming is not wiring.** `Pure Storage FlashArray Summary.json`,
`CiscoNetworkingDeviceSummary.json` and `Oracle-Database-Summary.json` all
ship in vendor paks and none is bound to anything. `isDefault` is `false`
on all 36 pak dashboards parsed. Oracle 9.1's "Drill Down" dashboards ship
`hidden: true` with populated `dashboardNavigations`, but that is keyed by
widget UUID: widget-to-widget drill-down, not a summary binding.

## The mechanism that does work

The UI layer. Source: 9.x SPA bundle `app.part6.min.js`, class
`Ext.vcops.dashboard.DashboardAssociateWindow.save()`. Same Struts tier as
the known dashboard delete/list actions, so it needs a `JSESSIONID` plus
the CSRF `secureToken` from the base64-decoded `OPS_SESSION` cookie, not
the Suite API bearer token.

Read current assignments:

```
GET /ui/resourceKind.action?mainAction=getResourceKindList
    &appendDetailPageMappings=true&adapterKindId=<adapterKind>
    &searchField=name&searchText=&page=1&start=0&limit=<n>
```

Returns `resourceKindList[]`, each carrying `resourceKindTemplate` (the
current assignment), plus a top-level `defaultTemplateName`.

Write (bulk; one call carries the whole map):

```
POST /ui/dashboard.action
  mainAction=associateResourceKindDashboards
  dashboardAssociations={"resourceKind_<resourceKindId>":"<dashboardName>_::_<dashboardUuid>", ...}
  secureToken=<csrfToken>
-> 200, body "ok"
```

Restore to the built-in page ("Use Default") is the same POST with the
value `"<defaultTemplateName>_::_null"`.

### The key is resourceKind, not adapter kind

The vendor doc's "Adapter Type" column is only the grid's filter. The id
is deterministic and computable offline:

```
resourceKindId = "0020" + "%02d" % len(adapterKind) + adapterKind + resourceKind
```

Validated against all 363 resource kinds on the devel instance across 14
distinct adapter-kind name lengths: zero mismatches. A generator needs no
lookup call to build the map.

## Two mechanisms share one field: native pages and dashboard-backed pages

This was got wrong twice before it was got right, so read the
discriminator before drawing conclusions from `resourceKindTemplate`.

The object Summary tab branches on exactly one call:

```
POST /ui/dashboard.action  mainAction=getSummaryTabId
     &resourceKindId=&traversalSpecId=&resourceKindType=&resourceId=
  -> {"tabId": <uuid>}  render that dashboard
  -> {"tabId": null}    ResourceSummaryBuilder.getSummaryPanel(...)  [native JS]
```

`ResourceSummaryBuilder` (SPA `app.part4`, class
`Ext.vcops.objectview.Summary`) holds a hardcoded static map
`RESKND_ASSOCIATION` of **51** entries from `resourceKindId` to a compiled
Ext JS class, e.g.
`"002006VMWAREVirtualMachine" -> summaryDetail.vsphere.VMSummaryDetail`.

**So a non-default `resourceKindTemplate` does NOT imply a dashboard
exists.** On prod, of the 32 non-default kinds:

- **23 return `tabId: null`** and have a native class. Every classic
  vSphere, vSAN and VCF summary page is here: `VirtualMachine`,
  `HostSystem`, `Datastore`, `ClusterComputeResource`, `vSphere World`.
  Their `resourceKindTemplate` value is a **label describing the compiled
  page**, not a content pointer. No dashboard exists behind them, and the
  product seeds these by a path no pak or API can reach.
- **9 return a real dashboard UUID** and are genuinely dashboard-backed
  through the association mechanism: VCF Automation, VKS
  (`SupervisorAdapter:GuestCluster`), vSAN Fault Domain, App Monitoring
  DSM.

**Every dashboard-backed one carries a numeric name suffix; none of the
native ones do.** The suffix is a reliable tell in practice, but
`getSummaryTabId` is the authoritative discriminator since it is what the
UI itself branches on.

### The template namespace is invisible to the dashboard list

Materialized templates live in a separate namespace that
`getDashboardList` never returns, under any filter. Confirmed: identical
249 dashboards with `isTemplate` absent, `false`, and `true`, and with
`filterDisabledTabs=false` / `isTemporary=false`. They are readable only
**by UUID**:

```
getDashboardConfig?tabId=<uuid>&isTemplate=true
  -> name='New Summary Page: vSAN Fault Domain 7'  widgets=5
  -> name='VKS Cluster Summary Page 3'            widgets=17
```

Real dashboards with widgets, whose name is exactly the grid label
including the suffix. There is **no list endpoint for this namespace**, so
materialized templates cannot be enumerated, diffed, or garbage-collected
without knowing their UUIDs in advance. Capture the UUID at assign time or
lose track of it.

### What the precedent is actually worth

Narrower than a first read suggests, and newer:

- We would **not** be doing what VMware does for `VirtualMachine` and
  `HostSystem`. Those are compiled UI on a privileged path.
- We **would** be doing what Broadcom does for its own *modern* adapters:
  VCF Automation, VKS, vSAN Fault Domain and DSM all ship dashboard-backed
  summary pages through this exact call, in 9.1.
- The `... 3` / `... 7` suffixes on those shipped names prove Broadcom's
  own build pipeline re-runs the association and collides with itself when
  it does.

For a **new** adapter with no native classes and no prospect of getting
any, the dashboard-backed path is the only path, and it is the same one
Broadcom uses for its own new adapters.

## The caveat that decides any design, and is UNVERIFIED

The platform does **not** share one dashboard across several kinds. Each
assignment materializes an independent server-side detail-page template.
Binding one dashboard to three resource kinds produced templates named
`X`, `X 1`, `X 2`, while the dashboard inventory was unchanged (176
before, 176 after), so these are template records rather than cloned
dashboards.

**Whether editing the source dashboard later propagates into
already-materialized templates was NOT tested.** The expectation is that
it does not. Answer this before designing anything that ships updates,
because it decides whether an update is a re-push or a re-assign.

## Support posture

This is the undocumented Struts UI layer: session-cookie auth, no Suite
API, no OpenAPI coverage in any of the four specs. It is the same tier
that carries the `X-Ops-API-use-unsupported` caveat and can change between
releases without notice. Anything the factory builds on it should treat
that as a stated, conscious dependency, not an implementation detail.
