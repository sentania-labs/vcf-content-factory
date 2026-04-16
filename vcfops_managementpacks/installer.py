"""Management pack install and uninstall via VCF Ops admin/UI session APIs.

Implements the two scripted flows documented in:
  - context/pak_install_api_exploration.md  (11-step admin SPA install)
  - context/pak_uninstall_api_exploration.md (/ui/ SPA remove + isUnremovable guard)

Both flows use undocumented internal Struts endpoints; they are not part of
any public VCF Ops REST API contract.  All path handling mirrors what the
admin-SPA and main-UI-SPA JavaScript clients do.

PakId namespace split (important):
  - Admin side (install):  compressed, e.g. "BroadcomSecurityAdvisories-1016"
    Returned by the upload endpoint; used for install and status polling.
  - UI side (uninstall):   short/display form, e.g. "Broadcom Security Advisories"
    Returned by getIntegrations; required for the remove mainAction.
  The two forms are NOT interchangeable.  Passing the wrong form to remove
  returns {} silently and does nothing.  This module always looks up the
  correct form from the appropriate endpoint before issuing a mutating call.
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
POLL_TIMEOUT = 300         # seconds before giving up
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

    result: Dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# Admin session (/admin/ — Clarity SPA for pak install)
# ---------------------------------------------------------------------------

class _AdminSession:
    """Encapsulates authentication and request helpers for /admin/ Struts context.

    The /admin/ context is a separate Struts app (Clarity SPA) scoped to
    the pak install/status lifecycle.  Its JSESSIONID is separate from the
    /ui/ JSESSIONID; the two must not be mixed.

    CSRF (secureToken) is obtained from:
      GET /admin/commonJS.action?mainAction=getApplicationGlobalData
    NOT from a cookie — this is the critical difference from the /ui/ flow.

    Documented in context/pak_install_api_exploration.md, steps 1-3.
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
        """Steps 1-2 of context/pak_install_api_exploration.md.

        Step 1: GET /admin/login.action to seed JSESSIONID scoped to /admin.
        Step 2: POST /admin/login.action with credentials; expect "ok".
        Step 3: GET /admin/commonJS.action to obtain secureToken (CSRF).
        """
        if not self._verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        s = requests.Session()
        s.verify = self._verify_ssl

        # Step 1 of context/pak_install_api_exploration.md: seed JSESSIONID
        try:
            s.get(f"https://{self._host}/admin/login.action")
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Cannot connect to {self._host}: {e}. "
                f"Check VCFOPS_HOST and network connectivity."
            ) from e

        # Step 2 of context/pak_install_api_exploration.md: authenticate
        r = s.post(
            f"https://{self._host}/admin/login.action",
            data={"mainAction": "login", "userName": self._user,
                  "password": self._password},
        )
        if r.text.strip() != "ok":
            raise RuntimeError(
                f"Admin login failed for user '{self._user}': {r.text!r}. "
                f"Check VCFOPS_ADMIN and VCFOPS_ADMINPASSWORD."
            )

        # Step 3 of context/pak_install_api_exploration.md: get CSRF token
        r = s.get(
            f"https://{self._host}/admin/commonJS.action",
            params={"mainAction": "getApplicationGlobalData"},
        )
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(
                f"Unexpected response from getApplicationGlobalData "
                f"(status {r.status_code}): {r.text[:200]}"
            )
        csrf = data.get("secureToken")
        if not csrf:
            raise RuntimeError(
                f"secureToken not found in getApplicationGlobalData response. "
                f"Response keys: {list(data.keys())}"
            )

        self._session = s
        self._csrf = csrf

    def logout(self) -> None:
        """Step 11 of context/pak_install_api_exploration.md: clean logout."""
        if self._session is None:
            return
        try:
            self._session.get(
                f"https://{self._host}/admin/login.action",
                params={"mainAction": "logout"},
                allow_redirects=False,
            )
        except Exception:
            pass
        finally:
            self._session = None
            self._csrf = None

    def _form(self, **extra) -> Dict[str, str]:
        """Build a base form dict with currentComponentInfo and secureToken.

        The value 'TODO' for currentComponentInfo matches what the admin SPA
        sends for all automated steps; it is required by the Struts filter but
        the value is not validated server-side (any non-empty string works).
        See context/pak_install_api_exploration.md step 3-9.
        """
        d: Dict[str, str] = {
            "currentComponentInfo": "TODO",
            "secureToken": self._csrf or "",
        }
        d.update(extra)
        return d

    def solution_action(self, **kwargs) -> Dict[str, Any]:
        """POST /admin/solution.action with arbitrary form fields."""
        assert self._session is not None, "call login() first"
        r = self._session.post(
            f"https://{self._host}/admin/solution.action",
            data=self._form(**kwargs),
        )
        r.raise_for_status()
        if not r.text.strip():
            return {}
        return r.json()

    def prepare_upload(self) -> None:
        """Step 3 of context/pak_install_api_exploration.md.

        POST /admin/utility.action mainAction=prepareFileUpload.
        Must be called immediately before the multipart upload.
        """
        assert self._session is not None
        r = self._session.post(
            f"https://{self._host}/admin/utility.action",
            data=self._form(mainAction="prepareFileUpload"),
        )
        r.raise_for_status()
        body = r.json()
        if not body.get("success"):
            raise RuntimeError(f"prepareFileUpload failed: {body}")

    def upload_pak(self, pak_path: Path, force_upload: bool = True,
                   ignore_signature: bool = True) -> Dict[str, Any]:
        """Step 4 of context/pak_install_api_exploration.md.

        POST /admin/admin/services/solution/upload?uploadId=<epoch_ms>
        Multipart body: solution=@<file>.pak plus form fields.

        NOTE: the double /admin/admin/ in the URL is intentional.  The outer
        /admin is the servlet context root; /admin/services/solution/upload is
        the REST sub-path within that context.

        Returns the full JSON response including pakId (admin-side compressed
        form, e.g. "BroadcomSecurityAdvisories-1016").

        force_upload=True and ignore_signature=True are the recommended defaults
        for factory use; the UI sends false/false on fresh installs but the
        factory cannot verify signatures on unsigned development paks.
        """
        assert self._session is not None
        upload_id = str(int(time.time() * 1000))

        with open(pak_path, "rb") as fh:
            files = {
                "solution": (pak_path.name, fh, "application/octet-stream"),
            }
            data = {
                "forceUpload": "true" if force_upload else "false",
                "ignoreSignatureChecking": "true" if ignore_signature else "false",
                "currentComponentInfo": "TODO",
                "secureToken": self._csrf or "",
            }
            r = self._session.post(
                f"https://{self._host}/admin/admin/services/solution/upload",
                params={"uploadId": upload_id},
                files=files,
                data=data,
            )

        r.raise_for_status()
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

    def get_installed_statuses(self) -> Dict[str, Any]:
        """Step 10 poll of context/pak_install_api_exploration.md.

        POST /admin/solution.action mainAction=getLatestInstalledSolutionStatuses.
        Returns the full status dict.  The key fields for polling:
          - pakInstalling (bool): True while any install/uninstall is in flight
          - solutionName (str): name of the most-recently-touched solution
          - isPakRemoved (bool): True after successful uninstall completes
          - solutionStatuses[].state: e.g. "Applied and Cleaned"
          - solutionStatuses[].status: e.g. "Completed"
        """
        return self.solution_action(
            mainAction="getLatestInstalledSolutionStatuses"
        )

    def trigger_install(self, pak_id: str) -> None:
        """Step 9 of context/pak_install_api_exploration.md.

        POST /admin/solution.action mainAction=install pakId=<id> forceContent=true.
        pak_id is the admin-side compressed form (e.g. "BroadcomSecurityAdvisories-1016")
        returned by the upload endpoint.

        Success shape: {} (empty dict, no errorMsg key).
        Failure shape: {"errorMsg": "..."}.
        """
        body = self.solution_action(
            mainAction="install",
            pakId=pak_id,
            forceContent="true",
        )
        _check_json_error(body, f"install mainAction for pakId={pak_id}")


# ---------------------------------------------------------------------------
# UI session (/ui/ — ExtJS SPA for pak uninstall)
# ---------------------------------------------------------------------------

class _UISession:
    """Encapsulates authentication and request helpers for /ui/ Struts context.

    The /ui/ context is the main VCF Ops ExtJS SPA.  It uses a separate
    JSESSIONID from the /admin/ context.  CSRF token comes from the
    base64-decoded OPS_SESSION cookie (NOT from getApplicationGlobalData
    which is an /admin/ endpoint).

    This is the IDENTICAL auth pattern used by UIClient in
    vcfops_packaging/templates/install.py for dashboard/view delete.
    The difference here is that we log in as the admin account (VCFOPS_ADMIN),
    because pak uninstall requires configuration.solutions.delete privilege.

    Documented in context/pak_uninstall_api_exploration.md, step 9-11, and
    context/dashboard_delete_api.md Authentication flow.
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
        """Steps 9-11 of context/pak_uninstall_api_exploration.md.

        Step 9:  GET /ui/login.action?vcf=1 to seed JSESSIONID scoped to /ui.
        Step 10: POST /ui/login.action with full admin credential form.
        Step 11: GET /ui/index.action (no redirect) to receive OPS_SESSION cookie;
                 decode base64(OPS_SESSION) and extract csrfToken.

        IMPORTANT: do NOT follow the 302 redirect from index.action.
        Following it invalidates OPS_SESSION (the redirect target sets
        OPS_SESSION=x with a past expiry).
        """
        if not self._verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        s = requests.Session()
        s.verify = self._verify_ssl

        # Step 9: seed JSESSIONID
        try:
            s.get(f"https://{self._host}/ui/login.action", params={"vcf": "1"})
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Cannot connect to {self._host}: {e}. "
                f"Check VCFOPS_HOST and network connectivity."
            ) from e

        # Step 10: authenticate as admin
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
                f"Check VCFOPS_ADMIN and VCFOPS_ADMINPASSWORD."
            )

        # Step 11: get OPS_SESSION cookie (do NOT follow redirect)
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
                "Check credentials and that the admin account has UI access."
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

    def get_integrations(self) -> list:
        """Step 2 of recommended uninstall flow in pak_uninstall_api_exploration.md.

        POST /ui/solution.action mainAction=getIntegrations.
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
        """Step 4 of context/pak_uninstall_api_exploration.md.

        POST /ui/solution.action mainAction=remove pakId=<short> version=<ver>.

        short_pak_id: the UI-side short form (from getIntegrations .pakId field),
                      e.g. "Broadcom Security Advisories".
                      NOT the admin-side compressed form "BroadcomSecurityAdvisories-1016".

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
    admin_user: Optional[str] = None,
    admin_password: Optional[str] = None,
    skip_ssl_verify: bool = False,
    wait: bool = True,
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> None:
    """Install a .pak file onto a VCF Ops instance.

    Implements the 11-step admin SPA flow from
    context/pak_install_api_exploration.md.

    Steps executed:
      1-3:  AdminSession.login()  (login + CSRF acquisition)
      3:    AdminSession.prepare_upload()
      4:    AdminSession.upload_pak()
      9:    AdminSession.trigger_install()
      10:   Poll getLatestInstalledSolutionStatuses until completed
      11:   AdminSession.logout()

    Steps 5 (upload progress polling), 6 (EULA fetch), 7 (release info),
    8 (finishStage) are omitted: steps 6 and 7 are UI-display-only,
    step 8 is only needed when the wizard is re-opened mid-stage,
    and step 5 is not required when using synchronous single-connection upload.

    Credentials resolve order: CLI flags > env vars.
    """
    p = Path(pak_path)
    if not p.exists():
        _abort(f"Pak file not found: {pak_path}")
    if not p.is_file():
        _abort(f"Not a file: {pak_path}")

    # Resolve credentials (CLI flags > env vars)
    host = host or os.environ.get("VCFOPS_HOST", "").strip()
    admin_user = admin_user or os.environ.get("VCFOPS_ADMIN", "").strip()
    admin_password = admin_password or os.environ.get("VCFOPS_ADMINPASSWORD", "").strip()

    missing = []
    if not host:
        missing.append("VCFOPS_HOST")
    if not admin_user:
        missing.append("VCFOPS_ADMIN")
    if not admin_password:
        missing.append("VCFOPS_ADMINPASSWORD")
    if missing:
        _abort(
            f"Missing required credentials: {', '.join(missing)}.\n"
            f"  Set as env vars or pass as CLI flags (--host, --admin-user, "
            f"--admin-password)."
        )

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

    # Admin session login
    _info(f"[2/6] Authenticating to /admin/ as {admin_user!r} ...")
    admin = _AdminSession(
        host=host,
        user=admin_user,
        password=admin_password,
        verify_ssl=not skip_ssl_verify,
    )
    try:
        admin.login()
    except RuntimeError as e:
        _abort(str(e))

    try:
        # Step 3: prepare upload
        _info("[3/6] Preparing upload slot ...")
        try:
            admin.prepare_upload()
        except RuntimeError as e:
            _abort(str(e))

        # Step 4: upload
        _info(f"[4/6] Uploading {p.name} ...")
        try:
            upload_result = admin.upload_pak(
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

        # Step 9: trigger install
        _info("[5/6] Triggering install ...")
        try:
            admin.trigger_install(pak_id)
        except RuntimeError as e:
            _abort(str(e))

        # Step 10: poll until done
        if wait:
            _info(
                f"[6/6] Waiting for install to complete "
                f"(timeout {poll_timeout}s, poll every {poll_interval}s) ..."
            )
            deadline = time.time() + poll_timeout
            last_state = "(unknown)"
            while time.time() < deadline:
                try:
                    status = admin.get_installed_statuses()
                except Exception as e:
                    _warn(f"Status poll failed (will retry): {e}")
                    time.sleep(poll_interval)
                    continue

                installing = status.get("pakInstalling", True)
                statuses = status.get("solutionStatuses", [])
                state = statuses[0].get("state", "") if statuses else ""
                completion = statuses[0].get("status", "") if statuses else ""
                last_state = (
                    f"pakInstalling={installing}  state={state!r}  "
                    f"status={completion!r}"
                )
                _info(f"      {last_state}")

                if not installing:
                    if state == "Applied and Cleaned" and completion == "Completed":
                        _info(f"OK: Install completed: {server_name} {server_version}")
                        return
                    else:
                        # pakInstalling flipped to false but state does not look clean
                        failed = status.get("installationFailed", False)
                        if failed:
                            _abort(
                                f"Install reported failure. "
                                f"Last status: {last_state}"
                            )
                        # Some paks may reach a different terminal state; treat
                        # pakInstalling=False as completion if no failure flag.
                        _info(
                            f"OK: Install completed (non-standard terminal state). "
                            f"Last status: {last_state}"
                        )
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
                f"[6/6] Install triggered (--wait not set). "
                f"Check Admin UI > Software Updates > Solutions for status."
            )

    finally:
        # Step 11: logout
        admin.logout()


# ---------------------------------------------------------------------------
# Public uninstall function
# ---------------------------------------------------------------------------

def uninstall_pak(
    adapter_kind_or_pak_name: str,
    host: Optional[str] = None,
    admin_user: Optional[str] = None,
    admin_password: Optional[str] = None,
    skip_ssl_verify: bool = False,
    wait: bool = True,
    allow_builtin: bool = False,
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> None:
    """Uninstall a management pack from a VCF Ops instance.

    Implements the recommended uninstall flow from
    context/pak_uninstall_api_exploration.md.

    Steps executed:
      1:  UISession.login()  (/ui/ admin session + OPS_SESSION CSRF)
      2:  UISession.get_integrations()  (resolve name -> short pakId + version)
      3:  isUnremovable guard (MANDATORY — server does NOT enforce this)
      4:  UISession.remove_pak()
      5:  AdminSession.login() + poll getLatestInstalledSolutionStatuses
      6:  Both sessions logged out

    The isUnremovable guard is the most critical safety feature.  Bypassing
    it by sending remove against a built-in pak (vSAN, vCenter, NSX, etc.)
    partially deregisters the adapter kind and leaves the instance in a stuck
    state requiring manual recovery.  See context/pak_uninstall_api_exploration.md
    Safety-critical section for the full incident report.

    Credentials resolve order: CLI flags > env vars.
    """
    # Resolve credentials
    host = host or os.environ.get("VCFOPS_HOST", "").strip()
    admin_user = admin_user or os.environ.get("VCFOPS_ADMIN", "").strip()
    admin_password = admin_password or os.environ.get("VCFOPS_ADMINPASSWORD", "").strip()

    missing = []
    if not host:
        missing.append("VCFOPS_HOST")
    if not admin_user:
        missing.append("VCFOPS_ADMIN")
    if not admin_password:
        missing.append("VCFOPS_ADMINPASSWORD")
    if missing:
        _abort(
            f"Missing required credentials: {', '.join(missing)}.\n"
            f"  Set as env vars or pass as CLI flags (--host, --admin-user, "
            f"--admin-password)."
        )

    # Step 1: UI admin session login
    _info(f"[1/5] Authenticating to /ui/ as {admin_user!r} ...")
    ui = _UISession(
        host=host,
        user=admin_user,
        password=admin_password,
        verify_ssl=not skip_ssl_verify,
    )
    try:
        ui.login()
    except RuntimeError as e:
        _abort(str(e))

    try:
        # Step 2: resolve pak name -> (short UI pakId, version)
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

        # Step 5: poll via admin session
        if wait:
            _info(
                f"[4/5] Waiting for uninstall to complete "
                f"(timeout {poll_timeout}s, poll every {poll_interval}s) ..."
            )
            # Need an admin session for status polling.
            # getLatestInstalledSolutionStatuses lives on /admin/solution.action.
            admin = _AdminSession(
                host=host,
                user=admin_user,
                password=admin_password,
                verify_ssl=not skip_ssl_verify,
            )
            try:
                admin.login()
            except RuntimeError as e:
                _warn(
                    f"Could not open admin session for status polling: {e}. "
                    f"Uninstall was issued — check Admin UI manually."
                )
            else:
                try:
                    _poll_uninstall_completion(
                        admin,
                        display_name,
                        poll_interval=poll_interval,
                        poll_timeout=poll_timeout,
                    )
                finally:
                    admin.logout()
        else:
            _info(
                "[4/5] Uninstall triggered (--wait not set). "
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
      3. entry['adapter_kind'] — adapter kind key (e.g. mpb_broadcom_security_advisories)

    Returns the matched entry dict, or None if not found.
    """
    query = adapter_kind_or_pak_name.strip().lower()
    for entry in installed:
        if (
            str(entry.get("pakId", "")).strip().lower() == query
            or str(entry.get("name", "")).strip().lower() == query
            or str(entry.get("adapter_kind", "")).strip().lower() == query
        ):
            return entry
    return None


def _poll_uninstall_completion(
    admin: _AdminSession,
    target_name: str,
    poll_interval: int,
    poll_timeout: int,
) -> None:
    """Poll /admin/solution.action getLatestInstalledSolutionStatuses until
    the target pak disappears from the status grid or isPakRemoved=True.

    Corresponds to step 5 of the recommended uninstall flow in
    context/pak_uninstall_api_exploration.md.

    Completion signals:
      - response.solutionName != target_name  (pak no longer the last-touched)
      - response.isPakRemoved == True
      AND pakInstalling == False in both cases.

    NOTE: pakInstalling=True covers both install AND uninstall in-progress;
    the flag name is misleading but this is the documented server behavior.
    During uninstall, state stays "Applied and Cleaned" while pakInstalling=True.
    """
    deadline = time.time() + poll_timeout
    last_state = "(unknown)"
    target_lower = target_name.strip().lower()

    while time.time() < deadline:
        try:
            status = admin.get_installed_statuses()
        except Exception as e:
            _warn(f"Status poll failed (will retry): {e}")
            time.sleep(poll_interval)
            continue

        installing = status.get("pakInstalling", True)
        current_name = str(status.get("solutionName", "")).strip()
        is_removed = bool(status.get("isPakRemoved", False))
        statuses = status.get("solutionStatuses", [])
        state = statuses[0].get("state", "") if statuses else ""
        last_state = (
            f"pakInstalling={installing}  solutionName={current_name!r}  "
            f"isPakRemoved={is_removed}  state={state!r}"
        )
        _info(f"      {last_state}")

        if not installing:
            # Grid reverts to the previously-touched pak after uninstall;
            # completion is confirmed when the target name is no longer active.
            if (
                is_removed
                or current_name.strip().lower() != target_lower
            ):
                _info(f"OK: Uninstall completed: {target_name}")
                return
            else:
                # pakInstalling=False but pak still appears as current —
                # could be a transient grid state; wait one more cycle.
                _info("      (pak still appears current — waiting one more poll)")

        time.sleep(poll_interval)

    _abort(
        f"Uninstall timed out after {poll_timeout}s. "
        f"Last known status: {last_state}\n"
        f"The uninstall may still be running on the server. "
        f"Check Admin UI > Software Updates > Solutions."
    )
