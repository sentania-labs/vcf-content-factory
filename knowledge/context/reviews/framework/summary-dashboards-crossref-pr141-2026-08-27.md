# Framework review: PR #141 (`pr/summary-dashboard-tooling`), 2026-08-27

RULE-013 blanket gate before merge. Two scopes reviewed separately.

- **Scope A** — `6abbdcd` "five framework fixes" (13 files, +1051/-51).
- **Scope B** — `165c6f9` "summary dashboard tooling" (57 files, +21647/-170),
  never through CI on this branch; first met CI via stacked PR #142, where it failed.

**Verdict: CHANGES REQUESTED.** 2 BLOCKING / 4 WARNING / 3 NIT.

## Checks re-run independently

| Check | Result |
|---|---|
| Seven-package validate chain | all rc=0, zero INVALID lines — **but see BLOCKING 2**, this is green only because of unpushed local pak commits |
| pytest (full, `-n auto --dist=loadgroup --override-ini="addopts=" -m ""`) | **1458 passed, 7 skipped, 0 failed** in 695s — matches tooling's claim exactly |
| `tests/test_common_doctor.py` alone | **91 passed** — the four known environment failures do not reproduce, claim confirmed |
| New tests (3 files) | 34 passed, claim confirmed |
| Render regression, scope A | `165c6f9` vs `6abbdcd`, 19 views + 9 dashboards, `PYTHONHASHSEED=0`: **byte-identical** (`99a08f29…` both sides) |
| Render regression, scope B | base `fd926d0` content (19 views + 8 dashboards) rendered by the `fd926d0` renderer and by the HEAD renderer: **byte-identical** (`6e2f56e7…` both sides) |
| `CURRENT_TEMPLATE_VERSION` no-bump | **safe**, see below |
| buildkit import rewrite | verified functionally, see below |
| pak-compare | n/a (read-only gate, no pak built) |

My render sha differs from tooling's `88015693…` because the recipe differs (owner UUID,
ordering, join). The invariant that matters — no drift before/after — holds on both scopes,
verified with my own recipe applied identically to both trees.

### The no-bump decision is correct, on the stated contract

`src/vcfops_packaging/template_version.py` says bump when `templates/install.{py,ps1}`,
`builder.py` *output structure*, or `render.py` *dashboard wire format* change. Across
`fd926d0..HEAD` the branch touches `render.py`, `builder.py`, `discrete_builder.py` and
**not** `templates/`. Both render hashes above prove no wire-format change for existing
content, and the `builder.py` / `discrete_builder.py` changes are provably inert absent
`@supermetric:` tokens (the pre-PR-#142 corpus has none). No bump required.

## BLOCKING

### 1. The `@supermetric:` fix does not close the regression end to end: it emits a doubled `Super Metric|` prefix

`src/vcfops_supermetrics/crossref.py:118-131` (`resolve_sm_formula._replace`)

Run the fixed `builder._render_supermetrics_dict` against the content this fix exists to
rescue (PR #142's `bundles/vcf-license-consumption-overview.yaml`, 8 refs across 6 SMs):

```
[VCF Content Factory] VCF Total License Usage (%)
  (${this, metric=Super Metric|Super Metric|sm_c43ec7e3-...}
   / ${this, metric=Super Metric|Super Metric|sm_e2560d5e-...}) * 100
```

All 8 references come out `Super Metric|Super Metric|sm_<uuid>`. That is as unparseable as
the literal token it replaced. **The stated P1 regression is still open**; the failure mode
merely changed shape, and the build reports success.

Root cause is a three-way authority mismatch that this fix should have resolved and did not:

- The resolver's contract (`crossref.py:8-10`, `sdk_builder.py` docstring, and every
  existing SDK pak formula — `vcommunity/supermetrics/vsphere-cluster-performance.yaml`,
  `vcommunity-vsphere/supermetrics/esxi-hosts-average-availability.yaml`, 9 files total)
  is that the token replaces the **whole** wire term including the prefix:
  `attribute=@supermetric:"Name"` / `metric=@supermetric:"Name"`.
- PR #142's content writes `metric=Super Metric|@supermetric:"Name"` — the prefix by hand.
- `.claude/skills/vcfops-supermetric-dsl/SKILL.md:168-172` is what makes that mistake
  reachable. It says `In YAML: @supermetric:"<exact name>"` and then, separately,
  `On the wire: ${this, metric=Super Metric|sm_<uuid>}`, never stating that the token
  supplies its own `Super Metric|`. The same block also says
  **"Loader rewrites to `sm_<uuid>` at validate time"**, which is false: there is no
  `@supermetric` handling anywhere in `vcfops_supermetrics/loader.py`, and `validate`
  passes the doubled form clean (confirmed: `vcfops_supermetrics validate` rc=0 on the
  PR #142 corpus).

Smallest correct fix, framework side (this PR's scope): in `resolve_sm_formula`, make the
match consume an immediately-preceding `Super Metric|` so the substitution is
prefix-idempotent, exactly as it is already `sm_<uuid>`-idempotent — or, if the authored
form is to be treated as an error, raise on it. Either way it must not silently emit
`Super Metric|Super Metric|`. A resolver whose whole justification (`crossref.py:18-21`)
is "failing loudly at build time is strictly safer than shipping it" cannot ship this
quietly. Add the regression test; none of the 34 new assertions covers it
(`grep 'Super Metric|Super Metric' tests/` returns nothing).

Corresponding content fix in PR #142 (drop the hand-written prefix) and the SKILL.md
correction are the other two legs, but the framework leg belongs here.

### 2. Scope B's new partial-bounds validator rejects the published state of two managed paks; local green depends on unpushed commits

`src/vcfops_dashboards/loader.py` (metric-bounds check added by `165c6f9`, encoding
`knowledge/lessons/scoreboard-partial-bounds-render-unknown.md`)

PR #142's CI failure (run `33026923667`, 7 failed / 1417 passed) is seven publish tests all
tripping on `python3 -m vcfops_managementpacks validate`. Its Tier 2 list stops at four
paks — `vcommunity` and `vcommunity-vsphere` are absent. Reproduced locally by validating
those two repos at **`origin/main`** (what `scripts/bootstrap_managed_paks.sh` clones in CI):

```
INVALID: 1 error(s) in .../vcommunity:
  bundled_content.dashboards: failed to load .../dashboards/Cluster Performance 2.0.yaml:
  widget '75262957-...': metric 'configuration|dasConfig|enabled': color_method 0 needs
  all three bounds or none; missing red_bound.
```
(identical for `vcommunity-vsphere`.)

Both local clones sit **one unpushed commit ahead of `origin/main`**
(`ff93501` / `c5da826`, "complete bound triple on Cluster Performance 2.0 HA/DRS tiles"),
and that commit is the fix. So:

- The validate chain is green on this machine and red anywhere else.
- PR #141 will fail CI identically to #142 the moment CI runs on it. The branch has zero
  workflow runs despite an unfiltered `pull_request` trigger, so nothing has told anyone.
- This is the CLAUDE.md "portability is non-negotiable" bar and the dimension-7 corpus
  regression: a framework tightening that mis-validates previously-good published content.

The validator itself is correct and live-proven; the defect is sequencing. Fix: push
`ff93501` and `c5da826` to the two `sentania-labs` pak repos' `main` **before** merging
this PR, then re-run CI and confirm all six Tier 2 paks report OK from a clean bootstrap.
No framework code change needed. Merging first ships a repo whose own validate chain fails
on a fresh clone.

## WARNING

### 1. `allow_external_views=True` does not reopen Fix 3's hole, but it is wider than it needs to be and launders a wire-format defect

`src/vcfops_dashboards/loader.py:1646-1651, 1737-1747`; `src/vcfops_managementpacks/sdk_builder.py:906-929`

**Direct answer to the flagged judgement call: the flag suppresses only the view-existence
check, nothing more.** `known_views` is referenced exactly once inside `Dashboard.validate()`
(line 1740), and the `summary_for` pinned / self-provider invariant (lines 1665-1688) runs
earlier and unconditionally. Fix 3's actual point is fully preserved on the pak path. That
part of the author's judgement is correct and I verified it by reading every `known_views`
use in the method, not by taking the docstring's word.

What the author did not weigh: the flag is load-bearing for **exactly one widget in the
entire pak corpus**. Strict validation across all six paks yields one failure:

```
STRICT-FAIL vcommunity-vsphere: dashboard VM Details: widget f5b4a644-...:
  unknown view 'Windows Services vCommunity'
```

And that reference is itself broken on the wire. Rendering the dashboard through the pak
path emits:

```
643f1e7a-b010-5bb2-a22a-7263ad8aec84 -> 'Windows Services vCommunity'
e1a3ad50-2043-5b2e-8e80-bc2ded937b87 -> 'f12d5911-bcd2-48c9-b7b9-5ae57eef8a41'
```

a display name in `viewDefinitionId` where every sibling widget carries a UUID. Ground
truth: `reference/references/` contains **235 `viewDefinitionId` occurrences, 235 of them
UUID form, zero name form**. There is no evidence the platform resolves that field by name,
and the widget will render blank with no diagnostic.

The correct authoring form is already available and already passes the *existing* raw-UUID
passthrough: the referenced view ships with a stable id `ae751947-1782-466f-b560-9a950be3c1f9`
in both `vcommunity` and `vcommunity-os`. Referencing that UUID needs no new flag at all.

This does not regress against `main` (the pak path ran no validation before Fix 3, so the
bare name already flowed through), which is why it is WARNING and not BLOCKING. But as
shipped, a genuine view-name typo in any future pak is permanently unvalidated, and the
one case it was added for produces exactly the silent-blank-widget outcome the fix's own
"reports green while broken" reasoning exists to prevent.

Fix: reference the view by its UUID in `vcommunity-vsphere/dashboards/VM Details.yaml` and
drop `allow_external_views`. If the flag is kept, it must at minimum warn loudly and name
the unresolved view, so an unmatched bare name is never silent.

### 2. `render.py`'s external-view comment is now false

`src/vcfops_dashboards/render.py:2221-2223`

> "A bare name that isn't bundled cannot reach here, loader.validate() already rejects that
> case as an authoring error."

With `allow_external_views=True` it can and does. The INFO line at 2226-2230 then
mislabels it: `external view UUID 'Windows Services vCommunity'` — it is not a UUID. Fix
the comment and make the message distinguish the two cases.

### 3. Near-miss `@supermetric` syntax passes through silently

`src/vcfops_supermetrics/crossref.py:40`

`SM_CROSSREF_RE = @supermetric:["']([^"']+)["']` requires the quote immediately after the
colon. Probed directly:

| input | result |
|---|---|
| `@supermetric:"A"` | resolved |
| `@supermetric: "A"` (one space) | **passes through unresolved, no error** |
| `@supermetric:A` (unquoted) | **passes through unresolved, no error** |
| `Super Metric\|sm_<uuid>` | untouched (idempotency confirmed) |

Both near-misses ship a literal `@supermetric` into the pak, which is the exact P1 this
module exists to eliminate, and nothing anywhere catches it: the loader has no
`@supermetric` awareness at all (`grep` over `vcfops_supermetrics/loader.py` is empty), so
`validate` is blind too. Fix: after substitution, hard-error if the literal string
`@supermetric` survives in the formula. Three lines, closes the whole class.

Idempotency, name-collision precedence and hard-error correctness otherwise check out:
the batch/bundle map is consulted before `fallback_lookup`, so an SM being pushed always
wins over a same-named stranger on the target, and double resolution is a no-op.

### 4. The live-sync `find_by_name` fallback binds silently and cannot detect ambiguity

`src/vcfops_supermetrics/client.py:556-561`, `find_by_name` at `client.py:83-90`

`find_by_name` returns the **first** exact-name match from
`GET /api/supermetrics?name=<n>` and never reports that a second existed. So on the live
sync path, a reference to an SM outside the batch binds to whichever same-named SM the
target happens to return first, with no output telling the operator which UUID was chosen
or that the choice was ambiguous. RULE-006's `[VCF Content Factory]` prefix narrows but does
not eliminate this (`vcommunity` and `vcommunity-os` already ship the same view name and
UUID from two paks, so same-name-two-objects is a real shape here).

Fix: print the resolved `name -> sm_<uuid>` for every fallback hit, and error rather than
guess when the response carries more than one exact-name match.

## NIT

1. `src/vcfops_packaging/template_version.py:8-11` lists `builder.py` and `render.py` as
   bump triggers; CLAUDE.md "After tooling changes" lists `discrete_builder.py` and
   `release_builder.py` too. The two lists should agree, or the next person will reason
   from the shorter one.
2. `vcfops_common.dep_walker.extract_refs_from_supermetrics` (`dep_walker.py:219-247`)
   handles `attribute=sm_<uuid>` only, not `metric=` and not the `@supermetric:` name form,
   while the name-form handler at `dep_walker.py:663` covers view columns only. **I agree
   this is safe to defer**: the sync advisory is a convenience and
   `import_supermetrics_bundle` now hard-errors at push, so the failure is loud, not silent.
   Worth an issue, not a blocker.
3. `crossref.sm_name_to_uuid_map` silently drops any SM lacking an `id`; a reference to one
   then surfaces as the generic "could not be resolved" rather than naming the real cause.

## Do the ten committed reviews cover Scope B?

Partly, and not enough to skip a fresh pass. `2026-08-25-summary-dashboards.md` (nine
passes) and `2026-08-26-license-consumption.md` are genuine incremental reviews of the
loader / render / `summary_bind` / `reverse` surfaces as they were built, and they do cover
that surface well. What they do not and structurally could not cover:

- They ran against a scratchpad-installed pytest and treat "1142 passed, **7 failed**"
  as an accepted baseline. My clean run is 1458/0 failed, so that baseline was environmental
  and was masking nothing here, but it is not the CI contract.
- None of them saw CI, because CI never ran on this branch.
- None covers BLOCKING 2: the partial-bounds validator was reviewed as a *code* change,
  never re-run against the two pak repos at `origin/main`.
- None covers `@supermetric:` at all, since no content used it yet.
- `src/vcfops_packaging/deps.py` in `165c6f9` is not covered by any of them. I reviewed it
  independently: the accumulate-keys-then-fan-out-over-`view.subject_kinds` refactor is
  correct, `subject_kinds` (`loader.py:485-490`) always returns at least one pair so no view
  silently loses its audit, and the `time_segment` skip matches the existing instanced-group
  driver skip.

## Verified inert (the three claimed tightenings)

- **`hide_object_name` type check** (`loader.py:2318-2325`): every occurrence repo-wide,
  including PR #142's three views, is an unquoted `true`. Inert.
- **Unresolvable SM cross-reference**: the pr141 corpus has zero `@supermetric:` tokens, so
  `builder`/`discrete_builder` are no-ops on it. On PR #142's corpus `_expand_sm_crossrefs`
  resolves all 8 refs and correctly walks two levels transitively
  (`VCF License Potential Cores -> vSphere World VCF Licensed Cores -> Host VCF Licensed Cores`).
  No spurious error. Inert on valid input.
- **Bundled pak `Dashboard.validate()`**: strict-mode sweep over all six paks produces
  exactly one failure, the `vcommunity-vsphere` external view of WARNING 1. Everything else
  passes. Inert.

## buildkit (verified functionally, not just registered)

`_apply_rewrites` on the real `sdk_builder.py` source turns
`from vcfops_supermetrics import crossref as _crossref` into
`from . import sm_crossref as _crossref`, and the rewritten module carries **zero**
remaining top-level `vcfops_*` imports. `crossref.py` itself imports only `re` and `typing`,
so it is safe to vendor. `tests/managementpacks/test_buildkit_isolated_build.py` +
`test_buildkit_release_flag.py`: 7 passed.

## If shipped as-is

Two things. First, every one of PR #142's eight SM cross-references installs as
`Super Metric|Super Metric|sm_<uuid>`, so six super metrics evaluate to nothing and the
License Consumption dashboard's gauges read empty, with the build having reported success
throughout. Second, CI fails on merge to `main` on a validate error that cannot be
reproduced on the author's machine, because the fix for it lives only in two unpushed
commits inside gitignored pak clones.

## What has to change to clear this gate

1. `resolve_sm_formula` must not emit `Super Metric|Super Metric|` — absorb the adjacent
   prefix or reject it, with a test. (Plus, outside this PR: PR #142's formulas drop the
   hand-written prefix, and `vcfops-supermetric-dsl` SKILL.md §Cross-SM references is
   corrected on both the prefix and the false "loader rewrites at validate time".)
2. Push `ff93501` (`vcommunity`) and `c5da826` (`vcommunity-vsphere`) upstream, then show a
   CI run on this branch that is green from a clean `bootstrap_managed_paks.sh`.

The four WARNINGs do not block, but 1 and 3 are cheap and land in the same files.
