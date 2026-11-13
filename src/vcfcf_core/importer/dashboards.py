"""Dashboard JSON -> factory dashboard YAML (every field of the 2026-11-12 schema).

Wire format and YAML: ``knowledge/context/wire-formats/dashboard_fidelity_wire_format.md``.
One YAML per dashboard: a source file with an ``{entries, dashboards[]}``
envelope of many dashboards becomes one YAML each; the shared ``entries``
table resolves the synthetic ``resourceKind:id:<n>_::_`` and
``resource:id:<n>_::_`` references here, and the renderer rebuilds a table
per dashboard.

Widget ids are the product's; YAML names a widget by a local id (``w<i>``,
its position), and the renderer derives the wire id from the dashboard id
and the local id. So every reference to a widget (interactions, Section
members, navigations, ``{self}`` in a state value) is rewritten to the local
id, and a verification maps the source widget ids by position.

Documented as not modeled (dashboard fidelity doc), recorded as losses at
their exact flat paths: ``adapterName`` (install ownership, set by the pak
builder), navigation entries keyed by a widget that is not on the dashboard
(no widget can fire them), the absolute-date time range, ``ext-element``
UI residue states, a ``config.widgetId`` naming no widget of the dashboard
(clone residue; ``accounting``) and surrounding whitespace on the display
strings the loader strips (``accounting.STRIPPED_TEXT``: description,
widget titles, labels, tab names, TextDisplay HTML), accepted only where the
render is the source stripped.
Anything else the schema cannot carry stops the dashboard with a TOOLSET
GAP; ``accounting.account`` classifies every source key after mapping (the
constants the renderer writes are rows there).
"""
from __future__ import annotations

import re
from decimal import Decimal
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from ..dashboards.loader import (
    DASHBOARD_TIME_RANGES,
    WIDGET_STATE_PREFIXES,
    WIDGET_STATE_SELF_TOKEN,
    _WIDGET_STATE_VALUE_RE,
)
from . import flat as _flat
from .accounting import account
from .model import MappedObject, MappingError, Mark, documented_loss, gap_error, wire_number
from .refs import NavRef, Ref

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
TIME_BY_WIRE = {v: k for k, v in DASHBOARD_TIME_RANGES.items()}
#: The pak ``dashboards/<Folder>/dashboard.json`` folders that bind a
#: Summary page (``summary_for: VMWARE:<Folder>``).
SUMMARY_FOLDERS = {"VMFolder", "HostFolder", "DatastoreFolder", "NetworkFolder",
                   "VmwareDistributedVirtualSwitch", "DistributedVirtualPortgroup"}

#: Dashboard keys the renderer writes as constants: an absent one is not
#: modeled (the render always writes it). Present values are checked by the
#: accounting table.
_RENDER_CONSTANTS = ("autoswitchEnabled", "importAttempts", "importComplete", "homeTab", "gridsterMaxColumns",
                     "rank", "locked")
_WIRE_TYPES = {"IntSummaryAlertVolume": "AlertVolume"}
SUPPORTED_WIDGETS = {"View", "TextDisplay", "Scoreboard", "MetricChart", "HealthChart", "ParetoAnalysis",
                     "Heatmap", "ResourceRelationshipAdvanced", "AlertList", "Section", "ResourceList",
                     "ProblemAlertsList", "PropertyList", "AlertVolume"}
_SM_IN_KEY = re.compile(r"sm_(" + UUID + r")")


def split_rkid(s: str) -> Tuple[str, str]:
    """``'002006VMWAREvSphere World'`` -> ``('VMWARE', 'vSphere World')``."""
    m = re.match(r"^0020(\d\d)(.*)$", s or "")
    if not m:
        raise MappingError(f"resource kind id {s!r} is not in the 0020<nn><adapter><kind> form")
    n = int(m.group(1))
    return m.group(2)[:n], m.group(2)[n:]


def _num(v):
    """A numeric string (a metric entry ``maxValue``) as a YAML number,
    exactly (``model.wire_number``; an integral decimal such as ``"25.0"``
    becomes 25, as before)."""
    n = wire_number(v, "maxValue", "dashboard")
    if isinstance(n, float) and n.is_integer():
        return int(Decimal(repr(n)))
    return n


def local_widget_ids(db: dict) -> Dict[str, str]:
    """Source widget id -> YAML local id (``w<position>``)."""
    return {w.get("id"): f"w{i}" for i, w in enumerate(db.get("widgets") or [])}


def strip_folder(name: str, name_path: Optional[str]) -> str:
    if name_path and name.startswith(name_path + "/"):
        return name[len(name_path) + 1:]
    return name


class _DashMapper:
    def __init__(self, db: dict, context: dict, location: str):
        self.db = db
        self.ctx = context
        self.location = location
        self.losses = []
        self.notes: List[str] = []
        entries = context.get("entries") or {}
        self.rk = {e.get("internalId"): (e.get("adapterKindKey"), e.get("resourceKindKey"))
                   for e in entries.get("resourceKind", []) or []}
        self.res = {e.get("internalId"): (e.get("adapterKindKey"), e.get("resourceKindKey"), e.get("name"))
                    for e in entries.get("resource", []) or []}
        self.lid = local_widget_ids(db)

    def loss(self, msg: str) -> None:
        """A feature the schema cannot carry and the docs do not list: the
        dashboard stops with a TOOLSET GAP."""
        raise gap_error(msg, "dashboard")

    def doc(self, cls: str, msg: str, marks) -> None:
        documented_loss(self.losses, cls, msg, list(marks))

    def state_path(self, base: str, key: str) -> str:
        """The flat path of a ``states[]`` entry (``flat`` grammar)."""
        own = {str(w.get("id")).lower(): f"w{i}" for i, w in enumerate(self.db.get("widgets") or [])
               if isinstance(w, dict)}
        k = re.sub(UUID, lambda m: own.get(m.group(0).lower(), m.group(0).lower()), key)
        return f"{base}.states{{{k}}}"

    def kind(self, rid, where: str) -> Tuple[str, str]:
        if rid not in self.rk:
            raise MappingError(f"{where}: resource kind reference {rid!r} is not in the entries table")
        return self.rk[rid]

    # ----------------------------------------------------------- dashboard
    def map(self) -> Dict[str, object]:
        db = self.db
        y: Dict[str, object] = OrderedDict()
        y["id"] = db["id"]
        name, npath = db.get("name", ""), db.get("namePath")
        if not isinstance(name, str) or (npath is not None and not isinstance(npath, str)):
            raise MappingError(f"dashboard name {name!r} / namePath {npath!r} are not strings")
        omit: List[str] = []
        if npath and not name.startswith(npath + "/"):
            omit.append("folder_in_name")
        y["name"] = strip_folder(name, npath)
        desc = db.get("description", "") or ""
        if not isinstance(desc, str):
            self.loss(f"description {desc!r} is not a string")
        # Surrounding whitespace the loader strips: accounting.STRIPPED_TEXT.
        y["description"] = desc
        y["name_path"] = npath or ""
        if "namePath" not in db:
            omit.append("name_path")
        if "temporary" not in db:
            omit.append("temporary")
        elif db.get("temporary") is not False:
            self.loss(f"temporary={db.get('temporary')!r} is not modeled (renders false)")
        if npath is not None and npath != npath.strip():
            self.loss("namePath with leading or trailing whitespace (the dashboard loader strips it)")
        if "widgetInteractions" not in db:
            omit.append("widget_interactions")
        if omit:
            y["omit"] = omit
        y["shared"] = bool(db.get("shared", False))
        y["hidden"] = bool(db.get("hidden", False))
        if db.get("disabled"):
            y["disabled"] = True
        states = db.get("states") or []
        if not isinstance(states, list) or any(not isinstance(s, dict) for s in states):
            self.loss("dashboard states that are not a list of objects")
        kept_states = 0
        for s in states:
            key = str(s.get("key", ""))
            sp = self.state_path(_flat.DASH, key)
            if set(s) - {"key", "value"}:
                self.loss(f"dashboard state {key!r} with keys {sorted(set(s) - {'key', 'value'})}")
            if (key == f"permDashboardTime_dashboard_{db['id']}" and s.get("value") in TIME_BY_WIRE
                    and "time_range" not in y):
                y["time_range"] = TIME_BY_WIRE[s["value"]]
                kept_states += 1
            elif key.startswith("permDashboardTime_dashboard_"):
                self.doc("absolute-date time range",
                         f"dashboard absolute-date time range {s.get('value')!r} is not modeled (only the relative "
                         f"ranges are; dashboard fidelity doc §Dashboard level)", [Mark(sp, "missing", subtree=True)])
            elif key.startswith("ext-element-"):
                self.doc("ext-element UI residue", f"dashboard state {key!r} (ext-element UI residue) is not modeled "
                         f"(dashboard fidelity doc §Dashboard level)", [Mark(sp, "missing", subtree=True)])
            else:
                self.loss(f"dashboard state {key!r} is not modeled")
        if states and not kept_states:
            # the render then writes states: []
            for x in self.losses:
                if x.cls in ("absolute-date time range", "ext-element UI residue"):
                    x.marks.append(Mark(f"{_flat.DASH}.states", "extra", empty_only=True))
        if "editAllowed" in db:
            y["edit_allowed"] = db["editAllowed"]
        if "docCenterKey" in db:
            y["doc_center_key"] = db["docCenterKey"]
        if db.get("columnProportion", "1") != "1":
            y["column_proportion"] = db["columnProportion"]
        if db.get("columnCount", 1) != 1:
            y["column_count"] = db["columnCount"]
        if self.ctx.get("folder") in SUMMARY_FOLDERS:
            y["summary_for"] = f"VMWARE:{self.ctx['folder']}"
        for k in _RENDER_CONSTANTS:
            if k not in db:
                self.loss(f"absent {k} is not modeled (the renderer always writes it)")
        navs = db.get("dashboardNavigations") or {}
        if not isinstance(navs, dict):
            self.loss("dashboardNavigations that is not a mapping is not modeled")
        if not isinstance(db.get("widgets") or [], list):
            self.loss("widgets that is not a list is not modeled")
        widgets = []
        for i, w in enumerate(db.get("widgets") or []):
            widgets.append(self.widget(w, i, navs))
        y["widgets"] = widgets
        inter = []
        for ix in db.get("widgetInteractions") or []:
            if not isinstance(ix, dict) or set(ix) - {"widgetIdProvider", "widgetIdReceiver", "type"}:
                self.loss(f"interaction {ix!r} with keys other than widgetIdProvider, widgetIdReceiver, type")
            a, b = ix.get("widgetIdProvider"), ix.get("widgetIdReceiver")
            if a not in self.lid or b not in self.lid:
                self.loss(f"interaction {a} -> {b} names a widget not on the dashboard (not modeled)")
                continue
            inter.append(OrderedDict([("from", self.lid[a]), ("to", self.lid[b]), ("type", ix.get("type"))]))
        y["interactions"] = inter
        return y

    # ------------------------------------------------------------- pieces
    def metric(self, m: dict, where: str) -> Dict[str, object]:
        ak, k = self.kind(m.get("resourceKindId"), where)
        e: Dict[str, object] = OrderedDict(adapter_kind=ak, resource_kind=k,
                                           metric_key=m.get("metricKey"), metric_name=m.get("metricName"))
        if m.get("isStringMetric"):
            e["is_string_metric"] = True
        e["color_method"] = m.get("colorMethod")
        if m.get("colorMethod") == 0:
            for b in ("yellow", "orange", "red"):
                if m.get(b + "Bound") is not None:
                    e[b + "_bound"] = m[b + "Bound"]
        omit = []
        if "label" in m:
            if m["label"]:
                e["label"] = m["label"]
        else:
            omit.append("label")
        if "maxValue" in m:
            if m["maxValue"] not in ("", None):
                e["max_value"] = _num(m["maxValue"])
        else:
            omit.append("max_value")
        if "handleOldColoring" not in m:
            omit.append("handle_old_coloring")
        if "link" not in m:
            omit.append("link")
        if "unit" in m or "metricUnitId" in m:
            if m.get("metricUnitId") not in (None, ""):
                e["unit_id"] = m["metricUnitId"]
            if "unit" in m and m["unit"] is not None:
                e["unit"] = m["unit"]
        else:
            omit.append("unit")
        for wk, yk in (("link", "link"), ("labelLocalized", "label_localized"), ("labelOrig", "label_orig"),
                       ("metricUnit", "metric_unit"), ("defUnit", "def_unit"),
                       ("resourceKindName", "resource_kind_name")):
            if wk in m:
                if wk == "link" and m[wk] == "":
                    continue
                e[yk] = m[wk]
        if omit:
            e["omit"] = omit
        return e

    def tag_filter(self, t: dict, where: str) -> Dict[str, object]:
        v = t.get("value") or {}
        if not isinstance(v, dict):
            self.loss(f"{where}: tag filter value {v!r} is not an object")
        out: Dict[str, object] = OrderedDict()
        if v.get("kind"):
            out["resource_kinds"] = [OrderedDict(zip(("adapter_kind", "resource_kind"), self.kind(k, where)))
                                     for k in v["kind"]]
        if v.get("state"):
            out["states"] = list(v["state"])
        if v.get("status"):
            out["statuses"] = list(v["status"])
        for k, val in v.items():
            if k not in ("kind", "state", "status") and val not in ([], None, False):
                self.loss(f"{where}: tag filter {k}={val!r} is not modeled")
        return out

    def pin_from_resource(self, rid, where: str) -> Dict[str, object]:
        if not isinstance(rid, str):
            raise MappingError(f"{where}: resource reference {rid!r} is not an entries reference")
        if rid not in self.res:
            raise MappingError(f"{where}: resource reference {rid!r} is not in the entries table")
        ak, k, nm = self.res[rid]
        pin: Dict[str, object] = OrderedDict(adapter_kind=ak, resource_kind=k)
        if nm != k:
            pin["name"] = nm
        return pin

    # -------------------------------------------------------------- widget
    def widget(self, w: dict, idx: int, navs: dict) -> Dict[str, object]:
        if not isinstance(w, dict):
            raise MappingError(f"widget {idx} is not an object")
        c = w.get("config") or {}
        if not isinstance(c, dict):
            raise MappingError(f"widget {idx}: config is not an object")
        t = _WIRE_TYPES.get(w.get("type"), w.get("type"))
        where = f"widget {idx} ({t} {w.get('title', '')!r})"
        if t not in SUPPORTED_WIDGETS:
            raise MappingError(f"{where}: widget type {w.get('type')!r} is not modeled by the factory YAML",
                               gap={"what": f"dashboard widget type {w.get('type')}"})
        y: Dict[str, object] = OrderedDict(id=self.lid[w.get("id")], type=t, title=w.get("title", ""))
        gc = dict(w.get("gridsterCoords") or {})
        y["coords"] = gc
        ui: Dict[str, object] = OrderedDict()
        if t == "Section":
            y["coords"] = OrderedDict(x=gc.get("x", 1), y=gc.get("y", 1))
            if gc.get("w", 12) != 12 or gc.get("h", 1) != 1:
                self.loss(f"{where}: Section coords w/h other than 12/1 are not modeled")
            if w.get("collapsed"):
                y["collapsed"] = True
            members = []
            for m in c.get("widgets") or []:
                if m in self.lid:
                    members.append(self.lid[m])
                else:
                    self.loss(f"{where}: Section member {m} is not on the dashboard (not modeled)")
            y["widgets"] = members
            if c.get("description"):
                y["description"] = c["description"]
            if c.get("titleLocalized") != w.get("title"):
                y["title_localized"] = c.get("titleLocalized")
            if w.get("height", 0) != 0:
                self.loss(f"{where}: Section height {w.get('height')} is not modeled (renders 0)")
        else:
            if "collapsed" in w and w.get("collapsed"):
                y["collapsed"] = True
            if "description" in c:
                y["description"] = c["description"]
            if "titleLocalized" in c:
                y["title_localized"] = c["titleLocalized"]
            if w.get("height", 600) != 600:
                ui["height"] = w["height"]
        if "viewDetails" in c:
            y["view_details"] = c["viewDetails"]
        if "state" in w:
            ui["state"] = w["state"]
        if "tabId" in w:
            if w["tabId"] != self.db["id"]:
                self.loss(f"{where}: tabId {w['tabId']} is not the dashboard id (not modeled)")
            ui["tab_id"] = True
        if "x" in w or "y" in w:
            ui["legacy_xy"] = OrderedDict(x=w.get("x"), y=w.get("y"))
        if w.get("states"):
            sts = []
            allowed = WIDGET_STATE_PREFIXES.get(t, frozenset())
            own = f"widget_{self.db['id']}_{w.get('id')}"
            for s in w["states"]:
                m = re.match(r"^(.*?)widget_(%s)_(%s)$" % (UUID, UUID), str(s.get("key", "")))
                if not m or f"widget_{m.group(2)}_{m.group(3)}" != own:
                    self.loss(f"{where}: widget state {s.get('key')!r} is not keyed by this widget (not modeled)")
                    continue
                value = str(s.get("value", ""))
                if m.group(1) not in allowed:
                    self.loss(f"{where}: widget state prefix {m.group(1)!r} is not in the {t} vocabulary (not modeled)")
                    continue
                value = value.replace(own, "{self}")
                # The loader accepts the {self} token beside the value alphabet.
                if not _WIDGET_STATE_VALUE_RE.match(value.replace(WIDGET_STATE_SELF_TOKEN, "widget_self")):
                    self.loss(f"{where}: widget state {m.group(1)!r} value is outside the accepted alphabet (not modeled)")
                    continue
                sts.append(OrderedDict(key=m.group(1), value=value))
            if sts:
                ui["states"] = sts
        if "widgetId" in c:
            ui["widget_id"] = True
        if "key" in c:
            ui["config_key"] = True
        if "viewType" in c:
            ui["view_type"] = c["viewType"]
        if "undefined" in c:
            ui["undefined"] = c["undefined"]
        if isinstance(c.get("customFilter"), dict) and "filterMode" in c["customFilter"]:
            ui["custom_filter_mode"] = c["customFilter"]["filterMode"]
        sp = (c.get("selfProvider") or {}).get("selfProvider", False) if isinstance(c.get("selfProvider"), dict) else False
        nav = navs.get(w.get("id"))
        if nav:
            out = []
            for n in nav:
                if not isinstance(n, dict) or set(n) - {"id", "widgets"}:
                    self.loss(f"{where}: navigation entry keys {sorted(n) if isinstance(n, dict) else n!r} other "
                              f"than id and widgets are not modeled")
                rx = n.get("widgets") or []
                if not isinstance(rx, list) or any(not isinstance(x, dict) or set(x) - {"id", "interactionType"}
                                                   for x in rx):
                    self.loss(f"{where}: navigation receiving widgets {rx!r} are not modeled")
                out.append(NavRef(dashboard_id=str(n.get("id")), widget_ids=[str(x.get("id")) for x in rx]))
            y["navigations"] = out
        elif nav == []:
            ui["empty_navigations"] = True

        getattr(self, f"w_{t}")(w, c, y, ui, sp, where)
        if ui:
            y["ui"] = ui
        return y

    def w_View(self, w, c, y, ui, sp, where):
        vid = c.get("viewDefinitionId")
        if not vid:
            raise MappingError(f"{where}: View widget without viewDefinitionId")
        y["view"] = Ref("view", str(vid), form="name", where=where)
        if c.get("chartViewItems"):
            y["chart_view_items"] = c["chartViewItems"]
        y["select_first_row"] = (c.get("selectFirstRow") or {}).get("selectFirstRow", True)
        if sp:
            y["self_provider"] = True
        r = c.get("resource")
        if isinstance(r, dict):
            ak, k = split_rkid(r.get("resourceKindId", ""))
            pin: Dict[str, object] = OrderedDict(adapter_kind=ak, resource_kind=k)
            if r.get("resourceName") != k:
                pin["name"] = r.get("resourceName")
            if r.get("traversalSpecId"):
                pin["traversal_spec"] = r["traversalSpecId"]
            y["pin"] = pin
        if c.get("traversalSpecId") is not None:
            y["traversal_spec_id"] = c["traversalSpecId"]

    def w_TextDisplay(self, w, c, y, ui, sp, where):
        y["html"] = c.get("editorData", "")
        for k, v in (("locationFile", ""), ("locationUrl", ""), ("viewModeHTML", True)):
            if c.get(k, v) != v:
                self.loss(f"{where}: TextDisplay {k}={c.get(k)!r} is not modeled")

    def _metrics_common(self, w, c, y, sp, where):
        metric = c.get("metric") or {}
        y["metrics"] = [self.metric(m, where) for m in metric.get("resourceKindMetrics") or []]
        if sp:
            y["self_provider"] = True
        if "subMode" not in metric:
            y.setdefault("omit", []).append("sub_mode")

    def _resource_metrics(self, metric: dict, y, where: str) -> None:
        """A resource-mode Scoreboard: every entry pinned to one resource
        (``metric_mode: resource`` + ``resource:``)."""
        entries = metric.get("resourceMetrics") or []
        rids = {m.get("resourceId") for m in entries}
        if len(rids) != 1 or metric.get("resourceKindMetrics"):
            self.loss(f"{where}: a resource-mode Scoreboard over {len(rids)} resources is not modeled")
        rid = next(iter(rids))
        if rid not in self.res:
            raise MappingError(f"{where}: resource reference {rid!r} is not in the entries table")
        ak, rk, nm = self.res[rid]
        y["metric_mode"] = "resource"
        y["resource"] = OrderedDict(adapter_kind=ak, resource_kind=rk, name=nm)
        out = []
        for m in entries:
            if split_rkid(m.get("resourceKindId", "")) != (ak, rk) or m.get("resourceName") != nm:
                self.loss(f"{where}: resource-mode entry {m.get('metricKey')!r} names another kind or resource")
            e: Dict[str, object] = OrderedDict(metric_key=m.get("metricKey"), metric_name=m.get("metricName"))
            if m.get("isStringMetric"):
                e["is_string_metric"] = True
            e["color_method"] = m.get("colorMethod")
            if m.get("colorMethod") == 0:
                for b in ("yellow", "orange", "red"):
                    if m.get(b + "Bound") is not None:
                        e[b + "_bound"] = m[b + "Bound"]
            for k, v in (("handleOldColoring", False), ("link", "")):
                if m.get(k, v) != v:
                    self.loss(f"{where}: resource-mode entry {k}={m.get(k)!r} is not modeled")
            omit = []
            if "label" in m:
                if m["label"] is not None:
                    e["label"] = m["label"]
            else:
                omit.append("label")
            if "maxValue" in m:
                if m["maxValue"] not in ("", None):
                    e["max_value"] = _num(m["maxValue"])
            else:
                omit.append("max_value")
            for wk, ok in (("handleOldColoring", "handle_old_coloring"), ("link", "link")):
                if wk not in m:
                    omit.append(ok)
            if "unit" in m or "metricUnitId" in m:
                if m.get("metricUnitId") not in (None, ""):
                    e["unit_id"] = m["metricUnitId"]
                if m.get("unit") not in (None, ""):
                    e["unit"] = m["unit"]
            else:
                omit.append("unit")
            for wk, yk in (("labelLocalized", "label_localized"), ("labelOrig", "label_orig"),
                           ("metricUnit", "metric_unit"), ("defUnit", "def_unit")):
                if wk in m:
                    e[yk] = m[wk]
            if omit:
                e["omit"] = omit
            out.append(e)
        y["metrics"] = out

    def w_Scoreboard(self, w, c, y, ui, sp, where):
        metric = c.get("metric") or {}
        if metric.get("mode") == "resource" or metric.get("resourceMetrics"):
            self._resource_metrics(metric, y, where)
            if sp:
                y["self_provider"] = True
        else:
            self._metrics_common(w, c, y, sp, where)
        y["visual_theme"] = c.get("visualTheme")
        y["layout_mode"] = (c.get("mode") or {}).get("layoutMode")
        y["box_columns"] = c.get("boxColumns")
        if c.get("boxHeight") is not None:
            y["box_height"] = c["boxHeight"]
        y["value_size"] = c.get("valueSize")
        y["label_size"] = c.get("labelSize")
        y["round_decimals"] = c.get("roundDecimals")
        y["max_cell_count"] = c.get("maxCellCount")
        y["show_sparkline"] = (c.get("showSparkline") or {}).get("showSparkline")
        y["show_resource_name"] = (c.get("showResourceName") or {}).get("showResourceName")
        y["show_metric_name"] = (c.get("showMetricName") or {}).get("showMetricName")
        y["show_metric_unit"] = (c.get("showMetricUnit") or {}).get("showMetricUnit")
        y["show_dt"] = (c.get("showDT") or {}).get("showDT")
        if c.get("periodLength") is not None:
            y["period_length"] = c["periodLength"]
        y["refresh_content"] = (c.get("refreshContent") or {}).get("refreshContent")
        y["old_metric_values"] = c.get("oldMetricValues")
        if "showRemaining" in c:
            y["show_remaining"] = c["showRemaining"]
            y["show_percent_text"] = c.get("showPercentText")
            y["focus_on_percent"] = c.get("focusOnPercent")
            if c.get("visualTheme") != 9:
                ui["gauge_switches"] = True
        if c.get("resource"):
            y["pin"] = self.pin_from_resource(c["resource"][0].get("id"), where)
            y["pin_resource"] = True

    def w_MetricChart(self, w, c, y, ui, sp, where):
        self._metrics_common(w, c, y, sp, where)
        rc = (c.get("refreshContent") or {}).get("refreshContent")
        if rc is not True:
            y["refresh_content"] = rc
        rmo = c.get("relationshipMode") or {}
        rm = rmo.get("relationshipMode") if isinstance(rmo, dict) else rmo
        if isinstance(rm, list):
            # 9.1.1 built-ins ("vSAN Performance"): the array form the renderer
            # writes for Heatmap / AlertList; MetricChart renders a scalar.
            self.loss(f"{where}: MetricChart relationshipMode as a list {rm!r} (the renderer writes a scalar "
                      f"-1, 0 or 1)")
        if rm:
            names = {-1: "children", 1: "parents"}
            if rm not in names:
                raise MappingError(f"{where}: MetricChart relationshipMode {rm!r} is not modeled")
            y["relationship_mode"] = names[rm]

    def w_HealthChart(self, w, c, y, ui, sp, where):
        ak, k = self.kind(c.get("resourceKindId"), where)
        y.update(OrderedDict(
            adapter_kind=ak, resource_kind=k, metric_key=c.get("metricKey"),
            metric_name=c.get("metricName"), metric_full_name=c.get("metricFullName"),
            mode=c.get("mode"), depth=c.get("depth"), chart_height=c.get("chartHeight"),
            pagination_number=c.get("paginationNumber"),
            sort_by_dir=(c.get("sortByDir") or {}).get("orderByDir"),
            yellow_bound=c.get("yellowBound"), orange_bound=c.get("orangeBound"), red_bound=c.get("redBound"),
            show_resource_name=(c.get("showResourceName") or {}).get("showResourceName"),
        ))
        if sp:
            y["self_provider"] = True
        if c.get("resource"):
            y["pin"] = self.pin_from_resource(c["resource"][0].get("id"), where)
        if (c.get("relationshipMode") or {}).get("relationshipMode") == -1:
            y["relationship_mode"] = "children"
        if isinstance(c.get("tagFilter"), dict):
            y["tag_filter"] = self.tag_filter(c["tagFilter"], where)

    def w_ParetoAnalysis(self, w, c, y, ui, sp, where):
        rks = c.get("resourceKind") or []
        if not rks:
            raise MappingError(f"{where}: ParetoAnalysis without resourceKind")
        ak, k = self.kind(rks[0].get("id"), where)
        metric = c.get("metric") or {}
        y.update(OrderedDict(
            adapter_kind=ak, resource_kind=k, metric_key=metric.get("metricKey"),
            metric_name=metric.get("name"), mode=c.get("mode"), top_n=c.get("barsCount"),
            top_option=c.get("topOption"), depth=c.get("depth"),
            regeneration_time=c.get("regenerationTime"), round_decimals=c.get("roundDecimals"),
        ))
        if c.get("metricName") != metric.get("name"):
            y["metric_label"] = c.get("metricName")
        if (c.get("refreshContent") or {}).get("refreshContent") is not True:
            y["refresh_content"] = False
        if (c.get("relationshipMode") or {}).get("relationshipMode") == -1:
            y["relationship_mode"] = "children"
        if "maxValue" in c:
            y["max_value"] = c["maxValue"]
        mu = c.get("metricUnit") or {}
        if (mu.get("metricUnitId"), mu.get("metricUnitName")) != (-1, "Auto"):
            y["metric_unit"] = OrderedDict(id=mu.get("metricUnitId"), name=mu.get("metricUnitName"))
        if "yellowBound" in c:
            y["yellow_bound"], y["orange_bound"], y["red_bound"] = c["yellowBound"], c.get("orangeBound"), c.get("redBound")
        if c.get("percentileValue") is not None:
            y["percentile_value"] = c["percentileValue"]
        if c.get("additionalColumns"):
            cols = []
            for a in c["additionalColumns"]:
                cak, ck = self.kind(a.get("resourceKindId"), where)
                cols.append(OrderedDict(metric_key=a.get("metricKey"), metric_name=a.get("metricName"),
                                        label=a.get("boxLabel"), adapter_kind=cak, resource_kind=ck))
            y["additional_columns"] = cols
        if c.get("bottomN"):
            y["bottom_n"] = c["bottomN"]
        if sp:
            y["self_provider"] = True

    def w_Heatmap(self, w, c, y, ui, sp, where):
        y["mode"] = c.get("mode")
        y["depth"] = c.get("depth")
        if (c.get("relationshipMode") or {}).get("relationshipMode") == -1:
            y["relationship_mode"] = "children"
        if c.get("value"):
            y["selected_tab"] = c["value"]
        if sp:
            y["self_provider"] = True
        tabs = []
        for ti, tb in enumerate(c.get("configs") or []):
            twhere = f"{where} tab {ti}"
            tak, tk = self.kind(tb.get("resourceKind"), twhere)
            gb = tb.get("groupBy") or {}
            gak, gk = self.kind(gb.get("typeId"), twhere)
            tab: Dict[str, object] = OrderedDict(
                name=tb.get("name"), adapter_kind=tak, resource_kind=tk,
                color_by=OrderedDict(metric_key=(tb.get("colorBy") or {}).get("metricKey"),
                                     label=(tb.get("colorBy") or {}).get("value")),
                size_by=OrderedDict(metric_key=(tb.get("sizeBy") or {}).get("metricKey"),
                                    label=(tb.get("sizeBy") or {}).get("value")),
                group_by=OrderedDict(adapter_kind=gak, resource_kind=gk, text=gb.get("text"),
                                     parent_text=gb.get("parentText")),
                color=OrderedDict(thresholds=(tb.get("color") or {}).get("thresholds")),
                solid_coloring=tb.get("solidColoring"), focus_on_groups=tb.get("focusOnGroups"),
            )
            omit = []
            color = tb.get("color") or {}
            if "minValue" in color:
                tab["color"]["min_value"] = color["minValue"]
            else:
                omit.append("color_min_value")
            if "maxValue" in color:
                tab["color"]["max_value"] = color["maxValue"]
            if "adapterKind" not in gb:
                omit.append("group_by_kind_keys")
            for wk, yk in (("nameLocalized", "name_localized"), ("nameOrig", "name_orig")):
                if wk in tb:
                    tab[yk] = tb[wk]
            if "id" in tb:
                tab["model_id"] = True
            if "tagFilter" not in tb:
                omit.append("tag_filter")
            elif isinstance(tb["tagFilter"], dict):
                tab["tag_filter"] = self.tag_filter(tb["tagFilter"], twhere)
            else:
                tab["tag_filter"] = None
            if tb.get("filterMode", "tagPicker") != "tagPicker":
                tab["filter_mode"] = tb["filterMode"]
            cf = tb.get("customFilter", "ABSENT")
            if cf == "ABSENT":
                omit.append("custom_filter")
            elif cf is None:
                tab["custom_filter"] = None
            elif isinstance(cf, dict) and cf.get("filter"):
                groups = []
                for g in cf["filter"]:
                    gak2, gk2 = split_rkid(g.get("resourceKindId", ""))
                    groups.append(OrderedDict(adapter_kind=gak2, resource_kind=gk2, conditions=[
                        OrderedDict(filter_type=ft.get("filterType"), metric_key=ft.get("metricKey"),
                                    metric_name=ft.get("metricName"), condition=ft.get("condition"),
                                    value=(ft.get("metricValue") or {}).get("value"),
                                    string_metric=ft.get("isStringMetric"), metric_unit=ft.get("metricUnit"))
                        for ft in g.get("filterTypes") or []]))
                tab["custom_filter"] = groups
            elif isinstance(cf, dict) and cf == {"filter": [], "excludedResources": None, "includedResources": None}:
                pass  # the renderer's own default: no YAML key
            elif isinstance(cf, dict):
                self.loss(f"{twhere}: custom filter {sorted(cf)} with excluded or included resources is not modeled")
            if omit:
                tab["omit"] = omit
            tabs.append(tab)
        y["configs"] = tabs

    def w_ResourceRelationshipAdvanced(self, w, c, y, ui, sp, where):
        rra: Dict[str, object] = OrderedDict(depth=c.get("depth"), self_provider=sp)
        tf = c.get("tagFilter")
        if isinstance(tf, dict) and (tf.get("value") or {}).get("kind"):
            rra["resource_kinds"] = [OrderedDict(zip(("adapter_kind", "resource_kind"), self.kind(k, where)))
                                     for k in tf["value"]["kind"]]
        elif tf is None:
            y["tag_filter"] = None
        if "paginationNumber" in c:
            rra["pagination_number"] = c["paginationNumber"]
        else:
            y.setdefault("omit", []).append("pagination_number")
        y["resource_relationship_advanced"] = rra
        if "selectFirstRow" in c:
            y["select_first_row"] = (c.get("selectFirstRow") or {}).get("selectFirstRow")
        else:
            y.setdefault("omit", []).append("select_first_row")
        if c.get("relationshipMode") == "":
            ui["blank_relationship_mode"] = True
        if c.get("visualTheme") is False:
            ui["visual_theme_false"] = True

    def w_AlertList(self, w, c, y, ui, sp, where):
        y["criticality"] = c.get("criticalityLevel")
        y["alert_types"] = c.get("type")
        y["status"] = c.get("status")
        y["state"] = c.get("state")
        y["alert_impact"] = c.get("alertImpact")
        y["alert_action"] = c.get("alertAction")
        y["mode"] = c.get("mode")
        y["depth"] = c.get("depth")
        names = {1: "parents", -1: "children", 0: "self"}
        rm = (c.get("relationshipMode") or {}).get("relationshipMode") or []
        if not isinstance(rm, list) or any(x not in names for x in rm):
            raise MappingError(f"{where}: AlertList relationshipMode {rm!r} is not modeled")
        y["relationship_mode"] = [names[x] for x in rm]
        if "alertDefinitions" not in c:
            y.setdefault("omit", []).append("alert_definitions")
        else:
            ad = c.get("alertDefinitions") or []
            if not isinstance(ad, list) or any(not isinstance(a, dict) or set(a) - {"id"} for a in ad):
                # 9.1.1 built-ins ("License Server Health", "vSAN Snapshots and
                # Replica") carry bare id strings; the renderer writes
                # [{"id": <id>}] objects only.
                self.loss(f"{where}: AlertList alertDefinitions {str(ad)[:80]} are not {{id: ...}} objects (the "
                          f"renderer writes [{{\"id\": <id>}}])")
            y["alert_definitions"] = [a.get("id") for a in ad]
        if sp:
            y["self_provider"] = True

    def w_ResourceList(self, w, c, y, ui, sp, where):
        tf = c.get("tagFilter") or {}
        kinds = (tf.get("value") or {}).get("kind") or []
        y["resource_kinds"] = [OrderedDict(zip(("adapter_kind", "resource_kind"), self.kind(k, where)))
                               for k in kinds]
        y["select_first_row"] = (c.get("selectFirstRow") or {}).get("selectFirstRow", True)
        from ..dashboards.render import _RESOURCE_LIST_COLUMN_STATE_NAME_ONLY
        states = ui.get("states") or []
        for s in list(states):
            if s["key"] == "permResGrid_" and s["value"] == _RESOURCE_LIST_COLUMN_STATE_NAME_ONLY:
                y["column_preset"] = "name-only"
                states.remove(s)
        if "states" in ui and not states:
            del ui["states"]
        if sp:
            self.loss(f"{where}: a self-provider ResourceList is not modeled (renders selfProvider false)")

    def w_ProblemAlertsList(self, w, c, y, ui, sp, where):
        y["impacted_badge"] = c.get("impactedBadge")
        y["triggered_object"] = (c.get("triggeredObject") or {}).get("triggeredObject")
        if c.get("topIssuesDisplayLimit"):
            y["top_issues_limit"] = c["topIssuesDisplayLimit"]
        r = c.get("resource")
        if sp and isinstance(r, dict):
            y["self_provider"] = True
            y["pin"] = self.pin_from_resource(r.get("resourceId"), where)

    def w_AlertVolume(self, w, c, y, ui, sp, where):
        y["refresh_content"] = (c.get("refreshContent") or {}).get("refreshContent", False)
        y["refresh_interval"] = c.get("refreshInterval", 300)
        r = c.get("resource")
        if sp and isinstance(r, dict):
            y["self_provider"] = True
            y["pin"] = self.pin_from_resource(r.get("resourceId"), where)

    def w_PropertyList(self, w, c, y, ui, sp, where):
        metric = c.get("metric") or {}
        y["property_list"] = OrderedDict(
            properties=[self.metric(m, where) for m in metric.get("resourceKindMetrics") or []],
            visual_theme=c.get("visualTheme"), depth=c.get("depth"),
            show_metric_full_name=(c.get("showMetricFullName") or {}).get("metricFullName", False),
        )
        if sp:
            self.loss(f"{where}: a self-provider PropertyList is not modeled")

    def w_Section(self, w, c, y, ui, sp, where):
        return


def map_dashboard(db: dict, context: dict, location: str) -> MappedObject:
    """Map one dashboard dict, then classify every source key
    (``accounting.account``). Raises ``MappingError``."""
    if not isinstance(db.get("id"), str):
        raise MappingError(f"dashboard id {db.get('id')!r} is not a string")
    m = _DashMapper(db, context, location)
    y = m.map()
    account("dashboard", _flat.flatten_dashboard(db, context.get("entries") or {}, {}), m.losses)
    navs = db.get("dashboardNavigations")
    if isinstance(navs, dict) and navs and not any(wid in m.lid and m.lid[wid] for wid in navs):
        # Every navigation key is stale: the render then writes {}.
        for x in m.losses:
            if x.cls == "navigation keyed by a widget not on the dashboard":
                x.marks.append(Mark(f"{_flat.DASH}.dashboardNavigations", "extra", empty_only=True))
    return MappedObject("dashboard", y, losses=m.losses, notes=m.notes, source_name=y["name"])


def sm_ids_in(tree) -> List[str]:
    """Every ``sm_<uuid>`` id named in the strings of ``tree``."""
    out: List[str] = []
    if isinstance(tree, str):
        out += [m.group(1) for m in _SM_IN_KEY.finditer(tree)]
    elif isinstance(tree, dict):
        for v in tree.values():
            out += sm_ids_in(v)
    elif isinstance(tree, list):
        for v in tree:
            out += sm_ids_in(v)
    return out
