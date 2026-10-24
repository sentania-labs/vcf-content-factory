"""Bundle sync hands the reports handler the ReportDefs load_bundle built (#232 W4).

Before #232 the reports handler was unreachable from bundle sync. Now it is
reached, and reloading each report file with factory defaults (prefix
enforcement on) rejected a third-party bundle's report that its own build
accepts. The syncer now passes the already-loaded objects.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_packaging.syncer import sync_bundle  # noqa: E402
from vcfcf_reports import handler as rep_handler  # noqa: E402

REPORT_NAME = "Partner Capacity Report"  # third-party: no factory prefix


def _third_party_bundle(tmp_path: Path) -> Path:
    proj = tmp_path / "third_party" / "partner"
    (proj / "reports").mkdir(parents=True)
    (proj / "reports" / "r.yaml").write_text(yaml.safe_dump({
        "id": "dddddddd-4444-4444-8444-444444444444",
        "name": REPORT_NAME,
        "description": "d",
        "subject_types": [{"adapter_kind": "VMWARE",
                           "resource_kind": "HostSystem", "type": "self"}],
        "sections": [{"type": "CoverPage"}],
    }), encoding="utf-8")
    manifest = proj / "bundle.yaml"
    manifest.write_text(yaml.safe_dump({
        "name": "partner",
        "description": "third-party bundle with a report",
        "factory_native": False,
        "author": "Partner",
        "license": "MIT",
        "reports": ["reports/r.yaml"],
    }), encoding="utf-8")
    return manifest


def _stub_network(monkeypatch, imported):
    monkeypatch.setattr(rep_handler, "get_current_user", lambda s: {"id": "u"})
    monkeypatch.setattr(rep_handler, "discover_marker_filename", lambda s: "1L.v1")
    monkeypatch.setattr(rep_handler, "build_import_zip",
                        lambda reports, **k: imported.extend(r.name for r in reports) or b"zip")
    monkeypatch.setattr(rep_handler, "import_reports_zip", lambda s, b: {"state": "FINISHED"})


def test_third_party_report_syncs_with_bundle_context(tmp_path, monkeypatch, capsys):
    manifest = _third_party_bundle(tmp_path)
    monkeypatch.chdir(tmp_path)  # not the repo root: no content/views here
    imported: list = []
    _stub_network(monkeypatch, imported)
    rc = sync_bundle(manifest, handlers=[rep_handler.ReportsHandler()], session=object())
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert imported == [REPORT_NAME]
    assert f"OK    {REPORT_NAME}" in out.out


def test_reloading_with_factory_defaults_would_have_rejected_it(tmp_path, monkeypatch):
    """The failure the hook avoids: the plain path-based sync applies the
    factory prefix rule and fails this report."""
    manifest = _third_party_bundle(tmp_path)
    monkeypatch.chdir(tmp_path)
    imported: list = []
    _stub_network(monkeypatch, imported)
    path = str(manifest.parent / "reports" / "r.yaml")
    res = rep_handler.ReportsHandler().sync([path], object())
    assert [i.status for i in res.items] == ["failed"]
    assert imported == []
