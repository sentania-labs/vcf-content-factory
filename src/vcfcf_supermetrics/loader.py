"""Factory entry point to the super metric loader (M2 row 3).

The parse and validate half lives in ``vcfcf_core.supermetrics.loader``.
This module adds the things a library must not do on its own and that
every factory caller relied on:

- mint a uuid4 into an authored YAML that has no ``id``
  (``_mint_id_into_file``, the UUID contract in
  knowledge/context/authoring/uuids_and_cross_references.md),
- derive ``provenance`` from the repo layout (``vcfcf_common.provenance``),
  and
- default ``load_dir`` to the ``supermetrics`` directory.

The unscoped ``sm_id_map()`` cwd scan (``content/supermetrics`` then
``supermetrics``) was removed with issue #270: every caller now passes a
scope, and ``supermetric:"<name>"`` columns on the standalone dashboards
paths resolve through ``vcfcf_dashboards.sm_columns`` instead. ``sm_id_map()``
with no scope is now the core's empty map.

``load_file``, ``load_dir`` and ``sm_id_map`` keep their old signatures and
pass the callbacks into the core loader. Every other name (``SuperMetricDef``,
``SuperMetricValidationError``, ``LOOPING_FUNCS``, ``_strict_load``,
``_UUID_RE``, ...) is served by module ``__getattr__`` straight from the
core module, so ``from vcfcf_supermetrics.loader import X`` works for any
``X`` the core module defines and reads back the identical object. That is
a read-only view: ``monkeypatch.setattr(vcfcf_supermetrics.loader, "X", ...)``
binds a new attribute on this wrapper and the core loader keeps calling its
own. To affect the running loader, patch ``vcfcf_core.supermetrics.loader``.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Iterable, List, Optional

from vcfcf_core.supermetrics import loader as _core
from vcfcf_core.supermetrics.loader import SuperMetricDef


def _mint_id_into_file(path: Path) -> str:
    """Generate a uuid4 and prepend `id: <uuid>` to the YAML file.

    Called on first validate when a YAML lacks an `id`. Per
    `knowledge/context/authoring/uuids_and_cross_references.md`, UUIDs are
    stable content identifiers: generated once, never changed after.
    """
    new_id = str(uuid.uuid4())
    original = path.read_text()
    path.write_text(f"id: {new_id}\n{original}")
    return new_id


def _provenance_of(path: Path) -> str:
    from vcfcf_common.provenance import provenance_from_path
    return provenance_from_path(path)


def load_file(path: str | Path, enforce_framework_prefix: bool = True) -> SuperMetricDef:
    return _core.load_file(
        path,
        enforce_framework_prefix=enforce_framework_prefix,
        on_missing_id=_mint_id_into_file,
        provenance_of=_provenance_of,
    )


def sm_id_map(sm_scope: Optional[Iterable[Path]] = None, bundle_context: Optional[str] = None) -> dict[str, str]:
    """Super metric name to uuid map for the view renderer (M2 row 2).

    The core map over exactly the SM YAML paths in ``sm_scope`` (possibly
    empty), loaded with ``enforce_framework_prefix=False`` and this module's
    minting and provenance callbacks; any load failure, or two different SMs
    sharing a display name, is a ``ValueError`` naming ``bundle_context``.
    ``None`` is an empty map, as in the core (the unscoped cwd scan was
    removed with issue #270).
    """
    return _core.sm_id_map(
        sm_scope, bundle_context,
        on_missing_id=_mint_id_into_file, provenance_of=_provenance_of,
    )


def load_dir(directory: str | Path = "supermetrics", enforce_framework_prefix: bool = True) -> List[SuperMetricDef]:
    return _core.load_dir(
        directory,
        enforce_framework_prefix=enforce_framework_prefix,
        on_missing_id=_mint_id_into_file,
        provenance_of=_provenance_of,
    )


def _preview_id(path: Path) -> str:
    """A stable stand-in id for an id-less SM YAML, never written to it:
    uuid5 of the resolved path.  Lets a read-only load keep an id-less SM
    (its formula is still checked) without the file changing
    (``vcfcf_dashboards.sm_columns.load_sm_dir_readonly``)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, Path(path).resolve().as_uri()))


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
