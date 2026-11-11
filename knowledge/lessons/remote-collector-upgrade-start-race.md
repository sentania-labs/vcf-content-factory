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

## Second failure mode: the jar sync fails and the old version loads

Seen 2026-10-28, compliance 0.0.0.103 on devel_8_18 (Cloud Proxy). The
proxy logged "Did not receive response from Controller for 'Sync Adapters'
task. Wait for response timed out" and "Adapter jar synchronization failed",
then loaded the OLD adapter version (0.0.0.102). This is not the start race:
the collector never got the new jar, so a start would only have run the old
one. Re-running the same install fixed it; the sync succeeded and the
account started on its own.

- Before starting a FAILED account by hand, read the collector log. "Adapter
  jar synchronization failed" means re-run the install, not start the
  account. "Loaded adapter entry class ... version <new>" means start it.
- No Suite API endpoint reports the adapter version a collector has loaded
  (checked in the operations and internal specs for 8.18, 9.0 and 9.1:
  `describeVersion` is the controller's describe.xml version, `/api/solutions`
  is the controller's pak version, and neither `collector` nor
  `/api/collectors/{id}/adapters` carries a version). Only the collector log
  tells the two failure modes apart.

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
a 300 s deadline passes (up to about 360 s in the worst case, when the
server rejects the session token near the end and the client's re-auth and
retried call run past it) and prints each account's final state; an account that
was collecting or already FAILED before and is still not STARTED prints
`ACCOUNT NOT STARTED` and the command exits 3 (installed, post-install check
failed: do not reinstall). If the last state read failed it prints `ACCOUNTS
UNCHECKED` instead, with no verdict. `--no-restart-failed` turns it off;
`--no-wait` never runs it.

The installer reads `resourceState`, not the collector log, so it does not
confirm the jar loaded before starting, and it cannot see the jar-sync
failure above: a start it sends can run the old version and read STARTED.
`ACCOUNT NOT STARTED` tells you to re-run the install if the collector log
shows "Adapter jar synchronization failed", and a `NOTE` line says the same
whenever the installer sent a start. If an account is still FAILED after
its two starts, do the by-hand steps above. A green install still says
nothing about a collection cycle: verify one.

## Third mode (2026-11-06, vsanperf 0.0.0.7 on devel 8.18): a NEW kind never arrives

The Cloud Proxy fetches a new or updated jar from the analytics node with a
30 s wait on its "Sync Adapters" request (whether that wait is configurable
was not tested). On the devel 8.18 proxy the
transfer took 31.5 s: `Did not receive response from Controller for 'Sync
Adapters' task`, then `FileNotFoundException: …/plugins/inbound/vcfcf_vsanperf.jar`.
Nothing retries. For an upgrade this is the second mode above (old jar keeps
running). For a kind the proxy has never had there is nothing to fall back
to: every start and stop of an instance placed there fails with `Unknown
adapter type is specified in collector configuration (Type = <kind>)`, the
account sits FAILED with an empty status message, and the installer's
restart watch cannot help because nothing can load. The same proxy overran
the wait 4 times out of 14 since 2026-10-23.

Correction (2026-11-11): the 30 s wait exists on 8.18 collectors only. The
9.0.2 and 9.1.1 proxies waited 93 to 426 s for the same reply and then loaded
the adapter, with no timeout line in any kept log; the earlier reading that
the 9.0.2 proxy "got its file at ~30 s" was an inference. The start race
(first and second modes) still happens on 9.x. The per-collector truth is the
collector log line `'<kind>' adapter version: <v>`, readable without SSH:
`knowledge/context/api-surface/2026-11-11-collector-adapter-sync-signals.md`.

What to do: after installing a NEW kind, before creating an instance on a
remote collector, confirm `plugins/inbound/<kind>.jar` (or the kind's
directory next to the other paks) exists on that proxy, by SSH or the UI
Support Logs browser (collector.log "Sync Adapters"). If it is missing,
re-run the install, which re-sends the Update Adapters task (this fixed the
upgrade case on 10-28; for a NEW kind it is untested, issue #314), and if the
jar is still absent restart the collector service on the proxy (also
untested) before placing an instance; do not create or start the instance
until the jar is there. Tooling follow-up: issue #314 (verify each proxy
received the jar before the install reports success). Evidence:
`knowledge/context/investigations/2026-11-06-vsanperf-proxy-logs.md`.
