# SDK Adapter Review: compliance build 61 (v3 content round)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 61, commit `04de2b4`, vs build 60 `1706d4b` (delta: content only, no Java) and build 56 `32de5aa` (pak-compare reference)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.61.pak`
- **Contracts:** `knowledge/designs/dashboards/compliance-{environment-overview,esxi-hosts,vms,vcenter-networking}.md` (with their 2026-09-23 amendments); build-60 key contract (adapter `README.md`, `docs/overview.md`, `ComplianceDecisions` / `ComplianceRollup` push code)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 3 WARNING / 3 NIT
- **Accepted gaps, not re-raised (coordinator brief):** SUM-only totals rows, no default sort on embedded views, uncolored Average Score tile, Overview W6 empty until a vCenter is selected.

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass.** 7 Java suites + generator unittest OK. |
| `generate_compliance_alerts.py --check` | **Up to date.** |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...61.pak`. Bundled: 4 super metrics, 8 views, 4 dashboards, as `adapter.yaml` claims. Old Host Overview view and Fleet Overview dashboard are absent. Adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO.** WARNING is the known ComplianceWorld attribute retirement. INFO: the new content files, the removed Fleet Overview and Host Overview, the manifest description, and the five profile files. |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Contract checks

**Keys (97 references checked by script).** Every `attribute:` in the 8 views, every `metric_key:` in the 4 dashboards, and every `metric=` in the 4 super metrics was checked against the build-60 push set.

- **Per-object metrics:** `score`, `pass_count`, `fail_count`, `total_count`, `unreadable_count`, `non_compliant`, `no_benchmark`.
- **Per-object property:** `profile_name`.
- **Rollups:** `Rollup|<All|Host|VM|vCenter|Cluster|vDS|Portgroup>|<scored|non_compliant|no_benchmark|score_sum|avg_score>`, `Rollup|Host|scored_stale`, and `Rollup|Benchmark|<SCG_6.7..SCG_9.1|none|unknown>|objects`.
- **Result:** every reference is spelled exactly as pushed, metrics are never flagged `is_property`, and `profile_name` is always flagged property/string.
- **VMWARE keys:**
  - `summary|version` on VMwareAdapter Instance: observed per the overview design.
  - `summary|version` on VmwareDistributedVirtualSwitch: vendor precedent in vcommunity's "Distributed Switch for CSV export" report.
  - `summary|parentCluster` / `summary|parentVcenter` on HostSystem: known-good per the hosts design.
  - `summary|parentHost` on VirtualMachine: recon log.

**Super metrics.** Each formula is assigned to `VMWARE / vSphere World` and sums `depth=1` VMwareAdapter Instance children (recon: the vCenters are World's only depth-1 children on devel and prod). A key with a space inside `metric=` has repo precedent (`metric=Super Metric|sm_...`). Average Score is `sum(score_sum) / sum(scored)`, which is the correct weighted environment average (not an average of averages). See N1 for the 0/0 behavior.

**Dashboard to super metric references.** All five scoreboard and chart references use `Super Metric|sm_<id>` with ids equal to the four SM YAML `id:` values, and `metric_name` equals the SM names.

**AlertList definition ids.** Checked by script against `describe.xml`. Ids are `AlertDefinition-vcfcf_compliance-<id>`; that prefix is proven live for pak alerts (recon: `AlertDefinition-vcfcf_compliance-vcfcf_compliance_score_degraded`).

| Dashboard widget | Listed | Expected (by describe.xml resourceKind) | Missing / extra / dup |
|---|---|---|---|
| Overview W6 | 144 | all 144 generated | 0 / 0 / 0 |
| ESXi Hosts W4 | 86 | HostSystem 86 | 0 / 0 / 0 |
| VMs W3 | 23 | VirtualMachine 23 | 0 / 0 / 0 |
| vCenter & Networking W6 | 35 | vCenter 15 + Cluster 2 + vDS 11 + Portgroup 7 | 0 / 0 / 0 |

The hand-written score alert is correctly excluded.

**Interaction wiring (rendered `dashboard.json` inspected).**
- **Overview:** 1 edge, W3 to W6. Views resolve to UUIDs.
- **ESXi Hosts:** 5 edges (W1 to W2 and W3; W2 to W4, W5 and W6), matching the wireframe.
- **VMs:** 4 edges (W1 to W2; W2 to W3, W4 and W5), matching.
- **vCenter & Networking:** 8 edges (W1 to W2..W5; each of W2..W5 to W6), matching.
- **Grid:** coordinates match every wireframe table.
- **Pickers:** the ResourceList pickers render the framework's standard `tagPicker` form over the listed kinds.

**View summary indexes.** 0-based over `columns`, the same indexes the renderer emits for the attribute items. Each view sums the count and flag columns, never version, profile or score columns.

## WARNING

### W1. Dashboard alert lists are hand-copied from the generator's output with no drift gate

- **Where:** `alert_definitions` in all four dashboards (288 ids); `scripts/generate_compliance_alerts.py`; `tests/test_generate_compliance_alerts.py`.
- **Authority:** reviewer dimension 9 (the reproducibility gate must cover what it produces); skill § *Unreadable is NOT compliant* spirit (a failing control must not be silently invisible).
- **What:** the lists are exact today. But the generator derives the alert set from the profiles, and `--check` only guards describe.xml and resources.properties. The next profile change (a new SCG version or a manual_review edit) adds or renames generated alerts that the dashboards do not list. That control's failure then never appears in "Failing Controls on Selected Host / VM / Object", and CI stays green.
- **Fix:** add a generator unittest (already run in CI on push, PR and tag) that loads the four dashboard YAMLs and asserts each list equals the generated set for its kinds. Or have the generator rewrite the four lists between markers, the same way it does describe.xml.

### W2. Approved per-kind designs require score gating the shipped views and heatmap do not implement, with no amendment recorded

- **Where:** `compliance-esxi-hosts.md` § Known constraints ("the view and heatmap filter to `no_benchmark = 0` and `total_count > 0` for score columns so a stale score never shows as current"); `compliance-vms.md` § New view ("Score columns filtered to ..."); `compliance-vcenter-networking.md` § Wireframe ("filters score columns to ..."). Shipped: all six object views and the ESXi heatmap have no filter. The view descriptions say "see Known constraints below", but no such section exists in the view YAML (dangling reference).
- **Authority:** approved design contract (RULE-011 gate); build-57 review W2 (the origin of this requirement).
- **What:** this deviation is not in the accepted-gaps list. A readable host that moves to an unmapped version keeps its last score in Ops. The Host Detail row shows it next to No SCG = 1 (visible). The **heatmap colors that host by the retained score with no flag at all**, for example green for a host the adapter no longer scores.
- **Scope:** only in Auto mode, for unmapped versions (and a few whole-host-unreadable hosts, which the Non-Compliant column already flags). Not a pass on a live read, but a displayed score for an unscored object.
- **Fix:** the per-column gating the design describes is not expressible. The toolset's `subject_filter` filters rows, which would drop no-benchmark rows the design says must still list. Take this back to the owner:
  - **(a)** Record an amendment in the three designs accepting "flag columns instead of score gating", and fix the dangling "Known constraints" text in the view descriptions; or
  - **(b)** use `subject_filter` (`total_count > 0` AND `no_benchmark = 0`) on the heatmap and on a scored-only variant of each list, with unscored objects shown by the flag columns elsewhere.

  Either way the heatmap needs a decision.

### W3. Bundled super metrics need policy enablement, and no doc says so or even mentions the dashboards

- **Where:** `bundled_content.supermetrics` (4 SMs feeding Overview W1 and W5); `README.md`, `docs/installing.md`, `docs/overview.md` (no mention of dashboards, views, super metrics or policy enablement).
- **Authority:** `vcfops-content-model` skill § *Policy enablement* ("Super metrics must be enabled in a policy to collect data"); reviewer dimension 11 (a user-visible behavior absent from every doc surface is a WARNING).
- **What:** the SDK pak emits SM JSON but nothing enables the SMs in a policy (`sdk-content-emit` review: install only). Unless the pak import enables them (unproven), the Environment Overview scoreboard and trend show no data after install, which looks like a broken pak. The four dashboards themselves are also undocumented.
- **Fix:**
  - **Docs:** add a "Dashboards" section to README and overview.md naming the four dashboards. In installing.md, add a step to enable the four `[VCF Content Factory] Compliance ...` super metrics on vSphere World in the active policy (Default Policy: `PUT /internal/supermetrics/assign/default`).
  - **Acceptance:** first check on devel whether the import already enables them.
  - **Registry:** if they are not auto-enabled, this is a candidate for registration against the pak.

## NIT

- **N1.** `supermetrics/compliance-average-score.yaml` calls "0/0 yields no-data" a "confirmed idiom". Its only citation is a one-line assertion in the VCF license design note ("Division by zero ... yields no-data, not an error. Fine."), not a live observation. The failure mode is safe: the worst plausible result is a 0 (a false alarm, never a pass), since `score_sum > 0` implies `scored > 0`. Reword it to "expected" and confirm at devel install (a moment when every vCenter's `Rollup|All|scored` is 0, such as right after install before the first v3 cycle).
- **N2.** The three per-kind designs say the Scope picker defaults to vSphere World. The rendered ResourceList uses `selectFirstRow: true` over a mixed World / vCenter / Cluster (/ Host) list, so the default is whichever row sorts first, which is not guaranteed to be the World. Confirm at first install; if it is not the World, note the actual default in the designs.
- **N3.** Upgrade residue: devel currently has build 56's Compliance Fleet Overview dashboard and Compliance Host Overview view installed. Build 61 no longer ships them, and a pak upgrade is not known to delete content it stopped shipping, so the retired-key dashboard may keep showing frozen values on devel and prod. The acceptance plan should check for both after upgrade. Deleting them is a destructive action on Scott's verbatim go.

## If shipped as-is

The four dashboards, eight views and four super metrics install with every key, id and interaction correct. Risks:
- The Environment Overview may show empty tiles until someone enables the super metrics in a policy, and nothing tells them to.
- The ESXi heatmap can color an unscored host by a stale score.
- The next profile update can silently drop new controls from the "Failing Controls" lists.
