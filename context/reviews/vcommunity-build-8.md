# SDK Adapter Review — vcommunity build 8

- **Adapter:** `content/sdk-adapters/vcommunity` (review-before-commit gate; HEAD is build 7 `bad8ad4`, working tree is build 8, uncommitted)
- **Build reviewed:** 8 (`dist/vcfcf_sdk_vcommunity.1.0.0.8.pak`, reproduced locally)
- **Reviewer:** `sdk-adapter-reviewer`
- **Scope:** the build 7→8 diff only (4 files): `VCommunityVSphereClient.java` (broad `guest` read), `VmCollector.java` (gate-skip WARN), `adapter.yaml` (7→8), `CHANGELOG.md`. Prior-build clearances stand (see build-6 review).
- **Ground truth:** prod original `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/app/` — gate predicate `properties/vm/vmService.py:131`, `events/vm/collect_windows_event_logs.py:135`, `properties/vm/vmOSInformation.py:133`; live evidence `context/investigations/recon_log.md` (2026-06-22 entries).
- **Verdict:** **APPROVE** (zero BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 2 NIT

## Independent claims verification (re-run, not trusted)

| Claim | My result | Status |
|---|---|---|
| validate-sdk passes | `python3 -m vcfops_managementpacks validate-sdk content/sdk-adapters/vcommunity` → `OK: ... valid Tier 2 SDK adapter project`; 9 sources compile clean, only the benign `-source 11` warning | **CONFIRMED** |
| build-sdk produces 1.0.0.8 pak | `build-sdk` → `Built: dist/vcfcf_sdk_vcommunity.1.0.0.8.pak` | **CONFIRMED** |
| pak-compare vs compliance = 0 BLOCKING | `pak-compare dist/vcfcf_sdk_vcommunity.1.0.0.8.pak dist/vcfcf_sdk_compliance.1.0.0.51.pak` → `Score: 0 BLOCKING, 2 WARNING, 288 INFO`. The 2 WARNINGs are the reference-topology divergence accepted since build 1 (manifest description + cred/identifier shape vs the minimal compliance reference). | **CONFIRMED** |
| defect-gate clean | `defect-gate --pak vcommunity` → `no open blocking defects affecting vcommunity` | **CONFIRMED** |

Build metadata correct: `adapter.yaml build_number: 8`, `version: 1.0.0`; CHANGELOG `1.0.0.8 (2026-06-22)` entry present, dated today, accurate. Minimal diff — only the 4 in-scope files changed, no drive-by refactor.

## Registry check (context/defects.md)

- **No open defect names `vcommunity` in `Affects:`.** DEF-001 (synology, open), DEF-002 (unifi, open), DEF-003 (synology, closed) — none affect this pak. `defect-gate --pak vcommunity` independently confirms. Nothing to re-assert.
- **Registration candidate:** the WARNING below (unproven causal claim / gap honesty) is a candidate the orchestrator may graduate per RULE-012 if it survives acceptance — it is not yet a defect, but the devel symptom it was meant to fix is unproven-resolved.

## The change — correctness verified SAFE

### Gate predicate is byte-identical to the original — VERIFIED
Original (all three collectors): `toolsStatus == "toolsOk" and guestOSFamily == "windowsGuest"` (`vmService.py:131`, `collect_windows_event_logs.py:135`, `vmOSInformation.py:133`). Java gate (`VmCollector.java:191-192`) is the exact negated form: skip unless `"toolsOk".equals(toolsStatus) && "windowsGuest".equals(guestFamily)`. No loosened literals, **no `guestId` substitution**, no `||`-for-`&&` slip. The predicate did not change in this diff at all — only the *read feeding it* changed.

### Broad `guest` read — faithful port, fails closed — VERIFIED
`vmGuestToolsStatus`/`vmGuestFamily` (`VCommunityVSphereClient.java:545-555`) now do `walkToNode(vm, dot("guest"))` then `childText(guest, "toolsStatus"/"guestFamily")` — a `RetrieveProperties` of the broad `guest` object, reading the child off the returned DOM, mirroring pyVmomi's full-`GuestInfo` materialization. This is the established broad-read idiom already used by ~20 other callers in this client (clusters, hosts, licensing, extraConfig, hardware). It is a genuine wire-level change from the prior narrow `getStringProperty(vm, "guest.toolsStatus")` (which requested the dotted sub-path in the pathSet).
- **Fails closed:** `childText` returns `null` when the child is absent (`:1120-1123`); `elementText` trims and an empty element yields `""`. `null` and `""` both fail `"toolsOk".equals(...)` / `"windowsGuest".equals(...)` (null-safe constant-first `equals`). A non-Windows or tools-down VM → gate skip, never a false-positive collection. **Unreadable-is-NOT-compliant upheld** (skill § *Unreadable is NOT compliant*).
- **Reflection-tolerant:** the read is pure DOM (`firstDirectChild`/`getTextContent`), no cast to a concrete vim25 subclass, no `getX()`/`isX()` assumption. A missing field cannot throw — it returns null → skip (skill § *vim25 over JAX-WS*, dimension 2).

### Exception granularity / crash-the-cycle — VERIFIED
The gate read is wrapped in its own `try/catch` (`VmCollector.java:183-190`): a SOAP-level failure logs an isolated WARN and `return`s (skip), and the whole `collectGuest` call sits inside the per-VM `try` at `collect:75-96`. One VM's unreadable `guest` cannot abort the collection cycle (dimension 3). No broad swallow into a silent pass — a failed read skips guest-ops for that VM, it does not fold into "collected."

### New WARN is behavior-neutral and secret-free — VERIFIED
`VmCollector.java:196-198` converts a bare `return` into `log.warn(...); return`. Control flow is identical (same predicate, same `return`) — behavior-neutral confirmed. The line logs only `v.name`, `toolsStatus`, `guestFamily`. Grep of every `log.*` line in `VmCollector.java` for `pass|cred|winUser|winPass|secret|token` → **none**. No credential/winPass in any log line (RULE-008 / `rules/no-secrets-on-disk.md`) — CLEAN.

### Side-effect / blast-radius — VERIFIED none
- Only callers of `vmGuestToolsStatus`/`vmGuestFamily` are the gate at `VmCollector.java:184-185` — no other path is affected by the broad read.
- `walkToNode`/`getLongestPrefixElement` are pure reads (local assignments only, no instance-field mutation) — no shared-state side effect on other callers.
- No stitching/identity change (the MOID/`instanceUuid` stitch is untouched), no describe-path change, no resource-hygiene change. Expected-none confirmed.

## WARNING

- **[brief vs `context/investigations/recon_log.md` 2026-06-22 — gap honesty / `rules/no-fabricated-metrics.md` (unproven causal claim)] — the build's stated root cause is not supported by the available ground truth, and the recon log actively fingers a *different* gate leg.** The CHANGELOG and brief assert the narrow `guest.toolsStatus`/`guest.guestFamily` pathSet "returned blank/stale, so every Windows VM was silently rejected" at the `toolsStatus`/`guestFamily` gate. But the recon log's own 2026-06-22 root-cause analysis concludes the zero-collection traces to the **`guestOps.ready()` leg** — the GuestOperationsManager / VMware-Tools-running readiness check (`recon_log.md:1267, 1307, 1356`) — and explicitly states *"This is NOT a pak code bug (prod has the same failure)"* (`:1307`). Those are two distinct legs: `guestOps.ready()` (`GuestOpsClient.java:91-94`) checks `guestFileManager`/`guestProcessManager`/`winUser` and is part of the `guestEnabled` precondition (`VmCollector.java:64-66`); it does **not** read `toolsStatus`/`guestFamily` at all. The recon also shows `dcint1`/`dcint2` carry their VMware-Tools OS-path keys and `toolsRunningStatus = Guest Tools Running` (`:1358`), implying `guest` data *is* reaching the adapter for those VMs — i.e. there is **no captured evidence that the narrow read returned blank**. → **Fix to the claim, not the code:** the change is correct and safe *as a parity port* (read the broad object the way the original does), and the new gate-skip WARN is exactly the instrument that will *prove or refute* the hypothesis on the next devel cycle. But do not represent build 8 as having *fixed* the observed devel zero-collection until a devel collect shows `dcint1`/`dcint2` now pass the `toolsStatus`/`guestFamily` gate (the new WARN absent for them) AND service/event keys land — OR confirms they still skip at `guestOps.ready()`, in which case build 8 did not address the real blocker. This is owed live proof, same posture as a DEF live-proof requirement. Until then the causal claim is unverified.

## NIT

- **[VCommunityVSphereClient.java:547-554] — the broad `guest` object is retrieved twice per gated VM.** `vmGuestToolsStatus` and `vmGuestFamily` each independently call `walkToNode(vm, dot("guest"))`, issuing two separate `RetrieveProperties` of the full `guest` object per Windows-candidate VM per cycle. This is not a regression (the prior shape was also two narrow round-trips) and only runs when `guestEnabled`, so it is within the bulk-read discipline (skill § *bulk-read dynamic pattern*) at current scale. A single `guest` fetch feeding both reads would halve the round-trips and the broad-object parse if the candidate set ever grows. Cosmetic at this scale.
- **[pak-compare W1/W2] — reference-topology divergence, ACCEPT.** The 2 WARNINGs (manifest description + cred-field/identifier shape vs the minimal compliance reference) are the design-mandated original shape, same accepted disposition as builds 1 and 6. Not install defects; 0 BLOCKING.

## Failure-mode hunt — cleared (change surface only)

- **Unreadable-is-NOT-compliant:** upheld — null/empty `toolsStatus`/`guestFamily` fail the gate closed; no false-positive Windows collection on a non-Windows / tools-down VM.
- **vim25 reflection-tolerance / crash-the-cycle:** upheld — pure-DOM `childText`, missing field returns null (never throws); gate read isolated per-VM in its own try/catch nested inside the per-VM try.
- **Exception granularity:** upheld — failed read skips guest-ops for that VM, does not fold into "collected" and does not abort the cycle.
- **Secrets in logs:** CLEAN — new WARN carries VM name + two enum-ish gate values only.
- **Stitching/identity, resource hygiene, describe path:** untouched by this diff; build-1/build-6 clearances stand (including the pre-existing multi-vCenter bare-MOID stitch corpus item, unchanged here).

## If shipped as-is

The adapter builds and validates clean and behaves correctly: Windows guest-ops still gates strictly on `toolsOk` + `windowsGuest`, now read from the broad `guest` object the way the prod original does, and still fails closed on any unreadable/non-Windows VM — no false-positive collection, no crash, no secret in the log. The operator additionally gets a WARN per gate-skipped VM naming the VM and the actual `toolsStatus`/`guestFamily` values, which is the diagnostic that finally makes the silent skip visible. **Caveat:** per the 2026-06-22 recon, the observed devel zero-collection on `dcint1`/`dcint2` was traced to the `guestOps.ready()` / VMware-Tools-running leg, not the leg this build touches — so an operator should not expect build 8 alone to start Windows service/event collection on devel. The new WARN is exactly what will tell them which leg is actually blocking on the next cycle. Verify on a devel collect before declaring the guest-ops symptom resolved.
