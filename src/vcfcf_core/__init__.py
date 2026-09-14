"""vcf-cf-tooling-core: the location-agnostic part of the VCF Content Factory.

Import name ``vcfcf_core``. Everything here parses, tokenizes, renders, or
walks content in memory. Nothing here reads ``.env``, assumes a ``content/``
or ``knowledge/`` tree exists, calls a VCF Ops instance, or writes a file it
was not handed a path for. ``tests/test_core_contract.py`` enforces that.

Design: ``knowledge/designs/tooling-core-carveout-v1.md``. Modules land here
row by row; the factory keeps a one-line re-export at each old path so
existing imports keep working.

``__version__`` comes from the installed distribution's metadata (the wheel
is versioned from a ``core-vX.Y.Z`` git tag). When the package is imported
from the source tree with no wheel installed, it reports ``0.0.0+src``.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _dist_version

try:
    __version__ = _dist_version("vcf-cf-tooling-core")
except PackageNotFoundError:  # running from src/ via PYTHONPATH, not installed
    __version__ = "0.0.0+src"

__all__ = ["__version__"]
