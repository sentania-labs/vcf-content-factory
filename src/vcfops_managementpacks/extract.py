"""Extract an MPB UI exchange-format JSON back to a factory YAML.

This is the reverse of render_export.py: read a working MPB design JSON
(as exported from MPB UI or unpacked from a .pak) and produce a YAML
definition that round-trips through render-export to a semantically
equivalent design.

Semantic equivalence is the bar — byte-for-byte match is a non-goal
because the exchange format contains UUIDs minted by MPB that differ from
the factory's UUID5-derived IDs.

USAGE:
    python3 -m vcfops_managementpacks extract \\
        --from context/mpb_wire_reference/synology_nas_working_export.json \\
        --out /tmp/extracted.yaml

The output YAML is a starting point for review, not a drop-in replacement.
The author should:
  1. Review all extracted field labels (metric labels → metric keys).
  2. Verify list_path values (derived from metricSet.listId in the exchange).
  3. Add any business-logic markup (kpi: true, units, etc.) that the
     exchange format does not carry.
  4. Confirm response_path (derived from the DML id prefix before the
     list component).

WIRE FORMAT NOTES (from context/mpb_wire_reference/synology_nas_working_export.json):
  - top-level keys: type, design, source, objects, relationships, events, requests
  - requests[].request.response.result.dataModelLists[].id encodes the full
    JSON path + .* suffix for list DMLs (e.g. "data.volumes.*") or "base"
    for singleton/world DMLs.
  - metricSets[].listId on objects gives the DML id this metricSet uses.
  - metricSets[].requestId links the metricSet to a request by id.
  - Relationship expressions point at metric originId (metric id on the object).
  - chainingSettings on a request encodes the parent request + bind mapping.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(label: str) -> str:
    """Convert a human label to a snake_case key."""
    s = label.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "field"


def _dml_to_list_path(dml_id: str, response_path: str) -> str:
    """Derive list_path from a DML id and response_path.

    DML id conventions (confirmed from working export 2026-04-21):
      "base"            → list_path = ""   (world/singleton)
      "data.volumes.*"  → strip response_path prefix + ".*" suffix
                          → list_path = "volumes"
      "data.space.volume.*" → list_path = "space.volume"

    The list_path is the portion between response_path and ".*".
    If the DML id starts with response_path + ".", strip that prefix.
    Then strip the trailing ".*".
    """
    if dml_id == "base":
        return ""

    work = dml_id
    if work.endswith(".*"):
        work = work[:-2]

    rp = (response_path or "").strip()
    if rp and work.startswith(rp + "."):
        work = work[len(rp) + 1:]
    elif rp and work == rp:
        work = ""

    return work


def _infer_response_path(dml_ids: List[str]) -> str:
    """Infer response_path from a request's DML ids.

    The primary (non-base, non-wildcard-only) DML id for list objects is
    typically "data.<list>.*".  We strip the ".*" and take the first
    dotted component if it starts with "data".

    For world/singleton objects (only "base" DML), response_path is "data"
    by convention (the most common Synology pattern).
    """
    non_base = [d for d in dml_ids if d != "base" and not d.startswith("*")]
    if not non_base:
        return "data"
    # Sort by specificity (fewest wildcards first) to get the canonical one
    canonical = sorted(non_base, key=lambda x: x.count("*"))[0]
    # Strip trailing .*
    if canonical.endswith(".*"):
        canonical = canonical[:-2]
    # Take the leading component
    parts = canonical.split(".")
    if parts[0] == "data":
        return "data"
    return parts[0] if parts else "data"


def _metric_label_to_key(label: str) -> str:
    """Convert a metric label to a snake_case key.

    Labels come from the MPB UI (title-case human labels like "Pool Path").
    We need a stable identifier. Snake-case the label.
    """
    return _slug(label)


def _find_metric_id(objects: List[Dict], target_id: str) -> Optional[Dict]:
    """Find a metric dict by id across all objects."""
    for obj_wrap in objects:
        obj = obj_wrap["object"]
        for ms in obj.get("metricSets", []):
            for m in ms.get("metrics", []):
                if m.get("id") == target_id:
                    return m
    return None


def _build_request_id_map(exchange: Dict) -> Dict[str, str]:
    """Return request_id → request_name mapping."""
    result = {}
    for r in exchange.get("requests", []):
        req = r["request"]
        result[req["id"]] = req["name"]
    # Also check test request in source
    src = exchange.get("source", {}).get("source", {})
    tr = src.get("testRequest")
    if tr:
        result[tr["id"]] = "__test_request__"
    return result


def _build_metric_id_map(exchange: Dict) -> Dict[str, Tuple[str, str, str]]:
    """Return metric_id → (object_label, metric_label, metric_key) mapping.

    metric_key is a snake_case slug derived from the metric label.
    """
    result = {}
    for obj_wrap in exchange.get("objects", []):
        obj = obj_wrap["object"]
        obj_label = obj.get("internalObjectInfo", {}).get("objectTypeLabel", "")
        for ms in obj.get("metricSets", []):
            for m in ms.get("metrics", []):
                m_id = m.get("id", "")
                m_label = m.get("label", "")
                m_key = _metric_label_to_key(m_label)
                result[m_id] = (obj_label, m_label, m_key)
    return result


# ---------------------------------------------------------------------------
# Source / auth extraction
# ---------------------------------------------------------------------------

def _extract_source(exchange: Dict) -> Dict:
    """Extract the source: YAML block from the exchange format."""
    src_block = exchange.get("source", {})
    src_inner = src_block.get("source", {})
    config = src_block.get("configuration", [])

    # Port and SSL from configuration
    port = 443
    ssl = "NO_VERIFY"
    timeout = 30
    max_retries = 2
    max_concurrent = 2
    for c in config:
        k = c.get("key", "")
        dv = c.get("defaultValue", "")
        if k == "mpb_port":
            try:
                port = int(dv)
            except (ValueError, TypeError):
                pass
        elif k == "mpb_ssl_config":
            # MPB exchange uses display strings ("No Verify", "Verify", "No SSL")
            _map = {"No Verify": "NO_VERIFY", "Verify": "VERIFY", "No SSL": "NO_SSL"}
            ssl = _map.get(str(dv), "NO_VERIFY")
        elif k == "mpb_connection_timeout":
            try:
                timeout = int(dv)
            except (ValueError, TypeError):
                pass
        elif k == "mpb_max_retries":
            try:
                max_retries = int(dv)
            except (ValueError, TypeError):
                pass
        elif k == "mpb_concurrent_requests":
            try:
                max_concurrent = int(dv)
            except (ValueError, TypeError):
                pass

    base_path = src_inner.get("configuration", {}).get("baseApiPath", "")

    source: Dict[str, Any] = {
        "port": port,
        "ssl": ssl,
        "base_path": base_path,
        "timeout": timeout,
        "max_retries": max_retries,
        "max_concurrent": max_concurrent,
    }

    # Auth
    auth_block = _extract_auth(src_inner)
    if auth_block:
        source["auth"] = auth_block

    # Test request
    tr = src_inner.get("testRequest")
    if tr:
        tr_yaml: Dict[str, Any] = {
            "method": tr.get("method", "GET"),
            "path": tr.get("path", ""),
        }
        params = tr.get("params", [])
        if params:
            tr_yaml["params"] = [{"key": p["key"], "value": p["value"]} for p in params]
        source["test_request"] = tr_yaml

    return source


def _extract_auth(src_inner: Dict) -> Optional[Dict]:
    """Extract the auth: YAML block from the exchange source.source."""
    auth = src_inner.get("authentication", {})
    if not auth:
        return None

    cred_type = auth.get("credentialType", "NONE")
    if cred_type == "NONE":
        return {"preset": "none"}

    if cred_type == "BASIC":
        creds_yaml = []
        for c in auth.get("creds", []):
            creds_yaml.append({
                "key": c.get("label", ""),
                "label": c.get("label", ""),
                "sensitive": c.get("sensitive", False),
            })
        return {"preset": "basic_auth", "credentials": creds_yaml}

    if cred_type == "TOKEN":
        creds_yaml = []
        for c in auth.get("creds", []):
            creds_yaml.append({
                "key": c.get("label", ""),
                "label": c.get("label", ""),
                "sensitive": c.get("sensitive", True),
            })
        return {"preset": "bearer_token", "credentials": creds_yaml}

    if cred_type == "CUSTOM":
        creds_yaml = []
        for c in auth.get("creds", []):
            # Exchange format usage: "${authentication.credentials.<label>}"
            # Strip the wrapping to get the label for our grammar
            creds_yaml.append({
                "key": c.get("label", ""),
                "label": c.get("label", ""),
                "sensitive": c.get("sensitive", False),
            })

        ss = auth.get("sessionSettings", {}) or {}
        login_yaml: Dict[str, Any] = {}
        get_sess = ss.get("getSession", {})
        if get_sess:
            # Rewrite ${authentication.credentials.*} → ${credentials.*}
            def _rewrite_back(text: str) -> str:
                if not text:
                    return text
                text = re.sub(r"\$\{authentication\.credentials\.([a-zA-Z0-9_]+)\}",
                              r"${credentials.\1}", text)
                text = re.sub(r"\$\{authentication\.session\.([a-zA-Z0-9_]+)\}",
                              r"${session.\1}", text)
                return text

            login_params = []
            for p in get_sess.get("params", []):
                login_params.append({
                    "key": p["key"],
                    "value": _rewrite_back(p.get("value", "")),
                })
            login_yaml = {
                "method": get_sess.get("method", "GET"),
                "path": get_sess.get("path", ""),
                "params": login_params,
            }

        # Extract rule from sessionVariables
        extract_yaml: Dict[str, Any] = {}
        for sv in ss.get("sessionVariables", []):
            location = sv.get("location", "HEADER")
            path_list = sv.get("path", [])
            key = sv.get("key", "")
            # path[0] is the header name for HEADER location
            header_name = path_list[0] if path_list else key
            extract_yaml = {
                "location": location,
                "name": header_name,
                "bind_to": f"session.{key}",
            }
            break  # typically one session variable

        # Inject rules from globalHeaders
        inject_yaml: List[Dict[str, Any]] = []
        for h in src_inner.get("globalHeaders", []):
            if h.get("key") == "Content-Type":
                continue  # implied by the preset
            inject_yaml.append({
                "type": "header",
                "name": h.get("key", ""),
                "value": re.sub(
                    r"\$\{authentication\.session\.([a-zA-Z0-9_]+)\}",
                    r"${session.\1}",
                    h.get("value", ""),
                ),
            })

        logout_yaml: Dict[str, Any] = {}
        rel_sess = ss.get("releaseSession", {})
        if rel_sess:
            def _rewrite_back_inner(text: str) -> str:
                if not text:
                    return text
                text = re.sub(r"\$\{authentication\.credentials\.([a-zA-Z0-9_]+)\}",
                              r"${credentials.\1}", text)
                text = re.sub(r"\$\{authentication\.session\.([a-zA-Z0-9_]+)\}",
                              r"${session.\1}", text)
                return text
            logout_params = []
            for p in rel_sess.get("params", []):
                logout_params.append({
                    "key": p["key"],
                    "value": _rewrite_back_inner(p.get("value", "")),
                })
            logout_yaml = {
                "method": rel_sess.get("method", "DELETE"),
                "path": rel_sess.get("path", ""),
                "params": logout_params,
            }

        result: Dict[str, Any] = {
            "preset": "cookie_session",
            "credentials": creds_yaml,
        }
        if login_yaml:
            result["login"] = login_yaml
        if extract_yaml:
            result["extract"] = extract_yaml
        if inject_yaml:
            result["inject"] = inject_yaml
        if logout_yaml:
            result["logout"] = logout_yaml
        return result

    return {"preset": "none"}


# ---------------------------------------------------------------------------
# Request extraction
# ---------------------------------------------------------------------------

def _extract_requests(exchange: Dict) -> List[Dict]:
    """Extract the requests: YAML block.

    For each request:
    - Extract name, method, path, params, body.
    - Derive response_path from the primary DML id.
    - Rewrite ${requestParameters.*} → ${chain.*} in params.
    """
    requests_yaml: List[Dict] = []
    for r in exchange.get("requests", []):
        req = r["request"]
        name = req.get("name", "")
        method = req.get("method", "GET")
        path = req.get("path", "")
        body = req.get("body") or None

        params_raw = req.get("params", [])
        params = []
        for p in params_raw:
            key = p.get("key", "")
            value = p.get("value", "")
            # Rewrite ${requestParameters.<name>} → ${chain.<name>}
            value = re.sub(
                r"\$\{requestParameters\.([a-zA-Z0-9_]+)\}",
                r"${chain.\1}",
                str(value),
            )
            params.append({"key": key, "value": value})

        # Derive response_path from DML ids
        dmls = req.get("response", {}).get("result", {}).get("dataModelLists", [])
        dml_ids = [d["id"] for d in dmls]
        response_path = _infer_response_path(dml_ids)

        entry: Dict[str, Any] = {
            "name": name,
            "method": method,
            "path": path,
        }
        if params:
            entry["params"] = params
        if body:
            entry["body"] = body
        entry["response_path"] = response_path

        requests_yaml.append(entry)

    return requests_yaml


# ---------------------------------------------------------------------------
# Object type extraction
# ---------------------------------------------------------------------------

def _extract_objects(
    exchange: Dict,
    req_id_to_name: Dict[str, str],
    metric_id_map: Dict[str, Tuple[str, str, str]],
) -> List[Dict]:
    """Extract the object_types: YAML block."""
    objects_yaml: List[Dict] = []

    for obj_wrap in exchange.get("objects", []):
        obj = obj_wrap["object"]
        ioi = obj.get("internalObjectInfo", {})
        label = ioi.get("objectTypeLabel", "Unknown")
        key = _slug(label)
        is_list_obj = obj.get("isListObject", True)
        is_world = not is_list_obj
        icon = ioi.get("icon", "server.svg")

        # Build metricSets and metrics
        metric_sets_yaml: List[Dict] = []
        metrics_yaml: List[Dict] = []
        # Map: metric_id → metric_key (for identifier/name_expression lookup)
        local_metric_id_to_key: Dict[str, str] = {}

        # Check for chaining (objectBinding on any metricSet)
        chaining_info: Dict[str, Any] = {}  # ms_id → objectBinding info

        for ms in obj.get("metricSets", []):
            ms_req_id = ms.get("requestId", "")
            ms_req_name = req_id_to_name.get(ms_req_id, ms_req_id)
            ms_list_id = ms.get("listId", "base")
            ob = ms.get("objectBinding")

            # Derive list_path from ms_list_id
            # For world objects listId is always "base"
            # For list objects, need response_path to strip it
            # Find the request's response_path by looking at the DML ids
            # (we can infer it from the DML id itself)
            if ms_list_id == "base":
                list_path = ""
            else:
                # Strip the trailing .* if present
                work = ms_list_id
                if work.endswith(".*"):
                    work = work[:-2]
                # The response_path is typically the first component "data"
                # Strip leading "data." prefix for list_path
                if work.startswith("data."):
                    list_path = work[5:]
                elif work == "data":
                    list_path = ""
                else:
                    list_path = work

            ms_entry: Dict[str, Any] = {
                "from_request": ms_req_name,
            }
            if not is_world:
                ms_entry["primary"] = ob is None
            if list_path:
                ms_entry["list_path"] = list_path

            # Handle chaining (objectBinding present means this is a chained MS)
            if ob is not None:
                # objectBinding.matchExpression.expressionParts[0].originId
                # encodes the chainingSettings param id.
                # We need to recover the bind mapping from the chained request's
                # chainingSettings. We'll resolve this in a second pass.
                ms_entry["_is_chained"] = True
                ms_entry["_object_binding"] = ob

            metric_sets_yaml.append(ms_entry)

            # Extract metrics from this metricSet
            for m in ms.get("metrics", []):
                m_id = m.get("id", "")
                m_label = m.get("label", "")
                m_key = _metric_label_to_key(m_label)
                m_usage = m.get("usage", "METRIC")
                m_type = m.get("dataType", "STRING")
                m_unit = m.get("unit", "") or ""
                m_kpi = m.get("isKpi", False)

                local_metric_id_to_key[m_id] = m_key

                # Recover the field path from expressionParts[0].originId
                # originId format: "<req_id>-<dml_id>-<field_path>"
                field_path = ""
                expr = m.get("expression", {})
                for part in expr.get("expressionParts", []):
                    origin_id = part.get("originId", "")
                    # Strip <req_id>-<dml_id>- prefix
                    # The req_id is a UUID (36 chars), dml_id is until the next "-"
                    # Format: <36-char-uuid>-<dml_id>-<field>
                    # Find the field after the second segment
                    # UUID is exactly 36 chars (8-4-4-4-12 = 36)
                    if len(origin_id) > 37 and origin_id[36] == "-":
                        rest = origin_id[37:]
                        # rest is <dml_id>-<field_path>
                        # dml_id uses dots, not hyphens; split on first segment
                        # that ends the dml_id. The dml_id is everything up to
                        # the last "-<field>" segment where field doesn't contain dots.
                        # Simpler: find the matching dml_id from ms_list_id
                        if ms_list_id != "base":
                            prefix = ms_list_id + "-"
                            if rest.startswith(prefix):
                                field_path = rest[len(prefix):]
                            else:
                                # Try without leading .*
                                dml_no_star = ms_list_id
                                if dml_no_star.endswith(".*"):
                                    dml_no_star = dml_no_star[:-2]
                                prefix2 = dml_no_star + "-"
                                if rest.startswith(prefix2):
                                    field_path = rest[len(prefix2):]
                                else:
                                    # Fallback: last "-"-delimited segment
                                    # that looks like a field name
                                    field_path = part.get("label", m_label)
                        else:
                            # base DML: field_path is the full dotted path
                            # rest = "base-<field_path>"
                            if rest.startswith("base-"):
                                field_path = rest[5:]
                            else:
                                field_path = part.get("label", m_label)
                    else:
                        field_path = part.get("label", m_label)
                    break  # only first part

                if not field_path:
                    field_path = m_label

                # For world objects, source path is relative to response_path.
                # The originId encodes "data.<field>" — strip the "data." prefix.
                if is_world and field_path.startswith("data."):
                    source_path = field_path[5:]
                else:
                    source_path = field_path

                m_yaml: Dict[str, Any] = {
                    "key": m_key,
                    "label": m_label,
                    "usage": m_usage,
                    "type": m_type,
                    "source": f"metricset:{ms_req_name}.{source_path}",
                }
                if m_unit:
                    m_yaml["unit"] = m_unit
                if m_kpi:
                    m_yaml["kpi"] = True

                metrics_yaml.append(m_yaml)

        # Identifiers: look up metric labels from identifierIds
        identifier_keys: List[str] = []
        for mid in ioi.get("identifierIds", []):
            mk = local_metric_id_to_key.get(mid, mid)
            identifier_keys.append(mk)

        # Name expression: from nameMetricExpression.expressionParts[0]
        name_expr = ""
        nme = ioi.get("nameMetricExpression", {})
        for part in nme.get("expressionParts", []):
            origin_id = part.get("originId", "")
            if part.get("originType") == "METRIC":
                mk = local_metric_id_to_key.get(origin_id, part.get("label", ""))
                name_expr = mk
            else:
                name_expr = part.get("label", "")
            break

        # Resolve chaining: for chained metricSets, find the chainingSettings
        # on the child request and extract bind mappings + parent metricSet name.
        for i, ms_e in enumerate(metric_sets_yaml):
            if not ms_e.pop("_is_chained", False):
                continue
            ob = ms_e.pop("_object_binding", None)
            child_req_name = ms_e.get("from_request", "")
            # Find the request with this name and look at chainingSettings
            parent_ms_name = ""
            bind_list: List[Dict[str, str]] = []
            for r in exchange.get("requests", []):
                req = r["request"]
                if req.get("name") == child_req_name:
                    cs = req.get("chainingSettings")
                    if cs:
                        parent_req_id = cs.get("parentRequestId", "")
                        parent_req_name = req_id_to_name.get(parent_req_id, parent_req_id)
                        # Find the sibling metricSet local_name that matches
                        for ms_sib in metric_sets_yaml:
                            if ms_sib.get("from_request") == parent_req_name:
                                parent_ms_name = parent_req_name
                                break
                        # Extract bind entries
                        for param in cs.get("params", []):
                            bind_name = param.get("key", "")
                            # from_attribute comes from the attributeExpression
                            ae = param.get("attributeExpression", {})
                            from_attr = ""
                            for part in ae.get("expressionParts", []):
                                from_attr = part.get("label", "")
                                break
                            if bind_name and from_attr:
                                bind_list.append({
                                    "name": bind_name,
                                    "from_attribute": from_attr,
                                })
                    break

            if parent_ms_name:
                ms_e["chained_from"] = parent_ms_name
            if bind_list:
                ms_e["bind"] = bind_list

        # Remove internal helpers from ms entries
        for ms_e in metric_sets_yaml:
            ms_e.pop("_is_chained", None)
            ms_e.pop("_object_binding", None)

        obj_yaml: Dict[str, Any] = {
            "name": label,
            "key": key,
            "type": obj.get("type", "INTERNAL"),
            "icon": icon,
        }
        if is_world:
            obj_yaml["is_world"] = True
            obj_yaml["identity"] = {
                "tier": "system_issued",
                "source": "metricset",  # placeholder — author should verify
            }
        if identifier_keys:
            obj_yaml["identifiers"] = identifier_keys
        if name_expr:
            obj_yaml["name_expression"] = name_expr
        if metric_sets_yaml:
            obj_yaml["metricSets"] = metric_sets_yaml
        if metrics_yaml:
            obj_yaml["metrics"] = metrics_yaml

        objects_yaml.append(obj_yaml)

    return objects_yaml


# ---------------------------------------------------------------------------
# Relationship extraction
# ---------------------------------------------------------------------------

def _extract_relationships(
    exchange: Dict,
    metric_id_map: Dict[str, Tuple[str, str, str]],
    obj_label_to_key: Dict[str, str],
) -> List[Dict]:
    """Extract the relationships: YAML block."""
    rels_yaml: List[Dict] = []

    # Build object id → key mapping
    obj_id_to_key: Dict[str, str] = {}
    for obj_wrap in exchange.get("objects", []):
        obj = obj_wrap["object"]
        obj_id = obj.get("id", "")
        label = obj.get("internalObjectInfo", {}).get("objectTypeLabel", "")
        obj_id_to_key[obj_id] = obj_label_to_key.get(label, _slug(label))

    for rel_wrap in exchange.get("relationships", []):
        rel = rel_wrap["relationship"]
        parent_id = rel.get("parentObjectId", "")
        child_id = rel.get("childObjectId", "")
        parent_key = obj_id_to_key.get(parent_id, parent_id)
        child_key = obj_id_to_key.get(child_id, child_id)

        rel_yaml: Dict[str, Any] = {
            "parent": parent_key,
            "child": child_key,
            "scope": "field_match",
        }

        # Extract parent_expression (from parentExpression.expressionParts[0].originId)
        pe = rel.get("parentExpression", {})
        for part in pe.get("expressionParts", []):
            if part.get("originType") == "METRIC":
                m_id = part.get("originId", "")
                _, _, mk = metric_id_map.get(m_id, ("", "", _slug(part.get("label", ""))))
                rel_yaml["parent_expression"] = mk
            break

        # Extract child_expression
        ce = rel.get("childExpression", {})
        for part in ce.get("expressionParts", []):
            if part.get("originType") == "METRIC":
                m_id = part.get("originId", "")
                _, _, mk = metric_id_map.get(m_id, ("", "", _slug(part.get("label", ""))))
                rel_yaml["child_expression"] = mk
            break

        rels_yaml.append(rel_yaml)

    return rels_yaml


# ---------------------------------------------------------------------------
# YAML serializer (stdlib-only, no PyYAML dependency for output)
# ---------------------------------------------------------------------------

def _to_yaml(obj: Any, indent: int = 0, _inline: bool = False) -> str:
    """Minimal YAML serializer producing clean, readable output.

    Does not use PyYAML for output so the indentation and style are
    exactly what we want (block style lists, inline simple scalars).
    """
    ind = "  " * indent
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return str(obj)
    if isinstance(obj, str):
        # Quote if contains special characters
        if (not obj or obj[0] in ("#", "&", "*", "?", "|", "-", "<", ">",
                                   "=", "!", "%", "@", "`", "'", '"', "{", "}")
                or ":" in obj or "\n" in obj or obj.strip() != obj
                or obj.lower() in ("true", "false", "null", "yes", "no",
                                   "on", "off")):
            escaped = obj.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return obj
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if _inline or all(isinstance(x, (str, int, float, bool)) and
                          not isinstance(x, bool) or isinstance(x, bool)
                          for x in obj):
            # Check if all items are simple scalars for inline representation
            if all(isinstance(x, (int, float, bool)) for x in obj) or \
               (all(isinstance(x, str) for x in obj) and
                    all(len(x) < 30 and " " not in x for x in obj)):
                items = [_to_yaml(x, 0, _inline=True) for x in obj]
                return "[" + ", ".join(items) + "]"
        lines = []
        for item in obj:
            item_str = _to_yaml(item, indent + 1)
            if isinstance(item, dict):
                # First key inline with "-"
                first_line = item_str.split("\n")[0]
                rest_lines = item_str.split("\n")[1:]
                lines.append(f"{ind}- {first_line.lstrip()}")
                for rl in rest_lines:
                    lines.append(f"{ind}  {rl.lstrip()}" if rl.strip() else rl)
            else:
                lines.append(f"{ind}- {item_str}")
        return "\n".join(lines)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = []
        for k, v in obj.items():
            if isinstance(v, dict):
                if not v:
                    lines.append(f"{ind}{k}: {{}}")
                else:
                    lines.append(f"{ind}{k}:")
                    lines.append(_to_yaml(v, indent + 1))
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{ind}{k}: []")
                else:
                    lines.append(f"{ind}{k}:")
                    lines.append(_to_yaml(v, indent + 1))
            else:
                lines.append(f"{ind}{k}: {_to_yaml(v, indent, _inline=True)}")
        return "\n".join(lines)
    return str(obj)


# ---------------------------------------------------------------------------
# Main extract function
# ---------------------------------------------------------------------------

def extract_to_yaml(exchange_path: str) -> str:
    """Read an MPB exchange JSON and return YAML text.

    This is the main entry point for the extract CLI command.
    """
    with open(exchange_path) as f:
        exchange = json.load(f)

    design = exchange.get("design", {}).get("design", {})
    src_block = exchange.get("source", {})
    src_inner = src_block.get("source", {})

    # MP-level fields
    name = design.get("name", "Extracted MP")
    version = design.get("version", "1.0.0")
    description = design.get("description", "")
    adapter_type = design.get("type", "HTTP")

    # Build index structures
    req_id_to_name = _build_request_id_map(exchange)
    metric_id_map = _build_metric_id_map(exchange)
    obj_label_to_key: Dict[str, str] = {}
    for obj_wrap in exchange.get("objects", []):
        obj = obj_wrap["object"]
        lbl = obj.get("internalObjectInfo", {}).get("objectTypeLabel", "")
        obj_label_to_key[lbl] = _slug(lbl)

    # Extract each section
    source_yaml = _extract_source(exchange)
    requests_yaml = _extract_requests(exchange)
    objects_yaml = _extract_objects(exchange, req_id_to_name, metric_id_map)
    rels_yaml = _extract_relationships(exchange, metric_id_map, obj_label_to_key)

    # Assemble the document
    doc: Dict[str, Any] = {}
    doc["name"] = name
    doc["version"] = version
    doc["build_number"] = 1
    doc["author"] = ""
    if description:
        doc["description"] = description
    doc["source"] = source_yaml
    doc["requests"] = requests_yaml
    doc["object_types"] = objects_yaml
    if rels_yaml:
        doc["relationships"] = rels_yaml

    # Use PyYAML for output (it's already a dependency)
    import yaml
    header = (
        "# Extracted from MPB exchange format — review before use.\n"
        "# Keys, list_paths, and source paths are derived from MPB's internal\n"
        "# structure and may need adjustment. Verify:\n"
        "#   - metric keys (slug-derived from MPB labels)\n"
        "#   - list_path values (derived from metricSet.listId)\n"
        "#   - response_path values (inferred from DML id prefix)\n"
        "#   - identity.tier on world object (set to 'system_issued' as placeholder)\n"
        "#   - name_expression (derived from nameMetricExpression)\n"
        "#   - relationships parent_expression / child_expression (label-derived)\n"
        "#\n"
        "# This file round-trips through render-export to a semantically\n"
        "# equivalent MPB design. Byte-for-byte match with the source is not\n"
        "# a goal — UUIDs will differ (factory uses UUID5, MPB uses UUID4).\n"
    )
    return header + yaml.dump(doc, default_flow_style=False, allow_unicode=True,
                              sort_keys=False, width=120)
