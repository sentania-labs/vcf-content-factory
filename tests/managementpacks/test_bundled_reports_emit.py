"""Tests for bundled_content.reports emit path in sdk_builder.py.

Layout confirmed from the vCommunity reference pak:
  references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/
  - Report XMLs are FLAT files directly in content/reports/ (no subdirectory).
  - Each file: <Content><Reports><ReportDef ...>...</ReportDef></Reports></Content>
  - No separate resources/content.properties per report (unlike views).
  - Dashboard/view UUIDs in ContentKey elements are emitted verbatim.

Covers:
  1. A bundled report emits to content/reports/<safe_name>.xml (flat layout).
  2. The emitted XML is well-formed with <Content><Reports><ReportDef> root.
  3. Empty/absent bundled_content.reports key → no spurious content/reports output
     beyond what views may write.
  4. Tuple arity: _load_bundled_content returns a 6-tuple; empty reports is [].
  5. Reports and views coexist: content/reports/ dir entry appears exactly once.
  6. Report safe_name collision dedup: two reports with same sanitized name get -2.
  7. Dashboard UUID in a Dashboard section is emitted verbatim (not resolved).
"""
from __future__ import annotations

import io
import textwrap
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

import pytest

from vcfops_managementpacks.sdk_builder import (
    SdkBuildError,
    _load_bundled_content,
    _write_outer_pak,
)
from vcfops_managementpacks.sdk_project import SdkProjectDef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    name: str = "Test Adapter", adapter_kind: str = "test_adapter"
) -> SdkProjectDef:
    from vcfops_managementpacks.sdk_project import _derive_entry_class

    return SdkProjectDef(
        name=name,
        version="1.0.0",
        build_number=1,
        adapter_kind=adapter_kind,
        description="Test adapter for report emit tests.",
        tier=2,
        dependencies=[],
        entry_class=_derive_entry_class(adapter_kind),
        source_path=Path("/dev/null"),
    )


def _minimal_adapters_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w"):
        pass
    return buf.getvalue()


def _pak_namelist(pak_path: Path) -> List[str]:
    with zipfile.ZipFile(pak_path, "r") as zf:
        return zf.namelist()


def _pak_read(pak_path: Path, entry: str) -> bytes:
    with zipfile.ZipFile(pak_path, "r") as zf:
        return zf.read(entry)


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Minimal report YAML
# ---------------------------------------------------------------------------

_REPORT_UUID = "deadbeef-0001-0001-0001-000000000001"

_REPORT_YAML = textwrap.dedent(
    f"""\
    id: {_REPORT_UUID}
    name: "Test Report"
    description: "A minimal test report"
    subject_types:
      - adapter_kind: VMWARE
        resource_kind: VirtualMachine
        type: self
    sections:
      - type: CoverPage
      - type: TableOfContents
    settings:
      show_page_footer: true
      output_formats:
        - pdf
    """
)

_REPORT_YAML_2 = textwrap.dedent(
    """\
    id: deadbeef-0002-0002-0002-000000000002
    name: "Test Report"
    description: "Second report with same sanitized name"
    subject_types:
      - adapter_kind: VMWARE
        resource_kind: HostSystem
        type: self
    sections:
      - type: CoverPage
    settings:
      show_page_footer: false
      output_formats:
        - csv
    """
)

# Report that embeds a Dashboard ContentKey UUID
_DASHBOARD_UUID = "aabbccdd-1111-2222-3333-444455556666"

_REPORT_WITH_DASHBOARD_YAML = textwrap.dedent(
    f"""\
    id: deadbeef-0003-0003-0003-000000000003
    name: "Test Report With Dashboard"
    description: "Report that has a Dashboard section"
    subject_types:
      - adapter_kind: VMWARE
        resource_kind: VirtualMachine
        type: self
    sections:
      - type: CoverPage
      - type: Dashboard
        dashboard: "Fake Dashboard"
        orientation: Landscape
    settings:
      show_page_footer: true
      output_formats:
        - pdf
    """
)

# Minimal view YAML for coexistence tests
_VIEW_UUID = "11112222-3333-4444-5555-666677778888"

_VIEW_YAML = textwrap.dedent(
    f"""\
    id: {_VIEW_UUID}
    name: "[VCF Content Factory] Test View"
    description: "View for coexistence test"
    subject:
      adapter_kind: VMWARE
      resource_kind: VirtualMachine
    summary: false
    columns:
      - attribute: cpu|usage_average
        display_name: "CPU Usage"
        unit: percent
        transformation: AVG
    """
)


# ---------------------------------------------------------------------------
# Test 1 — basic emit path and XML shape
# ---------------------------------------------------------------------------


class TestReportEmit:
    """content/reports/<safe_name>.xml is written with correct XML structure."""

    def test_report_xml_written_to_pak(self, tmp_path: Path) -> None:
        """Report XML appears flat at content/reports/<safe_name>.xml."""
        project_dir = tmp_path / "adapter"
        rpt_path = project_dir / "reports" / "test_report.yaml"
        _write_yaml(rpt_path, _REPORT_YAML)

        from vcfops_reports.loader import load_file

        rpt = load_file(rpt_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            reports=[rpt],
        )

        names = _pak_namelist(pak_path)
        assert "content/" in names, "content/ dir entry missing"
        assert "content/reports/" in names, "content/reports/ dir entry missing"
        report_entries = [
            n for n in names
            if n.startswith("content/reports/") and n.endswith(".xml")
        ]
        assert len(report_entries) == 1, (
            f"Expected 1 report XML entry; got: {report_entries}"
        )
        # Flat layout: no subdirectory between content/reports/ and the .xml
        assert "/" not in report_entries[0].removeprefix("content/reports/"), (
            f"Report XML must be at flat path content/reports/<name>.xml, "
            f"not in a subdirectory; got: {report_entries[0]}"
        )

    def test_report_xml_well_formed_with_correct_root(self, tmp_path: Path) -> None:
        """Emitted XML is well-formed with <Content><Reports><ReportDef> root."""
        project_dir = tmp_path / "adapter"
        rpt_path = project_dir / "reports" / "test_report.yaml"
        _write_yaml(rpt_path, _REPORT_YAML)

        from vcfops_reports.loader import load_file

        rpt = load_file(rpt_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            reports=[rpt],
        )

        names = _pak_namelist(pak_path)
        report_entries = [
            n for n in names
            if n.startswith("content/reports/") and n.endswith(".xml")
        ]
        raw = _pak_read(pak_path, report_entries[0]).decode("utf-8")

        # Parse XML — must not raise
        root = ET.fromstring(raw)
        assert root.tag == "Content", f"Expected root tag 'Content'; got '{root.tag}'"
        reports_el = root.find("Reports")
        assert reports_el is not None, "<Reports> element missing under <Content>"
        report_def = reports_el.find("ReportDef")
        assert report_def is not None, "<ReportDef> element missing under <Reports>"
        assert report_def.get("id") == _REPORT_UUID, (
            f"Expected ReportDef id='{_REPORT_UUID}'; got '{report_def.get('id')}'"
        )

    def test_report_xml_contains_report_title(self, tmp_path: Path) -> None:
        """Emitted XML contains the report title."""
        project_dir = tmp_path / "adapter"
        rpt_path = project_dir / "reports" / "test_report.yaml"
        _write_yaml(rpt_path, _REPORT_YAML)

        from vcfops_reports.loader import load_file

        rpt = load_file(rpt_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            reports=[rpt],
        )

        names = _pak_namelist(pak_path)
        report_entries = [
            n for n in names
            if n.startswith("content/reports/") and n.endswith(".xml")
        ]
        raw = _pak_read(pak_path, report_entries[0]).decode("utf-8")
        assert "Test Report" in raw, f"Report title not found in XML: {raw[:400]}"
        assert "CoverPage" in raw, "CoverPage section missing"
        assert "TABLE_OF_CONTENTS" in raw, "TableOfContents section missing"

    def test_no_reports_no_extra_content_reports_entries(self, tmp_path: Path) -> None:
        """When no reports are bundled (and no views), no content/reports/ is emitted."""
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project, _minimal_adapters_zip(), output_dir
        )
        names = _pak_namelist(pak_path)
        # No content at all expected
        assert not any("content/reports" in n for n in names), (
            f"Unexpected content/reports entries: "
            f"{[n for n in names if 'content/reports' in n]}"
        )


# ---------------------------------------------------------------------------
# Test 2 — _load_bundled_content returns 6-tuple; empty reports is []
# ---------------------------------------------------------------------------


class TestLoadBundledContentReportsTuple:
    """_load_bundled_content returns a 6-tuple; reports element is [] when absent."""

    def _make_adapter_dir(self, tmp_path: Path) -> Path:
        adapter_dir = tmp_path / "my_adapter"
        adapter_dir.mkdir()
        return adapter_dir

    def test_absent_reports_returns_empty_list(self, tmp_path: Path) -> None:
        raw = {"bundled_content": {"views": []}}
        project_dir = self._make_adapter_dir(tmp_path)
        result = _load_bundled_content(raw, project_dir, project_dir)
        assert len(result) == 6, f"Expected 6-tuple; got {len(result)}-tuple"
        views, dashboards, supermetrics, symptoms, alerts, reports = result
        assert reports == [], f"Expected reports=[], got {reports!r}"

    def test_no_bundled_content_returns_six_empty_lists(self, tmp_path: Path) -> None:
        raw = {}
        project_dir = self._make_adapter_dir(tmp_path)
        result = _load_bundled_content(raw, project_dir, project_dir)
        assert len(result) == 6, f"Expected 6-tuple; got {len(result)}-tuple"
        for i, item in enumerate(result):
            assert item == [], f"Element {i} should be []; got {item!r}"

    def test_reports_path_loads_report_def(self, tmp_path: Path) -> None:
        project_dir = self._make_adapter_dir(tmp_path)
        rpt_dir = project_dir / "reports"
        rpt_dir.mkdir()
        (rpt_dir / "r.yaml").write_text(_REPORT_YAML, encoding="utf-8")

        raw = {"bundled_content": {"reports": ["reports/r.yaml"]}}
        result = _load_bundled_content(raw, project_dir, project_dir)
        assert len(result) == 6
        _, _, _, _, _, reports = result
        assert len(reports) == 1
        assert reports[0].id == _REPORT_UUID

    def test_missing_report_path_raises_sdk_build_error(self, tmp_path: Path) -> None:
        project_dir = self._make_adapter_dir(tmp_path)
        raw = {"bundled_content": {"reports": ["reports/nonexistent.yaml"]}}
        with pytest.raises(SdkBuildError, match="bundled_content.reports"):
            _load_bundled_content(raw, project_dir, project_dir)


# ---------------------------------------------------------------------------
# Test 3 — content/reports/ dir entry appears exactly once when both views
#           and reports are bundled
# ---------------------------------------------------------------------------


class TestViewsAndReportsCoexist:
    """Views (subdir) and reports (flat) can coexist under content/reports/
    without duplicating the dir entry."""

    def test_views_and_reports_content_reports_dir_once(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "adapter"

        view_path = project_dir / "views" / "v.yaml"
        _write_yaml(view_path, _VIEW_YAML)
        rpt_path = project_dir / "reports" / "r.yaml"
        _write_yaml(rpt_path, _REPORT_YAML)

        from vcfops_dashboards.loader import load_view
        from vcfops_reports.loader import load_file as load_report

        view = load_view(view_path)
        rpt = load_report(rpt_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            views=[view],
            reports=[rpt],
        )

        names = _pak_namelist(pak_path)
        reports_dir_count = names.count("content/reports/")
        assert reports_dir_count == 1, (
            f"content/reports/ dir entry appears {reports_dir_count} times "
            f"(expected exactly 1)"
        )

        # View: subdirectory pattern
        view_entries = [
            n for n in names
            if n.startswith("content/reports/") and n.endswith("content.xml")
        ]
        assert len(view_entries) == 1, f"Expected 1 view content.xml; got {view_entries}"

        # Report: flat pattern
        report_xml_entries = [
            n for n in names
            if n.startswith("content/reports/") and n.endswith(".xml")
            and "/content.xml" not in n
        ]
        assert len(report_xml_entries) == 1, (
            f"Expected 1 flat report XML; got {report_xml_entries}"
        )
        # Confirm the flat entry has no subdirectory component
        flat_basename = report_xml_entries[0].removeprefix("content/reports/")
        assert "/" not in flat_basename, (
            f"Report XML must be flat (no subdir); got path: {report_xml_entries[0]}"
        )

    def test_only_reports_no_views_content_reports_dir_once(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "adapter"
        rpt_path = project_dir / "reports" / "r.yaml"
        _write_yaml(rpt_path, _REPORT_YAML)

        from vcfops_reports.loader import load_file as load_report

        rpt = load_report(rpt_path, enforce_framework_prefix=False)
        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            reports=[rpt],
        )

        names = _pak_namelist(pak_path)
        assert names.count("content/reports/") == 1, (
            f"content/reports/ should appear exactly once; "
            f"got {names.count('content/reports/')} times"
        )


# ---------------------------------------------------------------------------
# Test 4 — safe_name collision dedup
# ---------------------------------------------------------------------------


class TestReportSafeNameDedup:
    """Two reports with the same sanitized safe_name get distinct filenames."""

    def test_report_collision_both_files_present(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "adapter"
        rpt_a_path = project_dir / "reports" / "r_a.yaml"
        rpt_b_path = project_dir / "reports" / "r_b.yaml"
        _write_yaml(rpt_a_path, _REPORT_YAML)
        _write_yaml(rpt_b_path, _REPORT_YAML_2)

        from vcfops_reports.loader import load_file as load_report

        rpt_a = load_report(rpt_a_path, enforce_framework_prefix=False)
        rpt_b = load_report(rpt_b_path, enforce_framework_prefix=False)

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            project_dir=project_dir,
            reports=[rpt_a, rpt_b],
        )

        names = _pak_namelist(pak_path)
        report_entries = sorted(
            n for n in names
            if n.startswith("content/reports/") and n.endswith(".xml")
        )
        assert len(report_entries) == 2, (
            f"Expected 2 report XML entries (dedup); got: {report_entries}"
        )
        stems = {
            e.removeprefix("content/reports/").removesuffix(".xml")
            for e in report_entries
        }
        base_stem = min(stems, key=len)
        assert f"{base_stem}-2" in stems, (
            f"Expected dedup suffix '-2' on second entry; got stems: {stems}"
        )


# ---------------------------------------------------------------------------
# Test 5 — dashboard UUID in Dashboard section is emitted verbatim
# ---------------------------------------------------------------------------


class TestReportDashboardUuidVerbatim:
    """Dashboard UUIDs in report sections are emitted verbatim (no resolution).

    The loader resolves view/dashboard names to UUIDs by scanning content dirs.
    When those dirs are absent (or the name cannot be resolved), the id is empty
    and the loader raises a validation error.  For bundled-content reports,
    the caller must supply a pre-resolved ReportDef or bypass validation.

    This test verifies that whatever UUID appears in the loaded ReportDef's
    Dashboard section ContentKey is emitted verbatim in the pak XML — the
    builder does not further transform or look up the UUID.
    """

    def test_dashboard_uuid_emitted_verbatim(self, tmp_path: Path) -> None:
        """A ReportDef with a pre-resolved dashboard_id emits that UUID verbatim."""
        from vcfops_reports.loader import ReportDef, Section, SubjectType, ReportSettings

        # Build a ReportDef directly (bypassing file load) with a known dashboard_id
        rpt = ReportDef(
            id=_REPORT_UUID,
            name="Test Report With Dashboard",
            description="Dashboard UUID passthrough test",
            subject_types=[
                SubjectType(adapter_kind="VMWARE", resource_kind="VirtualMachine", type="self")
            ],
            sections=[
                Section(type="CoverPage"),
                Section(
                    type="Dashboard",
                    dashboard_name="Fake Dashboard",
                    dashboard_id=_DASHBOARD_UUID,
                    orientation="Landscape",
                ),
            ],
            settings=ReportSettings(show_page_footer=True, output_formats=["pdf"]),
        )

        project = _make_project()
        output_dir = tmp_path / "out"
        pak_path = _write_outer_pak(
            project,
            _minimal_adapters_zip(),
            output_dir,
            reports=[rpt],
        )

        names = _pak_namelist(pak_path)
        report_entries = [
            n for n in names
            if n.startswith("content/reports/") and n.endswith(".xml")
        ]
        assert report_entries, "No report XML in pak"
        raw = _pak_read(pak_path, report_entries[0]).decode("utf-8")

        assert _DASHBOARD_UUID in raw, (
            f"Expected dashboard UUID '{_DASHBOARD_UUID}' emitted verbatim "
            f"in report XML; got excerpt: {raw[:600]}"
        )
