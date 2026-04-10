"""Render ReportDef models to the XML wire format VCF Operations expects.

Report definitions are packaged as ``reports.zip`` containing a single
``content.xml``.  The outer content-zip structure is the same as the
dashboards import path (marker file + configuration.json).

Wire format reference: context/reports_api_surface.md

The minimal shape emitted here was established from the reports_api_surface.md
documentation and confirmed against the reference bundles at
references/brockpeterson_operations_reports/ and
references/AriaOperationsContent/Cost Reporting/.
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from xml.sax.saxutils import escape

from .loader import ReportDef, Section, _STATIC_CONTENT_KEYS


def _render_section(sec: Section) -> str:
    """Render a single Section element."""
    if sec.type in ("CoverPage", "TableOfContents"):
        content_key = _STATIC_CONTENT_KEYS[sec.type]
        return (
            "<Section>"
            f"<ContentType>{escape(sec.type)}</ContentType>"
            f"<ContentKey>{escape(content_key)}</ContentKey>"
            "</Section>"
        )

    if sec.type == "View":
        colorize_str = "true" if sec.colorize else "false"
        return (
            "<Section>"
            f"<ContentType>View</ContentType>"
            f"<ContentKey>{escape(sec.view_id)}</ContentKey>"
            f"<ContentOrientation>{escape(sec.orientation)}</ContentOrientation>"
            "<ContentFormatting>"
            f"<ColorizeListView>{colorize_str}</ColorizeListView>"
            "</ContentFormatting>"
            "</Section>"
        )

    if sec.type == "Dashboard":
        return (
            "<Section>"
            f"<ContentType>Dashboard</ContentType>"
            f"<ContentKey>{escape(sec.dashboard_id)}</ContentKey>"
            f"<ContentOrientation>{escape(sec.orientation)}</ContentOrientation>"
            "</Section>"
        )

    # Should not reach here after validation; emit a comment for debugging.
    return f"<!-- unsupported section type: {escape(sec.type)} -->"


def render_report_xml(reports: list[ReportDef]) -> str:
    """Render one or more ReportDefs into the content.xml string."""
    fragments: list[str] = []
    for rd in reports:
        sections_xml = "".join(_render_section(s) for s in rd.sections)

        subject_types_xml = "".join(
            f'<SubjectType adapterKind="{escape(st.adapter_kind)}" '
            f'resourceKind="{escape(st.resource_kind)}" '
            f'type="{escape(st.type)}"'
            + (f' filter="{escape(st.filter)}"' if st.filter else "")
            + "/>"
            for st in rd.subject_types
        )

        output_formats_xml = "".join(
            f"<OutputFormat>{escape(fmt)}</OutputFormat>"
            for fmt in rd.settings.output_formats
        )
        show_footer = "true" if rd.settings.show_page_footer else "false"

        fragments.append(
            f'<ReportDef id="{escape(rd.id)}">'
            "<isTenant>false</isTenant>"
            f"<Title>{escape(rd.name)}</Title>"
            f"<Description>{escape(rd.description)}</Description>"
            + subject_types_xml
            + f"<Sections>{sections_xml}</Sections>"
            + "<Settings>"
            + f"<ShowPageFooter>{show_footer}</ShowPageFooter>"
            + output_formats_xml
            + "</Settings>"
            + "</ReportDef>"
        )

    reports_xml = "".join(fragments)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<Content><Reports>{reports_xml}</Reports></Content>"
    )


def _build_reports_inner_zip(xml_text: str) -> bytes:
    """Package content.xml into the inner reports.zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_text)
    return buf.getvalue()


def _default_marker_filename() -> str:
    """Fallback marker for offline package runs; sync path replaces this."""
    return f"{time.time_ns()}L.v1"


def build_import_zip(
    reports: list[ReportDef],
    owner_user_id: str = "00000000-0000-0000-0000-00a1c0ffee01",
    marker_filename: str | None = None,
) -> bytes:
    """Build the outer content-zip that POST /api/content/operations/import accepts.

    Structure:
        <marker>L.v1          — marker file; content = owner user UUID
        configuration.json    — {"reports": N, "type": "CUSTOM"}
        reports.zip           — inner zip containing content.xml

    The marker filename must match the target instance's fingerprint.  Pass
    the value returned by ``vcfops_dashboards.client.discover_marker_filename``
    for a live sync; offline ``package`` invocations use a synthetic value that
    the importer will reject (documented limitation, same as dashboards packager).
    """
    xml = render_report_xml(reports)
    reports_inner = _build_reports_inner_zip(xml)

    config = {
        "reports": len(reports),
        "type": "CUSTOM",
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr(marker_filename or _default_marker_filename(), owner_user_id)
        outer.writestr("reports.zip", reports_inner)
        outer.writestr("configuration.json", json.dumps(config, indent=3))
    return buf.getvalue()
