"""build-buildkit must run with only PyYAML installed.

The Publish sdk-buildkit workflow (.github/workflows/publish-buildkit.yml)
installs nothing but PyYAML, by design. No kit published since 1.0.12;
the v1.0.19 tag's publish failed: #248 added ``_factory_source_commit()``, which
imports ``sdk_builder``, whose module-level
``from vcfcf_supermetrics import crossref`` ran ``vcfcf_supermetrics/__init__``,
which imported the REST client and so ``requests``. Every unit test runs in
the full dev venv, where ``requests`` is installed, so nothing caught it.

These tests run the real CLI in a subprocess whose ``sys.meta_path`` refuses
``requests``, the same condition as the publish runner.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"

# Installed before anything else runs: any import of requests (or a
# submodule) raises exactly as it would on a runner without the package.
_BLOCK_REQUESTS = (
    "import sys\n"
    "class _NoRequests:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name == 'requests' or name.startswith('requests.'):\n"
    "            raise ModuleNotFoundError(\"No module named 'requests'\", name=name)\n"
    "        return None\n"
    "sys.meta_path.insert(0, _NoRequests())\n"
    "for _m in [m for m in sys.modules if m == 'requests' or m.startswith('requests.')]:\n"
    "    del sys.modules[_m]\n"
)


def _run(code: str, *args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_REQUESTS + code, *args],
        capture_output=True, text=True, env=env, cwd=str(cwd), timeout=300,
    )


def test_the_blocker_blocks():
    result = _run("import requests\n")
    assert result.returncode != 0
    assert "No module named 'requests'" in result.stderr


def test_build_buildkit_runs_without_requests(tmp_path):
    ref = tmp_path / "ref" / "vcfcf_sdk_compliance.1.0.0.1.pak"
    ref.parent.mkdir()
    with zipfile.ZipFile(ref, "w") as zf:
        zf.writestr("manifest.txt", "reference pak fixture\n")
    out = tmp_path / "out"

    result = _run(
        "import runpy\n"
        "sys.argv = ['vcfcf_managementpacks'] + sys.argv[1:]\n"
        "runpy.run_module('vcfcf_managementpacks', run_name='__main__')\n",
        "build-buildkit", "--output", str(out), "--version", "9.9.9",
        "--reference-pak", str(ref),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    tarball = out / "sdk-buildkit-9.9.9.tgz"
    assert tarball.is_file()
    assert (out / "sdk-buildkit-9.9.9.tgz.sha256").is_file()

    # The kit it produced also imports without requests.
    kit_root = tmp_path / "kit"
    with tarfile.open(tarball) as tf:
        if sys.version_info >= (3, 12):
            tf.extractall(kit_root, filter="data")
        else:
            tf.extractall(kit_root)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(kit_root)
    kit = subprocess.run(
        [sys.executable, "-c", _BLOCK_REQUESTS + "import sdk_buildkit.sdk_builder\n"
         "import sdk_buildkit.pak_compare\nprint('kit ok')\n"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60,
    )
    assert kit.returncode == 0, kit.stderr
    assert "kit ok" in kit.stdout


def test_every_vcfcf_package_init_imports_without_requests():
    """A package ``__init__`` that eagerly imports its REST client breaks
    every offline submodule import under it (``pkg.loader`` runs
    ``pkg/__init__`` first). Clients resolve lazily instead."""
    pkgs = sorted(
        p.name for p in SRC.iterdir()
        if p.is_dir() and p.name.startswith("vcfcf_") and (p / "__init__.py").is_file()
    )
    assert "vcfcf_supermetrics" in pkgs and "vcfcf_managementpacks" in pkgs
    result = _run(
        "import importlib\n"
        "for name in sys.argv[1:]:\n"
        "    importlib.import_module(name)\n"
        "import vcfcf_managementpacks.sdk_builder, vcfcf_managementpacks.buildkit\n"
        "assert 'requests' not in sys.modules\n"
        "print('imports ok')\n",
        *pkgs,
    )
    assert result.returncode == 0, result.stderr
    assert "imports ok" in result.stdout
