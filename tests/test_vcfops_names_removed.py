"""The ``vcfops_*`` import names are gone (issue #159).

M1 (2026-09-14) renamed the ten framework packages to ``vcfcf_*`` and kept
``src/vcfops_*/`` as one-release compatibility shims. They are removed; an
old import or ``python3 -m vcfops_<x>`` must now fail loudly instead of
forwarding. Runs in a fresh interpreter so nothing imported by another
test can satisfy the import.
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


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          env=env, cwd=str(SRC.parent), timeout=60)


@pytest.mark.parametrize("name", OLD_NAMES)
def test_old_import_name_fails(name):
    r = _run("-c", f"import {name}")
    assert r.returncode != 0
    assert "ModuleNotFoundError" in r.stderr and name in r.stderr


def test_old_module_cli_fails():
    r = _run("-m", "vcfops_packaging", "--help")
    assert r.returncode != 0
    assert "No module named vcfops_packaging" in r.stderr


def test_no_shim_directories_or_machinery_remain():
    assert sorted(p.name for p in SRC.glob("vcfops_*")) == []
    assert not (SRC / "vcfcf_common" / "compat_shim.py").exists()


def test_new_names_still_import():
    r = _run("-c", "import vcfcf_core, vcfcf_common, vcfcf_packaging, vcfcf_managementpacks")
    assert r.returncode == 0, r.stderr
