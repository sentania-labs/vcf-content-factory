"""Bind a `summary_for` dashboard to every listed resource kind's Summary tab.

This is the post-import route (content-zip installs cannot carry the
binding; a pak can, via ``content/dashboards/dashboards.properties``).
Everything here rides the undocumented Struts UI layer described in
knowledge/context/api-surface/summary_dashboard_assignment.md (the dated
2026-08-25 note there is the ground truth for the wire format):

- ``resourceKindId`` is computable offline:
  ``"0020" + "%02d" % len(AK) + AK + RK`` (validated against 363 kinds).
- Binding is COPY, not reference: the server materializes a template
  clone with its own UUID. On re-assign the server deletes the kind's
  previous copy in the same call, so the update story is simply "assign
  again"; there is no client-side template cleanup (and no template list
  or delete action exists on ``dashboard.action``).
- Unbind ("Use Default") goes through ``resetAssociations`` with the
  kind's own ``defaultTemplateName`` (per entry; the top-level value is
  the generic fallback).
- ``getSummaryTabId`` omits the ``tabId`` key when it is null; a missing
  key is treated as null everywhere here.
- The association call is sent in whichever request form the build reads
  (two maps on 9.1.1 and 9.2, one ``dashboardAssociations`` map on 9.0.2
  and 8.18; issue #260, ``VCFOpsUIClient.associate_resource_kind_dashboards``).
  9.0.2 answers ``getSummaryTabId`` without an ``isDashboard`` key, so a
  bound tab is read with ``summary_dashboard_tab``.
- A bind copies the source as it is right now. A source still building
  (``getDashboardList`` ``isLoading: true``) copies into a Summary template
  whose widgets are never resolved, so the Summary tab shows stock widgets
  for good (issue #200). A bind therefore refuses a source that is still
  building, or whose state the list does not report, and names its
  unfinished widgets; ``wait=True`` (``--wait``) polls every
  ``WAIT_POLL_S`` until it is built or ``wait_s`` is spent (issue #256).

Dashboard identity is the NAME (see id_guard.py): the installed
dashboard is resolved by name, never by the YAML id, because an import
under an existing name replaces the object and can leave the YAML id
pointing at nothing.

The client is injected (``ui``) so the flow is unit-testable with a fake;
``bind_summary(None, ..., dry_run=True)`` prints the planned map without
any session.

M2 row 2: the offline half (``resource_kind_id``, ``KindTarget``,
``BindPlan``, ``plan_bindings``, ``_find_kind_entry``,
``_default_template_name``) lives in ``vcfcf_core.dashboards.summary_bind``
and is re-exported here; this module keeps everything that talks to an
instance.
"""
from __future__ import annotations

import sys
import time
from typing import Callable, Iterable, Optional

import requests

from vcfcf_core.dashboards.loader import Dashboard
from vcfcf_core.dashboards.summary_bind import (  # noqa: F401  (re-exported for old-path callers)
    BindPlan,
    KindTarget,
    _default_template_name,
    _find_kind_entry,
    loading_widgets,
    plan_bindings,
    resource_kind_id,
    source_loading,
    summary_dashboard_tab,
)

from .ui_client import UIClientError

#: ``--wait`` default: the per-user importer resolves dashboards on a
#: 10-minute tick (bytecode read on 9.0.2), plus a minute of margin; the
#: same budget as the pak install's Summary repair.
WAIT_DEFAULT_S = 660
#: ``--wait`` poll interval.
WAIT_POLL_S = 30
#: Upper bound of ``--wait-timeout``, the same cap as the pak install's
#: materialization wait.
WAIT_MAX_S = 900


def _template_label(value) -> str:
    """``resourceKindTemplate`` as a plain name; tolerant of dict shapes."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for k in ("name", "templateName", "label"):
            if value.get(k):
                return str(value[k])
        return ""
    return str(value)


def _installed_entries(listing, name: str) -> list:
    """Every ``getDashboardList`` entry named ``name`` or ``<folder>/<name>``."""
    out = []
    for d in listing or []:
        if not isinstance(d, dict):
            continue
        dn = d.get("name", "")
        if dn == name or dn.endswith("/" + name):
            out.append(d)
    return out


def _resolve_installed(ui, name: str) -> Optional[str]:
    """Installed dashboard UUID by exact name, or by ``<folder>/<name>``
    (the first match; ``bind_summary`` refuses several)."""
    found = _installed_entries(ui.list_dashboards(), name)
    return found[0].get("id") if found else None


def _entry_by_id(listing, uuid: str) -> Optional[dict]:
    for d in listing or []:
        if isinstance(d, dict) and str(d.get("id") or "").lower() == uuid.lower():
            return d
    return None


def _source_state(ui, entry: dict) -> tuple:
    """``(state, pending)`` for an installed source dashboard.

    ``state`` is ``"built"``, ``"building"`` or ``"unknown"``. The list's
    ``isLoading`` is the gate; the dashboard's own config
    (``getDashboardConfig``, ``isTemplate=false``) names the widgets still
    building and can only make the answer stricter (a widget still loading
    under a list entry that says built is ``"building"``). A config that
    cannot be read leaves the list's answer and no names.
    """
    loading = source_loading(entry)
    pending = None
    try:
        pending = loading_widgets(
            ui.get_dashboard_config(str(entry.get("id")), is_template=False),
            str(entry.get("id")))
    except Exception:  # noqa: BLE001  naming the widgets is best effort
        pending = None
    if loading is None:
        return "unknown", pending or []
    if loading or pending:
        return "building", pending or []
    return "built", []


def _pending_text(pending) -> str:
    return ("unfinished widgets: " + ", ".join(f"'{w}'" for w in pending)
            if pending else "its unfinished widgets could not be read")


def _wait_until_built(ui, entry: dict, *, wait_s: int, poll_s: int,
                      sleep: Callable[[float], None], out: Callable[[str], None]) -> tuple:
    """Poll the source every ``poll_s`` seconds for up to ``wait_s``.

    Returns ``(state, pending, problem, spent)``. A failed read, or a read
    that does not list the dashboard, keeps the last answer and polls on
    (a transient error must not end the wait); ``problem`` then names what
    went wrong at the LAST read (None when the last read worked), so the
    caller reports the real cause rather than a stale "still building".
    ``spent`` is the seconds slept.
    """
    uuid = str(entry.get("id"))
    state, pending = _source_state(ui, entry)
    problem = None
    elapsed = 0
    while state != "built" and elapsed < wait_s:
        step = min(poll_s, wait_s - elapsed)
        sleep(step)
        elapsed += step
        try:
            fresh = _entry_by_id(ui.list_dashboards(), uuid)
        except Exception as exc:  # noqa: BLE001  transient: poll on
            problem = f"the last read of the dashboard list failed ({exc})"
            out(f"   [{elapsed} s] could not read the dashboard list ({exc}); polling on")
            continue
        if fresh is None:
            problem = f"{uuid} was not in the dashboard list at the last read"
            out(f"   [{elapsed} s] {uuid} is not in the dashboard list; polling on")
            continue
        problem = None
        state, pending = _source_state(ui, fresh)
        if state == "building":
            out(f"   [{elapsed} s] still building; {_pending_text(pending)}")
    return state, pending, problem, elapsed


def _read_tabs(ui, kinds) -> dict:
    """``{association_key: dashboard tab or None}`` from ``getSummaryTabId``."""
    return {k.association_key: summary_dashboard_tab(ui.get_summary_tab_id(k.resource_kind_id))
            for k in kinds}


def _live_tab_id(answer) -> Optional[str]:
    """``tabId`` from a ``getSummaryTabId`` answer; a missing key is null
    (org.json drops null-valued keys server-side)."""
    if not isinstance(answer, dict):
        return None
    tab = answer.get("tabId")
    return str(tab) if tab else None


def bind_summary(
    ui,
    dashboards: Iterable[Dashboard],
    *,
    only: Optional[str] = None,
    unbind: bool = False,
    dry_run: bool = False,
    out: Callable[[str], None] = print,
    wait: bool = False,
    wait_s: int = WAIT_DEFAULT_S,
    poll_s: int = WAIT_POLL_S,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Bind (or unbind) every ``summary_for`` dashboard. Returns an exit code.

    Per dashboard: resolve the installed dashboard by name, read every
    listed kind's current assignment, write ONE association call carrying
    all kinds (bind through ``assignedAssociations``, unbind through
    ``resetAssociations``; the maps take many entries and the server
    materializes one template copy per kind), then read ``getSummaryTabId``
    back per kind and print each LIVE tabId (that kind's template UUID).
    After a bind every readback must show a dashboard tab
    (``summary_dashboard_tab``: ``isDashboard: true``, or on 9.0.2 a UUID
    ``tabId`` with no ``isDashboard`` key); after an unbind none may. A listed kind that does not
    resolve on the instance is reported as an ERROR (exit code 2 for the
    run) and left out of the map; the resolvable kinds are still written,
    matching the pak installer's per-kind association. The dashboard is
    skipped whole only when none of its kinds resolve. ``--unbind``
    behaves the same. ``dry_run`` prints the full map only and needs no
    client.

    A bind first checks the source (issue #256): several installed
    dashboards with the name, a source still building, or one whose state
    the list does not report is an ERROR with nothing written. With
    ``wait`` a building source is polled every ``poll_s`` seconds; ``wait_s``
    is the budget for the whole run, not per dashboard. After the write each
    kind's Summary tab must show a dashboard template other than the one it
    showed before; an unchanged tab is an ERROR (a pre-9.1 server skips, and
    still answers ``ok`` for, a dashboard the session user cannot see).

    An association call that is not answered ``ok`` is not taken as a
    refusal on its own (the single-map success body is unread on 9.0.2 and
    8.18): every kind's Summary tab is read back first. Unchanged means
    refused, an ERROR, and the run goes on with the next dashboard; a moved
    tab means the write happened with an unexpected answer, which is said
    as such and then checked per kind like any bind.
    """
    if wait and poll_s <= 0:
        raise ValueError(f"poll_s must be positive with wait, got {poll_s}")
    plans = plan_bindings(dashboards, only)
    if not plans:
        out("no dashboard carries summary_for" + (f" (filter: {only!r})" if only else ""))
        return 1

    if dry_run:
        out(f"{'UNBIND' if unbind else 'BIND'} plan ({len(plans)} dashboard(s)), nothing written:")
        for p in plans:
            for k in p.kinds:
                if unbind:
                    out(f"  resetAssociations   {k.association_key}  ->  <defaultTemplateName>")
                else:
                    out(f"  assignedAssociations  {k.association_key}  ->  "
                        f"{p.dashboard.name}_::_<installed uuid>")
                out(f"      {k.label}  yaml id {p.dashboard.id}")
        return 0

    failures = 0
    budget = max(0, int(wait_s))
    for p in plans:
        name = p.dashboard.name
        out(f"== {name}  ->  {', '.join(k.label for k in p.kinds)}")

        # Resolve every kind. A kind absent on the instance is an ERROR
        # (and the run exits 2) but does not block the others: the pak
        # installer binds each kind independently, so a map carrying only
        # the resolvable kinds is exactly the state a pak install of the
        # same dashboard would leave. Skip the dashboard only when nothing
        # resolves.
        assigned: dict[str, str] = {}
        reset: dict[str, str] = {}
        kind_lists: dict[str, dict] = {}
        bound: list[KindTarget] = []
        for k in p.kinds:
            kinds = kind_lists.get(k.adapter_kind)
            if kinds is None:
                kinds = kind_lists[k.adapter_kind] = ui.get_resource_kind_list(k.adapter_kind)
            entry = _find_kind_entry(kinds, k)
            if entry is None:
                out(f"   ERROR: {name}: resource kind {k.resource_kind!r} not found under adapter "
                    f"kind {k.adapter_kind!r} on this instance (is the adapter installed?); "
                    f"{k.label} not bound")
                failures += 1
                continue
            current = _template_label(entry.get("resourceKindTemplate"))
            out(f"   {k.label}  ({k.resource_kind_id})  current assignment: {current or '<default>'}")
            if unbind:
                default_name = _default_template_name(kinds, entry)
                if not default_name:
                    out(f"   ERROR: {name}: no defaultTemplateName for {k.resource_kind!r}; "
                        f"{k.label} not reset")
                    failures += 1
                    continue
                reset[k.association_key] = default_name
            bound.append(k)
        if not bound:
            out(f"   ERROR: {name}: no listed kind resolves on this instance; nothing written")
            continue

        if not unbind:
            found = _installed_entries(ui.list_dashboards(), name)
            if not found:
                out(f"   ERROR: dashboard {name!r} is not installed (identity is the name; "
                    f"sync it first)")
                failures += 1
                continue
            if len(found) > 1:
                listed = "; ".join(
                    f"{d.get('name')!r} id {d.get('id')} owner {d.get('owner') or '?'}"
                    for d in found)
                out(f"   ERROR: {len(found)} installed dashboards are named {name!r} "
                    f"({listed}); cannot tell which one to bind, nothing written. Rename "
                    f"or delete the extra one.")
                failures += 1
                continue
            entry = found[0]
            uuid = entry.get("id")
            out(f"   installed dashboard uuid: {uuid}")
            state, pending = _source_state(ui, entry)
            problem, spent = None, 0
            if state == "building" and wait:
                out(f"   '{name}' is still building; {_pending_text(pending)}. Waiting up to "
                    f"{budget} s (left of this run's {wait_s} s), re-checking every "
                    f"{poll_s} s.")
                state, pending, problem, spent = _wait_until_built(
                    ui, entry, wait_s=budget, poll_s=poll_s, sleep=sleep, out=out)
                budget -= spent
            if state == "building" and problem:
                out(f"   ERROR: '{name}' ({uuid}) could not be confirmed built after {spent} s: "
                    f"{problem}. It was still building at the last good read "
                    f"({_pending_text(pending)}). Nothing written. Check the session and the "
                    f"dashboard, then run bind-summary again.")
                failures += 1
                continue
            if state == "building":
                waited = f" after {spent} s" if wait else ""
                hint = ("Opening the dashboard once in the UI usually finishes it; then run "
                        "bind-summary again." if wait else
                        "Re-run with --wait, or open the dashboard once in the UI and run "
                        "bind-summary again.")
                out(f"   ERROR: '{name}' ({uuid}) is still building{waited} (isLoading: true; "
                    f"{_pending_text(pending)}). Nothing written: a bind now would copy the "
                    f"unfinished widgets into the Summary template, which the server never "
                    f"finishes (issue #200). {hint}")
                failures += 1
                continue
            if state == "unknown":
                out(f"   ERROR: '{name}' ({uuid}): the dashboard list carries no isLoading "
                    f"flag for it on this build, so whether it finished building is unknown. "
                    f"Nothing written. Once it shows its configured widgets in the UI, bind "
                    f"it under Manage Summary Dashboards.")
                failures += 1
                continue
            assigned = {k.association_key: f"{name}_::_{uuid}" for k in bound}

        before = _read_tabs(ui, bound)
        refused = None
        try:
            ui.associate_resource_kind_dashboards(assigned, reset)
        except (UIClientError, requests.RequestException) as exc:
            refused = exc
        if refused is not None:
            # A non-ok answer is not proof that nothing was written: read
            # every kind back before calling it a refusal (#260 W1).
            try:
                after = _read_tabs(ui, bound)
            except Exception as rexc:  # noqa: BLE001  report, go on with the next dashboard
                out(f"   ERROR: '{name}': the association call was not answered ok "
                    f"({refused}), and the Summary tabs could not be read back ({rexc}); "
                    f"whether anything was written is unknown.")
                failures += 1
                continue
            moved = [k for k in bound if after[k.association_key] != before[k.association_key]]
            if not moved:
                out(f"   ERROR: '{name}': the server refused the association ({refused}); "
                    f"every kind's Summary tab is unchanged, nothing written.")
                failures += 1
                continue
            out(f"   WARNING: '{name}': the association call was not answered ok "
                f"({refused}), but the Summary tab moved for "
                f"{', '.join(k.label for k in moved)}: the write happened and the server's "
                f"answer was unexpected. Each kind is checked below.")
        form = getattr(ui, "association_form", None)
        how = f" ({form} request form)" if isinstance(form, str) else ""
        for k in bound:
            if unbind:
                out(f"   wrote resetAssociations {k.association_key} = "
                    f"{reset[k.association_key]}{how}")
            else:
                out(f"   wrote assignedAssociations {k.association_key} = "
                    f"{assigned[k.association_key]}{how}")

        for k in bound:
            live = ui.get_summary_tab_id(k.resource_kind_id)
            tab = _live_tab_id(live)
            shown = summary_dashboard_tab(live)
            out(f"   {k.label}  LIVE tabId: {tab}")

            if unbind:
                # Symmetric with the bind check: the reset took iff the server
                # no longer reports a dashboard. A native page may still answer
                # with a non-uuid tabId (isDashboard: false, pluginExist), which
                # is the expected post-unbind state, not a failure.
                if shown:
                    out(f"   WARNING: {k.label}: expected isDashboard: false after unbind, "
                        f"got dashboard tab {tab}")
                    failures += 1
            elif not shown:
                out(f"   ERROR: {k.label}: getSummaryTabId did not return a dashboard tab "
                    f"after bind; the association did not take (native page still renders)")
                failures += 1
            elif shown == before.get(k.association_key):
                answered = "answered ok" if refused is None else "was not answered ok"
                out(f"   ERROR: {k.label}: the association call {answered} but the Summary "
                    f"tab still shows {shown}, the copy it showed before the bind; the "
                    f"association did not take (a pre-9.1 server skips a dashboard the "
                    f"session user cannot see)")
                failures += 1
            else:
                out(f"   {k.label}  template UUID: {tab}   <- the server's copy of the "
                    f"dashboard for this kind; this is what renders on the Summary tab, not "
                    f"the installed dashboard. The server replaces it on the next bind of "
                    f"this kind.")
    return 0 if failures == 0 else 2


def print_err(msg: str) -> None:
    print(msg, file=sys.stderr)
