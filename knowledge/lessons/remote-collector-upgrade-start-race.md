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
