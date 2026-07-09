# Framework review — BC-mirror loopback TLS transport (DEF-005 code half)

- **Area:** `vcfops_managementpacks/adapter_framework` (`VcfCfAdapter.openPlatformConnection` /
  `applyBcMirrorTransport` / `isFipsApprovedOnly`; `SuiteApiStitchClient` text-only)
- **Date:** 2026-07-01
- **Reviewer:** `framework-reviewer` (RULE-013, blanket pre-PR gate)
- **Change:** Suite API hop now mirrors vendor `aria-ops-core SuiteAPIClient` non-FIPS
  transport (trust-all + ignore-hostname, unconditional — peer-gating removed) instead of the
  platform strict-TOFU `CustomSSLSocketFactory` that PKIX-failed every cycle on live devel.
  FIPS-approved-only mode logs a WARN and falls through to the non-FIPS mirror (documented gap).
- **Ships with:** three APPROVED siblings in one PR (`stitcher-identity-additive-foreign-v1`,
  `sdk-builder-jar-staleness-v1`, `sdk-version-guardrail-v1`).
- **Verdict:** CHANGES REQUESTED (1 BLOCKING)

## Checks re-run (independently)
- **Java framework suites:** `VcfCfAdapterTest` 9/9, `SuiteApiStitchClientTest` 18/18,
  `AmbientCredentialTest` 13/13, `RelationshipBuilderTest` 8/8 — all PASS (matches expected
  9+18+13+8). Framework jar rebuilt clean via `build-framework.sh` (SDK-only classpath, no
  aria-ops-core residue). Jar is gitignored/rebuilt-from-source → no git staleness concern.
- **pytest:** 453 passed, **4 failed**, 4 skipped. All 4 failures = `tests/test_defect_gate.py`
  synology "clean" assertions, root cause DEF-005 now open (see BLOCKING).
- **Validate chain:** all 7 modules PASS.
- **validate-sdk (Tier 2 recompile):** compliance / synology / unifi / vcommunity /
  vcommunity-os / vcommunity-vsphere — all 6 OK against the rebuilt framework jar.
- **pak-compare:** n/a (no template.json/describe.xml/render.py change).

## BLOCKING
- **[knowledge/context/defects.md + tests/test_defect_gate.py]** — dimension 7 (corpus regression),
  RULE-005 / RULE-012. This changeset files **DEF-005 as `Status: open` blocking against
  `synology`** (new, +33 lines, not in HEAD). The defect gate now correctly returns
  `['DEF-005']` for synology, which reds 4 corpus tests that assert synology is clean:
  `TestGatePak::test_synology_is_clean_def001_closed`,
  `TestCLIDefectGate::test_pak_synology_exits_0_def001_closed`,
  `TestGatePublish::test_synology_passes_def001_closed`,
  `TestStandaloneEntrypoint::test_pak_synology_exits_0_def001_closed`. The pytest suite ships
  **red**. `test_synology_is_clean_def001_closed`'s own docstring instructs: *"If a new open
  blocking defect is filed against synology, update this test."* — that update was not made.
  The **gate behavior is correct** (DEF-005 legitimately stays open until live-devel
  verification per its own closing criterion); only the stale corpus tests are wrong.
  → **Smallest fix:** update the 4 tests to expect synology's one known open blocker
  (DEF-005) instead of asserting zero blockers, per the docstring's own instruction. Do not
  close DEF-005 to make them pass — it closes on live verification, not on this code fix.

## WARNING
- none.

## NIT
- **[VcfCfAdapter.java:1075-1084]** — the FIPS WARN fires inside `openPlatformConnection`,
  which `SuiteApiStitchClient.urlConnRequest` calls **per HTTP request** (token acquire + each
  datastore page + each stitch write). Under `-Dorg.bouncycastle.fips.approved_only=true` this
  emits an identical WARN on every Suite API call, every cycle, forever. Correctness is fine
  (`isFipsApprovedOnly` = `Boolean.getBoolean`, cannot throw on any value; verified false/true/
  false by test). Consider emitting the FIPS-gap WARN once per client/adapter construction
  rather than per request to avoid log bloat in FIPS deployments.

## Cleared on inspection (proven safe, not findings)
- **No trust-all leak onto target-system TLS** (dimension 1 / anchor 00d3382). `openPlatformConnection`
  and its `applyBcMirrorTransport` helper are the Suite API hop only; `applyBcMirrorTransport`
  has exactly one caller (`openPlatformConnection`). Target-system connections
  (vCenter/NAS/UniFi) go through `HttpClientBuilder.platformSsl → getPlatformSslContext`, which
  is **unchanged** and still strict. `HttpClientBuilder` is not in this diff.
- **Remote-path posture change is documented** (dimension 8). The relaxation from JDK-strict
  hostname on the explicit/remote path to unconditional trust-all is called out explicitly in
  the `openPlatformConnection` javadoc ("Non-FIPS branch (implemented)", peer-gating-removed
  note) and in the runtime INFO log (`BC-mirror: trust-all + ignore-hostname, non-FIPS`). It
  mirrors the vendor client exactly (`knowledge/context/api-surface/casa-injected-vs-raw-client.md` §3),
  per the "mirror BC, don't invent" directive. Loud + documented → not a downgrade finding.
- **Preserved pieces preserved** (dimension 2/4). `SuiteApiStitchClient` credential resolution
  (automation-first ambient, explicit fallback), endpoint selection, and token lifecycle are
  logically byte-equivalent — the only executable delta is a log-line `file=` label using the
  sibling-provided `AmbientCredential.getSourceLabel()`; all else is javadoc/log text.
  `SuiteApiStitcher` diff is javadoc-only. `AmbientCredential`/`RelationshipBuilder` changes
  belong to the already-APPROVED siblings; their suites are green under the combined tree.
- **Dead code is dead-but-documented, not half-wired** (dimension 5). `getPlatformSslContext`
  is still live (target-system path, `HttpClientBuilder:81`); the old peer-gating / `getByName`
  loopback machinery is fully removed from `openPlatformConnection`, not stranded.

## If shipped as-is
CI/pytest ships red — the PR fails its own defect-gate corpus tests, and any operator running
the suite sees 4 synology failures with no signal that they are the *expected* consequence of
the DEF-005 filing rather than a real gate regression. The transport code itself is correct and
would behave as intended on-instance.
