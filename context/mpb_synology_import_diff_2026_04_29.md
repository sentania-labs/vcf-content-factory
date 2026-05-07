# MPB Synology import failure — diff vs working export (2026-04-29)

Comparison of the failing factory-authored design against the
known-working community export. All findings are derived statically
from the two files (no live API calls).

- Failing: `tmp/mp-step1/synology_nas_design.json` (3,054 lines, 109 KB)
- Working: `context/mpb_wire_reference/synology_nas_working_export.json` (10,471 lines, 462 KB)

## Summary

The failing file is a **plausible MPB design at the envelope level** —
top-level keys, section shapes, list-of-wrappers, and source/auth
sub-trees all line up with the working export. Most of the reference
graph (relationships, expressions, originIds, listIds, requestIds)
resolves cleanly inside the file.

The most likely root cause of the `unknown error` toast is one of
these three structural problems, in order of severity:

1. **A "Synology NAS World" object exists with `isListObject: false`,
   `metricSets: []`, `identifierIds: []`, and `nameMetricExpression:
   null`.** This is the only object in the failing file with all
   three structurally meaningless. The working file has no
   metricSet-less objects, and every working object carries at least
   one identifier and a non-null name expression. A strict server-side
   validator that requires `nameMetricExpression != null` for any
   non-list object (or rejects empty `metricSets[]`) will trip here.
   Even if the validator is lenient, this object contributes nothing
   to the model — it is an architectural error that should not be
   shipped.

2. **`Synology Diskstation` was demoted from singleton to list
   (`isListObject: true`).** In the working file Diskstation is the
   `isListObject: false` root entity bound to three parallel
   metricSets (system / filestation / utilization). In the failing
   file, those three metricSets are still wired (correctly) but the
   object is now `isListObject: true`. List objects with multiple
   metricSets bound to different requests need a chained secondary
   request (per `context/mpb_chaining_wire_format.md` §7), and the
   failing file does not chain `filestation` or `utilization` onto
   `system`. This is a contradiction MPB may detect at import time.

3. **`volume_util` is a dangling chained request.** The failing
   `volume_util` request uses `${requestParameters.volume_id}` as a
   path parameter but has **no `chainingSettings` block**. In the
   working file, `volume_util` carries a full
   `chainingSettings` declaring `parentRequestId` = `get_volumes`,
   `baseListId` = `data.volumes.*`, and a `volume_id` parameter
   sourced from `data.volumes.*-volume_id`. Without that, the request
   graph references a request parameter with no producer.
   `mpb_chaining_wire_format.md` §6 calls a chained request not bound
   to its source a "dangling chain"; the importer may reject this or
   accept it but break at runtime.

Beyond these three, the failing file also drops the entire `paging`
sub-tree from the six requests that need it in the working file, and
contains 21 explicit `null` values in DML descriptors where the
working file simply omits those keys. Either could be ignored by a
permissive parser or rejected by a strict one.

## Top-level envelope shape

Identical. Both files have:

```
{ type, design, source, objects, relationships, events, requests }
```

with `design.design`, `source.source`, and list items wrapped in
`{"object": ...}`, `{"relationship": ...}`, `{"request": ...}`.

| Key | Working | Failing |
|---|---|---|
| `type` | `"HTTP"` | `"HTTP"` |
| `design.design.{name,type,description,version}` | matches | matches |
| `source.{source,configuration}` | both | both |
| `source.source.{id,configuration,authentication,globalHeaders,testRequest}` | all present | all present |
| `objects` count | 5 | **6** (extra rogue object) |
| `relationships` count | 3 | 3 |
| `events` count | 0 | 0 |
| `requests` count | 10 | 10 |

## Critical structural differences

### 1. Spurious "Synology NAS World" object (objects[5] in failing)

Failing `objects[5].object`:

```json
{
  "id": "d8288d29-664f-5a47-b8ea-377d792849fd",
  "type": "INTERNAL",
  "isListObject": false,
  "internalObjectInfo": {
    "icon": "default.svg",
    "identifierIds": [],
    "objectTypeLabel": "Synology NAS World",
    "nameMetricExpression": null
  },
  "metricSets": []
}
```

- `metricSets` is empty
- `identifierIds` is empty
- `nameMetricExpression` is **null** (every other object has a populated expression)
- Not referenced by any relationship (no `parentObjectId` / `childObjectId` points at it)

This object should not exist. The working file's "world" / root concept
is `Synology Diskstation` with full metricSets and identifiers.

### 2. `Synology Diskstation` is a list in failing, singleton in working

| Field | Working | Failing |
|---|---|---|
| `isListObject` | **false** | **true** |
| metricSet count | 3 | 3 |
| metricSets bound to | system, filestation, utilization | system, filestation, utilization |
| metricSets all `listId` = | `"base"` (working) | `"data.*"` (failing) |
| chainingSettings on filestation/utilization | none (singleton, OK) | none (list with multiple sources, **broken**) |

A list object with three metricSets pulling from three different
requests needs the secondary requests chained onto the primary. The
factory file kept the parallel-fanout pattern but switched the object
class. Either fix:

- demote back to `isListObject: false` and use `listId: "base"` for
  all three metricSets (matches working), or
- keep it a list, pick a primary request, and chain the other two.

The working pattern (singleton with `listId: "base"`) is the simpler
and faithful port.

### 3. `volume_util` is a dangling chained request

Failing `volume_util` carries:

```json
"params": [
  ...
  { "key": "location", "value": "${requestParameters.volume_id}" }
]
```

but the request body has **no `chainingSettings`** key. Working file
includes the full chaining declaration:

```json
"chainingSettings": {
  "id": "...",
  "parentRequestId": "<get_volumes id>",
  "baseListId": "data.volumes.*",
  "params": [
    {
      "key": "volume_id",
      "listId": "data.volumes.*",
      "attributeExpression": {
        "expressionParts": [
          { "originType": "ATTRIBUTE",
            "originId": "<get_volumes id>-data.volumes.*-volume_id",
            "label": "volume_id" }
        ]
      },
      "usage": "${requestParameters.volume_id}"
    }
  ]
}
```

Additionally: `volume_util` is **not bound to any object metricSet**
in the failing file (Volume is bound only to `get_volumes`). The
working file likewise binds Volume only to `get_volumes`, and
`volume_util` feeds metrics that the working DML chain attaches via a
`data.disk.disk.*` etc. dataModelLists — the failing file's
`volume_util` parser has only a `base` DML with **0 attributes**, so
even if the chain were declared, no attributes would be parsed.

### 4. Missing `paging` block on six requests

Working file: 6 of 10 requests carry a `paging` block (utilization,
get_volumes, storage_info, get_disks, get_storage_pools, network_info).
Failing file: **0 of 10**.

The `paging` block in the working export contains substantial nested
config including its own `response.result.dataModelLists` and `key`/
`limitParam`/`pagingParam` definitions. If the importer requires
`paging` for endpoints that produced paged data on import-time test,
this is a problem. If the importer just treats `paging` as optional,
it isn't a blocker (just a runtime regression — bigger pages might
get truncated).

### 5. 21 explicit `null` values in failing, 0 in working

| Path pattern | Count in failing | Count in working |
|---|---|---|
| `requests[].response.result.dataModelLists[].label = null` | 10 | 0 |
| `requests[].response.result.dataModelLists[].parentListId = null` | 10 | 0 |
| `objects[].internalObjectInfo.nameMetricExpression = null` | 1 | 0 |

The working file **omits** these keys when not applicable (e.g. the
`base` DML uses keys `['id', 'key', 'attributes']` only, no `label`,
no `parentListId`). The failing file emits them with explicit
`null`. Strict Jackson/Gson deserializers configured with
`FAIL_ON_INVALID_VALUES` will reject `null` where a string or
non-null object is expected.

### 6. Missing `Content-Type` header on getSession

| Field | Working | Failing |
|---|---|---|
| `source.source.authentication.sessionSettings.getSession.headers` | `[{key: "Content-Type", value: "application/json", type: "REQUIRED"}]` | `[]` |

Probably runtime-only — the global header layer carries the same
`Content-Type` — but worth restoring for parity.

### 7. `mpb_min_event_severity` defaultValue mismatch

Failing `source.configuration[mpb_min_event_severity]`:

```json
"defaultValue": "WARNING",
"options": ["Critical", "Immediate", "Warning", "Info"]
```

The default value (`"WARNING"`, all caps) does not match any option
(`"Warning"`, title case). If the importer validates that
`SINGLE_SELECTION` defaults must be one of `options`, this is a hard
error. Working file has `defaultValue: "Warning"`, which matches.

## Schema completeness

### Per-section key audit

| Section | Working keys | Failing keys | Diff |
|---|---|---|---|
| `design.design` | name, type, description, version | name, type, description, version | identical |
| `source.source` | id, configuration, authentication, globalHeaders, testRequest | id, configuration, authentication, globalHeaders, testRequest | identical |
| `source.source.configuration` | baseApiPath, customConfigs | baseApiPath, customConfigs | identical |
| `source.source.authentication` | creds, credentialType, sessionSettings | creds, credentialType, sessionSettings | identical |
| `source.source.authentication.sessionSettings` | sessionVariables, getSession, releaseSession | getSession, sessionVariables, releaseSession | identical (order differs, harmless) |
| `objects[].object` | id, type, isListObject, metricSets, internalObjectInfo | id, type, metricSets, isListObject, internalObjectInfo | identical (order differs) |
| `objects[].object.metricSets[]` | id, metrics, listId, requestId | id, listId, requestId, metrics | identical (order differs) |
| `objects[].object.metricSets[].metrics[]` | id, label, dataType, expression, isKpi, usage, unit, groups | id, unit, isKpi, label, usage, groups, dataType, expression | identical (order differs) |
| `objects[].object.internalObjectInfo` | objectTypeLabel, icon, nameMetricExpression, identifierIds | icon, identifierIds, objectTypeLabel, nameMetricExpression | identical (order differs) |
| `requests[].request` (paged) | id, name, path, method, body, headers, params, **paging**, response | id, name, path, method, body, headers, params, response | **paging missing** |
| `requests[].request` (chained: volume_util) | ..., **chainingSettings**, response | ..., response | **chainingSettings missing** |
| `requests[].request.response.result` | responseCode, dataModelLists | responseCode, dataModelLists | identical |
| `requests[].request.response.result.dataModelLists[]` (non-base) | id, label, key, attributes, parentListId | id, key, label, attributes, parentListId | identical (order differs) |
| `requests[].request.response.result.dataModelLists[]` (base) | id, key, attributes | id, key, label (=null), attributes, parentListId (=null) | **failing emits two extra null keys** |
| `relationships[].relationship` | id, name, parentObjectId, childObjectId, parentExpression, childExpression, caseSensitive | id, name, caseSensitive, childObjectId, parentObjectId, childExpression, parentExpression | identical (order differs) |
| `events[]` | empty | empty | identical |

Field-content density is dramatically different in `requests[].response.result.dataModelLists[]` — the working file has 7-24 DMLs per paged request with up to 86 attributes each; the failing file has 1-2 DMLs with at most ~18 attributes (and the `base` DML always has 0 attributes). This is a runtime signal richness gap, not necessarily an import-blocker.

## UUID hygiene

| Check | Result |
|---|---|
| All UUID-shaped strings declared as `"id"` somewhere in failing | **yes** (269 distinct, all defined) |
| UUID references resolve | **yes** (0 unresolved originIds) |
| Duplicate UUIDs in failing | **none** (the only "duplicate id" hits are non-UUID parser keys like `"base"`, `"data.*"`, which are intentional) |
| All `parentObjectId` / `childObjectId` resolve to declared objects | **yes** |
| All `requestId` in metricSets resolve to declared requests | **yes** |
| All `listId` in metricSets resolve to a DML inside the bound request | **yes** |

UUID-version distribution differs:

| Version | Working count | Failing count |
|---|---|---|
| v4 (random) | 2,256 | 1 |
| v5 (SHA-1 namespace) | 3 | 524 |

The failing file uses **deterministic UUID v5** for nearly every ID,
which is RFC-4122 compliant and should be accepted by the importer.
However:

- Two factory invocations against the same source design seed will
  produce **identical UUIDs**. If two factory packagings are imported
  into the same Ops, the second hits a primary-key collision.
  Long-term concern, not the immediate import failure.
- `mpb_chaining_wire_format.md` §8 explicitly says: "Our tooling
  should emit RFC-4122 UUIDs for consistency with the rest of the
  factory and with the Synology-family designs we are repackaging."
  v4 is the implicit assumption; v5 is non-standard within the
  factory.

## Encoding gotchas

- `design.design.description`: identical bytes in both files. The
  text contains "rootdevice", "pervolume", "perentity" without
  hyphens — that's pre-existing in the working file too. Not a smart
  quote / unicode issue (verified char-equal).
- No non-ASCII in either file's structural keys or values.

## Recommended concrete fixes

Ordered by likelihood of being the actual import blocker:

1. **Delete the "Synology NAS World" object entirely** (objects[5]
   in the failing file). It contributes nothing — empty metricSets,
   empty identifiers, null name expression, no relationships pointing
   at it. The working file has no analogue.

2. **Restore `Synology Diskstation` as `isListObject: false`** and
   change all three metricSet `listId` values from `"data.*"` to
   `"base"`. Update each bound request's parser DMLs so the
   singleton-style `base` list contains the attributes (working file
   has `system` with 25 base attributes, `filestation` with 17
   base attributes, `utilization` with 36 base attributes). This is
   a much larger change because the parser DMLs need to be rebuilt
   for each — but it matches the working architecture and removes
   the chaining problem in #3 below.

3. **Add `chainingSettings` to `volume_util` OR remove the request
   entirely.** If kept, declare `parentRequestId` = `get_volumes` id,
   `baseListId` = `data.volumes.*`, and a `volume_id` param sourced
   from the `get_volumes` `data.volumes.*-volume_id` attribute (see
   `context/mpb_chaining_wire_format.md` §6 for the exact wire
   format). If removed, also delete any references to it (the failing
   file has none — it's already orphan, so deletion is one-step).

4. **Fix `mpb_min_event_severity` defaultValue** from `"WARNING"`
   to `"Warning"` to match the option list.

5. **Drop explicit `null` values on `dataModelLists[].label` and
   `dataModelLists[].parentListId`** for the `base` DMLs. Either
   omit the keys entirely (working pattern) or set `parentListId`
   to a real ID (no `base` should have a parent in this design).

6. **Restore `getSession.headers` to include
   `{Content-Type: application/json, type: REQUIRED}`** for parity.
   Probably not a blocker.

7. **Add `paging` blocks to the six paged requests** to match the
   working export. This is a substantial port — each `paging` block
   has its own nested `dataModelLists`. Likely not the immediate
   blocker (the failing file would have failed even with this) but
   needed for runtime correctness.

8. **Switch UUID generation from v5 to v4** for parity with the
   factory's stated convention and to avoid cross-import collisions.
   Tooling-level change, not a per-design fix.

## Open questions

1. **Is the importer's validator strict about `nameMetricExpression
   != null` on `isListObject: false` objects?** Cannot determine
   from files alone; the live API call would tell us, but we cannot
   call it. The working file's pattern (every object has a non-null
   expression) suggests the answer is yes.

2. **Does the importer require `paging` to be present, or treat it
   as optional?** Unknown. The working file's pattern is "present
   for paged endpoints, absent for non-paged" — but we don't know
   how the validator treats absent `paging` on what looks like a
   list endpoint.

3. **Does the importer's validator key on
   `SINGLE_SELECTION.defaultValue ∈ options` exactly?** Unknown
   without server logs. The mismatch is real (`WARNING` vs
   `Warning`); whether it's the trigger is uncertain.

4. **The failing file's parser DMLs are dramatically sparser than
   the working file's** (e.g. `storage_info` has 1 DML in failing vs
   5 DMLs in working; `get_storage_pools` has 2 vs 24). This won't
   block import but means many metrics will not be extractable at
   collection time. Out of scope for this diagnostic, but
   downstream `mp-author` should know.

5. **What does the actual server-side error log say?** This is
   the highest-signal data we don't have. Even an `ERROR` line
   from `pakManager.log` or the MPB importer log would shorten this
   list of candidates. Recommend Scott checks the relevant logs on
   devel after a repeat import attempt and feeds the message back
   to `api-explorer` for a follow-up.
