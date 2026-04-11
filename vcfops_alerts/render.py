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
    from vcfops_alerts.loader import AlertDef, Recommendation
except ImportError:  # pragma: no cover — allows isolated testing
    SymptomDef = None  # type: ignore[assignment,misc]
    AlertDef = None    # type: ignore[assignment,misc]
    Recommendation = None  # type: ignore[assignment,misc]


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
    recommendation_map: Optional[dict] = None,
) -> None:
    """Append an <AlertDefinition> element to *parent*.

    Each alert's <State> contains:
      - One <SymptomSet> per symptom-set in the alert's symptom_sets.
      - One <Impact> element.
      - An optional <Recommendations> block if the alert has recommendations.

    Cross-references to SymptomDefinitions use the deterministic id scheme.
    Cross-references to Recommendations use the Recommendation.id property
    to guarantee the ref= attribute matches the key= attribute in the
    top-level <Recommendations> block.

    Args:
        parent:           Parent XML element (<AlertDefinitions>).
        alert:            AlertDef object.
        symptom_objs:     List of SymptomDef objects for adapter_kind lookup.
        recommendation_map: Dict mapping recommendation name -> Recommendation
            object.  Used to resolve RecommendationRef objects on the alert.
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
    # alert.recommendations is a list of RecommendationRef objects.
    rec_refs = getattr(alert, "recommendations", None) or []
    rmap = recommendation_map or {}
    resolved_recs = []
    for ref in rec_refs:
        rec_name = ref.name if hasattr(ref, "name") else ref.get("name", "")
        rec_priority = ref.priority if hasattr(ref, "priority") else ref.get("priority", 1)
        rec_obj = rmap.get(rec_name)
        if rec_obj is not None:
            resolved_recs.append((rec_priority, rec_obj.id))
        # Unresolved recommendations are silently skipped in render
        # (validation already caught missing [VCF Content Factory] refs)
    if resolved_recs:
        recs_elem = ET.SubElement(state_elem, "Recommendations")
        for priority, rec_key in sorted(resolved_recs, key=lambda t: t[0]):
            ET.SubElement(recs_elem, "Recommendation", {
                "priority": str(priority),
                "ref": rec_key,
            })


# ---------------------------------------------------------------------------
# Top-level serializer
# ---------------------------------------------------------------------------

def render_alert_content_xml(
    symptoms: list,
    alerts: list,
    recommendations: Optional[list] = None,
) -> str:
    """Produce a single ``<alertContent>`` XML string for UI drag-drop import.

    Args:
        symptoms:        List of SymptomDef objects (from vcfops_symptoms.loader).
        alerts:          List of AlertDef objects (from vcfops_alerts.loader).
        recommendations: Optional list of Recommendation objects
            (from vcfops_alerts.loader).  These populate the top-level
            ``<Recommendations>`` block.  The Recommendation.id property
            is used for the ``key=`` attribute, which guarantees it matches
            the ``ref=`` attributes emitted inside each ``<AlertDefinition>``.

    Returns:
        A UTF-8 XML string with a ``<?xml version="1.0" encoding="UTF-8"?>``
        declaration, suitable for writing to ``AlertContent.xml``.
    """
    recommendations = recommendations or []

    # Build a name -> Recommendation map for O(1) lookups in alert rendering.
    rec_map: dict = {}
    for rec in recommendations:
        if hasattr(rec, "name"):
            rec_map[rec.name] = rec

    # Also collect recommendations referenced by alerts but not in the explicit
    # list — this handles the case where the caller passes alert-level inline
    # dicts (legacy path).  In the new path all recs come from recommendations/.
    # We keep this guard so existing bundle builder calls with recommendations=[]
    # still work correctly.

    root = ET.Element("alertContent")

    # --- AlertDefinitions ---
    if alerts:
        alert_defs_elem = ET.SubElement(root, "AlertDefinitions")
        for alert in alerts:
            _render_alert_definition(alert_defs_elem, alert, symptoms, rec_map)

    # --- SymptomDefinitions ---
    if symptoms:
        symptom_defs_elem = ET.SubElement(root, "SymptomDefinitions")
        all_sym_names = {s.name for s in symptoms}
        for sym in symptoms:
            _render_symptom_definition(symptom_defs_elem, sym, all_sym_names)

    # --- Top-level Recommendations ---
    # Include all Recommendation objects that were passed in.  The Recommendation.id
    # property generates the key= attribute; the description goes into <Description>.
    if rec_map:
        recs_elem = ET.SubElement(root, "Recommendations")
        for rec in recommendations:
            if not hasattr(rec, "id"):
                continue  # skip non-Recommendation objects (safety guard)
            rec_elem = ET.SubElement(recs_elem, "Recommendation", {"key": rec.id})
            desc_elem = ET.SubElement(rec_elem, "Description")
            desc_elem.text = rec.description or ""

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
