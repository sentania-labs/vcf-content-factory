"""Factory entry point to the report loader (M2 row 3).

The parse and validate half (``ReportDef``, ``Section``, the YAML schema
in its docstring) lives in ``vcfcf_core.reports.loader``. This module adds
what a library must not do on its own:

- mint a uuid4 into an authored YAML that has no ``id``
  (``_mint_id_into_file``, same contract as views and dashboards), and
- default the directories: reports under ``content/reports``, view and
  dashboard name references resolved against ``content/views`` and
  ``content/dashboards`` (relative to the working directory, as before).

``load_file`` and ``load_dir`` keep their old signatures and pass the
minting callback into the core loader. Every other name (``ReportDef``,
``Section``, ``ReportValidationError``, ``_STATIC_CONTENT_KEYS``,
``_build_view_index``, ...) is served by module ``__getattr__`` straight
from the core module and reads back the identical object. That is a
read-only view: to monkeypatch a name the running loader sees, patch
``vcfcf_core.reports.loader``.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

from vcfcf_core.reports import loader as _core
from vcfcf_core.reports.loader import ReportDef


def _mint_id_into_file(path: Path) -> str:
    """Prepend ``id: <uuid4>`` to the YAML file, same contract as dashboards."""
    new_id = str(uuid.uuid4())
    original = path.read_text()
    path.write_text(f"id: {new_id}\n{original}")
    return new_id


def load_file(
    path: str | Path,
    views_dir: str | Path = "content/views",
    dashboards_dir: str | Path = "content/dashboards",
    enforce_framework_prefix: bool = True,
) -> ReportDef:
    """Load and validate one report YAML, minting a UUID into the file on
    first validate (same contract as views and dashboards)."""
    return _core.load_file(
        path,
        views_dir=views_dir,
        dashboards_dir=dashboards_dir,
        enforce_framework_prefix=enforce_framework_prefix,
        on_missing_id=_mint_id_into_file,
    )


def load_dir(
    directory: str | Path = "content/reports",
    views_dir: str | Path = "content/views",
    dashboards_dir: str | Path = "content/dashboards",
    enforce_framework_prefix: bool = True,
) -> List[ReportDef]:
    return _core.load_dir(
        directory,
        views_dir=views_dir,
        dashboards_dir=dashboards_dir,
        enforce_framework_prefix=enforce_framework_prefix,
        on_missing_id=_mint_id_into_file,
    )


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
