"""CLI: validate / list / sync / delete super metrics."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .client import VCFOpsClient, VCFOpsError
from .loader import SuperMetricDef, SuperMetricValidationError, load_dir, load_file

DEFAULT_DIR = "supermetrics"


def _collect(paths: List[str]) -> List[SuperMetricDef]:
    if not paths:
        return load_dir(DEFAULT_DIR)
    defs: List[SuperMetricDef] = []
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
    except SuperMetricValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(defs)} super metric(s) valid")
    for d in defs:
        print(f"  - {d.name}  ({d.source_path})")
    return 0


def cmd_list(args) -> int:
    client = VCFOpsClient.from_env()
    for sm in client.list_supermetrics():
        print(f"{sm.get('id')}  {sm.get('name')}")
    return 0


def cmd_sync(args) -> int:
    try:
        defs = _collect(args.paths)
    except SuperMetricValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("nothing to sync", file=sys.stderr)
        return 1
    client = VCFOpsClient.from_env()
    rc = 0
    for d in defs:
        try:
            action, sm = client.upsert(
                d.name, d.formula, d.description, d.resource_kinds
            )
            print(f"{action:8s}  {sm.get('id')}  {d.name}")
        except VCFOpsError as e:
            print(f"FAILED   {d.name}: {e}", file=sys.stderr)
            rc = 1
    return rc


def cmd_delete(args) -> int:
    client = VCFOpsClient.from_env()
    sm = client.find_by_name(args.name)
    if not sm:
        print(f"not found: {args.name}", file=sys.stderr)
        return 1
    client.delete_supermetric(sm["id"])
    print(f"deleted  {sm['id']}  {args.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_supermetrics")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML definitions")
    pv.add_argument("paths", nargs="*")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list super metrics on the instance")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("sync", help="create/update super metrics from YAML")
    ps.add_argument("paths", nargs="*")
    ps.set_defaults(func=cmd_sync)

    pd = sub.add_parser("delete", help="delete a super metric by name")
    pd.add_argument("name")
    pd.set_defaults(func=cmd_delete)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except VCFOpsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
