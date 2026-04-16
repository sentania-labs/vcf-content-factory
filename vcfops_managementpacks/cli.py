"""CLI: validate / list / render / build management pack definitions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from .loader import ManagementPackDef, ManagementPackValidationError, load_dir, load_file

DEFAULT_DIR = "managementpacks"


def _collect(paths: List[str]) -> List[ManagementPackDef]:
    if not paths:
        return load_dir(DEFAULT_DIR)
    defs: List[ManagementPackDef] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            defs.extend(load_dir(path))
        else:
            defs.append(load_file(path))
    return defs


def cmd_validate(args) -> int:
    try:
        defs = _collect(args.paths)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("OK: no management pack definitions found")
        return 0
    print(f"OK: {len(defs)} management pack definition(s) valid")
    for d in defs:
        obj_count = len(d.object_types)
        rel_count = len(d.relationships)
        print(
            f"  - {d.name}  v{d.version}  "
            f"adapter_kind={d.adapter_kind}  "
            f"objects={obj_count}  relationships={rel_count}  "
            f"({d.source_path})"
        )
    return 0


def cmd_list(args) -> int:
    try:
        defs = _collect([])
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("no management pack definitions found")
        return 0
    for d in defs:
        print(f"{d.adapter_kind}  {d.name}  v{d.version}  ({d.source_path})")
    return 0


def cmd_render(args) -> int:
    from .render import render_mp_design_json

    try:
        mp = load_file(args.path)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    strategy = args.relationship_strategy
    valid_strategies = {
        "world_implicit", "synthetic_adapter_instance",
        "shared_constant_property", "test_all",
    }
    if strategy not in valid_strategies:
        print(
            f"ERROR: --relationship-strategy must be one of "
            f"{sorted(valid_strategies)}; got {strategy!r}",
            file=sys.stderr,
        )
        return 1

    rendered = render_mp_design_json(mp, relationship_strategy=strategy)
    output_str = json.dumps(rendered, indent=2)

    if args.output:
        Path(args.output).write_text(output_str)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(output_str)

    return 0


def cmd_build(args) -> int:
    from .builder import build_pak

    try:
        mp = load_file(args.path)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    strategy = args.relationship_strategy
    valid_strategies = {
        "world_implicit", "synthetic_adapter_instance",
        "shared_constant_property", "test_all",
    }
    if strategy not in valid_strategies:
        print(
            f"ERROR: --relationship-strategy must be one of "
            f"{sorted(valid_strategies)}; got {strategy!r}",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output)
    try:
        pak_path = build_pak(mp, output_dir=output_dir, relationship_strategy=strategy)
    except Exception as exc:
        print(f"ERROR building .pak: {exc}", file=sys.stderr)
        return 1

    print(f"Built: {pak_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_managementpacks")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate MP YAML definitions")
    pv.add_argument("paths", nargs="*")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list management pack definitions")
    pl.add_argument("paths", nargs="*")
    pl.set_defaults(func=cmd_list)

    pr = sub.add_parser("render", help="render MP YAML to MPB design JSON")
    pr.add_argument("path", help="path to MP YAML file")
    pr.add_argument("--output", "-o", help="output file path (default: stdout)")
    pr.add_argument(
        "--relationship-strategy",
        default="test_all",
        choices=[
            "world_implicit",
            "synthetic_adapter_instance",
            "shared_constant_property",
            "test_all",
        ],
        help="strategy for adapter-instance-trivial (null-expression) relationships (default: test_all)",
    )
    pr.set_defaults(func=cmd_render)

    pb = sub.add_parser("build", help="build a .pak file from MP YAML")
    pb.add_argument("path", help="path to MP YAML file")
    pb.add_argument(
        "--output", "-o",
        default="dist",
        help="output directory for the .pak file (default: dist/)",
    )
    pb.add_argument(
        "--relationship-strategy",
        default="test_all",
        choices=[
            "world_implicit",
            "synthetic_adapter_instance",
            "shared_constant_property",
            "test_all",
        ],
        help="strategy for adapter-instance-trivial relationships (default: test_all)",
    )
    pb.set_defaults(func=cmd_build)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
