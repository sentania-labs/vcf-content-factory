"""Content Management import client for dashboards / view definitions.

Reuses the auth/session handling from vcfcf_supermetrics.client so we
have a single place that knows how to talk to the Suite API.
"""
from __future__ import annotations

import io
import time
import zipfile

from vcfcf_common.client import VCFOpsClient, VCFOpsError


# Content types this package imports, as they appear in the import
# result's ``operationSummaries[].contentType``.
DASHBOARD_CONTENT_TYPES = ("DASHBOARDS", "VIEW_DEFINITIONS")


def all_skipped_content_types(result: dict, content_types=None) -> dict:
    """Content types the importer imported NOTHING for while skipping some.

    Returns ``{contentType: (imported, skipped)}`` for every summary
    where ``imported == 0 and skipped > 0``, i.e. the import ran to
    FINISHED but changed nothing. Callers must not report such a run as
    a plain success: the operator's edits did not land on the instance.

    Scope note: the automatic re-import that recovers this signal is
    bisected for SUPER_METRICS only (see the SM ghost-state section in
    knowledge/context/wire-formats/wire_formats.md). Nothing here claims
    the same cause or the same remedy applies to other content types;
    this helper only reports the counts.
    """
    wanted = tuple(content_types) if content_types else None
    flagged: dict = {}
    for s in (result or {}).get("operationSummaries") or []:
        ct = s.get("contentType") or "?"
        if wanted is not None and ct not in wanted:
            continue
        try:
            imported = int(s.get("imported") or 0)
            skipped = int(s.get("skipped") or 0)
        except (TypeError, ValueError):
            continue
        if imported == 0 and skipped > 0:
            flagged[ct] = (imported, skipped)
    return flagged


def import_shortfalls(result: dict, content_types=None) -> dict:
    """Content types whose counters do not add up to their ``total``.

    Returns ``{contentType: (total, imported, skipped, failed)}`` for every
    summary where ``imported + skipped + failed < total``: objects the
    importer neither imported, skipped nor failed. Measured on 8.18.7 and
    9.0.2 (2026-11-13): a dashboard with a widget type the build does not
    know aborts the owner's whole dashboards batch, and the task still
    reports FINISHED, ``errorCode: NONE``, ``imported=0 skipped=0
    failed=0`` and no message. This is the only signature in the envelope.

    The one definition of the check: every factory reader of a content
    import result calls it (the installer templates carry a pinned copy).
    A summary with no usable ``total`` is not flagged.
    """
    wanted = tuple(content_types) if content_types else None
    short: dict = {}
    for s in (result or {}).get("operationSummaries") or []:
        if not isinstance(s, dict):
            continue
        ct = s.get("contentType") or "?"
        if wanted is not None and ct not in wanted:
            continue
        if s.get("total") is None:
            continue
        try:
            total = int(s.get("total"))
            imported = int(s.get("imported") or 0)
            skipped = int(s.get("skipped") or 0)
            failed = int(s.get("failed") or 0)
        except (TypeError, ValueError):
            continue
        if imported + skipped + failed < total:
            short[ct] = (total, imported, skipped, failed)
    return short


def import_shortfall_message(content_type: str, counts) -> str:
    """The error for one :func:`import_shortfalls` entry. The installer
    templates carry the same text verbatim (pinned by a test)."""
    total, imported, skipped, failed = counts
    missing = total - imported - skipped - failed
    head = (
        f"{content_type}: the import accounted for {total - missing} of "
        f"{total} (imported={imported} skipped={skipped} failed={failed}); "
        f"{missing} were neither imported, skipped nor failed, and the task "
        f"still reported FINISHED."
    )
    if content_type == "DASHBOARDS":
        return head + (
            " The likely cause is a widget type this instance's version "
            "cannot import (for example Section before VCF Operations "
            "9.1.1): on 8.18.7 and 9.0.2 one such dashboard makes the "
            "importer discard every dashboard in the same import, and "
            "view-bridge.log shows 'restoreData failed to import "
            "Dashboards'. Check which dashboards exist on the instance."
        )
    return head + (
        " The cause is not known for this content type. Check on the "
        "instance which objects exist, and report it with the import "
        "envelope."
    )


def import_shortfall_errors(result: dict, content_types=None) -> list:
    """One :func:`import_shortfall_message` per short content type, sorted."""
    return [
        import_shortfall_message(ct, counts)
        for ct, counts in sorted(import_shortfalls(result, content_types).items())
    ]


def get_ops_version(client: VCFOpsClient):
    """The instance's product version from ``GET /api/versions/current``
    ``releaseName`` (an int tuple), or None when it cannot be read."""
    from vcfcf_core.dashboards.widget_versions import parse_release_name
    try:
        r = client._request("GET", "/api/versions/current")
        if r.status_code != 200:
            return None
        return parse_release_name((r.json() or {}).get("releaseName"))
    except Exception:  # noqa: BLE001  unreadable is reported by the caller
        return None


def widget_import_refusal(client: VCFOpsClient, dashboards) -> "tuple":
    """``(refusal, note)`` for a content import of ``dashboards`` on ``client``.

    ``refusal`` is the message when the instance's version is below a widget
    type's floor (``widget_versions.import_refusal``): the caller must not
    import. ``note`` is a WARNING when a floored type is present but the
    version could not be read; the import goes ahead and the post-import
    :func:`import_shortfalls` check is what catches a loss. Both None when no
    dashboard carries a floored type (no request is made).
    """
    from vcfcf_core.dashboards.widget_versions import (
        WIDGET_TYPE_MIN_OPS_VERSION,
        import_refusal,
    )
    pairs = [
        (d.name, [(w.local_id, w.type) for w in d.widgets]) for d in dashboards
    ]
    if not any(
        WIDGET_TYPE_MIN_OPS_VERSION.get(t) is not None
        for _n, ws in pairs for _i, t in ws
    ):
        return None, None
    version = get_ops_version(client)
    if version is None:
        return None, (
            "could not read the instance version (GET /api/versions/current), "
            "so the widget-type floors were not checked before import; a "
            "dashboard with a widget type this build cannot import loses every "
            "dashboard in the import, which the import result check reports."
        )
    return import_refusal(pairs, version), None


def skipped_import_advice(content_type: str) -> str:
    """What an ``imported=0 / skipped=N`` result for ``content_type`` means
    for the request every factory import sends, ``force=true``
    (``import_content_zip``; the installer templates send the same).

    ``force=false`` (create-only) is named only to rule it out. It never
    asserts the skipped object exists: under the owner-mapping cause a
    dashboard was never created. Evidence and the "unexplained" rule:
    ``knowledge/context/api-surface/content_import_skip_semantics.md``.
    The installer templates carry the same two texts verbatim (pinned by
    a test).
    """
    if content_type == "DASHBOARDS":
        return (
            "This import sent force=true, so the create-only cause "
            "(force=false, which leaves an existing dashboard as it was) does "
            "not apply. The one demonstrated cause under force=true is an owner"
            " in usermappings.json that maps to no user on the target; the "
            "dashboard was then never created. Look in view-bridge.log for "
            "'restoreData failed to map Dashboard. File: <ownerId>' and check "
            "whether the dashboard exists on the instance. Without that log "
            "line the skip is unexplained: report it with the import envelope."
        )
    if content_type == "VIEW_DEFINITIONS":
        return (
            "This import sent force=true, so the create-only cause "
            "(force=false, which leaves an existing view as it was) does not "
            "apply, and an unmapped owner skips dashboards, not views. A view "
            "skip under force=true is unexplained: check whether the view "
            "exists on the instance and holds this version, and report the skip"
            " with the import envelope."
        )
    return (
        "The cause is not known for this content type. Check on the instance "
        "whether the object exists and holds this version, and report the "
        "skip with the import envelope."
    )


def get_current_user(client: VCFOpsClient) -> dict:
    """Return ``{id, username, firstName, lastName}`` for the
    authenticated user. Used by the sync path so generated content
    bundles can be owned by the real importing user rather than a
    synthetic placeholder."""
    r = client._request("GET", "/api/auth/currentuser")
    if r.status_code != 200:
        raise VCFOpsError(f"currentuser failed ({r.status_code}): {r.text}")
    return r.json()


def current_user_name(user: dict, default: str = "admin") -> str:
    """Return the account name from a ``/api/auth/currentuser`` body.

    The key is ``username`` (lower-case n): the ``user`` schema in the
    8.18, 9.0 and 9.1 Suite API specs under ``reference/docs/`` names
    it so, and a 9.0.2 response was observed with it on 2026-11-11.
    ``userName`` is the spelling the content-zip ``usermappings.json``
    and the ``/ui/`` login form use, not this endpoint; it is accepted
    second only so a body that ever carries it is not misread.
    ``default`` is the last resort, for a body with neither key.
    """
    if isinstance(user, dict):
        for key in ("username", "userName"):
            name = user.get(key)
            if isinstance(name, str) and name.strip():
                return name
    return default


def discover_marker_filename(client: VCFOpsClient, timeout_s: int = 120) -> str:
    """Return the ``<digits>L.v1`` marker filename this VCF Ops
    instance stamps onto every content export.

    The importer rejects bundles whose marker filename does not match
    the server's own value (verified by probing: 6844548499441080431L.v1
    imports fine, 6844548499441080432L.v1 returns INVALID_FILE_FORMAT).

    The filename is not a per-instance fingerprint. It was
    byte-identical (6844548499441080431L.v1) in five exports from four
    instances on 8.18.7, 9.0.2 and 9.1.1; only the file's content (the
    owner user uuid) varies (issue #166). It is not proven constant on
    every build, so it is still read from the target as insurance, by
    triggering a tiny SUPER_METRICS export, downloading the resulting
    zip, and reading the one entry that ends in ``L.v1``.

    There is no dedicated endpoint for it (checked /api/versions,
    /api/deployment/*, /api/cluster*) so a throwaway export is the
    cheapest reliable source.

    startTime is snapshotted before the POST so the completion poll
    can distinguish the new export from a prior already-FINISHED one.
    Without this, a stale FINISHED state from a previous run causes the
    poll to exit immediately and the zip download returns 400 because
    the prior zip was already consumed."""
    blob = export_content_zip(
        client, ["SUPER_METRICS"], timeout_s=timeout_s, label="marker-probe export"
    )
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            if name.endswith("L.v1"):
                return name
    raise VCFOpsError("export zip did not contain a *L.v1 marker file")


def export_content_zip(
    client: VCFOpsClient,
    content_types: list,
    timeout_s: int = 120,
    label: str = "export",
) -> bytes:
    """Run one CUSTOM content export and return the outer zip bytes.

    Waits for any export already in flight (only one may run at a time),
    snapshots the prior export's startTime, POSTs, then polls until an
    export that started after the snapshot reaches FINISHED. ``label``
    prefixes the error messages.
    """
    client._ensure_auth()
    # Wait for any export already in flight; only one may run at a time.
    deadline = time.monotonic() + timeout_s
    while True:
        g = client._request("GET", "/api/content/operations/export")
        if g.status_code == 200:
            st = (g.json() or {}).get("state", "")
            if st != "RUNNING" and st != "INITIALIZED":
                break
        if time.monotonic() > deadline:
            raise VCFOpsError("timed out waiting for prior export to finish")
        time.sleep(2)

    # Snapshot startTime of any prior export so the poll loop can
    # require start_time > prior_start_time, preventing a stale
    # FINISHED state from a previous run from being mistaken for ours.
    prior_start_time = 0
    g = client._request("GET", "/api/content/operations/export")
    if g.status_code == 200:
        prior_start_time = (g.json() or {}).get("startTime") or 0

    r = client._request(
        "POST",
        "/api/content/operations/export",
        json={"scope": "CUSTOM", "contentTypes": list(content_types)},
    )
    if r.status_code not in (200, 202):
        raise VCFOpsError(f"{label} failed ({r.status_code}): {r.text}")

    deadline = time.monotonic() + timeout_s
    while True:
        g = client._request("GET", "/api/content/operations/export")
        if g.status_code != 200:
            raise VCFOpsError(f"export status failed ({g.status_code}): {g.text}")
        body = g.json() or {}
        st = body.get("state", "")
        start_time = body.get("startTime") or 0
        # Require both a fresh startTime and a finished state so we
        # do not mistake the prior export's FINISHED state for ours.
        if start_time > prior_start_time and st.startswith("FINI"):
            break
        if time.monotonic() > deadline:
            raise VCFOpsError(f"{label} timed out; state={st}")
        time.sleep(2)

    z = client._session.get(f"{client.base}/api/content/operations/export/zip")
    if z.status_code != 200:
        raise VCFOpsError(f"export zip download failed ({z.status_code})")
    return z.content


def list_adapter_kind_keys(client: VCFOpsClient) -> set:
    """Adapter-kind keys installed on the target (GET /api/adapterkinds).

    Response shape per operations-api.json ``adapter-kinds``:
    ``{"adapter-kind": [{"key": "VMWARE", ...}, ...]}``.
    """
    r = client._request("GET", "/api/adapterkinds")
    if r.status_code != 200:
        raise VCFOpsError(f"adapterkinds read failed ({r.status_code}): {r.text[:300]}")
    body = r.json() or {}
    return {
        str(ak.get("key"))
        for ak in (body.get("adapter-kind") or [])
        if isinstance(ak, dict) and ak.get("key")
    }


#: Seconds to wait before the one re-check of dashboards still building
#: after the first read (issue #167). Phase 2 is observed at ~3 minutes after
#: a dashboard is first opened and up to ~20 minutes for the background pass
#: (knowledge/context/api-surface/ui_deep_links.md), so 180 s matches the
#: faster cadence without holding a sync for the slow one. Only paid when the
#: first read finds a dashboard still building.
MATERIALIZATION_RECHECK_DEFAULT_S = 180
#: Upper bound on the re-check wait, whatever is asked for, so a sync cannot
#: hang on it.
MATERIALIZATION_RECHECK_MAX_S = 900
#: Environment override for the wait (seconds), for the bundle-sync path,
#: which has no CLI flag of its own. A CLI flag wins over it.
MATERIALIZATION_RECHECK_ENV = "VCFCF_MATERIALIZATION_WAIT_S"


def materialization_recheck_wait(requested=None) -> int:
    """Re-check wait in seconds: ``requested``, else the env override, else
    the default; clamped to 0..MATERIALIZATION_RECHECK_MAX_S. 0 disables the
    re-check (anything still building is then reported at once)."""
    import os

    value = requested
    if value is None:
        raw = os.environ.get(MATERIALIZATION_RECHECK_ENV, "").strip()
        if raw:
            try:
                value = int(raw)
            except ValueError:
                value = None
    if value is None:
        value = MATERIALIZATION_RECHECK_DEFAULT_S
    return max(0, min(int(value), MATERIALIZATION_RECHECK_MAX_S))


def check_dashboard_materialization(
    client: VCFOpsClient,
    dashboards: list,
    recheck_wait_s=None,
    on_wait=None,
    _sleep=time.sleep,
) -> list:
    """Phase-2 state of each just-imported dashboard (issue #167).

    One DASHBOARDS export (read-only: it creates no content) gives each
    dashboard's ``importComplete`` / ``entryKeys``; when any is incomplete,
    one GET /api/adapterkinds names which pending adapter kinds the target
    lacks (STALLED). If any is incomplete with every pending adapter kind
    installed, it waits ``recheck_wait_s`` (see
    :func:`materialization_recheck_wait`), calling ``on_wait(count,
    seconds)`` first, and exports once more. Whatever is still building
    after that is INCOMPLETE: never reported as fine, because a dashboard
    can stay half-built for weeks with every adapter installed.

    ``dashboards`` is anything with ``.id`` and ``.name``. Returns
    :class:`vcfcf_core.dashboards.materialization.MaterializationStatus`
    per dashboard, never in the SETTLING state. Raises VCFOpsError when the
    first export fails; a failed re-check export or adapter-kind read
    degrades (the first read stands, or "not ruled out") rather than
    guessing. See
    knowledge/context/api-surface/dashboard_import_two_phase_materialization.md.
    """
    from vcfcf_core.dashboards.materialization import (
        SETTLING,
        classify_dashboards,
        finalize_statuses,
        is_incomplete,
    )
    from vcfcf_core.extractor import dashboards_from_export_zip

    wanted = {d.id: d.name for d in dashboards if getattr(d, "id", None)}
    if not wanted:
        return []
    ids = {str(i).lower() for i in wanted}
    installed_cache: dict = {}

    def _read() -> list:
        blob = export_content_zip(
            client, ["DASHBOARDS"], timeout_s=180,
            label="dashboard materialization export",
        )
        try:
            exported = dashboards_from_export_zip(blob)
        except ValueError as e:
            raise VCFOpsError(str(e)) from e
        if "kinds" not in installed_cache and any(
            is_incomplete(d) for d in exported if str(d.get("id") or "").lower() in ids
        ):
            try:
                installed_cache["kinds"] = list_adapter_kind_keys(client)
            except VCFOpsError:
                installed_cache["kinds"] = None
        return classify_dashboards(exported, wanted, installed_cache.get("kinds"))

    statuses = _read()
    wait = materialization_recheck_wait(recheck_wait_s)
    settling = [s for s in statuses if s.state == SETTLING]
    if not settling or wait <= 0:
        return finalize_statuses(statuses, 0)
    if on_wait is not None:
        on_wait(len(settling), wait)
    _sleep(wait)
    try:
        statuses = _read()
    except VCFOpsError:
        # The re-check is best effort: report from the first read.
        return finalize_statuses(statuses, 0)
    return finalize_statuses(statuses, wait)


def import_content_zip(client: VCFOpsClient, zip_bytes: bytes, timeout_s: int = 180) -> dict:
    """POST a multi-content ZIP to /api/content/operations/import and
    poll until the operation finishes.

    The endpoint is multipart/form-data with a single ``contentFile``
    field. The session's default JSON Content-Type header has to be
    suppressed so requests can set the multipart boundary.

    The POST response's ``id`` is a *stable pipeline id* for the content
    importer, not a per-operation id, every import on a given instance
    returns the same id. The GET status endpoint returns the summary of
    the last import operation. To tell "our" import apart from a prior
    one, snapshot ``endTime`` before POST and poll until it advances.

    Every factory content import goes through here, so the stock-id guard
    (#345) runs here too: a zip that defines content under a VCF Operations
    stock id is refused before anything is sent (it would overwrite the
    stock object), as is any import when the guard cannot run.
    """
    from vcfcf_packaging.stock_ids import StockIdRefused, refuse_stock_ids_in_zip
    try:
        refuse_stock_ids_in_zip(zip_bytes, "content import")
    except StockIdRefused as exc:
        raise VCFOpsError(str(exc)) from exc

    client._ensure_auth()

    # Snapshot the current import state so we can detect when the server
    # records OUR new run. A fresh instance reports no prior import, in
    # which case endTime is 0 and any advance means our run finished.
    pre = client._request("GET", "/api/content/operations/import")
    prior_end = 0
    if pre.status_code == 200:
        prior_end = (pre.json() or {}).get("endTime") or 0

    url = f"{client.base}/api/content/operations/import"
    # The session has a default `Content-Type: application/json` header
    # for the JSON endpoints. Override with None so requests can set the
    # multipart boundary itself; otherwise the server returns 500.
    r = client._session.post(
        url,
        headers={"Content-Type": None},
        params={"force": "true"},
        files={"contentFile": ("content.zip", zip_bytes, "application/zip")},
    )
    if r.status_code not in (200, 202):
        raise VCFOpsError(f"import failed ({r.status_code}): {r.text}")

    # Poll until a run that started after our POST shows up as finished.
    deadline = time.monotonic() + timeout_s
    while True:
        s = client._request("GET", "/api/content/operations/import")
        if s.status_code != 200:
            raise VCFOpsError(f"import status check failed ({s.status_code}): {s.text}")
        body = s.json()
        state = body.get("state", "")
        end_time = body.get("endTime") or 0
        if end_time > prior_end and state not in ("RUNNING", "INITIALIZED"):
            return body
        if time.monotonic() > deadline:
            raise VCFOpsError(f"import did not finish within {timeout_s}s; last state={state}")
        time.sleep(2)
