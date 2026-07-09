# SDK Adapter Review — vcommunity build 9

- **Adapter:** `content/sdk-adapters/vcommunity` (pre-install/pre-tag static gate; HEAD is build 7 `bad8ad4`, working tree carries builds 8 + 9, uncommitted)
- **Build reviewed:** 9 (`dist/vcfcf_sdk_vcommunity.1.0.0.9.pak`, reproduced locally)
- **Reviewer:** `sdk-adapter-reviewer`
- **Scope:** the build 8→9 delta only — all behavior-neutral guest-ops decision diagnostics. Build 8 was reviewed APPROVE (`context/reviews/vcommunity-build-8.md`); that diff's clearances stand. Four source files changed vs build 8: `GuestOpsClient.java` (new `readyReason()`), `VCommunityVSphereClient.java` (new `vmGuestId()`), `VmCollector.java` (`Result` diagnostics + tally + bounded skip summary), `VCommunityAdapter.java:411-413` (three `Summary|*` props), plus `adapter.yaml` 8→9 and the `1.0.0.9` CHANGELOG entry (docs README/inventory-tree also touched — out of read-path scope, no behavior).
- **Ground truth:** `ready()` predicate `GuestOpsClient.java:91-94`; gate predicate `VmCollector.java:263-264`; recon `context/investigations/recon_log.md` (2026-06-22).
- **Verdict:** **APPROVE** (zero BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT

## Independent claims verification (re-run, not trusted)

| Claim | My result | Status |
|---|---|---|
| validate-sdk passes | `validate-sdk content/sdk-adapters/vcommunity` → `OK: ... valid Tier 2 SDK adapter project`; 9 sources compile clean, only the benign `-source 11` warning | **CONFIRMED** |
| build-sdk produces 1.0.0.9 pak | `build-sdk` → `Built: dist/vcfcf_sdk_vcommunity.1.0.0.9.pak` | **CONFIRMED** |
| pak-compare vs compliance = 0 BLOCKING | `pak-compare …vcommunity.1.0.0.9.pak …compliance.1.0.0.51.pak` → `Score: 0 BLOCKING, 2 WARNING, 288 INFO` — the same reference-topology divergence (manifest description + cred/identifier shape) accepted since build 1 | **CONFIRMED** |
| defect-gate clean | `defect-gate --pak vcommunity` → `no open blocking defects affecting vcommunity` | **CONFIRMED** |

Build metadata correct: `adapter.yaml build_number: 9`, `version: 1.0.0`; CHANGELOG `1.0.0.9 (2026-06-22)` present, dated today, accurate. Minimal diff — only the in-scope diagnostic files plus docs; no drive-by refactor of any collection path.

## Registry check (context/defects.md)

- **No open defect names `vcommunity` in `Affects:`.** DEF-001 (synology, open), DEF-002 (unifi, open), DEF-003 (synology, closed) — none affect this pak. `defect-gate --pak vcommunity` independently confirms `no open blocking defects affecting vcommunity`. Nothing to re-assert.
- **Build-8 owed-proof note (not a registry defect).** The build-8 review's single WARNING was an *unproven causal claim* — whether the zero-collection is the narrow-read gate (build-8 target) or the `guestOps.ready()` leg (recon's prime suspect). It was never graduated to a defect; it is owed live proof. **Build 9 is the instrument that pays that debt:** `Summary|guestops_ready` now reads the `ready()` outcome on the anchor (`vCommunityWorld`), which the Suite API can read even though the appliance adapter log is 404. One install + recon now reads which leg blocks. Build 9 does not itself resolve the claim — a devel collect still does — but it makes it resolvable without appliance log access, which the build-8 WARNING explicitly called the missing ground-truth window.
- **No registration candidate.** No WARNING-or-worse finding in this build.

## Behavior-neutrality — the cardinal question, verified SAFE

The whole build is diagnostics. The binding question is whether collection is genuinely unchanged and whether `readyReason()` can report a different answer than the real gate. Both verified.

### `readyReason()` cannot diverge from `ready()` — VERIFIED byte-for-byte
`ready()` (`GuestOpsClient.java:91-94`): `guestFileManager != null && guestProcessManager != null && winUser != null && !winUser.isEmpty()`. `readyReason()` (`:104-108`) tests the **same three predicates in the same order**: `guestFileManager == null` → `guestProcessManager == null` → `winUser == null || winUser.isEmpty()` → else `"true"`. Each `false (...)` branch is the exact negation of the corresponding `ready()` conjunct, evaluated in `ready()`'s short-circuit order, so the first reported failing leg is exactly the leg that would have made `ready()` return false. `readyReason()=="true"` iff `ready()==true`. No fourth check, no reordered check, no loosened literal. A diagnostic that lied about the gate would be worse than none; this one cannot. (skill § *Unreadable is NOT compliant* — the diagnostic faithfully mirrors the decision; `rules/no-fabricated-metrics.md` — it reports the real predicate, not a fabricated proxy.)

### `guestopsReady` precedence in `VmCollector` mirrors `guestEnabled` — VERIFIED
`VmCollector.java:118-126` assigns `guestopsReady` in exactly the order `guestEnabled` (`:128-130`) short-circuits: DISABLED → no-credential → `guestOps == null` → else `guestOps.readyReason()`. So the anchor string distinguishes *monitoring off* / *no credential* / *client unresolved* / *ready() precondition failed* — the four legs the recon needs to disambiguate — and never claims `ready()` ran when `guestEnabled` would have short-circuited before it. Faithful to the existing decision path.

### `vmGuestId()` is skip-path only, no extra collect-path round-trip — VERIFIED
`collectGuest` (`VmCollector.java:247-284`): the happy path (gate passes, `:282` onward) calls only `vmGuestToolsStatus` + `vmGuestFamily` — exactly the two reads build 8 already issues. `vmGuestId(vm)` is invoked **only inside the `if (!toolsOk || !windowsGuest)` skip block** (`:271-273`) and inside the gate-read-failure catch path it is *not* called at all (the catch records `"READ_FAILED"` literals, `:260`). So a VM that *would be collected* incurs zero new SOAP round-trips. The new round-trip lands only on VMs already being rejected — which by definition are not collected this cycle. (skill § *The bulk-read dynamic pattern* — no N+1 added to the collect path.)

### `vmGuestId()` cannot crash the cycle — VERIFIED
`vmGuestId` (`VCommunityVSphereClient.java:563-567`) is the established broad-read idiom: `walkToNode(vm, dot("guest"))` then `childText(guest, "guestId")` — pure DOM, no cast to a concrete vim25 subclass, no `getX()`/`isX()` assumption; `childText` returns `null` on an absent child (never throws on absence). Its one call site (`:272`) is itself wrapped in `try { guestId = vs.vmGuestId(vm); } catch (Exception ex) { guestId = "READ_FAILED"; }`, which sits inside `collectGuest`, which sits inside the per-VM `try` at `:139-160`. Three layers of isolation: a SOAP/parse failure on the diagnostic read degrades to the literal `"READ_FAILED"` for that one VM and never propagates. (skill § *vim25 over JAX-WS*, dimension 2; dimension 3 exception granularity — upheld.)

### Skip summary is genuinely bounded — VERIFIED no unbounded growth
`recordSkip` (`VmCollector.java:77-87`) appends a detail entry **only while `skipsRecorded < MAX_SKIP_DETAIL` (10)** and always increments the counter; `guestSkipsSummary` (`:90-98`) emits the ≤10 detailed entries plus, when `skipsRecorded > 10`, a single `(+N more skipped, detail capped)` overflow count. The summary is **one** anchor property (`Summary|guestops_skips`), not a per-VM property — there is no per-VM property explosion, and the string length is bounded by 10 entries regardless of fleet size. `Result` is freshly constructed each `collect()` call (`:108`), so `skips`/`skipsRecorded` do not accumulate across cycles. This is the opposite of the property-flood pattern — it is the bounded summary that avoids it. (Memory safety / resource hygiene, dimension 7 — upheld.)

### Diagnostics fail closed / quiet — VERIFIED
- `prop` (`VCommunityAdapter.java:478-481`) writes `value != null ? value : ""` — a null diagnostic becomes an empty string, never a crash. All three new props pass non-null strings anyway: `guestopsReady` is always assigned a non-null literal or `readyReason()` (never null); the `guestops_vms` tally is a plain string concat of ints; `guestSkipsSummary()` returns `"none"` at minimum.
- `nz()` guards every value placed into the skip summary (`:83-85`), so a null `toolsStatus`/`guestFamily`/`guestId`/`vmName` renders as empty text rather than throwing.
- Unreadable values surface as empty/`READ_FAILED` text — never a fabricated pass, never a thrown exception aborting the push. (skill § *Unreadable is NOT compliant*.)

### Secrets — VERIFIED CLEAN
None of the three `Summary|*` values nor the updated log lines carry credential material.
- `Summary|guestops_ready`: the only credential-adjacent token it can emit is the literal string `"false (winUser=empty)"` — emitted **only when winUser is empty**, so it never discloses a real username, and it never references `winPassword` at all. `readyReason()` reads no password.
- `Summary|guestops_vms`: integer counts only.
- `Summary|guestops_skips`: `vmName`, `toolsStatus`, `guestFamily`, `guestId` — all confirmed non-secret per the brief; `guestId` is the VM's OS identifier (e.g. `windows2025_64Guest`), not credential material.
- The updated `log.info` summary line (`:162-168`) and the new skip WARN (`:274-277`) carry VM name + gate enum values + `guestopsReady` only.
- `grep` of `GuestOpsClient.java` + `VmCollector.java` for `winPass|winPassword|password|getPassword|token|secret` returns only the constructor field and doc comments — **no secret value flows into any prop or log line**. `winPassword` is never read by any build-9 code. (RULE-008 / `rules/no-secrets-on-disk.md` — CLEAN.)

## Failure-mode hunt — cleared (build-9 surface only)

- **Unreadable-is-NOT-compliant / widened evaluable set:** upheld — the gate predicate (`:263-264`) is untouched (strict `toolsOk` + `windowsGuest`); no `guestId` substitution into the gate; diagnostics never widen what gets collected. A skipped VM is recorded as skipped, never folded into "passed."
- **vim25 reflection-tolerance / crash-the-cycle:** upheld — `vmGuestId` is pure-DOM broad-read, returns null on absence, wrapped in its own catch nested in the per-VM try.
- **Exception granularity:** upheld — diagnostic read failures degrade to `READ_FAILED` text for one VM; never abort the cycle, never swallow a real collection error into a pass.
- **Stitching / identity:** untouched — no relationship/MOID change in this diff (the pre-existing multi-vCenter bare-MOID stitch corpus item is unchanged and out of build-9 scope).
- **Memory / resource hygiene:** upheld — bounded skip summary, fresh per-cycle `Result`, no new session/handle, no unbounded growth.
- **Build hygiene:** `build_number` 8→9, matching CHANGELOG line, minimal diff; the author generalized nothing — these are pure additive observations, behavior-preservation on existing controls is structural (no existing call site changed).

## NIT

- **[VCommunityVSphereClient.java vmGuestToolsStatus/vmGuestFamily/vmGuestId] — the broad `guest` object is now fetched up to three times per gate-skipped VM.** Carried forward from the build-8 NIT (two fetches per gated VM) and extended by one on the skip path: `vmGuestToolsStatus`, `vmGuestFamily`, and now `vmGuestId` each independently `walkToNode(vm, dot("guest"))`, so a skipped VM triggers three `RetrieveProperties` of the full `guest` object. Diagnostics-only, skip-path-only, and the CHANGELOG states the whole feature is pruned once the blocking leg is confirmed — within the bulk-read discipline at current scale. A single `guest` fetch feeding all three reads would third the round-trips if the candidate set ever grows. Cosmetic; ties off when the diagnostics are removed.
- **[pak-compare W1/W2] — reference-topology divergence, ACCEPT.** The 2 WARNINGs (manifest description + cred-field/identifier shape vs the minimal compliance reference) are the design-mandated original shape, same accepted disposition as builds 1, 6 and 8. Not install defects; 0 BLOCKING.

## If shipped as-is

The adapter builds and validates clean and collection is **genuinely unchanged**: the strict `toolsOk` + `windowsGuest` per-VM gate and the `ready()` precondition both behave exactly as in build 8 — build 9 only *observes* them. An operator gains three readable diagnostics on the `vCommunityWorld` anchor — `Summary|guestops_ready` (the exact `ready()` outcome or the first failing leg, faithful to the real predicate), `Summary|guestops_vms` (considered/passed/skipped tally), and `Summary|guestops_skips` (bounded ≤10-entry per-VM skip reasons with the actual gate values) — readable via the Suite API even though the appliance adapter log is 404. This is precisely the instrument the build-8 review said was owed: one install + one recon will now show whether devel zero-collection is the gate leg build 8 touched or the `guestOps.ready()` leg the recon fingered, **without** appliance log access. No false-positive collection, no extra round-trip on any VM that would be collected, no unbounded property growth, no crash path, and no secret in any property or log line.
