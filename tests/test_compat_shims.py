"""M1 compatibility shims: the old ``vcfops_*`` names still work for one release.

Six external SDK adapter repos run ``python3 -m vcfops_packaging ...`` and
``python3 -m vcfops_managementpacks ...`` from their own CI. The shim
packages under ``src/vcfops_<name>/`` must forward to ``vcfcf_<name>`` and
warn exactly once. See ``vcfcf_common/compat_shim.py``.
"""
from __future__ import annotations

import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

OLD_PACKAGES = [
    "vcfops_alerts", "vcfops_common", "vcfops_customgroups",
    "vcfops_dashboards", "vcfops_extractor", "vcfops_managementpacks",
    "vcfops_packaging", "vcfops_reports", "vcfops_supermetrics",
    "vcfops_symptoms",
]


def _run_old_module(module: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    # DeprecationWarning is silenced by default outside __main__; surface it
    # so the test can count it.
    env["PYTHONWARNINGS"] = "default::DeprecationWarning"
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=120,
    )


@pytest.mark.parametrize("old_module", ["vcfops_packaging", "vcfops_managementpacks"])
def test_old_module_help_exits_zero_and_warns_once(old_module):
    new_module = old_module.replace("vcfops_", "vcfcf_", 1)
    result = _run_old_module(old_module, "--help")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "help text should still print through the shim"
    assert result.stderr.count("DeprecationWarning") == 1, result.stderr
    assert new_module in result.stderr, result.stderr


@pytest.mark.parametrize("old_pkg", OLD_PACKAGES)
def test_shim_package_exists_for_every_old_name(old_pkg):
    assert (SRC / old_pkg / "__init__.py").is_file()
    assert (SRC / old_pkg / "__main__.py").is_file()
    assert (SRC / old_pkg.replace("vcfops_", "vcfcf_", 1) / "__init__.py").is_file()


def test_old_submodule_import_is_same_object_as_new():
    """``vcfops_common.client`` must be the very same module as ``vcfcf_common.client``."""
    for name in ("vcfops_common", "vcfops_common.client"):
        sys.modules.pop(name, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        import vcfops_common.client as old_client  # noqa: PLC0415
        import vcfcf_common.client as new_client  # noqa: PLC0415
    assert old_client is new_client
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1
    assert "vcfcf_common" in str(deprecations[0].message)
