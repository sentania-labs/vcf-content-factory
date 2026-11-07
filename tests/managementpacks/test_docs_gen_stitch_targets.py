"""Tests for the stitch_targets adapter.yaml stanza (factory #310).

Covers:
  1. Regression: a pak without the stanza gets byte-identical docs, checked
     against docsets captured before the stanza existed
     (tests/fixtures/sdk_adapters/docs_gen_baseline/<pak>/expected/).
  2. Stanza present: "Metrics Pushed Onto" section in docs/README.md,
     docs/inventory-tree.md and the docs/overview.md scaffold; quick-reference
     line; targets drawn into the SVG and Excalidraw diagrams as dashed
     external nodes with a dashed "pushes keys" edge from the adapter
     instance.
  3. Invalid stanza: clear SdkProjectError from load_sdk_project, the same
     message through validate-sdk and docs-gen.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from vcfcf_managementpacks.docs_gen import (
    DocsGenError,
    build_doc_model,
    generate_docset,
    generate_excalidraw,
    generate_inventory_tree_md,
    generate_overview_md,
    generate_readme_md,
    generate_svg,
)
from vcfcf_managementpacks.sdk_builder import validate_sdk_project
from vcfcf_managementpacks.sdk_project import SdkProjectError, load_sdk_project


_BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "sdk_adapters" / "docs_gen_baseline"
_BASELINE_PAKS = ("tree_pak", "stitch_only_pak")

_STANZA = """stitch_targets:
  - adapter_kind: VMWARE
    resource_kind: HostSystem
    identity: "VMEntityObjectID + VMEntityVCID"
    instanced_by: "<vmnic> = vSAN physical NIC"
    key_groups:
      - "vSAN Perf|DOM Owner|*"
      - "vSAN Perf|pNIC:<vmnic>|*"
  - adapter_kind: VMWARE
    resource_kind: ClusterComputeResource
    identity: "VMEntityObjectID + VMEntityVCID"
    key_groups:
      - "vSAN Perf|Capacity|*"
"""


def _copy_pak(tmp_path: Path, pak: str, extra: str = "") -> Path:
    dest = tmp_path / pak
    shutil.copytree(_BASELINE / pak, dest, ignore=shutil.ignore_patterns("expected"))
    if extra:
        with (dest / "adapter.yaml").open("a", encoding="utf-8") as fh:
            fh.write(extra)
    return dest


# ---------------------------------------------------------------------------
# 1. Regression: no stanza, no change
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pak", _BASELINE_PAKS)
def test_docset_without_stanza_is_byte_identical_to_baseline(tmp_path: Path, pak: str) -> None:
    project = _copy_pak(tmp_path, pak)
    generate_docset(project)
    expected_dir = _BASELINE / pak / "expected"
    expected = sorted(p.name for p in expected_dir.iterdir())
    actual = sorted(p.name for p in (project / "docs").iterdir())
    assert actual == expected
    for name in expected:
        assert (project / "docs" / name).read_bytes() == (expected_dir / name).read_bytes(), name


def test_interior_space_in_resource_kind_is_allowed(tmp_path: Path) -> None:
    stanza = (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: \"VMwareAdapter Instance\"\n"
        "    identity: VMEntityVCID\n    key_groups: [\"X|*\"]\n"
    )
    project = _copy_pak(tmp_path, "stitch_only_pak", stanza)
    targets = load_sdk_project(project / "adapter.yaml").stitch_targets
    assert targets[0].resource_kind == "VMwareAdapter Instance"
    assert "### VMwareAdapter Instance (VMWARE)" in generate_readme_md(build_doc_model(project))


def test_model_without_stanza_has_no_targets(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak")
    assert build_doc_model(project).stitch_targets == []
    assert load_sdk_project(project / "adapter.yaml").stitch_targets == []


# ---------------------------------------------------------------------------
# 2. Stanza rendered
# ---------------------------------------------------------------------------

def test_loader_parses_stanza(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak", _STANZA)
    targets = load_sdk_project(project / "adapter.yaml").stitch_targets
    assert [(t.adapter_kind, t.resource_kind) for t in targets] == [
        ("VMWARE", "HostSystem"), ("VMWARE", "ClusterComputeResource"),
    ]
    assert targets[0].key_groups == ["vSAN Perf|DOM Owner|*", "vSAN Perf|pNIC:<vmnic>|*"]
    assert targets[0].instanced_by == "<vmnic> = vSAN physical NIC"
    assert targets[1].instanced_by == ""


def test_readme_renders_section_and_quick_reference(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak", _STANZA)
    readme = generate_readme_md(build_doc_model(project))
    assert "## Metrics Pushed Onto" in readme
    assert "### HostSystem (VMWARE)" in readme
    assert "### ClusterComputeResource (VMWARE)" in readme
    assert "- **Matched on:** VMEntityObjectID + VMEntityVCID" in readme
    # placeholders escaped in prose, pipes escaped in table cells
    assert "- **Instanced by:** \\<vmnic\\> = vSAN physical NIC" in readme
    assert "| `vSAN Perf\\|pNIC:<vmnic>\\|*` |" in readme
    assert (
        "- **Metrics pushed onto:** HostSystem (VMWARE), ClusterComputeResource (VMWARE) "
        "(see [Metrics Pushed Onto](#metrics-pushed-onto))"
    ) in readme
    # section sits between the diagram and the quick reference
    assert readme.index("![Inventory Tree]") < readme.index("## Metrics Pushed Onto") < readme.index("## Quick Reference")


def test_readme_with_cross_mp_and_stitch_keeps_both(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "tree_pak", _STANZA)
    readme = generate_readme_md(build_doc_model(project))
    assert readme.index("## Cross-MP Relationships") < readme.index("## Metrics Pushed Onto")
    assert "\n\n## Metrics Pushed Onto\n" in readme
    assert "- **Cross-MP relationships:** 1" in readme
    assert "- **Metrics pushed onto:** " in readme


def test_inventory_tree_md_and_overview_scaffold(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak", _STANZA)
    model = build_doc_model(project)
    assert "## Metrics Pushed Onto" in generate_inventory_tree_md(model)
    overview = generate_overview_md(model)
    assert overview.index("## Metrics Pushed Onto") < overview.index("## Cross-Adapter Notes")
    assert "\n\n## Cross-Adapter Notes" in overview


def test_svg_draws_targets_with_dashed_edges(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak", _STANZA)
    svg = generate_svg(build_doc_model(project))
    assert 'id="arrow-stitch"' in svg
    assert svg.count('marker-end="url(#arrow-stitch)"') == 2
    assert svg.count(">pushes keys</text>") == 2
    assert ">HostSystem</text>" in svg and ">ClusterComputeResource</text>" in svg
    assert ">Baseline Stitch Instance</text>" in svg
    assert "vSAN Perf|pNIC:&lt;vmnic&gt;|*" in svg
    assert ">Baseline Collector</text>" in svg  # own kinds still drawn


def test_svg_instance_only_pak_is_not_the_empty_placeholder(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak", _STANZA)
    describe = project / "describe.xml"
    text = describe.read_text(encoding="utf-8")
    start = text.index('        <ResourceKind key="BaselineCollector"')
    end = text.index("</ResourceKind>", start) + len("</ResourceKind>\n")
    describe.write_text(text[:start] + text[end:], encoding="utf-8")
    model = build_doc_model(project)
    assert [k.key for k in model.kinds] == ["baseline_stitch"]
    svg = generate_svg(model)
    assert "No traversal spec found." not in svg
    assert svg.count(">pushes keys</text>") == 2


def test_excalidraw_draws_dashed_external_nodes(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "stitch_only_pak", _STANZA)
    elements = generate_excalidraw(build_doc_model(project))["elements"]
    rects = [e for e in elements if e["type"] == "rectangle"]
    dashed_rects = [e for e in rects if e["strokeStyle"] == "dashed"]
    assert [r["label"]["text"].split("\n")[0] for r in dashed_rects] == [
        "HostSystem", "ClusterComputeResource",
    ]
    arrows = [e for e in elements if e["type"] == "arrow" and e["strokeStyle"] == "dashed"]
    assert len(arrows) == 2
    rect_ids = {r["id"] for r in dashed_rects}
    assert {a["endBinding"]["elementId"] for a in arrows} == rect_ids
    labels = [e for e in elements if e["type"] == "text" and e["text"] == "pushes keys"]
    assert len(labels) == 2
    assert len({e["id"] for e in elements}) == len(elements)  # ids unique


def test_same_resource_kind_under_two_adapter_kinds(tmp_path: Path) -> None:
    stanza = (
        "stitch_targets:\n"
        "  - adapter_kind: VMWARE\n    resource_kind: Datastore\n"
        "    identity: x\n    key_groups: [\"A|*\"]\n"
        "  - adapter_kind: OTHER\n    resource_kind: Datastore\n"
        "    identity: y\n    key_groups: [\"B|*\"]\n"
    )
    project = _copy_pak(tmp_path, "stitch_only_pak", stanza)
    model = build_doc_model(project)
    readme = generate_readme_md(model)
    assert "### Datastore (VMWARE)" in readme
    assert "### Datastore (OTHER)" in readme
    assert "- **Metrics pushed onto:** Datastore (VMWARE), Datastore (OTHER) " in readme
    elements = generate_excalidraw(model)["elements"]
    dashed = [e for e in elements if e["type"] == "rectangle" and e["strokeStyle"] == "dashed"]
    assert len(dashed) == 2
    assert len({e["id"] for e in dashed}) == 2
    assert len({e["id"] for e in elements}) == len(elements)
    arrows = [e for e in elements if e["type"] == "arrow" and e["strokeStyle"] == "dashed"]
    assert {a["endBinding"]["elementId"] for a in arrows} == {e["id"] for e in dashed}
    svg = generate_svg(model)
    assert svg.count(">Datastore</text>") == 2
    assert svg.count('marker-end="url(#arrow-stitch)"') == 2


def test_svg_and_markdown_escape_special_characters(tmp_path: Path) -> None:
    stanza = (
        "stitch_targets:\n"
        "  - adapter_kind: VMWARE\n    resource_kind: \"R&D \\\"Kind\\\"\"\n"
        "    identity: \"*id* _x_ `y` [z](w) <m>\"\n"
        "    key_groups: [\"A & \\\"B\\\"|<i>|*\"]\n"
    )
    project = _copy_pak(tmp_path, "stitch_only_pak", stanza)
    model = build_doc_model(project)
    assert model.stitch_targets[0].resource_kind == 'R&D "Kind"'
    svg = generate_svg(model)
    assert ">R&amp;D &quot;Kind&quot;</text>" in svg
    assert ">A &amp; &quot;B&quot;|&lt;i&gt;|*</text>" in svg
    assert 'R&D "' not in svg
    readme = generate_readme_md(model)
    assert "- **Matched on:** \\*id\\* \\_x\\_ \\`y\\` \\[z\\](w) \\<m\\>" in readme
    assert '| `A & "B"\\|<i>\\|*` |' in readme
    json.loads(json.dumps(generate_excalidraw(model)))


def test_docset_with_stanza_is_deterministic(tmp_path: Path) -> None:
    project = _copy_pak(tmp_path, "tree_pak", _STANZA)
    generate_docset(project)
    first = {p.name: p.read_bytes() for p in (project / "docs").iterdir()}
    for name in ("README.md", "inventory-tree.md", "inventory-tree.svg", "inventory-tree.excalidraw"):
        (project / "docs" / name).unlink()
    generate_docset(project)
    second = {p.name: p.read_bytes() for p in (project / "docs").iterdir()}
    assert first == second
    json.loads(first["inventory-tree.excalidraw"])


# ---------------------------------------------------------------------------
# 3. Validation
# ---------------------------------------------------------------------------

_ENTRY_OK = (
    "  - adapter_kind: VMWARE\n"
    "    resource_kind: HostSystem\n"
    "    identity: \"MoRef + vCenter UUID\"\n"
    "    key_groups: [\"X|*\"]\n"
)

_BAD = {
    "not_a_list": ("stitch_targets: VMWARE\n", "'stitch_targets' must be a list"),
    "entry_not_mapping": ("stitch_targets:\n  - HostSystem\n", "stitch_targets[0]: must be a mapping"),
    "unknown_key": (
        "stitch_targets:\n" + _ENTRY_OK + "    colour: red\n",
        "unknown key(s) ['colour']",
    ),
    "missing_identity": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: HostSystem\n"
        "    key_groups: [\"X|*\"]\n",
        "missing required field(s) ['identity']",
    ),
    "blank_resource_kind": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: \" \"\n"
        "    identity: x\n    key_groups: [\"X|*\"]\n",
        "'resource_kind' must be a non-empty string",
    ),
    "empty_key_groups": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: HostSystem\n"
        "    identity: x\n    key_groups: []\n",
        "'key_groups' must be a non-empty list",
    ),
    "non_string_group": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: HostSystem\n"
        "    identity: x\n    key_groups: [\"X|*\", 3]\n",
        "key_groups[1] must be a non-empty string",
    ),
    "duplicate_group": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: HostSystem\n"
        "    identity: x\n    key_groups: [\"X|*\", \"X|*\"]\n",
        "key_groups lists 'X|*' twice",
    ),
    "own_adapter_kind": (
        "stitch_targets:\n  - adapter_kind: baseline_stitch\n    resource_kind: BaselineCollector\n"
        "    identity: x\n    key_groups: [\"X|*\"]\n",
        "is this pak's own adapter_kind",
    ),
    "duplicate_target": (
        "stitch_targets:\n" + _ENTRY_OK + _ENTRY_OK,
        "stitch_targets[1]: VMWARE HostSystem is already listed",
    ),
    "pipe_in_resource_kind": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: \"Host|System\"\n"
        "    identity: x\n    key_groups: [\"X|*\"]\n",
        "'resource_kind' may not contain",
    ),
    "angle_in_adapter_kind": (
        "stitch_targets:\n  - adapter_kind: \"<VMWARE>\"\n    resource_kind: HostSystem\n"
        "    identity: x\n    key_groups: [\"X|*\"]\n",
        "'adapter_kind' may not contain",
    ),
    "tab_in_resource_kind": (
        "stitch_targets:\n  - adapter_kind: VMWARE\n    resource_kind: \"Host\\tSystem\"\n"
        "    identity: x\n    key_groups: [\"X|*\"]\n",
        "'resource_kind' may not contain",
    ),
    "instanced_by_not_string": (
        "stitch_targets:\n" + _ENTRY_OK + "    instanced_by: [a]\n",
        "'instanced_by' must be a string",
    ),
}


@pytest.mark.parametrize("case", sorted(_BAD))
def test_invalid_stanza_rejected_everywhere(tmp_path: Path, case: str) -> None:
    stanza, message = _BAD[case]
    project = _copy_pak(tmp_path, "stitch_only_pak", stanza)

    with pytest.raises(SdkProjectError) as exc:
        load_sdk_project(project / "adapter.yaml")
    assert message in str(exc.value)

    errors = validate_sdk_project(project)
    assert any(e.startswith("adapter.yaml validation error:") and message in e for e in errors), errors

    with pytest.raises(DocsGenError) as exc:
        generate_docset(project)
    assert message in str(exc.value)
