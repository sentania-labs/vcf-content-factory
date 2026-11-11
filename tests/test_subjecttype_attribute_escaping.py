"""``<SubjectType>`` attribute values are escaped for quotes, too.

The view renderer (``vcfcf_core.dashboards.render``, both the view's own
SubjectType pair and the owning-adapter SubjectType) and the report
renderer wrote ``adapterKind`` / ``resourceKind`` (and the report's
``type``) through ``xml.sax.saxutils.escape`` with no entity map, which
escapes ``&``, ``<`` and ``>`` but not ``"``. A key containing a double
quote would end the attribute early. They now use the same
``escape(value, {chr(34): "&quot;"})`` form the package already uses for
``filter=`` and ``<Property>`` attributes. No real key contains a quote,
so no existing content renders differently.
"""
from __future__ import annotations

import dataclasses
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from vcfcf_core.dashboards.loader import load_view
from vcfcf_core.dashboards.render import render_views_xml
from vcfcf_core.reports.loader import (
    ReportDef,
    ReportSettings,
    Section,
    SubjectType,
)
from vcfcf_core.reports.render import render_report_xml

_REPO = Path(__file__).resolve().parents[1]

AK = 'Adapter"Kind & <A>'
RK = 'Resource"Kind & <R>'
OWN_AK = 'Own"Adapter & <O>'
OWN_RK = 'Own"Resource & <Q>'
TYPE = 'desc"endant & <T>'


def _resolver(view, name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "sm:" + name))


def _a_view():
    paths = sorted((_REPO / "content" / "views").glob("*.yaml"))
    assert paths, "no views under content/views"
    v = load_view(
        paths[0],
        enforce_framework_prefix=False,
        on_missing_id=lambda *a, **k: str(uuid.uuid4()),
    )
    # Single-subject form so subject_kinds is the scalar pair.
    return dataclasses.replace(v, adapter_kind=AK, resource_kind=RK, subjects=[])


def _subject_types(xml_text: str) -> list:
    root = ET.fromstring(xml_text)  # raises on a broken attribute
    return [dict(e.attrib) for e in root.iter("SubjectType")]


def test_view_subjecttype_pair_round_trips():
    xml_text = render_views_xml([_a_view()], sm_resolver=_resolver)
    sts = _subject_types(xml_text)
    pair = [s for s in sts if s.get("adapterKind") == AK]
    assert [s["type"] for s in pair] == ["descendant", "self"]
    assert all(s["resourceKind"] == RK for s in pair)
    assert "&quot;" in xml_text and "&amp;" in xml_text and "&lt;" in xml_text


def test_owning_subjecttype_round_trips():
    xml_text = render_views_xml(
        [_a_view()],
        sm_resolver=_resolver,
        owning_adapter_kind=OWN_AK,
        owning_resource_kind=OWN_RK,
    )
    owning = [s for s in _subject_types(xml_text) if s.get("adapterKind") == OWN_AK]
    assert owning == [
        {"adapterKind": OWN_AK, "resourceKind": OWN_RK, "type": "descendant"}
    ]


def test_report_subjecttype_round_trips():
    rd = ReportDef(
        name="[VCF Content Factory] Escape Probe",
        description="d",
        subject_types=[SubjectType(adapter_kind=AK, resource_kind=RK, type=TYPE)],
        sections=[Section(type="CoverPage")],
        settings=ReportSettings(),
        id=str(uuid.uuid4()),
    )
    sts = _subject_types(render_report_xml([rd]))
    assert sts == [{"adapterKind": AK, "resourceKind": RK, "type": TYPE}]
