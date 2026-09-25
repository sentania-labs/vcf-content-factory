# [VCF Content Factory] Synology iSCSI LUN Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-iscsi-lun
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-iscsi-lun.yaml
- **summary_for:** `synology_diskstation:SynologyIscsiLun`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology iSCSI LUN
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select iSCSI LUN)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- How hard is vSphere driving this LUN: IOPS and throughput over the week, target config, and the VMware datastore it backs (foreign parent in S8).
- Built from the shared Synology Summary layout; layout variant for this kind: leaf: S7 is a PropertyList (iSCSI target).
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): IO|read_latency and IO|write_latency are 0 on every sample for 6 h while write IOPS reached 1112, so the adapter does not populate them. Removed from tiles and charts; IOPS and throughput kept.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
