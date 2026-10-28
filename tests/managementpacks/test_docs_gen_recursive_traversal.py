"""Tests for traversal rendering in docs_gen.py: /recursive and /preferred
ResourcePath modifiers, multi-parent tree references, and diagram routing of
edges whose child is not in the row below the parent.

The vendor grammar (knowledge/context/cleanroom-spec/spec/07-relationships-cross-mp.md)
lets a ResourcePath segment end in ``/recursive`` (the level repeats, so the
kind nests under itself) and ``/preferred`` (path preference, no topology).
UniFi build 18 review W4: the generator read each segment once, so the
Switch > Switch and AP > AP nesting never reached the tree, the diagram, or
the Parent(s) column.

Covers:
  1. Parsing: /recursive adds the self-edge right after the edge into the
     level; /preferred is stripped; both combine; the kind key is clean.
  2. Paths without modifiers parse to the same consecutive pairs as before,
     and a /preferred-only path renders byte-identical to the bare path.
  3. Tree markdown: one self-nested line per recursive kind, no infinite
     walk (also when the recursive kind is the root); Parent(s) lists self.
  4. Layout and diagrams: the recursive kind keeps its row, roots are
     unaffected, the SVG and Excalidraw outputs draw one self-loop each.
  5. Multi-parent kinds: drawn in full once, with a *(see above)* line under
     every other parent.
  6. Same-row and upward diagram edges: routed through lanes between rows,
     so no horizontal edge segment runs through a node (UniFi Gateway >
     Switch, Synology SSD Cache > Disk shapes).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from vcfcf_managementpacks.docs_gen import (
    _assign_depth,
    _layout_nodes,
    _parse_traversal_paths,
    _tree_roots,
    build_doc_model,
    generate_excalidraw,
    generate_inventory_tree_md,
    generate_svg,
)


_NS = "{http://schemas.vmware.com/vcops/schema}"

_DESCRIBE_TMPL = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema" key="ak" nameKey="1" version="1">
    <ResourceKinds>
        <ResourceKind key="ak" nameKey="2" type="7"/>
        <ResourceKind key="Site" type="1"/>
        <ResourceKind key="Gateway" type="1"/>
        <ResourceKind key="Switch" type="1"/>
        <ResourceKind key="Port" type="1"/>
        <ResourceKind key="AP" type="1"/>
        <ResourceKind key="Radio" type="1"/>
        <ResourceKind key="Pool" type="1"/>
        <ResourceKind key="Volume" type="1"/>
        <ResourceKind key="Cache" type="1"/>
        <ResourceKind key="Disk" type="1"/>
    </ResourceKinds>
    <ResourceTypeAttributes>
        <TraversalSpecKinds>
            <TraversalSpecKind name="Test Traversal">
{paths}
            </TraversalSpecKind>
        </TraversalSpecKinds>
    </ResourceTypeAttributes>
</AdapterKind>
"""

_ADAPTER_YAML = """name: "Test Adapter"
version: "1.0.0"
build_number: 1
adapter_kind: "ak"
tier: 2
"""

_SELF_MARK = "*(recursive: nests under itself)*"


def _paths_xml(paths) -> str:
    return "\n".join(f'                <ResourcePath path="{p}"/>' for p in paths)


def _pairs(paths):
    xml = _DESCRIBE_TMPL.format(paths=_paths_xml(paths)).split("?>", 1)[1]
    spec = next(ET.fromstring(xml).iter(f"{_NS}TraversalSpecKind"))
    return [(e.parent_key, e.child_key) for e in _parse_traversal_paths(spec, _NS)]


def _model(tmp_path: Path, paths, name: str = "adapter"):
    project_dir = tmp_path / name
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(_ADAPTER_YAML, encoding="utf-8")
    (project_dir / "describe.xml").write_text(
        _DESCRIBE_TMPL.format(paths=_paths_xml(paths)), encoding="utf-8"
    )
    return build_doc_model(project_dir)


# UniFi build 18 shape, trimmed.
_UNIFI_LIKE = [
    "ak::Site||ak::Gateway::child||ak::Switch::child/recursive||ak::Port::child",
    "ak::Site||ak::Gateway::child||ak::Switch::child/recursive||ak::AP::child/recursive||ak::Radio::child",
    "ak::Site||ak::Switch::child/recursive||ak::Port::child",
    "ak::Site||ak::AP::child/recursive||ak::Radio::child",
]

# Synology shape: Disk sits under Pool and under Cache, Cache is deeper
# than Disk's shallowest row, so Cache > Disk points up in the diagram.
_SYNOLOGY_LIKE = [
    "ak::Site||ak::Pool::child||ak::Volume::child||ak::Cache::child||ak::Disk::child",
    "ak::Site||ak::Pool::child||ak::Disk::child",
]

_SEE_ABOVE = "*(see above)*"

_PLAIN = [
    "ak::Site||ak::Gateway::child||ak::Switch::child||ak::Port::child",
    "ak::Site||ak::Switch::child||ak::AP::child||ak::Radio::child",
]


class TestParse:
    def test_recursive_adds_self_edge_after_incoming_edge(self) -> None:
        assert _pairs(["ak::Site||ak::Switch::child/recursive||ak::Port::child"]) == [
            ("Site", "Switch"),
            ("Switch", "Switch"),
            ("Switch", "Port"),
        ]

    def test_preferred_is_stripped_without_topology(self) -> None:
        assert _pairs(["ak::Site||ak::Switch::child/preferred||ak::Port::child"]) == [
            ("Site", "Switch"),
            ("Switch", "Port"),
        ]

    def test_recursive_and_preferred_combine_in_either_order(self) -> None:
        expected = [("Site", "Folder"), ("Folder", "Folder"), ("Folder", "Host")]
        assert _pairs(["ak::Site||ak::Folder::child/recursive/preferred||ak::Host::child"]) == expected
        assert _pairs(["ak::Site||ak::Folder::child/preferred/recursive||ak::Host::child"]) == expected

    def test_modifier_on_two_part_segment_leaves_clean_kind_key(self) -> None:
        assert _pairs(["ak::Folder/recursive||ak::Host::child"]) == [
            ("Folder", "Folder"),
            ("Folder", "Host"),
        ]

    def test_unknown_slash_suffix_is_not_stripped(self) -> None:
        # Only the two grammar modifiers are stripped; anything else is left alone.
        assert _pairs(["ak::Site||ak::Switch::child/other"]) == [("Site", "Switch")]
        assert _pairs(["ak::Site||ak::A/B"]) == [("Site", "A/B")]

    def test_self_edge_deduplicated_across_paths(self) -> None:
        pairs = _pairs(_UNIFI_LIKE)
        assert pairs.count(("Switch", "Switch")) == 1
        assert pairs.count(("AP", "AP")) == 1
        assert ("Site", "Switch") in pairs and ("Site", "AP") in pairs

    def test_plain_paths_are_consecutive_pairs(self) -> None:
        assert _pairs(_PLAIN) == [
            ("Site", "Gateway"),
            ("Gateway", "Switch"),
            ("Switch", "Port"),
            ("Site", "Switch"),
            ("Switch", "AP"),
            ("AP", "Radio"),
        ]


class TestNoChurnWithoutRecursive:
    def test_preferred_only_renders_identical_to_bare_paths(self, tmp_path: Path) -> None:
        bare = _model(tmp_path, _PLAIN, "bare")
        preferred = _model(
            tmp_path,
            [p.replace("::Switch::child", "::Switch::child/preferred") for p in _PLAIN],
            "preferred",
        )
        assert generate_inventory_tree_md(bare) == generate_inventory_tree_md(preferred)
        assert generate_svg(bare) == generate_svg(preferred)
        assert generate_excalidraw(bare) == generate_excalidraw(preferred)

    def test_plain_tree_has_no_recursive_marker(self, tmp_path: Path) -> None:
        model = _model(tmp_path, _PLAIN)
        assert "recursive" not in generate_inventory_tree_md(model)

    def test_single_parent_tree_has_no_reference_lines(self, tmp_path: Path) -> None:
        model = _model(tmp_path, ["ak::Site||ak::Gateway::child||ak::Switch::child"])
        assert _SEE_ABOVE not in generate_inventory_tree_md(model)


class TestTreeMarkdown:
    def test_self_nesting_drawn_once_per_recursive_kind(self, tmp_path: Path) -> None:
        tree = generate_inventory_tree_md(_model(tmp_path, _UNIFI_LIKE))
        assert tree.count(f"- **Switch** (`Switch`) {_SELF_MARK}") == 1
        assert tree.count(f"- **AP** (`AP`) {_SELF_MARK}") == 1
        lines = tree.splitlines()
        # The self-nested line sits one level below the kind it repeats.
        sw = next(i for i, l in enumerate(lines) if l.lstrip() == "- **Switch** (`Switch`)")
        assert lines[sw + 1] == "  " + lines[sw] + f" {_SELF_MARK}"

    def test_parents_column_lists_self(self, tmp_path: Path) -> None:
        tree = generate_inventory_tree_md(_model(tmp_path, _UNIFI_LIKE))
        assert "| `Switch` | Switch | - | Gateway, Switch, Site |" in tree
        assert "| `AP` | AP | - | Switch, AP, Site |" in tree

    def test_recursive_root_terminates_and_stays_root(self, tmp_path: Path) -> None:
        model = _model(tmp_path, ["ak::Site/recursive||ak::Gateway::child"])
        assert _tree_roots(model) == ["Site"]
        lines = generate_inventory_tree_md(model).splitlines()
        start = lines.index("## Traversal Tree") + 2
        assert lines[start:start + 3] == [
            "- **Site** (`Site`)",
            f"  - **Site** (`Site`) {_SELF_MARK}",
            "  - **Gateway** (`Gateway`)",
        ]


def _tree_lines(model):
    lines = generate_inventory_tree_md(model).splitlines()
    start = lines.index("## Traversal Tree") + 2
    return lines[start:lines.index("", start)]


class TestMultiParentReferences:
    def test_unifi_shape_shows_every_parent(self, tmp_path: Path) -> None:
        assert _tree_lines(_model(tmp_path, _UNIFI_LIKE)) == [
            "- **Site** (`Site`)",
            "  - **Gateway** (`Gateway`)",
            "    - **Switch** (`Switch`)",
            f"      - **Switch** (`Switch`) {_SELF_MARK}",
            "      - **Port** (`Port`)",
            "      - **AP** (`AP`)",
            f"        - **AP** (`AP`) {_SELF_MARK}",
            "        - **Radio** (`Radio`)",
            f"  - **Switch** (`Switch`) {_SEE_ABOVE}",
            f"  - **AP** (`AP`) {_SEE_ABOVE}",
        ]

    def test_plain_multi_parent_reference_never_expands(self, tmp_path: Path) -> None:
        assert _tree_lines(_model(tmp_path, _SYNOLOGY_LIKE)) == [
            "- **Site** (`Site`)",
            "  - **Pool** (`Pool`)",
            "    - **Volume** (`Volume`)",
            "      - **Cache** (`Cache`)",
            "        - **Disk** (`Disk`)",
            f"    - **Disk** (`Disk`) {_SEE_ABOVE}",
        ]


def _svg_rects(svg: str):
    return [
        tuple(float(v) for v in m)
        for m in re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg)
    ]


def _svg_paths(svg: str):
    paths = []
    for d in re.findall(r'<path d="(M [^"]+)" fill="none"', svg):
        pts = [tuple(float(v) for v in pt.split(",")) for pt in re.findall(r"[\d.]+,[\d.]+", d)]
        paths.append(pts)
    return paths


def _horizontal_segments_through_nodes(svg: str):
    """Horizontal path segments whose y lies strictly inside a node they overlap."""
    hits = []
    for pts in _svg_paths(svg):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if y1 != y2:
                continue
            lo, hi = sorted((x1, x2))
            for rx, ry, rw, rh in _svg_rects(svg):
                if ry < y1 < ry + rh and lo < rx + rw and hi > rx:
                    hits.append(((x1, y1), (x2, y2)))
    return hits


class TestRoutedEdges:
    def test_flat_line_through_nodes_is_gone(self, tmp_path: Path) -> None:
        for name, paths in (("unifi", _UNIFI_LIKE), ("synology", _SYNOLOGY_LIKE)):
            svg = generate_svg(_model(tmp_path, paths, name))
            assert _horizontal_segments_through_nodes(svg) == [], name

    def test_same_row_edge_runs_under_the_row(self, tmp_path: Path) -> None:
        model = _model(tmp_path, _UNIFI_LIKE)
        pos = _layout_nodes(model)
        assert pos["Gateway"][1] == pos["Switch"][1]  # same row
        row_bottom = max(y + h for x, y, w, h in pos.values() if y == pos["Switch"][1])
        lane_paths = [
            pts for pts in _svg_paths(generate_svg(model))
            if pts[0] == (pos["Gateway"][0] + pos["Gateway"][2] * 0.75, row_bottom)
        ]
        assert len(lane_paths) == 1
        pts = lane_paths[0]
        assert len(pts) == 4 and pts[1][1] == pts[2][1] > row_bottom
        # Enters the child's bottom.
        assert pts[-1][1] == pos["Switch"][1] + pos["Switch"][3]

    def test_upward_edge_enters_child_bottom_from_gap_above(self, tmp_path: Path) -> None:
        model = _model(tmp_path, _SYNOLOGY_LIKE)
        pos = _layout_nodes(model)
        assert pos["Cache"][1] > pos["Disk"][1]  # parent below child
        cache_x, cache_y, cache_w, _ = pos["Cache"]
        up = [p for p in _svg_paths(generate_svg(model)) if p[0] == (cache_x + cache_w * 0.65, cache_y)]
        assert len(up) == 1
        pts = up[0]
        disk_bottom = pos["Disk"][1] + pos["Disk"][3]
        assert disk_bottom < pts[1][1] < cache_y  # lane in the gap between the rows
        assert pts[-1][1] == disk_bottom

    def test_lanes_widen_the_gap(self, tmp_path: Path) -> None:
        routed = _layout_nodes(_model(tmp_path, _UNIFI_LIKE, "routed"))
        plain = _layout_nodes(
            _model(tmp_path, ["ak::Site||ak::Gateway::child||ak::Port::child"], "plain")
        )
        # Row 1 to row 2 gap: same-row lanes under row 1 push row 2 down.
        assert routed["Port"][1] > plain["Port"][1]

    def test_excalidraw_routes_the_same_edges(self, tmp_path: Path) -> None:
        doc = generate_excalidraw(_model(tmp_path, _SYNOLOGY_LIKE + _UNIFI_LIKE))
        arrows = [e for e in doc["elements"] if e["type"] == "arrow"]
        routed = [a for a in arrows if len(a["points"]) == 4]
        # Gateway > Switch, Switch > AP (same row), Cache > Disk (upward).
        assert len(routed) == 3
        for a in routed:
            assert a["startBinding"]["elementId"] != a["endBinding"]["elementId"]


class TestLayoutAndDiagrams:
    def test_recursive_kind_keeps_its_row(self, tmp_path: Path) -> None:
        depth = _assign_depth(
            _model(tmp_path, ["ak::Site||ak::Switch::child/recursive||ak::Port::child"])
        )
        assert (depth["Site"], depth["Switch"], depth["Port"]) == (0, 1, 2)

    def test_svg_draws_one_self_loop_per_recursive_kind(self, tmp_path: Path) -> None:
        recursive = generate_svg(_model(tmp_path, _UNIFI_LIKE, "rec"))
        flat = generate_svg(
            _model(tmp_path, [p.replace("/recursive", "") for p in _UNIFI_LIKE], "flat")
        )
        # Two more edge paths: the Switch and AP self-loops.
        marker = 'marker-end="url(#arrow)"'
        assert recursive.count(marker) == flat.count(marker) + 2

    def test_excalidraw_self_loop_binds_to_its_own_node(self, tmp_path: Path) -> None:
        doc = generate_excalidraw(_model(tmp_path, _UNIFI_LIKE))
        rects = {e["id"] for e in doc["elements"] if e["type"] == "rectangle"}
        loops = [
            e for e in doc["elements"]
            if e["type"] == "arrow"
            and e["startBinding"]["elementId"] == e["endBinding"]["elementId"]
        ]
        assert len(loops) == 2
        for loop in loops:
            assert loop["startBinding"]["elementId"] in rects
            assert len(loop["points"]) == 5
            assert loop["points"][0] == [0, 0]

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        a = _model(tmp_path, _UNIFI_LIKE, "a")
        b = _model(tmp_path, _UNIFI_LIKE, "b")
        assert generate_svg(a) == generate_svg(b)
        assert generate_excalidraw(a) == generate_excalidraw(b)
        assert generate_inventory_tree_md(a) == generate_inventory_tree_md(b)
