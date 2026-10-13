# Compliance adapter: rollup counts only pushable objects; Pod VMs out of scope

- **Type:** managementpack (Tier 2 SDK adapter change), build 88
- **Slug:** compliance-rollup-unmatched-and-pod-skip
- **Adapter repo:** `content/sdk-adapters/compliance/` (sentania-labs/vcf-content-factory-sdk-compliance)
- **Date:** 2026-10-12
- **Tracking:** adapter issue #38
- **Status:** go from Scott 2026-10-12 ("Option 1."); build 88 reviewed APPROVE and installed on devel 2026-10-12 5:11 PM (Environment 175 scored / 140 non-compliant, wld01 18 pods skipped, unmatched 0); PR #44 on the adapter repo

## Initial prompt (Scott, verbatim, 2026-10-12)

> The maths on this don't math

then, on the three options presented:

> Option 1.

## Recon (devel, 2026-10-12, read-only)

The Environment Overview tiles read ComplianceWorld `Rollup|Environment|*`
and equal the sum of the three vCenters' `Rollup|All|*` exactly. The one
mismatch is wld01: `Rollup|VM|scored` 43 against 25 VirtualMachine
resources in Ops. The 18 extra are the vSphere Supervisor Pods on wld01
(vm-15058 to vm-16029; Argo CD, Harbor, metrics-aggregator, auto-attach,
cci-ns-controller and similar), which Ops models as kind `Pod`. Each
scores 78.947 (15 of 19 VM controls). Effect: Objects Scored 193 where
175 are reachable in Ops; Non-Compliant 158 where 140 are reachable.

Mechanism (source): `ComplianceAdapter.collectVms` calls
`rollup.recordEvaluated` for every VM vCenter returns, then
`pushComplianceViaClient` only when `stitcher.matchVm` found a resource.
The host loop has the same shape. There is no "scored but not in Ops"
bucket, and `VSphereClient.VmInfo` does not carry the guest id, so a Pod
VM is indistinguishable from a real VM today.

## Vision

Two changes, both in build 88:

1. **The rollup counts only objects the adapter could push to.** For
   every kind (host, VM, vCenter, cluster, vDS, port group), an object
   with no matching Ops resource is excluded from `Rollup|<Kind>|scored`,
   `non_compliant`, `no_benchmark`, `score_sum` and the `All` and
   `Benchmark` totals. The gap is visible, not hidden: a new per-kind
   key `Rollup|<Kind>|unmatched` (count, 0 when none; pushed on every
   complete cycle and held back with the kind's other keys when that
   kind's listing failed, since a count that was not taken is not a 0;
   `Rollup|incomplete` alone goes out every cycle) and one INFO line
   per cycle per kind naming the unmatched objects (name and MOID,
   capped sensibly). Amended 2026-10-12 after the build 88 review (N2):
   the code holds the key back with its kind, and that is the right
   reading.
   Whether to skip scoring an unmatched object entirely (saves the
   vCenter reads) is the author's call; the count and names must still
   be reported.
2. **CRX Pod VMs are out of scope.** vSphere Pods (guest id
   `crxPod1Guest`, `crxSys1Guest` and any other `crx*` guest id, read
   in the bulk VM enumeration) are skipped before scoring and before
   the rollup, counted under a separate `Rollup|VM|skipped_pods` key
   and named at DEBUG. They are not "unmatched"; they are not VMs the
   SCG VM controls apply to, and Ops files them under kind `Pod`.

Expected devel result: wld01 `Rollup|VM|scored` 25, environment Objects
Scored 175 and Non-Compliant 140 (three stale mgmt templates already
excluded by Ops), `Rollup|VM|skipped_pods` 18 on wld01 and 0 elsewhere,
`Rollup|*|unmatched` 0 everywhere.

Docs: README key list, docs/data-reference.md, docs/overview.md
(what unmatched and skipped_pods mean, where the names are logged),
CHANGELOG build 88 entry. No new alerts or symptoms. Dashboards: none
required by this change (the alert-widget rework on
`fix/alert-widget-type-filter-and-depth` and the ComplianceWorld summary
dashboard are separate build 88 items on the same branch line).
