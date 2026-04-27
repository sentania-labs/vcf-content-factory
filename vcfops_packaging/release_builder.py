"""Build distribution zips for release manifests.

Given a release manifest, this module routes each headline artifact to the
appropriate builder (bundle or discrete), names the output zip per the release
convention, and returns a structured artifact list for the Phase 3 publish
orchestrator.

Public API
----------
build_release(release_path, output_dir) -> List[ReleaseArtifact]
    Build all headline zips for a release manifest.

expected_artifact_path(release, dest_root) -> Path
    Return the path the artifact would land at if published, without building.

artifact_already_exists(release, dest_root) -> bool
    True iff a zip with the expected filename already exists at dest_root/<subdir>/.

Naming convention
-----------------
Output zip: ``<release-name>.zip``  (versionless consumer artifact)
  e.g. ``demand-driven-capacity-v2.zip``

The ``release_version`` field in :class:`ReleaseArtifact` still carries the
version string from the release manifest — it is used internally for change
detection, audit, and commit messages.  The version never appears in the
consumer-facing zip filename so the distribution repo always contains exactly
one zip per release slug.

Routing
-------
- Bundle headline (``bundles/*.yaml``):
    delegates to ``vcfops_packaging.builder.build_bundle``
- Component headline (``dashboards/``, ``views/``, ``supermetrics/``,
  ``customgroups/``, ``reports/``):
    delegates to ``vcfops_packaging.discrete_builder.build_discrete``

Both builders write to a temporary working directory; the result is moved
to ``output_dir/<expected-filename>`` so the final filename always follows
the release manifest convention regardless of the builder's internal naming.
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

from .releases import ReleaseDef, ReleaseArtifact as _ManifestArtifact, load_release
from .release_types import headline_to_dir


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class ReleaseArtifact:
    """One built distribution zip for a single release headline."""
    zip_path: Path           # absolute path to the built zip on disk
    dest_subdir: str         # "dashboards" / "bundles" / "views" / ...
    headline_source: str     # the source YAML path that drove this artifact
    release_name: str
    release_version: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Map first path component (source prefix) to the discrete_builder content_type
# string.  "bundles" is handled separately; managementpacks is deferred.
_SOURCE_PREFIX_TO_DISCRETE_TYPE: dict[str, str] = {
    "dashboards":   "dashboard",
    "views":        "view",
    "supermetrics": "supermetric",
    "customgroups": "customgroup",
    "reports":      "report",
}


def _read_name_from_yaml(path: Path) -> str:
    """Read the ``name:`` field from a content or bundle YAML file.

    Args:
        path: Absolute path to the YAML file.

    Returns:
        The string value of the top-level ``name:`` field.

    Raises:
        ValueError: If the file cannot be parsed or has no ``name:`` field.
    """
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:
        raise ValueError(f"cannot parse YAML at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping, got {type(data).__name__}")
    name = data.get("name", "")
    if not name:
        raise ValueError(f"{path}: missing 'name:' field")
    return str(name).strip()


def _zip_filename(release_name: str, release_version: str = "") -> str:
    """Return the canonical consumer-facing output zip filename for a release.

    Convention: ``<release-name>.zip``  (versionless)
    e.g.  ``demand-driven-capacity-v2.zip``

    The ``release_version`` parameter is accepted but ignored — it is kept in
    the signature so callers that still pass it (e.g. the retirement handler,
    which needs the OLD versioned name for deprecated releases) can work without
    changes.  Only the retirement handler and the legacy-sweep need the version-
    bearing name; they construct it directly rather than using this helper.
    """
    return f"{release_name}.zip"


def _build_bundle_headline(
    source_path: Path,
    tmp_dir: Path,
    skip_audit: bool,
) -> Path:
    """Build a bundle headline zip using the bundle builder.

    Returns the path to the zip written by the builder (before rename).
    """
    from .builder import build_bundle

    built = build_bundle(
        bundle_path=source_path,
        output_dir=tmp_dir,
        skip_audit=skip_audit,
    )
    return built


def _build_component_headline(
    source_path: Path,
    source_prefix: str,
    tmp_dir: Path,
) -> Path:
    """Build a component headline zip using the discrete builder.

    Returns the path to the zip written by the builder (before rename).
    """
    from .discrete_builder import build_discrete

    content_type = _SOURCE_PREFIX_TO_DISCRETE_TYPE.get(source_prefix)
    if content_type is None:
        raise ValueError(
            f"source path prefix {source_prefix!r} has no discrete builder mapping. "
            f"Supported: {sorted(_SOURCE_PREFIX_TO_DISCRETE_TYPE)}"
        )

    item_name = _read_name_from_yaml(source_path)
    built = build_discrete(
        content_type=content_type,
        item_name=item_name,
        output_dir=tmp_dir,
    )
    return built


# ---------------------------------------------------------------------------
# Core public functions
# ---------------------------------------------------------------------------

def build_release(
    release_path: "str | Path",
    output_dir: Path,
    *,
    skip_audit: bool = True,
) -> List[ReleaseArtifact]:
    """Load the release manifest at release_path, build one zip per headline.

    For each headline artifact in the manifest:
      - Determines the content type via ``release_types.headline_to_dir()``.
      - Routes to the appropriate builder (bundle or discrete).
      - Names the output zip ``<release-name>.zip`` (versionless).
      - Writes it to ``output_dir``.

    Callers are responsible for managing ``output_dir`` (creation, cleanup).
    A missing ``output_dir`` is created automatically.

    Args:
        release_path:  Path to a ``releases/*.yaml`` manifest.
        output_dir:    Directory where output zips are written.
        skip_audit:    Passed to the bundle builder to skip the describe-cache
                       dependency audit (default True for offline builds).
                       Has no effect for discrete (component) headlines —
                       the discrete builder's dep walk is always offline.

    Returns:
        One ``ReleaseArtifact`` per headline artifact in the manifest.

    Raises:
        ReleaseValidationError:  If the manifest fails schema validation.
        ValueError:              If a headline type is unsupported.
        DiscreteBuilderError:    If the discrete builder cannot find the item.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    release = load_release(release_path)
    artifacts: List[ReleaseArtifact] = []

    for manifest_artifact in release.artifacts:
        if not manifest_artifact.headline:
            continue

        source_str = manifest_artifact.source
        source_path = manifest_artifact.source_path

        # Derive the source prefix (the containing directory name: "dashboards",
        # "bundles", "views", etc.) from the resolved absolute source path.
        # Using source_path.parent.name is more robust than parsing the raw
        # source_str, since tests may write absolute paths into the manifest.
        source_prefix = source_path.parent.name
        dest_subdir = headline_to_dir(source_prefix + "/dummy.yaml")

        final_filename = _zip_filename(release.name, release.version)
        final_path = output_dir / final_filename

        with tempfile.TemporaryDirectory(prefix="release_build_") as tmp_str:
            tmp_dir = Path(tmp_str)

            if source_prefix == "bundles":
                built_path = _build_bundle_headline(source_path, tmp_dir, skip_audit)
            elif source_prefix in _SOURCE_PREFIX_TO_DISCRETE_TYPE:
                built_path = _build_component_headline(source_path, source_prefix, tmp_dir)
            else:
                raise ValueError(
                    f"unsupported headline source prefix {source_prefix!r} "
                    f"in {release_path}"
                )

            # Move/rename from builder's internal filename to release convention.
            shutil.move(str(built_path), str(final_path))

        artifacts.append(ReleaseArtifact(
            zip_path=final_path.resolve(),
            dest_subdir=dest_subdir,
            headline_source=source_str,
            release_name=release.name,
            release_version=release.version,
        ))

    return artifacts


# ---------------------------------------------------------------------------
# Stale-check / idempotence helpers for Phase 3
# ---------------------------------------------------------------------------

def _artifact_dest_subdir(artifact: "_ManifestArtifact") -> str:
    """Return the distribution subdirectory for a release manifest artifact.

    Derives the prefix (dashboards, bundles, views, …) from the resolved
    absolute path rather than the raw source string, so absolute-path
    manifests (common in tests) work correctly alongside repo-relative ones.
    """
    source_prefix = artifact.source_path.parent.name
    return headline_to_dir(source_prefix + "/dummy.yaml")


def expected_artifact_path(release: ReleaseDef, dest_root: Path) -> Path:
    """Return the path the first headline artifact would land at if published.

    Used by the Phase 3 publish orchestrator for idempotence checks.
    When a release has multiple headlines each goes to its own subdir, so
    this returns only the path for the first headline artifact.  For
    multi-headline releases, iterate expected_artifact_paths() (if added
    in Phase 3) or call expected_artifact_path() once per headline.

    Args:
        release:   A loaded ReleaseDef (from load_release / load_all_releases).
        dest_root: Root of the distribution repo (e.g. Path("vcf-content-factory-bundles/")).

    Returns:
        Absolute path to where the zip would be written.
    """
    # Find the first headline artifact.
    headline = next(
        (a for a in release.artifacts if a.headline),
        None,
    )
    if headline is None:
        raise ValueError(f"release {release.name!r} has no headline artifact")

    dest_subdir = _artifact_dest_subdir(headline)
    filename = _zip_filename(release.name, release.version)
    return (dest_root / dest_subdir / filename).resolve()


def artifact_already_exists(release: ReleaseDef, dest_root: Path) -> bool:
    """True iff the expected artifact zip already exists at dest_root/<subdir>/.

    Checks only the first headline artifact.  For multi-headline releases,
    check each headline separately.

    Args:
        release:   A loaded ReleaseDef.
        dest_root: Root of the distribution repo.

    Returns:
        True if the file exists, False otherwise.
    """
    try:
        path = expected_artifact_path(release, dest_root)
    except ValueError:
        return False
    return path.exists()
