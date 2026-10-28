# Synology build 33 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/synology` (repo `sentania-labs/vcf-content-factory-sdk-synology`)
- **Branch reviewed:** `fix/41-load-average-scale`, tip `4188969`, one commit on `main` `acbd2a2`. Read as checked out, tree clean before and after the review.
- **Fork issue:** #41 (DSM load averages are x100)
- **Evidence cited by the build:** `knowledge/context/investigations/2026-10-16-synology-32-devel-9-1-proof.md` item 4 (committed), `knowledge/context/api-maps/synology-system.md` cpu object (committed)
- **Date:** 2026-10-18
- **Verdict:** APPROVE (0 BLOCKING, 1 WARNING, 3 NIT). Round 2 (below, commit `50e9c92`): APPROVE (0 BLOCKING, 0 WARNING, 1 new NIT).

## Bottom line

The fix is correct and ships safely. The three load averages go through one
helper that divides by 100 exactly once, a real 0 is still published as 0,
and a field DSM did not send is skipped instead of published as 0. The
describe.xml, keys, display names and (absent) unit are byte-identical to
build 32, and pak-compare is 0/0/0. The one warning is a regression guard:
the helper is well tested, but nothing pins the adapter to call it, so
reverting the three lines to raw, dividing twice, or reading the wrong field
all pass the full test runner.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh` passes | Confirmed: 16 Java + 8 Python, all "all assertions passed". |
| validate-sdk OK | Confirmed: `OK: content/sdk-adapters/synology is a valid Tier 2 SDK adapter project`. |
| build-sdk produces `vcfcf_sdk_synology_diskstation.0.0.0.33.pak` | Confirmed, rebuilt to a scratch dir. My `synology_diskstation.jar` classes are identical to the author's `dist/` pak. Adapter tree still clean after the build. |
| pak-compare 0/0/0 vs build 32 | Confirmed: `0 BLOCKING, 0 WARNING, 0 INFO` against `dist/vcfcf_sdk_synology_diskstation.0.0.0.32.pak`. |
| Keys, names, unit unchanged | Confirmed: `conf/describe.xml` in the 33 pak is identical to the 32 pak; `cpu_load_1m/5m/15m` nameKeys 31/32/33, no `unit`; resources.properties 31..33 = "Load Average (1 min / 5 min / 15 min)". The only conf diff is `version.txt` `Implementation-Version=0.32` to `0.33` (same format as build 32). |
| No alerts or symptoms touched (dimension 13) | Confirmed; describe unchanged. |

Bytecode check: `SynologyMetrics.loadAverage` is `num(...)`, null passes
through, else one `ddiv 100.0`. `SynologyAdapter` references `loadAverage`
exactly three times, all in `collectDiskstation`.

Mutation pass (fresh copies, full runner):

| Mutation | Result |
|---|---|
| M1 remove the `/ 100.0` | CAUGHT (MetricsTest "API map 1 min") |
| M2 absent returns 0.0 | CAUGHT ("absent: not published, not 0") |
| M5 treat 0 as absent | CAUGHT ("an idle NAS: a real 0") |
| M3 adapter `cpu_load_1m` back to `metric(..., cpu.get("1min_load").asDouble())` | SURVIVED |
| M4 adapter divides `cpu_load_5m` a second time | SURVIVED |
| M6 adapter `cpu_load_15m` reads `5min_load` | SURVIVED |

## The questions in the brief

- **Division exactly once, no double path.** Yes. `SynologyMetrics.java:91-95`
  is the only division; `SynologyAdapter.java:837-842` is the only publisher
  of the three keys (grep of src and tests; no stitcher, ComputedMetrics or
  other path touches them). No factory content (`content/`, `bundles/`,
  `third_party/`) references the keys. Not pinned by a test: see W1.
- **Skip-when-absent does not swallow a real 0.** Yes. `num()` returns null
  only for a missing/JSON-null node, a non-numeric string, NaN or infinity.
  Numeric 0 renders as `"0"` via `SimpleJson.asString()` and parses to 0.0,
  then 0.0 / 100 = 0.0 is published (test "an idle NAS: a real 0", M5
  caught). `cpu` itself cannot be a Java null in production: `SimpleJson.get`
  returns a null-object node, and the snapshot already throws when
  `Utilization.get` has no `cpu` (`SynologyAdapter.java:1529`), so a hollow
  payload is ERROR, not a set of skipped keys.
- **CHANGELOG under an unreleased 0.0.0.33 heading (RULE-014).** Yes,
  `## 0.0.0.33 (Unreleased)`, with the "1.0.0 line unchanged until a
  `v1.0.0.33` tag" sentence. Build 32 is also still "(Unreleased)", which is
  accurate: the newest tag is `v1.0.0.30`.
- **Upgrade note honest about the 100x step.** Yes. It says values drop by
  100, history before the build is 100 times the real load, charts show a
  step, thresholds on these keys need re-checking, keys/names/unit
  unchanged. See N2 on one REFERENCE.md phrase.
- **No em-dash added.** No authored line adds one. The single `+` line that
  contains an em-dash is the regenerated `docs/inventory-tree.md` header
  (the "Do not edit, regenerated on every build" notice), which carried the
  same em-dash in build 32; see N3.

## Findings

### BLOCKING

None.

### WARNING

**W1. The adapter's use of `loadAverage` is not pinned by any test.**
Authority: skill § *Unreadable is NOT compliant* (a missing read must
provably skip), author hard rule on proving behavior; build 32 review W3
precedent (wiring guards in `test_collect_wiring.py`).
`SynologyAdapter.java:837-842`. M3, M4 and M6 above all pass the full
runner: an edit that restores the raw `asDouble()` read (100x values and 0
on absent), divides twice (values 10,000 times too small), or crosses the
fields would ship green. The brief's "cannot be applied twice on any path"
holds today only by inspection.
Fix: in `tests/test_collect_wiring.py`, for each of the three
(key, field) pairs assert
`metricIfPresent(out, "CPU|<key>",\s*SynologyMetrics\.loadAverage\(SJ, cpu, "<field>"\)\);`
and `ADAPTER.count('"CPU|<key>"') == 1`, matching the existing
`memory_usage_pct` guard.

### NIT

**N1. "Confirmed" overstates the evidence slightly.** Authority: RULE-002
spirit / evidence over labels. Build 32's comment deferred the division
"until devel compares them with /proc/loadavg". The proof did not read
`/proc/loadavg`; it inferred x100 from 473 at 98 % CPU on 4 cores and 13 at
0 % idle. The inference is strong and I accept it, but the comment at
`SynologyAdapter.java:831` and the CHANGELOG say "confirmed". Either soften
to "established by" or have the build 33 devel proof record one side-by-side
against a run-queue reading (DSM Resource Monitor or `/proc/loadavg`).

**N2. REFERENCE.md history sentence names only the 0.x line.**
`REFERENCE.md:69`: "Builds up to 0.0.0.32 published DSM's value as sent".
Operators on the release line (`v1.0.0.30` and earlier) also have 100x
history. The CHANGELOG wording ("history collected before this build") is
correct; align REFERENCE.md, e.g. "Every build before 0.0.0.33, including
the 1.0.0.x releases, published...".

**N3. Generator-owned em-dash (factory tooling, not the author).**
`docs/inventory-tree.md:1` and `:3` come from the factory's docs generator
under `src/vcfcf_*/`; every build re-emits them. Not introduced by this
diff. Candidate for a `tooling` issue so generated pak docs stop carrying
em-dashes.

## Dimension walk

1. Cardinal: improved. A missing load field was 0.0 published; now skipped. Real 0 preserved. Hollow `cpu` still throws upstream.
2. vim25: not applicable (DSM JSON). No throw path added; `num()` catches `NumberFormatException`.
3. Exceptions: none added; no empty catch.
4. Canonical loader: not applicable.
5. Stitching identity: untouched.
6. Logging: no logging added. A skipped key is silent, same as the build 32 memory keys; acceptable.
7. Memory/resources: no new state.
8. API discipline: no new calls.
9. Hygiene: `build_number` 33, CHANGELOG line, minimal diff (8 files, the docs changes are generated version stamps). No drive-by changes.
10. Gap honesty: no gap; evidence cited and committed (RULE-015).
11. Docs parity: REFERENCE.md documents the scale and skip; README.md lists "load averages" without a scale claim; overview.md and docs/README.md say nothing contradictory.
12. Registry: see below.
13. describe import rules: describe unchanged from build 32.

Out-of-scope observation (not a finding, not in the diff): the neighbouring
`cpu_user_pct`, `cpu_system_pct` and `cpu_total_load` still publish
`asDouble()` (0 when absent), like build 32 N7 for memory. Worth a fork
issue if the skip-when-absent pattern is meant to cover the whole CPU group.

## Registry check (knowledge/context/defects.md)

No open defect has `Affects: synology` (DEF-001, -003, -005, -006 are
closed). `defect-gate --pak synology`: "no open blocking defects affecting
synology". No new finding is a registration candidate; W1 is a test gap,
not shipped behavior.

## If shipped as-is

Operators see load averages at their real scale (about 4.7 on a busy 4-core
NAS instead of 473), a one-time step down in charts at the upgrade, and no
false 0 when DSM omits a value.

## Round 2 (commit 50e9c92 on 4188969)

- **Date:** 2026-10-18
- **Diff:** `git diff 4188969..50e9c92`, 5 files (+22 / -9): `tests/test_collect_wiring.py`, comment and javadoc wording in `SynologyAdapter.java` and `SynologyMetrics.java`, `CHANGELOG.md`, `REFERENCE.md`. The two Java edits are comment-only; no executable code changed.
- **Verdict:** APPROVE (0 BLOCKING, 0 WARNING, 1 new NIT)

### Re-run

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | Pass: 24 of 24 "all assertions passed" (16 Java + 8 Python). |
| validate-sdk | `OK: ... is a valid Tier 2 SDK adapter project`. |
| Em-dash in added lines | None. |
| Adapter tree | Clean before and after. |

build-sdk and pak-compare were not re-run: the commit changes only Java
comments, a Python test and markdown, so the shipped classes and
describe.xml cannot differ in behavior from the round 1 pak (0/0/0 vs
0.0.0.32). A rebuild for the release pak is still the author's step.

### Mutation pass (fresh full-tree copies, full runner)

| Mutation | Result |
|---|---|
| M0 baseline, unmodified | passes |
| M3 `cpu_load_1m` back to `metric(..., cpu.get("1min_load").asDouble())` | CAUGHT: "CPU\|cpu_load_1m is not published through loadAverage from 1min_load" |
| M4 `cpu_load_5m` divided a second time | CAUGHT: "CPU\|cpu_load_5m is not published through loadAverage from 5min_load" |
| M6 `cpu_load_15m` reads `5min_load` | CAUGHT: "CPU\|cpu_load_15m is not published through loadAverage from 15min_load" |
| M7 the `cpu_load_1m` publish line duplicated verbatim | CAUGHT: "CPU\|cpu_load_1m is published somewhere else too" |
| M8 a second, raw `metric(out, "CPU\|cpu_load_1m", ...asDouble())` added | CAUGHT: "published somewhere else too" |
| M9 a second publish with the key built by concatenation, `"CPU\|" + "cpu_load_1m"` | SURVIVED |

### Round 1 findings

- **W1 closed.** The guard pins each key to `loadAverage(SJ, cpu, "<own field>")` with nothing between the call and `);`, and counts each key literal once. M3, M4, M6 and the exactly-once mutations M7 and M8 now fail the suite.
- **N1 closed.** The comment (`SynologyAdapter.java:831-836`), the javadoc and the CHANGELOG now say "derived" and state it was not compared against /proc/loadavg.
- **N2 closed.** REFERENCE.md and the CHANGELOG upgrade note both name v1.0.0.30 and earlier releases.
- **N3 unchanged, by design.** It belongs to factory tooling, not the author.

### New NIT

**R2-N1.** The exactly-once guard counts the full `"CPU|<key>"` literal, so
a second publish that builds the key another way (M9: concatenation, or a
constant) gets past it. That is a contrived edit and the existing
`memory_usage_pct` guard has the same limit, so it does not block. To
close it, count the bare key with its closing quote (`cpu_load_1m"`)
instead of the full literal.

### Registry

Unchanged: no open defect in `knowledge/context/defects.md` affects synology.
