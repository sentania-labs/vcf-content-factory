# [VCF Content Factory] Synology Disk Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-disk
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-disk.yaml
- **summary_for:** `synology_diskstation:SynologyDisk`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology Disk
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select Disk)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is this drive failing: SMART status, temperature and uncorrectable sectors with their trend, plus its IO and where it sits.
- Built from the shared Synology Summary layout; layout variant for this kind: leaf: S7 is a PropertyList (remaining hardware properties).
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): Health|remain_life is 0 on every disk, SATA and NVMe, for 6 h (never populated), so it is removed. Health|unc_sectors carries real values on SATA and a flat -1 no-data sentinel on NVMe cache drives: display rule, -1 shows as n/a and is uncolored (an NVMe page shows n/a in the tile and a flat line at -1 in S5, noted under the chart).
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
