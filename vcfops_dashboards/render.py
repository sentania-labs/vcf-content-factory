"""Render in-memory models to the wire formats VCF Operations expects.

View definitions are XML (`content.xml`); dashboards are JSON
(`dashboard/dashboard.json`). Both formats were learned by reverse
engineering an export from a live VCF Ops 9 instance plus reference
content from the AriaOperationsContent and operations_dashboards
GitHub repos.

This module deliberately produces the *minimum viable* shape — only
the fields the importer demonstrably needs for the v1 widget set
(ResourceList + View) and a list-style view definition. Every other
property is omitted, defaulted, or left empty.
"""
from __future__ import annotations

import json
import time
import uuid
from xml.sax.saxutils import escape

from .loader import Dashboard, Interaction, ViewDef, Widget


# Stable per-adapter-kind prefix used in `resourceKindId` fields inside
# dashboard widget configs. Harvested from reference bundles under
# `references/` — the value is the same on every Ops instance for a
# given adapter. Extend as new adapter kinds get pinned; there is no
# API to derive these at runtime (checked /api/adapterkinds and
# /api/adapterkinds/*/resourcekinds; no numeric id is exposed).
_ADAPTER_KIND_PREFIX = {
    "VMWARE": "002006",
    "Container": "002009",
    "CASAdapter": "002010",
    "NSXTAdapter": "002011",
    "KubernetesAdapter": "002017",
    "VMWARE_INFRA_HEALTH": "002019",
}


# ---------------- View definition (XML) ----------------

def _xml_property(name: str, value: str) -> str:
    return f'<Property name="{escape(name)}" value="{escape(value)}"/>'


def _xml_attribute_item(view: ViewDef, col, idx: int) -> str:
    # Super metric columns live in their own namespace and need the
    # "Super Metric|sm_<uuid>" attributeKey form — bare "sm_<uuid>"
    # renders as a blank column in the UI. Reference: exported views
    # from the sentania/AriaOperationsContent VCF License Consumption
    # bundle. Super metric columns also use rollUpType=NONE, not AVG.
    raw = col.attribute
    if raw.startswith("sm_"):
        attribute_key = f"Super Metric|{raw}"
        roll_up_type = "NONE"
    elif raw.startswith("Super Metric|"):
        attribute_key = raw
        roll_up_type = "NONE"
    else:
        attribute_key = raw
        roll_up_type = "AVG"
    props = [
        _xml_property("objectType", "RESOURCE"),
        _xml_property("attributeKey", attribute_key),
    ]
    if col.unit:
        props.append(_xml_property("preferredUnitId", col.unit))
    props += [
        _xml_property("isStringAttribute", "false"),
        _xml_property("adapterKind", view.adapter_kind),
        _xml_property("resourceKind", view.resource_kind),
        _xml_property("rollUpType", roll_up_type),
        _xml_property("rollUpCount", "1"),
        '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>',
        _xml_property("isProperty", "false"),
        _xml_property("displayName", col.display_name),
        _xml_property("addTimestampAsColumn", "false"),
        _xml_property("isShowRelativeTimestamp", "false"),
    ]
    return "<Item><Value>" + "".join(props) + "</Value></Item>"


def _render_summary_infos(view: ViewDef) -> str:
    """Render the summaryInfos XML block for a view's summary/totals row."""
    if not view.summary:
        return ""
    indexes = view.summary.column_indexes
    if indexes is None:
        indexes = list(range(len(view.columns)))
    idx_items = "".join(f'<Item value="{i}"/>' for i in indexes)
    return (
        '<Property name="summaryInfos"><List><Item><Value>'
        f'{_xml_property("displayName", view.summary.display_name)}'
        f'{_xml_property("aggregation", view.summary.aggregation)}'
        f'<Property name="attributeIndexes"><List>{idx_items}</List></Property>'
        '</Value></Item></List></Property>'
    )


def _render_view_def_fragment(view: ViewDef) -> str:
    items = "".join(_xml_attribute_item(view, c, i) for i, c in enumerate(view.columns))
    summary = _render_summary_infos(view)
    return (
        f'<ViewDef id="{view.id}">'
        f"<Title>{escape(view.name)}</Title>"
        f"<Description>{escape(view.description)}</Description>"
        f'<SubjectType adapterKind="{escape(view.adapter_kind)}" resourceKind="{escape(view.resource_kind)}" type="descendant"/>'
        f'<SubjectType adapterKind="{escape(view.adapter_kind)}" resourceKind="{escape(view.resource_kind)}" type="self"/>'
        "<Usage>dashboard</Usage><Usage>report</Usage><Usage>details</Usage><Usage>content</Usage>"
        "<Controls>"
        '<Control id="time-interval-selector_id_1" type="time-interval-selector" visible="false">'
        '<Property name="advancedTimeMode" value="false"/>'
        '<Property name="unit" value="HOURS"/>'
        '<Property name="count" value="24"/>'
        "</Control>"
        '<Control id="attributes-selector_id_1" type="attributes-selector" visible="false">'
        f'<Property name="attributeInfos"><List>{items}</List></Property>'
        f'{summary}'
        "</Control>"
        '<Control id="pagination-control_id_1" type="pagination-control" visible="true">'
        '<Property name="start" value="0"/>'
        '<Property name="size" value="500"/>'
        "</Control>"
        '<Control id="metadata_id_1" type="metadata" visible="false">'
        '<Property name="maxPointsCount" value="5000"/>'
        '<Property name="hideObjectNameColumn" value="false"/>'
        '<Property name="listTopResultSize" value="-1"/>'
        '<Property name="includeResourceCreationTime" value="false"/>'
        "</Control>"
        "</Controls>"
        '<DataProviders><DataProvider dataType="list-view" id="list-view_id_1"/></DataProviders>'
        '<Presentation type="list"/>'
        "</ViewDef>"
    )


def render_views_xml(views: list[ViewDef]) -> str:
    """Render one or more ViewDefs into the single content.xml the
    VCF Ops content importer expects inside views.zip."""
    fragments = "".join(_render_view_def_fragment(v) for v in views)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<Content><Views>{fragments}</Views></Content>"
    )


# ---------------- Dashboard (JSON) ----------------

def _resource_list_widget(w: Widget, kind_index: dict[tuple[str, str], int]) -> dict:
    kinds = [
        f"resourceKind:id:{kind_index[(rk.adapter_kind, rk.resource_kind)]}_::_"
        for rk in w.resource_kinds
    ]
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": {"x": w.coords["x"], "y": w.coords["y"], "w": w.coords["w"], "h": w.coords["h"]},
        "type": "ResourceList",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": [],
            "refreshContent": {"refreshContent": False},
            "relationshipMode": {"relationshipMode": 0},
            "additionalColumns": [],
            "title": w.title,
            "mode": "all",
            "filterMode": "tagPicker",
            "tagFilter": {
                "path": [f"/source/kind/kind:{k}" for k in kinds],
                "value": {
                    "bus": [], "adapterKind": [], "kind": kinds,
                    "exclaim": False, "healthRange": [], "maintenanceSchedule": [],
                    "adapterInstance": [], "collector": [], "tier": [],
                    "state": [], "tag": [], "day": [], "status": [],
                },
            },
            "depth": 1,
            "customFilter": {"filter": [], "excludedResources": None, "includedResources": None},
            "selectFirstRow": {"selectFirstRow": True},
            "selfProvider": {"selfProvider": False},
        },
        "height": 600,
    }


def _view_widget(w: Widget, view: ViewDef, kind_index: dict[tuple[str, str], int],
                  resource_index: dict[tuple[str, str], int]) -> dict:
    # A self-provider View widget enumerates its own subject set instead
    # of waiting for an incoming interaction. Ops requires the widget to
    # be pinned to a container resource — typically `vSphere World` for
    # VMWARE subjects — whose descendants the view walks.
    #
    # The `resourceKindId` field format is `<6-digit prefix><adapterKey>
    # <resourceKey>`. The 6-digit prefix is **per adapter kind**, not
    # dashboard-local — it's a stable Ops-internal identifier that is
    # the same across every instance and every dashboard. Harvested
    # empirically from the reference bundles (brockpeterson +
    # AriaOperationsContent + tkopton) by grepping every dashboard.json
    # for `resourceKindId` values. A dashboard that emits a wrong
    # prefix (e.g. `000000`) installs cleanly but the widget fails to
    # render at view time with no diagnostic.
    if w.self_provider and w.pin:
        pin_key = (w.pin.adapter_kind, w.pin.resource_kind)
        prefix = _ADAPTER_KIND_PREFIX.get(w.pin.adapter_kind)
        if prefix is None:
            raise ValueError(
                f"no known resourceKindId prefix for adapter kind "
                f"{w.pin.adapter_kind!r} — extend _ADAPTER_KIND_PREFIX "
                f"after harvesting from an exported reference dashboard"
            )
        # Widget config.resource.resourceId is 1-indexed into the
        # entries.resource table (0-indexed internalIds). Ops does
        # not resolve resource:id:0 as a valid widget pin — it
        # causes "Please wait being configured" and ISE on edit.
        res_idx = resource_index[pin_key]
        pin_ref = res_idx + 1
        resource = {
            "resourceId": f"resource:id:{pin_ref}_::_",
            "traversalSpecId": "",
            "resourceName": w.pin.resource_kind,
            "resourceKindId": f"{prefix}{w.pin.adapter_kind}{w.pin.resource_kind}",
            "id": f"Ext.vcops.chrome.model.Resource-{pin_ref}",
        }
        self_provider_flag = True
        refresh_content = True
    else:
        resource = None
        self_provider_flag = False
        refresh_content = False
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": {"x": w.coords["x"], "y": w.coords["y"], "w": w.coords["w"], "h": w.coords["h"]},
        "type": "View",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": resource,
            "traversalSpecId": None,
            "refreshContent": {"refreshContent": refresh_content},
            "isUpdatedView": True,
            "chartViewItems": [],
            "selectFirstRow": {"selectFirstRow": True},
            "selfProvider": {"selfProvider": self_provider_flag},
            "title": w.title,
            "viewDefinitionId": view.id,
        },
        "height": 600,
    }


def _build_dashboard_obj(
    dashboard: Dashboard,
    views_by_name: dict[str, ViewDef],
    kind_index: dict[tuple[str, str], int],
    resource_index: dict[tuple[str, str], int],
    owner_user_id: str,
) -> dict:
    widgets_json = []
    for w in dashboard.widgets:
        if w.type == "ResourceList":
            widgets_json.append(_resource_list_widget(w, kind_index))
        elif w.type == "View":
            widgets_json.append(_view_widget(w, views_by_name[w.view_name], kind_index, resource_index))

    widget_id_by_local = {w.local_id: w.widget_id for w in dashboard.widgets}
    interactions_json = [
        {
            "widgetIdProvider": widget_id_by_local[ix.from_local_id],
            "type": ix.type,
            "widgetIdReceiver": widget_id_by_local[ix.to_local_id],
        }
        for ix in dashboard.interactions
    ]

    now_ms = int(time.time() * 1000)
    return {
        # Default dashboards to shared so other Ops users can see them.
        # The framework's audience is "an average vSphere admin needs
        # to find and use this" — private-to-author dashboards defeat
        # the point. Can be overridden per-dashboard via the YAML's
        # `shared:` field.
        "shared": dashboard.shared,
        "temporary": False,
        "hidden": False,
        "creationTime": now_ms,
        "autoswitchEnabled": False,
        "importAttempts": 0,
        "lastUpdateUserId": owner_user_id,
        "columnProportion": "1",
        "importComplete": True,
        "description": dashboard.description,
        "columnCount": 1,
        "userId": owner_user_id,
        "states": [],
        "homeTab": False,
        # Ops folders: the dashboard's `name` field carries a leading
        # "<folder>/" segment, and `namePath` mirrors the folder. This
        # matches the pattern in the vROpsTOP + Troubleshooting VMs +
        # tkopton reference bundles. Ops renders the dashboard in the
        # sidebar under the folder, showing only the portion after the
        # slash as the visible name. `namePath` alone (without the
        # slash in `name`) does NOT place the dashboard in a folder.
        "name": f"{dashboard.name_path}/{dashboard.name}" if dashboard.name_path else dashboard.name,
        "namePath": dashboard.name_path,
        "gridsterMaxColumns": 12,
        "rank": 0,
        "disabled": False,
        "id": dashboard.id,
        "locked": False,
        "dashboardNavigations": {},
        "widgetInteractions": interactions_json,
        "lastUpdateTime": now_ms,
        "widgets": widgets_json,
    }


def render_dashboards_bundle_json(
    dashboards: list[Dashboard],
    views_by_name: dict[str, ViewDef],
    owner_user_id: str,
) -> str:
    """Render all of an owner's dashboards into the single
    dashboard/dashboard.json the VCF Ops content importer expects
    inside dashboards/<ownerUserId>. The `entries.resourceKind` table
    is a shared synthetic-id lookup for every resource kind referenced
    by any ResourceList widget across the bundle."""
    kind_index: dict[tuple[str, str], int] = {}
    for d in dashboards:
        for w in d.widgets:
            for rk in w.resource_kinds:
                key = (rk.adapter_kind, rk.resource_kind)
                if key not in kind_index:
                    kind_index[key] = len(kind_index)
            if w.pin:
                key = (w.pin.adapter_kind, w.pin.resource_kind)
                if key not in kind_index:
                    kind_index[key] = len(kind_index)
    # Build resource index for self-provider pinned widgets. Each
    # unique (adapter_kind, resource_kind) pin gets a 0-based slot
    # in entries.resource[]. Widget configs reference these with
    # 1-based resource:id:<N+1>_::_ values.
    resource_index: dict[tuple[str, str], int] = {}
    for d in dashboards:
        for w in d.widgets:
            if w.self_provider and w.pin:
                key = (w.pin.adapter_kind, w.pin.resource_kind)
                if key not in resource_index:
                    resource_index[key] = len(resource_index)

    entries_resource_kind = [
        {
            "resourceKindKey": rk_kind,
            "internalId": f"resourceKind:id:{idx}_::_",
            "adapterKindKey": rk_adapter,
        }
        for (rk_adapter, rk_kind), idx in kind_index.items()
    ]
    entries_resource = [
        {
            "resourceKindKey": res_kind,
            "internalId": f"resource:id:{idx}_::_",
            "adapterKindKey": res_adapter,
            "identifiers": [],
            "name": res_kind,
        }
        for (res_adapter, res_kind), idx in resource_index.items()
    ]
    entries: dict = {"resourceKind": entries_resource_kind}
    if entries_resource:
        entries["resource"] = entries_resource
    return json.dumps(
        {
            "uuid": str(uuid.uuid4()),
            "entries": entries,
            "dashboards": [
                _build_dashboard_obj(d, views_by_name, kind_index, resource_index, owner_user_id)
                for d in dashboards
            ],
        }
    )
