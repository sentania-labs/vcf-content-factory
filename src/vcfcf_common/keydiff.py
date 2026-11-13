"""Key differential: compare stat and property keys of matching objects on two
VCF Operations instances (or two saved snapshots).

Read-only recon tooling (vCommunity Java port design, section 11, toolset gap
T5). Every Suite API call is a GET; nothing is created, changed, or deleted.
The only non-GET request is the token acquire the shared client makes to log
in.

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
for objects present on one side. Numbers compare within ``--tolerance``
(absolute) or ``--rel-tolerance`` (relative to the larger magnitude),
whichever is wider; property values compare as strings, or as numbers when both
parse as finite numbers (``"1"`` equals ``"1.0"``), without tolerance.

Exit status: 0 nothing differs (stale rows do not count), 1 a difference was
found, 2 usage error, 3 a fetch or snapshot read failed.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

SNAPSHOT_FORMAT = "vcfcf-keydiff-snapshot/1"

VMWARE = "VMWARE"
VCID = "VMEntityVCID"
MOID = "VMEntityObjectID"

PAGE_SIZE = 1000
IDS_PER_GET = 50

CATEGORIES = ("object_only_a", "object_only_b", "only_a", "only_b", "differ",
              "stale", "match")
DIFFERENCES = {"object_only_a", "object_only_b", "only_a", "only_b", "differ"}

TSV_COLUMNS = ("category", "kind", "identity", "object_a", "object_b",
               "resource_kind", "key", "value_a", "value_b", "delta", "ts_a",
               "ts_b")


class KeydiffError(RuntimeError):
    """A fetch or snapshot problem; the CLI exits 3."""


# ---------------------------------------------------------------------------
# Fetch (GET only)
# ---------------------------------------------------------------------------

def _get_json(client: Any, path: str, params: Optional[List[Tuple[str, Any]]] = None) -> Any:
    """GET ``path`` and return the parsed JSON body. The only request verb used."""
    r = client._request("GET", path, params=params or [])
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

def _as_number(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    elif isinstance(v, str):
        try:
            f = float(v.strip())
        except ValueError:
            return None
    else:
        return None
    return f if math.isfinite(f) else None


def _numbers_close(a: float, b: float, tol: float, rel: float) -> bool:
    return abs(a - b) <= max(tol, rel * max(abs(a), abs(b)))


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


def compare(a: dict, b: dict, *, tolerance: float = 0.0, rel_tolerance: float = 0.0,
            stale_hours: Optional[float] = None,
            key_prefixes: Sequence[str] = ()) -> dict:
    """Compare two snapshots. Returns ``{"rows", "counts", "unidentified"}``."""
    ia, amb_a = _index(a, "a")
    ib, amb_b = _index(b, "b")
    window_ms = None if stale_hours is None else stale_hours * 3600_000.0
    now_a = a.get("captured_at") or 0
    now_b = b.get("captured_at") or 0
    rows: List[dict] = []

    def row(category: str, ident: Tuple[str, ...], oa: Optional[dict], ob: Optional[dict],
            kind: str = "", key: str = "", va: Any = None, vb: Any = None,
            delta: Optional[float] = None, ts_a: Any = None, ts_b: Any = None) -> None:
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
                na, nb = _as_number(va), _as_number(vb)
                delta = None
                if na is not None and nb is not None:
                    delta = nb - na
                    if kind == "stat":
                        same = _numbers_close(na, nb, tolerance, rel_tolerance)
                    else:
                        same = na == nb
                else:
                    same = va == vb
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
    return {"rows": rows, "counts": counts, "unidentified": unidentified}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    s = str(v)
    # One row per line, one cell per tab: never let a value break the shape.
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


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
    if result["unidentified"]:
        out.append(f"not compared: {len(result['unidentified'])} object(s) without a"
                   " stable identity (listed below)")
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
            out.append(f"  [{u.get('side')}] {u.get('resource_kind')} {u.get('name')!r}"
                       f" ({u.get('resource_id')}): {u.get('reason')}")
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m vcfcf_common keydiff",
        description=("Compare stat and property keys and latest values of matching"
                     " objects on two VCF Operations instances or snapshots."
                     " Read-only: GET requests only."),
    )
    p.add_argument("--profile", action=_SideAction, dest="sides", metavar="NAME",
                   help="a live side: credential profile from .env (VCFOPS_<NAME>_*)."
                        " Give twice, or once with --snapshot-in.")
    p.add_argument("--snapshot-in", action=_SideAction, dest="sides", metavar="FILE",
                   help="a saved side, written earlier with --snapshot-out")
    p.add_argument("--snapshot-out", metavar="FILE",
                   help="with exactly one live side: write its snapshot and stop")
    p.add_argument("--adapter-kind", metavar="KEY", help="scope: adapter kind (e.g. VMWARE)")
    p.add_argument("--b-adapter-kind", metavar="KEY",
                   help="adapter kind for side B (the second side) when it is live and its"
                        " adapter kind differs (e.g. a port that renamed its kind)")
    p.add_argument("--resource-kind", metavar="KEY", help="scope: resource kind")
    p.add_argument("--name", action="append", default=[], metavar="NAME",
                   help="scope: an object name (repeatable), exact match")
    p.add_argument("--key-prefix", action="append", default=[], metavar="PREFIX",
                   help="only keys starting with PREFIX (repeatable), e.g. 'vCommunity|'")
    p.add_argument("--tolerance", type=float, default=0.0,
                   help="absolute tolerance for numeric stats (default 0)")
    p.add_argument("--rel-tolerance", type=float, default=0.0,
                   help="relative tolerance for numeric stats, of the larger magnitude"
                        " (default 0)")
    p.add_argument("--stale-hours", type=float, default=None,
                   help="a stat sampled longer ago than this before its side's capture"
                        " is reported stale, not compared (properties are exempt: they"
                        " are stored only on change)")
    p.add_argument("--format", choices=("table", "tsv"), default="table",
                   help="stdout format (default table)")
    p.add_argument("--tsv-out", metavar="FILE", help="also write every row as TSV")
    p.add_argument("--show-matches", action="store_true",
                   help="table: list matching keys too (TSV always does)")
    return p


def _client_for_profile(profile: str) -> Any:
    from .client import VCFOpsClient  # noqa: PLC0415
    return VCFOpsClient.from_env(profile=profile)


def _live_side(profile: str, args: argparse.Namespace, adapter_kind: Optional[str],
               client_factory: Callable[[str], Any]) -> dict:
    client = client_factory(profile)
    host = getattr(client, "base", "")
    return capture(client, adapter_kind=adapter_kind, resource_kind=args.resource_kind,
                   names=args.name, key_prefixes=args.key_prefix,
                   source={"profile": profile, "base": host})


def main(argv: Optional[Sequence[str]] = None,
         client_factory: Callable[[str], Any] = _client_for_profile) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0) if e.code in (0, None) else 2
    sides = list(args.sides or [])
    live = [s for s in sides if s[0] == "profile"]

    def usage(msg: str) -> int:
        print(f"keydiff: {msg}", file=sys.stderr)
        return 2

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
        if not math.isfinite(v) or v < 0:
            return usage(f"--{opt.replace('_', '-')} must be a finite number >= 0")
    if args.stale_hours is not None and (not math.isfinite(args.stale_hours)
                                         or args.stale_hours <= 0):
        return usage("--stale-hours must be a finite number > 0")

    try:
        docs: List[dict] = []
        for i, (kind, value) in enumerate(sides):
            if kind == "snapshot":
                docs.append(load_snapshot(value))
                continue
            ak = args.b_adapter_kind if (i == 1 and args.b_adapter_kind) else args.adapter_kind
            docs.append(_live_side(value, args, ak, client_factory))
    except KeydiffError as e:
        print(f"keydiff: {e}", file=sys.stderr)
        return 3
    except Exception as e:  # credential or transport failure from the client
        print(f"keydiff: {type(e).__name__}: {e}", file=sys.stderr)
        return 3

    if args.snapshot_out:
        doc = docs[0]
        write_snapshot(doc, args.snapshot_out)
        print(f"keydiff: wrote {len(doc['objects'])} object(s)"
              f" ({len(doc['unidentified'])} without a stable identity) to"
              f" {args.snapshot_out}")
        return 0

    result = compare(docs[0], docs[1], tolerance=args.tolerance,
                     rel_tolerance=args.rel_tolerance, stale_hours=args.stale_hours,
                     key_prefixes=args.key_prefix)
    if args.tsv_out:
        with open(args.tsv_out, "w", encoding="utf-8") as fh:
            fh.write(to_tsv(result))
    sys.stdout.write(to_tsv(result) if args.format == "tsv"
                     else to_table(result, show_matches=args.show_matches))
    return 1 if any(result["counts"][c] for c in DIFFERENCES) else 0


if __name__ == "__main__":
    raise SystemExit(main())
