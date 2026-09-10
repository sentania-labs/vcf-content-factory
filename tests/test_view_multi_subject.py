"""Multi-subject views (`subjects:`): loader, validation, XML emission.

Closes the view-author TOOLSET GAP: ViewDef held one (adapter_kind,
resource_kind) and the renderer hardcoded two <SubjectType> elements.
VCF Ops accepts N SubjectType pairs with distinct resourceKind values in
one ViewDef. Public wire evidence (RULE-016 read-only extract):
reference/docs/extracted/view-multi-subject/ (vCommunity vSphere pak,
`vSphere Data Centers Inventory`: VMWARE Datacenter + vSphere World,
descendant then self per kind, kinds in authored sequence).

All fixtures are tmp_path-local; public VMWARE kinds only.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_EXTRACT = (
    Path(__file__).resolve().parents[1]
    / "reference/docs/extracted/view-multi-subject/vsphere-data-centers-inventory-viewdef-header.xml"
)
_ST = re.compile(r'<SubjectType adapterKind="([^"]*)"(?: filter="[^"]*")? resourceKind="([^"]*)" type="([^"]*)"/>')

VIEW_ID = "3f2e1d0c-9b8a-4765-8321-0fedcba98765"


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
        "columns": [{"attribute": "summary|total_number_hosts", "display_name": "Hosts"}],
    }
    d.update(over)
    return d


def _render(tmp_path, data) -> str:
    from vcfops_dashboards.loader import load_view
    from vcfops_dashboards.render import render_views_xml

    return render_views_xml([load_view(_write(tmp_path, data))])


def _subject_types(xml: str) -> list[tuple[str, str, str]]:
    return _ST.findall(xml)


def test_extract_is_the_vendor_shape():
    """The committed extract carries descendant+self per kind, in sequence."""
    assert _subject_types(_EXTRACT.read_text()) == [
        ("VMWARE", "Datacenter", "descendant"),
        ("VMWARE", "Datacenter", "self"),
        ("VMWARE", "vSphere World", "descendant"),
        ("VMWARE", "vSphere World", "self"),
    ]


class TestSingleSubjectRegression:
    def test_scalar_subject_emits_exactly_one_pair(self, tmp_path):
        xml = _render(tmp_path, _view())
        assert _subject_types(xml) == [
            ("VMWARE", "Datacenter", "descendant"),
            ("VMWARE", "Datacenter", "self"),
        ]

    def test_one_entry_subjects_is_byte_identical_to_scalar(self, tmp_path):
        (tmp_path / "a").mkdir()
        scalar = _render(tmp_path / "a", _view())
        (tmp_path / "b").mkdir()
        listed = _render(tmp_path / "b", _view(
            subject=None,
            subjects=[{"adapter_kind": "VMWARE", "resource_kind": "Datacenter"}],
        ))
        assert scalar == listed

    def test_scalar_fields_and_subject_kinds_default(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        v = load_view(_write(tmp_path, _view()))
        assert v.subjects == []
        assert v.subject_kinds == [("VMWARE", "Datacenter")]
        assert (v.adapter_kind, v.resource_kind) == ("VMWARE", "Datacenter")


class TestMultiSubject:
    SUBJECTS = [
        {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
        {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
    ]

    def test_renders_one_pair_per_kind_in_authored_order(self, tmp_path):
        xml = _render(tmp_path, _view(subject=None, subjects=self.SUBJECTS))
        assert _subject_types(xml) == _subject_types(_EXTRACT.read_text())
        # the pairs sit between Description and the first Usage, like the vendor
        assert xml.index("</Description>") < xml.index("<SubjectType") < xml.index("<Usage>")

    def test_reversed_order_is_preserved(self, tmp_path):
        xml = _render(tmp_path, _view(subject=None, subjects=list(reversed(self.SUBJECTS))))
        kinds = [rk for _, rk, _ in _subject_types(xml)]
        assert kinds == ["vSphere World", "vSphere World", "Datacenter", "Datacenter"]

    def test_scalar_fields_mirror_first_subject(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        v = load_view(_write(tmp_path, _view(subject=None, subjects=self.SUBJECTS)))
        assert (v.adapter_kind, v.resource_kind) == ("VMWARE", "Datacenter")
        assert v.subject_kinds == [("VMWARE", "Datacenter"), ("VMWARE", "vSphere World")]
        (tmp_path / "x").mkdir()
        xml = _render(tmp_path / "x", _view(subject=None, subjects=self.SUBJECTS))
        # Columns of a multi-subject view are unbound: no per-column
        # adapterKind/resourceKind Property (the product treats them as a
        # kind filter; see knowledge/context/api-surface/
        # view_multi_subject_column_binding.md). The kinds live on the
        # SubjectType elements only.
        assert '<Property name="resourceKind"' not in xml
        assert '<Property name="adapterKind"' not in xml
        assert 'resourceKind="Datacenter" type="self"' in xml

    def test_subject_filter_applies_to_every_subject_type(self, tmp_path):
        xml = _render(tmp_path, _view(
            subject={"filter": [{"metric_key": "summary|total_number_hosts", "condition": "GREATER_THAN", "value": 0, "filter_type": "metrics"}]},
            subjects=self.SUBJECTS,
        ))
        assert xml.count(' filter="') == 4
        assert len(_subject_types(xml)) == 4

    def test_three_kinds(self, tmp_path):
        subjects = self.SUBJECTS + [{"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"}]
        xml = _render(tmp_path, _view(subject=None, subjects=subjects))
        assert len(_subject_types(xml)) == 6


class TestRejections:
    def test_duplicate_subject_rejected(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_view

        with pytest.raises(DashboardValidationError, match="duplicate subject VMWARE:Datacenter"):
            load_view(_write(tmp_path, _view(subject=None, subjects=[
                {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
                {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
                {"adapter_kind": "VMWARE", "resource_kind": "Datacenter"},
            ])))

    def test_subjects_with_scalar_kinds_rejected(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_view

        with pytest.raises(DashboardValidationError, match="mutually exclusive"):
            load_view(_write(tmp_path, _view(subjects=[
                {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"},
            ])))

    @pytest.mark.parametrize("bad", [[], "VMWARE:Datacenter", [{"adapter_kind": "VMWARE"}],
                                     [{"adapter_kind": "VMWARE", "resource_kind": "Datacenter", "type": "self"}],
                                     ["VMWARE:Datacenter"]])
    def test_malformed_subjects_rejected(self, tmp_path, bad):
        from vcfops_dashboards.loader import DashboardValidationError, load_view

        with pytest.raises(DashboardValidationError):
            load_view(_write(tmp_path, _view(subject=None, subjects=bad)))

    def test_dataclass_guard_on_mismatched_scalar(self):
        from vcfops_dashboards.loader import (DashboardValidationError, ViewColumn, ViewDef,
                                              ViewSubject)

        v = ViewDef(name="[VCF Content Factory] X", description="", adapter_kind="VMWARE",
                    resource_kind="HostSystem", id=VIEW_ID,
                    columns=[ViewColumn(attribute="a|b", display_name="A")],
                    subjects=[ViewSubject("VMWARE", "Datacenter")])
        with pytest.raises(DashboardValidationError, match="mirror subjects"):
            v.validate()


class TestDependencyAudit:
    """packaging.deps._refs_from_view audits every subject kind (third-pass
    W1): a column can be policy-disabled on the second kind while enabled on
    the first, so one MetricReference per (kind, key) is required."""

    SUBJECTS = TestMultiSubject.SUBJECTS

    def _refs(self, tmp_path, data):
        from vcfops_dashboards.loader import load_view
        from vcfops_packaging.deps import _refs_from_view

        return _refs_from_view(load_view(_write(tmp_path, data)))

    def test_two_kind_view_emits_one_ref_per_kind(self, tmp_path):
        refs = self._refs(tmp_path, _view(subject=None, subjects=self.SUBJECTS))
        assert [(r.adapter_kind, r.resource_kind, r.metric_key) for r in refs] == [
            ("VMWARE", "Datacenter", "summary|total_number_hosts"),
            ("VMWARE", "vSphere World", "summary|total_number_hosts"),
        ]
        assert {r.source_desc for r in refs} == {"view '[VCF Content Factory] Inventory'"}

    def test_subject_filter_keys_audited_per_kind(self, tmp_path):
        refs = self._refs(tmp_path, _view(
            subject={"filter": [{"metric_key": "summary|number_running_vms", "condition": "GREATER_THAN",
                                 "value": 0, "filter_type": "metrics"}]},
            subjects=self.SUBJECTS,
        ))
        assert [(r.resource_kind, r.metric_key) for r in refs] == [
            ("Datacenter", "summary|total_number_hosts"),
            ("Datacenter", "summary|number_running_vms"),
            ("vSphere World", "summary|total_number_hosts"),
            ("vSphere World", "summary|number_running_vms"),
        ]

    def test_scalar_subject_unchanged(self, tmp_path):
        refs = self._refs(tmp_path, _view())
        assert [(r.adapter_kind, r.resource_kind, r.metric_key) for r in refs] == [
            ("VMWARE", "Datacenter", "summary|total_number_hosts"),
        ]


class TestReverseParsers:
    """Third-pass W2: the three XML-to-YAML parsers used to keep the first
    SubjectType silently. Against the committed extract they must now
    populate `subjects` in document order, and the written YAML must load
    back with the same subject_kinds. Single-subject views are unchanged."""

    KINDS = [("VMWARE", "Datacenter"), ("VMWARE", "vSphere World")]
    SINGLE = (
        '<ViewDef id="%s"><Title>One</Title>'
        '<SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="descendant"/>'
        '<SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="self"/>'
        '</ViewDef>' % VIEW_ID
    )
    COLUMN = {"attribute": "summary|total_number_hosts", "display_name": "Hosts"}

    @staticmethod
    def _elem(xml: str):
        import xml.etree.ElementTree as ET

        return ET.fromstring(xml)

    @classmethod
    def _extract_elem(cls):
        # the committed extract is the ViewDef header only (RULE-016 fixture)
        return cls._elem(_EXTRACT.read_text() + "</ViewDef>")

    def test_dataclass_parser_populates_subjects_in_document_order(self):
        from vcfops_dashboards.reverse import parse_view_xml_element

        vd = parse_view_xml_element(self._extract_elem())
        assert vd.subject_kinds == self.KINDS
        assert (vd.adapter_kind, vd.resource_kind) == self.KINDS[0]

    def test_dataclass_parser_single_subject_leaves_subjects_empty(self):
        from vcfops_dashboards.reverse import parse_view_xml_element

        vd = parse_view_xml_element(self._elem(self.SINGLE))
        assert vd.subjects == []
        assert vd.subject_kinds == [("VMWARE", "HostSystem")]

    @pytest.mark.parametrize("parser", ["extractor", "reverse_local"])
    def test_dict_parsers_populate_subjects(self, parser):
        if parser == "extractor":
            from vcfops_extractor.extractor import _parse_view_def_element as parse
        else:
            from vcfops_extractor.reverse_local import _parse_view_xml_to_dict as parse

        data = parse(self._extract_elem())
        assert data["subjects"] == [
            {"adapter_kind": ak, "resource_kind": rk} for ak, rk in self.KINDS
        ]
        assert (data["adapter_kind"], data["resource_kind"]) == self.KINDS[0]
        assert parse(self._elem(self.SINGLE))["subjects"] == []

    @pytest.mark.parametrize("writer", ["extractor", "reverse_local"])
    def test_written_yaml_round_trips_subjects(self, tmp_path, writer):
        from vcfops_dashboards.loader import load_view

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

        data = parse(self._extract_elem())
        data["columns"] = [dict(self.COLUMN)]
        out = tmp_path / "multi.yaml"
        write(out, data)
        doc = yaml.safe_load(out.read_text())
        assert "subject" not in doc
        assert doc["subjects"] == [
            {"adapter_kind": ak, "resource_kind": rk} for ak, rk in self.KINDS
        ]
        assert load_view(out, enforce_framework_prefix=False).subject_kinds == self.KINDS

        single = parse(self._elem(self.SINGLE))
        single["columns"] = [dict(self.COLUMN)]
        out1 = tmp_path / "single.yaml"
        write(out1, single)
        doc1 = yaml.safe_load(out1.read_text())
        assert "subjects" not in doc1
        assert doc1["subject"] == {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"}
