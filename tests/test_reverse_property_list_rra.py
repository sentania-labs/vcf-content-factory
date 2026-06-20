"""Unit tests for PropertyList and ResourceRelationshipAdvanced reverse parsers.

Covers:
  F. _parse_property_list_config: wire JSON → PropertyListConfig with correct
     fields including is_string_metric propagation.
  G. _parse_resource_relationship_advanced_config: wire JSON →
     ResourceRelationshipAdvancedConfig with kind resolution and depth string.
  H. PropertyList round-trip: source widget JSON → parse_dashboard_json produces
     correct dataclass → forward-render → structural MATCH against source widget.
  I. ResourceRelationshipAdvanced round-trip: same gate.
  J. Both types no longer appear in the unsupported/WARN path of
     parse_dashboard_json.

All fixtures are in-memory or tmp_path-local; no live instance, no content
YAML in the factory tree is touched, no files installed.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

# Minimal entries.resourceKind[] table with two slots:
#   slot 0: VMWARE / HostSystem
#   slot 1: VMWARE / VirtualMachine
_ENTRIES_RK = {
    "resourceKind": [
        {
            "resourceKindKey": "HostSystem",
            "internalId": "resourceKind:id:0_::_",
            "adapterKindKey": "VMWARE",
        },
        {
            "resourceKindKey": "VirtualMachine",
            "internalId": "resourceKind:id:1_::_",
            "adapterKindKey": "VMWARE",
        },
        {
            "resourceKindKey": "ClusterComputeResource",
            "internalId": "resourceKind:id:2_::_",
            "adapterKindKey": "VMWARE",
        },
        {
            "resourceKindKey": "ResourcePool",
            "internalId": "resourceKind:id:3_::_",
            "adapterKindKey": "VMWARE",
        },
    ],
    "resource": [],
}

# A minimal PropertyList widget block matching the vCommunity wire format.
_PROPERTY_LIST_WIDGET = {
    "id": "pl-widget-001",
    "type": "PropertyList",
    "title": "Properties (for selected ESXi Host)",
    "gridsterCoords": {"x": 1, "y": 15, "w": 4, "h": 10},
    "config": {
        "visualTheme": 0,
        "depth": 1,
        "refreshInterval": 300,
        "metric": {
            "mode": "resourceKind",
            "resourceMetrics": [],
            "resourceKindMetrics": [
                {
                    "metricKey": "runtime|powerState",
                    "metricName": "Runtime|Power State",
                    "isStringMetric": True,
                    "resourceKindId": "resourceKind:id:0_::_",
                    "resourceKindName": "HostSystem",
                    "colorMethod": 1,
                    "label": "Power State",
                    "yellowBound": None,
                    "orangeBound": None,
                    "redBound": None,
                    "metricUnitId": None,
                    "unit": "",
                    "handleOldColoring": False,
                    "maxValue": "",
                    "id": "extModel24191-10",
                },
                {
                    "metricKey": "config|hyperThread|active",
                    "metricName": "Configuration|Hyperthreading|Active",
                    "isStringMetric": True,
                    "resourceKindId": "resourceKind:id:0_::_",
                    "resourceKindName": "HostSystem",
                    "colorMethod": 1,
                    "label": "Hyperthreading Enabled",
                    "yellowBound": None,
                    "orangeBound": None,
                    "redBound": None,
                    "metricUnitId": None,
                    "unit": "",
                    "handleOldColoring": False,
                    "maxValue": "",
                    "id": "extModel24191-1",
                },
            ],
        },
        "resource": [],
        "refreshContent": {"refreshContent": True},
        "relationshipMode": {"relationshipMode": 0},
        "selfProvider": {"selfProvider": False},
        "showMetricFullName": {"metricFullName": True},
        "resInteractionMode": None,
        "title": "Properties (for selected ESXi Host)",
        "customFilter": {
            "filter": [], "excludedResources": None, "includedResources": None,
        },
    },
}

# A minimal ResourceRelationshipAdvanced widget block matching the vCommunity
# wire format (vSphere Resource Management.json).
_RRA_WIDGET = {
    "id": "rra-widget-001",
    "type": "ResourceRelationshipAdvanced",
    "title": "Cascading Resource Pools?",
    "gridsterCoords": {"x": 10, "y": 11, "w": 3, "h": 10},
    "config": {
        "resourceId": None,
        "refreshInterval": 300,
        "traversalSpecId": "",
        "refreshContent": {"refreshContent": False},
        "resourceName": None,
        "title": "Cascading Resource Pools?",
        "filterMode": "tagPicker",
        "tagFilter": {
            "path": [
                "/source/kind/kind:resourceKind:id:2_::_",
                "/source/kind/kind:resourceKind:id:3_::_",
            ],
            "value": {
                "bus": [],
                "adapterKind": [],
                "kind": [
                    "resourceKind:id:2_::_",
                    "resourceKind:id:3_::_",
                ],
                "exclaim": False,
                "healthRange": [],
                "maintenanceSchedule": [],
                "adapterInstance": [],
                "collector": [],
                "tier": [],
                "state": [],
                "tag": [],
                "day": [],
                "status": [],
            },
        },
        "paginationNumber": 5,
        "depth": "0,2",
        "customFilter": {
            "filter": [], "excludedResources": None, "includedResources": None,
        },
        "selectFirstRow": {"selectFirstRow": True},
        "selfProvider": {"selfProvider": False},
    },
}


def _make_dash(widgets: list) -> dict:
    """Wrap a list of widget dicts into a minimal content-zip dashboard envelope."""
    return {
        "entries": _ENTRIES_RK,
        "dashboards": [
            {
                "id": "ffffffff-0000-0000-0000-000000000001",
                "name": "Test Dashboard",
                "description": "",
                "shared": True,
                "namePath": "",
                "widgets": widgets,
                "widgetInteractions": [],
            }
        ],
        "uuid": "ffffffff-0000-0000-0000-000000000001",
    }


# ---------------------------------------------------------------------------
# Test F — _parse_property_list_config
# ---------------------------------------------------------------------------

class TestParsePropertyListConfig:
    def test_parses_metrics_with_is_string_metric(self) -> None:
        from vcfops_dashboards.reverse import _parse_property_list_config, _build_kind_lookup

        kind_lookup = _build_kind_lookup({"entries": _ENTRIES_RK})
        cfg = _PROPERTY_LIST_WIDGET["config"]

        result = _parse_property_list_config(cfg, "Test Dashboard", "pl-widget-001", kind_lookup)

        assert len(result.properties) == 2
        spec0 = result.properties[0]
        assert spec0.metric_key == "runtime|powerState"
        assert spec0.is_string_metric is True
        assert spec0.resource_kind == "HostSystem"
        assert spec0.adapter_kind == "VMWARE"
        assert spec0.color_method == 1

        spec1 = result.properties[1]
        assert spec1.metric_key == "config|hyperThread|active"
        assert spec1.label == "Hyperthreading Enabled"

    def test_visual_theme_depth_show_full_name(self) -> None:
        from vcfops_dashboards.reverse import _parse_property_list_config

        cfg = {
            "visualTheme": 3,
            "depth": 2,
            "showMetricFullName": {"metricFullName": False},
            "metric": {"resourceKindMetrics": []},
        }
        result = _parse_property_list_config(cfg, "dash", "w1")
        assert result.visual_theme == 3
        assert result.depth == 2
        assert result.show_metric_full_name is False

    def test_no_metrics_emits_warn(self) -> None:
        from vcfops_dashboards.reverse import _parse_property_list_config

        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            result = _parse_property_list_config({}, "dash", "w1")

        assert result.properties == []
        texts = [str(w.message) for w in wlist]
        assert any("PropertyList" in t and "no parseable metrics" in t for t in texts)


# ---------------------------------------------------------------------------
# Test G — _parse_resource_relationship_advanced_config
# ---------------------------------------------------------------------------

class TestParseResourceRelationshipAdvancedConfig:
    def test_resolves_two_resource_kinds(self) -> None:
        from vcfops_dashboards.reverse import (
            _parse_resource_relationship_advanced_config,
            _build_kind_lookup,
        )

        kind_lookup = _build_kind_lookup({"entries": _ENTRIES_RK})
        cfg = _RRA_WIDGET["config"]

        result = _parse_resource_relationship_advanced_config(
            cfg, "Test Dashboard", "rra-widget-001", kind_lookup
        )

        assert len(result.resource_kinds) == 2
        rk_names = {rk.resource_kind for rk in result.resource_kinds}
        assert "ClusterComputeResource" in rk_names
        assert "ResourcePool" in rk_names
        assert all(rk.adapter_kind == "VMWARE" for rk in result.resource_kinds)

    def test_depth_is_string(self) -> None:
        from vcfops_dashboards.reverse import _parse_resource_relationship_advanced_config

        cfg = {
            "depth": "0,2",
            "paginationNumber": 5,
            "selfProvider": {"selfProvider": False},
            "tagFilter": {"value": {"kind": []}},
        }
        result = _parse_resource_relationship_advanced_config(cfg, "dash", "w1")
        assert result.depth == "0,2"
        assert isinstance(result.depth, str)

    def test_pagination_number_and_self_provider(self) -> None:
        from vcfops_dashboards.reverse import _parse_resource_relationship_advanced_config

        cfg = {
            "depth": "2,1",
            "paginationNumber": 10,
            "selfProvider": {"selfProvider": True},
            "tagFilter": {"value": {"kind": []}},
        }
        result = _parse_resource_relationship_advanced_config(cfg, "dash", "w1")
        assert result.pagination_number == 10
        assert result.self_provider is True

    def test_empty_kind_filter(self) -> None:
        from vcfops_dashboards.reverse import _parse_resource_relationship_advanced_config

        cfg = {
            "depth": "2,1",
            "tagFilter": {"value": {"kind": []}},
        }
        result = _parse_resource_relationship_advanced_config(cfg, "dash", "w1")
        assert result.resource_kinds == []


# ---------------------------------------------------------------------------
# Test H — PropertyList round-trip: parse → forward-render → MATCH
# ---------------------------------------------------------------------------

class TestPropertyListRoundTrip:
    """Source widget JSON → parse_dashboard_json → forward-render → structural match."""

    def test_property_list_round_trip(self) -> None:
        from vcfops_dashboards.reverse import parse_dashboard_json
        from vcfops_dashboards.render import render_dashboards_bundle_json

        dash_envelope = _make_dash([_PROPERTY_LIST_WIDGET])
        dash_json = dash_envelope["dashboards"][0]
        dash_json["entries"] = dash_envelope["entries"]

        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            dashboard = parse_dashboard_json(dash_json, views_by_id={})

        # No "not supported" WARN
        texts = [str(w.message) for w in wlist]
        assert not any("PropertyList" in t and "not supported" in t for t in texts)

        # Exactly one widget parsed
        assert len(dashboard.widgets) == 1
        w = dashboard.widgets[0]
        assert w.type == "PropertyList"
        assert w.property_list_config is not None
        cfg = w.property_list_config
        assert len(cfg.properties) == 2
        assert cfg.properties[0].metric_key == "runtime|powerState"
        assert cfg.properties[0].is_string_metric is True
        assert cfg.visual_theme == 0
        assert cfg.depth == 1
        assert cfg.show_metric_full_name is True

        # Forward-render and compare structure to source
        rendered_str = render_dashboards_bundle_json(
            dashboards=[dashboard],
            views_by_name={},
            owner_user_id="00000000-0000-0000-0000-000000000001",
        )
        rendered = json.loads(rendered_str)
        rendered_widgets = rendered["dashboards"][0]["widgets"]
        assert len(rendered_widgets) == 1
        rw = rendered_widgets[0]

        # Structural match
        assert rw["type"] == "PropertyList"
        assert rw["gridsterCoords"] == _PROPERTY_LIST_WIDGET["gridsterCoords"]
        assert rw["title"] == _PROPERTY_LIST_WIDGET["title"]

        # Config keys match source
        rcfg = rw["config"]
        assert rcfg["visualTheme"] == 0
        assert rcfg["depth"] == 1
        assert rcfg["showMetricFullName"] == {"metricFullName": True}
        # Key fix: relationshipMode must be wrapped object, not bare 0
        assert rcfg["relationshipMode"] == {"relationshipMode": 0}
        assert rcfg["selfProvider"] == {"selfProvider": False}

        # Metrics round-trip
        rk_metrics = rcfg["metric"]["resourceKindMetrics"]
        assert len(rk_metrics) == 2
        assert rk_metrics[0]["metricKey"] == "runtime|powerState"
        assert rk_metrics[0]["isStringMetric"] is True


# ---------------------------------------------------------------------------
# Test I — ResourceRelationshipAdvanced round-trip
# ---------------------------------------------------------------------------

class TestResourceRelationshipAdvancedRoundTrip:
    """Source widget JSON → parse_dashboard_json → forward-render → structural match."""

    def test_rra_round_trip(self) -> None:
        from vcfops_dashboards.reverse import parse_dashboard_json
        from vcfops_dashboards.render import render_dashboards_bundle_json

        dash_envelope = _make_dash([_RRA_WIDGET])
        dash_json = dash_envelope["dashboards"][0]
        dash_json["entries"] = dash_envelope["entries"]

        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            dashboard = parse_dashboard_json(dash_json, views_by_id={})

        # No "not supported" WARN
        texts = [str(w.message) for w in wlist]
        assert not any("ResourceRelationshipAdvanced" in t and "not supported" in t for t in texts)

        # Exactly one widget parsed
        assert len(dashboard.widgets) == 1
        w = dashboard.widgets[0]
        assert w.type == "ResourceRelationshipAdvanced"
        assert w.resource_relationship_advanced_config is not None
        cfg = w.resource_relationship_advanced_config
        assert cfg.depth == "0,2"
        assert cfg.pagination_number == 5
        assert cfg.self_provider is False
        rk_names = {rk.resource_kind for rk in cfg.resource_kinds}
        assert "ClusterComputeResource" in rk_names
        assert "ResourcePool" in rk_names

        # Forward-render
        rendered_str = render_dashboards_bundle_json(
            dashboards=[dashboard],
            views_by_name={},
            owner_user_id="00000000-0000-0000-0000-000000000001",
        )
        rendered = json.loads(rendered_str)
        rendered_widgets = rendered["dashboards"][0]["widgets"]
        assert len(rendered_widgets) == 1
        rw = rendered_widgets[0]

        # Structural match
        assert rw["type"] == "ResourceRelationshipAdvanced"
        assert rw["gridsterCoords"] == _RRA_WIDGET["gridsterCoords"]
        assert rw["title"] == _RRA_WIDGET["title"]

        # Config match
        rcfg = rw["config"]
        assert rcfg["depth"] == "0,2"
        assert rcfg["paginationNumber"] == 5
        assert rcfg["selfProvider"] == {"selfProvider": False}
        assert rcfg["refreshContent"] == {"refreshContent": False}

        # kind refs round-trip: two kinds in tagFilter.value.kind[]
        rendered_kinds = rcfg["tagFilter"]["value"]["kind"]
        assert len(rendered_kinds) == 2
        # Each rendered kind is a "resourceKind:id:N_::_" synthetic ref
        assert all(k.startswith("resourceKind:id:") for k in rendered_kinds)

        # path[] mirrors kind[] with /source/kind/kind: prefix
        rendered_paths = rcfg["tagFilter"]["path"]
        assert len(rendered_paths) == 2
        assert all(p.startswith("/source/kind/kind:") for p in rendered_paths)


# ---------------------------------------------------------------------------
# Test J — both types absent from "not supported" WARN path
# ---------------------------------------------------------------------------

class TestBothTypesNotWarned:
    """parse_dashboard_json must not emit 'not supported by the forward renderer'
    WARN for PropertyList or ResourceRelationshipAdvanced."""

    def test_no_unsupported_warn_for_property_list(self) -> None:
        from vcfops_dashboards.reverse import parse_dashboard_json

        dash_json = _make_dash([_PROPERTY_LIST_WIDGET])["dashboards"][0]
        dash_json["entries"] = _ENTRIES_RK

        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            parse_dashboard_json(dash_json, views_by_id={})

        skip_warns = [
            str(w.message) for w in wlist
            if "not supported by the forward renderer" in str(w.message)
               and "PropertyList" in str(w.message)
        ]
        assert skip_warns == [], f"PropertyList should not produce skip WARN: {skip_warns}"

    def test_no_unsupported_warn_for_rra(self) -> None:
        from vcfops_dashboards.reverse import parse_dashboard_json

        dash_json = _make_dash([_RRA_WIDGET])["dashboards"][0]
        dash_json["entries"] = _ENTRIES_RK

        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            parse_dashboard_json(dash_json, views_by_id={})

        skip_warns = [
            str(w.message) for w in wlist
            if "not supported by the forward renderer" in str(w.message)
               and "ResourceRelationshipAdvanced" in str(w.message)
        ]
        assert skip_warns == [], f"ResourceRelationshipAdvanced should not produce skip WARN: {skip_warns}"
