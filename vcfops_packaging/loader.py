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
recommendations:  list[path]   (optional) -- recommendation definitions under
                               recommendations/*.yaml.  Loaded and validated
                               at bundle load time; included in AlertContent.xml.
builtin_metric_enables: list (optional) -- built-in metrics to enable on the
                               Default Policy at install time.  Each entry:
                               adapter_kind: str (required) -- e.g. "VMWARE"
                               resource_kind: str (required) -- e.g. "VirtualMachine"
                               metric_key: str (required) -- e.g. "net|packetsPerSec"
                               reason: str (optional) -- human-readable explanation

Attribution and provenance (all optional; for extracted/third-party bundles):
author:         str  (optional) -- attribution line, e.g. "Scott Bowe"
license:        str  (optional) -- SPDX id or free-form, e.g. "MIT", "Proprietary"
source:         dict (optional) -- provenance block:
                               url: str           -- source URL
                               version: str       -- version string
                               captured_at: str   -- ISO date of extraction
                               captured_from_host: str -- source instance hostname
factory_native: bool (optional, default true)
                               False = extracted/third-party content; skips
                               [VCF Content Factory] prefix enforcement and
                               uses display_name for the zip filename.
display_name:   str  (optional) -- explicit display name for README and zip
                               filename when factory_native is False.
design:         str  (optional) -- path to design artifact (relative to repo
                               root), e.g. "designs/capacity-assessment.md".
                               When absent, the builder tries the convention-
                               based path "designs/<bundle-name>.md".

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
from vcfops_alerts.loader import (
    AlertDef, load_file as load_alert,
    Recommendation, load_recommendation_file,
)


class BundleValidationError(ValueError):
    pass


@dataclass
class BuiltinMetricEnable:
    """A single built-in metric enablement declaration."""
    adapter_kind: str
    resource_kind: str
    metric_key: str
    reason: str = ""


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
    recommendations: List[Recommendation] = field(default_factory=list)
    builtin_metric_enables: List[BuiltinMetricEnable] = field(default_factory=list)
    source_path: Optional[Path] = None
    # Resolved absolute paths to the SM YAML files declared in this bundle's
    # manifest.  Preserved so the renderer can scope SM name resolution to
    # exactly the SMs in this bundle, preventing cross-bundle UUID leakage.
    sm_paths: List[Path] = field(default_factory=list)
    # Attribution and provenance fields (all optional; default to empty/True
    # so existing factory-native manifests load unchanged).
    author: str = ""
    license: str = ""
    source: dict = field(default_factory=dict)
    factory_native: bool = True
    display_name: str = ""
    design: str = ""  # explicit design artifact path from manifest (optional)


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

    # factory_native is read early because it controls SM prefix enforcement
    # during content loading below.  Full validation with a clear error
    # message is done again later (after all paths are resolved).
    factory_native_raw = data.get("factory_native", True)
    factory_native = bool(factory_native_raw) if isinstance(factory_native_raw, bool) else True

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

    # Validate and load builtin_metric_enables (inline list, not file paths).
    raw_bme = data.get("builtin_metric_enables") or []
    if not isinstance(raw_bme, list):
        raise BundleValidationError(
            f"{path}: 'builtin_metric_enables' must be a list, got {type(raw_bme).__name__}"
        )
    builtin_metric_enables = []
    for i, entry in enumerate(raw_bme):
        if not isinstance(entry, dict):
            raise BundleValidationError(
                f"{path}: builtin_metric_enables[{i}] must be a mapping, "
                f"got {type(entry).__name__}"
            )
        for required_field in ("adapter_kind", "resource_kind", "metric_key"):
            val = entry.get(required_field)
            if not val or not isinstance(val, str) or not val.strip():
                raise BundleValidationError(
                    f"{path}: builtin_metric_enables[{i}].{required_field} "
                    f"is required and must be a non-empty string"
                )
        reason = entry.get("reason", "") or ""
        if not isinstance(reason, str):
            raise BundleValidationError(
                f"{path}: builtin_metric_enables[{i}].reason must be a string"
            )
        builtin_metric_enables.append(BuiltinMetricEnable(
            adapter_kind=entry["adapter_kind"].strip(),
            resource_kind=entry["resource_kind"].strip(),
            metric_key=entry["metric_key"].strip(),
            reason=reason.strip(),
        ))

    sm_paths = [_resolve(r) for r in (data.get("supermetrics") or [])]
    view_paths = [_resolve(r) for r in (data.get("views") or [])]
    dash_paths = [_resolve(r) for r in (data.get("dashboards") or [])]
    cg_paths = [_resolve(r) for r in (data.get("customgroups") or [])]
    report_paths = [_resolve(r) for r in (data.get("reports") or [])]
    symptom_paths = [_resolve(r) for r in (data.get("symptoms") or [])]
    alert_paths = [_resolve(r) for r in (data.get("alerts") or [])]
    recommendation_paths = [_resolve(r) for r in (data.get("recommendations") or [])]

    # Load and validate each content object.
    # For third-party (factory_native=False) bundles, SM names are not required
    # to carry the "[VCF Content Factory]" prefix — they use the original author's
    # naming convention.  Skip prefix enforcement for those bundles.
    try:
        supermetrics = [load_sm(p, enforce_framework_prefix=factory_native) for p in sm_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: super metric error: {e}") from e

    try:
        views = [load_view(p, enforce_framework_prefix=factory_native) for p in view_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: view error: {e}") from e

    # For third-party bundles (factory_native=False), don't force dashboards
    # into the "VCF Content Factory" folder.  Use an empty default_name_path
    # so only an explicit name_path: field in the YAML places them in a folder.
    dash_default_name_path = "VCF Content Factory" if factory_native else ""
    try:
        dashboards = [load_dashboard(p, enforce_framework_prefix=factory_native, default_name_path=dash_default_name_path) for p in dash_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: dashboard error: {e}") from e

    # Cross-validate dashboards against loaded views
    views_by_name = {v.name: v for v in views}
    for d in dashboards:
        try:
            d.validate(views_by_name, enforce_framework_prefix=factory_native)
        except Exception as e:
            raise BundleValidationError(
                f"{path}: dashboard '{d.name}' cross-validation error: {e}"
            ) from e

    try:
        customgroups = [load_cg(p, enforce_framework_prefix=factory_native) for p in cg_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: custom group error: {e}") from e

    try:
        reports = [load_report(p, enforce_framework_prefix=factory_native) for p in report_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: report error: {e}") from e

    try:
        symptoms = [load_symptom(p, enforce_framework_prefix=factory_native) for p in symptom_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: symptom error: {e}") from e

    try:
        alerts = [load_alert(p, enforce_framework_prefix=factory_native) for p in alert_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: alert error: {e}") from e

    try:
        recommendations = [load_recommendation_file(p, enforce_framework_prefix=factory_native) for p in recommendation_paths]
    except Exception as e:
        raise BundleValidationError(f"{path}: recommendation error: {e}") from e

    # --- Attribution and provenance fields (all optional) ---
    author = str(data.get("author", "") or "").strip()
    license_field = str(data.get("license", "") or "").strip()

    source_raw = data.get("source")
    if source_raw is not None and not isinstance(source_raw, dict):
        raise BundleValidationError(
            f"{path}: 'source' must be a mapping, got {type(source_raw).__name__}"
        )
    source = dict(source_raw) if source_raw else {}

    factory_native_raw = data.get("factory_native", True)
    if not isinstance(factory_native_raw, bool):
        raise BundleValidationError(
            f"{path}: 'factory_native' must be a boolean (true/false), "
            f"got {factory_native_raw!r}"
        )
    factory_native = bool(factory_native_raw)

    display_name = str(data.get("display_name", "") or "").strip()

    design = str(data.get("design", "") or "").strip()

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
        recommendations=recommendations,
        builtin_metric_enables=builtin_metric_enables,
        source_path=path,
        sm_paths=sm_paths,
        author=author,
        license=license_field,
        source=source,
        factory_native=factory_native,
        display_name=display_name,
        design=design,
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
