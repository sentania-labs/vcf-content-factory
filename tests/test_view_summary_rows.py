"""List views with more than one summary (totals) row (issue #168).

Wire evidence: knowledge/context/wire-formats/
dashboard_sort_color_default_summary_rows.md §#168. ``summaryInfos`` is a
List with one ``<Item>`` per row, each carrying displayName, aggregation
and attributeIndexes in that order (vendor view ``vSphere Performance
Profiling``, two rows, quoted verbatim there).

Covers:
  A. the single-mapping and ``true`` forms render byte-identical to the
     pre-#168 single-Item output;
  B. the list form renders one Item per entry, in authored order, matching
     the vendor two-row fragment byte for byte;
  C. the loader rejects malformed summary values.
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

# Verbatim from the research doc (vendor `vSphere Performance Profiling`,
# View - Set 3.xml), the summaryInfos Property only.
VENDOR_TWO_ROWS = (
    '<Property name="summaryInfos"><List><Item><Value>'
    '<Property name="displayName" value="Average of all VMs"/>'
    '<Property name="aggregation" value="AVG"/>'
    '<Property name="attributeIndexes"><List><Item value="0"/><Item value="1"/><Item value="2"/></List></Property>'
    '</Value></Item><Item><Value>'
    '<Property name="displayName" value="Worst of all VMs"/>'
    '<Property name="aggregation" value="MAX"/>'
    '<Property name="attributeIndexes"><List><Item value="0"/><Item value="1"/><Item value="2"/></List></Property>'
    '</Value></Item></List></Property>'
)


def _view(summary) -> dict:
    d = {
        "name": "[VCF Content Factory] Summary Probe",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [
            {"attribute": "cpu|usage_average", "display_name": "CPU"},
            {"attribute": "mem|usage_average", "display_name": "Memory"},
            {"attribute": "disk|usage_average", "display_name": "Disk"},
        ],
    }
    if summary is not None:
        d["summary"] = summary
    return d


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "probe.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _summary_infos(tmp_path: Path, summary) -> str:
    from vcfcf_dashboards.loader import load_view
    from vcfcf_dashboards.render import _render_view_def_fragment

    frag = _render_view_def_fragment(load_view(_write(tmp_path, _view(summary))), {})
    m = re.search(r'<Property name="summaryInfos">.*?</List></Property>(?=</Control>|<Property)', frag)
    return m.group(0) if m else ""


def _legacy_single(display_name: str, aggregation: str, indexes) -> str:
    """The exact pre-#168 single-row output (render.py before this change)."""
    idx = "".join(f'<Item value="{i}"/>' for i in indexes)
    return (
        '<Property name="summaryInfos"><List><Item><Value>'
        f'<Property name="displayName" value="{display_name}"/>'
        f'<Property name="aggregation" value="{aggregation}"/>'
        f'<Property name="attributeIndexes"><List>{idx}</List></Property>'
        '</Value></Item></List></Property>'
    )


# A. single-row forms unchanged ------------------------------------------------

def test_true_renders_legacy_single_row(tmp_path):
    assert _summary_infos(tmp_path, True) == _legacy_single("Summary", "SUM", [0, 1, 2])


def test_mapping_renders_legacy_single_row(tmp_path):
    got = _summary_infos(tmp_path, {"display_name": "Total", "aggregation": "sum", "columns": [1, 2]})
    assert got == _legacy_single("Total", "SUM", [1, 2])


def test_one_entry_list_equals_mapping(tmp_path):
    spec = {"display_name": "Total", "aggregation": "SUM", "columns": [2]}
    assert _summary_infos(tmp_path, [spec]) == _summary_infos(tmp_path, spec)


@pytest.mark.parametrize("value", [None, False])
def test_absent_or_false_renders_nothing(tmp_path, value):
    assert _summary_infos(tmp_path, value) == ""


def test_loader_shape_is_a_list(tmp_path):
    from vcfcf_dashboards.loader import SummaryRow, load_view

    v = load_view(_write(tmp_path, _view({"display_name": "Total"})))
    assert v.summary == [SummaryRow(display_name="Total", aggregation="SUM", column_indexes=None)]
    assert load_view(_write(tmp_path, _view(None))).summary == []


# B. several rows ---------------------------------------------------------------

def test_two_rows_match_vendor_fragment(tmp_path):
    got = _summary_infos(tmp_path, [
        {"display_name": "Average of all VMs", "aggregation": "AVG"},
        {"display_name": "Worst of all VMs", "aggregation": "MAX", "columns": [0, 1, 2]},
    ])
    assert got == VENDOR_TWO_ROWS


def test_rows_keep_authored_order_and_own_columns(tmp_path):
    got = _summary_infos(tmp_path, [
        {"display_name": "Spread", "aggregation": "DEVIATION", "columns": [0]},
        {"display_name": "Total", "aggregation": "SUM", "columns": [1, 2]},
        {"display_name": "Lowest", "aggregation": "MIN", "columns": [2]},
    ])
    names = re.findall(r'name="displayName" value="([^"]+)"', got)
    aggs = re.findall(r'name="aggregation" value="([^"]+)"', got)
    idx = re.findall(r'<Property name="attributeIndexes"><List>(.*?)</List>', got)
    assert names == ["Spread", "Total", "Lowest"]
    assert aggs == ["DEVIATION", "SUM", "MIN"]
    assert idx == ['<Item value="0"/>', '<Item value="1"/><Item value="2"/>', '<Item value="2"/>']
    assert got.count('<Property name="summaryInfos">') == 1


# C. rejections -----------------------------------------------------------------

@pytest.mark.parametrize(
    "summary, needle",
    [
        ([], "must not be an empty list"),
        (["Total"], "summary[0] must be a mapping"),
        ([{"display_name": "A"}, 3], "summary[1] must be a mapping"),
        ("Total", "summary must be true, a mapping, or a list of mappings"),
        ({"aggregation": "MEDIAN"}, "aggregation 'MEDIAN' must be one of"),
        ({"aggregation": "COUNT"}, "aggregation 'COUNT' must be one of"),
        ([{"aggregation": "SUM"}, {"aggregation": "TOTAL"}], "summary row 1"),
        ({"columns": [3]}, "column indexes below 3"),
        ({"columns": []}, "columns must be a non-empty list"),
        ({"columns": "1,2"}, "columns must be a non-empty list"),
        ({"columns": [True]}, "columns must be a non-empty list"),
    ],
)
def test_loader_rejects_bad_summary(tmp_path, summary, needle):
    from vcfcf_dashboards.loader import DashboardValidationError, load_view

    with pytest.raises(DashboardValidationError, match=re.escape(needle)):
        load_view(_write(tmp_path, _view(summary)))


# Oracle EM vendor pak (reference/references/tvs/
# OracleEnterpriseManager-9.0.0_b20231005.113304.pak -> adapters.zip ->
# oem_adapter3/conf/reports/Oracle Database Instance Bottlenecks Report.xml),
# view "Oracle Databases Overview", presentation list, 13 columns, four
# summary rows ending in DEVIATION. Verbatim, whitespace between tags removed.
_OEM_IDX = "".join(f'<Item value="{i}"/>' for i in range(13))
VENDOR_OEM_FOUR_ROWS = (
    '<Property name="summaryInfos"><List>'
    + "".join(
        '<Item><Value>'
        f'<Property name="displayName" value="{name}"/>'
        f'<Property name="aggregation" value="{agg}"/>'
        f'<Property name="attributeIndexes"><List>{_OEM_IDX}</List></Property>'
        '</Value></Item>'
        for name, agg in (
            ("Minimum", "MIN"), ("Maximum", "MAX"),
            ("Average", "AVG"), ("Standard Deviation", "DEVIATION"),
        )
    )
    + '</List></Property>'
)


def test_oracle_em_deviation_shape_loads_and_renders(tmp_path):
    from vcfcf_dashboards.loader import load_view
    from vcfcf_dashboards.render import _render_view_def_fragment

    data = _view([
        {"display_name": "Minimum", "aggregation": "MIN"},
        {"display_name": "Maximum", "aggregation": "MAX"},
        {"display_name": "Average", "aggregation": "AVG"},
        {"display_name": "Standard Deviation", "aggregation": "deviation"},
    ])
    data["columns"] = [
        {"attribute": f"metric|m{i}", "display_name": f"M{i}"} for i in range(13)
    ]
    v = load_view(_write(tmp_path, data))
    assert [r.aggregation for r in v.summary] == ["MIN", "MAX", "AVG", "DEVIATION"]
    assert VENDOR_OEM_FOUR_ROWS in _render_view_def_fragment(v, {})
