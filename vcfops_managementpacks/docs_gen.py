"""docs_gen.py — SDK adapter docset generator.

Generates a docs/ directory inside a Tier 2 SDK adapter project.

Two classes of output:

REGENERATE every run (derived from describe.xml / adapter.yaml):
  docs/inventory-tree.md          — indented traversal tree + per-kind table
  docs/inventory-tree.excalidraw  — Excalidraw JSON diagram (editable source)
  docs/inventory-tree.svg         — SVG render of the same diagram (headless,
                                    pure Python, deterministic, no new deps)
  docs/README.md                  — index linking all docset sections

SCAFFOLD if missing (hand-curated thereafter):
  docs/overview.md                — what's in the pack (scaffold only)
  docs/installing.md              — prereqs + config fields table (scaffold only)

Usage:
    from vcfops_managementpacks.docs_gen import generate_docset
    generate_docset(project_dir)

CLI:
    python3 -m vcfops_managementpacks docs-gen <adapter_dir>
"""
from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from .sdk_project import CrossMpEdgeInfo, _parse_cross_mp_edges


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class IdentifierInfo:
    key: str
    label: str
    required: bool
    is_unique: bool  # inferred: required=true identifiers mark the unique key


@dataclass
class KindInfo:
    key: str
    label: str
    type_code: str          # "7" = adapter-instance, "1" = regular, "" = unknown
    identifiers: List[IdentifierInfo] = field(default_factory=list)
    is_adapter_instance: bool = False


@dataclass
class TraversalEdge:
    parent_key: str
    child_key: str


@dataclass
class AdapterDocModel:
    adapter_kind: str
    adapter_name: str
    adapter_version: str
    adapter_description: str
    kinds: List[KindInfo]                    # ordered: adapter-instance first, then describe.xml order
    traversal_name: str
    edges: List[TraversalEdge]              # parent→child pairs, in describe.xml order
    config_fields: List[IdentifierInfo]     # from adapter-instance ResourceIdentifiers
    cross_mp_edges: List[CrossMpEdgeInfo] = field(default_factory=list)  # runtime-only, from adapter.yaml
    # derived
    kind_map: Dict[str, KindInfo] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from a tag."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _resolve_label(name_key: Optional[str], props: Dict[str, str], fallback: str) -> str:
    """Resolve a nameKey integer → display label from resources.properties."""
    if name_key and name_key in props:
        return props[name_key]
    return fallback


def _load_properties(project_dir: Path) -> Dict[str, str]:
    """Load resources/resources.properties → dict of key→value."""
    res_file = project_dir / "resources" / "resources.properties"
    if not res_file.is_file():
        return {}
    props: Dict[str, str] = {}
    for line in res_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        props[k.strip()] = v.strip()
    return props


def _parse_traversal_paths(spec_kind_elem, ns: str) -> List[TraversalEdge]:
    """Parse ResourcePath elements → ordered list of unique TraversalEdge pairs.

    Path format:
      ak::rk1||ak::rk2::child||ak::rk3::child||...

    Each consecutive pair rk(i) → rk(i+1) produces an edge (if not already seen).
    The adapter-instance root is skipped — it appears in describe.xml as type=7.
    """
    edges: List[TraversalEdge] = []
    seen: set = set()

    for rp in spec_kind_elem.iter(f"{ns}ResourcePath"):
        path_str = rp.get("path", "")
        # Split on "||" to get segments
        segments = path_str.split("||")
        # Each segment: "adapterKind::resourceKind" or "adapterKind::resourceKind::child"
        rk_keys = []
        for seg in segments:
            parts = seg.split("::")
            if len(parts) >= 2:
                rk_keys.append(parts[1])  # resource kind key

        # Build consecutive pairs
        for i in range(len(rk_keys) - 1):
            parent = rk_keys[i]
            child = rk_keys[i + 1]
            pair = (parent, child)
            if pair not in seen:
                seen.add(pair)
                edges.append(TraversalEdge(parent_key=parent, child_key=child))

    return edges


def parse_describe_xml(project_dir: Path) -> Tuple[List[KindInfo], str, List[TraversalEdge], List[IdentifierInfo]]:
    """Parse describe.xml and return (kinds, traversal_name, edges, config_fields).

    Returns:
        kinds           — all ResourceKinds in describe.xml order
        traversal_name  — TraversalSpecKind name (or "")
        edges           — ordered unique parent→child edges from traversal spec
        config_fields   — ResourceIdentifiers of the adapter-instance kind (type=7)
    """
    describe_xml = project_dir / "describe.xml"
    if not describe_xml.is_file():
        return [], "", [], []

    props = _load_properties(project_dir)

    try:
        tree = ET.parse(describe_xml)
    except ET.ParseError as exc:
        raise ValueError(f"Cannot parse describe.xml: {exc}") from exc

    root = tree.getroot()
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}", 1)[0] + "}"

    kinds: List[KindInfo] = []
    config_fields: List[IdentifierInfo] = []

    for rk in root.iter(f"{ns}ResourceKind"):
        key = rk.get("key", "")
        name_key = rk.get("nameKey", "")
        type_code = rk.get("type", "")
        label = _resolve_label(name_key, props, key)
        is_adapter_instance = (type_code == "7")

        # ResourceIdentifiers
        identifiers: List[IdentifierInfo] = []
        for ri in rk:
            if _strip_ns(ri.tag) != "ResourceIdentifier":
                continue
            ri_key = ri.get("key", "")
            ri_name_key = ri.get("nameKey", "")
            ri_label = _resolve_label(ri_name_key, props, ri_key)
            required = ri.get("required", "false").lower() == "true"
            # isUnique: required=true identifiers are the identifying keys
            is_unique = required
            identifiers.append(IdentifierInfo(
                key=ri_key,
                label=ri_label,
                required=required,
                is_unique=is_unique,
            ))

        kind = KindInfo(
            key=key,
            label=label,
            type_code=type_code,
            identifiers=identifiers,
            is_adapter_instance=is_adapter_instance,
        )
        kinds.append(kind)

        if is_adapter_instance:
            config_fields = identifiers

    # Traversal spec
    traversal_name = ""
    edges: List[TraversalEdge] = []
    for spec_kind in root.iter(f"{ns}TraversalSpecKind"):
        traversal_name = spec_kind.get("name", "")
        name_key = spec_kind.get("nameKey", "")
        if name_key and name_key in props:
            traversal_name = props[name_key]
        edges = _parse_traversal_paths(spec_kind, ns)
        break  # use first traversal spec

    return kinds, traversal_name, edges, config_fields


def build_doc_model(project_dir: Path) -> AdapterDocModel:
    """Load adapter.yaml + describe.xml and build the AdapterDocModel."""
    adapter_yaml = project_dir / "adapter.yaml"
    if not adapter_yaml.is_file():
        raise ValueError(f"adapter.yaml not found in {project_dir}")

    if not _YAML_AVAILABLE:
        raise RuntimeError("PyYAML is required for docs-gen. Install it with: pip install pyyaml")

    with adapter_yaml.open(encoding="utf-8") as fh:
        raw = _yaml.safe_load(fh) or {}

    adapter_kind = raw.get("adapter_kind", "unknown")
    adapter_name = raw.get("name", adapter_kind)
    adapter_version = f"{raw.get('version', '1.0.0')}.{raw.get('build_number', 0)}"
    adapter_description = (raw.get("description") or "").strip()

    kinds, traversal_name, edges, config_fields = parse_describe_xml(project_dir)

    kind_map = {k.key: k for k in kinds}

    # Same validation as validate-sdk (SdkProjectError is a ValueError subclass,
    # caught by generate_docset's except (ValueError, RuntimeError) below) —
    # docs-gen refuses to silently drop a malformed stanza.
    cross_mp_edges = _parse_cross_mp_edges(raw, str(adapter_yaml))

    return AdapterDocModel(
        adapter_kind=adapter_kind,
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        adapter_description=adapter_description,
        kinds=kinds,
        traversal_name=traversal_name,
        edges=edges,
        config_fields=config_fields,
        cross_mp_edges=cross_mp_edges,
        kind_map=kind_map,
    )


# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------

def _build_children_map(model: AdapterDocModel) -> Dict[str, List[str]]:
    """Return dict: parent_key → [child_key, ...] (in edge order)."""
    children: Dict[str, List[str]] = {}
    seen: Dict[str, set] = {}
    for edge in model.edges:
        p = edge.parent_key
        c = edge.child_key
        if p not in children:
            children[p] = []
            seen[p] = set()
        if c not in seen[p]:
            children[p].append(c)
            seen[p].add(c)
    return children


def _tree_roots(model: AdapterDocModel) -> List[str]:
    """Return kind keys that are edge sources but not edge targets (tree roots).

    Excludes the adapter-instance kind (type=7).
    """
    all_parents = {e.parent_key for e in model.edges}
    all_children = {e.child_key for e in model.edges}
    # Roots appear as parents but not as children
    roots = [k for k in all_parents if k not in all_children]
    if not roots:
        # Fallback: first non-adapter-instance kind that appears as a parent
        for e in model.edges:
            if e.parent_key not in all_children:
                roots.append(e.parent_key)
                break
    return roots


def _parents_map(model: AdapterDocModel) -> Dict[str, List[str]]:
    """Return dict: child_key → [parent_key, ...]"""
    parents: Dict[str, List[str]] = {}
    for edge in model.edges:
        parents.setdefault(edge.child_key, [])
        if edge.parent_key not in parents[edge.child_key]:
            parents[edge.child_key].append(edge.parent_key)
    return parents


def _assign_depth(model: AdapterDocModel) -> Dict[str, int]:
    """Assign a depth (0 = root) to each kind key, based on traversal edges.

    Adapter-instance kind gets depth -1 (excluded from diagram rows).
    Kinds not in traversal get depth = max_depth + 1.
    """
    children = _build_children_map(model)
    roots = _tree_roots(model)

    depth: Dict[str, int] = {}
    queue = [(r, 0) for r in roots]
    while queue:
        node, d = queue.pop(0)
        if node in depth:
            depth[node] = min(depth[node], d)
        else:
            depth[node] = d
        for child in children.get(node, []):
            queue.append((child, d + 1))

    # Adapter-instance kinds: depth = -1
    for k in model.kinds:
        if k.is_adapter_instance:
            depth[k.key] = -1

    return depth


# ---------------------------------------------------------------------------
# Markdown generator
# ---------------------------------------------------------------------------

def _render_tree_md(model: AdapterDocModel) -> str:
    """Render the indented inventory tree as markdown."""
    children = _build_children_map(model)
    roots = _tree_roots(model)
    visited: set = set()

    lines: List[str] = []

    def _walk(key: str, indent: int) -> None:
        if key in visited:
            return
        visited.add(key)
        kind = model.kind_map.get(key)
        label = kind.label if kind else key
        prefix = "  " * indent + "- "
        lines.append(f"{prefix}**{label}** (`{key}`)")
        for child in children.get(key, []):
            _walk(child, indent + 1)

    for root in roots:
        _walk(root, 0)

    return "\n".join(lines)


def _format_cross_mp_endpoint(label: str, is_foreign: bool, foreign_adapter_kind: str) -> str:
    """Render one edge endpoint, visually distinguishing foreign kinds.

    Foreign endpoints render in italics with a "(foreign[, <adapter kind>])"
    annotation so they can't be confused with this adapter's own containment
    tree. Own-adapter endpoints render as inline code, matching the
    inventory table style.
    """
    if is_foreign:
        annotation = f"(foreign, {foreign_adapter_kind})" if foreign_adapter_kind else "(foreign)"
        return f"*{label}* {annotation}"
    return f"`{label}`"


def _render_cross_mp_edges_md(model: AdapterDocModel, heading_level: str = "##") -> str:
    """Render the "Cross-MP Relationships" section as a markdown table.

    Returns "" if there are no cross_mp_edges (callers must skip the section
    entirely in that case to keep byte-identical output for packs without
    stitches).
    """
    if not model.cross_mp_edges:
        return ""

    rows = [
        "| Parent | Child | Description |",
        "|--------|-------|-------------|",
    ]
    for edge in model.cross_mp_edges:
        parent_is_foreign = edge.direction == "parent_foreign"
        child_is_foreign = edge.direction == "child_foreign"
        parent_cell = _format_cross_mp_endpoint(
            edge.parent, parent_is_foreign, edge.foreign_adapter_kind
        )
        child_cell = _format_cross_mp_endpoint(
            edge.child, child_is_foreign, edge.foreign_adapter_kind
        )
        desc_cell = edge.description or "—"
        rows.append(f"| {parent_cell} | {child_cell} | {desc_cell} |")

    table_md = "\n".join(rows)

    return "\n".join([
        f"{heading_level} Cross-MP Relationships",
        "",
        "These edges are created at collection time via the Suite API and "
        "never appear in `describe.xml` — they are declared explicitly in "
        "`adapter.yaml` (`cross_mp_edges`) so this generated docset doesn't "
        "silently omit them. *Italic* endpoints belong to a foreign "
        "management pack; `code` endpoints are owned by this adapter.",
        "",
        table_md,
        "",
    ])


def generate_inventory_tree_md(model: AdapterDocModel) -> str:
    """Generate docs/inventory-tree.md content."""
    parents_map = _parents_map(model)
    children_map = _build_children_map(model)

    # Traversal tree section
    tree_lines = _render_tree_md(model)

    # Per-kind table
    # Columns: Kind | Display Label | Identifying Keys | Unique Keys | Parent(s)
    table_rows: List[str] = []
    table_rows.append("| Kind | Display Label | Identifying Keys | Parent(s) |")
    table_rows.append("|------|--------------|-----------------|-----------|")

    # Order: non-adapter-instance kinds in model order
    for kind in model.kinds:
        if kind.is_adapter_instance:
            continue

        parent_labels = []
        for pk in parents_map.get(kind.key, []):
            pk_kind = model.kind_map.get(pk)
            parent_labels.append(pk_kind.label if pk_kind else pk)

        id_parts = []
        for ident in kind.identifiers:
            marker = " *" if ident.is_unique else ""
            id_parts.append(f"`{ident.key}`{marker}")

        id_cell = ", ".join(id_parts) if id_parts else "—"
        parent_cell = ", ".join(parent_labels) if parent_labels else "—"

        table_rows.append(
            f"| `{kind.key}` | {kind.label} | {id_cell} | {parent_cell} |"
        )

    table_md = "\n".join(table_rows)

    traversal_header = f"**Traversal Spec:** {model.traversal_name}" if model.traversal_name else ""

    parts = [
        f"# Inventory Tree — {model.adapter_name}",
        "",
        f"> Generated from `describe.xml` v{model.adapter_version}. Do not edit — regenerated on every build.",
        "",
    ]
    if traversal_header:
        parts += [traversal_header, ""]

    parts += [
        "## Traversal Tree",
        "",
        tree_lines,
        "",
        "> \\* = identifying (unique) key",
        "",
        "## Resource Kinds Reference",
        "",
        table_md,
        "",
    ]

    cross_mp_section = _render_cross_mp_edges_md(model)
    if cross_mp_section:
        parts += [cross_mp_section]

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# SVG / Excalidraw layout engine
# ---------------------------------------------------------------------------

# Layout constants
_NODE_W = 220          # node width in px
_NODE_H_BASE = 60      # base height (title + adapter label)
_NODE_H_PER_KEY = 18   # extra height per identifier key line
_H_GAP = 60            # horizontal gap between nodes in same row
_V_GAP = 90            # vertical gap between rows
_MARGIN = 40           # canvas margin


def _stable_id(seed: str) -> str:
    """Derive a stable 8-hex-char ID from a seed string."""
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]


def _node_height(kind: KindInfo) -> int:
    """Calculate node height based on number of identifier keys."""
    key_lines = len(kind.identifiers)
    return _NODE_H_BASE + max(0, key_lines) * _NODE_H_PER_KEY


def _layout_nodes(model: AdapterDocModel) -> Dict[str, Tuple[float, float, int, int]]:
    """Assign (x, y, w, h) to each non-adapter-instance kind.

    Layout: rows by depth, stable ordering within row = describe.xml order.
    Returns dict: kind_key → (x, y, w, h).
    """
    depth_map = _assign_depth(model)
    children_map = _build_children_map(model)

    # Group kinds by depth (exclude adapter-instance)
    depth_groups: Dict[int, List[str]] = {}
    for kind in model.kinds:
        if kind.is_adapter_instance:
            continue
        d = depth_map.get(kind.key, 0)
        depth_groups.setdefault(d, [])
        if kind.key not in depth_groups[d]:
            depth_groups[d].append(kind.key)

    if not depth_groups:
        return {}

    max_depth = max(depth_groups.keys())
    positions: Dict[str, Tuple[float, float, int, int]] = {}

    y = _MARGIN
    for d in range(max_depth + 1):
        row_keys = depth_groups.get(d, [])
        if not row_keys:
            continue

        # Compute heights for this row
        row_heights = [_node_height(model.kind_map[k]) for k in row_keys if k in model.kind_map]
        row_h = max(row_heights) if row_heights else _NODE_H_BASE

        # Calculate row width and x offsets (centered or left-aligned)
        x = _MARGIN
        for key in row_keys:
            kind = model.kind_map.get(key)
            h = _node_height(kind) if kind else _NODE_H_BASE
            positions[key] = (x, y, _NODE_W, h)
            x += _NODE_W + _H_GAP

        y += row_h + _V_GAP

    return positions


def _excalidraw_element_rect(
    elem_id: str,
    x: float, y: float, w: int, h: int,
    label: str,
    id_lines: List[str],
    is_root: bool = False,
) -> dict:
    """Build an Excalidraw rectangle element dict."""
    # Multi-line text: label on top, then identifier keys
    text_parts = [label]
    for line in id_lines:
        text_parts.append(line)
    text = "\n".join(text_parts)

    bg_color = "#e3f2fd" if is_root else "#ffffff"
    stroke_color = "#1565c0" if is_root else "#374151"

    return {
        "id": elem_id,
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke_color,
        "backgroundColor": bg_color,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "roundness": {"type": 3},
        "seed": int(hashlib.md5(elem_id.encode()).hexdigest()[:8], 16),
        "version": 1,
        "versionNonce": int(hashlib.md5((elem_id + "v").encode()).hexdigest()[:8], 16),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1700000000000,
        "link": None,
        "locked": False,
        "label": {
            "text": text,
            "fontSize": 13,
            "fontFamily": 1,
            "textAlign": "center",
            "verticalAlign": "middle",
        },
    }


def _excalidraw_element_text(
    elem_id: str,
    x: float, y: float, w: int, h: int,
    text: str,
    font_size: int = 13,
    bold: bool = False,
) -> dict:
    """Build an Excalidraw text element."""
    return {
        "id": elem_id,
        "type": "text",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#1e293b",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "roundness": None,
        "seed": int(hashlib.md5(elem_id.encode()).hexdigest()[:8], 16),
        "version": 1,
        "versionNonce": int(hashlib.md5((elem_id + "v").encode()).hexdigest()[:8], 16),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1700000000000,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": font_size,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "containerId": None,
        "originalText": text,
        "lineHeight": 1.25,
    }


def _excalidraw_element_arrow(
    elem_id: str,
    start_x: float, start_y: float,
    end_x: float, end_y: float,
    start_binding: Optional[str] = None,
    end_binding: Optional[str] = None,
) -> dict:
    """Build an Excalidraw arrow element (straight line)."""
    return {
        "id": elem_id,
        "type": "arrow",
        "x": start_x,
        "y": start_y,
        "width": abs(end_x - start_x),
        "height": abs(end_y - start_y),
        "angle": 0,
        "strokeColor": "#374151",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "roundness": {"type": 2},
        "seed": int(hashlib.md5(elem_id.encode()).hexdigest()[:8], 16),
        "version": 1,
        "versionNonce": int(hashlib.md5((elem_id + "v").encode()).hexdigest()[:8], 16),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1700000000000,
        "link": None,
        "locked": False,
        "points": [
            [0, 0],
            [end_x - start_x, end_y - start_y],
        ],
        "lastCommittedPoint": None,
        "startBinding": {"elementId": start_binding, "focus": 0, "gap": 4} if start_binding else None,
        "endBinding": {"elementId": end_binding, "focus": 0, "gap": 4} if end_binding else None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "elbowed": False,
    }


def generate_excalidraw(model: AdapterDocModel) -> dict:
    """Generate the Excalidraw JSON dict for the inventory tree diagram.

    Layout: rows by tree depth, stable ordering = describe.xml order.
    One rectangle per non-adapter-instance ResourceKind, label = display name
    + identifier keys (unique ones starred). Arrows parent→child.
    All IDs are derived deterministically from kind keys.
    """
    positions = _layout_nodes(model)
    depth_map = _assign_depth(model)
    roots = set(_tree_roots(model))

    elements: List[dict] = []
    rect_ids: Dict[str, str] = {}  # kind_key → element id

    # 1. Rectangle nodes
    for kind in model.kinds:
        if kind.is_adapter_instance:
            continue
        pos = positions.get(kind.key)
        if pos is None:
            continue

        x, y, w, h = pos
        elem_id = _stable_id(f"rect:{kind.key}")
        rect_ids[kind.key] = elem_id

        id_lines: List[str] = []
        for ident in kind.identifiers:
            marker = " *" if ident.is_unique else ""
            id_lines.append(f"  {ident.key}{marker}")

        is_root = kind.key in roots
        rect = _excalidraw_element_rect(
            elem_id=elem_id,
            x=x, y=y, w=w, h=h,
            label=kind.label,
            id_lines=id_lines,
            is_root=is_root,
        )
        elements.append(rect)

    # 2. Arrow edges
    for edge in model.edges:
        p = edge.parent_key
        c = edge.child_key
        if p not in positions or c not in positions:
            continue

        px, py, pw, ph = positions[p]
        cx, cy, cw, ch = positions[c]

        # Arrow from bottom-center of parent to top-center of child
        start_x = px + pw / 2
        start_y = py + ph
        end_x = cx + cw / 2
        end_y = cy

        arrow_id = _stable_id(f"arrow:{p}->{c}")
        arrow = _excalidraw_element_arrow(
            elem_id=arrow_id,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            start_binding=rect_ids.get(p),
            end_binding=rect_ids.get(c),
        )
        elements.append(arrow)

    # Calculate canvas bounds
    if positions:
        max_x = max(x + w for x, y, w, h in positions.values()) + _MARGIN
        max_y = max(y + h for x, y, w, h in positions.values()) + _MARGIN
    else:
        max_x = 800
        max_y = 400

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }


# ---------------------------------------------------------------------------
# SVG renderer (pure Python, no new deps)
# ---------------------------------------------------------------------------

_SVG_FONT = "ui-monospace, SFMono-Regular, Menlo, monospace"
_SVG_LABEL_FONT = "ui-sans-serif, system-ui, sans-serif"
_SVG_FONT_SIZE = 12
_SVG_LABEL_FONT_SIZE = 13
_SVG_LINE_H = 15


def _svg_escape(s: str) -> str:
    """Escape XML special characters for SVG text."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_svg(model: AdapterDocModel) -> str:
    """Generate a headless SVG render of the inventory tree diagram.

    Pure Python, no external dependencies. Same layout model as the Excalidraw
    generator — deterministic, stable across runs.
    """
    positions = _layout_nodes(model)
    roots = set(_tree_roots(model))

    if not positions:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="10" y="20" font-family="sans-serif" font-size="13">No traversal spec found.</text></svg>'

    # Canvas size
    max_x = max(x + w for x, y, w, h in positions.values()) + _MARGIN
    max_y = max(y + h for x, y, w, h in positions.values()) + _MARGIN

    svg_parts: List[str] = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{max_x:.0f}" height="{max_y:.0f}" '
        f'style="font-family: {_SVG_LABEL_FONT}; background: #fff;">'
    )
    svg_parts.append("<defs>")
    svg_parts.append(
        '  <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#374151"/></marker>'
    )
    svg_parts.append("</defs>")

    # Draw edges first (under rectangles)
    for edge in model.edges:
        p = edge.parent_key
        c = edge.child_key
        if p not in positions or c not in positions:
            continue
        px, py, pw, ph = positions[p]
        cx, cy, cw, ch = positions[c]

        # Arrow: bottom-center of parent → top-center of child
        x1 = px + pw / 2
        y1 = py + ph
        x2 = cx + cw / 2
        y2 = cy

        # Orthogonal path: down from parent, right/left, then down to child
        mid_y = (y1 + y2) / 2
        path = f"M {x1:.1f},{y1:.1f} L {x1:.1f},{mid_y:.1f} L {x2:.1f},{mid_y:.1f} L {x2:.1f},{y2:.1f}"
        svg_parts.append(
            f'<path d="{path}" fill="none" stroke="#374151" stroke-width="1.5" '
            f'marker-end="url(#arrow)"/>'
        )

    # Draw rectangles
    for kind in model.kinds:
        if kind.is_adapter_instance:
            continue
        pos = positions.get(kind.key)
        if pos is None:
            continue

        x, y, w, h = pos
        is_root = kind.key in roots

        fill = "#e3f2fd" if is_root else "#f8fafc"
        stroke = "#1565c0" if is_root else "#374151"
        stroke_w = 2 if is_root else 1.5

        svg_parts.append(
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" '
            f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>'
        )

        # Label (bold)
        label_y = y + 22
        svg_parts.append(
            f'<text x="{x + w / 2:.0f}" y="{label_y:.0f}" '
            f'font-family="{_SVG_LABEL_FONT}" font-size="{_SVG_LABEL_FONT_SIZE}" '
            f'font-weight="600" fill="#111827" text-anchor="middle">'
            f'{_svg_escape(kind.label)}</text>'
        )

        # Identifier lines
        for i, ident in enumerate(kind.identifiers):
            marker = " *" if ident.is_unique else ""
            iy = label_y + 18 + i * _SVG_LINE_H
            svg_parts.append(
                f'<text x="{x + w / 2:.0f}" y="{iy:.0f}" '
                f'font-family="{_SVG_FONT}" font-size="{_SVG_FONT_SIZE}" '
                f'fill="#374151" text-anchor="middle">'
                f'{_svg_escape(ident.key + marker)}</text>'
            )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ---------------------------------------------------------------------------
# Scaffold generators
# ---------------------------------------------------------------------------

def generate_overview_md(model: AdapterDocModel) -> str:
    """Generate docs/overview.md scaffold content."""
    non_instance_kinds = [k for k in model.kinds if not k.is_adapter_instance]
    kind_count = len(non_instance_kinds)

    kind_list = "\n".join(
        f"- **{k.label}** (`{k.key}`)"
        for k in non_instance_kinds
    )

    return f"""# Overview — {model.adapter_name}

> **Scaffold** — edit this file to describe your pack. It is generated once and
> not overwritten on subsequent builds.

## What's in the Pack

{model.adapter_name} version {model.adapter_version}.

{model.adapter_description}

### Resource Kinds ({kind_count})

{kind_list}

## Cross-Adapter Notes

<!-- Describe LLDP stitching, ARIA_OPS metric stitching, or other cross-adapter
     relationships here. -->

## Known Limitations

<!-- List known limitations, gaps, or caveats here. -->
"""


def generate_installing_md(model: AdapterDocModel) -> str:
    """Generate docs/installing.md scaffold content."""
    adapter_instance = next((k for k in model.kinds if k.is_adapter_instance), None)

    config_table_rows = ["| Field | Key | Required | Default | Notes |",
                         "|-------|-----|----------|---------|-------|"]

    if adapter_instance:
        for ident in adapter_instance.identifiers:
            req = "Yes" if ident.required else "No"
            config_table_rows.append(
                f"| {ident.label} | `{ident.key}` | {req} | — | |"
            )
    else:
        config_table_rows.append("| — | — | — | — | No adapter instance kind found |")

    config_table = "\n".join(config_table_rows)

    return f"""# Installing & Configuring — {model.adapter_name}

> **Scaffold** — edit this file with actual prerequisites and steps. It is generated
> once and not overwritten on subsequent builds.

## Prerequisites

- VCF Operations 8.0 or later
- <!-- describe target system access requirements here -->

## Permissions Required

<!-- List permissions the adapter credential account needs. -->

## Network Requirements

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 443  | HTTPS    | Outbound  | <!-- describe target endpoint --> |

## Configuration Fields

When adding a new adapter instance in VCF Operations, you will be prompted for:

{config_table}

## Step-by-Step Installation

1. Install the `.pak` file via **Administration > Solutions > Add**.
2. After installation, navigate to **Data Sources > Integrations > Accounts**.
3. Click **Add Account** and select **{model.adapter_name}**.
4. Fill in the configuration fields above.
5. Click **Validate Connection**, then **Add**.

## Troubleshooting

<!-- Common issues and solutions. -->
"""


def generate_readme_md(model: AdapterDocModel) -> str:
    """Generate docs/README.md index content."""
    contents_rows = [
        "| Section | Description |",
        "|---------|-------------|",
        "| [Overview](overview.md) | What's in the pack, resource kinds, cross-adapter notes |",
        "| [Installing & Configuring](installing.md) | Prerequisites, configuration fields, step-by-step guide |",
        "| [Inventory Tree](inventory-tree.md) | Traversal spec, per-kind table with identifying keys |",
        "| [Metrics Reference](../REFERENCE.md) | Full metrics and properties reference (generated) |",
    ]

    cross_mp_line = ""
    cross_mp_section = ""
    if model.cross_mp_edges:
        cross_mp_line = (
            f"- **Cross-MP relationships:** {len(model.cross_mp_edges)} "
            f"(see [Cross-MP Relationships](#cross-mp-relationships) below)\n"
        )
        cross_mp_section = "\n" + _render_cross_mp_edges_md(model)

    return f"""# {model.adapter_name} — Documentation

> Generated index. The SVG diagram and per-kind table are regenerated on every
> build; prose sections (overview, installing) are hand-curated.

## Contents

{chr(10).join(contents_rows)}

## Inventory Tree

![Inventory Tree](inventory-tree.svg)
{cross_mp_section}
## Quick Reference

- **Adapter kind:** `{model.adapter_kind}`
- **Version:** {model.adapter_version}
- **Traversal spec:** {model.traversal_name or "(none)"}
- **Resource kinds:** {len([k for k in model.kinds if not k.is_adapter_instance])}
{cross_mp_line}"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

class DocsGenError(ValueError):
    """Raised when docs-gen encounters an unrecoverable error."""


def generate_docset(project_dir: Path, verbose: bool = False) -> Dict[str, str]:
    """Generate the docs/ docset for a Tier 2 SDK adapter project.

    REGENERATE policy (always overwritten):
      docs/inventory-tree.md
      docs/inventory-tree.excalidraw
      docs/inventory-tree.svg
      docs/README.md

    SCAFFOLD policy (only written if the file does not already exist):
      docs/overview.md
      docs/installing.md

    Args:
        project_dir: Path to the adapter project directory (contains adapter.yaml).
        verbose:     Print progress messages.

    Returns:
        Dict mapping relative path (e.g. "docs/README.md") → "generated" | "scaffolded" | "skipped".

    Raises:
        DocsGenError: if adapter.yaml or describe.xml cannot be parsed.
    """
    def _log(msg: str) -> None:
        if verbose:
            import sys
            print(msg, file=sys.stderr)

    project_dir = Path(project_dir).resolve()
    docs_dir = project_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    try:
        model = build_doc_model(project_dir)
    except (ValueError, RuntimeError) as exc:
        raise DocsGenError(str(exc)) from exc

    results: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # REGENERATE outputs
    # ------------------------------------------------------------------

    # 1. inventory-tree.md
    tree_md = generate_inventory_tree_md(model)
    (docs_dir / "inventory-tree.md").write_text(tree_md, encoding="utf-8")
    results["docs/inventory-tree.md"] = "generated"
    _log("  generated docs/inventory-tree.md")

    # 2. inventory-tree.excalidraw
    excalidraw_dict = generate_excalidraw(model)
    excalidraw_json = json.dumps(excalidraw_dict, indent=2, sort_keys=False)
    (docs_dir / "inventory-tree.excalidraw").write_text(excalidraw_json, encoding="utf-8")
    results["docs/inventory-tree.excalidraw"] = "generated"
    _log("  generated docs/inventory-tree.excalidraw")

    # 3. inventory-tree.svg
    svg_content = generate_svg(model)
    (docs_dir / "inventory-tree.svg").write_text(svg_content, encoding="utf-8")
    results["docs/inventory-tree.svg"] = "generated"
    _log("  generated docs/inventory-tree.svg")

    # 4. README.md
    readme_md = generate_readme_md(model)
    (docs_dir / "README.md").write_text(readme_md, encoding="utf-8")
    results["docs/README.md"] = "generated"
    _log("  generated docs/README.md")

    # ------------------------------------------------------------------
    # SCAFFOLD outputs (only if missing)
    # ------------------------------------------------------------------

    overview_path = docs_dir / "overview.md"
    if not overview_path.is_file():
        overview_md = generate_overview_md(model)
        overview_path.write_text(overview_md, encoding="utf-8")
        results["docs/overview.md"] = "scaffolded"
        _log("  scaffolded docs/overview.md")
    else:
        results["docs/overview.md"] = "skipped (exists)"
        _log("  docs/overview.md exists — skipping (scaffold only)")

    installing_path = docs_dir / "installing.md"
    if not installing_path.is_file():
        installing_md = generate_installing_md(model)
        installing_path.write_text(installing_md, encoding="utf-8")
        results["docs/installing.md"] = "scaffolded"
        _log("  scaffolded docs/installing.md")
    else:
        results["docs/installing.md"] = "skipped (exists)"
        _log("  docs/installing.md exists — skipping (scaffold only)")

    return results
