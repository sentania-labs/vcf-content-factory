# Approval: compliance v1.0.0.93 on prod (vcf-lab-operations, 9.1.1)

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "go ahead and install 93", then, after being told the qa
  profile is the prod appliance and what the upgrade changes: "yes install
  v1.0.0.93 from the github release"
- **Pak:** GitHub Release v1.0.0.93 of
  sentania-labs/vcf-content-factory-sdk-compliance, asset
  `vcfcf_sdk_compliance.1.0.0.93.pak`, sha256
  ae42689c336529ae1c33444e0d4a645208102e448d4c6b3b880347b1140b58c5 (matches
  the release's published digest). CI-built from main 9d0e985.
- **Upgrade from:** 1.0.0.80.

## Scope

- Record every compliance account's id, name, stored settings and credential
  id before the upgrade (GET only).
- Upgrade-install on prod (profile prod) with content force-update; verify by
  the installed solution version, the pak results file and the jar hash, not
  the CLI's OK line.
- After: same account ids; Validate Connection on each account (accept the
  vCenter certificate where prompted; the old Allow Insecure setting is gone);
  re-enter a host by its certificate name only if an account was entered by
  IP, after reporting it; confirm collection; read the ComplianceWorld Summary
  tab clone state (expected possibly blank on 9.1.1, see
  investigations/2026-10-13-first-party-summary-binding.md Addendum 2).

## Not covered

- Any other instance, any non-compliance change, deleting anything, rebinding
  the Summary tab, the stuck admin dashboards.
