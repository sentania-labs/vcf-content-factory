"""Transform a ManagementPackDef design.json render into MPB template.json format.

The MPB adapter runtime reads ``conf/template.json`` at startup via
``BuilderFile.Companion.read()``.  This file uses a substantially different
schema from the design.json that ``render_mp_design_json()`` produces.

Wire format reverse-engineered from:
  - vcfops_managementpacks/adapter_runtime/mpb_synology_nas_template.json
    (ground-truth template built by MPB UI on VCF Ops 9.0.x)
  - context/mpb_template_json_schema.md
    (full field-by-field diff and conversion spec)

Key conversion facts encoded here:
  - Top-level ``version`` field must be ABSENT (design.json has ``"version": 1``).
  - ``pakSettings.version`` must be 4-part (Major.Minor.Patch.Build).
  - ``pakSettings.collectionInterval`` is required (integer, minutes).
  - ``source.globalHeaders`` is ABSENT; contents move into
    ``source.authentication.headers``.
  - ``source.authentication`` restructures completely:
      design: {creds, credentialType, sessionSettings}
      template: {type, credentials, headers, token?}
  - ``source.requests[]`` strips designId/response/chainingSettings;
    adds param id fields; converts chainingSettings to parentRequest.
  - ``source.resources[]`` is the biggest structural gap: replaces
    metricSets/internalObjectInfo with requestedMetrics/label/name/identifiers.
  - ``source.configuration[]`` renames configType->type, defaultValue->default.
  - ``relationships[]`` restructures from objectId references to parent/child
    containers with resourceKind/adapterKind/matchIdentifiers.

Auth type discriminator (design.json has no ``type`` field):
  - design.auth.sessionSettings is not None  ->  template type = "SESSION_TOKEN"
  - design.auth.sessionSettings is None       ->  template type = "CUSTOM"
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from .loader import ManagementPackDef
from .render import render_mp_design_json

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FACTORY_NS = uuid.UUID("4b8d2c10-1f9e-4f4f-9b90-0e8f6a8e2a12")


def _make_id(seed: str) -> str:
    """Derive a stable UUID5 from a seed string (same namespace as render.py)."""
    return str(uuid.uuid5(_FACTORY_NS, seed))


def _snake_case(label: str) -> str:
    """Convert an object type label to snake_case.

    Examples:
      "Access Point" -> "access_point"
      "iSCSI LUN"    -> "iscsi_lun"
      "Storage Pool" -> "storage_pool"
    """
    # Lowercase, replace non-alphanumeric runs with single underscore, strip edges
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _camel_to_snake(name: str) -> str:
    """Convert a camelCase or PascalCase identifier to snake_case.

    Handles consecutive uppercase sequences (e.g. "txRateBps" -> "tx_rate_bps",
    "ipAddress" -> "ip_address", "loadAverage1Min" -> "load_average1_min").
    Also strips any characters that are not alphanumeric (keeps digits as-is).

    Examples:
      "macAddress"         -> "mac_address"
      "cpuUtilizationPct"  -> "cpu_utilization_pct"
      "txRateBps"          -> "tx_rate_bps"
      "uptimeSec"          -> "uptime_sec"
      "loadAverage1Min"    -> "load_average1_min"
      "id"                 -> "id"
      "cpu_pct"            -> "cpu_pct"  (already snake_case, unchanged)
    """
    # Step 1: insert underscore between a run of uppercase letters followed by
    # an uppercase+lowercase sequence (e.g. "IPAddress" -> "IP_Address").
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # Step 2: insert underscore between a lowercase/digit and an uppercase letter.
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    # Step 3: lowercase everything.
    s3 = s2.lower()
    # Step 4: replace any character that is not alphanumeric or underscore with
    # underscore, then strip leading/trailing underscores and collapse runs.
    s4 = re.sub(r"[^a-z0-9_]+", "_", s3).strip("_")
    s5 = re.sub(r"_+", "_", s4)
    return s5


def _derive_key(expr_label: str) -> str:
    """Derive the Aria Ops metric/property key from an expression label.

    For simple attribute paths like ``id``, ``device_type``, the key is
    the full label (converted to snake_case).  For dotted paths like
    ``uplink.txRateBps``, the key is the last segment converted to
    snake_case (``tx_rate_bps``).

    For JMESPath filter expressions (containing ``[?``), the key is derived
    by extracting the final property name before the pipe and any filter
    values for disambiguation:
      ``interfaces.radios[?frequencyGHz==`2.4`].txRetriesPct | [0]``
        -> final property: "txRetriesPct", filter value: "2.4"
        -> key: "tx_retries_pct_2_4"

    The key validation rule is: ``/^[a-z][a-z0-9_]*$/``.

    Examples:
      "id"                    -> "id"
      "device_type"           -> "device_type"
      "macAddress"            -> "mac_address"
      "uplink.txRateBps"      -> "tx_rate_bps"
      "loadAverage1Min"       -> "load_average1_min"
      "interfaces.radios[?frequencyGHz==`2.4`].txRetriesPct | [0]"
                              -> "tx_retries_pct_2_4"
    """
    if "[?" in expr_label:
        # JMESPath expression: extract the final dotted-property name before the pipe.
        # Strip the pipe and everything after it first.
        base = expr_label.split("|")[0].strip()
        # Find the last simple property segment (after the last '.', excluding
        # any filter bracket content).  Split on '.' and take the last non-empty
        # segment that doesn't start with '['.
        segments = base.split(".")
        prop_name = ""
        for seg in reversed(segments):
            # Strip bracket filters: take only the part before any '['
            clean = seg.split("[")[0].strip()
            if clean:
                prop_name = clean
                break
        # Extract filter literal values for disambiguation (e.g. '2.4', '5').
        filter_values = re.findall(r"`([^`]+)`", base)
        # Sanitize filter values: replace non-alphanumeric with underscore
        sanitized_filters = [
            re.sub(r"[^a-z0-9]+", "_", fv.lower()).strip("_")
            for fv in filter_values
        ]
        key = _camel_to_snake(prop_name)
        if sanitized_filters:
            key = key + "_" + "_".join(sanitized_filters)
        # Final safety strip
        key = re.sub(r"[^a-z0-9_]+", "_", key).strip("_")
        return key

    # Simple dotted path: take the last segment, convert camelCase -> snake_case.
    parts = expr_label.split(".")
    last_seg = parts[-1]
    return _camel_to_snake(last_seg)


def _wrap_quote_body(label: str) -> str:
    """Wrap a label in the MPB template BODY expression format.

    Template format: ``"${@@@MPB_QUOTE_BODY <label> @@@MPB_QUOTE}"``

    MPB's runtime expression grammar supports dot-path field navigation and
    the wildcard form ``data.*`` only.  It is backed by Jackson ``JsonNode``
    (``BuilderQueryJsonNodeParserKt``), not JMESPath or Jayway JsonPath.
    Expressions containing filter projections (``[?...]``), pipes (``|``),
    current-element references (``@``), or function calls are silently no-op'd
    by the runtime regardless of any wrap markers.

    The backslash-wrap form (``${@@@MPB_QUOTE_BODY \\<label>\\ @@@MPB_QUOTE}``)
    was a workaround for what was believed to be a grammar-routing limitation.
    Cleanroom confirmation (54 compiled paths across UniFi + phpIPAM reference
    paks, 2026-05-16) established that no such routing exists: MPB always uses
    its simple dot-path parser for BODY expressions, wrap or no wrap.  The wrap
    is therefore removed; all BODY expressions use the plain form universally.

    Use this for expressions that read from the parent/child *response body*
    (listExpression, attributeExpression, metric expressions, parentRequest
    parameters).  Do NOT use for objectBinding.requestMatchIdExpression — see
    _wrap_quote_request_parameters().
    """
    return f"${{@@@MPB_QUOTE_BODY {label} @@@MPB_QUOTE}}"


def _wrap_quote_request_parameters(label: str) -> str:
    """Wrap a label in the MPB template REQUEST_PARAMETERS expression format.

    Template format: ``"${@@@MPB_QUOTE_REQUEST_PARAMETERS <label> @@@MPB_QUOTE}"``

    Use this for objectBinding.requestMatchIdExpression.  The chaining
    parameter name (e.g. "id_device_stats_ap") is substituted into the
    sub-request URL via requestParameters, so it lives in REQUEST_PARAMETERS
    scope — NOT BODY scope.  Using BODY here causes the runtime to look for
    the label in the response body rather than the request parameters, which
    returns no match and silently drops all metrics for that resource.

    Evidence: prod adapter logs 2026-05-16 — every chained request WARN:
      "requestMatchIdExpression ${@@@MPB_QUOTE_BODY id_device_stats_ap
      @@@MPB_QUOTE} returned matches did not return a result."
    MPB-built reference pak (VCFContentFactoryUniFiIntegration-1001.pak,
    template.json) uses @@@MPB_QUOTE_REQUEST_PARAMETERS for this field.
    """
    return f"${{@@@MPB_QUOTE_REQUEST_PARAMETERS {label} @@@MPB_QUOTE}}"


def _convert_session_request(design_req: Dict) -> Dict:
    """Convert a design.json session request (getSession/releaseSession) to template format.

    Strips ``designId``, ``response``, ``chainingSettings``; adds ``id`` to params;
    converts ``body: null`` to ``body: ""``.
    """
    params = []
    for p in design_req.get("params", []) or []:
        params.append({
            "id": p.get("key", ""),
            "key": p.get("key", ""),
            "value": p.get("value", ""),
        })

    headers = []
    for h in design_req.get("headers", []) or []:
        h_key = h.get("key", "")
        headers.append({
            "id": h_key.lower().replace("-", "_"),
            "enabled": True,
            "key": h_key,
            "value": h.get("value", ""),
        })

    return {
        "id": design_req["id"],
        "name": design_req.get("name", ""),
        "path": design_req.get("path", ""),
        "method": design_req.get("method", "GET"),
        "headers": headers,
        "body": design_req.get("body") or "",
        "params": params,
        "parentRequest": None,
        "paging": design_req.get("paging"),
    }


def _convert_authentication(design_auth: Dict, design_global_headers: List[Dict]) -> Dict:
    """Convert design.json authentication block to template.json authentication block.

    Parameters
    ----------
    design_auth:
        The ``source.authentication`` dict from design.json.
        Shape: {creds, credentialType, sessionSettings}
    design_global_headers:
        The ``source.globalHeaders`` list from design.json.
        Moved into ``authentication.headers`` in template format.

    Returns
    -------
    Template-format authentication dict.

    Auth type logic
    ---------------
    - ``sessionSettings`` is not None  ->  ``SESSION_TOKEN``
    - ``sessionSettings`` is None      ->  ``CUSTOM``
      Note: The schema spec documents ``CUSTOM`` as the known value for
      stateless header-based auth.  This is empirically inferred from the
      UniFi Integration MP (http_header preset, credentialType=CUSTOM,
      sessionSettings=null) — no ground-truth template.json exists yet for
      this case.  See context/mpb_template_json_schema.md §4.
    """
    session_settings = design_auth.get("sessionSettings")
    design_creds = design_auth.get("creds", []) or []

    # Convert credentials: rename creds -> credentials, strip usage/value/editable,
    # add key field (= key, falling back to label for backwards compatibility).
    credentials = []
    for c in design_creds:
        credentials.append({
            "id": c["id"],
            "key": c.get("key", c.get("label", "")),
            "label": c.get("label", ""),
            "sensitive": c.get("sensitive", False),
            "description": c.get("description", ""),
        })

    # Convert globalHeaders to authentication.headers.
    # Each header gets id = key, enabled = true.
    headers = []
    for h in design_global_headers:
        h_key = h.get("key", "")
        headers.append({
            "id": h_key,
            "enabled": True,
            "key": h_key,
            "value": h.get("value", ""),
        })

    if session_settings is None:
        # CUSTOM auth — stateless header-based (e.g. http_header preset)
        return {
            "type": "CUSTOM",
            "credentials": credentials,
            "headers": headers,
        }

    # SESSION_TOKEN auth — login/logout flow (e.g. cookie_session preset)
    get_session_design = session_settings.get("getSession")
    release_session_design = session_settings.get("releaseSession")
    session_variables = session_settings.get("sessionVariables", []) or []

    token: Dict = {}
    if get_session_design:
        token["getSession"] = _convert_session_request(get_session_design)
    if release_session_design:
        token["releaseSession"] = _convert_session_request(release_session_design)

    # responseFields: rename sessionVariables -> responseFields, strip usage/example
    response_fields = []
    for sv in session_variables:
        response_fields.append({
            "id": sv["id"],
            "key": sv.get("key", ""),
            "path": sv.get("path", []),
            "location": sv.get("location", "HEADER"),
        })
    token["responseFields"] = response_fields
    token["credentialType"] = "CUSTOM"

    return {
        "type": "SESSION_TOKEN",
        "credentials": credentials,
        "headers": headers,
        "token": token,
    }


def _convert_object_binding(
    design_ob: Optional[Dict],
    metrics_by_id: Dict[str, Dict],
) -> Optional[Dict]:
    """Convert a design.json objectBinding to template.json objectBinding format.

    Design objectBinding types and their template conversions:

    1. None -> None (chain-parent / primary metricSet keeps null)

    2. ATTRIBUTE_TO_PROPERTY (chained secondary, N+1 pattern):
       Design shape:
         {type, matchExpression: {expressionParts: [{label: "<req_attr>", ...}]},
                objectMatchExpression: {expressionParts: [{originId: "<metric_id>",
                                                           originType: "METRIC", ...}]}}
       Template shape:
         {type: "ATTRIBUTE_TO_PROPERTY", id: <uuid>,
          requestMatchIdExpression: "${@@@MPB_QUOTE_REQUEST_PARAMETERS <req_attr> @@@MPB_QUOTE}",
          resourceMatcherExpression: "${<matcher-uuid>}",
          resourceMatchers: [{id: "<matcher-uuid>", type: "IDENTIFIER",
                              key: "<prop_key>", regex: null}]}

       Cross-reference contract (corrected 2026-05-16, prod log evidence):
         - requestMatchIdExpression uses @@@MPB_QUOTE_REQUEST_PARAMETERS format.
           The chaining parameter name (e.g. "id_device_stats_ap") is the value
           injected into the sub-request URL path via requestParameters — it
           lives in REQUEST_PARAMETERS scope, NOT in the response body.
           Using @@@MPB_QUOTE_BODY causes the runtime to search the body,
           returns no match, and silently drops all metrics for that resource.
           Prod evidence (2026-05-16): every chained request logged WARN
           "requestMatchIdExpression ${@@@MPB_QUOTE_BODY id_device_stats_ap
           @@@MPB_QUOTE} returned matches did not return a result."
           MPB-built reference (VCFContentFactoryUniFiIntegration-1001.pak,
           template.json) uses @@@MPB_QUOTE_REQUEST_PARAMETERS throughout.
         - resourceMatcherExpression uses ${<uuid>} format — the UUID must
           exactly match resourceMatchers[0].id.  Using @@@MPB_QUOTE_BODY here
           causes BuilderFileParseException: "fields referenced in the resource
           expression but do not have a matching ID in match identifiers".
         - resourceMatchers[].id is the stable UUID assigned to this matcher
           (generated via _make_id); its ``key`` is the derived property key.

    3. CHAINED_REQUEST:
       Template shape: {type: "CHAINED_REQUEST", id: <uuid>}

    Wire format captured in context/mpb_template_json_schema.md section 6.3.
    """
    if design_ob is None:
        return None

    # Handle both "type" (INTERNAL bindings) and "objectBindingType" (ARIA_OPS bindings).
    # ARIA_OPS objectBinding uses "objectBindingType" as the discriminator key;
    # INTERNAL uses "type".  Both map to the same template conversion logic.
    ob_type = design_ob.get("type") or design_ob.get("objectBindingType", "ATTRIBUTE_TO_PROPERTY")

    if ob_type == "CHAINED_REQUEST":
        match_expr_id = design_ob.get("matchExpression", {}).get("id", "")
        return {
            "type": "CHAINED_REQUEST",
            "id": _make_id(f"chain-ob-{match_expr_id}"),
        }

    # ATTRIBUTE_TO_PROPERTY
    match_expr = design_ob.get("matchExpression", {})
    obj_match_expr = design_ob.get("objectMatchExpression", {})

    # Request side: the JSON attribute path from the secondary response.
    # matchExpression.expressionParts[0].label is the raw field name (e.g. "id").
    match_parts = match_expr.get("expressionParts", [])
    request_attr = match_parts[0].get("label", "") if match_parts else ""

    # Resource side: look up the metric to get the property key.
    # objectMatchExpression.expressionParts[0].originId is the metric wire-ID;
    # look it up, extract its expression label, then derive the property key.
    obj_parts = obj_match_expr.get("expressionParts", [])
    if obj_parts:
        origin_id = obj_parts[0].get("originId", "")
        referenced_metric = metrics_by_id.get(origin_id)
        if referenced_metric:
            resource_prop = referenced_metric.get("key") or _derive_key(_get_metric_expr_label(referenced_metric))
        else:
            # Fallback: use the request attribute label (often identical for N+1 pattern)
            resource_prop = _derive_key(request_attr)
    else:
        resource_prop = _derive_key(request_attr)

    # Stable UUID for this resourceMatcher entry.
    # resourceMatcherExpression must be "${<matcher_id>}" — NOT @@@MPB_QUOTE_BODY
    # format.  The parser resolves the UUID inside ${...} against resourceMatchers[].id
    # directly.  Using @@@MPB_QUOTE_BODY here causes the parser to look for a matcher
    # whose id equals the literal string "@@@MPB_QUOTE_BODY id @@@MPB_QUOTE", which
    # will never match.
    matcher_id = _make_id(f"http-ob-matcher-{match_expr.get('id', '')}")

    return {
        "type": "ATTRIBUTE_TO_PROPERTY",
        "id": _make_id(f"http-ob-{match_expr.get('id', '')}"),
        "requestMatchIdExpression": _wrap_quote_request_parameters(request_attr),
        "resourceMatcherExpression": f"${{{matcher_id}}}",
        "resourceMatchers": [
            {
                "id": matcher_id,
                "type": "IDENTIFIER",
                "key": resource_prop,
                "regex": None,
            }
        ],
    }


def _convert_request(design_req: Dict, adapter_kind: str) -> Dict:
    """Convert one design.json request to template.json request format.

    Changes:
      - Strip ``designId``, ``response``
      - Add ``id`` field to each param (= ``key``)
      - Convert ``body: null`` to ``body: ""``
      - Convert ``chainingSettings`` to ``parentRequest``; remove ``chainingSettings``
    """
    # params: add id = key to each param
    params = []
    for p in design_req.get("params", []) or []:
        params.append({
            "id": p.get("key", ""),
            "key": p.get("key", ""),
            "value": p.get("value", ""),
        })

    # paging: keep as-is (design.json paging is always None for factory-rendered designs)
    paging = design_req.get("paging")

    # headers: keep as-is
    headers = design_req.get("headers", []) or []

    # chainingSettings -> parentRequest
    chaining = design_req.get("chainingSettings")
    parent_request: Optional[Dict] = None
    if chaining:
        parent_request = _convert_chaining_settings(chaining, adapter_kind)

    return {
        "id": design_req["id"],
        "name": design_req.get("name", ""),
        "path": design_req.get("path", ""),
        "method": design_req.get("method", "GET"),
        "headers": headers,
        "body": design_req.get("body") or "",
        "params": params,
        "parentRequest": parent_request,
        "paging": paging,
    }


def _convert_chaining_settings(chaining: Dict, adapter_kind: str) -> Dict:
    """Convert design.json chainingSettings to template.json parentRequest format.

    Design chainingSettings:
      {
        "id": "<uuid>",
        "parentRequestId": "<uuid>",
        "baseListId": "data.volumes.*",
        "params": [{
          "id": "<uuid>",
          "key": "volume_id",          <- request parameter name (used in path)
          "label": "volume_id",
          "usage": "${requestParameters.volume_id}",
          "listId": "data.volumes.*",
          "example": "",
          "attributeExpression": {
            "expressionParts": [{"label": "id", ...}]  <- field name in parent response
          }
        }]
      }

    Template parentRequest:
      {
        "id": "<uuid>",
        "requestId": "<parent-request-uuid>",
        "parameters": [{
          "id": "volume_id",
          "listExpression": "${@@@MPB_QUOTE_BODY data.volumes.* @@@MPB_QUOTE}",
          "attributeExpression": "${@@@MPB_QUOTE_BODY id @@@MPB_QUOTE}"
        }]
      }

    Critical distinction (bug fix 2026-05-09):
      ``id`` (the ``parameters[].id``) is the request parameter name used in the
      URL path (e.g. ``${requestParameters.device_id}``).
      ``attributeExpression`` is the field name to extract from each row of the
      parent response — it comes from
      ``chainingSettings.params[].attributeExpression.expressionParts[0].label``,
      which is the raw JSON field path (e.g. ``"id"``), NOT the parameter name.

      When ``from_attribute`` != parameter name (e.g. YAML has
      ``bind: [{name: device_id, from_attribute: id}]``), these differ.
      Using the parameter name in ``attributeExpression`` causes the runtime to
      look for a non-existent field in the parent response, yielding empty
      substitution and broken URLs (zero devices discovered).

      The Synology MP was not affected because its sole chain binding has
      ``key == from_attribute == "volume_id"``, masking the bug.
    """
    base_list_id = chaining.get("baseListId", "")
    parameters = []
    for cp in (chaining.get("params") or []):
        param_key = cp.get("key", "")
        # listExpression: wrap baseListId
        list_expr = _wrap_quote_body(base_list_id)
        # attributeExpression: wrap the field name from the parent response.
        # This is attributeExpression.expressionParts[0].label — the raw JSON
        # field path — NOT the parameter name (cp["key"]).  These only coincide
        # when the YAML bind entry has from_attribute == name (e.g. Synology's
        # volume_id == volume_id).  For UniFi, from_attribute="id" != name="device_id".
        attr_parts = (
            cp.get("attributeExpression", {}).get("expressionParts") or []
        )
        if attr_parts:
            attr_field = attr_parts[0].get("label", param_key)
        else:
            # Fallback: if no expressionParts, use the param key (Synology-safe
            # since key == field name there)
            attr_field = param_key
        attr_expr = _wrap_quote_body(attr_field)
        parameters.append({
            "id": param_key,
            "listExpression": list_expr,
            "attributeExpression": attr_expr,
        })

    return {
        "id": chaining["id"],
        "requestId": chaining.get("parentRequestId", ""),
        "parameters": parameters,
    }


def _build_all_metrics_by_id(design_resources: List[Dict]) -> Dict[str, Dict]:
    """Build a flat lookup: metric_id -> metric dict for all resources."""
    result: Dict[str, Dict] = {}
    for r in design_resources:
        for ms in r.get("metricSets", []):
            for m in ms.get("metrics", []):
                result[m["id"]] = m
    return result


def _get_metric_expr_label(metric: Dict) -> str:
    """Extract expressionParts[0].label from a design.json metric."""
    expr = metric.get("expression")
    if not expr:
        return ""
    parts = expr.get("expressionParts", [])
    if parts:
        return parts[0].get("label", "")
    return ""


def _convert_metric(design_metric: Dict) -> Dict:
    """Convert one design.json metric to template.json metric format.

    Changes:
      - ``expression`` object -> ``expression`` string (``@@@MPB_QUOTE_BODY`` format)
      - ``usage`` -> ``property`` (bool: usage == "PROPERTY")
      - ``isKpi`` -> ``kpi``
      - ``dataType``: ``NUMBER`` -> ``DECIMAL``
      - ``unit``: empty string -> null
      - Add ``key`` field (last dot-segment of expression label)
    """
    expr_label = _get_metric_expr_label(design_metric)
    key = design_metric.get("key") or _derive_key(expr_label)
    expression_str = _wrap_quote_body(expr_label) if expr_label else ""

    data_type = design_metric.get("dataType", "STRING")
    if data_type == "NUMBER":
        data_type = "DECIMAL"

    unit = design_metric.get("unit")
    if unit == "":
        unit = None

    return {
        "id": design_metric["id"],
        "expression": expression_str,
        "key": key,
        "label": design_metric.get("label", ""),
        "dataType": data_type,
        "property": design_metric.get("usage") == "PROPERTY",
        "kpi": design_metric.get("isKpi", False),
        "groups": design_metric.get("groups", []),
        "unit": unit,
        "timeseries": design_metric.get("timeseries"),
    }


def _convert_resource(
    design_resource: Dict,
    adapter_kind: str,
) -> Dict:
    """Convert one design.json resource to template.json resource format.

    Changes (see context/mpb_template_json_schema.md §6):
      - Decompose ``internalObjectInfo`` into ``label``, ``resourceKind``,
        ``name``, ``identifiers``, ``icon``.
      - Rename ``metricSets`` -> ``requestedMetrics`` with deep conversion.
      - Rename ``isListObject`` -> ``isListResource``.
      - Remove ``type``, ``designId``, ``ariaOpsConf``, ``internalObjectInfo``.
      - Add ``metricGroups: {}``.

    ARIA_OPS resources: these push metrics onto existing Aria Ops resource kinds
    and do not define their own resourceKind in the adapter.  For template.json
    they are rendered with an empty label/resourceKind derived from ariaOpsConf
    and no identifiers/name (the target resource's identity is used).
    """
    is_aria_ops = design_resource.get("type") == "ARIA_OPS"

    if is_aria_ops:
        aria_conf = design_resource.get("ariaOpsConf") or {}
        label = aria_conf.get("objectTypeLabel", "")
        resource_kind = f"{aria_conf.get('adapterType', adapter_kind)}_{_snake_case(aria_conf.get('objectType', ''))}"
        icon = ""
    else:
        info = design_resource.get("internalObjectInfo", {})
        label = info.get("objectTypeLabel", "")
        resource_kind = f"{adapter_kind}_{_snake_case(label)}"
        icon = info.get("icon", "")

    info = design_resource.get("internalObjectInfo", {})
    is_list_resource = design_resource.get("isListObject", True)

    # Build metric lookup for this resource (needed for identifiers + name expr)
    metrics_by_id: Dict[str, Dict] = {}
    for ms in design_resource.get("metricSets", []):
        for m in ms.get("metrics", []):
            metrics_by_id[m["id"]] = m

    # name expression: from nameMetricExpression.expressionParts[0].originId (metric ID)
    name_expr_design = info.get("nameMetricExpression")
    name_obj: Optional[Dict] = None
    if name_expr_design:
        expr_id = name_expr_design.get("id")
        parts = name_expr_design.get("expressionParts", [])
        if parts:
            # originId is the metric ID that provides the name
            ref_id = parts[0].get("originId")
            name_obj = {
                "id": expr_id,
                "type": "PROPERTY",
                "refId": ref_id,
            }

    # identifiers: for each id in identifierIds, look up the metric and derive key
    identifier_ids = info.get("identifierIds", []) or []
    identifiers = []
    for ident_id in identifier_ids:
        m = metrics_by_id.get(ident_id)
        if m:
            key = m.get("key") or _derive_key(_get_metric_expr_label(m))
        else:
            # Fallback: use the id as key (should not happen if design is consistent)
            key = ident_id
        identifiers.append({
            "id": ident_id,
            "key": key,
            "propertyKey": key,
        })

    # requestedMetrics: convert from metricSets
    requested_metrics = []
    for ms in design_resource.get("metricSets", []):
        ms_id = ms.get("id")
        request_id = ms.get("requestId")
        list_id = ms.get("listId", "")
        object_binding = ms.get("objectBinding")

        # Convert metrics
        converted_metrics = [_convert_metric(m) for m in ms.get("metrics", [])]

        rm: Dict[str, Any] = {
            "id": ms_id,
            "requestId": request_id,
            "metrics": converted_metrics,
            # Convert objectBinding from design format to template format.
            # Primary/chain-parent metricSets keep null (at most one null per
            # resource is allowed by BuilderFile.Companion.read()).
            # Chained secondary metricSets carry ATTRIBUTE_TO_PROPERTY bindings
            # that tell the runtime how to stitch stats responses to the correct
            # device resource.  The design-format fields (matchExpression,
            # objectMatchExpression) are replaced by the flat template fields
            # (requestMatchIdExpression, resourceMatcherExpression).
            "objectBinding": _convert_object_binding(object_binding, metrics_by_id),
        }

        # Chain-anchor metricSets are now guaranteed non-empty by the stub
        # mechanism in render.py (chain_anchor_stub field on MetricSetDef).
        # The previous guard that skipped empty REQUESTED_METRIC blocks
        # (task #18/#20) has been reverted: the Dell pattern requires the parent
        # object to carry a metricSet binding for every chain-anchor request so
        # that MPB's Relationships tab can infer the parent→child ownership.
        # Stripping the binding causes MPB to treat the anchored request as a
        # free-floating root with no chaining and no relationship edges.
        # Non-empty is now enforced by stub injection in render.py, so
        # BuilderFile.Companion.read() will never see an empty metrics array.
        # pak_validator.py Rule 8 remains as a regression gate.

        # listExpression: only for list resources with a non-"base" listId
        # Scalar resources (world/singleton, listId="base") omit listExpression
        if is_list_resource and list_id and list_id != "base":
            rm["listExpression"] = _wrap_quote_body(list_id)

        requested_metrics.append(rm)

    return {
        "id": design_resource["id"],
        "label": label,
        "resourceKind": resource_kind,
        "name": name_obj,
        "identifiers": identifiers,
        "isListResource": is_list_resource,
        "icon": icon,
        "requestedMetrics": requested_metrics,
        "metricGroups": {},
    }


def _convert_configuration(design_config: Dict) -> Dict:
    """Convert one design.json configuration entry to template.json format.

    Changes (see context/mpb_template_json_schema.md §7):
      - Use ``id`` as ``key`` (mpb_-prefixed key, not the short alias)
      - Rename ``configType`` -> ``type``, ``NUMBER`` -> ``INTEGER``
      - Rename ``defaultValue`` -> ``default``, stringify the value
      - Remove ``usage``, ``value``, ``editable``
      - Keep ``options`` if present
    """
    config_type = design_config.get("configType", "STRING")
    if config_type == "NUMBER":
        config_type = "INTEGER"

    default_value = design_config.get("defaultValue")
    # Template default is always a string (or empty string)
    if default_value is None:
        default_str = ""
    else:
        default_str = str(default_value)

    # SINGLE_SELECTION requires a non-empty default (BuilderFile.Companion.read()
    # rejects an empty string for selection fields).  If the design defaultValue
    # was not set, pick "Verify" when available (matching the Synology working
    # template ground truth), otherwise fall back to the first option.
    if config_type == "SINGLE_SELECTION" and not default_str:
        options = design_config.get("options") or []
        if "Verify" in options:
            default_str = "Verify"
        elif options:
            default_str = str(options[0])

    result: Dict[str, Any] = {
        "id": design_config.get("id", ""),
        "key": design_config.get("id", ""),  # use the mpb_-prefixed id as key
        "label": design_config.get("label", ""),
        "advanced": design_config.get("advanced", False),
        "default": default_str,
        "description": design_config.get("description", ""),
        "type": config_type,
    }

    # options: include only for SINGLE_SELECTION types
    options = design_config.get("options")
    if options is not None:
        result["options"] = options

    return result


def _convert_relationship(
    design_rel: Dict,
    resources_by_id: Dict[str, Dict],
    adapter_kind: str,
    all_metrics_by_id: Dict[str, Dict],
) -> Optional[Dict]:
    """Convert one design.json relationship to template.json relationship format.

    Design format uses parentObjectId/childObjectId + expression objects.
    Template format uses parent/child containers with resourceKind, adapterKind,
    resourceKindName, expression string, matchIdentifiers.

    Returns None if the relationship cannot be converted (missing resource refs
    or expression parts).

    Identifier type:
      - Parent side: ``type: "IDENTIFIER"`` (it IS the identifier on the parent)
      - Child  side: ``type: "PROPERTY"``   (it is a property on the child)
    """
    rel_id = design_rel.get("id", "")

    parent_obj_id = design_rel.get("parentObjectId")
    child_obj_id = design_rel.get("childObjectId")
    parent_expr = design_rel.get("parentExpression")
    child_expr = design_rel.get("childExpression")

    parent_resource = resources_by_id.get(parent_obj_id)
    child_resource = resources_by_id.get(child_obj_id)

    if not parent_resource or not child_resource:
        return None
    if not parent_expr or not child_expr:
        # Cannot build matchIdentifiers without expression info
        return None

    parent_label = parent_resource["internalObjectInfo"]["objectTypeLabel"]
    child_label = child_resource["internalObjectInfo"]["objectTypeLabel"]
    parent_rk = f"{adapter_kind}_{_snake_case(parent_label)}"
    child_rk = f"{adapter_kind}_{_snake_case(child_label)}"

    def _get_match_info(expr: Dict) -> Optional[Dict]:
        """Extract matchIdentifier info from an expression dict.

        The expression's expressionParts[0].originId is the metric ID when
        originType == "METRIC".  Look up the metric to get its expression label
        (the field path), then derive the key from the last dot-segment.

        Returns {id, key, expr_id} or None on failure.
        """
        parts = expr.get("expressionParts", [])
        if not parts:
            return None
        part = parts[0]
        origin_id = part.get("originId")
        origin_type = part.get("originType")

        if origin_type == "METRIC" and origin_id:
            # Look up the metric to get its field key
            m = all_metrics_by_id.get(origin_id)
            if m:
                key = m.get("key") or _derive_key(_get_metric_expr_label(m))
            else:
                # Fallback: derive from expression text label
                key = _derive_key(part.get("label", origin_id))
        else:
            # ATTRIBUTE or other: use expression label directly
            label = part.get("label", "")
            key = _derive_key(label)

        # Use a stable id for the matchIdentifier: derive from the rel id + side
        # (the template reference uses hand-assigned UUIDs; we generate stable ones)
        return {"key": key}

    parent_match = _get_match_info(parent_expr)
    child_match = _get_match_info(child_expr)

    if not parent_match or not child_match:
        return None

    # Stable IDs for parent/child container and their matchIdentifier
    parent_container_id = _make_id(f"{rel_id}:parent:container")
    parent_mi_id = _make_id(f"{rel_id}:parent:matchIdentifier")
    child_container_id = _make_id(f"{rel_id}:child:container")
    child_mi_id = _make_id(f"{rel_id}:child:matchIdentifier")

    parent_mi = {
        "id": parent_mi_id,
        "type": "IDENTIFIER",
        "key": parent_match["key"],
        "regex": None,
    }
    child_mi = {
        "id": child_mi_id,
        "type": "PROPERTY",
        "key": child_match["key"],
        "regex": None,
    }

    return {
        "id": rel_id,
        "parent": {
            "id": parent_container_id,
            "resourceKind": parent_rk,
            "adapterKind": adapter_kind,
            "resourceKindName": parent_label,
            "expression": f"${{{parent_mi_id}}}",
            "matchIdentifiers": [parent_mi],
        },
        "child": {
            "id": child_container_id,
            "resourceKind": child_rk,
            "adapterKind": adapter_kind,
            "resourceKindName": child_label,
            "expression": f"${{{child_mi_id}}}",
            "matchIdentifiers": [child_mi],
        },
        "caseSensitive": design_rel.get("caseSensitive", True),
    }


def _aria_ops_bind_metric_key(aria_conf: Dict) -> Optional[str]:
    """Extract the VMWARE property key used for ARIA_OPS stitching.

    The ariaOpsConf.metricSet contains a metric with usage=ARIA_OPS_REFERENCE_ID.
    Its expression.expressionParts[0].originId is the VMWARE property identifier
    key (e.g. "VMEntityName", "VMEntityObjectID").

    This key must be used as resourceMatchers[].key in the template objectBinding
    so the runtime knows which VMWARE property to match against.
    """
    ms = aria_conf.get("metricSet") or {}
    for metric in ms.get("metrics", []):
        if metric.get("usage") == "ARIA_OPS_REFERENCE_ID":
            parts = (metric.get("expression") or {}).get("expressionParts", [])
            if parts:
                return parts[0].get("originId")
    return None


def _patch_aria_ops_resource_matchers(
    requested_metrics: List[Dict],
    bind_key: Optional[str],
) -> List[Dict]:
    """Patch resourceMatchers[].key in objectBinding to use the VMWARE property key.

    _convert_object_binding falls back to the request-attribute label when the
    objectMatchExpression's originId is not found in metrics_by_id (which only
    covers metricSets metrics, not ariaOpsConf metrics).  For ARIA_OPS external
    resources the correct key is the VMWARE identifier property (e.g.
    "VMEntityName", "VMEntityObjectID") from ariaOpsConf, not the API field label.

    Confirmed from MPB-built vSphere Storage Paths template.json (2026-05-15):
      HostSystem: resourceMatchers[0].key = "VMEntityName"
      Datastore:  resourceMatchers[0].key = "VMEntityObjectID"
    """
    if not bind_key:
        return requested_metrics
    patched = []
    for rm in requested_metrics:
        rm = dict(rm)
        ob = rm.get("objectBinding")
        if ob and isinstance(ob, dict):
            ob = dict(ob)
            matchers = ob.get("resourceMatchers", [])
            if matchers:
                matchers = [dict(m) for m in matchers]
                matchers[0]["key"] = bind_key
                ob["resourceMatchers"] = matchers
            rm["objectBinding"] = ob
        patched.append(rm)
    return patched


def _convert_aria_ops_external_resource(
    design_resource: Dict,
    mp_display_name: str,
) -> Dict:
    """Convert an ARIA_OPS design resource to template.json externalResources entry.

    ARIA_OPS objects stitch metrics onto existing Aria Ops resource kinds
    (e.g. VMWARE/HostSystem, VMWARE/Datastore).  In template.json they appear
    in source.externalResources[] rather than source.resources[].

    Shape (confirmed from MPB-built vSphere Storage Paths template.json, 2026-05-15;
    see context/mp_format_comparison_2026_05_15.md §item 1):

      {
        "id":               "<object_id>",          # same as resources[].id
        "adapterKind":      "VMWARE",               # from ariaOpsConf.adapterType
        "resourceKind":     "Datastore",            # from ariaOpsConf.objectType (raw, no prefix)
        "resourceKindName": "Datastore",            # from ariaOpsConf.objectTypeLabel
        "isListResource":   true,                   # always true for ARIA_OPS
        "requestedMetrics": [...],                  # same conversion as _convert_resource
        "metricGroups": {
          "<mp_display_name>": {
            "id": "<mp_display_name>",
            "key": "<mp_display_name>",
            "childGroups": {}
          }
        }
      }

    Note: resourceKind is the raw object type (e.g. "Datastore"), NOT the
    adapter-prefixed form ("VMWARE_datastore") used in source.resources[].

    Note: resourceMatchers[].key in each objectBinding is patched to use the
    VMWARE property identifier key (e.g. "VMEntityName") from ariaOpsConf,
    since _convert_object_binding cannot resolve this key from metricSets alone.
    """
    aria_conf = design_resource.get("ariaOpsConf") or {}
    adapter_kind_external = aria_conf.get("adapterType", "")
    resource_kind_raw = aria_conf.get("objectType", "")
    resource_kind_label = aria_conf.get("objectTypeLabel", resource_kind_raw)

    # requestedMetrics: reuse _convert_resource which handles ARIA_OPS resources
    # and produces the correct metric/binding conversion.  We only need the
    # requestedMetrics sub-field from its output.
    converted = _convert_resource(design_resource, adapter_kind_external)
    requested_metrics = converted.get("requestedMetrics", [])

    # Patch resourceMatchers[].key to use the VMWARE property identifier key.
    # _convert_object_binding falls back to the request-field label for ARIA_OPS
    # because the ariaOpsConf bind metric UUID is not in the metricSets lookup.
    bind_key = _aria_ops_bind_metric_key(aria_conf)
    requested_metrics = _patch_aria_ops_resource_matchers(requested_metrics, bind_key)

    # metricGroups: one entry keyed by the MP display name, matching MPB's output.
    # This tells the runtime which metric group the pushed metrics belong to.
    metric_groups = {
        mp_display_name: {
            "id": mp_display_name,
            "key": mp_display_name,
            "childGroups": {},
        }
    }

    return {
        "id": design_resource["id"],
        "adapterKind": adapter_kind_external,
        "resourceKind": resource_kind_raw,
        "resourceKindName": resource_kind_label,
        "isListResource": True,
        "requestedMetrics": requested_metrics,
        "metricGroups": metric_groups,
    }


# ---------------------------------------------------------------------------
# Main transform function
# ---------------------------------------------------------------------------

def render_template_json(
    mp: ManagementPackDef,
    relationship_strategy: str = "synthetic_adapter_instance",
) -> dict:
    """Transform a ManagementPackDef into the MPB template.json format.

    Calls ``render_mp_design_json()`` to obtain the design dict, then applies
    section-by-section transformations to produce the template format expected
    by ``BuilderFile.Companion.read()`` in the MPB adapter runtime.

    Parameters
    ----------
    mp:
        The loaded management pack definition.
    relationship_strategy:
        Passed through to ``render_mp_design_json()``.

    Returns
    -------
    dict
        Template-format dict (not serialized).

    Raises
    ------
    ValueError
        If the design dict is structurally inconsistent.
    """
    design = render_mp_design_json(mp, relationship_strategy=relationship_strategy)

    ak = mp.adapter_kind
    design_source = design["source"]

    # ---- pakSettings -------------------------------------------------------
    pak_settings_design = design["pakSettings"]
    # version: 3-part -> 4-part by appending .build_number
    version_3part = pak_settings_design.get("version", "1.0.0")
    version_4part = f"{version_3part}.{mp.build_number}"
    # collectionInterval: from YAML collection_interval if present, else default 5
    collection_interval = getattr(mp, "collection_interval", None) or 5

    pak_settings_template = {
        "author": pak_settings_design.get("author", ""),
        "name": pak_settings_design.get("name", ""),
        "adapterKind": pak_settings_design.get("adapterKind", ""),
        "version": version_4part,
        "description": pak_settings_design.get("description", ""),
        "icon": pak_settings_design.get("icon", "default.png"),
        "collectionInterval": collection_interval,
    }

    # ---- authentication ----------------------------------------------------
    design_auth = design_source.get("authentication", {})
    global_headers = design_source.get("globalHeaders", []) or []
    auth_template = _convert_authentication(design_auth, global_headers)

    # ---- configuration -----------------------------------------------------
    config_template = [
        _convert_configuration(c)
        for c in (design_source.get("configuration") or [])
    ]

    # ---- requests ----------------------------------------------------------
    design_requests = design_source.get("requests", {}) or {}
    requests_template: Dict[str, Dict] = {}
    for req_id, design_req in design_requests.items():
        converted = _convert_request(design_req, ak)
        requests_template[req_id] = converted

    # ---- resources ---------------------------------------------------------
    # ARIA_OPS objects are excluded from source.resources[] in template.json.
    # They stitch onto existing Aria Ops resource kinds (e.g. HostSystem,
    # Datastore) and do not define their own adapter-owned resourceKind.
    # Including them in resources[] would produce resourceKind values like
    # "VMWARE_hostsystem" which are not mpb_-prefixed and fail the pak runtime
    # validator.  Confirmed from MPB-built reference pak (tmp/devel_mpb_built.pak):
    # source.resources == [] despite 2 ARIA_OPS objects in the design.
    # ARIA_OPS objects go into source.externalResources[] instead (see below).
    design_resources = design_source.get("resources", []) or []
    resources_template = [
        _convert_resource(r, ak)
        for r in design_resources
        if r.get("type") != "ARIA_OPS"
    ]

    # Build lookup for relationships: resource id -> design resource dict
    resources_by_id: Dict[str, Dict] = {
        r["id"]: r for r in design_resources
    }

    # ---- relationships -----------------------------------------------------
    all_metrics_by_id = _build_all_metrics_by_id(design_resources)
    design_rels = design.get("relationships", []) or []
    relationships_template = []
    for rel in design_rels:
        converted_rel = _convert_relationship(
            rel, resources_by_id, ak, all_metrics_by_id
        )
        if converted_rel is not None:
            relationships_template.append(converted_rel)

    # ---- externalResources -------------------------------------------------
    # ARIA_OPS objects appear in template.json's externalResources[] (not
    # resources[]).  Convert each ARIA_OPS design resource into the template
    # externalResources shape (adapterKind, resourceKind, resourceKindName,
    # isListResource, requestedMetrics, metricGroups).
    # Fix 2026-05-15: previously passed through design-format list unchanged;
    # template runtime requires converted format with requestedMetrics.
    # See context/mp_format_comparison_2026_05_15.md §item 1.
    aria_ops_resources = [r for r in design_resources if r.get("type") == "ARIA_OPS"]
    mp_display_name = pak_settings_template.get("name", "")
    external_resources_template = [
        _convert_aria_ops_external_resource(r, mp_display_name)
        for r in aria_ops_resources
    ]

    # ---- source section ----------------------------------------------------
    source_template: Dict[str, Any] = {
        "basePath": design_source.get("basePath", ""),
        "testRequestId": design_source.get("testRequestId"),
        "authentication": auth_template,
        "configuration": config_template,
        "requests": requests_template,
        "resources": resources_template,
        "externalResources": external_resources_template,
        # Always emit empty events list in template.json.  The pak runtime
        # parses ALL json files in the adapter conf directory; events in
        # design-import format (from render_mp_design_json) cause a schema
        # mismatch and pak install failure.  MPB-built reference pak has
        # source.events: [] in template.json.  Events can be re-enabled once
        # a pak-runtime event wire format is confirmed.
        "events": [],
        "type": design_source.get("type", "HTTP"),
    }

    # ---- top-level (NO version field) --------------------------------------
    return {
        "id": design["id"],
        "name": design["name"],
        "pakSettings": pak_settings_template,
        "source": source_template,
        "constants": design.get("constants", []),
        "relationships": relationships_template,
    }
