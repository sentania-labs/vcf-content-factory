"""sdk_builder._load_bundled_content cross-validates bundled dashboards
against bundled_content.views (2026-08-29 view-reference guard).

Before this, an SDK pak could list a dashboard whose View widget named a
view that was not bundled; the render fallback then wrote the view NAME
into viewDefinitionId and the installed widget reported "view does not
exist". See knowledge/lessons/dashboard-import-without-views-corrupts-refs.md.

Hermetic tmp_path fixture, no adapter repo, no Java tooling.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_VIEW_ID = "ef3e6901-4c10-4208-9b95-4c82bf54f810"
_VIEW_NAME = "Windows Services vCommunity"
_EXTERNAL_UUID = "ae751947-1782-466f-b560-9a950be3c1f9"


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _make_project(tmp_path: Path, view_ref: str) -> Path:
    project_dir = tmp_path / "adapter_project"
    _write_yaml(project_dir / "views" / "services.yaml", {
        "id": _VIEW_ID,
        "name": _VIEW_NAME,
        "description": "",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [{"attribute": "summary|guest|hostName", "display_name": "Hostname"}],
    })
    _write_yaml(project_dir / "dashboards" / "vm-details.yaml", {
        "id": "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b",
        "name": "VM Details",
        "description": "",
        "widgets": [
            {"id": "svc", "type": "View", "title": "Services",
             "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
             "view": view_ref},
        ],
        "interactions": [],
    })
    return project_dir


def _load(project_dir: Path, views: list[str]):
    from vcfops_managementpacks.sdk_builder import _load_bundled_content
    raw = {"bundled_content": {
        "views": views,
        "dashboards": ["dashboards/vm-details.yaml"],
    }}
    return _load_bundled_content(raw, project_dir, project_dir)


def test_dashboard_view_not_bundled_raises_naming_the_view(tmp_path):
    from vcfops_managementpacks.sdk_builder import SdkBuildError

    project_dir = _make_project(tmp_path, _VIEW_NAME)
    with pytest.raises(SdkBuildError) as ei:
        _load(project_dir, views=[])  # view file exists but is not listed
    msg = str(ei.value)
    assert "bundled_content.dashboards" in msg
    assert "VM Details" in msg
    assert _VIEW_NAME in msg
    assert "bundled_content.views" in msg


def test_dashboard_view_bundled_loads(tmp_path):
    project_dir = _make_project(tmp_path, _VIEW_NAME)
    views, dashboards, *_ = _load(project_dir, views=["views/services.yaml"])
    assert [v.name for v in views] == [_VIEW_NAME]
    assert [d.name for d in dashboards] == ["VM Details"]
    assert dashboards[0].widgets[0].view_name == _VIEW_NAME


def test_dashboard_external_uuid_view_still_loads_without_bundling(tmp_path):
    """A canonical UUID reference is an external view: no bundling required."""
    project_dir = _make_project(tmp_path, _EXTERNAL_UUID)
    views, dashboards, *_ = _load(project_dir, views=[])
    assert views == []
    assert dashboards[0].widgets[0].view_name == _EXTERNAL_UUID
