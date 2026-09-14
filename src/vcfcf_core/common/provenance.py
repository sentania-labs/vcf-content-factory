"""Provenance of a loaded content file, given the repo root (M2 row 3).

Every content object (SuperMetricDef, ViewDef, Dashboard, CustomGroupDef, ...)
carries a ``provenance`` string that records *where* in a repo layout the
file was loaded from:

  ``"factory"``          lives under ``<root>/content/``
  ``"<project_slug>"``   lives under ``<root>/third_party/<slug>/``
  ``""``                 outside both trees (a test fixture, a tmp_path, a
                         programmatically constructed object)

The empty-string case is the safe fallback: the dependency walker treats it
as "unknown provenance" and does NOT enforce any scope boundary on it.

This module takes the root as a required argument and never guesses one.
The factory's ``vcfcf_common.provenance`` keeps the pre-row-3 signature
(``repo_root=None`` walks up from the file looking for a ``content/`` or
``third_party/`` sibling) and delegates here.

Public API
----------
  provenance_from_path(path, repo_root) -> str
"""
from __future__ import annotations

from pathlib import Path


def provenance_from_path(path: "str | Path", repo_root: "str | Path") -> str:
    """Return the provenance string for a loaded content file.

    Args:
        path:      Absolute or relative path to the loaded YAML file.
        repo_root: The directory whose ``content/`` and ``third_party/``
                   children define the two provenance trees. Required.

    Returns:
        ``"factory"`` if the file lives under ``<repo_root>/content/``.
        ``"<slug>"``  if it lives under ``<repo_root>/third_party/<slug>/``.
        ``""``        if the path is outside both trees (test fixture, etc.).
    """
    if not path:
        return ""
    if repo_root is None or str(repo_root) == "":
        raise TypeError("provenance_from_path: repo_root is required")
    p = Path(path).resolve()
    root = Path(repo_root).resolve()

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

    # Outside both trees: test fixture or explicit path
    return ""
