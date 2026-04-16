"""CLI: validate / list management pack definitions."""
from __future__ import annotations

import argparse
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_managementpacks")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate MP YAML definitions")
    pv.add_argument("paths", nargs="*")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list management pack definitions")
    pl.add_argument("paths", nargs="*")
    pl.set_defaults(func=cmd_list)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
