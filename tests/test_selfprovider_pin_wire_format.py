"""Self-provider widget pin wire format — regression tests per
knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md.

  FIX 1 (twice-revised) — a self-provider pinned View widget's nested
      `config.resource.traversalSpecId` is emitted EMPTY, unconditionally
      — no enrichment table. render.py briefly (commits b1b044b/8e44ba9)
      carried a `_VIEW_PIN_TRAVERSAL_SPEC` table that filled in a
      known-good spec string for mapped containers (e.g. VMWARE/vSphere
      World), reasoning the vendor's "Cluster Performance 2.0.json"
      "vSphere Clusters" widget carries one. That was REMOVED: a
      traversal spec constrains the VIEW SUBJECT's hierarchy, not just the
      pin container, so container-keyed injection misfires whenever a
      view's subject isn't in the hierarchy the spec describes —
      concretely, `content/dashboards/vks_core_consumption.yaml` pins to
      VMWARE/vSphere World but its view subject is `VMwareAdapter
      Instance`, and the checked-in WORKING export of that exact widget
      (`knowledge/context/exports/working_dashboards.json`) carries an
      empty nested traversalSpecId — the enrichment would have regressed
      it. No evidence anywhere shows the spec string is REQUIRED for a pin
      to bind (binding comes from selfProvider + the bound resource
      entry); the vendor's own "ESXi Host Details Dashboard.json" (five
      widgets) and our own VKS working export both prove empty is a
      working shape. The TOP-LEVEL `config.traversalSpecId` is ALWAYS
      `null` and `refreshContent` is ALWAYS `false`, mapped container or
      not — unchanged from the previous revision. What IS locked in
      regardless: selfProvider:true plus a bound resource entry — the old
      selfProvider:false/resource:null shape must never come back for a
      self-provider pinned widget.

  FIX 2 — a self-provider HealthChart widget must carry a
      ``resource: [{"name", "id"}]`` entry (never the impossible
      ``selfProvider:true`` + ``resource:[]``), and the container must be
      registered in the shared ``entries.resource`` block.

  FIX 3 (post-review, framework-reviewer WARNING 1) — the external-UUID
      View passthrough branch (``view: '<raw-uuid>'``) must honor a
      declared ``self_provider``+``pin`` the same way the internal
      (bundled-ViewDef) branch does. This is the wire-format delta behind
      Cluster Performance 2.0's live-broken "vSphere Clusters" widget,
      which pins an external built-in view UUID.

  FIX 4 (post-review, framework-reviewer WARNING 2) — a self-provider
      HealthChart's implicit pin fallback (deriving the container from its
      own ``adapter_kind``/``resource_kind`` with no explicit ``pin:``
      block) must NOT silently redirect a leaf kind (e.g. VMWARE
      ``HostSystem``) to the vSphere World container — there is no vendor
      evidence for that. The fallback only applies when the declared kind
      already resolves to itself (a world/singleton). An explicit ``pin:``
      is still honored for any kind.

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
    """Return a minimal ViewDef representing a bundled view."""
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

def test_selfprovider_view_pin_emits_empty_nested_traversal_spec_id():
    """A self-provider View pinned to VMWARE/vSphere World emits an EMPTY
    nested config.resource.traversalSpecId, unconditionally — no
    container-keyed enrichment (removed; see the NOTE above
    _resolve_view_pin in render.py). The top-level config.traversalSpecId
    is always null and refreshContent is always false."""
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
    assert widget["config"]["resource"]["traversalSpecId"] == ""
    assert widget["config"]["traversalSpecId"] is None
    assert widget["config"]["refreshContent"]["refreshContent"] is False
    # Leaf-kind pin (HostSystem) redirects to the vSphere World container,
    # so the resource entry itself is still named/kinded as the world.
    assert widget["config"]["resource"]["resourceName"] == "vSphere World"


def test_selfprovider_view_pin_leaf_kind_redirects_container_only():
    """A pin to a leaf kind (HostSystem) redirects to the vSphere World
    container via _resolve_view_pin for naming/kinding purposes, but the
    nested traversalSpecId stays empty regardless — there is no per-
    container spec lookup any more."""
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
    assert widget["config"]["resource"]["traversalSpecId"] == ""
    assert widget["config"]["traversalSpecId"] is None


def test_selfprovider_view_pin_any_container_keeps_empty_nested_spec():
    """Any container (including one that would previously have been
    "unmapped") emits the same empty nested traversalSpecId — there is no
    map to miss any more, so no distinction between "mapped" and
    "unmapped" containers exists at this site."""
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
    # Vendor bytes: refreshContent stays false even on a fully-bound pin
    # (Cluster Performance 2.0.json "vSphere Clusters" widget).
    assert widget["config"]["refreshContent"]["refreshContent"] is False


# ---------------------------------------------------------------------------
# FIX 3 — external-UUID View passthrough honors self_provider + pin
# ---------------------------------------------------------------------------

_EXTERNAL_UUID = "d8a3767e-9d5e-4bf2-b613-9e3bef977502"


def test_external_uuid_passthrough_with_pin_emits_vendor_shape():
    """Cluster Performance 2.0's live-broken widget shape: a View widget
    pinned to a raw external UUID (view: d8a3767e-...) with self_provider
    + pin must still emit selfProvider:true + a bound resource entry — the
    vendor's own CP2 export does exactly this for its "vSphere Clusters"
    widget. Previously the isinstance(view, str) branch returned early with
    selfProvider:false/resource:None, silently dropping the pin.

    The NESTED config.resource.traversalSpecId is emitted EMPTY (see the
    module docstring FIX 1 note — the container-keyed enrichment that once
    filled this in for VMWARE/vSphere World was removed as unsound: a
    traversal spec constrains the view SUBJECT's hierarchy, and container-
    keying misfires for widgets whose subject isn't in that hierarchy,
    e.g. content/dashboards/vks_core_consumption.yaml). Top-level
    config.traversalSpecId is null and refreshContent is false regardless."""
    w = Widget(
        local_id="view1",
        type="View",
        title="vSphere Clusters",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_EXTERNAL_UUID,
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind="vSphere World"),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    bundle = json.loads(result_json)
    widget = bundle["dashboards"][0]["widgets"][0]

    assert widget["config"]["viewDefinitionId"] == _EXTERNAL_UUID
    assert widget["config"]["selfProvider"]["selfProvider"] is True
    assert widget["config"]["resource"] == {
        "resourceId": "resource:id:0_::_",
        "traversalSpecId": "",
        "resourceName": "vSphere World",
        "resourceKindId": "002006VMWAREvSphere World",
        "id": "Ext.vcops.chrome.model.Resource-1",
    }
    assert widget["config"]["traversalSpecId"] is None
    assert widget["config"]["refreshContent"]["refreshContent"] is False
    assert bundle["entries"]["resource"] == [
        {
            "resourceKindKey": "vSphere World",
            "internalId": "resource:id:0_::_",
            "adapterKindKey": "VMWARE",
            "identifiers": [],
            "name": "vSphere World",
        }
    ]


def test_external_uuid_passthrough_without_pin_unchanged():
    """A non-self-provider (interaction-driven) external-UUID View widget
    keeps the historic passthrough shape — no pin resolution attempted."""
    w = Widget(
        local_id="view1",
        type="View",
        title="External View",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=_EXTERNAL_UUID,
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    widget = json.loads(result_json)["dashboards"][0]["widgets"][0]

    assert widget["config"]["viewDefinitionId"] == _EXTERNAL_UUID
    assert widget["config"]["selfProvider"]["selfProvider"] is False
    assert widget["config"]["resource"] is None
    assert widget["config"]["traversalSpecId"] is None


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


# ---------------------------------------------------------------------------
# FIX 4 — implicit HealthChart fallback is gated to world/singleton kinds
# ---------------------------------------------------------------------------

def test_selfprovider_healthchart_leaf_kind_no_pin_keeps_empty_resource():
    """A self-provider HealthChart authored directly on a VMWARE leaf kind
    (ClusterComputeResource) with NO explicit pin: block must NOT be
    silently redirected to the vSphere World container — there is no
    vendor evidence for that. resource stays []."""
    w = Widget(
        local_id="hc1",
        type="HealthChart",
        title="Leaf Kind Chart",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        self_provider=True,
        health_chart_config=HealthChartConfig(
            adapter_kind="VMWARE",
            resource_kind="ClusterComputeResource",
            metric_key="cpu|usage_average",
            metric_name="CPU Usage (%)",
            mode="resource",
        ),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    bundle = json.loads(result_json)
    widget = bundle["dashboards"][0]["widgets"][0]

    assert widget["config"]["selfProvider"]["selfProvider"] is True
    assert widget["config"]["resource"] == []
    assert bundle["entries"].get("resource", []) == []


def test_selfprovider_healthchart_leaf_kind_mode_all_no_pin_keeps_empty_resource():
    """Same gate applies for mode: 'all' ("list all resources of the kind")
    — the fallback is not mode-dependent; a leaf kind never implicitly
    world-pins regardless of mode."""
    w = Widget(
        local_id="hc1",
        type="HealthChart",
        title="Leaf Kind Chart (mode=all)",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        self_provider=True,
        health_chart_config=HealthChartConfig(
            adapter_kind="VMWARE",
            resource_kind="VirtualMachine",
            metric_key="cpu|usage_average",
            metric_name="CPU Usage (%)",
            mode="all",
        ),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    widget = json.loads(result_json)["dashboards"][0]["widgets"][0]

    assert widget["config"]["selfProvider"]["selfProvider"] is True
    assert widget["config"]["resource"] == []


def test_selfprovider_healthchart_leaf_kind_with_explicit_pin_still_binds():
    """An explicit pin: block IS honored for a leaf kind — only the
    implicit adapter_kind/resource_kind fallback is gated, not an
    author-declared pin."""
    w = Widget(
        local_id="hc1",
        type="HealthChart",
        title="Leaf Kind Chart (explicit pin)",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        self_provider=True,
        pin=WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind="HostSystem"),
        health_chart_config=HealthChartConfig(
            adapter_kind="VMWARE",
            resource_kind="ClusterComputeResource",
            metric_key="cpu|usage_average",
            metric_name="CPU Usage (%)",
            mode="resource",
        ),
        dashboard_name="Test Dashboard",
    )
    dashboard = _make_dashboard([w])

    result_json = render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    bundle = json.loads(result_json)
    widget = bundle["dashboards"][0]["widgets"][0]

    assert widget["config"]["resource"] == [
        {"name": "vSphere World", "id": "resource:id:0_::_"}
    ]
    assert bundle["entries"]["resource"] == [
        {
            "resourceKindKey": "vSphere World",
            "internalId": "resource:id:0_::_",
            "adapterKindKey": "VMWARE",
            "identifiers": [],
            "name": "vSphere World",
        }
    ]
