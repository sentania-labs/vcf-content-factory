# View widget: list every object of one kind (custom group types included)

- Date: 2026-10-28, api-explorer. Instance: devel (VCF Operations 9.x lab).
- Trigger: TOOLSET GAP on `content/dashboards/application_allocation_summary.yaml`.
  The View widget is `self_provider: true` with no `pin`; the renderer emits
  `selfProvider:false, resource:null` and the widget shows "Select the widget
  source...". Goal: list all six `Container / (Custom) Application` groups with
  the view's Sum summary row, regardless of which `(Custom) Porfolio` group
  contains them.

> **UNSUPPORTED ENDPOINT.** The render checks used
> `GET /suite-api/internal/views/{id}/data/export` (needs header
> `X-Ops-API-use-unsupported: true`; no back-compat guarantee). See
> `knowledge/context/api-surface/view_render_internal_endpoint.md`.

## Answer in one line

There is no "all objects" source at the widget or view level. A list view
applies to one object and walks its `self` + `descendant` relationships. To
list every object of a kind that has no natural common ancestor (custom groups),
create a dynamic **helper custom group whose rule names that kind with no
conditions**, and pin the self-provider View widget to the helper group by name.
This is the community vendor pattern (vmbro hardware vCommunity "Dell EMC
Servers") and was proven live on devel for the Application case.

## 1. What OEM/community content pins to

Tally of `resourceKindId` on pinned widgets across `reference/references/**`:
`002006VMWAREvSphere World` (25), `002009ContainerEnvironment` (4),
`002006VMWAREDatastore` (4), three MPB worlds, one ClusterComputeResource.
Nothing pins to `Universe`, a traversal-spec root, or an "all objects" token
for a View widget. (`Universe` pins exist only on IntSummary/ProblemAlertsList
widgets, `knowledge/context/api-surface/widget_types_survey.md`, which are not
relational list views.)

The custom-group pattern, verbatim from
`reference/references/vmbro_vcf_operations_hardware_vcommunity/Management Pack/content/dashboards/Dell EMC Servers.json`
(same shape in `Dell EMC Server Workbench.json`, `Dell EMC Server Ping Response.json`):

```json
"entries": {"resource": [{"resourceKindKey": "Environment",
  "internalId": "resource:id:0_::_", "adapterKindKey": "Container",
  "identifiers": [], "name": "Dell EMC Servers"}]}
...
"config": {
  "resource": {"resourceId": "resource:id:0_::_", "traversalSpecId": "",
    "resourceName": "Dell EMC Servers",
    "resourceKindId": "002009ContainerEnvironment",
    "id": "Ext.vcops.chrome.model.Resource-37"},
  "traversalSpecId": null,
  "selfProvider": {"selfProvider": true},
  "viewDefinitionId": "e4b8fd54-3f27-430e-b039-d0b2c4a5be03"}
```

The pinned group, `.../content/customgroups/Dell EMC Servers.json`, is an
`Environment` group whose only rule group names a kind with **no conditions**:

```json
{"resourceKind": "Environment", "adapterKind": "Container",
 "autoResolveMembership": true, "name": "Dell EMC Servers",
 "membershipDefinition": {"ruleGroups": [
   {"resourceKind": "PhysicalServer", "adapterKind": "HardwarevCommunity", "rules": []}]}}
```

i.e. "every PhysicalServer", which the view then lists as descendants.

## 2. Is there a view-level "all objects" setting? No.

- View XML subject is always a `SubjectType` pair `type="descendant"` and
  `type="self"` (all 300+ SubjectType elements in the corpus; factory
  `render.py` ~965-979 emits the same pair). Applicability is purely
  relational. No attribute in the corpus scopes a view to "all of kind".
- Vendor docs, View widget (`reference/docs/vcf9/dashboards.md` ~6216-6250):
  self-provider Input Data is "Inventory trees: select a predefined traversal
  spec to pick an object" + "Object". One object; no environment-wide option.
  `reference/docs/vcf9/views-reports.md` ~552: "The subject you specify
  determines where the view is applicable."
- Live (`/internal/views/8580e840-.../data/export?resourceId=`), view
  `[VCF Content Factory] Application Allocation Summary`:

| Source object | Result |
|---|---|
| `Universe` (Container/Universe) | 400 "The specified view is not applicable to the specified resource(s)." |
| `Container` adapter instance | 400 not applicable |
| `vSphere World` | 400 not applicable |
| any of the above + `traversalSpec=Custom Groups` | 400 "Invalid traversal specification name" (the "Custom Groups" tree in `/api/auth/traversalspecs` has root `?/?`; its type folders are not resources) |
| `Portfolio Home` | 200, 3 rows + Total |
| `LabApp4 Home` (self) | 200, 1 row + Total |

Relationship facts on devel: each `(Custom) Application` has exactly one
parent (a `(Custom) Porfolio` group); both Portfolio groups have **no
parents**; `Universe`'s children are adapter instances; the Container adapter
instance has no children. So no existing object is an ancestor of all six.

## 3. Live proof of the helper-group pattern

`POST /api/resources/groups` (public API):

```json
{"resourceKey": {"name": "zz-apiexplorer-all-apps-probe",
  "adapterKindKey": "Container", "resourceKindKey": "Environment"},
 "autoResolveMembership": true,
 "membershipDefinition": {"includedResources": [], "excludedResources": [],
  "custom-group-properties": [],
  "rules": [{"resourceKindKey": {"resourceKind": "(Custom) Application", "adapterKind": "Container"},
   "statConditionRules": [], "propertyConditionRules": [], "resourceNameConditionRules": [],
   "relationshipConditionRules": [], "resourceTagConditionRules": []}]}}
```

- 201. The server accepts a rule with zero conditions.
- Membership resolved immediately (first poll): all six Applications.
- View render against the probe group: 200, **6 rows + Total**
  (Total = VMs 3, vCPU 6, Mem 10 GB, Storage 142.3 GB), spanning both
  Portfolios. The helper group is type `Environment`, so it does not
  appear as a row in a view whose subject is `(Custom) Application`.
- Clean-up: `DELETE /api/resources/groups/{id}` 200; GET returned 200 for a
  few seconds (async delete), then 404 on both `/groups/{id}` and
  `/resources/{id}`.

Groups of groups are normal here: `Portfolio Home` is itself a dynamic
group with rule `(Custom) Application` + name ENDS_WITH "Home".

Not yet live-verified: a *dashboard import* pinned to a custom group by
name (the dashboard was not imported, per brief). Vendor export evidence
above is the same shape the factory renders. The importer binds
`entries.resource[].name` by display name
(`dashboard_view_pin_resolution.md`), so the group must exist with that
exact name **before** the dashboard imports, or the dashboard sits
stuck-deferred.

## 4. What the factory can express today

**Dashboard: yes, no change needed.**

```yaml
- id: app_allocation
  type: View
  self_provider: true
  pin:
    adapter_kind: Container
    resource_kind: Environment          # the helper group's type
    name: "[VCF Content Factory] All Applications"
  view: "[VCF Content Factory] Application Allocation Summary"
```

Rendered in scratch (`load_dashboard` + `render_dashboards_bundle_json`):
`entries.resource[0]` = `{resourceKindKey: Environment, adapterKindKey:
Container, name: "[VCF Content Factory] All Applications", internalId:
resource:id:0_::_}` and `config.resource.resourceKindId:
"002009ContainerEnvironment"`, `traversalSpecId: ""`, `selfProvider: true`.
Matches the Dell vendor bytes field for field (vendor has
`refreshContent: true`; immaterial). `pin.name` is allowed because
Container/Environment is not in `_VIEW_PIN_CONTAINER`.

**Custom group: no, one loader change.**
`src/vcfcf_core/customgroups/loader.py` `_validate_rule` (~171) rejects a
rule with no stat/property/name/relationship/tag condition. Both emitters
already produce the proven wire for an empty rule (`to_wire` gives the exact
POST body above; `to_ui_wire` gives `"rules": []`, the Dell export shape).
Tooling brief: allow a condition-less rule ("all objects of this kind").
Prefer an explicit opt-in key (e.g. `all_of_kind: true`, mutually exclusive
with conditions) over silently accepting an empty rule, so a forgotten
condition still fails validation.

**Loader guard (separate, small):** `Dashboard.validate` rejects
`self_provider` without `pin` on AlertVolume and ProblemAlertsList but not on
View; `_view_widget` (`render.py` ~1366) then silently renders
`selfProvider:false`. Add the same check for View. Only
`content/dashboards/application_allocation_summary.yaml` trips it in the repo
today (scanned `content/` and `third_party/`).

## Alternatives considered

- ResourceList (Object List) widget, `mode: all` with a kind tag filter, does
  list every object of a kind with no source, but has no super-metric columns
  in the view sense and no summary row. Not a fit for this request.
- Re-parenting Portfolio groups under one top group works but changes the
  user's data model; the helper group is additive and self-maintaining.
