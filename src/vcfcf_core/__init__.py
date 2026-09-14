"""vcf-cf-tooling-core: the location-agnostic part of the VCF Content Factory.

Import name ``vcfcf_core``. Everything here parses, tokenizes, renders, or
walks content in memory. Nothing here reads ``.env``, assumes a ``content/``
or ``knowledge/`` tree exists, calls a VCF Ops instance, or writes a file it
was not handed a path for. ``tests/test_core_contract.py`` enforces that.

Design: ``knowledge/designs/tooling-core-carveout-v1.md``. Modules land here
row by row; the factory keeps a one-line re-export at each old path so
existing imports keep working.

``__version__`` is whatever distribution metadata ``importlib.metadata`` can
see for ``vcf-cf-tooling-core``: the wheel's version (from a ``core-vX.Y.Z``
tag, or ``0.0.1.devN+g<sha>`` on an untagged working tree, or ``0.0.0`` from
a git-archive export with no ``.git``). Note that a ``python -m build`` run
leaves ``src/vcf_cf_tooling_core.egg-info/`` behind (gitignored), and with
that residue on ``PYTHONPATH=src`` the tree reports the last built version
too. Only when no metadata is visible at all does it report ``0.0.0+src``.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _dist_version

try:
    __version__ = _dist_version("vcf-cf-tooling-core")
except PackageNotFoundError:  # no wheel installed and no egg-info residue under src/
    __version__ = "0.0.0+src"

__all__ = ["__version__"]
