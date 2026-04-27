"""Map release headline source paths to distribution subdirectory names.

Used by the publish orchestrator (Phase 3) and release builder (Phase 2)
to route output zips to the correct subdir in the distribution repo.

Type-to-subdir map (factory-native content)
-------------------------------------------
bundles/foo.yaml          -> "bundles"
dashboards/foo.yaml       -> "dashboards"
views/foo.yaml            -> "views"
supermetrics/foo.yaml     -> "supermetrics"
customgroups/foo.yaml     -> "customgroups"
reports/foo.yaml          -> "reports"
managementpacks/foo.yaml  -> "management-packs"

Third-party routing (factory_native: false on a bundle YAML)
------------------------------------------------------------
A bundle YAML whose ``factory_native: false`` field is set routes under
the ``ThirdPartyContent/`` subtree instead of the top-level subdirs:

  - Exactly 1 dashboard (single-headline-dashboard shape):
      -> "ThirdPartyContent/dashboards"
  - 2+ dashboards or other multi-content shape:
      -> "ThirdPartyContent/bundles"

Pass the loaded bundle YAML data (a dict) as ``bundle_data`` to enable
this routing.  When ``bundle_data`` is None or the source path prefix is
not "bundles", the factory-native routing is used.

Symptoms and alerts are deliberately absent from v1 — they ship inside
bundles only.  If a headline path begins with symptoms/ or alerts/, this
function raises a clear error rather than silently routing incorrectly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


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

# Third-party content subtree root.
_THIRD_PARTY_ROOT = "ThirdPartyContent"


def _third_party_subdir(bundle_data: dict) -> str:
    """Return the ThirdPartyContent sub-path for a third-party bundle.

    Routing rule:
      - Exactly 1 dashboard entry -> "ThirdPartyContent/dashboards"
      - 0 or 2+ dashboards         -> "ThirdPartyContent/bundles"

    Args:
        bundle_data: Loaded YAML data for a bundle manifest.

    Returns:
        A distribution subdir string, e.g. ``"ThirdPartyContent/dashboards"``.
    """
    dashboards = bundle_data.get("dashboards") or []
    if isinstance(dashboards, list) and len(dashboards) == 1:
        return f"{_THIRD_PARTY_ROOT}/dashboards"
    return f"{_THIRD_PARTY_ROOT}/bundles"


def headline_to_dir(
    source_path: str,
    bundle_data: Optional[dict] = None,
) -> str:
    """Return the distribution subdirectory name for a headline source path.

    Args:
        source_path:  A repo-relative path string as written in the release
            manifest's ``artifacts[].source`` field, e.g.
            ``"dashboards/demand_driven_capacity_v2.yaml"``, or for
            convenience a bare prefix string like ``"bundles/dummy.yaml"``.
        bundle_data:  When the source path begins with ``"bundles"``, callers
            may pass the loaded YAML data dict for the bundle manifest.  If
            ``factory_native: false`` is set in that data, the return value
            will be under the ``ThirdPartyContent/`` subtree.  When None
            (the default), factory-native routing is assumed.

    Returns:
        The distribution subdirectory name (e.g. ``"dashboards"`` or
        ``"ThirdPartyContent/dashboards"``).

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

    # Third-party routing: only applies to bundle headlines with
    # factory_native: false.
    if prefix == "bundles" and bundle_data is not None:
        factory_native = bundle_data.get("factory_native", True)
        if factory_native is False:
            return _third_party_subdir(bundle_data)

    return dist_dir
