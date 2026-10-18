"""Dashboard names over the editor's 50-character limit warn at validate.

Issue #198: the VCF Operations dashboard editor refuses to save a dashboard
whose name exceeds 50 characters, while the content-import API accepts it.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards.loader import (  # noqa: E402
    DASHBOARD_NAME_MAX_LEN,
    dashboard_name_length_problem,
    load_all,
)

PREFIX = "[VCF Content Factory] "


def _name(total_len: int) -> str:
    return PREFIX + "x" * (total_len - len(PREFIX))


def _write_dash(tmp_path: Path, name: str) -> Path:
    dash_dir = tmp_path / "dashboards"
    dash_dir.mkdir()
    (dash_dir / "d.yaml").write_text(yaml.safe_dump({
        "id": "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b",
        "name": name,
        "description": "",
        "widgets": [{"id": "t", "type": "TextDisplay", "title": "T",
                     "coords": {"x": 1, "y": 1, "w": 4, "h": 2},
                     "text_display_config": {"text": "hi"}}],
    }, sort_keys=False))
    return dash_dir


def _name_warnings(caught) -> list:
    return [w for w in caught if "issue #198" in str(w.message)]


def test_limit_is_fifty():
    assert DASHBOARD_NAME_MAX_LEN == 50


@pytest.mark.parametrize("n", [1, 49, 50])
def test_at_or_under_limit_is_fine(n):
    assert dashboard_name_length_problem("x" * n) is None


def test_over_limit_names_length_and_limit():
    msg = dashboard_name_length_problem(_name(51))
    assert msg is not None and "51 characters" in msg and "50" in msg


def test_validate_warns_but_does_not_fail(tmp_path):
    dash_dir = _write_dash(tmp_path, _name(53))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _, dashboards = load_all(tmp_path / "views", dash_dir)
    assert len(dashboards) == 1
    hits = _name_warnings(caught)
    assert len(hits) == 1
    assert issubclass(hits[0].category, UserWarning)
    assert "d.yaml" in str(hits[0].message)


def test_cli_validate_reports_warning_and_exits_zero(tmp_path):
    """The vcfcf_dashboards CLI validate path surfaces the warning, rc 0."""
    import os
    import subprocess

    dash_dir = _write_dash(tmp_path, _name(53))
    (tmp_path / "views").mkdir()
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    r = subprocess.run(
        [sys.executable, "-m", "vcfcf_dashboards",
         "--views-dir", str(tmp_path / "views"),
         "--dashboards-dir", str(dash_dir), "validate"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "53 characters" in r.stderr and "issue #198" in r.stderr


def test_validate_quiet_at_limit(tmp_path):
    dash_dir = _write_dash(tmp_path, _name(50))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all(tmp_path / "views", dash_dir)
    assert _name_warnings(caught) == []
