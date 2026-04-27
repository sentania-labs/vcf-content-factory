"""README auto-generation helper for the bundles distribution repo.

Regenerates per-section tables in a README.md between marker pairs:

    <!-- AUTO:START <section-name> -->
    | Name | Version | Description |
    |---|---|---|
    | ... |
    <!-- AUTO:END -->

Sections supported (factory-repo content flags, original update_readme):
    bundles                -- released bundle manifests (bundles/*.yaml, factory_native=True)
    third-party-bundles    -- released third-party bundle manifests (bundles/third_party/*.yaml)
    management-packs       -- released management pack YAMLs (managementpacks/*.yaml)
    dashboards             -- individually released dashboards
    supermetrics           -- individually released super metrics
    views                  -- individually released views
    reports                -- individually released reports
    alerts                 -- individually released alerts
    customgroups           -- individually released custom groups

Sections supported (release manifests, update_readme_release / Phase 3):
    release-catalog        -- per-subdir tables generated from releases/*.yaml manifests
                             (bundles, dashboards, views, supermetrics, customgroups,
                              reports, management-packs) + retired section.

Empty section = blank body between markers (no table header emitted if no items).

Usage (CLI)::

    python3 -m vcfops_packaging update-readme <readme-path> [--repo-root <path>]

Usage (programmatic)::

    from vcfops_packaging.readme_gen import update_readme
    changed = update_readme(Path("../vcf-content-factory-bundles/README.md"))

    # Phase 3 — release-manifest-driven generation:
    from vcfops_packaging.readme_gen import update_readme_release
    changed = update_readme_release(
        Path("../vcf-content-factory-bundles/README.md"),
        dist_repo=Path("../vcf-content-factory-bundles/"),
        releases=releases,
    )
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


# ---------------------------------------------------------------------------
# Phase 3 — release-manifest-driven README generation
# ---------------------------------------------------------------------------

# Canonical display name for each dist subdir.
_SUBDIR_HEADING: dict[str, str] = {
    "bundles":         "Bundles",
    "dashboards":      "Dashboards",
    "views":           "Views",
    "supermetrics":    "Super Metrics",
    "customgroups":    "Custom Groups",
    "reports":         "Reports",
    "management-packs": "Management Packs",
}

# Ordered iteration order for factory-native section rendering.
_SUBDIR_ORDER = [
    "bundles",
    "dashboards",
    "views",
    "supermetrics",
    "customgroups",
    "reports",
    "management-packs",
]

# Third-party subdir heading labels (sub-path -> heading text).
_THIRD_PARTY_SUBDIR_HEADING: dict[str, str] = {
    "ThirdPartyContent/dashboards": "Dashboards",
    "ThirdPartyContent/bundles":    "Bundles",
}

# Ordered iteration order for third-party sub-sections.
_THIRD_PARTY_SUBDIR_ORDER = [
    "ThirdPartyContent/dashboards",
    "ThirdPartyContent/bundles",
]


def _render_release_table(rows: list[dict]) -> str:
    """Render the per-subdir release table for factory-native content.

    Each row dict has keys: name, released, description, download, install.
    (Version is internal-only; it is not shown in the consumer-facing catalog.)
    Returns empty string if rows is empty.
    """
    if not rows:
        return ""
    lines = [
        "| Name | Released | Description | Download | Install |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        name = str(row.get("name", "")).replace("|", "\\|")
        released = str(row.get("released", "")).replace("|", "\\|")
        description = str(row.get("description", "")).replace("|", "\\|")
        download = str(row.get("download", "")).replace("|", "\\|")
        install = str(row.get("install", "")).replace("|", "\\|")
        lines.append(f"| {name} | {released} | {description} | {download} | {install} |")
    return "\n".join(lines) + "\n"


def _render_third_party_table(rows: list[dict]) -> str:
    """Render the per-subdir release table for third-party content.

    Third-party rows carry additional License and Authors columns read from
    the bundle YAML's ``license:`` and ``author:`` fields.

    Shape: Name | Version | Released | Description | License | Authors | Download | Install

    Returns empty string if rows is empty.
    """
    if not rows:
        return ""
    lines = [
        "| Name | Version | Released | Description | License | Authors | Download | Install |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        name = str(row.get("name", "")).replace("|", "\\|")
        version = str(row.get("version", "")).replace("|", "\\|")
        released = str(row.get("released", "")).replace("|", "\\|")
        description = str(row.get("description", "")).replace("|", "\\|")
        license_val = str(row.get("license", "")).replace("|", "\\|")
        authors = str(row.get("authors", "")).replace("|", "\\|")
        download = str(row.get("download", "")).replace("|", "\\|")
        install = str(row.get("install", "")).replace("|", "\\|")
        lines.append(
            f"| {name} | {version} | {released} | {description} "
            f"| {license_val} | {authors} | {download} | {install} |"
        )
    return "\n".join(lines) + "\n"


def _load_bundle_yaml_for_release(artifact) -> dict:
    """Load the raw bundle YAML dict for a release artifact, or return {}."""
    try:
        import yaml as _yaml
        data = _yaml.safe_load(artifact.source_path.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _render_release_catalog(dist_repo: Path, releases: list) -> str:
    """Render the full release-catalog AUTO section body.

    Produces factory-native per-subdir H2 sections, a Third-Party Content
    H2 section with sub-sections, and a Retired section.

    Args:
        dist_repo: Root of the distribution repo (for mtime lookups and retired/ scan).
        releases:  List of ReleaseDef objects (already loaded, selftest skipped).

    Returns:
        The markdown body to insert between the AUTO markers (without the markers).
    """
    from .release_builder import _artifact_dest_subdir, _zip_filename

    # Group releases by subdir — factory-native and third-party separately.
    by_subdir: dict[str, list] = {s: [] for s in _SUBDIR_ORDER}
    by_third_party: dict[str, list] = {s: [] for s in _THIRD_PARTY_SUBDIR_ORDER}

    for r in releases:
        for a in r.artifacts:
            if not a.headline:
                continue
            subdir = _artifact_dest_subdir(a)

            # Versionless consumer artifact filename.
            filename = _zip_filename(r.name)
            zip_path = dist_repo / subdir / filename

            # Release date from filesystem mtime if the zip exists, else "—".
            if zip_path.exists():
                mtime = zip_path.stat().st_mtime
                released_date = (
                    __import__("datetime")
                    .datetime
                    .utcfromtimestamp(mtime)
                    .strftime("%Y-%m-%d")
                )
            else:
                released_date = "—"

            # Description: first sentence of the release manifest description.
            desc = (r.description or "").strip()
            first_sentence = desc.split(".")[0].strip()
            if first_sentence and not first_sentence.endswith("."):
                first_sentence += "."

            # Download link: subdir-prefixed path so it resolves from the
            # dist-repo root (README lives at the root, zip lives at
            # <subdir>/<filename>).
            zip_url = f"{subdir}/{filename}"
            download_cell = f"[Download]({zip_url})"

            # Install column: bare command in a code fence.
            install_cell = "`python3 install.py`"

            if subdir in by_third_party:
                # Third-party row — load license + author from bundle YAML.
                bundle_data = _load_bundle_yaml_for_release(a)
                by_third_party[subdir].append({
                    "name": r.name,
                    "version": r.version,
                    "released": released_date,
                    "description": first_sentence,
                    "license": bundle_data.get("license", "") or "",
                    "authors": bundle_data.get("author", "") or "",
                    "download": download_cell,
                    "install": install_cell,
                })
            else:
                if subdir not in by_subdir:
                    by_subdir[subdir] = []
                by_subdir[subdir].append({
                    "name": r.name,
                    # version is intentionally omitted — internal-only field;
                    # the catalog table does not show version to consumers.
                    "released": released_date,
                    "description": first_sentence,
                    "download": download_cell,
                    "install": install_cell,
                })
            break  # one entry per release (first headline wins for catalog row)

    # Build the retired section.
    retired_rows = _collect_retired_rows(dist_repo, releases)

    # Render factory-native sections.
    parts: list[str] = []
    for subdir in _SUBDIR_ORDER:
        rows = by_subdir.get(subdir, [])
        heading = _SUBDIR_HEADING.get(subdir, subdir.title())
        parts.append(f"\n## {heading}\n")
        table = _render_release_table(rows)
        if table:
            parts.append(table)
        else:
            parts.append("_No releases yet._\n")

    # Render third-party section (only if any third-party releases exist).
    has_third_party = any(rows for rows in by_third_party.values())
    if has_third_party:
        parts.append("\n## Third-Party Content\n")
        parts.append(
            "_Content authored by the community and packaged here for convenience. "
            "License and authorship information is shown per item._\n"
        )
        for subdir in _THIRD_PARTY_SUBDIR_ORDER:
            rows = by_third_party.get(subdir, [])
            if not rows:
                continue
            sub_heading = _THIRD_PARTY_SUBDIR_HEADING.get(subdir, subdir.title())
            parts.append(f"\n### {sub_heading}\n")
            table = _render_third_party_table(rows)
            if table:
                parts.append(table)

    # Retired section.
    parts.append("\n## Retired\n")
    if retired_rows:
        lines = [
            "| Name | Subdir | Retired | Reason | Download |",
            "|---|---|---|---|---|",
        ]
        for row in retired_rows:
            name = str(row.get("name", "")).replace("|", "\\|")
            subdir_val = str(row.get("subdir", "")).replace("|", "\\|")
            retired_date = str(row.get("retired_date", "—")).replace("|", "\\|")
            reason = str(row.get("reason", "")).replace("|", "\\|")
            # Download link uses retired/<subdir>/<filename> path.
            zip_name = str(row.get("name", ""))
            download_cell = f"[Download](retired/{subdir_val}/{zip_name})"
            lines.append(f"| {name} | {subdir_val} | {retired_date} | {reason} | {download_cell} |")
        parts.append("\n".join(lines) + "\n")
    else:
        parts.append("_No retired artifacts._\n")

    return "\n" + "".join(parts)


def _collect_retired_rows(dist_repo: Path, releases: list) -> list[dict]:
    """Collect rows for the Retired section.

    Scans retired/<subdir>/ directories.  For each zip, checks whether a
    release manifest's deprecates: list references it (to produce a reason);
    otherwise marks it as "stale: no source release manifest".
    """
    from .release_builder import _artifact_dest_subdir, _zip_filename
    from .releases import load_release

    # Build a reverse map: zip filename -> deprecating release name.
    # Register both the versionless name and the legacy versioned name so the
    # map works regardless of when the deprecated zip was published.
    deprecated_by: dict[str, str] = {}
    for r in releases:
        if not r.deprecates:
            continue
        for dep_manifest_path in r.deprecates:
            try:
                dep_rel = load_release(dep_manifest_path)
            except Exception:
                continue
            for a in dep_rel.artifacts:
                if not a.headline:
                    continue
                subdir = _artifact_dest_subdir(a)
                versionless_name = _zip_filename(dep_rel.name)
                versioned_name = f"{dep_rel.name}-{dep_rel.version}.zip"
                for filename in (versionless_name, versioned_name):
                    deprecated_by[f"{subdir}/{filename}"] = r.name

    retired_dir = dist_repo / "retired"
    if not retired_dir.exists():
        return []

    rows = []
    all_subdirs = list(_SUBDIR_ORDER) + list(_THIRD_PARTY_SUBDIR_ORDER)
    for subdir in all_subdirs:
        sub_retired = retired_dir / subdir
        if not sub_retired.exists():
            continue
        for zip_path in sorted(sub_retired.glob("*.zip")):
            key = f"{subdir}/{zip_path.name}"
            if zip_path.exists():
                mtime = zip_path.stat().st_mtime
                retired_date = (
                    __import__("datetime")
                    .datetime
                    .utcfromtimestamp(mtime)
                    .strftime("%Y-%m-%d")
                )
            else:
                retired_date = "—"
            reason = (
                f"deprecated by {deprecated_by[key]!r}"
                if key in deprecated_by
                else "stale: no source release manifest"
            )
            rows.append({
                "name": zip_path.name,
                "subdir": subdir,
                "retired_date": retired_date,
                "reason": reason,
            })
    return rows


def update_readme_release(
    readme_path: Path,
    dist_repo: Path,
    releases: list,
) -> bool:
    """Regenerate the ``release-catalog`` AUTO section in a README.md.

    Unlike ``update_readme()`` (which reads from factory repo content flags),
    this function builds the catalog from a pre-loaded list of ReleaseDef
    objects (from the publish orchestrator) and looks up zip mtime from
    the dist repo.

    The README must contain:

        <!-- AUTO:START release-catalog -->
        ...
        <!-- AUTO:END -->

    Content outside the markers is preserved verbatim.

    Args:
        readme_path: Path to the README.md in the dist repo.
        dist_repo:   Root of the dist repo (for mtime + retired/ lookups).
        releases:    List of ReleaseDef objects (selftest fixture excluded).

    Returns:
        True if the file was modified, False if unchanged.

    Raises:
        FileNotFoundError: if readme_path does not exist.
        ValueError:        if no ``release-catalog`` AUTO marker is found.
    """
    readme_path = Path(readme_path)
    if not readme_path.exists():
        raise FileNotFoundError(f"README not found: {readme_path}")

    content = readme_path.read_text(encoding="utf-8")
    original = content

    # Check marker exists.
    if "<!-- AUTO:START release-catalog -->" not in content:
        raise ValueError(
            f"No '<!-- AUTO:START release-catalog -->' marker found in {readme_path}. "
            f"Add the marker pair to enable auto-generation."
        )

    catalog_body = _render_release_catalog(dist_repo, releases)

    def _replace(m: re.Match) -> str:
        section_name = m.group(2)
        if section_name != "release-catalog":
            return m.group(0)
        open_marker = m.group(1)
        close_marker = m.group(4)
        return f"{open_marker}{catalog_body}{close_marker}"

    updated = _MARKER_RE.sub(_replace, content)
    if updated != original:
        readme_path.write_text(updated, encoding="utf-8")
        return True
    return False
