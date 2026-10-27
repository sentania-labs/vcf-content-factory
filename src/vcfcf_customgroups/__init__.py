"""vcfcf_customgroups: factory wrapper for dynamic custom groups.

``VCFOpsCustomGroupClient`` is resolved lazily by module ``__getattr__``
because the client pulls in ``requests``; offline loads must not need it.
"""
from .loader import (
    CustomGroupDef,
    CustomGroupValidationError,
    load_dir,
    load_file,
)

__all__ = [
    "VCFOpsCustomGroupClient",
    "CustomGroupDef",
    "CustomGroupValidationError",
    "load_dir",
    "load_file",
]


def __getattr__(name: str):
    if name == "VCFOpsCustomGroupClient":
        from .client import VCFOpsCustomGroupClient  # noqa: PLC0415
        globals()["VCFOpsCustomGroupClient"] = VCFOpsCustomGroupClient
        return VCFOpsCustomGroupClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
