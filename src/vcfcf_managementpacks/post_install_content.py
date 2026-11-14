"""After a pak install: is every view, report, symptom and alert the pak ships there?

The pak installer reports success whatever its content import did. The
vCommunity Java pak 0.0.0.15 installed "successfully" on 9.0.2 and 9.1.1
with 14 views and a report template missing (an empty localization value
failed their directories) and, on 9.0.2, two alerts without their conditions
(a symptom defined twice): ``knowledge/context/investigations/2026-11-14-pak-content-silent-drops.md``.
Dashboards have their own check (``post_install.py``).

This module counts the pak's own ids (``vcfcf_core.packaging.pak_content``,
read from the pak offline) against the instance:

- views: ``viewServiceController.getGroupedViewDefinitionThumbnails`` (the
  /ui/ list, ``viewDefinitionKey``; the Suite API has no view list);
- reports: ``GET /api/reportdefinitions`` (paged);
- symptoms: ``GET /api/symptomdefinitions/{id}`` per standalone symptom
  (200 present, 404 absent);
- alerts: ``GET /api/alertdefinitions/{id}`` per alert, and each alert's
  sets must still name every symptom its pak definition names. An alert's
  inline conditions (``symptomDefType`` set) are never on the symptom
  endpoints; REST shows them only inside the alert, as
  ``alertConditions[].id = "Condition-<x>"`` for ``SymptomDefinition-<x>``
  (``2026-11-11-alert-symptom-export-completeness.md``), and a dangling
  reference as an empty set. So a lost condition shows as a shortfall of the
  alert, never as a missing symptom.

Timing: these four types are written by ``installContent`` inside the
install task, before the pak manager reports it done (the import errors of
0.0.0.15 were logged minutes before the install finished), so a shortfall at
the first read is expected to be final. A short re-read guards against a
read that lands before the write is visible: every :data:`CONTENT_POLL_S`
seconds up to :data:`CONTENT_WAIT_S`, only while something is missing. The
check runs after the dashboard materialization check, which has already
waited 180 s or more whenever a dashboard was still building.

The live half takes injected clients, so it is unit-testable with fakes.
"""
from __future__ import annotations

import sys
import time
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from vcfcf_core.packaging import pak_content as _pak_content

#: Re-read window when something is missing at the first read (see module doc).
CONTENT_WAIT_S = 120
#: Re-read interval inside that window.
CONTENT_POLL_S = 30
#: Exit code shared with the dashboard check (``post_install``).
CONTENT_FAILED_RC = 3

_PAGE = 1000


class ContentUnreadable(Exception):
    """A live read failed (transport, auth, an unexpected status)."""


@dataclass
class LiveContent:
    views: Set[str] = field(default_factory=set)
    reports: Set[str] = field(default_factory=set)
    symptoms: Set[str] = field(default_factory=set)
    #: alert id to the symptom ids its live sets name (conditions mapped back).
    alerts: Dict[str, Set[str]] = field(default_factory=dict)


def _norm(oid: str) -> str:
    return str(oid or "").strip().lower()


def _flatten_view_ids(node, out: Set[str]) -> None:
    """Every ``viewDefinitionKey`` in the grouped thumbnail answer (a list or
    a type/subject-keyed dict of lists, depending on the build)."""
    if isinstance(node, dict):
        key = node.get("viewDefinitionKey")
        if key:
            out.add(_norm(key))
        for v in node.values():
            if isinstance(v, (dict, list)):
                _flatten_view_ids(v, out)
    elif isinstance(node, list):
        for v in node:
            _flatten_view_ids(v, out)


def _walk_sets(node, out: Set[str]) -> None:
    if isinstance(node, dict):
        for sid in node.get("symptomDefinitionIds") or []:
            out.add(_norm(sid))
        for cond in node.get("alertConditions") or []:
            cid = str((cond or {}).get("id") or "")
            if cid.startswith("Condition-"):
                out.add(_norm("SymptomDefinition-" + cid[len("Condition-"):]))
        for child in node.get("symptom-sets") or []:
            _walk_sets(child, out)


def alert_live_refs(alert: dict) -> Set[str]:
    """The symptom ids a REST alert definition's states name, inline
    conditions mapped back to ``SymptomDefinition-<x>``."""
    out: Set[str] = set()
    for st in (alert or {}).get("states") or []:
        if isinstance(st, dict):
            _walk_sets(st.get("base-symptom-set"), out)
    return out


def _get(suite, path: str, **params):
    try:
        return suite._request("GET", path, params=params or None)
    except Exception as exc:  # noqa: BLE001  transport errors
        raise ContentUnreadable(f"GET {path}: {exc}") from exc


def read_live_content(suite, ui, inv: "_pak_content.PakContentInventory") -> LiveContent:
    """What the instance holds of the pak's views, reports, symptoms and alerts.

    ``suite`` needs ``_request`` (``VCFOpsClient``); ``ui`` needs
    ``list_views`` (``VCFOpsUIClient``, logged in). Raises
    :class:`ContentUnreadable` on any failed read.
    """
    live = LiveContent()
    if inv.views:
        try:
            listing = ui.list_views()
        except Exception as exc:  # noqa: BLE001
            raise ContentUnreadable(f"view list: {exc}") from exc
        _flatten_view_ids(listing, live.views)
    if inv.reports:
        page = 0
        while True:
            r = _get(suite, "/api/reportdefinitions", page=page, pageSize=_PAGE)
            if r.status_code != 200:
                raise ContentUnreadable(f"GET /api/reportdefinitions: HTTP {r.status_code}")
            body = r.json() or {}
            items = body.get("reportDefinitions") or []
            live.reports.update(_norm(x.get("id")) for x in items if isinstance(x, dict))
            total = (body.get("pageInfo") or {}).get("totalCount", len(items))
            if not items or (page + 1) * _PAGE >= total:
                break
            page += 1
    for sid in inv.symptoms:
        r = _get(suite, f"/api/symptomdefinitions/{sid}")
        if r.status_code == 200:
            live.symptoms.add(_norm(sid))
        elif r.status_code != 404:
            raise ContentUnreadable(f"GET /api/symptomdefinitions/{sid}: HTTP {r.status_code}")
    for aid in inv.alerts:
        r = _get(suite, f"/api/alertdefinitions/{aid}")
        if r.status_code == 200:
            live.alerts[_norm(aid)] = alert_live_refs(r.json() or {})
        elif r.status_code != 404:
            raise ContentUnreadable(f"GET /api/alertdefinitions/{aid}: HTTP {r.status_code}")
    return live


def content_shortfall(inv: "_pak_content.PakContentInventory", live: LiveContent) -> List[str]:
    """One line per missing id (by type) and per alert that lost a condition."""
    lines: List[str] = []
    for label, wanted, have in (
        ("view", inv.views, live.views),
        ("report template", inv.reports, live.reports),
        ("symptom definition", inv.symptoms, live.symptoms),
    ):
        for oid, name in sorted(wanted.items(), key=lambda kv: (kv[1], kv[0])):
            if _norm(oid) not in have:
                lines.append(f"CONTENT MISSING: {label} {oid} '{name}'")
    names = {**inv.symptoms, **inv.conditions}
    for aid, alert in sorted(inv.alerts.items(), key=lambda kv: (kv[1].name, kv[0])):
        refs = live.alerts.get(_norm(aid))
        if refs is None:
            lines.append(f"CONTENT MISSING: alert definition {aid} '{alert.name}'")
            continue
        lost = [s for s in alert.symptom_refs if _norm(s) not in refs]
        if lost:
            what = ", ".join(f"{s} '{names[s]}'" if s in names else s for s in lost)
            lines.append(
                f"CONTENT INCOMPLETE: alert definition {aid} '{alert.name}' lost "
                f"{len(lost)} of {len(alert.symptom_refs)} symptom/condition "
                f"reference(s): {what}"
            )
    return lines


def check_installed_content(
    inv: "_pak_content.PakContentInventory",
    *,
    read: Callable[[], LiveContent],
    out: Callable[[str], None],
    err: Callable[[str], None],
    wait_s: int = CONTENT_WAIT_S,
    poll_s: int = CONTENT_POLL_S,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Count the pak's content on the instance; returns 0 or :data:`CONTENT_FAILED_RC`.

    ``read()`` returns a :class:`LiveContent` or raises
    :class:`ContentUnreadable`. A first read that fails is a WARNING and 0
    (unknown is not a shortfall); a failed re-read keeps the last good one.
    """
    try:
        lines = content_shortfall(inv, read())
    except ContentUnreadable as exc:
        err(f"WARNING: CONTENT UNCHECKED: could not read the pak's content on the "
            f"instance: {exc}")
        return 0
    elapsed = 0
    if lines and wait_s > 0:
        out(f"CONTENT WAIT: {len(lines)} problem(s); re-checking every "
            f"{poll_s} s for up to {wait_s} s")
    while lines and elapsed < wait_s:
        step = min(poll_s, wait_s - elapsed)
        sleep(step)
        elapsed += step
        try:
            lines = content_shortfall(inv, read())
        except ContentUnreadable:
            continue
    c = inv.counts()
    summary = (f"{c['views']} view(s), {c['reports']} report template(s), "
               f"{c['symptoms']} symptom definition(s), {c['alerts']} alert "
               f"definition(s) with {c['conditions']} inline condition(s)")
    if not lines:
        if any(c.values()):
            out(f"CONTENT OK: {summary} all present")
        return 0
    for line in lines:
        err(line)
    err(f"ERROR: CONTENT SHORTFALL: {len(lines)} problem(s) in the pak's {summary}"
        f" (read {elapsed} s after the first check). The install reported success; "
        f"the pak installer drops content silently. The cause is in the appliance "
        f"logs (analytics and view-bridge logs at the install time), e.g. "
        f"cvc-minLength-valid or duplicate key.")
    return CONTENT_FAILED_RC


def report_pak_content(
    pak_path,
    *,
    host: str,
    user: str,
    password: str,
    verify_ssl: bool,
    ui_factory: Optional[Callable[..., object]] = None,
    suite_factory: Optional[Callable[..., object]] = None,
    sleep: Callable[[float], None] = time.sleep,
    wait_s: int = CONTENT_WAIT_S,
) -> int:
    """Run the post-install content count for one pak and print it."""
    try:
        inv = _pak_content.read_pak_content_inventory(pak_path)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"WARNING: CONTENT UNCHECKED: could not read the pak's content: {exc}",
              file=sys.stderr)
        return 0
    if not (inv.views or inv.reports or inv.symptoms or inv.alerts):
        return 0
    if ui_factory is None:
        from vcfcf_dashboards.ui_client import VCFOpsUIClient

        def ui_factory(h, u, pw, v):
            return VCFOpsUIClient(host=h, username=u, password=pw,
                                  auth_source="localItem", verify_ssl=v)
    if suite_factory is None:
        from vcfcf_common.client import VCFOpsClient

        def suite_factory(h, u, pw, v):
            # Local: the credentials the installer's local-only /ui/ login proved.
            return VCFOpsClient(host=h, username=u, password=pw,
                                auth_source="Local", verify_ssl=v)

    def _err(msg: str) -> None:
        print(msg, file=sys.stderr)

    try:
        suite = suite_factory(host, user, password, verify_ssl)
        ui = ui_factory(host, user, password, verify_ssl) if inv.views else None
        if ui is not None:
            ui.login()
    except Exception as exc:  # noqa: BLE001  advisory when unreadable
        _err(f"WARNING: CONTENT UNCHECKED: could not open a session: {exc}")
        return 0
    try:
        return check_installed_content(
            inv, read=lambda: read_live_content(suite, ui, inv),
            out=print, err=_err, wait_s=wait_s, sleep=sleep,
        )
    finally:
        if ui is not None:
            try:
                ui.logout()
            except Exception:  # noqa: BLE001
                pass
