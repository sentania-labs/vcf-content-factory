"""Tests for GAP #1 (super-metric emit + view SM cross-ref),
GAP #2 (symptom pak emit), and GAP #3 (alert pak emit + cross-ref check).

Covers:
  1. SM JSON emitted at content/supermetrics/<name>.json with correct UUID key.
  2. View with supermetric:"<name>" column resolves via sm_scope at build time.
  3. Symptom XML emitted at content/symptomdefs/<name>.xml.
  4. Alert XML emitted at content/alertdefs/<name>.xml (with symptom inline).
  5. Alert referencing a missing symptom raises SdkBuildError (cross-ref guard).
  6. Regression: SM + view + symptom + alert + content/files all package together
     in a single pak without any entry duplicated or dropped.
"""
from __future__ import annotations

import io
import json
import textwrap
import zipfile
from pathlib import Path
from typing import List

import pytest

from vcfops_managementpacks.sdk_builder import (
    SdkBuildError,
    _load_bundled_content,
    _write_outer_pak,
)
from vcfops_managementpacks.sdk_project import SdkProjectDef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    name: str = "Test Adapter", adapter_kind: str = "test_adapter"
) -> SdkProjectDef:
    from vcfops_managementpacks.sdk_project import _derive_entry_class

    return SdkProjectDef(
        name=name,
        version="1.0.0",
        build_number=1,
        adapter_kind=adapter_kind,
        description="Test adapter for content emit tests.",
        tier=2,
        dependencies=[],
        entry_class=_derive_entry_class(adapter_kind),
        source_path=Path("/dev/null"),
    )


def _minimal_adapters_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w"):
        pass
    return buf.getvalue()


def _pak_namelist(pak_path: Path) -> List[str]:
    with zipfile.ZipFile(pak_path, "r") as zf:
        return zf.namelist()


def _pak_read(pak_path: Path, entry: str) -> bytes:
    with zipfile.ZipFile(pak_path, "r") as zf:
        return zf.read(entry)


# ---------------------------------------------------------------------------
# Minimal YAML content helpers
# ---------------------------------------------------------------------------

_SM_UUID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"

_SM_NAME = "Test Super Metric"

_SM_YAML = textwrap.dedent(
    f"""\
    id: {_SM_UUID}
    name: "{_SM_NAME}"
    formula: "avg(${{adaptertype=VMWARE, objecttype=VirtualMachine, metric=cpu|usage_average, depth=1}})"
    description: "CPU average across VMs"
    resource_kinds:
      - resource_kind_key: VirtualMachine
        adapter_kind_key: VMWARE
    unit_id: percent
    """
)

# View name includes the [VCF Content Factory] prefix so load_view() passes
# without enforce_framework_prefix=False.  Column uses supermetric:"<name>"
# syntax to test SM cross-reference resolution.
_VIEW_YAML = textwrap.dedent(
    f"""\
    id: 11112222-3333-4444-5555-666677778888
    name: "[VCF Content Factory] Test View With SM"
    description: "View that references the bundled SM"
    subject:
      adapter_kind: VMWARE
      resource_kind: VirtualMachine
    summary: false
    columns:
      - attribute: "supermetric:\\"Test Super Metric\\""
        display_name: "CPU Average"
        unit: percent
        transformation: AVG
    """
)

_VIEW_YAML_NO_SM = textwrap.dedent(
    """\
    id: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
    name: "[VCF Content Factory] Test View No SM"
    description: "View with plain metric only"
    subject:
      adapter_kind: VMWARE
      resource_kind: VirtualMachine
    summary: false
    columns:
      - attribute: cpu|usage_average
        display_name: "CPU Usage"
        unit: percent
        transformation: AVG
    """
)

_SYMPTOM_NAME = "Test Symptom High CPU"
_SYMPTOM_UUID = "c8d1e671-d0ea-489f-acc4-46e34cc246b6"

_SYMPTOM_YAML = textwrap.dedent(
    f"""\
    name: "{_SYMPTOM_NAME}"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    severity: CRITICAL
    wait_cycles: 2
    cancel_cycles: 2
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT
      value: 90
    """
)

# Same symptom but with an id: UUID field (ported/third-party content)
_SYMPTOM_YAML_WITH_UUID = textwrap.dedent(
    f"""\
    id: {_SYMPTOM_UUID}
    name: "{_SYMPTOM_NAME}"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    severity: CRITICAL
    wait_cycles: 2
    cancel_cycles: 2
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT
      value: 90
    """
)

_ALERT_NAME = "Test Alert High CPU"

_ALERT_YAML = textwrap.dedent(
    f"""\
    name: "{_ALERT_NAME}"
    description: "CPU is critically high"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    type: 16
    sub_type: 3
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
            - name: "{_SYMPTOM_NAME}"
    """
)


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# GAP #1 — Super-metric JSON emit
# ---------------------------------------------------------------------------


class TestSuperMetricEmit:
    """content/supermetrics/<name>.json is written with the correct UUID key."""

    def test_sm_json_written_to_pak(self, tmp_path: Path) -> None:
        """SM JSON appears at content/supermetrics/<name>.json."""
        project_dir = tmp_path / "adapter"
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)

        from vcfops_supermetrics.loader import load_file

        sm = load_file(sm_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm],
        )

        names = _pak_namelist(pak_path)
        assert "content/" in names, "content/ dir entry missing"
        assert "content/supermetrics/" in names, "content/supermetrics/ dir entry missing"
        # Filename is the SM display name (without framework prefix for test SM)
        sm_entries = [n for n in names if n.startswith("content/supermetrics/") and n.endswith(".json")]
        assert len(sm_entries) == 1, f"Expected 1 SM JSON entry, got: {sm_entries}"

    def test_sm_json_uuid_is_top_level_key(self, tmp_path: Path) -> None:
        """The SM UUID is the top-level JSON key in the emitted file."""
        project_dir = tmp_path / "adapter"
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)

        from vcfops_supermetrics.loader import load_file

        sm = load_file(sm_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm],
        )

        sm_entries = [n for n in _pak_namelist(pak_path) if n.startswith("content/supermetrics/") and n.endswith(".json")]
        assert sm_entries, "No SM JSON entry found"
        raw = _pak_read(pak_path, sm_entries[0])
        data = json.loads(raw)
        assert _SM_UUID in data, (
            f"Expected UUID '{_SM_UUID}' as top-level key; got keys: {list(data.keys())}"
        )
        payload = data[_SM_UUID]
        assert payload["name"] == "Test Super Metric"
        assert "formula" in payload
        assert "resourceKinds" in payload

    def test_sm_json_filename_uses_display_name(self, tmp_path: Path) -> None:
        """The JSON filename is <display_name>.json (filesystem-safe)."""
        project_dir = tmp_path / "adapter"
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)

        from vcfops_supermetrics.loader import load_file

        sm = load_file(sm_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm],
        )

        names = _pak_namelist(pak_path)
        # "Test Super Metric.json" — display name preserved as-is (no bracket prefix here)
        assert "content/supermetrics/Test Super Metric.json" in names, (
            f"Expected 'content/supermetrics/Test Super Metric.json'; "
            f"SM entries: {[n for n in names if 'supermetric' in n]}"
        )

    def test_no_supermetrics_no_supermetrics_dir(self, tmp_path: Path) -> None:
        """When no SMs are bundled, content/supermetrics/ is NOT emitted."""
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project, _minimal_adapters_zip(), output_dir
        )
        names = _pak_namelist(pak_path)
        assert not any("supermetric" in n for n in names), (
            f"Unexpected supermetric entries: {[n for n in names if 'supermetric' in n]}"
        )


# ---------------------------------------------------------------------------
# GAP #1 part 2 — View SM cross-reference resolution via sm_scope
# ---------------------------------------------------------------------------


class TestViewSmCrossRefResolution:
    """View columns using supermetric:"<name>" resolve to sm_<uuid> via sm_scope."""

    def test_view_with_sm_column_resolves(self, tmp_path: Path) -> None:
        """View with supermetric:"<name>" renders successfully when SM is bundled."""
        project_dir = tmp_path / "adapter"
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)
        view_path = project_dir / "views" / "test_view.yaml"
        _write_yaml(view_path, _VIEW_YAML)

        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_dashboards.loader import load_view

        sm = load_sm(sm_path, enforce_framework_prefix=False)
        view = load_view(view_path)

        project = _make_project()
        output_dir = tmp_path / "out"
        # Should not raise — sm_scope is derived from the bundled supermetrics
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            views=[view],
            supermetrics=[sm],
        )
        names = _pak_namelist(pak_path)
        view_entries = [n for n in names if "content/reports/" in n and n.endswith("content.xml")]
        assert view_entries, "No view content.xml in pak"

    def test_view_sm_column_uuid_in_xml(self, tmp_path: Path) -> None:
        """The rendered view XML contains 'Super Metric|sm_<uuid>' for the SM column."""
        project_dir = tmp_path / "adapter"
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)
        view_path = project_dir / "views" / "test_view.yaml"
        _write_yaml(view_path, _VIEW_YAML)

        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_dashboards.loader import load_view

        sm = load_sm(sm_path, enforce_framework_prefix=False)
        view = load_view(view_path)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            views=[view],
            supermetrics=[sm],
        )
        # Find the view's content.xml
        names = _pak_namelist(pak_path)
        xml_entries = [n for n in names if "content/reports/" in n and n.endswith("content.xml")]
        assert xml_entries
        xml_bytes = _pak_read(pak_path, xml_entries[0])
        xml_text = xml_bytes.decode("utf-8")
        # The attribute key must contain the SM UUID
        expected_attr = f"Super Metric|sm_{_SM_UUID}"
        assert expected_attr in xml_text, (
            f"Expected attributeKey containing '{expected_attr}' in view XML.\n"
            f"XML snippet: {xml_text[:800]}"
        )


# ---------------------------------------------------------------------------
# GAP #2 — Symptom XML emit
# ---------------------------------------------------------------------------


class TestSymptomEmit:
    """content/symptomdefs/<name>.xml is written with correct XML structure."""

    def test_symptom_xml_written_to_pak(self, tmp_path: Path) -> None:
        """Symptom XML appears at content/symptomdefs/."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)

        from vcfops_symptoms.loader import load_file

        sym = load_file(sym_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
        )

        names = _pak_namelist(pak_path)
        assert "content/" in names
        assert "content/symptomdefs/" in names, "content/symptomdefs/ dir entry missing"
        sym_entries = [n for n in names if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        assert len(sym_entries) == 1, f"Expected 1 symptom XML; got {sym_entries}"

    def test_symptom_xml_contains_symptom_definition_element(self, tmp_path: Path) -> None:
        """Symptom XML has <SymptomDefinition> element with correct name."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)

        from vcfops_symptoms.loader import load_file

        sym = load_file(sym_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
        )

        sym_entries = [n for n in _pak_namelist(pak_path) if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        raw = _pak_read(pak_path, sym_entries[0]).decode("utf-8")
        assert "SymptomDefinition" in raw, "No <SymptomDefinition> in symptom XML"
        assert "Test Symptom High CPU" in raw, "Symptom name not in XML"
        assert "alertContent" in raw, "Root element <alertContent> missing"

    def test_no_symptoms_no_symptomdefs_dir(self, tmp_path: Path) -> None:
        """When no symptoms are bundled, content/symptomdefs/ is NOT emitted."""
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project, _minimal_adapters_zip(), output_dir
        )
        names = _pak_namelist(pak_path)
        assert not any("symptomdefs" in n for n in names), (
            f"Unexpected symptomdefs entries: {[n for n in names if 'symptomdefs' in n]}"
        )

    def test_symptom_xml_id_uses_uuid_when_present(self, tmp_path: Path) -> None:
        """Symptom XML id attr is SymptomDefinition-<uuid> when id: is in YAML."""
        import re as _re
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML_WITH_UUID)

        from vcfops_symptoms.loader import load_file

        sym = load_file(sym_path, enforce_framework_prefix=False)
        assert sym.id == _SYMPTOM_UUID, f"Expected id={_SYMPTOM_UUID!r}; got {sym.id!r}"

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
        )

        sym_entries = [n for n in _pak_namelist(pak_path) if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        assert sym_entries, "No symptom XML in pak"
        raw = _pak_read(pak_path, sym_entries[0]).decode("utf-8")
        # Must emit SymptomDefinition-<uuid>
        assert f'id="SymptomDefinition-{_SYMPTOM_UUID}"' in raw, (
            f"Expected 'id=\"SymptomDefinition-{_SYMPTOM_UUID}\"' in symptom XML; "
            f"got excerpt: {raw[:600]}"
        )
        # Must NOT use the slug form
        assert "SymptomDefinition-VMWARE-" not in raw, (
            "Symptom XML should not use slug-form id when UUID is available"
        )

    def test_symptom_xml_id_uses_slug_when_no_uuid(self, tmp_path: Path) -> None:
        """Symptom XML id attr falls back to SymptomDefinition-<adapter>-<slug> when no id: in YAML."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)  # no id: field

        from vcfops_symptoms.loader import load_file

        sym = load_file(sym_path, enforce_framework_prefix=False)
        assert sym.id is None, f"Expected id=None for symptom without id: field; got {sym.id!r}"

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
        )

        sym_entries = [n for n in _pak_namelist(pak_path) if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        assert sym_entries, "No symptom XML in pak"
        raw = _pak_read(pak_path, sym_entries[0]).decode("utf-8")
        # Falls back to slug form
        assert 'id="SymptomDefinition-VMWARE-' in raw, (
            f"Expected slug-form id 'SymptomDefinition-VMWARE-...' in symptom XML; "
            f"got excerpt: {raw[:400]}"
        )

    def test_alert_symptom_crossref_uses_uuid_when_present(self, tmp_path: Path) -> None:
        """SymptomSet ref= in alert XML matches SymptomDefinition-<uuid> when symptom has id:."""
        import re as _re
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML_WITH_UUID)
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
            alerts=[alert],
        )

        names = _pak_namelist(pak_path)
        sym_entries = [n for n in names if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        alert_entries = [n for n in names if n.startswith("content/alertdefs/") and n.endswith(".xml")]
        assert sym_entries and alert_entries

        sym_raw = _pak_read(pak_path, sym_entries[0]).decode("utf-8")
        alert_raw = _pak_read(pak_path, alert_entries[0]).decode("utf-8")

        expected_id = f"SymptomDefinition-{_SYMPTOM_UUID}"
        assert f'id="{expected_id}"' in sym_raw, (
            f"Symptom XML must use UUID form id; got: {sym_raw[:400]}"
        )
        assert f'ref="{expected_id}"' in alert_raw, (
            f"Alert XML SymptomSet ref must match UUID form; got: {alert_raw[:400]}"
        )

    def test_symptom_xml_has_no_alert_definitions(self, tmp_path: Path) -> None:
        """Symptom-only XML must NOT contain <AlertDefinitions>."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)

        from vcfops_symptoms.loader import load_file

        sym = load_file(sym_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
        )

        sym_entries = [n for n in _pak_namelist(pak_path) if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        raw = _pak_read(pak_path, sym_entries[0]).decode("utf-8")
        assert "AlertDefinition" not in raw, (
            "Symptom XML must not contain AlertDefinition elements"
        )


# ---------------------------------------------------------------------------
# GAP #3 — Alert XML emit + cross-reference validation
# ---------------------------------------------------------------------------


class TestAlertEmit:
    """content/alertdefs/<name>.xml is written with alert + symptom inline."""

    def test_alert_xml_written_to_pak(self, tmp_path: Path) -> None:
        """Alert XML appears at content/alertdefs/."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
            alerts=[alert],
        )

        names = _pak_namelist(pak_path)
        assert "content/" in names
        assert "content/alertdefs/" in names, "content/alertdefs/ dir entry missing"
        alert_entries = [n for n in names if n.startswith("content/alertdefs/") and n.endswith(".xml")]
        assert len(alert_entries) == 1, f"Expected 1 alert XML; got {alert_entries}"

    def test_alert_xml_contains_alert_and_symptom_elements(self, tmp_path: Path) -> None:
        """Alert XML has both <AlertDefinition> and inline <SymptomDefinition>."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
            alerts=[alert],
        )

        alert_entries = [n for n in _pak_namelist(pak_path) if n.startswith("content/alertdefs/") and n.endswith(".xml")]
        raw = _pak_read(pak_path, alert_entries[0]).decode("utf-8")
        assert "AlertDefinition" in raw, "No <AlertDefinition> in alert XML"
        assert "SymptomDefinition" in raw, "No inline <SymptomDefinition> in alert XML"
        assert "Test Alert High CPU" in raw, "Alert name not in XML"
        assert "Test Symptom High CPU" in raw, "Symptom name not in alert XML"

    def test_alert_symptom_cross_ref_id_consistent(self, tmp_path: Path) -> None:
        """The SymptomSet ref= in alert XML matches the SymptomDefinition id= in symptom XML."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
            alerts=[alert],
        )

        names = _pak_namelist(pak_path)
        # Read symptom XML to extract id=
        sym_entries = [n for n in names if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        assert sym_entries, "No symptom XML in pak"
        sym_raw = _pak_read(pak_path, sym_entries[0]).decode("utf-8")

        # Read alert XML to extract ref=
        alert_entries = [n for n in names if n.startswith("content/alertdefs/") and n.endswith(".xml")]
        assert alert_entries, "No alert XML in pak"
        alert_raw = _pak_read(pak_path, alert_entries[0]).decode("utf-8")

        # Extract id= from symptom XML: id="SymptomDefinition-..."
        import re
        sym_ids = re.findall(r'id="(SymptomDefinition-[^"]+)"', sym_raw)
        assert sym_ids, f"No SymptomDefinition id= found in symptom XML: {sym_raw}"

        # Extract ref= from alert XML: ref="SymptomDefinition-..."
        alert_refs = re.findall(r'ref="(SymptomDefinition-[^"]+)"', alert_raw)
        assert alert_refs, f"No SymptomSet ref= found in alert XML: {alert_raw}"

        # Every ref in the alert XML must match an id in the symptom XML
        for ref in alert_refs:
            assert ref in sym_ids, (
                f"Alert XML references symptom id '{ref}' but symptom XML has ids {sym_ids}. "
                "Cross-reference is inconsistent — the alert would fail to import."
            )

    def test_no_alerts_no_alertdefs_dir(self, tmp_path: Path) -> None:
        """When no alerts are bundled, content/alertdefs/ is NOT emitted."""
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project, _minimal_adapters_zip(), output_dir
        )
        names = _pak_namelist(pak_path)
        assert not any("alertdefs" in n for n in names), (
            f"Unexpected alertdefs entries: {[n for n in names if 'alertdefs' in n]}"
        )


# ---------------------------------------------------------------------------
# GAP #3 — Alert→missing-symptom cross-ref guard (build-time check)
# ---------------------------------------------------------------------------


class TestAlertMissingSymptomGuard:
    """Alert referencing a symptom not in bundled_content.symptoms raises SdkBuildError."""

    def test_alert_missing_symptom_raises(self, tmp_path: Path) -> None:
        """SdkBuildError raised when alert references a symptom not in the bundle."""
        project_dir = tmp_path / "adapter"
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_alerts.loader import load_file as load_alert

        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        # symptoms=[] — the referenced symptom "Test Symptom High CPU" is missing
        with pytest.raises(SdkBuildError, match="Test Symptom High CPU"):
            _write_outer_pak(
                project,
                _minimal_adapters_zip(),
                output_dir,
                project_dir=project_dir,
                symptoms=[],
                alerts=[alert],
            )

    def test_alert_missing_symptom_error_names_alert(self, tmp_path: Path) -> None:
        """Error message names both the missing symptom and the alert that requires it."""
        project_dir = tmp_path / "adapter"
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_alerts.loader import load_file as load_alert

        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        with pytest.raises(SdkBuildError) as exc_info:
            _write_outer_pak(
                project,
                _minimal_adapters_zip(),
                output_dir,
                project_dir=project_dir,
                symptoms=[],
                alerts=[alert],
            )
        msg = str(exc_info.value)
        assert "Test Alert High CPU" in msg, f"Alert name not in error: {msg}"
        assert "Test Symptom High CPU" in msg, f"Symptom name not in error: {msg}"
        # Error should also show the expected ID so the operator knows what to fix
        assert "SymptomDefinition-" in msg, f"Expected symptom ID hint in error: {msg}"

    def test_alert_with_matching_symptom_does_not_raise(self, tmp_path: Path) -> None:
        """When the symptom is correctly bundled, no error is raised."""
        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        # Must not raise
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
            alerts=[alert],
        )
        assert pak_path.is_file()


# ---------------------------------------------------------------------------
# Regression — full combined pak (SM + view + symptom + alert + content/files)
# ---------------------------------------------------------------------------


class TestFullCombinedPak:
    """All new content types (SM, view, symptom, alert) plus content/files package
    together correctly — no entry duplicated, no entry dropped."""

    def test_all_content_types_in_single_pak(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "adapter"

        # SM
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)

        # View referencing the SM
        view_path = project_dir / "views" / "test_view.yaml"
        _write_yaml(view_path, _VIEW_YAML)

        # Symptom
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)

        # Alert referencing the symptom
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        # content/files/solutionconfig/
        cf_dir = project_dir / "content" / "files" / "solutionconfig"
        cf_dir.mkdir(parents=True)
        (cf_dir / "esxi_settings.xml").write_text("<settings/>", encoding="utf-8")

        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_dashboards.loader import load_view
        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sm = load_sm(sm_path, enforce_framework_prefix=False)
        view = load_view(view_path)
        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            views=[view],
            supermetrics=[sm],
            symptoms=[sym],
            alerts=[alert],
        )

        names = _pak_namelist(pak_path)

        # Verify content/ root appears exactly once
        assert names.count("content/") == 1, (
            f"content/ appears {names.count('content/')} times (expected 1)"
        )

        # SM
        sm_entries = [n for n in names if n.startswith("content/supermetrics/") and n.endswith(".json")]
        assert len(sm_entries) == 1, f"Expected 1 SM JSON; got {sm_entries}"

        # View
        view_entries = [n for n in names if "content/reports/" in n and n.endswith("content.xml")]
        assert len(view_entries) == 1, f"Expected 1 view XML; got {view_entries}"

        # Symptom
        sym_entries = [n for n in names if n.startswith("content/symptomdefs/") and n.endswith(".xml")]
        assert len(sym_entries) == 1, f"Expected 1 symptom XML; got {sym_entries}"

        # Alert
        alert_entries = [n for n in names if n.startswith("content/alertdefs/") and n.endswith(".xml")]
        assert len(alert_entries) == 1, f"Expected 1 alert XML; got {alert_entries}"

        # content/files/ (safety assertion: non-empty src → non-zero files written)
        cf_entries = [n for n in names if n.startswith("content/files/") and not n.endswith("/")]
        assert "content/files/solutionconfig/esxi_settings.xml" in names, (
            f"content/files entry missing; content/files entries: {cf_entries}"
        )

    def test_view_sm_uuid_present_in_combined_pak(self, tmp_path: Path) -> None:
        """In a combined pak, the view XML must reference the SM UUID from the bundled SM."""
        project_dir = tmp_path / "adapter"
        sm_path = project_dir / "supermetrics" / "test_sm.yaml"
        _write_yaml(sm_path, _SM_YAML)
        view_path = project_dir / "views" / "test_view.yaml"
        _write_yaml(view_path, _VIEW_YAML)
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)
        alert_path = project_dir / "alerts" / "test_alert.yaml"
        _write_yaml(alert_path, _ALERT_YAML)

        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_dashboards.loader import load_view
        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        sm = load_sm(sm_path, enforce_framework_prefix=False)
        view = load_view(view_path)
        sym = load_sym(sym_path, enforce_framework_prefix=False)
        alert = load_alert(alert_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            views=[view],
            supermetrics=[sm],
            symptoms=[sym],
            alerts=[alert],
        )

        view_entries = [n for n in _pak_namelist(pak_path) if "content/reports/" in n and n.endswith("content.xml")]
        assert view_entries
        view_xml = _pak_read(pak_path, view_entries[0]).decode("utf-8")
        assert f"sm_{_SM_UUID}" in view_xml, (
            f"Expected 'sm_{_SM_UUID}' in view XML attributeKey. XML: {view_xml[:600]}"
        )

    def test_content_files_safety_assertion_still_active_in_combined_pak(
        self, tmp_path: Path
    ) -> None:
        """The content/files/ safety assertion fires even when other bundled
        content is also present (regression guard)."""
        from unittest.mock import patch

        project_dir = tmp_path / "adapter"
        sym_path = project_dir / "symptoms" / "test_symptom.yaml"
        _write_yaml(sym_path, _SYMPTOM_YAML)
        cf_dir = project_dir / "content" / "files" / "solutionconfig"
        cf_dir.mkdir(parents=True)
        (cf_dir / "esxi_settings.xml").write_text("<settings/>", encoding="utf-8")

        from vcfops_symptoms.loader import load_file as load_sym

        sym = load_sym(sym_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"

        import builtins

        original_sorted = builtins.sorted
        call_count = [0]

        def _patched_sorted(iterable, *a, **kw):
            items = list(original_sorted(iterable, *a, **kw))
            if items and all(isinstance(p, Path) for p in items):
                if any("content" in str(p) for p in items):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        class _FakePath:
                            def is_file(self):
                                return False
                        return [_FakePath()]
            return items

        with patch("builtins.sorted", _patched_sorted):
            with pytest.raises(SdkBuildError, match="content/files.*non-empty.*zero files"):
                _write_outer_pak(
                    project,
                    _minimal_adapters_zip(),
                    output_dir,
                    project_dir=project_dir,
                    symptoms=[sym],
                )


# ---------------------------------------------------------------------------
# NIT-1 — safe_name filename collision dedup
# ---------------------------------------------------------------------------
# Two display names that sanitize to the same filesystem-safe string must not
# silently overwrite each other in the zip.  The second file gets a "-2" suffix.
# Payload UUIDs / IDs are unaffected — this is filename-only defence.


def _write_yaml_to(path: Path, content: str) -> Path:
    """Write YAML content to path and return path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


_SM_YAML_COLL_A = textwrap.dedent(
    """\
    id: 11110000-0000-0000-0000-000000000001
    name: "My SM"
    formula: "avg(${{adaptertype=VMWARE, objecttype=VirtualMachine, metric=cpu|usage_average, depth=1}})"
    description: "First SM"
    resource_kinds:
      - resource_kind_key: VirtualMachine
        adapter_kind_key: VMWARE
    unit_id: percent
    """
)

_SM_YAML_COLL_B = textwrap.dedent(
    """\
    id: 11110000-0000-0000-0000-000000000002
    name: "My SM"
    formula: "avg(${{adaptertype=VMWARE, objecttype=VirtualMachine, metric=cpu|usage_average, depth=1}})"
    description: "Second SM — same display name, different uuid"
    resource_kinds:
      - resource_kind_key: VirtualMachine
        adapter_kind_key: VMWARE
    unit_id: percent
    """
)

_SYMPTOM_YAML_COLL_A = textwrap.dedent(
    """\
    name: "High CPU"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    severity: CRITICAL
    wait_cycles: 1
    cancel_cycles: 1
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT
      value: 90
    """
)

_SYMPTOM_YAML_COLL_B = textwrap.dedent(
    """\
    name: "High CPU"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    severity: WARNING
    wait_cycles: 1
    cancel_cycles: 1
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT
      value: 80
    """
)

_ALERT_YAML_COLL_A = textwrap.dedent(
    """\
    name: "CPU Alert"
    description: "First CPU alert"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    type: 16
    sub_type: 3
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
            - name: "High CPU"
    """
)

_ALERT_YAML_COLL_B = textwrap.dedent(
    """\
    name: "CPU Alert"
    description: "Second CPU alert — same display name, different config"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    type: 16
    sub_type: 3
    wait_cycles: 2
    cancel_cycles: 2
    criticality: WARNING
    impact:
      badge: HEALTH
    symptom_sets:
      operator: ALL
      sets:
        - defined_on: SELF
          operator: ALL
          symptoms:
            - name: "High CPU"
    """
)


class TestSafeNameCollisionDedup:
    """Two items whose display names sanitize to the same safe_name must both
    appear in the pak with distinct filenames (suffix -2)."""

    def test_sm_collision_both_files_present(self, tmp_path: Path) -> None:
        """Two SMs with identical display names → <name>.json and <name>-2.json."""
        from vcfops_supermetrics.loader import load_file

        project_dir = tmp_path / "adapter"
        sm_a = load_file(
            _write_yaml_to(tmp_path / "sm_a.yaml", _SM_YAML_COLL_A),
            enforce_framework_prefix=False,
        )
        sm_b = load_file(
            _write_yaml_to(tmp_path / "sm_b.yaml", _SM_YAML_COLL_B),
            enforce_framework_prefix=False,
        )

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm_a, sm_b],
        )

        sm_entries = sorted(
            n for n in _pak_namelist(pak_path)
            if n.startswith("content/supermetrics/") and n.endswith(".json")
        )
        assert len(sm_entries) == 2, (
            f"Expected 2 SM JSON entries (dedup); got: {sm_entries}"
        )
        stems = {
            e.removeprefix("content/supermetrics/").removesuffix(".json")
            for e in sm_entries
        }
        # One stem should be the base name and the other should be base + "-2".
        # Identify the base (shorter) stem.
        base_stem = min(stems, key=len)
        assert f"{base_stem}-2" in stems, (
            f"Expected dedup suffix '-2' on second entry; got stems: {stems}"
        )

    def test_symptom_collision_both_files_present(self, tmp_path: Path) -> None:
        """Two symptoms with identical display names → <name>.xml and <name>-2.xml."""
        from vcfops_symptoms.loader import load_file

        project_dir = tmp_path / "adapter"
        sym_a = load_file(
            _write_yaml_to(tmp_path / "sym_a.yaml", _SYMPTOM_YAML_COLL_A),
            enforce_framework_prefix=False,
        )
        sym_b = load_file(
            _write_yaml_to(tmp_path / "sym_b.yaml", _SYMPTOM_YAML_COLL_B),
            enforce_framework_prefix=False,
        )

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym_a, sym_b],
        )

        sym_entries = sorted(
            n for n in _pak_namelist(pak_path)
            if n.startswith("content/symptomdefs/") and n.endswith(".xml")
        )
        assert len(sym_entries) == 2, (
            f"Expected 2 symptomdef XML entries (dedup); got: {sym_entries}"
        )
        stems = {
            e.removeprefix("content/symptomdefs/").removesuffix(".xml")
            for e in sym_entries
        }
        base_stem = min(stems, key=len)
        assert f"{base_stem}-2" in stems, (
            f"Expected dedup suffix '-2' on second entry; got stems: {stems}"
        )

    def test_alert_collision_both_files_present(self, tmp_path: Path) -> None:
        """Two alerts with identical display names → <name>.xml and <name>-2.xml."""
        from vcfops_symptoms.loader import load_file as load_sym
        from vcfops_alerts.loader import load_file as load_alert

        project_dir = tmp_path / "adapter"
        sym = load_sym(
            _write_yaml_to(tmp_path / "sym.yaml", _SYMPTOM_YAML_COLL_A),
            enforce_framework_prefix=False,
        )
        alert_a = load_alert(
            _write_yaml_to(tmp_path / "alert_a.yaml", _ALERT_YAML_COLL_A),
            enforce_framework_prefix=False,
        )
        alert_b = load_alert(
            _write_yaml_to(tmp_path / "alert_b.yaml", _ALERT_YAML_COLL_B),
            enforce_framework_prefix=False,
        )

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            symptoms=[sym],
            alerts=[alert_a, alert_b],
        )

        alert_entries = sorted(
            n for n in _pak_namelist(pak_path)
            if n.startswith("content/alertdefs/") and n.endswith(".xml")
        )
        assert len(alert_entries) == 2, (
            f"Expected 2 alertdef XML entries (dedup); got: {alert_entries}"
        )
        stems = {
            e.removeprefix("content/alertdefs/").removesuffix(".xml")
            for e in alert_entries
        }
        base_stem = min(stems, key=len)
        assert f"{base_stem}-2" in stems, (
            f"Expected dedup suffix '-2' on second entry; got stems: {stems}"
        )


# ---------------------------------------------------------------------------
# SM formula cross-reference resolution (_resolve_sm_formula)
# ---------------------------------------------------------------------------

_SM_REF_UUID = "b6f20136-03bf-48d3-8b80-429f59d21374"
_SM_REF_NAME = "ESXi Host Availability"
_SM_CONSUMER_UUID = "98997eae-62ba-4614-a622-11082c48ff00"
_SM_CONSUMER_NAME = "ESXi Hosts Average Availability"

# SM YAML for a referenced SM (no cross-refs in formula)
_SM_YAML_REF = textwrap.dedent(
    f"""\
    id: {_SM_REF_UUID}
    name: "{_SM_REF_NAME}"
    formula: "avg(${{adaptertype=VMWARE, objecttype=HostSystem, metric=availability|availability, depth=1}})"
    description: "ESXi host availability percent."
    resource_kinds:
      - resource_kind_key: HostSystem
        adapter_kind_key: VMWARE
    unit_id: percent
    """
)

# SM YAML for a consumer SM whose formula references the SM above via @supermetric:
_SM_YAML_CONSUMER = textwrap.dedent(
    f"""\
    id: {_SM_CONSUMER_UUID}
    name: "{_SM_CONSUMER_NAME}"
    formula: |
      avg(${{adaptertype=VMWARE, objecttype=HostSystem, attribute=@supermetric:"{_SM_REF_NAME}", depth=5}})
    description: "Average availability across all ESXi hosts."
    resource_kinds:
      - resource_kind_key: VMwareAdapter Instance
        adapter_kind_key: VMWARE
    unit_id: percent
    """
)

# SM YAML with NO cross-references in formula (regression/no-op guard)
_SM_YAML_PLAIN_NOREF = textwrap.dedent(
    """\
    id: 11112222-3333-4444-5555-000000000000
    name: "Plain Metric SM"
    formula: "avg(${adaptertype=VMWARE, objecttype=VirtualMachine, metric=cpu|usage_average, depth=1})"
    description: "CPU average, no SM cross-ref."
    resource_kinds:
      - resource_kind_key: VirtualMachine
        adapter_kind_key: VMWARE
    unit_id: percent
    """
)


class TestSmFormulaResolution:
    """_resolve_sm_formula resolves @supermetric: tokens to Super Metric|sm_<uuid>."""

    def test_resolve_sm_crossref_in_formula(self, tmp_path: Path) -> None:
        """Formula with @supermetric:"<name>" emits Super Metric|sm_<uuid> in pak JSON."""
        from vcfops_supermetrics.loader import load_file

        project_dir = tmp_path / "adapter"
        sm_ref_path = _write_yaml_to(tmp_path / "sm_ref.yaml", _SM_YAML_REF)
        sm_consumer_path = _write_yaml_to(tmp_path / "sm_consumer.yaml", _SM_YAML_CONSUMER)

        sm_ref = load_file(sm_ref_path, enforce_framework_prefix=False)
        sm_consumer = load_file(sm_consumer_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm_ref, sm_consumer],
        )

        with zipfile.ZipFile(pak_path, "r") as zf:
            entries = zf.namelist()
            consumer_entry = next(
                (e for e in entries
                 if "supermetrics" in e and "ESXi Hosts Average Availability" in e),
                None,
            )
            assert consumer_entry is not None, (
                f"Consumer SM JSON not found in pak; entries: "
                f"{[e for e in entries if 'supermetric' in e]}"
            )
            raw = zf.read(consumer_entry)

        data = json.loads(raw)
        payload = data[_SM_CONSUMER_UUID]
        formula = payload["formula"]

        expected_token = f"Super Metric|sm_{_SM_REF_UUID}"
        assert expected_token in formula, (
            f"Expected '{expected_token}' in resolved formula; got: {formula!r}"
        )
        assert "@supermetric:" not in formula, (
            f"Unresolved @supermetric: token found in emitted formula: {formula!r}"
        )

    def test_sm_with_no_crossref_formula_unchanged(self, tmp_path: Path) -> None:
        """SM formula with no @supermetric: token is emitted unchanged."""
        from vcfops_supermetrics.loader import load_file

        project_dir = tmp_path / "adapter"
        sm_plain_path = _write_yaml_to(tmp_path / "sm_plain2.yaml", _SM_YAML_PLAIN_NOREF)
        sm_plain = load_file(sm_plain_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm_plain],
        )

        with zipfile.ZipFile(pak_path, "r") as zf:
            sm_entries = [e for e in zf.namelist() if "supermetrics" in e and e.endswith(".json")]
            assert sm_entries
            raw = zf.read(sm_entries[0])

        data = json.loads(raw)
        formula = data["11112222-3333-4444-5555-000000000000"]["formula"]
        assert "cpu|usage_average" in formula, (
            f"Plain formula was unexpectedly mutated: {formula!r}"
        )
        assert "@supermetric:" not in formula

    def test_sm_crossref_to_unbundled_sm_raises(self, tmp_path: Path) -> None:
        """SdkBuildError raised when a formula references an SM not in the bundle."""
        from vcfops_supermetrics.loader import load_file

        project_dir = tmp_path / "adapter"
        sm_consumer_path = _write_yaml_to(tmp_path / "sm_consumer.yaml", _SM_YAML_CONSUMER)
        sm_consumer = load_file(sm_consumer_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        with pytest.raises(SdkBuildError) as exc_info:
            _write_outer_pak(
                project,
                _minimal_adapters_zip(),
                output_dir,
                project_dir=project_dir,
                supermetrics=[sm_consumer],  # ref SM is NOT in bundle
            )
        msg = str(exc_info.value)
        assert _SM_REF_NAME in msg, (
            f"Error message must name the missing SM '{_SM_REF_NAME}'; got: {msg}"
        )
        assert _SM_CONSUMER_NAME in msg, (
            f"Error message must name the SM with the bad formula "
            f"'{_SM_CONSUMER_NAME}'; got: {msg}"
        )

    def test_already_resolved_token_left_untouched(self, tmp_path: Path) -> None:
        """A formula with Super Metric|sm_<uuid> already present is not double-resolved."""
        from vcfops_supermetrics.loader import load_file

        already_resolved_yaml = textwrap.dedent(
            f"""\
            id: ffffffff-0000-0000-0000-000000000001
            name: "Already Resolved SM"
            formula: "avg(${{adaptertype=VMWARE, objecttype=HostSystem, attribute=Super Metric|sm_{_SM_REF_UUID}, depth=5}})"
            description: "Already has the native token."
            resource_kinds:
              - resource_kind_key: HostSystem
                adapter_kind_key: VMWARE
            unit_id: percent
            """
        )
        project_dir = tmp_path / "adapter"
        sm_path = _write_yaml_to(tmp_path / "sm_already.yaml", already_resolved_yaml)
        sm = load_file(sm_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            supermetrics=[sm],
        )

        with zipfile.ZipFile(pak_path, "r") as zf:
            sm_entries = [e for e in zf.namelist() if "supermetrics" in e and e.endswith(".json")]
            assert sm_entries
            raw = zf.read(sm_entries[0])

        data = json.loads(raw)
        formula = data["ffffffff-0000-0000-0000-000000000001"]["formula"]
        assert f"Super Metric|sm_{_SM_REF_UUID}" in formula, (
            f"Expected native token in formula; got: {formula!r}"
        )
        assert "Super Metric|sm_Super Metric|sm_" not in formula, (
            f"Double-resolution detected in formula: {formula!r}"
        )
