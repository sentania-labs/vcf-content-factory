"""Tests for the SDK pak version-line guardrail.

Convention under test (see vcfops_managementpacks/sdk_builder.py
_stamp_build_version / _is_release_build):

  - Hand-built / local dev preview builds (the default) stamp
    ``0.0.0.<build_number>`` everywhere, regardless of adapter.yaml's
    declared ``version:``.
  - Only an explicit release opt-in (VCFCF_RELEASE_BUILD=1, set by the
    --release CLI flag) uses adapter.yaml's real version.

This guarantees a hand-built pak is never version-indistinguishable from
a CI release build.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vcfops_managementpacks.sdk_builder import (
    _generate_outer_manifest,
    _generate_version_txt,
    _is_release_build,
    _stamp_build_version,
)
from vcfops_managementpacks.sdk_project import SdkProjectDef, _derive_entry_class


def _make_project(
    version: str = "1.0.0",
    build_number: int = 23,
    adapter_kind: str = "test_adapter",
) -> SdkProjectDef:
    return SdkProjectDef(
        name="Test Adapter",
        version=version,
        build_number=build_number,
        adapter_kind=adapter_kind,
        description="Test adapter for version-stamp packaging.",
        tier=2,
        dependencies=[],
        entry_class=_derive_entry_class(adapter_kind),
        source_path=Path("/dev/null"),
    )


@pytest.fixture(autouse=True)
def _clean_release_env(monkeypatch):
    """Every test starts with the release opt-in env var unset."""
    monkeypatch.delenv("VCFCF_RELEASE_BUILD", raising=False)


# ---------------------------------------------------------------------------
# _is_release_build()
# ---------------------------------------------------------------------------

def test_release_build_defaults_false():
    assert _is_release_build() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "Yes"])
def test_release_build_true_values(monkeypatch, value):
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", value)
    assert _is_release_build() is True


@pytest.mark.parametrize("value", ["0", "false", "", "no", "garbage"])
def test_release_build_false_values(monkeypatch, value):
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", value)
    assert _is_release_build() is False


# ---------------------------------------------------------------------------
# _stamp_build_version() — default (dev preview) behavior
# ---------------------------------------------------------------------------

def test_default_build_stamps_0_0_0_build_number():
    project = _make_project(version="1.0.0", build_number=23)
    declared = _stamp_build_version(project, release_build=False)

    assert declared == "1.0.0"          # returns the original declared version
    assert project.version == "0.0.0"   # but overwrites project.version in place
    assert project.build_number == 23   # build_number is untouched


def test_default_build_ignores_declared_version_value():
    # Regardless of what adapter.yaml declares, default build is always 0.0.0.N
    for declared in ("1.0.0", "2.5.3", "9.9.9"):
        project = _make_project(version=declared, build_number=7)
        _stamp_build_version(project, release_build=False)
        assert project.version == "0.0.0"
        assert project.pak_filename == "vcfcf_sdk_test_adapter.0.0.0.7.pak"


# ---------------------------------------------------------------------------
# _stamp_build_version() — release opt-in behavior
# ---------------------------------------------------------------------------

def test_release_opt_in_uses_declared_adapter_yaml_version():
    project = _make_project(version="1.2.3", build_number=42)
    declared = _stamp_build_version(project, release_build=True)

    assert declared == "1.2.3"
    assert project.version == "1.2.3"   # unchanged — real adapter.yaml version
    assert project.build_number == 42


# ---------------------------------------------------------------------------
# Consistency across filename / manifest / version.txt surfaces
# ---------------------------------------------------------------------------

def test_default_build_surfaces_agree_on_0_0_0_n():
    project = _make_project(version="3.1.4", adapter_kind="vcfcf_widget", build_number=11)
    _stamp_build_version(project, release_build=False)

    # Filename
    assert project.pak_filename == "vcfcf_sdk_widget.0.0.0.11.pak"

    # Outer/inner manifest.txt "version" field
    import json
    manifest = json.loads(_generate_outer_manifest(project))
    assert manifest["version"] == "0.0.0.11"

    # conf/version.txt Major/Minor/Implementation-Version
    version_txt = _generate_version_txt(project)
    lines = dict(
        line.split("=", 1) for line in version_txt.splitlines() if "=" in line
    )
    assert lines["Major-Version"] == "0"
    assert lines["Minor-Version"] == "0"
    assert lines["Implementation-Version"] == f"0.{project.build_number}"


def test_release_build_surfaces_agree_on_declared_version():
    project = _make_project(version="3.1.4", adapter_kind="vcfcf_widget", build_number=11)
    _stamp_build_version(project, release_build=True)

    assert project.pak_filename == "vcfcf_sdk_widget.3.1.4.11.pak"

    import json
    manifest = json.loads(_generate_outer_manifest(project))
    assert manifest["version"] == "3.1.4.11"

    version_txt = _generate_version_txt(project)
    lines = dict(
        line.split("=", 1) for line in version_txt.splitlines() if "=" in line
    )
    assert lines["Major-Version"] == "3"
    assert lines["Minor-Version"] == "1"
    assert lines["Implementation-Version"] == f"4.{project.build_number}"


def test_one_build_all_surfaces_agree(monkeypatch):
    """End-to-end-ish: simulate a single build_sdk_pak-style flow (load ->
    stamp -> read every downstream surface) and assert filename, manifest,
    and version.txt never disagree on which version line was stamped —
    covering both the default and the release-opt-in path in one pass.
    """
    import json

    for release_build, expected_line in ((False, "0.0.0"), (True, "9.8.7")):
        project = _make_project(version="9.8.7", adapter_kind="vcfcf_agree", build_number=5)
        _stamp_build_version(project, release_build=release_build)

        filename_version = project.pak_filename.split(".", 2)[-1].rsplit(".", 1)[0]
        # pak_filename = vcfcf_sdk_agree.<version>.<build>.pak
        # Extract the "<version>" segment directly instead of guessing split counts.
        stem = project.pak_filename[len("vcfcf_sdk_agree."):-len(f".{project.build_number}.pak")]
        assert stem == expected_line

        manifest = json.loads(_generate_outer_manifest(project))
        assert manifest["version"] == f"{expected_line}.{project.build_number}"

        version_txt = _generate_version_txt(project)
        lines = dict(
            l.split("=", 1) for l in version_txt.splitlines() if "=" in l
        )
        major, minor, patch = expected_line.split(".")
        assert lines["Major-Version"] == major
        assert lines["Minor-Version"] == minor
        assert lines["Implementation-Version"] == f"{patch}.{project.build_number}"
