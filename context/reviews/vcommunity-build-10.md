# SDK Adapter Review — vcommunity build 10

- **Adapter:** `content/sdk-adapters/vcommunity` (pre-install/pre-tag static gate; HEAD is build 7 `bad8ad4`, working tree carries builds 8 + 9 + 10, uncommitted)
- **Build reviewed:** 10 (`dist/vcfcf_sdk_vcommunity.1.0.0.10.pak`, reproduced locally)
- **Reviewer:** `sdk-adapter-reviewer`
- **Scope:** the build 9→10 delta only — **observability-only**: surface the previously-swallowed guest-ops SOAP fault. Builds 8 and 9 were reviewed APPROVE (`context/reviews/vcommunity-build-8.md`, `-build-9.md`); those clearances stand and are not re-litigated. Four source files carry the build-10 change: `GuestOpsClient.java` (rewritten `post()` non-2xx branch + new `lastFault`/`currentVmName` fields, `lastFault()`/`clearLastFault()`/`operationName()`/`extractFaultString()`/`redactSecrets()`), `VmCollector.java` (`Result` fault recorder + `clearLastFault`/`recordFault` wiring), `VCommunityAdapter.java:415` (one new `Summary|guestops_last_error` prop), plus `adapter.yaml` 9→10 and the `1.0.0.10` CHANGELOG entry (docs README/inventory-tree touched — out of read-path scope, no behavior).
- **Verdict:** **APPROVE** (zero BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 2 NIT

## Independent claims verification (re-run, not trusted)

| Claim | My result | Status |
|---|---|---|
| validate-sdk passes | `validate-sdk content/sdk-adapters/vcommunity` → `OK: ... valid Tier 2 SDK adapter project`; 9 sources compile clean, only the benign `-source 11` warning | **CONFIRMED** |
| build-sdk produces 1.0.0.10 pak | `build-sdk` → `Built: dist/vcfcf_sdk_vcommunity.1.0.0.10.pak` | **CONFIRMED** |
| pak-compare vs compliance = 0 BLOCKING | `pak-compare …vcommunity.1.0.0.10.pak …compliance.1.0.0.51.pak` → `Score: 0 BLOCKING, 2 WARNING, 288 INFO` — same reference-topology divergence (manifest description + cred/identifier shape) accepted since build 1 | **CONFIRMED** |
| defect-gate clean | `defect-gate --pak vcommunity` → `no open blocking defects affecting vcommunity` | **CONFIRMED** |

Build metadata correct: `adapter.yaml build_number: 10`, `version: 1.0.0`; CHANGELOG `1.0.0.10 (2026-06-22)` present, dated today, accurate to the diff. Minimal diff — only the in-scope diagnostic files plus docs; no drive-by refactor of any collection path.

## Registry check (context/defects.md)

- **No open defect names `vcommunity` in `Affects:`.** DEF-001 (synology, open/blocking), DEF-002 (unifi, open/blocking), DEF-003 (synology, closed) — none affect this pak. `defect-gate --pak vcommunity` independently confirms `no open blocking defects affecting vcommunity`. Nothing to re-assert.
- **Registration candidate (WARNING-1, below).** The unredacted-username residual is a defense-in-depth gap, not a confirmed live leak (no standard vim25 guest-auth faultstring echoes the username, and `winUser` is `type="string"`, not a `password="true"` field). It is below the bar for blocking and I am not certain it survives acceptance, but I flag it so the orchestrator can graduate it per RULE-012 if the author chooses not to tighten the redactor this build.

## Behavior-neutrality — the cardinal question, verified SAFE (byte-for-byte)

The whole build is observability. The binding question is whether `post()`'s return contract and the entire collection path are genuinely unchanged.

### `post()` still returns null on non-2xx — VERIFIED against the prior source
`git show HEAD:GuestOpsClient.java` confirms the prior non-2xx handling was exactly `if (code < 200 || code >= 300) return null;`. Build 10 replaces that single statement with a block that (a) derives `op` from the SOAPAction, (b) calls `extractFaultString(resp)`, (c) sets `this.lastFault`, (d) logs WARN — and then **`return null;`** (`GuestOpsClient.java:522`). The error-stream was *already* drained into `resp` in the prior code (`conn.getErrorStream()` on non-2xx, `drain(is)`), so build 10 adds **zero new socket reads** — it only parses bytes it already had. The 2xx happy path (`:524-525`), `auth()` (`:455-462`), every SOAP body builder, `fileAttributes`, spec serialization, the file-transfer PUT/GET — all byte-identical. No new early-return, no new throw on any path a caller branches on. **Collection behavior is identical.**

### No collection-path branch reads the new state — VERIFIED
`lastFault`/`currentVmName` are written by `post()` and the collector entry points and read **only** by the WARN line, `lastFault()` (→ anchor diagnostics), and the per-VM fault attribution. No gate, no `ready()`, no row count, no skip decision reads either field. `currentVmName` is assigned at all three public collector entry points (`collectServices:164`, `collectOsInfo:230`, `collectEvents:318` region) before any `post()`; a missed assignment degrades only to the literal `"?"` in a diagnostic string, never a crash or a collection change.

## Secrets — the highest-risk item, analyzed with an executed redactor test

The new readable surfaces are `Summary|guestops_last_error` (anchor property), the new WARN line, and the `lastFault` field. The only attacker/server-controlled text reaching any of them is the vim25 `<faultstring>`/`<localizedMessage>`, **post-`redactSecrets()`**. I confirmed `GuestOpsClient.redactSecrets` is byte-identical to `VCommunityVSphereClient.redactSecrets` (the "mirrors" claim is accurate) and ran it standalone against realistic vim25 guest-auth fault strings:

| Fault string | Redacted output | Disposition |
|---|---|---|
| `Failed to authenticate with the guest operating system using the supplied credentials.` | unchanged | SAFE — no credential present |
| `Permission to perform this operation was denied.` | unchanged | SAFE |
| `password=Sup3rSecret! was rejected` | `password=<redacted> was rejected` | **REDACTED** |
| `passwd: hunter2` | `passwd: <redacted>` | **REDACTED** |
| `vmware_soap_session="52a1b..." expired` | `vmware_soap_session=<redacted> expired` | **REDACTED** |
| `login failed for user 'Administrator'` | **unchanged** | residual — bare username passes (see WARNING-1) |

- **Password / session-id vector — SAFE.** vim25 never echoes the supplied guest password back in a fault; even a hypothetical `password=`/`passwd=`/`vmware_soap_session=` run is caught by the redactor. The SOAP fault body does not echo the request body (`auth()` `<password>` element), so the password cannot route into the property. `winPassword` is read by no build-10 code (`grep` confirms it appears only in the constructor, `auth()`, and the `// REDACT-SECRET` doc markers).
- **Realistic guest-auth faults — SAFE.** The two faultstrings vim25 actually returns for a bad/denied Windows credential (`InvalidGuestLogin`, `GuestPermissionDenied`) carry no credential material and pass through as plain operator-useful text — which is the whole point of the build.
- **RULE-008 / `rules/no-secrets-on-disk.md`:** no password, token, `_sid`, or session cookie can reach the on-disk adapter log or the readable anchor property. CLEAN on the secret-class material the rule governs.

## Bounded / fail-closed / crash-safe — VERIFIED

- **Bounded** (`rules/no-fabricated-metrics.md` n/a; dimension 7 memory safety): `recordFault` (`VmCollector.java`) appends a detail entry only while `faultsRecorded < MAX_FAULT_DETAIL (5)`, always increments, and `guestLastErrorSummary()` emits ≤5 entries plus a single `(+N more faulted, detail capped)` overflow. One anchor property, not per-VM — no property flood. `Result` is freshly constructed each `collect()`, so `faults`/`faultsRecorded` never accumulate across cycles. Same proven bounding pattern as build-9's `recordSkip` (cap 5 here vs 10 there).
- **Fail-closed / quiet:** `extractFaultString` returns null on an empty/unparseable body (`parseXml` catches internally → null), driving `post()`'s `else` branch to record `"<op> -> HTTP <code> (no SOAP faultstring in body)"` — never a crash, never an empty NPE. `recordFault` ignores a null fault (a non-faulting empty cycle records nothing). `guestLastErrorSummary()` returns `"none"` at minimum, and `prop()` writes `""` for a null value. An unparseable fault degrades to readable text, never a thrown exception aborting the push (skill § *Unreadable is NOT compliant* — the failure is surfaced, not folded into a pass).
- **Crash-the-cycle isolation** (skill § *vim25 over JAX-WS*, dimension 2/3): no new cast to a concrete vim25 subclass; `extractFaultString`/`operationName`/`redactSecrets` are pure static string/DOM ops with null guards; `firstByLocalName`/`elementText` null-guard. No new exception type escapes `post()` beyond what the prior `throws Exception` already declared, and the per-VM `try` in `VmCollector`/the per-method `catch` in each collector still wrap everything. A fault-parse failure on one VM cannot abort the cycle.
- **Concurrency:** `lastFault`/`currentVmName` are `volatile`; guest-ops is documented single-threaded (CHANGELOG "Guest-ops scope/concurrency — single-threaded"). `clearLastFault()` runs before a VM's calls (happy path) and `recordFault(v.name, guestOps.lastFault())` reads after, within one VM's serial sequence — no race, attribution is correct per VM.

## Failure-mode hunt — cleared (build-10 surface only)

- **Unreadable-is-NOT-compliant / widened evaluable set:** upheld — the gate predicate is untouched; the captured fault never widens what is collected and never becomes a pass. A faulting VM still returns empty (unchanged), now *also* recording the fault as a fault — the opposite of folding a failed read into a pass.
- **vim25 reflection-tolerance / crash-the-cycle:** upheld — pure-DOM fault parse, null on absence, no concrete-subclass cast.
- **Exception granularity:** upheld — the formerly-silent swallow is now logged at WARN with operation + VM context; no real error is hidden, none newly aborts the cycle.
- **Stitching / identity:** untouched — no relationship/MOID change in this diff.
- **Memory / resource hygiene:** upheld — bounded fault summary, fresh per-cycle `Result`, no new session/handle (`post()` still `conn.disconnect()`s), no unbounded growth.
- **Build hygiene:** `build_number` 9→10, matching CHANGELOG line, minimal diff; pure additive observation — no existing collection call site changed behavior.

## WARNING

- **[GuestOpsClient.java:567-575 `redactSecrets`] — `rules/no-secrets-on-disk.md` (RULE-008), defense-in-depth.** The redactor catches `password=`/`passwd=`/`account=`/`_sid=`/`vmware_soap_session=` runs but does **not** redact a bare attempted username quoted in free text (executed test: `login failed for user 'Administrator'` passes through unchanged onto the readable `Summary|guestops_last_error` property and the WARN log). The Windows username is `type="string"` (not a `password="true"` field, so not secret-classified), and no standard vim25 guest-auth faultstring (`InvalidGuestLogin`/`GuestPermissionDenied`) echoes it — so this is a residual hardening gap, not a confirmed leak, which is why it is WARNING and not BLOCKING. → Smallest correct fix: extend the redactor to drop any quoted `winUser` value when present (the client already holds `winUser` — `s.replace(winUser, "<user>")` after the existing passes), so even a non-standard vendor fault that quotes the attempted account cannot surface it. Cheap belt-and-braces; closes the exact vector the brief flagged.

## NIT

- **[GuestOpsClient.java:511 fault attribution]** — `currentVmName` is `volatile` instance state set per entry point rather than threaded as a `post()` parameter; correct under the documented single-threaded model, but a future move to per-VM concurrency (roadmap v2) would make attribution racy. Tie a `vmName` argument onto `post()` when concurrency lands. Cosmetic at current scope.
- **[pak-compare W1/W2]** — reference-topology divergence, ACCEPT. The 2 WARNINGs (manifest description + cred-field/identifier shape vs the minimal compliance reference) are the design-mandated original shape, same accepted disposition as builds 1, 6, 8, 9. Not install defects; 0 BLOCKING.

## If shipped as-is

The adapter builds and validates clean and **collection is byte-for-byte unchanged** — `post()` still returns null on every non-2xx, the auth, spec serialization, fileAttributes and the whole collection path are identical; build 10 only *reads* the error bytes it already drained and surfaces them. An operator gains the missing diagnostic: `Summary|guestops_last_error` on the `vCommunityWorld` anchor now names the exact vim25 fault (operation + fault class + message, bounded ≤5 + overflow, `"none"` when clean) behind devel's silent zero-row guest collection, plus a matching WARN — readable via the Suite API even with the appliance log 404. No false-positive collection, no extra round-trip, no unbounded property growth, no crash path. The realistic guest-auth faults and any `password`/session-id echo are safe (redactor verified by executed test); the one residual is that a non-standard fault quoting the bare attempted username would surface it on a readable property (WARNING-1) — credential-adjacent but not a secret-classified field, and trivially closable by extending the redactor with the `winUser` value the client already holds.
