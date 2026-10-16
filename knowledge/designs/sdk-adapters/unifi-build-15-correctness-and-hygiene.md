# UniFi build 15: correctness, hygiene and docs findings that need no design call

- **Type:** managementpack (Tier 2 SDK adapter change), build 15 (main is v1.1.0.14, untagged)
- **Slug:** unifi-build-15-correctness-and-hygiene
- **Adapter repo:** `content/sdk-adapters/unifi/` (branch from `origin/main`)
- **Date:** 2026-10-16
- **Status:** merged to unifi main (6c3c66d, PR #36, 2026-10-16), not tagged; devel_9_1 proof pending

## Initial prompt (Scott, verbatim, 2026-10-16)

> the fork paks are enhancedments we will tackle.  let's focus on the
> compliance, unif, synology, and template.  Triage them, order them, and
> let's fix them all in this session.

## Scope (fork issues, in order)

1. **#34** resolve the `UniFiApiClient` component logger once in
   `configureAdapter`, store it on `Configured`, pass it to the login
   callback and Test Connection; extend `tests/test_snapshot_logger_once.py`.
2. **#24** discard the previous `httpClient` and `suiteStitcher` in
   `configureAdapter`; return the raw login client with the main one (a
   holder) so `getTester`'s finally and `onDiscard` discard both.
3. **#23** one shared guard: skip (DEBUG) devices and cameras with an empty
   MAC and ports with no `port_idx`, in `enumerateResources`,
   `buildRelationships` and the snapshot index alike.
4. **#22** percent-encode the site name as one path segment in
   `UniFiApiClient` (match what `UniFiStitcher` does).
5. **#18** `device_count` from the snapshot (adopted devices for the site);
   `version` from `stat/sysinfo`, `timezone` from sysinfo or site settings;
   if neither is reachable in the API, drop the two attributes from
   `describe.xml` and say so.
6. **#14** publish `Status|state` (1 connected, 0 otherwise) on gateway,
   switch and access point; when not connected publish state only and skip
   the performance metrics; everywhere, publish a metric only when the field
   is present (a `metricIfPresent` helper), never 0.0 for absent.
7. **#16** (2) `Status|seconds_since_last_motion` replaces the epoch value
   (keep the key name only if renaming breaks the approved dashboards;
   check `content/sdk-adapters/unifi` dashboards and the parked
   `feat/dashboards` branch is out of scope, main has no dashboards);
   (3) `recording_retention_days` numeric property replaces
   `recording_retention_mode`.
8. **#16** (1) + **#29** WAN `Traffic|tx_bytes` / `rx_bytes` relabelled as
   cumulative `bytes`; add UniFi's own `-r` rate fields as new
   `Traffic|tx_rate` / `rx_rate` (bytes/s) keys on SwitchPort, Radio and
   WanInterface where the payload has them, keep the counters.
9. **#21** vmnic stitch: one bulk Suite API properties call (or a few
   batches) instead of one per host; refresh the stitch at most every 15
   minutes and reuse the last good result between refreshes; Protect
   bootstrap cached the same way unless a lighter endpoint exists.
10. **#27** docs items 1 to 3: TLS default consistent (build 14 made it
    false), replace "LLDP-based stitching" with the vmnic stitch
    description and its Suite API requirement, add an Account section
    (dedicated local View Only account, no SSO, no MFA).
11. **#32** README Configuration path: Administration > Integrations >
    Accounts.

Waiting on Scott's decision, not in this build: #15 (traversal tree
shape), #17 (classic controller support or drop the claim), #20 (stale
resource handling), #27 item 4 (display names), #30 (symptoms and alerts
content), #28 (CI, handled from the template).

## What must not regress

- Build 14 behaviour: TLS default, SnapshotCache back-off, SiteReads
  isolation, DOWN mapping. All existing tests pass.
- Existing metric keys keep their names except the two in item 7, which
  are renamed deliberately and noted in the CHANGELOG.

## Proof

- Unit tests per item where the code is SDK-independent.
- `validate-sdk`, `build-sdk` dev build 0.0.0.15, pak-compare against the
  build 14 pak with zero BLOCKING.
- Reviewer gate, peer review, PR, Codex round, merge, no tag. devel_9_1
  install under the standing approval to see state, rate keys and the
  stitch refresh working.
