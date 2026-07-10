"""Alert <State> SymptomSet encoding — multi-tier import regression.

Bug (root-caused by api-explorer; see
knowledge/context/wire-formats/alertdef_symptomset_import.md):
``_render_alert_definition`` emitted one bare ``<SymptomSet ref=.../>``
sibling per symptom directly under ``<State>``, with no ``<SymptomSets>``
compound wrapper. The platform's content importer keeps only the LAST such
sibling and silently drops the rest — proven live: a 4-tier alert survived
import with only its Info tier.

The surviving encoding (proven by the identical vendor alert, which ships in
a real, importable pak) is:
  - group by SET, not by symptom: one ``<SymptomSet>`` per entry in
    ``symptom_sets["sets"]``;
  - a single-symptom set is a bare ``ref=`` attribute on ``<SymptomSet>``;
    a multi-symptom set becomes ``<Symptom ref=.../>`` children of
    ``<SymptomSet operator="...">``;
  - when there are >=2 sets, wrap them all in ONE
    ``<SymptomSets operator="{or|and}">`` (child of ``<State>``);
  - when there is exactly 1 set, omit the wrapper (bare ``<SymptomSet>``
    directly under ``<State>``, matching prior/vendor single-tier output);
  - the non-vendor ``aggregation="any"`` attribute is never emitted.

Vendor ground truth (RULE-016 read-only reference):
    reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
    content/alertdefs/ESXi Host License Expiring.xml

All fixtures are tmp_path-local; no content YAML, network, or install
commands are touched.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


_SYM_A = textwrap.dedent(
    """\
    name: "[VCF Content Factory] Sym A"
    adapter_kind: VMWARE
    resource_kind: HostSystem
    severity: CRITICAL
    wait_cycles: 1
    cancel_cycles: 1
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT
      value: 10
    """
)
_SYM_B = _SYM_A.replace("Sym A", "Sym B")
_SYM_C = _SYM_A.replace("Sym A", "Sym C")
_SYM_D = _SYM_A.replace("Sym A", "Sym D")


def _load_symptoms(tmp_path: Path) -> list:
    from vcfops_symptoms.loader import load_file as load_sym

    names = ["Sym A", "Sym B", "Sym C", "Sym D"]
    bodies = [_SYM_A, _SYM_B, _SYM_C, _SYM_D]
    syms = []
    for name, body in zip(names, bodies):
        p = tmp_path / "symptoms" / f"{name.lower().replace(' ', '_')}.yaml"
        _write(p, body)
        syms.append(load_sym(p, enforce_framework_prefix=False))
    return syms


def _load_alert(tmp_path: Path, alert_yaml: str):
    from vcfops_alerts.loader import load_file as load_alert

    p = tmp_path / "alerts" / "test_alert.yaml"
    _write(p, alert_yaml)
    return load_alert(p, enforce_framework_prefix=False)


_MULTI_SET_ALERT_YAML = textwrap.dedent(
    """\
    name: "[VCF Content Factory] Multi Tier Alert"
    description: "Multi-tier test alert"
    adapter_kind: VMWARE
    resource_kind: HostSystem
    type: 15
    sub_type: 19
    wait_cycles: 1
    cancel_cycles: 1
    criticality: AUTO
    impact:
      badge: HEALTH
    symptom_sets:
      operator: ANY
      sets:
        - defined_on: SELF
          operator: ALL
          symptoms:
            - name: "[VCF Content Factory] Sym A"
        - defined_on: SELF
          operator: ALL
          symptoms:
            - name: "[VCF Content Factory] Sym B"
            - name: "[VCF Content Factory] Sym C"
    """
)

_SINGLE_SET_ALERT_YAML = textwrap.dedent(
    """\
    name: "[VCF Content Factory] Single Tier Alert"
    description: "Single-tier test alert"
    adapter_kind: VMWARE
    resource_kind: HostSystem
    type: 15
    sub_type: 19
    wait_cycles: 1
    cancel_cycles: 1
    criticality: CRITICAL
    impact:
      badge: HEALTH
    symptom_sets:
      operator: ALL
      sets:
        - defined_on: SELF
          operator: ALL
          symptoms:
            - name: "[VCF Content Factory] Sym A"
    """
)

_SINGLE_SET_MULTI_SYMPTOM_ALERT_YAML = textwrap.dedent(
    """\
    name: "[VCF Content Factory] Single Tier AND Alert"
    description: "Single-tier, two-symptom AND test alert"
    adapter_kind: VMWARE
    resource_kind: HostSystem
    type: 15
    sub_type: 19
    wait_cycles: 1
    cancel_cycles: 1
    criticality: CRITICAL
    impact:
      badge: HEALTH
    symptom_sets:
      operator: ALL
      sets:
        - defined_on: SELF
          operator: ALL
          symptoms:
            - name: "[VCF Content Factory] Sym A"
            - name: "[VCF Content Factory] Sym B"
    """
)


class TestMultiSetWrapping:
    def test_multi_set_alert_emits_single_symptomsets_wrapper(self, tmp_path: Path):
        """>=2 sets => exactly one <SymptomSets operator="or"> wrapper, one
        <SymptomSet> child per set (bare ref= for the 1-symptom set,
        <Symptom> children for the 2-symptom set) — matches the vendor
        ESXi Host License Expiring shape byte-for-byte in structure."""
        from vcfops_alerts.render import render_alert_content_xml

        syms = _load_symptoms(tmp_path)
        alert = _load_alert(tmp_path, _MULTI_SET_ALERT_YAML)
        xml_text = render_alert_content_xml(syms, [alert])

        # Exactly one SymptomSets wrapper.
        assert xml_text.count("<SymptomSets") == 1, xml_text
        wrapper_m = re.search(r'<SymptomSets operator="(\w+)">', xml_text)
        assert wrapper_m is not None, xml_text
        assert wrapper_m.group(1) == "or"  # symptom_sets.operator: ANY -> or

        state_m = re.search(r"<State.*?</State>", xml_text, re.S)
        assert state_m is not None
        state_xml = state_m.group(0)

        # Two SymptomSet children of the wrapper.
        assert state_xml.count("<SymptomSet ") + state_xml.count("<SymptomSet>") == 2, state_xml

        # First set: bare ref= (1 symptom), no <Symptom> children.
        assert re.search(r'<SymptomSet applyOn="self" operator="and" ref="[^"]+"\s*/>', state_xml), state_xml

        # Second set: no ref= attribute, two <Symptom ref=.../> children.
        second_set_m = re.search(
            r'<SymptomSet applyOn="self" operator="and">\s*'
            r'<Symptom ref="[^"]+"\s*/>\s*<Symptom ref="[^"]+"\s*/>\s*'
            r'</SymptomSet>',
            state_xml,
        )
        assert second_set_m is not None, state_xml

        # Non-vendor aggregation attribute must never appear.
        assert "aggregation" not in xml_text

        # Impact comes after the SymptomSets wrapper (vendor order).
        assert state_xml.index("</SymptomSets>") < state_xml.index("<Impact")

    def test_multi_set_xml_parses(self, tmp_path: Path):
        import xml.etree.ElementTree as ET
        from vcfops_alerts.render import render_alert_content_xml

        syms = _load_symptoms(tmp_path)
        alert = _load_alert(tmp_path, _MULTI_SET_ALERT_YAML)
        xml_text = render_alert_content_xml(syms, [alert])
        root = ET.fromstring(xml_text)
        assert root.tag == "alertContent"


class TestSingleSetUnchanged:
    """A single-set alert must render unchanged: no <SymptomSets> wrapper,
    the lone <SymptomSet> directly under <State> — the shape that already
    survives import."""

    def test_single_symptom_single_set_no_wrapper(self, tmp_path: Path):
        from vcfops_alerts.render import render_alert_content_xml

        syms = _load_symptoms(tmp_path)
        alert = _load_alert(tmp_path, _SINGLE_SET_ALERT_YAML)
        xml_text = render_alert_content_xml(syms, [alert])

        assert "<SymptomSets" not in xml_text
        state_m = re.search(r"<State.*?</State>", xml_text, re.S)
        assert state_m is not None
        state_xml = state_m.group(0)
        assert re.search(r'<SymptomSet applyOn="self" operator="and" ref="[^"]+"\s*/>', state_xml)
        assert "aggregation" not in state_xml

    def test_multi_symptom_single_set_no_wrapper(self, tmp_path: Path):
        """A single set that AND-combines two symptoms must stay a single
        <SymptomSet> with two <Symptom> children — NOT explode into two
        sibling <SymptomSet> elements (the second defect the doc calls out)."""
        from vcfops_alerts.render import render_alert_content_xml

        syms = _load_symptoms(tmp_path)
        alert = _load_alert(tmp_path, _SINGLE_SET_MULTI_SYMPTOM_ALERT_YAML)
        xml_text = render_alert_content_xml(syms, [alert])

        assert "<SymptomSets" not in xml_text
        assert xml_text.count("<SymptomSet") == 1, xml_text
        state_m = re.search(r"<State.*?</State>", xml_text, re.S)
        assert state_m is not None
        state_xml = state_m.group(0)
        assert state_xml.count("<Symptom ") == 2, state_xml
        assert "aggregation" not in state_xml
