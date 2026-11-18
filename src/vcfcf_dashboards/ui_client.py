"""UI session client for VCF Ops dashboard/view delete operations.

These operations use the Struts/.action + Ext.Direct RPC layer that backs
the VCF Operations web console, NOT the Suite API. The two session systems
are completely independent; a Suite API bearer token cannot authenticate to
*.action endpoints.

AUTH FLOW
---------
1. GET /ui/login.action?vcf=1  →  initial JSESSIONID cookie
2. POST /ui/login.action (form-encoded creds)  →  updated JSESSIONID, body "ok"
3. GET /ui/index.action (do NOT follow 302)  →  OPS_SESSION cookie (base64 JSON)
   Extract csrfToken (== secureToken) from the decoded JSON.

SUPPORTABILITY CAVEAT
---------------------
These are **unsupported internal UI endpoints**, not part of any public API
contract. They can change between VCF Ops releases without notice. Tested
against VCF Operations 9.0.2.0 build 25137838.

Credentials are read from environment variables:
  VCFOPS_HOST, hostname (no scheme)
  VCFOPS_USER, username
  VCFOPS_PASSWORD, password
  VCFOPS_AUTH_SOURCE, auth source id (default: localItem for local accounts)
  VCFOPS_VERIFY_SSL, set to "true" to enable SSL verification (default: false)
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

import requests

from vcfcf_common._env import load_dotenv, resolve_profile_credentials
from vcfcf_common.client import new_session


class UIClientError(RuntimeError):
    """A UI action failed. ``status`` and ``body`` carry the server's HTTP
    status and raw answer when the failure was the server's reply (None
    otherwise), so a caller can report what the server said."""

    def __init__(self, message: str = "", *, status: int | None = None,
                 body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body
        #: ``(form, status, body)`` per request form sent, for the
        #: association call (#260); empty otherwise.
        self.answers: list = []


#: associateResourceKindDashboards request forms, in the order tried (#260).
ASSOCIATION_FORMS = ("two-map", "single-map")


def association_params(form: str, assigned: dict, reset: dict) -> dict:
    """The form fields that carry ``assigned`` and ``reset`` in one request
    form (see :meth:`VCFOpsUIClient.associate_resource_kind_dashboards`).

    ``"two-map"``: ``assignedAssociations`` and ``resetAssociations``, the
    reset value the plain default template name. ``"single-map"``: one
    ``dashboardAssociations`` map; a reset entry becomes
    ``<defaultTemplateName>_::_null``, which the pre-9.1 action reads as
    "remove this kind's association" (its SPA sends
    ``templateName + "_::_" + tabId`` with a null tabId).
    """
    if form == "two-map":
        return {
            "assignedAssociations": json.dumps(dict(assigned)),
            "resetAssociations": json.dumps(dict(reset)),
        }
    if form == "single-map":
        merged = dict(assigned)
        merged.update({k: f"{v}_::_null" for k, v in reset.items()})
        return {"dashboardAssociations": json.dumps(merged)}
    raise ValueError(f"unknown association form {form!r}")


def is_true(value) -> bool:
    """A listing flag as a bool (``True`` or the string ``"true"``)."""
    return value is True or str(value).strip().lower() == "true"


def listed_owner_differs(entry: dict, session_user: str | None) -> bool:
    """True when the entry's listed ``owner`` is set and is not *session_user*
    (case-insensitive). False when either is unknown."""
    owner = str(entry.get("owner") or "").strip()
    return bool(owner and session_user
                and owner.lower() != session_user.strip().lower())


#: Text added wherever a delete is reported "still listed": the verification
#: limit measured on 9.1.1 (investigations/dashboard_delete_non_owner_2026-11-18.md Q5).
SAME_ID_COPY_NOTE = (
    "a copy under the same id owned by another account also produces this: when "
    "two owners hold one id, each account lists only the other's copy, so deleting "
    "the session's own copy leaves its listing unchanged. A DASHBOARDS content "
    "export, or a listing as the owner, settles it")


def dashboard_delete_blockers(entry: dict, session_user: str | None) -> list[str]:
    """Why a ``deleteTab`` by *session_user* is expected to be ignored for this
    ``getDashboardList`` entry, or ``[]``.

    Measured on 9.1.1 (``investigations/dashboard_delete_non_owner_2026-11-18.md``):
    ownership decides; only the owner's ``deleteTab`` deletes, and a
    non-owner's (the built-in admin account included) is an HTTP 200 no-op.
    The lock does not: ``locked``, ``edit`` and ``shared`` are per-viewer,
    and ``locked: true`` is how a non-owner sees a dashboard shared with it;
    an owner deletes a dashboard everyone else sees as locked. So only the
    listed owner differing from the session user is reported. 8.18.7 and
    9.0.2 not measured. *session_user* comes from ``/api/auth/currentuser``;
    when it is unknown the owner cannot be compared and nothing is reported.
    """
    if not listed_owner_differs(entry, session_user):
        return []
    owner = str(entry.get("owner") or "").strip()
    return [f"listed owner {owner!r} differs from session user {session_user!r}; on "
            f"9.1.1 only the owner's delete deletes (8.18.7 and 9.0.2 not measured)"]


def _dashboards_from_body(resp) -> list[dict]:
    """The ``dashboards`` list of a ``getDashboardList`` answer, strictly.

    Raises :class:`UIClientError` when the body is not JSON, is not an
    object, has no ``dashboards`` key, or the key is not a list: a listing
    used to verify a delete must never degrade to "empty".
    """
    try:
        body = resp.json()
    except ValueError as exc:
        raise UIClientError(f"getDashboardList answered non-JSON: {exc}",
                            status=getattr(resp, "status_code", None),
                            body=(getattr(resp, "text", "") or "")[:500]) from None
    if not isinstance(body, dict) or "dashboards" not in body:
        raise UIClientError("getDashboardList answer has no 'dashboards' key",
                            status=getattr(resp, "status_code", None),
                            body=(getattr(resp, "text", "") or "")[:500])
    if not isinstance(body["dashboards"], list):
        raise UIClientError("getDashboardList 'dashboards' is not a list",
                            status=getattr(resp, "status_code", None),
                            body=(getattr(resp, "text", "") or "")[:500])
    return body["dashboards"]


@dataclass
class DashboardDeleteResult:
    """Outcome of :meth:`VCFOpsUIClient.delete_dashboards_verified`, per id.

    ``deleted``: listed before the delete, absent after it, with the
    after-listing trusted. ``remaining``: the after-listing entry of each
    target still listed. ``unlisted``: not listed before the delete
    (already gone, or not visible to the session account). ``unverifiable``:
    listed before, but the after-listing could not be read or cannot be
    trusted (*note* says why). Only ``deleted`` is success.
    """

    deleted: list = field(default_factory=list)       # [(id, name)]
    remaining: list = field(default_factory=list)     # [listing entry]
    unlisted: list = field(default_factory=list)      # [(id, name)]
    unverifiable: list = field(default_factory=list)  # [(id, name)]
    note: str = ""

    @property
    def ok(self) -> bool:
        return not (self.remaining or self.unlisted or self.unverifiable)


#: Marker of the generic Ext error panel Struts renders for an exception
#: in a ``.action`` (the body of the refused binds on 9.0.2 and 8.18.7,
#: 2026-10-24: ``var errorPanel = new Ext.Panel(...)``).
ERROR_PANEL_MARKER = "errorPanel"


def is_wrong_form_answer(status: int, text: str) -> bool:
    """True only for the answer a build gives to the request form it does
    not read: HTTP 200 with the generic error panel (the NPE on the first
    line of the action, before any write)."""
    return status == 200 and ERROR_PANEL_MARKER in (text or "")


# The Struts read actions (resourceKind.action and friends) answer the
# generic error panel unless the request identifies itself as XHR.
_UI_XHR_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


class VCFOpsUIClient:
    """Thin UI-session client for dashboard and view delete operations.

    Instantiate via :meth:`from_env` or pass credentials directly. Call
    :meth:`login` before any operation; call :meth:`logout` when done (or
    use as a context manager).

    Example::

        with VCFOpsUIClient.from_env() as ui:
            dashboards = ui.list_dashboards()
            ui.delete_dashboards([("uuid-1", "My Dashboard")])
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        auth_source: str = "localItem",
        verify_ssl: bool = False,
    ):
        self._host = host
        self._username = username
        self._password = password
        self._auth_source = auth_source
        self._verify_ssl = verify_ssl
        self._session: requests.Session | None = None
        self._csrf_token: str | None = None
        self._tid = 1  # monotonically increasing Ext.Direct transaction id
        #: The associateResourceKindDashboards request form this instance
        #: answered ``ok`` to (``"two-map"`` or ``"single-map"``); None
        #: until a call succeeds (#260).
        self.association_form: str | None = None

    @classmethod
    def from_env(cls, profile: str | None = None, *, default_profile: str = "devel") -> "VCFOpsUIClient":
        """Construct from the active credential profile.

        Profile resolution order: ``profile`` arg > ``VCFOPS_PROFILE`` env var
        > ``default_profile`` arg > ``"devel"``.

        Delete operations (which this client is used for) default to the
        ``devel`` profile since they are mutating.
        """
        try:
            creds = resolve_profile_credentials(profile, default=default_profile)
        except ValueError as e:
            raise UIClientError(str(e)) from None
        # VCFOPS_AUTH_SOURCE for Suite API is a display name ("Local");
        # for the UI form it must be the authSourceId value ("localItem" for
        # local accounts, or a UUID for SSO/LDAP). Map the common Suite API
        # display name to the UI form value.
        raw_source = creds.auth_source.strip()
        if not raw_source or raw_source.lower() == "local":
            auth_source = "localItem"
        else:
            auth_source = raw_source
        return cls(
            host=creds.host,
            username=creds.user,
            password=creds.password,
            auth_source=auth_source,
            verify_ssl=creds.verify_ssl,
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------
    def __enter__(self) -> "VCFOpsUIClient":
        self.login()
        return self

    def __exit__(self, *_) -> None:
        self.logout()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Authenticate to the VCF Ops UI and capture the CSRF token.

        Three-step flow documented in knowledge/context/api-surface/dashboard_delete_api.md:
        1. GET /ui/login.action?vcf=1, seeds JSESSIONID
        2. POST /ui/login.action (form creds), validates credentials
        3. GET /ui/index.action (no redirect), OPS_SESSION cookie with csrfToken

        The OPS_SESSION cookie is base64-encoded JSON. It is set on the 302
        response from step 3 but CLEARED if the redirect is followed, so we
        must capture it without following the redirect.
        """
        # new_session: an explicit verify_ssl=False must beat REQUESTS_CA_BUNDLE (#174).
        s = new_session(self._verify_ssl)

        # Step 1: seed JSESSIONID
        s.get(f"https://{self._host}/ui/login.action", params={"vcf": "1"})

        # Step 2: login with credentials
        resp = s.post(
            f"https://{self._host}/ui/login.action",
            data={
                "mainAction": "login",
                "userName": self._username,
                "password": self._password,
                "authSourceId": self._auth_source,
                "authSourceName": "Local Account",
                "authSourceType": "",
                "forceLogin": "false",
                "timezone": "0",
                "languageCode": "us",
            },
        )
        if resp.text.strip() != "ok":
            raise UIClientError(f"UI login failed: {resp.text!r}")

        # Step 3: hit index.action WITHOUT following the 302 redirect.
        # The OPS_SESSION cookie is set on the 302 response and cleared on
        # the redirect target response.
        resp = s.get(
            f"https://{self._host}/ui/index.action",
            allow_redirects=False,
        )
        ops_cookie = resp.cookies.get("OPS_SESSION") or s.cookies.get("OPS_SESSION")
        if not ops_cookie:
            raise UIClientError(
                "OPS_SESSION cookie not received after /ui/index.action, "
                "check credentials and auth source"
            )
        try:
            ops_data = json.loads(base64.b64decode(ops_cookie))
        except Exception as exc:
            raise UIClientError(f"Failed to decode OPS_SESSION cookie: {exc}") from exc
        csrf_token = ops_data.get("csrfToken")
        if not csrf_token:
            raise UIClientError("csrfToken not found in OPS_SESSION payload")

        self._session = s
        self._csrf_token = csrf_token

    def logout(self) -> None:
        """Invalidate the UI session. Safe to call even if not logged in."""
        if self._session is None:
            return
        try:
            self._session.get(
                f"https://{self._host}/ui/login.action",
                params={"mainAction": "logout"},
                allow_redirects=False,
            )
        except Exception:
            pass  # best-effort
        finally:
            self._session = None
            self._csrf_token = None

    def _require_auth(self) -> tuple[requests.Session, str]:
        if self._session is None or self._csrf_token is None:
            raise UIClientError("Not logged in, call login() first")
        return self._session, self._csrf_token

    # ------------------------------------------------------------------
    # Dashboard operations
    # ------------------------------------------------------------------
    def list_dashboards(self) -> list[dict]:
        """Return all dashboards visible to the authenticated user.

        Uses unsupported UI endpoint POST /ui/dashboard.action with
        mainAction=getDashboardList. Each entry has at minimum:
          id, name, description, locked, owner, shared, editable; 9.1.1
          also carries ``ownerId`` (the owner's user UUID) and ``edit``.
          On 9.1.1 ``locked``, ``edit`` and ``shared`` are per-viewer
          (``locked: true``: another account owns it and shared it with
          you) and ``editable`` was false for owner and non-owner alike.
          Field names on 8.18.7 and 9.0.2 not recorded.

        WARNING: unsupported internal endpoint; may change between releases.
        """
        return self._post_dashboard_list().json().get("dashboards") or []

    def list_dashboards_strict(self) -> list[dict]:
        """:meth:`list_dashboards`, but raises :class:`UIClientError` on an
        answer it cannot read (non-JSON, no ``dashboards`` list) instead of
        returning ``[]``. Use it wherever absence is evidence."""
        return _dashboards_from_body(self._post_dashboard_list())

    def _post_dashboard_list(self):
        s, csrf = self._require_auth()
        resp = s.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "getDashboardList",
                "secureToken": csrf,
                "currentComponentInfo": "TODO",
                "globalDate": json.dumps({"dateRange": "last6Hour"}),
            },
            headers=_UI_XHR_HEADERS,
        )
        resp.raise_for_status()
        return resp

    def delete_dashboards(self, dashboards: list[tuple[str, str]]) -> dict:
        """Delete one or more dashboards by (uuid, name) tuples.

        Multiple dashboards can be deleted in a single call. Deleting a
        non-existent UUID is a silent no-op (returns HTTP 200 with the
        full dashboard config).

        HTTP 200 is not a delete: on 9.1.1 only the owner's ``deleteTab``
        deletes; a non-owner's (the built-in admin account included) answers
        200 with the full config and deletes nothing. Use
        :meth:`delete_dashboards_verified` wherever the outcome matters.
        From an account that had never opened the UI, the first calls
        answered 200 with the Struts error panel instead of JSON, so the
        ``resp.json()`` below raises (cause not isolated). Measured but
        not implemented: an administrator removes another account's
        dashboard with ``dashboardShare.action`` ``discardDashboards``
        (``investigations/dashboard_delete_non_owner_2026-11-18.md``).

        Unverified request-shape differences from :meth:`list_dashboards`:
        no ``X-Requested-With`` header, and ``currentComponentInfo`` is the
        placeholder ``"TODO"``. The same request deleted dashboards the
        session account owned on 8.18.7, 9.0.2 and 9.1.1, so neither is
        known to matter.

        WARNING: unsupported internal endpoint; may change between releases.

        Args:
            dashboards: list of (uuid, display_name) tuples.

        Returns:
            The raw JSON response body (full dashboard configuration).
        """
        s, csrf = self._require_auth()
        tab_ids = [{"tabId": uid, "tabName": name} for uid, name in dashboards]
        resp = s.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "deleteTab",
                "tabIds": json.dumps(tab_ids),
                "secureToken": csrf,
                "currentComponentInfo": "TODO",
                "globalDate": json.dumps({"dateRange": "last6Hour"}),
            },
        )
        resp.raise_for_status()
        return resp.json()

    @property
    def username(self) -> str:
        """The login name this UI session signed in with (the credential
        profile's user). Not the identity to compare a listed ``owner``
        with: use ``/api/auth/currentuser``."""
        return self._username

    def delete_dashboards_verified(
        self, dashboards: list[tuple[str, str]], before: list[dict] | None = None,
    ) -> DashboardDeleteResult:
        """Delete *dashboards*, then re-list and say, per id, what happened.

        *before* is a strict listing (:meth:`list_dashboards_strict`) taken
        before the delete; listed now when None. Every target is sent. A
        target absent from *before* is ``unlisted``: its absence afterwards
        proves nothing. When the after-listing cannot be read, or has lost
        a dashboard that was listed before and was not a target, it is not
        trusted and every listed target is ``unverifiable``, never
        ``deleted``. Ids compare case-insensitively.

        Limit (9.1.1): when another owner holds a second record under the
        same id, each account lists only the other's copy; deleting the
        session's own copy leaves its listing unchanged, so the target is
        reported ``remaining`` although something was deleted. The error
        is in the safe direction: a surviving dashboard is never reported
        deleted. A DASHBOARDS export or a listing as the owner settles it
        (:data:`SAME_ID_COPY_NOTE`).
        """
        if not dashboards:
            return DashboardDeleteResult()
        if before is None:
            before = self.list_dashboards_strict()
        before_ids = {str(d.get("id") or "").lower() for d in before if d.get("id")}
        target_ids = {str(uid).lower() for uid, _ in dashboards}
        result = DashboardDeleteResult()
        self.delete_dashboards(list(dashboards))
        listed = [(uid, name) for uid, name in dashboards if str(uid).lower() in before_ids]
        result.unlisted = [(uid, name) for uid, name in dashboards
                           if str(uid).lower() not in before_ids]
        try:
            after_list = self.list_dashboards_strict()
        except (UIClientError, requests.RequestException) as exc:
            result.unverifiable = listed
            result.note = f"the listing after the delete could not be read: {exc}"
            return result
        after = {str(d.get("id") or "").lower(): d for d in after_list if d.get("id")}
        vanished = sorted(before_ids - target_ids - set(after))
        if vanished:
            result.unverifiable = listed
            result.note = (f"the listing after the delete lost {len(vanished)} dashboard(s) "
                           f"that were not targets, so it cannot be trusted")
            return result
        for uid, name in listed:
            entry = after.get(str(uid).lower())
            if entry is None:
                result.deleted.append((uid, name))
            else:
                result.remaining.append(entry)
        return result

    # ------------------------------------------------------------------
    # Summary-tab association (Manage Summary Dashboards)
    # ------------------------------------------------------------------
    # All three calls are the undocumented Struts UI layer documented in
    # knowledge/context/api-surface/summary_dashboard_assignment.md. No
    # Suite API exists for any of them. They may change between releases.
    # Parameter names come from the disassembled DashboardAction: the
    # 2026-08-25 note in that file (confirmed live on 9.1.1)
    # and the 2026-10-24 per-build read for 9.0.2 and 8.18 (issue #260).

    def get_resource_kind_list(self, adapter_kind: str, limit: int = 2000) -> dict:
        """Return the raw ``getResourceKindList`` answer for one adapter kind
        with detail-page mappings appended.

        The body carries ``resourceKindList[]`` (each entry with its
        ``resourceKindTemplate``, the current Summary-tab assignment label)
        and a top-level ``defaultTemplateName``.
        """
        s, csrf = self._require_auth()
        resp = s.get(
            f"https://{self._host}/ui/resourceKind.action",
            params={
                "mainAction": "getResourceKindList",
                "appendDetailPageMappings": "true",
                "adapterKindId": adapter_kind,
                "searchField": "name",
                "searchText": "",
                "page": "1",
                "start": "0",
                "limit": str(limit),
                "secureToken": csrf,
            },
            headers=_UI_XHR_HEADERS,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise UIClientError(
                f"getResourceKindList({adapter_kind!r}) did not return JSON: {resp.text[:200]!r}"
            ) from exc

    def associate_resource_kind_dashboards(
        self, assigned: dict[str, str], reset: dict[str, str] | None = None
    ) -> None:
        """Bulk-write Summary-tab assignments in whichever form the build reads.

        ``assigned`` maps ``"resourceKind_<resourceKindId>"`` to
        ``"<dashboardName>_::_<dashboardUuid>"`` (bind). ``reset`` maps the
        same key to the kind's plain ``defaultTemplateName`` ("Use
        Default"). The server materializes an independent template COPY of
        each bound dashboard and deletes the kind's previous copy in the
        same call; the new copy's UUID is what ``get_summary_tab_id``
        returns afterwards.

        Two request forms exist (issue #260; bytecode and SPA read per
        build, knowledge/context/api-surface/summary_dashboard_assignment.md
        "Two request forms"):

        - ``"two-map"`` (9.1.1 Build 25794169):
          ``assignedAssociations`` plus ``resetAssociations``, both always
          sent (``{}`` when empty); reset values are the plain name.
        - ``"single-map"`` (9.0.2 Build 25429562, 8.18.6 Build 25423535):
          one ``dashboardAssociations`` map; a reset entry's value is
          ``<defaultTemplateName>_::_null``.

        A build NPEs on the first line of the action when the parameter it
        reads is absent, before any lookup or write, and answers HTTP 200
        with the generic Ext error panel. Only that answer (HTTP 200 and the
        ``errorPanel`` marker in the body) is the proven "wrong form,
        nothing written" signal, so only that answer sends the other form.
        Any other answer that is not ``ok`` (a 4xx or 5xx, a login page, a
        proxy timeout the server may have completed) raises at once,
        without a second write. The call goes out in the two-map form first
        (the form proven live on 9.1.1); the form that answered
        ``ok`` is remembered on the client (``association_form``) and tried
        first next time. The version string is not used: the 9.1.1
        appliance's lastbuildversion.txt reads 9.0.0.0.

        Raises :class:`UIClientError` when no form answers ``ok``. Its
        ``answers`` lists ``(form, status, body)`` per form sent; ``status``
        is the first form's status, and ``body`` carries each form's answer
        (whitespace collapsed, form-labelled), so a caller quoting the
        server shows every refusal, not only the last. A non-``ok`` answer
        does not prove nothing was written (the single-map success body is
        unread on 9.0.2 and 8.18): callers read ``getSummaryTabId`` back
        before calling it a refusal.
        """
        assigned = dict(assigned or {})
        reset = dict(reset or {})
        both = sorted(set(assigned) & set(reset))
        if both:
            raise ValueError(f"a kind cannot be bound and reset in one call: {both}")
        s, csrf = self._require_auth()
        forms = [self.association_form] if self.association_form else []
        forms += [f for f in ASSOCIATION_FORMS if f not in forms]
        answers = []
        for form in forms:
            data = {"mainAction": "associateResourceKindDashboards"}
            data.update(association_params(form, assigned, reset))
            data["secureToken"] = csrf
            resp = s.post(
                f"https://{self._host}/ui/dashboard.action",
                data=data,
                headers=_UI_XHR_HEADERS,
            )
            if resp.status_code < 400 and resp.text.strip() == "ok":
                self.association_form = form
                return
            answers.append((form, resp.status_code, resp.text))
            if not is_wrong_form_answer(resp.status_code, resp.text):
                break  # not the proven NPE panel: never send a second write
        tried = ", ".join(f"{form} HTTP {status}" for form, status, _ in answers)
        body = " | ".join(
            f"[{form}] {' '.join(str(text or '').split())[:120]}" for form, _, text in answers)
        exc = UIClientError(
            f"associateResourceKindDashboards was not answered ok ({tried}): {body[:300]!r}",
            status=answers[0][1], body=body,
        )
        exc.answers = answers
        raise exc

    def get_summary_tab_id(self, resource_kind_id: str) -> dict:
        """Return the raw ``getSummaryTabId`` answer for a resource kind id.

        Shapes: ``{"isDashboard": false}`` (no association; the server
        drops the ``tabId`` key entirely when it is null, so callers must
        treat a MISSING key as null), ``{"tabId": "<uuid>",
        "isDashboard": true}`` (dashboard-backed), or ``{"tabId":
        "<non-uuid>", "isDashboard": false, "pluginExist": <bool>}``
        (legacy plugin page)."""
        s, csrf = self._require_auth()
        resp = s.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "getSummaryTabId",
                "resourceKindId": resource_kind_id,
                "traversalSpecId": "",
                "resourceKindType": "",
                "resourceId": "",
                "secureToken": csrf,
            },
            headers=_UI_XHR_HEADERS,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise UIClientError(
                f"getSummaryTabId({resource_kind_id!r}) did not return JSON: {resp.text[:200]!r}"
            ) from exc

    def get_dashboard_config(self, tab_id: str, *, is_template: bool = False) -> dict:
        """Return the raw ``getDashboardConfig`` answer for one tab.

        ``{"dashboardConfig": {"tabConfigs": [{"id", "name", "isLoading",
        "widgets": [{"key", "isLoading", ...}]}], "widgetInteractions"},
        "interactionTypes"}``. A Summary template clone (the copy a
        resource kind's Summary tab renders) is readable only with
        ``is_template=True``; ``isLoading`` on the tab and on each widget is
        the one signal that holds on 9.0.2 and 9.1.1 alike (read on devel
        9.0.2, 2026-10-24; knowledge/context/api-surface/summary_dashboard_pak_binding.md).
        """
        s, csrf = self._require_auth()
        resp = s.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "getDashboardConfig",
                "tabId": tab_id,
                "isTemplate": "true" if is_template else "false",
                "secureToken": csrf,
            },
            headers=_UI_XHR_HEADERS,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise UIClientError(
                f"getDashboardConfig({tab_id!r}) did not return JSON: {resp.text[:200]!r}"
            ) from exc

    # ------------------------------------------------------------------
    # View operations
    # ------------------------------------------------------------------
    def list_views(self) -> list[dict]:
        """List all view definitions via Ext.Direct RPC.

        Uses viewServiceController.getGroupedViewDefinitionThumbnails
        (no parameters), returns a grouped list of all views the user
        can see.

        WARNING: unsupported internal endpoint; may change between releases.
        """
        s, csrf = self._require_auth()
        tid = self._next_tid()
        resp = s.post(
            f"https://{self._host}/ui/vcops/services/router",
            json=[{
                "action": "viewServiceController",
                "method": "getGroupedViewDefinitionThumbnails",
                "data": [],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": csrf},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise UIClientError(
                f"getGroupedViewDefinitionThumbnails failed: {result[0].get('message')}"
            )
        return result[0].get("result") or []

    def delete_view(self, view_uuid: str, view_name: str) -> None:
        """Delete a single view by UUID+name via Ext.Direct RPC.

        Unlike dashboard delete, non-existent view UUIDs return an exception
        response (HTTP 200 with type=exception in body). This method raises
        UIClientError in that case.

        NOTE: secureToken is sent as an HTTP *header* for Ext.Direct
        endpoints, NOT as a form/body param (unlike Struts .action endpoints).

        WIRE FORMAT: data must be an array containing one dict whose
        ``viewDefIds`` value is a JSON-stringified array of {id, name} objects.
        Sending a bare UUID string (the old shape) causes the handler to crash
        and return {"type":"exception","message":"Internal server error."}.
        See knowledge/context/api-surface/dashboard_delete_api.md "2026-04-11 correction".

        WARNING: unsupported internal endpoint; may change between releases.

        Args:
            view_uuid: the UUID of the view definition to delete.
            view_name: the display name of the view (required by the handler).

        Raises:
            UIClientError: if the server returns an exception (e.g. view does
                not exist or is a system view that cannot be deleted).
        """
        s, csrf = self._require_auth()
        tid = self._next_tid()
        view_def_ids = json.dumps([{"id": view_uuid, "name": view_name}])
        resp = s.post(
            f"https://{self._host}/ui/vcops/services/router",
            json=[{
                "action": "viewServiceController",
                "method": "deleteView",
                "data": [{"viewDefIds": view_def_ids}],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": csrf},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise UIClientError(
                f"deleteView {view_uuid!r} failed: {result[0].get('message')}"
            )

    def _next_tid(self) -> int:
        tid = self._tid
        self._tid += 1
        return tid
