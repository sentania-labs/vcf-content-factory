"""Reverse parser: SM wire JSON -> SuperMetricDef dataclass.

Inverts the forward render path for super metric content received from
a live VCF Ops instance via GET /api/supermetrics/{id}.

Key transformation: rewrites ``sm_<uuid>`` tokens in the formula field to
``@supermetric:"<name>"`` by resolving each UUID via an additional GET call
(or from a pre-populated name cache).  The set of referenced SM UUIDs is
returned alongside the rewritten formula so the caller's dependency walker
can enqueue transitive SMs for extraction.

The SuperMetricDef dataclass produced here is compatible with loader.py's
contract (same fields, same validation logic).

Usage by vcfops_extractor:
    from vcfops_supermetrics.reverse import parse_sm_json, rewrite_formula

    sm_data = client.get_supermetric(uuid)
    rewritten_formula, referenced_uuids = rewrite_formula(
        sm_data["formula"],
        name_lookup=lambda uid: client.get_supermetric(uid)["name"],
    )
    sm_def = parse_sm_json(sm_data, rewritten_formula)
"""
from __future__ import annotations

import re
import warnings
from typing import Callable, Optional

from .loader import SuperMetricDef


# ---------------------------------------------------------------------------
# Formula UUID -> name rewriting
# ---------------------------------------------------------------------------

_SM_UUID_TOKEN_RE = re.compile(
    r"sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def rewrite_formula(
    formula: str,
    name_lookup: Callable[[str], Optional[str]],
) -> tuple[str, set[str]]:
    """Rewrite ``sm_<uuid>`` tokens in a formula to ``@supermetric:"<name>"``.

    Args:
        formula:     Raw formula string from the API.
        name_lookup: Callable that accepts a UUID string and returns the SM
                     name, or None if the UUID cannot be resolved.  The
                     caller is responsible for caching to avoid redundant
                     network calls.

    Returns:
        (rewritten_formula, set_of_referenced_sm_uuids)

    For each ``sm_<uuid>`` token:
    - If name_lookup returns a name, the token is replaced with
      ``@supermetric:"<name>"``.
    - If name_lookup returns None (unresolvable UUID), the raw token is
      kept and a UserWarning is emitted.  The UUID is still added to the
      returned set so the caller can decide how to handle it.
    """
    referenced_uuids: set[str] = set()
    result = formula

    def _replace(m: re.Match) -> str:
        uuid = m.group(1)
        referenced_uuids.add(uuid)
        name = name_lookup(uuid)
        if name:
            return f'@supermetric:"{name}"'
        warnings.warn(
            f"vcfops_supermetrics.reverse: could not resolve SM UUID {uuid} "
            "to a name; keeping raw token in formula",
            UserWarning,
            stacklevel=2,
        )
        return m.group(0)

    result = _SM_UUID_TOKEN_RE.sub(_replace, result)
    return result, referenced_uuids


# ---------------------------------------------------------------------------
# SM JSON -> SuperMetricDef
# ---------------------------------------------------------------------------

def parse_sm_json(
    sm_data: dict,
    rewritten_formula: Optional[str] = None,
) -> SuperMetricDef:
    """Parse a super metric dict from GET /api/supermetrics/{id} into a
    SuperMetricDef dataclass.

    Args:
        sm_data:           Dict from the API response.
        rewritten_formula: Pre-rewritten formula (UUID tokens replaced with
                           @supermetric:"name").  If None, the raw formula
                           from sm_data["formula"] is used verbatim (UUID
                           tokens preserved, which will fail validation).

    Returns:
        A SuperMetricDef.  Note: validate() is NOT called here — the caller
        should call it after any post-processing (e.g. after all SM names are
        resolved).

    Resource kinds are normalised to the loader's expected key names:
        {"resourceKindKey": ..., "adapterKindKey": ...}
    """
    sm_id = str(sm_data.get("id") or "").strip()
    name = str(sm_data.get("name") or "").strip()
    formula = rewritten_formula if rewritten_formula is not None else str(sm_data.get("formula") or "")
    description = str(sm_data.get("description") or "").strip()
    unit_id = str(sm_data.get("unitId") or "").strip()

    # Resource kinds — API returns {"resourceKindKey": ..., "adapterKindKey": ...}
    # or {"resourceKind": ..., "adapterKind": ...} depending on API version.
    raw_rks = sm_data.get("resourceKinds") or []
    resource_kinds: list[dict] = []
    for rk in raw_rks:
        if not isinstance(rk, dict):
            continue
        rk_key = (
            rk.get("resourceKindKey") or rk.get("resourceKind") or ""
        ).strip()
        ak_key = (
            rk.get("adapterKindKey") or rk.get("adapterKind") or "VMWARE"
        ).strip()
        if rk_key:
            resource_kinds.append({
                "resourceKindKey": rk_key,
                "adapterKindKey": ak_key,
            })

    return SuperMetricDef(
        id=sm_id,
        name=name,
        formula=formula,
        description=description,
        resource_kinds=resource_kinds or None,
        unit_id=unit_id,
    )
