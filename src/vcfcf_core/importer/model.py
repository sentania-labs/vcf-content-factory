"""Result types shared by the per-type mappers, the accounting and the plan.

A mapper classifies every source key it meets (``accounting`` module
docstring). Two of the classes are recorded here:

- a **loss** (:class:`Loss`): a source feature the fidelity docs list as
  deliberately not modeled. The object converts; the loss is listed per
  object with the exact flat path(s) it alters (:class:`Mark`), and a
  verification accepts a difference only at a recorded mark;
- a **gap** (:class:`MappingError` with ``gap``): anything else the schema
  cannot carry. The object stops, reported in the TOOLSET GAP format.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .flat import EMPTY_DICT, EMPTY_LIST, under


class MappingError(Exception):
    """The source object cannot be converted; the message is the reason.

    ``gap`` is set when the reason is a missing schema field (reported in
    the TOOLSET GAP format)."""

    def __init__(self, msg: str, gap: Optional[Dict[str, str]] = None):
        super().__init__(msg)
        self.gap = gap


_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')


def formula_literals(text: str) -> Optional[List[str]]:
    """The quoted string literals of a super metric formula, in order, or
    ``None`` when they cannot be told apart from the rest with certainty (an
    unbalanced quote, or a backslash that might escape one)."""
    if "\\" in text:
        return None
    lits = _QUOTED.findall(text)
    rest = _QUOTED.sub("", text)
    if '"' in rest or "'" in rest:
        return None
    return lits


def collapse_ws(text: str) -> str:
    """What ``packaging.assembly._render_supermetrics_dict`` writes for a formula."""
    return " ".join(text.split())


def ws_outside_literals_only(src: str) -> bool:
    """``src`` differs from its collapsed form, and only in whitespace outside
    its quoted string literals (every literal survives the collapse verbatim)."""
    if not isinstance(src, str):
        return False
    got = collapse_ws(src)
    lits = formula_literals(src)
    return got != src and lits is not None and formula_literals(got) == lits


def _cond_surrounding_ws(path: str, a, b) -> bool:
    """The render is the source with its leading and trailing whitespace
    stripped (what the loader does), nothing else."""
    return isinstance(a, str) and isinstance(b, str) and a != b and b == a.strip()


def _cond_formula_ws(path: str, a, b) -> bool:
    return isinstance(b, str) and ws_outside_literals_only(a) and b == collapse_ws(a)


_UUID_FULL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _cond_own_widget_id(path: str, a, b) -> bool:
    """The source names a widget id that is none of this dashboard's widgets
    (in the flat form those are position tokens ``w<j>``, so it is still a
    raw id), and the render writes the widget's own token."""
    m = re.match(r"^widget\[(\d+):", path)
    return bool(m) and isinstance(a, str) and bool(_UUID_FULL.fullmatch(a)) and b == f"w{m.group(1)}"


#: Conditions a :class:`Mark` can require of a ``value`` difference, beyond
#: its path (``cond``): ``(path, source value, render value) -> bool``.
MARK_CONDITIONS = {
    "surrounding whitespace only": _cond_surrounding_ws,
    "formula whitespace outside literals only": _cond_formula_ws,
    "render writes the widget's own id": _cond_own_widget_id,
}


@dataclass(frozen=True)
class Mark:
    """One difference a recorded loss or a target deviation explains.

    ``path``: the exact flat path (``flat`` module grammar). ``kind``:
    ``missing`` (source only), ``extra`` (render only), ``value`` or
    ``any``. ``subtree``: every key below ``path`` too (a dropped or forced
    element or object); with ``empty_only`` a forced subtree is accepted
    only where its leaves are empty values (``null``, ``""``, ``false``,
    ``0``, ``[]``, ``{}``), so a forced default cannot hide content.
    ``cond``: a ``value`` difference is accepted only when the named
    :data:`MARK_CONDITIONS` entry holds for its two values (a description
    whose render is the source stripped, and nothing else)."""

    path: str
    kind: str
    subtree: bool = False
    empty_only: bool = False
    cond: Optional[str] = None

    def __post_init__(self):
        if self.cond is not None and (self.cond not in MARK_CONDITIONS or self.kind != "value"):
            raise ValueError(f"mark condition {self.cond!r} on a {self.kind!r} mark")

    def matches(self, d) -> bool:
        if self.kind != "any" and d.kind != self.kind:
            return False
        if not (under(d.path, self.path) if self.subtree else d.path == self.path):
            return False
        if self.empty_only:
            return d.detail in ("null", '""', "false", "0", '"' + EMPTY_LIST + '"', '"' + EMPTY_DICT + '"')
        if self.cond is not None:
            return MARK_CONDITIONS[self.cond](d.path, d.a, d.b)
        return True


@dataclass
class Loss:
    """A recorded, documented loss of one object."""

    cls: str
    text: str
    marks: List[Mark] = field(default_factory=list)

    def __str__(self) -> str:
        return self.text


@dataclass
class MappedObject:
    """One source object mapped to a YAML tree (with placeholders).

    ``losses``: documented not-modeled features (the object still converts;
    each is listed). ``notes``: information for the caller that is not a
    loss (a reference to a super metric outside the set, a widget type that
    needs a newer product). ``source_name``: the name exactly as the source
    has it (the YAML ``name`` is what the loader keeps)."""

    type: str
    yaml: Dict[str, object]
    losses: List[Loss] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    source_name: Optional[str] = None


def toolset_gap(what: str, repro: str, needed: str, fix: str) -> Dict[str, str]:
    return {"what": what, "minimum repro": repro, "needed to satisfy": needed, "suggested fix": fix}


#: Loss classes the fidelity docs list as deliberately not modeled, with the
#: doc that lists each. A source feature in one of these classes converts
#: and is listed as a LOSS; any other feature the schema cannot carry stops
#: the object with a TOOLSET GAP. Nothing is added here without the doc.
DOCUMENTED_NOT_MODELED: Dict[str, str] = {
    "Title/Description localizationKey":
        "template_fidelity_wire_format.md §Not modeled; DEF-018 (views)",
    "buckets-control on a list view": "view_fidelity_wire_format.md §Not modeled",
    "empty preferredUnitId": "view_fidelity_wire_format.md §Not modeled",
    "per-SubjectType filters that differ": "view_fidelity_wire_format.md §Not modeled",
    "filter values list": "view_fidelity_wire_format.md §Not modeled",
    "filter conditionId": "view_fidelity_wire_format.md §Not modeled",
    "startSubUnit": "view_fidelity_wire_format.md §Not modeled",
    "BlacklistResourceKind": "view_fidelity_wire_format.md §Not modeled",
    "includeNotExistingResources": "view_fidelity_wire_format.md §Not modeled",
    "cellLink": "view_fidelity_wire_format.md §Not modeled",
    "related-object column": "view_fidelity_wire_format.md §Not modeled",
    "objectType POLICY": "view_fidelity_wire_format.md §Not modeled",
    "per-column transformations on a trend view": "view_fidelity_wire_format.md §Not modeled",
    "Description surrounding whitespace":
        "view_fidelity_wire_format.md §Not modeled; template_fidelity_wire_format.md §Not modeled",
    "displayName localizationKey": "view_fidelity_wire_format.md §Not modeled",
    "second displayName in a column": "view_fidelity_wire_format.md §Not modeled",
    "Heatmap tab name surrounding whitespace": "dashboard_fidelity_wire_format.md §Per type, Heatmap",
    "config.widgetId naming no widget of the dashboard":
        "dashboard_fidelity_wire_format.md §Widget fields common to every type",
    "formula whitespace outside string literals": "supermetric_authoring.md §Formula whitespace",
    "adapterName": "dashboard_fidelity_wire_format.md §Dashboard level",
    "absolute-date time range": "dashboard_fidelity_wire_format.md §Dashboard level",
    "ext-element UI residue": "dashboard_fidelity_wire_format.md §Dashboard level",
    "navigation keyed by a widget not on the dashboard": "dashboard_fidelity_wire_format.md §Per type, Navigations",
}


def gap_error(msg: str, type_: str) -> MappingError:
    return MappingError(
        f"{msg} (the {type_} YAML cannot carry it)",
        gap=toolset_gap(
            f"{type_} YAML: {msg}",
            f"a source {type_} with this shape",
            f"convert the {type_} without dropping or changing data",
            f"add a field (or an omit: entry) to the {type_} schema and renderer, with the product "
            f"export as evidence, or document it as not modeled in the {type_} fidelity doc",
        ),
    )


def documented_loss(losses: List[Loss], cls: str, text: str, marks: List[Mark]) -> None:
    """Record a loss of a documented class at its exact marks."""
    if cls not in DOCUMENTED_NOT_MODELED:  # a programming error, not a source shape
        raise ValueError(f"{cls!r} is not a documented not-modeled class")
    for x in losses:
        if x.cls == cls and x.text == text:
            for m in marks:
                if m not in x.marks:
                    x.marks.append(m)
            return
    losses.append(Loss(cls, text, list(marks)))
