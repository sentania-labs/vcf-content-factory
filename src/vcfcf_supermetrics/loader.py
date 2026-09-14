"""Factory entry point to the super metric loader (M2 row 3).

The parse and validate half lives in ``vcfcf_core.supermetrics.loader``.
This module adds the things a library must not do on its own and that
every factory caller relied on:

- mint a uuid4 into an authored YAML that has no ``id``
  (``_mint_id_into_file``, the UUID contract in
  knowledge/context/authoring/uuids_and_cross_references.md),
- derive ``provenance`` from the repo layout (``vcfcf_common.provenance``),
- default ``load_dir`` to the ``supermetrics`` directory, and
- the unscoped ``sm_id_map()`` scan of ``content/supermetrics`` then
  ``supermetrics`` under the working directory (the pre-row-2 renderer's
  native mode, kept verbatim).

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

    Scoped (``sm_scope`` is a list of SM YAML paths, possibly empty): the
    core map over exactly those files, loaded with
    ``enforce_framework_prefix=False`` and this module's minting and
    provenance callbacks; any load failure is a ``ValueError`` naming
    ``bundle_context``.

    Unscoped (``sm_scope`` is None): the pre-row-2 renderer's native mode,
    kept verbatim. Scan ``content/supermetrics`` then ``supermetrics``
    relative to the working directory (first that is a directory wins) and
    swallow every error into an empty map. ``load_dir`` builds its list
    before returning, so the result is all-or-nothing, as before. The core
    ``sm_id_map(None)`` is an empty map; only this wrapper scans.
    """
    if sm_scope is not None:
        return _core.sm_id_map(
            sm_scope, bundle_context,
            on_missing_id=_mint_id_into_file, provenance_of=_provenance_of,
        )
    sm_map: dict[str, str] = {}
    try:
        for candidate in (Path("content/supermetrics"), Path("supermetrics")):
            if candidate.is_dir():
                for sm in load_dir(candidate):
                    sm_map[sm.name] = sm.id
                break
    except Exception:
        pass
    return sm_map


def load_dir(directory: str | Path = "supermetrics", enforce_framework_prefix: bool = True) -> List[SuperMetricDef]:
    return _core.load_dir(
        directory,
        enforce_framework_prefix=enforce_framework_prefix,
        on_missing_id=_mint_id_into_file,
        provenance_of=_provenance_of,
    )


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
