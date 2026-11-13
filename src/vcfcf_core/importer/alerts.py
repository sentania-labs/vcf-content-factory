"""alertContent XML (alert definitions, symptom definitions, recommendations)
-> factory alert, symptom and recommendation YAML.

Wire format and YAML: ``knowledge/context/wire-formats/alert_fidelity_wire_format.md``.
An alert names its symptoms and recommendations by NAME; a symptom or
recommendation outside the conversion set cannot be named (the renderer
derives a slug id for an unknown symptom name and drops an unknown
recommendation), so such an alert fails with the reason instead of
converting to something that renders differently.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List

from .model import MappedObject, MappingError, loss_or_gap, toolset_gap
from .refs import Ref

#: XML operator symbol -> YAML operator (inverse of alerts.render._XML_OPERATOR_MAP).
OPERATORS = {
    "==": "EQ", "=": "EQ", "!=": "NOT_EQ", ">": "GT", ">=": "GT_EQ", "<": "LT", "<=": "LT_EQ",
    "contains": "CONTAINS", "notContains": "NOT_CONTAINS", "startsWith": "STARTS_WITH",
    "notStartsWith": "NOT_STARTS_WITH", "endsWith": "ENDS_WITH", "notEndsWith": "NOT_ENDS_WITH",
    "regex": "REGEX", "notRegex": "NOT_REGEX",
}
SEVERITIES = {"critical": "CRITICAL", "immediate": "IMMEDIATE", "warning": "WARNING", "info": "INFO"}
_DT = {"above": "ABOVE", "below": "BELOW", "abnormal": "ABNORMAL"}
_ALERT_ATTRS = {"adapterKind", "description", "id", "name", "resourceKind", "subType", "type",
                "waitCycle", "cancelCycle", "disableInBasePolicy"}
_SYMPTOM_ATTRS = {"adapterKind", "cancelCycle", "id", "name", "resourceKind", "waitCycle",
                  "disableInBasePolicy", "symptomDefType"}


def strip_prefix(value: str, prefix: str) -> str:
    return value[len(prefix):] if value.startswith(prefix) else value


def _value(v: str, numeric: bool):
    if not numeric:
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return float(f) if "." in v or "e" in v.lower() else int(f)


def map_symptom(sd, location: str) -> MappedObject:
    losses: List[str] = []
    for a in sd.attrib:
        if a not in _SYMPTOM_ATTRS:
            _gap(f"attribute {a} is not modeled")
    y: Dict[str, object] = OrderedDict()
    y["id"] = strip_prefix(sd.get("id", ""), "SymptomDefinition-")
    y["name"] = sd.get("name", "")
    y["adapter_kind"] = sd.get("adapterKind")
    y["resource_kind"] = sd.get("resourceKind")
    st = sd.find("State")
    if st is None:
        raise MappingError("SymptomDefinition has no State")
    sev = (st.get("severity") or "").lower()
    if sev not in SEVERITIES:
        raise MappingError(f"symptom severity {st.get('severity')!r} is not modeled")
    y["severity"] = SEVERITIES[sev]
    omit: List[str] = []
    for a, k in (("waitCycle", "wait_cycles"), ("cancelCycle", "cancel_cycles")):
        if sd.get(a) is None:
            y[k] = 1
            omit.append(k)
        else:
            y[k] = int(sd.get(a))
    if sd.get("disableInBasePolicy") == "true":
        y["disable_in_base_policy"] = True
    if sd.get("symptomDefType"):
        y["symptom_def_type"] = sd.get("symptomDefType")
    conds = st.findall("Condition")
    if len(conds) != 1 or len(st) != 1:
        raise MappingError(f"symptom State with {len(st)} children (one Condition expected) is not modeled")
    c = conds[0]
    ctype = c.get("type")
    op = c.get("operator")
    if ctype == "metric":
        if op not in OPERATORS:
            raise MappingError(f"metric condition operator {op!r} is not modeled")
        cond: Dict[str, object] = OrderedDict(type="metric_static", key=c.get("key"), operator=OPERATORS[op],
                                              value=_value(c.get("value", ""), True))
        expected = {"key", "operator", "value", "type", "instanced", "thresholdType", "valueType"}
        if c.get("thresholdType", "static") != "static" or c.get("valueType", "numeric") != "numeric":
            _gap(f"metric condition thresholdType/valueType {c.get('thresholdType')}/{c.get('valueType')} is not modeled")
        for a in ("thresholdType", "valueType"):
            if c.get(a) is None:
                _gap(f"metric condition without {a} is not modeled (the renderer always writes it)")
    elif ctype == "property":
        if op not in OPERATORS:
            raise MappingError(f"property condition operator {op!r} is not modeled")
        numeric = c.get("valueType") == "numeric"
        cond = OrderedDict(type="property", key=c.get("key"), operator=OPERATORS[op],
                           value=_value(c.get("value", ""), numeric))
        if numeric and isinstance(cond["value"], str):
            _gap("numeric property condition with a non-numeric value is rendered as a string")
        expected = {"key", "operator", "value", "type", "instanced", "thresholdType", "valueType"}
        if c.get("thresholdType", "static") != "static":
            _gap(f"property condition thresholdType {c.get('thresholdType')} is not modeled")
        for a in ("thresholdType", "valueType"):
            if c.get(a) is None:
                _gap(f"property condition without {a} is not modeled (the renderer always writes it)")
    elif ctype == "dtmetric":
        if op not in _DT:
            raise MappingError(f"dtmetric operator {op!r} is not modeled")
        cond = OrderedDict(type="metric_dynamic", key=c.get("key"), direction=_DT[op])
        expected = {"key", "operator", "type", "instanced"}
    else:
        raise MappingError(
            f"symptom condition type {ctype!r} is not modeled by the symptom YAML",
            gap=toolset_gap(
                f"symptom condition type {ctype!r} in the symptom YAML",
                f"<Condition type={ctype!r} .../> in a SymptomDefinition",
                "convert the symptom definition faithfully",
                "add the condition type to vcfcf_core/symptoms/loader.py and alerts/render.py",
            ),
        )
    for a in c.attrib:
        if a not in expected:
            _gap(f"condition attribute {a} is not modeled")
    if c.get("instanced") is None:
        if ctype == "dtmetric":
            _gap("dtmetric condition without instanced is not modeled")
        else:
            omit.append("instanced")
    else:
        cond["instanced"] = c.get("instanced") == "true"
    y["condition"] = cond
    if omit:
        y["omit"] = omit
    return MappedObject("symptom", y, losses=losses)


def map_recommendation(rec, location: str, adapter_kind: str) -> MappedObject:
    losses: List[str] = []
    key = rec.get("key") or rec.get("id")
    desc = (rec.findtext("Description") or "").strip()
    if not desc:
        raise MappingError("recommendation with an empty Description: the recommendation YAML requires one",
                           gap=toolset_gap("an empty recommendation description", "<Recommendation key=..."
                                           "><Description/></Recommendation>",
                                           "convert the recommendation", "allow description: '' in the loader"))
    for child in rec:
        if child.tag != "Description":
            _gap(f"recommendation element {child.tag} is not modeled")
    for a in rec.attrib:
        if a not in ("key", "id"):
            _gap(f"recommendation attribute {a} is not modeled")
    y: Dict[str, object] = OrderedDict(name=key, id=key, description=desc, adapter_kind=adapter_kind)
    return MappedObject("recommendation", y, losses=losses)


def map_alert(ad, location: str) -> MappedObject:
    losses: List[str] = []
    for a in ad.attrib:
        if a not in _ALERT_ATTRS:
            _gap(f"attribute {a} is not modeled")
    st = ad.find("State")
    if st is None:
        raise MappingError("AlertDefinition has no State")
    if len(ad.findall("State")) > 1:
        raise MappingError("AlertDefinition with several States is not modeled")
    sev = (st.get("severity") or "").lower()
    if sev == "automatic":
        crit = "SYMPTOM_BASED"
    elif sev in SEVERITIES:
        crit = SEVERITIES[sev]
    else:
        raise MappingError(f"alert severity {st.get('severity')!r} is not modeled")
    impact = st.find("Impact")
    if impact is None:
        raise MappingError("alert State has no Impact")
    if impact.get("type", "badge") != "badge":
        raise MappingError(f"alert Impact type {impact.get('type')!r} is not modeled")
    if ad.get("description") is None:
        _gap("absent description attribute is not modeled (renders description=\"\")")
    y: Dict[str, object] = OrderedDict()
    y["name"] = ad.get("name", "")
    y["description"] = ad.get("description", "") or ""
    y["id"] = strip_prefix(ad.get("id", ""), "AlertDefinition-")
    y["adapter_kind"] = ad.get("adapterKind")
    y["resource_kind"] = ad.get("resourceKind")
    try:
        y["type"] = int(ad.get("type"))
        y["sub_type"] = int(ad.get("subType"))
    except (TypeError, ValueError):
        raise MappingError(f"alert type/subType {ad.get('type')!r}/{ad.get('subType')!r} are not integers")
    y["wait_cycles"] = int(ad.get("waitCycle", 1))
    y["cancel_cycles"] = int(ad.get("cancelCycle", 1))
    if ad.get("waitCycle") == "1" or ad.get("cancelCycle") == "1":
        _gap("an explicit waitCycle/cancelCycle of 1 is not modeled (1 is not written)")
    y["criticality"] = crit
    y["impact"] = OrderedDict(badge=(impact.get("key") or "").upper())
    if ad.get("disableInBasePolicy") == "true":
        y["disable_in_base_policy"] = True
    wrapper = st.find("SymptomSets")
    set_els = list(wrapper) if wrapper is not None else st.findall("SymptomSet")
    for child in st:
        if child.tag not in ("SymptomSets", "SymptomSet", "Impact", "Recommendations"):
            _gap(f"State element {child.tag} is not modeled")
    sets = []
    for i, ss in enumerate(set_els):
        if ss.tag != "SymptomSet":
            raise MappingError(f"symptom set {i}: element {ss.tag} is not modeled")
        if ss.get("negateCondition") is not None:
            raise MappingError(
                f"symptom set {i}: negateCondition is not modeled",
                gap=toolset_gap("SymptomSet negateCondition in the alert YAML",
                                '<SymptomSet negateCondition="true" .../>',
                                "convert the alert definition faithfully",
                                "add a negate: field to symptom sets in alerts/loader.py and render it"))
        agg = ss.get("aggregation")
        s: Dict[str, object] = OrderedDict()
        s["defined_on"] = (ss.get("applyOn") or "self").upper()
        s["operator"] = "ALL" if ss.get("operator", "and") == "and" else "ANY"
        if agg is not None:
            if agg in ("any", "all") and ss.get("aggregationOperator") is None and ss.get("value") is None:
                s["threshold_type"] = agg.upper()
            else:
                raise MappingError(
                    f"symptom set {i}: aggregation {agg!r} with aggregationOperator/value is not modeled",
                    gap=toolset_gap("SymptomSet aggregationOperator (COUNT/PERCENT thresholds) on the XML path",
                                    '<SymptomSet aggregation="percent" aggregationOperator="&gt;=" value="25.0" .../>',
                                    "convert the alert definition faithfully",
                                    "add threshold_operator to symptom sets and render aggregationOperator/value"))
        for a in ss.attrib:
            if a not in ("applyOn", "operator", "ref", "aggregation"):
                _gap(f"symptom set {i}: attribute {a} is not modeled")
        refs = [ss.get("ref")] if ss.get("ref") else [x.get("ref") for x in ss.findall("Symptom")]
        for x in ss.findall("Symptom"):
            if set(x.attrib) - {"ref"}:
                raise MappingError(f"symptom set {i}: Symptom attributes {sorted(set(x.attrib) - {'ref'})} are not modeled")
        s["symptoms"] = [OrderedDict(name=Ref("symptom", r, form="name", raw_ok=False, where=f"symptom set {i}"))
                         for r in refs]
        sets.append(s)
    if not sets:
        raise MappingError("alert has no symptom set")
    y["symptom_sets"] = OrderedDict(
        operator="ALL" if wrapper is None or wrapper.get("operator", "and") == "and" else "ANY", sets=sets)
    if wrapper is not None and len(set_els) < 2:
        _gap("a SymptomSets wrapper around one set is not modeled (one set renders without it)")
    if wrapper is None and len(set_els) >= 2:
        _gap("several SymptomSet elements without a SymptomSets wrapper are not modeled")
    rr = st.find("Recommendations")
    if rr is not None:
        recs = []
        prios = []
        for r in rr:
            prios.append(int(r.get("priority", 1)))
            recs.append(OrderedDict(name=Ref("recommendation", r.get("ref"), form="name", raw_ok=False,
                                             where="recommendations"),
                                    priority=int(r.get("priority", 1))))
        if prios != sorted(prios):
            _gap("recommendations out of priority order are not modeled (rendered sorted)")
        y["recommendations"] = recs
    return MappedObject("alert", y, losses=losses)


def _gap(msg: str) -> None:
    """Nothing in these types is documented as not modeled: every feature
    the schema cannot carry stops the object with a TOOLSET GAP."""
    loss_or_gap([], msg, "alert content")
