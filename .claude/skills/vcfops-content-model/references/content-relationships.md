# Content cross-references and relationships

## Cross-reference syntax by content type

### Super metric → super metric

In YAML formula: `@supermetric:"<exact name>"`
Loader rewrites to: `sm_<uuid>`
Resolved at: `validate` (SM loader reads referenced SM YAML)

Example:
```yaml
formula: |
  ${this, metric=Super Metric|@supermetric:"[VCF Content Factory] VKS VMOperator vCPU"}
  -
  ${this, metric=Super Metric|@supermetric:"[VCF Content Factory] VKS Node Image vCPU"}
```

All referenced SMs must be assigned to the same resource kinds
and enabled in the same policy.

### View column → super metric

In YAML: `attribute: supermetric:"<exact name>"`
Loader rewrites to: `sm_<uuid>` in `attributeKey`
Resolved at: `validate` (dashboard loader reads SM YAML)

### Dashboard widget → view

In YAML: `view: "<exact view name>"`
Loader rewrites to: view UUID in `config.viewDefinitionId`
Resolved at: `validate` (dashboard loader reads view YAML)

### Alert → symptom

In YAML: `name: "<exact symptom name>"` in symptom set
Resolved at: `sync` (installer queries
`GET /api/symptomdefinitions` on the live instance)

This means symptoms must be synced BEFORE alerts.

### Report → view / dashboard

In YAML: `view: "<exact view name>"` or
`dashboard: "<exact dashboard name>"` in section config
Resolved at: `validate` (report loader reads view/dashboard YAML)

## Resolution rules

- Names must match exactly (case-sensitive, prefix included).
- SM/view/dashboard/report references resolve from local YAML at
  validate time — the referenced object must exist in the repo.
- Alert → symptom references resolve from the live instance at
  sync time — symptoms must be synced first.
- Validation fails loudly if a reference cannot be resolved.

## Dependency ordering

### Authoring order (bottom-up)

For compound requests, author in this order:
1. Super metrics (no dependencies)
2. Custom groups (may depend on SM for stat conditions, but rare)
3. Views (depend on SMs for column references)
4. Dashboards (depend on views for widget references)
5. Symptoms (no dependencies within this repo)
6. Alerts (depend on symptoms by name)
7. Reports (depend on views and dashboards)

### Install order

1. Sync super metrics
2. Enable super metrics (Default Policy)
3. Sync custom groups
4. Sync symptoms
5. Sync alerts
6. Sync dashboards + views
7. Sync reports

### Bundle completeness

When packaging a distributable bundle, every cross-referenced
object must be included. Specifically:
- If a view references SM UUIDs, those SMs must be in the bundle.
- If a dashboard references views, those views must be in the bundle.
- If an alert references symptoms, those symptoms must be in the
  bundle.
- If a report references views or dashboards, those must be in the
  bundle.

## Custom group rule grammar

Rules within a custom group:
- Multiple `rules[]` entries are **OR'd** (union of members).
- Within one rule, all condition lists (stat, property, name,
  relationship, tag) are **AND'd**.
- Each rule selects a single `(resourceKind, adapterKind)` pair.

Condition types:

| Type | Required fields |
|---|---|
| stat | `key`, `op`, `value` (numeric) |
| property | `key`, `op`, `value` (string or number) |
| name | `op`, `value` |
| relationship | `relation`, `name`, `op`, optional `traversal_spec_id` |
| tag | `category`, `op`, `value` |

Compare operators: `EQ`, `NOT_EQ`, `GT`, `GT_EQ`, `LT`, `LT_EQ`,
`CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`.

Relationship `relation` values: `PARENT`, `CHILD`, `ANCESTOR`,
`DESCENDANT`.
