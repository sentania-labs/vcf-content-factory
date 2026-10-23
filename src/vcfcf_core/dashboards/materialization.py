"""Classify imported dashboards by phase-2 materialization state (issue #167).

A content import materializes a dashboard in two phases. Phase 1, inside
the import operation, writes the record and parks the bundle's portability
tokens in ``entryKeys`` with ``importComplete: false``. Phase 2 runs later,
resolves the tokens to instance-local ids, clears ``entryKeys`` and sets
``importComplete: true``. Phase 2 cannot resolve a resource kind whose
adapter is not installed, and then the dashboard stays half-built for good
while the import envelope still reports FINISHED.

Evidence and wire shape:
``knowledge/context/api-surface/dashboard_import_two_phase_materialization.md``.
In a DASHBOARDS export each dashboard record carries ``importComplete`` and
``entryKeys``; ``entryKeys`` is null once phase 2 is done, otherwise
``{"resourceKind": [{"resourceKindKey", "internalId", "adapterKindKey"}],
"resource": [{..., "adapterKindKey", "name"}], "uuid": ...}``.

Pure functions: dashboard dicts and adapter-kind keys in, statuses out. The
live export and the adapter-kind read live in ``vcfcf_dashboards.client``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional

#: Phase 2 done: nothing to say.
COMPLETE = "complete"
#: Phase 2 pending and every adapter kind it waits on is installed: normal
#: right after an import, completes on its own (minutes, or on first open).
SETTLING = "settling"
#: Phase 2 pending on at least one adapter kind the target does not have:
#: it will never complete until that adapter is installed.
STALLED = "stalled"
#: The dashboard was in the import but is not in the export at all.
ABSENT = "absent"


@dataclass
class MaterializationStatus:
    id: str
    name: str
    state: str
    pending_adapter_kinds: List[str] = field(default_factory=list)
    missing_adapter_kinds: List[str] = field(default_factory=list)


def pending_adapter_kinds(dashboard: Mapping) -> List[str]:
    """Adapter kinds named in a dashboard's ``entryKeys`` (sorted, unique).

    Empty when ``entryKeys`` is null or carries no ``adapterKindKey``.
    """
    entry_keys = dashboard.get("entryKeys")
    if not isinstance(entry_keys, Mapping):
        return []
    kinds = set()
    for value in entry_keys.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, Mapping):
                ak = str(item.get("adapterKindKey") or "").strip()
                if ak:
                    kinds.add(ak)
    return sorted(kinds)


def is_incomplete(dashboard: Mapping) -> bool:
    """True while phase 2 has not finished.

    ``entryKeys`` non-null is the primary signal (it was non-null on exactly
    the incomplete dashboards across the recorded export); an explicit
    ``importComplete: false`` counts too.
    """
    return dashboard.get("entryKeys") is not None or dashboard.get("importComplete") is False


def classify_dashboards(
    exported: Iterable[Mapping],
    wanted: Mapping[str, str],
    installed_adapter_kinds: Optional[Iterable[str]],
) -> List[MaterializationStatus]:
    """One status per dashboard in ``wanted`` (``{id: display name}``).

    ``exported`` is the dashboard records from a DASHBOARDS export.
    ``installed_adapter_kinds`` is the target's adapter-kind keys, or None
    when they could not be read; then an incomplete dashboard is reported as
    settling with its pending kinds, never as stalled on a guess.
    Ids compare case-insensitively.
    """
    by_id = {}
    for d in exported:
        did = str(d.get("id") or "").strip().lower()
        if did:
            by_id[did] = d
    installed = (
        {str(k) for k in installed_adapter_kinds}
        if installed_adapter_kinds is not None else None
    )
    out: List[MaterializationStatus] = []
    for raw_id, name in wanted.items():
        did = str(raw_id).strip().lower()
        d = by_id.get(did)
        if d is None:
            out.append(MaterializationStatus(id=did, name=name, state=ABSENT))
            continue
        if not is_incomplete(d):
            out.append(MaterializationStatus(id=did, name=name, state=COMPLETE))
            continue
        pending = pending_adapter_kinds(d)
        missing = [k for k in pending if installed is not None and k not in installed]
        out.append(MaterializationStatus(
            id=did, name=name,
            state=STALLED if missing else SETTLING,
            pending_adapter_kinds=pending,
            missing_adapter_kinds=missing,
        ))
    return out


def describe_status(status: MaterializationStatus) -> str:
    """One operator-facing sentence for a non-complete status ("" if complete)."""
    if status.state == STALLED:
        kinds = ", ".join(status.missing_adapter_kinds)
        verb = "is" if len(status.missing_adapter_kinds) == 1 else "are"
        return (
            f"dashboard '{status.name}' is installed but cannot finish "
            f"building: it is waiting on {kinds}, which {verb} not installed "
            f"on this instance. Its widgets that use those resource kinds "
            f"stay empty until the adapter is installed; re-importing does "
            f"not help."
        )
    if status.state == SETTLING:
        return (
            f"dashboard '{status.name}' is still finishing its import (normal "
            f"for some minutes after an import; opening it once in the UI "
            f"speeds it up)."
        )
    if status.state == ABSENT:
        return (
            f"dashboard '{status.name}' ({status.id}) was in the import but is "
            f"not on the instance afterwards. The importer can drop a whole "
            f"dashboard silently (for example a widget type this Ops build "
            f"lacks); check the instance."
        )
    return ""
