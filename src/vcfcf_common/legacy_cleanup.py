"""``python3 -m vcfcf_common cleanup-legacy-prefix``: remove what a prefix rename left behind.

After ``migrate-prefix`` renames content from ``[VCF Content Factory] <title>``
to ``[VCF CF] <title>`` and the renamed content is synced (or a pak built from
it is upgraded), an instance can hold the old-named object beside the new one
wherever the type's import identity is the name rather than an id. This
command finds those leftovers and, only with ``--apply``, deletes them.

Per type (sources: ``knowledge/context/authoring/prefix_migration.md``):

- custom groups, symptoms, alerts: the factory syncs them over REST and
  matches by name, so a rename always creates a new object and leaves the
  old one;
- dashboards: import identity is the name (vcfops-api skill, gotcha 8), so a
  rename may leave the old one; what a same-id, new-name import does to the
  old dashboard has not been observed;
- super metrics, views, reports: content-zip import is keyed by the YAML
  UUID, so a rename is expected to land in place and leave nothing; they are
  checked anyway;
- recommendations: keyed by ``Recommendation-df-<kind>-<slug>``, which the
  renderer derives with the prefix stripped, so the key does not change and
  the rename lands in place. Not checked (the factory has no recommendation
  client).

Safety rules, all of which must hold before an object is deleted:

1. Its name is exactly the legacy spelling of a current repo object's name
   (``[VCF CF] X`` -> ``[VCF Content Factory] X``). No pattern match, no
   prefix match: only names computed from the repo's content.
2. The replacement, an object with the exact new name, exists on the
   instance. Nothing is deleted before its successor is installed.
3. Where the repo owns the id (super metrics, views, dashboards, reports):
   the new-named twin carries the repo id and the leftover does not. A
   legacy-named object that still carries the repo id, or a twin that does
   not, is reported as a conflict and left alone.
4. Where the server owns the id (custom groups, symptoms, alerts): the
   leftover is a different object from the twin (different id).

The default is a dry run; ``--apply`` deletes. Deletion order runs
dependents first: reports, dashboards, views, alerts, symptoms, custom
groups, super metrics. Report definitions have no delete API: a report
leftover is listed for removal in the UI.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import yaml

from vcfcf_core.naming import LEGACY_FACTORY_PREFIX_LABEL, legacy_name

from ._profile_cli import add_profile_arg, resolve_profile_from_args
from .migrate_prefix import detect_layout

#: Content-type directory -> kind, in deletion order (dependents first).
KINDS = ("report", "dashboard", "view", "alert", "symptom", "customgroup", "supermetric")
_DIR_KIND = {
    "reports": "report",
    "dashboards": "dashboard",
    "views": "view",
    "alerts": "alert",
    "symptoms": "symptom",
    "customgroups": "customgroup",
    "supermetrics": "supermetric",
}
#: Kinds whose YAML carries the id the instance keeps.
ID_OWNED = frozenset({"supermetric", "view", "dashboard", "report"})
_DEFAULT_NAME_PATH = "VCF Content Factory"


@dataclass(frozen=True)
class RepoItem:
    kind: str
    name: str
    id: Optional[str]
    source: str
    name_path: str = ""


@dataclass
class Action:
    kind: str
    verdict: str  # "delete" | "skip" | "conflict" | "manual"
    name: str
    id: Optional[str]
    reason: str
    source: str = ""


@dataclass
class CleanupPlan:
    actions: List[Action] = field(default_factory=list)

    def by_verdict(self, verdict: str) -> List[Action]:
        return [a for a in self.actions if a.verdict == verdict]


# ---------------------------------------------------------------------------
# Repo side
# ---------------------------------------------------------------------------

def _read_item(kind: str, path: Path) -> Optional[RepoItem]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        return None
    ident = data.get("id")
    name_path = ""
    if kind == "dashboard":
        name_path = str(data.get("name_path") or _DEFAULT_NAME_PATH)
    return RepoItem(kind=kind, name=data["name"].strip(),
                    id=str(ident) if ident else None, source=str(path),
                    name_path=name_path)


def collect_repo_items(root: Path) -> List[RepoItem]:
    """Every content object under *root* whose name carries the current prefix.

    Factory checkout: ``content/<type>/`` and ``third_party/**/<type>/``. Pak
    repo: the ``bundled_content`` lists in ``adapter.yaml``, which are what a
    pak install puts on the instance.
    """
    root = root.resolve()
    layout = detect_layout(root)
    if layout is None:
        raise ValueError(f"{root}: neither a factory checkout nor a pak repo")
    paths: List[tuple] = []
    if layout == "pak":
        raw = yaml.safe_load((root / "adapter.yaml").read_text(encoding="utf-8")) or {}
        bundled = raw.get("bundled_content") or {}
        for dirname, kind in _DIR_KIND.items():
            for rel in bundled.get(dirname) or []:
                paths.append((kind, root / str(rel)))
    else:
        for dirname, kind in _DIR_KIND.items():
            base = root / "content" / dirname
            if base.is_dir():
                paths.extend((kind, p) for p in sorted(base.rglob("*.y*ml")))
            tp = root / "third_party"
            if tp.is_dir():
                paths.extend((kind, p) for p in sorted(tp.glob(f"**/{dirname}/*.y*ml"))
                             if "debug" not in p.parts)
    items = []
    for kind, p in paths:
        it = _read_item(kind, p)
        if it is not None and legacy_name(it.name) is not None:
            items.append(it)
    return items


# ---------------------------------------------------------------------------
# Planning (pure: live listings are passed in)
# ---------------------------------------------------------------------------

def _names_for(item: RepoItem, name: str) -> set:
    """The listing names that mean *name* for *item* (dashboards may carry a folder)."""
    out = {name}
    if item.kind == "dashboard" and item.name_path:
        out.add(f"{item.name_path}/{name}")
    return out


def plan_cleanup(items: Iterable[RepoItem], live: Dict[str, List[dict]]) -> CleanupPlan:
    """Decide, per legacy-named object on the instance, delete or leave.

    *live* maps kind -> list of ``{"id": ..., "name": ...}`` as listed on the
    instance. Kinds missing from *live* are not checked.
    """
    plan = CleanupPlan()
    items = sorted(items, key=lambda i: (KINDS.index(i.kind), i.name))
    for item in items:
        if item.kind not in live:
            continue
        old = legacy_name(item.name)
        entries = live[item.kind]
        old_names = _names_for(item, old)
        new_names = _names_for(item, item.name)
        leftovers = [e for e in entries if e.get("name") in old_names]
        twins = [e for e in entries if e.get("name") in new_names]
        for lo in leftovers:
            lo_id = str(lo.get("id") or "")
            act = Action(kind=item.kind, verdict="skip", name=str(lo.get("name")),
                         id=lo_id or None, reason="", source=item.source)
            plan.actions.append(act)
            if not twins:
                act.reason = (f'no "{item.name}" on the instance yet: sync the '
                              f"renamed content first, then run this again")
                continue
            twin_ids = {str(t.get("id") or "") for t in twins}
            if item.kind in ID_OWNED:
                repo_id = (item.id or "").lower()
                if not repo_id:
                    act.verdict = "conflict"
                    act.reason = "the repo object has no id to compare"
                elif lo_id.lower() == repo_id:
                    act.verdict = "conflict"
                    act.reason = (f"the old-named object still carries the repo id "
                                  f"{item.id}; deleting it would delete that id. "
                                  f"Check the instance by hand")
                elif repo_id not in {t.lower() for t in twin_ids}:
                    act.verdict = "conflict"
                    act.reason = (f'"{item.name}" exists but not with the repo id '
                                  f"{item.id}. Check the instance by hand")
                else:
                    act.verdict = "manual" if item.kind == "report" else "delete"
                    act.reason = (f'"{item.name}" is installed with the repo id')
                    if item.kind == "report":
                        act.reason += ("; report definitions have no delete API: remove "
                                       "it in Administration > Content > Reports")
            else:
                if lo_id and lo_id in twin_ids:
                    act.verdict = "conflict"
                    act.reason = "the old and new names list the same id"
                else:
                    act.verdict = "delete"
                    act.reason = f'"{item.name}" is installed as a separate object'
    return plan


# ---------------------------------------------------------------------------
# Instance side
# ---------------------------------------------------------------------------

def _pairs(objs: Iterable[dict], name_of: Callable[[dict], Optional[str]]) -> List[dict]:
    out = []
    for o in objs:
        n = name_of(o)
        if o.get("id") and n:
            out.append({"id": str(o["id"]), "name": n})
    return out


class Instance:
    """Lists and deletes the seven kinds on one profile. Clients are built lazily."""

    def __init__(self, profile: Optional[str], default_profile: str):
        self.profile = profile
        self.default = default_profile
        self._clients: dict = {}

    def _client(self, key: str):
        if key in self._clients:
            return self._clients[key]
        kw = {"profile": self.profile, "default_profile": self.default}
        if key == "sm":
            from vcfcf_supermetrics.client import VCFOpsClient as C
            c = C.from_env(**kw)
        elif key == "cg":
            from vcfcf_customgroups.client import VCFOpsCustomGroupClient as C
            c = C.from_env(**kw)
        elif key == "sym":
            from vcfcf_symptoms.client import VCFOpsSymptomsClient as C
            c = C.from_env(**kw)
        elif key == "alert":
            from vcfcf_alerts.client import VCFOpsAlertsClient as C
            c = C.from_env(**kw)
        elif key == "suite":
            from vcfcf_common.client import VCFOpsClient as C
            c = C.from_env(**kw)
        elif key == "ui":
            from vcfcf_dashboards.ui_client import VCFOpsUIClient as C
            c = C.from_env(**kw)
            c.login()
        else:  # pragma: no cover
            raise KeyError(key)
        self._clients[key] = c
        return c

    def close(self) -> None:
        ui = self._clients.get("ui")
        if ui is not None:
            try:
                ui.logout()
            except Exception:  # noqa: BLE001
                pass

    def list(self, kind: str) -> List[dict]:
        if kind == "supermetric":
            return _pairs(self._client("sm").list_supermetrics(), lambda o: o.get("name"))
        if kind == "customgroup":
            return _pairs(
                (g for g in self._client("cg").list_groups()
                 if (g.get("resourceKey") or {}).get("adapterKindKey") == "Container"),
                lambda o: (o.get("resourceKey") or {}).get("name"))
        if kind == "symptom":
            return _pairs(self._client("sym").list_symptoms(), lambda o: o.get("name"))
        if kind == "alert":
            return _pairs(self._client("alert").list_alerts(), lambda o: o.get("name"))
        if kind == "report":
            from vcfcf_reports.client import list_reports
            return _pairs(list_reports(self._client("suite")), lambda o: o.get("name"))
        if kind == "dashboard":
            return _pairs(self._client("ui").list_dashboards(), lambda o: o.get("name"))
        if kind == "view":
            from vcfcf_dashboards.cli import flatten_view_groups
            return _pairs(flatten_view_groups(self._client("ui").list_views()),
                          lambda o: o.get("name"))
        raise KeyError(kind)

    def delete(self, a: Action) -> None:
        if a.kind == "supermetric":
            self._client("sm").delete_supermetric(a.id)
        elif a.kind == "customgroup":
            self._client("cg").delete_group(a.id)
        elif a.kind == "symptom":
            self._client("sym").delete_symptom(a.id)
        elif a.kind == "alert":
            self._client("alert").delete_alert(a.id)
        elif a.kind == "dashboard":
            self._client("ui").delete_dashboards([(a.id, a.name)])
        elif a.kind == "view":
            self._client("ui").delete_view(a.id, a.name)
        else:
            raise ValueError(f"no delete path for {a.kind}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run(root: Path, instance, kinds: Sequence[str], apply: bool, out=None) -> int:
    out = out or sys.stdout
    items = collect_repo_items(root)
    wanted = [k for k in KINDS if k in kinds and any(i.kind == k for i in items)]
    live: Dict[str, List[dict]] = {}
    for k in wanted:
        live[k] = instance.list(k)
    plan = plan_cleanup(items, live)
    print(f"cleanup-legacy-prefix: {len(items)} prefixed object(s) in {root}; "
          f"checked {', '.join(wanted) or 'nothing'}", file=out)
    if not plan.actions:
        print(f'  no "{LEGACY_FACTORY_PREFIX_LABEL} ..." object matching the repo '
              f"is on the instance", file=out)
        return 0
    for a in plan.actions:
        tag = {"delete": "DELETE" if apply else "WOULD DELETE", "skip": "SKIP",
               "conflict": "CONFLICT", "manual": "MANUAL"}[a.verdict]
        print(f"  {tag:12s} {a.kind:11s} {a.id or '-'}  {a.name}", file=out)
        print(f"               {a.reason}", file=out)
    rc = 0
    if apply:
        for a in plan.by_verdict("delete"):
            try:
                instance.delete(a)
                print(f"  deleted {a.kind} {a.id}  {a.name}", file=out)
            except Exception as e:  # noqa: BLE001
                print(f"  FAILED {a.kind} {a.id}  {a.name}: {e}", file=sys.stderr)
                rc = 2
    else:
        n = len(plan.by_verdict("delete"))
        print(f"  dry run: {n} object(s) would be deleted; pass --apply to delete", file=out)
    if plan.by_verdict("conflict") and rc == 0:
        rc = 1
    return rc


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m vcfcf_common cleanup-legacy-prefix",
        description=(
            "List (default) or delete the objects a content-prefix rename left on "
            "an instance: exact legacy names of the repo's current content whose "
            "renamed successor is installed. Never a pattern delete."
        ),
    )
    ap.add_argument("root", nargs="?", default=".",
                    help="factory checkout or pak repo whose content defines the names (default: .)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="list only (the default)")
    mode.add_argument("--apply", action="store_true",
                      help="delete the objects marked WOULD DELETE")
    ap.add_argument("--types", default=",".join(KINDS),
                    help=f"comma-separated kinds to check (default: {','.join(KINDS)})")
    add_profile_arg(ap, default="devel")
    args = ap.parse_args(list(argv) if argv is not None else None)

    kinds = [k.strip() for k in args.types.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        print(f"ERROR: unknown kind(s) {bad}; choose from {list(KINDS)}", file=sys.stderr)
        return 2
    try:
        profile, default = resolve_profile_from_args(args)
        inst = Instance(profile, default)
        try:
            return run(Path(args.root), inst, kinds, args.apply)
        finally:
            inst.close()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
