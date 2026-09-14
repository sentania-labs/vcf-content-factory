"""The non-overwrite invariant applies to the extracted dashboard itself
(Codex P2 on PR #164): ``extract_dashboard`` populated ``existing_dash_ids``
but never consulted it, so a dashboard already authored under
``content/dashboards`` was written again. Now it is skipped with the same
WARN shape the views and super metrics use, the plan prints a SKIP line,
the rest of the extraction (views, SMs, manifest) proceeds, and the exit
code stays 0, exactly as a skipped view or SM leaves it.

The live path is stubbed at its seams: the suite-api client, the dashboard
export, the SM export, the Default Policy fetch, and the repo root.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DASH_ID = "5f3f1c2a-7b1e-4c1d-9a2b-3c4d5e6f7a8b"


class _StubClient:
    def authenticate(self):
        return None

    def export_default_policy_xml(self):
        raise RuntimeError("no policy in this test")

    def get_supermetric(self, uuid):
        raise RuntimeError("no SM in this test")

    def list_supermetrics(self, page_size=2000):
        return []


def _dash_json() -> dict:
    return {
        "id": DASH_ID, "name": "Codex P2 Dash", "shared": True,
        "widgets": [{
            "id": "w1", "type": "TextDisplay", "title": "t",
            "gridsterCoords": {"x": 0, "y": 0, "w": 2, "h": 2}, "config": {"html": "<b>x</b>"},
        }],
        "widgetInteractions": [], "entries": {},
    }


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    import vcfcf_extractor.extractor as ex

    root = tmp_path / "repo"
    (root / "content" / "dashboards").mkdir(parents=True)
    (root / "content" / "views").mkdir()
    (root / "content" / "supermetrics").mkdir()
    monkeypatch.setattr(ex, "_REPO_ROOT", root)
    monkeypatch.setattr(ex, "_build_sm_client", lambda *a, **k: _StubClient())
    monkeypatch.setattr(ex, "_export_dashboard_json", lambda client, uuid: _dash_json() if uuid == DASH_ID else None)
    monkeypatch.setattr(ex, "_export_supermetrics_full", lambda client: {})
    monkeypatch.setattr(ex, "_export_views_zip", lambda client, uuids: (_ for _ in ()).throw(AssertionError("no views expected")))
    desc = tmp_path / "DESCRIPTION.md"
    desc.write_text("desc\n", encoding="utf-8")
    out = tmp_path / "out"

    def run(**overrides):
        kwargs = dict(
            host="h", user="u", password="p", verify_ssl=False,
            dashboard_id=DASH_ID, dashboard_name=None, bundle_slug="codex-p2",
            author="a", license_="MIT", description_file=desc, source_url="", source_version="",
            output_dir=str(out), skip_supermetrics=set(), include_customgroups=[],
            prefix="", dry_run=False, yes=True,
        )
        kwargs.update(overrides)
        return ex.extract_dashboard(**kwargs)

    return root, out, run


def test_already_authored_dashboard_is_skipped_with_a_warn(stubbed, capsys):
    root, out, run = stubbed
    planted = root / "content" / "dashboards" / "already.yaml"
    planted.write_text(f"id: {DASH_ID}\nname: \"[VCF Content Factory] Already\"\nwidgets: []\n", encoding="utf-8")

    rc = run()
    captured = capsys.readouterr()
    assert rc == 0
    assert f"WARN: dashboard {DASH_ID} already exists at {planted}; skipping" in captured.err
    assert f"  - SKIP {DASH_ID}: {planted}" in captured.out
    assert "Codex P2 Dash.yaml" not in captured.out
    assert not (out / "codex-p2" / "dashboards").exists()
    assert not list((out / "codex-p2").rglob("dashboards/*.yaml"))
    # The rest of the extraction still lands: the manifest is written.
    assert (out / "codex-p2" / "PROJECT.yaml").is_file()
    assert planted.read_text(encoding="utf-8").startswith(f"id: {DASH_ID}\n")


def test_unauthored_dashboard_is_still_written(stubbed, capsys):
    root, out, run = stubbed
    rc = run()
    captured = capsys.readouterr()
    assert rc == 0
    assert "already exists" not in captured.err
    assert f"  + Codex P2 Dash  ({DASH_ID})" in captured.out
    written = list((out / "codex-p2" / "dashboards").glob("*.yaml"))
    assert [p.name for p in written] == ["Codex P2 Dash.yaml"]
    assert written[0].read_text(encoding="utf-8").startswith(f"id: {DASH_ID}\n")


def test_confirmation_count_excludes_a_skipped_dashboard(stubbed, capsys):
    root, out, run = stubbed
    (root / "content" / "dashboards" / "already.yaml").write_text(f"id: {DASH_ID}\nname: x\nwidgets: []\n", encoding="utf-8")
    assert run(yes=False) == 0
    out_text = capsys.readouterr().out
    assert "Would write 0 YAML file(s)" in out_text
    assert not (out / "codex-p2" / "PROJECT.yaml").exists()
