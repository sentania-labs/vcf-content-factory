"""Factory side of the stock-id guard (issue #345).

The guard itself (scanner, baseline, allowlist, check) is
``vcfcf_core.stock_ids.guard``; this module adds what reads the factory
tree:

- ``repo_allowlist()``: every ``stock_id_allowlist`` entry in the bundle
  manifests (``bundles/*.yaml``) and project manifests
  (``third_party/*/PROJECT.yaml``), for the per-type ``validate`` commands
  and the content-import path, which have no single manifest in hand.
- ``report_stock_ids()``: the one check the per-type ``validate`` commands
  call; prints, returns an exit code.
- ``refuse_stock_ids_in_zip()``: the content-import choke point
  (``vcfcf_dashboards.client.import_content_zip``).
- ``cmd_stock_id_check`` / ``cmd_stock_id_baseline``: the CLI commands.

Fail closed throughout: an unloadable baseline is an error, never a pass.
"""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple

import yaml

from vcfcf_core.stock_ids import guard as _guard
from vcfcf_core.stock_ids import generate as _gen
from vcfcf_core.stock_ids.guard import (
    AllowlistEntry,
    Definition,
    StockIdAllowlistError,
    StockIdBaselineError,
    check_definitions,
    load_baseline,
    parse_allowlist,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Allowlist across the repo's manifests
# ---------------------------------------------------------------------------

def _manifest_paths(root: Path) -> List[Path]:
    paths = sorted((root / "bundles").glob("*.yaml")) + sorted((root / "bundles").glob("*.yml"))
    paths += sorted((root / "third_party").glob("*/PROJECT.yaml"))
    return paths


def repo_allowlist(root: Optional[Path] = None) -> List[AllowlistEntry]:
    """Every ``stock_id_allowlist`` entry declared by a manifest in the repo.

    A malformed entry raises ``StockIdAllowlistError``: an escape hatch that
    cannot be read must not silently widen or narrow what passes.
    """
    root = Path(root) if root is not None else REPO_ROOT
    out: List[AllowlistEntry] = []
    for p in _manifest_paths(root):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue  # the manifest's own loader reports it
        if isinstance(data, dict) and data.get("stock_id_allowlist") is not None:
            rel = p.relative_to(root) if p.is_relative_to(root) else p
            out.extend(parse_allowlist(data["stock_id_allowlist"], str(rel)))
    return out


def _merge_allowlists(entries: Iterable[AllowlistEntry]) -> List[AllowlistEntry]:
    """First entry per (type, id) wins; a repeat across manifests is fine."""
    seen = set()
    out = []
    for e in entries:
        key = (e.type, _guard.normalize_id(e.id))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


# ---------------------------------------------------------------------------
# Per-type validate
# ---------------------------------------------------------------------------

def report_stock_ids(defs: Sequence[Definition], what: str) -> int:
    """Check definitions a ``validate`` command loaded; print; return 0 or 1.

    Hits are ``STOCK-ID:`` errors. Allowlisted hits are warnings. An
    unloadable baseline or allowlist is an error (fail closed). Allowlist
    entries that match nothing here are not reported: one ``validate``
    sees one content type, and the entry may be for another.
    """
    try:
        baseline = load_baseline()
        allow = _merge_allowlists(repo_allowlist())
    except (StockIdBaselineError, StockIdAllowlistError) as exc:
        print(f"STOCK-ID: {exc}", file=sys.stderr)
        return 1
    result = check_definitions(defs, baseline=baseline, allowlist=allow)
    for w in result.warnings:
        if w.startswith("ALLOWLISTED"):
            print(f"WARNING: {w}", file=sys.stderr)
    for e in result.errors:
        print(f"STOCK-ID: {e}", file=sys.stderr)
    return 1 if result.errors else 0


def symptom_definitions(symptoms: Sequence) -> List[Definition]:
    """Definitions for loaded symptoms, under the ids they render with."""
    if not symptoms:
        return []
    from vcfcf_core.alerts.render import render_alert_content_xml
    xml = render_alert_content_xml(symptoms=list(symptoms), alerts=[], recommendations=[])
    return _guard.bundled_definitions(symptoms=symptoms, alert_content_xml=xml)


def alert_definitions(alerts: Sequence, recommendations: Sequence = ()) -> List[Definition]:
    """Definitions for loaded alerts and recommendations (rendered ids)."""
    if not alerts and not recommendations:
        return []
    from vcfcf_core.alerts.render import render_alert_content_xml
    xml = render_alert_content_xml(symptoms=[], alerts=list(alerts),
                                   recommendations=list(recommendations))
    return [d for d in _guard.bundled_definitions(
        alerts=alerts, recommendations=recommendations, alert_content_xml=xml,
    ) if d.type in ("alert", "recommendation")]


# ---------------------------------------------------------------------------
# Bundle and release builds
# ---------------------------------------------------------------------------

def guard_bundle(bundle, zip_bytes: Optional[bytes], what: str) -> None:
    """Refuse a bundle build whose content ships under stock ids (#345).

    Checks the bundle's loaded content (errors name the YAML file) and then
    every definition in the assembled zip (anything a renderer added), with
    the manifest's ``stock_id_allowlist``. Raises ``BundleValidationError``;
    prints a warning per allowlisted hit and per unused entry.
    """
    from .loader import BundleValidationError
    from vcfcf_core.alerts.render import render_alert_content_xml

    try:
        baseline = load_baseline()
    except StockIdBaselineError as exc:
        raise BundleValidationError(f"stock-id guard: {exc}") from exc
    alert_xml = None
    if bundle.symptoms or bundle.alerts or bundle.recommendations:
        alert_xml = render_alert_content_xml(
            symptoms=list(bundle.symptoms), alerts=list(bundle.alerts),
            recommendations=list(bundle.recommendations),
        )
    defs = _guard.bundled_definitions(
        views=bundle.views, dashboards=bundle.dashboards,
        supermetrics=bundle.supermetrics, reports=bundle.reports,
        symptoms=bundle.symptoms, alerts=bundle.alerts,
        recommendations=bundle.recommendations, alert_content_xml=alert_xml,
    )
    if zip_bytes is not None:
        seen = {(d.type, _guard.normalize_id(d.id)) for d in defs}
        defs += [d for d in _guard.scan_bytes(zip_bytes, what)
                 if (d.type, _guard.normalize_id(d.id)) not in seen]
    result = check_definitions(
        defs, baseline=baseline, allowlist=getattr(bundle, "stock_id_allowlist", []) or [],
        subject=what,
    )
    for w in result.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if result.errors:
        raise BundleValidationError(_guard.guard_failure_text(result, what))


# ---------------------------------------------------------------------------
# Content-import choke point
# ---------------------------------------------------------------------------

class StockIdRefused(RuntimeError):
    """Content about to be imported carries stock ids (or the check cannot run)."""


def refuse_stock_ids_in_zip(zip_bytes: bytes, what: str = "content zip") -> List[str]:
    """Raise ``StockIdRefused`` if ``zip_bytes`` defines a stock id.

    Called on every content-zip import the factory sends. Returns the
    allowlist warnings (already printed) so a caller can surface them.
    """
    try:
        baseline = load_baseline()
        allow = _merge_allowlists(repo_allowlist())
    except (StockIdBaselineError, StockIdAllowlistError) as exc:
        raise StockIdRefused(f"stock-id guard cannot run, import refused: {exc}") from exc
    defs = _guard.scan_bytes(zip_bytes, what)
    result = check_definitions(defs, baseline=baseline, allowlist=allow)
    warnings = [w for w in result.warnings if w.startswith("ALLOWLISTED")]
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if result.errors:
        raise StockIdRefused(_guard.guard_failure_text(result, what) + "\nImport refused.")
    return warnings


# ---------------------------------------------------------------------------
# stock-id-check (standalone, read-only)
# ---------------------------------------------------------------------------

def cmd_stock_id_check(args) -> int:
    """List every definition in a pak / zip / export / directory whose id is stock.

    Exit 0: no stock ids. 2: stock ids found. 1: the baseline cannot be
    loaded or a path is missing.
    """
    try:
        baseline = load_baseline(args.baseline)
    except StockIdBaselineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        for p in missing:
            print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    print(
        f"stock-id baseline: {baseline.source} ({baseline.count()} ids; "
        f"versions {', '.join(baseline.versions())})"
    )
    lines, total = _guard.check_paths(args.paths, baseline)
    for line in lines:
        print(line)
    if total:
        print(f"stock-id check: {total} definition(s) under stock ids")
        return 2
    print("stock-id check: no definition uses a stock id")
    return 0


# ---------------------------------------------------------------------------
# stock-id-baseline (generator)
# ---------------------------------------------------------------------------

_UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_YAML_ID_LINE = re.compile(r"^[+-]?\s*-?\s*(?:id|uuid)\s*:\s*[\"']?(" + _UUID_RE + ")", re.M)


def _yaml_ids_in_tree(root: Path) -> Set[str]:
    ids: Set[str] = set()
    for p in list(root.rglob("*.yaml")) + list(root.rglob("*.yml")):
        if ".git" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ids.update(m.lower() for m in _YAML_ID_LINE.findall(text))
    return ids


def _yaml_ids_in_git_history(repo: Path) -> Set[str]:
    """Every ``id:`` / ``uuid:`` value ever added or removed in a YAML file."""
    proc = subprocess.run(
        ["git", "log", "--all", "-p", "--no-color", "--unified=0", "--",
         "*.yaml", "*.yml"],
        cwd=str(repo), capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git log failed in {repo}: {proc.stderr.strip()}")
    return {m.lower() for m in _YAML_ID_LINE.findall(proc.stdout)}


def collect_factory_ids(
    trees: Sequence[Path], artifacts: Sequence[Path], git_repo: Optional[Path],
) -> Tuple[Set[str], List[str]]:
    """Ids the factory minted: YAML ``id:`` values in ``trees`` (and their git
    history when ``git_repo`` is given) plus every definition in ``artifacts``
    (built paks and zips). Returns (ids, notes)."""
    ids: Set[str] = set()
    notes: List[str] = []
    for t in trees:
        if t.exists():
            found = _yaml_ids_in_tree(t)
            ids |= found
            notes.append(f"{len(found)} ids in YAML under {t}")
    if git_repo is not None:
        found = _yaml_ids_in_git_history(git_repo)
        ids |= found
        notes.append(f"{len(found)} ids in the YAML history of {git_repo}")
    for a in artifacts:
        if a.exists():
            found = {_guard.normalize_id(d.id) for d in _guard.scan_path(a)}
            ids |= found
            notes.append(f"{len(found)} ids in built artifacts under {a}")
    return ids, notes


def _split_spec(spec: str, n: int, what: str) -> List[str]:
    parts = spec.split("=", n - 1)
    if len(parts) != n or not all(parts):
        raise SystemExit(f"ERROR: {what} must look like {'='.join(['X'] * n)}; got {spec!r}")
    return parts


def cmd_stock_id_baseline(args) -> int:
    """Regenerate the stock-id baseline from content exports.

    Writes the baseline JSON to ``--out`` and, with ``--candidates-out``, a
    report of every id left out and why. That report names non-stock
    content found on the source instances, so point it outside the repo.
    """
    observations: List[_gen.Observation] = []
    sources: List[dict] = []
    for spec in args.export or []:
        version, label, path = _split_spec(spec, 3, "--export")
        defs = _guard.scan_path(path)
        obs = _gen.observations_from_definitions(defs, label, version)
        observations.extend(obs)
        counts = {}
        for o in obs:
            counts[o.type] = counts.get(o.type, 0) + 1
        sources.append({"instance": label, "version": version, "kind": "content export",
                        "definitions": dict(sorted(counts.items()))})
        print(f"export   {label} ({version}): {sum(counts.values())} definitions", file=sys.stderr)
    for spec in args.inventory or []:
        version, label, ctype, path = _split_spec(spec, 4, "--inventory")
        obs = _gen.parse_inventory(Path(path).read_text(encoding="utf-8"), ctype, label, version)
        observations.extend(obs)
        sources.append({"instance": label, "version": version, "kind": f"{ctype} inventory",
                        "definitions": {ctype: len(obs)}})
        print(f"inventory {label} ({version}) {ctype}: {len(obs)} ids", file=sys.stderr)
    if not observations:
        print("ERROR: no --export or --inventory given", file=sys.stderr)
        return 1

    custom_ids = []
    for path in args.custom_export or []:
        defs = [d for d in _guard.scan_path(path) if not d.attrs.get("in_policy")]
        custom_ids.extend((d.type, d.id) for d in defs)
        sources.append({"kind": "custom-scope export (negative evidence)",
                        "definitions": len(defs)})
    known = {}
    for spec in args.known_content or []:
        label, path = _split_spec(spec, 2, "--known-content")
        known[label] = _guard.scan_path(path)
    factory_ids, notes = collect_factory_ids(
        [Path(p) for p in (args.factory_tree or [])],
        [Path(p) for p in (args.factory_artifacts or [])],
        Path(args.factory_git) if args.factory_git else None,
    )
    for n in notes:
        print(f"factory  {n}", file=sys.stderr)

    markers = list(_gen.DEFAULT_NAME_MARKERS) + list(args.exclude_name or [])
    build = _gen.build_baseline(
        observations,
        known_groups=known,
        custom_ids=custom_ids,
        factory_ids=factory_ids,
        exclude_name_markers=markers,
        exclude_adapter_kind_prefixes=list(args.exclude_adapter_kind or []),
        installed_threshold=args.installed_threshold,
        sources=sources,
        generated=args.generated or _dt.date.today().isoformat(),
        regenerate=(
            "python3 -m vcfcf_packaging stock-id-baseline --export <version>=<label>=<path> ... "
            "(knowledge/context/stock_id_guard.md)"
        ),
    )
    text = _gen.render_baseline_json(build.baseline)
    _guard.parse_baseline(text, "<generated>")  # never write a file the guard refuses
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    for t, c in build.baseline["counts"].items():
        if c["total"]:
            per = ", ".join(f"{v}: {n}" for v, n in c["by_version"].items())
            print(f"  {t}: {c['total']} ({per})")
    print(f"  candidates, not included: {len(build.candidates)} "
          f"({', '.join(f'{t}: {n}' for t, n in build.baseline['candidates_not_included'].items() if n)})")
    if args.candidates_out:
        Path(args.candidates_out).write_text(_gen.render_candidates_report(build.candidates),
                                             encoding="utf-8")
        print(f"wrote {args.candidates_out}")
    return 0


def add_parsers(sub) -> None:
    """Register ``stock-id-check`` and ``stock-id-baseline`` on the packaging CLI."""
    pchk = sub.add_parser(
        "stock-id-check",
        help=(
            "read-only: list every definition in a .pak (packed or unpacked), "
            "content zip, content export or directory whose id is a VCF "
            "Operations stock id. Exit 0 none, 2 found, 1 cannot check (#345)"
        ),
    )
    pchk.add_argument("paths", nargs="+", metavar="PATH")
    pchk.add_argument("--baseline", default=None, metavar="JSON",
                      help="baseline to check against (default: the packaged one)")
    pchk.set_defaults(func=cmd_stock_id_check)

    pgen = sub.add_parser(
        "stock-id-baseline",
        help=(
            "regenerate the stock-id baseline from clean content exports "
            "(knowledge/context/stock_id_guard.md) (#345)"
        ),
    )
    pgen.add_argument("--export", action="append", metavar="VERSION=LABEL=PATH",
                      help="a scope-ALL content export (dir or zip) from a clean instance; repeat")
    pgen.add_argument("--inventory", action="append", metavar="VERSION=LABEL=TYPE=PATH",
                      help="an '<id> <name>' list (REST inventory) of TYPE from another instance")
    pgen.add_argument("--custom-export", action="append", metavar="PATH",
                      help="a scope-CUSTOM export: every id in it is not stock")
    pgen.add_argument("--known-content", action="append", metavar="LABEL=PATH",
                      help="a third-party pak, fork or content repo that may be installed on a source")
    pgen.add_argument("--factory-tree", action="append", metavar="DIR",
                      help="a tree whose YAML id: values are factory ids (content/, a pak repo)")
    pgen.add_argument("--factory-artifacts", action="append", metavar="PATH",
                      help="built factory paks / zips (dist/): every id in them is a factory id")
    pgen.add_argument("--factory-git", default=None, metavar="REPO",
                      help="also take every YAML id: value in this repo's git history")
    pgen.add_argument("--exclude-name", action="append", metavar="MARKER",
                      help="a name substring that is never stock (third-party tag); repeat")
    pgen.add_argument("--exclude-adapter-kind", action="append", metavar="PREFIX",
                      help="an adapter kind prefix whose symptoms/alerts are never stock")
    pgen.add_argument("--installed-threshold", type=float,
                      default=_gen.DEFAULT_INSTALLED_THRESHOLD,
                      help="share of a known package's ids present for it to count as installed")
    pgen.add_argument("--generated", default=None, help="date stamp (default today)")
    pgen.add_argument("--out", required=True, metavar="JSON")
    pgen.add_argument("--candidates-out", default=None, metavar="PATH",
                      help="write the ids left out, with reasons (names content: keep out of the repo)")
    pgen.set_defaults(func=cmd_stock_id_baseline)
