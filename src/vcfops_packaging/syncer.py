"""Bundle sync orchestrator for vcfops_packaging.

This module drives the sync/uninstall workflow:
1. Load the bundle manifest.
2. Authenticate once (single session from env vars).
3. Discover available handlers (one pass, cached for the run).
4. For each content type in sync_order (or reverse for uninstall):
   - If the bundle has YAML paths for that type AND a handler is available:
     call handler.sync() / handler.delete().
   - If no handler is available for a type that has entries: WARN and skip.

Exit code contract:
    0  — all items OK (or no items to process)
    1  — fatal (auth failure, bundle load error)
    2  — partial failure (at least one item failed; others may have succeeded)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from .handler import ContentHandler, DeleteResult, ItemResult, SyncResult, discover_handlers
from .loader import Bundle, BundleValidationError, load_bundle, load_all_bundles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_ok(msg: str) -> None:
    print(f"  OK    {msg}")


def _print_warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def _print_fail(msg: str) -> None:
    print(f"  FAIL  {msg}", file=sys.stderr)


def _get_yaml_paths_for_type(bundle: Bundle, content_type: str) -> List[str]:
    """Return the list of absolute YAML path strings for a content type."""
    mapping = {
        "supermetrics": [str(p.source_path) for p in bundle.supermetrics
                         if p.source_path],
        "customgroups": [str(p.source_path) for p in bundle.customgroups
                         if p.source_path],
        "views": [str(p.source_path) for p in bundle.views
                  if p.source_path],
        "dashboards": [str(p.source_path) for p in bundle.dashboards
                       if p.source_path],
        "symptoms": [str(p) for p in bundle.symptom_paths],
        "alerts": [str(p) for p in bundle.alert_paths],
    }
    return mapping.get(content_type, [])


def _get_names_for_type(bundle: Bundle, content_type: str) -> List[str]:
    """Return display names for all content items of a type in the bundle."""
    mapping = {
        "supermetrics": [sm.name for sm in bundle.supermetrics],
        "customgroups": [cg.name for cg in bundle.customgroups],
        "views": [v.name for v in bundle.views],
        "dashboards": [d.name for d in bundle.dashboards],
        # symptoms/alerts: names not available without the package loader;
        # the handler is responsible for resolving them from the YAML files.
        "symptoms": [],
        "alerts": [],
    }
    return mapping.get(content_type, [])


def _check_cross_bundle_sharing(
    bundle: Bundle,
    content_type: str,
    all_bundles: List[Bundle],
) -> List[str]:
    """Return YAML path strings that are shared with other sync-enabled bundles.

    Used during uninstall to warn before deleting content referenced in
    multiple bundles.  Only checks other bundles where sync_enabled=True.
    """
    our_paths = set(_get_yaml_paths_for_type(bundle, content_type))
    if not our_paths:
        return []
    shared: List[str] = []
    for other in all_bundles:
        if other is bundle:
            continue
        if not other.sync_enabled:
            continue
        other_paths = set(_get_yaml_paths_for_type(other, content_type))
        shared.extend(str(p) for p in our_paths & other_paths)
    return shared


def _authenticate():
    """Authenticate using env vars and return a VCFOpsClient.

    Raises SystemExit(1) on failure.
    """
    try:
        from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError
        client = VCFOpsClient.from_env()
        client.authenticate()
        return client
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: authentication failed: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Sync one bundle
# ---------------------------------------------------------------------------

def sync_bundle(
    bundle_path: str | Path,
    handlers: Optional[List[ContentHandler]] = None,
    session=None,
) -> int:
    """Sync a single bundle.

    Args:
        bundle_path: Path to a bundles/*.yaml manifest.
        handlers: Pre-discovered handlers list (or None to discover now).
        session: Pre-authenticated VCFOpsClient (or None to authenticate now).

    Returns:
        0 on full success, 2 on partial failure, 1 on fatal.
    """
    try:
        bundle = load_bundle(bundle_path)
    except BundleValidationError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    if handlers is None:
        handlers = discover_handlers()

    if session is None:
        session = _authenticate()

    handlers_by_type = {h.content_type: h for h in handlers}

    print(f"\nSyncing bundle: {bundle.name}")
    if bundle.description:
        first_line = bundle.description.splitlines()[0]
        print(f"  {first_line}")

    any_failure = False

    for handler in handlers:
        content_type = handler.content_type
        yaml_paths = _get_yaml_paths_for_type(bundle, content_type)
        if not yaml_paths:
            continue  # this bundle has no content of this type

        print(f"\n  [{content_type}] syncing {len(yaml_paths)} item(s)...")
        try:
            result = handler.sync(yaml_paths, session)
        except Exception as exc:  # noqa: BLE001
            _print_fail(f"{content_type}: unexpected error: {exc}")
            any_failure = True
            continue

        for item in result.items:
            if item.status == "ok":
                _print_ok(item.name)
            elif item.status in ("skipped", "warn"):
                msg = f": {item.message}" if item.message else ""
                _print_warn(f"{item.name}{msg}")
            else:
                msg = f": {item.message}" if item.message else ""
                _print_fail(f"{item.name}{msg}")
                any_failure = True

    # Warn about content types the bundle has entries for but no handler covers
    all_known_types = {h.content_type for h in handlers}
    for content_type in ("supermetrics", "customgroups", "views", "dashboards",
                         "symptoms", "alerts"):
        if content_type in all_known_types:
            continue
        yaml_paths = _get_yaml_paths_for_type(bundle, content_type)
        if yaml_paths:
            _print_warn(
                f"no handler for '{content_type}' ({len(yaml_paths)} file(s) skipped)"
            )

    return 2 if any_failure else 0


# ---------------------------------------------------------------------------
# Sync all bundles
# ---------------------------------------------------------------------------

def sync_all_bundles(bundles_dir: str | Path = "bundles") -> int:
    """Sync all bundles in a directory where sync_enabled=True.

    Authenticates once and reuses the session across all bundles.

    Returns:
        0 on full success, 2 on any partial failures, 1 on fatal.
    """
    try:
        bundles = load_all_bundles(bundles_dir)
    except BundleValidationError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    active = [b for b in bundles if b.sync_enabled]
    skipped = [b for b in bundles if not b.sync_enabled]

    if not active:
        print("No bundles to sync (all have sync: false or directory is empty).")
        return 0

    print(f"Found {len(active)} bundle(s) to sync"
          + (f", {len(skipped)} skipped (sync: false)" if skipped else "") + ".")
    for b in skipped:
        print(f"  SKIP  {b.name} (sync: false)")

    handlers = discover_handlers()
    session = _authenticate()

    overall_rc = 0
    for bundle in active:
        rc = sync_bundle(bundle.source_path, handlers=handlers, session=session)
        if rc > overall_rc:
            overall_rc = rc

    return overall_rc


# ---------------------------------------------------------------------------
# Uninstall one bundle
# ---------------------------------------------------------------------------

def uninstall_bundle(
    bundle_path: str | Path,
    force: bool = False,
    handlers: Optional[List[ContentHandler]] = None,
    session=None,
    all_bundles: Optional[List[Bundle]] = None,
) -> int:
    """Uninstall a single bundle (reverse sync_order).

    Args:
        bundle_path: Path to a bundles/*.yaml manifest.
        force: When True, skip cross-bundle sharing check and pass force=True
               to each handler's delete().
        handlers: Pre-discovered handlers (or None to discover now).
        session: Pre-authenticated VCFOpsClient (or None to authenticate now).
        all_bundles: All known bundles for cross-bundle sharing check.
            When None and force=False, sharing check is skipped.

    Returns:
        0 on full success, 2 on partial failure, 1 on fatal.
    """
    try:
        bundle = load_bundle(bundle_path)
    except BundleValidationError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    if handlers is None:
        handlers = discover_handlers()

    if session is None:
        session = _authenticate()

    # Reverse sync order for uninstall
    handlers_in_unsync_order = sorted(handlers, key=lambda h: h.sync_order, reverse=True)

    print(f"\nUninstalling bundle: {bundle.name}")
    if force:
        print("  (--force: skipping cross-bundle sharing checks)")

    # Print what will be removed
    for content_type in ("alerts", "symptoms", "dashboards", "views",
                         "customgroups", "supermetrics"):
        names = _get_names_for_type(bundle, content_type)
        if names:
            print(f"  {content_type}: {', '.join(names)}")

    any_failure = False

    for handler in handlers_in_unsync_order:
        content_type = handler.content_type
        yaml_paths = _get_yaml_paths_for_type(bundle, content_type)
        if not yaml_paths:
            continue

        # Cross-bundle sharing check (skip if --force or no all_bundles provided)
        if not force and all_bundles:
            shared = _check_cross_bundle_sharing(bundle, content_type, all_bundles)
            if shared:
                _print_warn(
                    f"{content_type}: {len(shared)} file(s) shared with other "
                    f"sync-enabled bundle(s) — skipping deletion. "
                    f"Use --force to override."
                )
                continue

        # For symptoms/alerts the handler resolves names from the YAML paths.
        # For the four core types we can pass display names instead.
        names = _get_names_for_type(bundle, content_type)
        if not names:
            # For types where we can't resolve names (symptoms/alerts without
            # their packages), pass yaml_paths as "names" — the handler
            # is responsible for resolving.
            names = yaml_paths

        print(f"\n  [{content_type}] deleting {len(names)} item(s)...")
        try:
            result = handler.delete(names, session, force=force)
        except Exception as exc:  # noqa: BLE001
            _print_fail(f"{content_type}: unexpected error: {exc}")
            any_failure = True
            continue

        for item in result.items:
            if item.status == "ok":
                _print_ok(item.name)
            elif item.status in ("skipped", "warn"):
                msg = f": {item.message}" if item.message else ""
                _print_warn(f"{item.name}{msg}")
            else:
                msg = f": {item.message}" if item.message else ""
                _print_fail(f"{item.name}{msg}")
                any_failure = True

    return 2 if any_failure else 0
