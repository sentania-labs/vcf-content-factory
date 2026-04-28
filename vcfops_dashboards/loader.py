"""YAML -> in-memory dashboard / view definition models.

UUIDs are random uuid4 values stored in each view / dashboard YAML's
`id` field, minted on first validate and never touched again. This
matches the super metric loader's contract (see
`context/uuids_and_cross_references.md`) and means rename-safe
install: changing a view or dashboard's name does not change its id,
so the existing server-side object is updated in place on re-sync.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

import yaml

from vcfops_dashboards.yaml_utils import strict_load as _strict_load

# Stable namespace for derived UUIDs. Do NOT change once content has
# been deployed — every dashboard/view id is derived from this.
NS = uuid.UUID("4b8d2c10-1f9e-4f4f-9b90-0e8f6a8e2a12")


class DashboardValidationError(ValueError):
    pass


def stable_id(kind: str, name: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}::{name}"))


# Transformation enum whitelist — verified against real exported view XML.
# See context/view_column_wire_format.md §Per-column transformations.
_VALID_TRANSFORMATIONS: set[str] = {
    "CURRENT", "NONE", "AVG", "MAX",
    "PERCENTILE", "TREND", "FORECAST", "TRANSFORM_EXPRESSION",
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
    supported by VCF Ops — one view, one window.
    See context/view_column_wire_format.md §Limitations.
    """
    unit: str   # MONTHS|WEEKS|DAYS|HOURS|MINUTES|YEARS
    count: int  # positive integer
    advanced_time_mode: bool = False


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
    # Per-column color thresholds. See context/view_column_wire_format.md.
    yellow_bound: Optional[Union[float, str]] = None
    orange_bound: Optional[Union[float, str]] = None
    # red_bound accepts float for numeric, str for property-match (e.g. "Powered Off")
    red_bound: Optional[Union[float, str]] = None
    # Required when all three numeric bounds are set.
    # False = higher is worse (red=high). True = lower is worse (red=low).
    ascending_range: Optional[bool] = None


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
class ViewDef:
    name: str
    description: str
    adapter_kind: str
    resource_kind: str
    columns: List[ViewColumn]
    id: str = ""
    source_path: Path | None = None
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
    released: bool = False   # publish gate
    version: str = "1.0.0"  # internal semver
    # Optional list of custom group names this view is scoped to.
    # When set, the dependency walker surfaces these groups as deps.
    # YAML key: `customgroup:` (str or list[str]).
    customgroups: List[str] = field(default_factory=list)
    # Provenance: "factory", a third-party project slug, or "" (unknown).
    # Populated by the loader from source_path; never author-supplied.
    provenance: str = ""

    def validate(self, enforce_framework_prefix: bool = True) -> None:
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
        if not self.adapter_kind or not self.resource_kind:
            raise DashboardValidationError(
                f"view {self.name}: adapter_kind and resource_kind required"
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
            self._validate_column(c)
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
        if needs_window and self.time_window is None:
            warnings.warn(
                f"view {self.name!r}: one or more columns use an aggregating "
                "transformation (AVG/MAX/PERCENTILE/TRANSFORM_EXPRESSION) but "
                "no time_window is set. Columns will aggregate over the view's "
                "default window (typically 24 hours). Set time_window: "
                "{{unit: MONTHS, count: 6}} to make the window explicit.",
                UserWarning,
                stacklevel=2,
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
                "See context/view_column_wire_format.md."
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


@dataclass
class MetricSpec:
    """One metric entry within a Scoreboard or MetricChart widget.

    Maps to a single entry in ``metric.resourceKindMetrics[]``.

    Fields:
        adapter_kind:  VMWARE, NSXTAdapter, etc.
        resource_kind: VirtualMachine, ClusterComputeResource, etc.
        metric_key:    Ops stat key, e.g. ``cpu|usage_average`` or
                       ``Super Metric|sm_<uuid>``.
        metric_name:   Display name for the metric (shown in legend/tile).
        unit_id:       Optional Ops unit ID string (e.g. ``"percent"``).
        unit:          Optional display unit string (e.g. ``"%"``).
        color_method:  0=custom thresholds, 1=no color, 2=dynamic. Default 2.
        yellow_bound:  Threshold value when color_method=0.
        orange_bound:  Threshold value when color_method=0.
        red_bound:     Threshold value when color_method=0.
        label:         Short tile label override (Scoreboard). Optional.
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


@dataclass
class ScoreboardConfig:
    """Type-specific config for a Scoreboard widget."""
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

    Uses a FLAT metric spec — a single metric key and resourceKindId
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


@dataclass
class HeatmapColorThreshold:
    """Color threshold band for a Heatmap tab.

    ``values`` are the lower-bound breakpoints; ``colors`` are the hex
    color strings for each band. Color count distribution observed on the
    live instance: 3 colors (59 tabs), 5 colors (18), 6 colors (10),
    4 colors (7). There is no strict relationship between values and colors
    length enforced by Ops — the UI sets them together.
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
class Widget:
    local_id: str  # author-supplied short id used for interaction wiring
    type: str  # ResourceList | View | TextDisplay | Scoreboard | MetricChart | HealthChart | ParetoAnalysis | AlertList | ProblemAlertsList
    title: str
    coords: dict  # {x, y, w, h}
    # ResourceList only:
    resource_kinds: List[WidgetResourceKindRef] = field(default_factory=list)
    # View only:
    view_name: str = ""
    # View-widget self-provider: when true, the widget does not wait
    # for an incoming interaction and instead enumerates its subject.
    # Requires ``pin`` to a container resource kind (e.g. vSphere World)
    # whose descendants Ops walks to populate the list.
    self_provider: bool = False
    pin: WidgetResourceKindRef | None = None
    # Type-specific config for chart/text widgets
    scoreboard_config: ScoreboardConfig | None = None
    metric_chart_config: MetricChartConfig | None = None
    text_display_config: TextDisplayConfig | None = None
    health_chart_config: HealthChartConfig | None = None
    pareto_analysis_config: ParetoAnalysisConfig | None = None
    alert_list_config: AlertListConfig | None = None
    problems_alerts_list_config: ProblemAlertsListConfig | None = None
    heatmap_config: HeatmapConfig | None = None
    # Set by load_dashboard so widget UUIDs are namespaced by dashboard
    # name — otherwise two dashboards reusing the same local_id (e.g.
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
    # Ops dashboard folder path — lands in the Ops UI's dashboard
    # sidebar under this folder. Default is the framework folder; can
    # be overridden per-dashboard if an author has a specific reason.
    name_path: str = "VCF Content Factory"
    # Whether the dashboard is shared with other Ops users. Defaults
    # to True — a dashboard nobody else can see defeats the purpose
    # of the framework. Can be overridden per-dashboard via YAML.
    shared: bool = True
    id: str = ""
    source_path: Path | None = None
    released: bool = False   # publish gate
    version: str = "1.0.0"  # internal semver
    # Provenance: "factory", a third-party project slug, or "" (unknown).
    # Populated by the loader from source_path; never author-supplied.
    provenance: str = ""

    def validate(self, known_views: dict[str, ViewDef], enforce_framework_prefix: bool = True) -> None:
        if not self.name.strip():
            raise DashboardValidationError("dashboard: name is required")
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
            "Heatmap",
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
            if w.type == "View":
                if not w.view_name:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"View requires 'view' (the view definition name)"
                    )
                if w.view_name not in known_views:
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
        for ix in self.interactions:
            if ix.from_local_id not in seen or ix.to_local_id not in seen:
                raise DashboardValidationError(
                    f"dashboard {self.name}: interaction references unknown widget"
                )


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _mint_id_into_file(path: Path) -> str:
    """Mint a uuid4 and prepend ``id: <uuid>`` to the YAML file.

    Same contract as the super metric loader: UUIDs are generated
    once on first validate and never touched after. See
    context/uuids_and_cross_references.md.
    """
    new_id = str(uuid.uuid4())
    original = path.read_text()
    path.write_text(f"id: {new_id}\n{original}")
    return new_id


def load_view(path: Path, enforce_framework_prefix: bool = True) -> ViewDef:
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

        return ViewColumn(
            attribute=str(c["attribute"]).strip(),
            display_name=str(c["display_name"]).strip(),
            unit=str(c.get("unit", "") or "").strip(),
            transformation=transformation,
            percentile=percentile,
            transform_expression=str(transform_expr).strip() if transform_expr else None,
            yellow_bound=yellow,
            orange_bound=orange,
            red_bound=red,
            ascending_range=ascending,
        )

    cols = [_load_column(c) for c in (data.get("columns") or [])]
    subj = data.get("subject") or {}
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

    # data_type and presentation — defaults depend on each other
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
        time_window = ViewTimeWindow(unit=tw_unit, count=tw_count, advanced_time_mode=tw_adv)

    released_raw = data.get("released", False)
    released = bool(released_raw) if isinstance(released_raw, bool) else False
    version = str(data.get("version", "1.0.0") or "1.0.0").strip() or "1.0.0"

    # customgroup: str | list[str] — names of custom groups this view is scoped to.
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
        adapter_kind=str(subj.get("adapter_kind", "")).strip(),
        resource_kind=str(subj.get("resource_kind", "")).strip(),
        columns=cols,
        source_path=path,
        summary=summary,
        data_type=data_type,
        presentation=presentation,
        buckets=buckets,
        forecast_days=forecast_days,
        transformations=transformations,
        time_window=time_window,
        released=released,
        version=version,
        customgroups=view_customgroups,
        provenance=provenance_from_path(path),
    )
    v.validate(enforce_framework_prefix=enforce_framework_prefix)
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
            pin = WidgetResourceKindRef(
                adapter_kind=str(pin_raw["adapter_kind"]).strip(),
                resource_kind=str(pin_raw["resource_kind"]).strip(),
            )
        widget_type = str(w["type"]).strip()

        # --- Parse TextDisplay config ---
        text_display_config = None
        if widget_type == "TextDisplay":
            html_content = str(w.get("html") or w.get("text") or "<br>").strip()
            text_display_config = TextDisplayConfig(html=html_content)

        # --- Parse metric specs helper (shared by Scoreboard + MetricChart) ---
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
                ))
            return specs

        # --- Parse Scoreboard config ---
        scoreboard_config = None
        if widget_type == "Scoreboard":
            raw_metrics = w.get("metrics") or []
            specs = _parse_metric_specs(raw_metrics)
            scoreboard_config = ScoreboardConfig(
                metrics=specs,
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
                round_decimals=float(w["round_decimals"]) if w.get("round_decimals") is not None else 1,
                max_cell_count=int(w.get("max_cell_count", 100)),
            )

        # --- Parse MetricChart config ---
        metric_chart_config = None
        if widget_type == "MetricChart":
            raw_metrics = w.get("metrics") or []
            specs = _parse_metric_specs(raw_metrics)
            metric_chart_config = MetricChartConfig(metrics=specs)

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
            alert_list_config = AlertListConfig(
                criticality=criticality,
                alert_types=[str(t).strip() for t in raw_types],
                status=[int(s) for s in (w.get("status") or [])],
                state=list(w.get("state") or []),
                alert_impact=[str(a).strip() for a in (w.get("alert_impact") or [])],
                alert_action=list(w.get("alert_action") or []),
                mode=str(w.get("mode", "all") or "all").strip(),
                depth=int(w.get("depth", 1)),
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
                coords=dict(w.get("coords") or {"x": 1, "y": 1, "w": 6, "h": 6}),
                resource_kinds=rks,
                view_name=str(w.get("view", "") or "").strip(),
                self_provider=bool(w.get("self_provider", False)),
                pin=pin,
                scoreboard_config=scoreboard_config,
                metric_chart_config=metric_chart_config,
                text_display_config=text_display_config,
                health_chart_config=health_chart_config,
                pareto_analysis_config=pareto_analysis_config,
                alert_list_config=alert_list_config,
                problems_alerts_list_config=problems_alerts_list_config,
                heatmap_config=heatmap_config,
            )
        )
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
    released_raw = data.get("released", False)
    released = bool(released_raw) if isinstance(released_raw, bool) else False
    version = str(data.get("version", "1.0.0") or "1.0.0").strip() or "1.0.0"
    from vcfops_common.provenance import provenance_from_path

    return Dashboard(
        id=dash_id,
        name=name,
        description=str(data.get("description", "") or "").strip(),
        widgets=widgets,
        interactions=interactions,
        name_path=name_path or default_name_path,
        shared=shared,
        source_path=path,
        released=released,
        version=version,
        provenance=provenance_from_path(path),
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
    return views, dashboards
