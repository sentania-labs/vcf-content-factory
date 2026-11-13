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

from . import flat as _flat
from .accounting import account
from .model import MappedObject, MappingError, gap_error
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
    if not isinstance(sm["formula"], str) or " ".join(sm["formula"].split()) != sm["formula"]:
        # The bundle renderer collapses whitespace runs in a formula
        # (packaging.assembly._render_supermetrics_dict), so this one would
        # ship changed.
        _gap("formula with whitespace the renderer collapses (line breaks, tabs or repeated spaces)")
    y: Dict[str, object] = OrderedDict()
    y["id"] = sid
    y["name"] = sm.get("name", "")
    y["formula"] = FormulaRef(str(sm["formula"]))
    y["description"] = sm.get("description", "") or ""
    if not isinstance(y["description"], str) or y["description"] != y["description"].strip():
        _gap("description with leading or trailing whitespace (the super metric loader strips it)")
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
