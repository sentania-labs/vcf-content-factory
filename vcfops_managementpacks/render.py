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
    AriaOpsConf,
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
    PagingDef,
    RelationshipDef,
    RequestDef,
    WorldIdentityDef,
    derive_key_from_label,
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


def _chain_wire_key(bind_name: str) -> str:
    """Map a YAML bind name to its inherited/fallback wire requestParameters key.

    Used for INHERITED chain params (propagated from ancestor chains at runtime)
    and for the default non-request-scoped path.  The jcox UniFi reference
    (ground truth, 2026-05-14) uses a naming convention that avoids collisions
    between chain param keys and identifier metric keys in MPB's Properties screen.
    Identifier keys follow the '<thing>_id' pattern (e.g. device_id).  The wire
    key uses the inverse form: 'id_<thing>' (e.g. id_device, id_site, id_volume).

    Mapping rule:
      - bind_name == 'id'           → wire key 'id'      (single bare id, no collision possible)
      - bind_name ends with '_id'   → wire key 'id_<stem>'  (e.g. 'device_id' → 'id_device')
      - otherwise                   → wire key 'id_<bind_name>'  (prefix for safety)

    NOTE: for DIRECT (own) chain params on a child request, use
    _chain_wire_key_for_request(bind_name, child_req_name) instead to get a
    per-request-scoped key that avoids duplicate-attribute collisions on objects
    with two chained children sharing the same bind name (Bug 1 fix, 2026-05-14).

    Evidence: context/render_export_strip_audit_2026_05_14.md §chainingSettings.params
    Adopted 2026-05-14 to fix e135142 over-strip regression.
    """
    if bind_name == "id":
        return "id"
    if bind_name.endswith("_id"):
        stem = bind_name[:-3]
        return f"id_{stem}"
    return f"id_{bind_name}"


def _chain_wire_key_for_request(bind_name: str, child_req_name: str) -> str:
    """Map a YAML bind name + child request name to a per-request-scoped wire key.

    Bug 1 fix (2026-05-14): when an object type has two chained children that
    both bind the same attribute name (e.g. device_stats_ap and device_detail_ap
    both bind device_id), the naive _chain_wire_key produces the same wire key
    (id_device) for both.  MPB's Properties panel unions chain params across all
    requests for an object type and rejects duplicate labels.

    Fix (Option A): scope the key by child request name, making it globally unique.
    Each chain param key is id_<child_request_name>, regardless of bind_name.
    For the common single-bind case this is unambiguous.  For multi-bind requests
    (hypothetical), the index is appended: id_<child_req_name>_<bind_index>.

    The label follows the same convention as _chain_wire_key: "ID" + title-case
    of everything after the "id_" prefix.

    Examples (single-bind):
      (device_id, device_stats_ap)  → id_device_stats_ap
      (device_id, device_detail_ap) → id_device_detail_ap
      (site_id,   devices_ap)       → id_devices_ap
      (id,        get_sites_all)    → id_get_sites_all

    NOTE: the YAML ${chain.*} tokens in request paths/params/body are rewritten
    using the _own_chain_map stored on _RequestInfo (set by _build_chaining_settings).
    Inherited ancestor chain params (not in _own_chain_map) continue to use
    _chain_wire_key() so they match the ancestor's chainingSettings.params key.

    Codified 2026-05-14.  See context/mp_chain_authoring.md §wire key mapping.
    """
    return f"id_{child_req_name}"


def _rewrite_chain_tokens(text: str, own_chain_map: Optional[Dict[str, str]] = None) -> str:
    """Rewrite ${chain.<name>} → ${requestParameters.<wire_key>} in any string.

    Uses _chain_wire_key() to map bind names to collision-safe wire keys for
    inherited chain params, and own_chain_map for direct (own) chain params.

    own_chain_map: dict of {bind_name: wire_key} for the current request's own
    chainingSettings params.  When provided, tokens matching an own bind name
    are rewritten with the scoped key; all other tokens (inherited from ancestor
    chains) fall back to _chain_wire_key().

    E.g. for device_stats_ap with own_chain_map={'device_id': 'id_device_stats_ap'}:
      ${chain.site_id}   → ${requestParameters.id_site}       (inherited, fallback)
      ${chain.device_id} → ${requestParameters.id_device_stats_ap}  (own, scoped)
    """
    def _replace(m: "re.Match") -> str:
        bname = m.group(1)
        if own_chain_map and bname in own_chain_map:
            return f"${{requestParameters.{own_chain_map[bname]}}}"
        return f"${{requestParameters.{_chain_wire_key(bname)}}}"

    return _CHAIN_TOKEN_RE.sub(_replace, text)


def _rewrite_auth_refs(text: str) -> str:
    """Rewrite short auth variable references to the MPB full forms.

    ${credentials.<key>} → ${authentication.credentials.<key>}
    ${session.<key>}     → ${authentication.session.<key>}

    The MPB runtime only recognises the long form; the YAML author uses the
    short form for readability.  Applied to request path, body, param values,
    header values, and inject rule values.
    """
    if not text:
        return text
    text = re.sub(r"\$\{credentials\.([a-zA-Z0-9_]+)\}",
                  r"${authentication.credentials.\1}", text)
    text = re.sub(r"\$\{session\.([a-zA-Z0-9_]+)\}",
                  r"${authentication.session.\1}", text)
    return text


def _rewrite_params(params: Any, own_chain_map: Optional[Dict[str, str]] = None) -> Any:
    """Apply _rewrite_chain_tokens and _rewrite_auth_refs to all param values."""
    if not params:
        return params
    if isinstance(params, list):
        result = []
        for p in params:
            if isinstance(p, dict):
                v = p.get("value", "")
                rewritten = _rewrite_chain_tokens(str(v), own_chain_map) if v else ""
                rewritten = _rewrite_auth_refs(rewritten) if rewritten else rewritten
                result.append({"key": p.get("key", ""), "value": rewritten})
            else:
                result.append(p)
        return result
    if isinstance(params, dict):
        return {k: _rewrite_auth_refs(_rewrite_chain_tokens(str(v), own_chain_map)) for k, v in params.items()}
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

    NOTE: list_path values ending in ".*" are stripped before composition to
    avoid double-star paths (e.g. "volumes.*" → "volumes" → "data.volumes.*").
    The loader emits a DeprecationWarning for these; this normalization ensures
    pre-fix YAMLs render correctly while the lint is in warning-only mode.
    """
    rp = (response_path or "").strip()
    lp = list_path.strip() if list_path else ""
    # Normalize: strip trailing .* from list_path (the renderer always appends .*)
    if lp.endswith(".*"):
        lp = lp[:-2]

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
    # Normalize: strip trailing .* from list_path (matches _compute_dml_id)
    if lp.endswith(".*"):
        lp = lp[:-2]

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
        "label": "Connection Timeout (s)",
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
        "label": "Maximum Concurrent Requests",
        "usage": "${configuration.mpb_concurrent_requests}",
        "value": None,
        "options": None,
        "advanced": True,
        "editable": False,
        "configType": "NUMBER",
        "description": "Maximum number of concurrent HTTP requests.",
        # Template default 15; per-MP YAML overrides via src.max_concurrent.
        # MPB ships 2 / Verify; factory ships higher concurrency / No Verify
        # intentionally — parallel collection, lab-friendly TLS.
        # See context/mp_format_comparison_2026_05_15.md §item 5.
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
        "label": "SSL Configuration",
        "usage": "${configuration.mpb_ssl_config}",
        "value": None,
        # Options in title-case to match working export (synology_nas_working_export.json §source):
        # working: ["No Verify", "Verify", "No SSL"]
        # Previous all-caps form ("NO_VERIFY" etc.) caused SINGLE_SELECTION mismatch.
        "options": ["No Verify", "Verify", "No SSL"],
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
        # Options in title-case to match working export (synology_nas_working_export.json §source):
        # working: ["Critical", "Immediate", "Warning", "Info"]
        # defaultValue must be one of these options — previous "WARNING" (all-caps) caused
        # SINGLE_SELECTION validator rejection at MPB import time.
        "options": ["Critical", "Immediate", "Warning", "Info"],
        "advanced": True,
        "editable": False,
        "configType": "SINGLE_SELECTION",
        "description": "Minimum severity level for event collection.",
        "defaultValue": "Warning",
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
        # bind_name → wire_key map for this request's OWN chain params (Bug 1 fix).
        # Inherited ancestor chain params are NOT in this map; they use _chain_wire_key() fallback.
        # Set by _build_chaining_settings (called from _render_requests) and consumed by to_wire().
        self._own_chain_map: Dict[str, str] = {}
        # bind_name → (param_id, wire_key) for this request's OWN chain params (Pattern V, Bug 4).
        # param_id is the chainingSettings.params[N].id UUID.  Used by _render_one_object to
        # build objectBinding.matchExpression with originType=PARAMETER.
        # Set by _render_requests alongside _own_chain_map; absent = empty dict.
        self._own_chain_param_ids: Dict[str, Tuple[str, str]] = {}

    def register_field(self, field_path: str, dml_id: str) -> str:
        """Register a field and return its attribute-origin ID.

        dml_id is the fully-computed DML id (e.g. 'data.volumes.*' or 'base').
        field_path is the attribute label within the DML (relative to list item).
        The attribute origin ID is: <request_id>-<dml_id>-<attr_label>.

        Gap F (2026-04-30): field_path may contain JMESPath filter predicates
        such as ``radio_table_stats[?radio=='ng'].cu_total | [0]``.  Plain
        ``split('.')`` is unsafe for these paths because the predicate contains
        literal dots inside brackets.

        Key-array strategy for JMESPath paths:
          - If the path contains no ``[?`` predicate, split on '.' as before.
          - If the path contains a ``[?`` predicate, emit the full path as a
            single-element key array.  This preserves the expression verbatim
            for MPB runtime evaluation.  The label is the full path string.
          - The ``| [0]`` pipe-scalar suffix is kept in the key/label; it is
            the standard JMESPath idiom for forcing a scalar from a list result.
        """
        attr_label = field_path  # label is always the full path string

        # Gap F: choose key-array strategy based on predicate presence.
        if "[?" in field_path:
            # JMESPath filter predicate — emit full expression as single token.
            attr_key_path: List[str] = [field_path]
        else:
            attr_key_path = field_path.split(".")

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
        # Rewrite ${chain.*} tokens in path and params before normalizing.
        # Pass _own_chain_map so that OWN chain params (direct binds on this request)
        # use the per-request-scoped wire key (e.g. id_device_stats_ap) while
        # INHERITED chain params (from ancestor chains) keep the fallback key (e.g. id_site).
        ocm = self._own_chain_map if self._own_chain_map else None
        path = _rewrite_chain_tokens(req.path, ocm) if req.path else req.path
        path = _rewrite_auth_refs(path) if path else path
        body = _rewrite_chain_tokens(req.body, ocm) if req.body else req.body
        body = _rewrite_auth_refs(body) if body else body
        raw_params = _rewrite_params(req.params, ocm)
        # params: always a list of {key, value}
        params = _normalize_params(raw_params)
        dmls = list(self.dmls.values())

        return {
            "id": self.id,
            "body": body,
            "name": req.name,
            "path": path,
            "method": req.method,
            "paging": _render_paging(req.paging),
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


def _render_paging(pg: Optional["PagingDef"]) -> Optional[Dict]:
    """Render an explicit PagingDef to the MPB paging wire block.

    Returns None when no paging is declared (the common case).

    NOTE: The `paging:` YAML key is retired (2026-04-21).  The loader always
    sets RequestDef.paging=None, so this function always returns None from the
    YAML-driven path.  It is preserved for the flat-render path only.

    Wire format confirmed from context/mpb_wire_reference/synology_nas_working_export.json
    (2026-04-21 ground truth).  Key name is `pagingStart` (not `start`).
    The paging block also has a `response` sub-block with its own dataModelLists,
    which MPB populates from live API responses — we do not synthesize it here
    because the content is runtime-derived (wildcard variant permutations).

    MPB derives the paging block from live response data during interactive
    creation — authors do not need to declare it.  The factory emits no paging
    block; MPB populates it on first live run.
    """
    if pg is None:
        return None
    return {
        "type": pg.type,
        "pagingParam": pg.paging_param,
        "limitParam": pg.limit_param,
        "limitValue": pg.limit_value,
        "listPathId": pg.list_path_id,
        "pagingStart": pg.start,
    }


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
# ARIA_OPS label helpers
# ---------------------------------------------------------------------------

# Hardcoded adapter kind label overrides for known MPB adapter types.
# "VMWARE" → "vCenter" matches the MPB UI label observed in the ground truth.
_ARIA_OPS_ADAPTER_LABELS: Dict[str, str] = {
    "VMWARE": "vCenter",
}


def _humanize_aria_label(raw: str) -> str:
    """Insert spaces to humanize a CamelCase or PascalCase identifier.

    Handles acronyms correctly — consecutive uppercase sequences are kept
    together as one word, and a space is inserted before a new word that
    starts with an uppercase letter followed by a lowercase letter.

    Examples:
      "HostSystem"       → "Host System"
      "VirtualMachine"   → "Virtual Machine"
      "VMEntityObjectID" → "VM Entity Object ID"
      "VMEntityName"     → "VM Entity Name"

    For adapter kind labels, _ARIA_OPS_ADAPTER_LABELS provides exact overrides
    (e.g. "VMWARE" → "vCenter").
    """
    if raw in _ARIA_OPS_ADAPTER_LABELS:
        return _ARIA_OPS_ADAPTER_LABELS[raw]
    # Step 1: insert space between a run of >= 2 uppercase letters and the next
    # uppercase+lowercase sequence (e.g. "VMEntity" → "VM Entity").
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", raw)
    # Step 2: insert space between a lowercase/digit and an uppercase letter
    # (e.g. "hostMoid" → "host Moid").
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return s


def _render_aria_ops_conf(aria_ops: "AriaOpsConf", obj_seed: str) -> Dict:
    """Render the ariaOpsConf block for an ARIA_OPS object type.

    The ariaOpsConf declares the target Aria Ops resource kind and provides
    a minimal metric set containing only the binding metric
    (usage: ARIA_OPS_REFERENCE_ID).  MPB uses this metric's UUID as the
    cross-reference target in the metricSet's objectMatchExpression.

    Wire format ground truth:
      context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json
      §objects[0].object.ariaOpsConf

    The binding metric's usage is "ARIA_OPS_REFERENCE_ID" (NOT
    "ARIA_OPS_REFERENCE_PROPERTY") — confirmed from the ground truth where
    VMEntityObjectID carries ARIA_OPS_REFERENCE_ID.  Other reference metrics
    in the 206-metric ariaOpsConf use ARIA_OPS_REFERENCE_PROPERTY, but we
    only emit the one binding metric.

    The expressionText for ariaOpsConf metrics is "" (empty string), not
    the "@@@MPB_QUOTE..." format used by regular metrics.
    """
    conf_seed = f"{obj_seed}:ariaOpsConf"
    metric_set_id = _make_id(f"{conf_seed}:metricSet")
    bind_metric_id = _make_id(f"{conf_seed}:metric:{aria_ops.bind_metric}")

    # Expression for the bind metric — points at the Aria Ops metric key
    expr_id = _make_id(f"{conf_seed}:metric:{aria_ops.bind_metric}:expr")
    part_id = _make_id(f"{conf_seed}:metric:{aria_ops.bind_metric}:expr:part")

    bind_metric_expr = {
        "id": expr_id,
        "expressionText": "",
        "expressionParts": [
            {
                "id": part_id,
                "originType": "ARIA_OPS_METRIC",
                "originId": aria_ops.bind_metric,
                "label": aria_ops.bind_metric,
            }
        ],
    }

    resource_kind_label = _humanize_aria_label(aria_ops.resource_kind)
    adapter_kind_label = _humanize_aria_label(aria_ops.adapter_kind)
    bind_metric_label = _humanize_aria_label(aria_ops.bind_metric)

    return {
        "objectType": aria_ops.resource_kind,
        "objectTypeLabel": resource_kind_label,
        "adapterType": aria_ops.adapter_kind,
        "adapterTypeLabel": adapter_kind_label,
        "metricSet": {
            "id": metric_set_id,
            "metrics": [
                {
                    "id": bind_metric_id,
                    "label": bind_metric_label,
                    "dataType": "STRING",
                    "expression": bind_metric_expr,
                    "isKpi": False,
                    "usage": "ARIA_OPS_REFERENCE_ID",
                    "unit": "",
                    "groups": [],
                }
            ],
        },
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
    externalResources contains ARIA_OPS objects (same format as resources[])
    that stitch metrics onto existing adapter resource kinds at collection time.
    render_template.py converts these to the template.json externalResources shape.
    """
    src = mp.source

    # authentication block
    authentication = _render_authentication(mp)

    # adapter-instance configuration fields (Rubrik calls this "configuration")
    adapter_config_fields = list(_STANDARD_CONFIG_FIELDS)
    if src:
        # Use enumerate so that modified copies are written back into the list.
        # The previous `for cf in ...` loop rebind pattern lost all mutations
        # because the rebind only affected the local loop variable, not the list.
        #
        # mpb_ssl_config is intentionally omitted from this override map.
        # The YAML ssl field uses loader enum values (NO_VERIFY, VERIFY, NO_SSL)
        # but the MPB SINGLE_SELECTION options list uses display values
        # ("No Verify", "Verify", "No SSL").  Setting defaultValue to the loader
        # enum form ("NO_VERIFY") causes SINGLE_SELECTION validator rejection at
        # MPB import time (confirmed: context/mpb_synology_import_diff_2026_04_29.md §7).
        # The ssl default is user-configured per adapter instance; leave it as None
        # so MPB forces the operator to pick explicitly.
        _SRC_OVERRIDES = {
            "mpb_port":               src.port,
            "mpb_connection_timeout": src.timeout,
            "mpb_max_retries":        src.max_retries,
            "mpb_concurrent_requests": src.max_concurrent,
        }
        for idx, cf in enumerate(adapter_config_fields):
            if cf["id"] in _SRC_OVERRIDES:
                cf = dict(cf)
                cf["defaultValue"] = _SRC_OVERRIDES[cf["id"]]
                adapter_config_fields[idx] = cf

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

    # externalResources: ARIA_OPS objects that stitch metrics onto existing
    # Aria Ops resource kinds (e.g. VMWARE/HostSystem, VMWARE/Datastore).
    # These are the same objects that appear in resources[] — they carry
    # ariaOpsConf + metricSets in design.json format.  render_template.py
    # converts them to template.json externalResources format (with
    # requestedMetrics, adapterKind, resourceKind, etc.).
    # Fix 2026-05-15: previously hard-coded to []; ARIA_OPS-stitching MPs
    # (e.g. vSphere Storage Paths) had zero-metric collection as a result.
    # See context/mp_format_comparison_2026_05_15.md §item 1.
    external_resources = [obj for obj in wire_objects if obj.get("type") == "ARIA_OPS"]

    return {
        "type": "HTTP",
        "basePath": src.base_path if src else "",
        "testRequestId": test_request_id,
        "authentication": authentication,
        "configuration": adapter_config_fields,
        "globalHeaders": _render_global_headers(mp),
        "requests": requests_dict,
        "resources": wire_objects,          # flat array (no {"object": ...} wrapper)
        "externalResources": external_resources,  # ARIA_OPS stitching objects
        "events": wire_events,              # flat array (no {"event": ...} wrapper)
    }


def _render_cred_field(ak: str, cred, seed_suffix: str) -> Dict:
    """Render one CredentialFieldDef to the MPB wire shape."""
    cred_id = _make_id(f"{ak}:auth:{seed_suffix}:{cred.key}")
    return {
        "id": cred_id,
        "key": cred.key,
        "label": cred.label,
        "usage": f"${{authentication.credentials.{cred.key}}}",
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

    # Rewrite ${credentials.<key>} → ${authentication.credentials.<key>} at emit.
    # Delegates to the module-level _rewrite_auth_refs() function.
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
        "body": _rewrite_auth_refs(req.body) if req.body else req.body,
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

    if auth.preset == "http_header":
        # Stateless header-based auth (e.g. X-API-Key).
        # Emits CUSTOM credential type with no sessionSettings block.
        # TOKEN was previously emitted here but appears in zero known-working MPB
        # imports and caused HTTP 400 on POST /internal/mpbuilder/designs/import.
        # HoL GitLab-Basic (credentialType: CUSTOM, sessionSettings: null, single
        # API-key header via globalHeaders) is the correct analogue (2026-05-07).
        # The inject[] rules on this preset render into globalHeaders (handled in
        # _render_global_headers) alongside Content-Type.
        creds = [_render_cred_field(ak, c, "http_header") for c in auth.credentials]
        return {
            "creds": creds,
            "credentialType": "CUSTOM",
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

        # Session variables from extract rule(s).
        #
        # Gap B (2026-04-30): auth.extract is now List[ExtractRuleDef], allowing
        # multiple session variables from one login response (e.g. TOKEN cookie +
        # x-csrf-token header for UniFi classic-session auth).
        #
        # For each binding:
        #   key   — internal identifier for substitution; MPB requires [A-Za-z0-9_]+.
        #            Derived from bind_to (e.g. "set_cookie"), NOT the raw header name.
        #   path  — the literal HTTP header name / JSON path for extraction.
        #   usage — the ${authentication.session.<key>} template used in inject rules.
        #   location — HEADER or BODY.
        #
        # Wire parity: Synology reference (sentania_aria_operations_dsm_mp) uses one
        # entry; UniFi requires two.  sessionVariables is already an array in the wire
        # format — adding a second entry is the natural extension.
        session_variables = []
        for ex in auth.extract:
            session_key = ex.session_key
            session_var_id = _make_id(f"{ak}:auth:sessionVar:{session_key}")
            session_variables.append({
                "id": session_var_id,
                "key": session_key,        # ident-safe: from bind_to (e.g. "set_cookie")
                "path": [ex.name],         # literal header name / JSON path for extraction
                "usage": f"${{authentication.session.{session_key}}}",
                "example": None,
                "location": ex.location,
            })

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

    For cookie_session preset: emit Content-Type + inject[] rules (session refs).
    For http_header preset: emit Content-Type + inject[] rules (credential refs).
    For other presets / no auth: emit just Content-Type.

    Wire format requires header type: REQUIRED | IMMUTABLE | CUSTOM.
    Reference MP: Content-Type is REQUIRED; injected auth headers are CUSTOM.

    Gap 1 (2026-05-07): http_header preset processes inject rules the same way
    as cookie_session but rewrites ${credentials.<key>} references instead of
    ${session.<key>} references.  This allows static API-key headers (e.g.
    X-API-Key) to be emitted as globalHeaders using the standard inject grammar.
    """
    src = mp.source
    if not src or not src.auth or src.auth.preset not in ("cookie_session", "http_header"):
        # Default: just Content-Type
        return [
            {"key": "Content-Type", "type": "REQUIRED", "value": "application/json"}
        ]

    auth = src.auth
    headers: List[Dict] = []
    content_type_added = False

    for rule in auth.inject:
        key = rule.name
        value = _rewrite_auth_refs(rule.value)
        if key == "Content-Type":
            content_type_added = True
            htype = "REQUIRED"
        else:
            # Non-Content-Type inject rules are CUSTOM per wire format
            # Reference: Synology {"key": "id", "type": "CUSTOM", "value": "..."}
            #            jcox unifi {"key": "X-API-KEY", "type": "CUSTOM", "value": "..."}
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

    # Step 1b: pre-scan all metricSets to detect (parent_req_name, bind_name) collision pairs.
    # A collision occurs when two different child requests both chain from the same parent
    # with the same bind name on the same object type.  The naive _chain_wire_key scheme
    # would produce identical wire keys for both (e.g. id_device for device_id), causing
    # MPB Properties panel to show duplicate attribute labels.
    # For colliding pairs, _build_chaining_settings applies the per-request-scoped key
    # scheme (Option A: id_<child_req_name>).  Non-colliding pairs keep the simpler
    # _chain_wire_key scheme for cleaner wire output.
    # Scope: per-object-type.  Two different object types using the same (parent, bind_name)
    # pair do not collide because their chain params live in separate object namespaces.
    _colliding_pairs: set = set()  # set of (ot_key, parent_req_name, bind_name)
    for ot in mp.object_types:
        _chain_use: Dict[tuple, set] = {}  # (parent_req_name, bind_name) → {child_req_names}
        for ms in ot.metric_sets:
            if ms.chained_from is None:
                continue
            for b in ms.bind:
                key = (ms.chained_from, b.name)
                _chain_use.setdefault(key, set()).add(ms.from_request)
        for (parent_req_name, bind_name), child_set in _chain_use.items():
            if len(child_set) > 1:
                _colliding_pairs.add((ot.key, parent_req_name, bind_name))
                logger.info(
                    "Object '%s': bind_name '%s' on parent '%s' is shared by %d "
                    "child requests (%s) — applying per-request chain key scoping (Option A).",
                    ot.key, bind_name, parent_req_name, len(child_set),
                    ", ".join(sorted(child_set)),
                )

    # Step 2: process each object_type's metricSets
    for ot in mp.object_types:
        # Build map: metricSet.local_name → MetricSetDef
        ms_by_name: Dict[str, MetricSetDef] = {ms.local_name: ms for ms in ot.metric_sets}

        # Determine if this object type uses scalar (base DML) context.
        # Both is_world and is_singleton consume the response root as a
        # scalar — no list iteration, all metricSets use listId "base".
        # is_world  → adapter-instance root, no identifiers, MPB-managed rollups.
        # is_singleton → one-per-adapter named entity with identifiers and metrics.
        # List kinds (default) iterate over response rows; each row is one object.
        is_scalar = ot.is_world or ot.is_singleton

        # Build map: metricSet.local_name → (req, dml_id)
        ms_dml: Dict[str, Tuple[RequestDef, str]] = {}
        for ms in ot.metric_sets:
            req = req_by_name[ms.from_request]
            if is_scalar:
                # Scalar kinds always use the "base" DML regardless of response_path
                # or list_path.  The computed dml_id would be e.g. "data.*" (from
                # response_path="data", list_path=""), which is wrong — it creates a
                # spurious wildcard DML on what should be a scalar-context request.
                # Working export (2026-04-21) confirms: both world and singleton
                # requests carry ONLY a "base" DML in their dataModelLists.
                dml_id = "base"
            else:
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

            if is_scalar:
                # Scalar kind: DML is "base"; prepend response_path to field_path so
                # the attribute originId encodes the full path from the response root.
                # e.g. response_path="data", field_path="cpu_clock_speed"
                #   → full_fp="data.cpu_clock_speed", DML attr label="data.cpu_clock_speed"
                # This matches the working export's originId pattern:
                #   "<reqId>-base-data.cpu_clock_speed"
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

            # Gap 2 (2026-05-07): chained_from may reference a cross-object-type
            # chain root — a top-level request that is NOT consumed as a from_request
            # on any metricSet (including siblings on this object type).
            # Detection: chained_from name is absent from ms_by_name but present in
            # req_by_name.  For chain roots:
            #   - parent_dml_id is computed from the root request's response_path
            #     with an empty list_path (the root has no associated metricSet to
            #     supply a list_path).
            #   - bind.from_attribute entries are auto-synthesized onto the chain
            #     root's DML the same way as for sibling chains.
            #   - chainingSettings on the child is built identically.
            if ms.chained_from not in ms_by_name:
                # Cross-type chain root
                chain_root_req = req_by_name[ms.chained_from]
                parent_req = chain_root_req
                parent_dml_id = _compute_dml_id(chain_root_req.response_path, "")
            else:
                parent_req, parent_dml_id = ms_dml[ms.chained_from]

            child_req, child_dml_id = ms_dml[ms.local_name]
            parent_req_info = registry[parent_req.name]
            child_req_info = registry[child_req.name]

            # Auto-synthesize any bind.from_attribute not already in parent's DML.
            # For chain roots, ms_fields does not have an entry keyed by the root
            # request name (only sibling metricSet names are in ms_fields), so we
            # always auto-synthesize for chain-root binds.
            #
            # Bug 4 (2026-05-15): the previous Bug 2d addition synthesized
            # b.from_attribute on the CHILD's own DML so that the Synology-pattern
            # (ATTRIBUTE-origin) matchExpression had something to point at.  Pattern V
            # (PARAMETER-origin) does not need this synthesis — the matchExpression
            # points at the chain param's UUID directly, not at a DML attribute.
            # The synthesis is removed here.  Parent DML synthesis is retained (it is
            # still needed so chainingSettings.params[].attributeExpression can
            # reference the correct parent-row attribute).
            for b in ms.bind:
                if b.from_attribute not in ms_fields.get(ms.chained_from, set()):
                    # Attribute not sourced by any metric; synthesize it on parent DML
                    parent_req_info.register_field(b.from_attribute, parent_dml_id)
                    logger.info(
                        "Object '%s' metricSet '%s': auto-synthesized attribute "
                        "'%s' on parent request '%s' DML '%s' for chain bind.",
                        ot.name, ms.local_name,
                        b.from_attribute, parent_req.name, parent_dml_id,
                    )

            # Build chainingSettings for the child request
            # (uses parent request ID + parent DML id + bind entries)
            # Returns (chain_settings_dict, own_chain_map, own_chain_param_ids) —
            # see _build_chaining_settings.
            chain_settings, own_chain_map, own_chain_param_ids = _build_chaining_settings(
                parent_req_info=parent_req_info,
                parent_dml_id=parent_dml_id,
                ms=ms,
                child_req_name=child_req.name,
                parent_req_name=parent_req.name,
                ak=ak,
                ot_key=ot.key,
                colliding_pairs=_colliding_pairs,
            )
            # Set chainingSettings, own_chain_map, and own_chain_param_ids on child request.
            # Last write wins if multiple object_types chain the same child request
            # (should not happen in v1 but is safe — keys are per-request-unique).
            child_req_info._chaining_settings = chain_settings
            child_req_info._own_chain_map = own_chain_map
            child_req_info._own_chain_param_ids = own_chain_param_ids

    # Step 4: ensure every request has at least a "base" DML.
    # Requests that are declared in the YAML but not consumed by any object
    # (e.g. storage_info, network_info in the Synology KISS variant) would
    # otherwise emit dataModelLists: [] — MPB does not accept empty DML lists
    # and the reference (working export 2026-04-21) shows all requests carry
    # at minimum a "base" entry.
    for info in registry.values():
        info.ensure_dml("base")

    wire = [info.to_wire() for info in registry.values()]
    return wire, registry


def _build_chaining_settings(
    parent_req_info: "_RequestInfo",
    parent_dml_id: str,
    ms: "MetricSetDef",
    child_req_name: str,
    parent_req_name: str,
    ak: str,
    ot_key: str,
    colliding_pairs: set,
) -> Tuple[Dict, Dict[str, str]]:
    """Build the chainingSettings block for a child request.

    Wire format per context/mpb_chaining_wire_format.md §2.

    baseListId = parent_dml_id (the DML the chain iterates over).
    params[] = one entry per bind entry.
    Each param's attributeExpression points at the parent DML attribute.

    Wire key scheme (Bug 1 fix, 2026-05-14, Option B — collision-scoped):
    By default, uses _chain_wire_key() to derive the wire param key from the YAML
    bind name (e.g. 'device_id' → 'id_device').  This is the simple, jcox-compatible
    scheme for the common case where no two children share the same bind name.

    When a collision is detected — i.e., the (ot_key, parent_req_name, bind_name)
    triple is in colliding_pairs — uses _chain_wire_key_for_request(bind_name,
    child_req_name) instead, producing a per-request-scoped key (e.g. id_device_stats_ap,
    id_device_detail_ap) that is unique across all children on this parent.

    The collision detection pre-scan in _render_requests fills colliding_pairs.
    Only colliding (parent, bind_name) pairs get the scoped key; everything else
    keeps the simpler scheme.  This is Option B from the bug report: jcox-like
    for the common case, scoped for the collision case.

    Returns: (chainingSettings_dict, own_chain_map, own_chain_param_ids)
      own_chain_map: {bind_name: wire_key} — stored on _RequestInfo._own_chain_map
      to rewrite ${chain.<name>} tokens in the child request's paths/params/body.
      Only OWN chain params are in own_chain_map.  Inherited ancestor chain tokens
      (not in own_chain_map) fall back to _chain_wire_key() in _rewrite_chain_tokens,
      matching whatever key the ancestor's chainingSettings declared.
      own_chain_param_ids: {bind_name: (param_id, wire_key)} — stored on
      _RequestInfo._own_chain_param_ids.  Used by _render_one_object to build
      objectBinding.matchExpression with originType=PARAMETER (Pattern V, Bug 4).

    See context/mp_chain_authoring.md §wire key mapping for the full scheme.
    See context/render_export_strip_audit_2026_05_14.md §Bug1 for evidence.
    See context/render_export_strip_audit_2026_05_14.md §Bug4 for Pattern V evidence.
    """
    chain_seed = f"{ak}:object:{ot_key}:chain:{child_req_name}"
    chain_id = _make_id(chain_seed)

    params = []
    own_chain_map: Dict[str, str] = {}
    own_chain_param_ids: Dict[str, Tuple[str, str]] = {}

    for i, b in enumerate(ms.bind):
        # origin_id: <parentRequestId>-<baseListId>-<attributeLabel>
        origin_id = f"{parent_req_info.id}-{parent_dml_id}-{b.from_attribute}"

        param_seed = f"{chain_seed}:param:{b.name}"
        param_id = _make_id(param_seed)

        # Choose wire key based on collision status.
        # Colliding: (ot_key, parent_req_name, bind_name) → use per-request-scoped key.
        # Non-colliding: use the simple _chain_wire_key scheme (jcox-compatible).
        if (ot_key, parent_req_name, b.name) in colliding_pairs:
            wire_key = _chain_wire_key_for_request(b.name, child_req_name)
        else:
            wire_key = _chain_wire_key(b.name)

        own_chain_map[b.name] = wire_key
        own_chain_param_ids[b.name] = (param_id, wire_key)

        # Label follows jcox convention: "ID_<everything-after-id_>".
        # e.g. id_device → ID_device, id_device_stats_ap → ID_device_stats_ap
        stem = wire_key[3:] if wire_key.startswith("id_") else wire_key
        label = f"ID_{stem}" if stem else "ID"

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
                    "label": b.from_attribute,
                    "regex": None,
                    "example": "",
                    "originId": origin_id,
                    "originType": "ATTRIBUTE",
                    "regexOutput": "",
                }
            ],
        }

        params.append({
            "id": param_id,
            "key": wire_key,
            "label": label,
            "usage": f"${{requestParameters.{wire_key}}}",
            "listId": parent_dml_id,
            "example": "",
            "attributeExpression": attr_expression,
        })

    chain_settings = {
        "id": chain_id,
        "parentRequestId": parent_req_info.id,
        "baseListId": parent_dml_id,
        "params": params,
    }
    return chain_settings, own_chain_map, own_chain_param_ids


def _icon_string_for_design(hint: Optional[str]) -> str:
    """Render the icon string written into design.json / template.json
    ``source.resources[*].internalObjectInfo.icon`` (and the template-level
    ``icon`` field).

    MPB's adapter runtime rejects icon strings that do not end in an image
    extension (``.svg`` or ``.png``).  The factory's loader stores a bare
    hint like ``access_point`` (extension stripped) for library lookup; on
    emission we re-attach ``.svg`` so the runtime accepts it.

    Empty or unknown hints fall back to ``default.svg``.

    Evidence: UniFi 1.0.0.10 shipped bare hints (``access_point``, ``switch``,
    etc.) and was rejected with "design file does not match the design file
    provided by the Management Pack Builder."  UniFi 1.0.0.8 had
    filename-style values (``wireless-access-point.svg``, ``default.png``)
    and installed successfully.  MPB-built reference pak puts Clarity-style
    names with extensions in the same field.  Fix introduced in 1.0.0.11.
    """
    if not hint:
        return "default.svg"
    if hint.endswith((".svg", ".png")):
        return hint  # already has extension (defensive — shouldn't normally happen)
    return f"{hint}.svg"


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

    # Scalar kind flag: both is_world and is_singleton use "base" DML context.
    # is_world  → adapter topology root, no identifiers, MPB rollups only.
    # is_singleton → one-per-adapter named entity, has identifiers and metrics.
    # Both share the same scalar-context rendering paths: listId="base",
    # full dotted path from response root as attribute label.
    # List kinds use per-row DML ids and relative field paths.
    is_scalar = ot.is_world or ot.is_singleton

    # Build map: metricSet.local_name → (MetricSetDef, RequestDef, dml_id)
    req_by_name: Dict[str, RequestDef] = {r.name: r for r in mp.requests}
    ms_context: Dict[str, Tuple["MetricSetDef", RequestDef, str]] = {}
    for ms in ot.metric_sets:
        req = req_by_name[ms.from_request]
        if is_scalar:
            # Scalar kinds always use the "base" DML (no list iteration).
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

    # Identify chain-parent metricSet local names on this object.
    # A metricSet is a chain-parent if another metricSet's chained_from
    # equals its local_name.
    chain_parent_names: set = {
        ms.chained_from
        for ms in ot.metric_sets
        if ms.chained_from is not None
    }

    # ---------------------------------------------------------------------------
    # Bug 4 / Pattern V (2026-05-15): PARAMETER-origin objectBinding for chained secondaries
    #
    # Pivot from Pattern B (Synology, ATTRIBUTE-origin) to Pattern V (vSAN policy,
    # PARAMETER-origin) for chained secondary metricSets on INTERNAL objects.
    #
    # Pattern V rules applied here:
    #   1. Primary metricSet: objectBinding = null (unchanged from Bug 2d).
    #   2. Each sibling secondary: objectBinding = ATTRIBUTE_TO_PROPERTY where:
    #      - matchExpression: PARAMETER → secondary's own chainingSettings.params[0].id
    #        (originType = PARAMETER, originId = chain_param_id, label = wire_key)
    #      - objectMatchExpression: METRIC → primary's identifier metric UUID (unchanged).
    #   3. Cross-type chain-root primaries (chained_from not in ms_context) and
    #      chain-parents, singletons, scalar kinds: objectBinding = null (unchanged).
    #   4. Single-metricSet objects: objectBinding = null (unchanged).
    #
    # Why Pattern V is universal over Pattern B (Synology):
    #   PARAMETER origin resolves at collection time to the value substituted into the URL.
    #   This works whether or not the API echoes the identifier back in the response body.
    #   ATTRIBUTE origin (Pattern B) requires the identifier in the response body.
    #   For endpoints like UniFi's /devices/{device}/statistics/latest that omit id from
    #   the response, ATTRIBUTE-origin resolves to nothing, causing silent collection failure.
    #
    # Ground truth: vrealize.it vSAN default storage policy MP — confirmed collecting
    # cleanly on devel with PARAMETER-origin objectBinding (2026-05-15).
    #
    # Bug 2d's secondary-DML synthesis (child_req_info.register_field) removed here
    # because Pattern V does not need the DML attribute.
    #
    # "Sibling secondary" definition: a metricSet whose chained_from refers to
    # another metricSet declared on THIS object type (i.e., chained_from is in
    # ms_context) AND primary is not True.
    #
    # Pre-loop: identify sibling secondaries for later case detection.
    # No anchor variable or linking-metric synthesis needed (Bug 2c logic removed).

    _sibling_secondaries: List["MetricSetDef"] = [
        ms for ms in ot.metric_sets
        if ms.chained_from is not None
        and not getattr(ms, "primary", False)
        and ms.chained_from in ms_context
    ]

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

            if is_scalar:
                # Scalar kind: base DML; full dotted path from response root.
                # e.g. response_path="data", field_path="cpu_clock_speed"
                #   → expr_label = "data.cpu_clock_speed"
                # Matches working export originId pattern: "<reqId>-base-data.<field>"
                rp = (req.response_path or "").strip()
                full_field_path = f"{rp}.{field_path}" if rp else field_path
                origin_id = req_info.register_field(full_field_path, "base")
                expr_label = full_field_path
            else:
                # List kind: field_path is relative to list item row.
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
                # wire_key is the label-derived key (MPB derivation algorithm).
                # It always matches what MPB's pak-build pipeline emits for the same
                # label, ensuring factory-built paks and MPB-pipeline paks produce
                # identical metric/property keys.  The YAML's key: field is an
                # authoring identifier only (used for in-YAML cross-references)
                # and is never written to the wire.
                # See context/mpb_explicit_key_investigation_2026_05_16.md.
                "key": m.wire_key,
                "unit": m.unit,
                "isKpi": m.kpi,
                "label": m.label,
                "usage": m.usage,
                "groups": [],
                "dataType": m.type,
                "expression": expression,
                "timeseries": None,
            })

        # objectBinding for this metricSet (Bug 2d fix — Synology pattern, 2026-05-15).
        #
        # Ground truth: /tmp/synology_inspect/design.json (shipped Synology DSM pak,
        # imports AND collects cleanly end-to-end).
        #
        # Case 0 — ARIA_OPS primary: cross-resource stitching binding (objectBindingType key).
        # Case 1 — Aria-native stitching (stitch_to declared in YAML): ATTRIBUTE_TO_PROPERTY.
        # Case 4 — Primary INTERNAL non-scalar: objectBinding = null (Synology pattern).
        #   The primary is always null; secondaries carry the binding.
        #   This is the opposite of Bug 2c's jcox-idiom (which had primary non-null).
        #   Single-metricSet objects also fall here (same null outcome).
        # Case 2d — Sibling secondary (Bug 2d fix): objectBinding = ATTRIBUTE_TO_PROPERTY.
        #   matchExpression: ATTRIBUTE → secondary's OWN DML synthesized bind attr.
        #   objectMatchExpression: METRIC → primary's identifier metric UUID.
        #   Both secondaries (first and subsequent) get this binding; none is "anchor".
        #   Cross-type chain-root consumers (chained_from not in ms_context) are NOT
        #   sibling secondaries and fall through to null (Case 3).
        # Case 3 — Chain-parents, singletons, scalar kinds, cross-type primaries:
        #   objectBinding = null.
        object_binding: Optional[Dict] = None
        ob_seed = f"{obj_seed}:metricSet:{ms.local_name}:objectBinding"

        if ot.type == "ARIA_OPS" and ms_def.primary and ms_def.stitch_match_field:
            # Case 0 — ARIA_OPS primary metricSet: cross-resource stitching binding.
            # Ground truth: context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json
            stitch_field = ms_def.stitch_match_field
            aria_ops = ot.aria_ops

            match_origin_id = req_info.register_field(stitch_field, dml_id)
            match_expr = _make_expression(
                label=stitch_field,
                origin_id=match_origin_id,
                origin_type="ATTRIBUTE",
                expr_seed=f"{ob_seed}::matchExpr",
            )

            bind_metric_uuid = _make_id(
                f"{obj_seed}:ariaOpsConf:metric:{aria_ops.bind_metric}"
            )
            bind_metric_label = _humanize_aria_label(aria_ops.bind_metric)
            obj_match_expr = _make_expression(
                label=bind_metric_label,
                origin_id=bind_metric_uuid,
                origin_type="ARIA_OPS_METRIC",
                expr_seed=f"{ob_seed}::objMatchExpr",
            )

            object_binding = {
                "objectBindingType": "ATTRIBUTE_TO_PROPERTY",
                "matchExpression": match_expr,
                "objectMatchExpression": obj_match_expr,
            }

        elif ms_def.stitch_to:
            # Case 1: Aria-native stitching binding (INTERNAL only).
            stitch_field = ms_def.stitch_match_field

            match_origin_id = req_info.register_field(stitch_field, dml_id)
            match_expr = _make_expression(
                label=stitch_field,
                origin_id=match_origin_id,
                origin_type="ATTRIBUTE",
                expr_seed=f"{ob_seed}::matchExpr",
            )

            obj_match_expr = _make_expression(
                label=stitch_field,
                origin_id=ms_def.stitch_to,
                origin_type="ARIA_OPS_METRIC",
                expr_seed=f"{ob_seed}::objMatchExpr",
            )

            object_binding = {
                "type": "ATTRIBUTE_TO_PROPERTY",
                "matchExpression": match_expr,
                "objectMatchExpression": obj_match_expr,
            }

        elif (
            ms.chained_from is not None
            and not getattr(ms_def, "primary", False)
            and ms.chained_from in ms_context
        ):
            # Case 2d — Sibling secondary (Bug 4 / Pattern V, 2026-05-15).
            #
            # Pivot from Pattern B (Synology, ATTRIBUTE-origin matchExpression) to
            # Pattern V (vSAN policy, PARAMETER-origin matchExpression).
            #
            # Pattern V (canonical for INTERNAL chained secondaries):
            #   matchExpression: points at the secondary's OWN chainingSettings.params[0].id.
            #     originType = PARAMETER
            #     originId   = chain_param_id  (the UUID of chainingSettings.params[N])
            #     label      = chain_param_key (the wire key, e.g. "id_device_stats_ap")
            #   objectMatchExpression: UNCHANGED — points at primary's identifier metric UUID.
            #     originType = METRIC
            #
            # Ground truth: vSAN default storage policy MP
            #   (references/vrealize_it_vsan_default_policy/vSAN default storage policy.json)
            #   Request "Get Datastore default policy":
            #     chainingSettings.params[0].id = "w3ovEMMMaQF6VvGf7cqRha", key = "datastore"
            #   Object objectBinding.matchExpression.expressionParts[0]:
            #     originType = "PARAMETER", originId = "w3ovEMMMaQF6VvGf7cqRha", label = "datastore"
            #   Confirmed collecting cleanly on devel (3 resources, 2026-05-15).
            #
            # Why Pattern V is universal:
            #   The PARAMETER origin resolves at collection time to the value substituted into
            #   the URL — which IS the per-device identifier.  This works whether or not the
            #   API echoes the identifier back in the response body.  The Synology ATTRIBUTE
            #   pattern requires the identifier to appear in the response body; for endpoints
            #   like UniFi's /sites/{site}/devices/{device}/statistics/latest that do not echo
            #   back id, ATTRIBUTE-origin resolves to nothing and collection fails silently.
            #
            # Bug 2d's secondary-DML synthesis (child_req_info.register_field) is removed
            # because Pattern V does not need a DML attribute for the matchExpression.
            # The parent-DML synthesis is retained (needed for chainingSettings.params[].
            # attributeExpression to reference the correct parent-row attribute).
            _b0 = ms.bind[0]

            # Look up this secondary's own chain param id and wire key
            # from req_info._own_chain_param_ids (populated by _build_chaining_settings).
            _chain_param_entry = req_info._own_chain_param_ids.get(_b0.name)

            # Look up primary's identifier metric UUID from metric_map
            _ident_key = ot.identifiers[0].key if ot.identifiers else None
            _ident_metric_id = metric_map.get(_ident_key) if _ident_key else None
            _ident_metric_label = next(
                (m.label for m in ot.metrics if m.key == _ident_key), _ident_key
            ) if _ident_key else None

            if _ident_metric_id is not None and _chain_param_entry is not None:
                _cp_id, _cp_wire_key = _chain_param_entry
                match_expr_v = _make_expression(
                    label=_cp_wire_key,
                    origin_id=_cp_id,
                    origin_type="PARAMETER",
                    expr_seed=f"{ob_seed}::matchExpr",
                )
                obj_match_expr_v = _make_expression(
                    label=_ident_metric_label or _ident_key,
                    origin_id=_ident_metric_id,
                    origin_type="METRIC",
                    expr_seed=f"{ob_seed}::objMatchExpr",
                )
                object_binding = {
                    "type": "ATTRIBUTE_TO_PROPERTY",
                    "matchExpression": match_expr_v,
                    "objectMatchExpression": obj_match_expr_v,
                }
                logger.info(
                    "Object '%s' secondary metricSet '%s': objectBinding "
                    "matchExpr.originId=%s (PARAMETER, chain param) "
                    "objMatchExpr.originId=%s (METRIC, primary ident) [Pattern V].",
                    ot.name, ms.local_name, _cp_id, _ident_metric_id,
                )
            elif _chain_param_entry is None:
                logger.warning(
                    "Object '%s' secondary metricSet '%s': bind[0].name=%r not found "
                    "in req_info._own_chain_param_ids. Emitting null objectBinding.",
                    ot.name, ms.local_name, _b0.name,
                )
            else:
                logger.warning(
                    "Object '%s' secondary metricSet '%s': no identifier metric "
                    "in metric_map (key=%r). Emitting null objectBinding.",
                    ot.name, ms.local_name, _ident_key,
                )

        # Case 4: primary INTERNAL non-scalar → objectBinding=null (Synology pattern).
        # Case 3: chain-parents, singletons, scalar kinds, cross-type primaries → null.
        # (object_binding stays None for all these cases)

        # Chain-anchor stub injection (task #20 revert, 2026-05-18).
        #
        # Background: The Dell pattern uses "singleton anchor + same-request
        # list_path fan-out."  A SINGLE request (e.g. thermal) returns BOTH the
        # parent identity AND an inline list of children (Fans array).  For MPB UI
        # to know that thermal "belongs to" the Server (and therefore Fan objects
        # inside thermal's response are the Server's children), the Server object
        # MUST have a `from_request: thermal` binding in its metricSets.  That
        # binding is the only signal MPB has for ownership.  Without it, MPB treats
        # thermal as a free-floating root request with no owner, no chaining, and
        # no relationship inference — the Relationships tab is empty.
        #
        # This differs from UniFi/phpIPAM, which use chained two-request flow
        # (request A returns IDs, request B chains via chainingSettings.parentRequestId).
        # In that pattern, the parent's binding is not needed because chaining is
        # explicit on the child request.  The Dell pattern has no second request —
        # fan-out comes from list_path on the response in-place.
        #
        # MPB UI also requires every metricSet binding to carry at least one metric
        # ("Request <name> did not return attributes required to make metrics on
        # this object").  Authors declare `chain_anchor_stub: <field>` on chain-
        # anchor metricSets to provide a benign PROPERTY metric satisfying this
        # constraint while keeping the binding present for chaining inference.
        #
        # If chain_anchor_stub is set and wire_metrics is still empty after the
        # normal metric loop, inject a synthetic PROPERTY metric now.
        if not wire_metrics and ms_def.chain_anchor_stub:
            stub_field = ms_def.chain_anchor_stub
            stub_label = f"Stub Name ({ms.local_name})"
            stub_wire_key = derive_key_from_label(stub_label)
            stub_m_id = _make_id(f"{obj_seed}:metricSet:{ms.local_name}:stub")
            stub_expr_seed = f"{obj_seed}:metricSet:{ms.local_name}:stub:expr"
            if is_scalar:
                rp = (req.response_path or "").strip()
                stub_full_field = f"{rp}.{stub_field}" if rp else stub_field
                stub_origin_id = req_info.register_field(stub_full_field, "base")
                stub_expr_label = stub_full_field
            else:
                stub_origin_id = req_info.register_field(stub_field, dml_id)
                stub_expr_label = stub_field
            stub_expression = _make_expression(
                label=stub_expr_label,
                origin_id=stub_origin_id,
                origin_type="ATTRIBUTE",
                expr_seed=stub_expr_seed,
            )
            wire_metrics.append({
                "id": stub_m_id,
                "key": stub_wire_key,
                "unit": "",
                "isKpi": False,
                "label": stub_label,
                "usage": "PROPERTY",
                "groups": [],
                "dataType": "STRING",
                "expression": stub_expression,
                "timeseries": None,
            })
            logger.debug(
                "Object '%s' metricSet '%s': injected chain-anchor stub metric "
                "from chain_anchor_stub=%r (field=%r, wire_key=%r).",
                ot.name, ms.local_name, ms_def.chain_anchor_stub, stub_expr_label, stub_wire_key,
            )

        # Emit the metricSet unconditionally (reverted task #20 suppression).
        # metricSets with no metrics AND no chain_anchor_stub are emitted as-is;
        # MPB's design.json import accepts empty metrics arrays.  Only template.json
        # (pak runtime) enforces the non-empty constraint, and the stub mechanism
        # above guarantees non-empty for all chain-anchor cases.

        wire_metric_sets.append({
            "id": ms_id,
            "listId": dml_id,
            "requestId": req_info.id,
            "metrics": wire_metrics,
            "objectBinding": object_binding,
        })

    # Build nameMetricExpression
    name_expr = _render_name_expression(ot, metric_map, obj_seed)

    # Log world-object identity tier for debugging (Tier 3.3 axis 7).
    # identity: block is is_world-only; is_singleton does not declare identity.
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
    #
    # isListObject:
    #   - is_world     → false (adapter-instance root, no list iteration)
    #   - is_singleton → false (one-per-adapter named entity, no list iteration)
    #   - list kind    → true  (one MPB object instance per response row)
    #   - ARIA_OPS     → always true (list objects by definition)
    #
    # ARIA_OPS vs INTERNAL wire differences:
    #   - ARIA_OPS:  ariaOpsConf populated, internalObjectInfo absent
    #   - INTERNAL:  ariaOpsConf null, internalObjectInfo populated
    if ot.type == "ARIA_OPS":
        return {
            "id": obj_id,
            "type": ot.type,
            "designId": None,
            "isListObject": True,
            "metricSets": wire_metric_sets,
            "ariaOpsConf": _render_aria_ops_conf(ot.aria_ops, obj_seed),
        }

    return {
        "id": obj_id,
        "type": ot.type,
        "designId": None,
        "metricSets": wire_metric_sets,
        "ariaOpsConf": None,
        "isListObject": not is_scalar,
        "internalObjectInfo": {
            "id": internal_id,
            "icon": _icon_string_for_design(ot.icon),
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
                "using %s strategy.",
                rel.parent, rel.child, relationship_strategy,
            )
            wire_rels = _render_trivial_relationships(
                rel, mp, object_id_map, metric_id_map, ak,
                strategy=relationship_strategy,
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
    synthetic constant-property metric IDs (originType=METRIC).  The corresponding
    synthetic metrics are injected into each object's first metricSet by
    _inject_shared_constant_metrics(), which is called from render_mp_design_json()
    after relationships are built.

    The metric seed formula used here MUST stay in sync with
    _inject_shared_constant_metrics() so that the relationship originId and the
    injected metric id are identical:
        child:  _make_id("{ak}:object:{rel.child}:metric:__adapter_instance_const")
        parent: _make_id("{ak}:object:{rel.parent}:metric:__adapter_instance_const")

    ASSUMPTION: MPB validates that child/parent expression originIds resolve to
    actual metric ids on the respective objects.  Without the injection, MPB
    would fail with "Child property used in relationship does not exist".
    """
    name_suffix = f" ({suffix})" if suffix else ""
    rel_seed = f"{ak}:rel:{rel.parent}:{rel.child}:shared_constant"
    rel_id = _make_id(rel_seed)

    # Synthetic metric IDs for both sides — MUST match _inject_shared_constant_metrics().
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
    }


def _inject_shared_constant_metrics(
    mp: "ManagementPackDef",
    wire_objects: List[Dict],
    object_id_map: Dict[str, str],
    ak: str,
) -> None:
    """Inject synthetic __adapter_instance_const PROPERTY metrics into wire objects.

    Called from render_mp_design_json() when relationship_strategy is
    "shared_constant_property".  For every object key that appears as parent or
    child in an adapter_instance-scope relationship, this function:

    1. Derives the deterministic metric id using the same seed as
       _trivial_shared_constant():
           _make_id("{ak}:object:{obj_key}:metric:__adapter_instance_const")
       This ensures the relationship's originId and the metric's id are identical.

    2. Builds a synthetic PROPERTY metric with:
         - id:       the derived metric id (matches relationship originId)
         - key:      "__adapter_instance_const"   (derive_key_from_label of label)
         - label:    "__adapter_instance_const"
         - usage:    "PROPERTY"
         - dataType: "STRING"
         - expression: literal constant "ADAPTER_INSTANCE" (same on every object
                        so MPB's join predicate always matches)

    3. Prepends the metric to the first metricSet.metrics list of the matching
       wire object, unless that metric id is already present (idempotent).

    Modifies wire_objects in-place.  No return value.
    """
    # Collect unique object keys from adapter_instance-scope relationships.
    affected_keys: set = set()
    for rel in mp.relationships:
        if rel.scope == "adapter_instance":
            affected_keys.add(rel.parent)
            affected_keys.add(rel.child)

    if not affected_keys:
        return

    # Build reverse map: object_id → wire_object dict
    id_to_wire: Dict[str, Dict] = {obj["id"]: obj for obj in wire_objects}

    for obj_key in sorted(affected_keys):  # sorted for deterministic log order
        obj_id = object_id_map.get(obj_key)
        if not obj_id:
            logger.warning(
                "_inject_shared_constant_metrics: object key %r not in object_id_map; "
                "skipping.",
                obj_key,
            )
            continue

        wire_obj = id_to_wire.get(obj_id)
        if not wire_obj:
            logger.warning(
                "_inject_shared_constant_metrics: no wire object for key %r (id=%s); "
                "skipping.",
                obj_key, obj_id,
            )
            continue

        # Derive metric id — MUST match _trivial_shared_constant().
        metric_seed = f"{ak}:object:{obj_key}:metric:__adapter_instance_const"
        metric_id = _make_id(metric_seed)

        # Locate first metricSet (required — objects always have at least one).
        metric_sets = wire_obj.get("metricSets", [])
        if not metric_sets:
            logger.warning(
                "_inject_shared_constant_metrics: object %r has no metricSets; "
                "cannot inject synthetic metric.",
                obj_key,
            )
            continue

        target_ms = metric_sets[0]
        existing_metrics = target_ms.get("metrics", [])

        # Idempotency: skip if already injected.
        if any(m.get("id") == metric_id for m in existing_metrics):
            logger.debug(
                "_inject_shared_constant_metrics: object %r already has "
                "__adapter_instance_const metric; skipping.",
                obj_key,
            )
            continue

        # Build the synthetic PROPERTY metric.
        # Expression is a literal constant — same value on every object so the
        # join predicate always evaluates equal.
        expr_id = _make_id(f"{metric_seed}:expr")
        synthetic_expression = {
            "id": expr_id,
            "expressionText": "ADAPTER_INSTANCE",
            "expressionParts": [],
        }

        synthetic_metric = {
            "id": metric_id,
            "key": "__adapter_instance_const",
            "unit": "",
            "isKpi": False,
            "label": "__adapter_instance_const",
            "usage": "PROPERTY",
            "groups": [],
            "dataType": "STRING",
            "expression": synthetic_expression,
            "timeseries": None,
        }

        # Prepend so it appears first (visibility, not semantically required).
        target_ms["metrics"] = [synthetic_metric] + existing_metrics

        logger.info(
            "_inject_shared_constant_metrics: injected __adapter_instance_const "
            "metric (id=%s) into object %r metricSet[0].",
            metric_id, obj_key,
        )


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
          "externalResources": [ ... ],   <- ARIA_OPS stitching objects (populated 2026-05-15)
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

    # --- shared_constant_property: inject synthetic metrics into wire_objects ---
    # Must run AFTER _render_relationships (so we know which objects are affected)
    # and BEFORE _render_source (which packages wire_objects into source.resources).
    # Only active for the shared_constant_property strategy; no-op for all others.
    if relationship_strategy in ("shared_constant_property", "test_all"):
        _inject_shared_constant_metrics(mp, wire_objects, object_id_map, ak)

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
        "(%d field_match, %d adapter_instance scope), "
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
        f"({join_count} field_match, "
        f"{trivial_count} adapter_instance scope), "
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
