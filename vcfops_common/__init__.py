"""vcfops_common — shared utilities for all vcfops_* packages.

VCFOpsClient and VCFOpsError are lazy-loaded from .client so that
importing this package (which happens whenever any vcfops_* CLI module
loads _profile_cli) does NOT pull in `requests` at import time.
This keeps offline subcommands (validate, build-buildkit, build-sdk,
pak-compare) working in environments that have only PyYAML installed.
"""
from ._env import load_dotenv, resolve_profile_credentials, available_profiles
from ._profile_cli import add_profile_arg, validate_profile_arg, resolve_profile_from_args, client_from_args

__all__ = [
    "VCFOpsClient", "VCFOpsError",
    "load_dotenv", "resolve_profile_credentials", "available_profiles",
    "add_profile_arg", "validate_profile_arg", "resolve_profile_from_args", "client_from_args",
]

# Lazy-load VCFOpsClient and VCFOpsError so that importing this package
# does not pull in `requests` until a network-capable command actually
# needs a client.  Python 3.7+ module __getattr__ handles this cleanly.
def __getattr__(name: str):
    if name in ("VCFOpsClient", "VCFOpsError"):
        from . import client as _client  # noqa: PLC0415
        globals()["VCFOpsClient"] = _client.VCFOpsClient
        globals()["VCFOpsError"] = _client.VCFOpsError
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
