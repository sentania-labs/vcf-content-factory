# [VCF Content Factory] Compliance VM Detail

- **Type:** view (bundled in the compliance pak)
- **Slug:** compliance-vm-detail
- **Authored YAML:** content/sdk-adapters/compliance/views/compliance-vm-detail.yaml
- **Date:** 2026-09-23
- **Status:** authored 2026-09-23; ships in adapter build 61

## Initial prompt

Scott, 2026-09-23 (verbatim, relevant part):

> The host dashbaord for example should allow a user to see hosts that are in/out of compliance based on some scope World and vCenter maybe, view hosts and their compliance %, and select a host and see which metrics are not compliant (this may not be possible with ops dashboarded?, i.e. list metrics where compliance ~=1?

Derived from the approved dashboard design. Verbatim prompts live in
`knowledge/designs/sdk-adapters/compliance-v3-version-aware.md`; the
approved layout and keys in `knowledge/designs/dashboards/compliance-vms.md`.

## Vision

Feeds VMs W2. Spec: see the VMs note section New view. Keys are the adapter v3 build 60 key list
(content/sdk-adapters/compliance/README.md and docs/overview.md).
