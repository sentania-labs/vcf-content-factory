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
from .template_version import CURRENT_TEMPLATE_VERSION

# ---------------------------------------------------------------------------
# Display-name derivation
# ---------------------------------------------------------------------------
_ACRONYMS = frozenset({
    "vks", "vm", "vms", "sm", "sms", "vcf", "cpu", "gpu",
    "ram", "mem", "ha", "drs", "nsx", "esxi", "vcsa",
})


def _slug_to_display_name(slug: str) -> str:
    """Transform a bundle slug like 'vks-core-consumption' into a display
    name like 'VKS Core Consumption'. Known acronyms are uppercased;
    everything else is Title Cased."""
    parts = slug.replace("_", "-").split("-")
    result = []
    for part in parts:
        if not part:
            continue
        if part.lower() in _ACRONYMS:
            result.append(part.upper())
        else:
            result.append(part.capitalize())
    return " ".join(result)


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


def _build_bundle_json(bundle: Bundle, display_name: str) -> str:
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
    if bundle.builtin_metric_enables:
        content["builtin_metric_enables"] = {
            "file": "content/builtin_metric_enables.json",
            # Each item carries a "name" field (= metric_key) so the uninstall
            # registry predicate (which reads item["name"]) can detect the section.
            "items": [
                {
                    "name": bme.metric_key,       # uninstall-name contract
                    "adapter_kind": bme.adapter_kind,
                    "resource_kind": bme.resource_kind,
                    "metric_key": bme.metric_key,
                    **( {"reason": bme.reason} if bme.reason else {} ),
                }
                for bme in bundle.builtin_metric_enables
            ],
        }

    manifest: dict = {
        "name": bundle.name,
        "display_name": display_name,
        "description": bundle.description or "",
        "content": content,
    }
    # Include provenance fields when present
    if not bundle.factory_native:
        manifest["factory_native"] = False
    if bundle.author:
        manifest["author"] = bundle.author
    if bundle.license:
        manifest["license"] = bundle.license
    if bundle.source:
        manifest["source"] = bundle.source
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


def _render_customgroup_rest_payload(bundle: Bundle):
    """Render custom group REST API wire payloads (for content/customgroup.json).

    Returns a single dict if there is one group, a list if there are multiple.
    The install script's _install_customgroups() reads this file and calls
    upsert_custom_group() which POSTs/PUTs to /api/resources/groups.
    """
    if not bundle.customgroups:
        return None
    wire = [cg.to_wire() for cg in bundle.customgroups]
    return wire[0] if len(wire) == 1 else wire


def _render_customgroup_ui_payload(bundle: Bundle) -> dict | None:
    """Render custom group UI import payload (for drag-drop customgroup.json).

    Produces the envelope format expected by the VCF Ops UI custom group import
    dialog: {"customGroups": [...], "customGroupTypes": [...]}.  All groups in
    the bundle are merged into a single envelope.  Duplicate customGroupTypes
    (same resourceKind) are deduplicated, keeping the first occurrence.

    See context/customgroup_import_format.md for the format specification.
    """
    if not bundle.customgroups:
        return None
    all_groups = []
    seen_type_keys: dict = {}  # resourceKind -> first localization seen
    for cg in bundle.customgroups:
        ui = cg.to_ui_wire()
        all_groups.extend(ui["customGroups"])
        for gt in ui["customGroupTypes"]:
            rk = gt["resourceKind"]
            if rk not in seen_type_keys:
                seen_type_keys[rk] = gt
    return {
        "customGroups": all_groups,
        "customGroupTypes": list(seen_type_keys.values()),
    }


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


def _load_design_sections(bundle: Bundle) -> dict:
    """Load and extract named sections from a bundle's design artifact.

    Resolution order:
    1. Explicit ``design:`` field in the bundle manifest (repo-relative path).
    2. Convention: ``designs/<bundle-name>.md`` at repo root.
    3. If neither exists, return an empty dict (design sections are skipped).

    Sections extracted (keyed by destination name):
      intent          <- ## Scope and Intent
      layout          <- ## Dashboard Mockup
      design_decisions <- ## Design Decisions
      out_of_scope    <- ## Out of Scope          (if present)
      origin          <- ## Original Request       (if present)
                      <- ## Provenance             (if present AND ## Original Request is absent)

    Returns a dict of {section_key: markdown_content_str}.  Only keys whose
    source heading is found in the design artifact are included.
    """
    repo_root = Path(__file__).parent.parent

    # Resolve design artifact path.
    design_path: Optional[Path] = None
    if bundle.design:
        candidate = Path(bundle.design)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        if candidate.exists():
            design_path = candidate
    if design_path is None:
        # Convention-based lookup.
        candidate = repo_root / "designs" / f"{bundle.name}.md"
        if candidate.exists():
            design_path = candidate

    if design_path is None:
        return {}

    import re as _re
    text = design_path.read_text(encoding="utf-8")

    # Split into sections on H2 headings (^## ...).
    # Each match gives us (heading_text, content_until_next_h2).
    heading_re = _re.compile(r'^## (.+)$', _re.MULTILINE)
    sections: dict[str, str] = {}
    matches = list(heading_re.finditer(text))
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections[heading] = content

    result: dict = {}

    # Map source headings -> destination keys.
    if "Scope and Intent" in sections:
        result["intent"] = sections["Scope and Intent"]
    if "Dashboard Mockup" in sections:
        result["layout"] = sections["Dashboard Mockup"]
    if "Design Decisions" in sections:
        result["design_decisions"] = sections["Design Decisions"]
    if "Out of Scope" in sections:
        result["out_of_scope"] = sections["Out of Scope"]

    # Origin: prefer ## Original Request; fall back to ## Provenance only if
    # ## Original Request is absent.
    if "Original Request" in sections:
        result["origin"] = sections["Original Request"]
    elif "Provenance" in sections:
        result["origin"] = sections["Provenance"]

    return result


def _generate_bundle_readme(bundle: Bundle, display_name: str) -> str:
    """Generate the bundle-specific README.md (references ../../install.py)."""
    lines = [
        f"# {display_name}",
        "",
        bundle.description or "_No description provided._",
        "",
    ]

    # Provenance section: rendered when factory_native is False OR any
    # attribution field is set.  Placement: after lead description, before
    # design sections and ## Contents.
    has_provenance = (
        not bundle.factory_native
        or bool(bundle.author)
        or bool(bundle.license)
        or bool(bundle.source)
    )
    if has_provenance:
        lines += [
            "## Provenance",
            "",
        ]
        source = bundle.source or {}
        if source.get("url"):
            captured_at = source.get("captured_at", "")
            captured_from = source.get("captured_from_host", "")
            source_line = f"**Source:** {source['url']}"
            if captured_at:
                source_line += f" (captured {captured_at}"
                if captured_from:
                    source_line += f" from {captured_from}"
                source_line += ")"
            lines.append(source_line)
            lines.append("")
        if source.get("version"):
            lines.append(f"**Version:** {source['version']}")
            lines.append("")
        if bundle.author:
            lines.append(f"**Author:** {bundle.author}")
            lines.append("")
        if bundle.license:
            lines.append(f"**License:** {bundle.license}")
            lines.append("")
        # NOTE: no auto-injected boilerplate prose here.  When factory_native is
        # False, bundle.description is the DESCRIPTION.md the user authored —
        # it already provides the narrative (origin, context, usage notes).
        # The ## Provenance block above supplies the structured metadata
        # (source URL, captured date, version, author, license).
        # Duplicating extraction-origin language here creates double provenance.

    # --- Design artifact sections ---
    # Extracted from designs/<bundle-name>.md (or manifest's design: field).
    # Only present when the design artifact exists and contains the heading.
    # Sections included: Intent, Layout (mockup), Design Decisions, Out of
    # Scope (conditional), Origin (conditional).  Internal sections
    # (Traceability, Known Issues, Content Inventory, Side-by-Side Analysis)
    # are deliberately excluded.
    design_sections = _load_design_sections(bundle)

    if "intent" in design_sections:
        lines += [
            "## Intent",
            "",
            design_sections["intent"],
            "",
        ]

    if "layout" in design_sections:
        lines += [
            "## Layout",
            "",
            design_sections["layout"],
            "",
        ]

    if "design_decisions" in design_sections:
        lines += [
            "## Design Decisions",
            "",
            design_sections["design_decisions"],
            "",
        ]

    if "out_of_scope" in design_sections:
        lines += [
            "## Out of Scope",
            "",
            design_sections["out_of_scope"],
            "",
        ]

    if "origin" in design_sections:
        lines += [
            "## Origin",
            "",
            design_sections["origin"],
            "",
        ]

    lines += [
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
    *,
    audit_mode: str = "auto",
    live_describe: bool = True,
    skip_audit: bool = False,
) -> Path:
    """Build a distributable zip for the given bundle manifest.

    Args:
        bundle_path: Path to a bundles/*.yaml manifest.
        output_dir: Directory where the output zip is written.
            Defaults to 'dist/'.
        audit_mode: Dependency audit mode — "auto" (default), "strict", or
            "lax".  See vcfops_packaging/audit.py for semantics.
        live_describe: If True (default) and VCFOPS_HOST/USER/PASSWORD are in
            the environment, refresh the describe cache for all adapter/resource
            kind pairs referenced by this bundle before auditing.  If False,
            use the cache as-is (cache-only mode).
        skip_audit: If True, skip the dependency audit entirely.  Metric
            references are NOT validated.  Use only when the describe cache
            cannot be refreshed (e.g. no lab access) and the content is known
            to be correct.  Emits a WARN to stderr.

    Returns:
        Path to the built zip file.
    """
    from .audit import audit_bundle_dependencies, print_audit_summary
    from .describe import make_cache, DescribeCacheError

    bundle = load_bundle(bundle_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Dependency audit ---
    if skip_audit:
        import sys as _sys
        print(
            f"  WARN: --skip-audit is set; dependency audit skipped for {bundle_path}. "
            "Metric references will NOT be validated.",
            file=_sys.stderr,
        )
        audit_result = None
    else:
        describe_cache = make_cache(live=live_describe)

        # If live mode and client is attached, refresh relevant kind pairs first.
        if live_describe and describe_cache._client is not None:
            from .deps import extract_metric_references
            refs = extract_metric_references(bundle)
            pairs_needed: set[tuple[str, str]] = {
                (r.adapter_kind, r.resource_kind) for r in refs
            }
            for ak, rk in sorted(pairs_needed):
                try:
                    describe_cache.refresh(ak, rk)
                except DescribeCacheError as exc:
                    print(f"  WARN: could not refresh describe cache for {ak}/{rk}: {exc}",
                          file=__import__("sys").stderr)

        audit_result = audit_bundle_dependencies(
            bundle, describe_cache, mode=audit_mode
        )

        # In auto mode, merge auto-added entries into the bundle's list before
        # bundle.json serialization.
        if audit_result.auto_added:
            bundle.builtin_metric_enables = list(bundle.builtin_metric_enables) + audit_result.auto_added

    slug = bundle.name  # bundle slug = manifest name
    # Derive the display name: prefer manifest's explicit display_name, else
    # derive from slug.
    if bundle.display_name:
        display_name = bundle.display_name
    else:
        display_name = _slug_to_display_name(slug)
    # Zip filename: use the bundle slug as the filesystem identity.
    # The [VCF Content Factory] prefix exists for display-name identity inside
    # VCF Ops, not for filesystem identity.  Filesystem identity is the slug.
    out_path = output_dir / f"{slug}.zip"
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

    # Build the SM scope for the renderer: the set of SM YAML files declared
    # in this bundle's manifest.  This prevents cross-bundle UUID leakage —
    # a third-party bundle's views resolve only against its own SMs, never
    # against native SMs or another bundle's SMs.
    # bundle_context label is included in any resolution-error messages.
    bundle_ctx = f'"{bundle.name}" (factory_native={bundle.factory_native})'
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

    # REST-format payload for install-script REST API path (content/customgroup.json)
    cg_rest_payload = _render_customgroup_rest_payload(bundle)
    cg_rest_json = json.dumps(cg_rest_payload, indent=2) if cg_rest_payload is not None else None
    # UI-format payload for drag-drop import (bundles/<slug>/customgroup.json)
    cg_ui_payload = _render_customgroup_ui_payload(bundle)
    cg_ui_json = json.dumps(cg_ui_payload, indent=2) if cg_ui_payload is not None else None

    reports_xml = render_report_xml(bundle.reports) if bundle.reports else None

    # Symptoms: serialize to wire format at build time.
    symptoms_payload = [s.to_wire() for s in bundle.symptoms] if bundle.symptoms else None
    symptoms_json = json.dumps(symptoms_payload, indent=2) if symptoms_payload else None

    # Alerts: store YAML-equivalent dict for runtime symptom ID resolution.
    alerts_payload = None
    if bundle.alerts:
        alerts_payload = []
        for a in bundle.alerts:
            # Serialize RecommendationRef objects as plain dicts so
            # json.dumps can handle them.
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
    else:
        alerts_json = None

    # AlertContent.xml — synthesised when the bundle has symptoms, alerts,
    # or recommendations.  A bundle with only recommendations (unusual but
    # valid) still emits AlertContent.xml so the recommendations are importable.
    alert_content_xml = None
    if bundle.symptoms or bundle.alerts or bundle.recommendations:
        alert_content_xml = render_alert_content_xml(
            bundle.symptoms,
            bundle.alerts,
            recommendations=bundle.recommendations or [],
        )

    # --- bundle.json ---
    bundle_json = _build_bundle_json(bundle, display_name)

    # --- Bundle-specific README ---
    bundle_readme = _generate_bundle_readme(bundle, display_name)

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
    # --- vcfops_manifest.json: in-zip metadata for staleness detection ---
    import datetime as _dt
    vcfops_manifest = json.dumps({
        "bundle_name": bundle.name,
        "template_version": CURRENT_TEMPLATE_VERSION,
        "built_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Root-level static files
        z.writestr("install.py", install_py)
        z.writestr("install.ps1", install_ps1)
        z.writestr("README.md", framework_readme)
        z.writestr("vcfops_manifest.json", vcfops_manifest)
        if license_text is not None:
            z.writestr("LICENSE", license_text)

        # Bundle subdirectory: metadata
        z.writestr(bundle_prefix + "bundle.json", bundle_json)
        z.writestr(bundle_prefix + "README.md", bundle_readme)

        # Drag-drop artifacts at bundle root (community-native filenames)
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

        # Installer source files under content/
        if sm_json:
            z.writestr(content_prefix + "supermetrics.json", sm_json)
        if views_xml:
            z.writestr(content_prefix + "views_content.xml", views_xml)
        if dashboard_json:
            # content/ copy retains PLACEHOLDER_USER_ID for runtime stamping
            z.writestr(content_prefix + "dashboard.json", dashboard_json)
        if cg_rest_json:
            z.writestr(content_prefix + "customgroup.json", cg_rest_json)
        if reports_xml:
            z.writestr(content_prefix + "reports_content.xml", reports_xml)
        if symptoms_json:
            z.writestr(content_prefix + "symptoms.json", symptoms_json)
        if alerts_json:
            z.writestr(content_prefix + "alerts.json", alerts_json)
        if bundle.builtin_metric_enables:
            bme_items = [
                {
                    "name": bme.metric_key,
                    "adapter_kind": bme.adapter_kind,
                    "resource_kind": bme.resource_kind,
                    "metric_key": bme.metric_key,
                    **( {"reason": bme.reason} if bme.reason else {} ),
                }
                for bme in bundle.builtin_metric_enables
            ]
            z.writestr(
                content_prefix + "builtin_metric_enables.json",
                json.dumps(bme_items, indent=2),
            )

    out_path.write_bytes(buf.getvalue())

    # Print audit summary after successful build.
    if audit_result is not None:
        print_audit_summary(audit_result, audit_mode)

    return out_path
