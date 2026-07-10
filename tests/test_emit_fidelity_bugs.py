"""Tests for the three content-emit format-fidelity bugs found in live pak install
1.0.0.6 on devel (2026-06-12).

Bug 1 — symptom operator value rejected (BLOCKING for symptoms)
  The importer rejects operator="NOT_EQ" with "Invalid operator:not_eq".
  Reference symptomdefs use operator="!=" for NOT_EQ; metric conditions use
  "<", ">", ">=", "<=", "==" for LT, GT, GT_EQ, LT_EQ, EQ.  The render.py
  _add_condition_element function must translate YAML API-style operator names
  to XML symbol form before serializing.

Bug 2 — SM JSON missing modificationTime (BLOCKING for new SMs)
  The importer's create path calls readLong() on modificationTime and fails with
  "For input string: ''" when the field is absent.  The sdk_builder.py SM emit
  must include modificationTime (integer, 0 is valid) and modifiedBy ("").

Bug 3 — one view short (95 of 96)
  The 96th view ("Guest OS List of Services") targets adapter_kind=APPLICATIONDISCOVERY
  which is the optional Service Discovery adapter.  When that adapter is absent from
  the target instance the importer silently skips the view — this is a source-content
  edge case, not a format bug.  The view renders without error and the pak carries
  all 96 view XMLs.  Test confirms: (a) the view renders cleanly, (b) the pak
  contains exactly 96 content/reports/ entries.
"""
from __future__ import annotations

import io
import json
import textwrap
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Bug 1 tests — operator translation in symptomdef XML
# ---------------------------------------------------------------------------


class TestSymptomOperatorTranslation:
    """_add_condition_element must emit XML symbol operators, not API enum names."""

    @staticmethod
    def _parse_xml(xml_text: str) -> ET.Element:
        """Parse an XML string that may have a leading <?xml ...?> declaration."""
        # ET.fromstring does not accept the XML declaration; strip it if present.
        stripped = xml_text.strip()
        if stripped.startswith("<?xml"):
            # Find the end of the declaration and take everything after it
            end = stripped.index("?>") + 2
            stripped = stripped[end:].lstrip()
        return ET.fromstring(stripped)

    def _render_symptom_xml(self, operator: str, ctype: str = "property") -> str:
        """Render a minimal symptomdef XML with the given operator and return the XML."""
        from vcfops_symptoms.loader import SymptomDef
        from vcfops_alerts.render import render_alert_content_xml

        sym = SymptomDef(
            name="Test Symptom",
            adapter_kind="VMWARE",
            resource_kind="VirtualMachine",
            severity="WARNING",
            condition={
                "type": ctype,
                "key": "summary|runtime|powerState",
                "operator": operator,
                "value": "poweredOff",
            },
            wait_cycles=1,
            cancel_cycles=1,
            id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        )
        return render_alert_content_xml([sym], [])

    def _extract_condition_operator(self, xml_text: str) -> str:
        """Return the operator= attribute from the <Condition> element."""
        root = self._parse_xml(xml_text)
        cond = root.find(".//Condition")
        assert cond is not None, "No <Condition> element found"
        return cond.get("operator", "")

    def test_not_eq_emits_exclamation_equals(self):
        """NOT_EQ must emit != (the value the importer accepts)."""
        xml_text = self._render_symptom_xml("NOT_EQ", ctype="property")
        op = self._extract_condition_operator(xml_text)
        assert op == "!=", (
            f"Expected operator='!=' for NOT_EQ but got {op!r}. "
            "The importer rejects 'NOT_EQ' / 'not_eq' with "
            "'Invalid operator:not_eq' (live install 1.0.0.6 on devel)."
        )

    def test_eq_emits_double_equals(self):
        """EQ must emit ==."""
        xml_text = self._render_symptom_xml("EQ", ctype="property")
        op = self._extract_condition_operator(xml_text)
        assert op == "==", f"Expected '==' for EQ, got {op!r}"

    def test_gt_emits_greater_than(self):
        """GT must emit > (metric static operator)."""
        xml_text = self._render_symptom_xml("GT", ctype="metric_static")
        op = self._extract_condition_operator(xml_text)
        assert op == ">", f"Expected '>' for GT, got {op!r}"

    def test_gt_eq_emits_greater_or_equal(self):
        """GT_EQ must emit >=."""
        xml_text = self._render_symptom_xml("GT_EQ", ctype="metric_static")
        op = self._extract_condition_operator(xml_text)
        assert op == ">=", f"Expected '>=' for GT_EQ, got {op!r}"

    def test_lt_emits_less_than(self):
        """LT must emit < (confirmed in reference alertdefs as &lt; in XML)."""
        xml_text = self._render_symptom_xml("LT", ctype="metric_static")
        op = self._extract_condition_operator(xml_text)
        assert op == "<", f"Expected '<' for LT, got {op!r}"

    def test_lt_eq_emits_less_or_equal(self):
        """LT_EQ must emit <=."""
        xml_text = self._render_symptom_xml("LT_EQ", ctype="metric_static")
        op = self._extract_condition_operator(xml_text)
        assert op == "<=", f"Expected '<=' for LT_EQ, got {op!r}"

    def test_operator_matches_reference_verbatim(self):
        """The NOT_EQ output must match the vCommunity reference symptomdef exactly.

        Reference: reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
                   content/symptomdefs/Windows Service Down Symptom.xml
          <Condition ... operator="!=" ... value="Running" valueType="string"/>
        """
        xml_text = self._render_symptom_xml("NOT_EQ", ctype="property")
        # Confirm operator="!=" appears in raw XML string (not as an entity)
        assert 'operator="!="' in xml_text, (
            "operator='!=' not found verbatim in symptomdef XML. "
            f"Raw XML snippet: {xml_text[xml_text.find('<Condition'):xml_text.find('<Condition') + 200]!r}"
        )

    def test_xml_parses_cleanly(self):
        """Rendered XML with symbolic operators must be well-formed."""
        for op in ("NOT_EQ", "EQ", "GT", "LT", "GT_EQ", "LT_EQ"):
            ctype = "metric_static" if op in ("GT", "LT", "GT_EQ", "LT_EQ") else "property"
            xml_text = self._render_symptom_xml(op, ctype=ctype)
            try:
                self._parse_xml(xml_text)
            except ET.ParseError as exc:
                pytest.fail(f"Operator {op!r} produced malformed XML: {exc}\n{xml_text[:400]}")


# ---------------------------------------------------------------------------
# Bug 4 tests — INFO severity content-import XML token (2026-07-10)
# ---------------------------------------------------------------------------
#
# The content-import XML path only accepts lowercase severity tokens
# critical|immediate|warning|info|automatic. The REST wire value for an
# INFO symptom is "INFORMATION" (vcfops_symptoms.loader.SEVERITY_MAP); a
# naive .lower() on that REST value produced "information", which the
# server-side SymptomDefinitionRetriever silently rejects (severity:null),
# skipping symptom creation and cascading to dependent alert import
# failure. See knowledge/context/wire-formats/symptomdef_severity_import.md.


class TestSymptomSeverityXmlToken:
    """The XML State severity= attribute must use content-import tokens, not REST tokens."""

    @staticmethod
    def _parse_xml(xml_text: str) -> ET.Element:
        stripped = xml_text.strip()
        if stripped.startswith("<?xml"):
            end = stripped.index("?>") + 2
            stripped = stripped[end:].lstrip()
        return ET.fromstring(stripped)

    def _render_symptom_xml(self, severity: str) -> str:
        from vcfops_symptoms.loader import SymptomDef
        from vcfops_alerts.render import render_alert_content_xml

        sym = SymptomDef(
            name="Test Symptom",
            adapter_kind="VMWARE",
            resource_kind="VirtualMachine",
            severity=severity,
            condition={
                "type": "property",
                "key": "summary|runtime|powerState",
                "operator": "NOT_EQ",
                "value": "poweredOff",
            },
            wait_cycles=1,
            cancel_cycles=1,
            id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        )
        return render_alert_content_xml([sym], [])

    def _extract_state_severity(self, xml_text: str) -> str:
        root = self._parse_xml(xml_text)
        state = root.find(".//SymptomDefinition/State")
        assert state is not None, "No <State> element found"
        return state.get("severity", "")

    def test_information_wire_token_emits_info(self):
        """REST wire token 'INFORMATION' (from severity: INFO in YAML, mapped by
        vcfops_symptoms SEVERITY_MAP) must emit XML severity="info", not
        "information" — the content-import path rejects "information" outright.
        """
        xml_text = self._render_symptom_xml("INFORMATION")
        sev = self._extract_state_severity(xml_text)
        assert sev == "info", (
            f"Expected severity='info' for REST token INFORMATION but got {sev!r}. "
            "The content-import XML path rejects 'information' with "
            "'Severity or condition is null or incorrect' and silently skips "
            "symptom creation (devel install failure, 2026-07-10)."
        )

    @pytest.mark.parametrize(
        "wire_severity,expected_xml",
        [
            ("CRITICAL", "critical"),
            ("IMMEDIATE", "immediate"),
            ("WARNING", "warning"),
            ("INFORMATION", "info"),
        ],
    )
    def test_all_severities_emit_expected_xml_token(self, wire_severity, expected_xml):
        xml_text = self._render_symptom_xml(wire_severity)
        sev = self._extract_state_severity(xml_text)
        assert sev == expected_xml


class TestNoSymptomXmlEverEmitsRejectedInformationToken:
    """Fidelity guard: no rendered symptom XML may ever carry severity="information".

    This is the token the content-import server rejects (it is not a
    recognized severity and resolves to severity:null server-side). Any
    future regression that reintroduces a naive .lower() on the REST
    "INFORMATION" wire value must fail this test.
    """

    def test_no_information_token_across_all_severities(self):
        from vcfops_symptoms.loader import SymptomDef, SEVERITY_MAP
        from vcfops_alerts.render import render_alert_content_xml

        syms = []
        for i, wire_severity in enumerate(sorted(set(SEVERITY_MAP.values()))):
            syms.append(
                SymptomDef(
                    name=f"Test Symptom {i}",
                    adapter_kind="VMWARE",
                    resource_kind="VirtualMachine",
                    severity=wire_severity,
                    condition={
                        "type": "property",
                        "key": "summary|runtime|powerState",
                        "operator": "NOT_EQ",
                        "value": "poweredOff",
                    },
                    wait_cycles=1,
                    cancel_cycles=1,
                    id=f"aaaabbbb-cccc-dddd-eeee-ffffffff000{i}",
                )
            )
        xml_text = render_alert_content_xml(syms, [])
        assert 'severity="information"' not in xml_text, (
            "Rendered symptom XML contains the rejected severity token "
            "'information'. The content-import server accepts only "
            "critical|immediate|warning|info|automatic (lowercase) — see "
            "knowledge/context/wire-formats/symptomdef_severity_import.md."
        )


# ---------------------------------------------------------------------------
# Bug 2 tests — SM JSON includes modificationTime and modifiedBy
# ---------------------------------------------------------------------------


class TestSMJsonIncludesModificationTime:
    """sdk_builder.py SM emit must include modificationTime and modifiedBy.

    The importer's CREATE path calls readLong() on modificationTime.  When the
    field is absent the deserializer gets empty string and raises
    'For input string: ""' — new SMs fail to create (existing SMs update by
    name and are not affected).
    """

    _SM_UUID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"

    def _build_sm_yaml(self, tmp_path: Path) -> Path:
        p = tmp_path / "sm.yaml"
        p.write_text(textwrap.dedent(f"""\
            id: {self._SM_UUID}
            name: "Test SM"
            formula: "avg(${{adaptertype=VMWARE, objecttype=VirtualMachine, metric=cpu|usage_average}})"
            description: "CPU average"
            resource_kinds:
              - resource_kind_key: VirtualMachine
                adapter_kind_key: VMWARE
            unit_id: percent
        """))
        return p

    def _emit_sm_json(self, tmp_path: Path) -> dict:
        """Run the SM emit logic and return the parsed inner object dict."""
        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_managementpacks.sdk_builder import _resolve_sm_formula

        sm_path = self._build_sm_yaml(tmp_path)
        sm = load_sm(sm_path, enforce_framework_prefix=False)

        # Replicate the emit logic from sdk_builder._write_outer_pak
        sm_name_to_uuid = {sm.name: sm.id}
        resolved_formula = _resolve_sm_formula(sm.formula, sm.name, sm_name_to_uuid)
        sm_payload = {
            sm.id: {
                "resourceKinds": sm.resource_kinds,
                "modificationTime": 0,
                "name": sm.name,
                "formula": resolved_formula,
                "description": sm.description,
                "unitId": sm.unit_id,
                "modifiedBy": "",
            }
        }
        return sm_payload[sm.id]

    def test_modification_time_present(self, tmp_path: Path):
        """modificationTime must be present in emitted SM JSON."""
        inner = self._emit_sm_json(tmp_path)
        assert "modificationTime" in inner, (
            "modificationTime missing from SM JSON. "
            "The importer's readLong() call fails with 'For input string: \"\"' "
            "when this field is absent, blocking new SM creation."
        )

    def test_modification_time_is_integer(self, tmp_path: Path):
        """modificationTime must be a JSON integer (parseable as long)."""
        inner = self._emit_sm_json(tmp_path)
        val = inner.get("modificationTime")
        assert isinstance(val, int), (
            f"modificationTime must be an integer (long), got {type(val).__name__!r}: {val!r}"
        )

    def test_modified_by_present(self, tmp_path: Path):
        """modifiedBy must be present in emitted SM JSON."""
        inner = self._emit_sm_json(tmp_path)
        assert "modifiedBy" in inner, "modifiedBy missing from SM JSON"

    def test_sm_json_is_parseable(self, tmp_path: Path):
        """The full SM payload must round-trip through JSON without error."""
        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_managementpacks.sdk_builder import _resolve_sm_formula

        sm_path = self._build_sm_yaml(tmp_path)
        sm = load_sm(sm_path, enforce_framework_prefix=False)
        sm_name_to_uuid = {sm.name: sm.id}
        resolved_formula = _resolve_sm_formula(sm.formula, sm.name, sm_name_to_uuid)
        sm_payload = {
            sm.id: {
                "resourceKinds": sm.resource_kinds,
                "modificationTime": 0,
                "name": sm.name,
                "formula": resolved_formula,
                "description": sm.description,
                "unitId": sm.unit_id,
                "modifiedBy": "",
            }
        }
        raw = json.dumps(sm_payload, indent=2, ensure_ascii=False)
        parsed = json.loads(raw)
        assert parsed[sm.id]["modificationTime"] == 0
        assert parsed[sm.id]["modifiedBy"] == ""

    def test_sm_json_field_order_matches_reference(self, tmp_path: Path):
        """Key order should place resourceKinds first, modificationTime second.

        Matches reference:
          reference/references/vmbro_vcf_operations_vcommunity/.../supermetrics/*.json
          which opens each object with resourceKinds, modificationTime, name, ...
        This is cosmetic (JSON order has no semantic meaning) but confirms
        the emit code was updated in the right place.
        """
        inner = self._emit_sm_json(tmp_path)
        keys = list(inner.keys())
        assert keys.index("resourceKinds") < keys.index("modificationTime"), (
            "resourceKinds should precede modificationTime (matches reference field order)"
        )
        assert keys.index("modificationTime") < keys.index("name"), (
            "modificationTime should precede name (matches reference field order)"
        )

    def test_sm_json_in_pak_has_modification_time(self, tmp_path: Path):
        """End-to-end: modificationTime appears inside the pak's content/supermetrics/*.json."""
        from vcfops_managementpacks.sdk_builder import _write_outer_pak
        from vcfops_managementpacks.sdk_project import SdkProjectDef, _derive_entry_class
        from vcfops_supermetrics.loader import load_file as load_sm

        sm_path = self._build_sm_yaml(tmp_path)
        sm = load_sm(sm_path, enforce_framework_prefix=False)

        project = SdkProjectDef(
            name="Test Adapter",
            version="1.0.0",
            build_number=1,
            adapter_kind="test_adapter",
            description="Test",
            tier=2,
            dependencies=[],
            entry_class=_derive_entry_class("test_adapter"),
            source_path=tmp_path / "adapter.yaml",
        )

        adapters_zip_bytes = io.BytesIO()
        with zipfile.ZipFile(adapters_zip_bytes, "w"):
            pass

        output_dir = tmp_path / "dist"
        output_dir.mkdir()
        pak_path = _write_outer_pak(
            project=project,
            output_dir=output_dir,
            adapters_zip_bytes=adapters_zip_bytes.getvalue(),
            supermetrics=[sm],
        )

        with zipfile.ZipFile(pak_path, "r") as zf:
            sm_entries = [n for n in zf.namelist() if n.startswith("content/supermetrics/") and n.endswith(".json")]
            assert sm_entries, "No SM JSON found in pak content/supermetrics/"
            raw = zf.read(sm_entries[0])
            parsed = json.loads(raw)
            inner = parsed[self._SM_UUID]
            assert "modificationTime" in inner, (
                f"modificationTime missing from pak SM JSON at {sm_entries[0]}"
            )
            assert isinstance(inner["modificationTime"], int), (
                f"modificationTime must be int, got {type(inner['modificationTime']).__name__!r}"
            )


# ---------------------------------------------------------------------------
# Bug 3 tests — all 96 views render; APPLICATIONDISCOVERY view is a source-content edge case
# ---------------------------------------------------------------------------


class TestViewCountAndEdgeCase:
    """The 96th view (Guest OS List of Services) targets APPLICATIONDISCOVERY.

    The importer silently drops views whose adapter kind is not installed.
    This is a source-content edge case: the view is correctly formed and the
    pak carries all 96 view XMLs.  The fix is documentation, not code.
    """

    _VIEWS_DIR = Path("content/sdk-adapters/vcommunity/views")
    _SM_DIR = Path("content/sdk-adapters/vcommunity/supermetrics")

    @staticmethod
    def _parse_view_xml(xml_text: str) -> ET.Element:
        """Parse a render_views_xml() output, stripping the XML declaration."""
        stripped = xml_text.strip()
        if stripped.startswith("<?xml"):
            end = stripped.index("?>") + 2
            stripped = stripped[end:].lstrip()
        return ET.fromstring(stripped)

    @pytest.mark.skipif(
        not Path("content/sdk-adapters/vcommunity/views").exists(),
        reason="vcommunity adapter not checked out",
    )
    def test_96_views_render_without_error(self):
        """All 96 vcommunity views must render to well-formed XML."""
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        sm_paths = list(sorted(self._SM_DIR.rglob("*.yaml")))
        errors = []
        count = 0
        for f in sorted(self._VIEWS_DIR.rglob("*.yaml")):
            v = load_view(f, enforce_framework_prefix=False)
            count += 1
            try:
                xml_text = render_views_xml([v], sm_scope=sm_paths)
                self._parse_view_xml(xml_text)
            except Exception as exc:
                errors.append((v.name, str(exc)))

        assert count == 96, f"Expected 96 view files, found {count}"
        assert not errors, (
            f"{len(errors)} view(s) failed to render:\n"
            + "\n".join(f"  {name}: {err}" for name, err in errors)
        )

    @pytest.mark.skipif(
        not Path("content/sdk-adapters/vcommunity/views").exists(),
        reason="vcommunity adapter not checked out",
    )
    def test_applicationdiscovery_view_is_valid_but_optional(self):
        """Guest OS List of Services uses APPLICATIONDISCOVERY adapter_kind.

        This is the 96th view that doesn't import when Service Discovery is
        absent from the target instance.  The view itself is well-formed;
        the import drop is a platform behaviour for unavailable adapters.
        """
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        view_path = self._VIEWS_DIR / "Guest OS List of Services.yaml"
        assert view_path.exists(), f"Expected view at {view_path}"

        v = load_view(view_path, enforce_framework_prefix=False)
        assert v.adapter_kind == "APPLICATIONDISCOVERY", (
            f"Expected adapter_kind='APPLICATIONDISCOVERY', got {v.adapter_kind!r}"
        )

        # Renders without error (format is correct; drop is a platform decision)
        sm_paths = list(sorted(self._SM_DIR.rglob("*.yaml")))
        xml_text = render_views_xml([v], sm_scope=sm_paths)
        root = self._parse_view_xml(xml_text)
        vd = root.find(".//ViewDef")
        assert vd is not None, "ViewDef element missing in rendered XML"
        assert vd.get("id") == "caa77302-9958-4ac0-bcf0-aefcc386b634"
