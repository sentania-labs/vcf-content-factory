# v2 round-2 devel acceptance — compliance 50 / unifi 5 / synology 17 (2026-06-10)

All three pak upgrades installed on devel (9.0.2) and ACCEPTED the same
day; `v*` tags cut afterward and all three CI release builds green
(buildkit v1.0.2). Reviews: `context/reviews/{compliance-build-50,
unifi-build-5,synology-build-17}.md`. Root-cause context:
`context/investigations/unifi_401_and_relationship_persistence_2026_06_10.md`.

## Live proofs (what this round settled empirically)

1. **RelationshipBuilder ResourceKey fix works — TOOLSET GAP closed.**
   First collect cycle after unifi build 5: **126 edges persisted** in
   the Suite API (World→Site→Gateway/Switch/AP/NVR → ports 81, radios
   12, cameras 13, plus uplink switch→switch/gateway topology). Before
   the fix: zero, every cycle, silently. The investigation's open
   question (constructor swap vs collect-path-registration as cause) is
   resolved: the swap was the cause; collect-path-registered resources
   bind edges fine.
2. **Framework single-retry-on-401 recovers a dead session.** The unifi
   instance had been 401-dead for ~5h on an expired TOKEN cookie; build
   5 resumed collection (128 resources / 681 metrics) with no instance
   restart and no adapter-code change — framework jar only.
3. **Foreign-resource full-set `setRelationships` is ADDITIVE on 9.0.2 —
   re-confirmed** (this time via synology→VMWARE Datastore):
   `vcf-lab-wld01-cl01-iscsi` kept all 14 VMWARE children and gained
   the `SynologyIscsiLun/vcf-lab-wld01-cl01` child. Closes synology
   build-17 review WARNING-1; WARNING-2 (isUnique hardcoding) proven
   non-blocking — the matched edge lands on the correct Datastore.
4. **Host-header fix holds.** No `restricted header name: "Host"`
   crashes on synology's multi-homed NAS path post-upgrade; 25
   resources / 136 metrics parity with build 16.
5. **Strict SSL default + `allowInsecure=true` upgrade path.** Both
   compliance instances already carried an explicit `allowInsecure=true`
   which the upgrade preserved (instance config survives pak upgrade —
   the strict default applies to *absent* values only). Collection
   healthy; `avg_host_score` 61.9048 matches the baseline era.
6. **`Summary|hosts_scored_stale` live** on ComplianceWorld, value 0.0
   with all hosts readable (the pass state); pushed unconditionally.
7. **No resource duplication on any adapter** after the §22 collect-path
   discovery adoption — resource keys stayed byte-identical, the
   platform de-duplicated correctly (128 unifi / 25 synology / 1
   ComplianceWorld unchanged).

## State after this round

- devel: compliance 1.0.0.50 (2 instances, 60-min interval restored),
  unifi 1.0.0.5 (5-min interval, pre-existing), synology 1.0.0.17
  (5-min interval, pre-existing) — all collecting clean.
- Official releases: `v1.0.0.50` / `v1.0.0.5` / `v1.0.0.17` on the
  respective `sentania-labs/vcf-content-factory-sdk-*` repos, CI-built
  from kit v1.0.2 (framework source at d59785a).
- Fresh-instance discovery defect (tasks #18/#19): CLOSED — all three
  adapters now framework-§22 collect-path discovery.
- Prod compliance remains on build 42 (down since install on 9.1);
  build 50 is the fix candidate, awaiting Scott's go. Note for that
  upgrade: prod instances may NOT have `allowInsecure=true` set —
  check config before judging post-upgrade health, or import the
  vCenter cert.
