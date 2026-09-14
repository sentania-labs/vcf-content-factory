"""Load and validate super metric YAML definitions (M2 row 3: the parse half).

This module reads and validates; it never writes to its input and never
looks at the working directory. Two behaviours the factory relied on are
callbacks a caller may supply:

- ``on_missing_id(path) -> str``: called when a YAML has no ``id``. The
  factory (``vcfcf_supermetrics.loader``) mints a uuid4 into the file; with
  no callback a missing id is a ``SuperMetricValidationError``.
- ``provenance_of(path) -> str``: fills ``SuperMetricDef.provenance``. The
  factory derives it from the repo layout; with no callback it is ``""``.

``load_dir`` takes its directory as a required argument and ``sm_id_map``
only ever loads the files it is handed (``None`` is an empty map, never a
scan); the factory wrapper keeps the old ``"supermetrics"`` default and the
cwd scan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional

import yaml
import yaml.constructor
import yaml.resolver


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


class SuperMetricValidationError(ValueError):
    pass


# Looping functions accepted by VCF Ops super metric DSL.
LOOPING_FUNCS = {"avg", "sum", "min", "max", "count", "combine"}
SINGLE_FUNCS = {
    "abs", "acos", "asin", "atan", "ceil", "cos", "cosh",
    "exp", "floor", "log", "log10", "pow", "rand", "sin",
    "sinh", "sqrt", "tan", "tanh",
}


@dataclass
class SuperMetricDef:
    name: str
    formula: str
    description: str = ""
    resource_kinds: list = None  # list of {"resourceKindKey","adapterKindKey"}
    id: str = ""
    unit_id: str = ""
    source_path: Path | None = None
    released: bool = False   # publish gate
    version: str = "1.0.0"  # internal semver
    # Provenance: "factory", a third-party project slug, or "" (unknown).
    # Populated by the loader from source_path; never author-supplied.
    provenance: str = ""

    def validate(self, enforce_framework_prefix: bool = True) -> None:
        if not self.name or not self.name.strip():
            raise SuperMetricValidationError("name is required")
        if enforce_framework_prefix and not self.name.startswith("[VCF Content Factory] "):
            src = f" ({self.source_path})" if self.source_path else ""
            raise SuperMetricValidationError(
                f'{self.source_path or self.name}: name "{self.name}" missing framework prefix '
                f'"[VCF Content Factory]". All factory-authored content must carry the literal '
                f'"[VCF Content Factory]" prefix (see CLAUDE.md §Hard rules #5). For third-party '
                f"bundle content, ensure the bundle manifest sets factory_native: false."
            )
        if not self.formula or not self.formula.strip():
            raise SuperMetricValidationError(f"{self.name}: formula is required")
        if not self.resource_kinds:
            raise SuperMetricValidationError(
                f"{self.name}: resource_kinds is required "
                f"(e.g. [{{resource_kind_key: VirtualMachine, adapter_kind_key: VMWARE}}])"
            )
        for rk in self.resource_kinds:
            if not isinstance(rk, dict):
                raise SuperMetricValidationError(
                    f"{self.name}: each resource_kinds entry must be a mapping"
                )
            if not rk.get("resourceKindKey"):
                raise SuperMetricValidationError(
                    f"{self.name}: resource_kinds entry missing resource_kind_key"
                )
            if not rk.get("adapterKindKey"):
                raise SuperMetricValidationError(
                    f"{self.name}: resource_kinds entry missing adapter_kind_key"
                )

        f = self.formula

        # Balanced parens / braces / brackets.
        for opener, closer in (("(", ")"), ("{", "}"), ("[", "]")):
            if f.count(opener) != f.count(closer):
                raise SuperMetricValidationError(
                    f"{self.name}: unbalanced '{opener}{closer}' in formula"
                )

        # Must contain at least one resource entry.
        resource_entries = re.findall(r"\$\{[^}]*\}", f)
        if not resource_entries:
            raise SuperMetricValidationError(
                f"{self.name}: formula contains no ${{...}} resource entry"
            )

        for entry in resource_entries:
            self._validate_resource_entry(entry)

        # depth=0 is illegal per VCF docs.
        for m in re.finditer(r"depth\s*=\s*(-?\d+)", f):
            if int(m.group(1)) == 0:
                raise SuperMetricValidationError(
                    f"{self.name}: depth=0 is not allowed"
                )

    def _validate_resource_entry(self, entry: str) -> None:
        inner = entry[2:-1].strip()  # strip ${ }
        if not inner:
            raise SuperMetricValidationError(
                f"{self.name}: empty resource entry ${{}}"
            )
        # Either 'this, ...' bound to assigned object, or must specify
        # adaptertype + (objecttype OR resourcename).
        head = inner.split(",", 1)[0].strip().lower()
        if head == "this":
            return
        lower = inner.lower()
        if "adaptertype" not in lower:
            raise SuperMetricValidationError(
                f"{self.name}: resource entry must include 'adaptertype=' "
                f"or start with 'this': {entry}"
            )
        if "objecttype" not in lower and "resourcename" not in lower:
            raise SuperMetricValidationError(
                f"{self.name}: resource entry must include 'objecttype=' "
                f"or 'resourcename=': {entry}"
            )
        if "metric=" not in lower and "attribute=" not in lower:
            raise SuperMetricValidationError(
                f"{self.name}: resource entry must include 'metric=' "
                f"or 'attribute=': {entry}"
            )


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

IdMinter = Callable[[Path], str]
ProvenanceFn = Callable[[Path], str]


def _resolve_id(path: Path, data: dict, on_missing_id: Optional[IdMinter]) -> str:
    """The super metric's ``id`` from ``data``, validated as a uuid4.

    A missing ``id`` is handed to ``on_missing_id`` (the factory mints one
    into the file and returns it); with no callback it is an error, because
    this module never writes to its input. The callback's return gets the
    same normalize-and-validate path as a YAML id.
    """
    sm_id = str(data.get("id", "") or "").strip().lower()
    source = "id"
    if not sm_id:
        if on_missing_id is None:
            raise SuperMetricValidationError(
                f"{path}: missing id (a uuid4); pass on_missing_id= to mint one"
            )
        sm_id = str(on_missing_id(path) or "").strip().lower()
        source = f"on_missing_id ({getattr(on_missing_id, '__name__', on_missing_id)!s})"
    if not _UUID_RE.match(sm_id):
        if source == "id":
            raise SuperMetricValidationError(
                f"{path}: id '{sm_id}' is not a valid uuid4"
            )
        raise SuperMetricValidationError(
            f"{path}: {source} gave '{sm_id}', which is not a valid uuid4"
        )
    return sm_id


def load_file(
    path: str | Path,
    enforce_framework_prefix: bool = True,
    *,
    on_missing_id: Optional[IdMinter] = None,
    provenance_of: Optional[ProvenanceFn] = None,
) -> SuperMetricDef:
    path = Path(path)
    try:
        data = _strict_load(path.read_text()) or {}
    except yaml.constructor.ConstructorError as exc:
        raise SuperMetricValidationError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SuperMetricValidationError(f"{path}: expected a YAML mapping")
    sm_id = _resolve_id(path, data, on_missing_id)
    raw_rks = data.get("resource_kinds") or []
    rks: list = []
    for rk in raw_rks:
        if not isinstance(rk, dict):
            raise SuperMetricValidationError(
                f"{path}: resource_kinds entries must be mappings"
            )
        rks.append(
            {
                "resourceKindKey": str(
                    rk.get("resource_kind_key") or rk.get("resourceKindKey") or ""
                ).strip(),
                "adapterKindKey": str(
                    rk.get("adapter_kind_key")
                    or rk.get("adapterKindKey")
                    or "VMWARE"
                ).strip(),
            }
        )
    released_raw = data.get("released", False)
    released = bool(released_raw) if isinstance(released_raw, bool) else False
    version = str(data.get("version", "1.0.0") or "1.0.0").strip() or "1.0.0"

    sm = SuperMetricDef(
        id=sm_id,
        name=str(data.get("name", "")).strip(),
        formula=str(data.get("formula", "")).strip(),
        description=str(data.get("description", "") or "").strip(),
        resource_kinds=rks,
        unit_id=str(data.get("unit_id", "") or data.get("unitId", "") or "").strip(),
        source_path=path,
        released=released,
        version=version,
        provenance=provenance_of(path) if provenance_of is not None else "",
    )
    sm.validate(enforce_framework_prefix=enforce_framework_prefix)
    return sm


def sm_id_map(
    sm_scope: Optional[Iterable[Path]],
    bundle_context: Optional[str] = None,
    *,
    on_missing_id: Optional[IdMinter] = None,
    provenance_of: Optional[ProvenanceFn] = None,
) -> dict[str, str]:
    """Super metric name to uuid map for the view renderer, from exactly the
    SM YAML files in ``sm_scope`` (M2 row 2 introduced the map, row 3 moved
    the scoped half here).

    ``vcfcf_core.dashboards.render`` takes this map as an argument and never
    looks for SM YAML itself. Each listed file is loaded with
    ``enforce_framework_prefix=False``; any load failure is re-raised as
    ``ValueError`` naming ``bundle_context`` so a bundle build fails with a
    clear message.

    ``sm_scope=None`` is an empty map: the library never scans a directory
    for SM YAML. The factory wrapper (``vcfcf_supermetrics.loader.sm_id_map``)
    keeps the pre-row-2 renderer's unscoped mode on top, scanning
    ``content/supermetrics`` then ``supermetrics`` under the working
    directory.
    """
    sm_map: dict[str, str] = {}
    if sm_scope is None:
        return sm_map
    try:
        for sm_path in sm_scope:
            sm = load_file(
                sm_path, enforce_framework_prefix=False,
                on_missing_id=on_missing_id, provenance_of=provenance_of,
            )
            sm_map[sm.name] = sm.id
    except Exception as exc:
        raise ValueError(
            f"sm_id_map: failed to load scoped SM for "
            f"bundle {bundle_context!r}: {exc}"
        ) from exc
    return sm_map


def load_dir(
    directory: str | Path,
    enforce_framework_prefix: bool = True,
    *,
    on_missing_id: Optional[IdMinter] = None,
    provenance_of: Optional[ProvenanceFn] = None,
) -> List[SuperMetricDef]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[SuperMetricDef] = []
    seen: dict[str, Path] = {}
    for p in sorted(directory.rglob("*.y*ml")):
        sm = load_file(
            p, enforce_framework_prefix=enforce_framework_prefix,
            on_missing_id=on_missing_id, provenance_of=provenance_of,
        )
        if sm.name in seen:
            raise SuperMetricValidationError(
                f"duplicate super metric name '{sm.name}' "
                f"in {p} and {seen[sm.name]}"
            )
        seen[sm.name] = p
        out.append(sm)
    return out
