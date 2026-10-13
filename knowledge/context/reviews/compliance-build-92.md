# Review: compliance adapter build 92

- **Adapter:** `content/sdk-adapters/compliance`, branch `feat/build-90-overrides-file`
- **Reviewed:** HEAD `bdb49e6` (commits `bd41a75..bdb49e6`) against build 91 at `4fa180a`, 2026-10-13, 1:54 PM local
- **Design:** `knowledge/designs/sdk-adapters/compliance-build-92-drop-custom-skip-cancel.md`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.92.pak`, sha256 `670395c3d8d40f337306cd53e973def920173d65fc58f05962edb5e324d10479` (confirmed)
- **Verdict:** APPROVE, 0 BLOCKING / 4 WARNING (one pre-existing) / 4 NIT

Build 92 does what the design says, and the Skip fix is correct: a skipped
control in force on an object is pushed as -1 every cycle, with no
read-back and the right Actual text, only on objects whose own guide
version evaluates it. Nothing in the delta turns a failed or missing read
into a pass. The biggest open question is not in the code. The removed
`custom_profile_path` identifier was part of the account's identity, and
nothing in the repo proves what VCF Operations does when an upgrade drops
an identity field from accounts that already store a value. The devel
upgrade over 91 is the proof. Check the account's identity there before
anything else.

## Independent verification

| Check | Result |
|---|---|
| Pak sha256 | matches the brief |
| `validate-sdk` | OK, 21 sources compile |
| `build-sdk` from HEAD (scratch output) | builds 0.0.0.92; the jar entries, views.zip contents, overview contents and describe.xml are identical to the author's pak (archive timestamps differ); describe.xml in the pak is byte-identical to HEAD; working tree clean afterwards |
| `pak-compare` 92 vs 91 | gate PASS, 0 BLOCKING / 1 WARNING (adapter instance identifier count 5 vs 6) / 0 INFO. Matches the author. |
| `pak-compare` 92 vs 89 | 0 BLOCKING / 1 WARNING (ComplianceWorld group attributes 6 vs 1) / 1 INFO (overrides template). The identifier warning is gone because 89 also had 5 identifiers, just a different set: pak-compare counts identifiers and does not compare which ones carry identity (relevant to W1) |
| Describe 91 vs 92 (pak) | only the `Custom` enum value and the `custom_profile_path` identifier removed, plus the comment |
| Dimension 13, my own parse of the built pak's describe.xml | 144 alerts, 152 symptom definitions, 7 `<SymptomSets>` containers, every one with 2 or more children; every symptom reference resolves; `waitCycle` and `cancelCycle` are integers (1 and 1 or 3). No alert or symptom changed in this build. |
| `ci/run_java_tests.sh` | exit 0; 13 Java suites pass; generator `--check` up to date (136 + 6 + 1 alerts); symptom-set test, AlertList, widget types, template tests OK |
| `pytest` (adapter tests) | 33 passed, 11 subtests |

## (a) Removing `custom_profile_path`: identity risk on upgrade

The identifier had no `identType`. The SDK describe schema
(`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/conf/describeSchema.xsd`,
lines 375 to 379) says: "1 - part of uniqueness, 2 - not part of
uniqueness. By default identifiers are part of uniqueness." So in build 91
the account identity was the tuple (`vcenter_host`, `benchmark_profile`,
`custom_profile_path`, `allowInsecure`). The two later settings
(`read_appliance_settings`, build 74; `overrides_file`, build 90) were
deliberately added with `identType="2"` for exactly this reason. Build 92
is the first build that removes an identity field from this account kind.

Nothing in `knowledge/`, the skill, the lessons or the reference docs
records what VCF Operations does on a pak upgrade when an identifying
identifier disappears from accounts that already store a value (here
`""` by default). The only repo precedent (vcommunity builds 4 to 7,
`bad8ad4`) renamed identifiers on a pak with no proven in-place upgrade.
Plausible outcomes, from benign to bad:

1. The stored value stays as an orphan field, ignored. The account keeps
   its id and collects. (Most likely.)
2. The account works until someone edits and saves it, then the save is
   refused or the identity is recomputed.
3. The account is shown as needing attention, or a duplicate-identity
   error appears where two accounts on the same vCenter differed only by
   the CSV path (unlikely on devel).

Blast radius if it goes badly: the compliance metrics live on the VMWARE
objects and are not lost, but recreating an account gives it a new id, so
its ComplianceWorld child link and its Summary keys start over.

**What to check first on devel, in this order:**

1. Before upgrading, record the wld01 account's id and its identifier
   values (`GET /api/adapters/<id>`), including `custom_profile_path`.
2. After the upgrade, confirm the installed version reads 0.0.0.92 (not the
   CLI's OK line, factory issue #202), then that the same account id is
   still there, collecting, with no identity or configuration error.
3. Open the account's edit dialog, save it without changes, and confirm the
   save succeeds and the account id is unchanged.
4. Re-read `GET /api/adapters/<id>` and note whether `custom_profile_path`
   is still stored.

If any of 2 to 3 fails, the smallest fix is to put the identifier back in
describe.xml as `hidden="true"` (identity unchanged, never read by the
adapter) rather than removing it.

## (b) The per-cycle -1 push for skipped controls

Read in full: `ComplianceAdapter.afterPush` and `pushSkippedInForce`
(`ComplianceAdapter.java:1006-1056`), `ComplianceDecisions.skipPush` and
`SkipPush` (`ComplianceDecisions.java:648-701`), `buildSelector`
(`ComplianceAdapter.java:580-652`), `cleanBatch`.

- **No read-back.** `pushSkippedInForce` pushes `sp.props` and `sp.stats`
  directly. It does not touch `latestCompliant`. OverridesTest also pins
  this in the source.
- **Actual text.** `orphanProps(ids, null, ids, overridesFile)` gives every
  id `(skipped by override file <name>)`. Correct.
- **Bounded to the active guide version.** The ids are
  `addEvaluated(kind, cycleUnadjusted.get(d.profileName)) ∩ skipped`, which
  is the object's own decided profile (or its per-kind pin, or the reused
  previous profile) before the overrides were applied, filtered by
  `BenchmarkSelector.evaluatedFor`. Manual-review controls, and VAMI
  controls with appliance reads off, are not evaluable, so they are never
  pushed. A Skip of a control that only another SCG version carries
  pushes nothing here. It still goes through the build 90 cleanup path
  (W4 shape).
- **No push where nothing was decided.** Version-unreadable objects never
  reach `afterPush`. No-benchmark objects have `d.profile == null`.
  Unmatched objects have no resource id. The skipped ids join `live`, so
  the end-of-cycle cleanup does not touch them in the same cycle.
- **Removing the Skip resumes scoring.** The next parse lacks the Skip, so
  `adjust` keeps the control. It is scored and pushed 1 or 0 on that same
  cycle, and `skipPush` returns empty. A file that turns absent
  (HTTP 400/404) drops all overrides, so scoring resumes by design. A
  fetch failure with a copy in force keeps the Skip.
- **Creating -1 where the control never had a key.** This does happen on
  objects where the guide evaluates the control but the object does not
  apply at runtime. The concrete case: a skipped vSAN cluster control on a
  non-vSAN cluster (`collectVimObject` takes `emptyResult`, then
  `afterPush`). Before build 92 the cleanup never created a key. This is
  not a false compliance signal: -1 means not evaluated; the Actual names
  the skip; the symptom fires on `= 0`; `unreadable_count` is computed from
  the evaluation, not from these keys; and no shipped view reads
  per-control `Compliant`. The scope is small (one cluster control per
  guide). It is acceptable, but the docs no longer say it (N1).
- **Logging.** One INFO per cycle with key and object counts, not per object.

## (c) Instance-wide Profile rejection

`ComplianceOverrides.parse` rejects a `<Profile>` that has no `kind`
attribute, with `INSTANCE_PIN_REJECTED` ("instance-wide pin: use the
Compliance Profile setting"), and then `continue`s. Every other entry is
still parsed and applied. `kind=""` falls through to "unknown kind ''". A
rejection counts toward `N rejected` in `overrides_status` and does not
raise the not-loaded alert. Tests cover the reason text and confirm that a
Skip in the same file still applies.

## (d) An account stored as Custom

`ComplianceConfig.isCustomName` trims the value and ignores case. A stored
Custom becomes `BenchmarkSelector.AUTO`, with `storedAsCustom` set.
`onConfigure` logs one WARN, with no secrets in it. `isAuto()` is then
true, so `buildSelector` takes the `loadAll` path, and that path applies
`manual_review.csv` to every bundled profile. A null or blank value keeps
the SCG 8.0 fallback. Nothing throws. `resolveBundledProfileName("Custom")`
now throws "not bundled", but that call is reachable only when the config
mapping is bypassed, and the test asserts the message no longer offers
Custom.

## (e) The author's flagged leftover-0 bug (adapter issue #42)

Confirmed in code. `cleanBatch` reads the latest value back and pushes -1
only over a 0 (`zeroOnly`: controls outside the object's current guide,
for example after a guide version change) or over a 0 or 1 (`zeroOrOne`:
controls in the guide but not pushed this cycle, for example vSAN turned
off on a cluster). On the next cycle the read returns -1 and nothing is
pushed. The per-control symptoms have `cancelCycle="3"`
(`describe.xml`, generated symptom block). A single -1 sample therefore
leaves the alert open, which is the issue #41 shape exactly. It also
covers a Skip of a control outside the object's current guide. This build
did not introduce it, and it fails toward a stale open alert, never a
false pass. Graded W4, a registration candidate (RULE-012). Filed as
adapter issue #42 (2026-10-13, 1:47 PM).

## (f) Docs parity

Updated consistently: README, REFERENCE.md, docs/installing.md,
docs/data-reference.md, docs/overrides.md, docs/overview.md,
CANONICAL_SCHEMA.md (now framed as the contributor reference, linked only
from docs/building.md), profiles/UNAUDITED_CONTROLS.md, the template, the
overrides recommendation (2042) and the WARN text. The new menu path and
the clone steps (`.xml_Copy` default, rename to `<name>.xml`, User
Defined) are consistent across all of them, and "older builds" wording is
omitted as the design allowed. There is no Custom or old menu path left in
any doc, with one exception, W2. The overrides.md anchor
`#skip-turn-a-control-off` still resolves. The README known-issues list
needed no change (its #30 to #32 are still open). No em-dash in any added
authored line. The only em-dash in the diff is the generated
`docs/inventory-tree.md` header, which is the factory generator's issue.

## Findings

**WARNING 1** [describe.xml:35, removed `custom_profile_path`;
skill § describe.xml, describeSchema.xsd `identType`] An identifier that
was part of the account's identity is removed. The upgrade behavior is
unproven, and pak-compare cannot see it (it counts identifiers). See
section (a) for the risk and the devel check order. If devel shows any
identity symptom, restore it as `hidden="true"` instead of removing it.
Graded WARNING, not BLOCKING, because the likely outcome is benign and
the devel upgrade under its own go proves it before any tag.

**WARNING 2** [resources/resources.properties:31, key 105; design Vision 1,
dimension 11] The hand-written "Host Compliance Score Degraded"
recommendation, which operators see in the Ops UI, still says "If using a
custom benchmark profile, verify the profile CSV is current." That feature
no longer exists, and the design says every doc mention of the custom CSV
is removed. Fix: delete that sentence.

**WARNING 3** [ComplianceAdapter.java:1050-1052; skill § bulk-read
dynamic pattern, dimension 8] `pushSkippedInForce` makes its own
`pushProperties` and `pushStats` calls. Every object with a Skip in force
gets two more Suite API POSTs per cycle on top of the two from
`pushComplianceViaClient`. One Skip of a VM control on a 5,000-VM vCenter
adds about 10,000 POSTs every 5 minutes. Fix: merge `sp.props` and
`sp.stats` into the object's main push maps (or compute the skip push
before `pushComplianceViaClient` and send one props and one stats call).

**WARNING 4, pre-existing, not introduced by build 92** [ComplianceAdapter.java
`cleanBatch`, ComplianceDecisions.java `staleControls`; adapter issue #42]
The stale cleanup sets -1 once, so with `cancelCycle="3"` the alert stays
open after a guide version change, after a control stops applying, or
after a Skip of a control outside the object's guide. See section (e).
It does not block this build. Registration candidate for
`knowledge/context/defects.md`.

**NIT 1** [docs/overrides.md "What happens to a skipped control"] The build
removed the sentence "The pack never creates a metric the object did not
have", which is right, but it does not say that the skip push now creates
a -1 key where the control does not apply (a non-vSAN cluster). Add one
sentence.

**NIT 2** [ComplianceRollup bucket `Custom`] A formerly Custom account's
vCenter object keeps its last `Rollup|Benchmark|Custom|objects` value
forever, because the bucket is pushed only while it is in use. Push 0 once
on the first cycle after `storedAsCustom`, or say so in the README entry.

**NIT 3** [ControlEvaluator.java:620, 652] Comments still refer to
operators writing custom profiles. They are comment-only and stale.

**NIT 4** [adapter repo issues] #36 (custom CSV cache), #40 (custom
profile how-to) and the custom-cache part of #26 are moot after build 92.
They are closure candidates for the orchestrator once 92 is accepted.

## Review dimensions not covered above

1, 3: no new path folds a failed read into a pass. The skip push only
ever writes -1. 2: no vim25 code changed. 4: the loader lost the Custom
CSV branch, and bundled parsing is still by header. 5: no stitching or
foreign-key change. 6: one new WARN per configure and one INFO per cycle,
with no credentials in either. 7: `cycleUnadjusted` is replaced every
cycle and holds the cached bundled maps, so it does not grow. 9: build 92
is bumped and the CHANGELOG line matches the diff. The removals are
minimal, and behavior preservation for the remaining pin paths is covered
by the updated OverridesTest. 10: no gap changes.

## Registry check (knowledge/context/defects.md)

- **DEF-023** (single-page resource list): still open. `ComplianceStitcher.java`
  is not in the `4fa180a..bdb49e6` diff, so the build 88 paging fix is
  unchanged. Still owed: devel proof of the paging, or of the vCenter
  collection alert path.
- No other open defect names compliance (DEF-022 and DEF-024 closed on
  build 91 devel evidence).
- Registration candidate: W4 (adapter issue #42). W1 becomes one only if
  the devel upgrade shows an identity problem.

## Devel verification owed (orchestrator, under its own go)

Run the section (a) identity checks first. Then: the shell-timeout alerts
on both wld01 hosts cancel within three cycles of the first build 92
collection, and the log shows the per-cycle "skipped control key(s) set to
-1" INFO line. Confirm the lockout override and the VM pin are still in
force. Confirm the account's Compliance Profile dropdown no longer offers
Custom.

## Re-review: HEAD `ddaf06e` (fix commit on top of `bdb49e6`)

- **Reviewed:** 2026-10-13, about 2:30 PM local, branch `feat/build-90-overrides-file`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.92.pak`, sha256 `d212c9706f5abc3336220fb63df592e5b38c499a537c19ab2dad93c02a58bb34` (confirmed), reference 0.0.0.91
- **Verdict:** APPROVE, 0 BLOCKING / 1 new WARNING (R-W1) / 0 NIT. W2, W3, N1, N2 and N3 are closed. W1 (identity on upgrade, devel check owed) and W4 (now DEF-025) carry over unchanged. N4 (closure candidates for adapter issues #36, #40, part of #26) still stands for the orchestrator.

The W3 merge is correct in the shipped code. Each object now sends one
properties call and one stats call per cycle. The Skip's -1 and Actual
text travel inside those calls, and nothing scored is dropped or
overwritten. The one new finding is about the tests, not the code. The
commit message says the source pins force every object push through
`pushObject`. They do not catch a separate skip push added back in
`afterPush` or in a new helper, and they do not catch the skip being
dropped on the profile-name-only path (non-vSAN cluster). I proved
each case with a mutant in a scratch copy: the code changed and
OverridesTest still passed.

### Independent verification

| Check | Result |
|---|---|
| Pak sha256 | matches the brief |
| `validate-sdk` | OK |
| `build-sdk` from HEAD (scratch output) | builds 0.0.0.92. All 173 entries in adapters.zip (nested jars included) and the 5 overview entries hash-identical to the author's pak. Only the archive wrappers differ (timestamps). describe.xml in the pak is byte-identical to HEAD. The jar contains `ComplianceDecisions$PushSink` and `$SkipPush`. Working tree clean afterwards. |
| `pak-compare` 92 vs 91 | gate PASS, 0 BLOCKING / 1 WARNING (identifier count 5 vs 6, the W1 removal) / 0 INFO. Unchanged from the first pass. |
| Dimension 13, my own parse of the built pak's describe.xml | 144 alerts, 152 symptom definitions, 7 `<SymptomSets>` containers with 2, 2, 2, 3, 2, 2, 2 children; all 152 `SymptomSet ref` values resolve to a defined symptom; `waitCycle` is 1, `cancelCycle` is 1 or 3, all integers. describe.xml is unchanged since `bdb49e6`. |
| Symptom keys | the fix commit changes no stat key: `compliantKey`, `K`, the Summary, `collection_failed` and `Rollup|incomplete` keys are untouched, and generator `--check` is up to date |
| `ci/run_java_tests.sh` | exit 0; all 13 Java suites pass (OverridesTest includes `skipRidesInObjectPush`; ComplianceRollupTest includes `build92RetiredCustom`); generator `--check` up to date; the 5 Python checks OK |
| `pytest` (adapter tests) | 33 passed, 11 subtests |
| Em-dashes in added lines | none |

### Prior findings

- **W2 closed.** `resources/resources.properties:31` (key 105) no longer
  has the custom-profile sentence; the shipped `resources.properties` in
  the pak matches. No stray custom-profile wording is left in
  `resources/`, `docs/`, README or REFERENCE except the intended
  build 92 removal notes.
- **W3 closed** (details below).
- **N1 closed.** `docs/overrides.md` "What happens to a skipped control"
  now says a Skip creates a -1 metric where the guide checks the control
  but it does not apply (a vSAN control on a non-vSAN cluster), that -1
  is not a pass, and that no alert fires on it. It matches the code:
  `collectVimObject` takes `emptyResult` for a non-vSAN cluster and
  `skipInForce` still returns the skip ids.
- **N2 closed** (details below).
- **N3 closed.** `ControlEvaluator.java:620` and `:653` comments now
  describe Override literals, not custom profiles. Comment-only.

### The W3 merge

Read in full: `ComplianceDecisions.pushObject` and `PushSink`
(`ComplianceDecisions.java:702-738`), `SkipPush` and `skipPush`
(`:666-700`), `complianceProps`, `complianceStats`,
`nothingEvaluatedStats`, `profileNameProps`, and in
`ComplianceAdapter.java` `skipInForce` (`:1054`), `afterPush` (`:1021`),
`pushOrProfileName` (`:1892`), `pushProfileNamePropertyOnly` (`:2110`),
`pushComplianceViaClient` (`:2144`), and the five call sites (host
`:1432`, VM `:1548`, vCenter `:1674`, dvs/dvpg/cluster `:1843`,
no-benchmark `:1008`).

- **One call of each per object.** `pushObject` makes exactly one
  `pushProperties` and one `pushStats` call. With a non-empty skip it
  copies both scored maps into new `LinkedHashMap`s and `putAll`s the
  skip maps. With null or an empty skip it passes the original maps
  through untouched. The properties map is never empty (it always has
  `profile_name`), so `ComplianceStitcher.pushProperties`'s empty-map
  guard never removes a call.
- **No key collision.** The skip keys are `K + id + "|Compliant"` and
  `K + id + "|Actual"`. A scored key for the same id would need the id
  in `cr.controlResults`. `cr` is evaluated against the adjusted profile,
  and `ComplianceOverrides.Resolved.adjust` (`ComplianceOverrides.java:631-635`)
  removes every control whose `controlId` is in `skipped` from every
  profile, with no version or kind scope. `ControlResult.scgId` is
  `Control.controlId` (`BenchmarkProfile.java:267`). The summary keys
  (`score`, `pass_count`, ...) are not control ids. So the two key sets
  are disjoint by construction. If they ever did collide, the skip's -1
  would win, which fails toward "not evaluated", never toward a pass.
- **No dropped scored stat.** Nothing is removed from either map.
  `skipRidesInObjectPush` asserts every scored stat survives and that the
  merged sizes equal the sums (mutant m5, which builds the stats map
  without the scored keys, fails it at line 702).
- **Profile-name-only shape.** `pushProfileNamePropertyOnly` sends
  `profileNameProps` plus `nothingEvaluatedStats` through `pushObject`.
  With no skip, that is the same two payloads build 91 sent. With a skip,
  the -1 and Actual ride in the same two calls. No score is pushed
  (no sentinel), as before.
- **Call count unchanged from build 91 for objects with no Skip.**
  Build 91 (`4fa180a`) had 13 direct `stitcher.push*` calls in
  `ComplianceAdapter.java`. HEAD has 9, plus the two `pushObject`
  calls that replace the 4 direct calls in `pushComplianceViaClient` and
  `pushProfileNamePropertyOnly`. Every per-object path still makes 2
  calls. The version-unreadable and no-benchmark paths are unchanged
  and have no benchmark, so there is no skip to carry (`skipInForce`
  returns null when `d.profile == null`, which matches the build 92
  first cut).
- **Cleanup and logging.** `afterPush` still adds the skip ids to the
  live set, so the end-of-cycle cleanup leaves them alone, and still
  increments the counters behind the per-cycle INFO line (`:505-510`).
- **Ordering and failure.** The skip now shares the scored push's
  timestamp. A push exception behaves as it did for the scored payload
  in build 91; the merge adds no new throw.

### Do the source pins catch a separate skip push coming back?

I copied the adapter to a scratch directory, applied each mutation, and
ran OverridesTest. Baseline: passes.

| Mutant | What it does | OverridesTest |
|---|---|---|
| m2 | `pushObject` sends the scored maps, then the skip maps as a second pair of calls | **fails** (line 690, call count) |
| m5 | `pushObject` drops the scored stats | **fails** (line 702) |
| m1 | `afterPush` makes its own `stitcher.pushProperties(resourceId, skip.props, ...)` and `pushStats(..., skip.stats, ...)` after `live.addAll(skip.ids)` | **passes** |
| m3 | a new helper `sendSkip(resourceId, skip)` with its own two `stitcher.push*` calls, called from `afterPush` | **passes** |
| m7 | `pushOrProfileName` passes `null` instead of `skip` to `pushProfileNamePropertyOnly` | **passes** |

The pins catch the original shape (the name `pushSkippedInForce`, a
`stitcher.` call inside `skipInForce`, or a direct push inside the two
push helpers) and any split inside `pushObject`. They do not catch
m1 or m3. Both bring back exactly the W3 cost: two extra Suite API
POSTs per object with a Skip, every cycle. They also do not catch m7.
m7 is worse than a performance regression. On a non-vSAN cluster, or
any object whose slice has nothing evaluable, the skip ids still join
the live set in `afterPush`, so the cleanup skips them and no -1 is
ever pushed. A key left at 0 from before (vSAN turned off, then the
control skipped) keeps its open alert forever. That is issue #41 back
on that shape. The current code is correct. The gap is that the tests
would let either regression ship green.

### N2: zeroing the retired Custom bucket

Read in full: `ComplianceConfig.isCustomName` and `storedAsCustom`
(`ComplianceConfig.java:69, 94`), `onConfigure` (`ComplianceAdapter.java:144`),
`pushRollup` (`:787-817`), `ComplianceRollup.toStats` (`:254-292`) and
`zeroRetiredCustom` (`:74-95`).

- **The key is right.** Build 91 named the Custom profile `Custom`
  (`BenchmarkLoader.java:168` at `4fa180a`) and `bucketOf("Custom")`
  returned `Custom`, so the build 91 key was
  `VCF-CF Compliance|Rollup|Benchmark|Custom|objects`, which equals
  `RETIRED_CUSTOM_KEY` (the test also pins it).
- **Held back on incomplete cycles.** `toStats` emits the
  `Benchmark|<bucket>|objects` keys only when no kind is incomplete, and
  `unknown` is a fixed bucket, so `Benchmark|unknown|objects` is present
  exactly on complete cycles. `zeroRetiredCustom` adds the 0 only when
  that key is present and returns false otherwise, so the flag stays set
  and the 0 goes out on the next complete cycle. Tested both ways in
  `build92RetiredCustom`.
- **Once.** The flag clears only after `stitcher.pushStats` returns. If
  the push throws, the 0 is retried next cycle. `onConfigure` sets the
  flag again on every configure (collector restart, account edit), so
  one more 0 goes out after each. That is harmless and matches the
  README wording ("once, on the first complete collection after it is
  configured").
- **Can it push 0 for an account never on Custom?** Not for an account
  whose stored profile is anything other than `Custom`: the flag comes
  only from `storedAsCustom`, which requires the raw stored value to be
  `Custom` (trimmed, any case), and build 92 no longer offers Custom for
  a new account. One edge: a build 91 account stored as Custom with an
  empty CSV path never loaded a Custom profile (`BenchmarkLoader.java:165`
  at `4fa180a` falls through to the bundled path), so its vCenter never
  had the key. Build 92 creates it at 0. Zero objects in a retired
  bucket is true, so this is not a finding.

### New finding

**R-WARNING 1** [`tests/com/vcfcf/adapters/compliance/OverridesTest.java`
`adapterWiringSourcePins`, about lines 1050-1105; dimension 9
(behavior-preservation proven, not asserted), skill § bulk-read dynamic
pattern] The commit message says "the source pins require every object
push to go through pushObject". Mutants m1, m3 and m7 show they do not.
A separate skip push added back in `afterPush` or a new helper (the W3
cost) passes, and so does dropping the skip on the profile-name-only
path (no -1 ever pushed, so a stale 0 keeps its alert open on a non-vSAN
cluster). Smallest fix, test-only, no build number change needed:
(a) `T.check(!body(ca, "private void afterPush(").contains("stitcher."))`;
(b) `T.check(!ca.contains("skip.props") && !ca.contains("skip.stats"))`,
and pin the count of `stitcher.pushProperties(` and `stitcher.pushStats(`
in `ComplianceAdapter.java` at today's 4 and 5 (the rollup, overrides
status, version-unreadable, cleanup and no-benchmark sites), so a new
helper shows up as a changed count; (c) `inOrder` on
`body(ca, "private void pushOrProfileName(")`: both branches pass
`profileName, skip);`. Re-run m1, m3 and m7 to confirm all three fail.
Not a registration candidate: no shipped behavior is wrong.

### Review dimensions, fix commit only

1, 3: the skip payload only ever carries -1 and the skip text; no path
turns a failed read into a pass. 2: no vim25 change. 4: no loader change.
5: no stitching or foreign-key change; `ComplianceStitcher` gained only
`implements PushSink` and two `@Override`s. 6: one new INFO line per
configure-and-zero; no secrets. 7: two short-lived map copies per object
with a Skip, discarded after the push. 8: W3 closed, per-object calls
back to 2. 9: build number stays 92 (never installed), CHANGELOG line
matches the diff, diff is minimal; R-W1 is the one gap in the proof.
10: no gap change. 11: README and overrides.md match the behavior.
13: describe unchanged, check repeated on the built pak, passes.

### Registry check (knowledge/context/defects.md)

- **DEF-023** (single-page resource list): still open, unchanged.
  `ComplianceStitcher.fetchResources` (`ComplianceStitcher.java:277`) is
  untouched by `bdb49e6..ddaf06e` (only the `implements` line and two
  `@Override`s changed). Still owed: devel proof of the paging, or of
  the vCenter collection alert path.
- **DEF-025** (retired control alert never cancels): still present,
  unchanged. `cleanBatch` (`ComplianceAdapter.java:1138`) still pushes -1
  once over a 0 (`zeroOnly`) or a 0 or 1 (`zeroOrOne`) and reads -1 back
  afterwards. The fix commit does not touch the cleanup. Not closable.
- DEF-022 and DEF-024 are closed; no other open defect names compliance.
- Registration candidates: none new. W1 becomes one only if the devel
  upgrade shows an identity problem.

### Devel verification still owed

Unchanged from the first pass: the section (a) identity checks first,
then the shell-timeout alerts cancelling within three cycles, the
per-cycle "skipped control key(s) set to -1" INFO line, the lockout
override and VM pin still in force, and no Custom in the profile
dropdown. Add one check for W3: the Suite API call rate from the
collector does not rise after the upgrade with a Skip in force. For an
account still stored as Custom, look for the "set to 0 once" INFO line.
