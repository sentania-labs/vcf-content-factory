# Custom Group Import Format Reference

## Two distinct wire formats

VCF Ops custom groups have two incompatible JSON wire formats:

### 1. REST API format — `/api/resources/groups` (POST / PUT)

Used by: `install.py` `_install_customgroups()`, `vcfops_customgroups` CLI sync,
`CustomGroupDef.to_wire()`.

```json
{
  "resourceKey": {
    "name": "<group name>",
    "adapterKindKey": "Container",
    "resourceKindKey": "<type_key>",
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
          "resourceKind": "<resource kind>",
          "adapterKind": "<adapter kind>"
        },
        "statConditionRules": [
          { "key": "cpu|usage_average", "doubleValue": 80.0, "compareOperator": "GT" }
        ],
        "propertyConditionRules": [
          { "key": "summary|type", "stringValue": "vsan", "compareOperator": "EQ" }
        ],
        "resourceNameConditionRules": [
          { "name": "test", "compareOperator": "NOT_CONTAINS" }
        ],
        "relationshipConditionRules": [
          { "relation": "DESCENDANT", "name": "X", "compareOperator": "EQ" }
        ],
        "resourceTagConditionRules": [
          { "category": "Environment", "stringValue": "production", "compareOperator": "EQ" }
        ]
      }
    ]
  }
}
```

Key characteristics:
- No top-level envelope; one object per group.
- Name is nested under `resourceKey.name`.
- Rules are under `membershipDefinition.rules[]` (not `ruleGroups`).
- Each rule has a `resourceKindKey` object with `resourceKind`/`adapterKind`.
- Operators use short names: `EQ`, `NOT_EQ`, `GT`, `GT_EQ`, `LT`, `LT_EQ`,
  `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`.

### 2. UI import format — drag-drop via "Environment > Custom Groups > Import"

Used by: distribution package `bundles/<slug>/customgroup.json`,
`CustomGroupDef.to_ui_wire()`.

```json
{
  "customGroups": [
    {
      "name": "<group name>",
      "description": "",
      "resourceKind": "<type_key>",
      "adapterKind": "Container",
      "autoResolveMembership": true,
      "started": true,
      "membershipDefinition": {
        "ruleGroups": [
          {
            "resourceKind": "<resource kind>",
            "adapterKind": "<adapter kind>",
            "rules": [
              {
                "ruleType": "ResourceNameRule",
                "ruleStringOperator": "CONTAINS",
                "ruleStringValue": "test"
              },
              {
                "ruleType": "StringMetricPropertyRule",
                "ruleMetricKey": "summary|type",
                "isProperty": true,
                "ruleStringOperator": "EQUALS",
                "ruleStringValue": "vsan"
              },
              {
                "ruleType": "NumericMetricPropertyRule",
                "ruleMetricKey": "cpu|usage_average",
                "isProperty": false,
                "ruleOperator": "GREATER_THAN",
                "ruleValue": 80.0
              },
              {
                "ruleType": "RelationshipRule",
                "ruleRelationshipType": "CHILD",
                "ruleStringOperator": "EQUALS",
                "ruleStringValue": "cluster01"
              }
            ]
          }
        ]
      }
    }
  ],
  "customGroupTypes": [
    {
      "resourceKind": "<type_key>",
      "localization": [
        { "resourceKindName": "<display name>", "locale": "en" }
      ]
    }
  ]
}
```

Key characteristics:
- Top-level envelope: `{"customGroups": [...], "customGroupTypes": [...]}`.
- Group fields are flat at top level (`name`, `resourceKind`, `adapterKind`,
  `description`, `started`, `autoResolveMembership`). No `resourceKey` wrapper.
- Rules are under `membershipDefinition.ruleGroups[]` (not `rules[]`).
- Each ruleGroup has flat `resourceKind`/`adapterKind` strings (not `resourceKindKey`).
- Rules are typed objects with a `ruleType` discriminator field.
- `customGroupTypes` array declares the group type with per-locale display names.

## Rule type mapping

| YAML source | UI `ruleType` | Key discriminator fields |
|---|---|---|
| `name:` conditions | `ResourceNameRule` | `ruleStringOperator`, `ruleStringValue` |
| `property:` with string value | `StringMetricPropertyRule` | `ruleMetricKey`, `isProperty: true`, `ruleStringOperator`, `ruleStringValue` |
| `property:` with numeric value | `NumericMetricPropertyRule` | `ruleMetricKey`, `isProperty: true`, `ruleOperator`, `ruleValue` |
| `stat:` conditions | `NumericMetricPropertyRule` | `ruleMetricKey`, `isProperty: false`, `ruleOperator`, `ruleValue` |
| `relationship:` conditions | `RelationshipRule` | `ruleRelationshipType`, `ruleStringOperator`, `ruleStringValue` |
| `tag:` conditions | **Unknown — no specimen found** | Approximated as `StringMetricPropertyRule`; needs verification |

## Operator mapping

The UI format uses two operator fields depending on the rule type:
- `ruleStringOperator` — for `ResourceNameRule`, `StringMetricPropertyRule`,
  `RelationshipRule`
- `ruleOperator` — for `NumericMetricPropertyRule`

### String operator mapping (REST → UI)

| REST `compareOperator` | UI `ruleStringOperator` |
|---|---|
| `EQ` | `EQUALS` |
| `NOT_EQ` | `NOT_EQUALS` |
| `CONTAINS` | `CONTAINS` |
| `NOT_CONTAINS` | `NOT_CONTAINS` |
| `STARTS_WITH` | `STARTS_WITH` |
| `ENDS_WITH` | `ENDS_WITH` |
| `REGEX` | `REGEX` |

`EQ`→`EQUALS` confirmed from specimen: `CustomGroup-2024-12-02 11-36-04 AM.json`
(RelationshipRule `ruleStringOperator: EQUALS`) and `App Infra Cluster Insights/CustomGroup.json`
(`ruleStringOperator: CONTAINS`).

### Numeric operator mapping (REST → UI)

| REST `compareOperator` | UI `ruleOperator` |
|---|---|
| `GT` | `GREATER_THAN` |
| `GT_EQ` | `GREATER_THAN_OR_EQUALS` |
| `LT` | `LESS_THAN` |
| `LT_EQ` | `LESS_THAN_OR_EQUALS` |
| `EQ` | `EQUALS` |
| `NOT_EQ` | `NOT_EQUALS` |

`GREATER_THAN` confirmed from specimen: `Aria-Appliances-Custom Group.json`
(`ruleOperator: GREATER_THAN`). Others are logically derived — not all confirmed
from specimens.

## Known gap: tag rules

The reference specimens contain no example of a tag-based rule in UI format.
`vcfops_customgroups/loader.py` approximates tag conditions as
`StringMetricPropertyRule` with a `_tag_gap` comment key. If a bundle's
`customgroup.json` drag-drop import fails for a group with `tag:` conditions,
this gap is the likely cause. Investigation via api-explorer needed.

## Distribution package layout

| File | Format | Used by |
|---|---|---|
| `bundles/<slug>/customgroup.json` | **UI format** | Drag-drop via VCF Ops UI |
| `bundles/<slug>/content/customgroup.json` | **REST format** | `install.py` via `/api/resources/groups` |

The install script reads `content/customgroup.json` (path declared in
`bundle.json` under `content.customgroups.file`). The drag-drop artifact at
the bundle root is community-native format for hand-import.

## Reference specimens

1. `references/AriaOperationsContent/App Infra Cluster Insights/CustomGroup.json`
   — `ResourceNameRule` with `CONTAINS` operator
2. `references/AriaOperationsContent/Hosts in A Group Dashboard/CustomGroup-2024-12-02 11-36-04 AM.json`
   — `RelationshipRule` with `EQUALS` operator, multi-locale `customGroupTypes`
3. `references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/Dashboards/Aria-Appliances-Observability/Aria-Appliances-Custom Group.json`
   — `StringMetricPropertyRule` (isProperty: true) + `NumericMetricPropertyRule`
     (isProperty: false), multiple `ruleGroups` (OR semantics)

## Internal API wire format (third format, 2026-04-13 investigation)

`GET /internal/resources/groups/{id}` (requires `X-Ops-API-use-unsupported: true`)
returns a **different wire format** from both the public REST API and the UI import
format. Key differences from the public format:

| Public REST field | Internal field |
|---|---|
| `id` | `identifier` |
| `autoResolveMembership` | absent |
| `custom-group-properties` | absent |
| `statConditionRules` | `attributeRules` (combined stats + properties) |
| `propertyConditionRules` | `attributeRules` (combined) |
| `resourceNameConditionRules` | `resourceNameRules` |
| `relationshipConditionRules` | `relationshipRules` |
| `resourceTagConditionRules` | absent |
| absent | `description` (top-level) |

Internal list endpoint uses `{"values": [...]}` wrapper (not `{"groups": [...]}`).

The internal POST endpoint (`POST /internal/resources/groups`) accepts public field
names in the request body but **silently drops `resourceNameConditionRules`** and
other `*ConditionRules` fields — it only correctly processes the internal field names
(`attributeRules`, `resourceNameRules`, `relationshipRules`). Verified 2026-04-13
on VCF Ops 9.0.2: POSTing with `resourceNameConditionRules` returns 201 but the
created group has `resourceNameRules: []`.

**This format is NOT relevant to import/export.** Neither the UI import dialog
nor the distribution packages use this format. It's documented here only to
prevent confusion — a round-trip through the internal API will produce different
field names than the public API.

## UI import endpoint architecture (2026-04-13 investigation)

The Struts endpoint `customGroup.action` exists on VCF Ops 9.0.2 but is a
**dead stub**:
- All `mainAction` values (`import`, `export`, `importCustomGroups`,
  `exportCustomGroups`, etc.) return HTTP 200 with an empty body.
- Multipart file uploads return HTTP 400 with an empty body.
- No Ext.Direct RPC controller for custom groups exists in the
  `/ui/vcops/services/api.js` descriptor (only 6 controllers:
  `viewFilterController`, `reportServiceController`,
  `reportScheduleController`, `reportController`,
  `uploadContentController`, `viewServiceController`).

**The SPA handles custom group import client-side.** The VCF Ops 9 UI reads the
uploaded JSON file in the browser, parses the UI envelope format, transforms each
`customGroup` entry to REST API format (mapping `ruleGroups` to `rules`,
`ruleType` discriminators to the appropriate `*ConditionRules` arrays, etc.), and
POSTs each group individually to `POST /api/resources/groups`.

**The error "Could not import custom groups: invalid input parameter was given"**
is a SPA client-side error, not a REST API error. It occurs when the file does
not match the expected UI envelope format — for example, when the file contains
a single REST API format object instead of the `{"customGroups": [...],
"customGroupTypes": [...]}` envelope. The SPA's parser expects the top-level
`customGroups` array and fails validation when it's absent.

### Implications for distribution packages

- The drag-drop `customgroup.json` at the bundle root **must** use the UI
  envelope format (produced by `CustomGroupDef.to_ui_wire()` /
  `_render_customgroup_ui_payload()`).
- The install script's `content/customgroup.json` uses REST format (produced
  by `CustomGroupDef.to_wire()` / `_render_customgroup_rest_payload()`).
- Shipping REST format at the bundle root will cause the UI import error
  the user reported.
