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
                                   add: designId=null, paging=null, chainingSettings=null
                                   (paging/chainingSettings populated when non-null from flat)
                                   response: full envelope (id, log, status, timing,
                                   toolkitId, errorMessage + result.{body, headers,
                                   responseCode, dataModelLists})
    .source.resources (list)     → .objects  (list of {"object": <obj>})
                                   designId: always null (was stripped, now emitted)
                                   ariaOpsConf: always present (null for INTERNAL, value for ARIA_OPS)
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
    # NOTE: example/regex/regexOutput were previously stripped here but
    # the jcox reference (confirmed 2026-05-14) has them on ALL
    # expressionParts — metrics, relationships, objectBindings, chaining.
    # They are REQUIRED by the import parser. Do not strip.
})


def _strip_flat_only_fields(
    obj: Any,
    _in_chaining: bool = False,
    _in_objectbinding: bool = False,
    _in_relationship: bool = False,
) -> Any:
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

    Exception 1: when inside a chainingSettings block, example/regex/regexOutput
    on params[] and their expressionParts[] are REQUIRED by MPB (confirmed from
    HoL-2501-12 GitLab-Basic.json reference, 2026-04-19).  Those fields are
    preserved when _in_chaining=True.

    Exception 2: when inside an objectBinding block, example/regex/regexOutput
    on matchExpression/objectMatchExpression expressionParts[] are present in
    jcox-au_vmware/unifi_MP_Builder_Design.json (exchange format ground truth,
    2026-04-29).  Those fields are preserved when _in_objectbinding=True.

    Exception 3: when inside a relationship block, example/regex/regexOutput
    on childExpression/parentExpression expressionParts[] are present in
    jcox-au_vmware/unifi_MP_Builder_Design.json.  Preserved when
    _in_relationship=True.
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == "chainingSettings":
                result[k] = _strip_flat_only_fields(
                    v, _in_chaining=True, _in_objectbinding=False, _in_relationship=False
                )
                continue
            if k == "objectBinding":
                result[k] = _strip_flat_only_fields(
                    v, _in_chaining=False, _in_objectbinding=True, _in_relationship=False
                )
                continue
            if k == "relationship":
                result[k] = _strip_flat_only_fields(
                    v, _in_chaining=False, _in_objectbinding=False, _in_relationship=True
                )
                continue
            if (_in_chaining or _in_objectbinding or _in_relationship) and k in _FLAT_ONLY_KEYS:
                result[k] = v
                continue
            if k in _FLAT_ONLY_KEYS:
                continue
            result[k] = _strip_flat_only_fields(
                v, _in_chaining=_in_chaining, _in_objectbinding=_in_objectbinding, _in_relationship=_in_relationship
            )
        return result
    if isinstance(obj, list):
        return [
            _strip_flat_only_fields(
                item, _in_chaining=_in_chaining, _in_objectbinding=_in_objectbinding, _in_relationship=_in_relationship
            )
            for item in obj
        ]
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

    Key rules confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json
    (exchange format ground truth, 2026-05-14):

    1. designId: always emitted as null (confirmed present on every request in
       reference, value null). Earlier rule (drop entirely) was wrong.

    2. chainingSettings: always emitted — non-null dict when chained, null when
       not chained. Earlier rule (absent when null) was wrong; reference has the
       key with null value on non-chained requests.

    3. paging: always emitted — populated dict when pagination is in use, null
       when absent. Reference has the key with null value on non-paginated requests.
       Earlier rule (never emit) was wrong; MPB requires the key present.

    4. response: full envelope required — id, log, result, status, endTime,
       duration, startTime, toolkitId, errorMessage — plus result.body and
       result.headers inside the result block. Earlier rule (keep only
       result.{responseCode, dataModelLists}) was wrong; the full envelope is
       present on EVERY request in the reference (2026-05-14).

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
        "designId": None,
        "paging": None,
    }

    # Emit chainingSettings: non-null dict when chained, null otherwise.
    # Reference has the key on every request (confirmed 2026-05-14).
    chain = req.get("chainingSettings")
    r["chainingSettings"] = chain if chain is not None else None

    # Build full response envelope.
    # dataModelList entries: strip label and parentListId (absent in reference
    # export; confirmed from tmp/mpb_reference_none_auth.json, 2026-05-13).
    _DML_DROP = {"label", "parentListId"}
    resp = req.get("response")
    if resp and isinstance(resp, dict):
        result = resp.get("result", {})
        raw_dmls = result.get("dataModelLists", [])
        dmls = [{k: v for k, v in dml.items() if k not in _DML_DROP}
                for dml in raw_dmls]
        result_body = {
            "body": "Imported request, execute to get accurate body",
            "headers": [],
            "responseCode": result.get("responseCode", 200),
            "dataModelLists": dmls,
        }
    else:
        result_body = {
            "body": "Imported request, execute to get accurate body",
            "headers": [],
            "responseCode": 200,
            "dataModelLists": [],
        }

    r["response"] = _build_response_envelope(req_id, adapter_kind, result_body)

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


def _strip_metric_set(ms: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from a metricSet dict.

    objectBinding: kept when non-null (required for chained-secondary metricSets
    per MPB verify-time rule §8.1 — context/mpb_object_binding_wire_format.md).
    Dropped only when null (absent in exchange format for chain-parent,
    world/singleton, and single-metricSet list objects).
    The _strip_flat_only_fields pass preserves example/regex/regexOutput inside
    objectBinding.matchExpression/objectMatchExpression (ground truth: jcox
    exchange format includes them; see render_export.py _in_objectbinding flag).
    The two-expression shape (matchExpression + objectMatchExpression with
    originType METRIC) is required for chained-secondary bindings — confirmed
    from jcox-au_vmware/unifi_MP_Builder_Design.json (2026-05-07).
    Recurses into metrics[].
    """
    result = dict(ms)
    if result.get("objectBinding") is None:
        result.pop("objectBinding", None)
    if "metrics" in result:
        result["metrics"] = [_strip_metric(m) for m in result["metrics"]]
    return result


def _strip_internal_object_info(ioi: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flat-format-only fields from internalObjectInfo.

    Earlier rule stripped id from internalObjectInfo.  Confirmed from
    jcox-au_vmware/unifi_MP_Builder_Design.json (2026-05-14): ALL INTERNAL
    objects have internalObjectInfo.id present with a non-null value.
    The id field is now kept as-is from the flat render output.

    Removes:
      - nameMetricExpression.expressionParts[].label: present in flat format,
        absent in reference export (confirmed from
        tmp/mpb_reference_none_auth.json, 2026-05-13).
    """
    result = dict(ioi)
    nme = result.get("nameMetricExpression")
    if isinstance(nme, dict):
        eps = nme.get("expressionParts")
        if isinstance(eps, list):
            nme["expressionParts"] = [
                {k: v for k, v in ep.items() if k != "label"}
                for ep in eps
            ]
    return result


def _strip_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat resource/object to exchange format.

    For ALL objects (INTERNAL and ARIA_OPS):
      - designId: always emitted as null (confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json —
        all six objects have designId: null, 2026-05-14).
      - ariaOpsConf: always emitted (null for INTERNAL, populated for ARIA_OPS).
        Earlier rule (drop ariaOpsConf for INTERNAL) was wrong; reference has the
        key on all objects including INTERNAL ones, value null.

    For INTERNAL objects:
      Strips internalObjectInfo.id, metricSets[].objectBinding when null,
      and metricSets[].metrics[].timeseries (all absent in exchange format).

    For ARIA_OPS objects:
      ariaOpsConf is KEPT with its value (confirmed from ground truth:
        context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json).
      internalObjectInfo is absent (ARIA_OPS objects don't have it).
      objectBinding uses "objectBindingType" key (not "type") — passed through as-is.
    """
    # Drop nothing from the object dict — designId and ariaOpsConf are both
    # kept (designId forced to null below, ariaOpsConf kept as-is or set null).
    drop: set = set()

    result = {k: v for k, v in obj.items() if k not in drop}

    # Always emit designId as null (reference: all objects have designId: null)
    result["designId"] = None

    # Always emit ariaOpsConf: null for INTERNAL objects (reference confirms key
    # present with null value on all INTERNAL objects, 2026-05-14).
    # ARIA_OPS objects: keep existing ariaOpsConf value from flat format.
    if obj.get("type") != "ARIA_OPS":
        result["ariaOpsConf"] = None
    if "internalObjectInfo" in result and isinstance(result["internalObjectInfo"], dict):
        result["internalObjectInfo"] = _strip_internal_object_info(
            result["internalObjectInfo"]
        )
    if "metricSets" in result:
        result["metricSets"] = [_strip_metric_set(ms) for ms in result["metricSets"]]
    return result


def _strip_relationship(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat relationship to exchange format.

    Keeps designId as null (required by import parser). Removes _renderer_note.
    """
    r = {k: v for k, v in rel.items() if k != "_renderer_note"}
    r["designId"] = None
    return r


def _strip_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a flat event to exchange format.

    Removes: designId
    """
    drop = {"designId"}
    return {k: v for k, v in evt.items() if k not in drop}


def _strip_session_request(req: Dict[str, Any], adapter_kind: str = "") -> Dict[str, Any]:
    """Strip a session/test request to exchange shape.

    Earlier rule (responseCode only, no body/headers/dataModelLists) was derived
    from an older reference.  The jcox-au_vmware/unifi_MP_Builder_Design.json
    (2026-05-14) is the ground-truth exchange format and shows testRequest using
    the SAME full response envelope as regular requests — including body, headers,
    and dataModelLists inside result, plus the outer id/log/status/toolkitId fields.

    This function now delegates to _strip_request for a consistent envelope.
    Auth session requests (getSession/releaseSession) that genuinely have no
    dataModelLists will still get an empty list, which is correct.
    """
    return _strip_request(req, adapter_kind=adapter_kind)


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
    # design.buildNumber (sibling to design.design). Emit it from mp.build_number
    # (YAML field, defaults to 1). This allows MPB to distinguish successive
    # re-renders of the same version. See 2026-05-01 renderer gap fix.
    # ------------------------------------------------------------------
    # Confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json (2026-05-14):
    # design.design has id: null and author: "" (empty string) as top-level keys.
    # These were previously omitted; MPB import parser requires them.
    design_block = {
        "design": {
            "id": None,
            "name": pak.get("name", mp.name),
            "type": "HTTP",
            "author": None,
            "description": pak.get("description", ""),
            "version": mp.version,  # base version, no build suffix
        },
        "buildNumber": mp.build_number,
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

    # Always emit sessionSettings — confirmed from jcox-au_vmware/unifi_MP_Builder_Design.json
    # (2026-05-14): CUSTOM-auth MP has sessionSettings: null explicitly present.
    # Earlier rule (strip the key when null, based on mpb_reference_none_auth.json)
    # was wrong; the jcox reference is the correct ground truth.
    ss = auth.get("sessionSettings")
    if ss is None:
        auth["sessionSettings"] = None
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
        "designId": None,
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
    #    Filter out adapter_instance-scope relationships before emission.
    #
    #    MPB's relationship wire format requires non-empty childExpression /
    #    parentExpression — it has no concept of "pure containment" scope.
    #    Adapter-instance hierarchy is handled implicitly by VCF Ops (all
    #    resources created by the same adapter instance are already grouped
    #    under it in the resource tree).  Emitting these with synthetic
    #    expressions (or null ones) causes MPB validation error:
    #    "Child property used in relationship does not exist."
    #
    #    render.py emits adapter_instance rels using a deterministic ID seed
    #    based on the relationship strategy.  We compute those IDs here and
    #    skip the matching entries.  field_match rels are unaffected.
    #
    #    v1.1 follow-up (NOT this fix): synthesize a real constant-match field
    #    so adapter_instance rels survive the wire.  Today: strip them, matching
    #    the pak build_pak() behavior.
    # ------------------------------------------------------------------
    _adapter_instance_rel_ids: set = set()
    _strategy_suffixes = {
        "world_implicit": "world_implicit",
        "synthetic_adapter_instance": "synthetic_adapter",
        "shared_constant_property": "shared_constant",
    }
    _suffix = _strategy_suffixes.get(relationship_strategy, "synthetic_adapter")
    for _rel in mp.relationships:
        if _rel.scope == "adapter_instance":
            _seed = f"{ak}:rel:{_rel.parent}:{_rel.child}:{_suffix}"
            _adapter_instance_rel_ids.add(_make_id(_seed))
            # test_all emits three — add all three seeds
            if relationship_strategy == "test_all":
                for _ts in _strategy_suffixes.values():
                    _adapter_instance_rel_ids.add(
                        _make_id(f"{ak}:rel:{_rel.parent}:{_rel.child}:{_ts}")
                    )

    relationships_list = [
        {"relationship": _strip_relationship(rel)}
        for rel in flat.get("relationships", [])
        if rel.get("id") not in _adapter_instance_rel_ids
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
    #   - type: "HTTP"  — present at top level (confirmed from synology_nas_working_export.json)
    #   - content: []   — Fix 6: every reference pak has this key as an empty list.
    #     GitHub-1.0.0.2.pak and Broadcom both have "content": [] in export.json.
    #     The MPB-built devel reference (none-auth) had it absent in earlier captures,
    #     but the pak-compare [B2] finding ("factory missing top-level keys: ['content']")
    #     against GitHub/Broadcom confirms it must be present.  Emit as empty list.
    # Key order matches the reference for readability, though MPB ignores order.
    exchange = {
        "design": design_block,
        "source": source_block,
        "content": [],
        "objects": objects_list,
        "relationships": relationships_list,
        "events": events_list,
        "requests": requests_list,
    }
    # MPB's import parser rejects flat-format-only keys anywhere in the payload
    # (HTTP 400 "Invalid input format").  Strip the entire tree before returning.
    # Fields removed: example, regex, regexOutput, _renderer_note.
    return _strip_flat_only_fields(exchange)
