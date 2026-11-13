"""XML attribute values in the view and report renderers escape quotes, too.

The view renderer (``vcfcf_core.dashboards.render``) and the report
renderer wrote several attribute values through ``xml.sax.saxutils.escape``
with no entity map, which escapes ``&``, ``<`` and ``>`` but not ``"``, and
the trend view's ``transformations`` items with no escaping at all. A value
containing a double quote ended the attribute early. They now use the same
``escape(value, {chr(34): "&quot;"})`` form the package already uses for
``filter=`` and ``<Property>`` attributes. No real value contains a quote,
so no existing content renders differently (proved by a render comparison
against origin/main, not by this file).

Every touched attribute gets one round trip here: render a value with a
quote, an ampersand and angle brackets, parse the XML (a broken attribute
raises), and read the same value back.
"""
from __future__ import annotations

import dataclasses
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from vcfcf_core.dashboards.loader import (
    BucketsConfig,
    ViewTimeWindow,
    load_view,
)
from vcfcf_core.dashboards.render import render_views_xml
from vcfcf_core.reports.loader import (
    ReportDef,
    ReportSettings,
    Section,
    SubjectType,
)
from vcfcf_core.reports.render import render_report_xml

_REPO = Path(__file__).resolve().parents[1]
_VIEWS = _REPO / "content" / "views"

AK = 'Adapter"Kind & <A>'
RK = 'Resource"Kind & <R>'
OWN_AK = 'Own"Adapter & <O>'
OWN_RK = 'Own"Resource & <Q>'
TYPE = 'desc"endant & <T>'
NASTY = 'X"Y & <Z>'  # upper-case already: some sites upper-case the value


def _resolver(view, name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "sm:" + name))


def _load(name: str):
    return load_view(
        _VIEWS / name,
        enforce_framework_prefix=False,
        on_missing_id=lambda *a, **k: str(uuid.uuid4()),
    )


def _a_view():
    paths = sorted(_VIEWS.glob("*.yaml"))
    assert paths, "no views under content/views"
    return _load(paths[0].name)


def _root(view, **kw):
    return ET.fromstring(render_views_xml([view], sm_resolver=_resolver, **kw))


def _property_values(root, name: str) -> list:
    return [e.get("value") for e in root.iter("Property") if e.get("name") == name]


def _item_values(root) -> list:
    return [e.get("value") for e in root.iter("Item")]


# --- SubjectType -----------------------------------------------------------

def test_view_subjecttype_pair_round_trips():
    v = dataclasses.replace(_a_view(), adapter_kind=AK, resource_kind=RK, subjects=[])
    xml_text = render_views_xml([v], sm_resolver=_resolver)
    sts = [dict(e.attrib) for e in ET.fromstring(xml_text).iter("SubjectType")]
    pair = [s for s in sts if s.get("adapterKind") == AK]
    assert [s["type"] for s in pair] == ["descendant", "self"]
    assert all(s["resourceKind"] == RK for s in pair)
    assert "&quot;" in xml_text and "&amp;" in xml_text and "&lt;" in xml_text


def test_owning_subjecttype_round_trips():
    root = _root(_a_view(), owning_adapter_kind=OWN_AK, owning_resource_kind=OWN_RK)
    owning = [dict(e.attrib) for e in root.iter("SubjectType")
              if e.get("adapterKind") == OWN_AK]
    assert owning == [
        {"adapterKind": OWN_AK, "resourceKind": OWN_RK, "type": "descendant"}
    ]


def test_report_subjecttype_and_id_round_trip():
    rd = ReportDef(
        name="[VCF CF] Escape Probe",
        description="d",
        subject_types=[SubjectType(adapter_kind=AK, resource_kind=RK, type=TYPE)],
        sections=[Section(type="CoverPage")],
        settings=ReportSettings(),
        id=NASTY,
    )
    root = ET.fromstring(render_report_xml([rd]))
    sts = [dict(e.attrib) for e in root.iter("SubjectType")]
    assert sts == [{"adapterKind": AK, "resourceKind": RK, "type": TYPE}]
    assert [e.get("id") for e in root.iter("ReportDef")] == [NASTY]


# --- Presentation type (list, distribution and trend branches) -------------

def test_presentation_type_round_trips_on_every_branch():
    base = _a_view()
    trend = _load("vcf_license_automation_consumption_trend.yaml")
    for v in (
        dataclasses.replace(base, presentation=NASTY),
        dataclasses.replace(base, data_type="distribution", presentation=NASTY),
        dataclasses.replace(trend, presentation=NASTY),
    ):
        root = _root(v)
        assert [e.get("type") for e in root.iter("Presentation")] == [NASTY], v.data_type


# --- transformations Item --------------------------------------------------

def test_column_transformation_item_round_trips():
    v = _a_view()
    cols = list(v.columns)
    cols[0] = dataclasses.replace(cols[0], transformation=NASTY)
    root = _root(dataclasses.replace(v, columns=cols))
    assert NASTY in _item_values(root)


def test_instanced_group_transformation_item_round_trips():
    v = _load("vm_snapshot_inventory.yaml")
    cols = list(v.columns)
    idx = next(i for i, c in enumerate(cols)
               if c.instanced_group is not None and not c.instanced_group.is_driver)
    cols[idx] = dataclasses.replace(cols[idx], transformation=NASTY)
    root = _root(dataclasses.replace(v, columns=cols))
    assert NASTY in _item_values(root)


def test_trend_view_transformations_items_round_trip():
    v = _load("vcf_license_automation_consumption_trend.yaml")
    root = _root(dataclasses.replace(v, transformations=[NASTY, "TREND"]))
    items = _item_values(root)
    assert NASTY in items and "TREND" in items


# --- time window and buckets controls --------------------------------------

def test_time_window_values_round_trip():
    tw = ViewTimeWindow(unit=NASTY, count=3, advanced_time_mode=True,
                        start_period='S"P & <1>', end_period='E"P & <2>')
    root = _root(dataclasses.replace(_a_view(), time_window=tw))
    assert _property_values(root, "unit") == [NASTY]
    assert _property_values(root, "startPeriod") == ['S"P & <1>']
    assert _property_values(root, "endPeriod") == ['E"P & <2>']


def test_buckets_calc_function_round_trips():
    v = dataclasses.replace(
        _a_view(), data_type="distribution",
        buckets=BucketsConfig(is_dynamic=True, calc_function=NASTY),
    )
    assert _property_values(_root(v), "dynamicCalcFunction") == [NASTY]
