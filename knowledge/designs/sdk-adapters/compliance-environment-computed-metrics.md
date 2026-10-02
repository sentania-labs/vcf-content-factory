# Compliance adapter: environment totals as ComputedMetrics on ComplianceWorld

- **Type:** managementpack (Tier 2 SDK adapter change) + bundled dashboard repoint
- **Slug:** compliance-environment-computed-metrics
- **Adapter repo:** `content/sdk-adapters/compliance/` (sentania-labs/vcf-content-factory-sdk-compliance)
- **Date:** 2026-10-01
- **Status:** drafted (decision taken, implementation not started; devel install waits on Scott's go)

## Initial prompt

Scott, 2026-10-01 (verbatim):

> I want to talk about the 4 supermetrics in the compliance pack: can't we calculate them and then stich them to the desired object, vs. rolling them up as a supermetric

> so how do we make sure that 2,3,10 instances don't stomp on each other?  is there any other path?

> let's try path 2.
>
> Are there any packs out there that have a leader election?

> how does the vsphere adapters put thing slike total VM count, etc onto vsphere world?

> so these metrics roll up to Compliance world or whatever and not vsphere world?

Decision (verbatim):

> ComputedMetrics on ComplianceWorld
>
> THis is the correct path I think, and the pattern to set

## Recon that led here (2026-10-01, all read-only on devel)

- The four pak super metrics (Objects Scored, Non-Compliant Objects,
  Objects Without Benchmark, Average Score) exist only to sum the
  per-vCenter `VCF-CF Compliance|Rollup|All|*` keys (already stitched onto
  each VMwareAdapter Instance) onto the one shared vSphere World object,
  and they are the only part of the pak that needs manual policy
  enablement.
- Stitching the environment total from each instance is last-writer-wins
  across vCenters (the build 57 ComplianceWorld problem). Mitigations
  (source-timestamped pushes, leader election) are all adapter-invented;
  no management pack in the reference corpus does leader election.
- A pak policy fragment can carry `<SuperMetrics>` enablement (parser
  confirmed from devel classes, wire shape in
  `knowledge/context/investigations/policy_fragment_wire_format.md`), but
  it creates a named policy the admin must still assign. Rejected.
- vSphere World's own Summary counts are not collected by any instance.
  The VMWARE describe.xml declares them under `<ComputedMetrics>` with a
  super-metric-style expression the engine evaluates over the
  VMwareAdapter Instance children; live values on devel are exactly the
  sum of the three vCenters, and no VMware instance reports status on the
  World. `ComputedMetrics` is a legal ResourceKind child in the public
  `describeSchema.xsd`. Recon log entries dated 2026-10-01.

## Vision

Make ComplianceWorld the environment-level object, the way vSphere World
is for the VMWARE adapter: a singleton whose totals are declared, not
pushed. No instance writes an environment number, so instance count is
irrelevant and nothing needs enabling by hand.

1. **describe.xml, ComplianceWorld kind.** Add a `Rollup|Environment`
   ResourceGroup with four attributes (`scored`, `non_compliant`,
   `no_benchmark`, `avg_score`), declared like the adapter's other
   metrics (dataType, unit, defaultMonitored="true"), and a
   `<ComputedMetrics>` block whose expressions sum the per-vCenter
   `VCF-CF Compliance|Rollup|All|{scored, non_compliant, no_benchmark}`
   keys across every `VMWARE / VMwareAdapter Instance`, with `avg_score`
   as summed `score_sum` over summed `scored` (weighted, same shape as
   the retired super metric). Zero scored must yield no-data, not 0,
   consistent with unreadable-is-not-compliant; verify on devel.
2. **Relationship.** vSphere World sums its children. ComplianceWorld is
   not related to the VMwareAdapter Instances today. Each adapter
   instance already resolves its vCenter's VMwareAdapter Instance UUID;
   it should push a ComplianceWorld parent to VMwareAdapter Instance
   child relationship through the Suite API so the computed expressions
   have children to walk (and the user gets a navigable link). Whether
   the engine needs the relationship, and whether it reads pushed
   dynamic keys, is settled by the devel install, not assumed.
3. **Super metrics retired, dashboard repointed.** Once devel shows the
   computed values, delete the four YAMLs under
   `content/sdk-adapters/compliance/supermetrics/`, repoint the
   Environment Overview scoreboard (W1) and trend (W5) at ComplianceWorld,
   and remove the policy-enablement paragraphs from README, overview and
   installing docs. Until then the super metrics stay so devel keeps
   working.
4. **Pattern to set.** When this proves out, codify it as a lesson and in
   the `vcfops-sdk-adapter` skill: environment-wide totals for an SDK
   pak live on the pak's own singleton as `ComputedMetrics`, never as
   bundled super metrics on a foreign object and never as per-instance
   pushes.

## Proof gate

Dev-preview build on devel (install is a write and needs Scott's go). Pass
means: the four `Rollup|Environment` keys appear on ComplianceWorld with
values equal to the sums of the three vCenters' `Rollup|All` keys, with
no policy edit, and the trend has history after two cycles. Fail means
the engine does not evaluate `ComputedMetrics` for a non-VMWARE kind,
in which case the fallback is the stitched environment total with
source-stamped timestamps (no leader), documented in this file's recon
section.

## Go and progress

Scott, 2026-10-01 evening (verbatim), on the sequence author, reviewer,
devel install, phase 3:

> let's go on the plan

- Factory branch `feat/compliance-environment-computed-metrics` (cut from
  main): `SuiteApiStitcher.addChild` / `addChildren` (additive POST, no
  replace variant) and `findSingletonResourceId`. framework-reviewer
  APPROVE on two passes; report
  `knowledge/context/reviews/framework/adapter-framework-stitch-relationship-add-2026-10-02.md`.
- Adapter branch `feat/environment-computed-metrics`: ComputedMetrics on
  ComplianceWorld plus the per-cycle ComplianceWorld to vCenter link.
  sdk-adapter-reviewer APPROVE on build 82; report
  `knowledge/context/reviews/compliance-build-82.md`.
- Devel install: not done. It is a write and waits on Scott's yes.

## Carried into phase 3 (from the reviews)

- Adapter docs (`docs/overview.md`, `docs/data-reference.md`) still say
  ComplianceWorld carries only `Summary|last_scan_timestamp` and do not
  mention the new parent/child link. Correct them in the same round as
  the dashboard repoint, before any `v*` tag.
- When nothing is scored, `Rollup|Environment|non_compliant` sums to 0.
  A tile built on it must check `scored > 0` first or it reads as all
  clear. Consider a count of vCenters reporting.
- Edges are never removed. A vCenter whose compliance instance is deleted
  stays a ComplianceWorld child. Devel should show whether its stale
  rollup keeps feeding the totals; if it does, edge removal becomes a
  follow-up.
- Release order: factory PR merged, sdk-buildkit 1.0.11 published and
  the `sdk-buildkit-v1` tag moved, then tag the adapter. A tag before
  that fails at compile.

## Devel checklist (from the adapter review, so the test cannot mislead)

1. Collector log identity line, then read back ComplianceWorld's children
   across three or more cycles (catches the VMWARE adapter removing the
   edge, and one instance wiping another's).
2. Whether computed values appear before the edge does (would mean the
   engine is not walking children).
3. The four `Rollup|Environment` values against the bundled super metrics
   on vSphere World, which stay installed for exactly this comparison.
4. Whether the Suite API accepts a type 7 adapter-instance resource as a
   child of a foreign kind.
5. First cycle warns that the world does not exist yet; second cycle
   requests the link.
6. Zero scored gives no data, not 0.
