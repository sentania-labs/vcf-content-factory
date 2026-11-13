"""A pak's rendered content keeps its file paths across the prefix rename.

The server-side pak installer binds Summary dashboards by the directory key
in ``content/dashboards/dashboards.properties``
(knowledge/context/api-surface/summary_dashboard_pak_binding.md), and every
other in-pak path is derived from a display name. ``sdk_builder`` slugs the
id-basis (legacy-spelled) name, so a pak rendered before its content is
migrated and after it has the same file list and the same binding key; only
display strings and localization values change
(knowledge/context/authoring/prefix_migration.md).

Hermetic: a synthetic pak under tmp_path, no Java, no SDK jar, a stub
adapters.zip.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import yaml

from vcfcf_core.naming import FACTORY_PREFIX as NEW, LEGACY_FACTORY_PREFIX as OLD

_KIND = "test_adapter"


def _w(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _make_pak(root: Path, p: str) -> dict:
    """A pak with an SM, a view, two dashboards (one Summary-bound), a
    symptom, an alert, a recommendation and a report, all named with *p*."""
    _w(root / "supermetrics/sm.yaml", {
        "id": "aaaabbbb-cccc-4ddd-8eee-ffffffffffff",
        "name": p + "Pak SM",
        "formula": "avg(${adaptertype=VMWARE, objecttype=VirtualMachine, metric=cpu|usage_average})",
        "description": "CPU average",
        "resource_kinds": [{"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}],
        "unit_id": "percent",
    })
    _w(root / "views/v.yaml", {
        "id": "ef3e6901-4c10-4208-9b95-4c82bf54f810",
        "name": p + "Pak VM List",
        "description": "VM list.",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [{"attribute": "summary|guest|hostName", "display_name": "Hostname"}],
    })
    widgets = [
        {"id": "kpi", "type": "Scoreboard", "title": "CPU",
         "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
         "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                      "metric_key": "cpu|usage_average", "metric_name": "CPU"}]},
    ]
    _w(root / "dashboards/summary.yaml", {
        "id": "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b", "name": p + "Pak World Summary",
        "description": "", "summary_for": "VMWARE:HostSystem", "widgets": widgets,
        "interactions": [],
    })
    _w(root / "dashboards/plain.yaml", {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", "name": p + "Pak Overview",
        "description": "", "widgets": widgets, "interactions": [],
    })
    _w(root / "symptoms/s.yaml", {
        "name": p + "Pak Host Down", "adapter_kind": _KIND, "resource_kind": "TestWorld",
        "severity": "CRITICAL", "wait_cycles": 1, "cancel_cycles": 1,
        "condition": {"type": "property", "key": "Status|state", "operator": "EQ", "value": "down"},
        "description": "Host is down.",
    })
    _w(root / "recommendations/r.yaml", {
        "name": p + "Pak Investigate Host", "description": "Check the host.",
        "adapter_kind": _KIND,
    })
    _w(root / "alerts/a.yaml", {
        "name": p + "Pak Host Down", "description": "Host down.",
        "adapter_kind": _KIND, "resource_kind": "TestWorld", "type": 19, "sub_type": 18,
        "wait_cycles": 1, "cancel_cycles": 1, "criticality": "CRITICAL",
        "impact": {"badge": "HEALTH"},
        "symptom_sets": {"operator": "ALL", "sets": [
            {"defined_on": "SELF", "operator": "ALL", "symptoms": [{"name": p + "Pak Host Down"}]}]},
        "recommendations": [{"name": p + "Pak Investigate Host", "priority": 1}],
    })
    _w(root / "reports/rep.yaml", {
        "id": "ecc10685-6eea-4f01-9c33-70b1e00c1c3a", "name": p + "Pak VM Report",
        "description": "VM report.",
        "subject_types": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine", "type": "self"}],
        "sections": [{"type": "View", "view": p + "Pak VM List", "orientation": "Portrait",
                      "colorize": False}],
        "settings": {"show_page_footer": False, "output_formats": ["csv"]},
    })
    return {"bundled_content": {
        "supermetrics": ["supermetrics/sm.yaml"],
        "views": ["views/v.yaml"],
        "dashboards": ["dashboards/summary.yaml", "dashboards/plain.yaml"],
        "symptoms": ["symptoms/s.yaml"],
        "alerts": ["alerts/a.yaml"],
        "recommendations": ["recommendations/r.yaml"],
        "reports": ["reports/rep.yaml"],
    }}


def _render(tmp_path: Path, p: str, tag: str) -> dict:
    from vcfcf_managementpacks.sdk_builder import (
        _build_views_zip_bytes, _load_bundled_content, _write_outer_pak,
    )
    from vcfcf_managementpacks.sdk_project import SdkProjectDef, _derive_entry_class

    root = tmp_path / tag
    raw = _make_pak(root, p)
    v, d, sm, sy, al, rp, rc = _load_bundled_content(raw, root, root)
    project = SdkProjectDef(
        name="VCF Content Factory Test", version="1.0.0", build_number=1,
        adapter_kind=_KIND, description="Test", tier=2, dependencies=[],
        entry_class=_derive_entry_class(_KIND), source_path=root / "adapter.yaml",
    )
    scope = [s.source_path for s in sm if s.source_path is not None]
    vz = _build_views_zip_bytes(v, sm_scope=scope)
    stub = io.BytesIO()
    with zipfile.ZipFile(stub, "w") as z:
        z.writestr("stub.txt", "stub")
    out = root / "dist"
    out.mkdir()
    pak = _write_outer_pak(
        project, stub.getvalue(), out, root, views=v, dashboards=d, views_zip_bytes=vz,
        owning_adapter_kind=_KIND, owning_resource_kind="TestWorld", supermetrics=sm,
        symptoms=sy, alerts=al, reports=rp, recommendations=rc,
    )
    with zipfile.ZipFile(pak) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def _to_new(b: bytes) -> bytes:
    """The legacy display strings mapped to the new spelling (incl. the
    properties-escaped form)."""
    return (b.replace(OLD.encode(), NEW.encode())
             .replace(b"[VCF\\ Content\\ Factory]", b"[VCF\\ CF]"))


def test_pak_paths_and_binding_key_survive_the_rename(tmp_path):
    legacy = _render(tmp_path, OLD, "legacy")
    migrated = _render(tmp_path, NEW, "migrated")

    # Identical file list: no in-pak path moves.
    assert sorted(legacy) == sorted(migrated)

    # The paths are the ones the pre-rename builder wrote (legacy-slugged).
    names = set(migrated)
    for expected in (
        "content/dashboards/VCF_Content_Factory_Pak_World_Summary/dashboard.json",
        "content/dashboards/VCF_Content_Factory_Pak_Overview/dashboard.json",
        "content/reports/VCF_Content_Factory_Pak_VM_List/content.xml",
        "content/reports/VCF_Content_Factory_Pak_VM_Report/content.xml",
        "content/supermetrics/VCF Content Factory Pak SM.json",
        "content/symptomdefs/VCF Content Factory Pak Host Down.xml",
        "content/alertdefs/VCF Content Factory Pak Host Down.xml",
    ):
        assert expected in names, expected

    # The Summary binding key is byte-identical.
    props = "content/dashboards/dashboards.properties"
    assert legacy[props] == migrated[props]
    assert b"VCF_Content_Factory_Pak_World_Summary=VMWARE:HostSystem" in migrated[props]

    # Every body differs by display strings only.
    for n in sorted(names):
        if n.endswith(".zip"):
            continue
        assert _to_new(legacy[n]) == migrated[n], n
    # and the display names did change.
    assert any(legacy[n] != migrated[n] for n in names)
