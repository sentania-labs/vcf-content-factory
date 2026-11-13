"""Result types shared by the per-type mappers and the conversion plan."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class MappingError(Exception):
    """The source object cannot be converted; the message is the reason.

    ``gap`` is set when the reason is a missing schema field (reported in
    the TOOLSET GAP format)."""

    def __init__(self, msg: str, gap: Optional[Dict[str, str]] = None):
        super().__init__(msg)
        self.gap = gap


@dataclass
class MappedObject:
    """One source object mapped to a YAML tree (with placeholders).

    ``losses``: source features the schema cannot express (the object still
    converts; each is listed). ``notes``: information for the caller that is
    not a loss (a reference to a super metric outside the set, a widget type
    that needs a newer product).
    """

    type: str
    yaml: Dict[str, object]
    losses: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    #: Extra YAML documents emitted alongside (none today).
    extra: List["MappedObject"] = field(default_factory=list)


def toolset_gap(what: str, repro: str, needed: str, fix: str) -> Dict[str, str]:
    return {"what": what, "minimum repro": repro, "needed to satisfy": needed, "suggested fix": fix}


#: Source features the fidelity docs list as deliberately not modeled
#: (view_fidelity_wire_format.md, template_fidelity_wire_format.md and
#: dashboard_fidelity_wire_format.md, each §Not modeled). An object with one
#: of these converts and the loss is listed; any other feature the schema
#: cannot carry stops the object with a TOOLSET GAP (no data is dropped
#: silently, none is invented).
DOCUMENTED_NOT_MODELED = {
    # loss message fragment: regex on the verify difference path it explains
    "localizationKey": r"Title@|Description@|localizationKey",   # DEF-018
    "empty preferredUnitId": r"preferredUnitId",                  # view doc §Not modeled
    "buckets-control on a non-distribution view": r"buckets-control",
    "subject filter keys ['conditionId']": r"SubjectType",
    "metricValue.values": r"SubjectType",
    "different filters per SubjectType": r"SubjectType",
    "Property startSubUnit": r"time-interval-selector",
    "element BlacklistResourceKind": r"\.Other",
    "Property includeNotExistingResources": r"includeNotExistingResources",
    "Property cellLink": r"cellLink",
    "Property related": r"related",                               # related-object columns
    "Property isRelatedMetricAProperty": r"isRelatedMetricAProperty",
    "objectType 'POLICY'": r"objectType",
    "absolute-date time range": r"\.states",                       # dashboard doc §Dashboard level
}


def is_documented_loss(msg: str) -> bool:
    return any(p in msg for p in DOCUMENTED_NOT_MODELED)


def loss_or_gap(losses: List[str], msg: str, type_: str) -> None:
    """Record a documented loss, or stop the object with a TOOLSET GAP."""
    if is_documented_loss(msg):
        if msg not in losses:
            losses.append(msg)
        return
    raise MappingError(
        f"{msg} (the {type_} YAML cannot carry it)",
        gap=toolset_gap(
            f"{type_} YAML: {msg}",
            f"a source {type_} with this shape",
            f"convert the {type_} without dropping or changing data",
            f"add a field (or an omit: entry) to the {type_} schema and renderer, with the product "
            f"export as evidence, or document it as not modeled",
        ),
    )


def loss_path_patterns(losses: List[str]) -> List[str]:
    """The difference-path regexes the documented losses of one object explain."""
    return [rx for frag, rx in DOCUMENTED_NOT_MODELED.items() if any(frag in m for m in losses)]
