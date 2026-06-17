"""Unit tests for vcfops_extractor.reverse_local + reverse.py bug fix.

Covers:
  A. build_view_uuid_map: parses <ViewDef> elements from fixture XML.
  B. _write_view_yaml: SM UUID -> @supermetric:"<name>" rewriting.
  C. _to_bound: non-numeric redBound ("false") handled without ValueError
     (regression for the MetricSpec bound-parsing bug fixed in reverse.py).
  D. reverse_local_port: round-trip diff on a minimal fixture dashboard
     that has only supported widget types (View + TextDisplay) → MATCH.
  E. reverse_local_port: dashboard with an unsupported widget type
     (PropertyList) emits WARN and continues with partial YAML output.

All fixtures are tmp_path-local; no live instance, no content YAML
in the factory tree is touched, no files installed.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Minimal XML/JSON fixture builders
# ---------------------------------------------------------------------------

_SIMPLE_VIEW_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<Content>
  <Views>
    <ViewDef id="aaaaaaaa-0000-0000-0000-000000000001">
      <Title>Test View One</Title>
      <Description>A simple list view</Description>
      <SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine"/>
      <DataProviders>
        <DataProvider dataType="list-view"/>
      </DataProviders>
      <Controls>
        <Control type="time-interval-selector" visible="false">
          <Property name="advancedTimeMode" value="false"/>
          <Property name="unit" value="HOURS"/>
          <Property name="count" value="24"/>
        </Control>
        <Control type="attributes-selector">
          <Property name="attributeInfos">
            <List>
              <Item>
                <Value>
                  <Property name="attributeKey" value="cpu|demandmhz"/>
                  <Property name="displayName" value="CPU Demand (MHz)"/>
                  <Property name="preferredUnitId" value="mhz"/>
                  <Property name="transformations">
                    <List><Item value="CURRENT"/></List>
                  </Property>
                </Value>
              </Item>
              <Item>
                <Value>
                  <Property name="attributeKey" value="Super Metric|sm_aaaaaaaa-bbbb-cccc-dddd-000000000001"/>
                  <Property name="displayName" value="My SM Column"/>
                  <Property name="transformations">
                    <List><Item value="CURRENT"/></List>
                  </Property>
                </Value>
              </Item>
            </List>
          </Property>
        </Control>
      </Controls>
    </ViewDef>
    <ViewDef id="aaaaaaaa-0000-0000-0000-000000000002">
      <Title>Test View Two</Title>
      <SubjectType adapterKind="VMWARE" resourceKind="HostSystem"/>
      <Controls>
        <Control type="attributes-selector">
          <Property name="attributeInfos">
            <List>
              <Item>
                <Value>
                  <Property name="attributeKey" value="summary|number_running_vms"/>
                  <Property name="displayName" value="Running VMs"/>
                </Value>
              </Item>
            </List>
          </Property>
        </Control>
      </Controls>
    </ViewDef>
  </Views>
</Content>
"""


def _make_dash_json(dash_id: str, dash_name: str, view_id: str) -> dict:
    """Minimal dashboard JSON in content-zip format with one View widget."""
    return {
        "entries": {
            "resourceKind": [],
            "resource": [],
        },
        "dashboards": [
            {
                "id": dash_id,
                "name": dash_name,
                "description": "",
                "shared": True,
                "namePath": "",
                "widgets": [
                    {
                        "id": "widget-001",
                        "type": "View",
                        "title": "My View Widget",
                        "gridsterCoords": {"x": 1, "y": 1, "w": 6, "h": 4},
                        "config": {
                            "viewDefinitionId": view_id,
                            "selfProvider": {"selfProvider": False},
                        },
                        "widgetInteractions": [],
                    },
                    {
                        "id": "widget-002",
                        "type": "TextDisplay",
                        "title": "Info",
                        "gridsterCoords": {"x": 7, "y": 1, "w": 6, "h": 2},
                        "config": {"editorData": "<p>Hello</p>"},
                        "widgetInteractions": [],
                    },
                ],
                "widgetInteractions": [],
            }
        ],
        "uuid": dash_id,
    }


def _make_dash_json_with_unsupported(dash_id: str, dash_name: str) -> dict:
    """Dashboard JSON with one PropertyList (unsupported) + one TextDisplay."""
    return {
        "entries": {"resourceKind": [], "resource": []},
        "dashboards": [
            {
                "id": dash_id,
                "name": dash_name,
                "description": "",
                "shared": True,
                "namePath": "",
                "widgets": [
                    {
                        "id": "widget-A",
                        "type": "PropertyList",
                        "title": "Unsupported Widget",
                        "gridsterCoords": {"x": 1, "y": 1, "w": 6, "h": 4},
                        "config": {},
                        "widgetInteractions": [],
                    },
                    {
                        "id": "widget-B",
                        "type": "TextDisplay",
                        "title": "Supported",
                        "gridsterCoords": {"x": 7, "y": 1, "w": 6, "h": 2},
                        "config": {"editorData": "<p>hi</p>"},
                        "widgetInteractions": [],
                    },
                ],
                "widgetInteractions": [],
            }
        ],
        "uuid": dash_id,
    }


# ---------------------------------------------------------------------------
# Test A — build_view_uuid_map
# ---------------------------------------------------------------------------

class TestBuildViewUuidMap:
    def test_parses_two_views_from_fixture_xml(self, tmp_path: Path) -> None:
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        (xml_dir / "fixture.xml").write_text(_SIMPLE_VIEW_XML, encoding="utf-8")

        from vcfops_extractor.reverse_local import build_view_uuid_map
        result = build_view_uuid_map(xml_dir)

        assert "aaaaaaaa-0000-0000-0000-000000000001" in result
        assert "aaaaaaaa-0000-0000-0000-000000000002" in result
        vd1 = result["aaaaaaaa-0000-0000-0000-000000000001"]
        assert vd1["name"] == "Test View One"
        assert vd1["adapter_kind"] == "VMWARE"
        assert vd1["resource_kind"] == "VirtualMachine"
        # Two columns: a plain metric and an SM column
        cols = vd1["columns"]
        assert len(cols) == 2
        assert cols[0]["attribute"] == "cpu|demandmhz"
        # SM column retains sm_<uuid> form here (rewriting happens in _write_view_yaml)
        assert cols[1]["attribute"] == "sm_aaaaaaaa-bbbb-cccc-dddd-000000000001"

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        from vcfops_extractor.reverse_local import build_view_uuid_map
        result = build_view_uuid_map(tmp_path / "does_not_exist")
        assert result == {}

    def test_cross_file_duplicates_silently_keep_last(self, tmp_path: Path) -> None:
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        # File A: view with name "Version A"
        xml_a = """\
<Content><Views>
  <ViewDef id="bbbbbbbb-0000-0000-0000-000000000001">
    <Title>Version A</Title>
    <SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine"/>
  </ViewDef>
</Views></Content>"""
        # File B: same id, different name "Version B"
        xml_b = """\
<Content><Views>
  <ViewDef id="bbbbbbbb-0000-0000-0000-000000000001">
    <Title>Version B</Title>
    <SubjectType adapterKind="VMWARE" resourceKind="HostSystem"/>
  </ViewDef>
</Views></Content>"""
        (xml_dir / "a_file.xml").write_text(xml_a, encoding="utf-8")
        (xml_dir / "b_file.xml").write_text(xml_b, encoding="utf-8")

        from vcfops_extractor.reverse_local import build_view_uuid_map
        result = build_view_uuid_map(xml_dir)
        # b_file.xml is alphabetically after a_file.xml → "Version B" wins
        assert result["bbbbbbbb-0000-0000-0000-000000000001"]["name"] == "Version B"


# ---------------------------------------------------------------------------
# Test B — _write_view_yaml SM rewriting
# ---------------------------------------------------------------------------

class TestWriteViewYaml:
    def test_sm_uuid_rewritten_to_supermetric_no_at(self, tmp_path: Path) -> None:
        from vcfops_extractor.reverse_local import _write_view_yaml

        view_data = {
            "id": "cccccccc-0000-0000-0000-000000000001",
            "name": "SM Rewrite Test",
            "description": "",
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "data_type": "list",
            "presentation": "list",
            "columns": [
                {
                    "attribute": "sm_aaaaaaaa-bbbb-cccc-dddd-000000000001",
                    "display_name": "My SM",
                },
                {
                    "attribute": "cpu|demandmhz",
                    "display_name": "CPU Demand",
                },
            ],
            "time_window": None,
        }
        uuid_to_name = {
            "aaaaaaaa-bbbb-cccc-dddd-000000000001": "My Super Metric Name",
        }
        out = tmp_path / "test_view.yaml"
        _write_view_yaml(out, view_data, uuid_to_name)

        doc = yaml.safe_load(out.read_text())
        cols = doc["columns"]
        # VIEW-COLUMN form: supermetric:"<name>" — no @ prefix.
        # The @supermetric:"<name>" form is the SM-FORMULA form and must NOT
        # appear in view column attributes.
        assert cols[0]["attribute"] == 'supermetric:"My Super Metric Name"'
        assert not cols[0]["attribute"].startswith("@"), (
            "view column SM ref must use supermetric: form, not @supermetric: form"
        )
        # Plain metric col unchanged
        assert cols[1]["attribute"] == "cpu|demandmhz"

    def test_unresolved_sm_uuid_kept_as_sm_token(self, tmp_path: Path, capsys) -> None:
        from vcfops_extractor.reverse_local import _write_view_yaml

        view_data = {
            "id": "cccccccc-0000-0000-0000-000000000002",
            "name": "Unresolved SM",
            "description": "",
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "data_type": "list",
            "presentation": "list",
            "columns": [
                {
                    "attribute": "sm_aaaaaaaa-bbbb-cccc-dddd-000000000099",
                    "display_name": "Unknown SM",
                },
            ],
            "time_window": None,
        }
        out = tmp_path / "test_view_unresolved.yaml"
        _write_view_yaml(out, view_data, uuid_to_name={})

        doc = yaml.safe_load(out.read_text())
        # UUID kept as sm_<uuid> form (not resolved, not crashed)
        assert doc["columns"][0]["attribute"].startswith("sm_")
        # _warn() prints to stderr; verify WARN was emitted
        captured = capsys.readouterr()
        assert "could not resolve" in captured.err


# ---------------------------------------------------------------------------
# Test B2 — view column SM reference round-trip: reverse → render → wire
# ---------------------------------------------------------------------------

class TestViewColumnSmRoundTrip:
    """Regression test for the @supermetric vs supermetric: emission bug.

    The reverse path must emit ``supermetric:"<name>"`` (no ``@`` prefix) for
    view column SM references.  The ``@supermetric:"<name>"`` form is the
    SM-FORMULA form; emitting it in a view column produces an unresolvable
    literal that ships to the instance instead of ``Super Metric|sm_<uuid>``.

    Test G1: ``_rewrite_sm_attr`` emits ``supermetric:"<name>"`` (no ``@``).
    Test G2: The emitted form round-trips through the forward renderer to
             ``Super Metric|sm_<uuid>`` in the rendered XML.
    """

    _SM_UUID = "aaaaaaaa-bbbb-cccc-dddd-000000000001"
    _SM_NAME = "My Reversed Super Metric"

    def test_g1_rewrite_emits_view_column_form_not_formula_form(self) -> None:
        """_rewrite_sm_attr must emit supermetric:"<name>", not @supermetric:"<name>"."""
        from vcfops_extractor.reverse_local import _rewrite_sm_attr

        uuid_to_name = {self._SM_UUID: self._SM_NAME}

        # Both wire forms that the XML parser produces
        for wire_attr in (
            f"Super Metric|sm_{self._SM_UUID}",
            f"sm_{self._SM_UUID}",
        ):
            result = _rewrite_sm_attr(wire_attr, uuid_to_name)
            assert result == f'supermetric:"{self._SM_NAME}"', (
                f"_rewrite_sm_attr({wire_attr!r}) should emit view-column form "
                f"supermetric:\"<name>\" but got {result!r}"
            )
            assert not result.startswith("@"), (
                f"@supermetric: is the SM-FORMULA form and must NOT appear in "
                f"view column attributes; got {result!r} from {wire_attr!r}"
            )

    def test_g2_reversed_view_column_renders_to_super_metric_uuid_in_xml(
        self, tmp_path: Path
    ) -> None:
        """Reversed view column with supermetric:"<name>" renders to
        Super Metric|sm_<uuid> in the forward XML — not a literal token."""
        from vcfops_extractor.reverse_local import _write_view_yaml
        from vcfops_dashboards.render import render_views_xml
        from vcfops_dashboards.loader import load_view

        view_data = {
            "id": "354f7d8e-a570-4a37-91a3-3b93ef6bfc69",
            "name": "G2 Round Trip View",
            "description": "",
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "data_type": "list",
            "presentation": "list",
            "columns": [
                {
                    "attribute": f"sm_{self._SM_UUID}",
                    "display_name": "SM Column",
                },
                {
                    "attribute": "cpu|demandmhz",
                    "display_name": "CPU Demand",
                },
            ],
            "time_window": None,
        }
        uuid_to_name = {self._SM_UUID: self._SM_NAME}

        view_path = tmp_path / "g2_view.yaml"
        _write_view_yaml(view_path, view_data, uuid_to_name)

        # Verify the emitted YAML carries the correct view-column form (no @)
        doc = yaml.safe_load(view_path.read_text())
        sm_col = next(c for c in doc["columns"] if "supermetric" in c["attribute"])
        assert sm_col["attribute"] == f'supermetric:"{self._SM_NAME}"', (
            f"emitted YAML should carry view-column form, got {sm_col['attribute']!r}"
        )
        assert not sm_col["attribute"].startswith("@"), (
            "@ prefix must not appear in view column attribute"
        )

        # Write an SM YAML so the renderer can resolve the name → UUID
        sm_dir = tmp_path / "supermetrics"
        sm_dir.mkdir()
        sm_yaml = {
            "id": self._SM_UUID,
            "name": self._SM_NAME,
            "formula": "${this, metric=cpu|usage_average}",
            "resource_kinds": [
                {"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}
            ],
        }
        (sm_dir / "my-sm.yaml").write_text(yaml.dump(sm_yaml), encoding="utf-8")

        # Load the view YAML and forward-render it, scoped to our SM
        vd = load_view(view_path, enforce_framework_prefix=False)
        assert vd is not None

        sm_paths = list(sm_dir.rglob("*.yaml"))
        rendered_xml = render_views_xml([vd], sm_scope=sm_paths)

        # The rendered XML must contain Super Metric|sm_<uuid> — NOT a literal token
        expected_attr = f"Super Metric|sm_{self._SM_UUID}"
        assert expected_attr in rendered_xml, (
            f"rendered XML must contain {expected_attr!r} but it was absent.\n"
            f"Rendered XML snippet: {rendered_xml[:2000]}"
        )
        # Confirm no literal unresolved token leaked through
        assert "@supermetric:" not in rendered_xml, (
            "@supermetric: literal found in rendered XML — SM reference was not resolved"
        )
        assert 'supermetric:"' not in rendered_xml, (
            'supermetric:" literal found in rendered XML — SM reference was not resolved'
        )


# ---------------------------------------------------------------------------
# Test C — _to_bound: non-numeric "false" handled without ValueError
# ---------------------------------------------------------------------------

class TestMetricSpecBoundParsing:
    """Regression test for the reverse.py bug where redBound='false' raised
    ValueError.  Source dashboard JSONs (pre-install) may carry boolean JSON
    values serialised as the string 'false' rather than a numeric threshold."""

    def test_false_string_bound_treated_as_none(self) -> None:
        from vcfops_dashboards.reverse import _parse_metric_specs_from_wire

        raw_metric = {
            "resourceKindMetrics": [
                {
                    "metricKey": "configuration|dasConfig|enabled",
                    "resourceKindId": "",
                    "resourceKindName": "ClusterComputeResource",
                    "yellowBound": "1",
                    "orangeBound": "1",
                    "redBound": "false",   # ← pre-install "boolean-as-string" artifact
                    "colorMethod": 0,
                    "metricName": "HA Enabled",
                }
            ]
        }
        # Must not raise; redBound should be None (not parseable as float)
        specs = _parse_metric_specs_from_wire(raw_metric, "test-widget")
        assert len(specs) == 1
        s = specs[0]
        assert s.yellow_bound == 1.0
        assert s.orange_bound == 1.0
        assert s.red_bound is None  # "false" → None, not ValueError

    def test_numeric_bounds_still_parse(self) -> None:
        from vcfops_dashboards.reverse import _parse_metric_specs_from_wire

        raw_metric = {
            "resourceKindMetrics": [
                {
                    "metricKey": "cpu|readyPct",
                    "resourceKindId": "",
                    "resourceKindName": "ClusterComputeResource",
                    "yellowBound": 2.5,
                    "orangeBound": 5.0,
                    "redBound": 10.0,
                    "colorMethod": 0,
                    "metricName": "CPU Ready",
                }
            ]
        }
        specs = _parse_metric_specs_from_wire(raw_metric, "test-widget")
        assert specs[0].yellow_bound == 2.5
        assert specs[0].orange_bound == 5.0
        assert specs[0].red_bound == 10.0


# ---------------------------------------------------------------------------
# Test D — round-trip MATCH on minimal fixture (all supported widgets)
# ---------------------------------------------------------------------------

class TestRoundTripMatch:
    """Full reverse_local_port call on a small fixture with only supported
    widget types (View + TextDisplay).  Expected: MATCH after round-trip."""

    VIEW_ID = "aaaaaaaa-0000-0000-0000-000000000001"
    DASH_ID = "dddddddd-0000-0000-0000-000000000001"
    DASH_NAME = "Test Dashboard"

    def test_round_trip_match(self, tmp_path: Path) -> None:
        # Write fixture XML
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        (xml_dir / "views.xml").write_text(_SIMPLE_VIEW_XML, encoding="utf-8")

        # Write fixture dashboard JSON
        dash_json = _make_dash_json(self.DASH_ID, self.DASH_NAME, self.VIEW_ID)
        json_path = tmp_path / "dashboard.json"
        json_path.write_text(json.dumps(dash_json), encoding="utf-8")

        # SM dir: one SM YAML for UUID resolution
        sm_dir = tmp_path / "supermetrics"
        sm_dir.mkdir()
        sm_yaml = {
            "id": "aaaaaaaa-bbbb-cccc-dddd-000000000001",
            "name": "My Super Metric Name",
            "formula": "${this, metric=mem|usage_average}",
            "resource_kinds": [{"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}],
        }
        (sm_dir / "my-sm.yaml").write_text(yaml.dump(sm_yaml), encoding="utf-8")

        out_views = tmp_path / "views"
        out_dash = tmp_path / "dashboards"

        from vcfops_extractor.reverse_local import reverse_local_port
        rc = reverse_local_port(
            source_dashboard_json=json_path,
            source_view_xml_dir=xml_dir,
            sm_yaml_dir=sm_dir,
            output_views_dir=out_views,
            output_dashboards_dir=out_dash,
            run_diff=True,
        )
        assert rc == 0

        # View file must exist and contain the SM rewrite
        view_files = list(out_views.glob("*.yaml"))
        assert len(view_files) == 1
        vdoc = yaml.safe_load(view_files[0].read_text())
        sm_col = next(c for c in vdoc["columns"] if "supermetric" in c["attribute"])
        # VIEW-COLUMN form: supermetric:"<name>" — no @ prefix.
        assert sm_col["attribute"] == 'supermetric:"My Super Metric Name"'
        assert not sm_col["attribute"].startswith("@"), (
            "view column SM ref must use supermetric: form, not @supermetric: form"
        )

        # Dashboard YAML must exist
        dash_files = list(out_dash.glob("*.yaml"))
        assert len(dash_files) == 1
        ddoc = yaml.safe_load(dash_files[0].read_text())
        assert ddoc["id"] == self.DASH_ID
        # 2 widgets: View + TextDisplay
        assert len(ddoc["widgets"]) == 2
        view_widget = next(w for w in ddoc["widgets"] if w["type"] == "View")
        assert view_widget["view"] == "Test View One"


# ---------------------------------------------------------------------------
# Test E — formerly-unsupported PropertyList is now supported (no WARN)
# ---------------------------------------------------------------------------

class TestPropertyListNowSupported:
    """PropertyList was previously unsupported (emitted WARN + skipped).
    After the reverse-parser addition, it is a fully supported widget type:
    it parses, appears in YAML output, and does NOT produce a
    'not supported by the forward renderer' WARN."""

    DASH_ID = "eeeeeeee-0000-0000-0000-000000000001"
    DASH_NAME = "PropertyList Mix"

    def test_property_list_parsed_not_warned(self, tmp_path: Path, capsys) -> None:
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()
        (xml_dir / "empty.xml").write_text(
            '<?xml version="1.0"?><Content><Views/></Content>', encoding="utf-8"
        )

        # Build a dashboard with one PropertyList (with real metric entries)
        # and one TextDisplay.
        dash_json = {
            "entries": {
                "resourceKind": [
                    {
                        "resourceKindKey": "HostSystem",
                        "internalId": "resourceKind:id:0_::_",
                        "adapterKindKey": "VMWARE",
                    }
                ],
                "resource": [],
            },
            "dashboards": [
                {
                    "id": self.DASH_ID,
                    "name": self.DASH_NAME,
                    "description": "",
                    "shared": True,
                    "namePath": "",
                    "widgets": [
                        {
                            "id": "widget-PL",
                            "type": "PropertyList",
                            "title": "Properties",
                            "gridsterCoords": {"x": 1, "y": 1, "w": 4, "h": 10},
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
                                            "metricName": "Power State",
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
                                            "id": "extModel1-1",
                                        }
                                    ],
                                },
                                "resource": [],
                                "refreshContent": {"refreshContent": True},
                                "relationshipMode": {"relationshipMode": 0},
                                "selfProvider": {"selfProvider": False},
                                "showMetricFullName": {"metricFullName": True},
                                "resInteractionMode": None,
                                "title": "Properties",
                            },
                            "widgetInteractions": [],
                        },
                        {
                            "id": "widget-TD",
                            "type": "TextDisplay",
                            "title": "Info",
                            "gridsterCoords": {"x": 5, "y": 1, "w": 8, "h": 2},
                            "config": {"editorData": "<p>hi</p>"},
                            "widgetInteractions": [],
                        },
                    ],
                    "widgetInteractions": [],
                }
            ],
            "uuid": self.DASH_ID,
        }
        json_path = tmp_path / "dashboard.json"
        json_path.write_text(json.dumps(dash_json), encoding="utf-8")

        sm_dir = tmp_path / "supermetrics"
        sm_dir.mkdir()
        out_views = tmp_path / "views"
        out_dash = tmp_path / "dashboards"

        from vcfops_extractor.reverse_local import reverse_local_port

        rc = reverse_local_port(
            source_dashboard_json=json_path,
            source_view_xml_dir=xml_dir,
            sm_yaml_dir=sm_dir,
            output_views_dir=out_views,
            output_dashboards_dir=out_dash,
            run_diff=False,
        )
        assert rc == 0

        dash_files = list(out_dash.glob("*.yaml"))
        assert len(dash_files) == 1
        ddoc = yaml.safe_load(dash_files[0].read_text())

        # PropertyList IS present (now supported)
        widget_types = [w["type"] for w in ddoc["widgets"]]
        assert "PropertyList" in widget_types
        assert "TextDisplay" in widget_types

        # No "not supported by the forward renderer" WARN for PropertyList
        captured = capsys.readouterr()
        assert "PropertyList" not in captured.err or "not supported" not in captured.err

        # Verify PropertyList widget has property_list with correct structure
        pl_widget = next(w for w in ddoc["widgets"] if w["type"] == "PropertyList")
        assert "property_list" in pl_widget
        pl_cfg = pl_widget["property_list"]
        assert len(pl_cfg["properties"]) == 1
        prop = pl_cfg["properties"][0]
        assert prop["metric_key"] == "runtime|powerState"
        assert prop["is_string_metric"] is True


# ---------------------------------------------------------------------------
# Test F — ascending_range derivation from bound ordering (no ascendingRange in wire)
# ---------------------------------------------------------------------------

_ASCENDING_RANGE_XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<Content>
  <Views>
    <ViewDef id="{view_id}">
      <Title>{title}</Title>
      <Description></Description>
      <SubjectType adapterKind="VMWARE" resourceKind="HostSystem"/>
      <DataProviders>
        <DataProvider dataType="list-view"/>
      </DataProviders>
      <Controls>
        <Control type="time-interval-selector" visible="false">
          <Property name="advancedTimeMode" value="false"/>
          <Property name="unit" value="HOURS"/>
          <Property name="count" value="24"/>
        </Control>
        <Control type="attributes-selector" visible="false">
          <Property name="attributeInfos">
            <List>
              <Item>
                <Value>
                  <Property name="attributeKey" value="cpu|usage_average"/>
                  <Property name="displayName" value="CPU Usage %"/>
                  <Property name="yellowBound" value="{yellow}"/>
                  <Property name="orangeBound" value="{orange}"/>
                  <Property name="redBound" value="{red}"/>
                  {asc_prop}
                  <Property name="transformations">
                    <List><Item value="CURRENT"/></List>
                  </Property>
                </Value>
              </Item>
            </List>
          </Property>
        </Control>
      </Controls>
    </ViewDef>
  </Views>
</Content>
"""


class TestAscendingRangeDerivation:
    """Round-trip tests for ascending_range derivation from wire bound ordering.

    Covers the gap where the source wire has all three numeric bounds but
    ascendingRange is absent.  The fix in reverse.py (dataclass path) and
    reverse_local.py (dict path) must both derive ascending_range from the
    bound ordering so the loader accepts the reversed column.

    F1. Higher-is-worse (yellow < orange < red, no ascendingRange in wire):
        reversed column must have ascending_range=False.
    F2. Lower-is-worse (yellow > orange > red, no ascendingRange in wire):
        reversed column must have ascending_range=True.
    F3. Explicit ascendingRange="false" in wire → ascending_range=False
        (regression guard: existing explicit-wire path not broken).
    F4. Explicit ascendingRange="true" in wire → ascending_range=True.
    F5. Forward round-trip: reverse then render should produce XML whose
        ascendingRange matches the original bound ordering.
    """

    # ---- helpers ----

    @staticmethod
    def _make_xml(view_id: str, title: str, y: float, o: float, r: float,
                  ascending_str: str | None = None) -> str:
        if ascending_str is not None:
            asc_prop = f'<Property name="ascendingRange" value="{ascending_str}"/>'
        else:
            asc_prop = ""
        return _ASCENDING_RANGE_XML_TEMPLATE.format(
            view_id=view_id, title=title,
            yellow=y, orange=o, red=r,
            asc_prop=asc_prop,
        )

    @staticmethod
    def _parse_col_from_xml(xml_str: str, view_id: str):
        """Parse a ViewDef from XML and return the first column as a ViewColumn."""
        from vcfops_dashboards.reverse import parse_view_from_content_xml
        vd = parse_view_from_content_xml(xml_str.encode(), view_id)
        assert vd is not None
        assert len(vd.columns) == 1
        return vd.columns[0]

    @staticmethod
    def _parse_col_dict_from_xml(xml_str: str, view_id: str) -> dict:
        """Parse via the reverse_local dict path and return the first column dict."""
        import xml.etree.ElementTree as ET
        from vcfops_extractor.reverse_local import _parse_view_xml_to_dict

        root = ET.fromstring(xml_str)
        for elem in root.iter("ViewDef"):
            if (elem.get("id") or "").lower() == view_id.lower():
                view_data = _parse_view_xml_to_dict(elem)
                return view_data["columns"][0]
        raise AssertionError(f"ViewDef {view_id} not found in XML")

    # ---- F1: higher-is-worse (no ascendingRange in wire) ----

    def test_f1_higher_is_worse_derived_false(self) -> None:
        vid = "f1f1f1f1-0000-0000-0000-000000000001"
        xml = self._make_xml(vid, "CPU Queue View", y=3.0, o=12.0, r=48.0)
        col = self._parse_col_from_xml(xml, vid)
        assert col.ascending_range is False, (
            "yellow < orange < red (higher-is-worse) should derive ascending_range=False"
        )

    def test_f1_dict_path_higher_is_worse_derived_false(self) -> None:
        vid = "f1f1f1f1-0000-0000-0000-000000000002"
        xml = self._make_xml(vid, "CPU Queue Dict", y=3.0, o=12.0, r=48.0)
        col = self._parse_col_dict_from_xml(xml, vid)
        assert col.get("ascending_range") is False, (
            "dict path: yellow < orange < red should derive ascending_range=False"
        )

    # ---- F2: lower-is-worse (no ascendingRange in wire) ----

    def test_f2_lower_is_worse_derived_true(self) -> None:
        vid = "f2f2f2f2-0000-0000-0000-000000000001"
        xml = self._make_xml(vid, "Free Capacity View", y=50.0, o=30.0, r=10.0)
        col = self._parse_col_from_xml(xml, vid)
        assert col.ascending_range is True, (
            "yellow > orange > red (lower-is-worse) should derive ascending_range=True"
        )

    def test_f2_dict_path_lower_is_worse_derived_true(self) -> None:
        vid = "f2f2f2f2-0000-0000-0000-000000000002"
        xml = self._make_xml(vid, "Free Capacity Dict", y=50.0, o=30.0, r=10.0)
        col = self._parse_col_dict_from_xml(xml, vid)
        assert col.get("ascending_range") is True, (
            "dict path: yellow > orange > red should derive ascending_range=True"
        )

    # ---- F3: explicit ascendingRange=false ----

    def test_f3_explicit_false_wire(self) -> None:
        vid = "f3f3f3f3-0000-0000-0000-000000000001"
        xml = self._make_xml(vid, "Explicit False", y=3.0, o=12.0, r=48.0,
                              ascending_str="false")
        col = self._parse_col_from_xml(xml, vid)
        assert col.ascending_range is False

    # ---- F4: explicit ascendingRange=true ----

    def test_f4_explicit_true_wire(self) -> None:
        vid = "f4f4f4f4-0000-0000-0000-000000000001"
        xml = self._make_xml(vid, "Explicit True", y=50.0, o=30.0, r=10.0,
                              ascending_str="true")
        col = self._parse_col_from_xml(xml, vid)
        assert col.ascending_range is True

    # ---- F5: forward round-trip — reverse → render → wire matches source ----

    def test_f5_round_trip_higher_is_worse(self) -> None:
        """Reverse a column with y<o<r (no ascendingRange) then forward-render
        it and verify the output XML carries ascendingRange=false."""
        from vcfops_dashboards.render import render_views_xml
        vid = "f5f5f5f5-0000-0000-0000-000000000001"
        xml = self._make_xml(vid, "RT Higher Is Worse", y=2.5, o=5.0, r=10.0)
        col = self._parse_col_from_xml(xml, vid)
        assert col.ascending_range is False  # verified above

        # Build a minimal ViewDef and render
        from vcfops_dashboards.loader import ViewDef
        vd = ViewDef(
            id=vid,
            name="RT Higher Is Worse",
            description="",
            adapter_kind="VMWARE",
            resource_kind="HostSystem",
            columns=[col],
        )
        rendered_xml = render_views_xml([vd])
        assert 'ascendingRange" value="false"' in rendered_xml, (
            "forward render of ascending_range=False should emit ascendingRange=false"
        )

    def test_f5_round_trip_lower_is_worse(self) -> None:
        """Reverse a column with y>o>r (no ascendingRange) then forward-render
        it and verify the output XML carries ascendingRange=true."""
        from vcfops_dashboards.render import render_views_xml
        vid = "f5f5f5f5-0000-0000-0000-000000000002"
        xml = self._make_xml(vid, "RT Lower Is Worse", y=80.0, o=50.0, r=20.0)
        col = self._parse_col_from_xml(xml, vid)
        assert col.ascending_range is True  # verified above

        from vcfops_dashboards.loader import ViewDef
        vd = ViewDef(
            id=vid,
            name="RT Lower Is Worse",
            description="",
            adapter_kind="VMWARE",
            resource_kind="HostSystem",
            columns=[col],
        )
        rendered_xml = render_views_xml([vd])
        assert 'ascendingRange" value="true"' in rendered_xml, (
            "forward render of ascending_range=True should emit ascendingRange=true"
        )
