# UniFi build 14: safe TLS default, failure caching, snapshot timing, per-site isolation

- **Type:** managementpack (Tier 2 SDK adapter change), build 14 (main is v1.1.0.13)
- **Slug:** unifi-build-14-availability-and-tls
- **Adapter repo:** `content/sdk-adapters/unifi/` (branch from `origin/main`, not from the parked `feat/dashboards` branch)
- **Date:** 2026-10-15
- **Status:** merged to unifi main (cdf0476, PR #35, 2026-10-15); proven on devel_9_1; not tagged

## Initial prompt (Scott, verbatim, 2026-10-15)

> prioritize the unif and synology pak fixes - then work on some more of
> the frameowkr ones in conjunction with the compliance stuff

## Why

The 2026-09-24 adversarial review left the UniFi pak's High findings open.
Three of them are the same failure classes compliance fixed in builds 94
and 95 this week: a trust-everything default, a login retried per resource
with no back-off, and a cycle that can run far past its interval. One more
(a snapshot stamped before it is built) makes the cycle cost scale with the
number of resources.

## Scope (fork issues, in priority order)

1. **#13** `allowInsecure` defaults to `false` in `describe.xml` and README;
   parse strictly (`"true"` means insecure, anything else verifies); one WARN
   per configure while insecure mode is on; CHANGELOG upgrade note that
   existing instances keep their stored value.
2. **#11** cache a failed snapshot build for the rest of the cycle and for a
   back-off window; after an authentication-class response (401/403/429) do
   not log in again until the configuration changes or the back-off expires;
   fail the remaining resources fast from the cached failure; one clear WARN.
3. **#12** stamp `Snapshot.builtAt` when `build()` finishes, and make one
   build per collection cycle explicit rather than wall-clock only.
4. **#19** a failed per-site `stat/device` call marks that site failed and
   the other sites collect; the whole snapshot fails only when `/self/sites`
   fails or every site fails.
5. **#25** map timeouts and unknown-host to DOWN like `ConnectException`
   (small, same code path as 2).

Out of scope for this build: #14 (device state model is a design choice),
#20 (stale-object cleanup), #21 (stitch cost), #15/#16/#17/#18 (data
correctness), content issues #29/#30, docs #27, CI #28. Those stay open.

## What must not regress

- An explicit `allowInsecure=true` instance keeps working after upgrade.
- A healthy controller collects exactly as before: same keys, same
  relationships, same snapshot reuse across resources in a cycle.
- Test Connection reports a certificate failure as a certificate failure.

## Proof

- Unit tests for: strict parse; failure cache (second resource in the same
  cycle does not call login); `builtAt` after a slow build; one failed site
  leaves the others collected.
- `validate-sdk`, `build-sdk` dev build 0.0.0.14, pak-compare against the
  v1.1.0.13 release pak with zero BLOCKING.
- devel_9_1 install on the standing dev-pak approval: healthy collection
  seen in the UI, then a wrong-password edit shows one WARN and a fast
  failed cycle rather than a login storm (count logins in the collector log).
