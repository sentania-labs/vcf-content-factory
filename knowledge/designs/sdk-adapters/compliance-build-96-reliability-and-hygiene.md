# Compliance build 96: reliability, hygiene and docs findings that need no design call

- **Type:** managementpack (Tier 2 SDK adapter change), build 96 (main is 0.0.0.95 at bd2eba6, untagged)
- **Slug:** compliance-build-96-reliability-and-hygiene
- **Adapter repo:** `content/sdk-adapters/compliance/` (branch from `origin/main`)
- **Date:** 2026-10-16
- **Status:** in progress

## Initial prompt (Scott, verbatim, 2026-10-16)

> the fork paks are enhancedments we will tackle.  let's focus on the
> compliance, unif, synology, and template.  Triage them, order them, and
> let's fix them all in this session.

and, on #52 and its neighbours:

> we should fix or confirm those bugs before we design aroudn them

## What the morning's evidence settled

- #52 is not reproduced (investigations/2026-10-16-compliance-52-30-31-recon.md):
  3 of 3 clusters on 31 queries, unmatched and incomplete flat at 0 for
  43.5 hours. The blank wld01 and wld02 rows are non-vSAN clusters with no
  applicable control. The code trace found one latent hole: a 200 with an
  empty list and totalCount 0 is read as "no objects of this kind", every
  object becomes unmatched, and incomplete stays 0 (ComplianceDecisions.java:616).
- #30 and #31: data present and widget filters match; rendered-page check
  pending on 0.0.0.95.
- #39 (where unmatched surfaces) is deferred until unmatched is ever
  non-zero in practice.

## Scope (fork issues, in order)

1. **#52 latent case** an empty-but-valid listing for a kind that had one
   or more objects in the previous cycle is treated as INCOMPLETE (held
   back, incomplete = 1), not as zero. A kind empty two cycles in a row is
   accepted as genuinely empty. Table test on `resourcePageOutcome` and a
   fixture test on `fetchResources` with a stubbed client (HTTP error,
   timeout, empty page with totalCount > 0, 11 pages), which also covers
   DEF-023's open test; restore the interrupt flag in the catch at
   ComplianceStitcher.java:339; refresh the field comment at :89-92.
   Close #52 with the recon evidence and this fix.
2. **#41** push -1 for every skipped control on every cycle while the Skip
   is in force (same path as normal controls), so the symptom sees cancel
   cycles. Doc half: Infrastructure Operations > Configurations >
   Management Packs Configuration path, clone dialog naming, instance
   setting takes the name without .xml.
3. **#42** same shape for controls retired by a guide version change: push
   -1 every cycle while the object stays on the new version, or route
   through the same per-cycle cancel path as 2.
4. **#18** wrap `collectHosts`'s `getHosts()` the way `collectVms` wraps
   its own: WARN, count in CycleStats, mark HOST incomplete, return an
   empty map so VMs fall back to vCenter-version selection, continue with
   the other kinds.
5. **#16** per-cycle time budget (default 80 percent of the collection
   interval, read from the instance setting if the SDK exposes it,
   otherwise a constant) checked in the host, VM, DVS and cluster loops;
   a consecutive-timeout breaker (default 5) that ends the cycle; both end
   the cycle cleanly with incomplete = 1 and the affected kinds held back;
   shorter read timeout for keepalive and single-property reads.
6. **#23** disconnect and log out the old `vsphere` and `vcApi` in
   `configureAdapter` before replacing them (build 95 already disconnects
   `oldVsphere` at :2608; confirm `vcApi` and the tester path); in
   `VSphereClient.connect()` assign service-content fields to locals and
   commit them with the cookie only after Login succeeds; clear
   `sessionCookie` and `propertyCollector` on any failure.
7. **#24** cap SOAP response size (64 MB, one constant) and parse the DOM
   from the byte array, not via String.
8. **#26** remaining bullets: Test Connection adds SOAP
   RetrieveServiceContent plus Login and a Suite API reachability check;
   custom-profile cache key includes the file's lastModified and size.
   The memory bullet was fixed in build 95 (cf354ed); say so.
9. **#25** verify: `ComplianceDecisions.java:43` Basic auth encoding uses
   UTF-8 explicitly; if so close with evidence, if not fix and check
   `VCenterApiClient`.
10. **#28** dead code only: remove the unused `vcApi` field and
    `evaluateAdvancedSettings` if confirmed superseded (cover with a test
    if kept). History rewrite is Scott's call (decision D5), not this build.
11. **#43** docs halves (items 2 and 3): installing.md on CA-trusted
    validation, the IP-host accept dialog, non-resolving host behaviour;
    overrides.md and data-reference.md on overrides_status "fetch failed".
    Item 1 waits on decision D3.
12. **#33** Host Score Heatmap fixed 0 to 100 colour scale: red below 80,
    amber 80 to 95, green 95 and up (matches the Host Compliance Score
    Degraded thresholds). Dashboard YAML only.
13. **Build 95 nit** reuse the WARN wording at ComplianceAdapter.java:1191
    (carried from the build 95 review).
14. **#27** put the SDK Logger behind a small interface or a test-classpath
    stub so VSphereClient, EsxcliSoapClient, ComplianceStitcher and the
    adapter orchestration compile in ci/run_java_tests.sh; add fixture
    tests: recorded SOAP and esxcli XML for the parsers, a matchResource
    table, and the orchestration test from item 4.

Waiting on Scott, not in this build: #20 (D1), #39 (D2, deferred), #43
item 1 (D3), #17 (D4), #28 history (D5), #29 (CI, from the template).
#30, #31, #32, #34 close or reopen on the rendered-page check.

## What must not regress

- Build 95 behaviour: shadow pass rate, held-back kinds keep memory,
  bulk shadow read, certificate hook, overrides handling.
- Scores on devel identical to build 95 for every object (no evaluation
  path changes in this build).

## Proof

- Unit tests per item; the new fixture suite from item 14 runs in
  tests.yml on JDK 17 and 25.
- validate-sdk, build-sdk dev build 0.0.0.96, pak-compare against the
  0.0.0.95 pak with zero BLOCKING.
- Reviewer gate, peer review, PR, Codex round, merge, no tag. devel_9_1
  install under the standing approval: Skip clears an alert within three
  cycles, a broken credential ends the cycle inside the budget with
  incomplete = 1, scores unchanged from build 95.
