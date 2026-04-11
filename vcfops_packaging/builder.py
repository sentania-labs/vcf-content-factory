"""Build distributable content packages from bundle manifests.

A built package is a zip at dist/<bundle-name>.zip with the layout:

    install.py              -- static Python installer (no stamped vars)
    install.ps1             -- static PowerShell installer
    README.md               -- static framework overview (from README_framework.md)
    LICENSE                 -- repo LICENSE (if present)
    bundles/
      <bundle-slug>/
        bundle.json         -- metadata + runtime content manifest
        README.md           -- bundle-specific description
        # Community-native drag-drop artifacts:
        supermetric.json    -- same bytes as content/supermetrics.json
        customgroup.json    -- same bytes as content/customgroup.json
        Views.zip           -- inner content.xml at zip root
        Dashboard.zip       -- inner dashboard/dashboard.json with deterministic UUID5
        Reports.zip         -- inner content.xml
        AlertContent.xml    -- synthesised from symptoms + alerts YAML
        content/
          supermetrics.json
          dashboard.json    -- retains PLACEHOLDER_USER_ID for installer
          views_content.xml
          customgroup.json
          symptoms.json
          alerts.json
          reports_content.xml

Template stamping is removed entirely — install.py and install.ps1 are
static and read everything from bundle.json at runtime.
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from vcfops_dashboards.render import render_views_xml, render_dashboards_bundle_json
from vcfops_reports.render import render_report_xml
from vcfops_alerts.render import render_alert_content_xml
from .loader import Bundle, load_bundle

# The builder stamps PLACEHOLDER_USER_ID into the rendered dashboard JSON.
# The install script replaces this at install time with the real user UUID.
PLACEHOLDER_USER_ID = "PLACEHOLDER_USER_ID"

# Deterministic UUID5 used in drag-drop Dashboard.zip (no installer stamping
# available at drag-drop time).  Derived from the framework's canonical DNS
# label so it is constant across builds, syntactically valid, and grep-able
# as framework-stamped content.  Resolves to:
#   b58a71ee-e909-5b40-a355-9e199e6f0f53
# A 130-dashboard corpus survey found zero uses of the nil UUID in real
# community packages; UUID5 looks natural compared to the corpus's real-UUID
# values while remaining deterministic and identifiable.
DASHBOARD_DROPIN_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "vcf-content-factory.local"))

# Templates live next to this file in vcfops_packaging/templates/
_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _build_bundle_json(bundle: Bundle) -> str:
    """Build the bundle.json metadata manifest embedded in distribution zips.

    Paths in ``file:`` are relative to the bundle's own subdirectory
    (``bundles/<slug>/``).  The install script joins them with the bundle dir.

    Shape:
      {
        "name": "...",
        "display_name": "...",   (optional; same as name if absent)
        "description": "...",
        "content": {
          "supermetrics": {"file": "content/supermetrics.json", "items": [...]},
          "views":        {"file": "content/views_content.xml",  "items": [...]},
          "dashboards":   {"file": "content/dashboard.json",     "items": [...]},
          "customgroups": {"file": "content/customgroup.json",   "items": [...]},
          "symptoms":     {"file": "content/symptoms.json",      "items": [...]},
          "alerts":       {"file": "content/alerts.json",        "items": [...]},
          "reports":      {"file": "content/reports_content.xml","items": [...]}
        }
      }
    items[].name is the uninstall contract; items[].uuid is present for
    types that carry UUIDs (supermetrics, views, dashboards, reports).
    """

    content: dict = {}
    if bundle.supermetrics:
        content["supermetrics"] = {
            "file": "content/supermetrics.json",
            "items": [{"uuid": sm.id, "name": sm.name} for sm in bundle.supermetrics],
        }
    if bundle.views:
        content["views"] = {
            "file": "content/views_content.xml",
            "items": [{"uuid": v.id, "name": v.name} for v in bundle.views],
        }
    if bundle.dashboards:
        content["dashboards"] = {
            "file": "content/dashboard.json",
            "items": [{"uuid": d.id, "name": d.name} for d in bundle.dashboards],
        }
    if bundle.customgroups:
        content["customgroups"] = {
            "file": "content/customgroup.json",
            "items": [{"name": cg.name} for cg in bundle.customgroups],
        }
    if bundle.symptoms:
        content["symptoms"] = {
            "file": "content/symptoms.json",
            "items": [{"name": s.name} for s in bundle.symptoms],
        }
    if bundle.alerts:
        content["alerts"] = {
            "file": "content/alerts.json",
            "items": [{"name": a.name} for a in bundle.alerts],
        }
    if bundle.reports:
        content["reports"] = {
            "file": "content/reports_content.xml",
            "items": [{"uuid": rd.id, "name": rd.name} for rd in bundle.reports],
        }

    manifest = {
        "name": bundle.name,
        "description": bundle.description or "",
        "content": content,
    }
    return json.dumps(manifest, indent=2)


def _render_supermetrics_dict(bundle: Bundle) -> dict:
    """Render super metrics as a dict keyed by UUID (wire format)."""
    result = {}
    for sm in bundle.supermetrics:
        formula = " ".join(sm.formula.split())
        result[sm.id] = {
            "name": sm.name,
            "formula": formula,
            "description": sm.description,
            "unitId": sm.unit_id or "",
            "resourceKinds": sm.resource_kinds,
        }
    return result


def _render_customgroup_payload(bundle: Bundle):
    """Render custom group wire payloads."""
    if not bundle.customgroups:
        return None
    wire = [cg.to_wire() for cg in bundle.customgroups]
    return wire[0] if len(wire) == 1 else wire


def _build_views_inner_zip(xml_text: str) -> bytes:
    """Build Views.zip: inner content.xml at zip root."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_text)
    return buf.getvalue()


def _build_dashboard_dropin_zip(dashboard_json_with_placeholder: str) -> bytes:
    """Build Dashboard.zip for drag-drop UI import.

    Uses DASHBOARD_DROPIN_USER_ID (a deterministic UUID5) in place of
    PLACEHOLDER_USER_ID since no installer is available to stamp the real
    owner at drag-drop time.  Both userId and lastUpdateUserId are covered
    by the single string replace because the renderer writes PLACEHOLDER_USER_ID
    into both fields.
    Inner structure: dashboard/dashboard.json + language resource stubs.
    """
    patched = dashboard_json_with_placeholder.replace(PLACEHOLDER_USER_ID, DASHBOARD_DROPIN_USER_ID)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dashboard/dashboard.json", patched)
        for lang in ("", "_es", "_fr", "_ja"):
            z.writestr(f"dashboard/resources/resources{lang}.properties", "")
    return buf.getvalue()


def _build_reports_dropin_zip(reports_xml: str) -> bytes:
    """Build Reports.zip for drag-drop UI import (inner content.xml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", reports_xml)
    return buf.getvalue()


def _generate_bundle_readme(bundle: Bundle) -> str:
    """Generate the bundle-specific README.md (references ../../install.py)."""
    lines = [
        f"# {bundle.name}",
        "",
        bundle.description or "_No description provided._",
        "",
        "## Contents",
        "",
    ]
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
    if bundle.reports:
        lines.append(f"**Reports ({len(bundle.reports)}):**")
        lines.append("")
        for rd in bundle.reports:
            lines.append(f"- {rd.name}")
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
        "Both scripts support interactive prompts, CLI flags, and environment variables.",
        "Run with `--help` (Python) or `-?` (PowerShell) for usage details.",
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
        "See the top-level `README.md` for important notes about limitations of",
        "manual import vs the automated installer.",
        "",
        "## Uninstallation",
        "",
        "To remove all content installed by this bundle:",
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
        "> **Note:** If this bundle includes dashboards or views, uninstall must be",
        "> run as the `admin` user. Re-run with `--user admin` (Python) or",
        "> `-User admin` (PowerShell), or set `VCFOPS_USER=admin`.",
        "",
        "## Requirements",
        "",
        "- Python 3.8+ or PowerShell 5.1+",
        "- Network access to your VCF Operations instance",
        "- VCF Operations user with write access to content and policies",
        "",
        "---",
        "_Generated by vcfops_packaging. Part of the VCF Content Factory framework._",
    ]
    return "\n".join(lines) + "\n"


def build_bundle(
    bundle_path: str | Path,
    output_dir: str | Path = "dist",
) -> Path:
    """Build a distributable zip for the given bundle manifest.

    Args:
        bundle_path: Path to a bundles/*.yaml manifest.
        output_dir: Directory where the output zip is written.
            Defaults to 'dist/'.

    Returns:
        Path to the built zip file.
    """
    bundle = load_bundle(bundle_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / f"{bundle.name}.zip"
    slug = bundle.name  # bundle slug = manifest name
    bundle_prefix = f"bundles/{slug}/"
    content_prefix = f"bundles/{slug}/content/"

    # --- Read static templates (no stamping) ---
    install_py = (_TEMPLATES_DIR / "install.py").read_text(encoding="utf-8")
    install_ps1 = (_TEMPLATES_DIR / "install.ps1").read_text(encoding="utf-8")

    # --- Framework README (static) ---
    framework_readme_path = _TEMPLATES_DIR / "README_framework.md"
    framework_readme = framework_readme_path.read_text(encoding="utf-8")

    # --- Render content payloads ---
    sm_dict = _render_supermetrics_dict(bundle) if bundle.supermetrics else {}
    sm_json = json.dumps(sm_dict, indent=2) if sm_dict else None

    views_xml = render_views_xml(bundle.views) if bundle.views else None

    dashboard_json = None
    if bundle.dashboards:
        views_by_name = {v.name: v for v in bundle.views}
        dashboard_json = render_dashboards_bundle_json(
            bundle.dashboards, views_by_name, PLACEHOLDER_USER_ID
        )

    cg_payload = _render_customgroup_payload(bundle)
    cg_json = json.dumps(cg_payload, indent=2) if cg_payload is not None else None

    reports_xml = render_report_xml(bundle.reports) if bundle.reports else None

    # Symptoms: serialize to wire format at build time.
    symptoms_payload = [s.to_wire() for s in bundle.symptoms] if bundle.symptoms else None
    symptoms_json = json.dumps(symptoms_payload, indent=2) if symptoms_payload else None

    # Alerts: store YAML-equivalent dict for runtime symptom ID resolution.
    alerts_payload = None
    if bundle.alerts:
        alerts_payload = []
        for a in bundle.alerts:
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
                "recommendations": a.recommendations,
            })
        alerts_json = json.dumps(alerts_payload, indent=2)
    else:
        alerts_json = None

    # AlertContent.xml — synthesised when the bundle has symptoms or alerts.
    alert_content_xml = None
    if bundle.symptoms or bundle.alerts:
        alert_content_xml = render_alert_content_xml(
            bundle.symptoms,
            bundle.alerts,
            recommendations=bundle.recommendations or [],
        )

    # --- bundle.json ---
    bundle_json = _build_bundle_json(bundle)

    # --- Bundle-specific README ---
    bundle_readme = _generate_bundle_readme(bundle)

    # --- Drag-drop zip artifacts ---
    views_zip_bytes = _build_views_inner_zip(views_xml) if views_xml else None
    dashboard_zip_bytes = (
        _build_dashboard_dropin_zip(dashboard_json) if dashboard_json else None
    )
    reports_zip_bytes = (
        _build_reports_dropin_zip(reports_xml) if reports_xml else None
    )

    # --- Repo root LICENSE ---
    repo_root = Path(__file__).parent.parent
    license_path = repo_root / "LICENSE"
    license_text = license_path.read_text() if license_path.exists() else None

    # --- Assemble zip ---
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Root-level static files
        z.writestr("install.py", install_py)
        z.writestr("install.ps1", install_ps1)
        z.writestr("README.md", framework_readme)
        if license_text is not None:
            z.writestr("LICENSE", license_text)

        # Bundle subdirectory: metadata
        z.writestr(bundle_prefix + "bundle.json", bundle_json)
        z.writestr(bundle_prefix + "README.md", bundle_readme)

        # Drag-drop artifacts at bundle root (community-native filenames)
        if sm_json:
            z.writestr(bundle_prefix + "supermetric.json", sm_json)
        if cg_json:
            z.writestr(bundle_prefix + "customgroup.json", cg_json)
        if views_zip_bytes:
            z.writestr(bundle_prefix + "Views.zip", views_zip_bytes)
        if dashboard_zip_bytes:
            z.writestr(bundle_prefix + "Dashboard.zip", dashboard_zip_bytes)
        if reports_zip_bytes:
            z.writestr(bundle_prefix + "Reports.zip", reports_zip_bytes)
        if alert_content_xml:
            z.writestr(bundle_prefix + "AlertContent.xml", alert_content_xml)

        # Installer source files under content/
        if sm_json:
            z.writestr(content_prefix + "supermetrics.json", sm_json)
        if views_xml:
            z.writestr(content_prefix + "views_content.xml", views_xml)
        if dashboard_json:
            # content/ copy retains PLACEHOLDER_USER_ID for runtime stamping
            z.writestr(content_prefix + "dashboard.json", dashboard_json)
        if cg_json:
            z.writestr(content_prefix + "customgroup.json", cg_json)
        if reports_xml:
            z.writestr(content_prefix + "reports_content.xml", reports_xml)
        if symptoms_json:
            z.writestr(content_prefix + "symptoms.json", symptoms_json)
        if alerts_json:
            z.writestr(content_prefix + "alerts.json", alerts_json)

    out_path.write_bytes(buf.getvalue())
    return out_path
