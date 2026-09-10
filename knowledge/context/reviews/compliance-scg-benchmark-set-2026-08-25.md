# Review: compliance adapter — SCG-only benchmark set (build 55)

- **Adapter:** content/sdk-adapters/compliance (branch
  `feat/scg-benchmark-set-8-90-91`, commit `83f1f8e`, vs `main`)
- **Reviewer:** sdk-adapter-reviewer, 2026-08-25
- **Design:** knowledge/designs/sdk-adapters/compliance-scg-benchmark-set.md
  (owner scope: exactly SCG 8.0 / 9.0 / 9.1; CIS vSphere 8 removed)
- **Verdict: CHANGES REQUESTED** — 1 BLOCKING / 3 WARNING / 2 NIT

## Independent claims check

All re-run locally, not taken from the author's report.

| Claim | Result |
|---|---|
| `profiles/vmware_scg_9.1.csv` verbatim copy of reference clone 9.1 CSV | **Confirmed byte-identical** (`cmp` vs `reference/references/vcf-security-and-compliance-guidelines/security-configuration-hardening-guide/cloud-foundation/9.1/vcf-security-configuration-guide-91-controls.csv`, VERSION token `910-20260612-01` present). Reference clone is clean at `ce883a9` (RULE-016 satisfied). |
| Canonical `scg_9.1.csv` reproducible from the driver | **Confirmed byte-identical**: re-ran `scripts/normalize_scg_v91.py` against the committed source; output == committed canonical. |
| 260/260 rows normalized, 0 skipped | **Confirmed** (61 advanced_setting, 30 vim_property, 9 esxcli, 5 vami_api, 57 powercli_only, 98 manual_audit; every raw SCG ID present in canonical). |
| 101 evaluable in 9.1 vs 98 in 9.0 | **Numerically confirmed** by independent recompute — but see W2 (2 of the 101 can never actually evaluate). |
| "No control evaluable in 9.0 lost evaluability" | **REFUTED** — see W1. True only under an id-equality comparison; one control changed id and lost evaluability. |
| validate-sdk pass | **Confirmed** (javac clean, one benign `-source 11` warning). |
| build-sdk → 0.0.0.55 | **Confirmed**, rebuild produced `vcfcf_sdk_compliance.0.0.0.55.pak`. |
| pak-compare 0 BLOCKING / 0 WARNING / 5 INFO | **Confirmed vs build 54** (`dist/vcfcf_sdk_compliance.0.0.0.54.pak`); all 5 INFO are the intended description change + 9.1 profile add + CIS profile removal. (Vs older 1.0.0.49 there is 1 pre-existing WARNING — ComplianceWorld group attr 6 vs 5 — not introduced by this change.) |
| dvpg.network-vgt duplicate resolution matches 9.0 | **Confirmed**: same pair as 9.0 — `esx-9.network-vgt` row stays `powercli_only` (informational), `vcenter-9.network-vgt` row is `vim_property` with `vlan_id_not:config.defaultPortConfig.vlan`. |
| Spot-check (b) | 27 rows sampled (2 per sub-product across all 14 source prefixes): ids, priorities, kinds, recipes all match the raw CSV. One normalization noted and judged correct: raw priority `"P0, Upon Feature Enablement"` → canonical `P0` (schema requires the P0/P1/P2 enum). |
| Diff scope | The SCG change proper (`fdd2491..83f1f8e`) touches 17 files, all in-scope; the workflow tag-guard change is the separate, already-PR'd commit `fdd2491` (#9), not part of this review. Build 55 bumped + CHANGELOG line present (hygiene OK). |
| Docs parity | README.md, docs/README.md, docs/overview.md, docs/installing.md, docs/inventory-tree.md, CANONICAL_SCHEMA.md, resources.properties key 104 all updated to SCG-only; no CIS residue found. No relationship/stitch behavior changed, so no hidden cross-MP doc gap. |

## BLOCKING

### B1 — Removed CIS profile silently scores as SCG 8.0 (the unenumerated-input-becomes-a-verdict pattern)

`src/com/vcfcf/adapters/compliance/BenchmarkLoader.java:112-125`
(`resolveBundledProfileName`), reachable-in-anger only because this
build removes `CIS_vSphere_8` from the enumerated set.

Any adapter instance still configured `CIS_vSphere_8` (every existing
CIS user, after an in-place pak upgrade) falls into the `default:`
branch and is scored against **VMware_SCG_8.0**. The only signals are a
`logWarn` in the collector log (`ComplianceAdapter.java:366-371`) and
the pushed `profile_name` property — the instance's own configuration
UI still says CIS. The operator's dashboards show a confident
compliance score that answers a different question than the one they
configured.

- Authority: skill § *Unreadable is NOT compliant* (a value we could
  not produce as asked must never surface as a plausible number);
  `knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md`
  ("everything else is unknown, and unknown is never the reassuring
  branch"); the loader's **own javadoc**: "the adapter status goes
  Down with an actionable message instead of silently producing a
  wrong score" — the missing-column path already chose loud-fail; the
  unknown-profile path must match it.
- **Weighing the two failure modes:** crash-the-cycle costs one
  visible Down state, fixed by a one-click config edit; the wrong-score
  mode costs silent operator trust in a number from the wrong
  benchmark, indefinitely, with zero on-dashboard trace. For a
  compliance product the wrong-score mode is strictly worse.
- **Required fix (smallest correct):** in `resolveBundledProfileName`,
  keep `null → VMware_SCG_8.0` (describe.xml default), but an
  **unknown non-null** name throws a `RuntimeException` with an
  actionable message ("configured benchmark_profile 'CIS_vSphere_8' is
  not bundled in this version; choose VMware_SCG_8.0 / 9.0 / 9.1 or
  Custom"), which the existing caller path wraps into
  `CollectionException` → adapter Down. Release notes / CHANGELOG
  should state the migration explicitly.
- Upgrade semantics (task item d): replacing the enum value in
  describe.xml does not, per known VCF Ops describe-merge behavior,
  block an in-place pak upgrade — the stored identifier string
  persists on existing instances, which is exactly what feeds this
  fallback. That behavior cannot be proven statically from here;
  qa-tester should upgrade a CIS-configured instance on devel as part
  of acceptance. With the loud-fail fix, that stale instance becomes a
  visible, self-explanatory Down instead of a wrong score.

## WARNING

### W1 — `vcenter-9.network-reset-port` silently lost evaluability; the parity claim is false

Independent recompute: three 9.0-evaluable control_ids are absent from
canonical 9.1 (`esx.log-level-global`, `vc.fips-enable` — genuinely
removed upstream, fine) **but `vds.network-reset-port` is not removed
upstream**. The same source control (`vcenter-9.network-reset-port`)
exists in the 9.1 CSV; upstream changed its Setting Location text
("Distributed Switch Settings" → "UI: Distributed Port Group > …"), so
`map_setting_location` now refines it to
`dvpg.network-reset-port`, the control_id-keyed
`_VIM_RECLASS_BY_CONTROL_ID["vds.network-reset-port"]` entry
(`scripts/_compliance_normalize.py:597`) no longer matches, and the row
ships `powercli_only` with no recipe (canonical scg_9.1.csv:652).

- Safe direction (informational, never a fake pass) — not a scoring
  defect. But: (1) the author's claim "no control evaluable in 9.0
  lost evaluability" is false in substance (their id-equality check
  could not see an id migration); (2) the new
  `profiles/UNAUDITED_CONTROLS.md` 9.1 caveat rests on "canonical
  control_ids are version-stable", which this control disproves.
- Fix: add a reclass entry for `dvpg.network-reset-port`
  (`bool:config.policy.portConfigResetAtDisconnect` is a
  DVPortgroupConfigInfo.policy field, so the DVPG kind is arguably the
  *more* correct target than 9.0's vds mapping), or explicitly
  document the 9.1 regression in UNAUDITED_CONTROLS.md. Either way the
  claim and the doc must stop asserting parity.

### W2 — `vc.smtp` / `vc.snmp` promoted to "evaluable" with keys that can never resolve

Canonical 9.1 reclassifies both from 9.0's `manual_audit` to
`advanced_setting` (upstream assessment-text change picked up by
`classify_parameter_kind`). Their `parameter` values are
`"mail.smtp.port, mail.smtp.username, mail.smtp.password"` (a joined
multi-key list) and `"snmp.receiver.<x>.enabled"` (literal `<x>`
placeholder) — neither is a real OptionManager key, so every cycle they
hit the absent-key branch. Proven safe: `ControlEvaluator.java:139-151`
skips absent keys unless `allowsUndefined` matches, and
"Configured"/"Disabled" match neither idiom — never a pass, never in
the denominator. But they are dead rows counted in the "101 evaluable"
claim, contrary to skill § *Unreadable is NOT compliant* ("never widen
the evaluable set without backing it with a real assessment path").
Fix: have the normalizer demote multi-key / placeholder parameters back
to `manual_audit` (restoring 9.0's classification), or split into per-key
rows with comparable expected values.

### W3 — Monkeypatch driver can silently no-op on factory drift

`scripts/normalize_scg_v91.py` patches imported factory modules by
`setattr`. Failure modes are mixed: if the factory renames/reshapes the
header constants used in the rebuilt `REQUIRED_COLUMNS` list, the run
fails loud (AttributeError or required-column hard fail against the
9.1 header). But `v9.SOURCE_TOKEN = "SCG-9.1"` and the
`COMPONENT_MAP` / `SOURCE_ID_PREFIX_MAP` updates **silently create
stale attributes** if the factory ever renames those names — the run
then succeeds and emits canonical rows with `SCG-9.0` source tokens
and unmapped 9.1 sub-products (which at least skip loudly as
`unmapped_component`, but the token drift is fully silent). Fix: guard
each patch with `if not hasattr(v9/base, NAME): raise SystemExit(...)`
so a factory rename fails the driver instead of producing plausible
wrong output. Mitigant already in place: the canonical CSV is
committed and this review reproduced it byte-for-byte, so drift is
only dangerous on a future regeneration.

## NIT

- N1 — `profiles/UNAUDITED_CONTROLS.md` states "a full 9.1
  reconciliation pass of this document is pending" — honest, but
  should be tracked so it does not silently become permanent.
- N2 — pak-compare against pre-54 baselines (e.g. 1.0.0.49) shows one
  pre-existing WARNING (ComplianceWorld group attribute count 6 vs 5,
  introduced in an earlier reviewed build). Not this change's; noted
  so the next reviewer does not rediscover it.

## Registry check (knowledge/context/defects.md)

Read in full this review. Open defects: **DEF-004** (Affects:
vcommunity-os) and **DEF-017** (Affects: factory:packaging-cli) —
**none affect the compliance pak**. Closed DEF-005's closing note asks
each Tier 2 pak to verify the shared transport as it rebuilds; this
change does not touch transport code, and the transport question
belongs to the live acceptance pass, not this static gate.
Registration candidate per RULE-012: **B1** (silent wrong-benchmark
fallback), if it were ever shipped unfixed.

## If shipped as-is

Every existing CIS-configured adapter instance keeps collecting after
upgrade and silently reports SCG 8.0 compliance scores under a
configuration that still says CIS vSphere 8; the only trace is a
collector-log warning and a property few operators inspect.

---

# Delta re-review: build 56 (commit f1334e8) — 2026-08-25

**Verdict: APPROVE** — all build-55 findings resolved; 0 BLOCKING / 0
WARNING / 2 NIT (both non-gating).

## Finding-by-finding verification (all independently re-checked)

- **B1 RESOLVED** (`BenchmarkLoader.java:112-152`). Unknown non-null
  profile name now throws with the actionable three-profiles-or-Custom
  message; null/blank keeps the describe.xml default; `Custom` without
  a path (previously also a silent SCG-8.0 scorer — a bonus fix) throws
  naming `custom_profile_path`. **End-to-end propagation proven from
  source**: `load()` → `collectWorld()` → framework
  `VcfCfAdapter.onCollect` catch block (`adapter_framework/.../VcfCfAdapter.java:800-807`)
  logs the message and calls `mapCollectException` →
  `RESOURCE_STATUS_ERROR` → `setStatusSafe` → `setResourceStatus` — a
  visible resource error state, not a swallowed log. Granularity also
  verified: `enumerateOldProfileControlKeys`
  (`ComplianceAdapter.java:577-592`) wraps its own `load()` of the
  *previous* profile name in a caught-and-warned RuntimeException, so a
  retired old name cannot crash the cycle after the operator fixes the
  config. New test `tests/.../BenchmarkLoaderTest.java` run locally via
  `ci/run_java_tests.sh`: **all assertions passed** (covers the three
  resolves, null/blank defaults, CIS/unknown throws with message
  fragments, Custom throws, filename map). Test class confirmed
  **absent from the shipped jar** (0 Test entries in
  `vcfcf_compliance.jar` inside the built pak). CHANGELOG carries an
  explicit CIS **MIGRATION** paragraph.
- **W1 RESOLVED**. Regenerated canonical carries
  `dvpg.network-reset-port | vim_property |
  bool:config.policy.portConfigResetAtDisconnect | expected true` —
  same recipe/expected as 9.0's vds entry, under the more-correct DVPG
  kind. Recomputed parity: the only 9.0-evaluable ids not evaluable in
  9.1 are `esx.log-level-global` and `vc.fips-enable`, whose source
  controls are **genuinely absent from the 9.1 source CSV** (verified),
  plus the id-migrated `vds.network-reset-port` whose source control is
  now evaluable under the new id. UNAUDITED_CONTROLS.md no longer
  asserts id stability and names the migration.
- **W2 RESOLVED**. `vc.smtp` / `vc.snmp` demoted to `manual_audit` in
  the regenerated canonical; sweep confirms **zero** remaining
  `advanced_setting` rows with comma-joined or `<...>`-placeholder
  parameters. Recomputed evaluable set: **100/260** (59
  advanced_setting + 31 vim_property + 5 esxcli-with-recipe + 5
  vami_api-with-recipe) — matches the claimed total.
- **W3 RESOLVED**. All 16 patch targets `hasattr`-guarded with a
  SystemExit naming the moved target
  (`scripts/normalize_scg_v91.py:76-98`). Canonical regeneration
  re-run by this reviewer: **byte-identical** to the committed
  `profiles/canonical/scg_9.1.csv`.
- **N1 RESOLVED**: pending-reconciliation note date-stamped
  (2026-08-25, build 56) with an explicit staleness instruction.

## Build claims (independently re-run)

validate-sdk: pass. build-sdk: `vcfcf_sdk_compliance.0.0.0.56.pak`
reproduced. pak-compare vs `0.0.0.54`: **0 BLOCKING / 0 WARNING / 5
INFO**, all intended (description text, 9.1 profiles added, CIS
profiles removed). Build number 56 + CHANGELOG line present.

## Residual NITs (non-gating)

- N2 (new) — CHANGELOG build-56 entry's evaluable breakdown says
  "9 esxcli ... with recipes": 9 is the *total* esxcli row count; only
  5 carry recipes (59+31+5+5=100; the stated total is correct, the
  parenthetical is not). Cosmetic; fix in any later commit.
- N3 (carried) — full 9.1 UNAUDITED_CONTROLS reconciliation remains
  pending, now date-stamped.

## Release-tag readiness

Nothing blocks a `v1.0.0.56` tag from this reviewer's static gate
beyond the standing qa-tester acceptance note: upgrade a
CIS_vSphere_8-configured instance in place on devel and confirm it
surfaces as a visible resource ERROR with the actionable message (and
that a one-edit profile switch recovers it). The branch also carries
the tag/adapter.yaml consistency guard (`fdd2491`), so the tag must
match `1.0.0.56` exactly. Registry: still no open defects affecting
this pak; the B1 registration candidate is withdrawn (fixed before
ship, with an executing test).
