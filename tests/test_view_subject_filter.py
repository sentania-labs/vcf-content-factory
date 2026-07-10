"""SubjectType metric filter (`subject.filter:`) — loader + XML emission.

Covers the TOOLSET GAP closed for the ``VM Network Top Talkers`` view port
(`knowledge/designs/managementpacks/vcommunity-vsphere-parity-closeout.md`
Fix 2): our view renderer previously could not express the vendor's
SubjectType metric filter (a JSON ``filter="..."`` attribute that restricts
the resource set the view operates on, e.g. VMs whose ``net|usage_average``
sustained above a threshold).

Vendor wire format (ground truth, RULE-016 read-only reference):
    reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
    content/reports/View - Collection01.xml:7-9 (``VM Network Top Talkers``):

      <SubjectType adapterKind="VMWARE" filter="[[{&quot;condition&quot;:
        &quot;GREATER_THAN&quot;,&quot;transform&quot;:&quot;AVG&quot;,
        &quot;metricKey&quot;:&quot;net|usage_average&quot;,&quot;metricValue
        &quot;:{&quot;isStringMetric&quot;:false,&quot;value&quot;:12},
        &quot;businessHours&quot;:false,&quot;filterType&quot;:&quot;metrics
        &quot;}]]" resourceKind="VirtualMachine" type="descendant"/>
      <SubjectType adapterKind="VMWARE" filter="[[{...same...}]]"
        resourceKind="VirtualMachine" type="self"/>

The full grammar (OR-of-AND groups, filterType metrics|properties,
condition EQUALS|NOT_EQUALS|GREATER_THAN, optional transform AVG|CURRENT,
optional businessHours) was surveyed across every ``filter="..."``
occurrence in the vendor reference corpus (~35 unique strings across
``View - Collection01.xml``, ``View - Set {1,2,3,4}.xml``, and the
Dell EMC hardware pak's ``Dell EMC Server Details Workbench.xml``).

All fixtures are tmp_path-local; no content YAML, network, or install
commands are touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def _write_view(tmp_path: Path, data: dict, stem: str = "view") -> Path:
    d = tmp_path / "views"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _base_view_data(subject_filter) -> dict:
    return {
        "name": "[VCF Content Factory] VM Network Top Talkers",
        "description": "List of VMs that use the most bandwidth.",
        "subject": {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "filter": subject_filter,
        },
        "columns": [
            {"display_name": "Name", "attribute": "summary|name", "is_property": True, "is_string_attribute": True},
        ],
    }


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestLoader:
    def test_flat_list_wraps_into_single_and_group(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "transform": "AVG",
                "business_hours": False,
            }
        ])
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        assert v.subject_filter is not None
        assert len(v.subject_filter) == 1
        assert len(v.subject_filter[0]) == 1
        cond = v.subject_filter[0][0]
        assert cond.filter_type == "metrics"
        assert cond.metric_key == "net|usage_average"
        assert cond.condition == "GREATER_THAN"
        assert cond.value == 12
        assert cond.transform == "AVG"
        assert cond.business_hours is False
        assert cond.is_string_metric is False

    def test_nested_list_is_explicit_or_of_and_groups(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        data = _base_view_data([
            [
                {
                    "filter_type": "metrics",
                    "metric_key": "sys|poweredOn",
                    "condition": "EQUALS",
                    "value": 0,
                }
            ],
            [
                {
                    "filter_type": "properties",
                    "metric_key": "runtime|connectionState",
                    "condition": "EQUALS",
                    "value": "notConnected",
                }
            ],
        ])
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        assert len(v.subject_filter) == 2
        assert v.subject_filter[0][0].value == 0
        assert v.subject_filter[1][0].value == "notConnected"
        assert v.subject_filter[1][0].is_string_metric is True

    def test_and_group_multiple_conditions(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "mem|guestOSMemNotCollecting",
                "condition": "EQUALS",
                "value": 1,
            },
            {
                "filter_type": "metrics",
                "metric_key": "summary|running",
                "condition": "EQUALS",
                "value": 1,
            },
        ])
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        assert len(v.subject_filter) == 1
        assert len(v.subject_filter[0]) == 2

    def test_no_filter_is_none(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        data = _base_view_data(None)
        del data["subject"]["filter"]
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        assert v.subject_filter is None


# ---------------------------------------------------------------------------
# Loader validation — fail closed on anything unproven
# ---------------------------------------------------------------------------

class TestLoaderValidation:
    def test_invalid_condition_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "LESS_THAN",
                "value": 12,
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="condition"):
            load_view(p, enforce_framework_prefix=False)

    def test_invalid_filter_type_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "bogus",
                "metric_key": "net|usage_average",
                "condition": "EQUALS",
                "value": 12,
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="filter_type"):
            load_view(p, enforce_framework_prefix=False)

    def test_invalid_transform_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "transform": "SUM",
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="transform"):
            load_view(p, enforce_framework_prefix=False)

    def test_business_hours_quoted_false_string_rejected(self, tmp_path):
        """Codex P2 (PR #47): bool(raw["business_hours"]) previously coerced
        ANY truthy value — including the string "false" — to True before
        validate() ran, so a quoted "false" silently became `businessHours:
        true` in the rendered XML. Must now be a loud validation failure,
        not a silent flip.
        """
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "business_hours": "false",
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="business_hours"):
            load_view(p, enforce_framework_prefix=False)

    def test_business_hours_quoted_true_string_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "business_hours": "true",
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="business_hours"):
            load_view(p, enforce_framework_prefix=False)

    def test_business_hours_unquoted_false_accepted(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "business_hours": False,
            }
        ])
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        assert v.subject_filter[0][0].business_hours is False

    def test_business_hours_unquoted_true_accepted(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "business_hours": True,
            }
        ])
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        assert v.subject_filter[0][0].business_hours is True

    def test_transform_non_string_rejected(self, tmp_path):
        """Sibling-field audit: transform must also reject non-string types
        at load time (previously silently stringified via str(x) rather
        than reported with a clear type error)."""
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "transform": 5,
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="transform"):
            load_view(p, enforce_framework_prefix=False)

    def test_condition_non_string_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": True,
                "value": 12,
            }
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="condition"):
            load_view(p, enforce_framework_prefix=False)

    def test_empty_filter_list_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="subject.filter"):
            load_view(p, enforce_framework_prefix=False)

    def test_missing_metric_key_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = _base_view_data([
            {"filter_type": "metrics", "condition": "EQUALS", "value": 1}
        ])
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="metric_key"):
            load_view(p, enforce_framework_prefix=False)


# ---------------------------------------------------------------------------
# Rendering — byte-exact against the vendor VM Network Top Talkers fixture
# ---------------------------------------------------------------------------

class TestRenderByteExact:
    _VENDOR_FILTER_ENTITY = (
        '[[{&quot;condition&quot;:&quot;GREATER_THAN&quot;,&quot;transform&quot;:'
        '&quot;AVG&quot;,&quot;metricKey&quot;:&quot;net|usage_average&quot;,'
        '&quot;metricValue&quot;:{&quot;isStringMetric&quot;:false,&quot;value&quot;:12},'
        '&quot;businessHours&quot;:false,&quot;filterType&quot;:&quot;metrics&quot;}]]'
    )

    def _render(self, tmp_path):
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        data = _base_view_data([
            {
                "filter_type": "metrics",
                "metric_key": "net|usage_average",
                "condition": "GREATER_THAN",
                "value": 12,
                "transform": "AVG",
                "business_hours": False,
            }
        ])
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        return render_views_xml([v])

    def test_filter_attribute_byte_exact_against_vendor_fixture(self, tmp_path):
        xml_text = self._render(tmp_path)
        expected_descendant = (
            f'<SubjectType adapterKind="VMWARE" filter="{self._VENDOR_FILTER_ENTITY}" '
            f'resourceKind="VirtualMachine" type="descendant"/>'
        )
        expected_self = (
            f'<SubjectType adapterKind="VMWARE" filter="{self._VENDOR_FILTER_ENTITY}" '
            f'resourceKind="VirtualMachine" type="self"/>'
        )
        assert expected_descendant in xml_text, (
            f"descendant SubjectType did not byte-match vendor fixture.\n{xml_text}"
        )
        assert expected_self in xml_text, (
            f"self SubjectType did not byte-match vendor fixture.\n{xml_text}"
        )

    def test_filter_json_parses_back_to_expected_structure(self, tmp_path):
        import html
        import re

        xml_text = self._render(tmp_path)
        m = re.search(r'<SubjectType[^>]*filter="([^"]*)"', xml_text)
        assert m is not None
        decoded = html.unescape(m.group(1))
        parsed = json.loads(decoded)
        assert parsed == [
            [
                {
                    "condition": "GREATER_THAN",
                    "transform": "AVG",
                    "metricKey": "net|usage_average",
                    "metricValue": {"isStringMetric": False, "value": 12},
                    "businessHours": False,
                    "filterType": "metrics",
                }
            ]
        ]

    def test_no_filter_emits_no_filter_attribute(self, tmp_path):
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        data = _base_view_data(None)
        del data["subject"]["filter"]
        p = _write_view(tmp_path, data)
        v = load_view(p, enforce_framework_prefix=False)
        xml_text = render_views_xml([v])
        assert "filter=" not in xml_text
