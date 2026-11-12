"""The framework's logging harnesses against the real SDK logger factory.

``adapter_framework/test/com/vcfcf/adapter/TestConnectionLoggingTest.java``
(issue #322: Test Connection must not shadow a pak's conf/logging.properties)
and ``ComponentLoggerTest.java`` (#224, #228) run the real
``AdapterLoggerFactoryImpl`` of an SDK jar against log4j-core, each in its
own JVM. Both need a Broadcom SDK jar and log4j-core, which this public repo
does not carry, so this test skips without them:

  - SDK jars: ``VCFCF_SDK_JAR`` or the primary jar in ``adapter_runtime/``,
    plus every compat jar (``VCFCF_SDK_COMPAT_JARS``, ``--sdk-compat-jar``
    names in ``adapter_runtime/``). Each jar runs on a JDK new enough to
    read it; a jar no local JDK reads is skipped (the 9.1.1.0100 jar needs
    JDK 25).
  - log4j-core and log4j-api: ``VCFCF_LOG4J_CLASSPATH`` (colon-separated),
    else every jar in ``adapter_runtime/lib/``.

TestConnectionLoggingTest runs on every jar: on the 9.x SDKs every
scenario, on 8.18.7 (no ``AdapterLoggerConfig``) the unchanged-raise checks.
ComponentLoggerTest runs on 9.x jars only (the 8.18 factory needs its own
logger context for instance loggers).
"""
from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder

_FW = Path(sdk_builder.__file__).parent / "adapter_framework"
_TEST = _FW / "test"


def _sdk_jars():
    jars = []
    seen = set()
    try:
        candidates = [sdk_builder._primary_compile_jar()] + sdk_builder._resolve_compat_sdk_jars()
    except sdk_builder.SdkBuildError:
        candidates = []
    for jar in candidates:
        if jar is None or not jar.is_file():
            continue
        key = os.path.realpath(jar)
        if key not in seen:
            seen.add(key)
            jars.append(jar)
    return jars


def _log4j_classpath():
    env = os.environ.get("VCFCF_LOG4J_CLASSPATH", "").strip()
    if env:
        return [p for p in env.split(os.pathsep) if p]
    lib = sdk_builder._ADAPTER_RUNTIME_DIR / "lib"
    return [str(j) for j in sorted(lib.glob("*.jar"))] if lib.is_dir() else []


def _has_log4j_core(classpath):
    for entry in classpath:
        try:
            with zipfile.ZipFile(entry) as zf:
                if "org/apache/logging/log4j/core/LoggerContext.class" in zf.namelist():
                    return True
        except (OSError, zipfile.BadZipFile):
            continue
    return False


def _has_adapter_logger_config(jar: Path) -> bool:
    with zipfile.ZipFile(jar) as zf:
        return "com/integrien/alive/common/adapter3/AdapterLoggerConfig.class" in zf.namelist()


_JARS = _sdk_jars()
_LOG4J = _log4j_classpath()
pytestmark = [
    pytest.mark.skipif(not _JARS, reason="no Broadcom SDK jar (VCFCF_SDK_JAR or adapter_runtime/)"),
    pytest.mark.skipif(not _has_log4j_core(_LOG4J),
                       reason="no log4j-core (VCFCF_LOG4J_CLASSPATH or adapter_runtime/lib/)"),
]


def _run_suite(tmp_path: Path, jar: Path, suite: str, test_sources) -> str:
    need = sdk_builder._jar_required_java_major(jar)
    javac, _major, tried = sdk_builder._find_compat_javac(max(need, 11), jar.name)
    if javac is None:
        pytest.skip(f"no JDK reads {jar.name} (Java {need}); tried {', '.join(tried)}")
    java = str(Path(javac).with_name("java"))
    main, test = tmp_path / "main", tmp_path / "test"
    main.mkdir()
    test.mkdir()
    sources = sorted(str(p) for p in (_FW / "src").rglob("*.java"))
    r = subprocess.run([javac, "--release", "11", "-proc:none", "-nowarn", "-cp", str(jar),
                        "-d", str(main)] + sources, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([javac, "--release", "11", "-proc:none", "-nowarn",
                        "-cp", os.pathsep.join([str(jar), str(main)]), "-d", str(test)]
                       + [str(s) for s in test_sources], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    cp = os.pathsep.join([str(test), str(main), str(jar)] + _LOG4J)
    run = subprocess.run([java, "-cp", cp, f"com.vcfcf.adapter.{suite}"],
                         capture_output=True, text=True, timeout=300)
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert "SKIP: all" not in out, out
    assert "  FAIL: " not in out, out
    return out


@pytest.mark.parametrize("jar", _JARS, ids=lambda j: j.name)
def test_test_connection_does_not_shadow_the_pak_logging_entry(tmp_path, jar):
    """#322 on this SDK jar: on 9.x the control reproduces both symptoms and
    every fixed scenario passes, and another pak's parent-package entry does
    not stop a raise; on 8.18 the raise is unchanged. On both, the pak
    file's keys are parsed once per class and re-read on a change."""
    sources = [_TEST / "com/vcfcf/adapter/TestConnectionLoggingTest.java"] + sorted(
        (_TEST / "com/vcfcf/testpak/tc").rglob("*.java"))
    out = _run_suite(tmp_path, jar, "TestConnectionLoggingTest", sources)
    if _has_adapter_logger_config(jar):
        assert "PASS: control: instance INFO copied into collector.log (#322 symptom b)" in out
        assert "PASS: second account: helper DEBUG kept (#322 a fixed)" in out
        assert "PASS: first account: helper DEBUG kept" in out
        assert ("PASS: no pak file, another pak's parent entry (WARN) governs: "
                "raised to INFO, as before") in out
        assert "OK: 39/39 tests passed." in out
    else:
        assert "PASS: 8.18: the Test Connection helper logger is raised to INFO, as before" in out
        assert "OK: 14/14 tests passed." in out
    assert "PASS: three lookups read the file once" in out


@pytest.mark.parametrize("jar", [j for j in _JARS if _has_adapter_logger_config(j)],
                         ids=lambda j: j.name)
def test_component_logger_routing(tmp_path, jar):
    """#224 / #228 on a 9.x SDK jar (unchanged by #322)."""
    sources = [_TEST / "com/vcfcf/adapter/ComponentLoggerTest.java"] + sorted(
        (_TEST / "com/vcfcf/testpak").rglob("*.java"))
    out = _run_suite(tmp_path, jar, "ComponentLoggerTest", sources)
    assert "OK: 17/17 tests passed." in out
