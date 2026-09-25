# [VCF Content Factory] Synology Volume Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-volume
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-volume.yaml
- **summary_for:** `synology_diskstation:SynologyVolume`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology Volume
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select Volume)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- How busy is the volume, is the SSD cache helping, and what it serves: NFS exports and iSCSI LUNs side by side. How full it is stays in the layout but is blocked until the adapter reports free space correctly.
- Built from the shared Synology Summary layout; layout variant for this kind: standard, S7 split into two half-width Views (NFS exports | iSCSI LUNs) because a volume has two primary child kinds.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): Capacity|free_bytes is 0 on every sample for 6 h while IO is active and status is normal, so usage_pct is a constant 100 from an adapter bug. Capacity tiles are off S3; S5 keeps its slot greyed and BLOCKED on an adapter fix (Synology issue to be filed). Cache|cache_write_hit_rate is left to the SSD cache page.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
