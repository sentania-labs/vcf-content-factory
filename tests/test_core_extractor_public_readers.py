"""vcfcf_core.extractor exports public names for the export-zip readers (#165).

The migrator imported three underscore-private functions from
vcfcf_core.extractor.extractor. They now have public names on the package,
and the underscore names stay as aliases (the same objects) for one release.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PUBLIC = (
    "content_xml_from_export_zip",
    "dashboards_from_export_zip",
    "supermetrics_from_export_zip",
)


def test_public_names_import_from_the_package():
    from vcfcf_core.extractor import (  # noqa: F401
        content_xml_from_export_zip,
        dashboards_from_export_zip,
        supermetrics_from_export_zip,
    )
    import vcfcf_core.extractor as pkg

    assert sorted(pkg.__all__) == sorted(PUBLIC)
    for name in PUBLIC:
        assert callable(getattr(pkg, name))


def test_underscore_aliases_are_the_same_objects():
    import vcfcf_core.extractor as pkg
    import vcfcf_core.extractor.extractor as mod

    for name in PUBLIC:
        assert getattr(mod, "_" + name) is getattr(mod, name) is getattr(pkg, name)


def test_factory_reexport_still_resolves():
    import vcfcf_core.extractor as pkg
    import vcfcf_extractor.extractor as fac

    assert fac._dashboards_from_export_zip is pkg.dashboards_from_export_zip
    assert fac._supermetrics_from_export_zip is pkg.supermetrics_from_export_zip


def test_public_reader_parses_a_content_xml_zip():
    from vcfcf_core.extractor import content_xml_from_export_zip

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content.xml", "<Content><ViewDef id='x'/></Content>")
    assert content_xml_from_export_zip(buf.getvalue()).startswith(b"<Content>")
    assert content_xml_from_export_zip(b"not a zip") is None
