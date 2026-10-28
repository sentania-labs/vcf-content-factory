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
   once per account that reads FAILED, STOPPED or NONE, unless it read
   STOPPED, STOPPING or MAINTAINED* before the install (the user's choice,
   left alone). An account with no state from before the install is started
   only when FAILED, which is never a user's choice.
4. Keep polling until every account that should collect reads STARTED, or
   :data:`TIMEOUT_S` runs out, and print each account's final state.

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
#: Seconds after the install verifies before the check gives up.
TIMEOUT_S = 300
#: Seconds between state reads.
POLL_S = 15

#: Exit code when an account that should collect is not STARTED at the end.
#: Same code as the dashboard checks: the pak installed, a post-install
#: check failed, do not reinstall.
ACCOUNTS_NOT_STARTED_RC = 3

#: States that mean the user chose not to collect: an account in one of
#: these before the install is never started by the installer.
HELD_STATES = frozenset({"STOPPED", "STOPPING", "MAINTAINED", "MAINTAINED_MANUAL"})
#: States after the install that get one start.
RESTARTABLE_STATES = frozenset({"FAILED", "STOPPED", "NONE"})
#: The only state that counts as collecting.
OK_STATE = "STARTED"


@dataclass
class Account:
    """One adapter instance (an "account") and its collection state."""
    id: str
    name: str
    adapter_kind: str
    collector_id: Optional[object] = None
    state: str = "UNKNOWN"
    status: str = ""
    message: str = ""


def _ok_json(resp, what: str) -> dict:
    code = getattr(resp, "status_code", None)
    if code != 200:
        text = str(getattr(resp, "text", ""))[:300]
        raise RuntimeError(f"{what} returned HTTP {code}: {text}")
    body = resp.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{what} answered a {type(body).__name__}, not an object")
    return body


def read_accounts(client, adapter_kinds: Iterable[str]) -> Dict[str, Account]:
    """Every adapter instance of ``adapter_kinds`` with its state, keyed by id.

    Raises on a transport error or a non-200 answer; an instance whose
    resource carries no status entry reads UNKNOWN.
    """
    accounts: Dict[str, Account] = {}
    for kind in adapter_kinds:
        body = _ok_json(
            client._request("GET", "/api/adapters", params={"adapterKindKey": kind}),
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
                        params={"resourceId": ids, "pageSize": max(len(ids), 1)}),
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
            acct.state = str(entry.get("resourceState") or "UNKNOWN")
            acct.status = str(entry.get("resourceStatus") or "")
            acct.message = str(entry.get("statusMessage") or "")
    return accounts


def start_account(client, account_id: str) -> None:
    """``PUT /api/adapters/{id}/monitoringstate/start``; raises unless 2xx."""
    resp = client._request("PUT", f"/api/adapters/{account_id}/monitoringstate/start")
    code = getattr(resp, "status_code", None)
    if code is None or not 200 <= int(code) < 300:
        text = str(getattr(resp, "text", ""))[:300]
        raise RuntimeError(f"HTTP {code}: {text}")


def _should_start(acct: Account, before: Optional[Dict[str, Account]]) -> bool:
    if acct.state not in RESTARTABLE_STATES:
        return False
    prior = before.get(acct.id) if before is not None else None
    if prior is None:
        # No reading from before the install: FAILED is never a user's
        # choice; a STOPPED account might be, so it is left alone.
        return acct.state == "FAILED"
    return prior.state not in HELD_STATES


def _held(acct_id: str, before: Optional[Dict[str, Account]]) -> bool:
    prior = before.get(acct_id) if before is not None else None
    return prior is not None and prior.state in HELD_STATES


def _settled(acct: Account, before: Optional[Dict[str, Account]]) -> bool:
    """True when the account needs nothing more: STARTED, or left alone."""
    if acct.state == OK_STATE or _held(acct.id, before):
        return True
    if before is None or acct.id not in before:
        # Unknown prior intent: only FAILED is acted on, so anything else
        # that is not transitional is as settled as it will get.
        return acct.state not in {"FAILED", "STARTING", "STOPPING", "UPDATING"}
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
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    out: Callable[[str], None] = print,
    err: Optional[Callable[[str], None]] = None,
) -> int:
    """Watch the pak's accounts after the install, start the FAILED ones once.

    ``before`` is :func:`read_accounts` from before the upload, or None when
    that read failed. Returns 0, or :data:`ACCOUNTS_NOT_STARTED_RC` when an
    account that was collecting (or FAILED) before the install is not
    STARTED when the check ends. A state read that fails every time prints
    ``ACCOUNTS UNCHECKED`` and returns 0: the install itself is not in doubt.
    """
    if err is None:
        def err(msg: str) -> None:
            print(msg, file=sys.stderr)

    t0 = clock()
    accounts: Optional[Dict[str, Account]] = None
    started: Dict[str, str] = {}      # id -> "" on success, else the refusal
    last_error = ""
    announced = False
    while True:
        elapsed = clock() - t0
        try:
            accounts = read_accounts(client, adapter_kinds)
            last_error = ""
        except Exception as exc:  # noqa: BLE001  retried until the deadline
            last_error = str(exc)
            err(f"WARN: account state read failed (will retry): {exc}")
        if accounts is not None and not accounts:
            out(f"ACCOUNTS: no adapter instance of {', '.join(adapter_kinds)} exists; "
                f"nothing to start.")
            return 0
        if accounts is not None and not announced:
            announced = True
            out(f"ACCOUNT CHECK: {len(accounts)} adapter instance(s) of "
                f"{', '.join(adapter_kinds)}; watching for {start_delay_s} s before "
                f"starting any that the install left FAILED (up to {timeout_s} s).")
        if accounts is not None and elapsed >= start_delay_s:
            for acct in accounts.values():
                if acct.id in started or not _should_start(acct, before):
                    continue
                try:
                    start_account(client, acct.id)
                    started[acct.id] = ""
                    out(f"ACCOUNT START SENT: {_label(acct)} read {_state_text(acct)} "
                        f"{int(elapsed)} s after the install; start monitoring re-issued.")
                except Exception as exc:  # noqa: BLE001  reported per account
                    started[acct.id] = str(exc)
                    err(f"WARN: start monitoring refused for {_label(acct)}: {exc}")
            if all(_settled(a, before) for a in accounts.values()):
                break
        if elapsed >= timeout_s:
            break
        sleep(max(1.0, min(poll_s, timeout_s - elapsed)))

    if accounts is None:
        err(f"WARNING: ACCOUNTS UNCHECKED: could not read the adapter instances of "
            f"{', '.join(adapter_kinds)} ({last_error}). Check each account's "
            f"collection state by hand; a remote-collector account may need Start "
            f"monitoring (lesson remote-collector-upgrade-start-race).")
        return 0

    rc = 0
    for acct in sorted(accounts.values(), key=lambda a: a.name.lower()):
        prior = before.get(acct.id) if before is not None else None
        was = f"; was {prior.state} before the install" if prior is not None else ""
        if acct.state == OK_STATE:
            how = "restarted" if acct.id in started and not started[acct.id] else "collecting"
            out(f"ACCOUNT OK ({how}): {_label(acct)}: {_state_text(acct)}{was}.")
        elif _held(acct.id, before):
            out(f"ACCOUNT LEFT ALONE: {_label(acct)}: {_state_text(acct)}{was}; "
                f"not started (stopped or in maintenance by choice).")
        elif prior is None and acct.state not in {"FAILED", "STARTING", "STOPPING", "UPDATING"}:
            err(f"WARNING: ACCOUNT NOT COLLECTING: {_label(acct)}: {_state_text(acct)}; "
                f"its state before the install is unknown, so it was not started. "
                f"Start it by hand if it should collect.")
        else:
            rc = ACCOUNTS_NOT_STARTED_RC
            if acct.id in started and started[acct.id]:
                tried = f"; start monitoring was refused: {started[acct.id]}"
            elif acct.id in started:
                tried = "; start monitoring was re-issued once"
            else:
                tried = ""
            err(f"ACCOUNT NOT STARTED: {_label(acct)}: {_state_text(acct)} after "
                f"{timeout_s} s{was}{tried}. Confirm the collector loaded the new "
                f"adapter version, then PUT /suite-api/api/adapters/{acct.id}/"
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
                        auth_source="Local", verify_ssl=verify_ssl)
