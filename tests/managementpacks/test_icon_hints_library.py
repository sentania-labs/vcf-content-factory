"""Icon hints content_library, library_item, vm_template (vCommunity design T4).

The icon library is ``src/vcfcf_managementpacks/templates/icons/<hint>.svg``;
a hint is the file stem. Tier 2 paks name the file in ``icons/icons.yaml``
(``_pack_icons`` resolves it against the pak's own icons/ first, then the
library); Tier 1 MPB YAML names the stem in ``object_types[].icon``. Both
must find the new files, and each must follow the library's house style
(``knowledge/context/mpb/mp_icon_library.md``): 400x400 viewBox, the two
palette colours, plain shapes only.
"""
from __future__ import annotations

import io
import re
import types
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks import builder, sdk_builder
from vcfcf_managementpacks.loader import _parse_icon_hint

ICONS = Path(sdk_builder.__file__).resolve().parent / "templates" / "icons"
NEW_HINTS = ("content_library", "library_item", "vm_template")
SVG_NS = "{http://www.w3.org/2000/svg}"
PALETTE = {"#0098c7", "#005c8a"}
ALLOWED_TAGS = {"svg", "rect", "line", "path", "circle", "ellipse", "polyline", "polygon", "g"}


@pytest.mark.parametrize("hint", NEW_HINTS)
def test_icon_file_follows_house_style(hint):
    path = ICONS / f"{hint}.svg"
    assert path.is_file(), f"{path} missing"
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.tag == f"{SVG_NS}svg"
    assert root.get("viewBox") == "0 0 400 400"
    tags = {el.tag.replace(SVG_NS, "") for el in root.iter()}
    assert tags <= ALLOWED_TAGS, f"unexpected elements {tags - ALLOWED_TAGS}"
    colours = set(re.findall(r"#[0-9a-fA-F]{6}", text))
    assert colours and colours <= PALETTE, f"off-palette colours {colours - PALETTE}"
    assert "href" not in text and "<script" not in text and "<text" not in text
    # Not a copy of an existing library icon.
    others = {p.read_bytes() for p in ICONS.glob("*.svg") if p.stem != hint}
    assert path.read_bytes() not in others


@pytest.mark.parametrize("hint", NEW_HINTS)
def test_tier1_hint_resolves(hint):
    assert _parse_icon_hint(hint) == hint
    assert _parse_icon_hint(f"{hint}.svg") == hint
    data = builder._icon_bytes_for(hint)
    assert data == (ICONS / f"{hint}.svg").read_bytes()
    assert data != (ICONS / "default.svg").read_bytes()


_DESCRIBE = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind key="vcfcf_lib" nameKey="1" version="1"
             xmlns="http://schemas.vmware.com/vcops/schema">
  <ResourceKinds>
    <ResourceKind key="vcfcf_lib" nameKey="2" type="7"/>
    <ResourceKind key="Content Library" nameKey="3"/>
    <ResourceKind key="Library Item" nameKey="4"/>
    <ResourceKind key="VM Template" nameKey="5"/>
  </ResourceKinds>
</AdapterKind>
"""

_ICONS_YAML = """adapter_kind_icon: adapter_instance.svg
resource_kinds:
  vcfcf_lib: adapter_instance.svg
  Content Library: content_library.svg
  Library Item: library_item.svg
  VM Template: vm_template.svg
"""


def test_tier2_pack_icons_uses_new_hints(tmp_path):
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "icons.yaml").write_text(_ICONS_YAML, encoding="utf-8")
    describe = tmp_path / "describe.xml"
    describe.write_text(_DESCRIBE, encoding="utf-8")
    project = types.SimpleNamespace(adapter_dir_name="vcfcf_lib_adapter3",
                                    adapter_kind="vcfcf_lib")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        sdk_builder._pack_icons(zf, project, tmp_path, describe)
    with zipfile.ZipFile(buf) as zf:
        base = "vcfcf_lib_adapter3/conf/images/ResourceKind/"
        for kind, hint in (("Content Library", "content_library"),
                           ("Library Item", "library_item"),
                           ("VM Template", "vm_template")):
            assert zf.read(f"{base}{kind}.svg") == (ICONS / f"{hint}.svg").read_bytes()


def test_icon_library_doc_lists_new_hints():
    doc = (Path(__file__).resolve().parents[2] / "knowledge" / "context" / "mpb"
           / "mp_icon_library.md").read_text(encoding="utf-8")
    for hint in NEW_HINTS:
        assert f"| `{hint}` |" in doc
