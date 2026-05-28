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
    )
