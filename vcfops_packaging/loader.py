"""Load and validate bundle manifests from bundles/*.yaml.

A bundle manifest lists the YAML files that make up a distributable
package. The loader validates all referenced files exist, then loads each
content object using the existing per-type loaders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

from vcfops_supermetrics.loader import SuperMetricDef, load_file as load_sm
from vcfops_dashboards.loader import ViewDef, Dashboard, load_view, load_dashboard
from vcfops_customgroups.loader import CustomGroupDef, load_file as load_cg


class BundleValidationError(ValueError):
    pass


@dataclass
class Bundle:
    name: str
    description: str
    supermetrics: List[SuperMetricDef]
    views: List[ViewDef]
    dashboards: List[Dashboard]
    customgroups: List[CustomGroupDef]
    source_path: Path | None = None


def load_bundle(path: str | Path) -> Bundle:
    """Load a bundle manifest YAML and resolve all referenced content objects.

    Validates that all referenced files exist and loads each using the
    appropriate per-type loader (which also validates the content).

    Args:
        path: Path to a bundles/*.yaml manifest file.

    Returns:
        A populated Bundle dataclass.

    Raises:
        BundleValidationError: if the manifest is invalid or any referenced
            file is missing or fails content validation.
    """
    path = Path(path)
    if not path.exists():
        raise BundleValidationError(f"bundle manifest not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise BundleValidationError(f"{path}: expected a YAML mapping")

    name = str(data.get("name", "")).strip()
    if not name:
        raise BundleValidationError(f"{path}: 'name' is required")

    description = str(data.get("description", "") or "").strip()

    # Resolve all file references relative to the manifest's directory if
    # paths are not absolute. Manifests in bundles/ use repo-relative paths
    # (e.g. "supermetrics/foo.yaml") so we try the repo root first.
    repo_root = path.parent.parent  # bundles/ is one level under repo root

    def _resolve(ref: str) -> Path:
        p = Path(ref)
        if p.is_absolute() and p.exists():
            return p
        # Try repo-relative (most common: "supermetrics/foo.yaml")
        candidate = repo_root / p
        if candidate.exists():
            return candidate
        # Try manifest-relative as fallback
        candidate2 = path.parent / p
        if candidate2.exists():
            return candidate2
        raise BundleValidationError(
            f"{path}: referenced file not found: {ref!r} "
            f"(tried {candidate} and {candidate2})"
        )

    sm_paths = [_resolve(r) for r in (data.get("supermetrics") or [])]
    view_paths = [_resolve(r) for r in (data.get("views") or [])]
    dash_paths = [_resolve(r) for r in (data.get("dashboards") or [])]
    cg_paths = [_resolve(r) for r in (data.get("customgroups") or [])]

    # Load and validate each content object
    try:
        supermetrics = [load_sm(p) for p in sm_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: super metric error: {e}") from e

    try:
        views = [load_view(p) for p in view_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: view error: {e}") from e

    try:
        dashboards = [load_dashboard(p) for p in dash_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: dashboard error: {e}") from e

    # Cross-validate dashboards against loaded views
    views_by_name = {v.name: v for v in views}
    for d in dashboards:
        try:
            d.validate(views_by_name)
        except Exception as e:
            raise BundleValidationError(
                f"{path}: dashboard '{d.name}' cross-validation error: {e}"
            ) from e

    try:
        customgroups = [load_cg(p) for p in cg_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: custom group error: {e}") from e

    return Bundle(
        name=name,
        description=description,
        supermetrics=supermetrics,
        views=views,
        dashboards=dashboards,
        customgroups=customgroups,
        source_path=path,
    )


def load_all_bundles(bundles_dir: str | Path = "bundles") -> List[Bundle]:
    """Load all bundle manifests from a directory."""
    bundles_dir = Path(bundles_dir)
    if not bundles_dir.exists():
        return []
    bundles = []
    for p in sorted(bundles_dir.rglob("*.y*ml")):
        bundles.append(load_bundle(p))
    return bundles
