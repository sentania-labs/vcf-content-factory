"""ReportDef XML -> factory report YAML.

Wire format and YAML: ``knowledge/context/wire-formats/template_fidelity_wire_format.md``.
A View or Dashboard section names an object in the conversion set by name
(``view:`` / ``dashboard:``) and anything else by raw id (``view_id:`` /
``dashboard_id:``, the product-shipped form). ``localizationKey`` on the
Title and Description is not modeled (it points at a localization bundle the
factory does not ship; DEF-018), nor is surrounding whitespace on the
Description (the loader strips it; ``accounting.STRIPPED_TEXT``); each is recorded as a documented loss at
its exact path; anything else the YAML cannot carry stops the template with a
TOOLSET GAP, and ``accounting.account`` classifies every source key.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict

from . import flat as _flat
from .accounting import account
from .model import MappedObject, MappingError, Mark, documented_loss, gap_error
from .refs import Ref

_TOP = ("isTenant", "Title", "Description", "SubjectType", "Sections", "Settings")


def map_report(rd, location: str) -> MappedObject:
    losses: list = []

    class _L(list):
        def append(self, msg):  # not documented: a TOOLSET GAP
            raise gap_error(msg, "report")
    issues = _L()
    y: Dict[str, object] = OrderedDict()
    y["id"] = rd.get("id")
    # The name exactly as the source has it (the planner records a change).
    y["name"] = rd.findtext("Title") or ""
    # Surrounding whitespace the loader strips: accounting.STRIPPED_TEXT.
    y["description"] = rd.findtext("Description") or ""
    for tag in ("Title", "Description"):
        el = rd.find(tag)
        if el is not None and el.get("localizationKey") is not None:
            documented_loss(losses, "Title/Description localizationKey",
                            f"{tag} localizationKey is not modeled (template fidelity doc §Not modeled; DEF-018)",
                            [Mark(f"ReportDef/{tag}@localizationKey", "missing")])
    if (rd.findtext("isTenant") or "false").strip() != "false":
        issues.append(f"isTenant={rd.findtext('isTenant')!r} is not modeled (renders false)")
    if rd.find("isTenant") is None:
        issues.append("absent isTenant is not modeled (renders false)")
    for child in rd:
        if child.tag not in _TOP:
            issues.append(f"element {child.tag} is not modeled")
    sts = []
    for st in rd.findall("SubjectType"):
        e: Dict[str, object] = OrderedDict(adapter_kind=st.get("adapterKind"), resource_kind=st.get("resourceKind"),
                                           type=st.get("type"))
        if st.get("filter"):
            e["filter"] = st.get("filter")
        sts.append(e)
    y["subject_types"] = sts
    secs = []
    sections = rd.find("Sections")
    if sections is None:
        raise MappingError("ReportDef has no Sections element")
    for i, sec in enumerate(sections):
        ct = (sec.findtext("ContentType") or "").strip()
        s: Dict[str, object] = OrderedDict(type=ct)
        fmt = sec.find("ContentFormatting")
        known = {"ContentType", "ContentKey", "ContentOrientation", "ContentFormatting"}
        for child in sec:
            if child.tag not in known:
                issues.append(f"section {i}: element {child.tag} is not modeled")
        if ct in ("CoverPage", "TableOfContents"):
            if fmt is not None:
                if fmt.find("ColorizeListView") is not None:
                    s["colorize"] = (fmt.findtext("ColorizeListView") or "").strip() == "true"
                if fmt.find("FontColor") is not None:
                    s["font_color"] = (fmt.findtext("FontColor") or "").strip()
                for child in fmt:
                    if child.tag not in ("ColorizeListView", "FontColor"):
                        issues.append(f"section {i}: formatting {child.tag} is not modeled")
        elif ct in ("View", "Dashboard"):
            key = (sec.findtext("ContentKey") or "").strip()
            if ct == "View":
                s["view"] = Ref("view", key, form="name", external_key="view_id", where=f"section {i}")
                if fmt is None:
                    s["omit"] = ["formatting"]
                else:
                    s["colorize"] = (fmt.findtext("ColorizeListView") or "").strip() == "true"
                    for child in fmt:
                        if child.tag != "ColorizeListView":
                            issues.append(f"section {i}: formatting {child.tag} is not modeled")
            else:
                s["dashboard"] = Ref("dashboard", key, form="name", external_key="dashboard_id",
                                     where=f"section {i}")
                if fmt is not None:
                    issues.append(f"section {i}: ContentFormatting on a Dashboard section is not modeled")
            orient = sec.findtext("ContentOrientation")
            if orient is None:
                issues.append(f"section {i}: absent ContentOrientation is not modeled (renders Landscape)")
            s["orientation"] = (orient or "Landscape").strip()
        else:
            raise MappingError(f"section {i}: ContentType {ct!r} is not modeled",
                               gap={"what": f"report section type {ct}"})
        secs.append(s)
    y["sections"] = secs
    st_el = rd.find("Settings")
    if st_el is None:
        raise MappingError("ReportDef has no Settings element")
    for child in st_el:
        if child.tag not in ("ShowPageFooter", "OutputFormat"):
            issues.append(f"setting {child.tag} is not modeled")
    y["settings"] = OrderedDict(
        show_page_footer=(st_el.findtext("ShowPageFooter") or "true").strip() == "true",
        output_formats=[(o.text or "").strip() for o in st_el.findall("OutputFormat")],
    )
    if not y["settings"]["output_formats"]:
        issues.append("no OutputFormat is not modeled (renders pdf)")
    account("report", _flat.flatten_plain_xml(rd), losses)
    return MappedObject("report", y, losses=losses, source_name=y["name"])
