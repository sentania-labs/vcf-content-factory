# Content zip wire formats

Reverse-engineered from live exports. The content-import endpoint
(`POST /api/content/operations/import`) is picky — earlier iterations
sending nested-per-item layouts got `INVALID_FILE_FORMAT` on every
attempt. These are the exact shapes that work.

## Common import gotchas

1. **The marker filename is a per-instance fingerprint.** Every
   export from one Ops cluster uses the same `<19-digit>L.v1`
   filename. The importer rejects any other value — even an off-by-one
   is `INVALID_FILE_FORMAT`. Discover it via throwaway export:
   `vcfops_dashboards.client.discover_marker_filename`.
2. **The marker file contents are the owner user UUID**, not
   arbitrary. Same across all exports from the same instance.
3. **The multipart field is `contentFile`** on
   `POST /api/content/operations/import`. `file` or raw
   `application/zip` request bodies return 500.
4. **Import returns 202 + operation id**. Poll
   `GET /api/content/operations/import` until `state == FINISHED`.
   Check `errorCode` and `errorMessages`.

## Super metrics zip

```
outer.zip
├── <19-digit>L.v1           # marker, contents = owner user UUID
├── configuration.json       # {"superMetrics": N, "type": "ALL"}
└── supermetrics.json        # dict keyed by UUID, entries as below
```

Each entry in `supermetrics.json`:

```json
{
  "<uuid>": {
    "name": "...",
    "formula": "...",
    "description": "...",
    "unitId": "",
    "resourceKinds": [
      {"resourceKindKey": "ClusterComputeResource", "adapterKindKey": "VMWARE"}
    ]
  }
}
```

`modificationTime` and `modifiedBy` are present in exports but
**optional on import** — confirmed empirically. The importer
populates whatever it needs server-side.

## Dashboards + views zip (existing `vcfops_dashboards` layout)

```
outer.zip
├── <digits>L.v1                       # marker (same as above)
├── configuration.json                 # merged manifest for all content types
├── views.zip                          # nested: one content.xml with all ViewDefs
├── usermappings.json                  # owners referenced by dashboards/<id>
├── dashboards/<ownerUserId>           # nested: dashboard/dashboard.json holding
│                                      #   ALL owner's dashboards + i18n bundles
└── dashboardsharings/<ownerUserId>    # JSON list ([] = private to owner)
```

Dashboards are **grouped by owner user**, not per-dashboard. All of
one user's dashboards live in a single nested zip named
`dashboards/<ownerUserId>` whose inner `dashboard/dashboard.json` has
a shared `entries.resourceKind[]` table and a `dashboards[]` array
with every dashboard object. A matching `usermappings.json` at top
level must reference the same owner id.

### View definition XML

**Instanced metric keys.** `attributeKey` takes the literal `statKey.key`
string Ops uses internally. For metric families that the adapter
instances at runtime (most notably `virtualDisk|*` IOPS / latency /
read-write counts on VirtualMachine, and `datastore|*`, `net:*`,
`guestfilesystem|*`), the bare key (e.g. `virtualDisk|totalReadLatency_average`)
is **registered in `/api/adapterkinds/.../statkeys` but has no
timeseries data** — data lives only under
`virtualDisk:scsi0:N|<metric>` per disk and a synthetic
`virtualDisk:Aggregate of all instances|<metric>` rollup. A list view
that uses the bare key installs cleanly and renders blank columns
forever. Use the `:Aggregate of all instances|` form unless you
intentionally want a single-disk pin. Full procedure for telling
which families are instanced on a given instance:
`context/recon_metric_keys.md`. The `statkeys` endpoint cannot tell
you this — only `GET /api/resources/{id}/stats` on a representative
resource can.

Rooted at `<Content><Views><ViewDef id=…>` with: `Title`,
`Description`, two `SubjectType` elements (`type=self` and
`type=descendant`), `Usage` tags (`dashboard report details
content`), and a `Controls` block containing
`time-interval-selector`, `attributes-selector` (one `Item` per
column with `attributeKey`, `displayName`, optional `preferredUnitId`,
etc.), `pagination-control`, and `metadata`.
`DataProviders/DataProvider dataType="list-view"` and
`Presentation type="list"` close it out.

### Dashboard JSON

- `uuid` — package wrapper id.
- `entries.resourceKind[]` — list mapping synthetic ids
  (`resourceKind:id:N_::_`) to real `{resourceKindKey, adapterKindKey}`
  pairs. Widget configs reference resource kinds by these synthetic
  ids, *not* by the real keys.
- `dashboards[]` — per-dashboard metadata: `name`, `id`, `description`,
  `columnCount`, `gridsterMaxColumns`, `widgets`, `widgetInteractions`.
- Each widget has `id` (UUID), `type`, `title`, `gridsterCoords`
  (`{x,y,w,h}` on a 12-column grid), and a type-specific `config`.
- `widgetInteractions` is a list of
  `{widgetIdProvider, type: "resourceId", widgetIdReceiver}`.

A `View` widget references its view by `config.viewDefinitionId`,
which must match the view's UUID. In this repo, the dashboard YAML's
`view:` field names a view by name; the loader resolves it to the
view YAML's `id` at build time.

#### getDashboardConfig vs. content-zip export (extractor note)

`/ui/dashboard.action?mainAction=getDashboardConfig` returns an entirely
different format than the content-zip export: the response is
`{"interactionTypes": {...}, "dashboardConfig": {"tabConfigs": [...], "widgetInteractions": {...}}}`.
`tabConfigs[]` contains ALL dashboards on the instance (one entry per
dashboard, keyed by dashboard UUID in `tabConfigs[N].id`). Each entry has
`name`, `id`, `widgets[]` — but the `widgets[]` here are **shells only**:
they have `key` (not `type`), `gridsterX/Y/W/H` (flat, not nested
`gridsterCoords`), and **no `config` block**. Widget config
(viewDefinitionId, metric specs, etc.) is NOT available from this endpoint.

**The content-zip export is the only reliable source of full widget config
for extraction.** `vcfops_extractor` uses `POST /api/content/operations/export`
with `contentTypes: ["DASHBOARDS"]` to get the same `dashboard/dashboard.json`
format the importer and `parse_dashboard_json()` were built for.

#### Dashboard import lock and ownership behavior

The content-zip importer **always sets `locked: true` on imported
dashboards**, regardless of the `locked` field value in the
dashboard.json payload. This is server-side behavior — the importer
ignores the `locked: false` we send.

**Ownership** is governed by `usermappings.json`, not by `userId`
inside the dashboard object. The importer maps the `userId` in each
dashboard entry to a local account via `usermappings.json`'s
`users[].userName`. If `userName` is `"admin"`, the dashboard is
owned by admin regardless of whose API token performed the import.
To have dashboards owned by the importing user, `userName` must match
that user's account name.

**Consequences for delete:** The `deleteTab` Struts action silently
refuses to delete dashboards that are `locked: true` (HTTP 200, no
error, dashboard not deleted). There is no `unlockTab` or equivalent
mainAction in the Struts layer, no `/api/dashboards/{id}` REST
endpoint, and no lock/unlock endpoint in either the public or
internal OpenAPI specs.

**No unlock path exists (verified 2026-04-10).** `saveDashboardConfig`
with `isLocked: false` returns an HTML error page; `saveTab` accepts
but doesn't change lock state. There is no `unlockTab` or equivalent
mainAction. Re-importing with modified `usermappings.json` does not
reassign ownership. See `context/dashboard_delete_api.md` for full
empirical findings.

**Root cause in the packager:** `usermappings.json` hardcodes
`"userName": "admin"` (packager.py line 136). This causes all
imported dashboards to be owned by admin even when the import is
performed by a different user. Fix: pass the actual importing
user's `userName` (available from `GET /api/auth/currentuser`) into
`build_import_zip` and use it in `usermappings.json`.

**`entries.resource` is required for self-provider pinned widgets.**
When a View widget has `self_provider: true` with a `pin`, the
bundle's `entries` must include a `resource` array alongside
`resourceKind`. Each entry carries `resourceKindKey`,
`adapterKindKey`, `name` (same as `resourceKindKey`),
`identifiers` (empty `[]`), and a 0-indexed
`internalId` (`resource:id:0_::_`, `resource:id:1_::_`, ...).
The widget's `config.resource.resourceId` references these with a
**1-indexed** id (`resource:id:1_::_` for the first entry). Without
`entries.resource`, the widget imports cleanly but renders
"Please wait being configured" and throws an internal server error
on edit.

## Super metric enable endpoint

**Use `PUT /internal/supermetrics/assign/default`, NOT
`PUT /internal/supermetrics/assign?policyIds=<id>`.**

The spec lists two internal endpoints for enabling super metrics on
the Default Policy:

- `/internal/supermetrics/assign?policyIds=<id>` — general assign;
  accepts any policy UUID via query param. In practice the server
  returns HTTP 200 even when the policy resolution silently fails,
  so callers that look up the default policy ID and pass it here may
  see "OK" responses with no actual enablement.
- `/internal/supermetrics/assign/default` — targets the Default
  Policy directly, no `policyIds` lookup needed. This is the
  reliable path.

Both endpoints require `X-Ops-API-use-unsupported: true` header.
Request body (JSON):
```json
{
  "superMetricId": "<uuid>",
  "resourceKindKeys": [
    { "adapterKind": "VMWARE", "resourceKind": "VirtualMachine" }
  ]
}
```
Note: the body uses `adapterKind` / `resourceKind` (not the
`adapterKindKey` / `resourceKindKey` keys that the loader's
`resource_kinds` list stores). Both `vcfops_supermetrics/client.py`
and `vcfops_packaging/templates/install.py` translate the loader
keys to the API keys in the dict comprehension that builds the body.

### SM ghost state — assign returns 404 despite GET /{id} succeeding

**Symptom:** `PUT /internal/supermetrics/assign/default` returns
`404 "No such superMetricId"` for an SM whose UUID is returned by
`GET /api/supermetrics/{id}`. The SM also does NOT appear in
`GET /api/supermetrics` list pages. No data points are computed.

**Root cause:** The content-zip importer maintains two separate tables:
the SM object store (queryable by GET-by-id) and an internal SM catalog
used by the assign endpoint and the list API. When an SM was previously
imported but its registration in the internal catalog failed (e.g. a
prior partial import), the importer treats it as "already exists" and
returns `skipped=1` without updating the catalog. The SM sits in ghost
state: readable by ID, invisible to the list and to assign.

**Detection:** After `POST /api/content/operations/import`, poll the
status and check `operationSummaries[contentType=SUPER_METRICS]`. If
`imported == 0` and `skipped > 0`, the SMs are in ghost state.

**Fix:** Re-import the same ZIP a second time. The second import finds
the SM in ghost state, fully re-registers it, and reports `imported=N`.
After re-import the SM appears in the list and assign/default returns
200. Both `vcfops_supermetrics/client.py:import_supermetrics_bundle`
and `vcfops_packaging/templates/install.py:_install_supermetrics` detect
the all-skipped signal and retry automatically.

**Note:** `GET /api/supermetrics` returning a result does NOT guarantee
the SM is registered in the internal catalog. Always validate
post-import by checking the `operationSummaries` imported count.

## Policy export XML

Different zip, same instance. `GET /api/policies/export?id=<uuid>`
returns a zip containing `exportedPolicies.xml`. Relevant structure
for super metric enablement inside a policy:

```xml
<PolicyContent>
  <Policies>
    <Policy>
      <PackageSettings>
        <SuperMetrics adapterKind="VMWARE" resourceKind="ClusterComputeResource">
          <SuperMetric enabled="true" id="<uuid>"/>
        </SuperMetrics>
        <!-- one block per (adapterKind, resourceKind) pair -->
      </PackageSettings>
    </Policy>
  </Policies>
  <superMetrics>
    <!-- full super metric definitions bundled alongside -->
  </superMetrics>
</PolicyContent>
```

This is the policy import/export channel, not the content
import/export channel. Useful if you ever need to bulk-edit policy
enablements on the public API.

## Custom groups (dynamic)

**Not a content-zip format.** Unlike super metrics / dashboards /
views / policies, custom groups do **not** ride the
`/api/content/operations/import` path. There is no
`customgroups.json` or equivalent in any content zip exported by
Ops, and no `/internal/*/import` endpoint for them. They are
created directly via REST:

- `POST /suite-api/api/resources/groups` — create, returns `201`
  with the echoed object including a server-assigned `id` (UUID)
  and `links[]`.
- `PUT  /suite-api/api/resources/groups` — update (body includes `id`).
- `GET  /suite-api/api/resources/groups?pageSize=N` — list under
  `{"groups":[...], "pageInfo":{...}}`.
- `GET  /suite-api/api/resources/groups/{id}` — fetch one.
- `DELETE /suite-api/api/resources/groups/{id}` — remove.
- `GET  /suite-api/api/resources/groups/{id}/members` — list
  resolved member resources.

Implications for this repo: a `customgroups/` YAML tree cannot be
synced via the existing content-zip importer; it needs a dedicated
loader/client that POSTs/PUTs JSON directly (same style as the
old super-metric direct-POST path, but — because group
identity is server-assigned on create — cross-instance portability
requires matching by `resourceKey.name` on sync, not by UUID).

### JSON shape (dynamic group)

Exact shape returned by `GET /api/resources/groups` and accepted by
`POST`, verified by round-trip on the lab (create → GET → delete,
`2026-04-08`). Full specimens in
`context/specimens/customgroups/`.

```json
{
  "id": "<server-assigned UUID, omit on create>",
  "resourceKey": {
    "name": "My Group Name",
    "adapterKindKey": "Container",
    "resourceKindKey": "Environment",
    "resourceIdentifiers": []
  },
  "autoResolveMembership": true,
  "membershipDefinition": {
    "includedResources": [],
    "excludedResources": [],
    "custom-group-properties": [],
    "rules": [
      {
        "resourceKindKey": {
          "resourceKind": "VirtualMachine",
          "adapterKind": "VMWARE"
        },
        "statConditionRules":        [ { "key": "cpu|usage_average", "doubleValue": 80.0, "compareOperator": "GT" } ],
        "propertyConditionRules":    [ { "key": "config|hardware|numCpu", "doubleValue": 4.0, "compareOperator": "LT" } ],
        "resourceNameConditionRules":[ { "name": "VSAN", "compareOperator": "NOT_CONTAINS" } ],
        "relationshipConditionRules":[ { "relation": "CHILD", "name": "SampleStorage", "compareOperator": "CONTAINS", "travesalSpecId": "vSphere Storage-VMWARE-vSphere World" } ],
        "resourceTagConditionRules": [ { "category": "VMFolder", "compareOperator": "NOT_CONTAINS", "stringValue": "TestVMFolder" } ]
      }
    ]
  }
}
```

Gotchas:

1. **`adapterKindKey`/`resourceKindKey` at the top level are the
   group object's *own* type**, almost always
   `Container`/`Environment`. The **member selector** kind lives
   under `membershipDefinition.rules[].resourceKindKey`
   (`{resourceKind, adapterKind}`, note flipped field names — no
   `Key` suffix here). Easy to swap by accident.
2. **All five rule arrays are required**, even when empty. Missing
   arrays are tolerated on create but come back empty on GET;
   including them explicitly keeps diffs clean.
3. **`custom-group-properties` has a literal hyphen** in the JSON
   key — not camelCase like everything else.
4. **Multiple entries in `rules[]` are OR'd** (union). Multiple
   condition rules *inside* one rule group are AND'd. Specimen
   `03_VCF_Operations_Self_Monitoring.json` has 13 rule groups,
   one per adapter resource kind — classic OR-of-ANDs pattern.
5. **`compareOperator` values observed:** `EQ`, `NOT_EQ`, `GT`,
   `GTE`, `LT`, `LTE`, `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`,
   `ENDS_WITH`, `REGEX`. Per spec example.
6. **`relationshipConditionRules[].travesalSpecId`** is misspelled
   in the API (missing `r` — `travesal` not `traversal`). Use the
   misspelling; Ops expects it.
7. **`relation` values:** `PARENT`, `CHILD`, `ANCESTOR`,
   `DESCENDANT`.
8. **`autoResolveMembership: true`** means Ops periodically
   re-evaluates rules against the inventory. `false` freezes the
   initial membership — almost never what you want for a dynamic
   group.
9. **Static-only groups** (no `rules`, only `includedResources`)
   can also be created here, or via
   `POST /internal/resources/groups/static`. This repo scope is
   dynamic-only.
10. **`id` must be omitted on create** (POST). On update (PUT) it
    must be present and match an existing group.
11. **On DELETE, a subsequent GET returns 500**, not 404. Normal
    Ops behavior; the delete itself returns 200 and is
    authoritative.

## Pak bundled content layout (first-party + SDK)

VCF Ops auto-imports content from the `content/` directory inside a
`.pak` file during the CASA APPLY_ADAPTER phase. No post-install
scripts needed. Confirmed against VMware first-party paks (NSX-T,
vSphere, vSAN) and vCommunity Integration SDK pak on the devel
appliance.

### Canonical directory structure

```
<pak>.pak
└── content/
    ├── dashboards/<slug>/dashboard.json   # subdirectory per dashboard
    ├── reports/<slug>/content.xml         # views as <Content><Views> XML
    ├── alertdefs/alert-content.xml        # combined <alertContent> XML
    ├── supermetrics/<slug>.json
    ├── customgroups/<slug>.json
    ├── traversalspecs/<slug>.xml
    ├── scorecards/scorecard-def.json
    ├── files/reskndmetric/                # metric selection configs
    ├── resources/resources.properties     # localization
    └── policies/                          # policy configs
```

### Critical rules

1. **Dashboards use subdirectories.** Each dashboard gets its own
   directory under `content/dashboards/` with the JSON file inside.
   Flat files at `content/dashboards/<slug>.json` are NOT processed.
   NSX-T uses `dashboard.json`; vSphere uses `<slug>.json`. Both work.

2. **Views go in `content/reports/`, NOT `content/views/`.** Each
   view group gets a subdirectory containing `content.xml`. Format:
   `<Content><Views><ViewDef id="...">...</ViewDef></Views></Content>`.

3. **Alerts/symptoms/recommendations**: first-party paks put all
   three in a single `content/alertdefs/<name>.xml` with root element
   `<alertContent>` containing `<AlertDefinitions>`,
   `<SymptomDefinitions>`, and `<Recommendations>`. Alternatively,
   these can go in describe.xml (confirmed working build 15).

4. **Include all standard empty directories** so the platform
   recognizes the content/ tree.

### Failed approaches

- `content/views/views.zip` — platform ignored it (build 14)
- Flat `content/dashboards/<slug>.json` — platform ignored it (build 15)
- Flat `content/reports/<slug>.xml` — not confirmed; switched to
  subdirectory pattern before testing

`sdk_builder.py::_write_outer_pak` implements this layout. The
`views_zip_bytes` passed to it is NOT written to the outer pak —
it lives only inside `adapters.zip/<adapter>/conf/views/views.zip`
as a belt-and-suspenders copy for post-install scripts.

## Custom group types

Two-field flat taxonomy that classifies custom group instances.
JSON object: `{name, key}`. See
`context/customgroup_authoring.md` §"Group types" for full detail
including the cross-reference path from instances.

| Verb | Path | Notes |
|---|---|---|
| GET | `/api/resources/groups/types` | List, returns `{groupTypes:[{name,key}]}`. Public. |
| POST | `/api/resources/groups/types` | Create. Body `{"name":"X"}`. Server sets `key=name`. 201, empty body. Public. |
| DELETE | `/api/resources/groups/types/{key}` | Delete by key. 200, empty body. Public. |

No GET-by-key, no PUT/PATCH, no `/internal/*` equivalent.
Cross-reference from a group instance:
`resourceKey.resourceKindKey == <type.key>`,
`resourceKey.adapterKindKey == "Container"`.

## Pre-install dashboard JSON quirks (local reverse-port)

The original `VCFOperationsvCommunity` MP source files (under
`references/vmbro_vcf_operations_vcommunity/`) are **pre-install** — they
have not been processed by the VCF Ops content-import pipeline.  Several
fields that the pipeline normalises are present in their raw form and differ
from live content-zip exports:

### Boolean-as-string in metric bounds

Scoreboard and MetricChart widget configs carry metric bound fields
(`yellowBound`, `orangeBound`, `redBound`) that the importer expects to be
numeric or absent.  In pre-install source files some entries carry
`"redBound": "false"` — a JSON `false` value that was serialised to a string
literal during the MP's authoring toolchain.

**This is NOT a valid threshold.** The value means "no red threshold",
equivalent to `null`.

`reverse.py`'s `_parse_metric_specs_from_wire()` now handles this
gracefully: any non-numeric non-null bound value is treated as `None`
(absent) rather than raising `ValueError`.  Confirmed instances:
- `Cluster Performance 2.0.json` → Scoreboard widgets for
  `configuration|dasConfig|enabled` and `configuration|drsconfig|enabled`
  carry `"redBound": "false"` with valid `yellowBound`/`orangeBound` of `"1"`.

### Views spread across multiple XML files

The reference tree contains several overlapping XML files:
- `View - Collection01.xml` — master list (179 ViewDefs total, first seen)
- `View - Set 1.xml`, `View - Set 2.xml`, `View - Set 3.xml`,
  `View - Set 4.xml` — subsets that repeat views from Collection01

The `reverse-local` command merges all files; duplicate UUIDs are silently
overwritten (last file wins alphabetically).  This is expected MP packaging
behaviour, not a data error.

### Missing view XMLs

Three views referenced in `Cluster Performance 2.0.json` and six views in
`Input dashboards.json` are not present in the reference tree (no matching
`<ViewDef>` element).  These are:
- `d8a3767e` (vSphere Clusters list)
- `12fd58e7` (Resource Pools by CPU Shares)
- `421ac1e1` (Resource Pools by Memory Shares)
- + 6 storage/compute capacity views in Input dashboards

The `reverse-local` command emits WARN per missing UUID and continues; View
widgets for these UUIDs use the UUID string as the `view:` value (a
placeholder requiring manual authoring).  Round-trip diff for affected
dashboards reports PARTIAL with a clear explanation.

---

## PropertyList widget (dashboard JSON)

Source: `references/vmbro_vcf_operations_vcommunity/Management Pack/content/dashboards/ESXi Host Details Dashboard.json`, `VM Details.json`.

```json
{
  "type": "PropertyList",
  "config": {
    "visualTheme": 0,
    "depth": 1,
    "refreshInterval": 300,
    "metric": { /* standard resourceKindMetrics[] envelope */ },
    "resource": [],
    "refreshContent": {"refreshContent": true},
    "relationshipMode": {"relationshipMode": 0},
    "selfProvider": {"selfProvider": false},
    "showMetricFullName": {"metricFullName": true},
    "resInteractionMode": null,
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "title": "..."
  }
}
```

**Quirks:**
- `metric` uses the same `resourceKindMetrics[]` envelope as Scoreboard/MetricChart.
  `isStringMetric: true` is set on property-type metric entries (e.g. `runtime|powerState`).
- `relationshipMode` is a **wrapped object** `{"relationshipMode": 0}`, NOT a bare integer 0.
  The forward renderer previously emitted the bare integer — fixed in 2026-06.
- `showMetricFullName` inner key is `metricFullName` (not `showMetricFullName`).
- `selfProvider` is always `false` in all observed instances; no self-provider mode seen.

---

## ResourceRelationshipAdvanced widget (dashboard JSON)

Source: `references/vmbro_vcf_operations_vcommunity/Management Pack/content/dashboards/vSphere Resource Management.json`, `VM Performance 2.0.json`.

```json
{
  "type": "ResourceRelationshipAdvanced",
  "config": {
    "resourceId": null,
    "refreshInterval": 300,
    "traversalSpecId": "",
    "refreshContent": {"refreshContent": false},
    "resourceName": null,
    "title": "...",
    "filterMode": "tagPicker",
    "tagFilter": {
      "path": ["/source/kind/kind:resourceKind:id:0_::_", "..."],
      "value": {
        "kind": ["resourceKind:id:0_::_", "..."],
        "bus": [], "adapterKind": [], "exclaim": false,
        "healthRange": [], "maintenanceSchedule": [], "adapterInstance": [],
        "collector": [], "tier": [], "state": [], "tag": [], "day": [], "status": []
      }
    },
    "paginationNumber": 5,
    "depth": "0,2",
    "customFilter": {"filter": [], "excludedResources": null, "includedResources": null},
    "selectFirstRow": {"selectFirstRow": true},
    "selfProvider": {"selfProvider": false}
  },
  "states": [ /* UI persistence artefact; ignored on import */ ]
}
```

**Quirks:**
- `depth` is a **string** in the wire format (e.g. `"0,2"` or `"2,1"`), not an integer.
  This is unique among all widget types.  The YAML dataclass stores it as a string.
- `tagFilter` shape is identical to ResourceList — `tagFilter.value.kind[]` holds
  `resourceKind:id:N_::_` synthetic refs from `entries.resourceKind[]`.
- `states[]` appears at the top-level widget object (not in `config`); it is a UI
  persistence cookie set by the Ops client and is ignored on import.  The factory
  forward renderer omits it (consistent with all other widget types).
- Interaction-driven only in all observed instances (`selfProvider.selfProvider: false`).
  A self-provider mode may be possible but was not observed.
