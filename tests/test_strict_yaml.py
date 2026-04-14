"""Tests for duplicate-key rejection across all vcfops_* loaders.

Each loader now uses a strict YAML parser that raises on duplicate
top-level keys.  This test suite verifies:

  1. A YAML file with a duplicated top-level key (e.g. two ``id:``
     lines) is rejected with a clear error message that names the
     duplicated key.
  2. A valid YAML file (single ``id:``) continues to load without
     error.

Tests use ``tmp_path`` fixtures to write minimal-but-valid YAML
fixtures that exercise only the strict-key guard, not full schema
validation.  The ``yaml_utils.strict_load`` helper used by
vcfops_dashboards is also tested directly.

Production incident reference: 2026-04-14 — stacked ``id:`` lines
in view YAMLs caused transient UUIDs in Views.zip, breaking widget
cross-references on the server.
"""
from __future__ import annotations

import textwrap
import uuid
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Direct helper test (vcfops_dashboards.yaml_utils)
# ---------------------------------------------------------------------------


def test_strict_load_rejects_duplicate_key():
    from vcfops_dashboards.yaml_utils import strict_load

    doc = textwrap.dedent("""\
        id: 1234
        name: foo
        id: 5678
    """)
    with pytest.raises(yaml.constructor.ConstructorError) as exc_info:
        strict_load(doc)
    assert "duplicate key 'id'" in str(exc_info.value)


def test_strict_load_accepts_valid_yaml():
    from vcfops_dashboards.yaml_utils import strict_load

    doc = textwrap.dedent("""\
        id: 1234
        name: foo
        value: bar
    """)
    result = strict_load(doc)
    assert result == {"id": 1234, "name": "foo", "value": "bar"}


# ---------------------------------------------------------------------------
# vcfops_dashboards  — view loader
# ---------------------------------------------------------------------------


def _valid_view_yaml(view_id: str) -> str:
    return textwrap.dedent(f"""\
        id: {view_id}
        name: "[VCF Content Factory] Test View"
        description: "test"
        subject:
          adapter_kind: VMWARE
          resource_kind: VirtualMachine
        columns:
          - attribute: "cpu|usage_average"
            display_name: "CPU Usage"
    """)


def test_view_loader_rejects_duplicate_id(tmp_path: Path):
    from vcfops_dashboards.loader import DashboardValidationError, load_view

    view_id = str(uuid.uuid4())
    yaml_content = textwrap.dedent(f"""\
        id: {view_id}
        id: ""
        name: "[VCF Content Factory] Bad View"
        description: "test"
        adapter_kind: VMWARE
        resource_kind: VirtualMachine
        columns:
          - attribute: "cpu|usage_average"
            display_name: "CPU Usage"
    """)
    p = tmp_path / "bad_view.yaml"
    p.write_text(yaml_content)

    with pytest.raises(DashboardValidationError) as exc_info:
        load_view(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'id'" in error_msg
    assert "bad_view.yaml" in error_msg


def test_view_loader_accepts_valid_file(tmp_path: Path):
    from vcfops_dashboards.loader import load_view

    view_id = str(uuid.uuid4())
    p = tmp_path / "good_view.yaml"
    p.write_text(_valid_view_yaml(view_id))
    v = load_view(p)
    assert v.id == view_id


# ---------------------------------------------------------------------------
# vcfops_dashboards  — dashboard loader
# ---------------------------------------------------------------------------


def test_dashboard_loader_rejects_duplicate_id(tmp_path: Path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    dash_id = str(uuid.uuid4())
    yaml_content = textwrap.dedent(f"""\
        id: {dash_id}
        id: ""
        name: "[VCF Content Factory] Bad Dashboard"
        widgets: []
    """)
    p = tmp_path / "bad_dashboard.yaml"
    p.write_text(yaml_content)

    with pytest.raises(DashboardValidationError) as exc_info:
        load_dashboard(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'id'" in error_msg
    assert "bad_dashboard.yaml" in error_msg


# ---------------------------------------------------------------------------
# vcfops_supermetrics
# ---------------------------------------------------------------------------


def test_supermetric_loader_rejects_duplicate_id(tmp_path: Path):
    from vcfops_supermetrics.loader import SuperMetricValidationError, load_file

    sm_id = str(uuid.uuid4())
    yaml_content = textwrap.dedent(f"""\
        id: {sm_id}
        id: ""
        name: "[VCF Content Factory] Bad SM"
        formula: "avg(${{this, metric=cpu|usage_average}})"
        resource_kinds:
          - resourceKindKey: VirtualMachine
            adapterKindKey: VMWARE
    """)
    p = tmp_path / "bad_sm.yaml"
    p.write_text(yaml_content)

    with pytest.raises(SuperMetricValidationError) as exc_info:
        load_file(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'id'" in error_msg
    assert "bad_sm.yaml" in error_msg


# ---------------------------------------------------------------------------
# vcfops_customgroups
# ---------------------------------------------------------------------------


def test_customgroup_loader_rejects_duplicate_key(tmp_path: Path):
    from vcfops_customgroups.loader import CustomGroupValidationError, load_file

    yaml_content = textwrap.dedent("""\
        name: "[VCF Content Factory] Bad Group"
        name: "[VCF Content Factory] Duplicate Name"
        rules:
          - resource_kind: VirtualMachine
            adapter_kind: VMWARE
    """)
    p = tmp_path / "bad_group.yaml"
    p.write_text(yaml_content)

    with pytest.raises(CustomGroupValidationError) as exc_info:
        load_file(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'name'" in error_msg
    assert "bad_group.yaml" in error_msg


# ---------------------------------------------------------------------------
# vcfops_symptoms
# ---------------------------------------------------------------------------


def test_symptom_loader_rejects_duplicate_key(tmp_path: Path):
    from vcfops_symptoms.loader import SymptomValidationError, load_file

    yaml_content = textwrap.dedent("""\
        name: "[VCF Content Factory] Bad Symptom"
        name: "[VCF Content Factory] Duplicate Symptom"
        adapter_kind: VMWARE
        resource_kind: VirtualMachine
        severity: CRITICAL
        conditions:
          - type: metric_static
            key: cpu|usage_average
            operator: GT
            value: 90
    """)
    p = tmp_path / "bad_symptom.yaml"
    p.write_text(yaml_content)

    with pytest.raises(SymptomValidationError) as exc_info:
        load_file(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'name'" in error_msg
    assert "bad_symptom.yaml" in error_msg


# ---------------------------------------------------------------------------
# vcfops_alerts
# ---------------------------------------------------------------------------


def test_alert_loader_rejects_duplicate_key(tmp_path: Path):
    from vcfops_alerts.loader import AlertValidationError, load_file

    yaml_content = textwrap.dedent("""\
        name: "[VCF Content Factory] Bad Alert"
        name: "[VCF Content Factory] Duplicate Alert"
        description: "test"
        adapter_kind: VMWARE
        resource_kind: VirtualMachine
        criticality: IMMEDIATE
        type: 16
        sub_type: 3
        symptom_sets: []
    """)
    p = tmp_path / "bad_alert.yaml"
    p.write_text(yaml_content)

    with pytest.raises(AlertValidationError) as exc_info:
        load_file(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'name'" in error_msg
    assert "bad_alert.yaml" in error_msg


def test_recommendation_loader_rejects_duplicate_key(tmp_path: Path):
    from vcfops_alerts.loader import AlertValidationError, load_recommendation_file

    yaml_content = textwrap.dedent("""\
        name: "[VCF Content Factory] Bad Rec"
        name: "[VCF Content Factory] Duplicate Rec"
        description: "test"
        type: OperatorAction
        impact: NONE
        action: "Do something."
    """)
    p = tmp_path / "bad_rec.yaml"
    p.write_text(yaml_content)

    with pytest.raises(AlertValidationError) as exc_info:
        load_recommendation_file(p)
    error_msg = str(exc_info.value)
    assert "duplicate key 'name'" in error_msg
    assert "bad_rec.yaml" in error_msg


# ---------------------------------------------------------------------------
# vcfops_reports
# ---------------------------------------------------------------------------


def test_report_loader_rejects_duplicate_id(tmp_path: Path):
    from vcfops_reports.loader import ReportValidationError, load_file

    report_id = str(uuid.uuid4())
    yaml_content = textwrap.dedent(f"""\
        id: {report_id}
        id: ""
        name: "[VCF Content Factory] Bad Report"
        description: "test"
        subject_types:
          - adapter_kind: VMWARE
            resource_kind: VirtualMachine
            type: self
        sections:
          - type: CoverPage
    """)
    p = tmp_path / "bad_report.yaml"
    p.write_text(yaml_content)

    with pytest.raises(ReportValidationError) as exc_info:
        load_file(str(p), views_dir=str(tmp_path / "views"),
                  dashboards_dir=str(tmp_path / "dashboards"))
    error_msg = str(exc_info.value)
    assert "duplicate key 'id'" in error_msg
    assert "bad_report.yaml" in error_msg
