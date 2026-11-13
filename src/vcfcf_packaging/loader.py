"""Factory entry point to the bundle manifest loader (M2 row 3).

The parse half (``Bundle``, ``BundleValidationError``, ``BuiltinMetricEnable``,
``parse_builtin_metric_enables``, ``render_bme_items``, the manifest schema
in its docstring) lives in ``vcfcf_core.packaging.loader``. This module adds
what a library must not do on its own and that every factory caller relied
on:

- sniff the repo root that repo-relative references resolve against
  (``_find_repo_root``: walk up from the manifest for a ``vcfcf_common`` or
  ``src/vcfcf_common`` sibling, falling back to the manifest's parent's
  parent);
- resolve report sections against ``content/views`` and
  ``content/dashboards`` under the working directory (the pre-row-3
  report loader default, kept verbatim). For a third-party
  ``PROJECT.yaml`` the project's own ``views/`` and ``dashboards/`` come
  first and that same factory content second (since 2026-11-13): a
  project report may name its own view, or a factory view it cross-links
  (``cross_links``), as before;
- mint a uuid4 into a super metric, view, dashboard or report YAML that
  has no ``id`` and derive ``provenance`` from the repo layout;
- default ``load_all_bundles`` to the ``bundles`` directory.

``load_bundle`` and ``load_all_bundles`` keep their old signatures. Every
other name is served by module ``__getattr__`` straight from the core
module and reads back the identical object; to monkeypatch a name the
running loader sees, patch ``vcfcf_core.packaging.loader``.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import List, Sequence

from vcfcf_core.packaging import loader as _core
from vcfcf_core.packaging.loader import Bundle, BundleValidationError


def _find_repo_root(start: Path) -> Path:
    """Walk up from the manifest's directory to a plausible repo root.

    Manifests in bundles/ are one level under repo root; PROJECT.yaml files
    in third_party/<project>/ are two levels under it. The marker is a
    ``vcfcf_common`` (or ``src/vcfcf_common``) child; the fallback is the
    manifest's parent's parent.
    """
    current = start
    for _ in range(5):
        if (current / "vcfcf_common").exists() or (current / "src" / "vcfcf_common").exists():
            return current
        current = current.parent
    return start.parent  # fallback: manifest's parent


def _mint_id_into_file(path: Path) -> str:
    from vcfcf_dashboards.loader import _mint_id_into_file as _mint
    return _mint(path)


def _provenance_of(path: Path) -> str:
    from vcfcf_common.provenance import provenance_from_path
    return provenance_from_path(path)


def _write_name_index(dirs: Sequence[Path], dest: Path, dashboards: bool) -> None:
    """``{id, name}`` stubs for every view (or dashboard) YAML under
    ``dirs``, the first directory that has a name winning it. The report
    loader indexes a single directory by exactly these two fields."""
    import yaml
    from vcfcf_core.reports.loader import _build_dashboard_index, _build_view_index
    build = _build_dashboard_index if dashboards else _build_view_index
    merged: dict = {}
    for d in dirs:
        for name, oid in build(Path(d)).items():
            merged.setdefault(name, oid)
    dest.mkdir(parents=True)
    for i, (name, oid) in enumerate(sorted(merged.items())):
        (dest / f"{i}.yaml").write_text(yaml.safe_dump({"id": oid, "name": name}), encoding="utf-8")


def load_bundle(path: str | Path) -> Bundle:
    """Load a bundle manifest and every content object it references, with
    the factory's root sniff, minting and provenance (see module docstring)."""
    path = Path(path)
    kwargs = dict(repo_root=_find_repo_root(path.parent), on_missing_id=_mint_id_into_file,
                  provenance_of=_provenance_of)
    if path.name != "PROJECT.yaml":
        return _core.load_bundle(path, report_views_dir=Path("content/views"),
                                 report_dashboards_dir=Path("content/dashboards"), **kwargs)
    # A third-party project's report names its own views and dashboards
    # (beside PROJECT.yaml) or factory content it cross-links (content/
    # under the working directory, as before). Own first: a project report
    # naming its own view could not resolve against content/ alone (found
    # by import-local, 2026-11-13). The index is built after the project's
    # views and dashboards load, so an id minted into one is seen.
    index = Path(tempfile.mkdtemp(prefix="vcfcf-report-names-"))

    def report_dirs():
        _write_name_index([path.parent / "views", Path("content/views")], index / "views", False)
        _write_name_index([path.parent / "dashboards", Path("content/dashboards")], index / "dashboards", True)
        return index / "views", index / "dashboards"
    try:
        return _core.load_bundle(path, report_dirs=report_dirs, **kwargs)
    finally:
        shutil.rmtree(index, ignore_errors=True)


def load_all_bundles(bundles_dir: str | Path = "bundles") -> List[Bundle]:
    """Load all bundle manifests from a directory."""
    bundles_dir = Path(bundles_dir)
    if not bundles_dir.exists():
        return []
    bundles = []
    for p in sorted(bundles_dir.rglob("*.y*ml")):
        bundles.append(load_bundle(p))
    return bundles


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
