"""Provenance helpers for loaded content objects.

Every content object (SuperMetricDef, ViewDef, Dashboard, CustomGroupDef, …)
gets a ``provenance`` string that records *where* in the repo the file was
loaded from:

  ``"factory"``          — lives under ``content/<type>/``
  ``"<project_slug>"``   — lives under ``third_party/<slug>/<type>/``
  ``""``                 — loaded via an explicit path outside both trees
                           (e.g. a test fixture, a tmp_path, or a
                           programmatically constructed object).

The empty-string case is the safe fallback: the walker treats it as "unknown
provenance" and does NOT enforce any scope boundary on it.  This means test
fixtures and programmatically constructed objects continue to work without
needing to carry synthetic provenance.

Public API
----------
  provenance_from_path(path, repo_root=None) -> str

    Derive provenance from a file path.  ``repo_root`` defaults to the
    directory containing the ``content/`` and ``third_party/`` directories.
    When ``repo_root`` is None the function does a best-effort search up the
    directory tree for the first ancestor that contains both ``content/`` and
    ``third_party/`` (or either one), stopping at the filesystem root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def _find_repo_root(start: Path) -> Optional[Path]:
    """Walk up from ``start`` to find the first directory that looks like a
    repo root (contains a ``content/`` or ``third_party/`` child directory).

    Returns None if no such ancestor is found.
    """
    candidate = start if start.is_dir() else start.parent
    seen: set = set()
    while candidate not in seen:
        seen.add(candidate)
        if (candidate / "content").is_dir() or (candidate / "third_party").is_dir():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def provenance_from_path(
    path: "str | Path",
    repo_root: Optional["str | Path"] = None,
) -> str:
    """Return the provenance string for a loaded content file.

    Args:
        path:      Absolute or relative path to the loaded YAML file.
        repo_root: Explicit repo root.  When None, auto-detected by walking
                   up from ``path``.

    Returns:
        ``"factory"`` if the file lives under ``<repo_root>/content/``.
        ``"<slug>"``  if it lives under ``<repo_root>/third_party/<slug>/``.
        ``""``        if the path is outside both trees (test fixture, etc.).
    """
    if not path:
        return ""
    p = Path(path).resolve()

    if repo_root is not None:
        root = Path(repo_root).resolve()
    else:
        root = _find_repo_root(p)
        if root is None:
            return ""

    content_root = (root / "content").resolve()
    third_party_root = (root / "third_party").resolve()

    # --- factory content ---
    try:
        p.relative_to(content_root)
        return "factory"
    except ValueError:
        pass

    # --- third-party content ---
    try:
        rel = p.relative_to(third_party_root)
        # rel.parts[0] is the project slug (first path component under third_party/)
        if rel.parts:
            return rel.parts[0]
    except ValueError:
        pass

    # Outside both trees — test fixture or explicit path
    return ""
