"""After a pak install: did the pak's dashboards finish building? (issue #244)

The pak installer imports every ``content/dashboards/<dir>/`` of the pak.
Like a content-zip import, that import lands in two phases: the record is
written at once and each widget's settings are resolved later by a
background pass (``knowledge/context/api-surface/dashboard_import_two_phase_materialization.md``).
A FINISHED install therefore says nothing about whether the dashboards work.

This module reports the same states as ``vcfcf_dashboards sync`` (issue
#167), through the same core classifier
(``vcfcf_core.dashboards.materialization``) and the same report lines. The
data source differs, because a ``CUSTOM`` ``DASHBOARDS`` content export does
not carry pak-installed dashboards at all (read on devel 9.0.2 on 2026-10-24,
about 12:15 AM: the export listed 13 dashboards for ``admin``, none of the
five compliance pak dashboards, which ``getDashboardList`` showed owned by
``admin``). So:

- the pak's own ``dashboard.json`` gives each dashboard's id (the importer
  keeps it) and its portability table ``entries``, which is what the
  server parks in ``entryKeys`` until phase 2 is done;
- ``getDashboardList`` gives ``isLoading`` per dashboard, the UI surface
  of ``importComplete: false``.

Each pak dashboard becomes the record the classifier takes:
``{"id", "importComplete": not isLoading, "entryKeys": entries or None}``.
A dashboard the list does not carry is ABSENT (the importer drops a whole
dashboard silently on an unknown widget type, lesson
``unknown-widget-type-aborts-pak-dashboard-import.md``).

Summary tabs (issue #200). A pak's ``content/dashboards/dashboards.properties``
makes the server's installer clone each bound dashboard into a SUMMARY
template seconds after importing it. On 9.0.2 that clone is taken while the
source's widgets are still unresolved, and nothing resolves a template
afterwards, so the Summary tab shows stock widgets for good
(``knowledge/context/api-surface/summary_dashboard_pak_binding.md``). A pak
cannot reorder the server's steps, so the factory's install does the
binding step again, after the source has materialized:

1. the materialization wait polls (every 30 s, up to 660 s by default: one
   10-minute importer tick plus a margin) until every dashboard has
   settled, instead of the single re-check;
2. per bound resource kind, ``getSummaryTabId`` gives the installer's
   clone and ``getDashboardConfig?isTemplate=true`` says whether it
   finished. A finished clone (the 9.1.1 case) is left alone;
3. an unfinished clone of a finished source is bound again by the pak
   dashboard's id (``associateResourceKindDashboards``, the UI's own bind),
   and the new clone is read back.

Nothing is ever bound that the installer did not bind first, and a Summary
tab is rebound only when its name reads as a copy of the pak's dashboard
(``<name>`` or ``<name> <n>``); a tab whose name cannot be read is left
alone (``SUMMARY UNCHECKED``).

The pak read is offline. The live half takes injected clients, so the flow
is unit-testable with fakes.
"""
from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

DASHBOARDS_DIR = "content/dashboards/"
PROPERTIES_PATH = "content/dashboards/dashboards.properties"

#: Default wait when the pak binds a Summary dashboard: the per-user
#: importer resolves a dashboard on a 10-minute tick (bytecode read on
#: 9.0.2, ``2026-10-13-compliance-summary-clone-config-loss.md``), plus a
#: minute of margin. Still under the 900 s cap.
BOUND_SOURCE_WAIT_S = 660
#: Poll interval of that wait.
BOUND_SOURCE_POLL_S = 30

#: Exit code of ``install`` when the pak installed but a post-install
#: dashboard check failed. Distinct from 1 (the install itself failed) so a
#: wrapper that retries on 1 does not reinstall a pak that is installed.
POST_INSTALL_FAILED_RC = 3


@dataclass
class PakDashboard:
    """One dashboard shipped in a pak's ``content/dashboards/<directory>/``."""
    id: str
    #: Display name without the ``namePath`` folder prefix (what
    #: ``getDashboardList`` shows).
    name: str
    directory: str
    #: The pak JSON's top-level ``entries`` table (or None when absent).
    entries: Optional[dict] = None


def _strip_name_path(name: str, name_path: str) -> str:
    if name_path and name.startswith(name_path + "/"):
        return name[len(name_path) + 1:]
    return name


def read_pak_dashboards(pak_path, *, warn: Callable[[str], None]) -> List[PakDashboard]:
    """Every dashboard a pak ships, read from ``content/dashboards/*/dashboard.json``.

    Offline. ``GenericTemplates*`` directories are skipped (the installer
    imports them as templates, which the dashboard list never shows). A
    directory whose JSON is unreadable, not an object, or holds no
    dashboard with an id is skipped with a ``warn`` line; the install itself
    is not affected.
    """
    out: List[PakDashboard] = []
    with zipfile.ZipFile(Path(pak_path), "r") as zf:
        for member in sorted(zf.namelist()):
            if not member.startswith(DASHBOARDS_DIR) or not member.endswith("/dashboard.json"):
                continue
            directory = member[len(DASHBOARDS_DIR):-len("/dashboard.json")]
            if not directory or "/" in directory:
                continue
            if directory.startswith("GenericTemplates"):
                # Imported as templates where the installer honours the
                # prefix, so never in getDashboardList: checking them would
                # report a false ABSENT. Factory paks ship none.
                continue
            try:
                doc = json.loads(zf.read(member).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                warn(f"{member} is not valid JSON ({exc}); not checked")
                continue
            if not isinstance(doc, dict):
                warn(f"{member} is not a JSON object; not checked")
                continue
            entries = doc.get("entries") if isinstance(doc.get("entries"), dict) else None
            for d in doc.get("dashboards") or []:
                if not isinstance(d, dict) or not str(d.get("id") or "").strip():
                    continue
                out.append(PakDashboard(
                    id=str(d["id"]).strip().lower(),
                    name=_strip_name_path(str(d.get("name") or ""), str(d.get("namePath") or "")),
                    directory=directory,
                    entries=entries,
                ))
    return out


@dataclass
class PakBinding:
    """One ``dashboards.properties`` entry the installer acts on."""
    directory: str
    dashboard: PakDashboard
    #: (adapter kind, resource kind), the raw tokens the installer uses.
    kinds: List[tuple] = field(default_factory=list)


def _unescape(text: str) -> str:
    """``java.util.Properties`` backslash escapes (``\\t`` etc., else the char)."""
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append({"t": "\t", "n": "\n", "r": "\r", "f": "\f"}.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_properties(text: str) -> Dict[str, str]:
    """Parse a ``.properties`` file as ``Properties.load`` does: ``#``/``!``
    comments, ``key=value`` / ``key: value`` / ``key value`` (first unescaped
    separator), leading whitespace of the value dropped, trailing-backslash
    continuation."""
    result: Dict[str, str] = {}
    logical: List[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.lstrip()
        if not buf and (not line or line[0] in "#!"):
            continue
        trailing = len(line) - len(line.rstrip("\\"))
        if trailing % 2 == 1:
            buf += line[:-1]
            continue
        logical.append(buf + line)
        buf = ""
    if buf:
        logical.append(buf)
    for line in logical:
        key_end, i = len(line), 0
        while i < len(line):
            c = line[i]
            if c == "\\":
                i += 2
                continue
            if c in "=:" or c.isspace():
                key_end = i
                break
            i += 1
        key = line[:key_end]
        rest = line[key_end:].lstrip()
        if rest[:1] in ("=", ":"):
            rest = rest[1:].lstrip()
        result[_unescape(key)] = _unescape(rest)
    return result


def java_split(text: str, sep: str) -> List[str]:
    """``String.split`` for a one-character literal: trailing empty strings
    are dropped, leading ones kept, nothing is trimmed."""
    parts = text.split(sep)
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def read_pak_bindings(
    pak_path, dashboards: List[PakDashboard], *, warn: Callable[[str], None]
) -> List[PakBinding]:
    """The Summary-tab bindings the installer makes for this pak, as it makes
    them: ``GenericTemplates*`` directories are never bound, a value part
    that does not ``split(":")`` into exactly two tokens is skipped, tokens
    are not trimmed. A bound directory that does not hold exactly one
    dashboard is skipped with a ``warn`` line (the installer then binds
    whichever its HashMap yields first; guessing would bind a different one).
    """
    with zipfile.ZipFile(Path(pak_path), "r") as zf:
        if PROPERTIES_PATH not in zf.namelist():
            return []
        props = parse_properties(zf.read(PROPERTIES_PATH).decode("utf-8", errors="replace"))
    by_dir: Dict[str, List[PakDashboard]] = {}
    for d in dashboards:
        by_dir.setdefault(d.directory, []).append(d)
    out: List[PakBinding] = []
    for directory, value in props.items():
        if directory.startswith("GenericTemplates"):
            continue
        kinds = []
        for part in java_split(value, ","):
            tokens = java_split(part, ":")
            if len(tokens) == 2:
                kinds.append((tokens[0], tokens[1]))
        if not kinds:
            continue
        found = by_dir.get(directory) or []
        if len(found) != 1:
            warn(f"{PROPERTIES_PATH} binds {directory!r}, which holds "
                 f"{len(found)} dashboard(s) in the pak; its Summary tab is not checked")
            continue
        out.append(PakBinding(directory=directory, dashboard=found[0], kinds=kinds))
    return out


class ListUnreadable(Exception):
    """``getDashboardList`` could not be read or carried no ``isLoading``."""


def _records(listing: list, dashboards: List[PakDashboard]) -> tuple:
    """(records for the classifier, ids whose list entry has no ``isLoading``)."""
    by_id = {}
    for entry in listing or []:
        if isinstance(entry, dict) and entry.get("id"):
            by_id[str(entry["id"]).strip().lower()] = entry
    records, unknown = [], []
    for d in dashboards:
        entry = by_id.get(d.id)
        if entry is None:
            continue  # classifier reports ABSENT
        if "isLoading" not in entry:
            unknown.append(d.id)
            continue
        loading = bool(entry.get("isLoading"))
        records.append({
            "id": d.id,
            "importComplete": not loading,
            # The pending work list is the pak's own portability table; an
            # empty dict still marks the dashboard incomplete.
            "entryKeys": (d.entries or {}) if loading else None,
        })
    return records, unknown


def check_pak_dashboards(
    ui,
    dashboards: List[PakDashboard],
    *,
    wait_s: int,
    adapter_kinds: Callable[[], Optional[set]],
    on_wait: Optional[Callable[[int, int], None]] = None,
    sleep: Callable[[float], None] = time.sleep,
    poll_s: Optional[int] = None,
) -> tuple:
    """Classify each pak dashboard; returns ``(statuses, unknown_ids)``.

    ``ui`` needs ``list_dashboards()``. ``adapter_kinds()`` returns the
    target's adapter-kind keys or None when unreadable; it is called at most
    once, and only when a dashboard is still building. When any dashboard is
    still building with every pending adapter kind installed, ``on_wait``
    is called, then one re-read follows after ``wait_s`` (the same single
    re-check as ``vcfcf_dashboards sync``). With ``poll_s`` (issue #200,
    a pak that binds a Summary dashboard) it re-reads every ``poll_s``
    seconds instead, until nothing is still building or ``wait_s`` is spent;
    a failed poll keeps the last good read and polls on. Raises
    :class:`ListUnreadable` when the first list read fails.
    """
    from vcfcf_core.dashboards.materialization import (
        SETTLING,
        classify_dashboards,
        finalize_statuses,
    )

    wanted = {d.id: d.name for d in dashboards}
    kinds_cache: dict = {}

    def _read() -> tuple:
        try:
            listing = ui.list_dashboards()
        except Exception as exc:  # noqa: BLE001  any transport or parse error
            raise ListUnreadable(str(exc)) from exc
        records, unknown = _records(listing, dashboards)
        if "kinds" not in kinds_cache and any(r["entryKeys"] is not None for r in records):
            kinds_cache["kinds"] = adapter_kinds()
        known = {k: v for k, v in wanted.items() if k not in unknown}
        return classify_dashboards(records, known, kinds_cache.get("kinds")), unknown

    statuses, unknown = _read()
    settling = [s for s in statuses if s.state == SETTLING]
    if not settling or wait_s <= 0:
        return finalize_statuses(statuses, 0), unknown
    if on_wait is not None:
        on_wait(len(settling), wait_s)
    if not poll_s or poll_s >= wait_s:
        sleep(wait_s)
        try:
            statuses, unknown = _read()
        except ListUnreadable:
            # The re-check is best effort: report from the first read.
            return finalize_statuses(statuses, 0), unknown
        return finalize_statuses(statuses, wait_s), unknown
    elapsed = read_at = 0
    while elapsed < wait_s:
        step = min(poll_s, wait_s - elapsed)
        sleep(step)
        elapsed += step
        try:
            statuses, unknown = _read()
        except ListUnreadable:
            continue  # transient: keep the last good read, poll on
        read_at = elapsed
        if not any(s.state == SETTLING for s in statuses):
            break
    return finalize_statuses(statuses, read_at), unknown


#: Clone states read from ``getDashboardConfig?isTemplate=true``.
CLONE_COMPLETE = "complete"
CLONE_INCOMPLETE = "incomplete"
CLONE_UNKNOWN = "unknown"


def template_state(config, tab_id: str) -> tuple:
    """``(state, name)`` of one template tab from a ``getDashboardConfig``
    answer. Incomplete when the tab or any widget has ``isLoading: true``;
    complete only when the tab and every widget carry ``isLoading: false``;
    otherwise (no such tab, no flag) unknown."""
    tabs = []
    if isinstance(config, dict) and isinstance(config.get("dashboardConfig"), dict):
        tabs = config["dashboardConfig"].get("tabConfigs") or []
    tab = next((t for t in tabs if isinstance(t, dict)
                and str(t.get("id") or "").lower() == str(tab_id).lower()), None)
    if tab is None:
        return CLONE_UNKNOWN, ""
    name = str(tab.get("name") or "")
    flags = [tab.get("isLoading")] + [
        w.get("isLoading") for w in (tab.get("widgets") or []) if isinstance(w, dict)
    ]
    if any(f is True for f in flags):
        return CLONE_INCOMPLETE, name
    if all(f is False for f in flags):
        return CLONE_COMPLETE, name
    return CLONE_UNKNOWN, name


def _is_copy_of(clone_name: str, source_name: str) -> bool:
    """A Summary template is named after its source, de-duplicated with a
    numeric suffix (``<name> 6``)."""
    if clone_name == source_name:
        return True
    tail = clone_name[len(source_name):] if clone_name.startswith(source_name + " ") else ""
    return tail.strip().isdigit()


def _resource_kind_id(adapter_kind: str, resource_kind: str) -> str:
    from vcfcf_core.dashboards.summary_bind import resource_kind_id

    return resource_kind_id(adapter_kind, resource_kind)


def repair_summary_bindings(
    ui,
    bindings: List[PakBinding],
    statuses: list,
    *,
    out: Callable[[str], None],
    err: Callable[[str], None],
) -> int:
    """Rebind each installer-made Summary clone that did not finish (#200).

    Returns :data:`POST_INSTALL_FAILED_RC` when a bound kind's Summary tab
    is known to show an unfinished copy afterwards, else 0. ``ui`` needs
    ``get_summary_tab_id``, ``get_dashboard_config`` and
    ``associate_resource_kind_dashboards``. Lines start ``SUMMARY <STATE>:``.
    """
    from vcfcf_core.dashboards.materialization import ABSENT, COMPLETE

    state_by_id = {s.id: s.state for s in statuses}
    rc = 0
    for b in bindings:
        d = b.dashboard
        source_state = state_by_id.get(d.id)
        for ak, rk in b.kinds:
            label = f"{ak}:{rk}"
            needs_fix = False
            try:
                if source_state == ABSENT:
                    err(f"WARNING: SUMMARY NOT CHECKED: {label}: dashboard '{d.name}' is "
                        f"not on the instance (see MATERIALIZATION ABSENT), so the "
                        f"installer could not bind it.")
                    continue
                rkid = _resource_kind_id(ak, rk)
                answer = ui.get_summary_tab_id(rkid)
                old = str(answer.get("tabId") or "") if isinstance(answer, dict) else ""
                if not old or (isinstance(answer, dict) and answer.get("isDashboard") is False):
                    err(f"WARNING: SUMMARY NOT BOUND: {label}: the installer did not bind "
                        f"'{d.name}' to this Summary tab (getSummaryTabId: {answer!r}); "
                        f"left as it is.")
                    continue
                state, clone_name = template_state(
                    ui.get_dashboard_config(old, is_template=True), old)
                if not clone_name:
                    # Cannot tell whose tab this is: the config answer did not
                    # carry the bound tab, or carried it without a name. Never
                    # write over a binding that cannot be identified.
                    err(f"WARNING: SUMMARY UNCHECKED: {label}: could not read the name of "
                        f"the Summary tab {old}, so whether it is a copy of '{d.name}' is "
                        f"unknown; left as it is.")
                    continue
                if not _is_copy_of(clone_name, d.name):
                    err(f"WARNING: SUMMARY NOT REBOUND: {label}: the Summary tab shows "
                        f"'{clone_name}' ({old}), not a copy of '{d.name}'; left as it is.")
                    continue
                if state == CLONE_COMPLETE:
                    out(f"SUMMARY OK: {label} shows a finished copy of '{d.name}' ({old})")
                    continue
                needs_fix = state == CLONE_INCOMPLETE
                if source_state != COMPLETE:
                    why = (
                        "whether it finished building could not be checked (the "
                        "dashboard list carried no isLoading flag for it)"
                        if source_state is None else "had not finished building"
                    )
                    err(f"WARNING: SUMMARY NOT REBOUND: {label}: the Summary tab copy {old} "
                        f"is {state} and '{d.name}' {why}, so it was not bound again. "
                        f"Once the dashboard has finished building (open it once in the "
                        f"UI), assign it again under Manage Summary Dashboards.")
                    if needs_fix:
                        rc = POST_INSTALL_FAILED_RC
                    continue
                ui.associate_resource_kind_dashboards(
                    {f"resourceKind_{rkid}": f"{d.name}_::_{d.id}"}, {})
                answer = ui.get_summary_tab_id(rkid)
                new = str(answer.get("tabId") or "") if isinstance(answer, dict) else ""
                if not new or new == old:
                    err(f"WARNING: SUMMARY NOT REBOUND: {label}: bound '{d.name}' ({d.id}) "
                        f"again, but the Summary tab still points at {old or 'nothing'}.")
                    rc = POST_INSTALL_FAILED_RC
                    continue
                new_state, _ = template_state(
                    ui.get_dashboard_config(new, is_template=True), new)
                if new_state == CLONE_INCOMPLETE:
                    err(f"WARNING: SUMMARY NOT REBOUND: {label}: the new copy {new} of "
                        f"'{d.name}' is unfinished too.")
                    rc = POST_INSTALL_FAILED_RC
                    continue
                out(f"SUMMARY REBOUND: {label} now shows copy {new} of '{d.name}' ({d.id}); "
                    f"the installer's copy {old} was {state}. The previous copy may remain as "
                    f"an unused template (the server deletes it on 9.2; not confirmed on "
                    f"9.0.2). New copy state: {new_state}.")
            except Exception as exc:  # noqa: BLE001  one kind's failure must not stop the rest
                err(f"WARNING: SUMMARY UNCHECKED: {label}: could not check or repair the "
                    f"Summary tab for '{d.name}': {exc}")
                if needs_fix:
                    rc = POST_INSTALL_FAILED_RC
    return rc


def report_pak_dashboards(
    pak_path,
    *,
    host: str,
    user: str,
    password: str,
    verify_ssl: bool,
    wait_s: Optional[int] = None,
    summary_rebind: bool = True,
    ui_factory: Optional[Callable[..., object]] = None,
    suite_factory: Optional[Callable[..., object]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run the post-install materialization check for one pak and print it.

    Returns 0, or :data:`POST_INSTALL_FAILED_RC` when a dashboard is
    STALLED (waiting on an adapter kind the target lacks) or a bound
    Summary tab is left showing an unfinished copy (#200). When the pak
    binds Summary dashboards the wait polls (default
    :data:`BOUND_SOURCE_WAIT_S`) and, with ``summary_rebind``, the Summary
    clones are checked and repaired. Credentials are never printed. ``ui_factory(host, user, password, verify_ssl)`` and
    ``suite_factory(...)`` are injectable for tests.
    """
    from vcfcf_dashboards.client import list_adapter_kind_keys, materialization_recheck_wait
    from vcfcf_dashboards.cli import report_materialization_statuses

    def _warn(msg: str) -> None:
        print(f"WARN: {msg}", file=sys.stderr)

    try:
        dashboards = read_pak_dashboards(pak_path, warn=_warn)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"WARNING: MATERIALIZATION UNCHECKED: could not read the pak's dashboards: {exc}",
              file=sys.stderr)
        return 0
    if not dashboards:
        return 0
    try:
        bindings = read_pak_bindings(pak_path, dashboards, warn=_warn)
    except (OSError, zipfile.BadZipFile) as exc:
        _warn(f"could not read {PROPERTIES_PATH}: {exc}; Summary tabs not checked")
        bindings = []

    if ui_factory is None:
        from vcfcf_dashboards.ui_client import VCFOpsUIClient

        def ui_factory(h, u, pw, v):
            # The installer's own /ui/ session logs in as a local account.
            return VCFOpsUIClient(host=h, username=u, password=pw,
                                  auth_source="localItem", verify_ssl=v)
    if suite_factory is None:
        from vcfcf_common.client import VCFOpsClient

        def suite_factory(h, u, pw, v):
            return VCFOpsClient(host=h, username=u, password=pw,
                                auth_source="Local", verify_ssl=v)

    def _adapter_kinds() -> Optional[set]:
        try:
            return list_adapter_kind_keys(suite_factory(host, user, password, verify_ssl))
        except Exception:  # noqa: BLE001  unknown, not a guess: reported as such
            return None

    from vcfcf_dashboards.client import MATERIALIZATION_RECHECK_ENV

    poll = None
    if bindings and summary_rebind:
        # The long polled wait exists only for the rebind; without it the
        # check keeps the 180 s single re-check.
        poll = BOUND_SOURCE_POLL_S
        if wait_s is None and not os.environ.get(MATERIALIZATION_RECHECK_ENV, "").strip():
            # The binding step needs the source finished; one importer tick.
            wait_s = BOUND_SOURCE_WAIT_S
    wait = materialization_recheck_wait(wait_s)

    def _on_wait(count: int, seconds: int) -> None:
        how = (f"re-checking every {poll} s for up to {seconds} s"
               if poll and poll < seconds else f"re-checking once in {seconds} s")
        print(f"MATERIALIZATION WAIT: {count} dashboard(s) still building; {how}", flush=True)

    def _err(msg: str) -> None:
        print(msg, file=sys.stderr)

    ui = ui_factory(host, user, password, verify_ssl)
    try:
        try:
            ui.login()
            statuses, unknown = check_pak_dashboards(
                ui, dashboards, wait_s=wait, adapter_kinds=_adapter_kinds,
                on_wait=_on_wait, sleep=sleep, poll_s=poll,
            )
        except Exception as exc:  # noqa: BLE001  advisory check: a transport error is a WARNING
            print(f"WARNING: MATERIALIZATION UNCHECKED: could not check whether the pak's "
                  f"dashboards finished building: {exc}", file=sys.stderr)
            if bindings:
                print("WARNING: SUMMARY UNCHECKED: the pak's Summary tabs were not checked.",
                      file=sys.stderr)
            return 0

        names = {d.id: d.name for d in dashboards}
        for did in unknown:
            print(f"WARNING: MATERIALIZATION UNCHECKED: dashboard '{names.get(did, did)}': the "
                  f"dashboard list carries no isLoading flag on this build, so whether it "
                  f"finished building is unknown.", file=sys.stderr)
        rc = POST_INSTALL_FAILED_RC if report_materialization_statuses(statuses) else 0
        if bindings and summary_rebind:
            rc = repair_summary_bindings(ui, bindings, statuses, out=print, err=_err) or rc
        elif bindings:
            print("SUMMARY SKIPPED: --skip-summary-rebind; the installer's Summary tab "
                  "copies were not checked")
        return rc
    finally:
        try:
            ui.logout()
        except Exception:  # noqa: BLE001
            pass
