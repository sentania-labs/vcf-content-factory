# Design Artifact: VM Rightsizing Demo Dashboard

## Original Request

> Create a quick demo dashboard about VM optimization and rightsizing for the
> entire environment
>
> (Scott confirmed: even though Capacity Assessment already covers this,
> create a NEW dashboard for demo purposes — velocity over reuse.)

## Scope and Intent

- **Audience**: demo viewer. Show what the factory can produce for rightsizing
  analysis in a single, scannable dashboard.
- **Scope**: entire environment (all `VirtualMachine` resources across all
  vCenters). No cluster/tenant filter, no custom group scoping.
- **Velocity posture**: minimal content set. One dashboard, one view, zero SMs
  (per `feedback_percentiles_are_view_transforms.md` — percentile / long-term
  aggregation is a view-column transform, not a super metric).
- **Not a replacement** for the existing `bundles/capacity-assessment.yaml` —
  different slug, different name, coexists.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Content decomposition | 1 view + 1 dashboard, zero SMs | Simplest viable demo; built-in VM metrics + view-column 95th-percentile transforms cover the need |
| Scope mechanism | Self-provider View widget pinned to vSphere World | Standard factory pattern per `feedback_dashboard_self_provider_view.md` — picker-less, environment-wide |
| Name prefix | `[VCF Content Factory]` on both view and dashboard | Factory identity convention per `project_naming_convention.md` |
| Dashboard folder | `VCF Content Factory` | Factory default per `feedback_dashboard_pin_and_sharing.md` |
| Sharing | shared=true | Default for factory dashboards |
| Recon | Skip live (lab in stuck state) | Offline recon only: repo YAML + `docs/vcf9/metrics-properties.md` for built-in metric keys |

## Dashboard Mockup

```
+------------------------------------------------------------------+
|  [VCF Content Factory] VM Rightsizing Demo                       |
|                                                                  |
|  +------------------------------------------------------------+  |
|  |  About this dashboard                                      |  |
|  |  Environment-wide VM rightsizing snapshot. Sort columns    |  |
|  |  to find oversized (high configured, low demand),          |  |
|  |  undersized (low configured, high demand), or idle VMs.    |  |
|  +------------------------------------------------------------+  |
|                                                                  |
|  +-----+-----+-----+  +------------------------------------+    |
|  |  N  |Cfg  |P95  |  |                                    |    |
|  |VMs  |vCPU |CPU  |  |  (optional scoreboard tile row)    |    |
|  |     |tot. |Dem% |  |                                    |    |
|  +-----+-----+-----+  +------------------------------------+    |
|                                                                  |
|  +------------------------------------------------------------+  |
|  |  VM Rightsizing — Environment Scan                         |  |
|  |  +----+-------+-----+------+------+-------+-------+-----+  |  |
|  |  |VM  |Cluster|Power|vCPUs |P95   |Memory |P95    |Ready|  |  |
|  |  |Name|       |State|(cfg) |CPU   |(cfg   |Memory |%    |  |  |
|  |  |    |       |     |      |Dem%  |GB)    |Dem%   |(avg)|  |  |
|  |  +----+-------+-----+------+------+-------+-------+-----+  |  |
|  |  |vm1 |Clus-A | On  |  8   | 12%  |  32   |  24%  | 0.2%|  |  |
|  |  |vm2 |Clus-B | On  |  2   | 95%  |   4   |  88%  | 3.1%|  |  |
|  |  |vm3 |Clus-A | On  |  4   |  2%  |   8   |   5%  | 0.0%|  |  |
|  |  |... |       |     |      |      |       |       |     |  |  |
|  |  +----+-------+-----+------+------+-------+-------+-----+  |  |
|  |  (sort by any column; group by cluster if view supports)   |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
```

**Reading the demo**:
- Low P95 CPU Demand% + low P95 Memory Demand% → **oversized** (rightsizing down candidate)
- High P95 CPU Demand% + high Ready% → **undersized / under pressure** (rightsizing up or co-scheduling relief)
- Very low P95 CPU + very low P95 Memory → **idle** (decomm candidate)

## Content Plan

**Supermetrics**: none. Percentile demand metrics are view-column aggregation transforms on built-in VM stats.

**Custom groups**: none. Scope is entire environment via self-provider pin to vSphere World.

**Views** (1):
- `views/vm_rightsizing_environment_scan.yaml`
  - Subject: `VMWARE:VirtualMachine`
  - Columns (intent — author picks built-in metric keys):
    - VM name
    - Parent cluster (resolved relationship)
    - Power state
    - Configured vCPU count
    - 95th-percentile CPU demand (% of configured) — view-column aggregation over last 30 days
    - Configured memory (GB)
    - 95th-percentile memory demand (% of configured) — same aggregation window
    - Average CPU ready %
  - Sort: leave to user interaction (no default sort needed for demo)

**Dashboards** (1):
- `dashboards/vm_rightsizing_demo.yaml`
  - Name: `[VCF Content Factory] VM Rightsizing Demo`
  - `name_path`: `VCF Content Factory`
  - Shared: true
  - Widgets:
    - TextDisplay: intro block (1-2 sentences)
    - View widget: the single list view, `self_provider: true`, pinned to vSphere World
    - Optional: Scoreboard tiles for total VM count, total configured vCPUs (if author finds clean built-in metrics; skip if it complicates)

**Symptoms / alerts / reports**: none (demo, not monitoring).

## Out of Scope (Explicit)

- Monitoring / alerting
- Right-sizing recommendations as computed fields (vCF Ops doesn't compute those natively — we'd need SMs or hand calculation, both out of scope for "quick")
- Idle-flag boolean column (requires composite logic — skip for demo; user infers from sorted columns)
- Cluster / tenant filter picker
- Custom groups
- Reports

## Delegation Plan

Per CLAUDE.md §Delegation protocol, compound content authored bottom-up:

1. **Skip recon** — lab is in stuck `isPakInstalling` state per Scott's signal; offline authoring against built-in metric docs is sufficient for this demo.
2. **`view-author`** — single view `views/vm_rightsizing_environment_scan.yaml`. Intent: per this design artifact's Content Plan > Views section. Let author pick exact built-in metric keys and view-column aggregation config.
3. **Validate** (`python3 -m vcfops_supermetrics validate && python3 -m vcfops_dashboards validate && ...`).
4. **`dashboard-author`** — single dashboard `dashboards/vm_rightsizing_demo.yaml`. Intent: this design's mockup. Author resolves view by name.
5. **Validate** again.
6. **Report back to Scott** with file paths + brief preview.

No live install expected — Scott tests via his normal workflow, not through this pass.

## Verification

- View YAML validates (`vcfops_dashboards validate`)
- Dashboard YAML validates (`vcfops_dashboards validate`)
- Dashboard YAML cross-reference to view resolves
- Manual visual check: dashboard layout is a single-screen demo scan, not scrollable heavy

## Provenance

- Design artifact written 2026-04-17 by orchestrator (Claude)
- Scott pre-approved the intent: "I just want to demo - so even if candidates exist - create this"
- Framework convention compliance per memories `project_naming_convention.md`,
  `feedback_percentiles_are_view_transforms.md`,
  `feedback_dashboard_self_provider_view.md`,
  `feedback_dashboard_pin_and_sharing.md`,
  `feedback_delegate_intent_not_design.md`.
