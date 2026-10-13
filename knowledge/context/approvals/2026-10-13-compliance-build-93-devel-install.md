# Approval: compliance build 93 devel install

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "go ahead and do the build 93 install."
- **Pak:** dist/vcfcf_sdk_compliance.0.0.0.93.pak, sha256
  6c436c55136d4b2640dc297b5e7710f7bf85cb91ddd58406fff88395115d941c (adapter
  HEAD 54ca857 on feat/build-93-auto-only-cert-accept). Review:
  knowledge/context/reviews/compliance-build-93.md (APPROVE on re-review,
  nit confirmation pending at the time of this record).

## Scope this covers (devel only)

- Upgrade-install over build 92 with content force-update; version verified
  on /api/solutions.
- Identity: record the three accounts before; same ids after; save wld01
  unchanged.
- Certificate flow on wld01 (its certificate was untrusted; it ran with
  Allow Insecure true): Validate Connection shows the accept dialog;
  accept; Validate passes; next cycle collects. Same on wld02. mgmt
  (trusted) validates with no prompt.
- Name check: re-enter wld01's host as its IP, Validate (expect the name
  message), restore the FQDN.
- Not-collected marker: one cycle with wld01 unreachable (point the host at
  a name that does not resolve, wait one cycle, expect Rollup|incomplete 1
  and the vCenter collection alert), then restore and confirm recovery.
- Account dialog shape, Auto only, the overrides file still in force, the
  stored-value INFO/WARN lines if they fire.
- Accepted certificates on the three accounts stay accepted afterwards.

## Not covered

- prod or qa, pushes, PRs, tags, other instance changes.

## Outcome 2026-10-13

Installed 4:19 PM, version 0.0.0.93 on /api/solutions, pak results all
successful, jars match. Identity PASS: same three account ids, the two
removed settings no longer stored, wld01 saved twice without error. Dialog
PASS: Host, Credential, Collector; Advanced Settings holds Overrides file and
Read vCenter appliance settings only. Validate PASS on all three FQDNs with
no prompt: devel's vCenter certificates chain to the lab CAs already in the
platform trust store, so the accept path could not be exercised on the
FQDN. The accept dialog did appear when validating wld01 by IP
(172.27.8.32), and after acceptance Validate failed with the name-mismatch
message as designed (name check PASS). Not-collected marker NOT PROVEN: the
test changed the host to a non-resolving name, so the adapter could not
resolve the vCenter object (no VCURL equal to the entered host) and, as
documented, pushed nothing; a test that keeps the real host and breaks the
credential is needed. All three accounts restored to FQDNs and collecting at
4:51 PM; overrides in force (1 skipped, 1 overridden, VM pin SCG 8.0).
Transient: overrides_status read "fetch failed: no answer
(SocketTimeoutException), last good from 4:29 PM" at 4:52 PM while mgmt and
wld02 also logged Suite API read timeouts at 4:50 PM; cached copy applied.
No stored-value INFO/WARN lines fired (the platform does not hand the
adapter removed identifiers). Screenshots in the session scratchpad shots/:
build93-wld01-dialog.png, build93-wld01-cert-dialog.png,
build93-wld01-ip-validate.png.
