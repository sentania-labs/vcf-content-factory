# Framework review: installer post-install account restart

- Branch: `installer-restart-failed-accounts`, commit bd6cd88 (base c263fd3)
- Area: `src/vcfcf_managementpacks/` (account_restart.py new, installer.py, cli.py, README)
- Reviewed: 2026-10-28, scratch clone (main tree left on main)
- Verdict: **CHANGES REQUESTED** (1 BLOCKING / 3 WARNING / 4 NIT)

## Checks re-run

- Validate chain (7 packages) on the branch: all rc 0.
- Full suite on the branch: 3120 passed, 6 failed, 13 skipped. The same 6
  fail at base c263fd3 in the same clone (`test_release_naming_phase_v2_item1`
  x5, `test_validator_phase2` x1): `vcfcf_packaging validate` needs the
  gitignored `content/sdk-adapters/synology/`. Environmental, not this change.
  `tests/test_install_account_restart.py`: 20 tests, all pass.
- Render regression / pak-compare: n/a. No file under `src/vcfcf_packaging/`
  or `src/vcfcf_core/` is touched, so no zip is stale and no
  `CURRENT_TEMPLATE_VERSION` bump is owed (dimension 9 clean).
- Fake-client probes of `restart_failed_accounts` (injected clock/sleep) for
  each case below; results quoted where they back a finding.

## BLOCKING

**B1. `account_restart.py:153-161` `_should_start`: an account whose state
before the install read UNKNOWN, NONE or NOT_EXISTING is treated as "was
collecting" and gets a start when it reads STOPPED afterwards.**
Authority: the contract this change writes into the lesson, README and CLI
help ("never to one that was STOPPED or in maintenance before the install"),
and the module's own rule for unknown intent (`prior is None` means start only
FAILED). `read_accounts` leaves `state="UNKNOWN"` when the instance is absent
from `resourceList` or has no `resourceStatusStates` entry, so "no reading" is
represented as a non-None prior and falls through to `prior.state not in
HELD_STATES`, which is True. Probe: prior UNKNOWN / NONE / NOT_EXISTING, post
STOPPED, gives `ACCOUNT START SENT` at 120 s each time. A user-stopped
account whose pre-read came back without a status entry gets started.
Fix: allowlist instead of denylist. Treat a prior as known only when it is
one of STARTED, STARTING, UPDATING, FAILED. Any other prior (UNKNOWN, NONE,
NOT_EXISTING, REMOVING) takes the `prior is None` branch, meaning start only
on FAILED. Mirror that in `_settled` and in the final-report branch, and add
a test per prior state.

## WARNING

**W1. `account_restart.py:224-229, 257-291`: after a failed read the loop
reuses the last good state, both for starts and for the final verdict, and
never says so.** Probe: FAILED until t=105, every read failing after that,
true state STARTED from 200 s. Output: `ACCOUNT NOT STARTED ... FAILED after
300 s`, rc 3. That message states something that was never observed. Same
class as "reports-green-while-broken", aimed the other way.
Fix: keep the time of the last good read. When the final read failed, say
"state as of N s, last read failed: <error>" and do not return 3 on stale
data; print ACCOUNTS UNCHECKED instead. Do not send a start from a reading
older than one poll.

**W2. `account_restart.py:107,125,146` (and `installer.py:1197-1209`): no
request timeout.** `VCFOpsClient._request` passes no `timeout` and
`new_session` sets none. The pre-read now runs **before the upload**, so a
stalled Suite API connection hangs the install before it starts. Previously
this path had no Suite API call at all. After the install it can also run
past the "up to 300 s" that `INSTALL_POLL_TIMEOUT`'s docstring tells
subprocess wrappers to budget. The `_UISession` polls already pass
`timeout=remaining`. Fix: pass `timeout=` (for example 30 s, and
`min(30, remaining)` in the loop) on all three calls. Add a test that the
pre-read raising a timeout lets the install go ahead (the existing
ConnectionError test covers the except, not the hang).

**W3. `account_restart.py:239-250`: one start, at 120 s after *verify*, with
no second try when the account fails again.** The lesson times the jar load
at 90 to 120 s after the server's *start task*. Nothing in the repo
establishes when verify (isPakInstalling false + version registered) happens
relative to that task. If verify comes first, the single start can land
inside the same window and be rejected the same way. Probe "start accepted
but re-FAILS": rc 3 at 300 s with 180 s of budget unused. The failure is
loud (rc 3 with the by-hand PUT), so this is not BLOCKING. But it leaves the
lesson's exact failure only half automated. Fix: allow one more start (cap
2) when an account that was sent a start reads FAILED again at least 60 s
later, still inside `TIMEOUT_S`. Or cite the evidence that verify follows
the start task by at least 30 s.

## NIT

**N1. `cli.py` epilog / README: `ACCOUNT NOT STARTED` is described as "an
account that was collecting before the install".** The code also returns 3
for an account that was already FAILED before the install (probe: prior
FAILED gives a start and rc 3). An account broken for unrelated reasons, such
as bad credentials, makes every install exit 3. That may be the right call,
but the docs should say so ("collecting or FAILED before the install").

**N2. `account_restart.py:227-229`: a persistent read failure prints a WARN
every 15 s for 300 s (about 20 lines).** A 401/403 will not heal. Stop
retrying on an auth refusal, and print the WARN once with a count.

**N3. `tests/test_install_account_restart.py`: no `read_accounts` test with
two adapter kinds.** Multi-kind behaviour looked correct on reading
(per-kind GET, one batched resources GET, ids keyed globally, label from
`resourceKey.adapterKindKey`). One failing kind's GET fails the whole read,
which is acceptable but untested. Add a two-kind test, one with a kind that
has zero instances.

**N4. `account_restart.py:274` and `_settled`: a post-install read with no
status entry (UNKNOWN) for an account that was STARTED waits the full 300 s
and exits 3 with "UNKNOWN after 300 s".** After B1's fix, word this as "state
unreadable" rather than NOT STARTED, or route it to ACCOUNTS UNCHECKED.

## Dimensions proven clean

- **User-stopped accounts (beyond B1):** prior STOPPED, STOPPING, MAINTAINED,
  or MAINTAINED_MANUAL is never started and settles at once. That set covers
  every user-held value in the 9.1 `resource-status-state.resourceState` enum
  (`reference/docs/operations-api-9.1.json`; there is no
  MAINTAINED_SCHEDULED). A failed pre-read gives `before=None`, so only
  FAILED is started. `--no-restart-failed` skips both reads, and so does
  `--no-wait`, because `installed` is never set without `wait`.
- **Exit codes:** `dashboards_rc or accounts_rc` with both drawn from {0, 3}
  is correct. `--skip-materialization-check` now returns `accounts_rc`
  instead of 0, which is intended. Rc 4 (still running) returns before the
  account check, and the README says so. A suite-factory exception gives
  ACCOUNTS UNCHECKED, rc unchanged.
- **Secrets:** the password reaches only `VCFOpsClient`. Auth failures echo
  the server's `r.text`, not the request. Output carries account names, ids,
  collector ids and `statusMessage`. No credential path.
- **Global path / packaging:** no renderer, template, builder or assembly
  file is touched, and no wire format is emitted. Bundles are not stale.

## Local (non-proxy) collector, nothing failing

The cost is exactly `START_DELAY_S`: probe "local all STARTED" ends at
t=120 with no start and rc 0. The `_settled` break sits inside
`elapsed >= start_delay_s`, so it cannot end sooner. Ending early on "every
account STARTED / DATA_RECEIVING" is **not** provably safe with what the code
reads. A STARTED reading right after verify may come from before the
server's own stop/start, and the repo has no evidence of when that cycle runs
relative to verify. A safe early exit would key on the race's actual
precondition: the lesson says it appears only on remote collectors and Cloud
Proxies. The 9.1 spec's `collector` schema has `local` and `type`
(`GET /api/collectors`). Skipping the watch for accounts whose `collectorId`
is a local collector would make the primary-node case cost nothing. Those
fields have never been read live, though (RULE-002), so this is an
api-explorer read plus a follow-up, not a fix for this PR.

## If shipped as-is

A user-stopped account whose pre-install state read came back empty gets
started by the installer. A transient Suite API outage at the end of the
watch can produce a false `ACCOUNT NOT STARTED` and exit 3. A stalled Suite
API connection can hang the install before the upload.
