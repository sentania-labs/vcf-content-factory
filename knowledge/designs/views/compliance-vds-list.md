# [VCF Content Factory] Compliance Distributed Switches

- **Type:** view (bundled in the compliance pak)
- **Slug:** compliance-vds-list
- **Authored YAML:** content/sdk-adapters/compliance/views/compliance-vds-list.yaml
- **Date:** 2026-09-23
- **Status:** authored 2026-09-23; ships in adapter build 61

## Initial prompt

Scott, 2026-09-23 (verbatim, relevant part):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

Derived from the approved dashboard design. Verbatim prompts live in
`knowledge/designs/sdk-adapters/compliance-v3-version-aware.md`; the
approved layout and keys in `knowledge/designs/dashboards/compliance-vcenter-networking.md`.

## Vision

Feeds vCenter & Networking W4. Spec: columns in the wireframe row W4. Keys are the adapter v3 build 60 key list
(content/sdk-adapters/compliance/README.md and docs/overview.md).
