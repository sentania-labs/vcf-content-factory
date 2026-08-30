"""Per-column kind binding on multi-subject views.

On the product a column's adapterKind/resourceKind Properties are a kind
filter: a bound column renders null on rows of every other subject kind.
Vendor multi-subject views leave their shared columns unbound and bind only
the columns that belong to one kind. Wire format:
knowledge/context/wire-formats/view_column_wire_format.md.

Contract under test:
  1. 2+ `subjects:` -> columns unbound by default (no adapterKind, no
     resourceKind; isStringAttribute is followed directly by rollUpType),
     on both the generic and the instanced-group member column paths.
  2. Optional per-column `subject:` binds that column to one of the
     view's subjects; a subject not in `subjects:` is a loader error.
  3. Single-subject views are byte-identical to the historical output.
  4. Reverse path: unbound -> no `subject:`; bound (multi-subject) ->
     per-column `subject:`; single-subject -> never a `subject:`.

All fixtures are tmp_path-local; public VMWARE kinds only.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

VIEW_ID = "5a6b7c8d-1e2f-4a3b-9c0d-1e2f3a4b5c6d"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "multi_subject_viewdef.xml"

SUBJECTS = [
    {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
    {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
]
_ITEM = re.compile(r"<Item>\s*<Value>(.*?)</Value>\s*</Item>", re.DOTALL)
_PROP = re.compile(r'<Property name="([^"]+)"')


def _write(tmp_path: Path, data: dict, name="v.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


def _view(**over) -> dict:
    d = {
        "id": VIEW_ID,
        "name": "[VCF Content Factory] Inventory",
        "description": "d",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
        "columns": [
            {"attribute": "summary|total_number_hosts", "display_name": "Hosts"},
            {"attribute": "summary|total_number_vms", "display_name": "VMs"},
        ],
    }
    d.update(over)
    return d


def _load(tmp_path, data):
    from vcfops_dashboards.loader import load_view

    return load_view(_write(tmp_path, data))


def _render(tmp_path, data) -> str:
    from vcfops_dashboards.render import render_views_xml

    return render_views_xml([_load(tmp_path, data)])


def _column_items(xml: str) -> list[str]:
    return _ITEM.findall(xml)


def _prop_names(item: str) -> list[str]:
    return _PROP.findall(item)


def _binding(item: str):
    ak = re.search(r'<Property name="adapterKind" value="([^"]*)"', item)
    rk = re.search(r'<Property name="resourceKind" value="([^"]*)"', item)
    if ak is None and rk is None:
        return None
    return (ak.group(1) if ak else "", rk.group(1) if rk else "")


# ---------------------------------------------------------------------------
# Fixture sanity: the checked-in vendor-shape multi-subject ViewDef leaves
# its shared column unbound and binds the kind-specific column to the
# second subject (the contract we implement).
# ---------------------------------------------------------------------------

def test_fixture_multi_subject_shared_column_is_unbound():
    xml = _FIXTURE.read_text()
    assert xml.count('type="self"') > 1, "fixture must be multi-subject"
    items = [i for i in _column_items(xml) if 'name="attributeKey"' in i]
    assert items, "fixture must carry attribute Items"
    shared = [i for i in items if _binding(i) is None]
    assert shared, "fixture must carry an unbound shared column"
    for item in shared:
        names = _prop_names(item)
        assert names[names.index("isStringAttribute") + 1] == "rollUpType"
    bound = [b for b in map(_binding, items) if b is not None]
    assert bound == [("VMWARE", "vSphere World")]


# ---------------------------------------------------------------------------
# 1. Multi-subject default: unbound
# ---------------------------------------------------------------------------

class TestMultiSubjectUnboundDefault:
    def test_no_kind_properties_on_any_column(self, tmp_path):
        xml = _render(tmp_path, _view(subject=None, subjects=SUBJECTS))
        items = _column_items(xml)
        assert len(items) == 2
        for item in items:
            assert _binding(item) is None
            names = _prop_names(item)
            # isStringAttribute is followed directly by rollUpType
            i = names.index("isStringAttribute")
            assert names[i + 1] == "rollUpType"

    def test_everything_else_in_the_item_is_unchanged(self, tmp_path):
        (tmp_path / "s").mkdir()
        (tmp_path / "m").mkdir()
        single = _column_items(_render(tmp_path / "s", _view()))
        multi = _column_items(_render(tmp_path / "m", _view(subject=None, subjects=SUBJECTS)))
        strip = re.compile(r'<Property name="(?:adapterKind|resourceKind)" value="[^"]*"/>')
        assert [strip.sub("", i) for i in single] == multi

    def test_instanced_group_member_column_is_unbound(self, tmp_path):
        cols = [
            {"display_name": "Instance", "instanced_group": {"name": "vmdk"}},
            {
                "display_name": "Used",
                "instanced_group": {
                    "name": "vmdk", "prefix": "diskspace", "suffix": "used",
                    "sample_instance": "vm-1",
                },
            },
        ]
        xml = _render(tmp_path, _view(subject=None, subjects=SUBJECTS, columns=cols))
        member = [i for i in _column_items(xml) if 'value="diskspace:vm-1|used"' in i]
        assert len(member) == 1
        assert _binding(member[0]) is None
        names = _prop_names(member[0])
        assert names[names.index("isStringAttribute") + 1] == "rollUpType"

    def test_subject_types_still_one_pair_per_kind(self, tmp_path):
        xml = _render(tmp_path, _view(subject=None, subjects=SUBJECTS))
        assert xml.count("<SubjectType ") == 4


# ---------------------------------------------------------------------------
# 2. Per-column `subject:` override
# ---------------------------------------------------------------------------

class TestPerColumnSubject:
    def test_bound_column_names_that_kind_others_stay_unbound(self, tmp_path):
        cols = [
            {"attribute": "summary|total_number_hosts", "display_name": "Hosts"},
            {
                "attribute": "summary|parentVcenter", "display_name": "vCenter",
                "is_property": True, "is_string_attribute": True,
                "subject": {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
            },
            {
                "attribute": "summary|total_number_vms", "display_name": "VMs",
                "subject": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
            },
        ]
        xml = _render(tmp_path, _view(subject=None, subjects=SUBJECTS, columns=cols))
        items = _column_items(xml)
        assert [_binding(i) for i in items] == [
            None,
            ("VMWARE", "Datacenter"),
            ("VMWARE", "vSphere World"),  # not subjects[0]
        ]
        # bound Item keeps the historical property order
        names = _prop_names(items[2])
        i = names.index("isStringAttribute")
        assert names[i + 1:i + 4] == ["adapterKind", "resourceKind", "rollUpType"]

    def test_bound_instanced_group_member(self, tmp_path):
        cols = [
            {"display_name": "Instance", "instanced_group": {"name": "vmdk"}},
            {
                "display_name": "Used",
                "instanced_group": {
                    "name": "vmdk", "prefix": "diskspace", "suffix": "used",
                    "sample_instance": "vm-1",
                },
                "subject": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
            },
        ]
        xml = _render(tmp_path, _view(subject=None, subjects=SUBJECTS, columns=cols))
        member = [i for i in _column_items(xml) if 'value="diskspace:vm-1|used"' in i][0]
        assert _binding(member) == ("VMWARE", "vSphere World")

    def test_loader_exposes_column_subject(self, tmp_path):
        cols = [{
            "attribute": "summary|total_number_vms", "display_name": "VMs",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
        }]
        v = _load(tmp_path, _view(subject=None, subjects=SUBJECTS, columns=cols))
        assert v.columns[0].subject is not None
        assert v.columns[0].subject.key == ("VMWARE", "vSphere World")


# ---------------------------------------------------------------------------
# 2b. Loader rejection
# ---------------------------------------------------------------------------

class TestLoaderRejects:
    def test_subject_not_in_subjects(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError

        cols = [{
            "attribute": "cpu|usage_average", "display_name": "CPU",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        }]
        with pytest.raises(DashboardValidationError, match="not one of the view's subjects"):
            _load(tmp_path, _view(subject=None, subjects=SUBJECTS, columns=cols))

    def test_subject_on_column_of_single_subject_view(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError

        cols = [{
            "attribute": "cpu|usage_average", "display_name": "CPU",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
        }]
        with pytest.raises(DashboardValidationError, match="declares no subjects"):
            _load(tmp_path, _view(columns=cols))

    @pytest.mark.parametrize("bad", [
        "VMWARE:Datacenter",
        {"adapter_kind": "VMWARE"},
        {"adapter_kind": "VMWARE", "resource_kind": "Datacenter", "filter": "x"},
    ])
    def test_malformed_subject(self, tmp_path, bad):
        from vcfops_dashboards.loader import DashboardValidationError

        cols = [{"attribute": "cpu|usage_average", "display_name": "CPU", "subject": bad}]
        with pytest.raises(DashboardValidationError):
            _load(tmp_path, _view(subject=None, subjects=SUBJECTS, columns=cols))


# ---------------------------------------------------------------------------
# 3. Single-subject views unchanged
# ---------------------------------------------------------------------------

class TestSingleSubjectUnchanged:
    def test_every_column_bound_to_the_one_kind(self, tmp_path):
        xml = _render(tmp_path, _view())
        items = _column_items(xml)
        assert len(items) == 2
        for item in items:
            assert _binding(item) == ("VMWARE", "Datacenter")
            names = _prop_names(item)
            i = names.index("isStringAttribute")
            assert names[i + 1:i + 4] == ["adapterKind", "resourceKind", "rollUpType"]

    def test_one_entry_subjects_list_is_still_bound(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        scalar = _render(tmp_path / "a", _view())
        listed = _render(tmp_path / "b", _view(subject=None, subjects=SUBJECTS[:1]))
        assert scalar == listed

    def test_instanced_group_member_still_bound(self, tmp_path):
        cols = [
            {"display_name": "Instance", "instanced_group": {"name": "vmdk"}},
            {
                "display_name": "Used",
                "instanced_group": {
                    "name": "vmdk", "prefix": "diskspace", "suffix": "used",
                    "sample_instance": "vm-1",
                },
            },
        ]
        xml = _render(tmp_path, _view(columns=cols))
        member = [i for i in _column_items(xml) if 'value="diskspace:vm-1|used"' in i][0]
        assert _binding(member) == ("VMWARE", "Datacenter")


# ---------------------------------------------------------------------------
# 4. Reverse path round-trip
# ---------------------------------------------------------------------------

def _viewdef_xml(subjects: list[tuple[str, str]], columns: list[tuple[str, tuple | None]]) -> str:
    st = "".join(
        f'<SubjectType adapterKind="{ak}" resourceKind="{rk}" type="descendant"/>'
        f'<SubjectType adapterKind="{ak}" resourceKind="{rk}" type="self"/>'
        for ak, rk in subjects
    )
    items = []
    for key, binding in columns:
        bind = (
            f'<Property name="adapterKind" value="{binding[0]}"/>'
            f'<Property name="resourceKind" value="{binding[1]}"/>'
            if binding else ""
        )
        items.append(
            '<Item><Value><Property name="objectType" value="RESOURCE"/>'
            f'<Property name="attributeKey" value="{key}"/>'
            '<Property name="isStringAttribute" value="false"/>'
            + bind +
            '<Property name="rollUpType" value="AVG"/><Property name="rollUpCount" value="1"/>'
            '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'
            '<Property name="isProperty" value="false"/>'
            f'<Property name="displayName" value="{key.split("|")[-1]}"/>'
            '</Value></Item>'
        )
    return (
        f'<ViewDef id="{VIEW_ID}"><Title>[VCF Content Factory] Inventory</Title>'
        f'<Description>d</Description>{st}'
        '<Controls><Control type="attributes-selector"><Property name="attributeInfos"><List>'
        + "".join(items) +
        '</List></Property></Control></Controls></ViewDef>'
    )


MULTI = [("VMWARE", "Datacenter"), ("VMWARE", "vSphere World")]
COLS = [
    ("summary|total_number_hosts", None),
    ("summary|total_number_vms", ("VMWARE", "vSphere World")),
]


class TestReverse:
    @staticmethod
    def _elem(xml: str):
        import xml.etree.ElementTree as ET

        return ET.fromstring(xml)

    def test_dataclass_parser_multi_subject(self):
        from vcfops_dashboards.reverse import parse_view_xml_element

        vd = parse_view_xml_element(self._elem(_viewdef_xml(MULTI, COLS)))
        assert vd.columns[0].subject is None
        assert vd.columns[1].subject.key == ("VMWARE", "vSphere World")

    def test_dataclass_parser_single_subject_drops_binding(self):
        from vcfops_dashboards.reverse import parse_view_xml_element

        xml = _viewdef_xml(MULTI[:1], [("summary|total_number_hosts", ("VMWARE", "Datacenter"))])
        vd = parse_view_xml_element(self._elem(xml))
        assert vd.subjects == []
        assert vd.columns[0].subject is None

    @pytest.mark.parametrize("parser", ["extractor", "reverse_local"])
    def test_dict_parsers(self, parser):
        if parser == "extractor":
            from vcfops_extractor.extractor import _parse_view_def_element as parse
        else:
            from vcfops_extractor.reverse_local import _parse_view_xml_to_dict as parse

        data = parse(self._elem(_viewdef_xml(MULTI, COLS)))
        assert "subject" not in data["columns"][0]
        assert data["columns"][1]["subject"] == {
            "adapter_kind": "VMWARE", "resource_kind": "vSphere World",
        }
        single = parse(self._elem(_viewdef_xml(
            MULTI[:1], [("summary|total_number_hosts", ("VMWARE", "Datacenter"))]
        )))
        assert all("subject" not in c for c in single["columns"])

    @pytest.mark.parametrize("writer", ["extractor", "reverse_local"])
    def test_round_trip_through_yaml_and_render(self, tmp_path, writer):
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        if writer == "extractor":
            from vcfops_extractor.extractor import _parse_view_def_element as parse
            from vcfops_extractor.extractor import _write_view_yaml

            def write(path, data):
                _write_view_yaml(path, data)
        else:
            from vcfops_extractor.reverse_local import _parse_view_xml_to_dict as parse
            from vcfops_extractor.reverse_local import _write_view_yaml

            def write(path, data):
                _write_view_yaml(path, data, {})

        src = _viewdef_xml(MULTI, COLS)
        out = tmp_path / "multi.yaml"
        write(out, parse(self._elem(src)))
        doc = yaml.safe_load(out.read_text())
        assert "subject" not in doc["columns"][0]
        assert doc["columns"][1]["subject"] == {
            "adapter_kind": "VMWARE", "resource_kind": "vSphere World",
        }
        v = load_view(out)
        rendered = render_views_xml([v])
        items = _column_items(rendered)
        assert [_binding(i) for i in items] == [None, ("VMWARE", "vSphere World")]
        # and the binding survives a second reverse pass
        from vcfops_dashboards.reverse import parse_view_xml_element
        import xml.etree.ElementTree as ET

        vd_elem = ET.fromstring(rendered).find(".//ViewDef")
        if vd_elem is None:
            root = ET.fromstring(rendered)
            vd_elem = root if root.tag.endswith("ViewDef") else next(
                e for e in root.iter() if e.tag.split("}")[-1] == "ViewDef"
            )
        vd2 = parse_view_xml_element(vd_elem)
        assert vd2.columns[0].subject is None
        assert vd2.columns[1].subject.key == ("VMWARE", "vSphere World")
