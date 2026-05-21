# MPB design import investigation: vSphere Storage Paths (2026-05-13)

> **Historical.** Most recommendations (§1-3, §6) are implemented.
> Event format (§5, §7) remains a TOOLSET GAP — events are stripped
> from both design imports and pak builds.

Investigation of `POST /suite-api/internal/mpbuilder/designs/import`
rejection of `/tmp/vsphere_storage_paths_design.json`.

Error: `Error importing design. /suite-api/internal/mpbuilder/designs/import`

## Background

The factory's `render-export` command produces an "exchange format" JSON
designed for the MPB UI import action. This file was rendered from
`content/managementpacks/vsphere_storage_paths.yaml` and rejected by the
MPB UI.

The MPB import endpoint is **entirely undocumented** -- it appears in
neither `docs/internal-api.json` nor `docs/operations-api.json`. All
knowledge comes from empirical probing documented in
`context/mpb_api_surface.md`.

## Three exchange format variants in play

The investigation found THREE structurally distinct JSON formats that are
often conflated:

| Format | Source | Top-level keys | Purpose |
|---|---|---|---|
| **MPB UI export** | MPB UI "Export" button | `design, source, requests, objects, relationships, events, content` | What `POST /designs/import` accepts |
| **Pak-embedded export.json** | `adapters.zip/conf/export.json` | `type, design, source, requests, objects, relationships, events` | What the adapter runtime reads at init |
| **Our render-export** | `render_export.py` | `type, content, design, source, requests, objects, relationships, events` | Hybrid -- matches neither |

The factory's `render_export.py` was designed against the **pak-embedded**
format (specifically `synology_nas_working_export.json`), then patched with
elements from the **MPB UI** format (`content: null`, `buildNumber`). The
result is a hybrid that the import endpoint rejects.

## Divergences ranked by import-failure likelihood

### 1. EVENTS -- KNOWN IMPORT BLOCKER (HIGH)

The `render_export.py` source code already documents this:

```python
# 6. events -- flat list (strip designId only)
#    When no_events=True, emit an empty list.  MPB 400s on our
#    events wire format (ground-truth export not yet captured);
#    --no-events lets the import loop work until we have a real
#    MPB-authored event to diff against.
```

The file was rendered WITHOUT `--no-events`, so it contains 2 events.
The events wire format has never been validated against a known-working
MPB export because **no reference MP in the repo contains events** (all
four jcox/Rubrik/HoL references have `events: []`).

Additional event-level problems:
- Event `listId` is `data.*.*` but the request's data model only defines
  `data.*` and `base`. The double-wild `data.*.*` does not match any
  declared `dataModelList.id`, which would cause validation failure.
  **Root cause**: the YAML declares `response_path: "data.*"` on the
  event, but `_response_path_to_dml_id()` in render.py appends `.*` to
  any non-empty path, producing `data.*.*`. The author intended
  `response_path: "data"` (just the JSON key path, no glob suffix).
  The renderer does not strip trailing `.*` before composing the DML id.
- Event `originId` patterns use `data.*.*-hostname` instead of
  `data.*-hostname`, compounding the listId mismatch.

**Wrapping status**: the event `{"event": ...}` wrapping was already
fixed (render_export.py lines 705-707). Per `mpb_api_surface.md`
(2026-04-18 binary-substitution testing), wrapping events in
`{"event": ...}` does make the import PARSER accept them (201 Created).
However, imported events may still cause design VALIDATION failures
(the design lands as INVALID). The Synology MP ultimately stripped all
events to get a clean import (commit a6ec12d: "strip Tier-2 events").
No reference MP in the repo has a working event import to diff against.

**Fix**: re-render with `--no-events` until a ground-truth event export
is captured from the MPB UI and the event renderer is fixed.

### 2. `content: null` vs `content: []` (MEDIUM)

| File | `content` value | Import result |
|---|---|---|
| jcox UniFi (MPB UI export) | `list(1)` | works |
| phpIPAM (MPB UI export) | `list(3)` | works |
| Rubrik (MPB UI export) | `list(0)` = `[]` | works |
| GitLab HoL (MPB UI export) | `list(0)` = `[]` | works |
| Synology (pak-embedded) | absent | works (pak format, not import format) |
| **Our render-export** | **`null`** | **fails** |

Every genuine MPB UI export has `content` as a **list** (empty or
populated). Our render emits `null`. The import parser may reject `null`
as an invalid type for a field it expects to be an array. A safe fix is
to emit `content: []`.

### 3. Top-level `type: "HTTP"` key (LOW-MEDIUM)

Genuine MPB UI exports do NOT have a `type` key at top level. The
pak-embedded format does. Our render emits it (copied from the Synology
working export, which is the pak format). The import endpoint may ignore
it or may reject it as unexpected.

| File | Has top-level `type` | Format | Import via MPB UI |
|---|---|---|---|
| jcox/Rubrik/HoL (MPB UI) | No | UI export | works |
| Synology (pak-embedded) | Yes | pak export | N/A (not imported via UI) |
| **Our render-export** | **Yes** | hybrid | **fails** |

Per `context/mpb_api_surface.md`, a factory-rendered Synology design
with `type` at top level was confirmed to import successfully (201
Created) when events were stripped. So `type` alone is not a blocker.
But it IS an unnecessary divergence from the genuine UI export format.

### 4. `source.source.configuration` shape (MEDIUM)

| File | `source.source.configuration` | Import |
|---|---|---|
| jcox UniFi | Full object: `{hostname, port, maxRetries, sslSetting, baseApiPath, customConfigs, minEventSeverity, connectionTimeout, maxConcurrentRequests}` | works |
| **Our render-export** | Minimal: `{baseApiPath, customConfigs}` | **fails** |

The genuine MPB UI export includes the full connection configuration
inline in `source.source.configuration`. Our render emits only
`baseApiPath` and `customConfigs` (matching the pak-embedded format).
The import parser may require the full set of connection parameters.

### 5. Missing fields on objects (LOW)

Our render strips fields that genuine MPB UI exports include:

| Field | Genuine MPB UI | Our render | Verdict |
|---|---|---|---|
| `object.designId` | `null` | absent | Synology pak also omits; probably OK |
| `object.ariaOpsConf` | `null` | absent | Same |
| `internalObjectInfo.id` | populated | absent | Same |
| `metricSet.objectBinding` | `null` | absent | Same |
| `metric.timeseries` | `null` | absent | Same |
| `metric.key` | absent | **present** | Our render includes `key`; genuine does not |

The `metric.key` field is a renderer artifact that genuine MPB exports
lack. Its presence may not cause failure but is incorrect.

### 6. Missing fields on requests (LOW)

| Field | Genuine MPB UI | Our render | Verdict |
|---|---|---|---|
| `request.designId` | `null` | absent | Probably OK |
| `request.paging` | dict or `null` | absent | Synology pak includes it |
| `request.chainingSettings` | `null` or dict | absent (when null) | Probably OK |
| `response` envelope | Full (id, log, status, body, headers, etc.) | Minimal (result only) | Synology pak also uses minimal |

### 7. Expression parts missing fields (LOW)

| Field | Genuine MPB UI | Our render |
|---|---|---|
| `expressionPart.example` | `""` | absent |
| `expressionPart.regex` | `null` | absent |
| `expressionPart.regexOutput` | `""` | absent |

These are stripped by `_strip_flat_only_fields()`. The Synology pak
export also strips them, but the Synology pak goes through a different
code path (adapter init) than the MPB UI import.

### 8. `design.design` missing fields (LOW)

| Field | Genuine MPB UI | Our render |
|---|---|---|
| `design.design.id` | `null` | absent |
| `design.design.author` | `""` | absent |

## Root cause assessment

Event wrapping was confirmed to produce 201 Created on 2026-04-18
(`mpb_api_surface.md`), so wrapped events in the payload should not
cause an import parser rejection. However, the events have a structural
data model mismatch (listId `data.*.*` references a non-existent
dataModelList). This may cause the import parser to reject the entire
payload if it validates internal references at import time.

Most likely root cause candidates, in order:

1. **Event `listId`/`originId` data model mismatch** -- events reference
   `data.*.*` but only `data.*` exists in the request data model. If the
   import parser validates these cross-references, this would cause a 400.
2. **`content: null` instead of `content: []`** -- type mismatch.
   Every genuine MPB UI export uses a list. The import parser may
   reject null as an invalid type for this field.
3. Possibly the **minimal `source.source.configuration`** shape
   (missing hostname, port, etc.).

The underlying architectural issue is that `render_export.py` was built
against the pak-embedded format (which the adapter runtime reads), not
the MPB UI export format (which the import endpoint accepts). These are
two different serializations of the same logical design.

## Recommendation for renderer fix

Priority order:

1. **Re-render with `--no-events`** as an immediate workaround:
   ```
   python3 -m vcfops_managementpacks render-export \
     content/managementpacks/vsphere_storage_paths.yaml \
     --out /tmp/vsphere_storage_paths_design.json --no-events
   ```

2. **Change `content: null` to `content: []`** in `render_export.py`
   line 719.

3. **Remove top-level `type` key** from the exchange output. Genuine
   MPB UI exports do not have it. The `type` information is already
   in `design.design.type`.

4. **Populate `source.source.configuration` fully** with all connection
   parameters (hostname, port, maxRetries, sslSetting, etc.) matching
   the genuine MPB UI export shape. Currently only `baseApiPath` and
   `customConfigs` are emitted.

5. **Fix event listId generation** -- the double-wild `data.*.*`
   pattern does not match any declared `dataModelList.id` in the
   request response mapping.

6. **Strip `metric.key`** field from the exchange output (genuine MPB
   UI exports do not include it).

7. **Long-term**: capture a ground-truth MPB UI export that includes
   events and diff the event wire format against what our renderer
   produces. Until then, `--no-events` is the only safe path.

## Reference files

| Path | What it is |
|---|---|
| `/tmp/vsphere_storage_paths_design.json` | The failing factory-rendered export |
| `context/mpb_wire_reference/synology_nas_working_export.json` | Known-working pak-embedded export (NOT MPB UI format) |
| `references/jcox-au_vmware/unifi_MP_Builder_Design.json` | Known-working genuine MPB UI export |
| `references/jcox-au_vmware/phpipam_MP_Builder_Design.json` | Known-working genuine MPB UI export |
| `references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json` | Known-working genuine MPB UI export |
| `context/mpb_import_diff_unifi_2026_05_07.md` | Prior investigation (UniFi import failure) |
| `context/mpb_api_surface.md` | Empirically confirmed MPB API surface |
