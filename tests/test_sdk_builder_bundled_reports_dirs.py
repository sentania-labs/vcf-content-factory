"""Regression test: sdk_builder._load_bundled_content() must resolve a
bundled report's view/dashboard cross-references against the adapter
project's own views/ and dashboards/ directories, not the factory-default
content/views and content/dashboards.

Root cause (2026-07-10, closeout Fix 3): `_load_bundled_content()` called
`vcfops_reports.loader.load_file(path, enforce_framework_prefix=False)`
without `views_dir`/`dashboards_dir`, so it fell back to the loader's
default `content/views` / `content/dashboards` — the factory repo's own
directories — instead of the adapter repo's `<project_dir>/views/` and
`<project_dir>/dashboards/`. Any bundled report referencing a view that
lives only in the adapter repo (the normal case for Tier 2 SDK adapters,
whose content lives under `content/sdk-adapters/<name>/`) failed to
resolve with "could not be resolved — ensure the view exists in views/",
even though the view file was right there in the same project.

This is a hermetic tmp_path fixture — it does not depend on the
vcommunity-vsphere adapter repo (a separate, independently-versioned git
repo) or touch any Java/javac tooling.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False))


def _make_project(tmp_path: Path) -> Path:
    """Build a minimal adapter project dir with a view + report pair whose
    report references the view by name — the exact shape of the pilot
    content (`Report - VOA - Virtual Machines for CSV export.yaml` /
    `Report Virtual Machines for CSV export.yaml`) in the vcommunity-vsphere
    adapter repo.
    """
    project_dir = tmp_path / "adapter_project"

    _write_yaml(project_dir / "views" / "csv-export.yaml", {
        "id": "ef3e6901-4c10-4208-9b95-4c82bf54f810",
        "name": "Report: Virtual Machines for CSV export",
        "description": "A simple table for export as a CSV file.",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [
            {"attribute": "summary|guest|hostName", "display_name": "Hostname"},
        ],
    })

    _write_yaml(project_dir / "reports" / "csv-export-report.yaml", {
        "id": "ecc10685-6eea-4f01-9c33-70b1e00c1c3a",
        "name": "Report: Virtual Machines for CSV export",
        "description": "CSV export report.",
        "subject_types": [
            {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine", "type": "self"},
        ],
        "sections": [
            {
                "type": "View",
                "view": "Report: Virtual Machines for CSV export",
                "orientation": "Portrait",
                "colorize": False,
            },
        ],
        "settings": {"show_page_footer": False, "output_formats": ["csv"]},
    })

    return project_dir


class TestLoadBundledContentReportsResolveAdapterViewsDir:
    def test_report_view_reference_resolves_against_project_dir(self, tmp_path):
        from vcfops_managementpacks.sdk_builder import _load_bundled_content

        project_dir = _make_project(tmp_path)
        raw = {
            "bundled_content": {
                "views": ["views/csv-export.yaml"],
                "reports": ["reports/csv-export-report.yaml"],
            }
        }

        (views, dashboards, supermetrics, symptoms, alerts, reports,
         recommendations) = _load_bundled_content(raw, project_dir, project_dir)

        assert len(reports) == 1
        report = reports[0]
        view_sections = [s for s in report.sections if s.type == "View"]
        assert len(view_sections) == 1
        assert view_sections[0].view_id == "ef3e6901-4c10-4208-9b95-4c82bf54f810", (
            "Report's View section did not resolve to the adapter project's "
            "own view id — _load_bundled_content regressed to scanning the "
            "factory-default content/views instead of <project_dir>/views."
        )

    def test_report_fails_closed_without_the_fix_semantics(self, tmp_path):
        """Sanity check on the fixture itself: a report referencing a view
        that does NOT exist anywhere must still fail to resolve (proves the
        fixture isn't accidentally passing for an unrelated reason).
        """
        from vcfops_managementpacks.sdk_builder import _load_bundled_content, SdkBuildError

        project_dir = _make_project(tmp_path)
        # Point the report at a view that isn't bundled or present anywhere.
        report_path = project_dir / "reports" / "csv-export-report.yaml"
        data = yaml.safe_load(report_path.read_text())
        data["sections"][0]["view"] = "Nonexistent View"
        report_path.write_text(yaml.dump(data, default_flow_style=False))

        raw = {
            "bundled_content": {
                "views": ["views/csv-export.yaml"],
                "reports": ["reports/csv-export-report.yaml"],
            }
        }
        with pytest.raises(SdkBuildError, match="could not be resolved"):
            _load_bundled_content(raw, project_dir, project_dir)
