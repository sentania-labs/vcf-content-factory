"""Exact comparison of a source object with its factory render.

Both sides are reduced to their flat form (``flat``: ``{path: value}``,
every attribute, text, key and list position of the object) and compared
key by key. A key on one side only is always a difference; values are
compared verbatim, whitespace included.

What the comparison does not see is only what the flat forms remove,
each counted by class in ``Comparison.set_aside`` (the ids the product
renumbers, server metadata; ``flat`` module docstring), plus two
equivalences that are counted too when they decide a comparison:

- **number spelling**, exact (``Decimal``, never ``float``): a JSON ``1``
  equals ``1.0`` (a JSON string is never equal to a number, and ``true`` is
  never ``1``); an XML value ``"70"`` equals ``"70.0"`` only at a key that is
  numeric by its semantics (:func:`xml_numeric`: a view bound on a column
  that is not a string attribute, bucket, count and size Properties, a
  numeric filter operand, a symptom condition whose ``valueType`` is
  numeric, cycle counts and priorities). Everywhere else an XML value is
  compared as the exact string (``"01"`` is not ``"1"``);
- **order** where the product keys an element by identity rather than
  position: SubjectType, SubjectsGroupBy and Usage elements of a view,
  Controls by type, Properties by name, JSON object keys, dashboard and
  widget ``states`` by key. Every other list is compared by position.

``Difference.kind`` is ``missing`` (on the source only), ``extra`` (on
the render only) or ``value``. A caller that sets a difference aside (a
recorded loss, a target-version deviation) matches it by exact path and
kind, and where the mark names a condition by the two values
(``model.Mark``); nothing here sets one aside.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, NamedTuple, Optional

from . import flat as _flat
from .flat import Leaves, _EmptyMarker

UUID = _flat.UUID
_DECIMAL = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
NUMBER_SPELLING = "number spelling (equal numbers written differently)"


class Difference(NamedTuple):
    """``a`` / ``b``: the two raw values of a ``value`` difference (a mark
    with a condition tests them; ``detail`` is the printed form)."""

    path: str
    kind: str      # missing | extra | value
    detail: str = ""
    a: object = None
    b: object = None

    def __str__(self) -> str:
        return f"{self.path}: {self.kind}{(' ' + self.detail) if self.detail else ''}"


@dataclass
class Comparison:
    """The result of comparing one object."""

    fields: int = 0
    differences: List[Difference] = field(default_factory=list)
    #: keys the flat forms removed (renumbered ids, server metadata) and
    #: equivalences that decided a comparison, by class
    set_aside: Counter = field(default_factory=Counter)

    @property
    def identical(self) -> bool:
        return not self.differences


def _short(v) -> str:
    return json.dumps(v, default=str)[:80]


def _exact(v) -> Optional[Decimal]:
    """A JSON number or a decimal string as an exact ``Decimal`` (a float by
    its shortest repr, which is the value it holds as written)."""
    try:
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return Decimal(v)
        if isinstance(v, float):
            return Decimal(repr(v)) if math.isfinite(v) else None
        if isinstance(v, str) and _DECIMAL.match(v):
            return Decimal(v)
    except InvalidOperation:
        return None
    return None


def same(a, b, xml: bool, sa: Optional[Counter] = None, numeric: bool = False) -> bool:
    """Value equality of two leaves (see the module docstring). ``numeric``:
    the key is numeric by its semantics (:func:`xml_numeric`), so two XML
    strings spelling one number are equal."""
    if isinstance(a, _EmptyMarker) != isinstance(b, _EmptyMarker):
        return False
    if type(a) is bool or type(b) is bool:
        return type(a) is type(b) and a == b
    if a == b and type(a) is type(b):
        return True
    num = (int, float)
    if isinstance(a, num) and isinstance(b, num):
        da, db = _exact(a), _exact(b)
        if da is not None and da == db:
            if sa is not None:
                sa[NUMBER_SPELLING] += 1
            return True
        return False
    if xml and numeric and isinstance(a, str) and isinstance(b, str):
        da, db = _exact(a), _exact(b)
        if da is not None and da == db:
            if sa is not None:
                sa[NUMBER_SPELLING] += 1
            return True
    return False


_COLPROP = r"ViewDef/Controls/Control\{[^}]*\}/Property\{(?:attributeInfos|summaryInfos|distributionAdditionalColumns)\}/List/Item\[\d+\]/Value"
_VIEW_BOUND = re.compile(_COLPROP + r"/Property\{(?:yellowBound|orangeBound|redBound)\}@value")
_VIEW_NUMERIC = re.compile(
    "(?:" + _COLPROP + r"/Property\{(?:rollUpCount|percentile|forecastDays|startingOnCount)\}@value"
    r"|" + _COLPROP + r"/Property\{attributeIndexes\}/List/Item\[\d+\]@value"
    r"|ViewDef/Controls/Control\{time-interval-selector\}/Property\{count\}@value"
    r"|ViewDef/Controls/Control\{buckets-control\}/Property\{(?:bucketCount|minValue|maxValue)\}@value"
    r"|ViewDef/Controls/Control\{buckets-control\}/Property\{bucketInfos\}/List/Item\[\d+\]/Value/"
    r"Property\{(?:startValue|endValue)\}@value"
    r"|ViewDef/Controls/Control\{metadata\}/Property\{(?:maxPointsCount|listTopResultSize)\}@value"
    r"|ViewDef/Controls/Control\{pagination-control\}/Property\{(?:start|size)\}@value"
    r"|(?:Symptom|Alert)Definition@(?:waitCycle|cancelCycle)|AlertDefinition@(?:type|subType)"
    r"|AlertDefinition/State/Recommendations/Recommendation\[\d+\]@priority)")
_FILTER_VALUE = re.compile(r"(ViewDef/SubjectType\{[^}]*\}(?:~\d+)?@filter\[\d+\]\[\d+\]\.metricValue)\.value")
_COND_VALUE = re.compile(r"(SymptomDefinition/State/Condition\[\d+\])@value")


def xml_numeric(path: str, leaves: Leaves) -> bool:
    """True when the XML key ``path`` is numeric by its semantics, read from
    the object's own flat form ``leaves`` (the source side): a column bound
    unless the column is a string attribute, the count / size / bucket /
    roll-up Properties, a filter operand that is not a string metric, a
    symptom condition value whose ``valueType`` is numeric, cycle counts,
    alert type and sub-type, recommendation priorities."""
    if _VIEW_NUMERIC.fullmatch(path):
        return True
    if _VIEW_BOUND.fullmatch(path):
        return leaves.get(path.rsplit("/", 1)[0] + "/Property{isStringAttribute}@value") != "true"
    m = _FILTER_VALUE.fullmatch(path)
    if m:
        return leaves.get(m.group(1) + ".isStringMetric") is False
    m = _COND_VALUE.fullmatch(path)
    if m:
        return leaves.get(m.group(1) + "@valueType") == "numeric"
    return False


def diff_flat(a: Leaves, b: Leaves, out: Comparison, xml: bool) -> None:
    """``a`` is the expected (source) side, ``b`` the render. Which XML keys
    are numeric is read from ``a`` (:func:`xml_numeric`)."""
    for k in sorted(set(a) | set(b)):
        out.fields += 1
        if k not in b:
            out.differences.append(Difference(k, "missing", _short(a[k])))
        elif k not in a:
            out.differences.append(Difference(k, "extra", _short(b[k])))
        elif not same(a[k], b[k], xml, out.set_aside, numeric=xml and xml_numeric(k, a)):
            out.differences.append(Difference(k, "value", f"{_short(a[k])} vs {_short(b[k])}", a[k], b[k]))


# ----------------------------------------------------------------- views
def compare_view(src_elem, rendered_elem) -> Comparison:
    out = Comparison()
    a = _flat.flatten_view(src_elem, out.set_aside)
    b = _flat.flatten_view(rendered_elem, Counter())
    diff_flat(a, b, out, xml=True)
    return out


# ------------------------------------------------------------ XML trees
def compare_xml(src_elem, rendered_elem) -> Comparison:
    """Report templates, alerts, symptoms, recommendations."""
    out = Comparison()
    diff_flat(_flat.flatten_plain_xml(src_elem, out.set_aside), _flat.flatten_plain_xml(rendered_elem, Counter()),
              out, xml=True)
    return out


# ------------------------------------------------------------ dashboards
def compare_dashboard(src_db: dict, src_entries: dict, rendered_env: dict, rendered_db: dict,
                      widget_idmap: Dict[str, str], id_rewrites: Dict[str, str]) -> Comparison:
    """``widget_idmap``: source widget id -> rendered widget id, for widgets
    of other dashboards a navigation names (this dashboard's own widgets
    are compared by position). ``id_rewrites``: intended object id changes
    (old -> new)."""
    out = Comparison()
    idmap = dict(id_rewrites)
    idmap.update(widget_idmap)
    a = _flat.flatten_dashboard(src_db, src_entries, idmap, out.set_aside)
    b = _flat.flatten_dashboard(rendered_db, rendered_env.get("entries") or {}, {}, Counter())
    diff_flat(a, b, out, xml=False)
    return out


# ---------------------------------------------------------- super metrics
def compare_supermetric(src: dict, rendered: dict) -> Comparison:
    out = Comparison()
    diff_flat(_flat.flatten_supermetric(src, out.set_aside), _flat.flatten_supermetric(rendered, Counter()),
              out, xml=False)
    return out


# -------------------------------------------------------------- duplicates
def source_leaves(obj, set_aside: Optional[Counter] = None) -> Leaves:
    """The flat form of a source object (``inputs.SourceObject``)."""
    if obj.type == "view":
        return _flat.flatten_view(obj.payload, set_aside)
    if obj.type in ("report", "alert", "symptom", "recommendation"):
        return _flat.flatten_plain_xml(obj.payload, set_aside)
    if obj.type == "dashboard":
        return _flat.flatten_dashboard(obj.payload, obj.context.get("entries") or {}, {}, set_aside)
    if obj.type == "supermetric":
        return _flat.flatten_supermetric(obj.payload, set_aside)
    raise ValueError(f"no flat form for {obj.type}")


def compare_copies(first, other) -> Comparison:
    """Two source copies of one id, compared exactly as a source is compared
    with its render (the same flat form and equality): duplicate merging
    uses this, so copies merge only when the comparator finds no
    difference between them."""
    out = Comparison()
    diff_flat(source_leaves(first, out.set_aside), source_leaves(other, Counter()), out,
              xml=first.type not in ("dashboard", "supermetric"))
    return out
