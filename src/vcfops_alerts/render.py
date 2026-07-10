"""Render symptom/alert/recommendation definitions as AlertContent XML.

The produced XML matches the shape observed in
``tmp/Alert Definition-2026-04-11 03-54-10 PM.xml`` and the community
packages in reference/references/AriaOperationsContent.

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


def _symptom_id(adapter_kind: str, name: str, uuid: Optional[str] = None) -> str:
    """Return the canonical SymptomDefinition id attribute value.

    When ``uuid`` is supplied (i.e. the SymptomDef carries an ``id:`` field
    from its source YAML), the id is ``SymptomDefinition-<uuid>`` — matching
    the VCF Ops importer's corpus convention (original vmbro pack and every
    built-in symptomdef use this form).

    When ``uuid`` is absent (factory-authored symptoms that do not carry a
    pre-existing UUID), fall back to the derived slug form
    ``SymptomDefinition-<adapter>-<slug>`` so existing factory alerts and
    tests continue to work without change.

    The UUID form is required for pak content-import: the importer resolves
    symptomdef XML by the declared ``id``; a slug-based id is unresolvable
    and aborts the entire content/ tree (see
    ``knowledge/context/investigations/sdk_pak_content_import_gap.md``).
    """
    if uuid:
        return f"SymptomDefinition-{uuid}"
    return f"SymptomDefinition-{adapter_kind}-{_slug(name)}"


def _alert_id(adapter_kind: str, name: str) -> str:
    return f"AlertDefinition-{adapter_kind}-{_slug(name)}"


def _rec_key(adapter_kind: str, name: str) -> str:
    return f"Recommendation-df-{adapter_kind}-{_slug(name)}"


# ---------------------------------------------------------------------------
# Operator translation: YAML API-style names -> XML symbol form
# ---------------------------------------------------------------------------

# The VCF Ops content-import XML format uses symbolic operator strings, NOT the
# REST API enum names (NOT_EQ, GT, LT, etc.).  The importer rejects the API-style
# names with "Invalid operator:<name>".
#
# Reference: both symptomdefs in
#   reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/symptomdefs/
# use operator="!=" for NOT_EQ; alertdefs in the same pack use "&lt;" (decoded: "<")
# for LT and "&gt;=" (decoded: ">=") for GT_EQ.  ElementTree serializes "<" and ">="
# as "&lt;" / "&gt;=" automatically — we just supply the unescaped character.
#
# Mapping covers every operator the loader permits (STATIC_OPERATORS and
# PROPERTY_OPERATORS in vcfops_symptoms/loader.py).  Any unmapped operator passes
# through unchanged so future additions don't silently corrupt existing output.
_XML_OPERATOR_MAP: dict[str, str] = {
    "EQ": "==",
    "NOT_EQ": "!=",
    "GT": ">",
    "GT_EQ": ">=",
    "LT": "<",
    "LT_EQ": "<=",
    "CONTAINS": "contains",
    "NOT_CONTAINS": "notContains",
    "STARTS_WITH": "startsWith",
    "NOT_STARTS_WITH": "notStartsWith",
    "ENDS_WITH": "endsWith",
    "NOT_ENDS_WITH": "notEndsWith",
    "REGEX": "regex",
    "NOT_REGEX": "notRegex",
}


def _xml_operator(op: str) -> str:
    """Translate a YAML/API operator name to the XML symbol form the importer accepts."""
    return _XML_OPERATOR_MAP.get(op, op)


# ---------------------------------------------------------------------------
# Severity translation: REST wire token -> content-import XML token
# ---------------------------------------------------------------------------
#
# The REST API (vcfops_symptoms.loader.SEVERITY_MAP) and the content-import
# XML path disagree on the informational severity token: REST uses
# "INFORMATION", the XML importer only accepts lowercase "info" (and
# rejects "information" outright, silently skipping symptom creation — see
# knowledge/context/wire-formats/symptomdef_severity_import.md). Every other
# severity (WARNING/CRITICAL/IMMEDIATE) happens to share the same spelling
# on both paths, so a naive ``.lower()`` was correct for those and wrong
# only for INFO.
#
# This is a lookup map (not an inline branch) so future REST/XML token
# divergences slot in here rather than accreting ad-hoc special cases,
# mirroring the alert-State "auto" -> "automatic" translation below.
_XML_SEVERITY_MAP: dict[str, str] = {
    "INFORMATION": "info",
}


def _xml_severity(severity: str) -> str:
    """Translate a REST-wire severity token to the content-import XML token."""
    return _XML_SEVERITY_MAP.get(severity.upper(), severity.lower())


# ---------------------------------------------------------------------------
# Condition serialization (YAML condition dict -> XML Condition element)
# ---------------------------------------------------------------------------

def _add_condition_element(parent: ET.Element, cond: dict) -> None:
    """Append a <Condition> element to *parent* from the YAML condition dict.

    ``instanced``/``thresholdType``/``valueType`` wire shape — TOOLSET GAP
    fix (2026-07-09, defects.md DEF-<see below>): this XML content-import
    path previously never emitted ``instanced`` for metric_static/property
    conditions (the REST path's ``_condition_to_wire`` in
    ``vcfops_symptoms/loader.py`` always had it), so every instanced
    condition silently downgraded to exact-string key matching in every
    built pak. Fixed to mirror the vendor XML shape exactly, confirmed
    against two independent vendor symptomdefs (RULE-016 read-only
    references):

      reference/references/vmbro_vcf_operations_vcommunity/Management Pack/
        content/symptomdefs/ESXi Host NIC Disconnected Symptom.xml:5
        <Condition instanced="true" key="vCommunity|Network|Device:vmnic0|Status"
          operator="!=" thresholdType="static" type="property" value="Connected"
          valueType="string"/>

      reference/references/vmbro_vcf_operations_hardware_vcommunity/Management
        Pack/content/symptomdefs/Dell EMC Server Physical Disk Life Remaining -
        Critical.xml:5
        <Condition instanced="true" key="Hardware|Controller|Physical Disks:NVMe 0|
          Predicted Media Life Left Percent" operator="&lt;" thresholdType="static"
          type="metric" value="10.0" valueType="numeric"/>

    Both confirm ``thresholdType``/``valueType`` ARE present on the XML path
    (load-bearing, not server-defaulted) and use **lowercase** values
    ("static"/"numeric"/"string") — distinct from the REST wire's uppercase
    ("STATIC"/"NUMERIC"). The two wire formats are cased independently; do
    not copy the REST casing here.

    No vendor XML example with a DT (metric_dynamic) condition was found in
    any reference pak to confirm whether thresholdType/valueType apply
    there too. Since DT conditions carry no ``value`` at all (REST's own
    ``_condition_to_wire`` omits thresholdType/valueType for
    CONDITION_DT), this renderer follows the same omission for metric_dynamic
    on the XML path — instanced only, no thresholdType/valueType. Flag to
    api-explorer if a live/vendor DT example ever surfaces to confirm.
    """
    ctype = cond.get("type", "")
    key = cond.get("key", "")
    operator = cond.get("operator", "")
    instanced = "true" if cond.get("instanced", False) else "false"

    attribs: dict = {}

    if ctype == "metric_static":
        attribs["key"] = key
        attribs["operator"] = _xml_operator(operator)
        attribs["value"] = str(cond.get("value", ""))
        attribs["type"] = "metric"
        attribs["instanced"] = instanced
        attribs["thresholdType"] = "static"
        attribs["valueType"] = "numeric"

    elif ctype == "metric_dynamic":
        direction = cond.get("direction", "ABOVE")
        attribs["key"] = key
        attribs["operator"] = f"DT_{direction}"
        attribs["type"] = "metric"
        attribs["instanced"] = instanced

    elif ctype == "property":
        value = cond.get("value", "")
        attribs["key"] = key
        attribs["operator"] = _xml_operator(operator)
        attribs["value"] = str(value)
        attribs["type"] = "property"
        attribs["instanced"] = instanced
        attribs["thresholdType"] = "static"
        # Mirrors _condition_to_wire's CONDITION_PROPERTY_STRING/NUMERIC
        # split: bool -> string ("true"/"false" text), int/float -> numeric,
        # everything else -> string. See vcfops_symptoms/loader.py.
        if isinstance(value, bool):
            attribs["valueType"] = "string"
        elif isinstance(value, (int, float)):
            attribs["valueType"] = "numeric"
        else:
            attribs["valueType"] = "string"

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
    sym_uuid = getattr(sym, "id", None)
    sid = _symptom_id(adapter_kind, name, uuid=sym_uuid)

    attribs = {
        "adapterKind": adapter_kind,
        "cancelCycle": str(sym.cancel_cycles),
        "id": sid,
        "name": name,
        "resourceKind": resource_kind,
        "waitCycle": str(sym.wait_cycles),
    }
    sd_elem = ET.SubElement(parent, "SymptomDefinition", attribs)
    state_elem = ET.SubElement(sd_elem, "State", {"severity": _xml_severity(sym.severity)})
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

    # Emit SymptomSet elements — one per entry in symptom_sets["sets"], NOT
    # one per symptom.  Vendor ground truth (RULE-016; see
    # knowledge/context/wire-formats/alertdef_symptomset_import.md):
    # the platform's content importer keeps only the LAST of multiple bare
    # <SymptomSet> siblings under <State> — a compound <SymptomSets
    # operator="..."> wrapper is required whenever there are >=2 sets, and
    # is omitted (bare <SymptomSet> directly under <State>) when there is
    # exactly one set.  Within a set: a single symptom is a bare ref=
    # attribute on <SymptomSet>; multiple symptoms become <Symptom ref=.../>
    # children of a <SymptomSet operator="...">.  The non-vendor
    # aggregation="any" attribute is never emitted.
    symptom_sets = alert.symptom_sets or {}
    sets = symptom_sets.get("sets") or []

    def _symptom_set_elements() -> List[ET.Element]:
        elements: List[ET.Element] = []
        for s in sets:
            defined_on = (s.get("defined_on") or "SELF").upper()
            apply_on = defined_on.lower()
            set_op = "and" if (s.get("operator") or "ALL").upper() == "ALL" else "or"

            refs: List[str] = []
            for sym_ref in (s.get("symptoms") or []):
                sym_name = sym_ref.get("name", "")
                # Find the adapter_kind for this symptom by matching name to
                # the loaded symptom objects; fall back to the alert's
                # adapter_kind.
                sym_adapter = adapter_kind
                sym_uuid = None
                for sym_obj in symptom_objs:
                    if sym_obj.name == sym_name:
                        sym_adapter = sym_obj.adapter_kind
                        sym_uuid = getattr(sym_obj, "id", None)
                        break
                refs.append(_symptom_id(sym_adapter, sym_name, uuid=sym_uuid))

            if len(refs) == 1:
                ss_elem = ET.Element("SymptomSet", {
                    "applyOn": apply_on,
                    "operator": set_op,
                    "ref": refs[0],
                })
            else:
                ss_elem = ET.Element("SymptomSet", {
                    "applyOn": apply_on,
                    "operator": set_op,
                })
                for ref in refs:
                    ET.SubElement(ss_elem, "Symptom", {"ref": ref})
            elements.append(ss_elem)
        return elements

    ss_elements = _symptom_set_elements()
    if len(ss_elements) >= 2:
        top_op = "and" if (symptom_sets.get("operator") or "ALL").upper() == "ALL" else "or"
        wrapper = ET.SubElement(state_elem, "SymptomSets", {"operator": top_op})
        for elem in ss_elements:
            wrapper.append(elem)
    else:
        for elem in ss_elements:
            state_elem.append(elem)

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
