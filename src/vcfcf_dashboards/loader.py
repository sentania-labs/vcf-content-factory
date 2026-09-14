"""Factory entry point to the dashboard / view loader (M2 row 2).

The parse and validate half lives in ``vcfcf_core.dashboards.loader``. This
module adds the two things a library must not do on its own and that every
factory caller relied on:

- mint a uuid4 into an authored YAML that has no ``id``
  (``_mint_id_into_file``, same contract as the super metric loader), and
- derive ``provenance`` from the repo layout (``vcfcf_common.provenance``).

``load_view``, ``load_dashboard`` and ``load_all`` keep their old signatures
and pass those two behaviours into the core loader as callbacks. Every other
name (dataclasses, ``stable_id``, ``parse_summary_for``, underscore helpers)
is served by module ``__getattr__`` straight from the core module, so
``from vcfcf_dashboards.loader import X`` works for any ``X`` the core
module defines and reads back the identical object. That is a read-only
view: ``monkeypatch.setattr(vcfcf_dashboards.loader, "stable_id", ...)``
binds a new attribute on this wrapper and the core loader keeps calling
its own. To affect the running loader, patch ``vcfcf_core.dashboards.loader``.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from vcfcf_core.dashboards import loader as _core
from vcfcf_core.dashboards.loader import Dashboard, ViewDef


def _mint_id_into_file(path: Path) -> str:
    """Mint a uuid4 and prepend ``id: <uuid>`` to the YAML file.

    Same contract as the super metric loader: UUIDs are generated
    once on first validate and never touched after. See
    knowledge/context/authoring/uuids_and_cross_references.md.
    """
    new_id = str(uuid.uuid4())
    original = path.read_text()
    path.write_text(f"id: {new_id}\n{original}")
    return new_id


def _provenance_of(path: Path) -> str:
    # Lazy import, as the pre-row-2 loader did: vcfcf_common's package
    # __init__ pulls in .env machinery that a plain load must not trigger.
    from vcfcf_common.provenance import provenance_from_path
    return provenance_from_path(path)


def load_view(path: Path, enforce_framework_prefix: bool = True, embedded_in_dashboard: bool = False) -> ViewDef:
    return _core.load_view(
        path,
        enforce_framework_prefix=enforce_framework_prefix,
        embedded_in_dashboard=embedded_in_dashboard,
        on_missing_id=_mint_id_into_file,
        provenance_of=_provenance_of,
    )


def load_dashboard(path: Path, enforce_framework_prefix: bool = True, default_name_path: str = "VCF Content Factory") -> Dashboard:
    return _core.load_dashboard(
        path,
        enforce_framework_prefix=enforce_framework_prefix,
        default_name_path=default_name_path,
        on_missing_id=_mint_id_into_file,
        provenance_of=_provenance_of,
    )


def load_all(views_dir: Path, dashboards_dir: Path, enforce_framework_prefix: bool = True, default_name_path: str = "VCF Content Factory") -> tuple[list[ViewDef], list[Dashboard]]:
    return _core.load_all(
        views_dir,
        dashboards_dir,
        enforce_framework_prefix=enforce_framework_prefix,
        default_name_path=default_name_path,
        on_missing_id=_mint_id_into_file,
        provenance_of=_provenance_of,
    )


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
