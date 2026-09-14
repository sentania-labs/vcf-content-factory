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

Template stamping is removed entirely, install.py and install.ps1 are
static and read everything from bundle.json at runtime.

M2 row 3: the payload rendering, the drag-drop inner zips, bundle.json,
``vcfops_manifest.json`` and the outer zip layout live in
``vcfcf_core.packaging.assembly`` (re-exported here under their old names
for ``discrete_builder`` and tests). This module keeps what reads the repo:
the dependency audit, the static installer templates, the LICENSE, the
design note behind the bundle README, and the output path.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List, Optional

from vcfcf_core.packaging.assembly import (  # noqa: F401  (re-exported for old-path callers)
    DASHBOARD_DROPIN_USER_ID,
    PLACEHOLDER_USER_ID,
    _SM_CROSSREF_HINT_BUNDLE,
    _build_bundle_json,
    _build_dashboard_dropin_zip,
    _build_reports_dropin_zip,
    _build_views_inner_zip,
    _render_customgroup_rest_payload,
    _render_customgroup_ui_payload,
    _render_supermetrics_dict,
    assemble_distribution_zip,
    render_bundle_payloads,
    render_vcfops_manifest,
)
from vcfcf_supermetrics.loader import sm_id_map
from .loader import Bundle, BundleValidationError, load_bundle, render_bme_items  # noqa: F401
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


# PLACEHOLDER_USER_ID and DASHBOARD_DROPIN_USER_ID live in
# vcfcf_core.packaging.assembly (imported above).

# Templates live next to this file in vcfcf_packaging/templates/
_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_design_sections(bundle: Bundle) -> dict:
    """Load and extract named sections from a bundle's design artifact.

    Resolution order:
    1. Explicit ``design:`` field in the bundle manifest (repo-relative path).
    2. Convention: ``knowledge/designs/<bundle-name>.md`` at repo root.
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
    repo_root = Path(__file__).parent.parent.parent

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
        candidate = repo_root / "knowledge" / "designs" / f"{bundle.name}.md"
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
        # False, bundle.description is the DESCRIPTION.md the user authored,
        # it already provides the narrative (origin, context, usage notes).
        # The ## Provenance block above supplies the structured metadata
        # (source URL, captured date, version, author, license).
        # Duplicating extraction-origin language here creates double provenance.

    # --- Design artifact sections ---
    # Extracted from knowledge/designs/<bundle-name>.md (or manifest's design: field).
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
        "See the top-level `README.md` **Authentication** section for supported auth sources",
        "(Local, vCenter SSO, AD) and sources that are not supported (VIDB, VIDM).",
        "",
        "> **Policy enablement caveat.** The install script enables imported super",
        "> metrics on the **Default Policy** only. If your deployment uses",
        "> non-default, non-inheriting policies, you may need to manually enable the",
        "> imported super metrics in those policies, otherwise dashboard cells and",
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
        audit_mode: Dependency audit mode, "auto" (default), "strict", or
            "lax".  See vcfcf_packaging/audit.py for semantics.
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
    from .audit import print_audit_summary, run_dependency_audit

    bundle = load_bundle(bundle_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Dependency audit ---
    # Shared with discrete_builder.build_discrete, see audit.run_dependency_audit
    # (issue #77). Auto-added entries are merged into bundle.builtin_metric_enables
    # in place before bundle.json serialization below.
    audit_result = run_dependency_audit(
        bundle,
        str(bundle_path),
        live_describe=live_describe,
        audit_mode=audit_mode,
        skip_audit=skip_audit,
    )

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

    # --- Render content payloads (vcfcf_core.packaging.assembly) ---
    # Build the SM scope for the renderer: the set of SM YAML files declared
    # in this bundle's manifest.  This prevents cross-bundle UUID leakage,
    # a third-party bundle's views resolve only against its own SMs, never
    # against native SMs or another bundle's SMs.
    # bundle_context label is included in any resolution-error messages.
    bundle_ctx = f'"{bundle.name}" (factory_native={bundle.factory_native})'
    payloads = render_bundle_payloads(
        bundle,
        sm_map=sm_id_map(bundle.sm_paths, bundle_ctx),
        bundle_context=bundle_ctx,
    )

    # --- bundle.json ---
    bundle_json = _build_bundle_json(bundle, display_name)

    # --- Bundle-specific README ---
    bundle_readme = _generate_bundle_readme(bundle, display_name)

    # --- Repo root LICENSE ---
    repo_root = Path(__file__).parent.parent.parent
    license_path = repo_root / "LICENSE"
    license_text = license_path.read_text() if license_path.exists() else None

    # --- vcfops_manifest.json: in-zip metadata for staleness detection ---
    vcfops_manifest = render_vcfops_manifest(
        {
            "bundle_name": bundle.name,
            "template_version": CURRENT_TEMPLATE_VERSION,
        },
        built_at=_dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # --- Assemble zip ---
    out_path.write_bytes(assemble_distribution_zip(
        slug=slug,
        payloads=payloads,
        bundle_json=bundle_json,
        bundle_readme=bundle_readme,
        install_py=install_py,
        install_ps1=install_ps1,
        framework_readme=framework_readme,
        vcfops_manifest=vcfops_manifest,
        license_text=license_text,
    ))

    # Print audit summary after successful build.
    if audit_result is not None:
        print_audit_summary(audit_result, audit_mode)

    return out_path
