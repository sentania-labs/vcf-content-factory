"""Rendered Scoreboard / MetricChart ``extModel<n>-<seq>`` ids are stable
across interpreter runs (issue #147).

``render.py`` used ``abs(hash(widget_id)) % 100000``. ``hash()`` on a str is
salted per process (PYTHONHASHSEED), so every ``package`` run produced a
different set of ids and byte-comparison render regression on the
content-import path was impossible without ``PYTHONHASHSEED=0``. The ids are
now derived from a sha1 digest of the widget id (``_ext_model_id``).

Two guards here:

1. The derivation is pinned to an exact value for a known widget id, so a
   later "tidy" back to ``hash()`` (or a change of digest / truncation that
   would silently re-key every shipped dashboard) fails loudly.
2. The same dashboard rendered in two subprocesses with *different*
   ``PYTHONHASHSEED`` values yields byte-identical JSON. This is the property
   the issue is about, tested the way it breaks.

All fixtures are tmp_path-local.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
OWNER = "00000000-0000-0000-0000-000000000001"
ID_RE = re.compile(r"^extModel(\d{1,5})-(\d+)$")


def _scoreboard(widget_id: str = "cluster_headline") -> dict:
    return {
        "name": "[VCF Content Factory] extModel Stability Probe",
        "widgets": [{
            "id": widget_id,
            "type": "Scoreboard",
            "title": "Headline",
            "coords": {"x": 1, "y": 1, "w": 6, "h": 5},
            "self_provider": True,
            "metric_mode": "resource",
            "resource": {
                "adapter_kind": "VMWARE_INFRA_HEALTH",
                "resource_kind": "LICENSE_USAGE_WORLD",
                "name": "License Usage",
            },
            "metrics": [
                {"metric_key": "cpu|usage_average", "metric_name": "CPU Usage",
                 "label": "CPU", "color_method": 1},
                {"metric_key": "mem|usage_average", "metric_name": "Memory Usage",
                 "label": "Memory", "color_method": 1},
            ],
        }],
    }


def _write_dash(tmp_path: Path, widget_id: str = "cluster_headline") -> Path:
    d = tmp_path / "dashboards"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "probe.yaml"
    p.write_text(yaml.dump(_scoreboard(widget_id), default_flow_style=False))
    return p


def _render_in_subprocess(dash_path: Path, hashseed: str) -> str:
    """Render the dashboard bundle JSON in a fresh interpreter with a fixed,
    non-zero hash seed. ``hash()``-derived ids differ between seeds; sha1-
    derived ids do not."""
    code = textwrap.dedent(f"""\
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(SRC)!r})
        from vcfcf_dashboards.loader import load_dashboard
        from vcfcf_dashboards.render import render_dashboards_bundle_json
        d = load_dashboard(Path({str(dash_path)!r}))
        sys.stdout.write(render_dashboards_bundle_json([d], {{}}, {OWNER!r}))
        """)
    env = dict(os.environ, PYTHONHASHSEED=hashseed)
    env["PYTHONPATH"] = str(SRC)
    r = subprocess.run([sys.executable, "-c", code], env=env, check=True,
                       capture_output=True, text=True, cwd=str(REPO_ROOT))
    return r.stdout


def _entry_ids(bundle_json: str) -> list[str]:
    out = json.loads(bundle_json)
    metric = out["dashboards"][0]["widgets"][0]["config"]["metric"]
    return [e["id"] for e in metric["resourceMetrics"]]


class TestExtModelIdDerivation:
    def test_pinned_value_for_known_widget_id(self):
        from vcfcf_dashboards.render import _ext_model_id

        widget_id = "cluster_headline"
        expected_n = int(hashlib.sha1(widget_id.encode("utf-8")).hexdigest()[:8], 16) % 100000
        assert _ext_model_id(widget_id, 1) == f"extModel{expected_n}-1"
        assert _ext_model_id(widget_id, 7) == f"extModel{expected_n}-7"
        # Literal pin, independent of the formula above, so a change to
        # the digest or the truncation is caught even if both sides move.
        assert _ext_model_id(widget_id, 1) == "extModel9005-1"

    def test_shape_matches_previous_wire_form(self):
        from vcfcf_dashboards.render import _ext_model_id

        for wid in ("a", "cluster_headline", "x" * 200, "with spaces and/slashes"):
            m = ID_RE.match(_ext_model_id(wid, 3))
            assert m, _ext_model_id(wid, 3)
            assert 0 <= int(m.group(1)) < 100000

    def test_distinct_widgets_get_distinct_numbers(self):
        from vcfcf_dashboards.render import _ext_model_id

        a = _ext_model_id("widget_a", 1)
        b = _ext_model_id("widget_b", 1)
        assert a != b


class TestRenderIsStableAcrossInterpreters:
    @pytest.mark.parametrize("seeds", [("1", "2"), ("12345", "424242")])
    def test_same_bundle_json_under_different_hash_seeds(self, tmp_path, seeds):
        dash = _write_dash(tmp_path)
        a = _render_in_subprocess(dash, seeds[0])
        b = _render_in_subprocess(dash, seeds[1])
        assert a == b, "rendered bundle JSON differs between interpreter runs"
        ids = _entry_ids(a)
        assert ids == _entry_ids(b)
        # The renderer keys on the loader's widget_id, which is itself the
        # deterministic uuid5 stable_id("widget", "<dashboard name>::<local
        # id>") (e0deb90e-7f24-58f8-a3de-ce2f8ee5b9e6 for this probe), not
        # the bare YAML id. Literal pin so a re-key of shipped dashboards
        # (digest, truncation, or the widget_id seed) is caught here.
        assert ids == ["extModel35101-1", "extModel35101-2"], ids

    def test_hash_builtin_would_have_differed(self, tmp_path):
        """Sanity check on the harness: the seeds really do change ``hash()``.
        Without this, a passing stability test could just mean the two
        subprocesses shared a seed."""
        code = "import sys; sys.stdout.write(str(abs(hash('cluster_headline')) % 100000))"
        outs = set()
        for seed in ("1", "2", "3"):
            r = subprocess.run([sys.executable, "-c", code],
                               env=dict(os.environ, PYTHONHASHSEED=seed),
                               check=True, capture_output=True, text=True)
            outs.add(r.stdout)
        assert len(outs) > 1, outs
