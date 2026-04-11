"""Load and validate bundle manifests from bundles/*.yaml.

A bundle manifest lists the YAML files that make up a distributable
package. The loader validates all referenced files exist, then loads each
content object using the existing per-type loaders.

Schema
------
name:         str  (required)
description:  str  (optional)
sync:         bool (optional, default true)
              When false, ``sync --all`` skips this bundle.
supermetrics: list[path]   (optional)
customgroups: list[path]   (optional)
views:        list[path]   (optional)
dashboards:   list[path]   (optional)
symptoms:         list[path]   (optional) -- requires vcfops_symptoms package
alerts:           list[path]   (optional) -- requires vcfops_alerts package
reports:          list[path]   (optional) -- requires vcfops_reports package
recommendations:  list[path]   (optional, reserved) -- scaffolding for future
                               recommendations content type; no authored content
                               uses this yet.  Loading accepts empty/missing value.

All content-type keys are optional.  A bundle may contain only super
metrics, only dashboards, or any subset of the supported types.

All content types listed in the manifest are fully parsed and validated
at load time.  Missing files or invalid YAML raise BundleValidationError.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from vcfops_supermetrics.loader import SuperMetricDef, load_file as load_sm
from vcfops_dashboards.loader import ViewDef, Dashboard, load_view, load_dashboard
from vcfops_customgroups.loader import CustomGroupDef, load_file as load_cg
from vcfops_reports.loader import ReportDef, load_file as load_report
from vcfops_symptoms.loader import SymptomDef, load_file as load_symptom
from vcfops_alerts.loader import AlertDef, load_file as load_alert


class BundleValidationError(ValueError):
    pass


@dataclass
class Bundle:
    name: str
    description: str
    sync_enabled: bool                           # False means skip in --all
    supermetrics: List[SuperMetricDef]
    views: List[ViewDef]
    dashboards: List[Dashboard]
    customgroups: List[CustomGroupDef]
    reports: List[ReportDef] = field(default_factory=list)
    symptoms: List[SymptomDef] = field(default_factory=list)
    alerts: List[AlertDef] = field(default_factory=list)
    # recommendations: reserved for future vcfops_recommendations content type.
    # Accepted as an empty/missing value; no loader or content type yet.
    recommendations: List[dict] = field(default_factory=list)
    source_path: Optional[Path] = None


def load_bundle(path: str | Path) -> Bundle:
    """Load a bundle manifest YAML and resolve all referenced content objects.

    Validates that all referenced files exist and loads each using the
    appropriate per-type loader (which also validates the content).

    For content types whose tooling package is not yet installed (symptoms,
    alerts), the files are verified to exist on disk but are not parsed —
    parsing is deferred to the handler at sync time.

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

    # sync: default true; explicit false means skip in --all
    sync_raw = data.get("sync", True)
    if not isinstance(sync_raw, bool):
        raise BundleValidationError(
            f"{path}: 'sync' must be a boolean (true/false), got {sync_raw!r}"
        )
    sync_enabled = bool(sync_raw)

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
    report_paths = [_resolve(r) for r in (data.get("reports") or [])]
    symptom_paths = [_resolve(r) for r in (data.get("symptoms") or [])]
    alert_paths = [_resolve(r) for r in (data.get("alerts") or [])]

    # recommendations: reserved key — no loader yet; accept empty/missing value.
    raw_recommendations = data.get("recommendations") or []
    if raw_recommendations and not isinstance(raw_recommendations, list):
        raise BundleValidationError(
            f"{path}: 'recommendations' must be a list (reserved key; "
            f"no content expected yet)"
        )

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

    try:
        reports = [load_report(p) for p in report_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: report error: {e}") from e

    try:
        symptoms = [load_symptom(p) for p in symptom_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: symptom error: {e}") from e

    try:
        alerts = [load_alert(p) for p in alert_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: alert error: {e}") from e

    return Bundle(
        name=name,
        description=description,
        sync_enabled=sync_enabled,
        supermetrics=supermetrics,
        views=views,
        dashboards=dashboards,
        customgroups=customgroups,
        reports=reports,
        symptoms=symptoms,
        alerts=alerts,
        recommendations=list(raw_recommendations),
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
