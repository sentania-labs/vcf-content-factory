"""Offline half of the ``summary_for`` Summary-tab binding (M2 row 2).

Everything here is computable without a session: the deterministic
``resourceKindId``, the per-dashboard bind plan, the two readers of a
``getResourceKindList`` answer (``_find_kind_entry``,
``_default_template_name``), and the pure readers of the answers the live
flow gates on (``summary_dashboard_tab``, ``source_loading``,
``loading_widgets``). The live flow (``bind_summary`` and every
helper that takes a ``ui`` client) stays in the factory's
``vcfcf_dashboards.summary_bind``, which imports this module.

Wire-format ground truth:
knowledge/context/api-surface/summary_dashboard_assignment.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .loader import Dashboard
from .render import adapter_kind_prefix


def resource_kind_id(adapter_kind: str, resource_kind: str) -> str:
    """The UI's deterministic resource kind id.

    ``"0020" + two-digit adapter-kind key length + adapter kind + resource
    kind``; identical to the server's ``IdGeneratorUtil.toID`` used by the
    pak installer.
    """
    return f"{adapter_kind_prefix(adapter_kind)}{adapter_kind}{resource_kind}"


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


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def summary_dashboard_tab(answer) -> Optional[str]:
    """The template id a ``getSummaryTabId`` answer shows on the Summary
    tab, or None when the tab is not dashboard-backed.

    Shapes per build: ``{"tabId", "isDashboard": true}`` (9.1.1, 9.2),
    ``{"tabId"}`` with NO ``isDashboard`` key (9.0.2, read 2026-10-24),
    ``{}`` or ``{"isDashboard": false}`` with no ``tabId`` (no association;
    org.json drops a null key), ``{"tabId": "<non-uuid>", "isDashboard":
    false, "pluginExist"}`` (legacy plugin page). An explicit
    ``isDashboard`` decides; without one, only a UUID tab id counts as a
    dashboard template.
    """
    if not isinstance(answer, dict):
        return None
    tab = answer.get("tabId")
    if not tab:
        return None
    tab = str(tab)
    if "isDashboard" in answer:
        return tab if answer.get("isDashboard") else None
    return tab if _UUID_RE.match(tab) else None


def source_loading(entry) -> Optional[bool]:
    """``isLoading`` of one ``getDashboardList`` entry: True while the
    dashboard is still building (phase 2 of the import has not resolved its
    widgets), False once built, None when the entry is missing or carries no
    flag (state unknown; never read as built)."""
    if not isinstance(entry, dict):
        return None
    return loading_flag(entry.get("isLoading"))


def loading_flag(value) -> Optional[bool]:
    """One ``isLoading`` value: ``True``/``"true"`` is True,
    ``False``/``"false"`` is False, anything else (absent, null, another
    string or type) is None, unknown, so it never reads as built."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return {"true": True, "false": False}.get(value.strip().lower())
    return None


def loading_widgets(config, tab_id: str) -> Optional[list]:
    """Titles of the widgets still building (``isLoading: true``) in one tab
    of a ``getDashboardConfig`` answer, in layout order; a widget without a
    title is named by its ``key`` then its ``id``. Includes ``"(dashboard)"``
    when only the tab itself carries the flag. None when the answer does
    not carry the tab."""
    tabs = []
    if isinstance(config, dict) and isinstance(config.get("dashboardConfig"), dict):
        tabs = config["dashboardConfig"].get("tabConfigs") or []
    tab = next((t for t in tabs if isinstance(t, dict)
                and str(t.get("id") or "").lower() == str(tab_id).lower()), None)
    if tab is None:
        return None
    names = []
    for w in tab.get("widgets") or []:
        if isinstance(w, dict) and loading_flag(w.get("isLoading")) is True:
            names.append(str(w.get("title") or w.get("key") or w.get("id") or "?"))
    if not names and loading_flag(tab.get("isLoading")) is True:
        names.append("(dashboard)")
    return names


def _default_template_name(kinds: dict, entry: dict) -> str:
    """The reset value for a kind: its own ``defaultTemplateName`` when the
    entry carries one (kinds with a built-in page, e.g. ``HostSystem`` ->
    ``Host System Summary``), else the top-level generic default."""
    return str(entry.get("defaultTemplateName") or kinds.get("defaultTemplateName") or "")
