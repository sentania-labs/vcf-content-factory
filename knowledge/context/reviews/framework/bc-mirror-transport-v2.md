# Framework review v2 — BC-mirror loopback TLS transport (DEF-005 code half), re-review closeout

- **Area:** `vcfops_managementpacks/adapter_framework` (`VcfCfAdapter` FIPS-WARN gating) +
  `tests/test_defect_gate.py` (DEF-005 corpus alignment)
- **Date:** 2026-07-01
- **Reviewer:** `framework-reviewer` (RULE-013, blanket pre-PR gate)
- **Prior:** `knowledge/context/reviews/framework/bc-mirror-transport-v1.md` — CHANGES REQUESTED (1 BLOCKING / 1 NIT)
- **This pass:** verify the two v1 items are properly closed and nothing else moved.
- **Verdict:** APPROVE (0 BLOCKING)

## Scope of this round — independently confirmed

By mtime against the v1 review timestamp (18:39:28), **exactly two files** were modified
after v1:
- `tests/test_defect_gate.py` (18:41)
- `VcfCfAdapter.java` (18:42)

Every other file in the combined four-diff tree predates the v1 review
(`knowledge/context/defects.md` 18:21; `SuiteApiStitchClient.java` 18:24; `VcfCfAdapterTest.java` 18:27;
`SuiteApiStitchClientTest.java` 18:28; `cli.py`/`sdk_builder.py` 17:31;
`AmbientCredential`/`RelationshipBuilder` 16:26–16:27). **No drive-by edits** to the three
already-APPROVED sibling diffs or to `knowledge/context/defects.md`.

- **DEF-005 byte-identical:** `knowledge/context/defects.md` mtime (18:21) precedes the v1 review; the
  git diff still shows the same +33-line block characterized in v1 (blocking / open / synology,
  closes only on live-devel datastore+stitch verification). Not touched this round. Confirmed.

## Checks re-run (independently)

- **pytest:** **457 passed, 4 skipped, 0 failed** — matches tooling's claim. The 4 formerly-red
  synology-clean gate tests now pass.
- **Java framework suites (main()-based, run against a freshly rebuilt `vcfcf-adapter-base.jar`):**
  `VcfCfAdapterTest` **9/9**, `SuiteApiStitchClientTest` **18/18**, `AmbientCredentialTest` **13/13**
  (1 SKIP = Crypt unavailable off-appliance, as designed), `RelationshipBuilderTest` **8/8** —
  matches expected 9/18/13/8. The 4 new `VcfCfAdapterTest` assertions directly exercise
  `applyBcMirrorTransport` (trust-all SSLSocketFactory + all-true HostnameVerifier, unconditional)
  and `isFipsApprovedOnly`.
- **Validate chain:** `python3 -m vcfops_managementpacks validate` — all Tier 1 + 6 Tier 2 SDK
  adapters OK. (Other 6 modules unaffected by this round's two files; full chain was green in v1.)
- **Framework jar:** rebuilt clean via `build-framework.sh` (SDK-only classpath, no aria-ops-core
  residue). Gitignored/rebuilt-from-source → no staleness concern.
- **pak-compare / render-regression:** n/a — no `render.py` / `template.json` / `describe.xml`
  touched.

## v1 item 1 — BLOCKING (stale gate tests) → CLOSED

`tests/test_defect_gate.py` updated so the synology assertions expect DEF-005 as synology's one
open blocker, with docstrings citing DEF-005 by id. `knowledge/context/defects.md` **not** touched
(DEF-005 still `Status: open`, verbatim). Full pytest now green (457/4/0). Correctly did **not**
close DEF-005 to satisfy the suite — DEF-005 closes only on live-devel verification per its own
criterion.

**Test-quality (tightening check):** the gate-semantics test
`TestGatePak::test_synology_is_clean_def001_closed` asserts `ids == ["DEF-005"]` — an **exact
list** (line 324), so a *second* future open blocker against synology (e.g. DEF-006) would produce
`["DEF-005", "DEF-006"]` and correctly trip it. The other three updated tests
(`TestCLIDefectGate`, `TestGatePublish`, `TestStandaloneEntrypoint`) assert the exit-code/raise
contract plus `"DEF-005" in output` — substring is the right granularity there, because the
exact-blocker-set contract is owned by the `gate_pak` test above. Correct layering; no WARNING.

## v1 item 2 — NIT (FIPS WARN spam) → CLOSED (once per adapter instance lifetime, not per cycle)

`VcfCfAdapter.java` adds an instance-scoped `AtomicBoolean fipsGapWarnLogged` (line 192) gating the
FIPS-gap WARN via `compareAndSet(false, true)` (line 1095); `applyBcMirrorTransport` untouched
(unit-verified byte-for-byte behavior by `VcfCfAdapterTest`).

**Scope check (the one that mattered):** the v1 NIT was per-*request* spam. I checked whether the
adapter object is rebuilt each collect cycle — it is **not**. `abortRequested` (the sibling
instance flag) is explicitly `.set(false)` on cycle/config entry (lines 605, 696), which only makes
sense if the adapter instance *persists* across cycles. `fipsGapWarnLogged` is **never reset**
anywhere (grep-confirmed: only the declaration and the `compareAndSet`). Therefore the WARN fires
**exactly once per adapter-instance lifetime** (until collector restart), not once per cycle — the
strongest possible closure of the NIT, better than the "once per cycle" fallback the brief allowed.

## Combined-tree coherence (final pre-PR gate)

Working tree is coherent: validate green, all four Java suites green, pytest green. The three
already-APPROVED sibling diffs are unchanged since their approval. This diff is ready for the PR.

## If shipped as-is

CI/pytest ships green (457/0). The defect gate correctly refuses a synology release while DEF-005
is open, and the suite now carries an in-code record (docstrings + exact-list assertion) that
DEF-005 is the expected blocker rather than a gate regression. FIPS-approved-only deployments get
one WARN per adapter start identifying the documented FIPS-branch gap, then run on the non-FIPS
BC-mirror transport — no per-request/per-cycle log bloat. Transport behavior itself is unchanged
from the v1-reviewed (and separately unit-covered) code.
