# MP chaining authoring grammar

Documents the YAML grammar for declaring chained requests in factory
management pack definitions (`content/managementpacks/*.yaml`).
Tooling agent settled this grammar on 2026-04-29 during the four-piece
Synology MP import-fix run.

**Scope.** Factory YAML authoring only.  The rendered wire format is
documented in `context/mpb_chaining_wire_format.md`.  This file is the
*author-facing* reference; that file is the *wire-format* reference.

---

## Background: what is a chained request?

A chained request fires once **per row** of a parent request's response
list.  MPB substitutes a per-row attribute value (e.g. a volume ID) into
the child request's URL params or path.

Chained requests appear in two situations:

1. **List object, secondary metricSet** — the primary metricSet drives
   list membership (one object per row).  A secondary metricSet augments
   each object with data from a per-object detail endpoint.
2. **Orphan request** — a request that would be chained but whose output
   is never bound to an object metricSet.  The factory validator **rejects**
   these (they produce a dangling `${requestParameters.X}` with no
   `chainingSettings` block, which the MPB importer rejects).

---

## Grammar decision: explicit `chains_from:` block on the metricSet

The factory uses **grammar (B)** — explicit declaration.  The chain
source is declared on the *metricSet* that uses the chained request, not
inferred by scanning for matching attribute names.

Rationale: explicit declaration makes validation straightforward (the
validator can reject mis-configured chains without heuristic scanning),
and avoids silent failures when two requests happen to expose an attribute
with the same name.

---

## Authoring a chained metricSet

```yaml
object_types:
  - name: Volume
    key: volume
    type: INTERNAL
    identifiers: [volume_id]
    name_expression: display_name

    metricSets:
      # Primary metricSet — drives list membership (one Volume per row)
      - from_request: get_volumes
        primary: true
        list_path: volumes          # path under response_path to the list

      # Chained secondary metricSet — per-volume detail request
      - from_request: volume_util
        chained_from: get_volumes   # local_name of the parent metricSet
                                    # (defaults to from_request name)
        list_path: ""               # empty unless volume_util response
                                    # itself is a list you iterate
        bind:
          - name: volume_id         # matches ${chain.volume_id} in the request
            from_attribute: id      # attribute label on the parent row
                                    # (must exist in the parent DML or be
                                    # auto-synthesized)

    metrics:
      - key: volume_id
        source: metricset:get_volumes.id
      - key: io_read_iops
        source: metricset:volume_util.read_access
```

And the corresponding request declaration:

```yaml
requests:
  - name: get_volumes
    method: GET
    path: entry.cgi
    params:
      - {key: api, value: SYNO.Core.Storage.Volume}
    response_path: data

  - name: volume_util
    method: GET
    path: entry.cgi
    params:
      - {key: api,      value: SYNO.Core.System.Utilization}
      - {key: location, value: "${chain.volume_id}"}   # substitution
    response_path: data
```

---

## Field reference

### `metricSet.chained_from`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `chained_from` | string | conditional | The `local_name` (= `from_request` unless `as:` is set) of the sibling metricSet that this one chains off. The named metricSet is the *parent*. |

Required when the `from_request` contains any `${chain.*}` token.  If
absent but the request contains chain tokens, the validator fails with:
> metricSet '...' uses request '...' which contains ${chain.*} token(s)
> [...] but no 'chained_from' is declared on this metricSet.

### `metricSet.bind[]`

One entry per `${chain.<name>}` token in the parent request.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Matches the `<name>` in `${chain.<name>}`. Must equal the `key` in the chain param emitted in `chainingSettings.params[].key`. |
| `from_attribute` | string | yes | The attribute label on the parent DML that supplies the per-row value. Must exist as a field in the parent request's response, or will be auto-synthesized by the renderer. |

The renderer auto-synthesizes `from_attribute` as a DML attribute on the
parent request if no metric on the parent metricSet already registers it.
This means you can bind to any field the API returns, even one you do not
expose as a metric.

### `${chain.<name>}` substitution token

Place `${chain.<name>}` in any request `params[].value`, `path`, `body`,
or `headers[].value` to mark a per-row substitution point.  The renderer
rewrites this to `${requestParameters.<name>}` in the emitted JSON and
synthesizes the full `chainingSettings` block.

---

## Validation rules

The validator (loader.py `_validate_mp` + `_validate_chain_tokens`) enforces:

1. **Per-metricSet:** if a request contains `${chain.*}` tokens, the
   metricSet using it must declare `chained_from`.
2. **Per-metricSet:** all `${chain.<name>}` tokens in the request must
   have a matching `bind` entry.
3. **Cross-MP (new, 2026-04-29):** if a top-level request contains
   `${chain.*}` tokens, it must be consumed as a chained metricSet
   (`chained_from` set) on at least one object_type.  A request with
   chain tokens but no consumer is a dangling chain — MPB import rejects
   the design with "unknown error".

---

## Wire-format correspondence

The factory YAML chain grammar maps to the MPB design JSON as follows:

| YAML | Wire JSON |
|---|---|
| `metricSet.chained_from` | `requests[child].chainingSettings.parentRequestId` |
| `metricSet.list_path` (on parent metricSet) | `chainingSettings.baseListId` |
| `metricSet.bind[].name` | `chainingSettings.params[].key` = `params[].usage` suffix |
| `metricSet.bind[].from_attribute` | `chainingSettings.params[].attributeExpression.expressionParts[].label` |
| `${chain.<name>}` in request | `${requestParameters.<name>}` in emitted request params/path |

See `context/mpb_chaining_wire_format.md` §2 for the full wire schema.

---

## Singleton vs list — no chaining needed for singletons

A singleton object (`is_singleton: true`) has multiple metricSets but
fires all of them once per collection cycle against the single target.
No chaining is needed.  All metricSets use `listId: "base"` (scalar
context).  Do **not** declare `primary: true` or `chained_from` on any
metricSet of a singleton.

See also: `context/mpb_chaining_wire_format.md` §7 "Singleton vs list".

---

## Cross-object-type chain root (Gap 2, 2026-05-07)

The standard `chained_from` grammar chains a metricSet off a **sibling**
metricSet on the same object_type.  A more powerful pattern — the
**chain root** — fires a single top-level request once, iterates its
response list, and propagates a per-row value (e.g. a site UUID) to
**every** downstream request across all object types.

This mirrors the jcox UniFi reference MP pattern: `get-sites-all` fires
once, and every device-type request (`get-devices-all`, `get-clients-all`,
`get-networks`, ...) chains off it via `${requestParameters.id}`.

### Grammar

Declare `chained_from` on the **primary** metricSet of the object_type,
pointing at a top-level request name that has no `from_request` consumer
on any object_type (the "chain root"):

```yaml
requests:
  # Chain root: fires once per collection cycle; no object type consumes it.
  - name: sites
    method: GET
    path: "/proxy/network/integration/v1/sites"
    params: []
    response_path: "data"

  # Child request: chains off sites; ${chain.site_id} substituted per row.
  - name: devices_ap
    method: GET
    path: "/proxy/network/integration/v1/sites/${chain.site_id}/devices"
    params:
      - {key: filter, value: "features.contains('accessPoint')"}
    response_path: "data"

object_types:
  - name: "Access Point"
    key: access_point
    identifiers: [device_id]
    name_expression: name
    metricSets:
      - from_request: devices_ap
        primary: true
        list_path: ""
        chained_from: sites     # ← references a top-level chain root, not a sibling
        bind:
          - name: site_id
            from_attribute: id  # 'id' field from each sites response row
    metrics:
      - key: device_id
        source: "metricset:devices_ap.id"
```

### Rules

- The chain root request (`sites`) must be declared in the top-level
  `requests:` block.
- The chain root must NOT have any `${chain.*}` tokens of its own
  (it is not chained off anything).
- The chain root is NOT consumed as a `from_request` on any metricSet.
- `chained_from` on the primary metricSet is the mechanism; the primary
  metricSet still defines list membership (one object per response row
  of the child request).
- Multiple object_types can each have a different primary metricSet that
  all chain off the same chain root.

### Wire output

- The chain root request (`sites`) gets `chainingSettings: null` and a
  DML containing the bind attributes (e.g. `id`) auto-synthesized by the
  renderer.
- Each child request (`devices_ap`, etc.) gets `chainingSettings` with
  `parentRequestId` pointing at the chain root's UUID and `baseListId`
  derived from the chain root's `response_path`.
- The primary metricSet's `objectBinding` in the wire output points at
  the chain root's `id` attribute (non-null, satisfying the MPB
  verify-time per-resource null-count rule).

### Contrast with sibling chaining

| Feature | Sibling chain | Cross-type chain root |
|---|---|---|
| `chained_from` target | sibling metricSet name | top-level request name |
| Target is consumed by a metricSet? | yes (the parent ms) | no |
| Multiple object_types can use? | no (per-object-type scope) | yes |
| Primary metricSet has `chained_from`? | no (primary is the root) | yes |

---

## References

- `context/mpb_chaining_wire_format.md` — wire format spec, UUID rules
- `context/mpb_synology_import_diff_2026_04_29.md` — root-cause analysis
  of the dangling-chain defect (defect #3)
- `vcfops_managementpacks/loader.py` — validator implementation
- `vcfops_managementpacks/render.py:_build_chaining_settings` — renderer
