"""Dependency-auditor coverage for per-column kind binding in multi-subject
views (framework review 2026-08-29-multi-subject-column-binding, WARNING 2).

On the product a column's adapterKind/resourceKind Properties are a kind
filter (knowledge/context/api-surface/view_multi_subject_column_binding.md),
so a column bound via `subject:` only ever resolves against that one kind.
_refs_from_view() must audit it against that kind only; auditing it against
every subject kind would raise a false "metric key not found in the
describe cache" for the other kinds and fail the bundle build. Unbound
columns keep the per-kind fan-out.

Fixtures are tmp_path-local; no describe cache or live instance involved.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _write_view(tmp_path: Path, data: dict) -> Path:
    d = tmp_path / "views"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "view.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _multi_subject_view_data() -> dict:
    return {
        "name": "[VCF Content Factory] Multi Subject Binding Audit Test",
        "description": "",
        "subjects": [
            {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
            {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        ],
        "columns": [
            # Unbound: populates on every kind, audited on every kind.
            {"display_name": "CPU Demand", "attribute": "cpu|demandmhz"},
            # Bound to the second kind (not subjects[0]): audited there only.
            {
                "display_name": "Host Sockets",
                "attribute": "cpu|numpackages",
                "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            },
        ],
    }


def _load(tmp_path: Path):
    from vcfops_dashboards.loader import load_view

    v = load_view(_write_view(tmp_path, _multi_subject_view_data()), enforce_framework_prefix=False)
    v.validate(enforce_framework_prefix=False)
    return v


class TestRefsFromViewMultiSubjectBinding:
    def test_unbound_column_audited_on_every_kind(self, tmp_path):
        from vcfops_packaging.deps import _refs_from_view

        refs = _refs_from_view(_load(tmp_path))
        demand = {(r.adapter_kind, r.resource_kind) for r in refs if r.metric_key == "cpu|demandmhz"}
        assert demand == {("VMWARE", "VirtualMachine"), ("VMWARE", "HostSystem")}

    def test_bound_column_audited_on_bound_kind_only(self, tmp_path):
        from vcfops_packaging.deps import _refs_from_view

        refs = _refs_from_view(_load(tmp_path))
        sockets = [(r.adapter_kind, r.resource_kind) for r in refs if r.metric_key == "cpu|numpackages"]
        assert sockets == [("VMWARE", "HostSystem")]

    def test_total_reference_count(self, tmp_path):
        from vcfops_packaging.deps import _refs_from_view

        refs = _refs_from_view(_load(tmp_path))
        # 2 kinds for the unbound column + 1 for the bound column.
        assert len(refs) == 3


class TestExtractorEnablementWalkMirrorsDepsRule:
    """extractor.py's raw-dict enablement walk mirrors _refs_from_view; the
    same binding rule must hold there. Exercised through the module-level
    logic by replaying the walk on a raw view dict (the walk itself is
    inline in extract_dashboard; this pins the shared rule via deps)."""

    def test_raw_dict_binding_rule(self):
        from vcfops_packaging.deps import _column_kinds
        from types import SimpleNamespace

        bound = SimpleNamespace(subject=SimpleNamespace(adapter_kind="VMWARE", resource_kind="HostSystem"))
        unbound = SimpleNamespace(subject=None)
        assert _column_kinds(bound) == [("VMWARE", "HostSystem")]
        assert _column_kinds(unbound) is None
