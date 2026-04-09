"""Content Management import client for dashboards / view definitions.

Reuses the auth/session handling from vcfops_supermetrics.client so we
have a single place that knows how to talk to the Suite API.
"""
from __future__ import annotations

import io
import time
import zipfile

from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError


def get_current_user(client: VCFOpsClient) -> dict:
    """Return ``{id, username, firstName, lastName}`` for the
    authenticated user. Used by the sync path so generated content
    bundles can be owned by the real importing user rather than a
    synthetic placeholder."""
    r = client._request("GET", "/api/auth/currentuser")
    if r.status_code != 200:
        raise VCFOpsError(f"currentuser failed ({r.status_code}): {r.text}")
    return r.json()


def discover_marker_filename(client: VCFOpsClient, timeout_s: int = 120) -> str:
    """Return the ``<digits>L.v1`` marker filename this VCF Ops
    instance stamps onto every content export.

    The importer rejects bundles whose marker filename does not match
    the server's own value (verified by probing: 6844548499441080431L.v1
    imports fine, 6844548499441080432L.v1 returns INVALID_FILE_FORMAT).
    Every export from the same cluster uses the same marker — it's a
    stable per-instance fingerprint — so we discover it by triggering a
    tiny SUPER_METRICS export, downloading the resulting zip, and
    reading the one entry that ends in ``L.v1``.

    There is no dedicated "cluster fingerprint" endpoint (checked
    /api/versions, /api/deployment/*, /api/cluster*) so a throwaway
    export is the cheapest reliable source."""
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

    r = client._request(
        "POST",
        "/api/content/operations/export",
        json={"scope": "CUSTOM", "contentTypes": ["SUPER_METRICS"]},
    )
    if r.status_code != 202:
        raise VCFOpsError(f"marker-probe export failed ({r.status_code}): {r.text}")

    deadline = time.monotonic() + timeout_s
    while True:
        g = client._request("GET", "/api/content/operations/export")
        if g.status_code != 200:
            raise VCFOpsError(f"export status failed ({g.status_code}): {g.text}")
        st = (g.json() or {}).get("state", "")
        if st.startswith("FINI"):
            break
        if time.monotonic() > deadline:
            raise VCFOpsError(f"marker-probe export timed out; state={st}")
        time.sleep(2)

    z = client._session.get(f"{client.base}/api/content/operations/export/zip")
    if z.status_code != 200:
        raise VCFOpsError(f"export zip download failed ({z.status_code})")
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        for name in zf.namelist():
            if name.endswith("L.v1"):
                return name
    raise VCFOpsError("export zip did not contain a *L.v1 marker file")


def import_content_zip(client: VCFOpsClient, zip_bytes: bytes, timeout_s: int = 180) -> dict:
    """POST a multi-content ZIP to /api/content/operations/import and
    poll until the operation finishes.

    The endpoint is multipart/form-data with a single ``contentFile``
    field. The session's default JSON Content-Type header has to be
    suppressed so requests can set the multipart boundary.

    The POST response's ``id`` is a *stable pipeline id* for the content
    importer, not a per-operation id — every import on a given instance
    returns the same id. The GET status endpoint returns the summary of
    the last import operation. To tell "our" import apart from a prior
    one, snapshot ``endTime`` before POST and poll until it advances.
    """
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
