"""Plan an offline conversion: source objects -> factory YAML documents.

``plan_conversion`` takes an :class:`~.inputs.InputScan` and
:class:`ConvertOptions` and returns a :class:`Plan`: every object either
emitted (with its YAML text and target path relative to the output root),
dropped on request, or failed with the reason. Nothing is read from disk
and nothing is written here; the factory wrapper
(``vcfcf_extractor.importer``) writes the plan and verifies it.

Order of decisions, each reported:

1. **Duplicates.** The same id found in several files is one object when
   the copies are the same once renumbered ids and whitespace are set aside
   (``compare.canonical_key``); when they differ the object fails, naming
   every file, unless ``prefer_sources`` names the copy that wins.
2. **Drops.** Objects whose id is in ``drop`` are not emitted; references
   to them stay raw ids (the caller references the product object in place).
3. **Mapping** (per-type modules). A ``MappingError`` fails the object.
4. **Names.** ``rename`` (old name or id -> new name), then ``naming``
   (``factory-prefixed`` adds ``[VCF CF] ``). Two objects of one type with
   the same final name fail, naming both sources.
5. **Ids.** ``keep`` carries source ids; ``mint`` gives every object a new
   UUID; ``map`` applies ``id_map`` and keeps the rest. Every reference
   follows. The stock-id guard runs on the result in the wrapper.
6. **References.** By name inside the set, by raw id outside it where the
   schema has a raw-id form; otherwise the referencing object fails. An
   object that references a failed one fails too (cascade, named).
7. **Target version.** With ``target_min``, an ``omit:`` entry whose proven
   floor is above it is not emitted (the key renders), and each such
   deviation is listed; widgets needing a newer product (Section) are
   reported, not converted away. Without it the source is reproduced and
   the same things are warned about.
"""
from __future__ import annotations

import copy
import re
import uuid
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

import yaml

from ..dashboards.loader import DASHBOARD_NAME_MAX_LEN, WIDGET_OMIT_KEYS
from ..dashboards.widget_versions import (
    DASHBOARD_OMIT_MIN_OPS_VERSION,
    HEATMAP_TAB_OMIT_MIN_OPS_VERSION,
    METRIC_OMIT_MIN_OPS_VERSION,
    OLDEST_OMIT_EVIDENCE,
    WIDGET_OMIT_MIN_OPS_VERSION,
    WIDGET_TYPE_MIN_OPS_VERSION,
    format_ops_version,
    parse_ops_version,
)
from ..naming import FACTORY_PREFIX, has_factory_prefix, has_legacy_prefix, strip_factory_prefix
from ..reports.loader import SECTION_OMIT_MIN_OPS_VERSION
from ..symptoms.loader import SYMPTOM_OMIT_MIN_OPS_VERSION
from . import alerts as _alerts
from . import dashboards as _dash
from . import reports as _reports
from . import supermetrics as _sms
from . import views as _views
from .compare import canonical_key
from .inputs import CONTENT_TYPES, InputScan, SourceObject
from .model import MappedObject, MappingError
from .refs import FormulaRef, NavRef, Ref, UnresolvedReference

TARGET_VERSIONS = ("8.18.7", "9.0.2", "9.1.1")
TYPE_DIRS = {"supermetric": "supermetrics", "view": "views", "dashboard": "dashboards", "report": "reports",
             "symptom": "symptoms", "recommendation": "recommendations", "alert": "alerts"}
_ID_PREFIX = {"symptom": "SymptomDefinition-", "alert": "AlertDefinition-"}
_UUID_LOWER = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_UUID_ANY = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_REC_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_SM_TOKEN = re.compile(r"sm_([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
_SM_FORMULA_TERM = re.compile(
    r"((?i:super\s*metric)\s*\|\s*)?sm_([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
_UUID_IN = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
LAYOUTS = ("content", "third-party", "pak")


def norm_id(type_: str, raw: str) -> str:
    """Comparison form of a source id: stripped of the XML prefix, lower case."""
    s = str(raw or "").strip()
    p = _ID_PREFIX.get(type_)
    if p and s.startswith(p):
        s = s[len(p):]
    return s.lower()


@dataclass
class ConvertOptions:
    ids: str = "keep"                          # keep | mint | map
    id_map: Dict[str, str] = field(default_factory=dict)   # old (norm) -> new
    drop: Dict[str, str] = field(default_factory=dict)     # id (norm) -> label
    naming: str = "unprefixed"                 # unprefixed | factory-prefixed
    rename: Dict[str, str] = field(default_factory=dict)   # old name or id -> new name
    target_min: Optional[str] = None
    prefer_sources: List[str] = field(default_factory=list)
    layout: str = "third-party"
    minter: Callable[[], str] = field(default=lambda: str(uuid.uuid4()))


@dataclass
class Failure:
    type: str
    id: str
    name: str
    locations: List[str]
    reason: str
    gap: Optional[Dict[str, str]] = None


@dataclass
class Deviation:
    """A difference from the source the target version forces."""
    entry: str
    wire_keys: Tuple[str, ...]
    text: str


@dataclass
class Emitted:
    type: str
    source: SourceObject
    source_id: str
    id: str
    name: str
    relpath: str = ""
    yaml_tree: Dict[str, object] = field(default_factory=dict)
    text: str = ""
    losses: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    deviations: List[Deviation] = field(default_factory=list)
    version_warnings: List[str] = field(default_factory=list)
    #: the source id is the one the renderer derives from the name (no id: in the YAML)
    derived: bool = False


@dataclass
class Plan:
    emitted: List[Emitted] = field(default_factory=list)
    failures: List[Failure] = field(default_factory=list)
    dropped: List[Tuple[str, str, str, List[str]]] = field(default_factory=list)
    merged_duplicates: List[Tuple[str, str, List[str]]] = field(default_factory=list)
    resolved_duplicates: List[Tuple[str, str, str, List[str]]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    found: Counter = field(default_factory=Counter)
    #: (type, old id, new id, name) for every emitted object
    id_table: List[Tuple[str, str, str, str]] = field(default_factory=list)
    #: old norm id -> new id, for every object whose id changed
    id_rewrites: Dict[str, str] = field(default_factory=dict)
    #: (type, norm source id) -> final name, for every emitted object
    names: Dict[Tuple[str, str], str] = field(default_factory=dict)
    usage_error: Optional[str] = None

    def counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for t in CONTENT_TYPES:
            em = [e for e in self.emitted if e.type == t]
            out[t] = {
                "found": self.found.get(t, 0),
                "converted": len(em),
                "with_losses": sum(1 for e in em if e.losses),
                "failed": sum(1 for f in self.failures if f.type == t),
                "dropped": sum(1 for d in self.dropped if d[0] == t),
            }
        return out


# ------------------------------------------------------------------ helpers
def parse_tsv_map(text: str, what: str) -> Dict[str, str]:
    """Two-column TSV (``old<TAB>new``, extra columns ignored). A first row
    whose first cell is a column label (``old_id``, ``old``, ``id``,
    ``old_name``, ``name``) is a header; ``#`` lines and blank lines are
    skipped. Raises ValueError on a malformed row or a repeated key."""
    out: Dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.rstrip("\r\n").split("\t")
        if n == 1 and cells[0].strip().lower() in ("old_id", "old", "id", "old_name", "name"):
            continue
        if len(cells) < 2 or not cells[0].strip() or not cells[1].strip():
            raise ValueError(f"{what}: line {n}: expected two tab-separated columns, got {line!r}")
        k = cells[0].strip()
        if k in out:
            raise ValueError(f"{what}: line {n}: {k!r} is listed twice")
        out[k] = cells[1].strip()
    return out


def parse_id_list(text: str, what: str) -> Dict[str, str]:
    """One id per row (first TSV column; extra columns are a label). Header
    and comment rules as :func:`parse_tsv_map`."""
    out: Dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.rstrip("\r\n").split("\t")
        if n == 1 and cells[0].strip().lower() in ("old_id", "old", "id", "name"):
            continue
        out[cells[0].strip()] = " | ".join(c.strip() for c in cells[1:3] if c.strip())
    return out


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", strip_factory_prefix(name)).strip("-").lower()
    return (s or "object")[:80].rstrip("-")


def to_plain(tree):
    if isinstance(tree, dict):
        return {k: to_plain(v) for k, v in tree.items()}
    if isinstance(tree, list):
        return [to_plain(v) for v in tree]
    return tree


def dump_yaml(tree: dict, header: str = "") -> str:
    body = yaml.safe_dump(to_plain(tree), sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
    return (header + body) if header else body


def _version_floor_text(floor) -> str:
    return format_ops_version(floor) if floor is not None else "unknown (no product export shows it)"


# ------------------------------------------------------------------- plan
class _Planner:
    def __init__(self, scan: InputScan, opts: ConvertOptions):
        self.scan = scan
        self.opts = opts
        self.plan = Plan()
        self.target = parse_ops_version(opts.target_min) if opts.target_min else None

    def fail(self, obj: SourceObject, reason: str, gap=None) -> None:
        self.plan.failures.append(Failure(obj.type, obj.id, obj.name, list(obj.locations), reason, gap))

    # 1. duplicates ----------------------------------------------------
    def dedupe(self) -> List[SourceObject]:
        groups: "OrderedDict[Tuple[str, str], List[SourceObject]]" = OrderedDict()
        for o in self.scan.objects:
            groups.setdefault((o.type, norm_id(o.type, o.id)), []).append(o)
        unique: List[SourceObject] = []
        for (t, nid), copies in groups.items():
            self.plan.found[t] += 1
            forms: "OrderedDict[str, List[SourceObject]]" = OrderedDict()
            for c in copies:
                forms.setdefault(canonical_key(c), []).append(c)
            locs = [c.location for c in copies]
            if len(forms) == 1:
                first = copies[0]
                first.locations = locs
                if len(copies) > 1:
                    self.plan.merged_duplicates.append((t, first.id, locs))
                unique.append(first)
                continue
            # differing copies: does a preferred source pick exactly one form?
            chosen = None
            for pref in self.opts.prefer_sources:
                hits = [k for k, cs in forms.items() if any(pref in c.location for c in cs)]
                if len(hits) == 1:
                    chosen = hits[0]
                    break
            if chosen is not None:
                winner = forms[chosen][0]
                winner.locations = locs
                self.plan.resolved_duplicates.append((t, winner.id, winner.location, locs))
                unique.append(winner)
                continue
            first = copies[0]
            first.locations = locs
            by_form = "; ".join(f"copy {i + 1}: {', '.join(c.location for c in cs)}"
                                for i, cs in enumerate(forms.values()))
            self.fail(first, f"the same id is defined differently in several files ({by_form}); "
                             f"say which copy wins with --prefer-source <path fragment>")
        return unique

    # 2. drops ---------------------------------------------------------
    def apply_drops(self, objs: List[SourceObject]) -> List[SourceObject]:
        drop = {norm_id("", k): v for k, v in self.opts.drop.items()}
        used = set()
        kept = []
        for o in objs:
            nid = norm_id(o.type, o.id)
            if nid in drop:
                used.add(nid)
                self.plan.dropped.append((o.type, o.id, o.name, list(o.locations)))
            else:
                kept.append(o)
        for k in drop:
            if k not in used:
                self.plan.warnings.append(f"drop list: {k} names no object in the input")
        self.dropped_keys = {(t, norm_id(t, i)) for t, i, _, _ in self.plan.dropped}
        return kept

    # 3. mapping -------------------------------------------------------
    def map_all(self, objs: List[SourceObject]) -> List[Tuple[SourceObject, MappedObject]]:
        rec_kind: Dict[str, str] = {}
        for o in objs:
            if o.type == "alert":
                rr = o.payload.find("State/Recommendations")
                for r in (rr if rr is not None else []):
                    if r.get("ref"):
                        rec_kind.setdefault(r.get("ref"), o.payload.get("adapterKind") or "")
        out = []
        for o in sorted(objs, key=lambda x: (CONTENT_TYPES.index(x.type), x.location, x.id)):
            try:
                if o.type == "view":
                    m = _views.map_view(o.payload, o.location)
                elif o.type == "dashboard":
                    m = _dash.map_dashboard(o.payload, o.context, o.location)
                elif o.type == "report":
                    m = _reports.map_report(o.payload, o.location)
                elif o.type == "symptom":
                    m = _alerts.map_symptom(o.payload, o.location)
                elif o.type == "alert":
                    m = _alerts.map_alert(o.payload, o.location)
                elif o.type == "recommendation":
                    kind = rec_kind.get(o.id)
                    m = _alerts.map_recommendation(o.payload, o.location, kind or "VMWARE")
                    if not kind:
                        m.notes.append("adapter_kind is not in the source and no alert in the set references "
                                       "this recommendation; VMWARE is written (unused on the wire: the "
                                       "explicit id is rendered)")
                elif o.type == "supermetric":
                    m = _sms.map_supermetric(o.id, o.payload, o.location)
                else:  # pragma: no cover
                    raise MappingError(f"unknown type {o.type}")
            except MappingError as exc:
                self.fail(o, str(exc), exc.gap)
                continue
            out.append((o, m))
        return out

    # 4. names -----------------------------------------------------------
    def final_name(self, o: SourceObject, name: str) -> str:
        rename = self.opts.rename
        for key in (o.id, norm_id(o.type, o.id), name):
            if key in rename:
                self.rename_used.add(key)
                name = rename[key]
                break
        if self.opts.naming == "factory-prefixed":
            if has_legacy_prefix(name):
                name = FACTORY_PREFIX + strip_factory_prefix(name)
            elif not has_factory_prefix(name):
                name = FACTORY_PREFIX + name
        return name

    # 5. ids --------------------------------------------------------------
    def final_id(self, o: SourceObject) -> str:
        nid = norm_id(o.type, o.id)
        raw = o.id[len(_ID_PREFIX[o.type]):] if o.type in _ID_PREFIX and o.id.startswith(_ID_PREFIX[o.type]) else o.id
        mapping = {norm_id("", k): v for k, v in self.opts.id_map.items()}
        if self.opts.ids == "mint":
            new = self.opts.minter()
            return f"Recommendation-{new}" if o.type == "recommendation" else new
        if nid in mapping:
            self.map_used.add(nid)
            return norm_id(o.type, mapping[nid]) if o.type != "recommendation" else mapping[nid]
        if o.type in ("view", "dashboard", "report", "supermetric"):
            return raw.lower()
        return raw

    def derived_id(self, e: "Emitted") -> bool:
        """True when ``e`` keeps its source id and that id is the one the
        alert renderer derives (``<Type>-<adapter>-<slug of name>``)."""
        if e.type not in ("symptom", "alert", "recommendation"):
            return False
        raw = e.source_id
        if e.type in _ID_PREFIX and raw.startswith(_ID_PREFIX[e.type]):
            raw = raw[len(_ID_PREFIX[e.type]):]
        if e.id != raw:
            return False
        from ..alerts.render import _alert_id, _rec_key, _symptom_id
        ak = str(e.yaml_tree.get("adapter_kind") or "")
        derived = {"symptom": lambda: _symptom_id(ak, e.name), "alert": lambda: _alert_id(ak, e.name),
                   "recommendation": lambda: _rec_key(ak, e.name)}[e.type]()
        return derived == e.source_id

    def id_problem(self, t: str, fid: str) -> Optional[str]:
        if t in ("view", "dashboard", "report", "supermetric") and not _UUID_LOWER.match(fid):
            return f"id {fid!r} is not a UUID, which the {t} loader requires"
        if t == "alert" and not _UUID_ANY.match(fid):
            return (f"id AlertDefinition-{fid} does not end in a UUID, which the alert YAML requires "
                    f"(explicit alert ids are UUIDs)")
        if t == "recommendation" and not _REC_KEY.match(fid):
            return f"recommendation key {fid!r} is not an XML id the recommendation YAML accepts"
        if t == "symptom" and not fid:
            return "empty symptom id"
        return None

    # ---------------------------------------------------------------- run
    def run(self) -> Plan:
        p = self.plan
        objs = self.apply_drops(self.dedupe())
        mapped = self.map_all(objs)
        self.rename_used: Set[str] = set()
        self.map_used: Set[str] = set()
        entries: List[Emitted] = []
        for o, m in mapped:
            e = Emitted(o.type, o, o.id, "", "", losses=list(m.losses), notes=list(m.notes))
            e.yaml_tree = m.yaml
            e.name = self.final_name(o, str(m.yaml.get("name", "")))
            e.id = self.final_id(o)
            entries.append(e)
        for k in self.opts.rename:
            if k not in self.rename_used:
                p.warnings.append(f"rename file: {k!r} names no object in the input")
        for k in self.opts.id_map:
            if norm_id("", k) not in self.map_used:
                p.warnings.append(f"id map: {k} names no object in the input")
        # Objects that already failed (differing duplicate copies, mapping
        # errors) are failed targets too: a reference to one must not fall
        # through to the raw-id form as if it were product content.
        failed: Dict[Tuple[str, str], str] = {
            (f.type, norm_id(f.type, f.id)): f.reason for f in p.failures
        }

        def mark(e: Emitted, reason: str, gap=None):
            key = (e.type, norm_id(e.type, e.source_id))
            if key not in failed:
                failed[key] = reason
                self.fail(e.source, reason, gap)

        # name collisions and id problems
        by_name: Dict[Tuple[str, str], List[Emitted]] = defaultdict(list)
        by_id: Dict[Tuple[str, str], List[Emitted]] = defaultdict(list)
        for e in entries:
            by_name[(e.type, e.name)].append(e)
            by_id[(e.type, e.id.lower())].append(e)
            if self.derived_id(e):
                # The source id is the one the renderer derives from the
                # adapter kind and name: the YAML leaves id: out and the
                # render reproduces it.
                e.derived = True
                continue
            prob = self.id_problem(e.type, e.id)
            if prob:
                mark(e, prob + "; use --ids mint, or map it with --id-map")
            if not e.name:
                mark(e, "the source object has no name")
        for (t, n), es in by_name.items():
            if len(es) > 1:
                srcs = "; ".join(f"{x.source_id} in {', '.join(x.source.locations)}" for x in es)
                for x in es:
                    mark(x, f"{len(es)} {t}s share the name {n!r} ({srcs}); by-name references cannot tell "
                            f"them apart: give one a new name with --rename (keyed by id)")
        for (t, i), es in by_id.items():
            if len(es) > 1:
                srcs = "; ".join(f"{x.source_id} ({x.name!r})" for x in es)
                for x in es:
                    mark(x, f"{len(es)} {t}s would ship under the id {i} ({srcs}); fix the id map")
        if self.opts.naming == "factory-prefixed":
            for e in entries:
                if e.type == "dashboard" and len(e.name) > DASHBOARD_NAME_MAX_LEN:
                    mark(e, f"dashboard name {e.name!r} is {len(e.name)} characters with the {FACTORY_PREFIX.strip()} "
                            f"prefix; the factory loader refuses a prefixed name over {DASHBOARD_NAME_MAX_LEN} "
                            f"(the dashboard editor cannot save it). Give it a name of at most "
                            f"{DASHBOARD_NAME_MAX_LEN - len(FACTORY_PREFIX)} characters with --rename")
        if self.opts.layout == "content":
            bad = [e for e in entries if not has_factory_prefix(e.name)]
            if bad:
                p.usage_error = (
                    f"the content/ layout holds factory content, whose names carry the "
                    f"{FACTORY_PREFIX.strip()} prefix; {len(bad)} converted name(s) do not "
                    f"(for example {bad[0].name!r}). Use --naming factory-prefixed, or a "
                    f"third-party or pak layout")

        # references, to a fixed point (an object referencing a failed one fails)
        index: Dict[Tuple[str, str], Emitted] = {(e.type, norm_id(e.type, e.source_id)): e for e in entries}
        changed = True
        resolved: Dict[int, dict] = {}
        while changed:
            changed = False
            for e in entries:
                key = (e.type, norm_id(e.type, e.source_id))
                if key in failed:
                    continue
                try:
                    resolved[id(e)] = self.resolve(e, index, failed)
                except UnresolvedReference as exc:
                    mark(e, str(exc))
                    changed = True
        ok = [e for e in entries if (e.type, norm_id(e.type, e.source_id)) not in failed]
        for e in ok:
            e.yaml_tree = resolved[id(e)]
            e.yaml_tree["name"] = e.name
            if e.derived:
                e.yaml_tree.pop("id", None)
            elif "id" in e.yaml_tree:
                e.yaml_tree["id"] = e.id
            if e.id.lower() != norm_id(e.type, e.source_id) and e.type != "recommendation":
                p.id_rewrites[norm_id(e.type, e.source_id)] = e.id
            elif e.type == "recommendation" and e.id != e.source_id:
                p.id_rewrites[e.source_id] = e.id
            p.names[(e.type, norm_id(e.type, e.source_id))] = e.name
        for e in ok:
            self.rewrite_ids(e)
            self.gate_versions(e)
        self.layout_paths(ok)
        for e in ok:
            rel = ", ".join(e.source.locations)
            e.text = dump_yaml(e.yaml_tree, header=f"# Converted offline by vcfcf_extractor import-local from: {rel}\n")
            p.id_table.append((e.type, e.source_id, e.id, e.name))
        p.emitted = ok
        stale = self.stale_old_ids(ok)
        p.warnings += stale
        return p

    # 6. references ------------------------------------------------------
    def resolve(self, e: Emitted, index, failed) -> dict:
        def target(t: str, rid: str):
            k = (t, norm_id(t, rid))
            if k in failed:
                return "failed", None
            if k in index:
                return "in", index[k]
            return "out", None

        def res(node, parent_key=None):
            if isinstance(node, Ref):
                state, tgt = target(node.type, node.id)
                if state == "failed":
                    raise UnresolvedReference(
                        f"{node.where}: references {node.type} {node.id}, which did not convert "
                        f"(see its own failure)")
                if state == "in":
                    if node.form == "sm_column":
                        return None, f'supermetric:"{tgt.name}"'
                    return None, tgt.name
                if not node.raw_ok:
                    why = "dropped" if (node.type, norm_id(node.type, node.id)) in self.dropped_keys else "not in the input"
                    raise UnresolvedReference(
                        f"{node.where}: references {node.type} {node.id}, which is {why}; the YAML names a "
                        f"{node.type} here by name only, so a reference outside the set cannot be expressed "
                        f"(convert it with this set, or do not drop it)")
                if node.type in ("view", "dashboard") and (node.type, norm_id(node.type, node.id)) not in self.dropped_keys:
                    e.notes.append(f"{node.where}: {node.type} {node.id} is not in the input; referenced by raw id "
                                   f"(it must exist on the target instance)")
                if node.form == "sm_column":
                    e.notes.append(f"{node.where}: super metric {node.id} is not in the input; referenced by its "
                                   f"wire key (it must exist on the target instance)")
                    return None, f"Super Metric|sm_{node.id}"
                return node.external_key, node.id
            if isinstance(node, NavRef):
                state, tgt = target("dashboard", node.dashboard_id)
                if state == "failed":
                    raise UnresolvedReference(f"navigation target dashboard {node.dashboard_id} did not convert")
                if state == "in":
                    lid = _dash.local_widget_ids(tgt.source.payload)
                    widgets = []
                    for w in node.widget_ids:
                        if w in lid:
                            widgets.append(lid[w])
                        else:
                            raise UnresolvedReference(
                                f"navigation to {tgt.name!r} names widget {w}, which is not on that "
                                f"dashboard; the YAML cannot carry it")
                    out = OrderedDict(dashboard=tgt.name, widgets=widgets)
                else:
                    out = OrderedDict(dashboard_id=node.dashboard_id)
                    if node.widget_ids:
                        out["widget_ids"] = list(node.widget_ids)
                    if (("dashboard", norm_id("dashboard", node.dashboard_id)) not in self.dropped_keys):
                        e.notes.append(f"navigation target dashboard {node.dashboard_id} is not in the input; "
                                       f"referenced by raw id")
                if node.label:
                    out["label"] = node.label
                return None, out
            if isinstance(node, FormulaRef):
                # The wire term is ``Super Metric|sm_<uuid>``; the name form
                # @supermetric:"<name>" expands to the whole term, prefix
                # included (supermetrics/crossref.py), so it replaces both.
                def sub(m):
                    st, tgt = target("supermetric", m.group(2))
                    if st == "failed":
                        raise UnresolvedReference(f"formula references super metric {m.group(2)}, which did not convert")
                    if st == "in" and m.group(1):
                        return f'@supermetric:"{tgt.name}"'
                    if st == "in":
                        raise UnresolvedReference(
                            f"formula names super metric {m.group(2)} as a bare sm_<uuid> without the "
                            f"'Super Metric|' prefix; the name form would render the prefix, so the formula "
                            f"cannot be reproduced")
                    e.notes.append(f"formula references super metric {m.group(2)}, which is not in the input "
                                   f"(kept as a raw token; it must exist on the target)")
                    return m.group(0)
                return None, _SM_FORMULA_TERM.sub(sub, node.text)
            if isinstance(node, dict):
                out = OrderedDict()
                for k, v in node.items():
                    nk, nv = res(v, k)
                    out[nk or k] = nv
                return None, out
            if isinstance(node, list):
                return None, [res(v)[1] for v in node]
            return None, node

        tree = copy.deepcopy(e.yaml_tree)
        return res(tree)[1]

    # id rewrites in strings --------------------------------------------
    def rewrite_ids(self, e: Emitted) -> None:
        rw = self.plan.id_rewrites
        if e.type != "dashboard":
            return
        missing_sm = set()

        def sub_str(s: str, key: str) -> str:
            def sm(m):
                nid = m.group(1).lower()
                if ("supermetric", nid) in self.plan.names:
                    return "sm_" + rw.get(nid, m.group(1))
                missing_sm.add(m.group(1))
                return m.group(0)
            s = _SM_TOKEN.sub(sm, s)
            if key in ("html", "view_details", "link", "alert_definitions"):
                s = _UUID_IN.sub(lambda m: rw.get(m.group(0).lower(), m.group(0)), s)
            return s

        def walk(node, key=None):
            if isinstance(node, dict):
                for k, v in list(node.items()):
                    node[k] = walk(v, k)
                return node
            if isinstance(node, list):
                return [walk(v, key) for v in node]
            if isinstance(node, str):
                return sub_str(node, key or "")
            return node
        walk(e.yaml_tree)
        for sid in sorted(missing_sm):
            e.notes.append(f"references super metric {sid}, which is not in the input (kept as its wire key; "
                           f"it must exist on the target instance)")

    def stale_old_ids(self, ok: List[Emitted]) -> List[str]:
        """Old ids of re-identified objects still present in an emitted YAML."""
        rw = self.plan.id_rewrites
        if not rw:
            return []
        out = []
        for e in ok:
            blob = e.text.lower()
            for old in rw:
                if old in blob and old != norm_id(e.type, e.source_id):
                    out.append(f"{e.relpath}: still names the old id {old} of a re-identified object "
                               f"(free text the converter does not rewrite)")
        return out

    # 7. target versions -------------------------------------------------
    def _gate(self, e: Emitted, omit_list: list, entry: str, floor, wire_keys, where: str):
        """Return True to keep the omit entry."""
        if floor is not None and parse_ops_version(floor) <= (self.target or OLDEST_OMIT_EVIDENCE):
            return True
        floor_s = _version_floor_text(floor)
        if self.target is not None:
            text = (f"{where}: omit: {entry} not emitted: its floor is {floor_s}, above the target "
                    f"{format_ops_version(self.target)}; the render carries {'/'.join(wire_keys)} where the "
                    f"source leaves it out")
            e.deviations.append(Deviation(entry, tuple(wire_keys), text))
            return False
        e.version_warnings.append(
            f"{where}: omit: {entry} reproduces the source, but its floor is {floor_s}, above "
            f"{format_ops_version(OLDEST_OMIT_EVIDENCE)} (the oldest export read): a Tier 2 pak build "
            f"fails on it and content builds warn; pass --target-min to emit the key instead")
        return True

    def gate_versions(self, e: Emitted) -> None:
        y = e.yaml_tree
        if e.type == "dashboard":
            om = y.get("omit") or []
            wire = {"temporary": ("temporary",), "name_path": ("namePath",), "folder_in_name": ("name",),
                    "widget_interactions": ("widgetInteractions",)}
            keep = [x for x in om if self._gate(e, om, x, DASHBOARD_OMIT_MIN_OPS_VERSION.get(x),
                                                wire.get(x, (x,)), f"dashboard {e.name!r}")]
            if "folder_in_name" in om and "folder_in_name" not in keep:
                e.deviations[-1].text += " (the dashboard name then carries its folder)"
            if keep:
                y["omit"] = keep
            elif "omit" in y:
                del y["omit"]
            for w in y.get("widgets") or []:
                wt = w.get("type")
                floor = WIDGET_TYPE_MIN_OPS_VERSION.get(wt)
                if floor is not None and (self.target is None or self.target < parse_ops_version(floor)):
                    scope = (f"the target {format_ops_version(self.target)}" if self.target is not None
                             else "any build below it (no --target-min given)")
                    e.version_warnings.append(
                        f"dashboard {e.name!r} widget {w.get('id')} ({wt}): needs VCF Operations "
                        f"{format_ops_version(floor)} or later; on {scope} the importer aborts the whole "
                        f"dashboard (issue #199). Not converted away; a Tier 2 pak build fails on it")
                wo = w.get("omit") or []
                if wo:
                    kept = [x for x in wo if self._gate(
                        e, wo, x, WIDGET_OMIT_MIN_OPS_VERSION.get((wt, x)),
                        (WIDGET_OMIT_KEYS.get(wt, {}).get(x, (x,))[-1],),
                        f"dashboard {e.name!r} widget {w.get('id')} ({wt})")]
                    if kept:
                        w["omit"] = kept
                    else:
                        del w["omit"]
                mwire = {"label": ("label",), "max_value": ("maxValue",),
                         "handle_old_coloring": ("handleOldColoring",), "unit": ("unit", "metricUnitId"),
                         "link": ("link",)}
                for mi, m in enumerate(w.get("metrics") or []):
                    mo = m.get("omit") or []
                    if mo:
                        kept = [x for x in mo if self._gate(e, mo, x, METRIC_OMIT_MIN_OPS_VERSION.get(x),
                                                            mwire.get(x, (x,)),
                                                            f"dashboard {e.name!r} widget {w.get('id')} metric {mi}")]
                        if kept:
                            m["omit"] = kept
                        else:
                            del m["omit"]
                twire = {"tag_filter": ("tagFilter",), "custom_filter": ("customFilter",),
                         "color_min_value": ("minValue",), "group_by_kind_keys": ("adapterKind", "resourceKind")}
                for ti, tab in enumerate(w.get("configs") or []):
                    to = tab.get("omit") or []
                    if to:
                        kept = [x for x in to if self._gate(e, to, x, HEATMAP_TAB_OMIT_MIN_OPS_VERSION.get(x),
                                                            twire.get(x, (x,)),
                                                            f"dashboard {e.name!r} widget {w.get('id')} tab {ti}")]
                        if kept:
                            tab["omit"] = kept
                        else:
                            del tab["omit"]
        elif e.type == "report":
            for si, s in enumerate(y.get("sections") or []):
                so = s.get("omit") or []
                if so:
                    kept = [x for x in so if self._gate(e, so, x, SECTION_OMIT_MIN_OPS_VERSION.get(x),
                                                        ("ContentFormatting",), f"report {e.name!r} section {si}")]
                    if kept:
                        s["omit"] = kept
                    else:
                        del s["omit"]
                        s["colorize"] = True
        elif e.type == "symptom":
            so = y.get("omit") or []
            if so:
                wire = {"wait_cycles": ("waitCycle",), "cancel_cycles": ("cancelCycle",), "instanced": ("instanced",)}
                kept = [x for x in so if self._gate(e, so, x, SYMPTOM_OMIT_MIN_OPS_VERSION.get(x),
                                                    wire.get(x, (x,)), f"symptom {e.name!r}")]
                if kept:
                    y["omit"] = kept
                else:
                    del y["omit"]

    # layout ---------------------------------------------------------------
    def layout_paths(self, ok: List[Emitted]) -> None:
        used: Set[str] = set()
        for e in ok:
            base = f"{TYPE_DIRS[e.type]}/{slug(e.name)}"
            rel = f"{base}.yaml"
            n = 2
            while rel.lower() in used:
                rel = f"{base}-{n}.yaml"
                n += 1
            used.add(rel.lower())
            e.relpath = rel


def plan_conversion(scan: InputScan, opts: ConvertOptions) -> Plan:
    if opts.ids not in ("keep", "mint", "map"):
        raise ValueError(f"ids must be keep, mint or map; got {opts.ids!r}")
    if opts.ids == "map" and not opts.id_map:
        raise ValueError("ids map needs an id map")
    if opts.ids != "map" and opts.id_map:
        raise ValueError("an id map is only used with ids map")
    if opts.naming not in ("unprefixed", "factory-prefixed"):
        raise ValueError(f"naming must be unprefixed or factory-prefixed; got {opts.naming!r}")
    if opts.layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}; got {opts.layout!r}")
    if opts.target_min is not None and opts.target_min not in TARGET_VERSIONS:
        raise ValueError(f"target version must be one of {', '.join(TARGET_VERSIONS)}; got {opts.target_min!r}")
    return _Planner(scan, opts).run()
