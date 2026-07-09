"""CLI: validate / list / sync / delete symptom definitions."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from vcfops_common._profile_cli import add_profile_arg, validate_profile_arg, resolve_profile_from_args

from .client import VCFOpsSymptomsClient, VCFOpsSymptomsError
from .loader import SymptomDef, SymptomValidationError, load_dir, load_file

DEFAULT_DIR = "content/symptoms"


def _collect(paths: List[str]) -> List[SymptomDef]:
    if not paths:
        return load_dir(DEFAULT_DIR)
    defs: List[SymptomDef] = []
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
    except SymptomValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(defs)} symptom definition(s) valid")
    for d in defs:
        print(
            f"  - {d.name}  "
            f"({d.adapter_kind}/{d.resource_kind}, "
            f"severity={d.severity})  "
            f"({d.source_path})"
        )

    # Slug-uniqueness check across content/ and third_party/*/
    if not args.paths:
        try:
            from vcfops_packaging.project import check_slug_uniqueness
            errors = check_slug_uniqueness(
                content_type="symptoms",
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
    client = VCFOpsSymptomsClient.from_env(profile=profile, default_profile=default)
    for sd in client.list_symptoms():
        print(f"{sd.get('id')}  {sd.get('name')}")
    return 0


def cmd_sync(args) -> int:
    try:
        defs = _collect(args.paths)
    except SymptomValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("nothing to sync", file=sys.stderr)
        return 1
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsSymptomsClient.from_env(profile=profile, default_profile=default)
    rc = 0
    for d in defs:
        try:
            action, result = client.upsert_symptom(d.to_wire())
            print(f"{action:8s}  {result.get('id')}  {d.name}")
        except VCFOpsSymptomsError as e:
            print(f"FAILED   {d.name}: {e}", file=sys.stderr)
            rc = 1
    return rc


def cmd_delete(args) -> int:
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsSymptomsClient.from_env(profile=profile, default_profile=default)
    sd = client.find_by_name(args.name)
    if not sd:
        print(f"not found: {args.name}", file=sys.stderr)
        return 1
    client.delete_symptom(sd["id"])
    print(f"deleted  {sd['id']}  {args.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_symptoms")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML definitions")
    pv.add_argument("paths", nargs="*")
    add_profile_arg(pv, default="prod")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list symptom definitions on the instance")
    add_profile_arg(pl, default="prod")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("sync", help="create/update symptom definitions from YAML")
    ps.add_argument("paths", nargs="*")
    add_profile_arg(ps, default="devel")
    ps.set_defaults(func=cmd_sync)

    pd = sub.add_parser("delete", help="delete a symptom definition by name")
    pd.add_argument("name")
    add_profile_arg(pd, default="devel")
    pd.set_defaults(func=cmd_delete)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except VCFOpsSymptomsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
