# [VCF Content Factory] Synology DiskStation Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-diskstation
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-diskstation.yaml
- **summary_for:** `synology_diskstation:SynologyDiskstation`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology Diskstation
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select Diskstation)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is the NAS itself healthy: temperature, CPU, memory and NFS load over the week, DSM version and fan, and its storage pools.
- Built from the shared Synology Summary layout; layout variant for this kind: standard.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: CPU|cpu_total_load, cpu_user_pct and cpu_system_pct read 0 in the v1 baseline while cpu_load_* did not, so the design uses cpu_load_*. Memory byte keys looked like KiB in v1 (memory_total=20328576 on a 20 GB box); the design uses Memory|memory_usage_pct only.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
