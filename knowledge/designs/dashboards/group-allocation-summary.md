# Group Allocation Summary

- **Type:** dashboard
- **Slug:** group-allocation-summary
- **Authored YAML:** (pending)
- **Date:** 2026-10-28
- **Status:** drafted (mock pending approval, RULE-011)

## Initial prompt

> OKay.  dashboard construction.  I want two dashboards.  1 dashboard should have an object list that populates on an arbitrary list of custom group types (in devel there is a custom application group).  The user selects it and second widget provides a list view chart list of VMs in that group with CPU/Mem/Disk consumption/allocation with a summary line at the bottom.
>
> The second dashboard should contain a list view of all of those application groups listing a summary to CPU/Mem/Storage allocation for each group.
>
> Give me a mockup dashboard of this.

This file covers the second dashboard. Its sibling is `group-vm-resources.md`.

Clarification (Scott, same session, verbatim):

> it's OK with we create a new custom group type for this, I'm just referencing the ones that are there as examples.
>
> so maybe ApplicationCode or some such as the container type - which will be a set of dynamic groups populated by VM tag identify

## Vision

- One list view, one row per group of the same custom group types, with CPU, memory and storage allocation summed over the group's VMs.
- Audience: the same admin comparing applications against each other.

Decision (Scott, verbatim): "(Custom) Application  use this for now, to use the existing groups.  i'm mostly trying to get a workign mockup and an example of dashboard 2 to build for a customer."

- Subject: every group of the existing devel type `(Custom) Application`. Allocation only.
- Name: `[VCF Content Factory] Application Allocation` (dashboard; shortened under the 50-char editor cap, #198; the view keeps "Application Allocation Summary"), folder `VCF Content Factory`. Mock: `group-allocation-summary.html`. Meant as the customer example.

## Wireframe (RULE-011)

| Widget | x | y | w | h | Type | Subject | Content |
|---|---|---|---|---|---|---|---|
| W1 Allocation by application | 1 | 1 | 12 | 9 | View (List) | all `Container` / `(Custom) Application` groups | view `[VCF Content Factory] Application Allocation Summary` |

No interactions.

Super metrics, each evaluated on `Container` / `(Custom) Application`, over child VMs (depth 1):

| SM | Formula intent | Unit |
|---|---|---|
| `[VCF Content Factory] Application VM Count` | count of VMWARE VirtualMachine children | count |
| `[VCF Content Factory] Application vCPU Allocated` | sum `config|hardware|num_Cpu` | vCPU |
| `[VCF Content Factory] Application Memory Allocated (GB)` | sum `mem|guest_provisioned` / 1048576 | GB |
| `[VCF Content Factory] Application Storage Provisioned (GB)` | sum `diskspace|provisionedSpace` | GB |

View columns: Application (name), then the four SMs in that order. Summary row: Sum on all four.
