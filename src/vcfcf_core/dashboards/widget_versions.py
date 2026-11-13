"""Minimum VCF Operations version per dashboard widget type (issue #199).

A dashboard carrying a widget type the target Ops build does not know is
not skipped widget by widget: on 8.18.7 and 9.0.2 ``WidgetType.fromKey``
returns null, ``ImportExportManager.importDashboard`` then tries to log a skip
message with ``getString("Title")`` / ``getString("Type")`` (capital letters
the dashboard JSON does not carry), and the ``JSONException`` aborts the
import call. In a content import (``/api/content/operations/import``) that
call is the owner's whole dashboards batch, so EVERY dashboard in the same
import is lost and the task still reports FINISHED with
``imported + skipped + failed < total``; in a pak install it is the
``content/dashboards/<dir>`` directory, and the ``dashboards.properties``
Summary binding never runs. Nothing reports a failure on either path.
Evidence: ``knowledge/context/investigations/2026-11-13-section-widget-on-8x-and-90.md``,
``knowledge/context/api-surface/summary_dashboard_pak_binding.md`` §"Unknown
widget type aborts the import" and §"9.0.2 WidgetType keys (complete list)",
lesson ``knowledge/lessons/unknown-widget-type-aborts-pak-dashboard-import.md``.

The table is keyed by the factory YAML ``type`` (``AlertVolume`` renders as
wire type ``IntSummaryAlertVolume``).  A value of ``None`` means no known
floor: the wire type is in the 8.18.7 and 9.0.2 enums (the same 47 keys),
8.18.7 being the oldest build whose enum has been read.  A tuple is the lowest build
the type has been seen importing; ``Section`` is absent from the 9.0.2 enum
and proven on 9.1.1 (devel, 2026-08) and 9.2 (qa); 9.1.0 has not been
checked, so the floor is the lowest proven build, not necessarily the exact
one.

Not gated: ``view_details`` is a widget config key (``config.viewDetails``),
not a widget type, so ``WidgetType.fromKey`` never sees it; it is proven on
9.1.1 and 9.2 only, and 9.0.x import behaviour for it is unverified.

This module is pure (no I/O); ``Dashboard.validate()`` calls it, and the
sync paths call ``import_refusal`` with the version they read from the
instance.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

OpsVersion = Tuple[int, ...]

#: Oldest VCF Ops build whose WidgetType enum has been read (8.18.7 and
#: 9.0.2 carry the same 47 keys, 2026-11-13).
OLDEST_CHECKED_OPS_VERSION: OpsVersion = (8, 18, 7)

#: Factory widget type (YAML ``type``) -> lowest VCF Ops version known to
#: import it, or None when no floor is known (present on 8.18.7 and 9.0.2).
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
    "Section": (9, 1, 1),  # absent from the 8.18.7 and 9.0.2 enums; 9.1.0 unchecked
}

#: What a dashboard with a type the target cannot import costs, per install
#: path (2026-11-13 measurement on 8.18.7 and 9.0.2). One sentence, shared by
#: the validate warning, the pak build error and the sync refusal.
IMPORT_LOSS_SENTENCE = (
    "the importer then aborts on that dashboard: a content import (sync, "
    "bundle install) loses EVERY dashboard in the same import, a pak install "
    "every dashboard in the same content/dashboards directory, and the task "
    "still reports FINISHED with nothing failed"
)


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

    *widgets* is ``(local_id, type)`` pairs.  With *target_version* set
    (the Tier 2 pak build passes RULE-019's oldest supported line), a type
    is reported when its floor is above the target.  With no target
    (content bundles declare none), every type that has a floor is
    reported, because the dashboard cannot install on builds below that
    floor and nothing says those builds are out of scope.
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
                 "so this cannot be gated here; sync and bundle install refuse "
                 "an instance below it)"
        )
        problems.append(
            f"widget type {wtype} (widget(s) {', '.join(ids)}) needs VCF Ops "
            f"{floor_s} or later; on {scope} {IMPORT_LOSS_SENTENCE}, and any "
            f"Summary binding on it never runs (issue #199)."
        )
    return problems


def parse_release_name(release_name) -> Optional[OpsVersion]:
    """The product version in a ``GET /api/versions/current`` ``releaseName``.

    ``"VCF Operations 9.0.2.0"`` -> ``(9, 0, 2)``, ``"VMware Aria Operations
    8.18.7"`` -> ``(8, 18, 7)``. The body's ``major`` / ``minor`` are the API
    version (``2.2`` on 9.0.2, ``1.77`` on 8.18.7), not the product, so only
    the name is read. None when no dotted number is in it.
    """
    if not isinstance(release_name, str):
        return None
    found = None
    for token in release_name.split():
        if "." in token and all(p.isdigit() for p in token.split(".")):
            found = token
    return parse_ops_version(found) if found else None


def import_refusal(dashboards, instance_version) -> Optional[str]:
    """Why a content import of ``dashboards`` must not reach this instance.

    *dashboards* is ``(name, [(local_id, type), ...])`` pairs; the caller
    passes every dashboard the import would carry, because the loss is the
    whole batch, not just the dashboards that carry the type.
    *instance_version* is the instance's product version (a tuple or dotted
    string). Returns None when every widget type imports there, else one
    message naming the dashboards and the widgets that need a newer build.
    """
    have = parse_ops_version(instance_version)
    blocked: List[str] = []
    floors: Dict[str, OpsVersion] = {}
    for name, widgets in dashboards:
        bad: List[str] = []
        for local_id, wtype in widgets:
            floor = WIDGET_TYPE_MIN_OPS_VERSION.get(wtype)
            if floor is None or have >= parse_ops_version(floor):
                continue
            floors[wtype] = parse_ops_version(floor)
            bad.append(f"{local_id} ({wtype})")
        if bad:
            blocked.append(f"'{name}' (widget(s) {', '.join(bad)})")
    if not blocked:
        return None
    needs = ", ".join(
        f"{t} needs {format_ops_version(v)} or later" for t, v in sorted(floors.items())
    )
    return (
        f"refused before import: this instance is VCF Operations "
        f"{format_ops_version(have)} and {needs}. Dashboards carrying it: "
        f"{'; '.join(blocked)}. On this build {IMPORT_LOSS_SENTENCE}, so "
        f"the import was not sent. Remove those widgets or install on VCF "
        f"Operations {format_ops_version(max(floors.values()))} or later "
        f"(issue #199)."
    )


# ---------------------------------------------------------------------------
# omit: version floors (2026-11-12 fidelity review, W3)
# ---------------------------------------------------------------------------
#
# A dashboard ``omit:`` entry removes a key the renderer always writes. The
# 9.0.2 importer reads dashboard JSON with strict getters, so a key an older
# build expects and does not find can abort the whole dashboard (lesson
# unknown-widget-type-aborts-pak-dashboard-import.md). Each entry's floor is
# the oldest VCF Operations version whose OWN built-in export shows the key
# absent, read from the 8.18.7, 9.0.2 and 9.1.1 scope-ALL exports (counts:
# dashboard_fidelity_wire_format.md §Omit version floors). ``None``: no
# product export shows it absent (seen only on third-party content of
# unknown target build). A floor proves an export carries the shape, which
# is the evidence the factory has; import on that build is not separately
# tested.

#: The oldest export set the floors were read from.
OLDEST_OMIT_EVIDENCE: OpsVersion = (8, 18, 7)

#: Dashboard-level ``omit:`` entry -> floor.
DASHBOARD_OMIT_MIN_OPS_VERSION: Dict[str, Optional[OpsVersion]] = {
    "temporary": (9, 1, 1),            # on all 163 (8.18.7) and 180 (9.0.2); absent on all 179 (9.1.1)
    "name_path": (8, 18, 7),           # absent on 14 of 163 (8.18.7)
    "folder_in_name": None,            # no export; one third-party dashboard
    "widget_interactions": (9, 1, 1),  # on all 163 and 180; absent on 37 of 179 (9.1.1)
}

#: (widget type, ``omit:`` entry) -> floor.
WIDGET_OMIT_MIN_OPS_VERSION: Dict[Tuple[str, str], Optional[OpsVersion]] = {
    ("AlertList", "alert_definitions"): (8, 18, 7),               # absent on 8 of 14
    ("ResourceRelationshipAdvanced", "pagination_number"): (8, 18, 7),  # 30 of 30
    ("ResourceRelationshipAdvanced", "select_first_row"): (8, 18, 7),   # 29 of 30
    ("Scoreboard", "sub_mode"): (8, 18, 7),                       # 20 of 173
    ("MetricChart", "sub_mode"): (8, 18, 7),                      # 12 of 71
}

#: Scoreboard / MetricChart metric entry ``omit:`` entry -> floor (8.18.7
#: counts over 1,536 entries).
METRIC_OMIT_MIN_OPS_VERSION: Dict[str, Optional[OpsVersion]] = {
    "label": (8, 18, 7),                # 268 entries without label
    "max_value": (8, 18, 7),            # 1,516 without maxValue
    "handle_old_coloring": (8, 18, 7),  # 379 without handleOldColoring
    "unit": (8, 18, 7),                 # 285 without unit / metricUnitId
    "link": (8, 18, 7),                 # 242 without link
}

#: Heatmap tab ``omit:`` entry -> floor (8.18.7 counts over 77 tabs).
HEATMAP_TAB_OMIT_MIN_OPS_VERSION: Dict[str, Optional[OpsVersion]] = {
    "tag_filter": (8, 18, 7),          # 20 tabs without tagFilter
    "group_by_kind_keys": (8, 18, 7),  # 51 without groupBy resourceKind / adapterKind
    "color_min_value": (8, 18, 7),     # 15 without color.minValue
    "custom_filter": (8, 18, 7),       # 27 without customFilter
}


def omit_version_problems(
    entries: Iterable[Tuple[str, str, Optional[OpsVersion]]],
    target_version=None,
) -> List[str]:
    """One message per ``omit:`` entry the target may not import without.

    *entries* is ``(where, entry, floor)``. With *target_version* (the Tier 2
    pak build passes RULE-019's oldest supported line) an entry is reported
    when its floor is above the target or unknown. With no target (content
    bundles declare none) an entry is reported when its floor is above the
    oldest export read (``OLDEST_OMIT_EVIDENCE``) or unknown: below that the
    factory has no evidence either way, and every entry has a floor there.
    """
    target = parse_ops_version(target_version) if target_version is not None else OLDEST_OMIT_EVIDENCE
    problems: List[str] = []
    for where, entry, floor in entries:
        if floor is not None and parse_ops_version(floor) <= target:
            continue
        seen = (
            f"absent only from VCF Operations {format_ops_version(floor)} and later exports"
            if floor is not None else "absent from no product export"
        )
        problems.append(
            f"{where}: omit: {entry} leaves out a key {seen}; whether VCF Operations "
            f"{format_ops_version(target)} imports the dashboard without it is unproven, "
            f"and the 9.0.2 importer aborts the WHOLE dashboard on a key it expects "
            f"(install still reports success)."
        )
    return problems
