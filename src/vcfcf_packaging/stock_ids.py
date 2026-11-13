"""Factory side of the stock-id guard (issue #345).

The guard itself (scanner, baseline, allowlist, check) is
``vcfcf_core.stock_ids.guard``; this module adds what reads the factory
tree:

- ``repo_manifest_allowlists()``: the ``stock_id_allowlist`` entries of
  the bundle manifests (``bundles/*.yaml``) and project manifests
  (``third_party/*/PROJECT.yaml``), each with the content its manifest
  owns: the files a bundle lists, everything under a project's directory.
  An entry covers only definitions its own manifest owns.
- ``report_stock_ids()``: the one check the per-type ``validate`` commands
  call; attributes each definition to its owning manifest(s) by file;
  prints, returns an exit code.
- ``import_allowlist()`` / ``refuse_stock_ids_in_zip()``: the
  content-import choke point (``vcfcf_dashboards.client.import_content_zip``).
  A bundle sync declares the bundle's own entries for the imports it makes;
  any other import has no owning manifest and no allowlist.
- ``guard_bundle()``: the bundle, discrete and release build check.
- ``cmd_stock_id_check`` / ``cmd_stock_id_baseline``: the CLI commands.

Fail closed throughout: an unloadable baseline, and content the scanner
cannot read, are errors, never a pass.
"""
from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

import yaml

from vcfcf_core.stock_ids import guard as _guard
from vcfcf_core.stock_ids import generate as _gen
from vcfcf_core.stock_ids.guard import (
    AllowlistEntry,
    Definition,
    GuardResult,
    StockBaseline,
    StockIdAllowlistError,
    StockIdBaselineError,
    Unreadable,
    check_definitions,
    load_baseline,
    parse_allowlist,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Bundle manifest keys that list content files (the files a bundle owns).
_BUNDLE_CONTENT_KEYS = ("supermetrics", "views", "dashboards", "customgroups", "reports",
                        "symptoms", "alerts", "recommendations")


# ---------------------------------------------------------------------------
# Allowlists, each scoped to the content its manifest owns
# ---------------------------------------------------------------------------

def _resolved(path) -> Path:
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError, ValueError):
        return Path(path).absolute()


@dataclass
class ManifestAllowlist:
    """One manifest's ``stock_id_allowlist`` and the content it owns.

    A bundle manifest owns the files it lists; a ``PROJECT.yaml`` (and an
    adapter.yaml, on the SDK paths) owns everything under its directory.
    """

    manifest: str
    entries: List[AllowlistEntry]
    files: Set[Path] = field(default_factory=set)
    dirs: List[Path] = field(default_factory=list)

    def owns(self, location: str) -> bool:
        loc = str(location or "")
        if not loc or loc.startswith("<"):
            return False
        p = _resolved(loc)
        if p in self.files:
            return True
        return any(p == d or d in p.parents for d in self.dirs)


def _manifest_paths(root: Path) -> List[Path]:
    paths = sorted((root / "bundles").glob("*.yaml")) + sorted((root / "bundles").glob("*.yml"))
    paths += sorted((root / "third_party").glob("*/PROJECT.yaml"))
    return paths


def _load_manifest_allowlist(p: Path, root: Path) -> Optional[ManifestAllowlist]:
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None  # the manifest's own loader reports it
    if not isinstance(data, dict) or data.get("stock_id_allowlist") is None:
        return None
    rel = p.relative_to(root) if p.is_relative_to(root) else p
    entries = parse_allowlist(data["stock_id_allowlist"], str(rel))
    m = ManifestAllowlist(str(rel), entries)
    if p.name == "PROJECT.yaml":
        m.dirs.append(_resolved(p.parent))
    else:
        for key in _BUNDLE_CONTENT_KEYS:
            for ref in data.get(key) or []:
                if isinstance(ref, str) and ref.strip():
                    # load_bundle resolves a reference against the repo root
                    # first, then the manifest's directory: own both.
                    m.files.add(_resolved(root / ref.strip()))
                    m.files.add(_resolved(p.parent / ref.strip()))
    return m


def repo_manifest_allowlists(root: Optional[Path] = None) -> List[ManifestAllowlist]:
    """Every manifest in the repo that declares a ``stock_id_allowlist``.

    A malformed entry raises ``StockIdAllowlistError``: an escape hatch that
    cannot be read must not silently widen or narrow what passes.
    """
    root = Path(root) if root is not None else REPO_ROOT
    out: List[ManifestAllowlist] = []
    for p in _manifest_paths(root):
        m = _load_manifest_allowlist(p, root)
        if m is not None:
            out.append(m)
    return out


def project_allowlists(project_dirs: Iterable[Path]) -> List[ManifestAllowlist]:
    """The ``PROJECT.yaml`` allowlists of third-party project roots (the
    discrete builder's ``extra_search_dirs``), each owning its directory."""
    out: List[ManifestAllowlist] = []
    for d in project_dirs or []:
        p = Path(d) / "PROJECT.yaml"
        if p.is_file():
            m = _load_manifest_allowlist(p, Path(d).parent.parent)
            if m is not None:
                out.append(m)
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


def check_scoped(
    defs: Sequence[Definition], baseline: StockBaseline,
    manifests: Sequence[ManifestAllowlist],
) -> GuardResult:
    """Check definitions, honouring each manifest's entries only for the
    definitions that manifest owns (by file). A hit no manifest owns cannot
    be allowlisted. Unused-entry warnings are not produced: a repo-wide
    check sees only some of the content a manifest's entries are for."""
    groups: Dict[Tuple[int, ...], List[Definition]] = {}
    for d in defs:
        owners = tuple(i for i, m in enumerate(manifests) if m.owns(d.location))
        groups.setdefault(owners, []).append(d)
    result = GuardResult()
    for owners, group in groups.items():
        allow = _merge_allowlists(e for i in owners for e in manifests[i].entries)
        r = check_definitions(group, baseline=baseline, allowlist=allow)
        result.errors += r.errors
        result.warnings += [w for w in r.warnings if w.startswith("ALLOWLISTED")]
        result.hits += r.hits
        result.allowed += r.allowed
    return result


# ---------------------------------------------------------------------------
# Per-type validate
# ---------------------------------------------------------------------------

def report_stock_ids(defs: Sequence[Definition], what: str) -> int:
    """Check definitions a ``validate`` command loaded; print; return 0 or 1.

    Hits are ``STOCK-ID:`` errors. A hit is allowlisted only by an entry of
    a manifest that owns the definition's file. Allowlisted hits are
    warnings. An unloadable baseline or allowlist is an error (fail closed).
    """
    try:
        baseline = load_baseline()
        manifests = repo_manifest_allowlists()
    except (StockIdBaselineError, StockIdAllowlistError) as exc:
        print(f"STOCK-ID: {exc}", file=sys.stderr)
        return 1
    result = check_scoped(defs, baseline, manifests)
    for w in result.warnings:
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
# Stock names: symptom and alert sync upsert by name (W8)
# ---------------------------------------------------------------------------

def report_stock_name_collisions(objs: Sequence, content_type: str, what: str) -> int:
    """Warn for each symptom or alert whose name is a stock one's (#345).

    Symptoms and alerts are installed through REST by name (factory sync
    and the distribution ``install.py`` both find by exact name, then PUT
    the existing id): an object named exactly like a stock symptom or alert
    definition overwrites the stock object, whatever its id. Factory
    content carries the RULE-006 prefix, so this catches unprefixed
    third-party (``factory_native: false``) content. A warning, not an
    error: the baseline holds one display name per id, so a match is a
    prompt to rename, not proof. Returns the number found. An unloadable
    baseline returns 0 here; the id check in the same run fails closed on it.
    """
    if content_type not in ("symptom", "alert") or not objs:
        return 0
    try:
        baseline = load_baseline()
    except StockIdBaselineError:
        return 0
    stock: Dict[str, List[_guard.StockEntry]] = {}
    for e in baseline.entries():
        if e.type == content_type and e.name:
            stock.setdefault(e.name, []).append(e)
    found = 0
    label = _guard.type_label(content_type)
    for o in objs:
        name = str(getattr(o, "name", "") or "")
        hits = stock.get(name) if name else None
        if not hits:
            continue
        found += 1
        src = getattr(o, "source_path", None) or name
        ids = ", ".join(sorted(h.id for h in hits)[:3]) + (" ..." if len(hits) > 3 else "")
        print(
            f"WARNING: STOCK-NAME: {src}: {label} {name!r} has the name of a VCF "
            f"Operations stock {label} ({ids}). {what} install and sync match by "
            f"name, so installing it would overwrite that stock {label}. Rename it.",
            file=sys.stderr,
        )
    return found


def warn_bundle_stock_names(bundle) -> int:
    """``report_stock_name_collisions`` over a bundle's symptoms and alerts."""
    return (report_stock_name_collisions(list(getattr(bundle, "symptoms", None) or []),
                                         "symptom", "Symptom")
            + report_stock_name_collisions(list(getattr(bundle, "alerts", None) or []),
                                           "alert", "Alert"))


# ---------------------------------------------------------------------------
# Bundle and release builds
# ---------------------------------------------------------------------------

def guard_bundle(bundle, zip_bytes: Optional[bytes], what: str, *,
                 manifests: Optional[Sequence[ManifestAllowlist]] = None) -> None:
    """Refuse a bundle build whose content ships under stock ids (#345).

    Checks the bundle's loaded content (errors name the YAML file) and then
    every definition in the assembled zip (anything a renderer added).
    A zip member the scanner cannot read fails the build.

    Allowlist: by default the manifest's own ``stock_id_allowlist`` covers
    all of the bundle's content (the bundle owns everything it ships).
    With ``manifests`` (a discrete or release item, which has no manifest of
    its own) each definition is covered only by the entries of the
    manifests that own its file, such as its project's ``PROJECT.yaml``.
    Raises ``BundleValidationError``; prints a warning per allowlisted hit
    (and, for a bundle, per unused entry).
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
        unreadable: List[Unreadable] = []
        scanned = _guard.scan_bytes(zip_bytes, what, unreadable=unreadable)
        if unreadable:
            raise BundleValidationError(_guard.unreadable_failure_text(unreadable, what))
        seen = {(d.type, _guard.normalize_id(d.id)) for d in defs}
        defs += [d for d in scanned if (d.type, _guard.normalize_id(d.id)) not in seen]
    if manifests is None:
        result = check_definitions(
            defs, baseline=baseline, allowlist=getattr(bundle, "stock_id_allowlist", []) or [],
            subject=what,
        )
    else:
        result = check_scoped(defs, baseline, manifests)
    for w in result.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    # Symptoms and alerts install by name (install.py): a stock name is a
    # collision the id check cannot see. A warning (review W8).
    warn_bundle_stock_names(bundle)
    if result.errors:
        raise BundleValidationError(_guard.guard_failure_text(result, what))


# ---------------------------------------------------------------------------
# Content-import choke point
# ---------------------------------------------------------------------------

class StockIdRefused(RuntimeError):
    """Content about to be imported carries stock ids (or the check cannot run)."""


#: The owning manifest of the imports in progress: (label, entries), set by
#: ``import_allowlist`` around a bundle sync. None: no owning manifest.
_IMPORT_SCOPE: "contextvars.ContextVar[Optional[Tuple[str, List[AllowlistEntry]]]]" = (
    contextvars.ContextVar("vcfcf_stock_id_import_scope", default=None)
)


@contextlib.contextmanager
def import_allowlist(manifest: str, entries: Sequence[AllowlistEntry]) -> Iterator[None]:
    """Declare the manifest that owns every content import made inside.

    ``sync_bundle`` wraps its handlers in this with the bundle's own
    ``stock_id_allowlist``, so an import it makes honours that bundle's
    entries and no other manifest's. Outside it (a standalone per-type
    sync) an import has no owning manifest and nothing can be allowlisted.
    """
    token = _IMPORT_SCOPE.set((str(manifest), list(entries or [])))
    try:
        yield
    finally:
        _IMPORT_SCOPE.reset(token)


def refuse_stock_ids_in_zip(zip_bytes: bytes, what: str = "content zip") -> List[str]:
    """Raise ``StockIdRefused`` if ``zip_bytes`` defines a stock id.

    Called on every content-zip import the factory sends. Only the entries
    of the manifest declared by ``import_allowlist`` apply. A member the
    scanner cannot read refuses the import. Returns the allowlist warnings
    (already printed) so a caller can surface them.
    """
    try:
        baseline = load_baseline()
    except StockIdBaselineError as exc:
        raise StockIdRefused(f"stock-id guard cannot run, import refused: {exc}") from exc
    scope = _IMPORT_SCOPE.get()
    allow = scope[1] if scope else []
    unreadable: List[Unreadable] = []
    defs = _guard.scan_bytes(zip_bytes, what, unreadable=unreadable)
    if unreadable:
        raise StockIdRefused(_guard.unreadable_failure_text(unreadable, what) + "\nImport refused.")
    result = check_definitions(defs, baseline=baseline, allowlist=allow)
    warnings = [w for w in result.warnings if w.startswith("ALLOWLISTED")]
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if result.errors:
        tail = "\nImport refused."
        if scope is None:
            tail += (" (No owning manifest: a stock_id_allowlist entry applies only to "
                     "an import made by syncing the bundle that declares it.)")
        raise StockIdRefused(_guard.guard_failure_text(result, what) + tail)
    return warnings


# ---------------------------------------------------------------------------
# stock-id-check (standalone, read-only)
# ---------------------------------------------------------------------------

def cmd_stock_id_check(args) -> int:
    """List every definition in a pak / zip / export / directory whose id is stock.

    Exit 0: every definition read was compared, none is stock. 2: stock ids
    found. 1: the baseline cannot be loaded, a path is missing, something
    could not be read, or nothing was found to check.
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
    return _guard.standalone_check(args.paths, baseline)


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
            found = {_guard.normalize_id(d.id) for d in _scan_source(a, "factory artifacts")}
            ids |= found
            notes.append(f"{len(found)} ids in built artifacts under {a}")
    return ids, notes


class _UnreadableSource(RuntimeError):
    """A generator input holds content the scanner cannot read."""


def _scan_source(path, what: str) -> List[Definition]:
    """Scan one generator input; refuse it when anything in it is unreadable.

    An unread member of an export is a missing observation (a hole); an
    unread member of factory or excluded content is a missing exclusion (a
    false stock id). Either way the baseline would be wrong, so it is not
    written.
    """
    unreadable: List[Unreadable] = []
    defs = _guard.scan_path(path, unreadable=unreadable)
    if unreadable:
        raise _UnreadableSource(_guard.unreadable_failure_text(unreadable, f"{what} {path}"))
    return defs


#: A presence ratio this close to the threshold (in percentage points) is
#: flagged on every regeneration (review W4).
PRESENCE_MARGIN_POINTS = 10.0


def _presence_report(build, threshold: float) -> List[str]:
    lines = []
    for pr in build.presence:
        pct = 100.0 * pr.ratio
        near = abs(pct - 100.0 * threshold) < PRESENCE_MARGIN_POINTS and not pr.excluded
        state = "installed" if pr.installed else "not installed"
        line = (f"presence {pr.package} on {pr.instance}: {pr.present}/{pr.total} "
                f"({pct:.0f}%), {state}")
        if pr.excluded:
            line += " (excluded content: every id it defines is left out regardless)"
        if near:
            line = ("WARNING: " + line + f"; within {PRESENCE_MARGIN_POINTS:.0f} points of the "
                    f"{100 * threshold:.0f}% threshold: a small change to this package flips "
                    f"whether its ids are evidence. Read every added or dropped id in the "
                    f"baseline diff, or pass it as --exclude-content if its ids are never stock")
        lines.append(line)
    for label, n in sorted(build.masked.items()):
        line = f"excluded {label}: keeps out {n} id(s) that would otherwise be stock"
        if n:
            line = ("WARNING: " + line + " under the presence rule; excluded content "
                    "that carries copied stock ids hides them. Check that this checkout "
                    "is the re-identified one, and read those ids in the candidates report")
        lines.append(line)
    return lines


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
    try:
        return _cmd_stock_id_baseline(args)
    except _UnreadableSource as exc:
        print(f"ERROR: {exc}\nBaseline not written.", file=sys.stderr)
        return 1


def _cmd_stock_id_baseline(args) -> int:
    observations: List[_gen.Observation] = []
    sources: List[dict] = []
    for spec in args.export or []:
        version, label, path = _split_spec(spec, 3, "--export")
        defs = _scan_source(path, "export")
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
        defs = [d for d in _scan_source(path, "custom-scope export") if not d.attrs.get("in_policy")]
        custom_ids.extend((d.type, d.id) for d in defs)
        sources.append({"kind": "custom-scope export (negative evidence)",
                        "definitions": len(defs)})
    known = {}
    for spec in args.known_content or []:
        label, path = _split_spec(spec, 2, "--known-content")
        known[label] = _scan_source(path, "known content")
    excluded = {}
    for spec in args.exclude_content or []:
        label, path = _split_spec(spec, 2, "--exclude-content")
        if not Path(path).exists():
            print(f"ERROR: --exclude-content {label}: not found: {path}", file=sys.stderr)
            return 1
        excluded[label] = _scan_source(path, "excluded content")
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
        excluded_groups=excluded,
        custom_ids=custom_ids,
        factory_ids=factory_ids,
        exclude_name_markers=markers,
        exclude_adapter_kind_prefixes=list(args.exclude_adapter_kind or []),
        installed_threshold=args.installed_threshold,
        sources=sources,
        generated=args.generated or _dt.date.today().isoformat(),
        regenerate=(
            "python3 -m vcfcf_packaging stock-id-baseline --export <version>=<label>=<path> ... "
            "(the exact command for the committed file: knowledge/context/stock_id_guard.md, "
            "section 'The committed baseline')"
        ),
    )
    for line in _presence_report(build, args.installed_threshold):
        print(line, file=sys.stderr)
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
                      help="a third-party pak or content repo that may be installed on a source "
                           "(judged by --installed-threshold; its presence ratios are printed)")
    pgen.add_argument("--exclude-content", action="append", metavar="LABEL=PATH",
                      help="content whose ids are never stock (a registered, re-identified "
                           "third-party fork): every id it defines is left out, no threshold")
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
