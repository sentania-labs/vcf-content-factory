"""Re-point content from one adapter kind (and resource kind) to another
(``import-local --map-kind``).

A kind map is a list of :class:`KindRow` rows ``old adapter kind, old
resource kind or *, new adapter kind, new resource kind or *``. ``*`` in the
old resource kind maps every resource kind of that adapter kind and keeps its
key (the new resource kind is then ``*`` too); a row naming a resource kind
wins over a ``*`` row of the same adapter kind. Kinds not listed are left as
they are.

The map is applied to each **source** object before it is mapped
(:func:`remap_object`), at every place this module knows holds a kind, and
only there (never a text replace: the same string can be a display name, a
description, a metric key segment or a literal):

- views: ``SubjectType``, ``SubjectsGroupBy`` and ``BlacklistResourceKind``
  ``adapterKind`` / ``resourceKind``, a column's (or additional column's)
  ``adapterKind`` / ``resourceKind`` Properties;
- report templates: ``SubjectType`` ``adapterKind`` / ``resourceKind``;
- symptoms and alerts: ``adapterKind`` / ``resourceKind``, and an id in the
  factory's derived form (``SymptomDefinition-<kind>-<slug>``,
  ``AlertDefinition-<kind>-<slug>``, ``Recommendation-df-<kind>-<slug>``)
  together with every reference to it (alert symptom sets and
  recommendations, dashboard AlertList ``alertDefinitions``);
- super metrics: ``resourceKinds`` and the formula's resource entries
  (``adaptertype=`` / ``objecttype=``, parsed, :func:`remap_formula`);
- dashboards: the ``entries`` table (which every ``resourceKind:id:<n>_::_``
  and ``resource:id:<n>_::_`` reference resolves through: metric entries, tag
  filters, Heatmap tabs and groups, Pareto and HealthChart kinds, pins), the
  ``0020<nn><adapter><kind>`` ids (a View pin, a resource-mode Scoreboard
  entry, a Heatmap custom filter), a Heatmap ``groupBy`` (``adapterKind``,
  ``resourceKind``, ``parentId``, ``id``).

A place the map cannot rewrite with certainty stops the object (a problem,
reported as a TOOLSET GAP by the planner): a reference that names a mapped
adapter kind without a resource kind (a formula entry by ``resourcename``,
``objecttype=*``) when the adapter kind is mapped only for some of its
resource kinds or to more than one new adapter kind; a derived id of an
object outside the input; a mapping that makes two distinct kinds of one
object the same kind; a Summary page bound to a mapped kind; and, found by
the accounting, a View traversal spec id naming a mapped adapter kind
(``<spec>-<adapter>-<root kind>``: the target adapter's specs are not
known), a compared value equal to a mapped adapter kind. After mapping,
``accounting.account_kinds`` classifies every place of the source's flat form
that still holds a mapped adapter kind, so a place this module does not know
is a GAP, not a pass.

Nothing here reads a file or writes one.
"""
from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

STAR = "*"
_HEADER_CELLS = ("old_adapter_kind", "adapter_kind", "old_kind", "old")
#: Characters a new kind key may not carry: they delimit the forms a kind is
#: written in (``RK:<adapter>/<kind>``, formula entries, ``<adapter>:<kind>``).
_BAD_KIND_CHARS = set('/|,={}":') | {chr(c) for c in range(32)} | {"\x7f"}
_SYMPTOM_PREFIX = "SymptomDefinition-"
_ALERT_PREFIX = "AlertDefinition-"
_REC_PREFIX = "Recommendation-df-"
_SUMMARY_FOLDERS = {"VMFolder", "HostFolder", "DatastoreFolder", "NetworkFolder",
                    "VmwareDistributedVirtualSwitch", "DistributedVirtualPortgroup"}


@dataclass(frozen=True)
class KindRow:
    old_ak: str
    old_rk: str          # a resource kind key or STAR
    new_ak: str
    new_rk: str          # a resource kind key or STAR (keep the key)
    where: str = ""      # file:line

    def label(self) -> str:
        return f"{self.old_ak}:{self.old_rk} -> {self.new_ak}:{self.new_rk}"


def parse_kind_map(text: str, what: str) -> List[KindRow]:
    """``old adapter kind<TAB>old resource kind or *<TAB>new adapter kind<TAB>new
    resource kind or *`` rows. ``#`` and blank lines are skipped; the first
    other row is a header when its first cell is a column label
    (``old_adapter_kind``, ``adapter_kind``, ``old_kind``, ``old``). Raises
    ``ValueError`` on a malformed row (exactly four non-empty cells, so a
    header anywhere else is an error), a ``*`` old resource kind with a
    named new one, or a new kind key carrying a delimiter character."""
    rows: List[KindRow] = []
    first = True
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.rstrip("\r\n").split("\t")
        if first and cells[0].strip().lower() in _HEADER_CELLS:
            first = False
            continue
        first = False
        if cells[0].strip().lower() in _HEADER_CELLS:
            raise ValueError(f"{what}: line {n}: a header row is only read as the first row (after comments and "
                             f"blank lines), got {line!r}")
        if len(cells) != 4 or any(not c.strip() for c in cells):
            raise ValueError(f"{what}: line {n}: expected old adapter kind<TAB>old resource kind or *<TAB>"
                             f"new adapter kind<TAB>new resource kind or *, got {line!r}")
        oak, ork, nak, nrk = (c.strip() for c in cells)
        if oak == STAR or nak == STAR:
            raise ValueError(f"{what}: line {n}: an adapter kind cannot be *")
        if ork == STAR and nrk != STAR:
            raise ValueError(f"{what}: line {n}: old resource kind * maps every resource kind of {oak} and keeps "
                             f"its key; the new resource kind must be * too (got {nrk!r})")
        for label, key in (("new adapter kind", nak), ("new resource kind", nrk)):
            bad = sorted(set(key) & _BAD_KIND_CHARS) if key != STAR else []
            if bad:
                raise ValueError(f"{what}: line {n}: {label} {key!r} carries {''.join(bad)!r}, which delimits the "
                                 f"forms a kind is written in")
        if not nak.isascii() or len(nak) > 99:
            raise ValueError(f"{what}: line {n}: new adapter kind {nak!r} must be ASCII and at most 99 characters "
                             f"(the resourceKindId encoding, dashboards.render.adapter_kind_prefix)")
        rows.append(KindRow(oak, ork, nak, nrk, f"{what}:{n}"))
    return rows


class KindMap:
    """The validated rows, with lookups and a use count per row."""

    def __init__(self, rows: List[KindRow]):
        self.rows: List[KindRow] = []
        self._by: Dict[Tuple[str, str], KindRow] = {}
        problems: List[str] = []
        for r in rows:
            key = (r.old_ak, r.old_rk)
            if key in self._by:
                o = self._by[key]
                how = "the same way" if (o.new_ak, o.new_rk) == (r.new_ak, r.new_rk) else "differently"
                problems.append(f"{r.where}: {r.old_ak}:{r.old_rk} is already mapped {how} by {o.where} "
                                f"({o.label()})")
                continue
            if r.new_ak == r.old_ak and (r.new_rk == r.old_rk or r.new_rk == STAR):
                problems.append(f"{r.where}: {r.label()} maps a kind to itself")
                continue
            self._by[key] = r
            self.rows.append(r)
        for r in self.rows:
            # Chains and swaps (a new kind that another row maps again) are
            # refused: the map is applied once, and a re-pointed kind must
            # never be one the map re-points.
            if r.old_rk == STAR:
                hit = next((o for o in self.rows if o.old_ak == r.new_ak), None)
            else:
                hit = self._row(r.new_ak, r.new_rk if r.new_rk != STAR else r.old_rk)
            if hit is not None:
                problems.append(f"{r.where}: {r.label()} lands on a kind that {hit.where} ({hit.label()}) maps "
                                f"again; chains and swaps are not supported, map each old kind straight to its "
                                f"final kind")
        if problems:
            raise ValueError("--map-kind: " + "; ".join(problems))
        self.used: Counter = Counter()
        self.aks: Set[str] = {r.old_ak for r in self.rows}

    def _row(self, ak, rk) -> Optional[KindRow]:
        if ak is None:
            return None
        return self._by.get((ak, rk)) if rk is not None and (ak, rk) in self._by else self._by.get((ak, STAR))

    def lookup(self, ak, rk, count: bool = True) -> Optional[Tuple[str, Optional[str]]]:
        """``(new adapter kind, new resource kind)`` for a source pair, or
        ``None`` when no row maps it. A row naming the resource kind wins
        over the ``*`` row."""
        r = self._row(ak, rk)
        if r is None:
            return None
        if count:
            self.used[(r.old_ak, r.old_rk)] += 1
        return r.new_ak, (rk if r.new_rk == STAR else r.new_rk)

    def adapter_only(self, ak, count: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """``(new adapter kind, problem)`` for a reference that names the
        adapter kind alone (every resource kind of it): ``(None, None)`` when
        the adapter kind is not mapped; a problem when its rows do not move
        every resource kind to one new adapter kind (no ``*`` row, or a
        resource kind row to another adapter kind)."""
        if ak not in self.aks:
            return None, None
        rows = [r for r in self.rows if r.old_ak == ak]
        star = next((r for r in rows if r.old_rk == STAR), None)
        if star is None:
            return None, (f"adapter kind {ak} is mapped only for some resource kinds "
                          f"({', '.join(r.label() for r in rows)}), so a reference naming the adapter kind alone "
                          f"cannot be re-pointed with certainty; add a {ak}<TAB>*<TAB>... row")
        other = [r for r in rows if r.new_ak != star.new_ak]
        if other:
            return None, (f"adapter kind {ak} maps to more than one adapter kind ({star.label()}; "
                          f"{', '.join(r.label() for r in other)}), so a reference naming the adapter kind alone "
                          f"cannot be re-pointed with certainty")
        if count:
            self.used[(star.old_ak, star.old_rk)] += 1
        return star.new_ak, None

    def unused(self) -> List[KindRow]:
        return [r for r in self.rows if not self.used[(r.old_ak, r.old_rk)]]

    def new_adapter_kinds(self, used_only: bool = True) -> Set[str]:
        return {r.new_ak for r in self.rows if not used_only or self.used[(r.old_ak, r.old_rk)]}

    def occurs(self, s: str) -> List[str]:
        """The mapped (old) adapter kinds that occur in ``s`` as a substring."""
        return [ak for ak in self.aks if ak in s]


# ------------------------------------------------------------------ result
@dataclass
class Remap:
    """What the map did to one object."""

    payload: object = None
    context: Dict[str, object] = field(default_factory=dict)
    #: kind references re-pointed (a pair, an id, a formula entry: one each)
    count: int = 0
    #: "old -> new" -> occurrences
    changes: Counter = field(default_factory=Counter)
    problems: List[str] = field(default_factory=list)
    #: the definition id re-pointed (derived form), if any
    new_id: Optional[str] = None
    #: final pair -> the source pairs that land on it
    finals: Dict[Tuple, Set[Tuple]] = field(default_factory=lambda: defaultdict(set))


class _Ctx:
    def __init__(self, km: KindMap):
        self.km = km
        self.r = Remap()

    def pair(self, ak, rk, where: str, count: bool = True) -> Tuple:
        if ak is None:
            return ak, rk
        new = self.km.lookup(ak, rk, count=count)
        final = new if new is not None else (ak, rk)
        if count:
            self.r.finals[final].add((ak, rk))
        if new is not None and new != (ak, rk) and count:
            self.r.count += 1
            self.r.changes[f"{ak}:{rk} -> {new[0]}:{new[1]}"] += 1
        return final

    def adapter_only(self, ak, where: str) -> str:
        new, prob = self.km.adapter_only(ak)
        if prob:
            self.r.problems.append(f"{where}: {prob}")
            return ak
        if new is None:
            return ak
        self.r.count += 1
        self.r.changes[f"{ak}:* -> {new}:*"] += 1
        return new

    def id_change(self, old: str, new: str) -> None:
        self.r.count += 1
        self.r.changes[f"{old} -> {new}"] += 1

    def merge_check(self, what: str) -> None:
        for final, origs in self.r.finals.items():
            if len(origs) > 1 and any(self.km.lookup(a, k, count=False) is not None for a, k in origs):
                names = ", ".join(sorted(f"{a}:{k}" for a, k in origs))
                self.r.problems.append(
                    f"the kind map makes {names} the same kind {final[0]}:{final[1]} in this {what} (the kinds "
                    f"it holds would merge); map them to distinct kinds or convert the object separately")


# --------------------------------------------------------------- formulas
_ENTRY_KEYS_TEXT = ("metric", "attribute", "resourcename", "identifiers", "where")


def _scan_entry_end(text: str, i: int) -> int:
    """Index of the ``}`` closing the resource entry whose ``${`` is at
    ``i``, or -1 (quotes and ``{}`` nesting respected)."""
    depth, q = 0, False
    j = i + 2
    while j < len(text):
        c = text[j]
        if q:
            if c == '"':
                q = False
        elif c == '"':
            q = True
        elif c == "{":
            depth += 1
        elif c == "}":
            if depth == 0:
                return j
            depth -= 1
        j += 1
    return -1


def _split_parts(inner: str, base: int) -> List[Tuple[int, int]]:
    """``(start, end)`` spans (absolute, ``base`` added) of the comma
    separated parts of an entry, at depth 0 outside quotes."""
    parts, depth, q, start = [], 0, False, 0
    for j, c in enumerate(inner):
        if q:
            if c == '"':
                q = False
            continue
        if c == '"':
            q = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append((base + start, base + j))
            start = j + 1
    parts.append((base + start, base + len(inner)))
    return parts


@dataclass
class _Slot:
    key: str           # lower-cased entry key, "" for a bare part (this, a where string)
    vstart: int        # value span (absolute) without surrounding whitespace
    vend: int


def formula_entries(text: str) -> Optional[List[Tuple[int, int, List[_Slot]]]]:
    """The resource entries of a formula: ``(start, end, slots)`` with
    ``start`` at ``${`` and ``end`` after ``}``; ``None`` when an entry is
    not closed or the quotes cannot be told apart (a backslash)."""
    if "\\" in text:
        return None
    out = []
    i = 0
    while True:
        i = text.find("${", i)
        if i < 0:
            return out
        e = _scan_entry_end(text, i)
        if e < 0:
            return None
        slots = []
        for a, b in _split_parts(text[i + 2:e], i + 2):
            part = text[a:b]
            if "=" in part and not part.lstrip().startswith('"'):
                k, _, _v = part.partition("=")
                vs = a + len(k) + 1
                ve = b
                while vs < ve and text[vs].isspace():
                    vs += 1
                while ve > vs and text[ve - 1].isspace():
                    ve -= 1
                slots.append(_Slot(k.strip().lower(), vs, ve))
            else:
                vs, ve = a, b
                while vs < ve and text[vs].isspace():
                    vs += 1
                while ve > vs and text[ve - 1].isspace():
                    ve -= 1
                slots.append(_Slot("", vs, ve))
        out.append((i, e + 1, slots))
        i = e + 1


def remap_formula(text: str, ctx: _Ctx, where: str) -> str:
    """A super metric formula with the kind slots of its resource entries
    re-pointed (``adaptertype=`` / ``objecttype=``); nothing else is
    touched. Problems go to ``ctx``."""
    if not ctx.km.occurs(text):
        return text
    entries = formula_entries(text)
    if entries is None:
        ctx.r.problems.append(f"{where}: the formula names {', '.join(ctx.km.occurs(text))}, and its resource "
                              f"entries cannot be delimited with certainty (an unclosed entry or a backslash)")
        return text
    edits: List[Tuple[int, int, str]] = []
    for n, (s, e, slots) in enumerate(entries):
        ak_s = next((x for x in slots if x.key == "adaptertype"), None)
        rk_s = next((x for x in slots if x.key == "objecttype"), None)
        if ak_s is None:
            continue
        ak = text[ak_s.vstart:ak_s.vend]
        if ak not in ctx.km.aks:
            continue
        rk = text[rk_s.vstart:rk_s.vend] if rk_s is not None else None
        ewhere = f"{where} entry {n + 1} ({text[s:e][:80]})"
        if rk is None or rk == STAR:
            new_ak = ctx.adapter_only(ak, ewhere)
            if new_ak != ak:
                edits.append((ak_s.vstart, ak_s.vend, new_ak))
            continue
        nak, nrk = ctx.pair(ak, rk, ewhere)
        if nak != ak:
            edits.append((ak_s.vstart, ak_s.vend, nak))
        if nrk != rk:
            edits.append((rk_s.vstart, rk_s.vend, nrk))
    for a, b, rep in sorted(edits, reverse=True):
        text = text[:a] + rep + text[b:]
    return text


def formula_kind_problem(text: str, km: KindMap) -> Optional[str]:
    """Why an occurrence of a mapped adapter kind in ``text`` (a formula,
    after re-pointing) is not one the importer can classify, or ``None``:
    each must be inside a resource entry, as the kind slot of an entry the
    map does not cover, or inside a metric key, a resource name, an
    identifier block or a quoted string; a quoted string (a where clause)
    with a word equal to a mapped adapter kind may name the kind as data."""
    hits = km.occurs(text)
    if not hits:
        return None
    entries = formula_entries(text)
    if entries is None:
        return f"the formula names {', '.join(hits)} and its entries cannot be delimited with certainty"
    ok: List[Tuple[int, int]] = []
    for s, e, slots in entries:
        ak_s = next((x for x in slots if x.key == "adaptertype"), None)
        rk_s = next((x for x in slots if x.key == "objecttype"), None)
        if ak_s is not None and text[ak_s.vstart:ak_s.vend] in km.aks:
            ak = text[ak_s.vstart:ak_s.vend]
            rk = text[rk_s.vstart:rk_s.vend] if rk_s is not None else None
            moved = (km.adapter_only(ak, count=False)[0] if rk in (None, STAR)
                     else km.lookup(ak, rk, count=False))
            if moved:
                return (f"the formula entry {text[s:e][:80]!r} still names {ak}, which the kind map re-points (the "
                        f"importer missed this place; an internal error)")
        for x in slots:
            val = text[x.vstart:x.vend]
            if x.key in ("adaptertype", "objecttype") or x.key in _ENTRY_KEYS_TEXT:
                ok.append((x.vstart, x.vend))
            elif x.key == "" and val.startswith('"'):
                ok.append((x.vstart, x.vend))
            if '"' in val:
                for lit in re.findall(r'"([^"]*)"', val):
                    for w in lit.split():
                        if w in km.aks:
                            return (f"the formula's quoted string {lit[:60]!r} has the word {w!r}, a mapped "
                                    f"adapter kind; it may name the kind as data, which the importer cannot "
                                    f"re-point with certainty")
    for ak in hits:
        for m in re.finditer(re.escape(ak), text):
            if not any(a <= m.start() and m.end() <= b for a, b in ok):
                return (f"the formula names {ak} at character {m.start()} ({text[max(0, m.start() - 20):m.end() + 20]!r}), "
                        f"outside the kind slots, metric keys, names and quoted strings of its resource entries")
    return None


# ------------------------------------------------------------- derived ids
def _derived_ak(id_: str, prefix: str, ak: Optional[str]) -> bool:
    return bool(ak) and id_.startswith(prefix + ak + "-")


def derived_id_table(objs, km: KindMap, keep_ids: Set[Tuple[str, str]]):
    """The derived-form ids (``SymptomDefinition-<kind>-...``,
    ``AlertDefinition-<kind>-...``, ``Recommendation-df-<kind>-...``) the
    map re-points: ``{(type, old id): new id}``, ``{(type, old id):
    problem}`` and ``{(type, old id): exception}`` for an object whose
    shape raised (the caller records it as that object's internal error;
    it never stops the run). Only objects whose shipped id is this re-pointed one are in
    the table (``keep_ids``: (type, id) of objects that keep their source
    id; minted and id-mapped ones ship another id, so their references are
    left as they were). A symptom or alert is re-pointed when its id embeds
    its own adapter kind and its own pair is mapped. A recommendation (it has
    no kind of its own) follows the alerts in the set that reference it:
    when none of them moves, its key is kept; when they all move from the
    kind its key embeds to one new adapter kind, the key follows; when only
    some move, or they move to different kinds, it stops. Referenced by no
    alert, it follows its key's adapter kind when that moves as a whole, and
    is kept otherwise."""
    table: Dict[Tuple[str, str], str] = {}
    problems: Dict[Tuple[str, str], str] = {}
    rec_users: Dict[str, Set[Tuple]] = defaultdict(set)
    internal: Dict[Tuple[str, str], str] = {}
    for o in objs:
        try:
            if o.type == "alert":
                rr = o.payload.find("State/Recommendations")
                for r in (rr if rr is not None else []):
                    if r.get("ref"):
                        rec_users[r.get("ref")].add((o.payload.get("adapterKind") or "",
                                                     o.payload.get("resourceKind")))
        except Exception as exc:  # an unexpected shape: that object's internal error, never the run
            internal.setdefault((o.type, o.id), f"{type(exc).__name__}: {exc}")
    for o in objs:
        if (o.type, o.id) in internal:
            continue
        try:
            if (o.type, o.id) not in keep_ids:
                continue
            if o.type in ("symptom", "alert"):
                prefix = _SYMPTOM_PREFIX if o.type == "symptom" else _ALERT_PREFIX
                ak, rk = o.payload.get("adapterKind"), o.payload.get("resourceKind")
                if not _derived_ak(o.id, prefix, ak):
                    continue
                new = km.lookup(ak, rk, count=False)
                if new is not None and new[0] != ak:
                    table[(o.type, o.id)] = prefix + new[0] + o.id[len(prefix) + len(ak):]
            elif o.type == "recommendation":
                for ak in sorted(km.aks, key=len, reverse=True):
                    if not _derived_ak(o.id, _REC_PREFIX, ak):
                        continue
                    users = rec_users.get(o.id, set())
                    rest = o.id[len(_REC_PREFIX) + len(ak):]
                    if not users:
                        new_ak, prob = km.adapter_only(ak, count=False)
                        if new_ak and not prob:
                            table[(o.type, o.id)] = _REC_PREFIX + new_ak + rest
                        break
                    moving = {}
                    for u in users:
                        m = km.lookup(u[0], u[1], count=False)
                        if m is not None and m[0] != u[0]:
                            moving[u] = m
                    if not moving:
                        break  # no alert using it moves: the key is kept, with certainty
                    new_aks = {m[0] for m in moving.values()}
                    other = sorted({u[0] for u in users if u[0] != ak})
                    if len(moving) != len(users) or len(new_aks) > 1 or other:
                        still = sorted(f"{u[0]}:{u[1]}" for u in users if u not in moving)
                        problems[(o.type, o.id)] = (
                            f"recommendation key {o.id} embeds the mapped adapter kind {ak}; the alerts that use it "
                            f"move to {', '.join(sorted(new_aks))}"
                            + (f" while alerts on {', '.join(still)} stay" if still else "")
                            + (f", and alerts on {', '.join(other)} use it too" if other else "")
                            + "; the importer cannot re-point it with certainty")
                        break
                    table[(o.type, o.id)] = _REC_PREFIX + next(iter(new_aks)) + rest
                    break
        except Exception as exc:  # an unexpected shape: that object's internal error, never the run
            internal.setdefault((o.type, o.id), f"{type(exc).__name__}: {exc}")
    return table, problems, internal


# ----------------------------------------------------------- per type
def _xml_pair(el, ctx: _Ctx, where: str, count: bool = True) -> None:
    ak, rk = el.get("adapterKind"), el.get("resourceKind")
    if ak is None:
        return
    nak, nrk = ctx.pair(ak, rk, where, count=count)
    if nak != ak:
        el.set("adapterKind", nak)
    if rk is not None and nrk != rk:
        el.set("resourceKind", nrk)


def _ref(value: str, rtype: str, ctx: _Ctx, ids: "_Ids", where: str) -> str:
    """A reference to a symptom, alert or recommendation id."""
    new = ids.table.get((rtype, value))
    if new is not None:
        ctx.id_change(value, new)
        return new
    if (rtype, value) in ids.in_set or (rtype, value) in ids.dropped:
        return value
    prefix = {"symptom": _SYMPTOM_PREFIX, "alert": _ALERT_PREFIX, "recommendation": _REC_PREFIX}[rtype]
    for ak in ctx.km.aks:
        if value.startswith(prefix + ak + "-"):
            ctx.r.problems.append(
                f"{where}: references {rtype} {value}, which is not in the input; its id embeds the mapped "
                f"adapter kind {ak}, and whether the object it names moves with the map cannot be known "
                f"(convert it with this set, or drop it to keep the reference as it is)")
    return value


@dataclass
class _Ids:
    table: Dict[Tuple[str, str], str]
    in_set: Set[Tuple[str, str]]
    dropped: Set[Tuple[str, str]]


def _view(el, ctx: _Ctx) -> None:
    for tag in ("SubjectType", "SubjectsGroupBy", "BlacklistResourceKind"):
        for st in el.findall(tag):
            _xml_pair(st, ctx, tag)
    for val in el.iter("Value"):
        props = {p.get("name"): p for p in val.findall("Property") if p.get("name") in ("adapterKind", "resourceKind")}
        akp, rkp = props.get("adapterKind"), props.get("resourceKind")
        if akp is None or akp.get("value") is None:
            continue
        ak = akp.get("value")
        rk = rkp.get("value") if rkp is not None else None
        nak, nrk = ctx.pair(ak, rk, "column")
        if nak != ak:
            akp.set("value", nak)
        if rkp is not None and nrk != rk:
            rkp.set("value", nrk)


def _report(el, ctx: _Ctx) -> None:
    for st in el.findall("SubjectType"):
        _xml_pair(st, ctx, "SubjectType")


def _symptom(el, ctx: _Ctx, ids: _Ids) -> None:
    _xml_pair(el, ctx, "SymptomDefinition")
    old = el.get("id")
    new = ids.table.get(("symptom", old))
    if new:
        el.set("id", new)
        ctx.id_change(old, new)
        ctx.r.new_id = new


def _alert(el, ctx: _Ctx, ids: _Ids) -> None:
    _xml_pair(el, ctx, "AlertDefinition")
    old = el.get("id")
    new = ids.table.get(("alert", old))
    if new:
        el.set("id", new)
        ctx.id_change(old, new)
        ctx.r.new_id = new
    for x in el.iter():
        if x.tag in ("SymptomSet", "Symptom") and x.get("ref"):
            x.set("ref", _ref(x.get("ref"), "symptom", ctx, ids, f"{x.tag} ref"))
        elif x.tag == "Recommendation" and x.get("ref"):
            x.set("ref", _ref(x.get("ref"), "recommendation", ctx, ids, "recommendation ref"))


def _recommendation(el, ctx: _Ctx, ids: _Ids) -> None:
    for a in ("key", "id"):
        old = el.get(a)
        if old is None:
            continue
        new = ids.table.get(("recommendation", old))
        if new:
            el.set(a, new)
            ctx.id_change(old, new)
            ctx.r.new_id = new


def _supermetric(sm: dict, ctx: _Ctx) -> None:
    for r in sm.get("resourceKinds") or []:
        if isinstance(r, dict) and r.get("adapterKindKey") is not None:
            ak, rk = r.get("adapterKindKey"), r.get("resourceKindKey")
            nak, nrk = ctx.pair(ak, rk, "resourceKinds")
            r["adapterKindKey"] = nak
            if "resourceKindKey" in r:
                r["resourceKindKey"] = nrk
    if isinstance(sm.get("formula"), str):
        sm["formula"] = remap_formula(sm["formula"], ctx, "formula")


_RKID = re.compile(r"^0020(\d\d)(.*)$", re.S)
_INTERNAL = re.compile(r"(?:resourceKind|resource):id:\d+_::_")


def _split_rkid(s) -> Optional[Tuple[str, str]]:
    m = _RKID.match(s) if isinstance(s, str) else None
    if not m or len(m.group(2)) < int(m.group(1)):
        return None
    n = int(m.group(1))
    return m.group(2)[:n], m.group(2)[n:]


def _rkid(ak: str, rk: str) -> str:
    from ..dashboards.render import adapter_kind_prefix
    return f"{adapter_kind_prefix(ak)}{ak}{rk}"


def _dashboard(db: dict, context: dict, ctx: _Ctx, ids: _Ids) -> dict:
    """Re-point a dashboard (``db`` is a copy) and return its context with
    a re-pointed copy of the ``entries`` table."""
    import json
    used = set(_INTERNAL.findall(json.dumps(db)))
    entries = copy.deepcopy(context.get("entries") or {})
    orig_rk = {}
    for table in ("resourceKind", "resource"):
        for e in (entries.get(table) or []) if isinstance(entries, dict) else []:
            if not isinstance(e, dict) or e.get("adapterKindKey") is None:
                continue
            ak, rk = e.get("adapterKindKey"), e.get("resourceKindKey")
            if table == "resourceKind":
                orig_rk[e.get("internalId")] = (ak, rk)
            nak, nrk = ctx.pair(ak, rk, f"entries {table}", count=e.get("internalId") in used)
            e["adapterKindKey"] = nak
            if "resourceKindKey" in e:
                e["resourceKindKey"] = nrk
    folder = context.get("folder")
    if folder in _SUMMARY_FOLDERS and ctx.km.lookup("VMWARE", folder, count=False) is not None:
        ctx.r.problems.append(f"the dashboard is a Summary page for VMWARE:{folder} (its pak folder), which the "
                              f"kind map re-points; the importer does not re-point Summary page bindings")

    def rkid_field(obj: dict, key: str, where: str) -> None:
        sp = _split_rkid(obj.get(key))
        if sp is None:
            return
        nak, nrk = ctx.pair(sp[0], sp[1], where)
        if (nak, nrk) != sp:
            obj[key] = _rkid(nak, nrk)

    for i, w in enumerate(db.get("widgets") or []):
        if not isinstance(w, dict) or not isinstance(w.get("config"), dict):
            continue
        c = w["config"]
        where = f"widget {i} ({w.get('type')})"
        t = w.get("type")
        if t == "View" and isinstance(c.get("resource"), dict):
            rkid_field(c["resource"], "resourceKindId", f"{where} pin")
        if isinstance(c.get("metric"), dict):
            for m in c["metric"].get("resourceKindMetrics") or []:
                # resourceKindName is the resource kind key by the renderer's
                # default: one equal to the old key follows the kind
                if isinstance(m, dict) and m.get("resourceKindId") in orig_rk:
                    oak, ork = orig_rk[m["resourceKindId"]]
                    new = ctx.km.lookup(oak, ork, count=False)
                    if new is not None and m.get("resourceKindName") == ork and new[1] != ork:
                        m["resourceKindName"] = new[1]
        if t == "Scoreboard" and isinstance(c.get("metric"), dict):
            for m in c["metric"].get("resourceMetrics") or []:
                if isinstance(m, dict):
                    rkid_field(m, "resourceKindId", f"{where} resource metric")
        if t == "Heatmap":
            for tab in c.get("configs") or []:
                if not isinstance(tab, dict):
                    continue
                cf = tab.get("customFilter")
                if isinstance(cf, dict):
                    for g in cf.get("filter") or []:
                        if isinstance(g, dict):
                            before = g.get("resourceKindId")
                            rkid_field(g, "resourceKindId", f"{where} custom filter")
                            if g.get("resourceKind") == before and before != g.get("resourceKindId"):
                                g["resourceKind"] = g["resourceKindId"]
                gb = tab.get("groupBy")
                if isinstance(gb, dict) and gb.get("typeId") in orig_rk:
                    oak, ork = orig_rk[gb["typeId"]]
                    new = ctx.km.lookup(oak, ork, count=False)
                    if new is None:
                        continue
                    nak, nrk = new
                    if gb.get("adapterKind") == oak and gb.get("resourceKind") == ork:
                        gb["adapterKind"], gb["resourceKind"] = nak, nrk
                        ctx.pair(oak, ork, f"{where} groupBy")
                    if gb.get("parentId") == oak:
                        gb["parentId"] = nak
                    if gb.get("parentText") == oak:
                        # the renderer's default label is the adapter kind key
                        gb["parentText"] = nak
                    try:
                        if gb.get("id") == "004null" + _rkid(oak, ork):
                            gb["id"] = "004null" + _rkid(nak, nrk)
                    except ValueError:
                        pass
        if t == "AlertList":
            for a in c.get("alertDefinitions") or []:
                if isinstance(a, dict) and isinstance(a.get("id"), str):
                    a["id"] = _ref(a["id"], "alert", ctx, ids, f"{where} alertDefinitions")
    out = dict(context)
    out["entries"] = entries
    return out


def remap_object(o, km: KindMap, ids: _Ids) -> Remap:
    """Re-point one source object (``inputs.SourceObject``). The object is
    not changed: the returned :class:`Remap` carries a re-pointed copy of
    its payload (and, for a dashboard, of its context)."""
    ctx = _Ctx(km)
    payload = copy.deepcopy(o.payload)
    context = dict(o.context)
    if o.type == "view":
        _view(payload, ctx)
    elif o.type == "report":
        _report(payload, ctx)
    elif o.type == "symptom":
        _symptom(payload, ctx, ids)
    elif o.type == "alert":
        _alert(payload, ctx, ids)
    elif o.type == "recommendation":
        _recommendation(payload, ctx, ids)
    elif o.type == "supermetric":
        _supermetric(payload, ctx)
    elif o.type == "dashboard":
        context = _dashboard(payload, o.context, ctx, ids)
    ctx.merge_check(o.type)
    ctx.r.payload, ctx.r.context = payload, context
    return ctx.r


def make_ids(objs, km: KindMap, keep_ids, dropped):
    """``(ids, problems, internal)`` (:func:`derived_id_table`)."""
    table, problems, internal = derived_id_table(objs, km, keep_ids)
    return _Ids(table, {(o.type, o.id) for o in objs}, set(dropped)), problems, internal


def change_lines(r: Remap) -> List[str]:
    return [f"{k}" + (f" x{n}" if n > 1 else "") for k, n in sorted(r.changes.items())]


__all__ = ["KindRow", "KindMap", "Remap", "STAR", "parse_kind_map", "remap_object", "remap_formula",
           "formula_kind_problem", "make_ids", "change_lines"]
