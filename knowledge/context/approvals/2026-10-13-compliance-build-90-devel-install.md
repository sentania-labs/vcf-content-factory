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
