"""Factory entry point to the symptom loader (M2 row 1 move, row 3 wrapper).

The parse half lives in ``vcfcf_core.symptoms.loader`` and takes its
directory as a required argument. This wrapper keeps the pre-row-3 default
(``load_dir`` over ``symptoms``, relative to the working directory) so
every factory caller is unchanged. Every other name (``SymptomDef``,
``load_file``, ``SymptomValidationError``, ``_condition_to_wire``, ...) is
served by module ``__getattr__`` straight from the core module and reads
back the identical object; to monkeypatch a name the running loader sees,
patch ``vcfcf_core.symptoms.loader``.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from vcfcf_core.symptoms import loader as _core
from vcfcf_core.symptoms.loader import SymptomDef


def load_dir(directory: str | Path = "symptoms", enforce_framework_prefix: bool = True) -> List[SymptomDef]:
    return _core.load_dir(directory, enforce_framework_prefix=enforce_framework_prefix)


def __getattr__(name: str):
    """Every name this wrapper does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
