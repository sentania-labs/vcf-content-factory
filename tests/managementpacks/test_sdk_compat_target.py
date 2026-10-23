"""Second SDK compile target (issue #211): the 9.1.1.0100 jar.

The shipped compile target stays vrops-adapters-sdk-2.2.jar. build-sdk,
validate-sdk and build-framework.sh also compile the source against
vrops-adapters-sdk-9.1.1.0100.jar and fail on anything unresolved there.

Covered here, hermetically (tmp_path stand-ins for adapter_runtime/ and the
framework source tree; stub jars compiled by the javac on PATH):

  - the compat jar never joins the primary classpath, the primary SDK jar
    glob, or the Adapter-Version-Ref detection, even though it sits beside
    the 2.2 jar in adapter_runtime/;
  - the pass passes when the referenced class is in the compat jar and
    fails, naming the class, when it is not;
  - a missing jar or a too-old JDK is a loud skip, and a failure when
    VCFCF_SDK_COMPAT_REQUIRED=1;
  - the JDK requirement is read from the jar's class-file version;
  - JDK discovery honours VCFCF_SDK_COMPAT_JAVAC and the JAVA_HOME_<N>_<ARCH>
    variables actions/setup-java exports;
  - the adapter pass compiles framework source with the adapter and drops
    the primary SDK jar and vcfcf-adapter-base.jar from its classpath;
  - --sdk-compat-jar / --require-sdk-compat reach the env from both the
    factory CLI and the kit's own __main__.

The real 9.1.1.0100 jar needs JDK 25, which CI's test job does not have;
the stubs here are compiled by whatever javac is on PATH, so they exercise
the same code path with a JDK the job has.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder
from vcfcf_managementpacks.sdk_builder import SdkBuildError

_HAVE_JDK = shutil.which("javac") is not None

needs_javac = pytest.mark.skipif(not _HAVE_JDK, reason="javac not on PATH")

_COMPAT_ENV = (
    "VCFCF_SDK_COMPAT_JAR",
    "VCFCF_SDK_COMPAT_JAVAC",
    "VCFCF_SDK_COMPAT_REQUIRED",
    "VCFCF_SDK_JAR",
)


@pytest.fixture()
def runtime(tmp_path, monkeypatch):
    """A stand-in adapter_runtime/ and framework src dir; compat env cleared."""
    runtime_dir = tmp_path / "adapter_runtime"
    runtime_dir.mkdir()
    fw_src = tmp_path / "adapter_framework" / "src"
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", fw_src)
    for name in _COMPAT_ENV:
        monkeypatch.delenv(name, raising=False)
    return runtime_dir


def _write_java(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _jar_of(classes_dir: Path, jar_path: Path, major: int = 0) -> Path:
    """Zip classes_dir into jar_path; optionally rewrite each class-file major."""
    with zipfile.ZipFile(jar_path, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        for cls in sorted(classes_dir.rglob("*.class")):
            data = cls.read_bytes()
            if major:
                data = data[:6] + major.to_bytes(2, "big") + data[8:]
            zf.writestr(str(cls.relative_to(classes_dir)), data)
    return jar_path


def _stub_sdk_jar(tmp_path: Path, jar_path: Path, class_names, major: int = 0) -> Path:
    """Compile public classes sdkstub.<name> and jar them."""
    src = tmp_path / ("stubsrc_" + jar_path.stem)
    out = tmp_path / ("stubout_" + jar_path.stem)
    out.mkdir()
    files = [
        _write_java(src, f"sdkstub/{n}.java", f"package sdkstub;\npublic class {n} {{}}\n")
        for n in class_names
    ]
    subprocess.run(
        ["javac", "-d", str(out)] + [str(f) for f in files],
        check=True, capture_output=True,
    )
    return _jar_of(out, jar_path, major)


def _user_source(tmp_path: Path, class_name: str) -> Path:
    return _write_java(
        tmp_path / "usersrc", "user/Use.java",
        f"package user;\nclass Use {{ sdkstub.{class_name} field; }}\n",
    )


# ---------------------------------------------------------------------------
# The compat jar stays off every primary path
# ---------------------------------------------------------------------------


def _touch_jar(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    return path


def test_compat_jar_is_not_on_the_primary_classpath(runtime, tmp_path):
    primary = _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    compat = _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    jars = sdk_builder._build_classpath_jars(tmp_path)
    assert primary in jars
    assert compat not in jars
    assert str(compat) not in sdk_builder._build_classpath(tmp_path)


def test_primary_sdk_glob_skips_the_compat_jar(runtime):
    primary = _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    assert sdk_builder._primary_sdk_jars(runtime) == [primary]


def test_compat_jar_alone_is_not_a_primary_sdk_jar(runtime, tmp_path):
    """A runtime holding only the 9.1.1 jar must not pass as having the SDK."""
    _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    assert sdk_builder._primary_sdk_jars(runtime) == []
    with pytest.raises(SdkBuildError, match="not found in adapter_runtime"):
        sdk_builder._build_classpath_jars(tmp_path)


def test_adapter_version_ref_ignores_the_compat_jar(runtime):
    from vcfcf_managementpacks.sdk_project import SdkProjectDef

    # Only the compat jar present: Adapter-Version-Ref must not become
    # "9.1.1.0100" (it describes the jar the pak was compiled against).
    _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    project = SdkProjectDef(
        name="X", version="1.0.0", build_number=1, adapter_kind="x",
        tier=2, description="", dependencies=[], entry_class="a.B",
        source_path=Path("/dev/null"),
    )
    assert "Adapter-Version-Ref=N/A" in sdk_builder._generate_version_txt(project)
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    assert "Adapter-Version-Ref=2.2" in sdk_builder._generate_version_txt(project)


# ---------------------------------------------------------------------------
# The pass itself
# ---------------------------------------------------------------------------


@needs_javac
def test_pass_passes_when_the_class_is_present(runtime, tmp_path, capsys):
    _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Present"])
    src = _user_source(tmp_path, "Present")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is True
    assert "sdk-compat: test source compiles against" in capsys.readouterr().err


@needs_javac
def test_pass_fails_naming_the_missing_class(runtime, tmp_path):
    # The class exists in the "primary" world but not in the compat jar:
    # the drift issue #211 is about (e.g. adapter3/RollUpType).
    _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Other"])
    src = _user_source(tmp_path, "Gone")
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check([src], [], "test source")
    msg = str(exc.value)
    assert "SDK compat check failed" in msg
    assert "missing class Gone" in msg


@needs_javac
def test_pass_uses_the_env_jar_over_adapter_runtime(runtime, tmp_path, monkeypatch):
    # adapter_runtime/ copy lacks the class; the env-supplied jar has it.
    _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Other"])
    env_jar = _stub_sdk_jar(tmp_path, tmp_path / "elsewhere.jar", ["Present"])
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(env_jar))
    src = _user_source(tmp_path, "Present")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is True


def test_env_jar_that_does_not_exist_is_an_error(runtime, tmp_path, monkeypatch):
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(tmp_path / "nope.jar"))
    with pytest.raises(SdkBuildError, match="file not found"):
        sdk_builder._sdk_compat_check([], [], "test source")


def test_missing_jar_is_a_loud_skip(runtime, capsys):
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    err = capsys.readouterr().err
    assert "SDK COMPAT CHECK SKIPPED" in err
    assert "is not in adapter_runtime/" in err


def test_missing_jar_fails_when_required(runtime, monkeypatch):
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    with pytest.raises(SdkBuildError, match="could not run"):
        sdk_builder._sdk_compat_check([], [], "test source")


@needs_javac
def test_too_old_jdk_is_a_loud_skip_and_a_failure_when_required(
    runtime, tmp_path, capsys, monkeypatch,
):
    # Class-file major 200 = "Java 156": no installed JDK can read it, the
    # same position JDK 17 is in against the real 9.1.1 jar (major 69).
    _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Present"], major=200)
    src = _user_source(tmp_path, "Present")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is False
    err = capsys.readouterr().err
    assert "SDK COMPAT CHECK SKIPPED" in err
    assert "needs JDK 156 or newer" in err

    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    with pytest.raises(SdkBuildError, match="needs JDK 156 or newer"):
        sdk_builder._sdk_compat_check([src], [], "test source")


@needs_javac
def test_required_java_major_comes_from_the_class_files(tmp_path):
    jar = _stub_sdk_jar(tmp_path, tmp_path / "j.jar", ["A"], major=69)
    assert sdk_builder._jar_required_java_major(jar) == 25
    empty = _touch_jar(tmp_path / "empty.jar")
    assert sdk_builder._jar_required_java_major(empty) == 0


# ---------------------------------------------------------------------------
# JDK discovery
# ---------------------------------------------------------------------------


def _fake_javac(path: Path, version: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho 'javac {version}' >&2\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_explicit_javac_too_old_is_a_configuration_error(tmp_path, monkeypatch):
    old = _fake_javac(tmp_path / "jdk17" / "bin" / "javac", "17.0.20")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAVAC", str(old))
    with pytest.raises(SdkBuildError, match="JDK 17"):
        sdk_builder._find_compat_javac(25)


def test_setup_java_home_variables_are_searched(tmp_path, monkeypatch):
    monkeypatch.delenv("VCFCF_SDK_COMPAT_JAVAC", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    for name in list(os.environ):
        if name.startswith("JAVA_HOME_"):
            monkeypatch.delenv(name)
    monkeypatch.setattr(sdk_builder, "_COMPAT_JDK_GLOBS", [])
    monkeypatch.setattr(sdk_builder.shutil, "which", lambda _name: None)
    _fake_javac(tmp_path / "t17" / "bin" / "javac", "17.0.20")
    new = _fake_javac(tmp_path / "t25" / "bin" / "javac", "25.0.5")
    monkeypatch.setenv("JAVA_HOME_17_X64", str(tmp_path / "t17"))
    monkeypatch.setenv("JAVA_HOME_25_X64", str(tmp_path / "t25"))
    javac, major, _tried = sdk_builder._find_compat_javac(25)
    assert (javac, major) == (str(new), 25)


def test_javac_major_parses_old_and_new_formats(tmp_path):
    assert sdk_builder._javac_major(str(_fake_javac(tmp_path / "a" / "javac", "25.0.5"))) == 25
    assert sdk_builder._javac_major(str(_fake_javac(tmp_path / "b" / "javac", "1.8.0_402"))) == 8


# ---------------------------------------------------------------------------
# Adapter pass inputs
# ---------------------------------------------------------------------------


def test_adapter_inputs_swap_framework_jar_for_framework_source(runtime, tmp_path):
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    _touch_jar(runtime / "vcfcf-adapter-base.jar")
    other = _touch_jar(runtime / "alive_common.jar")
    fw = _write_java(sdk_builder._ADAPTER_FRAMEWORK_SRC_DIR, "fw/F.java", "package fw; class F {}\n")
    adapter_src = _write_java(tmp_path / "proj" / "src", "a/A.java", "package a; class A {}\n")

    sources, jars = sdk_builder._adapter_compat_inputs(tmp_path / "proj", [adapter_src])
    assert sources == [fw, adapter_src]
    assert jars == [other]


def test_adapter_inputs_keep_framework_jar_without_source(runtime, tmp_path, monkeypatch):
    env_sdk = _touch_jar(tmp_path / "custom-sdk.jar")
    monkeypatch.setenv("VCFCF_SDK_JAR", str(env_sdk))
    fw_jar = _touch_jar(runtime / "vcfcf-adapter-base.jar")
    adapter_src = tmp_path / "A.java"
    sources, jars = sdk_builder._adapter_compat_inputs(tmp_path, [adapter_src])
    assert sources == [adapter_src]
    assert jars == [fw_jar]


# ---------------------------------------------------------------------------
# CLI plumbing: factory CLI and the kit's own __main__
# ---------------------------------------------------------------------------


def test_factory_cli_flags_reach_the_env(monkeypatch):
    from vcfcf_managementpacks import cli

    for name in _COMPAT_ENV:
        monkeypatch.delenv(name, raising=False)
    args = argparse.Namespace(
        sdk_jar=None, sdk_compat_jar="/x/compat.jar", require_sdk_compat=True,
    )
    cli._apply_sdk_jar_flag(args)
    assert os.environ["VCFCF_SDK_COMPAT_JAR"] == "/x/compat.jar"
    assert os.environ["VCFCF_SDK_COMPAT_REQUIRED"] == "1"


@pytest.mark.parametrize("cmd", ["build-sdk", "validate-sdk"])
def test_kit_main_parses_the_flags_and_sets_the_env(cmd, monkeypatch):
    from vcfcf_managementpacks.buildkit import _KIT_MAIN

    for name in _COMPAT_ENV:
        monkeypatch.delenv(name, raising=False)
    namespace = {"__name__": "kit_main_under_test"}
    exec(compile(_KIT_MAIN, "sdk_buildkit/__main__.py", "exec"), namespace)
    args = namespace["_build_parser"]().parse_args(
        [cmd, "proj", "--sdk-compat-jar", "/k/compat.jar", "--require-sdk-compat"]
    )
    namespace["_apply_sdk_jar"](args)
    assert os.environ["VCFCF_SDK_COMPAT_JAR"] == "/k/compat.jar"
    assert os.environ["VCFCF_SDK_COMPAT_REQUIRED"] == "1"
