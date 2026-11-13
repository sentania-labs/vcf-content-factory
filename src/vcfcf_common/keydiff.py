"""Key differential: compare stat and property keys of matching objects on two
VCF Operations instances (or two saved snapshots).

Read-only recon tooling, for checking that a port of a management pack
reports the same keys and values as the original. Every Suite API read is a
GET; nothing is created, changed, or deleted. The only other requests are the
login of each live side: ``POST /api/auth/token/acquire`` and, when the side
is done, ``POST /api/auth/token/release``. Every request has a timeout
(``--timeout``, default 60 s).

    python3 -m vcfcf_common keydiff --profile devel --profile devel_9_1 \\
        --adapter-kind VMWARE --resource-kind HostSystem --key-prefix 'vCommunity|'

    # capture one side now, the other later, compare offline
    python3 -m vcfcf_common keydiff --profile devel --adapter-kind VMWARE \\
        --resource-kind HostSystem --snapshot-out a.json
    python3 -m vcfcf_common keydiff --snapshot-in a.json --snapshot-in b.json

Sides are given in order with ``--profile NAME`` (live) or ``--snapshot-in
FILE``; the first is A, the second B. One side plus ``--snapshot-out`` only
captures; two sides compare.

What is read, per object in scope:
  * ``GET /api/resources`` (paged) for the objects: by adapter and resource
    kind, or one ``name=`` lookup per requested name (exact match kept).
  * ``GET /api/resources/stats/latest?resourceId=...`` (no ``statKey``: every
    stat), the last sample of each with its timestamp.
  * ``GET /api/resources/properties?resourceId=...``: every property's current
    value. Properties are stored only on change
    (``knowledge/context/api-surface/suite_api_batch_push.md``), so their age
    says nothing about freshness and the staleness window applies to stats only.

Matching objects across instances uses stable identifiers, never a bare name
where one exists:
  * ``VMWARE`` objects: vCenter instance UUID (``VMEntityVCID``) plus MOID
    (``VMEntityObjectID``); MOIDs repeat across vCenters
    (``knowledge/lessons/stitch-moid-not-unique-across-vcenters.md``). A
    ``VMWARE`` object without both is reported unidentified and not compared;
    it never falls back to its name.
  * Every other adapter kind: resource kind plus name (the adapter kind is not
    part of the identity, so a port that renames its adapter kind still matches;
    use ``--b-adapter-kind`` for the second side's scope).
  * Two objects with the same identity on one side are ambiguous: both are
    reported and neither is compared.

Results per (object, key): ``only_a``, ``only_b``, ``differ``, ``match``,
``stale`` (a stat whose sample on either side is older than ``--stale-hours``
before that side's capture), plus ``object_only_a`` / ``object_only_b`` rows
for objects present on one side.

How values compare. Every numeric comparison is exact, in ``Decimal``; no value
is rounded through a binary float on its way to a verdict or to the output:
  * A value is numeric when it is a JSON number (not a boolean) or a string
    that is a plain decimal: an optional sign, digits, and optionally a point
    and more digits (``5``, ``-5.0``, ``+0.25``). A JSON integer is exact at any
    size; a JSON fraction is the double the instance sent (Suite API stat
    values are doubles) and compares as that double's shortest decimal
    (``repr``), so two different doubles never compare equal.
  * Everything else compares as itself, exactly: other strings, ``true`` /
    ``false`` (a JSON boolean never equals a number), empty strings,
    ``NaN`` / ``Infinity`` in any spelling, exponent forms (``1E3``), values
    with leading or trailing whitespace, thousands separators (``1,000``), and
    ``null``. ``"NaN"`` equals ``"NaN"``; ``"1E3"`` does not equal ``"1000"``;
    ``" 5"`` does not equal ``"5"``.
  * Properties: equal when the strings are identical or both are plain
    decimals with the same value (``"5"`` equals ``"5.0"``;
    ``"9007199254740992"`` does not equal ``"9007199254740993"``). No tolerance
    ever applies to a property.
  * Stats: equal when numerically equal, or when the exact difference is
    within ``--tolerance`` (absolute) or ``--rel-tolerance`` (of the larger
    magnitude), whichever is wider. A row matched within tolerance is still a
    ``match``; its ``delta`` column shows the nonzero difference, which is how
    to tell it from an identical value.
  * ``delta`` is B minus A, exact. ``value_a`` and ``value_b`` are the values
    as read, never re-rendered through a float.
  * Exact means no rounding anywhere: ``--tolerance`` and ``--rel-tolerance``
    are read as ``Decimal`` from their text; magnitudes use the context-free
    ``copy_abs``; subtraction and the relative-tolerance product run in one
    local context whose precision is computed from the operands, with the
    ``Inexact`` and ``Rounded`` traps on, so a rounding there raises (exit 6)
    instead of changing a verdict. Comparisons and ``max`` order Decimals
    exactly at any precision.

Every run reports what it compared: objects on each side and on both, keys
on each side and on both (and how many of those were stale), and objects not
compared (no stable identity, or ambiguous). In ``--format tsv`` that summary
goes to stderr so stdout stays TSV.

Exit status, checked in this order:
  2  usage error.
  3  a fetch or snapshot read failed.
  4  nothing was compared: no object is on both sides, no key is on both sides
     of a matched object (an empty scope, a ``--key-prefix`` that matches
     nothing, every object unidentified), or every key on both sides is stale.
  1  a difference was found (an object or key on one side only, or a value
     that differs).
  5  no difference among what was compared, but some objects were not
     compared: a VMWARE object without both identifiers, or two objects with
     one identity.
  0  objects and keys were compared, nothing differs, and every object was
     compared. Stale rows do not count as differences.
  6  internal error: an exact numeric comparison could not be completed (a
     rounding trap fired). Never reported as a match.

Snapshot files (``--snapshot-out``) hold what the instance returned for the
objects in scope: object names, resource ids, keys and their values (guest
names, IP addresses, annotations, anything a property carries). They hold the
profile name and Suite API base URL of the side, and no credentials or token.
Treat them as you would an export of the instance.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from decimal import (MAX_EMAX, MIN_EMIN, Context, Decimal, DecimalException, Inexact,
                     InvalidOperation, Rounded, localcontext)
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

SNAPSHOT_FORMAT = "vcfcf-keydiff-snapshot/1"

VMWARE = "VMWARE"
VCID = "VMEntityVCID"
MOID = "VMEntityObjectID"

PAGE_SIZE = 1000
IDS_PER_GET = 50

# Seconds per request (token acquire, GETs and release); --timeout overrides.
REQUEST_TIMEOUT_DEFAULT = 60.0

EXIT_OK = 0
EXIT_DIFFER = 1
EXIT_USAGE = 2
EXIT_FETCH = 3
EXIT_NOTHING_COMPARED = 4
EXIT_NOT_COMPARED = 5
EXIT_INTERNAL = 6

CATEGORIES = ("object_only_a", "object_only_b", "only_a", "only_b", "differ",
              "stale", "match")
DIFFERENCES = {"object_only_a", "object_only_b", "only_a", "only_b", "differ"}
# Key rows whose key is on both sides of a matched object.
KEYS_ON_BOTH = {"differ", "stale", "match"}

TSV_COLUMNS = ("category", "kind", "identity", "object_a", "object_b",
               "resource_kind", "key", "value_a", "value_b", "delta", "ts_a",
               "ts_b")


class KeydiffError(RuntimeError):
    """A fetch or snapshot problem; the CLI exits 3."""


# ---------------------------------------------------------------------------
# Fetch (GET only)
# ---------------------------------------------------------------------------

def _get_json(client: Any, path: str, params: Optional[List[Tuple[str, Any]]] = None) -> Any:
    """GET ``path`` and return the parsed JSON body. The only read verb used.

    The request carries the client's ``keydiff_timeout`` (set by
    :func:`_client_for_profile`), so a stalled instance cannot hang the CLI.
    """
    timeout = getattr(client, "keydiff_timeout", None)
    extra = {} if timeout is None else {"timeout": timeout}
    r = client._request("GET", path, params=params or [], **extra)
    if r.status_code != 200:
        raise KeydiffError(f"GET {path} returned HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as e:
        raise KeydiffError(f"GET {path} did not return JSON: {e}") from None


def _paged_resources(client: Any, params: List[Tuple[str, Any]]) -> List[dict]:
    out: List[dict] = []
    page = 0
    while True:
        body = _get_json(client, "/api/resources",
                         params + [("page", page), ("pageSize", PAGE_SIZE)])
        rows = body.get("resourceList") or []
        out.extend(rows)
        total = (body.get("pageInfo") or {}).get("totalCount")
        if not rows or not isinstance(total, int) or len(out) >= total:
            return out
        page += 1


def fetch_resources(client: Any, adapter_kind: Optional[str],
                    resource_kind: Optional[str],
                    names: Sequence[str]) -> List[dict]:
    """Resources in scope: by kind, or one ``name=`` lookup per name (exact
    names kept, since the server's name match is not documented as exact)."""
    base: List[Tuple[str, Any]] = []
    if adapter_kind:
        base.append(("adapterKind", adapter_kind))
    if resource_kind:
        base.append(("resourceKind", resource_kind))
    if not names:
        return _paged_resources(client, base)
    seen = set()
    out: List[dict] = []
    for name in names:
        for r in _paged_resources(client, base + [("name", name)]):
            if (r.get("resourceKey") or {}).get("name") != name:
                continue
            rid = r.get("identifier")
            if rid in seen:
                continue
            seen.add(rid)
            out.append(r)
    return out


def _chunks(seq: Sequence[str], n: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_latest_stats(client: Any, ids: Sequence[str]) -> Dict[str, Dict[str, dict]]:
    """resourceId -> statKey -> {"value", "ts"} (last sample of every stat)."""
    out: Dict[str, Dict[str, dict]] = {}
    for part in _chunks(list(ids), IDS_PER_GET):
        body = _get_json(client, "/api/resources/stats/latest",
                         [("resourceId", i) for i in part] + [("maxSamples", 1)])
        for entry in body.get("values") or []:
            rid = entry.get("resourceId")
            stats = out.setdefault(rid, {})
            for st in ((entry.get("stat-list") or {}).get("stat") or []):
                key = (st.get("statKey") or {}).get("key")
                ts_list = st.get("timestamps") or []
                data = st.get("data")
                vals = st.get("values")
                if not key or not ts_list:
                    continue
                if data:
                    value: Any = data[-1]
                elif vals:
                    value = vals[-1]
                else:
                    continue
                stats[key] = {"value": value, "ts": ts_list[-1]}
    return out


def fetch_properties(client: Any, ids: Sequence[str]) -> Dict[str, Dict[str, dict]]:
    """resourceId -> property key -> {"value"} (current values, no timestamps)."""
    out: Dict[str, Dict[str, dict]] = {}
    for part in _chunks(list(ids), IDS_PER_GET):
        body = _get_json(client, "/api/resources/properties",
                         [("resourceId", i) for i in part])
        for entry in body.get("resourcePropertiesList") or []:
            rid = entry.get("resourceId")
            props = out.setdefault(rid, {})
            for p in entry.get("property") or []:
                name = p.get("name")
                if name is not None:
                    props[name] = {"value": p.get("value")}
    return out


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def _identifiers(resource: dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for ident in (resource.get("resourceKey") or {}).get("resourceIdentifiers") or []:
        name = (ident.get("identifierType") or {}).get("name")
        if name:
            out[name] = ident.get("value")
    return out


def identity_of(resource: dict) -> Tuple[Optional[List[str]], Optional[str]]:
    """``(identity, None)`` or ``(None, reason)`` when no stable identity exists.

    VMWARE: ``["vcenter_moid", resourceKind, VCID, MOID]``. Others:
    ``["kind_name", resourceKind, name]``.
    """
    key = resource.get("resourceKey") or {}
    ak = key.get("adapterKindKey")
    rk = key.get("resourceKindKey")
    if ak == VMWARE:
        ids = _identifiers(resource)
        vcid = (ids.get(VCID) or "").strip()
        moid = (ids.get(MOID) or "").strip()
        if not vcid or not moid:
            return None, (f"VMWARE object without {VCID} and {MOID}; not matched by"
                          " name")
        return ["vcenter_moid", rk, vcid.lower(), moid], None
    name = key.get("name")
    if not name:
        return None, "object without a name"
    return ["kind_name", rk, name], None


def identity_label(identity: Sequence[str]) -> str:
    if identity[0] == "vcenter_moid":
        return f"vc={identity[2]} moid={identity[3]}"
    return f"kind={identity[1]} name={identity[2]}"


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def _key_kept(key: str, prefixes: Sequence[str]) -> bool:
    return not prefixes or any(key.startswith(p) for p in prefixes)


def capture(client: Any, *, adapter_kind: Optional[str], resource_kind: Optional[str],
            names: Sequence[str], key_prefixes: Sequence[str], source: Dict[str, Any],
            now_ms: Optional[int] = None) -> dict:
    """Read one side and return its snapshot document."""
    captured_at = int(time.time() * 1000) if now_ms is None else now_ms
    resources = fetch_resources(client, adapter_kind, resource_kind, names)
    ids = [r.get("identifier") for r in resources if r.get("identifier")]
    stats = fetch_latest_stats(client, ids) if ids else {}
    props = fetch_properties(client, ids) if ids else {}
    objects: List[dict] = []
    unidentified: List[dict] = []
    for r in resources:
        key = r.get("resourceKey") or {}
        rid = r.get("identifier")
        base = {
            "name": key.get("name"),
            "adapter_kind": key.get("adapterKindKey"),
            "resource_kind": key.get("resourceKindKey"),
            "resource_id": rid,
        }
        ident, why = identity_of(r)
        if ident is None:
            unidentified.append(dict(base, reason=why))
            continue
        objects.append(dict(
            base,
            identity=ident,
            stats={k: v for k, v in sorted((stats.get(rid) or {}).items())
                   if _key_kept(k, key_prefixes)},
            properties={k: v for k, v in sorted((props.get(rid) or {}).items())
                        if _key_kept(k, key_prefixes)},
        ))
    return {
        "format": SNAPSHOT_FORMAT,
        "captured_at": captured_at,
        "source": source,
        "scope": {
            "adapter_kind": adapter_kind,
            "resource_kind": resource_kind,
            "names": list(names),
            "key_prefixes": list(key_prefixes),
        },
        "objects": objects,
        "unidentified": unidentified,
    }


def load_snapshot(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as e:
        raise KeydiffError(f"cannot read snapshot {path}: {e}") from None
    if not isinstance(doc, dict) or doc.get("format") != SNAPSHOT_FORMAT:
        raise KeydiffError(f"{path} is not a {SNAPSHOT_FORMAT} snapshot")
    for o in doc.get("objects") or []:
        if not isinstance(o.get("identity"), list):
            raise KeydiffError(f"{path}: an object has no identity")
    return doc


def write_snapshot(doc: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

# A plain decimal: optional sign, digits, optionally a point and digits. No
# whitespace, exponent, separator, or NaN/Infinity spelling (those compare as
# strings; module docstring, "How values compare").
_PLAIN_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")


def _as_decimal(v: Any) -> Optional[Decimal]:
    """The exact numeric value of ``v``, or None when it is not numeric.

    ints are exact; a float (a double from the JSON) becomes its shortest
    round-trip decimal, so distinct doubles stay distinct; a string counts only
    when it is a plain decimal (``_PLAIN_DECIMAL``, ASCII digits only)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v)) if math.isfinite(v) else None
    if isinstance(v, str) and _PLAIN_DECIMAL.fullmatch(v):
        return Decimal(v)
    return None


def _digits(v: Decimal) -> int:
    return len(v.as_tuple().digits)


def _exact_context(a: Decimal, b: Decimal, rel: Optional[Decimal] = None) -> Context:
    """A context in which ``b - a`` and ``rel * max(|a|, |b|)`` are exact.

    A difference needs every digit from the highest place of either operand to
    the lowest, plus one for a carry; a product needs at most the digits of
    both factors. The exponent range is the widest there is, and ``Inexact``
    and ``Rounded`` are trapped (with the default traps), so if a precision
    here is ever too small the operation raises rather than rounds."""
    prec = 1
    nonzero = [v for v in (a, b) if v]
    if nonzero:
        top = max(v.adjusted() for v in nonzero)
        bottom = min(v.as_tuple().exponent for v in (a, b))
        prec = top - bottom + 2
    if rel is not None:
        prec = max(prec, _digits(rel) + max(_digits(a), _digits(b)) + 1)
    ctx = Context(prec=max(prec, 1), Emax=MAX_EMAX, Emin=MIN_EMIN)
    ctx.traps[Inexact] = True
    ctx.traps[Rounded] = True
    return ctx


def _delta(a: Decimal, b: Decimal) -> Decimal:
    """``b - a``, exact (module docstring, "How values compare")."""
    with localcontext(_exact_context(a, b)):
        return b - a


def _within(a: Decimal, b: Decimal, tol: Decimal, rel: Decimal) -> bool:
    """``|b - a| <= max(tol, rel * max(|a|, |b|))``, computed exactly.

    ``copy_abs`` is context-free; the subtraction and the product run in one
    exact, trapping context. ``==``, ``<=`` and ``max`` never round."""
    if a == b:
        return True
    with localcontext(_exact_context(a, b, rel)):
        diff = (b - a).copy_abs()
        big = max(a.copy_abs(), b.copy_abs())
        allowed = max(tol, rel * big)
        return diff <= allowed


def _same_raw(va: Any, vb: Any) -> bool:
    """Equality for values that are not both numeric: same type family and
    equal (a boolean never equals a number; non-finite floats compare by
    spelling, so NaN equals NaN)."""
    if isinstance(va, bool) or isinstance(vb, bool):
        return isinstance(va, bool) and isinstance(vb, bool) and va == vb
    if isinstance(va, float) and isinstance(vb, float):
        return repr(va) == repr(vb)
    return type(va) is type(vb) and va == vb


def _tol_decimal(v: Any) -> Decimal:
    d = _as_decimal(v) if not isinstance(v, Decimal) else v
    if d is None or not d.is_finite():
        raise ValueError(f"tolerance must be a finite number, not {v!r}")
    return d


def _index(doc: dict, label: str) -> Tuple[Dict[Tuple[str, ...], dict], List[dict]]:
    """identity -> object; duplicates (ambiguous) are returned separately."""
    by_id: Dict[Tuple[str, ...], List[dict]] = {}
    for o in doc.get("objects") or []:
        by_id.setdefault(tuple(o["identity"]), []).append(o)
    unique: Dict[Tuple[str, ...], dict] = {}
    ambiguous: List[dict] = []
    for ident, objs in by_id.items():
        if len(objs) == 1:
            unique[ident] = objs[0]
        else:
            for o in objs:
                ambiguous.append(dict(side=label, name=o.get("name"),
                                      resource_kind=o.get("resource_kind"),
                                      resource_id=o.get("resource_id"),
                                      reason=f"{len(objs)} objects share {identity_label(ident)}"))
    return unique, ambiguous


def compare(a: dict, b: dict, *, tolerance: Any = 0.0, rel_tolerance: Any = 0.0,
            stale_hours: Optional[float] = None,
            key_prefixes: Sequence[str] = ()) -> dict:
    """Compare two snapshots. Returns ``{"rows", "counts", "unidentified"}``.

    ``tolerance`` and ``rel_tolerance`` (int, float or Decimal; a float is
    taken as its shortest decimal, so 0.1 is exactly 0.1) apply to stats only.
    ``delta`` in each row is a Decimal (module docstring, "How values compare").
    """
    tol = _tol_decimal(tolerance)
    rel = _tol_decimal(rel_tolerance)
    ia, amb_a = _index(a, "a")
    ib, amb_b = _index(b, "b")
    window_ms = None if stale_hours is None else stale_hours * 3600_000.0
    now_a = a.get("captured_at") or 0
    now_b = b.get("captured_at") or 0
    rows: List[dict] = []

    def row(category: str, ident: Tuple[str, ...], oa: Optional[dict], ob: Optional[dict],
            kind: str = "", key: str = "", va: Any = None, vb: Any = None,
            delta: Optional[Decimal] = None, ts_a: Any = None, ts_b: Any = None) -> None:
        rows.append({
            "category": category,
            "kind": kind,
            "identity": identity_label(ident),
            "object_a": (oa or {}).get("name"),
            "object_b": (ob or {}).get("name"),
            "resource_kind": (oa or ob or {}).get("resource_kind"),
            "key": key,
            "value_a": va,
            "value_b": vb,
            "delta": delta,
            "ts_a": ts_a,
            "ts_b": ts_b,
        })

    for ident in sorted(set(ia) | set(ib)):
        oa, ob = ia.get(ident), ib.get(ident)
        if oa is None:
            row("object_only_b", ident, None, ob)
            continue
        if ob is None:
            row("object_only_a", ident, oa, None)
            continue
        for kind, field in (("stat", "stats"), ("property", "properties")):
            ka = {k: v for k, v in (oa.get(field) or {}).items() if _key_kept(k, key_prefixes)}
            kb = {k: v for k, v in (ob.get(field) or {}).items() if _key_kept(k, key_prefixes)}
            for key in sorted(set(ka) | set(kb)):
                ea, eb = ka.get(key), kb.get(key)
                va = None if ea is None else ea.get("value")
                vb = None if eb is None else eb.get("value")
                ta = None if ea is None else ea.get("ts")
                tb = None if eb is None else eb.get("ts")
                if ea is None:
                    row("only_b", ident, oa, ob, kind, key, None, vb, None, None, tb)
                    continue
                if eb is None:
                    row("only_a", ident, oa, ob, kind, key, va, None, None, ta, None)
                    continue
                na, nb = _as_decimal(va), _as_decimal(vb)
                delta = None
                if va == vb and type(va) is type(vb) and not isinstance(va, float):
                    same = True  # identical (strings, ints, booleans, null)
                    if na is not None:
                        delta = Decimal(0)
                elif na is not None and nb is not None:
                    delta = _delta(na, nb)
                    if kind == "stat":
                        same = _within(na, nb, tol, rel)
                    else:
                        same = na == nb
                else:
                    same = _same_raw(va, vb)
                stale = (kind == "stat" and window_ms is not None
                         and ((isinstance(ta, (int, float)) and now_a - ta > window_ms)
                              or (isinstance(tb, (int, float)) and now_b - tb > window_ms)))
                category = "stale" if stale else ("match" if same else "differ")
                row(category, ident, oa, ob, kind, key, va, vb, delta, ta, tb)

    counts = {c: 0 for c in CATEGORIES}
    for r in rows:
        counts[r["category"]] += 1
    unidentified = ([dict(u, side="a") for u in a.get("unidentified") or []]
                    + [dict(u, side="b") for u in b.get("unidentified") or []]
                    + amb_a + amb_b)
    both = set(ia) & set(ib)
    keys_a = sum(1 for r in rows if r["category"] in KEYS_ON_BOTH | {"only_a"})
    keys_b = sum(1 for r in rows if r["category"] in KEYS_ON_BOTH | {"only_b"})
    keys_both = sum(1 for r in rows if r["category"] in KEYS_ON_BOTH)
    compared = {
        "objects_a": len(ia),
        "objects_b": len(ib),
        "objects_both": len(both),
        "keys_a": keys_a,
        "keys_b": keys_b,
        "keys_both": keys_both,
        "keys_stale": counts["stale"],
        "not_compared_a": sum(1 for u in unidentified if u.get("side") == "a"),
        "not_compared_b": sum(1 for u in unidentified if u.get("side") == "b"),
    }
    return {"rows": rows, "counts": counts, "unidentified": unidentified,
            "compared": compared}


def exit_code(result: dict) -> int:
    """The CLI's exit status for a comparison (module docstring, in order)."""
    c = result["compared"]
    if c["objects_both"] == 0 or c["keys_both"] == 0 or c["keys_stale"] == c["keys_both"]:
        return EXIT_NOTHING_COMPARED
    if any(result["counts"][k] for k in DIFFERENCES):
        return EXIT_DIFFER
    if result["unidentified"]:
        return EXIT_NOT_COMPARED
    return EXIT_OK


def compared_line(result: dict) -> str:
    """One line saying what was compared, for every run."""
    c = result["compared"]
    nc = c["not_compared_a"] + c["not_compared_b"]
    return (f"compared: objects a={c['objects_a']} b={c['objects_b']}"
            f" on both={c['objects_both']}; keys a={c['keys_a']} b={c['keys_b']}"
            f" on both={c['keys_both']} (stale {c['keys_stale']});"
            f" objects not compared: {nc} (a={c['not_compared_a']}"
            f" b={c['not_compared_b']})")


def verdict_line(result: dict) -> str:
    """Why the run exits as it does, in words."""
    code = exit_code(result)
    c = result["compared"]
    if code == EXIT_NOTHING_COMPARED:
        if c["objects_both"] == 0:
            why = "no object is on both sides"
        elif c["keys_both"] == 0:
            why = "no key is on both sides of a matched object"
        else:
            why = "every key on both sides is stale"
        return f"result: NOTHING COMPARED ({why}); exit {code}"
    if code == EXIT_DIFFER:
        return f"result: differences found; exit {code}"
    if code == EXIT_NOT_COMPARED:
        return (f"result: no differences among what was compared, but"
                f" {len(result['unidentified'])} object(s) were not compared; exit {code}")
    return f"result: no differences; exit {code}"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

_NAMED_ESCAPES = {"\\": "\\\\", "\t": "\\t", "\r": "\\r", "\n": "\\n"}


def _escape_char(ch: str) -> str:
    if ch in _NAMED_ESCAPES:
        return _NAMED_ESCAPES[ch]
    o = ord(ch)
    # C0 (ESC included), DEL, C1, and format/separator characters that a
    # terminal acts on or hides (bidi overrides, zero-width, U+2028/9).
    if o < 0x20 or o == 0x7F or 0x80 <= o <= 0x9F or unicodedata.category(ch) in (
            "Cf", "Zl", "Zp"):
        return f"\\x{o:02x}" if o <= 0xFF else f"\\u{o:04x}" if o <= 0xFFFF else f"\\U{o:08x}"
    return ch


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)  # the double as read: shortest round-trip, never rounded
    if isinstance(v, Decimal):
        # A delta: exact, positional notation, no float in between.
        return "0" if v == 0 else format(v, "f")
    s = str(v)
    # One row per line, one cell per tab, and nothing the terminal would act
    # on: never let a value from the instance break the shape or the screen.
    return "".join(_escape_char(ch) for ch in s)


def to_tsv(result: dict) -> str:
    lines = ["\t".join(TSV_COLUMNS)]
    for r in result["rows"]:
        lines.append("\t".join(_cell(r[c]) for c in TSV_COLUMNS))
    return "\n".join(lines) + "\n"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def to_table(result: dict, show_matches: bool = False, width: int = 40) -> str:
    cols = ("category", "kind", "identity", "key", "value_a", "value_b", "delta")
    shown = [r for r in result["rows"] if show_matches or r["category"] != "match"]
    cells = [[_truncate(_cell(r[c]), width) for c in cols] for r in shown]
    widths = [max([len(c)] + [len(row[i]) for row in cells]) for i, c in enumerate(cols)]
    out = []
    counts = result["counts"]
    out.append("summary: " + ", ".join(f"{c}={counts[c]}" for c in CATEGORIES))
    out.append(compared_line(result))
    out.append(verdict_line(result))
    if result["unidentified"]:
        out.append(f"not compared: {len(result['unidentified'])} object(s) without a"
                   " stable identity or with a shared one (listed below)")
    if cells:
        out.append("")
        out.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(cols)).rstrip())
        out.append("  ".join("-" * widths[i] for i in range(len(cols))))
        for row in cells:
            out.append("  ".join(row[i].ljust(widths[i]) for i in range(len(cols))).rstrip())
    elif not show_matches and counts["match"]:
        out.append("")
        out.append(f"no differences ({counts['match']} matching key(s); --show-matches"
                   " lists them)")
    if result["unidentified"]:
        out.append("")
        out.append("not compared:")
        for u in result["unidentified"]:
            out.append(f"  [{_cell(u.get('side'))}] {_cell(u.get('resource_kind'))}"
                       f" '{_cell(u.get('name'))}' ({_cell(u.get('resource_id'))}):"
                       f" {_cell(u.get('reason'))}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _SideAction(argparse.Action):
    """``--profile`` and ``--snapshot-in`` append to one ordered side list."""

    def __call__(self, parser, namespace, values, option_string=None):
        sides = list(getattr(namespace, "sides", None) or [])
        kind = "profile" if option_string == "--profile" else "snapshot"
        sides.append((kind, values))
        namespace.sides = sides


def _decimal_arg(text: str) -> Decimal:
    """A tolerance option, read as ``Decimal`` from its text (never a float)."""
    try:
        return Decimal(text.strip())
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m vcfcf_common keydiff",
        description=("Compare stat and property keys and latest values of matching"
                     " objects on two VCF Operations instances or snapshots."
                     " Read-only: reads are GETs; the only other requests are each"
                     " live side's login, POST /api/auth/token/acquire, and logout,"
                     " POST /api/auth/token/release."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("exit status (checked in this order):\n"
                "  2  usage error\n"
                "  3  a fetch or snapshot read failed\n"
                "  4  nothing compared: no object on both sides, no key on both sides,\n"
                "     or every key on both sides stale\n"
                "  1  a difference was found\n"
                "  5  no difference, but some objects were not compared (a VMWARE object\n"
                "     without VMEntityVCID and VMEntityObjectID, or a shared identity)\n"
                "  0  objects and keys compared, nothing differs, every object compared\n"
                "  6  internal error: an exact numeric comparison could not complete\n"
                "     (never reported as a match)\n"
                "\n"
                "Every run prints what it compared (objects and keys on each side and on\n"
                "both); with --format tsv that summary goes to stderr.\n"
                "\n"
                "values compare exactly (Decimal, never a rounded float):\n"
                "  numeric = a JSON number, or a string that is a plain decimal\n"
                "  ([+-]digits[.digits]); anything else (exponent forms, NaN, Infinity,\n"
                "  whitespace, thousands separators, booleans, empty) compares as a string\n"
                "  properties: identical strings, or plain decimals of equal value ('5'\n"
                "  equals '5.0'); no tolerance ever\n"
                "  stats: equal, or the exact difference within --tolerance or\n"
                "  --rel-tolerance; a tolerated match shows its nonzero delta\n"
                "  delta is B minus A, exact; values are shown as read"),
    )
    p.add_argument("--profile", action=_SideAction, dest="sides", metavar="NAME",
                   help="a live side: credential profile from .env (VCFOPS_<NAME>_*)."
                        " Give twice, or once with --snapshot-in.")
    p.add_argument("--snapshot-in", action=_SideAction, dest="sides", metavar="FILE",
                   help="a saved side, written earlier with --snapshot-out")
    p.add_argument("--snapshot-out", metavar="FILE",
                   help="with exactly one live side: write its snapshot and stop. The"
                        " file holds object names, resource ids, keys and values from"
                        " the instance (guest names, IP addresses, annotations), plus the"
                        " profile name and base URL; no credentials or token")
    p.add_argument("--adapter-kind", metavar="KEY", help="scope: adapter kind (e.g. VMWARE)")
    p.add_argument("--b-adapter-kind", metavar="KEY",
                   help="adapter kind for side B (the second side) when it is live and its"
                        " adapter kind differs (e.g. a port that renamed its kind); a usage"
                        " error when side B is a snapshot or there is no side B")
    p.add_argument("--resource-kind", metavar="KEY", help="scope: resource kind")
    p.add_argument("--name", action="append", default=[], metavar="NAME",
                   help="scope: an object name (repeatable), exact match")
    p.add_argument("--key-prefix", action="append", default=[], metavar="PREFIX",
                   help="only keys starting with PREFIX (repeatable), e.g. 'vCommunity|'")
    p.add_argument("--tolerance", type=_decimal_arg, default=Decimal(0),
                   help="absolute tolerance for numeric stats only (default 0). Never"
                        " applies to properties")
    p.add_argument("--rel-tolerance", type=_decimal_arg, default=Decimal(0),
                   help="relative tolerance for numeric stats only, of the larger"
                        " magnitude (default 0). Never applies to properties")
    p.add_argument("--stale-hours", type=float, default=None,
                   help="a stat sampled longer ago than this before its side's capture"
                        " is reported stale, not compared (properties are exempt: they"
                        " are stored only on change)")
    p.add_argument("--format", choices=("table", "tsv"), default="table",
                   help="stdout format (default table)")
    p.add_argument("--tsv-out", metavar="FILE", help="also write every row as TSV")
    p.add_argument("--show-matches", action="store_true",
                   help="table: list matching keys too (TSV always does)")
    p.add_argument("--timeout", type=float, default=REQUEST_TIMEOUT_DEFAULT,
                   metavar="SECONDS",
                   help="timeout for each request to a live side, token acquire and"
                        f" release included (default {REQUEST_TIMEOUT_DEFAULT:g})")
    return p


def _client_for_profile(profile: str) -> Any:
    from .client import VCFOpsClient  # noqa: PLC0415
    return VCFOpsClient.from_env(profile=profile)


def _apply_timeout(client: Any, timeout: float) -> None:
    """Bound every request this CLI makes through ``client``: the GETs read
    ``keydiff_timeout``; ``VCFOpsClient``'s token acquire reads
    ``_auth_timeout`` when set."""
    client.keydiff_timeout = timeout
    if hasattr(client, "_auth_timeout"):
        client._auth_timeout = timeout


def release_token(client: Any, timeout: Optional[float]) -> None:
    """Log the side out: ``POST /api/auth/token/release`` when the client
    holds a token. Never raises; a failure is one stderr line, never a body."""
    token = getattr(client, "_token", None)
    session = getattr(client, "_session", None)
    if not token or session is None:
        return
    extra = {} if timeout is None else {"timeout": timeout}
    try:
        r = session.post(f"{client.base}/api/auth/token/release", **extra)
        status = getattr(r, "status_code", None)
        if status is not None and not 200 <= status < 300:
            print(f"keydiff: token release returned HTTP {status} (ignored)", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 - logout must never mask the result
        print(f"keydiff: token release failed ({type(e).__name__}; ignored)", file=sys.stderr)
    finally:
        client._token = None


def _live_side(profile: str, args: argparse.Namespace, adapter_kind: Optional[str],
               client_factory: Callable[[str], Any]) -> dict:
    client = client_factory(profile)
    _apply_timeout(client, args.timeout)
    try:
        host = getattr(client, "base", "")
        return capture(client, adapter_kind=adapter_kind, resource_kind=args.resource_kind,
                       names=args.name, key_prefixes=args.key_prefix,
                       source={"profile": profile, "base": host})
    finally:
        release_token(client, args.timeout)


def main(argv: Optional[Sequence[str]] = None,
         client_factory: Callable[[str], Any] = _client_for_profile) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0) if e.code in (0, None) else EXIT_USAGE
    sides = list(args.sides or [])
    live = [s for s in sides if s[0] == "profile"]

    def usage(msg: str) -> int:
        print(f"keydiff: {msg}", file=sys.stderr)
        return EXIT_USAGE

    if not sides:
        return usage("give two sides (--profile and/or --snapshot-in), or one"
                     " --profile with --snapshot-out")
    if len(sides) > 2:
        return usage("at most two sides")
    if args.snapshot_out and (len(sides) != 1 or sides[0][0] != "profile"):
        return usage("--snapshot-out captures exactly one live side (one --profile)")
    if len(sides) == 1 and not args.snapshot_out:
        return usage("one side given: add a second side, or --snapshot-out to capture it")
    if live and not (args.name or (args.adapter_kind and args.resource_kind)):
        return usage("a live side needs a scope: --adapter-kind and --resource-kind,"
                     " or --name (optionally narrowed by kind)")
    for opt in ("tolerance", "rel_tolerance"):
        v = getattr(args, opt)
        if not v.is_finite() or v < 0:
            return usage(f"--{opt.replace('_', '-')} must be a finite number >= 0")
    if args.stale_hours is not None and (not math.isfinite(args.stale_hours)
                                         or args.stale_hours <= 0):
        return usage("--stale-hours must be a finite number > 0")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        return usage("--timeout must be a finite number > 0")
    if args.b_adapter_kind and (len(sides) < 2 or sides[1][0] != "profile"):
        return usage("--b-adapter-kind sets the scope of a live side B; side B is"
                     + (" a snapshot, whose scope was fixed when it was captured"
                        if len(sides) >= 2 else " not given"))

    try:
        docs: List[dict] = []
        for i, (kind, value) in enumerate(sides):
            if kind == "snapshot":
                docs.append(load_snapshot(value))
                continue
            ak = args.b_adapter_kind if (i == 1 and args.b_adapter_kind) else args.adapter_kind
            docs.append(_live_side(value, args, ak, client_factory))
    except KeydiffError as e:
        print(f"keydiff: {_cell(str(e))}", file=sys.stderr)
        return EXIT_FETCH
    except Exception as e:  # credential or transport failure from the client
        print(f"keydiff: {type(e).__name__}: {_cell(str(e))}", file=sys.stderr)
        return EXIT_FETCH

    if args.snapshot_out:
        doc = docs[0]
        write_snapshot(doc, args.snapshot_out)
        print(f"keydiff: wrote {len(doc['objects'])} object(s)"
              f" ({len(doc['unidentified'])} without a stable identity) to"
              f" {args.snapshot_out}")
        return EXIT_OK

    try:
        result = compare(docs[0], docs[1], tolerance=args.tolerance,
                         rel_tolerance=args.rel_tolerance, stale_hours=args.stale_hours,
                         key_prefixes=args.key_prefix)
    except DecimalException as e:  # a rounding trap: never let it become a verdict
        print(f"keydiff: internal error: exact comparison failed"
              f" ({type(e).__name__}); no result", file=sys.stderr)
        return EXIT_INTERNAL
    if args.tsv_out:
        with open(args.tsv_out, "w", encoding="utf-8") as fh:
            fh.write(to_tsv(result))
    if args.format == "tsv":
        sys.stdout.write(to_tsv(result))
        print(f"keydiff: {compared_line(result)}", file=sys.stderr)
        print(f"keydiff: {verdict_line(result)}", file=sys.stderr)
    else:
        sys.stdout.write(to_table(result, show_matches=args.show_matches))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
