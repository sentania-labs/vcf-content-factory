"""Pak vendor, contact and EULA from adapter.yaml (factory #336).

build-sdk stamped ``VCF Content Factory`` as the vendor of every pak and the
factory MIT LICENSE as its eula.txt, so a third-party pak built with the
buildkit presented itself as ours.  adapter.yaml now takes optional
``vendor``, ``vendor_contact`` and ``eula_file``.  With none of them the pak
is byte-identical to before; with ``eula_file`` the factory LICENSE still
ships, beside the bundled MIT base jar, as its notice.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import sdk_builder
from vcfcf_managementpacks.sdk_builder import (
    FRAMEWORK_NOTICE_NAME,
    _assemble_adapters_zip,
    _attribution_report,
    _build_overview_packed,
    _generate_outer_manifest,
    _generate_outer_resources_properties,
    _prop_value_escape,
    _read_license,
    _write_outer_pak,
    validate_sdk_project,
)
from vcfcf_managementpacks.sdk_project import (
    DEFAULT_VENDOR,
    SdkProjectError,
    load_sdk_project,
)

_DESCRIBE = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind key="vcfcf_widget" nameKey="1" version="1"
             xmlns="http://schemas.vmware.com/vcops/schema">
  <ResourceKinds>
    <ResourceKind key="widget_world" nameKey="2" type="7"/>
  </ResourceKinds>
</AdapterKind>
"""

_BASE_YAML = """\
name: "VCF Content Factory Widget"
version: "1.0.0"
build_number: 3
adapter_kind: "vcfcf_widget"
tier: 2
description: "Widget pak."
entry_class: "com.vcfcf.adapters.widget.WidgetAdapter"
"""

_NOTICE_ENTRY = f"vcfcf_widget/lib/{FRAMEWORK_NOTICE_NAME}"


def _project_dir(tmp_path: Path, extra_yaml: str = "") -> Path:
    project_dir = tmp_path / "widget"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "adapter.yaml").write_text(
        _BASE_YAML + textwrap.dedent(extra_yaml), encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE, encoding="utf-8")
    return project_dir


def _load(tmp_path: Path, extra_yaml: str = ""):
    return load_sdk_project(_project_dir(tmp_path, extra_yaml) / "adapter.yaml")


def _adapters_zip(project, tmp_path: Path) -> zipfile.ZipFile:
    project_dir = project.source_path.parent
    jar = tmp_path / f"{project.adapter_kind}.jar"
    if not jar.exists():
        jar.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # empty zip
    base = tmp_path / "vcfcf-adapter-base.jar"
    if not base.exists():
        base.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    data = _assemble_adapters_zip(project, project_dir, jar, [base])
    return zipfile.ZipFile(io.BytesIO(data))


def _outer_pak(project, tmp_path: Path) -> zipfile.ZipFile:
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    pak = _write_outer_pak(project, b"", out, project.source_path.parent)
    return zipfile.ZipFile(pak)


def _overview(project) -> dict:
    z = zipfile.ZipFile(io.BytesIO(_build_overview_packed(project)))
    return {t: z.read(f"overview/{t}/overview.html").decode("utf-8")
            for t in ("light", "dark")}


def _props_value(text: str, key: str) -> str:
    """Decode one java.util.Properties value (the escapes Properties.load reads)."""
    line = next(l for l in text.splitlines() if l.startswith(key + "="))
    raw = line[len(key) + 1:]
    out, i = [], 0
    while i < len(raw):
        ch = raw[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = raw[i + 1]
        if nxt == "u":
            out.append(chr(int(raw[i + 2:i + 6], 16)))
            i += 6
            continue
        out.append({"n": "\n", "r": "\r", "t": "\t", "f": "\f"}.get(nxt, nxt))
        i += 2
    # Re-pair UTF-16 surrogates the way Java strings hold them.
    return "".join(out).encode("utf-16-be", "surrogatepass").decode("utf-16-be")


# ---------------------------------------------------------------------------
# Default: unchanged
# ---------------------------------------------------------------------------

# The pre-#336 template, verbatim, for the fixture project.
_PRE_336_LIGHT = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\" class=\"light\">\n"
    "<head>\n"
    "  <meta charset=\"UTF-8\">\n"
    "  <title>VCF Content Factory Widget</title>\n"
    "  <style>\n"
    "    body { font-family: sans-serif; margin: 2em; color: #222; background: #fff; }\n"
    "    h1 { font-size: 1.4em; }\n"
    "    p  { font-size: 0.95em; color: #555; }\n"
    "  </style>\n"
    "</head>\n"
    "<body>\n"
    "  <h1>VCF Content Factory Widget</h1>\n"
    "  <p>Version 1.0.0.3</p>\n"
    "  <p>Widget pak.</p>\n"
    "  <p>Vendor: VCF Content Factory</p>\n"
    "</body>\n"
    "</html>\n"
)

_PRE_336_PROPS = (
    "# Solution localization\n"
    "version=1\n"
    "DISPLAY_NAME=VCF Content Factory Widget\n"
    "DESCRIPTION=Widget pak.\n"
    "VENDOR=VCF Content Factory\n"
)


def test_default_project_fields(tmp_path):
    p = _load(tmp_path)
    assert (p.vendor, p.vendor_declared, p.vendor_contact) == (DEFAULT_VENDOR, False, "")
    assert (p.eula_file, p.eula_path) == ("", None)


def test_default_sinks_match_pre_336_output(tmp_path):
    p = _load(tmp_path)
    pages = _overview(p)
    assert pages["light"] == _PRE_336_LIGHT
    assert pages["dark"].count("  <p>Vendor: VCF Content Factory</p>\n") == 1
    assert "Contact" not in pages["dark"]
    assert _generate_outer_resources_properties(p) == _PRE_336_PROPS
    assert '    "vendor": "VCF Content Factory",\n' in _generate_outer_manifest(p)


def test_default_eula_and_no_notice(tmp_path):
    p = _load(tmp_path)
    inner = _adapters_zip(p, tmp_path)
    outer = _outer_pak(p, tmp_path)
    license_text = _read_license().encode("utf-8")
    assert inner.read("eula.txt") == license_text
    assert outer.read("eula.txt") == license_text
    assert _NOTICE_ENTRY not in inner.namelist()
    assert not any(FRAMEWORK_NOTICE_NAME in n for n in outer.namelist())


def test_explicit_default_vendor_is_byte_identical(tmp_path):
    a = _load(tmp_path / "a")
    b = _load(tmp_path / "b", f'vendor: "{DEFAULT_VENDOR}"\n')
    assert b.vendor_declared
    assert _generate_outer_manifest(a) == _generate_outer_manifest(b)
    assert _generate_outer_resources_properties(a) == _generate_outer_resources_properties(b)
    assert _overview(a) == _overview(b)


def test_unknown_top_level_keys_still_ignored(tmp_path):
    # adapter.yaml top-level keys are not closed; #336 does not change that.
    p = _load(tmp_path, 'vendr: "typo"\nlicense: MIT\n')
    assert p.vendor == DEFAULT_VENDOR


# ---------------------------------------------------------------------------
# Override: every sink
# ---------------------------------------------------------------------------

def test_vendor_applied_in_every_sink(tmp_path):
    p = _load(tmp_path, 'vendor: "Example Labs"\n')
    assert json.loads(_generate_outer_manifest(p))["vendor"] == "Example Labs"
    assert "VENDOR=Example Labs\n" in _generate_outer_resources_properties(p)
    for page in _overview(p).values():
        assert "  <p>Vendor: Example Labs</p>\n" in page
        assert "VCF Content Factory</p>" not in page
    inner = _adapters_zip(p, tmp_path)
    outer = _outer_pak(p, tmp_path)
    for zf in (inner, outer):
        assert json.loads(zf.read("manifest.txt"))["vendor"] == "Example Labs"
    assert inner.read("manifest.txt") == outer.read("manifest.txt")
    assert b"VENDOR=Example Labs\n" in outer.read("resources/resources.properties")
    packed = zipfile.ZipFile(io.BytesIO(outer.read("overview.packed")))
    for t in ("light", "dark"):
        assert b"<p>Vendor: Example Labs</p>" in packed.read(f"overview/{t}/overview.html")


def test_contact_shown_on_overview_only_when_set(tmp_path):
    absent = _load(tmp_path / "a", 'vendor: "Example Labs"\n')
    for page in _overview(absent).values():
        assert "Contact" not in page
    present = _load(tmp_path / "b",
                    'vendor: "Example Labs"\nvendor_contact: "support@example.com"\n')
    for page in _overview(present).values():
        assert ("  <p>Vendor: Example Labs</p>\n"
                "  <p>Contact: support@example.com</p>\n") in page
    # The contact is an overview line only: manifest and properties are the
    # same with and without it.
    assert _generate_outer_manifest(absent) == _generate_outer_manifest(present)
    assert (_generate_outer_resources_properties(absent)
            == _generate_outer_resources_properties(present))


def test_contact_without_vendor_keeps_default_vendor(tmp_path):
    p = _load(tmp_path, 'vendor_contact: "https://example.com"\n')
    assert p.vendor == DEFAULT_VENDOR
    for page in _overview(p).values():
        assert ("  <p>Vendor: VCF Content Factory</p>\n"
                "  <p>Contact: https://example.com</p>\n") in page


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------

_HARD_VENDORS = [
    "Smith & Sons",
    "<b>Bold</b> Ltd",
    'The "Quoted" Co',
    "It's Ours",
    "Back\\slash Inc",
    "Acmé GmbH",
    "株式会社サンプル",
    "Rocket \U0001F680 Labs",
    "  padded  ",
    "#1 = best: really!",
]


def _yaml_str(s: str) -> str:
    # A JSON string is a YAML double-quoted scalar.  Raw non-ASCII: PyYAML
    # does not pair "🚀"-style surrogate escapes.
    return json.dumps(s, ensure_ascii=False)


@pytest.mark.parametrize("vendor", _HARD_VENDORS)
def test_vendor_escaped_for_each_sink(tmp_path, vendor):
    p = _load(tmp_path, f"vendor: {_yaml_str(vendor)}\n"
                        f"vendor_contact: {_yaml_str(vendor + ' <x@y.z>')}\n")
    want = vendor.strip()
    assert p.vendor == want

    manifest = _generate_outer_manifest(p)
    assert manifest.isascii()
    assert json.loads(manifest)["vendor"] == want

    props = _generate_outer_resources_properties(p)
    assert props.isascii()
    assert _props_value(props, "VENDOR") == want

    for page in _overview(p).values():
        line = next(l for l in page.splitlines() if l.startswith("  <p>Vendor: "))
        body = line[len("  <p>Vendor: "):-len("</p>")]
        assert body.isascii()
        assert not re.search(r"[<>\"']|&(?!(amp|lt|gt|quot|#x?[0-9a-fA-F]+);)", body)
        assert html.unescape(body) == want
        contact = next(l for l in page.splitlines() if l.startswith("  <p>Contact: "))
        assert (html.unescape(contact[len("  <p>Contact: "):-len("</p>")])
                == (vendor + " <x@y.z>").strip())


def test_prop_value_escape_specifics():
    assert _prop_value_escape("VCF Content Factory") == "VCF Content Factory"
    assert _prop_value_escape("a\\b") == "a\\\\b"
    assert _prop_value_escape("é") == "\\u00e9"
    assert _prop_value_escape("\U0001F680") == "\\ud83d\\ude80"
    assert _prop_value_escape("a\nb\tc") == "a\\nb\\tc"


def _accepted_code_points():
    """Every code point _parse_one_line accepts (the regex is the rule)."""
    from vcfcf_managementpacks.sdk_project import _ONE_LINE_BAD_CHARS
    return [chr(c) for c in range(0x110000)
            if not _ONE_LINE_BAD_CHARS.match(chr(c))]


def test_every_accepted_character_encodes_in_all_three_sinks(tmp_path):
    # #336 review W1: nothing validation accepts may raise in a sink.
    from types import SimpleNamespace
    from vcfcf_managementpacks.sdk_builder import _html_text
    chars = _accepted_code_points()
    assert "\ud83d" not in chars and "‮" not in chars and "é" in chars
    for i in range(0, len(chars), 4096):
        s = "x" + "".join(chars[i:i + 4096]) + "x"
        manifest = json.dumps({"vendor": s}, indent=4)
        assert json.loads(manifest)["vendor"] == s
        props = _prop_value_escape(s)
        assert props.isascii()
        assert _props_value("VENDOR=" + props, "VENDOR") == s
        assert _html_text(s).isascii()
    # And the real generators, on one value mixing the hard cases.
    p = _load(tmp_path, f"vendor: {_yaml_str('A' + ''.join(chars[0x80:0x200]) + '😀')}\n")
    p.vendor_contact = p.vendor
    _generate_outer_manifest(p)
    _generate_outer_resources_properties(p)
    _build_overview_packed(p)
    _attribution_report(p)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", ["vendor", "vendor_contact"])
@pytest.mark.parametrize("value, message", [
    ('""', "present but blank"),
    ('"   "', "present but blank"),
    ("", "present but blank"),            # `key:` with no value is null
    ("42", "must be a string; got int"),
    ("true", "must be a string; got bool"),
    ("[a, b]", "must be a string; got list"),
    ("{name: x}", "must be a string; got dict"),
    ('"two\\nlines"', "U+000A at position 3"),
    ('"tab\\there"', "U+0009 at position 3"),
    ('"del\\x7f"', "U+007F"),
    # #336 review W1: an unpaired surrogate crashed the .properties sink.
    ('"Acme \\ud83d Labs"', "U+D83D at position 5"),
    ('"Acme \\ude80 Labs"', "U+DE80"),
    # #336 review N1: C1 controls, line/paragraph separators, bidi controls.
    ('"next\\x85line"', "U+0085"),
    ('"c1\\x9f"', "U+009F"),
    ('"line\\u2028sep"', "U+2028"),
    ('"para\\u2029sep"', "U+2029"),
    ('"Acme \\u202eLabs"', "U+202E"),
    ('"Acme \\u202aLabs"', "U+202A"),
    ('"rlm\\u200f"', "U+200F"),
    ('"lrm\\u200e"', "U+200E"),
    ('"alm\\u061c"', "U+061C"),
    ('"isolate\\u2066x\\u2069"', "U+2066"),
    ('"pdi\\u2069"', "U+2069"),
])
def test_one_line_keys_reject(tmp_path, key, value, message):
    with pytest.raises(SdkProjectError, match=re.escape(f"'{key}'")) as exc:
        _load(tmp_path, f"{key}: {value}\n")
    assert message in str(exc.value)
    if message.startswith("U+"):
        assert "must be one line of plain text" in str(exc.value)


def test_surrogate_vendor_fails_validate_sdk_not_build(tmp_path):
    # Before the fix validate-sdk passed and build-sdk raised UnicodeEncodeError.
    project_dir = _project_dir(tmp_path, 'vendor: "Acme \\ud83d Labs"\n')
    errors = validate_sdk_project(project_dir)
    assert any("'vendor' must be one line of plain text" in e and "U+D83D" in e
               for e in errors), errors


@pytest.mark.parametrize("ok", [
    "Acme Labs",        # no-break space: not a control
    "Ünïcödé Labs",
    "Rocket \U0001F680",     # astral character, written raw
    "שלום Ltd",  # right-to-left letters, no bidi control
])
def test_one_line_keys_accept_plain_unicode(tmp_path, ok):
    assert _load(tmp_path, f"vendor: {_yaml_str(ok)}\n").vendor == ok


def _eula_case(tmp_path: Path, case: str) -> str:
    """Set up one bad eula_file case; return the adapter.yaml line."""
    proj = tmp_path / "widget"
    proj.mkdir(exist_ok=True)
    if case == "missing":
        return "eula_file: NOPE.txt\n"
    if case == "directory":
        (proj / "legal").mkdir()
        return "eula_file: legal\n"
    if case == "empty":
        (proj / "EULA.txt").write_bytes(b"")
        return "eula_file: EULA.txt\n"
    if case == "whitespace":
        (proj / "EULA.txt").write_bytes(b"  \n\t\n")
        return "eula_file: EULA.txt\n"
    # #336 review W2: visually empty files.
    if case == "bom_only":
        (proj / "EULA.txt").write_bytes(b"\xef\xbb\xbf")
        return "eula_file: EULA.txt\n"
    if case == "bom_whitespace":
        (proj / "EULA.txt").write_bytes(b"\xef\xbb\xbf \r\n\t\n")
        return "eula_file: EULA.txt\n"
    if case == "nul_only":
        (proj / "EULA.txt").write_bytes(b"\x00\x00\x00")
        return "eula_file: EULA.txt\n"
    if case == "nul_in_text":
        (proj / "EULA.txt").write_bytes(b"Terms\x00 of use\n")
        return "eula_file: EULA.txt\n"
    if case == "no_printable":
        (proj / "EULA.txt").write_bytes(b"\x01\x02\n\x1b\xef\xbb\xbf\xe2\x80\x8b\n")
        return "eula_file: EULA.txt\n"
    if case == "not_utf8":
        (proj / "EULA.txt").write_bytes(b"Licen\xe7a \xff\xfe\n")
        return "eula_file: EULA.txt\n"
    if case == "dotdot":
        (tmp_path / "OUTSIDE.txt").write_text("outside\n", encoding="utf-8")
        return "eula_file: ../OUTSIDE.txt\n"
    if case == "absolute":
        (tmp_path / "OUTSIDE.txt").write_text("outside\n", encoding="utf-8")
        return f"eula_file: {_yaml_str(str(tmp_path / 'OUTSIDE.txt'))}\n"
    if case == "symlink_out":
        (tmp_path / "OUTSIDE.txt").write_text("outside\n", encoding="utf-8")
        (proj / "EULA.txt").symlink_to(tmp_path / "OUTSIDE.txt")
        return "eula_file: EULA.txt\n"
    if case == "blank":
        return 'eula_file: "  "\n'
    if case == "null":
        return "eula_file:\n"
    if case == "wrong_type":
        return "eula_file: [EULA.txt]\n"
    raise AssertionError(case)


@pytest.mark.parametrize("case, message", [
    ("missing", "not found"),
    ("directory", "is not a regular file"),
    ("empty", "is empty"),
    ("whitespace", "is empty"),
    ("bom_only", "is empty"),
    ("bom_whitespace", "is empty"),
    ("nul_only", "contains NUL bytes"),
    ("nul_in_text", "contains NUL bytes"),
    ("no_printable", "has no printable text"),
    ("not_utf8", "is not UTF-8 text"),
    ("dotdot", "outside the adapter project"),
    ("absolute", "outside the adapter project"),
    ("symlink_out", "outside the adapter project"),
    ("blank", "present but blank"),
    ("null", "present but blank"),
    ("wrong_type", "must be a path string"),
])
def test_eula_file_rejects(tmp_path, case, message):
    line = _eula_case(tmp_path, case)
    with pytest.raises(SdkProjectError, match="'eula_file'") as exc:
        _load(tmp_path, line)
    assert message in str(exc.value)


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0,
                    reason="needs a non-root POSIX user for chmod 000")
def test_eula_file_unreadable(tmp_path):
    proj = tmp_path / "widget"
    proj.mkdir()
    f = proj / "EULA.txt"
    f.write_text("terms\n", encoding="utf-8")
    f.chmod(0)
    try:
        with pytest.raises(SdkProjectError, match="cannot be read"):
            _load(tmp_path, "eula_file: EULA.txt\n")
    finally:
        f.chmod(0o644)


def test_validate_sdk_reports_attribution_errors(tmp_path):
    project_dir = _project_dir(tmp_path, 'vendor: ""\n')
    errors = validate_sdk_project(project_dir)
    assert any("adapter.yaml validation error" in e and "'vendor' is present but blank" in e
               for e in errors), errors


# ---------------------------------------------------------------------------
# EULA override and the framework notice
# ---------------------------------------------------------------------------

_EULA = "Example Labs End User Licence\r\nCopyright Exämple.\r\n".encode("utf-8")


def _eula_project(tmp_path: Path, rel: str = "legal/EULA.txt"):
    proj = _project_dir(tmp_path, f"eula_file: {rel}\n")
    (proj / rel).parent.mkdir(parents=True, exist_ok=True)
    (proj / rel).write_bytes(_EULA)
    return load_sdk_project(proj / "adapter.yaml")


def test_eula_override_written_to_both_copies(tmp_path):
    p = _eula_project(tmp_path)
    assert p.eula_file == "legal/EULA.txt"
    assert p.eula_path == (p.source_path.parent / "legal/EULA.txt").resolve()
    inner = _adapters_zip(p, tmp_path)
    outer = _outer_pak(p, tmp_path)
    assert inner.read("eula.txt") == _EULA   # bytes as written, CRLF kept
    assert outer.read("eula.txt") == _EULA


def test_notice_present_only_when_overridden_and_equals_license(tmp_path):
    p = _eula_project(tmp_path)
    inner = _adapters_zip(p, tmp_path)
    assert inner.read(_NOTICE_ENTRY) == _read_license().encode("utf-8")
    assert inner.read(_NOTICE_ENTRY) == (
        Path(sdk_builder._LICENSE_PATH).read_bytes())
    # Beside the jar it covers.
    assert "vcfcf_widget/lib/vcfcf-adapter-base.jar" in inner.namelist()


def test_eula_override_adds_only_the_notice(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()  # _adapters_zip writes its jars here
    default = _adapters_zip(_load(tmp_path / "a"), tmp_path / "a")
    override = _adapters_zip(_eula_project(tmp_path / "b"), tmp_path / "b")
    assert set(override.namelist()) - set(default.namelist()) == {_NOTICE_ENTRY}
    assert set(default.namelist()) - set(override.namelist()) == set()
    for name in default.namelist():
        if name != "eula.txt":
            assert default.read(name) == override.read(name), name


def test_eula_leading_bom_is_dropped_from_shipped_bytes(tmp_path):
    proj = _project_dir(tmp_path, "eula_file: EULA.txt\n")
    (proj / "EULA.txt").write_bytes(b"\xef\xbb\xbf" + _EULA)
    p = load_sdk_project(proj / "adapter.yaml")
    assert p.eula_bytes == _EULA
    inner = _adapters_zip(p, tmp_path)
    outer = _outer_pak(p, tmp_path)
    assert inner.read("eula.txt") == outer.read("eula.txt") == _EULA


@pytest.mark.parametrize("change", ["rewrite", "truncate", "symlink_out", "delete"])
def test_eula_change_after_load_does_not_change_what_ships(tmp_path, change):
    # #336 review W3: the bytes validated at load are the bytes that ship.
    p = _eula_project(tmp_path)
    f = p.source_path.parent / "legal" / "EULA.txt"
    if change == "rewrite":
        f.write_bytes(b"something else entirely\n")
    elif change == "truncate":
        f.write_bytes(b"")
    elif change == "symlink_out":
        (tmp_path / "OUTSIDE.txt").write_bytes(b"outside bytes\n")
        f.unlink()
        f.symlink_to(tmp_path / "OUTSIDE.txt")
    else:
        f.unlink()
    inner = _adapters_zip(p, tmp_path)
    outer = _outer_pak(p, tmp_path)
    assert inner.read("eula.txt") == _EULA
    assert outer.read("eula.txt") == _EULA
    assert inner.read("eula.txt") == outer.read("eula.txt")


def test_notice_fails_build_when_license_missing(tmp_path, monkeypatch):
    # An empty MIT notice is never shipped (#336 review N3, factory side).
    p = _eula_project(tmp_path)
    monkeypatch.setattr(sdk_builder, "_LICENSE_PATH", tmp_path / "no-LICENSE")
    with pytest.raises(sdk_builder.SdkBuildError, match="LICENSE not found"):
        _adapters_zip(p, tmp_path)


def test_buildkit_assembly_fails_without_license(tmp_path, monkeypatch):
    # #336 review N3: no placeholder LICENSE in a kit.
    from vcfcf_managementpacks import buildkit
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    monkeypatch.setattr(buildkit, "_REPO_ROOT", fake_root)
    ref = tmp_path / "ref.pak"
    ref.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    with pytest.raises(FileNotFoundError, match="factory LICENSE not found"):
        buildkit.assemble_buildkit(tmp_path / "dist", version="9.9.9",
                                   reference_pak=ref, verbose=False)
    assert not list((tmp_path / "dist").glob("*.tgz"))


def test_eula_file_inside_via_symlink_is_accepted(tmp_path):
    proj = _project_dir(tmp_path, "eula_file: EULA.txt\n")
    (proj / "legal").mkdir()
    (proj / "legal" / "real.txt").write_bytes(_EULA)
    (proj / "EULA.txt").symlink_to(proj / "legal" / "real.txt")
    p = load_sdk_project(proj / "adapter.yaml")
    assert p.eula_path == (proj / "legal" / "real.txt").resolve()


# ---------------------------------------------------------------------------
# Build output
# ---------------------------------------------------------------------------

def test_report_default_says_how_to_set():
    from types import SimpleNamespace
    p = SimpleNamespace(vendor=DEFAULT_VENDOR, vendor_declared=False,
                        vendor_contact="", eula_file="", eula_path=None,
                        eula_bytes=None)
    lines = _attribution_report(p)
    assert lines == [
        "  vendor: VCF Content Factory (default; set adapter.yaml vendor: and "
        "vendor_contact: to name the pak's author)",
        "  eula: factory MIT LICENSE (default)",
    ]
    assert not any("WARNING" in l or "ERROR" in l for l in lines)


def test_report_declared(tmp_path):
    p = _eula_project(tmp_path)
    p.vendor, p.vendor_declared, p.vendor_contact = "Example Labs", True, "a@b.c"
    assert _attribution_report(p) == [
        "  vendor: Example Labs (adapter.yaml vendor)",
        "  vendor contact: a@b.c",
        "  eula: legal/EULA.txt (adapter.yaml eula_file); factory MIT LICENSE "
        f"ships as lib/{FRAMEWORK_NOTICE_NAME}",
    ]


# ---------------------------------------------------------------------------
# Assembled buildkit: the kit reads its own LICENSE copy for both
# ---------------------------------------------------------------------------

_KIT_SCRIPT = textwrap.dedent("""\
    import io, sys, zipfile
    from pathlib import Path
    from sdk_buildkit import sdk_builder
    from sdk_buildkit.sdk_project import load_sdk_project

    tmp = Path(sys.argv[1])
    print("LICENSE_PATH:" + str(sdk_builder._LICENSE_PATH))
    for name in ("default", "override"):
        proj = tmp / name
        p = load_sdk_project(proj / "adapter.yaml")
        jar = tmp / (name + ".jar")
        jar.write_bytes(b"PK\\x05\\x06" + b"\\x00" * 18)
        data = sdk_builder._assemble_adapters_zip(p, proj, jar, [])
        z = zipfile.ZipFile(io.BytesIO(data))
        out = tmp / (name + "-out")
        out.mkdir()
        outer = zipfile.ZipFile(sdk_builder._write_outer_pak(p, b"", out, proj))
        (tmp / (name + ".eula.inner")).write_bytes(z.read("eula.txt"))
        (tmp / (name + ".eula.outer")).write_bytes(outer.read("eula.txt"))
        notice = "vcfcf_widget/lib/" + sdk_builder.FRAMEWORK_NOTICE_NAME
        if notice in z.namelist():
            (tmp / (name + ".notice")).write_bytes(z.read(notice))
    print("OK")
""")


def test_assembled_kit_reads_kit_license(tmp_path):
    from vcfcf_managementpacks.buildkit import assemble_buildkit

    ref = tmp_path / "ref.pak"
    ref.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    tarball = assemble_buildkit(tmp_path / "dist", version="9.9.9",
                                reference_pak=ref, verbose=False)
    kit_root = tmp_path / "kit"
    with tarfile.open(tarball) as tf:
        tf.extractall(kit_root)
    kit_license = kit_root / "sdk_buildkit" / "LICENSE"
    # A sentinel licence proves the kit reads its own copy, not the repo's.
    kit_license.write_text("KIT LICENSE SENTINEL\n", encoding="utf-8")

    work = tmp_path / "work"
    work.mkdir()
    for name, extra in (("default", ""), ("override", "eula_file: EULA.txt\n")):
        proj = work / name
        proj.mkdir()
        (proj / "adapter.yaml").write_text(_BASE_YAML + extra, encoding="utf-8")
        (proj / "describe.xml").write_text(_DESCRIBE, encoding="utf-8")
    (work / "override" / "EULA.txt").write_bytes(_EULA)

    repo_root = str(Path(__file__).resolve().parents[2])
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(kit_root)] + [e for e in env.get("PYTHONPATH", "").split(os.pathsep)
                           if e and Path(e).resolve() != Path(repo_root)
                           and Path(e).resolve() != Path(repo_root) / "src"])
    script = tmp_path / "kit_script.py"
    script.write_text(_KIT_SCRIPT, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), str(work)],
                            capture_output=True, text=True, env=env,
                            cwd=tempfile.gettempdir(), timeout=100)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"LICENSE_PATH:{kit_license}" in result.stdout

    sentinel = b"KIT LICENSE SENTINEL\n"
    assert (work / "default.eula.inner").read_bytes() == sentinel
    assert (work / "default.eula.outer").read_bytes() == sentinel
    assert not (work / "default.notice").exists()
    assert (work / "override.eula.inner").read_bytes() == _EULA
    assert (work / "override.eula.outer").read_bytes() == _EULA
    assert (work / "override.notice").read_bytes() == sentinel
