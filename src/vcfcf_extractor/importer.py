"""``python3 -m vcfcf_extractor import-local``: offline conversion of existing
VCF Operations content files to factory YAML, written into a target layout,
checked by the stock-id guard and verified through the real loaders and
renderers.

The parse, map, account and compare logic is ``vcfcf_core.importer``; this
module owns what the core may not do: write files, read the stock-id
baseline through the factory, load the written YAML with the factory,
third-party and pak loaders, and print the report. No network access
anywhere. How-to: ``knowledge/context/authoring/importer_offline_conversion.md``.

Writing is staged: the tree is written into a temporary sibling of
``--out``, verified there, and moved into place only when the run
succeeds (or succeeds with partial results ``--allow-partial`` accepts).
On any other outcome ``--out`` is untouched. ``--force`` replaces only a
directory carrying this importer's marker file (:data:`MARKER`) from an
earlier run, whole, so no file of the earlier run is left behind.

Exit status: 0 success; 1 an object failed, lost data, is of an
unsupported type, is not deliverable to ``--target-min``, or differed on
verification (``--allow-partial`` accepts these, except in the pak layout a
pak check failure or a dashboard the stated target cannot import), or an
input could not be read (never accepted: what cannot be read was not
checked); 2 a usage or safety refusal, or the tree could not be written
(nothing written); 3 the stock-id guard refused the result (nothing
written); 4 verification compared nothing; 5 an internal error in the
converter on at least one object (never accepted; the other objects are
reported as usual).
"""
from __future__ import annotations

import contextlib
import copy
import dataclasses
import io
import json
import os
import re
import shutil
import sys
import tempfile
import types
import warnings
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vcfcf_core.importer import compare as _cmp
from vcfcf_core.importer.convert import (
    ConvertOptions,
    Plan,
    TYPE_DIRS,
    dump_yaml,
    mint_namespace_uuid,
    norm_id,
    parse_describe_map,
    parse_id_list,
    parse_rename_map,
    parse_tsv_map,
    plan_conversion,
)
from vcfcf_core.importer.inputs import CONTENT_TYPES, scan_inputs
from vcfcf_core.importer.kinds import KindMap, parse_kind_map
from vcfcf_core.importer.model import Mark

EXIT_OK, EXIT_PARTIAL, EXIT_USAGE, EXIT_STOCK, EXIT_NOTHING, EXIT_INTERNAL = 0, 1, 2, 3, 4, 5
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RENDERED_PREFIX = {"symptom": "SymptomDefinition-", "alert": "AlertDefinition-"}
#: Written into every --out this importer produces; --force replaces only a
#: directory that carries it.
MARKER = ".vcfcf-import-local"
#: Written into an explicit --report-dir; the report files there are
#: overwritten only when it carries it.
REPORT_MARKER = ".vcfcf-import-local-report"
REPORT_FILES = ("report.json", "id_map.tsv", "bundled_content.yaml")


def add_parser(sub) -> None:
    p = sub.add_parser(
        "import-local",
        help="Convert existing content files (views, dashboards, reports, alerts, symptoms, "
             "recommendations, super metrics; directories, zips, paks) to factory YAML, offline",
        description=(
            "Convert a tree of existing VCF Operations content files to factory YAML, one file per\n"
            "object, into a content/, third-party project or SDK pak layout. Offline: no instance,\n"
            "no network. Inputs: files, directories (recursive), content-export zips, .pak files.\n"
            "\n"
            "Ids and names are explicit decisions: --ids keep|mint or --id-map, and --naming.\n"
            "The stock-id guard runs on the result; verification (on unless --no-verify) re-loads the\n"
            "written YAML through the real loaders of the layout, renders it and compares it with the\n"
            "source. The tree is written to a temporary sibling and moved into --out only on success.\n"
            "\n"
            "How-to: knowledge/context/authoring/importer_offline_conversion.md\n"
            "\n"
            "Example:\n"
            "  python3 -m vcfcf_extractor import-local 'Management Pack/content' \\\n"
            "    --out third_party/my-port --layout third-party --project-name my-port \\\n"
            "    --ids mint --naming unprefixed\n"
        ),
        formatter_class=__import__("argparse").RawDescriptionHelpFormatter,
    )
    p.add_argument("inputs", nargs="+", metavar="INPUT", help="file, directory, zip or .pak (read only)")
    p.add_argument("--out", required=True, metavar="DIR",
                   help="target directory: absent or empty, or (with --force) one this importer wrote")
    p.add_argument("--layout", required=True, choices=("content", "third-party", "pak"),
                   help="content: a factory content/ tree; third-party: a third_party/<project> with "
                        "PROJECT.yaml; pak: an SDK pak's bundled-content folders")
    ids = p.add_mutually_exclusive_group(required=True)
    ids.add_argument("--ids", choices=("keep", "mint"),
                     help="keep: carry the source ids; mint: a deterministic new UUID for every object "
                          "(version 5 from --mint-namespace and the source type and id; a rerun gives the "
                          "same ids), every reference rewritten, the mapping written to the report directory")
    ids.add_argument("--id-map", metavar="TSV", action="append",
                     help="old id<TAB>new id rows for some objects; the rest keep theirs (repeatable; "
                          "an old id listed in two files is an error)")
    p.add_argument("--mint-namespace", metavar="TEXT",
                   help="--ids mint: the text the minted ids derive from (default: 'project:<--project-name>'; "
                        "one of the two is required with --ids mint)")
    p.add_argument("--naming", required=True, choices=("unprefixed", "factory-prefixed"),
                   help="unprefixed: names as in the source; factory-prefixed: '[VCF CF] ' on every name, "
                        "references follow")
    p.add_argument("--rename", metavar="TSV",
                   help="type<TAB>old name (or id)<TAB>new name rows, applied before --naming; the type "
                        "(view, dashboard, ...) keeps a rename from crossing types")
    p.add_argument("--drop", metavar="TSV", action="append",
                   help="ids (first column) not to emit; references to them stay raw ids (repeatable)")
    p.add_argument("--map-kind", metavar="TSV", action="append",
                   help="old adapter kind<TAB>old resource kind or *<TAB>new adapter kind<TAB>new resource kind or * "
                        "rows: re-point content to another kind at every place a kind sits (never a text "
                        "replace); a resource kind row wins over a * row; a place the map cannot re-point with "
                        "certainty stops that object (repeatable)")
    p.add_argument("--describe", metavar="TSV", action="append",
                   help="type<TAB>name or id<TAB>new description rows (\\n, \\t, \\\\ escapes): replace an "
                        "object's description, matched as --rename matches, before renaming (repeatable)")
    p.add_argument("--target-min", choices=("8.18.7", "9.0.2", "9.1.1"),
                   help="oldest VCF Operations the output must import on: omit: entries proven only on "
                        "newer builds are not emitted (each deviation listed); a dashboard with a widget "
                        "type the target lacks is not deliverable to it")
    p.add_argument("--prefer-source", action="append", default=[], metavar="FRAGMENT",
                   help="when one id is defined differently in several files, the copy from the one file "
                        "whose path (relative to its input) contains FRAGMENT wins; a fragment matching "
                        "two of those files, or none, is an error (repeatable)")
    p.add_argument("--project-name", metavar="NAME", help="third-party layout: PROJECT.yaml name (default: "
                                                          "--out dir name); also the default mint namespace")
    p.add_argument("--report-dir", metavar="DIR", help="where the report, id map and pak snippet go "
                                                       "(default: <out>/import-report)")
    vg = p.add_mutually_exclusive_group()
    vg.add_argument("--verify", action="store_true", default=True,
                    help="re-load, render and compare every written object (the default)")
    vg.add_argument("--no-verify", dest="verify", action="store_false",
                    help="skip verification (a warning says nothing was checked)")
    p.add_argument("--allow-partial", action="store_true",
                   help="exit 0 (and write) even when objects failed, lost data, are unsupported or differ "
                        "on verification")
    p.add_argument("--force", action="store_true",
                   help="replace a non-empty --out that this importer wrote before (it carries "
                        f"{MARKER}); anything else is refused")
    p.add_argument("--dry-run", action="store_true", help="plan and report; write nothing")


# ------------------------------------------------------------------- helpers
def _say(msg: str = "") -> None:
    print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _rel_location(loc: str, roots: List[Path]) -> str:
    for r in roots:
        rs = str(r.resolve()) if r.is_dir() else str(r.resolve().parent)
        for cand in (rs, str(r) if r.is_dir() else str(r.parent)):
            if cand and loc.startswith(cand):
                return loc[len(cand):].lstrip("/\\") or r.name
    return loc


def _rendered_id(t: str, fid: str) -> str:
    return _RENDERED_PREFIX.get(t, "") + fid


# ---------------------------------------------------------- completeness
def _completeness(scan, inputs: List[Path]) -> Tuple[List[str], list]:
    """Cross-check the converter's findings with the stock-id guard's own
    scanner: every definition it sees (outside policy exports) must be one
    the converter found."""
    from vcfcf_core.stock_ids.guard import scan_path
    unreadable: list = []
    seen = {(o.type, norm_id(o.type, o.id)) for o in scan.objects}
    refused = {u.location for u in scan.unreadable}
    missed = []
    for p in inputs:
        for d in scan_path(p, unreadable=unreadable):
            if d.attrs.get("in_policy") or d.location in refused:
                continue
            if (d.type, norm_id(d.type, d.id)) not in seen:
                missed.append(f"{d.location}: {d.type} {d.id} ({d.name!r}) is a definition the stock-id "
                              f"scanner finds but the converter did not read")
    return missed, unreadable


# ------------------------------------------------------------ stock guard
def _stock_guard(plan: Plan) -> Tuple[List[str], str]:
    from vcfcf_core.stock_ids.guard import Definition, check_definitions, coverage_text, load_baseline
    baseline = load_baseline()
    defs = [Definition(e.type, _rendered_id(e.type, e.id), e.name, e.relpath) for e in plan.emitted]
    result = check_definitions(defs, baseline=baseline)
    return result.errors, coverage_text(defs, baseline)


# ----------------------------------------------------------------- write
def _id_map_text(plan: Plan) -> str:
    lines = []
    if plan.mint_namespace:
        lines.append(f"# mint-namespace: {plan.mint_namespace} (uuid {mint_namespace_uuid(plan.mint_namespace)}); "
                     f"rerun with the same --mint-namespace to get the same ids")
    lines.append("type\told_id\tnew_id\tname\tsource_name\tfile")
    for e in plan.emitted:
        new = _rendered_id(e.type, e.id) if e.type in _RENDERED_PREFIX else e.id
        src_name = e.source_name if e.source_name != e.name else ""
        lines.append(f"{e.type}\t{e.source_id}\t{new}\t{e.name}\t{src_name}\t{e.relpath}")
    return "\n".join(lines) + "\n"


def _bundled_content_text(plan: Plan, args) -> str:
    bc: Dict[str, List[str]] = defaultdict(list)
    kinds = set()
    for e in plan.emitted:
        bc[TYPE_DIRS[e.type]].append(e.relpath)
        if e.type in ("symptom", "alert") and e.yaml_tree.get("adapter_kind"):
            kinds.add(str(e.yaml_tree["adapter_kind"]))
    head = ["# Merge into the pak's adapter.yaml (paths are relative to it)."]
    if args.naming == "unprefixed":
        head.append("# The names are unprefixed: also set  content_naming: unprefixed")
    own = plan.kind_map.new_adapter_kinds() if plan.kind_map is not None else set()
    if len(own) == 1:
        # --map-kind re-pointed content to one adapter kind: the pak's own,
        # so content on it is not foreign.
        (ak,) = own
        head.append(f"# --map-kind re-pointed content to {ak}, taken as the pak's own adapter kind (content on it "
                    f"is not foreign)")
        kinds.discard(ak)
        if kinds:
            head.append(f"# Symptoms and alerts here also target {', '.join(sorted(kinds))}: also set  "
                        f"content_foreign_adapter_kinds: [{', '.join(sorted(kinds))}]")
    elif kinds:
        head.append(f"# Symptoms and alerts here target {', '.join(sorted(kinds))}: unless that is the pak's own "
                    f"adapter kind, also set  content_foreign_adapter_kinds: [{', '.join(sorted(kinds))}]")
    return "\n".join(head) + "\n" + dump_yaml({"bundled_content": dict(bc)})


def _write_tree(plan: Plan, root: Path, args, out: Path, report_inside: Optional[Path]) -> List[str]:
    """Write every emitted object (and PROJECT.yaml, the marker, the report
    files that live inside --out) under ``root`` (the staging directory).
    Returns notes."""
    notes = []
    for e in plan.emitted:
        p = root / e.relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(e.text, encoding="utf-8")
    if args.layout == "third-party":
        proj = root / "PROJECT.yaml"
        old = out / "PROJECT.yaml"
        if old.is_file():
            shutil.copyfile(old, proj)
            notes.append(f"KEPT {old} from the earlier run (its attribution may have been edited); every other file "
                         f"in {out} is replaced")
        else:
            name = args.project_name or out.name
            proj.write_text(dump_yaml({
                "name": name,
                "display_name": name,
                "description": "Converted offline by `python3 -m vcfcf_extractor import-local`. "
                               "Fill in the attribution and license before release.",
                "factory_native": False,
                "released": False,
            }), encoding="utf-8")
    (root / MARKER).write_text(json.dumps({
        "written_by": "python3 -m vcfcf_extractor import-local", "layout": args.layout,
        "files": sorted(e.relpath for e in plan.emitted)}, indent=1) + "\n", encoding="utf-8")
    if report_inside is not None:
        rd = root / report_inside
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "id_map.tsv").write_text(_id_map_text(plan), encoding="utf-8")
        if args.layout == "pak":
            (rd / "bundled_content.yaml").write_text(_bundled_content_text(plan, args), encoding="utf-8")
    return notes


def _write_external_report(report_dir: Path, files: Dict[str, str]) -> None:
    """Write the report files into an explicit --report-dir outside --out:
    staged beside it and moved in file by file (``os.replace``)."""
    report_dir.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".import-local-report-", dir=report_dir))
    try:
        for name, text in files.items():
            (stage / name).write_text(text, encoding="utf-8")
        (stage / REPORT_MARKER).write_text("written by python3 -m vcfcf_extractor import-local\n", encoding="utf-8")
        for f in stage.iterdir():
            os.replace(f, report_dir / f.name)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ---------------------------------------------------------------- verify
class _Loaded:
    def __init__(self):
        self.views, self.dashboards, self.supermetrics = [], [], []
        self.symptoms, self.alerts, self.reports, self.recommendations = [], [], [], []
        self.sm_paths: List[Path] = []
        self.pak_problems: List[str] = []
        self.load_errors: List[str] = []
        self.notes: List[str] = []


def _per_file_load(plan: Plan, root: Path, layout: str, only=None) -> Tuple[_Loaded, Dict[str, str]]:
    """Load every emitted file alone with the layout's per-type loader
    (prefix rule on for content/, the layout's folder default, dashboards
    validated against the loaded views). Returns the loaded objects and
    ``{relpath: error}`` for each file a loader refuses."""
    from vcfcf_core.alerts.loader import load_file as load_alert, load_recommendation_file
    from vcfcf_core.dashboards.loader import load_dashboard, load_view
    from vcfcf_core.reports.loader import load_file as load_report
    from vcfcf_core.supermetrics.loader import load_file as load_sm
    from vcfcf_core.symptoms.loader import load_file as load_sym
    enforce = layout == "content"
    default_np = "" if layout == "third-party" else "VCF Content Factory"
    L = _Loaded()
    errors: Dict[str, str] = {}
    order = sorted(plan.emitted, key=lambda e: CONTENT_TYPES.index(e.type))
    if only is not None:
        # Later rounds re-check only what references other objects; views
        # are reloaded too because dashboards validate against them.
        order = [e for e in order if e.type in only or e.type == "view"]
    views_by_name = {}
    index = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for e in order:
            path = root / e.relpath
            try:
                if e.type == "view":
                    o = load_view(path, enforce_framework_prefix=enforce)
                    views_by_name[o.name] = o
                    L.views.append(o)
                elif e.type == "dashboard":
                    o = load_dashboard(path, enforce_framework_prefix=enforce, default_name_path=default_np)
                    o.validate(views_by_name, enforce_framework_prefix=enforce)
                    L.dashboards.append(o)
                elif e.type == "report":
                    if index is None:
                        # The report loader re-reads every view and dashboard
                        # YAML per report to index name -> id; index the ones
                        # that loaded this round as id/name stubs instead (the
                        # same two fields it reads), so a large tree stays fast.
                        index = Path(tempfile.mkdtemp(prefix="index-", dir=root.parent))
                        for sub, objs in (("views", L.views), ("dashboards", L.dashboards)):
                            (index / sub).mkdir()
                            for i, o in enumerate(objs):
                                (index / sub / f"{i}.yaml").write_text(
                                    dump_yaml({"id": o.id, "name": o.name}), encoding="utf-8")
                    L.reports.append(load_report(path, index / "views", index / "dashboards",
                                                 enforce_framework_prefix=enforce))
                elif e.type == "supermetric":
                    L.supermetrics.append(load_sm(path, enforce_framework_prefix=enforce))
                elif e.type == "symptom":
                    L.symptoms.append(load_sym(path, enforce_framework_prefix=enforce))
                elif e.type == "alert":
                    L.alerts.append(load_alert(path, enforce_framework_prefix=enforce))
                else:
                    L.recommendations.append(load_recommendation_file(path, enforce_framework_prefix=enforce))
            except Exception as exc:
                errors[e.relpath] = f"{type(exc).__name__}: {exc}"
    return L, errors


def _load_check(plan: Plan, layout: str, args) -> List[str]:
    """Stage the plan in a temporary directory and drop, as failures, every
    object whose written YAML a loader refuses, repeating until the rest
    loads (a dashboard whose view was refused then fails too). Nothing is
    written to --out by this step. Returns one line per dropped object."""
    from vcfcf_core.importer.convert import Failure
    lines: List[str] = []
    base = Path(tempfile.mkdtemp(prefix="vcfcf-import-check-"))
    tmp = base / "tree"  # the staged output; report index stubs go beside it
    try:
        for e in plan.emitted:
            f = tmp / e.relpath
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(e.text, encoding="utf-8")
        only = None
        removed: set = set()
        removed_ids: set = set()
        while True:
            _, errors = _per_file_load(plan, tmp, layout, only)
            only = {"dashboard", "report", "alert"}
            # A per-file load does not see every reference (an alert's
            # symptoms and recommendations, a navigation target, every
            # super metric reference), so an object naming one that was
            # refused is refused too, to a fixed point.
            grew = True
            while grew:
                grew = False
                for e in plan.emitted:
                    if e.relpath in errors:
                        continue
                    for t, n in _named_refs(e):
                        if (t, n) in removed or (t, n) in {(x.type, x.name) for x in plan.emitted
                                                           if x.relpath in errors}:
                            errors[e.relpath] = f"names {t} {n!r}, which was refused (see its own failure)"
                            grew = True
                            break
                    else:
                        for t, i in _id_refs(e):
                            if (t, i) in removed_ids or (t, i) in {(x.type, x.id.lower()) for x in plan.emitted
                                                                   if x.relpath in errors}:
                                errors[e.relpath] = f"references {t} {i}, which was refused (see its own failure)"
                                grew = True
                                break
            if not errors:
                break
            keep = []
            for e in plan.emitted:
                if e.relpath in errors:
                    removed.add((e.type, e.name))
                    removed_ids.add((e.type, e.id.lower()))
                    reason = f"the written YAML does not load: {errors[e.relpath]}"
                    reason = reason.replace(str(tmp) + "/", "")
                    plan.failures.append(Failure(e.type, e.source_id, e.name, list(e.source.locations), reason))
                    (tmp / e.relpath).unlink()
                    lines.append(f"FAILED {e.type} {e.source_id} {e.name!r}: {reason}")
                else:
                    keep.append(e)
            plan.emitted = keep
        plan.id_table = [(e.type, e.source_id, e.id, e.name) for e in plan.emitted]
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return lines


_SM_NAME_REF = re.compile(r'@?supermetric:"([^"]+)"')
_SM_ID_REF = re.compile(r"sm_(" + _UUID.pattern + ")")


def _yaml_strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _yaml_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _yaml_strings(v)
    elif isinstance(node, str):
        yield node


def _named_refs(e) -> List[Tuple[str, str]]:
    """The (type, name) references in an emitted YAML that a per-file load
    does not resolve: alert symptoms and recommendations, navigation
    targets, and every super metric named by name (``@supermetric:"<name>"``
    in a formula, ``supermetric:"<name>"`` in a view column). Views named by
    dashboards and reports are checked by the per-file load itself."""
    y = e.yaml_tree
    out: List[Tuple[str, str]] = []
    if e.type == "alert":
        for st in (y.get("symptom_sets") or {}).get("sets") or []:
            out += [("symptom", s.get("name")) for s in st.get("symptoms") or []]
        out += [("recommendation", r.get("name")) for r in y.get("recommendations") or []]
    elif e.type == "dashboard":
        for w in y.get("widgets") or []:
            out += [("dashboard", n.get("dashboard")) for n in w.get("navigations") or [] if n.get("dashboard")]
    for s in _yaml_strings(y):
        out += [("supermetric", m.group(1)) for m in _SM_NAME_REF.finditer(s) if m.group(1) != e.name]
    return out


def _id_refs(e) -> List[Tuple[str, str]]:
    """The (type, id) references a per-file load does not resolve: a super
    metric key ``sm_<uuid>`` in any string (a symptom condition, a view
    filter, a widget metric, HTML)."""
    own = str(e.yaml_tree.get("id", "")).lower() if e.type == "supermetric" else None
    return [("supermetric", m.group(1).lower()) for s in _yaml_strings(e.yaml_tree)
            for m in _SM_ID_REF.finditer(s) if m.group(1).lower() != own]


def _load_layout(plan: Plan, out: Path, layout: str) -> _Loaded:
    """The written tree through the layout's real loader: the pak
    ``_load_bundled_content`` (with the pak checks), the factory bundle
    loader on PROJECT.yaml, or the factory per-type loaders on content/."""
    L = _Loaded()
    rels = defaultdict(list)
    for e in plan.emitted:
        rels[e.type].append(e.relpath)
    L.sm_paths = [out / r for r in rels["supermetric"]]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if layout == "pak":
            from vcfcf_managementpacks.sdk_builder import (
                _load_bundled_content, check_bundled_content_references, check_bundled_version_floors,
            )
            raw = {"bundled_content": {TYPE_DIRS[t]: rels[t] for t in CONTENT_TYPES if rels[t]}}
            bundled = _load_bundled_content(raw, out, out)
            (L.views, L.dashboards, L.supermetrics, L.symptoms, L.alerts, L.reports, L.recommendations) = bundled
            L.pak_problems += check_bundled_version_floors(bundled)
            L.pak_problems += check_bundled_content_references(L.symptoms, L.alerts, L.recommendations)
        elif layout == "third-party":
            from vcfcf_packaging.loader import load_bundle
            b = load_bundle(out / "PROJECT.yaml")
            L.views, L.dashboards, L.supermetrics = b.views, b.dashboards, b.supermetrics
            L.symptoms, L.alerts, L.reports, L.recommendations = b.symptoms, b.alerts, b.reports, b.recommendations
        else:
            from vcfcf_alerts.loader import load_dir as load_alerts, load_recommendations
            from vcfcf_dashboards.loader import load_all
            from vcfcf_reports.loader import load_file as load_report
            from vcfcf_supermetrics.loader import load_dir as load_sms
            from vcfcf_symptoms.loader import load_dir as load_syms
            L.supermetrics = load_sms(out / "supermetrics")
            L.views, L.dashboards = load_all(out / "views", out / "dashboards")
            L.reports = [load_report(out / r, out / "views", out / "dashboards") for r in rels["report"]]
            L.symptoms = load_syms(out / "symptoms")
            L.alerts = load_alerts(out / "alerts")
            L.recommendations = load_recommendations(out / "recommendations")
    return L


def _expected_xml(src, e, plan: Plan):
    """The source element with the intended renames and id rewrites applied."""
    el = copy.deepcopy(src)
    rw = plan.id_rewrites
    rec_rw = {k: v for k, v in rw.items() if not _UUID.fullmatch(k)}

    def fix(s: str) -> str:
        return _UUID.sub(lambda m: rw.get(m.group(0).lower(), m.group(0)), s)

    exact = plan.exact_id_rewrites
    for x in el.iter():
        for k, v in list(x.attrib.items()):
            if x.tag == "Recommendation" and k in ("key", "ref") and v in rec_rw:
                x.set(k, rec_rw[v])
            elif x.tag in ("SymptomSet", "Symptom") and k == "ref" and v in exact:
                x.set(k, exact[v])
            else:
                x.set(k, fix(v))
        if x.text and not len(x):
            x.text = fix(x.text)
    if e.type in ("view", "report"):
        t = el.find("Title")
        if t is not None:
            t.text = e.name
    elif e.type in ("alert", "symptom"):
        el.set("name", e.name)
    if e.type in ("alert", "symptom"):
        el.set("id", _rendered_id(e.type, e.id))
    elif e.type in ("view", "report"):
        el.set("id", e.id)
    if e.described is not None:
        # --describe: the intended new description (counted and reported
        # as a replaced description, never as identical or a loss)
        if e.type == "alert":
            el.set("description", e.described[1])
        else:
            d = el.find("Description")
            if d is None:
                d = ET.SubElement(el, "Description")
            d.text = e.described[1]
    return el


def _expected_dashboard(e, plan: Plan) -> dict:
    db = copy.deepcopy(e.source.payload)
    name, npath = db.get("name", ""), db.get("namePath")
    if npath and name.startswith(npath + "/"):
        db["name"] = f"{npath}/{e.name}"
    else:
        db["name"] = e.name
    if e.described is not None:
        db["description"] = e.described[1]
    exact = plan.exact_id_rewrites
    if exact:
        for w in db.get("widgets") or []:
            c = w.get("config") if isinstance(w, dict) else None
            for a in (c.get("alertDefinitions") or []) if isinstance(c, dict) else []:
                if isinstance(a, dict) and a.get("id") in exact:
                    a["id"] = exact[a["id"]]
    return db


def _classify(t: str, path: str, kind: str) -> str:
    from vcfcf_core.importer.flat import generic
    return f"{t}: {generic(path)} [{kind}]"


def _sm_context(sm):
    """A super metric as context for rendering another one alone: its name
    and id resolve references to it, its own formula is not rendered."""
    c = copy.copy(sm)
    c.formula = "0"
    return c


def _render_each(objs: list, render, key, context=None):
    """``render(objs) -> {key(o): rendered}``, or, when the batch raises,
    each object rendered on its own (with the others as ``context(o)`` where
    a render needs the whole set): ``({key: rendered}, {key: exception})``."""
    if not objs:
        return {}, {}
    try:
        return render(list(objs)), {}
    except Exception:
        pass
    out, errs = {}, {}
    for o in objs:
        k = key(o)
        others = [context(x) for x in objs if x is not o] if context else []
        try:
            hit = render([o] + others).get(k)
            if hit is None:
                raise RuntimeError("not in the render")
            out[k] = hit
        except Exception as exc:
            errs[k] = exc
    return out, errs


def _translate(mark: Mark, rewrites: Dict[str, str]) -> Mark:
    """A mark recorded on the source (old ids) as the expected side spells
    it (intended id rewrites applied, lower case)."""
    path = _UUID.sub(lambda m: rewrites.get(m.group(0).lower(), m.group(0).lower()), mark.path)
    return dataclasses.replace(mark, path=path) if path != mark.path else mark


def _empty_verify() -> dict:
    return {"objects": 0, "fields": 0, "identical": 0, "deviation_only": 0, "only_losses": 0, "differ": 0,
            "per_type": defaultdict(Counter), "classes": Counter(), "class_objects": defaultdict(set),
            "set_aside": Counter(), "deviations": Counter(), "loss_classes": Counter(),
            "loss_class_objects": defaultdict(set), "objects_detail": [], "load_errors": [], "pak_problems": [],
            "guard": [], "intended_only": 0, "kind_objects": 0, "kind_refs": 0, "described": 0}


def _verify(plan: Plan, out: Path, layout: str):
    """Verify the staged tree (``_verify_tree``). Per-object render and
    compare failures are that object's load error; anything else that
    raises stops verification with a load error, never a traceback."""
    try:
        return _verify_tree(plan, out, layout)
    except Exception as exc:
        res = _empty_verify()
        res["load_errors"].append(f"verification stopped: {type(exc).__name__}: {exc}")
        return res


def _verify_tree(plan: Plan, out: Path, layout: str):
    from vcfcf_core.alerts.render import render_alert_content_xml
    from vcfcf_core.dashboards.render import render_dashboards_bundle_json, render_views_xml
    from vcfcf_core.packaging.assembly import _render_supermetrics_dict
    from vcfcf_core.reports.render import render_report_xml

    res = _empty_verify()
    try:
        L = _load_layout(plan, out, layout)
    except Exception as exc:  # the real loader refused the written tree
        res["load_errors"].append(f"the {layout} loader refused the written tree: {type(exc).__name__}: {exc}")
        return res
    res["pak_problems"] = L.pak_problems

    # the stock-id guard on the loaded objects, through the rendered AlertContent
    from vcfcf_core.stock_ids.guard import bundled_definitions, check_definitions, load_baseline
    try:
        ac = render_alert_content_xml(L.symptoms, L.alerts, L.recommendations) if (
            L.symptoms or L.alerts or L.recommendations) else None
        defs = bundled_definitions(views=L.views, dashboards=L.dashboards, supermetrics=L.supermetrics,
                                   reports=L.reports, symptoms=L.symptoms, alerts=L.alerts,
                                   recommendations=L.recommendations, alert_content_xml=ac)
        res["guard"] = check_definitions(defs, baseline=load_baseline()).errors
    except Exception as exc:
        res["load_errors"].append(f"stock-id check on the loaded tree: {type(exc).__name__}: {exc}")

    by_path = {}
    for group in (L.views, L.dashboards, L.supermetrics, L.symptoms, L.alerts, L.reports, L.recommendations):
        for o in group:
            src = getattr(o, "source_path", None) or getattr(o, "source_file", None)
            if src:
                by_path[str(Path(src).resolve())] = o
    views_by_name = {v.name: v for v in L.views}
    # The batch renders, each falling back to one object at a time so a
    # renderer exception is that object's error, never a traceback.
    try:
        if layout == "pak":
            from vcfcf_supermetrics.loader import sm_id_map
            sm_map = sm_id_map(L.sm_paths)
            view_kw = {"sm_map": sm_map, "sm_scope_active": True}
        else:
            view_kw = {"sm_map": {s.name: s.id for s in L.supermetrics}}
    except Exception as exc:
        res["load_errors"].append(f"super metric id map of the loaded tree: {type(exc).__name__}: {exc}")
        return res
    rendered_views, view_errors = _render_each(
        L.views, lambda vs: {vd.get("id").lower(): vd
                             for vd in ET.fromstring(render_views_xml(vs, **view_kw)).iter("ViewDef")},
        key=lambda v: str(v.id).lower())
    sm_render, sm_errors = _render_each(
        L.supermetrics, lambda sms: _render_supermetrics_dict(types.SimpleNamespace(supermetrics=sms)),
        key=lambda sm: sm.id, context=_sm_context)
    widget_ids: Dict[str, str] = {}
    for e in plan.emitted:
        if e.type != "dashboard":
            continue
        d = by_path.get(str((out / e.relpath).resolve()))
        if d is None:
            continue
        for sw, yw in zip(e.source.payload.get("widgets") or [], d.widgets):
            widget_ids[sw.get("id")] = yw.widget_id

    rewrites = dict(plan.id_rewrites)
    for e in plan.emitted:
        obj = by_path.get(str((out / e.relpath).resolve()))
        detail = {"type": e.type, "name": e.name, "file": e.relpath}
        if obj is None:
            res["load_errors"].append(f"{e.relpath}: written but not loaded by the {layout} loader")
            continue
        try:
            if e.type == "view":
                rv = rendered_views.get(e.id.lower())
                if rv is None:
                    raise view_errors.get(e.id.lower()) or RuntimeError("view not in the render")
                c = _cmp.compare_view(_expected_xml(e.source.payload, e, plan), rv)
            elif e.type == "dashboard":
                buf = io.StringIO()
                with contextlib.redirect_stderr(buf):
                    env = json.loads(render_dashboards_bundle_json(
                        [obj], views_by_name, "00000000-0000-0000-0000-000000000000",
                        known_dashboards=L.dashboards))
                c = _cmp.compare_dashboard(_expected_dashboard(e, plan), e.source.context.get("entries") or {},
                                           env, env["dashboards"][0], widget_ids, rewrites)
            elif e.type == "report":
                root = ET.fromstring(render_report_xml([obj]))
                c = _cmp.compare_xml(_expected_xml(e.source.payload, e, plan), root.find("Reports/ReportDef"))
            elif e.type in ("alert", "symptom", "recommendation"):
                if e.type == "alert":
                    root = ET.fromstring(render_alert_content_xml(L.symptoms, [obj], L.recommendations))
                    got = root.find("AlertDefinitions/AlertDefinition")
                elif e.type == "symptom":
                    root = ET.fromstring(render_alert_content_xml([obj], [], []))
                    got = root.find("SymptomDefinitions/SymptomDefinition")
                else:
                    root = ET.fromstring(render_alert_content_xml([], [], [obj]))
                    got = root.find("Recommendations/Recommendation")
                c = _cmp.compare_xml(_expected_xml(e.source.payload, e, plan), got)
            else:
                exp = dict(e.source.payload)
                exp["name"] = e.name
                if e.described is not None:
                    exp["description"] = e.described[1]
                exp["formula"] = re.sub(r"sm_(" + _UUID.pattern + ")",
                                        lambda m: "sm_" + rewrites.get(m.group(1).lower(), m.group(1)),
                                        str(exp.get("formula", "")))
                if obj.id not in sm_render:
                    raise sm_errors.get(obj.id) or RuntimeError("super metric not in the render")
                got = dict(sm_render[obj.id])
                if "id" in exp:
                    exp["id"] = e.id
                    got["id"] = obj.id
                c = _cmp.compare_supermetric(exp, got)
        except Exception as exc:
            res["load_errors"].append(f"{e.relpath}: render or compare failed: {type(exc).__name__}: {exc}")
            continue
        res["objects"] += 1
        res["fields"] += c.fields
        res["set_aside"].update(c.set_aside)
        dev_marks = [_translate(m, rewrites) for d in e.deviations for m in d.marks]
        loss_marks = [(x, _translate(m, rewrites)) for x in e.losses for m in x.marks]
        differences, at_losses, at_devs = [], [], []
        losses_hit = set()
        for d in c.differences:
            if any(m.matches(d) for m in dev_marks):
                res["deviations"][_classify(e.type, d.path, d.kind)] += 1
                at_devs.append(d)
                continue
            hit = next((x for x, m in loss_marks if m.matches(d)), None)
            if hit is not None:
                at_losses.append(d)
                losses_hit.add(hit.cls)
                res["loss_classes"][hit.cls] += 1
                res["loss_class_objects"][hit.cls].add(e.relpath)
                continue
            differences.append(d)
            cls = _classify(e.type, d.path, d.kind)
            res["classes"][cls] += 1
            res["class_objects"][cls].add(e.relpath)
        detail["fields"] = c.fields
        detail["differences"] = [list(d[:3]) for d in differences]
        detail["at_recorded_losses"] = [list(d[:3]) for d in at_losses]
        detail["recorded_losses"] = [x.text for x in e.losses]
        detail["target_deviations"] = [d.text for d in e.deviations]
        detail["at_target_deviations"] = [list(d[:3]) for d in at_devs]
        pt = res["per_type"][e.type]
        pt["compared"] += 1
        if differences:
            status = "differs"
            res["differ"] += 1
        elif at_losses:
            status = "differs only at recorded losses"
            res["only_losses"] += 1
        elif at_devs:
            status = "identical apart from forced target keys"
            res["deviation_only"] += 1
        elif e.kind_refs or e.described is not None:
            # the only differences from the source are the intended ones:
            # re-pointed kinds (--map-kind), a replaced description
            # (--describe); never "identical"
            status = "identical apart from " + " and ".join(
                x for x, on in (("re-pointed kinds", e.kind_refs), ("a replaced description", e.described))
                if on)
            res["intended_only"] += 1
        else:
            status = "identical"
            res["identical"] += 1
        if e.kind_refs:
            res["kind_objects"] += 1
            res["kind_refs"] += e.kind_refs
            detail["kind_references_repointed"] = e.kind_refs
        if e.described is not None:
            res["described"] += 1
            detail["description_replaced"] = True
        pt[status] += 1
        detail["status"] = status
        res["objects_detail"].append(detail)
    return res


# ------------------------------------------------------------------- main
def _check_out(out: Path, args) -> Optional[str]:
    """``None`` when --out may be written, else the refusal."""
    if not out.exists():
        return None
    if not out.is_dir():
        return f"--out {out} exists and is not a directory"
    if not any(out.iterdir()):
        return None
    if not args.force:
        return (f"--out {out} is not empty; pass --force to replace a directory this importer wrote before "
                f"(it carries {MARKER})")
    if not (out / MARKER).is_file():
        return (f"--out {out} is not empty and was not written by import-local (no {MARKER}); --force replaces "
                f"only such a directory. Choose an empty or new --out")
    return None


def _check_report_dir(report_dir: Path) -> Optional[str]:
    if not report_dir.exists():
        return None
    if not report_dir.is_dir():
        return f"--report-dir {report_dir} exists and is not a directory"
    ours = [f for f in REPORT_FILES if (report_dir / f).exists()]
    if ours and not (report_dir / REPORT_MARKER).is_file():
        return (f"--report-dir {report_dir} holds {', '.join(ours)}, which import-local did not write (no "
                f"{REPORT_MARKER}); it does not overwrite them. Choose another --report-dir")
    return None


def run(args) -> int:
    inputs = [Path(p) for p in args.inputs]
    out = Path(args.out)
    report_dir = Path(args.report_dir) if args.report_dir else out / "import-report"
    report_inside = report_dir.resolve().relative_to(out.resolve()) if _inside(report_dir, out) else None
    for p in inputs:
        if not p.exists():
            _err(f"ERROR: input not found: {p}")
            return EXIT_USAGE
        if _inside(out, p) or _inside(p, out):
            _err(f"ERROR: --out {out} overlaps the input {p}; inputs are read only, write elsewhere")
            return EXIT_USAGE
        if _inside(report_dir, p):
            _err(f"ERROR: --report-dir {report_dir} is inside the input {p}; inputs are read only")
            return EXIT_USAGE
    if not args.dry_run:
        problem = _check_out(out, args) or (_check_report_dir(report_dir) if report_inside is None else None)
        if problem:
            _err(f"ERROR: {problem}")
            return EXIT_USAGE
    mint_ns = None
    if getattr(args, "ids", None) == "mint":
        mint_ns = args.mint_namespace or (f"project:{args.project_name}" if args.project_name else None)
        if not mint_ns:
            _err("ERROR: --ids mint needs --mint-namespace TEXT (or --project-name, whose 'project:<name>' is the "
                 "default): the minted ids derive from it, so a rerun gives the same ids")
            return EXIT_USAGE
    elif args.mint_namespace:
        _err("ERROR: --mint-namespace is only used with --ids mint")
        return EXIT_USAGE
    try:
        id_map: Dict[str, str] = {}
        for f in args.id_map or []:
            for k, v in parse_tsv_map(Path(f).read_text(encoding="utf-8"), f).items():
                if norm_id("", k) in {norm_id("", x) for x in id_map}:
                    raise ValueError(f"{f}: {k} is already mapped by an earlier --id-map file")
                id_map[k] = v
        drop: Dict[str, str] = {}
        for f in args.drop or []:
            drop.update(parse_id_list(Path(f).read_text(encoding="utf-8"), f))
        rename = parse_rename_map(Path(args.rename).read_text(encoding="utf-8"), args.rename) if args.rename else {}
        kind_rows = []
        for f in getattr(args, "map_kind", None) or []:
            kind_rows += parse_kind_map(Path(f).read_text(encoding="utf-8"), f)
        kind_map = KindMap(kind_rows) if getattr(args, "map_kind", None) else None
        if kind_map is not None and not kind_map.rows:
            raise ValueError(f"--map-kind: {', '.join(args.map_kind)} hold no rows")
        describe: Dict[Tuple[str, str], str] = {}
        for f in getattr(args, "describe", None) or []:
            for k, v in parse_describe_map(Path(f).read_text(encoding="utf-8"), f).items():
                if k in describe:
                    raise ValueError(f"{f}: {k[0]} {k[1]!r} is already described by an earlier --describe file")
                describe[k] = v
    except (OSError, ValueError) as exc:
        _err(f"ERROR: {exc}")
        return EXIT_USAGE
    opts = ConvertOptions(ids="map" if args.id_map else args.ids, id_map=id_map, drop=drop,
                          naming=args.naming, rename=rename, target_min=args.target_min,
                          prefer_sources=list(args.prefer_source or []), layout=args.layout,
                          mint_namespace=mint_ns, kind_map=kind_map, describe=describe)

    scan = scan_inputs(inputs)
    missed, guard_unreadable = _completeness(scan, inputs)
    unreadable = list(scan.unreadable)
    known = {u.location for u in unreadable}
    unreadable += [u for u in guard_unreadable if u.location not in known]
    try:
        plan = plan_conversion(scan, opts)
    except ValueError as exc:
        _err(f"ERROR: {exc}")
        return EXIT_USAGE
    if plan.usage_error:
        _err(f"ERROR: {plan.usage_error}")
        return EXIT_USAGE
    # Every file that is written must load: staged in a temporary directory
    # first; an object a loader refuses (and anything referencing it) becomes
    # a reported failure instead of a file nothing can read.
    _load_check(plan, args.layout, args)
    roots = inputs

    # -- report: what was found -------------------------------------------
    _say(f"import-local: {len(inputs)} input(s), {scan.files_read} file(s) read, "
         f"{len(scan.objects)} definition(s) found ({len(plan.merged_duplicates)} id(s) repeated in several files)")
    if plan.mint_namespace:
        _say(f"ids minted from namespace {plan.mint_namespace!r} (uuid {mint_namespace_uuid(plan.mint_namespace)}): "
             f"a rerun with the same namespace gives the same ids")
    if scan.passed_over:
        _say(f"passed over (not content objects): {len(scan.passed_over)}")
        for po in scan.passed_over:
            _say(f"  - {_rel_location(po.location, roots)}: {po.reason}")
    for u in unreadable:
        _say(f"CANNOT READ {_rel_location(u.location, roots)}: {u.reason}")
    for m in missed:
        _say(f"MISSED {m}")
    for t, i, locs in plan.merged_duplicates:
        _say(f"merged: {t} {i} is the same in {len(locs)} files: "
             + "; ".join(_rel_location(x, roots) for x in locs))
    for t, i, winner, locs in plan.resolved_duplicates:
        _say(f"duplicate resolved by --prefer-source: {t} {i}: kept {_rel_location(winner, roots)} "
             f"(copies in {'; '.join(_rel_location(x, roots) for x in locs)})")
    for t, i, n, locs in plan.dropped:
        _say(f"dropped (--drop): {t} {i} {n!r}")
    for f in plan.unsupported:
        _say(f"NOT CONVERTED (unsupported type) {f.type} {f.id} {f.name!r} in {_rel_location(f.locations[0], roots)}")
    for f in plan.failures:
        if f.kind == "unsupported":
            continue
        label = "INTERNAL ERROR" if f.kind == "internal" else "FAILED"
        _say(f"{label} {f.type} {f.id} {f.name!r}: {_rel_reason(f.reason, roots)}")
        if f.gap:
            _say("  TOOLSET GAP")
            for k, v in f.gap.items():
                _say(f"  - {k}: {v}")
    for e in plan.emitted:
        if e.rename_reasons:
            _say(f"RENAMED {e.type} {e.source_name!r} -> {e.name!r} ({'; '.join(e.rename_reasons)})")
    for e in plan.emitted:
        if e.kind_refs:
            _say(f"KIND {e.type} {e.name!r}: {e.kind_refs} kind reference(s) re-pointed ({'; '.join(e.kind_changes)})")
    for e in plan.emitted:
        if e.described:
            _say(f"DESCRIBED {e.type} {e.name!r}: description replaced ({len(e.described[0])} characters in the "
                 f"source, {len(e.described[1])} written)")
    for e in plan.emitted:
        for loss in e.losses:
            _say(f"LOSS {e.type} {e.name!r}: {loss.text} [at {', '.join(m.path for m in loss.marks)}]")
    for e in plan.emitted:
        for d in e.deviations:
            _say(f"TARGET {args.target_min}: {e.relpath}: {d.text}")
        for w in e.version_warnings:
            _say(f"VERSION: {e.relpath}: {w}")
        for u in e.undeliverable:
            _say(f"NOT DELIVERABLE to {args.target_min}: {e.relpath} ({e.name!r}): converted, but {u}")
    note_files: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for e in plan.emitted:
        for n in e.notes:
            if e.relpath not in note_files[(e.type, n)]:
                note_files[(e.type, n)].append(e.relpath)
    for (t, n), files in sorted(note_files.items()):
        _say(f"note ({', '.join(files)}): {n}")
    for w in plan.warnings:
        _say(f"WARNING: {w}")
    if plan.kind_map is not None:
        km = plan.kind_map
        moved = [e for e in plan.emitted if e.kind_refs]
        _say(f"kind map: {len(km.rows)} row(s), {len(km.rows) - len(km.unused())} used; {len(moved)} converted "
             f"object(s) carry re-pointed kinds, {sum(e.kind_refs for e in moved)} kind reference(s) re-pointed")
    vt = [e for e in plan.emitted if e.verbatim]
    _say(f"verbatim source text: {len(vt)} object(s) ship the source's prose in {sum(len(e.verbatim) for e in vt)} "
         f"free-text field(s) not replaced by --rename or --describe ({sum(n for e in vt for _, n in e.verbatim)} "
         f"characters as the source wrote them: names, descriptions, widget titles and text); listed per object "
         f"in report.json (verbatim_text)")
    if args.naming == "factory-prefixed":
        from vcfcf_core.dashboards.loader import DASHBOARD_NAME_MAX_LEN
        for e in plan.emitted:
            if e.type == "dashboard":
                _say(f"name length: {e.relpath}: {len(e.name)} of {DASHBOARD_NAME_MAX_LEN} characters")

    # -- stock-id guard on the result ---------------------------------------
    errors, coverage = _stock_guard(plan)
    if errors:
        _err(f"stock-id guard: the result defines {len(errors)} object(s) under VCF Operations stock ids "
             f"(issue #345); nothing written. Mint new ids (--ids mint) or map them (--id-map), or drop "
             f"them (--drop) and reference the product object in place:")
        for line in errors:
            _err(f"  {line}")
        _summary(plan, unreadable, missed)
        return EXIT_STOCK
    _say(f"stock-id guard: clear. {coverage}")

    if args.dry_run:
        _summary(plan, unreadable, missed)
        _say("dry run: nothing written, nothing verified")
        return _exit(plan, unreadable, missed, None, args)

    # -- write into a staging sibling, verify there, move into place ------
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.import-local-", dir=out.parent))
    except OSError as exc:
        _err(f"ERROR: cannot create a staging directory beside {out}: {exc}; nothing written")
        return EXIT_USAGE
    try:
        try:
            for n in _write_tree(plan, stage, args, out, report_inside):
                _say(n)
        except OSError as exc:
            _err(f"ERROR: writing the tree failed ({type(exc).__name__}: {exc}); nothing written to {out}")
            return EXIT_USAGE
        v = None
        if args.verify:
            v = _verify(plan, stage, args.layout)
            for k in ("load_errors", "pak_problems", "guard"):
                v[k] = [x.replace(str(stage), str(out)) for x in v[k]]
            _print_verify(v, args)
        else:
            _say("")
            _say("WARNING: --no-verify: nothing was checked. The written YAML was not loaded by the layout's "
                 "loader, rendered or compared with the source")
        _summary(plan, unreadable, missed)
        rc = _exit(plan, unreadable, missed, v, args)
        rep = _report(plan, args, scan, unreadable, missed, v, roots, rc)
        rep_files = {"report.json": json.dumps(rep, indent=2, default=str), "id_map.tsv": _id_map_text(plan)}
        if args.layout == "pak":
            rep_files["bundled_content.yaml"] = _bundled_content_text(plan, args)
        if rc == EXIT_OK:
            if report_inside is not None:
                (stage / report_inside / "report.json").write_text(rep_files["report.json"], encoding="utf-8")
            _place(stage, out)
            stage = None
            if report_inside is None:
                _write_external_report(report_dir, rep_files)
            _say(f"wrote {len(plan.emitted)} YAML file(s) under {out} ({args.layout} layout); report, id map"
                 f"{' and bundled_content snippet' if args.layout == 'pak' else ''} in {report_dir}")
        else:
            _say(f"nothing written to {out}: the run did not succeed (exit {rc}); the tree was staged, "
                 f"verified and removed. Fix what is reported, or pass --allow-partial to accept what it accepts")
            if report_inside is None:
                _write_external_report(report_dir, rep_files)
                _say(f"report and id map written to {report_dir}")
        return rc
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def _place(stage: Path, out: Path) -> None:
    """Move the staged tree to ``out``, replacing an earlier run's tree whole."""
    old = None
    if out.exists():
        old = Path(tempfile.mkdtemp(prefix=f".{out.name}.import-local-old-", dir=out.parent))
        old.rmdir()
        os.replace(out, old)
    os.replace(stage, out)
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)


def _rel_reason(reason: str, roots: List[Path]) -> str:
    for r in roots:
        reason = reason.replace(str(r.resolve()) + "/", "").replace(str(r) + "/", "")
    return reason


def _summary(plan: Plan, unreadable, missed) -> None:
    c = plan.counts()
    _say("")
    _say("summary            found  converted  with losses  not deliverable  failed  internal errors  dropped")
    for t in CONTENT_TYPES:
        r = c[t]
        _say(f"  {t:16s} {r['found']:5d}  {r['converted']:9d}  {r['with_losses']:11d}  {r['undeliverable']:15d}  "
             f"{r['failed']:6d}  {r['internal_errors']:15d}  {r['dropped']:7d}")
    uns = Counter(f.type for f in plan.unsupported)
    for t, n in sorted(uns.items()):
        _say(f"  {t:16s} {n:5d}  not converted (unsupported type)")
    if unreadable or missed:
        _say(f"  inputs that could not be read: {len(unreadable)}; definitions missed: {len(missed)}")


def _print_verify(v, args) -> None:
    _say("")
    intended = bool(getattr(args, "map_kind", None) or getattr(args, "describe", None))
    _say(f"verify ({args.layout} layout, real loaders): compared {v['objects']} object(s), {v['fields']} field(s): "
         f"{v['identical']} identical; {v['deviation_only']} identical apart from keys forced by --target-min; "
         + (f"{v['intended_only']} identical apart from intended changes (re-pointed kinds, replaced "
            f"descriptions); " if intended else "")
         + f"{v['only_losses']} differ only at recorded losses; {v['differ']} differ")
    if intended:
        _say(f"  intended changes: {v['kind_refs']} kind reference(s) re-pointed in {v['kind_objects']} object(s); "
             f"{v['described']} description(s) replaced (each object's status says which it carries)")
    for t, cnt in sorted(v["per_type"].items()):
        n_int = sum(n for k, n in cnt.items() if k.startswith("identical apart from ") and "forced" not in k)
        _say(f"  {t:16s} {cnt['identical']} of {cnt['compared']} identical"
             + (f"; {cnt['identical apart from forced target keys']} apart from forced target keys"
                if cnt["identical apart from forced target keys"] else "")
             + (f"; {n_int} apart from intended changes" if n_int else "")
             + (f"; {cnt['differs only at recorded losses']} only at recorded losses"
                if cnt["differs only at recorded losses"] else "")
             + (f"; {cnt['differs']} differ" if cnt["differs"] else ""))
    for le in v["load_errors"]:
        _say(f"  LOAD ERROR: {le}")
    for pp in v["pak_problems"]:
        _say(f"  PAK CHECK: {pp}")
    for g in v["guard"]:
        _say(f"  STOCK-ID (loaded tree): {g}")
    if v["loss_classes"]:
        _say("  differences at recorded losses (class: objects / differences):")
        for cls, n in sorted(v["loss_classes"].items(), key=lambda kv: (-len(v["loss_class_objects"][kv[0]]), kv[0])):
            _say(f"    {len(v['loss_class_objects'][cls]):4d} / {n:5d}  {cls}")
    if v["classes"]:
        _say("  differences (class: objects / occurrences):")
        for cls, n in sorted(v["classes"].items(), key=lambda kv: (-len(v["class_objects"][kv[0]]), kv[0])):
            _say(f"    {len(v['class_objects'][cls]):4d} / {n:4d}  {cls}")
    if v["deviations"]:
        _say("  differences forced by --target-min (each at its recorded path):")
        for cls, n in sorted(v["deviations"].items()):
            _say(f"    {n:4d}  {cls}")
    _say("  set aside, by class (count):")
    for cls, n in sorted(v["set_aside"].items()):
        _say(f"    {n:6d}  {cls}")
    for d in v["objects_detail"]:
        if d["status"] == "differs":
            _say(f"  DIFFERS {d['file']} ({d['name']!r}):")
            for path, kind, detail in d["differences"][:12]:
                _say(f"      {path}: {kind} {detail}")
            if len(d["differences"]) > 12:
                _say(f"      ... {len(d['differences']) - 12} more")
        elif d["status"] == "differs only at recorded losses":
            _say(f"  ONLY RECORDED LOSSES {d['file']} ({d['name']!r}): differs only at "
                 f"{len(d['at_recorded_losses'])} recorded loss difference(s): {'; '.join(d['recorded_losses'])}")


def _report(plan: Plan, args, scan, unreadable, missed, v, roots, rc) -> dict:
    rep = {
        "command": "import-local",
        "exit": rc,
        "layout": args.layout, "ids": "map" if args.id_map else args.ids, "naming": args.naming,
        "mint_namespace": plan.mint_namespace,
        "target_min": args.target_min,
        "verified": v is not None,
        "counts": plan.counts(),
        "passed_over": [{"location": _rel_location(p.location, roots), "reason": p.reason} for p in scan.passed_over],
        "unreadable": [{"location": _rel_location(u.location, roots), "reason": u.reason} for u in unreadable],
        "missed": missed,
        "merged_duplicates": [{"type": t, "id": i, "files": [_rel_location(x, roots) for x in locs]}
                              for t, i, locs in plan.merged_duplicates],
        "failures": [{"type": f.type, "id": f.id, "name": f.name, "kind": f.kind,
                      "reason": _rel_reason(f.reason, roots), "gap": f.gap} for f in plan.failures],
        "dropped": [{"type": t, "id": i, "name": n} for t, i, n, _ in plan.dropped],
        "objects": [{"type": e.type, "file": e.relpath, "source_id": e.source_id, "id": e.id, "name": e.name,
                     "source_name": e.source_name, "renamed": e.rename_reasons,
                     "losses": [{"class": x.cls, "text": x.text, "at": [m.path for m in x.marks]} for x in e.losses],
                     "notes": e.notes, "deviations": [{"text": d.text, "at": [m.path for m in d.marks]}
                                                      for d in e.deviations],
                     "version_warnings": e.version_warnings, "not_deliverable": e.undeliverable,
                     "verbatim_text": [{"field": f, "length": n} for f, n in e.verbatim],
                     **({"kind_references_repointed": e.kind_refs, "kind_changes": e.kind_changes}
                        if plan.kind_map is not None else {}),
                     **({"description_replaced": e.described is not None,
                         "source_description_length": len(e.described[0]) if e.described else None}
                        if plan.describing else {})}
                    for e in plan.emitted],
        "warnings": plan.warnings,
    }
    if plan.kind_map is not None:
        km = plan.kind_map
        rep_rows = []
        for r in km.rows:
            rep_rows.append({"row": r.where, "map": r.label(), "used": km.used[(r.old_ak, r.old_rk)]})
        rep["kind_map"] = {"rows": rep_rows, "objects_repointed": sum(1 for e in plan.emitted if e.kind_refs),
                           "kind_references_repointed": sum(e.kind_refs for e in plan.emitted)}
    if v is not None:
        rep["verify"] = {
            "objects": v["objects"], "fields": v["fields"], "identical": v["identical"],
            "identical_apart_from_forced_target_keys": v["deviation_only"],
            "differ_only_at_recorded_losses": v["only_losses"], "differ": v["differ"],
            "per_type": {t: dict(c) for t, c in v["per_type"].items()},
            "recorded_loss_classes": {k: {"objects": len(v["loss_class_objects"][k]), "differences": n}
                                      for k, n in v["loss_classes"].items()},
            "difference_classes": {k: {"objects": len(v["class_objects"][k]), "occurrences": n}
                                   for k, n in v["classes"].items()},
            "target_deviations": dict(v["deviations"]), "set_aside": dict(v["set_aside"]),
            "load_errors": v["load_errors"], "pak_problems": v["pak_problems"], "stock_ids": v["guard"],
            "objects_detail": v["objects_detail"],
        }
        if plan.kind_map is not None or plan.describing:
            rep["verify"]["identical_apart_from_intended_changes"] = v["intended_only"]
            rep["verify"]["intended_changes"] = {"objects_with_repointed_kinds": v["kind_objects"],
                                                 "kind_references_repointed": v["kind_refs"],
                                                 "descriptions_replaced": v["described"]}
    return rep


def _exit(plan: Plan, unreadable, missed, v, args) -> int:
    if plan.internal_errors:
        _err(f"internal error in the converter on {len(plan.internal_errors)} object(s) (listed as INTERNAL ERROR); "
             f"--allow-partial does not accept it")
        return EXIT_INTERNAL
    if unreadable or missed:
        return EXIT_PARTIAL
    if v is not None and (v["objects"] == 0 or v["fields"] == 0):
        _err("verify: compared nothing")
        return EXIT_NOTHING
    never = False
    if v is not None and (v["load_errors"] or v["guard"]):
        never = True
    if args.layout == "pak":
        # A pak build refuses these; accepting them would write a pak tree
        # that does not build or does not deliver to the stated target.
        if v is not None and v["pak_problems"]:
            never = True
        if any(e.undeliverable for e in plan.emitted):
            never = True
    if never:
        return EXIT_PARTIAL
    partial = (bool(plan.failures) or any(e.losses for e in plan.emitted)
               or any(e.undeliverable for e in plan.emitted)
               or (v is not None and (v["differ"] or v["only_losses"])))
    if partial and not args.allow_partial:
        return EXIT_PARTIAL
    return EXIT_OK
