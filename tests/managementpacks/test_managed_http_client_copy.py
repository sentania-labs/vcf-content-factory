"""ManagedHttpClient.copyWithUri: the DNS round-robin request copy (#252).

It replaced HttpRequest.newBuilder(HttpRequest, BiPredicate), a Java 16
call that throws NoSuchMethodError on the 8.18 collector (OpenJDK 11).
This compiles ManagedHttpClient, the auth and retry framework packages and the Java
test with javac --release 11 (no SDK jar needed) and runs the test: the
copy keeps method, headers, body, timeout, version and expect-continue,
drops restricted headers, and changes only the URI.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder

_FW = Path(sdk_builder.__file__).parent / "adapter_framework"
_JAVAC = shutil.which("javac")
_JAVA = shutil.which("java")


@pytest.mark.skipif(_JAVAC is None or _JAVA is None, reason="needs javac and java")
def test_copy_with_uri_keeps_method_headers_and_body(tmp_path):
    pkg = _FW / "src" / "com" / "vcfcf" / "adapter"
    # ManagedHttpClient needs only auth/ and retry/, which need only the JDK.
    sources = [pkg / "http" / "ManagedHttpClient.java"] \
        + sorted((pkg / "auth").glob("*.java")) + sorted((pkg / "retry").glob("*.java")) \
        + [_FW / "test" / "com" / "vcfcf" / "adapter" / "http" / "ManagedHttpClientCopyTest.java"]
    out = tmp_path / "classes"
    out.mkdir()
    compiled = subprocess.run(
        [_JAVAC, "--release", "11", "-proc:none", "-d", str(out)] + [str(s) for s in sources],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run(
        [_JAVA, "-Djdk.httpclient.allowRestrictedHeaders=host,connection",
         "-cp", str(out), "com.vcfcf.adapter.http.ManagedHttpClientCopyTest"],
        capture_output=True, text=True, timeout=120,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "ALL PASS" in run.stdout
    assert "FAIL " not in run.stdout
