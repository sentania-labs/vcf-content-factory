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
    """One built distribution zip for a single release headline.

    For SDK pointer releases (``is_sdk_pointer=True``), no zip is built or
    copied to the distribution repo.  The artifact contributes a README entry
    only.  ``zip_path`` is ``None`` and ``pointer_info`` carries the registry
    data needed to render the README row.
    """
    zip_path: "Path | None"  # None for sdk-pointer releases
    dest_subdir: str         # "dashboards" / "bundles" / "views" / "management-packs" / ...
    headline_source: str     # the source YAML path that drove this artifact
    release_name: str
    release_version: str
    is_sdk_pointer: bool = False   # True iff this is a Tier 2 SDK adapter pointer
    pointer_info: "dict | None" = None  # populated when is_sdk_pointer=True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Map first path component (source prefix) to the discrete_builder content_type
# string.  "bundles" and "managementpacks" are handled separately.
# Supports both old bare prefixes and the new content/<type> layout.
_SOURCE_PREFIX_TO_DISCRETE_TYPE: dict[str, str] = {
    "dashboards":   "dashboard",
    "views":        "view",
    "supermetrics": "supermetric",
    "customgroups": "customgroup",
    "reports":      "report",
}

# For the new content/<type>/ layout, the containing dir of the YAML
# file is the type name.
# _build_component_headline() uses source_path.parent.name to find the type.

# Mapping from parent directory name to discrete_builder content_type.
# Used when source_prefix is not a bare type name (e.g. path is
# content/dashboards/foo.yaml → parent.name == "dashboards").
_PARENT_DIR_TO_DISCRETE_TYPE: dict[str, str] = {
    "dashboards":   "dashboard",
    "views":        "view",
    "supermetrics": "supermetric",
    "customgroups": "customgroup",
    "reports":      "report",
}


def _is_sdk_adapter_source(source_path: Path) -> bool:
    """Return True iff source_path is under content/sdk-adapters/<name>/."""
    return source_path.parent.parent.name == "sdk-adapters"


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
    extra_search_dirs: "list[Path] | None" = None,
) -> Path:
    """Build a component headline zip using the discrete builder.

    Args:
        source_path:        Absolute path to the component YAML file.
        source_prefix:      Content type directory name ("dashboards", "views", …).
        tmp_dir:            Temporary directory for builder output.
        extra_search_dirs:  Additional project root directories to scan for
                            the item and its dependencies.  Used when the
                            source lives under ``third_party/<project>/`` rather
                            than the factory-native ``content/`` tree.

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
        extra_search_dirs=extra_search_dirs,
    )
    return built


def _resolve_sdk_mp_pointer(source_path: Path) -> dict:
    """Resolve the registry entry for a Tier 2 SDK management pack headline.

    Looks up the adapter in ``knowledge/context/managed_paks.md`` by directory name and
    returns a pointer-info dict with all fields needed for README generation.
    No zip or binary is produced.

    Args:
        source_path:  Path to ``content/sdk-adapters/<name>/adapter.yaml``
                      (or any file inside the adapter project directory).

    Returns:
        Pointer-info dict::

            {
                "type": "sdk-pak-pointer",
                "adapter_name": "<name>",
                "adapter_kind": "<vcfcf_name>",
                "remote": "https://github.com/sentania-labs/vcf-content-factory-sdk-<name>",
                "latest_release_url": "https://github.com/.../releases/latest",
                "api_latest_url": "https://api.github.com/repos/.../releases/latest",
                "asset_glob": "*.pak"
            }

    Raises:
        ValueError: if the adapter is not found in the managed-paks registry.
            This is a hard failure — add the registry entry in
            ``knowledge/context/managed_paks.md`` before publishing.
    """
    from .managed_paks import (
        lookup_by_adapter_name,
        derived_latest_release_url,
        derived_api_latest_url,
    )

    # source_path points to content/sdk-adapters/<name>/adapter.yaml
    # (or similar); the adapter name is the direct parent directory name.
    adapter_name = source_path.parent.name

    pak = lookup_by_adapter_name(adapter_name)
    if pak is None:
        raise ValueError(
            f"SDK adapter {adapter_name!r} is not registered in knowledge/context/managed_paks.md. "
            f"This means the adapter has not been extracted to its own remote repo and "
            f"registered in the managed-paks registry yet. "
            f"Complete Workstream D (de-track migration) before publishing this adapter. "
            f"Do NOT fall back to a local build — add the registry entry instead."
        )

    return {
        "type": "sdk-pak-pointer",
        "adapter_name": pak.name,
        "adapter_kind": pak.adapter_kind,
        "remote": pak.remote,
        "latest_release_url": derived_latest_release_url(pak),
        "api_latest_url": derived_api_latest_url(pak),
        "asset_glob": "*.pak",
    }


# Keep the old name as a deprecated alias for any external callers.
# Internal publish path no longer calls it.
def _build_sdk_mp_headline(source_path: Path, tmp_dir: Path) -> Path:  # pragma: no cover
    """Deprecated — use ``_resolve_sdk_mp_pointer`` instead.

    Previously wrote a pointer zip to ``tmp_dir``.  The publish pipeline no
    longer produces a zip for SDK MP releases; this shim is preserved only for
    callers that were written against the old signature.  It will be removed in
    a future cleanup.
    """
    import json
    import zipfile

    pointer = _resolve_sdk_mp_pointer(source_path)
    zip_name = f"{pointer['adapter_kind']}-pointer.zip"
    zip_path = tmp_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pointer.json", json.dumps(pointer, indent=2) + "\n")
    return zip_path


def _build_mp_headline(
    source_path: Path,
    tmp_dir: Path,
) -> Path:
    """Build a management pack headline zip containing .pak and exchange JSON.

    Loads the ManagementPackDef from source_path, builds the .pak file via
    vcfops_managementpacks.builder.build_pak, renders the MPB UI exchange JSON
    via vcfops_managementpacks.render_export.render_mpb_exchange_json, and
    packages both into a single zip.

    Returns the path to the zip written to tmp_dir.
    """
    import json
    import zipfile

    from vcfops_managementpacks.loader import load_file
    from vcfops_managementpacks.builder import build_pak
    from vcfops_managementpacks.render_export import render_mpb_exchange_json

    mp = load_file(str(source_path))

    # Build the .pak file — build_pak returns the path to the created .pak
    pak_path = build_pak(mp, output_dir=tmp_dir)

    # Render the MPB UI exchange JSON
    exchange = render_mpb_exchange_json(mp)
    exchange_filename = f"{mp.adapter_kind}_exchange.json"
    exchange_path = tmp_dir / exchange_filename
    exchange_path.write_text(json.dumps(exchange, indent=2))

    # Package both into a single zip
    zip_name = f"{mp.adapter_kind}.zip"
    zip_path = tmp_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(pak_path, Path(pak_path).name)
        zf.write(exchange_path, exchange_filename)

    return zip_path


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
        release_path:  Path to a ``bundles/releases/*.yaml`` manifest.
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

        # -----------------------------------------------------------------------
        # Phase 5: detect direct third-party component releases.
        # Shape: third_party/<project>/<type>/<file>.yaml
        # grandparent.parent.name == "third_party" (i.e. great-grandparent of file)
        # -----------------------------------------------------------------------
        _is_third_party_component = (
            source_prefix in _SOURCE_PREFIX_TO_DISCRETE_TYPE
            and source_path.parent.parent.parent.name == "third_party"
        )

        if not _is_third_party_component:
            # Normalise project-level bundle files to "bundles":
            # third_party/<project>/PROJECT.yaml → parent.name == <project>
            #   → grandparent == "third_party"
            if source_prefix not in _SOURCE_PREFIX_TO_DISCRETE_TYPE and source_prefix != "bundles":
                if source_path.parent.parent.name == "third_party":
                    source_prefix = "bundles"

            # Normalise SDK adapter paths:
            # content/sdk-adapters/<name>/adapter.yaml
            #   → parent.name == <name>, grandparent.name == "sdk-adapters"
            if source_path.parent.parent.name == "sdk-adapters":
                source_prefix = "sdk-adapters"

        if _is_third_party_component:
            # Route via the third_party/<proj>/<type>/<file> path so
            # headline_to_dir resolves to ThirdPartyContent/<sub>.
            dest_subdir = headline_to_dir(
                f"third_party/{source_path.parent.parent.name}/{source_prefix}/{source_path.name}"
            )
        else:
            bundle_data = _load_bundle_data_if_bundle(source_path)
            dest_subdir = headline_to_dir(source_prefix + "/dummy.yaml", bundle_data=bundle_data)

        # -----------------------------------------------------------------------
        # SDK adapter headlines: pointer-only release — no zip produced.
        # The artifact carries pointer_info from the registry; the publish
        # orchestrator and README generator consume it directly.  Nothing is
        # written to output_dir for these releases.
        # -----------------------------------------------------------------------
        if source_prefix == "sdk-adapters":
            pointer_info = _resolve_sdk_mp_pointer(source_path)
            artifacts.append(ReleaseArtifact(
                zip_path=None,
                dest_subdir=dest_subdir,
                headline_source=source_str,
                release_name=release.name,
                release_version=release.version,
                is_sdk_pointer=True,
                pointer_info=pointer_info,
            ))
            continue

        final_filename = _zip_filename(release.name, release.version)
        final_path = output_dir / final_filename

        with tempfile.TemporaryDirectory(prefix="release_build_") as tmp_str:
            tmp_dir = Path(tmp_str)

            if _is_third_party_component:
                built_path = _build_component_headline(
                    source_path, source_prefix, tmp_dir,
                    extra_search_dirs=[source_path.parent.parent],
                )
            elif source_prefix == "bundles":
                built_path = _build_bundle_headline(source_path, tmp_dir, skip_audit)
            elif source_prefix in _SOURCE_PREFIX_TO_DISCRETE_TYPE:
                built_path = _build_component_headline(source_path, source_prefix, tmp_dir)
            elif source_prefix == "managementpacks":
                built_path = _build_mp_headline(source_path, tmp_dir)
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

def _load_bundle_data_if_bundle(source_path: Path) -> "dict | None":
    """If source_path is a bundle YAML or PROJECT.yaml, load and return its raw data dict.

    Returns None if loading fails or the file is not a bundle.

    Recognised bundle file locations:
    - bundles/*.yaml (parent == "bundles")
    - third_party/<project>/PROJECT.yaml (grandparent == "third_party")

    For PROJECT.yaml files that have no explicit ``dashboards:`` list, the
    dashboard count is discovered by scanning the project's dashboards/
    subdirectory.  This is needed so headline_to_dir can route correctly
    (exactly-1-dashboard -> ThirdPartyContent/dashboards) without requiring
    an explicit list in the PROJECT.yaml.
    """
    parent_name = source_path.parent.name
    grandparent_name = source_path.parent.parent.name
    is_bundle = (
        parent_name == "bundles"
        or grandparent_name == "third_party"
    )
    if not is_bundle:
        return None
    try:
        data = yaml.safe_load(source_path.read_text()) or {}
        if not isinstance(data, dict):
            return None
        # For PROJECT.yaml with no explicit dashboards list, discover from subdir.
        if source_path.name == "PROJECT.yaml" and not data.get("dashboards"):
            dash_dir = source_path.parent / "dashboards"
            if dash_dir.exists():
                data["dashboards"] = sorted(str(p) for p in dash_dir.rglob("*.y*ml"))
        return data
    except Exception:
        return None


def _artifact_dest_subdir(artifact: "_ManifestArtifact") -> str:
    """Return the distribution subdirectory for a release manifest artifact.

    Derives the prefix (dashboards, bundles, views, …) from the resolved
    absolute path rather than the raw source string, so absolute-path
    manifests (common in tests) work correctly alongside repo-relative ones.

    For bundle headlines, loads the bundle YAML to detect ``factory_native:
    false`` and routes third-party bundles under ``ThirdPartyContent/``.

    For direct third-party component paths
    (``third_party/<project>/<type>/<file>.yaml``), routes to
    ``ThirdPartyContent/<dist-sub>`` via the Phase 5 branch in
    ``headline_to_dir``.
    """
    source_prefix = artifact.source_path.parent.name

    # Phase 5: direct third-party component — shape is
    # third_party/<project>/<type>/<file>.yaml, so great-grandparent == "third_party".
    _is_third_party_component = (
        source_prefix in _SOURCE_PREFIX_TO_DISCRETE_TYPE
        and artifact.source_path.parent.parent.parent.name == "third_party"
    )
    if _is_third_party_component:
        project_name = artifact.source_path.parent.parent.name
        return headline_to_dir(
            f"third_party/{project_name}/{source_prefix}/{artifact.source_path.name}"
        )

    # Normalise project-level bundle files
    # (third_party/<project>/PROJECT.yaml → grandparent == "third_party") to "bundles".
    if source_prefix not in _SOURCE_PREFIX_TO_DISCRETE_TYPE and source_prefix != "bundles":
        grandparent = artifact.source_path.parent.parent.name
        if grandparent == "third_party":
            source_prefix = "bundles"

    # Normalise SDK adapter paths:
    # content/sdk-adapters/<name>/adapter.yaml → grandparent == "sdk-adapters"
    if artifact.source_path.parent.parent.name == "sdk-adapters":
        source_prefix = "sdk-adapters"

    bundle_data = _load_bundle_data_if_bundle(artifact.source_path)
    return headline_to_dir(source_prefix + "/dummy.yaml", bundle_data=bundle_data)


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
