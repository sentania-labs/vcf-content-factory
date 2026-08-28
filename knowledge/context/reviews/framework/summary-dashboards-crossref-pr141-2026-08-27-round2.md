# Framework review round 2: PR #141 (`pr/summary-dashboard-tooling`) @ `b2cb0fb`

Companion to `summary-dashboards-crossref-pr141-2026-08-27.md` (round 1,
CHANGES REQUESTED, 2 BLOCKING / 4 WARNING / 3 NIT).

Three commits under review: `db7024b` (SKILL.md), `ab5e4f9` (code + tests),
`b2cb0fb` (`uuids_and_cross_references.md`). Scope B (`165c6f9`) got a full
pass in round 1 and is re-checked only where the new commits reach it.

**Verdict: CHANGES REQUESTED.** 1 BLOCKING (carried, non-code, now broader) /
1 WARNING / 1 NIT. **BLOCKING 1 is closed. No framework code change is owed.**

## Checks re-run independently

| Check | Result |
|---|---|
| Seven-package validate chain, local clones | 7/7 rc=0, zero INVALID |
| Seven-package validate chain, pak repos at `origin/main` | **2 of 6 paks INVALID** — see BLOCKING A |
| pytest full (`-n auto --dist=loadgroup --override-ini="addopts=" -m ""`) | **1476 passed, 7 skipped, 0 failed** in 827s — matches tooling's claim exactly |
| Render regression, scope A (HEAD content, renderer `6abbdcd` vs `b2cb0fb`) | **byte-identical**, 19 views + 9 dashboards, `sha=470e0443…` both sides |
| Render regression, scope B (`fd926d0` content, renderers `fd926d0`/`165c6f9`/`6abbdcd`/`b2cb0fb`) | **byte-identical across all four**, 19 views + 8 dashboards, `sha=051dffd0…` |
| PR #142 bundle build `--strict-deps`, no `--skip-audit` | audit **10/10 resolved**; 16 SM references across both zip members, zero doubled prefix, zero naked UUID, zero surviving `@supermetric`, every UUID maps to the SM actually named in source YAML — Scott's verification reproduced independently |
| `CURRENT_TEMPLATE_VERSION` no-bump | still correct; the new commits touch `render.py` stderr text only, proven output-inert by the two render hashes |
| dist-zip staleness signal | PR body explicitly owes a `content-packager` rebuild. Dimension 9 satisfied |
| pak-compare | n/a (read-only gate, no pak built) |

Render recipe: `load_all()` -> `render_views_xml()` + `render_dashboards_bundle_json()`,
fixed owner UUID, id-sorted, `PYTHONHASHSEED=0`, applied identically to every tree.

## Round-1 findings: disposition

| # | Round-1 finding | Round-2 status |
|---|---|---|
| B1 | doubled `Super Metric\|Super Metric\|` prefix | **CLOSED** for the documented/authored form; residual variant -> WARNING A |
| B2 | validate chain green only via unpushed pak commits | **OPEN, and broader** -> BLOCKING A |
| W1 | `allow_external_views` too wide, laundered a wire defect | **CLOSED**, correctly, and better than I asked |
| W2 | false render.py comment + mislabelled INFO | **CLOSED**, verified |
| W3 | near-miss `@supermetric` syntax passes silently | **CLOSED**, verified by probe |
| W4 | `find_by_name` binds silently, cannot detect ambiguity | **CLOSED**, verified; the reach beyond live-sync is correct (below) |
| N1 | `template_version.py` bump-trigger list | **CLOSED** |
| N2 | `dep_walker` coverage | deferred by agreement, issue #144 |
| N3 | id-less SM dropped from map | **CLOSED**, with its own diagnostic and test |

## BLOCKING

### A. The unpushed-pak-commit dependency is still open, and this round added a third commit to it

Carried from round 1 BLOCKING 2. Confirmed still the only such dependency, and
confirmed it grew.

I extracted all six Tier 2 pak repos at `origin/main` (`git archive`, no write to
the clones) and ran `validate_sdk_project` on each:

```
compliance         OK
synology           OK
unifi              OK
vcommunity         1 ERROR   Cluster Performance 2.0: color_method 0 needs all three bounds
vcommunity-os      OK
vcommunity-vsphere 1 ERROR   (same)
```

The three commits that fix it are all local-only, and both repos are sitting on
a feature branch (`fix/scoreboard-partial-bounds`), not `main`, so
`bootstrap_managed_paks.sh` will not pick them up:

- `vcommunity` `ff93501` — bound triple
- `vcommunity-vsphere` `c5da826` — bound triple
- `vcommunity-vsphere` `63f8506` — **new this round**, `VM Details` widget by UUID

`63f8506` became load-bearing *because* `allow_external_views` was deleted.
Proven: validating `vcommunity-vsphere` at `c5da826` (bounds fixed, view fix
absent) fails hard:

```
dashboard VM Details: widget f5b4a644-…: unknown view 'Windows Services vCommunity'
```

At local HEAD (with `63f8506`) it is clean, and the UUID it now carries,
`ae751947-1782-466f-b560-9a950be3c1f9`, is exactly the `id:` of
`vcommunity/views/Windows Services vCommunity.yaml`. The content fix is right;
it is just not published.

`vcommunity-os` is 2 commits ahead of `origin/main` too, but both are CI-workflow
only and it validates OK at `origin/main`, so it is not a dependency.

**Authority:** CLAUDE.md "Portability is non-negotiable"; review dimension 7
(corpus regression). No framework code change owed. Clears when all three
commits are on the respective `main`s and a CI run on this branch is green from
a clean `bootstrap_managed_paks.sh`.

## WARNING

### A. Prefix absorption is exact-case-and-spacing only, and the doc claims more than the code delivers

`src/vcfops_supermetrics/crossref.py:47`

Absorption is the right call over erroring, and it fixes the form PR #142
actually authored. But `(?:Super Metric\|)?` is case- and whitespace-exact,
while `vcfops_packaging.deps._is_sm_ref` lowercases its input — the codebase's
own admission that prefix case varies in authored keys. Probed directly against
`resolve_sm_formula`:

| input | output |
|---|---|
| `metric=@supermetric:"X"` | `metric=Super Metric\|sm_…` correct |
| `metric=Super Metric\|@supermetric:"X"` | `metric=Super Metric\|sm_…` correct, the PR #142 form |
| `metric=super metric\|@supermetric:"X"` | `metric=super metric\|Super Metric\|sm_…` **doubled, silent** |
| `metric=SUPER METRIC\|@supermetric:"X"` | `…SUPER METRIC\|Super Metric\|sm_…` **doubled, silent** |
| `metric=Super Metric\| @supermetric:"X"` | `…Super Metric\| Super Metric\|sm_…` **doubled, silent** |
| `metric=Super Metric\|Super Metric\|@supermetric:"X"` | `…Super Metric\|Super Metric\|sm_…` **doubled, silent** |
| `metric=Super Metric\|sm_zzz} + …Super Metric\|@supermetric:"X"` | mixed resolved/unresolved handled correctly |

Every residual case is already-malformed input (all 17 `Super Metric|`
occurrences across `content/` and `reference/references/` are canonical case,
and the reverse module emits canonical case), which is why this is WARNING and
not BLOCKING. The problem is the *claim*:

- `.claude/skills/vcfops-supermetric-dsl/SKILL.md`: "The resolver consumes an
  immediately-preceding `Super Metric|` **so this cannot ship silently**"
- `knowledge/context/authoring/uuids_and_cross_references.md`: "The regex now
  absorbs an immediately-preceding `Super Metric|`, so **both forms resolve to
  a single prefix**"

Both are true for one spelling and false for four. That is the
reports-green-while-broken shape aimed at a downstream author who cannot see
this repo — the same shape `_SM_CROSSREF_LITERAL` was added to close.

**Fix**, one line beside the guard that already exists, closing the whole class
regardless of spelling:

```python
if re.search(r"(?i)super\s*metric\s*\|\s*super\s*metric\s*\|", resolved):
    raise error_cls(...)
```

with a parametrized case-variant test. `grep -i 'super metric|super metric' tests/`
currently matches only the canonical-case assertion in
`TestHandWrittenPrefixIsAbsorbed`. Alternatively, soften both doc sentences to
say absorption covers the canonical prefix only. Do not ship the strong claim
with the narrow code.

## Verified as claimed (skeptical checks that came back clean)

**`_UNRESOLVED_SM_FORMULA_REF_PREFIX` is not a second blind spot; the `@`-less
constant is live.** `vcfops-project-conventions` SKILL.md:126-127 defines two
distinct forms, and both are in the corpus: SM formula -> SM is
`@supermetric:"<name>"`, view column -> SM is `supermetric:"<name>"` (no `@`).
The `@`-less form appears in `content/views/cpu_support_status_by_host.yaml:42`,
`cluster_storage_trend.yaml:34`, `cpu_support_status_by_cluster.yaml:23`, and
across `vcommunity-vsphere/views/`. `_is_sm_ref` is consumed at
`deps.py:190,253,267` (view/formula key routing) and `310-357` (builtin-key
exclusion); both constants are reachable on live paths. **tooling's claim is
correct.** The new constant only stops the auditor calling `@supermetric` an
unknown builtin; the SM dependency itself is still audited by the SM path,
proven by the 10/10 strict-deps run.

**The `find_by_name` tightening is right where it reaches, and reaches nowhere
it shouldn't.** Only `_SMExtendedClient.find_by_name` changed; symptoms, alerts
and reports carry their own. The three affected callers are
`vcfops_supermetrics/cli.py:193` (`cmd_enable`, name -> id for policy
assignment), `cli.py:261` (`cmd_delete`), and `handler.py:105` (batch delete).
Two of those **delete**. Silently picking one of two same-named super metrics
to delete is strictly worse than a hard error, so raising is a safety
improvement, not a regression of a working flow. `handler.delete` catches
`VCFOpsError` per item and reports `failed` without aborting the batch;
`cmd_enable` is not per-item, but `cli.main` catches `VCFOpsError` and returns
rc=2 with a clean message, no traceback. Acceptable.

**`allow_external_views` never escaped this PR.** Introduced in `6abbdcd`,
removed in `ab5e4f9`, both on this branch. `git grep` on `origin/main`: zero
hits. `git grep` at HEAD: zero remaining references. Safe breaking change,
claim confirmed.

**The `render.py` INFO split is sound.** It imports `loader._UUID_RE` (same
package) rather than a second copy, so its UUID/non-UUID classification is
byte-for-byte the same predicate `Dashboard.validate()` accepts by. The regex
is anchored `^…$`, so `.match` cannot mislabel a string that merely starts with
a UUID. Output-inert: stderr only, proven by both render hashes.

**Docs are accurate and appropriately blunt.** Both corrected files state the
correct form, state that the wrong form "is still wrong on the page", and
correct the false "loader rewrites at validate time" claim (the SM loader has
no `@supermetric` awareness; the quick-reference table now says **emit/push**,
not `validate`). Subject to WARNING A on the one overstated sentence in each.

## NIT

1. `crossref.py` gained a hard error for `@supermetric` surviving substitution,
   but no equivalent for a doubled prefix surviving it. The two guards are the
   same shape and belong in the same block; see WARNING A.

## If shipped as-is

The framework code is correct: PR #142's six super metrics resolve to single,
correct `Super Metric|sm_<uuid>` terms on all four emit paths, and the License
Consumption dashboard's gauges will read. The one remaining exposure is
operational: merging before the three pak commits are published gives a repo
whose own `validate` chain fails on a fresh clone, and CI on this branch will
fail exactly as PR #142's run `33026923667` did.

## What has to change to clear this gate

Push `ff93501` (`vcommunity`), `c5da826` and `63f8506` (`vcommunity-vsphere`)
to their repos' `main`, then show a green CI run on this branch from a clean
`bootstrap_managed_paks.sh`. Nothing in `src/vcfops_*/` is owed. WARNING A is
cheap, lands in files already touched, and should go in the same push.
