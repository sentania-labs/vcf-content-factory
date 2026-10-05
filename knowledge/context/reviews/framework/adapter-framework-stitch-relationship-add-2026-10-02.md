# Framework review: Suite API relationship add + singleton lookup (2026-10-02)

- **Reviewer:** framework-reviewer
- **Branch:** `feat/compliance-environment-computed-metrics` (base `06c8550` = `origin/main`), uncommitted diff
- **Area:** `src/vcfcf_managementpacks/adapter_framework/` (stitch package)
- **Files:** `SuiteApiStitchClient.java`, `SuiteApiStitcher.java`, `RelationshipBuilder.java` (Javadoc only), new `test/.../SuiteApiStitchRelationshipTest.java`; docs `knowledge/context/tier2_architecture.md`, `knowledge/context/framework_v2_migration.md`, `.claude/skills/vcfops-sdk-adapter/SKILL.md`
- **Verdict:** APPROVE (0 BLOCKING / 4 WARNING / 4 NIT). Per CLAUDE.md delegation rule 9, every WARNING and NIT below is fixed in one re-brief before the PR opens.

## Bottom line

The wire call is right and the never-throw contract holds on every path I could drive. The weak spots are a lookup that ignores pagination (so the "never guesses" promise rests on an unverified server-side assumption), one doc sentence that says `get` swallows failures when it throws, a sample that caches a parent id forever, and no doc line saying these edges are never removed.

## Checks re-run (independently)

| Check | Result |
|---|---|
| Framework compile, `-source 11 -target 11` against SDK jar only (as `build-framework.sh`) | clean |
| `VcfCfAdapterTest` | 11/11 |
| `CertificateReviewTest` | 86/86 |
| `SuiteApiStitchClientTest` | 18/18 |
| `AmbientCredentialTest` | 28/28 (3 environmental SKIPs, pre-existing) |
| `RelationshipBuilderTest` | 8/8 |
| `SuiteApiStitchRelationshipTest`, SDK classpath only | 17/17, transport group SKIPPED |
| `SuiteApiStitchRelationshipTest`, plus `adapter_runtime/lib/*` (log4j-api) | 64/64 |
| Reviewer probe (`ReviewProbe`, scratch only, reuses the test harness) | see findings; 12 adversarial cases |
| pytest, full | 2631 passed, 8 skipped, 1 failed: `content/migrator/tests/test_preview.py` (`ModuleNotFoundError: vcfcf_migrator`; `content/migrator/` is a gitignored sibling repo, no Python in this diff; unrelated) |
| Validate chain (7 packages) | all rc=0; managementpacks "6 Tier 2 SDK adapter project(s) valid" |
| `adapter_runtime/vcfcf-adapter-base.jar` | rebuilt, `javap` shows `addChild`, `addChildren`, `findSingletonResourceId` |
| Render regression / pak-compare | n/a (no renderer, builder, or template touched) |

## Wire conformance (verified, not taken on faith)

Against `reference/docs/operations-api.json` (9.0) and `reference/docs/operations-api-9.1.json`, both identical for this operation:

- `POST /api/resources/{id}/relationships/{relationshipType}`, `operationId: addRelationship`, `relationshipType` enum `["parents","children"]`. Code emits `/api/resources/<parent>/relationships/children` with POST. Matches.
- Body `$ref uuid-values`: `{"uuids":[...]}`, `required: ["uuids"]`, `uniqueItems: true`. Code emits exactly that via `jsonStr`. Matches.
- Responses `204`, `404`. Code treats any 2xx as accepted, anything else as WARN + `false`. Matches.
- `PUT` on the same path is `setRelationship`, description "exposes replace semantics". No PUT anywhere in the diff; the test asserts no public `set*`/`replace*`/`*put*` method on either class. Confirmed by probe: no PUT ever issued.
- `GET /api/resources`: `adapterKind`, `resourceKind` are array query params; `page` default 0, **`pageSize` default 1000**. See W1.

## Brief's attack list, item by item

| Probe | Observed | Status |
|---|---|---|
| Verb/path/body | POST, `.../relationships/children`, `{"uuids":[...]}` | OK |
| Token leak on error paths | 401 message carries URL + principal, non-2xx carries URL + status; no token, no password. `acquireToken` body never logged | OK |
| Ids into path/body | Parent and children gated by anchored `matches()` on 8-4-4-4-12 hex, trimmed; `PARENT + "/../x"` rejected; body through `jsonStr` | OK |
| 401 retry | One re-acquire, one retry; perpetual 401 stops at 2 attempts; 401 on token acquire itself returns `false` after 1 request | OK |
| Interrupt | Pre-interrupted thread: `addChild` returns `false`, 0 requests, interrupt flag still set; lookup returns `null`, flag still set | OK |
| Thread safety across instances | No new mutable state; `UUID_PATTERN` static immutable, matcher per call; token per client instance under existing `tokenLock` | OK |
| Empty / all rejected | Empty, null, or all-invalid collection: `false`, zero HTTP requests | OK |
| Kind encoding | `VMwareAdapter Instance` to `VMwareAdapter%20Instance`; `A&b=c` to `A%26b%3Dc`; `x+y/z?#%` to `x%2By%2Fz%3F%23%25` | OK |
| Pagination | Page with one match and `totalCount: 1001` returns that id | **W1** |
| Existing callers | Additive public methods only; `RelationshipBuilder` change is Javadoc; no existing method body changed | OK |

## Findings

### WARNING

**W1. `SuiteApiStitchClient.java:668-692` (lookup ignores paging).** Authority: `operations-api.json` / `operations-api-9.1.json` `GET /api/resources`, `pageSize` default 1000; brief contract "return nothing on more than one match". The query sends no `pageSize` and never reads `pageInfo.totalCount`. Probe: a response whose page holds one exact match but reports `totalCount: 1001` returns that id. In normal use, server-side kind filtering means page 1 is all matches, so more than 1000 resources would already show as ambiguous. But "never guesses" then depends on an unverified server behaviour (exact, case-sensitive kind filtering) instead of on the code. **Fix:** read `pageInfo.totalCount` and return `null` with a WARN when it is greater than the number of `resourceList` entries on the page (or when it is greater than 1). Add a test using the existing `resources()` fixture with an inflated `totalCount`.

**W2. `.claude/skills/vcfops-sdk-adapter/SKILL.md:114` (doc says `get` never throws).** Authority: the code. `SuiteApiStitcher.get` is declared `throws IOException, InterruptedException` and does throw. The skill text lists `get` in the surface and then says "Every call logs and swallows failures; none throws into the collect cycle." An author who believes that will let a Suite API outage throw out of `collect()`. **Fix:** say the push/add/lookup calls swallow failures and that `get` throws, so the caller must catch.

**W3. `knowledge/context/tier2_architecture.md:627` and `:659`, `framework_v2_migration.md:499` (samples and Javadoc disagree on caching).** Authority: the client Javadoc for `findSingletonResourceId`: "cache a non-null result ... and only look up again after a later call that uses it fails." The tier2 sample does `if (worldId == null) worldId = ...` and never clears it, and the prose says "Cache a non-null result for the adapter instance's life." If the singleton is deleted and recreated (pak reinstall, admin delete, resource aged out), every later `addChild` gets a 404, returns `false`, logs a WARN, and the link is never re-established until the adapter restarts. The migration-doc one-liner goes the other way: a GET on every cycle. **Fix:** make the samples match the Javadoc, e.g. `if (worldId != null && !stitcher.addChild(worldId, child)) worldId = null;`, and state the re-lookup rule in the tier2 prose. Re-looking up after any `false` is acceptable, since a transient failure only costs one extra GET.

**W4. Docs and Javadoc (add-only, nothing removes the edge).** Authority: dimension 8 (a silent capability gap is a finding); spec `deleteRelationship` exists and is not wrapped. Nothing in the framework retracts an edge added this way, and no doc says so. In the intended first use (ComplianceWorld summing its VMwareAdapter Instance children through `ComputedMetrics`), a vCenter removed from a compliance instance's scope stays a child of the World. If that vCenter's stale `Rollup|All` keys still hold values, they keep feeding the environment totals. Nothing fails loudly. **Fix:** add one sentence to the `addChildren` Javadoc and to the tier2 "POST adds, PUT replaces" section: edges added here persist until removed through `DELETE /api/resources/{id}/relationships/children/{childId}`, which the framework does not wrap. A pak whose scope can shrink owns that cleanup, or it is recorded as a known limitation in the design. Adding a remove method is a scope decision for the orchestrator, not required here.

### NIT

**N1. `SuiteApiStitchClient.java:597` (input iterated outside the try).** The caller's collection is iterated before the `try`, so a `ConcurrentModificationException` from a collection another thread is mutating would escape into collect, against the "never throws" contract. **Fix:** move validation and dedupe inside the outer `try`.

**N2. `SuiteApiStitchClient.java:599` (dedupe and self-edge).** Dedupe is case-sensitive: probe body `["c87c...","C87C..."]` sends the same UUID twice. `addChild(P, P)` is sent; the spec says cycle-forming ids are skipped, so this is harmless but wasted. **Fix:** lowercase after trim; skip children equal to the parent with a WARN.

**N3. `SuiteApiStitchClient.java:672` and `:993` (lookup inputs and output).** The blank check trims but encode and compare use the untrimmed kinds, so `" MyWorld"` never matches. The returned `identifier` is not checked with `isUuid`, despite the "@return the single matching resource UUID" contract (probe returned `"not a uuid"`). A case mismatch logs "not created yet?", which misdiagnoses. **Fix:** trim kinds once; drop non-UUID identifiers; word the zero-match WARN as "no exact match (wrong kind key or not created yet)".

**N4. `SuiteApiStitchClient.java:601` (raw input in logs).** Rejected ids are logged raw, so a value with CR/LF can forge log lines. **Fix:** log a truncated, control-character-stripped form.

## Dimensions walked

1. Global/pak-specific leak (`00d3382`): n/a to the content-import path. Additive methods; no existing default, path, or behaviour changed. Clean.
2. Key/label collisions (`6c59f6b`): no key derivation. Clean.
3. Wire conformance: verified against both specs (above). Clean.
4. Loader/validator: untouched; validate chain green.
5. Render regression: n/a.
6. Builder/pak structure: n/a. The buildkit jar changes. `BUILDKIT_VERSION = "1.0.11"` in `src/vcfcf_managementpacks/buildkit.py`; the latest published release is `sdk-buildkit v1.0.10`, and no `sdk-buildkit-v1.0.11` tag exists. The changelog's "ships in 1.0.11 if it merges before the tag" claim holds today.
7. Corpus regression: validate chain green; pytest has one unrelated environmental failure (above).
8. Silent capability change: W4.
9. Stale-zip / template-version: none of the listed paths touched; `CURRENT_TEMPLATE_VERSION` n/a. Adapter paks pick this up only by adopting the new buildkit.
10. Test coverage: strong. Pure helpers plus 13 transport scenarios through a scripted `HttpURLConnection`. Gap: no paging case (W1). Context, not a finding on this branch: no CI job runs the Java framework tests at all, and the transport group silently SKIPs without log4j-api. That was already true and is outside this diff.

## Docs vs code

- tier2 spec facts (async 204, cycles skipped, 404 only when all ids invalid, 9.0/9.1 identical): match the spec text.
- "No PUT/replace variant exposed": true, and enforced by a test.
- SKILL.md "none throws": false for `get` (W2).
- Caching guidance: inconsistent across three places (W3).
- `RelationshipBuilder` cross-reference and the "do not mix routes on one parent, unverified" hedge: accurate. It is consistent with the superseded lesson `knowledge/lessons/setrelationships-foreign-adapter-scoped.md`, which proved per-reporting-adapter scoping only on 9.0.2.

## If shipped as-is

The compliance pak's World link works and never throws. Without W3's fix, a recreated World silently stops collecting links until restart. Without W4's note, a de-scoped vCenter keeps counting in the environment totals with no error.

## Second pass (2026-10-02, post-fix diff)

- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 2 NIT). All eight first-pass findings are closed in code, tests and docs, verified by reading the diff and by re-running, not from the result block. The fixes introduced no regression I could drive. Two small NITs remain; per CLAUDE.md delegation rule 9 they go in the same re-brief before the PR opens.

### Checks re-run (independently, fresh compile into scratch)

| Check | Result |
|---|---|
| Framework compile, `-source 11 -target 11`, SDK jar only | clean |
| `VcfCfAdapterTest` / `CertificateReviewTest` / `RelationshipBuilderTest` / `SuiteApiStitchClientTest` | 11/11, 86/86, 8/8, 18/18 |
| `AmbientCredentialTest` | 28/28 (same 3 environmental SKIPs) |
| `SuiteApiStitchRelationshipTest`, SDK classpath only | 30/30, transport group SKIPPED |
| `SuiteApiStitchRelationshipTest`, plus `adapter_runtime/lib/*` | 104/104 (was 64/64) |
| Reviewer probe `Probe2` (scratch only, reuses the test harness) | 19 adversarial cases, results below |
| pytest, full | 2631 passed, 8 skipped, 1 failed: the same `content/migrator/tests/test_preview.py` collection error as the first pass (gitignored sibling repo, no Python in this diff) |
| Validate chain (7 packages) | all rc=0; managementpacks "6 Tier 2 SDK adapter project(s) valid" |
| `adapter_runtime/vcfcf-adapter-base.jar` (gitignored) | newer than the source, `javap` shows `normalizeUuid` and `loggable`, so local pak builds see the fixed code |
| Em-dashes in added lines; `git diff --check` | none; clean |

### First-pass findings, closure verified

| Finding | Closed by | Evidence |
|---|---|---|
| W1 paging | `findSingletonResourceId` reads `pageInfo.totalCount`, returns `null` + WARN when it exceeds `resourceList` size | test `testFindSingletonPartialPageReturnsNothing` (1 of 1001 gives null; total equal to page gives the id; no pageInfo gives the id); probe: total 2 with one entry gives null, total `"1001"` as a string gives null |
| W2 `get` throws | SKILL.md now says push/relationship/lookup swallow, `get` throws `IOException` / `InterruptedException`, catch at call site | diff read; matches `SuiteApiStitcher.get` signature |
| W3 caching | tier2 sample and migration sample both `if (worldId != null && !stitcher.addChild(...)) worldId = null;`; tier2 prose, client Javadoc and facade Javadoc all say clear on `false` | three places now agree; the compliance caller (`ComplianceDecisions.linkWorld`) follows the same rule |
| W4 add-only | "Known limitation: nothing removes these edges" in `addChildren` Javadoc, facade Javadoc, tier2 section, migration doc, SKILL.md, changelog row; names `deleteRelationship` and its path | diff read; the compliance adapter Javadoc and design record it as a known limitation |
| N1 iteration outside try | collection read inside the outer `try` | test `testAddChildrenConcurrentModificationDoesNotThrow` (hostile iterator, returns false, WARN, zero requests) |
| N2 case dedupe, self-edge | `normalizeUuid` (trim + `Locale.ROOT` lowercase) before the `LinkedHashSet`; child equal to parent skipped with WARN | tests `testAddChildrenCaseInsensitiveDedupe`, `testAddChildSelfEdgeSkipped`; probe: uppercase parent and child go out lowercase in both path and body |
| N3 trim, non-UUID id, WARN wording | kinds trimmed once and used for query and compare; `parseResourceIds` drops non-UUID identifiers and lowercases; zero-match WARN names both causes | tests `testFindSingletonTrimsKinds`, `testFindSingletonDropsNonUuidIdentifier`; probe: `" <UPPER-UUID> "` identifier comes back trimmed and lowercase |
| N4 raw input in logs | every caller-supplied value logged through `loggable()` (ISO controls to `?`, 80-char cap with `...`) | test `testLoggable`, `testAddChildControlCharacterIdSendsNothing` |

### Attacks on what the fixes introduced

| Probe | Observed | Status |
|---|---|---|
| Lowercased return vs a mixed-case id from `/api/resources` | `findSingletonResourceId` is the only new returner and has one caller (compliance), which passes the id straight back into `addChild` and never compares it. No pre-existing framework method changed its return. Every resource `identifier` captured in `knowledge/`, `reference/` and `content/sdk-adapters/` (15 distinct) is already lowercase, so a lowercase id equals what `/api/resources` returns. | OK |
| `totalCount` 0, empty list | null, "no exact match" WARN | OK |
| `totalCount` 0 with one match (server inconsistency) | returns the id (`0 > 1` is false) | OK, a server that says 0 and sends 1 is not a paging risk |
| `pageInfo` absent, `null`, a string, or `totalCount` absent | returns the single match, no WARN | See N6 (spec marks `totalCount` optional; behaviour is intended and tested, the Javadoc is silent on it) |
| `totalCount` non-numeric (`"abc"`) or negative | treated as 0 / negative, check passes, returns the match | See N6 |
| `totalCount` 2 as `2.0`, two entries, one exact match | returns the id | OK |
| `totalCount` 5, no `resourceList` key | null, partial-page WARN | OK, fails closed |
| Empty 200 body; top-level `[]` | null, WARN, no throw | OK |
| Pre-interrupted thread, lookup and add | null / false, zero requests, interrupt flag preserved | OK |
| Truncation on a surrogate pair (79 ASCII then an emoji) | output char 80 is a lone high surrogate, then `...` | N5 |
| `loggable` on U+0085 / U+2028 / U+202E | U+0085 replaced (ISO control); U+2028 and U+202E pass through | N5 |
| Fixture change `world-1` to real UUIDs | Every assertion label from the first-pass test class (extracted from its compiled constants) is still present in the new source; none removed or loosened. The old `{"identifier":"id-4"}` row (no `resourceKey`) became a valid-UUID row with no `resourceKey`, so that case now tests the `resourceKey` filter alone instead of being rejected for its id: stronger. Real UUIDs were required, because the lookup now drops non-UUID identifiers; non-UUID rows moved into explicit tests. | OK |
| `resources()` fixture now carries `pageInfo.totalCount = entries.length` | zero-match test therefore runs with `totalCount 0`, covering that edge | OK |

### Findings

#### NIT

**N5. `SuiteApiStitchClient.java` `loggable()` (surrogate split, line-separator passthrough).** Authority: the method's own Javadoc ("so a value cannot forge a log line") and `String` UTF-16 semantics. The loop stops at 80 chars, so when char 80 is the high half of a pair the output ends in a lone surrogate (probe: `isHighSurrogate=true` at index 79). Log4j writes that as `?`, so this is cosmetic. Separately, U+2028 / U+2029 and bidi controls such as U+202E are not ISO controls and pass through. They cannot break a newline-delimited log file but can split or visually reorder a line in some viewers. Only rejected (non-UUID) values reach `loggable`, so the blast radius is one WARN line. **Fix:** if the last appended char is a high surrogate, drop it before adding `...`; also replace chars whose `Character.getType` is `LINE_SEPARATOR`, `PARAGRAPH_SEPARATOR` or `FORMAT`; add both cases to `testLoggable`.

**N6. `SuiteApiStitchClient.java` `findSingletonResourceId` Javadoc (absent or unreadable `totalCount` is trusted).** Authority: `operations-api.json` / `operations-api-9.1.json` `page-info` schema, `totalCount` not in `required`. When `pageInfo` or `totalCount` is missing, or `totalCount` is non-numeric (`SimpleJson.asLong` gives 0) or negative, the partial-page guard is skipped and one visible match is returned. That is reasonable (the server filters by kind and the default `pageSize` is 1000) and a test pins it ("no pageInfo, one match is returned"). But the Javadoc's "Incomplete page" bullet and the tier2 prose describe only the larger-than-page case, so a reader takes "never guesses" to cover a response with no count. **Fix:** one sentence in the Javadoc bullet and the tier2 paragraph: when the response carries no usable `totalCount`, the page is trusted as complete (server-side kind filter, default `pageSize` 1000). No code change needed.

### Dimensions (delta from first pass)

1 and 2 (`00d3382`, `6c59f6b` patterns): still n/a; additive methods, no default or key derivation touched. 3: wire unchanged from first pass (POST, `{"uuids":[...]}`, lowercase UUID path segment, accepted per the canonical id form). 4, 5, 6: n/a; validate chain green. 7: suites and validate green, pytest failure unrelated and pre-existing. 8: W4 now documented loudly everywhere. 9: no listed packaging path touched; `CURRENT_TEMPLATE_VERSION` n/a. 10: coverage grew from 64 to 104 assertions, one test per closed finding; the residual "no CI runs the Java framework tests" context from the first pass is unchanged and outside this diff.

### If shipped as-is

The compliance pak's World link behaves as designed: it finds the World only on an unambiguous, complete page, never throws, and re-looks it up after a failed add. An operator would at worst see one oddly rendered WARN line for a garbage id (N5), and a future maintainer could misread how the lookup treats a response with no count (N6).

## Third pass (2026-10-02, after rounds A and B)

- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 3 NIT). Round A closes N5 and N6 and replaces the clear-on-false caching advice with "look up every cycle, `true` means accepted, not linked" consistently in every place it appears. Round B's `logFailure` behaves as described on every path I could drive: the interrupt flag survives, nothing throws for any realistic input, and a non-2xx response body never reaches the log. Three small NITs remain, all in code this branch adds, so per CLAUDE.md delegation rule 9 they go into one re-brief before the PR.

### Checks re-run (independently, fresh compile into scratch)

| Check | Result |
|---|---|
| Framework compile, `-source 11 -target 11`, SDK jars only | clean |
| `VcfCfAdapterTest` / `CertificateReviewTest` / `RelationshipBuilderTest` / `SuiteApiStitchClientTest` / `AmbientCredentialTest` | 11/11, 86/86, 8/8, 18/18, 28/28 |
| `SuiteApiStitchRelationshipTest`, SDK classpath only | 44/44, transport group SKIPPED |
| `SuiteApiStitchRelationshipTest`, plus `adapter_runtime/lib/*` | 130/130 (was 104/104) |
| Reviewer probe `Probe3` (scratch only, reuses the test harness) | 10 adversarial cases, results below |
| pytest, full | 2631 passed, 8 skipped, 1 failed: the same `content/migrator/tests/test_preview.py` failure as both earlier passes (gitignored sibling repo, no Python in this diff) |
| Validate chain (7 packages) | all rc=0; managementpacks "6 Tier 2 SDK adapter project(s) valid" |
| `adapter_runtime/vcfcf-adapter-base.jar` | built 28 s after the last source edit; `javap` shows `logFailure`, `isExpectedFailure`, `failureSummary`, `unsafeForLog` |
| `pushStats` / `pushProperties` | outside every diff hunk, so unchanged as claimed; issue #192 is open and names exactly that gap. Deferral is legitimate under rule 9: the branch does not touch those methods. |
| Em-dashes in added lines; `git diff --check` | none; clean |

### Round A, closure verified

| Item | Evidence |
|---|---|
| N5 surrogate split | `loggable` drops a trailing high surrogate before `...`; `testLoggable` asserts the exact cut and that no lone surrogate remains |
| N5 separators / format chars | `unsafeForLog` adds `LINE_SEPARATOR`, `PARAGRAPH_SEPARATOR`, `FORMAT`; `testLoggable` covers U+2028, U+2029, U+202E, U+200B |
| N6 no usable `totalCount` | stated in the client Javadoc bullet, the facade Javadoc, tier2 prose and the tier2 changelog row; code unchanged (`isNull` gives -1, non-numeric gives 0, neither exceeds the page) |
| Per-cycle lookup rule | Same rule, same reason (async add, a 2xx to a deleted id is dropped later) in: client class Javadoc sample, `findSingletonResourceId` Javadoc, facade Javadoc, tier2 sample + prose + changelog, migration doc sample + "`worldId` is a local, not a field" paragraph, SKILL.md. No remaining text recommends `worldId = null` on `false`; tier2 and the client Javadoc mention clear-on-false only as the rejected alternative. All samples log "requested (accepted by Suite API)", not "linked". The one real caller (`ComplianceDecisions.linkWorld`, in the gitignored compliance repo) calls the lookup supplier each cycle and caches nothing. |

### Round B, attacks

| Probe | Observed | Status |
|---|---|---|
| Interrupt flag, `addChild` on a pre-interrupted thread | `false`, flag still set after return, 1 WARN, one-line branch, 0 requests | OK |
| Interrupt flag, lookup on a pre-interrupted thread | `null`, flag still set, 1 WARN, one-line branch | OK |
| Interrupt restored on every path | both catch blocks call `Thread.currentThread().interrupt()` before `logFailure`; the only `InterruptedException` source is the pre-check in `urlConnRequest`; nothing wraps one into another type | OK |
| Does "expected" hide a shutdown? | No. The WARN line still names `InterruptedException` with "thread interrupted before POST <url>", the flag reaches the caller, and the request is never sent. Only the stack trace is demoted, and it carries nothing a shutdown diagnosis needs. | OK |
| Non-2xx with a hostile body (CR/LF, forged log line, 20 KB) | message is `Suite API <METHOD> <url> HTTP <status>` only; the transport never reads the error stream. URL parts are config, a validated UUID, or URL-encoded kinds. Token-acquire 403 likewise carries no body. | OK, no server text |
| Null message | `failureSummary` gives `IOException: (no message)`; 1 WARN, no throw | OK |
| Null exception | not reachable: both callers pass the caught `Exception` | OK |
| Logger throwing | same exposure as every other log call in the class (SDK `Logger`); not new | OK |
| Path that logs nothing on failure | only `null` / empty child collection, which the Javadoc documents as a no-op; every invalid id, lookup outcome and caught failure logs | OK |
| 200 body with a malformed `\u` escape (`"\u\r\n\r\n"`) | `SimpleJson` throws `NumberFormatException: For input string: "\r\n\r\n" under radix 16`; the lookup takes the stack-trace branch and the CR/LF goes into the WARN line raw | N7 |
| 200 body with a 100 000-digit number | `failureSummary` is 100 043 chars, logged raw at WARN | N7 |
| 200 HTML body | `NumberFormatException`, null, 1 WARN, stack-trace branch, matching the Javadoc's "a malformed response included" | OK |
| Caller collection whose iterator throws an exception whose `getMessage()` itself throws | escapes `addChildren` | Accepted, not a finding: the throw is in the caller's own exception object, and the pre-round-B code had the same exposure through `e.getMessage()` |

### Findings

#### NIT

**N7. `SuiteApiStitchClient.java` `failureSummary` (server text unsanitized in the WARN line).** Authority: the class's own `loggable` contract ("a value cannot forge, split or visually reorder a log line") and the brief's own question. A non-2xx body cannot reach the log (probe above). But a malformed **200** body can, through the parser's exception message: `SimpleJson`'s `\u` handler passes four raw body characters to `Integer.parseInt`, and a digit run goes to `Long.parseLong`, and `NumberFormatException` echoes its input. That message reaches the WARN line through `failureSummary` with no sanitizing and no cap. Blast radius is small: the source is the platform's own Suite API, and only a broken server or a man-in-the-middle on the trust-all explicit-host path could send it. Note that the attached throwable still prints the raw message in the trace; the summary line is the part this class controls. **Fix:** pass the message through a sanitizing cap (reuse `unsafeForLog`; a cap around 200 characters, larger than `LOGGABLE_MAX`, keeps URLs readable) inside `failureSummary`, and add a `testFailureClassification` case with CR/LF and an over-long message.

**N8. `SuiteApiStitchRelationshipTest.java` (no committed test for interrupt handling through `logFailure`).** Authority: review dimension 10. Round B reclassified `InterruptedException` and moved both catch blocks onto a new helper, but the suite has no test that drives an interrupt through `addChild` or `findSingletonResourceId`. `isExpectedFailure(new InterruptedException())` is tested in isolation only. My probe proves the flag is restored today; nothing stops a later edit from dropping the `interrupt()` call. **Fix:** two transport tests: interrupt the thread, call each method, assert `false` / `null`, zero requests, one WARN, the one-line branch, and `Thread.interrupted()` true after return (which also clears the flag for the next test).

**N9. `SuiteApiStitchClient.java:585` (Javadoc line 126 chars).** Cosmetic: the round B sentence was spliced onto an existing line, so it runs past the file's wrap width (the only line over 110 in the file). **Fix:** rewrap the paragraph.

### Dimensions (delta from second pass)

1 and 2 (`00d3382`, `6c59f6b` patterns): n/a, no default or key derivation touched. 3: wire unchanged. 4, 5, 6: n/a; validate chain green. 7: Java suites, pytest and validate green apart from the pre-existing unrelated migrator failure. 8: no silent downgrade; the demotion of stack traces to DEBUG is loud (documented in Javadoc and tier2) and keeps the class and message at WARN. 9: no listed packaging path touched; `CURRENT_TEMPLATE_VERSION` n/a. 10: 104 to 130 assertions; gap in N8.

### If shipped as-is

A persistent failure (missing permission, World gone, Suite API down) writes one readable WARN line per cycle instead of a stack trace, and the collector still shuts down cleanly on interrupt. The residue: a broken or spoofed Suite API that returns malformed JSON could put a stray line break or a very long line into the collector log (N7), and the interrupt behaviour depends on code no test pins (N8).

## Fourth pass (2026-10-05, after the N7 / N8 / N9 re-brief)

- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 3 NIT). All three third-pass nits are closed in code and the jar. Attacking the closures turned up three new nits, all in code this branch adds. Under CLAUDE.md delegation rule 9 they go into one more `tooling` re-brief before the factory PR opens. Nothing here blocks the build 85 pak already on devel; it is cosmetic and test-strength only.
- **Premise correction:** the HTTP status is at the **end** of the transport message, not the start (`"Suite API " + method + " " + fullUrl + " HTTP " + status`, `SuiteApiStitchClient.java:1025-1026`). A tail cap can cut it. See N10.

### Checks re-run (independently, fresh compile into scratch)

| Check | Result |
|---|---|
| Framework compile, `-source 11 -target 11`, SDK jar only | clean |
| `adapter_runtime/vcfcf-adapter-base.jar` vs fresh compile | `javap -p -c` identical for all 43 classes; `FAILURE_MESSAGE_MAX = 200` and `failureSummary` present |
| `dist/vcfcf_sdk_compliance.0.0.0.85.pak` | its `lib/vcfcf-adapter-base.jar` is byte-identical to the runtime jar, so build 85 carries this source |
| `VcfCfAdapterTest` / `CertificateReviewTest` / `RelationshipBuilderTest` / `SuiteApiStitchClientTest` / `AmbientCredentialTest` | 11/11, 86/86, 8/8, 18/18, 28/28 |
| `SuiteApiStitchRelationshipTest`, SDK classpath only | 49/49, transport group SKIPPED |
| `SuiteApiStitchRelationshipTest`, plus `adapter_runtime/lib/*` | 145/145 (was 130/130) |
| pytest, full | 2631 passed, 8 skipped, 1 failed: the same `content/migrator/tests/test_preview.py` failure as every earlier pass (gitignored sibling repo, no Python in this diff) |
| Validate chain (7 packages) | all rc=0; managementpacks "6 Tier 2 SDK adapter project(s) valid" |
| `git diff --check`; em-dashes in added lines and the untracked test | clean; none |
| Lines over 110 chars in the touched files | only the test's usage comment (a `java -cp` command line, line 66) |

### Closures verified

| Item | Evidence | Status |
|---|---|---|
| N7 `failureSummary` sanitize + cap | message goes through `loggable(msg, FAILURE_MESSAGE_MAX)` (same `unsafeForLog` set: ISO controls, U+2028, U+2029, format chars); cap 200 plus `...`; class name and `(no message)` unchanged. Mutation (summary returns the raw message) fails 5 assertions, so the tests pin it. | Closed |
| N8 interrupt through both methods | `testAddChildInterruptedRestoresFlag` and `testFindSingletonInterruptedRestoresFlag` assert false / null, zero requests, one WARN, the one-line branch, flag set. Both read the flag with `Thread.interrupted()` in a `finally`, which clears it on every path (including the `fail` path), and they run last before `report()`. No other test touches the interrupt flag. **No leak into later tests.** But see N11: the tests do not catch removal of the restore call. | Closed as written; gap in N11 |
| N9 long Javadoc line | `SuiteApiStitchClient.java:579-585` rewrapped; no line over 110 in the file | Closed |
| No regression elsewhere | `logFailure`, `isExpectedFailure` and both catch blocks are unchanged from the third pass; only `failureSummary`, a private `loggable(String, int)` overload and the constant are new; the public `loggable(String)` delegates with `LOGGABLE_MAX`, so every existing `loggable` assertion still passes | OK |

### Attacks

| Probe (scratch only) | Observed | Status |
|---|---|---|
| Does the 200 cap hide the HTTP status? Real message shapes, `localhost` (default path) | addChild 403 is 125 chars, compliance lookup (`vcfcf_compliance` / `ComplianceWorld`) 403 is 122 chars: status visible | OK |
| Same, explicit host `vcf-lab-operations.int.sentania.net` (35 chars) | 151 / 148 chars: status visible | OK |
| Same, longer explicit hosts | status lost from a host length of **85** chars (addChild) and **88** chars (lookup); the WARN line ends `HTTP 4...`. 401-after-retry message keeps `returned 401` up to a similar length but loses the principal tail even on `localhost` (cosmetic). Full message is still in the DEBUG trace. | N10 |
| Mutation: drop `Thread.currentThread().interrupt()` in `addChildren` catch (line 658) | all 145 still pass | N11 |
| Mutation: same in the lookup catch (line 737) | all 145 still pass | N11 |
| Scratch test: fake responder throws `InterruptedException` mid-request with the flag clear | original: false, flag restored; with the line 658 mutation: the probe assertion fails. So the restore works today, and a test of this shape pins it. | N11 fix proven |
| Mutation: remove the trailing-high-surrogate drop in `loggable` | `testLoggable` fails 2 (good), but the new `failureSummary` surrogate assertions pass either way | N12 |

### Findings

#### NIT

**N10. `SuiteApiStitchClient.java:810-814` `failureSummary` (tail cap can cut the HTTP status).** Authority: `logFailure`'s own Javadoc ("the HTTP status is in the message") and the brief's question. The cap keeps the head, and the transport puts the status last, so on an explicit Suite API host of 85+ characters (legal; FQDNs run to 253) the WARN line ends `HTTP 4...` and an operator cannot tell 403 from 404 without DEBUG. Before the N7 fix the status always showed, so this is a small diagnostic regression introduced by the closure. The default `localhost` path and every host length seen in this lab are unaffected. **Fix:** when the message is over the cap, keep the head and the tail (for example the first 150 and the last 47 characters joined by `...`), dropping a high surrogate at the head cut and a low surrogate at the tail start; update the Javadoc; add a `testFailureClassification` case with a 90-character host on the addChild message shape asserting `HTTP 403` survives and the length stays bounded.

**N11. `SuiteApiStitchRelationshipTest.java:712-755` (interrupt tests do not pin the restore call).** Authority: review dimension 10 and the stated purpose of N8. The only `InterruptedException` source is the `isInterrupted()` pre-check in `urlConnRequest`, which never clears the flag, so the flag is still set on return whether or not the catch blocks call `interrupt()`. Both mutations above pass the suite. My own N8 prescription had this flaw; the tests pin the observable contract (no request, one line, false / null) but not the line N8 was meant to protect. **Fix:** add one test per method where the fake responder throws `InterruptedException` on the relationships / resources request with the flag clear (a generic sneaky-throw helper, since `Responder.respond` declares only `IOException`), then assert false / null and `Thread.interrupted()` true after return. A scratch version of this test passes on the current source and fails with the line 658 mutation.

**N12. `SuiteApiStitchRelationshipTest.java:616-628` (`failureSummary` surrogate case never hits the split).** Authority: dimension 10. 200 pairs is 400 chars; the cut at 200 lands after a low surrogate, so nothing is dropped and the assertion `length == FAILURE_MESSAGE_MAX` confirms that. The case passes with the surrogate drop removed. Coverage of the shared logic still exists through `testLoggable`, so this is test accuracy, not a hole. **Fix:** prefix the pairs with one ASCII character so the cut lands on a high surrogate, and assert the echoed message is `FAILURE_MESSAGE_MAX - 1` characters with no lone surrogate (if N10 changes the cut shape, cover both cut points).

### Dimensions (delta from third pass)

1 and 2 (`00d3382`, `6c59f6b` patterns): n/a. 3: wire unchanged. 4, 5, 6: n/a; validate chain green. 7: Java suites, pytest and validate green apart from the pre-existing unrelated migrator failure. 8: N10 is a narrow loss of diagnostic detail at WARN, still present at DEBUG; not silent content loss. 9: no listed packaging path touched; `CURRENT_TEMPLATE_VERSION` n/a; the framework jar is rebuilt and in build 85. 10: 130 to 145 assertions; gaps in N11 and N12.

### What remains before the factory PR

One `tooling` re-brief covering N10, N11 and N12 (all inside this branch's new code), a framework jar rebuild, then a fifth pass here. No compliance pak rebuild is needed for correctness; the next compliance build picks up the jar.

### If shipped as-is

Collectors behave exactly as in the third pass, with log lines now safe from malformed server text. On a Suite API host name of 85 characters or more, a failed World link WARN would end `HTTP 4...` instead of the status code, and a future edit that drops the interrupt restore would not be caught by the suite.

## Fifth pass (2026-10-05, after the N10 / N11 / N12 re-brief)

- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 1 NIT). N10, N11 and N12 are closed in code, tests and the jar, and every mutation claim in the brief holds. Attacking the head-and-tail cut found no defect in the code: every boundary I could construct behaves correctly. One new NIT: no test pins the exact-200 boundary, and a `<=` to `<` mutation survives the suite. It is in code this branch adds, so under CLAUDE.md delegation rule 9 it is fixed before the PR opens (a two-assertion test change; no source or jar change needed).

### Checks re-run (independently, fresh compile into scratch)

| Check | Result |
|---|---|
| Framework compile, `-source 11 -target 11`, SDK jar only | clean |
| `adapter_runtime/vcfcf-adapter-base.jar` (rebuilt 2026-10-05 10:32) vs fresh compile | `javap -p -c` identical for all 43 classes |
| `VcfCfAdapterTest` / `CertificateReviewTest` / `RelationshipBuilderTest` / `SuiteApiStitchClientTest` / `AmbientCredentialTest` | 11/11, 86/86, 8/8, 18/18, 28/28 |
| `SuiteApiStitchRelationshipTest`, SDK classpath only | 56/56, transport group SKIPPED |
| `SuiteApiStitchRelationshipTest`, plus `adapter_runtime/lib/*` | 162/162 (was 145/145) |
| pytest, full | 2631 passed, 8 skipped, 1 failed: the same `content/migrator/tests/test_preview.py` failure as every earlier pass (gitignored sibling repo, no Python in this diff) |
| Validate chain (7 packages) | all rc=0; managementpacks "6 Tier 2 SDK adapter project(s) valid" |
| `git diff --check`; em-dashes in added lines and the untracked test; trailing whitespace | clean; none; none |
| Lines over 110 chars in the touched files | only the test's usage comment (a `java -cp` command line, line 66), as before |
| `dist/vcfcf_sdk_compliance.0.0.0.85.pak` | carries the round-four jar (sha256 `cad29420...`), not this one (`400e4a77...`). Expected: build 85 predates the re-brief; the next compliance build picks up the jar. No correctness impact. |

### Closures verified

| Item | Evidence | Status |
|---|---|---|
| N10 head-and-tail cut | `capHeadAndTail` (`SuiteApiStitchClient.java:828-840`): sanitize the whole message, return it untouched at 200 or under, otherwise head 150 + `...` + tail 47 = 200. Probe on the real message shapes with a 244-char host (longest legal label run): addChild and the compliance lookup both end `HTTP 403`. The 90-char-host test asserts `HTTP 403`, the head, and the bounded length. Mutation back to head-only fails 5 assertions. | Closed |
| N10 Javadoc | `logFailure` now says the status is at the end and `failureSummary` keeps it; `failureSummary` Javadoc describes both cuts and the surrogate drops accurately | Closed |
| N11 mid-request interrupt | `interruptAfterToken()` throws `InterruptedException` from the fake transport with the flag clear (via `sneakyThrow`). Mutation: drop the restore at line 658, suite fails exactly "addChild interrupted mid-request restores the interrupt flag"; drop it at line 737, suite fails exactly the lookup twin. So both restores are now pinned. | Closed |
| N12 surrogate at both cuts | `"a"` + 200 pairs = 401 chars: index 149 is a high surrogate (dropped, head 149) and index 354 a low surrogate (skipped, tail 46), total 149 + 3 + 46 = **198**. Tooling's `FAILURE_MESSAGE_MAX - 2` is right; the `- 1` in my fourth-pass prescription assumed one cut. Mutation: remove the head drop, 3 assertions fail; remove the tail drop, 3 fail. | Closed |
| Interrupt flag hygiene | All four interrupt tests read the flag with `Thread.interrupted()` in a `finally`; the mid-request tests also clear it first. Probe: flag is false after the full suite, and false after running the mid-request test with the flag pre-set. No other test touches interrupt state. **No leak.** | OK |
| `loggable(String, int)` now has one caller | Private, behaviour-identical to before, Javadoc still accurate. Inlining it is taste, not correctness. | Not a finding |

### Attacks on the cut (scratch probe `P5Probe`, reuses nothing outside the class under test)

| Probe | Observed | Status |
|---|---|---|
| `null` message | `IOException: (no message)` | OK |
| Lengths 1, 196 to 200 | returned unchanged, no marker | OK |
| Length 201 | 200 chars, marker at 150, tail is source chars 154..200 exactly (4 dropped, none duplicated) | OK |
| Lengths 202, 203, 247, 248, 1000 | always 200, marker at 150, status kept | OK |
| Shorter than head + tail (197) | under the cap, unchanged; the cut code is unreachable below 201, and at 201 `tailStart` = 154 > `headEnd` = 150, so the head and tail can never overlap | OK |
| Exhaustive surrogate placement: one pair at every offset for lengths 195..260, plus all-pair strings of 100..200 pairs at both parities (15,151 cases) | zero lone surrogates, zero outputs over 200 | OK |
| CR/LF, U+2028, U+202E straddling both halves | all replaced with `?`, status tail `HTTP?403` intact | OK |
| Off-by-one mutations: `tailStart + 1`, `headEnd - 1` | each fails 2 to 3 assertions | Pinned |
| Mutation `clean.length() <= MAX` to `<` | **all 162 pass**; a message of exactly 200 chars would then lose 4 chars to `...` despite fitting | N13 |
| Cost | the sanitize pass now walks the whole message (the old `loggable` loop stopped at the cap); one linear copy per failure per cycle, of a string already in memory. Negligible. | OK |

### Findings

#### NIT

**N13. `SuiteApiStitchRelationshipTest.java` `testFailureClassification` (exact-cap boundary not pinned).** Authority: review dimension 10, and `failureSummary`'s own Javadoc ("A message longer than `FAILURE_MESSAGE_MAX` keeps its head and ..."), which promises a 200-char message is echoed whole. The code at `SuiteApiStitchClient.java:834` does that today (probe above), but nothing in the suite would notice the comparison flipping to `<`. Same class of gap as N11 and N12. In code this branch adds: **must fix before the PR.** **Fix:** two assertions in `testFailureClassification`: a message of exactly `FAILURE_MESSAGE_MAX` chars comes back unchanged (no `...`), and one of `FAILURE_MESSAGE_MAX + 1` comes back at `FAILURE_MESSAGE_MAX` with the marker at `FAILURE_MESSAGE_MAX - 3 - FAILURE_TAIL_KEEP`. Test-only; no source change, no jar rebuild, no pak rebuild.

### Dimensions (delta from fourth pass)

1 and 2 (`00d3382`, `6c59f6b` patterns): n/a. 3: wire unchanged. 4, 5, 6: n/a; validate chain green. 7: Java suites, pytest and validate green apart from the pre-existing unrelated migrator failure. 8: N10 closed, so the WARN line again always carries the HTTP status; no silent downgrade. 9: no listed packaging path touched; `CURRENT_TEMPLATE_VERSION` n/a; the framework jar is rebuilt and matches source. 10: 145 to 162 assertions; one boundary gap (N13).

### What remains before the factory PR

One `tooling` re-brief for N13 (test-only, inside this branch's new test file), then a short sixth pass confined to that test. Nothing else is outstanding from any pass.

### If shipped as-is

Collectors behave correctly: one sanitized, bounded WARN line per failure that always ends with the HTTP status, stack traces at DEBUG, and the interrupt flag restored on shutdown. The only residue is that a future edit to the exact-200 comparison would go unnoticed by the suite.

## Sixth pass (2026-10-05, after the N13 re-brief, test-only)

- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 0 NIT). N13 is closed: the exact-cap boundary is pinned from both sides, the source and the framework jar are unchanged since the fifth pass, and every suite and the validate chain are green.
- **The factory PR may open.** Nothing is outstanding from any of the six passes.

### Checks re-run (independently, fresh compile into scratch)

| Check | Result |
|---|---|
| Source unchanged since fifth pass | `SuiteApiStitchClient.java` mtime 10:31:54, `SuiteApiStitcher.java` and `RelationshipBuilder.java` 2026-10-02, all before the fifth pass; only the test file is newer (10:39:49) |
| `adapter_runtime/vcfcf-adapter-base.jar` | sha256 `400e4a77...`, the same jar the fifth pass reviewed (mtime 10:32:39) |
| Jar vs fresh compile (`-source 11 -target 11`, SDK jar only) | `javap -p -c` identical for all 43 classes, 43 in the jar |
| `VcfCfAdapterTest` / `CertificateReviewTest` / `RelationshipBuilderTest` / `SuiteApiStitchClientTest` / `AmbientCredentialTest` | 11/11, 86/86, 8/8, 18/18, 28/28 |
| `SuiteApiStitchRelationshipTest`, SDK classpath only | 59/59, transport group SKIPPED (was 56/56) |
| `SuiteApiStitchRelationshipTest`, plus `adapter_runtime/lib/*` | 165/165 (was 162/162) |
| pytest, full | 2631 passed, 8 skipped, 1 failed: the same `content/migrator/tests/test_preview.py` failure as every earlier pass (gitignored sibling repo, no Python in this diff) |
| Validate chain (7 packages) | all rc=0 on the first run; managementpacks "6 Tier 2 SDK adapter project(s) valid". No transient compliance compile error seen, so no re-run was needed |
| `git diff --check`; em-dashes and trailing whitespace in the test | clean; none; none |
| Lines over 110 chars in the test | only the usage comment at line 66, as before |

### N13 closure verified

| Item | Evidence | Status |
|---|---|---|
| Assertions present and correct | `testFailureClassification` (test lines 622 to 634): a 200-char message (`a`..`z` cycling, no unsafe chars) must come back as `"IOException: " + message`, byte for byte; that message plus `z` (201 chars) must come back at exactly `FAILURE_MESSAGE_MAX` with `...` at `headKeep` = 200 - 3 - 47 = 150. Both expectations derive from the class constants, so they track any future retune. Matches the fifth-pass prescription. | Closed |
| Mutation `<=` to `<` at `SuiteApiStitchClient.java:834` (scratch copy, compiled ahead of the real classes) | exactly 1 of 165 fails: "message of exactly FAILURE_MESSAGE_MAX is unchanged" (actual shows the 150 + `...` + 47 cut). Tooling's claim holds. | Pinned |
| Reviewer's extra mutation, `<=` to `<= MAX + 1` (the other side of the boundary) | 2 of 165 fail: the 201-char length and marker assertions. Before this re-brief only the 100,000-char test touched the cut and would not have noticed. | Pinned |

### Dimensions (delta from fifth pass)

Test-only change; dimensions 1 to 9 unchanged from the fifth pass. 10: 162 to 165 assertions; the cap boundary is now pinned on both sides; no remaining coverage gap found.

### If shipped as-is

Same runtime behavior as the fifth pass (source and jar unchanged): one sanitized WARN line per failure, at most 200 chars of message, always ending with the HTTP status. A future edit to the cap comparison in either direction now fails the suite.
