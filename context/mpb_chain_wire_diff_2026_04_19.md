# MPB Chain Wire Format Diff — 2026-04-19

Evidence for the chain1 INVALID import failure. Compares our
render-export output against known-good HoL-2501-12 Module 5
(`GitLab-Basic.json`) — the only public ground-truth example of
chainingSettings wire format we have access to.

## Artifacts
- Reference (good): `references/hol-2501-lab-files/HOL-2501-12/Module 5/GitLab-Basic.json`
  chained request: `getBranches` → `getProjects`.
- Ours (INVALID): `managementpacks/synology_dsm_chain1.yaml`
  chained request: `volume_util` → `get_volumes`.
- Ours rendered: `python3 -m vcfops_managementpacks render-export managementpacks/synology_dsm_chain1.yaml > /tmp/chain1_export.json`

## Chain-block shape (structure matches, field set differs)

Both place `chainingSettings` on the **request** (not the metricSet).
Both structure:
```
chainingSettings:
  id, parentRequestId, baseListId
  params[]:
    id, key, label, usage, listId, attributeExpression
    attributeExpression:
      id, expressionText, expressionParts[]
      expressionParts[]:
        id, label, originId, originType
```

The topology, UUID scheme, and `@@@MPB_QUOTE` placeholder in
`expressionText` all match. Internal references (originId →
parent dml attribute) are consistent within our design.

## Missing fields (renderer gap)

These are fields HoL emits that our renderer does not:

### In `chainingSettings.params[]`
- `example: ""`

### In `chainingSettings.params[].attributeExpression.expressionParts[]`
- `example: ""`
- `regex: null`
- `regexOutput: ""`

### In every metric's `expression.expressionParts[]` (broader gap)
- `example: ""`
- `regex: null`
- `regexOutput: ""`

### On every metric object
- `timeseries: null` — HoL emits this on every metric; we don't.

**Caveat:** The roundtrip (non-chain) design imports cleanly and it
has the same missing metric-side fields. So the metric-side
missing fields are tolerated by MPB. The **chain-specific fields**
(in `chainingSettings.params` and their expressionParts) are the
actual delta between a working import (roundtrip) and an INVALID
one (chain1).

## Known non-issues (ruled out)

### Missing "base" root in dataModelLists — NOT the bug
Roundtrip and chain1 both emit nested-list requests with a single
dml entry `{id: "data.volumes.*.*", parentListId: "base"}` and no
matching `{id: "base", parentListId: null}` root. HoL always emits
both. Since roundtrip imports fine with the same malformation,
MPB tolerates this.

### listId style difference — NOT the bug
HoL uses short list ids (`"*"`) while we use full paths
(`"data.volumes.*.*"`). Our usage is internally consistent (all
cross-refs match), and the roundtrip works with this same style.

### `from_attribute: id` binding a non-declared metric — OPEN
Riker flagged this as suspect #1. The HoL `getProjects` response
has `id` declared as a metric ("ID", PROPERTY, STRING) on the
consumer object. Our chain1 does not declare `id` as a metric on
Volume (we use `volume_id`, `volume_path`, etc.). The renderer
auto-synthesizes `id` into the parent request's dml attribute
list so the chain `originId` resolves — so structurally the wire
is consistent. We have no direct evidence this matters for MPB
import validation. **Deferred** until we see whether the renderer
fix alone closes the gap.

## Recommended renderer fix

Target file: `vcfops_managementpacks/render_export.py` (or
`render.py` — whichever emits chainingSettings).

Add these fields in the chainingSettings emit path:

```python
params.append({
    "id": param_id,
    "key": param_key,
    "label": param_label,
    "usage": param_usage,
    "listId": param_list_id,
    "example": "",                                   # NEW
    "attributeExpression": {
        "id": expr_id,
        "expressionText": expr_text,
        "expressionParts": [
            {
                "id": part_id,
                "label": part_label,
                "regex": None,                       # NEW
                "example": "",                       # NEW
                "originId": origin_id,
                "originType": "ATTRIBUTE",
                "regexOutput": "",                   # NEW
            }
        ],
    },
})
```

Field ordering in HoL places `example` after `usage`/`listId` and
before `attributeExpression`, and places `regex`, `example`,
`regexOutput` in that order on expressionParts (label, regex,
example, originId, originType, regexOutput). Match this order to
keep byte-level diffs narrow for future comparison, though JSON
parsers do not require it.

## Verification plan

1. Apply renderer fix.
2. Re-run `python3 -m vcfops_managementpacks render-export
   managementpacks/synology_dsm_chain1.yaml > /tmp/chain1_v2.json`.
3. Confirm the 4 chain-specific fields (`params[].example`,
   expressionParts `example/regex/regexOutput`) now appear.
4. Build .pak and re-attempt MPB Import on devel lab.
5. If still INVALID, proceed to suspect #2 (from_attribute: id →
   declare `id` as a Volume metric).
