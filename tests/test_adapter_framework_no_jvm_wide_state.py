"""Guard: the Tier 2 adapter framework never changes JVM-wide state.

Each pak bundles its own vcfcf-adapter-base.jar, loaded by that adapter's
own class loader, so paks built on different buildkit versions run side by
side on one collector (issue #214). That is safe only while the framework
touches nothing shared by the whole collector JVM: no system properties, no
default socket factory, hostname verifier, SSL context, authenticator,
cookie handler, proxy selector, locale or time zone, no security provider
registration, no URL stream handler factory. This test greps the framework
source (comments stripped) for the setters of that state.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC = (
    Path(__file__).resolve().parent.parent
    / "src" / "vcfcf_managementpacks" / "adapter_framework" / "src"
)

# Calls that change state every class loader in the JVM sees.
_JVM_WIDE_SETTERS = [
    r"System\s*\.\s*setProperty\s*\(",
    r"System\s*\.\s*setProperties\s*\(",
    r"System\s*\.\s*clearProperty\s*\(",
    r"System\s*\.\s*setSecurityManager\s*\(",
    r"System\s*\.\s*set(?:Out|Err|In)\s*\(",
    r"HttpsURLConnection\s*\.\s*setDefaultSSLSocketFactory\s*\(",
    r"HttpsURLConnection\s*\.\s*setDefaultHostnameVerifier\s*\(",
    r"HttpURLConnection\s*\.\s*setFollowRedirects\s*\(",
    r"SSLContext\s*\.\s*setDefault\s*\(",
    r"Security\s*\.\s*(?:addProvider|insertProviderAt|removeProvider|setProperty)\s*\(",
    r"Authenticator\s*\.\s*setDefault\s*\(",
    r"CookieHandler\s*\.\s*setDefault\s*\(",
    r"ProxySelector\s*\.\s*setDefault\s*\(",
    r"ResponseCache\s*\.\s*setDefault\s*\(",
    r"Locale\s*\.\s*setDefault\s*\(",
    r"TimeZone\s*\.\s*setDefault\s*\(",
    r"URL\s*\.\s*setURLStreamHandlerFactory\s*\(",
    r"URLConnection\s*\.\s*setDefaultUseCaches\s*\(",
    r"Thread\s*\.\s*setDefaultUncaughtExceptionHandler\s*\(",
    r"Configurator\s*\.\s*setRootLevel\s*\(",
]


def _strip_comments(java: str) -> str:
    """Drop /* */ and // comments; string literals are kept (crudely)."""
    java = re.sub(r"/\*.*?\*/", " ", java, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", java)


def _framework_sources():
    return sorted(_SRC.rglob("*.java"))


def test_framework_sources_present():
    assert _framework_sources(), f"no framework sources under {_SRC}"


@pytest.mark.parametrize("pattern", _JVM_WIDE_SETTERS)
def test_no_jvm_wide_setter(pattern):
    hits = []
    rx = re.compile(pattern)
    for path in _framework_sources():
        code = _strip_comments(path.read_text(encoding="utf-8"))
        for m in rx.finditer(code):
            line = code.count("\n", 0, m.start()) + 1
            hits.append(f"{path.relative_to(_SRC)}:~{line}: {m.group(0)}")
    assert not hits, (
        "the adapter framework must not change JVM-wide state (paks with "
        "different framework versions share one collector JVM):\n  "
        + "\n  ".join(hits)
    )


def test_guard_catches_a_setter():
    code = _strip_comments(
        "class X { void f() { /* System.setProperty(\"a\",\"b\") */\n"
        "  HttpsURLConnection.setDefaultHostnameVerifier((h, s) -> true); } }"
    )
    assert re.search(_JVM_WIDE_SETTERS[0], code) is None  # commented out
    assert re.search(
        r"HttpsURLConnection\s*\.\s*setDefaultHostnameVerifier\s*\(", code
    )
