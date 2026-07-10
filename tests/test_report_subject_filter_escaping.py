"""Report-level SubjectType ``filter=`` attribute — XML-escaping regression.

Bug (routed from sdk-adapter-author build 8): ``render_report_xml`` escaped
the SubjectType ``filter=`` attribute with plain ``xml.sax.saxutils.escape()``
— no quote-entity map — so a report-level subject filter (which is itself a
JSON string full of double quotes) rendered as invalid XML: unescaped ``"``
characters broke out of the attribute. The VIEW path
(``vcfops_dashboards.render``) already handles this correctly via
``escape(filter_json, {chr(34): "&quot;"})`` (PR #47). This test locks the
report path to the same treatment.

Vendor ground truth (RULE-016 read-only reference):
    reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
    content/reports/Report - VOA - Supervisor Cluster for CSV export.xml

    <SubjectType adapterKind="VMWARE" filter="[[{&quot;condition&quot;:
      &quot;EQUALS&quot;,&quot;metricKey&quot;:&quot;configuration|
      wpConfiguration|wpEnabled&quot;,&quot;metricValue&quot;:{&quot;
      isStringMetric&quot;:true,&quot;value&quot;:&quot;true&quot;},
      &quot;filterType&quot;:&quot;properties&quot;}]]"
      resourceKind="ClusterComputeResource" type="descendant"/>

    Note the ``&quot;`` entity encoding every embedded double quote — the
    same treatment the view renderer already applies.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from vcfops_reports.loader import load_file
from vcfops_reports.render import render_report_xml

# The raw (unescaped) filter JSON the author writes in YAML, taken verbatim
# from the vendor's Supervisor Cluster report.
_RAW_FILTER_JSON = (
    '[[{"condition":"EQUALS","metricKey":"configuration|wpConfiguration|'
    'wpEnabled","metricValue":{"isStringMetric":true,"value":"true"},'
    '"filterType":"properties"}]]'
)

# The byte-exact vendor encoding of that same string inside a filter="..."
# attribute (every " -> &quot;).
_VENDOR_FILTER_ENTITY = (
    '[[{&quot;condition&quot;:&quot;EQUALS&quot;,&quot;metricKey&quot;:'
    '&quot;configuration|wpConfiguration|wpEnabled&quot;,&quot;metricValue'
    '&quot;:{&quot;isStringMetric&quot;:true,&quot;value&quot;:&quot;true'
    '&quot;},&quot;filterType&quot;:&quot;properties&quot;}]]'
)


def _write_report(tmp_path: Path) -> Path:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "views").mkdir(parents=True, exist_ok=True)
    (tmp_path / "dashboards").mkdir(parents=True, exist_ok=True)

    data = {
        "name": "[VCF Content Factory] Supervisor Cluster VOA",
        "description": "Supervisor cluster VOA export with a subject filter.",
        "subject_types": [
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "ClusterComputeResource",
                "type": "descendant",
                "filter": _RAW_FILTER_JSON,
            }
        ],
        "sections": [
            {"type": "CoverPage"},
            {"type": "TableOfContents"},
        ],
        "settings": {
            "show_page_footer": True,
            "output_formats": ["pdf", "csv"],
        },
    }
    p = reports_dir / "supervisor-cluster-voa.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


class TestReportSubjectFilterEscaping:
    def _render(self, tmp_path: Path) -> str:
        p = _write_report(tmp_path)
        rd = load_file(
            p,
            views_dir=tmp_path / "views",
            dashboards_dir=tmp_path / "dashboards",
            enforce_framework_prefix=False,
        )
        return render_report_xml([rd])

    def test_filter_attribute_byte_exact_against_vendor_fixture(self, tmp_path):
        xml_text = self._render(tmp_path)
        expected = (
            f'<SubjectType adapterKind="VMWARE" '
            f'resourceKind="ClusterComputeResource" type="descendant" '
            f'filter="{_VENDOR_FILTER_ENTITY}"/>'
        )
        assert expected in xml_text, (
            f"SubjectType filter attribute did not byte-match vendor "
            f"fixture.\n{xml_text}"
        )

    def test_filter_json_round_trips_to_expected_structure(self, tmp_path):
        import html
        import re

        xml_text = self._render(tmp_path)
        m = re.search(r'<SubjectType[^>]*filter="([^"]*)"', xml_text)
        assert m is not None
        decoded = html.unescape(m.group(1))
        assert json.loads(decoded) == json.loads(_RAW_FILTER_JSON)

    def test_emitted_xml_parses(self, tmp_path):
        """Guard: the emitted report content.xml must be well-formed XML —
        a plain (non-quote-aware) escape() call would break this by leaving
        raw ``"`` characters inside the filter="..." attribute value."""
        xml_text = self._render(tmp_path)
        root = ET.fromstring(xml_text)
        assert root.tag == "Content"

    def test_no_filter_emits_no_filter_attribute(self, tmp_path):
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "views").mkdir(parents=True, exist_ok=True)
        (tmp_path / "dashboards").mkdir(parents=True, exist_ok=True)

        data = {
            "name": "[VCF Content Factory] No Filter Report",
            "description": "No subject filter here.",
            "subject_types": [
                {
                    "adapter_kind": "VMWARE",
                    "resource_kind": "VirtualMachine",
                    "type": "self",
                }
            ],
            "sections": [{"type": "CoverPage"}],
            "settings": {"show_page_footer": True, "output_formats": ["pdf"]},
        }
        p = reports_dir / "no-filter.yaml"
        p.write_text(yaml.dump(data, default_flow_style=False))
        rd = load_file(
            p,
            views_dir=tmp_path / "views",
            dashboards_dir=tmp_path / "dashboards",
            enforce_framework_prefix=False,
        )
        xml_text = render_report_xml([rd])
        assert "filter=" not in xml_text
