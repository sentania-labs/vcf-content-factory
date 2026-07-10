"""Instanced-group view columns — loader validation + XML emission.

Covers the TOOLSET GAP closed by feat/view-instanced-group-columns: our view
renderer previously could not express the vendor's isInstancedGroup /
instanceGroupName attributes-selector construct (one row per instance of a
colon-syntax metric group, e.g. one per license name under
``vCommunity|Licensing:<name>|...``).

Vendor wire format (ground truth, RULE-016 read-only reference):
    reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/
        ESXi Host License Information vCommunity.xml
        ESXi Packages.xml
        Windows Services vCommunity.xml

All fixtures are tmp_path-local; no content YAML, network, or install
commands are touched.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml


def _write_view(tmp_path: Path, data: dict, stem: str = "view") -> Path:
    d = tmp_path / "views"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _license_view_data() -> dict:
    """Mirrors ESXi Host License Information vCommunity.xml columns 1:1."""
    return {
        "name": "[VCF Content Factory] ESXi Host License Information vCommunity",
        "description": "ESXi Host License Information vCommunity",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [
            {
                "display_name": "Instance",
                "instanced_group": {
                    "name": "GROUP_vCommunity",
                    "keep_instance_summary": True,
                },
            },
            {
                "display_name": "Edition",
                "is_property": True,
                "is_string_attribute": True,
                "instanced_group": {
                    "name": "GROUP_vCommunity",
                    "prefix": "vCommunity|Licensing",
                    "suffix": "Edition Key",
                    "sample_instance": "Evaluation Mode",
                },
            },
            {
                "display_name": "Key",
                "is_property": True,
                "is_string_attribute": True,
                "instanced_group": {
                    "name": "GROUP_vCommunity",
                    "prefix": "vCommunity|Licensing",
                    "suffix": "License Key",
                    "sample_instance": "Evaluation Mode",
                },
            },
            {
                "display_name": "Expiration Date",
                "is_property": True,
                "is_string_attribute": True,
                "instanced_group": {
                    "name": "GROUP_vCommunity",
                    "prefix": "vCommunity|Licensing",
                    "suffix": "License Expiration Date",
                    "sample_instance": "Evaluation Mode",
                },
            },
            {
                "display_name": "Days to Expire",
                "is_property": False,
                "is_string_attribute": False,
                "instanced_group": {
                    "name": "GROUP_vCommunity",
                    "prefix": "vCommunity|Licensing",
                    "suffix": "Remaining Days",
                    "sample_instance": "Evaluation Mode",
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Loader validation
# ---------------------------------------------------------------------------

class TestLoaderValidation:
    def test_hardcoded_attribute_plus_instanced_group_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = {
            "name": "X",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "columns": [
                {
                    "display_name": "Edition",
                    "attribute": "vCommunity|Licensing:Foo|Edition Key",
                    "instanced_group": {
                        "name": "GROUP_x",
                        "prefix": "vCommunity|Licensing",
                        "suffix": "Edition Key",
                        "sample_instance": "Foo",
                    },
                }
            ],
        }
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="must not also set `attribute`"):
            load_view(p, enforce_framework_prefix=False)

    def test_member_missing_sample_instance_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = {
            "name": "X",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "columns": [
                {"display_name": "Driver", "instanced_group": {"name": "GROUP_x"}},
                {
                    "display_name": "Edition",
                    "instanced_group": {
                        "name": "GROUP_x",
                        "prefix": "vCommunity|Licensing",
                        "suffix": "Edition Key",
                    },
                },
            ],
        }
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="require sample_instance"):
            load_view(p, enforce_framework_prefix=False)

    def test_prefix_without_suffix_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = {
            "name": "X",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "columns": [
                {
                    "display_name": "Edition",
                    "instanced_group": {"name": "GROUP_x", "prefix": "vCommunity|Licensing"},
                }
            ],
        }
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="prefix and instanced_group.suffix"):
            load_view(p, enforce_framework_prefix=False)

    def test_member_without_driver_in_view_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_view, DashboardValidationError

        data = {
            "name": "X",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "columns": [
                {
                    "display_name": "Edition",
                    "instanced_group": {
                        "name": "GROUP_x",
                        "prefix": "vCommunity|Licensing",
                        "suffix": "Edition Key",
                        "sample_instance": "Foo",
                    },
                }
            ],
        }
        p = _write_view(tmp_path, data)
        with pytest.raises(DashboardValidationError, match="no driver column"):
            load_view(p, enforce_framework_prefix=False)

    def test_driver_and_member_valid(self, tmp_path):
        """The full license-view fixture loads and validates cleanly."""
        from vcfops_dashboards.loader import load_view

        p = _write_view(tmp_path, _license_view_data())
        v = load_view(p, enforce_framework_prefix=False)
        v.validate(enforce_framework_prefix=False)
        assert v.columns[0].instanced_group.is_driver
        assert v.columns[0].attribute == "Instance Name"
        assert not v.columns[1].instanced_group.is_driver
        assert v.columns[1].attribute == "vCommunity|Licensing:Evaluation Mode|Edition Key"


# ---------------------------------------------------------------------------
# XML emission — byte-semantic comparison against the vendor fixture
# ---------------------------------------------------------------------------

class TestXmlEmission:
    def _render(self, tmp_path: Path):
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        p = _write_view(tmp_path, _license_view_data())
        v = load_view(p, enforce_framework_prefix=False)
        v.validate(enforce_framework_prefix=False)
        return render_views_xml([v])

    def test_driver_column_shape(self, tmp_path):
        """Driver Item matches vendor property order + values exactly.

        Ref: ESXi Host License Information vCommunity.xml:42-62.
        """
        xml = self._render(tmp_path)
        expected = (
            "<Item><Value>"
            '<Property name="objectType" value="RESOURCE"/>'
            '<Property name="attributeKey" value="Instance Name"/>'
            '<Property name="rollUpCount" value="0"/>'
            '<Property name="isInstancedGroup" value="true"/>'
            '<Property name="showInstanceName" value="true"/>'
            '<Property name="instanceGroupName" value="GROUP_vCommunity"/>'
            '<Property name="keepInstanceSummary" value="true"/>'
            '<Property name="displayName" value="Instance"/>'
            "</Value></Item>"
        )
        assert expected in xml

    def test_property_member_column_omits_rollup_type(self, tmp_path):
        """Property member columns (isProperty=true) carry no rollUpType.

        Ref: ESXi Host License Information vCommunity.xml:100-138 (Edition Key).
        """
        xml = self._render(tmp_path)
        expected = (
            "<Item><Value>"
            '<Property name="objectType" value="RESOURCE"/>'
            '<Property name="attributeKey" value="vCommunity|Licensing:Evaluation Mode|Edition Key"/>'
            '<Property name="isStringAttribute" value="true"/>'
            '<Property name="adapterKind" value="VMWARE"/>'
            '<Property name="resourceKind" value="HostSystem"/>'
            '<Property name="rollUpCount" value="0"/>'
            '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'
            '<Property name="isProperty" value="true"/>'
            '<Property name="displayName" value="Edition"/>'
            '<Property name="addTimestampAsColumn" value="false"/>'
            '<Property name="isShowRelativeTimestamp" value="false"/>'
            "</Value></Item>"
        )
        assert expected in xml
        assert "rollUpType" not in expected

    def test_metric_member_column_has_rollup_type_none(self, tmp_path):
        """Metric member column (isProperty=false) carries rollUpType=NONE.

        Ref: ESXi Host License Information vCommunity.xml:178-216 (Remaining Days).
        """
        xml = self._render(tmp_path)
        expected = (
            "<Item><Value>"
            '<Property name="objectType" value="RESOURCE"/>'
            '<Property name="attributeKey" value="vCommunity|Licensing:Evaluation Mode|Remaining Days"/>'
            '<Property name="isStringAttribute" value="false"/>'
            '<Property name="adapterKind" value="VMWARE"/>'
            '<Property name="resourceKind" value="HostSystem"/>'
            '<Property name="rollUpType" value="NONE"/>'
            '<Property name="rollUpCount" value="0"/>'
            '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'
            '<Property name="isProperty" value="false"/>'
            '<Property name="displayName" value="Days to Expire"/>'
            '<Property name="addTimestampAsColumn" value="false"/>'
            '<Property name="isShowRelativeTimestamp" value="false"/>'
            "</Value></Item>"
        )
        assert expected in xml

    def test_packages_view_shape_show_instance_name_default(self, tmp_path):
        """Member columns for a second group (Packages) also render correctly,
        and show_instance_name/keep_instance_summary default correctly when
        the driver block omits them.

        Ref: ESXi Packages.xml:42-102 (keepInstanceSummary=false there, vs
        Licensing's true — confirms the field is per-view, not hardcoded).
        """
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        data = {
            "name": "[VCF Content Factory] ESXi Packages",
            "description": "",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "columns": [
                {
                    "display_name": "Instance",
                    "instanced_group": {"name": "GROUP_vCommunity"},
                },
                {
                    "display_name": "Package Name",
                    "is_property": True,
                    "is_string_attribute": True,
                    "instanced_group": {
                        "name": "GROUP_vCommunity",
                        "prefix": "vCommunity|Configuration|Packages",
                        "suffix": "Package Name",
                        "sample_instance": "atlantic",
                    },
                },
            ],
        }
        p = _write_view(tmp_path, data, stem="packages")
        v = load_view(p, enforce_framework_prefix=False)
        v.validate(enforce_framework_prefix=False)
        xml = render_views_xml([v])
        assert '<Property name="keepInstanceSummary" value="false"/>' in xml
        assert '<Property name="showInstanceName" value="true"/>' in xml
        assert (
            '<Property name="attributeKey" value="vCommunity|Configuration|Packages:atlantic|Package Name"/>'
            in xml
        )
