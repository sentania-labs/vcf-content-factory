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
    bundle = [
        {
            "id": d.id,
            "name": d.name,
            "formula": d.formula,
            "description": d.description,
            "unitId": d.unit_id,
            "resourceKinds": d.resource_kinds,
        }
        for d in defs
    ]
    try:
        result = client.import_supermetrics_bundle(bundle)
    except VCFOpsError as e:
        print(f"FAILED   bundle import: {e}", file=sys.stderr)
        return 1
    # The content importer reports per-contentType summaries. Per-op
    # `errorCode: NONE` is the success sentinel, not an error. Per-
    # contentType `state=FAILED` signals partial-or-zero import.
    summaries = result.get("operationSummaries") or []
    imported = skipped = failed = 0
    for s in summaries:
        imported += int(s.get("imported") or 0)
        skipped += int(s.get("skipped") or 0)
        failed += int(s.get("failed") or 0)
    print(
        f"super metric import: imported={imported} skipped={skipped} "
        f"failed={failed} (bundle={len(bundle)})"
    )
    for d in defs:
        print(f"  {d.id}  {d.name}")
    if imported == 0 and (skipped or failed):
        print(
            "WARNING: nothing imported — all entries skipped/failed. "
            "Check name/UUID collisions with existing super metrics.",
            file=sys.stderr,
        )
        return 1
    if failed:
        return 1
    return 0


def cmd_enable(args) -> int:
    try:
        defs = _collect(args.paths)
    except SuperMetricValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("nothing to enable", file=sys.stderr)
        return 1
    client = VCFOpsClient.from_env()
    rc = 0
    for d in defs:
        existing = client.find_by_name(d.name)
        if not existing:
            print(f"FAILED   {d.name}: not installed (run sync first)", file=sys.stderr)
            rc = 1
            continue
        try:
            client.enable_supermetric_on_default_policy(
                existing["id"], d.resource_kinds
            )
            print(f"enabled  {existing['id']}  {d.name}")
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

    pe = sub.add_parser(
        "enable",
        help="enable super metric(s) on the Default Policy "
             "(uses unsupported /internal/ endpoint; Default Policy only)",
    )
    pe.add_argument("paths", nargs="*")
    pe.set_defaults(func=cmd_enable)

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
