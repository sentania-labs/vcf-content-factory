# MPB request chaining — design-export wire format

Authoritative reference for how Management Pack Builder (MPB) serializes
request-to-request chaining inside its design-export JSON. Future tooling
work (`vcfops_managementpacks/render.py`, `render_export.py`) and
`mp-designer` decisions cite this file.

**Scope.** The design-export JSON. The live MPB `/suite-api/internal/mpbuilder/*`
request surface is documented separately in
[`context/mpb_api_surface.md`](./mpb_api_surface.md). Pak-bundle wire format
is in [`context/pak_wire_format.md`](./pak_wire_format.md). Other content-
type wire formats are under [`context/wire_formats.md`](./wire_formats.md).

**Primary evidence.** `Synology DSM MP.json` exported 2026-04-18 from devel
MPB UI after Scott hand-built a chained request. Captured at
`/tmp/mpb_chain_export/Synology DSM MP.json`. Request index 9
(`"Volumes by Pool"`) is the only chained request.

**Cross-validation.**
`references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json`
(29 requests, 5 with non-null `chainingSettings`). Rubrik provides the
ground-truth LIST-object-with-chained-secondary-metricSet example that is
missing from Scott's Synology capture.

**UI narrative.** Broadcom's MPB walkthrough blog post documents the UI
flow for building chained requests, the "Enable chaining" toggle, the
3-request hierarchy (list → per-item detail → per-item-related list), and
the `${requestParameters.X}` substitution syntax:
<https://vrealize.it/2024/12/20/extend-vcenter-metrics-with-management-pack-builder/>

---

## 1. High-level model

MPB chaining is **strictly parent/child request-to-request iteration**. It
is not a peer enrichment join. The mental model is:

1. A parent request returns a list of items (e.g. one row per storage pool
   at some list path in the JSON response).
2. For each item in the parent's list, MPB fires the child request once,
   substituting one or more per-row attribute values into the child's URL
   params, path, headers, or body.
3. The child's response rows are then available for object binding —
   either as the sole source for a chained child object, or (in the Rubrik
   VM pattern) as a secondary metricSet on the same logical object whose
   primary metricSet is the parent's list.

A child request can itself be a parent — the chain depth is not bounded
by the wire format.

The chain is expressed **on the child**, pointing back at the parent:
`chainingSettings.parentRequestId` on the child request's JSON carries
the parent's `request.id`. The parent has no pointer to its children.

---

## 2. The `chainingSettings` block

### 2.1 Presence and nullability

`chainingSettings` lives directly on the `request` object —
`design.requests[i].request.chainingSettings` (design-export top-level is
`requests[]`, each element wraps a single `request` object).

Observations on nullability across captured designs:

| Design | Requests | non-null chains | null chains |
|---|---|---|---|
| Synology DSM MP.json (Scott, 2026-04-18) | 10 | 1 | 0 (absent, not null) |
| Rubrik Management Pack Design.json | 29 | 5 | 24 (present, value `null`) |
| sentania_aria_operations_dsm_mp Synology | 9 | 0 | 9 (present, value `null`) |
| Dale's fastapi.json | 2 | 0 | 2 |
| Dale's GitHub-MP-Builder.json | 1 | 0 | 1 |
| Dale's Broadcom Security Advisories.json | 2 | 0 | 2 |

Both shapes occur — MPB sometimes omits the key entirely, sometimes
serializes it as JSON `null`. Tooling must treat either as "no chain".

### 2.2 Full schema (from Synology request 9)

```json
"chainingSettings": {
  "id": "175ccb0b-f1ed-6c5e-152c-c8d6f8f1953c",
  "parentRequestId": "924420ac-b97c-4c49-883e-cf3453d03c2b",
  "baseListId": "data.pools.*",
  "params": [
    {
      "id": "2ed93c05-41c0-d526-3b17-f552ef651c6e",
      "label": "pool_id",
      "listId": "data.pools.*",
      "attributeExpression": {
        "id": "cdafba16-2f49-5178-5954-a4ff5aecc78a",
        "expressionText": "@@@MPB_QUOTE 69257d9b-473a-6d88-cfa0-e0f68dc0897f @@@MPB_QUOTE",
        "expressionParts": [
          {
            "id": "69257d9b-473a-6d88-cfa0-e0f68dc0897f",
            "originType": "ATTRIBUTE",
            "originId": "924420ac-b97c-4c49-883e-cf3453d03c2b-data.pools.*-@@@id",
            "label": "@@@id"
          }
        ]
      },
      "key": "pool_id",
      "usage": "${requestParameters.pool_id}"
    }
  ]
}
```

### 2.3 Field reference

**Top level.**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | opaque string (UUID or 22-char base62) | yes | Chain-block identity. Stable per design; may be regenerated if the chain is dropped and re-added via UI. |
| `parentRequestId` | string | yes | Equals `design.requests[p].request.id` for the parent request. |
| `baseListId` | string | yes | Logical list path in the parent's response that the chain iterates over (one substitution fire per element). Must match a `dataModelLists[].id` on the parent's `response.result.dataModelLists`. |
| `params[]` | array | yes (non-empty) | One entry per per-row value bound into the child request. |

**`params[i]`.**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | opaque string | yes | Param binding identity. |
| `key` | string | yes | Name used as `requestParameters.<key>` when the child substitutes this value. In Synology: `"pool_id"`. In Rubrik: `"id"`. |
| `label` | string | yes | UI display label. In Synology the value equals `key` (`"pool_id"`); in Rubrik it is a friendly name (`"ID"`) distinct from `key`. |
| `usage` | string | yes | The literal substitution template `${requestParameters.<key>}`. This is what the child's `path` / `params[].value` / `headers[].value` / `body` contains verbatim. |
| `listId` | string | yes | Logical list path the attribute lives in. Typically equals `baseListId` for single-row binding; may differ if an attribute is pulled from a deeper nested list. |
| `attributeExpression` | object | yes | How the per-row value is computed. See §2.4. |
| `example` | string | no | Optional example value. Present in Rubrik, absent in Synology. |

### 2.4 `attributeExpression`

```json
{
  "id": "<uuid>",
  "expressionText": "@@@MPB_QUOTE <part-id> @@@MPB_QUOTE",
  "expressionParts": [
    {
      "id": "<same-part-id>",
      "originType": "ATTRIBUTE",
      "originId": "<parentRequestId>-<listId>-<label>",
      "label": "<attribute-label>"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `id` | Expression block identity. |
| `expressionText` | A string template built from literal text plus `@@@MPB_QUOTE <uuid> @@@MPB_QUOTE` tokens. Each token references an `expressionParts[].id`. For a single-attribute passthrough, the entire expressionText is exactly one quoted token. Complex expressions (concat, transforms) combine multiple tokens and literal text, though this document has no empirical examples beyond single-attribute. |
| `expressionParts[]` | Declarations of the UUID references used in `expressionText`. |
| `expressionParts[].id` | UUID referenced inside `expressionText`. |
| `expressionParts[].originType` | `"ATTRIBUTE"` in all captured examples. No other values observed. |
| `expressionParts[].originId` | Composite pointer to a specific attribute on a specific list of a specific request — see §4. |
| `expressionParts[].label` | The attribute label (also the trailing segment of `originId`). |
| `expressionParts[].regex` / `regexOutput` / `example` | Present in Rubrik export as `null`/`""`; absent in Synology export. Reserved for regex extraction on the source value. Not exercised by captured examples. |

---

## 3. Substitution syntax and scopes

Substitution tokens appear inline in request fields (`path`, `name`,
`params[].value`, `headers[].value`, `body`) as `${<scope>.<field>}`.
The `usage` field in a chain param is always the template for that
specific chain binding — the child request is responsible for
containing that literal template somewhere it will be expanded.

### 3.1 Scopes observed

| Scope | Example | Meaning |
|---|---|---|
| `requestParameters.<key>` | `${requestParameters.pool_id}` | Value bound by a chain `params[]` entry, resolved per parent row at execution time. |
| `authentication.credentials.<field>` | `${authentication.credentials.username}`, `${authentication.credentials.passwd}` | User-input credential fields from the adapter instance config. |
| `authentication.basic` | `${authentication.basic}` | Pre-computed `Basic <base64>` string for HTTP Basic auth. |
| `authentication.session.<field>` | `${authentication.session.datadid}` | Values extracted from a prior authentication request's response and carried as session state. |
| `configuration.<key>` | `${configuration.mpb_hostname}`, `${configuration.mpb_connection_timeout}` | Builder-level configuration such as hostname, port, SSL mode, retry counts, concurrency. |

### 3.2 Where `usage` templates appear in the child

In Synology request 9 the child binds `pool_id` into a URL param:

```json
"params": [
  { "key": "location", "value": "${requestParameters.pool_id}" }
]
```

In Rubrik requests 14/15/17/18/19 the child binds `id` into the URL path
itself:

```
"path": "api/v1/vmware/host/${requestParameters.id}"
"name": "vmware/vm/${requestParameters.id}/snapshot"
```

Both are valid; MPB does not care where the template lives as long as it
will be evaluated when the child request is fired.

---

## 4. The `@@@X` convention and `originId` composite

### 4.1 `@@@` prefix on attribute labels

MPB auto-synthesizes certain row-level attributes that are not in the raw
JSON. These appear in `response.result.dataModelLists[].attributes[]`
with labels prefixed `@@@`. Observed labels:

| Label | Meaning |
|---|---|
| `@@@id` | Synthetic per-row identifier (array index or derived). |
| `@@@rawValue` | Raw row value when the list element is a scalar rather than an object. |

Real attributes from the source JSON appear with their natural path as
the label (e.g. `id`, `size.total`, `data_scrubbing.can_do_manual`).
Both `@@@id` and a real `id` can coexist on the same list — Synology's
`data.pools.*` has 73 attributes including both `@@@id` and `id`. Scott's
export bound `@@@id`, Rubrik's chains bind the real `id`. Either works as
long as the target attribute exists on the parent's declared list.

### 4.2 `originId` composite format

The `expressionParts[].originId` is a three-part composite joined by `-`:

```
<parentRequestId>-<listId>-<attributeLabel>
```

Worked examples:

| Composite | Parts |
|---|---|
| `924420ac-b97c-4c49-883e-cf3453d03c2b-data.pools.*-@@@id` | req UUID · list `data.pools.*` · attr `@@@id` (Synology) |
| `4oPuK7kokCC9tszuJA1aHN-data.*-id` | req base62 · list `data.*` · attr `id` (Rubrik) |
| `rSJRsa6Lh4Knmh5ZbvqxUz-data.*-id` | req base62 · list `data.*` · attr `id` (Rubrik) |

The same composite value appears verbatim as the `id` on the parent
request's `response.result.dataModelLists[x].attributes[y]`. For example
the Synology parent has:

```json
{
  "id": "924420ac-b97c-4c49-883e-cf3453d03c2b-data.pools.*-@@@id",
  "label": "@@@id",
  "key": ["@@@id"]
}
```

**Rule for tooling:** to construct `originId`, take the parent request's
`id`, append `-`, append the `baseListId` (or the attribute's enclosing
list id if different), append `-`, append the attribute `label`. No
escaping is applied — the composite relies on the fact that list IDs and
labels do not themselves contain `-` in MPB-generated data. (JSON keys
that do contain `-` would break this scheme; none have been observed.)

---

## 5. The `@@@MPB_QUOTE <uuid> @@@MPB_QUOTE` tokenizer

`attributeExpression.expressionText` is a string that interleaves literal
text with UUID references to `expressionParts[]` entries. The token
syntax is:

```
@@@MPB_QUOTE <space> <part-uuid> <space> @@@MPB_QUOTE
```

That is, the literal string `@@@MPB_QUOTE`, a single space, the referenced
part's `id`, a single space, then the literal string `@@@MPB_QUOTE`
again. Both opening and closing sentinels are the same string — this is a
symmetric delimiter, not an open/close pair.

All captured chains use **exactly one** such token consuming the entire
expressionText (a pure passthrough of the referenced attribute value).
Empirically:

- Synology req 9: `"@@@MPB_QUOTE 69257d9b-473a-6d88-cfa0-e0f68dc0897f @@@MPB_QUOTE"`
- Rubrik req 14: `"@@@MPB_QUOTE chZ3Lv5gozCaeUm75gohyy @@@MPB_QUOTE"`
- Rubrik req 19: `"@@@MPB_QUOTE fsXC6GkSBCXX1ERWGpfGfQ @@@MPB_QUOTE"`

The UUID inside the token always exists as an `expressionParts[].id` in
the same `attributeExpression` block.

**Multi-attribute expressions.** Inferred but not yet captured: combining
multiple attributes or mixing literal text with references would produce
expressionText like
`"prefix-@@@MPB_QUOTE <id1> @@@MPB_QUOTE/@@@MPB_QUOTE <id2> @@@MPB_QUOTE"`
with two expressionParts entries. **Gap** — no captured example. A
follow-up UI capture of a chain with two bound values (or a concat
expression) would close this.

---

## 6. Two-concern separation: chain vs. object binding

The chain (request-to-request via `chainingSettings.parentRequestId`) is
**separate** from the object binding (object-to-request via
`objects[].object.metricSets[].requestId`). Both must be correct for a
chained multi-metricSet LIST object to work.

Captured evidence, Rubrik VM list object (`objects[0]`):

```
metricSets[0]: listId="data.*"  requestId=<vmware/vm>
metricSets[1]: listId="base"    requestId=<vmware/vm/${requestParameters.id}>
```

The two metricSets are siblings on one LIST object. MetricSet[0] (the
primary) pulls each row from the parent list request. MetricSet[1] (the
chained secondary) pulls a scalar-rowed response from the per-VM detail
request. The chain relationship lives on the detail request's
`chainingSettings` (pointing at the VM list request); the object
relationship lives on the object's metricSets (each referencing its own
requestId).

**Rule for tooling / mp-designer:** to add a chained-in secondary
metricSet on a LIST object, two separate pieces of output JSON must
agree:

1. The secondary request's `chainingSettings.parentRequestId` must equal
   the primary request's `id`, and `baseListId` must equal the primary
   metricSet's `listId`.
2. The object must carry both metricSets with correct `requestId` and
   `listId` for each.

Tooling must emit both sides atomically — a chained request with no
object binding (Synology request 9 as captured) is a dangling chain.

---

## 7. Singleton vs list — chaining is required for lists, optional for singletons

Empirical contrast within Scott's Synology capture:

**Singleton Diskstation object (`objects[1]`).** `isListObject=false`,
three metricSets bound to three different requests:

```
metricSets[0]: listId="base"  requestId=<System>
metricSets[1]: listId="base"  requestId=<FileStation>
metricSets[2]: listId="base"  requestId=<Utilization>
```

None of `System`, `FileStation`, `Utilization` has a `chainingSettings`
block. All three requests fire in parallel once per collection cycle,
producing scalar rows (`listId="base"`) that MPB merges onto the single
Diskstation instance. No chain is needed — a singleton has exactly one
target object, so MPB has no "which row does this attribute go on?"
question to resolve.

**LIST object with secondary metricSet (Rubrik VM, `objects[0]`).** The
secondary request MUST be chained. MPB needs a per-row binding to know
which VM row the `vmware/vm/<id>` response attaches to — the chain's
`parentRequestId` + `baseListId` provides that, and the
`${requestParameters.id}` substitution steers the detail request to the
correct per-row endpoint.

**Consequence for mp-designer:** multi-metricSet singletons do not need
to render `chainingSettings` on any of their secondary requests.
Multi-metricSet list objects require a chain on every non-primary request,
pointing at the primary.

---

## 8. UUID inventory for chaining

Every new chained request introduces the following fresh identifiers,
which tooling must generate at render time and keep stable across
re-renders if rename-safe behavior is desired:

| Field | Fresh or derived | Notes |
|---|---|---|
| `chainingSettings.id` | Fresh | Block identity. |
| `chainingSettings.params[i].id` | Fresh | Per-param identity. |
| `chainingSettings.params[i].attributeExpression.id` | Fresh | Expression identity. |
| `chainingSettings.params[i].attributeExpression.expressionParts[j].id` | Fresh | Each part has its own id, referenced by `expressionText` tokens. |
| `chainingSettings.parentRequestId` | Derived | Must equal the parent `request.id` already generated for that request. |
| `chainingSettings.params[i].attributeExpression.expressionParts[j].originId` | Derived | Composite `<parentRequestId>-<listId>-<attributeLabel>`. Must match an attribute `id` on the parent's `dataModelLists[].attributes[]`. |
| `chainingSettings.baseListId` | Derived | Must equal one of the parent's `dataModelLists[].id` values. |
| `chainingSettings.params[i].listId` | Derived | Usually equals `baseListId`. |

**Format.** Synology uses full RFC-4122 UUIDs (`650da298-c4d2-...`).
Rubrik uses 22-character base62 tokens (`rSJRsa6Lh4Knmh5ZbvqxUz`). MPB
accepts either — the `id` fields are treated as opaque strings. Our
tooling should emit RFC-4122 UUIDs for consistency with the rest of the
factory and with the Synology-family designs we are repackaging.

---

## 9. Known capture gaps

1. **No ground-truth chained-secondary-metricSet example in our own
   design.** Scott's 2026-04-18 Synology export has a chained request
   (`Volumes by Pool`) that is not bound to any object — `Test Request`
   errored during capture, so no response data was available to map, so
   no object was created or extended. The Rubrik design fills this gap
   from an outside source, but an in-factory capture is still needed to
   confirm MPB serializes the object side identically for our designs.

   **Follow-up:** add a chained request to any devel design, map its
   response to an existing list object even if the response data is
   sparse or mocked, export, commit the export to `/tmp/` for a fresh
   capture diff.

2. **No multi-attribute expressionText example.** All captured chains
   use a single `@@@MPB_QUOTE <uuid> @@@MPB_QUOTE` token. Capture needed
   for expressions combining two or more attributes, and for any use of
   the `regex` / `regexOutput` fields on `expressionParts`.

3. **No multi-hop chain example (parent → child → grandchild).** The
   blog describes a 3-request chain pattern but all captured non-null
   chains are depth-1. Capture needed to verify whether depth-2+ chains
   serialize with any additional fields, and how substitution scopes
   compose across hops.

4. **No session-state + chain interaction.** Synology uses
   `${authentication.session.datadid}` in unchained requests; Rubrik has
   no session auth. We have no example of a chain whose `usage` template
   references session state or whose parent derives session state.

---

## 10. Rendering implications for factory tooling

**Current state (2026-04-18).** `vcfops_managementpacks/render.py` and
`render_export.py` have no chainingSettings emission. Designs that need
multi-request LIST objects cannot be expressed.

**Delta from current YAML grammar.** `bundles/.../synology_dsm.yaml` (and
any future MP YAML) expresses per-object request binding via
`object_binding:` style grammar. That grammar is flat — each binding is
object-to-request, no request-to-request relationship. It cannot
currently express:

- A child request's pointer at its parent (`parentRequestId`).
- The `baseListId` iteration path.
- The per-param binding of a parent attribute to a child-request
  substitution key (`params[]` with `attributeExpression`).

**What render has to emit** (specification — fix is mp-designer /
tooling territory):

- On a child request's output JSON, a full `chainingSettings` block
  following §2 and §4 with fresh UUIDs per §8.
- Guarantee that `originId` composites are constructed from values
  already emitted on the parent's `dataModelLists` section — i.e. the
  parent's response discovery must precede or coexist with child-request
  chain emission.
- On an object with a chained secondary metricSet, one `metricSets[]`
  entry per request, with correct `listId` / `requestId` on each.

**What the YAML grammar needs to grow** (design target — not decided
here): a way to declare "request X is chained off request Y iterating
list Z, binding attribute A of Y's row to key K in X's params". The
exact surface is mp-designer's call.

---

## 11. References

- [`context/mpb_api_surface.md`](./mpb_api_surface.md) — live MPB REST surface
  (`/suite-api/internal/mpbuilder/*`).
- [`context/pak_wire_format.md`](./pak_wire_format.md) — sibling wire format doc
  for .pak bundle structure.
- [`context/wire_formats.md`](./wire_formats.md) — index of other content-zip
  wire formats (super metrics, dashboards, views, policies).
- <https://vrealize.it/2024/12/20/extend-vcenter-metrics-with-management-pack-builder/>
  — Broadcom's UI narrative for MPB chaining.
- Captured evidence: `/tmp/mpb_chain_export/Synology DSM MP.json`
  (request index 9, parent request index 4).
- Cross-validation: `references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json`
  (requests 14, 15, 17, 18, 19).
