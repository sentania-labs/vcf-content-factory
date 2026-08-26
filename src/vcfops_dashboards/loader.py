"""YAML -> in-memory dashboard / view definition models.

UUIDs are random uuid4 values stored in each view / dashboard YAML's
`id` field, minted on first validate and never touched again. This
matches the super metric loader's contract (see
`knowledge/context/authoring/uuids_and_cross_references.md`) and means rename-safe
install: changing a view or dashboard's name does not change its id,
so the existing server-side object is updated in place on re-sync.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Union

import yaml

from vcfops_dashboards.yaml_utils import strict_load as _strict_load

# Stable namespace for derived UUIDs. Do NOT change once content has
# been deployed, every dashboard/view id is derived from this.
NS = uuid.UUID("4b8d2c10-1f9e-4f4f-9b90-0e8f6a8e2a12")


class DashboardValidationError(ValueError):
    pass


def stable_id(kind: str, name: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}::{name}"))


# Transformation enum whitelist, verified against real exported view XML.
# See knowledge/context/wire-formats/view_column_wire_format.md §Per-column transformations.
# MIN/SUM/LAST/TIMESTAMP/TIME_POINT confirmed present in live 13.6 MB export
# (ops-recon 2026-05-27): MIN=15 uses, SUM=59, LAST=138, TIMESTAMP=24, TIME_POINT=12.
# STDDEV and HIGH_WATER_MARK confirmed absent (zero hits).
_VALID_TRANSFORMATIONS: set[str] = {
    "CURRENT", "NONE", "AVG", "MAX", "MIN", "SUM", "LAST",
    "PERCENTILE", "TIMESTAMP", "TIME_POINT",
    "TREND", "FORECAST", "TRANSFORM_EXPRESSION",
}

# Time-interval-selector unit whitelist.
_VALID_TIME_WINDOW_UNITS: set[str] = {
    "MONTHS", "WEEKS", "DAYS", "HOURS", "MINUTES", "YEARS",
}


@dataclass
class ViewTimeWindow:
    """View-wide aggregation time window, rendered as a time-interval-selector
    Control at the top of the Controls block.

    ``unit`` must be one of MONTHS, WEEKS, DAYS, HOURS, MINUTES, YEARS.
    ``count`` is a positive integer.

    This window applies to ALL aggregating columns in the view (AVG, MAX,
    PERCENTILE, TRANSFORM_EXPRESSION). Per-column time windows are not
    supported by VCF Ops, one view, one window.
    See knowledge/context/wire-formats/view_column_wire_format.md §Limitations.
    """
    unit: str   # MONTHS|WEEKS|DAYS|HOURS|MINUTES|YEARS
    count: int  # positive integer
    advanced_time_mode: bool = False
    # start_period/end_period: only observed pairing in the vendor corpus is
    # PREVIOUS/NOW (the sole advancedTimeMode=true control found across the
    # full reference corpus, "vSphere Cluster HA Admission Control status",
    # View - Set 3.xml, ViewDef fc64c67a-d5b0-4a03-a10b-767b9b247120). Left
    # free-form (not a closed enum) since the wider vocabulary is unknown,
    # see FB-011 / knowledge/context/feedback_queue.md. The renderer defaults
    # both to PREVIOUS/NOW when advanced_time_mode is true and these are
    # unset, since advanced mode with no range is the leading suspect for
    # the "View request timed out" bug.
    start_period: Optional[str] = None
    end_period: Optional[str] = None


@dataclass
class InstancedGroupSpec:
    """Instanced-group column config, one row/column-set per instance of a
    colon-syntax metric group (e.g. one row per license name under
    ``vCommunity|Licensing:<name>|...``).

    Vendor wire format (ground truth, RULE-016 read-only reference):
      reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/
        ESXi Host License Information vCommunity.xml (Licensing group)
        ESXi Packages.xml                              (Packages group)
        Windows Services vCommunity.xml                (Guest OS|Services group)
      All three ship an ``attributes-selector`` Control whose first
      ``attributeInfos`` Item is a "driver" column carrying
      ``attributeKey=Instance Name``, ``isInstancedGroup=true``,
      ``showInstanceName``, ``instanceGroupName`` and ``keepInstanceSummary``.
      Every subsequent Item in the same view is a normal-looking column whose
      ``attributeKey`` embeds one *representative* instance name in the
      colon segment (e.g. ``vCommunity|Licensing:Evaluation Mode|Edition Key``,
      ``vCommunity|Configuration|Packages:atlantic|Package Name``,
      ``vCommunity|Guest OS|Services:DHCP Client|Service Name``). VCF Ops
      expands these into one row per instance found on the resource at
      render time, the embedded instance name is a *sample* used to
      identify the group+suffix pattern, not a filter.

    AMBIguity (flagged per brief, not guessed): whether the *value* of the
    embedded sample instance name matters to the server's instanced-group
    matching (vs. being purely cosmetic / first-seen-at-authoring-time) is
    not verifiable from static XML alone. This loader requires the author
    to supply ``sample_instance`` explicitly (no default) so the choice is
    visible in the YAML and in code review, rather than silently guessing
    a placeholder. Recommend confirming behavior against a live instance
    via api-explorer / ops-recon before relying on the exact string.

    ``name`` (-> instanceGroupName) is emitted verbatim. The vendor pak
    uses the literal ``GROUP_vCommunity`` for every one of its own
    user-defined instanced groups (Licensing, Packages, Guest OS Services)
    regardless of the underlying metric family, see the three files
    above. VMware's own built-in instanced groups use different literal
    tokens (``GROUP_net``, ``GROUP_cpu``, ``GROUP_disk``, ...; see
    ``View - Set 4.xml`` in the same directory). The factory does not
    validate ``name`` against a known enum, treat it as an opaque
    wire-format token the author supplies.

    Two column roles, distinguished by whether ``prefix``/``suffix`` are set:

    - Driver column (``prefix``/``suffix`` both unset): the single
      "Instance Name" pseudo-column that turns on instanced-group mode
      for the view. ``show_instance_name`` / ``keep_instance_summary``
      apply here.
    - Member column (``prefix`` AND ``suffix`` both set): a data column
      belonging to the group. The loader synthesizes the wire
      ``attributeKey`` as ``f"{prefix}:{sample_instance}|{suffix}"``.
      Authors must NOT also set ``attribute:`` on a member (or driver)
      column, see ``ViewDef.validate()`` for the rejection.
    """
    name: str
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    sample_instance: Optional[str] = None
    show_instance_name: bool = True
    keep_instance_summary: bool = False

    @property
    def is_driver(self) -> bool:
        return not self.prefix and not self.suffix


@dataclass
class TimeSegmentSpec:
    """A time-segment ("Interval Breakdown") pseudo-column on a list view.

    Turns a list view into one row per time bucket (for example one row
    per month over a ``time_window`` of ``YEARS x 1``) instead of one row
    per object. The column carries no metric; the sibling metric columns
    are sampled once per bucket.

    Wire format (verbatim vendor export, RULE-016 read-only reference:
    reference/docs/extracted/view-time-segment/, column 0 of the
    ``[VCF Consumption Overview v2] VCF Licensing Overtime`` ViewDef)::

        <Property name="objectType" value="RESOURCE"/>
        <Property name="attributeKey" value="Interval Breakdown"/>
        <Property name="rollUpCount" value="0"/>
        <Property name="sortCriteria" value="false"/>
        <Property name="isTimeSegment" value="true"/>
        <Property name="breakdownBy" value="MONTHS"/>
        <Property name="startingOnUnit" value="WEEKS"/>
        <Property name="startingOnCount" value="1"/>
        <Property name="displayName" value="Month"/>

    No adapterKind/resourceKind/rollUpType/transformations/isProperty
    properties: the renderer emits exactly the nine above, in that order.
    ``attributeKey`` is the literal ``Interval Breakdown`` (synthesized by
    the loader, never author-supplied). Only ``breakdownBy=MONTHS`` with
    ``startingOnUnit=WEEKS`` / ``startingOnCount=1`` is evidence-backed;
    the other time units are accepted because they share the
    time-interval-selector enum, but are unverified on a live instance.
    Evidence exists only for list views; the loader rejects the column on
    distribution and trend views.

    YAML::

        columns:
          - display_name: Month
            time_segment:
              breakdown_by: MONTHS
              starting_on_unit: WEEKS    # optional, default WEEKS
              starting_on_count: 1       # optional, default 1
    """
    breakdown_by: str
    starting_on_unit: str = "WEEKS"
    starting_on_count: int = 1


@dataclass
class ViewColumn:
    attribute: str
    display_name: str
    unit: str = ""  # preferredUnitId, optional
    # Per-column metric transformation.
    # One of: CURRENT NONE AVG MAX PERCENTILE TREND FORECAST TRANSFORM_EXPRESSION
    # Default CURRENT matches the list-view default for existing views.
    transformation: Optional[str] = None
    # Required when transformation == "PERCENTILE". Range 1..99.
    percentile: Optional[int] = None
    # Required when transformation == "TRANSFORM_EXPRESSION".
    # Arbitrary arithmetic formula; only `avg` is bound as a symbol.
    transform_expression: Optional[str] = None
    # Required when transformation == "TIME_POINT".
    # The metric key whose extreme timestamp this column displays.
    metric_to_relate_with: Optional[str] = None
    # Display label for the related metric (shown in column header tooltip).
    localized_metric_to_relate_with: Optional[str] = None
    # Which extreme of the related metric to find: "MAX" or "MIN".
    operator_to_relate_with: Optional[str] = None
    # Per-column color thresholds. See knowledge/context/wire-formats/view_column_wire_format.md.
    yellow_bound: Optional[Union[float, str]] = None
    orange_bound: Optional[Union[float, str]] = None
    # red_bound accepts float for numeric, str for property-match (e.g. "Powered Off")
    red_bound: Optional[Union[float, str]] = None
    # Required when all three numeric bounds are set.
    # False = higher is worse (red=high). True = lower is worse (red=low).
    ascending_range: Optional[bool] = None
    # True when the attribute is a string property (e.g. VCF-CF Compliance|profile_name).
    # Controls isProperty and isStringAttribute in the rendered XML.
    # Default False preserves existing behaviour for numeric metric columns.
    is_property: bool = False
    is_string_attribute: bool = False
    # Instanced-group column config. When set, `attribute` is synthesized by
    # the loader (driver -> "Instance Name"; member ->
    # "{prefix}:{sample_instance}|{suffix}") and must not be author-supplied.
    # See InstancedGroupSpec docstring for the wire format and citations.
    instanced_group: Optional["InstancedGroupSpec"] = None
    # Time-segment ("Interval Breakdown") pseudo-column. When set,
    # `attribute` is synthesized by the loader as the literal
    # "Interval Breakdown" and the column renders the isTimeSegment wire
    # shape instead of a metric column. See TimeSegmentSpec.
    time_segment: Optional["TimeSegmentSpec"] = None


@dataclass
class SummaryRow:
    """A footer summary row on a list view (e.g. totals)."""
    display_name: str = "Summary"
    aggregation: str = "SUM"  # SUM, AVG, MIN, MAX, COUNT
    # Column indexes to aggregate. None = all columns.
    column_indexes: List[int] | None = None


# Valid data_type values and their allowed presentation types.
_VALID_PRESENTATIONS: dict[str, set[str]] = {
    "list": {"list", "summary"},
    "distribution": {"bar-chart", "pie-chart", "donut-chart"},
    "trend": {"line-chart"},
}

# Attribute-name substrings (case-insensitive, matched anywhere in the
# `attribute:` key) that historically indicate a string/enum/boolean VCF Ops
# *resource property* rather than a genuine numeric metric. Used only to
# power the distribution-view "no data" validate-time WARNING below.
#
# Root cause: DEF-012, documented in
# knowledge/context/api-surface/distribution_view_no_data.md. A
# `data_type: distribution` column that is really a string property but is
# declared `is_property: false` (the default) renders with a fixed numeric
# histogram (buckets min/max/count) instead of a DISCRETE bucket set, the
# widget then queries the metric subsystem for a numeric metric that does
# not exist and silently shows "No data to display" / "Metrics displaying
# 0 of N". The fix shape is `is_property: true` + `is_string_attribute:
# true` + `buckets: {dynamic: true, calc_function: DISCRETE}`.
#
# This is deliberately an allowlist of *suspicion*, not a blocklist of
# certainty: a false negative (an unusual property name this list doesn't
# catch) is acceptable for a WARNING; a false positive on a genuinely
# numeric metric distribution is not. Calibrated against every real
# `data_type: distribution` view attribute in
# content/sdk-adapters/vcommunity-vsphere/views/ (2026-07-14, tooling),
# zero collisions with the numeric set (counts, sizes, GHz, percentages,
# reservations, limits, latencies, capacities, VMDK/RDM counts, datastore/
# host counts) while catching the version/model/enabled/policy/available/
# behavior/technology-shaped properties that produced DEF-012.
_DISTRIBUTION_PROPERTY_ATTR_HINTS = (
    "version", "model", "polic", "enabled", "available", "allow",
    "behavior", "technolo", "vendor", "status", "state", "capabilit",
    "name", "type", "mode", "level",
)


@dataclass
class BucketsConfig:
    """Bucketing configuration for distribution views.

    Two modes:
    - Fixed numeric histogram: is_dynamic=False + min_value/max_value/count
    - Discrete grouping: is_dynamic=True + calc_function="DISCRETE"
      (works for string properties)
    """
    count: int = 10
    min_value: float = 0.0
    max_value: float = 100.0
    is_dynamic: bool = False
    calc_function: str = "DISCRETE"  # used only when is_dynamic=True


@dataclass
class SubjectFilterCondition:
    """One condition in a SubjectType metric/property filter.

    Vendor wire format (ground truth, RULE-016 read-only reference):
      reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
        content/reports/View - Collection01.xml:7-9, ``VM Network Top
        Talkers``:
          <SubjectType adapterKind="VMWARE" filter="[[{&quot;condition&quot;:
            &quot;GREATER_THAN&quot;,&quot;transform&quot;:&quot;AVG&quot;,
            &quot;metricKey&quot;:&quot;net|usage_average&quot;,
            &quot;metricValue&quot;:{&quot;isStringMetric&quot;:false,
            &quot;value&quot;:12},&quot;businessHours&quot;:false,
            &quot;filterType&quot;:&quot;metrics&quot;}]]" resourceKind=
            "VirtualMachine" type="descendant"/>

    Decoded, the ``filter=`` attribute is a JSON array-of-arrays:
    the outer array is OR'd groups, each inner array is AND'd
    conditions within that group, confirmed by surveying every
    ``filter="..."`` occurrence across the vendor reference corpus
    (``View - Collection01.xml``, ``View - Set {1,2,3,4}.xml``,
    ``Dell EMC Server Details Workbench.xml``, ~35 unique filter
    strings total). Two AND'd conditions in one group:
      ``[[{mem|guestOSMemNotCollecting==1},{summary|running==1}]]``
    Multiple OR'd single-condition groups:
      ``[[{sys|poweredOn==0}],[{runtime|connectionState==notConnected}],
        ...]``

    Fields observed across the whole survey (fail-closed: only these
    are accepted; anything else the vendor corpus doesn't prove is
    rejected rather than silently passed through):
      - ``filterType``: ``"metrics"`` | ``"properties"``
      - ``metricKey``: the same colon/pipe metric-key syntax used
        elsewhere in this loader (e.g. ``net|usage_average``).
      - ``condition``: ``"EQUALS"`` | ``"NOT_EQUALS"`` | ``"GREATER_THAN"``
        (no LESS_THAN or other comparator observed anywhere in corpus).
      - ``metricValue``: ``{"isStringMetric": bool, "value": ...}``,
        ``isStringMetric`` is derived from the Python type of ``value``
        (str -> true, int/float -> false); every observed occurrence is
        consistent with this rule, including string-typed "true"/"false"
        literals (e.g. ``config|extraConfig|vcpu_hotadd == "true"`` has
        ``isStringMetric: true`` despite looking boolean).
      - ``transform`` (optional): ``"AVG"`` | ``"CURRENT"``, omitted
        entirely in several vendor examples, never any other value.
      - ``businessHours`` (optional bool), omitted in several vendor
        examples; when present, always paired with a metrics-type,
        transform-bearing condition in the corpus (co-occurrence, not
        a proven hard requirement, the loader does not enforce the
        pairing since no counter-example was found to test against).

    Key order on the JSON object mirrors the ``VM Network Top Talkers``
    fixture exactly (``condition``, ``transform``, ``metricKey``,
    ``metricValue``, ``businessHours``, ``filterType``) so the byte-exact
    regression test can assert against the vendor XML verbatim, the
    corpus shows the key order varies vendor-side (JS object literal
    insertion order, not a schema constraint), so this is a rendering
    choice, not a proven requirement, but it keeps our one currently-
    ported fixture byte-identical to source.
    """
    filter_type: str          # "metrics" | "properties"
    metric_key: str
    condition: str             # "EQUALS" | "NOT_EQUALS" | "GREATER_THAN"
    value: Union[str, int, float]
    transform: Optional[str] = None       # "AVG" | "CURRENT"
    business_hours: Optional[bool] = None

    _VALID_FILTER_TYPES = {"metrics", "properties"}
    _VALID_CONDITIONS = {"EQUALS", "NOT_EQUALS", "GREATER_THAN"}
    _VALID_TRANSFORMS = {"AVG", "CURRENT"}

    @property
    def is_string_metric(self) -> bool:
        return isinstance(self.value, str)

    def validate(self, view_name: str) -> None:
        if not self.metric_key.strip():
            raise DashboardValidationError(
                f"view {view_name}: subject_filter condition missing metric_key"
            )
        if self.filter_type not in self._VALID_FILTER_TYPES:
            raise DashboardValidationError(
                f"view {view_name}: subject_filter.filter_type must be one of "
                f"{sorted(self._VALID_FILTER_TYPES)}; got {self.filter_type!r}"
            )
        if self.condition not in self._VALID_CONDITIONS:
            raise DashboardValidationError(
                f"view {view_name}: subject_filter.condition must be one of "
                f"{sorted(self._VALID_CONDITIONS)}; got {self.condition!r} "
                "(only these are proven present in the vendor reference "
                "corpus, fail closed rather than guess)"
            )
        if isinstance(self.value, bool):
            raise DashboardValidationError(
                f"view {view_name}: subject_filter.value must not be a bare "
                "boolean, the vendor corpus only shows string \"true\"/"
                "\"false\" literals or numeric thresholds; use a quoted "
                "string if that's the intent"
            )
        if not isinstance(self.value, (str, int, float)):
            raise DashboardValidationError(
                f"view {view_name}: subject_filter.value must be a string, "
                f"int, or float; got {type(self.value).__name__}"
            )
        if self.transform is not None and self.transform not in self._VALID_TRANSFORMS:
            raise DashboardValidationError(
                f"view {view_name}: subject_filter.transform must be one of "
                f"{sorted(self._VALID_TRANSFORMS)} (or omitted); got {self.transform!r}"
            )
        if self.business_hours is not None and not isinstance(self.business_hours, bool):
            raise DashboardValidationError(
                f"view {view_name}: subject_filter.business_hours must be a bool "
                f"(unquoted true/false in YAML); got {type(self.business_hours).__name__} "
                f"{self.business_hours!r}, a quoted \"true\"/\"false\" string is not "
                "accepted and is not silently coerced"
            )


@dataclass
class ViewSubject:
    """One (adapter_kind, resource_kind) subject of a view (``subjects:``)."""
    adapter_kind: str
    resource_kind: str

    @property
    def key(self) -> tuple:
        return (self.adapter_kind, self.resource_kind)


@dataclass
class ViewDef:
    name: str
    description: str
    adapter_kind: str
    resource_kind: str
    columns: List[ViewColumn]
    id: str = ""
    source_path: Path | None = None
    # Optional SubjectType metric/property filter, OR of AND-groups.
    # Applied identically to both the "descendant" and "self" SubjectType
    # elements (the vendor corpus always carries the same filter= value on
    # both). See SubjectFilterCondition docstring for the wire format.
    subject_filter: Optional[List[List["SubjectFilterCondition"]]] = None
    # Multi-subject views (YAML `subjects:`): every entry gets its own
    # descendant+self <SubjectType> pair, in authored order. Empty means
    # the single (adapter_kind, resource_kind) subject above; when set,
    # adapter_kind/resource_kind mirror subjects[0] so per-column kinds and
    # every other consumer of the scalar pair keep working unchanged.
    # Wire evidence: reference/docs/extracted/view-multi-subject/.
    subjects: List[ViewSubject] = field(default_factory=list)
    summary: SummaryRow | None = None
    # "list" (default), "distribution", or "trend"
    data_type: str = "list"
    # Presentation type; default depends on data_type
    presentation: str = "list"
    # Distribution-view bucketing config (only relevant when data_type="distribution")
    buckets: BucketsConfig | None = None
    # Trend-view forecast horizon in days (0 = no forecast)
    forecast_days: int = 0
    # Metric transformations for trend views. May include "TREND", "FORECAST".
    # "NONE" and "CURRENT" are the list-view defaults.
    transformations: List[str] | None = None
    # View-wide aggregation time window. Applies to all aggregating columns.
    # Rendered as a time-interval-selector Control replacing the default 24h window.
    time_window: Optional[ViewTimeWindow] = None
    # metadata control ``hideObjectNameColumn``. False (the historical
    # hardcoded value) keeps the object-name column; true hides it, which
    # a time_segment list view wants (one row per bucket, not per object).
    # Wire evidence: reference/docs/extracted/view-time-segment/.
    hide_object_name: bool = False
    released: bool = False   # publish gate
    version: str = "1.0.0"  # internal semver
    # Optional list of custom group names this view is scoped to.
    # When set, the dependency walker surfaces these groups as deps.
    # YAML key: `customgroup:` (str or list[str]).
    customgroups: List[str] = field(default_factory=list)
    # Provenance: "factory", a third-party project slug, or "" (unknown).
    # Populated by the loader from source_path; never author-supplied.
    provenance: str = ""

    @property
    def subject_kinds(self) -> List[tuple]:
        """``[(adapter_kind, resource_kind), ...]`` in SubjectType emission
        order: ``subjects`` when declared, else the single scalar pair."""
        if self.subjects:
            return [sub.key for sub in self.subjects]
        return [(self.adapter_kind, self.resource_kind)]

    def validate(self, enforce_framework_prefix: bool = True, embedded_in_dashboard: bool = False) -> None:
        import warnings
        if not self.name.strip():
            raise DashboardValidationError("view: name is required")
        if enforce_framework_prefix and not self.name.startswith("[VCF Content Factory] "):
            src = str(self.source_path) if self.source_path else self.name
            raise DashboardValidationError(
                f'{src}: name "{self.name}" missing framework prefix '
                f'"[VCF Content Factory]". All factory-authored content must carry the literal '
                f'"[VCF Content Factory]" prefix (see CLAUDE.md §Hard rules #5). For third-party '
                f"bundle content, ensure the bundle manifest sets factory_native: false."
            )
        if len(self.description) > 1024:
            raise DashboardValidationError(
                f"view {self.name}: description is {len(self.description)} characters, "
                f"exceeding the 1024-character limit. On VCF Operations 9.1, a "
                f"VIEW_DEFINITIONS content-zip import with a description over 1024 "
                f"characters fails SILENTLY server-side (state=FAILED, skipped=1, "
                f"empty errorMessages), see "
                f"knowledge/context/wire-formats/view_column_wire_format.md "
                f'"View-level field limits" and knowledge/context/known_limitations.md '
                f"§14. Shorten the description."
            )
        if not self.adapter_kind or not self.resource_kind:
            raise DashboardValidationError(
                f"view {self.name}: adapter_kind and resource_kind required"
            )
        if self.subjects:
            seen: set = set()
            for sub in self.subjects:
                if not sub.adapter_kind or not sub.resource_kind:
                    raise DashboardValidationError(
                        f"view {self.name}: every subjects entry requires adapter_kind "
                        f"and resource_kind"
                    )
                if sub.key in seen:
                    raise DashboardValidationError(
                        f"view {self.name}: duplicate subject "
                        f"{sub.adapter_kind}:{sub.resource_kind} in subjects"
                    )
                seen.add(sub.key)
            if self.subjects[0].key != (self.adapter_kind, self.resource_kind):
                raise DashboardValidationError(
                    f"view {self.name}: adapter_kind/resource_kind must mirror subjects[0]"
                )
        if not self.columns:
            raise DashboardValidationError(
                f"view {self.name}: at least one column required"
            )
        for c in self.columns:
            if not c.attribute or not c.display_name:
                raise DashboardValidationError(
                    f"view {self.name}: column requires attribute and display_name"
                )
            if c.time_segment is not None:
                self._validate_time_segment_column(c)
                continue
            self._validate_column(c)
        # Instanced-group cross-check: every member column's group `name`
        # must have a matching driver column somewhere in the same view.
        # Without the driver, VCF Ops has no isInstancedGroup/instanceGroupName
        # signal and the member columns render as ordinary (non-expanding)
        # single-instance columns, the exact bug this capability fixes.
        driver_names = {
            c.instanced_group.name
            for c in self.columns
            if c.instanced_group is not None and c.instanced_group.is_driver
        }
        for c in self.columns:
            ig = c.instanced_group
            if ig is not None and not ig.is_driver and ig.name not in driver_names:
                raise DashboardValidationError(
                    f"view {self.name}: column {c.display_name!r} belongs to "
                    f"instanced_group {ig.name!r} but no driver column "
                    f"(instanced_group with no prefix/suffix, name={ig.name!r}) "
                    "is present in this view. Add the 'Instance Name' driver "
                    "column first."
                )
        # SubjectType metric filter, OR of AND-groups.
        if self.subject_filter is not None:
            if not self.subject_filter:
                raise DashboardValidationError(
                    f"view {self.name}: subject_filter must not be an empty list"
                )
            for group in self.subject_filter:
                if not group:
                    raise DashboardValidationError(
                        f"view {self.name}: subject_filter group must not be empty"
                    )
                for cond in group:
                    cond.validate(self.name)
        if self.data_type not in _VALID_PRESENTATIONS:
            raise DashboardValidationError(
                f"view {self.name}: data_type must be one of "
                f"{sorted(_VALID_PRESENTATIONS.keys())}, got {self.data_type!r}"
            )
        allowed = _VALID_PRESENTATIONS[self.data_type]
        if self.presentation not in allowed:
            raise DashboardValidationError(
                f"view {self.name}: presentation {self.presentation!r} is not "
                f"valid for data_type {self.data_type!r}; allowed: {sorted(allowed)}"
            )
        # Distribution-view "no data" footgun (DEF-012): a
        # property-looking attribute rendered with a fixed numeric histogram
        # (buckets not dynamic) instead of a DISCRETE bucket set silently
        # produces "No data to display". WARNING only, existing
        # intentionally-numeric distributions (buckets not set, or set
        # non-dynamic on purpose) must not break. See
        # knowledge/context/api-surface/distribution_view_no_data.md.
        #
        # The fully-fixed shape requires BOTH pieces on the property-hinted
        # column: `is_property: true` AND view-level dynamic DISCRETE
        # buckets (`buckets: {dynamic: true, calc_function: DISCRETE}`).
        # Either piece alone is a *partial* fix that still renders "No data
        # to display" (Codex PR #57 P2 finding, the original guard's
        # outer/column gates each independently suppressed on a partial
        # fix). `is_string_attribute` is deliberately NOT part of the
        # suppression condition: two legitimate vendor views (vSphere
        # Cluster Admission Control Policy, vSphere Cluster DRS Automation
        # Level, in content/sdk-adapters/vcommunity-vsphere/views/) use
        # is_property: true + is_string_attribute: false + dynamic DISCRETE
        # buckets and must not warn.
        if self.data_type == "distribution":
            buckets_dynamic_discrete = (
                self.buckets is not None
                and self.buckets.is_dynamic
                and self.buckets.calc_function == "DISCRETE"
            )
            for c in self.columns:
                attr_lower = c.attribute.lower()
                if attr_lower.startswith("supermetric:"):
                    continue
                if not any(hint in attr_lower for hint in _DISTRIBUTION_PROPERTY_ATTR_HINTS):
                    continue
                if c.is_property and buckets_dynamic_discrete:
                    # Fully-fixed shape, silent.
                    continue
                missing: list[str] = []
                if not c.is_property:
                    missing.append("is_property: true")
                if not buckets_dynamic_discrete:
                    missing.append(
                        "buckets: {dynamic: true, calc_function: DISCRETE}"
                    )
                warnings.warn(
                    f"view {self.name!r} column {c.display_name!r} "
                    f"(attribute {c.attribute!r}): data_type is "
                    "'distribution' and this attribute looks like a "
                    "string/enum resource property, but "
                    + " and ".join(missing)
                    + ", it will render as a fixed numeric histogram "
                    "(min/max/count) instead of a discrete bucket set, "
                    "which silently produces \"No data to display\" "
                    "(DEF-012; see knowledge/context/api-surface/"
                    "distribution_view_no_data.md). If this attribute "
                    "really is a string property, fix with: "
                    "is_property: true and "
                    "buckets: {dynamic: true, calc_function: DISCRETE} "
                    "(is_string_attribute is independent and does not "
                    "affect this warning). If it is genuinely numeric, "
                    "this warning is a false positive and can be ignored.",
                    UserWarning,
                    stacklevel=2,
                )
        # Time window validation
        if self.time_window is not None:
            tw = self.time_window
            if tw.unit not in _VALID_TIME_WINDOW_UNITS:
                raise DashboardValidationError(
                    f"view {self.name}: time_window.unit {tw.unit!r} is not valid; "
                    f"must be one of {sorted(_VALID_TIME_WINDOW_UNITS)}"
                )
            if tw.count <= 0:
                raise DashboardValidationError(
                    f"view {self.name}: time_window.count must be a positive integer, "
                    f"got {tw.count!r}"
                )
        # Warn if aggregating columns present but no time_window set
        _AGGREGATING = {"AVG", "MAX", "PERCENTILE", "TRANSFORM_EXPRESSION"}
        needs_window = any(
            (c.transformation or "CURRENT").upper() in _AGGREGATING
            for c in self.columns
        )
        if needs_window and self.time_window is None and not embedded_in_dashboard:
            warnings.warn(
                f"view {self.name!r}: one or more columns use an aggregating "
                "transformation (AVG/MAX/PERCENTILE/TRANSFORM_EXPRESSION) but "
                "no time_window is set. Columns will aggregate over the view's "
                "default window (typically 24 hours). Set time_window: "
                "{{unit: MONTHS, count: 6}} to make the window explicit.",
                UserWarning,
                stacklevel=2,
            )

    def _validate_time_segment_column(self, c: "ViewColumn") -> None:  # noqa: F821
        """A time_segment column carries nothing but its bucket spec.

        Evidence (reference/docs/extracted/view-time-segment/) exists only
        for list views, so the column is rejected elsewhere rather than
        guessed at. Metric-column fields (unit, transformation, bounds,
        is_property, instanced_group) have no place in the wire shape.
        """
        name_ctx = f"view {self.name!r} column {c.display_name!r}"
        ts = c.time_segment
        assert ts is not None
        if self.data_type != "list":
            raise DashboardValidationError(
                f"{name_ctx}: time_segment columns are only supported on "
                f"data_type: list views (got {self.data_type!r}); the only vendor "
                "evidence is on list views (reference/docs/extracted/view-time-segment/)."
            )
        if ts.breakdown_by not in _VALID_TIME_WINDOW_UNITS:
            raise DashboardValidationError(
                f"{name_ctx}: time_segment.breakdown_by {ts.breakdown_by!r} must be "
                f"one of {sorted(_VALID_TIME_WINDOW_UNITS)}"
            )
        if ts.starting_on_unit not in _VALID_TIME_WINDOW_UNITS:
            raise DashboardValidationError(
                f"{name_ctx}: time_segment.starting_on_unit {ts.starting_on_unit!r} must "
                f"be one of {sorted(_VALID_TIME_WINDOW_UNITS)}"
            )
        if ts.starting_on_count < 1:
            raise DashboardValidationError(
                f"{name_ctx}: time_segment.starting_on_count must be >= 1, "
                f"got {ts.starting_on_count}"
            )
        stray = [
            label for label, val in (
                ("unit", c.unit),
                ("transformation", c.transformation),
                ("percentile", c.percentile),
                ("transform_expression", c.transform_expression),
                ("yellow_bound", c.yellow_bound),
                ("orange_bound", c.orange_bound),
                ("red_bound", c.red_bound),
                ("ascending_range", c.ascending_range),
                ("instanced_group", c.instanced_group),
            ) if val not in (None, "")
        ]
        if c.is_property or c.is_string_attribute:
            stray.append("is_property/is_string_attribute")
        if stray:
            raise DashboardValidationError(
                f"{name_ctx}: time_segment columns carry no metric fields; "
                f"remove {', '.join(stray)}"
            )

    def _validate_column(self, c: "ViewColumn") -> None:  # noqa: F821
        """Per-column validation for transformation and threshold fields."""
        import warnings
        name_ctx = f"view {self.name!r} column {c.display_name!r}"

        # Transformation whitelist
        transform = (c.transformation or "CURRENT").upper()
        if transform not in _VALID_TRANSFORMATIONS:
            raise DashboardValidationError(
                f"{name_ctx}: transformation {c.transformation!r} is not valid. "
                f"Must be one of {sorted(_VALID_TRANSFORMATIONS)}. "
                "See knowledge/context/wire-formats/view_column_wire_format.md."
            )

        # Instanced-group member column transformation whitelist.
        # A survey of every isInstancedGroup Item across all reference/references/
        # vmbro_* content/reports/*.xml files (2026-07-10, tooling) found vendor
        # evidence for CURRENT, MAX, TRANSFORM_EXPRESSION, and TIMESTAMP on
        # instanced-group member columns (e.g. "View - Set 4.xml": "Windows CPU
        # Usage" MAX, "Linux Disk Performance" TRANSFORM_EXPRESSION, "VM
        # Snapshots List" TIMESTAMP), _xml_instanced_group_item() mirrors their
        # companion-property shape exactly (see that function's docstring).
        # PERCENTILE and TIME_POINT have NO vendor example on an instanced-group
        # member column anywhere in the surveyed corpus, despite both appearing
        # on plenty of *non*-instanced columns in the same files. Per the
        # framework's no-silent-downgrade posture, an unproven combination is
        # rejected here rather than guessed at render time, the importer's
        # actual behavior for e.g. a per-instance percentile is unknown.
        if (
            c.instanced_group is not None
            and not c.instanced_group.is_driver
            and transform in ("PERCENTILE", "TIME_POINT")
        ):
            raise DashboardValidationError(
                f"{name_ctx}: transformation {transform!r} is not supported on "
                "instanced_group member columns, no vendor XML example of this "
                "combination exists in the surveyed reference corpus (RULE-016), "
                "so the wire shape is unproven and the factory will not guess it. "
                "See knowledge/context/wire-formats/view_column_wire_format.md "
                "§ Instanced-group columns."
            )

        # PERCENTILE cross-validation
        if transform == "PERCENTILE":
            if c.percentile is None:
                raise DashboardValidationError(
                    f"{name_ctx}: transformation PERCENTILE requires percentile "
                    "field (integer 1..99)."
                )
            if not (1 <= c.percentile <= 99):
                raise DashboardValidationError(
                    f"{name_ctx}: percentile {c.percentile!r} out of range; "
                    "must be 1..99."
                )
        elif c.percentile is not None:
            raise DashboardValidationError(
                f"{name_ctx}: percentile field is only valid when "
                f"transformation == 'PERCENTILE', got {c.transformation!r}."
            )

        # TRANSFORM_EXPRESSION cross-validation
        if transform == "TRANSFORM_EXPRESSION":
            if not c.transform_expression:
                raise DashboardValidationError(
                    f"{name_ctx}: transformation TRANSFORM_EXPRESSION requires "
                    "transform_expression field (formula string using 'avg' symbol)."
                )
        elif c.transform_expression is not None:
            raise DashboardValidationError(
                f"{name_ctx}: transform_expression field is only valid when "
                f"transformation == 'TRANSFORM_EXPRESSION', got {c.transformation!r}."
            )

        # TIME_POINT cross-validation
        _time_point_fields = (
            c.metric_to_relate_with,
            c.localized_metric_to_relate_with,
            c.operator_to_relate_with,
        )
        if transform == "TIME_POINT":
            if not all(_time_point_fields):
                raise DashboardValidationError(
                    f"{name_ctx}: transformation TIME_POINT requires all three "
                    "fields: metric_to_relate_with, localized_metric_to_relate_with, "
                    "and operator_to_relate_with."
                )
            op = (c.operator_to_relate_with or "").upper()
            if op not in ("MAX", "MIN"):
                raise DashboardValidationError(
                    f"{name_ctx}: operator_to_relate_with must be 'MAX' or 'MIN', "
                    f"got {c.operator_to_relate_with!r}."
                )
        elif any(_time_point_fields):
            raise DashboardValidationError(
                f"{name_ctx}: metric_to_relate_with / localized_metric_to_relate_with "
                f"/ operator_to_relate_with are only valid when "
                f"transformation == 'TIME_POINT', got {c.transformation!r}."
            )

        # Color threshold validation
        # Determine which bounds are numeric vs string
        def _is_numeric(v) -> bool:
            if v is None:
                return False
            try:
                float(str(v))
                return True
            except (ValueError, TypeError):
                return False

        has_yellow = c.yellow_bound is not None
        has_orange = c.orange_bound is not None
        has_red = c.red_bound is not None
        red_is_string = has_red and not _is_numeric(c.red_bound)

        # String-only red_bound case: ascending_range must NOT be set
        if red_is_string and not has_yellow and not has_orange:
            if c.ascending_range is not None:
                raise DashboardValidationError(
                    f"{name_ctx}: ascending_range must not be set when only "
                    "red_bound is specified as a string (property-match coloring)."
                )
        elif has_yellow or has_orange or (has_red and not red_is_string):
            # Numeric bound case: require ascending_range when all three are set
            all_numeric_set = has_yellow and has_orange and has_red and not red_is_string
            if all_numeric_set and c.ascending_range is None:
                raise DashboardValidationError(
                    f"{name_ctx}: ascending_range is required when all three "
                    "numeric color bounds (yellow_bound, orange_bound, red_bound) "
                    "are set. Use False for higher-is-worse (CPU %, latency), "
                    "True for lower-is-worse (free capacity %, headroom)."
                )
            # Warn on inverted band ordering
            if (all_numeric_set and c.ascending_range is not None
                    and _is_numeric(c.yellow_bound) and _is_numeric(c.orange_bound)
                    and _is_numeric(c.red_bound)):
                y = float(str(c.yellow_bound))
                o = float(str(c.orange_bound))
                r = float(str(c.red_bound))
                if not c.ascending_range:
                    # Higher-is-worse: yellow < orange < red
                    if y >= o or o >= r:
                        warnings.warn(
                            f"{name_ctx}: ascending_range=False (higher-is-worse) "
                            f"expects yellow < orange < red, got "
                            f"yellow={y}, orange={o}, red={r}.",
                            UserWarning,
                            stacklevel=3,
                        )
                else:
                    # Lower-is-worse: yellow > orange > red
                    if y <= o or o <= r:
                        warnings.warn(
                            f"{name_ctx}: ascending_range=True (lower-is-worse) "
                            f"expects yellow > orange > red, got "
                            f"yellow={y}, orange={o}, red={r}.",
                            UserWarning,
                            stacklevel=3,
                        )


@dataclass
class WidgetResourceKindRef:
    adapter_kind: str
    resource_kind: str
    # pin: only. Display name of the container resource the importer must
    # resolve (``entries.resource[].name``). Empty (default) lets the
    # renderer pick it: the leaf-kind redirect table, then the world
    # display-name table, then the kind key. Set it when the world
    # singleton's display name differs from its kind key and the renderer
    # does not know the pair yet. Live-verified 2026-08-26 on devel 9.1.1
    # (knowledge/context/wire-formats/dashboard_view_pin_resolution.md): a
    # pin whose name is not a resource display name never binds and leaves
    # the dashboard stuck deferred (isLoading: true). Only world-singleton
    # pins are verified; the loader rejects a name on any leaf kind listed
    # in render._VIEW_PIN_CONTAINER (e.g. VMWARE/HostSystem) until a live
    # probe proves a leaf resource can be pinned by name.
    name: str = ""


@dataclass
class WidgetResourceRef:
    """A single named resource a widget binds to (``entries.resource[]``).

    ``name`` is the resource's display name on the target instance (for
    example ``License Usage`` for VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD),
    which the importer resolves at install time. Used by resource-mode
    Scoreboards (``metric_mode: resource``).
    """
    adapter_kind: str
    resource_kind: str
    name: str


@dataclass
class MetricSpec:
    """One metric entry within a Scoreboard, MetricChart, or PropertyList widget.

    Maps to a single entry in ``metric.resourceKindMetrics[]``, or to one
    entry per listed kind on a dashboard whose ``summary_for`` names more
    than one kind (see ``Dashboard.summary_for``).

    Fields:
        adapter_kind:     VMWARE, NSXTAdapter, etc.
        resource_kind:    VirtualMachine, ClusterComputeResource, etc.
        metric_key:       Ops stat key, e.g. ``cpu|usage_average`` or
                          ``Super Metric|sm_<uuid>``.
        metric_name:      Display name for the metric (shown in legend/tile).
        unit_id:          Optional Ops unit ID string (e.g. ``"percent"``).
        unit:             Optional display unit string (e.g. ``"%"``).
        color_method:     0=custom thresholds, 1=no color, 2=dynamic,
                          3=custom thresholds as a percent of ``max_value``
                          (read-only; see below). Default 2.
        yellow_bound:     Threshold value when color_method=0.
        orange_bound:     Threshold value when color_method=0.
        red_bound:        Threshold value when color_method=0.

    Bound semantics (replayed against the product's own Scoreboard
    ``.action`` calls on 9.2, 2026-08-25; lesson
    ``scoreboard-partial-bounds-render-unknown``):

    - With ``color_method: 0`` the three bounds are all-or-nothing. The
      server answers ``value: "?"`` / ``state: Unknown`` for a metric
      entry that carries only some of ``yellowBound`` / ``orangeBound`` /
      ``redBound``, even though the value exists. The loader therefore
      rejects a partial set; none at all is accepted and renders an
      uncolored tile.
    - Thresholds are ascending and inclusive: ``>= yellow`` Warning,
      ``>= orange`` Immediate, ``>= red`` Critical. "Red at >= 1" is
      ``(1, 1, 1)``.
    - ``color_method: 3`` is how vendor exports express the same three
      bounds as a percent of ``max_value``. It is documented here for
      reading those exports only: the factory emits bounds solely for
      ``color_method: 0`` and nulls them for every other method, and the
      partial-set behaviour on 3 is unverified server-side. The loader
      rejects any bound supplied with ``color_method: 3`` so the author
      gets an error instead of an uncolored tile.
        label:            Short tile label override (Scoreboard). Optional.
        is_string_metric: True when the metric key returns a string property
                          (e.g. ``summary|parentVcenter``). Default False.
                          PropertyList commonly uses True; Scoreboard/MetricChart
                          default to False (backwards compatible).
        max_value:        Optional numeric ceiling for the tile, emitted as
                          the per-metric ``maxValue`` (stringified, e.g.
                          ``"100"``). Required for a readable gauge
                          (Scoreboard ``visual_theme: 9``), where it sets
                          the dial's full-scale value. ``None`` emits the
                          historical ``""``.
    """
    adapter_kind: str
    resource_kind: str
    metric_key: str
    metric_name: str
    unit_id: str = ""
    unit: str = ""
    color_method: int = 2  # dynamic by default
    yellow_bound: float | None = None
    orange_bound: float | None = None
    red_bound: float | None = None
    label: str = ""
    is_string_metric: bool = False
    max_value: float | None = None


@dataclass
class ScoreboardConfig:
    """Type-specific config for a Scoreboard widget.

    ``visual_theme`` is 1..9: 1 Original, 2 Solid, 3 Default, 4 Simple,
    5 Pastel, 6 Shadow, 7 Outline, 8 Gradient (factory default), 9 Gauge.
    The widget resets anything outside 1..9 to 3, so the loader rejects
    it instead (source: the appliance's ``editors/Scoreboard.js`` and
    ``widgets/Scoreboard.js``, see knowledge/context/api-surface/
    dashboard_widgets_alertvolume_section_viewdetails.md §4).

    Gauge recipe (``visual_theme: 9``)
    ----------------------------------
    A gauge is a Scoreboard whose tiles render as dials; the editor's
    Score/Gauge toggle is literally ``visualTheme == 9``. Surveyed on 9.2
    (15 gauge widgets, ``getWidgetConfigs`` captures, 2026-08-25; see
    knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md):
    ``mode.layoutMode`` is ``"fixedView"`` and ``showMetricName`` is true
    on every one, both of which this renderer already emits. What makes a
    dial readable is per-metric:

    - ``max_value``: the dial's full-scale value (``maxValue`` on the
      wire, a string such as ``"100"``). When left unset the component
      falls back to 100 for a ``%`` unit and to **1** for anything else,
      so set it for every non-percentage metric or the dial is drawn
      against 1.
    - ``color_method: 0`` plus ``yellow_bound`` / ``orange_bound`` /
      ``red_bound``: the colored arcs (``colorMethod: 0`` with the three
      ``*Bound`` fields).
    - Optional gauge switches ``show_remaining``, ``show_percent_text``,
      ``focus_on_percent`` (all default false; emitted only on a gauge).
    - ``layout_mode``: ``fixedView`` (default) or ``floatingView``; not a
      gauge switch, it only controls row stretching vs scrolling.

    Minimal YAML::

        - id: cpu_gauge
          type: Scoreboard
          title: CPU Usage
          coords: {x: 1, y: 1, w: 3, h: 4}
          visual_theme: 9
          box_columns: 1
          metrics:
            - adapter_kind: VMWARE
              resource_kind: VirtualMachine
              metric_key: cpu|usage_average
              metric_name: CPU Usage
              unit: "%"
              max_value: 100
              color_method: 0
              yellow_bound: 70
              orange_bound: 85
              red_bound: 95

    Left at the historical defaults so existing output is byte-identical:
    the captures show ``oldMetricValues: false`` and ``roundDecimals:
    null`` on gauges. The all-three-or-none bound contract, and why
    ``colorMethod: 3`` (bounds as percent of ``maxValue``) is read-only
    for the factory, are documented on ``MetricSpec``.
    """
    metrics: List[MetricSpec] = field(default_factory=list)
    visual_theme: int = 8
    show_sparkline: bool = False
    period_length: str | None = None  # None, "dashboardTime", "last24Hour", etc.
    show_resource_name: bool = False
    show_metric_name: bool = True
    show_metric_unit: bool = True
    box_columns: int = 4
    box_height: float | None = None
    value_size: int = 24
    label_size: int = 12
    round_decimals: float | None = 1
    max_cell_count: int = 100
    # "fixedView" (default; rows stretch to fill the widget height) or
    # "floatingView" (boards keep box_height, body scrolls). Independent
    # of gauge vs score.
    layout_mode: str = "fixedView"
    # Gauge-only booleans (visual_theme 9). Emitted only for a gauge so
    # non-gauge output stays byte-identical; the component ignores them
    # on other themes anyway.
    show_remaining: bool = False
    show_percent_text: bool = False
    focus_on_percent: bool = False
    # ``resourceKind`` (default): metrics are resolved against the page
    # object / self-provider subject kind via ``resourceKindMetrics[]``.
    # ``resource``: every metric is pinned to ONE named resource via
    # ``resourceMetrics[]`` and ``entries.resource[]``; ``resource`` below
    # names it. Wire evidence: the ``License Overview`` widget of Scott's
    # public VCF License Consumption Overview export (six SMs pinned to the
    # single ``License Usage`` resource); see
    # knowledge/context/wire-formats/wire_formats.md §Scoreboard resource mode.
    metric_mode: str = "resourceKind"
    resource: "WidgetResourceRef | None" = None
    # ``showDT`` (dynamic-threshold colouring) and ``refreshContent``.
    # Defaults are the historical hardcoded values (false / true) so
    # existing output is byte-identical.
    show_dt: bool = False
    refresh_content: bool = True


_VALID_SCOREBOARD_LAYOUT_MODES = frozenset({"fixedView", "floatingView"})
_VALID_SCOREBOARD_METRIC_MODES = frozenset({"resourceKind", "resource"})


@dataclass
class MetricChartConfig:
    """Type-specific config for a MetricChart widget."""
    metrics: List[MetricSpec] = field(default_factory=list)


@dataclass
class TextDisplayConfig:
    """Type-specific config for a TextDisplay widget."""
    html: str = "<br>"


@dataclass
class HealthChartConfig:
    """Type-specific config for a HealthChart widget.

    Uses a FLAT metric spec, a single metric key and resourceKindId
    referenced directly in config, not in a resourceKindMetrics[] array.
    This is different from Scoreboard/MetricChart which use the array pattern.

    Fields:
        adapter_kind:    Adapter kind key (e.g. VMWARE).
        resource_kind:   Resource kind key (e.g. VirtualMachine).
        metric_key:      Ops stat key (e.g. ``cpu|usage_average``).
        metric_name:     Short display name for the metric.
        metric_full_name: Full display name with unit suffix. Defaults to metric_name.
        mode:            ``all`` (interaction-driven), ``resource`` (pinned).
        depth:           Resource traversal depth. Default 1.
        chart_height:    Sparkline bar height in px. 135 or 190. Default 135.
        pagination_number: Page size. Default 15.
        sort_by_dir:     ``asc`` or ``desc``. Default ``asc``.
        yellow_bound:    Yellow threshold value. -2 for DT. Default -2.
        orange_bound:    Orange threshold value. Default -2.
        red_bound:       Red threshold value. Default -2.
        show_resource_name: Show resource name on bars. Default True.
    """
    adapter_kind: str = "VMWARE"
    resource_kind: str = ""
    metric_key: str = ""
    metric_name: str = ""
    metric_full_name: str = ""
    mode: str = "all"
    depth: int = 1
    chart_height: int = 135
    pagination_number: int = 15
    sort_by_dir: str = "asc"
    yellow_bound: float = -2
    orange_bound: float = -2
    red_bound: float = -2
    show_resource_name: bool = True


@dataclass
class ParetoAnalysisConfig:
    """Type-specific config for a ParetoAnalysis (Top-N) widget.

    Only Shape 1 (mode=all/resource) is supported for authoring. Shape 2
    (mode=metric with metricOption/tagOption) requires live-instance metric
    picker interaction and cannot be statically authored.

    Fields:
        adapter_kind:  Adapter kind key (e.g. VMWARE).
        resource_kind: Resource kind key (e.g. VirtualMachine).
        metric_key:    Ops stat key.
        metric_name:   Display name for the metric (shown as axis label).
        mode:          ``all`` (all resources of kind) or ``resource`` (pinned).
        top_n:         Number of top-ranked bars to show. Default 10.
        bottom_n:      If > 0, show bottom-N (lowest) instead of top-N.
        top_option:    ``metricsHighestUtilization`` (default) or
                       ``metricsLowestUtilization``.
        depth:         Resource traversal depth. Default 10.
        regeneration_time: Refresh cycle in minutes. Default 15.
        round_decimals: Decimal places. Default 1.
    """
    adapter_kind: str = "VMWARE"
    resource_kind: str = ""
    metric_key: str = ""
    metric_name: str = ""
    mode: str = "all"
    top_n: int = 10
    bottom_n: int = 0
    top_option: str = "metricsHighestUtilization"
    depth: int = 10
    regeneration_time: int = 15
    round_decimals: float = 1


@dataclass
class AlertListConfig:
    """Type-specific config for an AlertList widget.

    Displays a filterable alert grid. Typically interaction-driven (receives
    a resource from a picker), but can also operate in self-provider mode.

    Fields:
        criticality:   List of criticality level ints to include.
                       2=Warning, 3=Major, 4=Critical. Default [2, 3, 4].
        alert_types:   List of alert type code strings (e.g. "15_19").
                       Empty list = all types.
        status:        List of status ints. [] = all. [0] = active only.
        state:         List of state values. Usually [].
        alert_impact:  List of impact strings. [] = all. ["health"], etc.
        alert_action:  List of action values. Usually [].
        mode:          "all" (default).
        depth:         Resource traversal depth. Default 1.
    """
    criticality: List[int] = field(default_factory=lambda: [2, 3, 4])
    alert_types: List[str] = field(default_factory=list)
    status: List[int] = field(default_factory=list)
    state: List = field(default_factory=list)
    alert_impact: List[str] = field(default_factory=list)
    alert_action: List = field(default_factory=list)
    mode: str = "all"
    depth: int = 1
    alert_definitions: List[str] = field(default_factory=list)
    # When True, emit selfProvider:false + resource:[{resourceId:"resource:id:0_::_",
    # resourceName:"vSphere World"}] instead of the standard self-provider shape.
    # This mirrors the sdwan ProblemAlertsList corpus pattern and is required when
    # a definition-pinned AlertList needs to query the full fleet without an
    # interaction-driven resource binding.  See knowledge/lessons/heatmap-empty-groupby-crashes-renderer.md
    # for the AlertList counterpart.
    pin_to_world: bool = False


@dataclass
class PropertyListConfig:
    """Type-specific config for a PropertyList widget.

    Displays a vertical list of metric/property values for the selected
    resource. Structurally similar to Scoreboard but vertical and
    single-resource oriented. Typically interaction-driven (receives a
    resource from a View or ResourceList picker).

    Fields:
        properties:            List of MetricSpec entries to display. Set
                               ``is_string_metric: true`` on string property
                               keys (e.g. ``summary|parentVcenter``).
        visual_theme:          Display style integer. 0=default. Range 0–5.
        depth:                 Resource traversal depth. Default 1.
        show_metric_full_name: Show the full metric name in each row.
                               Default True.
    """
    properties: List[MetricSpec] = field(default_factory=list)
    visual_theme: int = 0
    depth: int = 1
    show_metric_full_name: bool = True


@dataclass
class HeatmapColorThreshold:
    """Color threshold band for a Heatmap tab.

    ``values`` are the lower-bound breakpoints; ``colors`` are the hex
    color strings for each band. Color count distribution observed on the
    live instance: 3 colors (59 tabs), 5 colors (18), 6 colors (10),
    4 colors (7). There is no strict relationship between values and colors
    length enforced by Ops, the UI sets them together.
    """
    min_value: float = 0
    max_value: Optional[float] = None
    values: List[float] = field(default_factory=lambda: [0, 50, 100])
    colors: List[str] = field(default_factory=lambda: ["#74B43B", "#ECC33E", "#DE3F30"])


@dataclass
class HeatmapTab:
    """One tab definition inside a Heatmap widget's ``configs[]`` array.

    Fields:
        name:              Tab display name.
        adapter_kind:      Adapter kind of the subject resource (e.g. VMWARE).
        resource_kind:     Resource kind to display as heatmap cells (e.g. VirtualMachine).
        color_by_key:      Metric key for cell coloring (e.g. ``cpu|usage_average``).
        color_by_label:    Display label for colorBy metric (e.g. ``CPU|Usage (%)``).
        size_by_key:       Metric key for cell sizing. ``None`` = uniform sizing.
        size_by_label:     Display label for sizeBy metric. ``""`` when uniform.
        group_by_adapter:  Adapter kind of the grouping parent resource. Defaults to
                           ``adapter_kind`` when not specified.
        group_by_kind:     Resource kind to group cells by (e.g. ClusterComputeResource).
                           ``None`` = no grouping (groupBy emitted as empty object).
        group_by_text:     Display text for the group kind (shown in UI).
        color:             Color threshold configuration.
        solid_coloring:    True = flat fill, False = gradient. Default False.
        focus_on_groups:   Zoom into groups on selection. Default True.
    """
    name: str = ""
    adapter_kind: str = "VMWARE"
    resource_kind: str = ""
    color_by_key: str = ""
    color_by_label: str = ""
    size_by_key: str | None = None
    size_by_label: str = ""
    group_by_adapter: str = ""
    group_by_kind: str = ""
    group_by_text: str = ""
    color: HeatmapColorThreshold = field(default_factory=HeatmapColorThreshold)
    solid_coloring: bool = False
    focus_on_groups: bool = True


@dataclass
class HeatmapConfig:
    """Type-specific config for a Heatmap (treemap) widget.

    Heatmap is the most complex widget type. Its ``configs[]`` array holds
    one entry per tab; tabs allow the user to switch between different metric
    views without navigating away from the dashboard.

    Fields:
        tabs:    One or more tab definitions. At least one required.
        mode:    ``"all"`` (all resources of kind, interaction-driven or self-provider).
                 Matches the outer config.mode field.
        depth:   Resource traversal depth. Default 10 (typical for Heatmap).
    """
    tabs: List[HeatmapTab] = field(default_factory=list)
    mode: str = "all"
    depth: int = 10


@dataclass
class ProblemAlertsListConfig:
    """Type-specific config for a ProblemAlertsList widget.

    Top problem alerts impacting a badge (health/risk/efficiency) for
    the selected resource or its descendants. Usually self-provider,
    pinned to a container resource like vSphere World.

    Fields:
        impacted_badge:      "health", "risk", "efficiency", or "" (all).
        triggered_object:    "children" (descendants) or "self". Default "children".
        top_issues_limit:    Max alerts to display. 0 = no limit (default).
    """
    impacted_badge: str = "health"
    triggered_object: str = "children"
    top_issues_limit: int = 0


@dataclass
class AlertVolumeConfig:
    """Type-specific config for an AlertVolume widget (wire type
    ``IntSummaryAlertVolume``, palette name "Alert Volume").

    Source: knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md
    §1 (appliance widget + editor source, 9.1.1 and 9.2, Suite API export
    samples under reference/docs/extracted/dashboard-widgets/).

    The stored config is ONLY ``title``, ``refreshContent``,
    ``refreshInterval``, ``selfProvider`` and, with self provider ON, a
    single-object ``resource: {resourceId, resourceName}`` (an object, not
    the array other widgets use). The 7-day window and "all criticalities"
    are hard-coded in the component: there is no time window, severity,
    or chart option anywhere in the config, so the loader rejects such
    YAML keys instead of silently dropping them.

    Self provider OFF (default) consumes a single incoming ``resourceId``
    interaction (exactly one selected resource; zero or many are ignored).
    Self provider ON requires ``pin`` to a container resource kind, the
    same way a self-provider View widget does.

    Fields:
        refresh_content:  ``refreshContent`` flag. Default False (the vendor
                          Home template's interaction-driven instance).
        refresh_interval: Seconds. Default 300.
    """
    refresh_content: bool = False
    refresh_interval: int = 300


# YAML keys an AlertVolume widget cannot honor: the component hard-codes a
# 7-day window and shows every criticality, and it carries no metrics.
_ALERT_VOLUME_FORBIDDEN_KEYS = (
    "criticality", "severity", "alert_types", "type_codes", "status", "state",
    "alert_impact", "alert_action", "alert_definitions", "time_window",
    "date_range", "period_length", "metrics", "view", "resource_kinds",
    "depth", "mode", "pin_to_world",
)


@dataclass
class ResourceRelationshipAdvancedConfig:
    """Type-specific config for a ResourceRelationshipAdvanced widget.

    Displays a relationship graph (topology tree) rooted at the selected
    resource, showing ancestors and/or descendants to a configurable depth.
    Typically interaction-driven (receives a resource selection from another
    widget such as ResourceList or View).

    Fields:
        resource_kinds:   List of resource kinds whose resources are eligible
                          as root nodes for the graph.  Each entry maps to one
                          ``resourceKind:id:N_::_`` synthetic ref in the wire
                          ``tagFilter.value.kind[]``.  When empty the widget
                          accepts any resource pushed via interaction.
        depth:            Traversal depth expressed as "<up>,<down>" string, e.g.
                          "0,2" (0 ancestors, 2 descendants) or "2,1".
                          Default "2,1".
        pagination_number: Number of rows per page. Default 5.
        self_provider:    When True the widget is self-provider (does not wait
                          for an incoming interaction). Default False.
    """
    resource_kinds: List[WidgetResourceKindRef] = field(default_factory=list)
    depth: str = "2,1"
    pagination_number: int = 5
    self_provider: bool = False


@dataclass
class SectionConfig:
    """Type-specific config for a Section widget (collapsible row header).

    A Section is a full-width, zero-height header row that groups the
    widgets beneath it; the Ops UI renders a collapse/expand chevron on
    it and hides the member widgets when collapsed. Source of truth:
    knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md
    §3 (appliance ``widgets/Section.js`` + ``GridsterPanel.js``, 9.1.1 and
    9.2 captures, Suite API export samples under
    reference/docs/extracted/dashboard-widgets/).

    Export (import-bundle) shape::

        {"collapsed": false, "id": "<uuid>", "gridsterCoords": {"w": 12, "x": 1, "h": 1, "y": 5},
         "type": "Section", "title": "...",
         "config": {"title": "...", "titleLocalized": "...", "description": "", "widgets": ["<uuid>", ...]},
         "height": 0}

    ``gridsterW`` is always 12 and ``gridsterH`` always 1 (class statics),
    ``height`` is 0. ``config.widgets`` is the explicit membership list and
    is **authoritative at load**: only listed widgets are hidden when the
    Section collapses. The UI itself (re)computes that list after any
    layout edit as "every non-hidden widget below this Section, in
    gridsterY order, until the next Section". The loader mirrors that rule
    when ``widgets:`` is not authored: members are every non-Section widget
    whose ``coords.y`` is strictly between this Section's row and the next
    Section's row (by y), ordered by (y, x). Author ``widgets:`` explicitly
    to override.

    Fields:
        collapsed:   Initial collapsed state. Default False.
        member_ids:  Widget local ids that belong to this Section, either
                     authored (``widgets:``) or inferred by row order.
    """
    collapsed: bool = False
    member_ids: List[str] = field(default_factory=list)
    # True when ``widgets:`` was authored explicitly, False when inferred.
    explicit_members: bool = False


# The only link forms the widget's View Details click handler resolves.
_VIEW_DETAILS_PREFIXES = ("http://", "https://", "/ui/", "/vcf-operations/ui/")


# YAML keys that only make sense on a data widget. A Section carrying any of
# them is an authoring error (a Section has no subject, no data, and no
# interaction endpoints).
_SECTION_FORBIDDEN_KEYS = (
    "metrics", "view", "resource_kinds", "pin", "self_provider",
    "property_list", "configs", "metric_key", "resource_relationship_advanced",
    "column_preset", "relationship_mode", "view_details",
)


# ResourceList "Show Columns" grid-state presets. Closed enum, see
# Widget.column_preset docstring-comment for why this isn't a raw-blob
# passthrough. Keys are the YAML-facing values; ``render.py`` maps
# "name-only" to the verbatim captured wire-format constant.
_SUPPORTED_COLUMN_PRESETS = frozenset({"name-only"})


@dataclass
class Widget:
    local_id: str  # author-supplied short id used for interaction wiring
    type: str  # ResourceList | View | TextDisplay | Scoreboard | MetricChart | HealthChart | ParetoAnalysis | AlertList | ProblemAlertsList | PropertyList | ResourceRelationshipAdvanced | Section
    title: str
    coords: dict  # {x, y, w, h}
    # Section only: collapsible row-header config. See SectionConfig.
    section_config: "SectionConfig | None" = None
    # Optional, any non-Section widget: copied verbatim into the widget
    # config's ``viewDetails`` field, the "View Details" link at the
    # bottom of the widget (every widget on 9.x carries one, ``""`` when
    # unset). ``None`` (default) emits nothing, so output for existing
    # content is byte-identical.
    #
    # Accepted forms are exactly what the product's click handler
    # understands (WidgetBase.createViewDetailsBottomBar, see
    # knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md
    # §2): an absolute ``http://`` / ``https://`` URL (opens a new tab) or
    # a relative Angular shell route starting with ``/ui/`` or
    # ``/vcf-operations/ui/`` (navigates in place). Anything else is
    # handed to the router verbatim and does not resolve, so the loader
    # rejects it. Links are STATIC: there is no placeholder expansion on
    # the product side (no ``%resourceId%`` / ``{resourceId}``), so a
    # link to "the current object" cannot be expressed. Portable example,
    # another dashboard by its YAML id:
    #   view_details: "/ui/operate/dashboards/dashboards;tabId=<dashboard uuid>"
    # A resourceId-bearing route is instance-specific and does not survive
    # a move between instances.
    view_details: Optional[str] = None
    # ResourceList only:
    resource_kinds: List[WidgetResourceKindRef] = field(default_factory=list)
    # ResourceList only: optional typed "Show Columns" grid-state preset.
    # Wire format: a top-level widget `states[]` array carrying a captured
    # ExtJS grid-state blob, keyed `permResGrid_widget_<dashUuid>_<widgetUuid>`.
    # See knowledge/context/api-surface/resourcelist_column_state_wire_format.md
    # for the full investigation, the blob is an internal, unpublished Ops
    # UI persistence artefact (no OpenAPI schema) reproduced verbatim from a
    # captured ground-truth export, not re-derived. Only "name-only" (h15 =
    # Name is the sole visible column) is verified; this is a closed enum by
    # design, extend it only after capturing and verifying a new preset the
    # same way, not by accepting arbitrary blobs. ``None`` (default) emits no
    # `states[]`, i.e. current/unchanged behavior (Ops falls back to its
    # built-in default column set).
    column_preset: str | None = None
    # View only:
    view_name: str = ""
    # View-widget self-provider: when true, the widget does not wait
    # for an incoming interaction and instead enumerates its subject.
    # Requires ``pin`` to a container resource kind (e.g. vSphere World)
    # whose descendants Ops walks to populate the list.
    self_provider: bool = False
    pin: WidgetResourceKindRef | None = None
    # Whether the widget auto-selects its first row and fires a
    # downstream resourceId interaction as soon as data loads. Wire
    # format: config.selectFirstRow.selectFirstRow (View and
    # ResourceList widgets). Defaults to True, the historical,
    # byte-identical-with-existing-content behavior. Set to False as a
    # strict opt-out on a *middle* tier of a picker -> intermediate view
    # -> terminal view drill chain when the intermediate view's
    # auto-select re-fires on every upstream refresh and permanently
    # pins the terminal widget to the intermediate view's first row,
    # this is what blocks a wider upstream selection (e.g. World/
    # vCenter) from ever reaching the terminal widget. See the CPU
    # Support Status v2 dashboard investigation
    # (knowledge/context/investigations/) and the vendor corpus, which
    # emits selectFirstRow:false 132 times vs true 16 times,
    # overwhelmingly the norm on multi-tier drill dashboards.
    select_first_row: bool = True
    # View only: ``config.chartViewItems`` (e.g. ``["legend"]`` to show the
    # legend on a trend view). Empty (default) is the historical output.
    chart_view_items: List[str] = field(default_factory=list)
    # Type-specific config for chart/text widgets
    scoreboard_config: ScoreboardConfig | None = None
    metric_chart_config: MetricChartConfig | None = None
    text_display_config: TextDisplayConfig | None = None
    health_chart_config: HealthChartConfig | None = None
    pareto_analysis_config: ParetoAnalysisConfig | None = None
    alert_list_config: AlertListConfig | None = None
    problems_alerts_list_config: ProblemAlertsListConfig | None = None
    heatmap_config: HeatmapConfig | None = None
    property_list_config: PropertyListConfig | None = None
    resource_relationship_advanced_config: ResourceRelationshipAdvancedConfig | None = None
    alert_volume_config: "AlertVolumeConfig | None" = None
    # Optional traversal mode for MetricChart widgets.
    # Maps to a scalar integer in config.relationshipMode (NOT an array).
    # ``None`` (default) → 0, no traversal.
    # ``"children"``     → -1, one line per child of the selected parent.
    # ``"parents"``      → 1, one line per parent of the selected child.
    # Other values are rejected at load time.
    relationship_mode: Optional[str] = None
    # Set by load_dashboard so widget UUIDs are namespaced by dashboard
    # name, otherwise two dashboards reusing the same local_id (e.g.
    # "vm_perf_view") generate identical widget UUIDs and their
    # interaction wiring collides in the rendered bundle.
    dashboard_name: str = ""

    @property
    def widget_id(self) -> str:
        return stable_id("widget", f"{self.dashboard_name}::{self.local_id}")


@dataclass
class Interaction:
    from_local_id: str
    to_local_id: str
    type: str = "resourceId"


@dataclass
class Dashboard:
    name: str
    description: str
    widgets: List[Widget]
    interactions: List[Interaction]
    # Ops dashboard folder path, lands in the Ops UI's dashboard
    # sidebar under this folder. Default is the framework folder; can
    # be overridden per-dashboard if an author has a specific reason.
    name_path: str = "VCF Content Factory"
    # Whether the dashboard is shared with other Ops users. Defaults
    # to True, a dashboard nobody else can see defeats the purpose
    # of the framework. Can be overridden per-dashboard via YAML.
    shared: bool = True
    # Whether the dashboard is hidden in the Ops sidebar by default.
    # Factory dashboards default to visible (hidden: false) so users can find
    # them without extra configuration. Pak-shipped dashboards that must be
    # hidden on import (e.g. compliance) should set hidden: true explicitly
    # in their YAML.
    hidden: bool = False
    id: str = ""
    source_path: Path | None = None
    released: bool = False   # publish gate
    version: str = "1.0.0"  # internal semver
    # Provenance: "factory", a third-party project slug, or "" (unknown).
    # Populated by the loader from source_path; never author-supplied.
    provenance: str = ""
    # Summary-tab binding targets: a normalized list of
    # "<AdapterKind>:<ResourceKind>" strings (exactly two colon-separated
    # tokens each, raw describe.xml keys, not display names). YAML may
    # give one string, a comma-separated string, or a list; the loader
    # normalizes all three to this list (see normalize_summary_for). When
    # set, this dashboard is meant to render as the object Summary tab
    # for every listed kind (the product materializes one template copy
    # per kind), which means every widget must inherit the page object:
    # no self_provider, no pinned resources (vendor guideline for summary
    # dashboards). Bound either at install time from a pak
    # (content/dashboards/dashboards.properties, comma-joined, see
    # knowledge/context/api-surface/summary_dashboard_pak_binding.md) or
    # after a content-zip import via `bind-summary` (see
    # summary_dashboard_assignment.md and vcfops_dashboards/summary_bind.py).
    #
    # Multi-kind fan-out (render-time, see render._fan_out_summary_specs):
    # the server shows only the resourceKindMetrics entries whose kind
    # matches the page object and hides the rest, with no wildcard kind.
    # So when this list has more than one kind, every Scoreboard /
    # MetricChart / PropertyList MetricSpec (self_provider false) whose
    # adapter_kind:resource_kind is one of the listed kinds is emitted
    # once per listed kind of the same adapter kind, in summary_for order.
    # A spec on an unlisted kind is author-pinned and passes through as
    # one entry. YAML stays single-entry. Not validated: a metric key that
    # does not exist on one of the listed kinds is a hidden entry on that
    # kind's page (the server drops it), not a loader error.
    summary_for: Optional[list[str]] = None

    @property
    def summary_kinds(self) -> "list[tuple[str, str]]":
        """``[(adapter_kind, resource_kind), ...]`` from ``summary_for``
        (empty when unset)."""
        if not self.summary_for:
            return []
        return [parse_summary_for(v) for v in self.summary_for]

    def validate(self, known_views: dict[str, ViewDef], enforce_framework_prefix: bool = True) -> None:
        if not self.name.strip():
            raise DashboardValidationError("dashboard: name is required")
        if self.summary_for is not None:
            try:
                normalize_summary_for(self.summary_for)
            except ValueError as exc:
                raise DashboardValidationError(f"dashboard {self.name}: {exc}") from None
            for w in self.widgets:
                if w.type == "Section":
                    continue
                pinned = (
                    w.self_provider
                    or w.pin is not None
                    or (w.alert_list_config is not None and w.alert_list_config.pin_to_world)
                    or (w.resource_relationship_advanced_config is not None
                        and w.resource_relationship_advanced_config.self_provider)
                )
                if pinned:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: summary_for dashboards "
                        f"inherit the page object, so every widget must have "
                        f"self_provider: false and no pin / pin_to_world (vendor summary "
                        f"dashboard guideline). Remove the pin and let the interaction "
                        f"wiring or the Summary page supply the resource."
                    )
        if enforce_framework_prefix and not self.name.startswith("[VCF Content Factory] "):
            src = str(self.source_path) if self.source_path else self.name
            raise DashboardValidationError(
                f'{src}: name "{self.name}" missing framework prefix '
                f'"[VCF Content Factory]". All factory-authored content must carry the literal '
                f'"[VCF Content Factory]" prefix (see CLAUDE.md §Hard rules #5). For third-party '
                f"bundle content, ensure the bundle manifest sets factory_native: false."
            )
        _supported_types = (
            "ResourceList", "View", "TextDisplay", "Scoreboard", "MetricChart",
            "HealthChart", "ParetoAnalysis", "AlertList", "ProblemAlertsList",
            "Heatmap", "PropertyList", "ResourceRelationshipAdvanced",
            "Section", "AlertVolume",
        )
        seen: set[str] = set()
        for w in self.widgets:
            if w.local_id in seen:
                raise DashboardValidationError(
                    f"dashboard {self.name}: duplicate widget id {w.local_id}"
                )
            seen.add(w.local_id)
            if w.type not in _supported_types:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"unsupported type {w.type} (supported: {', '.join(_supported_types)})"
                )
            if w.type == "ResourceList" and not w.resource_kinds:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"ResourceList requires resource_kinds"
                )
            if w.column_preset is not None and w.column_preset not in _SUPPORTED_COLUMN_PRESETS:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"unsupported column_preset {w.column_preset!r} "
                    f"(supported: {', '.join(sorted(_SUPPORTED_COLUMN_PRESETS))})"
                )
            if w.column_preset is not None and w.type != "ResourceList":
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"column_preset is only supported on ResourceList widgets"
                )
            if w.type == "View":
                if not w.view_name:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"View requires 'view' (the view definition name)"
                    )
                # External view passthrough: a raw UUID that does not match any
                # bundled view is treated as an EXTERNAL reference (a platform-
                # or other-MP-provided view resolved at install time).  Only bare
                # names that fail to match are authoring mistakes.
                if w.view_name not in known_views and not _UUID_RE.match(w.view_name):
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"unknown view '{w.view_name}'"
                    )
            if w.type == "Scoreboard" and w.scoreboard_config is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"Scoreboard requires at least one entry in 'metrics'"
                )
            if w.type == "MetricChart" and w.metric_chart_config is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"MetricChart requires at least one entry in 'metrics'"
                )
            if w.type == "TextDisplay" and w.text_display_config is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"TextDisplay requires 'text' or 'html' field"
                )
            if w.type == "HealthChart" and w.health_chart_config is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"HealthChart requires 'metric_key', 'adapter_kind', and 'resource_kind'"
                )
            if w.type == "ParetoAnalysis" and w.pareto_analysis_config is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"ParetoAnalysis requires 'metric_key', 'adapter_kind', and 'resource_kind'"
                )
            if w.type == "AlertVolume":
                if w.alert_volume_config is None:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: AlertVolume is missing its config"
                    )
                if w.self_provider and w.pin is None:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"AlertVolume with self_provider=true requires a 'pin' resource kind"
                    )
            if w.type == "ProblemAlertsList" and w.self_provider and w.pin is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"ProblemAlertsList with self_provider=true requires a 'pin' resource kind"
                )
            if w.type == "Heatmap":
                if w.heatmap_config is None or not w.heatmap_config.tabs:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"Heatmap requires at least one entry in 'configs'"
                    )
                for tab in w.heatmap_config.tabs:
                    if not tab.resource_kind:
                        raise DashboardValidationError(
                            f"dashboard {self.name}: widget {w.local_id}: "
                            f"Heatmap tab '{tab.name}' requires 'resource_kind'"
                        )
                    if not tab.color_by_key:
                        raise DashboardValidationError(
                            f"dashboard {self.name}: widget {w.local_id}: "
                            f"Heatmap tab '{tab.name}' requires 'color_by_key'"
                        )
            if w.type == "PropertyList" and (
                w.property_list_config is None or not w.property_list_config.properties
            ):
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"PropertyList requires at least one entry in 'properties'"
                )
        section_ids = {w.local_id for w in self.widgets if w.type == "Section"}
        for w in self.widgets:
            if w.type != "Section":
                continue
            if w.section_config is None:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: Section is missing its config"
                )
            if (w.resource_kinds or w.view_name or w.pin is not None or w.self_provider
                    or w.scoreboard_config or w.metric_chart_config or w.heatmap_config
                    or w.property_list_config or w.view_details is not None):
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: a Section must not "
                    f"carry metrics, views, resource kinds, pins, self_provider, or view_details"
                )
            for mid in w.section_config.member_ids:
                if mid not in seen:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: Section member "
                        f"{mid!r} is not a widget on this dashboard"
                    )
                if mid in section_ids:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: Section member "
                        f"{mid!r} is itself a Section; Sections do not nest"
                    )
        for ix in self.interactions:
            if ix.from_local_id not in seen or ix.to_local_id not in seen:
                raise DashboardValidationError(
                    f"dashboard {self.name}: interaction references unknown widget"
                )
            if ix.from_local_id in section_ids or ix.to_local_id in section_ids:
                raise DashboardValidationError(
                    f"dashboard {self.name}: interaction {ix.from_local_id} -> "
                    f"{ix.to_local_id} references a Section; Sections carry no interactions"
                )


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def parse_summary_for(value: str) -> tuple[str, str]:
    """Split ``"<AdapterKind>:<ResourceKind>"`` into its two tokens.

    Exactly two non-empty colon-separated tokens; the server-side pak
    installer silently skips anything else (``objectTypes.size() != 2``),
    so the loader fails loudly instead.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"summary_for must be a string \"<AdapterKind>:<ResourceKind>\"; "
            f"got {type(value).__name__} {value!r}"
        )
    parts = value.split(":")
    if len(parts) != 2 or not all(p.strip() for p in parts):
        raise ValueError(
            f"summary_for must be exactly \"<AdapterKind>:<ResourceKind>\" "
            f"(two non-empty colon-separated tokens); got {value!r}"
        )
    return parts[0].strip(), parts[1].strip()


def normalize_summary_for(value) -> list[str]:
    """Normalize a YAML ``summary_for`` value to a list of ``"AK:RK"``.

    Accepts one string, a comma-separated string (the same shape the pak
    installer parses from ``dashboards.properties``), or a YAML list of
    strings. Every entry is parsed with :func:`parse_summary_for` and
    re-joined with the tokens stripped (the installer splits on ``:``
    without trimming, so inner whitespace would bind nothing, silently).
    Order is preserved; a kind listed twice in one dashboard is an error.
    """
    if isinstance(value, str):
        items = [v for v in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        raise ValueError(
            f"summary_for must be a string \"<AdapterKind>:<ResourceKind>\" (or a "
            f"comma-separated string / YAML list of them); got {type(value).__name__} {value!r}"
        )
    if not items:
        raise ValueError("summary_for must list at least one \"<AdapterKind>:<ResourceKind>\"")
    out: list[str] = []
    for item in items:
        ak, rk = parse_summary_for(item)
        key = f"{ak}:{rk}"
        if key in out:
            raise ValueError(f"summary_for lists {key!r} more than once")
        out.append(key)
    return out


def check_unique_summary_for(dashboards: Iterable["Dashboard"]) -> None:
    """Reject two dashboards claiming the same ``summary_for`` kind.

    The check is per kind, not per dashboard: a resource kind has one
    Summary tab. In a pak both lines would land in ``dashboards.properties``
    and the installer's directory order would pick the winner; in
    ``bind-summary`` the second plan would overwrite the first and orphan
    its template. Fail at load instead.
    """
    owners: dict[str, "Dashboard"] = {}
    for d in dashboards:
        for kind in d.summary_for or []:
            prior = owners.get(kind)
            if prior is not None:
                raise DashboardValidationError(
                    f"summary_for {kind!r} is claimed by both dashboard "
                    f"{prior.name!r} ({prior.source_path}) and {d.name!r} ({d.source_path}); "
                    f"a resource kind has one Summary tab"
                )
            owners[kind] = d


def _mint_id_into_file(path: Path) -> str:
    """Mint a uuid4 and prepend ``id: <uuid>`` to the YAML file.

    Same contract as the super metric loader: UUIDs are generated
    once on first validate and never touched after. See
    knowledge/context/authoring/uuids_and_cross_references.md.
    """
    new_id = str(uuid.uuid4())
    original = path.read_text()
    path.write_text(f"id: {new_id}\n{original}")
    return new_id


def load_view(path: Path, enforce_framework_prefix: bool = True, embedded_in_dashboard: bool = False) -> ViewDef:
    try:
        data = _strict_load(path.read_text()) or {}
    except yaml.constructor.ConstructorError as exc:
        raise DashboardValidationError(
            f"{path}: {exc}"
        ) from exc
    view_id = str(data.get("id", "") or "").strip().lower()
    if not view_id:
        view_id = _mint_id_into_file(path)
    elif not _UUID_RE.match(view_id):
        raise DashboardValidationError(
            f"{path}: id '{view_id}' is not a valid uuid4"
        )
    def _load_column(c: dict) -> "ViewColumn":
        transform_raw = c.get("transformation")
        transform_expr = c.get("transform_expression")
        # Convenience: if transform_expression is set but transformation isn't,
        # auto-set transformation to TRANSFORM_EXPRESSION.
        if transform_expr and not transform_raw:
            transform_raw = "TRANSFORM_EXPRESSION"
        transformation = str(transform_raw).strip().upper() if transform_raw else None

        percentile_raw = c.get("percentile")
        percentile = int(percentile_raw) if percentile_raw is not None else None

        def _maybe_float(v):
            """Return float if numeric string/number, else return as-is string."""
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            try:
                return float(s)
            except ValueError:
                return s  # string-match bound (e.g. "Powered Off")

        yellow = _maybe_float(c.get("yellow_bound"))
        orange = _maybe_float(c.get("orange_bound"))
        red = _maybe_float(c.get("red_bound")) if c.get("red_bound") is not None else None
        # For string red_bound, _maybe_float returns the string itself
        if "red_bound" in c and isinstance(c["red_bound"], str):
            red = c["red_bound"].strip()

        ascending_raw = c.get("ascending_range")
        ascending = bool(ascending_raw) if ascending_raw is not None else None

        mtrw_raw = c.get("metric_to_relate_with")
        lmtrw_raw = c.get("localized_metric_to_relate_with")
        otrw_raw = c.get("operator_to_relate_with")
        metric_to_relate_with = str(mtrw_raw).strip() if mtrw_raw else None
        localized_metric_to_relate_with = str(lmtrw_raw).strip() if lmtrw_raw else None
        operator_to_relate_with = str(otrw_raw).strip().upper() if otrw_raw else None

        # Instanced-group column: `attribute` is loader-synthesized, not
        # author-supplied. See InstancedGroupSpec docstring for the wire
        # format this mirrors.
        ig_raw = c.get("instanced_group")
        instanced_group: Optional[InstancedGroupSpec] = None
        attribute_raw = c.get("attribute")
        # Time-segment column: `attribute` is the literal "Interval
        # Breakdown", synthesized here. See TimeSegmentSpec.
        ts_raw = c.get("time_segment")
        time_segment: Optional[TimeSegmentSpec] = None
        if ts_raw is not None:
            if not isinstance(ts_raw, dict):
                raise DashboardValidationError(
                    "view column: time_segment must be a mapping "
                    f"(breakdown_by, starting_on_unit, starting_on_count), got {ts_raw!r}."
                )
            if attribute_raw:
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: time_segment columns must "
                    "not also set `attribute`; the attributeKey is always the literal "
                    "'Interval Breakdown' and is synthesized by the loader."
                )
            if ig_raw is not None:
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: time_segment and "
                    "instanced_group are mutually exclusive."
                )
            bb = str(ts_raw.get("breakdown_by", "") or "").strip().upper()
            if not bb:
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: time_segment.breakdown_by "
                    "is required (e.g. MONTHS)."
                )
            sou = str(ts_raw.get("starting_on_unit", "WEEKS") or "WEEKS").strip().upper()
            soc_raw = ts_raw.get("starting_on_count", 1)
            if isinstance(soc_raw, bool) or not isinstance(soc_raw, int):
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: time_segment.starting_on_count "
                    f"must be an integer; got {soc_raw!r}"
                )
            time_segment = TimeSegmentSpec(
                breakdown_by=bb, starting_on_unit=sou, starting_on_count=soc_raw,
            )
            attribute_raw = "Interval Breakdown"
        if ig_raw is not None:
            if not isinstance(ig_raw, dict):
                raise DashboardValidationError(
                    "view column: instanced_group must be a mapping "
                    f"(name, prefix, suffix, sample_instance, ...), got {ig_raw!r}."
                )
            if attribute_raw:
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: instanced_group columns "
                    "must not also set `attribute`, the attributeKey is synthesized "
                    "by the loader (driver -> 'Instance Name'; member -> "
                    "'{prefix}:{sample_instance}|{suffix}'). Setting `attribute` "
                    "here would hardcode a single instance and defeat the "
                    "one-row-per-instance expansion. Use `prefix`/`suffix`/"
                    "`sample_instance` on the instanced_group block instead."
                )
            ig_name = str(ig_raw.get("name", "") or "").strip()
            if not ig_name:
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: instanced_group.name is required."
                )
            ig_prefix = ig_raw.get("prefix")
            ig_suffix = ig_raw.get("suffix")
            ig_prefix = str(ig_prefix).strip() if ig_prefix else None
            ig_suffix = str(ig_suffix).strip() if ig_suffix else None
            if bool(ig_prefix) != bool(ig_suffix):
                raise DashboardValidationError(
                    f"view column {c.get('display_name')!r}: instanced_group.prefix and "
                    "instanced_group.suffix must both be set (member column) or both "
                    "unset (driver column)."
                )
            ig_sample = ig_raw.get("sample_instance")
            ig_sample = str(ig_sample).strip() if ig_sample else None
            instanced_group = InstancedGroupSpec(
                name=ig_name,
                prefix=ig_prefix,
                suffix=ig_suffix,
                sample_instance=ig_sample,
                show_instance_name=bool(ig_raw.get("show_instance_name", True)),
                keep_instance_summary=bool(ig_raw.get("keep_instance_summary", False)),
            )
            if instanced_group.is_driver:
                attribute = "Instance Name"
            else:
                if not instanced_group.sample_instance:
                    raise DashboardValidationError(
                        f"view column {c.get('display_name')!r}: instanced_group member "
                        "columns require sample_instance (a representative instance name "
                        "embedded in the synthesized attributeKey; see InstancedGroupSpec "
                        "docstring, the factory does not guess this value)."
                    )
                attribute = f"{instanced_group.prefix}:{instanced_group.sample_instance}|{instanced_group.suffix}"
        else:
            attribute = str(attribute_raw or "").strip()

        return ViewColumn(
            attribute=attribute,
            display_name=str(c["display_name"]).strip(),
            unit=str(c.get("unit", "") or "").strip(),
            transformation=transformation,
            percentile=percentile,
            transform_expression=str(transform_expr).strip() if transform_expr else None,
            metric_to_relate_with=metric_to_relate_with,
            localized_metric_to_relate_with=localized_metric_to_relate_with,
            operator_to_relate_with=operator_to_relate_with,
            yellow_bound=yellow,
            orange_bound=orange,
            red_bound=red,
            ascending_range=ascending,
            is_property=bool(c.get("is_property", False)),
            is_string_attribute=bool(c.get("is_string_attribute", False)),
            instanced_group=instanced_group,
            time_segment=time_segment,
        )

    cols = [_load_column(c) for c in (data.get("columns") or [])]
    subj = data.get("subject") or {}
    if not isinstance(subj, dict):
        raise DashboardValidationError(f"{path}: subject must be a mapping")

    # subjects: N (adapter_kind, resource_kind) pairs, one SubjectType pair
    # each, in authored order. Mutually exclusive with the scalar
    # subject.adapter_kind / subject.resource_kind (subject.filter may
    # still accompany it; the filter applies to every SubjectType).
    subjects_raw = data.get("subjects")
    view_subjects: List[ViewSubject] = []
    if subjects_raw is not None:
        if not isinstance(subjects_raw, list) or not subjects_raw:
            raise DashboardValidationError(
                f"{path}: subjects must be a non-empty list of "
                f"{{adapter_kind, resource_kind}} mappings"
            )
        if subj.get("adapter_kind") or subj.get("resource_kind"):
            raise DashboardValidationError(
                f"{path}: subjects and subject.adapter_kind/resource_kind are mutually "
                f"exclusive; declare the kinds in one place"
            )
        for entry in subjects_raw:
            if not isinstance(entry, dict):
                raise DashboardValidationError(
                    f"{path}: subjects entry must be a mapping, got {entry!r}"
                )
            unknown = set(entry) - {"adapter_kind", "resource_kind"}
            if unknown:
                raise DashboardValidationError(
                    f"{path}: subjects entry has unknown key(s) {sorted(unknown)}"
                )
            view_subjects.append(ViewSubject(
                adapter_kind=str(entry.get("adapter_kind", "") or "").strip(),
                resource_kind=str(entry.get("resource_kind", "") or "").strip(),
            ))
    if view_subjects:
        subject_adapter_kind = view_subjects[0].adapter_kind
        subject_resource_kind = view_subjects[0].resource_kind
    else:
        subject_adapter_kind = str(subj.get("adapter_kind", "")).strip()
        subject_resource_kind = str(subj.get("resource_kind", "")).strip()

    def _load_filter_condition(raw: dict) -> "SubjectFilterCondition":
        if not isinstance(raw, dict):
            raise DashboardValidationError(
                f"{path}: subject.filter condition must be a mapping, got {raw!r}"
            )

        # Coerce-before-validate ordering bug (Codex P2, PR #47): the loader
        # must NOT type-coerce a field into a value that happens to already
        # be valid before SubjectFilterCondition.validate() gets a chance to
        # reject the wrong type. `bool(raw["business_hours"])` was the
        # concrete instance, bool() of ANY truthy value (including the
        # string "false") is True, so a quoted `business_hours: "false"`
        # silently became `True` instead of failing validation, and the
        # renderer emitted `"businessHours":true`. Fixed by passing raw
        # values straight through (preserving their original type) and
        # letting `validate()` do the sole type check.
        #
        # For the string-typed fields (filter_type/metric_key/condition/
        # transform) the same failure *shape* (str(x) coincidentally
        # equalling a valid enum token) cannot happen for any YAML-typed
        # value, but a non-str input was still being silently stringified
        # here rather than reported with a clear type error, fixed the
        # same way: reject non-str values at load time instead of masking
        # them via str().
        def _str_field(key: str, upper: bool = False) -> str:
            v = raw.get(key)
            if v is None:
                return ""
            if not isinstance(v, str):
                raise DashboardValidationError(
                    f"{path}: subject.filter.{key} must be a string; got "
                    f"{type(v).__name__} ({v!r})"
                )
            v = v.strip()
            return v.upper() if upper else v

        transform = None
        if "transform" in raw and raw.get("transform") is not None:
            transform = _str_field("transform", upper=True) or None

        business_hours = None
        if "business_hours" in raw and raw.get("business_hours") is not None:
            business_hours = raw["business_hours"]  # type preserved; validate() rejects non-bool

        return SubjectFilterCondition(
            filter_type=_str_field("filter_type"),
            metric_key=_str_field("metric_key"),
            condition=_str_field("condition", upper=True),
            value=raw.get("value"),
            transform=transform,
            business_hours=business_hours,
        )

    # subject.filter, flat list of condition mappings (single implicit AND
    # group) or a nested list-of-lists (explicit OR-of-AND groups), mirroring
    # the vendor JSON shape 1:1. See SubjectFilterCondition docstring.
    subject_filter: Optional[List[List["SubjectFilterCondition"]]] = None
    sf_raw = subj.get("filter")
    if sf_raw is not None:
        if not isinstance(sf_raw, list) or not sf_raw:
            raise DashboardValidationError(
                f"{path}: subject.filter must be a non-empty list"
            )
        if isinstance(sf_raw[0], list):
            # Explicit OR-of-AND groups.
            subject_filter = [
                [_load_filter_condition(c) for c in group]
                for group in sf_raw
            ]
        else:
            # Flat list -> single AND group.
            subject_filter = [[_load_filter_condition(c) for c in sf_raw]]

    summary_raw = data.get("summary")
    summary = None
    if summary_raw is True:
        summary = SummaryRow()
    elif isinstance(summary_raw, dict):
        col_idx = summary_raw.get("columns")
        summary = SummaryRow(
            display_name=str(summary_raw.get("display_name", "Summary")).strip(),
            aggregation=str(summary_raw.get("aggregation", "SUM")).strip().upper(),
            column_indexes=col_idx,
        )

    # data_type and presentation, defaults depend on each other
    data_type = str(data.get("data_type", "list") or "list").strip().lower()
    # Derive default presentation from data_type when not explicitly set
    _default_presentation = {
        "list": "list",
        "distribution": "bar-chart",
        "trend": "line-chart",
    }
    presentation_raw = data.get("presentation")
    if presentation_raw is None:
        presentation = _default_presentation.get(data_type, "list")
    else:
        presentation = str(presentation_raw).strip().lower()

    # Buckets config for distribution views
    buckets = None
    buckets_raw = data.get("buckets")
    if buckets_raw is not None:
        if isinstance(buckets_raw, dict):
            buckets = BucketsConfig(
                count=int(buckets_raw.get("count", 10)),
                min_value=float(buckets_raw.get("min_value", 0.0)),
                max_value=float(buckets_raw.get("max_value", 100.0)),
                is_dynamic=bool(buckets_raw.get("dynamic", False)),
                calc_function=str(buckets_raw.get("calc_function", "DISCRETE")).strip().upper(),
            )
    elif data_type == "distribution":
        # Apply sensible defaults when distribution view has no explicit buckets
        buckets = BucketsConfig()

    # Trend-view fields
    forecast_days = int(data.get("forecast_days", 0) or 0)
    transformations_raw = data.get("transformations")
    transformations = None
    if transformations_raw is not None:
        transformations = [str(t).strip().upper() for t in (transformations_raw or [])]

    # View-level time window (time-interval-selector)
    time_window = None
    tw_raw = data.get("time_window")
    if tw_raw is not None and isinstance(tw_raw, dict):
        tw_unit = str(tw_raw.get("unit", "")).strip().upper()
        tw_count = int(tw_raw.get("count", 0))
        tw_adv = bool(tw_raw.get("advanced_time_mode", False))
        tw_start_raw = tw_raw.get("start_period")
        tw_end_raw = tw_raw.get("end_period")
        tw_start = str(tw_start_raw).strip().upper() if tw_start_raw else None
        tw_end = str(tw_end_raw).strip().upper() if tw_end_raw else None
        time_window = ViewTimeWindow(
            unit=tw_unit,
            count=tw_count,
            advanced_time_mode=tw_adv,
            start_period=tw_start,
            end_period=tw_end,
        )

    released_raw = data.get("released", False)
    released = bool(released_raw) if isinstance(released_raw, bool) else False
    version = str(data.get("version", "1.0.0") or "1.0.0").strip() or "1.0.0"

    # customgroup: str | list[str], names of custom groups this view is scoped to.
    cg_raw = data.get("customgroup")
    if cg_raw is None:
        view_customgroups: List[str] = []
    elif isinstance(cg_raw, str):
        view_customgroups = [cg_raw.strip()] if cg_raw.strip() else []
    elif isinstance(cg_raw, list):
        view_customgroups = [str(x).strip() for x in cg_raw if str(x).strip()]
    else:
        view_customgroups = []

    from vcfops_common.provenance import provenance_from_path

    v = ViewDef(
        id=view_id,
        name=str(data.get("name", "")).strip(),
        description=str(data.get("description", "") or "").strip(),
        adapter_kind=subject_adapter_kind,
        resource_kind=subject_resource_kind,
        columns=cols,
        source_path=path,
        subject_filter=subject_filter,
        subjects=view_subjects,
        summary=summary,
        data_type=data_type,
        presentation=presentation,
        buckets=buckets,
        forecast_days=forecast_days,
        transformations=transformations,
        time_window=time_window,
        hide_object_name=bool(data.get("hide_object_name", False)),
        released=released,
        version=version,
        customgroups=view_customgroups,
        provenance=provenance_from_path(path),
    )
    v.validate(enforce_framework_prefix=enforce_framework_prefix, embedded_in_dashboard=embedded_in_dashboard)
    return v


def load_dashboard(path: Path, enforce_framework_prefix: bool = True, default_name_path: str = "VCF Content Factory") -> Dashboard:
    try:
        data = _strict_load(path.read_text()) or {}
    except yaml.constructor.ConstructorError as exc:
        raise DashboardValidationError(
            f"{path}: {exc}"
        ) from exc
    dash_id = str(data.get("id", "") or "").strip().lower()
    if not dash_id:
        dash_id = _mint_id_into_file(path)
    elif not _UUID_RE.match(dash_id):
        raise DashboardValidationError(
            f"{path}: id '{dash_id}' is not a valid uuid4"
        )
    widgets: List[Widget] = []
    for w in data.get("widgets", []) or []:
        rks = [
            WidgetResourceKindRef(
                adapter_kind=str(rk["adapter_kind"]).strip(),
                resource_kind=str(rk["resource_kind"]).strip(),
            )
            for rk in (w.get("resource_kinds") or [])
        ]
        pin_raw = w.get("pin")
        pin = None
        if pin_raw:
            pin_name_raw = pin_raw.get("name", "")
            if pin_name_raw is not None and not isinstance(pin_name_raw, str):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: pin.name must be a string (the "
                    f"container resource's display name); got {pin_name_raw!r}"
                )
            pin_ak = str(pin_raw["adapter_kind"]).strip()
            pin_rk = str(pin_raw["resource_kind"]).strip()
            pin_name = str(pin_name_raw or "").strip()
            if pin_name:
                # Local import: render.py owns the leaf-kind redirect table
                # and imports nothing from this module at import time, but
                # keep the dependency one-directional at module load.
                from vcfops_dashboards.render import _VIEW_PIN_CONTAINER
                if (pin_ak, pin_rk) in _VIEW_PIN_CONTAINER:
                    raise DashboardValidationError(
                        f"widget {w.get('id', '?')!r}: pin.name is not supported on "
                        f"leaf kind {pin_ak}/{pin_rk}: pinning a single leaf resource by "
                        f"name is not live-verified (only world-singleton pins by display "
                        f"name are), see knowledge/context/wire-formats/"
                        f"dashboard_view_pin_resolution.md. Drop pin.name to pin the "
                        f"{_VIEW_PIN_CONTAINER[(pin_ak, pin_rk)][1]!r} container instead."
                    )
            pin = WidgetResourceKindRef(
                adapter_kind=pin_ak,
                resource_kind=pin_rk,
                name=pin_name,
            )
        widget_type = str(w["type"]).strip()

        select_first_row_raw = w.get("select_first_row", True)
        if not isinstance(select_first_row_raw, bool):
            raise DashboardValidationError(
                f"widget '{w.get('id', '')}': select_first_row must be a bool "
                f"(unquoted true/false in YAML); got {type(select_first_row_raw).__name__} "
                f"{select_first_row_raw!r}"
            )
        cvi_raw = w.get("chart_view_items")
        chart_view_items: List[str] = []
        if cvi_raw is not None:
            if widget_type != "View":
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: chart_view_items is only valid on View widgets"
                )
            if not isinstance(cvi_raw, list) or not all(isinstance(x, str) and x.strip() for x in cvi_raw):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: chart_view_items must be a list of "
                    f"non-empty strings (e.g. [legend]); got {cvi_raw!r}"
                )
            chart_view_items = [x.strip() for x in cvi_raw]

        # --- Parse view_details (any widget) ---
        view_details_raw = w.get("view_details")
        if view_details_raw is not None:
            if not isinstance(view_details_raw, str):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: view_details must be a string; "
                    f"got {type(view_details_raw).__name__} {view_details_raw!r}"
                )
            view_details_raw = view_details_raw.strip()
            if view_details_raw and not view_details_raw.startswith(_VIEW_DETAILS_PREFIXES):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: view_details {view_details_raw!r} must "
                    f"start with one of {list(_VIEW_DETAILS_PREFIXES)} (absolute URL, or a "
                    f"relative Angular route such as "
                    f"/ui/operate/dashboards/dashboards;tabId=<uuid>); the product hands "
                    f"anything else to its router verbatim and it does not resolve. "
                    f"No placeholder expansion exists, links are static."
                )

        # --- Parse AlertVolume config ---
        alert_volume_config = None
        if widget_type == "AlertVolume":
            bad = [k for k in _ALERT_VOLUME_FORBIDDEN_KEYS if k in w]
            if bad:
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: AlertVolume does not support "
                    f"{', '.join(bad)}: the widget hard-codes a 7-day window and shows "
                    f"every criticality; its config is only title, refresh_content, "
                    f"refresh_interval, self_provider and pin"
                )
            rc_raw = w.get("refresh_content", False)
            if not isinstance(rc_raw, bool):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: refresh_content must be a bool; "
                    f"got {type(rc_raw).__name__} {rc_raw!r}"
                )
            alert_volume_config = AlertVolumeConfig(
                refresh_content=rc_raw,
                refresh_interval=int(w.get("refresh_interval", 300)),
            )

        # --- Parse Section config ---
        section_config = None
        if widget_type == "Section":
            bad = [k for k in _SECTION_FORBIDDEN_KEYS if k in w]
            if bad:
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: Section must not carry "
                    f"{', '.join(bad)} (a Section is a row header with no data)"
                )
            collapsed_raw = w.get("collapsed", False)
            if not isinstance(collapsed_raw, bool):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: collapsed must be a bool "
                    f"(unquoted true/false in YAML); got {type(collapsed_raw).__name__} "
                    f"{collapsed_raw!r}"
                )
            members_raw = w.get("widgets")
            if members_raw is not None and not isinstance(members_raw, list):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: Section widgets must be a list of widget ids"
                )
            section_config = SectionConfig(
                collapsed=collapsed_raw,
                member_ids=[str(m).strip() for m in (members_raw or [])],
                explicit_members=members_raw is not None,
            )
            # A Section spans the whole 12-column row; any other x would
            # overflow the grid once w is forced to 12. Only y is authored.
            sec_x = (w.get("coords") or {}).get("x", 1)
            if sec_x != 1:
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: a Section is full width and starts at "
                    f"x: 1 (got x: {sec_x!r}); author only coords.y"
                )
        elif "collapsed" in w or "widgets" in w:
            raise DashboardValidationError(
                f"widget {w.get('id', '?')!r}: collapsed / widgets are only "
                f"supported on Section widgets, got type {widget_type!r}"
            )

        # --- Parse TextDisplay config ---
        text_display_config = None
        if widget_type == "TextDisplay":
            html_content = str(w.get("html") or w.get("text") or "<br>").strip()
            text_display_config = TextDisplayConfig(html=html_content)

        # --- Parse metric specs helper (shared by Scoreboard, MetricChart, PropertyList) ---
        def _parse_metric_specs(raw_metrics: list) -> List[MetricSpec]:
            specs = []
            for m in (raw_metrics or []):
                color_method_raw = m.get("color_method", 2)
                try:
                    color_method = int(color_method_raw)
                except (TypeError, ValueError):
                    color_method = 2
                yellow = m.get("yellow_bound")
                orange = m.get("orange_bound")
                red = m.get("red_bound")
                if color_method == 0:
                    # All three or none: a partial set makes the server
                    # answer "?" / Unknown for the tile (see MetricSpec).
                    missing = [
                        name for name, val in (
                            ("yellow_bound", yellow),
                            ("orange_bound", orange),
                            ("red_bound", red),
                        ) if val is None
                    ]
                    if 0 < len(missing) < 3:
                        raise DashboardValidationError(
                            f"widget {w.get('id', '?')!r}: metric "
                            f"{m.get('metric_key', '?')!r}: color_method 0 "
                            f"needs all three bounds or none; missing "
                            f"{', '.join(missing)}. A partial set renders "
                            f"the tile as '?' / Unknown on the server."
                        )
                elif color_method == 3:
                    # The renderer nulls every bound for any method other
                    # than 0, so bounds on 3 would silently vanish and the
                    # author would get an uncolored tile (see MetricSpec).
                    supplied = [
                        name for name, val in (
                            ("yellow_bound", yellow),
                            ("orange_bound", orange),
                            ("red_bound", red),
                        ) if val is not None
                    ]
                    if supplied:
                        raise DashboardValidationError(
                            f"widget {w.get('id', '?')!r}: metric "
                            f"{m.get('metric_key', '?')!r}: color_method 3 "
                            f"(percent-of-max thresholds) is not emitted by "
                            f"the factory; the renderer drops "
                            f"{', '.join(supplied)}. Use color_method 0 "
                            f"with absolute bounds."
                        )
                max_value_raw = m.get("max_value")
                if max_value_raw is not None:
                    if isinstance(max_value_raw, bool) or not isinstance(max_value_raw, (int, float)):
                        raise DashboardValidationError(
                            f"widget {w.get('id', '?')!r}: metric "
                            f"{m.get('metric_key', '?')!r}: max_value must be a number; "
                            f"got {type(max_value_raw).__name__} {max_value_raw!r}"
                        )
                specs.append(MetricSpec(
                    adapter_kind=str(m.get("adapter_kind", "")).strip(),
                    resource_kind=str(m.get("resource_kind", "")).strip(),
                    metric_key=str(m.get("metric_key", "")).strip(),
                    metric_name=str(m.get("metric_name", m.get("metric_key", ""))).strip(),
                    unit_id=str(m.get("unit_id", "") or "").strip(),
                    unit=str(m.get("unit", "") or "").strip(),
                    color_method=color_method,
                    yellow_bound=float(yellow) if yellow is not None else None,
                    orange_bound=float(orange) if orange is not None else None,
                    red_bound=float(red) if red is not None else None,
                    label=str(m.get("label", "") or "").strip(),
                    is_string_metric=bool(m.get("is_string_metric", False)),
                    max_value=float(max_value_raw) if max_value_raw is not None else None,
                ))
            return specs

        # --- Parse Scoreboard config ---
        scoreboard_config = None
        if widget_type == "Scoreboard":
            raw_metrics = w.get("metrics") or []
            metric_mode = str(w.get("metric_mode", "resourceKind") or "resourceKind").strip()
            if metric_mode not in _VALID_SCOREBOARD_METRIC_MODES:
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: Scoreboard metric_mode must be one of "
                    f"{sorted(_VALID_SCOREBOARD_METRIC_MODES)}; got {metric_mode!r}"
                )
            sb_resource = None
            res_raw = w.get("resource")
            if metric_mode == "resource":
                if not bool(w.get("self_provider", False)):
                    # The only wire evidence (wire_formats.md, Scoreboard
                    # resource mode) has selfProvider: true; a non-self-
                    # provider resourceMetrics[] widget is an unverified
                    # shape, so refuse it rather than emit it.
                    raise DashboardValidationError(
                        f"widget {w.get('id', '?')!r}: Scoreboard metric_mode: resource "
                        "requires self_provider: true (the pinned resource is the "
                        "widget's own provider; a non-self-provider resource-mode "
                        "Scoreboard has no wire evidence yet)"
                    )
                if not isinstance(res_raw, dict):
                    raise DashboardValidationError(
                        f"widget {w.get('id', '?')!r}: Scoreboard metric_mode: resource "
                        "requires a resource: {adapter_kind, resource_kind, name} block "
                        "naming the one resource every metric is pinned to"
                    )
                missing = [k for k in ("adapter_kind", "resource_kind", "name")
                           if not str(res_raw.get(k, "") or "").strip()]
                if missing:
                    raise DashboardValidationError(
                        f"widget {w.get('id', '?')!r}: Scoreboard resource block is missing "
                        f"{', '.join(missing)}; name is the resource's display name on the "
                        "target instance (e.g. 'License Usage')"
                    )
                sb_resource = WidgetResourceRef(
                    adapter_kind=str(res_raw["adapter_kind"]).strip(),
                    resource_kind=str(res_raw["resource_kind"]).strip(),
                    name=str(res_raw["name"]).strip(),
                )
                # In resource mode every metric lives on the pinned
                # resource; adapter_kind/resource_kind default to it and
                # may not disagree with it.
                filled = []
                for m in raw_metrics:
                    m = dict(m)
                    m.setdefault("adapter_kind", sb_resource.adapter_kind)
                    m.setdefault("resource_kind", sb_resource.resource_kind)
                    if (str(m["adapter_kind"]).strip(), str(m["resource_kind"]).strip()) != (
                        sb_resource.adapter_kind, sb_resource.resource_kind
                    ):
                        raise DashboardValidationError(
                            f"widget {w.get('id', '?')!r}: metric "
                            f"{m.get('metric_key', '?')!r} names kind "
                            f"{m['adapter_kind']}/{m['resource_kind']} but metric_mode: "
                            f"resource pins every metric to the widget's resource "
                            f"({sb_resource.adapter_kind}/{sb_resource.resource_kind})"
                        )
                    filled.append(m)
                raw_metrics = filled
            elif res_raw is not None:
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: Scoreboard resource: block is only "
                    "valid with metric_mode: resource"
                )
            specs = _parse_metric_specs(raw_metrics)
            scoreboard_config = ScoreboardConfig(
                metrics=specs,
                metric_mode=metric_mode,
                resource=sb_resource,
                visual_theme=int(w.get("visual_theme", 8)),
                show_sparkline=bool(w.get("show_sparkline", False)),
                period_length=w.get("period_length") or None,
                show_resource_name=bool(w.get("show_resource_name", False)),
                show_metric_name=bool(w.get("show_metric_name", True)),
                show_metric_unit=bool(w.get("show_metric_unit", True)),
                box_columns=int(w.get("box_columns", 4)),
                box_height=float(w["box_height"]) if w.get("box_height") is not None else None,
                value_size=int(w.get("value_size", 24)),
                label_size=int(w.get("label_size", 12)),
                # An explicit `round_decimals: null` is a real wire value
                # (roundDecimals: null, the widget's own "no rounding"
                # setting); only an ABSENT key falls back to 1.
                round_decimals=(
                    (float(w["round_decimals"]) if w["round_decimals"] is not None else None)
                    if "round_decimals" in w else 1
                ),
                max_cell_count=int(w.get("max_cell_count", 100)),
                layout_mode=str(w.get("layout_mode", "fixedView") or "fixedView").strip(),
                show_remaining=bool(w.get("show_remaining", False)),
                show_percent_text=bool(w.get("show_percent_text", False)),
                focus_on_percent=bool(w.get("focus_on_percent", False)),
                show_dt=bool(w.get("show_dt", False)),
                refresh_content=bool(w.get("refresh_content", True)),
            )
            if not (1 <= scoreboard_config.visual_theme <= 9):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: Scoreboard visual_theme must be 1..9 "
                    f"(9 = Gauge); got {scoreboard_config.visual_theme}"
                )
            if scoreboard_config.layout_mode not in _VALID_SCOREBOARD_LAYOUT_MODES:
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: Scoreboard layout_mode must be one of "
                    f"{sorted(_VALID_SCOREBOARD_LAYOUT_MODES)}; got {scoreboard_config.layout_mode!r}"
                )

        # --- Parse MetricChart config ---
        metric_chart_config = None
        if widget_type == "MetricChart":
            raw_metrics = w.get("metrics") or []
            specs = _parse_metric_specs(raw_metrics)
            metric_chart_config = MetricChartConfig(metrics=specs)

        # --- Parse relationship_mode (MetricChart only for now) ---
        raw_rm = w.get("relationship_mode")
        if raw_rm is not None:
            rm_str = str(raw_rm).strip().lower()
            if rm_str not in ("children", "parents"):
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: relationship_mode must be "
                    f"'children', 'parents', or omitted, got {raw_rm!r}"
                )
            if widget_type != "MetricChart":
                raise DashboardValidationError(
                    f"widget {w.get('id', '?')!r}: relationship_mode is only "
                    f"supported on MetricChart widgets, got type {widget_type!r}"
                )
            relationship_mode: Optional[str] = rm_str
        else:
            relationship_mode = None

        # --- Parse HealthChart config ---
        health_chart_config = None
        if widget_type == "HealthChart":
            mk = str(w.get("metric_key", "") or "").strip()
            rk = str(w.get("resource_kind", "") or "").strip()
            ak = str(w.get("adapter_kind", "VMWARE") or "VMWARE").strip()
            mn = str(w.get("metric_name", mk) or mk).strip()
            mfn = str(w.get("metric_full_name", mn) or mn).strip()
            health_chart_config = HealthChartConfig(
                adapter_kind=ak,
                resource_kind=rk,
                metric_key=mk,
                metric_name=mn,
                metric_full_name=mfn,
                mode=str(w.get("mode", "all") or "all").strip(),
                depth=int(w.get("depth", 1)),
                chart_height=int(w.get("chart_height", 135)),
                pagination_number=int(w.get("pagination_number", 15)),
                sort_by_dir=str(w.get("sort_by_dir", "asc") or "asc").strip(),
                yellow_bound=float(w["yellow_bound"]) if w.get("yellow_bound") is not None else -2,
                orange_bound=float(w["orange_bound"]) if w.get("orange_bound") is not None else -2,
                red_bound=float(w["red_bound"]) if w.get("red_bound") is not None else -2,
                show_resource_name=bool(w.get("show_resource_name", True)),
            )

        # --- Parse AlertList config ---
        alert_list_config = None
        if widget_type == "AlertList":
            raw_criticality = w.get("criticality")
            if raw_criticality is None:
                criticality = [2, 3, 4]
            else:
                criticality = [int(c) for c in raw_criticality]
            raw_types = w.get("alert_types") or w.get("type_codes") or []
            raw_alert_defs = w.get("alert_definitions") or []
            if not isinstance(raw_alert_defs, list):
                raise ValueError(
                    f"Widget '{w.get('title', '?')}': alert_definitions must be a list, "
                    f"got {type(raw_alert_defs).__name__}"
                )
            for i, entry in enumerate(raw_alert_defs):
                if not isinstance(entry, str):
                    raise ValueError(
                        f"Widget '{w.get('title', '?')}': alert_definitions[{i}] must be "
                        f"a string (alert definition id), got {type(entry).__name__}"
                    )
            alert_list_config = AlertListConfig(
                criticality=criticality,
                alert_types=[str(t).strip() for t in raw_types],
                status=[int(s) for s in (w.get("status") or [])],
                state=list(w.get("state") or []),
                alert_impact=[str(a).strip() for a in (w.get("alert_impact") or [])],
                alert_action=list(w.get("alert_action") or []),
                mode=str(w.get("mode", "all") or "all").strip(),
                depth=int(w.get("depth", 1)),
                alert_definitions=list(raw_alert_defs),
                pin_to_world=bool(w.get("pin_to_world", False)),
            )

        # --- Parse ProblemAlertsList config ---
        problems_alerts_list_config = None
        if widget_type == "ProblemAlertsList":
            problems_alerts_list_config = ProblemAlertsListConfig(
                impacted_badge=str(w.get("impacted_badge", "health") or "health").strip(),
                triggered_object=str(w.get("triggered_object", "children") or "children").strip(),
                top_issues_limit=int(w.get("top_issues_limit", 0) or 0),
            )

        # --- Parse Heatmap config ---
        heatmap_config = None
        if widget_type == "Heatmap":
            mode = str(w.get("mode", "all") or "all").strip()
            depth = int(w.get("depth", 10))
            tabs: list = []
            for raw_tab in (w.get("configs") or []):
                # Color threshold: author specifies values + colors arrays, or
                # min_value/max_value scalars. Full form or shorthand accepted.
                raw_color = raw_tab.get("color") or {}
                raw_thresholds = raw_color.get("thresholds") or {}
                color = HeatmapColorThreshold(
                    min_value=float(raw_color.get("min_value", raw_color.get("minValue", 0))),
                    max_value=(
                        float(_mv)
                        if (_mv := raw_color.get("max_value", raw_color.get("maxValue"))) is not None
                        else None
                    ),
                    values=list(raw_thresholds.get("values", [0, 50, 100])),
                    colors=list(raw_thresholds.get("colors", ["#74B43B", "#ECC33E", "#DE3F30"])),
                )
                # colorBy and sizeBy: simple {key, label} maps
                raw_cb = raw_tab.get("color_by") or raw_tab.get("colorBy") or {}
                color_by_key = str(raw_cb.get("metric_key", raw_cb.get("metricKey", ""))).strip()
                color_by_label = str(raw_cb.get("label", raw_cb.get("value", color_by_key))).strip()
                raw_sb = raw_tab.get("size_by") or raw_tab.get("sizeBy") or {}
                size_by_key_raw = raw_sb.get("metric_key", raw_sb.get("metricKey"))
                size_by_key = str(size_by_key_raw).strip() if size_by_key_raw is not None else None
                size_by_label = str(raw_sb.get("label", raw_sb.get("value", "")) or "").strip()
                # groupBy: what parent resource kind to group cells by
                raw_gb = raw_tab.get("group_by") or raw_tab.get("groupBy") or {}
                group_by_kind = str(raw_gb.get("resource_kind", raw_gb.get("resourceKind", "")) or "").strip()
                group_by_adapter = str(raw_gb.get("adapter_kind", raw_gb.get("adapterKind", "")) or "").strip()
                group_by_text = str(raw_gb.get("text", "") or "").strip()
                tab_ak = str(raw_tab.get("adapter_kind", w.get("adapter_kind", "VMWARE")) or "VMWARE").strip()
                tabs.append(HeatmapTab(
                    name=str(raw_tab.get("name", "")).strip(),
                    adapter_kind=tab_ak,
                    resource_kind=str(raw_tab.get("resource_kind", raw_tab.get("resourceKind", "")) or "").strip(),
                    color_by_key=color_by_key,
                    color_by_label=color_by_label,
                    size_by_key=size_by_key,
                    size_by_label=size_by_label,
                    group_by_adapter=group_by_adapter or tab_ak,
                    group_by_kind=group_by_kind,
                    group_by_text=group_by_text,
                    color=color,
                    solid_coloring=bool(raw_tab.get("solid_coloring", raw_tab.get("solidColoring", False))),
                    focus_on_groups=bool(raw_tab.get("focus_on_groups", raw_tab.get("focusOnGroups", True))),
                ))
            heatmap_config = HeatmapConfig(tabs=tabs, mode=mode, depth=depth)

        # --- Parse PropertyList config ---
        property_list_config = None
        if widget_type == "PropertyList":
            raw_pl = w.get("property_list") or {}
            raw_properties = raw_pl.get("properties") or []
            props = _parse_metric_specs(raw_properties)
            property_list_config = PropertyListConfig(
                properties=props,
                visual_theme=int(raw_pl.get("visual_theme", 0)),
                depth=int(raw_pl.get("depth", 1)),
                show_metric_full_name=bool(raw_pl.get("show_metric_full_name", True)),
            )

        # --- Parse ResourceRelationshipAdvanced config ---
        resource_relationship_advanced_config = None
        if widget_type == "ResourceRelationshipAdvanced":
            raw_rra = w.get("resource_relationship_advanced") or {}
            rra_rks_raw = raw_rra.get("resource_kinds") or []
            rra_rks = [
                WidgetResourceKindRef(
                    adapter_kind=str(rk["adapter_kind"]).strip(),
                    resource_kind=str(rk["resource_kind"]).strip(),
                )
                for rk in rra_rks_raw
            ]
            resource_relationship_advanced_config = ResourceRelationshipAdvancedConfig(
                resource_kinds=rra_rks,
                depth=str(raw_rra.get("depth", "2,1")).strip(),
                pagination_number=int(raw_rra.get("pagination_number", 5)),
                self_provider=bool(raw_rra.get("self_provider", False)),
            )

        # --- Parse ParetoAnalysis config ---
        pareto_analysis_config = None
        if widget_type == "ParetoAnalysis":
            mk = str(w.get("metric_key", "") or "").strip()
            rk = str(w.get("resource_kind", "") or "").strip()
            ak = str(w.get("adapter_kind", "VMWARE") or "VMWARE").strip()
            mn = str(w.get("metric_name", mk) or mk).strip()
            # bottom_n > 0 means show lowest, which maps to metricsLowestUtilization
            bottom_n = int(w.get("bottom_n", 0))
            top_n = int(w.get("top_n", 10))
            default_top_option = (
                "metricsLowestUtilization" if bottom_n > 0
                else "metricsHighestUtilization"
            )
            pareto_analysis_config = ParetoAnalysisConfig(
                adapter_kind=ak,
                resource_kind=rk,
                metric_key=mk,
                metric_name=mn,
                mode=str(w.get("mode", "all") or "all").strip(),
                top_n=top_n,
                bottom_n=bottom_n,
                top_option=str(w.get("top_option", default_top_option) or default_top_option).strip(),
                depth=int(w.get("depth", 10)),
                regeneration_time=int(w.get("regeneration_time", 15)),
                round_decimals=float(w.get("round_decimals", 1)),
            )

        widgets.append(
            Widget(
                local_id=str(w["id"]).strip(),
                type=widget_type,
                title=str(w.get("title", "")).strip(),
                coords=(
                    # Section: always full width (12 columns), one grid row.
                    # Only x/y are author-controlled.
                    {**dict(w.get("coords") or {"x": 1, "y": 1}), "w": 12, "h": 1}
                    if widget_type == "Section"
                    else dict(w.get("coords") or {"x": 1, "y": 1, "w": 6, "h": 6})
                ),
                section_config=section_config,
                view_details=view_details_raw,
                resource_kinds=rks,
                view_name=str(w.get("view", "") or "").strip(),
                self_provider=bool(w.get("self_provider", False)),
                pin=pin,
                select_first_row=select_first_row_raw,
                chart_view_items=chart_view_items,
                scoreboard_config=scoreboard_config,
                metric_chart_config=metric_chart_config,
                text_display_config=text_display_config,
                health_chart_config=health_chart_config,
                pareto_analysis_config=pareto_analysis_config,
                alert_list_config=alert_list_config,
                problems_alerts_list_config=problems_alerts_list_config,
                heatmap_config=heatmap_config,
                property_list_config=property_list_config,
                resource_relationship_advanced_config=resource_relationship_advanced_config,
                alert_volume_config=alert_volume_config,
                relationship_mode=relationship_mode,
                column_preset=(str(w["column_preset"]).strip() if w.get("column_preset") else None),
            )
        )
    # Section membership by row order when not authored explicitly (the
    # same rule the UI's GridsterPanel.syncSectionWidgets applies): each
    # Section owns every non-Section widget whose row lies strictly
    # between its own row and the next Section's row, ordered by (y, x).
    def _y(wd: Widget) -> int:
        return int(wd.coords.get("y", 1))

    def _x(wd: Widget) -> int:
        return int(wd.coords.get("x", 1))

    sections_by_row = sorted((w for w in widgets if w.type == "Section"), key=_y)
    # A Section owns its whole row: any other widget on that row would
    # overlap it and belong to no Section, silently.
    for sec in sections_by_row:
        for other in widgets:
            if other is not sec and _y(other) == _y(sec):
                raise DashboardValidationError(
                    f"widget {other.local_id!r} shares row y: {_y(sec)} with Section "
                    f"{sec.local_id!r}; a Section owns its whole row, move one of them"
                )
    for i, sec in enumerate(sections_by_row):
        if sec.section_config is None or sec.section_config.explicit_members:
            continue
        upper = _y(sections_by_row[i + 1]) if i + 1 < len(sections_by_row) else None
        members = [
            w for w in widgets
            if w.type != "Section" and _y(w) > _y(sec) and (upper is None or _y(w) < upper)
        ]
        members.sort(key=lambda wd: (_y(wd), _x(wd)))
        sec.section_config.member_ids = [w.local_id for w in members]
    interactions = [
        Interaction(
            from_local_id=str(ix["from"]).strip(),
            to_local_id=str(ix["to"]).strip(),
            type=str(ix.get("type", "resourceId")).strip(),
        )
        for ix in (data.get("interactions") or [])
    ]
    name = str(data.get("name", "")).strip()
    for w in widgets:
        w.dashboard_name = name
    name_path = str(data.get("name_path", "") or "").strip()
    shared_raw = data.get("shared")
    shared = True if shared_raw is None else bool(shared_raw)
    hidden_raw = data.get("hidden")
    # Default hidden=False so factory dashboards are visible immediately after
    # import. Pak-shipped dashboards that need to be hidden on import (e.g.
    # compliance) must set hidden: true explicitly in their YAML.
    hidden = False if hidden_raw is None else bool(hidden_raw)
    released_raw = data.get("released", False)
    released = bool(released_raw) if isinstance(released_raw, bool) else False
    version = str(data.get("version", "1.0.0") or "1.0.0").strip() or "1.0.0"
    summary_for_raw = data.get("summary_for")
    summary_for: Optional[list[str]] = None
    if summary_for_raw is not None:
        try:
            # Stored as a normalized list (one string, comma string and
            # YAML list all collapse to the same shape; tokens stripped).
            summary_for = normalize_summary_for(summary_for_raw)
        except ValueError as exc:
            raise DashboardValidationError(f"{path}: {exc}") from None
    from vcfops_common.provenance import provenance_from_path

    return Dashboard(
        id=dash_id,
        name=name,
        description=str(data.get("description", "") or "").strip(),
        widgets=widgets,
        interactions=interactions,
        name_path=name_path or default_name_path,
        shared=shared,
        hidden=hidden,
        source_path=path,
        released=released,
        version=version,
        provenance=provenance_from_path(path),
        summary_for=summary_for,
    )


def load_all(views_dir: Path, dashboards_dir: Path, enforce_framework_prefix: bool = True, default_name_path: str = "VCF Content Factory") -> tuple[list[ViewDef], list[Dashboard]]:
    views = [load_view(p, enforce_framework_prefix=enforce_framework_prefix) for p in sorted(views_dir.rglob("*.y*ml"))] if views_dir.exists() else []
    by_name = {v.name: v for v in views}
    dashboards: List[Dashboard] = []
    if dashboards_dir.exists():
        for p in sorted(dashboards_dir.rglob("*.y*ml")):
            d = load_dashboard(p, enforce_framework_prefix=enforce_framework_prefix, default_name_path=default_name_path)
            d.validate(by_name, enforce_framework_prefix=enforce_framework_prefix)
            dashboards.append(d)
    check_unique_summary_for(dashboards)
    return views, dashboards
