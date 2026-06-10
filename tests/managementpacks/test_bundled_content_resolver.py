"""Tests that bundled_content paths resolve relative to project_dir (adapter
directory), NOT the factory repo root.

Workstream G — resolver reconciliation.

Key assertions:
  1. A view YAML placed under <adapter_dir>/views/ is found when
     bundled_content.views lists 'views/<file>.yaml'.
  2. The same relative path does NOT resolve when the file only exists
     at an unrelated 'repo root' location outside the adapter dir.
  3. Adapters without a bundled_content key return ([], []) and are
     unaffected by the change.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from vcfops_managementpacks.sdk_builder import _load_bundled_content, SdkBuildError


# ---------------------------------------------------------------------------
# Minimal view YAML that passes load_view() without enforce_framework_prefix
# blocking (we pass enforce_framework_prefix=False via the loader's defaults
# being overridden).  We use a name that starts with "[VCF Content Factory] "
# so the default enforce check passes too.
# ---------------------------------------------------------------------------

_MINIMAL_VIEW_YAML = textwrap.dedent("""\
    id: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
    name: "[VCF Content Factory] Bundled Test View"
    description: "A minimal test view for bundled_content resolver tests."
    subject:
      adapter_kind: VMWARE
      resource_kind: VirtualMachine
    summary: false
    columns:
      - attribute: cpu|usage_average
        display_name: "CPU Usage"
        unit: percent
        transformation: AVG
""")

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_adapter_dir(tmp_path: Path) -> Path:
    """Create a minimal adapter project directory and return its path."""
    adapter_dir = tmp_path / "my_adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter.yaml").write_text(
        'name: "Test Adapter"\n'
        'version: "1.0.0"\n'
        'build_number: 1\n'
        'adapter_kind: "my_adapter"\n'
        'tier: 2\n'
        'description: "test"\n',
        encoding="utf-8",
    )
    (adapter_dir / "describe.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"'
        ' key="my_adapter" nameKey="1" version="1">'
        '<ResourceKinds>'
        '<ResourceKind key="my_adapter" nameKey="2" type="7" monitoringInterval="5"/>'
        '</ResourceKinds>'
        '</AdapterKind>\n',
        encoding="utf-8",
    )
    src = adapter_dir / "src" / "com" / "example"
    src.mkdir(parents=True)
    (src / "MyAdapter.java").write_text("public class MyAdapter {}\n", encoding="utf-8")
    (adapter_dir / "resources").mkdir()
    (adapter_dir / "resources" / "resources.properties").write_text(
        "1=Test Adapter\n2=Test Adapter Instance\n", encoding="utf-8"
    )
    return adapter_dir


# ---------------------------------------------------------------------------
# Test 1 — no bundled_content: returns ([], [])
# ---------------------------------------------------------------------------


class TestNoBundledContent:
    """Adapters without bundled_content are unaffected."""

    def test_absent_key_returns_empty_lists(self, tmp_path: Path) -> None:
        raw = {
            "name": "Test Adapter",
            "version": "1.0.0",
            "build_number": 1,
        }
        project_dir = _make_adapter_dir(tmp_path)
        views, dashboards = _load_bundled_content(raw, project_dir, project_dir)
        assert views == []
        assert dashboards == []

    def test_null_bundled_content_returns_empty_lists(self, tmp_path: Path) -> None:
        raw = {
            "name": "Test Adapter",
            "bundled_content": None,
        }
        project_dir = _make_adapter_dir(tmp_path)
        views, dashboards = _load_bundled_content(raw, project_dir, project_dir)
        assert views == []
        assert dashboards == []

    def test_empty_bundled_content_returns_empty_lists(self, tmp_path: Path) -> None:
        raw = {
            "name": "Test Adapter",
            "bundled_content": {},
        }
        project_dir = _make_adapter_dir(tmp_path)
        views, dashboards = _load_bundled_content(raw, project_dir, project_dir)
        assert views == []
        assert dashboards == []


# ---------------------------------------------------------------------------
# Test 2 — view co-located under adapter_dir/views/ resolves correctly
# ---------------------------------------------------------------------------


class TestViewResolvesRelativeToProjectDir:
    """bundled_content.views paths resolve relative to project_dir."""

    def test_colocated_view_is_found(self, tmp_path: Path) -> None:
        project_dir = _make_adapter_dir(tmp_path)
        views_dir = project_dir / "views"
        views_dir.mkdir()
        (views_dir / "test_view.yaml").write_text(_MINIMAL_VIEW_YAML, encoding="utf-8")

        raw = {
            "bundled_content": {
                "views": ["views/test_view.yaml"],
            }
        }
        views, dashboards = _load_bundled_content(raw, project_dir, project_dir)
        assert len(views) == 1
        assert dashboards == []
        assert views[0].name == "[VCF Content Factory] Bundled Test View"

    def test_view_only_at_unrelated_root_is_not_found(self, tmp_path: Path) -> None:
        """A view that exists at a sibling 'repo root' but NOT inside the adapter
        dir must raise SdkBuildError — it must NOT be found via the old repo-root
        resolution path.
        """
        # Simulate old layout: file lives at <tmp>/content/views/test_view.yaml
        # (the factory repo root structure), NOT under <tmp>/my_adapter/views/.
        fake_repo_root = tmp_path
        repo_views_dir = fake_repo_root / "content" / "views"
        repo_views_dir.mkdir(parents=True)
        (repo_views_dir / "test_view.yaml").write_text(
            _MINIMAL_VIEW_YAML, encoding="utf-8"
        )

        project_dir = _make_adapter_dir(tmp_path)
        # The adapter dir does NOT contain views/test_view.yaml.
        # Only the factory root does.

        raw = {
            "bundled_content": {
                "views": ["views/test_view.yaml"],
            }
        }
        with pytest.raises(SdkBuildError, match="path not found"):
            _load_bundled_content(raw, project_dir, project_dir)

    def test_view_at_full_factory_path_not_found_via_relative(
        self, tmp_path: Path
    ) -> None:
        """A path like 'content/views/test_view.yaml' relative to project_dir
        does NOT resolve to a file that lives at project_dir/../content/views/.
        Only a file genuinely inside project_dir resolves.
        """
        project_dir = _make_adapter_dir(tmp_path)
        # Place view one directory above project_dir (simulating factory root layout)
        above_views = tmp_path / "content" / "views"
        above_views.mkdir(parents=True)
        (above_views / "test_view.yaml").write_text(
            _MINIMAL_VIEW_YAML, encoding="utf-8"
        )

        raw = {
            "bundled_content": {
                "views": ["content/views/test_view.yaml"],
            }
        }
        with pytest.raises(SdkBuildError, match="path not found"):
            _load_bundled_content(raw, project_dir, project_dir)


# ---------------------------------------------------------------------------
# Test 3 — validate_sdk_project uses project_dir for bundled_content
# ---------------------------------------------------------------------------


class TestValidateSdkProjectUsesProjectDir:
    """validate_sdk_project must also resolve bundled_content relative to
    project_dir, not the factory root.  We test the negative: putting the
    view only at an unrelated path causes a validation error (not a silent
    pass from the old repo-root fallback).
    """

    def test_missing_colocated_view_surfaces_as_validation_error(
        self, tmp_path: Path
    ) -> None:
        from vcfops_managementpacks.sdk_builder import validate_sdk_project

        project_dir = _make_adapter_dir(tmp_path)
        # Write adapter.yaml with a bundled_content.views reference that
        # points to views/test_view.yaml relative to the adapter dir.
        # Do NOT create that file — it should appear as a bundled_content
        # load error in the validation output.
        (project_dir / "adapter.yaml").write_text(
            'name: "Test Adapter"\n'
            'version: "1.0.0"\n'
            'build_number: 1\n'
            'adapter_kind: "my_adapter"\n'
            'tier: 2\n'
            'description: "test"\n'
            "bundled_content:\n"
            "  views:\n"
            "    - views/missing_view.yaml\n",
            encoding="utf-8",
        )

        errors = validate_sdk_project(project_dir)
        # The bundled_content path error must surface as a validation error,
        # not be silently swallowed.
        bundled_errors = [e for e in errors if "bundled_content" in e]
        assert bundled_errors, (
            f"Expected a bundled_content error but got errors: {errors}"
        )
        # The error must reference the project_dir resolution, not a repo-root path.
        assert any("missing_view.yaml" in e for e in bundled_errors), (
            f"Expected 'missing_view.yaml' in error message, got: {bundled_errors}"
        )
