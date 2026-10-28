"""After a pak install: start the accounts the upgrade left FAILED.

Lesson ``knowledge/lessons/remote-collector-upgrade-start-race.md``. On a
remote collector or Cloud Proxy, a pak install stops the pak's adapter
instances, pushes the new jar, and sends Start monitoring about 30 s later,
before the collector has loaded the new adapter. Each start is rejected
("Unknown adapter type is specified in collector configuration"), every
account of that adapter kind sits at ``resourceState`` FAILED, and nothing
retries. The collector loads the jar lazily, about 90 to 120 s after the
start task (prod 9.1.1, devel_9_1). Reproduced 2026-10-13, -14, -15, -16 and
2026-10-28 (compliance 0.0.0.102 on devel_9_1: all three accounts FAILED, a
manual start per account a minute later fixed them).

So ``install`` does what the lesson said to do by hand:

1. Before the upload, read every adapter instance of the pak's adapter
   kinds and its ``resourceState`` (:func:`read_accounts`).
2. After the install verifies, poll those states every
   :data:`POLL_S` seconds. For the first :data:`START_DELAY_S` seconds it
   only watches: a start sent before the collector loads the jar fails the
   same way, and an account still reading STARTED right after the install
   may not have been stopped yet.
3. Once that delay has passed, send ``PUT /api/adapters/{id}/monitoringstate/start``
   to each account that reads FAILED, STOPPED or NONE, by what it read
   before the install:

   - STARTED, STARTING, UPDATING or FAILED (a *known* prior, the account was
     meant to collect): started.
   - STOPPED, STOPPING, MAINTAINED or MAINTAINED_MANUAL (a *held* prior, the
     user's choice): never started.
   - anything else (UNKNOWN, NONE, NOT_EXISTING, REMOVING, no status entry,
     a new account, or the read before the install failed): started only
     when FAILED, which is never a user's choice.

   An account that was sent a start and reads FAILED again at least
   :data:`RETRY_AFTER_S` later gets a second start (at most
   :data:`MAX_STARTS`): nothing establishes that the install's verify
   follows the server's start task by enough for the first start to clear
   the jar load. A start is only ever sent on a reading taken that poll.
4. Keep polling until every account is settled, or :data:`TIMEOUT_S` runs
   out, and print each account's final state. When the last read failed
   the verdict is ``ACCOUNTS UNCHECKED`` (state as of the last good read),
   never a failure built from stale data. A 401/403 stops the polling.

Wire shapes (read on devel_9_1, 9.1, 2026-10-28):
``GET /api/adapters?adapterKindKey=<kind>`` answers
``{"adapterInstancesInfoDto": [{"id", "resourceKey": {"name", ...},
"collectorId", ...}]}`` (an empty list for an unknown kind, still 200). The
adapter instance carries no state; it is a resource with the same id, and
``GET /api/resources?resourceId=<id>&resourceId=<id>...`` returns
``resourceList[].resourceStatusStates[]``, one entry whose
``adapterInstanceId`` is the instance's own id, carrying ``resourceState``
(STARTED, FAILED, ...), ``resourceStatus`` (DATA_RECEIVING, ...) and
``statusMessage``.

The live half takes an injected Suite API client (anything with
``_request(method, path, **kw)`` returning a ``requests``-like response) and
injected ``sleep``/``clock``, so the flow is unit-testable with fakes.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

#: Seconds after the install verifies before any start is sent. The
#: collector loaded the jar about 2 minutes after the start task on 9.1.
START_DELAY_S = 120
#: Seconds after the install verifies before the check gives up: the shared
#: deadline for every read, start and sleep. One overrun remains: a session
#: token rejected near the end makes ``VCFOpsClient._request`` re-acquire
#: (``auth_timeout``) and retry the call, 30 s each, so the worst case is
#: about 360 s.
TIMEOUT_S = 300
#: Seconds between state reads.
POLL_S = 15
#: Seconds after a start before an account that reads FAILED again gets
#: its second (and last) start.
RETRY_AFTER_S = 60
#: Starts per account, at most.
MAX_STARTS = 2
#: Per-request timeout (seconds) on every Suite API call: the read before
#: the upload must not hang the install, and the watch must stay near
#: :data:`TIMEOUT_S`.
REQUEST_TIMEOUT_S = 30

#: Exit code when an account that should collect is not STARTED at the end.
#: Same code as the dashboard checks: the pak installed, a post-install
#: check failed, do not reinstall.
ACCOUNTS_NOT_STARTED_RC = 3

#: States that mean the user chose not to collect: an account in one of
#: these before the install is never started by the installer.
HELD_STATES = frozenset({"STOPPED", "STOPPING", "MAINTAINED", "MAINTAINED_MANUAL"})
#: States before the install that say the account was meant to collect. Any
#: prior outside this set and :data:`HELD_STATES` is unknown intent.
KNOWN_PRIOR_STATES = frozenset({"STARTED", "STARTING", "UPDATING", "FAILED"})
#: States after the install that get a start.
RESTARTABLE_STATES = frozenset({"FAILED", "STOPPED", "NONE"})
#: States that are on their way somewhere: never settled.
TRANSITIONAL_STATES = frozenset({"STARTING", "STOPPING", "UPDATING"})
#: The only state that counts as collecting.
OK_STATE = "STARTED"
#: What :func:`read_accounts` records when an instance has no status entry.
UNREADABLE_STATE = "UNKNOWN"


class AuthRefused(RuntimeError):
    """The Suite API refused the credentials (401/403): retrying will not help."""


@dataclass
class Account:
    """One adapter instance (an "account") and its collection state."""
    id: str
    name: str
    adapter_kind: str
    collector_id: Optional[object] = None
    state: str = UNREADABLE_STATE
    status: str = ""
    message: str = ""


def _ok_json(resp, what: str) -> dict:
    code = getattr(resp, "status_code", None)
    if code in (401, 403):
        raise AuthRefused(f"{what} returned HTTP {code}")
    if code != 200:
        text = str(getattr(resp, "text", ""))[:300]
        raise RuntimeError(f"{what} returned HTTP {code}: {text}")
    body = resp.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{what} answered a {type(body).__name__}, not an object")
    return body


class DeadlineReached(RuntimeError):
    """The watch's shared budget ran out before a request could be sent."""


#: A request is not sent with less than this many seconds of budget left.
MIN_REQUEST_S = 1.0


def _request_timeout(timeout: float, budget: Optional[Callable[[], float]]) -> float:
    """Per-request timeout: ``timeout``, cut to what is left of ``budget``.

    ``budget`` (seconds left, recomputed on every call) is the watch's shared
    deadline; with less than :data:`MIN_REQUEST_S` left the request is not
    sent and :class:`DeadlineReached` is raised. None means no deadline.
    """
    if budget is None:
        return timeout
    left = budget()
    if left < MIN_REQUEST_S:
        raise DeadlineReached(f"{max(left, 0.0):.1f} s of the account check's budget left")
    return min(timeout, left)


def read_accounts(client, adapter_kinds: Iterable[str],
                  timeout: float = REQUEST_TIMEOUT_S,
                  budget: Optional[Callable[[], float]] = None) -> Dict[str, Account]:
    """Every adapter instance of ``adapter_kinds`` with its state, keyed by id.

    Raises on a transport error or a non-200 answer (:class:`AuthRefused` on
    401/403); an instance whose resource carries no status entry reads
    :data:`UNREADABLE_STATE`. ``timeout`` goes on every request, cut to what
    ``budget()`` says is left before each one (:func:`_request_timeout`).
    """
    accounts: Dict[str, Account] = {}
    for kind in adapter_kinds:
        body = _ok_json(
            client._request("GET", "/api/adapters",
                            params={"adapterKindKey": kind},
                            timeout=_request_timeout(timeout, budget)),
            f"GET /api/adapters?adapterKindKey={kind}",
        )
        for dto in body.get("adapterInstancesInfoDto") or []:
            aid = str(dto.get("id") or "").strip()
            if not aid:
                continue
            key = dto.get("resourceKey") or {}
            accounts[aid] = Account(
                id=aid,
                name=str(key.get("name") or aid),
                adapter_kind=str(key.get("adapterKindKey") or kind),
                collector_id=dto.get("collectorId"),
            )
    if not accounts:
        return accounts
    ids = list(accounts)
    body = _ok_json(
        client._request("GET", "/api/resources",
                        params={"resourceId": ids, "pageSize": max(len(ids), 1)},
                        timeout=_request_timeout(timeout, budget)),
        "GET /api/resources?resourceId=...",
    )
    for res in body.get("resourceList") or []:
        rid = str(res.get("identifier") or "")
        acct = accounts.get(rid)
        if acct is None:
            continue
        entries = [e for e in (res.get("resourceStatusStates") or []) if isinstance(e, dict)]
        own = [e for e in entries if str(e.get("adapterInstanceId") or "") == rid]
        entry = (own or entries or [None])[0]
        if entry is not None:
            acct.state = str(entry.get("resourceState") or UNREADABLE_STATE)
            acct.status = str(entry.get("resourceStatus") or "")
            acct.message = str(entry.get("statusMessage") or "")
    return accounts


def start_account(client, account_id: str, timeout: float = REQUEST_TIMEOUT_S,
                  budget: Optional[Callable[[], float]] = None) -> None:
    """``PUT /api/adapters/{id}/monitoringstate/start``; raises unless 2xx
    (:class:`DeadlineReached`, unsent, when ``budget`` has run out)."""
    resp = client._request("PUT", f"/api/adapters/{account_id}/monitoringstate/start",
                           timeout=_request_timeout(timeout, budget))
    code = getattr(resp, "status_code", None)
    if code is None or not 200 <= int(code) < 300:
        text = str(getattr(resp, "text", ""))[:300]
        raise RuntimeError(f"HTTP {code}: {text}")


def _is_auth_refusal(exc: BaseException) -> bool:
    if isinstance(exc, AuthRefused):
        return True
    # VCFOpsClient.authenticate raises VCFOpsError("auth failed (<code>): ...")
    # when the token acquire is refused.
    text = str(exc)
    return text.startswith("auth failed (401)") or text.startswith("auth failed (403)")


def _prior(acct_id: str, before: Optional[Dict[str, Account]]) -> str:
    """'known', 'held' or 'unknown': what the reading before the install says."""
    prior = before.get(acct_id) if before is not None else None
    if prior is None:
        return "unknown"
    if prior.state in HELD_STATES:
        return "held"
    if prior.state in KNOWN_PRIOR_STATES:
        return "known"
    return "unknown"


def _should_start(acct: Account, before: Optional[Dict[str, Account]]) -> bool:
    if acct.state not in RESTARTABLE_STATES:
        return False
    kind = _prior(acct.id, before)
    if kind == "held":
        return False
    if kind == "unknown":
        # No usable reading from before the install: FAILED is never a
        # user's choice; a STOPPED account might be, so it is left alone.
        return acct.state == "FAILED"
    return True


def _settled(acct: Account, before: Optional[Dict[str, Account]]) -> bool:
    """True when the account needs nothing more from the watch."""
    if acct.state == OK_STATE or acct.state == UNREADABLE_STATE:
        return True
    kind = _prior(acct.id, before)
    if kind == "held":
        return True
    if kind == "unknown":
        # Only FAILED is acted on, so anything else that is not
        # transitional is as settled as it will get.
        return acct.state != "FAILED" and acct.state not in TRANSITIONAL_STATES
    return False


def _label(acct: Account) -> str:
    where = f", collector {acct.collector_id}" if acct.collector_id is not None else ""
    return f"'{acct.name}' ({acct.adapter_kind}{where}, id {acct.id})"


def _state_text(acct: Account) -> str:
    text = acct.state + (f" / {acct.status}" if acct.status else "")
    if acct.message:
        text += f" ({acct.message})"
    return text


def restart_failed_accounts(
    client,
    adapter_kinds: List[str],
    before: Optional[Dict[str, Account]],
    *,
    start_delay_s: int = START_DELAY_S,
    timeout_s: int = TIMEOUT_S,
    poll_s: int = POLL_S,
    retry_after_s: int = RETRY_AFTER_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    out: Callable[[str], None] = print,
    err: Optional[Callable[[str], None]] = None,
) -> int:
    """Watch the pak's accounts after the install, start the FAILED ones.

    ``before`` is :func:`read_accounts` from before the upload, or None when
    that read failed. Returns 0, or :data:`ACCOUNTS_NOT_STARTED_RC` when an
    account that was collecting or FAILED before the install is not STARTED
    when the check ends. When the final read failed (or a 401/403 stopped
    the watch) it prints ``ACCOUNTS UNCHECKED`` and returns 0: the install
    itself is not in doubt and stale data proves nothing.
    """
    if err is None:
        def err(msg: str) -> None:
            print(msg, file=sys.stderr)

    kinds_text = ", ".join(adapter_kinds)
    t0 = clock()
    accounts: Optional[Dict[str, Account]] = None
    last_good_at: Optional[float] = None
    last_error = ""
    failed_reads = 0
    auth_refused = False
    # id -> [(elapsed, refusal or "")] per start sent
    starts: Dict[str, List[tuple]] = {}
    # Accounts that needed a start the budget had no room for.
    unsent: List[str] = []
    announced = False
    deadline = t0 + timeout_s

    def budget() -> float:
        # One shared deadline, recomputed before every request and sleep, so
        # slow requests cannot stack past timeout_s (Codex P2, PR #293: 12
        # FAILED accounts with 30 s start timeouts ran a 300 s check to 495 s).
        return deadline - clock()

    while True:
        if budget() < MIN_REQUEST_S:
            break
        elapsed = clock() - t0
        fresh = False
        try:
            accounts = read_accounts(client, adapter_kinds, budget=budget)
            fresh = True
            last_good_at = elapsed
            last_error = ""
        except DeadlineReached:
            # Out of time mid-read: not a failed read. The last good reading
            # (one poll old at most) stands.
            break
        except Exception as exc:  # noqa: BLE001  retried until the deadline
            failed_reads += 1
            last_error = str(exc)
            if _is_auth_refusal(exc):
                auth_refused = True
                err(f"WARN: account state read refused ({exc}) after {failed_reads} "
                    f"failed read(s); not retrying.")
                break
            if failed_reads == 1:
                err(f"WARN: account state read failed (will retry quietly): {exc}")
        if fresh and not accounts:
            out(f"ACCOUNTS: no adapter instance of {kinds_text} exists; nothing to start.")
            return 0
        if fresh and not announced:
            announced = True
            out(f"ACCOUNT CHECK: {len(accounts)} adapter instance(s) of {kinds_text}; "
                f"watching for {start_delay_s} s before starting any that the install "
                f"left FAILED (up to {timeout_s} s).")
        out_of_time = False
        if fresh and elapsed >= start_delay_s:
            for acct in accounts.values():
                sent = starts.get(acct.id, [])
                if not _should_start(acct, before):
                    continue
                if sent:
                    # A second start only for an account that took the first
                    # one and reads FAILED again a while later. first_at is
                    # when that start was actually sent and ``elapsed`` is
                    # when this reading was taken (after it), so the FAILED
                    # was seen at least retry_after_s after the first start,
                    # and the second goes out later still.
                    first_at, first_err = sent[0]
                    if (len(sent) >= MAX_STARTS or first_err or acct.state != "FAILED"
                            or elapsed - first_at < retry_after_s):
                        continue
                if out_of_time:
                    unsent.append(acct.id)
                    continue
                # Timestamp the start when it is sent, not when the poll
                # began: earlier slow starts in this sweep move it on (Codex
                # P2, PR #293).
                sent_at = clock() - t0
                try:
                    start_account(client, acct.id, budget=budget)
                    starts.setdefault(acct.id, []).append((sent_at, ""))
                    nth = "re-issued" if not sent else "re-issued a second time"
                    out(f"ACCOUNT START SENT: {_label(acct)} read {_state_text(acct)} "
                        f"{int(elapsed)} s after the install; start monitoring {nth} "
                        f"at {int(sent_at)} s.")
                except DeadlineReached:
                    # No start goes out past the deadline; the rest are listed.
                    out_of_time = True
                    unsent.append(acct.id)
                except Exception as exc:  # noqa: BLE001  reported per account
                    starts.setdefault(acct.id, []).append((sent_at, str(exc)))
                    err(f"WARN: start monitoring refused for {_label(acct)}: {exc}")
            if out_of_time:
                err(f"WARN: the {timeout_s} s account check ran out before start "
                    f"monitoring could be sent to {len(unsent)} account(s).")
                break
            if all(_settled(a, before) for a in accounts.values()):
                break
        left = budget()
        if left < MIN_REQUEST_S:
            break
        sleep(min(poll_s, left))

    if accounts is None or last_error:
        why = "a 401/403 stopped the watch" if auth_refused else "the last read failed"
        if accounts is None:
            err(f"WARNING: ACCOUNTS UNCHECKED: could not read the adapter instances of "
                f"{kinds_text} ({failed_reads} failed read(s); last: {last_error}). Check "
                f"each account's collection state by hand; a remote-collector account "
                f"may need Start monitoring (lesson remote-collector-upgrade-start-race).")
        else:
            err(f"WARNING: ACCOUNTS UNCHECKED: {why} ({failed_reads} failed read(s); "
                f"last: {last_error}). State as of {int(last_good_at)} s after the "
                f"install, not a verdict:")
            for acct in sorted(accounts.values(), key=lambda a: a.name.lower()):
                n = len([s for s in starts.get(acct.id, []) if not s[1]])
                sent = f"; {n} start(s) sent" if n else ""
                err(f"  {_label(acct)}: {_state_text(acct)}{sent}")
            err("  Check each account by hand; start any that is FAILED (lesson "
                "remote-collector-upgrade-start-race).")
        return 0

    rc = 0
    for acct in sorted(accounts.values(), key=lambda a: a.name.lower()):
        prior = before.get(acct.id) if before is not None else None
        kind = _prior(acct.id, before)
        was = f"; was {prior.state} before the install" if prior is not None else ""
        sent = starts.get(acct.id, [])
        ok_starts = [s for s in sent if not s[1]]
        if acct.state == OK_STATE:
            how = "restarted" if ok_starts else "collecting"
            out(f"ACCOUNT OK ({how}): {_label(acct)}: {_state_text(acct)}{was}.")
        elif acct.state == UNREADABLE_STATE:
            err(f"WARNING: ACCOUNT UNCHECKED: {_label(acct)}: state unreadable (the "
                f"resource carries no status entry){was}. Check it by hand.")
        elif kind == "held":
            out(f"ACCOUNT LEFT ALONE: {_label(acct)}: {_state_text(acct)}{was}; "
                f"not started (stopped or in maintenance by choice).")
        elif kind == "unknown" and acct.state != "FAILED" \
                and acct.state not in TRANSITIONAL_STATES:
            err(f"WARNING: ACCOUNT NOT COLLECTING: {_label(acct)}: {_state_text(acct)}"
                f"{was}; no usable state from before the install, so it was not "
                f"started. Start it by hand if it should collect.")
        else:
            rc = ACCOUNTS_NOT_STARTED_RC
            refused = [s[1] for s in sent if s[1]]
            if refused:
                tried = f"; start monitoring was refused: {refused[-1]}"
            elif ok_starts:
                tried = f"; start monitoring was re-issued {len(ok_starts)} time(s)"
            else:
                tried = ""
            if acct.id in unsent:
                tried += (f"; {'no further' if ok_starts else 'no'} start was sent: "
                          f"the {timeout_s} s budget ran out")
            err(f"ACCOUNT NOT STARTED: {_label(acct)}: {_state_text(acct)} after "
                f"{int(clock() - t0)} s{was}{tried}. Confirm the collector loaded the "
                f"new adapter version, then PUT /suite-api/api/adapters/{acct.id}/"
                f"monitoringstate/start (lesson remote-collector-upgrade-start-race). "
                f"Do not reinstall.")
    return rc


def pak_adapter_kinds(manifest: Dict[str, str]) -> List[str]:
    """The adapter kinds a parsed manifest declares (comma-joined field)."""
    raw = str(manifest.get("adapter_kinds", "") or "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def default_suite_factory(host: str, user: str, password: str, verify_ssl: bool):
    """Suite API client for the installer's local account."""
    from vcfcf_common.client import VCFOpsClient
    return VCFOpsClient(host=host, username=user, password=password,
                        auth_source="Local", verify_ssl=verify_ssl,
                        auth_timeout=REQUEST_TIMEOUT_S)
