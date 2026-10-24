"""Default sort for a view column, and rejection of widget-level sort keys
(issue #175).

Wire evidence: knowledge/context/wire-formats/
dashboard_sort_color_default_summary_rows.md §#175. The product stores a
view's opening sort on the column Item as
``<Property name="sortCriteria" value="true|false"/>`` (true ascending,
false descending), after ``transformations`` and before ``isProperty``. The
dashboard View widget has no sort key; ``sort_by_column`` / ``sort_by_dir``
were parsed nowhere and silently dropped.

Covers:
  A. render: ``sort: asc|desc`` emits sortCriteria true/false in the vendor
     position, on that column only; no ``sort:`` emits nothing.
  B. loader: bad values, more than one sorted column, non-list views,
     time_segment and instanced_group columns are rejected.
  C. dashboard loader: sort_by_column / sort_by_dir on a View widget are
     rejected with a pointer to the view column key; HealthChart keeps
     sort_by_dir.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _view(**overrides) -> dict:
    d = {
        "name": "[VCF Content Factory] Sort Probe",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [
            {"attribute": "summary|parentCluster", "display_name": "Cluster",
             "is_property": True, "is_string_attribute": True},
            {"attribute": "cpu|usage_average", "display_name": "CPU"},
        ],
    }
    d.update(overrides)
    return d


def _write(tmp_path: Path, data: dict, name: str = "probe.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _items(tmp_path: Path, data: dict) -> list[str]:
    from vcfcf_dashboards.loader import load_view
    from vcfcf_dashboards.render import _render_view_def_fragment

    frag = _render_view_def_fragment(load_view(_write(tmp_path, data)), {})
    return re.findall(r"<Item><Value><Property name=\"objectType\".*?</Value></Item>", frag)


# A. render ------------------------------------------------------------------

@pytest.mark.parametrize("value, wire", [("asc", "true"), ("desc", "false"), ("DESC", "false")])
def test_sort_emits_sort_criteria_in_vendor_position(tmp_path, value, wire):
    data = _view()
    data["columns"][1]["sort"] = value
    unsorted, sorted_item = _items(tmp_path, data)
    assert "sortCriteria" not in unsorted
    assert (
        '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'
        f'<Property name="sortCriteria" value="{wire}"/>'
        '<Property name="isProperty" value="false"/>'
    ) in sorted_item
    assert sorted_item.count("sortCriteria") == 1


def test_sort_on_property_column(tmp_path):
    data = _view()
    data["columns"][0]["sort"] = "asc"
    item = _items(tmp_path, data)[0]
    assert (
        '<Property name="sortCriteria" value="true"/><Property name="isProperty" value="true"/>'
    ) in item


def test_no_sort_renders_no_sort_criteria(tmp_path):
    assert all("sortCriteria" not in i for i in _items(tmp_path, _view()))


def test_sorted_column_otherwise_unchanged(tmp_path):
    plain = _items(tmp_path, _view())[1]
    data = _view()
    data["columns"][1]["sort"] = "desc"
    sorted_item = _items(tmp_path, data)[1]
    assert sorted_item.replace('<Property name="sortCriteria" value="false"/>', "") == plain


# B. loader rejections --------------------------------------------------------

def _seg_view() -> dict:
    return _view(
        subject={"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD"},
        time_window={"unit": "YEARS", "count": 1},
        columns=[
            {"display_name": "Month", "time_segment": {"breakdown_by": "MONTHS"}},
            {"attribute": "cpu|usage_average", "display_name": "CPU"},
        ],
    )


def _ig_view() -> dict:
    return _view(
        subject={"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        columns=[
            {"display_name": "Disk", "instanced_group": {"name": "Disks"}},
            {"display_name": "Read", "instanced_group": {
                "name": "Disks", "prefix": "virtualDisk", "sample_instance": "scsi0:0",
                "suffix": "totalReadLatency_average"}},
        ],
    )


@pytest.mark.parametrize(
    "build, needle",
    [
        (lambda: _view(columns=[{"attribute": "a|b", "display_name": "A", "sort": "up"}]),
         "sort must be 'asc' or 'desc'"),
        (lambda: _view(columns=[{"attribute": "a|b", "display_name": "A", "sort": True}]),
         "sort must be 'asc' or 'desc'; got bool"),
        (lambda: _view(columns=[
            {"attribute": "a|b", "display_name": "A", "sort": "asc"},
            {"attribute": "c|d", "display_name": "B", "sort": "desc"},
        ]), "sort is set on 2 columns ('A', 'B'); set it on one column"),
        (lambda: _view(data_type="trend",
                       columns=[{"attribute": "a|b", "display_name": "A", "sort": "asc"}]),
         "only supported on data_type: list"),
        (lambda: _view(data_type="distribution",
                       columns=[{"attribute": "a|b", "display_name": "A", "sort": "asc"}]),
         "only supported on data_type: list"),
    ],
)
def test_loader_rejects_bad_sort(tmp_path, build, needle):
    from vcfcf_dashboards.loader import DashboardValidationError, load_view

    with pytest.raises(DashboardValidationError, match=re.escape(needle)):
        load_view(_write(tmp_path, build()))


def test_sort_on_time_segment_column_rejected(tmp_path):
    from vcfcf_dashboards.loader import DashboardValidationError, load_view

    data = _seg_view()
    data["columns"][0]["sort"] = "asc"
    with pytest.raises(DashboardValidationError, match="carry no metric fields; remove sort"):
        load_view(_write(tmp_path, data))


def test_sort_beside_time_segment_column_rejected(tmp_path):
    from vcfcf_dashboards.loader import DashboardValidationError, load_view

    data = _seg_view()
    data["columns"][1]["sort"] = "desc"
    with pytest.raises(DashboardValidationError, match="has a time_segment column"):
        load_view(_write(tmp_path, data))


def test_sort_on_instanced_group_column_rejected(tmp_path):
    from vcfcf_dashboards.loader import DashboardValidationError, load_view

    data = _ig_view()
    data["columns"][1]["sort"] = "desc"
    with pytest.raises(DashboardValidationError, match="not supported on instanced_group columns"):
        load_view(_write(tmp_path, data))


# C. dashboard widget keys ----------------------------------------------------

def _dashboard(widget_extra: dict, widget_type: str = "View") -> dict:
    w = {"id": "w1", "type": widget_type, "title": "W", "coords": {"x": 1, "y": 1, "w": 6, "h": 4}}
    if widget_type == "View":
        w["view"] = "[VCF Content Factory] Sort Probe"
    w.update(widget_extra)
    return {"name": "[VCF Content Factory] Sort Probe Dashboard", "widgets": [w]}


@pytest.mark.parametrize(
    "extra, named",
    [
        ({"sort_by_column": "CPU"}, "sort_by_column"),
        ({"sort_by_dir": "desc"}, "sort_by_dir"),
        ({"sort_by_column": "CPU", "sort_by_dir": "desc"}, "sort_by_column, sort_by_dir"),
    ],
)
def test_view_widget_sort_keys_rejected(tmp_path, extra, named):
    from vcfcf_dashboards.loader import DashboardValidationError, load_dashboard

    p = _write(tmp_path, _dashboard(extra), "dash.yaml")
    with pytest.raises(DashboardValidationError) as exc:
        load_dashboard(p)
    msg = str(exc.value)
    assert f"{named} is not supported on View widgets" in msg
    assert "`sort: asc` or `sort: desc` on one column of the view YAML" in msg


def test_sort_by_column_rejected_on_health_chart(tmp_path):
    from vcfcf_dashboards.loader import DashboardValidationError, load_dashboard

    p = _write(tmp_path, _dashboard({"sort_by_column": "x", "metric_key": "cpu|usage_average",
                                     "resource_kind": "HostSystem"}, "HealthChart"), "dash.yaml")
    with pytest.raises(DashboardValidationError, match="sort_by_column is not supported on HealthChart"):
        load_dashboard(p)


def test_health_chart_sort_by_dir_still_parsed(tmp_path):
    from vcfcf_core.dashboards.loader import load_dashboard

    p = _write(tmp_path, _dashboard({"sort_by_dir": "desc", "metric_key": "cpu|usage_average",
                                     "resource_kind": "HostSystem"}, "HealthChart"), "dash.yaml")
    d = load_dashboard(p, on_missing_id=lambda path: "11111111-1111-4111-8111-111111111111")
    assert d.widgets[0].health_chart_config.sort_by_dir == "desc"
