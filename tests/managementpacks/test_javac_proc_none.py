"""No classpath jar can run an annotation processor in an SDK build (sdk-runtime#1).

javac before JDK 23 discovers processors through
META-INF/services/javax.annotation.processing.Processor in any classpath jar
and runs them inside the compiler, so a third-party jar in a pak's lib/ could
execute code on the build host. Every javac call the factory and the kit make
passes -proc:none:

  - sdk_builder._compile           (the adapter compile, build-sdk / validate-sdk)
  - sdk_builder._ensure_framework_jar (the framework jar, factory and kit)
  - sdk_builder._sdk_compat_leg    (one compile per supported line)
  - adapter_framework/build-framework.sh (factory-only primary compile)

The fixture is a processor whose init() throws: if it runs, the compile fails.
The kit ships a path-relocated copy of sdk_builder.py, so these cover the kit
path too; test_kit_sdk_builder_keeps_proc_none checks the copy directly.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder

_JAVAC = shutil.which("javac")
_JAR = shutil.which("jar")

needs_jdk = pytest.mark.skipif(
    _JAVAC is None or _JAR is None, reason="needs javac and jar on PATH")

_BOOM = """package evil;
import java.util.Set;
import javax.annotation.processing.*;
import javax.lang.model.SourceVersion;
import javax.lang.model.element.TypeElement;
@SupportedAnnotationTypes("*")
public class Boom extends AbstractProcessor {
    @Override public synchronized void init(ProcessingEnvironment env) {
        throw new IllegalStateException("ANNOTATION PROCESSOR RAN");
    }
    @Override public boolean process(Set<? extends TypeElement> a, RoundEnvironment r) {
        return false;
    }
    @Override public SourceVersion getSupportedSourceVersion() {
        return SourceVersion.latestSupported();
    }
}
"""

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _processor_jar(tmp_path: Path, jar_path: Path) -> Path:
    """A jar that registers evil.Boom as a classpath annotation processor."""
    src = _write(tmp_path / "boomsrc", "evil/Boom.java", _BOOM)
    out = tmp_path / "boomout"
    out.mkdir()
    subprocess.run([_JAVAC, "--release", "11", "-d", str(out), str(src)],
                   check=True, capture_output=True)
    jar_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(jar_path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF", _ZIP_EPOCH),
                    f"Manifest-Version: 1.0\nX-Stub-Jar: {jar_path.name}\n")
        zf.writestr(
            zipfile.ZipInfo("META-INF/services/javax.annotation.processing.Processor",
                            _ZIP_EPOCH),
            "evil.Boom\n")
        for cls in sorted(out.rglob("*.class")):
            zf.writestr(zipfile.ZipInfo(str(cls.relative_to(out)), _ZIP_EPOCH),
                        cls.read_bytes())
    return jar_path


def _plain_source(root: Path) -> Path:
    return _write(root, "plain/A.java", "package plain;\npublic class A {}\n")


def _processors_run_by_default() -> bool:
    """JDK 23+ no longer runs classpath processors without -proc; before it, the
    fixture must actually fire without -proc:none or the tests prove nothing."""
    return (sdk_builder._javac_major(_JAVAC) or 0) < 23


@needs_jdk
def test_fixture_processor_runs_without_proc_none(tmp_path):
    if not _processors_run_by_default():
        pytest.skip("this JDK does not run classpath processors by default")
    jar = _processor_jar(tmp_path, tmp_path / "boom.jar")
    out = tmp_path / "classes"
    out.mkdir()
    r = subprocess.run(
        [_JAVAC, "--release", "11", "-cp", str(jar), "-d", str(out),
         str(_plain_source(tmp_path / "src"))],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "ANNOTATION PROCESSOR RAN" in r.stdout + r.stderr


@needs_jdk
def test_adapter_compile_does_not_run_a_classpath_processor(tmp_path):
    jar = _processor_jar(tmp_path, tmp_path / "lib" / "third-party.jar")
    sdk_builder._compile(_JAVAC, str(jar), [_plain_source(tmp_path / "src")],
                         tmp_path / "classes")
    assert (tmp_path / "classes" / "plain" / "A.class").is_file()


@needs_jdk
def test_framework_compile_does_not_run_a_classpath_processor(tmp_path, monkeypatch):
    """The framework classpath is the SDK jar alone; a doctored SDK jar must
    not run code either."""
    sdk_jar = _processor_jar(tmp_path, tmp_path / "sdk" / "vrops-adapters-sdk-2.2.jar")
    fw_src = tmp_path / "fw" / "src"
    _plain_source(fw_src)
    runtime = tmp_path / "adapter_runtime"
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", fw_src)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime)
    monkeypatch.setenv("VCFCF_SDK_JAR", str(sdk_jar))
    sdk_builder._ensure_framework_jar()
    assert (runtime / "vcfcf-adapter-base.jar").is_file()


@needs_jdk
def test_compat_leg_does_not_run_a_classpath_processor(tmp_path, monkeypatch, capsys):
    """A leg's classpath is the line's SDK jar plus the pak's other jars."""
    for name in ("VCFCF_SDK_COMPAT_JAR", "VCFCF_SDK_COMPAT_JARS",
                 "VCFCF_SDK_COMPAT_JAVAC", "VCFCF_SDK_COMPAT_REQUIRED", "VCFCF_SDK_JAR"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    runtime = tmp_path / "adapter_runtime"
    runtime.mkdir()
    monkeypatch.setattr(sdk_builder, "_ADAPTER_RUNTIME_DIR", runtime)
    monkeypatch.setattr(sdk_builder, "_ADAPTER_FRAMEWORK_SRC_DIR", tmp_path / "fw" / "src")
    leg_jar = _processor_jar(tmp_path / "leg", tmp_path / "vrops-adapters-sdk-8.18.7.jar")
    other = _processor_jar(tmp_path / "other", tmp_path / "lib" / "third-party.jar")
    monkeypatch.setattr(sdk_builder, "_SDK_COMPAT_LINES", (
        sdk_builder._CompatLine("8.18.7", leg_jar.name, sdk_builder._sha256_of(leg_jar)),
    ))
    monkeypatch.setenv("VCFCF_SDK_COMPAT_JARS", str(leg_jar))
    assert sdk_builder._sdk_compat_check(
        [_plain_source(tmp_path / "src")], [other], "test source") is True
    assert "compiles against the VCF Ops 8.18.7 SDK jar" in capsys.readouterr().err


@needs_jdk
def test_build_framework_script_does_not_run_a_classpath_processor(tmp_path):
    """build-framework.sh in a scratch package tree whose SDK jar carries the
    processor; the script's own javac line must pass -proc:none."""
    script_src = (Path(sdk_builder.__file__).parent / "adapter_framework"
                  / "build-framework.sh")
    pkg = tmp_path / "pkgroot" / "vcfcf_managementpacks"
    (pkg / "adapter_framework").mkdir(parents=True)
    script = pkg / "adapter_framework" / "build-framework.sh"
    shutil.copy(script_src, script)
    _plain_source(pkg / "adapter_framework" / "src")
    _processor_jar(tmp_path, pkg / "adapter_runtime" / "vrops-adapters-sdk-2.2.jar")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("VCFCF_") and k != "PYTHONPATH"}
    env["VCFCF_FRAMEWORK_VERSION"] = "test"
    r = subprocess.run([shutil.which("bash") or "/bin/bash", str(script)],
                       capture_output=True, text=True, env=env, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ANNOTATION PROCESSOR RAN" not in r.stdout + r.stderr
    assert (pkg / "adapter_runtime" / "vcfcf-adapter-base.jar").is_file()


def test_every_javac_command_in_sdk_builder_passes_proc_none():
    """Static guard: a new javac call path cannot land without -proc:none.
    Counts the '--release' list entries (each javac command builds one) and
    the -proc:none entries."""
    text = Path(sdk_builder.__file__).read_text(encoding="utf-8")
    release_args = text.count('"--release", str(')
    assert release_args >= 3
    assert text.count('"-proc:none",') == release_args


def test_kit_sdk_builder_keeps_proc_none():
    """The kit's relocated sdk_builder.py still passes -proc:none everywhere."""
    from vcfcf_managementpacks import buildkit
    kit_text = buildkit._apply_rewrites(
        Path(sdk_builder.__file__).read_text(encoding="utf-8"),
        buildkit._IMPORT_REWRITES["sdk_builder.py"],
    )
    release_args = kit_text.count('"--release", str(')
    assert release_args >= 3
    assert kit_text.count('"-proc:none",') == release_args
