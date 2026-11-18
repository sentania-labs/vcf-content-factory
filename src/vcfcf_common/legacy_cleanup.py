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
- dashboards: a content-zip import is keyed by name (measured on 8.18.7,
  9.0.2 and 9.1.1): syncing the renamed dashboard beside the old-named one
  adds a second dashboard under a server-assigned id, and the old-named one
  keeps the repo id (the two-copy state, rule 5);
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
   sync imports as on this profile (``/api/auth/currentuser``): delete.
   RESYNC, every same-named copy listed, never applied here (it leaves no
   dashboard of that name until the re-import, rule 3): the old-named one
   carries the repo id and no new-named copy does (what a normal sync
   leaves, or what a sync would cause), or only new-named copies remain
   and none carries it. The printed remedy is one delete of every copy of
   every RESYNC dashboard, a re-run of the dry run that must show no
   RESYNC, then one sync per dashboards tree (a sync re-imports the whole
   tree, so syncing while any copy remains adds one). Anything else is a
   conflict. A dashboard delete is verified by re-listing: HTTP 200 is not
   a delete.
6. Custom groups, symptoms, alerts (server-owned ids): the leftover is a
   different object from the twin (different id).

The default is a dry run. It names the profile and host first, ends with
what to back up, a plan digest and the exact apply command (every input
that shapes the plan: ROOT, ``--types``, ``--profile``), and ``--apply``
needs ``--plan-digest <digest>``: the plan is recomputed and nothing is
deleted unless its scope (profile, ROOT, kinds), host and verdicts are the
ones reviewed. Deletion runs dependents first
(dashboards, alerts, symptoms, custom groups) and stops at the first
failure. Exit 1 when a conflict or a RESYNC dashboard was listed.
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
    verdict: str  # "delete" | "skip" | "conflict" | "resync"
    name: str
    id: Optional[str]
    reason: str
    source: str = ""
    owner: str = ""
    twin_id: str = ""
    locked: bool = False


@dataclass
class Resync:
    """A dashboard not under the repo id, fixed by hand (rule 5): delete
    every copy, then import once.

    *state*: ``two-copy`` (old-named copy under the repo id beside new-named
    copies), ``old-only`` (old-named copy under the repo id, no new-named
    copy: a sync now would add one), ``new-only`` (new-named copies only,
    none under the repo id: a sync updates one by name and the repo id never
    returns). *copies*: every same-named dashboard (old and new name), as
    ``(id, name, owner, locked)``. *blockers*: ``(id, owner, reason)`` per
    copy whose listed owner differs from the session user.
    """
    name: str
    repo_id: str
    source: str
    state: str = "two-copy"  # "two-copy" | "old-only" | "new-only"
    copies: List[tuple] = field(default_factory=list)
    blockers: List[tuple] = field(default_factory=list)


@dataclass
class CleanupPlan:
    actions: List[Action] = field(default_factory=list)
    resyncs: List[Resync] = field(default_factory=list)

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


_RESYNC_STATE = {
    "two-copy": ("old-named copy under the repo id {rid} beside {n} new-named copy(ies) "
                 "under server-assigned ids: the import of \"{name}\" is keyed by name, "
                 "so it added a dashboard instead of renaming this one"),
    "old-only": ("old-named copy under the repo id {rid} and no new-named copy: a sync "
                 "now adds a second dashboard beside it (the import is keyed by name) "
                 "instead of renaming it"),
    "new-only": ("only new-named copies remain, {n} of them, none under the repo id "
                 "{rid}: a sync updates one by name and the repo id never returns"),
}


def _resync_dashboard(plan: CleanupPlan, item: RepoItem, olds: List[dict],
                      twins: List[dict], dashboard_owner: Optional[str],
                      state: str) -> None:
    """Record a dashboard that is not under the repo id: every copy listed,
    verdict resync, never deleted here.

    A content-zip dashboard import is keyed by name (8.18.7, 9.0.2, 9.1.1,
    ``investigations/2026-11-18-dashboard-import-by-name-and-delete-noop.md``).
    The remedy, proven on all three: delete every copy, then import again;
    with no dashboard of that name or id present the import lands under the
    repo id with the new name. Not applied here: it leaves no dashboard of
    that name until the re-import (rule 3).
    """
    from vcfcf_dashboards.ui_client import dashboard_delete_blockers, is_true
    rs = Resync(name=item.name, repo_id=item.id or "", source=item.source, state=state)
    summary = _RESYNC_STATE[state].format(rid=item.id, n=len(twins), name=item.name)
    for e, is_old in [(o, True) for o in olds] + [(t, False) for t in twins]:
        eid = str(e.get("id") or "")
        owner = str(e.get("owner") or "")
        locked = is_true(e.get("locked"))
        if is_old and eid.lower() == (item.id or "").lower():
            reason = summary
        elif is_old:
            reason = "another old-named copy (not under the repo id)"
        elif state == "new-only":
            reason = summary
        else:
            reason = (f"new-named copy under a server-assigned id, not the repo id "
                      f"{item.id}")
            if len(twins) > 1:
                reason += (f" ({len(twins)} new-named copies: each sync on this state, "
                           f"for instance after a delete that did not take, adds one)")
        plan.actions.append(Action(
            kind="dashboard", verdict="resync", name=str(e.get("name")), id=eid or None,
            reason=reason, source=item.source, owner=owner, locked=locked))
        rs.copies.append((eid, str(e.get("name")), owner, locked))
        why = dashboard_delete_blockers(e, dashboard_owner)
        if why:
            rs.blockers.append((eid, owner, "; ".join(why)))
    plan.resyncs.append(rs)


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
        repo_lc = (item.id or "").lower()
        if item.kind == "dashboard" and repo_lc:
            # Import is keyed by name: any state where the repo id is not on
            # the new name, and the old name or a new-named copy holds the
            # name, needs every copy deleted and one import (rule 5).
            twin_has_repo = repo_lc in {t.lower() for t in twin_ids}
            old_has_repo = any(str(e.get("id") or "").lower() == repo_lc for e in leftovers)
            if old_has_repo and not twin_has_repo:
                _resync_dashboard(plan, item, leftovers, twins, dashboard_owner,
                                  "two-copy" if twins else "old-only")
                continue
            if not leftovers and twins and not twin_has_repo:
                _resync_dashboard(plan, item, [], twins, dashboard_owner, "new-only")
                continue

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
                    # Guard only: an old-named copy under the repo id is RESYNC
                    # above unless a new-named copy lists the same id, which
                    # one id under two names cannot be. Never delete the repo id.
                    act.verdict = "conflict"
                    act.reason = (f"the old-named object carries the repo id "
                                  f"{item.id} and a new-named one lists it too; "
                                  f"deleting it would delete that id. Check by hand")
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
                    act.reason = (f"listed owner {act.owner or 'none'!r} differs from "
                                  f"session user {dashboard_owner!r} (the account the "
                                  f"factory syncs dashboards as on this profile). "
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


def dry_run_command(root: Path, profile: str, kinds: Sequence[str],
                    types_given: bool = False) -> str:
    """The shell command that repeats this dry run (same ROOT, kinds, profile)."""
    return CLEANUP_COMMAND + " " + " ".join(
        shlex.quote(a) for a in _scope_args(root, profile, kinds, types_given))


def _scope_args(root: Path, profile: str, kinds: Sequence[str],
                types_given: bool) -> List[str]:
    args = []
    resolved = Path(root).resolve()
    if resolved != Path.cwd().resolve():
        args.append(str(resolved))
    chosen = canonical_kinds(kinds)
    if types_given or chosen != list(KINDS):
        args += ["--types", ",".join(chosen)]
    return args + ["--profile", profile]


def apply_command(root: Path, profile: str, kinds: Sequence[str], digest: str,
                  types_given: bool = False) -> str:
    """The shell command that applies exactly the plan a dry run printed.

    Carries every input that shapes the plan: ROOT (absolute, unless it is
    the current directory, the default), ``--types`` when it was given or
    narrows the default, and ``--profile`` always, so the apply does not
    depend on ``VCFOPS_PROFILE``. Each argument is shell-quoted.
    """
    args = _scope_args(root, profile, kinds, types_given)
    args += ["--apply", "--plan-digest", digest]
    return CLEANUP_COMMAND + " " + " ".join(shlex.quote(a) for a in args)


# ---------------------------------------------------------------------------
# Instance side
# ---------------------------------------------------------------------------

def _pairs(objs: Iterable[dict], name_of: Callable[[dict], Optional[str]],
           extra: Optional[Callable[[dict], dict]] = None,
           id_of: Callable[[dict], Optional[str]] = lambda o: o.get("id")) -> List[dict]:
    out = []
    for o in objs:
        n = name_of(o)
        i = id_of(o)
        if i and n:
            out.append({"id": str(i), "name": n, **(extra(o) if extra else {})})
    return out


def _view_id(o: dict) -> Optional[str]:
    """A view thumbnail's id: ``viewDefinitionKey`` (the listing on 8.18.7,
    9.0.2 and 9.1.1 carries no ``id``), ``id`` as a fallback for older shapes."""
    return o.get("viewDefinitionKey") or o.get("id")


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
            # Strict: an unreadable answer must not read as "nothing installed".
            return _pairs(self._client("ui").list_dashboards_strict(), lambda o: o.get("name"),
                          lambda o: {"owner": o.get("owner") or "",
                                     "locked": o.get("locked"),
                                     "edit": o.get("edit")})
        if kind == "view":
            from vcfcf_dashboards.cli import flatten_view_groups
            return _pairs(flatten_view_groups(self._client("ui").list_views()),
                          lambda o: o.get("name"), id_of=_view_id)
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
            # HTTP 200 is not a delete (on 9.1.1 a non-owner's delete is a
            # 200 no-op); re-list and check.
            from vcfcf_dashboards.ui_client import SAME_ID_COPY_NOTE, dashboard_delete_blockers
            res = self._client("ui").delete_dashboards_verified([(a.id, a.name)])
            if res.remaining:
                # Same identity source as the plan's owner check.
                why = dashboard_delete_blockers(res.remaining[0], self.dashboard_owner())
                raise RuntimeError(
                    "still listed after the delete (the server answered 200)"
                    + (f"; likely cause: {'; '.join(why)}" if why else "")
                    + f"; {SAME_ID_COPY_NOTE}")
            if res.unverifiable:
                raise RuntimeError(f"delete not verified: {res.note}")
            if res.unlisted:
                raise RuntimeError("not listed before the delete, so the delete "
                                   "cannot be verified")
        elif a.kind == "view":
            self._client("ui").delete_view(a.id, a.name)
        else:
            raise ValueError(f"no delete path for {a.kind}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_TAG = {"delete": "DELETE", "skip": "SKIP", "conflict": "CONFLICT", "resync": "RESYNC"}


def _sync_step(root: Path, source: str, profile: str) -> str:
    """How to import the dashboard at *source* again, from *root*."""
    root = Path(root).resolve()
    src = Path(source).resolve()
    q = shlex.quote
    if detect_layout(root) == "pak":
        return ("re-install the pak built from this repo, which imports its "
                "dashboards again (the import-by-name behaviour was measured for "
                "content-zip imports, not for pak installs)")
    cmd = "python3 -m vcfcf_dashboards"
    # The dashboards tree the file belongs to: the nearest "dashboards" folder.
    tree = next((p for p in src.parents if p.name == "dashboards"), src.parent)
    if tree != root / "content" / "dashboards":
        try:
            dash_dir = tree.relative_to(root)
        except ValueError:
            dash_dir = tree
        views = tree.parent / "views"
        if views.is_dir():
            try:
                cmd += f" --views-dir {q(str(views.relative_to(root)))}"
            except ValueError:
                cmd += f" --views-dir {q(str(views))}"
        cmd += f" --dashboards-dir {q(str(dash_dir))}"
    cmd += f" sync --profile {q(profile)}"
    where = "" if root == Path.cwd().resolve() else f"cd {q(str(root))} && "
    return where + cmd


def _resync_advice(plan: CleanupPlan, root: Path, profile: str, kinds: Sequence[str],
                   types_given: bool = False) -> List[str]:
    """The by-hand remedy for every RESYNC dashboard, in the only safe order.

    One delete of every copy of every RESYNC dashboard, then a re-run of the
    dry run that must show no RESYNC line, then one sync per dashboards
    tree. Never a delete-then-sync pair per dashboard: ``vcfcf_dashboards
    sync`` re-imports the whole tree, so a sync while another RESYNC
    dashboard still has a copy adds a copy of it under an id no printed
    delete covers.
    """
    q = shlex.quote
    lines = [
        f"  RESYNC: {len(plan.resyncs)} dashboard(s) not under their repo id. A dashboard",
        "  import is keyed by name: delete every copy, then import once, and it lands",
        "  under the repo id with the new name. Until the import the dashboard is not on",
        "  the instance. This tool does not do it. Follow the steps in order: a sync",
        "  re-imports the whole dashboards tree, not one dashboard, so syncing while any",
        "  RESYNC dashboard still has a copy adds another copy of it, under an id none",
        "  of the delete commands below covers.",
    ]
    for rs in plan.resyncs:
        lines.append(f'    "{rs.name}" (repo id {rs.repo_id}, {len(rs.copies)} '
                     f"cop{'y' if len(rs.copies) == 1 else 'ies'}, {rs.state})")
    # Step 1: one command for the copies this profile can be expected to
    # delete, one per other listed owner.
    blocked = {}
    for rs in plan.resyncs:
        for eid, owner, _why in rs.blockers:
            blocked[eid] = owner
    mine = [c[0] for rs in plan.resyncs for c in rs.copies if c[0] and c[0] not in blocked]
    others: Dict[str, List[str]] = {}
    for rs in plan.resyncs:
        for c in rs.copies:
            if c[0] in blocked:
                others.setdefault(blocked[c[0]], []).append(c[0])
    lines.append("  1. Delete every copy of every RESYNC dashboard:")
    if mine:
        lines.append(f"       python3 -m vcfcf_dashboards delete-dashboard "
                     f"{' '.join(q(i) for i in mine)} --profile {q(profile)}")
    for owner, ids in others.items():
        lines.append(f"     listed owner {owner!r} differs from the session user of profile "
                     f"{profile!r}; on 9.1.1 only the owner's delete deletes (a "
                     f"non-owner's answers 200 and deletes nothing), so run this on a "
                     f"profile that signs in as {owner!r}:")
        lines.append(f"       python3 -m vcfcf_dashboards delete-dashboard "
                     f"{' '.join(q(i) for i in ids)} --profile <that profile>")
    lines.append("     delete-dashboard re-lists afterwards and exits non-zero if any copy "
                 "is still listed.")
    lines.append("  2. Re-run this dry run and confirm no RESYNC line remains:")
    lines.append(f"       {dry_run_command(root, profile, kinds, types_given)}")
    lines.append("     If any remains, repeat step 1 for the ids it lists. Do not sync "
                 "until none remains.")
    lines.append("  3. Import once per dashboards tree:")
    steps: List[str] = []
    for rs in plan.resyncs:
        step = _sync_step(root, rs.source, profile)
        if step not in steps:
            steps.append(step)
    lines += [f"       {st}" for st in steps]
    return lines


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
        try:
            live[k] = instance.list(k)
        except Exception as e:  # noqa: BLE001 - an unread listing is not "none installed"
            print(f"  ERROR: could not list {k}s on the instance: {e}. No plan was made "
                  f"and nothing was deleted.", file=sys.stderr)
            return 2
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
            if a.locked:
                detail.append("locked")
        if a.twin_id:
            detail.append(f"new-named twin id={a.twin_id}")
        if detail:
            print(f"               {'  '.join(detail)}", file=out)
        print(f"               {a.reason}", file=out)
    deletes = plan.by_verdict("delete")
    conflicts = plan.by_verdict("conflict")
    # Exit 1 when anything needs a person: a conflict, or a RESYNC dashboard.
    attention = bool(conflicts or plan.resyncs)
    if plan.resyncs:
        for line in _resync_advice(plan, root, profile, kinds, types_given):
            print(line, file=out)

    if not apply:
        print(f"  dry run: {len(deletes)} to delete, {len(conflicts)} conflict(s), "
              f"{len(plan.resyncs)} RESYNC dashboard(s) to fix by hand, "
              f"{len(plan.by_verdict('skip'))} left alone", file=out)
        if deletes:
            for line in _backup_advice(plan, profile, host):
                print(line, file=out)
            print(f"  plan digest: {digest}", file=out)
            cmd = apply_command(root, profile, kinds, digest, types_given=types_given)
            print(f"  to delete exactly this plan: {cmd}", file=out)
        return 1 if attention else 0

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
    return 1 if attention else 0


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
