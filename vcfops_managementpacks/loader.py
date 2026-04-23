"""Load and validate management pack YAML definitions.

Management packs are identified by name.  Each YAML file in managementpacks/
defines one MP.  There is no UUID — the adapter kind key is derived from the
name if not supplied explicitly.

YAML schema — Option C grammar (Tier 3.3, 2026-04-18):

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
        # Flow-based auth grammar (Tier 3.2, 2026-04-18).
        # Use a named preset; authors fill in preset-specific blocks.
        preset: cookie_session          # one of: cookie_session, bearer_token, basic_auth, none
        credentials:
          - {key: username, label: username, sensitive: false}
          - {key: passwd,   label: passwd,   sensitive: true}
        login:
          method: GET
          path: "auth.cgi"
          params:
            - {key: api,     value: "SYNO.API.Auth"}
            - {key: version, value: "3"}
            - {key: method,  value: "login"}
            - {key: session, value: "FileStation"}
            - {key: format,  value: "cookie"}
            - {key: account, value: "${credentials.username}"}
            - {key: passwd,  value: "${credentials.passwd}"}
        extract:
          location: HEADER              # HEADER or BODY
          name: set_cookie              # header name or JSON path
          bind_to: session.set_cookie   # session variable
        inject:
          - type: header                # header or query_param
            name: id
            value: "${session.set_cookie}"
        logout:
          method: DELETE
          path: "auth.cgi"
          params:
            - {key: api,     value: "SYNO.API.Auth"}
            - {key: version, value: "3"}
            - {key: method,  value: "logout"}
      test_request:
        path: "entry.cgi"
        method: GET
        params: [...]
      config_fields: []

    # NEW (Option C) — requests at MP scope, not under object_type
    requests:
      - name: storage_load_info
        method: GET
        path: "entry.cgi"
        params:
          - {key: api, value: "SYNO.Storage.CGI.Storage"}
        response_path: "data"

      - name: volume_util
        method: GET
        path: "entry.cgi"
        params:
          - {key: location, value: "${chain.volume_id}"}   # chain substitution
        response_path: "data"

    object_types:
      - name: "Synology Diskstation"
        key: "diskstation"
        type: INTERNAL
        is_world: true
        identifiers: [serial]
        name_expression: "model"

        # NEW (Option C) — replaces implicit request-is-metricSet
        metricSets:
          - from_request: system_info
            list_path: ""          # empty = consume whole response root

        metrics:
          - key: serial
            label: "Serial Number"
            usage: PROPERTY
            type: STRING
            source: "metricset:system_info.serial"   # NEW source form

      - name: "Volume"
        key: volume
        type: INTERNAL
        identifiers: [volume_id]
        name_expression: display_name

        metricSets:
          - from_request: storage_load_info
            primary: true
            list_path: "volumes"
          - from_request: volume_util
            chained_from: storage_load_info     # parent metricSet on THIS object_type
            list_path: "space.volume"
            bind:
              - name: volume_id               # ${chain.volume_id} in the request
                from_attribute: id            # parent row attribute label

        metrics:
          - key: volume_id
            source: "metricset:storage_load_info.id"
          - key: io_read_iops
            source: "metricset:volume_util.read_access"

    relationships:
      - parent: diskstation
        child: volume
        child_expression: pool_path
        parent_expression: id

    content:
      dashboards: []
      views: []

SKIP CONVENTION:
    load_dir() ignores files whose name contains ".reference." so that
    archived pre-Option-C YAMLs can coexist in the directory as reference
    material without being loaded.  Example:
        managementpacks/synology_dsm.reference.yaml   ← skipped
        managementpacks/synology_dsm.yaml             ← loaded

MIGRATION NOTE:
    Old grammar had requests: under each object_type: entry and used
    source: "request:<name>.<field>" in metrics.  Both forms now produce
    a ManagementPackValidationError with a clear migration hint.  See
    designs/synology-mp-v1.md §"Chaining grammar design" for the Option C
    specification.
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
# Flow-based auth presets (Tier 3.2, 2026-04-18).
# VALID_AUTH_TYPE enum is retired — see migration note in _parse_auth().
VALID_AUTH_PRESET = {"cookie_session", "bearer_token", "basic_auth", "none"}
VALID_SSL = {"NO_VERIFY", "VERIFY", "NO_SSL"}

# Relationship scope kinds (Tier 3.3, 2026-04-18).
# field_match — value-join predicate (child_expression + parent_expression required).
# adapter_instance — trivial adapter-instance containment (no expressions allowed).
VALID_RELATIONSHIP_SCOPE = {"field_match", "adapter_instance"}

# World-object identity tiers (Tier 3.3, 2026-04-18).
# Ordered preference: system_issued > connection_address > display_name.
VALID_IDENTITY_TIER = {"system_issued", "connection_address", "display_name"}
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
_SINGLE_METRIC_RE = re.compile(r"^\$\{([a-zA-Z0-9_]+)\}$|^([a-zA-Z0-9_]+)$")

# Detect template strings that contain ${...} tokens.
_TEMPLATE_RE = re.compile(r"\$\{[^}]+\}")

# NEW: Parse "metricset:<metricset_name>.<field_path>" source references
_METRICSET_SOURCE_RE = re.compile(r"^metricset:([a-zA-Z0-9_]+)\.(.+)$")

# OLD (rejected): "request:<request_name>.<field_path>" source references
_OLD_REQUEST_SOURCE_RE = re.compile(r"^request:[a-zA-Z0-9_]+\..+$")

# ${chain.<name>} substitution in request params/path/body
_CHAIN_TOKEN_RE = re.compile(r"\$\{chain\.([a-zA-Z0-9_]+)\}")


# Derive adapter_kind from MP name: lowercase, replace non-alphanum with _
def _derive_adapter_kind(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return f"mpb_{slug}"

# Derive object type key from object name
def _derive_object_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------

class ManagementPackValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class IdentifierDef:
    """One identifier entry (Tier 3.3 structured form).

    Shorthand ``identifiers: [foo, bar]`` parses to a list of
    ``IdentifierDef(key='foo', source=None)`` etc.

    ``source`` — optional; ``None`` means "use the primary metricSet by
    convention" (renderer resolves at emit time).

    ``derive`` — reserved for future use. If present the loader raises
    ``ManagementPackValidationError`` with a "reserved — not implementable
    yet" message.
    """
    key: str
    source: Optional[str] = None   # "metricset:<name>.<path>" or None
    derive: Optional[Any] = None   # reserved; fail-loud if set


@dataclass
class NamePartDef:
    """One part of a structured name_expression (Tier 3.3).

    Exactly one of ``metric`` or ``literal`` must be set.
    """
    metric: Optional[str] = None    # metric key on this object_type
    literal: Optional[str] = None   # literal text string


@dataclass
class NameExpressionDef:
    """Structured name expression (Tier 3.3).

    Both shorthand (``name_expression: hostname``) and structured
    (``name_expression: {parts: [...]}``) parse to this type.

    ``parts`` contains at least one ``NamePartDef``.  At render time:
    - Single-part (one ``metric`` entry): emits the standard single-part
      expression (verified wire format).
    - Multi-part: renderer raises a clear "not yet implemented" error until
      live capture of the composite wire format is available.
    """
    parts: List["NamePartDef"]


@dataclass
class MetricSourceDef:
    """Structured metric source (Tier 3.3).

    Both shorthand (``source: "metricset:X.Y.Z"``) and structured
    (``source: {metricset: X, path: Y.Z}``) parse to this type.

    ``aggregate``, ``extract``, ``compose`` are reserved for future use.
    If any is set the loader raises a "reserved — not implementable yet"
    error.
    """
    metricset: str
    path: str
    aggregate: Optional[str] = None   # reserved
    extract: Optional[Any] = None     # reserved
    compose: Optional[Any] = None     # reserved


@dataclass
class WorldIdentityDef:
    """Identity declaration for a world object_type (Tier 3.3 axis 7).

    ``tier`` names the identity preference category:
      - ``system_issued``     — stable hardware/system UUID or serial
      - ``connection_address`` — operator-entered hostname/URL
      - ``display_name``      — last resort; admin-entered name

    ``source`` — ``"metricset:<name>.<path>"`` shorthand pointing at the
    metric that carries the unique identity value.  Required for
    ``system_issued``; for other tiers the renderer logs the tier choice
    but the wire emission is the same.
    """
    tier: str     # VALID_IDENTITY_TIER
    source: str   # "metricset:<name>.<path>"


@dataclass
class MetricDef:
    key: str
    label: str
    usage: str              # PROPERTY or METRIC
    type: str               # STRING or NUMBER
    source: "MetricSourceDef"   # parsed source (Tier 3.3)
    unit: str = ""
    kpi: bool = False


@dataclass
class PagingDef:
    """Explicit paging declaration on a request (Tier 3.3+, 2026-04-21).

    Authors who need true MPB-managed chunked pagination declare this block.
    The factory emits the paging wire block from this declaration so MPB
    performs multi-page fetching.  Most APIs that use offset/limit params
    simply need those as literal query params without this block — pass them
    in ``params:`` directly and omit ``paging:``.

    Fields match the MPB paging wire shape observed in captured designs:
      type          — pagination strategy; only "OFFSET" observed.
      paging_param  — query-param key for the page offset (e.g. "offset").
      limit_param   — query-param key for the page size (e.g. "limit").
      limit_value   — concrete page-size integer sent to the server.
      list_path_id  — dot-path (with trailing .*) pointing at the
                      response array that contains the page items
                      (e.g. "data.volumes.*").  Maps to MPB listPathId.
      start         — initial offset value (almost always 0).
    """
    type: str           # OFFSET (only value observed in wire captures)
    paging_param: str   # offset param key
    limit_param: str    # limit param key
    limit_value: int    # concrete page size
    list_path_id: str   # response path to paged array (e.g. "data.volumes.*")
    start: int = 0      # initial offset (default 0)


@dataclass
class RequestDef:
    name: str
    method: str
    path: Optional[str]
    params: Any = field(default_factory=list)   # list[{key,value}] or dict
    body: Optional[str] = None
    response_path: Optional[str] = None
    paging: Optional["PagingDef"] = None        # explicit paging; None = no paging


@dataclass
class BindDef:
    """Per-row substitution binding on a chained metricSet."""
    name: str            # factory-facing key; ${chain.<name>} in parent request templates
    from_attribute: str  # attribute label on the parent metricSet's rows


@dataclass
class MetricSetDef:
    """One metricSet entry on an object_type (Option C grammar)."""
    from_request: str                    # top-level request name
    list_path: str = ""                  # sub-path under request.response_path
    primary: bool = False                # exactly one per list object_type
    chained_from: Optional[str] = None   # sibling metricSet's from_request name
    bind: List[BindDef] = field(default_factory=list)
    # Optional alias for this metricSet within the object_type;
    # defaults to from_request; used as the key in chained_from lookups.
    as_name: Optional[str] = None

    @property
    def local_name(self) -> str:
        """The name used to identify this metricSet within its object_type's metricSets list."""
        return self.as_name if self.as_name else self.from_request


@dataclass
class CredentialFieldDef:
    """One declared credential field in auth.credentials[]."""
    key: str            # factory-facing key; used in ${credentials.<key>} references
    label: str          # wire label; determines ${authentication.credentials.<label>} variable name
    sensitive: bool = False


@dataclass
class LoginRequestDef:
    """auth.login block — the session-establishment request."""
    method: str                     # HTTP method (GET, POST, ...)
    path: str                       # request path (relative to base_path)
    params: Any = None              # list of {key, value} or dict
    headers: Optional[List[Dict[str, Any]]] = None
    body: Optional[str] = None


@dataclass
class ExtractRuleDef:
    """auth.extract block — where to find the session token in the login response."""
    location: str     # HEADER or BODY
    name: str         # header name (for HEADER) or JSON path (for BODY)
    bind_to: str      # session variable name as "session.<key>" (e.g. "session.set_cookie")

    @property
    def session_key(self) -> str:
        """The bare session key, stripped of the 'session.' prefix."""
        if self.bind_to.startswith("session."):
            return self.bind_to[len("session."):]
        return self.bind_to


@dataclass
class InjectRuleDef:
    """One entry in auth.inject[] — where/how to inject the session token per request."""
    type: str    # "header" or "query_param"
    name: str    # header name or query-param key
    value: str   # value template (may reference ${session.<key>} or ${credentials.<key>})


@dataclass
class LogoutRequestDef:
    """auth.logout block — the session-teardown request."""
    method: str
    path: str
    params: Any = None
    headers: Optional[List[Dict[str, Any]]] = None
    body: Optional[str] = None


@dataclass
class AuthFlowDef:
    """Flow-based auth definition (Tier 3.2).

    Replaces the old AuthDef + SessionDef pair.  Every auth block now carries:
      preset       — named shorthand that sets the MPB credentialType and
                     supplies defaults for blocks the author omits.
      credentials  — declared credential fields (key, label, sensitive).
      login        — optional login (session-establishment) request.
      extract      — optional extraction rule for the session token.
      inject       — list of injection rules (headers / query params).
      logout       — optional logout (session-teardown) request.

    Preset rules (enforced by _validate_auth_flow):
      none          creds absent/empty; login/extract/inject/logout absent.
      basic_auth    creds: username + password pair only; login/extract/logout absent.
      bearer_token  creds: single token field; login/extract/logout absent.
      cookie_session creds, login, extract, inject, logout all REQUIRED.
    """
    preset: str
    credentials: List[CredentialFieldDef] = field(default_factory=list)
    login: Optional[LoginRequestDef] = None
    extract: Optional[ExtractRuleDef] = None
    inject: List[InjectRuleDef] = field(default_factory=list)
    logout: Optional[LogoutRequestDef] = None


@dataclass
class ObjectTypeDef:
    name: str
    key: str
    type: str               # INTERNAL or ARIA_OPS
    identifiers: List["IdentifierDef"]    # Tier 3.3 structured form
    metric_sets: List[MetricSetDef]       # Option C: explicit metricSets block
    metrics: List[MetricDef]
    icon: str = "server.svg"
    is_world: bool = False
    name_expression: Optional["NameExpressionDef"] = None   # Tier 3.3 structured form
    identity: Optional["WorldIdentityDef"] = None           # Tier 3.3 axis 7 (required for is_world)


@dataclass
class RelationshipDef:
    parent: str
    child: str
    scope: str = "field_match"                  # Tier 3.3: "field_match" or "adapter_instance"
    child_expression: Optional[str] = None      # metric key on child (required for field_match)
    parent_expression: Optional[str] = None     # metric key on parent (required for field_match)


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
    auth: Optional[AuthFlowDef] = None
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
    requests: List[RequestDef] = field(default_factory=list)   # NEW: MP-scope requests
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

    # Top-level requests: names must be unique
    request_names: Dict[str, int] = {}
    for i, req in enumerate(mp.requests):
        if not req.name or not req.name.strip():
            raise ManagementPackValidationError(
                f"{tag}: requests[{i}]: name is required"
            )
        if req.name in request_names:
            raise ManagementPackValidationError(
                f"{tag}: duplicate request name '{req.name}' (first at index "
                f"{request_names[req.name]}, repeated at {i})"
            )
        request_names[req.name] = i
        _validate_request(tag, req)

    # Object types
    object_keys: Dict[str, set] = {}  # key -> set of metric keys
    world_count = 0

    for ot in mp.object_types:
        ot_tag = f"{tag}: object_type '{ot.name}'"

        if not ot.name or not ot.name.strip():
            raise ManagementPackValidationError(f"{tag}: object type name is required")
        if ot.type not in VALID_OBJECT_TYPE:
            raise ManagementPackValidationError(
                f"{ot_tag}: type must be one of {sorted(VALID_OBJECT_TYPE)}; "
                f"got {ot.type!r}"
            )
        # Pure world kinds are topology roots and carry no identifiers by design.
        if not ot.is_world and not ot.identifiers:
            raise ManagementPackValidationError(
                f"{ot_tag}: at least one identifier is required"
            )
        # Validate each IdentifierDef
        for ident in ot.identifiers:
            _validate_identifier(ot_tag, ident)
        if not ot.is_world:
            # Non-world object types must have at least one metricSet and one metric.
            if not ot.metric_sets:
                raise ManagementPackValidationError(
                    f"{ot_tag}: at least one metricSet is required"
                )
            if not ot.metrics:
                raise ManagementPackValidationError(
                    f"{ot_tag}: at least one metric or property is required"
                )
        # World kinds (is_world: true) with no metric_sets/metrics are valid —
        # their only metrics are auto-computed summary rollups emitted by the
        # MPB runtime (ComputedMetrics in describe.xml).  If metric_sets or
        # metrics are present on a world kind they are still validated below.

        if ot.is_world:
            world_count += 1
            # identity block is required for world objects
            if ot.identity is None:
                raise ManagementPackValidationError(
                    f"{ot_tag}: is_world: true objects require an 'identity:' block. "
                    f"Add 'identity: {{tier: system_issued, source: \"metricset:<name>.<path>\"}}' "
                    f"(or connection_address / display_name tier as appropriate). "
                    f"See designs/synology-mp-v1.md §\"Axis 7 — World-object identity\"."
                )
        else:
            # Non-world objects must NOT declare identity
            if ot.identity is not None:
                raise ManagementPackValidationError(
                    f"{ot_tag}: is_world: false objects must not declare 'identity:'. "
                    f"Remove the 'identity:' block or set 'is_world: true'."
                )

        # Build the set of local metricSet names for this object_type
        ms_local_names: Dict[str, int] = {}
        for i, ms in enumerate(ot.metric_sets):
            local = ms.local_name
            if local in ms_local_names:
                raise ManagementPackValidationError(
                    f"{ot_tag}: metricSets[{i}]: duplicate local name '{local}' "
                    f"(also at index {ms_local_names[local]}). Use 'as:' on one "
                    f"of them to disambiguate."
                )
            ms_local_names[local] = i

        # Validate each metricSet
        for i, ms in enumerate(ot.metric_sets):
            _validate_metric_set(ot_tag, i, ms, request_names, ms_local_names,
                                 is_world=ot.is_world)

        # Primary-validator
        _validate_primary(ot_tag, ot)

        # Chain-graph walker (cycle detection + orphan detection)
        _validate_chain_graph(ot_tag, ot)

        # Validate ${chain.*} token coverage on each chained request
        _validate_chain_tokens(ot_tag, ot, mp.requests)

        # Collect metric keys for this object_type
        # Build the set of metricSet local names for source validation
        ms_names_for_source = set(ms_local_names.keys())
        metric_keys = set()
        for m in ot.metrics:
            _validate_metric(ot_tag, m, ms_names_for_source)
            metric_keys.add(m.key)
        object_keys[ot.key] = metric_keys

        # Validate name_expression (NameExpressionDef)
        if ot.name_expression is not None:
            _validate_name_expression(ot_tag, ot.name_expression, metric_keys)

    # Exactly one world object
    if mp.object_types and world_count != 1:
        raise ManagementPackValidationError(
            f"{tag}: exactly one object_type must have is_world: true; "
            f"found {world_count}"
        )

    # Relationships reference valid object type keys + scope validation
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
        _validate_relationship_scope(tag, rel)

    # Collect all request names for MPB event cross-reference
    all_request_names: set = set(request_names.keys())

    # MPB events
    for ev in mp.mpb_events:
        _validate_mpb_event(ev, tag, all_request_names, set(object_keys.keys()))


def _validate_metric_set(
    ot_tag: str,
    index: int,
    ms: MetricSetDef,
    mp_request_names: Dict[str, int],
    sibling_names: Dict[str, int],
    is_world: bool = False,
) -> None:
    """Validate one MetricSetDef entry."""
    import warnings as _warnings
    mstag = f"{ot_tag}: metricSets[{index}]"

    if not ms.from_request or not ms.from_request.strip():
        raise ManagementPackValidationError(f"{mstag}: from_request is required")

    # list_path must NOT carry a trailing .*
    # The renderer appends .* automatically for array iteration.
    # A trailing .* produces a double-star path (data.volumes.*.* instead of
    # data.volumes.*) which MPB silently uses as a sub-nested iterator, causing
    # metricSet attributes to be associated with the wrong response level.
    # Confirmed as the silent-failure mode on 2026-04-21 QA audit.
    # Emitted as a DeprecationWarning (not an error) to avoid breaking pre-fix
    # YAMLs that pre-date this lint; the renderer handles it correctly by
    # stripping the trailing .* before computing the DML id.
    # New YAMLs MUST NOT use the trailing .* form.
    lp = ms.list_path or ""
    if lp.endswith(".*"):
        _warnings.warn(
            f"{mstag}: list_path '{lp}' must NOT end with '.*' — "
            f"the renderer appends '.*' automatically. "
            f"Correct form: list_path: '{lp[:-2]}' (bare array name, no trailing .*). "
            f"A trailing .* produces a double-star path (e.g. data.volumes.*.* instead "
            f"of data.volumes.*) which MPB interprets as a nested sub-iterator, "
            f"causing all metrics on this metricSet to be silently unresolvable. "
            f"This will become a hard error in a future release.",
            DeprecationWarning,
            stacklevel=4,
        )

    # World/singleton objects must have an empty list_path on every metricSet.
    # They consume the whole response root as scalar context ("base" DML).
    # A non-empty list_path on a world object produces a wildcard DML instead
    # of the required "base" DML, causing all world-object metrics to be
    # silently unresolvable at collection time (2026-04-21 QA audit).
    # Emitted as a DeprecationWarning (matching the .*  lint above) rather than
    # a hard error for backward-compat; new YAMLs must not use this form.
    if is_world and lp.strip():
        _warnings.warn(
            f"{mstag} (from_request: '{ms.from_request}'): "
            f"list_path should be empty ('') on is_world: true objects. "
            f"World/singleton objects consume the whole response root as scalar "
            f"context (MPB 'base' DML). A non-empty list_path produces a wildcard "
            f"DML causing all metrics on this object to be silently unresolvable. "
            f"This will become a hard error in a future release.",
            DeprecationWarning,
            stacklevel=4,
        )

    if ms.from_request not in mp_request_names:
        raise ManagementPackValidationError(
            f"{mstag}: from_request '{ms.from_request}' does not match any "
            f"top-level request (known: {sorted(mp_request_names)})"
        )

    if ms.chained_from is not None:
        # chained_from must name a sibling metricSet local_name
        if ms.chained_from not in sibling_names:
            raise ManagementPackValidationError(
                f"{mstag}: chained_from '{ms.chained_from}' does not match any "
                f"sibling metricSet local name (known: {sorted(sibling_names)}). "
                f"chained_from must reference a sibling metricSet's from_request "
                f"(or its 'as:' alias if set)."
            )
        if ms.chained_from == ms.local_name:
            raise ManagementPackValidationError(
                f"{mstag}: chained_from cannot point at itself ('{ms.chained_from}')"
            )
        if not ms.bind:
            raise ManagementPackValidationError(
                f"{mstag}: chained_from '{ms.chained_from}' requires at least one "
                f"bind entry"
            )

    for j, b in enumerate(ms.bind):
        btag = f"{mstag}: bind[{j}]"
        if not b.name or not b.name.strip():
            raise ManagementPackValidationError(f"{btag}: name is required")
        if not b.from_attribute or not b.from_attribute.strip():
            raise ManagementPackValidationError(f"{btag}: from_attribute is required")


def _validate_primary(ot_tag: str, ot: ObjectTypeDef) -> None:
    """Validate primary metricSet rule per is_world."""
    primary_count = sum(1 for ms in ot.metric_sets if ms.primary)

    if ot.is_world:
        # World/singleton: primary must be absent/false on all metricSets
        if primary_count > 0:
            raise ManagementPackValidationError(
                f"{ot_tag}: is_world objects must not declare 'primary: true' "
                f"on any metricSet (singletons don't define list membership); "
                f"found {primary_count} metricSet(s) with primary: true"
            )
    else:
        # List object: exactly one primary required
        if primary_count == 0:
            raise ManagementPackValidationError(
                f"{ot_tag}: list objects (is_world: false) require exactly one "
                f"metricSet with 'primary: true'; found zero"
            )
        if primary_count > 1:
            raise ManagementPackValidationError(
                f"{ot_tag}: list objects (is_world: false) must have exactly one "
                f"metricSet with 'primary: true'; found {primary_count}"
            )


def _validate_chain_graph(ot_tag: str, ot: ObjectTypeDef) -> None:
    """Detect cycles and orphan chains in the metricSet chained_from graph."""
    # Build adjacency: local_name -> chained_from (or None)
    local_names = {ms.local_name for ms in ot.metric_sets}

    # Detect orphan chains (chained_from points at a non-existent sibling)
    # This is already caught in _validate_metric_set, but double-check here
    # for cross-object-type chain detection.
    for ms in ot.metric_sets:
        if ms.chained_from is not None and ms.chained_from not in local_names:
            raise ManagementPackValidationError(
                f"{ot_tag}: metricSet '{ms.local_name}' has chained_from "
                f"'{ms.chained_from}' which is not a sibling metricSet. "
                f"Cross-object-type chains are not supported in v1."
            )

    # Detect cycles using DFS
    parent_map: Dict[str, Optional[str]] = {
        ms.local_name: ms.chained_from for ms in ot.metric_sets
    }

    def _find_cycle(start: str) -> Optional[List[str]]:
        visited: List[str] = []
        current: Optional[str] = start
        while current is not None:
            if current in visited:
                cycle_start = visited.index(current)
                return visited[cycle_start:]
            visited.append(current)
            current = parent_map.get(current)
        return None

    for name in list(parent_map.keys()):
        cycle = _find_cycle(name)
        if cycle:
            raise ManagementPackValidationError(
                f"{ot_tag}: cycle detected in metricSet chained_from graph: "
                f"{' -> '.join(cycle)} -> {cycle[0]}"
            )


def _validate_chain_tokens(
    ot_tag: str,
    ot: ObjectTypeDef,
    mp_requests: List[RequestDef],
) -> None:
    """Validate ${chain.*} token coverage.

    For each chained metricSet, ensure every ${chain.<name>} token in the
    request's params/path/body/headers has a matching bind entry.
    Also ensure that requests with ${chain.*} tokens are consumed as a
    chained metricSet on at least one object_type (within this object_type's
    metricSets).
    """
    request_by_name: Dict[str, RequestDef] = {r.name: r for r in mp_requests}

    for ms in ot.metric_sets:
        req = request_by_name.get(ms.from_request)
        if req is None:
            continue  # already caught by _validate_metric_set

        # Collect all ${chain.*} tokens in this request's templates
        chain_tokens_in_req: set = set()
        for part in _collect_request_template_parts(req):
            for m in _CHAIN_TOKEN_RE.finditer(part):
                chain_tokens_in_req.add(m.group(1))

        if chain_tokens_in_req and ms.chained_from is None:
            # Request has chain tokens but this metricSet is not chained
            raise ManagementPackValidationError(
                f"{ot_tag}: metricSet '{ms.local_name}' uses request "
                f"'{ms.from_request}' which contains ${{chain.*}} token(s) "
                f"{sorted(chain_tokens_in_req)!r}, but no 'chained_from' is "
                f"declared on this metricSet. Either add 'chained_from:' or "
                f"remove the ${{chain.*}} token from the request params/path/body."
            )

        if ms.chained_from is not None:
            # Chained: verify all ${chain.*} tokens have matching bind entries
            bind_names = {b.name for b in ms.bind}
            missing = chain_tokens_in_req - bind_names
            if missing:
                raise ManagementPackValidationError(
                    f"{ot_tag}: metricSet '{ms.local_name}' is chained from "
                    f"'{ms.chained_from}' but request '{ms.from_request}' uses "
                    f"${{chain.*}} token(s) {sorted(missing)!r} with no matching "
                    f"bind entry. Add bind entries for each missing name."
                )


def _collect_request_template_parts(req: RequestDef) -> List[str]:
    """Return all string values from a request that may contain ${...} tokens."""
    parts: List[str] = []
    if req.path:
        parts.append(req.path)
    if req.body:
        parts.append(str(req.body))
    params = req.params or []
    if isinstance(params, list):
        for p in params:
            if isinstance(p, dict):
                v = p.get("value")
                if v:
                    parts.append(str(v))
    elif isinstance(params, dict):
        for v in params.values():
            if v:
                parts.append(str(v))
    return parts


def _validate_identifier(tag: str, ident: "IdentifierDef") -> None:
    """Validate one IdentifierDef."""
    if not ident.key or not ident.key.strip():
        raise ManagementPackValidationError(f"{tag}: identifier key is required")
    if ident.derive is not None:
        raise ManagementPackValidationError(
            f"{tag}: identifier '{ident.key}': 'derive:' is reserved for future use "
            f"and is not implementable in the current version. "
            f"Remove the 'derive:' key — computed/derived identifiers are not yet "
            f"supported. Use a metric key reference instead."
        )


def _validate_relationship_scope(tag: str, rel: "RelationshipDef") -> None:
    """Validate relationship scope + expression requirements."""
    rtag = f"{tag}: relationship {rel.parent!r} → {rel.child!r}"

    if rel.scope not in VALID_RELATIONSHIP_SCOPE:
        raise ManagementPackValidationError(
            f"{rtag}: scope must be one of {sorted(VALID_RELATIONSHIP_SCOPE)}; "
            f"got {rel.scope!r}"
        )

    if rel.scope == "adapter_instance":
        if rel.child_expression is not None or rel.parent_expression is not None:
            raise ManagementPackValidationError(
                f"{rtag}: scope 'adapter_instance' must not declare "
                f"child_expression or parent_expression (the renderer synthesizes "
                f"the wire-level predicate). Remove both expression fields."
            )

    elif rel.scope == "field_match":
        if rel.child_expression is None or rel.parent_expression is None:
            raise ManagementPackValidationError(
                f"{rtag}: scope 'field_match' requires both child_expression and "
                f"parent_expression. "
                f"Provide metric keys for both sides of the value-join predicate."
            )


def _validate_name_expression(
    tag: str,
    expr: "NameExpressionDef",
    metric_keys: set,
) -> None:
    """Validate a NameExpressionDef.

    Rules:
      - At least one part required.
      - Each part has exactly one of metric: or literal:.
      - Metric references must resolve to a metric on this object_type.
      - Multi-part expressions (more than one non-literal entry) are accepted
        by the grammar but the renderer will emit a "not yet implemented" error
        at render time.
    """
    if not expr.parts:
        raise ManagementPackValidationError(
            f"{tag}: name_expression requires at least one part. "
            f"Provide at least one '{{metric: <key>}}' or '{{literal: <text>}}' entry "
            f"under 'parts:'."
        )
    for i, part in enumerate(expr.parts):
        ptag = f"{tag}: name_expression.parts[{i}]"
        has_metric = part.metric is not None
        has_literal = part.literal is not None
        if has_metric and has_literal:
            raise ManagementPackValidationError(
                f"{ptag}: each part must have exactly one of 'metric:' or 'literal:', "
                f"not both. Got metric={part.metric!r} and literal={part.literal!r}."
            )
        if not has_metric and not has_literal:
            raise ManagementPackValidationError(
                f"{ptag}: each part must have exactly one of 'metric:' or 'literal:'. "
                f"Got neither."
            )
        if has_metric:
            if not part.metric.strip():
                raise ManagementPackValidationError(
                    f"{ptag}: metric key must not be empty"
                )
            if part.metric not in metric_keys:
                raise ManagementPackValidationError(
                    f"{ptag}: metric key {part.metric!r} is not declared on this "
                    f"object_type (known metric keys: {sorted(metric_keys)})"
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
            f"top-level request (known requests: {sorted(all_request_names)})"
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


def _validate_auth(tag: str, auth: AuthFlowDef) -> None:
    atag = f"{tag}: auth"

    if auth.preset not in VALID_AUTH_PRESET:
        raise ManagementPackValidationError(
            f"{atag}: unknown preset {auth.preset!r}. "
            f"Valid presets are: {sorted(VALID_AUTH_PRESET)}. "
            f"See designs/synology-mp-v1.md §\"Framework-vs-Synology review "
            f"(2026-04-18)\" axis 1 for the flow grammar spec."
        )

    preset = auth.preset

    if preset == "none":
        _validate_auth_none(atag, auth)
    elif preset == "basic_auth":
        _validate_auth_basic(atag, auth)
    elif preset == "bearer_token":
        _validate_auth_bearer(atag, auth)
    elif preset == "cookie_session":
        _validate_auth_cookie_session(atag, auth)

    # Validate ${credentials.X}, ${session.X}, ${configuration.X} references
    _validate_auth_substitution_refs(atag, auth)


def _validate_auth_none(tag: str, auth: AuthFlowDef) -> None:
    """Preset 'none': no credentials, no flow blocks."""
    if auth.credentials:
        raise ManagementPackValidationError(
            f"{tag}: preset 'none' must not declare credentials"
        )
    for block, name in [(auth.login, "login"), (auth.extract, "extract"),
                        (auth.logout, "logout")]:
        if block is not None:
            raise ManagementPackValidationError(
                f"{tag}: preset 'none' must not declare '{name}'"
            )
    if auth.inject:
        raise ManagementPackValidationError(
            f"{tag}: preset 'none' must not declare 'inject'"
        )


def _validate_auth_basic(tag: str, auth: AuthFlowDef) -> None:
    """Preset 'basic_auth': exactly username + password credentials; no flow blocks."""
    for block, name in [(auth.login, "login"), (auth.extract, "extract"),
                        (auth.logout, "logout")]:
        if block is not None:
            raise ManagementPackValidationError(
                f"{tag}: preset 'basic_auth' must not declare '{name}'"
            )
    # credentials: must have exactly a username and a password field
    keys = {c.key for c in auth.credentials}
    if "username" not in keys or "password" not in keys:
        raise ManagementPackValidationError(
            f"{tag}: preset 'basic_auth' requires credentials with keys "
            f"'username' and 'password'; found: {sorted(keys)!r}"
        )
    extra = keys - {"username", "password"}
    if extra:
        raise ManagementPackValidationError(
            f"{tag}: preset 'basic_auth' credentials must contain only "
            f"'username' and 'password'; unexpected keys: {sorted(extra)!r}"
        )
    _validate_inject_rules(tag, auth.inject)


def _validate_auth_bearer(tag: str, auth: AuthFlowDef) -> None:
    """Preset 'bearer_token': single token credential; no flow blocks."""
    for block, name in [(auth.login, "login"), (auth.extract, "extract"),
                        (auth.logout, "logout")]:
        if block is not None:
            raise ManagementPackValidationError(
                f"{tag}: preset 'bearer_token' must not declare '{name}'"
            )
    if len(auth.credentials) != 1:
        raise ManagementPackValidationError(
            f"{tag}: preset 'bearer_token' requires exactly one credential "
            f"field (the token); found {len(auth.credentials)}"
        )
    _validate_inject_rules(tag, auth.inject)


def _validate_auth_cookie_session(tag: str, auth: AuthFlowDef) -> None:
    """Preset 'cookie_session': all blocks required."""
    if not auth.credentials:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires credentials"
        )
    if auth.login is None:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires a 'login' block"
        )
    if auth.extract is None:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires an 'extract' block"
        )
    if not auth.inject:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires at least one 'inject' rule"
        )
    if auth.logout is None:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires a 'logout' block"
        )

    # login method
    login_method = (auth.login.method or "GET").strip().upper()
    if login_method not in VALID_HTTP_METHOD:
        raise ManagementPackValidationError(
            f"{tag}: login.method must be one of {sorted(VALID_HTTP_METHOD)}; "
            f"got {login_method!r}"
        )

    # extract location
    if auth.extract.location not in ("HEADER", "BODY"):
        raise ManagementPackValidationError(
            f"{tag}: extract.location must be HEADER or BODY; "
            f"got {auth.extract.location!r}"
        )
    if not auth.extract.name or not auth.extract.name.strip():
        raise ManagementPackValidationError(
            f"{tag}: extract.name is required"
        )
    if not auth.extract.bind_to or not auth.extract.bind_to.strip():
        raise ManagementPackValidationError(
            f"{tag}: extract.bind_to is required (e.g. 'session.set_cookie')"
        )

    # logout method
    logout_method = (auth.logout.method or "DELETE").strip().upper()
    if logout_method not in VALID_HTTP_METHOD:
        raise ManagementPackValidationError(
            f"{tag}: logout.method must be one of {sorted(VALID_HTTP_METHOD)}; "
            f"got {logout_method!r}"
        )

    _validate_inject_rules(tag, auth.inject)


def _validate_inject_rules(tag: str, inject: List) -> None:
    """Validate inject[] entries."""
    for i, rule in enumerate(inject):
        rtag = f"{tag}: inject[{i}]"
        if rule.type not in ("header", "query_param"):
            raise ManagementPackValidationError(
                f"{rtag}: type must be 'header' or 'query_param'; "
                f"got {rule.type!r}"
            )
        if not rule.name or not rule.name.strip():
            raise ManagementPackValidationError(f"{rtag}: name is required")
        if not rule.value or not rule.value.strip():
            raise ManagementPackValidationError(f"{rtag}: value is required")


# Patterns for substitution reference validation
_CRED_REF_RE = re.compile(r"\$\{credentials\.([a-zA-Z0-9_]+)\}")
_SESSION_REF_RE = re.compile(r"\$\{session\.([a-zA-Z0-9_]+)\}")


def _validate_auth_substitution_refs(tag: str, auth: AuthFlowDef) -> None:
    """Validate that ${credentials.X} and ${session.X} refs resolve."""
    declared_cred_keys = {c.key for c in auth.credentials}
    declared_session_keys: set = set()
    if auth.extract is not None:
        declared_session_keys.add(auth.extract.session_key)

    # Collect all template strings to check
    templates: List[str] = []

    def _collect_from_request(req) -> None:
        if req is None:
            return
        if req.path:
            templates.append(req.path)
        if req.body:
            templates.append(str(req.body))
        params = req.params or []
        if isinstance(params, list):
            for p in params:
                if isinstance(p, dict):
                    v = p.get("value")
                    if v:
                        templates.append(str(v))
        elif isinstance(params, dict):
            for v in params.values():
                if v:
                    templates.append(str(v))
        for h in (req.headers or []):
            if isinstance(h, dict):
                v = h.get("value")
                if v:
                    templates.append(str(v))

    _collect_from_request(auth.login)
    _collect_from_request(auth.logout)
    for rule in auth.inject:
        if rule.value:
            templates.append(rule.value)

    for tmpl in templates:
        for m in _CRED_REF_RE.finditer(tmpl):
            key = m.group(1)
            if key not in declared_cred_keys:
                raise ManagementPackValidationError(
                    f"{tag}: unresolved credential reference ${{credentials.{key}}}; "
                    f"declared credential keys: {sorted(declared_cred_keys)!r}"
                )
        for m in _SESSION_REF_RE.finditer(tmpl):
            key = m.group(1)
            if key not in declared_session_keys:
                raise ManagementPackValidationError(
                    f"{tag}: unresolved session reference ${{session.{key}}}; "
                    f"declared session keys (from extract.bind_to): "
                    f"{sorted(declared_session_keys)!r}"
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

    # paging: validation removed 2026-04-21 — paging key is retired.
    # _parse_request emits a DeprecationWarning if paging: is present in YAML.


def _validate_metric_source(tag: str, src: "MetricSourceDef", ms_names: set) -> None:
    """Validate a MetricSourceDef.

    Reserved fields (aggregate, extract, compose) raise an error if present.
    """
    if not src.metricset or not src.metricset.strip():
        raise ManagementPackValidationError(f"{tag}: source.metricset is required")
    if not src.path or not src.path.strip():
        raise ManagementPackValidationError(f"{tag}: source.path is required")
    if src.aggregate is not None:
        raise ManagementPackValidationError(
            f"{tag}: source.aggregate is reserved for future use and is not "
            f"implementable in the current version. "
            f"Remove the 'aggregate:' key — aggregation transforms are not yet supported."
        )
    if src.extract is not None:
        raise ManagementPackValidationError(
            f"{tag}: source.extract is reserved for future use and is not "
            f"implementable in the current version. "
            f"Remove the 'extract:' key — regex extraction is not yet supported."
        )
    if src.compose is not None:
        raise ManagementPackValidationError(
            f"{tag}: source.compose is reserved for future use and is not "
            f"implementable in the current version. "
            f"Remove the 'compose:' key — multi-source composition is not yet supported."
        )
    if src.metricset not in ms_names:
        raise ManagementPackValidationError(
            f"{tag}: source references unknown metricSet '{src.metricset}' "
            f"(known metricSet names on this object_type: {sorted(ms_names)}). "
            f"The name is the from_request value of the metricSet (or its 'as:' alias)."
        )


def _validate_metric(tag: str, m: MetricDef, ms_names: set) -> None:
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
    # Validate source (MetricSourceDef — Tier 3.3 structured form)
    _validate_metric_source(mtag, m.source, ms_names)


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


def _reject_object_type_requests(raw: dict, ot_tag: str) -> None:
    """Raise if 'requests' appears under an object_type (old Option A grammar)."""
    if "requests" in raw:
        raise ManagementPackValidationError(
            f"{ot_tag}: 'requests:' under an object_type is not supported in "
            f"the Option C grammar. Move all requests to the top-level 'requests:' "
            f"block (sibling of 'object_types:') and replace the implicit "
            f"request-is-metricSet convention with an explicit 'metricSets:' "
            f"block on each object_type. "
            f"See designs/synology-mp-v1.md §'Chaining grammar design'."
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_request(raw: dict, parent_tag: str) -> RequestDef:
    """Parse one request entry from YAML into a RequestDef.

    The ``paging:`` key is silently dropped (2026-04-21 retirement):
    MPB auto-derives paging configuration from live API responses during
    interactive import — authors do not need to declare it. If present in
    YAML it is ignored with a warning so existing files don't fail validation.
    The PagingDef dataclass and _render_paging() function are kept in render.py
    to avoid breaking the flat-format path, but RequestDef.paging is always None.
    """
    import warnings
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each request must be a mapping"
        )
    if raw.get("paging") is not None:
        req_name = raw.get("name", "<unnamed>")
        warnings.warn(
            f"{parent_tag}: request '{req_name}' declares paging: — "
            f"this key is retired (2026-04-21). MPB auto-derives paging from "
            f"live API responses. The paging: block is ignored and will not be "
            f"emitted. Remove it from your YAML to suppress this warning.",
            DeprecationWarning,
            stacklevel=3,
        )
    return RequestDef(
        name=str(raw.get("name", "") or "").strip(),
        method=str(raw.get("method", "GET") or "GET").strip().upper(),
        path=raw.get("path"),
        params=raw.get("params") or [],
        body=raw.get("body"),
        response_path=raw.get("response_path"),
        paging=None,  # always None — paging: key retired 2026-04-21
    )


def _parse_metric_source(raw_source: Any, parent_tag: str) -> "MetricSourceDef":
    """Parse a metric source — string shorthand or structured dict.

    String shorthand: ``"metricset:<name>.<path>"`` → MetricSourceDef(metricset=<name>, path=<path>)
    Structured: ``{metricset: <name>, path: <path>, [aggregate: ...], ...}``

    Old grammar ``"request:..."`` is rejected with a migration hint.
    """
    if isinstance(raw_source, str):
        s = raw_source.strip()
        # Reject old-grammar form loudly
        if _OLD_REQUEST_SOURCE_RE.match(s):
            raise ManagementPackValidationError(
                f"{parent_tag}: old-grammar source form 'request:...' is no longer "
                f"supported. Migrate to 'metricset:<metricset_name>.<field_path>'. "
                f"The metricset_name is the from_request value (or 'as:' alias) of "
                f"the metricSet that sources this metric. "
                f"See designs/synology-mp-v1.md §'Chaining grammar design'."
            )
        m = _METRICSET_SOURCE_RE.match(s)
        if not m:
            raise ManagementPackValidationError(
                f"{parent_tag}: source string must be 'metricset:<name>.<field>'; "
                f"got {s!r}"
            )
        return MetricSourceDef(metricset=m.group(1), path=m.group(2))

    if isinstance(raw_source, dict):
        return MetricSourceDef(
            metricset=str(raw_source.get("metricset", "") or "").strip(),
            path=str(raw_source.get("path", "") or "").strip(),
            aggregate=raw_source.get("aggregate"),
            extract=raw_source.get("extract"),
            compose=raw_source.get("compose"),
        )

    raise ManagementPackValidationError(
        f"{parent_tag}: source must be a string ('metricset:<name>.<path>') "
        f"or a mapping ({{metricset: <name>, path: <path>}}); "
        f"got {type(raw_source).__name__}"
    )


def _parse_metric(raw: dict, parent_tag: str) -> MetricDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each metric must be a mapping"
        )
    raw_source = raw.get("source")
    if raw_source is None:
        raise ManagementPackValidationError(
            f"{parent_tag}: metric '{raw.get('key', '')}': source is required"
        )
    source = _parse_metric_source(raw_source, f"{parent_tag}: metric '{raw.get('key', '')}'")
    return MetricDef(
        key=str(raw.get("key", "") or "").strip(),
        label=str(raw.get("label", "") or "").strip(),
        usage=str(raw.get("usage", "") or "").strip().upper(),
        type=str(raw.get("type", "") or "").strip().upper(),
        source=source,
        unit=str(raw.get("unit", "") or "").strip(),
        kpi=bool(raw.get("kpi", False)),
    )


def _parse_bind(raw: dict, parent_tag: str) -> BindDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each bind entry must be a mapping"
        )
    return BindDef(
        name=str(raw.get("name", "") or "").strip(),
        from_attribute=str(raw.get("from_attribute", "") or "").strip(),
    )


def _parse_metric_set(raw: dict, parent_tag: str) -> MetricSetDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each metricSet must be a mapping"
        )
    raw_bind = raw.get("bind") or []
    if not isinstance(raw_bind, list):
        raise ManagementPackValidationError(f"{parent_tag}: bind must be a list")
    bind = [_parse_bind(b, parent_tag) for b in raw_bind]

    raw_as = raw.get("as")
    return MetricSetDef(
        from_request=str(raw.get("from_request", "") or "").strip(),
        list_path=str(raw.get("list_path", "") or "").strip(),
        primary=bool(raw.get("primary", False)),
        chained_from=str(raw.get("chained_from")).strip() if raw.get("chained_from") else None,
        bind=bind,
        as_name=str(raw_as).strip() if raw_as else None,
    )


def _parse_login_request(raw: dict, parent_tag: str) -> LoginRequestDef:
    """Parse an auth.login or auth.logout block."""
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: must be a mapping"
        )
    raw_headers = raw.get("headers") or []
    if not isinstance(raw_headers, list):
        raw_headers = []
    return LoginRequestDef(
        method=str(raw.get("method", "GET") or "GET").strip().upper(),
        path=str(raw.get("path", "") or "").strip(),
        params=raw.get("params") or [],
        headers=list(raw_headers),
        body=raw.get("body"),
    )


def _parse_logout_request(raw: dict, parent_tag: str) -> LogoutRequestDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: must be a mapping"
        )
    raw_headers = raw.get("headers") or []
    if not isinstance(raw_headers, list):
        raw_headers = []
    return LogoutRequestDef(
        method=str(raw.get("method", "DELETE") or "DELETE").strip().upper(),
        path=str(raw.get("path", "") or "").strip(),
        params=raw.get("params") or [],
        headers=list(raw_headers),
        body=raw.get("body"),
    )


def _parse_extract_rule(raw: dict, parent_tag: str) -> ExtractRuleDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: auth.extract must be a mapping"
        )
    return ExtractRuleDef(
        location=str(raw.get("location", "HEADER") or "HEADER").strip().upper(),
        name=str(raw.get("name", "") or "").strip(),
        bind_to=str(raw.get("bind_to", "") or "").strip(),
    )


def _parse_inject_rule(raw: dict, parent_tag: str) -> InjectRuleDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each inject entry must be a mapping"
        )
    return InjectRuleDef(
        type=str(raw.get("type", "header") or "header").strip().lower(),
        name=str(raw.get("name", "") or "").strip(),
        value=str(raw.get("value", "") or "").strip(),
    )


def _parse_credential_field(raw: dict, parent_tag: str) -> CredentialFieldDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each credentials entry must be a mapping"
        )
    return CredentialFieldDef(
        key=str(raw.get("key", "") or "").strip(),
        label=str(raw.get("label", "") or "").strip(),
        sensitive=bool(raw.get("sensitive", False)),
    )


def _parse_identifier(raw: Any, parent_tag: str) -> "IdentifierDef":
    """Parse one identifier entry — string shorthand or structured dict.

    String shorthand: ``"foo"`` → IdentifierDef(key="foo", source=None)
    Structured:       ``{key: foo, source: "metricset:X.Y"}``
    """
    if isinstance(raw, str):
        key = raw.strip()
        if not key:
            raise ManagementPackValidationError(
                f"{parent_tag}: identifier string must not be empty"
            )
        return IdentifierDef(key=key, source=None, derive=None)

    if isinstance(raw, dict):
        key = str(raw.get("key", "") or "").strip()
        if not key:
            raise ManagementPackValidationError(
                f"{parent_tag}: identifier mapping requires a 'key' field"
            )
        raw_derive = raw.get("derive")
        if raw_derive is not None:
            # Parse it — we stash it so the validator can reject it with a
            # clear "reserved" message
            return IdentifierDef(
                key=key,
                source=str(raw.get("source", "") or "").strip() or None,
                derive=raw_derive,
            )
        return IdentifierDef(
            key=key,
            source=str(raw.get("source", "") or "").strip() or None,
            derive=None,
        )

    raise ManagementPackValidationError(
        f"{parent_tag}: identifier must be a string or a mapping; "
        f"got {type(raw).__name__}"
    )


def _parse_name_expression(raw: Any, parent_tag: str) -> "NameExpressionDef":
    """Parse a name_expression — string shorthand or structured dict.

    String shorthand: ``"hostname"`` → NameExpressionDef(parts=[NamePartDef(metric="hostname")])
    Structured:       ``{parts: [{metric: model}, {literal: " ("}, {metric: hostname}, {literal: ")"}]}``
    """
    if isinstance(raw, str):
        key = raw.strip()
        # Strip leading ${...} wrapper if present — bare key or ${key}
        bare_match = re.match(r"^\$\{([a-zA-Z0-9_]+)\}$", key)
        if bare_match:
            key = bare_match.group(1)
        return NameExpressionDef(parts=[NamePartDef(metric=key)])

    if isinstance(raw, dict):
        raw_parts = raw.get("parts")
        if raw_parts is None:
            raise ManagementPackValidationError(
                f"{parent_tag}: name_expression mapping must have a 'parts:' key"
            )
        if not isinstance(raw_parts, list):
            raise ManagementPackValidationError(
                f"{parent_tag}: name_expression.parts must be a list"
            )
        parts: List[NamePartDef] = []
        for i, p in enumerate(raw_parts):
            if not isinstance(p, dict):
                raise ManagementPackValidationError(
                    f"{parent_tag}: name_expression.parts[{i}] must be a mapping"
                )
            metric = p.get("metric")
            literal = p.get("literal")
            parts.append(NamePartDef(
                metric=str(metric).strip() if metric is not None else None,
                literal=str(literal) if literal is not None else None,
            ))
        return NameExpressionDef(parts=parts)

    raise ManagementPackValidationError(
        f"{parent_tag}: name_expression must be a string or a mapping with 'parts:'; "
        f"got {type(raw).__name__}"
    )


def _parse_world_identity(raw: Any, parent_tag: str) -> "WorldIdentityDef":
    """Parse an identity: block on a world object_type."""
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: identity must be a mapping "
            f"{{tier: <tier>, source: 'metricset:<name>.<path>'}}"
        )
    tier = str(raw.get("tier", "") or "").strip()
    if not tier:
        raise ManagementPackValidationError(
            f"{parent_tag}: identity.tier is required. "
            f"Valid values: {sorted(VALID_IDENTITY_TIER)}"
        )
    if tier not in VALID_IDENTITY_TIER:
        raise ManagementPackValidationError(
            f"{parent_tag}: identity.tier must be one of {sorted(VALID_IDENTITY_TIER)}; "
            f"got {tier!r}"
        )
    source = str(raw.get("source", "") or "").strip()
    if not source:
        raise ManagementPackValidationError(
            f"{parent_tag}: identity.source is required "
            f"(e.g. 'metricset:system_info.serial')"
        )
    return WorldIdentityDef(tier=tier, source=source)


def _parse_object_type(raw: dict, parent_tag: str) -> ObjectTypeDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each object_type must be a mapping"
        )
    ot_name = str(raw.get("name", "") or "").strip()
    ot_tag = f"{parent_tag}: object_type '{ot_name}'"

    # Reject events key immediately
    _reject_events_key(raw, ot_tag)

    # Reject old-grammar 'requests:' under object_type
    _reject_object_type_requests(raw, ot_tag)

    raw_key = raw.get("key")
    ot_key = str(raw_key).strip() if raw_key else _derive_object_key(ot_name)

    # Parse metricSets (Option C — required, replaces implicit requests)
    raw_metric_sets = raw.get("metricSets") or []
    if not isinstance(raw_metric_sets, list):
        raise ManagementPackValidationError(f"{ot_tag}: metricSets must be a list")
    metric_sets = [_parse_metric_set(ms, ot_tag) for ms in raw_metric_sets]

    raw_metrics = raw.get("metrics") or []
    if not isinstance(raw_metrics, list):
        raise ManagementPackValidationError(f"{ot_tag}: metrics must be a list")
    metrics = [_parse_metric(m, ot_tag) for m in raw_metrics]

    # Identifiers — Tier 3.3 structured form (shorthand or structured)
    raw_identifiers = raw.get("identifiers") or []
    if not isinstance(raw_identifiers, list):
        raise ManagementPackValidationError(f"{ot_tag}: identifiers must be a list")
    identifiers = [_parse_identifier(ident, ot_tag) for ident in raw_identifiers]

    # name_expression — Tier 3.3 structured form (shorthand string or parts dict)
    raw_name_expr = raw.get("name_expression")
    name_expression: Optional[NameExpressionDef] = None
    if raw_name_expr is not None:
        name_expression = _parse_name_expression(raw_name_expr, ot_tag)

    # identity — Tier 3.3 axis 7 (required for is_world, forbidden otherwise)
    raw_identity = raw.get("identity")
    identity: Optional[WorldIdentityDef] = None
    if raw_identity is not None:
        identity = _parse_world_identity(raw_identity, ot_tag)

    return ObjectTypeDef(
        name=ot_name,
        key=ot_key,
        type=str(raw.get("type", "INTERNAL") or "INTERNAL").strip().upper(),
        icon=str(raw.get("icon", "server.svg") or "server.svg").strip(),
        is_world=bool(raw.get("is_world", False)),
        identifiers=identifiers,
        name_expression=name_expression,
        identity=identity,
        metric_sets=metric_sets,
        metrics=metrics,
    )


def _parse_auth(raw: dict, parent_tag: str) -> AuthFlowDef:
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: auth must be a mapping"
        )

    # Detect and reject the old enum grammar immediately.
    if "type" in raw:
        raise ManagementPackValidationError(
            f"{parent_tag}: auth.type: enum form is retired. "
            f"Migrate to auth.preset with one of: "
            f"{', '.join(sorted(VALID_AUTH_PRESET))}. "
            f"See designs/synology-mp-v1.md §\"Framework-vs-Synology review "
            f"(2026-04-18)\" axis 1 for the flow grammar spec."
        )

    atag = f"{parent_tag}: auth"
    preset = str(raw.get("preset", "none") or "none").strip().lower()

    # credentials
    raw_creds = raw.get("credentials") or []
    if not isinstance(raw_creds, list):
        raise ManagementPackValidationError(f"{atag}: credentials must be a list")
    credentials = [_parse_credential_field(c, atag) for c in raw_creds]

    # login
    raw_login = raw.get("login")
    login = _parse_login_request(raw_login, f"{atag}: login") if isinstance(raw_login, dict) else None

    # extract
    raw_extract = raw.get("extract")
    extract = _parse_extract_rule(raw_extract, atag) if isinstance(raw_extract, dict) else None

    # inject
    raw_inject = raw.get("inject") or []
    if not isinstance(raw_inject, list):
        raise ManagementPackValidationError(f"{atag}: inject must be a list")
    inject = [_parse_inject_rule(r, atag) for r in raw_inject]

    # logout
    raw_logout = raw.get("logout")
    logout = _parse_logout_request(raw_logout, f"{atag}: logout") if isinstance(raw_logout, dict) else None

    return AuthFlowDef(
        preset=preset,
        credentials=credentials,
        login=login,
        extract=extract,
        inject=inject,
        logout=logout,
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

    # NEW: parse top-level requests block
    raw_requests = data.get("requests") or []
    if not isinstance(raw_requests, list):
        raise ManagementPackValidationError(f"{tag}: requests must be a list")
    requests = [_parse_request(r, tag) for r in raw_requests]

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
        # scope defaults to "field_match" for backwards-compat
        raw_scope = raw_rel.get("scope")
        scope = str(raw_scope).strip() if raw_scope else "field_match"
        relationships.append(RelationshipDef(
            parent=str(raw_rel.get("parent", "") or "").strip(),
            child=str(raw_rel.get("child", "") or "").strip(),
            scope=scope,
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
        requests=requests,
        object_types=object_types,
        relationships=relationships,
        mpb_events=mpb_events,
        content=raw_content,
        source_path=path,
    )
    mp.validate()
    return mp


def load_dir(directory: str | Path = "managementpacks") -> List[ManagementPackDef]:
    """Load all MP YAML files from a directory.

    Skip convention: files whose name contains ".reference." are ignored.
    This allows pre-Option-C YAMLs to coexist in the directory as reference
    material.  Example:
        managementpacks/synology_dsm.reference.yaml   ← skipped
        managementpacks/synology_dsm.yaml             ← loaded
    """
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[ManagementPackDef] = []
    seen: dict = {}
    for p in sorted(directory.rglob("*.y*ml")):
        # Skip reference files (pre-Option-C archive YAMLs)
        if ".reference." in p.name:
            continue
        mp = load_file(p)
        if mp.name in seen:
            raise ManagementPackValidationError(
                f"duplicate management pack name '{mp.name}' "
                f"in {p} and {seen[mp.name]}"
            )
        seen[mp.name] = p
        out.append(mp)
    return out
