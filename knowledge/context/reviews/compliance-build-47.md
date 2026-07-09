# SDK Adapter Review — compliance build 47

- **Adapter:** `content/sdk-adapters/compliance`
- **Build reviewed:** 47 (commit `f24540a`) vs APPROVEd 46 (`7d93781`)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 1 BLOCKING / 1 WARNING / 1 NIT
- **Date:** 2026-06-10

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| Diff scope = only named hunks | **Confirmed.** `git diff 46→47` touches exactly: `VSphereClient` (new `AdvancedSettingsUnreadableException`, `getAdvancedSettings` null-guard return→throw, new `getHostConnectionState`); `ControlEvaluator` (one additive `evaluateControlsUnreadable`); `ComplianceAdapter` (host-loop guard + `isDisconnectedState` + `unreadableVimResult`); version/docs. |
| `evaluateControls` / `evaluateVimProperties` zero modified lines | **Confirmed.** Both byte-identical (ControlEvaluator.java:101–200, 322–415). `queryOptions`, `readByRecipe`, `getMoRefProperty`, `getRawPropertyElement`, `elementText` bodies untouched (the `queryOptions`/`getMoRefProperty` diff hits are call-sites inside `getAdvancedSettings`, not body edits). |
| framework jar UNCHANGED (sha `9a1e5974…`) | **Confirmed by sha256.** `vcfcf-adapter-base.jar` = `9a1e59749edf56e0b34be2a0a266cdd0e8daef437e2164f1ddb305c5ed3e337e` in both pak 46 and pak 47. No framework delta. |
| pak-compare 47-vs-46 = 0/0/0 | **Confirmed structurally** (buildkit unavailable in sandbox; verified by direct pak extraction). File structure identical, `describe.xml` identical, all 6 profile CSVs byte-identical, only `manifest.txt` version string `1.0.0.46`→`1.0.0.47`. New `AdvancedSettingsUnreadableException.class` compiled into the adapter jar; adapter jar sha differs as expected. |
| validate-sdk clean | **Inferred-confirmed.** The buildkit is not present in this checkout (pulled from the published `sdk-buildkit` tarball at build time), so I could not re-invoke `validate-sdk` directly. The shipped `dist/…47.pak` compiled the build-47 sources into a well-formed adapter jar (all expected classes present), which is the compile-gate `validate-sdk` enforces. No discrepancy observed. |

## Healthy-host parity (the hard constraint) — PASS

Traced the connected-host path end-to-end (ComplianceAdapter.java:570–626).
It is operation-identical to build 46: same `vsphere.getAdvancedSettings` →
`evaluateControls(hostControls, advSettings, hostName)` (the `advUnreadable`
flag is `false` on the success path, selecting the identical evaluator call),
same `evaluateVimForResource`, same `mergeResults`, same
`stats.total++ / if (cr.totalCount>0) { scored++; scoreSum+=; belowThreshold }`
gating, same `pushComplianceViaClient`. The connection-state guard (535–568)
sits entirely *before* the success path and only `continue`s on an explicit
disconnected/notResponding state. The 7 passing hosts do not move.

## Unreadable accounting — arithmetically coherent

`evaluateControlsUnreadable` (ControlEvaluator.java:224–252) mirrors
`evaluateControls`' parameterKind/N/A/empty/multiline filters exactly, folds
each evaluable `advanced_setting` control to one `(unreadable)` ControlResult,
and returns `pass=0, fail=0, total=0, unreadable=N, score=100.0`. The
`totalCount=0 + unreadableCount=N` convention matches build 43's vim_property
unreadable precedent (`evaluateVimProperties` lines 376–386: unreadable counted,
excluded from pass/fail/total). The world rollup gate
(ComplianceAdapter.java:330 `if (hostStats.scored > 0)`) keys on `scored`, which
is only incremented when `cr.totalCount > 0` — a disconnected host's
`totalCount==0` result never reaches `scoreSum`, so it **cannot skew
`avg_host_score`**. The "No hosts produced real compliance signal" else-branch
(335–340) fires correctly if every host is unreadable. `total = scored + (not
scored)`; `unreadable` accumulates independently into
`Summary|total_unreadable_controls`. Accounting closes.

## Systemic-failure granularity (claim 5) — acceptable

`collectWorld` (293) and `collectHosts` (512) are `throws Exception`; a
vCenter-wide outage throws from `vsphere.ensureConnected()` / `getHosts()` and
propagates to the adapter (cycle errors / DOWN) — it does NOT present as 8 quiet
unreadable hosts. The per-host catch-all (586) and the connection-state guard
only engage *after* `getHosts()` succeeded, i.e. genuine per-host degradation.
If every connected host is individually unreadable, `hostStats.scored==0` →
`avg_host_score` suppressed with a loud WARN + a large
`total_unreadable_controls`. Honest, not green. PASS.

## Exception hygiene & logging — PASS

Typed `AdvancedSettingsUnreadableException` caught at per-host scope (574); the
catch-all (586) is per-host and the loop `continue`s, so one host never aborts
the cycle. `getHostConnectionState` failure is caught (538) → `connState=null` →
treated as unknown → normal evaluation (does NOT fabricate disconnected).
`isDisconnectedState(null)==false` (claim 6 confirmed). All new WARNs route
through the framework-base `logWarn` (the visible path, per the investigation's
E2 finding), not the dead helper logger. No credentials/tokens in any new log
line — messages carry host name + connectionState enum + exception message only
(`knowledge/rules/no-secrets-on-disk.md` upheld). `getHostConnectionState` is a
reflection-tolerant DOM read (`getStringProperty` → null on absent element,
never throws) — skill § *vim25 over JAX-WS* upheld.

---

## BLOCKING

- **[ComplianceAdapter.java:560–566 (disconnected-host push) + :1124]** —
  skill § *Unreadable is NOT compliant* (zero-divisor contract: "every caller
  refuses to fold a `totalCount==0` result"). The disconnected-host branch
  pushes its `ComplianceResult` through the unmodified `pushComplianceViaClient`,
  which **unconditionally** publishes `VCF-CF Compliance|score = cr.score` —
  and for an unreadable host `cr.score = 100.0` (the zero-divisor sentinel from
  `evaluateControlsUnreadable`, line 250). So a host that could not be read at
  all now lands a **per-resource `score = 100` stat** on its own HostSystem.

  The world rollup correctly refuses to fold this (gated on
  `totalCount>0`), but the **per-host symptoms do not**:
  `content/symptoms/host_compliance_score_warning.yaml` and
  `host_compliance_score_critical.yaml` fire on `VCF-CF Compliance|score LT 95 /
  LT 80` with no `total_count>0` guard. A `score=100` push reads as fully
  compliant → **neither symptom fires** and the host shows a green 100 on the
  compliance scoreboard while it is actually unreadable. This is strictly worse
  than build 46, where the disconnected host pushed a non-zero (83.33) score
  that at least tripped the WARNING symptom. The honesty signal
  (`unreadable_count`, the WARN log) is real, but the headline `score` metric —
  the one an operator and the symptoms key on — actively reads "perfect" on a
  blind host. That is the cardinal "unreadable becomes a folded score=100"
  failure, now on a per-resource stat.

  → **Smallest correct fix (adapter side, where the regression is introduced):**
  in `pushComplianceViaClient`, when `cr.totalCount == 0`, do **not** push
  `VCF-CF Compliance|score` (and `pass_count`/`fail_count`) — push only
  `total_count=0` + `unreadable_count`, leaving `score` absent so the per-host
  symptoms see "no data" rather than a sentinel 100. (Mirror the exact
  `if (… scored > 0)` discipline the world rollup already uses at
  ComplianceAdapter.java:330.) Do not push a `score=0` either — 0 would
  false-trip CRITICAL and is equally dishonest. Absent is the only honest value
  for a `totalCount==0` per-resource push. The factory-side symptom hardening
  (add a `total_count>0` companion condition) is a defensible belt-and-suspenders
  but is out of this adapter's scope and does not substitute for not emitting the
  sentinel.

## WARNING

- **[ComplianceAdapter.java:541–568 vs :596–600]** — skill § *Unreadable is NOT
  compliant* (consistency of the unreadable push). The disconnected-host branch
  pushes a host result with `vim/esxcli` controls folded to UNREADABLE via
  `unreadableVimResult` *plus* advanced_setting via `evaluateControlsUnreadable`,
  i.e. ALL ~42 controls marked `(unreadable)`. The *flap-between-reads* branch
  (`advUnreadable`, 596–600) folds only the **advanced_setting** channel and
  still runs `evaluateVimForResource` live for vim/esxcli — so that host can
  still emit a partial `totalCount>0` score from the vim channel that resolved
  from cache. That is the build-46 partial-score shape resurfacing on the narrow
  flap window (connectionState read OK, OptionManager MoRef gone a moment later).
  It is genuinely rarer than the build-46 bug and the advanced_setting channel
  is now honest, so this is a WARNING not a BLOCKING — but the two unreadable
  paths are not symmetric, and the flap path can still publish a
  flattering-but-smaller partial host score. → Consider, when
  `AdvancedSettingsUnreadableException` fires, treating the whole host as
  unreadable (same as the connection-state branch) rather than only the
  advanced_setting channel — a host whose OptionManager just vanished is the same
  disconnected host, and its cached vim reads are equally suspect.

## NIT

- **[CHANGELOG.md:3]** — the 1.0.0.47 entry is a single ~450-word paragraph.
  Content is accurate and traces the fix to the investigation, but the
  wall-of-text format is hard to diff against future entries. Consider the
  numbered-list form the body already uses. Non-blocking.

## If shipped as-is

An operator watching a flapping/disconnected ESXi host (the exact esx04 scenario
this build exists to fix) would see its per-host `VCF-CF Compliance|score` read
**100 (green / fully compliant)** with **no symptom or alert firing**, because
the unreadable host now pushes the zero-divisor sentinel score onto its own
resource. The world scoreboard is honest (avg suppressed, unreadable count
loud), but the per-host view and the two compliance symptoms are actively
misled — a blind host masquerades as a perfect one. The denominator-collapse of
build 46 is fixed; the per-resource sentinel-score leak it traded for is a new
silent false-pass on the same host.

## Verification artifacts

- Framework jar sha (46 == 47): `9a1e59749edf56e0b34be2a0a266cdd0e8daef437e2164f1ddb305c5ed3e337e`
- Adapter jar sha 46: `b631dfb6…` / 47: `0632edcc…` (differs, expected)
- Pak structural compare 47-vs-46: identical file tree, identical describe.xml,
  6/6 profile CSVs byte-identical, manifest version-string only.
- Working tree left clean.
