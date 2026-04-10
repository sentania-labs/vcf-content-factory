"""Content handler interface and discovery for vcfops_packaging sync.

Each vcfops_* package that wants to participate in bundle sync exposes a
module named ``handler.py`` at its package root.  That module must define a
module-level ``HANDLER`` object that is an instance of a class conforming to
the ContentHandler protocol defined here.

Discovery:
    The sync orchestrator scans for importable ``vcfops_*/handler.py`` modules
    by looking for directories on ``sys.path`` whose name starts with
    ``vcfops_`` and contain a ``handler.py`` file.  If a module cannot be
    imported (e.g. the package has a missing dependency), it is skipped with a
    WARN and the sync continues.

Adding a new content type:
    1. Create ``vcfops_<type>/handler.py`` with a ``HANDLER`` instance.
    2. Set ``content_type`` to the bundle YAML key (e.g. ``"symptoms"``).
    3. Set ``sync_order`` to a value that respects the dependency graph (higher
       numbers depend on lower numbers).
    4. No changes needed in this file or in the CLI.

Sync order contract (enforced by the registry, not the handlers):
    1  supermetrics   — no deps
    2  customgroups   — may reference super metrics
    3  views          — reference super metrics
    4  dashboards     — reference views
    5  symptoms       — reference metrics/super metrics
    6  alerts         — reference symptoms

Exit codes produced by sync/delete results:
    All items OK        -> 0
    Some items failed   -> 2
    Fatal (auth, etc.)  -> 1 (raised by the orchestrator before result)
"""
from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ItemResult:
    name: str
    status: str          # "ok", "warn", "skipped", "failed"
    message: str = ""


@dataclass
class SyncResult:
    content_type: str
    items: List[ItemResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.status in ("ok", "skipped", "warn") for r in self.items)

    @property
    def has_failures(self) -> bool:
        return any(r.status == "failed" for r in self.items)


@dataclass
class DeleteResult:
    content_type: str
    items: List[ItemResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.status in ("ok", "skipped", "warn") for r in self.items)

    @property
    def has_failures(self) -> bool:
        return any(r.status == "failed" for r in self.items)


@dataclass
class ValidateResult:
    content_type: str
    items: List[ItemResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.status in ("ok",) for r in self.items)


# ---------------------------------------------------------------------------
# Handler protocol (duck-typed; no ABC needed for our scale)
# ---------------------------------------------------------------------------

class ContentHandler:
    """Base class for content type handlers.

    Subclass this in each ``vcfops_*/handler.py`` and set the class
    attributes.  Override the three methods to implement sync/delete/validate
    for your content type.

    The ``session`` parameter passed to sync/delete is a
    ``vcfops_supermetrics.client.VCFOpsClient`` that has already been
    authenticated.  Custom-group handlers that need a
    ``VCFOpsCustomGroupClient`` should construct one from the same env vars
    (the session object carries the token in its headers, but the two client
    types are not interchangeable today — create a fresh
    VCFOpsCustomGroupClient.from_env() inside the handler instead).
    """

    content_type: str = ""   # bundle YAML key, e.g. "supermetrics"
    sync_order: int = 99     # lower runs first
    unsync_order: int = 0    # set automatically as (100 - sync_order); used for uninstall ordering

    def sync(self, yaml_paths: List[str], session) -> SyncResult:  # noqa: ANN001
        """Install/update content from the given YAML file paths.

        Args:
            yaml_paths: Absolute path strings to YAML source files.
            session: An authenticated VCFOpsClient instance.

        Returns:
            A SyncResult with one ItemResult per content item processed.
        """
        raise NotImplementedError

    def delete(
        self,
        names: List[str],
        session,  # noqa: ANN001
        force: bool = False,
    ) -> DeleteResult:
        """Delete content items by display name.

        Args:
            names: Display names of items to delete.
            session: An authenticated VCFOpsClient instance.
            force: When True, skip dependency checks and delete unconditionally.

        Returns:
            A DeleteResult with one ItemResult per name processed.
        """
        raise NotImplementedError

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        """Validate YAML files without contacting the server.

        Args:
            yaml_paths: Absolute path strings to YAML source files.

        Returns:
            A ValidateResult with one ItemResult per file.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Handler discovery
# ---------------------------------------------------------------------------

def discover_handlers() -> List[ContentHandler]:
    """Discover all available content handlers by scanning for
    ``vcfops_*/handler.py`` modules on sys.path.

    A handler module may expose either:
    - A single ``HANDLER`` object (a ContentHandler instance), or
    - A ``HANDLERS`` list of ContentHandler instances.

    Both forms may coexist in the same module (e.g. vcfops_dashboards exposes
    handlers for both "views" and "dashboards" via HANDLERS).

    Returns handlers sorted by sync_order (ascending).  Modules that cannot
    be imported are skipped with a WARN printed to stderr.
    """
    handlers: List[ContentHandler] = []
    seen_packages: set = set()

    for search_root in sys.path:
        try:
            root = Path(search_root)
            if not root.is_dir():
                continue
        except (TypeError, ValueError):
            continue

        try:
            entries = sorted(root.iterdir())
        except PermissionError:
            continue

        for entry in entries:
            pkg_name = entry.name
            if not pkg_name.startswith("vcfops_") or pkg_name == "vcfops_packaging":
                continue
            if not (entry / "handler.py").exists():
                continue
            if pkg_name in seen_packages:
                continue
            seen_packages.add(pkg_name)

            module_name = f"{pkg_name}.handler"
            try:
                mod = importlib.import_module(module_name)
                # Collect from HANDLERS list first, then fall back to HANDLER
                found: List[ContentHandler] = []
                handlers_list = getattr(mod, "HANDLERS", None)
                if isinstance(handlers_list, list):
                    found.extend(handlers_list)
                single = getattr(mod, "HANDLER", None)
                if single is not None and single not in found:
                    found.append(single)
                if not found:
                    print(
                        f"  WARN  {module_name}: no HANDLER or HANDLERS defined"
                        f" — skipping",
                        file=sys.stderr,
                    )
                    continue
                handlers.extend(found)
            except Exception as exc:
                print(
                    f"  WARN  {module_name}: import failed ({exc}) — skipping",
                    file=sys.stderr,
                )

    handlers.sort(key=lambda h: h.sync_order)
    return handlers
