"""Exact comparison of a source object with its factory render.

Both sides are reduced to their flat form (``flat``: ``{path: value}``,
every attribute, text, key and list position of the object) and compared
key by key. A key on one side only is always a difference; values are
compared verbatim, whitespace included.

What the comparison does not see is only what the flat forms remove,
each counted by class in ``Comparison.set_aside`` (the ids the product
renumbers, server metadata; ``flat`` module docstring), plus two
equivalences that are counted too when they decide a comparison:

- **number spelling**: an XML value ``"70"`` equals ``"70.0"`` when both
  are plain decimal numbers, and a JSON ``1`` equals ``1.0`` (a JSON string
  is never equal to a number, and ``true`` is never ``1``);
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
import re
from collections import Counter
from dataclasses import dataclass, field
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


def same(a, b, xml: bool, sa: Optional[Counter] = None) -> bool:
    """Value equality of two leaves (see the module docstring)."""
    if isinstance(a, _EmptyMarker) != isinstance(b, _EmptyMarker):
        return False
    if type(a) is bool or type(b) is bool:
        return type(a) is type(b) and a == b
    if a == b and type(a) is type(b):
        return True
    num = (int, float)
    if isinstance(a, num) and isinstance(b, num):
        if float(a) == float(b):
            if sa is not None:
                sa[NUMBER_SPELLING] += 1
            return True
        return False
    if xml and isinstance(a, str) and isinstance(b, str) and _DECIMAL.match(a) and _DECIMAL.match(b):
        try:
            if float(a) == float(b):
                if sa is not None:
                    sa[NUMBER_SPELLING] += 1
                return True
        except ValueError:
            return False
    return False


def diff_flat(a: Leaves, b: Leaves, out: Comparison, xml: bool) -> None:
    """``a`` is the expected (source) side, ``b`` the render."""
    for k in sorted(set(a) | set(b)):
        out.fields += 1
        if k not in b:
            out.differences.append(Difference(k, "missing", _short(a[k])))
        elif k not in a:
            out.differences.append(Difference(k, "extra", _short(b[k])))
        elif not same(a[k], b[k], xml, out.set_aside):
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
