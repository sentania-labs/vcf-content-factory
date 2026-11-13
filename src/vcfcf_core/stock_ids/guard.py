"""Stock content id guard: scanner, baseline, allowlist and check (issue #345).

VCF Operations tracks pak and content-import content by id. Installing
content overwrites any existing object with the same id; uninstalling a pak
deletes every id it shipped. A definition that reuses the id of a view,
dashboard, report template, super metric, symptom, alert or recommendation
shipped with the product therefore overwrites the stock object when it is
installed and deletes it when the pak is removed (the factory's retired
vCommunity port deleted 64 stock views from a lab this way). This module
refuses such definitions.

Only DEFINITIONS count. A dashboard widget, report section or alert that
points at a stock object by id is a reference and is legal: the scanner
reads ``<ViewDef id>``, ``<ReportDef id>``, ``<SymptomDefinition id>``,
``<AlertDefinition id>``, ``<Recommendation key>`` (not ``ref``), the
top-level ``dashboards[].id`` of a dashboard JSON and the top-level keys of a
super metric JSON, and nothing nested inside them.

The baseline (``stock_ids_baseline.json`` beside this file) holds ids only:
type, id, a display name for the error message and the product versions the
id was seen in. It is generated from clean content exports by
``python3 -m vcfcf_packaging stock-id-baseline`` (see ``generate.py`` for how
an id is shown to be stock). Fail closed: a missing, unreadable, malformed or
empty baseline raises ``StockIdBaselineError``, and every caller turns that
into a failed build rather than skipping the check.

The escape hatch is an explicit allowlist (``stock_id_allowlist:`` in
adapter.yaml or a bundle manifest), one entry per id with a required reason.
An allowlisted hit is a warning on every run, never silent.

This file is self-contained (stdlib only, no package-relative import) so the
sdk-buildkit ships it verbatim as ``sdk_buildkit/stock_ids.py`` next to the
same baseline file.
"""
from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Content types
# ---------------------------------------------------------------------------

#: Content types with stable, content-carried ids. Custom groups are not
#: here: their id is assigned by the server and never travels in content.
CONTENT_TYPES: Tuple[str, ...] = (
    "view",
    "dashboard",
    "report",
    "supermetric",
    "symptom",
    "alert",
    "recommendation",
)

_TYPE_LABELS: Dict[str, str] = {
    "view": "view",
    "dashboard": "dashboard",
    "report": "report template",
    "supermetric": "super metric",
    "symptom": "symptom definition",
    "alert": "alert definition",
    "recommendation": "recommendation",
}

BASELINE_FORMAT = "vcfcf-stock-ids/1"
BASELINE_FILE_NAME = "stock_ids_baseline.json"

#: Nested archives deeper than this are not opened (a pak is
#: pak > adapters.zip > views.zip, an export dashboards zip is two deep).
_MAX_ZIP_DEPTH = 6
#: A zip member larger than this is skipped with a note (zip-bomb guard).
_MAX_MEMBER_BYTES = 512 * 1024 * 1024


class StockIdBaselineError(RuntimeError):
    """The stock-id baseline is missing, unreadable, malformed or empty."""


class StockIdAllowlistError(ValueError):
    """A ``stock_id_allowlist`` entry is malformed."""


def type_label(content_type: str) -> str:
    return _TYPE_LABELS.get(content_type, content_type)


def normalize_id(value: str) -> str:
    """Comparison form of an id: stripped, lower case."""
    return str(value).strip().lower()


def version_sort_key(version: str) -> Tuple:
    return tuple(int(n) for n in re.findall(r"\d+", version)) or (0,)


# ---------------------------------------------------------------------------
# Definitions found in content
# ---------------------------------------------------------------------------

@dataclass
class Definition:
    """One content definition: its type, id, display name and where it is."""

    type: str
    id: str
    name: str
    location: str
    attrs: Dict[str, str] = field(default_factory=dict)


def definitions_from_objects(
    content_type: str,
    objs: Iterable,
    *,
    id_of: Optional[Callable[[object], Optional[str]]] = None,
) -> List[Definition]:
    """Definitions for loaded content objects (views, dashboards, ...).

    ``id_of`` returns the id the object ships under; the default reads
    ``obj.id``. Objects with no id (a server-assigned type) are skipped.
    The location is the object's ``source_path`` (or ``source_file``).
    """
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"unknown content type {content_type!r}")
    out: List[Definition] = []
    for obj in objs or []:
        oid = id_of(obj) if id_of is not None else getattr(obj, "id", None)
        if not oid:
            continue
        name = str(getattr(obj, "name", "") or "")
        src = getattr(obj, "source_path", None) or getattr(obj, "source_file", None)
        out.append(Definition(content_type, str(oid), name, str(src) if src else name))
    return out


def bundled_definitions(
    *,
    views: Iterable = (),
    dashboards: Iterable = (),
    supermetrics: Iterable = (),
    reports: Iterable = (),
    symptoms: Iterable = (),
    alerts: Iterable = (),
    recommendations: Iterable = (),
    alert_content_xml: Optional[str] = None,
) -> List[Definition]:
    """Every definition a set of loaded content objects ships under.

    Views, dashboards, super metrics and reports carry their id. Symptom,
    alert and recommendation ids are derived when the content is rendered,
    so the caller passes the rendered ``<alertContent>`` XML for them
    (``render_alert_content_xml``); each id found there is attributed back
    to its YAML by name (symptom, alert) or id (recommendation).
    """
    defs: List[Definition] = []
    defs += definitions_from_objects("view", views)
    defs += definitions_from_objects("dashboard", dashboards)
    defs += definitions_from_objects("supermetric", supermetrics)
    defs += definitions_from_objects("report", reports)
    if alert_content_xml:
        def _src(objs, key):
            out = {}
            for o in objs or []:
                src = getattr(o, "source_path", None) or getattr(o, "source_file", None)
                k = key(o)
                if k and src and k not in out:
                    out[k] = str(src)
            return out
        sym_src = _src(symptoms, lambda o: getattr(o, "name", None))
        alert_src = _src(alerts, lambda o: getattr(o, "name", None))
        rec_src = _src(recommendations, lambda o: getattr(o, "id", None))
        data = alert_content_xml.encode("utf-8") if isinstance(alert_content_xml, str) else alert_content_xml
        for d in scan_bytes(data, "<rendered alert content>"):
            if d.type == "symptom":
                d.location = sym_src.get(d.name, d.location)
            elif d.type == "alert":
                d.location = alert_src.get(d.name, d.location)
            elif d.type == "recommendation":
                d.location = rec_src.get(d.id, d.location)
            defs.append(d)
    return defs


# ---------------------------------------------------------------------------
# Artifact scanner: paks, content zips, exports, directories, single files
# ---------------------------------------------------------------------------

_XML_TOKENS = (b"ViewDef", b"ReportDef", b"SymptomDefinition", b"AlertDefinition",
               b"Recommendation", b"superMetric")
_JSON_TOKENS = (b'"dashboards"', b'"formula"')
_XML_DEF_TAGS = {
    "ViewDef": "view",
    "ReportDef": "report",
    "SymptomDefinition": "symptom",
    "AlertDefinition": "alert",
}


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _is_zip(data: bytes) -> bool:
    return data[:4] in (b"PK\x03\x04", b"PK\x05\x06")


def _strip_lead(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.lstrip()


def _child_text(elem, tag: str) -> Optional[str]:
    for child in elem:
        if _local(child.tag) == tag:
            return child.text or ""
    return None


def _xml_definitions(data: bytes, location: str) -> List[Definition]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return _xml_definitions_by_regex(data, location)
    out: List[Definition] = []
    # Iterative walk (an explicit stack, not recursion): a deeply nested
    # third-party file must not turn into a RecursionError.
    stack = [(root, False)]
    while stack:
        elem, in_policy = stack.pop()
        tag = _local(elem.tag)
        attrs: Dict[str, str] = {"in_policy": "1"} if in_policy else {}
        ctype = _XML_DEF_TAGS.get(tag)
        if ctype is not None and elem.get("id"):
            if ctype in ("view", "report"):
                name = ""
                for child in elem:
                    if _local(child.tag) == "Title":
                        name = (child.text or "").strip()
                        # Product-localized content carries
                        # <Title localizationKey=...>; the generator reads it.
                        if child.get("localizationKey"):
                            attrs["localized"] = "1"
                        break
            else:
                name = elem.get("name", "") or ""
            for a in ("adapterKind", "symptomDefType"):
                if elem.get(a):
                    attrs[a] = elem.get(a)
            out.append(Definition(ctype, elem.get("id"), name, location, attrs))
        elif tag == "Recommendation" and elem.get("ref") is None:
            # Definition form: <Recommendation key="..."> (alertContent) or
            # id= in a recommendation export; ref= is a reference.
            oid = elem.get("key") or elem.get("id")
            if oid:
                desc = " ".join((_child_text(elem, "Description") or "").split())
                out.append(Definition("recommendation", oid, desc[:80], location, attrs))
        elif tag == "superMetric" and elem.get("uuid") and _child_text(elem, "formula") is not None:
            # A policy export embeds full super metric definitions as
            # <superMetric uuid=...><formula>; <SuperMetric enabled id=.../>
            # (capital S, no formula) is a policy enablement, a reference.
            out.append(Definition("supermetric", elem.get("uuid"), elem.get("name", "") or "", location, attrs))
        child_in_policy = in_policy or tag in ("Policy", "PolicyContent", "Policies")
        stack.extend((child, child_in_policy) for child in reversed(list(elem)))
    return out


_RE_DEF_TAG = re.compile(rb"<(ViewDef|ReportDef|SymptomDefinition|AlertDefinition|Recommendation)\b([^>]*)>")
_RE_ATTR = re.compile(rb'\b(id|key|ref|name)\s*=\s*"([^"]*)"')


def _xml_definitions_by_regex(data: bytes, location: str) -> List[Definition]:
    """Fallback for XML that does not parse: still report its definitions.

    A malformed file must not hide a definition from the guard (the
    importer may be more lenient than ElementTree).
    """
    out: List[Definition] = []
    for m in _RE_DEF_TAG.finditer(data):
        tag = m.group(1).decode("ascii")
        attrs = {k.decode(): v.decode("utf-8", "replace") for k, v in _RE_ATTR.findall(m.group(2))}
        if tag == "Recommendation":
            if "ref" in attrs:
                continue
            oid = attrs.get("key") or attrs.get("id")
            ctype = "recommendation"
        else:
            oid = attrs.get("id")
            ctype = _XML_DEF_TAGS[tag]
        if oid:
            out.append(Definition(ctype, oid, attrs.get("name", ""), location + " (unparsed XML)"))
    return out


def _json_definitions(data: bytes, location: str) -> List[Definition]:
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return []  # not JSON the importer could read either
    out: List[Definition] = []

    def _sm(oid, v) -> None:
        if oid:
            out.append(Definition("supermetric", str(oid), str(v.get("name", "") or ""), location))

    if isinstance(obj, dict):
        dashes = obj.get("dashboards")
        if isinstance(dashes, list):
            for d in dashes:
                if isinstance(d, dict) and d.get("id"):
                    attrs = {}
                    if d.get("adapterName"):
                        attrs["adapterName"] = str(d.get("adapterName"))
                    out.append(Definition("dashboard", str(d["id"]), str(d.get("name", "") or ""), location, attrs))
        for key in ("superMetrics", "supermetrics"):
            lst = obj.get(key)
            if isinstance(lst, list):
                for v in lst:
                    if isinstance(v, dict) and "formula" in v:
                        _sm(v.get("id"), v)
        for k, v in obj.items():
            if isinstance(v, dict) and "formula" in v:
                _sm(v.get("id") or k, v)
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, dict) and "formula" in v:
                _sm(v.get("id"), v)
    return out


def scan_bytes(data: bytes, location: str, _depth: int = 0) -> List[Definition]:
    """Every content definition in ``data`` (a zip, an XML or a JSON file).

    Zips are opened recursively (a .pak, an adapters.zip, a views.zip, a
    content-export zip and the per-owner dashboard zips inside it). The
    location of a definition inside an archive is ``outer!member``.
    """
    if _is_zip(data):
        if _depth >= _MAX_ZIP_DEPTH:
            return []
        out: List[Definition] = []
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return []
        with zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > _MAX_MEMBER_BYTES:
                    continue
                try:
                    member = zf.read(info)
                except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError):
                    continue
                out.extend(scan_bytes(member, f"{location}!{info.filename}", _depth + 1))
        return out
    body = _strip_lead(data)
    if body[:1] == b"<":
        if any(tok in body for tok in _XML_TOKENS):
            return _xml_definitions(body, location)
        return []
    if body[:1] in (b"{", b"["):
        if any(tok in body for tok in _JSON_TOKENS):
            return _json_definitions(body, location)
        return []
    return []


def scan_path(path) -> List[Definition]:
    """Every content definition under ``path``: a file, a zip or a directory."""
    path = Path(path)
    if path.is_dir():
        out: List[Definition] = []
        for p in sorted(path.rglob("*")):
            if p.is_file():
                out.extend(scan_bytes(p.read_bytes(), str(p)))
        return out
    return scan_bytes(path.read_bytes(), str(path))


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StockEntry:
    type: str
    id: str
    name: str
    versions: Tuple[str, ...]


class StockBaseline:
    """The loaded stock-id baseline: ``(type, id) -> StockEntry``."""

    def __init__(self, entries: Dict[Tuple[str, str], StockEntry], source: str, meta: dict):
        self._entries = entries
        self.source = source
        self.meta = meta

    def lookup(self, content_type: str, oid: str) -> Optional[StockEntry]:
        return self._entries.get((content_type, normalize_id(oid)))

    def count(self, content_type: Optional[str] = None) -> int:
        if content_type is None:
            return len(self._entries)
        return sum(1 for (t, _) in self._entries if t == content_type)

    def versions(self) -> List[str]:
        vs = {v for e in self._entries.values() for v in e.versions}
        return sorted(vs, key=version_sort_key)

    def entries(self) -> List[StockEntry]:
        return list(self._entries.values())


def default_baseline_path() -> Path:
    """The baseline shipped beside this module (factory and buildkit alike)."""
    return Path(__file__).with_name(BASELINE_FILE_NAME)


_CACHE: Dict[str, StockBaseline] = {}


def parse_baseline(text: str, source: str = "<baseline>") -> StockBaseline:
    """Parse baseline JSON text; raise ``StockIdBaselineError`` on any defect."""
    def bad(msg: str) -> StockIdBaselineError:
        return StockIdBaselineError(f"stock-id baseline {source}: {msg}")

    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise bad(f"not valid JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise bad("expected a JSON object at the top level")
    if raw.get("format") != BASELINE_FORMAT:
        raise bad(f"format is {raw.get('format')!r}, expected {BASELINE_FORMAT!r}")
    ids = raw.get("ids")
    if not isinstance(ids, dict):
        raise bad("'ids' must be an object keyed by content type")
    entries: Dict[Tuple[str, str], StockEntry] = {}
    for ctype, table in ids.items():
        if ctype not in CONTENT_TYPES:
            raise bad(f"unknown content type {ctype!r} under 'ids'")
        if not isinstance(table, dict):
            raise bad(f"ids.{ctype} must be an object keyed by id")
        for oid, rec in table.items():
            if not isinstance(oid, str) or not oid.strip():
                raise bad(f"ids.{ctype} has a blank id")
            if not isinstance(rec, dict):
                raise bad(f"ids.{ctype}.{oid} must be an object")
            name = rec.get("name")
            versions = rec.get("versions")
            if not isinstance(name, str):
                raise bad(f"ids.{ctype}.{oid}.name must be a string")
            if (not isinstance(versions, list) or not versions
                    or not all(isinstance(v, str) and v for v in versions)):
                raise bad(f"ids.{ctype}.{oid}.versions must be a non-empty list of strings")
            key = (ctype, normalize_id(oid))
            if key in entries:
                raise bad(f"ids.{ctype} lists {oid} twice")
            entries[key] = StockEntry(ctype, oid, name, tuple(versions))
    if not entries:
        raise bad("holds no ids; a baseline that gates nothing is refused")
    meta = {k: v for k, v in raw.items() if k != "ids"}
    return StockBaseline(entries, source, meta)


def load_baseline(path=None) -> StockBaseline:
    """Load the stock-id baseline (default: the one beside this module).

    Raises ``StockIdBaselineError`` when it cannot be read or is not a
    usable baseline. Callers fail the build on that error: no baseline is
    never a pass.
    """
    p = Path(path) if path is not None else default_baseline_path()
    key = str(p.resolve()) if p.exists() else str(p)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise StockIdBaselineError(
            f"stock-id baseline {p} cannot be read ({exc}). The stock-id guard "
            f"fails closed: restore the file (it ships with the factory and the "
            f"sdk-buildkit) rather than skipping the check."
        ) from exc
    baseline = parse_baseline(text, str(p))
    _CACHE[key] = baseline
    return baseline


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AllowlistEntry:
    type: str
    id: str
    reason: str
    where: str = ""


_ALLOWLIST_KEYS = {"type", "id", "reason"}


def parse_allowlist(raw, where: str) -> List[AllowlistEntry]:
    """Parse a ``stock_id_allowlist`` list (adapter.yaml or bundle manifest).

    Each entry is a mapping with exactly ``type`` (one of CONTENT_TYPES),
    ``id`` and a non-blank ``reason``. Absent (None) means no entries.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise StockIdAllowlistError(
            f"{where}: stock_id_allowlist must be a list of {{type, id, reason}} entries"
        )
    out: List[AllowlistEntry] = []
    seen = set()
    for i, item in enumerate(raw):
        at = f"{where}: stock_id_allowlist[{i}]"
        if not isinstance(item, dict):
            raise StockIdAllowlistError(f"{at} must be a mapping with type, id and reason")
        unknown = set(item) - _ALLOWLIST_KEYS
        if unknown:
            raise StockIdAllowlistError(
                f"{at}: unknown key(s) {sorted(map(str, unknown))}; allowed: type, id, reason"
            )
        ctype = item.get("type")
        if ctype not in CONTENT_TYPES:
            raise StockIdAllowlistError(
                f"{at}: type must be one of {', '.join(CONTENT_TYPES)}; got {ctype!r}"
            )
        oid = item.get("id")
        if not isinstance(oid, str) or not oid.strip():
            raise StockIdAllowlistError(f"{at}: id is required")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise StockIdAllowlistError(
                f"{at}: reason is required: say why this content must ship under a stock id"
            )
        key = (ctype, normalize_id(oid))
        if key in seen:
            raise StockIdAllowlistError(f"{at}: {ctype} {oid} is listed twice")
        seen.add(key)
        out.append(AllowlistEntry(ctype, oid.strip(), " ".join(reason.split()), where))
    return out


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

@dataclass
class StockIdHit:
    definition: Definition
    stock: StockEntry


@dataclass
class GuardResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hits: List[StockIdHit] = field(default_factory=list)
    allowed: List[Tuple[StockIdHit, AllowlistEntry]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_stock_hits(defs: Iterable[Definition], baseline: StockBaseline) -> List[StockIdHit]:
    """Every definition whose id is a stock id of the same type (deduplicated)."""
    hits: List[StockIdHit] = []
    seen = set()
    for d in defs:
        entry = baseline.lookup(d.type, d.id)
        if entry is None:
            continue
        key = (d.type, normalize_id(d.id), d.location)
        if key in seen:
            continue
        seen.add(key)
        hits.append(StockIdHit(d, entry))
    return hits


def _versions_text(versions: Sequence[str]) -> str:
    return ", ".join(sorted(versions, key=version_sort_key))


def format_hit(hit: StockIdHit) -> str:
    d, s = hit.definition, hit.stock
    label = type_label(d.type)
    own = f" ({d.name!r})" if d.name and d.name != s.name else ""
    return (
        f"{d.location}: {label} id {d.id}{own} is the id of the VCF Operations "
        f"stock {label} {s.name!r} (stock in {_versions_text(s.versions)}). "
        f"Installing this content overwrites that stock {label} and uninstalling "
        f"it deletes it. Give this definition an id of its own (mint a new "
        f"UUID; where the id derives from the name, rename it). Referencing the "
        f"stock {label} by id is fine: only definitions count."
    )


def check_definitions(
    defs: Iterable[Definition],
    *,
    baseline: StockBaseline,
    allowlist: Sequence[AllowlistEntry] = (),
    subject: str = "",
) -> GuardResult:
    """Check definitions against the baseline, honouring the allowlist.

    A hit not on the allowlist is an error. An allowlisted hit is a warning
    naming the reason, on every run. An allowlist entry that matches no
    definition is a warning too (stale entries must not linger).
    """
    defs = list(defs)
    result = GuardResult()
    allow = {(a.type, normalize_id(a.id)): a for a in allowlist}
    used = set()
    for hit in find_stock_hits(defs, baseline):
        key = (hit.definition.type, normalize_id(hit.definition.id))
        entry = allow.get(key)
        result.hits.append(hit)
        if entry is None:
            result.errors.append(format_hit(hit))
        else:
            used.add(key)
            result.allowed.append((hit, entry))
            result.warnings.append(
                f"ALLOWLISTED stock id: {hit.definition.location}: "
                f"{type_label(hit.definition.type)} {hit.definition.id} is the stock "
                f"{type_label(hit.stock.type)} {hit.stock.name!r} (stock in "
                f"{_versions_text(hit.stock.versions)}); shipped anyway because "
                f"{entry.where or 'the allowlist'} says: {entry.reason}. Installing "
                f"overwrites the stock object and uninstalling deletes it."
            )
    for key, entry in allow.items():
        if key not in used:
            what = f" for {subject}" if subject else ""
            result.warnings.append(
                f"{entry.where}: stock_id_allowlist entry {entry.type} {entry.id} "
                f"matches no definition{what}; remove it"
            )
    return result


def guard_failure_text(result: GuardResult, what: str) -> str:
    """One error block for a failed check, for build errors."""
    n = len(result.errors)
    head = (
        f"stock-id guard: {what} ships {n} definition(s) under VCF Operations "
        f"stock ids (issue #345):"
    )
    return "\n".join([head] + [f"  {e}" for e in result.errors])


def check_paths(paths: Sequence, baseline: StockBaseline) -> Tuple[List[str], int]:
    """Read-only report for the standalone check (third-party paks, exports).

    Returns ``(lines, hit_count)``: every distinct definition id in each of
    ``paths`` that is in the baseline (one line per id, naming every file
    that defines it), with per-type totals. ``hit_count`` counts distinct
    ``(type, id)`` per path.
    """
    lines: List[str] = []
    total = 0
    for p in paths:
        defs = scan_path(p)
        distinct: Dict[Tuple[str, str], List[Definition]] = {}
        for d in defs:
            distinct.setdefault((d.type, normalize_id(d.id)), []).append(d)
        hits: Dict[Tuple[str, str], Tuple[StockEntry, List[Definition]]] = {}
        for key, ds in distinct.items():
            entry = baseline.lookup(key[0], key[1])
            if entry is not None:
                hits[key] = (entry, ds)
        lines.append(f"{p}:")
        summary = ", ".join(
            f"{type_label(t)}: {sum(1 for k in hits if k[0] == t)} stock of "
            f"{sum(1 for k in distinct if k[0] == t)}"
            for t in CONTENT_TYPES if any(k[0] == t for k in distinct)
        )
        lines.append(f"  distinct definition ids scanned: {summary or 'none'}")
        for t in CONTENT_TYPES:
            rows = sorted(((k, v) for k, v in hits.items() if k[0] == t),
                          key=lambda kv: (kv[1][0].name, kv[0][1]))
            for (_, _), (s, ds) in rows:
                shipped = sorted({d.name for d in ds if d.name and d.name != s.name})
                as_text = f" shipped as {shipped[0]!r}" if shipped else ""
                where = sorted({d.location for d in ds})
                more = f" (+{len(where) - 1} more)" if len(where) > 1 else ""
                lines.append(
                    f"  STOCK {type_label(t)} {ds[0].id} {s.name!r} "
                    f"[{_versions_text(s.versions)}]{as_text} in {where[0]}{more}"
                )
        total += len(hits)
    return lines, total
