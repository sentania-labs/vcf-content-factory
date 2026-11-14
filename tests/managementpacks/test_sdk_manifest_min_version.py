"""manifest.txt vcops_minimum_version follows the oldest supported line.

Owner decision 2026-11-14: the minimum is 8.18.x (tested on 8.18.7), not
8.18.7 and not the old hardcoded 8.0.0, and it is derived from
_SDK_COMPAT_LINES so retiring a line moves it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import vcfcf_managementpacks.sdk_builder as sb  # noqa: E402
from vcfcf_managementpacks.sdk_project import SdkProjectDef, _derive_entry_class  # noqa: E402


def _project():
    return SdkProjectDef(
        name="Min Version Probe", version="1.0.0", build_number=1,
        adapter_kind="minver_probe", description="d", tier=2, dependencies=[],
        entry_class=_derive_entry_class("minver_probe"), source_path=Path("/dev/null"),
    )


def test_manifest_minimum_is_the_oldest_line_major_minor():
    assert sb._oldest_supported_line() == "8.18.7"
    manifest = json.loads(sb._generate_outer_manifest(_project()))
    assert manifest["vcops_minimum_version"] == "8.18.0"


def test_minimum_follows_the_compat_lines(monkeypatch):
    remaining = tuple(line for line in sb._SDK_COMPAT_LINES if not line.key.startswith("8."))
    assert remaining, "expected a 9.x line in _SDK_COMPAT_LINES"
    monkeypatch.setattr(sb, "_SDK_COMPAT_LINES", remaining)
    oldest = sb._oldest_supported_line()
    major, minor = oldest.split(".")[:2]
    assert sb._pak_minimum_ops_version() == f"{major}.{minor}.0"
    assert json.loads(sb._generate_outer_manifest(_project()))["vcops_minimum_version"] == (
        f"{major}.{minor}.0")


def test_the_tested_line_gates_are_unchanged():
    """The Section / floor gates still key on the tested line, not the
    widened manifest minimum."""
    assert sb._oldest_supported_line() != sb._pak_minimum_ops_version()
