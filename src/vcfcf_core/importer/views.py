"""ViewDef XML -> factory view YAML (every field of the 2026-11-12 schema).

Wire format and YAML: ``knowledge/context/wire-formats/view_fidelity_wire_format.md``
and ``view_column_wire_format.md``. The mapping writes a field only where the
source differs from what the renderer emits without it, and an ``omit:``
entry wherever the source leaves out a Property the renderer always writes,
so a load and render reproduces the source.

What the schema cannot express is a *loss*: the object still converts, and
each loss is listed (``MappedObject.losses``). The documented ones (the
view fidelity doc §Not modeled) are a buckets-control on a list view, an
empty ``preferredUnitId``, filter ``values`` lists and ``conditionId``, a
different filter per SubjectType; anything the mapper does not recognise is
reported by name as well.
"""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Dict, List, Tuple

from .model import MappedObject, MappingError, loss_or_gap
from .refs import Ref

DATA_TYPES = {"list-view": "list", "distribution-view": "distribution", "trend-view": "trend"}
_DEFAULT_SUBJECT_TYPES = ["descendant", "self"]
_USAGE_ALL = ["dashboard", "report", "details", "content"]
_SM_KEY_RE = re.compile(r"(?i)^super metric\|sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")

_TOP_LEVEL = ("Title", "Description", "SubjectType", "SubjectsGroupBy", "Usage",
              "Controls", "DataProviders", "Presentation")

_COLUMN_PROPS = {
    "objectType", "attributeKey", "id", "preferredUnitId", "isStringAttribute", "adapterKind",
    "resourceKind", "rollUpType", "rollUpUnit", "rollUpCount", "percentile", "transformExpression",
    "transformations", "sortCriteria", "isProperty", "yellowBound", "orangeBound", "redBound",
    "ascendingRange", "useSymptomThresholds", "displayName", "addTimestampAsColumn",
    "isShowRelativeTimestamp", "metricToRelateWith", "localizedMetricToRelateWith",
    "operatorToRelateWith", "forecastDays",
    "isInstancedGroup", "showInstanceName", "instanceGroupName", "keepInstanceSummary",
    "isTimeSegment", "breakdownBy", "startingOnUnit", "startingOnCount",
}
_ADDITIONAL_PROPS = {
    "objectType", "attributeKey", "id", "preferredUnitId", "localizedAttributeName",
    "isStringAttribute", "adapterKind", "resourceKind", "rollUpType", "rollUpCount", "percentile",
    "transformations", "sortCriteria", "isProperty", "displayName", "isShowRelativeTimestamp",
}
_FILTER_KEYS = {"condition", "transform", "metricKey", "metricValue", "businessHours", "filterType"}


def _num(s: str):
    """A wire number as YAML: integers stay integers, the rest floats."""
    try:
        f = float(s)
    except (TypeError, ValueError):
        return s
    return int(f) if re.fullmatch(r"-?\d+", str(s).strip()) else f


def _bound(s: str):
    try:
        float(s)
    except ValueError:
        return s
    return _num(s)


def _item_props(item) -> Dict[str, object]:
    val = item.find("Value")
    out: Dict[str, object] = OrderedDict()
    if val is None:
        return out
    for p in val.findall("Property"):
        if p.get("value") is not None:
            out[p.get("name")] = p.get("value")
        else:
            out[p.get("name")] = [i.get("value") for i in p.iter("Item") if i.get("value") is not None]
    return out


def _ctl_props(ctl) -> Dict[str, object]:
    out: Dict[str, object] = OrderedDict()
    for p in ctl.findall("Property"):
        out[p.get("name")] = p.get("value") if p.get("value") is not None else p
    return out


class _ViewMapper:
    def __init__(self, elem, location: str):
        self.v = elem
        self.location = location
        self.losses: List[str] = []
        self.refs: List[Ref] = []

    def loss(self, msg: str) -> None:
        """A documented not-modeled feature is listed; anything else stops
        the view with a TOOLSET GAP (model.loss_or_gap)."""
        loss_or_gap(self.losses, msg, "view")

    # ------------------------------------------------------------ filter
    def _filter(self, fjson: str):
        try:
            groups_raw = json.loads(fjson)
        except ValueError as exc:
            raise MappingError(f"SubjectType filter is not JSON ({exc})")
        if not isinstance(groups_raw, list):
            raise MappingError("SubjectType filter is not a list of condition groups")
        groups = []
        for grp in groups_raw:
            g = []
            for c in grp:
                extra = set(c) - _FILTER_KEYS
                if extra:
                    self.loss(f"subject filter keys {sorted(extra)} are not modeled (view fidelity doc §Not modeled)")
                mv = c.get("metricValue") or {}
                if "values" in mv and mv.get("value") is None and c.get("condition") not in ("EXISTS", "NOT_EXISTS"):
                    # Only the list carries the operand: without it the
                    # condition has no value the YAML can hold.
                    raise MappingError(
                        f"subject filter condition {c.get('condition')!r} on {c.get('metricKey')!r} takes its "
                        f"operand from a metricValue.values list, which the view YAML does not model",
                        gap={"what": "view subject filter metricValue.values (a list operand)"})
                if "values" in mv:
                    self.loss("subject filter metricValue.values list is not modeled")
                d = OrderedDict()
                d["filter_type"] = c.get("filterType")
                d["metric_key"] = c.get("metricKey")
                d["condition"] = c.get("condition")
                v = mv.get("value")
                if v is None:
                    d["value"] = None
                    d["string_metric"] = bool(mv.get("isStringMetric"))
                else:
                    if mv.get("isStringMetric") and not isinstance(v, str):
                        self.loss("subject filter isStringMetric=true with a non-string value is rendered as a string")
                        v = str(v)
                    d["value"] = v
                if "transform" in c:
                    d["transform"] = c["transform"]
                if "businessHours" in c:
                    d["business_hours"] = c["businessHours"]
                g.append(d)
            groups.append(g)
        return groups

    # ------------------------------------------------------------ columns
    def _sm_attr(self, attr: str, raw_ok: bool, where: str):
        m = _SM_KEY_RE.match(attr)
        if not m:
            return attr
        ref = Ref("supermetric", m.group(1), form="sm_column", raw_ok=raw_ok, where=where)
        self.refs.append(ref)
        return ref

    def _column(self, d: dict, kinds, dt: str, trend_tx: list, forecast: list, idx: int):
        for k in d:
            if k not in _COLUMN_PROPS:
                self.loss(f"column {idx}: Property {k} is not modeled")
        if d.get("objectType", "RESOURCE") != "RESOURCE":
            self.loss(f"column {idx}: objectType {d.get('objectType')!r} is not modeled (renders RESOURCE)")
        col: Dict[str, object] = OrderedDict()
        omit: List[str] = []
        if d.get("isInstancedGroup") == "true":
            ig = OrderedDict(name=d.get("instanceGroupName", ""))
            ig["show_instance_name"] = d.get("showInstanceName") == "true"
            ig["keep_instance_summary"] = d.get("keepInstanceSummary") == "true"
            col["instanced_group"] = ig
            for k in ("preferredUnitId", "adapterKind", "resourceKind", "rollUpType", "transformations",
                      "isProperty", "isStringAttribute"):
                if k in d:
                    self.loss(f"column {idx}: instanced-group driver Property {k} is not modeled")
            if d.get("rollUpCount", "0") != "0":
                self.loss(f"column {idx}: instanced-group driver rollUpCount {d['rollUpCount']} is not modeled")
            if "displayName" in d:
                col["display_name"] = d["displayName"]
            else:
                omit.append("display_name")
            if "sortCriteria" in d:
                col["sort"] = "asc" if d["sortCriteria"] == "true" else "desc"
            if omit:
                col["omit"] = omit
            return col
        if d.get("isTimeSegment") == "true":
            ts = OrderedDict(breakdown_by=d.get("breakdownBy"))
            ts["starting_on_unit"] = d.get("startingOnUnit", "WEEKS")
            ts["starting_on_count"] = int(d.get("startingOnCount", "1"))
            col["display_name"] = d.get("displayName", "")
            col["time_segment"] = ts
            expected = {"objectType", "attributeKey", "id", "rollUpCount", "sortCriteria", "isTimeSegment",
                        "breakdownBy", "startingOnUnit", "startingOnCount", "displayName"}
            for k in d:
                if k not in expected:
                    self.loss(f"column {idx}: time-segment Property {k} is not modeled")
            for k, v in (("sortCriteria", "false"), ("rollUpCount", "0"), ("displayName", None)):
                if k not in d:
                    self.loss(f"column {idx}: time-segment column without {k} (the renderer always writes it)")
                elif v is not None and d[k] != v:
                    self.loss(f"column {idx}: time-segment {k}={d[k]!r} is not modeled (renders {v})")
            return col
        if "attributeKey" not in d:
            raise MappingError(f"column {idx} has no attributeKey")
        col["attribute"] = self._sm_attr(d["attributeKey"], True, f"column {idx}")
        if "displayName" in d:
            col["display_name"] = d["displayName"]
        else:
            omit.append("display_name")
        if "preferredUnitId" in d:
            if d["preferredUnitId"]:
                col["unit"] = d["preferredUnitId"]
            else:
                self.loss(f"column {idx}: empty preferredUnitId is not modeled (view fidelity doc §Not modeled)")
        if d.get("isProperty") == "true":
            col["is_property"] = True
        elif "isProperty" not in d:
            omit.append("is_property")
        if d.get("isStringAttribute") == "true":
            col["is_string_attribute"] = True
        elif "isStringAttribute" not in d:
            self.loss(f"column {idx}: absent isStringAttribute is not modeled (renders false)")
        if len(kinds) > 1:
            if "adapterKind" in d:
                if (d.get("adapterKind"), d.get("resourceKind")) not in kinds:
                    self.loss(f"column {idx}: bound to {d.get('adapterKind')}/{d.get('resourceKind')}, "
                              f"which is not one of the view's subjects (not modeled)")
                col["subject"] = OrderedDict(adapter_kind=d["adapterKind"], resource_kind=d["resourceKind"])
        else:
            if "adapterKind" not in d:
                omit.append("subject")
            elif (d["adapterKind"], d.get("resourceKind")) != kinds[0]:
                self.loss(f"column {idx}: bound to {d['adapterKind']}/{d.get('resourceKind')}, not the "
                          f"view's subject (not modeled; renders the subject kind)")
        if "rollUpType" in d:
            col["roll_up_type"] = d["rollUpType"]
        else:
            omit.append("roll_up_type")
        if "rollUpUnit" in d:
            col["roll_up_unit"] = d["rollUpUnit"]
        if "rollUpCount" in d:
            col["roll_up_count"] = int(d["rollUpCount"])
        else:
            self.loss(f"column {idx}: absent rollUpCount is not modeled")
        tx = d.get("transformations")
        if tx is None and dt == "trend":
            # omit: [transformation] is a load error on a trend column (the
            # Property is the view-level stack, and no export lacks it).
            self.loss(f"column {idx}: a trend column without transformations is not modeled")
        elif tx is None:
            omit.append("transformation")
        elif dt == "trend":
            trend_tx.append(tuple(tx))
            if "forecastDays" in d:
                forecast.append(d["forecastDays"])
            else:
                forecast.append(None)
        else:
            if len(tx) != 1:
                self.loss(f"column {idx}: {len(tx)} transformations on a {dt} column are not modeled (first kept)")
            col["transformation"] = tx[0] if tx else "CURRENT"
            if "percentile" in d:
                pf = float(d["percentile"])
                if not pf.is_integer():
                    self.loss(f"column {idx}: percentile {d['percentile']} is not an integer (the YAML "
                              f"field percentile is an integer)")
                col["percentile"] = int(pf)
            if "transformExpression" in d:
                col["transform_expression"] = d["transformExpression"]
            for wk, yk in (("metricToRelateWith", "metric_to_relate_with"),
                           ("localizedMetricToRelateWith", "localized_metric_to_relate_with"),
                           ("operatorToRelateWith", "operator_to_relate_with")):
                if wk in d:
                    col[yk] = d[wk]
        if dt != "trend" and "forecastDays" in d:
            self.loss(f"column {idx}: forecastDays on a {dt} column is not modeled")
        if "sortCriteria" in d:
            col["sort"] = "asc" if d["sortCriteria"] == "true" else "desc"
        for wk, yk in (("yellowBound", "yellow_bound"), ("orangeBound", "orange_bound"), ("redBound", "red_bound")):
            if wk in d:
                col[yk] = _bound(d[wk])
        has_num_bound = any(isinstance(col.get(k), (int, float))
                            for k in ("yellow_bound", "orange_bound", "red_bound"))
        if "ascendingRange" in d:
            col["ascending_range"] = d["ascendingRange"] == "true"
        elif has_num_bound:
            omit.append("ascending_range")
        if "useSymptomThresholds" in d:
            col["use_symptom_thresholds"] = d["useSymptomThresholds"] == "true"
        if "addTimestampAsColumn" in d:
            if d["addTimestampAsColumn"] == "true":
                col["add_timestamp_as_column"] = True
        else:
            omit.append("add_timestamp_as_column")
        if "isShowRelativeTimestamp" in d:
            if d["isShowRelativeTimestamp"] == "true":
                col["show_relative_timestamp"] = True
        else:
            omit.append("show_relative_timestamp")
        if omit:
            col["omit"] = omit
        return col

    def _additional(self, d: dict, kinds, idx: int):
        for k in d:
            if k not in _ADDITIONAL_PROPS:
                self.loss(f"additional column {idx}: Property {k} is not modeled")
        if "attributeKey" not in d or "localizedAttributeName" not in d:
            raise MappingError(f"additional column {idx} lacks attributeKey or localizedAttributeName")
        col: Dict[str, object] = OrderedDict()
        col["attribute"] = self._sm_attr(d["attributeKey"], False, f"additional column {idx}")
        col["localized_name"] = d["localizedAttributeName"]
        omit: List[str] = []
        if "displayName" in d:
            col["display_name"] = d["displayName"]
        else:
            omit.append("display_name")
        if d.get("preferredUnitId"):
            col["unit"] = d["preferredUnitId"]
        elif "preferredUnitId" in d:
            self.loss(f"additional column {idx}: empty preferredUnitId is not modeled")
        if d.get("isStringAttribute") == "true":
            col["is_string_attribute"] = True
        if d.get("isProperty") == "true":
            col["is_property"] = True
        if (d.get("adapterKind"), d.get("resourceKind")) != kinds[0] and len(kinds) == 1:
            self.loss(f"additional column {idx}: bound to a kind that is not the view subject (not modeled)")
        if "rollUpType" in d:
            col["roll_up_type"] = d["rollUpType"]
        col["roll_up_count"] = int(d.get("rollUpCount", "0"))
        if "transformations" in d:
            tx = d["transformations"]
            col["transformation"] = tx[0] if tx else "CURRENT"
            if "percentile" in d:
                pf = float(d["percentile"])
                if not pf.is_integer():
                    self.loss(f"additional column {idx}: percentile {d['percentile']} is not an integer")
                col["percentile"] = int(pf)
        if "sortCriteria" in d:
            col["sort"] = "asc" if d["sortCriteria"] == "true" else "desc"
        if "isShowRelativeTimestamp" in d:
            col["show_relative_timestamp"] = d["isShowRelativeTimestamp"] == "true"
        if omit:
            col["omit"] = omit
        return col

    # ------------------------------------------------------------ view
    def map(self) -> Dict[str, object]:
        v = self.v
        y: Dict[str, object] = OrderedDict()
        y["id"] = v.get("id")
        title = v.find("Title")
        y["name"] = (v.findtext("Title") or "").strip()
        y["description"] = (v.findtext("Description") or "").strip()
        for el, label in ((title, "Title"), (v.find("Description"), "Description")):
            if el is not None and el.get("localizationKey"):
                self.loss(f"{label} localizationKey is not modeled (no localization bundle ships with the YAML)")
        dps = [d.get("dataType") for d in v.iter("DataProvider")]
        if not dps or dps[0] not in DATA_TYPES:
            pres_t = (v.find("Presentation").get("type") if v.find("Presentation") is not None else None)
            raise MappingError(
                f"the view YAML models list, distribution and trend views; this ViewDef has data "
                f"provider(s) {dps or 'none'} and presentation {pres_t!r} (view fidelity doc §Not modeled: "
                f"text and image presentations)",
                gap={"what": f"view without a list/distribution/trend data provider (presentation {pres_t!r})"})
        if len(dps) > 1:
            self.loss(f"{len(dps)} DataProviders: only the first is modeled")
        dt = DATA_TYPES[dps[0]]
        y["data_type"] = dt
        pres = v.find("Presentation")
        if pres is None or not pres.get("type"):
            raise MappingError("ViewDef has no Presentation type")
        y["presentation"] = pres.get("type")
        if len(pres) or set(pres.attrib) - {"type"}:
            self.loss("Presentation child elements or attributes other than type are not modeled")

        entries: "OrderedDict[Tuple[str, str], List[str]]" = OrderedDict()
        filters = []
        for st in v.findall("SubjectType"):
            entries.setdefault((st.get("adapterKind"), st.get("resourceKind")), []).append(st.get("type"))
            filters.append(st.get("filter"))
            if set(st.attrib) - {"adapterKind", "resourceKind", "type", "filter"}:
                self.loss(f"SubjectType attributes {sorted(set(st.attrib) - {'adapterKind', 'resourceKind', 'type', 'filter'})} are not modeled")
        if not entries:
            raise MappingError("ViewDef has no SubjectType")
        if len(set(filters)) > 1:
            self.loss("different filters per SubjectType are not modeled (the first is applied to all)")
        kinds = list(entries)
        if len(kinds) == 1:
            (ak, rk), types = kinds[0], entries[kinds[0]]
            subj: Dict[str, object] = OrderedDict(adapter_kind=ak, resource_kind=rk)
            if types != _DEFAULT_SUBJECT_TYPES:
                subj["types"] = types
            y["subject"] = subj
        else:
            y["subject"] = OrderedDict()
            subs = []
            for (ak, rk), types in entries.items():
                e: Dict[str, object] = OrderedDict(adapter_kind=ak, resource_kind=rk)
                if types != _DEFAULT_SUBJECT_TYPES:
                    e["types"] = types
                subs.append(e)
            y["subjects"] = subs
        if filters and filters[0]:
            y["subject"]["filter"] = self._filter(filters[0])
        gb = v.findall("SubjectsGroupBy")
        if len(gb) > 1:
            self.loss(f"{len(gb)} SubjectsGroupBy elements: only the first is modeled")
        if gb:
            y["group_by"] = OrderedDict(adapter_kind=gb[0].get("adapterKind"), resource_kind=gb[0].get("resourceKind"))
        usage = [(u.text or "").strip() for u in v.findall("Usage")]
        if sorted(usage) != sorted(_USAGE_ALL):
            y["usage"] = usage
        for child in v:
            if child.tag not in _TOP_LEVEL:
                self.loss(f"top-level element {child.tag} is not modeled")

        ctls: Dict[str, object] = {}
        for c in v.iter("Control"):
            if c.get("type") in ctls:
                self.loss(f"second {c.get('type')} control is not modeled")
                continue
            ctls[c.get("type")] = c
        for t in ctls:
            if t not in ("time-interval-selector", "attributes-selector", "pagination-control",
                         "buckets-control", "metadata"):
                self.loss(f"control {t} is not modeled")
        omit: List[str] = []

        if "time-interval-selector" not in ctls:
            self.loss("no time-interval-selector control (not modeled; one is rendered)")
        else:
            tis = _ctl_props(ctls["time-interval-selector"])
            for k in tis:
                if k not in ("advancedTimeMode", "unit", "count", "startPeriod", "endPeriod"):
                    self.loss(f"time-interval-selector Property {k} is not modeled")
            for k in ("unit", "count"):
                if k not in tis:
                    self.loss(f"time-interval-selector without {k} (the renderer always writes it)")
            tw: Dict[str, object] = OrderedDict(unit=tis.get("unit", "HOURS"), count=int(tis.get("count", "24")))
            if tis.get("advancedTimeMode") == "true":
                tw["advanced_time_mode"] = True
                if "startPeriod" in tis:
                    tw["start_period"] = tis["startPeriod"]
                    tw["end_period"] = tis.get("endPeriod")
            elif "startPeriod" in tis or "endPeriod" in tis:
                self.loss("startPeriod/endPeriod without advancedTimeMode=true are not modeled")
            if "advancedTimeMode" not in tis:
                self.loss("absent advancedTimeMode is not modeled (renders false)")
            y["time_window"] = tw

        attr = ctls.get("attributes-selector")
        if attr is None:
            raise MappingError("ViewDef has no attributes-selector control")
        for p in attr.findall("Property"):
            if p.get("name") not in ("attributeInfos", "summaryInfos"):
                self.loss(f"attributes-selector Property {p.get('name')} is not modeled")
        trend_tx: list = []
        forecast: list = []
        cols = []
        lst = attr.find("Property[@name='attributeInfos']/List")
        for i, it in enumerate(lst if lst is not None else []):
            cols.append(self._column(_item_props(it), kinds, dt, trend_tx, forecast, i))
        if dt == "trend" and trend_tx:
            if len(set(trend_tx)) > 1:
                self.loss("trend columns with differing transformations are not modeled (first kept)")
            y["transformations"] = list(trend_tx[0])
            fd = {f for f in forecast}
            if len(fd) > 1:
                self.loss("trend columns with differing forecastDays are not modeled")
            fdv = next(iter(fd)) if fd else None
            if fdv is not None and int(float(fdv)) > 0:
                y["forecast_days"] = int(float(fdv))
            elif fdv is not None:
                self.loss("forecastDays=0 on a trend column is not modeled")
        y["columns"] = cols
        summ = attr.find("Property[@name='summaryInfos']/List")
        if summ is not None:
            rows = []
            for it in summ:
                d = _item_props(it)
                for k in ("displayName", "aggregation"):
                    if k not in d:
                        self.loss(f"summary row without {k} (the renderer always writes it)")
                rows.append(OrderedDict(display_name=d.get("displayName"), aggregation=d.get("aggregation"),
                                        columns=[int(x) for x in d.get("attributeIndexes") or []]))
            if dt != "list":
                self.loss(f"summaryInfos on a {dt} view are not modeled")
            else:
                y["summary"] = rows

        if "pagination-control" in ctls:
            pp = _ctl_props(ctls["pagination-control"])
            for k in pp:
                if k not in ("start", "size"):
                    self.loss(f"pagination-control Property {k} is not modeled")
            if pp.get("start", "0") != "0":
                self.loss(f"pagination start {pp.get('start')} is not modeled (renders 0)")
            if ctls["pagination-control"].get("visible") != "true":
                self.loss("pagination-control visible other than true is not modeled")
            size = int(pp.get("size", "500"))
            if dt == "distribution" or size != 500:
                y["page_size"] = size
        elif dt != "distribution":
            omit.append("pagination")

        if "buckets-control" in ctls:
            bp = _ctl_props(ctls["buckets-control"])
            if dt != "distribution":
                self.loss("buckets-control on a non-distribution view is not modeled (view fidelity doc §Not modeled)")
            else:
                y["buckets"] = self._buckets(bp)
        elif dt == "distribution":
            self.loss("distribution view without a buckets-control is not modeled (one is rendered)")

        if "metadata" in ctls:
            mp = _ctl_props(ctls["metadata"])
            for k in mp:
                if k not in ("maxPointsCount", "distributionColor", "hideObjectNameColumn", "listTopResultSize",
                             "includeResourceCreationTime", "distributionAdditionalColumns"):
                    self.loss(f"metadata Property {k} is not modeled")
            for k in ("maxPointsCount", "hideObjectNameColumn", "listTopResultSize"):
                if k not in mp:
                    self.loss(f"metadata without {k} is not modeled (the renderer always writes it)")
            if mp.get("maxPointsCount", "5000") != "5000":
                y["max_points_count"] = int(mp["maxPointsCount"])
            if "distributionColor" in mp:
                y["distribution_color"] = mp["distributionColor"]
            if mp.get("hideObjectNameColumn") == "true":
                y["hide_object_name"] = True
            if mp.get("listTopResultSize", "-1") != "-1":
                y["top_n"] = int(mp["listTopResultSize"])
            if "includeResourceCreationTime" in mp:
                if mp["includeResourceCreationTime"] == "true":
                    y["include_resource_creation_time"] = True
            else:
                omit.append("include_resource_creation_time")
            if "distributionAdditionalColumns" in mp:
                if dt != "distribution":
                    self.loss("distributionAdditionalColumns on a non-distribution view are not modeled")
                else:
                    y["additional_columns"] = [
                        self._additional(_item_props(it), kinds, i)
                        for i, it in enumerate(mp["distributionAdditionalColumns"].find("List"))
                    ]
        else:
            omit.append("metadata")
        if omit:
            y["omit"] = omit
        return y

    def _buckets(self, bp: dict) -> Dict[str, object]:
        b: Dict[str, object] = OrderedDict()
        for k in bp:
            if k not in ("isDynamic", "dynamicCalcFunction", "bucketCount", "minValue", "maxValue",
                         "bucketInfos", "isSum"):
                self.loss(f"buckets-control Property {k} is not modeled")
        dyn = bp.get("isDynamic") == "true"
        b["dynamic"] = dyn
        ranges = []
        if "bucketInfos" in bp:
            for it in bp["bucketInfos"].find("List"):
                d = _item_props(it)
                r: Dict[str, object] = OrderedDict(start=_num(d.get("startValue")), end=_num(d.get("endValue")))
                if "bucketColor" in d:
                    r["color"] = d["bucketColor"]
                ranges.append(r)
        if ranges:
            b["ranges"] = ranges
            if bp.get("dynamicCalcFunction") != "SIMPLEMAXMIN":
                self.loss("bucketInfos without dynamicCalcFunction=SIMPLEMAXMIN are not modeled")
        elif "dynamicCalcFunction" in bp:
            b["calc_function"] = bp["dynamicCalcFunction"]
        elif dyn:
            self.loss("dynamic buckets without dynamicCalcFunction are not modeled (renders DISCRETE)")
        if "bucketCount" in bp:
            b["count"] = int(bp["bucketCount"])
        elif not dyn and not ranges:
            self.loss("fixed buckets without bucketCount are not modeled (renders 10)")
        if not dyn:
            if "minValue" not in bp or "maxValue" not in bp:
                self.loss("fixed buckets without minValue/maxValue are not modeled")
            b["min_value"] = _num(bp.get("minValue", "0"))
            b["max_value"] = _num(bp.get("maxValue", "100"))
        elif "minValue" in bp or "maxValue" in bp:
            self.loss("minValue/maxValue on dynamic buckets are not modeled")
        if "isSum" in bp:
            b["is_sum"] = bp["isSum"] == "true"
        return b


def map_view(elem, location: str) -> MappedObject:
    """Map one ``<ViewDef>`` element. Raises ``MappingError``."""
    m = _ViewMapper(elem, location)
    y = m.map()
    return MappedObject("view", y, losses=m.losses)
