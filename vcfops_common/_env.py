"""Shared .env loader and credential-profile resolver for VCF Ops clients.

Walks up from the current working directory looking for a `.env` file
and loads KEY=VALUE lines into `os.environ` without overwriting vars
that are already set (so a real shell export always wins over the
file). Intentionally dependency-free — we parse the trivial subset
of .env syntax we actually use:

    # comment
    KEY=value
    KEY="value with spaces"
    KEY='value'

No variable interpolation, no `export` prefix handling beyond
stripping it, no multiline values. This exists so every caller of
`VCFOpsClient.from_env()` gets credentials automatically, removing
the need for agents to shell-source `.env` before invoking Python
(which triggers Claude Code's shell-injection prompt).

## Profile system

Credentials are grouped into named profiles (prod / qa / devel).
Each profile is a set of env vars prefixed ``VCFOPS_<PROFILE>_``:

    VCFOPS_PROD_HOST      VCFOPS_PROD_USER      VCFOPS_PROD_PASSWORD
    VCFOPS_PROD_AUTH_SOURCE  VCFOPS_PROD_VERIFY_SSL

Active profile resolution order (first wins):
1. Explicit ``profile`` argument passed to ``resolve_profile_credentials()``.
2. ``VCFOPS_PROFILE`` environment variable.
3. Caller-supplied ``default`` argument (per-command default).
4. ``"prod"`` if nothing else matches.

No fallback to the legacy flat ``VCFOPS_HOST`` / ``VCFOPS_USER`` /
``VCFOPS_PASSWORD`` vars — this is a hard cutover.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, NamedTuple, Set

_LOADED: bool = False


def load_dotenv(start: Optional[Path] = None) -> Optional[Path]:
    """Find and load the nearest `.env` walking up from `start` (cwd by
    default). Idempotent — subsequent calls are no-ops. Returns the
    path loaded, or None if no `.env` was found.
    """
    global _LOADED
    if _LOADED:
        return None
    _LOADED = True  # set early so failures don't cause retry storms

    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        env_file = candidate / ".env"
        if env_file.is_file():
            _parse_into_environ(env_file)
            return env_file
    return None


def _parse_into_environ(path: Path) -> None:
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # Strip inline `# comment` only when the value is unquoted.
        # Quoted values keep `#` literal.
        if val and val[0] not in ("'", '"'):
            hash_idx = val.find("#")
            if hash_idx != -1:
                val = val[:hash_idx].rstrip()
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


# ---------------------------------------------------------------------------
# Profile resolver
# ---------------------------------------------------------------------------

class ProfileCredentials(NamedTuple):
    host: str
    user: str
    password: str
    auth_source: str
    verify_ssl: bool
    profile_name: str  # the resolved profile name, for diagnostics


def available_profiles() -> Set[str]:
    """Return the set of profile names for which VCFOPS_<P>_HOST is defined.

    Useful for --profile arg validation and "did you mean?" error messages.
    Loads .env first so the caller doesn't have to remember to do it.
    """
    load_dotenv()
    profiles: Set[str] = set()
    for key in os.environ:
        if key.startswith("VCFOPS_") and key.endswith("_HOST"):
            middle = key[len("VCFOPS_"):-len("_HOST")]
            if middle and middle.isidentifier():
                profiles.add(middle.lower())
    return profiles


def resolve_profile_credentials(
    profile: Optional[str] = None,
    *,
    default: str = "prod",
) -> ProfileCredentials:
    """Return credentials for the resolved profile.

    Resolution order:
      1. ``profile`` argument if provided and non-empty.
      2. ``VCFOPS_PROFILE`` env var (loaded from .env automatically).
      3. ``default`` argument.
      4. ``"prod"`` as the hard fallback.

    Profile names are case-insensitive on input; env-var lookup uses
    the upper-cased form (e.g. ``devel`` → ``VCFOPS_DEVEL_HOST``).

    Raises ``ValueError`` if a required key for the resolved profile is
    missing, with a message naming the missing var and listing available
    profiles.
    """
    load_dotenv()

    # Resolve the active profile name.
    if profile and profile.strip():
        active = profile.strip().upper()
    elif os.environ.get("VCFOPS_PROFILE", "").strip():
        active = os.environ["VCFOPS_PROFILE"].strip().upper()
    else:
        active = (default or "prod").upper()

    prefix = f"VCFOPS_{active}_"

    def _get(suffix: str, required: bool = True) -> str:
        key = prefix + suffix
        val = os.environ.get(key, "")
        if required and not val:
            avail = sorted(available_profiles())
            hint = f"  Available profiles: {', '.join(avail)}" if avail else ""
            raise ValueError(
                f"Profile {active.lower()!r} is missing required env var {key}. "
                f"Check .env.{hint}"
            )
        return val

    host = _get("HOST")
    user = _get("USER")
    password = _get("PASSWORD")
    auth_source = _get("AUTH_SOURCE", required=False) or "Local"
    verify_ssl_raw = _get("VERIFY_SSL", required=False)
    verify_ssl = verify_ssl_raw.lower() != "false" if verify_ssl_raw else True

    return ProfileCredentials(
        host=host,
        user=user,
        password=password,
        auth_source=auth_source,
        verify_ssl=verify_ssl,
        profile_name=active.lower(),
    )
