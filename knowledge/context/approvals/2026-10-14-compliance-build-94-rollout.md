# Approval: compliance build 94 rollout (devel, then release, then prod)

- **Date:** 2026-10-14
- **From:** Scott, in session
- **Verbatim:** "okay do the build and install it to devel, verify it works,
  then tag a release and install that to ops \"prod\""
- **Context:** prod (vcf-lab-operations, 9.1.1) has collected nothing since
  v1.0.0.93 was installed 2026-10-13 (incident record
  2026-10-13-compliance-v1.0.0.93-prod-install.md); build 94 is the fix
  (adapter PR #49, review reviews/compliance-build-94.md, APPROVE twice).

## Scope, in order, each step gated on the previous one passing

1. Devel: upgrade-install dist/vcfcf_sdk_compliance.0.0.0.94.pak (sha256
   121e8b96..., the reviewed build); verify version, pak results, jar, the
   three accounts keep their ids and complete a full collection cycle with no
   certificate error; wld01 overrides still OK.
2. Release: merge adapter PR #49 to main once green; tag v1.0.0.94 only after
   reading back PR state MERGED, local main fast-forwarded to the merge commit,
   and build_number 94 at HEAD; watch the release workflow to success.
3. Prod: install the v1.0.0.94 GitHub Release asset (hash checked against the
   release digest); verify version, pak results, jar on both nodes; same three
   account ids; if any account is FAILED after the upgrade (the
   start-monitoring race on collector01), Start Collecting on that account;
   confirm a full cycle with no certificate error on all three and record the
   new Rollup values.

## Not covered

- Any other instance, any account setting change, rotating credentials,
  rebinding the Summary tab, the expired root passwords.
