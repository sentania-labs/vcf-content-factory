# MPB `objectBinding` wire format — empirical reference

Authoritative reference for how the MPB importer accepts (and silently
mutates) the `objectBinding` block on `objects[].object.metricSets[]`
in a design-import payload. Future tooling work
(`vcfops_managementpacks/render.py`, `render_export.py`) and
`mp-author` decisions cite this file before editing the renderer.

**Scope.** Only the MPB design-import wire format
(`POST /suite-api/internal/mpbuilder/designs/import`). Runtime adapter
behavior — whether a given binding actually correlates rows at
collection time — is not covered. The MPB API does not expose enough
to test runtime end-to-end (the source-test gate, see
[`mpb_api_surface.md`](./mpb_api_surface.md), blocks reaching VALID).

**Primary evidence.** Live POST/GET cycles on
`vcf-lab-operations-devel.int.sentania.net` 2026-04-29 against the
factory-rendered `tmp/synology_rendered_v2.json` (Synology MP). 18
distinct objectBinding shapes were uploaded, the server's stored form
read back, and the per-section status errors compared. All test
designs were deleted after observation. Cross-referenced against
`reference/references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json`
(authoritative third-party MPB pack with non-null bindings) and
`context/mpb_wire_reference/synology_nas_working_export.json` (known-
working community Synology pack — zero objectBindings).

Probe scripts retained at `tmp/objbind/probe.py`, `probe_advanced.py`,
`probe_validation.py`, `probe_working.py`. Raw results at
`tmp/objbind/results.jsonl`, `results_adv.jsonl`.

---

## 1. Summary

The MPB importer is **far more permissive** about `objectBinding`
than the factory renderer assumed.

- **Import never fails because of `objectBinding` shape.** Every
  variant tested — null, omitted, type=`PARAMETER_TO_PROPERTY`,
  type=`PARAMETER_TO_ATTRIBUTE`, type=`ATTRIBUTE_TO_ATTRIBUTE`,
  type=`TOTALLY_MADE_UP_VALUE`, missing-type field, missing
  matchExpression, originId pointing at non-existent attributes,
  garbage originId, originId with the zero UUID — produced HTTP 201
  with the design accepted. The only validation error any variant
  triggered was the unrelated `Source requires environment test
  response after import.` source-gate.
- **The wire field name on output is `objectBindingType`, not
  `type`.** The server's import path accepts incoming `type` (and,
  apparently, several other names — see §2.2) but stores and emits
  the field as `objectBindingType` on `GET /designs/{id}/objects/{id}`.
- **Every `type` value is silently coerced to `ATTRIBUTE_TO_PROPERTY`
  on output.** No matter what enum the import sends — including
  literal nonsense like `"TOTALLY_MADE_UP_VALUE"` — the server
  rewrites `objectBindingType` to `ATTRIBUTE_TO_PROPERTY` on the
  stored object. **There is no evidence any other enum value is
  honored at import time.** Whether the runtime treats
  `PARAMETER_TO_PROPERTY` differently from `ATTRIBUTE_TO_PROPERTY`
  could not be tested via this API surface.
- **`originType` IS preserved verbatim.** Sending `PARAMETER` returns
  `PARAMETER`; sending `ATTRIBUTE` returns `ATTRIBUTE`. So if the
  runtime gates behavior on `originType`, that distinction survives
  round-trip.
- **`originId` requestId prefixes are remapped on import.** The
  importer mints a fresh request UUID for each request in the
  payload; references to the original requestId inside `originId`
  composites (`<reqId>-<listId>-<attribute>`) get rewritten to use
  the new requestId on read-back. So cross-request references can be
  authored using the original IDs and the server fixes them up. The
  importer does NOT, however, validate that the listId or attribute
  portion actually exists in the referenced request's
  `dataModelLists` — non-existent attribute labels are preserved
  verbatim.
- **The "type stripped to null" symptom in the original observation
  is wrong.** The factory previously thought the importer was
  stripping `type` to null. It is not. It is renaming `type` ->
  `objectBindingType` AND coercing the value to
  `ATTRIBUTE_TO_PROPERTY`. Any reader looking for the field as
  `type` would see absence and infer "stripped". The diagnostic
  needed to inspect the alternate field name.
- **The known-working community Synology export has zero
  `objectBinding` blocks at all** (grep `"objectBinding"` against
  `synology_nas_working_export.json` returns zero matches). It
  imports cleanly, with only the source-test source-gate error.
  This is strong evidence that the canonical pattern for "MP-owned
  list object with chained secondary request" is to **not bind on
  the metricSet** — the chain in `chainingSettings` provides
  per-row binding implicitly.
- **Rubrik's non-null `objectBinding` blocks are exclusively for
  stitching to native Aria Ops objects** (their `idx0` augments
  Aria's `VMWARE-VirtualMachine`). Both binding types in Rubrik
  carry an `objectMatchExpression` whose origin is
  `originType: ARIA_OPS_METRIC` with originId `aria-VMWARE-VirtualMachine-VMEntityObjectID`.
  No Rubrik objectBinding is for an MP-owned chained-secondary
  metricSet without a stitching target.

**Bottom line for the factory.** For MP-owned chained-secondary
metricSets (Synology Volume → volume_util pattern), the renderer
should emit `objectBinding: null` and rely on `chainingSettings` on
the secondary request. The renderer's current emission of
`ATTRIBUTE_TO_PROPERTY` + `originType: PARAMETER` was modeled on a
mis-read of Rubrik's stitching pattern; both Rubrik's authoritative
shape and the working Synology community export disagree with it.

> **2026-04-29 second-round correction (see §8):** the bottom-
> line above is **import-time correct, verify-time wrong**.
> Import accepts both metricSets null on a multi-metricSet
> resource. The verify-time builder-file parser rejects it
> with: "Only one [metricRequest per resource] can be null and
> it must be referenced by another request." The correct
> emission for chained-secondary metricSets is a NON-null
> `objectBinding`. See §8 for the rule, §9 for captured working
> patterns including three new reference packs (Unifi,
> phpIPAM, vSAN-policy), and §10 for the updated renderer
> spec. The recommendation in §4.2 is **superseded** by §10.

---

## 2. The enum table

### 2.1 `objectBinding.type` (input) → `objectBinding.objectBindingType` (output)

All variants below received HTTP 201 on import. None affected the
overall design `status` (which stayed `INVALID` solely because of
the source-test gate). All non-null variants stored a non-null
`objectBindingType` on read-back.

| # | Sent `type` | Sent `originType` | Stored `objectBindingType` | Stored `originType` | Notes |
|---|---|---|---|---|---|
| 1 | `null` (or omitted) | n/a | `null` (or absent) | n/a | The "no binding" baseline. |
| 2 | `ATTRIBUTE_TO_PROPERTY` | `ATTRIBUTE` | `ATTRIBUTE_TO_PROPERTY` | `ATTRIBUTE` | originId remapped, attr existence not validated. |
| 3 | `PARAMETER_TO_PROPERTY` | `PARAMETER` | `ATTRIBUTE_TO_PROPERTY` | `PARAMETER` | type coerced; originType preserved. |
| 4 | `PARAMETER_TO_ATTRIBUTE` | `PARAMETER` | `ATTRIBUTE_TO_PROPERTY` | `PARAMETER` | type coerced; originType preserved. |
| 5 | `ATTRIBUTE_TO_PROPERTY` | `PARAMETER` | `ATTRIBUTE_TO_PROPERTY` | `PARAMETER` | The current renderer's output — accepted, originType preserved. |
| 6 | `ATTRIBUTE_TO_ATTRIBUTE` | `ATTRIBUTE` | `ATTRIBUTE_TO_PROPERTY` | `ATTRIBUTE` | type coerced; originType preserved. |
| 7 | `TOTALLY_MADE_UP_VALUE` | `ATTRIBUTE` | `ATTRIBUTE_TO_PROPERTY` | `ATTRIBUTE` | Garbage type accepted; coerced. |
| 8 | (key omitted) | `ATTRIBUTE` | `ATTRIBUTE_TO_PROPERTY` | `ATTRIBUTE` | Type defaults to `ATTRIBUTE_TO_PROPERTY` if missing. |
| 9 | input field `objectBindingType: ATTRIBUTE_TO_PROPERTY` (the output field name) | `ATTRIBUTE` | `ATTRIBUTE_TO_PROPERTY` | `ATTRIBUTE` | Server accepts the alternate field name on input. |

**Conclusion:** at the import-validation surface, the `type` field
value is **not checked**. It is normalized to a single output value
on read-back. The runtime may distinguish, but the import API
provides no signal.

### 2.2 Synonymy of `type` and `objectBindingType` on input

The server accepts BOTH `objectBinding.type` (which is what every
captured reference design uses) AND `objectBinding.objectBindingType`
(the output field name) on input. Both produce the same stored
shape. The factory should standardize on `type` for input parity
with the Rubrik reference.

### 2.3 `matchExpression.expressionParts[].originType` (input → preserved)

| Sent | Stored |
|---|---|
| `ATTRIBUTE` | `ATTRIBUTE` |
| `PARAMETER` | `PARAMETER` |
| `ARIA_OPS_METRIC` (in `objectMatchExpression`, Rubrik pattern) | `ARIA_OPS_METRIC` (assumed; not directly tested in this probe — see Rubrik export for evidence) |

`originType` IS preserved through round-trip. So **runtime divergent
behavior on originType is the only mechanism by which input
choices around `type` could matter** — the server rewrites `type`
to a single value but keeps the origin pointer's discriminator.

### 2.4 `originId` composite handling

| Input shape | Server behavior |
|---|---|
| `<existing-reqId>-<existing-listId>-<existing-attr-label>` | Request UUID prefix remapped to the new (server-minted) request id. List/attr portions preserved verbatim. |
| `<existing-reqId>-<existing-listId>-<NON-existing-attr>` | Same as above. **Attribute existence is NOT validated.** |
| `<all-zero-UUID>-...` (nonexistent reqId) | Prefix replaced with some other new UUID. Listing/attr portion preserved. (Probably not the right UUID — runtime likely fails.) |
| `garbage-string-no-uuid-prefix` | Server prepends a new UUID before the string. (Pathological; never author this way.) |
| `expressionParts: []` (empty list) | Accepted; stored as empty list. |

The takeaway: **the importer does best-effort UUID remapping for
references, but does no semantic validation that the binding
target exists.** Authors must validate attribute references at
factory build time (see §5).

---

## 3. Common author scenarios with the right shape

### 3.1 Singleton (`isListObject: false`) with one or more metricSets

**Pattern.** Set `objectBinding: null` on every metricSet. No
`chainingSettings` on the bound requests. Each request returns scalar
data on listId `"base"`; MPB merges them onto the single instance.

**Evidence.**
- Rubrik Cluster — `isListObject=false`, 8 metricSets across 8
  parallel requests, all with `objectBinding=null`,
  none chained. Read with `python3 tmp/objbind/probe_working.py`-
  equivalent inspection of the Rubrik design.
- Working Synology Diskstation — `isListObject=false`, 3 metricSets
  (system / filestation / utilization), all `objectBinding=null`,
  none chained.

**Renderer rule.** For singletons, never emit objectBinding.

### 3.2 List object with one metricSet (single source request)

**Pattern.** `isListObject: true`, one metricSet, `listId` =
the parent's `dataModelLists[].id` (e.g. `data.volumes.*`),
`objectBinding: null`. No chaining required.

**Evidence.**
- Working Synology Storage Pool, iSCSI LUN, Disks, Volume — all
  list objects with one metricSet, no objectBinding, no chaining.

**Renderer rule.** Drop the speculative second metricSet emission
that the current factory renderer adds for chained requests on the
same object. If the chained API doesn't echo the parent identifier
and isn't going to be useful via `chainingSettings`-only, the
chained metrics simply aren't expressible on this object — that's
a design constraint, not a renderer bug.

### 3.3 List object with chained secondary metricSet (chained API echoes parent identifier — Rubrik VM detail pattern)

**Pattern.** Two metricSets on the list object. The first uses the
parent list request, `listId` = the parent's data list. The second
uses the chained per-item request, `listId` = `"base"` (or whatever
single-row listId the chained response provides). The chained
request carries a full `chainingSettings` (per
[`mpb_chaining_wire_format.md`](./mpb_chaining_wire_format.md)).

**objectBinding on the chained metricSet:** evidence is mixed.

| Evidence | Has objectBinding? | objectBinding shape |
|---|---|---|
| Rubrik idx0 ms[1] (`vmware/vm/${requestParameters.id}`) | YES | `type: ATTRIBUTE_TO_PROPERTY`, matchExpression originId points at chained response's own `base.moid`, plus `objectMatchExpression` for stitching to Aria's VirtualMachine. |
| Working Synology Volume | NO (and no chained second metricSet either; chained `volume_util` is a dangling chain) | n/a |
| Existence of any captured pure-MP-owned list object with chained-secondary metricSet AND objectBinding | NONE found. |

**Renderer rule.** When the chained API echoes the parent
identifier (e.g. `vmware/vm/{id}` returns `id` field in its body),
two correct shapes both work at import time:

1. **No objectBinding** (recommended for pure MP-owned objects).
   Rely on `chainingSettings.params[].attributeExpression` on the
   chained request to provide row-binding. This is the simpler
   shape and matches the working Synology community pattern.
2. **objectBinding pointing at the chained response's echoed
   attribute** (Rubrik pattern, but only when the chained response
   *actually echoes* the parent identifier — i.e. the attribute
   composite `<chainedReqId>-<chainedListId>-<echoed-attr>` exists
   in the chained request's `dataModelLists`). Default
   `originType: ATTRIBUTE`.

Until runtime tests prove otherwise, **prefer shape #1** — it's
strictly fewer bytes, matches the working community precedent, and
sidesteps the silently-coerced `type` enum.

### 3.4 List object with chained secondary metricSet (chained API does NOT echo parent identifier — Synology volume_util pattern)

> **SUPERSEDED at verify-time by §8 + §10.** This section's
> recommendation #1 ("don't bind at all") fails the verify-time
> per-resource null-count rule when a list resource has
> multiple metricSets. Read §10.2 for the correct shape.
> The structural-options inventory below remains accurate.

**Pattern.** Same as 3.3 structurally, but the chained response
contains only IO data, no field that echoes the parent's primary
key.

**Wire-shape options observed:**

1. **Don't bind at all on the chained metricSet** (`objectBinding:
   null`). The chained request still carries `chainingSettings`, so
   it iterates per-parent-row at runtime. The synthetic `@@@id`
   row marker MPB always synthesizes (`<chainedReqId>-<listId>-@@@id`)
   provides an implicit per-row identifier — runtime's job to
   correlate by iteration order, not by attribute value. Whether
   this actually correlates correctly cannot be determined from
   import alone.
2. **Bind via the synthetic `@@@id`** (`originId: <chainedReqId>-<listId>-@@@id`,
   `originType: ATTRIBUTE`). MPB always synthesizes `@@@id` on every
   list, so this composite always resolves at import. Probe
   variant `D_self_at_id` confirmed import accepts this shape.
3. **Synthesize an echo attribute manually** by adding the parent
   key as an extra entry in the chained response's `dataModelLists`
   attributes list, then bind to it (probe variant
   `C_augment_dml_self`). Imports accept this — but the runtime
   would only see the synthesized attribute if the actual response
   payload contains a value at that JSON path, which for a
   no-echo API it does not. So this is a structurally-valid lie:
   the importer accepts it but the adapter can't fulfill it.

**Recommendation.** Don't expose the chained request's metrics on
the parent list object if the chained API doesn't echo the parent
identifier. Either (a) skip those metrics entirely (working Synology
pattern — `volume_util` exists in the design but is dangling), or
(b) restructure the model so the chained request feeds a different
object that lives at the iteration target's natural identity (e.g.
pull `volume_util` per-volume IO into a different downstream object
or into a relationship). The factory's current attempt to staple
`volume_util` onto Volume via a fabricated `PARAMETER` originType
binding does not match any captured working pattern and the
import-time silent coercion of `type` makes it likely the runtime
either ignores the binding or attaches data ambiguously.

### 3.5 List object stitched onto a native Aria object (Rubrik VM augmentation pattern)

**Pattern.** Two metricSets on the list object; both carry an
`objectBinding` with **two** expressions:

- `matchExpression` — points at the source data attribute that
  contains a value matching some Aria-native identifier (e.g.
  Rubrik's `moid` echoes vCenter's managed-object ID).
- `objectMatchExpression` — points at the **Aria-native** attribute
  the moid should match against. Uses `originType: ARIA_OPS_METRIC`
  and an `originId` like `aria-VMWARE-VirtualMachine-VMEntityObjectID`.

Both metricSets in Rubrik idx0 carry **identical**
`objectMatchExpression` → `aria-VMWARE-VirtualMachine-VMEntityObjectID`,
so all rows from both requests stitch onto the same Aria native
VM object.

**Renderer rule.** This is the only scenario where `objectBinding`
on a list object's metricSet is unambiguously documented in
captured evidence. If the factory ever needs to stitch (i.e.
augment a VMware/vSphere/Aria-native object with custom-collected
metrics), this is the shape to copy. Out of scope for current
Synology / Unifi authoring.

---

## 4. The recommended `render.py:1302` fix

### 4.1 The current emission (factory bug)

At `vcfops_managementpacks/render.py:1302` (or whichever line the
chained-metricSet branch lives — verify before patching), for a
chained metricSet on a list object, the renderer currently emits:

```python
objectBinding = {
    "type": "ATTRIBUTE_TO_PROPERTY",
    "matchExpression": {
        "id": <fresh uuid>,
        "expressionText": f"@@@MPB_QUOTE {<part-uuid>} @@@MPB_QUOTE",
        "expressionParts": [{
            "id": <part-uuid>,
            "label": <chain-param-label>,    # e.g. "volume_id"
            "originId": <parent-chain-param-uuid>,  # e.g. eb689da5-...
            "originType": "PARAMETER",
        }],
    },
}
```

This is **wrong** in three ways:

1. The `originId` points at the chaining-settings parameter UUID,
   not at any attribute or parameter identity the runtime knows
   how to resolve. The reference Rubrik pattern uses `originId`
   composites of the form `<requestId>-<listId>-<attrLabel>` —
   our code emits a bare parameter UUID instead.
2. `originType: PARAMETER` is not a documented value for this
   slot. Rubrik (the only source-of-truth for non-null bindings)
   uses `originType: ATTRIBUTE` exclusively.
3. The implicit assertion is "the runtime will dereference this
   param UUID and produce per-row binding." There is no captured
   evidence the runtime does this.

### 4.2 The correct emission — SUPERSEDED, see §10

> **This subsection is superseded by §10.** The original
> recommendation here ("emit null") was correct at the
> import-time validator and wrong at the verify-time
> validator. See §8 for the verify rule and §10.2 for the
> updated renderer spec.

(Original text retained below for diff context only.)

**Default rule.** Emit `objectBinding: null` on every
chained-secondary metricSet. Let the chained request's
`chainingSettings.params[].attributeExpression` provide row-binding
implicitly. This is the simpler shape and matches all working
captures.

```python
objectBinding = None  # or omit the key entirely; both round-trip identically
```

### 4.3 Worked example — Synology Volume + volume_util

Today's factory output (excerpt):

```json
{
  "object": {
    "id": "<volume-obj-uuid>",
    "isListObject": true,
    "metricSets": [
      {
        "requestId": "<get_volumes-uuid>",
        "listId": "data.volumes.*",
        "metrics": [...properties from get_volumes...],
        "objectBinding": null
      },
      {
        "requestId": "<volume_util-uuid>",
        "listId": "data.*",
        "metrics": [...IO metrics from volume_util...],
        "objectBinding": {
          "type": "ATTRIBUTE_TO_PROPERTY",
          "matchExpression": { ... originType=PARAMETER, originId=<chain-param-uuid> ... }
        }
      }
    ]
  }
}
```

Recommended factory output:

```json
{
  "object": {
    "id": "<volume-obj-uuid>",
    "isListObject": true,
    "metricSets": [
      {
        "requestId": "<get_volumes-uuid>",
        "listId": "data.volumes.*",
        "metrics": [...properties from get_volumes...],
        "objectBinding": null
      },
      {
        "requestId": "<volume_util-uuid>",
        "listId": "data.*",
        "metrics": [...IO metrics from volume_util...],
        "objectBinding": null
      }
    ]
  }
}
```

The key invariant the renderer must guarantee: `volume_util`'s
`request.chainingSettings` is fully populated (parentRequestId,
baseListId, params with attributeExpression). That's what makes the
chained metricSet work at runtime, not the objectBinding.

### 4.4 Worked example — when echo IS available (Rubrik-style chained API)

If a future MP target chains an API that DOES echo the parent
identifier in the chained response (e.g. `GET /things/{id}` returns
`{"id": "<echo>", ...}`), the optional richer shape is:

```json
{
  "objectBinding": {
    "type": "ATTRIBUTE_TO_PROPERTY",
    "matchExpression": {
      "id": "<fresh uuid>",
      "expressionText": "@@@MPB_QUOTE <part-uuid> @@@MPB_QUOTE",
      "expressionParts": [{
        "id": "<part-uuid>",
        "label": "id",
        "originId": "<chained-request-uuid>-base-id",
        "originType": "ATTRIBUTE"
      }]
    }
  }
}
```

**Authoring rule:** the `originId` composite must point at a real
attribute in the chained request's response `dataModelLists` — i.e.
`<chainedRequest.id>-<listId>-<attrLabel>` must equal an existing
`request.response.result.dataModelLists[i].attributes[j].id`. The
importer does NOT validate this, so the validator (§5) must.

The default is still null — this richer shape is only worth
emitting when the runtime semantics depend on it (currently
unknown), or when the rendering is being copied verbatim from a
known-working external source like Rubrik.

### 4.5 Stitching (out of scope for current MPs)

If/when the factory needs to augment an Aria-native object,
emission shape is per §3.5 — copy Rubrik's pattern with both
`matchExpression` and `objectMatchExpression`, the latter using
`originType: ARIA_OPS_METRIC`. Don't synthesize this shape today;
it's parked until needed.

---

## 5. Validator rule the framework should add

`vcfops_managementpacks` validate-time checks (added to whichever
schema or post-load validator covers MP designs):

1. **Singleton objects must not carry `objectBinding`.** If
   `isListObject: false`, every metricSet's `objectBinding` MUST be
   null/absent. Reject otherwise.
2. **List objects with one metricSet must not carry
   `objectBinding`** unless the binding is a stitching binding
   (carries `objectMatchExpression` with `originType:
   ARIA_OPS_METRIC`). The non-stitching shape on a single-metricSet
   list object has no captured precedent; refuse to render.
3. **List objects with multiple metricSets** — the secondary
   metricSets' bound requests MUST carry `chainingSettings` with
   `parentRequestId` equal to the primary metricSet's `requestId`
   and `baseListId` equal to the primary's `listId`. (Per
   `mpb_chaining_wire_format.md` §6.) If chainingSettings is
   missing, refuse to render — the binding will be ambiguous.
4. **If `objectBinding` is non-null on any metricSet:**
   - `objectBinding.type` MUST be `ATTRIBUTE_TO_PROPERTY` (the only
     value the server keeps; emitting anything else is misleading).
   - `objectBinding.matchExpression.expressionParts[]` MUST have
     `originType` ∈ {`ATTRIBUTE`}. (`PARAMETER` is round-tripped by
     the import API but has no captured working precedent. Avoid
     emitting it. `ARIA_OPS_METRIC` belongs in
     `objectMatchExpression`, not `matchExpression`.)
   - `expressionParts[].originId` MUST be a string of the form
     `<reqId>-<listId>-<attrLabel>` where `<reqId>` is one of the
     design's request UUIDs, `<listId>` is one of that request's
     `dataModelLists[].id` values, and `<attrLabel>` is one of that
     list's `attributes[].label` values. Validator must dereference
     all three. (Critical: the importer does NOT validate this, so
     the factory must.)
5. **If `objectBinding.objectMatchExpression` is present, it MUST
   carry `originType: ARIA_OPS_METRIC`.** Stitching-only field.
6. **Renderer must emit `null` (or omit) `objectBinding` by default**
   on factory-authored chained-secondary metricSets. Authoring an
   override into the YAML grammar should require an explicit
   stitching declaration (e.g. `stitch_to: vmware/VirtualMachine`),
   not be inferred from the presence of a chained request.

---

## 6. Open questions / things I couldn't determine

1. **Does the runtime adapter actually correlate rows for a chained
   metricSet with `objectBinding: null`?** Cannot test via the
   import API alone — the source-test gate blocks reaching VALID,
   so `/install` is silently a no-op. The hypothesis (chaining +
   per-row iteration via `chainingSettings.params` is sufficient
   for row-binding) is supported by the working Synology community
   pack having no objectBinding on Volume — but Volume in the
   community pack does NOT have a chained secondary metricSet at
   all. **Open: confirm via `claude -p` install on devel after the
   renderer fix lands and Scott runs source-test through the UI.**
2. **Does the runtime distinguish `originType: PARAMETER` from
   `originType: ATTRIBUTE` semantically?** The import API
   round-trips both faithfully but only ever sees
   `objectBindingType=ATTRIBUTE_TO_PROPERTY` regardless of input.
   Captured evidence shows ATTRIBUTE only. Treat ATTRIBUTE as the
   only safe value until runtime evidence appears.
3. **Does the runtime correlate by attribute value match, by
   iteration order, or by both?** The working Rubrik chained
   metricSet binds to `base.moid` (a real value in the chained
   response) AND has `chainingSettings` for iteration. No captured
   evidence isolates which mechanism does the work. Probably
   matters when the chained API can return rows out-of-order
   relative to the parent's iteration — but unverified.
4. **Source-test source-gate.** All probe variants land INVALID
   solely because the source has not been tested. The MPB UI's
   `/jobs` endpoint is reachable on `/suite-api/internal/mpbuilder/`
   (responds 400 on POST instead of 404) but rejects all probed
   bodies with `No collector found with UUID null`. The collector
   reference field's correct name and position were not located in
   this investigation. **Open: HAR capture from Scott's MPB UI
   session would close this.** Tracked separately in
   `mpb_api_surface.md` §"Source Test Endpoint".
5. **What does the `objectBinding` shape look like on the response
   of `GET /designs/export?id=...` after a design has been made
   VALID via UI source-test?** Cannot capture without a VALID
   design on devel via this API. May reveal whether the server
   re-normalizes `objectBindingType` again on export, or whether
   it preserves what was stored at import. Worth a follow-up
   capture by Scott via the UI.
6. **Multi-attribute `matchExpression`.** All captures use a single
   `@@@MPB_QUOTE <id> @@@MPB_QUOTE` token. Whether multi-attribute
   compound bindings are accepted is untested. (Same gap as
   `mpb_chaining_wire_format.md` §9.)
7. **`objectBindingType` enum reality.** The server coerces all
   inputs to `ATTRIBUTE_TO_PROPERTY`. Whether other enum values
   exist somewhere in the codebase (e.g. for stitching, for
   property-only bindings, for self-references) is not visible
   from the API surface. The output is single-valued in our
   captures. If a future MP needs a different binding semantic,
   the question to ask is "does the runtime distinguish on
   `objectBindingType` at all, or only on the presence of
   `objectMatchExpression` plus `matchExpression` content?"

---

## 7. References

- [`context/mpb_api_surface.md`](./mpb_api_surface.md) — MPB live REST surface, including the source-test gate this investigation could not bypass.
- [`context/mpb_chaining_wire_format.md`](./mpb_chaining_wire_format.md) — sibling reference for `chainingSettings`. §6 + §7 overlap with §3 of this doc.
- [`context/mpb_synology_import_diff_2026_04_29.md`](./mpb_synology_import_diff_2026_04_29.md) — static diff that surfaced the original "type stripped to null" symptom.
- [`context/mpb_wire_reference/synology_nas_working_export.json`](./mpb_wire_reference/synology_nas_working_export.json) — community-known-working Synology export. Zero `objectBinding` blocks.
- `reference/references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json` — Rubrik MP, only third-party MPB design with non-null `objectBinding` blocks. All bindings are stitching to Aria-native VirtualMachine.
- `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json` — Unifi MP, ATTRIBUTE_TO_PROPERTY with `me-part: ATTRIBUTE` and `ome-part: METRIC`. Captures peer-to-peer same-object metricSet stitching by metric value (added 2026-04-29).
- `reference/references/jcox-au_vmware/phpipam_MP_Builder_Design.json` — phpIPAM MP, all-null bindings even on multi-list objects. Confirms null-everywhere is valid for the no-chain case (added 2026-04-29).
- `reference/references/vrealize_it_vsan_default_policy/vSAN default storage policy.json` — vSAN default storage policy MP, ATTRIBUTE_TO_PROPERTY with `me-part: PARAMETER` and `ome-part: ARIA_OPS_METRIC`. Confirms PARAMETER+ARIA_OPS_METRIC stitch pattern WITH companion ome (added 2026-04-29).
- `tmp/objbind/probe.py`, `probe_advanced.py`, `probe_validation.py`, `probe_working.py` — empirical probes used in original 2026-04-29 round.
- `tmp/objbind/results.jsonl`, `results_adv.jsonl` — raw probe results.
- `tmp/objbind2/probe.py`, `probe2.py`, `results2.json` — second-round import-time probes (verify-time round, 2026-04-29).

---

## 8. Verify-time validation rules (2026-04-29 second-round investigation)

### 8.1 The rule (authoritative — from server error text)

When a design is exercised through verify (the `/jobs` source-test
flow on `/suite-api/internal/mpbuilder/designs/{id}/jobs`, or
the equivalent UI Verify-step), an additional **builder-file
parser** runs over the per-resource metricRequest set. The exact
constraints (verbatim from the server's error text, captured by
Scott on devel 2026-04-29):

> 'RESOURCES' error for ids [<resource-uuid>] regarding field
> 'requestedMetrics'. Field was invalid. Multiple groups of
> metrics from 'metricRequests' were not given an object binding.
> **Only one per resource can be null and it must be referenced
> by another request.**
>
> 'REQUESTED_METRIC' error for ids [<metricSet-uuid-1>,
> <metricSet-uuid-2>] regarding field 'objectBinding'. Missing
> fields detected. **A list resource request is missing its
> object binding and it has not been referenced by another
> request on that list resource. Set an object binding for this
> request.**

Plain reading:

1. **At most ONE metricSet per resource may have null
   `objectBinding`.**
2. The single null-bound metricSet must be **the chain-parent**
   — i.e. some other request's `chainingSettings.parentRequestId`
   must equal that metricSet's `requestId`.
3. Every other metricSet on the same resource MUST have a
   non-null `objectBinding`.

### 8.2 What this overrides from §1 / §3.4

The previous bottom-line ("emit `objectBinding: null` on chained-
secondary metricSets") was correct at the **import** validator
(import accepts both-null without complaint and stores both
null). It is wrong at the **verify** validator. The correct rule
is the strict per-resource null-count rule above.

The community Synology pack does NOT contradict this — it never
ships a chained-secondary metricSet **on the same resource**. Its
`volume_util` chained request exists in the design but no
resource attaches a metricSet to it (it's a "dangling" chained
request whose metrics are simply not exposed). That works under
the verify rule because Volume has only one metricSet (the
get_volumes one), with null binding, satisfying the "exactly one
null and it's the chain-parent" condition trivially (it's the
only metricSet).

The factory's design intent — "expose `volume_util` IO metrics
on Volume objects" — is what forces a SECOND metricSet onto
Volume, which is what triggers the verify error. The fix is not
"emit both null" (which works at import but fails at verify);
the fix is "emit a non-null binding on the secondary metricSet".

### 8.3 Where this validator runs

Empirically located: the verify rule is **NOT** enforced by
`POST /suite-api/internal/mpbuilder/designs/import` (which
returns 201 Created for any objectBinding shape, including
both-null on a multi-metricSet resource). It is **NOT** enforced
by `POST /designs/{id}/jobs` with `testType: TEST_CONNECTION`
either — that endpoint just runs the test request HTTP call
and returns its response.

The rule is enforced by some pipeline that runs **after** an
edit through the UI's design editor — likely a server-side
"build-file generation" pass that produces the parser-readable
form of the design and validates per-resource consistency.

The exact REST endpoint that triggers it has not been located
under `/suite-api/internal/mpbuilder/*`. Probed and rejected:
`/designs/{id}/verify`, `/validate`, `/build`, `/preview`,
`/parse`, `/check`, `/buildFile`, `/builder`, all variants on
`/jobs` with `jobType` ∈ {`VERIFY`, `BUILD`, `PREVIEW`,
`PARSE`, `VALIDATE`, `TEST_DESIGN`, `RUN_REQUEST`,
`TEST_REQUEST`, `PARSE_BUILDER`}. All returned the generic
"Invalid input format" 400.

The rule definitely runs in the UI's Verify wizard step (Scott
observed it). It also produces the terse `objects.errors`
entry visible at `GET /designs/{id}/status`:

```json
"objects": {
  "errors": [{
    "refId": "<volume-object-uuid>",
    "error": "Unknown error in object, edit to resolve the error."
  }],
  "itemCount": 5
}
```

This terse status entry is what the Synology factory-imported
design exhibits today (verified 2026-04-29 on devel design
`a6b6877f-bfad-43af-84e7-aa56f209b8d9`). The verbose error
message above is what the UI Verify-step exposes; the API only
gives the terse form via `/status`.

### 8.4 The collectorId gotcha (incidental finding)

`/jobs` `TEST_SOURCE` rejects requests where the source's
`configuration.collectorId` is null with: `400 Invalid input
format / "No collector found with UUID null"`. Factory-rendered
designs leave `collectorId` null because at render time we
don't know the lab's collector UUID. Either:

- Author the design with a placeholder collectorId and rely on
  the UI to set the actual one before source-test, or
- Pull `GET /api/collectors` at install time and inject the
  first available collectorId.

This is unrelated to objectBinding but blocks any factory-
driven `/jobs` source-test until resolved. Tracked here because
it surfaced during the verify-time investigation.

---

## 9. Captured working patterns (updated 2026-04-29)

| Pack | Pattern | me-part originType | me-part originId shape | ome-part originType | ome-part originId shape | Use case |
|---|---|---|---|---|---|---|
| Working Synology community | NULL on every metricSet | n/a | n/a | n/a | n/a | Singleton or list with one metricSet, no chained secondary attached. |
| Rubrik | Aria-stitch (both metricSets on idx0 carry binding) | `ATTRIBUTE` | `<chained-req-id>-base-moid` | `ARIA_OPS_METRIC` | `aria-VMWARE-VirtualMachine-VMEntityObjectID` | Augment Aria-native VirtualMachine with custom metrics. |
| **Unifi** (new) | Peer-stitch by metric value (ms[1] binding) | `ATTRIBUTE` | `<thisRequestId>-<thisListId>-id` (own response's id field) | `METRIC` | `<metric.id-on-the-other-metricSet-of-this-resource>` | Same object has two parallel non-chained requests; ms[1]'s rows match ms[0]'s by metric value. The two requests do NOT chain. |
| **phpIPAM** (new) | NULL on every metricSet | n/a | n/a | n/a | n/a | Pure self-discovery, no multi-metricSet resources. Same shape as community Synology. |
| **vSAN-policy** (new) | Aria-stitch via PARAMETER | `PARAMETER` | `<param-uuid>` (the request's parameter id) | `ARIA_OPS_METRIC` | `aria-VMWARE-Datastore-VMEntityObjectID` | Single-metricSet list resource that fetches detail per Datastore (param=`{datastoreId}`), stitched onto Aria-native Datastore. The PARAMETER shape works **only with companion ome ARIA_OPS_METRIC**; the param is the variable used in the URL, the ome is what the resulting rows stitch onto. |

**Synology no-echo case is structurally NEW** — none of the
captured patterns directly cover "MP-owned chained-secondary
metricSet on a list object whose chained API does not echo the
parent identifier in its response". The closest analogues are:

- **Unifi** (peer-to-peer same-object stitching) — but Unifi's
  ms[1] response DOES contain its own `id` attribute that the
  me-part points at. Synology volume_util's response has nothing
  similarly stable.
- **vSAN-policy** (PARAMETER + ARIA_OPS_METRIC ome) — but
  vSAN-policy stitches onto an Aria-native Datastore. Synology
  Volume is MP-owned, not Aria-native, so the ARIA_OPS_METRIC
  shape doesn't apply directly.

### 9.1 Hypothesis ranking for the Synology no-echo case

Based on the captured patterns and the verify rule, ranked from
most-likely-correct to least:

**Tier 1 — likely correct:**

1. **Cross-metricSet ATTRIBUTE pointing at the parent's
   `volume_id` attribute, no ome.** Shape:
   ```json
   {
     "type": "ATTRIBUTE_TO_PROPERTY",
     "matchExpression": {
       "id": "<uuid>",
       "expressionText": "@@@MPB_QUOTE <part-id> @@@MPB_QUOTE",
       "expressionParts": [{
         "id": "<part-id>",
         "label": "volume_id",
         "originId": "<get_volumes-uuid>-data.volumes.*-volume_id",
         "originType": "ATTRIBUTE"
       }]
     }
   }
   ```
   Rationale: the parent metricSet's data list (`data.volumes.*`)
   contains a `volume_id` attribute with the actual volume
   identifier value. Pointing the chained metricSet's binding
   at THAT attribute tells the parser "the chained rows stitch
   onto whichever parent row produced their `volume_id`". This
   is logically equivalent to chainingSettings — but expressed
   via the binding so the parser's per-resource null-count rule
   is satisfied. **No ome required** — there's no Aria-native
   stitch target.

   Status: imports cleanly (variant X3 in
   `tmp/objbind2/results2.json`); verify-time test pending.

**Tier 2 — possibly correct, less aligned with captured
evidence:**

2. **Self @@@id binding** (variant X2). Server keeps it
   round-trip; whether the parser accepts is unverified. The
   `@@@id` synthesized identifier is a positional row index, not
   the parent's identity, so even if it parses it likely
   correlates by iteration order rather than by value.

3. **PARAMETER + ARIA_OPS_METRIC ome (vSAN-policy pattern
   adapted)** — would only work if the runtime treats
   `ARIA_OPS_METRIC` ome as "stitch into THIS native object".
   Synology Volume is MP-owned, so there's no aria-* native
   object id to point at. Probably not applicable.

**Tier 3 — known-broken:**

4. **PARAMETER alone, no ome** — the current factory output;
   the verify rule's terse error is on this design.
   Confirmed-broken. Do not emit.

5. **Both null** — fails the per-resource null-count rule.
   Confirmed-broken. Do not emit.

### 9.2 Verify-time confirmation gap

Direct verify-time confirmation of Tier 1 was not achieved this
round. The blockers:

- `/jobs` `TEST_CONNECTION` runs only the source's testRequest,
  not the per-resource builder-file parse.
- A bearer-reachable endpoint that triggers the parser was not
  located (probed exhaustively per §8.3).
- Re-importing a probe variant resets `installed: false` and
  `installStatus: DRAFT`, AND the importer strips
  `authentication.credentials[].value` for sensitive creds — so
  re-imported probe designs cannot pass source-test without
  manual credential re-entry through the UI.
- Modifying objectBinding on the existing devel Synology design
  via `PUT /designs/{id}/objects/{objId}` returns HTTP 500
  (server-side bug), and `PUT /designs/{id}` only accepts a
  summary-shape body, not a full design.

**Closing this gap requires either:**

- **HAR capture from Scott's UI session** during a Verify
  click, isolating the exact endpoint + body the UI uses; OR
- **Manual UI test cycle**: Scott edits the live Synology
  design's Volume objectBinding to each Tier-1 candidate via
  the UI, clicks Verify, and reports which shape clears the
  error. (Most reliable; most time-expensive.)

Tier 1 #1 (cross-metricSet ATTRIBUTE pointing at parent's
volume_id) is the highest-confidence shape pending verify-time
confirmation. The renderer should emit it; if Scott's UI test
shows it doesn't clear the verify error, fall back to Tier 2 #2
(self @@@id) and re-test.

---

## 10. Recommended renderer change (supersedes §4.2)

`vcfops_managementpacks/render.py` chained-secondary-metricSet
branch must emit the Tier 1 #1 shape, NOT null. Concrete spec:

### 10.1 Inputs the renderer needs at this site

For each chained secondary metricSet on a list object:

- `parent_request_id` — the chain-parent request's UUID (already
  in scope as `chainingSettings.parentRequestId` of the chained
  request).
- `parent_list_id` — the chain-parent's `dataModelLists[].id`
  that the chain iterates over (already in scope as
  `chainingSettings.baseListId`).
- `parent_attr_label` — the label of the chain-parent attribute
  whose value is the chain-key. This is the SAME attribute that
  the chain `params[i].attributeExpression.expressionParts[0]`
  references via `originId = <parent_request_id>-<parent_list_id>-<attr-label>`.
  The `attr-label` portion of that originId composite IS the
  parent_attr_label.

For Synology Volume + volume_util:
- `parent_request_id` = `b8c7ce81-fa05-403e-9d7e-f590449471d3` (get_volumes)
- `parent_list_id` = `data.volumes.*`
- `parent_attr_label` = `volume_id`

### 10.2 Emit shape

```python
def _emit_objectbinding_for_chained_secondary(parent_request_id,
                                              parent_list_id,
                                              parent_attr_label):
    part_id = str(uuid.uuid4())
    expr_id = str(uuid.uuid4())
    return {
        "type": "ATTRIBUTE_TO_PROPERTY",
        "matchExpression": {
            "id": expr_id,
            "expressionText": f"@@@MPB_QUOTE {part_id} @@@MPB_QUOTE",
            "expressionParts": [{
                "id": part_id,
                "label": parent_attr_label,
                "originId": f"{parent_request_id}-{parent_list_id}-{parent_attr_label}",
                "originType": "ATTRIBUTE",
            }],
        },
        # NO objectMatchExpression — we are not stitching to an Aria-native object.
    }
```

The renderer should call this for every metricSet that
references a request whose `chainingSettings.parentRequestId`
equals another metricSet's request on the SAME object. The
chain-parent metricSet (the one referenced by parentRequestId)
keeps `objectBinding: null`.

### 10.3 Keep `objectBinding: null` cases

Per the verify rule, a metricSet's objectBinding should remain
null if and only if:

- The object has only ONE metricSet (the trivial case), OR
- This metricSet is the chain-parent (its requestId is referenced
  by another metricSet's request via `chainingSettings.parentRequestId`).

For all other metricSets, emit the shape in §10.2.

### 10.4 Validator update (supersedes §5)

The §5 validator rules need a single correction:

**Rule 4 was wrong**: "Renderer must emit `null` (or omit)
`objectBinding` by default on factory-authored chained-secondary
metricSets." This rule causes the verify-time failure. Replace
with:

> Renderer must emit a NON-NULL `objectBinding` on every
> chained-secondary metricSet (i.e. every metricSet whose
> request has a populated `chainingSettings`). The shape is
> per §10.2 unless the design explicitly opts into a stitching
> shape (e.g. ARIA_OPS_METRIC ome).

**Other §5 rules stand**, with one tightening:

> Rule 4.b update: `originType` ∈ {`ATTRIBUTE`} for the
> me-part on MP-owned same-resource binding. `PARAMETER` is
> reserved for the vSAN-policy stitching pattern (§3.5 / §9 row
> "vSAN-policy") and MUST be paired with an `objectMatchExpression`
> with `originType: ARIA_OPS_METRIC`. Emitting `PARAMETER`
> without ome is the broken shape that triggered this entire
> investigation; refuse to render.

### 10.5 Aria-stitching extension (out-of-scope today, designed for tomorrow)

When the factory eventually grows MP-owned objects that
stitch onto Aria-native objects (e.g. an external MP that
augments VMware-VirtualMachine), the renderer needs:

- An optional `stitch_to: <aria-native-resource-kind>` field in
  the MP YAML grammar (e.g. `stitch_to: vmware/VirtualMachine`).
- When present, both metricSets on the affected object emit
  objectBinding with the Rubrik (§3.5) or vSAN-policy (§9)
  shape, depending on whether the stitch attribute is an
  ATTRIBUTE-from-response or a PARAMETER-from-request.

Not implemented today. Synology / Unifi / Synology+volume_util
are all MP-owned-only and do not stitch onto Aria natives.

---

## 11. Ground-truth fix — jcox cross-metricSet binding (2026-05-07)

### 11.1 The reference

`reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json` — "UniFi -
Devices" object, ms[1] (`get-device-statistics`). This is the
authoritative working example of a chained-secondary metricSet
binding on an MP-owned list object. Confirmed identical shape on
"UniFi - WiFi Broadcasts" ms[1].

The jcox UniFi MP ms[1] objectBinding structure (exact fields):

```json
{
  "type": "ATTRIBUTE_TO_PROPERTY",
  "matchExpression": {
    "id": "<uuid>",
    "expressionText": "@@@MPB_QUOTE <part-id> @@@MPB_QUOTE",
    "expressionParts": [{
      "id": "<part-id>",
      "label": "id",
      "regex": null,
      "example": "",
      "originId": "<secondary-req-id>-data.*-id",
      "originType": "ATTRIBUTE",
      "regexOutput": ""
    }]
  },
  "objectMatchExpression": {
    "id": "<uuid>",
    "expressionText": "@@@MPB_QUOTE <part-id> @@@MPB_QUOTE",
    "expressionParts": [{
      "id": "<part-id>",
      "label": "ID_device",
      "regex": null,
      "example": "",
      "originId": "<parent-metric-wire-id>",
      "originType": "METRIC",
      "regexOutput": ""
    }]
  }
}
```

Note: example/regex/regexOutput fields ARE present in the exchange
format (jcox is an exchange-format export). The `_strip_flat_only_fields`
pass in `render_export.py` preserves them inside objectBinding via the
`_in_objectbinding=True` context flag.

### 11.2 How the two expressions map onto the factory YAML schema

Given:
- Parent metricSet: `from_request: devices_ap`, bind[0]: `from_attribute: id`
- Secondary metricSet: `from_request: device_stats_ap`, `chained_from: devices_ap`
- Parent metric declared on this object sourced from `metricset:devices_ap.id`:
  key=`device_id`, label=`"Device ID"`

Then:

| Expression field | Value | Source |
|---|---|---|
| `matchExpression.expressionParts[0].originId` | `<secondary_req_id>-<secondary_dml_id>-id` | Secondary's OWN attribute (same field name as from_attribute) |
| `matchExpression.expressionParts[0].originType` | `ATTRIBUTE` | Always ATTRIBUTE for intra-MP binding |
| `matchExpression.expressionParts[0].label` | `id` (= from_attribute) | bind[0].from_attribute |
| `objectMatchExpression.expressionParts[0].originId` | `<parent-metric-wire-id>` | `_make_id(f"{obj_seed}:metric:{m.key}")` for the parent metric whose field_path == from_attribute |
| `objectMatchExpression.expressionParts[0].originType` | `METRIC` | Always METRIC for intra-MP cross-metricSet binding |
| `objectMatchExpression.expressionParts[0].label` | `"Device ID"` | The parent metric's display label (m.label) |

**Critical distinction from §10.2 (superseded):** §10.2 specified
matchExpression pointing at the PARENT's attribute
(`<parent_req_id>-<parent_list_id>-<attr>`) with no objectMatchExpression.
The jcox ground truth shows the OPPOSITE — matchExpression points at
the SECONDARY's own attribute, and objectMatchExpression points at the
PARENT's metric (by wire metric ID, originType METRIC, not ATTRIBUTE).

### 11.3 Renderer implementation

Implemented in `vcfops_managementpacks/render.py` Case 2 (2026-05-07).
The renderer now:

1. Calls `req_info.register_field(parent_attr_label, dml_id)` to get the
   secondary's own attribute origin ID.
2. Iterates `metrics_by_ms[parent_ms_local_name]` to find the parent
   metric whose `field_path == from_attribute`.
3. Uses that metric's wire ID (`_make_id(f"{obj_seed}:metric:{m.key}")`)
   as the objectMatchExpression originId with `originType: "METRIC"`.
4. Falls back to the old ATTRIBUTE shape (with a warning log) if no
   parent metric sources from_attribute — indicating the bind attribute
   was auto-synthesized and not declared as a metric. This prevents
   invalid renders while signalling the authoring gap.

### 11.4 Verified on

- UniFi Integration MP: 3 objects (Access Point, Switch, Gateway), each
  with ms[0] null + ms[1] ATTRIBUTE_TO_PROPERTY+METRIC shape. ✓
- Synology NAS MP: Volume with ms[0] null + ms[1] ATTRIBUTE_TO_PROPERTY+METRIC
  shape (volume_id binding). ✓

---

## 12. CHAINED_REQUEST objectBinding — when secondary doesn't echo the bind attribute (2026-05-09)

### 12.1 The problem

The §11 jcox shape (ATTRIBUTE_TO_PROPERTY with matchExpression pointing at
the secondary's own attribute) only works when the secondary response
actually contains that field. For UniFi's `/statistics/latest` response,
the payload contains only statistics (cpuUtilizationPct, memoryUtilizationPct,
etc.) — it does NOT contain the device `id` field used as the chain key.
The `originId` composite `<secondary_req_id>-<listId>-id` references a
field that never appears in the response, so the runtime attribute match
silently fails → `numberOfMetricsCollected = 0`.

### 12.2 Detection logic

The renderer detects whether Sub-case A (ATTRIBUTE_TO_PROPERTY) or Sub-case B
(CHAINED_REQUEST) applies by scanning the object type's metrics for any metric
whose source is `metricset:<secondary_ms_name>.<from_attribute>`:

```python
secondary_echoes_bind = False
for m in metrics_by_ms.get(ms.local_name, []):
    _, field_path = _parse_source_ref(m.source)
    if field_path == parent_attr_label:
        secondary_echoes_bind = True
        break
```

- If a metric IS sourced from `metricset:<secondary>.<from_attribute>`,
  the secondary payload contains that field → use ATTRIBUTE_TO_PROPERTY
  (Sub-case A, §11 shape).
- If NO such metric exists, the secondary payload does not echo the bind
  attribute → use CHAINED_REQUEST (Sub-case B).

### 12.3 CHAINED_REQUEST shape

```python
object_binding = {
    "type": "CHAINED_REQUEST",
    "matchExpression": {
        "id": _make_id(f"{ob_seed}::matchExpr"),
    },
}
```

`render_template.py` `_render_object_binding()` handles this type by
emitting `{"type": "CHAINED_REQUEST", "id": <uuid>}` in the template JSON.
The MPB runtime uses the chain context (chainingSettings) for per-row
binding implicitly — no explicit attribute match expression is required.

### 12.4 Applied cases (2026-05-09)

| MP | Object | Secondary metricSet | from_attribute | Secondary echoes? | Shape |
|---|---|---|---|---|---|
| UniFi Integration | Access Point | device_stats_ap | id | No (/statistics/latest has no `id` field) | CHAINED_REQUEST |
| UniFi Integration | Switch | device_stats_switch | id | No | CHAINED_REQUEST |
| UniFi Integration | Gateway | device_stats_gateway | id | No | CHAINED_REQUEST |
| Synology NAS | Volume | volume_util | volume_id | No (volume_util returns only IO stats) | CHAINED_REQUEST |

### 12.5 Future authoring note

If a future MP chains a secondary API that DOES echo the parent key in
its response (e.g. a detail endpoint that returns `{"id": "...", ...}`),
declare a metric sourcing `metricset:<secondary>.<from_attribute>` on that
object type. The renderer will then automatically select the
ATTRIBUTE_TO_PROPERTY shape (§11) with the correct ATTRIBUTE+METRIC
expression pair.
