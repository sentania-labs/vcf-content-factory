# Review: template adapter build 2 (`fix/review-findings-build-2`)

- **Adapter:** `content/sdk-adapters/template` (sentania-labs/vcf-content-factory-sdk-template)
- **Branch:** `fix/review-findings-build-2` at `65d52aa`, compared against `origin/main` (build 1)
- **Scope:** design `knowledge/designs/sdk-adapters/template-build-2-review-findings.md` items 1 to 9 (issues #8, #13, #10, #9, #14, #12, #16, #15, #17). CI items 10 and 11 are a separate PR and were not reviewed.
- **Reviewer:** sdk-adapter-reviewer, 2026-10-16
- **Verdict: CHANGES REQUESTED** (1 BLOCKING, 2 WARNING, 6 NIT)

## Verdict in one line

The nine fixes are present and mostly right, and the build reproduces clean, but the new host validator copies a credential the operator pasted into the Host field (`https://admin:pw@nas`) into an error message that is logged every collection cycle and shown in Test Connection, which is the one thing the template's redaction section says never to do.

## Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` (JDK 17.0.20.1) | 7 test classes, all assertions passed. JDK 25 leg of the CI matrix not reproduced locally (no JDK 25 on the workstation). |
| `validate-sdk content/sdk-adapters/template` | OK (one benign javac `-source 11` options warning). |
| `build-sdk` build 1 from `git archive origin/main` | `vcfcf_sdk_example_adapter.0.0.0.1.pak`, built. |
| `build-sdk` build 2 from the branch | `vcfcf_sdk_example_adapter.0.0.0.2.pak`, built. Jar carries the five new helper classes; packaged `describe.xml` has `allowInsecure default="false"`. |
| `pak-compare` build 2 vs build 1 | PASS, 0 BLOCKING / 0 WARNING / 0 INFO. Matches the author's claim. |
| README buildkit steps | `gh release download sdk-buildkit-v1.0.11 --pattern 'sdk-buildkit-1.0.11.tgz*'` fetches both assets; `sdk-buildkit-1.0.11.tgz.sha256` holds `2b82728b...e2629e8`, which equals the GitHub asset digest, and `sha256sum -c` prints `OK`. |
| Em-dash / non-ASCII scan | Zero em-dashes, en-dashes or other non-ASCII on added lines of the diff and in all nine commit messages. |
| Registry (`knowledge/context/defects.md`) | No open (or closed) defect names `template` in `Affects:`. No `defects.local.md`. |

Side effect to note: `build-sdk` rewrites `docs/README.md` and `docs/inventory-tree.md` in the adapter repo (stamp `0.1.0.1` to `0.0.0.2`). I restored both files with `git checkout --` after my build so the branch is as the author left it; `git status` is clean.

Edge cases probed with a scratch harness against the branch classes (not committed anywhere):

- `[:]`, `[:::::]`, `[1:2:3:4:5:6:7:8:9]` rejected (via the `URI` constructor); `[::1]` accepted.
- `admin:S3cret@nas.lab` and `https://admin:S3cret@nas.lab` rejected, **with the password in the message** (B1).
- `ExampleValues.numericOrNull`: `42d` gives 42.0, `0x1p3` gives 8.0, `1f` gives 1.0 (N1).
- `BoundedBody` against a local server answering HTTP 500 with a 20-second body stream and a 2-second request timeout: `send()` returned only after 20,156 ms, when the server stopped (W1).

## Findings, ranked

### BLOCKING

**B1. The host validator writes a pasted credential into the adapter log every cycle and into the Test Connection dialog.**
`src/com/vcfcf/adapters/example/ExampleConfig.java:122`, `:129`, `:144`, `:170` (each message embeds the raw host `h`), reached through `ExampleAdapter.java:137-139` (`configError = e.getMessage()` plus `logError`) and `ExampleAdapter.java:398-401` (rethrown as `IllegalStateException("...invalid: " + invalid)` on every read).
Authority: RULE-008 `knowledge/rules/no-secrets-on-disk.md` ("Scrub error paths. An exception can carry a URL with embedded credentials"); review dimension 6 (a secret in a log is BLOCKING); the template's own idiom 7 at `ExampleAdapter.java:69-71` ("Never put a secret in a log line, exception message, or URL").
Failure scenario: an operator pastes `https://svc-ops:Hunter2@nas.lab` into Host / IP Address. The `@` check fires, correctly, and the message it builds is `Host / IP Address 'https://svc-ops:Hunter2@nas.lab' must be a bare hostname...`. That string is logged at ERROR with a stack trace on configure, then the framework logs it again at WARN on every cycle (`onCollect: rediscovery failed` and `onCollect: error collecting <resource>` for each resource), and `onTest` puts it in the UI dialog and logs it. The validator is the code that knows user-info is present, and it is the code that copies it out. Build 1 logged the raw host once at INFO; build 2 logs it every cycle. Every pak instantiated from the template inherits this.
Smallest fix: never echo the raw value once it has failed the character check. For example, when `h` contains `@`, say "must not contain a user name or password (`@`)" without the value, or echo only the part after the last `@`. Apply the same rule to the IPv6 branch (`[admin:pw@x]` reaches the `:122` message) and to the `URI` fallback at `:170`. Add a test in `RedactionTest` (or `ExampleConfigTest`) that `user:S3cret@nas.lab` is rejected and the message does not contain `S3cret`.

### WARNING

**W1. A non-200 body is not "discarded unread": it is drained to the end, with no time bound.**
`src/com/vcfcf/adapters/example/BoundedBody.java:47-50` (`BodySubscribers.replacing(null)`), claims at `BoundedBody.java:27-28`, `ExampleApiClient.java` class comment, CHANGELOG 0.1.0.2 ("non-200 bodies are discarded unread"), and `BoundedBodyTest.nonOkBodyDiscarded` (feeds `onNext` and never checks cancellation).
Authority: review dimension 7 (memory safety and resource hygiene); issue #12's intent (bound what a misbehaving target or proxy can cost the shared collector); dimension 11 (docs must state what the code does).
Failure scenario: `replacing()` requests every byte and throws it away, so memory is safe but time is not. Proven above: a 500 with a streaming body held `send()` for 20 seconds against a 2-second request timeout (the JDK timeout stops at the response headers). A target or proxy that streams an endless 5xx body pins the collector thread forever; the cycle never finishes and no resource changes status. 5xx is also in the framework's default retry set, so each attempt drains again.
Smallest fix: for a non-200 status return a subscriber that cancels the subscription in `onSubscribe` and completes with `null` (the `Capped` fail-fast shape already does the cancel). Correct the comment and CHANGELOG wording, and make the test assert the subscription is cancelled with zero bytes requested, like `declaredLengthOverCapFailsUnread` does.

**W2. Snapshot freshness silently depends on `needsRediscovery()` returning `true`, and nothing says so where a child would change it.**
`src/com/vcfcf/adapters/example/ExampleAdapter.java:327` (the only per-cycle `snapshots.beginCycle()` is inside `rediscover`) and `:302-305` (`needsRediscovery`); `CycleCache.java:20-25`.
Authority: vcfops-sdk-adapter skill, *Unreadable is NOT compliant* (a value the adapter did not read this cycle must not be published as a reading); review dimension 1.
Failure scenario: a child that copies the template and makes `needsRediscovery` conditional (for example, rediscover every tenth cycle to save calls, a reasonable-looking change) skips `beginCycle` on the other nine cycles. `collect` then serves the old snapshot, and `metric()` stamps it with `System.currentTimeMillis()`, so stale values chart as fresh readings and a dead target keeps looking healthy until the next rediscover. The `needsRediscovery` javadoc explains the discovery reason it must be true, not that the snapshot also depends on it, and `CycleCache`'s "maximum snapshot age" note is about a cycle that never ends, not a cycle that never begins.
Smallest fix: state the coupling at both sites (a sentence in the `needsRediscovery` javadoc and at the `beginCycle` call: "rediscover is also the top of the snapshot cycle; if you ever make needsRediscovery conditional, move beginCycle somewhere that runs every cycle"). Optional and stronger: have `CycleCache` refuse a snapshot older than one collection interval.

### NIT

**N1. `numericOrNull` accepts Java-only number forms that are not JSON numbers.** `src/com/vcfcf/adapters/example/ExampleValues.java:24` (`Double.parseDouble(raw.trim())`). A JSON string `"42d"`, `"1f"` or `"0x1p3"` is published as 42, 1 or 8. The UniFi child already guards this (`UniFiValues.number`, regex `[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?` before parsing); the template should teach the stricter version it is the parent of. Fix: add the same regex, and add `42d`, `1f`, `0x1p3` to `MetricPresenceTest.missingFieldSkipped`.

**N2. The docs say "exact value `true`" but the parse is case-insensitive.** `docs/installing.md:73` ("Only the exact value `true` disables certificate validation") and CHANGELOG 0.1.0.2 ("only `true` turns it off") versus `ExampleConfig.java:79` (`"true".equalsIgnoreCase(raw)`, javadoc at `:72-78` says "any letter case"), where `TRUE` turns validation off. The code matches UniFi and Synology, so fix the two doc lines to say "`true` (any letter case)".

**N3. The `rediscover` abort check's comment describes something it cannot do.** `ExampleAdapter.java:325-326` ("Stop/discard may land between cycles; honor it before any read"). `VcfCfAdapter.onCollect` runs `abortRequested.set(false)` as its first statement (framework `VcfCfAdapter.java:716`), so a stop or discard that lands between cycles is cleared before `rediscover` runs. The check only catches a discard in the moment between that reset and the call. Keep the check (#14 asked for it) and reword the comment, so a pak author does not rely on it as a between-cycles guard.

**N4. The absent-item comment says the framework leaves the resource without fresh data; the framework marks it DATA_RECEIVING.** `ExampleAdapter.java:426-429`. When `collect` returns normally with no samples, `onCollect` sets `RESOURCE_STATUS_DATA_RECEIVING` (framework `VcfCfAdapter.java`, after `collectRelationships`). A resource that vanished from the target therefore shows as collecting. Fix the comment in this PR (the function is touched). Whether absence should throw (ERROR) instead is a family-wide question (UniFi and Synology have the same shape, for example `UniFiAdapter.java:871`, `:990`); see registration candidates.

**N5. A configure that fails with anything other than `IllegalArgumentException` keeps the previous configuration's client.** `ExampleAdapter.java:142-145`. The framework discards the old `httpClient` before calling `configureAdapter`, but `this.api` is only replaced at the end. If `buildHttpClient` throws (for example a platform trust-store failure), `api` still points at an `ExampleApiClient` over a discarded client, and `configError` stays `null`. Reads then fail ERROR (no pass), but with a misleading cause. Fix: set `this.api = null` at the top of `configureAdapter`.

**N6. An all-digit host such as `999` passes validation.** `ExampleConfig.java:48` (`HOSTNAME`). Java resolves `999` as the IPv4 literal 0.0.3.231, so the target is not the one the class comment (`:21-26`) promises. Fix: reject a host whose last label is all digits unless it matched `IPV4`, and add `999` and `10.1` to `ExampleConfigTest.invalidHosts`.

**N7. Generated doc stamps: the template does the opposite of its children.** `docs/README.md:22` and `docs/inventory-tree.md:3` still say `0.1.0.1`, and `REFERENCE.md:3` says "for build 0.1.0.1" while its table was hand-edited for build 2. UniFi (build 15, `0.0.0.15`), Synology (build 31, `0.0.0.31`) and Compliance (build 95, `0.0.0.95`) all commit the dev-preview stamp `build-sdk` writes, and regenerate to the release stamp in a "regenerate docset" commit at release. The template reverts instead. The effect is that the template's docs name a build that is not the one in the repo, and every local `build-sdk` leaves the tree dirty for the next author to puzzle over. Fix: commit the stamps `build-sdk` generates (`0.0.0.2` in the two generated docs, and the matching REFERENCE.md line), as the children do.

## The hunt list, item by item

- **allowInsecure (#8):** `describe.xml:47` defaults to `false` (also in the packaged describe); parse is strict (`equalsIgnoreCase("true")`; blank, `yes`, `1`, `" true"` all validate, tested). The WARN is built by `insecureWarning()` and logged only in `configureAdapter` (`ExampleAdapter.java:156-159`), so once per configure, never per cycle; Test Connection does not log it. Upgrade note in CHANGELOG and `docs/installing.md`. Docs wording: N2.
- **DOWN mapping (#13):** `ExampleFailures.isUnreachable` walks the cause chain with an identity set (cycle safe, tested) and matches the six types. An HTTP 401/403 surfaces as a cause-less `IOException("... returned HTTP 401")` and stays ERROR; a DSM-style refusal (HTTP 200 with an error code in the body) would be a payload failure and stays ERROR; `SSLHandshakeException` stays ERROR (tested). The template has no login, so UniFi's `authStatus` pre-check is not needed here, and the class comment says where a child adds it. The CycleCache rethrows the original exception, so a cached failure classifies the same as a fresh one.
- **metricIfPresent (#10):** `metricIfPresent` is the only caller of `metric()`; no `asDouble()` remains in the adapter. A real `0` is published (tested); null, missing, `NaN`, `Infinity`, booleans and objects are skipped (tested). Gap: N1. One leftover sentinel by the template's own definition (`ExampleAdapter.java:66`, "0.0 / \"\" sentinel"): `prop(out, "Configuration|name", item.get("name").asString(""))` at `:436` publishes `""` for a missing name. Pre-existing and identical in the children; I list it here rather than as a finding because the brief scoped the hunt to 0.0, but it should be fixed in the same pass if the author is in that function anyway.
- **CycleCache (#9):** one build per cycle, served to rediscover and every collect (tested with 51 reads); a failure is remembered only until the next `beginCycle` (tested); `InterruptedException` is never remembered (tested); a `null` build is a failure, not an empty snapshot (tested). `beginCycle` also runs on every configure, valid or not, so a new configuration is never served the old one's snapshot. Nothing in it is a sentinel. Freshness coupling: W2.
- **Discard mid-cycle (#14):** `fetchSnapshot` copies the volatile `api` to a local and throws `InterruptedException("discarded")` when it is null and no config error is recorded. No NPE path found in `rediscover`, `collect`, `enumerateResources` or `collectExampleResource`. A read through a client the framework has just discarded fails with an exception, which marks ERROR on an instance that is going away anyway. Abort check present; comment: N3.
- **BoundedBody (#12):** 8 MB in one constant; over-cap fails with `IOException` and cancels, including the up-front `Content-Length` case with zero bytes requested (tested); non-JSON `Content-Type` rejected only when the header is present (`ExampleApiClient.java:56-60`), `+json` types accepted. Non-200 handling: W1. Observation only: the framework `RetryPolicy` retries every `IOException`, including the over-cap one, so an oversized body is read to the cap three times per cycle; that is framework behavior and not this branch's to fix.
- **Host and port (#16):** bracketed IPv6 accepted, malformed brackets rejected (the `URI` constructor catches what the loose regex lets through); scheme, path, `@`, `?`, `#`, `:`, whitespace rejected; port is an `int`, 1 to 65535, blank defaults to 443; URL built with `new URI(...)`. Credential echo: B1. Digit-only host: N6.
- **Swallowing a bad host or port at configure: right call for a template.** The alternative, letting the `IllegalArgumentException` escape `onConfigure`, hands the failure to platform behavior nobody has verified on 9.0.2 or 9.1, and a template should not teach an unverified path. What the author did is loud and deterministic: one ERROR with the reason on configure, every read fails with the same message, resources go ERROR (correctly not DOWN, since the operator has to fix the config, not the target), and Test Connection shows the reason because the tester builds its own config and the framework turns the exception into the dialog text. Nothing reads as a pass. Two limits worth knowing: a brand-new instance with a bad host has zero resources, so nothing turns red and the operator only sees the log or Test Connection; and the message must not carry the raw value (B1).
- **Password (#15):** field is `private final`; the only reader is `password()`, package-private, with one caller (`ExampleAdapter.java:176`); `toString()` prints host, port, username, allowInsecure and `password=***` (tested, plus a reflection test that the field is private). No other path reads it.
- **Docs (#17):** CHANGELOG corrects the `SDK_RUNTIME_TOKEN` claim to the `SDK_RUNTIME_SSH_KEY` deploy key; README says CI shallow-clones the sdk-runtime repo and uses no release asset; buildkit pinned to `sdk-buildkit-v1.0.11` with `sha256sum -c` (checksum file exists and matches the published asset, verified); jar storage reads "a private repo only ... Never upload the jar as a workflow artifact"; `installing.md` states the `false` default and the upgrade note. The template's own `build-pak-on-tag.yml` still uses the floating `sdk-buildkit-v1` (`:35`); that is CI2 in the separate PR, so not a finding here, but until it lands the README and the workflow disagree. Note that the `.sha256` comes from the same release as the tarball, so it proves integrity, not authenticity; pinning the hash in the README would be stronger, and that is a CI2 design choice.
- **Em-dashes:** none added.
- **Doc stamps:** N7.

## Other dimensions

- **Build hygiene (dimension 9):** `build_number` 1 to 2, CHANGELOG 0.1.0.2 entry, one commit per issue plus a build commit. The rewrite of `currentSnapshot`/`findItem` into `fetchSnapshot` plus a map is the requested #9 change, not a drive-by. Behavior preservation: duplicate ids were enumerated more than once before and collected first-match; now first-wins at index time, which is the same collected value with one registration instead of several.
- **Logging (dimension 6):** apart from B1, levels are right (configure INFO, insecure WARN, invalid config ERROR once). The per-resource WARN for an absent item is pre-existing and shared with the children.
- **Stitching (dimension 5), canonical loader (4), vim25 (2), alerts (13):** not applicable; the template has no foreign keys, no loader, no vim25 and no alerts.
- **Docs parity (dimension 11):** no cross-MP relationships. Beyond W1's wording, N2 and N7, the docs match the code.

## Registry check (`knowledge/context/defects.md`)

No open defect has `Affects: template`, and none closed either. Nothing to re-assert or propose for closure.

Registration candidate (orchestrator's call per RULE-012, not this branch's): **a resource that vanished from the target is marked DATA_RECEIVING** (N4). Template, UniFi and Synology all log a WARN and return normally, and the framework then reports the resource as collecting. That fits "absence is not a pass" poorly, and the fix belongs in one decision across the family rather than in the template alone.

## If shipped as-is

An operator who pastes a URL with a user name and password into the Host field gets that password written to the adapter log every collection cycle and shown in Test Connection, and every pak started from this template inherits the same leak; everything else in build 2 is an improvement over build 1.

---

## Round 2 (head `a7ac07c`, eight commits on `65d52aa`), 2026-10-16

**Verdict: APPROVE** (0 BLOCKING, 1 WARNING, 2 NIT). All ten round 1 findings are resolved. One new WARNING and one NIT come from the fixes themselves, and per the factory process both should be fixed before the PR opens. The third item (generator em-dash) is in factory code this branch does not touch, so it becomes a factory issue.

### Re-runs

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` (JDK 17) | 7 classes, all assertions passed (new cases for B1, W1, W2, N1, N6). |
| `validate-sdk` | OK. |
| `build-sdk` | `vcfcf_sdk_example_adapter.0.0.0.2.pak` built; the adapter repo stays clean afterwards (stamps now committed, so the build rewrites nothing). |
| `pak-compare` vs build 1 pak | PASS, 0 BLOCKING / 0 WARNING / 0 INFO. |
| W1 live probe | Same local server streaming a 500 body for 20 s: `send()` now returns status 500, body `null`, in 66 ms (7 ms on a second request over the same client). Round 1: 20,156 ms. |
| Em-dash scan | Commit messages: none. Added lines: one, see N-R2-2. |

### Round 1 findings

| Finding | Status | Evidence |
|---|---|---|
| B1 credential echo | Resolved | `brokenHostRule` names the rule for `@`, `://`, `/`, `?`, `#`, `:`, whitespace without the value; IPv6 failure no longer quotes; port is quoted only when it is 1 to 10 digits; `RedactionTest.rejectedValuesNeverEchoed` covers URL, user-info, bracketed, whitespace and port cases. Residual gap: W-R2-1. |
| W1 non-200 drain | Resolved | `BoundedBody.Unread` cancels on subscribe and completes `null`; test asserts cancelled, zero bytes requested, answered at once; live probe above. Comment and CHANGELOG corrected. |
| W2 snapshot coupling | Resolved | Coupling documented at `needsRediscovery` and at the `beginCycle` call; `CycleCache` gained a maximum age. Tuning of that age: N-R2-1. |
| N1 numeric forms | Resolved | `PLAIN_NUMBER` regex, same as `UniFiValues.number`; `42d`, `1f`, `0x1p3`, `1_000`, `12abc` tested as skipped. |
| N2 case-insensitive parse | Resolved by doc change, **acceptable** | See below. |
| N3 abort comment | Resolved | Comment now says it only catches a stop just after `onCollect` starts. |
| N4 absent-item comment | Resolved | Comment states the framework marks DATA_RECEIVING and says to throw if a pak wants ERROR. Family-wide registration candidate from round 1 stands. |
| N5 stale client | Resolved | `configureAdapter` clears `api`, `configError` and the snapshot first; a `RuntimeException` from `buildHttpClient` becomes a `configError` naming only the exception class. No path left where reads go through a discarded client. |
| N6 digit-only host | Resolved | Last label all digits rejected unless a full dotted IPv4; `999`, `10.1`, `nas.123` tested. |
| N7 doc stamps | Resolved | `docs/README.md`, `docs/inventory-tree.md`, `REFERENCE.md` carry `0.0.0.2`, matching the children's convention. |

**N2 judgment: acceptable.** Issue #8 itself quotes the existing `"true".equalsIgnoreCase(allowInsecure)` and asks to *keep* the parse strict, so the issue's author treated case-insensitive `true` as strict. The property that matters is fail-closed: blank, missing, `yes`, `1`, `on` and `" true"` all keep validation on (tested), and only a deliberate `true` in some casing turns it off. Matching UniFi (`UniFiConfig.java:31`) and Synology (`SynologyConfig.java:56`) is the right call for a parent template; diverging would make the next pak differ from its siblings for no security gain. The docs now say exactly what the code does.

**Extra change, `prop()` skips null: correct.** The only caller passes `item.get("name").asString()`, which is `null` exactly when the field is absent or JSON null, so a missing name is now a gap instead of an empty-string property. That matches idiom 6 (`ExampleAdapter.java:64-68`, no `""` sentinel). As with any property, Ops keeps the last published value when a later cycle skips it; that is normal property behavior, not a sentinel.

### New findings

**W-R2-1 (WARNING). One host rejection still quotes a value that failed the character check, and the class Javadoc says it never does.**
`src/com/vcfcf/adapters/example/ExampleConfig.java:153` (`"Host / IP Address '" + h + "' is not a valid hostname ..."`) against the claim at `:31` ("A value is quoted only after it has passed the character check (letters, digits, hyphens, dots ...)").
Authority: RULE-008 `knowledge/rules/no-secrets-on-disk.md` ("Scrub error paths"); the class's own contract.
Failure scenario: probed. `Hunter2!pw`, `p4ss$word` and `nas.lab%x` are all quoted in full. A value reaches `:153` after only `brokenHostRule`, which forbids `@ / ? # :` and whitespace, not `! $ %` and the rest, so an operator who types a password into Host by mistake gets it logged every cycle and shown in Test Connection, which is the B1 path with a different input. Lower likelihood than the URL form (credentials are entered in a separate dialog, and the Host value is already stored and shown as the instance identifier), which is why this is a WARNING, not BLOCKING.
Fix: drop the quote from the `:153` message (for example "Host / IP Address is not a valid hostname (letters, digits, hyphens and dots only)"), and add `Hunter2!pw` to `RedactionTest.rejectedValuesNeverEchoed`. The messages at `:146` and `:160` are safe, because they run only after the value has matched `IPV4` or `HOSTNAME`.

**N-R2-1 (NIT). The maximum age equals the interval, so the safety net misses the case it was added for, a single skipped cycle.**
`CycleCache.java:79` (`clock - builtAt >= maxAgeMs`, with `builtAt` set when the build finishes at `:91`/`:94`) and `ExampleAdapter.java:93`/`:102` (`maxAgeMs` = 5 minutes = the interval).
Scenario: cycle N starts at T and its read finishes at T+d. Cycle N+1 starts at T+300 s. If `beginCycle` was skipped (the conditional-`needsRediscovery` child from W2), the snapshot's age is 300 s minus d, under the limit, so cycle N+1 is served cycle N's data stamped as current. It only expires on the cycle after that, so such a child serves stale data on every other cycle. Also, an operator can change an instance's collection interval in Ops, so "MUST match `monitoringInterval`" (`ExampleAdapter.java:88-92`, `describe.xml` comment) does not hold after an edit. No effect on the template as shipped, because `needsRediscovery` always returns true.
Fix: use half the interval as the maximum age, so the previous cycle's snapshot has always expired by the next cycle, and say in the comment that an operator-edited interval is not tracked. Alternatively, keep the value and correct the `needsRediscovery` Javadoc to say the net catches only from the second skipped cycle. Add a test with build-finish offset d > 0 and age = interval minus d.

**N-R2-2 (NIT, factory issue, not this branch). The doc generator writes an em-dash into every pak's committed docs.**
`docs/inventory-tree.md:3` (added line `> Generated from describe.xml v0.0.0.2. Do not edit [EM DASH] regenerated on every build.`, em-dash shown here as [EM DASH]). The text comes from the factory doc generator under `src/vcfcf_managementpacks/`, and UniFi, Synology and Compliance carry the same line; hand-editing it here would be reverted by the next build. File a factory issue for `tooling` (then `framework-reviewer`) to drop the em-dash from the generator template. Do not block or edit this branch for it.

### Registry check (round 2)

Unchanged: no defect in `knowledge/context/defects.md` names `template`. The round 1 registration candidate (vanished resources marked DATA_RECEIVING, family-wide) still stands for the orchestrator.

### If shipped as-is (round 2)

Operators get certificate validation on by default, correct DOWN/ERROR states, no zero or empty-string sentinels and bounded HTTP reads. One edge remains: a password typed into the Host field by mistake would still appear in the log and in Test Connection.

## After round 2 (recorded 2026-10-19)

Eight commits landed on PR #21 after the round 2 approval at `a7ac07c` and
merged with it (merge `df34aea`): `83f1e48`, `80385df`, `17ce0c3`,
`125b034`, `83eb342` (never echo a rejected port), `28a32bc`, `347a5c3`,
`39a0552` (Test Connection validates ids like the collection cycle). They
came out of the template's own peer-review rounds, which this record does
not contain. No round here covers them.
