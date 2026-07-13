"""Self-provider widget pin wire format — regression tests per
knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md.

  FIX 1 (revised) — a self-provider pinned View widget's traversalSpecId is
      an OPTIONAL enrichment, not a requirement: two vendor exports were
      compared and "ESXi Host Details Dashboard.json" ships five working
      pinned View widgets with `traversalSpecId: ""` (empty). So render.py
      fills in a known-good traversalSpecId (``_VIEW_PIN_TRAVERSAL_SPEC``)
      for mapped containers (e.g. VMWARE/vSphere World) but silently falls
      back to the historic empty-string / null shape for unmapped
      containers — no warning, since empty is itself a vendor-proven
      working shape. What IS locked in regardless: selfProvider:true plus
      a bound resource entry — the old selfProvider:false/resource:null
      shape must never come back for a self-provider pinned widget.

  FIX 2 — a self-provider HealthChart widget must carry a
      ``resource: [{"name", "id"}]`` entry (never the impossible
      ``selfProvider:true`` + ``resource:[]``), and the container must be
      registered in the shared ``entries.resource`` block.

All fixtures are built in-memory using loader/render dataclasses; no disk
content YAML, no network, no install.
"""
from __future__ import annotations

import json
import uuid

from vcfops_dashboards.loader import (
    Dashboard,
    HealthChartConfig,
    ViewColumn,
    ViewDef,
    Widget,
    WidgetResourceKindRef,
)
from vcfops_dashboards.render import render_dashboards_bundle_json


_OWNER_ID = "00000000-0000-0000-0000-000000000001"
_BUNDLED_VIEW_NAME = "vSphere Cluster Performance List"
_BUNDLED_VIEW_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_bundled_view() -> ViewDef:
    """Return a minimal ViewDef representing a bundled view (a View widget
    must reference a bundled view — not an external UUID — for pin/
    self-provider config to be emitted; the external-passthrough branch in
    ``_view_widget`` intentionally skips pin resolution entirely)."""
    return ViewDef(
        id=_BUNDLED_VIEW_ID,
        name=_BUNDLED_VIEW_NAME,
        description="",
        adapter_kind="VMWARE",
        resource_kind="ClusterComputeResource",
        columns=[ViewColumn(attribute="cpu|usage_average", display_name="CPU Usage (%)")],
    )


def _make_dashboard(widgets: list[Widget], dash_id: str | None = None) -> Dashboard:
    return Dashboard(
        id=dash_id or str(uuid.uuid4()),
        name="Test Dashboard",
        description="",
        widgets=widgets,
        interactions=[],
        name_path="Testing",
        shared=True,
        hidden=False,
    )


# ---------------------------------------------------------------------------
# FIX 1 — View widget pin traversalSpecId
# ---------------------------------------------------------------------------

def test_selfprovider_view_pin_emits_mapped_traversal_spec_id():
    """A self-provider View pinned to VMWARE/vSphere World emits the known
    built-in traversalSpecId in both wire-format locations."""
    w = Widget(
        local_id="view1",
        type="View",
        title="Pinned View",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_BUNDLED_VIEW_NAME,
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind="vSphere World"),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])
    views_by_name = {_BUNDLED_VIEW_NAME: _make_bundled_view()}

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    bundle = json.loads(result_json)
    widget = bundle["dashboards"][0]["widgets"][0]

    assert widget["config"]["selfProvider"]["selfProvider"] is True
    assert widget["config"]["resource"]["traversalSpecId"] == (
        "vSphere Hosts and Clusters-VMWARE-vSphere World"
    )
    assert widget["config"]["traversalSpecId"] == (
        "vSphere Hosts and Clusters-VMWARE-vSphere World"
    )
    # Leaf-kind pin (HostSystem) redirects to the vSphere World container,
    # so the resource entry itself is still named/kinded as the world.
    assert widget["config"]["resource"]["resourceName"] == "vSphere World"


def test_selfprovider_view_pin_leaf_kind_redirects_and_maps_traversal_spec():
    """A pin to a leaf kind (HostSystem) redirects to the vSphere World
    container via _resolve_view_pin, and still resolves a traversalSpecId
    because the container (not the leaf) is the map key."""
    w = Widget(
        local_id="view1",
        type="View",
        title="Pinned Host View",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_BUNDLED_VIEW_NAME,
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind="HostSystem"),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])
    views_by_name = {_BUNDLED_VIEW_NAME: _make_bundled_view()}

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    widget = json.loads(result_json)["dashboards"][0]["widgets"][0]

    assert widget["config"]["resource"]["resourceName"] == "vSphere World"
    assert widget["config"]["resource"]["traversalSpecId"] == (
        "vSphere Hosts and Clusters-VMWARE-vSphere World"
    )
    assert widget["config"]["traversalSpecId"] == (
        "vSphere Hosts and Clusters-VMWARE-vSphere World"
    )


def test_selfprovider_view_pin_unmapped_container_keeps_empty_shape_silently():
    """An unmapped container keeps the historic empty-string / null emission,
    with NO warning — the vendor's "ESXi Host Details Dashboard.json" export
    proves an empty traversalSpecId is itself a working, shipped shape (its
    five pinned View widgets all carry ""), so this is not a downgrade."""
    w = Widget(
        local_id="view1",
        type="View",
        title="Pinned Unmapped View",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_BUNDLED_VIEW_NAME,
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="NSXTAdapter", resource_kind="NSXTManager"),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])
    views_by_name = {_BUNDLED_VIEW_NAME: _make_bundled_view()}

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    widget = json.loads(result_json)["dashboards"][0]["widgets"][0]

    assert widget["config"]["resource"]["traversalSpecId"] == ""
    assert widget["config"]["traversalSpecId"] is None


def test_selfprovider_view_pin_always_emits_selfprovider_and_resource_entry():
    """Vendor-shape lock-in (both Cluster Performance 2.0 and ESXi Host
    Details Dashboard exports agree on this much): a self-provider pinned
    View widget always emits selfProvider:true plus a bound resource entry
    — regardless of whether a traversalSpecId is known for the container.
    Must not regress silently to selfProvider:false/resource:null."""
    w = Widget(
        local_id="view1",
        type="View",
        title="Pinned Unmapped View",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_BUNDLED_VIEW_NAME,
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="NSXTAdapter", resource_kind="NSXTManager"),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])
    views_by_name = {_BUNDLED_VIEW_NAME: _make_bundled_view()}

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    widget = json.loads(result_json)["dashboards"][0]["widgets"][0]

    assert widget["config"]["selfProvider"]["selfProvider"] is True
    assert widget["config"]["resource"] is not None
    assert widget["config"]["resource"]["resourceId"] == "resource:id:0_::_"
    assert widget["config"]["refreshContent"]["refreshContent"] is True


# ---------------------------------------------------------------------------
# FIX 2 — HealthChart self-provider resource pin
# ---------------------------------------------------------------------------

def _make_health_chart_widget(self_provider: bool = True) -> Widget:
    return Widget(
        local_id="hc1",
        type="HealthChart",
        title="Average Performance",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        self_provider=self_provider,
        health_chart_config=HealthChartConfig(
            adapter_kind="VMWARE",
            resource_kind="vSphere World",
            metric_key="performance|cluster_performance",
            metric_name="Performance|Clusters Performance (%)",
            mode="resource",
        ),
        dashboard_name="Test Dashboard",
    )


def test_selfprovider_healthchart_emits_resource_entry_no_pin_field_needed():
    """A self-provider HealthChart with no explicit `pin:` block derives the
    binding from its own adapter_kind/resource_kind and emits the vendor
    shape — never the impossible selfProvider:true + resource:[]."""
    w = _make_health_chart_widget()
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    bundle = json.loads(result_json)
    widget = bundle["dashboards"][0]["widgets"][0]

    assert widget["config"]["selfProvider"]["selfProvider"] is True
    assert widget["config"]["resource"] == [
        {"name": "vSphere World", "id": "resource:id:0_::_"}
    ]


def test_selfprovider_healthchart_registers_container_in_entries_resource():
    """The container the HealthChart binds to must appear in the shared
    ``entries.resource`` block so the importer can resolve the pin."""
    w = _make_health_chart_widget()
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    bundle = json.loads(result_json)
    entries_resource = bundle["entries"]["resource"]

    assert entries_resource == [
        {
            "resourceKindKey": "vSphere World",
            "internalId": "resource:id:0_::_",
            "adapterKindKey": "VMWARE",
            "identifiers": [],
            "name": "vSphere World",
        }
    ]


def test_non_selfprovider_healthchart_keeps_empty_resource_list():
    """A non-self-provider HealthChart (interaction-driven) must keep the
    old resource:[] shape — no pin binding attempted."""
    w = _make_health_chart_widget(self_provider=False)
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    widget = json.loads(result_json)["dashboards"][0]["widgets"][0]

    assert widget["config"]["selfProvider"]["selfProvider"] is False
    assert widget["config"]["resource"] == []


def test_selfprovider_healthchart_and_view_share_one_resource_index_slot():
    """When a View and a HealthChart on the same dashboard both pin to the
    same container, they share one entries.resource[] slot (0), not two."""
    view_w = Widget(
        local_id="view1",
        type="View",
        title="Pinned View",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_BUNDLED_VIEW_NAME,
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind="vSphere World"),
        dashboard_name="Test Dashboard",
    )
    hc_w = _make_health_chart_widget()
    dashboard = _make_dashboard([view_w, hc_w])
    views_by_name = {_BUNDLED_VIEW_NAME: _make_bundled_view()}

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    bundle = json.loads(result_json)
    entries_resource = bundle["entries"]["resource"]
    widgets = bundle["dashboards"][0]["widgets"]

    assert len(entries_resource) == 1
    assert entries_resource[0]["internalId"] == "resource:id:0_::_"
    view_widget = next(w for w in widgets if w["type"] == "View")
    hc_widget = next(w for w in widgets if w["type"] == "HealthChart")
    assert view_widget["config"]["resource"]["resourceId"] == "resource:id:0_::_"
    assert hc_widget["config"]["resource"][0]["id"] == "resource:id:0_::_"
