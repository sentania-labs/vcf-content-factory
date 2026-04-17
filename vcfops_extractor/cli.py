"""argparse CLI for vcfops_extractor.

Subcommands:
  extract dashboard  -- walk a dashboard and its deps, emit YAML + manifest
  list-dashboards    -- list dashboards available on the lab instance

No interactive prompts anywhere in this module.  All missing required flags
produce a clear error message and a non-zero exit code.  The /extract slash
command is the interactive UX; this module is the scriptable workhorse.

Connection:
  --host / VCFOPS_HOST    hostname or IP of the VCF Ops instance
  --user / VCFOPS_USER    admin-privileged username
  --password / VCFOPS_PASSWORD  password

Credentials are read from the environment (sourced from .env automatically
by the _env loader).  The CLI never prompts for missing credentials --
it aborts with a clear error naming the missing variable.
"""
from __future__ import annotations

import argparse
import sys


# ---------------------------------------------------------------------------
# Top-level parser + subcommand dispatch
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m vcfops_extractor",
        description=(
            "Reverse-engineering toolkit for VCF Operations content.\n"
            "\n"
            "Pulls a live dashboard (and its dependency graph) from a VCF Ops\n"
            "instance and emits factory-shape YAML under bundles/third_party/<slug>/\n"
            "plus a bundle manifest that vcfops_packaging build can consume.\n"
            "\n"
            "Connection is controlled by env vars or --host/--user/--password flags.\n"
            "No interactive prompts -- missing required flags abort with a clear error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global connection flags (apply to all subcommands)
    conn = p.add_argument_group("connection (defaults from env / .env)")
    conn.add_argument(
        "--host", metavar="HOST",
        help="VCF Ops hostname or IP (default: VCFOPS_HOST env var)",
    )
    conn.add_argument(
        "--user", metavar="USER",
        help="VCF Ops username (default: VCFOPS_USER env var)",
    )
    conn.add_argument(
        "--password", metavar="PASSWORD",
        help="VCF Ops password (default: VCFOPS_PASSWORD env var)",
    )
    conn.add_argument(
        "--no-verify-ssl", action="store_true",
        help="Disable SSL certificate verification",
    )

    sub = p.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    sub.required = True

    # --- extract -----------------------------------------------------------
    extract_p = sub.add_parser(
        "extract",
        help="Extract content from a live VCF Ops instance",
        description=(
            "Extract content (dashboard, views, super metrics) from a live VCF Ops\n"
            "instance and emit factory-shape YAML + a bundle manifest.\n"
            "\n"
            "Phase 1 supports 'dashboard' only.  See also: extract --help."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    extract_sub = extract_p.add_subparsers(dest="extract_type", metavar="TYPE")
    extract_sub.required = True

    # extract dashboard
    dash_p = extract_sub.add_parser(
        "dashboard",
        help="Extract a dashboard and its dependency graph (views, super metrics)",
        description=(
            "Walk a dashboard's dependency graph (dashboard -> views -> super metrics,\n"
            "plus SM->SM recursion) and emit factory-shape YAML + a bundle manifest.\n"
            "\n"
            "Required: one of --dashboard-id or --dashboard-name; --bundle-slug;\n"
            "          --author; --license; --description-file\n"
            "\n"
            "In --dry-run mode the dependency walk is printed without writing files.\n"
            "\n"
            "Examples:\n"
            "  python -m vcfops_extractor extract dashboard \\\n"
            "    --dashboard-name 'IDPS Planner' \\\n"
            "    --bundle-slug idps-planner \\\n"
            "    --author 'Scott Bowe' \\\n"
            "    --license Proprietary \\\n"
            "    --description-file bundles/third_party/idps-planner/DESCRIPTION.md \\\n"
            "    --source-url https://sentania.net \\\n"
            "    --source-version 3.2 \\\n"
            "    --yes\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_dashboard_flags(dash_p)

    # --- list-dashboards ---------------------------------------------------
    list_p = sub.add_parser(
        "list-dashboards",
        help="List dashboards available on the lab instance (name + UUID)",
        description=(
            "Query the live VCF Ops instance for all available dashboards and print\n"
            "each one as 'UUID  name' for use in subsequent extract commands.\n"
            "\n"
            "The --folder flag filters to dashboards under a specific UI folder.\n"
            "\n"
            "Examples:\n"
            "  python -m vcfops_extractor list-dashboards\n"
            "  python -m vcfops_extractor list-dashboards --folder 'IDPS'\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    list_p.add_argument(
        "--folder", metavar="FOLDER",
        help="Filter to dashboards under this folder name (substring match)",
    )

    return p


def _add_dashboard_flags(p: argparse.ArgumentParser) -> None:
    """Add all flags for the 'extract dashboard' subcommand."""

    # Identification (one of id or name required)
    id_group = p.add_argument_group("dashboard identification (one required)")
    id_group.add_argument(
        "--dashboard-id", metavar="UUID",
        help="Dashboard UUID (preferred; unambiguous)",
    )
    id_group.add_argument(
        "--dashboard-name", metavar="NAME",
        help="Dashboard display name (resolved via list-dashboards; must match exactly)",
    )

    # Required attribution
    req = p.add_argument_group("attribution (required)")
    req.add_argument(
        "--bundle-slug", metavar="SLUG", required=True,
        help=(
            "Short identifier for the bundle, e.g. 'idps-planner'.  "
            "Used as the directory name under bundles/third_party/ and "
            "the manifest filename (bundles/third_party/<slug>.yaml)."
        ),
    )
    req.add_argument(
        "--author", metavar="AUTHOR", required=True,
        help="Attribution line for the bundle README, e.g. 'Scott Bowe'",
    )
    req.add_argument(
        "--license", metavar="LICENSE", required=True,
        help=(
            "SPDX identifier or free-form license name, "
            "e.g. 'MIT', 'Apache-2.0', 'Proprietary', 'CC-BY-4.0'"
        ),
    )
    req.add_argument(
        "--description-file", metavar="PATH", required=True,
        help=(
            "Path to a Markdown file containing the long-form bundle description.  "
            "Written by the /extract slash command to "
            "bundles/third_party/<slug>/DESCRIPTION.md before invoking this CLI."
        ),
    )

    # Optional provenance
    prov = p.add_argument_group("provenance (optional)")
    prov.add_argument(
        "--source-url", metavar="URL",
        help="URL where the source dashboard can be found or referenced",
    )
    prov.add_argument(
        "--source-version", metavar="VERSION",
        help="Version string for the source dashboard, e.g. '3.2'",
    )

    # Output control
    out = p.add_argument_group("output control")
    out.add_argument(
        "--output-dir", metavar="DIR", default="bundles/third_party",
        help="Root directory for emitted YAML and manifest (default: bundles/third_party)",
    )

    # Per-type filters
    filt = p.add_argument_group("dependency filters")
    filt.add_argument(
        "--skip-supermetric", metavar="NAME", action="append", default=[],
        help=(
            "Skip a super metric by name (may be repeated).  Use when a dependency "
            "already exists in the factory repo or should not be redistributed."
        ),
    )
    filt.add_argument(
        "--include-customgroup", metavar="NAME", action="append", default=[],
        help=(
            "Force-include a custom group by name (may be repeated).  "
            "Phase 1: custom group extraction is not yet implemented; this flag "
            "is accepted but has no effect (a WARN is emitted instead)."
        ),
    )

    # Run mode
    mode = p.add_argument_group("run mode")
    mode.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Walk the dependency graph and print the plan without writing any files.  "
            "Use this to preview what would be extracted before committing."
        ),
    )
    mode.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt and proceed immediately",
    )


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _resolve_credentials(args) -> tuple[str, str, str, bool]:
    """Resolve host/user/password from flags then env vars.

    Returns (host, user, password, verify_ssl).
    Aborts with a clear error if any required value is missing.
    """
    from vcfops_supermetrics._env import load_dotenv
    load_dotenv()

    import os
    host = args.host or os.environ.get("VCFOPS_HOST", "")
    user = args.user or os.environ.get("VCFOPS_USER", "")
    password = args.password or os.environ.get("VCFOPS_PASSWORD", "")
    verify_ssl = not getattr(args, "no_verify_ssl", False)
    if os.environ.get("VCFOPS_VERIFY_SSL", "").lower() == "false":
        verify_ssl = False

    missing = []
    if not host:
        missing.append("VCFOPS_HOST (or --host)")
    if not user:
        missing.append("VCFOPS_USER (or --user)")
    if not password:
        missing.append("VCFOPS_PASSWORD (or --password)")
    if missing:
        print(
            f"ERROR: missing required connection parameters: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "  Set them in the .env file at the repo root or pass them as flags.",
            file=sys.stderr,
        )
        sys.exit(1)
    return host, user, password, verify_ssl


def cmd_extract_dashboard(args) -> int:
    """Handler for: python -m vcfops_extractor extract dashboard ..."""
    from .extractor import extract_dashboard

    if not args.dashboard_id and not args.dashboard_name:
        print(
            "ERROR: one of --dashboard-id or --dashboard-name is required",
            file=sys.stderr,
        )
        return 1

    from pathlib import Path
    desc_path = Path(args.description_file)
    if not args.dry_run and not desc_path.exists():
        print(
            f"ERROR: --description-file not found: {desc_path}",
            file=sys.stderr,
        )
        print(
            "  Create this file with the bundle's long-form description before running.",
            file=sys.stderr,
        )
        return 1

    host, user, password, verify_ssl = _resolve_credentials(args)

    return extract_dashboard(
        host=host,
        user=user,
        password=password,
        verify_ssl=verify_ssl,
        dashboard_id=args.dashboard_id or None,
        dashboard_name=args.dashboard_name or None,
        bundle_slug=args.bundle_slug,
        author=args.author,
        license_=args.license,
        description_file=desc_path,
        source_url=args.source_url or "",
        source_version=args.source_version or "",
        output_dir=args.output_dir,
        skip_supermetrics=set(args.skip_supermetric or []),
        include_customgroups=list(args.include_customgroup or []),
        dry_run=args.dry_run,
        yes=args.yes,
    )


def cmd_list_dashboards(args) -> int:
    """Handler for: python -m vcfops_extractor list-dashboards ..."""
    from .extractor import list_dashboards

    host, user, password, verify_ssl = _resolve_credentials(args)
    return list_dashboards(
        host=host,
        user=user,
        password=password,
        verify_ssl=verify_ssl,
        folder_filter=getattr(args, "folder", None) or "",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand == "list-dashboards":
        sys.exit(cmd_list_dashboards(args))
    elif args.subcommand == "extract":
        if args.extract_type == "dashboard":
            sys.exit(cmd_extract_dashboard(args))
        else:
            print(f"ERROR: unknown extract type: {args.extract_type}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"ERROR: unknown subcommand: {args.subcommand}", file=sys.stderr)
        sys.exit(1)
