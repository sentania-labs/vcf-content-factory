"""CLI: validate / list / sync / delete super metrics."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List

from .client import VCFOpsClient, VCFOpsError
from .loader import SuperMetricDef, SuperMetricValidationError, load_dir, load_file

# Dep walker is imported lazily inside cmd_sync to avoid import-time errors
# when vcfops_dashboards is absent (rare, but keeps the package self-contained).

DEFAULT_DIR = "content/supermetrics"
SM_ENABLE_ATTEMPTS = 3
SM_ENABLE_VERIFY_DELAY = 2


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

    # Slug-uniqueness check across content/ and third_party/*/
    if not args.paths:
        try:
            from vcfops_packaging.project import check_slug_uniqueness
            errors = check_slug_uniqueness(
                content_type="supermetrics",
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

    # --- Dependency walker: check OOTB metric collection state for any
    #     metrics referenced in the SM formulas being synced. ---------
    rc = _run_dep_walker_for_sms(
        client,
        defs,
        auto_enable_metrics=getattr(args, "auto_enable_metrics", False),
        skip_metric_check=getattr(args, "skip_metric_check", False),
    )
    return rc


def _run_dep_walker_for_sms(
    client: VCFOpsClient,
    defs: List[SuperMetricDef],
    auto_enable_metrics: bool = False,
    skip_metric_check: bool = False,
) -> int:
    """Run the dep walker for an SM-only sync (no views or dashboards).

    Checks OOTB metric references inside SM formulas. SM-to-SM references
    within this batch are handled by the normal enable step; pre-existing
    SMs referenced by formula are also checked.
    """
    try:
        from vcfops_common.dep_walker import walk_and_check
    except ImportError as e:
        print(f"WARN  dep walker unavailable: {e}", file=sys.stderr)
        return 0

    sm_name_map = {d.name: d.id for d in defs}
    walk = walk_and_check(
        client=client,
        supermetrics=defs,
        views=[],
        dashboards=[],
        customgroups=[],  # SM-only sync; no customgroup refs to validate
        auto_enable_metrics=auto_enable_metrics,
        skip_metric_check=skip_metric_check,
        sm_name_map=sm_name_map,
    )
    for level, msg in walk.messages:
        if level == "ERROR":
            print(f"DEP-{level}  {msg}", file=sys.stderr)
        else:
            print(f"DEP-{level}  {msg}")
    if not walk.ok:
        print("sync incomplete: dependency check found errors (see DEP-ERROR above)",
              file=sys.stderr)
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

    # Phase 1: resolve all SM names to server IDs
    unverified = {}  # {sm_id: (def, name)}
    for d in defs:
        existing = client.find_by_name(d.name)
        if not existing:
            print(f"FAILED   {d.name}: not installed (run sync first)",
                  file=sys.stderr)
            rc = 1
            continue
        unverified[existing["id"]] = (d, d.name)

    if not unverified:
        return rc

    # Phase 2: assign + verify with retries
    for attempt in range(1, SM_ENABLE_ATTEMPTS + 1):
        assign_errors = {}
        for sm_id, (d, name) in list(unverified.items()):
            try:
                client.enable_supermetric_on_default_policy(
                    sm_id, d.resource_kinds)
            except VCFOpsError as e:
                assign_errors[sm_id] = str(e)

        time.sleep(SM_ENABLE_VERIFY_DELAY)

        try:
            policy_xml = client.export_default_policy_xml()
            status = client.verify_supermetrics_enabled(
                policy_xml, list(unverified.keys()))
        except VCFOpsError as e:
            print(f"WARN  policy export failed on attempt {attempt}: {e}",
                  file=sys.stderr)
            if attempt < SM_ENABLE_ATTEMPTS:
                continue
            for sm_id, (d, name) in unverified.items():
                print(f"FAILED   {name}: could not verify (export error)",
                      file=sys.stderr)
            rc = 1
            break

        still_pending = {}
        for sm_id, (d, name) in list(unverified.items()):
            if sm_id in assign_errors:
                print(f"FAILED   {name}: {assign_errors[sm_id]}",
                      file=sys.stderr)
                rc = 1
            elif status.get(sm_id):
                print(f"enabled  {sm_id}  {name}")
            else:
                if attempt < SM_ENABLE_ATTEMPTS:
                    still_pending[sm_id] = (d, name)
                else:
                    print(
                        f"FAILED   {name}: not confirmed in Default Policy "
                        f"after {SM_ENABLE_ATTEMPTS} attempts",
                        file=sys.stderr)
                    rc = 1

        unverified = still_pending
        if not unverified:
            break
        print(f"  [{attempt}/{SM_ENABLE_ATTEMPTS}] {len(unverified)} SM(s) "
              f"not verified, retrying in {SM_ENABLE_VERIFY_DELAY}s...")

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
    ps.add_argument(
        "--auto-enable-metrics",
        action="store_true",
        default=False,
        help=(
            "Enable OOTB metrics with defaultMonitored=false on the Default Policy. "
            "Default: warn and flag, but do not modify the policy."
        ),
    )
    ps.add_argument(
        "--skip-metric-check",
        action="store_true",
        default=False,
        help=(
            "Skip the OOTB metric defaultMonitored check entirely. "
            "Use when you know the target policy already covers these metrics."
        ),
    )
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
