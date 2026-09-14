"""Factory entry point to provenance (M2 row 3).

``vcfcf_core.common.provenance.provenance_from_path`` classifies a file as
``"factory"`` / ``"<slug>"`` / ``""`` given an explicit repo root. This
wrapper keeps the pre-row-3 signature: when ``repo_root`` is None it walks
up from the file looking for the first ancestor with a ``content/`` or
``third_party/`` child (``_find_repo_root``) and, finding none, returns
``""``. That sniff is a factory-layout assumption and stays here; the
library never guesses a root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from vcfcf_core.common import provenance as _core


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
                   up from ``path``; no detectable root means ``""``.

    Returns:
        ``"factory"`` if the file lives under ``<repo_root>/content/``.
        ``"<slug>"``  if it lives under ``<repo_root>/third_party/<slug>/``.
        ``""``        if the path is outside both trees (test fixture, etc.).
    """
    if not path:
        return ""
    if repo_root is None:
        root = _find_repo_root(Path(path).resolve())
        if root is None:
            return ""
    else:
        root = repo_root
    return _core.provenance_from_path(path, root)


def __getattr__(name: str):
    """Every name this module does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
