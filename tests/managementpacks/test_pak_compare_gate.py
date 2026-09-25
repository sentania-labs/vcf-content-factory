"""pak-compare is a gate: exit codes and build failure (issue #181).

Before this fix every pak-compare path reported BLOCKING findings and then
returned 0: the factory CLI (`cli.cmd_pak_compare`), the buildkit's own
`python3 -m sdk_buildkit pak-compare` (`buildkit._KIT_MAIN`), and the
post-build step inside `build-sdk` (`sdk_builder._run_pak_compare`), which
printed the findings and swallowed every error.  Reproduced: a pak with
manifest.txt deleted reported "2 BLOCKING" and exited 0.

Covered here:
  - factory CLI and kit CLI: 0 on a clean compare, 1 on any BLOCKING, 1 when
    the compare cannot run (unreadable pak, compare raising).
  - build-sdk's gate: BLOCKING fails the build by default, warn-only
    downgrades it on a dev build, a missing reference pak fails a release
    build and is skipped on a dev build, and warn-only is refused on a
    release build.
  - javac is invoked with -proc:none (sdk-runtime#1).
  - the buildkit tarball gets a sha256sum-format sidecar.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import cli, sdk_builder
from vcfcf_managementpacks.sdk_builder import PakCompareGateError, SdkBuildError


# ---------------------------------------------------------------------------
# Synthetic paks
# ---------------------------------------------------------------------------

def _adapters_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "fixture_kind/conf/describe.xml",
            '<?xml version="1.0"?><AdapterKind key="fixture_kind" nameKey="1" '
            'version="1"><ResourceKinds><ResourceKind key="w" nameKey="2" '
            'type="1"/></ResourceKinds></AdapterKind>',
        )
        zf.writestr("fixture_kind.jar", b"x")
    return buf.getvalue()


def _write_pak(path: Path, *, manifest: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        if manifest:
            zf.writestr("manifest.txt", json.dumps({
                "display_name": "fixture",
                "name": "fixture",
                "version": "1.0.0.1",
                "adapter_kinds": ["fixture_kind"],
                "adapters": ["adapters.zip"],
                "pak_validation_script": {"script": ""},
                "vcops_minimum_version": "8.10.0",
            }))
        zf.writestr("adapters.zip", _adapters_zip())
    return path


def _write_mpb_pak(path: Path) -> Path:
    """An MPB-shaped (Tier 1, _adapter3 layout) pak: an unrelated reference."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "mpb_other_adapter3/conf/describe.xml",
            '<?xml version="1.0"?><AdapterKind key="mpb_other" nameKey="1" '
            'version="1"><ResourceKinds><ResourceKind key="w" nameKey="2" '
            'type="1"/></ResourceKinds></AdapterKind>',
        )
        zf.writestr("mpb_other_adapter3/conf/export.json", "{}")
        zf.writestr("mpb_adapter3.jar", b"x")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.txt", json.dumps({
            "display_name": "mpb", "name": "mpb_other", "version": "1.0.0.1",
            "adapter_kinds": ["mpb_other"], "adapters": ["adapters.zip"],
            "pak_validation_script": {"script": "validate.py"},
            "vcops_minimum_version": "8.10.0",
        }))
        zf.writestr("adapters.zip", buf.getvalue())
        zf.writestr("validate.py", "")
        zf.writestr("resources/resources.properties", "")
    return path


def _mixed_reference_dir(base: Path) -> Path:
    """The reviewer's repro shape: a passing SDK reference plus an MPB one
    that sorts FIRST alphabetically and reports BLOCKING for an SDK pak."""
    from vcfcf_managementpacks.pak_compare import compare_paks

    d = base / "mixed_refs"
    d.mkdir()
    sdk_ref = _write_pak(d / "zz_sdk_ref.pak")
    mpb_ref = _write_mpb_pak(d / "aa_mpb_ref.pak")
    probe = _write_pak(base / "probe.pak")
    # Preconditions, so the test cannot pass vacuously.
    assert compare_paks(probe, mpb_ref).blocking(), "MPB ref must block an SDK pak"
    assert not compare_paks(probe, sdk_ref).blocking()
    return d


@pytest.fixture
def paks(tmp_path):
    good = _write_pak(tmp_path / "good.pak")
    ref = _write_pak(tmp_path / "ref.pak")
    no_manifest = _write_pak(tmp_path / "no_manifest.pak", manifest=False)
    corrupt = tmp_path / "corrupt.pak"
    corrupt.write_bytes(b"this is not a zip")
    return {"good": good, "ref": ref, "no_manifest": no_manifest, "corrupt": corrupt}


def _args(factory, reference=None, reference_dir=None, output=None):
    return argparse.Namespace(
        factory_pak=str(factory),
        reference_pak=str(reference) if reference else None,
        reference_dir=str(reference_dir) if reference_dir else None,
        output=output,
    )


# ---------------------------------------------------------------------------
# Factory CLI: cmd_pak_compare
# ---------------------------------------------------------------------------

class TestFactoryCliExitCodes:

    def test_clean_compare_exits_zero(self, paks, capsys):
        assert cli.cmd_pak_compare(_args(paks["good"], paks["ref"])) == 0
        assert "pak-compare gate: PASS" in capsys.readouterr().err

    def test_blocking_exits_nonzero(self, paks, capsys):
        """The reported repro: manifest.txt deleted, 2 BLOCKING, used to exit 0."""
        rc = cli.cmd_pak_compare(_args(paks["no_manifest"], paks["ref"]))
        captured = capsys.readouterr()
        assert rc == 1
        assert "2 BLOCKING" in captured.out
        assert "pak-compare gate: FAIL (2 BLOCKING" in captured.err

    def test_blocking_exits_nonzero_with_report_file(self, paks, tmp_path):
        out = tmp_path / "report.txt"
        rc = cli.cmd_pak_compare(
            _args(paks["no_manifest"], paks["ref"], output=str(out))
        )
        assert rc == 1
        assert "BLOCKING" in out.read_text(), "the report is still written on failure"

    def test_unreadable_factory_pak_exits_nonzero(self, paks):
        assert cli.cmd_pak_compare(_args(paks["corrupt"], paks["ref"])) == 1

    def test_directory_mode_any_blocking_exits_nonzero(self, paks, tmp_path):
        ref_dir = tmp_path / "refs"
        ref_dir.mkdir()
        _write_pak(ref_dir / "a.pak")
        _write_pak(ref_dir / "b.pak")
        assert cli.cmd_pak_compare(_args(paks["good"], reference_dir=ref_dir)) == 0
        assert cli.cmd_pak_compare(
            _args(paks["no_manifest"], reference_dir=ref_dir)
        ) == 1

    def test_directory_mode_gates_on_closest_reference(self, paks, tmp_path, capsys):
        """An unrelated MPB reference must not fail an SDK pak (WARNING 1)."""
        mixed = _mixed_reference_dir(tmp_path)
        assert cli.cmd_pak_compare(_args(paks["good"], reference_dir=mixed)) == 0
        assert "closest reference zz_sdk_ref.pak" in capsys.readouterr().err
        assert cli.cmd_pak_compare(
            _args(paks["no_manifest"], reference_dir=mixed)
        ) == 1

    def test_compare_raising_exits_nonzero(self, paks, monkeypatch, capsys):
        import vcfcf_managementpacks.pak_compare as pc

        def _boom(*_a, **_k):
            raise RuntimeError("synthetic compare crash")

        monkeypatch.setattr(pc, "compare_paks", _boom)
        assert cli.cmd_pak_compare(_args(paks["good"], paks["ref"])) == 1
        assert "comparison did not run" in capsys.readouterr().err

    def test_missing_reference_exits_nonzero(self, paks, tmp_path):
        assert cli.cmd_pak_compare(
            _args(paks["good"], tmp_path / "absent.pak")
        ) == 1


# ---------------------------------------------------------------------------
# Buildkit CLI (python3 -m sdk_buildkit pak-compare), run as CI runs it
# ---------------------------------------------------------------------------

@pytest.fixture
def kit_env(tmp_path):
    """A minimal assembled kit: __init__, __main__, and pak_compare.py."""
    from vcfcf_managementpacks.buildkit import _FACTORY_SOURCES, _KIT_INIT, _KIT_MAIN

    pkg = tmp_path / "kit" / "sdk_buildkit"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(_KIT_INIT, encoding="utf-8")
    (pkg / "__main__.py").write_text(_KIT_MAIN, encoding="utf-8")
    (pkg / "pak_compare.py").write_bytes(_FACTORY_SOURCES["pak_compare.py"].read_bytes())

    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path / "kit")
    return env


def _run_kit(env, *argv):
    return subprocess.run(
        [sys.executable, "-m", "sdk_buildkit", "pak-compare", *map(str, argv)],
        capture_output=True, text=True, env=env, cwd=tempfile.gettempdir(),
        timeout=60,
    )


class TestKitCliExitCodes:

    def test_clean_compare_exits_zero(self, kit_env, paks):
        result = _run_kit(kit_env, paks["good"], paks["ref"])
        assert result.returncode == 0, result.stderr

    def test_blocking_exits_nonzero(self, kit_env, paks):
        result = _run_kit(kit_env, paks["no_manifest"], paks["ref"])
        assert result.returncode == 1, result.stdout + result.stderr
        assert "2 BLOCKING" in result.stdout

    def test_directory_mode_blocking_exits_nonzero(self, kit_env, paks, tmp_path):
        """The template workflow's invocation shape (--reference-dir)."""
        ref_dir = tmp_path / "reference_paks"
        ref_dir.mkdir()
        _write_pak(ref_dir / "ref.pak")
        ok = _run_kit(kit_env, paks["good"], "--reference-dir", ref_dir)
        bad = _run_kit(kit_env, paks["no_manifest"], "--reference-dir", ref_dir)
        assert ok.returncode == 0, ok.stderr
        assert bad.returncode == 1, bad.stdout + bad.stderr

    def test_unreadable_factory_pak_exits_nonzero(self, kit_env, paks):
        result = _run_kit(kit_env, paks["corrupt"], paks["ref"])
        assert result.returncode == 1

    def test_directory_mode_gates_on_closest_reference(self, kit_env, paks, tmp_path):
        mixed = _mixed_reference_dir(tmp_path)
        ok = _run_kit(kit_env, paks["good"], "--reference-dir", mixed)
        assert ok.returncode == 0, ok.stdout + ok.stderr
        assert "closest reference zz_sdk_ref.pak" in ok.stderr
        bad = _run_kit(kit_env, paks["no_manifest"], "--reference-dir", mixed)
        assert bad.returncode == 1


# ---------------------------------------------------------------------------
# build-sdk's post-build gate: sdk_builder._run_pak_compare
# ---------------------------------------------------------------------------

@pytest.fixture
def ref_dir(tmp_path, monkeypatch, paks):
    d = tmp_path / "reference_paks"
    d.mkdir()
    _write_pak(d / "ref.pak")
    monkeypatch.setattr(sdk_builder, "_REFERENCES_DIR", d)
    return d


class TestBuildGate:

    def test_clean_pak_passes(self, ref_dir, paks):
        sdk_builder._run_pak_compare(paks["good"])
        sdk_builder._run_pak_compare(paks["good"], release_build=True)

    def test_blocking_fails_by_default(self, ref_dir, paks):
        with pytest.raises(PakCompareGateError, match="2 BLOCKING"):
            sdk_builder._run_pak_compare(paks["no_manifest"])

    def test_blocking_fails_release(self, ref_dir, paks):
        with pytest.raises(PakCompareGateError):
            sdk_builder._run_pak_compare(paks["no_manifest"], release_build=True)

    def test_gate_error_is_a_build_error(self):
        """Every caller maps SdkBuildError to exit 1; the gate must ride that."""
        assert issubclass(PakCompareGateError, SdkBuildError)

    def test_warn_only_does_not_fail(self, ref_dir, paks, capsys):
        sdk_builder._run_pak_compare(paks["no_manifest"], warn_only=True)
        assert "warn-only" in capsys.readouterr().err

    def test_compare_crash_fails(self, ref_dir, paks, monkeypatch):
        import vcfcf_managementpacks.pak_compare as pc

        def _boom(*_a, **_k):
            raise RuntimeError("synthetic compare crash")

        monkeypatch.setattr(pc, "compare_paks", _boom)
        with pytest.raises(PakCompareGateError, match="failed to run"):
            sdk_builder._run_pak_compare(paks["good"])
        # warn-only downgrades a crash too (dev builds only)
        sdk_builder._run_pak_compare(paks["good"], warn_only=True)

    def test_gates_on_closest_not_alphabetical_reference(self, tmp_path, monkeypatch, paks):
        """build-sdk used sorted(...)[0]: an MPB pak sorting first failed an SDK pak."""
        mixed = _mixed_reference_dir(tmp_path)
        monkeypatch.setattr(sdk_builder, "_REFERENCES_DIR", mixed)
        sdk_builder._run_pak_compare(paks["good"], release_build=True)
        with pytest.raises(PakCompareGateError, match="zz_sdk_ref.pak"):
            sdk_builder._run_pak_compare(paks["no_manifest"], release_build=True)

    def test_no_reference_fails_release(self, tmp_path, monkeypatch, paks):
        monkeypatch.setattr(sdk_builder, "_REFERENCES_DIR", tmp_path / "absent")
        with pytest.raises(PakCompareGateError, match="release build cannot skip"):
            sdk_builder._run_pak_compare(paks["good"], release_build=True)

    def test_no_reference_skips_dev(self, tmp_path, monkeypatch, paks, capsys):
        monkeypatch.setattr(sdk_builder, "_REFERENCES_DIR", tmp_path / "absent")
        sdk_builder._run_pak_compare(paks["good"])
        assert "skipping comparison (dev build)" in capsys.readouterr().err


class TestFailedPakDisposal:

    def test_release_build_deletes_failed_pak(self, ref_dir, tmp_path):
        pak = _write_pak(tmp_path / "built.pak", manifest=False)
        with pytest.raises(PakCompareGateError):
            sdk_builder._gate_built_pak(pak, release_build=True, warn_only=False)
        assert not pak.exists(), "a release pak that failed the gate must not survive"

    def test_dev_build_keeps_failed_pak_for_inspection(self, ref_dir, tmp_path):
        pak = _write_pak(tmp_path / "built.pak", manifest=False)
        with pytest.raises(PakCompareGateError):
            sdk_builder._gate_built_pak(pak, release_build=False, warn_only=False)
        assert pak.exists()

    def test_passing_release_pak_is_kept(self, ref_dir, tmp_path):
        pak = _write_pak(tmp_path / "built.pak")
        sdk_builder._gate_built_pak(pak, release_build=True, warn_only=False)
        assert pak.exists()


_ADAPTER_YAML = textwrap.dedent("""\
    name: "VCF Content Factory Gate Test Adapter"
    version: "1.2.3"
    build_number: 42
    adapter_kind: "gate_test"
    tier: 2
    description: "Synthetic adapter for the pak-compare gate test."
    entry_class: "com.vcfcf.adapters.gatetest.GateTestAdapter"
    released: false
""")


class TestBuildSdkWarnOnlyGuard:

    def test_warn_only_refused_on_release_build(self, tmp_path, monkeypatch):
        (tmp_path / "adapter.yaml").write_text(_ADAPTER_YAML, encoding="utf-8")
        monkeypatch.setenv("VCFCF_RELEASE_BUILD", "1")
        with pytest.raises(SdkBuildError, match="warn-only mode is not allowed"):
            sdk_builder.build_sdk_pak(
                tmp_path, tmp_path / "out", pak_compare_warn_only=True
            )

    def test_factory_cli_flag_parses(self):
        parser = cli.build_parser()
        args = parser.parse_args(["build-sdk", "some/dir", "--pak-compare-warn-only"])
        assert args.pak_compare_warn_only is True
        assert parser.parse_args(["build-sdk", "some/dir"]).pak_compare_warn_only is False

    def test_kit_cli_flag_parses(self):
        from vcfcf_managementpacks.buildkit import _KIT_MAIN

        ns: dict = {"__name__": "sdk_buildkit_main_under_test"}
        exec(compile(_KIT_MAIN, "sdk_buildkit/__main__.py", "exec"), ns)
        parser = ns["_build_parser"]()
        args = parser.parse_args(["build-sdk", "some/dir", "--pak-compare-warn-only"])
        assert args.pak_compare_warn_only is True
        assert parser.parse_args(["build-sdk", "some/dir"]).pak_compare_warn_only is False


# ---------------------------------------------------------------------------
# javac -proc:none (sdk-runtime#1)
# ---------------------------------------------------------------------------

class _Done:
    returncode = 0
    stderr = ""
    stdout = ""


def test_compile_disables_annotation_processing(tmp_path, monkeypatch):
    seen = []

    def _fake_run(cmd, **_kw):
        seen.append(cmd)
        return _Done()

    monkeypatch.setattr(sdk_builder.subprocess, "run", _fake_run)
    src = tmp_path / "A.java"
    src.write_text("class A {}", encoding="utf-8")
    sdk_builder._compile("javac", "cp.jar", [src], tmp_path / "classes")
    assert seen and "-proc:none" in seen[0], seen


def test_framework_compile_disables_annotation_processing(tmp_path, monkeypatch):
    """The framework jar compile (_ensure_framework_jar) passes -proc:none too."""
    seen = []

    def _fake_run(cmd, **_kw):
        seen.append(list(cmd))
        if cmd and cmd[0].endswith("jar") and "cf" in cmd:
            Path(cmd[2]).write_bytes(b"jar")
        return _Done()

    src = tmp_path / "fw" / "src" / "com" / "x"
    src.mkdir(parents=True)
    (src / "A.java").write_text("package com.x; class A {}", encoding="utf-8")
    sdk_jar = tmp_path / "vrops-adapters-sdk-2.2.jar"
    sdk_jar.write_bytes(b"jar")
    runtime = tmp_path / "adapter_runtime"
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", tmp_path / "fw" / "src")
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime)
    monkeypatch.setenv("VCFCF_SDK_JAR", str(sdk_jar))
    monkeypatch.setattr(sdk_builder.subprocess, "run", _fake_run)
    monkeypatch.setattr(sdk_builder.shutil, "which", lambda name: f"/usr/bin/{name}")
    sdk_builder._ensure_framework_jar()
    javac_calls = [c for c in seen if c and c[0].endswith("javac")]
    assert javac_calls, f"framework was not compiled; calls: {seen}"
    assert "-proc:none" in javac_calls[0], javac_calls[0]


# ---------------------------------------------------------------------------
# Buildkit tarball SHA-256 sidecar
# ---------------------------------------------------------------------------

def test_buildkit_writes_sha256_sidecar(tmp_path, paks):
    from vcfcf_managementpacks.buildkit import assemble_buildkit

    tarball = assemble_buildkit(
        output_dir=tmp_path / "dist",
        version="9.9.9",
        reference_pak=paks["ref"],
        verbose=False,
    )
    sidecar = tarball.with_name(tarball.name + ".sha256")
    assert sidecar.is_file()
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    assert sidecar.read_text(encoding="utf-8") == f"{digest}  {tarball.name}\n"
