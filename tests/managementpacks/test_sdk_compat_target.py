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
    "VCFCF_SDK_COMPAT_JARS",
    "VCFCF_SDK_COMPAT_JAVAC",
    "VCFCF_SDK_COMPAT_REQUIRED",
    "VCFCF_SDK_JAR",
)


def _isolate_compat_env(monkeypatch):
    """Unset the compat env vars AND register their restore.

    monkeypatch.delenv(name, raising=False) on a variable that is not set
    records nothing, so a value the code under test then writes into
    os.environ (the CLI flag helpers do exactly that) outlives the test and
    leaks into every later test on the same xdist worker. That is how
    VCFCF_SDK_COMPAT_REQUIRED=1 reached test_cli_phase4's validate run in CI
    on PR #251. setenv first makes monkeypatch remember the original state.
    """
    for name in _COMPAT_ENV:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


@pytest.fixture()
def runtime(tmp_path, monkeypatch):
    """A stand-in adapter_runtime/ and framework src dir; compat env cleared."""
    runtime_dir = tmp_path / "adapter_runtime"
    runtime_dir.mkdir()
    fw_src = tmp_path / "adapter_framework" / "src"
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", fw_src)
    _isolate_compat_env(monkeypatch)
    return runtime_dir


def _write_java(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# Fixed zip entry timestamps: a stub jar's bytes depend only on its content,
# never on the wall-clock second it was written in. With writestr(str, ...)
# two stubs of equal content got equal sha256 only when written in the same
# second, which a fast CI runner hit and a workstation did not (PR #258).
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _entry(name: str) -> zipfile.ZipInfo:
    return zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)


def _jar_of(classes_dir: Path, jar_path: Path, major: int = 0) -> Path:
    """Zip classes_dir into jar_path; optionally rewrite each class-file major."""
    with zipfile.ZipFile(jar_path, "w") as zf:
        # The jar's own name in the manifest: two stubs standing for two
        # different platform jars must not share a sha256, since a supplied
        # jar is matched to its line by sha256.
        zf.writestr(_entry("META-INF/MANIFEST.MF"),
                    f"Manifest-Version: 1.0\nX-Stub-Jar: {jar_path.name}\n")
        for cls in sorted(classes_dir.rglob("*.class")):
            data = cls.read_bytes()
            if major:
                data = data[:6] + major.to_bytes(2, "big") + data[8:]
            zf.writestr(_entry(str(cls.relative_to(classes_dir))), data)
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


def _register_lines(monkeypatch, jars) -> None:
    """Make the stub jars the supported lines (key -> jar), so a run that
    supplies them covers every expected line (issue #252 review B2)."""
    monkeypatch.setattr(sdk_builder, "_SDK_COMPAT_LINES", tuple(
        sdk_builder._CompatLine(key, Path(jar).name, sdk_builder._sha256_of(Path(jar)))
        for key, jar in jars.items()
    ))


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
        zf.writestr(_entry("META-INF/MANIFEST.MF"), "Manifest-Version: 1.0\n")
    return path


def test_compat_jar_is_not_on_the_primary_classpath(runtime, tmp_path):
    primary = _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    compat = _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    jars = sdk_builder._build_classpath_jars(tmp_path)
    assert primary in jars
    assert compat not in jars
    assert str(compat) not in sdk_builder._build_classpath(tmp_path)


def _sdk_jars_on(jars):
    return [j for j in jars if j.name.startswith("vrops-adapters-sdk")]


def test_primary_classpath_takes_exactly_one_sdk_jar(runtime, tmp_path):
    primary = _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    assert sdk_builder._primary_sdk_jar() == primary
    assert _sdk_jars_on(sdk_builder._build_classpath_jars(tmp_path)) == [primary]


def test_compat_jar_alone_is_not_a_primary_sdk_jar(runtime, tmp_path):
    """A runtime holding only the 9.1.1 jar must not pass as having the SDK."""
    _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    assert sdk_builder._primary_sdk_jar() is None
    with pytest.raises(SdkBuildError, match="not found in adapter_runtime"):
        sdk_builder._build_classpath_jars(tmp_path)


@pytest.mark.parametrize("stray", [
    "vrops-adapters-sdk.jar",        # the name the appliance gives it
    "vrops-adapters-sdk-1.0.jar",    # its identical sibling on the appliance
    "vrops-adapters-sdk-9.1.1.0.jar",
])
def test_a_second_sdk_jar_under_any_name_is_an_error(runtime, tmp_path, stray):
    """Review B1: the 9.1.1 jar copied under its appliance name used to join
    the primary classpath beside 2.2 while the compat pass skipped."""
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    _touch_jar(runtime / stray)
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._build_classpath_jars(tmp_path)
    assert stray in str(exc.value)
    assert sdk_builder._SDK_COMPAT_JAR_NAME in str(exc.value)


def test_an_sdk_jar_under_adapter_runtime_lib_is_an_error(runtime, tmp_path):
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    (runtime / "lib").mkdir()
    _touch_jar(runtime / "lib" / "vrops-adapters-sdk.jar")
    with pytest.raises(SdkBuildError, match="lib/vrops-adapters-sdk.jar"):
        sdk_builder._build_classpath_jars(tmp_path)


def test_env_sdk_jar_is_the_only_sdk_jar_on_the_classpath(runtime, tmp_path, monkeypatch):
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    env_jar = _touch_jar(tmp_path / "supplied-sdk.jar")
    monkeypatch.setenv("VCFCF_SDK_JAR", str(env_jar))
    jars = sdk_builder._build_classpath_jars(tmp_path)
    assert jars[0] == env_jar
    assert _sdk_jars_on(jars) == []  # the runtime 2.2 copy stays off


def test_framework_compile_refuses_two_sdk_jars(runtime):
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    _touch_jar(runtime / "vrops-adapters-sdk.jar")
    _write_java(sdk_builder._ADAPTER_FRAMEWORK_SRC_DIR, "fw/F.java", "package fw; class F {}\n")
    with pytest.raises(SdkBuildError, match="exactly one primary SDK jar"):
        sdk_builder._ensure_framework_jar()


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
    (runtime / "vrops-adapters-sdk-2.2.jar").unlink()
    _touch_jar(runtime / "vrops-adapters-sdk.jar")  # no version in the name
    assert "Adapter-Version-Ref=N/A" in sdk_builder._generate_version_txt(project)


# ---------------------------------------------------------------------------
# The pass itself
# ---------------------------------------------------------------------------


@needs_javac
def test_pass_passes_when_the_class_is_present(runtime, tmp_path, capsys, monkeypatch):
    jar = _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Present"])
    _register_lines(monkeypatch, {"9.1.1.0100": jar})
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
    _register_lines(monkeypatch, {"9.1.1.0100": env_jar})
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
    with pytest.raises(sdk_builder.SdkCompatUnavailable, match="could not run"):
        sdk_builder._sdk_compat_check([], [], "test source")


@pytest.mark.parametrize("release,actions,annotated", [
    ("1", "true", True),
    ("", "true", False),
    ("1", "", False),
])
def test_release_build_skip_is_annotated_on_github_actions(
    runtime, monkeypatch, capsys, release, actions, annotated,
):
    """Review W1: a tagged pak release that skips the pass shows a
    ::warning:: on the run page, not only the stderr box."""
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", release)
    monkeypatch.setenv("GITHUB_ACTIONS", actions)
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    out = capsys.readouterr()
    assert ("::warning title=sdk-compat skipped::" in out.out) is annotated
    assert "SDK COMPAT CHECK SKIPPED" in out.err


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

    _isolate_compat_env(monkeypatch)
    args = argparse.Namespace(
        sdk_jar=None, sdk_compat_jar=["/x/a.jar", "/x/b.jar"], require_sdk_compat=True,
    )
    cli._apply_sdk_jar_flag(args)
    assert os.environ["VCFCF_SDK_COMPAT_JARS"] == os.pathsep.join(["/x/a.jar", "/x/b.jar"])
    assert os.environ["VCFCF_SDK_COMPAT_REQUIRED"] == "1"


def test_factory_cli_flag_jars_join_the_env_list(monkeypatch):
    from vcfcf_managementpacks import cli

    _isolate_compat_env(monkeypatch)
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", "/env/one.jar")
    cli._apply_sdk_jar_flag(argparse.Namespace(
        sdk_jar=None, sdk_compat_jar=["/x/two.jar"], require_sdk_compat=False,
    ))
    assert os.environ["VCFCF_SDK_COMPAT_JARS"] == os.pathsep.join(["/env/one.jar", "/x/two.jar"])


@pytest.mark.parametrize("cmd", ["build-sdk", "validate-sdk"])
def test_factory_cli_flag_repeats(cmd, monkeypatch):
    from vcfcf_managementpacks import cli

    _isolate_compat_env(monkeypatch)
    args = cli.build_parser().parse_args(
        [cmd, "proj", "--sdk-compat-jar", "/a/x.jar", "--sdk-compat-jar", "/a/y.jar"]
    )
    assert args.sdk_compat_jar == ["/a/x.jar", "/a/y.jar"]


@pytest.mark.parametrize("cmd", ["build-sdk", "validate-sdk"])
def test_kit_main_parses_the_flags_and_sets_the_env(cmd, monkeypatch):
    from vcfcf_managementpacks.buildkit import _KIT_MAIN

    _isolate_compat_env(monkeypatch)
    namespace = {"__name__": "kit_main_under_test"}
    exec(compile(_KIT_MAIN, "sdk_buildkit/__main__.py", "exec"), namespace)
    args = namespace["_build_parser"]().parse_args(
        [cmd, "proj", "--sdk-compat-jar", "/k/compat.jar",
         "--sdk-compat-jar", "/k/other.jar", "--require-sdk-compat"]
    )
    namespace["_apply_sdk_jar"](args)
    assert os.environ["VCFCF_SDK_COMPAT_JARS"] == os.pathsep.join(["/k/compat.jar", "/k/other.jar"])
    assert os.environ["VCFCF_SDK_COMPAT_REQUIRED"] == "1"


# ---------------------------------------------------------------------------
# Wiring: the pass is actually called from validate-sdk, build-sdk and
# build-framework.sh (review W3: replacing both calls with `pass` used to
# leave the suite green)
# ---------------------------------------------------------------------------


@pytest.fixture()
def scaffolded(tmp_path, monkeypatch, capsys):
    """A scaffolded adapter project with the primary compile stubbed out and
    _sdk_compat_check replaced by a recorder that fails like a real miss."""
    _isolate_compat_env(monkeypatch)
    project = sdk_builder.scaffold_sdk_project("Compat Wiring", tmp_path)
    capsys.readouterr()
    calls = []
    monkeypatch.setattr(sdk_builder, "_ensure_framework_jar", lambda: None)
    monkeypatch.setattr(sdk_builder, "_build_classpath_jars", lambda _pd: [])
    monkeypatch.setattr(sdk_builder, "_compile", lambda *a, **k: calls.append("compile"))

    def fake_check(sources, other_jars, what):
        calls.append(("compat", [Path(s).name for s in sources]))
        raise SdkBuildError("SDK compat check failed: missing class Gone")

    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", fake_check)
    return project, calls


def test_validate_sdk_runs_the_pass_and_reports_its_failure(scaffolded, tmp_path, monkeypatch):
    project, calls = scaffolded
    monkeypatch.setattr(sdk_builder.shutil, "which", lambda _n: "/usr/bin/javac")
    monkeypatch.setenv("VCFCF_SDK_JAR", str(_touch_jar(tmp_path / "sdk.jar")))
    errors = sdk_builder.validate_sdk_project(project)
    assert "SDK compat check failed: missing class Gone" in errors
    assert calls[0] == "compile"
    compat_sources = calls[1][1]
    # Adapter source and framework source are both compiled in the pass.
    assert "CompatWiringAdapter.java" in compat_sources
    assert "VcfCfAdapter.java" in compat_sources


def test_build_sdk_fails_on_the_pass_before_packaging(scaffolded, tmp_path, monkeypatch):
    project, calls = scaffolded
    monkeypatch.setattr(sdk_builder, "_detect_jdk", lambda: "javac")
    monkeypatch.setattr(sdk_builder, "_detect_jar_tool", lambda: "jar")
    monkeypatch.setattr(
        sdk_builder, "_write_adapter_properties", lambda *a, **k: calls.append("step5"),
    )
    out = tmp_path / "out"
    with pytest.raises(SdkBuildError, match="missing class Gone"):
        sdk_builder.build_sdk_pak(project, out)
    assert [c if isinstance(c, str) else c[0] for c in calls] == ["compile", "compat"]
    assert not out.exists() or not list(out.glob("*.pak"))


_BUILD_FRAMEWORK = (
    Path(sdk_builder.__file__).parent / "adapter_framework" / "build-framework.sh"
)


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("VCFCF_") and k != "PYTHONPATH"}
    env.update(extra)
    return env


def _run_build_framework(script: Path, env) -> subprocess.CompletedProcess:
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(script), "--compat-only"],
        capture_output=True, text=True, env=env, timeout=600,
    )


def _isolated_script(tmp_path: Path) -> Path:
    """build-framework.sh in a scratch package tree with an empty adapter_runtime/."""
    pkg = tmp_path / "pkgroot" / "vcfcf_managementpacks"
    (pkg / "adapter_framework").mkdir(parents=True)
    (pkg / "adapter_runtime").mkdir()
    script = pkg / "adapter_framework" / "build-framework.sh"
    shutil.copy(_BUILD_FRAMEWORK, script)
    return script


@needs_javac
def test_build_framework_compat_only_fails_on_a_missing_class(tmp_path):
    # The stub "9.1.1" jar lacks every SDK class the real framework uses.
    jar = _stub_sdk_jar(tmp_path, tmp_path / "compat.jar", ["Present"])
    r = _run_build_framework(_BUILD_FRAMEWORK, _clean_env(VCFCF_SDK_COMPAT_JAR=str(jar)))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "SDK compat check failed" in r.stderr
    assert "COMPAT PASS FAILED" in r.stderr


@needs_javac
def test_build_framework_required_pass_that_cannot_run_exits_3(tmp_path):
    jar = _stub_sdk_jar(tmp_path, tmp_path / "compat.jar", ["Present"], major=200)
    r = _run_build_framework(
        _BUILD_FRAMEWORK,
        _clean_env(VCFCF_SDK_COMPAT_JAR=str(jar), VCFCF_SDK_COMPAT_REQUIRED="1"),
    )
    assert r.returncode == sdk_builder.COMPAT_COULD_NOT_RUN == 3, r.stdout + r.stderr
    assert "COMPAT PASS COULD NOT RUN" in r.stderr


def test_build_framework_skips_in_shell_without_a_jar(tmp_path):
    """Review W2: no jar and not required means no python3 at all."""
    script = _isolated_script(tmp_path)
    tools = tmp_path / "bin"
    tools.mkdir()
    for tool in ("dirname", "tr"):
        (tools / tool).symlink_to(shutil.which(tool))
    r = _run_build_framework(script, _clean_env(PATH=str(tools)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SDK COMPAT CHECK SKIPPED" in r.stdout


def test_build_framework_import_failure_is_could_not_run(tmp_path):
    """Review W2: a python3 that cannot import the package is not reported
    as a 9.1.1 compile failure."""
    script = _isolated_script(tmp_path)
    jar = _touch_jar(tmp_path / "compat.jar")
    r = _run_build_framework(script, _clean_env(VCFCF_SDK_COMPAT_JAR=str(jar)))
    assert r.returncode == 3, r.stdout + r.stderr
    assert "cannot import" in r.stderr
    assert "COMPAT PASS COULD NOT RUN" in r.stderr


@needs_javac
def test_validate_with_an_empty_adapter_runtime_skips_like_main(
    runtime, tmp_path, monkeypatch, capsys,
):
    """The public CI runner has no SDK jar at all (the 2.2 jar is private).
    `python3 -m vcfcf_managementpacks validate` must skip the compile checks
    with the existing notice and pass, exactly as on main: the one-SDK-jar
    rule fires only for two or more jars, never for none, and no compat box
    or error appears when the pass is not required."""
    from vcfcf_managementpacks import cli

    assert not list(runtime.glob("*.jar"))
    monkeypatch.chdir(tmp_path)
    sdk_builder.scaffold_sdk_project("Empty Runtime", tmp_path / "content" / "sdk-adapters")
    capsys.readouterr()
    assert cli._validate_tier2_projects() == (1, 0)
    err = capsys.readouterr().err
    assert "skipping compile check" in err
    assert "SDK COMPAT CHECK SKIPPED" not in err
    assert "exactly one primary SDK jar" not in err


def test_cli_flag_helpers_do_not_leak_env_past_a_test():
    """Guard for the PR #251 CI failure: whatever test ran before this one on
    this worker, no compat variable it set may still be in the environment.
    (Only meaningful when an env-writing test ran first on the worker; the
    real guarantee is _isolate_compat_env.)"""
    leaked = [n for n in _COMPAT_ENV if n != "VCFCF_SDK_JAR" and os.environ.get(n)]
    assert not leaked, leaked


# ---------------------------------------------------------------------------
# Issue #242: the framework stays free of APIs deprecated for removal
# ---------------------------------------------------------------------------


def test_removal_warnings_are_picked_out():
    out = (
        "A.java:3: warning: [removal] Integer(int) in Integer has been deprecated and marked for removal\n"
        "A.java:9: warning: [deprecation] foo() in Bar has been deprecated\n"
        "2 warnings\n"
    )
    assert sdk_builder.removal_warnings(out) == [
        "A.java:3: warning: [removal] Integer(int) in Integer has been deprecated and marked for removal"
    ]
    assert sdk_builder.removal_warnings("") == []


def _removal_source(tmp_path: Path) -> Path:
    # The fixture declares its own forRemoval API rather than leaning on a JDK
    # one: JDK APIs move in and out of forRemoval between releases (OpenJDK 25
    # declares Integer(int) plain @Deprecated, a note not a [removal] warning),
    # so a self-declared one warns the same on every JDK from 11 through 25.
    # It sits in its own top-level class: javac does not warn on a use inside
    # the declaring class.
    _write_java(
        tmp_path / "usersrc", "user/Doomed.java",
        "package user;\nclass Doomed {\n"
        "  @Deprecated(since = \"1\", forRemoval = true)\n"
        "  static int gone() { return 1; }\n}\n",
    )
    return _write_java(
        tmp_path / "usersrc", "user/Old.java",
        "package user;\nclass Old { sdkstub.Present p; int i = Doomed.gone(); }\n",
    )


@needs_javac
def test_framework_pass_fails_on_a_removal_warning(runtime, tmp_path):
    _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Present"])
    src = _removal_source(tmp_path)
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check(
            [src, src.with_name("Doomed.java")], [], "framework source", fail_on_removal=True)
    assert "deprecated for removal" in str(exc.value)
    assert "[removal] gone() in Doomed" in str(exc.value)


@needs_javac
def test_adapter_pass_still_only_prints_a_removal_warning(runtime, tmp_path, capsys):
    _stub_sdk_jar(tmp_path, runtime / sdk_builder._SDK_COMPAT_JAR_NAME, ["Present"])
    src = _removal_source(tmp_path)
    assert sdk_builder._sdk_compat_check(
        [src, src.with_name("Doomed.java")], [], "framework + adapter source") is True
    assert "[removal]" in capsys.readouterr().err


def test_check_framework_sdk_compat_asks_for_the_removal_gate(runtime, monkeypatch):
    _write_java(sdk_builder._ADAPTER_FRAMEWORK_SRC_DIR, "x/A.java", "package x; class A {}\n")
    seen = {}

    def fake_check(sources, other_jars, what, fail_on_removal=False):
        seen["fail_on_removal"] = fail_on_removal
        return True

    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", fake_check)
    assert sdk_builder.check_framework_sdk_compat() == 0
    assert seen["fail_on_removal"] is True


def _java_code_only(text: str) -> str:
    """Java source with comments and string/char literals blanked."""
    import re as _re

    pattern = _re.compile(
        r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', _re.S)
    return pattern.sub(" ", text)


def test_framework_source_never_names_threaddeath():
    """Issue #242: java.lang.ThreadDeath is deprecated for removal on the
    JDK 25 collectors. Comments and the class-name string are fine; code
    that references the type is not. Runs without JDK 25."""
    src = Path(__file__).resolve().parents[2] / "src" / "vcfcf_managementpacks" / "adapter_framework"
    hits = [
        str(p.relative_to(src))
        for p in sorted(src.rglob("*.java"))
        if "ThreadDeath" in _java_code_only(p.read_text(encoding="utf-8"))
    ]
    assert hits == []


# ---------------------------------------------------------------------------
# Several compatibility legs (issue #252)
# ---------------------------------------------------------------------------


def test_sdk_version_label_comes_from_the_file_name():
    assert sdk_builder._sdk_jar_label(Path("vrops-adapters-sdk-8.18.7.jar")) == "8.18.7"
    assert sdk_builder._sdk_jar_label(Path("/x/vrops-adapters-sdk-9.1.1.0100.jar")) == "9.1.1.0100"
    assert "no version in the file name" in sdk_builder._sdk_jar_label(Path("elsewhere.jar"))


@needs_javac
def test_every_explicit_jar_is_a_leg_and_each_line_names_its_version(
    runtime, tmp_path, monkeypatch, capsys,
):
    a = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"])
    b = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-9.1.1.0100.jar", ["Present"])
    _register_lines(monkeypatch, {"8.18.7": a, "9.1.1.0100": b})
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", os.pathsep.join([str(a), str(b)]))
    src = _user_source(tmp_path, "Present")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is True
    err = capsys.readouterr().err
    assert "compiles against the VCF Ops 8.18.7 SDK jar (vrops-adapters-sdk-8.18.7.jar" in err
    assert "compiles against the VCF Ops 9.1.1.0100 SDK jar (vrops-adapters-sdk-9.1.1.0100.jar" in err


@needs_javac
def test_old_single_env_var_still_works_and_adds_to_the_list(
    runtime, tmp_path, monkeypatch, capsys,
):
    a = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"])
    b = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-9.1.1.0100.jar", ["Present"])
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(a))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(b))
    assert sdk_builder._resolve_compat_sdk_jars() == [a, b]
    # The same jar named twice is one leg.
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(a))
    assert sdk_builder._resolve_compat_sdk_jars() == [a]
    # The one-jar form on its own, as before #252.
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", "")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(b))
    assert sdk_builder._resolve_compat_sdk_jars() == [b]


def test_missing_jar_in_the_list_is_an_error_naming_the_variable(runtime, tmp_path, monkeypatch):
    real = _touch_jar(tmp_path / "vrops-adapters-sdk-8.18.7.jar")
    monkeypatch.setenv(
        "VCFCF_SDK_COMPAT_JARS", os.pathsep.join([str(real), str(tmp_path / "nope.jar")]),
    )
    with pytest.raises(sdk_builder.SdkCompatUnavailable, match="VCFCF_SDK_COMPAT_JARS names"):
        sdk_builder._sdk_compat_check([], [], "test source")


def test_runtime_compat_jars_are_legs_only_without_explicit_jars(runtime, tmp_path, monkeypatch):
    in_runtime = _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    assert sdk_builder._resolve_compat_sdk_jars() == [in_runtime]
    explicit = _touch_jar(tmp_path / "vrops-adapters-sdk-8.18.7.jar")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(explicit))
    assert sdk_builder._resolve_compat_sdk_jars() == [explicit]


@needs_javac
def test_a_failing_leg_fails_the_check_after_every_leg_ran(runtime, tmp_path, monkeypatch, capsys):
    good = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-9.1.1.0100.jar", ["Present"])
    bad = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Other"])
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", os.pathsep.join([str(bad), str(good)]))
    src = _user_source(tmp_path, "Present")
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check([src], [], "test source")
    assert not isinstance(exc.value, sdk_builder.SdkCompatUnavailable)
    msg = str(exc.value)
    assert "against the VCF Ops 8.18.7 SDK jar" in msg
    assert "can fail to load on 8.18.7" in msg
    assert "9.1.1.0100 SDK jar" not in msg
    # The leg after the failing one still ran.
    assert "compiles against the VCF Ops 9.1.1.0100 SDK jar" in capsys.readouterr().err


@needs_javac
def test_each_leg_picks_its_own_jdk(runtime, tmp_path, monkeypatch, capsys):
    """An old-bytecode jar runs on the javac at hand while a jar no installed
    JDK can read is skipped, naming only that leg (the 8.18 jar on JDK 17
    next to the 9.1.1 jar without a JDK 25)."""
    old = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"])
    new = _stub_sdk_jar(
        tmp_path, tmp_path / "vrops-adapters-sdk-9.1.1.0100.jar", ["Present"], major=200,
    )
    _register_lines(monkeypatch, {"8.18.7": old, "9.1.1.0100": new})
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", os.pathsep.join([str(old), str(new)]))
    src = _user_source(tmp_path, "Present")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is False
    err = capsys.readouterr().err
    assert "compiles against the VCF Ops 8.18.7 SDK jar" in err
    assert "SDK COMPAT CHECK SKIPPED: test source vs the VCF Ops 9.1.1.0100 SDK jar" in err
    assert "needs JDK 156 or newer" in err

    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    with pytest.raises(sdk_builder.SdkCompatUnavailable) as exc:
        sdk_builder._sdk_compat_check([src], [], "test source")
    assert "the VCF Ops 9.1.1.0100 SDK jar could not run" in str(exc.value)
    assert "8.18.7" not in str(exc.value)


def test_legs_compile_main_sources_only(runtime, tmp_path):
    """Framework tests (adapter_framework/test/) and the pak's tests/ never
    reach a leg: CertificateReviewTest calls a 2.2-only member."""
    fw = _write_java(sdk_builder._ADAPTER_FRAMEWORK_SRC_DIR, "fw/F.java", "package fw; class F {}\n")
    _write_java(
        sdk_builder._ADAPTER_FRAMEWORK_SRC_DIR.parent / "test", "fw/FTest.java",
        "package fw; class FTest {}\n",
    )
    proj = tmp_path / "proj"
    _write_java(proj / "tests", "a/ATest.java", "package a; class ATest {}\n")
    adapter_src = _write_java(proj / "src", "a/A.java", "package a; class A {}\n")
    _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    sources, _jars = sdk_builder._adapter_compat_inputs(proj, sdk_builder._find_sources(proj))
    assert sources == [fw, adapter_src]


@needs_javac
def test_build_framework_runs_legs_from_the_list_env_var(tmp_path):
    jar = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"])
    r = _run_build_framework(_BUILD_FRAMEWORK, _clean_env(VCFCF_SDK_COMPAT_JARS=str(jar)))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "against the VCF Ops 8.18.7 SDK jar" in r.stderr
    assert "COMPAT PASS FAILED" in r.stderr


def test_the_8_18_jar_in_adapter_runtime_is_a_leg_not_a_primary_jar(runtime, tmp_path):
    """Issue #252: vrops-adapters-sdk-8.18.7.jar beside the 2.2 jar is the
    8.18 leg, never a second primary SDK jar; both known compat jars are
    legs, oldest first."""
    primary = _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    old = _touch_jar(runtime / "vrops-adapters-sdk-8.18.7.jar")
    new = _touch_jar(runtime / sdk_builder._SDK_COMPAT_JAR_NAME)
    assert sdk_builder._primary_sdk_jar() == primary
    assert _sdk_jars_on(sdk_builder._build_classpath_jars(tmp_path)) == [primary]
    assert sdk_builder._resolve_compat_sdk_jars() == [old, new]


def test_build_framework_knows_the_same_compat_names_as_sdk_builder():
    text = _BUILD_FRAMEWORK.read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("COMPAT_JAR_NAMES="))
    names = tuple(line.split("=", 1)[1].strip('"').split())
    assert names == sdk_builder._SDK_COMPAT_JAR_NAMES


def test_ci_sdk_compat_matrix_has_the_8_18_and_9_1_legs():
    import yaml

    ci = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    legs = yaml.safe_load(ci.read_text(encoding="utf-8"))["jobs"]["sdk-compat"][
        "strategy"]["matrix"]["include"]
    by_sdk = {leg["sdk"]: leg for leg in legs}
    assert by_sdk["8.18.7"] == {"sdk": "8.18.7", "jdk": "17", "jar": "vrops-adapters-sdk-8.18.7.jar"}
    assert by_sdk["9.1.1.0100"]["jdk"] == "25"
    assert by_sdk["9.0"] == {"sdk": "9.0", "jdk": "17", "jar": "vrops-adapters-sdk-2.2.jar"}
    # One row per supported line; the row's sdk is the VCFCF_SDK_COMPAT_LEGS key.
    assert {(leg["sdk"], leg["jar"]) for leg in legs} == {
        (line.key, line.jar_name) for line in sdk_builder._SDK_COMPAT_LINES}
    job = yaml.safe_load(ci.read_text(encoding="utf-8"))["jobs"]["sdk-compat"]
    env = next(s["env"] for s in job["steps"] if s.get("name", "").startswith("Compile"))
    assert env["VCFCF_SDK_COMPAT_LEGS"] == "${{ matrix.sdk }}"
    assert env["VCFCF_SDK_COMPAT_REQUIRED"] == "1"


# ---------------------------------------------------------------------------
# Each line at its own Java, the 9.0 leg, the expected set (#252 review)
# ---------------------------------------------------------------------------

_JAVAC_MAJOR = sdk_builder._javac_major(shutil.which("javac")) if _HAVE_JDK else None
needs_javac_17 = pytest.mark.skipif(
    not _JAVAC_MAJOR or _JAVAC_MAJOR < 17, reason="needs javac 17+ on PATH",
)


def _write_src(tmp_path: Path, name: str, body: str) -> Path:
    return _write_java(tmp_path / "usersrc", f"user/{name}.java", f"package user;\n{body}\n")


def test_line_hashes_match_provenance():
    prov = (Path(sdk_builder.__file__).parent / "adapter_runtime" / "PROVENANCE.md").read_text(
        encoding="utf-8")
    import re

    for line in sdk_builder._SDK_COMPAT_LINES:
        rows = [r for r in prov.splitlines() if r.startswith("|") and f"`{line.jar_name}`" in r]
        hashes = set(re.findall(r"\b[0-9a-f]{64}\b", "\n".join(rows)))
        assert hashes == {line.sha256}, line.key
    assert [l.key for l in sdk_builder._SDK_COMPAT_LINES] == ["8.18.7", "9.0", "9.1.1.0100"]


def test_leg_release_follows_the_jar_class_files():
    assert sdk_builder._compat_leg_release(11) == 11   # 8.18.7, major 55
    assert sdk_builder._compat_leg_release(17) == 17   # 2.2 (9.0), major 61
    assert sdk_builder._compat_leg_release(25) == 25   # 9.1.1.0100, major 69
    assert sdk_builder._compat_leg_release(8) == 11    # never below the shipped release


def test_primary_jar_is_the_first_leg(runtime, tmp_path, monkeypatch):
    primary = _touch_jar(runtime / "vrops-adapters-sdk-2.2.jar")
    compat = _touch_jar(runtime / "vrops-adapters-sdk-8.18.7.jar")
    assert sdk_builder._compat_leg_jars() == [primary, compat]
    env_primary = _touch_jar(tmp_path / "supplied-sdk.jar")
    monkeypatch.setenv("VCFCF_SDK_JAR", str(env_primary))
    assert sdk_builder._compat_leg_jars() == [env_primary, compat]


@needs_javac_17
def test_java17_library_removal_fails_the_9_0_leg(runtime, tmp_path, monkeypatch, capsys):
    """Review B1: java.rmi.activation exists in Java 11 and was removed in
    Java 17. The 8.18 leg (release 11) passes it; the 9.0 leg (the primary
    jar, major 61, release 17) must fail it, blaming the Java 17 library."""
    primary = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-2.2.jar", ["Present"], major=61)
    old = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"], major=55)
    _register_lines(monkeypatch, {"8.18.7": old, "9.0": primary})
    monkeypatch.setenv("VCFCF_SDK_JAR", str(primary))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(old))
    src = _write_src(tmp_path, "Act", "class Act { Object a(){ return new java.rmi.activation.ActivationID(null); } }")
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check([src], [], "test source")
    msg = str(exc.value)
    assert "against the VCF Ops 9.0 SDK jar" in msg and "--release 17" in msg
    assert "not in the Java 17 class library" in msg
    assert "missing package java.rmi.activation" in msg
    assert "lacks or has changed" not in msg
    assert "against the VCF Ops 8.18.7 SDK jar" not in msg
    assert "compiles against the VCF Ops 8.18.7 SDK jar" in capsys.readouterr().err


@needs_javac_17
def test_removal_warnings_come_from_the_leg_java(runtime, tmp_path, monkeypatch, capsys):
    """#242's [removal] gate needs the leg to compile against its own Java:
    System.getSecurityManager is deprecated for removal in 17, not in 11."""
    primary = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-2.2.jar", ["Present"], major=61)
    old = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"], major=55)
    _register_lines(monkeypatch, {"8.18.7": old, "9.0": primary})
    monkeypatch.setenv("VCFCF_SDK_JAR", str(primary))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(old))
    src = _write_src(tmp_path, "Sm", "class Sm { Object s(){ return System.getSecurityManager(); } }")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is True
    err = capsys.readouterr().err
    block_17 = err.split("sdk-compat javac warnings (9.0):", 1)[1]
    assert "[removal]" in block_17
    assert "sdk-compat javac warnings (8.18.7)" not in err  # release 11: no warning


@needs_javac
def test_jdk_library_miss_is_not_blamed_on_the_jar(runtime, tmp_path, monkeypatch):
    """Review N1: String.indent (Java 12) on the release 11 leg."""
    old = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"], major=55)
    _register_lines(monkeypatch, {"8.18.7": old})
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(old))
    src = _write_src(tmp_path, "Ind", "class Ind { String i(String s){ return s.indent(2); } }")
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check([src], [], "test source")
    msg = str(exc.value)
    assert "not in the Java 11 class library" in msg
    assert "missing method indent(int) in java.lang.String" in msg
    assert "lacks or has changed" not in msg


@needs_javac
def test_sdk_miss_is_blamed_on_the_jar(runtime, tmp_path, monkeypatch):
    old = _stub_sdk_jar(tmp_path, tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Other"])
    _register_lines(monkeypatch, {"8.18.7": old})
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(old))
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check([_user_source(tmp_path, "Gone")], [], "test source")
    msg = str(exc.value)
    assert "the VCF Ops 8.18.7 SDK jar lacks or has changed" in msg
    assert "missing class Gone in sdkstub" in msg
    assert "class library" not in msg


def _renewal_stub(tmp_path: Path, jar_name: str) -> Path:
    """A stub SDK jar whose AdapterBase has getCertificateRenewalUrls (as 2.2
    and 9.1.1 do; 8.18 does not)."""
    src = _write_java(
        tmp_path / ("rs_" + jar_name), "sdkstub/AdapterBase.java",
        "package sdkstub;\npublic class AdapterBase { "
        "public java.util.Set<String> getCertificateRenewalUrls() { return null; } }\n",
    )
    out = tmp_path / ("ro_" + jar_name)
    out.mkdir()
    subprocess.run(["javac", "--release", "11", "-d", str(out), str(src)],
                   check=True, capture_output=True)
    return _jar_of(out, tmp_path / jar_name)


@needs_javac
def test_required_run_without_the_8_18_jar_fails_naming_8_18(runtime, tmp_path, monkeypatch, capsys):
    """Review B2: required, only the 9.1.1 jar supplied, source calling a
    member 8.18 lacks: the run must fail naming 8.18.7, not pass."""
    (tmp_path / "elsewhere").mkdir()
    absent_818 = _touch_jar(tmp_path / "elsewhere" / "vrops-adapters-sdk-8.18.7.jar")
    new = _renewal_stub(tmp_path, "vrops-adapters-sdk-9.1.1.0100.jar")
    _register_lines(monkeypatch, {"8.18.7": absent_818, "9.1.1.0100": new})
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(new))
    src = _write_src(tmp_path, "Ren",
                     "class Ren { Object r(sdkstub.AdapterBase b){ return b.getCertificateRenewalUrls(); } }")
    # Not required: the 9.1.1 leg passes, 8.18.7 gets its SKIPPED box.
    assert sdk_builder._sdk_compat_check([src], [], "test source") is False
    err = capsys.readouterr().err
    assert "compiles against the VCF Ops 9.1.1.0100 SDK jar" in err
    assert "SDK COMPAT CHECK SKIPPED: test source vs the VCF Ops 8.18.7 SDK jar" in err
    # Required: fails naming 8.18.7.
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    with pytest.raises(sdk_builder.SdkCompatUnavailable) as exc:
        sdk_builder._sdk_compat_check([src], [], "test source")
    assert "the VCF Ops 8.18.7 SDK jar could not run" in str(exc.value)
    assert "9.1.1.0100 SDK jar could not run" not in str(exc.value)
    # Narrowed to the one line the run covers (a CI matrix row): passes.
    monkeypatch.setenv("VCFCF_SDK_COMPAT_LEGS", "9.1.1.0100")
    assert sdk_builder._sdk_compat_check([src], [], "test source") is True


def test_unknown_leg_key_is_a_configuration_error(runtime, monkeypatch):
    monkeypatch.setenv("VCFCF_SDK_COMPAT_LEGS", "8.18.7,9.2")
    with pytest.raises(sdk_builder.SdkCompatUnavailable, match="unknown line"):
        sdk_builder._sdk_compat_check([], [], "test source")


def test_a_jar_with_a_known_name_but_another_hash_does_not_cover_the_line(
    runtime, tmp_path, monkeypatch, capsys,
):
    fake = _touch_jar(tmp_path / "vrops-adapters-sdk-8.18.7.jar")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(fake))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_LEGS", "8.18.7")
    monkeypatch.setattr(sdk_builder, "_find_compat_javac", lambda *_a: (None, None, []))
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    err = capsys.readouterr().err
    assert "sha256 matches no known line" in err
    assert "vrops-adapters-sdk-8.18.7.jar was supplied but its sha256" in err


@needs_javac
def test_stub_jars_are_deterministic_and_distinct_per_name(tmp_path):
    """PR #258 CI: equal-content stubs written in the same second had equal
    sha256, so two 'lines' collapsed into one on a fast runner. Stub bytes
    now depend only on content and name, the same on every machine."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _stub_sdk_jar(tmp_path / "a", tmp_path / "vrops-adapters-sdk-8.18.7.jar", ["Present"])
    b = _stub_sdk_jar(tmp_path / "b", tmp_path / "vrops-adapters-sdk-9.1.1.0100.jar", ["Present"])
    assert sdk_builder._sha256_of(a) != sdk_builder._sha256_of(b)
    again = tmp_path / "again"
    again.mkdir()
    (again / "x").mkdir()
    c = _stub_sdk_jar(again / "x", again / "vrops-adapters-sdk-8.18.7.jar", ["Present"])
    assert sdk_builder._sha256_of(c) == sdk_builder._sha256_of(a)


def test_identical_jar_bytes_cover_one_line_only(runtime, tmp_path, monkeypatch, capsys):
    """Two files with the same bytes are the same jar: they cover one line,
    and the other line is reported as not covered (what CI saw)."""
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    a = _touch_jar(tmp_path / "x" / "vrops-adapters-sdk-8.18.7.jar")
    b = _touch_jar(tmp_path / "y" / "vrops-adapters-sdk-9.1.1.0100.jar")
    assert sdk_builder._sha256_of(a) == sdk_builder._sha256_of(b)
    monkeypatch.setattr(sdk_builder, "_SDK_COMPAT_LINES", (
        sdk_builder._CompatLine("8.18.7", a.name, sdk_builder._sha256_of(a)),
        sdk_builder._CompatLine("9.1.1.0100", b.name, "0" * 64),
    ))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", os.pathsep.join([str(a), str(b)]))
    monkeypatch.setattr(sdk_builder, "_sdk_compat_leg", lambda *a_, **k: True)
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    assert "SKIPPED: test source vs the VCF Ops 9.1.1.0100 SDK jar" in capsys.readouterr().err
