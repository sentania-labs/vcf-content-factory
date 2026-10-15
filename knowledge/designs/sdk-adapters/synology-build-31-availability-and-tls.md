# Synology build 31: safe TLS default, login back-off, optional endpoints, reconfigure leak, relationship NPE

- **Type:** managementpack (Tier 2 SDK adapter change), build 31 (main is v1.0.0.30)
- **Slug:** synology-build-31-availability-and-tls
- **Adapter repo:** `content/sdk-adapters/synology/` (branch from `origin/main`, not from the parked `feat/dashboards` branch)
- **Date:** 2026-10-15
- **Status:** go from Scott 2026-10-15; authoring queued behind the UniFi build 14 (serial authors)

## Initial prompt (Scott, verbatim, 2026-10-15)

> prioritize the unif and synology pak fixes - then work on some more of
> the frameowkr ones in conjunction with the compliance stuff

## Why

Same 2026-09-24 review, same open High findings, same failure classes as
UniFi build 14 and compliance builds 94 and 95. Synology adds two of its
own: a failed login per resource can trip DSM Auto Block against the
collector's IP (which other integrations may share), and one optional
endpoint failing discovers nothing at all.

## Scope (fork issues, in priority order)

1. **#15** `allowInsecure` defaults to `false`; strict parse; docs and
   CHANGELOG upgrade note.
2. **#12** cache a failed login or snapshot for the rest of the cycle and a
   back-off window; never retry login on an authentication-class DSM error;
   exponential back-off across cycles after consecutive auth failures; one
   WARN.
3. **#13** per-cycle budget: after the first snapshot build fails the
   remaining resources fail immediately; shorter connect timeout than read
   timeout if the framework client exposes it; abort check between
   resources.
4. **#14** only DSM info, system info, utilization and storage load_info are
   required; every other endpoint is wrapped like UPS already is (WARN once,
   empty JSON, dependent metrics and relationships skipped); document the
   minimum DSM privileges.
5. **#21** reconfigure logs out the old DSM session and discards the old
   stitcher and HTTP client, best effort, sharing the teardown with
   `onDiscard()`.
6. **#19** null-safe joins in `buildRelationships` so one odd object costs
   its own edges, not the whole tree; fixture test with missing fields.

**Deferred to its own build, needs Scott's call:** **#11** multi-NAS
identity collision. Correct fix adds the DSM serial as a second uniqueness
identifier on every child kind, which recreates every existing object on
upgrade. That is an operator-visible migration, not a fix to slip in.

Out of scope here: #16/#17/#27 (secrets in query strings and logs; worth a
security build next), #18/#24/#25/#26/#34 (data correctness), #20/#28
(performance), #22/#23/#29/#30/#31 (docs, tests, compatibility).

## What must not regress

- Explicit `allowInsecure=true` instances keep working after upgrade.
- A full-privilege account on a model with fans, NFS and iSCSI collects
  exactly the keys and relationships it does today.

## Proof

- Unit tests for: strict parse; no second login after an auth error in the
  same cycle; optional endpoint failure leaves core inventory discovered;
  relationship fixture with missing `pool_path`, `location`, `id`.
- `validate-sdk`, `build-sdk` dev build 0.0.0.31, pak-compare against the
  v1.0.0.30 release pak with zero BLOCKING.
- devel_9_1 install on the standing dev-pak approval: healthy collection
  seen in the UI, then a wrong-password edit shows one WARN and no DSM Auto
  Block entry on the NAS.
