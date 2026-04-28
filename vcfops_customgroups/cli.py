"""CLI: validate / list / list-types / sync / delete custom groups."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from vcfops_common._profile_cli import add_profile_arg, validate_profile_arg, resolve_profile_from_args

from .client import VCFOpsCustomGroupClient, VCFOpsCustomGroupError
from .loader import (
    CustomGroupDef,
    CustomGroupValidationError,
    collect_required_types,
    load_dir,
    load_file,
)

DEFAULT_DIR = "content/customgroups"


def _collect(paths: List[str]) -> List[CustomGroupDef]:
    if not paths:
        return load_dir(DEFAULT_DIR)
    defs: List[CustomGroupDef] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            defs.extend(load_dir(path))
        else:
            defs.append(load_file(path))
    return defs


def cmd_validate(args) -> int:
    validate_profile_arg(args)  # validate --profile name if supplied; exits on unknown profile
    try:
        defs = _collect(args.paths)
    except CustomGroupValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(defs)} custom group(s) valid")
    for d in defs:
        print(f"  - {d.name}  (type={d.type_key})  ({d.source_path})")
    if defs:
        types = collect_required_types(defs)
        print(f"required group types: {', '.join(types)}")

    # Slug-uniqueness check across content/ and third_party/*/
    if not args.paths:
        try:
            from vcfops_packaging.project import check_slug_uniqueness
            errors = check_slug_uniqueness(
                content_type="customgroups",
                content_type_dir=DEFAULT_DIR,
            )
            if errors:
                for err in errors:
                    print(f"SLUG-COLLISION: {err}", file=sys.stderr)
                return 1
        except ImportError:
            pass  # vcfops_packaging not available — skip cross-provenance check

    return 0


def cmd_list(args) -> int:
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsCustomGroupClient.from_env(profile=profile, default_profile=default)
    for g in client.list_groups():
        rk = g.get("resourceKey") or {}
        if rk.get("adapterKindKey") != "Container":
            continue
        print(
            f"{g.get('id')}  type={rk.get('resourceKindKey')!s:<24} "
            f"{rk.get('name')}"
        )
    return 0


def cmd_list_types(args) -> int:
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsCustomGroupClient.from_env(profile=profile, default_profile=default)
    for t in client.list_group_types():
        print(f"{t.get('key'):<32}  {t.get('name')}")
    return 0


def cmd_sync(args) -> int:
    try:
        defs = _collect(args.paths)
    except CustomGroupValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("nothing to sync", file=sys.stderr)
        return 1
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsCustomGroupClient.from_env(profile=profile, default_profile=default)
    rc = 0

    # Step 1: ensure all referenced group types exist on the
    # instance. Types must precede instances because the
    # cross-reference is by `key` and the API rejects unknowns.
    for type_key in collect_required_types(defs):
        try:
            action, t = client.ensure_group_type(type_key)
            print(f"type {action:8s}  {t.get('key')}")
        except VCFOpsCustomGroupError as e:
            print(f"FAILED   type {type_key}: {e}", file=sys.stderr)
            return 1

    # Step 2: upsert group instances by name.
    for d in defs:
        try:
            action, g = client.upsert_group(d.to_wire())
            print(f"{action:8s}  {g.get('id')}  {d.name}")
        except VCFOpsCustomGroupError as e:
            print(f"FAILED   {d.name}: {e}", file=sys.stderr)
            rc = 1
    return rc


def cmd_delete(args) -> int:
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsCustomGroupClient.from_env(profile=profile, default_profile=default)
    g = client.find_group_by_name(args.name)
    if not g:
        print(f"not found: {args.name}", file=sys.stderr)
        return 1
    client.delete_group(g["id"])
    print(f"deleted  {g['id']}  {args.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_customgroups")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML definitions")
    pv.add_argument("paths", nargs="*")
    add_profile_arg(pv, default="prod")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser(
        "list", help="list custom groups on the instance"
    )
    add_profile_arg(pl, default="prod")
    pl.set_defaults(func=cmd_list)

    plt = sub.add_parser(
        "list-types", help="list group types on the instance"
    )
    add_profile_arg(plt, default="prod")
    plt.set_defaults(func=cmd_list_types)

    ps = sub.add_parser(
        "sync",
        help="ensure required group types exist, then create/update "
             "groups from YAML",
    )
    ps.add_argument("paths", nargs="*")
    add_profile_arg(ps, default="devel")
    ps.set_defaults(func=cmd_sync)

    pd = sub.add_parser(
        "delete", help="delete a custom group by name"
    )
    pd.add_argument("name")
    add_profile_arg(pd, default="devel")
    pd.set_defaults(func=cmd_delete)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except VCFOpsCustomGroupError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
