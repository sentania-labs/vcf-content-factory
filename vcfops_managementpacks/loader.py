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
VALID_AUTH_PRESET = {"cookie_session", "bearer_token", "basic_auth", "http_header", "none"}
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

# Gap F: Detect JMESPath filter predicates in source paths.
# A predicate is any "[?" substring anywhere in the path.
_JMESPATH_FILTER_RE = re.compile(r"\[\?")

# Gap F: Detect JMESPath pipe-scalar suffix "| [0]" at end of path.
_JMESPATH_PIPE_SCALAR_RE = re.compile(r"\s*\|\s*\[0\]\s*$")

# ${chain.<name>} substitution in request params/path/body
_CHAIN_TOKEN_RE = re.compile(r"\$\{chain\.([a-zA-Z0-9_]+)\}")


# Derive adapter_kind from MP name: lowercase, replace non-alphanum with _
def _derive_adapter_kind(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return f"mpb_{slug}"


def derive_class_name_fragment(adapter_kind: str) -> str:
    """Derive the CamelCase class name fragment from adapter_kind.

    Strips the ``mpb_`` prefix, splits on underscores, and title-cases
    each part.  Example: ``mpb_unifi_integration`` → ``UnifiIntegration``.

    This auto-derivation is correct for most adapters, but acronym-heavy
    names (e.g. ``mpb_synology_nas`` → ``SynologyNas`` instead of
    ``SynologyNAS``) require an explicit ``adapter_class`` override in
    the YAML.
    """
    # Strip leading "mpb_"
    without_prefix = re.sub(r"^mpb_", "", adapter_kind)
    parts = without_prefix.split("_")
    return "".join(p.title() for p in parts if p)

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
    coerce: Optional[str] = None   # Gap D: optional "number" hint for string→NUMBER coercion


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
    # Optional Aria-native stitching declaration.  When set (together with
    # stitch_match_field), the renderer emits a full objectBinding block
    # (matchExpression + objectMatchExpression with originType: ARIA_OPS_METRIC)
    # to stitch this metricSet's rows onto a native Aria Ops resource kind.
    #
    # stitch_to         — Full Aria-native objectMatchExpression originId, in
    #                     the form "aria-<ADAPTER>-<KIND>-<METRIC_KEY>".
    #                     E.g. for Rubrik → VMware VM stitching:
    #                       "aria-VMWARE-VirtualMachine-VMEntityObjectID"
    #                     The originType on the objectMatchExpression is always
    #                     ARIA_OPS_METRIC (per the captured Rubrik pattern).
    # stitch_match_field — The response field label (relative to this metricSet's
    #                     listId) whose value matches the Aria-native identifier.
    #                     E.g. for Rubrik VMs this is "moid".  The matchExpression
    #                     originId composite becomes "<reqId>-<listId>-<field>".
    #
    # Both fields must be present or both absent — partial declaration is an
    # error (see _validate_object_binding_rules).
    #
    # Must be absent on scalar kinds (is_world/is_singleton) and may not be
    # combined with chained_from.
    # See context/mpb_object_binding_wire_format.md §3.5 and §5 rule 6.
    stitch_to: Optional[str] = None
    stitch_match_field: Optional[str] = None

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
    """One auth.extract binding — where to find one session value in the login response.

    Gap B (2026-04-30): AuthFlowDef.extract is now a List[ExtractRuleDef] so that
    multiple values can be captured from the same login response (e.g. TOKEN cookie
    AND x-csrf-token header from a UniFi classic-session login).

    Backward compatibility: the YAML author may write either a single mapping
    (dict — Synology-style) or a list of mappings.  The loader normalises both to
    a list before handing off to AuthFlowDef.  Single-entry lists are identical
    in wire output to the previous single-binding form.
    """
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

    Gap B (2026-04-30): ``extract`` is now ``Optional[List[ExtractRuleDef]]``.
    A single-mapping YAML form is parsed into a one-element list; a list-of-
    mappings form produces a multi-element list.  Validator requires the list to
    be non-empty for cookie_session.  Renderer iterates the list to emit
    multiple sessionVariables entries.
    """
    preset: str
    credentials: List[CredentialFieldDef] = field(default_factory=list)
    login: Optional[LoginRequestDef] = None
    extract: Optional[List[ExtractRuleDef]] = None   # Gap B: list of bindings
    inject: List[InjectRuleDef] = field(default_factory=list)
    logout: Optional[LogoutRequestDef] = None


@dataclass
class AriaOpsConf:
    """ARIA_OPS object type stitching configuration.

    When an object_type has type: ARIA_OPS, this block declares which existing
    VCF Ops resource kind to push metrics onto, and which metric on that kind
    is used to match rows from the API response.

    Fields:
      adapter_kind  — Aria Ops adapter kind for the target resource kind
                      (e.g. "VMWARE").
      resource_kind — Aria Ops resource kind to stitch onto
                      (e.g. "HostSystem", "VirtualMachine").
      bind_metric   — Metric key on the target Aria Ops resource kind whose
                      value matches the API response field declared in the
                      metricSet's stitch_match_field
                      (e.g. "VMEntityObjectID").

    Grammar rules (enforced by loader validation):
      - ARIA_OPS objects REQUIRE this block.
      - INTERNAL objects MUST NOT declare this block.
    """
    adapter_kind: str    # e.g. "VMWARE"
    resource_kind: str   # e.g. "HostSystem"
    bind_metric: str     # e.g. "VMEntityObjectID"


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
    is_singleton: bool = False            # one-per-adapter-instance named entity with identifiers
    name_expression: Optional["NameExpressionDef"] = None   # Tier 3.3 structured form
    identity: Optional["WorldIdentityDef"] = None           # Tier 3.3 axis 7 (required for is_world)
    aria_ops: Optional["AriaOpsConf"] = None                # ARIA_OPS stitching config (ARIA_OPS only)


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
    adapter_class: Optional[str] = None  # CamelCase fragment override (e.g. "SynologyNAS")
    source: Optional[SourceDef] = None
    requests: List[RequestDef] = field(default_factory=list)   # NEW: MP-scope requests
    object_types: List[ObjectTypeDef] = field(default_factory=list)
    relationships: List[RelationshipDef] = field(default_factory=list)
    mpb_events: List[MPBEventDef] = field(default_factory=list)
    content: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[Path] = None
    released: bool = False   # publish gate — True means include in /publish output

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

        # Guardrail: is_world and is_singleton are mutually exclusive.
        # is_world  → topology root, no identifiers, MPB-managed rollups only.
        # is_singleton → one-per-adapter named entity with identifiers and metrics.
        # Both true simultaneously is nonsensical and produces the rogue-World defect
        # (objects[5] in the failing Synology import — null name expression, empty
        # identifiers, empty metricSets).  Fail loudly rather than rendering garbage.
        if ot.is_world and ot.is_singleton:
            raise ManagementPackValidationError(
                f"{ot_tag}: is_world and is_singleton cannot both be true. "
                f"Use is_world: true for the adapter-instance topology root (no identifiers, "
                f"MPB-managed rollups). Use is_singleton: true for one-per-adapter named "
                f"entities that carry identifiers and metrics (e.g. a NAS unit)."
            )

        # Guardrail: is_world kinds are cross-instance anchors — empty stubs with no
        # per-adapter-instance identity.  Identifiers on a world kind are architecturally
        # wrong: with two adapter instances the MPB would create a single shared object
        # that collides on the identifier value (e.g. serial).  If you need a kind that
        # carries identifiers and metrics describing the device, use is_singleton: true.
        if ot.is_world and ot.identifiers:
            raise ManagementPackValidationError(
                f"{ot_tag}: `is_world: true` requires empty `identifiers` (world kinds "
                f"are cross-instance anchors with no per-adapter-instance identity). "
                f"For a one-per-adapter-instance named entity that carries identifiers "
                f"and metrics, use `is_singleton: true` instead. See "
                f"context/mp_chain_authoring.md §\"Singleton vs list\" and the "
                f"architecture decision in context/mpb_synology_pickup_2026_04_29.md."
            )

        # Guardrail: is_world kinds are navigation roots only — they must not carry
        # metricSets or metrics.  Metrics on a world kind belong to a singleton or list
        # kind that describes the per-adapter-instance device.
        if ot.is_world and (ot.metric_sets or ot.metrics):
            raise ManagementPackValidationError(
                f"{ot_tag}: `is_world: true` kinds are empty stubs (no metrics, no "
                f"metricSets — they exist only as navigation roots for fleet-level "
                f"aggregation). For a kind that holds metrics about the "
                f"adapter-instance-level device, use `is_singleton: true` instead. See "
                f"context/mp_chain_authoring.md §\"Singleton vs list\" and the "
                f"architecture decision in context/mpb_synology_pickup_2026_04_29.md."
            )

        # ARIA_OPS-specific validation block.
        # ARIA_OPS objects stitch metrics onto existing Aria Ops resource instances;
        # they do not define their own identity in the adapter.
        if ot.type == "ARIA_OPS":
            # Require aria_ops: block
            if ot.aria_ops is None:
                raise ManagementPackValidationError(
                    f"{ot_tag}: type ARIA_OPS requires an 'aria_ops:' block with "
                    f"adapter_kind, resource_kind, and bind_metric fields."
                )
            _validate_aria_ops_conf(ot_tag, ot.aria_ops)
            # ARIA_OPS objects must not declare identifiers (identity is on the target object)
            if ot.identifiers:
                raise ManagementPackValidationError(
                    f"{ot_tag}: type ARIA_OPS must not declare 'identifiers:'. "
                    f"ARIA_OPS objects push metrics onto existing Aria Ops resource "
                    f"instances; identity comes from the target resource kind. "
                    f"Remove 'identifiers:' or change type to INTERNAL."
                )
            # ARIA_OPS objects must not declare name_expression
            if ot.name_expression is not None:
                raise ManagementPackValidationError(
                    f"{ot_tag}: type ARIA_OPS must not declare 'name_expression:'. "
                    f"ARIA_OPS objects do not own a name — they stitch onto an "
                    f"existing named resource. Remove 'name_expression:'."
                )
            # ARIA_OPS objects must not be world or singleton kinds
            if ot.is_world or ot.is_singleton:
                kind_label = "is_world" if ot.is_world else "is_singleton"
                raise ManagementPackValidationError(
                    f"{ot_tag}: type ARIA_OPS must not set '{kind_label}: true'. "
                    f"ARIA_OPS objects are always list objects (one row per matched "
                    f"Aria Ops resource instance). Remove '{kind_label}: true'."
                )

        # Pure world kinds are topology roots and carry no identifiers by design.
        # ARIA_OPS objects also omit identifiers (validated above with clearer message).
        if not ot.is_world and not ot.identifiers and ot.type != "ARIA_OPS":
            raise ManagementPackValidationError(
                f"{ot_tag}: at least one identifier is required"
            )
        # Validate each IdentifierDef
        for ident in ot.identifiers:
            _validate_identifier(ot_tag, ident)
        if not ot.is_world:
            # Non-world object types (including is_singleton) must have at least one
            # metricSet and one metric.
            if not ot.metric_sets:
                raise ManagementPackValidationError(
                    f"{ot_tag}: at least one metricSet is required"
                )
            if not ot.metrics:
                raise ManagementPackValidationError(
                    f"{ot_tag}: at least one metric or property is required"
                )

        # Guardrail: is_singleton must have a name_expression.
        # A singleton with no nameMetricExpression renders as null, which the MPB
        # importer rejects on non-list objects.  This is the same defect as
        # the rogue World stub in the failing Synology import.
        if ot.is_singleton and ot.name_expression is None:
            raise ManagementPackValidationError(
                f"{ot_tag}: is_singleton: true objects require a 'name_expression:'. "
                f"A singleton with no nameMetricExpression renders null, which MPB rejects "
                f"at import time.  Add 'name_expression: <metric_key>' (shorthand) or "
                f"the structured 'name_expression: {{parts: [...]}}' form."
            )

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
            # Non-world objects (both is_singleton and plain list) must NOT declare identity.
            # identity: is is_world-only because it declares the adapter-instance anchor tier.
            if ot.identity is not None:
                raise ManagementPackValidationError(
                    f"{ot_tag}: only is_world: true objects may declare 'identity:'. "
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

        # is_singleton objects consume scalar responses — same rule as is_world:
        # list_path must be empty, and primary: true is disallowed.
        # Pass is_world=True here to reuse the same metricSet lint rules.
        is_scalar = ot.is_world or ot.is_singleton

        # Validate each metricSet
        for i, ms in enumerate(ot.metric_sets):
            _validate_metric_set(ot_tag, i, ms, request_names, ms_local_names,
                                 is_world=is_scalar)

        # objectBinding guardrails — validate stitch_to/chaining rules
        _validate_object_binding_rules(ot_tag, ot)

        # Primary-validator (reuses is_world semantics for is_singleton)
        _validate_primary(ot_tag, ot)

        # Chain-graph walker (cycle detection + orphan detection)
        _validate_chain_graph(ot_tag, ot, mp_request_names=request_names)

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

    # World-kind cardinality: 0 or 1 is valid; 2+ is nonsense.
    #
    # world_count == 0: valid — the MP is fully self-contained at the
    #   adapter-instance level (e.g. Synology NAS where Diskstation is
    #   is_singleton: true and serves as the per-adapter root).  VCF Ops
    #   auto-generates the world-aggregate tier in the .pak describe.xml;
    #   no is_world stub is required.  To enable fleet-level cross-instance
    #   aggregation later, add an empty is_world: true stub.
    #
    # world_count == 1: valid — one world kind, the standard model.
    #
    # world_count >= 2: hard error — only one world kind is meaningful.
    #   Multiple world kinds produce colliding topology roots.
    if mp.object_types and world_count >= 2:
        raise ManagementPackValidationError(
            f"{tag}: at most one object_type may have is_world: true; "
            f"found {world_count}. Multiple world kinds produce colliding "
            f"topology roots and are not supported."
        )

    if mp.object_types and world_count == 0:
        import logging as _logging
        _logging.getLogger(__name__).info(
            "%s: no is_world: true kind declared. This is valid — the MP is "
            "fully self-contained at the adapter-instance level. To enable "
            "fleet-level cross-instance aggregation later, add an empty "
            "is_world: true stub.",
            tag,
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

    # -----------------------------------------------------------------------
    # Cross-MP guardrail: dangling ${chain.X} requests
    #
    # If a top-level request contains ${chain.<name>} tokens it must be
    # consumed as a chained metricSet (chained_from is set) on at least one
    # object_type.  A request with chain tokens but no chained consumer is a
    # dangling chain — the importer sees ${requestParameters.X} with no
    # chainingSettings block and rejects the design.
    #
    # Context: context/mpb_synology_import_diff_2026_04_29.md §3 (defect #3).
    # -----------------------------------------------------------------------
    chained_requests: set = set()
    for ot in mp.object_types:
        for ms in ot.metric_sets:
            if ms.chained_from is not None:
                chained_requests.add(ms.from_request)

    for req in mp.requests:
        # Collect all ${chain.*} tokens in this request's templates
        chain_tokens_in_req: set = set()
        for part in _collect_request_template_parts(req):
            for m in _CHAIN_TOKEN_RE.finditer(part):
                chain_tokens_in_req.add(m.group(1))

        if chain_tokens_in_req and req.name not in chained_requests:
            raise ManagementPackValidationError(
                f"{tag}: request '{req.name}' contains ${{chain.*}} token(s) "
                f"{sorted(chain_tokens_in_req)!r} but is never consumed as a "
                f"chained metricSet (chained_from) on any object_type. "
                f"Either declare 'chained_from: <parent_metricset_name>' on the "
                f"metricSet that uses this request, or remove the ${{chain.*}} "
                f"token from the request params/path/body. "
                f"A request with ${{chain.*}} tokens but no chainingSettings block "
                f"causes MPB import to reject the design with 'unknown error'."
            )

    # -----------------------------------------------------------------------
    # Cross-MP guardrail: SINGLE_SELECTION config defaultValue must be in options
    #
    # The MPB importer validates SINGLE_SELECTION defaults against the options
    # list at import time.  A mismatch (e.g. case difference: "WARNING" vs
    # "Warning") causes a hard import rejection.
    # Context: context/mpb_synology_import_diff_2026_04_29.md §7 (defect #7).
    # -----------------------------------------------------------------------
    if mp.source:
        for cf in mp.source.config_fields:
            if cf.type == "SINGLE_SELECTION" and cf.default:
                # config_fields options not stored on ConfigFieldDef — this check
                # is for future ConfigFieldDef extensions.  Currently config_fields
                # in YAML have no 'options' list (they're free-form string defaults).
                # The standard config fields are hardcoded in render.py and audited
                # separately.  Pass here; extend when ConfigFieldDef gains options.
                pass


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

    # World and singleton objects must have an empty list_path on every metricSet.
    # Both kinds consume the whole response root as scalar context ("base" DML).
    # A non-empty list_path on either kind produces a wildcard DML instead of
    # the required "base" DML, causing all metrics to be silently unresolvable
    # at collection time (2026-04-21 QA audit).
    # Emitted as a DeprecationWarning (matching the .* lint above) rather than
    # a hard error for backward-compat; new YAMLs must not use this form.
    if is_world and lp.strip():
        _warnings.warn(
            f"{mstag} (from_request: '{ms.from_request}'): "
            f"list_path should be empty ('') on is_world: true / is_singleton: true objects. "
            f"Scalar kinds consume the whole response root as scalar "
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
        # chained_from must name a sibling metricSet local_name OR a top-level request
        # (cross-object-type chain root — Gap 2, 2026-05-07).
        # A "chain root" is a top-level request that fires once and propagates its
        # per-row attributes (e.g. site IDs) to child requests on other object types.
        # It is not consumed as a from_request on any metricSet.
        is_chain_root_ref = (ms.chained_from not in sibling_names
                             and ms.chained_from in mp_request_names)
        if ms.chained_from not in sibling_names and not is_chain_root_ref:
            raise ManagementPackValidationError(
                f"{mstag}: chained_from '{ms.chained_from}' does not match any "
                f"sibling metricSet local name (known: {sorted(sibling_names)}) "
                f"or top-level request name (known: {sorted(mp_request_names)}). "
                f"chained_from must reference a sibling metricSet's from_request "
                f"(or its 'as:' alias if set) or a top-level chain-root request."
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
    """Validate primary metricSet rule per object kind.

    Scalar kinds (is_world or is_singleton): primary: true is disallowed on every
    metricSet.  Scalar objects have no list iteration — the concept of "which request
    defines list membership" does not apply.  All metricSets fire in parallel once
    per collection cycle and merge onto the single object instance.

    List kinds (default, neither is_world nor is_singleton): exactly one primary
    metricSet required.  The primary metricSet's request defines list membership
    (one object instance per response row); secondary metricSets are chained.
    """
    primary_count = sum(1 for ms in ot.metric_sets if ms.primary)

    if ot.is_world or ot.is_singleton:
        # Scalar kind: primary must be absent/false on all metricSets.
        if primary_count > 0:
            kind_label = "is_world" if ot.is_world else "is_singleton"
            raise ManagementPackValidationError(
                f"{ot_tag}: {kind_label} objects must not declare 'primary: true' "
                f"on any metricSet (scalar kinds don't define list membership); "
                f"found {primary_count} metricSet(s) with primary: true"
            )
    else:
        # List object: exactly one primary required
        if primary_count == 0:
            raise ManagementPackValidationError(
                f"{ot_tag}: list objects (is_world: false, is_singleton: false) require "
                f"exactly one metricSet with 'primary: true'; found zero"
            )
        if primary_count > 1:
            raise ManagementPackValidationError(
                f"{ot_tag}: list objects (is_world: false, is_singleton: false) must have "
                f"exactly one metricSet with 'primary: true'; found {primary_count}"
            )


def _validate_aria_ops_conf(ot_tag: str, conf: "AriaOpsConf") -> None:
    """Validate an AriaOpsConf block."""
    if not conf.adapter_kind or not conf.adapter_kind.strip():
        raise ManagementPackValidationError(
            f"{ot_tag}: aria_ops.adapter_kind is required (e.g. 'VMWARE')"
        )
    if not conf.resource_kind or not conf.resource_kind.strip():
        raise ManagementPackValidationError(
            f"{ot_tag}: aria_ops.resource_kind is required (e.g. 'HostSystem')"
        )
    if not conf.bind_metric or not conf.bind_metric.strip():
        raise ManagementPackValidationError(
            f"{ot_tag}: aria_ops.bind_metric is required (e.g. 'VMEntityObjectID')"
        )


def _validate_object_binding_rules(ot_tag: str, ot: ObjectTypeDef) -> None:
    """Validate objectBinding-related constraints on metricSets.

    These rules encode the empirical findings from the 2026-04-29 MPB
    objectBinding investigation on vcf-lab-operations-devel.
    See context/mpb_object_binding_wire_format.md §5 for the rationale
    behind every rule here.

    The YAML grammar exposes objectBinding only via the 'stitch_to' knob
    (§5 rule 6 — author intent must be explicit).  The renderer emits:
      - objectBinding: null   for singletons, scalar kinds, and chain-parents
      - objectBinding: <§10.2 cross-metricSet ATTRIBUTE shape>  for chained secondaries
      - objectBinding: <stitch shape>  when stitch_to is declared
    Chained secondaries MUST carry a non-null objectBinding to satisfy the
    MPB verify-time per-resource null-count rule (§8.1 of
    context/mpb_object_binding_wire_format.md).  The renderer enforces this
    with a RuntimeError assertion; the loader validates the YAML preconditions
    (chained_from requires at least one bind entry with from_attribute).

    For ARIA_OPS object types the binding is declared differently:
      - stitch_match_field is REQUIRED on the primary metricSet (which API field
        to match against the ariaOpsConf bind_metric on the target resource).
      - stitch_to is FORBIDDEN (the binding target is declared in aria_ops.bind_metric).
    """
    is_scalar = ot.is_world or ot.is_singleton
    is_aria_ops = ot.type == "ARIA_OPS"
    doc_ref = "context/mpb_object_binding_wire_format.md"

    for i, ms in enumerate(ot.metric_sets):
        mstag = f"{ot_tag}: metricSets[{i}] ('{ms.local_name}')"

        # ARIA_OPS-specific metricSet rules.
        if is_aria_ops:
            # stitch_to is forbidden for ARIA_OPS — binding target is in aria_ops:
            if ms.stitch_to is not None:
                raise ManagementPackValidationError(
                    f"{mstag}: ARIA_OPS object types must not declare 'stitch_to'. "
                    f"For ARIA_OPS objects the binding target is declared in the "
                    f"'aria_ops.bind_metric' field on the object type. "
                    f"Remove 'stitch_to' from this metricSet."
                )
            # The primary metricSet must declare stitch_match_field
            if ms.primary and (not ms.stitch_match_field or not ms.stitch_match_field.strip()):
                raise ManagementPackValidationError(
                    f"{mstag}: the primary metricSet on an ARIA_OPS object type "
                    f"requires 'stitch_match_field'. "
                    f"Set 'stitch_match_field' to the API response field whose value "
                    f"matches the aria_ops.bind_metric on the target resource kind "
                    f"(e.g. 'host_moid' for VMEntityObjectID matching). "
                    f"See {doc_ref} §3.5."
                )
            # stitch_match_field without primary is an error for ARIA_OPS
            if not ms.primary and ms.stitch_match_field is not None:
                raise ManagementPackValidationError(
                    f"{mstag}: 'stitch_match_field' must only be declared on the "
                    f"primary metricSet of an ARIA_OPS object type. "
                    f"Only the primary metricSet drives the object binding. "
                    f"Remove 'stitch_match_field' from this non-primary metricSet."
                )
            continue  # ARIA_OPS metricSets skip the remaining INTERNAL rules

        if ms.stitch_to is not None:
            # Rule 1: scalar kinds (is_world/is_singleton) must not declare stitch_to.
            # Stitching is a list-object concept — it correlates per-row data with
            # native Aria resource instances.  Scalar kinds produce one object per
            # adapter instance; there is nothing to stitch.
            # §5 rule 1 and rule 6 of the reference doc.
            if is_scalar:
                kind_label = "is_world" if ot.is_world else "is_singleton"
                raise ManagementPackValidationError(
                    f"{mstag}: 'stitch_to' must not be declared on {kind_label} "
                    f"objects.  Stitching (objectMatchExpression: ARIA_OPS_METRIC) "
                    f"correlates list-object rows with native Aria resource instances "
                    f"and has no meaning on scalar kinds that produce one object per "
                    f"adapter instance.  Remove 'stitch_to' or change the object kind.  "
                    f"See {doc_ref} §5 rules 1 and 6."
                )

            # Rule 2: stitch_to must be a non-empty string and stitch_match_field
            # must be provided alongside it.  Both fields are required together
            # because the renderer needs both to build the two-expression stitching
            # objectBinding (matchExpression for the source field, objectMatchExpression
            # for the Aria-native identifier).
            if not ms.stitch_to.strip():
                raise ManagementPackValidationError(
                    f"{mstag}: 'stitch_to' must not be blank.  Provide the "
                    f"Aria-native resource kind path to stitch onto "
                    f"(e.g. 'vmware/VirtualMachine').  "
                    f"See {doc_ref} §3.5."
                )
            if not ms.stitch_match_field or not ms.stitch_match_field.strip():
                raise ManagementPackValidationError(
                    f"{mstag}: 'stitch_to' requires a companion 'stitch_match_field'.  "
                    f"Set 'stitch_match_field' to the response field label whose value "
                    f"matches the Aria-native identifier (e.g. 'moid' for VMware VMs).  "
                    f"See {doc_ref} §3.5."
                )

            # Rule 3: stitch_to and chained_from cannot be combined on the same
            # metricSet.  Chained secondary metricSets rely on chainingSettings for
            # row-binding; adding a stitching objectBinding on the same metricSet
            # produces conflicting binding semantics and has no captured working
            # precedent.  If you need both chaining and stitching, split them into
            # separate metricSets.
            # §5 rule 6 cross-references §3.3 (chaining) and §3.5 (stitching).
            if ms.chained_from is not None:
                raise ManagementPackValidationError(
                    f"{mstag}: 'stitch_to' and 'chained_from' cannot both be "
                    f"declared on the same metricSet.  Chained secondary metricSets "
                    f"use chainingSettings for row-binding; stitching objectBinding "
                    f"is for correlating primary list rows with native Aria objects.  "
                    f"Split into separate metricSets if both are needed.  "
                    f"See {doc_ref} §3.3 and §3.5."
                )

        # Rule 4a (companion check): stitch_match_field without stitch_to is an error.
        if ms.stitch_to is None and ms.stitch_match_field is not None:
            raise ManagementPackValidationError(
                f"{mstag}: 'stitch_match_field' declared without 'stitch_to'.  "
                f"Both fields must be present together or both absent.  "
                f"Add 'stitch_to: <aria_resource_kind>' or remove 'stitch_match_field'.  "
                f"See {doc_ref} §3.5."
            )

        # Rule 5: non-primary metricSets on list objects must declare chained_from
        # (unless they are a stitching primary, identified by stitch_to).
        # A secondary metricSet without chained_from and without stitch_to has
        # no declared binding mechanism — the renderer emits objectBinding: null
        # and the request has no chainingSettings, so the runtime has no row-binding.
        # (Primary metricSets, stitching metricSets, and scalar metricSets are exempt.)
        # §5 rule 3 of the reference doc.
        if not is_scalar and not ms.primary and ms.chained_from is None and ms.stitch_to is None:
            raise ManagementPackValidationError(
                f"{mstag}: non-primary metricSet on a list object must declare "
                f"either 'chained_from: <primary_metricset_name>' (for a chained "
                f"secondary) or 'primary: true' (for a primary).  Without one of "
                f"these, the renderer emits objectBinding: null and the request has "
                f"no chainingSettings, leaving the runtime with no row-binding "
                f"mechanism.  See {doc_ref} §5 rule 3."
            )


def _validate_chain_graph(
    ot_tag: str,
    ot: ObjectTypeDef,
    mp_request_names: Optional[Dict[str, int]] = None,
) -> None:
    """Detect cycles and orphan chains in the metricSet chained_from graph.

    Gap 2 (2026-05-07): cross-object-type chain roots are allowed.
    A chained_from value that names a top-level request (chain root) instead
    of a sibling metricSet is valid and skipped in orphan detection.
    """
    # Build adjacency: local_name -> chained_from (or None)
    local_names = {ms.local_name for ms in ot.metric_sets}
    mp_req_names = mp_request_names or {}

    # Detect orphan chains (chained_from points at a non-existent sibling)
    # Exception: cross-type chain roots (top-level request, not a sibling metricSet).
    for ms in ot.metric_sets:
        if ms.chained_from is not None and ms.chained_from not in local_names:
            if ms.chained_from in mp_req_names:
                # Cross-type chain root reference — valid; skip orphan check.
                continue
            raise ManagementPackValidationError(
                f"{ot_tag}: metricSet '{ms.local_name}' has chained_from "
                f"'{ms.chained_from}' which is not a sibling metricSet or a "
                f"top-level chain-root request. "
                f"Cross-object-type chains require the target to be a top-level "
                f"request with no ${{chain.*}} tokens of its own."
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
    request's params/path/body/headers has a matching bind entry on this
    metricSet OR on any ancestor metricSet in the chain hierarchy.

    MPB's requestParameters namespace is cumulative across multi-hop chains:
    a token bound on a grandparent is already resolved when the grandchild
    fires, so grandchild requests may legitimately reference ${chain.<name>}
    tokens that are only bound on an ancestor.

    Also ensures that requests with ${chain.*} tokens are consumed as a
    chained metricSet on at least one object_type (within this object_type's
    metricSets).
    """
    request_by_name: Dict[str, RequestDef] = {r.name: r for r in mp_requests}

    # Build a lookup from local_name -> MetricSetDef for ancestor walks.
    ms_by_local_name: Dict[str, MetricSetDef] = {
        ms.local_name: ms for ms in ot.metric_sets
    }

    def _ancestor_bind_names(start_ms: MetricSetDef) -> set:
        """Return the union of bind.name values from start_ms and all its ancestors."""
        names: set = set()
        current: Optional[MetricSetDef] = start_ms
        seen: set = set()  # cycle guard (cycles are caught by _validate_chain_graph)
        while current is not None:
            if current.local_name in seen:
                break
            seen.add(current.local_name)
            for b in current.bind:
                names.add(b.name)
            parent_ref = current.chained_from
            if parent_ref is None:
                break
            # parent_ref names either a sibling metricSet (local_name) or a
            # top-level chain-root request.  Chain roots have no bind entries
            # of their own in this namespace, so stop walking there.
            current = ms_by_local_name.get(parent_ref)
        return names

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
            # anywhere in the ancestor chain (MPB propagates requestParameters
            # cumulatively, so a token bound on a grandparent is visible here).
            all_ancestor_bind_names = _ancestor_bind_names(ms)
            missing = chain_tokens_in_req - all_ancestor_bind_names
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
    elif preset == "http_header":
        _validate_auth_http_header(atag, auth)
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


def _validate_auth_http_header(tag: str, auth: AuthFlowDef) -> None:
    """Preset 'http_header': static API-key header injection; no session flow.

    Gap 1 (2026-05-07): stateless header-based auth (e.g. X-API-Key).
    Wire: credentialType TOKEN, no sessionSettings.  The inject[] rules
    render into globalHeaders alongside Content-Type.

    Constraints:
      - At least one credential field required (the API key).
      - At least one inject rule required (the header to inject).
      - No login, extract, or logout blocks allowed.
    """
    if not auth.credentials:
        raise ManagementPackValidationError(
            f"{tag}: preset 'http_header' requires at least one credential field"
        )
    for block, name in [(auth.login, "login"), (auth.extract, "extract"),
                        (auth.logout, "logout")]:
        if block is not None:
            raise ManagementPackValidationError(
                f"{tag}: preset 'http_header' must not declare '{name}' "
                f"(http_header is stateless — no session flow)"
            )
    if not auth.inject:
        raise ManagementPackValidationError(
            f"{tag}: preset 'http_header' requires at least one 'inject' rule "
            f"(the header(s) to add to every request)"
        )
    _validate_inject_rules(tag, auth.inject)


def _validate_auth_cookie_session(tag: str, auth: AuthFlowDef) -> None:
    """Preset 'cookie_session': all blocks required.

    Gap B (2026-04-30): auth.extract is now List[ExtractRuleDef].  Each
    binding in the list is validated individually.  The list must not be
    empty (cookie_session requires at least one session variable).
    """
    if not auth.credentials:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires credentials"
        )
    if auth.login is None:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires a 'login' block"
        )
    if not auth.extract:
        raise ManagementPackValidationError(
            f"{tag}: preset 'cookie_session' requires an 'extract' block "
            f"(single mapping or non-empty list of mappings)"
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

    # Validate each extract binding.
    bind_to_keys: List[str] = []
    for i, ex in enumerate(auth.extract):
        etag = f"{tag}: extract[{i}]"
        if ex.location not in ("HEADER", "BODY"):
            raise ManagementPackValidationError(
                f"{etag}: location must be HEADER or BODY; got {ex.location!r}"
            )
        if not ex.name or not ex.name.strip():
            raise ManagementPackValidationError(
                f"{etag}: name is required (the header name or JSON path to extract)"
            )
        if not ex.bind_to or not ex.bind_to.strip():
            raise ManagementPackValidationError(
                f"{etag}: bind_to is required (e.g. 'session.set_cookie')"
            )
        if not ex.bind_to.startswith("session."):
            raise ManagementPackValidationError(
                f"{etag}: bind_to must start with 'session.' (got {ex.bind_to!r})"
            )
        sk = ex.session_key
        if sk in bind_to_keys:
            raise ManagementPackValidationError(
                f"{etag}: duplicate bind_to session key '{sk}' — each extract "
                f"binding must bind to a distinct session variable"
            )
        bind_to_keys.append(sk)

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
    # Gap B: auth.extract is now List[ExtractRuleDef]; collect all bound keys.
    if auth.extract:
        for ex in auth.extract:
            declared_session_keys.add(ex.session_key)

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

    Gap F (2026-04-30): source paths that contain JMESPath filter predicates
    ``[?field=='value']`` are valid.  The JMESPath expression (including the
    optional ``| [0]`` pipe-scalar suffix) is validated for syntax using the
    jmespath library.  Render-time: the full expression is emitted verbatim as
    the attribute label/key; the MPB runtime evaluates it at collection time.
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
    # Gap F: validate JMESPath filter predicates if present.
    if _JMESPATH_FILTER_RE.search(src.path):
        _validate_jmespath_path(tag, src.path)
    if src.metricset not in ms_names:
        raise ManagementPackValidationError(
            f"{tag}: source references unknown metricSet '{src.metricset}' "
            f"(known metricSet names on this object_type: {sorted(ms_names)}). "
            f"The name is the from_request value of the metricSet (or its 'as:' alias)."
        )


def _validate_jmespath_path(tag: str, path: str) -> None:
    """Validate a JMESPath expression in a metric source path.

    Gap F (2026-04-30): called when a source path contains '[?' filter
    predicate syntax.  Uses the jmespath library to catch malformed
    expressions at validate time (before the render step).

    The full path is validated as a JMESPath expression.  The 'metricset:X.'
    prefix is already stripped at this point — only the field_path is passed.

    Supported predicate forms (equality and logical conjunctions):
      [?subsystem=='wan']
      [?radio=='ng']
      [?name=='CPU']
      [?subsystem=='wan' && status=='active']   # multi-condition

    Hyphenated field names outside predicates (e.g. 'tx_bytes-r') are valid
    UniFi API field names.  JMESPath strict syntax treats '-' as subtraction,
    so the validator normalises hyphens in identifier positions (between
    alphanumerics/underscores) to underscores before re-trying compilation.
    This avoids false failures while still catching real predicate errors.

    Raises ManagementPackValidationError with the metric tag + path + parse
    error if jmespath cannot compile the expression.
    """
    try:
        import jmespath  # soft dependency; installed alongside package
    except ImportError:
        # jmespath not installed — skip validation with a warning.
        import warnings
        warnings.warn(
            f"{tag}: jmespath library not installed — cannot validate filter "
            f"predicate syntax in source path {path!r}. "
            f"Install with: pip install jmespath",
            RuntimeWarning,
            stacklevel=4,
        )
        return

    # Strategy: try full path first; if it fails because of hyphens in
    # identifier positions (not inside [?...] blocks), normalise hyphens
    # to underscores outside predicates and retry.  This lets us catch real
    # predicate errors without rejecting valid hyphenated API field names.
    def _try_compile(expr: str) -> Optional[str]:
        """Return error string if compilation fails, else None."""
        try:
            jmespath.compile(expr)
            return None
        except Exception as exc:
            return str(exc)

    err = _try_compile(path)
    if err is None:
        return

    # Normalise hyphens outside predicates and retry.
    def _normalize_hyphens(s: str) -> str:
        """Replace word-internal hyphens (not inside [?...]) with underscores."""
        result: List[str] = []
        i = 0
        while i < len(s):
            if s[i:i+2] == "[?":
                # Skip ahead past the predicate block, preserving it verbatim.
                end = s.find("]", i + 2)
                if end == -1:
                    result.append(s[i:])
                    break
                result.append(s[i:end + 1])
                i = end + 1
            elif (s[i] == "-"
                  and i > 0 and i < len(s) - 1
                  and (s[i - 1].isalnum() or s[i - 1] == "_")
                  and (s[i + 1].isalnum() or s[i + 1] == "_")):
                result.append("_")
                i += 1
            else:
                result.append(s[i])
                i += 1
        return "".join(result)

    normalized = _normalize_hyphens(path)
    if normalized != path:
        err2 = _try_compile(normalized)
        if err2 is None:
            return   # Valid once hyphenated identifiers are normalised.
        err = err2   # Report the cleaner error from the normalised form.

    raise ManagementPackValidationError(
        f"{tag}: source path {path!r} contains a JMESPath filter predicate "
        f"that failed to parse: {err}. "
        f"Expected forms: [?field=='value'], [?field=='x'].subfield | [0]. "
        f"Check the predicate syntax — equality comparison uses == (double equals), "
        f"logical AND is &&, logical OR is ||."
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
    # Gap D: validate coerce hint.
    # coerce: number — tells the renderer (and documents to the author) that the
    # source field is a string that must be parsed as a number at collection time.
    # The MPB runtime performs the coercion when dataType is NUMBER; this hint is
    # a documentation signal only (no wire format change).
    if m.coerce is not None:
        if m.coerce.strip().lower() != "number":
            raise ManagementPackValidationError(
                f"{mtag}: coerce must be 'number' (only supported value); "
                f"got {m.coerce!r}"
            )
        if m.type != "NUMBER":
            raise ManagementPackValidationError(
                f"{mtag}: coerce: number requires type: NUMBER; "
                f"got type {m.type!r}. Set type: NUMBER on this metric."
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
    raw_coerce = raw.get("coerce")
    coerce = str(raw_coerce).strip().lower() if raw_coerce is not None else None
    return MetricDef(
        key=str(raw.get("key", "") or "").strip(),
        label=str(raw.get("label", "") or "").strip(),
        usage=str(raw.get("usage", "") or "").strip().upper(),
        type=str(raw.get("type", "") or "").strip().upper(),
        source=source,
        unit=str(raw.get("unit", "") or "").strip(),
        kpi=bool(raw.get("kpi", False)),
        coerce=coerce,   # Gap D: optional "number" coerce hint
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
    raw_stitch = raw.get("stitch_to")
    raw_stitch_field = raw.get("stitch_match_field")
    return MetricSetDef(
        from_request=str(raw.get("from_request", "") or "").strip(),
        list_path=str(raw.get("list_path", "") or "").strip(),
        primary=bool(raw.get("primary", False)),
        chained_from=str(raw.get("chained_from")).strip() if raw.get("chained_from") else None,
        bind=bind,
        as_name=str(raw_as).strip() if raw_as else None,
        stitch_to=str(raw_stitch).strip() if raw_stitch else None,
        stitch_match_field=str(raw_stitch_field).strip() if raw_stitch_field else None,
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
    """Parse one extract binding from a mapping.

    Gap B (2026-04-30): called for each element of a list, or once for a
    single-mapping form.  Callers normalise both forms to a list before
    storing on AuthFlowDef.extract.
    """
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: each auth.extract entry must be a mapping"
        )
    return ExtractRuleDef(
        location=str(raw.get("location", "HEADER") or "HEADER").strip().upper(),
        name=str(raw.get("name", "") or "").strip(),
        bind_to=str(raw.get("bind_to", "") or "").strip(),
    )


def _parse_extract_block(raw_extract: Any, atag: str) -> Optional[List[ExtractRuleDef]]:
    """Parse auth.extract — either a single mapping or a list of mappings.

    Gap B (2026-04-30): both forms normalise to List[ExtractRuleDef].

    Single mapping (Synology-style — backward compatible):
      extract:
        location: HEADER
        name: Set-Cookie
        bind_to: session.set_cookie

    List of mappings (UniFi-style — new):
      extract:
        - location: HEADER
          name: Set-Cookie
          bind_to: session.token
        - location: HEADER
          name: x-csrf-token
          bind_to: session.csrf_token

    Returns None if raw_extract is None.
    Returns a non-empty list otherwise (single-mapping → one-element list).
    """
    if raw_extract is None:
        return None
    if isinstance(raw_extract, dict):
        # Single-mapping form: wrap in list for uniform processing.
        return [_parse_extract_rule(raw_extract, atag)]
    if isinstance(raw_extract, list):
        if not raw_extract:
            raise ManagementPackValidationError(
                f"{atag}: auth.extract list must not be empty"
            )
        return [_parse_extract_rule(entry, atag) for entry in raw_extract]
    raise ManagementPackValidationError(
        f"{atag}: auth.extract must be a mapping or a list of mappings; "
        f"got {type(raw_extract).__name__}"
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

    # aria_ops — ARIA_OPS stitching configuration (ARIA_OPS only)
    raw_aria_ops = raw.get("aria_ops")
    aria_ops: Optional[AriaOpsConf] = None
    if raw_aria_ops is not None:
        aria_ops = _parse_aria_ops_conf(raw_aria_ops, ot_tag)

    return ObjectTypeDef(
        name=ot_name,
        key=ot_key,
        type=str(raw.get("type", "INTERNAL") or "INTERNAL").strip().upper(),
        icon=str(raw.get("icon", "server.svg") or "server.svg").strip(),
        is_world=bool(raw.get("is_world", False)),
        is_singleton=bool(raw.get("is_singleton", False)),
        identifiers=identifiers,
        name_expression=name_expression,
        identity=identity,
        metric_sets=metric_sets,
        metrics=metrics,
        aria_ops=aria_ops,
    )


def _parse_aria_ops_conf(raw: Any, parent_tag: str) -> AriaOpsConf:
    """Parse an aria_ops: block on an ARIA_OPS object_type."""
    if not isinstance(raw, dict):
        raise ManagementPackValidationError(
            f"{parent_tag}: aria_ops must be a mapping with adapter_kind, "
            f"resource_kind, and bind_metric"
        )
    return AriaOpsConf(
        adapter_kind=str(raw.get("adapter_kind", "") or "").strip(),
        resource_kind=str(raw.get("resource_kind", "") or "").strip(),
        bind_metric=str(raw.get("bind_metric", "") or "").strip(),
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

    # extract — Gap B: normalise single-mapping or list to List[ExtractRuleDef]
    raw_extract = raw.get("extract")
    extract = _parse_extract_block(raw_extract, atag)

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

    released_raw = data.get("released", False)
    released = bool(released_raw) if isinstance(released_raw, bool) else False

    raw_adapter_class = data.get("adapter_class")
    adapter_class = (
        str(raw_adapter_class).strip()
        if raw_adapter_class
        else None
    )

    mp = ManagementPackDef(
        name=mp_name,
        version=str(data.get("version", "") or "").strip(),
        adapter_kind=adapter_kind,
        description=str(data.get("description", "") or "").strip(),
        build_number=int(data.get("build_number", 1) or 1),
        author=str(data.get("author", "") or "").strip(),
        adapter_class=adapter_class,
        source=source,
        requests=requests,
        object_types=object_types,
        relationships=relationships,
        mpb_events=mpb_events,
        content=raw_content,
        source_path=path,
        released=released,
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
