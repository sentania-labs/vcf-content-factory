# [VCF Content Factory] Compliance ESXi Hosts

- **Type:** dashboard (bundled in the compliance pak)
- **Slug:** compliance-esxi-hosts
- **Authored YAML:** content/sdk-adapters/compliance/dashboards/compliance-esxi-hosts.yaml
- **Date:** 2026-09-23
- **Status:** mock approved 2026-09-23
- **Mock:** knowledge/designs/dashboards/compliance-esxi-hosts.html
- **Parent design:** knowledge/designs/sdk-adapters/compliance-v3-version-aware.md

## Initial prompt

See the parent design note for the verbatim prompts. The relevant ask
(Scott, 2026-09-23):

> The host dashbaord for example should allow a user to see hosts that are in/out of compliance based on some scope World and vCenter maybe, view hosts and their compliance %, and select a host and see which metrics are not compliant (this may not be possible with ops dashboarded?, i.e. list metrics where compliance ~=1?

## Vision

Pick a scope (whole environment, one vCenter, or one cluster), see
every host in it worst first with its score and the SCG applied, then
select a host to see exactly which controls fail and how to fix each
one. "Which controls fail" comes from the per-control compliance alerts
(one alert per failing control, each with its runbook recommendation),
which is the answer to "list metrics where Compliant is not 1".

## Model decisions this dashboard depends on (adapter v3)

- Two per-object flags on every scored object `[planned v3]`:
  `VCF-CF Compliance|non_compliant` (1 when fail_count > 0 or
  unreadable_count > 0, else 0) and
  `VCF-CF Compliance|no_benchmark` (1 when the version has no SCG).
  They let a view's summary row count non-compliant hosts in whatever
  scope is selected, with no super metric per scope.
- Per-control alerts (subType 21) exist, one per control, each with a
  recommendation carrying the SCG remediation text.

## Keys

Observed on devel HostSystem by recon 2026-09-23:
`VCF-CF Compliance|score`, `|pass_count`, `|fail_count`,
`|total_count`, `|unreadable_count`, `|profile_name`.
Known-good VMWARE keys (used across reference content):
`summary|version`, `summary|parentCluster`, `summary|parentVcenter`.
`[planned v3]`: `VCF-CF Compliance|non_compliant`,
`VCF-CF Compliance|no_benchmark`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Scope | ResourceList | 1, 1, 3, 12 | `vSphere World`, `VMwareAdapter Instance`, `ClusterComputeResource` | Object picker; default selection vSphere World. Drives W2 and W3 |
| W2 | Host Compliance | View | 4, 1, 9, 12 | driven by W1, descendants of kind `HostSystem` | New view (below), sorted by score ascending. Selection drives W4, W5, W6 |
| W3 | Host Score Heatmap | Heatmap | 1, 13, 5, 8 | driven by W1, `HostSystem` | Color by `VCF-CF Compliance\|score` (red 0, green 100), group by parent cluster, fixed size |
| W4 | Failing Controls on Selected Host | AlertList | 6, 13, 7, 8 | driven by W2 | Alerts from adapter kind `vcfcf_compliance`, subType 21, on the selected host: control ID and title, criticality, recommendation (runbook), since |
| W5 | Score Trend | MetricChart | 1, 21, 6, 6 | driven by W2 | `VCF-CF Compliance\|score` and `\|fail_count`, 30 days |
| W6 | Compliance Details | PropertyList | 7, 21, 6, 6 | driven by W2 | `summary\|version`, `VCF-CF Compliance\|profile_name`, `\|total_count`, `\|pass_count`, `\|fail_count`, `\|unreadable_count` |

Interactions: W1 selection drives W2 and W3. W2 row selection drives
W4, W5, W6. Nothing selected in W2 leaves W4 to W6 empty with the
widget's own prompt.

## New view (authored before the dashboard)

**Compliance Host Detail** (subject `HostSystem`), replaces the current
Compliance Host Overview view:

| Column | Key | Notes |
|---|---|---|
| Host | name | |
| Cluster | `summary\|parentCluster` | |
| vCenter | `summary\|parentVcenter` | |
| ESXi version | `summary\|version` | |
| SCG applied | `VCF-CF Compliance\|profile_name` | "no benchmark for ESXi X.Y" when unmapped |
| Score (%) | `VCF-CF Compliance\|score` | red < 80, orange < 90, yellow < 95 |
| Failing | `VCF-CF Compliance\|fail_count` | |
| Unreadable | `VCF-CF Compliance\|unreadable_count` | |
| Non-compliant | `VCF-CF Compliance\|non_compliant` | planned v3, 0/1, hidden-ish narrow column |
| No SCG | `VCF-CF Compliance\|no_benchmark` | planned v3, 0/1 |

Summary row: host count, average score (unweighted average of hosts is
correct here, each host is one object), sum of Failing, sum of
Non-compliant (= non-compliant hosts in scope), sum of No SCG.

## Known constraints

- The ResourceList picker listing three kinds at once is expected to
  work (multi-kind ResourceList is in the renderer) but is confirmed at
  the first devel install; fallback is vCenters and clusters only with
  "all hosts" as the no-selection default.
- The lab has one ESXi build, so the SCG applied column shows 9.1 on
  every host until a mixed environment is available.
- Ops keeps a metric's last value when pushes stop. A host with no
  benchmark or nothing evaluated gets zeroed counters from the adapter
  (review of build 57, W2), and the view and heatmap filter to
  `no_benchmark = 0` and `total_count > 0` for score columns so a stale
  score never shows as current. No-benchmark hosts still list, with the
  No SCG flag set.
