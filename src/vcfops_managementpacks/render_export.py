"""Transform a flat MPB design JSON into the MPB UI exchange format (export.json).

STRIP RULE POLICY (codified 2026-05-14 after audit of e135142 over-strip pattern):

    A field is stripped from the exchange format ONLY when we have positive
    evidence MPB rejects it on import.  Evidence means a documented import
    failure (link to a knowledge/context/ file or commit message), NOT absence-in-one-sample.

    If the only justification is "this field was absent in the Synology DSM sample",
    that is NOT sufficient evidence.  The Synology sample was a minimal single-level
    chain; it did not exercise multi-level chaining, populated chainingSettings.params,
    or many expression patterns the jcox UniFi reference exhibits.

    Ground-truth references (treat as authoritative — if a field appears in ANY of
    these, it is NOT forbidden by MPB):
      1. reference/references/jcox-au_vmware/unifi_MP_Builder_Design.json  ← primary
      2. tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7_MP_Builder_Design.json
      3. reference/references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json

    When adding a NEW strip rule: record the positive evidence inline as a comment.
    Do not add new strip rules on the basis of absence-in-one-sample alone.
    Mark uncertain rules (no evidence either way) with # UNCERTAIN comment.

    Audit log: knowledge/context/investigations/render_export_strip_audit_2026_05_14.md

WRAPPING RULE (derived from diff_mpb/conf/export.json vs template.json,
cross-checked against vcf_operations_mp_designs_export.zip "Synology DSM MP.json"
which is byte-for-byte identical to the pak-embedded export.json):

    The flat format (what render_mp_design_json() produces and what is stored in
    adapters.zip/conf/design.json) and the exchange format (what MPB UI
    Import/Export uses) are NOT a simple double-wrap of each other.  They share
    the same internal schemas for most sub-objects (authentication, metricSets,
    expressions, etc.) but differ in their top-level organization:

    flat                         exchange (export.json)
    ----                         ----------------------
    .version                     (dropped)
    .id                          (dropped — not in exchange)
    .name                        (dropped)
    .pakSettings.name            → .design.design.name
    .pakSettings.version         → .design.design.version
    .pakSettings.description     → .design.design.description
    .source.type                 → .type  (top-level)
                                 → .design.design.type
    .source.basePath             → .source.source.configuration.baseApiPath
                                   .source.source.configuration.customConfigs = []
    .source.testRequestId        (used to look up the test request)
    test request (from requests) → .source.source.testRequest  (stripped to exchange shape)
    auth.headers / header_inject → .source.source.globalHeaders  (via _render_global_headers)
    .source.authentication       → .source.source.authentication  (same schema, stripped)
    .source.configuration        → .source.configuration  (same schema, same position)
    .source.requests (dict)      → .requests  (list of {"request": <req>})
                                   strip: designId, paging (neither in MPB exchange)
                                   chainingSettings: null when absent, populated when chained
                                   chain params: strip "example" field
                                   response: full envelope (id, log, status, timing,
                                   toolkitId, errorMessage + result.{body, headers,
                                   responseCode, dataModelLists})
    .source.resources (list)     → .objects  (list of {"object": <obj>})
                                   INTERNAL: strip designId, ariaOpsConf (both absent in MPB)
                                   ARIA_OPS: strip designId; keep ariaOpsConf (populated)
    .relationships (list)        → .relationships  (list of {"relationship": <rel>})
                                   strip: designId, _renderer_note
    .source.events (list)        → .events  (list of {"event": <evt>}, stripped: designId)
    .constants                   (dropped)

    source.source.id is a stable UUID5 derived from the adapter_kind — MPB normally
    mints a random UUID4 here, but stability is required per CLAUDE.md §6.

OPEN QUESTIONS / BLOCKERS:
    None.  All fields in export.json can be derived from the flat render output.
    The dataModelLists in request.response.result are already computed by
    render_mp_design_json() and just need to be extracted from the flat response
    envelope.

USAGE:
    python3 -m vcfops_managementpacks render-export <mp.yaml> --out <output.json>

REFERENCE ARTIFACTS (do not re-extract):
    tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json
    tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/template.json
    tmp/vcf_operations_mp_designs_export.zip (Synology DSM MP.json — identical to export.json)
"""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import ManagementPackDef
from .render import render_mp_design_json, _render_global_headers, _make_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FLAT_ONLY_KEYS: frozenset = frozenset({
    # Renderer internal annotation — never in exchange format:
    "_renderer_note",
    # example / regex / regexOutput: stripped universally across ALL contexts
    # (metric expressionParts, relationship child/parentExpression, objectBinding
    # sub-expressions, dataModelList attributes, chaining params).
    #
    # Previous policy (2026-05-14): preserved these based on jcox-au_vmware
    # unifi_MP_Builder_Design.json ground truth which had them on all expressionParts.
    # The `_in_chaining`, `_in_objectbinding`, `_in_relationship` exception flags
    # enforced this preservation in _strip_flat_only_fields.
    #
    # Superseded (2026-05-15): MPB UI exports for both UniFi and vSphere Storage
    # Paths strip them universally — expressionParts in metrics, relationships,
    # objectBindings, and chaining all lack these fields in the live MPB output.
    # The jcox reference appears to have been captured under an older MPB build;
    # the 2026-05-15 live evidence is more authoritative.  Strip everywhere to
    # match current MPB behavior.
    # See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 2.
    "example",
    "regex",
    "regexOutput",
})


def _strip_flat_only_fields(obj: Any) -> Any:
    """Recursively remove all flat-format-only keys from the exchange output.

    The flat format (render.py) emits several fields that MPB's exchange
    format does not include.  Stripped universally across all contexts
    (metrics, relationships, objectBindings, chainingSettings, dataModelLists):

      - example       — on expressionParts, dataModelList attributes, params
      - regex         — on expressionParts (null when no regex used)
      - regexOutput   — on expressionParts (empty string)
      - _renderer_note — internal renderer annotation

    Policy superseded 2026-05-15: previous code preserved example/regex/
    regexOutput inside chainingSettings (_in_chaining), objectBinding
    (_in_objectbinding), and relationship (_in_relationship) contexts based
    on jcox-au_vmware ground truth (2026-05-14).  Live MPB UI exports for
    both UniFi and vSphere Storage Paths (2026-05-15) strip them universally.
    Exception flags and their preservation logic have been removed.
    See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 2.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_flat_only_fields(v)
            for k, v in obj.items()
            if k not in _FLAT_ONLY_KEYS
        }
    if isinstance(obj, list):
        return [_strip_flat_only_fields(item) for item in obj]
    return obj


def _stable_source_id(adapter_kind: str) -> str:
    """Generate a per-emit UUID4 for source.source.id.

    MPB normally mints a random UUID4 here.  Per-emit randomness is required
    because MPB deduplicates imports on this field — a stable UUID5 would
    cause re-imports to clobber the existing design rather than create a new
    one.  CLAUDE.md §6 UUID stability applies to content objects (super metrics,
    views, dashboards) but NOT to the MPB exchange source identity field.

    The adapter_kind parameter is accepted for API compatibility but unused.
    """
    return str(uuid.uuid4())


def _stable_config_id(adapter_kind: str, key: str) -> str:
    """Generate a stable UUID for a source.configuration item.

    MPB mints random UUID4s for each config item on first creation.  We
    derive UUID5 from adapter_kind + key so they're reproducible per
    CLAUDE.md §6 UUID stability rule.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS,
                          f"vcfops_managementpacks:config:{adapter_kind}:{key}"))


# Canonical MPB exchange shapes for the seven standard mpb_* config items.
# Source of truth: tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json
# §source.configuration (captured 2026-04-17).
# Keys match exactly.  UUIDs are replaced with UUID5-derived values per
# _stable_config_id() at transform time — id placeholder is the mpb key name.
_MPB_STANDARD_CONFIG_TEMPLATE: List[Dict[str, Any]] = [
    {
        "id": "mpb_hostname",          # placeholder — replaced with UUID5
        "label": "Hostname",
        "key": "mpb_hostname",
        "defaultValue": "",
        "description": "The hostname used to connect to the target API.",
        "advanced": False,
        "editable": False,
        "configType": "STRING",
    },
    {
        "id": "mpb_port",
        "label": "Port",
        "key": "mpb_port",
        "defaultValue": "443",
        "description": "The port used to connect to the target API.",
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
    },
    {
        "id": "mpb_connection_timeout",
        "label": "Connection Timeout (s)",
        "key": "mpb_connection_timeout",
        "defaultValue": "30",
        "description": "The maximum number of seconds to wait for a response from the endpoint.",
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
    },
    {
        "id": "mpb_concurrent_requests",
        "label": "Maximum Concurrent Requests",
        "key": "mpb_concurrent_requests",
        # Template default "2" matches MPB default.  Per-MP YAML overrides this via
        # src.max_concurrent (e.g. UniFi ships 10, Storage Paths ships 5).
        # MPB ships 2 / Verify; factory ships higher concurrency / No Verify
        # intentionally — parallel collection, lab-friendly TLS.
        # See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 5.
        "defaultValue": "2",
        "description": "The maximum number of request that can be run simultaneously.",
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
    },
    {
        "id": "mpb_max_retries",
        "label": "Maximum Retries",
        "key": "mpb_max_retries",
        "defaultValue": "2",
        "description": "The maximum number of times a call to an endpoint will be retried if it fails.",
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
    },
    {
        "id": "mpb_ssl_config",
        "label": "SSL Configuration",
        "key": "mpb_ssl_config",
        # Template default "Verify" matches MPB default.  Per-MP YAML overrides this
        # via src.ssl (e.g. UniFi and Storage Paths ship "No Verify" for lab TLS).
        # MPB ships "Verify"; factory ships "No Verify" intentionally for lab environments.
        # See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 5.
        "defaultValue": "Verify",
        "description": "The SSL mode to use when connecting to the target. Can be configured without SSL (No SSL), to use SSL but do not verify the target's certificate (No Verify), or to use SSL and verify the target's certificate (Verify).",
        "advanced": True,
        "editable": False,
        "configType": "SINGLE_SELECTION",
        "options": ["No Verify", "Verify", "No SSL"],
    },
    {
        "id": "mpb_min_event_severity",
        "label": "Minimum VMware Aria Operations Severity",
        "key": "mpb_min_event_severity",
        "defaultValue": "Warning",
        "description": "The minimum event severity to collect.",
        "advanced": True,
        "editable": False,
        "configType": "SINGLE_SELECTION",
        "options": ["Critical", "Immediate", "Warning", "Info"],
    },
]

_MPB_STANDARD_KEYS = {item["key"] for item in _MPB_STANDARD_CONFIG_TEMPLATE}


def _transform_configuration(
    flat_config: List[Dict[str, Any]],
    adapter_kind: str,
) -> List[Dict[str, Any]]:
    """Transform a flat source.configuration list into MPB exchange format.

    Rules (derived from structural diff against known-good MPB export, 2026-04-17):
      1. Standard seven mpb_* items: replace wholesale with canonical template
         entries.  UUID5 IDs derived from adapter_kind + key.
      2. Non-standard items: apply field-level transforms:
           - drop 'usage' and 'value' keys
           - stringify defaultValue (None → "", int → str(int))
           - omit 'options' key entirely unless configType == "SINGLE_SELECTION"
           - id: keep as-is (non-standard items use whatever the flat format set)
      3. Ordering: standard seven first (in canonical order), then any
         non-standard items appended in the order they appear in flat_config.
    """
    # Collect non-standard items from flat (preserve order, skip standard keys)
    # The flat format uses the mpb_* slug as both the id and represents the key
    # via a different field name — we match on the flat id field which IS the mpb key.
    flat_by_key: Dict[str, Dict[str, Any]] = {}
    non_standard: List[Dict[str, Any]] = []
    for item in flat_config:
        flat_id = item.get("id", "")
        if flat_id in _MPB_STANDARD_KEYS:
            flat_by_key[flat_id] = item
        else:
            non_standard.append(item)

    # SSL value mapping: loader constants → MPB exchange display strings
    _SSL_LOADER_TO_MPB: Dict[str, str] = {
        "NO_VERIFY": "No Verify",
        "VERIFY":    "Verify",
        "NO_SSL":    "No SSL",
    }

    result: List[Dict[str, Any]] = []

    # 1. Emit standard seven in canonical order with UUID5 IDs.
    #    Overlay defaultValue from the flat entry when present so that
    #    per-MP source values (port, ssl, timeout, retries, concurrent)
    #    are preserved rather than silently replaced by template defaults.
    for tmpl in _MPB_STANDARD_CONFIG_TEMPLATE:
        entry = dict(tmpl)
        entry["id"] = _stable_config_id(adapter_kind, tmpl["key"])
        flat = flat_by_key.get(tmpl["key"])
        if flat is not None:
            dv = flat.get("defaultValue")
            if dv is not None:
                # SSL axis: loader constant → MPB display string
                if tmpl["key"] == "mpb_ssl_config":
                    entry["defaultValue"] = _SSL_LOADER_TO_MPB.get(
                        str(dv).upper(), str(dv)
                    )
                elif not isinstance(dv, str):
                    entry["defaultValue"] = str(dv)
                else:
                    entry["defaultValue"] = dv
        result.append(entry)

    # 2. Emit non-standard items with field-level transforms
    for item in non_standard:
        entry = {k: v for k, v in item.items()
                 if k not in ("usage", "value")}
        # Stringify defaultValue
        dv = entry.get("defaultValue")
        if dv is None:
            entry["defaultValue"] = ""
        elif not isinstance(dv, str):
            entry["defaultValue"] = str(dv)
        # Conditionally emit options
        if entry.get("configType") != "SINGLE_SELECTION":
            entry.pop("options", None)
        result.append(entry)

    return result


def _build_response_envelope(
    req_id: str,
    adapter_kind: str,
    result_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the full MPB exchange response envelope for a request.

    Every request in the exchange format (including testRequest) wraps the
    result block in a full envelope with id, log, status, timing, toolkitId,
    and errorMessage fields.  Confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json
    (2026-05-14): all 9 data requests AND testRequest have identical envelope shape.

    Constants used:
      log / result.body: literal import placeholders from the reference.
      status: "COMPLETED" — the reference uses this for imported designs.
      endTime / startTime: 0 (integer).
      duration: "NA" (string).
      errorMessage: "".
      id: deterministic UUID5 from req_id so renders are stable.
      toolkitId: deterministic UUID5 from adapter_kind — the reference uses a
        single shared toolkitId across all requests; we derive it from the
        adapter_kind for stability.
    """
    response_id = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                 f"vcfops_managementpacks:response:id:{req_id}"))
    toolkit_id = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                f"vcfops_managementpacks:toolkit:{adapter_kind}"))
    return {
        "id": response_id,
        "log": "Imported request, execute to get accurate log",
        "result": result_body,
        "status": "COMPLETED",
        "endTime": 0,
        "duration": "NA",
        "startTime": 0,
        "toolkitId": toolkit_id,
        "errorMessage": "",
    }


def _strip_request(req: Dict[str, Any], adapter_kind: str = "") -> Dict[str, Any]:
    """Convert a flat request object to exchange format.

    Key rules (updated 2026-05-15 against MPB UI exports for UniFi and
    vSphere Storage Paths — see knowledge/context/mpb/mp_format_comparison_2026_05_15.md):

    1. designId: NOT emitted.
       Evidence (2026-05-15): MPB-built UniFi export — request keys are
       ['body', 'chainingSettings', 'headers', 'id', 'method', 'name',
       'params', 'path', 'response'] — no designId.
       Previous rule (always emit null) reversed by this evidence.

    2. chainingSettings: emitted ONLY when non-null (i.e., only for chained
       requests).  Drop the key when null.
       Previous rule (2026-05-14, jcox): always emitted even when null.
       Superseded (2026-05-15): MPB exports drop the key on non-chaining requests.
       params[].example stripped (MPB-built UniFi export, 2026-05-15 — param
       keys are ['attributeExpression','id','key','label','listId','usage'],
       no 'example').

    3. paging: NOT emitted (same evidence as designId — absent in MPB export).
       Previous rule (always emit, even null) was wrong.

    4. response: minimal shape — {result: {responseCode, dataModelLists}}.
       Previous rule (full envelope with id/log/status/toolkitId/etc.) was
       based on jcox-au_vmware reference (2026-05-14).  Superseded (2026-05-15):
       MPB UI exports for both UniFi and Storage Paths use the minimal shape.
       The full envelope (_build_response_envelope) is retained in code for
       historical reference but is no longer used on this path.

    5. dataModelLists: the ghost {"id": "base", "key": [], "attributes": []}
       entry emitted by the factory when there are no base-level attributes is
       stripped.  MPB never emits this empty base entry.

    params.id is absent in our flat format already (render.py strips it).
    """
    req_id = req["id"]
    r = {
        "id": req_id,
        "name": req["name"],
        "path": req["path"],
        "method": req["method"],
        "body": req.get("body") or "",
        "headers": req.get("headers") or [],
        "params": req.get("params") or [],
    }
    # designId and paging are NOT emitted (absent in MPB-built UniFi export, 2026-05-15).

    # chainingSettings: emit only when non-null.
    # Strip "example" from params[] (MPB-built UniFi export, 2026-05-15).
    chain = req.get("chainingSettings")
    if chain and isinstance(chain, dict) and chain.get("params"):
        chain = dict(chain)
        chain["params"] = [
            {k: v for k, v in p.items() if k != "example"}
            for p in chain["params"]
        ]
    if chain is not None:
        r["chainingSettings"] = chain
    # else: key omitted entirely when null (matches MPB 2026-05-15 behavior)

    # response: minimal shape {result: {responseCode, dataModelLists}}.
    # Strip the ghost {"id": "base", "key": [], "attributes": []} base entry
    # from dataModelLists — MPB never emits this empty list (Category D, report).
    resp = req.get("response")
    if resp and isinstance(resp, dict):
        result = resp.get("result", {})
        raw_dmls = result.get("dataModelLists", [])
        # Filter out the ghost base entry (empty attributes, id=="base")
        dmls = [
            dml for dml in raw_dmls
            if not (dml.get("id") == "base" and not dml.get("attributes"))
        ]
        response_code = result.get("responseCode", 200)
    else:
        dmls = []
        response_code = 200

    r["response"] = {
        "result": {
            "responseCode": response_code,
            "dataModelLists": dmls,
        }
    }

    return r


def _strip_metric(metric: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from a metric dict.

    Removes:
      - timeseries: null in flat format, absent in exchange format.
      - key: present in flat format, absent in exchange format (confirmed
        from tmp/mpb_reference_none_auth.json, 2026-05-13).
    """
    drop = {"timeseries", "key"}
    return {k: v for k, v in metric.items() if k not in drop}


def _remap_object_binding(ob: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Remap a flat-format objectBinding to exchange-format shape.

    Two transforms are applied:

    1. Type remap + key rename: the flat renderer emits "type": <value> for
       INTERNAL object bindings.  The MPB exchange format uses the key
       "objectBindingType" (not "type") — confirmed from mpb_export.json
       (MPB-built UniFi export, 2026-05-15): all objectBinding dicts use
       "objectBindingType" key.  Rename "type" → "objectBindingType".
       Additionally remap "CHAINED_REQUEST" → "ATTRIBUTE_TO_PROPERTY": our
       flat-format internal marker "CHAINED_REQUEST" must become the exchange
       value "ATTRIBUTE_TO_PROPERTY" per jcox-au_vmware/unifi_MP_Builder_Design.json
       (2026-05-14).

    2. ARIA_OPS objectBinding: the flat renderer already uses "objectBindingType"
       key for ARIA_OPS objects (Case 0 in render.py), so those pass through
       unchanged.  Only the "type" key is subject to the rename.

    Returns None unchanged (null is kept by _strip_metric_set).
    """
    if ob is None:
        return None
    ob = dict(ob)
    if "type" in ob:
        # Rename flat-format "type" → exchange "objectBindingType".
        # Evidence: /tmp/mpb_pak_inspect/mpb_export.json (2026-05-15) — every
        # objectBinding uses "objectBindingType" key, never "type".
        binding_type = ob.pop("type")
        if binding_type == "CHAINED_REQUEST":
            binding_type = "ATTRIBUTE_TO_PROPERTY"
        ob["objectBindingType"] = binding_type
    return ob


def _strip_metric_set(ms: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from a metricSet dict.

    objectBinding rules (updated 2026-05-15):
    - Drop the "objectBinding" key entirely when null.
      Previous rule (2026-05-14, jcox): always emit even when null, because
      jcox-au_vmware/unifi_MP_Builder_Design.json had objectBinding: null
      on every primary/chain-parent metricSet.
      Superseded (2026-05-15): MPB UI exports for both UniFi and Storage Paths
      drop the key when null.  The field is listed in mpb_api_surface.md
      "Fields present in flat format that MPB's import parser rejects" for
      null values.  See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 3.
    - Remap type: "CHAINED_REQUEST" → "ATTRIBUTE_TO_PROPERTY" for exchange
      format.  "CHAINED_REQUEST" is our flat-format internal marker.
    - Full expression structures (expressionText + expressionParts) are present
      in the flat render output after the render.py Sub-case B fix.

    Recurses into metrics[].
    """
    result = dict(ms)
    # objectBinding: emit only when non-null (drop key when null).
    raw_ob = result.get("objectBinding")
    remapped_ob = _remap_object_binding(raw_ob)
    if remapped_ob is not None:
        result["objectBinding"] = remapped_ob
    else:
        result.pop("objectBinding", None)
    if "metrics" in result:
        result["metrics"] = [_strip_metric(m) for m in result["metrics"]]
    return result


def _strip_internal_object_info(ioi: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from internalObjectInfo.

    Strips: id
      Previous rule (2026-05-14, jcox): preserved id — jcox-au_vmware UniFi
      reference had internalObjectInfo.id present with a non-null value.
      Superseded (2026-05-15): MPB UI exports for UniFi and vSphere Storage
      Paths drop internalObjectInfo.id entirely.  The field is listed in
      mpb_api_surface.md "Fields present in flat format that MPB's import
      parser rejects".  The jcox reference was an older MPB version.
      See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 3.

    Preserves: nameMetricExpression (including expressionParts[].label) —
      MPB-built exports do have nameMetricExpression; the label field on
      expressionParts is retained (separate from example/regex/regexOutput
      which are stripped by _strip_flat_only_fields).
    """
    return {k: v for k, v in ioi.items() if k != "id"}


def _strip_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat resource/object to exchange format.

    For INTERNAL objects:
      - designId: dropped (not emitted).
        Previous rule (always emit null) was reversed by MPB-built UniFi export
        (2026-05-15): INTERNAL objects have no designId key at all.
        Evidence: /tmp/mpb_pak_inspect/mpb_export.json — all 5 INTERNAL objects
        have keys ['id', 'internalObjectInfo', 'isListObject', 'metricSets', 'type'].
      - ariaOpsConf: dropped (not emitted).
        Previous rule (emit null) was reversed by same evidence: INTERNAL objects
        have no ariaOpsConf key at all.
      - internalObjectInfo: id stripped; nameMetricExpression preserved.
        (2026-05-15: MPB drops id; _strip_internal_object_info() now removes it.)
      - metricSets[].metrics[].key: stripped.
      - metricSets[].metrics[].timeseries: stripped (null-value-only difference).

    For ARIA_OPS objects:
      - ariaOpsConf: KEPT with its value (confirmed from ground truth:
        knowledge/context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json).
      - internalObjectInfo is absent (ARIA_OPS objects don't have it).
      - objectBinding uses "objectBindingType" key — passed through as-is.
      - designId: dropped from ARIA_OPS objects as well (consistent with INTERNAL
        treatment, no counter-evidence).
    """
    is_internal = obj.get("type") != "ARIA_OPS"

    # For INTERNAL objects: drop designId and ariaOpsConf entirely.
    # For ARIA_OPS objects: drop designId; keep ariaOpsConf (populated value).
    drop: set = {"designId"}
    if is_internal:
        drop.add("ariaOpsConf")

    result = {k: v for k, v in obj.items() if k not in drop}

    if "internalObjectInfo" in result and isinstance(result["internalObjectInfo"], dict):
        result["internalObjectInfo"] = _strip_internal_object_info(
            result["internalObjectInfo"]
        )
    if "metricSets" in result:
        result["metricSets"] = [_strip_metric_set(ms) for ms in result["metricSets"]]
    return result


def _strip_relationship(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat relationship to exchange format.

    Removes _renderer_note and designId.
    Evidence (2026-05-15): /tmp/mpb_pak_inspect/mpb_export.json — relationships
    have keys ['caseSensitive', 'childExpression', 'childObjectId', 'id', 'name',
    'parentExpression', 'parentObjectId'] — no designId.
    Previous rule (emit designId: null) was reversed by this MPB-built evidence.
    """
    drop = {"_renderer_note", "designId"}
    return {k: v for k, v in rel.items() if k not in drop}


def _strip_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat event to exchange format.

    Removes: designId
    """
    drop = {"designId"}
    return {k: v for k, v in evt.items() if k not in drop}


def _strip_session_request(req: Dict[str, Any], adapter_kind: str = "") -> Dict[str, Any]:
    """Strip a session/test request to exchange shape.

    testRequest response: minimal shape {result: {responseCode: N}}.
    MPB UI exports for UniFi and Storage Paths (2026-05-15) use this minimal
    shape for testRequest — no body/headers/dataModelLists.

    Previous rule (2026-05-14, jcox): full envelope same as regular requests.
    Superseded (2026-05-15) — see knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 4.

    chainingSettings: dropped when null (testRequest never chains).
    """
    req_id = req["id"]
    r = {
        "id": req_id,
        "name": req["name"],
        "path": req["path"],
        "method": req["method"],
        "body": req.get("body") or "",
        "headers": req.get("headers") or [],
        "params": req.get("params") or [],
    }
    # chainingSettings: omit when null (testRequest never chains)
    chain = req.get("chainingSettings")
    if chain is not None:
        r["chainingSettings"] = chain

    # Minimal response shape for test/session requests
    resp = req.get("response")
    if resp and isinstance(resp, dict):
        result = resp.get("result", {})
        response_code = result.get("responseCode", 200)
    else:
        response_code = 200
    r["response"] = {"result": {"responseCode": response_code}}

    return r


def _strip_auth_request(req: Dict[str, Any], adapter_kind: str = "") -> Dict[str, Any]:
    """Strip a session request (getSession/releaseSession) to exchange shape."""
    return _strip_session_request(req, adapter_kind=adapter_kind)


def _strip_cred(cred: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from a credential item.

    Removes: value (null in flat format, absent in exchange format).
    """
    drop = {"value"}
    return {k: v for k, v in cred.items() if k not in drop}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_mpb_exchange_json(
    mp: ManagementPackDef,
    relationship_strategy: str = "synthetic_adapter_instance",
    no_events: bool = False,
) -> Dict[str, Any]:
    """Render a ManagementPackDef into the MPB UI import/export format.

    Calls render_mp_design_json() to produce the flat design dict, then
    transforms it into the exchange format accepted by the MPB UI Import
    Design action.

    The exchange format was reverse-engineered from:
      tmp/diff_mpb/adapters/mpb_synology_dsm_mp_adapter3/conf/export.json
    Cross-checked against:
      tmp/vcf_operations_mp_designs_export.zip -> Synology DSM MP.json
    (both files are byte-for-byte identical confirming the format is stable
    across pak-export and MPB-UI-export paths).

    Returns a dict ready for json.dumps().
    """
    flat = render_mp_design_json(mp, relationship_strategy=relationship_strategy)
    ak = mp.adapter_kind
    src = flat["source"]
    pak = flat["pakSettings"]

    # ------------------------------------------------------------------
    # 1. design.design block
    #
    # Confirmed shape from synology_nas_working_export.json (2026-04-21):
    #   {
    #     "design": {
    #       "name": "...",
    #       "type": "HTTP",
    #       "description": "...",
    #       "version": "1.0.0"
    #     }
    #   }
    # Keys ABSENT in synology_nas_working_export.json: buildNumber, id, author.
    # id and author were incorrectly emitted before the 2026-04-21 wire-format audit.
    # buildNumber is present in the jcox-au_vmware UniFi reference at
    # design.buildNumber (sibling to design.design).
    # ------------------------------------------------------------------
    # Superseded 2026-05-15: MPB UI exports for both UniFi and vSphere Storage
    # Paths strip design.design.id, design.design.author, and design.buildNumber
    # entirely.  The jcox reference appears to have been an older MPB build;
    # 2026-05-15 live MPB output is authoritative.  These null/numeric placeholders
    # are harmless on import but should be omitted to match current MPB.
    # See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 3.
    design_block = {
        "design": {
            "name": pak.get("name", mp.name),
            "type": "HTTP",
            "description": pak.get("description", ""),
            "version": mp.version,  # base version, no build suffix
        },
        # buildNumber omitted: MPB UI exports do not emit this field (2026-05-15).
    }

    # ------------------------------------------------------------------
    # 2. source.source block
    # ------------------------------------------------------------------
    auth = copy.deepcopy(src.get("authentication", {}))

    # Remap credentialType "NONE" → "CUSTOM" for exchange format.
    # "NONE" is a flat-format-only sentinel emitted by render.py for preset:none
    # and no-auth cases.  MPB's import parser rejects it — every known-good import
    # uses "CUSTOM" (with empty creds and null sessionSettings), "BASIC", or "TOKEN".
    # This remap is exchange-format-only; render.py's design.json output is unchanged.
    if auth.get("credentialType") == "NONE":
        auth["credentialType"] = "CUSTOM"

    # Strip flat-format-only fields from credential items (value: null)
    if isinstance(auth.get("creds"), list):
        auth["creds"] = [_strip_cred(c) for c in auth["creds"]]

    # sessionSettings: drop the key entirely when null.
    # Previous rule (2026-05-14): always emit as null, based on jcox UniFi reference
    # which had sessionSettings: null explicitly.
    # Superseded (2026-05-15): MPB UI exports for UniFi and Storage Paths drop the
    # key entirely when sessionSettings is null (stateless APIs have no session).
    # See knowledge/context/mpb/mp_format_comparison_2026_05_15.md §item 3.
    ss = auth.get("sessionSettings")
    if ss is None:
        auth.pop("sessionSettings", None)
    elif isinstance(ss, dict):
        # Strip session request fields that don't belong in exchange format.
        # Auth session requests use responseCode-only response (no dataModelLists).
        if ss.get("getSession"):
            ss["getSession"] = _strip_auth_request(ss["getSession"], adapter_kind=ak)
        if ss.get("releaseSession"):
            ss["releaseSession"] = _strip_auth_request(ss["releaseSession"], adapter_kind=ak)

    global_headers = _render_global_headers(mp)

    # Locate the test request from the requests dict.
    # testRequest uses the full response envelope (same as regular requests) —
    # confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json (2026-05-14).
    test_req_id = src.get("testRequestId")
    test_req_raw = src.get("requests", {}).get(test_req_id) if test_req_id else None
    test_req = _strip_session_request(test_req_raw, adapter_kind=ak) if test_req_raw else None

    # source.source.configuration block.
    # Confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json (2026-05-14):
    #   - port, maxRetries, connectionTimeout, maxConcurrentRequests: integers (not strings)
    #   - hostname: null (not empty string "")
    #   - sslSetting: loader constant string (e.g. "NO_VERIFY", not display "No Verify")
    #   - minEventSeverity: uppercase constant ("WARNING", not "Warning")
    # Earlier code stringified numeric values and used display strings for SSL/severity.
    _mp_src = mp.source  # ManagementPackDef.source (SourceDef)
    _ssl_str = str(_mp_src.ssl).upper() if _mp_src and _mp_src.ssl else "VERIFY"
    _source_configuration: dict = {
        "hostname": None,
        "port": int(_mp_src.port) if _mp_src and _mp_src.port is not None else 443,
        "maxRetries": int(_mp_src.max_retries) if _mp_src and _mp_src.max_retries is not None else 2,
        "sslSetting": _ssl_str,
        "baseApiPath": src.get("basePath", ""),
        "customConfigs": [],
        "minEventSeverity": "WARNING",
        "connectionTimeout": int(_mp_src.timeout) if _mp_src and _mp_src.timeout is not None else 30,
        "maxConcurrentRequests": int(_mp_src.max_concurrent) if _mp_src and _mp_src.max_concurrent is not None else 2,
    }

    source_source = {
        "id": _stable_source_id(ak),
        # designId omitted: MPB-built UniFi export (2026-05-15) has no designId
        # in source.source — keys are ['authentication','configuration',
        # 'globalHeaders','id','testRequest'].
        "configuration": _source_configuration,
        "authentication": auth,
        "globalHeaders": global_headers,
        "testRequest": test_req,
    }

    source_block = {
        "source": source_source,
        "configuration": _transform_configuration(
            src.get("configuration", []), ak
        ),
    }

    # ------------------------------------------------------------------
    # 3. requests — dict → list of {"request": ...}
    #    Exclude the testRequest (it lives in source.source, not requests[])
    # ------------------------------------------------------------------
    requests_list = []
    for req_id, req in src.get("requests", {}).items():
        if req_id == test_req_id:
            continue  # goes into source.source.testRequest, not requests[]
        requests_list.append({"request": _strip_request(req, adapter_kind=ak)})

    # ------------------------------------------------------------------
    # 4. objects — list of {"object": ...}
    # ------------------------------------------------------------------
    objects_list = [
        {"object": _strip_object(obj)}
        for obj in src.get("resources", [])
    ]

    # ------------------------------------------------------------------
    # 5. relationships — list of {"relationship": ...}
    #
    #    All relationships from the flat design dict are emitted, including
    #    adapter_instance-scope entries rendered by _render_relationships().
    #    render.py dispatches adapter_instance rels to
    #    _render_trivial_relationships(strategy=relationship_strategy), which
    #    produces a fully-formed wire dict with non-null child/parentExpression
    #    (for synthetic_adapter_instance and shared_constant_property strategies)
    #    or null expressions (world_implicit).
    #
    #    The previous code stripped adapter_instance rels here on the assumption
    #    that MPB would reject synthetic expressions.  That assumption was
    #    unverified; it was never confirmed by a documented import failure
    #    (contrary to the STRIP RULE POLICY at the top of this file).  Removed
    #    2026-05-18 so the design.json relationships array reflects the full YAML.
    # ------------------------------------------------------------------
    relationships_list = [
        {"relationship": _strip_relationship(rel)}
        for rel in flat.get("relationships", [])
    ]

    # ------------------------------------------------------------------
    # 6. events — flat list (strip designId only)
    #    When no_events=True, emit an empty list.  MPB 400s on our
    #    events wire format (ground-truth export not yet captured);
    #    --no-events lets the import loop work until we have a real
    #    MPB-authored event to diff against.
    # ------------------------------------------------------------------
    if no_events:
        events_list: List[Dict[str, Any]] = []
    else:
        events_list = [
            {"event": _strip_event(evt)}
            for evt in src.get("events", [])
        ]

    # Top-level exchange format:
    #   - type: "HTTP"  — present at top level.
    #     Evidence (2026-05-15): /tmp/mpb_pak_inspect/mpb_export.json top-level
    #     keys are ['type','design','source','objects','relationships','events',
    #     'requests'].  The wrapping rule docstring already specified this mapping
    #     (.source.type → .type top-level) but the field was never emitted.  Fixed.
    #   - content: NOT emitted.
    #     Previous rule (emit "content": []) reversed: MPB-built UniFi export
    #     (2026-05-15) has no 'content' key.  Earlier GitHub/Broadcom pak-compare
    #     evidence may have been from a different MPB version; MPB-built evidence
    #     is more authoritative.
    # Key order matches MPB output for readability.
    _top_type = src.get("type") or "HTTP"
    exchange = {
        "type": _top_type,
        "design": design_block,
        "source": source_block,
        "objects": objects_list,
        "relationships": relationships_list,
        "events": events_list,
        "requests": requests_list,
    }
    # MPB's import parser rejects flat-format-only keys anywhere in the payload
    # (HTTP 400 "Invalid input format").  Strip the entire tree before returning.
    # Fields removed: example, regex, regexOutput, _renderer_note.
    return _strip_flat_only_fields(exchange)
