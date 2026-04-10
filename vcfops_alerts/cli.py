"""CLI: validate / list / sync / delete / enable / disable alert definitions."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .client import VCFOpsAlertsClient, VCFOpsAlertsError
from .loader import AlertDef, AlertValidationError, load_dir, load_file

DEFAULT_ALERT_DIR = "alerts"
DEFAULT_SYMPTOM_DIR = "symptoms"


def _collect_alerts(paths: List[str]) -> List[AlertDef]:
    if not paths:
        return load_dir(DEFAULT_ALERT_DIR)
    defs: List[AlertDef] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            defs.extend(load_dir(path))
        else:
            defs.append(load_file(path))
    return defs


def _collect_repo_symptom_names() -> set:
    """Return the set of symptom names defined in the local symptoms/ dir.

    Used for cross-reference validation during validate command.
    Missing symptoms/ dir is not an error — some alerts reference only
    built-in symptoms.
    """
    symptom_dir = Path(DEFAULT_SYMPTOM_DIR)
    if not symptom_dir.exists():
        return set()
    try:
        from vcfops_symptoms.loader import load_dir as load_symptoms
        return {sd.name for sd in load_symptoms(symptom_dir)}
    except Exception:
        return set()


def cmd_validate(args) -> int:
    try:
        defs = _collect_alerts(args.paths)
    except AlertValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    repo_symptom_names = _collect_repo_symptom_names()
    rc = 0
    for d in defs:
        try:
            d.validate_symptom_refs(repo_symptom_names)
        except AlertValidationError as e:
            print(f"WARN: {e}", file=sys.stderr)
            # Cross-ref warnings are non-fatal at validate time — alerts
            # may reference built-in symptoms that we cannot enumerate
            # without a live instance. The sync command fails hard on
            # unresolvable symptoms.

    if rc == 0:
        print(f"OK: {len(defs)} alert definition(s) valid")
        for d in defs:
            print(
                f"  - {d.name}  "
                f"({d.adapter_kind}/{d.resource_kind}, "
                f"criticality={d.criticality}, badge={d.impact_badge})  "
                f"({d.source_path})"
            )
    return rc


def cmd_list(args) -> int:
    client = VCFOpsAlertsClient.from_env()
    for ad in client.list_alerts():
        print(f"{ad.get('id')}  {ad.get('name')}")
    return 0


def cmd_sync(args) -> int:
    try:
        defs = _collect_alerts(args.paths)
    except AlertValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("nothing to sync", file=sys.stderr)
        return 1

    client = VCFOpsAlertsClient.from_env()

    # Resolve all symptom names to ids in one pass before syncing alerts.
    print("resolving symptom definitions on instance...")
    try:
        sym_map = client.get_symptom_name_to_id_map()
    except VCFOpsAlertsError as e:
        print(f"FAILED   symptom resolution: {e}", file=sys.stderr)
        return 1

    rc = 0
    for d in defs:
        try:
            wire = d.to_wire(sym_map)
        except AlertValidationError as e:
            print(f"FAILED   {d.name}: {e}", file=sys.stderr)
            rc = 1
            continue
        try:
            action, result = client.upsert_alert(wire)
            print(f"{action:8s}  {result.get('id')}  {d.name}")
        except VCFOpsAlertsError as e:
            print(f"FAILED   {d.name}: {e}", file=sys.stderr)
            rc = 1
    return rc


def cmd_enable(args) -> int:
    client = VCFOpsAlertsClient.from_env()
    ad = client.find_by_name(args.name)
    if not ad:
        print(f"not found: {args.name}", file=sys.stderr)
        return 1
    client.enable_alert(ad["id"])
    print(f"enabled  {ad['id']}  {args.name}")
    return 0


def cmd_disable(args) -> int:
    client = VCFOpsAlertsClient.from_env()
    ad = client.find_by_name(args.name)
    if not ad:
        print(f"not found: {args.name}", file=sys.stderr)
        return 1
    client.disable_alert(ad["id"])
    print(f"disabled {ad['id']}  {args.name}")
    return 0


def cmd_delete(args) -> int:
    client = VCFOpsAlertsClient.from_env()
    ad = client.find_by_name(args.name)
    if not ad:
        print(f"not found: {args.name}", file=sys.stderr)
        return 1
    client.delete_alert(ad["id"])
    print(f"deleted  {ad['id']}  {args.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_alerts")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML definitions")
    pv.add_argument("paths", nargs="*")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list alert definitions on the instance")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("sync", help="create/update alert definitions from YAML")
    ps.add_argument("paths", nargs="*")
    ps.set_defaults(func=cmd_sync)

    pe = sub.add_parser(
        "enable",
        help="enable an alert definition by name (public API endpoint)",
    )
    pe.add_argument("name")
    pe.set_defaults(func=cmd_enable)

    pdi = sub.add_parser(
        "disable",
        help="disable an alert definition by name",
    )
    pdi.add_argument("name")
    pdi.set_defaults(func=cmd_disable)

    pd = sub.add_parser("delete", help="delete an alert definition by name")
    pd.add_argument("name")
    pd.set_defaults(func=cmd_delete)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except VCFOpsAlertsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
