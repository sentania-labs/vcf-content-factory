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


@dataclass(frozen=True)
class Mark:
    """One difference a recorded loss or a target deviation explains.

    ``path``: the exact flat path (``flat`` module grammar). ``kind``:
    ``missing`` (source only), ``extra`` (render only), ``value`` or
    ``any``. ``subtree``: every key below ``path`` too (a dropped or forced
    element or object); with ``empty_only`` a forced subtree is accepted
    only where its leaves are empty values (``null``, ``""``, ``false``,
    ``0``, ``[]``, ``{}``), so a forced default cannot hide content."""

    path: str
    kind: str
    subtree: bool = False
    empty_only: bool = False

    def matches(self, d) -> bool:
        if self.kind != "any" and d.kind != self.kind:
            return False
        if not (under(d.path, self.path) if self.subtree else d.path == self.path):
            return False
        if self.empty_only:
            return d.detail in ("null", '""', "false", "0", '"' + EMPTY_LIST + '"', '"' + EMPTY_DICT + '"')
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
