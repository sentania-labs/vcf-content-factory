"""View schema fidelity fields (2026-11-12).

Synthetic fixtures only. Wire format:
knowledge/context/wire-formats/view_fidelity_wire_format.md.

Each feature has: a load + render test with an exact emitted fragment, a
round trip (the rendered XML parsed back gives the Properties the YAML
asked for), and negative tests for the load errors. A last group proves
the defaults: every new field left out, or set to the value the renderer
already used, renders byte-identically to the historical output, and a
field on one view never leaks into another view rendered alongside it.
"""
from __future__ import annotations

import copy
import re
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards.loader import DashboardValidationError, load_view  # noqa: E402
from vcfcf_core.dashboards.render import (  # noqa: E402
    _render_view_def_fragment,
    render_view_def_fragments,
)

VID = "11111111-2222-4333-8444-555555555555"


def _list_view(**over) -> dict:
    d = {
        "id": VID,
        "name": "Fidelity Probe",
        "description": "synthetic",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [
            {"attribute": "cpu|usage_average", "display_name": "CPU", "unit": "percent"},
            {"attribute": "summary|version", "display_name": "Version",
             "is_property": True, "is_string_attribute": True},
        ],
        "time_window": {"unit": "DAYS", "count": 7},
    }
    d.update(over)
    return d


def _dist_view(**over) -> dict:
    d = _list_view(
        data_type="distribution",
        columns=[{"attribute": "cpu|corecount_provisioned", "display_name": "Cores"}],
    )
    d.update(over)
    return d


def _ig_view(**over) -> dict:
    d = _list_view(
        subject={"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        columns=[
            {"display_name": "Disk", "instanced_group": {"name": "GROUP_probe"}},
            {"display_name": "Read", "instanced_group": {
                "name": "GROUP_probe", "prefix": "probeDisk", "sample_instance": "d0",
                "suffix": "read_average"}},
        ],
    )
    d.update(over)
    return d


def _load(tmp_path: Path, data: dict, name: str = "v.yaml"):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_view(p, enforce_framework_prefix=False)


def _frag(tmp_path: Path, data: dict) -> str:
    return _render_view_def_fragment(_load(tmp_path, data), {})


def _xml(tmp_path: Path, data: dict) -> ET.Element:
    return ET.fromstring(_frag(tmp_path, data))


def _items(root: ET.Element, prop: str = "attributeInfos") -> list[list[tuple]]:
    """Each Item's Properties as an ordered [(name, value-or-list)]."""
    out = []
    for p in root.iter("Property"):
        if p.get("name") != prop:
            continue
        for it in p.find("List"):
            row = []
            for q in it.find("Value").findall("Property"):
                if q.get("value") is not None:
                    row.append((q.get("name"), q.get("value")))
                else:
                    row.append((q.get("name"), [i.get("value") for i in q.iter("Item")]))
            out.append(row)
    return out


def _control(root: ET.Element, ctype: str):
    for c in root.iter("Control"):
        if c.get("type") == ctype:
            return c
    return None


def _cprops(root: ET.Element, ctype: str) -> list[tuple]:
    c = _control(root, ctype)
    assert c is not None, f"no {ctype} control"
    return [(p.get("name"), p.get("value")) for p in c.findall("Property")]


def _rejects(tmp_path: Path, data: dict, needle: str) -> None:
    with pytest.raises(DashboardValidationError, match=re.escape(needle)):
        _load(tmp_path, data)


# 1. Distribution additional columns and distributionColor ---------------------

def _dist_with_additional():
    return _dist_view(
        distribution_color="37B3EB",
        additional_columns=[
            {"attribute": "cpu|usage_average", "display_name": "CPU at 95th",
             "localized_name": "CPU|Usage", "unit": "percent",
             "transformation": "PERCENTILE", "percentile": 95,
             "roll_up_type": "NONE", "sort": "asc", "show_relative_timestamp": False},
            {"attribute": "summary|version", "display_name": "Version",
             "localized_name": "Summary|Version", "is_property": True,
             "is_string_attribute": True},
        ],
    )


def test_additional_columns_render_in_metadata_in_vendor_order(tmp_path):
    frag = _frag(tmp_path, _dist_with_additional())
    assert (
        '<Property name="distributionAdditionalColumns"><List><Item><Value>'
        '<Property name="objectType" value="RESOURCE"/>'
        '<Property name="attributeKey" value="cpu|usage_average"/>'
        '<Property name="preferredUnitId" value="percent"/>'
        '<Property name="localizedAttributeName" value="CPU|Usage"/>'
        '<Property name="isStringAttribute" value="false"/>'
        '<Property name="adapterKind" value="VMWARE"/>'
        '<Property name="resourceKind" value="HostSystem"/>'
        '<Property name="rollUpType" value="NONE"/>'
        '<Property name="rollUpCount" value="0"/>'
        '<Property name="percentile" value="95"/>'
        '<Property name="transformations"><List><Item value="PERCENTILE"/></List></Property>'
        '<Property name="sortCriteria" value="true"/>'
        '<Property name="isProperty" value="false"/>'
        '<Property name="displayName" value="CPU at 95th"/>'
        '<Property name="isShowRelativeTimestamp" value="false"/>'
        '</Value></Item>'
    ) in frag
    assert frag.index("distributionAdditionalColumns") > frag.index('name="listTopResultSize"')


def test_additional_columns_round_trip(tmp_path):
    rows = _items(_xml(tmp_path, _dist_with_additional()), "distributionAdditionalColumns")
    assert rows[1] == [
        ("objectType", "RESOURCE"), ("attributeKey", "summary|version"),
        ("localizedAttributeName", "Summary|Version"), ("isStringAttribute", "true"),
        ("adapterKind", "VMWARE"), ("resourceKind", "HostSystem"), ("rollUpCount", "0"),
        ("isProperty", "true"), ("displayName", "Version"),
    ]


def test_distribution_color_after_max_points(tmp_path):
    props = _cprops(_xml(tmp_path, _dist_with_additional()), "metadata")
    assert props[:3] == [("maxPointsCount", "5000"), ("distributionColor", "37B3EB"),
                         ("hideObjectNameColumn", "false")]


def test_distribution_color_on_list_view(tmp_path):
    props = _cprops(_xml(tmp_path, _list_view(distribution_color="6870C4")), "metadata")
    assert ("distributionColor", "6870C4") in props


def test_additional_column_literal_super_metric_key_passes_through(tmp_path):
    data = _dist_view(additional_columns=[{
        "attribute": "Super Metric|sm_0a0a0a0a-0000-4000-8000-000000000001",
        "display_name": "SM", "localized_name": "Super Metrics|Probe"}])
    rows = _items(_xml(tmp_path, data), "distributionAdditionalColumns")
    assert ("attributeKey", "Super Metric|sm_0a0a0a0a-0000-4000-8000-000000000001") in rows[0]


@pytest.mark.parametrize("data, needle", [
    (_list_view(additional_columns=[{"attribute": "a|b", "display_name": "A", "localized_name": "A|B"}]),
     "additional_columns is only supported on data_type: distribution"),
    (_dist_view(additional_columns=[{"attribute": "a|b", "display_name": "A"}]),
     "localized_name is required"),
    (_dist_view(additional_columns=[{"attribute": "a|b", "display_name": "A",
                                     "localized_name": "A|B", "red_bound": 5}]),
     "do not carry red_bound"),
    (_dist_view(additional_columns=[{"attribute": 'supermetric:"Probe SM"', "display_name": "A",
                                     "localized_name": "A|B"}]),
     "only as the literal 'Super Metric|sm_<uuid>' key"),
    (_dist_view(additional_columns=[{"attribute": "a|b", "display_name": "A",
                                     "localized_name": "A|B", "omit": ["roll_up_type"]}]),
     "can only omit display_name"),
    (_dist_view(additional_columns=[]), "additional_columns must be a non-empty list"),
    (_dist_view(distribution_color="#37B3EB"), "six hex digits"),
    (_dist_view(distribution_color=123), "quoted RRGGBB string"),
    (_list_view(columns=[{"attribute": "a|b", "display_name": "A", "localized_name": "A|B"}]),
     "localized_name is only valid on additional_columns"),
])
def test_additional_column_and_color_errors(tmp_path, data, needle):
    _rejects(tmp_path, data, needle)


# 2. Buckets: ranges, isSum, explicit count / calc_function -------------------

def test_bucket_ranges_render_bucket_infos(tmp_path):
    data = _dist_view(buckets={
        "dynamic": False, "min_value": 0, "max_value": 0, "is_sum": False,
        "ranges": [{"start": 0, "end": 25, "color": "74B43B"},
                   {"start": 25, "end": 99.5}],
    })
    frag = _frag(tmp_path, data)
    assert (
        '<Control id="buckets-control_id_1" type="buckets-control" visible="false">'
        '<Property name="isDynamic" value="false"/>'
        '<Property name="minValue" value="0.0"/><Property name="maxValue" value="0.0"/>'
        '<Property name="dynamicCalcFunction" value="SIMPLEMAXMIN"/>'
        '<Property name="bucketInfos"><List>'
        '<Item><Value><Property name="startValue" value="0"/><Property name="endValue" value="25"/>'
        '<Property name="bucketColor" value="74B43B"/></Value></Item>'
        '<Item><Value><Property name="startValue" value="25"/><Property name="endValue" value="99.5"/>'
        '</Value></Item>'
        '</List></Property>'
        '<Property name="isSum" value="false"/>'
        '</Control>'
    ) in frag
    assert "bucketCount" not in frag


def test_bucket_ranges_round_trip(tmp_path):
    data = _dist_view(buckets={"dynamic": False, "ranges": [{"start": 1, "end": 2, "color": "ED891F"}]})
    rows = _items(_xml(tmp_path, data), "bucketInfos")
    assert rows == [[("startValue", "1"), ("endValue", "2"), ("bucketColor", "ED891F")]]


def test_bucket_ranges_with_explicit_count_keep_bucket_count(tmp_path):
    data = _dist_view(buckets={"dynamic": False, "count": 4, "ranges": [{"start": 0, "end": 1}]})
    assert ("bucketCount", "4") in _cprops(_xml(tmp_path, data), "buckets-control")


def test_dynamic_bucket_count_and_is_sum(tmp_path):
    data = _dist_view(buckets={"dynamic": True, "calc_function": "SIMPLEMAXMIN", "count": 10, "is_sum": True})
    assert _cprops(_xml(tmp_path, data), "buckets-control") == [
        ("isDynamic", "true"), ("dynamicCalcFunction", "SIMPLEMAXMIN"),
        ("bucketCount", "10"), ("isSum", "true"),
    ]


def test_fixed_explicit_calc_function_emitted(tmp_path):
    data = _dist_view(buckets={"dynamic": False, "calc_function": "SIMPLEMAXMIN", "count": 5})
    assert _cprops(_xml(tmp_path, data), "buckets-control") == [
        ("isDynamic", "false"), ("minValue", "0.0"), ("maxValue", "100.0"),
        ("bucketCount", "5"), ("dynamicCalcFunction", "SIMPLEMAXMIN"),
    ]


@pytest.mark.parametrize("buckets, needle", [
    ({"dynamic": True, "ranges": [{"start": 0, "end": 1}]}, "needs dynamic: false"),
    ({"dynamic": False, "calc_function": "DISCRETE", "ranges": [{"start": 0, "end": 1}]},
     "contradicts it"),
    ({"dynamic": False, "ranges": [{"start": 5, "end": 5}]}, "must be below end"),
    ({"dynamic": False, "ranges": [{"start": 0, "end": 1, "color": "red"}]}, "six hex digits"),
    ({"dynamic": False, "ranges": [{"start": "0", "end": 1}]}, "must be a number"),
    ({"dynamic": False, "ranges": [{"start": 0, "end": 1, "width": 3}]}, "must be a mapping of start"),
    ({"dynamic": False, "ranges": []}, "non-empty list"),
    ({"dynamic": True, "is_sum": "true"}, "is_sum must be a bool"),
    ({"dynamic": True, "count": 0}, "buckets.count must be a positive integer"),
])
def test_bucket_errors(tmp_path, buckets, needle):
    _rejects(tmp_path, _dist_view(buckets=buckets), needle)


def test_bucket_fidelity_fields_rejected_off_distribution(tmp_path):
    _rejects(tmp_path, _list_view(buckets={"dynamic": True, "is_sum": False}),
             "only render on data_type: distribution views")


# 3. Sort on additional columns (column sort lives in test_view_column_sort.py)

def test_sort_on_trend_view_still_rejected(tmp_path):
    data = _list_view(data_type="trend",
                      columns=[{"attribute": "cpu|usage_average", "display_name": "CPU", "sort": "asc"}])
    _rejects(tmp_path, data, "not supported on data_type: trend")


def test_bad_sort_on_additional_column_rejected(tmp_path):
    data = _dist_view(additional_columns=[{"attribute": "a|b", "display_name": "A",
                                           "localized_name": "A|B", "sort": "up"}])
    _rejects(tmp_path, data, "sort must be 'asc' or 'desc'")


# 4. Roll-up ------------------------------------------------------------------

def test_roll_up_avg_with_unit_in_vendor_order(tmp_path):
    data = _list_view(columns=[{"attribute": "cpu|usage_average", "display_name": "CPU",
                                "roll_up_type": "AVG", "roll_up_unit": "HOURS", "roll_up_count": 1}])
    frag = _frag(tmp_path, data)
    assert (
        '<Property name="rollUpType" value="AVG"/><Property name="rollUpUnit" value="HOURS"/>'
        '<Property name="rollUpCount" value="1"/>'
    ) in frag


def test_roll_up_none_count_zero_round_trip(tmp_path):
    data = _list_view(columns=[{"attribute": "cpu|usage_average", "display_name": "CPU",
                                "roll_up_type": "NONE", "roll_up_count": 0}])
    row = dict(_items(_xml(tmp_path, data))[0])
    assert (row["rollUpType"], row["rollUpCount"]) == ("NONE", "0")
    assert "rollUpUnit" not in row


def test_omit_roll_up_type(tmp_path):
    data = _list_view(columns=[{"attribute": "summary|version", "display_name": "V",
                                "is_property": True, "roll_up_count": 0, "omit": ["roll_up_type"]}])
    row = _items(_xml(tmp_path, data))[0]
    names = [n for n, _ in row]
    assert "rollUpType" not in names
    assert names[names.index("resourceKind") + 1] == "rollUpCount"


def test_roll_up_override_on_instanced_member(tmp_path):
    data = _ig_view()
    data["columns"][1].update(roll_up_type="AVG", roll_up_unit="MINUTES", roll_up_count=5)
    row = dict(_items(_xml(tmp_path, data))[1])
    assert (row["rollUpType"], row["rollUpUnit"], row["rollUpCount"]) == ("AVG", "MINUTES", "5")


@pytest.mark.parametrize("col, needle", [
    ({"roll_up_unit": "HOURS"}, "roll_up_unit needs roll_up_type: AVG"),
    ({"roll_up_type": "NONE", "roll_up_unit": "HOURS"}, "roll_up_unit needs roll_up_type: AVG"),
    ({"roll_up_type": "SUM"}, "roll_up_type must be one of"),
    ({"roll_up_type": "AVG", "roll_up_unit": "YEARS"}, "roll_up_unit must be one of"),
    ({"roll_up_count": -1}, "roll_up_count must be >= 0"),
    ({"roll_up_count": "1"}, "roll_up_count must be an integer"),
    ({"roll_up_type": 1}, "roll_up_type must be a string"),
    ({"roll_up_type": "NONE", "omit": ["roll_up_type"]}, "contradicts the column's own roll_up_type"),
])
def test_roll_up_errors(tmp_path, col, needle):
    base = {"attribute": "cpu|usage_average", "display_name": "CPU"}
    base.update(col)
    _rejects(tmp_path, _list_view(columns=[base]), needle)


def test_roll_up_on_driver_rejected(tmp_path):
    data = _ig_view()
    data["columns"][0]["roll_up_type"] = "NONE"
    _rejects(tmp_path, data, "fixed wire shape and cannot set roll_up_type")


def test_omit_roll_up_type_on_property_member_rejected(tmp_path):
    data = _ig_view()
    data["columns"][1].update(is_property=True, omit=["roll_up_type"])
    _rejects(tmp_path, data, "a property member column emits no rollUpType")


def test_roll_up_on_time_segment_rejected(tmp_path):
    data = _list_view(
        subject={"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD"},
        columns=[{"display_name": "Month", "time_segment": {"breakdown_by": "MONTHS"},
                  "roll_up_count": 0}],
    )
    _rejects(tmp_path, data, "carry no metric fields; remove roll_up_count")


# 5. useSymptomThresholds ---------------------------------------------------

def test_use_symptom_thresholds_false_before_display_name(tmp_path):
    data = _list_view(columns=[{"attribute": "cpu|usage_average", "display_name": "CPU",
                                "yellow_bound": 80, "orange_bound": 90, "red_bound": 95,
                                "ascending_range": False, "use_symptom_thresholds": False}])
    frag = _frag(tmp_path, data)
    assert (
        '<Property name="ascendingRange" value="false"/>'
        '<Property name="useSymptomThresholds" value="false"/>'
        '<Property name="displayName" value="CPU"/>'
    ) in frag


@pytest.mark.parametrize("value, needle", [
    (True, "use_symptom_thresholds only accepts false"),
    ("false", "use_symptom_thresholds must be a bool"),
])
def test_use_symptom_thresholds_errors(tmp_path, value, needle):
    data = _list_view(columns=[{"attribute": "cpu|usage_average", "display_name": "CPU",
                                "use_symptom_thresholds": value}])
    _rejects(tmp_path, data, needle)


# 6. Top N, page size, maxPointsCount, includeResourceCreationTime ----------

def test_metadata_and_pagination_values(tmp_path):
    data = _list_view(top_n=20, page_size=50, max_points_count=1000,
                      include_resource_creation_time=True)
    root = _xml(tmp_path, data)
    assert _cprops(root, "pagination-control") == [("start", "0"), ("size", "50")]
    assert _cprops(root, "metadata") == [
        ("maxPointsCount", "1000"), ("hideObjectNameColumn", "false"),
        ("listTopResultSize", "20"), ("includeResourceCreationTime", "true"),
    ]


def test_omit_metadata_and_pagination(tmp_path):
    root = _xml(tmp_path, _list_view(data_type="trend", omit=["metadata", "pagination"]))
    assert _control(root, "metadata") is None
    assert _control(root, "pagination-control") is None


def test_omit_include_resource_creation_time(tmp_path):
    props = _cprops(_xml(tmp_path, _list_view(omit=["include_resource_creation_time"])), "metadata")
    assert [n for n, _ in props] == ["maxPointsCount", "hideObjectNameColumn", "listTopResultSize"]


def test_page_size_on_distribution_adds_pagination_between_buckets_and_metadata(tmp_path):
    frag = _frag(tmp_path, _dist_view(page_size=25))
    assert frag.index("buckets-control") < frag.index("pagination-control") < frag.index('type="metadata"')
    assert '<Property name="size" value="25"/>' in frag


@pytest.mark.parametrize("data, needle", [
    (_dist_view(top_n=10), "top_n is only supported on data_type: list"),
    (_list_view(top_n=0), "top_n must be a positive integer"),
    (_list_view(page_size=0), "page_size must be a positive integer"),
    (_list_view(max_points_count=-5), "max_points_count must be a positive integer"),
    (_list_view(page_size="50"), "page_size must be an integer"),
    (_list_view(include_resource_creation_time="false"), "include_resource_creation_time must be a bool"),
    (_dist_view(omit=["pagination"]), "renders no pagination control"),
    (_list_view(page_size=50, omit=["pagination"]), "contradict each other"),
    (_list_view(top_n=5, omit=["metadata"]), "top_n would be silently lost"),
    (_list_view(hide_object_name=True, omit=["metadata"]), "hide_object_name would be silently lost"),
    (_list_view(include_resource_creation_time=False, omit=["include_resource_creation_time"]),
     "contradict each other"),
    (_list_view(omit=["metadata", "include_resource_creation_time"]), "already drops"),
    (_list_view(omit=["summary"]), "is not omittable at view level"),
    (_list_view(omit=["metadata", "metadata"]), "lists 'metadata' twice"),
    (_list_view(omit="metadata"), "omit must be a list of strings"),
])
def test_metadata_and_pagination_errors(tmp_path, data, needle):
    _rejects(tmp_path, data, needle)


# 7. Timestamps --------------------------------------------------------------

def test_timestamp_flags_render(tmp_path):
    data = _list_view(columns=[{"attribute": "config|createDate", "display_name": "Created",
                                "transformation": "TIMESTAMP", "is_property": True,
                                "add_timestamp_as_column": True, "show_relative_timestamp": True}])
    assert (
        '<Property name="displayName" value="Created"/>'
        '<Property name="addTimestampAsColumn" value="true"/>'
        '<Property name="isShowRelativeTimestamp" value="true"/></Value></Item>'
    ) in _frag(tmp_path, data)
    row = _items(_xml(tmp_path, data))[0]
    assert row[-2:] == [("addTimestampAsColumn", "true"), ("isShowRelativeTimestamp", "true")]


def test_timestamp_flags_omitted(tmp_path):
    data = _list_view(columns=[{"attribute": "cpu|usage_average", "display_name": "CPU",
                                "omit": ["add_timestamp_as_column", "show_relative_timestamp"]}])
    names = [n for n, _ in _items(_xml(tmp_path, data))[0]]
    assert names[-1] == "displayName"


@pytest.mark.parametrize("col, needle", [
    ({"add_timestamp_as_column": "true"}, "add_timestamp_as_column must be a bool"),
    ({"show_relative_timestamp": True, "omit": ["show_relative_timestamp"]}, "contradicts"),
])
def test_timestamp_errors(tmp_path, col, needle):
    base = {"attribute": "cpu|usage_average", "display_name": "CPU"}
    base.update(col)
    _rejects(tmp_path, _list_view(columns=[base]), needle)


# 8. Subject filter operators -----------------------------------------------

@pytest.mark.parametrize("cond", [
    "EQUALS", "NOT_EQUALS", "GREATER_THAN", "LESS_THAN",
    "CONTAINS", "NOT_CONTAINS", "EXISTS", "NOT_EXISTS",
])
def test_every_evidenced_filter_condition_round_trips(tmp_path, cond):
    data = _list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "filter": [
        {"filter_type": "properties", "metric_key": "summary|version", "condition": cond,
         "value": "8.", "transform": "CURRENT"}]})
    st = _xml(tmp_path, data).find("SubjectType")
    import json
    assert json.loads(st.get("filter"))[0][0]["condition"] == cond


@pytest.mark.parametrize("transform", ["LAST", "SUM", "MAX"])
def test_widened_filter_transforms_accepted(tmp_path, transform):
    data = _list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "filter": [
        {"filter_type": "metrics", "metric_key": "cpu|usage_average", "condition": "GREATER_THAN",
         "value": 1, "transform": transform}]})
    assert f"&quot;transform&quot;:&quot;{transform}&quot;" in _frag(tmp_path, data)


def test_exists_with_null_value(tmp_path):
    data = _list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "Datastore", "filter": [
        {"filter_type": "properties", "metric_key": "summary|vmfs_version", "condition": "EXISTS",
         "value": None, "string_metric": True, "transform": "CURRENT"}]})
    assert ("&quot;metricValue&quot;:{&quot;isStringMetric&quot;:true,&quot;value&quot;:null}"
            in _frag(tmp_path, data))


@pytest.mark.parametrize("cond, extra, needle", [
    ("EXISTS", {"value": None}, "needs string_metric: true|false"),
    ("EQUALS", {"value": None, "string_metric": True}, "value is required for condition"),
    ("EQUALS", {"value": "x", "string_metric": True}, "string_metric is only valid with value: null"),
    ("BETWEEN", {"value": 1}, "condition must be one of"),
])
def test_filter_errors(tmp_path, cond, extra, needle):
    c = {"filter_type": "properties", "metric_key": "summary|version", "condition": cond}
    c.update(extra)
    data = _list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "filter": [c]})
    _rejects(tmp_path, data, needle)


# 9. SubjectsGroupBy -----------------------------------------------------------

def test_group_by_after_subject_types_before_usage(tmp_path):
    data = _list_view(group_by={"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"})
    frag = _frag(tmp_path, data)
    assert (
        'type="self"/><SubjectsGroupBy adapterKind="VMWARE" resourceKind="ClusterComputeResource"/>'
        '<Usage>dashboard</Usage>'
    ) in frag


def test_owning_subject_lands_before_group_by(tmp_path):
    view = _load(tmp_path, _list_view(group_by={"adapter_kind": "VMWARE", "resource_kind": "Datacenter"}))
    frag = render_view_def_fragments([view], owning_adapter_kind="vcfcf_probe",
                                     owning_resource_kind="ProbeWorld")
    root = ET.fromstring(frag)
    tags = [c.tag for c in root]
    assert tags.index("SubjectsGroupBy") > max(i for i, t in enumerate(tags) if t == "SubjectType")
    assert root.findall("SubjectType")[-1].get("adapterKind") == "vcfcf_probe"


@pytest.mark.parametrize("data, needle", [
    (_dist_view(group_by={"adapter_kind": "VMWARE", "resource_kind": "Datacenter"}),
     "group_by is only supported on data_type: list"),
    (_list_view(group_by={"adapter_kind": "VMWARE", "resource_kind": "Datacenter", "type": "x"}),
     "group_by must be a mapping"),
    (_list_view(group_by={"adapter_kind": "VMWARE"}), "group_by requires adapter_kind and resource_kind"),
])
def test_group_by_errors(tmp_path, data, needle):
    _rejects(tmp_path, data, needle)


# 10. SubjectType sets and Usage ----------------------------------------------

def test_subject_types_descendant_only(tmp_path):
    data = _list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                               "types": ["descendant"]})
    sts = _xml(tmp_path, data).findall("SubjectType")
    assert [(s.get("resourceKind"), s.get("type")) for s in sts] == [("HostSystem", "descendant")]


def test_subjects_entry_types_and_default(tmp_path):
    data = _list_view(subject={}, subjects=[
        {"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "types": ["self", "descendant"]},
        {"adapter_kind": "VMWARE", "resource_kind": "Datastore"},
    ])
    sts = _xml(tmp_path, data).findall("SubjectType")
    assert [(s.get("resourceKind"), s.get("type")) for s in sts] == [
        ("HostSystem", "self"), ("HostSystem", "descendant"),
        ("Datastore", "descendant"), ("Datastore", "self"),
    ]


def test_usage_subset_in_product_order(tmp_path):
    root = _xml(tmp_path, _list_view(usage=["content", "dashboard", "report"]))
    assert [u.text for u in root.findall("Usage")] == ["dashboard", "report", "content"]


@pytest.mark.parametrize("data, needle", [
    (_list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "types": []}),
     "subject.types must be a non-empty list"),
    (_list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "types": ["child"]}),
     "subject.types must be a non-empty list"),
    (_list_view(subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                         "types": ["self", "self"]}), "of distinct values"),
    (_list_view(subject={}, subjects=[{"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                                       "types": "self"}]), "types must be a list of strings"),
    (_list_view(usage=[]), "usage must be a non-empty list"),
    (_list_view(usage=["dashboard", "analysis"]), "usage must be a non-empty list"),
    (_list_view(usage=["report", "report"]), "of distinct values"),
])
def test_subject_type_and_usage_errors(tmp_path, data, needle):
    _rejects(tmp_path, data, needle)


# Column omit and the string red bound ----------------------------------------

def test_column_omit_display_name_is_property_subject(tmp_path):
    data = _list_view(columns=[{"attribute": "cpu|usage_average",
                                "omit": ["display_name", "is_property", "subject"]}])
    names = [n for n, _ in _items(_xml(tmp_path, data))[0]]
    for gone in ("displayName", "isProperty", "adapterKind", "resourceKind"):
        assert gone not in names


def test_omit_ascending_range_waives_three_bound_rule(tmp_path):
    data = _list_view(columns=[{"attribute": "cpu|usage_average", "display_name": "CPU",
                                "yellow_bound": 1, "orange_bound": 2, "red_bound": 3,
                                "omit": ["ascending_range"]}])
    names = [n for n, _ in _items(_xml(tmp_path, data))[0]]
    assert "redBound" in names and "ascendingRange" not in names


def test_omit_transformation(tmp_path):
    data = _dist_view(columns=[{"attribute": "summary|version", "display_name": "V",
                                "is_property": True, "omit": ["transformation"]}])
    assert "transformations" not in [n for n, _ in _items(_xml(tmp_path, data))[0]]


def test_driver_omit_display_name(tmp_path):
    data = _ig_view()
    del data["columns"][0]["display_name"]
    data["columns"][0]["omit"] = ["display_name"]
    assert "displayName" not in [n for n, _ in _items(_xml(tmp_path, data))[0]]


def test_string_red_bound_with_ascending_true(tmp_path):
    data = _list_view(columns=[{"attribute": "summary|flag", "display_name": "Flag",
                                "is_property": True, "is_string_attribute": True,
                                "red_bound": "true", "ascending_range": True}])
    assert ('<Property name="redBound" value="true"/><Property name="ascendingRange" value="true"/>'
            in _frag(tmp_path, data))


@pytest.mark.parametrize("col, needle", [
    ({"omit": ["colour"]}, "is not omittable"),
    ({"omit": ["subject", "subject"]}, "lists 'subject' twice"),
    ({"omit": "display_name"}, "omit must be a list of field names"),
    ({"omit": ["display_name"]}, "contradicts the column's own display_name"),
    ({"omit": ["ascending_range"]}, "no numeric color bound is set"),
    ({"transformation": "MAX", "omit": ["transformation"]}, "contradicts the column's own transformation"),
    ({"is_property": True, "omit": ["is_property"]}, "contradicts the column's own is_property"),
    ({"red_bound": "Off", "ascending_range": False}, "may be omitted or true"),
])
def test_column_omit_errors(tmp_path, col, needle):
    base = {"attribute": "summary|power", "display_name": "Power"}
    base.update(col)
    _rejects(tmp_path, _list_view(columns=[base]), needle)


def test_omit_subject_on_multi_subject_rejected(tmp_path):
    data = _list_view(subject={}, subjects=[
        {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        {"adapter_kind": "VMWARE", "resource_kind": "Datastore"}],
        columns=[{"attribute": "summary|name", "display_name": "N", "omit": ["subject"]}])
    _rejects(tmp_path, data, "columns of a multi-subject view are unbound by default")


def test_driver_omit_other_than_display_name_rejected(tmp_path):
    data = _ig_view()
    data["columns"][0]["omit"] = ["transformation"]
    _rejects(tmp_path, data, "only display_name can be omitted there")


def test_omit_on_time_segment_rejected(tmp_path):
    data = _list_view(
        subject={"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD"},
        columns=[{"display_name": "Month", "time_segment": {"breakdown_by": "MONTHS"},
                  "omit": ["display_name"]}],
    )
    _rejects(tmp_path, data, "remove omit")


# Defaults: nothing moves ---------------------------------------------------

def _explicit_defaults(view: dict) -> dict:
    v = copy.deepcopy(view)
    v["subject"]["types"] = ["descendant", "self"]
    v["usage"] = ["dashboard", "report", "details", "content"]
    v["max_points_count"] = 5000
    v["include_resource_creation_time"] = False
    if v.get("data_type", "list") != "distribution":
        v["page_size"] = 500
    for c in v["columns"]:
        if "instanced_group" in c:
            continue
        c.setdefault("add_timestamp_as_column", False)
        c.setdefault("show_relative_timestamp", False)
        c.setdefault("roll_up_count", 1)
    return v


@pytest.mark.parametrize("builder", [_list_view, _dist_view, lambda: _list_view(data_type="trend")])
def test_explicit_default_values_render_byte_identical(tmp_path, builder):
    plain = _frag(tmp_path, builder())
    assert _frag(tmp_path, _explicit_defaults(builder())) == plain


def test_absent_fields_render_historical_shape(tmp_path):
    frag = _frag(tmp_path, _list_view())
    assert ('<Property name="rollUpType" value="AVG"/><Property name="rollUpCount" value="1"/>'
            in frag)
    assert ('<Control id="pagination-control_id_1" type="pagination-control" visible="true">'
            '<Property name="start" value="0"/><Property name="size" value="500"/></Control>'
            '<Control id="metadata_id_1" type="metadata" visible="false">'
            '<Property name="maxPointsCount" value="5000"/>'
            '<Property name="hideObjectNameColumn" value="false"/>'
            '<Property name="listTopResultSize" value="-1"/>'
            '<Property name="includeResourceCreationTime" value="false"/></Control>') in frag
    assert ("<Usage>dashboard</Usage><Usage>report</Usage><Usage>details</Usage>"
            "<Usage>content</Usage>") in frag
    for absent in ("rollUpUnit", "useSymptomThresholds", "distributionColor", "SubjectsGroupBy",
                   "isSum", "bucketInfos", "distributionAdditionalColumns"):
        assert absent not in frag


def test_fields_on_one_view_do_not_leak_into_another(tmp_path):
    rich = _load(tmp_path, _list_view(
        id="22222222-2222-4333-8444-555555555555", page_size=25, top_n=5,
        usage=["dashboard"], distribution_color="ED891F",
        group_by={"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
        subject={"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "types": ["descendant"]},
        columns=[{"attribute": "cpu|usage_average", "display_name": "CPU", "roll_up_type": "NONE",
                  "roll_up_count": 0, "omit": ["add_timestamp_as_column"]}],
    ), "rich.yaml")
    plain = _load(tmp_path, _list_view(), "plain.yaml")
    alone = render_view_def_fragments([plain])
    together = render_view_def_fragments([rich, plain])
    assert together.endswith(alone)
