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

The pak read is offline. The live half takes injected clients, so the flow
is unit-testable with fakes.
"""
from __future__ import annotations

import json
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

DASHBOARDS_DIR = "content/dashboards/"

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

    Offline. A directory whose JSON is unreadable, not an object, or holds no
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
) -> tuple:
    """Classify each pak dashboard; returns ``(statuses, unknown_ids)``.

    ``ui`` needs ``list_dashboards()``. ``adapter_kinds()`` returns the
    target's adapter-kind keys or None when unreadable; it is called at most
    once, and only when a dashboard is still building. When any dashboard is
    still building with every pending adapter kind installed, ``on_wait``
    is called, then one re-read follows after ``wait_s`` (the same single
    re-check as ``vcfcf_dashboards sync``). Raises :class:`ListUnreadable`
    when the first list read fails.
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
    sleep(wait_s)
    try:
        statuses, unknown = _read()
    except ListUnreadable:
        # The re-check is best effort: report from the first read.
        return finalize_statuses(statuses, 0), unknown
    return finalize_statuses(statuses, wait_s), unknown


def report_pak_dashboards(
    pak_path,
    *,
    host: str,
    user: str,
    password: str,
    verify_ssl: bool,
    wait_s: Optional[int] = None,
    ui_factory: Optional[Callable[..., object]] = None,
    suite_factory: Optional[Callable[..., object]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run the post-install materialization check for one pak and print it.

    Returns 0, or :data:`POST_INSTALL_FAILED_RC` when a dashboard is
    STALLED (waiting on an adapter kind the target lacks). Credentials are
    never printed. ``ui_factory(host, user, password, verify_ssl)`` and
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

    def _on_wait(count: int, seconds: int) -> None:
        print(f"MATERIALIZATION WAIT: {count} dashboard(s) still building; "
              f"re-checking once in {seconds} s", flush=True)

    wait = materialization_recheck_wait(wait_s)
    ui = ui_factory(host, user, password, verify_ssl)
    try:
        ui.login()
        statuses, unknown = check_pak_dashboards(
            ui, dashboards, wait_s=wait, adapter_kinds=_adapter_kinds,
            on_wait=_on_wait, sleep=sleep,
        )
    except Exception as exc:  # noqa: BLE001  advisory check: a transport error is a WARNING
        print(f"WARNING: MATERIALIZATION UNCHECKED: could not check whether the pak's "
              f"dashboards finished building: {exc}", file=sys.stderr)
        return 0
    finally:
        try:
            ui.logout()
        except Exception:  # noqa: BLE001
            pass

    names = {d.id: d.name for d in dashboards}
    for did in unknown:
        print(f"WARNING: MATERIALIZATION UNCHECKED: dashboard '{names.get(did, did)}': the "
              f"dashboard list carries no isLoading flag on this build, so whether it "
              f"finished building is unknown.", file=sys.stderr)
    rc = report_materialization_statuses(statuses)
    return POST_INSTALL_FAILED_RC if rc else 0
