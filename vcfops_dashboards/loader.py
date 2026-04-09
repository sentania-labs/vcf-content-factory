"""YAML -> in-memory dashboard / view definition models.

UUIDs are random uuid4 values stored in each view / dashboard YAML's
`id` field, minted on first validate and never touched again. This
matches the super metric loader's contract (see
`context/uuids_and_cross_references.md`) and means rename-safe
install: changing a view or dashboard's name does not change its id,
so the existing server-side object is updated in place on re-sync.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

# Stable namespace for derived UUIDs. Do NOT change once content has
# been deployed — every dashboard/view id is derived from this.
NS = uuid.UUID("4b8d2c10-1f9e-4f4f-9b90-0e8f6a8e2a12")


class DashboardValidationError(ValueError):
    pass


def stable_id(kind: str, name: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}::{name}"))


@dataclass
class ViewColumn:
    attribute: str
    display_name: str
    unit: str = ""  # preferredUnitId, optional


@dataclass
class ViewDef:
    name: str
    description: str
    adapter_kind: str
    resource_kind: str
    columns: List[ViewColumn]
    id: str = ""
    source_path: Path | None = None

    def validate(self) -> None:
        if not self.name.strip():
            raise DashboardValidationError("view: name is required")
        if not self.adapter_kind or not self.resource_kind:
            raise DashboardValidationError(
                f"view {self.name}: adapter_kind and resource_kind required"
            )
        if not self.columns:
            raise DashboardValidationError(
                f"view {self.name}: at least one column required"
            )
        for c in self.columns:
            if not c.attribute or not c.display_name:
                raise DashboardValidationError(
                    f"view {self.name}: column requires attribute and display_name"
                )


@dataclass
class WidgetResourceKindRef:
    adapter_kind: str
    resource_kind: str


@dataclass
class Widget:
    local_id: str  # author-supplied short id used for interaction wiring
    type: str  # ResourceList | View
    title: str
    coords: dict  # {x, y, w, h}
    # ResourceList only:
    resource_kinds: List[WidgetResourceKindRef] = field(default_factory=list)
    # View only:
    view_name: str = ""
    # View-widget self-provider: when true, the widget does not wait
    # for an incoming interaction and instead enumerates its subject.
    # Requires ``pin`` to a container resource kind (e.g. vSphere World)
    # whose descendants Ops walks to populate the list.
    self_provider: bool = False
    pin: WidgetResourceKindRef | None = None
    # Set by load_dashboard so widget UUIDs are namespaced by dashboard
    # name — otherwise two dashboards reusing the same local_id (e.g.
    # "vm_perf_view") generate identical widget UUIDs and their
    # interaction wiring collides in the rendered bundle.
    dashboard_name: str = ""

    @property
    def widget_id(self) -> str:
        return stable_id("widget", f"{self.dashboard_name}::{self.local_id}")


@dataclass
class Interaction:
    from_local_id: str
    to_local_id: str
    type: str = "resourceId"


@dataclass
class Dashboard:
    name: str
    description: str
    widgets: List[Widget]
    interactions: List[Interaction]
    # Ops dashboard folder path — lands in the Ops UI's dashboard
    # sidebar under this folder. Default is the framework folder; can
    # be overridden per-dashboard if an author has a specific reason.
    name_path: str = "VCF Content Factory"
    # Whether the dashboard is shared with other Ops users. Defaults
    # to True — a dashboard nobody else can see defeats the purpose
    # of the framework. Can be overridden per-dashboard via YAML.
    shared: bool = True
    id: str = ""
    source_path: Path | None = None

    def validate(self, known_views: dict[str, ViewDef]) -> None:
        if not self.name.strip():
            raise DashboardValidationError("dashboard: name is required")
        seen: set[str] = set()
        for w in self.widgets:
            if w.local_id in seen:
                raise DashboardValidationError(
                    f"dashboard {self.name}: duplicate widget id {w.local_id}"
                )
            seen.add(w.local_id)
            if w.type not in ("ResourceList", "View"):
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"unsupported type {w.type} (v1 supports ResourceList, View)"
                )
            if w.type == "ResourceList" and not w.resource_kinds:
                raise DashboardValidationError(
                    f"dashboard {self.name}: widget {w.local_id}: "
                    f"ResourceList requires resource_kinds"
                )
            if w.type == "View":
                if not w.view_name:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"View requires 'view' (the view definition name)"
                    )
                if w.view_name not in known_views:
                    raise DashboardValidationError(
                        f"dashboard {self.name}: widget {w.local_id}: "
                        f"unknown view '{w.view_name}'"
                    )
        for ix in self.interactions:
            if ix.from_local_id not in seen or ix.to_local_id not in seen:
                raise DashboardValidationError(
                    f"dashboard {self.name}: interaction references unknown widget"
                )


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _mint_id_into_file(path: Path) -> str:
    """Mint a uuid4 and prepend ``id: <uuid>`` to the YAML file.

    Same contract as the super metric loader: UUIDs are generated
    once on first validate and never touched after. See
    context/uuids_and_cross_references.md.
    """
    new_id = str(uuid.uuid4())
    original = path.read_text()
    path.write_text(f"id: {new_id}\n{original}")
    return new_id


def load_view(path: Path) -> ViewDef:
    data = yaml.safe_load(path.read_text()) or {}
    view_id = str(data.get("id", "") or "").strip().lower()
    if not view_id:
        view_id = _mint_id_into_file(path)
    elif not _UUID_RE.match(view_id):
        raise DashboardValidationError(
            f"{path}: id '{view_id}' is not a valid uuid4"
        )
    cols = [
        ViewColumn(
            attribute=str(c["attribute"]).strip(),
            display_name=str(c["display_name"]).strip(),
            unit=str(c.get("unit", "") or "").strip(),
        )
        for c in (data.get("columns") or [])
    ]
    subj = data.get("subject") or {}
    v = ViewDef(
        id=view_id,
        name=str(data.get("name", "")).strip(),
        description=str(data.get("description", "") or "").strip(),
        adapter_kind=str(subj.get("adapter_kind", "")).strip(),
        resource_kind=str(subj.get("resource_kind", "")).strip(),
        columns=cols,
        source_path=path,
    )
    v.validate()
    return v


def load_dashboard(path: Path) -> Dashboard:
    data = yaml.safe_load(path.read_text()) or {}
    dash_id = str(data.get("id", "") or "").strip().lower()
    if not dash_id:
        dash_id = _mint_id_into_file(path)
    elif not _UUID_RE.match(dash_id):
        raise DashboardValidationError(
            f"{path}: id '{dash_id}' is not a valid uuid4"
        )
    widgets: List[Widget] = []
    for w in data.get("widgets", []) or []:
        rks = [
            WidgetResourceKindRef(
                adapter_kind=str(rk["adapter_kind"]).strip(),
                resource_kind=str(rk["resource_kind"]).strip(),
            )
            for rk in (w.get("resource_kinds") or [])
        ]
        pin_raw = w.get("pin")
        pin = None
        if pin_raw:
            pin = WidgetResourceKindRef(
                adapter_kind=str(pin_raw["adapter_kind"]).strip(),
                resource_kind=str(pin_raw["resource_kind"]).strip(),
            )
        widgets.append(
            Widget(
                local_id=str(w["id"]).strip(),
                type=str(w["type"]).strip(),
                title=str(w.get("title", "")).strip(),
                coords=dict(w.get("coords") or {"x": 1, "y": 1, "w": 6, "h": 6}),
                resource_kinds=rks,
                view_name=str(w.get("view", "") or "").strip(),
                self_provider=bool(w.get("self_provider", False)),
                pin=pin,
            )
        )
    interactions = [
        Interaction(
            from_local_id=str(ix["from"]).strip(),
            to_local_id=str(ix["to"]).strip(),
            type=str(ix.get("type", "resourceId")).strip(),
        )
        for ix in (data.get("interactions") or [])
    ]
    name = str(data.get("name", "")).strip()
    for w in widgets:
        w.dashboard_name = name
    name_path = str(data.get("name_path", "") or "").strip()
    shared_raw = data.get("shared")
    shared = True if shared_raw is None else bool(shared_raw)
    return Dashboard(
        id=dash_id,
        name=name,
        description=str(data.get("description", "") or "").strip(),
        widgets=widgets,
        interactions=interactions,
        name_path=name_path or "VCF Content Factory",
        shared=shared,
        source_path=path,
    )


def load_all(views_dir: Path, dashboards_dir: Path) -> tuple[list[ViewDef], list[Dashboard]]:
    views = [load_view(p) for p in sorted(views_dir.rglob("*.y*ml"))] if views_dir.exists() else []
    by_name = {v.name: v for v in views}
    dashboards: List[Dashboard] = []
    if dashboards_dir.exists():
        for p in sorted(dashboards_dir.rglob("*.y*ml")):
            d = load_dashboard(p)
            d.validate(by_name)
            dashboards.append(d)
    return views, dashboards
