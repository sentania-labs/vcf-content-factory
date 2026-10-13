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
