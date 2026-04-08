# Custom group authoring (dynamic)

Scope: dynamic custom groups — membership resolved from rules. For
wire format / gotchas see `context/wire_formats.md` §"Custom
groups (dynamic)". For API endpoints see
`context/content_api_surface.md`.

## Decision checklist (what the author agent must ground)

Before writing YAML, pin down:

1. **Group name** — user-visible. Becomes `resourceKey.name`.
   Must be unique in the instance. This is the cross-instance
   identity (custom group UUIDs are server-assigned on create, so
   sync matches by name, not UUID — different rule from super
   metrics).
2. **Member resource kind(s)** — one `rules[]` entry per distinct
   `(adapterKind, resourceKind)` selector. VirtualMachine/VMWARE,
   Datastore/VMWARE, HostSystem/VMWARE, etc. Must come from a
   real adapter, never invented. Grep existing specimens or
   `docs/vcf9/metrics-properties.md` if unsure.
3. **Rule semantics** — within one rule group, all condition
   rules are AND'd. Across rule groups in `rules[]`, results are
   OR'd (union). If the user says "VMs that match A AND B", one
   rule group. If "VMs that match A, plus hosts that match B",
   two rule groups.
4. **Condition data** — for every condition rule:
   - `statConditionRules`: metric key + numeric threshold +
     operator. Metric key must be valid for the rule's
     `resourceKind`.
   - `propertyConditionRules`: property key + value (double or
     string) + operator. Same grounding requirement.
   - `resourceNameConditionRules`: literal name fragment +
     operator (`CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`,
     `ENDS_WITH`, `REGEX`, `EQ`, `NOT_EQ`).
   - `relationshipConditionRules`: relation (`PARENT`, `CHILD`,
     `ANCESTOR`, `DESCENDANT`) + related resource name +
     operator. Optional `travesalSpecId` (sic — misspelled in
     the API) narrows the traversal.
   - `resourceTagConditionRules`: vSphere tag `category` +
     `stringValue` + operator.
5. **`autoResolveMembership`** — default `true`. Only set `false`
   if the user explicitly wants a snapshot group.

If any of the above is missing and can't be recovered from recon
or the docs, the author agent MUST return a clarification request
rather than guess — especially for metric/property keys.

## Required recon before authoring

`ops-recon` should answer:

1. Does a custom group with this name already exist on the
   instance? (`GET /api/resources/groups`, match on
   `resourceKey.name`.) If yes, stop and show the user.
2. Is there a near-duplicate that could be edited instead?
3. Are all referenced metric/property keys live on the target
   resource kind? (Sample one resource of that kind and verify.)
4. For relationship rules: does the referenced related resource
   name actually exist and sit at the claimed distance?

## YAML shape (proposed — no loader yet)

There is no `vcfops_customgroups` package today. When one lands
it should follow the same pattern as `vcfops_supermetrics`:

```yaml
name: "[Custom] Noisy production VMs"
autoResolveMembership: true
rules:
  - resourceKind: VirtualMachine
    adapterKind: VMWARE
    stat:
      - { key: "cpu|usage_average", op: GT, value: 80 }
    property:
      - { key: "summary|runtime|powerState", op: EQ, value: "poweredOn" }
    name:
      - { op: NOT_CONTAINS, value: "test" }
    relationship: []
    tag:
      - { category: "Environment", op: EQ, value: "production" }
```

Loader responsibilities:

- Expand the terse YAML into the verbose JSON body documented in
  `wire_formats.md` (top-level `resourceKey` with
  `Container`/`Environment`, empty `includedResources` /
  `excludedResources` / `custom-group-properties`, the five
  rule arrays always present even when empty).
- Match existing groups by `resourceKey.name` for sync (no local
  UUID file; server owns the id).
- Validate metric/property keys are non-empty strings; refuse
  invented compare operators; warn if `autoResolveMembership:
  false`.

## Specimens to learn from

Under `context/specimens/customgroups/`:

- `01_[Custom]_VMs_on_only_Standard_PGs.json` — relationship-only,
  double-condition (`DESCENDANT EQ X` AND `DESCENDANT NOT_EQ Y`)
  inside one rule group. Pattern: set subtraction.
- `02_vSAN_Datastores.json` — property-based selector.
- `03_VCF_Operations_Self_Monitoring.json` — 13 rule groups
  OR'd, one per self-monitoring adapter resource kind. Pattern:
  multi-kind umbrella group.

## Anti-patterns

- Inventing `resourceKind` / `adapterKind` pairs. Only real ones.
- Using the top-level `adapterKindKey`/`resourceKindKey` for the
  member selector. Those describe the group object itself:
  `adapterKindKey` is always `Container`; `resourceKindKey` is
  the group **type key** (default `Environment`, but any key from
  `GET /api/resources/groups/types` is valid — see "Group types"
  below).
- Treating `rules[]` as AND. It's OR.
- Spelling `travesalSpecId` correctly. The API wants the typo.
- Relying on `id` for cross-instance portability. The server
  assigns it on create; sync identity is `resourceKey.name`.

## Group types

Custom groups are classified by a **group type** (a short taxonomy
bucket like `Environment`, `Department`, `Location`). A group
instance points at its type via `resourceKey.resourceKindKey`
(the type's `key`, not its `name`). `adapterKindKey` is always
`Container` for custom groups. Types are a flat list, no
hierarchy, no attributes — just `{name, key}`.

### Endpoints (all public, `/api/*`; no `/internal/*` equivalent)

| Verb | Path | Notes |
|---|---|---|
| GET | `/api/resources/groups/types` | List. Returns `{groupTypes: [{name, key}]}`. |
| POST | `/api/resources/groups/types` | Create. 201 with empty body. |
| DELETE | `/api/resources/groups/types/{key}` | Delete by `key`. 200 on success. |

No GET-by-key, no PUT/PATCH. To "rename" a type you must delete
and recreate (and fix up every group instance that references the
old key — destructive, avoid).

### JSON shape

```json
{ "name": "DRTier", "key": "DRTier" }
```

Only two fields. Full stop.

- `name` (string, **required on POST**) — user-visible label.
  Must be unique in the instance.
- `key` (string, server-assigned on POST if omitted) — stable
  identifier used as the foreign key from group instances. On
  POST, if you omit `key`, the server sets `key = name`. If you
  send `key`, it must equal `name` per the OpenAPI note — but
  the lab has two built-in types where `key != name`
  (`Tags Group`/`Feature`, `VCF Operations Self Monitoring`/
  `vC-Ops-Self-Monitoring`), so the server clearly accepts a
  divergent key for built-ins. For user-created types, treat
  `key == name` as the only supported shape. **Do not send
  `key`** — let the server assign it and then persist whatever
  it returns (look it up via a GET list after POST; 201 body is
  empty).

### Round-trip verified on lab (2026-04-08)

- `POST {"name":"APIEXPLORER_TEST_TYPE_DELETE_ME"}` → 201, empty
  body.
- `GET /api/resources/groups/types` → new entry appears with
  `key` == `name`.
- `DELETE /api/resources/groups/types/APIEXPLORER_TEST_TYPE_DELETE_ME`
  → 200, empty body.
- Subsequent GET no longer lists it. Clean.

### Cross-reference from group instance to type

A custom group's JSON encodes its type at
`resourceKey.resourceKindKey`, which is the type's `key`. Example
from the lab:

```json
"resourceKey": {
  "name": "[Custom] VMs on only Standard PGs",
  "adapterKindKey": "Container",
  "resourceKindKey": "Function"
}
```

Here `Function` is a group type (listed in `/groups/types`).
The link is **by key**, not by id — there is no separate type
id field. Consequences for the future `vcfops_customgroups`
loader:

1. **Types must be synced before instances.** An instance
   referencing a non-existent `resourceKindKey` will be rejected
   by the group create endpoint (or silently reclassified —
   untested; assume rejected).
2. **Sync identity for types is the `key` string.** Idempotent
   sync = "list, diff by key, POST missing". Deletes are
   dangerous because they orphan instances; prefer add-only.
3. **Renames are not supported.** A YAML rename = delete +
   recreate + rewrite every instance's `resourceKindKey`.
   Loader should refuse a rename unless explicitly forced.

### Gotchas

- `resourceKindKey` also appears on **non-custom** container
  resources (`vSphere World`, `NSXT World`, `Automation World`,
  etc.). Those are built-in container kinds, not group types,
  and will not appear in `/groups/types`. Don't confuse the two
  when scanning `GET /api/resources/groups` output; filter by
  `adapterKindKey == "Container"` **and** cross-check
  `resourceKindKey` against the types list if you want "true
  user custom groups only".
- OpenAPI claims "key must either not be sent or must match
  name". Empirically, the server is lenient on built-in types
  but enforces this for POST. Author loader: never send `key`.
- No bulk POST. One type per request.
- No `description` / `icon` / `color` / attribute schema. A
  group type is literally two strings.
