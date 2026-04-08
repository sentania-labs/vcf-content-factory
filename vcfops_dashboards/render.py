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


# ---------------- View definition (XML) ----------------

def _xml_property(name: str, value: str) -> str:
    return f'<Property name="{escape(name)}" value="{escape(value)}"/>'


def _xml_attribute_item(view: ViewDef, col, idx: int) -> str:
    props = [
        _xml_property("objectType", "RESOURCE"),
        _xml_property("attributeKey", col.attribute),
    ]
    if col.unit:
        props.append(_xml_property("preferredUnitId", col.unit))
    props += [
        _xml_property("isStringAttribute", "false"),
        _xml_property("adapterKind", view.adapter_kind),
        _xml_property("resourceKind", view.resource_kind),
        _xml_property("rollUpType", "AVG"),
        _xml_property("rollUpCount", "1"),
        '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>',
        _xml_property("isProperty", "false"),
        _xml_property("displayName", col.display_name),
        _xml_property("addTimestampAsColumn", "false"),
        _xml_property("isShowRelativeTimestamp", "false"),
    ]
    return "<Item><Value>" + "".join(props) + "</Value></Item>"


def _render_view_def_fragment(view: ViewDef) -> str:
    items = "".join(_xml_attribute_item(view, c, i) for i, c in enumerate(view.columns))
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


def _view_widget(w: Widget, view: ViewDef) -> dict:
    return {
        "collapsed": False,
        "id": w.widget_id,
        "gridsterCoords": {"x": w.coords["x"], "y": w.coords["y"], "w": w.coords["w"], "h": w.coords["h"]},
        "type": "View",
        "title": w.title,
        "config": {
            "refreshInterval": 300,
            "resource": None,
            "traversalSpecId": "",
            "refreshContent": {"refreshContent": False},
            "isUpdatedView": True,
            "chartViewItems": [],
            "selectFirstRow": {"selectFirstRow": True},
            "selfProvider": {"selfProvider": False},
            "title": w.title,
            "viewDefinitionId": view.id,
        },
        "height": 600,
    }


def _build_dashboard_obj(
    dashboard: Dashboard,
    views_by_name: dict[str, ViewDef],
    kind_index: dict[tuple[str, str], int],
    owner_user_id: str,
) -> dict:
    widgets_json = []
    for w in dashboard.widgets:
        if w.type == "ResourceList":
            widgets_json.append(_resource_list_widget(w, kind_index))
        elif w.type == "View":
            widgets_json.append(_view_widget(w, views_by_name[w.view_name]))

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
        "shared": False,
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
        "name": dashboard.name,
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
    entries_resource_kind = [
        {
            "resourceKindKey": rk_kind,
            "internalId": f"resourceKind:id:{idx}_::_",
            "adapterKindKey": rk_adapter,
        }
        for (rk_adapter, rk_kind), idx in kind_index.items()
    ]
    return json.dumps(
        {
            "uuid": str(uuid.uuid4()),
            "entries": {"resourceKind": entries_resource_kind},
            "dashboards": [
                _build_dashboard_obj(d, views_by_name, kind_index, owner_user_id)
                for d in dashboards
            ],
        }
    )
