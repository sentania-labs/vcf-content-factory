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
sync paths call ``import_check`` with the version they read from the
instance.
"""
from __future__ import annotations

import re
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

#: Factory widget type -> the version below which the type is MEASURED not to
#: import (live, on both install paths). Section: failing on 8.18.7 and 9.0.2
#: (knowledge/context/investigations/2026-11-13-section-widget-on-8x-and-90.md).
#: Between this and ``WIDGET_TYPE_MIN_OPS_VERSION`` nothing is measured (9.1.0
#: for Section): the live paths warn and import there, and the import result
#: check is the backstop. A floored type with no entry here is never refused,
#: only warned on.
WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION: Dict[str, OpsVersion] = {
    "Section": (9, 1, 0),
}

#: What a dashboard with a type the target cannot import costs, per install
#: path (2026-11-13 measurement on 8.18.7 and 9.0.2, one owner per import, as
#: every factory import has). One sentence, shared by the validate warning,
#: the pak build error and the sync refusal.
IMPORT_LOSS_SENTENCE = (
    "the importer then aborts on that dashboard: a content import (sync, "
    "bundle install) loses EVERY dashboard in the same import (measured with "
    "one owner, which every factory import has), a pak install every "
    "dashboard in the same content/dashboards directory, and the task still "
    "reports FINISHED with nothing failed"
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
    """``(9, 1)`` -> ``"9.1.0"``: at least three parts, so a trimmed version
    reads as the product names it."""
    parts = list(v) + [0] * (3 - len(v))
    return ".".join(str(p) for p in parts)


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
            else "a VCF Ops build below it (no target version is declared, "
                 "so this cannot be gated here; sync and bundle install refuse "
                 "an instance measured not to import it and warn on an "
                 "unmeasured one)"
        )
        problems.append(
            f"widget type {wtype} (widget(s) {', '.join(ids)}) is proven to "
            f"import from VCF Ops {floor_s}; on {scope} {IMPORT_LOSS_SENTENCE}, "
            f"and any Summary binding on it never runs (issue #199)."
        )
    return problems


#: The product version in a ``releaseName``: the first dotted ASCII number
#: after ``Operations`` and whitespace, ending at whitespace or the end.
#: install.py and install.ps1 carry the same pattern (``\z`` there).
RELEASE_NAME_VERSION_RE = re.compile(
    r"Operations[ \t\r\n]+([0-9]+(?:\.[0-9]+)+)(?=[ \t\r\n]|\Z)"
)


def parse_release_name(release_name) -> Optional[OpsVersion]:
    """The product version in a ``GET /api/versions/current`` ``releaseName``.

    ``"VCF Operations 9.0.2.0"`` -> ``(9, 0, 2)``, ``"VMware Aria Operations
    8.18.7"`` -> ``(8, 18, 7)``, ``"VCF Operations 9.1.1.0100"`` -> ``(9, 1,
    1, 100)``. Only the name is read: the body's ``major`` / ``minor`` are the
    API version on 8.18.7 and 9.0.2 (``1.77``, ``2.2``) but the product
    version on 9.1 (``9``, ``1``), so only ``releaseName`` is consistent
    across lines. The first dotted number after ``Operations`` wins, so a
    later dotted token cannot be taken for the product. None when there is
    none (never raises).
    """
    if not isinstance(release_name, str):
        return None
    m = RELEASE_NAME_VERSION_RE.search(release_name)
    return parse_ops_version(m.group(1)) if m else None


def import_check(dashboards, instance_version) -> Tuple[Optional[str], Optional[str]]:
    """``(refusal, warning)`` for a content import of ``dashboards`` here.

    *dashboards* is ``(name, [(local_id, type), ...])`` pairs; the caller
    passes every dashboard the import would carry, because the loss is the
    whole batch, not just the dashboards that carry the type.
    *instance_version* is the instance's product version (a tuple or dotted
    string).

    ``refusal`` (the caller must not import) when a widget type is below its
    ``WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION`` (measured failing). Otherwise
    ``warning`` (import, the import result check is the backstop) when a type
    is below its proven floor on a build nobody measured. Both None when
    every type is proven to import there.
    """
    have = parse_ops_version(instance_version)
    refused: List[str] = []
    unverified: List[str] = []
    refused_types: Dict[str, Tuple[OpsVersion, OpsVersion]] = {}
    unverified_types: Dict[str, Tuple[OpsVersion, OpsVersion]] = {}
    for name, widgets in dashboards:
        bad: List[str] = []
        unsure: List[str] = []
        for local_id, wtype in widgets:
            floor = WIDGET_TYPE_MIN_OPS_VERSION.get(wtype)
            if floor is None or have >= parse_ops_version(floor):
                continue
            floor = parse_ops_version(floor)
            below = WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION.get(wtype)
            if below is not None and have < parse_ops_version(below):
                refused_types[wtype] = (parse_ops_version(below), floor)
                bad.append(f"{local_id} ({wtype})")
            else:
                unverified_types[wtype] = (parse_ops_version(below) if below else floor, floor)
                unsure.append(f"{local_id} ({wtype})")
        if bad:
            refused.append(f"'{name}' (widget(s) {', '.join(bad)})")
        if unsure:
            unverified.append(f"'{name}' (widget(s) {', '.join(unsure)})")
    have_s = format_ops_version(have)
    if refused:
        why = ", ".join(
            f"{t} is measured not to import below {format_ops_version(b)} and "
            f"proven to import from {format_ops_version(f)}"
            for t, (b, f) in sorted(refused_types.items())
        )
        top = max(f for _b, f in refused_types.values())
        return (
            f"refused before import: this instance is VCF Operations {have_s}; "
            f"{why}. Dashboards carrying it: {'; '.join(refused)}. On this "
            f"build {IMPORT_LOSS_SENTENCE}, so the import was not sent. Remove "
            f"those widgets or install on VCF Operations "
            f"{format_ops_version(top)} or later (issue #199).",
            None,
        )
    if unverified:
        why = ", ".join(
            f"{t} is proven to import from {format_ops_version(f)} and measured "
            f"not to import below {format_ops_version(b)}"
            for t, (b, f) in sorted(unverified_types.items())
        )
        return (
            None,
            f"this instance is VCF Operations {have_s}, which is unverified: "
            f"{why}. Dashboards carrying it: {'; '.join(unverified)}. Importing "
            f"anyway; if this build cannot import it, {IMPORT_LOSS_SENTENCE}, "
            f"and the import result check reports the loss (issue #199).",
        )
    return None, None


# ---------------------------------------------------------------------------
# section_fallback: the Section-less variant of a dashboard (2026-11-13)
# ---------------------------------------------------------------------------
#
# A dashboard that sets ``section_fallback: omit`` may be rendered without
# its Section widgets where the target cannot import Section. One YAML
# source, two variants: the build or sync picks one from the lowest product
# version its output targets, so when the floor rises the same source
# ships its Sections with no content edit.

#: Allowed values of the dashboard YAML key ``section_fallback``.
SECTION_FALLBACK_VALUES: Tuple[str, ...] = ("omit",)

#: Values of the ``--sections`` override (``build-sdk``, dashboards
#: ``package``). ``auto``: the target decides. ``ship``: keep every Section.
#: ``omit``: leave the Sections out of every dashboard that sets
#: ``section_fallback: omit`` (a dashboard without the key keeps them).
SECTIONS_CHOICES: Tuple[str, ...] = ("auto", "ship", "omit")


def section_ship_floor() -> OpsVersion:
    """The lowest target on which a Section is shipped: Section's PROVEN
    floor, ``WIDGET_TYPE_MIN_OPS_VERSION["Section"]`` (9.1.1), not its
    measured-failing bound (``WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION``, 9.1.0).

    Between the two nothing is measured: 9.1.0 may import Section or may lose
    every dashboard in the import. Omitting there costs the header rows of a
    dashboard whose author declared it complete without them; shipping there
    risks the whole batch. So the conservative constant governs omission, and
    a measurement of 9.1.0 lowers it by editing the one table above.
    """
    return parse_ops_version(WIDGET_TYPE_MIN_OPS_VERSION["Section"])


def _section_floor_sentence() -> str:
    below = WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION.get("Section")
    tail = (f"; measured not to import below {format_ops_version(below)}"
            if below is not None else "")
    return (f"{format_ops_version(section_ship_floor())}, the first VCF Operations "
            f"build proven to import Section{tail}")


def section_omission_reason(
    target_version,
    fallback: Optional[str],
    sections: str = "auto",
    unknown_target: str = "ship",
) -> Optional[str]:
    """Why a dashboard's Section widgets are left out, or None to ship them.

    *fallback* is the dashboard's ``section_fallback`` (None or ``"omit"``).
    *target_version* is the lowest product version the output targets (a
    tuple or dotted string), or None when it is unknown. *sections* is the
    ``--sections`` override. *unknown_target* is what a None target means:
    ``"ship"`` where no target is declared at all (a content bundle, a local
    ``package``; today's output), ``"omit"`` where a target exists but could
    not be read (live sync with the instance version unreadable).

    Only a dashboard with *fallback* set is ever omitted. Decision:

    ================  ==================================  ===========
    sections          target                              result
    ================  ==================================  ===========
    ship              any                                 ship
    omit              any                                 omit
    auto              >= section_ship_floor() (9.1.1)     ship
    auto              below it (8.18.7, 9.0.x, 9.1.0)     omit
    auto              None                                unknown_target
    ================  ==================================  ===========
    """
    if sections not in SECTIONS_CHOICES:
        raise ValueError(f"sections must be one of {', '.join(SECTIONS_CHOICES)}; got {sections!r}")
    if fallback is None or sections == "ship":
        return None
    if sections == "omit":
        return "--sections omit was given"
    if target_version is None:
        if unknown_target == "omit":
            return (f"the target version could not be read, and the Section variant "
                    f"needs VCF Operations {_section_floor_sentence()}")
        return None
    target = parse_ops_version(target_version)
    if target >= section_ship_floor():
        return None
    return (f"the target is VCF Operations {format_ops_version(target)}, below "
            f"{_section_floor_sentence()}")


def section_omitted_note(name: str, count: int, reason: str) -> str:
    """The line every omission prints: dashboard, count, reason."""
    return (f"SECTIONS OMITTED: dashboard {name!r}: {count} Section widget(s) left out "
            f"(section_fallback: omit): {reason}.")


def section_kept_below_floor_note(name: str, count: int, target_version) -> str:
    """The line ``--sections ship`` prints for a target below the floor."""
    return (f"SECTIONS KEPT BELOW FLOOR (--sections ship): dashboard {name!r} keeps "
            f"{count} Section widget(s) although the target is VCF Operations "
            f"{format_ops_version(parse_ops_version(target_version))}, below "
            f"{_section_floor_sentence()}; on such a build {IMPORT_LOSS_SENTENCE}.")


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
