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
exactly like ``python -m vcfcf_x``. Dotted runs (``python -m
vcfops_x.sub``) go through the alias loader's ``get_code``, which prints
the same notice and executes the real module's code once, as
``__main__``, without importing it under the new name first.

Remove this module and the ten shim packages one release after M1 ships.
"""
from __future__ import annotations

import copy
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
    """Loader that hands back the real module object under an old name.

    Built from the real module's spec (found, not executed), so the finder
    never imports library code just to answer ``find_spec``. Three paths:

    * ``import old_pkg.sub``: ``create_module`` imports the real module
      (once, under its real name) and returns that very object. Python's
      ``_init_module_attrs`` then overwrites the object's ``__spec__`` with
      the alias spec, so ``exec_module`` puts back a copy of the real spec
      (real name, origin, cached, path) whose ``loader`` is this forwarder.
      The real name is what ``importlib.reload`` re-finds, so reload
      re-executes through the real loader; the forwarder is what runpy
      needs when the old dotted name is run in-process after being
      imported, since runpy reads the object's ``__spec__`` and the real
      ``SourceFileLoader`` refuses a name it does not own.
    * ``python -m old_pkg.sub``: runpy calls ``get_code``, which forwards to
      the real loader captured at find time (never the alias, so no
      recursion) and prints the one-line deprecation notice. The module
      body executes exactly once, as ``__main__``.
    * ``get_source`` / ``get_filename`` / ``get_data`` / ``is_package``:
      forwarded to the real loader under the real name; any other loader
      attribute is delegated as-is.

    Known limit: ``importlib.reload`` of the real module re-finds it by its
    real name, so afterwards its ``__spec__`` carries the pure
    ``SourceFileLoader`` again. A later ``runpy.run_module("old_pkg.sub")``
    in that same process then fails loudly with ``ImportError`` (the real
    loader cannot handle the old name). Contrived sequence, loud failure,
    one-release shim: accepted as is.
    """

    def __init__(self, real_spec: ModuleSpec, old_name: str) -> None:
        self._real_spec = real_spec
        self._real_loader = real_spec.loader
        self._new_name = real_spec.name
        self._old_name = old_name
        self._orig_spec: Optional[ModuleSpec] = None

    # -- import path -------------------------------------------------------

    def create_module(self, spec):  # noqa: D401
        module = importlib.import_module(self._new_name)
        # Captured before _init_module_attrs clobbers it with the alias spec.
        self._orig_spec = getattr(module, "__spec__", None)
        return module

    def exec_module(self, module) -> None:
        base = self._orig_spec if self._orig_spec is not None else self._real_spec
        restored = copy.copy(base)
        restored.loader = self
        module.__spec__ = restored

    # -- runpy / introspection path ----------------------------------------

    def get_code(self, fullname: Optional[str] = None):
        if self._real_loader is None or not hasattr(self._real_loader, "get_code"):
            raise ImportError(f"{self._new_name} has no runnable code")
        print(_notice(self._old_name, self._new_name), file=sys.stderr)
        return self._real_loader.get_code(self._new_name)

    def get_source(self, fullname: Optional[str] = None):
        if self._real_loader is None or not hasattr(self._real_loader, "get_source"):
            return None
        return self._real_loader.get_source(self._new_name)

    def get_filename(self, fullname: Optional[str] = None):
        if self._real_loader is None or not hasattr(self._real_loader, "get_filename"):
            raise ImportError(f"{self._new_name} has no file")
        return self._real_loader.get_filename(self._new_name)

    def get_data(self, path):
        return self._real_loader.get_data(path)

    def is_package(self, fullname: Optional[str] = None) -> bool:
        return self._real_spec.submodule_search_locations is not None

    def __getattr__(self, name: str):
        # Anything else (get_resource_reader, ...) goes to the real loader.
        if name.startswith("_") or self._real_loader is None:
            raise AttributeError(name)
        return getattr(self._real_loader, name)


def _notice(old_name: str, new_name: str) -> str:
    """One-line stderr notice for the ``-m`` path; ``-m pkg.sub`` reports ``pkg.sub``."""
    suffix = ".__main__"
    if old_name.endswith(suffix) and new_name.endswith(suffix):
        old_name, new_name = old_name[: -len(suffix)], new_name[: -len(suffix)]
    return f"{old_name} is deprecated, use {new_name}; removed next release"


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Resolve ``old_pkg.sub`` to the module object behind ``new_pkg.sub``."""

    def find_spec(self, fullname: str, path=None, target=None) -> Optional[ModuleSpec]:
        head, sep, tail = fullname.partition(".")
        if not sep or head not in _ALIASES:
            return None
        if tail == "__main__":
            # Let the shim package's own __main__.py handle `python -m old_pkg`.
            return None
        new_name = f"{_ALIASES[head]}.{tail}"
        try:
            # find_spec imports parent packages (the real ones) but never
            # executes the target module itself.
            real_spec = importlib.util.find_spec(new_name)
        except ModuleNotFoundError as exc:
            if exc.name and new_name.startswith(exc.name):
                return None
            raise
        if real_spec is None:
            return None
        spec = importlib.util.spec_from_loader(
            fullname,
            _AliasLoader(real_spec, fullname),
            origin=real_spec.origin,
        )
        # Carry the real file location so a module run as __main__ through
        # the old name sees the same __file__ it would under the new one.
        spec.has_location = bool(real_spec.has_location)
        spec.cached = real_spec.cached
        if real_spec.submodule_search_locations is not None:
            spec.submodule_search_locations = list(real_spec.submodule_search_locations)
        return spec


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
