# [VCF Content Factory] Synology SSD Cache Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-ssd-cache
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-ssd-cache.yaml
- **summary_for:** `synology_diskstation:SynologySsdCache`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology SSD Cache
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select SSD Cache)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is the cache earning its keep and are its drives healthy: hit rates and occupancy over time, cache config, and the member NVMe drives.
- Built from the shared Synology Summary layout; layout variant for this kind: standard.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Capacity|reusable_bytes and Capacity|memory_used are defaultMonitored=false; left out. Hardware|disk_failure_count is a string property, so it displays but cannot be colored.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
