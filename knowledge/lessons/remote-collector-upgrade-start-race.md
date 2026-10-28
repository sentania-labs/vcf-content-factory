# A pak upgrade on a remote collector leaves its accounts FAILED: start them after the jar loads

Date: 2026-10-13 and 2026-10-14. Compliance v1.0.0.93 and v1.0.0.94 on prod
(VCF Operations 9.1.1), accounts on remote collector collector01.

## What happened

Both upgrades did the same thing. The controller stopped the pak's adapter
instances, pushed the new jar, and sent Start monitoring about 30 seconds
later. The remote collector had not loaded the new adapter yet, rejected each
start with `Unknown adapter type is specified in collector configuration.
(Type = <adapter kind>)`, and nothing retried. The collector loaded the adapter
lazily about 90 seconds later, on the next Test Connection or config read. The
accounts showed resourceState FAILED with an empty message and collected
nothing until someone started them. Devel never showed it because its
accounts run on the primary node's collector.

## Lesson

- After every pak upgrade, read each of the pak's accounts' resourceState. Any
  FAILED account on a remote collector: confirm the collector has loaded the
  new adapter version (collector.log "Loaded adapter entry class ... version
  <new>"), then `PUT /api/adapters/{id}/monitoringstate/start` for exactly that
  account, and confirm a fresh cycle.
- A green install (version, pak results, jar hash) says nothing about
  collection. Verify a cycle.
- The collector's logs are readable without SSH through the admin UI's Support
  Logs browser (Administration, Control Panel, Support Logs, per node), which
  matters when a node's root password has expired.
- Seen again 2026-10-15 on devel_9_1 (Cloud Proxy): a same-version reinstall
  of UniFi 0.0.0.14 put its account FAILED with no message for over nine
  minutes until started by hand. The race is not limited to version bumps;
  any pak install that reloads the adapter on a remote collector can trip it.
  The 9.0.2 instance with its collector on the primary did not.
- Seen again 2026-10-28 on devel_9_1: the compliance 0.0.0.102 install left
  all three accounts FAILED; a manual start per account a minute later fixed
  them.

## Codified in the installer (2026-10-28)

`python3 -m vcfcf_managementpacks install` now does the check above itself
(`src/vcfcf_managementpacks/account_restart.py`). Before the upload it reads
each adapter instance of the pak's `adapter_kinds` and its `resourceState`.
After the install verifies it watches them for 120 s (a start sent before
the collector loads the jar fails the same way), then sends Start monitoring
to each account that reads FAILED, STOPPED or NONE and read STARTED,
STARTING, UPDATING or FAILED before the install. One that was STOPPED or in
maintenance before is never started; one with no usable state from before
is started only when FAILED. An account that reads FAILED again 60 s after
its start gets a second, never a third. It polls until they read STARTED or
300 s have passed and prints each account's final state; an account that
was collecting or already FAILED before and is still not STARTED prints
`ACCOUNT NOT STARTED` and the command exits 3 (installed, post-install check
failed: do not reinstall). If the last state read failed it prints `ACCOUNTS
UNCHECKED` instead, with no verdict. `--no-restart-failed` turns it off;
`--no-wait` never runs it.

The installer reads `resourceState`, not the collector log, so it does not
confirm the jar loaded before starting. If an account is still FAILED after
its two starts, do the by-hand steps above. A green install still says
nothing about a collection cycle: verify one.
