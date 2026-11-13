"""Build a stock-id baseline from content exports (issue #345).

Pure: takes definitions already read from exports (``guard.scan_path``) plus
the exclusion evidence, returns the baseline as a dict and the ids it left
out. The factory CLI ``python3 -m vcfcf_packaging stock-id-baseline`` reads
the inputs and writes the files.

The hard part is purity. Lab instances hold factory content, third-party
content and content from installed paks next to the product's own. A
non-stock id in the baseline fails builds that are fine; a stock id missing
from it is a hole. When an id cannot be shown to be stock it is left out
and reported as a candidate, never guessed in.

How an id is decided (per content type and id):

1. Sources. ``Observation``s come from scope-ALL content exports taken on a
   clean instance (no pak under test installed), each tagged with the
   product version and an instance label, and optionally from id/name
   inventories (REST lists) of other instances. Definitions embedded in a
   policy export are not observations.

2. Exclusions. Any one of these keeps the id out:
   - a name marker: some observed name contains one of
     ``exclude_name_markers`` (the factory prefix, third-party tags);
   - an excluded adapter kind (the factory's and registered paks' kinds);
   - a factory id: the id appears in the factory tree, its history, its
     registered paks or its built artifacts (``factory_ids``);
   - a custom-scope export lists it: the product itself calls it custom.

3. Explained presence. Each known third-party package (a pak, a fork, a
   reference content repo) is a group of ids. A group counts as installed
   on an instance when at least ``installed_threshold`` of its ids (of the
   types that instance's sources cover) are present there. Presence of an
   id on an instance where a group holding it is installed is explained by
   that package and is not evidence. This is what keeps the content of a
   pak installed on every lab out, while a package that merely copied stock
   ids (and is not installed) does not hide them.

4. Evidence. The instances where the id is present and not explained:
   - two or more: stock;
   - exactly one, for a view or report template whose title carries the
     product's ``localizationKey`` there, or a dashboard whose
     ``adapterName`` is one that two-instance stock dashboards carry, AND a
     known third-party package (not installed there) carries the same id:
     stock. The package is an export of its author's own instance, so the
     id was seen on two independent appliances;
   - otherwise: candidate, not included.

The versions an id is stock in are the versions of its evidence instances;
its display name is the most common name among them (latest version wins a
tie).
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .guard import (
    BASELINE_FORMAT,
    CONTENT_TYPES,
    Definition,
    normalize_id,
    version_sort_key,
)

#: Name markers that are never stock: the factory prefix in both forms and
#: the legacy one. Third-party markers are passed by the caller and
#: recorded in the baseline's ``rule`` block.
DEFAULT_NAME_MARKERS: Tuple[str, ...] = (
    "[VCF Content Factory]",
    "VCF Content Factory",
    "[AI Content]",
)

DEFAULT_INSTALLED_THRESHOLD = 0.9

_Key = Tuple[str, str]


@dataclass
class Observation:
    """One definition seen on one instance."""

    type: str
    id: str
    name: str
    instance: str
    version: str
    attrs: Dict[str, str] = field(default_factory=dict)


@dataclass
class Candidate:
    type: str
    id: str
    names: List[str]
    instances: List[str]
    reason: str


@dataclass
class BaselineBuild:
    baseline: dict
    candidates: List[Candidate]


def observations_from_definitions(
    defs: Iterable[Definition], instance: str, version: str,
) -> List[Observation]:
    """Observations for one instance's export; policy-embedded copies dropped."""
    out = []
    for d in defs:
        if d.attrs.get("in_policy"):
            continue
        out.append(Observation(d.type, d.id, d.name, instance, version, dict(d.attrs)))
    return out


def parse_inventory(text: str, content_type: str, instance: str, version: str) -> List[Observation]:
    """An id/name inventory: one ``<id><whitespace><name>`` per line.

    The shape of ``GET /api/<type>`` lists saved as text. Blank lines and
    ``#`` comments are skipped.
    """
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"unknown content type {content_type!r}")
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        out.append(Observation(content_type, parts[0], parts[1].strip() if len(parts) > 1 else "",
                               instance, version))
    return out


def _marker_hit(names: Iterable[str], markers: Sequence[str]) -> Optional[str]:
    lowered = [m.lower() for m in markers if m]
    for n in names:
        nl = (n or "").lower()
        for m, ml in zip([m for m in markers if m], lowered):
            if ml in nl:
                return m
    return None


def build_baseline(
    observations: Iterable[Observation],
    *,
    known_groups: Optional[Mapping[str, Iterable[Definition]]] = None,
    custom_ids: Iterable[_Key] = (),
    factory_ids: Iterable[str] = (),
    exclude_name_markers: Sequence[str] = DEFAULT_NAME_MARKERS,
    exclude_adapter_kind_prefixes: Sequence[str] = (),
    installed_threshold: float = DEFAULT_INSTALLED_THRESHOLD,
    sources: Sequence[dict] = (),
    generated: str = "",
    regenerate: str = "",
) -> BaselineBuild:
    """Decide every observed id; return the baseline dict and the candidates."""
    obs_by_key: Dict[_Key, List[Observation]] = defaultdict(list)
    inst_version: Dict[str, str] = {}
    inst_types: Dict[str, Set[str]] = defaultdict(set)
    for o in observations:
        if o.type not in CONTENT_TYPES:
            continue
        key = (o.type, normalize_id(o.id))
        obs_by_key[key].append(o)
        inst_version[o.instance] = o.version
        inst_types[o.instance].add(o.type)
    present: Dict[str, Set[_Key]] = defaultdict(set)
    for key, obs in obs_by_key.items():
        for o in obs:
            present[o.instance].add(key)

    custom = {(t, normalize_id(i)) for t, i in custom_ids}
    factory = {normalize_id(i) for i in factory_ids}
    adapter_prefixes = [p.lower() for p in exclude_adapter_kind_prefixes if p]

    # Known third-party packages: id sets and where each counts as installed.
    groups: Dict[str, Set[_Key]] = {}
    for label, defs in (known_groups or {}).items():
        ids = set()
        for d in defs:
            if d.attrs.get("in_policy") or d.type not in CONTENT_TYPES:
                continue
            k = (d.type, normalize_id(d.id))
            ids.add(k)
        if ids:
            groups[label] = ids
    installed: Dict[str, Set[str]] = defaultdict(set)  # group -> instances
    for label, ids in groups.items():
        for inst, types in inst_types.items():
            denom = [k for k in ids if k[0] in types]
            if not denom:
                continue
            hit = sum(1 for k in denom if k in present[inst])
            if hit / len(denom) >= installed_threshold:
                installed[label].add(inst)
    groups_of: Dict[_Key, Set[str]] = defaultdict(set)
    for label, ids in groups.items():
        for k in ids:
            groups_of[k].add(label)

    def evidence(key: _Key) -> Tuple[List[str], List[str]]:
        """(evidence instances, explanation notes)."""
        ev, notes = [], []
        for inst in sorted({o.instance for o in obs_by_key[key]}):
            by = sorted(g for g in groups_of.get(key, ()) if inst in installed[g])
            if by:
                notes.append(f"present on {inst} only because {by[0]} is installed there")
            else:
                ev.append(inst)
        return ev, notes

    # Two-instance stock dashboards define the product adapter names a
    # single-instance dashboard may carry.
    decided: Dict[_Key, Tuple[List[str], List[str]]] = {}
    stock_dash_adapters: Set[str] = set()
    for key in obs_by_key:
        decided[key] = evidence(key)
        if key[0] == "dashboard" and len(decided[key][0]) >= 2:
            for o in obs_by_key[key]:
                if o.attrs.get("adapterName"):
                    stock_dash_adapters.add(o.attrs["adapterName"])

    ids_out: Dict[str, Dict[str, dict]] = {t: {} for t in CONTENT_TYPES}
    candidates: List[Candidate] = []
    for key in sorted(obs_by_key):
        ctype, nid = key
        obs = obs_by_key[key]
        names = sorted({o.name for o in obs if o.name})
        all_inst = sorted({o.instance for o in obs})
        display_id = obs[0].id

        def cand(reason: str) -> None:
            candidates.append(Candidate(ctype, display_id, names, all_inst, reason))

        marker = _marker_hit(names, exclude_name_markers)
        if marker:
            cand(f"name carries the marker {marker!r}")
            continue
        kinds = sorted({o.attrs.get("adapterKind", "") for o in obs if o.attrs.get("adapterKind")})
        bad_kind = next((k for k in kinds if any(k.lower().startswith(p) for p in adapter_prefixes)), None)
        if bad_kind:
            cand(f"adapter kind {bad_kind!r} is excluded")
            continue
        if nid in factory:
            cand("the id is a factory id (factory tree, history, registered paks or builds)")
            continue
        if key in custom:
            cand("a custom-scope export lists it")
            continue
        ev, notes = decided[key]
        if len(ev) >= 2:
            pass  # corroborated: stock
        elif len(ev) == 1:
            inst = ev[0]
            here = [o for o in obs if o.instance == inst]
            independent = sorted(g for g in groups_of.get(key, ()) if inst not in installed[g])
            if ctype in ("view", "report"):
                signal = any(o.attrs.get("localized") for o in here)
                what = "a product localizationKey"
            elif ctype == "dashboard":
                signal = any(o.attrs.get("adapterName") in stock_dash_adapters for o in here)
                what = "a stock dashboard adapterName"
            else:
                signal, what = False, None
            if not (signal and independent):
                why = [f"seen on one clean instance only ({inst})"]
                if what is None:
                    why.append(f"type {ctype} has no single-instance signal, so it needs two")
                else:
                    if not signal:
                        why.append(f"without {what}")
                    if not independent:
                        why.append("and no independent third-party copy")
                cand(", ".join(why) + ("; " + "; ".join(notes) if notes else ""))
                continue
        else:
            cand("; ".join(notes) or "no evidence instance")
            continue
        ev_obs = [o for o in obs if o.instance in ev]
        versions = sorted({inst_version[i] for i in ev}, key=version_sort_key)
        counts = Counter(o.name for o in ev_obs if o.name)
        if counts:
            top = max(counts.values())
            best = [n for n, c in counts.items() if c == top]
            latest = {}
            for o in ev_obs:
                if o.name in best:
                    latest[o.name] = max(latest.get(o.name, (0,)), version_sort_key(o.version))
            name = sorted(best, key=lambda n: (latest[n], n))[-1]
        else:
            name = ""
        ids_out[ctype][display_id] = {"name": name, "versions": versions}

    all_versions = sorted(set(inst_version.values()), key=version_sort_key)
    counts_out = {}
    for t in CONTENT_TYPES:
        table = ids_out[t]
        counts_out[t] = {
            "total": len(table),
            "by_version": {v: sum(1 for e in table.values() if v in e["versions"]) for v in all_versions},
        }
    cand_counts = Counter(c.type for c in candidates)
    baseline = {
        "format": BASELINE_FORMAT,
        "about": (
            "VCF Operations stock content ids (issue #345): ids only, with a display name "
            "for error messages and the product versions each id was seen in. Content "
            "that ships a DEFINITION under one of these ids overwrites the stock object "
            "on install and deletes it on uninstall; the factory's builds refuse it. "
            "References to these ids are fine."
        ),
        "generated": generated,
        "regenerate": regenerate,
        "rule": {
            "doc": "src/vcfcf_core/stock_ids/generate.py module docstring",
            "exclude_name_markers": list(exclude_name_markers),
            "exclude_adapter_kind_prefixes": list(exclude_adapter_kind_prefixes),
            "installed_threshold": installed_threshold,
            "factory_ids_considered": len(factory),
            "known_packages": sorted(groups),
        },
        "sources": list(sources),
        "counts": counts_out,
        "candidates_not_included": {t: cand_counts.get(t, 0) for t in CONTENT_TYPES},
        "ids": {t: dict(sorted(ids_out[t].items())) for t in CONTENT_TYPES if ids_out[t]},
    }
    return BaselineBuild(baseline, candidates)


def render_baseline_json(baseline: dict) -> str:
    """Deterministic JSON text: metadata indented, one line per id."""
    meta = {k: v for k, v in baseline.items() if k != "ids"}
    head = json.dumps(meta, indent=2, ensure_ascii=False)
    assert head.endswith("}")
    lines = [head[:-1].rstrip() + ',', '  "ids": {']
    types = list(baseline.get("ids", {}))
    for ti, t in enumerate(types):
        lines.append(f'    {json.dumps(t)}: {{')
        items = list(baseline["ids"][t].items())
        for i, (oid, rec) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            body = json.dumps({"name": rec["name"], "versions": rec["versions"]}, ensure_ascii=False)
            lines.append(f"      {json.dumps(oid)}: {body}{comma}")
        lines.append("    }" + ("," if ti < len(types) - 1 else ""))
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_candidates_report(candidates: Sequence[Candidate]) -> str:
    """Plain-text report of the ids left out, grouped by type and reason.

    It names non-stock content found on the source instances, so it is
    written where the caller says (a scratch path), not into the repo.
    """
    out = ["# Stock-id baseline: candidates, not included", ""]
    by_type: Dict[str, List[Candidate]] = defaultdict(list)
    for c in candidates:
        by_type[c.type].append(c)
    for t in CONTENT_TYPES:
        cs = by_type.get(t)
        if not cs:
            continue
        out.append(f"## {t}: {len(cs)}")
        reasons = Counter(re.sub(r"\(.*?\)|'.*?'", "", c.reason).strip() for c in cs)
        for r, n in reasons.most_common():
            out.append(f"   {n:5d}  {r}")
        out.append("")
        for c in sorted(cs, key=lambda c: (c.reason, c.names[:1], c.id)):
            out.append(f"  {c.id}  {' | '.join(c.names[:2])}  [{', '.join(c.instances)}]  {c.reason}")
        out.append("")
    return "\n".join(out) + "\n"
