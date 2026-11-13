"""sdk_project.py — Loader and dataclass for Tier 2 SDK adapter.yaml files.

Schema (all fields):
    name:          str   — display name (e.g. "VCF Content Factory Hello World SDK");
                           stripped, non-blank, one line (_ONE_LINE_BAD_CHARS)
    version:       str   — semver string (e.g. "1.0.0")
    build_number:  int   — monotonic build counter (e.g. 1)
    adapter_kind:  str   — adapter kind key; must match describe.xml + adapter.properties
    tier:          int   — must be 2 for SDK adapters
    description:   str   — optional human-readable description; stripped,
                           may span lines (LF, CRLF, tab), otherwise the
                           _ONE_LINE_BAD_CHARS rule (_MULTI_LINE_BAD_CHARS)
    dependencies:  list  — optional list of vendor JAR names from project lib/
    entry_class:   str   — optional fully-qualified entry class override;
                           default: derived as com.vcfcf.adapters.<adapter_kind>.<CamelCase>Adapter
    cross_mp_edges: list — optional; documents runtime-only cross-MP relationship
                           edges (e.g. LLDP/foreign-adapter stitching) that never
                           appear in describe.xml. See CrossMpEdgeInfo below for
                           the per-entry schema. Consumed by docs_gen.py to render
                           a "Cross-MP relationships" section into the generated
                           docs/README.md and docs/inventory-tree.md, since those
                           surfaces are otherwise derived solely from describe.xml
                           and would silently omit runtime-only stitched edges.
    content_naming: str  (optional) naming contract for the pak's
                           bundled_content (#229). One of:
                             factory_prefixed  every bundled content name starts
                                               with "[VCF CF] "
                                               (RULE-006). The default.
                             unprefixed        no bundled content name carries
                                               the "[VCF CF]" (or retired
                                               "[VCF Content Factory]")
                                               prefix (a pak that keeps its
                                               upstream names, e.g. vCommunity).
                           validate-sdk enforces it: an error when the key is
                           declared, a warning when it is absent, so a pak that
                           predates the key keeps validating until it declares.
    content_foreign_adapter_kinds: list (optional) adapter kinds other than
                           this pak's that bundled symptoms and alerts may
                           target (e.g. [VMWARE] for an alert on a vSphere
                           metric).  validate-sdk / build-sdk reject bundled
                           content on any other adapter kind unless describe.xml
                           or cross_mp_edges already names it.  Non-empty
                           strings, no duplicates, not this pak's own kind.
    stitch_targets: list (optional) the other adapters' resource kinds this
                           pak pushes metrics and properties onto through the
                           Suite API (ARIA_OPS stitching, e.g. vsanperf onto
                           VMWARE HostSystem). See StitchTargetInfo below for
                           the per-entry schema. Consumed by docs_gen.py to
                           render a "Metrics Pushed Onto" section and to draw
                           the targets into the inventory tree diagram, so a
                           pak whose only kind is its adapter instance gets a
                           landing page that says where its data lands (#310).
                           Documentation only: it does not change the pak.
    logging:       mapping (optional) the conf/logging.properties build-sdk
                           ships inside the pak (factory #313).  By default
                           the pak carries one line, ``<entry_class
                           package>=INFO``, so every logger in the pak's
                           package reaches the per-instance adapter log at
                           INFO.  Keys:
                             generate  bool, default true; false ships no
                                       generated file (an explicit
                                       conf/logging.properties in the
                                       adapter source still ships).
                             level     log4j level for the package line,
                                       default INFO.  A Test Connection
                                       raises every name it looks up (the
                                       adapter class, its helpers) to INFO
                                       until the next log4j reload or
                                       collector restart, so a DEBUG here
                                       holds only for names no Test
                                       Connection touched since (#322).
                             loggers   mapping of extra lines: logger name
                                       -> level, plus the SDK's MaxFileSize
                                       (e.g. 10MB) and MaxBackupIndex (int).
                                       The SDK skips a name the collector's
                                       own log4j config already covers
                                       (e.g. com.integrien.*, set to ERROR).
                           An adapter-source conf/logging.properties wins
                           over the generated file.  The file is read by
                           the 9.0.2 and 9.1.1 SDK jars' logger factory only;
                           8.18's never loads it.  See LoggingConfig.
    vendor:        str   (optional) the pak's vendor name (#336), stamped
                           into manifest.txt "vendor", the solution
                           resources.properties VENDOR= and both
                           overview.html pages.  Default
                           "VCF Content Factory".
    vendor_contact: str  (optional) free-text contact line (an email
                           address or URL) shown under the vendor on the
                           overview pages only.  Absent: no contact line.
    eula_file:     str   (optional) path, relative to the adapter project,
                           of the text shipped as the pak's eula.txt (both
                           copies).  Default: the factory MIT LICENSE.  When
                           set, the factory LICENSE also ships as
                           <adapter_kind>/lib/vcfcf-adapter-base-LICENSE.txt,
                           the notice for the bundled MIT base jar.
                           A present key must be a non-blank one-line string
                           (vendor, vendor_contact; see _ONE_LINE_BAD_CHARS)
                           or name a UTF-8 regular file inside the project
                           with printable text and no NUL (eula_file; read
                           once at load, leading BOM dropped).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore


class SdkProjectError(ValueError):
    """Raised when adapter.yaml fails schema validation."""


# adapter.yaml ``content_naming`` values (#229). See the module docstring.
CONTENT_NAMING_FACTORY_PREFIXED = "factory_prefixed"
CONTENT_NAMING_UNPREFIXED = "unprefixed"
CONTENT_NAMING_VALUES = (CONTENT_NAMING_FACTORY_PREFIXED, CONTENT_NAMING_UNPREFIXED)
CONTENT_NAMING_DEFAULT = CONTENT_NAMING_FACTORY_PREFIXED

# adapter.yaml ``vendor`` default (#336): what build-sdk stamped before the key.
DEFAULT_VENDOR = "VCF Content Factory"
# One-line fields (vendor, vendor_contact, name) reject: C0 controls
# and DEL (newline, tab, ...), C1 controls (U+0080-U+009F, e.g. NEL), the
# line and paragraph separators U+2028/U+2029, the Unicode bidi controls
# (ALM U+061C, LRM/RLM U+200E-U+200F, embeddings and overrides U+202A-U+202E,
# isolates U+2066-U+2069), which can make a vendor display other than it
# reads, and unpaired UTF-16 surrogates U+D800-U+DFFF (YAML "\ud83d"-style
# escapes), which no sink can encode.
_ONE_LINE_BAD_CHARS = re.compile(
    "[\x00-\x1f\x7f-\x9f  ؜‎‏"
    "‪-‮⁦-⁩\ud800-\udfff]"
)
_ONE_LINE_RULE = (
    "one line of plain text: no control character (newline, tab, U+0080-"
    "U+009F), line or paragraph separator (U+2028, U+2029), bidi control "
    "(U+061C, U+200E, U+200F, U+202A-U+202E, U+2066-U+2069) or unpaired "
    "surrogate (U+D800-U+DFFF)"
)
# ``description`` (#338) is the one-line rule with line breaks allowed: LF,
# CR only as part of CRLF, and tab.  A lone CR is rejected: HTML turns it
# into a line feed, so the overview page would not read back as the value.
_MULTI_LINE_BAD_CHARS = re.compile(r"(?!\r\n|[\n\t])" + _ONE_LINE_BAD_CHARS.pattern)
_MULTI_LINE_RULE = (
    "plain text (line feed, CRLF and tab allowed): no other control "
    "character (lone CR, NUL, U+0080-U+009F), line or paragraph separator "
    "(U+2028, U+2029), bidi control (U+061C, U+200E, U+200F, U+202A-U+202E, "
    "U+2066-U+2069) or unpaired surrogate (U+D800-U+DFFF)"
)


def _reject_bad_chars(val: str, key: str, where: str,
                      pattern=_ONE_LINE_BAD_CHARS, rule: str = _ONE_LINE_RULE) -> None:
    """Raise when ``val`` holds a character ``pattern`` rejects.

    The shared check for every adapter.yaml string stamped into the pak
    (vendor, vendor_contact, name, description): what passes encodes in
    every sink (JSON manifest.txt, the .properties escaper, the HTML
    escaper) and reads back as itself from the overview pages.
    """
    bad = pattern.search(val)
    if bad:
        raise SdkProjectError(
            f"{where}: '{key}' must be {rule}; got "
            f"U+{ord(bad.group()):04X} at position {bad.start()} of {val!r}"
        )


def _parse_one_line(raw: dict, key: str, where: str) -> Optional[str]:
    """Optional one-line string key: None when absent, stripped otherwise.

    A value that passes is safe in every sink: JSON (manifest.txt), the
    .properties escaper and the HTML escaper encode any other code point.
    """
    if key not in raw:
        return None
    val = raw[key]
    if val is not None and not isinstance(val, str):
        raise SdkProjectError(
            f"{where}: '{key}' must be a string; got {type(val).__name__} "
            f"{val!r}. Quote it, or remove the key to use the default."
        )
    if val is None or not val.strip():
        raise SdkProjectError(
            f"{where}: '{key}' is present but blank; set a value or remove "
            f"the key to use the default."
        )
    _reject_bad_chars(val.strip(), key, where)
    return val.strip()


_UTF8_BOM = b"\xef\xbb\xbf"


def _parse_eula_file(raw: dict, project_dir: Path,
                     where: str) -> Tuple[str, Optional[Path], Optional[bytes]]:
    """Optional ``eula_file`` key: ("", None, None) when absent.

    The path is relative to the adapter project and must resolve inside it
    (symlinks followed) to a regular file that decodes as UTF-8, holds no NUL
    and has at least one printable non-space character after any leading
    BOM.  Returns (path as written, resolved path, the bytes to ship).

    The file is read once, here; build-sdk ships exactly these bytes, so a
    change to the file after validation cannot change the pak (#336 review
    W3).  A leading UTF-8 BOM is dropped from them: the factory LICENSE and
    57 of 58 reference vendor paks ship eula.txt without one, and a BOM read
    as anything but UTF-8 shows as stray characters.
    """
    if "eula_file" not in raw:
        return "", None, None
    val = raw["eula_file"]
    if val is not None and not isinstance(val, str):
        raise SdkProjectError(
            f"{where}: 'eula_file' must be a path string relative to the "
            f"adapter project; got {type(val).__name__} {val!r}"
        )
    rel = (val or "").strip()
    if not rel:
        raise SdkProjectError(
            f"{where}: 'eula_file' is present but blank; name the licence "
            f"file (e.g. LICENSE) or remove the key to ship the factory MIT "
            f"LICENSE."
        )
    try:
        root = project_dir.resolve()
        target = (project_dir / rel).resolve()
    except (OSError, ValueError) as exc:
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} is not a usable path: {exc}"
        ) from None
    try:
        target.relative_to(root)
    except ValueError:
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} resolves to {target}, outside the "
            f"adapter project {root}; keep the licence file in the project."
        ) from None
    if not target.exists():
        raise SdkProjectError(f"{where}: 'eula_file' {rel!r} not found ({target})")
    if not target.is_file():
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} is not a regular file ({target})"
        )
    try:
        data = target.read_bytes()
    except OSError as exc:
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} cannot be read: {exc}"
        ) from None
    if data.startswith(_UTF8_BOM):
        data = data[len(_UTF8_BOM):]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} is not UTF-8 text ({exc})"
        ) from None
    if not text.strip():
        raise SdkProjectError(f"{where}: 'eula_file' {rel!r} is empty")
    if "\x00" in text:
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} contains NUL bytes; it must be a "
            f"plain-text licence"
        )
    if not any(ch.isprintable() and not ch.isspace() for ch in text):
        raise SdkProjectError(
            f"{where}: 'eula_file' {rel!r} has no printable text; the pak "
            f"would ship a blank licence"
        )
    return rel, target, data


@dataclass
class CrossMpEdgeInfo:
    """One entry of the optional ``cross_mp_edges`` adapter.yaml stanza.

    Documents a runtime-only relationship edge between this adapter's own
    resource kind and a resource kind owned by a *different* (foreign)
    management pack — e.g. unifi's per-vmnic LLDP join onto VMWARE
    HostSystem, or synology's datastore/LUN attachment onto VMWARE
    Datastore. These edges are created via the Suite API at collection
    time; they are never expressed in describe.xml (which only knows
    about this adapter's own ResourceKinds/TraversalSpec), so without this
    stanza the generated docset has no way to mention them.

    Fields:
        parent:               display label of the edge's parent endpoint
                               (e.g. "VMWARE HostSystem").
        child:                display label of the edge's child endpoint
                               (e.g. "UniFiSwitchPort").
        direction:            "parent_foreign" (default) — the parent
                               endpoint belongs to a foreign adapter kind,
                               child is owned by this adapter — or
                               "child_foreign" — the reverse.
        foreign_adapter_kind: adapter kind of the foreign endpoint (e.g.
                               "VMWARE"), used for the "(foreign, X)"
                               annotation. Optional; omitted from the
                               annotation if blank.
        description:          free-text one-liner describing the edge
                               (transport, cardinality, additive/optional
                               nature, etc).
    """

    parent: str
    child: str
    direction: str = "parent_foreign"
    foreign_adapter_kind: str = ""
    description: str = ""


_CROSS_MP_EDGE_ALLOWED_KEYS = {
    "parent", "child", "direction", "foreign_adapter_kind", "description",
}
_CROSS_MP_EDGE_REQUIRED_KEYS = {"parent", "child"}
_CROSS_MP_EDGE_DIRECTIONS = {"parent_foreign", "child_foreign"}


def _parse_cross_mp_edges(raw: dict, where: str) -> List[CrossMpEdgeInfo]:
    """Parse and validate the optional ``cross_mp_edges`` adapter.yaml stanza.

    Schema (list of mappings):
        cross_mp_edges:
          - parent: "VMWARE HostSystem"        # required, non-empty str
            child: UniFiSwitchPort             # required, non-empty str
            direction: parent_foreign          # optional; parent_foreign (default) | child_foreign
            foreign_adapter_kind: VMWARE        # optional str
            description: "Per-vmnic LLDP join via Suite API; additive, optional"

    Returns an empty list if the key is absent (zero-churn default).

    Raises:
        SdkProjectError: on unknown keys, missing required fields, or bad
                         types/values — same error class as the rest of
                         adapter.yaml schema validation, so validate-sdk
                         surfaces a clear message.
    """
    entries = raw.get("cross_mp_edges")
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise SdkProjectError(
            f"{where}: 'cross_mp_edges' must be a list; got {type(entries).__name__}"
        )

    edges: List[CrossMpEdgeInfo] = []
    for i, entry in enumerate(entries):
        entry_where = f"{where}: cross_mp_edges[{i}]"
        if not isinstance(entry, dict):
            raise SdkProjectError(
                f"{entry_where}: must be a mapping; got {type(entry).__name__}"
            )

        unknown = set(entry.keys()) - _CROSS_MP_EDGE_ALLOWED_KEYS
        if unknown:
            raise SdkProjectError(
                f"{entry_where}: unknown key(s) {sorted(unknown)}; "
                f"allowed keys are {sorted(_CROSS_MP_EDGE_ALLOWED_KEYS)}"
            )

        missing = _CROSS_MP_EDGE_REQUIRED_KEYS - set(entry.keys())
        if missing:
            raise SdkProjectError(
                f"{entry_where}: missing required field(s) {sorted(missing)}"
            )

        parent = entry["parent"]
        child = entry["child"]
        if not isinstance(parent, str) or not parent.strip():
            raise SdkProjectError(f"{entry_where}: 'parent' must be a non-empty string")
        if not isinstance(child, str) or not child.strip():
            raise SdkProjectError(f"{entry_where}: 'child' must be a non-empty string")

        direction = entry.get("direction", "parent_foreign")
        if not isinstance(direction, str) or direction not in _CROSS_MP_EDGE_DIRECTIONS:
            raise SdkProjectError(
                f"{entry_where}: 'direction' must be one of "
                f"{sorted(_CROSS_MP_EDGE_DIRECTIONS)}; got {direction!r}"
            )

        foreign_adapter_kind = entry.get("foreign_adapter_kind", "")
        if not isinstance(foreign_adapter_kind, str):
            raise SdkProjectError(
                f"{entry_where}: 'foreign_adapter_kind' must be a string"
            )

        description = entry.get("description", "")
        if not isinstance(description, str):
            raise SdkProjectError(f"{entry_where}: 'description' must be a string")

        edges.append(CrossMpEdgeInfo(
            parent=parent.strip(),
            child=child.strip(),
            direction=direction,
            foreign_adapter_kind=foreign_adapter_kind.strip(),
            description=description.strip(),
        ))

    return edges


# log4j level names Level.toLevel accepts.  The SDK parses logging.properties
# values with it and an unknown name silently falls back, so reject it here.
LOG4J_LEVELS = ("OFF", "FATAL", "ERROR", "WARN", "INFO", "DEBUG", "TRACE", "ALL")
_LOGGING_ALLOWED_KEYS = {"generate", "level", "loggers"}
_LOGGER_NAME_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(\.[A-Za-z_$][A-Za-z0-9_$]*)*")


@dataclass
class LoggingConfig:
    """The optional ``logging:`` adapter.yaml stanza (factory #313).

    The SDK's per-instance adapter log appender takes the level of the log4j
    entry covering the bare logger name at the instance's first lookup.
    Entries from ``<adapter>/conf/logging.properties`` are the vendor
    mechanism (``com.vmware.adapter3.nsxt=INFO``); without one, a name falls
    to the collector root (WARN) and its INFO is dropped.  build-sdk ships
    the file from this config (``sdk_builder._generate_logging_properties``).

    Fields:
        generate: False ships no generated file.
        level:    level for the ``<package>`` line (upper-case log4j name).
                  Not absolute: a Test Connection's ``raiseToInfo`` adds an
                  exact-name INFO entry for each name it looks up (the
                  adapter class and the helpers it builds), which shadows a
                  DEBUG here for instances created after it, until the next
                  log4j reload or collector restart (#322).
        loggers:  extra lines in declaration order, (name, value).  The SDK
                  only loads a name the collector's own log4j config leaves
                  to root; one it already covers (``com.integrien.*``) is
                  skipped silently.
        declared: adapter.yaml carries a ``logging:`` key.
    """

    generate: bool = True
    level: str = "INFO"
    loggers: List[Tuple[str, str]] = field(default_factory=list)
    declared: bool = False


def entry_package_of(entry_class: str) -> str:
    """Java package of an entry class: the key logging.properties uses.

    A class in the default package (no dot) keys its own name.
    """
    dot = entry_class.rfind(".")
    return entry_class[:dot] if dot > 0 else entry_class


def _parse_log_level(value, where: str) -> str:
    if not isinstance(value, str) or value.strip().upper() not in LOG4J_LEVELS:
        raise SdkProjectError(
            f"{where} must be one of {', '.join(LOG4J_LEVELS)}; got {value!r}"
        )
    return value.strip().upper()


def _parse_logging(raw: dict, where: str) -> LoggingConfig:
    """Parse and validate the optional ``logging`` adapter.yaml stanza."""
    if "logging" not in raw:
        return LoggingConfig()
    stanza = raw["logging"]
    if not isinstance(stanza, dict):
        raise SdkProjectError(
            f"{where}: 'logging' must be a mapping; got {type(stanza).__name__}"
        )
    unknown = set(stanza) - _LOGGING_ALLOWED_KEYS
    if unknown:
        raise SdkProjectError(
            f"{where}: logging: unknown key(s) {sorted(unknown, key=str)}; "
            f"allowed keys are {sorted(_LOGGING_ALLOWED_KEYS)}"
        )
    generate = stanza.get("generate", True)
    if not isinstance(generate, bool):
        raise SdkProjectError(
            f"{where}: logging.generate must be true or false; got {generate!r}"
        )
    level = _parse_log_level(stanza.get("level", "INFO"), f"{where}: logging.level")
    loggers_raw = stanza.get("loggers")
    if loggers_raw is None:
        loggers_raw = {}
    if not isinstance(loggers_raw, dict):
        raise SdkProjectError(
            f"{where}: logging.loggers must be a mapping of logger name to level; "
            f"got {type(loggers_raw).__name__}"
        )
    loggers: List[Tuple[str, str]] = []
    for name, value in loggers_raw.items():
        key_where = f"{where}: logging.loggers[{name!r}]"
        if name == "MaxFileSize":
            if not isinstance(value, str) or not re.fullmatch(r"\d+[GMK]B", value.strip()):
                raise SdkProjectError(
                    f"{key_where} must be a size such as 10MB (digits, then GB, "
                    f"MB or KB); got {value!r}"
                )
            loggers.append((name, value.strip()))
        elif name == "MaxBackupIndex":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SdkProjectError(
                    f"{key_where} must be a non-negative integer; got {value!r}"
                )
            loggers.append((name, str(value)))
        else:
            if not isinstance(name, str) or not _LOGGER_NAME_RE.fullmatch(name):
                raise SdkProjectError(
                    f"{where}: logging.loggers key {name!r} is not a logger name "
                    "(dotted Java identifiers, e.g. com.example.client)"
                )
            loggers.append((name, _parse_log_level(value, key_where)))
    return LoggingConfig(generate=generate, level=level, loggers=loggers,
                         declared=True)


@dataclass
class StitchTargetInfo:
    """One entry of the optional ``stitch_targets`` adapter.yaml stanza (#310).

    A resource kind owned by another adapter that this pak pushes keys onto
    through the Suite API. describe.xml cannot declare keys on another
    adapter's kinds, so without this stanza a stitch-only pak's docs show
    no resource kinds and an empty inventory tree.

    Fields:
        adapter_kind:  adapter kind that owns the target (e.g. "VMWARE").
        resource_kind: the target resource kind key (e.g. "HostSystem").
        identity:      free text: how the pak matches its data to the
                       target object (e.g. "VMEntityObjectID + VMEntityVCID").
        key_groups:    key-group prefixes pushed onto the target, in the
                       order the docs list them (e.g. "vSAN Perf|DOM Owner|*").
        instanced_by:  optional free text: what an instanced group's
                       instance name is (e.g. "<vmnic> = vSAN physical NIC").

    ``adapter_kind`` and ``resource_kind`` may hold interior spaces (VMWARE's
    "VMwareAdapter Instance") but not ``<``, ``>``, ``|``, a backtick, or a
    control character. ``identity`` and ``instanced_by`` are plain text, not
    markdown: docs-gen escapes markdown metacharacters in them.
    """

    adapter_kind: str
    resource_kind: str
    identity: str
    key_groups: List[str] = field(default_factory=list)
    instanced_by: str = ""


_STITCH_TARGET_ALLOWED_KEYS = {
    "adapter_kind", "resource_kind", "identity", "key_groups", "instanced_by",
}
_STITCH_TARGET_REQUIRED_KEYS = {"adapter_kind", "resource_kind", "identity", "key_groups"}
# adapter_kind / resource_kind become a markdown heading, a quick-reference
# entry and a diagram node title. Interior spaces stay legal: VMWARE's own
# "VMwareAdapter Instance" kind key has one.
_STITCH_KIND_BAD_CHARS = re.compile(r"[<>|`\x00-\x1f\x7f]")


def _parse_stitch_targets(raw: dict, where: str,
                          own_adapter_kind: Optional[str] = None) -> List[StitchTargetInfo]:
    """Parse and validate the optional ``stitch_targets`` adapter.yaml stanza.

    Schema (list of mappings):
        stitch_targets:
          - adapter_kind: VMWARE                          # required, non-empty str
            resource_kind: HostSystem                     # required, non-empty str
            identity: "VMEntityObjectID + VMEntityVCID"   # required, non-empty str
            key_groups:                                   # required, non-empty list
              - "vSAN Perf|DOM Owner|*"                   #   of non-empty strs, no duplicates
              - "vSAN Perf|pNIC:<vmnic>|*"
            instanced_by: "<vmnic> = vSAN physical NIC"   # optional str

    ``own_adapter_kind``, when given, may not appear as a target's
    ``adapter_kind``: a pak's own kinds belong in describe.xml. The same
    (adapter_kind, resource_kind) pair may not appear twice; list every
    group for one target under one entry.

    Returns an empty list if the key is absent (zero-churn default).

    Raises:
        SdkProjectError: on unknown keys, missing required fields, or bad
                         types/values, so validate-sdk and docs-gen surface
                         the same message.
    """
    entries = raw.get("stitch_targets")
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise SdkProjectError(
            f"{where}: 'stitch_targets' must be a list of mappings; "
            f"got {type(entries).__name__}"
        )

    targets: List[StitchTargetInfo] = []
    seen_pairs: set = set()
    for i, entry in enumerate(entries):
        entry_where = f"{where}: stitch_targets[{i}]"
        if not isinstance(entry, dict):
            raise SdkProjectError(
                f"{entry_where}: must be a mapping; got {type(entry).__name__}"
            )

        unknown = set(entry.keys()) - _STITCH_TARGET_ALLOWED_KEYS
        if unknown:
            raise SdkProjectError(
                f"{entry_where}: unknown key(s) {sorted(unknown, key=str)}; "
                f"allowed keys are {sorted(_STITCH_TARGET_ALLOWED_KEYS)}"
            )

        missing = _STITCH_TARGET_REQUIRED_KEYS - set(entry.keys())
        if missing:
            raise SdkProjectError(
                f"{entry_where}: missing required field(s) {sorted(missing)}"
            )

        values = {}
        for key in ("adapter_kind", "resource_kind", "identity"):
            val = entry[key]
            if not isinstance(val, str) or not val.strip():
                raise SdkProjectError(
                    f"{entry_where}: '{key}' must be a non-empty string; got {val!r}"
                )
            values[key] = val.strip()
            if key != "identity" and _STITCH_KIND_BAD_CHARS.search(values[key]):
                raise SdkProjectError(
                    f"{entry_where}: '{key}' may not contain '<', '>', '|', a "
                    f"backtick, or a tab or newline; got {val!r}"
                )

        if own_adapter_kind and values["adapter_kind"] == own_adapter_kind:
            raise SdkProjectError(
                f"{entry_where}: 'adapter_kind' is this pak's own adapter_kind "
                f"{own_adapter_kind!r}; stitch_targets lists only other "
                f"adapters' kinds (declare your own kinds in describe.xml)"
            )

        pair = (values["adapter_kind"], values["resource_kind"])
        if pair in seen_pairs:
            raise SdkProjectError(
                f"{entry_where}: {pair[0]} {pair[1]} is already listed; put "
                f"every key group for one target under a single entry"
            )
        seen_pairs.add(pair)

        groups_raw = entry["key_groups"]
        if not isinstance(groups_raw, list) or not groups_raw:
            raise SdkProjectError(
                f"{entry_where}: 'key_groups' must be a non-empty list of "
                f"key-group prefixes (e.g. \"vSAN Perf|DOM Owner|*\"); "
                f"got {groups_raw!r}"
            )
        groups: List[str] = []
        for j, group in enumerate(groups_raw):
            if not isinstance(group, str) or not group.strip():
                raise SdkProjectError(
                    f"{entry_where}: key_groups[{j}] must be a non-empty "
                    f"string; got {group!r}"
                )
            group = group.strip()
            if group in groups:
                raise SdkProjectError(
                    f"{entry_where}: key_groups lists {group!r} twice"
                )
            groups.append(group)

        instanced_by = entry.get("instanced_by", "")
        if instanced_by is None:
            instanced_by = ""
        if not isinstance(instanced_by, str):
            raise SdkProjectError(
                f"{entry_where}: 'instanced_by' must be a string; got {instanced_by!r}"
            )

        targets.append(StitchTargetInfo(
            adapter_kind=values["adapter_kind"],
            resource_kind=values["resource_kind"],
            identity=values["identity"],
            key_groups=groups,
            instanced_by=instanced_by.strip(),
        ))

    return targets


@dataclass
class SdkProjectDef:
    """In-memory representation of an adapter.yaml file."""

    name: str
    version: str
    build_number: int
    adapter_kind: str
    tier: int
    description: str
    dependencies: List[str]
    entry_class: str
    source_path: Path
    cross_mp_edges: List[CrossMpEdgeInfo] = field(default_factory=list)
    # Naming contract for bundled_content (#229). ``content_naming_declared``
    # is False when adapter.yaml omits the key: validate-sdk then applies the
    # default as a warning, not an error.
    content_naming: str = CONTENT_NAMING_DEFAULT
    content_naming_declared: bool = False
    # Opt-in: other adapter kinds bundled symptoms/alerts may target.
    content_foreign_adapter_kinds: List[str] = field(default_factory=list)
    # Documentation only (#310): other adapters' kinds this pak pushes onto.
    stitch_targets: List[StitchTargetInfo] = field(default_factory=list)
    # conf/logging.properties the build ships (factory #313).
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    # Pak attribution and licence (#336).  ``vendor_declared`` is False when
    # adapter.yaml omits ``vendor`` (build-sdk then says how to set one).
    # ``eula_path`` is the resolved file, ``eula_file`` the value as written,
    # ``eula_bytes`` the validated content read at load: what ships.
    vendor: str = DEFAULT_VENDOR
    vendor_declared: bool = False
    vendor_contact: str = ""
    eula_file: str = ""
    eula_path: Optional[Path] = None
    eula_bytes: Optional[bytes] = None

    @property
    def entry_package(self) -> str:
        """Java package of entry_class: the logger prefix logging.properties keys."""
        return entry_package_of(self.entry_class)

    @property
    def pak_filename(self) -> str:
        """Output .pak filename: vcfcf_sdk_<name>.<version>.<build>.pak

        Strips the redundant ``vcfcf_`` prefix from adapter_kind (factory
        convention is for SDK adapter_kinds to start with ``vcfcf_``) so the
        filename doesn't double up.
        """
        name = self.adapter_kind
        if name.startswith("vcfcf_"):
            name = name[len("vcfcf_"):]
        return f"vcfcf_sdk_{name}.{self.version}.{self.build_number}.pak"

    @property
    def adapter_dir_name(self) -> str:
        """Directory name inside adapters.zip (convention: adapter_kind)."""
        return self.adapter_kind

    @property
    def adapter_jar_name(self) -> str:
        """Entry-point JAR name at the root of adapters.zip."""
        return f"{self.adapter_kind}.jar"


def _derive_entry_class(adapter_kind: str) -> str:
    """Derive a default entry class from the adapter kind key.

    Convention: com.vcfcf.adapters.<adapter_kind>.<CamelCase>Adapter
    where CamelCase converts 'vcfcf_hello_world' → 'HelloWorldAdapter'.

    Examples:
        vcfcf_hello_world  → com.vcfcf.adapters.vcfcf_hello_world.HelloWorldAdapter
        synology_dsm       → com.vcfcf.adapters.synology_dsm.SynologyDsmAdapter
    """
    return f"com.vcfcf.adapters.{adapter_kind}.{adapter_class_name(adapter_kind)}"


def adapter_class_name(adapter_kind: str) -> str:
    """Simple Java class name for an adapter kind key: <CamelCase>Adapter.

    The leading ``vcfcf_`` is dropped from the stem, except when the rest
    starts with a digit: scaffold-sdk adds ``vcfcf_`` to a name like
    "9Lives" precisely because an identifier cannot start with a digit, so
    the class keeps it too ("vcfcf_9lives" -> "Vcfcf9livesAdapter") rather
    than emitting "9livesAdapter", which javac rejects.

    Examples:
        vcfcf_hello_world  -> HelloWorldAdapter
        synology_dsm       -> SynologyDsmAdapter
        vcfcf_9lives       -> Vcfcf9livesAdapter
    """
    stem = adapter_kind
    if stem.startswith("vcfcf_") and not stem[len("vcfcf_"):][:1].isdigit():
        stem = stem[len("vcfcf_"):]

    # CamelCase: split on underscore, capitalize each part
    camel = "".join(part.capitalize() for part in stem.split("_"))
    return f"{camel}Adapter"


def _require(raw: dict, key: str, expected_type: type, where: str):
    if key not in raw:
        raise SdkProjectError(f"{where}: missing required field '{key}'")
    val = raw[key]
    if not isinstance(val, expected_type):
        raise SdkProjectError(
            f"{where}: field '{key}' must be {expected_type.__name__}; got {type(val).__name__}"
        )
    return val


def load_sdk_project(path: Path) -> SdkProjectDef:
    """Load and validate an adapter.yaml, returning an SdkProjectDef.

    Args:
        path: path to adapter.yaml

    Returns:
        validated SdkProjectDef

    Raises:
        SdkProjectError: if the YAML is missing required fields or fails validation
        FileNotFoundError: if the file does not exist
    """
    if yaml is None:
        raise ImportError(
            "PyYAML is required to load adapter.yaml files. "
            "Install it with: pip install pyyaml"
        )

    where = str(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise SdkProjectError(f"{where}: expected a YAML mapping at root level")

    # name is stripped like vendor and description (#338): the stripped value
    # is the one every sink stamps.
    name = _require(raw, "name", str, where).strip()
    if not name:
        raise SdkProjectError(f"{where}: field 'name' is blank")
    _reject_bad_chars(name, "name", where)
    version = _require(raw, "version", str, where)
    build_number_raw = _require(raw, "build_number", int, where)
    adapter_kind = _require(raw, "adapter_kind", str, where)
    tier = _require(raw, "tier", int, where)

    if tier != 2:
        raise SdkProjectError(
            f"{where}: field 'tier' must be 2 for SDK adapters; got {tier}"
        )

    # Validate adapter_kind: lowercase alphanumeric + underscore only
    if not re.fullmatch(r"[a-z][a-z0-9_]*", adapter_kind):
        raise SdkProjectError(
            f"{where}: adapter_kind must be lowercase alphanumeric + underscore, "
            f"starting with a letter; got {adapter_kind!r}"
        )

    # Validate version: semver-like (digits and dots)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SdkProjectError(
            f"{where}: version must be semver (e.g. '1.0.0'); got {version!r}"
        )

    description = raw.get("description", "")
    if not isinstance(description, str):
        description = str(description)
    description = description.strip()
    _reject_bad_chars(description, "description", where,
                      _MULTI_LINE_BAD_CHARS, _MULTI_LINE_RULE)

    dependencies = raw.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise SdkProjectError(
            f"{where}: 'dependencies' must be a list of JAR names; "
            f"got {type(dependencies).__name__}"
        )
    for dep in dependencies:
        if not isinstance(dep, str):
            raise SdkProjectError(
                f"{where}: each entry in 'dependencies' must be a string; got {dep!r}"
            )

    entry_class = raw.get("entry_class", None)
    if entry_class is None:
        entry_class = _derive_entry_class(adapter_kind)
    elif not isinstance(entry_class, str):
        raise SdkProjectError(
            f"{where}: 'entry_class' must be a string; got {type(entry_class).__name__}"
        )

    cross_mp_edges = _parse_cross_mp_edges(raw, where)
    stitch_targets = _parse_stitch_targets(raw, where, adapter_kind)

    content_naming_declared = "content_naming" in raw
    content_naming = raw.get("content_naming", CONTENT_NAMING_DEFAULT)
    if content_naming not in CONTENT_NAMING_VALUES:
        raise SdkProjectError(
            f"{where}: 'content_naming' must be one of "
            f"{', '.join(CONTENT_NAMING_VALUES)}; got {content_naming!r}"
        )

    content_foreign_adapter_kinds = _parse_content_foreign_adapter_kinds(
        raw, adapter_kind, where,
    )

    logging_config = _parse_logging(raw, where)
    _package = entry_package_of(entry_class)
    if any(name == _package for name, _ in logging_config.loggers):
        raise SdkProjectError(
            f"{where}: logging.loggers names the adapter package {_package!r}; "
            "set its level with logging.level instead"
        )

    vendor = _parse_one_line(raw, "vendor", where)
    vendor_contact = _parse_one_line(raw, "vendor_contact", where)
    eula_file, eula_path, eula_bytes = _parse_eula_file(raw, path.parent, where)

    return SdkProjectDef(
        name=name,
        version=version,
        build_number=int(build_number_raw),
        adapter_kind=adapter_kind,
        tier=tier,
        description=description,
        dependencies=dependencies,
        entry_class=entry_class,
        source_path=path,
        cross_mp_edges=cross_mp_edges,
        content_naming=content_naming,
        content_naming_declared=content_naming_declared,
        content_foreign_adapter_kinds=content_foreign_adapter_kinds,
        stitch_targets=stitch_targets,
        logging=logging_config,
        vendor=vendor if vendor is not None else DEFAULT_VENDOR,
        vendor_declared=vendor is not None,
        vendor_contact=vendor_contact or "",
        eula_file=eula_file,
        eula_path=eula_path,
        eula_bytes=eula_bytes,
    )


def _parse_content_foreign_adapter_kinds(raw: dict, adapter_kind: str,
                                         where: str) -> List[str]:
    """Parse the optional ``content_foreign_adapter_kinds`` list."""
    entries = raw.get("content_foreign_adapter_kinds")
    if entries is None:
        return []
    key = "content_foreign_adapter_kinds"
    if not isinstance(entries, list):
        raise SdkProjectError(
            f"{where}: '{key}' must be a list of adapter kind keys; "
            f"got {type(entries).__name__}"
        )
    out: List[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, str) or not entry.strip():
            raise SdkProjectError(
                f"{where}: {key}[{i}] must be a non-empty string; got {entry!r}"
            )
        kind = entry.strip()
        if kind == adapter_kind:
            raise SdkProjectError(
                f"{where}: {key}[{i}] is this pak's own adapter_kind "
                f"{kind!r}; list only other adapter kinds"
            )
        if kind in out:
            raise SdkProjectError(f"{where}: {key} lists {kind!r} twice")
        out.append(kind)
    return out
