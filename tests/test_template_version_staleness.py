"""The template-version staleness signal, which had no coverage at all.

`src/vcfops_packaging/template_version.py` requires a bump whenever
`templates/install.py` (or the other listed files) change. The builders
stamp `CURRENT_TEMPLATE_VERSION` into each zip's `vcfops_manifest.json`
and `check-staleness` compares only that value, so a missed bump makes
every previously built zip report OK while shipping the old installer.
Codex caught exactly that on PR #105: the installer template changed
twice and the constant did not move.

These tests assert the CONTRACT, not the literal value. Pinning the
literal would mean editing a test on every legitimate bump, which trains
people to update the assertion rather than think about it, and a test
that must be edited alongside the thing it guards guards nothing.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pytest

from vcfops_packaging.cli import cmd_check_staleness
from vcfops_packaging.template_version import CURRENT_TEMPLATE_VERSION


class _Args:
    def __init__(self, zip_path):
        self.zip_path = str(zip_path)


def _zip_with_version(tmp_path: Path, version, name="b.zip") -> Path:
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        payload = {"bundle": "b"}
        if version is not None:
            payload["template_version"] = version
        z.writestr("vcfops_manifest.json", json.dumps(payload))
    return p


def test_current_version_is_well_formed():
    """Format is YYYY-MM-DD-N per the module docstring. A typo here is
    silent: it would simply never equal any bundle's value."""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d+", CURRENT_TEMPLATE_VERSION), (
        f"malformed CURRENT_TEMPLATE_VERSION: {CURRENT_TEMPLATE_VERSION!r}"
    )


def test_matching_version_reports_ok(tmp_path, capsys):
    rc = cmd_check_staleness(_Args(_zip_with_version(tmp_path, CURRENT_TEMPLATE_VERSION)))
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("OK --")


def test_older_version_reports_stale_and_exits_nonzero(tmp_path, capsys):
    """The actual PR #105 bug: a zip built before the bump must not read
    as current. rc 1 is what makes this usable in a gate."""
    rc = cmd_check_staleness(_Args(_zip_with_version(tmp_path, "1999-01-01-1")))
    out = capsys.readouterr().out
    assert rc == 1
    assert out.startswith("STALE --")
    assert "1999-01-01-1" in out
    assert CURRENT_TEMPLATE_VERSION in out


def test_missing_marker_is_unknown_not_ok(tmp_path, capsys):
    """Pre-versioning zips must not be silently blessed as current."""
    rc = cmd_check_staleness(_Args(_zip_with_version(tmp_path, None)))
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("UNKNOWN --")
    assert "OK --" not in out


@pytest.mark.parametrize(
    "module_name", ["vcfops_packaging.builder", "vcfops_packaging.discrete_builder"]
)
def test_builders_stamp_the_constant_not_a_literal(module_name):
    """If a builder ever hardcodes a version string, the bump mechanism
    stops working for the zips that builder produces."""
    import importlib

    mod = importlib.import_module(module_name)
    src = Path(mod.__file__).read_text()
    assert '"template_version": CURRENT_TEMPLATE_VERSION' in src, (
        f"{module_name} no longer stamps CURRENT_TEMPLATE_VERSION"
    )
    # No date-stamped literal anywhere in the builder.
    literals = re.findall(r'"\d{4}-\d{2}-\d{2}-\d+"', src)
    assert not literals, f"{module_name} carries hardcoded version literals: {literals}"
