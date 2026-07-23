"""Render in-memory models to the wire formats VCF Operations expects.

View definitions are XML (`content.xml`); dashboards are JSON
(`dashboard/dashboard.json`). Both formats were learned by reverse
engineering an export from a live VCF Ops 9 instance plus reference
content from the AriaOperationsContent and operations_dashboards
GitHub repos.

This module deliberately produces the *minimum viable* shape — only
the fields the importer demonstrably needs for the v1 widget set
(ResourceList + View) and a list-style view definition. Every other
property is omitted, defaulted, or left empty.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from .loader import (
    Dashboard, Interaction, MetricSpec, ViewDef, ViewColumn, ViewTimeWindow, Widget,
    SubjectFilterCondition,
    MetricChartConfig, ScoreboardConfig, TextDisplayConfig,
    HealthChartConfig, ParetoAnalysisConfig,
    AlertListConfig, ProblemAlertsListConfig,
    HeatmapConfig, HeatmapTab, HeatmapColorThreshold,
    PropertyListConfig, ResourceRelationshipAdvancedConfig,
)


# Stable per-adapter-kind prefix used in `resourceKindId` fields inside
# dashboard widget configs. Harvested from reference bundles under
# `reference/references/` — the value is the same on every Ops instance for a
# given adapter. Extend as new adapter kinds get pinned; there is no
# API to derive these at runtime (checked /api/adapterkinds and
# /api/adapterkinds/*/resourcekinds; no numeric id is exposed).
_ADAPTER_KIND_PREFIX = {
    "VMWARE": "002006",
    "Container": "002009",
    "CASAdapter": "002010",
    "NSXTAdapter": "002011",
    "KubernetesAdapter": "002017",
    "VMWARE_INFRA_HEALTH": "002019",
    "VrAdapter": "002009",
}

# When a self-provider View (or ProblemAlertsList) widget is pinned to a leaf
# resource kind — one where no single resource carries the kind name as its
# display name — the importer cannot resolve "entries.resource[name=<kind>]"
# because the resource doesn't exist under that name on the instance.  The
# correct container to pin to is the adapter's world singleton, which always
# exists.  This table maps (adapter_kind, leaf_resource_kind) to the
# (container_adapter_kind, container_resource_kind, container_resource_name)
# that the importer CAN resolve.
#
# Evidence: VCFAutomation dashboard pins Views to "Automation World"; idps-
# planner pins to "vSphere World"; AppOSUCP pins to "Universe".  In every
# confirmed working case the resource entry name matches an actual resource
# display name on the target instance.
#
# Extend this table when new leaf kinds are pinned:
#   key:   (adapter_kind, leaf_resource_kind)
#   value: (container_adapter_kind, container_resource_kind, container_resource_name)
_VIEW_PIN_CONTAINER: dict[tuple[str, str], tuple[str, str, str]] = {
    # VMWARE leaf kinds → vSphere World container
    ("VMWARE", "HostSystem"):        ("VMWARE", "vSphere World", "vSphere World"),
    ("VMWARE", "VirtualMachine"):    ("VMWARE", "vSphere World", "vSphere World"),
    ("VMWARE", "Datastore"):         ("VMWARE", "vSphere World", "vSphere World"),
    ("VMWARE", "ClusterComputeResource"): ("VMWARE", "vSphere World", "vSphere World"),
    ("VMWARE", "Datacenter"):        ("VMWARE", "vSphere World", "vSphere World"),
    # World singletons pass through unchanged (no entry needed — the helper
    # falls back to (adapter_kind, resource_kind, resource_kind) for unknowns)
}

# NOTE on nested config.resource.traversalSpecId (removed enrichment,
# 2026-07-13): an earlier revision of this module carried a
# `_VIEW_PIN_TRAVERSAL_SPEC` table that filled in a known-good traversal
# spec string (e.g. "vSphere Hosts and Clusters-VMWARE-vSphere World") for
# self-provider pinned View/ProblemAlertsList widgets keyed on the
# *container* resource (adapter_kind, resource_kind). That was wrong: a
# traversal spec constrains the VIEW SUBJECT's hierarchy, not just the pin
# container, so container-keyed injection misfires whenever a view's
# subject isn't in the hierarchy the spec describes. Concretely,
# `content/dashboards/vks_core_consumption.yaml` pins a View to VMWARE/
# vSphere World, but the view's subject
# (`content/views/vks_core_consumption_by_vcenter.yaml`) is
# `VMwareAdapter Instance` — not in the "Hosts and Clusters" hierarchy the
# spec traverses — and the checked-in WORKING export of that exact widget
# (`knowledge/context/exports/working_dashboards.json` ~L412-424) carries
# an EMPTY nested `traversalSpecId`. Emitting the spec string there would
# have been a wire-format regression on real, shipped, working content.
#
# Decision: emit `config.resource.traversalSpecId: ""` unconditionally.
# Binding is provided by `selfProvider` + the bound `resource` entry, not
# by this field. Evidence an empty string is itself proven-working (not a
# fallback/downgrade): the vendor's own "ESXi Host Details Dashboard.json"
# ships five pinned View widgets with an empty nested traversalSpecId; our
# own checked-in VKS working export (cited above) does the same; and the
# api-explorer's content-import round-trips succeeded either way. No
# evidence anywhere shows the spec string is REQUIRED for a pin to bind —
# only that one vendor export (Cluster Performance 2.0.json) happens to
# carry one for a widget whose view subject IS in the Hosts-and-Clusters
# hierarchy. If a future visual QA pass shows a specific widget failing to
# scope data without a spec string, add a narrowly-scoped, evidence-backed
# mechanism then (keyed on view subject, not container) — not a blanket
# container-keyed table.
#
# Evidence: knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md


def _resolve_view_pin(
    adapter_kind: str,
    resource_kind: str,
) -> tuple[str, str, str]:
    """Return (container_adapter_kind, container_resource_kind, container_resource_name)
    for a self-provider View/ProblemAlertsList widget pin.

    For leaf kinds that are registered in _VIEW_PIN_CONTAINER the function
    returns the world-singleton container so that the importer can resolve
    "entries.resource[name=<container_resource_name>]" against an actual
    running resource on the target instance.

    For unregistered kinds (typically world singletons like ComplianceWorld,
    Automation World, VRMS World) the resource name equals the kind name, so
    the function falls back to (adapter_kind, resource_kind, resource_kind).
    Those resources exist on every instance where the owning adapter is
    installed.
    """
    container = _VIEW_PIN_CONTAINER.get((adapter_kind, resource_kind))
    if container is not None:
        return container
    # World/singleton convention: the resource's display name equals the kind
    # name (e.g., ComplianceWorld resource is named "ComplianceWorld").
    return (adapter_kind, resource_kind, resource_kind)


def _self_provider_pin_container(
    w: "Widget",
    cfg_adapter_kind: str = "",
    cfg_resource_kind: str = "",
) -> tuple[str, str, str] | None:
    """Resolve the container pin for a self-provider widget.

    Prefers an explicit ``w.pin`` (the generic ``pin:`` YAML block used by
    View/ProblemAlertsList) — an explicit pin is always honored, whatever
    kind it names.

    Falls back to the widget's own declared ``adapter_kind``/
    ``resource_kind`` (e.g. a self-provider HealthChart's
    ``health_chart_config``) ONLY when that kind already resolves to itself
    through ``_resolve_view_pin`` — i.e. it's already a world/singleton
    container (`vSphere World`, `ComplianceWorld`, etc.), not a leaf kind
    that `_resolve_view_pin` would redirect (e.g. VMWARE `HostSystem` →
    `vSphere World`). There is no vendor evidence for silently world-pinning
    a self-provider HealthChart authored on a leaf kind — that redirect is
    only proven for View/ProblemAlertsList widgets carrying an *explicit*
    `pin:` block. Without this gate, a future self-provider HealthChart on a
    leaf kind (any `mode`) would silently become world-pinned with no basis.

    Returns None when no pin applies (not self-provider, no resource kind
    declared, or an implicit leaf-kind fallback that isn't gated) — the
    caller keeps the historic ``resource: []`` shape in that case.
    """
    if w.pin:
        return _resolve_view_pin(w.pin.adapter_kind, w.pin.resource_kind)
    if cfg_adapter_kind and cfg_resource_kind:
        resolved = _resolve_view_pin(cfg_adapter_kind, cfg_resource_kind)
        _, resolved_kind, _ = resolved
        if resolved_kind == cfg_resource_kind:
            return resolved
    return None


# ---------------- View definition (XML) ----------------

def _subject_filter_json(groups: list[list["SubjectFilterCondition"]]) -> str:
    """Render a ViewDef.subject_filter (OR-of-AND groups) to the vendor JSON
    string that goes verbatim into a SubjectType ``filter="..."`` attribute.

    Key order per condition object mirrors the vendor ``VM Network Top
    Talkers`` fixture exactly (``condition``, ``transform``, ``metricKey``,
    ``metricValue``, ``businessHours``, ``filterType``) — see
    SubjectFilterCondition docstring in loader.py for the citation and the
    caveat that vendor key order otherwise varies (not schema-significant).
    """
    def _cond_dict(c: "SubjectFilterCondition") -> dict:
        d: dict = {"condition": c.condition}
        if c.transform is not None:
            d["transform"] = c.transform
        d["metricKey"] = c.metric_key
        d["metricValue"] = {"isStringMetric": c.is_string_metric, "value": c.value}
        if c.business_hours is not None:
            d["businessHours"] = c.business_hours
        d["filterType"] = c.filter_type
        return d

    payload = [[_cond_dict(c) for c in group] for group in groups]
    return json.dumps(payload, separators=(",", ":"))


def _xml_property(name: str, value: str, localization_key: Optional[str] = None) -> str:
    if localization_key:
        return (
            f'<Property localizationKey="{escape(localization_key, {chr(34): "&quot;"})}"'
            f' name="{escape(name, {chr(34): "&quot;"})}"'
            f' value="{escape(value, {chr(34): "&quot;"})}"/>'
        )
    return f'<Property name="{escape(name, {chr(34): "&quot;"})}" value="{escape(value, {chr(34): "&quot;"})}"/>'


# The platform's ViewDef Localization Property `key` attribute is XSD-capped
# at maxLength=64 (`#AnonType_keyPropertyLocaleLocalizationViewDefViewsContent`).
# This helper is dormant for view columns today (displayName carries no
# localizationKey — see the module docstring note near _xml_column below),
# but the twin in vcfops_managementpacks/sdk_builder.py hit a real 69-char
# key that aborted a whole colocated content/reports/ batch. Capped here too
# so this class of bug can't resurface if column localizationKeys are ever
# re-enabled or this helper reused elsewhere. See the 2026-07-10 addendum in
# knowledge/context/investigations/sdk_pak_content_import_gap.md.
_LOCALIZATION_KEY_MAX_LEN = 64


def _cap_localization_key(key: str, max_len: int = _LOCALIZATION_KEY_MAX_LEN) -> str:
    """Deterministically shorten *key* to at most *max_len* chars.

    A blind truncate risks two long attribute keys colliding on the same
    truncated prefix — Java properties would then silently keep only the
    last-written line, dropping a column's localized label. To preserve
    uniqueness, an over-length key is shortened to a prefix of the original
    plus an underscore and an 8-hex-char SHA-1 digest of the *full* original
    key, so two keys sharing a long common prefix still diverge in their
    hash suffix.
    """
    if len(key) <= max_len:
        return key
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    prefix_len = max_len - len(digest) - 1  # -1 for the separating "_"
    return f"{key[:prefix_len]}_{digest}"


def _attribute_to_localization_key(attribute: str) -> str:
    """Convert an attribute key to a Java-properties-compatible localizationKey.

    The localizationKey is used in both the rendered view XML (on the
    displayName Property element) and the content.properties bundle, so they
    must match exactly.

    Removes the 'Super Metric|' prefix, replaces '|' with '_', spaces with '_',
    and strips non-(alphanumeric/hyphen/underscore) characters. The result is
    capped at ``_LOCALIZATION_KEY_MAX_LEN`` chars (platform XSD maxLength=64)
    — see ``_cap_localization_key``.

    Examples:
        "VCF-CF Compliance|score"       → "VCF-CF_Compliance_score"
        "Summary|total_hosts"           → "Summary_total_hosts"
        "Super Metric|sm_abc123"        → "sm_abc123"
    """
    key = attribute
    if key.startswith("Super Metric|"):
        key = key[len("Super Metric|"):]
    key = key.replace("|", "_").replace(" ", "_")
    key = "".join(c for c in key if c.isalnum() or c in "-_")
    return _cap_localization_key(key)


def _xml_buckets_control(view: ViewDef) -> str:
    """Emit the buckets-control XML element for distribution views."""
    from .loader import BucketsConfig
    b = view.buckets or BucketsConfig()
    if b.is_dynamic:
        return (
            '<Control id="buckets-control_id_1" type="buckets-control" visible="false">'
            '<Property name="isDynamic" value="true"/>'
            f'<Property name="dynamicCalcFunction" value="{escape(b.calc_function)}"/>'
            "</Control>"
        )
    else:
        return (
            '<Control id="buckets-control_id_1" type="buckets-control" visible="false">'
            '<Property name="isDynamic" value="false"/>'
            f'<Property name="minValue" value="{b.min_value}"/>'
            f'<Property name="maxValue" value="{b.max_value}"/>'
            f'<Property name="bucketCount" value="{b.count}"/>'
            "</Control>"
        )


def _xml_time_interval_selector(view: ViewDef, control_id: str = "time-interval-selector_id_1") -> str:
    """Emit the time-interval-selector Control.

    When ``view.time_window`` is set the control uses those values.
    Otherwise falls back to the prior default (HOURS/24).

    ``startPeriod``/``endPeriod`` (FB-011): the vendor wire format pairs
    ``advancedTimeMode=true`` with a ``startPeriod``/``endPeriod`` range —
    across the full reference corpus (250+ time-interval-selector controls
    surveyed) the *only* control with ``advancedTimeMode=true`` carries
    ``startPeriod=PREVIOUS``/``endPeriod=NOW`` ("vSphere Cluster HA
    Admission Control status", View - Set 3.xml, ViewDef
    fc64c67a-d5b0-4a03-a10b-767b9b247120). No vendor evidence of
    advancedTimeMode=true without a range, or of a range value other than
    PREVIOUS/NOW. We therefore default start_period/end_period to
    PREVIOUS/NOW whenever advanced_time_mode is true and the author left
    them unset — advanced mode with no defined range is the leading
    suspect for the "View request timed out" bug this control produced
    (knowledge/context/feedback_queue.md FB-011). Authors may still set
    explicit values in time_window.start_period/end_period to override.
    The properties are omitted entirely when advanced_time_mode is false,
    matching every non-advanced vendor control observed.

    The control always sits at the top of the <Controls> block.
    See knowledge/context/wire-formats/view_column_wire_format.md §Per-column transformations.
    """
    if view.time_window is not None:
        tw = view.time_window
        adv = "true" if tw.advanced_time_mode else "false"
        unit = escape(tw.unit)
        count = str(tw.count)
        start_period = tw.start_period
        end_period = tw.end_period
        if tw.advanced_time_mode:
            start_period = start_period or "PREVIOUS"
            end_period = end_period or "NOW"
    else:
        adv = "false"
        unit = "HOURS"
        count = "24"
        start_period = None
        end_period = None
    period_props = ""
    if adv == "true":
        period_props = (
            f'<Property name="startPeriod" value="{escape(start_period)}"/>'
            f'<Property name="endPeriod" value="{escape(end_period)}"/>'
        )
    return (
        f'<Control id="{control_id}" type="time-interval-selector" visible="false">'
        f'<Property name="advancedTimeMode" value="{adv}"/>'
        f'<Property name="unit" value="{unit}"/>'
        f'<Property name="count" value="{count}"/>'
        f'{period_props}'
        f'</Control>'
    )


def _xml_transformations_block(view: ViewDef) -> str:
    """Build the <Property name="transformations"> XML block.

    List views use CURRENT. Trend views use NONE + TREND, and optionally
    FORECAST when forecast_days > 0. Authors may also supply an explicit
    transformations list via the YAML.
    """
    if view.transformations:
        items = "".join(f'<Item value="{t}"/>' for t in view.transformations)
        return f'<Property name="transformations"><List>{items}</List></Property>'
    if view.data_type == "trend":
        # NONE = raw data points; TREND = trend line; FORECAST = projection
        transforms = ["NONE", "TREND"]
        if view.forecast_days and view.forecast_days > 0:
            transforms.append("FORECAST")
        items = "".join(f'<Item value="{t}"/>' for t in transforms)
        return f'<Property name="transformations"><List>{items}</List></Property>'
    # Default: CURRENT (list and distribution views)
    return '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'


def _xml_instanced_group_item(view: ViewDef, col) -> str:
    """Render an instanced-group driver or member column Item.

    Wire format ground truth (RULE-016 read-only vendor reference):
      reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/
        ESXi Host License Information vCommunity.xml:36-222 (Licensing, no driver displayName)
        ESXi Packages.xml:36-146                            (Packages, driver has displayName)
        Windows Services vCommunity.xml:36-188              (Guest OS|Services, driver has displayName)

    Driver Item property order (all three files, identical):
      objectType, attributeKey="Instance Name", rollUpCount="0",
      isInstancedGroup="true", showInstanceName, instanceGroupName,
      keepInstanceSummary, [displayName]
    The License view's driver omits displayName; the other two include it
    ("Instance" / "Service"). Since this loader always has a non-empty
    display_name (required field on every ViewColumn), always emitting it
    matches the two-of-three observed variant and is harmless — VCF Ops
    accepts a displayName on the driver as evidenced by those exports.

    Member Item property order (all three files, identical):
      objectType, attributeKey, isStringAttribute, adapterKind, resourceKind,
      [rollUpType — metric columns only, e.g. "NONE" for Remaining Days;
       property columns (isProperty=true) omit rollUpType entirely],
      rollUpCount="0", [transformExpression], transformations=[CURRENT],
      isProperty, [color bounds], displayName, addTimestampAsColumn="false",
      isShowRelativeTimestamp="false".

    AMBIGUITY: whether rollUpType-omission-for-properties is specific to
    this pak's instanced-group columns or a broader vCommunity-pak-wide
    convention (ESXi Host Details vCommunity.xml:44-76 shows the same
    omission on a *non*-instanced property column) was not resolved here —
    out of scope for this instanced-group capability. Only the
    instanced-group code path below mirrors it; the generic
    _xml_attribute_item() path is untouched.

    Non-CURRENT transformations on member columns (2026-07-10 follow-up,
    Codex P2 on PR #46): a full survey of every isInstancedGroup Item across
    all reference/references/vmbro_* content/reports/*.xml files found
    additional vendor evidence beyond the three files above —
    "View - Set 4.xml" (same vmbro_vcf_operations_vcommunity pak) bundles
    several *other* instanced-group views whose member columns use MAX,
    TRANSFORM_EXPRESSION, and TIMESTAMP:
      "Windows CPU Usage" — cpu:0|Percent.DPC.Time, transform=MAX,
        rollUpType="NONE", plus yellowBound/orangeBound/redBound/
        ascendingRange color bounds (same shape this function already
        supports).
      "Linux Disk Performance" — diskio:dm-0|read.time,
        transform=TRANSFORM_EXPRESSION, transformExpression=
        "(current-first)/60000" emitted as a sibling Property
        **immediately before** the transformations Property (same
        ordering as the generic _xml_attribute_item() path),
        rollUpType="NONE".
      "VM Snapshots List" — diskspace:262|snapshot:snapshot-1|accessTime,
        transform=TIMESTAMP, rollUpType="NONE", no extra sibling
        properties (matches the generic path's TIMESTAMP handling).
    Critically, **every** non-property instanced-group member column found
    in this wider survey — CURRENT, MAX, TRANSFORM_EXPRESSION, and
    TIMESTAMP alike — carries rollUpType="NONE". There is no vendor
    evidence anywhere in the corpus for a non-"NONE" rollUpType on an
    instanced-group member column; the previous "AVG" fallback for
    non-CURRENT/NONE transforms here was an unproven guess (not vendor
    evidence) and is corrected below.

    No vendor example of PERCENTILE or TIME_POINT on an instanced-group
    member column was found anywhere in the surveyed corpus (both DO
    appear on plenty of *non*-instanced columns in the same files, so
    their absence here is not merely "these files don't use that
    transformation" — it's specific to instanced-group columns). Per the
    framework's no-silent-downgrade posture, `ViewDef._validate_column`
    rejects both on instanced_group member columns rather than guessing
    their wire shape.
    """
    ig = col.instanced_group
    props = [_xml_property("objectType", "RESOURCE")]
    if ig.is_driver:
        props.append(_xml_property("attributeKey", "Instance Name"))
        props.append(_xml_property("rollUpCount", "0"))
        props.append(_xml_property("isInstancedGroup", "true"))
        props.append(_xml_property("showInstanceName", "true" if ig.show_instance_name else "false"))
        props.append(_xml_property("instanceGroupName", ig.name))
        props.append(_xml_property("keepInstanceSummary", "true" if ig.keep_instance_summary else "false"))
        props.append(_xml_property("displayName", col.display_name))
        return "<Item><Value>" + "".join(props) + "</Value></Item>"

    # Member column.
    props.append(_xml_property("attributeKey", col.attribute))
    props.append(_xml_property("isStringAttribute", "true" if col.is_string_attribute else "false"))
    # adapterKind/resourceKind are the view's own subject kinds, matching
    # every observed instanced-group member column (all three cited files
    # carry the same adapterKind/resourceKind as their <SubjectType>).
    props.append(_xml_property("adapterKind", view.adapter_kind))
    props.append(_xml_property("resourceKind", view.resource_kind))
    transform = (col.transformation or "CURRENT").upper()
    if not col.is_property:
        # Every non-property instanced-group member column found in the
        # vendor survey — CURRENT, MAX, TRANSFORM_EXPRESSION, TIMESTAMP —
        # carries rollUpType="NONE" (see docstring). No vendor evidence
        # supports a different rollUpType here for any transformation.
        props.append(_xml_property("rollUpType", "NONE"))
    props.append(_xml_property("rollUpCount", "0"))
    # transformExpression is a sibling Property emitted immediately before
    # the transformations block — matches both the generic column path
    # ordering and the vendor's "Linux Disk Performance" instanced example
    # (see docstring). PERCENTILE/TIME_POINT companion properties are not
    # handled here: ViewDef._validate_column rejects those transformations
    # on instanced_group member columns before render is ever reached.
    if transform == "TRANSFORM_EXPRESSION" and col.transform_expression:
        props.append(_xml_property("transformExpression", col.transform_expression))
    props.append(
        f'<Property name="transformations"><List><Item value="{escape(transform)}"/></List></Property>'
    )
    props.append(_xml_property("isProperty", "true" if col.is_property else "false"))

    def _bound_str(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float):
            return str(v)
        return str(v)

    def _is_numeric_bound(v) -> bool:
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return True
        try:
            float(str(v))
            return True
        except (ValueError, TypeError):
            return False

    has_yellow = col.yellow_bound is not None
    has_orange = col.orange_bound is not None
    has_red = col.red_bound is not None
    red_is_string = has_red and not _is_numeric_bound(col.red_bound)
    if has_yellow:
        props.append(_xml_property("yellowBound", _bound_str(col.yellow_bound)))
    if has_orange:
        props.append(_xml_property("orangeBound", _bound_str(col.orange_bound)))
    if has_red:
        props.append(_xml_property("redBound", _bound_str(col.red_bound)))
    if col.ascending_range is not None and not (red_is_string and not has_yellow and not has_orange):
        props.append(_xml_property("ascendingRange", "true" if col.ascending_range else "false"))

    props.append(_xml_property("displayName", col.display_name))
    props += [
        _xml_property("addTimestampAsColumn", "false"),
        _xml_property("isShowRelativeTimestamp", "false"),
    ]
    return "<Item><Value>" + "".join(props) + "</Value></Item>"


def _xml_attribute_item(
    view: ViewDef,
    col,
    idx: int,
    sm_map: dict[str, str] | None = None,
    sm_scope_active: bool = False,
    bundle_context: str | None = None,
) -> str:
    # Instanced-group columns (driver + member) have their own wire shape,
    # distinct from every other column kind rendered below. Handle them
    # first and return early. See InstancedGroupSpec in loader.py for the
    # vendor XML citations this mirrors.
    if getattr(col, "instanced_group", None) is not None:
        return _xml_instanced_group_item(view, col)

    # Super metric columns live in their own namespace and need the
    # "Super Metric|sm_<uuid>" attributeKey form — bare "sm_<uuid>"
    # renders as a blank column in the UI. Reference: exported views
    # from the sentania/AriaOperationsContent VCF License Consumption
    # bundle. Super metric columns also use rollUpType=NONE, not AVG.
    raw = col.attribute
    if raw.startswith('supermetric:"') or raw.startswith("supermetric:'"):
        # Author wrote supermetric:"<name>" — resolve to sm_<uuid> using
        # the SM name map built from supermetrics/ YAML at render time.
        m = re.match(r'''supermetric:["'](.+?)["']$''', raw)
        if m:
            sm_name = m.group(1)
            sm_id = (sm_map or {}).get(sm_name)
            if sm_id:
                attribute_key = f"Super Metric|sm_{sm_id}"
            else:
                if sm_scope_active:
                    ctx = bundle_context or "(unknown bundle)"
                    raise ValueError(
                        f'View "{view.name}" references super metric "{sm_name}" '
                        f"which is not in the bundle scope for {ctx!r}. "
                        f"Either add the SM to the bundle's `supermetrics:` manifest "
                        f"list, or remove the reference from the view."
                    )
                raise ValueError(
                    f'View "{view.name}" column {idx} references super metric '
                    f'"{sm_name}" which could not be resolved to a UUID. '
                    f"Ensure the SM YAML exists in content/supermetrics/ and "
                    f"has a valid id field."
                )
        else:
            raise ValueError(
                f'View "{view.name}" column {idx} has malformed supermetric '
                f'reference: {raw!r}. Expected supermetric:"<name>".'
            )
        roll_up_type = "NONE"
    elif raw.startswith("sm_"):
        attribute_key = f"Super Metric|{raw}"
        roll_up_type = "NONE"
    elif raw.startswith("Super Metric|"):
        attribute_key = raw
        roll_up_type = "NONE"
    else:
        attribute_key = raw
        roll_up_type = "AVG"
    props = [
        _xml_property("objectType", "RESOURCE"),
        _xml_property("attributeKey", attribute_key),
    ]
    if col.unit:
        props.append(_xml_property("preferredUnitId", col.unit))
    props += [
        _xml_property("isStringAttribute", "true" if col.is_string_attribute else "false"),
        _xml_property("adapterKind", view.adapter_kind),
        _xml_property("resourceKind", view.resource_kind),
        _xml_property("rollUpType", roll_up_type),
        _xml_property("rollUpCount", "1"),
    ]
    # Per-column transformation block.
    # Trend views retain the view-level stacked list (NONE/TREND/FORECAST);
    # all other view types get a per-column single-item transformations block.
    if view.data_type == "trend":
        props.append(_xml_transformations_block(view))
    else:
        # Emit per-transformation sibling properties BEFORE the transformations
        # block (matches exported order: knowledge/context/wire-formats/view_column_wire_format.md).
        transform = (col.transformation or "CURRENT").upper()
        if transform == "PERCENTILE" and col.percentile is not None:
            props.append(_xml_property("percentile", str(col.percentile)))
        if transform == "TRANSFORM_EXPRESSION" and col.transform_expression:
            props.append(_xml_property("transformExpression", col.transform_expression))
        if transform == "TIME_POINT":
            # Three required siblings: metricToRelateWith, localizedMetricToRelateWith,
            # operatorToRelateWith. Wire format confirmed by ops-recon 2026-05-27
            # (12 live uses). See knowledge/context/wire-formats/view_column_wire_format.md.
            if col.metric_to_relate_with:
                props.append(_xml_property("metricToRelateWith", col.metric_to_relate_with))
            if col.localized_metric_to_relate_with:
                props.append(_xml_property("localizedMetricToRelateWith", col.localized_metric_to_relate_with))
            if col.operator_to_relate_with:
                props.append(_xml_property("operatorToRelateWith", col.operator_to_relate_with))
        props.append(
            f'<Property name="transformations">'
            f'<List><Item value="{escape(transform)}"/></List>'
            f'</Property>'
        )
    props.append(_xml_property("isProperty", "true" if col.is_property else "false"))
    # Color bound Properties — emitted between isProperty and displayName
    # in order: yellow, orange, red, ascendingRange.
    # See knowledge/context/wire-formats/view_column_wire_format.md §Per-column color thresholds.
    def _bound_str(v) -> str:
        """Coerce a bound value to its wire-format string representation."""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float):
            # Preserve sub-integer notation as observed in real exports (e.g. ".1")
            return str(v)
        return str(v)

    def _is_numeric_bound(v) -> bool:
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return True
        try:
            float(str(v))
            return True
        except (ValueError, TypeError):
            return False

    has_yellow = col.yellow_bound is not None
    has_orange = col.orange_bound is not None
    has_red = col.red_bound is not None
    red_is_string = has_red and not _is_numeric_bound(col.red_bound)

    if has_yellow:
        props.append(_xml_property("yellowBound", _bound_str(col.yellow_bound)))
    if has_orange:
        props.append(_xml_property("orangeBound", _bound_str(col.orange_bound)))
    if has_red:
        props.append(_xml_property("redBound", _bound_str(col.red_bound)))
    # ascendingRange: emit for numeric bounds; suppress for string-only red_bound
    if col.ascending_range is not None and not (red_is_string and not has_yellow and not has_orange):
        props.append(_xml_property("ascendingRange", "true" if col.ascending_range else "false"))

    # displayName is emitted as a plain name/value Property with no
    # localizationKey.  Real VCF Ops exports (brockpeterson_operations_dashboards,
    # AriaOperationsContent — every reference checked) never carry a
    # localizationKey on displayName.  Emitting one caused collision for
    # transformed columns of the same metric (e.g. cpu|demandPct → AVG, MAX,
    # P95 all resolved to "cpu_demandPct"), making them indistinguishable in
    # environments that honour localizationKey.  The factory's content.properties
    # files are empty, so the key served no purpose anyway.
    props.append(_xml_property("displayName", col.display_name))
    props += [
        _xml_property("addTimestampAsColumn", "false"),
        _xml_property("isShowRelativeTimestamp", "false"),
    ]
    # Trend views additionally carry a forecastDays attribute on each metric
    if view.data_type == "trend" and view.forecast_days and view.forecast_days > 0:
        props.append(_xml_property("forecastDays", str(view.forecast_days)))
    return "<Item><Value>" + "".join(props) + "</Value></Item>"


def _render_summary_infos(view: ViewDef) -> str:
    """Render the summaryInfos XML block for a view's summary/totals row."""
    if not view.summary:
        return ""
    indexes = view.summary.column_indexes
    if indexes is None:
        indexes = list(range(len(view.columns)))
    idx_items = "".join(f'<Item value="{i}"/>' for i in indexes)
    return (
        '<Property name="summaryInfos"><List><Item><Value>'
        f'{_xml_property("displayName", view.summary.display_name)}'
        f'{_xml_property("aggregation", view.summary.aggregation)}'
        f'<Property name="attributeIndexes"><List>{idx_items}</List></Property>'
        '</Value></Item></List></Property>'
    )


def _render_view_def_fragment(
    view: ViewDef,
    sm_map: dict[str, str] | None = None,
    sm_scope_active: bool = False,
    bundle_context: str | None = None,
) -> str:
    items = "".join(
        _xml_attribute_item(view, c, i, sm_map, sm_scope_active, bundle_context)
        for i, c in enumerate(view.columns)
    )

    # Shared header elements.
    # localizationKey attributes on <Title> and <Description> match the
    # content.properties bundle keys: view.<uuid>.title and view.<uuid>.desc.
    # Reference: /tmp/vcf_auto/content/reports/VCF90/content.xml.
    # Only emit localizationKey="desc" when the view has a non-empty description.
    # An empty description has no content.properties entry (see
    # _generate_view_content_properties in sdk_builder.py) so emitting the key
    # causes a localization-key-mismatch validation error.  The rendered XML still
    # always carries a <Description> element (required by the importer) — it just
    # has no localizationKey attribute when the description is blank.
    if view.description:
        desc_elem = f'<Description localizationKey="desc">{escape(view.description)}</Description>'
    else:
        desc_elem = f'<Description>{escape(view.description)}</Description>'
    # Optional SubjectType metric/property filter — applied identically to
    # both the "descendant" and "self" SubjectType elements (matches the
    # vendor corpus, which always carries the same filter= value on both).
    if view.subject_filter:
        filter_json = _subject_filter_json(view.subject_filter)
        filter_attr = f' filter="{escape(filter_json, {chr(34): "&quot;"})}"'
    else:
        filter_attr = ""
    header = (
        f'<ViewDef id="{view.id}">'
        f'<Title localizationKey="title">{escape(view.name)}</Title>'
        + desc_elem +
        f'<SubjectType adapterKind="{escape(view.adapter_kind)}"{filter_attr} resourceKind="{escape(view.resource_kind)}" type="descendant"/>'
        f'<SubjectType adapterKind="{escape(view.adapter_kind)}"{filter_attr} resourceKind="{escape(view.resource_kind)}" type="self"/>'
        "<Usage>dashboard</Usage><Usage>report</Usage><Usage>details</Usage><Usage>content</Usage>"
    )

    # Time-interval control appears in all view types.
    # Uses view.time_window when set, otherwise defaults to HOURS/24.
    time_control = _xml_time_interval_selector(view)

    # Attributes-selector is common to all view types
    attr_control = (
        '<Control id="attributes-selector_id_1" type="attributes-selector" visible="false">'
        f'<Property name="attributeInfos"><List>{items}</List></Property>'
        "</Control>"
    )

    if view.data_type == "distribution":
        # Distribution view: buckets-control instead of pagination/summary
        buckets_ctrl = _xml_buckets_control(view)
        metadata_ctrl = (
            '<Control id="metadata_id_1" type="metadata" visible="false">'
            '<Property name="maxPointsCount" value="5000"/>'
            '<Property name="hideObjectNameColumn" value="false"/>'
            '<Property name="listTopResultSize" value="-1"/>'
            '<Property name="includeResourceCreationTime" value="false"/>'
            "</Control>"
        )
        controls = (
            "<Controls>"
            + time_control
            + attr_control
            + buckets_ctrl
            + metadata_ctrl
            + "</Controls>"
        )
        data_provider = '<DataProviders><DataProvider dataType="distribution-view" id="distribution-view_id_1"/></DataProviders>'
        presentation = f'<Presentation type="{escape(view.presentation)}"/>'

    elif view.data_type == "trend":
        # Trend view: pagination-control (same as list), no summary
        pagination_ctrl = (
            '<Control id="pagination-control_id_1" type="pagination-control" visible="true">'
            '<Property name="start" value="0"/>'
            '<Property name="size" value="500"/>'
            "</Control>"
        )
        metadata_ctrl = (
            '<Control id="metadata_id_1" type="metadata" visible="false">'
            '<Property name="maxPointsCount" value="5000"/>'
            '<Property name="hideObjectNameColumn" value="false"/>'
            '<Property name="listTopResultSize" value="-1"/>'
            '<Property name="includeResourceCreationTime" value="false"/>'
            "</Control>"
        )
        controls = (
            "<Controls>"
            + time_control
            + attr_control
            + pagination_ctrl
            + metadata_ctrl
            + "</Controls>"
        )
        data_provider = '<DataProviders><DataProvider dataType="trend-view" id="trend-view_id_1"/></DataProviders>'
        presentation = f'<Presentation type="{escape(view.presentation)}"/>'

    else:
        # List view (default): pagination-control + optional summary row
        summary = _render_summary_infos(view)
        # Re-render attr_control with summary inline (summary belongs inside
        # attributes-selector for list views per the wire format)
        attr_control = (
            '<Control id="attributes-selector_id_1" type="attributes-selector" visible="false">'
            f'<Property name="attributeInfos"><List>{items}</List></Property>'
            f'{summary}'
            "</Control>"
        )
        pagination_ctrl = (
            '<Control id="pagination-control_id_1" type="pagination-control" visible="true">'
            '<Property name="start" value="0"/>'
            '<Property name="size" value="500"/>'
            "</Control>"
        )
        metadata_ctrl = (
            '<Control id="metadata_id_1" type="metadata" visible="false">'
            '<Property name="maxPointsCount" value="5000"/>'
            '<Property name="hideObjectNameColumn" value="false"/>'
            '<Property name="listTopResultSize" value="-1"/>'
            '<Property name="includeResourceCreationTime" value="false"/>'
            "</Control>"
        )
        controls = (
            "<Controls>"
            + time_control
            + attr_control
            + pagination_ctrl
            + metadata_ctrl
            + "</Controls>"
        )
        data_provider = '<DataProviders><DataProvider dataType="list-view" id="list-view_id_1"/></DataProviders>'
        presentation = f'<Presentation type="{escape(view.presentation)}"/>'

    return header + controls + data_provider + presentation + "</ViewDef>"


def render_view_def_fragments(
    views: list[ViewDef],
    sm_scope: Optional[list[Path]] = None,
    bundle_context: Optional[str] = None,
    owning_adapter_kind: Optional[str] = None,
    owning_resource_kind: Optional[str] = None,
) -> str:
    """Render one or more ViewDefs into bare ``<ViewDef>...</ViewDef>``
    fragments (no ``<?xml?>`` prolog, no ``<Content><Views>`` wrapper).

    This is the shared building block behind :func:`render_views_xml`. It
    also lets callers that need to co-bundle ViewDefs inside another
    document's ``<Content>`` element (e.g. ``vcfops_managementpacks``
    embedding a report's referenced views in the same ``<Content>`` as its
    ``<ReportDef>``, matching the vendor TVS pak shape — see
    ``knowledge/context/investigations/sdk_pak_content_import_gap.md``)
    reuse the exact same rendering path as standalone view subdirs, instead
    of hand-rolling a second XML emitter that could drift.

    Args:
        views: ViewDef objects to render.
        sm_scope: When provided, restrict SM name resolution to only the SM
            YAML files in this list (bundle-scoped mode).  Any
            ``supermetric:"<name>"`` reference that cannot be resolved within
            this scope raises ``ValueError`` with a descriptive message naming
            the view, the unresolved reference, and the bundle context.
            When ``None`` (default), the full ``supermetrics/`` directory tree
            is scanned — the existing native-content behaviour.
        bundle_context: Human-readable bundle name used in scoped-mode error
            messages (e.g. ``'"idps-planner" (factory_native=False)'``).
            Ignored when ``sm_scope`` is None.
        owning_adapter_kind: When provided (alongside ``owning_resource_kind``),
            emit an additional ``<SubjectType>`` element on every ViewDef
            binding the view to the pak's owning adapter namespace.  Required
            for the platform's content importer to file the view under the
            owning adapter; without it the importer drops the view silently.
            Spec ref: knowledge/context/cleanroom-spec/spec/18-pak-content-bundle.md §A2.
        owning_resource_kind: The "World" ResourceKind for the owning adapter
            (the type=1 ResourceKind in describe.xml by convention).  Must be
            supplied together with ``owning_adapter_kind``; ignored when
            ``owning_adapter_kind`` is None.

    Returns:
        Concatenated ``<ViewDef>...</ViewDef>`` fragments (no wrapper).

    Raises:
        ValueError: (scoped mode only) when a ``supermetric:"<name>"``
            column references an SM not present in ``sm_scope``.
    """
    sm_map: dict[str, str] = {}
    sm_scope_active = sm_scope is not None

    if sm_scope_active:
        # Scoped mode: load only the SM files declared in the bundle manifest.
        # An empty list is valid — it means the bundle has no SMs, and any SM
        # reference in a view will be caught as an error below.
        try:
            from vcfops_supermetrics.loader import load_file as _sm_load_file
            for sm_path in sm_scope:
                sm = _sm_load_file(sm_path, enforce_framework_prefix=False)
                sm_map[sm.name] = sm.id
        except Exception as exc:
            # Re-raise as ValueError so the build fails with a clear message.
            raise ValueError(
                f"render_view_def_fragments: failed to load scoped SM for "
                f"bundle {bundle_context!r}: {exc}"
            ) from exc
    else:
        # Native (unscoped) mode: scan the full supermetrics/ directory tree.
        try:
            from pathlib import Path as _Path
            from vcfops_supermetrics.loader import load_dir as _sm_load_dir
            for _candidate in (_Path("content/supermetrics"), _Path("supermetrics")):
                if _candidate.is_dir():
                    for sm in _sm_load_dir(_candidate):
                        sm_map[sm.name] = sm.id
                    break
        except Exception:
            pass

    emit_owning_subject = bool(owning_adapter_kind and owning_resource_kind)

    def _fragment_with_owning(v: ViewDef) -> str:
        frag = _render_view_def_fragment(v, sm_map, sm_scope_active, bundle_context)
        if not emit_owning_subject:
            return frag
        # Inject the owning-adapter SubjectType immediately after the existing
        # SubjectType elements (before the first <Usage> tag).
        # Spec A2: every ViewDef must include a <SubjectType> whose adapterKind
        # matches the owning adapter so the importer can file it correctly.
        owning_st = (
            f'<SubjectType adapterKind="{escape(owning_adapter_kind)}"'
            f' resourceKind="{escape(owning_resource_kind)}"'
            f' type="descendant"/>'
        )
        # Insert just before the first <Usage> element.
        usage_pos = frag.find("<Usage>")
        if usage_pos == -1:
            # Fallback: append before closing </ViewDef>
            frag = frag[:-len("</ViewDef>")] + owning_st + "</ViewDef>"
        else:
            frag = frag[:usage_pos] + owning_st + frag[usage_pos:]
        return frag

    return "".join(_fragment_with_owning(v) for v in views)


def render_views_xml(
    views: list[ViewDef],
    sm_scope: Optional[list[Path]] = None,
    bundle_context: Optional[str] = None,
    owning_adapter_kind: Optional[str] = None,
    owning_resource_kind: Optional[str] = None,
) -> str:
    """Render one or more ViewDefs into the single content.xml the
    VCF Ops content importer expects inside views.zip.

    Thin wrapper around :func:`render_view_def_fragments` that adds the
    ``<?xml?>`` prolog and the ``<Content><Views>...</Views></Content>``
    envelope. See that function for the full argument/return docs.
    """
    fragments = render_view_def_fragments(
        views,
        sm_scope=sm_scope,
        bundle_context=bundle_context,
        owning_adapter_kind=owning_adapter_kind,
        owning_resource_kind=owning_resource_kind,
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<Content><Views>{fragments}</Views></Content>"
    )


# ---------------- Dashboard (JSON) ----------------


def _clamp_gridster_floor(coords: dict) -> dict:
    """Normalize an authored ``coords: {x, y, w, h}`` block into a wire-valid
    ``gridsterCoords``.

    The dashboard grid is **1-indexed**: every ``gridsterCoords`` observed
    across the entire known-good corpus (vendor MP exports under
    ``reference/references/`` — over 100 widgets surveyed — plus every
    ``knowledge/context/exports/*.json`` capture) uses ``x >= 1`` and
    ``y >= 1``. None use 0 for either axis.

    DEF-013: an authored ``coords`` block using 0-based x/y (e.g.
    ``{x: 0, y: 0, ...}``, the natural DX default for someone thinking in
    array-index terms) produces a dashboard where the picker/top widget
    renders *below* a widget declared later in y-order — an inverted
    vertical stack relative to the authored layout. 0 is outside the grid's
    valid coordinate space; downstream the UI's placement engine appears to
    treat it as unset/auto rather than "first row", so the widget falls
    back to flow order instead of the declared position. Clamping to the
    grid's 1-indexed floor here fixes the wire output without an author
    having to know this quirk, and without touching any authored YAML.

    Only the floor is clamped (``max(1, x)`` / ``max(1, y)``) — relative
    ordering of already-valid (>=1) coordinates in the same dashboard is
    left untouched, so multi-row layouts that were already 1-indexed are
    unaffected. This is deliberately NOT a reintroduction of the
    `_gridster_coords()` helper deleted in 00d3382 (see
    ``tests/test_renderer_regression_phase16.py`` Test A) — that helper
    unconditionally shifted every x/y by +1 regardless of whether the input
    was already 1-based, corrupting valid layouts. This helper is a no-op
    (`max(1, v) == v`) for every coordinate that was already >= 1, and only
    changes values that are provably out-of-grid (< 1).
    """
    c = dict(coords)
    c["x"] = max(1, c.get("x", 1))
    c["y"] = max(1, c.get("y", 1))
    return c


# Verbatim ExtJS grid-state blob for a ResourceList "Show Columns ->
# Name only" preset (h15 = Name; the sole hidden=b:0 column). This is NOT
# the raw capture from the live dashboard — the raw capture left 5
# columns (h2, h4, h5, h6, h14) with no `hidden` attribute at all, and an
# unflagged column defaults to VISIBLE (empirically confirmed on
# vcf-lab-operations-devel 2026-07-22; an earlier draft of this doc
# wrongly assumed default-hidden). A truly Name-only blob must carry an
# explicit `^hidden=b:1^width=n:100` on every non-Name column — no column
# may rely on an implicit default. This constant is the raw capture with
# that explicit hidden flag patched onto those 5 columns; every other
# byte is byte-identical to the ground-truth capture (see the decode/
# diff in the wire-format doc's §1 CORRECTION).
#
# Captured ground truth, decode grammar, and the empirical default-
# visible correction:
# knowledge/context/api-surface/resourcelist_column_state_wire_format.md
# Column ids are generic (h1..h47, resourceRating) — they do not embed
# any widget/dashboard UUID — so this value is a reusable constant across
# every ResourceList widget. Only the sibling `key` is per-widget. This
# is an internal, unpublished Ops UI (ExtJS) persistence artefact with no
# OpenAPI schema; paste verbatim, do not re-derive the multi-pass
# URL-encoding (see the doc's "Encoding note").
#
# PRINCIPLE: never rely on default-hidden (or any other implicit
# default) for this blob. Every column except the requested-visible set
# must carry an explicit `hidden=b:1` — an unflagged column is not a
# hidden column, it is a visible one.
_RESOURCE_LIST_COLUMN_STATE_NAME_ONLY = (
    "o%2525253Acolumns%2525253Da%2525253Ao%2525253Aid%2525253Ds%2525253Ah1%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah2%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah3%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah4%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah5%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah6%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah7%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah8%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah9%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah10%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah11%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah12%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah13%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah14%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah15%2525255Ehidden%2525253Db%2525253A0%2525255Eo%2525253Aid%2525253Ds%2525253Ah16%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253AresourceRating%2525255Ehidden%2525253Db%2525253A1%2525255Eo%2525253Aid%2525253Ds%2525253Ah18%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah19%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah20%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah21%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah22%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah23%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah24%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah25%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah26%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah27%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah28%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah29%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah30%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah31%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah32%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah33%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah34%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah35%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah36%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah37%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah38%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah39%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah40%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah41%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah42%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah43%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah44%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah45%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah46%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah47%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100"
)


def _resource_list_widget(
    w: Widget, kind_index: dict[tuple[str, str], int], dashboard_id: str = "",
) -> dict:
    kinds = [
        f"resourceKind:id:{kind_index[(rk.adapter_kind, rk.resource_kind)]}_::_"
        for rk in w.resource_kinds
    ]
    widget_json = {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "ResourceList",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": [],
            "refreshContent": {"refreshContent": False},
            "relationshipMode": {"relationshipMode": 0},
            "additionalColumns": [],
            "title": w.title,
            "mode": "all",
            "filterMode": "tagPicker",
            "tagFilter": {
                "path": [f"/source/kind/kind:{k}" for k in kinds],
                "value": {
                    "bus": [], "adapterKind": [], "kind": kinds,
                    "exclaim": False, "healthRange": [], "maintenanceSchedule": [],
                    "adapterInstance": [], "collector": [], "tier": [],
                    "state": [], "tag": [], "day": [], "status": [],
                },
            },
            "depth": 1,
            "customFilter": {"filter": [], "excludedResources": None, "includedResources": None},
            "selectFirstRow": {"selectFirstRow": w.select_first_row},
            "selfProvider": {"selfProvider": False},
        },
        "height": 600,
    }
    if w.column_preset == "name-only":
        widget_json["states"] = [
            {
                "value": _RESOURCE_LIST_COLUMN_STATE_NAME_ONLY,
                "key": f"permResGrid_widget_{dashboard_id}_{w.widget_id}",
            }
        ]
    return widget_json


def _view_widget(w: Widget, view: "ViewDef | str", kind_index: dict[tuple[str, str], int],
                  resource_index: dict[tuple[str, str], int]) -> dict:
    # A self-provider View widget enumerates its own subject set instead
    # of waiting for an incoming interaction. Ops requires the widget to
    # be pinned to a container resource — typically `vSphere World` for
    # VMWARE subjects — whose descendants the view walks.
    #
    # The `resourceKindId` field format is `<6-digit prefix><adapterKey>
    # <resourceKey>`. The 6-digit prefix is **per adapter kind**, not
    # dashboard-local — it's a stable Ops-internal identifier that is
    # the same across every instance and every dashboard. Harvested
    # empirically from the reference bundles (brockpeterson +
    # AriaOperationsContent + tkopton) by grepping every dashboard.json
    # for `resourceKindId` values. A dashboard that emits a wrong
    # prefix (e.g. `000000`) installs cleanly but the widget fails to
    # render at view time with no diagnostic.
    # External view passthrough: when `view` is a raw UUID string (not a bundled
    # ViewDef), the platform resolves it at install time.  Emit the UUID verbatim
    # as viewDefinitionId. `self_provider`+`pin` is honored on this branch too —
    # the vendor's own Cluster Performance 2.0.json export pins its "vSphere
    # Clusters" widget (an external built-in UUID) exactly this way
    # (selfProvider:true + bound vSphere World resource entry); a bare
    # early-return here previously discarded a declared self_provider+pin
    # silently, which is the wire-format delta behind the live
    # "Select the widget source…" symptom on that widget.
    view_def_id = view if isinstance(view, str) else view.id

    if w.self_provider and w.pin:
        # Resolve the pin to a container resource that will exist on the
        # target instance.  For leaf kinds (e.g. VMWARE/HostSystem) the
        # importer cannot resolve "entries.resource[name='HostSystem']"
        # because no resource has that display name.  _resolve_view_pin
        # maps leaf kinds to their world-singleton containers, which always
        # exist on any instance with the owning adapter installed.
        c_adapter, c_kind, c_name = _resolve_view_pin(
            w.pin.adapter_kind, w.pin.resource_kind
        )
        container_key = (c_adapter, c_kind)
        prefix = _ADAPTER_KIND_PREFIX.get(c_adapter)
        if prefix is None:
            raise ValueError(
                f"no known resourceKindId prefix for adapter kind "
                f"{c_adapter!r} — extend _ADAPTER_KIND_PREFIX "
                f"after harvesting from an exported reference dashboard"
            )
        # Widget config.resource.resourceId is 0-indexed, matching the
        # entries.resource[].internalId values (resource:id:0_::_, etc.).
        # The Ext.vcops.chrome.model.Resource-N id is 1-based in exports
        # but Ops reassigns it on import — any positive integer works.
        res_idx = resource_index[container_key]
        # Nested traversalSpecId is unconditionally empty — see the NOTE
        # above `_resolve_view_pin` for why a container-keyed enrichment
        # here was wrong and was removed. Top-level traversalSpecId (below)
        # is always null and refreshContent is always false, matching the
        # vendor bytes (Cluster Performance 2.0.json "vSphere Clusters" and
        # our own checked-in VKS working export agree on both).
        resource = {
            "resourceId": f"resource:id:{res_idx}_::_",
            "traversalSpecId": "",
            "resourceName": c_name,
            "resourceKindId": f"{prefix}{c_adapter}{c_kind}",
            "id": f"Ext.vcops.chrome.model.Resource-{res_idx + 1}",
        }
        self_provider_flag = True
    else:
        resource = None
        self_provider_flag = False
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "View",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": resource,
            # Vendor bytes: top-level traversalSpecId is always null.
            "traversalSpecId": None,
            # Vendor bytes: refreshContent is always false on this widget
            # type, self-provider or not.
            "refreshContent": {"refreshContent": False},
            "isUpdatedView": True,
            "chartViewItems": [],
            "selectFirstRow": {"selectFirstRow": w.select_first_row},
            "selfProvider": {"selfProvider": self_provider_flag},
            "title": w.title,
            "viewDefinitionId": view_def_id,
        },
        "height": 600,
    }


def _render_metric_spec(
    specs: list[MetricSpec],
    kind_index: dict[tuple[str, str], int],
    widget_id: str,
) -> dict:
    """Build the ``metric`` object shared by Scoreboard and MetricChart widgets.

    Each MetricSpec entry is mapped to one ``resourceKindMetrics[]`` entry.
    The ``resourceKindId`` references the kind_index table that is stored in
    ``entries.resourceKind[]`` in the dashboard bundle JSON.

    The ``id`` field within each entry must be unique per widget; we use
    ``extModel<hash>-<seq>`` where <hash> is a short numeric hash of the
    widget_id so that IDs remain stable across renders for the same content.
    """
    rk_metrics = []
    for seq, spec in enumerate(specs, start=1):
        key = (spec.adapter_kind, spec.resource_kind)
        rk_id = f"resourceKind:id:{kind_index[key]}_::_"
        entry: dict = {
            "metricKey": spec.metric_key,
            "metricName": spec.metric_name,
            "isStringMetric": spec.is_string_metric,
            "resourceKindId": rk_id,
            "resourceKindName": spec.resource_kind,
            "colorMethod": spec.color_method,
            "handleOldColoring": False,
            # Stable per-widget, per-sequence ID.
            "id": f"extModel{abs(hash(widget_id)) % 100000}-{seq}",
            "label": spec.label,
            "link": "",
            "maxValue": "",
        }
        if spec.unit_id:
            entry["metricUnitId"] = spec.unit_id
        else:
            entry["metricUnitId"] = None
        if spec.unit:
            entry["unit"] = spec.unit
        else:
            entry["unit"] = None
        if spec.color_method == 0:
            entry["yellowBound"] = spec.yellow_bound
            entry["orangeBound"] = spec.orange_bound
            entry["redBound"] = spec.red_bound
        else:
            entry["yellowBound"] = None
            entry["orangeBound"] = None
            entry["redBound"] = None
        rk_metrics.append(entry)
    return {
        "mode": "resourceKind",
        "resourceMetrics": [],
        "resourceKindMetrics": rk_metrics,
        "subMode": "resourceKindAll",
    }


def _text_display_widget(w: Widget) -> dict:
    """Render a TextDisplay (static HTML) widget."""
    cfg = w.text_display_config
    assert cfg is not None
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "TextDisplay",
        "title": w.title,
        "config": {
            "editorData": cfg.html,
            "locationFile": "",
            "locationUrl": "",
            "refreshInterval": 300,
            "refreshContent": {"refreshContent": False},
            "title": w.title,
            "viewModeHTML": True,
        },
        "height": 600,
    }


def _scoreboard_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
) -> dict:
    """Render a Scoreboard (KPI tiles) widget."""
    cfg = w.scoreboard_config
    assert cfg is not None
    metric_obj = _render_metric_spec(cfg.metrics, kind_index, w.widget_id)
    self_provider_flag = w.self_provider
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "Scoreboard",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "metric": metric_obj,
            "resource": [],
            "refreshContent": {"refreshContent": True},
            "relationshipMode": {"relationshipMode": 0},
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            "selfProvider": {"selfProvider": self_provider_flag},
            "title": w.title,
            "depth": 1,
            "resInteractionMode": None,
            "visualTheme": cfg.visual_theme,
            "mode": {"layoutMode": "fixedView"},
            "showResourceName": {"showResourceName": cfg.show_resource_name},
            "showMetricName": {"showMetricName": cfg.show_metric_name},
            "showMetricUnit": {"showMetricUnit": cfg.show_metric_unit},
            "showDT": {"showDT": False},
            "showSparkline": {"showSparkline": cfg.show_sparkline},
            "periodLength": cfg.period_length,
            "maxCellCount": cfg.max_cell_count,
            "oldMetricValues": True,
            "roundDecimals": cfg.round_decimals,
            "valueSize": cfg.value_size,
            "labelSize": cfg.label_size,
            "boxHeight": cfg.box_height,
            "boxColumns": cfg.box_columns,
        },
        "height": 600,
    }


def _metric_chart_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
) -> dict:
    """Render a MetricChart (time-series line chart) widget.

    MetricChart ``config.relationshipMode`` is a **scalar integer** wrapped in
    the outer object: ``{"relationshipMode": <int>}``.  Allowed values:

    - ``0``  — no traversal (default).
    - ``-1`` — children/descendants (one line per child of the selected parent).
    - ``1``  — parents/ancestors (one line per parent of the selected child).

    Verified against 146 live MetricChart widgets: zero use any array form.
    The array form ``[1, -1, 0]`` is Heatmap/AlertList-only and causes a 500
    on MetricChart.  See knowledge/context/api-surface/widget_types_survey.md §MetricChart.
    """
    cfg = w.metric_chart_config
    assert cfg is not None
    metric_obj = _render_metric_spec(cfg.metrics, kind_index, w.widget_id)
    self_provider_flag = w.self_provider
    relationship_mode_val = {
        "children": -1,
        "parents": 1,
    }.get(w.relationship_mode, 0)
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "MetricChart",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "metric": metric_obj,
            "resource": [],
            "refreshContent": {"refreshContent": True},
            "relationshipMode": {"relationshipMode": relationship_mode_val},
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            "selfProvider": {"selfProvider": self_provider_flag},
            "title": w.title,
            "depth": 1,
            "resInteractionMode": None,
        },
        "height": 600,
    }


def _health_chart_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
    resource_index: dict[tuple[str, str], int],
) -> dict:
    """Render a HealthChart (ranked health-bar) widget.

    Uses a FLAT metric spec — metricKey and resourceKindId are top-level
    config fields, NOT inside a metric.resourceKindMetrics[] array. This
    is the key structural difference from Scoreboard and MetricChart.

    A self-provider HealthChart (``self_provider: true``) must be pinned to
    a container resource the same way a self-provider View is — the vendor
    wire format is ``selfProvider:true`` + ``resource:[{"name","id"}]``
    (NOT the impossible ``selfProvider:true`` + ``resource:[]``, which
    causes the UI to list every resource on the instance instead of just
    the pinned container). The binding is derived from ``w.pin`` if set, else
    from the widget's own declared ``adapter_kind``/``resource_kind`` — see
    ``_self_provider_pin_container``.

    Wire format reference: knowledge/context/api-surface/widget_types_survey.md §HealthChart;
    knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md §HealthChart.
    """
    cfg = w.health_chart_config
    assert cfg is not None
    key = (cfg.adapter_kind, cfg.resource_kind)
    rk_id = f"resourceKind:id:{kind_index[key]}_::_"
    resource_list: list = []
    if w.self_provider:
        container = _self_provider_pin_container(w, cfg.adapter_kind, cfg.resource_kind)
        if container is not None:
            c_adapter, c_kind, c_name = container
            res_idx = resource_index[(c_adapter, c_kind)]
            resource_list = [{"name": c_name, "id": f"resource:id:{res_idx}_::_"}]
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "HealthChart",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": resource_list,
            "refreshContent": {"refreshContent": False},
            "relationshipMode": {"relationshipMode": 0},
            "selfProvider": {"selfProvider": w.self_provider},
            "title": w.title,
            "mode": cfg.mode,
            "filterMode": "tagPicker",
            "tagFilter": None,
            "depth": cfg.depth,
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            # Flat metric spec — these are direct config fields, not nested
            "metricKey": cfg.metric_key,
            "metricName": cfg.metric_name,
            "metricFullName": cfg.metric_full_name or cfg.metric_name,
            "resourceKindId": rk_id,
            "metricUnit": {"metricUnitId": -1, "metricUnitName": "Default Unit"},
            "metricType": {"metricType": "custom"},
            "chartHeight": cfg.chart_height,
            "yellowBound": cfg.yellow_bound,
            "orangeBound": cfg.orange_bound,
            "redBound": cfg.red_bound,
            "sortBy": "metricValue",
            "sortByDir": {"orderByDir": cfg.sort_by_dir},
            "paginationNumber": cfg.pagination_number,
            "showResourceName": {"showResourceName": cfg.show_resource_name},
            "showMetricLabel": {"showMetricLabel": False},
            "metricLabel": "",
            "selectFirstRow": {"selectFirstRow": False},
        },
        "height": 600,
    }


def _pareto_analysis_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
) -> dict:
    """Render a ParetoAnalysis (Top-N bar chart) widget — Shape 1 only.

    Shape 1 covers mode=all and mode=resource. It uses a flat
    ``metric: {metricKey, name}`` field and a ``resourceKind: [{id}]``
    array referencing entries.resourceKind[]. This is structurally
    different from MetricChart's metric.resourceKindMetrics[] pattern.

    Shape 2 (mode=metric, metricOption/tagOption) requires live-instance
    metric-picker interaction and is not supported for static authoring.

    Wire format reference: knowledge/context/api-surface/widget_types_survey.md §ParetoAnalysis.
    """
    cfg = w.pareto_analysis_config
    assert cfg is not None
    key = (cfg.adapter_kind, cfg.resource_kind)
    rk_id = f"resourceKind:id:{kind_index[key]}_::_"
    bars_count = cfg.bottom_n if cfg.bottom_n > 0 else cfg.top_n
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "ParetoAnalysis",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": [],
            "refreshContent": {"refreshContent": True},
            "relationshipMode": {"relationshipMode": [-1, 0]},
            "selfProvider": {"selfProvider": w.self_provider},
            "title": w.title,
            "mode": cfg.mode,
            "filterMode": "tagPicker",
            "tagFilter": None,
            "depth": cfg.depth,
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            "filterOldMetrics": {"filterOldMetrics": False},
            "topOption": cfg.top_option,
            "barsCount": bars_count,
            "roundDecimals": cfg.round_decimals,
            "regenerationTime": cfg.regeneration_time,
            "percentileValue": None,
            "metricName": cfg.metric_name,
            "metricUnit": {"metricUnitId": -1, "metricUnitName": "Auto"},
            "additionalColumns": [],
            # Flat metric spec — {metricKey, name} NOT the array pattern
            "metric": {
                "metricKey": cfg.metric_key,
                "name": cfg.metric_name,
            },
            "resourceKind": [{"id": rk_id}],
        },
        "height": 600,
    }


def _alert_list_widget(w: Widget) -> dict:
    """Render an AlertList (alert grid) widget.

    Typically interaction-driven — receives a resource selection from another
    widget (e.g. ResourceList or View) and shows that resource's alerts.
    Can also be self-provider when self_provider=True is set on the widget.

    The ``type`` field in the config is the alert type codes array and is
    distinct from the top-level widget type field. To avoid naming collision
    the loader stores it as ``alert_types``.

    ``pin_to_world`` mode (cfg.pin_to_world=True):
        Emits selfProvider:false + resource:[{resourceId:"resource:id:0_::_",
        resourceName:"vSphere World"}].  Required when the widget has a
        definition pin (alertDefinitions filter) AND needs to query the full
        fleet without an interaction-driven resource binding.  The
        selfProvider:true + resource:[] combination silently issues zero
        backend queries in this scenario (no heatMap.action call observed in
        the access log).  Corpus reference: sdwan ProblemAlertsList widgets
        use the same resource shape; adapted for AlertList per investigation
        knowledge/context/investigations/2026-05-29-compliance-dashboard-render-failures.md.

    Wire format reference: knowledge/context/api-surface/widget_types_survey.md §AlertList.
    """
    cfg = w.alert_list_config
    assert cfg is not None

    if cfg.pin_to_world:
        # World-pinned mode: selfProvider:false, resource bound to vSphere World.
        # This triggers real backend queries; selfProvider:true + resource:[] does not.
        self_provider_obj = {"selfProvider": False}
        resource_obj: list = [{"resourceId": "resource:id:0_::_", "resourceName": "vSphere World"}]
    else:
        self_provider_obj = {"selfProvider": w.self_provider}
        resource_obj = []

    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "AlertList",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": resource_obj,
            "refreshContent": {"refreshContent": False},
            "relationshipMode": {"relationshipMode": [-1, 0]},
            "selfProvider": self_provider_obj,
            "title": w.title,
            "mode": cfg.mode,
            "filterMode": "tagPicker",
            "tagFilter": None,
            "depth": cfg.depth,
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            "criticalityLevel": cfg.criticality,
            "type": cfg.alert_types,
            "status": cfg.status,
            "state": cfg.state,
            "alertImpact": cfg.alert_impact,
            "alertAction": cfg.alert_action,
            "alertDefinitions": [{"id": d} for d in cfg.alert_definitions],
        },
        "height": 600,
    }


def _problem_alerts_list_widget(
    w: Widget,
    resource_index: dict[tuple[str, str], int],
) -> dict:
    """Render a ProblemAlertsList (top problem alerts badge summary) widget.

    Usually self-provider, pinned to a container resource (e.g. vSphere World)
    whose descendants Ops evaluates for badge impact. Non-self-provider mode
    is interaction-driven: resource=null and selfProvider=false.

    Wire format reference: knowledge/context/api-surface/widget_types_survey.md §ProblemAlertsList.
    """
    cfg = w.problems_alerts_list_config
    assert cfg is not None

    if w.self_provider and w.pin:
        # Use the resolved container resource (same pattern as _view_widget).
        # Leaf-kind pins (e.g. VMWARE/HostSystem) must redirect to the world
        # singleton so the importer can find the resource by name.
        c_adapter, c_kind, c_name = _resolve_view_pin(
            w.pin.adapter_kind, w.pin.resource_kind
        )
        container_key = (c_adapter, c_kind)
        res_idx = resource_index[container_key]
        resource_obj = {
            "resourceId": f"resource:id:{res_idx}_::_",
            "resourceName": c_name,
        }
        self_provider_flag = True
        refresh_content = True
    else:
        resource_obj = None
        self_provider_flag = False
        refresh_content = True

    config: dict = {
        "refreshInterval": 300,
        "resource": resource_obj,
        "refreshContent": {"refreshContent": refresh_content},
        "selfProvider": {"selfProvider": self_provider_flag},
        "title": w.title,
        "impactedBadge": cfg.impacted_badge,
        "triggeredObject": {"triggeredObject": cfg.triggered_object},
    }
    if cfg.top_issues_limit > 0:
        config["topIssuesDisplayLimit"] = cfg.top_issues_limit

    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "ProblemAlertsList",
        "title": w.title,
        "config": config,
        "height": 600,
    }


def _heatmap_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
) -> dict:
    """Render a Heatmap (treemap) widget.

    Structural notes from wire format analysis (knowledge/context/api-surface/widget_types_survey.md):

    1. ``configs[]`` holds one entry per tab. Each tab defines a subject
       resource kind (``resourceKind``), a colorBy metric, an optional sizeBy
       metric (null key = uniform sizing), and a groupBy parent resource kind.

    2. ``configs[].resourceKind`` uses ``resourceKind:id:N_::_`` referencing
       the shared ``entries.resourceKind[]`` table (same kind_index as other
       widgets). The subject kind and the groupBy kind each get their own slot.

    3. ``groupBy.id`` format is ``004null<6-digit-prefix><adapterKind><resourceKind>``.
       The ``004null`` prefix is fixed. The 6-digit numeric prefix is the same
       per-adapter-kind constant used in other widget types (see
       ``_ADAPTER_KIND_PREFIX``). Example: ``004null002006VMWAREClusterComputeResource``.

    4. ``groupBy.typeId`` uses ``resourceKind:id:N_::_`` and MUST appear in
       ``entries.resourceKind[]`` — the kind_index pass adds it automatically.

    5. When ``group_by_kind`` is empty, ``groupBy`` is emitted as a
       **self-grouping** block using the subject resource kind.  An empty
       ``{}`` causes ``HeatMapAction.initParam`` to throw JSONException
       because it calls ``groupBy.getString("type")`` unconditionally.
       See knowledge/lessons/heatmap-empty-groupby-crashes-renderer.md.

    6. ``value`` (selected tab index) is always 0; authors control default
       tab by ordering configs[].

    7. ``relationshipMode`` uses the array form ``[1, -1, 0]`` (observed in
       65/70 live Heatmap instances; consistent with AlertList and ParetoAnalysis).

    Wire format reference: knowledge/context/api-surface/widget_types_survey.md §Heatmap.
    """
    cfg = w.heatmap_config
    assert cfg is not None

    configs_json = []
    for tab in cfg.tabs:
        subj_key = (tab.adapter_kind, tab.resource_kind)
        subj_rk_id = f"resourceKind:id:{kind_index[subj_key]}_::_"

        # colorBy — always present
        color_by: dict = {
            "metricKey": tab.color_by_key,
            "value": tab.color_by_label or tab.color_by_key,
        }

        # sizeBy — None key means uniform cell sizing (no size metric)
        size_by: dict = {
            "metricKey": tab.size_by_key,
            "value": tab.size_by_label if tab.size_by_key is not None else "",
        }

        # groupBy — when no grouping kind is specified, emit a self-grouping block
        # using the subject resource kind itself.  Ops requires all 9 keys to be
        # present; an empty {} causes HeatMapAction.initParam to throw
        # JSONException("type not found") and the widget returns blank.
        # Corpus reference: idps-planner "VM by Host PPS" tab uses HostSystem as
        # both subject and groupBy (resourceKind:id:1_::_, id=004null002006VMWAREHostSystem).
        # Fix documented in knowledge/lessons/heatmap-empty-groupby-crashes-renderer.md.
        if tab.group_by_kind:
            gb_adapter = tab.group_by_adapter or tab.adapter_kind
            gb_kind = tab.group_by_kind
        else:
            # Self-grouping: use the subject kind as the single swim-lane group.
            gb_adapter = tab.adapter_kind
            gb_kind = tab.resource_kind
        gb_prefix = _ADAPTER_KIND_PREFIX.get(gb_adapter)
        if gb_prefix is None:
            raise ValueError(
                f"Heatmap groupBy: no known resourceKindId prefix for adapter kind "
                f"{gb_adapter!r} — extend _ADAPTER_KIND_PREFIX after harvesting "
                f"from an exported reference dashboard"
            )
        gb_key = (gb_adapter, gb_kind)
        gb_rk_id = f"resourceKind:id:{kind_index[gb_key]}_::_"
        # groupBy.id format: 004null + 6-digit adapter prefix + adapterKind + resourceKind
        # This is a stable Ops-internal composite ID; the format is documented in
        # knowledge/context/api-surface/widget_types_survey.md §Heatmap / §Gotchas #7.
        gb_id = f"004null{gb_prefix}{gb_adapter}{gb_kind}"
        gb_text = (tab.group_by_text or gb_kind) if tab.group_by_kind else tab.resource_kind
        group_by: dict = {
            "resourceKind": gb_kind,
            "adapterKind": gb_adapter,
            "typeId": gb_rk_id,
            "type": "resourceKind",
            "text": gb_text,
            "originalText": gb_text,
            "id": gb_id,
            "parentText": gb_adapter,
            "parentId": gb_adapter,
        }

        color_obj: dict = {
            "minValue": tab.color.min_value,
            "thresholds": {
                "values": tab.color.values,
                "colors": tab.color.colors,
            },
        }
        if tab.color.max_value is not None:
            color_obj["maxValue"] = tab.color.max_value

        configs_json.append({
            "name": tab.name,
            "resourceKind": subj_rk_id,
            "colorBy": color_by,
            "sizeBy": size_by,
            "groupBy": group_by,
            "thenBy": None,
            "color": color_obj,
            "focusOnGroups": tab.focus_on_groups,
            "relationalGrouping": False,
            "solidColoring": tab.solid_coloring,
            "mode": {"mode": False},
            "attributeKind": {"value": ""},
            "filterMode": "tagPicker",
            "tagFilter": None,
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
        })

    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "Heatmap",
        "title": w.title,
        "config": {
            "mode": cfg.mode,
            "depth": cfg.depth,
            "selfProvider": {"selfProvider": w.self_provider},
            "refreshInterval": 300,
            "refreshContent": {"refreshContent": False},
            "resource": [],
            "relationshipMode": {"relationshipMode": [1, -1, 0]},
            "title": w.title,
            "configs": configs_json,
            "value": 0,
        },
        "height": 600,
    }


def _property_list_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
) -> dict:
    """Render a PropertyList (vertical property/metric details panel) widget.

    Displays a list of metric or property values for the selected resource.
    Structurally similar to Scoreboard — both use the same
    ``metric.resourceKindMetrics[]`` envelope via ``_render_metric_spec()``.

    Key differences from Scoreboard:
    - Always interaction-driven (``selfProvider: false``); no self-provider mode
      observed across 47 live + 67 reference samples.
    - Uses ``showMetricFullName: {"metricFullName": <bool>}`` (inner key is
      ``metricFullName``, not ``showMetricFullName`` — verified from reference
      exports in ``reference/references/vmbro_vcf_operations_vcommunity/``).
    - ``relationshipMode`` is a plain integer ``0``, not wrapped in an object
      (verified from reference samples).
    - String properties use ``isStringMetric: true`` on their metric entries;
      authors set ``is_string_metric: true`` per entry in the YAML.

    Wire format reference: knowledge/context/api-surface/widget_renderer_scope.md
    §PropertyList and knowledge/context/api-surface/widget_types_survey.md §PropertyList.
    """
    cfg = w.property_list_config
    assert cfg is not None
    metric_obj = _render_metric_spec(cfg.properties, kind_index, w.widget_id)
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "PropertyList",
        "title": w.title,
        "config": {
            "visualTheme": cfg.visual_theme,
            "depth": cfg.depth,
            "refreshInterval": 300,
            "metric": metric_obj,
            "resource": [],
            "refreshContent": {"refreshContent": True},
            "relationshipMode": {"relationshipMode": 0},
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            "selfProvider": {"selfProvider": False},
            "title": w.title,
            "showMetricFullName": {"metricFullName": cfg.show_metric_full_name},
            "resInteractionMode": None,
        },
        "height": 600,
    }


def _resource_relationship_advanced_widget(
    w: Widget,
    kind_index: dict[tuple[str, str], int],
) -> dict:
    """Render a ResourceRelationshipAdvanced (topology tree) widget.

    Displays a relationship graph rooted at the selected resource.
    The ``tagFilter`` shape mirrors ResourceList — ``tagFilter.value.kind[]``
    holds ``resourceKind:id:N_::_`` synthetic refs from the kind_index table.
    When ``resource_kinds`` is empty the filter lists are also empty (the
    widget accepts any resource pushed via interaction).

    ``depth`` is a ``"<up>,<down>"`` string (e.g. ``"0,2"`` or ``"2,1"``).

    Wire format reference: reference/references/vmbro_vcf_operations_vcommunity/
    Management Pack/content/dashboards/vSphere Resource Management.json
    and VM Performance 2.0.json.
    """
    cfg = w.resource_relationship_advanced_config
    assert cfg is not None
    kinds = [
        f"resourceKind:id:{kind_index[(rk.adapter_kind, rk.resource_kind)]}_::_"
        for rk in cfg.resource_kinds
    ]
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": _clamp_gridster_floor(w.coords),
        "type": "ResourceRelationshipAdvanced",
        "title": w.title,
        "config": {
            "resourceId": None,
            "refreshInterval": 300,
            "traversalSpecId": "",
            "refreshContent": {"refreshContent": False},
            "resourceName": None,
            "title": w.title,
            "filterMode": "tagPicker",
            "tagFilter": {
                "path": [f"/source/kind/kind:{k}" for k in kinds],
                "value": {
                    "bus": [], "adapterKind": [], "kind": kinds,
                    "exclaim": False, "healthRange": [], "maintenanceSchedule": [],
                    "adapterInstance": [], "collector": [], "tier": [],
                    "state": [], "tag": [], "day": [], "status": [],
                },
            },
            "paginationNumber": cfg.pagination_number,
            "depth": cfg.depth,
            "customFilter": {
                "filter": [], "excludedResources": None, "includedResources": None,
            },
            "selectFirstRow": {"selectFirstRow": w.select_first_row},
            "selfProvider": {"selfProvider": cfg.self_provider},
        },
        "height": 600,
    }


def _build_dashboard_obj(
    dashboard: Dashboard,
    views_by_name: dict[str, ViewDef],
    kind_index: dict[tuple[str, str], int],
    resource_index: dict[tuple[str, str], int],
    owner_user_id: str,
) -> dict:
    widgets_json = []
    for w in dashboard.widgets:
        if w.type == "ResourceList":
            widgets_json.append(_resource_list_widget(w, kind_index, dashboard.id))
        elif w.type == "View":
            # Resolve to a bundled ViewDef when available; fall back to the raw
            # UUID for external (platform/other-MP) views.  A bare name that
            # isn't bundled cannot reach here — loader.validate() already rejects
            # that case as an authoring error.
            _view_ref: "ViewDef | str" = views_by_name.get(w.view_name, w.view_name)
            if _view_ref is w.view_name and _view_ref not in views_by_name:
                import sys as _sys
                print(
                    f"  INFO: dashboard {w.dashboard_name!r} widget {w.local_id!r}: "
                    f"external view UUID {w.view_name!r} — emitted verbatim",
                    file=_sys.stderr,
                )
            widgets_json.append(_view_widget(w, _view_ref, kind_index, resource_index))
        elif w.type == "TextDisplay":
            widgets_json.append(_text_display_widget(w))
        elif w.type == "Scoreboard":
            widgets_json.append(_scoreboard_widget(w, kind_index))
        elif w.type == "MetricChart":
            widgets_json.append(_metric_chart_widget(w, kind_index))
        elif w.type == "HealthChart":
            widgets_json.append(_health_chart_widget(w, kind_index, resource_index))
        elif w.type == "ParetoAnalysis":
            widgets_json.append(_pareto_analysis_widget(w, kind_index))
        elif w.type == "AlertList":
            widgets_json.append(_alert_list_widget(w))
        elif w.type == "ProblemAlertsList":
            widgets_json.append(_problem_alerts_list_widget(w, resource_index))
        elif w.type == "Heatmap":
            widgets_json.append(_heatmap_widget(w, kind_index))
        elif w.type == "PropertyList":
            widgets_json.append(_property_list_widget(w, kind_index))
        elif w.type == "ResourceRelationshipAdvanced":
            widgets_json.append(_resource_relationship_advanced_widget(w, kind_index))

    widget_id_by_local = {w.local_id: w.widget_id for w in dashboard.widgets}
    interactions_json = [
        {
            "widgetIdProvider": widget_id_by_local[ix.from_local_id],
            "type": ix.type,
            "widgetIdReceiver": widget_id_by_local[ix.to_local_id],
        }
        for ix in dashboard.interactions
    ]

    # Use 0 for creationTime/lastUpdateTime: VCF Ops overwrites both fields
    # on import, so the values in the bundle are placeholder only.  A constant
    # zero makes the output deterministic across repeated builds of the same
    # content, which keeps git diffs clean on idempotent re-publishes.
    now_ms = 0
    return {
        # Default dashboards to shared so other Ops users can see them.
        # The framework's audience is "an average vSphere admin needs
        # to find and use this" — private-to-author dashboards defeat
        # the point. Can be overridden per-dashboard via the YAML's
        # `shared:` field.
        "shared": dashboard.shared,
        "temporary": False,
        # Whether the dashboard is hidden in the Ops sidebar after import.
        # Factory dashboards default to visible (hidden: false). Pak-shipped
        # dashboards that need to be hidden (e.g. compliance) set hidden: true
        # explicitly in their YAML; that value is faithfully passed through here.
        "hidden": getattr(dashboard, "hidden", False),
        "creationTime": now_ms,
        "autoswitchEnabled": False,
        "importAttempts": 0,
        "lastUpdateUserId": owner_user_id,
        "columnProportion": "1",
        "importComplete": True,
        "description": dashboard.description,
        "columnCount": 1,
        "userId": owner_user_id,
        "states": [],
        "homeTab": False,
        # Ops folders: the dashboard's `name` field carries a leading
        # "<folder>/" segment, and `namePath` mirrors the folder. This
        # matches the pattern in the vROpsTOP + Troubleshooting VMs +
        # tkopton reference bundles. Ops renders the dashboard in the
        # sidebar under the folder, showing only the portion after the
        # slash as the visible name. `namePath` alone (without the
        # slash in `name`) does NOT place the dashboard in a folder.
        "name": f"{dashboard.name_path}/{dashboard.name}" if dashboard.name_path else dashboard.name,
        "namePath": dashboard.name_path,
        "gridsterMaxColumns": 12,
        "rank": 0,
        "disabled": False,
        "id": dashboard.id,
        "locked": False,
        "dashboardNavigations": {},
        "widgetInteractions": interactions_json,
        "lastUpdateTime": now_ms,
        "widgets": widgets_json,
    }


def render_dashboards_bundle_json(
    dashboards: list[Dashboard],
    views_by_name: dict[str, ViewDef],
    owner_user_id: str,
    owning_adapter_kind: Optional[str] = None,
) -> str:
    """Render all of an owner's dashboards into the single
    dashboard/dashboard.json the VCF Ops content importer expects
    inside dashboards/<ownerUserId>. The `entries.resourceKind` table
    is a shared synthetic-id lookup for every resource kind referenced
    by any ResourceList widget across the bundle.

    Args:
        dashboards: Dashboard objects to render.
        views_by_name: ViewDef lookup keyed by name (for View-type widgets).
        owner_user_id: UUID string placed in ``userId`` / ``lastUpdateUserId``.
        owning_adapter_kind: When provided, populate ``entries.adapterKind``
            with a single binding entry and set ``dashboards[].adapterName``
            to this value.  Required for the platform's DashboardImporter to
            associate the dashboard with the owning adapter; without it the
            importer silently drops the dashboard.
            Spec ref: knowledge/context/cleanroom-spec/spec/18-pak-content-bundle.md §A1.
    """
    kind_index: dict[tuple[str, str], int] = {}
    for d in dashboards:
        for w in d.widgets:
            # ResourceList widgets contribute their explicit resource_kinds
            for rk in w.resource_kinds:
                key = (rk.adapter_kind, rk.resource_kind)
                if key not in kind_index:
                    kind_index[key] = len(kind_index)
            # Scoreboard and MetricChart widgets contribute kinds via metric specs
            if w.type == "Scoreboard" and w.scoreboard_config:
                for spec in w.scoreboard_config.metrics:
                    key = (spec.adapter_kind, spec.resource_kind)
                    if key not in kind_index:
                        kind_index[key] = len(kind_index)
            elif w.type == "MetricChart" and w.metric_chart_config:
                for spec in w.metric_chart_config.metrics:
                    key = (spec.adapter_kind, spec.resource_kind)
                    if key not in kind_index:
                        kind_index[key] = len(kind_index)
            # HealthChart and ParetoAnalysis use a flat single metric spec —
            # one (adapter_kind, resource_kind) pair per widget
            elif w.type == "HealthChart" and w.health_chart_config:
                key = (w.health_chart_config.adapter_kind, w.health_chart_config.resource_kind)
                if key not in kind_index:
                    kind_index[key] = len(kind_index)
            elif w.type == "ParetoAnalysis" and w.pareto_analysis_config:
                key = (w.pareto_analysis_config.adapter_kind, w.pareto_analysis_config.resource_kind)
                if key not in kind_index:
                    kind_index[key] = len(kind_index)
            elif w.type == "Heatmap" and w.heatmap_config:
                # Each tab contributes two kinds: the subject resource kind and
                # the groupBy resource kind. Both must appear in entries.resourceKind[]
                # so configs[].resourceKind and groupBy.typeId resolve correctly.
                for tab in w.heatmap_config.tabs:
                    subj_key = (tab.adapter_kind, tab.resource_kind)
                    if subj_key not in kind_index:
                        kind_index[subj_key] = len(kind_index)
                    if tab.group_by_kind:
                        gb_adapter = tab.group_by_adapter or tab.adapter_kind
                        gb_key = (gb_adapter, tab.group_by_kind)
                        if gb_key not in kind_index:
                            kind_index[gb_key] = len(kind_index)
            elif w.type == "PropertyList" and w.property_list_config:
                for spec in w.property_list_config.properties:
                    key = (spec.adapter_kind, spec.resource_kind)
                    if key not in kind_index:
                        kind_index[key] = len(kind_index)
            elif w.type == "ResourceRelationshipAdvanced" and w.resource_relationship_advanced_config:
                for rk in w.resource_relationship_advanced_config.resource_kinds:
                    key = (rk.adapter_kind, rk.resource_kind)
                    if key not in kind_index:
                        kind_index[key] = len(kind_index)
    # Build resource index for self-provider pinned View, ProblemAlertsList,
    # and HealthChart widgets.  Those are the widget types that reference
    # entries.resource[] in their widget configs; other self-provider types
    # (Scoreboard, MetricChart, Heatmap, AlertList) use "resource": [] and
    # don't need an entry here.
    #
    # IMPORTANT: the key is the CONTAINER resource, not the raw pin target.
    # When the YAML pins a View to a leaf kind (e.g. VMWARE/HostSystem), the
    # importer cannot resolve "entries.resource[name='HostSystem']" because no
    # resource on the instance carries that name.  _resolve_view_pin redirects
    # leaf-kind pins to the adapter's world singleton (e.g. "vSphere World")
    # which DOES exist on every vSphere-connected instance.  For world kinds
    # (e.g. vcfcf_compliance/ComplianceWorld) the kind name equals the resource
    # name, so _resolve_view_pin returns them unchanged.
    #
    # HealthChart widgets don't require a ``pin:`` block — a self-provider
    # HealthChart's own ``adapter_kind``/``resource_kind`` (already required
    # for the metric's resourceKindId) doubles as the implicit pin target via
    # ``_self_provider_pin_container``. An explicit ``pin:`` still wins if set.
    #
    # The resource_index maps (container_adapter_kind, container_resource_kind)
    # to a 0-based slot matching entries.resource[].internalId.
    # resource_name_map stores the display name for each container key, which
    # may differ from the resource_kind (e.g. "Virtual Machines" vs
    # "VirtualMachine" for a custom group).
    resource_index: dict[tuple[str, str], int] = {}
    resource_name_map: dict[tuple[str, str], str] = {}
    for d in dashboards:
        for w in d.widgets:
            container = None
            if w.self_provider and w.type in ("View", "ProblemAlertsList") and w.pin:
                container = _resolve_view_pin(w.pin.adapter_kind, w.pin.resource_kind)
            elif w.self_provider and w.type == "HealthChart" and w.health_chart_config:
                cfg = w.health_chart_config
                container = _self_provider_pin_container(
                    w, cfg.adapter_kind, cfg.resource_kind
                )
            if container is not None:
                c_adapter, c_kind, c_name = container
                container_key = (c_adapter, c_kind)
                if container_key not in resource_index:
                    resource_index[container_key] = len(resource_index)
                    resource_name_map[container_key] = c_name

    entries_resource_kind = [
        {
            "resourceKindKey": rk_kind,
            "internalId": f"resourceKind:id:{idx}_::_",
            "adapterKindKey": rk_adapter,
        }
        for (rk_adapter, rk_kind), idx in kind_index.items()
    ]
    entries_resource = [
        {
            "resourceKindKey": res_kind,
            "internalId": f"resource:id:{idx}_::_",
            "adapterKindKey": res_adapter,
            "identifiers": [],
            "name": resource_name_map[(res_adapter, res_kind)],
        }
        for (res_adapter, res_kind), idx in resource_index.items()
    ]
    entries: dict = {"resourceKind": entries_resource_kind}
    # A1: emit entries.adapterKind when an owning adapter is specified.
    # The importer uses this to bind the dashboard to the adapter's content
    # namespace; without it the dashboard is silently dropped on pak install.
    # Spec ref: knowledge/context/cleanroom-spec/spec/18-pak-content-bundle.md §A1.
    if owning_adapter_kind:
        entries["adapterKind"] = [
            {
                "internalId": "adapterKind:id:0_::_",
                "adapterKindKey": owning_adapter_kind,
            }
        ]
    if entries_resource:
        entries["resource"] = entries_resource
    # Derive the envelope UUID deterministically from the sorted dashboard
    # IDs so that repeated builds of identical content yield the same bytes.
    # The envelope UUID is an import-session identifier only — VCF Ops does
    # not persist it after import.
    _id_seed = ",".join(sorted(d.id for d in dashboards)).encode()
    _envelope_uuid = str(uuid.UUID(bytes=hashlib.sha256(_id_seed).digest()[:16], version=4))

    def _build_dashboard_with_adapter(d: Dashboard) -> dict:
        obj = _build_dashboard_obj(d, views_by_name, kind_index, resource_index, owner_user_id)
        # A1: set adapterName on each dashboard object so the importer can file it.
        if owning_adapter_kind:
            obj["adapterName"] = owning_adapter_kind
        return obj

    return json.dumps(
        {
            "uuid": _envelope_uuid,
            "entries": entries,
            "dashboards": [_build_dashboard_with_adapter(d) for d in dashboards],
        }
    )
