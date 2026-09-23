# [VCF Content Factory] Compliance Environment Overview

- **Type:** dashboard (bundled in the compliance pak)
- **Slug:** compliance-environment-overview
- **Authored YAML:** content/sdk-adapters/compliance/dashboards/compliance-environment-overview.yaml
- **Replaces:** content/sdk-adapters/compliance/dashboards/compliance-overview.yaml (Compliance Fleet Overview)
- **Date:** 2026-09-23
- **Status:** mock approved 2026-09-23
- **Mock:** knowledge/designs/dashboards/compliance-environment-overview.html
- **Parent design:** knowledge/designs/sdk-adapters/compliance-v3-version-aware.md

## Initial prompt

See the parent design note for the verbatim prompts. The relevant ask
(Scott, 2026-09-23):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

## Vision

The top-level page of the four-dashboard set. It answers three
questions without a click: how compliant is the environment, which
object types and which vCenters drag it down, and which SCG versions
are in play (including objects with no matching SCG). The per-kind
dashboards (ESXi Hosts, VMs, vCenter & Networking) are where a user
goes to act on a single object.

## Model decisions this dashboard depends on (adapter v3)

- **Rollups live on the vCenter object, not on ComplianceWorld.**
  Recon 2026-09-23 (devel): there is ONE ComplianceWorld shared by all
  three adapter instances, so its `Summary|*` values are whichever
  instance wrote last. v3 pushes per-vCenter rollups onto each
  `VMWARE / VMwareAdapter Instance` (already a stitch target).
- **Environment totals are super metrics on `VMWARE / vSphere World`**,
  depth 1 over its `VMwareAdapter Instance` children (recon: the three
  vCenters are its only direct children, on devel and prod).
- **Non-compliant** = an object with at least one failing or
  unreadable control (`fail_count > 0` or `unreadable_count > 0`), per
  the unreadable-is-not-compliant rule. The adapter computes it.
- **No benchmark** = object whose version has no SCG in the pak; it is
  counted, never scored.

## Keys

`[planned v3]` keys do not exist yet; the adapter work creates them.
Everything else was observed by recon on devel 2026-09-23.

Per-vCenter rollups on `VMWARE / VMwareAdapter Instance` `[planned v3]`,
`<K>` in `All, Host, VM, vCenter, Cluster, vDS, Portgroup`:

| Key | Meaning |
|---|---|
| `VCF-CF Compliance\|Rollup\|<K>\|scored` | objects scored |
| `VCF-CF Compliance\|Rollup\|<K>\|non_compliant` | objects with fail_count > 0 or unreadable_count > 0 |
| `VCF-CF Compliance\|Rollup\|<K>\|no_benchmark` | objects with no matching SCG |
| `VCF-CF Compliance\|Rollup\|<K>\|score_sum` | sum of scores (for weighted averages) |
| `VCF-CF Compliance\|Rollup\|<K>\|avg_score` | score_sum / scored |
| `VCF-CF Compliance\|Rollup\|Benchmark\|<B>\|objects` | objects scored against `<B>` in `SCG_6.7, SCG_7.0, SCG_8.0, SCG_9.0, SCG_9.1, none` |

Observed: `summary|version` on `VMwareAdapter Instance` (vCenter version).

Super metrics on `VMWARE / vSphere World` (new, authored before the
dashboard):

| Super metric | Formula sketch |
|---|---|
| [VCF Content Factory] Compliance Objects Scored | `sum(${adaptertype=VMWARE, objecttype=VMwareAdapter Instance, metric=VCF-CF Compliance\|Rollup\|All\|scored, depth=1})` |
| [VCF Content Factory] Compliance Non-Compliant Objects | same, `Rollup\|All\|non_compliant` |
| [VCF Content Factory] Compliance Objects Without Benchmark | same, `Rollup\|All\|no_benchmark` |
| [VCF Content Factory] Compliance Average Score | `sum(...Rollup\|All\|score_sum...) / sum(...Rollup\|All\|scored...)` |

## Wireframe

12-column grid. Row units as in the mock.

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Environment Compliance | Scoreboard | 1, 1, 8, 4 | self-provider, pinned `VMWARE / vSphere World` | 4 SMs above. Avg score: red < 80, orange < 90, yellow < 95. Non-compliant: yellow >= 1. Without benchmark: orange >= 1 |
| W2 | About this dashboard | TextDisplay | 9, 1, 4, 4 | none | What non-compliant and no-benchmark mean; names of the three drill-down dashboards |
| W3 | Compliance by vCenter and Object Type | View | 1, 5, 12, 8 | self-provider, pinned `vSphere World`, children `VMwareAdapter Instance` | New view (below). Summary row = environment totals |
| W4 | Objects by SCG Version | View | 1, 13, 6, 7 | same as W3 | New view (below). Summary row = totals |
| W5 | Environment Score Trend | MetricChart | 7, 13, 6, 7 | pinned `vSphere World` | SM Average Score and SM Non-Compliant Objects, last 30 days |
| W6 | Open Compliance Alerts | AlertList | 1, 20, 12, 7 | driven by W3, default all | Alerts from adapter kind `vcfcf_compliance`, subType 21 (compliance), criticality warning and up, newest first |

Interactions: W3 row selection drives W6 (alerts scoped to that
vCenter's descendants). No selection = all compliance alerts.

## New views (authored before the dashboard)

**Compliance by vCenter and Object Type** (subject `VMwareAdapter Instance`):
vCenter name, `summary|version`, then for Host, VM, Cluster, vDS,
Portgroup: `avg_score` (colored red < 80 / orange < 90 / yellow < 95)
and `non_compliant`; for vCenter: the object's own
`VCF-CF Compliance|score`; last column `Rollup|All|no_benchmark`.
Summary row: sum for counts, weighted average not available in a view
summary so score columns summarize as average of vCenters (labelled so).

**Objects by SCG Version** (subject `VMwareAdapter Instance`):
vCenter name, then `Rollup|Benchmark|<B>|objects` for SCG 6.7, 7.0,
8.0, 9.0, 9.1, none. Summary row: sum.

## Known constraints

- The lab runs one ESXi build (9.1.1) on all hosts in both instances,
  so the SCG-version view will show a single populated column until a
  mixed-version environment is available; mixed versions are tested
  with simulated input in the adapter tests.
- vDS objects report their own version (9.0.0) separately from the
  vCenter (9.1.1); per the parent design they are scored by the vCenter
  version, and the views show the benchmark applied, not the vDS
  version.
- View summary rows cannot compute a weighted average; the environment
  weighted average lives in W1 (super metric), and the view summary
  row is labelled "avg of vCenters".
- Widget availability on Ops 9.0 (devel) vs 9.1 (prod) is not
  checkable by API; verified visually after the first install on each.
- Retires the existing Compliance Fleet Overview, whose ComplianceWorld
  summaries are last-writer-wins across adapter instances.
