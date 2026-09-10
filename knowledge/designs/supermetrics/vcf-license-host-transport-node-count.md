# NSX Host Transport Node Count

- **Type:** supermetric
- **Slug:** vcf-license-host-transport-node-count
- **Authored YAML:** supermetrics/vcf_license_host_transport_node_count.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Number of ESXi hosts prepared as NSX host transport nodes (vs edge nodes). This is the
  "how many hosts actually use NSX" number the text widget tells the reader to compare
  against vSphere host count.
- Feeds NSX Usage Insights (NSX vSphere Hosts), NSX Consumption Trend, NSX Licensing Overtime.

## Spec

**Name:** `[VCF Content Factory] NSX Host Transport Node Count` (RULE-006 prefix, literal brackets, one space).
Source name: `[VCF Consumption Overview v2] Host Transport Node Count`.

**Assignment (adapter kind / resource kind):**
- `NSXTAdapter / NSXT World` (assignment)
- iterates `NSXTAdapter / TransportNode`

**Unit:** `(none)`

**Source formula (verbatim):**

```
count(${adaptertype=NSXTAdapter, objecttype=TransportNode, metric=summary|NodeType, depth=10, where= "summary|nodetype startsWith HostNode"})
```

**Rebuild formula:**

```
count(${adaptertype=NSXTAdapter, objecttype=TransportNode, metric=summary|NodeType, depth=10, where="summary|NodeType startsWith HostNode"})
```

**Raw keys used (8.18 recon status):**
- `TransportNode` `summary|NodeType` (property, addressed via `metric=`): **defined but 0 TransportNode
  objects on ro818 and prod**. Structurally valid, cannot be proven non-zero on either recon target.

**Dependencies (must be authored and policy-enabled first):**
- none

### Notes

- **Deviation (cosmetic):** source had a space after `where=` and lowercase `nodetype` inside
  the where clause while the `metric=` key is `summary|NodeType`. Ops accepted it on Scott's
  instance, which suggests the where-clause key lookup is case-insensitive, but the rebuild
  uses the exact catalog spelling `summary|NodeType` in both places. If the author has reason
  to believe the lowercase form was load-bearing, keep the source spelling and record why.
- The unused duplicate `[VCF Consumption Overview v2] Host Transport Node Core Count`
  (`fb06a31b`, identical formula, referenced by nothing) is **dropped**.
- Live-verify item: needs a lab with NSX transport nodes. On ro818 this returns no data.
