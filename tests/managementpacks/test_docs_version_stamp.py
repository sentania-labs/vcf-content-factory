"""Generated docs carry the same version line as the pak (RULE-014).

A dev build-sdk stamps the pak 0.0.0.<build_number>. The docs/ docset used
to re-read adapter.yaml and stamp the declared version (e.g. 1.1.0.14), so
a dev build wrote release-looking docs next to a 0.x pak. build-sdk now
hands the stamped version to generate_docset; the standalone docs-gen
command still uses the declared version.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vcfcf_managementpacks.docs_gen import build_doc_model, generate_docset
from vcfcf_managementpacks.sdk_builder import _generate_docs

_DESCRIBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"
             key="test_adapter" nameKey="1" version="1">
    <ResourceKinds>
        <ResourceKind key="test_adapter" nameKey="2" type="7" monitoringInterval="5">
            <ResourceIdentifier key="host" nameKey="3" required="true" identType="1"/>
        </ResourceKind>
        <ResourceKind key="TestSwitch" nameKey="4" type="1">
            <ResourceIdentifier key="switch_id" nameKey="5" required="true" identType="1"/>
        </ResourceKind>
    </ResourceKinds>
    <LicenseConfig enabled="false"/>
</AdapterKind>
"""

_PROPERTIES = "1=Test Adapter\n2=Test Adapter Instance\n3=Host\n4=Test Switch\n5=Switch ID\n"

_ADAPTER_YAML = """name: "Test Adapter"
version: "1.0.0"
build_number: 1
adapter_kind: "test_adapter"
tier: 2
description: "Test adapter for docs version stamping."
"""


def _make_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "adapter"
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(_ADAPTER_YAML, encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE_XML, encoding="utf-8")
    (project_dir / "resources").mkdir()
    (project_dir / "resources" / "resources.properties").write_text(
        _PROPERTIES, encoding="utf-8"
    )
    return project_dir


def _docset_text(project_dir: Path) -> tuple[str, str]:
    docs = project_dir / "docs"
    return (
        (docs / "README.md").read_text(encoding="utf-8"),
        (docs / "inventory-tree.md").read_text(encoding="utf-8"),
    )


def test_docset_defaults_to_declared_version(tmp_path: Path) -> None:
    project_dir = _make_project(tmp_path)
    generate_docset(project_dir)
    readme, tree = _docset_text(project_dir)
    assert "**Version:** 1.0.0.1" in readme
    assert "v1.0.0.1." in tree


def test_docset_override_stamps_given_version(tmp_path: Path) -> None:
    project_dir = _make_project(tmp_path)
    assert build_doc_model(project_dir, adapter_version="0.0.0.1").adapter_version == "0.0.0.1"
    generate_docset(project_dir, adapter_version="0.0.0.1")
    readme, tree = _docset_text(project_dir)
    assert "**Version:** 0.0.0.1" in readme
    assert "v0.0.0.1." in tree
    assert "1.0.0.1" not in readme + tree


@pytest.mark.parametrize("stamped", ["0.0.0.1", "1.0.0.1"])
def test_build_docs_use_stamped_version(tmp_path: Path, stamped: str) -> None:
    """build-sdk's doc step stamps the REGENERATED surfaces (docs/README.md,
    docs/inventory-tree.md, REFERENCE.generated.md) with the pak version."""
    project_dir = _make_project(tmp_path)
    (project_dir / "REFERENCE.md").write_text("hand-authored\n", encoding="utf-8")
    _generate_docs(project_dir, stamped)
    readme, tree = _docset_text(project_dir)
    assert f"**Version:** {stamped}" in readme
    assert f"v{stamped}." in tree
    generated = (project_dir / "REFERENCE.generated.md").read_text(encoding="utf-8")
    assert f"for build {stamped}." in generated
    assert (project_dir / "REFERENCE.md").read_text(encoding="utf-8") == "hand-authored\n"


def test_first_dev_build_write_once_files_carry_no_version(tmp_path: Path) -> None:
    """Write-once files carry no build version at all.

    Codex P2 on #188: docs/overview.md, docs/installing.md and the first-run
    REFERENCE.md are never rewritten, so a dev stamp (0.0.0.N) written by a
    project's first build would go stale. framework-reviewer round 2: the
    declared 1.x version is no answer either, since RULE-014 forbids a 1.x
    stamp from a local build. So neither version appears in them, while the
    regenerated docs/README.md still shows the dev stamp.
    """
    project_dir = _make_project(tmp_path)
    docs = project_dir / "docs"

    _generate_docs(project_dir, "0.0.0.1")
    readme, tree = _docset_text(project_dir)
    assert "**Version:** 0.0.0.1" in readme
    assert "v0.0.0.1." in tree
    overview = (docs / "overview.md").read_text(encoding="utf-8")
    installing = (docs / "installing.md").read_text(encoding="utf-8")
    reference = (project_dir / "REFERENCE.md").read_text(encoding="utf-8")
    assert "docs/README.md" in overview  # points readers at the version
    assert "for build" not in reference
    for text in (overview, installing, reference):
        assert "0.0.0.1" not in text
        assert "1.0.0.1" not in text

    _generate_docs(project_dir, "1.0.0.1")  # later release build
    readme, tree = _docset_text(project_dir)
    assert "**Version:** 1.0.0.1" in readme
    assert (docs / "overview.md").read_text(encoding="utf-8") == overview
    assert (docs / "installing.md").read_text(encoding="utf-8") == installing
    assert (project_dir / "REFERENCE.md").read_text(encoding="utf-8") == reference


def test_docset_scaffolds_carry_no_version(tmp_path: Path) -> None:
    project_dir = _make_project(tmp_path)
    results = generate_docset(project_dir, adapter_version="0.0.0.1")
    assert results["docs/overview.md"] == "scaffolded"
    docs = project_dir / "docs"
    for name in ("overview.md", "installing.md"):
        text = (docs / name).read_text(encoding="utf-8")
        assert "0.0.0.1" not in text and "1.0.0.1" not in text
