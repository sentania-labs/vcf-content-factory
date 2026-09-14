"""Factory entry point to the custom group loader (M2 row 3).

The parse and validate half (``CustomGroupDef``, ``to_wire``, ``to_ui_wire``,
the YAML schema in its docstring) lives in
``vcfcf_core.customgroups.loader``. This module adds what a library must
not do on its own: derive ``provenance`` from the repo layout
(``vcfcf_common.provenance``) and default ``load_dir`` to the
``customgroups`` directory. Custom groups carry no UUID, so there is no
minting here.

``load_file`` and ``load_dir`` keep their old signatures and pass the
provenance callback into the core loader. Every other name
(``CustomGroupDef``, ``CustomGroupValidationError``, ``COMPARE_OPS``,
``collect_required_types``, ``_strict_load``, ...) is served by module
``__getattr__`` straight from the core module and reads back the identical
object. That is a read-only view: to monkeypatch a name the running loader
sees, patch ``vcfcf_core.customgroups.loader``.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from vcfcf_core.customgroups import loader as _core
from vcfcf_core.customgroups.loader import CustomGroupDef


def _provenance_of(path: Path) -> str:
    from vcfcf_common.provenance import provenance_from_path
    return provenance_from_path(path)


def load_file(path: str | Path, enforce_framework_prefix: bool = True) -> CustomGroupDef:
    return _core.load_file(
        path,
        enforce_framework_prefix=enforce_framework_prefix,
        provenance_of=_provenance_of,
    )


def load_dir(directory: str | Path = "customgroups", enforce_framework_prefix: bool = True) -> List[CustomGroupDef]:
    return _core.load_dir(
        directory,
        enforce_framework_prefix=enforce_framework_prefix,
        provenance_of=_provenance_of,
    )


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
