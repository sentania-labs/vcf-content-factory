#!/usr/bin/env python3
"""Convert .excalidraw files to .svg.

Handles the shape subset used by the framework's architecture diagrams:
rectangle, ellipse, diamond, text (multi-line, font family 3 = mono),
arrow (with end triangle), line.

Usage:
    python3 scripts/excalidraw_to_svg.py knowledge/diagrams/intro-flow.excalidraw
    python3 scripts/excalidraw_to_svg.py knowledge/diagrams/*.excalidraw
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


# Excalidraw font family code -> CSS font-family stack.
FONT_FAMILY = {
    1: "Virgil, Excalifont, sans-serif",
    2: "Helvetica, Arial, sans-serif",
    3: '"Cascadia Code", "Consolas", ui-monospace, monospace',
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_rect(el: dict, body: list[str]) -> None:
    fill = el.get("backgroundColor") or "none"
    stroke = el.get("strokeColor") or "none"
    sw = el.get("strokeWidth", 1)
    if stroke == "transparent":
        stroke = "none"
    rx = 0
    if el.get("roundness"):
        rx = 8
    body.append(
        f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" '
        f'height="{el["height"]}" rx="{rx}" ry="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def render_ellipse(el: dict, body: list[str]) -> None:
    cx = el["x"] + el["width"] / 2
    cy = el["y"] + el["height"] / 2
    rx = el["width"] / 2
    ry = el["height"] / 2
    fill = el.get("backgroundColor") or "none"
    stroke = el.get("strokeColor") or "none"
    sw = el.get("strokeWidth", 1)
    if stroke == "transparent":
        stroke = "none"
    body.append(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def render_diamond(el: dict, body: list[str]) -> None:
    x, y, w, h = el["x"], el["y"], el["width"], el["height"]
    points = f"{x + w/2},{y} {x + w},{y + h/2} {x + w/2},{y + h} {x},{y + h/2}"
    fill = el.get("backgroundColor") or "none"
    stroke = el.get("strokeColor") or "none"
    sw = el.get("strokeWidth", 1)
    if stroke == "transparent":
        stroke = "none"
    body.append(
        f'<polygon points="{points}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def render_text(el: dict, body: list[str]) -> None:
    text = el.get("text") or el.get("originalText") or ""
    if not text:
        return
    font_size = el.get("fontSize", 16)
    fill = el.get("strokeColor") or "#000000"
    if fill == "transparent":
        return
    font_family = FONT_FAMILY.get(el.get("fontFamily", 3), FONT_FAMILY[3])
    align = el.get("textAlign", "left")
    text_anchor = {"left": "start", "center": "middle", "right": "end"}.get(align, "start")
    line_height = el.get("lineHeight", 1.25)

    x = el["x"]
    width = el["width"]
    if align == "center":
        x_text = x + width / 2
    elif align == "right":
        x_text = x + width
    else:
        x_text = x

    lines = text.split("\n")
    # Baseline of the first line approximates "top + fontSize" (close enough
    # for excalidraw's verticalAlign=top default; verticalAlign=middle is
    # handled by a small downward nudge).
    vertical = el.get("verticalAlign", "top")
    base_y = el["y"] + font_size
    if vertical == "middle":
        block_height = font_size * line_height * len(lines)
        base_y = el["y"] + (el["height"] - block_height) / 2 + font_size
    dy_step = font_size * line_height

    body.append(
        f'<text x="{x_text}" y="{base_y}" '
        f'font-family=\'{font_family}\' font-size="{font_size}" '
        f'fill="{fill}" text-anchor="{text_anchor}" '
        f'xml:space="preserve">'
    )
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else dy_step
        body.append(
            f'<tspan x="{x_text}" dy="{dy}">{esc(line)}</tspan>'
        )
    body.append("</text>")


def render_arrow(el: dict, body: list[str]) -> None:
    pts = el.get("points") or []
    if not pts:
        return
    x0, y0 = el["x"], el["y"]
    stroke = el.get("strokeColor") or "#000000"
    sw = el.get("strokeWidth", 2)
    dash = ""
    if el.get("strokeStyle") == "dashed":
        dash = ' stroke-dasharray="10,6"'
    elif el.get("strokeStyle") == "dotted":
        dash = ' stroke-dasharray="2,4"'

    # Build polyline path.
    pts_abs = [(x0 + p[0], y0 + p[1]) for p in pts]
    d = "M " + " L ".join(f"{x},{y}" for x, y in pts_abs)

    marker_end = ' marker-end="url(#arrow)"' if el.get("endArrowhead") else ""
    body.append(
        f'<path d="{d}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}" stroke-linecap="square" '
        f'stroke-linejoin="miter"{dash}{marker_end}/>'
    )


def render_line(el: dict, body: list[str]) -> None:
    # Same shape as arrow but without arrowhead.
    el2 = dict(el)
    el2["endArrowhead"] = None
    render_arrow(el2, body)


RENDERERS = {
    "rectangle": render_rect,
    "ellipse": render_ellipse,
    "diamond": render_diamond,
    "text": render_text,
    "arrow": render_arrow,
    "line": render_line,
}


def convert(excalidraw_path: Path) -> str:
    data = json.loads(excalidraw_path.read_text())
    elements = data.get("elements") or []

    # Compute bounding box.
    xs, ys = [], []
    for el in elements:
        if el.get("isDeleted"):
            continue
        xs.append(el.get("x", 0))
        ys.append(el.get("y", 0))
        xs.append(el.get("x", 0) + el.get("width", 0))
        ys.append(el.get("y", 0) + el.get("height", 0))
        for p in el.get("points") or []:
            xs.append(el.get("x", 0) + p[0])
            ys.append(el.get("y", 0) + p[1])
    if not xs:
        xs, ys = [0, 1000], [0, 1000]
    pad = 0
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    width = max_x - min_x
    height = max_y - min_y

    bg = data.get("appState", {}).get("viewBackgroundColor", "#ffffff")

    body: list[str] = []
    body.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{min_x} {min_y} {width} {height}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet">'
    )
    body.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/>'
        '</marker></defs>'
    )
    body.append(
        f'<rect x="{min_x}" y="{min_y}" width="{width}" height="{height}" '
        f'fill="{bg}"/>'
    )

    for el in elements:
        if el.get("isDeleted"):
            continue
        renderer = RENDERERS.get(el.get("type"))
        if renderer:
            renderer(el, body)

    body.append("</svg>")
    return "\n".join(body)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+", type=Path)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: same as input)",
    )
    args = p.parse_args(argv)

    for path in args.inputs:
        if not path.exists():
            print(f"missing: {path}", file=sys.stderr)
            continue
        svg = convert(path)
        out_dir = args.out_dir or path.parent
        out_path = out_dir / (path.stem + ".svg")
        out_path.write_text(svg)
        print(f"wrote: {out_path}  ({len(svg):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
