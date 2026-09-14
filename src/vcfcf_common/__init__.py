"""vcfcf_common: shared utilities for all vcfcf_* packages.

Nothing is imported eagerly (M2 row 3). The ``.env`` and profile machinery
(``load_dotenv``, ``resolve_profile_credentials``, ``available_profiles``,
the ``--profile`` CLI helpers) and the network client (``VCFOpsClient``,
``VCFOpsError``, which pulls in ``requests``) are all resolved lazily by
module ``__getattr__`` on first use. Importing ``vcfcf_common.provenance``
or ``vcfcf_common.dep_walker`` for an offline load therefore touches neither
``.env`` nor ``requests``, and offline subcommands (validate, build-buildkit,
build-sdk, pak-compare) keep working in environments that have only PyYAML
installed.
"""

__all__ = [
    "VCFOpsClient", "VCFOpsError",
    "load_dotenv", "resolve_profile_credentials", "available_profiles",
    "add_profile_arg", "validate_profile_arg", "resolve_profile_from_args", "client_from_args",
]

_ENV_NAMES = ("load_dotenv", "resolve_profile_credentials", "available_profiles")
_PROFILE_CLI_NAMES = ("add_profile_arg", "validate_profile_arg", "resolve_profile_from_args", "client_from_args")


def __getattr__(name: str):
    if name in ("VCFOpsClient", "VCFOpsError"):
        from . import client as _client  # noqa: PLC0415
        globals()["VCFOpsClient"] = _client.VCFOpsClient
        globals()["VCFOpsError"] = _client.VCFOpsError
        return globals()[name]
    if name in _ENV_NAMES:
        from . import _env  # noqa: PLC0415
        for n in _ENV_NAMES:
            globals()[n] = getattr(_env, n)
        return globals()[name]
    if name in _PROFILE_CLI_NAMES:
        from . import _profile_cli  # noqa: PLC0415
        for n in _PROFILE_CLI_NAMES:
            globals()[n] = getattr(_profile_cli, n)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
