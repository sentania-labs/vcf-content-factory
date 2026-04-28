"""v2 item #3 — validator polish: time_window warning suppressed for dashboard-embedded views.

Four test cases:

  T1 — Aggregating-column view embedded in a dashboard via View widget:
       full-corpus validate suppresses the warning.

  T2 — Same aggregating-column view with NO dashboard referencing it:
       full-corpus validate emits the warning (current behavior, regression guard).

  T3 — Same aggregating-column view WITH explicit time_window set:
       no warning regardless of embedding (current behavior, regression guard).

  T4 — Single-file validate (explicit path argument, not full-corpus):
       warning fires regardless of embedding since there is no dashboard context.

All tests use tmp_path fixtures and do not touch any content YAML.
No network calls are made. No install commands are run.
"""
from __future__ import annotations

import textwrap
import uuid
import warnings
from pathlib import Path
from typing import List, Optional

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n")
    return path


def _make_aggregating_view(views_dir: Path, stem: str, name: str,
                           with_time_window: bool = False) -> Path:
    """Write a minimal view YAML with a MAX column (aggregating transformation).

    If with_time_window is True, adds a time_window block so the warning should
    NOT fire under any circumstances.
    """
    data: dict = {
        "name": name,
        "subject": {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
        },
        "columns": [
            {
                "attribute": "cpu|usage_average",
                "display_name": "CPU Usage",
                "transformation": "MAX",
            }
        ],
    }
    if with_time_window:
        data["time_window"] = {"unit": "MONTHS", "count": 6}
    p = views_dir / f"{stem}.yaml"
    views_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _make_dashboard_referencing_view(dashboards_dir: Path, stem: str, view_name: str) -> Path:
    """Write a minimal dashboard YAML with a View widget that references view_name."""
    data = {
        "name": f"Dashboard {stem}",
        "widgets": [
            {
                "id": str(uuid.uuid4()),
                "type": "View",
                "title": "Widget",
                "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
                "view": view_name,
            }
        ],
    }
    p = dashboards_dir / f"{stem}.yaml"
    dashboards_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _collect_time_window_warnings(
    views_dir: Path,
    dashboards_dir: Optional[Path] = None,
) -> List[str]:
    """Run the full-corpus validate flow (the cmd_validate path) and return
    the text of any time_window UserWarnings that were emitted.

    Simulates what cmd_validate does for the full-corpus case: loads all views
    and dashboards, builds the embedded set, and re-emits only non-embedded
    time_window warnings.

    We call the loader + dep_walker directly rather than subprocess so the test
    stays in-process and avoids needing a real repo layout.
    """
    from vcfops_dashboards.loader import load_all
    from vcfops_common.dep_walker import extract_view_names_from_dashboards
    from vcfops_dashboards.cli import (
        _is_time_window_warning,
        _extract_view_name_from_time_window_warning,
    )

    if dashboards_dir is None:
        dashboards_dir = Path("/nonexistent-empty-dir-for-testing")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        views, dashboards = load_all(
            views_dir,
            dashboards_dir,
            enforce_framework_prefix=False,
        )

    # Build embedded set from all loaded dashboards
    embedded_names: set = set(extract_view_names_from_dashboards(dashboards))

    # Replay only non-embedded time_window warnings
    emitted: List[str] = []
    for w in caught:
        if not (issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message))):
            continue
        view_name = _extract_view_name_from_time_window_warning(str(w.message))
        if view_name and view_name in embedded_names:
            continue  # suppressed
        emitted.append(str(w.message))

    return emitted


# ---------------------------------------------------------------------------
# T1 — Aggregating view embedded in a dashboard → warning suppressed
# ---------------------------------------------------------------------------

class TestEmbeddedViewWarningSuppressed:
    """T1: A view with aggregating columns that is embedded in a dashboard
    does NOT trigger the time_window warning during full-corpus validate."""

    def test_no_warning_when_view_is_dashboard_embedded(self, tmp_path):
        views_dir = tmp_path / "views"
        dashboards_dir = tmp_path / "dashboards"
        view_name = "My Aggregating View"

        _make_aggregating_view(views_dir, "agg_view", view_name)
        _make_dashboard_referencing_view(dashboards_dir, "my_dash", view_name)

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir)

        assert emitted == [], (
            f"Expected no time_window warning for dashboard-embedded view, "
            f"but got: {emitted}"
        )

    def test_warning_suppressed_for_each_embedded_view(self, tmp_path):
        """Multiple embedded views all have their warnings suppressed."""
        views_dir = tmp_path / "views"
        dashboards_dir = tmp_path / "dashboards"
        view_a = "View Alpha"
        view_b = "View Beta"

        _make_aggregating_view(views_dir, "view_a", view_a)
        _make_aggregating_view(views_dir, "view_b", view_b)
        _make_dashboard_referencing_view(dashboards_dir, "dash_a", view_a)
        _make_dashboard_referencing_view(dashboards_dir, "dash_b", view_b)

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir)
        assert emitted == [], (
            f"Expected no warnings for two embedded views, got: {emitted}"
        )


# ---------------------------------------------------------------------------
# T2 — Aggregating view with NO dashboard → warning fires
# ---------------------------------------------------------------------------

class TestStandaloneViewWarningFires:
    """T2: A view with aggregating columns that is NOT referenced by any
    dashboard DOES trigger the time_window warning (current behavior)."""

    def test_warning_fires_when_view_not_embedded(self, tmp_path):
        views_dir = tmp_path / "views"
        # No dashboards directory → no embedding
        view_name = "My Standalone Aggregating View"

        _make_aggregating_view(views_dir, "agg_view", view_name)

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir=None)

        assert len(emitted) == 1, (
            f"Expected exactly 1 time_window warning for standalone view, "
            f"got: {emitted}"
        )
        assert view_name in emitted[0], (
            f"Warning should mention the view name '{view_name}', got: {emitted[0]}"
        )

    def test_warning_fires_when_dashboard_does_not_reference_view(self, tmp_path):
        """A dashboard exists but doesn't reference the aggregating view → warning fires."""
        views_dir = tmp_path / "views"
        dashboards_dir = tmp_path / "dashboards"
        view_name = "Unreferenced Aggregating View"
        other_view = "Some Other View"

        _make_aggregating_view(views_dir, "agg_view", view_name)
        _make_aggregating_view(views_dir, "other_view", other_view)
        # Dashboard only references 'other_view', not 'agg_view'
        _make_dashboard_referencing_view(dashboards_dir, "my_dash", other_view)

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir)

        # 'agg_view' is standalone → warning fires
        # 'other_view' is embedded → warning suppressed
        warning_subjects = [_extract_name(e) for e in emitted]
        assert view_name in warning_subjects, (
            f"Expected warning for standalone '{view_name}', got subjects: {warning_subjects}"
        )
        assert other_view not in warning_subjects, (
            f"Expected no warning for embedded '{other_view}', got subjects: {warning_subjects}"
        )


def _extract_name(warning_msg: str) -> str:
    """Extract view name from warning message text (helper for T2 assertions)."""
    from vcfops_dashboards.cli import _extract_view_name_from_time_window_warning
    return _extract_view_name_from_time_window_warning(warning_msg)


# ---------------------------------------------------------------------------
# T3 — Explicit time_window set → no warning regardless of embedding
# ---------------------------------------------------------------------------

class TestExplicitTimeWindowNoWarning:
    """T3: A view with aggregating columns AND an explicit time_window never
    triggers the warning, regardless of whether it is embedded in a dashboard."""

    def test_no_warning_when_time_window_set_standalone(self, tmp_path):
        """time_window set + no embedding → no warning."""
        views_dir = tmp_path / "views"
        view_name = "View With Window"

        _make_aggregating_view(views_dir, "windowed_view", view_name, with_time_window=True)

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir=None)

        assert emitted == [], (
            f"Expected no warning when time_window is explicit, got: {emitted}"
        )

    def test_no_warning_when_time_window_set_embedded(self, tmp_path):
        """time_window set + embedded → no warning."""
        views_dir = tmp_path / "views"
        dashboards_dir = tmp_path / "dashboards"
        view_name = "View With Window Embedded"

        _make_aggregating_view(views_dir, "windowed_view", view_name, with_time_window=True)
        _make_dashboard_referencing_view(dashboards_dir, "my_dash", view_name)

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir)

        assert emitted == [], (
            f"Expected no warning when time_window is explicit (embedded), got: {emitted}"
        )


# ---------------------------------------------------------------------------
# T4 — Single-file validate (explicit path) → warning fires regardless
# ---------------------------------------------------------------------------

class TestSingleFileValidateWarningFires:
    """T4: When validate is invoked with an explicit single-file path (not the
    full-corpus default), the warning fires even for a view that would be
    embedded if the full corpus were loaded.

    This test calls load_view() directly (which is what a single-file validate
    would do, with no dashboard context available) and asserts the warning
    appears.
    """

    def test_warning_fires_on_direct_load_view_call(self, tmp_path):
        """load_view() without embedded_in_dashboard=True always emits the warning
        for aggregating columns without time_window."""
        views_dir = tmp_path / "views"
        view_name = "My View For Single File Test"

        view_path = _make_aggregating_view(views_dir, "single_file_view", view_name)

        from vcfops_dashboards.loader import load_view

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_view(view_path, enforce_framework_prefix=False)

        time_window_warnings = [
            str(w.message) for w in caught
            if issubclass(w.category, UserWarning) and "no time_window is set" in str(w.message)
        ]
        assert len(time_window_warnings) == 1, (
            f"Expected 1 time_window warning from load_view, got: {time_window_warnings}"
        )
        assert view_name in time_window_warnings[0], (
            f"Warning should mention the view name, got: {time_window_warnings[0]}"
        )

    def test_no_warning_when_embedded_in_dashboard_flag_set(self, tmp_path):
        """load_view() with embedded_in_dashboard=True suppresses the warning.

        This verifies the ViewDef.validate() parameter works correctly,
        which is the underlying mechanism cmd_validate uses.
        """
        views_dir = tmp_path / "views"
        view_name = "My Embedded View For Flag Test"

        view_path = _make_aggregating_view(views_dir, "flag_test_view", view_name)

        from vcfops_dashboards.loader import load_view

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_view(view_path, enforce_framework_prefix=False, embedded_in_dashboard=True)

        time_window_warnings = [
            str(w.message) for w in caught
            if issubclass(w.category, UserWarning) and "no time_window is set" in str(w.message)
        ]
        assert time_window_warnings == [], (
            f"Expected no time_window warning when embedded_in_dashboard=True, "
            f"got: {time_window_warnings}"
        )


# ---------------------------------------------------------------------------
# T5 — Real-repo regression: IDPS Planner views are suppressed in full-corpus
# ---------------------------------------------------------------------------

class TestRealRepoIDPSPlannerSuppression:
    """Regression guard: the two IDPS Planner views that triggered the original
    report are suppressed in the real repo's full-corpus validate."""

    def test_idps_planner_vm_metrics_view_warning_suppressed(self):
        """The '[IDPS] IDPS Planner VM Metrics' view is embedded and should not warn."""
        repo_root = Path(__file__).parent.parent
        views_dir = repo_root / "third_party" / "idps-planner" / "views"
        dashboards_dir = repo_root / "third_party" / "idps-planner" / "dashboards"

        if not views_dir.exists() or not dashboards_dir.exists():
            pytest.skip("idps-planner third_party content not present")

        emitted = _collect_time_window_warnings(views_dir, dashboards_dir)

        # Both IDPS Planner views with aggregating columns are dashboard-embedded.
        for w in emitted:
            assert "IDPS Planner VM Metrics" not in w, (
                f"'[IDPS] IDPS Planner VM Metrics' warning should be suppressed, got: {w}"
            )
            assert "IDPS Planner Host Metrics" not in w, (
                f"'IDPS Planner Host Metrics' warning should be suppressed, got: {w}"
            )
