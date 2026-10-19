"""A bare `pytest` from the repo root collects only factory tests (issue #207).

reference/references/ holds cloned vendor repos (the integration SDK clone
ships its own tests that fail on import here) and content/sdk-adapters/
holds the gitignored pak repos. The repo's pytest config must keep both out
of collection, for bare `pytest` and for an explicit `pytest .`.

Hermetic: copies the real pyproject.toml into a tmp tree that mimics the
layout, then runs pytest --collect-only there in a subprocess.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_BAD = "import module_that_does_not_exist_207\n\ndef test_bad():\n    pass\n"


@pytest.fixture
def fake_repo(tmp_path):
    shutil.copy(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    files = {
        "tests/test_ok.py": "def test_ok():\n    pass\n",
        # A factory fixture dir that happens to be named reference is kept.
        "tests/fixtures/reference/test_kept.py": "def test_kept():\n    pass\n",
        "reference/references/vendor-sdk/tests/test_vendor.py": _BAD,
        "content/sdk-adapters/somepak/tests/test_pak.py": _BAD,
    }
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("args", [[], ["."]], ids=["bare", "dot"])
def test_root_collection_skips_vendor_and_pak_clones(fake_repo, args):
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", *args],
        cwd=fake_repo, capture_output=True, text=True, timeout=120,
    )
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "tests/test_ok.py::test_ok" in out
    assert "tests/fixtures/reference/test_kept.py::test_kept" in out
    assert "vendor-sdk" not in out
    assert "somepak" not in out
