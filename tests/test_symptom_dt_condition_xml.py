"""Guard: a dynamic-threshold (metric_dynamic) symptom condition renders in
the content-import XML vocabulary, not the REST one.

Content import (pak ``content/symptomdefs/`` and ``content/alertdefs/``,
factory content zips) reads ``type="dtmetric"`` with a lowercase
``above``/``below``/``abnormal`` operator. The REST spelling
(``type="metric" operator="DT_ABOVE"``) fails import with
``Invalid operator:dt_above`` on 8.18 and 9.1, and the platform drops the
symptom and every alert that references it while the install reports
success (Synology pak 0.0.0.35).

Vendor forms these tests compare against (verbatim, from
knowledge/context/wire-formats/symptomdef_dt_condition_import.md):

  VMSP pak content/alertdefs/alertdefs.xml (devel_9_1) line 355:
    <Condition key="ingestion|ops-logs-avg-write-response-time"
               operator="above" type="dtmetric"/>
  vmwarevi_adapter3 describe.xml line 7858:
    <Condition key="network|port_statistics|link_state" instanced="true"
               operator="below" type="dtmetric"/>
  alertDefinitionSchema.xsd ConditionType: "For dtmetric and dtsuper:
    above, below, abnormal".

The REST path (``CONDITION_DT`` / ``DT_<direction>``) is correct and must
stay as it is; it is guarded here too so a future "make them match" change
breaks loudly.
"""
from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from vcfcf_core.alerts.render import render_alert_content_xml
from vcfcf_core.symptoms.loader import (
    SymptomDef,
    SymptomValidationError,
    _condition_to_wire,
)

_SYM_ID = "c8d1e671-d0ea-489f-acc4-46e34cc246b6"
_SYM_NAME = "[VCF Content Factory] DT Test Symptom"


def _parse(xml_text: str) -> ET.Element:
    stripped = xml_text.strip()
    if stripped.startswith("<?xml"):
        stripped = stripped[stripped.index("?>") + 2:].lstrip()
    return ET.fromstring(stripped)


def _dt_symptom(direction: str = "ABOVE", instanced: bool = False,
                key: str = "Health|unc_sectors") -> SymptomDef:
    return SymptomDef(
        name=_SYM_NAME,
        adapter_kind="synology_diskstation",
        resource_kind="disk",
        severity="CRITICAL",
        condition={
            "type": "metric_dynamic",
            "key": key,
            "direction": direction,
            "instanced": instanced,
        },
        wait_cycles=1,
        cancel_cycles=1,
        id=_SYM_ID,
    )


def _conditions(xml_text: str) -> list:
    return _parse(xml_text).findall(".//Condition")


class TestDtConditionVendorForm:

    @pytest.mark.parametrize(
        "direction,operator",
        [("ABOVE", "above"), ("BELOW", "below"), ("ABNORMAL", "abnormal")],
    )
    def test_attribute_set_is_exactly_the_vendor_form(self, direction, operator):
        conds = _conditions(render_alert_content_xml([_dt_symptom(direction)], []))
        assert len(conds) == 1
        assert conds[0].attrib == {
            "key": "Health|unc_sectors",
            "operator": operator,
            "type": "dtmetric",
            "instanced": "false",
        }

    def test_synology_failure_shape_never_renders(self):
        """The exact condition the 0.0.0.35 importer rejected."""
        xml_text = render_alert_content_xml([_dt_symptom("ABOVE")], [])
        assert "DT_ABOVE" not in xml_text
        assert 'operator="DT_' not in xml_text
        cond = _conditions(xml_text)[0]
        assert cond.get("type") != "metric"

    def test_instanced_true_matches_vsphere_describe(self):
        cond = _conditions(
            render_alert_content_xml(
                [_dt_symptom("BELOW", instanced=True,
                             key="network|port_statistics|link_state")], []
            )
        )[0]
        assert cond.get("instanced") == "true"
        assert cond.get("operator") == "below"
        assert cond.get("type") == "dtmetric"

    def test_no_hard_threshold_attributes(self):
        cond = _conditions(render_alert_content_xml([_dt_symptom()], []))[0]
        for attr in ("thresholdType", "value", "valueType"):
            assert cond.get(attr) is None, attr

    def test_alertdefs_file_embeds_the_same_form(self, tmp_path: Path):
        """The SDK pak's content/alertdefs/ file embeds the referenced
        symptoms; one bad condition there drops every symptom in the file
        and the alert. Render an alert over the DT symptom and check the
        embedded copy."""
        from vcfcf_core.alerts.loader import load_file as load_alert

        alert_yaml = textwrap.dedent(
            f"""\
            name: "[VCF Content Factory] DT Test Alert"
            description: "DT test alert"
            adapter_kind: synology_diskstation
            resource_kind: disk
            type: 15
            sub_type: 19
            wait_cycles: 1
            cancel_cycles: 1
            criticality: AUTO
            impact:
              badge: HEALTH
            symptom_sets:
              operator: ALL
              sets:
                - defined_on: SELF
                  operator: ALL
                  symptoms:
                    - name: "{_SYM_NAME}"
            """
        )
        p = tmp_path / "alert.yaml"
        p.write_text(alert_yaml, encoding="utf-8")
        alert = load_alert(p, enforce_framework_prefix=False)
        conds = _conditions(render_alert_content_xml([_dt_symptom()], [alert]))
        assert conds, "alert content rendered no Condition"
        for cond in conds:
            assert cond.get("type") == "dtmetric"
            assert cond.get("operator") == "above"

    def test_unknown_direction_raises_in_renderer(self):
        sym = _dt_symptom()
        sym.condition = dict(sym.condition, direction="SIDEWAYS")
        with pytest.raises(ValueError):
            render_alert_content_xml([sym], [])


class TestDtConditionRestUnchanged:

    @pytest.mark.parametrize("direction", ["ABOVE", "BELOW", "ABNORMAL"])
    def test_rest_wire_stays_condition_dt(self, direction):
        wire = _condition_to_wire(
            {"type": "metric_dynamic", "key": "Health|unc_sectors",
             "direction": direction, "instanced": False}
        )
        assert wire["type"] == "CONDITION_DT"
        assert wire["operator"] == f"DT_{direction}"


class TestDtOnSuperMetricRejected:
    """DT on a super metric is XML type="dtsuper" / REST CONDITION_DT_SUPER.
    The factory emits neither, so the loader refuses the case rather than
    ship a condition the importer would drop silently."""

    def test_super_metric_key_rejected(self):
        with pytest.raises(SymptomValidationError, match="super metric"):
            _dt_symptom(
                key="Super Metric|sm_b394eb82-d4d4-47d1-bd7e-0ef267457e52"
            ).validate(enforce_framework_prefix=False)

    def test_plain_metric_key_validates(self):
        _dt_symptom().validate(enforce_framework_prefix=False)

    def test_static_on_super_metric_still_allowed(self):
        SymptomDef(
            name=_SYM_NAME,
            adapter_kind="VMWARE",
            resource_kind="ClusterComputeResource",
            severity="WARNING",
            condition={
                "type": "metric_static",
                "key": "Super Metric|sm_b394eb82-d4d4-47d1-bd7e-0ef267457e52",
                "operator": "GT",
                "value": 0,
            },
            wait_cycles=1,
            cancel_cycles=1,
            id=_SYM_ID,
        ).validate(enforce_framework_prefix=False)
