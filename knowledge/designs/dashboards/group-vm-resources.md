# Group VM Resources

- **Type:** dashboard
- **Slug:** group-vm-resources
- **Authored YAML:** (pending)
- **Date:** 2026-10-28
- **Status:** drafted (mock pending approval, RULE-011)

## Initial prompt

> OKay.  dashboard construction.  I want two dashboards.  1 dashboard should have an object list that populates on an arbitrary list of custom group types (in devel there is a custom application group).  The user selects it and second widget provides a list view chart list of VMs in that group with CPU/Mem/Disk consumption/allocation with a summary line at the bottom.
>
> The second dashboard should contain a list view of all of those application groups listing a summary to CPU/Mem/Storage allocation for each group.
>
> Give me a mockup dashboard of this.

This file covers the first dashboard. Its sibling is `group-allocation-summary.md`.

Clarification (Scott, same session, verbatim):

> it's OK with we create a new custom group type for this, I'm just referencing the ones that are there as examples.
>
> so maybe ApplicationCode or some such as the container type - which will be a set of dynamic groups populated by VM tag identify

## Vision

- Pick one custom group from a list that shows groups of a configurable set of custom group types (devel: the custom application group type), then see that group's VMs in a list view with CPU, memory and disk consumption and allocation per VM, plus a summary (totals) row.
- Audience: an admin answering "what does this application use and what has it been given".

Decision (Scott, verbatim): "(Custom) Application  use this for now, to use the existing groups.  i'm mostly trying to get a workign mockup and an example of dashboard 2 to build for a customer."

- Group type: the existing devel type `(Custom) Application` (adapter `Container`, key = name). No new type. Six dynamic groups (LabApp1..6, rule VM tag `bwtest-application` EQ AppN); 3 VMs in LabApp1/2/4.
- Name: `[VCF Content Factory] Application VM Resources`, folder `VCF Content Factory`. Mock: `group-vm-resources.html`.

## Wireframe (RULE-011)

12-column grid.

| Widget | x | y | w | h | Type | Subject | Content |
|---|---|---|---|---|---|---|---|
| W1 Applications | 1 | 1 | 4 | 9 | ResourceList | `resource_kinds: [{adapter_kind: Container, resource_kind: "(Custom) Application"}]` (a list; more group types can be added) | group picker, name column |
| W2 VMs in selected application | 5 | 1 | 8 | 9 | View (List) | VirtualMachine children (depth 1) of the selected group | view `[VCF Content Factory] Application VM Resources` |

Interaction: W1 selection -> W2 (view resource = selected group).

View `[VCF Content Factory] Application VM Resources` (VMWARE VirtualMachine), columns, all native metrics confirmed on devel VMs:

| Column | Key | Unit / transform | Summary |
|---|---|---|---|
| VM | name | | "Total" |
| vCPU | `config|hardware|num_Cpu` | count | Sum |
| CPU used | `cpu|usagemhz_average` | MHz | Sum |
| CPU usage | `cpu|usage_average` | % | Average |
| Memory allocated | `mem|guest_provisioned` | KB -> GB | Sum |
| Memory consumed | `mem|consumed_average` | KB -> GB | Sum |
| Disk provisioned | `diskspace|provisionedSpace` | GB | Sum |
| Disk used | `diskspace|used` | GB | Sum |

Summary row: the list view's native summary row (Sum, Average for usage %). Not drawn: a trend chart.
