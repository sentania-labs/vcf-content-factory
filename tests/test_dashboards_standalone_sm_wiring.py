"""The standalone dashboards paths still resolve ``supermetric:"<name>"``
view columns after M2 row 2.

The renderer no longer scans ``content/supermetrics`` itself; the
standalone CLI (``cmd_package``) and the bundle sync ``ViewsHandler`` pass
``sm_id_map()`` into ``build_import_zip``. A dropped ``sm_map=`` would
raise (unresolved reference), not render blank, but nothing else proves the
map reaches the zip. Both tests load a view with an SM column, point the
working directory at a ``content/supermetrics`` tree under ``tmp_path``,
and read ``Super Metric|sm_<uuid>`` back out of ``views.zip/content.xml``.

No network: the handler's import call is stubbed and the blob captured.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from vcfcf_dashboards import cli as dash_cli
from vcfcf_dashboards import handler as dash_handler

_SM_ID = str(uuid.uuid4())
_SM_NAME = "[VCF Content Factory] Standalone Wiring Probe SM"
_VIEW_ID = str(uuid.uuid4())


def _write_tree(root: Path) -> Path:
    """content/supermetrics + content/views under root; returns the view path."""
    sm_dir = root / "content" / "supermetrics"
    sm_dir.mkdir(parents=True)
    (sm_dir / "probe.yaml").write_text(
        f"id: {_SM_ID}\n"
        f"name: \"{_SM_NAME}\"\n"
        "formula: \"avg(${this, metric=cpu|usage_average})\"\n"
        "resource_kinds:\n  - {adapter_kind_key: VMWARE, resource_kind_key: HostSystem}\n",
        encoding="utf-8",
    )
    views_dir = root / "content" / "views"
    views_dir.mkdir(parents=True)
    view = views_dir / "probe.yaml"
    view.write_text(
        f"id: {_VIEW_ID}\n"
        "name: \"[VCF Content Factory] Standalone Wiring Probe View\"\n"
        "description: probe\n"
        "subject: {adapter_kind: VMWARE, resource_kind: HostSystem}\n"
        "columns:\n"
        "  - {display_name: Plain, attribute: cpu|usage_average}\n"
        f"  - {{display_name: SM, attribute: 'supermetric:\"{_SM_NAME}\"'}}\n",
        encoding="utf-8",
    )
    (root / "content" / "dashboards").mkdir()
    return view


def _views_xml(blob: bytes) -> str:
    outer = zipfile.ZipFile(io.BytesIO(blob))
    inner = zipfile.ZipFile(io.BytesIO(outer.read("views.zip")))
    return inner.read("content.xml").decode("utf-8")


def test_cmd_package_resolves_sm_column_from_cwd_tree(tmp_path, monkeypatch):
    _write_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.zip"
    args = SimpleNamespace(
        views_dir="content/views", dashboards_dir="content/dashboards", output=str(out)
    )
    assert dash_cli.cmd_package(args) == 0
    xml = _views_xml(out.read_bytes())
    assert f'name="attributeKey" value="Super Metric|sm_{_SM_ID}"' in xml
    assert "supermetric:" not in xml


def test_views_handler_sync_resolves_sm_column_from_cwd_tree(tmp_path, monkeypatch):
    view = _write_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    captured: dict = {}
    monkeypatch.setattr(
        dash_handler, "get_current_user", lambda s: {"id": "u1", "userName": "admin"}
    )
    monkeypatch.setattr(dash_handler, "discover_marker_filename", lambda s: "1L.v1")

    def _import(session, blob):
        captured["blob"] = blob
        return {
            "state": "FINISHED",
            "operationSummaries": [
                {"contentType": "VIEW_DEFINITIONS", "imported": 1, "skipped": 0,
                 "failed": 0, "state": "FINISHED"}
            ],
        }

    monkeypatch.setattr(dash_handler, "import_content_zip", _import)
    result = dash_handler.ViewsHandler().sync([str(view)], session=object())
    assert [i.status for i in result.items] == ["ok"], [i.message for i in result.items]
    xml = _views_xml(captured["blob"])
    assert f'name="attributeKey" value="Super Metric|sm_{_SM_ID}"' in xml


def test_cmd_package_without_sm_tree_reports_the_unresolved_reference(tmp_path, monkeypatch, capsys):
    """Sanity for the two tests above: with no supermetrics tree on the cwd
    the same view cannot resolve, so a green run really did use the map."""
    _write_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "content" / "supermetrics" / "probe.yaml").unlink()
    args = SimpleNamespace(
        views_dir="content/views", dashboards_dir="content/dashboards",
        output=str(tmp_path / "out.zip"),
    )
    with pytest.raises(ValueError, match="could not be resolved to a UUID"):
        dash_cli.cmd_package(args)
