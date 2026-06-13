"""Suite-wide guards.

The only logic here is the xdist dist-mode guard: the `real_corpus`
xdist_group (see pytest.ini) only serializes its tests when xdist runs
with --dist=loadgroup. The default --dist=load scatters them across
workers and they race on the real content/ directories (proven: 3
failures). Running parallel without loadgroup is always a mistake, so
fail fast with instructions instead of letting the race surface as
flaky test failures.
"""

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
