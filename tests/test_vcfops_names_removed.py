"""The ``vcfops_*`` import names are gone (issue #159).

M1 (2026-09-14) renamed the ten framework packages to ``vcfcf_*`` and kept
``src/vcfops_*/`` as one-release compatibility shims. They are removed.

A pull deletes only tracked files, so an upgraded clone can keep
``src/vcfops_*/__pycache__/`` (and other ignored files). Python then
imports ``vcfops_x`` as an empty NAMESPACE package instead of raising. The
removal guarantees no shim CODE, not an absent directory: an old import
either fails or yields a namespace package with nothing in it, and
``python3 -m vcfops_x`` fails either way. The doctor reports the leftover
directories (``vcfcf_common.doctor.leftover_shim_dirs``). Runs in a fresh
interpreter so nothing imported by another test can satisfy the import.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

OLD_NAMES = [
    "vcfops_core",
    "vcfops_alerts", "vcfops_common", "vcfops_customgroups",
    "vcfops_dashboards", "vcfops_extractor", "vcfops_managementpacks",
    "vcfops_packaging", "vcfops_reports", "vcfops_supermetrics",
    "vcfops_symptoms",
]

#: Prints SHIM when the name resolves to real code, else the outcome.
_PROBE = """
import importlib, importlib.util, sys
name = sys.argv[1]
spec = importlib.util.find_spec(name)
if spec is None:
    print("MISSING")
elif spec.origin in (None, "namespace"):  # a namespace package: no file behind it
    mod = importlib.import_module(name)
    public = [a for a in dir(mod) if not a.startswith("__")]
    print("NAMESPACE" if not public else "SHIM " + ",".join(public))
else:
    print("SHIM " + str(spec.origin))
"""


def _run(*args: str, extra_path: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (extra_path, str(SRC)) if p)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          env=env, cwd=str(SRC.parent), timeout=60)


@pytest.mark.parametrize("name", OLD_NAMES)
def test_old_import_name_carries_no_code(name):
    r = _run("-c", _PROBE, name)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() in ("MISSING", "NAMESPACE"), r.stdout


def test_old_module_cli_fails():
    r = _run("-m", "vcfops_packaging", "--help")
    assert r.returncode != 0
    assert "vcfops_packaging" in r.stderr


def test_no_shim_code_or_machinery_remains():
    code = sorted(str(p.relative_to(SRC)) for p in SRC.glob("vcfops_*/*.py"))
    assert code == []
    assert not (SRC / "vcfcf_common" / "compat_shim.py").exists()


def test_upgraded_clone_with_leftover_pycache(tmp_path):
    """The case a pull leaves behind: a directory holding only __pycache__."""
    cache = tmp_path / "vcfops_common" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "__init__.cpython-312.pyc").write_bytes(b"stale")
    r = _run("-c", _PROBE, "vcfops_common", extra_path=str(tmp_path))
    assert r.stdout.strip() == "NAMESPACE", (r.stdout, r.stderr)
    r = _run("-m", "vcfops_common", extra_path=str(tmp_path))
    assert r.returncode != 0


def test_new_names_still_import():
    r = _run("-c", "import vcfcf_core, vcfcf_common, vcfcf_packaging, vcfcf_managementpacks")
    assert r.returncode == 0, r.stderr
