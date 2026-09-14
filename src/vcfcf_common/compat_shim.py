"""Support for the deprecated ``vcfops_*`` import names.

Milestone M1 of the content-migrator plan renamed every package from
``vcfops_<name>`` to ``vcfcf_<name>``. Callers that still use the old
names (the SDK adapter repos' READMEs document ``python3 -m
vcfops_packaging ...`` and ``python3 -m vcfops_managementpacks ...``;
their CI does not, it runs the published sdk_buildkit) keep working for
one release through thin ``src/vcfops_<name>/`` shim packages that call
:func:`install`. Follow-up to retire the old names: issue #159.

What ``install`` does, once per old package:

1. Emits a single ``DeprecationWarning`` naming the new module.
2. Copies the new package's public attributes into the shim namespace so
   ``import vcfops_x; vcfops_x.thing`` keeps resolving, and forwards the
   new package's module-level ``__getattr__`` / ``__dir__`` when it has
   them (``vcfcf_common`` lazy-loads ``VCFOpsClient`` that way).
3. Registers an alias finder so ``import vcfops_x.sub`` yields the very
   same module object as ``import vcfcf_x.sub`` (no duplicate module
   instances, so isinstance checks and module-level state stay shared).

The shim's own ``__main__.py`` is deliberately not aliased: it prints a
one-line deprecation notice to stderr (the ``DeprecationWarning`` is
hidden by Python's default filters on the ``-m`` path) and forwards to
the new package via ``runpy`` so ``python -m vcfops_x`` otherwise behaves
exactly like ``python -m vcfcf_x``.

Remove this module and the ten shim packages one release after M1 ships.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings
from importlib.machinery import ModuleSpec
from typing import Dict, Optional

# old top-level name -> new top-level name
_ALIASES: Dict[str, str] = {}


class _AliasLoader(importlib.abc.Loader):
    """Loader that hands back an already-imported module object."""

    def __init__(self, target) -> None:
        self._target = target

    def create_module(self, spec):  # noqa: D401
        return self._target

    def exec_module(self, module) -> None:
        return None


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Resolve ``old_pkg.sub`` to the module object behind ``new_pkg.sub``."""

    def find_spec(self, fullname: str, path=None, target=None) -> Optional[ModuleSpec]:
        head, sep, tail = fullname.partition(".")
        if not sep or head not in _ALIASES:
            return None
        if tail == "__main__":
            # Let the shim package's own __main__.py handle `python -m`.
            return None
        new_name = f"{_ALIASES[head]}.{tail}"
        try:
            new_mod = importlib.import_module(new_name)
        except ModuleNotFoundError as exc:
            if exc.name in (new_name, _ALIASES[head]):
                return None
            raise
        return importlib.util.spec_from_loader(fullname, _AliasLoader(new_mod))


_FINDER = _AliasFinder()


def install(old_name: str, new_name: str, namespace: dict) -> None:
    """Wire ``old_name`` (a shim package) to ``new_name`` (the real one)."""
    warnings.warn(
        f"{old_name} is deprecated and will be removed in the next release; "
        f"import {new_name} instead",
        DeprecationWarning,
        stacklevel=3,
    )
    new_mod = importlib.import_module(new_name)
    _ALIASES[old_name] = new_name
    if _FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _FINDER)
    for key, value in vars(new_mod).items():
        if key == "__all__" or not key.startswith("__"):
            namespace[key] = value
    # Module-level __getattr__ / __dir__ (PEP 562) are dunders the loop
    # above skips on purpose; forward them so lazily exposed names such as
    # vcfcf_common.VCFOpsClient resolve through the old name too.
    if hasattr(new_mod, "__getattr__"):
        namespace["__getattr__"] = lambda name: getattr(new_mod, name)
    if hasattr(new_mod, "__dir__"):
        namespace["__dir__"] = lambda: dir(new_mod)
