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

Dashboard identity is the NAME (see id_guard.py): the installed
dashboard is resolved by name, never by the YAML id, because an import
under an existing name replaces the object and can leave the YAML id
pointing at nothing.

The client is injected (``ui``) so the flow is unit-testable with a fake;
``bind_summary(None, ..., dry_run=True)`` prints the planned map without
any session.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .loader import Dashboard


def resource_kind_id(adapter_kind: str, resource_kind: str) -> str:
    """The UI's deterministic resource kind id.

    ``"0020" + two-digit adapter-kind key length + adapter kind + resource
    kind``; identical to the server's ``IdGeneratorUtil.toID`` used by the
    pak installer.
    """
    return f"0020{len(adapter_kind):02d}{adapter_kind}{resource_kind}"


@dataclass
class KindTarget:
    """One ``AdapterKind:ResourceKind`` a dashboard binds to."""
    adapter_kind: str
    resource_kind: str

    @property
    def resource_kind_id(self) -> str:
        return resource_kind_id(self.adapter_kind, self.resource_kind)

    @property
    def association_key(self) -> str:
        return f"resourceKind_{self.resource_kind_id}"

    @property
    def label(self) -> str:
        return f"{self.adapter_kind}:{self.resource_kind}"


@dataclass
class BindPlan:
    """One dashboard and every kind it binds to (one association call).

    ``adapter_kind`` / ``resource_kind`` / ``resource_kind_id`` /
    ``association_key`` describe the FIRST kind; they are kept so
    single-kind callers read as before.
    """
    dashboard: Dashboard
    kinds: list[KindTarget]

    @property
    def adapter_kind(self) -> str:
        return self.kinds[0].adapter_kind

    @property
    def resource_kind(self) -> str:
        return self.kinds[0].resource_kind

    @property
    def resource_kind_id(self) -> str:
        return self.kinds[0].resource_kind_id

    @property
    def association_key(self) -> str:
        return self.kinds[0].association_key


def plan_bindings(dashboards: Iterable[Dashboard], only: Optional[str] = None) -> list[BindPlan]:
    """Every dashboard carrying ``summary_for`` (optionally just ``only``),
    one plan per dashboard with all of its kinds."""
    plans: list[BindPlan] = []
    for d in dashboards:
        if not d.summary_for:
            continue
        if only is not None and d.name != only:
            continue
        kinds = [KindTarget(ak, rk) for ak, rk in d.summary_kinds]
        plans.append(BindPlan(dashboard=d, kinds=kinds))
    return plans


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


def _resolve_installed(ui, name: str) -> Optional[str]:
    """Installed dashboard UUID by exact name, or by ``<folder>/<name>``."""
    for d in ui.list_dashboards():
        dn = d.get("name", "")
        if dn == name or dn.endswith("/" + name):
            return d.get("id")
    return None


def _find_kind_entry(body: dict, plan: "BindPlan | KindTarget") -> Optional[dict]:
    """The ``resourceKindList[]`` entry for the kind.

    Live shape (reference/docs/extracted/summary-dashboard-assignment/):
    every entry carries ``resourceKindId``, ``resourceKind``,
    ``adapterKind``, ``name`` and ``resourceKindTemplate``. Match on the
    id first; fall back to the (adapterKind, resourceKind) pair.
    """
    entries = [e for e in (body.get("resourceKindList") or []) if isinstance(e, dict)]
    for entry in entries:
        if entry.get("resourceKindId") == plan.resource_kind_id:
            return entry
    for entry in entries:
        if (entry.get("resourceKind") == plan.resource_kind
                and entry.get("adapterKind") == plan.adapter_kind):
            return entry
    return None


def _default_template_name(kinds: dict, entry: dict) -> str:
    """The reset value for a kind: its own ``defaultTemplateName`` when the
    entry carries one (kinds with a built-in page, e.g. ``HostSystem`` ->
    ``Host System Summary``), else the top-level generic default."""
    return str(entry.get("defaultTemplateName") or kinds.get("defaultTemplateName") or "")


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
) -> int:
    """Bind (or unbind) every ``summary_for`` dashboard. Returns an exit code.

    Per dashboard: resolve the installed dashboard by name, read every
    listed kind's current assignment, write ONE association call carrying
    all kinds (bind through ``assignedAssociations``, unbind through
    ``resetAssociations``; the maps take many entries and the server
    materializes one template copy per kind), then read ``getSummaryTabId``
    back per kind and print each LIVE tabId (that kind's template UUID).
    After a bind every readback must carry ``isDashboard: true`` and a
    ``tabId``; after an unbind none may. A listed kind that does not
    resolve on the instance is reported as an ERROR (exit code 2 for the
    run) and left out of the map; the resolvable kinds are still written,
    matching the pak installer's per-kind association. The dashboard is
    skipped whole only when none of its kinds resolve. ``--unbind``
    behaves the same. ``dry_run`` prints the full map only and needs no
    client.
    """
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
            uuid = _resolve_installed(ui, name)
            if uuid is None:
                out(f"   ERROR: dashboard {name!r} is not installed (identity is the name; "
                    f"sync it first)")
                failures += 1
                continue
            out(f"   installed dashboard uuid: {uuid}")
            assigned = {k.association_key: f"{name}_::_{uuid}" for k in bound}

        ui.associate_resource_kind_dashboards(assigned, reset)
        for k in bound:
            if unbind:
                out(f"   wrote resetAssociations {k.association_key} = {reset[k.association_key]}")
            else:
                out(f"   wrote assignedAssociations {k.association_key} = {assigned[k.association_key]}")

        for k in bound:
            live = ui.get_summary_tab_id(k.resource_kind_id)
            tab = _live_tab_id(live)
            is_dashboard = bool(isinstance(live, dict) and live.get("isDashboard"))
            out(f"   {k.label}  LIVE tabId: {tab}")

            if unbind:
                # Symmetric with the bind check: the reset took iff the server
                # no longer reports a dashboard. A native page may still answer
                # with a non-uuid tabId (isDashboard: false, pluginExist), which
                # is the expected post-unbind state, not a failure.
                if is_dashboard:
                    out(f"   WARNING: {k.label}: expected isDashboard: false after unbind, "
                        f"got dashboard tab {tab}")
                    failures += 1
            elif not tab or not is_dashboard:
                out(f"   ERROR: {k.label}: getSummaryTabId did not return isDashboard: true "
                    f"with a tabId after bind; the association did not take (native page "
                    f"still renders)")
                failures += 1
            else:
                out(f"   {k.label}  template UUID: {tab}   <- the server's copy of the "
                    f"dashboard for this kind; this is what renders on the Summary tab, not "
                    f"the installed dashboard. The server replaces it on the next bind of "
                    f"this kind.")
    return 0 if failures == 0 else 2


def print_err(msg: str) -> None:
    print(msg, file=sys.stderr)
