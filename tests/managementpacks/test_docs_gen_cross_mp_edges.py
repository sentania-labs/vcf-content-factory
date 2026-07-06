"""Tests for the cross_mp_edges adapter.yaml stanza in docs_gen.py.

Covers:
  1. Stanza absent → generated docs/README.md and docs/inventory-tree.md are
     byte-identical to the no-stanza baseline (zero churn for packs without
     cross-MP stitches).
  2. Stanza present → rendered into both docs/README.md ("Cross-MP
     Relationships" section) and docs/inventory-tree.md, with the foreign
     endpoint visually distinguished (italics + "(foreign, <kind>)").
  3. Invalid stanza (unknown key, missing required field, bad direction
     value) → raises a clear validation error, surfaced identically by
     docs-gen and by validate-sdk (both go through
     vcfops_managementpacks.sdk_project._parse_cross_mp_edges /
     SdkProjectError).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vcfops_managementpacks.docs_gen import (
    DocsGenError,
    build_doc_model,
    generate_docset,
    generate_inventory_tree_md,
    generate_readme_md,
)
from vcfops_managementpacks.sdk_project import SdkProjectError


_DESCRIBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             key="test_adapter"
             nameKey="1"
             version="1"
             xsi:schemaLocation="http://schemas.vmware.com/vcops/schema describeSchema.xsd">
    <ResourceKinds>
        <ResourceKind key="test_adapter" nameKey="2" type="7" monitoringInterval="5">
            <ResourceIdentifier key="host" nameKey="3" required="true" identType="1"/>
        </ResourceKind>
        <ResourceKind key="TestSwitch" nameKey="4" type="1">
            <ResourceIdentifier key="switch_id" nameKey="5" required="true" identType="1"/>
        </ResourceKind>
        <ResourceKind key="TestSwitchPort" nameKey="6" type="1">
            <ResourceIdentifier key="port_key" nameKey="7" required="true" identType="1"/>
        </ResourceKind>
    </ResourceKinds>

    <ResourceTypeAttributes>
        <TraversalSpecKinds>
            <TraversalSpecKind name="Test Traversal" nameKey="8">
                <ResourcePath path="test_adapter::TestSwitch||test_adapter::TestSwitchPort::child"/>
            </TraversalSpecKind>
        </TraversalSpecKinds>
    </ResourceTypeAttributes>

    <LicenseConfig enabled="false"/>
</AdapterKind>
"""

_PROPERTIES = """1=Test Adapter
2=Test Adapter Instance
3=Host
4=Test Switch
5=Switch ID
6=Test Switch Port
7=Port Key
8=Test Traversal
"""

_ADAPTER_YAML_BASE = """name: "Test Adapter"
version: "1.0.0"
build_number: 1
adapter_kind: "test_adapter"
tier: 2
description: "Test adapter for docs-gen cross_mp_edges coverage."
"""

_CROSS_MP_STANZA = """cross_mp_edges:
  - parent: "VMWARE HostSystem"
    child: TestSwitchPort
    direction: parent_foreign
    foreign_adapter_kind: VMWARE
    description: "Per-vmnic LLDP join via Suite API; additive, optional"
"""


def _make_project(tmp_path: Path, adapter_yaml_extra: str = "") -> Path:
    project_dir = tmp_path / "adapter"
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(_ADAPTER_YAML_BASE + adapter_yaml_extra, encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE_XML, encoding="utf-8")
    resources_dir = project_dir / "resources"
    resources_dir.mkdir()
    (resources_dir / "resources.properties").write_text(_PROPERTIES, encoding="utf-8")
    return project_dir


class TestCrossMpEdgesAbsent:
    """No cross_mp_edges key → zero churn vs. the pre-existing baseline output."""

    def test_readme_and_tree_unaffected(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        model = build_doc_model(project_dir)
        assert model.cross_mp_edges == []

        readme = generate_readme_md(model)
        tree_md = generate_inventory_tree_md(model)

        assert "Cross-MP Relationships" not in readme
        assert "Cross-MP relationships" not in readme  # quick-reference line too
        assert "Cross-MP Relationships" not in tree_md

    def test_generate_docset_idempotent_without_stanza(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path)
        generate_docset(project_dir)
        readme_first = (project_dir / "docs" / "README.md").read_text(encoding="utf-8")
        tree_first = (project_dir / "docs" / "inventory-tree.md").read_text(encoding="utf-8")

        generate_docset(project_dir)
        readme_second = (project_dir / "docs" / "README.md").read_text(encoding="utf-8")
        tree_second = (project_dir / "docs" / "inventory-tree.md").read_text(encoding="utf-8")

        assert readme_first == readme_second
        assert tree_first == tree_second


class TestCrossMpEdgesRendered:
    """cross_mp_edges present → rendered into both README.md and inventory-tree.md."""

    def test_readme_contains_section_and_foreign_annotation(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path, _CROSS_MP_STANZA)
        model = build_doc_model(project_dir)
        assert len(model.cross_mp_edges) == 1

        readme = generate_readme_md(model)
        assert "## Cross-MP Relationships" in readme
        assert "*VMWARE HostSystem* (foreign, VMWARE)" in readme
        assert "`TestSwitchPort`" in readme
        assert "Per-vmnic LLDP join via Suite API; additive, optional" in readme
        assert "**Cross-MP relationships:** 1" in readme

    def test_inventory_tree_contains_section_and_foreign_annotation(self, tmp_path: Path) -> None:
        project_dir = _make_project(tmp_path, _CROSS_MP_STANZA)
        model = build_doc_model(project_dir)

        tree_md = generate_inventory_tree_md(model)
        assert "## Cross-MP Relationships" in tree_md
        assert "*VMWARE HostSystem* (foreign, VMWARE)" in tree_md
        assert "`TestSwitchPort`" in tree_md

    def test_child_foreign_direction_annotates_child_instead(self, tmp_path: Path) -> None:
        stanza = """cross_mp_edges:
  - parent: TestSwitch
    child: "VMWARE VirtualMachine"
    direction: child_foreign
    foreign_adapter_kind: VMWARE
    description: "Reverse-direction example"
"""
        project_dir = _make_project(tmp_path, stanza)
        model = build_doc_model(project_dir)

        readme = generate_readme_md(model)
        assert "`TestSwitch`" in readme
        assert "*VMWARE VirtualMachine* (foreign, VMWARE)" in readme


class TestCrossMpEdgesInvalid:
    """Malformed stanza → clear SdkProjectError, not a silent drop."""

    def test_missing_required_field(self, tmp_path: Path) -> None:
        stanza = """cross_mp_edges:
  - parent: "VMWARE HostSystem"
"""
        project_dir = _make_project(tmp_path, stanza)
        with pytest.raises((SdkProjectError, DocsGenError)) as exc_info:
            build_doc_model(project_dir)
        assert "missing required field" in str(exc_info.value)

    def test_unknown_key(self, tmp_path: Path) -> None:
        stanza = """cross_mp_edges:
  - parent: "VMWARE HostSystem"
    child: TestSwitchPort
    bogus_field: true
"""
        project_dir = _make_project(tmp_path, stanza)
        with pytest.raises((SdkProjectError, DocsGenError)) as exc_info:
            build_doc_model(project_dir)
        assert "unknown key" in str(exc_info.value)

    def test_invalid_direction(self, tmp_path: Path) -> None:
        stanza = """cross_mp_edges:
  - parent: "VMWARE HostSystem"
    child: TestSwitchPort
    direction: sideways
"""
        project_dir = _make_project(tmp_path, stanza)
        with pytest.raises((SdkProjectError, DocsGenError)) as exc_info:
            build_doc_model(project_dir)
        assert "direction" in str(exc_info.value)

    def test_not_a_list(self, tmp_path: Path) -> None:
        stanza = "cross_mp_edges: \"not a list\"\n"
        project_dir = _make_project(tmp_path, stanza)
        with pytest.raises((SdkProjectError, DocsGenError)) as exc_info:
            build_doc_model(project_dir)
        assert "must be a list" in str(exc_info.value)

    def test_generate_docset_surfaces_docs_gen_error(self, tmp_path: Path) -> None:
        stanza = """cross_mp_edges:
  - parent: "VMWARE HostSystem"
    child: TestSwitchPort
    direction: sideways
"""
        project_dir = _make_project(tmp_path, stanza)
        with pytest.raises(DocsGenError):
            generate_docset(project_dir)
