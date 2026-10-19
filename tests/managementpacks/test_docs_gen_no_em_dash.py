"""Generated SDK pak docs carry no em-dash (U+2014). Issues #194 and #225.

The no-em-dash writing rule binds generated output too. Every Tier 2 pak
carries whatever the docset generator writes (docs/*.md, the SVG and
Excalidraw diagrams) plus the REFERENCE.md / README.md the build writes, and
a hand edit is overwritten on the next build, so the fixed text and the
blank-cell placeholders must be clean at the source.

The fixture is built to exercise every placeholder path: a kind with no
identifiers and no parents, an identifier with no default, a metric with no
unit, a property (monitored column placeholder), and a cross-MP edge with no
description. A second fixture has no type="7" adapter-instance kind, which
is the only path to the installing.md "No adapter instance kind found" row.
"""
from __future__ import annotations

from pathlib import Path

from vcfcf_managementpacks.docs_gen import generate_docset
from vcfcf_managementpacks.sdk_builder import _generate_docs

EM_DASH = "\u2014"

_DESCRIBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"
             key="test_adapter" nameKey="1" version="1">
    <ResourceKinds>
        <ResourceKind key="test_adapter" nameKey="2" type="7" monitoringInterval="5">
            <ResourceIdentifier key="host" nameKey="3" required="true" identType="1"/>
            <ResourceIdentifier key="port" nameKey="9" required="false" identType="2"/>
        </ResourceKind>
        <ResourceKind key="TestSwitch" nameKey="4" type="1">
            <ResourceIdentifier key="switch_id" nameKey="5" required="true" identType="1"/>
            <ResourceGroup key="stats" nameKey="10">
                <ResourceAttribute key="packets" nameKey="11" dataType="float"
                                   isProperty="false" defaultMonitored="false"/>
                <ResourceAttribute key="model" nameKey="12" dataType="string"
                                   isProperty="true"/>
            </ResourceGroup>
        </ResourceKind>
        <ResourceKind key="TestSwitchPort" nameKey="6" type="1">
            <ResourceIdentifier key="port_key" nameKey="7" required="true" identType="1"/>
        </ResourceKind>
        <ResourceKind key="TestOrphan" nameKey="13" type="1"/>
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

_PROPERTIES = (
    "1=Test Adapter\n2=Test Adapter Instance\n3=Host\n4=Test Switch\n"
    "5=Switch ID\n6=Test Switch Port\n7=Port Key\n8=Test Traversal\n9=Port\n"
    "10=Stats\n11=Packets\n12=Model\n13=Test Orphan\n"
)

_ADAPTER_YAML = """name: "Test Adapter"
version: "1.0.0"
build_number: 1
adapter_kind: "test_adapter"
tier: 2
description: "Test adapter for the no-em-dash docs check."
cross_mp_edges:
  - parent: "VMWARE HostSystem"
    child: TestSwitchPort
    direction: parent_foreign
    foreign_adapter_kind: VMWARE
"""


_NO_INSTANCE_DESCRIBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"
             key="test_adapter" nameKey="1" version="1">
    <ResourceKinds>
        <ResourceKind key="TestSwitch" nameKey="4" type="1">
            <ResourceIdentifier key="switch_id" nameKey="5" required="true" identType="1"/>
        </ResourceKind>
    </ResourceKinds>
    <LicenseConfig enabled="false"/>
</AdapterKind>
"""

_NO_INSTANCE_ROW = "| - | - | - | - | No adapter instance kind found |"


def _make_project(
    tmp_path: Path,
    describe_xml: str = _DESCRIBE_XML,
    adapter_yaml: str = _ADAPTER_YAML,
) -> Path:
    project_dir = tmp_path / "adapter"
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(adapter_yaml, encoding="utf-8")
    (project_dir / "describe.xml").write_text(describe_xml, encoding="utf-8")
    (project_dir / "resources").mkdir()
    (project_dir / "resources" / "resources.properties").write_text(
        _PROPERTIES, encoding="utf-8"
    )
    return project_dir


def _generated_files(project_dir: Path) -> dict[str, str]:
    inputs = {"adapter.yaml", "describe.xml", "resources/resources.properties"}
    out = {}
    for path in sorted(project_dir.rglob("*")):
        rel = path.relative_to(project_dir).as_posix()
        if path.is_file() and rel not in inputs:
            out[rel] = path.read_text(encoding="utf-8")
    return out


def _assert_no_em_dash(files: dict[str, str]) -> None:
    offenders = [
        f"{name}:{lineno}: {line}"
        for name, text in files.items()
        for lineno, line in enumerate(text.splitlines(), 1)
        if EM_DASH in line
    ]
    assert not offenders, "em-dash in generated docs:\n" + "\n".join(offenders)


def test_docset_has_no_em_dash(tmp_path: Path) -> None:
    project_dir = _make_project(tmp_path)
    generate_docset(project_dir)
    files = _generated_files(project_dir)
    for expected in (
        "docs/README.md",
        "docs/inventory-tree.md",
        "docs/inventory-tree.svg",
        "docs/inventory-tree.excalidraw",
        "docs/overview.md",
        "docs/installing.md",
    ):
        assert expected in files
    # The placeholder paths really were hit, so the check is not vacuous.
    tree = files["docs/inventory-tree.md"]
    assert "| `TestOrphan` | Test Orphan | - | - |" in tree
    assert "Do not edit: regenerated on every build." in tree
    assert "Cross-MP Relationships" in files["docs/README.md"]
    _assert_no_em_dash(files)


def test_build_docs_have_no_em_dash_first_and_later_runs(tmp_path: Path) -> None:
    """build-sdk's doc step: first run writes REFERENCE.md and README.md
    directly; a later run writes REFERENCE.generated.md beside the
    hand-authored file. Both shapes must be clean."""
    project_dir = _make_project(tmp_path)
    _generate_docs(project_dir, "0.0.0.1")
    first = _generated_files(project_dir)
    assert "REFERENCE.md" in first and "README.md" in first
    assert "| Port | `port` | - | No |" in first["REFERENCE.md"]
    _assert_no_em_dash(first)

    _generate_docs(project_dir, "0.0.0.2")
    second = _generated_files(project_dir)
    assert "REFERENCE.generated.md" in second
    _assert_no_em_dash(second)


def test_docset_without_adapter_instance_kind_has_no_em_dash(tmp_path: Path) -> None:
    """No type="7" kind: installing.md emits its "no adapter instance" row,
    whose cells are placeholders. The row must be emitted and clean."""
    adapter_yaml = _ADAPTER_YAML.split("cross_mp_edges:")[0]
    project_dir = _make_project(
        tmp_path, describe_xml=_NO_INSTANCE_DESCRIBE_XML, adapter_yaml=adapter_yaml
    )
    generate_docset(project_dir)
    files = _generated_files(project_dir)
    assert _NO_INSTANCE_ROW in files["docs/installing.md"].splitlines()
    _assert_no_em_dash(files)
