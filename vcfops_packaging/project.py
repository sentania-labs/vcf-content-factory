"""Load and validate third-party PROJECT.yaml files.

Every ``third_party/<project>/PROJECT.yaml`` describes a third-party content
project housed in this repo.  This module provides:

  - Schema validation for individual PROJECT.yaml files.
  - Discovery of all third-party projects under a given ``third_party/`` root.
  - Slug-uniqueness enforcement across both ``content/<type>/`` and
    ``third_party/*/<type>/`` provenances.
  - Project-membership boundary check: a third-party dashboard must not pull
    in deps (views, super metrics, custom groups) that live outside its own
    ``third_party/<project>/`` subtree.

Schema (required unless noted)
-------------------------------
name:             str  -- slug, must match the parent directory name
display_name:     str  -- human-readable project name
factory_native:   bool -- must be literal false (third-party always false)
author:           str  -- comma-separated attribution string
license:          str  -- SPDX id or free-form (MIT, Apache-2.0, etc.)
description:      str  -- elevator-pitch description

Optional fields
---------------
source:             dict  -- provenance block
  captured_at:      str   -- ISO date string
  origin:           str   -- extraction method or tool
  upstream:         str   -- source URL or reference
builtin_metric_enables: list[dict]  -- OOTB metrics required by this project
  adapter_kind:     str   (required in each entry)
  resource_kind:    str   (required in each entry)
  metric_key:       str   (required in each entry)
  reason:           str   (required in each entry)
released:           bool  -- publish gate flag
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


class ProjectValidationError(ValueError):
    """Raised when a PROJECT.yaml fails schema validation.

    The ``loc`` attribute points to the failing file so callers can produce
    actionable error messages.
    """
    def __init__(self, message: str, loc: Optional[Path] = None) -> None:
        super().__init__(message)
        self.loc = loc


@dataclass
class BuiltinMetricEnable:
    adapter_kind: str
    resource_kind: str
    metric_key: str
    reason: str = ""


@dataclass
class ProjectDef:
    """Parsed and validated representation of a third-party PROJECT.yaml."""
    name: str
    display_name: str
    factory_native: bool          # always False for third-party
    author: str
    license: str
    description: str
    source: dict = field(default_factory=dict)
    builtin_metric_enables: List[BuiltinMetricEnable] = field(default_factory=list)
    released: bool = False
    source_path: Optional[Path] = None


def load_project(path: str | Path) -> ProjectDef:
    """Load and validate a single PROJECT.yaml file.

    Args:
        path: Absolute or relative path to a ``PROJECT.yaml`` file.

    Returns:
        A validated :class:`ProjectDef`.

    Raises:
        :class:`ProjectValidationError`: when the file is missing, not a
            mapping, or any required field fails its constraint.
    """
    path = Path(path)
    if not path.exists():
        raise ProjectValidationError(
            f"PROJECT.yaml not found: {path}", loc=path
        )

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ProjectValidationError(
            f"{path}: YAML parse error: {exc}", loc=path
        ) from exc

    if not isinstance(data, dict):
        raise ProjectValidationError(
            f"{path}: expected a YAML mapping, got {type(data).__name__}", loc=path
        )

    # ---- name ----
    name = str(data.get("name", "") or "").strip()
    if not name:
        raise ProjectValidationError(
            f"{path}: 'name' is required and must be non-empty", loc=path
        )
    expected_dir_name = path.parent.name
    if name != expected_dir_name:
        raise ProjectValidationError(
            f"{path}: 'name' must match the parent directory name. "
            f"Got {name!r} but directory is {expected_dir_name!r}",
            loc=path,
        )

    # ---- display_name ----
    display_name = str(data.get("display_name", "") or "").strip()
    if not display_name:
        raise ProjectValidationError(
            f"{path}: 'display_name' is required and must be non-empty", loc=path
        )

    # ---- factory_native ----
    factory_native_raw = data.get("factory_native", _MISSING)
    if factory_native_raw is _MISSING:
        raise ProjectValidationError(
            f"{path}: 'factory_native' is required and must be false", loc=path
        )
    if not isinstance(factory_native_raw, bool):
        raise ProjectValidationError(
            f"{path}: 'factory_native' must be a boolean (true/false), "
            f"got {factory_native_raw!r}",
            loc=path,
        )
    if factory_native_raw is not False:
        raise ProjectValidationError(
            f"{path}: 'factory_native' must be false for third-party projects "
            f"(got {factory_native_raw!r})",
            loc=path,
        )

    # ---- author ----
    author = str(data.get("author", "") or "").strip()
    if not author:
        raise ProjectValidationError(
            f"{path}: 'author' is required and must be non-empty", loc=path
        )

    # ---- license ----
    license_val = str(data.get("license", "") or "").strip()
    if not license_val:
        raise ProjectValidationError(
            f"{path}: 'license' is required and must be non-empty", loc=path
        )

    # ---- description ----
    description = str(data.get("description", "") or "").strip()
    if not description:
        raise ProjectValidationError(
            f"{path}: 'description' is required and must be non-empty", loc=path
        )

    # ---- source (optional dict) ----
    source_raw = data.get("source")
    if source_raw is not None and not isinstance(source_raw, dict):
        raise ProjectValidationError(
            f"{path}: 'source' must be a mapping, got {type(source_raw).__name__}",
            loc=path,
        )
    source = dict(source_raw) if source_raw else {}

    # ---- builtin_metric_enables (optional list of dicts) ----
    raw_bme = data.get("builtin_metric_enables") or []
    if not isinstance(raw_bme, list):
        raise ProjectValidationError(
            f"{path}: 'builtin_metric_enables' must be a list, "
            f"got {type(raw_bme).__name__}",
            loc=path,
        )
    bme_list: List[BuiltinMetricEnable] = []
    for i, entry in enumerate(raw_bme):
        if not isinstance(entry, dict):
            raise ProjectValidationError(
                f"{path}: builtin_metric_enables[{i}] must be a mapping, "
                f"got {type(entry).__name__}",
                loc=path,
            )
        for required_field in ("adapter_kind", "resource_kind", "metric_key", "reason"):
            val = entry.get(required_field)
            if val is None or not isinstance(val, str) or not str(val).strip():
                raise ProjectValidationError(
                    f"{path}: builtin_metric_enables[{i}].{required_field} "
                    f"is required and must be a non-empty string",
                    loc=path,
                )
        bme_list.append(BuiltinMetricEnable(
            adapter_kind=entry["adapter_kind"].strip(),
            resource_kind=entry["resource_kind"].strip(),
            metric_key=entry["metric_key"].strip(),
            reason=entry["reason"].strip(),
        ))

    # ---- released (optional bool) ----
    released_raw = data.get("released", False)
    if not isinstance(released_raw, bool):
        raise ProjectValidationError(
            f"{path}: 'released' must be a boolean (true/false), "
            f"got {released_raw!r}",
            loc=path,
        )

    return ProjectDef(
        name=name,
        display_name=display_name,
        factory_native=bool(factory_native_raw),
        author=author,
        license=license_val,
        description=description,
        source=source,
        builtin_metric_enables=bme_list,
        released=bool(released_raw),
        source_path=path,
    )


# Sentinel for detecting a missing key vs. an explicit None/false value.
_MISSING = object()


_CONTENT_TYPE_DIRS = frozenset({
    "supermetrics", "views", "dashboards", "customgroups",
    "alerts", "symptoms", "reports", "recommendations",
    "managementpacks",
})


def _has_content_subdirs(project_dir: Path) -> bool:
    """Return True if ``project_dir`` contains at least one recognised content
    type subdirectory (e.g. ``dashboards/``, ``views/``, etc.)."""
    for child in project_dir.iterdir():
        if child.is_dir() and child.name in _CONTENT_TYPE_DIRS:
            return True
    return False


def load_all_projects(third_party_dir: str | Path = "third_party") -> List[ProjectDef]:
    """Load and validate all PROJECT.yaml files found under ``third_party_dir``.

    Scans immediate subdirectories of ``third_party_dir`` for PROJECT.yaml files.
    A subdirectory that contains at least one recognised content-type directory
    (dashboards/, views/, etc.) must have a PROJECT.yaml — its absence is an
    error.  Subdirectories with no recognised content-type dirs are skipped
    (they may be scratch/debug directories, not content projects).

    Args:
        third_party_dir: Root of the third-party project tree.

    Returns:
        List of :class:`ProjectDef` objects, sorted by project name.

    Raises:
        :class:`ProjectValidationError`: if any PROJECT.yaml fails validation
            OR if a content-bearing project directory is missing its
            PROJECT.yaml.
    """
    third_party_dir = Path(third_party_dir)
    if not third_party_dir.exists():
        return []

    projects: List[ProjectDef] = []
    for entry in sorted(third_party_dir.iterdir()):
        if not entry.is_dir():
            continue
        project_yaml = entry / "PROJECT.yaml"
        if not project_yaml.exists():
            # Only error if the directory actually contains content.
            if _has_content_subdirs(entry):
                raise ProjectValidationError(
                    f"third_party/{entry.name}/ contains content but is missing "
                    f"PROJECT.yaml — every content-bearing third-party project "
                    f"must have an attribution file",
                    loc=project_yaml,
                )
            # Otherwise it's a scratch/debug directory; skip silently.
            continue
        projects.append(load_project(project_yaml))

    return projects


# ---------------------------------------------------------------------------
# Slug uniqueness across both provenances
# ---------------------------------------------------------------------------

def check_slug_uniqueness(
    content_type: str,
    content_type_dir: str | Path,
    third_party_dir: str | Path = "third_party",
) -> List[str]:
    """Check that no YAML filename stem (slug) appears in more than one location
    for a given content type.

    Scans:
      - ``<content_type_dir>/`` (factory-native)
      - ``<third_party_dir>/*/<content_type>/`` (all third-party projects)

    Returns a list of error message strings (empty = all clear).

    Args:
        content_type:     Directory name for the type (e.g. ``"dashboards"``).
        content_type_dir: The factory-native content directory (e.g.
                          ``Path("content/dashboards")``).
        third_party_dir:  Root of the third-party tree (default ``"third_party"``).
    """
    content_type_dir = Path(content_type_dir)
    third_party_dir = Path(third_party_dir)

    # slug -> list of paths that contain it
    slug_paths: dict[str, List[Path]] = {}

    def _collect(directory: Path) -> None:
        if not directory.exists():
            return
        for p in sorted(directory.rglob("*.y*ml")):
            slug = p.stem
            slug_paths.setdefault(slug, []).append(p)

    # Factory-native content
    _collect(content_type_dir)

    # Third-party projects
    if third_party_dir.exists():
        for project_dir in sorted(third_party_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            _collect(project_dir / content_type)

    errors: List[str] = []
    for slug, paths in sorted(slug_paths.items()):
        if len(paths) > 1:
            path_list = ", ".join(str(p) for p in paths)
            errors.append(
                f"duplicate {content_type} slug {slug!r}: found in {path_list}"
            )
    return errors


# ---------------------------------------------------------------------------
# Project-membership boundary check
# ---------------------------------------------------------------------------

def check_project_membership(
    dashboards: "list",
    all_views: "list",
    all_supermetrics: "list",
    all_customgroups: "list",
    third_party_dir: str | Path = "third_party",
) -> List[str]:
    """Check that third-party dashboards only pull in deps from their own project.

    For each dashboard whose ``source_path`` lives under
    ``third_party/<project>/``, every dependency it pulls in (views, super
    metrics, custom groups) must also live under ``third_party/<project>/``.

    Cross-project deps (third-party A using third-party B's view, or any
    third-party component using a factory-native dep) are errors.

    Factory-native dashboards (``content/dashboards/``) are unconstrained —
    they may reference any factory-native component freely.

    Args:
        dashboards:      All loaded Dashboard objects (source_path required).
        all_views:       All loaded ViewDef objects.
        all_supermetrics: All loaded SuperMetricDef objects.
        all_customgroups: All loaded CustomGroupDef objects.
        third_party_dir: Root of the third-party tree.

    Returns:
        A list of error message strings.  Empty = all clear.
    """
    from vcfops_common.dep_walker import collect_deps

    third_party_dir = Path(third_party_dir).resolve()

    errors: List[str] = []

    for dash in dashboards:
        dash_path = getattr(dash, "source_path", None)
        if dash_path is None:
            continue
        dash_path = Path(dash_path).resolve()

        # Only check dashboards that live under third_party/
        try:
            rel = dash_path.relative_to(third_party_dir)
        except ValueError:
            continue  # factory-native — skip

        # Project root is the immediate child of third_party_dir
        project_name = rel.parts[0]
        project_root = third_party_dir / project_name

        # Walk deps for this single dashboard
        graph = collect_deps(
            dashboards=[dash],
            all_views=all_views,
            all_sms=all_supermetrics,
            all_customgroups=all_customgroups,
        )

        # Check views
        for view in graph.views:
            view_path = getattr(view, "source_path", None)
            if view_path is None:
                continue
            view_path = Path(view_path).resolve()
            if not _is_under(view_path, project_root):
                errors.append(
                    f"dashboard {dash_path.name!r} (project {project_name!r}) "
                    f"pulls in view {view.name!r} from outside its project: "
                    f"{view_path}"
                )

        # Check super metrics
        for sm in graph.supermetrics:
            sm_path = getattr(sm, "source_path", None)
            if sm_path is None:
                continue
            sm_path = Path(sm_path).resolve()
            if not _is_under(sm_path, project_root):
                errors.append(
                    f"dashboard {dash_path.name!r} (project {project_name!r}) "
                    f"pulls in super metric {sm.name!r} from outside its project: "
                    f"{sm_path}"
                )

        # Check custom groups
        for cg in graph.customgroups:
            cg_path = getattr(cg, "source_path", None)
            if cg_path is None:
                continue
            cg_path = Path(cg_path).resolve()
            if not _is_under(cg_path, project_root):
                errors.append(
                    f"dashboard {dash_path.name!r} (project {project_name!r}) "
                    f"pulls in custom group {cg.name!r} from outside its project: "
                    f"{cg_path}"
                )

    return errors


def _is_under(path: Path, root: Path) -> bool:
    """Return True if ``path`` is under ``root`` (inclusive)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
