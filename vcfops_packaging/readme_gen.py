"""README auto-generation helper for the bundles distribution repo.

Regenerates per-section tables in a README.md between marker pairs:

    <!-- AUTO:START <section-name> -->
    | Name | Version | Description |
    |---|---|---|
    | ... |
    <!-- AUTO:END -->

Sections supported:
    bundles                -- released bundle manifests (bundles/*.yaml, factory_native=True)
    third-party-bundles    -- released third-party bundle manifests (bundles/third_party/*.yaml)
    management-packs       -- released management pack YAMLs (managementpacks/*.yaml)
    dashboards             -- individually released dashboards
    supermetrics           -- individually released super metrics
    views                  -- individually released views
    reports                -- individually released reports
    alerts                 -- individually released alerts
    customgroups           -- individually released custom groups

Empty section = blank body between markers (no table header emitted if no items).

Usage (CLI)::

    python3 -m vcfops_packaging update-readme <readme-path> [--repo-root <path>]

Usage (programmatic)::

    from vcfops_packaging.readme_gen import update_readme
    changed = update_readme(Path("../vcf-content-factory-bundles/README.md"))
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).parent.parent

# Marker pattern: <!-- AUTO:START <section> --> ... <!-- AUTO:END -->
_MARKER_RE = re.compile(
    r"(<!-- AUTO:START (\S+) -->)(.*?)(<!-- AUTO:END -->)",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Section data collectors
# ---------------------------------------------------------------------------

def _collect_bundles(repo_root: Path) -> list[dict]:
    """Collect released factory-native bundle manifests."""
    from .loader import load_bundle, BundleValidationError
    bundles_dir = repo_root / "bundles"
    if not bundles_dir.exists():
        return []
    items = []
    for p in sorted(bundles_dir.glob("*.y*ml")):
        try:
            b = load_bundle(p)
        except BundleValidationError:
            continue
        if b.released and b.factory_native:
            display = b.display_name or _slug_to_display_name(b.name)
            items.append({
                "name": f"[VCF Content Factory] {display}",
                "version": b.version or "1.0.0",
                "description": (b.description or "").splitlines()[0].strip() if b.description else "",
            })
    return items


def _collect_third_party_bundles(repo_root: Path) -> list[dict]:
    """Collect released third-party bundle manifests."""
    from .loader import load_bundle, BundleValidationError
    tp_dir = repo_root / "bundles" / "third_party"
    if not tp_dir.exists():
        return []
    items = []
    for p in sorted(tp_dir.rglob("*.y*ml")):
        try:
            b = load_bundle(p)
        except BundleValidationError:
            continue
        if b.released:
            name = b.display_name or _slug_to_display_name(b.name)
            items.append({
                "name": name,
                "version": b.version or "1.0.0",
                "description": (b.description or "").splitlines()[0].strip() if b.description else "",
            })
    return items


def _collect_management_packs(repo_root: Path) -> list[dict]:
    """Collect released management pack definitions."""
    from vcfops_managementpacks.loader import load_dir, ManagementPackValidationError
    mp_dir = repo_root / "managementpacks"
    if not mp_dir.exists():
        return []
    items = []
    try:
        mps = load_dir(mp_dir)
    except Exception:
        return []
    for mp in mps:
        if mp.released:
            items.append({
                "name": mp.name,
                "version": mp.version or "1.0.0",
                "description": (mp.description or "").splitlines()[0].strip() if mp.description else "",
            })
    return items


def _collect_dashboards(repo_root: Path) -> list[dict]:
    """Collect individually released dashboards."""
    from vcfops_dashboards.loader import load_all, DashboardValidationError
    vd = repo_root / "views"
    dd = repo_root / "dashboards"
    if not dd.exists():
        return []
    try:
        _, dashboards = load_all(vd, dd)
    except DashboardValidationError:
        return []
    items = []
    for d in dashboards:
        if d.released:
            items.append({
                "name": d.name,
                "version": d.version or "1.0.0",
                "description": (d.description or "").splitlines()[0].strip() if d.description else "",
            })
    return sorted(items, key=lambda x: x["name"])


def _collect_supermetrics(repo_root: Path) -> list[dict]:
    """Collect individually released super metrics."""
    from vcfops_supermetrics.loader import load_dir
    sm_dir = repo_root / "supermetrics"
    if not sm_dir.exists():
        return []
    try:
        sms = load_dir(sm_dir)
    except Exception:
        return []
    items = []
    for sm in sms:
        if sm.released:
            items.append({
                "name": sm.name,
                "version": sm.version or "1.0.0",
                "description": (sm.description or "").splitlines()[0].strip() if sm.description else "",
            })
    return sorted(items, key=lambda x: x["name"])


def _collect_views(repo_root: Path) -> list[dict]:
    """Collect individually released views."""
    from vcfops_dashboards.loader import load_view, DashboardValidationError
    views_dir = repo_root / "views"
    if not views_dir.exists():
        return []
    items = []
    for p in sorted(views_dir.rglob("*.y*ml")):
        try:
            v = load_view(p)
        except DashboardValidationError:
            continue
        if v.released:
            items.append({
                "name": v.name,
                "version": v.version or "1.0.0",
                "description": (v.description or "").splitlines()[0].strip() if v.description else "",
            })
    return sorted(items, key=lambda x: x["name"])


def _collect_reports(repo_root: Path) -> list[dict]:
    """Collect individually released reports."""
    from vcfops_reports.loader import load_dir, ReportValidationError
    r_dir = repo_root / "reports"
    if not r_dir.exists():
        return []
    try:
        reports = load_dir(r_dir, views_dir=repo_root / "views", dashboards_dir=repo_root / "dashboards")
    except ReportValidationError:
        return []
    items = []
    for r in reports:
        if r.released:
            items.append({
                "name": r.name,
                "version": r.version or "1.0.0",
                "description": (r.description or "").splitlines()[0].strip() if r.description else "",
            })
    return sorted(items, key=lambda x: x["name"])


def _collect_alerts(repo_root: Path) -> list[dict]:
    """Collect individually released alerts."""
    from vcfops_alerts.loader import load_dir, AlertValidationError
    a_dir = repo_root / "alerts"
    if not a_dir.exists():
        return []
    try:
        alerts = load_dir(a_dir)
    except AlertValidationError:
        return []
    items = []
    for a in alerts:
        if a.released:
            items.append({
                "name": a.name,
                "version": a.version or "1.0.0",
                "description": (a.description or "").splitlines()[0].strip() if a.description else "",
            })
    return sorted(items, key=lambda x: x["name"])


def _collect_customgroups(repo_root: Path) -> list[dict]:
    """Collect individually released custom groups."""
    from vcfops_customgroups.loader import load_dir, CustomGroupValidationError
    cg_dir = repo_root / "customgroups"
    if not cg_dir.exists():
        return []
    try:
        cgs = load_dir(cg_dir)
    except CustomGroupValidationError:
        return []
    items = []
    for cg in cgs:
        if cg.released:
            items.append({
                "name": cg.name,
                "version": cg.version or "1.0.0",
                "description": (cg.description or "").splitlines()[0].strip() if cg.description else "",
            })
    return sorted(items, key=lambda x: x["name"])


_SECTION_COLLECTORS = {
    "bundles": _collect_bundles,
    "third-party-bundles": _collect_third_party_bundles,
    "management-packs": _collect_management_packs,
    "dashboards": _collect_dashboards,
    "supermetrics": _collect_supermetrics,
    "views": _collect_views,
    "reports": _collect_reports,
    "alerts": _collect_alerts,
    "customgroups": _collect_customgroups,
}


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

def _render_table(items: list[dict]) -> str:
    """Render a Markdown table for a section. Returns empty string if no items."""
    if not items:
        return ""
    lines = [
        "| Name | Version | Description |",
        "|---|---|---|",
    ]
    for item in items:
        name = item["name"].replace("|", "\\|")
        version = item["version"].replace("|", "\\|")
        description = item["description"].replace("|", "\\|")
        lines.append(f"| {name} | {version} | {description} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def update_readme(
    readme_path: Path,
    repo_root: Optional[Path] = None,
) -> bool:
    """Regenerate AUTO sections in a README.md file.

    Args:
        readme_path: Path to the README.md to update (in the bundles repo).
        repo_root: Path to the factory repo root. Defaults to the package parent.

    Returns:
        True if the file was modified, False if no changes were needed.
    """
    if repo_root is None:
        repo_root = _REPO_ROOT

    readme_path = Path(readme_path)
    if not readme_path.exists():
        raise FileNotFoundError(f"README not found: {readme_path}")

    content = readme_path.read_text(encoding="utf-8")
    original = content

    def _replace(m: re.Match) -> str:
        open_marker = m.group(1)   # <!-- AUTO:START <section> -->
        section_name = m.group(2)
        close_marker = m.group(4)  # <!-- AUTO:END -->

        collector = _SECTION_COLLECTORS.get(section_name)
        if collector is None:
            # Unknown section — leave unchanged
            return m.group(0)

        items = collector(repo_root)
        table = _render_table(items)
        if table:
            body = f"\n{table}"
        else:
            body = ""
        return f"{open_marker}{body}{close_marker}"

    updated = _MARKER_RE.sub(_replace, content)
    if updated != original:
        readme_path.write_text(updated, encoding="utf-8")
        return True
    return False


# ---------------------------------------------------------------------------
# Display-name helper (mirrors builder.py)
# ---------------------------------------------------------------------------
_ACRONYMS = frozenset({
    "vks", "vm", "vms", "sm", "sms", "vcf", "cpu", "gpu",
    "ram", "mem", "ha", "drs", "nsx", "esxi", "vcsa",
})


def _slug_to_display_name(slug: str) -> str:
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
