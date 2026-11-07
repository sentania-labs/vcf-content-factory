# Baseline Tree Pak Documentation

> Generated index. The SVG diagram and per-kind table are regenerated on every
> build; prose sections (overview, installing) are hand-curated.

## Contents

| Section | Description |
|---------|-------------|
| [Overview](overview.md) | What's in the pack, resource kinds, cross-adapter notes |
| [Installing & Configuring](installing.md) | Prerequisites, configuration fields, step-by-step guide |
| [Inventory Tree](inventory-tree.md) | Traversal spec, per-kind table with identifying keys |
| [Metrics Reference](../REFERENCE.md) | Full metrics and properties reference (generated) |

## Inventory Tree

![Inventory Tree](inventory-tree.svg)

## Cross-MP Relationships

These edges are created at collection time via the Suite API and never appear in `describe.xml`. They are declared explicitly in `adapter.yaml` (`cross_mp_edges`) so this generated docset doesn't silently omit them. *Italic* endpoints belong to a foreign management pack; `code` endpoints are owned by this adapter.

| Parent | Child | Description |
|--------|-------|-------------|
| *VMWARE HostSystem* (foreign, VMWARE) | `BaseSwitchPort` | Per-vmnic LLDP join via Suite API; additive, optional |

## Quick Reference

- **Adapter kind:** `baseline_tree`
- **Version:** 1.2.3.7
- **Traversal spec:** Baseline Traversal
- **Resource kinds:** 4
- **Cross-MP relationships:** 1 (see [Cross-MP Relationships](#cross-mp-relationships) below)
