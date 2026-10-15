# Approval: development and build paks on all three devel instances

- **Date:** 2026-10-15
- **From:** Scott, in session
- **Verbatim:** "we need to verify funcationality against all 3 versions in
  devel"
- **Context:** asked right after the per-instance inventory showed devel
  (9.0.2) behind on every pak and devel_8_18 (8.18.7) empty. Extends the
  2026-10-14 devel_9_1 approval to the other two devel instances.
- **Instances:** devel (vcf-lab-operations-devel, 9.0.2.0), devel_9_1
  (vcf-lab-operations-devel-91, 9.1.1.0), devel_8_18
  (vcf-lab-operations-devel-8, 8.18.7).

## Standing scope

- Install, upgrade and reinstall factory dev-preview paks (0.0.0.N) and the
  Python fork paks on the three devel instances, with the adapter accounts
  and collector groups they need to be exercised.
- Read-only log access through the UI Support Logs browser or SSH where it
  works.

## Not covered

- Prod, in every form.
- Uninstalling anything, including the retired vCommunity pak still on devel
  9.0.2 (an uninstall is a delete and needs its own go).
- Global settings on any instance; Broadcom stock packs; the vCenter
  accounts Scott created.
- SSH-based evidence on 8.18 (issue #212 step 1) is still gated on Scott
  providing access.
