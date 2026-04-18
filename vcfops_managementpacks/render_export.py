"""Transform a flat MPB design JSON into the MPB UI exchange format (export.json).

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
                                   strip: paging, chainingSettings, designId
                                   response: keep only result.{responseCode, dataModelLists}
    .source.resources (list)     → .objects  (list of {"object": <obj>})
                                   strip: designId, ariaOpsConf
    .relationships (list)        → .relationships  (list of {"relationship": <rel>})
                                   strip: designId, _renderer_note
    .source.events (list)        → .events  (list of event dicts, stripped: designId)
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
from .render import render_mp_design_json, _render_global_headers


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FLAT_ONLY_KEYS: frozenset = frozenset({
    # On expressionParts (dataModelList attrs, metric/event/name expressions):
    "example",       # empty string placeholder; absent in exchange format
    "regex",         # always null in our output; absent in exchange format
    "regexOutput",   # always "" in our output; absent in exchange format
    # Renderer internal annotation:
    "_renderer_note",
})


def _strip_flat_only_fields(obj: Any) -> Any:
    """Recursively remove all flat-format-only keys from the exchange output.

    The flat format (render.py) emits several fields that MPB's exchange
    format does not accept.  Their presence causes HTTP 400 "Invalid input
    format" on POST /internal/mpbuilder/designs/import.

    Fields stripped (confirmed absent in known-good MPB export, 2026-04-17):
      - example       — on expressionParts, dataModelList attributes,
                        session variables
      - regex         — on expressionParts (null when no regex used)
      - regexOutput   — on expressionParts (empty string)
      - _renderer_note — internal renderer annotation on relationships and
                         expression parts
    """
    if isinstance(obj, dict):
        return {k: _strip_flat_only_fields(v) for k, v in obj.items()
                if k not in _FLAT_ONLY_KEYS}
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

    result: List[Dict[str, Any]] = []

    # 1. Emit standard seven in canonical order with UUID5 IDs
    for tmpl in _MPB_STANDARD_CONFIG_TEMPLATE:
        entry = dict(tmpl)
        entry["id"] = _stable_config_id(adapter_kind, tmpl["key"])
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


def _strip_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat request object to exchange format.

    Removes fields that appear in the flat format but NOT in the exchange format:
      paging, designId

    chainingSettings IS present in exchange format exports (confirmed from
    context/mpb_chaining_wire_format.md §2.1 cross-validation against both the
    Synology DSM MP.json capture and the Rubrik reference).  It must NOT be
    stripped — dropping it would silently break chain wiring in imported designs.

    Collapses response: keeps only result.{responseCode, dataModelLists}.
    params.id is absent in our flat format already (render.py strips it).
    """
    r = {
        "id": req["id"],
        "name": req["name"],
        "path": req["path"],
        "method": req["method"],
        "body": req.get("body") or "",
        "headers": req.get("headers") or [],
        "params": req.get("params") or [],
    }

    # Preserve chainingSettings (present in exchange format; null means no chain)
    r["chainingSettings"] = req.get("chainingSettings")

    # Collapse response: keep only result.{responseCode, dataModelLists}
    resp = req.get("response")
    if resp and isinstance(resp, dict):
        result = resp.get("result", {})
        r["response"] = {
            "result": {
                "responseCode": result.get("responseCode", 200),
                "dataModelLists": result.get("dataModelLists", []),
            }
        }
    else:
        r["response"] = {
            "result": {
                "responseCode": 200,
                "dataModelLists": [],
            }
        }

    return r


def _strip_metric(metric: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from a metric dict.

    Removes: timeseries (null in flat format, absent in exchange format).
    """
    drop = {"timeseries"}
    return {k: v for k, v in metric.items() if k not in drop}


def _strip_metric_set(ms: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from a metricSet dict.

    Removes: objectBinding (null in flat format, absent in exchange format).
    Recurses into metrics[].
    """
    drop = {"objectBinding"}
    result = {k: v for k, v in ms.items() if k not in drop}
    if "metrics" in result:
        result["metrics"] = [_strip_metric(m) for m in result["metrics"]]
    return result


def _strip_internal_object_info(ioi: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from internalObjectInfo.

    Removes: id (present in flat format, absent in exchange format).
    """
    drop = {"id"}
    return {k: v for k, v in ioi.items() if k not in drop}


def _strip_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat resource/object to exchange format.

    Removes: designId, ariaOpsConf
    Strips internalObjectInfo.id, metricSets[].objectBinding,
    and metricSets[].metrics[].timeseries (all absent in exchange format).
    """
    drop = {"designId", "ariaOpsConf"}
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

    Removes: designId, _renderer_note
    """
    drop = {"designId", "_renderer_note"}
    return {k: v for k, v in rel.items() if k not in drop}


def _strip_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat event to exchange format.

    Removes: designId
    """
    drop = {"designId"}
    return {k: v for k, v in evt.items() if k not in drop}


def _strip_session_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Strip a session/test request to exchange shape.

    Auth session requests (getSession/releaseSession) and testRequest use a
    response shape with responseCode only — no dataModelLists.  The full
    _strip_request shape (which includes dataModelLists) is for regular
    requests only.

    Confirmed from known-good MPB export (2026-04-17): all three request
    types (getSession, releaseSession, testRequest) have
    response.result = {responseCode: N} only.
    """
    resp = req.get("response")
    if resp and isinstance(resp, dict):
        result = resp.get("result", {})
        response_code = result.get("responseCode", 200)
    else:
        response_code = 200

    return {
        "id": req["id"],
        "name": req["name"],
        "path": req["path"],
        "method": req["method"],
        "body": req.get("body") or "",
        "headers": req.get("headers") or [],
        "params": req.get("params") or [],
        "response": {
            "result": {
                "responseCode": response_code,
            }
        },
    }


def _strip_auth_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Strip a session request (getSession/releaseSession) to exchange shape.

    Delegates to _strip_session_request which produces responseCode-only
    response (no dataModelLists).
    """
    return _strip_session_request(req)


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
    # ------------------------------------------------------------------
    design_block = {
        "design": {
            "name": pak.get("name", mp.name),
            "type": src.get("type", "HTTP"),
            "description": pak.get("description", ""),
            "version": mp.version,  # base version, no build suffix
        }
    }

    # ------------------------------------------------------------------
    # 2. source.source block
    # ------------------------------------------------------------------
    auth = copy.deepcopy(src.get("authentication", {}))

    # Strip flat-format-only fields from credential items (value: null)
    if isinstance(auth.get("creds"), list):
        auth["creds"] = [_strip_cred(c) for c in auth["creds"]]

    # Strip session request fields that don't belong in exchange format.
    # Auth session requests use responseCode-only response (no dataModelLists).
    ss = auth.get("sessionSettings")
    if ss and isinstance(ss, dict):
        if ss.get("getSession"):
            ss["getSession"] = _strip_auth_request(ss["getSession"])
        if ss.get("releaseSession"):
            ss["releaseSession"] = _strip_auth_request(ss["releaseSession"])

    global_headers = _render_global_headers(mp)

    # Locate the test request from the requests dict.
    # testRequest uses responseCode-only response (no dataModelLists).
    test_req_id = src.get("testRequestId")
    test_req_raw = src.get("requests", {}).get(test_req_id) if test_req_id else None
    test_req = _strip_session_request(test_req_raw) if test_req_raw else None

    source_source = {
        "id": _stable_source_id(ak),
        "configuration": {
            "baseApiPath": src.get("basePath", ""),
            "customConfigs": [],
        },
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
        requests_list.append({"request": _strip_request(req)})

    # ------------------------------------------------------------------
    # 4. objects — list of {"object": ...}
    # ------------------------------------------------------------------
    objects_list = [
        {"object": _strip_object(obj)}
        for obj in src.get("resources", [])
    ]

    # ------------------------------------------------------------------
    # 5. relationships — list of {"relationship": ...}
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
            _strip_event(evt)
            for evt in src.get("events", [])
        ]

    exchange = {
        "type": src.get("type", "HTTP"),
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
