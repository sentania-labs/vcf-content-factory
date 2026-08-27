# Framework review round 3: PR #141 (`pr/summary-dashboard-tooling`) @ `30b8933`

Companion to `summary-dashboards-crossref-pr141-2026-08-27.md` (round 1,
CHANGES REQUESTED, 2 BLOCKING / 4 WARNING / 3 NIT) and
`summary-dashboards-crossref-pr141-2026-08-27-round2.md` (round 2,
CHANGES REQUESTED, 1 BLOCKING / 1 WARNING / 1 NIT).

One commit under review: `30b8933` (`crossref.py` + tests +
`uuids_and_cross_references.md`), plus re-verification of everything rounds 1
and 2 left open.

**Verdict: CHANGES REQUESTED.** 1 BLOCKING / 0 WARNING / 1 NIT.
The round-2 BLOCKING is genuinely closed. The round-2 WARNING is closed on the
prefix, and the identical defect one layer over, on the token itself, is the
new BLOCKING. The owed fix is one line.

## Checks re-run independently

| Check | Result |
|---|---|
| Seven-package validate chain | 7/7 rc=0, zero INVALID |
| Seven-package validate chain, pak repos at published `origin/main` | **5 Tier 1 valid, 6 of 6 Tier 2 `OK`**, rc=0 |
| pytest full (`-m ""`, the CI invocation) | **1491 passed, 7 skipped, 0 failed** in 642s |
| Test-count delta for `30b8933` | 23 -> 38 collected in `test_supermetric_crossref_resolution.py` = **+15**, matching 1476 -> 1491 exactly |
| Render regression (bundle rebuild `b2cb0fb` vs `30b8933`) | **content-identical**, all members incl. nested zips |
| Old-vs-new regex over the whole corpus | **102 formula lines, 0 behavioural differences, 0 doubled-prefix hits** |
| PR #142 bundle build `--strict-deps`, no `--skip-audit` | audit **10/10 resolved**; **35 distinct SM references, 70 occurrences**, all well-formed |
| `CURRENT_TEMPLATE_VERSION` no-bump | correct for this commit; `30b8933` touches no bump-trigger file |
| pak-compare | n/a (read-only gate, no pak built) |

Render-regression recipe: build `bundles/vks-core-consumption-bundle.yaml` and
`bundles/storage-path-monitoring.yaml` with `--strict-deps --no-live-describe`
at each tree, then SHA-256 every zip member, descending into nested
`Views.zip` / `Dashboard.zip` / `Reports.zip` and stripping `built_at` from
`vcfops_manifest.json`. The only raw-hash differences between the two trees are
nested-zip internal timestamps and that one manifest field. "Renders
byte-identical" holds.

PR #142 bundle recipe: scratch worktree of `origin/pr/vcf-license-consumption`
with this branch's `src/` overlaid in place (a `PYTHONPATH` overlay does **not**
work: `vcfops_packaging/describe.py:83` derives `_DEFAULT_CACHE_ROOT` from
`_REPO_ROOT`, which is resolved from the module file's own location, so the
build reads the *framework* tree's describe cache and fails the audit with
"No describe cache files for CASAdapter:CAS World...". Copy `src/` into the
content tree instead. Noting the recipe so round 4 does not rediscover it.)

## Round-2 findings: disposition

| # | Round-2 finding | Round-3 status |
|---|---|---|
| B-A | validate chain green only via unpushed/unmerged pak commits | **CLOSED**, verified against published `origin/main` |
| W-A | prefix absorption exact-case-and-spacing; docs claim more than the code delivers | **CLOSED on the prefix.** The same defect on the `@supermetric` token itself is BLOCKING A below |
| N-1 | surviving-`@supermetric` guard placement | **CLOSED**, folded into one block as asked |

### B-A, closed: the pak dependency is published

Verified independently rather than taken on report. In each clone I fetched
`origin/main` and compared SHAs directly:

- `content/sdk-adapters/vcommunity`: HEAD == `origin/main` == `95ed99c`
- `content/sdk-adapters/vcommunity-vsphere`: HEAD == `origin/main` == `2ebc967`

Both clones are on `main`, not a fix branch. `2ebc967` is the squash of PR #19
and its body carries both legs; leg 2 is the `VM Details` widget `f5b4a644`
change from a bare display name to
`viewDefinitionId: ae751947-1782-466f-b560-9a950be3c1f9`, which is the leg round
2 identified as missing. `python3 -m vcfops_managementpacks validate` against
that published state: 5 Tier 1 valid, all 6 Tier 2 `OK`, rc=0.

This finding was raised twice and is now genuinely closed. No further
sequencing constraint on the PR from the pak side.

### W-A, closed on the prefix

All seven probe classes reproduce exactly. Canonical, `Super Metric|`,
`super metric|`, `SUPER METRIC|`, `Super Metric| `, `Super  Metric  |  `, and
`Super Metric|Super Metric|` all collapse to exactly one
`Super Metric|sm_<uuid>`. `cpu|usage_average`,
`net:Aggregate of all instances|packetsPerSec`,
`vCommunity|Licensing:Evaluation Mode|Edition Key`, an already-resolved term,
and two separately-prefixed terms in one formula are all left untouched.
`Super Metric|Super Metric|sm_<uuid>` raises, and `@supermetric: "X"` and
`@supermetric:X` still raise.

No interaction with `_normalize_metric_key`: it lives in
`vcfops_packaging/deps.py`, never references `SM_CROSSREF_RE`, and `_is_sm_ref`
short-circuits SM references *before* normalization runs.

## BLOCKING

### A. The case-sensitivity defect just fixed on the prefix is still open on the token, and both of this PR's gates pass it through silently

`src/vcfops_supermetrics/crossref.py:71` and `:187`.

`_SM_CROSSREF_LITERAL = "@supermetric"` is compared with a case-sensitive `in`,
and `SM_CROSSREF_RE` matches `@supermetric:` case-sensitively. After `30b8933`
the *prefix* is `(?i:...)` but the *token* is not. Reproducible:

```
'${this, metric=@SuperMetric:"X"}'  ->  '${this, metric=@SuperMetric:"X"}'   no raise, no diff
'${this, metric=@SUPERMETRIC:"X"}'  ->  '${this, metric=@SUPERMETRIC:"X"}'   no raise, no diff
```

The literal authoring token ships verbatim into `supermetric.json`, into the
pak, and onto a live instance. That is precisely the P1 the module's own
docstring says it exists to eliminate: "emitting the literal token produces a
corrupt super metric that VCF Ops silently fails to evaluate, so failing loudly
at build/push time is strictly safer than shipping it."

**The dependency audit does not catch it either, and for the reason `30b8933`
itself cites.** `vcfops_packaging.deps._is_sm_ref` lowercases before comparing,
so it returns `True` for the mis-cased token, and `_refs_from_formula`
therefore *skips* it as "an SM reference, not a built-in metric":

```
@supermetric:"X"   _is_sm_ref = True
@SuperMetric:"X"   _is_sm_ref = True        <- audit treats it as an SM ref
Super Metric|sm_a  _is_sm_ref = True

_refs_from_formula('${adaptertype=A, objecttype=B, metric=@SuperMetric:"X"}')  ->  []
```

So the audit will not flag it as an unknown metric, the resolver will not match
it, and the survivor guard will not catch it. Audit green, build green,
`validate` green (the SM loader has no `@supermetric` awareness at all, by
design, as the context doc itself states), zip written, nothing reported. This
is the reports-green-while-broken class, aimed at an operator who cannot see the
repo.

**This is introduced by this PR, not inherited.** `crossref.py` is a new file in
PR #141. And `_is_sm_ref`'s lowercasing is the exact authority `30b8933` quoted
to justify loosening case on the prefix: "this codebase's own admission that
authored prefix case varies." That admission is made by a function that
lowercases the *token* on the line above the one that lowercases the prefix. The
fix stopped one line short of its own stated rationale.

**It also makes two shipped doc sentences false as written**, which was the
entire point of the round-2 WARNING:

- `knowledge/context/authoring/uuids_and_cross_references.md`: "Any literal
  `@supermetric` surviving substitution raises" - true only for exact lowercase.
- Same file: "it can never ship silently" - false for a mis-cased token.
- `.claude/skills/vcfops-supermetric-dsl/SKILL.md:186` "this cannot ship
  silently" claims only the *prefix* guarantee, and that one is now true as
  written. tooling's judgement that the SKILL.md needed no edit is correct.

**Smallest correct fix.** Make the survivor guard case-insensitive:

```python
if re.search(r"@supermetric", resolved, re.I):
```

That alone closes the silent-ship path: the author gets a loud error that names
the problem. Making `SM_CROSSREF_RE` case-insensitive on `@supermetric:` as well
would be symmetric with the prefix and is a reasonable second step, but the
guard is the minimum bar and the one that makes the two doc sentences true.
Add the mis-cased token to the parametrized hard-error test.

## NIT (accepted as-is, recorded so a future false positive is recognised rather than re-diagnosed)

### 1. `_DOUBLED_PREFIX_RE` is deliberately over-permissive and will fire on two constructed non-defects

`src/vcfops_supermetrics/crossref.py:68`. `_PREFIX_SRC` uses `\s*` between
"super" and "metric", which permits zero whitespace, so the doubled-prefix hard
error also raises on:

```
'${this, metric=Supermetric|Supermetric|x}'
'${this, attribute=summary|super metric|super metric|count}'
```

Neither is a plausible VCF Ops metric key, and neither exists anywhere: a
repo-wide sweep of `-iE 'super\s*metric\s*\|\s*super\s*metric'` across every
`*.yaml`, `*.yml`, `*.json` and `*.xml` in `content/`, `reference/references/`,
`bundles/` and all six `content/sdk-adapters/*` clones returns **zero hits**.

**Accepted as-is.** The permissiveness is the right trade: the false-negative
cost (an unparseable formula shipping silently) is far worse than the
false-positive cost (a loud error on a key nobody would write). Recorded here so
that if this error ever fires on something that looks legitimate, the reader
recognises the shape immediately instead of re-deriving it.

## Verified as claimed (skeptical checks that came back clean)

- **The near-miss guard is unchanged.** Same condition, same message; only the
  surrounding comment was renumbered when the two guards were merged into one
  block. Confirmed by diff and by probe. Its case hole is BLOCKING A above, not
  a regression from round 2.
- **The new hard error is a real behaviour change with zero corpus exposure.**
  tooling's sweep reproduces. Beyond the sweep, I ran the *old* regex and the
  *new* regex over all **102** `formula:` lines in the corpus and diffed the
  substitution results: **0 behavioural differences, 0 doubled-prefix hits**. No
  pak repo or third-party corpus in this tree can trip the new error.
- **"Hard error on every emit path" is true.** All four documented call sites
  plus the two feeders were checked, and **none** short-circuits on
  `has_crossref()`: every SM's formula goes through `resolve_sm_formula`
  unconditionally, so a token-less doubled prefix does reach the new guard.
  - `vcfops_packaging/builder.py:196` (`_render_supermetrics_dict`), which
    `discrete_builder.py:756` and `release_builder` both delegate to
  - `vcfops_supermetrics/client.py:601` (live sync)
  - `vcfops_managementpacks/sdk_builder.py:1890` (Tier 2 pak)
  - `vcfops_supermetrics/cli.py:88` and `handler.py:49` emit raw formulas but
    both feed `import_supermetrics_bundle`, which resolves.
  - `extractor.py` and `reverse.py` are ingest, not emit.
- **Test delta is exactly as claimed.** `test_supermetric_crossref_resolution.py`
  collects 23 at `b2cb0fb` and 38 at `30b8933`: **+15**, matching 1476 -> 1491
  precisely. Four new test functions, two of them parametrized.
- **Suite.** `pytest -m ""` (the CI invocation; the default
  `addopts = -m "not slow"` deselects 128) -> **1491 passed, 7 skipped, 0
  failed**, exit 0.
- **Dimension 9, staleness.** `30b8933` touches no file in the bump-trigger list
  (`templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`,
  `render.py`), so `CURRENT_TEMPLATE_VERSION = "2026-08-24-2"` correctly stays
  put for this commit. The round-1 disposition for `6abbdcd`'s `builder.py` /
  `discrete_builder.py` changes (output-inert, proven by render hashes) stands
  unchanged, and the PR body's owed `content-packager` rebuild is unaffected.

## The reference count, stated plainly

Round 2's brief said "16 references across both zip members". That was wrong and
the record should not carry it. **16 is the Views member alone.**

Rebuilt independently: scratch worktree of `pr/vcf-license-consumption` with
this branch's `src/` overlaid, `--strict-deps`, no `--skip-audit`, no live
instance. Audit: **10 references, 10 resolved `defaultMonitored=true`**,
reproducing tooling's number exactly.

`Super Metric|sm_<uuid>` occurrences in
`dist/vcf-license-consumption-overview.zip`:

| Member | Count |
|---|---|
| `Views.zip!content.xml` | **16** |
| `Dashboard.zip!dashboard/dashboard.json` | **11** |
| `supermetric.json` | **8** |
| `content/views_content.xml` (flattened duplicate) | 16 |
| `content/dashboard.json` (flattened duplicate) | 11 |
| `content/supermetrics.json` (flattened duplicate) | 8 |
| **Total** | **70** |

**35 distinct references, 70 occurrences** once the flattened `content/` copies
are counted. All **70** match `Super Metric\|sm_[0-9a-fA-F-]{36}` exactly: zero
malformed, zero doubled prefixes, zero surviving `@supermetric` literals
anywhere in the archive, including inside the nested zips.

## If shipped as-is

Nothing in today's corpus breaks. Every reference in the #142 bundle is
well-formed, the audit resolves 10/10, and the render is unchanged. The exposure
is forward-looking, narrow, and sharp: the next author who types
`@SuperMetric:"..."` gets a green build, a green audit, a green `validate`, an
installed super metric that evaluates to nothing forever, and no diagnostic
anywhere. That is the failure this module was written to make impossible,
reachable by one capital letter.

## On CI: precondition, not informative

Green CI on this branch is a **precondition for merge**, not merely
informative.

The branch has never had a CI run, and its code already failed CI once through
PR #142, so there is no observed-green evidence at any point in its history.
Everything recorded above is a local reproduction of the CI gates, which is
evidence about this machine, not about the pipeline that actually guards the
merge: my `pytest` invocation, my Python, my describe cache, my clone state. The
global rule that "done means seen working, not pipeline green" sets pipeline
green as *insufficient*, not as *optional*. Here it is not even present.
"I ran the same commands locally" does not substitute for it.

Require a green run on `pr/summary-dashboard-tooling` after the BLOCKING fix
lands, then merge.

## What has to change to clear this gate

One line: make the surviving-`@supermetric` guard case-insensitive
(`re.search(r"@supermetric", resolved, re.I)`). Optionally make
`SM_CROSSREF_RE` case-insensitive on the token for symmetry with the
now-case-insensitive prefix. Add the mis-cased token to the parametrized
hard-error test. Then both doc sentences are true as written and round 4 should
be quick.
