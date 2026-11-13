"""Super metric JSON -> factory super metric YAML.

``modificationTime`` and ``modifiedBy`` are server metadata the product
writes on export and overwrites on import; they are not carried and a
verification counts them as documented non-differences. A ``sm_<uuid>``
token in the formula naming a super metric in the conversion set becomes
``@supermetric:"<name>"`` (``refs.FormulaRef``). Formula whitespace
outside quoted string literals, which the bundle renderer collapses, is a
documented loss; whitespace it would change inside a literal is a GAP.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List

from . import flat as _flat
from .accounting import account
from .model import (Loss, MappedObject, MappingError, Mark, collapse_ws, documented_loss, gap_error,
                    ws_outside_literals_only)
from .refs import FormulaRef

SERVER_METADATA = ("modificationTime", "modifiedBy")
_KNOWN = {"id", "name", "formula", "description", "unitId", "resourceKinds"} | set(SERVER_METADATA)


def map_supermetric(sid: str, sm: dict, location: str) -> MappedObject:
    losses: List[Loss] = []
    for k in sm:
        if k not in _KNOWN:
            _gap(f"key {k} is not modeled")
    if not sm.get("formula"):
        raise MappingError("super metric without a formula")
    if not isinstance(sm["formula"], str):
        _gap("formula that is not a string")
    if collapse_ws(sm["formula"]) != sm["formula"]:
        # The bundle renderer collapses whitespace runs in a formula
        # (packaging.assembly._render_supermetrics_dict). Outside quoted
        # string literals that is formatting (a documented loss, accepted
        # only where the render is exactly the collapsed source); inside a
        # literal (a where clause's value) it would ship changed: a GAP.
        if not ws_outside_literals_only(sm["formula"]):
            _gap("formula whitespace the renderer collapses inside a quoted string literal (or quotes that "
                 "cannot be delimited: unbalanced, or a backslash)")
        documented_loss(losses, "formula whitespace outside string literals",
                        "formula whitespace outside string literals is not modeled (the bundle renderer collapses "
                        "line breaks, tabs and repeated spaces; supermetric_authoring.md §Formula whitespace)",
                        [Mark("supermetric.formula", "value", cond="formula whitespace outside literals only")])
    y: Dict[str, object] = OrderedDict()
    y["id"] = sid
    y["name"] = sm.get("name", "")
    y["formula"] = FormulaRef(str(sm["formula"]))
    y["description"] = sm.get("description", "") or ""
    if not isinstance(y["description"], str):
        _gap("description that is not a string")
    # Surrounding whitespace the loader strips: accounting.STRIPPED_TEXT.
    y["unit_id"] = sm.get("unitId", "") or ""
    rks = []
    for r in sm.get("resourceKinds") or []:
        if not isinstance(r, dict) or set(r) - {"resourceKindKey", "adapterKindKey"}:
            _gap(f"resourceKinds entry {r!r} is not modeled")
            continue
        rks.append(OrderedDict(resource_kind_key=r.get("resourceKindKey"), adapter_kind_key=r.get("adapterKindKey")))
    y["resource_kinds"] = rks
    account("supermetric", _flat.flatten_supermetric(sm), losses)
    return MappedObject("supermetric", y, losses=losses, source_name=y["name"])


def _gap(msg: str) -> None:
    """Nothing in these types is documented as not modeled: every feature
    the schema cannot carry stops the object with a TOOLSET GAP."""
    raise gap_error(msg, "super metric")
