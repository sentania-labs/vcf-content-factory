# Approval: compliance build 92 devel install

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "go ahead and install to devel"
- **Pak:** dist/vcfcf_sdk_compliance.0.0.0.92.pak, sha256
  d212c9706f5abc3336220fb63df592e5b38c499a537c19ab2dad93c02a58bb34 (adapter
  HEAD f22c3d8 on feat/build-90-overrides-file; pak content from ddaf06e,
  later commit is test-only). Review: knowledge/context/reviews/compliance-build-92.md
  (APPROVE, re-review APPROVE, R-W1 closed by f22c3d8).

## Scope this covers (devel only)

- Upgrade-install over build 91 with content force-update.
- Identity check on the wld01 account (record before, confirm same id after,
  save unchanged), the same read-only checks on mgmt and wld02.
- Evaluation per the build 92 design: the two shell-timeout alerts on the
  wld01 hosts cancel within three cycles; lockout override and VM pin still
  in force; instance setting no longer offers Custom; Suite API call rate
  unchanged with a Skip in force.
- The existing `compliance_overrides_wld01.xml` copy and the wld01 setting
  stay as they are.

## Not covered

- Any other instance setting change, prod or qa, pushes, PRs, tags.

## Outcome 2026-10-13

Installed 2:44 to 2:49 PM, version 0.0.0.92 on /api/solutions, pak results
all successful, jar matches. Identity: all three account ids and stored
settings unchanged except custom_profile_path no longer stored; wld01 saved
unchanged at 2:54 PM with no error. Skip pushes -1 every cycle (samples
2:45, 2:52, 2:58, 3:03 PM on both hosts); overrides and VM pin in force;
Suite API POST count per two cycles 1182 before and after. Not proven: the
Skip alert cancel, because both shell-timeout alerts were already CANCELED
at 1:10 and 1:15 PM before the upgrade (not by the adapter: no samples after
11:54 AM). Proof needs the alerts re-fired (remove the Skip, then restore),
which is outside this approval.
