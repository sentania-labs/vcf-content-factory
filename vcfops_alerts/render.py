"""Render symptom/alert/recommendation definitions as AlertContent XML.

The produced XML matches the shape observed in
``tmp/Alert Definition-2026-04-11 03-54-10 PM.xml`` and the community
packages in references/AriaOperationsContent.

Root element: ``<alertContent>``
Children:
  ``<AlertDefinitions>``   (per alert)
  ``<SymptomDefinitions>`` (per symptom)
  ``<Recommendations>``    (per recommendation, if any)

ID / key derivation
-------------------
The id and key attributes are synthesised deterministically from the
adapter_kind and a slugified form of the display name:

  SymptomDefinition  id="SymptomDefinition-<adapter>-<slug>"
  AlertDefinition    id="AlertDefinition-<adapter>-<slug>"
  Recommendation     key="Recommendation-df-<adapter>-<slug>"

The slug is the display name with characters outside [A-Za-z0-9_-]
replaced by an underscore, then deduplicated runs of underscores
collapsed, and leading/trailing underscores stripped.

Adapter kind caveat
-------------------
Our YAML stores adapter_kind in key form (e.g. ``VMWARE``).
The XML format observed in the reference export uses the display-name
form for some adapters (e.g. ``"vCenter Operations Adapter"``).
This renderer uses the key form as-is; a follow-up api-explorer task
will verify which adapters need display-name form and can build a
lookup table.  See the plan in `.claude/plans/woolly-humming-pretzel.md`.

Condition type mapping (symptom XML vs REST JSON)
-------------------------------------------------
The REST API wire format (used by the installer) differs from the XML
import format used by the UI:

REST -> XML mapping:
  CONDITION_HT  -> Condition type="metric"   (key, operator, value attrs)
  CONDITION_DT  -> Condition type="metric"   (key, operator=DT_ABOVE etc, no value)
  CONDITION_PROPERTY_STRING/NUMERIC -> Condition type="property" (key, operator, value)
  msg_event     -> Condition type="msg_event" (eventMsg, eventSubType, eventType, operator)

The condition dict in our YAML uses the loader's terse form:
  {type: metric_static, key: ..., operator: ..., value: ...}
  {type: metric_dynamic, key: ..., direction: ...}
  {type: property, key: ..., operator: ..., value: ...}

This renderer maps those to XML attributes.  The msg_event type is not
authored via our symptom YAML today (it appears in built-in symptoms) but
is included here for completeness so the serialiser does not break when
given such a symptom in future.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, Optional

# Type imports — kept lightweight; no dependency on the full loader pipeline
# so this module can be tested in isolation.
try:
    from vcfops_symptoms.loader import SymptomDef
    from vcfops_alerts.loader import AlertDef
except ImportError:  # pragma: no cover — allows isolated testing
    SymptomDef = None  # type: ignore[assignment,misc]
    AlertDef = None    # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    """Deterministic slug from a display name for use in id/key attrs."""
    slug = re.sub(r"[^\w\-]", "_", name)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def _symptom_id(adapter_kind: str, name: str) -> str:
    return f"SymptomDefinition-{adapter_kind}-{_slug(name)}"


def _alert_id(adapter_kind: str, name: str) -> str:
    return f"AlertDefinition-{adapter_kind}-{_slug(name)}"


def _rec_key(adapter_kind: str, name: str) -> str:
    return f"Recommendation-df-{adapter_kind}-{_slug(name)}"


# ---------------------------------------------------------------------------
# Condition serialization (YAML condition dict -> XML Condition element)
# ---------------------------------------------------------------------------

def _add_condition_element(parent: ET.Element, cond: dict) -> None:
    """Append a <Condition> element to *parent* from the YAML condition dict."""
    ctype = cond.get("type", "")
    key = cond.get("key", "")
    operator = cond.get("operator", "")

    attribs: dict = {}

    if ctype == "metric_static":
        attribs["key"] = key
        attribs["operator"] = operator
        attribs["value"] = str(cond.get("value", ""))
        attribs["type"] = "metric"

    elif ctype == "metric_dynamic":
        direction = cond.get("direction", "ABOVE")
        attribs["key"] = key
        attribs["operator"] = f"DT_{direction}"
        attribs["type"] = "metric"

    elif ctype == "property":
        attribs["key"] = key
        attribs["operator"] = operator
        attribs["value"] = str(cond.get("value", ""))
        attribs["type"] = "property"

    elif ctype == "msg_event":
        # Built-in / future symptom type: pass through event attributes.
        attribs["type"] = "msg_event"
        for k in ("eventMsg", "eventSubType", "eventType", "operator"):
            if k in cond:
                attribs[k] = str(cond[k])

    else:
        # Unknown type — emit whatever we have with a generic type attr.
        attribs["key"] = key
        attribs["type"] = ctype

    ET.SubElement(parent, "Condition", attribs)


# ---------------------------------------------------------------------------
# Symptom serialization
# ---------------------------------------------------------------------------

def _render_symptom_definition(parent: ET.Element, sym, all_sym_names: set) -> None:
    """Append a <SymptomDefinition> element to *parent*."""
    adapter_kind = sym.adapter_kind
    resource_kind = sym.resource_kind
    name = sym.name
    sid = _symptom_id(adapter_kind, name)

    attribs = {
        "adapterKind": adapter_kind,
        "cancelCycle": str(sym.cancel_cycles),
        "id": sid,
        "name": name,
        "resourceKind": resource_kind,
        "waitCycle": str(sym.wait_cycles),
    }
    sd_elem = ET.SubElement(parent, "SymptomDefinition", attribs)
    state_elem = ET.SubElement(sd_elem, "State", {"severity": sym.severity.lower()})
    _add_condition_element(state_elem, sym.condition)


# ---------------------------------------------------------------------------
# Alert serialization
# ---------------------------------------------------------------------------

def _render_alert_definition(
    parent: ET.Element,
    alert,
    symptom_objs: list,
    recommendations: Optional[List[dict]] = None,
) -> None:
    """Append an <AlertDefinition> element to *parent*.

    Each alert's <State> contains:
      - One <SymptomSet> per symptom-set in the alert's symptom_sets.
      - One <Impact> element.
      - An optional <Recommendations> block if the alert has recommendations.

    Cross-references to SymptomDefinitions use the deterministic id scheme.
    """
    adapter_kind = alert.adapter_kind
    resource_kind = alert.resource_kind
    name = alert.name
    aid = _alert_id(adapter_kind, name)

    attribs = {
        "adapterKind": adapter_kind,
        "description": alert.description or "",
        "id": aid,
        "name": name,
        "resourceKind": resource_kind,
        "subType": str(alert.sub_type),
        "type": str(alert.type),
    }
    ad_elem = ET.SubElement(parent, "AlertDefinition", attribs)

    # Build severity for State — use the criticality from the alert (lowercased
    # for consistency with the observed XML format; "automatic" for AUTO).
    severity = alert.criticality.lower()
    if severity == "auto":
        severity = "automatic"
    state_elem = ET.SubElement(ad_elem, "State", {"severity": severity})

    # Emit SymptomSet references.
    symptom_sets = alert.symptom_sets or {}
    sets = symptom_sets.get("sets") or []
    for s in sets:
        for sym_ref in (s.get("symptoms") or []):
            sym_name = sym_ref.get("name", "")
            # Find the adapter_kind for this symptom by matching name to the
            # loaded symptom objects; fall back to the alert's adapter_kind.
            sym_adapter = adapter_kind
            for sym_obj in symptom_objs:
                if sym_obj.name == sym_name:
                    sym_adapter = sym_obj.adapter_kind
                    break
            ref = _symptom_id(sym_adapter, sym_name)
            ET.SubElement(state_elem, "SymptomSet", {
                "aggregation": "any",
                "applyOn": "self",
                "operator": "and",
                "ref": ref,
            })

    # Impact badge.
    ET.SubElement(state_elem, "Impact", {
        "key": alert.impact_badge.lower(),
        "type": "badge",
    })

    # Recommendations block (inside <State>).
    recs = recommendations or []
    if recs:
        recs_elem = ET.SubElement(state_elem, "Recommendations")
        for i, rec in enumerate(recs, 1):
            rec_name = rec.get("name") or rec.get("description", f"Recommendation {i}")
            rec_key = _rec_key(adapter_kind, rec_name)
            ET.SubElement(recs_elem, "Recommendation", {
                "priority": str(i),
                "ref": rec_key,
            })


# ---------------------------------------------------------------------------
# Top-level serializer
# ---------------------------------------------------------------------------

def render_alert_content_xml(
    symptoms: list,
    alerts: list,
    recommendations: Optional[List[dict]] = None,
) -> str:
    """Produce a single ``<alertContent>`` XML string for UI drag-drop import.

    Args:
        symptoms: List of SymptomDef objects (from vcfops_symptoms.loader).
        alerts:   List of AlertDef objects (from vcfops_alerts.loader).
        recommendations: Optional list of recommendation dicts with at least
            ``name`` (or ``description``) and ``description`` keys.  These
            correspond to the top-level ``<Recommendations>`` block.

    Returns:
        A UTF-8 XML string with a ``<?xml version="1.0" encoding="UTF-8"?>``
        declaration, suitable for writing to ``AlertContent.xml``.
    """
    recommendations = recommendations or []

    root = ET.Element("alertContent")

    # --- AlertDefinitions ---
    if alerts:
        alert_defs_elem = ET.SubElement(root, "AlertDefinitions")
        for alert in alerts:
            # Gather per-alert recommendations: from the alert's own
            # recommendations list (if any).
            alert_recs = getattr(alert, "recommendations", None) or []
            _render_alert_definition(alert_defs_elem, alert, symptoms, alert_recs)

    # --- SymptomDefinitions ---
    if symptoms:
        symptom_defs_elem = ET.SubElement(root, "SymptomDefinitions")
        all_sym_names = {s.name for s in symptoms}
        for sym in symptoms:
            _render_symptom_definition(symptom_defs_elem, sym, all_sym_names)

    # --- Top-level Recommendations ---
    # Collect from alert-level recommendations too.
    all_recs: List[dict] = list(recommendations)
    for alert in alerts:
        alert_recs = getattr(alert, "recommendations", None) or []
        all_recs.extend(alert_recs)

    if all_recs:
        recs_elem = ET.SubElement(root, "Recommendations")
        for rec in all_recs:
            adapter_kind = rec.get("adapter_kind", "")
            rec_name = rec.get("name") or rec.get("description", "")
            rec_key = _rec_key(adapter_kind, rec_name)
            rec_elem = ET.SubElement(recs_elem, "Recommendation", {"key": rec_key})
            desc_elem = ET.SubElement(rec_elem, "Description")
            desc_elem.text = rec.get("description", "")

    # Serialize with indentation for human readability.
    _indent(root)

    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"


def _indent(elem: ET.Element, level: int = 0) -> None:
    """In-place pretty-print indentation for ElementTree (Python < 3.9 compat)."""
    indent = "\n" + "    " * level
    if len(elem):
        elem.text = indent + "    "
        for child in elem:
            _indent(child, level + 1)
            child.tail = indent + "    "
        # Last child gets the closing-tag indent
        child.tail = indent  # type: ignore[possibly-undefined]
    else:
        if not elem.text:
            elem.text = ""
    if level:
        elem.tail = indent
