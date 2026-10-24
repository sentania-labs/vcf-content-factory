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
#: Intermediate, first read only: phase 2 pending and every adapter kind it
#: waits on is installed. Often still running right after an import, but
#: NOT reliably transient: the 8.18.7 corpus export
#: (``scott-8.18.7-2026-09-14.zip``) has a dashboard incomplete for 19 days
#: with all four of its adapter kinds installed. Callers re-check and turn
#: whatever is still settling into :data:`INCOMPLETE` via
#: :func:`finalize_statuses`; it is never reported as fine.
SETTLING = "settling"
#: Final: still incomplete after the re-check (or with no re-check), every
#: pending adapter kind installed or unknown. Reported, naming the pending
#: adapter kinds and the ``entryKeys.resource`` names.
INCOMPLETE = "incomplete"
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
    #: ``entryKeys.resource[].name``: specific resources phase 2 must find.
    pending_resources: List[str] = field(default_factory=list)
    #: Seconds between the first read and the read this status came from.
    checked_after_s: int = 0
    #: False when the target's adapter kinds could not be read, so "every
    #: pending adapter kind is installed" is unknown rather than true.
    adapter_kinds_known: bool = True


def pending_resource_names(dashboard: Mapping) -> List[str]:
    """Names in a dashboard's ``entryKeys.resource`` list (order kept, unique).

    These are specific resources (e.g. "License Usage", "NSX World") the
    dashboard binds to; phase 2 must resolve each on the target.
    """
    entry_keys = dashboard.get("entryKeys")
    if not isinstance(entry_keys, Mapping):
        return []
    names: List[str] = []
    for item in entry_keys.get("resource") or []:
        if isinstance(item, Mapping):
            n = str(item.get("name") or "").strip()
            if n and n not in names:
                names.append(n)
    return names


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
            pending_resources=pending_resource_names(d),
            adapter_kinds_known=installed is not None,
        ))
    return out


def finalize_statuses(
    statuses: Iterable[MaterializationStatus], checked_after_s: int
) -> List[MaterializationStatus]:
    """Turn every remaining SETTLING into INCOMPLETE, stamping the wait.

    Call this on the last read (after the re-check, or on the only read when
    no re-check runs). A dashboard is never reported as fine merely because
    every adapter it waits on is installed.
    """
    out: List[MaterializationStatus] = []
    for st in statuses:
        st.checked_after_s = int(checked_after_s)
        if st.state == SETTLING:
            st.state = INCOMPLETE
        out.append(st)
    return out


def _quoted(names: Iterable[str]) -> str:
    return ", ".join(f"'{n}'" for n in names)


def describe_status(status: MaterializationStatus) -> str:
    """One operator-facing sentence for a non-complete status ("" if complete)."""
    resources = (
        f" It also binds the resources {_quoted(status.pending_resources)}."
        if status.pending_resources else ""
    )
    if status.state == STALLED:
        kinds = ", ".join(status.missing_adapter_kinds)
        verb = "is" if len(status.missing_adapter_kinds) == 1 else "are"
        return (
            f"dashboard '{status.name}' is installed but cannot finish "
            f"building: it is waiting on {kinds}, which {verb} not installed "
            f"on this instance. Its widgets that use those resource kinds "
            f"stay empty until the adapter is installed; re-importing does "
            f"not help.{resources}"
        )
    if status.state in (INCOMPLETE, SETTLING):
        kinds = ", ".join(status.pending_adapter_kinds) or "(none named)"
        res = (
            f" and the resources {_quoted(status.pending_resources)}"
            if status.pending_resources else ""
        )
        installed = (
            "Every adapter kind is installed, so it may still finish"
            if status.adapter_kinds_known else
            "The installed adapter kinds could not be read, so a missing "
            "adapter is not ruled out; it may still finish"
        )
        return (
            f"dashboard '{status.name}' had not finished building "
            f"{status.checked_after_s} s after the import. It waits on the "
            f"adapter kinds {kinds}{res}. {installed} (the background pass "
            f"can take about 20 minutes; opening it once in the UI is "
            f"faster), but it does not always: a factory dashboard stayed "
            f"incomplete for 19 days with every adapter installed. If it is "
            f"still incomplete later, check that the named resources exist "
            f"on this instance."
        )
    if status.state == ABSENT:
        return (
            f"dashboard '{status.name}' ({status.id}) was in the import but is "
            f"not on the instance afterwards. The importer can drop a whole "
            f"dashboard silently (for example a widget type this Ops build "
            f"lacks); check the instance."
        )
    return ""
