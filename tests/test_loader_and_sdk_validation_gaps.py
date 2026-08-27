"""Two validation gaps.

Fix 2 — ``vcfops_dashboards.loader.load_view()`` coerced ``hide_object_name``
with ``bool(...)``, so a quoted ``hide_object_name: "false"`` became ``True``
and the renderer hid the object-name column against the authored intent.  It is
now type-checked the same way the loader's other boolean fields are.

Fix 3 — ``vcfops_managementpacks.sdk_builder._load_bundled_content()`` ran
``load_dashboard()`` and then only a duplicate-``summary_for`` check, so the
cross-object invariants in ``Dashboard.validate()`` never ran on the pak path.
A pak could ship a Summary dashboard whose widgets stay pinned instead of
inheriting the page object.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# --- Fix 2: hide_object_name -------------------------------------------------

def _view(tmp_path: Path, hide_object_name) -> Path:
    data = {
        "id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
        "name": "[VCF Content Factory] Probe View",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [{"attribute": "cpu|usage_average", "display_name": "CPU"}],
    }
    if hide_object_name is not None:
        data["hide_object_name"] = hide_object_name
    p = tmp_path / "view.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


class TestHideObjectNameTypeCheck:
    @pytest.mark.parametrize("value,expected", [(True, True), (False, False), (None, False)])
    def test_real_booleans_and_default(self, tmp_path, value, expected):
        from vcfops_dashboards.loader import load_view

        assert load_view(_view(tmp_path, value)).hide_object_name is expected

    @pytest.mark.parametrize("bad", ["false", "true", "no", 0, 1])
    def test_non_boolean_raises_instead_of_coercing(self, tmp_path, bad):
        """A quoted "false" used to coerce to True and silently hide the column."""
        from vcfops_dashboards.loader import DashboardValidationError, load_view

        with pytest.raises(DashboardValidationError) as exc:
            load_view(_view(tmp_path, bad))
        assert "hide_object_name" in str(exc.value)
        assert "bool" in str(exc.value)

    def test_quoted_false_no_longer_hides_the_column(self, tmp_path):
        """The end-to-end symptom: the renderer must never see hideObjectNameColumn
        flipped to true by a quoted "false"."""
        from vcfops_dashboards.loader import DashboardValidationError, load_view

        with pytest.raises(DashboardValidationError):
            load_view(_view(tmp_path, "false"))


# --- Fix 3: SDK bundled dashboards must be validated ------------------------

_SUMMARY_DASH_PINNED = textwrap.dedent("""\
    id: 0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b
    name: "Probe Host Summary"
    description: ""
    summary_for: "VMWARE:HostSystem"
    widgets:
      - id: kpi
        type: Scoreboard
        title: CPU
        coords: {x: 1, y: 1, w: 4, h: 4}
        self_provider: true
        metrics:
          - adapter_kind: VMWARE
            resource_kind: HostSystem
            metric_key: cpu|usage_average
            metric_name: CPU
    interactions: []
    """)

_SUMMARY_DASH_CLEAN = _SUMMARY_DASH_PINNED.replace("    self_provider: true\n", "")

_DASH_UNKNOWN_VIEW = textwrap.dedent("""\
    id: 1f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4c
    name: "Probe View Dash"
    description: ""
    widgets:
      - id: v1
        type: View
        title: Listing
        coords: {x: 1, y: 1, w: 4, h: 4}
        view: "Nonexistent View"
    interactions: []
    """)


def _bundled(tmp_path: Path, dashboard_yaml: str) -> tuple:
    project_dir = tmp_path / "adapter"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "dash.yaml").write_text(dashboard_yaml)
    raw = {"bundled_content": {"dashboards": ["dash.yaml"]}}
    return raw, project_dir


class TestSdkBundledDashboardValidation:
    def test_pinned_summary_dashboard_is_rejected(self, tmp_path):
        from vcfops_managementpacks.sdk_builder import (
            SdkBuildError,
            _load_bundled_content,
        )

        raw, project_dir = _bundled(tmp_path, _SUMMARY_DASH_PINNED)
        with pytest.raises(SdkBuildError) as exc:
            _load_bundled_content(raw, project_dir, project_dir)
        msg = str(exc.value)
        assert "summary_for" in msg, msg
        assert "self_provider" in msg, msg

    def test_cross_pak_view_reference_is_allowed(self, tmp_path):
        """A pak bundles only its own views; a bare name it does not bundle may
        be shipped by a sibling pak installed alongside it (real case:
        vcommunity-vsphere's `VM Details` -> vcommunity's `Windows Services
        vCommunity`).  The pak path must not treat that as an authoring error."""
        from vcfops_managementpacks.sdk_builder import _load_bundled_content

        raw, project_dir = _bundled(tmp_path, _DASH_UNKNOWN_VIEW)
        dashboards = _load_bundled_content(raw, project_dir, project_dir)[1]
        assert [d.name for d in dashboards] == ["Probe View Dash"]

    def test_unknown_view_still_rejected_for_the_repo_corpus(self, tmp_path):
        """The native (non-pak) path keeps the strict check."""
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        p = tmp_path / "dash.yaml"
        p.write_text(_DASH_UNKNOWN_VIEW)
        d = load_dashboard(p, enforce_framework_prefix=False)
        with pytest.raises(DashboardValidationError) as exc:
            d.validate({}, enforce_framework_prefix=False)
        assert "unknown view" in str(exc.value)

    def test_valid_summary_dashboard_still_loads(self, tmp_path):
        from vcfops_managementpacks.sdk_builder import _load_bundled_content

        raw, project_dir = _bundled(tmp_path, _SUMMARY_DASH_CLEAN)
        result = _load_bundled_content(raw, project_dir, project_dir)
        dashboards = result[1]
        assert [d.name for d in dashboards] == ["Probe Host Summary"]
