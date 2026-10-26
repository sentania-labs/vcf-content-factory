# Framework review: pak install poll timeout (2026-10-26)

- Branch: `fix/pak-install-poll-timeout`, base `ddaf12d`
- Commits: `eb6afa9` (src, tests, README), `32e08b7` (content-installer prompt)
- Files: `src/vcfcf_managementpacks/installer.py`, `cli.py`, `README.md`,
  `tests/test_pak_install_poll_timeout.py`, `.claude/agents/content-installer.md`
- Verdict: **CHANGES REQUESTED** (2 BLOCKING, 1 WARNING, 4 NIT)

## Checks re-run

- Validate chain, all seven packages: rc 0.
- `tests/test_pak_install_poll_timeout.py` plus the installer neighbours
  (`test_install_materialization`, `test_pak_summary_rebind`,
  `test_installer_unsigned_pak_policy`): 129 passed. The new file holds 12 tests.
- Full suite: 6 failed, 2911 passed, 9 skipped. All 6 are
  `test_release_naming_phase_v2_item1.py` (5) and `test_validator_phase2.py` (1).
  Each fails on `artifact source not found: content/sdk-adapters/synology/adapter.yaml`,
  so tooling's attribution (the missing sdk-adapters clone) holds.
- Render regression and pak-compare: n/a. No renderer, builder or template
  was touched, and nothing on the content-import zip path changed. Dimension 9
  is not triggered: none of the stale-zip trigger files was touched, so no
  `CURRENT_TEMPLATE_VERSION` bump is needed.
- Probe tests (scratch only, not committed) against the branch:
  - every `isPakInstalling` poll raises: rc 4, `INSTALL STILL RUNNING ... Last known status: (unknown) ... This is not a failure; do not reinstall`;
  - the poll answers JSON without `isPakInstalling`: rc 4;
  - `--no-wait --install-timeout 5`: rc 0, the flag is silently ignored.

## Claims

| Claim | Result |
|---|---|
| Default 1800 s; flag and env override; the flag wins | Confirmed (`resolve_install_timeout`, cli passthrough, tests) |
| A bad env value warns and keeps 1800; a bad flag exits 2 | Confirmed |
| Running out *while isPakInstalling=True* gives exit 4, INSTALL STILL RUNNING, clean logout | Partly. Logout runs (the `finally` is intact). But exit 4 also fires when no poll ever succeeded, or when the answer has no `isPakInstalling` key. See B1 |
| Uninstall keeps 300 s | Confirmed (`POLL_TIMEOUT = 300`, `uninstall_pak` default unchanged) |
| 12 new tests with a fake clock | Confirmed |
| The 6 failures are the known clone-absence set | Confirmed |
| Exit 4 collides with nothing | Confirmed. No caller in `src/`, `scripts/`, `.github/` or `bundles/` parses the install CLI's exit code. The only other exit 4 is `scripts/version_line_guard.sh`, which is unrelated. No other `vcfcf_managementpacks` subcommand returns 4 |
| No outer subprocess timeout at 300/400 s in code | Confirmed for code. Not true for the operator path: see B2 |

## BLOCKING

### B1. A wait with no successful poll is reported as "still running, not a failure"

`installer.py:1209-1256`. `still_running = True` is set whenever `installed` is
False at the deadline. Nothing checks that any poll succeeded, or that the last
good one read `isPakInstalling=True`. Two inputs reach exit 4 without evidence
that the install is running:

- **Every poll raises.** The probe shows rc 4 with `Last known status: (unknown)`.
  The message asserts "was still installing" and "This is not a failure; do not
  reinstall". Realistic causes over a 30-minute window: the `/ui/` session is
  invalidated (devel_9_1 refused UI login with `concurrentSessionDetected` on
  2026-10-26, `knowledge/designs/HANDOFF-2026-10-26.md`), a 401/403, or the
  cluster going offline (`clusterBringOffline`) and coming back in a state the
  session cannot read.
- **The answer lacks the key.** `status.get("isPakInstalling", True)` turns an
  error-shaped JSON body into "installing". This line predates the change, but
  it now feeds a "not a failure" verdict instead of an exit 1.

The same gap covers a stale state. If one poll read True at minute 2 and the
next 28 minutes of polls all failed, the CLI still prints "Last known status:
pakInstalling=True" and exits 4.

Before this change, all three cases exited 1 with "may still be running". Now
they tell the operator and content-installer not to reinstall, and they skip
the post-install checks, on no evidence. That is the reports-green-while-broken
class (reviewer doctrine: unproven is a finding). The brief named it
explicitly: "a server failure state seen during the wait being misreported as
still running."

**Fix.**
- Track whether the last poll succeeded and what it read. Return 4 only when the
  most recent poll succeeded with an explicit `isPakInstalling is True`.
- Otherwise keep the old `_abort` (exit 1, status unknown), and name the number
  of consecutive failed polls and the last error.
- Treat a missing key as a failed poll, not as True.
- Add tests for all three: every poll fails, the key is missing, and True then
  failures.

### B2. The content-installer prompt advertises a 30-minute wait its own harness kills at 600 s

`.claude/agents/content-installer.md:100-108`, with lines 186-190. The prompt
now says the install waits up to 1800 s, then runs the materialization check and
Summary repair (up to 900 s more). content-installer runs the CLI through the
Bash tool, which caps a foreground command at 600 s (default 120 s). Lines
188-190 forbid handing a wait to a background command.

The prompt gives no instruction that fits a run of up to about 46 minutes
(1800 + 30 settle + up to 900 post-install + request time). As written, an
install like the 2026-10-26 one is killed by the harness at or before 600 s:

- no exit code and no INSTALL STILL RUNNING line;
- the `finally: ui.logout()` does not run on a kill, so the server-side `/ui/`
  session is left open, which feeds `concurrentSessionDetected`;
- the materialization check and Summary repair still do not run.

That is the failure the change exists to fix, unchanged on the factory's
designated pak-install path. The README's subprocess advice ("set your
subprocess timeout above that wait plus the post-install checks") is correct
for scripts, but nothing carries it to the agent. This is a prompt/code
mismatch in the diff under review.

**Fix:** state the 600 s foreground cap in the prompt and the sanctioned way to
run the install. Either:
- run it in the background and wait in the same turn on its exit with a Monitor
  until-loop, without ending the turn, which is consistent with lines 188-190; or
- name the exact Bash timeout and `--install-timeout` to pass so the whole run
  fits under 600 s, and say that this gives up most of the 1800 s.

The first preserves the fix. Also tell the agent to record the
`INSTALL STILL RUNNING` line verbatim on 4.

## WARNING

### W1. The wait loop's deadline is not a bound: `is_pak_installing` sends no request timeout

`installer.py:689-713` (`self._session.post(...)` with no `timeout=`), called
from the loop at 1209-1214. Issue #235 gave every `solution_action` request a
timeout because a stalled socket held the verify loop forever. `isPakInstalling`
goes to `/ui/clusterManagement.action` directly and skipped that fix.

A server that accepts the connection and never answers holds the CLI past the
1800 s deadline indefinitely. The README and installer comment promise
"wait plus post-install checks" as a wall-time bound, and both exit 4 and the
B2 sizing depend on that bound.

The method predates this change, but the loop that depends on it is the subject
of the change.

**Fix:** pass `timeout=(SOLUTION_ACTION_TIMEOUT[0], min(SOLUTION_ACTION_TIMEOUT[1], remaining))`.
A timeout then raises into the existing "Status poll failed (will retry)" path,
which after B1 is not evidence of "still running". Add a test.

## NIT

### N1. `--install-timeout` with `--no-wait` is silently ignored

`cli.py:1337-1347`, `installer.py:1199`. The probe returns rc 0 with
`poll_timeout=5` passed and unused.

**Fix:** reject the combination (exit 2) or warn.

### N2. The epilog says "default 1800 s" and omits the env override

`cli.py:1401-1402`. The `--install-timeout` help names `VCFCF_INSTALL_TIMEOUT_S`;
the exit-code epilog does not. An operator with the env set reads the wrong
wait.

**Fix:** "(--install-timeout or VCFCF_INSTALL_TIMEOUT_S, default 1800 s)". The
test at `tests/test_pak_install_poll_timeout.py:187` pins the old string, so
update it too.

### N3. The prompt section heading still dates the rules "since 2026-10-24, #244 and #200"

`.claude/agents/content-installer.md:100`. Exit 4 and the 1800 s wait are
2026-10-26 additions.

**Fix:** extend the heading (e.g. "2026-10-24/26").

### N4. The recovery for exit 4 is manual only, with no tracking

The message, epilog, README and prompt all say "no command re-runs them [the
post-install checks] on their own against an installed pak". That is accurate
(the only caller of `post_install.report_pak_dashboards` is `install_pak`), and
it is a loud, documented limitation, so it is not a silent downgrade
(dimension 8). Still, every exit 4 leaves the #200 Summary repair undone with
no tool to finish it.

**Fix:** open a follow-up issue for a `post-install` (check-only) subcommand
that takes a pak path and profile and calls `report_pak_dashboards`, and
reference it in the exit-4 text.

## Dimensions walked

1. **Global-default leak:** n/a. The change is confined to the pak installer;
   the content-zip `install.py` is untouched.
2. **Key collisions:** n/a.
3. **Wire format:** no change to `isPakInstalling` or the install request bodies.
4. **Loader/validator:** untouched. The validate chain is green.
5. **Render regression:** n/a.
6. **Builder/pak:** untouched.
7. **Corpus/suite:** green, apart from the known clone-absence six.
8. **Silent downgrade:** none. Exit 4 is loud. B1 is a mis-verdict rather than a
   downgrade.
9. **Stale zips:** not triggered. No template-version bump is needed.
10. **Tests:** good coverage of the happy path, overrides, the flag, the epilog
    and logout. Missing are the failed-poll and missing-key paths (B1) and the
    request timeout (W1).

## If shipped as-is

- **content-installer** (the designated pak-install path): a slow install is
  still killed at or before 600 s by the Bash harness. There is no exit code
  and no logout, and the post-install checks are still skipped. The bug is not
  fixed there.
- **A script with an adequate timeout:** a session that dies mid-wait is
  reported as "still running, not a failure, do not reinstall", on no evidence.
