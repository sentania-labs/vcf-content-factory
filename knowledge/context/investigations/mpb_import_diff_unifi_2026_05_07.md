# MPB import diff: factory UniFi Integration export vs jcox reference (2026-05-07)

Static diff of `tmp/unifi_integration_export.json` (factory-rendered,
fails on import) against `reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json`
(known-working MPB UI export). Cross-referenced against
`context/mpb_wire_reference/synology_nas_working_export.json` (factory-rendered,
known-working import) and three other reference packs (phpIPAM, Rubrik,
vSAN-policy).

---

## Divergences ranked by likelihood of causing import failure

### 1. `credentialType: "TOKEN"` -- LIKELY ROOT CAUSE

Our file emits `credentialType: "TOKEN"`. No known-working import uses
this value. The full evidence table:

| File | credentialType | Import result |
|---|---|---|
| jcox UniFi (reference) | `CUSTOM` | works |
| jcox phpIPAM | `BASIC` | works |
| Rubrik | `BASIC` | works |
| vSAN-policy | `BASIC` | works |
| Synology working export | `CUSTOM` | works |
| HoL GitLab-Basic | `CUSTOM` | works |
| **Our UniFi Integration** | **`TOKEN`** | **fails** |

The HoL GitLab-Basic design
(`reference/references/hol-2501-lab-files/HOL-2501-12/Module 2/GitLab-Basic.json`)
is especially relevant: it uses `credentialType: "CUSTOM"` with a
single credential injected via `Authorization: Bearer ...` global
header and `sessionSettings: null` -- functionally identical to our
http_header preset. It imports successfully.

The renderer (`render.py:805-815`) maps `http_header` preset to
`credentialType: "TOKEN"`. The jcox pack achieves the same auth
pattern (stateless X-API-Key header) using `credentialType: "CUSTOM"`
with `sessionSettings: null`. TOKEN may be an invalid enum value for
the import endpoint, or it may trigger a code path that requires
additional fields we don't provide.

**Fix hypothesis**: change `http_header` preset to emit
`credentialType: "CUSTOM"` instead of `"TOKEN"`, matching the jcox
pattern.

### 2. Top-level `"type": "HTTP"` present, `"content"` key absent

Our file has `"type": "HTTP"` at the top level and no `"content"` key.
All four reference-pack exports (jcox, phpIPAM, Rubrik, vSAN-policy)
have `"content"` and lack `"type"`. However, the Synology working
export has `"type"` and no `"content"` -- and imported successfully.

| File | Has `type` | Has `content` | Import result |
|---|---|---|---|
| jcox UniFi | no | yes (list len=1) | works |
| phpIPAM | no | yes (list len=3) | works |
| Rubrik | no | yes (list len=0) | works |
| vSAN-policy | no | yes (list len=0) | works |
| Synology working | yes | no | works |
| **Our UniFi** | **yes** | **no** | **fails** |

Since the Synology working export proves `type`-without-`content`
imports successfully, this divergence is **probably not the root
cause**. However, `content` carries embedded dashboard definitions in
jcox/phpIPAM; the import endpoint may have changed behavior for the
`type`-keyed variant between versions. Low-probability but worth
noting.

### 3. All metricSets have non-null `objectBinding` (no null chain-parent)

Our file gives every metricSet a non-null `objectBinding`. Per the
verify-time rule documented in `context/mpb_object_binding_wire_format.md`
section 8.1, exactly one metricSet per resource must have null
`objectBinding` and it must be the chain-parent.

| Object | ms[0] | ms[1] | Correct per verify rule |
|---|---|---|---|
| Access Point | non-null (points at sites data) | non-null (points at devices_ap data) | ms[0] should be null (it's ms[1]'s chain-parent) |
| Switch | non-null (points at sites data) | non-null (points at devices_switch data) | ms[0] should be null |
| Gateway | non-null (points at sites data) | non-null (points at devices_gateway data) | ms[0] should be null |

Jcox pattern: ms[0] is null, ms[1] carries objectBinding with BOTH
`matchExpression` AND `objectMatchExpression`. Our ms[1] has only
`matchExpression` (no `objectMatchExpression`).

This is a **verify-time** problem (section 8), not necessarily an
**import-time** problem. The import endpoint is documented as accepting
any objectBinding shape (section 1 of the wire format doc). However,
the ms[0] binding pointing at the `sites` request (a cross-object
chain-parent, not the within-object chain-parent) is structurally
unusual and might confuse the import parser. **Medium probability**.

### 4. Missing `design.design.id` field (absent vs null)

Our file omits `design.design.id` entirely. Jcox has `"id": null`.
The Synology working export also omits it. **Low probability** --
the working Synology export proves absent is accepted.

### 5. Missing `design.design.author` field

Our file omits `design.design.author`. Jcox has `"author": ""`.
**Low probability** -- same reasoning as above.

### 6. Missing `source.source.designId` (absent vs null)

Our file omits `source.source.designId`. Jcox has `"designId": null`.
Synology working also omits it. **Low probability**.

### 7. Missing `object.designId` and `object.ariaOpsConf` (absent vs null)

Our renderer explicitly strips these (line 417:
`drop = {"designId", "ariaOpsConf"}`). Jcox has both as `null`.
Synology working also strips them. **Low probability** -- the
Synology working export proves absent is accepted.

### 8. Missing `internalObjectInfo.id`

Our renderer explicitly strips this (line 406). Jcox has it populated
with a short-hash string. Synology working also strips it. **Low
probability**.

### 9. Missing `request.paging` and `request.designId`

Our renderer strips both. Jcox has `paging` (dict or null per
request) and `designId: null`. The Synology working export DOES
include `paging` (dict) but omits `designId`. This means our
renderer's decision to strip paging diverges from the Synology
working export -- but the Synology export imports fine without
paging being the cause. **Low probability** -- but if paging is
actually required, this would be a secondary bug.

### 10. `response` envelope stripped to minimal shape

Our file collapses `request.response` to just
`{"result": {"responseCode": 200, "dataModelLists": [...]}}`.
Jcox has a full response envelope with `id`, `log`, `status`,
`duration`, `startTime`, `endTime`, `errorMessage`, `toolkitId`,
and `result.body`, `result.headers`. The Synology working export
also uses the minimal shape and imports fine. **Low probability**.

### 11. `expressionParts` missing `example`, `regex`, `regexOutput`

Our renderer strips these fields outside `chainingSettings` context
(lines 86-124). Jcox has them on all expressionParts. The Synology
working export also lacks them. **Low probability** -- the
`_strip_flat_only_fields` function was designed around the Synology
working import succeeding.

### 12. `metrics` missing `timeseries` field

Our renderer strips `timeseries` (line 381). Jcox has it on some
metrics. Synology working also lacks it. **Low probability**.

### 13. Auth `creds[].value` field absent vs null

Our cred omits `value`. Jcox has `"value": null`. The Synology
working export's creds also omit `value`. **Low probability**.

---

## Summary of fix priority

1. **Change `credentialType` from `"TOKEN"` to `"CUSTOM"`** for the
   `http_header` auth preset. This is the only field that (a) differs
   from every known-working import and (b) is present in our file.
   This is a renderer bug in `render.py:805-815`.

2. **Fix objectBinding**: ms[0] (the chain-parent for ms[1]) should
   have `objectBinding: null`. ms[1] should carry the full binding
   with both `matchExpression` and `objectMatchExpression` (matching
   jcox's peer-stitch pattern). This is a renderer bug that will
   cause verify-time failure even if import succeeds.

3. **Consider adding `"content": []`** to the top-level envelope if
   fix #1 alone doesn't resolve the import failure. All four
   reference-pack UI exports include it.

---

## Structural comparison table

| Field path | Our value | Jcox value | Synology working | Verdict |
|---|---|---|---|---|
| (top) `type` | `"HTTP"` | absent | `"HTTP"` | OK (synology proves it) |
| (top) `content` | absent | `list[1]` | absent | OK (synology proves absent works) |
| `design.design.id` | absent | `null` | absent | OK |
| `design.design.author` | absent | `""` | absent | OK |
| `source.source.designId` | absent | `null` | absent | OK |
| `source.source.authentication.credentialType` | **`TOKEN`** | **`CUSTOM`** | `CUSTOM` | **SUSPECT** |
| `source.source.authentication.sessionSettings` | `null` | `null` | `dict` | OK (both null) |
| `object.ariaOpsConf` | absent | `null` | absent | OK |
| `object.designId` | absent | `null` | absent | OK |
| `internalObjectInfo.id` | absent | present | absent | OK |
| `metricSets[].objectBinding` | all non-null | ms[0]=null, ms[1]=full | all null | **SUSPECT (verify-time)** |
| `request.paging` | absent | present/null | present | Benign |
| `request.designId` | absent | `null` | absent | OK |
| `response` envelope | minimal | full | minimal | OK |
| `metrics[].timeseries` | absent | present | absent | OK |
| `expressionParts[].example/regex/regexOutput` | absent | present | absent | OK |
| `creds[].value` | absent | `null` | absent | OK |
