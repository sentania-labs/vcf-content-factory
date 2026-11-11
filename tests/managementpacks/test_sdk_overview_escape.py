"""Overview page name and description are HTML-escaped (factory #338).

build-sdk interpolated adapter.yaml ``name`` and ``description`` into both
overview pages (``overview.packed``: light and dark ``overview.html``) raw,
so ``R&D`` left a bare ampersand and ``<vmnic>`` vanished as a tag.  They
now go through the same ``_html_text`` as vendor and vendor_contact (#336):
HTML-escaped, non-ASCII as character references.  The manifest JSON and the
localization ``.properties`` sinks already encoded correctly and must not
gain HTML escaping.
"""
from __future__ import annotations

import html
import io
import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import pytest

from vcfcf_managementpacks.sdk_builder import (
    _build_overview_packed,
    _generate_outer_manifest,
    _generate_outer_resources_properties,
)
from vcfcf_managementpacks.sdk_project import load_sdk_project

_DESCRIBE = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind key="vcfcf_widget" nameKey="1" version="1"
             xmlns="http://schemas.vmware.com/vcops/schema">
  <ResourceKinds>
    <ResourceKind key="widget_world" nameKey="2" type="7"/>
  </ResourceKinds>
</AdapterKind>
"""


def _project(tmp_path: Path, name_yaml: str, description_yaml: str):
    project_dir = tmp_path / "widget"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "adapter.yaml").write_text(
        f"name: {name_yaml}\n"
        'version: "1.0.0"\n'
        "build_number: 3\n"
        'adapter_kind: "vcfcf_widget"\n'
        "tier: 2\n"
        f"description: {description_yaml}\n"
        'entry_class: "com.vcfcf.adapters.widget.WidgetAdapter"\n',
        encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE, encoding="utf-8")
    return load_sdk_project(project_dir / "adapter.yaml")


def _yaml_str(s: str) -> str:
    # A JSON string is a YAML double-quoted scalar.
    return json.dumps(s, ensure_ascii=False)


def _pages(project) -> dict:
    z = zipfile.ZipFile(io.BytesIO(_build_overview_packed(project)))
    assert z.namelist() == ["overview/", "overview/light/", "overview/dark/",
                            "overview/light/overview.html",
                            "overview/dark/overview.html"]
    return {t: z.read(f"overview/{t}/overview.html") for t in ("light", "dark")}


class _Page(HTMLParser):
    """Records the tag sequence and the decoded text of each text element."""

    _VOID = {"meta"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list = []
        self.stack: list = []
        self.text: dict = {"title": [], "h1": [], "p": []}
        self._buf: list = []
        self.comments: list = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag not in self._VOID:
            self.stack.append(tag)
            self._buf = []

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, (tag, self.stack)
        self.stack.pop()
        if tag in self.text:
            self.text[tag].append("".join(self._buf))

    def handle_data(self, data):
        self._buf.append(data)

    def handle_comment(self, data):
        self.comments.append(data)


def _parse(page: bytes) -> _Page:
    parser = _Page()
    parser.feed(page.decode("utf-8"))
    parser.close()
    assert parser.stack == []
    return parser


_UNESCAPED = re.compile(r"[<>\"']|&(?!(amp|lt|gt|quot|#x?[0-9a-fA-F]+);)")

_TAGS = ["html", "head", "meta", "title", "style", "body", "h1", "p", "p", "p"]


# ---------------------------------------------------------------------------
# Hostile and non-ASCII text reads back as itself
# ---------------------------------------------------------------------------

_HARD = [
    "R&D Storage",
    "Latency < 5 ms",
    "Throughput > 1 GB/s",
    'The "quoted" one',
    "It's ours",
    "<script>alert(1)</script>",
    "before <!-- after",
    "already &amp; escaped",
    "Acmé – naïve — 株式会社 🚀",
    "vmnic->port <vmnic> & \"both\" 'kinds'",
]


@pytest.mark.parametrize("text", _HARD)
def test_name_and_description_read_back(tmp_path, text):
    p = _project(tmp_path, _yaml_str("N " + text), _yaml_str("D " + text))
    for theme, page in _pages(p).items():
        assert page.isascii(), theme
        parsed = _parse(page)
        # Structure is the template's, whatever the text holds: no tag,
        # script or comment came from adapter.yaml.
        assert parsed.tags == _TAGS, theme
        assert parsed.comments == []
        assert parsed.text["title"] == ["N " + text]
        assert parsed.text["h1"] == ["N " + text]
        assert parsed.text["p"][0] == "Version 1.0.0.3"
        assert parsed.text["p"][1] == "D " + text
        assert parsed.text["p"][2] == "Vendor: VCF Content Factory"
        # A lenient parser reads a bare "R&D" or "< 5" back as text too, so
        # also hold the raw bytes to strict escaping, as #336 does for vendor.
        lines = page.decode("ascii").splitlines()
        for line, (open_, close, want) in zip(
                (lines[4], lines[12], lines[14]),
                (("  <title>", "</title>", "N " + text),
                 ("  <h1>", "</h1>", "N " + text),
                 ("  <p>", "</p>", "D " + text))):
            assert line.startswith(open_) and line.endswith(close), line
            body = line[len(open_):-len(close)]
            assert not _UNESCAPED.search(body), body
            assert html.unescape(body) == want


def test_pre_escaped_entity_is_text(tmp_path):
    p = _project(tmp_path, '"A &amp; B"', '"C &lt;x&gt; D"')
    for page in _pages(p).values():
        assert b"<title>A &amp;amp; B</title>" in page
        assert b"<h1>A &amp;amp; B</h1>" in page
        assert b"<p>C &amp;lt;x&amp;gt; D</p>" in page


def test_specific_encodings(tmp_path):
    p = _project(tmp_path, _yaml_str("<b>&\"'"), _yaml_str("é 🚀"))
    for page in _pages(p).values():
        assert b"<h1>&lt;b&gt;&amp;&quot;&#x27;</h1>" in page
        assert b"<p>&#233; &#128640;</p>" in page


def test_light_and_dark_escape_alike(tmp_path):
    p = _project(tmp_path, _yaml_str(_HARD[-1]), _yaml_str(_HARD[-2]))
    pages = _pages(p)
    light = _parse(pages["light"]).text
    dark = _parse(pages["dark"]).text
    assert light == dark


# ---------------------------------------------------------------------------
# Plain ASCII: byte-for-byte what build-sdk wrote before #338
# ---------------------------------------------------------------------------

def _page(theme: str, color: str, background: str, p_color: str,
          description: str) -> bytes:
    return (
        "<!DOCTYPE html>\n"
        f"<html lang=\"en\" class=\"{theme}\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>VCF Content Factory Widget (v2), 100% plain</title>\n"
        "  <style>\n"
        f"    body {{ font-family: sans-serif; margin: 2em; color: {color}; background: {background}; }}\n"
        "    h1 { font-size: 1.4em; }\n"
        f"    p  {{ font-size: 0.95em; color: {p_color}; }}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>VCF Content Factory Widget (v2), 100% plain</h1>\n"
        "  <p>Version 1.0.0.3</p>\n"
        f"  <p>{description}</p>\n"
        "  <p>Vendor: VCF Content Factory</p>\n"
        "</body>\n"
        "</html>\n"
    ).encode("ascii")


# Captured from origin/main (buildkit 1.0.26) before the change.
_PLAIN_NAME = '"VCF Content Factory Widget (v2), 100% plain"'


def test_plain_ascii_single_line_unchanged(tmp_path):
    desc = "Monitors widgets: pools, volumes; #1 = best! (see docs/ref.md) [a-b] {c} ~ * + @ $ ? / \\ |."
    p = _project(tmp_path, _PLAIN_NAME, _yaml_str(desc))
    pages = _pages(p)
    assert pages["light"] == _page("light", "#222", "#fff", "#555", desc)
    assert pages["dark"] == _page("dark", "#eee", "#1a1a1a", "#aaa", desc)


def test_plain_ascii_folded_description_layout_unchanged(tmp_path):
    folded = ">\n  Line one of a folded\n  description.\n\n  Second paragraph.\n"
    p = _project(tmp_path, _PLAIN_NAME, folded)
    want = "Line one of a folded description.\nSecond paragraph."
    pages = _pages(p)
    assert pages["light"] == _page("light", "#222", "#fff", "#555", want)
    assert pages["dark"] == _page("dark", "#eee", "#1a1a1a", "#aaa", want)


def test_plain_ascii_literal_description_layout_unchanged(tmp_path):
    literal = "|\n  First line\n    indented line\n  last line\n"
    p = _project(tmp_path, _PLAIN_NAME, literal)
    want = "First line\n  indented line\nlast line"
    pages = _pages(p)
    assert pages["light"] == _page("light", "#222", "#fff", "#555", want)
    assert pages["dark"] == _page("dark", "#eee", "#1a1a1a", "#aaa", want)


def test_multiline_description_with_specials_keeps_line_breaks(tmp_path):
    literal = "|\n  a & b\n  <c>\n"
    p = _project(tmp_path, _PLAIN_NAME, literal)
    for page in _pages(p).values():
        assert b"  <p>a &amp; b\n&lt;c&gt;</p>\n" in page


# ---------------------------------------------------------------------------
# Manifest and properties: no HTML escaping, ever
# ---------------------------------------------------------------------------

def _props_line(text: str, key: str) -> str:
    return next(l for l in text.splitlines() if l.startswith(key + "="))[len(key) + 1:]


@pytest.mark.parametrize("text", _HARD)
def test_manifest_and_properties_are_not_html_escaped(tmp_path, text):
    name, desc = "N " + text, "D " + text
    p = _project(tmp_path, _yaml_str(name), _yaml_str(desc))

    manifest = _generate_outer_manifest(p)
    loaded = json.loads(manifest)
    assert (loaded["name"], loaded["display_name"], loaded["description"]) == (
        name, name, desc)
    assert manifest == json.dumps(json.loads(manifest), indent=4)

    props = _generate_outer_resources_properties(p)
    # Neither value holds a backslash or a line break, so the properties
    # sink writes it verbatim: an HTML entity here would be a double escape.
    assert _props_line(props, "DISPLAY_NAME") == name
    assert _props_line(props, "DESCRIPTION") == desc


def test_pre_escaped_entity_passes_through_manifest_and_properties(tmp_path):
    p = _project(tmp_path, '"A &amp; B"', '"C &lt;x&gt; D"')
    loaded = json.loads(_generate_outer_manifest(p))
    assert loaded["name"] == "A &amp; B"
    assert loaded["description"] == "C &lt;x&gt; D"
    props = _generate_outer_resources_properties(p)
    assert _props_line(props, "DISPLAY_NAME") == "A &amp; B"
    assert _props_line(props, "DESCRIPTION") == "C &lt;x&gt; D"


# ---------------------------------------------------------------------------
# Loader: name and description carry the #336 character rules (#338 review W1)
# ---------------------------------------------------------------------------

from vcfcf_managementpacks.sdk_project import SdkProjectError  # noqa: E402

_PLAIN_DESC = '"Widget pak."'


@pytest.mark.parametrize("key", ["name", "description"])
@pytest.mark.parametrize("yaml_value, code_point", [
    ('"Pools\\Nvolumes"', "U+0085"),     # C1 NEL: &#133; would read as an ellipsis
    ('"A\\x80B"', "U+0080"),             # C1: &#128; would read as a euro sign
    ('"a\\ud800b"', "U+D800"),           # lone surrogate: no sink can encode it
    ('"evil\\u202Etxt"', "U+202E"),      # bidi override
    ('"nul\\0here"', "U+0000"),          # NUL
    ('"a\\u2028b"', "U+2028"),           # line separator
])
def test_bad_characters_rejected_at_load(tmp_path, key, yaml_value, code_point):
    name, desc = (yaml_value, _PLAIN_DESC) if key == "name" else (_PLAIN_NAME, yaml_value)
    with pytest.raises(SdkProjectError) as exc:
        _project(tmp_path, name, desc)
    msg = str(exc.value)
    assert f"'{key}' must be" in msg
    assert code_point in msg


def test_name_with_newline_rejected(tmp_path):
    with pytest.raises(SdkProjectError, match=r"'name' must be one line.*U\+000A"):
        _project(tmp_path, '"Line one\\nLine two"', _PLAIN_DESC)


def test_description_with_lone_cr_rejected(tmp_path):
    with pytest.raises(SdkProjectError, match=r"'description' must be.*U\+000D"):
        _project(tmp_path, _PLAIN_NAME, '"a\\rb"')


def test_blank_name_rejected(tmp_path):
    with pytest.raises(SdkProjectError, match="'name' is blank"):
        _project(tmp_path, '"   "', _PLAIN_DESC)


def test_name_is_stripped_in_every_sink(tmp_path):
    p = _project(tmp_path, '"  Padded Name \\t"', _PLAIN_DESC)
    assert p.name == "Padded Name"
    loaded = json.loads(_generate_outer_manifest(p))
    assert loaded["name"] == loaded["display_name"] == "Padded Name"
    assert _props_line(_generate_outer_resources_properties(p), "DISPLAY_NAME") == "Padded Name"
    for page in _pages(p).values():
        assert b"  <title>Padded Name</title>\n" in page
        assert b"  <h1>Padded Name</h1>\n" in page


def test_tab_and_multiline_description_accepted(tmp_path):
    p = _project(tmp_path, _PLAIN_NAME, "|\n  col\tvalue\n\n  next & last\n")
    assert p.description == "col\tvalue\n\nnext & last"
    for page in _pages(p).values():
        assert b"  <p>col\tvalue\n\nnext &amp; last</p>\n" in page
        assert _parse(page).text["p"][1] == p.description


def test_crlf_description_accepted_and_written_verbatim(tmp_path):
    p = _project(tmp_path, _PLAIN_NAME, '"first\\r\\nsecond"')
    assert p.description == "first\r\nsecond"
    for page in _pages(p).values():
        # Written as is.  A browser's input stream turns the CRLF into one
        # line break, as it did before #338; the <p> layout is unchanged.
        assert b"  <p>first\r\nsecond</p>\n" in page
        assert _parse(page).text["p"][1] == "first\r\nsecond"
    assert json.loads(_generate_outer_manifest(p))["description"] == "first\r\nsecond"
    assert _props_line(_generate_outer_resources_properties(p),
                       "DESCRIPTION") == "first\\r\\nsecond"


def test_every_accepted_character_builds_and_reads_back(tmp_path):
    # #338 review W1 and its surrogate follow-up: nothing the loader accepts
    # for name or description may raise in a sink, and the overview page
    # must decode to the value.  Noncharacters (U+FDD0-U+FDEF, U+xFFFE,
    # U+xFFFF) are the exception in this check only: the WHATWG HTML parser
    # decodes their references to themselves, but CPython's html.unescape
    # follows an older table and drops them, so they are checked as emitted
    # references instead.
    from vcfcf_managementpacks.sdk_project import (
        _MULTI_LINE_BAD_CHARS, _ONE_LINE_BAD_CHARS)
    from vcfcf_managementpacks.sdk_builder import _html_text
    p = _project(tmp_path, _PLAIN_NAME, _PLAIN_DESC)
    for pattern, field_name in ((_ONE_LINE_BAD_CHARS, "name"),
                                (_MULTI_LINE_BAD_CHARS, "description")):
        chars = [chr(c) for c in range(0x110000) if not pattern.match(chr(c))]
        assert "\x85" not in chars and "\ud800" not in chars and "‮" not in chars
        assert ("\n" in chars) == (field_name == "description")
        for i in range(0, len(chars), 4096):
            s = "x" + "".join(chars[i:i + 4096]) + "x"
            escaped = _html_text(s)
            assert escaped.isascii()
            assert html.unescape(escaped) == "".join(
                c for c in s if not _is_noncharacter(c))
            setattr(p, field_name, s)
            _generate_outer_manifest(p).encode("utf-8")
            _generate_outer_resources_properties(p).encode("utf-8")
            _build_overview_packed(p)
        setattr(p, field_name, _PLAIN_NAME.strip('"') if field_name == "name" else "Widget pak.")


def _is_noncharacter(c: str) -> bool:
    cp = ord(c)
    return 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE


def test_noncharacters_are_emitted_as_references():
    from vcfcf_managementpacks.sdk_builder import _html_text
    assert _html_text("a\ufdd0\uffff\U0010fffeb") == "a&#64976;&#65535;&#1114110;b"
