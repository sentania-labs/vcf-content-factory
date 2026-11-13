"""Source accounting: every source key is classified, or the object stops.

After a mapper has built an object's YAML, :func:`account` walks the
object's flat form (``flat``; every attribute, text, JSON key and list
position) and classifies each key by the first matching row of the type's
table below:

- ``conv``: **converted**. The mapper carries it into the YAML (and is
  responsible for refusing a value it cannot carry). A verification proves
  it end to end.
- ``const <json>``: a **constant** the renderer always writes, with the
  evidence named on the row (the renderer function). The source value must
  equal it; any other value stops the object with a TOOLSET GAP (the YAML
  cannot carry it).
- ``same <ref>``: a value the renderer **derives** from another key (a
  widget's ``config.title`` is its ``title``). ``^key`` is relative to the
  widget, ``..key`` is a sibling. The source must hold the same value.
- ``check <name>``: a derived value the renderer computes (a tag filter's
  ``path`` list from its kinds, a Heatmap ``groupBy.id``); the named check
  recomputes it with the renderer's own helper. A check may instead find a
  documented loss at the key (``LossAt``: a ``config.widgetId`` naming no
  widget of the dashboard).
- ``loss <class>``: a documented not-modeled class
  (``model.DOCUMENTED_NOT_MODELED``): recorded as a LOSS at this exact key.

On a converted or derived key, a display string the loader strips
(``STRIPPED_TEXT``) with surrounding whitespace is also recorded as a LOSS
there, conditional on the render being the source stripped.

Keys the product renumbers are not in the flat form at all (they are
removed and counted there). Any key no row matches is **unclassified**:
the object stops with a TOOLSET GAP naming the key, so a key a future
product version adds cannot vanish quietly. Unsupported widget types stop
the dashboard before this runs.

Pattern syntax: a generic flat path (``flat.generic``) where ``widget:*``
matches any widget type, ``(a|b)`` is an alternation and everything else is
literal (``[]``, ``{*}`` and ``~*`` are the generic forms of a list
position, a state key and a repeat); ``?`` after a group makes it optional.
``const []`` / ``const {}`` is an empty JSON list / object.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Dict, List, Optional, Tuple

from . import flat as _flat
from .model import DOCUMENTED_NOT_MODELED, Loss, Mark, MappingError, documented_loss, toolset_gap


# ------------------------------------------------------------------ rows
class Rule:
    __slots__ = ("pattern", "rx", "kind", "arg", "evidence")

    def __init__(self, pattern: str, kind: str, arg, evidence: str):
        self.pattern, self.kind, self.arg, self.evidence = pattern, kind, arg, evidence
        self.rx = re.compile(_pattern_rx(pattern))


def _pattern_rx(p: str) -> str:
    out, i = [], 0
    while i < len(p):
        if p.startswith("widget:*", i):
            out.append(r"widget:[A-Za-z]+")
            i += len("widget:*")
            continue
        c = p[i]
        if c == "(":
            out.append("(?:")
        elif c in "|)?":
            out.append(c)
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def parse_table(text: str) -> List[Rule]:
    rules = []
    for raw in text.splitlines():
        line = raw.split("  #", 1)
        body, ev = line[0].strip(), (line[1].strip() if len(line) > 1 else "")
        if not body or body.startswith("#"):
            continue
        parts = body.split(None, 2)
        pattern, kind = parts[0], parts[1]
        arg = parts[2] if len(parts) > 2 else None
        if kind == "const":
            arg = json.loads(arg)
            if arg == []:
                arg = _flat.EMPTY_LIST_LEAF
            elif arg == {}:
                arg = _flat.EMPTY_DICT_LEAF
        elif kind == "loss" and arg not in DOCUMENTED_NOT_MODELED:
            raise ValueError(f"accounting row {pattern}: {arg!r} is not a documented class")
        elif kind not in ("conv", "same", "check", "loss"):
            raise ValueError(f"accounting row {pattern}: unknown kind {kind!r}")
        rules.append(Rule(pattern, kind, arg, ev))
    return rules


# ----------------------------------------------------------------- views
_COLUMN_CONV = ("objectType|attributeKey|preferredUnitId|isStringAttribute|adapterKind|resourceKind|rollUpType|"
                "rollUpUnit|rollUpCount|percentile|transformExpression|sortCriteria|isProperty|yellowBound|"
                "orangeBound|redBound|ascendingRange|useSymptomThresholds|displayName|addTimestampAsColumn|"
                "isShowRelativeTimestamp|metricToRelateWith|localizedMetricToRelateWith|operatorToRelateWith|"
                "forecastDays|isInstancedGroup|showInstanceName|instanceGroupName|keepInstanceSummary|"
                "isTimeSegment|breakdownBy|startingOnUnit|startingOnCount|cellLink|related|"
                "isRelatedMetricAProperty")
_ADDCOL_CONV = ("objectType|attributeKey|preferredUnitId|localizedAttributeName|isStringAttribute|adapterKind|"
                "resourceKind|rollUpType|rollUpCount|percentile|sortCriteria|isProperty|displayName|"
                "isShowRelativeTimestamp")
_COL = "ViewDef/Controls/Control{attributes-selector}/Property{attributeInfos}/List/Item[]/Value"
_SUM = "ViewDef/Controls/Control{attributes-selector}/Property{summaryInfos}/List/Item[]/Value"
_ADD = "ViewDef/Controls/Control{metadata}/Property{distributionAdditionalColumns}/List/Item[]/Value"
_BKT = "ViewDef/Controls/Control{buckets-control}"
_TIS = "ViewDef/Controls/Control{time-interval-selector}"
_MD = "ViewDef/Controls/Control{metadata}"
_PG = "ViewDef/Controls/Control{pagination-control}"

VIEW_TABLE = parse_table(f"""
ViewDef@id                                         conv
ViewDef/Title#text                                 conv
ViewDef/Description#text                           conv   # surrounding whitespace: STRIPPED_TEXT
ViewDef/(Title|Description)@localizationKey       conv   # the mapper records the documented loss
ViewDef/SubjectType{{*}}#text                      const ""   # render._render_view_def_fragment: empty element
ViewDef/SubjectType{{*}}@filter[][].(condition|transform|metricKey|filterType|businessHours|conditionId)  conv
ViewDef/SubjectType{{*}}@filter[][].metricValue.(value|isStringMetric)  conv
ViewDef/SubjectType{{*}}@filter[][].metricValue.values  conv
ViewDef/SubjectType{{*}}@filter[][].metricValue.values[]  conv   # the mapper records the documented loss
ViewDef/SubjectType{{*}}@filter    conv
ViewDef/SubjectType{{*}}@filter[]  conv
ViewDef/SubjectsGroupBy{{*}}#text                  const ""   # render: empty element
ViewDef/Usage{{*}}                                 conv
ViewDef/Presentation@type                          conv
ViewDef/Presentation#text                          const ""   # render: empty element
ViewDef/DataProviders/DataProvider[]@dataType      conv
ViewDef/DataProviders/DataProvider[]#text          const ""   # render: empty element
ViewDef/BlacklistResourceKind(@adapterKind|@resourceKind|#text)  loss BlacklistResourceKind
ViewDef/Controls/Control{{time-interval-selector}}@visible  const "false"   # render._xml_time_interval_selector
ViewDef/Controls/Control{{attributes-selector}}@visible     const "false"   # render._render_view_def_fragment
ViewDef/Controls/Control{{pagination-control}}@visible      const "true"    # render._xml_pagination_control
ViewDef/Controls/Control{{buckets-control}}@visible         const "false"   # render._xml_buckets_control
ViewDef/Controls/Control{{metadata}}@visible                const "false"   # render._xml_metadata_control
{_TIS}/Property{{(advancedTimeMode|unit|count|startPeriod|endPeriod|startSubUnit)}}@value  conv
{_COL}/Property{{({_COLUMN_CONV})}}@value          conv
{_COL}/Property{{transformations}}/List/Item[]@value  conv
{_COL}/Property{{displayName}}@localizationKey     loss displayName localizationKey
{_COL}/Property{{displayName}}~*(@value|@localizationKey)  conv   # the mapper records the documented loss (a second displayName)
{_COL}/Property{{displayName}}~*#text              const ""   # an empty element (dropped with the repeat)
{_SUM}/Property{{(displayName|aggregation)}}@value  conv
{_SUM}/Property{{displayName}}@localizationKey     loss displayName localizationKey
{_SUM}/Property{{attributeIndexes}}/List/Item[]@value  conv
{_BKT}/Property{{(isDynamic|dynamicCalcFunction|bucketCount|minValue|maxValue|isSum)}}@value  conv
{_BKT}/Property{{bucketInfos}}/List/Item[]/Value/Property{{(startValue|endValue|bucketColor)}}@value  conv
{_MD}/Property{{(maxPointsCount|distributionColor|hideObjectNameColumn|listTopResultSize|includeResourceCreationTime|includeNotExistingResources)}}@value  conv
{_ADD}/Property{{({_ADDCOL_CONV})}}@value          conv
{_ADD}/Property{{transformations}}/List/Item[]@value  conv
{_PG}/Property{{(start|size)}}@value               conv
""")

# Every Property / Item / List / Value element under a control is written
# empty (render._xml_property and the control renderers): one rule, a regex
# the table syntax cannot express.
_VIEW_TEXT_RX = re.compile(r"ViewDef/Controls/Control\{[^}]*\}(?:/[^#@]*)?/(?:Property\{[^}]*\}|Item\[\]|List|Value)#text")


# ----------------------------------------------------------- reports etc.
REPORT_TABLE = parse_table("""
ReportDef@id                                    conv
ReportDef/(Title|Description)#text              conv   # Description surrounding whitespace: STRIPPED_TEXT
ReportDef/(Title|Description)@localizationKey   conv   # the mapper records the documented loss
ReportDef/isTenant#text                         conv
ReportDef/SubjectType[](@adapterKind|@resourceKind|@type|@filter)  conv
ReportDef/SubjectType[]#text                    const ""   # reports.render: empty element
ReportDef/Sections/Section[]/(ContentType|ContentOrientation)#text  conv
ReportDef/Sections/Section[]/ContentKey#text    check report_content_key
ReportDef/Sections/Section[]/ContentFormatting/(ColorizeListView|FontColor)#text  conv
ReportDef/Settings/(ShowPageFooter|OutputFormat[])#text  conv
""")

ALERT_TABLE = parse_table("""
AlertDefinition@(adapterKind|cancelCycle|description|disableInBasePolicy|id|name|resourceKind|subType|type|waitCycle)  conv
AlertDefinition/State@severity                  conv
AlertDefinition/State/Impact@(key|type)         conv
AlertDefinition/State/Impact#text               const ""   # alerts.render: empty element
AlertDefinition/State/(SymptomSets/)?SymptomSet[]@(aggregation|applyOn|operator|ref)  conv
AlertDefinition/State/(SymptomSets/)?SymptomSet[]#text  const ""   # alerts.render: empty element
AlertDefinition/State/(SymptomSets/)?SymptomSet[]/Symptom[]@ref  conv
AlertDefinition/State/(SymptomSets/)?SymptomSet[]/Symptom[]#text  const ""   # alerts.render: empty element
AlertDefinition/State/SymptomSets@operator      conv
AlertDefinition/State/Recommendations/Recommendation[]@(priority|ref)  conv
AlertDefinition/State/Recommendations/Recommendation[]#text  const ""   # alerts.render: empty element
""")

SYMPTOM_TABLE = parse_table("""
SymptomDefinition@(adapterKind|cancelCycle|disableInBasePolicy|id|name|resourceKind|symptomDefType|waitCycle)  conv
SymptomDefinition/State@severity                conv
SymptomDefinition/State/Condition[]@(instanced|key|operator|thresholdType|type|value|valueType)  conv
SymptomDefinition/State/Condition[]#text        const ""   # alerts.render: empty element
""")

RECOMMENDATION_TABLE = parse_table("""
Recommendation@(key|id)                          conv
Recommendation/Description#text                  conv
""")

SUPERMETRIC_TABLE = parse_table("""
supermetric.(id|name|formula|description|unitId)  conv
supermetric.resourceKinds                          conv
supermetric.resourceKinds[].(adapterKindKey|resourceKindKey)  conv
""")


# ------------------------------------------------------------- dashboards
_W = "widget:*"
_TAGV = "tagFilter.value.(adapterInstance|adapterKind|bus|collector|day|healthRange|maintenanceSchedule|tag|tier)"
_MET = ("metric.resourceKindMetrics[].(metricKey|metricName|isStringMetric|resourceKindId|resourceKindName|"
        "colorMethod|handleOldColoring|label|link|maxValue|metricUnitId|unit|labelLocalized|labelOrig|"
        "metricUnit|defUnit)")
_RMET = ("metric.resourceMetrics[].(metricKey|metricName|isStringMetric|resourceId|resourceName|resourceKindId|"
         "colorMethod|handleOldColoring|label|link|maxValue|metricUnitId|unit|labelLocalized|labelOrig|"
         "metricUnit|defUnit)")

DASHBOARD_TABLE = parse_table(f"""
# dashboard level (render._build_dashboard_obj)
dashboard.(id|name|namePath|description|shared|hidden|disabled|temporary|editAllowed|docCenterKey|columnProportion|columnCount)  conv
dashboard.autoswitchEnabled    const false   # render._build_dashboard_obj
dashboard.importAttempts       const 0       # render._build_dashboard_obj
dashboard.importComplete       const true    # render._build_dashboard_obj
dashboard.homeTab              const false   # render._build_dashboard_obj
dashboard.gridsterMaxColumns   const 12      # render._build_dashboard_obj
dashboard.rank                 const 0       # render._build_dashboard_obj
dashboard.locked               const false   # render._build_dashboard_obj
dashboard.adapterName          loss adapterName
dashboard.states               conv
dashboard.states{{*}}.value    conv   # the mapper converts the relative time range and records the absolute-date loss
dashboard.widgetInteractions   conv
dashboard.widgetInteractions[].(type|widgetIdProvider|widgetIdReceiver)  conv
dashboard.dashboardNavigations conv
dashboard.dashboardNavigations.*  conv
dashboard.dashboardNavigations.*[].(id|widgets)  conv
dashboard.dashboardNavigations.*[].widgets[].id  conv
dashboard.dashboardNavigations.*[].widgets[].interactionType  const "resourceId"   # render._render_dashboard_navigations
dashboard.dashboardNavigations.stale:*  loss navigation keyed by a widget not on the dashboard
dashboard.dashboardNavigations.stale:*[].(id|widgets)  loss navigation keyed by a widget not on the dashboard
dashboard.dashboardNavigations.stale:*[].widgets[].(id|interactionType)  loss navigation keyed by a widget not on the dashboard
dashboard.widgets              conv
entries.resourceKind{{*}}.(adapterKindKey|resourceKindKey)  conv
entries.resource{{*}}.(adapterKindKey|resourceKindKey|name)  conv
entries.resource{{*}}.identifiers  const []   # render_dashboards_bundle_json: identifiers []
# every widget type (render._apply_widget_fidelity and the type renderers)
{_W}.(type|title|collapsed|height|state|tabId|x|y)  conv
{_W}.gridsterCoords.(x|y|w|h)  conv
{_W}.states{{*}}.value         conv
{_W}.config.(description|titleLocalized|viewDetails)  conv
{_W}.config.key                same ^type   # render._apply_widget_fidelity: config.key = the wire type
{_W}.config.widgetId           check widget_id_self   # render._apply_widget_fidelity: the widget's own id
widget:(View|TextDisplay|Scoreboard|MetricChart|HealthChart|ParetoAnalysis|Heatmap|ResourceRelationshipAdvanced|AlertList|Section|ResourceList|ProblemAlertsList|PropertyList|IntSummaryAlertVolume).config.title  same ^title   # every type renderer writes title: w.title
# View (render._view_widget)
widget:View.config.(viewDefinitionId|chartViewItems|traversalSpecId|viewType|resource)  conv
widget:View.config.chartViewItems[]  conv
widget:View.config.selectFirstRow.selectFirstRow  conv
widget:View.config.selfProvider.selfProvider  conv
widget:View.config.resource.(resourceKindId|resourceName|traversalSpecId)  conv
widget:View.config.resource.resourceId  check view_pin_resource
widget:View.config.refreshInterval  const 300     # render._view_widget
widget:View.config.refreshContent.refreshContent  const false   # render._view_widget
widget:View.config.isUpdatedView  const true      # render._view_widget
# TextDisplay (render._text_display_widget)
widget:TextDisplay.config.(editorData|locationFile|locationUrl|viewModeHTML)  conv
widget:TextDisplay.config.refreshInterval  const 300   # render._text_display_widget
widget:TextDisplay.config.refreshContent.refreshContent  const false   # render._text_display_widget
# Section (render._section_widget)
widget:Section.config.widgets  conv
widget:Section.config.widgets[]  conv
# metric entries (render._render_metric_spec / _render_resource_metric_spec)
widget:Scoreboard.config.metric.(mode|subMode|resourceKindMetrics)  conv
widget:MetricChart.config.metric.(subMode|resourceKindMetrics)  conv
widget:PropertyList.config.metric.resourceKindMetrics  conv
widget:(MetricChart|PropertyList).config.metric.mode  const "resourceKind"   # render._render_metric_spec
widget:PropertyList.config.metric.subMode  const "resourceKindAll"   # render._render_metric_spec
widget:(Scoreboard|MetricChart|PropertyList).config.{_MET}  conv
widget:(Scoreboard|MetricChart|PropertyList).config.metric.resourceKindMetrics[].(yellowBound|orangeBound|redBound)  check metric_bound
widget:Scoreboard.config.metric.resourceMetrics  conv
widget:Scoreboard.config.{_RMET}  conv
widget:Scoreboard.config.metric.resourceMetrics[].(yellowBound|orangeBound|redBound)  check metric_bound
widget:(MetricChart|PropertyList).config.metric.resourceMetrics  const []   # render._render_metric_spec
# Scoreboard (render._scoreboard_widget)
widget:Scoreboard.config.(visualTheme|boxColumns|boxHeight|valueSize|labelSize|roundDecimals|maxCellCount|periodLength|oldMetricValues|showRemaining|showPercentText|focusOnPercent|resource)  conv
widget:Scoreboard.config.(mode.layoutMode|showSparkline.showSparkline|showResourceName.showResourceName|showMetricName.showMetricName|showMetricUnit.showMetricUnit|showDT.showDT|refreshContent.refreshContent|selfProvider.selfProvider)  conv
widget:Scoreboard.config.resource[].id  conv
widget:Scoreboard.config.resource[].name  check res_name ..id
widget:Scoreboard.config.refreshInterval  const 300   # render._scoreboard_widget
widget:Scoreboard.config.relationshipMode.relationshipMode  const 0   # render._scoreboard_widget
widget:Scoreboard.config.depth  const 1   # render._scoreboard_widget
widget:Scoreboard.config.resInteractionMode  const null   # render._scoreboard_widget
# MetricChart (render._metric_chart_widget)
widget:MetricChart.config  conv
widget:MetricChart.config.(refreshContent.refreshContent|relationshipMode.relationshipMode|selfProvider.selfProvider)  conv
widget:MetricChart.config.refreshInterval  const 300   # render._metric_chart_widget
widget:MetricChart.config.resource  const []   # render._metric_chart_widget
widget:MetricChart.config.depth  const 1   # render._metric_chart_widget
widget:MetricChart.config.resInteractionMode  const null   # render._metric_chart_widget
# PropertyList (render._property_list_widget)
widget:PropertyList.config.(visualTheme|depth|selfProvider.selfProvider|showMetricFullName.metricFullName)  conv
widget:PropertyList.config.refreshInterval  const 300   # render._property_list_widget
widget:PropertyList.config.resource  const []   # render._property_list_widget
widget:PropertyList.config.refreshContent.refreshContent  const true   # render._property_list_widget
widget:PropertyList.config.relationshipMode.relationshipMode  const 0   # render._property_list_widget
widget:PropertyList.config.resInteractionMode  const null   # render._property_list_widget
# HealthChart (render._health_chart_widget)
widget:HealthChart.config.(chartHeight|depth|metricFullName|metricKey|metricName|mode|yellowBound|orangeBound|redBound|paginationNumber|resource|resourceKindId|undefined)  conv
widget:HealthChart.config.(relationshipMode.relationshipMode|selfProvider.selfProvider|showResourceName.showResourceName|sortByDir.orderByDir|customFilter.filterMode)  conv
widget:HealthChart.config.undefined[].(id|name)  conv
widget:HealthChart.config.resource[].id  conv
widget:HealthChart.config.resource[].name  check res_name ..id
widget:HealthChart.config.tagFilter  conv
widget:HealthChart.config.tagFilter.value.(kind|state|status)  conv
widget:HealthChart.config.tagFilter.value.(kind|state|status)[]  conv
widget:HealthChart.config.{_TAGV}  const []   # render._tag_filter_json
widget:HealthChart.config.tagFilter.value.exclaim  const false   # render._tag_filter_json
widget:HealthChart.config.tagFilter.path[]  check tag_filter_path
widget:HealthChart.config.refreshInterval  const 300   # render._health_chart_widget
widget:HealthChart.config.refreshContent.refreshContent  const false   # render._health_chart_widget
widget:HealthChart.config.filterMode  const "tagPicker"   # render._health_chart_widget
widget:HealthChart.config.metricUnit.metricUnitId  const -1   # render._health_chart_widget
widget:HealthChart.config.metricUnit.metricUnitName  const "Default Unit"   # render._health_chart_widget
widget:HealthChart.config.metricType.metricType  const "custom"   # render._health_chart_widget
widget:HealthChart.config.sortBy  const "metricValue"   # render._health_chart_widget
widget:HealthChart.config.showMetricLabel.showMetricLabel  const false   # render._health_chart_widget
widget:HealthChart.config.metricLabel  const ""   # render._health_chart_widget
widget:HealthChart.config.selectFirstRow.selectFirstRow  const false   # render._health_chart_widget
# ParetoAnalysis (render._pareto_analysis_widget)
widget:ParetoAnalysis.config.(barsCount|depth|maxValue|metricName|mode|yellowBound|orangeBound|redBound|percentileValue|regenerationTime|roundDecimals|topOption|additionalColumns)  conv
widget:ParetoAnalysis.config.(metric.metricKey|metric.name|metricUnit.metricUnitId|metricUnit.metricUnitName|refreshContent.refreshContent|relationshipMode.relationshipMode|selfProvider.selfProvider)  conv
widget:ParetoAnalysis.config.relationshipMode.relationshipMode[]  conv
widget:ParetoAnalysis.config.resourceKind[].id  conv
widget:ParetoAnalysis.config.additionalColumns[].(boxLabel|metricKey|metricName|resourceKindId)  conv
widget:ParetoAnalysis.config.refreshInterval  const 300   # render._pareto_analysis_widget
widget:ParetoAnalysis.config.resource  const []   # render._pareto_analysis_widget
widget:ParetoAnalysis.config.filterMode  const "tagPicker"   # render._pareto_analysis_widget
widget:ParetoAnalysis.config.tagFilter  const null   # render._pareto_analysis_widget
widget:ParetoAnalysis.config.filterOldMetrics.filterOldMetrics  const false   # render._pareto_analysis_widget
# Heatmap (render._heatmap_widget)
widget:Heatmap.config.(mode|depth|value|selfProvider.selfProvider|relationshipMode.relationshipMode)  conv
widget:Heatmap.config.relationshipMode.relationshipMode[]  conv
widget:Heatmap.config.refreshInterval  const 300   # render._heatmap_widget
widget:Heatmap.config.refreshContent.refreshContent  const false   # render._heatmap_widget
widget:Heatmap.config.resource  const []   # render._heatmap_widget
widget:Heatmap.config.configs[].(name|nameLocalized|nameOrig|resourceKind|solidColoring|focusOnGroups|filterMode|tagFilter|customFilter)  conv
widget:Heatmap.config.configs[].(colorBy.metricKey|colorBy.value|sizeBy.metricKey|sizeBy.value|color.minValue|color.maxValue)  conv
widget:Heatmap.config.configs[].color.thresholds.(values|colors)[]  conv
widget:Heatmap.config.configs[].groupBy.(typeId|text|parentText)  conv
widget:Heatmap.config.configs[].groupBy.(adapterKind|resourceKind)  check heatmap_group_kind
widget:Heatmap.config.configs[].groupBy.id  check heatmap_group_id
widget:Heatmap.config.configs[].groupBy.parentId  check heatmap_group_parent
widget:Heatmap.config.configs[].groupBy.originalText  same ..text   # render._heatmap_widget: originalText = text
widget:Heatmap.config.configs[].groupBy.type  const "resourceKind"   # render._heatmap_widget
widget:Heatmap.config.configs[].thenBy  const null   # render._heatmap_widget
widget:Heatmap.config.configs[].relationalGrouping  const false   # render._heatmap_widget
widget:Heatmap.config.configs[].mode.mode  const false   # render._heatmap_widget
widget:Heatmap.config.configs[].attributeKind.value  const ""   # render._heatmap_widget
widget:Heatmap.config.configs[].customFilter.filter  conv
widget:Heatmap.config.configs[].customFilter.(excludedResources|includedResources)  const null   # render._heatmap_widget
widget:Heatmap.config.configs[].customFilter.filter[].resourceKindId  conv
widget:Heatmap.config.configs[].customFilter.filter[].resourceKind  same ..resourceKindId   # render._heatmap_widget
widget:Heatmap.config.configs[].customFilter.filter[].filterTypes[].(condition|metricName|metricKey|isStringMetric|filterType|metricUnit|metricValue.value)  conv
widget:Heatmap.config.configs[].customFilter.filter[].filterTypes[].metricValue.isStringMetric  same ...isStringMetric   # render._heatmap_widget
widget:Heatmap.config.configs[].tagFilter.value.(kind|state|status)  conv
widget:Heatmap.config.configs[].tagFilter.value.(kind|state|status)[]  conv
widget:Heatmap.config.configs[].{_TAGV}  const []   # render._tag_filter_json
widget:Heatmap.config.configs[].tagFilter.value.exclaim  const false   # render._tag_filter_json
widget:Heatmap.config.configs[].tagFilter.path[]  check tag_filter_path
# ResourceRelationshipAdvanced (render._resource_relationship_advanced_widget)
widget:ResourceRelationshipAdvanced.config.(depth|paginationNumber|relationshipMode|visualTheme|tagFilter|selectFirstRow.selectFirstRow|selfProvider.selfProvider|customFilter.filterMode)  conv
widget:ResourceRelationshipAdvanced.config.tagFilter.value.kind  conv
widget:ResourceRelationshipAdvanced.config.tagFilter.value.kind[]  conv
widget:ResourceRelationshipAdvanced.config.tagFilter.value.(state|status)  const []   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.{_TAGV}  const []   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.tagFilter.value.exclaim  const false   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.tagFilter.path[]  check tag_filter_path
widget:ResourceRelationshipAdvanced.config.tagFilter.path  const []   # an empty kinds list
widget:ResourceRelationshipAdvanced.config.refreshInterval  const 300   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.refreshContent.refreshContent  const false   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.(resourceId|resourceName)  const null   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.traversalSpecId  const ""   # render._resource_relationship_advanced_widget
widget:ResourceRelationshipAdvanced.config.filterMode  const "tagPicker"   # render._resource_relationship_advanced_widget
# AlertList (render._alert_list_widget)
widget:AlertList.config.(alertAction|alertDefinitions|alertImpact|criticalityLevel|depth|mode|state|status|type|selfProvider.selfProvider|customFilter.filterMode)  conv
widget:AlertList.config.(criticalityLevel|status|type|alertDefinitions|alertImpact|alertAction|state)[]  conv
widget:AlertList.config.alertDefinitions[].id  conv
widget:AlertList.config.relationshipMode.relationshipMode  conv
widget:AlertList.config.relationshipMode.relationshipMode[]  conv
widget:AlertList.config.refreshInterval  const 300   # render._alert_list_widget
widget:AlertList.config.refreshContent.refreshContent  const false   # render._alert_list_widget
widget:AlertList.config.resource  const []   # render._alert_list_widget
widget:AlertList.config.filterMode  const "tagPicker"   # render._alert_list_widget
widget:AlertList.config.tagFilter  const null   # render._alert_list_widget
# ResourceList (render._resource_list_widget)
widget:ResourceList.config.(tagFilter|selectFirstRow.selectFirstRow|selfProvider.selfProvider|customFilter.filterMode)  conv
widget:ResourceList.config.tagFilter.value.kind  conv
widget:ResourceList.config.tagFilter.value.kind[]  conv
widget:ResourceList.config.tagFilter.value.(state|status)  const []   # render._resource_list_widget
widget:ResourceList.config.{_TAGV}  const []   # render._resource_list_widget
widget:ResourceList.config.tagFilter.value.exclaim  const false   # render._resource_list_widget
widget:ResourceList.config.tagFilter.path[]  check tag_filter_path
widget:ResourceList.config.tagFilter.path  const []   # an empty kinds list
widget:ResourceList.config.refreshInterval  const 300   # render._resource_list_widget
widget:ResourceList.config.resource  const []   # render._resource_list_widget
widget:ResourceList.config.refreshContent.refreshContent  const false   # render._resource_list_widget
widget:ResourceList.config.relationshipMode.relationshipMode  const 0   # render._resource_list_widget
widget:ResourceList.config.additionalColumns  const []   # render._resource_list_widget
widget:ResourceList.config.mode  const "all"   # render._resource_list_widget
widget:ResourceList.config.filterMode  const "tagPicker"   # render._resource_list_widget
widget:ResourceList.config.depth  const 1   # render._resource_list_widget
# ProblemAlertsList (render._problem_alerts_list_widget)
widget:ProblemAlertsList.config.(impactedBadge|triggeredObject.triggeredObject|topIssuesDisplayLimit|resource|selfProvider.selfProvider)  conv
widget:ProblemAlertsList.config.resource.resourceId  conv
widget:ProblemAlertsList.config.resource.resourceName  check res_name ..resourceId
widget:ProblemAlertsList.config.refreshInterval  const 300   # render._problem_alerts_list_widget
widget:ProblemAlertsList.config.refreshContent.refreshContent  const true   # render._problem_alerts_list_widget
# AlertVolume (render._alert_volume_widget, wire type IntSummaryAlertVolume)
widget:IntSummaryAlertVolume.config.(refreshInterval|refreshContent.refreshContent|selfProvider.selfProvider)  conv
widget:IntSummaryAlertVolume.config.resource.resourceId  conv
widget:IntSummaryAlertVolume.config.resource.resourceName  check res_name ..resourceId
""")

# The customFilter default the renderers write on every type that has one:
# {"filter": [], "excludedResources": null, "includedResources": null}.
_CF_DEFAULT = {"filter": _flat.EMPTY_LIST_LEAF, "excludedResources": None, "includedResources": None}
_CF_TYPES = ("Scoreboard", "MetricChart", "PropertyList", "HealthChart", "ParetoAnalysis",
             "ResourceRelationshipAdvanced", "AlertList", "ResourceList")
DASHBOARD_TABLE = DASHBOARD_TABLE + [
    Rule(f"widget:{t}.config.customFilter.{k}", "const", v,
         "every type renderer: customFilter {filter: [], excludedResources: null, includedResources: null}")
    for t in _CF_TYPES for k, v in _CF_DEFAULT.items()
]

# ------------------------------------------------- stripped display text
#: Display strings the factory loaders strip of surrounding whitespace, by
#: the source key that carries each (class, generic pattern, the loader
#: line). A source value with surrounding whitespace at one of these keys is
#: a documented loss there, accepted by a verification only where the render
#: is exactly the source stripped (``model.MARK_CONDITIONS``); any other
#: change at that key is still a difference. Names are not here: the planner
#: records a stripped name as a rename. Keys, references (a pinned resource's
#: name, a view's name in a widget), enumerations, URLs and expressions are
#: not here either: stripping one changes what it means, so it stays a
#: difference.
_DLBL = "dashboard label surrounding whitespace"
_VLBL = "view column label surrounding whitespace"
_DESC = "Description surrounding whitespace"
_METRICS = "widget:(Scoreboard|MetricChart|PropertyList).config.metric.(resourceKindMetrics|resourceMetrics)[]"
STRIPPED_TEXT = {
    "view": [
        (_DESC, "ViewDef/Description#text", "dashboards.loader._load_view: description"),
        (_VLBL, f"{_COL}/Property{{(displayName|instanceGroupName|localizedMetricToRelateWith)}}@value",
         "dashboards.loader._load_column: display_name, instanced_group.name, localized_metric_to_relate_with"),
        (_VLBL, f"{_ADD}/Property{{(displayName|localizedAttributeName)}}@value",
         "dashboards.loader._load_column: display_name, localized_name"),
        (_VLBL, f"{_SUM}/Property{{displayName}}@value", "dashboards.loader._load_summary: display_name"),
    ],
    "report": [
        (_DESC, "ReportDef/Description#text", "reports.loader: description"),
    ],
    "supermetric": [
        (_DESC, "supermetric.description", "supermetrics.loader: description"),
    ],
    "dashboard": [
        (_DESC, "dashboard.description", "dashboards.loader.load_dashboard: description"),
        ("widget title surrounding whitespace", "widget:*.(title|config.title)",
         "dashboards.loader.load_dashboard: widget title (config.title is the title)"),
        ("Heatmap tab name surrounding whitespace", "widget:Heatmap.config.configs[].name",
         "dashboards.loader: Heatmap tab name"),
        (_DLBL, f"{_METRICS}.(label|metricName|unit)", "dashboards.loader: metric entry label, metric_name, unit"),
        (_DLBL, "widget:HealthChart.config.(metricName|metricFullName)",
         "dashboards.loader: HealthChart metric_name, metric_full_name"),
        (_DLBL, "widget:ParetoAnalysis.config.(metricName|metric.name)",
         "dashboards.loader: ParetoAnalysis metric_name"),
        (_DLBL, "widget:Heatmap.config.configs[].(colorBy.value|sizeBy.value|groupBy.text|groupBy.originalText)",
         "dashboards.loader: Heatmap color_by / size_by label, group_by text (originalText is the text)"),
        ("TextDisplay HTML surrounding whitespace", "widget:TextDisplay.config.editorData",
         "dashboards.loader: TextDisplay html"),
    ],
}
_STRIPPED_RX = {t: [(cls, re.compile(_pattern_rx(pat)), ev) for cls, pat, ev in rows]
                for t, rows in STRIPPED_TEXT.items()}
for _rows in STRIPPED_TEXT.values():
    for _cls, _pat, _ev in _rows:
        if _cls not in DOCUMENTED_NOT_MODELED:
            raise ValueError(f"stripped text row {_pat}: {_cls!r} is not a documented class")


def _stripped_text(type_: str, path: str):
    g = _flat.generic(path)
    for cls, rx, ev in _STRIPPED_RX.get(type_, ()):
        if rx.fullmatch(g):
            return cls, ev
    return None


TABLES = {"view": VIEW_TABLE, "report": REPORT_TABLE, "alert": ALERT_TABLE, "symptom": SYMPTOM_TABLE,
          "recommendation": RECOMMENDATION_TABLE, "supermetric": SUPERMETRIC_TABLE, "dashboard": DASHBOARD_TABLE}


# ----------------------------------------------------------------- checks
def _resolve_ref(path: str, ref: str) -> str:
    """``^key``: the widget's key; ``..key`` a sibling; ``...key`` the
    parent's sibling."""
    if ref.startswith("^"):
        m = re.match(r"^(widget\[\d+:[^\]]*\])", path)
        return f"{m.group(1)}.{ref[1:]}" if m else ref[1:]
    if ref.startswith("..."):
        base = path.rsplit(".", 2)[0]
        return f"{base}.{ref[3:]}"
    if ref.startswith(".."):
        return f"{path.rsplit('.', 1)[0]}.{ref[2:]}"
    return ref


def _rk_parts(token) -> Optional[Tuple[str, str]]:
    if isinstance(token, str) and token.startswith("RK:") and "/" in token:
        ak, rk = token[3:].split("/", 1)
        return ak, rk
    return None


def _check_tag_filter_path(path, value, leaves):
    base = path.rsplit(".path[", 1)[0]
    exp = []
    for sect, fmt in (("kind", "/source/kind/kind:{}"), ("state", "/source/state/state:{}"),
                      ("status", "/source/status/status:{}")):
        i = 0
        while f"{base}.value.{sect}[{i}]" in leaves:
            exp.append(fmt.format(leaves[f"{base}.value.{sect}[{i}]"]))
            i += 1
    idx = int(path.rsplit("[", 1)[1].rstrip("]"))
    want = exp[idx] if idx < len(exp) else None
    if value != want:
        return f"the renderer derives it from the filter's kinds, states and statuses ({want!r})"
    return None


def _group_kind(path, leaves):
    return _rk_parts(leaves.get(path.rsplit(".", 1)[0] + ".typeId"))


def _check_heatmap_group_kind(path, value, leaves):
    kinds = _group_kind(path, leaves)
    want = None if kinds is None else (kinds[0] if path.endswith(".adapterKind") else kinds[1])
    if value != want:
        return f"the renderer writes the group's kind from groupBy.typeId ({want!r})"
    return None


def _check_heatmap_group_id(path, value, leaves):
    from ..dashboards.render import adapter_kind_prefix
    kinds = _group_kind(path, leaves)
    want = None if kinds is None else f"004null{adapter_kind_prefix(kinds[0])}{kinds[0]}{kinds[1]}"
    if value != want:
        return f"the renderer derives it from groupBy.typeId ({want!r})"
    return None


def _check_heatmap_group_parent(path, value, leaves):
    kinds = _group_kind(path, leaves)
    want = None if kinds is None else kinds[0]
    if value != want:
        return f"the renderer writes the group's adapter kind ({want!r})"
    return None


def _check_res_name(path, value, leaves, ref):
    token = leaves.get(_resolve_ref(path, ref))
    want = token.split("/", 2)[2] if isinstance(token, str) and token.startswith("RES:") and token.count("/") >= 2 else None
    if value != want:
        return f"the renderer writes the name of the pinned entries resource ({want!r})"
    return None


def _check_view_pin_resource(path, value, leaves):
    from .dashboards import split_rkid
    base = path.rsplit(".", 1)[0]
    try:
        ak, rk = split_rkid(str(leaves.get(base + ".resourceKindId", "")))
    except MappingError:
        return "the pin's resourceKindId is not in the 0020<nn><adapter><kind> form"
    want = f"RES:{ak}/{rk}/{leaves.get(base + '.resourceName')}"
    if value != want:
        return f"the renderer derives it from the pin's kind and resourceName ({want!r})"
    return None


def _check_metric_bound(path, value, leaves):
    cm = leaves.get(path.rsplit(".", 1)[0] + ".colorMethod")
    if cm == 0 or value is None:
        return None
    return f"the renderer writes null here when colorMethod is {cm!r} (the bounds apply to colorMethod 0 only)"


class LossAt:
    """What a check returns for a value that is a documented loss at its
    path (rather than ``None``, accepted, or a string, a GAP)."""

    def __init__(self, cls: str, text: str, mark: Mark):
        self.cls, self.text, self.mark = cls, text, mark


_OWN_TOKEN = re.compile(r"w\d+")


def _check_widget_id_self(path, value, leaves):
    """The renderer writes the widget's own id. A source value naming no
    widget of this dashboard (in the flat form each of its widgets' ids is
    the position token ``w<j>``, so such a value is still a raw UUID) is
    clone residue: a documented loss. One naming another widget of this
    dashboard, or any other shape, is a GAP."""
    m = re.match(r"^widget\[(\d+):", path)
    want = f"w{m.group(1)}" if m else None
    if value == want:
        return None
    if m and isinstance(value, str) and re.fullmatch(_flat.UUID, value) and not _OWN_TOKEN.fullmatch(value):
        cls = "config.widgetId naming no widget of the dashboard"
        return LossAt(cls, f"{cls} is not modeled: the renderer writes the widget's own id "
                           f"({DOCUMENTED_NOT_MODELED[cls]})",
                      Mark(path, "value", cond="render writes the widget's own id"))
    if isinstance(value, str) and _OWN_TOKEN.fullmatch(value):
        return (f"it names widget {value[1:]} of this dashboard; the renderer writes the widget's own id "
                f"(config.widgetId of another widget on the dashboard is not modeled)")
    return "the renderer writes the widget's own id (config.widgetId of another shape is not modeled)"


def _check_report_content_key(path, value, leaves):
    from ..reports.loader import _STATIC_CONTENT_KEYS
    ct = leaves.get(path.rsplit("/", 1)[0] + "/ContentType#text")
    if ct in _STATIC_CONTENT_KEYS:
        want = _STATIC_CONTENT_KEYS[ct]
        if value != want:
            return f"the renderer writes {want!r} for a {ct} section (reports.loader._STATIC_CONTENT_KEYS)"
    return None  # View / Dashboard sections: the mapper converts the key


CHECKS: Dict[str, Callable] = {
    "tag_filter_path": _check_tag_filter_path,
    "heatmap_group_kind": _check_heatmap_group_kind,
    "heatmap_group_id": _check_heatmap_group_id,
    "heatmap_group_parent": _check_heatmap_group_parent,
    "view_pin_resource": _check_view_pin_resource,
    "metric_bound": _check_metric_bound,
    "report_content_key": _check_report_content_key,
    "widget_id_self": _check_widget_id_self,
    "res_name": _check_res_name,
}


# ------------------------------------------------------------- classify
def classify(type_: str, path: str) -> Optional[Rule]:
    g = _flat.generic(path)
    if type_ == "view" and _VIEW_TEXT_RX.fullmatch(g):
        return Rule(g, "const", "", "render._xml_property and the control renderers: empty elements")
    for r in TABLES[type_]:
        if r.rx.fullmatch(g):
            return r
    return None


def _gap(type_: str, path: str, why: str) -> MappingError:
    return MappingError(
        f"source key {path}: {why} (the {type_} YAML cannot carry it)",
        gap=toolset_gap(
            f"{type_} YAML: source key {_flat.generic(path)}",
            f"a source {type_} carrying {path}",
            f"convert the {type_} without dropping or changing data",
            f"add a field (or a rule with evidence to vcfcf_core/importer/accounting.py) for this key, or "
            f"document it as not modeled in the {type_} fidelity doc",
        ),
    )


def account(type_: str, leaves: _flat.Leaves, losses: List[Loss]) -> None:
    """Classify every key of one object's flat source form (module
    docstring). Records documented losses into ``losses``; raises
    ``MappingError`` (a TOOLSET GAP) at the first key that is unclassified
    or whose value the YAML cannot carry."""
    for path in sorted(leaves):
        value = leaves[path]
        rule = classify(type_, path)
        if rule is None:
            raise _gap(type_, path, "unclassified: no rule says the YAML carries it, the renderer writes it as "
                                    "a constant or derives it, or that it is a documented loss")
        st = _stripped_text(type_, path) if rule.kind in ("conv", "same") else None
        if st and isinstance(value, str) and value != value.strip():
            cls, ev = st
            documented_loss(losses, cls, f"{cls} is not modeled: the loader strips it ({DOCUMENTED_NOT_MODELED[cls]})",
                            [Mark(path, "value", cond="surrounding whitespace only")])
        if rule.kind == "conv":
            continue
        if rule.kind == "const":
            from .compare import same
            if not same(value, rule.arg, xml=type_ not in ("dashboard", "supermetric")):
                raise _gap(type_, path, f"the source has {json.dumps(value, default=str)[:80]}; the renderer always "
                                        f"writes {json.dumps(rule.arg)} ({rule.evidence})")
            continue
        if rule.kind == "same":
            other = _resolve_ref(path, rule.arg)
            if other not in leaves or leaves[other] != value:
                raise _gap(type_, path, f"the source has {json.dumps(value, default=str)[:80]}; the renderer writes "
                                        f"{other}'s value ({json.dumps(leaves.get(other), default=str)[:80]})")
            continue
        if rule.kind == "check":
            name, *rest = rule.arg.split()
            why = CHECKS[name](path, value, leaves, *rest)
            if isinstance(why, LossAt):
                documented_loss(losses, why.cls, why.text, [why.mark])
                continue
            if why:
                raise _gap(type_, path, f"the source has {json.dumps(value, default=str)[:80]}; {why}")
            continue
        if rule.kind == "loss":
            documented_loss(losses, rule.arg, f"{rule.arg} is not modeled ({DOCUMENTED_NOT_MODELED[rule.arg]})",
                            [Mark(path, "missing")])
