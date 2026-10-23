"""docs/_index_extra.md: the adapter's own sections in the generated index (#171).

docs_gen rewrites docs/README.md on every build, so a hand edit to it is
erased. The declared extension point is a hand-curated include,
docs/_index_extra.md, that the generator reads (never writes) and merges
verbatim under a stable heading.

Covers:
  1. Include absent: README is byte-identical to the pre-#171 output.
  2. Include present: merged under INDEX_EXTRA_HEADING, survives repeated
     builds, the include itself is untouched, and the result map says so.
  3. Blank include: treated as absent (no empty heading).
  4. The heading lands after the generated sections, so the include cannot
     displace the generated Contents / Quick Reference.
"""
from __future__ import annotations

from pathlib import Path

from vcfcf_managementpacks.docs_gen import (
    INDEX_EXTRA_FILENAME,
    INDEX_EXTRA_HEADING,
    build_doc_model,
    generate_docset,
    generate_readme_md,
)


_DESCRIBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"
             key="test_adapter" nameKey="1" version="1">
    <ResourceKinds>
        <ResourceKind key="test_adapter" nameKey="2" type="7" monitoringInterval="5">
            <ResourceIdentifier key="host" nameKey="3" required="true" identType="1"/>
        </ResourceKind>
        <ResourceKind key="TestThing" nameKey="4" type="1">
            <ResourceIdentifier key="thing_id" nameKey="5" required="true" identType="1"/>
        </ResourceKind>
    </ResourceKinds>
    <LicenseConfig enabled="false"/>
</AdapterKind>
"""

_PROPERTIES = """1=Test Adapter
2=Test Adapter Instance
3=Host
4=Test Thing
5=Thing ID
"""

_ADAPTER_YAML = """name: "Test Adapter"
version: "1.0.0"
build_number: 7
adapter_kind: "test_adapter"
tier: 2
description: "Fixture adapter for the docs index include."
"""

_EXTRA = """### Pushed onto VMWARE objects

Per-control results, per-vCenter rollups and alerts land on existing
VMWARE resources. See [Data reference](data-reference.md).
"""


def _make_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "adapter"
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(_ADAPTER_YAML, encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE_XML, encoding="utf-8")
    (project_dir / "resources").mkdir()
    (project_dir / "resources" / "resources.properties").write_text(_PROPERTIES, encoding="utf-8")
    return project_dir


def _readme(project_dir: Path) -> str:
    return (project_dir / "docs" / "README.md").read_text(encoding="utf-8")


class TestIndexExtraAbsent:
    def test_readme_unchanged_without_include(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        results = generate_docset(project_dir)
        model = build_doc_model(project_dir)
        # Same text the pre-#171 one-argument call produced.
        assert _readme(project_dir) == generate_readme_md(model)
        assert INDEX_EXTRA_HEADING not in _readme(project_dir)
        assert f"docs/{INDEX_EXTRA_FILENAME}" not in results

    def test_blank_include_is_ignored(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        (project_dir / "docs").mkdir()
        (project_dir / "docs" / INDEX_EXTRA_FILENAME).write_text("\n  \n", encoding="utf-8")
        generate_docset(project_dir)
        assert INDEX_EXTRA_HEADING not in _readme(project_dir)


class TestIndexExtraMerged:
    def test_include_merged_under_stable_heading(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        (project_dir / "docs").mkdir()
        (project_dir / "docs" / INDEX_EXTRA_FILENAME).write_text(_EXTRA, encoding="utf-8")

        results = generate_docset(project_dir)
        readme = _readme(project_dir)

        assert results[f"docs/{INDEX_EXTRA_FILENAME}"] == "merged"
        assert readme.count(INDEX_EXTRA_HEADING) == 1
        assert _EXTRA.strip() in readme
        # After the generated sections, not in place of them.
        assert readme.index("## Quick Reference") < readme.index(INDEX_EXTRA_HEADING)
        assert readme.index(INDEX_EXTRA_HEADING) < readme.index("### Pushed onto VMWARE objects")
        assert readme.endswith("\n") and not readme.endswith("\n\n")

    def test_include_survives_rebuilds_and_is_not_written(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        (project_dir / "docs").mkdir()
        include = project_dir / "docs" / INDEX_EXTRA_FILENAME
        include.write_text(_EXTRA, encoding="utf-8")

        generate_docset(project_dir)
        first = _readme(project_dir)
        generate_docset(project_dir)
        generate_docset(project_dir)

        assert _readme(project_dir) == first
        assert include.read_text(encoding="utf-8") == _EXTRA

    def test_edit_to_include_flows_into_next_build(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        (project_dir / "docs").mkdir()
        include = project_dir / "docs" / INDEX_EXTRA_FILENAME
        include.write_text(_EXTRA, encoding="utf-8")
        generate_docset(project_dir)

        include.write_text("### Changed\n\nNew text.\n", encoding="utf-8")
        generate_docset(project_dir)
        readme = _readme(project_dir)
        assert "### Changed" in readme
        assert "### Pushed onto VMWARE objects" not in readme

    def test_generated_section_carries_no_em_dash(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        (project_dir / "docs").mkdir()
        (project_dir / "docs" / INDEX_EXTRA_FILENAME).write_text(_EXTRA, encoding="utf-8")
        generate_docset(project_dir)
        assert "—" not in _readme(project_dir)
