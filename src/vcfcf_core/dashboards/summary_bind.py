"""Offline half of the ``summary_for`` Summary-tab binding (M2 row 2).

Everything here is computable without a session: the deterministic
``resourceKindId``, the per-dashboard bind plan, and the two readers of a
``getResourceKindList`` answer (``_find_kind_entry``,
``_default_template_name``). The live flow (``bind_summary`` and every
helper that takes a ``ui`` client) stays in the factory's
``vcfcf_dashboards.summary_bind``, which imports this module.

Wire-format ground truth:
knowledge/context/api-surface/summary_dashboard_assignment.md.
"""
from __future__ import annotations

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


def _default_template_name(kinds: dict, entry: dict) -> str:
    """The reset value for a kind: its own ``defaultTemplateName`` when the
    entry carries one (kinds with a built-in page, e.g. ``HostSystem`` ->
    ``Host System Summary``), else the top-level generic default."""
    return str(entry.get("defaultTemplateName") or kinds.get("defaultTemplateName") or "")
