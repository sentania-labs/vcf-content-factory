"""Plan an offline conversion: source objects -> factory YAML documents.

``plan_conversion`` takes an :class:`~.inputs.InputScan` and
:class:`ConvertOptions` and returns a :class:`Plan`: every object either
emitted (with its YAML text and target path relative to the output root),
dropped on request, or failed with the reason. Nothing is read from disk
and nothing is written here; the factory wrapper
(``vcfcf_extractor.importer``) writes the plan and verifies it.

Order of decisions, each reported:

1. **Duplicates.** The same id found in several files is one object when
   the comparator finds no difference between the copies
   (``compare.compare_copies``: the same flat form, renumbered ids aside);
   when they differ the object fails, naming every file, unless one
   ``prefer_sources`` fragment matches exactly one of the files that define
   it (matched against the path relative to the input root).
2. **Drops.** Objects whose id is in ``drop`` are not emitted; references
   to them stay raw ids (the caller references the product object in place).
   Then **kinds** (``kind_map``, ``kinds``): each source is re-pointed at
   every place a kind sits; a place it cannot re-point with certainty fails
   the object; after mapping, ``accounting.account_kinds`` classifies every
   place still holding a mapped adapter kind.
3. **Mapping** (per-type modules), then **accounting** of every source key
   (``accounting``). A ``MappingError`` fails the object; any other
   exception fails it as an internal error (object, file and exception type
   named), never the run.
4. **Names.** Whitespace the loaders strip is stripped, then ``rename``
   (keyed by type and old name or id), then ``naming``
   (``factory-prefixed`` adds ``[VCF CF] ``). Every change is a recorded
   rename. Two objects of one type with the same final name fail, naming
   both sources. Then ``describe`` replaces descriptions (matched as
   ``rename`` matches, on source ids and names).
5. **Ids.** ``keep`` carries source ids; ``mint`` gives every object a
   UUID version 5 from ``mint_namespace`` and its type and source id (a
   rerun gives the same ids); ``map`` applies ``id_map`` and keeps the
   rest. The stock-id guard runs on the result in the wrapper.
6. **References.** By name inside the set, by raw id outside it where the
   schema has a raw-id form; otherwise the referencing object fails. An
   object that references a failed one fails too (cascade, named). Then
   every string of every object has the old ids of re-identified objects in
   the set replaced (``sm_<uuid>`` super metric keys among them: the name
   form where the schema has one is set by step 6's references, the new id
   everywhere else), and any old id that still appears anywhere fails that
   object, naming the field.
7. **Target version.** With ``target_min``, an ``omit:`` entry whose proven
   floor is above it is not emitted (the key renders), and each such
   deviation is listed with the exact path it changes; a dashboard carrying
   a widget type that needs a newer product than the target is *converted,
   not deliverable to the stated target*. Without a target the source is
   reproduced and the same things are warned about.
"""
from __future__ import annotations

import copy
import re
import uuid
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

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
from . import accounting as _acct
from . import alerts as _alerts
from . import dashboards as _dash
from . import kinds as _kinds
from . import reports as _reports
from . import supermetrics as _sms
from . import views as _views
from .compare import compare_copies, source_leaves
from .flat import widget_path
from .inputs import CONTENT_TYPES, InputScan, SourceObject
from .kinds import KindMap
from .model import Loss, MappedObject, MappingError, Mark
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
_WIRE_WIDGET = {"AlertVolume": "IntSummaryAlertVolume"}
#: File names Windows reserves (any extension): a slug equal to one is suffixed.
WINDOWS_RESERVED = frozenset({"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)}
                             | {f"lpt{i}" for i in range(1, 10)})
#: The fixed root of every ``--ids mint`` namespace (uuid5 of a text under it).
MINT_ROOT = uuid.UUID("8f3c7a2e-5d14-5b9e-9c61-4f0a6e2d1b73")


def norm_id(type_: str, raw: str) -> str:
    """Comparison form of a source id: stripped of the XML prefix, lower case."""
    s = str(raw or "").strip()
    p = _ID_PREFIX.get(type_)
    if p and s.startswith(p):
        s = s[len(p):]
    return s.lower()


def norm_key(raw: str) -> Tuple[Optional[str], str]:
    """Comparison form of a ``--drop`` / ``--id-map`` key: ``(type, id)``.
    A key carrying an XML prefix (``SymptomDefinition-<id>``,
    ``AlertDefinition-<id>``, as ``id_map.tsv`` and the stock-id guard print
    them) names that type only; a bare key names no type (``None``) and
    matches any object whose :func:`norm_id` it equals, as before."""
    s = str(raw or "").strip()
    for t, p in _ID_PREFIX.items():
        if s.startswith(p):
            return t, s[len(p):].lower()
    return None, s.lower()


def key_hit(keys, type_: str, nid: str):
    """The ``norm_key`` form in ``keys`` that names an object of ``type_``
    with norm id ``nid`` (its own type first), or ``None``."""
    for k in ((type_, nid), (None, nid)):
        if k in keys:
            return k
    return None


def mint_namespace_uuid(text: str) -> uuid.UUID:
    """The UUID namespace a ``--mint-namespace`` text names."""
    return uuid.uuid5(MINT_ROOT, text)


def minted_id(namespace: uuid.UUID, type_: str, source_id: str) -> str:
    """The deterministic new id of one source object (UUID version 5)."""
    return str(uuid.uuid5(namespace, f"{type_}:{norm_id(type_, source_id)}"))


@dataclass
class ConvertOptions:
    ids: str = "keep"                          # keep | mint | map
    id_map: Dict[str, str] = field(default_factory=dict)   # old (norm) -> new
    drop: Dict[str, str] = field(default_factory=dict)     # id (norm) -> label
    naming: str = "unprefixed"                 # unprefixed | factory-prefixed
    #: (type, old name or id) -> new name
    rename: Dict[Tuple[str, str], str] = field(default_factory=dict)
    target_min: Optional[str] = None
    prefer_sources: List[str] = field(default_factory=list)
    layout: str = "third-party"
    #: the ``--ids mint`` namespace text (required with mint)
    mint_namespace: Optional[str] = None
    #: ``--map-kind``: re-point kinds (``kinds.KindMap``), or None
    kind_map: Optional[KindMap] = None
    #: ``--describe``: (type, name or id) -> new description
    describe: Dict[Tuple[str, str], str] = field(default_factory=dict)


#: Types whose factory YAML has a description that ships on the content
#: wire, and the flat source path of that description (a symptom's YAML
#: description is REST-only: the content-import XML has none).
DESCRIBED_TYPES = {"view": "ViewDef/Description#text", "dashboard": "dashboard.description",
                   "report": "ReportDef/Description#text", "supermetric": "supermetric.description",
                   "alert": "AlertDefinition@description", "recommendation": "Recommendation/Description#text"}


@dataclass
class Failure:
    type: str
    id: str
    name: str
    locations: List[str]
    reason: str
    gap: Optional[Dict[str, str]] = None
    #: failed (a mapping or reference failure) | internal (an unexpected
    #: exception in the converter) | unsupported (a type it does not convert)
    kind: str = "failed"


@dataclass
class Deviation:
    """A difference from the source the target version forces, at exact marks."""
    entry: str
    text: str
    marks: List[Mark] = field(default_factory=list)


@dataclass
class Emitted:
    type: str
    source: SourceObject
    source_id: str
    id: str
    name: str
    relpath: str = ""
    yaml_tree: Dict[str, object] = field(default_factory=dict)
    #: the mapper's tree with its reference placeholders (resolved afresh each round)
    mapped_tree: Dict[str, object] = field(default_factory=dict)
    text: str = ""
    losses: List[Loss] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    base_notes: List[str] = field(default_factory=list)
    deviations: List[Deviation] = field(default_factory=list)
    version_warnings: List[str] = field(default_factory=list)
    #: the name exactly as the source has it, and why the written name differs
    source_name: str = ""
    rename_reasons: List[str] = field(default_factory=list)
    #: widget types the stated target cannot import (W2): converted, not deliverable
    undeliverable: List[str] = field(default_factory=list)
    #: the source id is the one the renderer derives from the name (no id: in the YAML)
    derived: bool = False
    #: ``--map-kind``: kind references re-pointed in this object, and how
    kind_refs: int = 0
    kind_changes: List[str] = field(default_factory=list)
    #: ``--describe``: (source description, new description) when replaced
    described: Optional[Tuple[str, str]] = None
    #: free text carried from the source verbatim: (field, length)
    verbatim: List[Tuple[str, int]] = field(default_factory=list)


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
    #: the namespace text minted ids derive from (``--ids mint``)
    mint_namespace: Optional[str] = None
    #: ``--map-kind``: the map (rows and their use), or None
    kind_map: Optional[KindMap] = None
    #: ``--describe`` was given
    describing: bool = False
    #: full wire id -> full wire id for every symptom and alert whose id is
    #: not a UUID and changed (a derived id under ``--ids mint``, a map or
    #: ``--map-kind``): a reference that is the whole id follows it
    exact_id_rewrites: Dict[str, str] = field(default_factory=dict)

    def counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for t in CONTENT_TYPES:
            em = [e for e in self.emitted if e.type == t]
            out[t] = {
                "found": self.found.get(t, 0),
                "converted": len(em),
                "with_losses": sum(1 for e in em if e.losses),
                "undeliverable": sum(1 for e in em if e.undeliverable),
                "failed": sum(1 for f in self.failures if f.type == t and f.kind == "failed"),
                "internal_errors": sum(1 for f in self.failures if f.type == t and f.kind == "internal"),
                "dropped": sum(1 for d in self.dropped if d[0] == t),
            }
        return out

    @property
    def internal_errors(self) -> List[Failure]:
        return [f for f in self.failures if f.kind == "internal"]

    @property
    def unsupported(self) -> List[Failure]:
        return [f for f in self.failures if f.kind == "unsupported"]


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


def parse_rename_map(text: str, what: str) -> Dict[Tuple[str, str], str]:
    """``type<TAB>old name or id<TAB>new name`` rows (a header row whose
    first cell is ``type`` is skipped; ``#`` and blank lines too). The type
    is one of :data:`~.inputs.CONTENT_TYPES`, so a rename cannot cross
    types. Raises ValueError on a malformed row, an unknown type or a
    repeated key."""
    out: Dict[Tuple[str, str], str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = [c for c in line.rstrip("\r\n").split("\t")]
        if n == 1 and cells[0].strip().lower() == "type":
            continue
        if len(cells) < 3 or not cells[0].strip() or not cells[1] or not cells[2].strip():
            raise ValueError(f"{what}: line {n}: expected type<TAB>old name or id<TAB>new name, got {line!r}")
        t = cells[0].strip()
        if t not in CONTENT_TYPES:
            raise ValueError(f"{what}: line {n}: type {t!r} is not one of {', '.join(CONTENT_TYPES)}")
        k = (t, cells[1])
        if k in out:
            raise ValueError(f"{what}: line {n}: {t} {cells[1]!r} is listed twice")
        out[k] = cells[2].strip()
    return out


_DESC_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\"}


def unescape_description(cell: str, where: str) -> str:
    """A ``--describe`` cell: ``\\n`` a line break, ``\\t`` a tab, ``\\\\`` a
    backslash; any other backslash is an error (so a literal backslash is
    always written doubled)."""
    out, i = [], 0
    while i < len(cell):
        c = cell[i]
        if c == "\\":
            nxt = cell[i + 1] if i + 1 < len(cell) else ""
            if nxt not in _DESC_ESCAPES:
                raise ValueError(f"{where}: unknown escape \\{nxt} (use \\n, \\t or \\\\)")
            out.append(_DESC_ESCAPES[nxt])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_describe_map(text: str, what: str) -> Dict[Tuple[str, str], str]:
    """``type<TAB>name or id<TAB>new description`` rows (header row whose
    first cell is ``type``, ``#`` and blank lines skipped). The type is one
    whose description ships on the content wire (:data:`DESCRIBED_TYPES`).
    The description is unescaped (:func:`unescape_description`) and stripped
    (the loaders strip it); an empty one is an error. Raises ValueError on a
    malformed row, a type without a shipped description or a repeated key."""
    out: Dict[Tuple[str, str], str] = {}
    first = True
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.rstrip("\r\n").split("\t")
        # the header is the first row that is not blank or a comment
        if first and cells[0].strip().lower() == "type":
            first = False
            continue
        first = False
        if len(cells) != 3 or not cells[0].strip() or not cells[1] or not cells[2].strip():
            raise ValueError(f"{what}: line {n}: expected type<TAB>name or id<TAB>new description (a tab or a "
                             f"line break inside the description is written \\t or \\n), got {line[:120]!r}")
        t = cells[0].strip()
        if t == "symptom":
            raise ValueError(f"{what}: line {n}: a symptom has no description on the content-import wire (the "
                             f"symptom YAML's description is REST-only), so there is nothing to replace")
        if t not in DESCRIBED_TYPES:
            raise ValueError(f"{what}: line {n}: type {t!r} is not one of {', '.join(DESCRIBED_TYPES)}")
        k = (t, cells[1])
        if k in out:
            raise ValueError(f"{what}: line {n}: {t} {cells[1]!r} is listed twice")
        desc = unescape_description(cells[2], f"{what}: line {n}").strip()
        if not desc:
            raise ValueError(f"{what}: line {n}: the new description is empty")
        out[k] = desc
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


def _walk_strings(node, path: str = ""):
    """(path, key-or-None, string) for every string in a YAML tree, keys included."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else str(k)
            if isinstance(k, str):
                yield p, k, k
            yield from _walk_strings(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, None, node


def _kinds_gap(type_: str, problem: str) -> Dict[str, str]:
    from .model import toolset_gap
    return toolset_gap(
        f"{type_} YAML: --map-kind cannot re-point a kind with certainty",
        f"a source {type_}: {problem[:160]}",
        f"re-point the {type_} to the mapped kind without guessing",
        "map the kind with a row that makes the reference unambiguous, convert the object it references with "
        "this set, or re-point the object by hand after converting it without the map",
    )


def verbatim_text(e: "Emitted") -> List[Tuple[str, int]]:
    """The free-text fields of ``e`` that ship the source's prose (every
    one not replaced by ``--rename`` or ``--describe``; a name under
    ``--naming factory-prefixed`` still carries the source's name), with the
    length in characters of the SOURCE value: names, descriptions, widget
    titles and descriptions, TextDisplay HTML, recommendation text.
    Functional labels (view column display names, metric labels, tab names)
    are not listed. Empty fields are left out."""
    src = e.source.payload
    out: List[Tuple[str, int]] = []

    def add(label: str, v) -> None:
        if isinstance(v, str) and v:
            out.append((label, len(v)))

    if e.type != "recommendation" and "--rename" not in e.rename_reasons:
        add("name", e.source_name)
    if e.type in DESCRIBED_TYPES and e.described is None:
        if e.type in ("view", "report", "recommendation"):
            add("description", src.findtext("Description"))
        else:  # alert (an attribute), dashboard, super metric
            add("description", src.get("description"))
    if e.type == "dashboard":
        for i, w in enumerate(src.get("widgets") or []):
            if not isinstance(w, dict):
                continue
            c = w.get("config") if isinstance(w.get("config"), dict) else {}
            add(f"widget w{i} title", w.get("title"))
            add(f"widget w{i} description", c.get("description"))
            if w.get("type") == "TextDisplay":
                add(f"widget w{i} html", c.get("editorData"))
    return out


# ------------------------------------------------------------------- plan
class _Planner:
    def __init__(self, scan: InputScan, opts: ConvertOptions):
        self.scan = scan
        self.opts = opts
        self.plan = Plan()
        self.target = parse_ops_version(opts.target_min) if opts.target_min else None
        self.usage_errors: List[str] = []
        self.namespace = mint_namespace_uuid(opts.mint_namespace) if opts.mint_namespace else None
        self.plan.mint_namespace = opts.mint_namespace

    def fail(self, obj: SourceObject, reason: str, gap=None, kind: str = "failed") -> None:
        self.plan.failures.append(Failure(obj.type, obj.id, obj.name, list(obj.locations), reason, gap, kind))

    # 1. duplicates ----------------------------------------------------
    def dedupe(self) -> List[SourceObject]:
        groups: "OrderedDict[Tuple[str, str], List[SourceObject]]" = OrderedDict()
        for o in self.scan.objects:
            groups.setdefault((o.type, norm_id(o.type, o.id)), []).append(o)
        unique: List[SourceObject] = []
        used_prefs: Set[str] = set()
        for (t, nid), copies in groups.items():
            self.plan.found[t] += 1
            forms: List[List[SourceObject]] = []
            for c in copies:
                for f in forms:
                    if not compare_copies(f[0], c).differences:
                        f.append(c)
                        break
                else:
                    forms.append([c])
            locs = [c.location for c in copies]
            if len(forms) == 1:
                first = copies[0]
                first.locations = locs
                if len(copies) > 1:
                    self.plan.merged_duplicates.append((t, first.id, locs))
                unique.append(first)
                continue
            # Differing copies: a --prefer-source fragment must match exactly
            # one of the files that define this object (relative paths).
            hits: List[Tuple[str, SourceObject]] = []
            for pref in self.opts.prefer_sources:
                matched = [c for c in copies if pref in c.rel]
                if not matched:
                    continue
                used_prefs.add(pref)
                if len(matched) != 1:
                    self.usage_errors.append(
                        f"--prefer-source {pref!r} matches {len(matched)} of the files that define {t} {copies[0].id} "
                        f"({'; '.join(c.rel for c in matched)}); it must match exactly one")
                    continue
                hits.append((pref, matched[0]))
            if len({id(c) for _, c in hits}) > 1:
                self.usage_errors.append(
                    f"--prefer-source fragments pick different copies of {t} {copies[0].id}: "
                    + "; ".join(f"{p!r} -> {c.rel}" for p, c in hits))
                hits = []
            if hits:
                winner = hits[0][1]
                winner.locations = locs
                self.plan.resolved_duplicates.append((t, winner.id, winner.location, locs))
                unique.append(winner)
                continue
            first = copies[0]
            first.locations = locs
            by_form = "; ".join(f"copy {i + 1}: {', '.join(c.rel for c in cs)}" for i, cs in enumerate(forms))
            self.fail(first, f"the same id is defined differently in several files ({by_form}); say which copy "
                             f"wins with --prefer-source <fragment of exactly one file's path>")
        for pref in self.opts.prefer_sources:
            if pref not in used_prefs:
                self.usage_errors.append(f"--prefer-source {pref!r} matches none of the files that define an object "
                                         f"whose copies differ")
        return unique

    # 2. drops ---------------------------------------------------------
    def apply_drops(self, objs: List[SourceObject]) -> List[SourceObject]:
        drop = {norm_key(k): k for k in self.opts.drop}
        used = set()
        kept = []
        for o in objs:
            hit = key_hit(drop, o.type, norm_id(o.type, o.id))
            if hit is not None:
                used.add(hit)
                self.plan.dropped.append((o.type, o.id, o.name, list(o.locations)))
            else:
                kept.append(o)
        for k, raw in drop.items():
            if k not in used:
                shown = k[1] if k[0] is None else raw.strip()
                self.plan.warnings.append(f"drop list: {shown} names no object in the input")
        self.dropped_keys = {(t, norm_id(t, i)) for t, i, _, _ in self.plan.dropped}
        return kept

    # 2b. kind map ----------------------------------------------------
    def apply_kind_map(self, objs: List[SourceObject]) -> List[SourceObject]:
        """``--map-kind``: re-point each object's source (``kinds``), so the
        mapper reads, and verification compares against, the source with the
        map applied. The object's id and name stay the source's (``--drop``,
        ``--rename``, ``--describe`` and ``--id-map`` match them); a derived
        id the map re-points is recorded in ``kind_ids``."""
        km = self.opts.kind_map
        self.kind_ids: Dict[Tuple[str, str], str] = {}     # (type, norm source id) -> re-pointed id
        self.kind_unmap: Dict[Tuple[str, str], str] = {}   # (type, norm re-pointed id) -> source id
        self.kind_info: Dict[Tuple[str, str], _kinds.Remap] = {}
        self.kind_owner = {}
        if km is None:
            return objs
        mapping = {norm_key(k) for k in self.opts.id_map}
        keep = {(o.type, o.id) for o in objs
                if self.opts.ids != "mint" and key_hit(mapping, o.type, norm_id(o.type, o.id)) is None}
        ids, id_problems, id_internal = _kinds.make_ids(objs, km, keep,
                                                        {(t, i) for t, i, _, _ in self.plan.dropped})
        # re-pointed derived id -> (type, norm source id) of the object that
        # ships it: a reference to it fails when that object fails (run)
        self.kind_owner: Dict[str, Tuple[str, str]] = {
            new: (t, norm_id(t, old)) for (t, old), new in ids.table.items()}
        kept = []
        for o in objs:
            # An unexpected shape is that object's internal error, as in
            # map_all, never the run (the other objects convert as usual).
            err = id_internal.get((o.type, o.id))
            r = None
            if err is None:
                try:
                    r = _kinds.remap_object(o, km, ids)
                except Exception as exc:
                    err = f"{type(exc).__name__}: {exc}"
            if r is None:
                self.fail(o, f"internal error in the converter (--map-kind): {err} (source file {o.location})",
                          kind="internal")
                continue
            probs = list(r.problems)
            if (o.type, o.id) in id_problems:
                probs.insert(0, id_problems[(o.type, o.id)])
            if probs:
                self.fail(o, "kind map: " + "; ".join(probs), gap=_kinds_gap(o.type, probs[0]))
                continue
            key = (o.type, norm_id(o.type, o.id))
            self.kind_info[key] = r
            if r.count:
                o.payload = r.payload
                o.context = r.context
            if r.new_id:
                self.kind_ids[key] = r.new_id
                self.kind_unmap[(o.type, norm_id(o.type, r.new_id))] = o.id
            kept.append(o)
        return kept

    def kind_source_id(self, e_or_o) -> str:
        """The source id with the kind map applied (the source id when the
        map does not re-point it)."""
        t = e_or_o.type
        sid = e_or_o.source_id if isinstance(e_or_o, Emitted) else e_or_o.id
        return self.kind_ids.get((t, norm_id(t, sid)), sid)

    # 3. mapping -------------------------------------------------------
    def map_all(self, objs: List[SourceObject]) -> List[Tuple[SourceObject, MappedObject]]:
        rec_kind: Dict[str, str] = {}
        for o in objs:
            if o.type == "alert":
                rr = o.payload.find("State/Recommendations")
                for r in (rr if rr is not None else []):
                    if r.get("ref"):
                        # keyed by the recommendation's source id: under
                        # --map-kind the ref carries the re-pointed key, and
                        # the alert's (re-pointed) kind is the one written
                        ref = self.kind_unmap.get(("recommendation", norm_id("recommendation", r.get("ref"))),
                                                  r.get("ref"))
                        rec_kind.setdefault(ref, o.payload.get("adapterKind") or "")
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
                if self.opts.kind_map is not None:
                    # every place of the re-pointed source that still names a
                    # mapped adapter kind is classified, or the object stops
                    _acct.account_kinds(o.type, source_leaves(o), self.opts.kind_map)
            except MappingError as exc:
                self.fail(o, str(exc), exc.gap)
                continue
            except Exception as exc:  # an unexpected shape: one object, never the run
                self.fail(o, f"internal error in the converter: {type(exc).__name__}: {exc} (source file "
                             f"{o.location})", kind="internal")
                continue
            out.append((o, m))
        return out

    # 4. names -----------------------------------------------------------
    def final_name(self, o: SourceObject, src_name: str) -> Tuple[str, List[str]]:
        reasons: List[str] = []
        name = src_name.strip()  # every factory loader strips a name
        if name != src_name:
            reasons.append("surrounding whitespace the loader strips")
        rename = self.opts.rename
        for key in ((o.type, o.id), (o.type, norm_id(o.type, o.id)), (o.type, src_name), (o.type, name)):
            if key in rename:
                self.rename_used.add(key)
                name = rename[key].strip()
                reasons.append("--rename")
                break
        if self.opts.naming == "factory-prefixed":
            before = name
            if has_legacy_prefix(name):
                name = FACTORY_PREFIX + strip_factory_prefix(name)
            elif not has_factory_prefix(name):
                name = FACTORY_PREFIX + name
            if name != before:
                reasons.append("--naming factory-prefixed")
        return name, reasons

    # 4b. descriptions ----------------------------------------------------
    def apply_describe(self, entries: List["Emitted"]) -> None:
        """``--describe``: a row names one object by type and source id or
        source name (as ``--rename`` resolves it, before renaming); its
        description is replaced in the YAML. A row naming several objects,
        or an object two rows name, is a usage error; a row naming none is a
        warning (as for ``--rename``). A recorded loss on the replaced
        description (its surrounding whitespace) no longer applies."""
        rows = self.opts.describe
        if not rows:
            return
        self.plan.describing = True
        hits: Dict[Tuple[str, str], List[Emitted]] = defaultdict(list)
        for e in entries:
            o = e.source
            keys = []
            nid = norm_id(o.type, o.id)
            for key in rows:
                # an id in any letter case (and with or without its XML
                # prefix), or the source name exactly or stripped
                if key[0] == o.type and (norm_id(o.type, key[1]) == nid or key[1] in (
                        e.source_name, e.source_name.strip())) and key not in keys:
                    keys.append(key)
            if len(keys) > 1:
                self.usage_errors.append(
                    f"--describe: {o.type} {o.id} ({e.source_name!r}) is named by {len(keys)} rows "
                    f"({'; '.join(repr(k[1]) for k in keys)}); keep one")
                continue
            if keys:
                hits[keys[0]].append(e)
        for key, new in rows.items():
            es = hits.get(key, [])
            if not es:
                self.plan.warnings.append(f"describe file: {key[0]} {key[1]!r} names no object in the input")
                continue
            if len(es) > 1:
                self.usage_errors.append(
                    f"--describe: {key[0]} {key[1]!r} names {len(es)} objects "
                    f"({'; '.join(f'{x.source_id} ({x.source_name!r})' for x in es)}); key the row by id")
                continue
            e = es[0]
            try:
                tree = e.mapped_tree
                old = str(tree.get("description", "") or "")
                tree["description"] = new
                e.described = (old, new)
                path = DESCRIBED_TYPES[e.type]
                for x in list(e.losses):
                    x.marks = [m for m in x.marks if m.path != path]
                    if not x.marks:
                        e.losses.remove(x)
            except Exception as exc:  # that object's internal error, never the run
                self.fail(e.source, f"internal error in the converter (--describe): {type(exc).__name__}: {exc} "
                                    f"(source file {e.source.location})", kind="internal")

    # 5. ids --------------------------------------------------------------
    def final_id(self, o: SourceObject) -> str:
        nid = norm_id(o.type, o.id)
        # --ids keep carries the source id, with a derived id's kind re-pointed
        # by --map-kind (the renderer derives it from the new kind)
        src = self.kind_source_id(o)
        raw = src[len(_ID_PREFIX[o.type]):] if o.type in _ID_PREFIX and src.startswith(_ID_PREFIX[o.type]) else src
        mapping = {norm_key(k): v for k, v in self.opts.id_map.items()}
        if self.opts.ids == "mint":
            new = minted_id(self.namespace, o.type, o.id)
            return f"Recommendation-{new}" if o.type == "recommendation" else new
        hit = key_hit(mapping, o.type, nid)
        if hit is not None:
            self.map_used.add(hit)
            return norm_id(o.type, mapping[hit]) if o.type != "recommendation" else mapping[hit]
        if o.type in ("view", "dashboard", "report", "supermetric"):
            return raw.lower()
        return raw

    def derived_id(self, e: "Emitted") -> bool:
        """True when ``e`` keeps its source id and that id is the one the
        alert renderer derives (``<Type>-<adapter>-<slug of name>``)."""
        if e.type not in ("symptom", "alert", "recommendation"):
            return False
        src = self.kind_source_id(e)
        raw = src
        if e.type in _ID_PREFIX and raw.startswith(_ID_PREFIX[e.type]):
            raw = raw[len(_ID_PREFIX[e.type]):]
        if e.id != raw:
            return False
        from ..alerts.render import _alert_id, _rec_key, _symptom_id
        ak = str(e.yaml_tree.get("adapter_kind") or "")
        derived = {"symptom": lambda: _symptom_id(ak, e.name), "alert": lambda: _alert_id(ak, e.name),
                   "recommendation": lambda: _rec_key(ak, e.name)}[e.type]()
        return derived == src

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
        for u in self.scan.unsupported:
            p.failures.append(Failure(u.type, u.id, u.name, [u.location],
                                      f"not converted: the importer does not convert {u.type}s (unsupported type)",
                                      kind="unsupported"))
        objs = self.apply_kind_map(self.apply_drops(self.dedupe()))
        mapped = self.map_all(objs)
        self.rename_used: Set[Tuple[str, str]] = set()
        self.map_used: Set[str] = set()
        entries: List[Emitted] = []
        for o, m in mapped:
            e = Emitted(o.type, o, o.id, "", "", losses=list(m.losses), base_notes=list(m.notes))
            e.yaml_tree = m.yaml
            e.mapped_tree = m.yaml
            e.source_name = m.source_name if m.source_name is not None else str(m.yaml.get("name", ""))
            e.name, e.rename_reasons = self.final_name(o, e.source_name)
            if o.type == "recommendation" and e.source_name != o.name:
                # a recommendation's name is its key, re-pointed by --map-kind
                e.source_name = o.name
                e.rename_reasons.insert(0, "--map-kind (the key derives from the adapter kind)")
            e.id = self.final_id(o)
            info = self.kind_info.get((o.type, norm_id(o.type, o.id)))
            if info is not None and info.count:
                e.kind_refs = info.count
                e.kind_changes = _kinds.change_lines(info)
            entries.append(e)
        for k in self.opts.rename:
            if k not in self.rename_used:
                p.warnings.append(f"rename file: {k[0]} {k[1]!r} names no object in the input")
        for k in self.opts.id_map:
            if norm_key(k) not in self.map_used:
                p.warnings.append(f"id map: {k} names no object in the input")
        if self.opts.kind_map is not None:
            p.kind_map = self.opts.kind_map
            for r in self.opts.kind_map.unused():
                p.warnings.append(f"kind map: {r.where}: {r.label()} matches no kind-bearing place of any object "
                                  f"in the input (nothing was re-pointed by it)")
        self.apply_describe(entries)
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

        # name collisions (on the normalized name, every type) and id problems
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
                srcs = "; ".join(f"{x.source_id} ({x.source_name!r}) in {', '.join(x.source.locations)}" for x in es)
                for x in es:
                    mark(x, f"{len(es)} {t}s share the name {n!r} once the loader strips whitespace ({srcs}); "
                            f"by-name references cannot tell them apart: give one a new name with --rename "
                            f"(keyed by type and id)")
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
                self.usage_errors.append(
                    f"the content/ layout holds factory content, whose names carry the "
                    f"{FACTORY_PREFIX.strip()} prefix; {len(bad)} converted name(s) do not "
                    f"(for example {bad[0].name!r}). Use --naming factory-prefixed, or a "
                    f"third-party or pak layout")

        # references, rewrites and the old-id scan, to a fixed point (an
        # object referencing a failed one fails; so does one an old id
        # survives in)
        index: Dict[Tuple[str, str], Emitted] = {(e.type, norm_id(e.type, e.source_id)): e for e in entries}
        while True:
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
            p.id_rewrites, p.names = {}, {}
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
            p.exact_id_rewrites = {}
            for e in ok:
                if e.type in _ID_PREFIX and not _UUID_ANY.match(norm_id(e.type, e.source_id)):
                    new_full = _ID_PREFIX[e.type] + e.id
                    if new_full != e.source_id:
                        p.exact_id_rewrites[e.source_id] = new_full
                        k = self.kind_source_id(e)
                        if k != e.source_id and k != new_full:
                            p.exact_id_rewrites[k] = new_full
            new_failures = False
            final_ids = {e.id.lower() for e in ok}
            for e in ok:
                hit = self.failed_sm_reference(e, failed) or self.failed_kind_reference(e, failed)
                if hit:
                    mark(e, hit)
                    new_failures = True
                    continue
                self.rewrite_ids(e)
                hit = self.surviving_old_id(e, final_ids)
                if hit:
                    mark(e, hit)
                    new_failures = True
            # The ids that ship, after every rewrite: still one object per id
            # and type, and each definition carries the id the plan and the
            # id map report (a rewrite never touches a final definition id).
            shipped: Dict[Tuple[str, str], List[Emitted]] = defaultdict(list)
            for e in ok:
                if (e.type, norm_id(e.type, e.source_id)) in failed:
                    continue
                if "id" in e.yaml_tree and e.yaml_tree["id"] != e.id:
                    mark(e, f"internal: the written id {e.yaml_tree['id']} is not the planned id {e.id}")
                    new_failures = True
                    continue
                shipped[(e.type, str(e.yaml_tree.get("id", e.id)).lower())].append(e)
            for (t, i), es in shipped.items():
                if len(es) > 1:
                    for x in es:
                        mark(x, f"{len(es)} {t}s would ship under the id {i} "
                                f"({'; '.join(f'{y.source_id} ({y.name!r})' for y in es)}); fix the id map")
                    new_failures = True
            if not new_failures:
                break
        listed = []
        for e in ok:
            self.gate_versions(e)
            try:
                e.verbatim = verbatim_text(e)
            except Exception as exc:  # that object's internal error, never the run
                self.fail(e.source, f"internal error in the converter (verbatim text listing): "
                                    f"{type(exc).__name__}: {exc} (source file {e.source.location})",
                          kind="internal")
                continue
            listed.append(e)
        ok = listed
        self.layout_paths(ok)
        for e in ok:
            rel = ", ".join(e.source.locations)
            e.text = dump_yaml(e.yaml_tree, header=f"# Converted offline by vcfcf_extractor import-local from: {rel}\n")
            p.id_table.append((e.type, e.source_id, e.id, e.name))
        p.emitted = ok
        if self.usage_errors:
            p.usage_error = "; ".join(self.usage_errors)
        return p

    # 6. references ------------------------------------------------------
    def resolve(self, e: Emitted, index, failed) -> dict:
        e.notes = list(e.base_notes)

        def target(t: str, rid: str):
            # a reference the kind map re-pointed names the object by its
            # re-pointed derived id; the index is keyed by source ids
            rid = self.kind_unmap.get((t, norm_id(t, rid)), rid)
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

        tree = copy.deepcopy(e.mapped_tree)
        return res(tree)[1]

    def failed_sm_reference(self, e: Emitted, failed) -> Optional[str]:
        """A ``sm_<uuid>`` key in ``e`` (a symptom condition, a view filter, a
        widget metric, HTML) naming a super metric that did not convert: ``e``
        fails with it, as a by-name reference does (``resolve``)."""
        for path, key, s in _walk_strings(e.yaml_tree):
            for m in _SM_TOKEN.finditer(s):
                k = ("supermetric", m.group(1).lower())
                if k in failed and not (e.type == "supermetric" and norm_id(e.type, e.source_id) == k[1]):
                    return f"references super metric {m.group(1)}, which did not convert (see its own failure)"
        return None

    def failed_kind_reference(self, e: Emitted, failed) -> Optional[str]:
        """A whole-string reference in ``e`` (a dashboard AlertList entry) to
        a derived id ``--map-kind`` re-pointed, whose object did not convert:
        nothing ships that id, so ``e`` fails with it (the reference would
        otherwise verify against the same re-pointed expectation)."""
        if not self.kind_owner or e.type != "dashboard":
            return None
        for path, key, s in _walk_strings(e.yaml_tree):
            owner = self.kind_owner.get(s)
            if owner is not None and owner in failed:
                return (f"field {path} references {owner[0]} {s} (its derived id re-pointed by --map-kind), which "
                        f"did not convert (see its own failure)")
        return None

    # id rewrites in strings (every type) ---------------------------------
    def rewrite_ids(self, e: Emitted) -> None:
        """Every string of every object: an old id (any letter case) of a
        re-identified object in the set becomes its new id, in one
        simultaneous substitution over the source tree (a substituted id is
        never substituted again, so a chained or swapped --id-map holds).
        The object's own definition id is already final and is not
        touched. A super metric
        key ``sm_<uuid>`` / ``Super Metric|sm_<uuid>`` takes the name form
        where the schema has one (view columns, formulas: set as references
        in ``resolve``) and the new id here everywhere else (symptom
        conditions, view filters, widget metric entries, Pareto columns,
        Heatmap metrics, HTML)."""
        rw = {k: v for k, v in self.plan.id_rewrites.items() if _UUID_ANY.match(k)}
        exact = self.plan.exact_id_rewrites
        missing_sm: Set[str] = set()

        def sub_str(s: str) -> str:
            if s in exact:
                # a whole-string reference to a symptom or alert whose
                # non-UUID id changed (an AlertList alert definition id)
                return exact[s]
            for m in _SM_TOKEN.finditer(s):
                nid = m.group(1).lower()
                if ("supermetric", nid) not in self.plan.names and ("supermetric", nid) not in self.dropped_keys:
                    missing_sm.add(m.group(1))
            if not rw:
                return s
            return _UUID_IN.sub(lambda m: rw.get(m.group(0).lower(), m.group(0)), s)

        def walk(node, top=False):
            if isinstance(node, dict):
                for k, v in list(node.items()):
                    if top and k == "id":
                        continue  # the definition's final id (set in run)
                    node[k] = walk(v)
                return node
            if isinstance(node, list):
                return [walk(v) for v in node]
            if isinstance(node, str):
                return sub_str(node)
            return node
        walk(e.yaml_tree, top=True)
        if e.type != "supermetric":  # a formula's own note is set in resolve
            for sid in sorted(missing_sm):
                e.notes.append(f"references super metric {sid}, which is not in the input (kept as its wire key; "
                               f"it must exist on the target instance)")

    def surviving_old_id(self, e: Emitted, final_ids: Set[str]) -> Optional[str]:
        """The field of ``e`` that still names the OLD id of a re-identified
        object in the set (any type, any letter case), or ``None``. A
        dropped object's id is not re-identified, so it may remain."""
        old = {k for k in self.plan.id_rewrites if _UUID_ANY.match(k)} - final_ids
        if not old:
            return None
        for path, key, s in _walk_strings(e.yaml_tree):
            for m in _UUID_IN.finditer(s):
                if m.group(0).lower() in old:
                    where = f"the key {key!r}" if key is not None else f"field {path}"
                    return (f"{where} still names {m.group(0)}, the old id of a re-identified object in the set "
                            f"(its new id is {self.plan.id_rewrites[m.group(0).lower()]})")
        return None

    # 7. target versions -------------------------------------------------
    def _gate(self, e: Emitted, entry: str, floor, wire_keys, where: str, marks: List[Mark]) -> bool:
        """Return True to keep the omit entry; on a deviation record it."""
        if floor is not None and parse_ops_version(floor) <= (self.target or OLDEST_OMIT_EVIDENCE):
            return True
        floor_s = _version_floor_text(floor)
        if self.target is not None:
            text = (f"{where}: omit: {entry} not emitted: its floor is {floor_s}, above the target "
                    f"{format_ops_version(self.target)}; the render carries {'/'.join(wire_keys)} where the "
                    f"source leaves it out (set aside only at {', '.join(m.path for m in marks)})")
            if entry == "folder_in_name":
                text += " (the dashboard name then carries its folder)"
            e.deviations.append(Deviation(entry, text, list(marks)))
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
            dmarks = {"temporary": [Mark("dashboard.temporary", "extra")],
                      "name_path": [Mark("dashboard.namePath", "extra")],
                      "folder_in_name": [Mark("dashboard.name", "value")],
                      "widget_interactions": [Mark("dashboard.widgetInteractions", "extra", empty_only=True)]}
            keep = [x for x in om if self._gate(e, x, DASHBOARD_OMIT_MIN_OPS_VERSION.get(x), wire.get(x, (x,)),
                                                f"dashboard {e.name!r}", dmarks.get(x, []))]
            if keep:
                y["omit"] = keep
            elif "omit" in y:
                del y["omit"]
            for wi, w in enumerate(y.get("widgets") or []):
                wt = w.get("type")
                base = widget_path(wi, _WIRE_WIDGET.get(wt, wt))
                floor = WIDGET_TYPE_MIN_OPS_VERSION.get(wt)
                if floor is not None and (self.target is None or self.target < parse_ops_version(floor)):
                    if self.target is not None:
                        e.undeliverable.append(
                            f"widget {w.get('id')} ({wt}) needs VCF Operations {format_ops_version(floor)} or later; "
                            f"the stated target {format_ops_version(self.target)} aborts the whole dashboard on "
                            f"import (issue #199)"
                            + ("; to deliver it without its Section rows, convert it at a target that "
                               "imports Section (9.1.1 or later) or without --target-min, then add "
                               "section_fallback: omit to the written dashboard YAML (the importer never "
                               "adds it)" if wt == "Section" else ""))
                    else:
                        e.version_warnings.append(
                            f"dashboard {e.name!r} widget {w.get('id')} ({wt}): needs VCF Operations "
                            f"{format_ops_version(floor)} or later; on any build below it (no --target-min given) "
                            f"the importer aborts the whole dashboard (issue #199). Not converted away; a Tier 2 "
                            f"pak build fails on it"
                            + ("; to accept the dashboard without its Section rows there, add "
                               "section_fallback: omit to the written YAML (never added here)"
                               if wt == "Section" else ""))
                wo = w.get("omit") or []
                if wo:
                    kept = []
                    for x in wo:
                        path = WIDGET_OMIT_KEYS.get(wt, {}).get(x, (x,))
                        if self._gate(e, x, WIDGET_OMIT_MIN_OPS_VERSION.get((wt, x)), (path[-1],),
                                      f"dashboard {e.name!r} widget {w.get('id')} ({wt})",
                                      [Mark(f"{base}.config." + ".".join(path), "extra", subtree=True)]):
                            kept.append(x)
                    if kept:
                        w["omit"] = kept
                    else:
                        del w["omit"]
                mwire = {"label": ("label",), "max_value": ("maxValue",),
                         "handle_old_coloring": ("handleOldColoring",), "unit": ("unit", "metricUnitId"),
                         "link": ("link",)}
                arr = "resourceMetrics" if w.get("metric_mode") == "resource" else "resourceKindMetrics"
                for mi, m in enumerate(w.get("metrics") or []):
                    mo = m.get("omit") or []
                    if mo:
                        kept = [x for x in mo if self._gate(
                            e, x, METRIC_OMIT_MIN_OPS_VERSION.get(x), mwire.get(x, (x,)),
                            f"dashboard {e.name!r} widget {w.get('id')} metric {mi}",
                            [Mark(f"{base}.config.metric.{arr}[{mi}].{k}", "extra") for k in mwire.get(x, (x,))])]
                        if kept:
                            m["omit"] = kept
                        else:
                            del m["omit"]
                twire = {"tag_filter": (("tagFilter",), True), "custom_filter": (("customFilter",), True),
                         "color_min_value": (("color.minValue",), False),
                         "group_by_kind_keys": (("groupBy.adapterKind", "groupBy.resourceKind"), False)}
                for ti, tab in enumerate(w.get("configs") or []):
                    to = tab.get("omit") or []
                    if to:
                        kept = []
                        for x in to:
                            keys, sub = twire.get(x, ((x,), True))
                            if self._gate(e, x, HEATMAP_TAB_OMIT_MIN_OPS_VERSION.get(x), keys,
                                          f"dashboard {e.name!r} widget {w.get('id')} tab {ti}",
                                          [Mark(f"{base}.config.configs[{ti}].{k}", "extra", subtree=sub)
                                           for k in keys]):
                                kept.append(x)
                        if kept:
                            tab["omit"] = kept
                        else:
                            del tab["omit"]
        elif e.type == "report":
            for si, s in enumerate(y.get("sections") or []):
                so = s.get("omit") or []
                if so:
                    kept = [x for x in so if self._gate(
                        e, x, SECTION_OMIT_MIN_OPS_VERSION.get(x), ("ContentFormatting",),
                        f"report {e.name!r} section {si}",
                        [Mark(f"ReportDef/Sections/Section[{si}]/ContentFormatting", "extra", subtree=True)])]
                    if kept:
                        s["omit"] = kept
                    else:
                        del s["omit"]
                        s["colorize"] = True
        elif e.type == "symptom":
            so = y.get("omit") or []
            if so:
                wire = {"wait_cycles": "SymptomDefinition@waitCycle", "cancel_cycles": "SymptomDefinition@cancelCycle",
                        "instanced": "SymptomDefinition/State/Condition[0]@instanced"}
                kept = [x for x in so if self._gate(e, x, SYMPTOM_OMIT_MIN_OPS_VERSION.get(x),
                                                    (wire.get(x, x).rsplit("@", 1)[-1],), f"symptom {e.name!r}",
                                                    [Mark(wire.get(x, x), "extra")])]
                if kept:
                    y["omit"] = kept
                else:
                    del y["omit"]

    # layout ---------------------------------------------------------------
    def layout_paths(self, ok: List[Emitted]) -> None:
        used: Set[str] = set()
        for e in ok:
            s = slug(e.name)
            if s in WINDOWS_RESERVED:
                e.base_notes.append(f"file name: the name slugs to {s!r}, a name Windows reserves; written as "
                                    f"{s}-{e.type}.yaml")
                e.notes.append(e.base_notes[-1])
                s = f"{s}-{e.type}"
            base = f"{TYPE_DIRS[e.type]}/{s}"
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
    if opts.ids == "mint" and not opts.mint_namespace:
        raise ValueError("ids mint needs a mint namespace (the minted ids derive from it, so a rerun repeats them)")
    if opts.naming not in ("unprefixed", "factory-prefixed"):
        raise ValueError(f"naming must be unprefixed or factory-prefixed; got {opts.naming!r}")
    if opts.layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}; got {opts.layout!r}")
    if opts.target_min is not None and opts.target_min not in TARGET_VERSIONS:
        raise ValueError(f"target version must be one of {', '.join(TARGET_VERSIONS)}; got {opts.target_min!r}")
    return _Planner(scan, opts).run()
