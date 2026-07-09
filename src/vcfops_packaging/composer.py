"""Interactive bundle composer for vcfops_packaging.

Implements the /bundle CLI subcommand (Phase 4 of content-structure-v3.md).

Flow:
  1. Slug validation — unique across bundles/ and releases/.
  2. Display name + description.
  3. Component picking by type — factory + third-party, grouped by provenance.
  4. Dependency consistency check — walker finds dashboard deps missing from picks.
  5. Write bundles/<slug>.yaml (or print on --dry-run).

Public API
----------
  compose_bundle(
      slug, display_name, description,
      dry_run=False, force=False,
      repo_root=None,
      input_fn=None,   # injectable for testing; defaults to builtins.input
  ) -> int   (0 = ok, 1 = error)

  discover_components(repo_root, content_type) -> list[ComponentEntry]
    One entry per discovered YAML file across both provenances.

  check_slug_collision(slug, repo_root) -> str | None
    Return an error string if the slug is already taken, else None.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import yaml


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ComponentEntry:
    """One discoverable content component."""
    path: Path           # absolute path to the YAML file
    rel_path: str        # repo-relative path string (for bundle YAML)
    slug: str            # filename stem
    display_name: str    # from name: field in YAML (or slug if absent)
    provenance: str      # "factory" | third-party project slug | ""


# Content types the composer supports, in pick-order.
CONTENT_TYPES = [
    "dashboards",
    "views",
    "supermetrics",
    "customgroups",
    "symptoms",
    "alerts",
    "reports",
    "recommendations",
    "managementpacks",
]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _display_name_from_yaml(path: Path) -> str:
    """Read name: field from a YAML file, falling back to the stem."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            n = str(data.get("name", "") or "").strip()
            if n:
                return n
    except Exception:
        pass
    return path.stem


def discover_components(repo_root: Path, content_type: str) -> List[ComponentEntry]:
    """Discover all YAML files for a given content type across both provenances.

    Scans:
      - <repo_root>/content/<content_type>/*.yaml   (factory-native)
      - <repo_root>/third_party/*/<content_type>/*.yaml  (third-party)

    Returns list of ComponentEntry sorted: factory first, then each third-party
    project alphabetically, within each group alphabetically by slug.
    """
    entries: List[ComponentEntry] = []

    # Factory-native
    factory_dir = repo_root / "content" / content_type
    if factory_dir.exists():
        for p in sorted(factory_dir.glob("*.y*ml")):
            rel = str(p.relative_to(repo_root))
            entries.append(ComponentEntry(
                path=p,
                rel_path=rel,
                slug=p.stem,
                display_name=_display_name_from_yaml(p),
                provenance="factory",
            ))

    # Third-party
    third_party_dir = repo_root / "third_party"
    if third_party_dir.exists():
        for project_dir in sorted(third_party_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            type_dir = project_dir / content_type
            if not type_dir.exists():
                continue
            for p in sorted(type_dir.glob("*.y*ml")):
                rel = str(p.relative_to(repo_root))
                entries.append(ComponentEntry(
                    path=p,
                    rel_path=rel,
                    slug=p.stem,
                    display_name=_display_name_from_yaml(p),
                    provenance=project_dir.name,
                ))

    return entries


# ---------------------------------------------------------------------------
# Slug collision check
# ---------------------------------------------------------------------------

def check_slug_collision(slug: str, repo_root: Path) -> Optional[str]:
    """Return an error message if slug is already taken, else None.

    Checks:
      - bundles/<slug>.yaml exists
      - releases/<slug>.yaml exists
    """
    bundle_path = repo_root / "bundles" / f"{slug}.yaml"
    if bundle_path.exists():
        return f"bundle '{slug}' already exists at {bundle_path}"

    release_path = repo_root / "releases" / f"{slug}.yaml"
    if release_path.exists():
        return f"release manifest '{slug}' already exists at {release_path} (slugs must be unique across bundles/ and releases/)"

    return None


# ---------------------------------------------------------------------------
# Picker
# ---------------------------------------------------------------------------

def _parse_picks(raw: str, entries: List[ComponentEntry]) -> List[ComponentEntry]:
    """Parse a comma-separated list of indices and/or substring patterns.

    Accepts:
      - Bare integers (1-based index into the displayed list)
      - Substring patterns: matched case-insensitively against slug
      - "none" or empty string → empty selection

    Returns deduplicated list in the order picks first appear.
    """
    raw = raw.strip()
    if not raw or raw.lower() == "none":
        return []

    selected: List[ComponentEntry] = []
    seen_slugs: set = set()

    def _add(e: ComponentEntry) -> None:
        if e.slug not in seen_slugs:
            seen_slugs.add(e.slug)
            selected.append(e)

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for part in parts:
        # Integer index?
        try:
            idx = int(part)
            if 1 <= idx <= len(entries):
                _add(entries[idx - 1])
            # out-of-range integers are silently skipped
            continue
        except ValueError:
            pass
        # Substring match on slug
        pattern = part.lower()
        for e in entries:
            if pattern in e.slug.lower():
                _add(e)

    return selected


def _display_entries(entries: List[ComponentEntry], content_type: str, output_fn: Callable) -> None:
    """Print the numbered pick-list grouped by provenance."""
    if not entries:
        output_fn(f"  (no {content_type} found)")
        return

    current_provenance = None
    for i, e in enumerate(entries, 1):
        if e.provenance != current_provenance:
            current_provenance = e.provenance
            label = "factory" if e.provenance == "factory" else f"third-party [{e.provenance}]"
            output_fn(f"  [{label}]")
        output_fn(f"    {i:3d}. {e.slug}  —  {e.display_name}")


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def _check_deps(
    picked_dashboards: List[ComponentEntry],
    picked_views: List[ComponentEntry],
    picked_sms: List[ComponentEntry],
    picked_cgs: List[ComponentEntry],
    repo_root: Path,
) -> List[str]:
    """Run the dep walker on picked dashboards, return list of missing-dep warnings.

    Cross-provenance composition is explicitly allowed here (bundles are the
    legitimate place to compose across project boundaries) — we pass
    project_scope=None to the walker so no scope errors are raised.
    """
    if not picked_dashboards:
        return []

    try:
        # Load content objects for the picked items only.
        from vcfops_dashboards.loader import load_dashboard, load_view
        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_customgroups.loader import load_file as load_cg
        from vcfops_common.dep_walker import collect_deps

        dashboards = []
        for e in picked_dashboards:
            try:
                d = load_dashboard(e.path, enforce_framework_prefix=False, default_name_path="")
                dashboards.append(d)
            except Exception:
                pass  # loader errors surface separately during validate

        views = []
        for e in picked_views:
            try:
                v = load_view(e.path, enforce_framework_prefix=False)
                views.append(v)
            except Exception:
                pass

        sms = []
        for e in picked_sms:
            try:
                s = load_sm(e.path, enforce_framework_prefix=False)
                sms.append(s)
            except Exception:
                pass

        cgs = []
        for e in picked_cgs:
            try:
                c = load_cg(e.path, enforce_framework_prefix=False)
                cgs.append(c)
            except Exception:
                pass

        if not dashboards:
            return []

        # Walk with no scope enforcement — bundles allow cross-provenance.
        graph = collect_deps(
            dashboards=dashboards,
            all_views=views,
            all_sms=sms,
            all_customgroups=cgs,
            project_scope=None,
        )

        return graph.errors

    except ImportError:
        return []


# ---------------------------------------------------------------------------
# YAML serialization
# ---------------------------------------------------------------------------

def _build_bundle_yaml(
    slug: str,
    display_name: str,
    description: str,
    picks: dict,
) -> str:
    """Build a human-readable bundle YAML string.

    Field order: name, display_name, description, then content types
    in CONTENT_TYPES order.
    """
    lines = []
    lines.append(f"name: {slug}")
    lines.append(f"display_name: {_yaml_str(display_name)}")
    # Multi-line description uses block scalar
    lines.append("description: >")
    for dl in description.strip().splitlines():
        lines.append(f"  {dl}")
    lines.append("")

    for ct in CONTENT_TYPES:
        chosen = picks.get(ct, [])
        if chosen:
            lines.append(f"{ct}:")
            for e in chosen:
                lines.append(f"  - {e.rel_path}")
        else:
            lines.append(f"{ct}: []")

    lines.append("")
    return "\n".join(lines)


def _yaml_str(s: str) -> str:
    """Quote a string for YAML if it contains special characters."""
    if any(c in s for c in ('"', "'", ":", "#", "[", "]", "{", "}")):
        # Use double-quote with escaping
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


# ---------------------------------------------------------------------------
# Main composer entry point
# ---------------------------------------------------------------------------

def compose_bundle(
    slug: Optional[str],
    dry_run: bool = False,
    force: bool = False,
    repo_root: Optional[Path] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    output_fn: Optional[Callable[[str], None]] = None,
) -> int:
    """Run the interactive bundle composer.

    Args:
        slug:       Bundle slug (filename stem). None to prompt.
        dry_run:    Print proposed YAML, do not write.
        force:      Overwrite existing bundles/<slug>.yaml.
        repo_root:  Repo root directory. Defaults to cwd.
        input_fn:   Replacement for input() — useful for tests.
        output_fn:  Replacement for print() to stdout — useful for capturing.

    Returns:
        0 on success, 1 on error.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    repo_root = Path(repo_root).resolve()

    _input = input_fn if input_fn is not None else input
    _out = output_fn if output_fn is not None else (lambda s="", end="\n": print(s, end=end))

    # ------------------------------------------------------------------ #
    # Step 1: Slug                                                         #
    # ------------------------------------------------------------------ #
    if not slug:
        slug = _prompt_slug(repo_root, force, _input, _out)
        if slug is None:
            return 1
    else:
        collision = check_slug_collision(slug, repo_root)
        if collision and not force:
            print(f"ERROR: {collision}", file=sys.stderr)
            return 1

    # Validate slug format (kebab-case, lowercase)
    import re
    if not re.match(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$', slug):
        print(
            f"ERROR: slug must be kebab-case (lowercase letters, digits, hyphens; "
            f"cannot start or end with hyphen), got {slug!r}",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------ #
    # Step 2: Display name + description                                   #
    # ------------------------------------------------------------------ #
    default_display_name = slug.replace("-", " ").title()
    _out(f"\nDisplay name [{default_display_name}]: ", end="")
    try:
        raw_display = _input("").strip()
    except EOFError:
        raw_display = ""
    display_name = raw_display if raw_display else default_display_name

    _out("Description (type END on its own line when done):")
    desc_lines = []
    while True:
        try:
            line = _input("")
        except EOFError:
            break
        if line.strip() == "END":
            break
        desc_lines.append(line)
    description = "\n".join(desc_lines).strip()
    if not description:
        print("ERROR: description is required", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------ #
    # Step 3: Component picking by type                                    #
    # ------------------------------------------------------------------ #
    picks: dict = {}
    for ct in CONTENT_TYPES:
        entries = discover_components(repo_root, ct)
        if not entries:
            picks[ct] = []
            continue

        _out(f"\n--- {ct} ({len(entries)} available) ---")
        _display_entries(entries, ct, _out)
        _out(f"Pick {ct} (indices, slugs, or 'none'/blank to skip): ", end="")
        try:
            raw = _input("").strip()
        except EOFError:
            raw = ""
        chosen = _parse_picks(raw, entries)
        picks[ct] = chosen
        if chosen:
            _out(f"  Selected: {', '.join(e.slug for e in chosen)}")
        else:
            _out(f"  (none selected)")

    # ------------------------------------------------------------------ #
    # Step 4: Dependency consistency check                                 #
    # ------------------------------------------------------------------ #
    dep_warnings = _check_deps(
        picked_dashboards=picks.get("dashboards", []),
        picked_views=picks.get("views", []),
        picked_sms=picks.get("supermetrics", []),
        picked_cgs=picks.get("customgroups", []),
        repo_root=repo_root,
    )

    if dep_warnings:
        _out("\nDependency warnings (dashboard deps not included in bundle):")
        for w in dep_warnings:
            _out(f"  WARN: {w}")
        _out("Auto-add missing deps? [y/N]: ", end="")
        try:
            ans = _input("").strip().lower()
        except EOFError:
            ans = "n"
        if ans in ("y", "yes"):
            picks = _auto_add_deps(picks, dep_warnings, repo_root)
            _out("  Missing deps auto-added (where resolvable).")
        else:
            _out("  Leaving picks as-is. Bundle install may fail if deps are absent on the instance.")

    # ------------------------------------------------------------------ #
    # Step 5: Write (or dry-run)                                           #
    # ------------------------------------------------------------------ #
    bundle_yaml = _build_bundle_yaml(slug, display_name, description, picks)

    if dry_run:
        _out(f"\n--- bundles/{slug}.yaml (dry-run, not written) ---")
        _out(bundle_yaml)
        return 0

    out_path = repo_root / "bundles" / f"{slug}.yaml"
    if out_path.exists() and not force:
        print(f"ERROR: {out_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(bundle_yaml, encoding="utf-8")

    # Round-trip self-test: ensure the produced YAML loads cleanly.
    try:
        from vcfops_packaging.loader import load_bundle, BundleValidationError
        load_bundle(out_path)
    except Exception as e:
        print(
            f"ERROR: produced bundle YAML failed validation round-trip: {e}\n"
            f"  File written to {out_path} but may be unusable.",
            file=sys.stderr,
        )
        return 1

    _out(f"\nwritten: bundles/{slug}.yaml")
    total = sum(len(v) for v in picks.values())
    _out(f"  {total} component(s) across {sum(1 for v in picks.values() if v)} type(s)")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prompt_slug(
    repo_root: Path,
    force: bool,
    input_fn: Callable,
    output_fn: Callable,
) -> Optional[str]:
    """Prompt for a bundle slug, applying the <name>-bundle convention.

    When the user types a bare name without a ``-bundle`` suffix, we suggest
    ``<name>-bundle`` as the default and re-prompt with that value pre-filled.
    The user may override by typing a different slug at the confirmation step.
    """
    import re
    _SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$')

    for _ in range(5):  # max 5 attempts
        output_fn("Bundle slug (kebab-case, e.g. 'my-bundle'): ", end="")
        try:
            raw = input_fn("").strip()
        except EOFError:
            print("ERROR: no slug provided", file=sys.stderr)
            return None
        if not raw:
            output_fn("  (slug is required)")
            continue

        # Apply <name>-bundle convention when user omits the suffix.
        if not raw.endswith("-bundle"):
            suggested = f"{raw}-bundle"
            output_fn(f"Bundle slug [{suggested}]: ", end="")
            try:
                override = input_fn("").strip()
            except EOFError:
                override = ""
            slug = override if override else suggested
        else:
            slug = raw

        if not _SLUG_RE.match(slug):
            output_fn(f"  Invalid slug: must be kebab-case (lowercase, digits, hyphens, no leading/trailing hyphens)")
            continue
        collision = check_slug_collision(slug, repo_root)
        if collision and not force:
            output_fn(f"  Collision: {collision}")
            continue
        return slug

    print("ERROR: too many failed slug attempts", file=sys.stderr)
    return None


def _auto_add_deps(
    picks: dict,
    dep_warnings: List[str],
    repo_root: Path,
) -> dict:
    """Attempt to auto-resolve missing deps from dep walker error messages.

    The error messages from collect_deps contain the missing name in quotes.
    We search all components for a matching display_name and add them if found.
    This is best-effort; unresolvable deps are left as-is.
    """
    import re
    # Extract names from error strings like "references unknown view 'Some Name'"
    name_re = re.compile(r"'([^']+)'")

    for ct in CONTENT_TYPES:
        entries = discover_components(repo_root, ct)
        for w in dep_warnings:
            # Only try types mentioned in the warning
            if ct.rstrip("s") not in w.lower() and ct not in w.lower():
                continue
            for m in name_re.finditer(w):
                missing_name = m.group(1)
                for e in entries:
                    if e.display_name == missing_name:
                        existing_slugs = {x.slug for x in picks.get(ct, [])}
                        if e.slug not in existing_slugs:
                            picks.setdefault(ct, []).append(e)

    return picks
