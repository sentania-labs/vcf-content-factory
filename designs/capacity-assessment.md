# Design Artifact: Capacity Assessment & Right-Sizing

## Provenance

This is a **retroactive design artifact**. The capacity-assessment
bundle was authored in a single commit (`e9217af`, 2026-04-11) as a
16-file drop without a design trail — 9 days before the
plan-mode-plus-design-artifact discipline was codified (memory note
`feedback_plan_mode_for_content_requests.md`). No original prompt,
no mockup, no decisions record exists.

This document reconstructs intent from the shipped YAML, then
redesigns the one section found to be structurally broken (the
Right-Sizing Scoreboard) so future changes have something to
anchor against. The Capacity section is preserved as-authored and
its intent captured retroactively; it is not being re-scoped here.

## Scope and Intent

- **Audience**: VCF Ops admin doing a quarterly capacity review or
  a pre-deployment sanity check on a vSphere environment. Not a
  real-time operations dashboard — a *planning* dashboard.
- **Core question**: "Can I take on more workload, and if not, where
  can I find capacity?" Two sub-questions shape the two sections.
  - **Capacity section**: how much headroom exists, post-HA, and
    where is it? Which clusters are already tight?
  - **Right-Sizing section**: where has VCF Ops's capacity engine
    already identified reclamation opportunity inside existing
    workloads? Oversized, undersized, idle VMs.
- **Scope**: entire environment. Self-provider widgets pinned to
  `vSphere World`. No cluster/datacenter picker — this is an
  environment-wide snapshot, not a drill-down tool.
- **Framing bias**: post-HA adjusted figures everywhere capacity
  is measured. Raw cluster capacity overstates real admission
  capacity; post-HA matches what vSphere will actually schedule.
- **Color system**: green/yellow/orange/red stoplight, with
  specific band boundaries (15/30/50) for post-HA free%. Set
  once in the dashboard intro text so all widgets share a
  consistent vocabulary.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Section split | Capacity (top) + Right-Sizing (bottom) | Two different decisions driving two different investigations. Co-locating them in one dashboard reflects that they're the two dimensions of the same quarterly review. |
| Scope mechanism | Self-provider widgets pinned to vSphere World | Environment-wide snapshot. No picker — reduces friction for the "just show me everything" use case. |
| Post-HA framing | All capacity metrics use post-HA-adjusted SMs | Raw capacity is misleading. Post-HA is what matters for planning decisions. |
| Cluster-level counts | Per-cluster rollup SMs (Oversized/Undersized/Idle counts) | Cluster is the planning unit; VM-level flag data rolled up via `depth=2` walks makes clusters the row identity in the scoreboard. |
| Capacity reclaim display | **Environment-level sum** of reclaimable vCPUs and memory (new, redesigned) | Right-Sizing Scoreboard's *point* is "how much capacity could we get back." Per-cluster counts answer "how many VMs to look at"; sum of reclaim answers "how big is the prize." Both are useful; the fourth box should be a prize figure, not a repeat of "VM count." |
| Memory units in scoreboard | GB (computed in SM via `/1048576`) | `summary|oversized|memory` is KB. Displaying KB at environment level produces nine-digit numbers. Convert in the SM so the Scoreboard renders human-scale values. |
| Scoreboard layout | 5 boxes in a single row (`box_columns: 5`) | Fits the existing `w=12, h=3` real estate. Single row preserves parallel reading. Alternative considered: split into two Scoreboards ("Flagged VMs" counts + "Reclaimable Capacity") — rejected because it doubles widget count for the same info density. |
| ParetoAnalysis widgets | Keep unchanged | Top-15-by-reclaim-vCPUs and Top-15-by-reclaim-memory both already target VirtualMachine directly, which is correct. These were not broken. |
| View widgets | Keep unchanged | Cluster Capacity Overview and VM Right-Sizing Candidates views both still work; no design debt here. |

## Known Issues in Current Build → Resolution

| Issue | Where | Resolution |
|---|---|---|
| `summary\|oversized\|vcpus` referenced on `ClusterComputeResource` does not exist — VM-level metric only | `dashboards/capacity_assessment.yaml:174-179`, Scoreboard `rightsizing_kpis` fourth box | Author new SM `[VCF Content Factory] Cluster - Reclaimable vCPUs (sum)` with `sum(${...summary\|oversized\|vcpus, depth=2})`; update Scoreboard box to reference it. |
| No "Reclaimable Memory" KPI at cluster/env level, only at VM level in the Pareto below | Same Scoreboard | Author new SM `[VCF Content Factory] Cluster - Reclaimable Memory GB (sum)` (with `/1048576` KB→GB conversion); add as fifth box in Scoreboard. |
| Scoreboard has `box_columns: 4`, not enough slots for both new KPIs | Same Scoreboard | Bump to `box_columns: 5`. |
| No design artifact in `designs/` to anchor future changes | — | This file. |

## Dashboard Mockup

```
+======================================================================+
|  [VCF Content Factory] Capacity Assessment & Right-Sizing            |
+======================================================================+
|                                                                      |
|  === SECTION 1: Capacity Assessment ================================ |
|  ( TextDisplay intro — post-HA framing, stoplight legend )           |
|                                                                      |
|  +-----------+-----------+-----------+-----------+                   |
|  | Powered-  | Avg CPU   | Avg Mem   | Running   |  <- Scoreboard    |
|  | On VMs    | Free %    | Free %    | Hosts     |     (env-level    |
|  |           | post-HA   | post-HA   |           |      KPIs)        |
|  +-----------+-----------+-----------+-----------+                   |
|                                                                      |
|  +----------------------------------------------------------------+  |
|  |                                                                |  |
|  |   Cluster Heatmap — CPU Free % post-HA                         |  |
|  |   colored 15/30/50 stoplight, sized by Running VMs,            |  |
|  |   grouped by Datacenter                                        |  |
|  |                                                                |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
|  +----------------------------------------------------------------+  |
|  |   View: [VCF Content Factory] Cluster Capacity Overview        |  |
|  |   ( cluster table with post-HA CPU/mem, days-until-runout,     |  |
|  |     VMs-that-fit, colored columns )                            |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
|  === SECTION 2: Right-Sizing Opportunities ========================= |
|  ( TextDisplay intro — oversized/undersized/idle definitions,        |
|    95th-percentile demand column hint, color legend )                |
|                                                                      |
|  +--------+--------+--------+-------------+----------------+         |
|  |Over-   |Under-  |Idle    |Reclaimable  |Reclaimable     |   <-    |
|  |sized   |sized   |VMs     |vCPUs (sum)  |Memory GB (sum) | 5-box   |
|  |VMs     |VMs     |        |  ** NEW **  |  ** NEW **     | layout  |
|  +--------+--------+--------+-------------+----------------+         |
|                                                                      |
|  +----------------------------+  +-----------------------------+     |
|  |  Top 15 VMs by             |  |  Top 15 VMs by              |     |
|  |  Reclaimable vCPUs         |  |  Reclaimable Memory (GB)    |     |
|  |  ( ParetoAnalysis )        |  |  ( ParetoAnalysis )         |     |
|  +----------------------------+  +-----------------------------+     |
|                                                                      |
|  +----------------------------------------------------------------+  |
|  |   View: [VCF Content Factory] VM Right-Sizing Candidates       |  |
|  |   ( VM table with oversized/undersized/idle flags, target      |  |
|  |     vCPU + memory recommendations, 95th-percentile justif. )   |  |
|  +----------------------------------------------------------------+  |
+======================================================================+
```

Boxes marked `** NEW **` are the redesign delta. Everything else
reflects the existing build and is preserved.

## Content Inventory

**Existing content (preserved, no changes):**

Super metrics (11):
- `supermetrics/cluster_cpu_free_pct_after_ha.yaml`
- `supermetrics/cluster_memory_free_pct_after_ha.yaml`
- `supermetrics/cluster_vms_that_fit_cpu.yaml`
- `supermetrics/cluster_vms_that_fit_memory.yaml`
- `supermetrics/cluster_oversized_vm_count.yaml`
- `supermetrics/cluster_undersized_vm_count.yaml`
- `supermetrics/cluster_idle_vm_count.yaml`
- `supermetrics/vm_target_vcpus_oversized.yaml`
- `supermetrics/vm_target_memory_gb_oversized.yaml`
- `supermetrics/vm_target_vcpus_undersized.yaml`
- `supermetrics/vm_target_memory_gb_undersized.yaml`

Views (2):
- `views/cluster_capacity_overview.yaml`
- `views/vm_rightsizing_candidates.yaml`

Custom groups (1):
- `customgroups/vms_rightsizing_candidates.yaml`

Dashboard (1):
- `dashboards/capacity_assessment.yaml` (will be modified)

**New content (to be authored):**

Super metrics (2):
- `supermetrics/cluster_reclaimable_vcpus_sum.yaml` — `sum(${adaptertype=VMWARE, objecttype=VirtualMachine, metric=summary|oversized|vcpus, depth=2})` on ClusterComputeResource
- `supermetrics/cluster_reclaimable_memory_gb_sum.yaml` — `sum(${adaptertype=VMWARE, objecttype=VirtualMachine, metric=summary|oversized|memory, depth=2}) / 1048576` on ClusterComputeResource

**Modified content:**
- `dashboards/capacity_assessment.yaml` — Scoreboard `rightsizing_kpis`: fix broken fourth box to reference new vCPUs sum SM, add fifth box for memory sum SM, bump `box_columns` from 4 to 5.
- `bundles/capacity-assessment.yaml` — add the two new SM paths to the `supermetrics:` list.

## Out of Scope

- Adding a cluster/datacenter picker. Current environment-wide
  scope is by design. If per-cluster drill-down is wanted, that's
  a separate dashboard (future v2, not this redesign).
- Adding symptoms/alerts around capacity thresholds. The dashboard
  is for planning reviews, not operational alerting.
- Modifying existing super metrics (e.g., the VM target vCPU / memory
  SMs). They work, and their semantics are load-bearing for the
  view tables — don't touch.
- Re-examining the Capacity section. It's not broken.

## Traceability

- **Original commit** (un-designed): `e9217af` — 2026-04-11
- **Design artifact created**: 2026-04-20 (this file)
- **Redesign trigger**: tonight's full-package-rebuild surfaced
  the `summary|oversized|vcpus` on Cluster as a hard dependency-
  audit failure. Root cause = authored against VM-level metric
  without describe-cache check; this was exactly the class of bug
  the packaging dependency audit was later built to catch.
