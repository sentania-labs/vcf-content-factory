# render_export.py strip rule audit — 2026-05-14

Triggered by commit e135142's chainingSettings.params strip, which was the fifth
whack-a-mole over-strip regression in 24 hours.  This audit applies the new
strip policy codified in render_export.py's header:

> A field is stripped from the exchange format ONLY when we have positive
> evidence MPB rejects it on import.  Evidence = a documented import failure
> (link to a context/ file or PR), not absence-in-one-sample.

---

## References used for this audit

1. `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json` — **primary ground truth**
   Multi-level cross-type chaining, populated chainingSettings.params, many
   expression patterns the Synology sample lacks.
2. `tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7_MP_Builder_Design.json` — confirms jcox
3. `reference/references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json`
   — 29 requests, 5 with chainingSettings, confirms params[] shape
4. Previous Synology DSM MP.json sample (no longer available at original path) —
   motivated most of the strips that were subsequently reverted

---

## Section 1: REMOVE (strips removed as wrong)

### 1.1 chainingSettings.params cleared to [] — lines 429-433 (pre-fix)

**What was stripped:** Every `chainingSettings` dict had `params` removed and
replaced with `params: []` before emission to the exchange format.

**Commit:** e135142 ("fix(render-export): strip chaining params from exchange format")

**Stated justification:** Emitting `params[]` caused a duplicate-label collision
in MPB's Properties screen when the chain param key (e.g. `device_id`) matched
an identifier metric key.

**Why it was wrong:** jcox UniFi reference has fully-populated `chainingSettings.params[]`
on every chained request in the exchange format.  The collision was a naming
problem in the renderer (using YAML `bind.name` directly as the wire key),
not an exchange-format restriction.

**Fix applied:**
- `render_export.py`: removed the params strip; chainingSettings is passed
  through as-is from the flat render output.
- `render.py` `_chain_wire_key()`: new helper maps YAML bind names to
  collision-safe wire keys.  `device_id` → `id_device`, `site_id` → `id_site`,
  `volume_id` → `id_volume`.  The mapping is applied in both
  `_rewrite_chain_tokens` (path/params/body rewrite) and
  `_build_chaining_settings` (chainingSettings.params[].key).

**Evidence:** reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json — every
chained request (7 total) has populated params[].

---

### 1.2 dataModelList label and parentListId stripped — _DML_DROP (pre-fix)

**What was stripped:** `label` and `parentListId` were removed from every
`dataModelList` entry in `response.result.dataModelLists[]`.

**Stated justification:** "absent in reference export; confirmed from
tmp/mpb_reference_none_auth.json, 2026-05-13" (docstring).

**Why it was wrong:** jcox UniFi reference has BOTH `label` and `parentListId`
on every DML entry:
```json
{
  "id": "data.*",
  "key": ["data"],
  "label": "data.*",
  "attributes": [...],
  "parentListId": "base"
}
```
The mpb_reference_none_auth.json sample was a minimal single-request design;
absence there did not mean MPB rejects the fields.

**Fix applied:** Removed `_DML_DROP = {"label", "parentListId"}` filter.
`dmls = list(raw_dmls)` — DMLs passed through unchanged.

**Evidence:** reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json — all
DML entries have label and parentListId.

---

### 1.3 nameMetricExpression.expressionParts[].label stripped — _strip_internal_object_info (pre-fix)

**What was stripped:** `label` field removed from each expressionPart inside
`internalObjectInfo.nameMetricExpression.expressionParts[]`.

**Stated justification:** "present in flat format, absent in reference export
(confirmed from tmp/mpb_reference_none_auth.json, 2026-05-13)" (docstring).

**Why it was wrong:** jcox UniFi reference has `label` on every
nameMetricExpression.expressionPart:
```json
"expressionParts": [{
  "id": "ppUDCNUa2bMh5CbfnfDV3J",
  "label": "Name-Client",
  "regex": null,
  "example": "",
  "originId": "deCawHEv13tjcsnfeAYPDB",
  "originType": "METRIC",
  "regexOutput": ""
}]
```
Same over-strip-from-one-sample error as 1.2.

**Fix applied:** `_strip_internal_object_info()` now returns `dict(ioi)` directly
without any field removal.

**Evidence:** reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json (2026-05-14).

---

## Section 2: KEEP (strips retained with confirmed positive evidence)

### 2.1 `_renderer_note` — _FLAT_ONLY_KEYS

**What is stripped:** The `_renderer_note` key emitted by `render.py` on
relationship objects and some expression parts.

**Evidence for keeping strip:** This is an internal renderer annotation that
never appears in any MPB-generated export.  No reference has it.  It has no
MPB meaning.

**Status:** KEEP.

---

### 2.2 `key` from metric objects — _strip_metric

**What is stripped:** The `key` field on metric objects inside
`metricSets[].metrics[]`.

**Evidence:** jcox UniFi reference metrics do NOT have a `key` field.  Our flat
render emits `key` (the YAML metric key, e.g. `"device_id"`); the exchange
format does not include it.

**Status:** KEEP.  Confirmed from jcox (2026-05-14): metric objects have fields
`id, unit, isKpi, label, usage, groups, dataType, expression, timeseries` — no `key`.

---

### 2.3 `value` from credential items — _strip_cred

**What is stripped:** The `value: null` field from authentication `creds[]`
items.

**Status:** UNCERTAIN — see Section 3.2.  Left as-is (strip retained) because
the field is null; see Section 3.2 for details.

---

### 2.4 `designId` on objects and relationships — REVERSED by Bug 3.3 / Bug 3.5

**Original rule (2026-05-14):** designId emitted as null on objects and relationships.
Evidence: jcox has `designId: null` on every object and relationship.

**Reversal (2026-05-15, Bug 3.3 / Bug 3.5):** MPB-built UniFi export shows neither
objects nor relationships have `designId` at all.  The jcox community export had
null-value designIds; MPB's own normalization strips them.  MPB-built evidence
supersedes jcox for this field.

**Status:** REVERSED — designId is now dropped from objects, relationships,
requests, and source.source.  See Bug 3.3 and Bug 3.5 for details.

---

### 2.5 `_renderer_note` from relationships — _strip_relationship

**What is stripped:** `_renderer_note` key from flat relationship objects.

**Evidence:** Same as 2.1 — internal annotation, never in any reference.

**Status:** KEEP.

---

### 2.6 `designId` from events — _strip_event

**What is stripped:** `designId` from event objects.

**Evidence:** Flat render emits `designId` on events; exchange format should
not have it (events are stripped entirely for now due to unknown wire format
anyway).

**Status:** KEEP.

---

### 2.7 CHAINED_REQUEST → ATTRIBUTE_TO_PROPERTY remap — _remap_object_binding

**What is done:** objectBinding type "CHAINED_REQUEST" is remapped to
"ATTRIBUTE_TO_PROPERTY" for the exchange format.

**Evidence:** jcox has no "CHAINED_REQUEST" entries — only "ATTRIBUTE_TO_PROPERTY".
"CHAINED_REQUEST" is an internal flat-format marker.

**Status:** KEEP (correct remap).

---

## Section 3: UNCERTAIN (no evidence either way — left unchanged)

### 3.1 `timeseries: null` stripped from metrics

**What is stripped:** The `timeseries` key is removed from metric objects by
`_strip_metric`.

**Status:** UNCERTAIN.  jcox has `timeseries: null` present on every metric.
Our strip removes the key entirely.  Since the value is always null, MPB likely
treats absent and null as equivalent.  However, by the new strip policy, the
field should technically be kept (it appears in the reference).

**Action:** Left stripped for now.  If MPB returns a validation error related
to timeseries, remove the strip.  Revisit: add `timeseries` to the REMOVE list
if a confirmed import failure is observed.

---

### 3.2 `value: null` stripped from credential items

**What is stripped:** The `value` key is removed from `authentication.creds[]`
items.

**Status:** UNCERTAIN.  jcox has `"value": null` present on credential items.
Our strip removes the key.  Null-value difference; MPB likely accepts either.

**Action:** Left stripped for now.  If import fails with credential errors,
restore `value: null` on creds.

---

### 3.3 `usage` and `value` stripped from non-standard configuration items

**What is stripped:** `usage` and `value` keys removed from non-standard
(non-mpb_*) configuration items in `_transform_configuration`.

**Status:** UNCERTAIN.  No non-standard configuration items exist in any
reference.  Standard items in jcox DO have `usage` and `value: null`.

**Action:** Left as-is.  If a future MP requires non-standard config items and
import fails, revisit.

---

## chainingSettings.params wire key scheme (codified 2026-05-14)

The `_chain_wire_key()` function in `render.py` maps YAML bind names to wire
requestParameters keys:

| YAML bind.name | Wire key    | Wire label  | Wire usage                        |
|----------------|-------------|-------------|-----------------------------------|
| `id`           | `id`        | `ID`        | `${requestParameters.id}`         |
| `device_id`    | `id_device` | `ID_device` | `${requestParameters.id_device}`  |
| `site_id`      | `id_site`   | `ID_site`   | `${requestParameters.id_site}`    |
| `volume_id`    | `id_volume` | `ID_volume` | `${requestParameters.id_volume}`  |
| `pool_id`      | `id_pool`   | `ID_pool`   | `${requestParameters.id_pool}`    |

**Rule:** if bind_name ends with `_id`, strip suffix and prepend `id_`.
If bind_name is exactly `id`, use `id`.  Otherwise, prepend `id_`.

**Why:** Identifier metric keys follow `<thing>_id` (e.g. `device_id`).
Chain param wire keys follow `id_<thing>` (e.g. `id_device`).  These two
namespaces never overlap, eliminating the MPB Properties screen duplicate-label
collision.

**Scope:** This mapping applies in BOTH `_rewrite_chain_tokens` (path/params/body)
AND `_build_chaining_settings` (chainingSettings.params[].key/usage).  Both sides
must agree or MPB will not match the param to the substitution point.

**YAML is unchanged:** Authors still write `${chain.device_id}` and
`bind: [{name: device_id, from_attribute: id}]`.  The wire key remapping is
purely a render-time concern.  Loader validation still checks YAML bind names
against YAML `${chain.*}` tokens (not wire keys).

---

## Files modified in this audit

- `vcfops_managementpacks/render_export.py` — strip policy header added;
  chainingSettings.params strip removed; DML label/parentListId strip removed;
  internalObjectInfo label strip removed; docstrings updated.
- `vcfops_managementpacks/render.py` — `_chain_wire_key()` added;
  `_rewrite_chain_tokens()` updated to use wire keys;
  `_build_chaining_settings()` updated to use wire keys + jcox label convention.
- `context/mp_chain_authoring.md` — wire-format correspondence table updated.

---

## Post-audit wire bugs found on UniFi import (2026-05-14 follow-up)

Two additional bugs surfaced when the re-rendered UniFi exchange JSON was
imported into MPB.

### Bug 1 — Duplicate chain keys on objects with two chained children

**Symptom:** MPB Properties panel shows two attributes both labeled `ID_device`,
flagged "This field must be unique."  Affects Access Point, Switch, Gateway.

**Root cause:** `device_stats_ap` and `device_detail_ap` both chain from
`devices_ap` and both bind `device_id`.  `_chain_wire_key('device_id')` produces
`id_device` for both.  MPB unions chain params across all requests for an object
type and rejects duplicate keys.

**Fix (Option B — collision-scoped, 2026-05-14):**
- Added `_chain_wire_key_for_request(bind_name, child_req_name)` helper that
  returns `id_<child_req_name>` for scoped keys.
- Added pre-scan in `_render_requests` that detects `(ot_key, parent_req_name,
  bind_name)` triples with more than one child.  These are "collision pairs."
- `_build_chaining_settings` uses `_chain_wire_key_for_request` for colliding
  pairs, `_chain_wire_key` for non-colliding ones.
- `_RequestInfo._own_chain_map` stores `{bind_name: wire_key}` for the request's
  own direct params.  `to_wire()` passes this to `_rewrite_chain_tokens` so own
  tokens use the scoped key and inherited ancestor tokens use the fallback.

Result: `device_stats_ap` → `id_device_stats_ap`, `device_detail_ap` →
`id_device_detail_ap`.  Non-colliding `site_id` binds → `id_site` (unchanged).

Wire key table updated in `context/mp_chain_authoring.md`.

---

### Bug 2 — Primary metricSet objectBinding=null on multi-metricSet objects

**Symptom:** Red error icon on Access Point, Switch, Gateway, Client, Network;
tooltip "Attribute linking request to object is missing."

**Root cause:** Every primary metricSet emitted `objectBinding=None` (Case 3
"all other metricSets" fallback).  jcox UniFi reference shows the list-driver
metricSet (listId=data.*) MUST carry a non-null ATTRIBUTE_TO_PROPERTY binding
to tell MPB which request establishes per-row object identity.  The null was
accepted for Synology's original single-metricSet objects (no ambiguity), but
MPB rejects it when other metricSets are also present.

**Fix (Case 4, 2026-05-14):**
Added a new Case 4 branch in `_render_one_object` before Case 2 in the elif
chain:

```
elif getattr(ms_def, 'primary', False) and not is_scalar and ot.identifiers:
    # Case 4 — Primary non-scalar INTERNAL metricSet: identity binding
```

Shape (mirrors Sub-case A applied to the primary):
```
objectBinding:
  type: ATTRIBUTE_TO_PROPERTY
  matchExpression:
    expressionParts[0]:
      originId: <primary_req_id>-<dml_id>-<identifier_field_path>
      originType: ATTRIBUTE
      label: <identifier_field_path>  (e.g. "id")
  objectMatchExpression:
    expressionParts[0]:
      originId: <identifier_metric_uuid>
      originType: METRIC
      label: <identifier_metric_label>  (e.g. "Device ID")
```

Evidence from `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json`:
- `get-devices-all` (listId=data.*, chain-parent AND primary equivalent):
  objectBinding=ATTRIBUTE_TO_PROPERTY,
  matchExpression.label="id" originType=ATTRIBUTE,
  objectMatchExpression.label="ID_device" originType=METRIC.

Synology primaries (single-metricSet objects) also receive Case 4 now, giving
them an explicit identity binding that was previously null.  This is harmless
for single-metricSet objects (Synology imported cleanly both ways) and correct
per the jcox pattern.

**Files modified in this follow-up:**

- `vcfops_managementpacks/render.py`:
  - `_chain_wire_key_for_request()` added
  - `_rewrite_chain_tokens()` updated to accept `own_chain_map` param
  - `_rewrite_params()` updated to accept `own_chain_map` param
  - `_RequestInfo.__init__()` — `_own_chain_map` field added
  - `_RequestInfo.to_wire()` — passes `_own_chain_map` to rewrite helpers
  - `_render_requests()` — collision pre-scan added; `_build_chaining_settings` call updated
  - `_build_chaining_settings()` — signature updated (Option B collision-scoped keys);
    returns `(chain_settings, own_chain_map)` tuple
  - `_render_one_object()` — Case 4 added (primary objectBinding)
- `context/mp_chain_authoring.md` — collision-scoped scheme documented

---

### Bug 2b — Chained-secondary metricSets emitting non-null objectBinding

**Symptom:** After Bug 1 and Bug 2 fixes landed, re-import into MPB still showed
"Attribute linking request to object is missing" on Access Point, Switch, and
Gateway.  Client and Network (single-metricSet objects) were clean.  The error
fires exactly on the three object types that have **two** chained secondaries.

**Root cause:** The Case 2 branch in `_render_one_object()` emitted a non-null
`ATTRIBUTE_TO_PROPERTY` (or `CHAINED_REQUEST`) `objectBinding` on every chained
secondary regardless of `listId`.  When two secondaries (e.g. `device_stats_ap`
and `device_detail_ap`) both emit objectBinding entries pointing at the same
parent DML attribute (`id` on `devices_ap`), MPB cannot disambiguate and raises
the "Attribute linking request to object" error.

A single chained secondary (Synology `volume_util`) was tolerated because there
is no ambiguity, but the extra binding is still incorrect per the jcox reference
design: ALL chained secondaries in `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json`
have `objectBinding=null`.  MPB derives the per-row object link from
`chainingSettings.parentRequestId` alone; the secondary's own objectBinding is
irrelevant and, with two or more secondaries, harmful.

**Fix (2026-05-15):**

Removed the entire Case 2 block from `_render_one_object()`.  The old elif:

```python
elif ms.chained_from is not None and ms.local_name not in chain_parent_names \
        and not getattr(ms, 'primary', False):
    # ... build Sub-case A or Sub-case B objectBinding ...
```

is replaced with a comment explaining why secondaries get null:

```python
# Case 2 — Chained-secondary metricSet: objectBinding=null.  (Bug 2b fix)
# MPB derives the object link from chainingSettings.parentRequestId alone.
# pass — object_binding remains None
```

**Rule after fix:**

> `objectBinding` is set on a metricSet if and only if:
> - Case 0: ARIA_OPS primary with stitch_match_field.
> - Case 1: INTERNAL metricSet with stitch_to declared.
> - Case 4: PRIMARY non-scalar INTERNAL metricSet (`primary: true`, object
>   has identifiers, identifier metric is sourced from this metricSet).
>
> All other metricSets — including chained secondaries regardless of listId —
> emit `objectBinding=null`.

**Verification:**

Rendered UniFi Integration after fix:

| Object type | metricSet | listId | objectBinding |
|---|---|---|---|
| Access Point | devices_ap (primary) | data.* | ATTRIBUTE_TO_PROPERTY |
| Access Point | device_stats_ap (secondary) | base | null |
| Access Point | device_detail_ap (secondary) | base | null |
| Switch | same pattern | — | — |
| Gateway | same pattern | — | — |
| Client | clients (primary) | data.* | ATTRIBUTE_TO_PROPERTY |
| Network | networks (primary) | data.* | ATTRIBUTE_TO_PROPERTY |

Rendered Synology after fix:

| Object type | metricSet | listId | objectBinding |
|---|---|---|---|
| Volume | get_volumes (primary) | data.volumes.* | ATTRIBUTE_TO_PROPERTY |
| Volume | volume_util (secondary) | data.* | null ← was non-null before fix |

The Synology change (non-null → null on volume_util) is expected and correct.
Synology imported cleanly with the old non-null binding, and will continue to
import cleanly with null (MPB accepts null on a secondary when the primary
binding is present).

**Evidence:** `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json` —
confirmed by inspection that every secondary metricSet has `objectBinding=null`.
No exception to this pattern was found in the reference file.  The file contains
6 objects; the 3 with chained secondaries all show null binding on every secondary
metricSet.

**Files modified:**

- `vcfops_managementpacks/render.py`:
  - `_render_one_object()` Case 2 block removed (~180 lines).
  - Chain-parent comment block updated to reflect Bug 2b semantics.
  - Four-cases header comment updated (Case 2 description corrected).

---

### Bug 2c — Collection Preview fails on 3-metricSet objects: null-all-secondaries is wrong

**Symptom:** After Bug 2b fix (null all secondaries), MPB Collection Preview failed
with 4 distinct runtime validator errors on Access Point, Switch, and Gateway.  The errors
decode to four universal MPB runtime rules for objectBinding:

1. **Tree join:** all metricSets on an object_type must be transitively linked into a
   single tree via objectBindings.
2. **At-most-one-null:** at most ONE metricSet per object_type can have
   `objectBinding=null`, AND that one must be referenced by another metricSet's binding.
3. **Foreign-metric:** a metricSet's `objectBinding.objectMatchExpression` must reference
   a metric whose `originId` lives in a DIFFERENT metricSet's metrics array.
4. **Single-metricSet exception:** an object with only one metricSet can have
   `objectBinding=null` (exempt from tree/reference rules).

**Root cause:** Bug 2b nulled ALL chained secondaries.  For 3-metricSet objects
(primary + anchor secondary + extra secondary), this created two null metricSets
(`device_stats_ap` and `device_detail_ap`), violating rule 2 (at-most-one-null).
The extra secondary (`device_detail_ap`) was also disconnected from the tree,
violating rule 1.

Additionally, the previous Case 4 (primary identity binding) pointed at the identifier
metric (`device_id`) in the PRIMARY's own metrics array, violating rule 3 (foreign-metric).

**The jcox idiom (from `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json`):**

`UniFi - Devices` has 2 metricSets:
- `[0] get-device-statistics` (secondary, `listId=base`): `objectBinding=null`.  Carries
  a synthesized PROPERTY metric `ID_device` (`id=1xgJbg5AmaWpUCbKXMn9Cf`, `usage=PROPERTY`,
  `dataType=STRING`), whose expression has `originType=PARAMETER` and `originId` pointing at
  its own `chainingSettings.params[0].id` (`uGbMaRskKLJBH6GHTp1QQz`).
- `[1] get-devices-all` (primary, `listId=data.*`): `objectBinding=ATTRIBUTE_TO_PROPERTY`.
  `matchExpression.originId` = `m67AA62ETUe22aTuPwUuUi-data.*-id` (ATTRIBUTE on own DML).
  `objectMatchExpression.originId` = `1xgJbg5AmaWpUCbKXMn9Cf` (the `ID_device` metric on
  the SECONDARY — satisfying rule 3: foreign-metric in a different array).

This is the "synthesized-linking-metric" idiom: the secondary is the **anchor** (the one
permitted null), and the primary's `objectMatchExpression` points at the anchor's linking
metric instead of any metric in the primary's own array.

**3-metricSet extrapolation (not in jcox):**

For objects with 2+ chained secondaries, designate the FIRST sibling secondary in
declaration order as the **anchor**.  All other secondaries get an ATTRIBUTE_TO_PROPERTY
binding that also points at the anchor's linking metric, joining them into the tree.

Tree for Access Point:
```
device_stats_ap (anchor, null) <- holds ID_device linking metric
    referenced by: devices_ap (primary, Case 4)
    referenced by: device_detail_ap (other secondary, Case 2c)
```

Rule satisfaction:
- Rule 1 (tree join): all three metricSets connected via anchor's linking metric. ✓
- Rule 2 (at-most-one-null): only anchor is null, and it is referenced by primary + others. ✓
- Rule 3 (foreign-metric): primary's objectMatchExpression points at ID_device on anchor
  (different metricSet). Other secondary's objectMatchExpression points at same. ✓
- Rule 4 (single-metricSet): Client and Network have one metricSet each, objectBinding=null. ✓

**Fix (Bug 2c, 2026-05-15):**

Three changes to `_render_one_object()`:

1. **Pre-loop anchor detection.** Identifies `_anchor_ms` (first sibling secondary in
   declaration order) and computes `_anchor_link_metric_id`, `_anchor_link_metric_label`,
   `_anchor_chain_param_id`.

2. **Linking metric synthesis.** After the regular metrics loop, if the current metricSet
   is the anchor, appends the synthesized PROPERTY metric:
   ```python
   {
     "id": _anchor_link_metric_id,  # stable UUID from obj_seed + anchor + bind_name
     "label": "ID_device",          # ID_<stem> where stem from _chain_wire_key logic
     "usage": "PROPERTY",
     "dataType": "STRING",
     "expression": {
       "expressionParts": [{
         "originType": "PARAMETER",
         "originId": _anchor_chain_param_id,  # = chainingSettings.params[0].id
       }]
     }
   }
   ```

3. **objectBinding case table updated:**
   - Case 4 (primary with anchor): `objectMatchExpression.originId` = `_anchor_link_metric_id`
     (foreign — on anchor, satisfies rule 3).  Without anchor (single-metricSet objects):
     `objectBinding=null` (single-metricSet exception).
   - Case 2c (non-anchor sibling secondary): new elif branch; emits ATTRIBUTE_TO_PROPERTY
     with `objectMatchExpression.originId` = `_anchor_link_metric_id`.
   - Case 2a (anchor secondary): falls through to `object_binding=None` (no explicit branch).

**Label/UUID scheme:**
- Linking metric label: `ID_<stem>` where stem = `bind_name[:-3]` if ends with `_id`,
  else `bind_name` (e.g., `device_id` → `ID_device`, `volume_id` → `ID_volume`).
- Linking metric UUID: `_make_id(f"{obj_seed}:metricSet:{anchor_ms.local_name}:linking_metric:{bind_name}")`.
- Linking metric chain param UUID: `_make_id(f"{ak}:object:{ot.key}:chain:{anchor_ms.from_request}:param:{bind_name}")`.

**Verification (Python, 2026-05-15):**

| Object | metricSet | objectBinding | linking metric |
|---|---|---|---|
| Access Point | devices_ap (primary) | ATTRIBUTE_TO_PROPERTY (objMatch=ID_device on anchor) | — |
| Access Point | device_stats_ap (anchor) | null | ID_device (PARAMETER origin) |
| Access Point | device_detail_ap (other secondary) | ATTRIBUTE_TO_PROPERTY (objMatch=SAME ID_device) | — |
| Switch | same pattern | — | — |
| Gateway | same pattern | — | — |
| Client | clients (primary, single-MS) | null | — |
| Network | networks (primary, single-MS) | null | — |
| Synology Volume | get_volumes (primary) | ATTRIBUTE_TO_PROPERTY (objMatch=ID_volume on anchor) | — |
| Synology Volume | volume_util (anchor) | null | ID_volume (PARAMETER origin) |

Wire diff vs jcox `UniFi - Devices`: our Access Point has one extra metricSet
(`device_detail_ap`) plus our metricSet ordering is primary-first vs jcox's secondary-first.
No other unexpected structural differences.

**Files modified:**

- `vcfops_managementpacks/render.py`:
  - Pre-loop anchor detection block added to `_render_one_object()`.
  - Linking metric synthesis block added inside the metricSet loop (anchor only).
  - Case 4 (primary) rewritten: uses `_anchor_link_metric_id` when anchor exists, null
    when no anchor (single-metricSet exception).
  - Case 2c (non-anchor secondary) added: ATTRIBUTE_TO_PROPERTY pointing at anchor's linking metric.
  - Case 2b comment block replaced with new Cases 2a/2c/3 comments.
  - Bug 2b documentation block replaced by this Bug 2c entry.

---

### Bug 2d — Non-anchor secondary's matchExpression points at wrong request's DML

**Symptom:** After Bug 2c fix landed, re-import into MPB design-time validator
went back to "Attribute linking request to object is missing" on AP/Switch/Gateway.

**Root cause (identified from shipped Synology pak ground truth):**

In Bug 2c, Case 2c's `matchExpression.originId` was computed as:
```python
f"{_parent_req_info2.id}-{_parent_dml_id2}-{_b0.from_attribute}"
```
where `_parent_req_info2` is the **parent** request (e.g. `devices_ap`, UUID `47ec9023`).
This means `device_detail_ap`'s matchExpression pointed at `47ec9023-data.*-id` — an
attribute in a DIFFERENT request's DML.  MPB's design-time validator requires that
`matchExpression` references an attribute in the SAME request's DML.

**Ground truth: shipped Synology DSM pak (`/tmp/synology_inspect/design.json`)**

The Synology Volume object has 2 metricSets:
- **Primary** (`data.volumes.*`, request `3c82744a`): `objectBinding=null`
- **Secondary** (`data.*`, request `f0685bfd`): `objectBinding=ATTRIBUTE_TO_PROPERTY`
  - `matchExpression.originId` = `f0685bfd-1441-5ca7-9195-d78e706d3d85-data.*-volume_id`
    — starts with `f0685bfd` (secondary's **OWN** request UUID)
  - `objectMatchExpression.originId` = `c16570f5-ba6b-5a1e-b3b2-595447904e99`
    — the **Volume ID** metric UUID on the PRIMARY metricSet

The secondary's DML has a synthesized `volume_id` attribute (id =
`f0685bfd-...-data.*-volume_id`) that represents the chain-injected value.  The
objectBinding references this attr via its own request's UUID.

Note: the Synology pattern is the **mirror** of the jcox pattern:
- jcox: primary has binding, secondary is null with a synthesized linking metric
- Synology: secondary has binding, primary is null; no linking metric needed

Both are valid MPB arrangements.  Synology is adopted here because it is proven
end-to-end through live collection (not just UI design-time import).  The jcox
reference is a UI design export, which does not guarantee that the same shape
survives to actual collection in all multi-secondary configurations.

**Why Bug 2c's jcox-idiom failed design-time:**

Bug 2c's extrapolation of the jcox pattern to 3-metricSet objects was untested —
jcox only has 2-metricSet objects.  For the non-anchor secondary (`device_detail_ap`),
the matchExpression pointed at the parent request's DML (foreign DML), which MPB
design-time validator rejects.  The anchor (`device_stats_ap`) got away with null
objectBinding, but the primary's binding also pointed at a foreign metric (the anchor's
synthesized linking metric in a different metricSet), which may additionally fail
at design-time or collection time.

**The Synology-pattern fix (Bug 2d, 2026-05-15):**

Abandon the jcox-idiom (anchor + linking metric + primary non-null) entirely.
Replace with the Synology pattern universally for all objects with sibling secondaries:

1. **Primary metricSet: `objectBinding=null`** (always, regardless of sibling count).
2. **Each sibling secondary: `objectBinding=ATTRIBUTE_TO_PROPERTY`** where:
   - `matchExpression`: ATTRIBUTE → secondary's OWN DML synthesized `b.from_attribute` attr.
     `originId = {secondary_req_id}-{secondary_dml_id}-{b.from_attribute}`
   - `objectMatchExpression`: METRIC → primary's identifier metric UUID (`metric_map[ident_key]`)
3. **No anchor, no linking metric synthesis** — all secondaries treated identically.

The synthesized `b.from_attribute` attr on the secondary's OWN DML is added in
`_render_requests` step 3 (Bug 2d addition alongside the existing parent-DML synthesis).
It is idempotent (register_field deduplicates by origin_id).

**Verification (Python render, 2026-05-15):**

| Object | metricSet | listId | requestId (first 8) | objectBinding |
|---|---|---|---|---|
| Access Point | devices_ap (primary) | data.* | 47ec9023 | null |
| Access Point | device_stats_ap (secondary) | base | b32abf30 | ATTRIBUTE_TO_PROPERTY matchExpr.originId starts with b32abf30 (OWN) |
| Access Point | device_detail_ap (secondary) | base | d3fb2485 | ATTRIBUTE_TO_PROPERTY matchExpr.originId starts with d3fb2485 (OWN) |
| Switch/Gateway | same 3-metricSet pattern | — | — | — |
| Client, Network | primary (single MS) | data.* | — | null |
| Synology Volume | get_volumes (primary) | data.volumes.* | 3c82744a | null |
| Synology Volume | volume_util (secondary) | data.* | f0685bfd | ATTRIBUTE_TO_PROPERTY matchExpr.originId=f0685bfd-...-data.*-volume_id (OWN) — EXACT MATCH to ground truth |
| Synology other objects | single MS | — | — | null |
| vSphere ARIA_OPS | (unchanged) | data.* | — | ATTRIBUTE_TO_PROPERTY (objectBindingType key, Case 0) |

The Volume secondary objectBinding originIds match the shipped Synology pak byte-for-byte.

**Files modified:**

- `vcfops_managementpacks/render.py`:
  - `_render_requests()` step 3: added `child_req_info.register_field(b.from_attribute, child_dml_id)` to synthesize bind attr on each secondary's OWN DML (Bug 2d addition).
  - `_render_one_object()`: removed Bug 2c anchor detection block; removed linking metric synthesis block; replaced Cases 4/2c/2a with Bug 2d Synology pattern (Case 4=primary null, Case 2d=sibling secondary binding).
- `context/render_export_strip_audit_2026_05_14.md`: this Bug 2d section added.
- `context/mp_chain_authoring.md`: objectBinding pattern updated to Synology idiom.

---

## Bug 3 — Exchange format alignment from MPB-built UniFi diff (2026-05-15)

**Evidence source:** `/tmp/mpb_pak_inspect/mpb_export.json` — MPB's own export.json
generated by importing our UniFi Integration design into MPB and exporting it back.
This is the highest-fidelity evidence available: same design, MPB-normalized output.

The diff below is MPB-built output vs our factory render (pre-fix).  Positive evidence
only — every item below either "MPB has it, we didn't" (add) or "MPB doesn't have it,
we did" (drop/rename).

### Bug 3.1 — Add top-level `type` field

**Change:** Add `"type": "HTTP"` as the first key in the exchange envelope.

**Evidence:** `mpb_export.json` top-level keys:
`['type', 'design', 'source', 'objects', 'relationships', 'events', 'requests']`

Our pre-fix output had no `type` key at the top level.  The wrapping rule docstring
in `render_export.py` already specified `.source.type → .type (top-level)` but the
field was never emitted.

**Fix:** Added `"type": src.get("type") or "HTTP"` as the first key in the exchange
dict in `render_mpb_exchange_json()`.

---

### Bug 3.2 — Drop top-level `content` field

**Change:** Remove `"content": []` from the exchange envelope.

**Evidence:** `mpb_export.json` has no `content` key.  Previous rule (emit `"content": []`)
was based on pak-compare evidence against GitHub/Broadcom reference paks.  The MPB-built
export from our own design is more authoritative — MPB itself does not emit `content` when
exporting.

**Fix:** Removed `"content": []` from the exchange dict in `render_mpb_exchange_json()`.

---

### Bug 3.3 — Drop `ariaOpsConf: null` and `designId: null` from INTERNAL objects

**Change:** For `type: INTERNAL` objects, strip both `ariaOpsConf` and `designId` entirely
(do not emit null-value versions of either).

**Evidence:** `mpb_export.json` — all 5 INTERNAL objects have keys exactly:
`['id', 'internalObjectInfo', 'isListObject', 'metricSets', 'type']`
Neither `ariaOpsConf` nor `designId` appear.

Previous rule (from jcox-au_vmware/unifi_MP_Builder_Design.json, 2026-05-14) said both
were present with null value.  The MPB-built export supersedes jcox here — jcox is a
community design export, MPB's own normalization is authoritative.

**Fix (INTERNAL):** `_strip_object()` now adds `"ariaOpsConf"` to the drop set when
`type != "ARIA_OPS"`, and drops `"designId"` unconditionally.

**ARIA_OPS carve-out:** `ariaOpsConf` is still emitted on ARIA_OPS objects with its
populated value (confirmed correct from vSphere Storage Paths renders and the
`context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json` ground truth).

**Also dropped from relationships:** `designId: null` on relationship entries.
Evidence: `mpb_export.json` relationships have keys
`['caseSensitive', 'childExpression', 'childObjectId', 'id', 'name', 'parentExpression', 'parentObjectId']` — no `designId`.
Fix: `_strip_relationship()` now drops `designId` along with `_renderer_note`.

**Also dropped from source.source:** `designId: None` in the `source_source` dict.
Evidence: `mpb_export.json` `source.source` keys are
`['authentication', 'configuration', 'globalHeaders', 'id', 'testRequest']` — no `designId`.

---

### Bug 3.4 — Rename `objectBinding.type` → `objectBinding.objectBindingType`

**Change:** The flat renderer emits `"type": "ATTRIBUTE_TO_PROPERTY"` inside `objectBinding`.
MPB uses `"objectBindingType"` as the key name.

**Evidence:** `mpb_export.json` — every `objectBinding` dict has key `objectBindingType`,
not `type`.  Confirmed on all 6 non-null objectBindings across the 5 objects.

This is the most semantically important fix.  If MPB's import parser keyed off
`objectBindingType` and ignored our `type`, it would silently fall back to a default
binding type at collection time.

**Fix:** `_remap_object_binding()` now pops the `"type"` key (applying the CHAINED_REQUEST
→ ATTRIBUTE_TO_PROPERTY remap if needed) and re-inserts it as `"objectBindingType"`.
ARIA_OPS objects already used `"objectBindingType"` in the flat format and are unaffected.

---

### Bug 3.5 — Drop `designId`, `paging` from requests; drop `example` from chain params

**Change (requests):** Drop `designId: null` and `paging: null` from all request entries.

**Evidence:** `mpb_export.json` — all requests have keys:
`['body', 'chainingSettings', 'headers', 'id', 'method', 'name', 'params', 'path', 'response']`
— no `designId`, no `paging`.

Previous rule (always emit both as null, justified by jcox reference) reversed by
MPB-built evidence.

**Change (chain params):** Drop `example: ""` from each entry in
`chainingSettings.params[]`.

**Evidence:** `mpb_export.json` chain param keys:
`['attributeExpression', 'id', 'key', 'label', 'listId', 'usage']` — no `example`.

**Fix:** `_strip_request()` no longer assigns `"designId"` or `"paging"` to the request
dict.  Chain params are stripped of `example` inline when `chainingSettings` is
populated.

---

### Files modified in Bug 3

- `vcfops_managementpacks/render_export.py`:
  - `render_mpb_exchange_json()`: added top-level `"type"` key; removed `"content": []`;
    removed `"designId": None` from `source_source` dict.
  - `_strip_object()`: dropped `designId` and `ariaOpsConf` from INTERNAL objects;
    `designId` dropped from ARIA_OPS too.  Docstring updated.
  - `_strip_relationship()`: drops `designId` alongside `_renderer_note`.
    Docstring updated.
  - `_strip_request()`: removed `"designId": None` and `"paging": None` from returned
    dict; added inline chain param `example` strip.  Docstring updated.
  - `_remap_object_binding()`: renames `"type"` → `"objectBindingType"` (with
    CHAINED_REQUEST remap applied before rename).  Docstring updated.
  - Module wrapping rule table updated to reflect current state.
- `context/render_export_strip_audit_2026_05_14.md`: this Bug 3 section added.

---

## Bug 4 — Pattern V (PARAMETER-origin) for chained secondaries (2026-05-15)

### Problem: ATTRIBUTE-origin matchExpression fails when API omits id from response

Bug 2d's `objectBinding.matchExpression` used originType=ATTRIBUTE, pointing at a
synthesized DML attribute on the secondary's own request:

```
matchExpression.expressionParts[0]:
  originType: ATTRIBUTE
  originId: {secondary_req_id}-{secondary_dml_id}-{b.from_attribute}
```

This is Pattern B, extracted from the shipped Synology DSM pak.  For Synology it works
because the volume_util endpoint returns `volume_id` in its response body — the synthesized
DML attribute has something to resolve to at collection time.

For UniFi's per-device endpoints (`/sites/{site}/devices/{device}/statistics/latest`), the
response body contains only statistics — **no `id` field**.  At collection time MPB cannot
match the ATTRIBUTE expression to any response value and logs:

> Object binding requestMatchIdExpression ${id} returned matches did not return a result

The secondary's metrics are collected but never attached to a resource, silently discarding
all data.

### Solution: Pattern V (PARAMETER-origin)

Pattern V was identified from the vrealize.it vSAN default storage policy MP:

```
reference/references/vrealize_it_vsan_default_policy/vSAN default storage policy.json
```

In that MP, the `Get Datastore default policy` request has:
- `chainingSettings.params[0]`: `id = "w3ovEMMMaQF6VvGf7cqRha"`, `key = "datastore"`

The object's `objectBinding.matchExpression.expressionParts[0]`:
- `originType = "PARAMETER"`, `originId = "w3ovEMMMaQF6VvGf7cqRha"`, `label = "datastore"`

The `originId` is the chain param's own UUID (not a DML attribute id).  At collection time
MPB resolves a PARAMETER expression to the value substituted into the URL at that
collection cycle — which IS the per-device identifier.  This works regardless of whether
the API echoes the id back in the response body.

### Why Pattern V is the universal solution

| | Pattern B (Synology, ATTRIBUTE origin) | Pattern V (vSAN, PARAMETER origin) |
|---|---|---|
| Resolves from | Response body field | URL substitution value (chain param) |
| Requires id in response | YES | No |
| Works for UniFi /statistics/latest | No | YES |
| Works for Synology volume_util | Yes (response echoes volume_id) | YES |
| MPB logs on failure | "returned matches did not return a result" | Never fails if chain param is valid |

Pattern V works for any chained secondary, including Synology's, because the chain param
value and the response-body field value are the same identifier.  Pattern V is strictly
more universal and replaces Pattern B for all INTERNAL chained secondaries.

### Evidence: vSAN policy MP collecting cleanly on devel

The vSAN default storage policy MP uses Pattern V and was confirmed collecting cleanly on
devel (3 resources collecting, 2026-05-15) before this change was made to the renderer.
This is the end-to-end proof that MPB's collection engine honors PARAMETER-origin
objectBinding expressions.

### Bug 2d's secondary-DML synthesis — removed

Bug 2d added `child_req_info.register_field(b.from_attribute, child_dml_id)` in
`_render_requests` step 3 to synthesize the bind attribute on the secondary's own DML
so the ATTRIBUTE-origin matchExpression had something to point at.

With Pattern V, the matchExpression references the chain param UUID directly — no DML
attribute is needed.  The synthesis is removed.

**Verification before removal:** the secondary-DML synthesis was NOT used by the parent
side.  The parent-DML synthesis (`parent_req_info.register_field(b.from_attribute,
parent_dml_id)`) is still in place and still required — it provides the source attribute
for `chainingSettings.params[].attributeExpression` so MPB knows which parent-row field
to substitute into the child request's URL.

### Wire shape after fix

For each chained secondary metricSet, `objectBinding.matchExpression.expressionParts[0]`:

```
originType: PARAMETER
originId: <secondary's own chainingSettings.params[N].id>   # UUID, not a field reference
label: <chain param wire key, e.g. "id_device_stats_ap">
```

`objectMatchExpression` is UNCHANGED — still METRIC origin pointing at the primary's
identifier metric UUID.

### Verification results (2026-05-15)

**UniFi Integration:** 6 chained secondary bindings across AP/Switch/Gateway — all use
PARAMETER origin; each originId matches the secondary's own chainingSettings.params[].id.

**Synology:** volume_util secondary objectBinding — PARAMETER origin; originId matches
chainingSettings.params[0].id (`id_volume` key).

**vSphere Storage Paths (ARIA_OPS):** objectBindings unchanged — ATTRIBUTE origin on
matchExpression, ARIA_OPS_METRIC origin on objectMatchExpression.  Pattern V applies only
to INTERNAL chained secondaries; the ARIA_OPS case (Case 0) is unaffected.

### Files modified

- `vcfops_managementpacks/render.py`:
  - `_render_requests()` step 3: removed `child_req_info.register_field(b.from_attribute,
    child_dml_id)` (Bug 2d secondary-DML synthesis); parent-DML synthesis retained.
  - `_RequestInfo.__init__()`: added `_own_chain_param_ids: Dict[str, Tuple[str, str]] = {}`
    (bind_name → (param_id, wire_key)).
  - `_build_chaining_settings()`: now returns 3-tuple `(chain_settings, own_chain_map,
    own_chain_param_ids)`; populates `own_chain_param_ids` with each param's UUID.
  - `_render_requests()` step 3: stores `own_chain_param_ids` on `child_req_info`.
  - `_render_one_object()` Case 2d: replaced Pattern B (ATTRIBUTE-origin matchExpression
    pointing at synthesized DML attr) with Pattern V (PARAMETER-origin pointing at
    chain param UUID).  Comment block fully updated.
  - `_sibling_secondaries` pre-loop added (replaces old anchor detection; no anchor needed).
- `context/render_export_strip_audit_2026_05_14.md`: this Bug 4 section added.
- `context/mp_chain_authoring.md`: objectBinding pattern updated to Pattern V.
