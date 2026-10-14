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

## Step 1 outcome (devel, 2026-10-14)

0.0.0.94 installed 8:39 to 8:55 AM; /api/solutions 0.0.0.94 at 8:46 AM; pak
results all successful; adapter jar 606f04e2 matches the pak; same three
account ids, STARTED and DATA_RECEIVING; full cycles at 8:48 and 8:54 AM with
collection-complete lines and no certificate or SSL errors; wld01
overrides_status OK; Rollup|All fresh (mgmt 67/60/76.49, wld01 61/38/81.66,
wld02 48/42/78.87), incomplete 0. One transient Suite API read timeout on mgmt
cleanup at 8:53 AM, not certificate related. PASS.

## Step 2 outcome (release, 2026-10-14)

PR #49 merged (squash e92baab); read back PR MERGED, main at e92baab,
build_number 94; tag v1.0.0.94 pushed, guard clear; release run 38576298501
success; asset vcfcf_sdk_compliance.1.0.0.94.pak sha256 ce738ab1306d378b...
PASS.
