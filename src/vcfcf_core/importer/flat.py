"""Exact flat forms of source objects and renders: ``{path: value}``.

One flattening per content type, shared by everything that has to agree on
what a source key is and where it sits:

- the comparator (``compare``) diffs two flat forms key by key;
- duplicate merging (``compare.canonical_key``) uses the same form, so two
  copies merge only when the comparator would call them identical;
- the per-type mappers record each documented loss at its exact path;
- the planner records each target-version deviation at its exact path;
- the source accounting (``accounting``) classifies every flat key.

Nothing is collapsed: text and attribute values are kept verbatim (a
whitespace-only change is a difference). What a flat form leaves out is
only what the product renumbers on export or import; each such key is
removed and counted in ``set_aside`` by class, never dropped silently:

- views: ``Control@id``, ``DataProvider@id`` and the column ``Item``'s
  ``Property name="id"`` value;
- dashboards: the widget ``id`` (every widget id of the dashboard, wherever
  it appears, is replaced by its position token ``w<i>``), the synthetic
  ``entries`` internal ids (resolved to adapter / kind / name), metric entry
  and Heatmap tab ``extModel`` ids, the View pin's
  ``Ext.vcops.chrome.model.Resource-<n>`` id, ``creationTime``,
  ``lastUpdateTime``, ``userId``, ``lastUpdateUserId``;
- super metrics: ``modificationTime``, ``modifiedBy``.

Whitespace-only text between XML elements (indentation) is formatting, not
content, and is not part of the form.

Path grammar
------------

XML: ``Root/Child/Child@attr`` for an attribute, ``.../Elem#text`` for the
text of an element without children (every such element has one, empty
when it has no text, so an element present on one side only is always a
key). A child is keyed by:

- ``Tag{key}`` where its identity is an attribute or its text (views:
  ``Control{type}``, ``Property{name}``, ``SubjectType{ak|rk|type}``,
  ``SubjectsGroupBy{ak|rk}``, ``Usage{text}``; the key attribute is not a
  separate leaf), a repeat of the same key ``Tag{key}~1``;
- ``Tag[i]`` where order is the identity (``Item``, ``Section``,
  ``SymptomSet``, ...);
- ``Tag`` otherwise, a second element of the same tag ``Tag~1``.

A JSON-valued attribute (a view SubjectType ``filter``) is parsed and its
leaves continue the attribute path: ``...@filter[0][1].metricKey``.

JSON: ``dashboard.<key>`` for dashboard keys, ``widget[i:<Type>].<key>``
for widget keys, ``.k`` for object keys, ``[j]`` for list positions, and an
empty list or object is a leaf (``[]`` / ``{}``). Dashboard and widget
``states`` are keyed by their (normalized) ``key``: ``states{<key>}``.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Callable, Dict, Iterable, Optional, Tuple

Leaves = Dict[str, object]

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_UUID_RE = re.compile(UUID)
EMPTY_LIST = "[]"
EMPTY_DICT = "{}"


class _EmptyMarker(str):
    """The leaf value of an empty JSON list or object (distinct from a string)."""


EMPTY_LIST_LEAF = _EmptyMarker(EMPTY_LIST)
EMPTY_DICT_LEAF = _EmptyMarker(EMPTY_DICT)


# ------------------------------------------------------------------ JSON
def flatten_json(node, path: str, out: Leaves) -> None:
    """Every leaf of a JSON value under ``path`` (empty list / dict are leaves)."""
    if isinstance(node, dict):
        if not node:
            out[path] = EMPTY_DICT_LEAF
            return
        for k, v in node.items():
            flatten_json(v, f"{path}.{k}", out)
        return
    if isinstance(node, list):
        if not node:
            out[path] = EMPTY_LIST_LEAF
            return
        for i, v in enumerate(node):
            flatten_json(v, f"{path}[{i}]", out)
        return
    out[path] = node


# ------------------------------------------------------------------- XML
#: XML elements whose order is their identity (keyed by position).
POSITIONAL_TAGS = frozenset({"Item", "Section", "SymptomSet", "Symptom", "Recommendation", "OutputFormat",
                             "DataProvider", "Condition"})
#: Per-root-tag positional overrides: a report's SubjectType list is ordered.
_POSITIONAL_BY_ROOT = {"ReportDef": frozenset({"SubjectType"})}


def _view_key(child) -> Optional[Tuple[str, Tuple[str, ...]]]:
    """``(key text, attributes the key consumes)`` for a keyed view child."""
    tag = child.tag
    if tag == "Control":
        return child.get("type") or "", ("type",)
    if tag == "Property":
        return child.get("name") or "", ("name",)
    if tag == "SubjectType":
        return "|".join(child.get(a) or "" for a in ("adapterKind", "resourceKind", "type")), (
            "adapterKind", "resourceKind", "type")
    if tag == "SubjectsGroupBy":
        return "|".join(child.get(a) or "" for a in ("adapterKind", "resourceKind")), ("adapterKind", "resourceKind")
    if tag == "Usage" and not len(child):
        return (child.text or ""), ("#text",)
    return None


def _no_key(child):
    return None


def flatten_xml(root, *, keyer: Callable = _no_key, drop: Optional[Callable] = None,
                json_attrs: Iterable[str] = (), set_aside: Optional[Counter] = None) -> Leaves:
    """The flat form of an element tree.

    ``keyer(child)`` returns ``(key, consumed)`` for a keyed child (its key
    attributes, or ``"#text"``, are then not separate leaves) or ``None``.
    ``drop(elem, attr) -> class`` names a renumbered attribute to leave out
    (counted in ``set_aside`` under that class), or returns ``None``.
    ``json_attrs``: attributes whose value is JSON, flattened below the
    attribute path when it parses (kept verbatim when it does not).
    """
    out: Leaves = {}
    sa = set_aside if set_aside is not None else Counter()
    jattrs = frozenset(json_attrs)
    positional = POSITIONAL_TAGS | _POSITIONAL_BY_ROOT.get(root.tag, frozenset())

    def walk(el, path: str, consumed: Tuple[str, ...]) -> None:
        for k, v in el.attrib.items():
            if k in consumed:
                continue
            cls = drop(el, k) if drop else None
            if cls:
                sa[cls] += 1
                continue
            p = f"{path}@{k}"
            if k in jattrs:
                try:
                    j = json.loads(v)
                except ValueError:
                    out[p] = v
                else:
                    flatten_json(j, p, out)
                continue
            out[p] = v
        kids = list(el)
        if not kids:
            if "#text" not in consumed:
                out[f"{path}#text"] = el.text or ""
            else:
                out[path] = ""  # presence of an element its key fully describes (a Usage)
            return
        if el.text and el.text.strip():
            out[f"{path}#text"] = el.text
        seen: Counter = Counter()
        pos: Counter = Counter()
        for c in kids:
            if not isinstance(c.tag, str):
                continue  # a comment or processing instruction
            keyed = keyer(c)
            if keyed is not None:
                key, cons = keyed
                n = seen[(c.tag, key)]
                seen[(c.tag, key)] += 1
                seg = f"{c.tag}{{{key}}}" + (f"~{n}" if n else "")
            elif c.tag in positional:
                seg = f"{c.tag}[{pos[c.tag]}]"
                pos[c.tag] += 1
                cons = ()
            else:
                n = seen[(c.tag, None)]
                seen[(c.tag, None)] += 1
                seg = c.tag + (f"~{n}" if n else "")
                cons = ()
            walk(c, f"{path}/{seg}", cons)
            if c.tail and c.tail.strip():
                out[f"{path}/{seg}#tail"] = c.tail

    walk(root, root.tag, ())
    return out


# ------------------------------------------------------------------ views
VIEW = "ViewDef"
VIEW_RENUMBERED = "renumbered ids (view control, data provider, column Item id)"


def view_control(ctype: str) -> str:
    return f"{VIEW}/Controls/Control{{{ctype}}}"


def view_prop(parent: str, name: str) -> str:
    return f"{parent}/Property{{{name}}}"


def view_column(i: int, prop: Optional[str] = None) -> str:
    p = f"{view_prop(view_control('attributes-selector'), 'attributeInfos')}/List/Item[{i}]"
    return f"{p}/Value/Property{{{prop}}}" if prop else p


def view_additional_column(i: int, prop: Optional[str] = None) -> str:
    p = f"{view_prop(view_control('metadata'), 'distributionAdditionalColumns')}/List/Item[{i}]"
    return f"{p}/Value/Property{{{prop}}}" if prop else p


def view_subject(ak: str, rk: str, t: str, n: int = 0) -> str:
    return f"{VIEW}/SubjectType{{{ak}|{rk}|{t}}}" + (f"~{n}" if n else "")


def _view_drop(el, attr: str) -> Optional[str]:
    if attr == "id" and el.tag in ("Control", "DataProvider"):
        return VIEW_RENUMBERED
    return None


def flatten_view(elem, set_aside: Optional[Counter] = None) -> Leaves:
    sa = set_aside if set_aside is not None else Counter()
    leaves = flatten_xml(elem, keyer=_view_key, drop=_view_drop, json_attrs=("filter",), set_aside=sa)
    # The column (and additional column) Item's ``id`` Property is
    # product-assigned as a whole (the renderer writes its own or none).
    rx = re.compile(r"/List/Item\[\d+\]/Value/Property\{id\}(~\d+)?(?=[@#/]|$)")
    props = set()
    for p in [p for p in leaves if rx.search(p)]:
        props.add(p[:rx.search(p).end()])
        del leaves[p]
    sa[VIEW_RENUMBERED] += len(props)
    return leaves


# -------------------------------------------------------- other XML types
def flatten_plain_xml(elem, set_aside: Optional[Counter] = None) -> Leaves:
    """Report templates, alerts, symptoms, recommendations: no renumbered ids."""
    return flatten_xml(elem, set_aside=set_aside)


# ------------------------------------------------------------- dashboards
DASH = "dashboard"
DASH_SERVER_KEYS = ("creationTime", "lastUpdateTime", "userId", "lastUpdateUserId")
_RK_REF = re.compile(r"resourceKind:id:\d+_::_")
_RES_REF = re.compile(r"resource:id:\d+_::_")


def widget_path(i: int, wtype: str) -> str:
    return f"widget[{i}:{wtype}]"


def flatten_dashboard(db: dict, entries: dict, idmap: Dict[str, str],
                      set_aside: Optional[Counter] = None) -> Leaves:
    """The flat form of one dashboard.

    ``idmap``: lower-case uuid -> replacement for every id that the
    comparison should see changed (intended id rewrites; widget ids of
    other dashboards -> their rendered ids). This dashboard's own widget ids
    become their position token ``w<i>``. Synthetic ``entries`` ids resolve
    to ``RK:<adapter>/<kind>`` and ``RES:<adapter>/<kind>/<name>``, and the
    ``entries`` rows this dashboard uses are compared field by field under
    ``entries.resourceKind{RK:...}`` / ``entries.resource{RES:...}``.
    A ``dashboardNavigations`` key that is not one of the dashboard's
    widgets becomes ``stale:<id>`` (no widget can fire it).
    """
    sa = set_aside if set_aside is not None else Counter()
    rows: Dict[str, Dict[str, tuple]] = {"resourceKind": {}, "resource": {}}
    fmts = {"resourceKind": lambda e: "RK:%s/%s" % (e.get("adapterKindKey"), e.get("resourceKindKey")),
            "resource": lambda e: "RES:%s/%s/%s" % (e.get("adapterKindKey"), e.get("resourceKindKey"), e.get("name"))}
    for table, fmt in fmts.items():
        for e in (entries or {}).get(table, []) or []:
            if isinstance(e, dict) and isinstance(e.get("internalId"), str):
                rows[table][e["internalId"]] = (fmt(e), e)
    used: Dict[str, Dict[str, dict]] = {"resourceKind": {}, "resource": {}}
    widgets = db.get("widgets") if isinstance(db.get("widgets"), list) else []
    own = {}
    for i, w in enumerate(widgets):
        if isinstance(w, dict) and isinstance(w.get("id"), str):
            own[w["id"].lower()] = f"w{i}"
    lower_map = {k.lower(): v for k, v in idmap.items()}

    def ref(table):
        def sub(m):
            hit = rows[table].get(m.group(0))
            if hit is None:
                return m.group(0)
            used[table][hit[0]] = hit[1]
            return hit[0]
        return sub

    def fix_str(s: str) -> str:
        s = _RK_REF.sub(ref("resourceKind"), s)
        s = _RES_REF.sub(ref("resource"), s)
        return _UUID_RE.sub(lambda m: own.get(m.group(0).lower()) or lower_map.get(m.group(0).lower(),
                                                                                  m.group(0).lower()), s)

    def norm(x, path: str):
        if isinstance(x, dict):
            o = {}
            for k, v in x.items():
                kp = f"{path}.{k}"
                if k == "id" and isinstance(v, str) and v.startswith("extModel") and re.search(
                        r"(resourceKindMetrics|resourceMetrics|configs)\[\d+\]$", path):
                    sa["renumbered ids (extModel)"] += 1
                    continue
                if (k == "id" and path.endswith(".config.resource") and isinstance(v, str)
                        and v.startswith("Ext.vcops.chrome.model.Resource-")):
                    sa["renumbered ids (pin Ext resource)"] += 1
                    continue
                if k == "widgetId" and path.endswith(".config"):
                    sa["renumbered ids (config.widgetId, compared as its position token)"] += 1
                o[fix_str(k) if isinstance(k, str) else k] = norm(v, kp)
            return o
        if isinstance(x, list):
            return [norm(v, f"{path}[{i}]") for i, v in enumerate(x)]
        if isinstance(x, str):
            return fix_str(x)
        return x

    def emit(obj: dict, base: str, out: Leaves) -> None:
        for k, v in obj.items():
            kp = f"{base}.{k}"
            if (k == "states" and isinstance(v, list) and v
                    and all(isinstance(s, dict) and "key" in s for s in v)):
                seen: Dict[str, int] = {}
                for s in v:
                    key = "{%s}" % fix_str(str(s.get("key")))
                    n = seen.get(key, 0)
                    seen[key] = n + 1
                    sp = f"{kp}{key}" + (f"~{n}" if n else "")
                    body = {a: b for a, b in s.items() if a != "key"}
                    flatten_json(norm(body, sp) if body else {}, sp, out)
                continue
            if k == "dashboardNavigations" and base == DASH and isinstance(v, dict) and v:
                for wid, entries_ in v.items():
                    tok = own.get(str(wid).lower()) or f"stale:{str(wid).lower()}"
                    flatten_json(norm(entries_, f"{kp}.{tok}"), f"{kp}.{tok}", out)
                continue
            flatten_json(norm(v, kp), kp, out)

    out: Leaves = {}
    for k in DASH_SERVER_KEYS:
        if k in db:
            sa[f"server metadata ({k})"] += 1
    emit({k: v for k, v in db.items() if k not in DASH_SERVER_KEYS and k not in ("widgets", "entries")}, DASH, out)
    if "widgets" in db and not isinstance(db.get("widgets"), list):
        out[f"{DASH}.widgets"] = db.get("widgets")
    elif "widgets" in db and not widgets:
        out[f"{DASH}.widgets"] = EMPTY_LIST_LEAF
    for i, w in enumerate(widgets):
        if not isinstance(w, dict):
            out[f"widget[{i}:?]"] = w
            continue
        base = widget_path(i, str(w.get("type")))
        if "id" in w:
            sa["renumbered ids (widget)"] += 1
        body = {k: v for k, v in w.items() if k != "id"}
        if not body:
            out[base] = EMPTY_DICT_LEAF
        emit(body, base, out)
    for table in ("resourceKind", "resource"):
        for tok, row in sorted(used[table].items()):
            sa["renumbered ids (entries internalId)"] += 1
            body = {k: v for k, v in row.items() if k != "internalId"}
            flatten_json(body, f"entries.{table}{{{tok}}}", out)
    return out


# ----------------------------------------------------------- super metrics
SM = "supermetric"
SM_SERVER_KEYS = ("modificationTime", "modifiedBy")


def flatten_supermetric(sm: dict, set_aside: Optional[Counter] = None) -> Leaves:
    sa = set_aside if set_aside is not None else Counter()
    out: Leaves = {}
    for k in SM_SERVER_KEYS:
        if k in sm:
            sa[f"server metadata ({k})"] += 1
    flatten_json({k: v for k, v in sm.items() if k not in SM_SERVER_KEYS}, SM, out)
    return out


# --------------------------------------------------------------- generic
_GEN_SUBS = (
    (re.compile(r"widget\[\d+:([^\]]*)\]"), r"widget:\1"),
    (re.compile(r"\[\d+\]"), "[]"),
    (re.compile(r"~\d+"), "~*"),
    (re.compile(r"\.dashboardNavigations\.stale:[^.\[]+"), ".dashboardNavigations.stale:*"),
    (re.compile(r"\.dashboardNavigations\.(?!stale:\*)[^.\[]+"), ".dashboardNavigations.*"),
    (re.compile(r"states\{[^}]*\}"), "states{*}"),
    (re.compile(r"(SubjectType|SubjectsGroupBy|Usage)\{[^}]*\}"), r"\1{*}"),
    (re.compile(r"^entries\.(resourceKind|resource)\{[^}]*\}"), r"entries.\1{*}"),
)


def generic(path: str) -> str:
    """A path with its positions and instance keys generalized, for the
    accounting tables: ``widget[3:View].config.x`` -> ``widget:View.config.x``,
    ``Item[2]`` -> ``Item[]``, a repeat ``~1`` -> ``~*``, navigation and state
    keys and SubjectType / Usage keys -> ``*``. ``Control{type}`` and
    ``Property{name}`` keep their key: the rules depend on it."""
    for rx, rep in _GEN_SUBS:
        path = rx.sub(rep, path)
    return path


def under(path: str, root: str) -> bool:
    """``path`` is ``root`` or a key below it."""
    if path == root:
        return True
    return path.startswith(root) and path[len(root)] in "/.@[#{~"
