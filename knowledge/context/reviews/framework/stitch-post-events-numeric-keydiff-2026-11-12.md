# Framework review: stitcher post, events, numeric properties, icon hints, keydiff

- **Branch:** `tooling/stitcher-post-events-numeric` (5 commits on merge base `3a4eadf5`; tip `8edfc515`)
- **Diff:** `git diff origin/main...HEAD`, 18 files, +3067 / -47
- **Driver:** vCommunity Java port design, toolset gaps T1 to T5 (`knowledge/designs/managementpacks/vcommunity-java-port-design.md`, untracked in the main checkout, see B2)
- **Reviewer:** `framework-reviewer`, 2026-11-12. One round (CLAUDE.md delegation step 9).

## Verdict

**CHANGES REQUESTED: 3 BLOCKING / 6 WARNING / 5 NIT.**

The Java side holds up well. The `Kind` refactor changes nothing on the
wire or in the logs: I reproduced that independently and also widened the
differential. The typed wire format matches the spec. Events are escaped
correctly and message text never reaches a log line. The new suites are
green on all three SDK jars. Three things block:

1. The `/query` guard on `post` can be bypassed with a `#` fragment, and
   the request then goes to a write endpoint.
2. The new docs cite a design file that is not in the repo (RULE-015).
3. `keydiff` exits 0 ("nothing differs") when nothing was compared.

## What I reran

| Check | Result |
|---|---|
| Framework compile at `--release 11`, `build-framework.sh --compat-only`, legs 9.0 / 8.18.7 / 9.1.1.0100 with `VCFCF_SDK_COMPAT_REQUIRED=1` | rc 0 on all three |
| `run_stitch_tests.sh` against `vrops-adapters-sdk-8.18.7.25423534.jar`, `9.0.2.0.25137845.jar`, `9.1.1.0100.25795063.jar` (sha256 checked; JDK 17, JDK 25 for 9.1.1; log4j present so no skips) | 7 suites pass on each line. `SuiteApiStitchQueryEventsTest` 172/172, `SuiteApiStitchBatchTest` 155/155, Transport 81/81, Relationship 165/165 |
| Request-identity check (author's `RequestDiff` harness, compiled against my own `git archive origin/main` tree and against the branch) | **IDENTICAL**, 22 requests (method, URL, headers, body) and every log line |
| My own wider differential `RequestDiff2`: string/stat/combined batches under success, batch 400 then per-id 404 and 500, 401-once, 503, 400-everywhere, caps 0/-1, oversize entry, null/NaN/Infinity/-0.0/1e-7/non-BMP values, interrupted thread, closed client | **IDENTICAL**, 130 requests and 111 log lines |
| Probe of the new surface (branch only) | Results feed B1, W2 and the verified items below |
| Scratch copies of compliance and vsanperf: `validate-sdk --require-sdk-compat` and `build-sdk` with the branch kit (kit source checked byte-equal to the branch) | validate OK on both. Both build; pak-compare 1 WARNING, 0 BLOCKING, install gate passed |
| Seven-package validate chain | all rc 0 |
| pytest, branch vs `origin/main` | branch: 14 failed / 3846 passed / 15 skipped. main: 14 failed / 3921 passed. **The 14 failure names are identical.** The passed-count gap is main's newer `test_stock_id_guard.py` (61) and `test_buildkit_stock_ids.py` (6), which the branch lacks (see W1). The branch adds 15 keydiff and 4 icon tests, all passing |

## BLOCKING

### B1. `post` sends to write endpoints when the path carries a `#` fragment

`SuiteApiStitchClient.java:2119-2138` (`checkQueryPath`), used by `post` at `:2097`.

The guard strips text after `?` and checks that what is left ends in
`/query`. It never considers `#`. The request URL is built as
`new java.net.URL(suiteApiBase + path)` (`VcfCfAdapter.openPlatformConnection`,
`VcfCfAdapter.java:1577`), which treats everything after `#` as a fragment.
A fragment is never sent on the request line. Reproduced:

```
post("/api/resources/<uuid>/properties#/query", body)  -> ACCEPTED, wire path /suite-api/api/resources/<uuid>/properties
post("/api/events/bulk#/query", body)                  -> ACCEPTED, wire path /suite-api/api/events/bulk
```

That is an unisolated write through the call documented as "Not a write
path ... refused ... before a token is fetched or a byte is sent". The
claim is made in the `post` javadoc, `SuiteApiStitcher.post`,
`tier2_architecture.md` ("Stitcher reads, events and numeric properties"),
the skill, and the release note. A `#` after the `?` is also wrong: it
silently truncates the query string, so `?name=a#b` asks for `a`.

The guard also passes, untouched: `;` (`.../properties;/query`), `..`
segments (`/api/events/bulk/../../resources/query`), and percent-encoding
(`.../bulk%23/query`). In the specs (8.18, 9.0, 9.1, internal 9.1), every
path ending in `/query` is a read, so none of these three is a confirmed
write today. They are still raw input reaching the proxy's path
normalizer, carrying the token.

**Fix:**
- Before the suffix check, refuse any path containing `#`, `\`, `%` or
  `;`.
- Refuse any `.` or `..` segment in the part before `?`.
- Simplest form: require that part to match `^(/[A-Za-z0-9_\-{}]+)+$`
  (UUIDs and the spec's segments all fit).
- Add those cases to `testPostGuard`'s `bad` array.

### B2. RULE-015: the new docs cite a design file the repo does not contain

`knowledge/rules/cited-artifacts-reproducible.md`. Where the citations are:
- `knowledge/context/tier2_architecture.md:1559` ("Driver:
  `knowledge/designs/managementpacks/vcommunity-java-port-design.md`")
- design experiments E3, E4 and G5 cited in `tier2_architecture.md`, in
  `SuiteApiStitchClient.java:757`, `SuiteApiEvent.java:35`, and in the
  `api-surface/suite_api_batch_push.md` addition
- `keydiff.py:4` ("section 11, toolset gap T5")
- the `__main__.py` docstring

The file is not on `origin/main` or on the branch. It exists only as an
untracked file in the main checkout (`?? knowledge/designs/managementpacks/vcommunity-java-port-design.md`,
along with `vcommunity-java-port-2026-11.md`). A fresh clone cannot
resolve any of these citations.

**Fix (orchestrator, since `knowledge/designs/` is not `tooling`'s):**
commit the design file, and `vcommunity-java-port-2026-11.md` if it is
referenced, in this PR or merge them first. The other option is to restate
E3, E4 and G5 inline wherever they are cited.

### B3. `keydiff` exits 0 ("nothing differs") when nothing was compared

`src/vcfcf_common/keydiff.py:612`; table output at `:466-469`.

The exit code comes only from the difference categories. Reproduced, all
rc 0, with a summary of all zeros:

- (a) two empty scopes;
- (b) every object unidentified on both sides. This is a VMWARE scope where
  the listing carries no `VMEntityVCID`/`VMEntityObjectID`, the exact case
  the tool refuses to name-match;
- (c) a `--key-prefix` that matches no key;
- (d) a run where every row is stale; same logic, not separately run.

The skill tells authors to "use it for a port's parity check". A vacuous
pass is the failure that check exists to catch. Lesson:
`knowledge/lessons/sm-statkey-api-prefix.md`, where empty results look
exactly like a clean result.

**Fix:**
- Count the objects and keys actually compared, and print them in the
  summary ("compared N objects, M keys; K not compared").
- Exit with a distinct non-zero code (for example 4, "nothing compared")
  when M is 0 or every compared row is stale.
- Exit 1 when any object was not compared (unidentified or ambiguous), or
  give that its own code. Never exit 0 for it.
- Document the codes in the docstring and `--help`, and add a test for
  each of (a) to (d).

## WARNING

### W1. The branch is behind main and conflicts with it

`origin/main` is now `77aecc1d` (#353, stock-id guard, merged):
- `BUILDKIT_VERSION = "1.0.29"`;
- `.github/release-notes-buildkit.md` already opens with
  `## Behavior since 1.0.29`;
- `tier2_architecture.md` changed.

`git merge-tree` reports content conflicts in both
`.github/release-notes-buildkit.md` and
`knowledge/context/tier2_architecture.md`.

**Reconcile on rebase:**
- Release note: fold this branch's five bullets into the **existing**
  `## Behavior since 1.0.29` section. Keep one heading, not two. The
  stock-id bullets are already there.
- Tier2 changelog row (`tier2_architecture.md:1643`): change "`BUILDKIT_VERSION`
  not changed here; the release note goes under the next kit version" to
  "ships in 1.0.29".
- When `migration/vcf-cf-prefix` merges, it hits the same insertion point
  and also sets 1.0.29. Same rule: one 1.0.29 section, every branch's
  bullets under it. The kit version is set once, not bumped again.
- Rerun after rebase: kit build, then `validate-sdk --require-sdk-compat`
  and `build-sdk` on scratch compliance and vsanperf. The kit now carries
  the stock-id guard, which runs during `build-sdk`, so today's green
  result does not carry over. Also rerun the stitch suites and the
  validate chain.
- Add this report's row to the reviews index (`reviews/framework/README.md`
  on main).

### W2. Numbers lose precision without warning, and nothing says so

`SuiteApiStitchClient.java:2514-2515`. Every `Number` is written as
`Double.toString(n.doubleValue())`. Probe results:
- `9007199254740993L` is sent as `9.007199254740992E15`;
- `Long.MAX_VALUE` as `9.223372036854776E18`;
- a 30-digit `BigInteger` as `1.2345678901234568E29`;
- `0.1f` as `0.10000000149011612`;
- `5` as `5.0`.

This is valid JSON. It is locale-independent (checked under
`Locale.GERMANY`), and `-0.0` and `1.0E-9` are valid too. The schema
types `property-content.data` as `format: double` (8.18, 9.0, 9.1), so
some loss is inherent. But no javadoc, doc or skill line tells an author
that a `Long` above 2^53 (a byte counter, a µs epoch) or a `BigDecimal`
is rounded, or that integers go out as `n.0`.

**Fix:** one sentence in the client and facade javadoc, the tier2 section
and the skill: "values are sent as doubles; integers above 2^53 and
`BigDecimal`/`BigInteger` lose precision; send a `String` when the exact
value matters". Optionally drop and count an integral `Number` whose
magnitude exceeds 2^53.

### W3. The cancel-time floor is put down to the spec, which only floors start time

`SuiteApiEvent.java:62-63` ("Earliest start or cancel time the spec
accepts"), `SuiteApiStitchClient.java:1615,1625`, and
`tier2_architecture.md:1599` ("start or cancel time before 2000-01-01
(the spec floor ...)").

In all three specs, `startTimeUTC` has the `>= 946684800000` rule (and a
`minimum` on 9.0). `cancelTimeUTC` has no floor. The spec's own examples
send `"cancelTimeUTC" : 0`, and the investigation's read-back of a landed
event shows `"cancelTimeUTC":0` on an active event
(`investigations/vcommunity-notification-events-foreign-vm.md`, Result 3).
Refusing a cancel time before 2000 is a framework choice, presented as a
spec fact.

**Fix:** reword it as the framework's rule ("the spec floors only
`startTimeUTC`; 0 in its examples means not cancelled; the framework
refuses a set cancel time before 2000"), or treat `cancelTimeUtc <= 0` as
unset.

Same file, line 27: the 8.18 spec's XML name for `severity` is `severity`;
it is `criticality` from 9.0. Say "XML name `criticality` on 9.0 and 9.1".

### W4. `post` reads the whole response into memory, with a 30 s read timeout

`SuiteApiStitchClient.java:2105` reaches `urlConnRequest` at `:2403-2411`,
which reads the body into an unbounded `StringBuilder`. `get` shares this,
but `post` is the new route built for bulk reads (`stats/query`,
`stats/latest/query` over many resource ids). That is exactly the heap
risk the design names (Risk 4: Cloud Proxy heap unknown; the size limit
is a requirement there, not a tuning choice). 30 s also undercuts the
120 s the batch pushes allow.

**Fix:** state in the `post` javadoc, the tier2 section and the skill that
the body is read whole, and that callers bound the resource ids per query
and use `page`/`pageSize` where the endpoint takes them. Optionally add
`post(path, body, readTimeout)` or a response-size cap that throws.

### W5. The "byte-identical" proof for existing String callers lives only in session scratch

The committed tests (`SuiteApiStitchQueryEventsTest` T3,
`testTypedStringsIdentical` / `testTypedBatchStringsIdentical`) compare
the typed calls with the untyped ones **on the branch**. Proof that the
untyped calls send what `origin/main` sent is the scratch `RequestDiff`
harness, which the "Compatibility proof" paragraph
(`tier2_architecture.md:1629`) describes and no clone can rerun
(RULE-015's intent). The batch internals changed underneath every string
caller (W-level per dimension 10).

**Fix:** commit golden-body assertions captured from `origin/main` into
`SuiteApiStitchBatchTest`:
- exact request bodies for `pushPropertiesBatch`, `pushBatch` and the
  400 per-id fallback;
- a map that carries `""`, a control character, `\"`, `\\` and a non-BMP
  character.

Or commit the request-diff harness as a test that compares against a
checked-in fixture.

### W6. The skill gives the `managedExternally(false)` route without saying it is untested

`.claude/skills/vcfops-sdk-adapter/SKILL.md:225`: "use
`managedExternally(false)` and stop re-pushing, or ...". That is an
instruction. `tier2_architecture.md` and `SuiteApiEvent.java:30-35` both
say this lifecycle is not established for a GENERAL adapter's REST event
(G5).

**Fix:** append "(whether a GENERAL adapter's event is cancelled this way
is untested, G5)".

## NIT

- **N1.** `SuiteApiStitchClient.java:1059,1227,2497-2502`. The string
  batch and the per-id fallback for `Kind.PROPERTIES` now go through the
  `typed=true` serializer (`propertiesBatchEntryOf` /
  `buildPropertiesJsonOf`). The bytes stay identical only because
  `isSendable(PROPERTIES)` admits only `String`. The javadoc gives the
  reason as "without [the flag] every value is cast to String exactly as
  before". Pass `kind == Kind.TYPED_PROPERTIES` as the flag, so the old
  path is literally the old path, or correct the comment.
  `propertiesBatchEntry` is now test-only.
- **N2.** `SuiteApiStitcher.java:335-392`. The facade's typed javadoc
  leaves out the "keep one type per key; numeric over string history
  untested (E3)" caveat, and the facade is what authors read. Add the
  sentence.
- **N3.** `SuiteApiEvent.java:45-55` and the WARN text at
  `SuiteApiStitchClient.java` (`pushEvents`). The refusal is justified by
  the foreign-resource result only. Add the tier2 sentence: "not
  established on a pak's own resource; refused everywhere because the
  facade cannot tell". The investigation saw zero NOTIFICATION events
  system-wide, which supports refusing by default. No opt-in is needed
  now.
- **N4.** `SuiteApiStitchClient.java:1604`. The pushEvents failure WARN
  lists "first resource ids [X, X]", one entry per event. Deduplicate.
- **N5.** `keydiff.py`:
  - `--help` says "Read-only: GET requests only" (`:498`), but the client
    POSTs `/api/auth/token/acquire`. The docstring at `:5-7` is right;
    match it.
  - The token is never released.
  - `VCFOpsClient._request` sets no timeout, so a stalled instance hangs
    the CLI.
  - `_cell` (`:428`) escapes only `\t\r\n\\`, so an ESC in a property
    value reaches the terminal.
  - `--snapshot-out` writes every property value of every object in scope
    (guest names, IPs, annotations). Say so in its help.
  - `--b-adapter-kind` is silently ignored when side B is a snapshot.

## Verified, no finding

**`post`**
- The base URL is fixed. The path must start with `/`, so
  `https://evil/...` and `//evil/...` stay on the configured host.
- Control characters (CR/LF header injection) are refused.
- The request and response bodies never reach a log line or an exception
  message. Probed with a marker; the existing redaction tests cover it.
- The 401 path re-acquires once and re-sends a read-only query, which is
  safe.
- A closed client throws `ClientClosedException` with no token. Only
  locals and `tokenLock` are used, so it is thread-safe like `get`.

**`pushEvents`**
- Wire fields and enums match the `event` / `events` schemas on 8.18, 9.0
  and 9.1:
  - required `eventType`, `message`, `resourceId`;
  - seven severities;
  - the six-value `diagnosticSubType` common to all three lines, with
    `TROUBLESHOOT` added in 9.0 and more in 9.1;
  - `HARD_THRESHOLD` correctly omitted.
- The `/adapterkinds/{kind}` 1514 rejection is traced to the
  investigation, Result 1. The DIAGNOSTIC landing in about 45 s and the
  NOTIFICATION 200-and-dropped (with both `managedExternally` values) are
  traced to Results 2 and 3.
- JSON escaping is correct for `\u0000`, `\u001f`, ` `, `"` and `\\`,
  and for non-BMP pairs.
- A lone surrogate becomes `?` through UTF-8 encoding. That is
  pre-existing `jsonStr` behaviour, shared with properties.
- A 300k-character message serializes and sends.
- It never throws. A null event, a NOTIFICATION event and a closed client
  are all counted.
- Counting matches the batch result's meaning: a failed request counts in
  both `sent` and `skipped`, and the rest counts as skipped.
- The message text is never logged.

**Typed properties**
- The wire shape matches the `property-content` schema (`values` xor
  `data`) and the vendor `config|num|processes` / `data:[93.0]` example on
  all three lines.
- Boolean, null, NaN, infinite and a too-large `BigDecimal` are dropped
  and counted, with one WARN per call.
- The string batch still drops a smuggled `Number`.

**`Kind` refactor**
- Read line by line. Chunking, `fits`, the 400 per-id fallback, the
  NOT_SENT/STOP handling, counters, retry, and the op names in log text
  (`pushPropertiesBatch`/`pushStatsBatch`, per-id `pushProperties`/`pushStats`,
  and the dropped-entry text with `badValue`) are all unchanged for STATS
  and PROPERTIES. The two differentials above confirm it.

**Spec and doc claims**
- The four `/query` body schemas are identical across 8.18, 9.0 and 9.1.
- Compliance's ambient session called `properties/latest/query` and
  `resources/query` (`investigations/suiteapi_ambient_auth_devel_2026_06_09.md:80-81`).
- No doc claims a live test of the new calls; `suite_api_batch_push.md`
  says "not yet live tested".

**Icons**
- Original 400x400 shapes on the house palette.
- No `script`, `image`, `use`, `foreignObject` or `href`; they parse as
  XML.
- They resolve through the Tier 1 `builder._icon_bytes_for` and the Tier 2
  `_pack_icons` paths.
- `mp_icon_library.md` is the only enumeration of hints, and it is
  updated.
- The kit copies the whole `templates/icons/` directory.

**keydiff**
- Every request it makes: `GET /api/resources` (paged, `pageSize=1000`),
  `GET /api/resources/stats/latest` (50 ids per call, `maxSamples=1`),
  `GET /api/resources/properties` (50 ids per call), plus the client's
  `POST /api/auth/token/acquire`. 2500 objects took 103 GETs.
- Credentials come only through `VCFOpsClient.from_env(profile)`. Snapshots
  carry `profile` and `base` only, with no token or password. Error output
  carries the status, never a body.
- VMWARE objects never fall back to their name. Ambiguous identities are
  set aside.
- Keys missing on both sides cannot appear, because the rows are built
  from the union of keys.

**Stale zips (dimension 9)**
- No file on the "after tooling changes" list is touched.
- `vcfcf_packaging/templates` is untouched, so `CURRENT_TEMPLATE_VERSION`
  does not apply.
- A pak that needs the new methods or icons needs the next kit (W1), and
  the release note says so.

## If shipped as-is

- A pak author can write through `post` past its "query only" guard with a
  `#`.
- A fresh clone cannot resolve the design citations.
- A port's parity check can report clean (exit 0) after comparing nothing.
- The release note would conflict with main's 1.0.29 section, or
  duplicate it.
