"""Semantic comparison of a source object with its factory render.

Each type has a canonical form; :func:`diff` walks two canonical forms and
returns the differences together with the number of leaf fields it
compared, so a caller can say how much it compared and refuse a comparison
that compared nothing.

What the canonical forms set aside, each a documented non-difference that a
verification counts and reports rather than hides:

- **whitespace**: text and attribute values are compared with runs of
  whitespace collapsed (``" ".join(s.split())``), which also hides a
  whitespace-only change;
- **ids the product renumbers on export or import**: view control and
  data-provider ids and the per-column Item ``id`` Property; dashboard
  widget ids (mapped by position, also inside state keys, interactions,
  navigations, Section members, ``config.widgetId``, ``tabId``), the
  synthetic ``entries`` ids (resolved to adapter / kind / name), metric
  entry and Heatmap tab ``extModel`` ids and the View pin's
  ``Ext.vcops.chrome.model.Resource-<n>`` id; a dashboard's
  ``creationTime``, ``lastUpdateTime``, ``userId``, ``lastUpdateUserId``;
  super metric ``modificationTime`` and ``modifiedBy``;
- **adapterName** on a dashboard (install ownership, set by the pak
  builder; not modeled);
- **navigation entries keyed by a widget that is not on the dashboard**
  (no widget can fire them; not modeled);
- **number spelling**: ``"0"`` equals ``"0.0"``, an int equals the float of
  the same value;
- **order** where the product does not care: attribute order, Property
  order inside a Control or Item, JSON key order (also inside a view's
  filter JSON), the order of SubjectType / SubjectsGroupBy / Usage elements
  and of the ``entries`` rows.

Presence is never set aside: a key, attribute, Property or element present
on one side only is always a difference.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def ws(s) -> str:
    return " ".join((s or "").split())


@dataclass
class Comparison:
    """The result of comparing one object."""

    fields: int = 0
    differences: List[Tuple[str, str]] = field(default_factory=list)
    #: documented non-differences seen in this object, by class
    set_aside: Counter = field(default_factory=Counter)

    @property
    def identical(self) -> bool:
        return not self.differences


def diff(a, b, path: str, out: Comparison, unordered_lists: Tuple[str, ...] = ()) -> None:
    """``a`` is the expected (source) side, ``b`` the render."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            p = f"{path}.{k}"
            if k not in b:
                out.fields += 1
                out.differences.append((p, "missing on render"))
            elif k not in a:
                out.fields += 1
                out.differences.append((p, "extra on render"))
            else:
                diff(a[k], b[k], p, out, unordered_lists)
        return
    if isinstance(a, list) and isinstance(b, list):
        if path.rsplit(".", 1)[-1] in unordered_lists:
            a, b = sorted(map(repr, a)), sorted(map(repr, b))
        if len(a) != len(b):
            out.fields += 1
            out.differences.append((path, f"list length {len(a)} vs {len(b)}"))
            return
        for x, y in zip(a, b):
            diff(x, y, path + "[]", out, unordered_lists)
        return
    out.fields += 1
    if a != b:
        out.differences.append((path, f"value {json.dumps(a, default=str)[:80]} vs {json.dumps(b, default=str)[:80]}"))


# ----------------------------------------------------------------- views
def _nval(s):
    if s is None:
        return None
    try:
        return ("num", float(s))
    except ValueError:
        return ("str", ws(s))


def _canon_prop(p):
    if p.get("value") is not None:
        return _nval(p.get("value"))
    lst = p.find("List")
    if lst is None:
        return ("empty",)
    out = []
    for it in lst:
        val = it.find("Value")
        if val is None:
            out.append(_nval(it.get("value")))
        else:
            out.append({q.get("name"): _canon_prop(q) for q in val.findall("Property") if q.get("name") != "id"})
    return out


def _canon_filter(f):
    if not f:
        return None
    try:
        j = json.loads(f)
    except ValueError:
        return ("unparsed", f)

    def c(o):
        if isinstance(o, dict):
            return tuple(sorted((k, c(v)) for k, v in o.items()))
        if isinstance(o, list):
            return tuple(c(x) for x in o)
        if isinstance(o, (int, float)) and not isinstance(o, bool):
            return ("num", float(o))
        return o
    return repr(c(j))


def canon_view(v) -> Dict[str, object]:
    out: Dict[str, object] = {
        "id": (v.get("id") or "").lower(),
        "Title": ws(v.findtext("Title")),
        "Title@": sorted((v.find("Title").attrib if v.find("Title") is not None else {}).items()),
        "Description": ws(v.findtext("Description")),
        "Description@": sorted((v.find("Description").attrib if v.find("Description") is not None else {}).items()),
        "SubjectType": sorted(repr((s.get("adapterKind"), s.get("resourceKind"), s.get("type"),
                                    _canon_filter(s.get("filter")))) for s in v.findall("SubjectType")),
        "SubjectsGroupBy": sorted(repr((s.get("adapterKind"), s.get("resourceKind"))) for s in v.findall("SubjectsGroupBy")),
        "Usage": sorted(ws(u.text) for u in v.findall("Usage")),
        "DataProvider": sorted(d.get("dataType") or "" for d in v.iter("DataProvider")),
        "Presentation": [repr((p.get("type"), sorted(p.attrib.items()), len(list(p.iter())))) for p in v.findall("Presentation")],
    }
    ctls: Dict[str, object] = {}
    for c in v.iter("Control"):
        ctls.setdefault(c.get("type"), {"visible": c.get("visible"),
                                        "props": {p.get("name"): _canon_prop(p) for p in c.findall("Property")}})
    out["Controls"] = ctls
    out["Other"] = sorted(ch.tag for ch in v if ch.tag not in (
        "Title", "Description", "SubjectType", "SubjectsGroupBy", "Usage", "Controls", "DataProviders", "Presentation"))
    return out


VIEW_SET_ASIDE = ("control and data-provider ids", "column Item id Property", "whitespace", "number spelling",
                  "Property / attribute / element order")


def compare_view(src_elem, rendered_elem, expected_fix=None) -> Comparison:
    out = Comparison()
    a = canon_view(src_elem)
    if expected_fix:
        a = expected_fix(a)
    b = canon_view(rendered_elem)
    diff(a, b, "view", out, unordered_lists=("SubjectType", "SubjectsGroupBy", "Usage", "DataProvider"))
    n_items = len([1 for _ in src_elem.iter("Item") if _.find("Value") is not None])
    out.set_aside["renumbered ids (control, data provider, column Item id)"] += (
        len(list(src_elem.iter("Control"))) + len(list(src_elem.iter("DataProvider"))) + n_items)
    return out


# ------------------------------------------------------------ dashboards
IGNORE_DASH_TOP = ("creationTime", "lastUpdateTime", "userId", "lastUpdateUserId")


def normalize_dashboard(db: dict, entries: dict, idmap: Dict[str, str], keep_nav_keys=None,
                        set_aside: Optional[Counter] = None) -> dict:
    """The comparable form of one dashboard: synthetic entries refs resolved,
    widget ids mapped through ``idmap`` (also inside strings), renumbered
    ids replaced by placeholders, ignored keys dropped, whitespace collapsed.

    ``keep_nav_keys``: the widget ids whose navigation entries are kept
    (the widgets on the dashboard); entries keyed by any other id are set
    aside and counted.
    """
    sa = set_aside if set_aside is not None else Counter()
    rk = {e.get("internalId"): "RK:%s/%s" % (e.get("adapterKindKey"), e.get("resourceKindKey"))
          for e in (entries or {}).get("resourceKind", []) or []}
    res = {e.get("internalId"): "RES:%s/%s/%s" % (e.get("adapterKindKey"), e.get("resourceKindKey"), e.get("name"))
           for e in (entries or {}).get("resource", []) or []}
    lower_map = {k.lower(): v for k, v in idmap.items()}

    def fix_str(s: str) -> str:
        s = re.sub(r"resourceKind:id:\d+_::_", lambda m: rk.get(m.group(0), m.group(0)), s)
        s = re.sub(r"resource:id:\d+_::_", lambda m: res.get(m.group(0), m.group(0)), s)
        s = re.sub(UUID, lambda m: lower_map.get(m.group(0).lower(), m.group(0).lower()), s)
        return s

    def walk(x, path=""):
        if isinstance(x, dict):
            o = {}
            for k, v in x.items():
                nk = fix_str(k)
                if (path.endswith("resourceKindMetrics[]") or path.endswith("resourceMetrics[]")) and k == "id":
                    sa["renumbered ids (metric entry extModel)"] += 1
                    v = "<extModel>"
                if path.endswith("configs[]") and k == "id":
                    sa["renumbered ids (Heatmap tab extModel)"] += 1
                    v = "<extModel>"
                if path.endswith(".config") and k == "widgetId":
                    v = "<widgetId>"
                if path.endswith("config.resource") and k == "id" and isinstance(v, str) and v.startswith("Ext.vcops"):
                    sa["renumbered ids (pin Ext resource)"] += 1
                    v = "<ExtResource>"
                o[nk] = walk(v, path + "." + k)
            return o
        if isinstance(x, list):
            return [walk(v, path + "[]") for v in x]
        if isinstance(x, str):
            return ws(fix_str(x))
        if isinstance(x, float) and x.is_integer():
            return int(x)
        return x

    d = {k: v for k, v in db.items() if k not in IGNORE_DASH_TOP and k != "entries"}
    for k in IGNORE_DASH_TOP:
        if k in db:
            sa[f"server metadata ({k})"] += 1
    if "adapterName" in d:
        sa["adapterName (install ownership, not modeled)"] += 1
        d.pop("adapterName")
    navs = d.get("dashboardNavigations")
    if isinstance(navs, dict) and keep_nav_keys is not None:
        kept = {}
        for wid, entries_ in navs.items():
            if wid in keep_nav_keys:
                kept[wid] = entries_
            else:
                sa["navigation entries keyed by a widget not on the dashboard"] += len(entries_ or []) or 1
        d["dashboardNavigations"] = kept
    for w in d.get("widgets") or []:
        if w.get("id"):
            sa["renumbered ids (widget)"] += 1
    return walk(d)


def compare_dashboard(src_db: dict, src_entries: dict, rendered_env: dict, rendered_db: dict,
                      widget_idmap: Dict[str, str], id_rewrites: Dict[str, str]) -> Comparison:
    """``widget_idmap``: source widget id -> rendered widget id (by
    position, also covering navigation targets in other dashboards).
    ``id_rewrites``: intended object id changes (old -> new) and the
    dashboard's own id."""
    out = Comparison()
    idmap = dict(id_rewrites)
    idmap.update(widget_idmap)
    keep = {w.get("id") for w in src_db.get("widgets") or []}
    a = normalize_dashboard(src_db, src_entries, idmap, keep_nav_keys=keep, set_aside=out.set_aside)
    b = normalize_dashboard(rendered_db, rendered_env.get("entries") or {}, {}, set_aside=Counter())
    a_w, b_w = a.pop("widgets", []) or [], b.pop("widgets", []) or []
    diff(a, b, "dashboard", out)
    if len(a_w) != len(b_w):
        out.fields += 1
        out.differences.append(("dashboard.widgets", f"widget count {len(a_w)} vs {len(b_w)}"))
    for i, (wa, wb) in enumerate(zip(a_w, b_w)):
        diff(wa, wb, f"widget[{i}:{(src_db.get('widgets') or [{}])[i].get('type')}]", out)
    # entries: the kinds and resources this dashboard uses (the source table
    # may be shared by many dashboards in one file)
    blob = json.dumps([a, a_w])
    ka ={(e.get("adapterKindKey"), e.get("resourceKindKey")) for e in (src_entries or {}).get("resourceKind", []) or []}
    ka = {k for k in ka if ('RK:%s/%s"' % k) in blob}
    kb = {(e.get("adapterKindKey"), e.get("resourceKindKey")) for e in (rendered_env.get("entries") or {}).get("resourceKind", []) or []}
    ra = {(e.get("adapterKindKey"), e.get("resourceKindKey"), e.get("name")) for e in (src_entries or {}).get("resource", []) or []}
    ra = {k for k in ra if ('RES:%s/%s/%s"' % k) in blob}
    rb = {(e.get("adapterKindKey"), e.get("resourceKindKey"), e.get("name")) for e in (rendered_env.get("entries") or {}).get("resource", []) or []}
    out.fields += 2
    if ka != kb:
        out.differences.append(("entries.resourceKind", f"source-only {sorted(ka - kb)} render-only {sorted(kb - ka)}"))
    if ra != rb:
        out.differences.append(("entries.resource", f"source-only {sorted(ra - rb)} render-only {sorted(rb - ra)}"))
    out.set_aside["renumbered ids (entries table)"] += len(ka) + len(ra)
    return out


# ------------------------------------------------------------ XML trees
def xml_diff(a, b, path: str, out: Comparison, attr_fix=None) -> None:
    """Ordered element tree; attributes unordered; text whitespace-collapsed."""
    if a.tag != b.tag:
        out.fields += 1
        out.differences.append((path, f"tag {a.tag} vs {b.tag}"))
        return
    p = f"{path}/{a.tag}"
    for k in sorted(set(a.attrib) | set(b.attrib)):
        out.fields += 1
        if k not in b.attrib:
            out.differences.append((p + "@" + k, "missing on render"))
        elif k not in a.attrib:
            out.differences.append((p + "@" + k, "extra on render"))
        else:
            va = ws(a.attrib[k])
            if attr_fix:
                va = attr_fix(a.tag, k, va)
            if va != ws(b.attrib[k]):
                out.differences.append((p + "@" + k, f"value {a.attrib[k][:60]!r} vs {b.attrib[k][:60]!r}"))
    ka, kb = list(a), list(b)
    if not ka and not kb:
        out.fields += 1
        ta = ws(a.text)
        if attr_fix:
            ta = attr_fix(a.tag, "#text", ta)
        if ta != ws(b.text):
            out.differences.append((p + "#text", f"value {ws(a.text)[:60]!r} vs {ws(b.text)[:60]!r}"))
        return
    if [c.tag for c in ka] != [c.tag for c in kb]:
        out.fields += 1
        out.differences.append((p, f"children {[c.tag for c in ka]} vs {[c.tag for c in kb]}"[:240]))
        return
    for x, y in zip(ka, kb):
        xml_diff(x, y, p, out, attr_fix)


def compare_xml(src_elem, rendered_elem, attr_fix=None) -> Comparison:
    out = Comparison()
    xml_diff(src_elem, rendered_elem, "", out, attr_fix)
    return out


# ---------------------------------------------------------- super metrics
def compare_supermetric(src: dict, rendered: dict, expected_fix=None) -> Comparison:
    out = Comparison()
    a = {k: v for k, v in src.items() if k not in ("modificationTime", "modifiedBy", "id")}
    for k in ("modificationTime", "modifiedBy"):
        if k in src:
            out.set_aside[f"server metadata ({k})"] += 1
    if expected_fix:
        a = expected_fix(a)
    b = dict(rendered)

    def norm(x):
        if isinstance(x, str):
            return ws(x)
        if isinstance(x, list):
            return [norm(i) for i in x]
        if isinstance(x, dict):
            return {k: norm(v) for k, v in x.items()}
        return x
    diff(norm(a), norm(b), "supermetric", out)
    return out


def canonical_key(obj) -> str:
    """A string identifying a source object's content, for telling two
    copies of the same id apart (renumbered ids and whitespace ignored)."""
    if obj.type == "view":
        return json.dumps(canon_view(obj.payload), sort_keys=True, default=str)
    if obj.type in ("report", "alert", "symptom", "recommendation"):
        def c(e):
            return (e.tag, sorted((k, ws(v)) for k, v in e.attrib.items()), ws(e.text) if not len(e) else "",
                    [c(x) for x in e])
        return json.dumps(c(obj.payload), default=str)
    if obj.type == "dashboard":
        return json.dumps(normalize_dashboard(obj.payload, obj.context.get("entries") or {}, {}),
                          sort_keys=True, default=str)
    if obj.type == "supermetric":
        return json.dumps({k: v for k, v in obj.payload.items() if k not in ("modificationTime", "modifiedBy")},
                          sort_keys=True, default=str)
    return repr(obj.payload)
