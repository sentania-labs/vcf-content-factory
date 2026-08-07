# Framework review (round 3, final gate): instanced_group audit + release-manifest threading

- Date: 2026-08-06
- Reviewer: `framework-reviewer` (read-only, pre-PR gate, RULE-013 sibling)
- Branch: `feat/vm-snapshot-inventory` (working tree, uncommitted)
- Change author: `tooling`
- Round 1: `knowledge/context/reviews/framework/packaging-discrete-builtin-metric-enables-2026-07-27.md`
- Round 2: `knowledge/context/reviews/framework/packaging-deps-instanced-group-2026-08-06.md`
  (CHANGES REQUESTED — 1 BLOCKING, 3 WARNING, 1 NIT)

## Verdict

**APPROVE** — 0 BLOCKING, 2 WARNING, 4 NIT.

B1 is genuinely resolved and I reproduced the fix end to end through the real
CLI entry point. W1's delegation is proven safe against the actual describe
corpus, not just against the two shapes I cited. W3 is corrected. The two
remaining WARNINGs are new, both non-blocking: a residual (truthful, but
unsatisfiable) strict failure on the *view* discrete build, and a silent
exception swallow in the new lookup. Neither breaks a shipping path and
neither changes a shipped artifact.

## Scope of diff reviewed

```
 src/vcfops_packaging/cli.py                           | 14 ++
 src/vcfops_packaging/deps.py                          | 84 +++++++---
 src/vcfops_packaging/release_builder.py               | 73 ++++++++
 tests/test_discrete_builder_builtin_metric_enables.py | 49 +++++-
 tests/test_deps_instanced_group_columns.py            | new, 13 tests
```

(The tree also carries unrelated `content/` + `knowledge/designs/` edits for
fleet-capacity-rightsizing — outside this reviewer's surface, not reviewed.)

## Checks re-run independently

| Check | Result |
|---|---|
| `vcfops_{supermetrics,dashboards,customgroups,symptoms,alerts,reports,managementpacks} validate` | all **PASS** |
| Default suite (`pytest -q`, addopts `-m "not slow"`) | **646 passed, 4 skipped**, 178 deselected |
| deps/discrete/release subsets incl. slow (`-m ""`, 5 files) | **131 passed** |
| `build-discrete --no-live-describe --strict-deps dashboard "[VCF Content Factory] VM Snapshot Inventory"` | **rc=0** — 10 refs, 8 resolved, 2 enablement (matches tooling's claim) |
| Full pre/post sweep: strict discrete build of **all 19 views + 9 dashboards**, pre-change `_refs_from_view` emulated in-process | 27/28 unchanged; **1 delta**: `content/views/vm_snapshot_inventory.yaml` pre=0 → post=1 (W-A below) |
| Shipped-artifact drift: `content/builtin_metric_enables.json` in the new strict discrete zip vs committed `dist/dashboards/vm-snapshot-inventory-dashboard.zip` | **byte-identical** (manifest reasons, not auto-generated reasons) |
| Old-vs-new `_normalize_metric_key` over the describe corpus | **0 of 5729** cache keys (MSSQL/ORACLE/VMWARE) contain `:` |
| Release-corpus shape: 13 manifests, headline sources, duplicate detection | all single-headline; **no duplicate headline source**; only 1 release declares `builtin_metric_enables` |
| GitHub issues for deferred round-2 items | **#71** (W2 analyze path), **#72** (subject-filter NIT) — both open |
| `pak-compare` | n/a, no pak surface touched |

## B1 — RESOLVED (verified, not taken on faith)

`cli.py:425,437-448` + `release_builder.py:144-208`

Round 2's blocker was that `--strict-deps` on a *released* discrete item was
structurally unsatisfiable: the declarations existed in
`bundles/releases/vm-snapshot-inventory-dashboard.yaml:4-12` and
`cmd_build_discrete` never read the manifest. I re-ran the exact command that
failed in round 2 and it now exits 0 with the audit reporting `enablement: 2`
(i.e. it *sees* the two `default_monitored=false` refs and finds them declared,
rather than skipping them).

Mis-match analysis of `find_builtin_metric_enables_for_discrete_item`, the
thing I was asked to attack:

- **Name collision across types is real in this corpus and correctly handled.**
  `content/views/vm_snapshot_inventory.yaml` and
  `content/dashboards/vm_snapshot_inventory.yaml` carry the *identical*
  `name:` string. The parent-dir → `content_type` guard
  (`_PARENT_DIR_TO_DISCRETE_TYPE`, `release_builder.py:195-198`) means the
  `view` build does **not** pick up the dashboard release's enables — proven
  empirically (the view build received an empty list; see W-A).
- **Non-component headlines cannot mis-match.** Bundle headlines
  (`parent.name == "bundles"`), SDK pointers (`content/sdk-adapters/<name>/`),
  and the third-party headline (`third_party/idps-planner/`) all miss the map
  and are skipped. Verified across all 13 manifests.
- **Shared source dir is not sufficient to mis-match**: the match requires
  dir-derived type **and** the YAML `name:` to agree.
- Residual ambiguity is real but currently inert — see N-A.

Artifact safety: the newly-threaded enables do **not** alter any shipped zip.
The discrete strict build's `builtin_metric_enables.json` is byte-identical to
the committed `dist/` zip built by the release path.

## W1 — RESOLVED, and safer than round 2 could prove

`deps.py:95-116` (`_normalize_instanced_group_key`), `deps.py:126-147`
(`_normalize_metric_key` now delegating), `_INSTANCED_KEY_RE` removed.

Round 2 proved the segment-local rule correct on 119 vendor keys. Round 3
attacks the *other* direction — could delegation now over-strip a key the old
leading-segment regex left alone? Ground truth: **zero of 5729 keys** across
the whole `knowledge/context/adapter_describe_cache/` (MSSQL, ORACLE, VMWARE)
contain a `:`. So for every key the auditor can resolve, a `:` can only be an
instance token, and stripping it is the only path to a hit. Behaviour on the
widget / SM / direct-`attribute:` callers is unchanged for every key in the
committed corpus (28-item pre/post strict sweep: no delta outside W-A; full
suite green).

The one shape that *would* break the rule is not a false alarm to be dismissed
silently, so it is recorded as N-B.

## W3 — RESOLVED

`tests/test_discrete_builder_builtin_metric_enables.py:381-395` now correctly
attributes the pass to auto-mode auto-add, and points at the new strict test.
Strict coverage is now real, drives the actual CLI entry point, and I confirmed
it passes under `-m ""`.

---

## WARNING

### W-A — `build-discrete --strict-deps view "[VCF Content Factory] VM Snapshot Inventory"` regresses from pass to fail

`deps.py:213-239` (new member-column emission); reproduced:

```
$ python3 -m vcfops_packaging build-discrete --no-live-describe --strict-deps \
    view "[VCF Content Factory] VM Snapshot Inventory"
AUDIT FAILED  strict-deps mode: ... diskspace|snapshot|creator, diskspace|snapshot|description
exit 1
```

Proven introduced by this diff: with a pre-change `_refs_from_view` patched in
(skip all instanced_group columns), the same command returns **rc=0** with
`references: 4 total`. Post-change it is rc=1. This is the **only** delta in a
sweep of all 19 committed views and 9 committed dashboards.

Why this is a WARNING and not a repeat of B1:

- The failure is **truthful** — the view really does reference two
  `default_monitored=false` properties; surfacing that is the point of the fix.
- It is not the B1 paradox. B1 was "the declaration exists and the tool refuses
  to read it." Here no declaration exists anywhere: the release manifest lists
  only the dashboard as an artifact (`bundles/releases/vm-snapshot-inventory-dashboard.yaml:1-3`),
  and the view is embedded, not a listed artifact — so the round-2 "smallest
  fix" (headline lookup) structurally cannot cover it.
- The item joins an existing cohort: **7 committed views/dashboards already
  fail `--strict-deps` on discrete build** pre-change (`cluster_storage_trend`,
  `cpu_support_status_by_cluster`, `cpu_support_status_by_host`,
  `datastore_reclaimable_space`, `vsan_cluster_health_resync`,
  `vsan_cluster_performance`, dashboard `vsan_cluster_health`, plus the
  in-flight `fleet_capacity_rightsizing`). Same remedy, same message. No new
  failure class.
- No shipping path is affected: `release`/`publish` builds the dashboard
  headline (rc=0), default (auto) mode is unaffected, artifact byte-identical.

→ File an issue: `--strict-deps` is unsatisfiable for any discrete item that is
not itself a release headline, and its error text ("add these entries to the
'builtin_metric_enables' section of the bundle manifest") names a manifest that
does not exist for a discrete build. Either teach the lookup to walk a
release's embedded content, or make the message name the actual remedy for the
discrete case. Not a blocker on this diff.

### W-B — the new lookup silently swallows a broken release corpus, reverting a released item's declarations with no diagnostic

`release_builder.py:186-192`

```python
except ReleaseValidationError:
    return []
```

Demonstrated: with **one unrelated** manifest made invalid, the vm-snapshot
dashboard build

- under `--strict-deps` fails with the *exact* B1 message ("Add these entries
  to the 'builtin_metric_enables' section...") even though the entries are
  sitting in a valid manifest — B1's confusion recreated by a different
  trigger, with nothing on stdout/stderr hinting the manifest corpus failed to
  load; and
- under default auto mode succeeds but ships **different `reason` text**
  (`"Auto-detected: referenced by view ..."` instead of the curated
  `"View Creator column reads this policy-disabled property; enabled=true alone
  verified sufficient 2026-07-27"`). Dimension 8: a silent downgrade of shipped
  artifact content driven by an unrelated file's validity.

The comment says `validate` covers manifest validity, which is true, but the
operator running `build-discrete` gets no signal at all at the moment it bites.
→ Smallest fix: emit a one-line warning to stderr naming the exception before
`return []` (e.g. `warning: release manifests could not be loaded (<exc>);
proceeding without declared builtin_metric_enables`). Keeping the soft fallback
is fine; being silent about it is not.

## NIT

### N-A — first-match-wins lookup with no guard against ambiguity

`release_builder.py:194-206` returns the first matching headline over manifests
sorted by filename. `releases.py` validates duplicate release *names*, not
duplicate headline *sources*, and the schema explicitly allows a release with
more than one headline (`releases.py:36`, "at least one artifact must be
headline: true") while `builtin_metric_enables` is release-scoped. So two
releases headlining the same item, or one release headlining a dashboard and a
report, would resolve arbitrarily / over-broadly, and an over-broad match ships
enables into a zip whose content never references them. Verified inert today:
all 13 releases are single-headline, no duplicate headline source, and only one
release declares enables at all. → Prefer collecting all matches and raising on
>1, or add a duplicate-headline-source check to `load_all_releases`.

### N-B — delegated normalizer would truncate a stat name that legitimately contains `:`

The repo already contains such keys, in third-party pak content:
`content/sdk-adapters/vcommunity-vsphere/dashboards/VM Details.yaml:115` uses
`vCommunity|Configuration|Advanced Parameters|scsi0:0.redo`, where
`scsi0:0.redo` is the *stat name*, not an instance token. The old regex left it
alone; the new rule yields `...|Advanced Parameters|scsi0`, which would resolve
to `None` → `unknown` → hard `AuditError` in **every** mode
(`audit.py:141-155`). Currently unreachable: the describe cache holds only
MSSQL/ORACLE/VMWARE, none of which has a colon-bearing key, and SDK-adapter
content is built by the SDK buildkit, not by this audit path. → Worth one line
in the `_normalize_instanced_group_key` docstring recording the assumption
("`:` in a describe key is always an instance token; verified 0/5729 in the
current cache"), so a future adapter that violates it is diagnosable.

### N-C — the new strict CLI test does not run in the default `pytest`

`tests/test_discrete_builder_builtin_metric_enables.py:35` applies
`pytestmark = pytest.mark.slow` to the whole file, and `addopts = -m "not slow"`.
The B1 regression test therefore only runs in CI's `-m ""` invocation. That
matches the file's stated convention (it builds real zips), so this is a note,
not a defect — but the B1 coverage is one addopts change away from being
invisible locally.

### N-D — stale-zip protocol nominally fires; provably unnecessary here

CLAUDE.md "After tooling changes" lists `src/vcfops_packaging/release_builder.py`
as a trigger for rebuilding every `bundles/` manifest. This diff touches it.
The change is purely additive (a new function with no call site inside
`build_release` — verified by grep: the only caller is `cli.py:444`), and I
confirmed the affected release's shipped `builtin_metric_enables.json` is
byte-identical. → No `content-packager` rebuild is functionally required; the
orchestrator should waive it consciously rather than skip it silently.

## What is provably fine

- **No global-default / pak-specific leak** (anchor `00d3382`): no default,
  flag, transform, or coordinate convention added to a shared path. The deps
  change is confined to the `instanced_group is not None` branch; the CLI
  change adds a lookup that returns `[]` for every item that is not a release
  headline (proven: 27 of 28 corpus items behave identically pre/post).
- **No key/label collision** (anchor `6c59f6b`): refs dedupe on
  `(adapter_kind, resource_kind, metric_key)`; all 5 vm-snapshot member columns
  yield distinct keys and none collides with the flat `diskspace|snapshot`
  summary column (re-confirmed via the 10-ref strict run).
- **No wire-format drift**: the one artifact whose content could shift is
  byte-identical to the committed `dist/` zip, including `reason` text.
- **Soft fallback does not mask a real declaration miss for released items**:
  for unreleased items there is nothing to find, and for released items the
  fallback direction is *under*-declaration, which fails loudly under strict and
  is auto-repaired under auto — with the one silent-diagnostic gap recorded as
  W-B.
- **Test coverage**: 13 new deps tests (incl. both round-2-cited shapes and a
  real-content regression against the committed describe cache) + a real-CLI
  strict test. Gap: no direct unit test of
  `find_builtin_metric_enables_for_discrete_item`'s no-match / wrong-type /
  invalid-corpus branches (the cross-type name collision above is the case most
  worth pinning).
- Round-2 deferrals confirmed filed, not lost: issues **#71** and **#72**.

## If shipped as-is

Operators get the fixed behaviour on every path they actually ship through:
default and `--strict-deps` discrete builds of the released dashboard succeed,
the release/publish path and every `dist/` zip are unchanged byte for byte, and
a class of silently-unaudited built-in dependency is now caught. The two
residues are narrow: running `--strict-deps` against the *view* (not the
dashboard) still fails with a message naming a manifest that does not exist for
discrete builds, and if any release manifest is ever invalid, a discrete build
quietly ships auto-generated enable reasons instead of the curated ones.
