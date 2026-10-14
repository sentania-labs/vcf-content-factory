# Approval: development and build paks on devel_9_1

- **Date:** 2026-10-14
- **From:** Scott, in session
- **Verbatim:** "vcenter accounts are added to devel 9.1 - so you should be
  clear to install any development/build paks"
- **Instance:** devel_9_1, vcf-lab-operations-devel-91.int.sentania.net
  (VCF Operations 9.1.1.0 build 25795063; primary plus Cloud Proxy
  vcf-lab-operations-devel-91-collector).

## Standing scope

- Install, upgrade and reinstall factory dev-preview paks (0.0.0.N) and the
  Python fork rc paks on devel_9_1, and the adapter accounts and the Cloud
  Proxy collector group they need to be exercised.
- Read-only log access through the UI Support Logs browser or SSH.

## Not covered

- Uninstalling Broadcom's stock packs, changing the vCenter accounts Scott
  added, global settings, prod, devel (9.0.2).

## Note

No vCenter credential is held in `.env`, so compliance and vsanhostmetrics
accounts need a credential Scott enters once in the UI (or Scott creates those
accounts); cluster-perf-risk needs none.

## Unsigned paks enabled (2026-10-14, about 2:35 PM)

devel_9_1 refused every factory pak upload with `unsigned_pak_installation.not.allowed`
even with ignoreSignatureChecking=true. Scott, verbatim: "i've enabled allowing
unsigned paks" (changed by Scott himself in the UI). Installs resume under the
standing scope. Investigation of the setting and its customer impact:
`investigations/2026-10-14-unsigned-pak-policy-9-1-1.md` (in progress).
