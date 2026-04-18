"""Shared .env loader for VCF Ops clients.

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
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

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
