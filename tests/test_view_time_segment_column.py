"""Time-segment ("Interval Breakdown") view columns.

Wire evidence: reference/docs/extracted/view-time-segment/ (verbatim ViewDef
from Scott's public VCF License Consumption Overview export). The column is
a pseudo-column with isTimeSegment=true / breakdownBy=MONTHS and none of the
metric-column properties; before this change the loader had no model for
it, the renderer produced a bogus AVG metric column keyed
"Interval Breakdown", and all three reverse paths emitted it as a plain
`attribute:` column.

Covers:
  A. render: the column renders byte-identical to the export's Item.
  B. loader: attribute alongside time_segment, non-list views, stray metric
     fields, and bad units are rejected.
  C. reverse.py / extractor.py / reverse_local.py all emit time_segment
     from the evidence XML, and reverse_local's YAML re-renders identically.
  D. a view without time_segment renders exactly as before (no new bytes).
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

EVIDENCE = REPO_ROOT / "reference/docs/extracted/view-time-segment/vcf-licensing-overtime-viewdef.xml"
VIEW_ID = "6b512229-ff2c-490b-8cfb-ae70f3008de0"

EXPECTED_ITEM = (
    '<Item><Value>'
    '<Property name="objectType" value="RESOURCE"/>'
    '<Property name="attributeKey" value="Interval Breakdown"/>'
    '<Property name="rollUpCount" value="0"/>'
    '<Property name="sortCriteria" value="false"/>'
    '<Property name="isTimeSegment" value="true"/>'
    '<Property name="breakdownBy" value="MONTHS"/>'
    '<Property name="startingOnUnit" value="WEEKS"/>'
    '<Property name="startingOnCount" value="1"/>'
    '<Property name="displayName" value="Month"/>'
    '</Value></Item>'
)


def _evidence_item0() -> str:
    x = EVIDENCE.read_text()
    j = x.find("<Item>")
    k = x.find("</Item>", j) + len("</Item>")
    return re.sub(r">\s+<", "><", x[j:k])


def _base_view(**overrides) -> dict:
    d = {
        "name": "[VCF Content Factory] Segment Probe",
        "subject": {"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD"},
        "time_window": {"unit": "YEARS", "count": 1},
        "columns": [
            {"display_name": "Month", "time_segment": {"breakdown_by": "MONTHS"}},
            {"attribute": "cpu|usage_average", "display_name": "CPU"},
        ],
    }
    d.update(overrides)
    return d


def _write(tmp_path: Path, data: dict, name="probe.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _first_item(fragment: str) -> str:
    return re.search(r"<Item><Value>.*?</Value></Item>", fragment).group(0)


# A. render ------------------------------------------------------------------

def test_evidence_fixture_matches_expected_item():
    assert _evidence_item0() == EXPECTED_ITEM


def test_render_time_segment_column_byte_identical_to_export(tmp_path):
    from vcfops_dashboards.loader import load_view
    from vcfops_dashboards.render import _render_view_def_fragment

    v = load_view(_write(tmp_path, _base_view()))
    frag = _render_view_def_fragment(v, {})
    assert _first_item(frag) == _evidence_item0()
    # The metric column that follows is untouched and still a metric column.
    assert 'name="attributeKey" value="cpu|usage_average"' in frag
    assert frag.count('isTimeSegment') == 1


def test_render_honours_starting_on_overrides(tmp_path):
    from vcfops_dashboards.loader import load_view
    from vcfops_dashboards.render import _render_view_def_fragment

    data = _base_view()
    data["columns"][0]["time_segment"] = {
        "breakdown_by": "days", "starting_on_unit": "hours", "starting_on_count": 6,
    }
    v = load_view(_write(tmp_path, data))
    item = _first_item(_render_view_def_fragment(v, {}))
    assert '<Property name="breakdownBy" value="DAYS"/>' in item
    assert '<Property name="startingOnUnit" value="HOURS"/>' in item
    assert '<Property name="startingOnCount" value="6"/>' in item


# B. loader rejections --------------------------------------------------------

@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda d: d["columns"][0].update({"attribute": "x|y"}), "must not also set `attribute`"),
        (lambda d: d["columns"][0].update({"unit": "percent"}), "carry no metric fields"),
        (lambda d: d["columns"][0].update({"transformation": "AVG"}), "carry no metric fields"),
        (lambda d: d["columns"][0]["time_segment"].update({"breakdown_by": "FORTNIGHTS"}), "breakdown_by"),
        (lambda d: d["columns"][0]["time_segment"].update({"starting_on_count": 0}), "starting_on_count"),
        (lambda d: d["columns"][0]["time_segment"].pop("breakdown_by"), "breakdown_by is required"),
        (lambda d: d["columns"][0].update({"time_segment": "MONTHS"}), "must be a mapping"),
        (lambda d: d.update({"data_type": "trend"}), "only supported on data_type: list"),
    ],
)
def test_loader_rejects_bad_time_segment(tmp_path, mutate, needle):
    from vcfops_dashboards.loader import DashboardValidationError, load_view

    data = _base_view()
    mutate(data)
    with pytest.raises(DashboardValidationError, match=re.escape(needle)):
        load_view(_write(tmp_path, data))


# C. reverse paths ------------------------------------------------------------

def _viewdef_elem():
    return ET.fromstring(EVIDENCE.read_text())


def test_reverse_py_parses_time_segment_dataclass():
    from vcfops_dashboards.reverse import parse_view_from_content_xml

    wrapped = f"<Content><Views>{EVIDENCE.read_text()}</Views></Content>".encode()
    vd = parse_view_from_content_xml(wrapped, VIEW_ID)
    col0 = vd.columns[0]
    assert col0.attribute == "Interval Breakdown"
    assert col0.display_name == "Month"
    assert col0.time_segment is not None
    assert (col0.time_segment.breakdown_by, col0.time_segment.starting_on_unit,
            col0.time_segment.starting_on_count) == ("MONTHS", "WEEKS", 1)
    assert col0.transformation is None and col0.unit == ""
    assert len(vd.columns) == 7


def test_extractor_parses_time_segment_dict():
    from vcfops_extractor.extractor import _parse_view_def_element

    cols = _parse_view_def_element(_viewdef_elem())["columns"]
    assert cols[0] == {
        "display_name": "Month",
        "time_segment": {"breakdown_by": "MONTHS", "starting_on_unit": "WEEKS", "starting_on_count": 1},
    }
    assert "attribute" not in cols[0]
    assert cols[1]["attribute"].startswith("sm_")


def test_reverse_local_round_trips_time_segment(tmp_path):
    from vcfops_extractor.reverse_local import _parse_view_xml_to_dict, _write_view_yaml
    from vcfops_dashboards.loader import load_view
    from vcfops_dashboards.render import _render_view_def_fragment

    vdata = _parse_view_xml_to_dict(_viewdef_elem())
    out = tmp_path / "v.yaml"
    _write_view_yaml(out, vdata, {})
    doc = yaml.safe_load(out.read_text())
    assert "attribute" not in doc["columns"][0]
    assert doc["columns"][0]["time_segment"]["breakdown_by"] == "MONTHS"
    v = load_view(out, enforce_framework_prefix=False)
    assert _first_item(_render_view_def_fragment(v, {})) == _evidence_item0()


# D. no-regression ------------------------------------------------------------

def test_plain_view_unchanged(tmp_path):
    from vcfops_dashboards.loader import load_view
    from vcfops_dashboards.render import _render_view_def_fragment

    data = _base_view()
    data["columns"] = data["columns"][1:]
    frag = _render_view_def_fragment(load_view(_write(tmp_path, data)), {})
    assert "isTimeSegment" not in frag and "Interval Breakdown" not in frag
    assert '<Property name="rollUpType" value="AVG"/>' in frag


# F. packaging dependency audit ---------------------------------------------

def test_deps_skips_time_segment_column(tmp_path):
    """`_refs_from_view` must not audit the synthesized `Interval Breakdown`
    attributeKey (no describe-cache key exists for it); the sibling metric
    column is still audited."""
    from vcfops_dashboards.loader import load_view
    from vcfops_packaging.deps import _refs_from_view

    v = load_view(_write(tmp_path, _base_view()))
    refs = _refs_from_view(v)
    assert [r.metric_key for r in refs] == ["cpu|usage_average"]
    assert not any(r.metric_key == "Interval Breakdown" for r in refs)


@pytest.mark.slow
def test_discrete_build_over_time_segment_view_passes_audit(tmp_path, monkeypatch):
    """A bundle build (discrete path, audit ON) over a time-segment view
    succeeds against a describe cache that knows only the real metric column."""
    import json

    import vcfops_packaging.describe as describe_mod
    from vcfops_packaging.discrete_builder import build_discrete

    proj = tmp_path / "proj"
    (proj / "views").mkdir(parents=True)
    view = _base_view(subject={"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"})
    _write(proj / "views", view, name="segment_probe.yaml")

    cache_dir = tmp_path / "describe_cache"
    (cache_dir / "VMWARE").mkdir(parents=True)
    (cache_dir / "VMWARE" / "VirtualMachine.json").write_text(json.dumps({
        "adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
        "metrics": {"cpu|usage_average": {"name": "CPU Usage", "default_monitored": True}},
        "properties": {},
    }))
    monkeypatch.setattr(
        describe_mod, "make_cache",
        lambda live=True, cache_dir=None: describe_mod.DescribeCache(cache_dir=tmp_path / "describe_cache", client=None),
    )

    zip_path = build_discrete(
        content_type="view",
        item_name=view["name"],
        output_dir=tmp_path / "out",
        extra_search_dirs=[proj],
        skip_audit=False,
        live_describe=False,
        audit_mode="strict",
    )
    assert zip_path.exists()
