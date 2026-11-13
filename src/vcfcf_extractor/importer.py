"""``python3 -m vcfcf_extractor import-local``: offline conversion of existing
VCF Operations content files to factory YAML, written into a target layout,
checked by the stock-id guard and optionally verified through the real
loaders and renderers.

The parse, map and compare logic is ``vcfcf_core.importer``; this module
owns what the core may not do: write files, read the stock-id baseline
through the factory, load the written YAML with the factory, third-party
and pak loaders, and print the report. No network access anywhere.
How-to: ``knowledge/context/authoring/importer_offline_conversion.md``.

Exit status: 0 success; 1 an object failed, lost data or differed on
verification (``--allow-partial`` accepts that), or an input could not be
read (never accepted: what cannot be read was not checked); 2 a usage or
safety refusal (nothing written); 3 the stock-id guard refused the result
(nothing written); 4 ``--verify`` compared nothing.
"""
from __future__ import annotations

import copy
import io
import json
import re
import sys
import tempfile
import types
import warnings
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from vcfcf_core.importer import compare as _cmp
from vcfcf_core.importer.convert import (
    ConvertOptions,
    Plan,
    TYPE_DIRS,
    dump_yaml,
    norm_id,
    parse_id_list,
    parse_tsv_map,
    plan_conversion,
)
from vcfcf_core.importer.inputs import CONTENT_TYPES, scan_inputs
from vcfcf_core.importer.model import loss_path_patterns

EXIT_OK, EXIT_PARTIAL, EXIT_USAGE, EXIT_STOCK, EXIT_NOTHING = 0, 1, 2, 3, 4
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RENDERED_PREFIX = {"symptom": "SymptomDefinition-", "alert": "AlertDefinition-"}


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
            "The stock-id guard runs on the result; --verify re-loads the written YAML through the\n"
            "real loaders of the layout, renders it and compares it with the source.\n"
            "\n"
            "How-to: knowledge/context/authoring/importer_offline_conversion.md\n"
            "\n"
            "Example:\n"
            "  python3 -m vcfcf_extractor import-local 'Management Pack/content' \\\n"
            "    --out third_party/my-port --layout third-party --project-name my-port \\\n"
            "    --ids mint --naming unprefixed --verify\n"
        ),
        formatter_class=__import__("argparse").RawDescriptionHelpFormatter,
    )
    p.add_argument("inputs", nargs="+", metavar="INPUT", help="file, directory, zip or .pak (read only)")
    p.add_argument("--out", required=True, metavar="DIR", help="target directory (must be empty unless --force)")
    p.add_argument("--layout", required=True, choices=("content", "third-party", "pak"),
                   help="content: a factory content/ tree; third-party: a third_party/<project> with "
                        "PROJECT.yaml; pak: an SDK pak's bundled-content folders")
    ids = p.add_mutually_exclusive_group(required=True)
    ids.add_argument("--ids", choices=("keep", "mint"),
                     help="keep: carry the source ids; mint: a new UUID for every object, every "
                          "reference rewritten, the mapping written to the report directory")
    ids.add_argument("--id-map", metavar="TSV", action="append",
                     help="old id<TAB>new id rows for some objects; the rest keep theirs (repeatable; "
                          "an old id listed in two files is an error)")
    p.add_argument("--naming", required=True, choices=("unprefixed", "factory-prefixed"),
                   help="unprefixed: names as in the source; factory-prefixed: '[VCF CF] ' on every name, "
                        "references follow")
    p.add_argument("--rename", metavar="TSV", help="old name (or id)<TAB>new name rows, applied before --naming")
    p.add_argument("--drop", metavar="TSV", action="append",
                   help="ids (first column) not to emit; references to them stay raw ids (repeatable)")
    p.add_argument("--target-min", choices=("8.18.7", "9.0.2", "9.1.1"),
                   help="oldest VCF Operations the output must import on: omit: entries proven only on "
                        "newer builds are not emitted (each deviation listed)")
    p.add_argument("--prefer-source", action="append", default=[], metavar="FRAGMENT",
                   help="when one id is defined differently in several files, the copy from the file "
                        "whose path contains FRAGMENT wins (repeatable, first match wins)")
    p.add_argument("--project-name", metavar="NAME", help="third-party layout: PROJECT.yaml name (default: --out dir name)")
    p.add_argument("--report-dir", metavar="DIR", help="where the report, id map and pak snippet go "
                                                       "(default: <out>/import-report)")
    p.add_argument("--verify", action="store_true", help="re-load, render and compare every written object")
    p.add_argument("--allow-partial", action="store_true",
                   help="exit 0 even when objects failed, lost data or differ on verification")
    p.add_argument("--force", action="store_true", help="write into a non-empty --out (overwrites are listed)")
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
    missed = []
    for p in inputs:
        for d in scan_path(p, unreadable=unreadable):
            if d.attrs.get("in_policy"):
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
def _write(plan: Plan, out: Path, report_dir: Path, args, inputs: List[Path]) -> List[str]:
    """Write every emitted object; return the notes about pre-existing files."""
    notes = []
    out.mkdir(parents=True, exist_ok=True)
    for e in plan.emitted:
        p = out / e.relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            notes.append(f"OVERWROTE {p} (it existed before this run)")
        p.write_text(e.text, encoding="utf-8")
    if args.layout == "third-party":
        proj = out / "PROJECT.yaml"
        if proj.exists():
            notes.append(f"KEPT {proj} (it existed before this run; not rewritten)")
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
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = ["type\told_id\tnew_id\tname\tfile"]
    for (t, old, new, name), e in zip(plan.id_table, plan.emitted):
        lines.append(f"{t}\t{old}\t{_rendered_id(t, new) if t in _RENDERED_PREFIX else new}\t{name}\t{e.relpath}")
    (report_dir / "id_map.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.layout == "pak":
        bc: Dict[str, List[str]] = defaultdict(list)
        for e in plan.emitted:
            bc[TYPE_DIRS[e.type]].append(e.relpath)
        (report_dir / "bundled_content.yaml").write_text(
            "# Paste under bundled_content: in the pak's adapter.yaml (paths are relative to it).\n"
            + dump_yaml({"bundled_content": dict(bc)}), encoding="utf-8")
    return notes


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
    import shutil
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
        while True:
            _, errors = _per_file_load(plan, tmp, layout, only)
            only = {"dashboard", "report", "alert"}
            # A per-file load does not see every by-name reference (an
            # alert's symptoms and recommendations, a navigation target), so
            # an object naming one that was refused is refused too.
            for e in plan.emitted:
                if e.relpath in errors:
                    continue
                for t, n in _named_refs(e):
                    if (t, n) in removed:
                        errors[e.relpath] = f"names {t} {n!r}, which was refused (see its own failure)"
            if not errors:
                break
            keep = []
            for e in plan.emitted:
                if e.relpath in errors:
                    removed.add((e.type, e.name))
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


def _named_refs(e) -> List[Tuple[str, str]]:
    """The (type, name) references in an emitted YAML that a per-file load
    does not resolve: alert symptoms and recommendations, navigation
    targets."""
    y = e.yaml_tree
    out: List[Tuple[str, str]] = []
    if e.type == "alert":
        for st in (y.get("symptom_sets") or {}).get("sets") or []:
            out += [("symptom", s.get("name")) for s in st.get("symptoms") or []]
        out += [("recommendation", r.get("name")) for r in y.get("recommendations") or []]
    elif e.type == "dashboard":
        for w in y.get("widgets") or []:
            out += [("dashboard", n.get("dashboard")) for n in w.get("navigations") or [] if n.get("dashboard")]
    return out


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

    for x in el.iter():
        for k, v in list(x.attrib.items()):
            if x.tag == "Recommendation" and k in ("key", "ref") and v in rec_rw:
                x.set(k, rec_rw[v])
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
    return el


def _expected_dashboard(e, plan: Plan) -> dict:
    db = copy.deepcopy(e.source.payload)
    name, npath = db.get("name", ""), db.get("namePath")
    if npath and name.startswith(npath + "/"):
        db["name"] = f"{npath}/{e.name}"
    else:
        db["name"] = e.name
    return db


def _classify(t: str, path: str, kind: str) -> str:
    g = re.sub(r"\[\d+:", "[", path)
    g = re.sub(r"\[\]", "[]", g)
    k = kind.split(" ")[0]
    return f"{t}: {g} [{k}]"


def _verify(plan: Plan, out: Path, layout: str):
    from vcfcf_core.alerts.render import render_alert_content_xml
    from vcfcf_core.dashboards.render import render_dashboards_bundle_json, render_views_xml
    from vcfcf_core.packaging.assembly import _render_supermetrics_dict
    from vcfcf_core.reports.render import render_report_xml

    res = {"objects": 0, "fields": 0, "identical": 0, "only_documented": 0, "per_type": defaultdict(Counter),
           "classes": Counter(), "class_objects": defaultdict(set), "set_aside": Counter(),
           "deviations": Counter(), "objects_detail": [], "load_errors": [], "pak_problems": [],
           "guard": []}
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
    if layout == "pak":
        from vcfcf_supermetrics.loader import sm_id_map
        sm_map = sm_id_map(L.sm_paths)
        view_xml = render_views_xml(L.views, sm_map=sm_map, sm_scope_active=True) if L.views else None
    else:
        sm_map = {s.name: s.id for s in L.supermetrics}
        view_xml = render_views_xml(L.views, sm_map=sm_map) if L.views else None
    rendered_views = {}
    if view_xml:
        for vd in ET.fromstring(view_xml).iter("ViewDef"):
            rendered_views[vd.get("id").lower()] = vd
    sm_render = _render_supermetrics_dict(types.SimpleNamespace(supermetrics=L.supermetrics)) if L.supermetrics else {}
    widget_ids: Dict[str, str] = {}
    for e in plan.emitted:
        if e.type != "dashboard":
            continue
        d = by_path.get(str((out / e.relpath).resolve()))
        if d is None:
            continue
        for sw, yw in zip(e.source.payload.get("widgets") or [], d.widgets):
            widget_ids[sw.get("id")] = yw.widget_id

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
                    raise RuntimeError("view not in the render")
                c = _cmp.compare_view(_expected_xml(e.source.payload, e, plan), rv)
            elif e.type == "dashboard":
                buf = io.StringIO()
                import contextlib
                with contextlib.redirect_stderr(buf):
                    env = json.loads(render_dashboards_bundle_json(
                        [obj], views_by_name, "00000000-0000-0000-0000-000000000000",
                        known_dashboards=L.dashboards))
                rewrites = dict(plan.id_rewrites)
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
                exp["formula"] = re.sub(r"sm_(" + _UUID.pattern + ")",
                                        lambda m: "sm_" + plan.id_rewrites.get(m.group(1).lower(), m.group(1)),
                                        str(exp.get("formula", "")))
                c = _cmp.compare_supermetric(exp, sm_render[obj.id])
        except Exception as exc:
            res["load_errors"].append(f"{e.relpath}: render or compare failed: {type(exc).__name__}: {exc}")
            continue
        res["objects"] += 1
        res["fields"] += c.fields
        res["set_aside"].update(c.set_aside)
        dev_keys = {k for d in e.deviations for k in d.wire_keys}
        documented = loss_path_patterns(e.losses)
        differences, by_loss = [], 0
        for path, kind in c.differences:
            if any(re.search(r"[.@/]" + re.escape(k) + r"(\b|$)", path) for k in dev_keys):
                res["deviations"][_classify(e.type, path, kind)] += 1
                continue
            cls = _classify(e.type, path, kind)
            explained = any(re.search(rx, path) for rx in documented)
            if explained:
                by_loss += 1
                cls += "  (a documented loss of this object)"
            differences.append((path, kind))
            res["classes"][cls] += 1
            res["class_objects"][cls].add(e.relpath)
        detail["fields"] = c.fields
        detail["differences"] = differences
        detail["target_deviations"] = [d.text for d in e.deviations]
        res["per_type"][e.type]["compared"] += 1
        if not differences:
            res["identical"] += 1
            res["per_type"][e.type]["identical"] += 1
        elif by_loss == len(differences):
            res["only_documented"] += 1
            res["per_type"][e.type]["only documented losses"] += 1
        res["objects_detail"].append(detail)
    return res


# ------------------------------------------------------------------- main
def run(args) -> int:
    inputs = [Path(p) for p in args.inputs]
    out = Path(args.out)
    report_dir = Path(args.report_dir) if args.report_dir else out / "import-report"
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
    if not args.dry_run and out.exists() and any(out.iterdir()) and not args.force:
        _err(f"ERROR: --out {out} is not empty; pass --force to write into it (every overwritten file is listed)")
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
        rename = parse_tsv_map(Path(args.rename).read_text(encoding="utf-8"), args.rename) if args.rename else {}
    except (OSError, ValueError) as exc:
        _err(f"ERROR: {exc}")
        return EXIT_USAGE
    opts = ConvertOptions(ids="map" if args.id_map else args.ids, id_map=id_map, drop=drop,
                          naming=args.naming, rename=rename, target_min=args.target_min,
                          prefer_sources=list(args.prefer_source or []), layout=args.layout)

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
    for f in plan.failures:
        _say(f"FAILED {f.type} {f.id} {f.name!r}: {_rel_reason(f.reason, roots)}")
        if f.gap:
            _say("  TOOLSET GAP")
            for k, v in f.gap.items():
                _say(f"  - {k}: {v}")
    for e in plan.emitted:
        for loss in e.losses:
            _say(f"LOSS {e.type} {e.name!r}: {loss}")
    for e in plan.emitted:
        for d in e.deviations:
            _say(f"TARGET {args.target_min}: {e.relpath}: {d.text}")
        for w in e.version_warnings:
            _say(f"VERSION: {e.relpath}: {w}")
    note_files: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for e in plan.emitted:
        for n in e.notes:
            if e.relpath not in note_files[(e.type, n)]:
                note_files[(e.type, n)].append(e.relpath)
    for (t, n), files in sorted(note_files.items()):
        _say(f"note ({', '.join(files)}): {n}")
    for w in plan.warnings:
        _say(f"WARNING: {w}")
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
        _say("dry run: nothing written")
        return _exit(plan, unreadable, missed, None, args)

    notes = _write(plan, out, report_dir, args, inputs)
    for n in notes:
        _say(n)
    _say(f"wrote {len(plan.emitted)} YAML file(s) under {out} ({args.layout} layout); "
         f"report, id map{' and bundled_content snippet' if args.layout == 'pak' else ''} in {report_dir}")
    v = None
    if args.verify:
        v = _verify(plan, out, args.layout)
        _print_verify(v, args)
    _summary(plan, unreadable, missed)
    _write_report(plan, report_dir, args, scan, unreadable, missed, v, roots)
    return _exit(plan, unreadable, missed, v, args)


def _rel_reason(reason: str, roots: List[Path]) -> str:
    for r in roots:
        reason = reason.replace(str(r.resolve()) + "/", "").replace(str(r) + "/", "")
    return reason


def _summary(plan: Plan, unreadable, missed) -> None:
    c = plan.counts()
    _say("")
    _say("summary            found  converted  with losses  failed  dropped")
    for t in CONTENT_TYPES:
        r = c[t]
        _say(f"  {t:16s} {r['found']:5d}  {r['converted']:9d}  {r['with_losses']:11d}  {r['failed']:6d}  {r['dropped']:7d}")
    if unreadable or missed:
        _say(f"  inputs that could not be read: {len(unreadable)}; definitions missed: {len(missed)}")


def _print_verify(v, args) -> None:
    _say("")
    _say(f"verify ({args.layout} layout, real loaders): compared {v['objects']} object(s), {v['fields']} field(s); "
         f"{v['identical']} identical; {v['only_documented']} differ only where they list a documented loss")
    for t, cnt in sorted(v["per_type"].items()):
        extra = f"; {cnt['only documented losses']} more differ only by a documented loss" if cnt["only documented losses"] else ""
        _say(f"  {t:16s} {cnt['identical']} of {cnt['compared']} identical{extra}")
    for le in v["load_errors"]:
        _say(f"  LOAD ERROR: {le}")
    for pp in v["pak_problems"]:
        _say(f"  PAK CHECK: {pp}")
    for g in v["guard"]:
        _say(f"  STOCK-ID (loaded tree): {g}")
    if v["classes"]:
        _say("  differences (class: objects / occurrences):")
        for cls, n in sorted(v["classes"].items(), key=lambda kv: (-len(v["class_objects"][kv[0]]), kv[0])):
            _say(f"    {len(v['class_objects'][cls]):4d} / {n:4d}  {cls}")
    if v["deviations"]:
        _say("  differences forced by --target-min (listed deviations):")
        for cls, n in sorted(v["deviations"].items()):
            _say(f"    {n:4d}  {cls}")
    _say("  set aside as documented non-differences (count):")
    for cls, n in sorted(v["set_aside"].items()):
        _say(f"    {n:6d}  {cls}")
    _say("    (always also: whitespace collapsed; number spelling; attribute, Property and JSON key order)")
    for d in v["objects_detail"]:
        if d["differences"]:
            _say(f"  DIFFERS {d['file']} ({d['name']!r}):")
            for path, kind in d["differences"][:12]:
                _say(f"      {path}: {kind}")
            if len(d["differences"]) > 12:
                _say(f"      ... {len(d['differences']) - 12} more")


def _write_report(plan: Plan, report_dir: Path, args, scan, unreadable, missed, v, roots) -> None:
    rep = {
        "command": "import-local",
        "layout": args.layout, "ids": "map" if args.id_map else args.ids, "naming": args.naming,
        "target_min": args.target_min,
        "counts": plan.counts(),
        "passed_over": [{"location": _rel_location(p.location, roots), "reason": p.reason} for p in scan.passed_over],
        "unreadable": [{"location": _rel_location(u.location, roots), "reason": u.reason} for u in unreadable],
        "missed": missed,
        "merged_duplicates": [{"type": t, "id": i, "files": [_rel_location(x, roots) for x in locs]}
                              for t, i, locs in plan.merged_duplicates],
        "failures": [{"type": f.type, "id": f.id, "name": f.name, "reason": _rel_reason(f.reason, roots),
                      "gap": f.gap} for f in plan.failures],
        "dropped": [{"type": t, "id": i, "name": n} for t, i, n, _ in plan.dropped],
        "objects": [{"type": e.type, "file": e.relpath, "source_id": e.source_id, "id": e.id, "name": e.name,
                     "losses": e.losses, "notes": e.notes, "deviations": [d.text for d in e.deviations],
                     "version_warnings": e.version_warnings} for e in plan.emitted],
        "warnings": plan.warnings,
    }
    if v is not None:
        rep["verify"] = {
            "objects": v["objects"], "fields": v["fields"], "identical": v["identical"],
            "only_documented_losses": v["only_documented"],
            "per_type": {t: dict(c) for t, c in v["per_type"].items()},
            "difference_classes": {k: {"objects": len(v["class_objects"][k]), "occurrences": n}
                                   for k, n in v["classes"].items()},
            "target_deviations": dict(v["deviations"]), "set_aside": dict(v["set_aside"]),
            "load_errors": v["load_errors"], "pak_problems": v["pak_problems"], "stock_ids": v["guard"],
            "objects_detail": v["objects_detail"],
        }
    (report_dir / "report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")


def _exit(plan: Plan, unreadable, missed, v, args) -> int:
    if unreadable or missed:
        return EXIT_PARTIAL
    if v is not None:
        if v["objects"] == 0 or v["fields"] == 0:
            _err("verify: compared nothing")
            return EXIT_NOTHING
        if v["load_errors"] or v["guard"]:
            return EXIT_PARTIAL
    partial = bool(plan.failures) or any(e.losses for e in plan.emitted) or (
        v is not None and (v["identical"] != v["objects"] or v["pak_problems"]))
    if partial and not args.allow_partial:
        return EXIT_PARTIAL
    return EXIT_OK
