"""Build distributable content packages from bundle manifests.

A built package is a zip at dist/<bundle-name>.zip containing:

    install.py              -- Python installer (stamped template)
    install.ps1             -- PowerShell installer (stamped template)
    content/
        supermetrics.json   -- SM dict keyed by UUID (wire format); also used by enable step
        views_content.xml   -- View XML (if any views)
        dashboard.json      -- Dashboard JSON with PLACEHOLDER_USER_ID
        customgroup.json    -- Custom group wire payload(s)
    README.md               -- Generated from bundle metadata
    LICENSE                 -- Copied from repo root (if present)
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import List

from vcfops_dashboards.render import render_views_xml, render_dashboards_bundle_json
from vcfops_reports.render import render_report_xml
from .loader import Bundle, load_bundle

# The builder stamps PLACEHOLDER_USER_ID into the rendered dashboard JSON.
# The install script replaces this at install time with the real user UUID.
PLACEHOLDER_USER_ID = "PLACEHOLDER_USER_ID"

# Templates live next to this file in vcfops_packaging/templates/
_TEMPLATES_DIR = Path(__file__).parent / "templates"


_ESCAPE_VARS = {"PACKAGE_NAME", "PACKAGE_DESCRIPTION", "DASHBOARD_UUID"}


def _stamp_template(template_name: str, vars: dict) -> str:
    """Read a template file and replace {{VAR}} placeholders with values.

    Variables listed in _ESCAPE_VARS are escaped for embedding in
    string literals (double quotes and backslashes). Others (e.g.
    CONTENT_MANIFEST) are substituted raw since they appear as bare
    expressions, not inside quoted strings.
    """
    template_path = _TEMPLATES_DIR / template_name
    text = template_path.read_text(encoding="utf-8")
    for key, value in vars.items():
        if key in _ESCAPE_VARS:
            value = value.replace("\\", "\\\\").replace('"', '\\"')
        text = text.replace("{{" + key + "}}", value)
    return text


def _build_bundle_json(bundle: Bundle) -> str:
    """Build the bundle.json metadata manifest embedded in distribution zips.

    This manifest lets install scripts verify which content files belong to
    this specific bundle, so users who extract multiple bundles into the same
    directory can tell them apart and choose the right one to install.

    Shape (mirrors the spec in the feature request):
      {
        "name": "...",
        "description": "...",
        "content": {
          "supermetrics": {"file": "content/supermetrics.json", "items": [...]},
          "views":        {"file": "content/views_content.xml", "items": [...]},
          "dashboards":   {"file": "content/dashboard.json",    "items": [...]},
          "customgroups": {"file": "content/customgroup.json",  "items": [...]}
        }
      }
    Each item has "uuid" and "name" for super metrics / views / dashboards.
    Custom groups have "name" only (their API assigns IDs server-side).
    """
    def _sm_items():
        return [{"uuid": sm.id, "name": sm.name} for sm in bundle.supermetrics]

    def _view_items():
        return [{"uuid": v.id, "name": v.name} for v in bundle.views]

    def _dashboard_items():
        return [{"uuid": d.id, "name": d.name} for d in bundle.dashboards]

    def _cg_items():
        return [{"name": cg.name} for cg in bundle.customgroups]

    def _report_items():
        return [{"uuid": rd.id, "name": rd.name} for rd in bundle.reports]

    content: dict = {}
    if bundle.supermetrics:
        content["supermetrics"] = {
            "file": "content/supermetrics.json",
            "items": _sm_items(),
        }
    if bundle.views:
        content["views"] = {
            "file": "content/views_content.xml",
            "items": _view_items(),
        }
    if bundle.dashboards:
        content["dashboards"] = {
            "file": "content/dashboard.json",
            "items": _dashboard_items(),
        }
    if bundle.customgroups:
        content["customgroups"] = {
            "file": "content/customgroup.json",
            "items": _cg_items(),
        }
    if bundle.reports:
        content["reports"] = {
            "file": "content/reports_content.xml",
            "items": _report_items(),
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

    manifest = {
        "name": bundle.name,
        "description": bundle.description or "",
        "content": content,
    }
    return json.dumps(manifest, indent=2)


def _build_content_manifest(bundle: Bundle) -> str:
    """Build the CONTENT_MANIFEST JSON string for uninstall templates.

    The manifest records the display names of every content object in the
    bundle so the uninstall script can look them up by name at runtime.
    """
    manifest = {
        "dashboards": [d.name for d in bundle.dashboards],
        "views": [v.name for v in bundle.views],
        "supermetrics": [sm.name for sm in bundle.supermetrics],
        "customgroups": [cg.name for cg in bundle.customgroups],
        "reports": [rd.name for rd in bundle.reports],
        "symptoms": [s.name for s in bundle.symptoms],
        "alerts": [a.name for a in bundle.alerts],
    }
    return json.dumps(manifest, indent=2)


def _render_supermetrics_dict(bundle: Bundle) -> dict:
    """Render super metrics as a dict keyed by UUID (wire format).

    Matches the format vcfops_supermetrics/client.py's
    import_supermetrics_bundle produces. Formula whitespace is collapsed
    (API rejects multi-line formulas).
    """
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
    """Render custom group wire payloads.

    Returns a single dict if one group, list if multiple, None if none.
    """
    if not bundle.customgroups:
        return None
    wire = [cg.to_wire() for cg in bundle.customgroups]
    return wire[0] if len(wire) == 1 else wire


def _generate_readme(bundle: Bundle) -> str:
    """Generate a README.md from bundle metadata."""
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
        "**Python (recommended):**",
        "```",
        "python3 install.py",
        "```",
        "",
        "**PowerShell:**",
        "```powershell",
        ".\\install.ps1",
        "```",
        "",
        "Both scripts support interactive prompts, CLI flags, and environment variables.",
        "Run with `--help` (Python) or `-?` (PowerShell) for usage details.",
        "",
        "## Uninstallation",
        "",
        "To remove all content installed by this package, pass `--uninstall`",
        "to the same install script:",
        "",
        "**Python:**",
        "```",
        "python3 install.py --uninstall",
        "```",
        "",
        "**PowerShell:**",
        "```powershell",
        ".\\install.ps1 -Uninstall",
        "```",
        "",
        "To skip dependency checks and delete everything unconditionally:",
        "",
        "```",
        "python3 install.py --uninstall --force",
        "```",
        "```powershell",
        ".\\install.ps1 -Uninstall -Force",
        "```",
        "",
        "Deletion order: dashboards → views → super metrics → custom groups.",
        "Items not present on the target instance are skipped (not an error).",
        "",
        "> **Note:** If this package includes dashboards or views, uninstall must be run",
        "> as the `admin` user. VCF Ops locks imported dashboards to admin ownership;",
        "> only the admin user's UI session can delete them. Re-run with `--user admin`",
        "> (Python) or `-User admin` (PowerShell), or set `VCFOPS_USER=admin` in your",
        "> environment.",
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

    # Stamp template variables
    content_manifest_json = _build_content_manifest(bundle)
    template_vars = {
        "PACKAGE_NAME": bundle.name,
        "PACKAGE_DESCRIPTION": bundle.description or bundle.name,
        "DASHBOARD_UUID": bundle.dashboards[0].id if bundle.dashboards else "",
        "CONTENT_MANIFEST": content_manifest_json,
    }

    install_py = _stamp_template("install.py", template_vars)
    install_ps1 = _stamp_template("install.ps1", template_vars)

    # Render content payloads
    sm_dict = _render_supermetrics_dict(bundle) if bundle.supermetrics else {}

    views_xml = render_views_xml(bundle.views) if bundle.views else ""

    dashboard_json = ""
    if bundle.dashboards:
        views_by_name = {v.name: v for v in bundle.views}
        dashboard_json = render_dashboards_bundle_json(
            bundle.dashboards, views_by_name, PLACEHOLDER_USER_ID
        )

    cg_payload = _render_customgroup_payload(bundle)

    reports_xml = render_report_xml(bundle.reports) if bundle.reports else ""

    # Symptoms serialize to wire format at build time (no server-side dependencies).
    # Alerts need symptom name→id resolution at install time, so we store the
    # YAML-equivalent dict (name, description, adapter/resource kind, symptom_sets,
    # etc.) and let the install script call to_wire() with the live symptom map.
    symptoms_payload = [s.to_wire() for s in bundle.symptoms] if bundle.symptoms else []
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

    readme_text = _generate_readme(bundle)

    bundle_json = _build_bundle_json(bundle)

    # Find repo root LICENSE
    repo_root = Path(__file__).parent.parent
    license_path = repo_root / "LICENSE"
    license_text = license_path.read_text() if license_path.exists() else None

    # Assemble zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("install.py", install_py)
        z.writestr("install.ps1", install_ps1)

        if sm_dict:
            z.writestr("content/supermetrics.json", json.dumps(sm_dict, indent=2))
        if views_xml:
            z.writestr("content/views_content.xml", views_xml)
        if dashboard_json:
            z.writestr("content/dashboard.json", dashboard_json)
        if cg_payload is not None:
            z.writestr("content/customgroup.json", json.dumps(cg_payload, indent=2))
        if reports_xml:
            z.writestr("content/reports_content.xml", reports_xml)
        if symptoms_payload:
            z.writestr("content/symptoms.json", json.dumps(symptoms_payload, indent=2))
        if alerts_payload:
            z.writestr("content/alerts.json", json.dumps(alerts_payload, indent=2))

        z.writestr("bundle.json", bundle_json)
        z.writestr("README.md", readme_text)
        if license_text is not None:
            z.writestr("LICENSE", license_text)

    out_path.write_bytes(buf.getvalue())
    return out_path
