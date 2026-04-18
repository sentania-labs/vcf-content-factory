"""Render a ManagementPackDef into MPB design JSON.

Wire format derived from:
  - references/sentania_aria_operations_dsm_mp/Management Pack JSON/Synology DSM MP.json
    (Scott's build-8 ground truth — CUSTOM auth, globalHeaders, sessionVariables)
  - references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json
    (only reference with populated relationships + events)
  - context/mp_schema_vs_existing_mp.md (full cross-check document)
  - docs/reference-mpb-research.md (baseline research)

Key wire-format facts encoded here:
  - All IDs are UUID5 strings (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx), derived
    deterministically from a stable factory namespace + semantic seed string.
    MPB's UI import endpoint (POST /suite-api/internal/mpbuilder/designs/import)
    validates UUID shape before processing; base62 IDs cause HTTP 400.
  - Two independent `id` fields per object: object.id AND internalObjectInfo.id.
  - is_world: true → isListObject: false; world metricSets use listId "base".
  - Requests are deduplicated across object_types into a flat top-level array.
  - params is always a list of {key, value} — never a dict.
  - response_path (e.g. "data.storagePools") drives the dataModelList structure.
  - expressionText format: "@@@MPB_QUOTE <part-id> @@@MPB_QUOTE" (literal, verbatim).
  - @@@id synthetic attribute is included on every wildcard-iteration DML.
  - CUSTOM auth emits credentialType, creds, sessionSettings (getSession +
    releaseSession + sessionVariables), plus globalHeaders for cookie injection.
  - Relationship childExpression/parentExpression use originType: METRIC and
    point to the metric ID (not the attribute DML origin ID).
  - Null-expression relationships (adapter-instance-trivial) are handled per
    the relationship_strategy parameter.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .loader import (
    AuthFlowDef,
    BindDef,
    IdentifierDef,
    ManagementPackDef,
    MetricDef,
    MetricSetDef,
    MetricSourceDef,
    NameExpressionDef,
    NamePartDef,
    ObjectTypeDef,
    RelationshipDef,
    RequestDef,
    WorldIdentityDef,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic ID generation — UUID5, standard hyphenated format
#
# Canonical factory namespace shared with vcfops_dashboards/loader.py.
# Do NOT change this value once any MP has been deployed — every sub-object
# ID in every rendered design is derived from it (CLAUDE.md §6 UUID stability).
# ---------------------------------------------------------------------------

_FACTORY_NS = uuid.UUID("4b8d2c10-1f9e-4f4f-9b90-0e8f6a8e2a12")


def _make_id(seed: str) -> str:
    """Derive a stable UUID5 string from a seed string.

    Uses the factory-wide namespace (_FACTORY_NS) so IDs are globally
    unique across all factory content types and stable across re-renders
    of the same YAML (CLAUDE.md §6).

    The seed should encode the object's semantic position, e.g.:
      "<adapter_kind>:object:<object_key>"
      "<adapter_kind>:request:<request_name>"
      "<adapter_kind>:object:<object_key>:metric:<metric_key>"
    so two renders of the same YAML produce identical UUIDs for each
    sub-object.
    """
    return str(uuid.uuid5(_FACTORY_NS, seed))


def _make_sub_id(parent_seed: str, discriminator: str) -> str:
    """Sub-ID derived from a parent seed plus a discriminator."""
    return _make_id(f"{parent_seed}::{discriminator}")


# ---------------------------------------------------------------------------
# Source-field parsing helpers
# ---------------------------------------------------------------------------

# ${chain.<name>} in request templates → ${requestParameters.<name>} at emit
_CHAIN_TOKEN_RE = re.compile(r"\$\{chain\.([a-zA-Z0-9_]+)\}")


def _parse_source_ref(source: "MetricSourceDef") -> Tuple[str, str]:
    """Return (metricset_local_name, field_path) from a MetricSourceDef.

    Tier 3.3: source is always a MetricSourceDef at render time; the
    string shorthand is expanded by the loader.
    """
    return source.metricset, source.path


def _rewrite_chain_tokens(text: str) -> str:
    """Rewrite ${chain.<name>} → ${requestParameters.<name>} in any string."""
    return _CHAIN_TOKEN_RE.sub(lambda m: f"${{requestParameters.{m.group(1)}}}", text)


def _rewrite_params(params: Any) -> Any:
    """Apply _rewrite_chain_tokens to all param values."""
    if not params:
        return params
    if isinstance(params, list):
        result = []
        for p in params:
            if isinstance(p, dict):
                v = p.get("value", "")
                result.append({"key": p.get("key", ""), "value": _rewrite_chain_tokens(str(v)) if v else ""})
            else:
                result.append(p)
        return result
    if isinstance(params, dict):
        return {k: _rewrite_chain_tokens(str(v)) for k, v in params.items()}
    return params


def _response_path_to_dml_id(response_path: Optional[str]) -> str:
    """Convert a response_path like 'data.storagePools' to the DML list id 'data.storagePools.*'.

    If response_path is None or empty, the base DML is used (id='base').
    """
    if not response_path:
        return "base"
    # The DML id is the path joined with dots, plus '.*' suffix to indicate array iteration
    return f"{response_path}.*"


def _compute_dml_id(response_path: Optional[str], list_path: str) -> str:
    """Compute the DML id for a metricSet given request.response_path and metricSet.list_path.

    Logic:
      - list_path is the sub-path under response_path that selects the list of rows.
      - If both are empty/None: base DML (world/singleton, scalar response).
      - If list_path is empty but response_path is set: DML id is response_path.*
        (the response root is the list).
      - If both are set: DML id is response_path.list_path.* (composed path).
      - If only list_path is set: DML id is list_path.*

    Examples:
      response_path="data", list_path="volumes"   → "data.volumes.*"
      response_path="data", list_path=""           → "data.*"
      response_path="",     list_path=""           → "base"
      response_path="data", list_path="space.volume" → "data.space.volume.*"
    """
    rp = (response_path or "").strip()
    lp = list_path.strip() if list_path else ""

    if not rp and not lp:
        return "base"

    if rp and lp:
        return f"{rp}.{lp}.*"
    if rp:
        return f"{rp}.*"
    return f"{lp}.*"


def _compute_dml_key(response_path: Optional[str], list_path: str) -> List[str]:
    """Compute the DML key array from response_path + list_path."""
    rp = (response_path or "").strip()
    lp = list_path.strip() if list_path else ""

    if not rp and not lp:
        return []

    combined = ".".join(x for x in [rp, lp] if x)
    return combined.split(".")


def _response_path_to_dml_key(response_path: Optional[str]) -> List[str]:
    """Convert a response_path to the DML key array."""
    if not response_path:
        return []
    return response_path.strip().split(".")


def _field_path_to_dml_attr_key(field_path: str) -> List[str]:
    """Convert a dotted field path to attribute key array.

    For a source like 'data.storagePools', field_path is everything after
    the request name dot: e.g. 'size.total' → ['size', 'total'],
    or 'id' → ['id'].

    However, for a world-object (base DML), the field_path includes the
    response_path prefix: e.g. 'data.cpu_clock_speed' → ['data', 'cpu_clock_speed'].
    """
    return field_path.split(".")


# ---------------------------------------------------------------------------
# Standard source.configuration fields (MPB UI always emits these)
# ---------------------------------------------------------------------------

_STANDARD_CONFIG_FIELDS = [
    {
        "id": "mpb_hostname",
        "key": "hostname",
        "label": "Hostname",
        "usage": "${configuration.mpb_hostname}",
        "value": None,
        "options": None,
        "advanced": False,
        "editable": False,
        "configType": "STRING",
        "description": "Host name or IP address of the target device.",
        "defaultValue": None,
    },
    {
        "id": "mpb_port",
        "key": "port",
        "label": "Port",
        "usage": "${configuration.mpb_port}",
        "value": None,
        "options": None,
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
        "description": "The port used to connect to the target API.",
        "defaultValue": None,
    },
    {
        "id": "mpb_connection_timeout",
        "key": "connection_timeout_s",
        "label": "Connection Timeout",
        "usage": "${configuration.mpb_connection_timeout}",
        "value": None,
        "options": None,
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
        "description": "Connection timeout in seconds.",
        "defaultValue": 30,
    },
    {
        "id": "mpb_concurrent_requests",
        "key": "max_concurrent_requests",
        "label": "Max Concurrent Requests",
        "usage": "${configuration.mpb_concurrent_requests}",
        "value": None,
        "options": None,
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
        "description": "Maximum number of concurrent HTTP requests.",
        "defaultValue": 15,
    },
    {
        "id": "mpb_max_retries",
        "key": "maximum_retries",
        "label": "Maximum Retries",
        "usage": "${configuration.mpb_max_retries}",
        "value": None,
        "options": None,
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
        "description": "Maximum number of retries on request failure.",
        "defaultValue": 2,
    },
    {
        "id": "mpb_ssl_config",
        "key": "ssl",
        "label": "SSL",
        "usage": "${configuration.mpb_ssl_config}",
        "value": None,
        "options": ["NO_VERIFY", "VERIFY", "NO_SSL"],
        "advanced": True,
        "editable": False,
        "configType": "SINGLE_SELECTION",
        "description": "SSL verification mode.",
        "defaultValue": None,
    },
    {
        "id": "mpb_min_event_severity",
        "key": "minimum_vmware_aria_operations_severity",
        "label": "Minimum Event Severity",
        "usage": "${configuration.mpb_min_event_severity}",
        "value": None,
        "options": ["INFO", "WARNING", "IMMEDIATE", "CRITICAL"],
        "advanced": True,
        "editable": False,
        "configType": "SINGLE_SELECTION",
        "description": "Minimum severity level for event collection.",
        "defaultValue": "WARNING",
    },
]


# ---------------------------------------------------------------------------
# Request deduplication
# ---------------------------------------------------------------------------

class _RequestInfo:
    """Tracks a deduplicated request and its dataModelLists (DMls)."""

    def __init__(self, req: RequestDef, adapter_kind: str):
        # Stable ID: derived from adapter_kind + request name (unique per MP)
        self.id = _make_id(f"{adapter_kind}:request:{req.name}")
        self.req = req
        # DML structures keyed by dml_id
        self.dmls: Dict[str, Dict] = {}  # dml_id -> DML structure
        # Track attribute IDs we've registered (avoid double-registration)
        self._attr_ids: Dict[str, bool] = {}
        # chainingSettings to emit (set by _render_requests when a chained metricSet uses this req)
        self._chaining_settings: Optional[Dict] = None

    def register_field(self, field_path: str, dml_id: str) -> str:
        """Register a field and return its attribute-origin ID.

        dml_id is the fully-computed DML id (e.g. 'data.volumes.*' or 'base').
        field_path is the attribute label within the DML (relative to list item).
        The attribute origin ID is: <request_id>-<dml_id>-<attr_label>.
        """
        attr_key_path = field_path.split(".")
        attr_label = field_path  # label is the dotted path
        origin_id = f"{self.id}-{dml_id}-{attr_label}"

        if dml_id not in self.dmls:
            self._init_dml(dml_id)

        # Add the attribute if not already present
        if origin_id not in self._attr_ids:
            self._attr_ids[origin_id] = True
            self.dmls[dml_id]["attributes"].append({
                "id": origin_id,
                "key": attr_key_path,
                "label": attr_label,
                "example": "",
            })

        return origin_id

    def ensure_dml(self, dml_id: str) -> None:
        """Ensure a DML exists (initialize if missing)."""
        if dml_id not in self.dmls:
            self._init_dml(dml_id)

    def _init_dml(self, dml_id: str) -> None:
        """Initialize a DML structure in self.dmls.

        dml_id is the fully-computed id (e.g. 'data.volumes.*' or 'base').
        The DML key is derived from the id by stripping '.*' and splitting.
        """
        if dml_id == "base":
            dml = {
                "id": "base",
                "key": [],
                "label": None,
                "attributes": [],
                "parentListId": None,
            }
        else:
            # Array-iterating DML: derive key from dml_id by stripping '.*'
            path_without_wildcard = dml_id[:-2] if dml_id.endswith(".*") else dml_id
            key_parts = path_without_wildcard.split(".") if path_without_wildcard else []
            dml = {
                "id": dml_id,
                "key": key_parts,
                "label": dml_id,
                "attributes": [
                    # @@@id is always present on wildcard-iteration DMls
                    {
                        "id": f"{self.id}-{dml_id}-@@@id",
                        "key": ["@@@id"],
                        "label": "@@@id",
                        "example": "",
                    }
                ],
                "parentListId": "base",
            }
        self.dmls[dml_id] = dml
        self._attr_ids[f"{self.id}-{dml_id}-@@@id"] = True

    def to_wire(self) -> Dict:
        """Serialize to MPB request JSON shape (flat — no {"request": ...} wrapper).

        Wire format reference: mpb_rubrik_adapter3/conf/design.json §source.requests.
        Rubrik's source.requests is a dict of flat request objects, not wrapped dicts.

        ${chain.<name>} tokens in params/path/body are rewritten to
        ${requestParameters.<name>} at emit time per the Option C grammar spec.
        """
        req = self.req
        # Rewrite ${chain.*} tokens in path and params before normalizing
        path = _rewrite_chain_tokens(req.path) if req.path else req.path
        body = _rewrite_chain_tokens(req.body) if req.body else req.body
        raw_params = _rewrite_params(req.params)
        # params: always a list of {key, value}
        params = _normalize_params(raw_params)
        dmls = list(self.dmls.values())

        return {
            "id": self.id,
            "body": body,
            "name": req.name,
            "path": path,
            "method": req.method,
            "paging": None,
            "params": params,
            "headers": [],
            "designId": None,
            "response": {
                "id": _make_sub_id(self.id, "response"),
                "log": "Imported request, execute to get accurate log",
                "result": {
                    "body": "Imported request, execute to get accurate body",
                    "headers": [],
                    "responseCode": 200,
                    "dataModelLists": dmls,
                },
                "status": "COMPLETED",
                "endTime": 0,
                "duration": "NA",
                "startTime": 0,
                "toolkitId": _make_sub_id(self.id, "toolkit"),
                "errorMessage": "",
            },
            "chainingSettings": self._chaining_settings,
        }


def _normalize_params(params: Any) -> List[Dict]:
    """Convert params (list of {key,value} dicts, or a plain dict) to the MPB list form."""
    if not params:
        return []
    if isinstance(params, list):
        result = []
        for p in params:
            if isinstance(p, dict):
                result.append({"key": str(p.get("key", "")), "value": str(p.get("value", ""))})
        return result
    if isinstance(params, dict):
        # dict → ordered list; preserve insertion order (Python 3.7+)
        return [{"key": k, "value": str(v)} for k, v in params.items()]
    return []


# ---------------------------------------------------------------------------
# Expression helpers
# ---------------------------------------------------------------------------

def _make_expression(
    label: str,
    origin_id: str,
    origin_type: str,
    expr_seed: str,
    regex: Optional[str] = None,
) -> Dict:
    """Build an MPB expression object for a single-part expression.

    expressionText format: "@@@MPB_QUOTE <part-id> @@@MPB_QUOTE"
    """
    part_id = _make_id(f"{expr_seed}::part")
    expr_id = _make_id(f"{expr_seed}::expr")
    return {
        "id": expr_id,
        "expressionText": f"@@@MPB_QUOTE {part_id} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": part_id,
                "label": label,
                "regex": regex,
                "example": "",
                "originId": origin_id,
                "originType": origin_type,
                "regexOutput": "",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_pak_settings(mp: ManagementPackDef) -> Dict:
    """Render the flat pakSettings block (Rubrik wire format).

    Wire format reference: mpb_rubrik_adapter3/conf/design.json §pakSettings.
    Corresponds to what was previously the doubly-nested design.design block.
    """
    return {
        "adapterKind": mp.adapter_kind,
        "author": mp.author,
        "name": mp.name,
        "version": mp.version,
        "description": mp.description,
        "icon": "default.png",
    }


def _render_source(
    mp: ManagementPackDef,
    wire_requests: List[Dict],
    wire_objects: List[Dict],
    wire_events: List[Dict],
) -> Dict:
    """Render the flat source block (Rubrik wire format).

    Wire format reference: mpb_rubrik_adapter3/conf/design.json §source.
    The Rubrik source block contains:
      type, basePath, testRequestId, authentication, configuration,
      requests (dict keyed by id), resources (array), externalResources (array),
      events (array).

    Previously the factory emitted source.source (doubly-nested) with requests,
    objects, and events at the top level separately.  Rubrik's working wire
    format has them all inside source, and uses flat objects (no {"request": ...}
    / {"object": ...} / {"event": ...} wrappers).

    requests is a dict (id → request object); resources and events are arrays.
    externalResources is always [] — the factory does not model cross-adapter
    resource bindings.
    """
    src = mp.source

    # authentication block
    authentication = _render_authentication(mp)

    # adapter-instance configuration fields (Rubrik calls this "configuration")
    adapter_config_fields = list(_STANDARD_CONFIG_FIELDS)
    if src:
        for cf in adapter_config_fields:
            if cf["id"] == "mpb_port":
                cf = dict(cf)
                cf["defaultValue"] = src.port
            if cf["id"] == "mpb_ssl_config":
                cf = dict(cf)
                cf["defaultValue"] = src.ssl
            if cf["id"] == "mpb_connection_timeout":
                cf = dict(cf)
                cf["defaultValue"] = src.timeout
            if cf["id"] == "mpb_max_retries":
                cf = dict(cf)
                cf["defaultValue"] = src.max_retries
            if cf["id"] == "mpb_concurrent_requests":
                cf = dict(cf)
                cf["defaultValue"] = src.max_concurrent

    # testRequestId: the ID of the test-connection request (if any)
    test_request = _render_test_request(mp)
    test_request_id = test_request["id"] if test_request else None

    # Build requests dict (id → request object).
    # wire_requests is a list of already-flattened request objects (no wrapper).
    requests_dict: Dict[str, Dict] = {}
    for req in wire_requests:
        requests_dict[req["id"]] = req

    # If there is a testRequest, add it to the requests dict so it is reachable
    # by testRequestId (mirrors Rubrik's design.json where the test request also
    # appears in source.requests).
    if test_request and test_request["id"] not in requests_dict:
        requests_dict[test_request["id"]] = test_request

    return {
        "type": "HTTP",
        "basePath": src.base_path if src else "",
        "testRequestId": test_request_id,
        "authentication": authentication,
        "configuration": adapter_config_fields,
        "requests": requests_dict,
        "resources": wire_objects,          # flat array (no {"object": ...} wrapper)
        "externalResources": [],            # factory does not model cross-adapter bindings
        "events": wire_events,              # flat array (no {"event": ...} wrapper)
    }


def _render_cred_field(ak: str, cred, seed_suffix: str) -> Dict:
    """Render one CredentialFieldDef to the MPB wire shape."""
    cred_id = _make_id(f"{ak}:auth:{seed_suffix}:{cred.key}")
    return {
        "id": cred_id,
        "label": cred.label,
        "usage": f"${{authentication.credentials.{cred.label}}}",
        "value": None,
        "editable": True,
        "sensitive": cred.sensitive,
        "description": f"{cred.label} for authentication",
    }


def _render_session_request(
    ak: str,
    req,  # LoginRequestDef or LogoutRequestDef
    request_name: str,
    id_seed: str,
) -> Dict:
    """Render a login/logout request to the MPB sessionSettings wire shape."""
    req_id = _make_id(id_seed)
    params = _normalize_params(req.params or [])

    # Rewrite ${credentials.<key>} → ${authentication.credentials.<label>} at emit.
    # The author uses ${credentials.X}; MPB expects ${authentication.credentials.X}.
    # Labels equal keys in the current grammar (label is load-bearing, key is the
    # factory-facing alias — for creds they're the same by convention).
    # Also rewrite ${session.<key>} → ${authentication.session.<key>}.
    def _rewrite_auth_refs(text: str) -> str:
        if not text:
            return text
        text = re.sub(r"\$\{credentials\.([a-zA-Z0-9_]+)\}",
                      r"${authentication.credentials.\1}", text)
        text = re.sub(r"\$\{session\.([a-zA-Z0-9_]+)\}",
                      r"${authentication.session.\1}", text)
        return text

    rewritten_params = []
    for p in params:
        if isinstance(p, dict):
            v = p.get("value", "")
            rewritten_params.append({
                "key": p.get("key", ""),
                "value": _rewrite_auth_refs(str(v)) if v else "",
            })
        else:
            rewritten_params.append(p)

    headers = []
    for h in (req.headers or []):
        if isinstance(h, dict):
            headers.append({
                "key": h.get("key", ""),
                "type": h.get("type", "REQUIRED"),
                "value": _rewrite_auth_refs(str(h.get("value", ""))),
            })

    return {
        "id": req_id,
        "body": req.body,
        "name": request_name,
        "path": req.path or "",
        "method": (req.method or "GET").strip().upper(),
        "paging": None,
        "params": rewritten_params,
        "headers": headers,
        "designId": None,
        "response": {
            "id": _make_sub_id(req_id, "response"),
            "log": "Imported request, execute to get accurate log",
            "result": {
                "body": "Imported request, execute to get accurate body",
                "headers": [],
                "responseCode": 200,
                "dataModelLists": [
                    {
                        "id": "base",
                        "key": [],
                        "label": None,
                        "attributes": [],
                        "parentListId": None,
                    }
                ],
            },
            "status": "COMPLETED",
            "endTime": 0,
            "duration": "NA",
            "startTime": 0,
            "toolkitId": _make_sub_id(req_id, "toolkit"),
            "errorMessage": "",
        },
        "chainingSettings": None,
    }


def _render_authentication(mp: ManagementPackDef) -> Dict:
    """Render the authentication section.

    Maps AuthFlowDef presets to MPB wire shapes:
      none          → credentialType: NONE, no creds, no sessionSettings
      basic_auth    → credentialType: BASIC, username+password creds
      bearer_token  → credentialType: TOKEN, single token cred
      cookie_session → credentialType: CUSTOM, creds + getSession/releaseSession
                       + sessionVariables (wire shape unchanged from old CUSTOM path)

    Substitution rewriting at emit:
      ${credentials.<key>} → ${authentication.credentials.<label>}
      ${session.<key>}     → ${authentication.session.<key>}
      ${configuration.<key>} → passes through unchanged
    """
    src = mp.source
    if not src or not src.auth:
        return {
            "creds": [],
            "credentialType": "NONE",
            "sessionSettings": None,
        }

    auth: AuthFlowDef = src.auth
    ak = mp.adapter_kind

    if auth.preset == "none":
        return {
            "creds": [],
            "credentialType": "NONE",
            "sessionSettings": None,
        }

    if auth.preset == "basic_auth":
        creds = [_render_cred_field(ak, c, "basic") for c in auth.credentials]
        return {
            "creds": creds,
            "credentialType": "BASIC",
            "sessionSettings": None,
        }

    if auth.preset == "bearer_token":
        creds = [_render_cred_field(ak, c, "token") for c in auth.credentials]
        return {
            "creds": creds,
            "credentialType": "TOKEN",
            "sessionSettings": None,
        }

    if auth.preset == "cookie_session":
        creds = [_render_cred_field(ak, c, "custom") for c in auth.credentials]

        get_session = _render_session_request(
            ak, auth.login, "Get Session", f"{ak}:auth:getSession"
        )

        release_session = None
        if auth.logout is not None:
            release_session = _render_session_request(
                ak, auth.logout, "Release Session", f"{ak}:auth:releaseSession"
            )

        # Session variables from extract rule
        session_key = auth.extract.session_key
        # The wire format uses the raw header name (title-case per reference MP)
        # For HEADER location: key and path[] are the header name exactly as given
        # in extract.name.  Reference MP uses "Set-Cookie" (not lowercased).
        header_name = auth.extract.name  # e.g. "set_cookie" or "Set-Cookie"
        # Normalise to title-case for Set-Cookie specifically, pass others through
        # Reference: {"key": "Set-Cookie", "path": ["Set-Cookie"], ...}
        session_var_id = _make_id(f"{ak}:auth:sessionVar:{session_key}")
        session_variables = [
            {
                "id": session_var_id,
                "key": header_name,
                "path": [header_name],
                "usage": f"${{authentication.session.{session_key}}}",
                "example": None,
                "location": auth.extract.location,
            }
        ]

        session_settings: Dict = {
            "getSession": get_session,
            "sessionVariables": session_variables,
        }
        if release_session is not None:
            session_settings["releaseSession"] = release_session

        return {
            "creds": creds,
            "credentialType": "CUSTOM",
            "sessionSettings": session_settings,
        }

    # Fallback (should not be reached — loader validates preset)
    return {
        "creds": [],
        "credentialType": "NONE",
        "sessionSettings": None,
    }


def _render_global_headers(mp: ManagementPackDef) -> List[Dict]:
    """Render globalHeaders.

    For cookie_session preset: emit Content-Type + inject[] rules.
    For other presets / no auth: emit just Content-Type.

    Wire format requires header type: REQUIRED | IMMUTABLE | CUSTOM.
    Reference MP: Content-Type is REQUIRED; session cookie header is CUSTOM.
    """
    src = mp.source
    if not src or not src.auth or src.auth.preset != "cookie_session":
        # Default: just Content-Type
        return [
            {"key": "Content-Type", "type": "REQUIRED", "value": "application/json"}
        ]

    auth = src.auth
    headers: List[Dict] = []
    content_type_added = False

    # Rewrite ${session.<key>} → ${authentication.session.<key>} at emit.
    def _rewrite_session_refs(text: str) -> str:
        return re.sub(r"\$\{session\.([a-zA-Z0-9_]+)\}",
                      r"${authentication.session.\1}", text)

    for rule in auth.inject:
        key = rule.name
        value = _rewrite_session_refs(rule.value)
        if key == "Content-Type":
            content_type_added = True
            htype = "REQUIRED"
        else:
            # Non-Content-Type inject rules are CUSTOM per wire format
            # Reference MP: {"key": "id", "type": "CUSTOM", "value": "${authentication.session.set_cookie}"}
            htype = "CUSTOM"
        headers.append({"key": key, "type": htype, "value": value})

    if not content_type_added:
        headers.insert(0, {
            "key": "Content-Type",
            "type": "REQUIRED",
            "value": "application/json",
        })

    return headers


def _render_test_request(mp: ManagementPackDef) -> Optional[Dict]:
    """Render source.source.testRequest."""
    src = mp.source
    if not src or not src.test_request:
        return None

    tr = src.test_request
    tr_id = _make_id(f"{mp.adapter_kind}:testRequest")
    params = _normalize_params(tr.get("params", []))

    return {
        "id": tr_id,
        "body": tr.get("body"),
        "name": "Test Connection",
        "path": tr.get("path"),
        "method": str(tr.get("method", "GET")).upper(),
        "paging": None,
        "params": params,
        "headers": [],
        "designId": None,
        "response": {
            "id": _make_sub_id(tr_id, "response"),
            "log": "Imported request, execute to get accurate log",
            "result": {
                "body": "Imported request, execute to get accurate body",
                "headers": [],
                "responseCode": 200,
                "dataModelLists": [
                    {
                        "id": "base",
                        "key": [],
                        "label": None,
                        "attributes": [],
                        "parentListId": None,
                    }
                ],
            },
            "status": "COMPLETED",
            "endTime": 0,
            "duration": "NA",
            "startTime": 0,
            "toolkitId": _make_sub_id(tr_id, "toolkit"),
            "errorMessage": "",
        },
        "chainingSettings": None,
    }


def _render_requests(
    mp: ManagementPackDef,
) -> Tuple[List[Dict], Dict[str, "_RequestInfo"]]:
    """Build the flat request registry for Option C grammar.

    Under Option C, requests live at MP scope (mp.requests).  Each ObjectTypeDef
    has a metric_sets list; each MetricSetDef references a top-level request by name.

    This function:
      1. Registers every top-level request in the registry.
      2. For each object_type + metricSet pair, registers all metric attributes
         on the appropriate DML (computed from request.response_path + metricSet.list_path).
      3. For chained metricSets, emits the parent-requested DML, auto-synthesizes
         any bind.from_attribute that isn't already covered by a metric, and sets
         chainingSettings on the child request.

    Returns:
        (wire_requests, request_registry)
        where request_registry maps request_name → _RequestInfo
    """
    registry: Dict[str, _RequestInfo] = {}
    ak = mp.adapter_kind

    # Step 1: register all top-level requests
    req_by_name: Dict[str, RequestDef] = {}
    for req in mp.requests:
        registry[req.name] = _RequestInfo(req, ak)
        req_by_name[req.name] = req

    # Step 2: process each object_type's metricSets
    for ot in mp.object_types:
        # Build map: metricSet.local_name → MetricSetDef
        ms_by_name: Dict[str, MetricSetDef] = {ms.local_name: ms for ms in ot.metric_sets}

        # Build map: metricSet.local_name → (req, dml_id)
        ms_dml: Dict[str, Tuple[RequestDef, str]] = {}
        for ms in ot.metric_sets:
            req = req_by_name[ms.from_request]
            dml_id = _compute_dml_id(req.response_path, ms.list_path)
            ms_dml[ms.local_name] = (req, dml_id)
            # Ensure DML is initialized
            registry[req.name].ensure_dml(dml_id)

        # Build map: metricSet.local_name → set of registered field labels
        # (for bind auto-synthesis tracking)
        ms_fields: Dict[str, set] = {ms.local_name: set() for ms in ot.metric_sets}

        # Register metric attributes
        for m in ot.metrics:
            ms_ref, field_path = _parse_source_ref(m.source)
            req, dml_id = ms_dml[ms_ref]

            if ot.is_world:
                # World/singleton: DML is "base"; prepend response_path to field_path
                rp = (req.response_path or "").strip()
                full_fp = f"{rp}.{field_path}" if rp else field_path
                registry[req.name].register_field(full_fp, "base")
                ms_fields[ms_ref].add(full_fp)
            else:
                registry[req.name].register_field(field_path, dml_id)
                ms_fields[ms_ref].add(field_path)

        # Step 3: process chained metricSets — auto-synthesize bind.from_attribute
        # entries and emit chainingSettings
        for ms in ot.metric_sets:
            if ms.chained_from is None:
                continue

            parent_ms = ms_by_name[ms.chained_from]
            parent_req, parent_dml_id = ms_dml[ms.chained_from]
            child_req, child_dml_id = ms_dml[ms.local_name]
            parent_req_info = registry[parent_req.name]
            child_req_info = registry[child_req.name]

            # Auto-synthesize any bind.from_attribute not already in parent's DML
            for b in ms.bind:
                if b.from_attribute not in ms_fields.get(ms.chained_from, set()):
                    # Attribute not sourced by any metric; synthesize it
                    parent_req_info.register_field(b.from_attribute, parent_dml_id)
                    logger.info(
                        "Object '%s' metricSet '%s': auto-synthesized attribute "
                        "'%s' on parent request '%s' DML '%s' for chain bind.",
                        ot.name, ms.local_name,
                        b.from_attribute, parent_req.name, parent_dml_id,
                    )

            # Build chainingSettings for the child request
            # (uses parent request ID + parent DML id + bind entries)
            chain_settings = _build_chaining_settings(
                parent_req_info=parent_req_info,
                parent_dml_id=parent_dml_id,
                ms=ms,
                child_req_name=child_req.name,
                ak=ak,
                ot_key=ot.key,
            )
            # Set chainingSettings on child request (last write wins if
            # multiple object_types chain the same child request — should
            # not happen in v1 but is safe)
            child_req_info._chaining_settings = chain_settings

    wire = [info.to_wire() for info in registry.values()]
    return wire, registry


def _build_chaining_settings(
    parent_req_info: "_RequestInfo",
    parent_dml_id: str,
    ms: "MetricSetDef",
    child_req_name: str,
    ak: str,
    ot_key: str,
) -> Dict:
    """Build the chainingSettings block for a child request.

    Wire format per context/mpb_chaining_wire_format.md §2.

    baseListId = parent_dml_id (the DML the chain iterates over).
    params[] = one entry per bind entry.
    Each param's attributeExpression points at the parent DML attribute.
    """
    chain_seed = f"{ak}:object:{ot_key}:chain:{child_req_name}"
    chain_id = _make_id(chain_seed)

    params = []
    for i, b in enumerate(ms.bind):
        # origin_id: <parentRequestId>-<baseListId>-<attributeLabel>
        origin_id = f"{parent_req_info.id}-{parent_dml_id}-{b.from_attribute}"

        param_seed = f"{chain_seed}:param:{b.name}"
        param_id = _make_id(param_seed)

        # attributeExpression: single-part passthrough
        expr_seed = f"{param_seed}:attrExpr"
        part_id = _make_id(f"{expr_seed}::part")
        expr_id = _make_id(f"{expr_seed}::expr")
        attr_expression = {
            "id": expr_id,
            "expressionText": f"@@@MPB_QUOTE {part_id} @@@MPB_QUOTE",
            "expressionParts": [
                {
                    "id": part_id,
                    "originType": "ATTRIBUTE",
                    "originId": origin_id,
                    "label": b.from_attribute,
                }
            ],
        }

        params.append({
            "id": param_id,
            "key": b.name,
            "label": b.name,
            "listId": parent_dml_id,
            "attributeExpression": attr_expression,
            "usage": f"${{requestParameters.{b.name}}}",
        })

    return {
        "id": chain_id,
        "parentRequestId": parent_req_info.id,
        "baseListId": parent_dml_id,
        "params": params,
    }


def _render_objects(
    mp: ManagementPackDef,
    request_registry: Dict[str, "_RequestInfo"],
) -> List[Dict]:
    """Render the objects array.

    Each ObjectTypeDef → one MPB object entry.
    """
    result = []
    for ot in mp.object_types:
        obj_wire = _render_one_object(ot, mp, request_registry)
        result.append(obj_wire)
    return result


def _render_one_object(
    ot: ObjectTypeDef,
    mp: ManagementPackDef,
    request_registry: Dict[str, "_RequestInfo"],
) -> Dict:
    """Render one object type to MPB wire format under Option C grammar.

    Each metricSet in ot.metric_sets becomes one MPB metricSet entry.
    Metric source is 'metricset:<ms_local_name>.<field_path>'; the renderer
    resolves (ms_local_name) → (request, dml_id) via the metricSets list.
    """
    ak = mp.adapter_kind
    obj_seed = f"{ak}:object:{ot.key}"
    obj_id = _make_id(obj_seed)
    internal_id = _make_sub_id(obj_seed, "internalInfo")

    # Build map: metricSet.local_name → (MetricSetDef, RequestDef, dml_id)
    req_by_name: Dict[str, RequestDef] = {r.name: r for r in mp.requests}
    ms_context: Dict[str, Tuple["MetricSetDef", RequestDef, str]] = {}
    for ms in ot.metric_sets:
        req = req_by_name[ms.from_request]
        if ot.is_world:
            dml_id = "base"
        else:
            dml_id = _compute_dml_id(req.response_path, ms.list_path)
        ms_context[ms.local_name] = (ms, req, dml_id)

    # Build metric_map: metric_key → metric_id (for identifierIds + name expression)
    metric_map: Dict[str, str] = {}

    # Group metrics by metricSet local_name
    metrics_by_ms: Dict[str, List[MetricDef]] = {}
    for m in ot.metrics:
        ms_ref, _ = _parse_source_ref(m.source)
        metrics_by_ms.setdefault(ms_ref, []).append(m)

    # Build wire metricSets — one per MetricSetDef in ot.metric_sets
    wire_metric_sets: List[Dict] = []

    for ms in ot.metric_sets:
        ms_def, req, dml_id = ms_context[ms.local_name]
        req_info = request_registry[req.name]

        ms_id = _make_id(f"{obj_seed}:metricSet:{ms.local_name}")
        wire_metrics: List[Dict] = []

        for m in metrics_by_ms.get(ms.local_name, []):
            m_id = _make_id(f"{obj_seed}:metric:{m.key}")
            metric_map[m.key] = m_id

            _, field_path = _parse_source_ref(m.source)

            if ot.is_world:
                # World/singleton: base DML; full dotted path from response root
                rp = (req.response_path or "").strip()
                full_field_path = f"{rp}.{field_path}" if rp else field_path
                origin_id = req_info.register_field(full_field_path, "base")
                expr_label = full_field_path
            else:
                # List object: field_path is relative to list item
                origin_id = req_info.register_field(field_path, dml_id)
                expr_label = field_path

            # Build the metric expression
            expr_seed = f"{obj_seed}:metric:{m.key}:expr"
            expression = _make_expression(
                label=expr_label,
                origin_id=origin_id,
                origin_type="ATTRIBUTE",
                expr_seed=expr_seed,
            )

            wire_metrics.append({
                "id": m_id,
                "unit": m.unit,
                "isKpi": m.kpi,
                "label": m.label,
                "usage": m.usage,
                "groups": [],
                "dataType": m.type,
                "expression": expression,
                "timeseries": None,
            })

        wire_metric_sets.append({
            "id": ms_id,
            "listId": dml_id,
            "requestId": req_info.id,
            "metrics": wire_metrics,
            "objectBinding": None,
        })

    # Build nameMetricExpression
    name_expr = _render_name_expression(ot, metric_map, obj_seed)

    # Log world-object identity tier for debugging (Tier 3.3 axis 7)
    if ot.is_world and ot.identity is not None:
        logger.info(
            "Object '%s' (world): identity tier=%r source=%r",
            ot.key, ot.identity.tier, ot.identity.source,
        )

    # Identifier IDs (metric IDs for identifier metric keys)
    # Tier 3.3: identifiers is a list of IdentifierDef
    identifier_ids = []
    for ident in ot.identifiers:
        ident_key = ident.key
        if ident_key in metric_map:
            identifier_ids.append(metric_map[ident_key])
        else:
            logger.warning(
                "Object %s: identifier key %r not found in metrics; skipping",
                ot.key, ident_key,
            )

    # Return flat object (no {"object": ...} wrapper).
    # Wire format reference: mpb_rubrik_adapter3/conf/design.json §source.resources.
    return {
        "id": obj_id,
        "type": ot.type,
        "designId": None,
        "metricSets": wire_metric_sets,
        "ariaOpsConf": None,
        "isListObject": not ot.is_world,
        "internalObjectInfo": {
            "id": internal_id,
            "icon": ot.icon,
            "identifierIds": identifier_ids,
            "objectTypeLabel": ot.name,
            "nameMetricExpression": name_expr,
        },
    }


def _render_name_expression(
    ot: ObjectTypeDef, metric_map: Dict[str, str], obj_seed: str
) -> Optional[Dict]:
    """Render the nameMetricExpression for an object type.

    Tier 3.3: ot.name_expression is a NameExpressionDef (or None).

    Single-part (one metric part):
        Emits the standard single-part expression (verified wire format).

    Multi-part (more than one entry including literals and multiple metrics):
        Renderer emits a "not yet implemented" error. The grammar accepts it;
        the renderer blocks until live capture of the composite wire format.
        Exception: a single metric entry optionally surrounded by literal-only
        entries is treated as single-part (literals ignored at render time with
        a warning — the author should use the single-metric shorthand for now).
    """
    if ot.name_expression is None:
        return None

    nexpr = ot.name_expression
    metric_parts = [p for p in nexpr.parts if p.metric is not None]

    if len(metric_parts) == 0:
        logger.warning(
            "Object %s: name_expression has no metric parts (all literals); skipping.",
            ot.key,
        )
        return None

    if len(metric_parts) > 1:
        raise NotImplementedError(
            f"Object '{ot.key}': name_expression has {len(metric_parts)} metric parts "
            f"({[p.metric for p in metric_parts]!r}). "
            f"Multi-metric composite name expressions are not yet implemented — "
            f"the MPB wire format for multi-part composites has not been live-verified. "
            f"Use a single-metric name_expression (shorthand string form) until "
            f"composite rendering is verified and unlocked."
        )

    # Single metric part — standard single-part emission
    metric_key = metric_parts[0].metric
    has_literals = any(p.literal is not None for p in nexpr.parts)
    if has_literals:
        logger.warning(
            "Object %s: name_expression has literal parts alongside single metric %r; "
            "literal parts are ignored at render time (single-part MPB emission). "
            "To render composite names, wait for multi-part verification.",
            ot.key, metric_key,
        )

    metric_id = metric_map.get(metric_key)
    if not metric_id:
        logger.warning(
            "Object %s: name_expression references metric key %r which is not in "
            "metric_map; skipping.",
            ot.key, metric_key,
        )
        return None

    # Find the label for this metric
    label = next(
        (m.label for m in ot.metrics if m.key == metric_key), metric_key
    )

    name_expr_id = _make_id(f"{obj_seed}:nameExpr")
    name_part_id = _make_id(f"{obj_seed}:nameExprPart")
    return {
        "id": name_expr_id,
        "expressionText": f"@@@MPB_QUOTE {name_part_id} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": name_part_id,
                "label": label,
                "regex": None,
                "example": "",
                "originId": metric_id,
                "originType": "METRIC",
                "regexOutput": "",
            }
        ],
    }


def _render_relationships(
    mp: ManagementPackDef,
    object_id_map: Dict[str, str],       # object_key → object.id
    metric_id_map: Dict[str, Dict[str, str]],  # object_key → {metric_key → metric_id}
    relationship_strategy: str,
) -> List[Dict]:
    """Render the relationships array.

    For relationships with child_expression/parent_expression (value-join predicates):
    emit standard relationship with childExpression/parentExpression pointing to
    the metric IDs on child/parent objects.

    For adapter-instance-trivial relationships (null both sides), branch on strategy.
    """
    result: List[Dict] = []
    ak = mp.adapter_kind

    for rel in mp.relationships:
        if rel.scope == "field_match":
            wire_rels = _render_join_relationship(rel, mp, object_id_map, metric_id_map, ak)
            result.extend(wire_rels)
        elif rel.scope == "adapter_instance":
            # Tier 3.3: adapter_instance scope — synthesize the wire-level predicate.
            # Per describe.xml structural analysis (2026-04-18): containment is
            # modelled via adapter_instance_id + TraversalSpec, NOT via
            # relationships[]. Trivial containment relationships cause MPB design
            # validation errors. We use the synthetic_adapter_instance strategy
            # (the best-evidenced option) and log the choice.
            logger.info(
                "Relationship %s→%s: scope=adapter_instance — "
                "synthesizing @@@adapterInstance predicate (synthetic_adapter_instance strategy).",
                rel.parent, rel.child,
            )
            wire_rels = _render_trivial_relationships(
                rel, mp, object_id_map, metric_id_map, ak,
                strategy="synthetic_adapter_instance",
            )
            result.extend(wire_rels)
        else:
            logger.warning(
                "Relationship %s→%s: unknown scope %r; skipping.",
                rel.parent, rel.child, rel.scope,
            )

    return result


def _make_rel_expression(
    label: str,
    metric_id: str,
    rel_seed: str,
    side: str,  # "child" or "parent"
) -> Dict:
    expr_seed = f"{rel_seed}:{side}:expr"
    part_id = _make_id(f"{expr_seed}:part")
    expr_id = _make_id(f"{expr_seed}:id")
    return {
        "id": expr_id,
        "expressionText": f"@@@MPB_QUOTE {part_id} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": part_id,
                "label": label,
                "regex": None,
                "example": "",
                "originId": metric_id,
                "originType": "METRIC",
                "regexOutput": "",
            }
        ],
    }


def _render_join_relationship(
    rel: RelationshipDef,
    mp: ManagementPackDef,
    object_id_map: Dict[str, str],
    metric_id_map: Dict[str, Dict[str, str]],
    ak: str,
) -> List[Dict]:
    """Render a standard value-join relationship."""
    rel_seed = f"{ak}:rel:{rel.parent}:{rel.child}"
    rel_id = _make_id(rel_seed)

    parent_obj_id = object_id_map.get(rel.parent)
    child_obj_id = object_id_map.get(rel.child)
    if not parent_obj_id or not child_obj_id:
        logger.warning(
            "Relationship %s→%s: object ID not found; skipping.", rel.parent, rel.child
        )
        return []

    # Resolve metric IDs
    child_metric_id = metric_id_map.get(rel.child, {}).get(rel.child_expression)
    parent_metric_id = metric_id_map.get(rel.parent, {}).get(rel.parent_expression)

    if not child_metric_id:
        logger.warning(
            "Relationship %s→%s: child metric key %r not in metric_id_map; skipping.",
            rel.parent, rel.child, rel.child_expression,
        )
        return []
    if not parent_metric_id:
        logger.warning(
            "Relationship %s→%s: parent metric key %r not in metric_id_map; skipping.",
            rel.parent, rel.child, rel.parent_expression,
        )
        return []

    # Find labels
    child_obj = next((o for o in mp.object_types if o.key == rel.child), None)
    parent_obj = next((o for o in mp.object_types if o.key == rel.parent), None)
    child_label = next(
        (m.label for m in (child_obj.metrics if child_obj else [])
         if m.key == rel.child_expression),
        rel.child_expression,
    )
    parent_label = next(
        (m.label for m in (parent_obj.metrics if parent_obj else [])
         if m.key == rel.parent_expression),
        rel.parent_expression,
    )

    child_expr = _make_rel_expression(child_label, child_metric_id, rel_seed, "child")
    parent_expr = _make_rel_expression(parent_label, parent_metric_id, rel_seed, "parent")

    # Return flat relationship (no {"relationship": ...} wrapper).
    # Wire format reference: mpb_rubrik_adapter3/conf/design.json §relationships.
    return [{
        "id": rel_id,
        "name": f"{rel.parent} -> {rel.child}",
        "designId": None,
        "caseSensitive": True,
        "childObjectId": child_obj_id,
        "parentObjectId": parent_obj_id,
        "childExpression": child_expr,
        "parentExpression": parent_expr,
    }]


def _render_trivial_relationships(
    rel: RelationshipDef,
    mp: ManagementPackDef,
    object_id_map: Dict[str, str],
    metric_id_map: Dict[str, Dict[str, str]],
    ak: str,
    strategy: str,
) -> List[Dict]:
    """Render adapter-instance-trivial (null expression) relationships per strategy.

    Strategies:
      world_implicit   — emit relationship with null expressions; MPB infers from world-object parentage
      synthetic_adapter_instance — emit with synthetic @@@adapterInstance on both ends
      shared_constant_property   — synthesize a constant property on both objects, use those metric IDs
      test_all         — emit three separate relationships (one per strategy) with distinguishable names
    """
    parent_obj_id = object_id_map.get(rel.parent)
    child_obj_id = object_id_map.get(rel.child)
    if not parent_obj_id or not child_obj_id:
        logger.warning(
            "Trivial relationship %s→%s: object ID not found; skipping.",
            rel.parent, rel.child,
        )
        return []

    if strategy == "world_implicit":
        return [_trivial_world_implicit(rel, parent_obj_id, child_obj_id, ak)]

    if strategy == "synthetic_adapter_instance":
        return [_trivial_synthetic_adapter_instance(rel, parent_obj_id, child_obj_id, ak)]

    if strategy == "shared_constant_property":
        return [_trivial_shared_constant(rel, parent_obj_id, child_obj_id, ak)]

    if strategy == "test_all":
        logger.info(
            "Trivial relationship %s→%s: emitting 3 relationships (test_all strategy).",
            rel.parent, rel.child,
        )
        return [
            _trivial_world_implicit(rel, parent_obj_id, child_obj_id, ak, suffix="world_implicit"),
            _trivial_synthetic_adapter_instance(rel, parent_obj_id, child_obj_id, ak, suffix="synthetic"),
            _trivial_shared_constant(rel, parent_obj_id, child_obj_id, ak, suffix="shared_constant"),
        ]

    logger.warning("Unknown relationship strategy %r; defaulting to world_implicit.", strategy)
    return [_trivial_world_implicit(rel, parent_obj_id, child_obj_id, ak)]


def _trivial_world_implicit(
    rel: RelationshipDef,
    parent_obj_id: str,
    child_obj_id: str,
    ak: str,
    suffix: str = "",
) -> Dict:
    """Strategy: emit with null expressions; trust MPB to infer from world-object parentage.

    ASSUMPTION: MPB may support null childExpression/parentExpression as a signal
    that all child objects belong to the world (adapter instance) parent.
    This is unverified — if MPB rejects null expressions, import will fail for
    these relationships. Mark for testing.
    """
    name_suffix = f" ({suffix})" if suffix else ""
    rel_seed = f"{ak}:rel:{rel.parent}:{rel.child}:world_implicit"
    rel_id = _make_id(rel_seed)
    return {
        "id": rel_id,
        "name": f"{rel.parent} -> {rel.child}{name_suffix}",
        "designId": None,
        "caseSensitive": True,
        "childObjectId": child_obj_id,
        "parentObjectId": parent_obj_id,
        "childExpression": None,
        "parentExpression": None,
        "_renderer_note": (
            "world_implicit strategy: null expressions. "
            "ASSUMPTION: MPB infers parentage from world-object hierarchy. "
            "Unverified — delete if MPB rejects null expressions at import."
        ),
    }


def _trivial_synthetic_adapter_instance(
    rel: RelationshipDef,
    parent_obj_id: str,
    child_obj_id: str,
    ak: str,
    suffix: str = "",
) -> Dict:
    """Strategy: emit a synthetic @@@adapterInstance identifier on both ends.

    ASSUMPTION: MPB may have a built-in @@@adapterInstance attribute that
    identifies which adapter instance a resource belongs to. Using this as
    the join key would make all objects of the child type children of the
    same adapter instance world object. Wire format for @@@adapterInstance
    as a join field is unverified — this is an educated guess based on
    MPB's @@@id and @@@rawValue special attribute patterns.
    """
    name_suffix = f" ({suffix})" if suffix else ""
    rel_seed = f"{ak}:rel:{rel.parent}:{rel.child}:synthetic_adapter"
    rel_id = _make_id(rel_seed)
    part_id_child = _make_id(f"{rel_seed}:child:part")
    part_id_parent = _make_id(f"{rel_seed}:parent:part")
    expr_id_child = _make_id(f"{rel_seed}:child:expr")
    expr_id_parent = _make_id(f"{rel_seed}:parent:expr")

    # ASSUMPTION: @@@adapterInstance is a synthetic field available in MPB
    # expressions, similar to @@@id for list items. Both sides point to the
    # same virtual field, creating an always-match join.
    child_expr = {
        "id": expr_id_child,
        "expressionText": f"@@@MPB_QUOTE {part_id_child} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": part_id_child,
                "label": "@@@adapterInstance",
                "regex": None,
                "example": "",
                "originId": f"{ak}-@@@adapterInstance",
                "originType": "ATTRIBUTE",
                "regexOutput": "",
                "_renderer_note": (
                    "ASSUMPTION: @@@adapterInstance is a built-in MPB synthetic attribute "
                    "analogous to @@@id. Unverified wire format."
                ),
            }
        ],
    }
    parent_expr = {
        "id": expr_id_parent,
        "expressionText": f"@@@MPB_QUOTE {part_id_parent} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": part_id_parent,
                "label": "@@@adapterInstance",
                "regex": None,
                "example": "",
                "originId": f"{ak}-@@@adapterInstance",
                "originType": "ATTRIBUTE",
                "regexOutput": "",
            }
        ],
    }

    return {
        "id": rel_id,
        "name": f"{rel.parent} -> {rel.child}{name_suffix}",
        "designId": None,
        "caseSensitive": True,
        "childObjectId": child_obj_id,
        "parentObjectId": parent_obj_id,
        "childExpression": child_expr,
        "parentExpression": parent_expr,
    }


def _trivial_shared_constant(
    rel: RelationshipDef,
    parent_obj_id: str,
    child_obj_id: str,
    ak: str,
    suffix: str = "",
) -> Dict:
    """Strategy: synthesize a constant PROPERTY on both objects with the same value.

    Emits a relationship where both childExpression and parentExpression point to
    synthetic constant-property metric IDs. In this strategy, we define two
    "virtual" metric IDs that would need to be added to each object's metricSet
    as constant-valued properties.

    ASSUMPTION: The MPB engine supports a constant literal value as a join predicate.
    This may require the actual metrics to be present in the object's metricSet.
    If the MPB engine evaluates the expression at collection time and the metric
    doesn't exist, the join will fail silently.

    NOTE: The renderer does NOT add these synthetic metrics to the object's
    metricSet — doing so would pollute the object model. This relationship
    is emitted as a structural placeholder; the operator may need to add a
    constant property manually in the MPB UI.
    """
    name_suffix = f" ({suffix})" if suffix else ""
    rel_seed = f"{ak}:rel:{rel.parent}:{rel.child}:shared_constant"
    rel_id = _make_id(rel_seed)

    # Synthetic metric IDs for both sides
    # These would represent a constant PROPERTY with value "adapter_instance"
    child_metric_id = _make_id(f"{ak}:object:{rel.child}:metric:__adapter_instance_const")
    parent_metric_id = _make_id(f"{ak}:object:{rel.parent}:metric:__adapter_instance_const")

    child_expr = _make_rel_expression(
        "__adapter_instance_const", child_metric_id,
        f"{rel_seed}:child", "child"
    )
    parent_expr = _make_rel_expression(
        "__adapter_instance_const", parent_metric_id,
        f"{rel_seed}:parent", "parent"
    )

    return {
        "id": rel_id,
        "name": f"{rel.parent} -> {rel.child}{name_suffix}",
        "designId": None,
        "caseSensitive": True,
        "childObjectId": child_obj_id,
        "parentObjectId": parent_obj_id,
        "childExpression": child_expr,
        "parentExpression": parent_expr,
        "_renderer_note": (
            "shared_constant strategy: uses synthetic __adapter_instance_const metric. "
            "ASSUMPTION: MPB joins on a constant property added to each object. "
            "Synthetic metrics are NOT added to object metricSets by the renderer — "
            "add them manually in MPB UI if this approach is selected."
        ),
    }


def _render_events(
    mp: ManagementPackDef,
    request_registry: Dict[str, "_RequestInfo"],
    object_id_map: Dict[str, str],
) -> List[Dict]:
    """Render the events array.

    Each MPBEventDef → one MPB event entry.
    Wire format based on Rubrik MP (the only reference with events).

    NEEDS-RENDERER-WORK scenarios logged as warnings.
    """
    result: List[Dict] = []
    ak = mp.adapter_kind

    for ev in mp.mpb_events:
        wire = _render_one_event(ev, mp, request_registry, object_id_map, ak)
        if wire:
            result.append(wire)

    return result


def _render_one_event(
    ev,
    mp: ManagementPackDef,
    request_registry: Dict[str, "_RequestInfo"],
    object_id_map: Dict[str, str],
    ak: str,
) -> Optional[Dict]:
    """Render a single MPBEventDef to MPB event wire format."""
    ev_seed = f"{ak}:event:{ev.name}"
    ev_id = _make_id(ev_seed)

    # Resolve source request
    req_info = request_registry.get(ev.source_request)
    if not req_info:
        logger.warning(
            "Event %r: source_request %r not in registry; skipping.",
            ev.name, ev.source_request,
        )
        return None

    # The listId is the DML id for the event's response_path
    list_id = _response_path_to_dml_id(ev.response_path)

    # Ensure the DML is registered on the request (events may reference
    # response paths not covered by object metrics)
    if list_id != "base" and list_id not in req_info.dmls:
        req_info.ensure_dml(list_id)

    # NEEDS-RENDERER-WORK: severity mapping from a dynamic field
    # For events with match_normalizer or severity-map comments, we emit a fixed
    # severity and log a warning. The MPB runtime would need a severityMap to do
    # the mapping dynamically.
    severity_str = ev.severity.upper()

    # Check for NEEDS-RENDERER-WORK indicators
    needs_work_events = {
        "DSM Scrubbing Started", "DSM Scrubbing Finished",
        "DSM Update Available", "DSM Security Advisory", "DSM Disk Overheat",
        "Active Backup Package Transition",
    }
    if ev.name in needs_work_events:
        logger.warning(
            "Event %r: NEEDS-RENDERER-WORK — severity mapping and/or scrubbing path "
            "normalization required. Emitting fixed severity %r and simplified "
            "message binding. Review and adjust in MPB UI.",
            ev.name, severity_str,
        )

    # Build message expression (from message_template or fallback)
    message_expr = _render_event_message_expression(ev, req_info, list_id, ev_seed)

    # Build severity expression
    # For events where severity is dynamic (driven by a field like 'level' or 'severity'),
    # we emit a fixed severity value and a no-op expression pointing to a static field.
    # The MPB runtime needs a severityMap to do dynamic mapping — we include a default one.
    severity_expr = _render_event_severity_expression(ev, req_info, list_id, ev_seed, severity_str)

    # Severity map — default (static)
    # For events with dynamic severity (DSM level: info/warn/err) we emit the
    # DSM-to-Aria mapping. For others, a passthrough map.
    severity_map = _build_severity_map(ev)

    # Event matchers (object binding)
    event_matchers = _render_event_matchers(ev, req_info, list_id, ev_seed, object_id_map)

    # matchMode from match_rules (ALL if multiple rules, else single)
    match_mode = "ALL" if len(ev.match_rules) > 1 else "ALL"  # MPB uses ALL; one rule is also ALL

    # Return flat event (no {"event": ...} wrapper).
    # Wire format reference: mpb_rubrik_adapter3/conf/design.json §source.events.
    return {
        "id": ev_id,
        "alert": {
            "type": "APPLICATION",
            "badge": "HEALTH",
            "subType": "AVAILABILITY",
            "waitCycle": 1,
            "cancelCycle": 1,
            "recommendation": None,
        },
        "label": ev.name,
        "listId": list_id,
        "message": message_expr,
        "designId": None,
        "severity": severity_expr,
        "matchMode": match_mode,
        "requestId": req_info.id,
        "severityMap": severity_map,
        "eventMatchers": event_matchers,
        "defaultSeverity": severity_str,
        "unmatchedEventBehavior": "ATTACH_TO_ADAPTER",
    }


def _render_event_message_expression(ev, req_info, list_id: str, ev_seed: str) -> Dict:
    """Render the message expression for an event.

    If message_template is '${descr}', emit an expression pointing at the 'descr'
    attribute. Otherwise use the first field referenced or a generic fallback.
    """
    msg_seed = f"{ev_seed}:message"

    if ev.message_template:
        # Extract first ${field} reference from the template
        refs = re.findall(r"\$\{([a-zA-Z0-9_.]+)\}", ev.message_template)
        if refs:
            field = refs[0]
            attr_label = field
            # Build origin_id for this field in the DML
            origin_id = f"{req_info.id}-{list_id}-{attr_label}"
            # Register the attribute (may already exist)
            if list_id not in req_info.dmls:
                req_info.ensure_dml(list_id)
            if origin_id not in req_info._attr_ids:
                req_info._attr_ids[origin_id] = True
                req_info.dmls[list_id]["attributes"].append({
                    "id": origin_id,
                    "key": [field],
                    "label": attr_label,
                    "example": "",
                })
            return _make_expression(
                label=attr_label,
                origin_id=origin_id,
                origin_type="ATTRIBUTE",
                expr_seed=msg_seed,
            )

    # Fallback: point at the @@@id attribute
    origin_id = f"{req_info.id}-{list_id}-@@@id"
    return _make_expression(
        label="@@@id",
        origin_id=origin_id,
        origin_type="ATTRIBUTE",
        expr_seed=msg_seed,
    )


def _render_event_severity_expression(
    ev, req_info, list_id: str, ev_seed: str, default_severity: str
) -> Dict:
    """Render the severity expression.

    For events with dynamic severity (e.g. driven by 'level' or 'severity' fields),
    we emit an expression pointing at that field and rely on severityMap for mapping.
    For fixed-severity events, emit an expression pointing at @@@id with a no-op.

    HEURISTIC: if the event has a severityMap comment (NEEDS-RENDERER-WORK) and
    is from syslog_list or security_list, use the 'level' or 'severity' field.
    """
    sev_seed = f"{ev_seed}:severity"
    dynamic_sev_field = None

    # Events from syslog_list use 'level' as the severity carrier
    if ev.source_request == "syslog_list":
        dynamic_sev_field = "level"
    # Events from security_list use 'severity' field
    elif ev.source_request == "security_list":
        dynamic_sev_field = "severity"

    if dynamic_sev_field:
        attr_label = dynamic_sev_field
        origin_id = f"{req_info.id}-{list_id}-{attr_label}"
        if list_id not in req_info.dmls:
            req_info.ensure_dml(list_id)
        if origin_id not in req_info._attr_ids:
            req_info._attr_ids[origin_id] = True
            req_info.dmls[list_id]["attributes"].append({
                "id": origin_id,
                "key": [dynamic_sev_field],
                "label": attr_label,
                "example": "",
            })
        return _make_expression(
            label=attr_label,
            origin_id=origin_id,
            origin_type="ATTRIBUTE",
            expr_seed=sev_seed,
        )

    # Fixed severity — point at @@@id as a no-op carrier; severityMap passthrough
    origin_id = f"{req_info.id}-{list_id}-@@@id"
    return _make_expression(
        label="@@@id",
        origin_id=origin_id,
        origin_type="ATTRIBUTE",
        expr_seed=sev_seed,
    )


def _build_severity_map(ev) -> List[Dict]:
    """Build a severityMap for the event.

    For syslog_list events, DSM uses 'info', 'warn', 'err' (note: DSM misspells 'err').
    For security_list events, DSM uses 'low', 'medium', 'high'.
    For fixed-severity events, emit a simple passthrough map.
    """
    if ev.source_request == "syslog_list":
        return [
            {"rawSeverity": "info", "ariaOpsSeverity": "INFO"},
            {"rawSeverity": "warn", "ariaOpsSeverity": "WARNING"},
            {"rawSeverity": "err", "ariaOpsSeverity": "CRITICAL"},  # DSM misspelling (no 'or')
        ]
    if ev.source_request == "security_list":
        return [
            {"rawSeverity": "low", "ariaOpsSeverity": "INFO"},
            {"rawSeverity": "medium", "ariaOpsSeverity": "WARNING"},
            {"rawSeverity": "high", "ariaOpsSeverity": "CRITICAL"},
        ]
    if ev.source_request == "upgrade_check":
        # Dynamic: isSecurityVersion=true→WARNING, false→INFO (NEEDS-RENDERER-WORK)
        # Emit a reasonable default: passthrough of the fixed severity
        return [
            {"rawSeverity": "true", "ariaOpsSeverity": "WARNING"},
            {"rawSeverity": "false", "ariaOpsSeverity": "INFO"},
        ]
    # Passthrough
    return [
        {"rawSeverity": ev.severity, "ariaOpsSeverity": ev.severity},
    ]


def _render_event_matchers(ev, req_info, list_id: str, ev_seed: str, object_id_map: Dict[str, str]) -> List[Dict]:
    """Render eventMatchers (object binding predicates).

    Each matcher binds events to an object type by comparing a field in the
    event record against a metric in the target object.
    """
    if not ev.object_binding:
        return []

    ob = ev.object_binding
    obj_id = object_id_map.get(ob.object_type)
    if not obj_id:
        logger.warning(
            "Event %r: object_binding.object_type %r not in object_id_map; "
            "emitting empty eventMatchers.",
            ev.name, ob.object_type,
        )
        return []

    # Find a reasonable event-side field (match_field or 'descr' fallback)
    event_field = ob.match_field or "descr"
    attr_label = event_field
    origin_id = f"{req_info.id}-{list_id}-{attr_label}"

    # Register the field if needed
    if list_id not in req_info.dmls:
        req_info.ensure_dml(list_id)
    if origin_id not in req_info._attr_ids:
        req_info._attr_ids[origin_id] = True
        req_info.dmls[list_id]["attributes"].append({
            "id": origin_id,
            "key": [event_field],
            "label": attr_label,
            "example": "",
        })

    matcher_seed = f"{ev_seed}:matcher:{ob.object_type}"
    event_expr_id = _make_id(f"{matcher_seed}:eventExpr")
    event_part_id = _make_id(f"{matcher_seed}:eventPart")
    event_expr = {
        "id": event_expr_id,
        "expressionText": f"@@@MPB_QUOTE {event_part_id} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": event_part_id,
                "label": event_field,
                "regex": None,
                "example": "",
                "originId": origin_id,
                "originType": "ATTRIBUTE",
                "regexOutput": "",
            }
        ],
    }

    # For NEEDS-RENDERER-WORK match_normalizers, log and skip the normalizer
    if ob.match_normalizer:
        logger.warning(
            "Event %r: object_binding.match_normalizer %r is a NEEDS-RENDERER-WORK "
            "placeholder — complex field extraction not implemented. "
            "The match will compare the raw %r field value against the object's "
            "identifier. Manual adjustment in MPB UI may be required.",
            ev.name, ob.match_normalizer, event_field,
        )

    # Object-side expression: for INTERNAL objects we use the object type label
    # as an identifier reference. The MPB wire format (Rubrik) uses ARIA_OPS_METRIC
    # for ARIA_OPS type targets; for INTERNAL we use METRIC pointing at an identifier.
    # Since we don't know the exact identifier metric ID here (we'd need metric_id_map),
    # we emit a placeholder origin_id. This is a TOOLSET GAP — ideally we'd resolve
    # the object's first identifier metric ID, but object_id_map only has object.id,
    # not metric IDs.
    #
    # ASSUMPTION: the objectExpression for INTERNAL objects may work with the
    # object type ID directly, or MPB may automatically bind based on objectId alone.
    # The Rubrik example only shows ARIA_OPS type bindings. This is the largest
    # remaining unknown in event rendering.
    obj_expr_id = _make_id(f"{matcher_seed}:objectExpr")
    obj_part_id = _make_id(f"{matcher_seed}:objectPart")
    obj_expr = {
        "id": obj_expr_id,
        "expressionText": f"@@@MPB_QUOTE {obj_part_id} @@@MPB_QUOTE",
        "expressionParts": [
            {
                "id": obj_part_id,
                "label": ob.object_type,
                "regex": None,
                "example": "",
                "originId": obj_id,  # Using object.id as a placeholder
                "originType": "ATTRIBUTE",  # ASSUMPTION: may need METRIC for INTERNAL
                "regexOutput": "",
                "_renderer_note": (
                    "TOOLSET GAP: objectExpression for INTERNAL objects is unverified. "
                    "Rubrik reference only shows ARIA_OPS_METRIC bindings. "
                    "Adjust originId/originType in MPB UI if event matching fails."
                ),
            }
        ],
    }

    return [{
        "objectId": obj_id,
        "objectName": ob.object_type,
        "caseSensitive": False,
        "eventExpression": event_expr,
        "objectExpression": obj_expr,
    }]


def _list_id_to_response_path(list_id: str) -> Optional[str]:
    """Convert a DML list id (e.g. 'data.items.*') back to a response_path ('data.items')."""
    if list_id == "base":
        return None
    if list_id.endswith(".*"):
        return list_id[:-2]
    return list_id


def _render_content(mp: ManagementPackDef) -> List:
    """Render the content section. Empty for v1."""
    return []


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_mp_design_json(
    mp: ManagementPackDef,
    relationship_strategy: str = "synthetic_adapter_instance",
) -> dict:
    """Render a ManagementPackDef into the MPB design JSON structure.

    Output shape follows the flat Rubrik wire format
    (mpb_rubrik_adapter3/conf/design.json, confirmed working on VCF Ops 9.0.2):

      {
        "version": 1,
        "id": "<stable-id>",
        "name": "<adapter display name>",
        "pakSettings": { "adapterKind", "author", "name", "version", ... },
        "source": {
          "type": "HTTP",
          "basePath": "",
          "testRequestId": "<id or null>",
          "authentication": { ... },
          "configuration": [ ... ],       <- adapter connection fields
          "requests": { "<id>": { ... } },  <- dict, not array
          "resources": [ ... ],            <- flat objects (no {"object"} wrapper)
          "externalResources": [],
          "events": [ ... ]               <- flat events (no {"event"} wrapper)
        },
        "constants": [],
        "relationships": [ ... ]           <- flat (no {"relationship"} wrapper)
      }

    Previously the factory emitted a doubly-nested structure:
      { "design": {"design": {...}}, "source": {"source": {...}},
        "requests": [...], "objects": [...], ... }
    which caused the MPB runtime to silently fail adapter registration on
    VCF Ops 9.0.2 (~25s parse-fail-and-abort, not actual install time).

    relationship_strategy controls how adapter-instance-trivial relationships
    (null child_expression / parent_expression) are rendered. Valid values:
      - "world_implicit": emit relationship with null expressions,
        trust MPB to infer from world-object parentage
      - "synthetic_adapter_instance": emit a synthetic @@@adapterInstance
        identifier on both ends
      - "shared_constant_property": emit a constant property field on
        both ends whose values match
      - "test_all": emit three separate relationships, one per strategy,
        all with the same parent/child pair but distinguishable names;
        at import time the operator picks the one that works

    Returns the full MPB design JSON dict (not serialized).
    """
    # --- pakSettings ---
    pak_settings = _render_pak_settings(mp)

    # --- requests (deduplication + registry) ---
    wire_requests, request_registry = _render_requests(mp)

    # --- objects (resources in Rubrik terminology) ---
    wire_objects = _render_objects(mp, request_registry)

    # Build lookup maps for relationships and events
    # object_id_map: object_key → object.id
    object_id_map: Dict[str, str] = {}
    # metric_id_map: object_key → {metric_key → metric_id}
    metric_id_map: Dict[str, Dict[str, str]] = {}

    ak = mp.adapter_kind
    for ot in mp.object_types:
        obj_seed = f"{ak}:object:{ot.key}"
        object_id_map[ot.key] = _make_id(obj_seed)
        metric_id_map[ot.key] = {}
        for m in ot.metrics:
            metric_id_map[ot.key][m.key] = _make_id(f"{obj_seed}:metric:{m.key}")

    # --- relationships (flat, no wrapper) ---
    wire_relationships = _render_relationships(
        mp, object_id_map, metric_id_map, relationship_strategy
    )

    # --- events (flat, no wrapper) ---
    wire_events = _render_events(mp, request_registry, object_id_map)

    # --- source (contains requests, resources, events) ---
    source_section = _render_source(mp, wire_requests, wire_objects, wire_events)

    # --- summary log ---
    trivial_count = sum(
        1 for r in mp.relationships if r.scope == "adapter_instance"
    )
    join_count = sum(
        1 for r in mp.relationships if r.scope == "field_match"
    )
    emitted_rel_count = len(wire_relationships)

    logger.info(
        "Rendered %s: %d requests, %d objects, %d relationships emitted "
        "(%d with join predicates, %d containment-only dropped), "
        "%d events.",
        mp.name,
        len(wire_requests),
        len(wire_objects),
        emitted_rel_count,
        join_count,
        trivial_count,
        len(wire_events),
    )
    print(
        f"Rendered {mp.name}: "
        f"{len(wire_requests)} requests, "
        f"{len(wire_objects)} objects, "
        f"{emitted_rel_count} relationships emitted "
        f"({join_count} join predicates, "
        f"{trivial_count} containment-only dropped), "
        f"{len(wire_events)} events.",
        file=sys.stderr,
    )

    return {
        "version": 1,
        "id": _make_id(f"{mp.adapter_kind}:design"),
        "name": mp.name,
        "pakSettings": pak_settings,
        "source": source_section,
        "constants": [],
        "relationships": wire_relationships,
    }
