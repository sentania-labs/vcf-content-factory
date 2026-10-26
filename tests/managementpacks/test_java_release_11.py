"""Every compile uses javac --release 11 (issue #252, RULE-019).

-source 11 -target 11 emits Java 11 bytecode but still links against the
running JDK's library, so a Java 12+ call compiled on JDK 17 and failed
with NoSuchMethodError on the 8.18 collector (OpenJDK 11). --release 11
rejects it at build time. The fixture calls String.indent(int), added in
Java 12.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder
from vcfcf_managementpacks.sdk_builder import SdkBuildError

_JAVAC = shutil.which("javac")

needs_javac_12 = pytest.mark.skipif(
    _JAVAC is None or (sdk_builder._javac_major(_JAVAC) or 0) < 12,
    reason="needs javac 12+ on PATH (a JDK whose own library has String.indent)",
)

_JAVA12_CALL = (
    "package fixture;\n"
    "public class UsesJava12 {\n"
    "    public static String pad(String s) { return s.indent(2); }\n"
    "}\n"
)
_JAVA11_ONLY = (
    "package fixture;\n"
    "public class UsesJava11 {\n"
    "    public static boolean blank(String s) { return s.isBlank(); }\n"
    "}\n"
)


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@needs_javac_12
def test_java12_api_call_fails_the_primary_compile(tmp_path):
    src = _write(tmp_path / "src", "fixture/UsesJava12.java", _JAVA12_CALL)
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._compile(_JAVAC, "", [src], tmp_path / "classes")
    msg = str(exc.value)
    assert "cannot find symbol" in msg
    assert "indent" in msg


@needs_javac_12
def test_the_fixture_is_meaningful_without_release(tmp_path):
    """Control: the same source compiles with the old -source/-target flags,
    which is exactly the gap --release closes."""
    src = _write(tmp_path / "src", "fixture/UsesJava12.java", _JAVA12_CALL)
    out = tmp_path / "classes"
    out.mkdir()
    r = subprocess.run(
        [_JAVAC, "-source", "11", "-target", "11", "-Xlint:-options",
         "-d", str(out), str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


@needs_javac_12
def test_java11_api_compiles_to_java11_bytecode(tmp_path):
    src = _write(tmp_path / "src", "fixture/UsesJava11.java", _JAVA11_ONLY)
    out = tmp_path / "classes"
    sdk_builder._compile(_JAVAC, "", [src], out)
    head = (out / "fixture" / "UsesJava11.class").read_bytes()[:8]
    assert int.from_bytes(head[6:8], "big") == 55  # Java 11


@needs_javac_12
def test_java12_api_call_fails_the_framework_compile(tmp_path, monkeypatch):
    runtime = tmp_path / "adapter_runtime"
    runtime.mkdir()
    fw_src = tmp_path / "adapter_framework" / "src"
    _write(fw_src, "fixture/UsesJava12.java", _JAVA12_CALL)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", fw_src)
    sdk = tmp_path / "vrops-adapters-sdk-2.2.jar"
    subprocess.run(
        ["jar", "cf", str(sdk), "-C", str(tmp_path), "adapter_runtime"],
        check=True, capture_output=True,
    )
    monkeypatch.setenv("VCFCF_SDK_JAR", str(sdk))
    with pytest.raises(SdkBuildError, match="Framework compilation failed"):
        sdk_builder._ensure_framework_jar()
    assert not (runtime / "vcfcf-adapter-base.jar").exists()


@needs_javac_12
def test_java12_api_call_fails_a_compat_leg(tmp_path, monkeypatch):
    """A leg uses --release 11 too: on a newer JDK it still checks the Java 11
    library, not the leg JDK's own."""
    for name in ("VCFCF_SDK_COMPAT_JARS", "VCFCF_SDK_COMPAT_JAVAC",
                 "VCFCF_SDK_COMPAT_REQUIRED"):
        monkeypatch.setenv(name, "")
    jar = tmp_path / "vrops-adapters-sdk-8.18.7.jar"
    stub = _write(tmp_path / "stub", "sdkstub/S.java", "package sdkstub; public class S {}\n")
    classes = tmp_path / "stubclasses"
    classes.mkdir()
    subprocess.run([_JAVAC, "--release", "11", "-d", str(classes), str(stub)], check=True)
    subprocess.run(["jar", "cf", str(jar), "-C", str(classes), "."], check=True)
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JAR", str(jar))
    src = _write(tmp_path / "src", "fixture/UsesJava12.java", _JAVA12_CALL)
    with pytest.raises(SdkBuildError) as exc:
        sdk_builder._sdk_compat_check([src], [], "fixture source")
    assert "against the VCF Ops 8.18.7 SDK jar" in str(exc.value)
    assert "indent" in str(exc.value)


def test_build_framework_script_uses_release_11():
    script = (Path(sdk_builder.__file__).parent / "adapter_framework" / "build-framework.sh")
    text = script.read_text(encoding="utf-8")
    assert "javac --release 11" in text
    assert "-source 11" not in text.replace("not -source/-target", "")
