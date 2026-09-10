# Framework review round 4: PR #141 (`pr/summary-dashboard-tooling`) @ `097c175`

Fourth pass. Companions: round 1
(`summary-dashboards-crossref-pr141-2026-08-27.md`, CHANGES REQUESTED, 2
BLOCKING / 4 WARNING / 3 NIT), round 2 (`...-round2.md`, CHANGES REQUESTED, 1
BLOCKING / 1 WARNING / 1 NIT), round 3 (`...-round3.md`, CHANGES REQUESTED, 1
BLOCKING / 0 WARNING / 1 NIT).

Two commits since round 3:

- `fe20202` (tooling) - the round-3 BLOCKING fix: `crossref.py` + tests + docs
- `097c175` (orchestrator) - commits the three review reports into the PR record

**Verdict: APPROVE.** 0 BLOCKING / 3 WARNING / 2 NIT.

The round-3 BLOCKING is closed, verified by my own probes rather than by report.
Three WARNINGs are open; none is a merge blocker and none is introduced by
`fe20202`. Two of them are pre-existing defects this review found while
answering the questions round 4 was asked, and both deserve follow-up issues.
One record correction is owed by round 3 and one by tooling; the corrected
figure is stated below.

## Checks re-run independently

| Check | Result |
|---|---|
| Seven-package validate chain | rc=0, 5 Tier 1 valid, 6 of 6 Tier 2 `OK`, zero INVALID |
| pytest full (`-m ""`, the CI invocation) | **1501 passed, 7 skipped, 0 failed** in 727s |
| Test-count delta for `fe20202` | `test_supermetric_crossref_resolution.py` 38 -> **48** collected = **+10**, matching 1491 -> 1501 exactly |
| Render regression, bundles (`30b8933` vs `097c175`) | **content-identical**: 12/12 and 19/19 members, zero differing, nested zips descended and `built_at` stripped |
| Render regression, corpus dashboards + views (PR base `fd926d0` vs `097c175`) | clean, once per-run widget-id noise is accounted for (WARNING 2) |
| Build nondeterminism, two builds on identical code | reproduced and fully explained (below) |
| Mis-cased-token corpus sweep | **38 occurrences of `@supermetric`, all exactly lowercase, zero mis-cased** anywhere in `content/`, `bundles/`, `reference/references/` or the six pak clones. `fe20202` is behaviourally inert on today's corpus |
| Malformed-token sweep, all built artifacts | 11 zips in the PR #142 `dist/` tree, nested zips descended: **zero** surviving `@supermetric` literals (case-insensitive), **zero** doubled prefixes, **zero** malformed `Super Metric\|` tokens |
| `CURRENT_TEMPLATE_VERSION` | correctly unbumped for `fe20202`; round-1 disposition for the PR as a whole stands (see below) |
| pak-compare | n/a (read-only gate, no pak built) |

## The question round 4 was asked: is the wider fix the right call?

`fe20202` did both fixes, not the one-line guard round 3 specified.
**I agree with the wider fix, and round 3 explicitly sanctioned it** ("Making
`SM_CROSSREF_RE` case-insensitive on the token as well would be symmetric with
the prefix and is a reasonable second step"). It is not scope creep against my
own ask. On the merits:

**It does not institutionalise a spelling.** The authoring guidance is unchanged
and still teaches exactly one spelling.
`.claude/skills/vcfops-supermetric-dsl/SKILL.md:176-179` shows only
`@supermetric:"..."` as correct, and every one of the 38 occurrences in the
corpus and the pak clones is lowercase. The resolver became *forgiving*; the
documentation did not become *permissive*. That is the right shape: be liberal
in what you accept, be exact in what you teach.

**The alternative was strictly worse.** The guard alone converts a silent ship
into a loud error, which closes the P1, but leaves the author with a hard
failure over one capital letter and no way for any factory gate to help, because
`vcfops_packaging.deps._is_sm_ref` will never flag it. Resolving is the same
safety with none of the dead end.

**It cannot bind wrong.** The forgiveness is confined to the token. Verified
directly:

```
map = {"Super Metric": "abc-123", "SUPER METRIC": "zzz-999"}

@supermetric:"Super Metric"   -> Super Metric|sm_abc-123
@SuperMetric:"Super Metric"   -> Super Metric|sm_abc-123
@SUPERMETRIC:"Super Metric"   -> Super Metric|sm_abc-123
@SuPeRmEtRiC:"Super Metric"   -> Super Metric|sm_abc-123

@supermetric:"super metric"   -> RAISE (unresolvable)      <- name case is exact
@supermetric:"SUPER METRIC"   -> Super Metric|sm_zzz-999   <- its own distinct SM
```

Two super metrics whose names differ only by case stay distinct, and a name
that differs only by case from an existing SM fails as unresolvable rather than
binding to the wrong one. This is the property that matters, it is the property
the `6c59f6b` escape violated in the localizationKey case, and it holds.

**The whole of the orchestrator's probe reproduces exactly**, including the
prefix-plus-mis-cased-token combinations
(`Super Metric|@SuperMetric:"X"`, `SUPER METRIC|@SUPERMETRIC:"X"`) collapsing to
a single `Super Metric|sm_<uuid>`, the three near-misses raising
(`@SuperMetric: "X"` with a space, `@SuperMetric:X` unquoted,
`@supermetric:"nope"` unknown), and `cpu|usage_average` plus an already-resolved
term passing through untouched. `has_crossref` and `crossref_names` follow
`SM_CROSSREF_RE`, so `discrete_builder._expand_sm_crossrefs` (which calls
`crossref_names`) transitively pulls referents for a mis-cased token too:
consistent, not a new hole.

## The question round 4 was asked: is `_is_sm_ref`'s lowercasing still a blind spot?

**For the SM-formula form (`@supermetric:`), it is now consistent.** The audit
skips a mis-cased token because it genuinely is an SM reference, and the emit
path now guarantees that reference either resolves or hard-errors. Skipping it
is correct rather than blind. `fe20202` closes this exactly.

**For the view-column form (`supermetric:`), it is still a blind spot, and it is
the identical silent-ship defect one path over.** This is WARNING 1. It is
pre-existing (predates the PR base) and out of this PR's diff, so it does not
block, but it is now the last remaining instance of the pattern.

## WARNING

### 1. The view-column `supermetric:"<name>"` form silently ships the literal when mis-cased (pre-existing, not this PR)

`src/vcfops_dashboards/render.py:619` and `src/vcfops_packaging/deps.py:126`.

`render.py:619` tests `raw.startswith('supermetric:"')` case-sensitively.
`deps._is_sm_ref` lowercases before comparing, so the auditor classifies the
mis-cased form as an SM reference and skips it. Same two gates, same green,
same silent ship as round-3 BLOCKING A. Reproduced end to end on real content
(`content/views/cluster_storage_trend.yaml`, only the token case varied, SM
scope supplied):

```
supermetric:"..."   -> attributeKey="Super Metric|sm_ed7f2861-7814-4d68-87ab-584de31fc4e7"
SuperMetric:"..."   -> attributeKey="SuperMetric:&quot;[VCF Content Factory] Cluster - Disk Usage % (percent)&quot;"
SUPERMETRIC:"..."   -> attributeKey="SUPERMETRIC:&quot;[VCF Content Factory] Cluster - Disk Usage % (percent)&quot;"
```

No exception, no warning, rollUpType silently becomes `AVG` instead of `NONE`,
and the column renders blank in the UI. The audit skips it, `validate` has no
opinion, the zip is written. `_is_sm_ref` returns `True` for
`supermetric:"X"`, `SuperMetric:"X"` and `SUPERMETRIC:"X"` alike (verified).

**Provenance: pre-existing.** The `render.py` block dates to `30b025e`
(2026-07-09), and the `deps.py` lowercase view-form comparison predates the PR
base `fd926d0`. `git diff` confirms neither line is in this PR's diff.
**Not a merge blocker for PR #141** under the standard round 3 set (introduced
by this PR = BLOCKING; inherited = finding). But it is the same class as both
named escape anchors and it should get a follow-up issue: make
`render.py:619`'s prefix test and its `re.match` case-insensitive, and add the
mis-cased form to the loud-error path. One line each, and the same reasoning
already written into `crossref.py`'s comments applies verbatim.

### 2. Rendered dashboard widget ids are nondeterministic per process, and this PR extends the scheme to a new path

`src/vcfops_dashboards/render.py:1375` (new in `165c6f9`) and `:1432`
(pre-existing).

```python
"id": f"extModel{abs(hash(widget_id)) % 100000}-{seq}",
```

`hash()` on a `str` is salted per interpreter process (`PYTHONHASHSEED` is not
pinned anywhere in `src/`, `.github/` or `.claude/settings.json`), so the id
changes on every run. The comment on the pre-existing line calls it a
"Stable per-widget, per-sequence ID"; that is false across processes. Proven on
a real emitted artifact, not just in the abstract: two consecutive
`python3 -m vcfops_dashboards package` runs on identical code produce
dashboards whose 9 `extModel` ids share no value.

```
pk1.zip ids: 9  [extModel15812, extModel19574, extModel33285, extModel40740, ...]
pk2.zip ids: 9  [extModel1409,  extModel24642, extModel39695, extModel51773, ...]
```

Consequences, in order of how much they matter:

- **It defeats dimension 5, the render-regression gate, on the standalone
  content-import path** - the exact path where both named escapes hid. A
  byte-comparison of two dashboard zips can never be clean for any dashboard
  using Scoreboard, MetricChart or the new gauge/resource-mode widgets, so real
  drift in those widgets cannot be distinguished from id churn by the check the
  factory relies on to catch it.
- It makes distribution zips non-reproducible, so "rebuild and diff" is not
  available as a staleness check for dashboards.
- Functionally benign today: the ids are opaque, unique within the document,
  not cross-referenced, and not UUIDs (RULE-007 does not reach them).

**Scope, stated honestly.** The scheme is pre-existing. This PR *copies* it into
the new `_render_resource_metric_spec` (the gauge / resource-mode path), so it
extends the surface without introducing the class. **Not a merge blocker**, on
the same standard as WARNING 1.

**It also bounds every "byte-identical render" claim on this PR, including
mine.** The two bundles under test (`vks-core-consumption-bundle`,
`storage-path-monitoring`) contain **zero** `extModel` ids, which is why those
comparisons were clean and why the claim is sound *for those bundles*. It does
not generalise. Fix, for the follow-up issue: derive the id from a stable digest
(`int(hashlib.sha1(widget_id.encode()).hexdigest()[:8], 16) % 100000`) instead
of the builtin `hash()`, and correct the comment.

### 3. No test pins the invariant that the referenced SM *name* stays case-sensitive

`tests/test_supermetric_crossref_resolution.py`, `TestTokenCaseInsensitivity`.

The new class covers the four token spellings, the mis-cased unresolvable name,
and an end-to-end pass through `_render_supermetrics_dict`. It does **not**
assert the boundary of the new forgiveness: that
`@supermetric:"super metric"` does *not* resolve to the SM named
`Super Metric`. I verified that it holds today (above), so this is not a defect.
It is an unpinned invariant on a regex that just acquired an inline `(?i:)`.
The obvious future edit (someone converting
`re.compile(_PREFIX_SRC + r'''*(?i:@supermetric):...''')` to
`re.compile(..., re.I)` for readability) would silently make the *name* case
insensitive, at which point two SMs differing only by case collide on one
resolution. That is the `6c59f6b` key-collision class exactly, and it would pass
every test in the file. One parametrized case would prevent it:

```python
with pytest.raises(SuperMetricCrossRefError):
    resolve_sm_formula(f'...metric=@supermetric:"{REF_NAME.lower()}"...',
                       CONSUMER_NAME, {REF_NAME: REF_UUID})
```

## NIT

### 1. The doc explains the tolerance but does not name the canonical spelling

`knowledge/context/authoring/uuids_and_cross_references.md`, the new paragraph
"The token itself is case-insensitive, like the prefix." It is accurate and the
two previously-false sentences are now true as written. It stops one sentence
short of saying which spelling to *write*. SKILL.md carries that by example
(lowercase only, and it is untouched, which was the right call), so nothing is
wrong; a clause such as "write it lowercase, the tolerance is a safety net and
not a style choice" would close the gap.

### 2. The extractor's SM-rename rewrite is still case-sensitive

`src/vcfops_extractor/extractor.py:2069`,
`_sm_ref_rewrite_re = re.compile(r'@supermetric:"([^"]+)"')`. Now that a
mis-cased token is legal authoring syntax, a rename sweep will skip
`@SuperMetric:"Old Name"` and leave the stale name behind. The outcome is loud
(the next emit raises "could not be resolved"), not silent, so this is a NIT
rather than a WARNING. Pre-existing, out of this PR's diff.

## The two verification items round 4 was asked to check

### 1. The nondeterminism: the two accounts are the same phenomenon, and nothing is hiding inside it

Confirmed, and pinned to the byte. Two builds of both bundles on identical code
(`097c175`), raw member hashes:

```
storage-path-monitoring        raw-differing: 1  [vcfops_manifest.json]
vks-core-consumption-bundle    raw-differing: 4  [Dashboard.zip, Reports.zip,
                                                  Views.zip, vcfops_manifest.json]
```

Both causes identified directly rather than inferred:

- `vcfops_manifest.json`: the `built_at` field, `2026-08-27T22:50:23Z` vs
  `2026-08-27T22:50:39Z`. Nothing else in the JSON differs.
- The three nested zips: **identical CRCs, different entry mtimes**. Every entry
  in `Dashboard.zip` carries CRC `1268953776` for `dashboard/dashboard.json` in
  both builds, with `date_time` `(2026,8,27,17,50,22)` vs
  `(2026,8,27,17,50,38)`. The container bytes differ because the archive stores
  the timestamp; the payload is identical.

Descending into the nested zips and stripping `built_at`, **zero of 12 and zero
of 19 members differ**. Same result comparing `097c175` against `30b8933`
(the round-3 tree): **content-identical**. Round 3's account and tooling's
account are the same phenomenon; nothing real is hiding inside it.

One correction to tooling's description: it lists `dashboard.json` among the
differing members. The flattened `content/dashboard.json` is **not** raw-
differing in my runs; what differs is the nested `Dashboard.zip` *container*.
Immaterial to the conclusion, but the record should say container, not payload.

### 2. The bundle sweep: 70 occurrences / 13 distinct, and both prior figures were wrong in exactly one field each

Both numbers were checkable against a single artifact, so I counted it directly:
`/home/scott/claude/vcf-content-factory/.claude/worktrees/pr142/dist/vcf-license-consumption-overview.zip`,
matching `Super Metric\|sm_[0-9a-fA-F-]{36}`, descending into nested zips.

| Member | Occurrences | Distinct |
|---|---|---|
| `Views.zip!content.xml` | 16 | 10 |
| `Dashboard.zip!dashboard/dashboard.json` | 11 | 11 |
| `supermetric.json` | 8 | 6 |
| `content/views_content.xml` (flattened duplicate) | 16 | 10 |
| `content/dashboard.json` (flattened duplicate) | 11 | 11 |
| `content/supermetrics.json` (flattened duplicate) | 8 | 6 |
| **Archive total** | **70** | **13** |

**The record should carry 70 occurrences / 13 distinct.** Both divergences are
arithmetic, and both are now explained:

- **Round 3's "35 distinct" is wrong; it is my error.** 35 is `16 + 11 + 8`, the
  sum of the three non-flattened members' *occurrence* counts, mislabelled as a
  distinct count in the table's caption. The 70 total in that same table is
  correct. Round 3's sentence "35 distinct SM references, 70 occurrences" should
  read "13 distinct SM references, 70 occurrences".
- **tooling's "43 occurrences" is wrong; it does not descend into the nested
  zips.** 43 is `16 + 11 + 8` (the flattened `content/` copies) `+ 8`
  (top-level `supermetric.json`); the 27 occurrences inside
  `Views.zip!content.xml` and `Dashboard.zip!dashboard/dashboard.json` are
  missing. Those are the members VCF Ops actually imports, so they are the ones
  that must be counted. tooling's **13 distinct is correct**: distinct is
  insensitive to the omission, because the nested members carry the same tokens
  as their flattened duplicates.

The same explanation holds for the whole-tree figure. Sweeping the PR #142
`dist/` tree with nested descent:

```
  24 occ   5 distinct  ThirdPartyContent/dashboards/idps-planner-3.5.zip
   6 occ   2 distinct  bundles/storage-path-monitoring.zip
  22 occ   8 distinct  bundles/vks-core-consumption-bundle.zip
  32 occ  13 distinct  dashboards/capacity-assessment-dashboard.zip
   6 occ   2 distinct  dashboards/cpu-support-status-dashboard.zip
   0 occ   0 distinct  dashboards/demand-driven-capacity-v2.zip
   2 occ   1 distinct  dashboards/quarterly-capacity-review-dashboard.zip
  22 occ   8 distinct  dashboards/vks-core-consumption-dashboard.zip
   4 occ   2 distinct  dashboards/vm-snapshot-inventory-dashboard.zip
  22 occ   8 distinct  reports/vks-core-consumption-report.zip
  70 occ  13 distinct  vcf-license-consumption-overview.zip
  ---
  11 zips, 210 occurrences, 46 distinct
```

tooling's **46 distinct is correct**. Its 146 occurrences undercounts by the
same nested-zip omission, and its "13 zips" should be **11** (that is every
`*.zip` in the tree; the nested `Views.zip` / `Dashboard.zip` / `Reports.zip`
are members, not tree entries). **Correctness of the substantive claim is
unaffected**: with nested descent across all 11 zips there are **zero**
surviving `@supermetric` literals in any case, **zero** doubled prefixes, and
**zero** malformed `Super Metric|` tokens.

## Rounds 1 to 3: nothing left open

| Round | Finding | Status at `097c175` |
|---|---|---|
| 1 | 2 BLOCKING | closed in round 2 / round 3, re-verified |
| 2 | B-A pak dependency unpublished | closed in round 3 against `origin/main`; unchanged |
| 2 | W-A prefix case/whitespace | closed in round 3 |
| 3 | B-A token case-sensitivity | **closed by `fe20202`**, verified by probe, corpus sweep and artifact sweep |
| 3 | N-1 `_DOUBLED_PREFIX_RE` breadth | recorded as an in-code comment by `fe20202`, exactly as asked |

**Dimension 9, staleness.** `fe20202` touches none of the bump triggers
(`templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`,
`render.py`), so `CURRENT_TEMPLATE_VERSION = "2026-08-24-2"` correctly stays put
for this commit. The PR as a whole does touch `builder.py`,
`discrete_builder.py` and `render.py`; round 1's disposition (output-inert,
proven by render hashes) stands, and I re-tested it this round by rendering the
whole corpus with the base `src/` and the HEAD `src/` against the *same* content
YAML: every view is hash-identical, and the only dashboards that differ do so
solely in their `extModel<N>` widget ids, which WARNING 2 proves change between
two runs of the *same* code. No existing dashboard or view YAML is modified by
this PR (`summary_widget_smoke.yaml` is the single addition), so no distributed
bundle's rendered content changes and no bump is owed. The PR body's
`content-packager` rebuild obligation is unaffected and still stands.

## If shipped as-is

Nothing in today's corpus breaks, and the specific hole round 3 opened this
gate on is shut on every path that emits an SM formula. All 38 `@supermetric`
occurrences in the repo and the pak clones are canonical lowercase, so
`fe20202` changes no rendered byte anywhere. The next author who types
`@SuperMetric:"..."` now gets a resolved reference instead of a green build and
a super metric that evaluates to nothing forever.

The residue an operator could still hit is WARNING 1: an author who types
`SuperMetric:"..."` in a **view column** (no `@`) gets exactly the old outcome,
a green build and a blank column, because the renderer's test and the auditor's
test disagree on case. That is a separate, pre-existing defect and it should be
an issue, not another round on this PR.

## On CI: precondition, not informative (restated, unchanged)

Green CI on `pr/summary-dashboard-tooling` is a **precondition for merge**, not
merely informative.

The branch still has no CI run of its own, and its code already failed CI once
through PR #142. Everything in this report is a local reproduction of the CI
gates on one machine: my `pytest`, my Python, my describe cache, my clone state.
The global rule that "done means seen working, not pipeline green" makes
pipeline green *insufficient*, not *optional*, and here it is not present at
all. Merge after a green run on this branch at `097c175` or later.

## What round 5 would need (nothing, for this PR)

No BLOCKING findings. The three WARNINGs are follow-up issues, not re-work:

1. view-column `supermetric:` case-insensitivity (`render.py:619`, `deps.py:126`)
2. deterministic `extModel` widget ids (`render.py:1375`, `:1432`)
3. one parametrized test pinning SM-name case-sensitivity

Recommend opening 1 and 2 as issues before the next `render.py` change, and
folding 3 into whichever of them lands first.
