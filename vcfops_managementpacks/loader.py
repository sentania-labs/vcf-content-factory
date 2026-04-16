"""Load and validate management pack YAML definitions.

Management packs are identified by name.  Each YAML file in managementpacks/
defines one MP.  There is no UUID — the adapter kind key is derived from the
name if not supplied explicitly.

YAML schema (condensed):

    name: "Synology DSM"
    description: "Synology DiskStation Manager monitoring"
    version: "1.0.0"
    build_number: 1
    author: "sentania"
    adapter_kind: "mpb_synology_dsm"    # auto-derived if omitted

    source:
      port: 5001
      ssl: NO_VERIFY
      base_path: "webapi"              # no leading slash; MPB baseApiPath
      timeout: 30
      max_retries: 2
      max_concurrent: 15
      auth:
        # --- Option A: cookie-based session (CUSTOM) ---
        type: CUSTOM
        session:
          login_request:
            method: GET
            path: "auth.cgi"
            params:
              - {key: api,     value: "SYNO.API.Auth"}
              - {key: version, value: "3"}
              - {key: method,  value: "login"}
              - {key: account, value: "${authentication.credentials.username}"}
              - {key: passwd,  value: "${authentication.credentials.passwd}"}
              - {key: session, value: "FileStation"}
              - {key: format,  value: "cookie"}
            headers:
              - {key: Content-Type, type: REQUIRED, value: "application/json"}
          logout_request:
            method: DELETE
            path: "auth.cgi"
            params:
              - {key: method,  value: "logout"}
              - {key: version, value: "3"}
              - {key: api,     value: "SYNO.API.Auth"}
          cookie_binding: "set_cookie"   # session variable name; runtime ref:
                                         # ${authentication.session.set_cookie}
          header_injection:
            - {key: Cookie, value: "${authentication.session.set_cookie}"}
        # --- Option B: legacy SESSION (body-token extraction) ---
        type: SESSION
        session: { ... }               # required when type=SESSION
        # --- Option C/D: simple credential types ---
        type: BASIC | TOKEN | NONE
      test_request:
        path: "entry.cgi"
        method: GET
        params:
          - {key: api,     value: "SYNO.DSM.Info"}
          - {key: version, value: "2"}
          - {key: method,  value: "getinfo"}
      config_fields: []

    object_types:
      - name: "Synology Diskstation"
        key: "synology_diskstation"    # auto-derived if omitted
        type: INTERNAL                 # INTERNAL or ARIA_OPS
        icon: "server.svg"
        is_world: true
        identifiers: [serial]
        name_expression: "hostname"    # single metric key only (no templates)
        requests:
          - name: "system_info"
            method: GET
            path: "entry.cgi"
            params:
              - {key: api, value: "SYNO.DSM.Info"}
            response_path: "data"
        metrics:
          - key: serial
            label: "Serial Number"
            usage: PROPERTY
            type: STRING
            source: "request:system_info.serial"
        # NOTE: 'events' is NOT supported in MP YAML v1.
        # Author threshold-based alerts as factory symptoms + alerts instead.

    relationships:
      - parent: synology_diskstation
        child: storage_pool
        child_expression: pool_path    # metric key on child whose value is matched
        parent_expression: id          # metric key on parent whose value is matched
        # child_expression / parent_expression are optional at schema level.
        # When omitted the renderer will flag the relationship as incomplete.

    content:
      dashboards: []
      views: []
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
import yaml.constructor
import yaml.resolver


# ---------------------------------------------------------------------------
# Strict YAML loader (rejects duplicate keys)
# ---------------------------------------------------------------------------

def _strict_load(stream):
    """yaml.safe_load replacement that raises on duplicate mapping keys."""
    class _StrictKeyLoader(yaml.SafeLoader):
        pass

    def _no_duplicates(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None,
                    f"duplicate key '{key}' found at {key_node.start_mark}",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    _StrictKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _no_duplicates,
    )
    return yaml.load(stream, Loader=_StrictKeyLoader)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_METRIC_USAGE = {"PROPERTY", "METRIC"}
VALID_METRIC_TYPE = {"STRING", "NUMBER"}
VALID_OBJECT_TYPE = {"INTERNAL", "ARIA_OPS"}
VALID_AUTH_TYPE = {"BASIC", "TOKEN", "SESSION", "NONE", "CUSTOM"}
VALID_SSL = {"NO_VERIFY", "VERIFY", "NO_SSL"}
VALID_HTTP_METHOD = {"GET", "POST", "PUT", "DELETE", "PATCH"}

# MPB event severity — VCF Ops vocabulary (Rubrik §6c + cartographer guidance)
VALID_EVENT_SEVERITY = {"INFO", "WARNING", "IMMEDIATE", "CRITICAL", "AUTOMATIC"}

# Match-rule operators observed in Rubrik reference MP and cartographer spec
VALID_MATCH_OPERATOR = {
    "EQUALS", "NOT_EQUALS",
    "CONTAINS", "NOT_CONTAINS",
    "MATCHES_REGEX", "NOT_MATCHES_REGEX",
    "STARTS_WITH", "ENDS_WITH",
    "EXISTS", "NOT_EXISTS",
}

# Dedup strategy vocabulary
VALID_DEDUP_STRATEGY = {"TUPLE_HASH", "FIELD_ID", "NONE"}

# Adapter kind must begin with mpb_
_ADAPTER_KIND_RE = re.compile(r"^mpb_[a-z0-9_]+$")

# A single-metric name_expression: either a bare identifier or ${identifier}.
# Multi-metric templates like "${model} (${hostname})" are rejected.
_SINGLE_METRIC_RE = re.compile(r"^\$\{([a-zA-Z0-9_]+)\}$|^([a-zA-Z0-9_]+)$")

# Detect template strings that contain more than one ${...} or literal text
# mixed with ${...}.  If a value matches _TEMPLATE_RE it is a composite
# template and must be rejected.
_TEMPLATE_RE = re.compile(r"\$\{[^}]+\}")


# Derive adapter_kind from MP name: lowercase, replace non-alphanum with _
def _derive_adapter_kind(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return f"mpb_{slug}"

# Derive object type key from object name
def _derive_object_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")

# Parse "request:<request_name>.<field_path>" source references
_SOURCE_RE = re.compile(r"^request:([a-zA-Z0-9_]+)\.(.+)$")


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------

class ManagementPackValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MetricDef:
    key: str
    label: str
    usage: str          # PROPERTY or METRIC
    type: str           # STRING or NUMBER
    source: str         # "request:<name>.<field>"
    unit: str = ""
    kpi: bool = False


@dataclass
class RequestDef:
    name: str
    method: str
    path: Optional[str]
    params: Any = field(default_factory=list)   # list[{key,value}] or dict
    body: Optional[str] = None
    response_path: Optional[str] = None


@dataclass
class SessionDef:
    """Parsed session settings for CUSTOM auth type."""
    login_request: Dict[str, Any]
    logout_request: Optional[Dict[str, Any]]
    cookie_binding: str                    # session variable name (e.g. "set_cookie")
    header_injection: List[Dict[str, str]] # [{key, value}, ...]


@dataclass
class ObjectTypeDef:
    name: str
    key: str
    type: str               # INTERNAL or ARIA_OPS
    identifiers: List[str]
    requests: List[RequestDef]
    metrics: List[MetricDef]
    icon: str = "server.svg"
    is_world: bool = False
    name_expression: str = ""


@dataclass
class RelationshipDef:
    parent: str
    child: str
    child_expression: Optional[str] = None   # metric key on child for value join
    parent_expression: Optional[str] = None  # metric key on parent for value join


@dataclass
class MatchRuleDef:
    field: str
    operator: str   # EQUALS, CONTAINS, MATCHES_REGEX, etc. (VALID_MATCH_OPERATOR)
    value: str


@dataclass
class ObjectBindingDef:
    object_type: str                        # references an ObjectTypeDef.key
    match_field: Optional[str] = None       # response field whose value finds the target object
    match_normalizer: Optional[str] = None  # lightweight transform (e.g. strip_leading_slash)


@dataclass
class CollectionStrategyDef:
    interval_seconds: int
    dedup_strategy: str                     # TUPLE_HASH, FIELD_ID, NONE
    dedup_fields: List[str] = field(default_factory=list)  # for TUPLE_HASH


@dataclass
class MPBEventDef:
    name: str
    severity: str                                       # VALID_EVENT_SEVERITY
    source_request: str                                 # request name in the MP
    response_path: str                                  # JSON path to event list (e.g. data.items)
    match_rules: List[MatchRuleDef] = field(default_factory=list)
    object_binding: Optional[ObjectBindingDef] = None
    collection_strategy: Optional[CollectionStrategyDef] = None
    message_template: Optional[str] = None             # may use ${field} refs
    description: Optional[str] = None


@dataclass
class AuthDef:
    type: str                        # BASIC, TOKEN, SESSION, NONE, CUSTOM
    session: Optional[Dict[str, Any]] = None     # raw dict for SESSION type
    custom_session: Optional[SessionDef] = None  # parsed for CUSTOM type


@dataclass
class ConfigFieldDef:
    key: str
    label: str
    type: str           # STRING, NUMBER, SINGLE_SELECTION
    default: str = ""
    description: str = ""


@dataclass
class SourceDef:
    port: int
    ssl: str
    base_path: str
    timeout: int
    max_retries: int
    max_concurrent: int
    auth: Optional[AuthDef] = None
    test_request: Optional[Dict[str, Any]] = None
    config_fields: List[ConfigFieldDef] = field(default_factory=list)


@dataclass
class ManagementPackDef:
    name: str
    version: str
    adapter_kind: str
    description: str = ""
    build_number: int = 1
    author: str = ""
    source: Optional[SourceDef] = None
    object_types: List[ObjectTypeDef] = field(default_factory=list)
    relationships: List[RelationshipDef] = field(default_factory=list)
    mpb_events: List[MPBEventDef] = field(default_factory=list)
    content: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[Path] = None

    def validate(self) -> None:
        _validate_mp(self)


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

def _validate_mp(mp: ManagementPackDef) -> None:
    tag = mp.name or "(unnamed)"

    # Required top-level fields
    if not mp.name or not mp.name.strip():
        raise ManagementPackValidationError("name is required")
    if not mp.version or not mp.version.strip():
        raise ManagementPackValidationError(f"{tag}: version is required")

    # adapter_kind pattern
    if not _ADAPTER_KIND_RE.match(mp.adapter_kind):
        raise ManagementPackValidationError(
            f"{tag}: adapter_kind must match mpb_<lowercase_underscored>; "
            f"got {mp.adapter_kind!r}"
        )

    # Source validation (optional section, but if present, fields must be valid)
    if mp.source is not None:
        _validate_source(tag, mp.source)

    # Object types
    object_keys: Dict[str, set] = {}  # key -> set of metric keys
    world_count = 0
    request_names_by_object: Dict[str, set] = {}

    for ot in mp.object_types:
        ot_tag = f"{tag}: object_type '{ot.name}'"

        if not ot.name or not ot.name.strip():
            raise ManagementPackValidationError(f"{tag}: object type name is required")
        if ot.type not in VALID_OBJECT_TYPE:
            raise ManagementPackValidationError(
                f"{ot_tag}: type must be one of {sorted(VALID_OBJECT_TYPE)}; "
                f"got {ot.type!r}"
            )
        if not ot.identifiers:
            raise ManagementPackValidationError(
                f"{ot_tag}: at least one identifier is required"
            )
        if not ot.requests:
            raise ManagementPackValidationError(
                f"{ot_tag}: at least one request is required"
            )
        if not ot.metrics:
            raise ManagementPackValidationError(
                f"{ot_tag}: at least one metric or property is required"
            )

        if ot.is_world:
            world_count += 1

        # Validate requests
        req_names = set()
        for req in ot.requests:
            _validate_request(ot_tag, req)
            req_names.add(req.name)
        request_names_by_object[ot.key] = req_names

        # Collect metric keys for this object type
        metric_keys = set()
        for m in ot.metrics:
            _validate_metric(ot_tag, m, req_names)
            metric_keys.add(m.key)
        object_keys[ot.key] = metric_keys

        # Validate name_expression
        if ot.name_expression:
            _validate_name_expression(ot_tag, ot.name_expression)

    # Exactly one world object
    if mp.object_types and world_count != 1:
        raise ManagementPackValidationError(
            f"{tag}: exactly one object_type must have is_world: true; "
            f"found {world_count}"
        )

    # Relationships reference valid object type keys
    for rel in mp.relationships:
        if rel.parent not in object_keys:
            raise ManagementPackValidationError(
                f"{tag}: relationship parent '{rel.parent}' is not a known "
                f"object type key (known: {sorted(object_keys)})"
            )
        if rel.child not in object_keys:
            raise ManagementPackValidationError(
                f"{tag}: relationship child '{rel.child}' is not a known "
                f"object type key (known: {sorted(object_keys)})"
            )
        if rel.parent == rel.child:
            raise ManagementPackValidationError(
                f"{tag}: relationship cannot be self-referential ('{rel.parent}')"
            )

    # Collect all request names across all object types for MPB event cross-reference
    all_request_names: set = set()
    for ot in mp.object_types:
        for req in ot.requests:
            all_request_names.add(req.name)

    # MPB events
    for ev in mp.mpb_events:
        _validate_mpb_event(ev, tag, all_request_names, set(object_keys.keys()))


def _validate_name_expression(tag: str, expr: str) -> None:
    """Reject multi-metric templates; only bare metric key or ${metric_key} allowed."""
    # Count how many ${...} groups are present
    refs = _TEMPLATE_RE.findall(expr)
    if len(refs) > 1:
        raise ManagementPackValidationError(
            f"{tag}: name_expression contains multiple metric references "
            f"({refs!r}). Template name expressions with multiple metrics / "
            f"literals are not supported in v1; use a single metric key "
            f"(e.g. 'hostname' or '${{hostname}}')."
        )
    if len(refs) == 1:
        # Has exactly one ${...} — check there is no surrounding literal text
        stripped = expr.strip()
        if not stripped.startswith("${") or not stripped.endswith("}"):
            raise ManagementPackValidationError(
                f"{tag}: name_expression mixes a metric reference with literal "
                f"text ({expr!r}). Template name expressions with multiple "
                f"metrics / literals are not supported in v1; use a single "
                f"metric key (e.g. 'hostname' or '${{hostname}}')."
            )
    # If zero ${...} refs, it must be a bare identifier
    if len(refs) == 0:
        if not re.match(r"^[a-zA-Z0-9_]+$", expr.strip()):
            raise ManagementPackValidationError(
                f"{tag}: name_expression {expr!r} is not a valid metric key. "
                f"Use a bare metric key (e.g. 'hostname') or a single "
                f"reference (e.g. '${{hostname}}')."
            )


def _validate_mpb_event(
    ev: MPBEventDef,
    tag: str,
    all_request_names: set,
    object_type_keys: set,
) -> None:
    etag = f"{tag}: mpb_event '{ev.name}'"

    if not ev.name or not ev.name.strip():
        raise ManagementPackValidationError(f"{tag}: mpb_event name is required")
    if not ev.severity or ev.severity not in VALID_EVENT_SEVERITY:
        raise ManagementPackValidationError(
            f"{etag}: severity must be one of {sorted(VALID_EVENT_SEVERITY)}; "
            f"got {ev.severity!r}"
        )
    if not ev.source_request or not ev.source_request.strip():
        raise ManagementPackValidationError(
            f"{etag}: source_request is required"
        )
    if ev.source_request not in all_request_names:
        raise ManagementPackValidationError(
            f"{etag}: source_request '{ev.source_request}' does not match any "
            f"request defined on the object types "
            f"(known requests: {sorted(all_request_names)})"
        )
    if not ev.response_path or not ev.response_path.strip():
        raise ManagementPackValidationError(
            f"{etag}: response_path is required"
        )
    for i, rule in enumerate(ev.match_rules):
        if not rule.field or not rule.field.strip():
            raise ManagementPackValidationError(
                f"{etag}: match_rules[{i}] field is required"
            )
        if rule.operator not in VALID_MATCH_OPERATOR:
            raise ManagementPackValidationError(
                f"{etag}: match_rules[{i}] operator must be one of "
                f"{sorted(VALID_MATCH_OPERATOR)}; got {rule.operator!r}"
            )
        if rule.value is None:
            raise ManagementPackValidationError(
                f"{etag}: match_rules[{i}] value is required"
            )
    if ev.object_binding is not None:
        ob = ev.object_binding
        if not ob.object_type or not ob.object_type.strip():
            raise ManagementPackValidationError(
                f"{etag}: object_binding.object_type is required"
            )
        if ob.object_type not in object_type_keys:
            raise ManagementPackValidationError(
                f"{etag}: object_binding.object_type '{ob.object_type}' does not "
                f"match any declared object type key "
                f"(known: {sorted(object_type_keys)})"
            )
    if ev.collection_strategy is not None:
        cs = ev.collection_strategy
        if cs.interval_seconds < 1:
            raise ManagementPackValidationError(
                f"{etag}: collection_strategy.interval_seconds must be >= 1; "
                f"got {cs.interval_seconds}"
            )
        if cs.dedup_strategy not in VALID_DEDUP_STRATEGY:
            raise ManagementPackValidationError(
                f"{etag}: collection_strategy.dedup_strategy must be one of "
                f"{sorted(VALID_DEDUP_STRATEGY)}; got {cs.dedup_strategy!r}"
            )
        if cs.dedup_strategy == "TUPLE_HASH" and not cs.dedup_fields:
            raise ManagementPackValidationError(
                f"{etag}: collection_strategy.dedup_fields is required when "
                f"dedup_strategy is TUPLE_HASH"
            )


def _validate_source(tag: str, src: SourceDef) -> None:
    stag = f"{tag}: source"
    if src.port < 1 or src.port > 65535:
        raise ManagementPackValidationError(
            f"{stag}: port must be 1-65535; got {src.port}"
        )
    if src.ssl not in VALID_SSL:
        raise ManagementPackValidationError(
            f"{stag}: ssl must be one of {sorted(VALID_SSL)}; got {src.ssl!r}"
        )
    if src.timeout < 1:
        raise ManagementPackValidationError(
            f"{stag}: timeout must be >= 1; got {src.timeout}"
        )
    if src.max_retries < 0:
        raise ManagementPackValidationError(
            f"{stag}: max_retries must be >= 0; got {src.max_retries}"
        )
    if src.max_concurrent < 1:
        raise ManagementPackValidationError(
            f"{stag}: max_concurrent must be >= 1; got {src.max_concurrent}"
        )
    if src.auth is not None:
        _validate_auth(stag, src.auth)
    for cf in src.config_fields:
        if not cf.key or not cf.key.strip():
            raise ManagementPackValidationError(
                f"{stag}: config_field key is required"
            )
        if not cf.label or not cf.label.strip():
            raise ManagementPackValidationError(
                f"{stag}: config_field '{cf.key}' label is required"
            )


def _validate_auth(tag: str, auth: AuthDef) -> None:
    atag = f"{tag}: auth"
    if auth.type not in VALID_AUTH_TYPE:
        raise ManagementPackValidationError(
            f"{atag}: type must be one of {sorted(VALID_AUTH_TYPE)}; "
            f"got {auth.type!r}"
        )
    if auth.type == "SESSION" and not auth.session:
        raise ManagementPackValidationError(
            f"{atag}: session settings are required when auth type is SESSION"
        )
    if auth.type == "CUSTOM":
        if not auth.custom_session:
            raise ManagementPackValidationError(
                f"{atag}: session block is required when auth type is CUSTOM"
            )
        _validate_custom_session(atag, auth.custom_session)


def _validate_custom_session(tag: str, cs: SessionDef) -> None:
    stag = f"{tag}: session"
    # login_request is required
    if not cs.login_request:
        raise ManagementPackValidationError(
            f"{stag}: login_request is required for CUSTOM auth"
        )
    login_method = str(
        cs.login_request.get("method", "GET") or "GET"
    ).strip().upper()
    if login_method not in VALID_HTTP_METHOD:
        raise ManagementPackValidationError(
            f"{stag}: login_request.method must be one of "
            f"{sorted(VALID_HTTP_METHOD)}; got {login_method!r}"
        )
    # cookie_binding must be a non-empty identifier
    if not cs.cookie_binding or not cs.cookie_binding.strip():
        raise ManagementPackValidationError(
            f"{stag}: cookie_binding is required for CUSTOM auth "
            f"(e.g. 'set_cookie')"
        )
    # header_injection must be a non-empty list of {key, value} dicts
    if not cs.header_injection:
        raise ManagementPackValidationError(
            f"{stag}: header_injection must contain at least one entry "
            f"for CUSTOM auth"
        )
    for i, h in enumerate(cs.header_injection):
        if not isinstance(h, dict):
            raise ManagementPackValidationError(
                f"{stag}: header_injection[{i}] must be a mapping"
            )
        if not h.get("key"):
            raise ManagementPackValidationError(
                f"{stag}: header_injection[{i}] is missing 'key'"
            )
        if "value" not in h:
            raise ManagementPackValidationError(
                f"{stag}: header_injection[{i}] is missing 'value'"
            )
    # logout_request method, if present
    if cs.logout_request:
        logout_method = str(
            cs.logout_request.get("method", "GET") or "GET"
        ).strip().upper()
        if logout_method not in VALID_HTTP_METHOD:
            raise ManagementPackValidationError(
                f"{stag}: logout_request.method must be one of "
                f"{sorted(VALID_HTTP_METHOD)}; got {logout_method!r}"
            )


def _validate_request(tag: str, req: RequestDef) -> None:
    rtag = f"{tag}: request '{req.name}'"
    if not req.name or not req.name.strip():
        raise ManagementPackValidationError(f"{tag}: request name is required")
    if req.method.upper() not in VALID_HTTP_METHOD:
        raise ManagementPackValidationError(
            f"{rtag}: method must be one of {sorted(VALID_HTTP_METHOD)}; "
            f"got {req.method!r}"
        )


def _validate_metric(tag: str, m: MetricDef, req_names: set) -> None:
    mtag = f"{tag}: metric '{m.key}'"
    if not m.key or not m.key.strip():
        raise ManagementPackValidationError(f"{tag}: metric key is required")
    if not m.label or not m.label.strip():
        raise ManagementPackValidationError(f"{mtag}: label is required")
    if m.usage not in VALID_METRIC_USAGE:
        raise ManagementPackValidationError(
            f"{mtag}: usage must be one of {sorted(VALID_METRIC_USAGE)}; "
            f"got {m.usage!r}"
        )
    if m.type not in VALID_METRIC_TYPE:
        raise ManagementPackValidationError(
            f"{mtag}: type must be one of {sorted(VALID_METRIC_TYPE)}; "
            f"got {m.type!r}"
        )
    if m.usage == "METRIC" and m.type != "NUMBER":
        raise ManagementPackValidationError(
            f"{mtag}: METRIC usage requires type NUMBER; got {m.type!r}"
        )
    # Validate source reference
    if m.source:
        match = _SOURCE_RE.match(m.source)
        if not match:
            raise ManagementPackValidationError(
                f"{mtag}: source must be 'request:<name>.<field>'; "
                f"got {m.source!r}"
            )
        req_ref = match.group(1)
        if req_ref not in req_names:
            raise ManagementPackValidationError(
                f"{mtag}: source references unknown request '{req_ref}' "
                f"(known: {sorted(req_names)})"
            )


# ---------------------------------------------------------------------------
# events: rejected at YAML-parse time
# ---------------------------------------------------------------------------

def _reject_events_key(raw: dict, context: str) -> None:
    """Raise immediately if 'events' appears in a raw mapping."""
    if "events" in raw:
        raise ManagementPackValidationError(
            f"{context}: 'events' is not supported in MP YAML v1. "
            f"The 10 threshold conditions previously encoded as events must be "
            f"authored as factory symptoms + alerts (using symptom-author and "
            f"alert-author) after the MP is installed. Remove the 'events' key "
            f"and rewrite each threshold as a factory symptom referencing the "
            f"MP adapter kind's metric."
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_request(raw: dict, parent_tag: str) -> RequestDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each request must be a mapping"
        )
    return RequestDef(
        name=str(raw.get("name", "") or "").strip(),
        method=str(raw.get("method", "GET") or "GET").strip().upper(),
        path=raw.get("path"),
        params=raw.get("params") or [],
        body=raw.get("body"),
        response_path=raw.get("response_path"),
    )


def _parse_metric(raw: dict, parent_tag: str) -> MetricDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each metric must be a mapping"
        )
    return MetricDef(
        key=str(raw.get("key", "") or "").strip(),
        label=str(raw.get("label", "") or "").strip(),
        usage=str(raw.get("usage", "") or "").strip().upper(),
        type=str(raw.get("type", "") or "").strip().upper(),
        source=str(raw.get("source", "") or "").strip(),
        unit=str(raw.get("unit", "") or "").strip(),
        kpi=bool(raw.get("kpi", False)),
    )


def _parse_custom_session(raw: dict, parent_tag: str) -> SessionDef:
    """Parse a CUSTOM-auth session block."""
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: auth.session must be a mapping for CUSTOM auth"
        )
    raw_login = raw.get("login_request")
    if not isinstance(raw_login, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: auth.session.login_request must be a mapping"
        )
    raw_logout = raw.get("logout_request")
    raw_headers = raw.get("header_injection") or []
    if not isinstance(raw_headers, list):
        raise ManagementPackValidationError(
            f"{parent_tag}: auth.session.header_injection must be a list"
        )
    return SessionDef(
        login_request=raw_login,
        logout_request=raw_logout if isinstance(raw_logout, dict) else None,
        cookie_binding=str(raw.get("cookie_binding", "") or "").strip(),
        header_injection=list(raw_headers),
    )


def _parse_object_type(raw: dict, parent_tag: str) -> ObjectTypeDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each object_type must be a mapping"
        )
    ot_name = str(raw.get("name", "") or "").strip()
    ot_tag = f"{parent_tag}: object_type '{ot_name}'"

    # Reject events key immediately
    _reject_events_key(raw, ot_tag)

    raw_key = raw.get("key")
    ot_key = str(raw_key).strip() if raw_key else _derive_object_key(ot_name)

    raw_requests = raw.get("requests") or []
    if not isinstance(raw_requests, list):
        raise ManagementPackValidationError(f"{ot_tag}: requests must be a list")
    requests = [_parse_request(r, ot_tag) for r in raw_requests]

    raw_metrics = raw.get("metrics") or []
    if not isinstance(raw_metrics, list):
        raise ManagementPackValidationError(f"{ot_tag}: metrics must be a list")
    metrics = [_parse_metric(m, ot_tag) for m in raw_metrics]

    identifiers = list(raw.get("identifiers") or [])

    return ObjectTypeDef(
        name=ot_name,
        key=ot_key,
        type=str(raw.get("type", "INTERNAL") or "INTERNAL").strip().upper(),
        icon=str(raw.get("icon", "server.svg") or "server.svg").strip(),
        is_world=bool(raw.get("is_world", False)),
        identifiers=identifiers,
        name_expression=str(raw.get("name_expression", "") or "").strip(),
        requests=requests,
        metrics=metrics,
    )


def _parse_auth(raw: dict, parent_tag: str) -> AuthDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: auth must be a mapping"
        )
    auth_type = str(raw.get("type", "NONE") or "NONE").strip().upper()
    if auth_type == "CUSTOM":
        raw_session = raw.get("session")
        custom_session = _parse_custom_session(
            raw_session if isinstance(raw_session, dict) else {},
            f"{parent_tag}: auth",
        )
        return AuthDef(
            type=auth_type,
            session=None,
            custom_session=custom_session,
        )
    return AuthDef(
        type=auth_type,
        session=raw.get("session"),
        custom_session=None,
    )


def _parse_config_field(raw: dict, parent_tag: str) -> ConfigFieldDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each config_field must be a mapping"
        )
    return ConfigFieldDef(
        key=str(raw.get("key", "") or "").strip(),
        label=str(raw.get("label", "") or "").strip(),
        type=str(raw.get("type", "STRING") or "STRING").strip().upper(),
        default=str(raw.get("default", "") or ""),
        description=str(raw.get("description", "") or "").strip(),
    )


def _parse_source(raw: dict, parent_tag: str) -> SourceDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: source must be a mapping"
        )
    raw_auth = raw.get("auth")
    auth = _parse_auth(raw_auth, f"{parent_tag}: source") if raw_auth else None

    raw_cfs = raw.get("config_fields") or []
    config_fields = [_parse_config_field(cf, f"{parent_tag}: source") for cf in raw_cfs]

    return SourceDef(
        port=int(raw.get("port", 443) or 443),
        ssl=str(raw.get("ssl", "NO_VERIFY") or "NO_VERIFY").strip().upper(),
        base_path=str(raw.get("base_path", "") or "").strip(),
        timeout=int(raw.get("timeout", 30) or 30),
        max_retries=int(raw.get("max_retries", 2) or 2),
        max_concurrent=int(raw.get("max_concurrent", 15) or 15),
        auth=auth,
        test_request=raw.get("test_request"),
        config_fields=config_fields,
    )


# ---------------------------------------------------------------------------
# MPB event parsing helpers
# ---------------------------------------------------------------------------

def _parse_match_rule(raw: dict, parent_tag: str) -> MatchRuleDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each match_rule must be a mapping"
        )
    return MatchRuleDef(
        field=str(raw.get("field", "") or "").strip(),
        operator=str(raw.get("operator", "") or "").strip().upper(),
        value=str(raw.get("value", "") or ""),
    )


def _parse_object_binding(raw: dict, parent_tag: str) -> ObjectBindingDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: object_binding must be a mapping"
        )
    raw_normalizer = raw.get("match_normalizer")
    return ObjectBindingDef(
        object_type=str(raw.get("object_type", "") or "").strip(),
        match_field=str(raw.get("match_field", "") or "").strip() or None,
        match_normalizer=(
            str(raw_normalizer).strip() if raw_normalizer else None
        ),
    )


def _parse_collection_strategy(raw: dict, parent_tag: str) -> CollectionStrategyDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: collection_strategy must be a mapping"
        )
    raw_fields = raw.get("dedup_fields") or []
    if not isinstance(raw_fields, list):
        raise ManagementPackValidationError(
            f"{parent_tag}: collection_strategy.dedup_fields must be a list"
        )
    return CollectionStrategyDef(
        interval_seconds=int(raw.get("interval_seconds", 300) or 300),
        dedup_strategy=str(raw.get("dedup_strategy", "NONE") or "NONE").strip().upper(),
        dedup_fields=[str(f) for f in raw_fields],
    )


def _parse_mpb_event(raw: dict, parent_tag: str) -> MPBEventDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each mpb_event must be a mapping"
        )
    ev_name = str(raw.get("name", "") or "").strip()
    etag = f"{parent_tag}: mpb_event '{ev_name}'"

    raw_rules = raw.get("match_rules") or []
    if not isinstance(raw_rules, list):
        raise ManagementPackValidationError(f"{etag}: match_rules must be a list")
    match_rules = [_parse_match_rule(r, etag) for r in raw_rules]

    raw_ob = raw.get("object_binding")
    object_binding = (
        _parse_object_binding(raw_ob, etag)
        if isinstance(raw_ob, dict)
        else None
    )

    raw_cs = raw.get("collection_strategy")
    collection_strategy = (
        _parse_collection_strategy(raw_cs, etag)
        if isinstance(raw_cs, dict)
        else None
    )

    raw_desc = raw.get("description")
    raw_msg = raw.get("message_template")

    return MPBEventDef(
        name=ev_name,
        severity=str(raw.get("severity", "") or "").strip().upper(),
        source_request=str(raw.get("source_request", "") or "").strip(),
        response_path=str(raw.get("response_path", "") or "").strip(),
        match_rules=match_rules,
        object_binding=object_binding,
        collection_strategy=collection_strategy,
        message_template=str(raw_msg).strip() if raw_msg else None,
        description=str(raw_desc).strip() if raw_desc else None,
    )


# ---------------------------------------------------------------------------
# Public load functions
# ---------------------------------------------------------------------------

def load_file(path: str | Path) -> ManagementPackDef:
    path = Path(path)
    try:
        data = _strict_load(path.read_text()) or {}
    except yaml.constructor.ConstructorError as exc:
        raise ManagementPackValidationError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManagementPackValidationError(f"{path}: expected a YAML mapping")

    # Reject top-level events key
    _reject_events_key(data, str(path))

    mp_name = str(data.get("name", "") or "").strip()
    tag = mp_name or str(path)

    raw_adapter_kind = data.get("adapter_kind")
    adapter_kind = (
        str(raw_adapter_kind).strip()
        if raw_adapter_kind
        else _derive_adapter_kind(mp_name)
    )

    raw_source = data.get("source")
    source = _parse_source(raw_source, tag) if raw_source else None

    raw_ots = data.get("object_types") or []
    if not isinstance(raw_ots, list):
        raise ManagementPackValidationError(f"{tag}: object_types must be a list")
    object_types = [_parse_object_type(ot, tag) for ot in raw_ots]

    raw_rels = data.get("relationships") or []
    if not isinstance(raw_rels, list):
        raise ManagementPackValidationError(f"{tag}: relationships must be a list")
    relationships = []
    for raw_rel in raw_rels:
        if not isinstance(raw_rel, dict):
            raise ManagementPackValidationError(
                f"{tag}: each relationship must be a mapping"
            )
        relationships.append(RelationshipDef(
            parent=str(raw_rel.get("parent", "") or "").strip(),
            child=str(raw_rel.get("child", "") or "").strip(),
            child_expression=raw_rel.get("child_expression") or None,
            parent_expression=raw_rel.get("parent_expression") or None,
        ))

    raw_events = data.get("mpb_events") or []
    if not isinstance(raw_events, list):
        raise ManagementPackValidationError(f"{tag}: mpb_events must be a list")
    mpb_events = [_parse_mpb_event(ev, tag) for ev in raw_events]

    raw_content = data.get("content") or {}
    if not isinstance(raw_content, dict):
        raise ManagementPackValidationError(f"{tag}: content must be a mapping")

    mp = ManagementPackDef(
        name=mp_name,
        version=str(data.get("version", "") or "").strip(),
        adapter_kind=adapter_kind,
        description=str(data.get("description", "") or "").strip(),
        build_number=int(data.get("build_number", 1) or 1),
        author=str(data.get("author", "") or "").strip(),
        source=source,
        object_types=object_types,
        relationships=relationships,
        mpb_events=mpb_events,
        content=raw_content,
        source_path=path,
    )
    mp.validate()
    return mp


def load_dir(directory: str | Path = "managementpacks") -> List[ManagementPackDef]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[ManagementPackDef] = []
    seen: dict = {}
    for p in sorted(directory.rglob("*.y*ml")):
        mp = load_file(p)
        if mp.name in seen:
            raise ManagementPackValidationError(
                f"duplicate management pack name '{mp.name}' "
                f"in {p} and {seen[mp.name]}"
            )
        seen[mp.name] = p
        out.append(mp)
    return out
