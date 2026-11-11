"""Release builds accept only known SDK jars; hand builds warn (issue #343).

A release build is build-sdk --release (VCFCF_RELEASE_BUILD=1) or any run
with --require-sdk-compat / VCFCF_SDK_COMPAT_REQUIRED=1. In it the primary
jar must be a known jar of the 9.0 line and every compat jar a known jar,
with no override. A hand build makes the same check, prints a boxed warning
and goes on; validate-sdk warns and still passes. build-framework.sh and
run_stitch_tests.sh apply the same rule in shell.

The seam for stub jars: "known" is a sha256 in sdk_builder._SDK_COMPAT_LINES.
In-process tests replace that table with monkeypatch (``_known_as``), and
shell tests rewrite the table in a *copy* of the script. Nothing a real
build can pass (flag, environment variable, file) reaches the table, which
``test_no_environment_makes_an_unknown_jar_known`` and the PROVENANCE /
script equality tests pin.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import cli, sdk_builder
from vcfcf_managementpacks.sdk_builder import SdkBuildError, SdkJarRejected

_PKG = Path(sdk_builder.__file__).parent
_FW = _PKG / "adapter_framework"
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_ENV = (
    "VCFCF_SDK_COMPAT_JAR", "VCFCF_SDK_COMPAT_JARS", "VCFCF_SDK_COMPAT_JAVAC",
    "VCFCF_SDK_COMPAT_REQUIRED", "VCFCF_SDK_COMPAT_LEGS", "VCFCF_SDK_JAR",
    "VCFCF_RELEASE_BUILD", "GITHUB_ACTIONS",
)
_N_9_0_2_0 = "vrops-adapters-sdk-9.0.2.0.25137845.jar"
_N_9_0_2_0200 = "vrops-adapters-sdk-9.0.2.0200.25431135.jar"
_N_8_18_7 = "vrops-adapters-sdk-8.18.7.25423534.jar"
_N_9_1_1 = "vrops-adapters-sdk-9.1.1.0100.25795063.jar"
_RELEASE_SWITCHES = [("VCFCF_RELEASE_BUILD", "1"), ("VCFCF_SDK_COMPAT_REQUIRED", "1"),
                     ("VCFCF_SDK_COMPAT_REQUIRED", "true")]


@pytest.fixture()
def runtime(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "adapter_runtime"
    runtime_dir.mkdir()
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", tmp_path / "fwsrc")
    monkeypatch.setattr(sdk_builder, "_FORMER_NAMES_NOTED", set())
    for name in _ENV:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    return runtime_dir


def _jar(path: Path, tag: str = "", major: int = 61) -> Path:
    """A stub jar; tag varies its bytes (and so its sha256)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF", _ZIP_EPOCH),
                    f"Manifest-Version: 1.0\nX-Tag: {tag or path.name}\n")
        zf.writestr(zipfile.ZipInfo("sdk/A.class", _ZIP_EPOCH),
                    b"\xca\xfe\xba\xbe\x00\x00" + major.to_bytes(2, "big") + b"\x00" * 8)
    return path


def _known_as(monkeypatch, **jar_by_name):
    """The seam: the real table, with the named known jars' sha256 replaced
    by the stubs' (in this test process only)."""
    lines = []
    for line in sdk_builder._SDK_COMPAT_LINES:
        jars = tuple(
            k._replace(sha256=sdk_builder._sha256_of(jar_by_name[k.file_name]))
            if k.file_name in jar_by_name else k
            for k in line.jars)
        lines.append(line._replace(jars=jars))
    monkeypatch.setattr(sdk_builder, "_SDK_COMPAT_LINES", tuple(lines))


# ---------------------------------------------------------------------------
# The rule (in-process)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [_N_9_0_2_0, _N_9_0_2_0200])
@pytest.mark.parametrize("env", _RELEASE_SWITCHES)
def test_a_known_9_0_primary_and_known_compat_jars_pass_a_release_build(
        runtime, tmp_path, monkeypatch, capsys, name, env):
    primary = _jar(tmp_path / "p.jar", "9.0")
    j818 = _jar(tmp_path / "c1.jar", "8.18")
    j911 = _jar(tmp_path / "c2.jar", "9.1")
    _known_as(monkeypatch, **{name: primary, _N_8_18_7: j818, _N_9_1_1: j911})
    monkeypatch.setenv(*env)
    assert sdk_builder._check_sdk_jars("build-sdk", primary, [j818, j911]) == []
    assert "WARNING" not in capsys.readouterr().err


@pytest.mark.parametrize("other,key,platform", [
    (_N_8_18_7, "8.18.7", "Aria Operations 8.18.7 build 25423534"),
    (_N_9_1_1, "9.1.1.0100", "VCF Operations 9.1.1.0100 build 25795063"),
])
@pytest.mark.parametrize("env", _RELEASE_SWITCHES)
def test_a_release_build_refuses_another_lines_jar_as_the_primary(
        runtime, tmp_path, monkeypatch, other, key, platform, env):
    primary = _jar(tmp_path / _N_9_0_2_0, key)  # a 9.0.2 name proves nothing
    _known_as(monkeypatch, **{other: primary})
    monkeypatch.setenv(*env)
    with pytest.raises(SdkJarRejected) as exc:
        sdk_builder._check_sdk_jars("build-sdk", primary, [])
    msg = str(exc.value)
    assert f"is {platform}, the {key} line's jar, not a 9.0 line jar" in msg
    assert "Pass it with --sdk-compat-jar instead" in msg
    assert "there is no override" in msg
    assert _N_9_0_2_0 in msg and _N_9_0_2_0200 in msg


@pytest.mark.parametrize("env", _RELEASE_SWITCHES)
def test_a_release_build_refuses_an_unknown_primary_naming_its_sha256(
        runtime, tmp_path, monkeypatch, env):
    primary = _jar(tmp_path / _N_9_0_2_0, "patched-appliance")
    monkeypatch.setenv(*env)
    with pytest.raises(SdkJarRejected) as exc:
        sdk_builder._check_sdk_jars("build-sdk", primary, [])
    msg = str(exc.value)
    assert f"has sha256 {sdk_builder._sha256_of(primary)}" in msg
    assert "matches no known SDK jar" in msg
    assert "compiles only against SDK jars the kit knows" in msg
    assert "Adding an SDK jar" in msg


@pytest.mark.parametrize("env", _RELEASE_SWITCHES)
def test_a_release_build_refuses_an_unknown_compat_jar(runtime, tmp_path, monkeypatch, env):
    primary = _jar(tmp_path / "p.jar", "9.0")
    known = _jar(tmp_path / "c1.jar", "8.18")
    unknown = _jar(tmp_path / "c2.jar", "mystery")
    _known_as(monkeypatch, **{_N_9_0_2_0: primary, _N_8_18_7: known})
    monkeypatch.setenv(*env)
    with pytest.raises(SdkJarRejected) as exc:
        sdk_builder._check_sdk_jars("build-sdk", primary, [known, unknown])
    msg = str(exc.value)
    assert f"compatibility SDK jar {unknown} has sha256" in msg
    assert str(known) not in msg and f"primary SDK jar {primary}" not in msg


def test_a_9_0_jar_is_a_valid_compat_jar_in_a_release_build(runtime, tmp_path, monkeypatch):
    """Factory CI's 9.0 row passes the 9.0 jar as its one compat jar."""
    nine = _jar(tmp_path / "c.jar", "9.0")
    _known_as(monkeypatch, **{_N_9_0_2_0: nine})
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    assert sdk_builder._check_sdk_jars("build-framework.sh", None, [nine]) == []


def test_the_primary_listed_again_as_a_compat_jar_is_checked_once(runtime, tmp_path, monkeypatch):
    primary = _jar(tmp_path / "p.jar", "mystery")
    problems = sdk_builder._check_sdk_jars("build-sdk", primary, [primary])
    assert len(problems) == 1 and "primary SDK jar" in problems[0]


def test_check_primary_false_checks_only_the_compat_jars(runtime, tmp_path, monkeypatch):
    primary = _jar(tmp_path / "p.jar", "mystery")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    assert sdk_builder._check_sdk_jars("x", primary, [], check_primary=False) == []


@pytest.mark.parametrize("make", ["other-line", "unknown", "unknown-compat"])
def test_a_hand_build_warns_in_a_box_and_goes_on(runtime, tmp_path, monkeypatch, capsys, make):
    primary = _jar(tmp_path / "p.jar", "p")
    compat = []
    if make == "other-line":
        _known_as(monkeypatch, **{_N_9_1_1: primary})
    elif make == "unknown-compat":
        _known_as(monkeypatch, **{_N_9_0_2_0: primary})
        compat = [_jar(tmp_path / "c.jar", "c")]
    problems = sdk_builder._check_sdk_jars("build-sdk", primary, compat)
    assert len(problems) == 1
    err = capsys.readouterr().err
    bar = "  " + "=" * 72
    assert err.count(bar) == 2
    assert "WARNING: SDK JAR A RELEASE BUILD WOULD REFUSE: build-sdk" in err
    assert "This run continues, but a pak built this way may not run on every supported platform line." in err
    assert "A release build (--release, --require-sdk-compat or VCFCF_SDK_COMPAT_REQUIRED=1) refuses it" in err
    if make == "other-line":
        assert "the 9.1.1.0100 line's jar, not a 9.0 line jar" in err
    else:
        assert "matches no known SDK jar" in err


def test_no_environment_makes_an_unknown_jar_known(runtime, tmp_path, monkeypatch):
    """The shipped check has no switch: every kit environment variable set,
    an unknown jar is still refused in a release build."""
    primary = _jar(tmp_path / _N_9_0_2_0, "mystery")
    for name, value in (("VCFCF_SDK_JAR", str(primary)), ("VCFCF_SDK_COMPAT_LEGS", "9.0"),
                        ("VCFCF_SDK_COMPAT_JARS", str(primary)),
                        ("VCFCF_SDK_COMPAT_JAVAC", "/nonexistent/javac"),
                        ("VCFCF_RELEASE_BUILD", "1"), ("VCFCF_SDK_COMPAT_REQUIRED", "1"),
                        ("VCFCF_FRAMEWORK_VERSION", "9.9.9"), ("GITHUB_ACTIONS", "true")):
        monkeypatch.setenv(name, value)
    with pytest.raises(SdkJarRejected):
        sdk_builder._check_run_sdk_jars("build-sdk")


def test_the_real_table_knows_exactly_the_provenance_jars():
    """What a real (unpatched) process accepts: the four PROVENANCE hashes."""
    shas = {k.sha256 for line in sdk_builder._SDK_COMPAT_LINES for k in line.jars}
    assert shas == {
        "2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54",
        "a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b",
        "45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea",
        "79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7",
    }
    prov = (_PKG / "adapter_runtime" / "PROVENANCE.md").read_text(encoding="utf-8")
    table = prov.split("## The compile targets", 1)[1].split("\n## ", 1)[0]
    assert all(s in table for s in shas)


def test_adapter_version_ref_still_records_an_unknown_jar(runtime, tmp_path, monkeypatch):
    jar = _jar(runtime / "vrops-adapters-sdk-9.0.2.0300.25999999.jar", "new")
    assert sdk_builder._adapter_version_ref() == "9.0.2.0300.25999999"


# ---------------------------------------------------------------------------
# The rule is wired into build-sdk, validate-sdk and the framework pass
# ---------------------------------------------------------------------------


@pytest.fixture()
def project(tmp_path, runtime, monkeypatch, capsys):
    proj = sdk_builder.scaffold_sdk_project("Known Jars", tmp_path)
    capsys.readouterr()
    calls = []
    monkeypatch.setattr(sdk_builder, "_detect_jdk", lambda: "javac")
    monkeypatch.setattr(sdk_builder, "_detect_jar_tool", lambda: "jar")
    monkeypatch.setattr(sdk_builder, "_ensure_framework_jar", lambda: calls.append("framework"))
    monkeypatch.setattr(sdk_builder, "_build_classpath_jars", lambda _pd: [])
    monkeypatch.setattr(sdk_builder, "_require_javac_reads_jar", lambda *a: None)
    monkeypatch.setattr(sdk_builder, "_compile", lambda *a, **k: calls.append("compile"))

    def stop(*a, **k):
        calls.append("compat")
        raise SdkBuildError("stopped after the compat pass")

    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", stop)
    return proj, calls


def test_build_sdk_release_refuses_before_any_compile(project, tmp_path, monkeypatch):
    proj, calls = project
    monkeypatch.setenv("VCFCF_SDK_JAR", str(_jar(tmp_path / "sdk.jar", "mystery")))
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", "1")
    with pytest.raises(SdkJarRejected):
        sdk_builder.build_sdk_pak(proj, tmp_path / "out")
    assert calls == []


def test_build_sdk_hand_build_warns_and_compiles(project, tmp_path, monkeypatch, capsys):
    proj, calls = project
    monkeypatch.setenv("VCFCF_SDK_JAR", str(_jar(tmp_path / "sdk.jar", "mystery")))
    with pytest.raises(SdkBuildError, match="stopped after the compat pass"):
        sdk_builder.build_sdk_pak(proj, tmp_path / "out")
    assert calls == ["framework", "compile", "compat"]
    assert "WARNING: SDK JAR A RELEASE BUILD WOULD REFUSE: build-sdk" in capsys.readouterr().err


def test_build_sdk_cli_release_flag_refuses(project, tmp_path, monkeypatch, capsys):
    """--release through the factory CLI: exit 1 with the refusal."""
    proj, _calls = project
    jar = _jar(tmp_path / "sdk.jar", "mystery")
    args = type("A", (), {"project_dir": str(proj), "output": str(tmp_path / "out"),
                          "sdk_jar": str(jar), "release": True, "sdk_compat_jar": None,
                          "require_sdk_compat": False, "pak_compare_warn_only": False})()
    assert cli.cmd_build_sdk(args) == 1
    assert "compiles only against SDK jars the kit knows" in capsys.readouterr().err


def _validate(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(sdk_builder.shutil, "which", lambda _n: "/usr/bin/javac")
    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", lambda *a, **k: True)
    monkeypatch.setenv("VCFCF_SDK_JAR", str(_jar(tmp_path / "sdk.jar", "mystery")))
    return sdk_builder.validate_sdk_project(proj)


def test_validate_sdk_warns_and_passes_for_an_unknown_jar(project, tmp_path, monkeypatch, capsys):
    proj, calls = project
    assert _validate(proj, tmp_path, monkeypatch) == []
    assert "compile" in calls
    assert "WARNING: SDK JAR A RELEASE BUILD WOULD REFUSE: validate-sdk" in capsys.readouterr().err


def test_validate_sdk_cli_exits_0_for_an_unknown_jar(project, tmp_path, monkeypatch, capsys):
    proj, _calls = project
    monkeypatch.setattr(sdk_builder.shutil, "which", lambda _n: "/usr/bin/javac")
    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", lambda *a, **k: True)
    jar = _jar(tmp_path / "sdk.jar", "mystery")
    args = type("A", (), {"project_dir": str(proj), "sdk_jar": str(jar),
                          "sdk_compat_jar": None, "require_sdk_compat": False})()
    assert cli.cmd_validate_sdk(args) == 0
    out = capsys.readouterr()
    assert "OK:" in out.out and "WOULD REFUSE" in out.err


def test_validate_sdk_required_reports_the_refusal(project, tmp_path, monkeypatch):
    proj, calls = project
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    errors = _validate(proj, tmp_path, monkeypatch)
    assert len(errors) == 1 and "compiles only against SDK jars the kit knows" in errors[0]
    assert "compile" not in calls


def test_framework_pass_release_refusal_is_exit_3(runtime, tmp_path, monkeypatch, capsys):
    (tmp_path / "fwsrc" / "x").mkdir(parents=True)
    (tmp_path / "fwsrc" / "x" / "A.java").write_text("package x; class A {}\n", encoding="utf-8")
    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", lambda *a, **k: True)
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(_jar(tmp_path / "c.jar", "mystery")))
    assert sdk_builder.check_framework_sdk_compat() == 0  # hand run: warns
    assert "WOULD REFUSE: build-framework.sh" in capsys.readouterr().err
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    assert sdk_builder.check_framework_sdk_compat() == sdk_builder.COMPAT_COULD_NOT_RUN == 3
    assert "compiles only against SDK jars the kit knows" in capsys.readouterr().err


def test_framework_pass_skips_the_primary_when_the_shell_checked_it(
        runtime, tmp_path, monkeypatch):
    (tmp_path / "fwsrc" / "x").mkdir(parents=True)
    (tmp_path / "fwsrc" / "x" / "A.java").write_text("package x; class A {}\n", encoding="utf-8")
    monkeypatch.setattr(sdk_builder, "_sdk_compat_check", lambda *a, **k: True)
    _jar(runtime / _N_9_0_2_0, "mystery")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    assert sdk_builder.check_framework_sdk_compat(check_primary=False) == 0
    assert sdk_builder.check_framework_sdk_compat(check_primary=True) == 3


# ---------------------------------------------------------------------------
# build-framework.sh and run_stitch_tests.sh (shell; copies of the scripts
# carry rewritten tables, the shell form of the seam)
# ---------------------------------------------------------------------------

_SHA_9_0_2_0 = "2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54"
_SHA_9_1_1 = "79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7"


def _table(text: str) -> set:
    block = text.split('KNOWN_SDK_JARS="', 1)[1].split('"', 1)[0]
    return {tuple(row.split("|")) for row in block.splitlines()}


def test_run_stitch_tests_knows_the_same_jars_as_sdk_builder():
    py = {(k.sha256, line.key, k.platform)
          for line in sdk_builder._SDK_COMPAT_LINES for k in line.jars}
    assert _table((_FW / "run_stitch_tests.sh").read_text(encoding="utf-8")) == py
    assert _table((_FW / "build-framework.sh").read_text(encoding="utf-8")) == py


def _framework_tree(tmp_path: Path, javac_version: str):
    pkg = tmp_path / "pkgroot" / "vcfcf_managementpacks"
    (pkg / "adapter_framework" / "src").mkdir(parents=True)
    (pkg / "adapter_runtime").mkdir()
    script = pkg / "adapter_framework" / "build-framework.sh"
    shutil.copy(_FW / "build-framework.sh", script)
    tools = tmp_path / "bin"
    tools.mkdir()
    fake = tools / "javac"
    fake.write_text(f'#!/bin/sh\necho "javac {javac_version}" >&2\nexit 0\n', encoding="utf-8")
    fake.chmod(0o755)
    for tool in ("dirname", "tr", "awk", "cut", "basename", "python3", "find", "sort",
                 "wc", "rm", "mkdir", "grep", "sed", "head", "sha256sum"):
        found = shutil.which(tool)
        if found:
            (tools / tool).symlink_to(found)
    env = {k: v for k, v in os.environ.items() if not k.startswith("VCFCF_")}
    env["PATH"] = str(tools)
    return pkg / "adapter_runtime", script, env


def _bash(script: Path, env, *args) -> subprocess.CompletedProcess:
    return subprocess.run([shutil.which("bash") or "/bin/bash", str(script), *args],
                          capture_output=True, text=True, env=env, timeout=300)


def _shell_knows(script: Path, real_sha: str, stub: Path) -> None:
    text = script.read_text(encoding="utf-8")
    assert real_sha in text
    script.write_text(text.replace(real_sha, sdk_builder._sha256_of(stub)), encoding="utf-8")


# Values sdk_builder reads as true (str.strip().lower()); the shell must agree.
_PADDED_TRUE = ["1", "1 ", " TRUE", "\tyes\n"]


@pytest.mark.parametrize("value", _PADDED_TRUE)
def test_padded_switch_values_are_a_release_run_in_python(monkeypatch, value):
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", value)
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", value)
    assert sdk_builder._is_release_build() and sdk_builder._compat_required()


@pytest.mark.parametrize("value", _PADDED_TRUE)
@pytest.mark.parametrize("switch", ["VCFCF_SDK_COMPAT_REQUIRED", "VCFCF_RELEASE_BUILD"])
def test_build_framework_release_run_refuses_an_unknown_primary(tmp_path, switch, value):
    rt, script, env = _framework_tree(tmp_path, "17.0.2")
    jar = _jar(rt / _N_9_0_2_0, "mystery")
    env[switch] = value
    r = _bash(script, env)
    assert r.returncode == 3, r.stdout + r.stderr
    assert f"has sha256 {sdk_builder._sha256_of(jar)}, which matches no known SDK jar" in r.stderr
    assert "there is no override" in r.stderr
    assert "Compiling" not in r.stdout


def test_build_framework_release_run_refuses_another_lines_primary(tmp_path):
    rt, script, env = _framework_tree(tmp_path, "25.0.1")
    jar = _jar(rt / _N_9_0_2_0, "9.1", major=69)
    _shell_knows(script, _SHA_9_1_1, jar)
    env["VCFCF_SDK_COMPAT_REQUIRED"] = "1"
    r = _bash(script, env)
    assert r.returncode == 3, r.stdout + r.stderr
    assert ("is VCF Operations 9.1.1.0100 build 25795063, the 9.1.1.0100 line's jar, "
            "not a 9.0 line jar") in r.stderr


def test_build_framework_release_run_accepts_a_known_9_0_primary(tmp_path):
    """Gets past the check: the next stop is the fake javac's version check."""
    rt, script, env = _framework_tree(tmp_path, "11.0.24")
    jar = _jar(rt / _N_9_0_2_0, "9.0")
    _shell_knows(script, _SHA_9_0_2_0, jar)
    env["VCFCF_SDK_COMPAT_REQUIRED"] = "1"
    r = _bash(script, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "WOULD REFUSE" not in r.stdout and "no override" not in r.stderr
    assert "javac 11 cannot read" in r.stderr


def test_build_framework_hand_run_warns_in_a_box_and_goes_on(tmp_path):
    rt, script, env = _framework_tree(tmp_path, "11.0.24")
    _jar(rt / _N_9_0_2_0, "mystery")
    r = _bash(script, env)
    assert "WARNING: SDK JAR A RELEASE BUILD WOULD REFUSE: build-framework.sh" in r.stdout
    assert r.stdout.count("  " + "=" * 72) == 2
    # It went on to the next check (the fake javac 11 cannot read Java 17).
    assert r.returncode == 1 and "javac 11 cannot read" in r.stderr


def _stitch_copy(tmp_path: Path) -> Path:
    fw = tmp_path / "fw"
    (fw / "src").mkdir(parents=True)
    (fw / "test" / "com" / "vcfcf" / "adapter" / "stitch").mkdir(parents=True)
    script = fw / "run_stitch_tests.sh"
    shutil.copy(_FW / "run_stitch_tests.sh", script)
    return script


_needs_jdk = pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None,
                                reason="needs javac and java on PATH")


@pytest.mark.parametrize("value", ["0", "", " ", "no", "t rue", "11"])
def test_build_framework_non_true_values_are_a_hand_run(tmp_path, value):
    rt, script, env = _framework_tree(tmp_path, "11.0.24")
    _jar(rt / _N_9_0_2_0, "mystery")
    env["VCFCF_RELEASE_BUILD"] = value
    env["VCFCF_SDK_COMPAT_REQUIRED"] = value
    r = _bash(script, env)
    assert "no override" not in r.stderr
    assert "WARNING: SDK JAR A RELEASE BUILD WOULD REFUSE" in r.stdout


@_needs_jdk
@pytest.mark.parametrize("value", _PADDED_TRUE)
@pytest.mark.parametrize("switch", ["VCFCF_SDK_COMPAT_REQUIRED", "VCFCF_RELEASE_BUILD"])
def test_run_stitch_tests_release_run_refuses_an_unknown_jar(tmp_path, switch, value):
    script = _stitch_copy(tmp_path)
    jar = _jar(tmp_path / "sdk.jar", "mystery")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VCFCF_")}
    env.update({"VCFCF_SDK_JAR": str(jar), switch: value})
    r = _bash(script, env)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "runs only against a known SDK jar, and there is no override" in r.stderr
    assert sdk_builder._sha256_of(jar) in r.stderr


@_needs_jdk
def test_run_stitch_tests_hand_run_warns_and_goes_on(tmp_path):
    script = _stitch_copy(tmp_path)
    jar = _jar(tmp_path / "sdk.jar", "mystery")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VCFCF_")}
    env["VCFCF_SDK_JAR"] = str(jar)
    r = _bash(script, env)
    assert "WARNING: SDK JAR A RELEASE RUN WOULD REFUSE: run_stitch_tests" in r.stdout
    assert "runs only against" not in r.stderr
    assert "run_stitch_tests: " in r.stdout  # it reached the compile banner


@_needs_jdk
def test_run_stitch_tests_release_run_accepts_any_known_line(tmp_path):
    script = _stitch_copy(tmp_path)
    jar = _jar(tmp_path / "sdk.jar", "8.18", major=55)
    text = script.read_text(encoding="utf-8")
    script.write_text(text.replace("45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea",
                                   sdk_builder._sha256_of(jar)), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VCFCF_")}
    env.update({"VCFCF_SDK_JAR": str(jar), "VCFCF_SDK_COMPAT_REQUIRED": "1"})
    r = _bash(script, env)
    assert "no override" not in r.stderr and "WOULD REFUSE" not in r.stdout


# ---------------------------------------------------------------------------
# The framework jar records the SDK jar it was compiled against (review W2)
# ---------------------------------------------------------------------------


def _marker_source(runtime: Path) -> None:
    src = runtime.parent / "fwsrc" / "com" / "vcfcf" / "testfw"
    src.mkdir(parents=True, exist_ok=True)
    (src / "Marker.java").write_text(
        "package com.vcfcf.testfw;\npublic final class Marker {}\n", encoding="utf-8")


def _framework_sdk_sha(runtime: Path) -> str:
    attrs = sdk_builder._framework_manifest_attrs(runtime / "vcfcf-adapter-base.jar")
    return attrs[sdk_builder._FRAMEWORK_SDK_SHA_ATTR]


_needs_jar_tool = pytest.mark.skipif(shutil.which("javac") is None or shutil.which("jar") is None,
                                     reason="needs javac and jar on PATH")


@_needs_jar_tool
def test_a_release_build_after_a_hand_build_with_another_jar_recompiles_the_framework(
        runtime, tmp_path, monkeypatch, capsys):
    _marker_source(runtime)
    known = _jar(runtime / _N_9_0_2_0, "9.0")
    other = _jar(tmp_path / "patched" / "vrops-adapters-sdk.jar", "patched-appliance")
    _known_as(monkeypatch, **{_N_9_0_2_0: known})

    # Hand build with --sdk-jar <unknown>: warns, compiles the framework against it.
    monkeypatch.setenv("VCFCF_SDK_JAR", str(other))
    sdk_builder._check_run_sdk_jars("build-sdk")
    sdk_builder._ensure_framework_jar()
    assert _framework_sdk_sha(runtime) == sdk_builder._sha256_of(other)
    capsys.readouterr()

    # Release build with the known jar: passes the check, and the framework
    # jar (mtime-fresh) is recompiled, not reused.
    monkeypatch.delenv("VCFCF_SDK_JAR")
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", "1")
    assert sdk_builder._check_run_sdk_jars("build-sdk") == []
    sdk_builder._ensure_framework_jar()
    err = capsys.readouterr().err
    assert "is STALE" in err and "compiling" in err
    assert f"compiled against sha256 {sdk_builder._sha256_of(other)[:12]}" in err
    assert _framework_sdk_sha(runtime) == sdk_builder._sha256_of(known)

    # Same jar again: a true no-op.
    def _forbidden_run(*args, **kwargs):
        raise AssertionError("framework jar rebuilt although it matches the primary jar")
    monkeypatch.setattr(subprocess, "run", _forbidden_run)
    sdk_builder._ensure_framework_jar()


@_needs_jar_tool
def test_a_framework_jar_with_no_recorded_sdk_jar_is_rebuilt(runtime, tmp_path, capsys):
    """A jar built before 1.0.28 has no X-Vcfcf-Sdk-Sha256: which jar compiled
    it is unknown, so it is rebuilt."""
    _marker_source(runtime)
    _jar(runtime / _N_9_0_2_0, "9.0")
    fw = runtime / "vcfcf-adapter-base.jar"
    with zipfile.ZipFile(fw, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nImplementation-Version: 1.0.27\n")
    later = fw.stat().st_mtime + 60
    os.utime(fw, (later, later))  # newer than the source: fresh by mtime
    sdk_builder._ensure_framework_jar()
    assert "compiled against an unrecorded SDK jar" in capsys.readouterr().err
    assert _framework_sdk_sha(runtime) == sdk_builder._sha256_of(runtime / _N_9_0_2_0)


@pytest.mark.parametrize("release", [False, True])
def test_a_framework_jar_for_another_sdk_jar_with_no_source_to_rebuild(
        runtime, tmp_path, monkeypatch, capsys, release):
    """No framework source (runtime-only): the jar cannot be rebuilt, so a
    mismatch warns in a hand build and stops a release build."""
    _jar(runtime / _N_9_0_2_0, "9.0")
    fw = runtime / "vcfcf-adapter-base.jar"
    with zipfile.ZipFile(fw, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", f"Manifest-Version: 1.0\n"
                    f"{sdk_builder._FRAMEWORK_SDK_SHA_ATTR}: {'0' * 64}\n")
    if release:
        monkeypatch.setenv("VCFCF_RELEASE_BUILD", "1")
        with pytest.raises(SdkBuildError, match="cannot be rebuilt"):
            sdk_builder._ensure_framework_jar()
    else:
        sdk_builder._ensure_framework_jar()
        assert "WARNING: framework: vcfcf-adapter-base.jar cannot be rebuilt" in capsys.readouterr().err


def test_build_framework_stamps_the_sdk_jar_sha256():
    """build-framework.sh writes the same attribute build-sdk checks."""
    text = (_FW / "build-framework.sh").read_text(encoding="utf-8")
    assert f"\\n{sdk_builder._FRAMEWORK_SDK_SHA_ATTR}: %s\\n" in text
    assert '"${SDK_SHA:-unknown}" > "$MANIFEST_FILE"' in text
