"""TOOLSET GAP fix — `instanced`/`thresholdType`/`valueType` on the XML
content-import path (`src/vcfops_alerts/render.py::_add_condition_element`).

Prior to this fix, `_add_condition_element` never emitted `instanced` for
metric_static/property conditions on the XML path (the pak-build path),
even though the REST path (`vcfops_symptoms.loader._condition_to_wire`)
always emitted it. Proof: extracting
`content/sdk-adapters/vcommunity-vsphere/dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak`
showed `content/symptomdefs/'ESXi Host NIC Disconnected.xml'` with no
`instanced="true"` despite the source YAML declaring `condition.instanced:
true`. Every instanced condition in every built pak silently downgraded to
exact-string key matching. See knowledge/context/defects.md DEF-<see file>.

Vendor wire format (RULE-016 read-only reference), the ground truth these
tests compare against:
  reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
    content/symptomdefs/ESXi Host NIC Disconnected Symptom.xml:5
    content/symptomdefs/Windows Service Down Symptom.xml:5
  reference/references/vmbro_vcf_operations_hardware_vcommunity/Management
    Pack/content/symptomdefs/Dell EMC Server Physical Disk Life Remaining -
    Critical.xml:5

All fixtures are in-process; no content YAML, network, or install commands
are touched.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest


def _parse_xml(xml_text: str) -> ET.Element:
    stripped = xml_text.strip()
    if stripped.startswith("<?xml"):
        end = stripped.index("?>") + 2
        stripped = stripped[end:].lstrip()
    return ET.fromstring(stripped)


def _render_condition(condition: dict, name: str = "Test Symptom") -> ET.Element:
    from vcfops_symptoms.loader import SymptomDef
    from vcfops_alerts.render import render_alert_content_xml

    sym = SymptomDef(
        name=name,
        adapter_kind="VMWARE",
        resource_kind="HostSystem",
        severity="CRITICAL",
        condition=condition,
        wait_cycles=2,
        cancel_cycles=2,
        id="c8d1e671-d0ea-489f-acc4-46e34cc246b6",
    )
    xml_text = render_alert_content_xml([sym], [])
    root = _parse_xml(xml_text)
    cond = root.find(".//Condition")
    assert cond is not None, "No <Condition> element found"
    return cond


class TestInstancedPropertyCondition:
    """Ref: ESXi Host NIC Disconnected Symptom.xml / Windows Service Down
    Symptom.xml — both:
      <Condition instanced="true" key="..." operator="!=" thresholdType="static"
        type="property" value="..." valueType="string"/>
    """

    def test_nic_disconnected_condition_matches_vendor_shape(self):
        cond = _render_condition(
            {
                "type": "property",
                "key": "vCommunity|Network|Device:vmnic0|Status",
                "operator": "NOT_EQ",
                "value": "Connected",
                "instanced": True,
            }
        )
        assert cond.get("instanced") == "true", (
            "instanced attribute missing/wrong on XML content-import path — "
            "this is the exact silent downgrade the fix addresses."
        )
        assert cond.get("key") == "vCommunity|Network|Device:vmnic0|Status"
        assert cond.get("operator") == "!="
        assert cond.get("thresholdType") == "static"
        assert cond.get("type") == "property"
        assert cond.get("value") == "Connected"
        assert cond.get("valueType") == "string"

    def test_non_instanced_property_condition_emits_instanced_false(self):
        """instanced: false must render instanced="false", not be omitted —
        the attribute must always be present on property/metric_static
        conditions so downstream consumers don't have to guess a default."""
        cond = _render_condition(
            {
                "type": "property",
                "key": "summary|runtime|powerState",
                "operator": "EQ",
                "value": "poweredOff",
                "instanced": False,
            }
        )
        assert cond.get("instanced") == "false"

    def test_instanced_defaults_false_when_absent_from_yaml(self):
        """A condition dict with no `instanced` key at all (legacy content)
        must not crash and must default to instanced="false"."""
        cond = _render_condition(
            {
                "type": "property",
                "key": "summary|runtime|powerState",
                "operator": "EQ",
                "value": "poweredOff",
            }
        )
        assert cond.get("instanced") == "false"


class TestInstancedMetricStaticCondition:
    """Ref: Dell EMC Server Physical Disk Life Remaining - Critical.xml —
      <Condition instanced="true" key="..." operator="&lt;" thresholdType="static"
        type="metric" value="10.0" valueType="numeric"/>
    """

    def test_license_remaining_days_condition_matches_vendor_shape(self):
        """Mirrors the vcommunity-vsphere pak's
        esxi-host-license-remaining-days-critical.yaml condition block."""
        cond = _render_condition(
            {
                "type": "metric_static",
                "key": "vCommunity|Licensing:Any|Remaining Days",
                "operator": "LT",
                "value": 30,
                "instanced": True,
            }
        )
        assert cond.get("instanced") == "true"
        assert cond.get("key") == "vCommunity|Licensing:Any|Remaining Days"
        assert cond.get("operator") == "<"
        assert cond.get("thresholdType") == "static"
        assert cond.get("type") == "metric"
        assert cond.get("value") == "30"
        assert cond.get("valueType") == "numeric"

    def test_thresholdtype_valuetype_lowercase_not_rest_casing(self):
        """The XML path uses lowercase 'static'/'numeric' — the REST wire
        path's _condition_to_wire uses uppercase 'STATIC'/'NUMERIC'. The two
        casings are independent; this locks the XML path's casing so a
        future refactor doesn't accidentally copy the REST casing over."""
        cond = _render_condition(
            {
                "type": "metric_static",
                "key": "cpu|usage_average",
                "operator": "GT",
                "value": 90,
                "instanced": False,
            }
        )
        assert cond.get("thresholdType") == "static"
        assert cond.get("valueType") == "numeric"


class TestInstancedMetricDynamicCondition:
    """No vendor DT (metric_dynamic) XML example was found in any reference
    pak. This locks current (conservative) behavior: instanced is emitted,
    thresholdType/valueType are not (matching the REST wire's own omission
    for CONDITION_DT, which carries no `value`)."""

    def test_metric_dynamic_emits_instanced_no_threshold_or_value_type(self):
        cond = _render_condition(
            {
                "type": "metric_dynamic",
                "key": "cpu|usage_average",
                "direction": "ABOVE",
                "instanced": True,
            }
        )
        assert cond.get("instanced") == "true"
        assert cond.get("operator") == "DT_ABOVE"
        assert cond.get("type") == "metric"
        assert cond.get("thresholdType") is None
        assert cond.get("valueType") is None
        assert cond.get("value") is None


class TestPropertyValueTypeSplit:
    """Mirrors _condition_to_wire's bool/int-float/string valueType split."""

    def test_numeric_property_value_emits_numeric_valuetype(self):
        cond = _render_condition(
            {
                "type": "property",
                "key": "config|hardware|numCpu",
                "operator": "GT",
                "value": 4,
                "instanced": False,
            }
        )
        assert cond.get("valueType") == "numeric"
        assert cond.get("value") == "4"

    def test_bool_property_value_emits_string_valuetype(self):
        cond = _render_condition(
            {
                "type": "property",
                "key": "config|template",
                "operator": "EQ",
                "value": True,
                "instanced": False,
            }
        )
        assert cond.get("valueType") == "string"
