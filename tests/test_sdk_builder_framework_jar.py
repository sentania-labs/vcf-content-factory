"""Tests for vcfcf_managementpacks.sdk_builder._ensure_framework_jar().

Coverage (TOOLSET GAP fix — silent-staleness mode found in synology build 23
containment proof; see the tooling brief this test accompanies):

  - jar absent, source tree present         -> jar is built.
  - jar present but STALE vs. source tree   -> jar is rebuilt (not silently
    skipped). Verified two ways: (1) the rebuilt jar's bytecode reflects the
    newer source content, and (2) _find_stale_framework_sources correctly
    identifies which source files are newer than the jar.
  - jar present and FRESH vs. source tree   -> no-op (no javac/jar subprocess
    invoked — asserted via monkeypatched subprocess.run that raises if
    called).
  - jar present, source tree absent (runtime-only distribution) -> no-op;
    staleness cannot be checked without the source tree, existing jar used
    as-is.
  - jar absent, source tree absent          -> SdkBuildError (unchanged
    pre-existing behavior).

These tests are hermetic: they monkeypatch the module-level
``_ADAPTER_RUNTIME_DIR`` / ``_ADAPTER_FRAMEWORK_SRC_DIR`` constants to point
at tmp_path fixtures and never touch the real
vcfcf_managementpacks/adapter_runtime/ or adapter_framework/src/ trees.
They compile trivial, dependency-free Java sources with the real javac/jar
tools on PATH (skipped if unavailable) rather than mocking subprocess, so the
staleness-triggers-a-real-rebuild claim is actually exercised.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder


pytestmark = pytest.mark.skipif(
    shutil.which("javac") is None or shutil.which("jar") is None,
    reason="javac/jar not available on PATH",
)


def _write_marker_source(src_dir: Path, value: str) -> Path:
    """Write a trivial, dependency-free Java source carrying ``value``.

    No references to any SDK/framework type — compiles against an empty
    (even invalid-content) classpath entry without error.
    """
    pkg_dir = src_dir / "com" / "vcfcf" / "testfw"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    marker = pkg_dir / "Marker.java"
    marker.write_text(
        "package com.vcfcf.testfw;\n"
        "public final class Marker {\n"
        f"    public static final String VALUE = \"{value}\";\n"
        "}\n",
        encoding="utf-8",
    )
    return marker


def _jar_contains(jar_path: Path, needle: str) -> bool:
    with zipfile.ZipFile(jar_path) as zf:
        for name in zf.namelist():
            if name.endswith(".class"):
                if needle.encode("ascii") in zf.read(name):
                    return True
    return False


def _make_runtime_dir(tmp_path: Path) -> Path:
    """Create a fake adapter_runtime/ with a stub SDK jar (unused by Marker.java)."""
    runtime_dir = tmp_path / "adapter_runtime"
    runtime_dir.mkdir()
    # Marker.java has no external references, so the SDK "jar" only needs to
    # exist and be findable by the vrops-adapters-sdk-*.jar glob and be a
    # well-formed (if empty) zip — javac opens -cp entries as zips even when
    # nothing in them is referenced.
    stub_jar = runtime_dir / "vrops-adapters-sdk-2.2.jar"
    with zipfile.ZipFile(stub_jar, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    return runtime_dir


@pytest.fixture()
def patched_dirs(tmp_path, monkeypatch):
    """Monkeypatch sdk_builder's module-level path constants to tmp_path."""
    runtime_dir = _make_runtime_dir(tmp_path)
    src_dir = tmp_path / "adapter_framework" / "src"
    src_dir.mkdir(parents=True)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", src_dir)
    monkeypatch.delenv("VCFCF_SDK_JAR", raising=False)
    return runtime_dir, src_dir


def test_jar_absent_is_built(patched_dirs):
    runtime_dir, src_dir = patched_dirs
    _write_marker_source(src_dir, "v1")
    output_jar = runtime_dir / "vcfcf-adapter-base.jar"
    assert not output_jar.is_file()

    sdk_builder._ensure_framework_jar()

    assert output_jar.is_file()
    assert _jar_contains(output_jar, "v1")


def test_jar_stale_vs_src_is_rebuilt(patched_dirs):
    runtime_dir, src_dir = patched_dirs
    output_jar = runtime_dir / "vcfcf-adapter-base.jar"

    # Build v1 jar first.
    _write_marker_source(src_dir, "v1")
    sdk_builder._ensure_framework_jar()
    assert _jar_contains(output_jar, "v1")
    assert not _jar_contains(output_jar, "v2")

    # Edit source to v2, forcing its mtime strictly after the jar's mtime.
    time.sleep(1.05)  # coarse filesystem mtime granularity on some platforms
    _write_marker_source(src_dir, "v2")

    stale = sdk_builder._find_stale_framework_sources(
        output_jar, sorted(src_dir.rglob("*.java"))
    )
    assert len(stale) == 1  # staleness correctly detected before rebuild

    sdk_builder._ensure_framework_jar()

    # The silent-downgrade failure mode: assert the rebuild actually
    # happened and the jar now reflects the newer source, not the old one.
    assert _jar_contains(output_jar, "v2")
    assert not _jar_contains(output_jar, "v1")


def test_jar_fresh_is_a_true_noop(patched_dirs, monkeypatch):
    runtime_dir, src_dir = patched_dirs
    output_jar = runtime_dir / "vcfcf-adapter-base.jar"

    _write_marker_source(src_dir, "v1")
    sdk_builder._ensure_framework_jar()
    assert output_jar.is_file()

    before_bytes = output_jar.read_bytes()
    before_mtime = output_jar.stat().st_mtime

    # Jar is fresh (built after src, no src edits since). Assert no
    # subprocess is invoked — a real rebuild would call javac/jar via
    # subprocess.run; raising on any call proves the no-op path is taken.
    def _forbidden_run(*args, **kwargs):
        raise AssertionError(
            "subprocess.run was invoked on a fresh jar — staleness check "
            "regressed into an unconditional rebuild"
        )

    monkeypatch.setattr(subprocess, "run", _forbidden_run)

    sdk_builder._ensure_framework_jar()

    assert output_jar.read_bytes() == before_bytes
    assert output_jar.stat().st_mtime == before_mtime


def test_jar_present_src_absent_is_noop(tmp_path, monkeypatch):
    """Runtime-only distribution: jar shipped, no adapter_framework/src/ present."""
    runtime_dir = _make_runtime_dir(tmp_path)
    output_jar = runtime_dir / "vcfcf-adapter-base.jar"
    output_jar.write_bytes(b"PK\x03\x04prebuilt-jar-bytes")

    missing_src_dir = tmp_path / "adapter_framework" / "src"  # never created
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", missing_src_dir)

    before = output_jar.read_bytes()
    sdk_builder._ensure_framework_jar()
    assert output_jar.read_bytes() == before  # untouched


def test_jar_absent_src_absent_raises(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "adapter_runtime"
    runtime_dir.mkdir()
    missing_src_dir = tmp_path / "adapter_framework" / "src"  # never created
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", missing_src_dir)

    with pytest.raises(sdk_builder.SdkBuildError):
        sdk_builder._ensure_framework_jar()


# ---------------------------------------------------------------------------
# Framework version stamp in the jar manifest (issue #214)
# ---------------------------------------------------------------------------


def _manifest_attrs(jar: Path) -> dict:
    with zipfile.ZipFile(jar) as zf:
        raw = zf.read("META-INF/MANIFEST.MF").decode("utf-8")
    attrs = {}
    for line in raw.replace("\r\n", "\n").replace("\n ", "").splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            attrs[k] = v
    return attrs


def test_built_jar_manifest_carries_factory_version_and_commit(patched_dirs, monkeypatch):
    """Factory mode: version from buildkit.py's BUILDKIT_VERSION, commit from git."""
    from vcfcf_managementpacks.buildkit import BUILDKIT_VERSION

    runtime_dir, src_dir = patched_dirs
    _write_marker_source(src_dir, "v1")
    monkeypatch.setattr(sdk_builder, "_framework_source_commit", lambda: "abc123def")
    sdk_builder._ensure_framework_jar()

    jar = runtime_dir / "vcfcf-adapter-base.jar"
    attrs = _manifest_attrs(jar)
    assert attrs["Implementation-Title"] == "vcfcf-adapter-base"
    assert attrs["Implementation-Version"] == BUILDKIT_VERSION
    assert attrs["X-Vcfcf-Source-Commit"] == "abc123def"
    assert _jar_contains(jar, "v1")  # classes still packaged
    assert sdk_builder._framework_jar_label(jar) == (
        f"vcfcf-adapter-base {BUILDKIT_VERSION} (source abc123def)"
    )


def test_kit_mode_stamps_kit_version_and_commit_without_git(tmp_path, monkeypatch):
    """Kit mode (VERSION file beside sdk_builder): never asks git, which in a
    pak repo would answer with the pak's commit."""
    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (kit / "SOURCE_COMMIT").write_text("feedface\n", encoding="utf-8")
    monkeypatch.setattr(sdk_builder, "_HERE", kit)

    real_which = shutil.which
    monkeypatch.setattr(
        sdk_builder.shutil, "which",
        lambda name, *a, **k: None if name == "git" else real_which(name, *a, **k),
    )
    assert sdk_builder._framework_version() == "9.9.9"
    assert sdk_builder._framework_source_commit() == "feedface"

    (kit / "SOURCE_COMMIT").unlink()
    assert sdk_builder._framework_source_commit() == "unknown"


def test_factory_version_read_from_buildkit_constant():
    from vcfcf_managementpacks.buildkit import BUILDKIT_VERSION

    assert sdk_builder._framework_version() == BUILDKIT_VERSION


def test_label_for_a_jar_built_before_the_stamp(tmp_path):
    jar = tmp_path / "vcfcf-adapter-base.jar"
    with zipfile.ZipFile(jar, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nCreated-By: 17\n")
    assert "unversioned" in sdk_builder._framework_jar_label(jar)
    bad = tmp_path / "not-a-jar.jar"
    bad.write_bytes(b"nope")
    assert "no readable manifest" in sdk_builder._framework_jar_label(bad)
