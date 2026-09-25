# [VCF Content Factory] Synology Storage Pool Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-storage-pool
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-storage-pool.yaml
- **summary_for:** `synology_diskstation:SynologyStoragePool`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology Storage Pool
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select Storage Pool)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is the RAID healthy: status and RAID level, member disk temperatures, and every member disk's SMART state. How full it is stays in the layout but is blocked until the adapter reports pool capacity correctly.
- Built from the shared Synology Summary layout; layout variant for this kind: standard (S6 is a per-child MetricChart over member disks).
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): Capacity|used_bytes equals Capacity|total_bytes on every sample for 6 h while Configuration|status reads normal, so usage_pct is a constant 100 from an adapter mapping bug. S3 and S5 keep their slots, greyed and BLOCKED on an adapter fix (Synology issue to be filed); no capacity colors or trends until then. Configuration|disk_count is defaultMonitored=false; left out.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
