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
