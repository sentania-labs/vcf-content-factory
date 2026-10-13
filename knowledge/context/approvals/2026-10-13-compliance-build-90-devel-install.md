# Approval: compliance build 90 devel install and evaluation

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "let's intall and evaluate 90 on devel"
- **Pak:** dist/vcfcf_sdk_compliance.0.0.0.90.pak, sha256
  26323577ab88a84a36c7fe182ce2435b4924521e6df3c50a3528ca4e3cb7b4c4 (adapter
  commit eae8658 on feat/build-90-overrides-file), pending the third review pass
  (knowledge/context/reviews/compliance-build-90.md) returning APPROVE.

## Scope this covers (devel only)

- Upgrade-install over build 89 with content force-update.
- Evaluation per the design's devel check
  (knowledge/designs/sdk-adapters/compliance-overrides-file.md): create one
  user copy of the shipped template in Administration > Configuration Files
  (name `compliance_overrides_wld01`), carrying one Skip, one Override on the
  ESX account lockout attempts control, and one Profile pin for
  VirtualMachine; set the **wld01** instance's new Overrides file setting to
  that name (the one instance setting change this approval covers); after two
  cycles, read the results; then replace the copy with malformed XML to see
  the alert, then restore it.
- Read-only evidence for DEF-022 (unset settings now fail), DEF-024
  (dvfilter), and the empty-value exception on real hosts.

## Not covered

- Other instance settings, prod or qa, pushes, PRs, tags, the Summary
  rebind (parked).

## Amendment 2026-10-13, 11:12 AM

Build 90 failed to install (describe rejected: the new overrides alert wrapped
one symptom set in a composite container; devel rolled back to 89, instances
unaffected). Build 91 is build 90 plus that describe fix. The same scope and
evaluation plan apply to the build 91 pak under this approval.

## Outcome 2026-10-13

Build 91 installed 11:30 to 11:33 AM, version 0.0.0.91 confirmed on
/api/solutions. Evaluation per plan PASS, except the Skip's existing alert
did not clear (adapter issue #41). Left on devel under this approval: config
file `compliance_overrides_wld01.xml` (valid content) and the wld01 instance
Overrides file setting pointing at it.
