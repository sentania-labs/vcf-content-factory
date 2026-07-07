# Content-zip wire formats

Reverse-engineered from live exports. The content-import endpoint
is picky — these are the exact shapes that work.

## Super metrics zip

```
outer.zip
├── <19-digit>L.v1           # marker, contents = owner user UUID
├── configuration.json       # {"superMetrics": N, "type": "ALL"}
└── supermetrics.json        # dict keyed by UUID
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

`modificationTime` and `modifiedBy` are optional on import.

## Dashboards + views zip

```
outer.zip
├── <digits>L.v1                       # marker
├── configuration.json                 # merged manifest
├── views.zip                          # nested: content.xml with all ViewDefs
├── usermappings.json                  # owners referenced by dashboards
├── dashboards/<ownerUserId>           # nested zip per owner
└── dashboardsharings/<ownerUserId>    # JSON list ([] = private)
```

Dashboards are grouped by owner user. All of one user's dashboards
live in a single nested zip. A matching `usermappings.json` must
reference the same owner id.

### View definition XML

Key structure: `<Content><Views><ViewDef id=…>` with `Title`,
`Description`, `SubjectType` elements, `Usage` tags, and a
`Controls` block containing column definitions (`Item` elements
with `attributeKey`, `displayName`, etc.).

**Instanced metric keys**: Use the `:Aggregate of all instances|`
form for instanced metrics (virtualDisk, net, datastore, etc.).
The bare key registers in `/statkeys` but has no timeseries data.

### Dashboard JSON

- `entries.resourceKind[]` — maps synthetic ids to real
  `{resourceKindKey, adapterKindKey}` pairs.
- `entries.resource[]` — required for self-provider pinned widgets.
  Uses 0-indexed `internalId` in entries, but widget config
  references with **1-indexed** id.
- `dashboards[]` — per-dashboard metadata, widgets, interactions.
- `widgetInteractions` — list of
  `{widgetIdProvider, type: "resourceId", widgetIdReceiver}`.

## SM ghost state

**Symptom:** `PUT /internal/supermetrics/assign/default` returns
404 despite `GET /api/supermetrics/{id}` succeeding. SM does not
appear in list pages.

**Cause:** Content-zip importer has two tables (object store +
internal catalog). Partial prior import leaves SM in object store
but not catalog.

**Detection:** After import, check `operationSummaries`. If
`imported=0, skipped>0`, SMs are in ghost state.

**Fix:** Re-import the same ZIP. Second import fully re-registers.

## Policy export XML

```xml
<PolicyContent>
  <Policies>
    <Policy>
      <PackageSettings>
        <SuperMetrics adapterKind="VMWARE" resourceKind="ClusterComputeResource">
          <SuperMetric enabled="true" id="<uuid>"/>
        </SuperMetrics>
      </PackageSettings>
    </Policy>
  </Policies>
</PolicyContent>
```

Separate from content import/export. Used for bulk policy edits.

## Custom groups (dynamic)

NOT a content-zip format. Created via REST directly.

```json
{
  "resourceKey": {
    "name": "Group Name",
    "adapterKindKey": "Container",
    "resourceKindKey": "Environment",
    "resourceIdentifiers": []
  },
  "autoResolveMembership": true,
  "membershipDefinition": {
    "rules": [
      {
        "resourceKindKey": {
          "resourceKind": "VirtualMachine",
          "adapterKind": "VMWARE"
        },
        "statConditionRules": [],
        "propertyConditionRules": [],
        "resourceNameConditionRules": [],
        "relationshipConditionRules": [],
        "resourceTagConditionRules": []
      }
    ]
  }
}
```

Gotchas:
1. Top-level `adapterKindKey`/`resourceKindKey` = group's own type.
   Member selector kind = `rules[].resourceKindKey` (different
   field names, no `Key` suffix).
2. All five rule arrays required, even when empty.
3. `custom-group-properties` has a literal hyphen (not camelCase).
4. Multiple `rules[]` entries are OR'd. Conditions within one rule
   are AND'd.
5. `relationshipConditionRules[].travesalSpecId` is misspelled in
   the API (`travesal` not `traversal`). Use the misspelling.
6. Omit `id` on POST. Include on PUT.
7. DELETE returns 200; subsequent GET returns 500 (not 404). Normal.

## Custom group types

```
GET    /api/resources/groups/types      → {groupTypes:[{name,key}]}
POST   /api/resources/groups/types      → body {"name":"X"}, 201
DELETE /api/resources/groups/types/{key} → 200
```

Cross-ref: group's `resourceKey.resourceKindKey == <type.key>`.
