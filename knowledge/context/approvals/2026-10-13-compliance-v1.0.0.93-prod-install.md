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

## Outcome so far (2026-10-13, 11:10 PM)

Installed 10:39 to 10:41 PM: /api/solutions 1.0.0.93; pak results all
successful; adapter jar 07115606 on both nodes matches the release. Same three
account ids (mgmt 1fc78d19, wld01 78497279, wld02 cb8f2737), all on collector01
(172.27.8.52). Before: every account stored allowInsecure=true; after each
save those identifiers were gone. Validate Connection showed the accept dialog
on all three (issuer sentania Lab Issuing 2), accepted, test passed. **But all
three accounts are resourceState FAILED, GREY, empty message, no collection
since 10:08 PM** (last 1.0.0.80 cycle). Summary binding exists
(f72ad9cf), all six widgets isLoading (blank clone, as predicted for 9.1.1
without a templates importer). Root cause under investigation on collector01,
read-only.
