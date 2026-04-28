"""Build self-contained discrete artifact zips for individually-released content items.

A discrete artifact is a self-contained installable zip carrying the item and its
transitive dependencies.  Layout mirrors the bundle zip format produced by builder.py:

    install.py
    install.ps1
    README.md
    LICENSE
    bundles/<slug>/
        bundle.json
        README.md
        supermetric.json       (if any SMs)
        Views.zip              (if any views)
        Dashboard.zip          (if any dashboards)
        AlertContent.xml       (if any alerts/symptoms/recommendations)
        Reports.zip            (if any reports)
        customgroup.json       (if any custom groups)
        content/
          supermetrics.json
          views_content.xml
          dashboard.json
          customgroup.json
          reports_content.xml
          symptoms.json
          alerts.json

Usage::

    python3 -m vcfops_packaging build-discrete <content-type> <item-name-or-path>

Content types (case-insensitive): supermetric, dashboard, view, report, alert, customgroup

Dependency resolution:
  - dashboard  -> all views referenced by its widgets; all SMs referenced by those views
  - view       -> all SMs referenced in its column attributes
  - report     -> all views + dashboards referenced by its sections; transitively SMs
  - alert      -> all symptoms referenced in its symptom_sets; all recommendations referenced
  - supermetric, customgroup -> standalone (no external deps resolved here)
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import List, Optional

from vcfops_supermetrics.loader import SuperMetricDef, load_dir as load_sm_dir
from vcfops_dashboards.loader import ViewDef, Dashboard
from vcfops_customgroups.loader import CustomGroupDef, load_dir as load_cg_dir
from vcfops_reports.loader import ReportDef, load_dir as _load_reports_dir
from vcfops_symptoms.loader import SymptomDef, load_dir as load_symptom_dir
from vcfops_alerts.loader import (
    AlertDef, load_dir as load_alert_dir,
    Recommendation, load_recommendations,
)
from vcfops_dashboards.render import render_views_xml, render_dashboards_bundle_json
from vcfops_reports.render import render_report_xml
from vcfops_alerts.render import render_alert_content_xml
from .builder import (
    _render_supermetrics_dict,
    _build_views_inner_zip,
    _build_dashboard_dropin_zip,
    _build_reports_dropin_zip,
    _render_customgroup_rest_payload,
    _render_customgroup_ui_payload,
    PLACEHOLDER_USER_ID,
)
from .loader import Bundle, BuiltinMetricEnable
from .template_version import CURRENT_TEMPLATE_VERSION

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_REPO_ROOT = Path(__file__).parent.parent

# Supported content types
DISCRETE_TYPES = {
    "supermetric", "dashboard", "view", "report", "alert", "customgroup",
}

# Wire name for each type used in slug and bundle.json
_TYPE_SLUG = {
    "supermetric": "supermetric",
    "dashboard": "dashboard",
    "view": "view",
    "report": "report",
    "alert": "alert",
    "customgroup": "customgroup",
}


class DiscreteBuilderError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Dependency resolution helpers
# ---------------------------------------------------------------------------

def _sm_key_to_name(attr: str, sm_by_id: dict[str, SuperMetricDef]) -> Optional[str]:
    """Extract SM name from a view column attribute like 'Super Metric|sm_<uuid>' or 'sm_<uuid>'."""
    m = re.search(r"sm_([0-9a-f\-]{36})", attr, re.IGNORECASE)
    if not m:
        return None
    sm_id = m.group(1).lower()
    sm = sm_by_id.get(sm_id)
    return sm.name if sm else None


def _resolve_view_deps(view: ViewDef, all_sms: List[SuperMetricDef]) -> List[SuperMetricDef]:
    """Return SMs referenced by this view's column attributes."""
    sm_by_id = {sm.id.lower(): sm for sm in all_sms}
    result = []
    seen = set()
    for col in view.columns:
        m = re.search(r"sm_([0-9a-f\-]{36})", col.attribute, re.IGNORECASE)
        if m:
            sm_id = m.group(1).lower()
            if sm_id not in seen:
                sm = sm_by_id.get(sm_id)
                if sm:
                    result.append(sm)
                    seen.add(sm_id)
    return result


def _resolve_dashboard_deps(
    dashboard: Dashboard,
    all_views: List[ViewDef],
    all_sms: List[SuperMetricDef],
) -> tuple[List[ViewDef], List[SuperMetricDef]]:
    """Return (views, sms) needed by this dashboard."""
    view_by_name = {v.name: v for v in all_views}
    needed_views: dict[str, ViewDef] = {}
    needed_sms: dict[str, SuperMetricDef] = {}
    for widget in dashboard.widgets:
        if widget.view_name and widget.view_name in view_by_name:
            view = view_by_name[widget.view_name]
            if view.name not in needed_views:
                needed_views[view.name] = view
                for sm in _resolve_view_deps(view, all_sms):
                    needed_sms[sm.id] = sm
    return list(needed_views.values()), list(needed_sms.values())


def _resolve_report_deps(
    report: ReportDef,
    all_views: List[ViewDef],
    all_dashboards: List[Dashboard],
    all_sms: List[SuperMetricDef],
) -> tuple[List[ViewDef], List[Dashboard], List[SuperMetricDef]]:
    """Return (views, dashboards, sms) needed by this report."""
    view_by_name = {v.name: v for v in all_views}
    dash_by_name = {d.name: d for d in all_dashboards}
    needed_views: dict[str, ViewDef] = {}
    needed_dashboards: dict[str, Dashboard] = {}
    needed_sms: dict[str, SuperMetricDef] = {}
    for sec in report.sections:
        if sec.view_name and sec.view_name in view_by_name:
            view = view_by_name[sec.view_name]
            if view.name not in needed_views:
                needed_views[view.name] = view
                for sm in _resolve_view_deps(view, all_sms):
                    needed_sms[sm.id] = sm
        if sec.dashboard_name and sec.dashboard_name in dash_by_name:
            dash = dash_by_name[sec.dashboard_name]
            if dash.name not in needed_dashboards:
                needed_dashboards[dash.name] = dash
                views, sms = _resolve_dashboard_deps(dash, all_views, all_sms)
                for v in views:
                    needed_views[v.name] = v
                for sm in sms:
                    needed_sms[sm.id] = sm
    return list(needed_views.values()), list(needed_dashboards.values()), list(needed_sms.values())


def _resolve_alert_deps(
    alert: AlertDef,
    all_symptoms: List[SymptomDef],
    all_recommendations: List[Recommendation],
) -> tuple[List[SymptomDef], List[Recommendation]]:
    """Return (symptoms, recommendations) needed by this alert."""
    symptom_by_name = {s.name: s for s in all_symptoms}
    rec_by_name = {r.name: r for r in all_recommendations}

    needed_syms: dict[str, SymptomDef] = {}
    needed_recs: dict[str, Recommendation] = {}

    # Walk symptom_sets structure: {set_id: {symptom_set_operator, symptom_definitions: [{name, ...}]}}
    ss = alert.symptom_sets or {}
    for _set_id, ss_val in ss.items():
        if not isinstance(ss_val, dict):
            continue
        for sd in (ss_val.get("symptom_definitions") or []):
            sym_name = sd.get("name", "") if isinstance(sd, dict) else ""
            if sym_name and sym_name in symptom_by_name:
                needed_syms[sym_name] = symptom_by_name[sym_name]

    for ref in (alert.recommendations or []):
        if ref.name in rec_by_name:
            needed_recs[ref.name] = rec_by_name[ref.name]

    return list(needed_syms.values()), list(needed_recs.values())


# ---------------------------------------------------------------------------
# Bundle fabrication
# ---------------------------------------------------------------------------

def _make_synthetic_bundle(
    *,
    slug: str,
    name: str,
    description: str,
    supermetrics: List[SuperMetricDef] = None,
    views: List[ViewDef] = None,
    dashboards: List[Dashboard] = None,
    customgroups: List[CustomGroupDef] = None,
    reports: List[ReportDef] = None,
    symptoms: List[SymptomDef] = None,
    alerts: List[AlertDef] = None,
    recommendations: List[Recommendation] = None,
    sm_paths: List[Path] = None,
) -> Bundle:
    """Fabricate a Bundle dataclass for use with the rendering helpers."""
    return Bundle(
        name=slug,
        description=description,
        sync_enabled=True,
        supermetrics=supermetrics or [],
        views=views or [],
        dashboards=dashboards or [],
        customgroups=customgroups or [],
        reports=reports or [],
        symptoms=symptoms or [],
        alerts=alerts or [],
        recommendations=recommendations or [],
        builtin_metric_enables=[],
        source_path=None,
        sm_paths=sm_paths or [],
        factory_native=True,
        released=True,
    )


# ---------------------------------------------------------------------------
# README generation
# ---------------------------------------------------------------------------

def _generate_discrete_readme(
    item_type: str,
    item_name: str,
    description: str,
    version: str,
    bundle: Bundle,
) -> str:
    lines = [
        f"# {item_name}",
        "",
        f"**Type:** {item_type.title()}  ",
        f"**Version:** {version}  ",
        "",
    ]
    if description:
        lines += [description, ""]

    lines += ["## Contents", ""]
    if bundle.supermetrics:
        lines.append(f"**Super metrics ({len(bundle.supermetrics)}):**")
        lines.append("")
        for sm in bundle.supermetrics:
            lines.append(f"- {sm.name}")
        lines.append("")
    if bundle.views:
        lines.append(f"**Views ({len(bundle.views)}):**")
        lines.append("")
        for v in bundle.views:
            lines.append(f"- {v.name}")
        lines.append("")
    if bundle.dashboards:
        lines.append(f"**Dashboards ({len(bundle.dashboards)}):**")
        lines.append("")
        for d in bundle.dashboards:
            lines.append(f"- {d.name}")
        lines.append("")
    if bundle.customgroups:
        lines.append(f"**Custom groups ({len(bundle.customgroups)}):**")
        lines.append("")
        for cg in bundle.customgroups:
            lines.append(f"- {cg.name}")
        lines.append("")
    if bundle.symptoms:
        lines.append(f"**Symptoms ({len(bundle.symptoms)}):**")
        lines.append("")
        for s in bundle.symptoms:
            lines.append(f"- {s.name}")
        lines.append("")
    if bundle.alerts:
        lines.append(f"**Alerts ({len(bundle.alerts)}):**")
        lines.append("")
        for a in bundle.alerts:
            lines.append(f"- {a.name}")
        lines.append("")

    lines += [
        "## Installation",
        "",
        "Run the installer from the **package root** (two levels up from this file):",
        "",
        "**Python (recommended):**",
        "```",
        "python3 ../../install.py",
        "```",
        "",
        "**PowerShell:**",
        "```powershell",
        "..\\..\\install.ps1",
        "```",
        "",
        "> **Policy enablement caveat.** The install script enables imported super",
        "> metrics on the **Default Policy** only. If your deployment uses",
        "> non-default, non-inheriting policies, you may need to manually enable the",
        "> imported super metrics in those policies — otherwise dashboard cells and",
        "> view columns that depend on those metrics will appear blank for resources",
        "> scoped under those policies. Check `Administration > Policies` after",
        "> install to confirm enablement on every policy that needs to see the",
        "> bundle's data.",
        "",
        "## Manual import (drag-drop)",
        "",
        "Files in this directory use community-native filenames for per-object UI import:",
        "",
        "| File | VCF Ops UI dialog |",
        "|---|---|",
        "| `supermetric.json` | Administration > Super Metrics > Import |",
        "| `Views.zip` | Manage > Views > Import |",
        "| `Dashboard.zip` | Manage > Dashboards > Import |",
        "| `customgroup.json` | Environment > Custom Groups > Import |",
        "| `AlertContent.xml` | Alerts > Alert Definitions > Import |",
        "| `Reports.zip` | Administration > Content > Reports > Import |",
        "",
        "## Uninstallation",
        "",
        "**Python:**",
        "```",
        "python3 ../../install.py --uninstall",
        "```",
        "",
        "**PowerShell:**",
        "```powershell",
        "..\\..\\install.ps1 -Uninstall",
        "```",
        "",
        "---",
        "_Generated by vcfops_packaging. Part of the VCF Content Factory framework._",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main build entry point
# ---------------------------------------------------------------------------

def build_discrete(
    content_type: str,
    item_name: str,
    output_dir: str | Path = "dist/discrete",
    extra_search_dirs: "list[Path] | None" = None,
) -> Path:
    """Build a self-contained discrete artifact zip for a single released content item.

    Args:
        content_type:       One of: supermetric, dashboard, view, report, alert, customgroup.
        item_name:          The ``name`` field of the content item (exact match required).
        output_dir:         Directory where the output zip is written.
        extra_search_dirs:  Optional list of additional project root directories to scan
                            for the item and its dependencies *before* the factory-native
                            ``content/`` tree.  Each directory is expected to contain
                            sub-directories named after content types (``supermetrics/``,
                            ``views/``, ``dashboards/``, etc.) following the same layout as
                            a third-party project root (e.g. ``third_party/idps-planner/``).

    Returns:
        Path to the built zip file.

    Raises:
        DiscreteBuilderError: If the item is not found or content_type is unsupported.
    """
    ct = content_type.lower().strip()
    if ct not in DISCRETE_TYPES:
        raise DiscreteBuilderError(
            f"Unsupported content type {content_type!r}. "
            f"Must be one of: {', '.join(sorted(DISCRETE_TYPES))}"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all content — extra_search_dirs content is prepended so it takes
    # priority when resolving the target item and its dependencies.
    all_sms = _load_all_sms(extra_search_dirs=extra_search_dirs)
    all_views, all_dashboards = _load_all_views_and_dashboards(extra_search_dirs=extra_search_dirs)
    all_cgs = _load_all_customgroups(extra_search_dirs=extra_search_dirs)
    all_reports = _load_all_reports(extra_search_dirs=extra_search_dirs)
    all_symptoms = _load_all_symptoms(extra_search_dirs=extra_search_dirs)
    all_recommendations = _load_all_recommendations(extra_search_dirs=extra_search_dirs)
    all_alerts = _load_all_alerts(extra_search_dirs=extra_search_dirs)

    if ct == "supermetric":
        item = _find_by_name(item_name, all_sms, "super metric")
        version = item.version
        description = item.description
        bundle = _make_synthetic_bundle(
            slug=_item_slug(item_name),
            name=item_name,
            description=description,
            supermetrics=[item],
            sm_paths=[item.source_path] if item.source_path else [],
        )

    elif ct == "view":
        item = _find_by_name(item_name, all_views, "view")
        version = item.version
        description = item.description
        dep_sms = _resolve_view_deps(item, all_sms)
        bundle = _make_synthetic_bundle(
            slug=_item_slug(item_name),
            name=item_name,
            description=description,
            supermetrics=dep_sms,
            views=[item],
            sm_paths=[sm.source_path for sm in dep_sms if sm.source_path],
        )

    elif ct == "dashboard":
        item = _find_by_name(item_name, all_dashboards, "dashboard")
        version = item.version
        description = item.description
        # Use the walker's collect_deps for dashboard→view→SM→customgroup
        # traversal so the dependency model lives in one place.
        from vcfops_common.dep_walker import collect_deps as _collect_deps
        dep_graph = _collect_deps([item], all_views, all_sms, all_cgs)
        if dep_graph.errors:
            raise DiscreteBuilderError(
                f"dashboard {item_name!r}: dependency errors:\n"
                + "\n".join(f"  - {e}" for e in dep_graph.errors)
            )
        dep_views = dep_graph.views
        dep_sms = dep_graph.supermetrics
        dep_cgs = dep_graph.customgroups
        bundle = _make_synthetic_bundle(
            slug=_item_slug(item_name),
            name=item_name,
            description=description,
            supermetrics=dep_sms,
            views=dep_views,
            dashboards=[item],
            customgroups=dep_cgs,
            sm_paths=[sm.source_path for sm in dep_sms if sm.source_path],
        )

    elif ct == "report":
        item = _find_by_name(item_name, all_reports, "report")
        version = item.version
        description = item.description
        dep_views, dep_dashboards, dep_sms = _resolve_report_deps(
            item, all_views, all_dashboards, all_sms
        )
        bundle = _make_synthetic_bundle(
            slug=_item_slug(item_name),
            name=item_name,
            description=description,
            supermetrics=dep_sms,
            views=dep_views,
            dashboards=dep_dashboards,
            reports=[item],
            sm_paths=[sm.source_path for sm in dep_sms if sm.source_path],
        )

    elif ct == "alert":
        item = _find_by_name(item_name, all_alerts, "alert")
        version = item.version
        description = item.description
        dep_symptoms, dep_recs = _resolve_alert_deps(item, all_symptoms, all_recommendations)
        bundle = _make_synthetic_bundle(
            slug=_item_slug(item_name),
            name=item_name,
            description=description,
            symptoms=dep_symptoms,
            alerts=[item],
            recommendations=dep_recs,
        )

    elif ct == "customgroup":
        item = _find_by_name(item_name, all_cgs, "custom group")
        version = item.version
        description = item.description
        bundle = _make_synthetic_bundle(
            slug=_item_slug(item_name),
            name=item_name,
            description=description,
            customgroups=[item],
        )

    else:
        raise DiscreteBuilderError(f"Unhandled content type: {ct!r}")

    # Build the zip using the same rendering infrastructure as build_bundle
    return _assemble_zip(
        bundle=bundle,
        display_name=item_name,
        item_type=ct,
        version=version,
        description=description,
        output_dir=output_dir,
    )


def _item_slug(name: str) -> str:
    """Derive a filesystem-safe slug from a content item name."""
    # Strip the [VCF Content Factory] prefix and lowercase
    stripped = re.sub(r"^\[VCF Content Factory\]\s*", "", name)
    slug = re.sub(r"[^\w\s-]", "", stripped).strip()
    slug = re.sub(r"[\s_]+", "-", slug).lower()
    return slug or "item"


def _find_by_name(name: str, items, type_label: str):
    for item in items:
        if item.name == name:
            return item
    raise DiscreteBuilderError(
        f"{type_label} not found: {name!r}. "
        f"Available: {[i.name for i in items]}"
    )


def _load_all_sms(extra_search_dirs: "list[Path] | None" = None) -> List[SuperMetricDef]:
    from vcfops_supermetrics.loader import load_dir
    results = []
    for proj_root in (extra_search_dirs or []):
        d = proj_root / "supermetrics"
        if d.exists():
            results.extend(load_dir(d, enforce_framework_prefix=False))
    results.extend(load_dir(_REPO_ROOT / "content" / "supermetrics"))
    return results


def _load_all_views_and_dashboards(
    extra_search_dirs: "list[Path] | None" = None,
) -> tuple[List[ViewDef], List[Dashboard]]:
    from vcfops_dashboards.loader import load_all
    extra_views: List[ViewDef] = []
    extra_dashboards: List[Dashboard] = []
    for proj_root in (extra_search_dirs or []):
        vd = proj_root / "views"
        dd = proj_root / "dashboards"
        # load_all handles non-existent dirs gracefully; pass them directly.
        ev, ed = load_all(vd, dd, enforce_framework_prefix=False)
        extra_views.extend(ev)
        extra_dashboards.extend(ed)
    vd = _REPO_ROOT / "content" / "views"
    dd = _REPO_ROOT / "content" / "dashboards"
    if not vd.exists() and not dd.exists():
        return extra_views, extra_dashboards
    fv, fd = load_all(vd, dd)
    return extra_views + fv, extra_dashboards + fd


def _load_all_customgroups(
    extra_search_dirs: "list[Path] | None" = None,
) -> List[CustomGroupDef]:
    results = []
    for proj_root in (extra_search_dirs or []):
        d = proj_root / "customgroups"
        if d.exists():
            results.extend(load_cg_dir(d))
    results.extend(load_cg_dir(_REPO_ROOT / "content" / "customgroups"))
    return results


def _load_all_reports(
    extra_search_dirs: "list[Path] | None" = None,
) -> List[ReportDef]:
    from vcfops_reports.loader import load_dir
    results = []
    for proj_root in (extra_search_dirs or []):
        d = proj_root / "reports"
        if d.exists():
            results.extend(load_dir(
                d,
                views_dir=proj_root / "views",
                dashboards_dir=proj_root / "dashboards",
                enforce_framework_prefix=False,
            ))
    results.extend(load_dir(
        _REPO_ROOT / "content" / "reports",
        views_dir=_REPO_ROOT / "content" / "views",
        dashboards_dir=_REPO_ROOT / "content" / "dashboards",
    ))
    return results


def _load_all_symptoms(
    extra_search_dirs: "list[Path] | None" = None,
) -> List[SymptomDef]:
    results = []
    for proj_root in (extra_search_dirs or []):
        d = proj_root / "symptoms"
        if d.exists():
            results.extend(load_symptom_dir(d))
    results.extend(load_symptom_dir(_REPO_ROOT / "content" / "symptoms"))
    return results


def _load_all_recommendations(
    extra_search_dirs: "list[Path] | None" = None,
) -> List[Recommendation]:
    results = []
    for proj_root in (extra_search_dirs or []):
        d = proj_root / "recommendations"
        if d.exists():
            results.extend(load_recommendations(d))
    results.extend(load_recommendations(_REPO_ROOT / "content" / "recommendations"))
    return results


def _load_all_alerts(
    extra_search_dirs: "list[Path] | None" = None,
) -> List[AlertDef]:
    results = []
    for proj_root in (extra_search_dirs or []):
        d = proj_root / "alerts"
        if d.exists():
            results.extend(load_alert_dir(d))
    results.extend(load_alert_dir(_REPO_ROOT / "content" / "alerts"))
    return results


def _assemble_zip(
    *,
    bundle: Bundle,
    display_name: str,
    item_type: str,
    version: str,
    description: str,
    output_dir: Path,
) -> Path:
    """Assemble the output zip from a synthetic Bundle, mirroring build_bundle."""
    # Zip filename follows the same [VCF Content Factory] prefix convention
    out_path = output_dir / f"[VCF Content Factory] {display_name}.zip"
    slug = bundle.name
    bundle_prefix = f"bundles/{slug}/"
    content_prefix = f"bundles/{slug}/content/"

    # Static templates
    install_py = (_TEMPLATES_DIR / "install.py").read_text(encoding="utf-8")
    install_ps1 = (_TEMPLATES_DIR / "install.ps1").read_text(encoding="utf-8")
    framework_readme = (_TEMPLATES_DIR / "README_framework.md").read_text(encoding="utf-8")

    # Render content
    sm_dict = _render_supermetrics_dict(bundle) if bundle.supermetrics else {}
    sm_json = json.dumps(sm_dict, indent=2) if sm_dict else None

    bundle_ctx = f'discrete:{item_type}:{display_name!r}'
    views_xml = (
        render_views_xml(bundle.views, sm_scope=bundle.sm_paths, bundle_context=bundle_ctx)
        if bundle.views else None
    )

    dashboard_json = None
    if bundle.dashboards:
        views_by_name = {v.name: v for v in bundle.views}
        dashboard_json = render_dashboards_bundle_json(
            bundle.dashboards, views_by_name, PLACEHOLDER_USER_ID
        )

    cg_rest_payload = _render_customgroup_rest_payload(bundle)
    cg_rest_json = json.dumps(cg_rest_payload, indent=2) if cg_rest_payload is not None else None
    cg_ui_payload = _render_customgroup_ui_payload(bundle)
    cg_ui_json = json.dumps(cg_ui_payload, indent=2) if cg_ui_payload is not None else None

    reports_xml = render_report_xml(bundle.reports) if bundle.reports else None

    symptoms_payload = [s.to_wire() for s in bundle.symptoms] if bundle.symptoms else None
    symptoms_json = json.dumps(symptoms_payload, indent=2) if symptoms_payload else None

    alerts_json = None
    if bundle.alerts:
        alerts_payload = []
        for a in bundle.alerts:
            rec_refs_serialized = [
                {"name": r.name, "priority": r.priority}
                for r in a.recommendations
            ]
            alerts_payload.append({
                "name": a.name,
                "description": a.description,
                "adapter_kind": a.adapter_kind,
                "resource_kind": a.resource_kind,
                "type": a.type,
                "sub_type": a.sub_type,
                "wait_cycles": a.wait_cycles,
                "cancel_cycles": a.cancel_cycles,
                "criticality": a.criticality,
                "impact_badge": a.impact_badge,
                "symptom_sets": a.symptom_sets,
                "recommendations": rec_refs_serialized,
            })
        alerts_json = json.dumps(alerts_payload, indent=2)

    alert_content_xml = None
    if bundle.symptoms or bundle.alerts or bundle.recommendations:
        alert_content_xml = render_alert_content_xml(
            bundle.symptoms,
            bundle.alerts,
            recommendations=bundle.recommendations or [],
        )

    # bundle.json
    content_block: dict = {}
    if bundle.supermetrics:
        content_block["supermetrics"] = {
            "file": "content/supermetrics.json",
            "items": [{"uuid": sm.id, "name": sm.name} for sm in bundle.supermetrics],
        }
    if bundle.views:
        content_block["views"] = {
            "file": "content/views_content.xml",
            "items": [{"uuid": v.id, "name": v.name} for v in bundle.views],
        }
    if bundle.dashboards:
        content_block["dashboards"] = {
            "file": "content/dashboard.json",
            "items": [{"uuid": d.id, "name": d.name} for d in bundle.dashboards],
        }
    if bundle.customgroups:
        content_block["customgroups"] = {
            "file": "content/customgroup.json",
            "items": [{"name": cg.name} for cg in bundle.customgroups],
        }
    if bundle.symptoms:
        content_block["symptoms"] = {
            "file": "content/symptoms.json",
            "items": [{"name": s.name} for s in bundle.symptoms],
        }
    if bundle.alerts:
        content_block["alerts"] = {
            "file": "content/alerts.json",
            "items": [{"name": a.name} for a in bundle.alerts],
        }
    if bundle.reports:
        content_block["reports"] = {
            "file": "content/reports_content.xml",
            "items": [{"uuid": rd.id, "name": rd.name} for rd in bundle.reports],
        }

    bundle_json_str = json.dumps({
        "name": slug,
        "display_name": display_name,
        "description": description or "",
        "discrete_item_type": item_type,
        "discrete_item_version": version,
        "content": content_block,
    }, indent=2)

    # Item-focused README
    readme = _generate_discrete_readme(item_type, display_name, description, version, bundle)

    # Drag-drop zip artifacts
    views_zip_bytes = _build_views_inner_zip(views_xml) if views_xml else None
    dashboard_zip_bytes = (
        _build_dashboard_dropin_zip(dashboard_json) if dashboard_json else None
    )
    reports_zip_bytes = (
        _build_reports_dropin_zip(reports_xml) if reports_xml else None
    )

    # LICENSE
    license_path = _REPO_ROOT / "LICENSE"
    license_text = license_path.read_text() if license_path.exists() else None

    # vcfops_manifest.json
    import datetime as _dt
    vcfops_manifest = json.dumps({
        "bundle_name": slug,
        "item_type": item_type,
        "item_name": display_name,
        "item_version": version,
        "template_version": CURRENT_TEMPLATE_VERSION,
        "built_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("install.py", install_py)
        z.writestr("install.ps1", install_ps1)
        z.writestr("README.md", framework_readme)
        z.writestr("vcfops_manifest.json", vcfops_manifest)
        if license_text is not None:
            z.writestr("LICENSE", license_text)

        z.writestr(bundle_prefix + "bundle.json", bundle_json_str)
        z.writestr(bundle_prefix + "README.md", readme)

        if sm_json:
            z.writestr(bundle_prefix + "supermetric.json", sm_json)
        if cg_ui_json:
            z.writestr(bundle_prefix + "customgroup.json", cg_ui_json)
        if views_zip_bytes:
            z.writestr(bundle_prefix + "Views.zip", views_zip_bytes)
        if dashboard_zip_bytes:
            z.writestr(bundle_prefix + "Dashboard.zip", dashboard_zip_bytes)
        if reports_zip_bytes:
            z.writestr(bundle_prefix + "Reports.zip", reports_zip_bytes)
        if alert_content_xml:
            z.writestr(bundle_prefix + "AlertContent.xml", alert_content_xml)

        if sm_json:
            z.writestr(content_prefix + "supermetrics.json", sm_json)
        if views_xml:
            z.writestr(content_prefix + "views_content.xml", views_xml)
        if dashboard_json:
            z.writestr(content_prefix + "dashboard.json", dashboard_json)
        if cg_rest_json:
            z.writestr(content_prefix + "customgroup.json", cg_rest_json)
        if reports_xml:
            z.writestr(content_prefix + "reports_content.xml", reports_xml)
        if symptoms_json:
            z.writestr(content_prefix + "symptoms.json", symptoms_json)
        if alerts_json:
            z.writestr(content_prefix + "alerts.json", alerts_json)

    out_path.write_bytes(buf.getvalue())
    return out_path
