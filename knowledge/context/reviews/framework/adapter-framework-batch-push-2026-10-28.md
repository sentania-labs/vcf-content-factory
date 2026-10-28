# Framework review: batch Suite API pushes on the stitch facade (compliance#17), buildkit 1.0.24

- **Branch:** `suite-api-batch-push`, head 8ae1582 (on 44aff7d, fbfe095, ac11f65; base origin/main 0893525). Reviewed in a scratch clone with the pak clones, `reference/references` and the gitignored `adapter_runtime/` jars linked in.
- **Area:** `src/vcfcf_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/` (`SuiteApiStitchClient`, `SuiteApiStitcher`, new `SuiteApiBatchResult`), new `SuiteApiStitchBatchTest`, `buildkit.py` version; docs (release notes, tier2, skill, evidence doc, reference_docs, README); vendor specs `reference/docs/operations-api-8.18.json`, `internal-api-8.18.json`.
- **Reviewer:** framework-reviewer, 2026-10-28
- **Verdict: CHANGES REQUESTED** (1 BLOCKING, 6 WARNING, 1 NIT)

## Checks re-run

| Check | Result |
|---|---|
| Merge with origin/main | `git merge-tree`: clean. No open PR (#291, #293, #296) bumps `BUILDKIT_VERSION` |
| Framework build + compat pass, `build-framework.sh`, `VCFCF_SDK_COMPAT_REQUIRED=1` | rc 0. 9.0 (2.2), 8.18.7 (javac 17, `--release 11`), 9.1.1.0100 (javac 25.0.5, `--release 25`). Stamped 1.0.24 |
| Java stitch suites on 2.2 | Batch 104/104, Transport 81/81, Client 18/18, Relationship 165/165 |
| Batch + Transport at runtime on the 8.18.7 jar (JDK 17) and the 9.1.1.0100 jar (JDK 25.0.5) | 104/104 and 81/81 on both |
| pytest, CI flags (`-n auto --dist=loadgroup --override-ini="addopts=" -m ""`), pak clones linked | 3263 passed, 8 skipped, 0 failed |
| Seven-package validate chain | all rc 0 (managementpacks: 4 Tier 2 SDK projects valid) |
| `reference/` modifications or deletions | none (additions only) |
| Reviewer probes (scratch `BatchProbe`, same fake transport as the suite) | see findings; P1 to P8 below |

Probe results (250 resources unless noted, default caps):

| Probe | Observed |
|---|---|
| P1 property value with U+0001 / U+000C, statKey with U+0008 | body sent; Python `json.loads` rejects it: "Invalid control character" |
| P2 503 on every POST, `pushBatch` | 507 requests, 506 WARN lines; `fellBack=500` |
| P3 batch 401, then token acquire answers 500 | 254 `POST /api/auth/token/acquire` from one call; 0 per-id pushes on the wire; result `sent=250 batchesFailed=3 fellBack=250` |
| P4 every batch times out, `pushBatch` | 6 batch requests, each a 120 s read timeout (12 min); stats call still runs after properties all timed out |
| P5 1 good + NaN + null stat | `isClean()=true` |
| P6 batch 500, first per-id re-send times out (100 resources) | `fellBack=1 skipped=0`: 99 resources neither landed, re-sent nor counted |
| P7 interrupt during chunk 1's fallback (150 resources) | `sent=100 fellBack=1 skipped=50`: 99 of chunk 1 uncounted |
| P8 8 threads x 20 calls on one client, 300 resources each | 1 token acquisition, every result clean |

## Claims checked

| Claim | Verdict |
|---|---|
| Stats body `{"resource-stat-content":[{"id","stat-contents":[...]}]}`, properties `{"values":[{"resourceId","property-contents":{"property-content":[...]}}]}` | **Matches** the 9.0 (`operations-api.json`) and 9.1 schemas and examples, and the 8.18 `x-examples` (JSON and XML). 8.18 springfox schema says `list` / `properties`; the doc's JAXB-name inference is proven for stats (live test 2), not for properties (W5) |
| Never the `/adapterkinds/{kind}` variants | Proven: path constants are the plain bulk paths |
| `disableAnalyticsProcessing` can never be true | **Proven.** No query string on either path constant, no parameter on any public method, test asserts the URL. Spec default `false` on 8.18, 9.0, 9.1 |
| Chunk by count and UTF-8 bytes, oversized alone | **Correct.** `chunk()` accounts prefix, commas and `]}`; multibyte covered by the `é` test; lone surrogates encode to `?` in both the count and the write, so they agree |
| Single 401 retry, persistent 401 not re-sent | Correct for a 401 on the batch POST. Wrong when the token call itself fails (B1) |
| "Null keys, null values and non-finite stats dropped, so one bad entry cannot fail a batch" | **False** for control characters (W1) |
| "Nothing is retried on 5xx" (release notes) | **Contradicted** by the code and by the notes' own previous sentence (W2) |
| Timeout not re-sent | True per chunk; the remaining chunks still each wait 120 s (W3) |
| Thread safety | No new shared mutable state; token via the existing `tokenLock`; caller-map exceptions caught. P8 clean |
| Per-id bodies unchanged | Proven by `testPerIdBodiesUnchanged` and the transport suite |
| "Same on 8.18, 9.0 and 9.1" (release notes) | Overclaims the evidence (W5) |

## BLOCKING

### B1. A failure to get a token is treated as a failed batch: per-id fallback storm on the auth endpoint, and the result reports sends that never happened

`SuiteApiStitchClient.java` `postWithRetry` (`ensureToken()` and `reAcquireToken()` run inside the batch attempt) and the classification in `pushBatchOf` (`perId = err instanceof SuiteApiHttpException && !(err instanceof Suite401Exception)`).

`acquireToken` goes through `urlConnRequest`, so a non-401 answer from `POST /api/auth/token/acquire` (500, 503, 403) surfaces as a `SuiteApiHttpException`. The batch loop reads that as "the batch POST was answered non-2xx" and re-sends every resource of the chunk per id. Each per-id re-send calls `ensureToken`, the cache is empty, so each one POSTs a login. P3: one `pushStatsBatch` of 250 resources made **254 login POSTs** to a failing auth service, and `pushBatch` doubles that. The same happens with no 401 at all when the first `ensureToken` of the cycle hits a 5xx. That is the fallback storm the gate exists to catch, aimed at the login endpoint, where repeated attempts can count against the service account.

The result then misreports: P3 returns `sent=250 fellBack=250` with one batch request and **zero** per-id requests on the wire. `testClosedClient` pins the same pattern for a closed client: "nothing sent, no token" yet `sent=1 batchesFailed=1`, against `getSent()`'s own Javadoc ("put in a batch request that was sent"). An adapter that counts from the result (as the skill tells it to) is shown re-sends that never left the collector. Authority: `knowledge/context/api-surface/suite_api_batch_push.md` §What a batch API needs, item 5 ("no blind retry on 5xx ... beyond the per-id fallback"), and the reviewer doctrine's reports-green-while-broken class.

**Fix:** get the token before the chunk's POST, outside the batch attempt, and route a token failure (any status, or a 401 from re-acquire) to halt: stop the call, count every unsent resource as skipped, no per-id fallback. Count `sent` only for a chunk that reached `urlConnRequest`'s write, and `fellBack` only for a per-id request that was actually attempted. Add tests for: token acquire 500 at the start of a cycle; 401 then re-acquire 500; closed client reporting `sent=0`.

## WARNING

### W1. A control character in a key or value makes the whole batch invalid JSON

`SuiteApiStitchClient.java:1982` `jsonStr` escapes only `\\`, `"`, `\n`, `\r`, `\t`. Any other U+0000 to U+001F is written raw, which RFC 8259 §7 forbids. P1: a property value with U+0001/U+000C and a statKey with U+0008 produced a body a strict parser rejects. Jackson on the Suite API rejects unescaped control characters by default, so one such value 400s a batch of up to 100 resources; the per-id fallback then re-sends all of them, and the poisoned resource fails again, every cycle. The pre-existing per-id path had the same flaw for one resource; the batch path multiplies its cost and makes the stated contract false (tier2 row, evidence doc §What a batch API needs: "so they cannot turn a whole batch into a 400"). Compliance properties carry free-form vendor description text. **Fix:** escape every char below 0x20 as `\u00XX` in `jsonStr` (this fixes the per-id bodies too), and add a batch test with a control character.

### W2. A 5xx batch is re-sent per id, against a struggling server, and the release notes say it is not

`pushBatchOf` re-sends per id on any non-401 `SuiteApiHttpException`, 5xx included, and the per-id loop does not stop on a 5xx. P2: a server answering 503 got 507 requests and 506 WARN lines for 250 objects in one `pushBatch`, the same load as the per-object loop batching replaces, at the moment the server is least able to take it. `testFallbackOnFailure` asserts "no blind retry on 5xx" while expecting 5 per-id re-sends. `.github/release-notes-buildkit.md` says both "re-sends that batch's resources on the per-id path" and "nothing is retried on 5xx": a 5xx is a non-2xx. **Fix:** fall back per id only where the per-id path can isolate a bad entry (4xx other than 401 and 429, e.g. 400, 413, 422); on 5xx or 429 do not fall back, and stop the call (count the rest as skipped) or at least stop the chunk's fallback at its first 5xx. Make the release notes, Javadoc and tier2 row say exactly that.

### W3. After a timeout, every remaining chunk still waits the full 120 s

`pushBatchOf`: a failure with no HTTP status is logged and `continue`s to the next chunk; `pushBatch` then starts the stats call. P4: 6 batches, 6 x 120 s = 12 minutes of collect thread for 250 objects; ~40 minutes for 1,000 objects, many collect intervals. The per-id fallback already stops at its first no-status failure (Javadoc), so the batch loop is inconsistent with its own rule. **Fix:** after the first no-status failure, stop the call and count the remaining resources skipped; in `pushBatch`, skip the stats call when properties stopped that way. Test it.

### W4. The result undercounts lost data

- Dropped values do not show: P5, 2 of 3 values dropped (NaN, null), `isClean()` is `true`. The only trace is one WARN.
- Resources abandoned when a chunk's fallback stops are not counted: P6, 99 of 100 resources neither landed, re-sent nor skipped, `fellBack=1 skipped=0`. P7, on an interrupt mid-fallback the next chunk is counted skipped but the rest of the current chunk is not, contradicting `getSkipped()`'s Javadoc ("resources left when an interrupt or a closed client stopped the call").
- The outer `catch` returns partial counts with the unsent remainder uncounted.

The skill tells paks to "count from the returned `SuiteApiBatchResult` rather than grepping the log". **Fix:** add a `dropped` count (entries) and fold it into `isClean()`, and count every resource that was neither sent nor re-sent as skipped on every stop path.

### W5. Properties-batch landing is proven on no version, and 9.x has no live test; the release notes say "Same on 8.18, 9.0 and 9.1"

Evidence doc live test 1 used a same-value property, so 8.18 "accepted with 200, landing not observable", and the 8.18 springfox schema names that very field `properties`, not `property-contents`. Its §Open item 2: 9.0 and 9.1 untested for either batch. The doc's JAXB inference is strong (8.18 XML and JSON examples, and stats proven against the same kind of mismatch), but this is the one failure the doc says is silent: an unknown field or id gets a 200 and nothing lands, which the per-id fallback cannot catch. **Fix:** before any pak adopts (compliance's adoption build), prove landing with a changed value: properties batch on 8.18.7, both batches on 9.0 and 9.1.1 (the pak's next cycle restores the value). Until then the release notes and tier2 row should say "spec and vendor examples on all three lines; stats landing proven on 8.18.7" rather than "Same on 8.18, 9.0 and 9.1".

### W6. Every resource is serialized before the first request: peak memory is the whole cycle's payload

`pushBatchOf` builds `merged` (a copy of the caller's maps), `clean` (a second copy) and `BatchEntry.json` for every resource, then chunks. The evidence doc measures ~145 KB of properties JSON per host on 9.0.2: 500 hosts is about 72 MB of JSON text (about twice that as Java `String`s), held at once alongside the caller's maps, in the shared collector JVM. The per-id path held one object's body at a time. **Fix:** pack and send as you serialize (serialize an entry; if it does not fit, send the current chunk, then start a new one), so peak is one chunk; drop `clean` once its JSON exists (it is needed only for a fallback, which can re-serialize from `merged`).

## NIT

### N1. No CI job runs the Java stitch suites (pre-existing, outside this branch)

The 104 new checks, and the Transport, Client and Relationship suites, run only by hand; no pytest wrapper or workflow invokes them (`tests/managementpacks/test_sdk_compat_target.py` only names the directory). Follow-up issue, not this branch: wrap the stitch `main()`s in a pytest test behind the existing javac skip.

## Vendor specs and RULE-016

Consistent. `reference/docs/operations-api-8.18.json` and `internal-api-8.18.json` are additions only (no modified or deleted file under `reference/`), committed verbatim as served (single-line springfox JSON), named after the existing `-9.1` pair, and the correction about springfox field names lives in `knowledge/context/reference_docs.md` and the evidence doc, not in the specs (RULE-016, RULE-010). They are what makes the 8.18 wire claims reproducible from a clone (RULE-015). Size (2.2 MB) is in line with the 9.1 pair (4.6 MB). Note only: the 8.18 Swagger 2.0 `host` field carries the lab FQDN `vcf-lab-operations-devel-8.int.sentania.net`; verbatim requires keeping it, and that FQDN already appears in 80 tracked files.

## Docs

- Release notes: contradiction on 5xx (W2) and the version-parity overclaim (W5). Otherwise accurate, opt-in stated clearly.
- tier2 row and evidence doc §What a batch API needs: "cannot turn a whole batch into a 400" is false (W1). Rest accurate.
- Skill text: accurate, and the "2xx is not landed" warning is in the right place. It tells paks to count from the result, which is why W4 and B1's miscounts matter.
- Stale-zip discipline: not triggered (no packaging templates, builders, `assembly.py` or `render.py` touched). `BUILDKIT_VERSION` bumped to 1.0.24; the kit copies `adapter_framework/src` by `rglob`, so `SuiteApiBatchResult.java` ships.

## If shipped as-is

A pak that adopts `pushBatch` hits the Suite API login endpoint once per object every cycle whenever token acquisition returns a 5xx, while its result reports re-sends that never left the collector. One control character in a description 400s a whole batch every cycle. A hung server holds the collect thread for 2 minutes per chunk. Until the live checks in W5 are run, nobody knows that properties land on any version.
