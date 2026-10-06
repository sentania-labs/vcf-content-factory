# Environment totals for an SDK pak are ComputedMetrics on the pak's singleton, not super metrics and not per-instance pushes

**Rule.** When a Tier 2 pak needs a number that spans every adapter
instance (every vCenter, every array, every site), declare it as a
`<ComputedMetric>` on the pak's own singleton resource kind in
describe.xml, with a super-metric-style expression over the children,
and give that singleton a parent/child edge to each instance's target
through the additive Suite API relationship call. Do not bundle super
metrics on a foreign object, and do not have each instance push the
total.

**Why.** Compliance builds 84 and 85, devel, 2026-10-02 to 10-05:

- The four bundled super metrics on `VMWARE / vSphere World` worked, but
  they were the only part of the pak that needed manual policy
  enablement, and a pak policy fragment cannot fix that: a fragment
  creates its own named policy that an admin still has to assign
  (`knowledge/context/investigations/policy_fragment_wire_format.md`).
- Pushing the total from each instance is last-writer-wins across
  instances (the build 57 ComplianceWorld problem). Source-stamped pushes
  or leader election would work, but no management pack in the reference
  corpus does either; the platform's own answer is different.
- The VMWARE adapter's vSphere World counts are not collected at all.
  Its describe.xml declares them under `<ComputedMetrics>`, with
  `sum(${adapterkind=VMWARE, resourcekind=VMwareAdapter Instance,
  metric=...})`, and the engine sums the children. `ComputedMetrics` is a
  legal `ResourceKind` child in `describeSchema.xsd`, the evaluator is
  generic (twelve installed describes use it, NSX and the container
  adapter among them), and it evaluated correctly on our
  `vcfcf_compliance / ComplianceWorld` kind summing a foreign kind's
  pushed metric keys, with no policy edit.

**What it costs.** Three facts to design around:

1. **One collection interval of lag.** The engine evaluates when the
   singleton itself collects, and at that moment the children's newest
   values are the previous cycle's. Five cycles in a row on devel. Short
   intervals make this fine (5 minutes at 5 minutes); an hourly adapter
   shows totals an hour old, which is why the compliance interval moved
   to 5.
2. **One point skipped on every pak upgrade.** The redescribe resets the
   computed-metric state; the first evaluation afterwards stamps the
   then-current cycle and the previous one never surfaces.
3. **Edges persist.** The additive child link is never removed, so a
   target whose instance is deleted stays a child. Use `addChild`
   (POST), never the SDK full-set relationship route on a parent shared
   across instances, and never PUT: both wipe the other instances'
   links.

**Expression hygiene.** A describe test should pin, per computed key,
the exact source keys the adapter pushes (use the real prefix constant),
the summing kind, and the expression shape; a renamed or swapped key
empties the totals with no error (`EnvironmentKeyContractTest` in the
compliance pak is the template). Keep the denominator metric next to any
ratio so a zero reads as "nothing scored", not "all clear".

**Where it lives.** Reference implementation: compliance describe.xml
`ComplianceWorld`, `ComplianceAdapter.linkVCenterToWorld`,
`ComplianceDecisions.linkWorld`. Facade contract:
`knowledge/context/tier2_architecture.md` ("POST adds, PUT replaces").
Design and proof: `knowledge/designs/sdk-adapters/compliance-environment-computed-metrics.md`
and the 2026-10-01 to 10-05 recon log entries.
