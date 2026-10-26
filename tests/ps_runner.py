"""Shared PowerShell runner for the install.ps1 behaviour tests.

Two environment switches, both for CI:

- ``VCFCF_PS_EXE``: the interpreter to run (default ``pwsh``). Set it to
  ``powershell`` on a ``windows-latest`` runner to run the same tests under
  Windows PowerShell 5.1, the runtime RULE-018 says the shipped installer must
  keep working on and the factory's POSIX hosts cannot provide.
- ``VCFCF_REQUIRE_PWSH=1``: a missing interpreter FAILS the test instead of
  skipping it. Without it a CI image with no PowerShell reports every
  behaviour test as skipped and stays green (the gap review W1 found).

Windows notes: arguments are passed as a list (no shell quoting), paths come
from pathlib, and output is decoded as UTF-8 with ``errors="replace"``.
Harnesses that print non-ASCII pin ``[Console]::OutputEncoding`` to UTF-8
themselves; 5.1 otherwise writes the OEM code page to a redirected stdout.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Mapping, Optional

import pytest

PS_EXE = os.environ.get("VCFCF_PS_EXE", "").strip() or "pwsh"
REQUIRE_PS = os.environ.get("VCFCF_REQUIRE_PWSH", "").strip() == "1"

#: Works for pwsh 7 and powershell.exe 5.1 alike. -ExecutionPolicy is
#: accepted and ignored off Windows; on Windows it keeps a machine policy
#: of Restricted/AllSigned from refusing the unsigned test files.
PS_ARGS = ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]


def ps_available() -> bool:
    return shutil.which(PS_EXE) is not None


def require_ps() -> None:
    """Skip (default) or fail (VCFCF_REQUIRE_PWSH=1) when there is no PowerShell."""
    if ps_available():
        return
    msg = f"PowerShell interpreter {PS_EXE!r} not found on PATH"
    if REQUIRE_PS:
        pytest.fail(msg + " and VCFCF_REQUIRE_PWSH=1 makes that a failure")
    pytest.skip(msg)


@pytest.fixture
def ps_exe() -> str:
    require_ps()
    return PS_EXE


def run_ps_file(script: Path, args: Iterable[str] = (), *, cwd: Optional[Path] = None,
                env: Optional[Mapping[str, str]] = None,
                timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a .ps1 file with the configured interpreter, decoding as UTF-8."""
    return subprocess.run(
        [PS_EXE, *PS_ARGS, "-File", str(script), *[str(a) for a in args]],
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
