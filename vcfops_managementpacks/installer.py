"""Management pack install and uninstall via VCF Ops /ui/ session API.

Implements the two scripted flows using the /ui/ SPA Struts layer:
  - Install:   login → prepareFileUpload → upload → trigger install → poll → logout
  - Uninstall: login → getIntegrations → isUnremovable guard → remove → poll → logout

Both flows run through a single _UISession.  The former dual-session design
(_AdminSession for install, _UISession for uninstall) was eliminated after
context/pak_ui_upload_investigation.md §"Live-source findings (2026-04-16,
second pass)" confirmed that /ui/admin/services/solution/upload is a live
endpoint backed by the same Java handler as /admin/admin/services/solution/upload,
and that /ui/solution.action exposes the full install lifecycle mainAction surface
including getLatestInstalledSolutionStatuses.

Both flows use undocumented internal Struts endpoints; they are not part of
any public VCF Ops REST API contract.  All path handling mirrors what the
/ui/ SPA JavaScript client does.

PakId namespace split (important):
  - Upload response (install):  compressed, e.g. "BroadcomSecurityAdvisories-1016"
    Returned by the upload endpoint and used for install and status polling.
  - UI side (uninstall):        short/display form, e.g. "Broadcom Security Advisories"
    Returned by getIntegrations; required for the remove mainAction.
  The two forms are NOT interchangeable.  Passing the wrong form to remove
  returns {} silently and does nothing.  This module always looks up the
  correct form from the appropriate endpoint before issuing a mutating call.
  Switching from /admin/ to /ui/ for upload does NOT collapse this split —
  the upload endpoint returns the same compressed pakId regardless of which
  servlet context serves it.  See context/pak_ui_upload_investigation.md
  §"Upload response shape".

CREDENTIALS (primary env vars — matches the rest of the factory):
  VCFOPS_HOST          hostname or IP of the VCF Ops instance
  VCFOPS_USER          admin-privileged username
  VCFOPS_PASSWORD      password for VCFOPS_USER

BACKWARD COMPAT (old names still accepted, emit a deprecation warning):
  VCFOPS_ADMIN         → fallback for VCFOPS_USER  (deprecated)
  VCFOPS_ADMINPASSWORD → fallback for VCFOPS_PASSWORD  (deprecated)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import requests
    import urllib3
except ImportError as _e:
    raise ImportError(
        "The 'requests' package is required for pak install/uninstall. "
        "Install it with: pip install requests"
    ) from _e

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
POLL_INTERVAL = 5          # seconds between status polls
POLL_TIMEOUT = 300         # seconds before giving up — NOTE: subprocess wrappers that
                           # invoke `vcfops_managementpacks install` must set their own
                           # subprocess timeout HIGHER than this value (suggest 400s).
                           # A 300s subprocess timeout will race the poller and kill the
                           # installer while it is still waiting for the server.
UPLOAD_POLL_INTERVAL = 3   # seconds between upload-progress polls


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _abort(msg: str) -> None:
    """Print a clear error to stderr and exit non-zero."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(msg)


def _check_json_error(body: Dict[str, Any], context: str) -> None:
    """Raise RuntimeError if the response body contains an errorMsg key.

    Both /admin/ and /ui/ Struts handlers use the same convention:
      - success: {} or {... no errorMsg key ...}
      - failure: {"errorMsg": "<reason>"}
    NOTE: 'success: true' may be present even on failure (upload endpoint).
    """
    err = body.get("errorMsg")
    if err:
        raise RuntimeError(f"{context}: {err}")


def _resolve_credentials(
    host: Optional[str],
    user: Optional[str],
    password: Optional[str],
) -> Tuple[str, str, str]:
    """Resolve host/user/password from args then env vars.

    Primary env vars: VCFOPS_HOST, VCFOPS_USER, VCFOPS_PASSWORD.
    Backward-compat fallbacks: VCFOPS_ADMIN, VCFOPS_ADMINPASSWORD — both
    still accepted but emit a deprecation warning on stderr.

    Returns (host, user, password).  Calls _abort() if any are missing.
    """
    host = host or os.environ.get("VCFOPS_HOST", "").strip()

    # User: try primary name first, then old name with warning
    user = user or os.environ.get("VCFOPS_USER", "").strip()
    if not user:
        old_user = os.environ.get("VCFOPS_ADMIN", "").strip()
        if old_user:
            _warn(
                "VCFOPS_ADMIN is deprecated; rename to VCFOPS_USER. "
                "Support for VCFOPS_ADMIN will be removed in a future release."
            )
            user = old_user

    # Password: try primary name first, then old name with warning
    password = password or os.environ.get("VCFOPS_PASSWORD", "").strip()
    if not password:
        old_pw = os.environ.get("VCFOPS_ADMINPASSWORD", "").strip()
        if old_pw:
            _warn(
                "VCFOPS_ADMINPASSWORD is deprecated; rename to VCFOPS_PASSWORD. "
                "Support for VCFOPS_ADMINPASSWORD will be removed in a future release."
            )
            password = old_pw

    missing = []
    if not host:
        missing.append("VCFOPS_HOST")
    if not user:
        missing.append("VCFOPS_USER")
    if not password:
        missing.append("VCFOPS_PASSWORD")
    if missing:
        _abort(
            f"Missing required credentials: {', '.join(missing)}.\n"
            f"  Set as env vars or pass as CLI flags (--host, --user, --password)."
        )

    return host, user, password


# ---------------------------------------------------------------------------
# Manifest parsing (offline — no network)
# ---------------------------------------------------------------------------

def _parse_manifest_txt(pak_path: Path) -> Dict[str, str]:
    """Extract key=value pairs from manifest.txt inside a .pak zip file.

    Corresponds to context/pak_install_api_exploration.md pre-flight check:
    parse manifest before uploading to catch obviously-broken paks early.

    Returns a dict of all key=value pairs.  Raises RuntimeError on bad pak.
    """
    try:
        with zipfile.ZipFile(pak_path, "r") as zf:
            names = zf.namelist()
            # manifest.txt may be at root or inside a subdirectory
            manifest_names = [n for n in names if n == "manifest.txt"
                              or n.endswith("/manifest.txt")]
            if not manifest_names:
                raise RuntimeError(
                    f"manifest.txt not found in {pak_path.name}. "
                    f"Files present: {names[:20]}"
                )
            manifest_name = manifest_names[0]
            raw = zf.read(manifest_name).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as e:
        raise RuntimeError(
            f"{pak_path.name} is not a valid zip/pak file: {e}"
        ) from e

    # Modern MPB-built paks (e.g. Rubrik, Synology) use JSON format;
    # legacy paks use key=value.  Both expose 'name' and 'version' at the
    # top level so the caller's manifest.get('name') / manifest.get('version')
    # works without any special-casing there.
    result: Dict[str, str] = {}
    if raw.strip().startswith("{"):
        # JSON manifest.txt (MPB >= some version)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"manifest.txt in {pak_path.name} looks like JSON but could not "
                f"be parsed: {e}"
            ) from e
        # Flatten all top-level string/int/bool values to strings; skip
        # nested objects (adapters, adapter_kinds) — the caller only needs
        # name and version for pre-flight display.
        for k, v in parsed.items():
            if isinstance(v, (str, int, float, bool)):
                result[str(k)] = str(v)
    else:
        # Legacy key=value manifest.txt
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# UI session (/ui/ — ExtJS SPA, handles full pak lifecycle)
# ---------------------------------------------------------------------------

class _UISession:
    """Encapsulates authentication and request helpers for the /ui/ Struts context.

    This single session class drives the complete pak install + uninstall
    lifecycle.  It supersedes the former dual-session design where _AdminSession
    handled install and _UISession handled uninstall.

    AUTH PATTERN
    The /ui/ context is the main VCF Ops ExtJS SPA.  It uses a JSESSIONID scoped
    to /ui/ (separate from the /admin/ context).  CSRF token comes from the
    base64-decoded OPS_SESSION cookie obtained from GET /ui/index.action.

    CSRF is injected by the SPA's commonJS.action Ext.Ajax requestbefore hook
    as both a form field (secureToken=<csrf>) and a header (secureToken: <csrf>).
    Most POSTs use the form-field form only (identical to the admin-side pattern).
    EXCEPTION: /ui/admin/services/solution/upload requires secureToken as BOTH
    a request header AND a form field — empirically confirmed by qa-tester
    (2026-04-17); without the header the upload endpoint returns HTTP 500.
    See upload_pak() for the explicit header injection.

    INSTALL WIRE FORMAT
    Upload endpoint:  POST /ui/admin/services/solution/upload
                          ?uploadId=<epoch_ms>
                          &ignoreSignatureChecking=<bool>
      Form fields:    solution=@<file>.pak  (multipart)
                      forceUpload=<bool>
                      forceContent=<bool>
                      secureToken=<csrf>
    (Note: ignoreSignatureChecking is on the QUERY STRING for the /ui/ path;
    on the /admin/ path it was a form field.  This mirrors the SPA wire format
    exactly per context/pak_ui_upload_investigation.md §"Wire format".)

    prepareFileUpload:  POST /ui/utility.action  mainAction=prepareFileUpload
    install trigger:    POST /ui/solution.action  mainAction=install
                             (+ optional forceContentUpdate=true)
    status polling:     POST /ui/solution.action
                             mainAction=getLatestInstalledSolutionStatuses
    (NOTE: getLatestInstalledSolutionStatuses is advertised on /ui/solution.action
    per the mainAction surface enumerated in context/bug_report_pak_isunremovable_not_enforced.md
    and verified live for the uninstall flow.  The install-side exercising of this
    endpoint via /ui/ is implicit from the shared wizard code that backs both
    /ui/ and /admin/ — it has NOT been independently exercised end-to-end for
    install status from the /ui/ side.  Live verification is pending Scott's
    authorization.)

    UNINSTALL WIRE FORMAT
    getIntegrations:  POST /ui/solution.action  mainAction=getIntegrations
    remove:           POST /ui/solution.action  mainAction=remove
                           pakId=<short-display-form>  version=<ver>

    Documented in context/pak_ui_upload_investigation.md (install) and
    context/pak_uninstall_api_exploration.md (uninstall).
    Also see context/dashboard_delete_api.md Authentication flow for the
    identical /ui/ login pattern used elsewhere in the factory.
    """

    def __init__(self, host: str, user: str, password: str,
                 verify_ssl: bool = True):
        self._host = host
        self._user = user
        self._password = password
        self._verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None
        self._csrf: Optional[str] = None

    def login(self) -> None:
        """Three-step /ui/ login: JSESSIONID seed → credentials → OPS_SESSION CSRF.

        Step 1:  GET /ui/login.action?vcf=1 to seed JSESSIONID scoped to /ui.
        Step 2:  POST /ui/login.action with full credential form.
        Step 3:  GET /ui/index.action (no redirect) to receive OPS_SESSION cookie;
                 decode base64(OPS_SESSION) and extract csrfToken.

        IMPORTANT: do NOT follow the 302 redirect from index.action.
        Following it invalidates OPS_SESSION (the redirect target sets
        OPS_SESSION=x with a past expiry).
        """
        if not self._verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        s = requests.Session()
        s.verify = self._verify_ssl

        # Step 1: seed JSESSIONID
        try:
            s.get(f"https://{self._host}/ui/login.action", params={"vcf": "1"})
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Cannot connect to {self._host}: {e}. "
                f"Check VCFOPS_HOST and network connectivity."
            ) from e

        # Step 2: authenticate
        r = s.post(
            f"https://{self._host}/ui/login.action",
            data={
                "mainAction": "login",
                "userName": self._user,
                "password": self._password,
                "authSourceId": "localItem",
                "authSourceName": "Local Account",
                "authSourceType": "",
                "forceLogin": "false",
                "timezone": "0",
                "languageCode": "us",
            },
        )
        if r.text.strip() != "ok":
            raise RuntimeError(
                f"UI login failed for user '{self._user}': {r.text!r}. "
                f"Check VCFOPS_USER and VCFOPS_PASSWORD."
            )

        # Step 3: get OPS_SESSION cookie (do NOT follow redirect)
        r = s.get(
            f"https://{self._host}/ui/index.action",
            allow_redirects=False,
        )
        ops_cookie = (
            r.cookies.get("OPS_SESSION")
            or s.cookies.get("OPS_SESSION")
        )
        if not ops_cookie:
            raise RuntimeError(
                "OPS_SESSION cookie not received from /ui/index.action. "
                "Check credentials and that the account has UI access."
            )
        try:
            ops_data = json.loads(base64.b64decode(ops_cookie))
        except Exception as e:
            raise RuntimeError(
                f"Failed to decode OPS_SESSION cookie: {e}"
            ) from e

        csrf = ops_data.get("csrfToken")
        if not csrf:
            raise RuntimeError(
                f"csrfToken not found in OPS_SESSION payload. "
                f"Keys present: {list(ops_data.keys())}"
            )

        self._session = s
        self._csrf = csrf

    def logout(self) -> None:
        """Clean logout from /ui/ session."""
        if self._session is None:
            return
        try:
            self._session.get(
                f"https://{self._host}/ui/login.action",
                params={"mainAction": "logout"},
                allow_redirects=False,
            )
        except Exception:
            pass
        finally:
            self._session = None
            self._csrf = None

    def solution_action(self, **kwargs) -> Dict[str, Any]:
        """POST /ui/solution.action with arbitrary form fields + CSRF."""
        assert self._session is not None, "call login() first"
        r = self._session.post(
            f"https://{self._host}/ui/solution.action",
            data={"secureToken": self._csrf or "", **kwargs},
        )
        r.raise_for_status()
        if not r.text.strip():
            return {}
        return r.json()

    # ------------------------------------------------------------------
    # Install-side methods
    # ------------------------------------------------------------------

    def prepare_upload(self) -> None:
        """POST /ui/utility.action mainAction=prepareFileUpload.

        Must be called immediately before the multipart upload.
        Mirrors the admin-side prepareFileUpload step documented in
        context/pak_install_api_exploration.md step 3.

        /ui/utility.action is a registered Struts handler on the /ui/ side
        (proven by the SPA bundle grep in context/pak_ui_upload_investigation.md
        §"prepareFileUpload precursor").  Not live-tested via this code path;
        proven only from JS source inspection.
        """
        assert self._session is not None
        r = self._session.post(
            f"https://{self._host}/ui/utility.action",
            data={
                "mainAction": "prepareFileUpload",
                "secureToken": self._csrf or "",
            },
        )
        if not r.ok:
            raise RuntimeError(
                f"prepareFileUpload returned HTTP {r.status_code}. "
                f"Response body: {r.text[:2000]}"
            )
        body = r.json()
        if not body.get("success"):
            raise RuntimeError(f"prepareFileUpload failed: {body}")

    def upload_pak(self, pak_path: Path, force_upload: bool = True,
                   force_content: bool = False,
                   ignore_signature: bool = True) -> Dict[str, Any]:
        """POST /ui/admin/services/solution/upload?uploadId=<epoch_ms>&ignoreSignatureChecking=<bool>

        Multipart body: solution=@<file>.pak, forceUpload, forceContent, secureToken.
        Request headers: secureToken=<csrf> (REQUIRED — upload endpoint is uniquely
        strict; form-field-only returns HTTP 500), accept=application/json (advisory).

        KEY DIFFERENCE FROM /admin/ PATH: ignoreSignatureChecking is on the
        QUERY STRING here, not in the form body.  This mirrors the SPA's exact
        wire format (context/pak_ui_upload_investigation.md §"Wire format",
        uploadSolution() at part4 offset 487784).

        Returns the full JSON response including pakId (compressed form,
        e.g. "BroadcomSecurityAdvisories-1016").  The pakId namespace does
        NOT change just because we're using the /ui/ path — see module docstring.

        force_upload=True is appropriate for factory use.
        ignore_signature=True is appropriate for unsigned development paks.
        force_content=False (default) matches the SPA default for fresh installs.
        """
        assert self._session is not None
        upload_id = str(int(time.time() * 1000))

        # The /ui/admin/services/solution/upload endpoint requires secureToken
        # as a REQUEST HEADER in addition to the form body field.  All other
        # solution.action POSTs work with form-field-only, but this servlet is
        # uniquely strict — without the header it returns HTTP 500 regardless
        # of credentials, pak, or other params.  Empirically confirmed by
        # qa-tester (2026-04-17 run /tmp/qa-run-1776427320/): every upload
        # attempt without the header returned HTTP 500; every attempt with it
        # returned HTTP 200 with a clean success response.
        # Reference: context/pak_ui_upload_investigation.md §"CSRF placement"
        # (the SPA's Ext.Ajax.request hook always injects secureToken as both
        # header and form param; Ext.form.Panel.submit() injects form-param only
        # — upload uses a form submit, so the header must be set explicitly here).
        upload_headers = {
            "secureToken": self._csrf or "",
            "accept": "application/json, text/javascript, */*; q=0.01",
        }

        with open(pak_path, "rb") as fh:
            files = {
                "solution": (pak_path.name, fh, "application/octet-stream"),
            }
            data = {
                "forceUpload": "true" if force_upload else "false",
                "forceContent": "true" if force_content else "false",
                "secureToken": self._csrf or "",
            }
            r = self._session.post(
                f"https://{self._host}/ui/admin/services/solution/upload",
                params={
                    "uploadId": upload_id,
                    "ignoreSignatureChecking": "true" if ignore_signature else "false",
                },
                headers=upload_headers,
                files=files,
                data=data,
            )

        if not r.ok:
            raise RuntimeError(
                f"Upload returned HTTP {r.status_code}. "
                f"Response body (first 2000 chars): {r.text[:2000]}"
            )
        try:
            body = r.json()
        except Exception:
            raise RuntimeError(
                f"Upload returned non-JSON (status {r.status_code}): "
                f"{r.text[:500]}"
            )

        # NOTE: upload returns {"success":true, "errorMsg":"..."} on rejection.
        # "success":true does NOT mean the pak was accepted; check errorMsg.
        err = body.get("errorMsg")
        if err:
            raise RuntimeError(f"Pak upload rejected by PAK Manager: {err}")

        if not body.get("pakId"):
            raise RuntimeError(
                f"Upload succeeded but no pakId in response. "
                f"Response: {json.dumps(body)[:500]}"
            )

        return body

    def trigger_install(self, pak_id: str) -> None:
        """POST /ui/solution.action mainAction=install pakId=<id> forceContentUpdate=true.

        pak_id is the compressed form (e.g. "BroadcomSecurityAdvisories-1016")
        returned by the upload endpoint.

        The SPA wizard relies on server-side session state for pakId (it does
        not always pass it explicitly).  Passing it explicitly via pakId param
        is safe — the handler accepts it and being unambiguous is better for
        scripted use.  See context/pak_ui_upload_investigation.md
        §"Post-upload install handoff".

        Success shape: {} (empty dict, no errorMsg key).
        Failure shape: {"errorMsg": "..."}.
        """
        body = self.solution_action(
            mainAction="install",
            pakId=pak_id,
            forceContentUpdate="true",
        )
        _check_json_error(body, f"install mainAction for pakId={pak_id}")

    def get_installed_statuses(self) -> Dict[str, Any]:
        """POST /ui/solution.action mainAction=getLatestInstalledSolutionStatuses.

        NOTE: NON-FUNCTIONAL on VCF Ops 9.0.2.  Returns empty body at rest and
        {"pakInstalling": True, "solutionStatuses": []} during operations; never
        transitions to a terminal state.  Kept for reference only.
        Use is_pak_installing() for reliable polling on 9.0.2.
        Confirmed non-functional by qa-tester 2026-04-17 10-cycle run.
        """
        return self.solution_action(
            mainAction="getLatestInstalledSolutionStatuses"
        )

    def is_pak_installing(self) -> Dict[str, Any]:
        """POST /ui/clusterManagement.action mainAction=isPakInstalling.

        Returns {"isPakInstalling": bool, "isPakUninstallActive": bool}.
        Both fields transition correctly on VCF Ops 9.0.2 — confirmed working
        by qa-tester 2026-04-17 10-cycle run.

        Terminal conditions:
          - Install done:   not isPakInstalling
          - Uninstall done: not isPakInstalling AND not isPakUninstallActive
        """
        assert self._session is not None
        r = self._session.post(
            f"https://{self._host}/ui/clusterManagement.action",
            data={
                "mainAction": "isPakInstalling",
                "secureToken": self._csrf or "",
            },
        )
        if not r.ok:
            raise RuntimeError(
                f"isPakInstalling returned HTTP {r.status_code}. "
                f"Response body: {r.text[:2000]}"
            )
        try:
            return r.json()
        except Exception:
            raise RuntimeError(
                f"isPakInstalling returned non-JSON (status {r.status_code}): "
                f"{r.text[:500]}"
            )

    # ------------------------------------------------------------------
    # Uninstall-side methods
    # ------------------------------------------------------------------

    def get_integrations(self) -> list:
        """POST /ui/solution.action mainAction=getIntegrations.

        Returns the installedMPs[] list.  Each entry has:
          - pakId (str): UI short form, e.g. "Broadcom Security Advisories"
          - name (str): display name (often same as pakId on /ui/ side)
          - version (str): e.g. "1.0.1.6"
          - isUnremovable (bool): True for built-in paks (vSAN, vCenter, NSX, etc.)
          - adapter_kind (str): e.g. "mpb_broadcom_security_advisories"
        """
        body = self.solution_action(mainAction="getIntegrations")
        return body.get("installedMPs", [])

    def remove_pak(self, short_pak_id: str, version: str) -> None:
        """POST /ui/solution.action mainAction=remove pakId=<short> version=<ver>.

        short_pak_id: the UI-side short form (from getIntegrations .pakId field),
                      e.g. "Broadcom Security Advisories".
                      NOT the compressed form "BroadcomSecurityAdvisories-1016".

        Passing the wrong pakId form returns {} silently and does nothing —
        this is why we always resolve via getIntegrations first.

        Success shape: {} (empty body, no errorMsg key).
        Failure shape: {"errorMsg": "..."}.
        """
        body = self.solution_action(
            mainAction="remove",
            pakId=short_pak_id,
            version=version,
        )
        _check_json_error(body, f"remove mainAction for pakId={short_pak_id!r}")


# ---------------------------------------------------------------------------
# Public install function
# ---------------------------------------------------------------------------

def install_pak(
    pak_path: str,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    skip_ssl_verify: bool = False,
    wait: bool = True,
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> None:
    """Install a .pak file onto a VCF Ops instance via the /ui/ SPA Struts layer.

    All steps run through a single _UISession — no /admin/ session required.

    Steps executed:
      1:   Manifest parse (offline preflight)
      2:   _UISession.login()  (3-step /ui/ login + OPS_SESSION CSRF)
      3:   _UISession.prepare_upload()  (/ui/utility.action prepareFileUpload)
      4:   _UISession.upload_pak()  (/ui/admin/services/solution/upload)
      5:   _UISession.trigger_install()  (/ui/solution.action mainAction=install)
      6:   Poll _UISession.get_installed_statuses() until completed
      7:   _UISession.logout()

    Credentials resolve order: CLI flags > VCFOPS_USER/VCFOPS_PASSWORD env vars >
    legacy VCFOPS_ADMIN/VCFOPS_ADMINPASSWORD env vars (deprecated, warn).
    """
    p = Path(pak_path)
    if not p.exists():
        _abort(f"Pak file not found: {pak_path}")
    if not p.is_file():
        _abort(f"Not a file: {pak_path}")

    host, user, password = _resolve_credentials(host, user, password)

    # Pre-flight: parse manifest.txt to get declared name + version
    _info(f"[1/6] Parsing manifest from {p.name} ...")
    try:
        manifest = _parse_manifest_txt(p)
    except RuntimeError as e:
        _abort(str(e))

    pak_name = manifest.get("name", "(unknown)")
    pak_version = manifest.get("version", "(unknown)")
    _info(f"      name={pak_name!r}  version={pak_version!r}")
    pak_size_mb = p.stat().st_size / (1024 * 1024)
    _info(f"      size={pak_size_mb:.1f} MB")

    # UI session login
    _info(f"[2/6] Authenticating to /ui/ as {user!r} ...")
    ui = _UISession(
        host=host,
        user=user,
        password=password,
        verify_ssl=not skip_ssl_verify,
    )
    try:
        ui.login()
    except RuntimeError as e:
        _abort(str(e))

    try:
        # prepare upload
        _info("[3/6] Preparing upload slot (/ui/utility.action prepareFileUpload) ...")
        try:
            ui.prepare_upload()
        except RuntimeError as e:
            _abort(str(e))

        # upload
        _info(f"[4/6] Uploading {p.name} to /ui/admin/services/solution/upload ...")
        try:
            upload_result = ui.upload_pak(
                p,
                force_upload=True,
                ignore_signature=True,
            )
        except RuntimeError as e:
            _abort(str(e))

        pak_id = upload_result["pakId"]
        server_name = upload_result.get("solutionName", pak_name)
        server_version = upload_result.get("solutionVersion", pak_version)
        cluster_offline = upload_result.get("clusterBringOffline", False)
        cluster_restart = upload_result.get("clusterRestartRequired", False)

        _info(f"      Upload accepted: pakId={pak_id!r}")
        _info(f"      Server name: {server_name!r}  version: {server_version!r}")
        if cluster_offline:
            _warn("Cluster will be taken offline during install.")
        if cluster_restart:
            _warn("Cluster restart will be required after install.")

        # trigger install
        _info("[5/6] Triggering install (/ui/solution.action mainAction=install) ...")
        try:
            ui.trigger_install(pak_id)
        except RuntimeError as e:
            _abort(str(e))

        # poll until done
        if wait:
            _info(
                f"[6/6] Waiting for install to complete "
                f"(timeout {poll_timeout}s, poll every {poll_interval}s) ..."
            )
            # Use isPakInstalling (clusterManagement.action) — confirmed working
            # on VCF Ops 9.0.2.  getLatestInstalledSolutionStatuses is non-functional
            # on 9.0.2 (returns empty solutionStatuses[], never transitions).
            deadline = time.time() + poll_timeout
            last_state = "(unknown)"
            while time.time() < deadline:
                try:
                    status = ui.is_pak_installing()
                except Exception as e:
                    _warn(f"Status poll failed (will retry): {e}")
                    time.sleep(poll_interval)
                    continue

                installing = status.get("isPakInstalling", True)
                uninstall_active = status.get("isPakUninstallActive", False)
                last_state = (
                    f"pakInstalling={installing}  "
                    f"pakUninstallActive={uninstall_active}"
                )
                _info(f"      {last_state}")

                if not installing:
                    _info(f"OK: Install completed: {server_name} {server_version}")
                    return

                time.sleep(poll_interval)

            # Timeout
            _abort(
                f"Install timed out after {poll_timeout}s. "
                f"Last known status: {last_state}\n"
                f"The install may still be running on the server. "
                f"Check Admin UI > Software Updates > Solutions."
            )
        else:
            _info(
                f"[6/6] Install triggered (--no-wait set). "
                f"Check Admin UI > Software Updates > Solutions for status."
            )

    finally:
        # logout
        ui.logout()


# ---------------------------------------------------------------------------
# Public uninstall function
# ---------------------------------------------------------------------------

def uninstall_pak(
    adapter_kind_or_pak_name: str,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    skip_ssl_verify: bool = False,
    wait: bool = True,
    allow_builtin: bool = False,
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> None:
    """Uninstall a management pack from a VCF Ops instance.

    All steps run through a single _UISession.  The former design spun up
    a separate _AdminSession for status polling after issuing remove; that
    second session has been eliminated since /ui/solution.action exposes
    getLatestInstalledSolutionStatuses on the /ui/ side.

    Steps executed:
      1:  _UISession.login()  (/ui/ session + OPS_SESSION CSRF)
      2:  _UISession.get_integrations()  (resolve name → short pakId + version)
      3:  isUnremovable guard (MANDATORY — server does NOT enforce this)
      4:  _UISession.remove_pak()
      5:  Poll _UISession.get_installed_statuses() until completed
      6:  _UISession.logout()

    The isUnremovable guard is the most critical safety feature.  Bypassing
    it by sending remove against a built-in pak (vSAN, vCenter, NSX, etc.)
    partially deregisters the adapter kind and leaves the instance in a stuck
    state requiring manual recovery.  See context/pak_uninstall_api_exploration.md
    Safety-critical section for the full incident report.

    Credentials resolve order: CLI flags > VCFOPS_USER/VCFOPS_PASSWORD env vars >
    legacy VCFOPS_ADMIN/VCFOPS_ADMINPASSWORD env vars (deprecated, warn).
    """
    host, user, password = _resolve_credentials(host, user, password)

    # Step 1: UI session login
    _info(f"[1/5] Authenticating to /ui/ as {user!r} ...")
    ui = _UISession(
        host=host,
        user=user,
        password=password,
        verify_ssl=not skip_ssl_verify,
    )
    try:
        ui.login()
    except RuntimeError as e:
        _abort(str(e))

    try:
        # Step 2: resolve pak name → (short UI pakId, version)
        _info("[2/5] Fetching installed management packs ...")
        try:
            installed = ui.get_integrations()
        except RuntimeError as e:
            _abort(str(e))

        target = _find_installed_entry(installed, adapter_kind_or_pak_name)

        if target is None:
            _info(
                f"OK: '{adapter_kind_or_pak_name}' is not currently installed "
                f"(nothing to remove)."
            )
            return

        short_pak_id = target["pakId"]
        version = target.get("version", "")
        display_name = target.get("name", short_pak_id)
        is_unremovable = bool(target.get("isUnremovable", False))

        _info(
            f"      Found: name={display_name!r}  pakId={short_pak_id!r}  "
            f"version={version!r}  isUnremovable={is_unremovable}"
        )

        # Step 3: MANDATORY isUnremovable guard
        # The server does NOT enforce this flag; the UI disables the remove
        # button for built-in paks but the mainAction=remove handler accepts
        # ANY pakId regardless.  See context/pak_uninstall_api_exploration.md
        # Safety-critical section.
        if is_unremovable and not allow_builtin:
            print(
                f"\nABORT: {display_name} is marked isUnremovable=true.  "
                f"Built-in solutions cannot be\n"
                f"safely uninstalled via the factory.  The server does NOT "
                f"enforce this flag;\n"
                f"sending the remove call anyway will run uninstall against "
                f"the built-in and\n"
                f"leave the instance in a stuck state that requires manual "
                f"recovery.\n\n"
                f"If you are absolutely certain this is what you want "
                f"(e.g. reinstalling a\n"
                f"built-in after a known-good snapshot), pass --allow-builtin.",
                file=sys.stderr,
            )
            sys.exit(2)

        if is_unremovable and allow_builtin:
            _warn(
                f"--allow-builtin set: proceeding with removal of "
                f"isUnremovable=true pak '{display_name}'. "
                f"This may damage the instance."
            )

        # Step 4: issue remove
        _info(f"[3/5] Issuing remove for '{display_name}' version {version!r} ...")
        try:
            ui.remove_pak(short_pak_id, version)
        except RuntimeError as e:
            _abort(str(e))
        _info("      Remove accepted by server.")

        # Step 5: poll via the same UI session
        if wait:
            _info(
                f"[4/5] Waiting for uninstall to complete "
                f"(timeout {poll_timeout}s, poll every {poll_interval}s) ..."
            )
            _poll_uninstall_completion(
                ui,
                display_name,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
            )
        else:
            _info(
                "[4/5] Uninstall triggered (--no-wait set). "
                "Check Admin UI > Software Updates > Solutions for status."
            )

        _info(f"[5/5] Logging out.")

    finally:
        ui.logout()


def _find_installed_entry(
    installed: list,
    adapter_kind_or_pak_name: str,
) -> Optional[Dict[str, Any]]:
    """Resolve a user-supplied name to an installedMPs[] entry.

    Matches (case-insensitive) against:
      1. entry['pakId']       — the short UI-side pakId
      2. entry['name']        — display name
      3. entry['adapterKind'] — adapter kind key (camelCase, as returned by getIntegrations)
      4. entry['adapter_kind'] — legacy snake_case fallback (not returned by getIntegrations
                                  on VCF Ops 9.0.2; kept for forward-compat in case a future
                                  API version normalises casing differently)

    NOTE: getIntegrations returns adapterKind (camelCase) on VCF Ops 9.0.2.
    Checking only adapter_kind (snake_case) caused silent no-match on every
    uninstall-by-adapter-kind call.  Fix confirmed by qa-tester 2026-04-17.

    Returns the matched entry dict, or None if not found.
    """
    query = adapter_kind_or_pak_name.strip().lower()
    for entry in installed:
        if (
            str(entry.get("pakId", "")).strip().lower() == query
            or str(entry.get("name", "")).strip().lower() == query
            or str(entry.get("adapterKind", "")).strip().lower() == query   # camelCase (real field)
            or str(entry.get("adapter_kind", "")).strip().lower() == query  # snake_case (legacy fallback)
        ):
            return entry
    return None


def _poll_uninstall_completion(
    ui: _UISession,
    target_name: str,
    poll_interval: int,
    poll_timeout: int,
) -> None:
    """Poll /ui/clusterManagement.action isPakInstalling until uninstall is done.

    Runs on the same _UISession that issued the remove — no second session needed.

    Uses isPakInstalling (clusterManagement.action) which is confirmed working on
    VCF Ops 9.0.2.  getLatestInstalledSolutionStatuses was previously used here
    but is non-functional on 9.0.2 (returns empty solutionStatuses[], never
    transitions).  Confirmed non-functional by qa-tester 2026-04-17 10-cycle run.

    Terminal condition: not isPakInstalling AND not isPakUninstallActive.
    Both must be False to confirm uninstall completion — isPakInstalling alone
    going False can be a transient state during the uninstall sequence.
    """
    deadline = time.time() + poll_timeout
    last_state = "(unknown)"

    while time.time() < deadline:
        try:
            status = ui.is_pak_installing()
        except Exception as e:
            _warn(f"Status poll failed (will retry): {e}")
            time.sleep(poll_interval)
            continue

        installing = status.get("isPakInstalling", True)
        uninstall_active = status.get("isPakUninstallActive", True)
        last_state = (
            f"pakInstalling={installing}  pakUninstallActive={uninstall_active}"
        )
        _info(f"      {last_state}")

        if not installing and not uninstall_active:
            _info(f"OK: Uninstall completed: {target_name}")
            return

        time.sleep(poll_interval)

    _abort(
        f"Uninstall timed out after {poll_timeout}s. "
        f"Last known status: {last_state}\n"
        f"The uninstall may still be running on the server. "
        f"Check Admin UI > Software Updates > Solutions."
    )
