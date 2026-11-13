"""Super metric JSON -> factory super metric YAML.

``modificationTime`` and ``modifiedBy`` are server metadata the product
writes on export and overwrites on import; they are not carried and a
verification counts them as documented non-differences. A ``sm_<uuid>``
token in the formula naming a super metric in the conversion set becomes
``@supermetric:"<name>"`` (``refs.FormulaRef``).
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List

from .model import MappedObject, MappingError, loss_or_gap
from .refs import FormulaRef

SERVER_METADATA = ("modificationTime", "modifiedBy")
_KNOWN = {"id", "name", "formula", "description", "unitId", "resourceKinds"} | set(SERVER_METADATA)


def map_supermetric(sid: str, sm: dict, location: str) -> MappedObject:
    losses: List[str] = []
    for k in sm:
        if k not in _KNOWN:
            _gap(f"key {k} is not modeled")
    if not sm.get("formula"):
        raise MappingError("super metric without a formula")
    y: Dict[str, object] = OrderedDict()
    y["id"] = sid
    y["name"] = sm.get("name", "")
    y["formula"] = FormulaRef(str(sm["formula"]))
    y["description"] = sm.get("description", "") or ""
    y["unit_id"] = sm.get("unitId", "") or ""
    rks = []
    for r in sm.get("resourceKinds") or []:
        if not isinstance(r, dict) or set(r) - {"resourceKindKey", "adapterKindKey"}:
            _gap(f"resourceKinds entry {r!r} is not modeled")
            continue
        rks.append(OrderedDict(resource_kind_key=r.get("resourceKindKey"), adapter_kind_key=r.get("adapterKindKey")))
    y["resource_kinds"] = rks
    return MappedObject("supermetric", y, losses=losses)


def _gap(msg: str) -> None:
    """Nothing in these types is documented as not modeled: every feature
    the schema cannot carry stops the object with a TOOLSET GAP."""
    loss_or_gap([], msg, "super metric")
