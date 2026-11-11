"""SDK jar names by platform version and build (2026-11-11).

The Broadcom SDK jars are named vrops-adapters-sdk-<version>.<build>.jar
for the platform the bytes come from. Covered here, hermetically:

  - each current name and each former name (-2.2, -8.18.7, -9.1.1.0100) is
    recognised wherever the kit looks a jar up by name, with one INFO line
    for a former name;
  - a compat jar under its current or former name is never a primary-SDK
    candidate;
  - the 9.0 line knows two jars, and the 9.0.2.0200 one covers the 9.0 leg;
  - conf/version.txt Adapter-Version-Ref comes from the compile jar's
    sha256 under any file name, else a <version>.<build> file name, else
    "unknown";
  - a javac older than a jar's class files fails with a plain message
    naming the jar, its platform line, the Java it needs and the Java found,
    for the primary compile and per compat leg;
  - the 9.0 SKIPPED hint when VCFCF_SDK_JAR is another line's jar;
  - no message still points at the nonexistent appliance paths.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder
from vcfcf_managementpacks.sdk_builder import SdkBuildError
from vcfcf_managementpacks.sdk_project import SdkProjectDef

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_ENV = (
    "VCFCF_SDK_COMPAT_JAR", "VCFCF_SDK_COMPAT_JARS", "VCFCF_SDK_COMPAT_JAVAC",
    "VCFCF_SDK_COMPAT_REQUIRED", "VCFCF_SDK_COMPAT_LEGS", "VCFCF_SDK_JAR",
)


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


def _jar(path: Path, major: int = 61, tag: str = "") -> Path:
    """A jar with one fake class of the given class-file major; tag varies
    the bytes (and so the sha256) between otherwise equal jars."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF", _ZIP_EPOCH),
                    f"Manifest-Version: 1.0\nX-Tag: {tag or path.name}\n")
        zf.writestr(zipfile.ZipInfo("sdk/A.class", _ZIP_EPOCH),
                    b"\xca\xfe\xba\xbe\x00\x00" + major.to_bytes(2, "big") + b"\x00" * 8)
    return path


def _lines_with(monkeypatch, **sha_by_name):
    """The real line table with the named known jars' sha256 replaced (stub
    bytes stand in for the Broadcom jars, which tests cannot hold)."""
    lines = []
    for line in sdk_builder._SDK_COMPAT_LINES:
        jars = tuple(k._replace(sha256=sha_by_name.get(k.file_name, k.sha256)) for k in line.jars)
        lines.append(line._replace(jars=jars))
    monkeypatch.setattr(sdk_builder, "_SDK_COMPAT_LINES", tuple(lines))


def _project() -> SdkProjectDef:
    return SdkProjectDef(
        name="X", version="1.0.0", build_number=1, adapter_kind="x",
        tier=2, description="", dependencies=[], entry_class="a.B",
        source_path=Path("/dev/null"),
    )


def _ref(project=None) -> str:
    text = sdk_builder._generate_version_txt(project or _project())
    return next(l for l in text.splitlines() if l.startswith("Adapter-Version-Ref="))


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def test_the_table_names_each_jar_by_version_and_build():
    by_name = {k.file_name: (line.key, k) for line in sdk_builder._SDK_COMPAT_LINES
               for k in line.jars}
    assert set(by_name) == {
        "vrops-adapters-sdk-9.0.2.0.25137845.jar",
        "vrops-adapters-sdk-9.0.2.0200.25431135.jar",
        "vrops-adapters-sdk-8.18.7.25423534.jar",
        "vrops-adapters-sdk-9.1.1.0100.25795063.jar",
    }
    for name, (key, known) in by_name.items():
        assert name == f"vrops-adapters-sdk-{known.version_build}.jar"
        assert sdk_builder._SDK_JAR_VERSION_BUILD_RE.match(name)
    assert by_name["vrops-adapters-sdk-9.0.2.0.25137845.jar"][1].former_names == (
        "vrops-adapters-sdk-2.2.jar",)
    assert by_name["vrops-adapters-sdk-8.18.7.25423534.jar"][1].former_names == (
        "vrops-adapters-sdk-8.18.7.jar",)
    assert by_name["vrops-adapters-sdk-9.1.1.0100.25795063.jar"][1].former_names == (
        "vrops-adapters-sdk-9.1.1.0100.jar",)
    assert by_name["vrops-adapters-sdk-9.0.2.0200.25431135.jar"][1].sha256 == (
        "a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b")


def test_the_9_0_2_0200_jar_belongs_to_the_9_0_line():
    line = sdk_builder._line_for_sha(
        "a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b")
    assert line is not None and line.key == "9.0"
    ga = sdk_builder._line_for_sha(
        "2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54")
    assert ga is line


# ---------------------------------------------------------------------------
# Names: current and former, primary and compat
# ---------------------------------------------------------------------------

_PRIMARY_NAMES = [
    "vrops-adapters-sdk-9.0.2.0.25137845.jar",
    "vrops-adapters-sdk-9.0.2.0200.25431135.jar",
    "vrops-adapters-sdk-2.2.jar",  # former
]
_COMPAT_NAMES = [
    "vrops-adapters-sdk-8.18.7.25423534.jar",
    "vrops-adapters-sdk-9.1.1.0100.25795063.jar",
    "vrops-adapters-sdk-8.18.7.jar",      # former
    "vrops-adapters-sdk-9.1.1.0100.jar",  # former
]
_FORMER = {"vrops-adapters-sdk-2.2.jar", "vrops-adapters-sdk-8.18.7.jar",
           "vrops-adapters-sdk-9.1.1.0100.jar"}


@pytest.mark.parametrize("name", _PRIMARY_NAMES)
def test_each_primary_name_is_the_primary_jar(runtime, name, capsys):
    jar = _jar(runtime / name)
    assert sdk_builder._primary_sdk_jar() == jar
    sdk_builder._primary_sdk_jar()  # a second lookup prints nothing more
    err = capsys.readouterr().err
    if name in _FORMER:
        assert err.count(f"INFO: {name} is the former name of "
                         "vrops-adapters-sdk-9.0.2.0.25137845.jar") == 1
    else:
        assert "former name" not in err


@pytest.mark.parametrize("name", _COMPAT_NAMES)
def test_each_compat_name_is_a_leg_and_never_a_primary_candidate(runtime, name, capsys):
    primary = _jar(runtime / "vrops-adapters-sdk-9.0.2.0.25137845.jar")
    compat = _jar(runtime / name, major=55)
    assert sdk_builder._is_compat_sdk_jar(compat)
    assert compat not in sdk_builder._runtime_sdk_jar_candidates()
    assert sdk_builder._primary_sdk_jar() == primary  # no "exactly one" error
    assert sdk_builder._resolve_compat_sdk_jars() == [compat]
    assert sdk_builder._compat_leg_jars() == [primary, compat]
    err = capsys.readouterr().err
    assert ("is the former name of" in err) == (name in _FORMER)


@pytest.mark.parametrize("name", _COMPAT_NAMES)
def test_a_compat_jar_alone_is_no_primary_jar(runtime, tmp_path, name):
    _jar(runtime / name, major=55)
    assert sdk_builder._primary_sdk_jar() is None
    with pytest.raises(SdkBuildError, match="not found in adapter_runtime"):
        sdk_builder._build_classpath_jars(tmp_path)


def test_the_current_compat_name_wins_over_the_former_one(runtime):
    new = _jar(runtime / "vrops-adapters-sdk-8.18.7.25423534.jar", major=55)
    _jar(runtime / "vrops-adapters-sdk-8.18.7.jar", major=55)
    assert sdk_builder._resolve_compat_sdk_jars() == [new]


def test_two_primary_jars_are_still_an_error(runtime):
    _jar(runtime / "vrops-adapters-sdk-2.2.jar")
    _jar(runtime / "vrops-adapters-sdk-9.0.2.0.25137845.jar")
    with pytest.raises(SdkBuildError, match="exactly one primary SDK jar") as exc:
        sdk_builder._primary_sdk_jar()
    assert "vrops-adapters-sdk-9.0.2.0.25137845.jar" in str(exc.value)


def test_an_explicit_sdk_jar_of_any_name_is_used(runtime, tmp_path, monkeypatch):
    env_jar = _jar(tmp_path / "anything-at-all.jar")
    monkeypatch.setenv("VCFCF_SDK_JAR", str(env_jar))
    assert sdk_builder._build_classpath_jars(tmp_path)[0] == env_jar
    assert sdk_builder._primary_compile_jar() == env_jar


# ---------------------------------------------------------------------------
# The 9.0 line's second jar
# ---------------------------------------------------------------------------


def test_the_9_0_2_0200_jar_satisfies_the_required_9_0_leg(runtime, tmp_path, monkeypatch, capsys):
    patched = _jar(tmp_path / "vrops-adapters-sdk.jar", tag="0200")  # as copied off the box
    _lines_with(monkeypatch, **{
        "vrops-adapters-sdk-9.0.2.0200.25431135.jar": sdk_builder._sha256_of(patched)})
    monkeypatch.setenv("VCFCF_SDK_JAR", str(patched))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_LEGS", "9.0")
    monkeypatch.setenv("VCFCF_SDK_COMPAT_REQUIRED", "1")
    seen = []
    monkeypatch.setattr(sdk_builder, "_sdk_compat_leg",
                        lambda jar, line, *a, **k: seen.append((jar, line.key)) or True)
    assert sdk_builder._sdk_compat_check([], [], "test source") is True
    assert seen == [(patched, "9.0")]
    assert "SKIPPED" not in capsys.readouterr().err


def test_either_9_0_jar_is_named_when_the_9_0_leg_is_missing(runtime, capsys):
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    err = capsys.readouterr().err
    block = err.split("vs the VCF Ops 9.0 SDK jar", 1)[1].split("SKIPPED", 1)[0]
    assert "vrops-adapters-sdk-9.0.2.0.25137845.jar (VCF Operations 9.0.2.0 build 25137845" in block
    assert "vrops-adapters-sdk-9.0.2.0200.25431135.jar (VCF Operations 9.0.2.0200 build 25431135" in block


# ---------------------------------------------------------------------------
# conf/version.txt Adapter-Version-Ref
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [
    "vrops-adapters-sdk-9.0.2.0.25137845.jar",
    "vrops-adapters-sdk-2.2.jar",          # the former name
    "vrops-adapters-sdk.jar",              # the appliance's name
    "something-else.jar",                  # only via VCFCF_SDK_JAR
])
def test_a_known_jar_stamps_its_version_and_build_under_any_name(
    runtime, tmp_path, monkeypatch, name,
):
    jar = _jar(tmp_path / "src" / name, tag="ga")
    _lines_with(monkeypatch, **{
        "vrops-adapters-sdk-9.0.2.0.25137845.jar": sdk_builder._sha256_of(jar)})
    if name.startswith("vrops-adapters-sdk"):
        shutil.copy(jar, runtime / name)  # looked up in adapter_runtime/
    else:
        monkeypatch.setenv("VCFCF_SDK_JAR", str(jar))
    assert _ref() == "Adapter-Version-Ref=9.0.2.0.25137845"


def test_the_9_0_2_0200_jar_stamps_its_own_build(runtime, monkeypatch):
    jar = _jar(runtime / "vrops-adapters-sdk.jar", tag="0200")
    _lines_with(monkeypatch, **{
        "vrops-adapters-sdk-9.0.2.0200.25431135.jar": sdk_builder._sha256_of(jar)})
    assert _ref() == "Adapter-Version-Ref=9.0.2.0200.25431135"


def test_the_compile_jar_is_stamped_not_the_runtime_copy(runtime, tmp_path, monkeypatch):
    ga = _jar(runtime / "vrops-adapters-sdk-2.2.jar", tag="ga")
    patched = _jar(tmp_path / "supplied.jar", tag="0200")
    _lines_with(monkeypatch, **{
        "vrops-adapters-sdk-9.0.2.0.25137845.jar": sdk_builder._sha256_of(ga),
        "vrops-adapters-sdk-9.0.2.0200.25431135.jar": sdk_builder._sha256_of(patched)})
    assert _ref() == "Adapter-Version-Ref=9.0.2.0.25137845"
    monkeypatch.setenv("VCFCF_SDK_JAR", str(patched))
    assert _ref() == "Adapter-Version-Ref=9.0.2.0200.25431135"


def test_an_unknown_jar_with_a_version_build_name_stamps_the_name(runtime, capsys):
    _jar(runtime / "vrops-adapters-sdk-9.0.3.0.26000001.jar")
    assert _ref() == "Adapter-Version-Ref=9.0.3.0.26000001"
    assert "matches no known SDK jar" in capsys.readouterr().err


@pytest.mark.parametrize("name", [
    "vrops-adapters-sdk.jar",
    "vrops-adapters-sdk-2.2.jar",      # 2.2 was never a version
    "vrops-adapters-sdk-1.0.jar",
    "vrops-adapters-sdk-9.1.1.0.jar",  # a version but no build
])
def test_an_unknown_jar_with_no_version_build_name_stamps_unknown(runtime, name):
    _jar(runtime / name)
    assert _ref() == "Adapter-Version-Ref=unknown"


def test_no_sdk_jar_stamps_n_a(runtime):
    assert _ref() == "Adapter-Version-Ref=N/A"


def test_old_and_new_names_of_the_same_bytes_give_the_same_version_txt(
    runtime, tmp_path, monkeypatch,
):
    jar = _jar(tmp_path / "x.jar", tag="ga")
    _lines_with(monkeypatch, **{
        "vrops-adapters-sdk-9.0.2.0.25137845.jar": sdk_builder._sha256_of(jar)})
    texts = []
    for name in ("vrops-adapters-sdk-2.2.jar", "vrops-adapters-sdk-9.0.2.0.25137845.jar"):
        target = runtime / name
        shutil.copy(jar, target)
        texts.append(sdk_builder._generate_version_txt(_project()))
        target.unlink()
    assert texts[0] == texts[1]


# ---------------------------------------------------------------------------
# A javac too old to read the jar
# ---------------------------------------------------------------------------

_LINE_CASES = [
    # (reference jar name, class major, Java, platform text, line key)
    ("vrops-adapters-sdk-8.18.7.25423534.jar", 55, 11,
     "Aria Operations 8.18.7 build 25423534", "8.18.7"),
    ("vrops-adapters-sdk-9.0.2.0.25137845.jar", 61, 17,
     "VCF Operations 9.0.2.0 build 25137845", "9.0"),
    ("vrops-adapters-sdk-9.0.2.0200.25431135.jar", 61, 17,
     "VCF Operations 9.0.2.0200 build 25431135", "9.0"),
    ("vrops-adapters-sdk-9.1.1.0100.25795063.jar", 69, 25,
     "VCF Operations 9.1.1.0100 build 25795063", "9.1.1.0100"),
]


@pytest.mark.parametrize("name,major,java,platform,key", _LINE_CASES)
def test_javac_too_old_for_the_compile_jar_says_so(
    runtime, tmp_path, monkeypatch, name, major, java, platform, key,
):
    jar = _jar(tmp_path / name, major=major)
    _lines_with(monkeypatch, **{name: sdk_builder._sha256_of(jar)})
    monkeypatch.setattr(sdk_builder, "_javac_major", lambda _j: java - 1)
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._require_javac_reads_jar("/opt/old/bin/javac", jar)
    msg = str(exc.value)
    assert f"javac {java - 1} cannot read the SDK jar {jar}" in msg
    assert f"({platform} ({key} line))" in msg
    assert f"class files are Java {java} (class-file major {major})" in msg
    assert f"needs JDK {java} or newer; found JDK {java - 1} (/opt/old/bin/javac)" in msg
    # New enough: no error.
    monkeypatch.setattr(sdk_builder, "_javac_major", lambda _j: java)
    sdk_builder._require_javac_reads_jar("/opt/new/bin/javac", jar)


def test_javac_too_old_for_an_unknown_jar_still_says_so(runtime, tmp_path, monkeypatch):
    jar = _jar(tmp_path / "vrops-adapters-sdk.jar", major=61)
    monkeypatch.setattr(sdk_builder, "_javac_major", lambda _j: 11)
    with pytest.raises(SdkBuildError, match="matches no known platform") as exc:
        sdk_builder._require_javac_reads_jar("javac", jar)
    assert "needs JDK 17 or newer; found JDK 11" in str(exc.value)


def test_the_framework_compile_checks_javac_before_compiling(runtime, tmp_path, monkeypatch):
    src = tmp_path / "fwsrc" / "fw" / "F.java"
    src.parent.mkdir(parents=True)
    src.write_text("package fw; class F {}\n", encoding="utf-8")
    _jar(runtime / "vrops-adapters-sdk-9.0.2.0.25137845.jar", major=61)
    monkeypatch.setattr(sdk_builder.shutil, "which", lambda tool: f"/opt/jdk11/bin/{tool}")
    monkeypatch.setattr(sdk_builder, "_javac_major", lambda _j: 11)

    def no_compile(*_a, **_k):
        raise AssertionError("javac must not run")
    monkeypatch.setattr(sdk_builder.subprocess, "run", no_compile)
    with pytest.raises(SdkBuildError, match="javac 11 cannot read the SDK jar"):
        sdk_builder._ensure_framework_jar()


@pytest.mark.parametrize("name,major,java,platform,key", _LINE_CASES)
def test_a_compat_leg_skips_naming_the_jar_line_and_java(
    runtime, tmp_path, monkeypatch, capsys, name, major, java, platform, key,
):
    jar = _jar(tmp_path / name, major=major)
    _lines_with(monkeypatch, **{name: sdk_builder._sha256_of(jar)})
    line = sdk_builder._line_for_sha(sdk_builder._sha256_of(jar))
    monkeypatch.setattr(sdk_builder, "_find_compat_javac",
                        lambda need, label: (None, None, [f"/usr/bin/javac ({java - 1})"]))
    assert sdk_builder._sdk_compat_leg(jar, line, [], [], "test source") is False
    err = capsys.readouterr().err
    assert f"SKIPPED: test source vs the VCF Ops {key} SDK jar" in err
    assert f"no javac can read {name} ({platform} ({key} line))" in err
    assert f"class files are Java {java} (class-file major {major})" in err
    assert f"needs JDK {max(java, 11)} or newer; found /usr/bin/javac ({java - 1})" in err


# ---------------------------------------------------------------------------
# The 9.0 hint when VCFCF_SDK_JAR is another line's jar
# ---------------------------------------------------------------------------


def test_9_0_hint_names_the_other_lines_jar_in_vcfcf_sdk_jar(runtime, tmp_path, monkeypatch, capsys):
    other = _jar(tmp_path / "vrops-adapters-sdk.jar", major=69)
    _lines_with(monkeypatch, **{
        "vrops-adapters-sdk-9.1.1.0100.25795063.jar": sdk_builder._sha256_of(other)})
    monkeypatch.setenv("VCFCF_SDK_JAR", str(other))
    monkeypatch.setattr(sdk_builder, "_sdk_compat_leg", lambda *a, **k: True)
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    err = capsys.readouterr().err
    block = err.split("vs the VCF Ops 9.0 SDK jar", 1)[1]
    assert (f"VCFCF_SDK_JAR is {other}, the 9.1.1.0100 line's jar (VCF Operations "
            "9.1.1.0100 build 25795063 (9.1.1.0100 line))") in block
    assert "point VCFCF_SDK_JAR (--sdk-jar) at a 9.0.2 jar" in block
    assert "or set VCFCF_SDK_JAR" not in block


def test_9_0_hint_for_an_unknown_jar_in_vcfcf_sdk_jar(runtime, tmp_path, monkeypatch, capsys):
    unknown = _jar(tmp_path / "vrops-adapters-sdk.jar")
    monkeypatch.setenv("VCFCF_SDK_JAR", str(unknown))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_LEGS", "9.0")
    monkeypatch.setattr(sdk_builder, "_sdk_compat_leg", lambda *a, **k: True)
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    err = capsys.readouterr().err
    assert f"VCFCF_SDK_JAR is {unknown}, a jar whose sha256 matches no known jar" in err


def test_9_0_hint_without_any_primary_jar(runtime, monkeypatch, capsys):
    monkeypatch.setenv("VCFCF_SDK_COMPAT_LEGS", "9.0")
    assert sdk_builder._sdk_compat_check([], [], "test source") is False
    err = capsys.readouterr().err
    assert ("it is the primary SDK jar: put it in adapter_runtime/ as "
            "vrops-adapters-sdk-9.0.2.0.25137845.jar or set VCFCF_SDK_JAR") in err


# ---------------------------------------------------------------------------
# Messages point at real paths
# ---------------------------------------------------------------------------

_PKG = Path(sdk_builder.__file__).parent


@pytest.mark.parametrize("rel", [
    "sdk_builder.py", "buildkit.py", "cli.py", "README.md",
    "adapter_framework/build-framework.sh", "adapter_framework/run_stitch_tests.sh",
])
def test_no_message_names_a_path_that_exists_on_no_appliance(rel):
    text = (_PKG / rel).read_text(encoding="utf-8")
    assert "common-lib" not in text
    assert "/usr/lib/vmware-vcops/suite-api/" not in text
    assert "any 9.x" not in text
    assert "JDK 11+ on PATH" not in text
    assert "Install JDK 11+" not in text


def test_the_howto_gives_the_real_path_and_the_jdk():
    howto = sdk_builder._SDK_JAR_HOWTO
    assert "/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar" in howto
    assert "9.0.2.0 build 25137845 or 9.0.2.0200 build 25431135" in howto
    assert "JDK 17 or newer" in howto
    assert "optional compatibility checks" in howto


# ---------------------------------------------------------------------------
# build-framework.sh: names and the javac check
# ---------------------------------------------------------------------------

_BUILD_FRAMEWORK = _PKG / "adapter_framework" / "build-framework.sh"


def _script_tree(tmp_path: Path, javac_version: str) -> tuple:
    pkg = tmp_path / "pkgroot" / "vcfcf_managementpacks"
    (pkg / "adapter_framework" / "src").mkdir(parents=True)
    (pkg / "adapter_runtime").mkdir()
    script = pkg / "adapter_framework" / "build-framework.sh"
    shutil.copy(_BUILD_FRAMEWORK, script)
    tools = tmp_path / "bin"
    tools.mkdir()
    fake = tools / "javac"
    fake.write_text(f'#!/bin/sh\necho "javac {javac_version}" >&2\nexit 0\n', encoding="utf-8")
    fake.chmod(0o755)
    for tool in ("dirname", "tr", "awk", "cut", "basename", "python3", "find", "sort",
                 "wc", "rm", "mkdir", "grep", "sed", "head"):
        found = shutil.which(tool)
        if found:
            (tools / tool).symlink_to(found)
    env = {k: v for k, v in os.environ.items() if not k.startswith("VCFCF_")}
    env["PATH"] = str(tools)
    return pkg / "adapter_runtime", script, env


def _run(script: Path, env) -> subprocess.CompletedProcess:
    return subprocess.run([shutil.which("bash") or "/bin/bash", str(script)],
                          capture_output=True, text=True, env=env, timeout=120)


def test_build_framework_stops_plainly_on_a_javac_too_old(tmp_path):
    rt, script, env = _script_tree(tmp_path, "11.0.24")
    _jar(rt / "vrops-adapters-sdk-9.0.2.0.25137845.jar", major=61)
    r = _run(script, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert ("javac 11 cannot read vrops-adapters-sdk-9.0.2.0.25137845.jar "
            "(the 9.0 line's SDK jar)") in r.stderr
    assert "class files are Java 17 (class-file major 61), so it needs JDK 17 or newer" in r.stderr


def test_build_framework_accepts_the_former_name_with_a_note(tmp_path):
    rt, script, env = _script_tree(tmp_path, "11.0.24")
    _jar(rt / "vrops-adapters-sdk-2.2.jar", major=61)
    r = _run(script, env)
    assert "INFO: vrops-adapters-sdk-2.2.jar is the former name of" in r.stdout
    assert "cannot read vrops-adapters-sdk-2.2.jar" in r.stderr  # it found and checked it


def test_build_framework_refuses_two_9_0_jars(tmp_path):
    rt, script, env = _script_tree(tmp_path, "17.0.2")
    _jar(rt / "vrops-adapters-sdk-2.2.jar")
    _jar(rt / "vrops-adapters-sdk-9.0.2.0.25137845.jar")
    r = _run(script, env)
    assert r.returncode == 1
    assert "must hold exactly one 9.0.2 SDK jar" in r.stderr


def test_build_framework_without_the_jar_gives_the_real_path(tmp_path):
    _rt, script, env = _script_tree(tmp_path, "17.0.2")
    r = _run(script, env)
    assert r.returncode == 1
    assert "/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar" in r.stderr
