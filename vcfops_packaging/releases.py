"""Load and validate release manifests from releases/*.yaml.

A release manifest declares a shipping event: it references 1+ headline
artifacts (component or bundle YAMLs) and carries metadata (name, version,
description, release notes).

Schema
------
name:          str  (required) -- kebab-case slug, unique across all release manifests
version:       str  (required) -- "x.y" major.minor format (e.g. "1.0", "2.3")
description:   str  (required) -- free text
release_notes: str  (optional) -- free text
artifacts:     list (required, 1+ entries) -- each entry:
                   source:   str  (required) -- repo-relative path to source YAML
                   headline: bool (required) -- at least one must be true
deprecates:    list (optional) -- repo-relative paths to other release manifests
                   that this release retires; targets must exist on disk.

Validation rules
----------------
- ``name`` must be present, non-empty, and unique across all loaded manifests.
- ``version`` must match the ``x.y`` pattern (digits.digits).
- ``artifacts`` must be non-empty, each entry must have ``source`` (existing
  file) and ``headline`` (bool); at least one artifact must be ``headline: true``.
- ``deprecates`` entries must point to existing files.
- Flag-state consistency (two directions, both hard errors):
  (a) A headline component/bundle YAML has ``released: true`` but no release
      manifest references it as a headline.
  (b) A release manifest exists but its headline component has ``released: false``
      (or the field is absent, which defaults to false).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


VERSION_RE = re.compile(r"^\d+\.\d+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$|^[a-z0-9]$")

# ---------------------------------------------------------------------------
# Release-naming convention
# ---------------------------------------------------------------------------

#: Recognized type suffixes for the ``<content-stem>-<type>`` naming convention.
#: A release manifest ``name:`` that ends with one of these is considered conforming.
RELEASE_TYPE_SUFFIXES = frozenset({
    "dashboard",
    "view",
    "supermetric",
    "customgroup",
    "report",
    "bundle",
    "managementpack",
    "alert",
    "symptom",
    "recommendation",
})

#: Release manifest names that predate the convention and are permanently
#: grandfathered.  The WARN check skips these.
_LEGACY_RELEASE_NAMES: frozenset[str] = frozenset({
    "demand-driven-capacity-v2",
    "idps-planner",
})


class ReleaseValidationError(ValueError):
    pass


@dataclass
class ReleaseArtifact:
    source: str           # repo-relative path string, as written in YAML
    source_path: Path     # resolved absolute path
    headline: bool


@dataclass
class ReleaseDef:
    name: str
    version: str
    description: str
    release_notes: str
    artifacts: List[ReleaseArtifact]
    deprecates: List[Path]           # resolved absolute paths
    manifest_path: Path


def _load_released_flag(path: Path) -> Optional[bool]:
    """Return the ``released:`` flag from a content YAML, or None on load failure."""
    try:
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            return None
        raw = data.get("released", False)
        if isinstance(raw, bool):
            return raw
        return False
    except Exception:
        return None


def load_release(path: str | Path, repo_root: Optional[Path] = None) -> ReleaseDef:
    """Load a single release manifest YAML and validate its schema.

    Does NOT perform cross-manifest duplicate-name checks or flag-state
    consistency checks (those require the full corpus — see
    ``load_all_releases`` and ``validate_flag_state``).

    Args:
        path:      Path to a ``releases/*.yaml`` file.
        repo_root: Repo root for resolving ``source:`` paths.  When None,
                   defaults to two levels up from the manifest (releases/ is
                   one level under the repo root).

    Returns:
        A populated ``ReleaseDef``.

    Raises:
        ReleaseValidationError: if the manifest is invalid or any referenced
            source file or deprecates target does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise ReleaseValidationError(f"release manifest not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ReleaseValidationError(f"{path}: expected a YAML mapping")

    # --- name ---
    name = str(data.get("name", "") or "").strip()
    if not name:
        raise ReleaseValidationError(f"{path}: 'name' is required")
    if not SLUG_RE.match(name):
        raise ReleaseValidationError(
            f"{path}: 'name' must be kebab-case (lowercase letters, digits, "
            f"hyphens, periods; cannot start or end with a hyphen or period), "
            f"got {name!r}"
        )

    # --- version ---
    version = str(data.get("version", "") or "").strip()
    if not version:
        raise ReleaseValidationError(f"{path}: 'version' is required")
    if not VERSION_RE.match(version):
        raise ReleaseValidationError(
            f"{path}: 'version' must be in x.y format (e.g. '1.0', '2.3'), "
            f"got {version!r}"
        )

    # --- description ---
    description = str(data.get("description", "") or "").strip()
    if not description:
        raise ReleaseValidationError(f"{path}: 'description' is required")

    # --- release_notes (optional) ---
    release_notes = str(data.get("release_notes", "") or "").strip()

    # Resolve root: releases/ sits one level under repo root.
    if repo_root is None:
        repo_root = path.parent.parent

    def _resolve_source(ref: str) -> Path:
        p = Path(ref)
        if p.is_absolute() and p.exists():
            return p
        candidate = repo_root / p
        if candidate.exists():
            return candidate
        raise ReleaseValidationError(
            f"{path}: artifact source not found: {ref!r} (tried {candidate})"
        )

    # --- artifacts ---
    raw_artifacts = data.get("artifacts")
    if not raw_artifacts or not isinstance(raw_artifacts, list):
        raise ReleaseValidationError(
            f"{path}: 'artifacts' is required and must be a non-empty list"
        )

    artifacts: List[ReleaseArtifact] = []
    for i, entry in enumerate(raw_artifacts):
        if not isinstance(entry, dict):
            raise ReleaseValidationError(
                f"{path}: artifacts[{i}] must be a mapping, got {type(entry).__name__}"
            )
        source_str = str(entry.get("source", "") or "").strip()
        if not source_str:
            raise ReleaseValidationError(
                f"{path}: artifacts[{i}].source is required and must be non-empty"
            )
        headline_raw = entry.get("headline")
        if not isinstance(headline_raw, bool):
            raise ReleaseValidationError(
                f"{path}: artifacts[{i}].headline must be a boolean (true/false), "
                f"got {headline_raw!r}"
            )
        source_path = _resolve_source(source_str)
        artifacts.append(ReleaseArtifact(
            source=source_str,
            source_path=source_path,
            headline=bool(headline_raw),
        ))

    if not any(a.headline for a in artifacts):
        raise ReleaseValidationError(
            f"{path}: at least one artifact must have 'headline: true'"
        )

    # --- deprecates (optional) ---
    raw_deprecates = data.get("deprecates") or []
    if not isinstance(raw_deprecates, list):
        raise ReleaseValidationError(
            f"{path}: 'deprecates' must be a list, got {type(raw_deprecates).__name__}"
        )
    deprecates: List[Path] = []
    for i, dep_ref in enumerate(raw_deprecates):
        dep_str = str(dep_ref or "").strip()
        if not dep_str:
            raise ReleaseValidationError(
                f"{path}: deprecates[{i}] must be a non-empty path string"
            )
        dep_candidate = repo_root / dep_str
        if not dep_candidate.exists():
            raise ReleaseValidationError(
                f"{path}: deprecates target not found: {dep_str!r} "
                f"(tried {dep_candidate})"
            )
        deprecates.append(dep_candidate)

    return ReleaseDef(
        name=name,
        version=version,
        description=description,
        release_notes=release_notes,
        artifacts=artifacts,
        deprecates=deprecates,
        manifest_path=path,
    )


def load_all_releases(
    releases_dir: str | Path = "releases",
    repo_root: Optional[Path] = None,
) -> List[ReleaseDef]:
    """Load all release manifests from a directory.

    Also performs duplicate-name validation across the full corpus.

    Args:
        releases_dir: Directory to scan (defaults to ``releases/``).
        repo_root:    Passed through to ``load_release``; see that function.

    Returns:
        List of ``ReleaseDef`` objects, sorted by manifest filename.

    Raises:
        ReleaseValidationError: if any manifest fails validation, or if
            duplicate ``name:`` values are detected across manifests.
    """
    releases_dir = Path(releases_dir)
    if not releases_dir.exists():
        return []

    manifests = sorted(releases_dir.glob("*.y*ml"))
    releases: List[ReleaseDef] = []
    for p in manifests:
        releases.append(load_release(p, repo_root=repo_root))

    # Duplicate name check across the corpus.
    seen_names: dict[str, Path] = {}
    for r in releases:
        if r.name in seen_names:
            raise ReleaseValidationError(
                f"duplicate release name {r.name!r}: found in both "
                f"{seen_names[r.name]} and {r.manifest_path}"
            )
        seen_names[r.name] = r.manifest_path

    return releases


def validate_flag_state(
    releases: List[ReleaseDef],
    repo_root: Path,
) -> List[str]:
    """Check flag-state consistency between release manifests and content YAMLs.

    Two error directions — both are hard errors:
    (a) A release manifest exists but its headline component has
        ``released: false`` (or the field is absent).
    (b) A component/bundle YAML has ``released: true`` but no release
        manifest references it as a headline.

    This function only checks content types that carry the ``released:``
    field and are valid release manifest headline targets:
    - bundles/
    - dashboards/
    - views/
    - supermetrics/
    - customgroups/
    - reports/

    Args:
        releases:  Loaded release manifests (from ``load_all_releases``).
        repo_root: Absolute path to the repo root for scanning content dirs.

    Returns:
        A list of error message strings.  Empty list means all clear.
    """
    errors: List[str] = []

    # Collect all headline source_paths across all release manifests.
    headline_paths: set[Path] = set()
    for r in releases:
        for a in r.artifacts:
            if a.headline:
                headline_paths.add(a.source_path.resolve())

    # Direction (a): manifest exists, headline has released: false.
    for r in releases:
        for a in r.artifacts:
            if not a.headline:
                continue
            flag = _load_released_flag(a.source_path)
            if flag is None:
                # File failed to load (separate schema error); skip flag check.
                continue
            if not flag:
                errors.append(
                    f"release manifest {r.manifest_path.name!r} references "
                    f"{a.source!r} as headline but its 'released:' flag is false"
                )

    # Direction (b): content has released: true but no release manifest points at it.
    # Scan all content type directories that carry the released: field.
    content_dirs = [
        repo_root / "bundles",
        repo_root / "content" / "dashboards",
        repo_root / "content" / "views",
        repo_root / "content" / "supermetrics",
        repo_root / "content" / "customgroups",
        repo_root / "content" / "reports",
    ]
    for content_dir in content_dirs:
        if not content_dir.exists():
            continue
        for yaml_path in sorted(content_dir.glob("*.y*ml")):
            flag = _load_released_flag(yaml_path)
            if flag is True:
                if yaml_path.resolve() not in headline_paths:
                    errors.append(
                        f"{yaml_path.relative_to(repo_root)} has 'released: true' "
                        f"but no release manifest references it as a headline"
                    )

    return errors


def check_bundle_release_collision(
    bundles_dir: Path,
    releases: List[ReleaseDef],
) -> List[str]:
    """Hard-error check: a slug must not appear in both bundles/ and releases/.

    Scans every ``bundles/*.yaml`` filename stem and every loaded release
    manifest ``name:`` field.  If the same slug appears in both sets, returns
    an error string naming both files.

    Exception — legitimate bundle-release pairing: when a release manifest
    shares its slug with a bundle file AND its headline artifact's source
    points at that same bundle file (``bundles/<slug>.yaml`` or
    ``bundles/<slug>.yml``), the release manifest exists precisely to publish
    that bundle.  This is not a collision; it is skipped silently.

    Args:
        bundles_dir: Path to the ``bundles/`` directory (may not exist).
        releases:    Pre-loaded release manifests (from ``load_all_releases``).

    Returns:
        A list of error strings.  Empty list means no collision.
    """
    errors: List[str] = []
    if not bundles_dir.exists():
        return errors

    bundle_slugs: dict[str, Path] = {}
    for p in sorted(bundles_dir.glob("*.y*ml")):
        bundle_slugs[p.stem] = p

    release_by_name: dict[str, ReleaseDef] = {r.name: r for r in releases}

    for slug, bundle_path in bundle_slugs.items():
        if slug not in release_by_name:
            continue
        release = release_by_name[slug]
        # Check whether this is a legitimate bundle-release pairing: the
        # release manifest's headline artifact must point at this bundle file.
        headline_sources = {
            Path(a.source)
            for a in release.artifacts
            if a.headline
        }
        # Acceptable source paths for this bundle slug.
        expected_sources = {
            Path(f"bundles/{slug}.yaml"),
            Path(f"bundles/{slug}.yml"),
        }
        if headline_sources & expected_sources:
            # The headline source IS this bundle — legitimate pairing, not a collision.
            continue
        errors.append(
            f"slug collision: '{slug}' appears as both "
            f"bundle '{bundle_path}' and release manifest '{release.manifest_path}'"
        )

    return errors


def check_release_naming_convention(
    releases: List[ReleaseDef],
) -> List[str]:
    """WARN check: release manifest names should follow the ``<stem>-<type>`` convention.

    A name conforms if its last hyphen-delimited component is one of
    ``RELEASE_TYPE_SUFFIXES``.  Names in ``_LEGACY_RELEASE_NAMES`` are
    silently skipped.

    Returns:
        A list of warning strings.  Empty list means all clear.
    """
    warnings_: List[str] = []
    for r in releases:
        if r.name in _LEGACY_RELEASE_NAMES:
            continue
        # Check whether the name ends with a recognized type suffix.
        parts = r.name.rsplit("-", 1)
        if len(parts) < 2 or parts[-1] not in RELEASE_TYPE_SUFFIXES:
            warnings_.append(
                f"WARN  {r.manifest_path.name}: name {r.name!r} does not follow the "
                f"<content-stem>-<type> convention "
                f"(recognized types: {', '.join(sorted(RELEASE_TYPE_SUFFIXES))})"
            )
    return warnings_
