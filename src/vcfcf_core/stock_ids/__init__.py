"""Stock content id guard (issue #345).

VCF Operations tracks pak content by id: installing a pak overwrites any
object with the same id, and uninstalling the pak deletes every id it
shipped. Content that reuses an id belonging to content shipped with the
product therefore overwrites the stock object on install and deletes it on
uninstall. This package holds the stock-id baseline (ids only, as data) and
the check every build path runs against it.

- ``guard``: the artifact scanner, the baseline loader, the allowlist
  parser and the check. One self-contained module so the sdk-buildkit can
  ship it as a single file beside its baseline.
- ``generate``: builds a baseline from parsed content exports. Pure: the
  factory CLI (``python3 -m vcfcf_packaging stock-id-baseline``) reads the
  exports and writes the file.

Lesson: ``knowledge/lessons/pak-content-must-not-reuse-stock-ids.md``.
"""
from __future__ import annotations

from .guard import (  # noqa: F401
    BASELINE_FILE_NAME,
    CONTENT_TYPES,
    KNOWN_HOLES_POINTER,
    AllowlistEntry,
    Definition,
    GuardResult,
    PathCheck,
    StockBaseline,
    StockIdAllowlistError,
    StockIdBaselineError,
    StockIdHit,
    bundled_definitions,
    check_definitions,
    check_paths,
    coverage_text,
    default_baseline_path,
    guard_failure_text,
    definitions_from_objects,
    find_stock_hits,
    format_hit,
    load_baseline,
    parse_allowlist,
    scan_bytes,
    scan_path,
    standalone_check,
    unchecked_types,
    Unreadable,
    unreadable_failure_text,
)
