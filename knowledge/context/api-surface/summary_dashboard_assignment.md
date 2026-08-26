# Summary dashboard assignment (object detail page)

How to bind a dashboard to an object type so it renders on that object's
Summary tab instead of the built-in detail page. The UI calls this
"Manage Summary Dashboards" (Dashboards & Reports > Dashboards > Manage >
(...) > Manage Summary Dashboards).

Established 2026-08-21 by dissecting 51 real vendor paks offline and by
tracing the live UI on devel (all mutations restored, verified against a
pre-experiment snapshot of all 363 resource kinds).

> **Correction 2026-08-25:** the "A pak cannot ship the binding" section
> below is wrong. The server-side pak installer reads
> `content/dashboards/dashboards.properties` and binds dashboards to
> resource kinds at install time (present since at least 9.0). See
> `summary_dashboard_pak_binding.md`. The UI mechanism documented here
> is still accurate and is the same code path.

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

Entry keys (verbatim sample, filtered to public vSphere / vSAN / generic
kinds: `reference/docs/extracted/summary-dashboard-assignment/`):
`resourceKindId` (the computed id below), `resourceKind`, `adapterKind`,
`name` (display label), `resourceKindTemplate`, and on kinds with a
built-in summary page a per-entry `defaultTemplateName` (for example
`HostSystem` -> `Host System Summary`, distinct from the top-level
`Summary Detail`). There is no `id`, `key`, or `resourceKindKey`;
`bind-summary` matches on `resourceKindId` and falls back to the
(`adapterKind`, `resourceKind`) pair.

Write (bulk; one call carries both maps, from the SPA's
`DashboardAssociateWindow.save()` and the disassembled `DashboardAction`;
provenance in the 2026-08-25 note at the end of this file):

```
POST /ui/dashboard.action
  mainAction=associateResourceKindDashboards
  assignedAssociations={"resourceKind_<resourceKindId>":"<dashboardName>_::_<dashboardUuid>", ...}
  resetAssociations={"resourceKind_<resourceKindId>":"<defaultTemplateName>", ...}
  secureToken=<csrfToken>
-> 200, body "ok"
```

Both parameters are always present (`{}` when empty); the server reads
each with `request.getParameter` and a missing one NPEs into the generic
ERRPANEL with HTTP 200. Binds go in `assignedAssociations`. Restore to the
built-in page ("Use Default") goes in `resetAssociations`, whose value is
the kind's **plain** `defaultTemplateName` (the per-entry one from
`getResourceKindList` when present, e.g. `Host System Summary`; no
`_::_null` suffix). The parameter name `dashboardAssociations` does not
exist on any build and an earlier version of this section that used it was
wrong.

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
  -> {"tabId": <uuid>, "isDashboard": true}  render that dashboard
  -> {"isDashboard": false}                    ResourceSummaryBuilder.getSummaryPanel(...)  [native JS]
```

A null `tabId` is encoded by OMITTING the key (org.json drops null
values); clients treat a missing `tabId` as null. Full shape list in the
2026-08-25 note at the end of this file.

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
  summary tabs through this exact call, in 9.1.
- The `... 3` / `... 7` suffixes on those shipped names prove Broadcom's
  own build pipeline re-runs the association and collides with itself when
  it does.

For a **new** adapter with no native classes and no prospect of getting
any, the dashboard-backed path is the only path, and it is the same one
Broadcom uses for its own new adapters.

## Assignment is COPY, not reference (demonstrated)

Settled by controlled experiment on devel, not inferred.

Assigning source dashboard `b6796122-...` to one resource kind produced:

```
source dashboard UUID : b6796122-4c9b-4770-83d8-10f785755ef2
summary tabId         : 95d49327-39f1-404e-8bc4-f828fc6391ea   <- different
```

The association **materializes an independent snapshot** with its own UUID
and its own copy of the widgets. It does not store a pointer to your
dashboard.

Consequences, all of which any design must handle:

- **Editing the source dashboard after assignment does NOT propagate.**
  The materialized template is a point-in-time copy.
- **Re-assigning to publish an update replaces the copy server-side.**
  For each assigned entry the action calls `saveDashboardAsTemplate(...)`
  and, if the kind already pointed at a different template id, deletes
  the old one (`deleteDashboardTemplate(old)`) in the same call. The
  numeric suffixes on Broadcom's shipped names (`New Summary Page: vSAN
  Fault Domain 7`) come from the pak install path, not from this call.
- **Unassigning through `resetAssociations` deletes the copy** when the
  reset value's id matches the current one; `getSummaryTabId` then answers
  `{"isDashboard": false}` (no `tabId` key).
- **The update story is therefore "assign again."** There is no in-place
  update and no client-side cleanup step.

### Enumerating and deleting templates: no such actions

`dashboard.action` has **no** `getTemplateList` and **no** `deleteTemplate`
branch on any build examined (the class contains neither string). Sending
either falls through `execute()` to `SUCCESS` with no result mapping, and
Struts renders the ERRPANEL; an earlier version of this section misread
that fallthrough as a privilege check. The only `getTemplateList` /
`deleteTemplate` in the webapp belong to `payloadTemplateList.action`
(notification payloads) and are unrelated.

Template lifecycle is owned entirely by `associateResourceKindDashboards`
(replace on re-assign, delete on reset). Materialized templates remain
readable only by UUID (`getDashboardConfig?tabId=<uuid>&isTemplate=true`);
capture the UUID at assign time from `getSummaryTabId`. A separate
enumeration path, if one exists, is still to be found.

## Native summary tabs cannot be shipped or added

Both answers are no, and the evidence was gathered by trying to falsify
them.

`RESKND_ASSOCIATION` appears **exactly twice** in the entire 11 MB SPA:
once as a `statics:{...}` object literal in `ResourceSummaryBuilder.js`,
and once as a read inside `getSummaryPanel`. Zero writes, zero merges, no
`Ext.apply` onto it. `getSummaryPanel` is pure compile-time dispatch (static
map lookup, then a hardcoded prefix chain for AWS / Azure / GCP / Container
/ Network Insight, then a generic fallback) and makes **no server call**.
The only thing the server contributes to the summary tab is the single
`getSummaryTabId` answer: a dashboard UUID, or null.

The decisive falsifier reinforces it: of the 11 adapter kinds carrying
native classes, **8 are not installed on the instance at all** (AWS, Azure,
GCP, VMC, VMCd, AVS, GCVE, OCVS). The SPA ships their summary classes
unconditionally. That is compile-time inclusion; runtime registration would
only produce entries for adapters actually present.

All 11 are Broadcom first-party. **Zero** third-party or factory adapters
have one: `synology_diskstation`, `unifi_controller`,
`vcfcf_compliance`, `vcfcf_vcommunity_vsphere` and
`ManagementPackBuilderAdapter` all come back negative. There is no
counterexample of a pak-delivered adapter with a native page.

No extension point exists: no registry, no plugin class, no per-adapter UI
contribution hook. The only dynamic script load anywhere in the SPA is
`lib/jsoneditor/jsoneditor.min.js`; all 95 `summaryDetail.*` classes are
compiled in.

**The one genuine pak-to-SPA channel is images.** A pak's
`conf/images/ResourceKind/*.png` is served back as
`images/resknd/custom/16x16/<adapter>_<kind>.png`. Icons, not code.

Adding an entry would mean editing a minified product bundle on the
appliance: a modification to product files rather than content, reverted by
any upgrade, and a manual infra change of exactly the kind the standing
rules forbid.

So the dashboard-backed association is the **only** mechanism available for
any adapter we ship, and it is the same one Broadcom uses for its own newer
adapters. For a new adapter that will never have a native class, that is
not a downgrade; it is the only door, and Broadcom uses it too.

## Factory tooling (2026-08-25)

Declared in dashboard YAML as `summary_for: "<AdapterKind>:<ResourceKind>"`
(exactly two colon tokens; validated). One dashboard may bind to several
kinds: `summary_for` also accepts a YAML list of such strings or one
comma-separated string (`"VMWARE:HostSystem,VMWARE:VirtualMachine"`); the
loader normalizes all three shapes to a list (`Dashboard.summary_for`,
tokens stripped, order kept) and rejects a kind listed twice in one
dashboard. The cross-dashboard uniqueness check is per kind, not per
dashboard: any kind may be claimed by one dashboard only, whichever shape
declared it. Validation then requires every non-Section widget to have
`self_provider: false` and no pin / `pin_to_world`, because a summary
dashboard inherits the page object.

Two routes carry the binding, one implementation each:

- **Pak** (Tier 2 SDK builds): `src/vcfops_managementpacks/sdk_builder.py`
  writes `content/dashboards/dashboards.properties` with
  `<dashboard dir>=<AK>:<RK>[,<AK>:<RK>...]` (the kinds comma-joined, the
  shape the installer parses) for every bundled dashboard that declares
  `summary_for`; the server-side installer binds at install time
  (`summary_dashboard_pak_binding.md`). Tier 1 MPB paks do not bundle
  dashboards at all (`builder.py` writes an empty `content/dashboards/`).
- **Post-import** (content-zip installs): `python3 -m vcfops_dashboards
  bind-summary --profile <p> [--dashboard <name>] [--unbind] [--dry-run]`,
  implemented in `src/vcfops_dashboards/summary_bind.py` over the
  `VCFOpsUIClient` methods `get_resource_kind_list`,
  `associate_resource_kind_dashboards(assigned, reset)` and
  `get_summary_tab_id` (`ui_client.py`; all send
  `X-Requested-With: XMLHttpRequest` plus `secureToken`). Per dashboard it
  resolves the installed dashboard **by name** (identity is the name,
  `id_guard.py`), computes each listed kind's resource kind id offline,
  reads every kind's current assignment (one `getResourceKindList` per
  distinct adapter kind), writes ONE `associateResourceKindDashboards`
  call whose `assignedAssociations` map carries every kind
  (`{"resourceKind_<id>": "<name>_::_<uuid>", ...}`, with
  `resetAssociations` `{}`; the map takes many entries and the server
  materializes one template copy per kind), then reads `getSummaryTabId`
  back per kind: the bind counts only when every answer carries
  `isDashboard: true` and a `tabId`, printed per kind as `LIVE tabId` /
  `template UUID` (that copy is what renders for that kind). A listed kind
  absent on the instance is printed as `ERROR` (dashboard name and kind)
  and left out of the map; the resolvable kinds are still bound and the
  run exits 2 so the miss is not silent. This mirrors the pak installer,
  which associates each kind independently, so the partial map is the
  same state a pak install would leave; re-running after the adapter
  catches up is idempotent. The dashboard is skipped whole only when none
  of its kinds resolve. `--unbind` behaves the same. The server replaces a kind's
  previous copy on every re-bind, so there is no client-side template
  cleanup. `--unbind` writes `resetAssociations`
  `{"resourceKind_<id>": "<defaultTemplateName>", ...}` for every listed
  kind, using each kind's per-entry `defaultTemplateName` (top-level value
  as fallback) with `assignedAssociations` `{}`, and expects a null
  `tabId` back for each. A missing `tabId` key is treated as null
  everywhere. `--dry-run` prints the full maps without a session.

The wire shape is unit-tested with a fake client
(`tests/test_dashboard_summary_for.py`) and the parameter names were
confirmed with a no-op call (two empty maps) on 9.1 and 9.2 dailies. Live
binds belong to `content-installer`, after install, on explicit
confirmation.

## Support posture

This is the undocumented Struts UI layer: session-cookie auth, no Suite
API, no OpenAPI coverage in any of the four specs. It is the same tier
that carries the `X-Ops-API-use-unsupported` caveat and can change between
releases without notice. Anything the factory builds on it should treat
that as a stated, conscious dependency, not an implementation detail.

## 2026-08-25 note: 9.2 pre-release build and the ERRPANEL failures

Diagnosed against `DashboardAction.class` pulled read-only from the
appliance UI webapp and disassembled, plus `web.log` on the appliance,
plus the SPA's `DashboardAssociateWindow.save()`. Checked on two builds:
a 9.2.0.0 pre-release build and the devel instance (its
`lastbuildversion.txt` reads a 9.0.0.0 pre-release build). **Both builds carry
byte-identical logic for the three actions below; nothing here is a 9.2
change.** Classification for all three: **(c) request shape, client
defect**, not a regression, not a privilege check, not environmental.

### `associateResourceKindDashboards`: wrong parameter name

`web.log` at the client call:

```
[com.vmware.vcops.ui.util.MainPortalListener.log] -  (
Url: /ui/dashboard.action
Params: mainAction=associateResourceKindDashboards
)
java.lang.NullPointerException
	at java.util.Objects.requireNonNull
	at java.io.StringReader.<init>
	at org.json.JSONTokener.<init>(JSONTokener.java:101)
	at org.json.JSONObject.<init>(JSONObject.java:534)
	at com.vmware.vcops.ui.action.DashboardAction.associateResourceKindDashboards(DashboardAction.java:2073)
	at com.vmware.vcops.ui.action.DashboardAction.execute(DashboardAction.java:261)
```

Lines 2071-2073 of the action read
`request.getParameter("assignedAssociations")` and
`request.getParameter("resetAssociations")`, then `new JSONObject(assigned)`.
The string `dashboardAssociations` is not a request parameter on either
build. The client sends `dashboardAssociations`, the server sees null,
NPE, and the Struts error interceptor renders the generic ERRPANEL with
HTTP 200. The SPA's `save()` sends exactly:

```
POST /ui/dashboard.action
  mainAction=associateResourceKindDashboards
  assignedAssociations={"resourceKind_<resourceKindId>":"<dashboardName>_::_<dashboardUuid>", ...}
  resetAssociations={"resourceKind_<resourceKindId>":"<defaultTemplateName>", ...}
  secureToken=<csrfToken>
-> 200, body "ok"
```

Two maps, both always present (send `{}` when empty). Binds go in
`assignedAssociations`; "Use Default" goes in `resetAssociations`, whose
value is the plain default template name (the SPA does not append
`_::_null` there). Verified: the corrected shape with two empty maps
returns `200 ok` on both builds; the same call with `dashboardAssociations`
returns the ERRPANEL on both builds. The earlier "Write (bulk)" section
above is therefore wrong on the parameter name and on the restore value.

Server-side behaviour of the corrected call, from the bytecode (not yet
exercised live):

- For each assigned entry, the server calls `saveDashboardAsTemplate(
  uuid, name, TemplateSection.SUMMARY, userId, true)` and stores the
  returned template id (the COPY semantics above hold).
- **If the kind already had a different template id, the old template is
  deleted server-side** (`deleteDashboardTemplate(old)`) in the same call.
  Re-assigning therefore replaces rather than accumulates on these
  builds; the accumulation claim above describes older behaviour or the
  pak path, and should be re-verified before relying on it either way.
- A reset entry removes the kind from the association map and deletes
  its template if the reset value's id matches the current one.
- Ids in `DataRetrieverUtils.ootbDashboardTemplateIds` (built-in
  templates) are stored as-is without copying.
- Every change is audit-logged as `DASHBOARD_ASSOCIATE` with the raw
  `assignedAssociations` string.

### `getTemplateList`: not a `dashboard.action` action at all

`web.log`:

```
[com.vmware.vcops.ui.util.MainPortalListener.log] - No result defined for action com.vmware.vcops.ui.action.DashboardAction and result success (
Url: /ui/dashboard.action
Params: mainAction=getTemplateList
)
No result defined for action com.vmware.vcops.ui.action.DashboardAction and result success - action - file:/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/WEB-INF/classes/struts.xml:99:81
	at org.apache.struts2.DefaultActionInvocation.executeResult(DefaultActionInvocation.java:392)
```

`DashboardAction.execute()` has no `getTemplateList` branch and no
`deleteTemplate` branch on either build (the class contains neither
string). An unknown `mainAction` falls through, `execute()` returns
`SUCCESS`, and the `dashboard` action mapping in `struts.xml` defines
only `Etalon` and `ContainerDetails` results, so Struts throws "No result
defined" and the ERRPANEL is rendered. The only `getTemplateList` in the
webapp is `PayloadTemplateListAction` (notification payloads), and the
SPA never sends `mainAction=getTemplateList` to `dashboard.action`. The
"Enumerating and deleting templates" section above is wrong: there is no
template list or template delete on `dashboard.action`, and the
"privileged, works for admin" explanation was a misread of this same
fallthrough. Template cleanup is done by the association call itself
(see above); a separate enumeration path, if one exists, is still to be
found.

### `getSummaryTabId` returning only `{"isDashboard": false}`

From `execute()` lines 227-258 (identical on both builds):

```
tabId = dataRetriever.getSummaryDashboardId(resourceKindId)   // may be null
isDashboard = tabId != null && UUID.fromString(tabId) parses
json.put("tabId", tabId)            // org.json drops the key when the value is null
json.put("isDashboard", isDashboard)
if (tabId != null && !isDashboard) json.put("pluginExist", UtilityAction.pluginExist(tabId))
```

So `{"isDashboard": false}` is the null-tabId answer: `org.json` omits a
key whose value is null, which is why `tabId` is absent rather than
`null`. The shape is not a 9.2 change. Three shapes are possible:

- `{"isDashboard": false}`: no association, native page renders.
- `{"tabId": "<uuid>", "isDashboard": true}`: dashboard-backed.
- `{"tabId": "<non-uuid id>", "isDashboard": false, "pluginExist": <bool>}`:
  a legacy plugin-page id is stored for the kind.

Clients must treat a missing `tabId` key as null. The `resourceKindId`
parameter is also required non-blank; a blank one skips the lookup and
returns `{"isDashboard": false}` as well. There is one hardcoded special
case: for `resourceKindId` containing `002016AmazonAWSAdapter` the
`tabId` is forced to null.
