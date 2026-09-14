"""CLI helpers for the --profile flag.

Usage in a CLI module::

    from vcfops_common._profile_cli import add_profile_arg, validate_profile_arg, resolve_profile_from_args

    # In build_parser():
    add_profile_arg(sub_parser, default="prod")   # read-only subcommand
    add_profile_arg(sub_parser, default="devel")  # mutating subcommand

    # In a cmd_*() function:
    profile = resolve_profile_from_args(args)      # returns (profile_str_or_None, default_str)
    client = MyClient.from_env(profile=profile, default_profile=default)
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Tuple

from ._env import available_profiles


def add_profile_arg(
    parser: argparse.ArgumentParser,
    default: str = "prod",
) -> None:
    """Add ``--profile <name>`` to *parser* with the given per-command default.

    The default applies only when BOTH the --profile flag and the
    VCFOPS_PROFILE env var are absent. When VCFOPS_PROFILE is set in the
    environment, the env var overrides the per-command default for all
    invocations in that shell session.
    """
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help=(
            f"Credential profile to use (prod / qa / devel; default: {default!r} "
            "unless VCFOPS_PROFILE env var is set). "
            "Profile credentials are read from VCFOPS_<PROFILE>_HOST/USER/PASSWORD "
            "in .env."
        ),
    )
    # Stash the per-command default so resolve_profile_from_args can retrieve it.
    parser.set_defaults(_profile_default=default)


def validate_profile_arg(args: argparse.Namespace) -> Optional[str]:
    """Validate --profile value against available profiles.

    Returns None if --profile was not supplied (caller should use
    _profile_default + VCFOPS_PROFILE env var resolution in from_env).

    Prints an error and calls sys.exit(1) if the supplied name doesn't
    match any VCFOPS_<P>_HOST entry in the environment.
    """
    from ._env import load_dotenv
    load_dotenv()

    profile = getattr(args, "profile", None)
    if not profile:
        return None

    avail = available_profiles()
    if avail and profile.lower() not in avail:
        print(
            f"ERROR: unknown profile {profile!r}. "
            f"Available profiles: {', '.join(sorted(avail))}",
            file=sys.stderr,
        )
        sys.exit(1)
    return profile


def resolve_profile_from_args(args: argparse.Namespace) -> Tuple[Optional[str], str]:
    """Return (profile, default_profile) from parsed args.

    Validates --profile if supplied. Returns (profile_name_or_None, default).
    Pass both values to XxxClient.from_env(profile=profile, default_profile=default).
    """
    profile = validate_profile_arg(args)
    default = getattr(args, "_profile_default", "prod")
    return profile, default


def client_from_args(args: argparse.Namespace, client_class=None, import_from: str = "vcfops_common.client"):
    """Construct a VCFOpsClient (or subclass) from parsed CLI args.

    Validates --profile (if supplied) against available profiles, then
    calls client_class.from_env() with the resolved profile and per-command
    default. Exits with an error message if the profile is unknown or
    required env vars are missing.

    Args:
        args: Parsed argparse namespace.
        client_class: The client class to instantiate. If None, imports
            VCFOpsClient from import_from.
        import_from: Module path to import VCFOpsClient from if client_class
            is None. The module must export VCFOpsClient and VCFOpsError
            at its top level.
    """
    profile, default = resolve_profile_from_args(args)

    if client_class is None:
        import importlib
        mod = importlib.import_module(import_from)
        client_class = mod.VCFOpsClient  # type: ignore[attr-defined]
        error_class = getattr(mod, "VCFOpsError", Exception)
    else:
        import importlib
        mod = importlib.import_module(import_from)
        error_class = getattr(mod, "VCFOpsError", Exception)

    try:
        return client_class.from_env(profile=profile, default_profile=default)
    except Exception as e:
        if isinstance(e, error_class):
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        raise
