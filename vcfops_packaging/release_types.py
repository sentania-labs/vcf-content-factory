"""Map release headline source paths to distribution subdirectory names.

Used by the publish orchestrator (Phase 3) and release builder (Phase 2)
to route output zips to the correct subdir in the distribution repo.

Type-to-subdir map
------------------
bundles/foo.yaml          -> "bundles"
dashboards/foo.yaml       -> "dashboards"
views/foo.yaml            -> "views"
supermetrics/foo.yaml     -> "supermetrics"
customgroups/foo.yaml     -> "customgroups"
reports/foo.yaml          -> "reports"
managementpacks/foo.yaml  -> "management-packs"

Symptoms and alerts are deliberately absent from v1 — they ship inside
bundles only.  If a headline path begins with symptoms/ or alerts/, this
function raises a clear error rather than silently routing incorrectly.
"""
from __future__ import annotations

from pathlib import Path


# Ordered map: first path component -> distribution subdir name.
_SOURCE_TO_DIST: dict[str, str] = {
    "bundles":        "bundles",
    "dashboards":     "dashboards",
    "views":          "views",
    "supermetrics":   "supermetrics",
    "customgroups":   "customgroups",
    "reports":        "reports",
    "managementpacks": "management-packs",
}

# Types intentionally excluded from discrete release routing in v1.
_UNSUPPORTED_V1 = {"symptoms", "alerts"}


def headline_to_dir(source_path: str) -> str:
    """Return the distribution subdirectory name for a headline source path.

    Args:
        source_path: A repo-relative path string as written in the release
            manifest's ``artifacts[].source`` field, e.g.
            ``"dashboards/demand_driven_capacity_v2.yaml"``.

    Returns:
        The distribution subdirectory name (e.g. ``"dashboards"``).

    Raises:
        ValueError: if the source path prefix is not a supported headline
            type, or if it belongs to a type excluded from v1 routing
            (symptoms, alerts).
    """
    # Normalise to a Path so we can read the first component cleanly.
    parts = Path(source_path).parts
    if not parts:
        raise ValueError(f"source_path is empty: {source_path!r}")

    prefix = parts[0]

    if prefix in _UNSUPPORTED_V1:
        raise ValueError(
            f"source path {source_path!r} begins with {prefix!r}, which is "
            f"not a supported v1 headline type.  Symptoms and alerts ship "
            f"inside bundles only; use a bundle headline instead."
        )

    dist_dir = _SOURCE_TO_DIST.get(prefix)
    if dist_dir is None:
        supported = ", ".join(f"{k!r}" for k in _SOURCE_TO_DIST)
        raise ValueError(
            f"source path {source_path!r} begins with unrecognised prefix "
            f"{prefix!r}.  Supported prefixes: {supported}."
        )

    return dist_dir
