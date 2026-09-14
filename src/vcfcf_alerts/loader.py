"""Factory entry point to the alert loader (M2 row 1 move, row 3 wrapper).

The parse half lives in ``vcfcf_core.alerts.loader`` and takes its
directory as a required argument. This wrapper keeps the pre-row-3 defaults
(``load_dir`` over ``alerts``, ``load_recommendations`` over
``recommendations``, both relative to the working directory) so every
factory caller is unchanged. Every other name (``AlertDef``,
``Recommendation``, ``load_file``, ``load_recommendation_file``,
``AlertValidationError``, underscore helpers) is served by module
``__getattr__`` straight from the core module and reads back the identical
object; to monkeypatch a name the running loader sees, patch
``vcfcf_core.alerts.loader``.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from vcfcf_core.alerts import loader as _core
from vcfcf_core.alerts.loader import AlertDef, Recommendation


def load_dir(directory: str | Path = "alerts", enforce_framework_prefix: bool = True) -> List[AlertDef]:
    return _core.load_dir(directory, enforce_framework_prefix=enforce_framework_prefix)


def load_recommendations(directory: str | Path = "recommendations", enforce_framework_prefix: bool = True) -> List[Recommendation]:
    return _core.load_recommendations(directory, enforce_framework_prefix=enforce_framework_prefix)


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
