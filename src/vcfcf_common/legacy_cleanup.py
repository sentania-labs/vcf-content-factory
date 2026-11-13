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
  checked anyway, and any legacy-named one is reported, never deleted;
- recommendations: keyed by ``Recommendation-df-<kind>-<slug>``, which the
  renderer derives with the prefix stripped, so the key does not change and
  the rename lands in place. Not checked (the factory has no recommendation
  client).

Safety rules, all of which must hold before an object is deleted:

1. Its name is exactly the legacy spelling of a current repo object's name
   (``[VCF CF] X`` -> ``[VCF Content Factory] X``). No pattern match, no
   prefix match: only names computed from the repo's content.
2. It is the same kind of object as the repo's: symptoms and alerts match
   on name, adapter kind and resource kind; custom groups on name and group
   type. A same-named object of another kind (a pak's symptom beside the
   factory's MPB one) is not this repo's and is left alone.
3. The replacement, an object with the exact new name (and the same kind),
   exists on the instance. Nothing is deleted before its successor is
   installed.
4. Super metrics, views and reports: never deleted. Their import is keyed
   by the YAML UUID, so the rename lands in place; a legacy-named object
   under another id is not a leftover of this migration (a pak's object, a
   user's clone) and is reported as a conflict.
5. Dashboards: the new-named twin carries the repo id, the leftover does
   not, and the leftover's owner is the account the factory's dashboard
   sync imports as on this profile (``/api/auth/currentuser``). Anything
   else is a conflict.
6. Custom groups, symptoms, alerts (server-owned ids): the leftover is a
   different object from the twin (different id).

The default is a dry run. It names the profile and host first, ends with
what to back up, a plan digest and the exact apply command (every input
that shapes the plan: ROOT, ``--types``, ``--profile``), and ``--apply``
needs ``--plan-digest <digest>``: the plan is recomputed and nothing is
deleted unless its scope (profile, ROOT, kinds), host and verdicts are the
ones reviewed. Deletion runs dependents first
(dashboards, alerts, symptoms, custom groups) and stops at the first
failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from vcfcf_core.naming import CLEANUP_COMMAND, LEGACY_FACTORY_PREFIX_LABEL, legacy_name

from ._env import load_dotenv, resolve_profile_credentials
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
#: Id-owned kinds whose rename lands in place: never deleted here.
IN_PLACE = frozenset({"supermetric", "view", "report"})
#: Kinds whose identity on the instance includes their adapter/resource kind.
_KIND_SCOPED = frozenset({"symptom", "alert"})
_DEFAULT_NAME_PATH = "VCF Content Factory"


@dataclass(frozen=True)
class RepoItem:
    kind: str
    name: str
    id: Optional[str]
    source: str
    name_path: str = ""
    adapter_kind: str = ""   # symptoms, alerts
    resource_kind: str = ""  # symptoms, alerts
    group_type: str = ""     # custom groups


@dataclass
class Action:
    kind: str
    verdict: str  # "delete" | "skip" | "conflict"
    name: str
    id: Optional[str]
    reason: str
    source: str = ""
    owner: str = ""
    twin_id: str = ""


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
    def _s(key: str, default: str = "") -> str:
        return str(data.get(key) or default).strip()
    return RepoItem(kind=kind, name=data["name"].strip(),
                    id=str(ident) if ident else None, source=str(path),
                    name_path=name_path,
                    adapter_kind=_s("adapter_kind") if kind in _KIND_SCOPED else "",
                    resource_kind=_s("resource_kind") if kind in _KIND_SCOPED else "",
                    # The customgroups loader defaults the type to Environment.
                    group_type=_s("type", "Environment") if kind == "customgroup" else "")


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


def _scope_of(item: RepoItem) -> Optional[tuple]:
    """The non-name identity a live object must share with *item*, or None."""
    if item.kind in _KIND_SCOPED:
        return (item.adapter_kind, item.resource_kind)
    if item.kind == "customgroup":
        return (item.group_type,)
    return None


def _live_scope(item: RepoItem, entry: dict) -> Optional[tuple]:
    if item.kind in _KIND_SCOPED:
        return (str(entry.get("adapter_kind") or ""), str(entry.get("resource_kind") or ""))
    if item.kind == "customgroup":
        return (str(entry.get("group_type") or ""),)
    return None


def plan_cleanup(items: Iterable[RepoItem], live: Dict[str, List[dict]],
                 dashboard_owner: Optional[str] = None) -> CleanupPlan:
    """Decide, per legacy-named object on the instance, delete or leave.

    *live* maps kind -> list of ``{"id": ..., "name": ...}`` as listed on the
    instance, plus ``adapter_kind``/``resource_kind`` (symptoms, alerts),
    ``group_type`` (custom groups) and ``owner`` (dashboards). Kinds missing
    from *live* are not checked. *dashboard_owner* is the account the
    factory's dashboard sync imports as on this profile; without it no
    dashboard is deleted.
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
        scope = _scope_of(item)

        def _ours(e: dict) -> bool:
            return scope is None or _live_scope(item, e) == scope

        named_old = [e for e in entries if e.get("name") in old_names]
        leftovers = [e for e in named_old if _ours(e)]
        twins = [e for e in entries if e.get("name") in new_names and _ours(e)]
        twin_ids = {str(t.get("id") or "") for t in twins}
        twin_label = ",".join(sorted(i for i in twin_ids if i)) or ""

        for e in named_old:
            if _ours(e):
                continue
            plan.actions.append(Action(
                kind=item.kind, verdict="skip", name=str(e.get("name")),
                id=str(e.get("id") or "") or None, source=item.source,
                reason=(f"same name, different {'/'.join(_live_scope(item, e) or ())!r} "
                        f"from the repo's {'/'.join(scope or ())!r}: not this repo's object")))

        for lo in leftovers:
            lo_id = str(lo.get("id") or "")
            act = Action(kind=item.kind, verdict="skip", name=str(lo.get("name")),
                         id=lo_id or None, reason="", source=item.source,
                         owner=str(lo.get("owner") or ""), twin_id=twin_label)
            plan.actions.append(act)
            repo_id = (item.id or "").lower()
            if scope is not None and not all(scope):
                act.verdict = "conflict"
                act.reason = (f"the repo object has no {'adapter/resource kind' if item.kind in _KIND_SCOPED else 'group type'} "
                              f"to compare")
                continue
            if item.kind in IN_PLACE:
                # The rename lands in place for these: a legacy-named object
                # with the repo id is the not-yet-synced object itself, and
                # one with any other id is not a leftover of this migration.
                if repo_id and lo_id.lower() == repo_id and not twins:
                    act.reason = ("the repo object, not yet renamed here: sync it and "
                                  "the rename lands in place")
                elif repo_id and lo_id.lower() == repo_id:
                    act.verdict = "conflict"
                    act.reason = (f"carries the repo id {item.id}, and \"{item.name}\" also "
                                  f"exists. Check the instance by hand")
                else:
                    act.verdict = "conflict"
                    act.reason = (f"not the repo's object (repo id {item.id or 'none'}): a "
                                  f"{item.kind} rename lands in place, so this is not a "
                                  f"leftover of the migration (a pak's object, or a "
                                  f"clone?). Never deleted here; check by hand")
                continue
            if not twins:
                act.reason = (f'no "{item.name}" on the instance yet: sync the '
                              f"renamed content first, then run this again")
                continue
            if item.kind == "dashboard":
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
                elif not dashboard_owner:
                    act.verdict = "conflict"
                    act.reason = ("the account the factory syncs dashboards as on this "
                                  "profile is unknown, so the owner cannot be checked")
                elif act.owner.lower() != dashboard_owner.lower():
                    act.verdict = "conflict"
                    act.reason = (f"owned by {act.owner or 'nobody listed'!r}, not "
                                  f"{dashboard_owner!r} (the account the factory syncs "
                                  f"dashboards as on this profile): someone else's. "
                                  f"Check by hand")
                else:
                    act.verdict = "delete"
                    act.reason = (f'"{item.name}" is installed with the repo id, and '
                                  f"this one is owned by {dashboard_owner!r}")
                continue
            if lo_id and lo_id in twin_ids:
                act.verdict = "conflict"
                act.reason = "the old and new names list the same id"
            else:
                act.verdict = "delete"
                act.reason = f'"{item.name}" is installed as a separate object'
    return plan


def canonical_kinds(kinds: Iterable[str]) -> List[str]:
    """*kinds* deduplicated, in :data:`KINDS` order."""
    chosen = set(kinds)
    return [k for k in KINDS if k in chosen]


#: The digest's three parts, in order, as the refusal names them.
_DIGEST_PARTS = ("scope (profile, ROOT or selected kinds)", "host",
                 "plan (an object to delete, or a verdict)")
_DIGEST_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}$")


def _h8(obj) -> str:
    body = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]


def plan_digest(plan: CleanupPlan, profile: str, host: str, root: Path,
                kinds: Iterable[str]) -> str:
    """A digest of *plan* in one scope on one target, for ``--apply --plan-digest``.

    Three dash-joined parts: the scope (profile, resolved ROOT, selected
    kinds in canonical order), the host, and every action (kind, verdict,
    id, name). Another scope, another instance, a new leftover or a changed
    verdict changes it, and a refused apply can say which part moved.
    """
    scope = {"profile": profile.lower(), "root": str(Path(root).resolve()),
             "kinds": canonical_kinds(kinds)}
    actions = sorted([a.kind, a.verdict, a.id or "", a.name] for a in plan.actions)
    return "-".join((_h8(scope), _h8({"host": host.lower()}), _h8(actions)))


def _digest_mismatch(expected: Optional[str], digest: str) -> str:
    """Which parts of the reviewed plan differ, without naming any object."""
    if not expected:
        return "no digest was given"
    if not _DIGEST_RE.match(expected.strip().lower()):
        return ("the digest given is not one this version prints (digests from "
                "older dry runs no longer match)")
    given = expected.strip().lower().split("-")
    changed = [part for part, a, b in zip(_DIGEST_PARTS, given, digest.split("-")) if a != b]
    return "changed since the dry run: " + "; ".join(changed)


def apply_command(root: Path, profile: str, kinds: Sequence[str], digest: str,
                  types_given: bool = False) -> str:
    """The shell command that applies exactly the plan a dry run printed.

    Carries every input that shapes the plan: ROOT (absolute, unless it is
    the current directory, the default), ``--types`` when it was given or
    narrows the default, and ``--profile`` always, so the apply does not
    depend on ``VCFOPS_PROFILE``. Each argument is shell-quoted.
    """
    args = []
    resolved = Path(root).resolve()
    if resolved != Path.cwd().resolve():
        args.append(str(resolved))
    chosen = canonical_kinds(kinds)
    if types_given or chosen != list(KINDS):
        args += ["--types", ",".join(chosen)]
    args += ["--profile", profile, "--apply", "--plan-digest", digest]
    return CLEANUP_COMMAND + " " + " ".join(shlex.quote(a) for a in args)


# ---------------------------------------------------------------------------
# Instance side
# ---------------------------------------------------------------------------

def _pairs(objs: Iterable[dict], name_of: Callable[[dict], Optional[str]],
           extra: Optional[Callable[[dict], dict]] = None) -> List[dict]:
    out = []
    for o in objs:
        n = name_of(o)
        if o.get("id") and n:
            out.append({"id": str(o["id"]), "name": n, **(extra(o) if extra else {})})
    return out


def _kinds_of(o: dict) -> dict:
    return {"adapter_kind": o.get("adapterKindKey") or "",
            "resource_kind": o.get("resourceKindKey") or ""}


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
                lambda o: (o.get("resourceKey") or {}).get("name"),
                lambda o: {"group_type": (o.get("resourceKey") or {}).get("resourceKindKey") or ""})
        if kind == "symptom":
            return _pairs(self._client("sym").list_symptoms(), lambda o: o.get("name"), _kinds_of)
        if kind == "alert":
            return _pairs(self._client("alert").list_alerts(), lambda o: o.get("name"), _kinds_of)
        if kind == "report":
            from vcfcf_reports.client import list_reports
            return _pairs(list_reports(self._client("suite")), lambda o: o.get("name"))
        if kind == "dashboard":
            return _pairs(self._client("ui").list_dashboards(), lambda o: o.get("name"),
                          lambda o: {"owner": o.get("owner") or ""})
        if kind == "view":
            from vcfcf_dashboards.cli import flatten_view_groups
            return _pairs(flatten_view_groups(self._client("ui").list_views()),
                          lambda o: o.get("name"))
        raise KeyError(kind)

    def dashboard_owner(self) -> Optional[str]:
        """The account the factory's dashboard sync imports as on this profile.

        ``vcfcf_dashboards sync`` stamps the content zip with the
        ``/api/auth/currentuser`` account of the profile; the same call here.
        """
        from vcfcf_dashboards.client import current_user_name, get_current_user
        user = get_current_user(self._client("suite"))
        name = current_user_name(user, default="")
        return name or None

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

_TAG = {"delete": "DELETE", "skip": "SKIP", "conflict": "CONFLICT"}


def _backup_advice(plan: CleanupPlan, profile: str, host: str) -> List[str]:
    lines = [
        f"  BEFORE --apply: back up profile {profile!r} ({host}). Export its content",
        "  (Administration > Content > Export, all content types) or snapshot the",
        "  instance; a delete here cannot be undone. The objects to be deleted:",
    ]
    lines += [f"    {a.kind} {a.id}  {a.name}" for a in plan.by_verdict("delete")]
    return lines


def run(root: Path, instance, kinds: Sequence[str], apply: bool, out=None, *,
        target: Optional[Tuple[str, str, str]] = None,
        expected_digest: Optional[str] = None, types_given: bool = False) -> int:
    """List, or with *apply* delete, the legacy-named leftovers for *root*.

    *target* is ``(profile, host, how the profile was chosen)``, printed
    first. With *apply*, *expected_digest* must equal the digest of the plan
    recomputed now; otherwise nothing is deleted (rc 2). The first failed
    delete stops the run (rc 2). *types_given*: ``--types`` was on the
    command line, so the printed apply command repeats it.
    """
    out = out or sys.stdout
    profile, host, how = target or ("?", "?", "unknown")
    print(f"cleanup-legacy-prefix: profile={profile} host={host} ({how})", file=out)
    items = collect_repo_items(root)
    wanted = [k for k in KINDS if k in kinds and any(i.kind == k for i in items)]
    live: Dict[str, List[dict]] = {}
    for k in wanted:
        live[k] = instance.list(k)
    owner = None
    if "dashboard" in wanted and live.get("dashboard"):
        get_owner = getattr(instance, "dashboard_owner", None)
        owner = get_owner() if get_owner else None
    plan = plan_cleanup(items, live, dashboard_owner=owner)
    digest = plan_digest(plan, profile, host, root, kinds)
    print(f"  {len(items)} prefixed object(s) in {root}; "
          f"checked {', '.join(wanted) or 'nothing'}", file=out)
    if owner:
        print(f"  dashboards sync as {owner!r} on this profile", file=out)
    if not plan.actions:
        print(f'  no "{LEGACY_FACTORY_PREFIX_LABEL} ..." object matching the repo '
              f"is on the instance", file=out)
        return 0
    for a in plan.actions:
        tag = "WOULD DELETE" if a.verdict == "delete" and not apply else _TAG[a.verdict]
        print(f"  {tag:12s} {a.kind:11s} {a.id or '-'}  {a.name}", file=out)
        detail = []
        if a.kind == "dashboard":
            detail.append(f"owner={a.owner or '-'}")
        if a.twin_id:
            detail.append(f"new-named twin id={a.twin_id}")
        if detail:
            print(f"               {'  '.join(detail)}", file=out)
        print(f"               {a.reason}", file=out)
    deletes = plan.by_verdict("delete")
    conflicts = plan.by_verdict("conflict")

    if not apply:
        print(f"  dry run: {len(deletes)} to delete, {len(conflicts)} conflict(s), "
              f"{len(plan.by_verdict('skip'))} left alone", file=out)
        if deletes:
            for line in _backup_advice(plan, profile, host):
                print(line, file=out)
            print(f"  plan digest: {digest}", file=out)
            cmd = apply_command(root, profile, kinds, digest, types_given=types_given)
            print(f"  to delete exactly this plan: {cmd}", file=out)
        return 1 if conflicts else 0

    if expected_digest != digest:
        print(f"  REFUSED: the plan is not the one reviewed (digest now {digest}, "
              f"given {expected_digest or 'none'}): "
              f"{_digest_mismatch(expected_digest, digest)}. Run the dry run again, "
              f"review it, and run the command it prints. Nothing was deleted.",
              file=sys.stderr)
        return 2
    done: List[Action] = []
    for i, a in enumerate(deletes):
        try:
            instance.delete(a)
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED {a.kind} {a.id}  {a.name}: {e}", file=sys.stderr)
            print(f"  stopped at the first failure. Deleted {len(done)}:", file=sys.stderr)
            for d in done:
                print(f"    deleted      {d.kind} {d.id}  {d.name}", file=sys.stderr)
            print(f"  Not deleted ({len(deletes) - len(done)}):", file=sys.stderr)
            for n in deletes[i:]:
                print(f"    not deleted  {n.kind} {n.id}  {n.name}", file=sys.stderr)
            return 2
        done.append(a)
        print(f"  deleted {a.kind} {a.id}  {a.name}", file=out)
    print(f"  deleted {len(done)} object(s)", file=out)
    return 1 if conflicts else 0


def resolve_target(profile_arg: Optional[str]) -> Tuple[str, str, str]:
    """``(profile, host, how)`` for the instance to act on. No silent default.

    The profile comes from ``--profile`` or from ``VCFOPS_PROFILE`` (shell
    or ``.env``); with neither, ``ValueError``: this command deletes, so it
    does not fall back to a per-command default.
    """
    load_dotenv()
    if profile_arg and profile_arg.strip():
        name, how = profile_arg.strip(), "from --profile"
    elif os.environ.get("VCFOPS_PROFILE", "").strip():
        name = os.environ["VCFOPS_PROFILE"].strip()
        how = "from the VCFOPS_PROFILE environment variable (shell or .env)"
    else:
        raise ValueError(
            "no profile: pass --profile NAME or set VCFOPS_PROFILE. This command "
            "can delete content, so it does not default to a profile.")
    creds = resolve_profile_credentials(name)
    return name.lower(), creds.host, how


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m vcfcf_common cleanup-legacy-prefix",
        description=(
            "List (default) or delete the objects a content-prefix rename left on "
            "an instance: exact legacy names of the repo's current content whose "
            "renamed successor is installed. Never a pattern delete."
        ),
        # No abbreviations: "--a" / "--appl" must not mean --apply.
        allow_abbrev=False,
    )
    ap.add_argument("root", nargs="?", default=".",
                    help="factory checkout or pak repo whose content defines the names (default: .)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="list only (the default)")
    mode.add_argument("--apply", action="store_true",
                      help="delete the objects marked WOULD DELETE; needs --plan-digest")
    ap.add_argument("--plan-digest", metavar="DIGEST", default=None,
                    help="the digest the dry run printed; --apply deletes only if the "
                         "plan recomputed now has the same scope (profile, ROOT, "
                         "--types), host and verdicts. Run the apply command the dry "
                         "run prints: it repeats every one of those inputs")
    ap.add_argument("--types", default=None,
                    help=f"comma-separated kinds to check (default: {','.join(KINDS)}); "
                         f"part of the plan, so --apply must repeat it")
    ap.add_argument("--profile", metavar="NAME", default=None,
                    help="credential profile (VCFOPS_<NAME>_HOST/USER/PASSWORD in .env). "
                         "Required unless VCFOPS_PROFILE is set; no default")
    args = ap.parse_args(list(argv) if argv is not None else None)

    types_given = args.types is not None
    raw_types = args.types if types_given else ",".join(KINDS)
    kinds = [k.strip() for k in raw_types.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        print(f"ERROR: unknown kind(s) {bad}; choose from {list(KINDS)}", file=sys.stderr)
        return 2
    if args.apply and not args.plan_digest:
        print("ERROR: --apply needs --plan-digest DIGEST from a dry run of the same "
              "plan; run without --apply first", file=sys.stderr)
        return 2
    try:
        target = resolve_target(args.profile)
        inst = Instance(target[0], target[0])
        try:
            return run(Path(args.root), inst, kinds, args.apply, target=target,
                       expected_digest=args.plan_digest, types_given=types_given)
        finally:
            inst.close()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
