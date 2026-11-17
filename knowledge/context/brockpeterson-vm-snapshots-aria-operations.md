# Everything you wanted to know about VM Snapshots in Aria Operations (summary)

- **Title:** Everything you wanted to know about VM Snapshots in Aria Operations
- **Author:** Brock Peterson
- **URL:** https://www.brockpeterson.com/post/everything-you-wanted-to-know-about-vm-snapshots-in-aria-operations
- **Published:** 2024-11-17 (updated 2025-10-23)
- **Retrieved:** 2026-07-27

This is the factory's summary of a community blog post, not a copy of it.
Read the original at the URL above.

## Summary

Brock Peterson lists the VM snapshot metrics and properties that Aria
Operations collects, explains which ones overlap, and points out the
behaviour that surprises people: when the per-snapshot properties
appear, what the Age value means before then, and why the size shown in
Operations differs from the size vCenter reports. He closes with how the
two vSphere World snapshot disk metrics are computed from Datacenter and
Cluster values.

## Facts the factory relies on (credit: Brock Peterson)

- Snapshot properties appear once the snapshot is **24 hours** old. Disk
  and snapshot-count metrics appear at the next collection; the rest
  arrive after 24 hours.
- The snapshot Age property reads `-1` by default, including on a VM with
  no snapshot. It stays `-1` until a snapshot is 24 hours old and returns
  to `-1` when the snapshot is deleted.
- The snapshot Creator and Description properties are not activated in
  the default policy.
- Summary | Reclaimable Snapshot Space is computed once a day, so it can
  differ slightly from the other snapshot space metrics.
- The snapshot size in Operations covers the `-delta.vmdk` only, while
  vCenter counts all snapshot files, so the two figures differ.
- vSphere World "Disk Space Realized - VM Snapshots" is the sum of the
  Datacenter values, and "Disk Space Reclaimable - VM Snapshots" is the
  sum of the Cluster reclaimable values (computed daily).

Digested in
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`.
