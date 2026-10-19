"""Minimum VCF Operations version per dashboard widget type (issue #199).

A dashboard carrying a widget type the target Ops build does not know is
not skipped widget by widget: on 9.0.2 (Build 25137845) ``WidgetType.fromKey``
returns null, ``ImportExportManager.importDashboard`` then tries to log a skip
message with ``getString("Title")`` / ``getString("Type")`` (capital letters
the dashboard JSON does not carry), the ``JSONException`` aborts the WHOLE
dashboard, and on the pak path the ``dashboards.properties`` Summary binding
never runs.  Install still reports FINISHED.  Evidence:
``knowledge/context/api-surface/summary_dashboard_pak_binding.md`` §"Unknown
widget type aborts the import" and §"9.0.2 WidgetType keys (complete list)",
``knowledge/context/investigations/2026-10-12-compliance-pak-summary-binding.md``,
lesson ``knowledge/lessons/unknown-widget-type-aborts-pak-dashboard-import.md``.

The table is keyed by the factory YAML ``type`` (``AlertVolume`` renders as
wire type ``IntSummaryAlertVolume``).  A value of ``None`` means no known
floor: the wire type is in the 9.0.2 enum, the oldest build whose enum has
been read, and nothing older has been checked.  A tuple is the lowest build
the type has been seen importing; ``Section`` is absent from the 9.0.2 enum
and proven on 9.1.1 (devel, 2026-08) and 9.2 (qa); 9.1.0 has not been
checked, so the floor is the lowest proven build, not necessarily the exact
one.

Not gated: ``view_details`` is a widget config key (``config.viewDetails``),
not a widget type, so ``WidgetType.fromKey`` never sees it; it is proven on
9.1.1 and 9.2 only, and 9.0.x import behaviour for it is unverified.

This module is pure (no I/O); ``Dashboard.validate()`` calls it.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

OpsVersion = Tuple[int, ...]

#: Oldest VCF Ops build whose WidgetType enum has been read.
OLDEST_CHECKED_OPS_VERSION: OpsVersion = (9, 0, 2)

#: Factory widget type (YAML ``type``) -> lowest VCF Ops version known to
#: import it, or None when no floor is known (present on 9.0.2).
WIDGET_TYPE_MIN_OPS_VERSION: Dict[str, Optional[OpsVersion]] = {
    "ResourceList": None,
    "View": None,
    "TextDisplay": None,
    "Scoreboard": None,
    "MetricChart": None,
    "HealthChart": None,
    "ParetoAnalysis": None,
    "AlertList": None,
    "ProblemAlertsList": None,
    "Heatmap": None,
    "PropertyList": None,
    "ResourceRelationshipAdvanced": None,
    "AlertVolume": None,  # wire IntSummaryAlertVolume, in the 9.0.2 enum
    "Section": (9, 1, 1),  # absent from the 9.0.2 enum; 9.1.0 unchecked
}


def parse_ops_version(value) -> OpsVersion:
    """Parse ``"9.0.2"`` / ``"9.0.2.0"`` / ``(9, 0, 2)`` into an int tuple.

    Raises ValueError on anything that is not dot-separated integers.
    """
    if isinstance(value, tuple):
        parts = [int(p) for p in value]
    else:
        s = str(value).strip()
        if not s or not all(p.isdigit() for p in s.split(".")):
            raise ValueError(f"not a VCF Ops version: {value!r}")
        parts = [int(p) for p in s.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def format_ops_version(v: OpsVersion) -> str:
    return ".".join(str(p) for p in v)


def widget_version_problems(
    widgets: Iterable[Tuple[str, str]],
    target_version=None,
) -> List[str]:
    """Return one message per widget type that may not import on the target.

    *widgets* is ``(local_id, type)`` pairs.  With *target_version* set,
    a type is reported when its floor is above the target.  With no target
    (no bundle, release or adapter field declares one today), every type
    that has a floor is reported, because the dashboard cannot install on
    builds below that floor and nothing says those builds are out of scope.
    """
    target = parse_ops_version(target_version) if target_version is not None else None
    by_type: Dict[str, List[str]] = {}
    for local_id, wtype in widgets:
        floor = WIDGET_TYPE_MIN_OPS_VERSION.get(wtype)
        if floor is None:
            continue
        if target is not None and target >= parse_ops_version(floor):
            continue
        by_type.setdefault(wtype, []).append(local_id)

    problems: List[str] = []
    for wtype, ids in by_type.items():
        floor_s = format_ops_version(WIDGET_TYPE_MIN_OPS_VERSION[wtype])
        scope = (
            f"the declared target VCF Ops {format_ops_version(target)}"
            if target is not None
            else "any VCF Ops build below it (no target version is declared, "
                 "so this cannot be gated)"
        )
        problems.append(
            f"widget type {wtype} (widget(s) {', '.join(ids)}) needs VCF Ops "
            f"{floor_s} or later; on {scope} the importer aborts the WHOLE "
            f"dashboard and any Summary binding on it, while install still "
            f"reports success (issue #199)."
        )
    return problems
