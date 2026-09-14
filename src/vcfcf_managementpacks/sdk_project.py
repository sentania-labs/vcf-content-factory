"""sdk_project.py — Loader and dataclass for Tier 2 SDK adapter.yaml files.

Schema (all fields):
    name:          str   — display name (e.g. "VCF Content Factory Hello World SDK")
    version:       str   — semver string (e.g. "1.0.0")
    build_number:  int   — monotonic build counter (e.g. 1)
    adapter_kind:  str   — adapter kind key; must match describe.xml + adapter.properties
    tier:          int   — must be 2 for SDK adapters
    description:   str   — optional human-readable description
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
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore


class SdkProjectError(ValueError):
    """Raised when adapter.yaml fails schema validation."""


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
    # Strip leading vcfcf_ prefix for the class name stem if present
    stem = adapter_kind
    if stem.startswith("vcfcf_"):
        stem = stem[len("vcfcf_"):]

    # CamelCase: split on underscore, capitalize each part
    camel = "".join(part.capitalize() for part in stem.split("_"))
    return f"com.vcfcf.adapters.{adapter_kind}.{camel}Adapter"


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

    name = _require(raw, "name", str, where)
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

    return SdkProjectDef(
        name=name,
        version=version,
        build_number=int(build_number_raw),
        adapter_kind=adapter_kind,
        tier=tier,
        description=description.strip(),
        dependencies=dependencies,
        entry_class=entry_class,
        source_path=path,
        cross_mp_edges=cross_mp_edges,
    )
