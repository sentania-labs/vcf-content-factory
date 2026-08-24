"""Suite-wide guards.

Two of them:

1. The xdist dist-mode guard: the `real_corpus` xdist_group (see
   pyproject.toml's [tool.pytest.ini_options]) only serializes its
   tests when xdist runs with --dist=loadgroup. The default
   --dist=load scatters them across workers and they race on the real
   content/ directories (proven: 3 failures). Running parallel without
   loadgroup is always a mistake, so fail fast with instructions
   instead of letting the race surface as flaky test failures.

2. The `.env` walk boundary (see `_bound_env_discovery_to_tmp`): the
   doctor and the credential wizard both resolve `.env` by walking UP
   from the repo root, exactly as `_env.load_dotenv()` does. Tests hand
   them a tmp_path root, whose parents are this machine's real
   directories, so a contributor with a stray `/tmp/.env` (or one in
   pytest's basetemp parent) sees tests fail for a reason that has
   nothing to do with their change: 22 in test_common_setup.py and 3 in
   test_common_doctor.py, measured. The fixture bounds the walk to
   pytest's basetemp so only fixture-created files are ever found.
"""

import sys
from pathlib import Path

import pytest


def pytest_configure(config):
    # Both options exist only when pytest-xdist is installed; default-safe
    # lookups keep plain pytest working on clones without xdist.
    try:
        numprocesses = config.getoption("numprocesses", default=None)
        dist = config.getoption("dist", default="no")
    except (ValueError, KeyError):
        return
    if numprocesses and dist != "loadgroup":
        raise pytest.UsageError(
            "Parallel runs require --dist=loadgroup: the real_corpus "
            "xdist_group must serialize on one worker or its tests race "
            "on the real content/ directories. "
            "Use: pytest -n auto --dist=loadgroup  (see tests/README.md)"
        )


@pytest.fixture(autouse=True)
def _bound_env_discovery_to_tmp(monkeypatch, tmp_path_factory):
    """Stop the upward `.env` search at pytest's basetemp.

    `doctor.find_env_file` walks from the given root to `/`, which is
    correct in production (a `.env` above the checkout is a supported
    setup) and wrong under test: the "parents" of a tmp_path root belong
    to whoever is running the suite. Anything found outside basetemp is
    this machine's file, not the test's fixture, so it reads as absent.

    Wrapping rather than reimplementing keeps the real walk under test;
    only its result is filtered. Both modules are patched because
    `setup_credentials` imports the function by name.
    """
    # Every test module that needs it puts <repo>/src on sys.path at
    # import time, but this fixture is autouse for the WHOLE suite, so it
    # cannot assume some other module already did. Same insert, and a
    # degraded no-op rather than an ImportError if the tree is unusual:
    # a path fixture must never be the reason an unrelated test errors.
    src = str(Path(__file__).resolve().parents[1] / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from vcfops_common import doctor as _doctor
        from vcfops_common import setup_credentials as _setup
    except ImportError:  # pragma: no cover - defensive
        return

    base = tmp_path_factory.getbasetemp().resolve()
    real = _doctor.find_env_file

    def bounded(start: Path):
        found = real(start)
        if found is None:
            return None
        try:
            found.resolve().relative_to(base)
        except (ValueError, OSError):
            return None
        return found

    monkeypatch.setattr(_doctor, "find_env_file", bounded)
    monkeypatch.setattr(_setup, "find_env_file", bounded)
