"""vcfcf_supermetrics: factory wrapper for super metrics.

``VCFOpsClient`` is resolved lazily by module ``__getattr__`` because the
client pulls in ``requests``. Importing a submodule for offline work
(``vcfcf_supermetrics.loader``, ``.crossref``) must not need ``requests``:
build-buildkit runs with only PyYAML installed.
"""
from .loader import SuperMetricDef, load_dir, load_file

__all__ = ["VCFOpsClient", "SuperMetricDef", "load_dir", "load_file"]


def __getattr__(name: str):
    if name == "VCFOpsClient":
        from .client import VCFOpsClient  # noqa: PLC0415
        globals()["VCFOpsClient"] = VCFOpsClient
        return VCFOpsClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
