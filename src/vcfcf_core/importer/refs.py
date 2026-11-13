"""Cross-reference placeholders the mappers leave in a YAML tree.

A mapper does not know yet whether the object a reference points at is in
the conversion set, dropped, or product-shipped, nor what its final name and
id are (``--naming``, ``--rename``, ``--ids``). It leaves a :class:`Ref` (or
a :class:`NavRef`, :class:`FormulaRef`) in the tree, and
``convert.resolve_refs`` replaces each with the factory form:

- in the set: by NAME (the cross-reference convention);
- not in the set, or dropped: by raw id, where the schema has a raw-id form;
- otherwise the object fails with the reason (no silent downgrade).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class UnresolvedReference(Exception):
    """A reference the schema cannot express for this target."""


@dataclass
class Ref:
    """A reference to one object.

    ``form`` decides the factory spelling:

    - ``name``: the bare name (dashboard View widget ``view:``, alert
      ``symptoms[].name``, ``recommendations[].name``); a raw id when the
      target is outside the set and ``raw_ok``.
    - ``sm_column``: ``supermetric:"<name>"``; outside the set the wire key
      ``Super Metric|sm_<id>`` when ``raw_ok``.

    ``external_key``: when the target is outside the set, the dict key to
    use instead of the one the Ref sits under (a report section's
    ``view:`` becomes ``view_id:``).
    """

    type: str
    id: str
    form: str = "name"
    raw_ok: bool = True
    external_key: Optional[str] = None
    where: str = ""


@dataclass
class NavRef:
    """A Dashboard Navigation entry: target dashboard plus receiving widgets.

    In the set: ``{dashboard: <name>, widgets: [<local ids>]}``. Outside it:
    ``{dashboard_id: <id>, widget_ids: [<raw widget ids>]}``.
    """

    dashboard_id: str
    widget_ids: List[str] = field(default_factory=list)
    label: Optional[str] = None


@dataclass
class FormulaRef:
    """A super metric formula whose ``sm_<uuid>`` tokens name other super
    metrics: in the set they become ``@supermetric:"<name>"``; outside it
    the raw token stays (it must exist on the target)."""

    text: str


def walk_refs(tree, found: Optional[list] = None) -> list:
    """Every placeholder in ``tree`` (dicts, lists, scalars)."""
    if found is None:
        found = []
    if isinstance(tree, (Ref, NavRef, FormulaRef)):
        found.append(tree)
    elif isinstance(tree, dict):
        for v in tree.values():
            walk_refs(v, found)
    elif isinstance(tree, list):
        for v in tree:
            walk_refs(v, found)
    return found
