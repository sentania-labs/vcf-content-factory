# Framework review — discrete-release `builtin_metric_enables` + property `defaultMonitored`

- **Date:** 2026-07-27
- **Area:** `src/vcfops_packaging/` (`releases.py`, `discrete_builder.py`,
  `release_builder.py`, `describe.py`, `cli.py`) + 3 new test files
- **Change under review:** working tree vs `HEAD` (all uncommitted)
- **Reviewer:** `framework-reviewer` (RULE-013 blanket pre-PR gate)
- **Verdict: CHANGES REQUESTED** — 2 BLOCKING / 7 WARNING / 3 NIT

## What the change claims to do

Close the gap reported by `content-packager` as a TOOLSET GAP: the discrete
(single-item) release path had no way to carry `builtin_metric_enables:`, so
`vm-snapshot-inventory-dashboard` 1.0 shipped without
`content/builtin_metric_enables.json`. The change adds the field to the
release-manifest schema, threads it through `release_builder` →
`discrete_builder`, emits the same bundle.json content block +
`content/builtin_metric_enables.json` that `builder.py` emits, wires
`build_bundle`'s dependency-audit gate into `build_discrete`, and fixes
`describe.py` to persist and honour the real `defaultMonitored` flag on
*properties* (previously hard-coded `True`).

## Checks re-run independently

| Check | Result |
|---|---|
| Content validate chain (7 CLIs) | **exit 0** |
| `python3 -m vcfops_packaging validate` | **OK — 13 release manifests valid, flag-state clean; 1 third-party project valid** |
| Fast test suite (`-m "not slow"`) | **629 passed, 4 skipped, 170 deselected** (matches tooling's claim) |
| Scoped slow suite | **did not complete inside the review window** — the `-k` scope pulls in SDK/Java `javac` pak builds. Not gating; the BLOCKINGs below are reproduced directly on the CLI against real corpus content. Tooling's "110 passed" claim is **unverified**. |
| No-op regression (empty `builtin_metric_enables`) | **CLEAN — proven.** `build_release` over all 13 manifests in a throwaway `git worktree` at `HEAD` vs the working tree; per-zip, per-member sha256 (excluding `vcfops_manifest.json:built_at`). All 10 content/bundle releases byte-identical member-for-member. The 3 SDK-pointer releases differ only because `content/sdk-adapters/` is gitignored and absent from the throwaway worktree — harness artifact, not a code diff. |
| Publish-path emission (scratch manifest, temp dir; `bundles/releases/` untouched) | **PROVEN.** A scratch release manifest declaring 2 entries, driven through `publish._build_one_release` → `build_release(skip_audit=True)`, produces `bundles/vm-snapshot-inventory/content/builtin_metric_enables.json` and the bundle.json `content.builtin_metric_enables` block. |
| Wire-key parity vs `builder.py` | **EXACT.** `discrete_builder.py:828-844` / `:921-935` emit character-identical dict shapes to `builder.py:151-166` / `:812-826` — `name` (= `metric_key`, the uninstall-name contract read by `templates/install.py:1530-1547` and `:1992`), `adapter_kind`, `resource_kind`, `metric_key`, optional `reason`. Same file path, same `indent=2`, same insertion position (after `reports`). `install.py` reads `manifest["content"]["builtin_metric_enables"]` generically, so the discrete `bundle.json` is consumed identically. |
| `pak-compare` | n/a — no pak surface touched. |
| Repo state left behind | Clean. One tracked file (`knowledge/context/adapter_describe_cache/VMWARE/VirtualMachine.json`) was mutated as a **side effect of running `build-discrete`** and restored with `git checkout` — see W5. |

## BLOCKING

### B1 — Newly-wired audit gate hard-fails on the documented `supermetric:"<name>"` view-column cross-reference

**Where:** `src/vcfops_packaging/discrete_builder.py:530-566` (new audit block,
`skip_audit=False` default) against `src/vcfops_packaging/deps.py:84-97`.

`_is_sm_ref()` recognises only `super metric|…` (`_SUPER_METRIC_PREFIX`,
deps.py:85) and the resolved `sm_<uuid>` form (`_SM_KEY_RE`, deps.py:84). It
does **not** recognise `supermetric:"<name>"` — the form CLAUDE.md's
"Cross-reference syntax" table documents for *View column → SM* and the form
that is still present on the loader objects at the moment the new audit runs.
`build_bundle` never hit this; the discrete path audits the **unresolved**
synthetic bundle, because SM resolution happens later inside
`render_views_xml(sm_scope=…)` — i.e. *after* the audit.

Reproduced (offline, against the committed cache):

```
$ python3 -m vcfops_packaging build-discrete dashboard \
    "[VCF Content Factory] CPU Support Status" --no-live-describe
AUDIT FAILED  The following metric keys were not found in the adapter describe cache:
  VMWARE/ClusterComputeResource  supermetric:"[VCF Content Factory] Cluster CPU Support Worst Status (KB318697)"
  VMWARE/HostSystem              supermetric:"[VCF Content Factory] CPU Support Status (KB318697)"
exit 1
```

Same failure for `"[VCF Content Factory] Quarterly Capacity Review"`
(`supermetric:"[VCF Content Factory] Cluster - Disk Usage % (percent)"`).

Both are **released, shipped, QA'd content** that built fine before this diff.
This is dimension 4 (loader/validator newly mis-validating previously-good
content) and dimension 7 (corpus regression).

**Smallest correct fix:** resolve SM references before the audit (mirror
`build_bundle`'s ordering), **or** extend `_is_sm_ref()` to also match
`^supermetric:` (case-insensitive). Add a regression test that
`build-discrete` succeeds on `[VCF Content Factory] CPU Support Status`.

### B2 — Newly-wired audit gate hard-fails on `instanced_group` view columns, including the very item this change exists to fix

**Where:** `src/vcfops_packaging/discrete_builder.py:530-566` against
`src/vcfops_packaging/deps.py:91` (`_INSTANCED_KEY_RE`) and `deps.py:167-193`
(`_refs_from_view`).

`_refs_from_view` walks `col.attribute` unconditionally. For `instanced_group`
columns the loader synthesises attributes that are **not** describe keys:

- the driver column yields the literal `Instance Name`;
- prefix/suffix columns yield `diskspace|snapshot:snapshot-16|<suffix>` — the
  instance token sits in the *middle* segment, and `_INSTANCED_KEY_RE`
  (`^([^|:]+):[^|]+\|(.+)$`) only normalises `group:instance|stat`, so nothing
  is stripped.

Reproduced, and it persists **after a full live describe refresh** (so it is
not a stale-cache problem):

```
$ python3 -m vcfops_packaging build-discrete dashboard \
    "[VCF Content Factory] VM Snapshot Inventory" --no-live-describe
AUDIT FAILED  The following metric keys were not found in the adapter describe cache:
  VMWARE/VirtualMachine  Instance Name
  VMWARE/VirtualMachine  diskspace|snapshot:snapshot-16|name
  VMWARE/VirtualMachine  diskspace|snapshot:snapshot-16|numberOfDays
  VMWARE/VirtualMachine  diskspace|snapshot:snapshot-16|used
  VMWARE/VirtualMachine  diskspace|snapshot:snapshot-16|creator
  VMWARE/VirtualMachine  diskspace|snapshot:snapshot-16|description
exit 1
```

The base keys resolve fine — `diskspace|snapshot|used` →
`MetricInfo(default_monitored=True)` — proving the instance token is the only
cause.

Authority: `content/views/vm_snapshot_inventory.yaml:43-92` (released
known-good, instanced fan-out documented in
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`).

**Blast radius, measured:** 3 of 7 discrete-buildable released headline items
now hard-fail on the default `build-discrete` path — `cpu-support-status-dashboard`,
`quarterly-capacity-review-dashboard`, and `vm-snapshot-inventory-dashboard`
(the fix's own target). `capacity-assessment-dashboard`,
`demand-driven-capacity-v2`, `vks-core-consumption-dashboard`,
`vks-core-consumption-report` still pass.

**Smallest correct fix:** in `_refs_from_view`, skip columns carrying an
`instanced_group` (they have no static describe key); optionally extend
`_INSTANCED_KEY_RE` to strip `:<instance>` from any segment. Add a regression
test that `build-discrete` succeeds on `[VCF Content Factory] VM Snapshot Inventory`.

> B1/B2 are only reachable because `build_discrete` defaults `skip_audit=False`.
> Defaulting it `True` would mask, not fix, the deps.py gaps — and would leave
> the same false positives latent for `--strict-deps` users. Fix deps.py.

## WARNING

- **W1 — The publish path this change exists to fix is untested.**
  All three new test files exercise `build_discrete` directly; none touches
  `release_builder._build_component_headline` or `build_release`
  (`grep build_release tests/test_discrete_builder_builtin_metric_enables.py` →
  a comment only). I proved the threading works by hand; nothing protects it.
  → Add an end-to-end test: release manifest with `builtin_metric_enables:` →
  `build_release` → assert the member and the bundle.json block.

- **W2 — The emission block is duplicated verbatim, with no parity test.**
  `builder.py:151-166`/`:812-826` and `discrete_builder.py:828-844`/`:921-935`
  are character-identical copies. Today they match; nothing keeps them
  matching. This is the shape of escape `6c59f6b` (key emission drifting from
  the reference without a guard). → Extract one `_render_bme_items(bmes)`
  helper, or add a test asserting both builders produce identical dicts for
  the same input.

- **W3 — `describe.py` docstring drift on its own persisted format.**
  `describe.py:28-33` still documents the `properties` cache entry as
  `{"name": …}` only, and `:35-38` still says properties "will not be checked
  until the cache is refreshed". `refresh()` (`:292-296`) now writes
  `default_monitored` and `instance_type`. The module docstring is the
  format-of-record for that file. → Update it.

- **W4 — The property blind-spot fix is 100% inert in-repo, and nothing WARNs.**
  All 7 `DescribeCache`-format cache files are legacy (`properties` entries
  carry `name` only), including three refreshed today
  (`fetched_at: 2026-07-27T15:58`). So every property resolves via the
  `default_monitored=True` legacy shortcut in `describe.py:181`, exactly as
  before, silently. Measured impact when the cache *is* refreshed:
  **97 of 251 VMWARE/VirtualMachine properties are actually
  `defaultMonitored=false`** — the shortcut is wrong for 39% of them, and the
  audit will report them as `resolved: … defaultMonitored=true` with no hint
  that it guessed. → Stamp a cache-schema marker on write and emit a one-shot
  WARN per kind-pair when the legacy shortcut is taken.

- **W5 — `build-discrete` now makes live calls and rewrites tracked repo files by default.**
  `live_describe=True` is the default, so a build command contacts the
  configured instance and rewrites
  `knowledge/context/adapter_describe_cache/<ak>/<rk>.json`. Observed during
  this review: a single `build-discrete` dirtied
  `VMWARE/VirtualMachine.json` (restored). This is parity with `build`, but
  combined with W4 it means build *output* can change from one run to the next
  with no code change (a refresh flips 97 properties to `false`, which in
  `auto` mode starts auto-adding entries and in `strict` mode starts failing).
  → At minimum document it in the `--no-live-describe` help text; consider
  defaulting `build-discrete` to cache-only.

- **W6 — The fix supplies the declaration slot but no detection.**
  `publish._build_one_release` → `build_release(skip_audit=True)` →
  `_build_component_headline(skip_audit=True)`. Nothing on the shipping path
  ever notices that a discrete release *needed* `builtin_metric_enables:` and
  didn't declare it — which is exactly how
  `vm-snapshot-inventory-dashboard` 1.0 shipped broken.
  `bundles/releases/vm-snapshot-inventory-dashboard.yaml` still declares none,
  so this change alone does not fix the shipped release. `load_release` also
  performs no unknown-top-level-key check, so a typo
  (`builtin_metric_enable:`) is silently ignored. This is parity with the
  bundle path, not a regression — but the failure mode remains silent.
  → Consider a release-time check, and note the content follow-up.

- **W7 — `reason` validation parity gap with `loader.py`.**
  `releases.py:311-316` coerces via `str(entry.get("reason", "") or "")`;
  `loader.py:245-249` **raises** on a non-string `reason`. The
  `releases.py:18-27` docstring claims "Same entry shape as the bundle
  manifest field". A YAML list/dict `reason` lands stringified
  (`"['a', 'b']"`) in the shipped JSON. → Mirror loader.py's type check.

## NIT

- **N1** — `discrete_builder.py:558` uses `__import__("sys").stderr` while the
  same block does `import sys as _sys` a few lines above (`:543`); `sys` is not
  imported at module top. Import it once at module level.
- **N2** — CLAUDE.md's "After tooling changes" stale-zip trigger list names only
  `src/vcfops_packaging/templates/`, `builder.py`, and
  `src/vcfops_dashboards/render.py`. `discrete_builder.py` and
  `release_builder.py` also produce dist zips. My no-op run proves no rebuild
  is needed *today*, but the list is incomplete. Orchestrator-owned (neither
  `tooling` nor this reviewer may edit CLAUDE.md).
- **N3** — No entry in `knowledge/context/defects.md` for the original escape
  (discrete release shipped without `content/builtin_metric_enables.json`).

## If shipped as-is

The publish/`build_release` path is safe and byte-identical for every existing
release, and the new field works end-to-end once declared. But the default
`build-discrete` CLI regresses from working to hard-failing on 3 of 7 released
headline items — including `[VCF Content Factory] VM Snapshot Inventory`, the
item this change exists to fix. Anyone (or any agent) invoking
`build-discrete` on SM-backed or instanced-group content gets `AUDIT FAILED`
with a message that blames a misspelled metric key and tells them to refresh
the describe cache — advice that does not help, because refreshing does not
clear it. The likely reaction is `--skip-audit`, which disables the gate the
change was meant to add.

---

# Round 2 — re-review of the revised diff (2026-07-27)

- **Area:** as round 1, plus `deps.py`, `loader.py`, `builder.py`
- **Verdict: APPROVE** — 0 BLOCKING / 3 WARNING (1 new, 2 carried) / 2 NIT
- Round-1 verdict was CHANGES REQUESTED (2 BLOCKING). **Both are fixed and
  independently reproduced as fixed.**

## Checks re-run (round 2, independently)

| Check | Result |
|---|---|
| B1/B2 reproductions | **All three now exit 0.** `build-discrete dashboard --no-live-describe` on `[VCF Content Factory] CPU Support Status` (refs 2, resolved 2), `… Quarterly Capacity Review` (refs 8, resolved 8), `… VM Snapshot Inventory` (refs 5, resolved 5) all print `built …`. `git status` clean afterwards — no cache mutation on the offline path. |
| No-op byte-identity, **re-run because `builder.py` changed** | **CLEAN.** `build_release` over all 13 manifests, fresh `git worktree` at `HEAD` vs revised tree, per-member sha256 (`built_at` excluded). All 10 content/bundle releases byte-identical member-for-member. Only the 3 SDK-pointer releases differ, again solely because `content/sdk-adapters/` is gitignored and absent from the throwaway worktree — harness artifact, identical to round 1. **The `render_bme_items()` extraction is a proven no-op.** |
| Fast suite | **631 passed, 4 skipped, 177 deselected** — matches tooling's claim (+2 fast, +7 slow vs round 1). |
| New test files, all markers (`-m ""`) | **32 passed** in 8.2s. |
| Validate chain | content CLIs **exit 0**; `vcfops_packaging validate` OK. |
| Publish path re-proof | scratch release manifest (temp dir; `bundles/releases/` untouched) → `publish._build_one_release` → zip still carries `content/builtin_metric_enables.json` + the `bundle.json` `content.builtin_metric_enables` block, byte-shape unchanged. |
| CI marker check | `.github/workflows/ci.yml:62` runs `--override-ini="addopts=" -m ""`, so the `pytestmark = pytest.mark.slow` on the new regression file **does** run in CI. No finding. |

## Round-1 findings — disposition

| # | Status |
|---|---|
| **B1** (`supermetric:"<name>"` treated as unknown metric key) | **FIXED.** `deps.py:86-93,102-109` adds `_UNRESOLVED_SM_REF_PREFIX = "supermetric:"` to `_is_sm_ref()`. Reproductions pass; pinned by `TestAuditGateRegressionRealContent::test_cpu_support_status_dashboard_survives_audit` and `…quarterly_capacity_review…` against real repo content. |
| **B2** (instanced_group synthetic attributes audited as describe keys) | **FIXED** (with a caveat — see W-new). `deps.py:191-201` skips columns carrying an `instanced_group`. Pinned at both dashboard and view level. |
| W1 (release path untested) | **FIXED** — `TestReleaseBuilderEndToEnd::test_release_manifest_with_bme_emits_section` drives `build_release`. |
| W2 (duplicated emission block) | **FIXED** — `loader.render_bme_items()`; both builders call it; `TestRenderBmeItemsParity` pins the literal wire shape *and* helper identity. Byte-identity re-run confirms no drift. |
| W3 (describe.py docstring drift) | **FIXED** — `describe.py:27-52`. |
| W4 (silent legacy-cache fallback) | **FIXED** — one-shot WARN per kind pair (`describe.py:194-206`), `_legacy_prop_warned` guard, 2 tests. Observed firing live for `VMWARE/HostSystem` and `VMWARE/VirtualMachine`. |
| W5 (live default + tracked-file rewrite) | **ACCEPTED as documented.** `live_describe=True` kept for `build_bundle` parity; `cli.py`'s `--no-live-describe` help now states plainly that the default contacts the instance, **rewrites the tracked cache files**, and that build output can therefore change between runs with no code change. That is a loud, documented decision, which per review dimension 8 is at most a WARNING. Reasonable — closed. |
| W6 (no detection of an omitted declaration) | **CARRIED** — see below. |
| W7 (`reason` validation parity) | **FIXED** — `releases.py` now mirrors `loader.py` exactly (non-empty-string required fields, non-string `reason` raises). |
| N1 (`__import__("sys")`) | **FIXED** — module-level `import sys`. |
| N2 (CLAUDE.md stale-zip trigger list) | **SATISFIED** by the orchestrator — `discrete_builder.py` and `release_builder.py` added. |
| N3 (defect registry) | **SATISFIED** — `DEF-016` added, correctly scoped, and it cites this review. |

## WARNING (round 2)

- **W-new — B2's fix trades a false positive for an audit blind spot, and the
  code comment overstates what remains covered.**
  `deps.py:191-201` skips `instanced_group` columns wholesale. The comment
  claims "The underlying base key (e.g. `diskspace|snapshot|used`) is audited
  separately when referenced directly." That is not true in general, and it is
  **not true for DEF-016's own metrics.** Measured on the real view:

  ```
  audited refs now: ['summary|parentCluster', 'summary|parentVcenter',
                     'summary|datastore', 'diskspace|snapshot']
  diskspace|snapshot|creator      -> resolves in cache (never audited)
  diskspace|snapshot|description  -> resolves in cache (never audited)
  ```

  `diskspace|snapshot|creator` and `…|description` are exactly the two
  `defaultMonitored:false` properties `DEF-016` names as the reason the
  dashboard ships with blank columns. They are reachable only through
  `instanced_group` columns, so the newly-wired gate structurally cannot
  detect the defect it was added to prevent — while
  `discrete_builder.py:530-535` asserts the gate exists so that a release
  "must fail loudly at build time rather than shipping silently broken."

  **Not blocking:** there is no regression versus `HEAD` (the discrete path
  had no audit at all, and `build_bundle` produced only false positives on
  these columns — no correct detection is lost), and DEF-016 tracks the
  manual declaration.

  **Smallest correct fix:** normalise rather than skip. The synthetic form is
  `diskspace|snapshot:snapshot-16|creator`; the base key is
  `diskspace|snapshot|creator`. Widening `_INSTANCED_KEY_RE` (`deps.py:96`) to
  strip a `:<instance>` token from *any* segment, instead of only a leading
  `group:instance|`, removes the false positives **and** keeps the base keys
  audited — which would have caught DEF-016 at build time. Correct the
  comment either way.

- **W6 (carried) — the shipping path still has no detection.**
  `publish._build_one_release` → `build_release(skip_audit=True)` →
  discrete builder skips the audit, and `load_release` performs no
  unknown-top-level-key check, so a missing or typo'd
  `builtin_metric_enables:` is still silent. Combined with W-new, DEF-016's
  remediation rests entirely on a human/agent remembering to declare the two
  entries in `bundles/releases/vm-snapshot-inventory-dashboard.yaml`. That
  declaration is **not yet present** — this diff alone does not fix the
  shipped release.

## NIT (round 2)

- **N-new** — `discrete_builder.py:722` builds
  `f"[VCF Content Factory] {display_name}.zip"` while `display_name` already
  carries the prefix, so direct CLI use emits
  `[VCF Content Factory] [VCF Content Factory] CPU Support Status.zip`.
  Pre-existing and unchanged by this diff (identical at `HEAD:652`); masked on
  the release path because `build_release` renames. Out of scope, worth a
  separate one-liner.
- **N-carried** — `discrete_builder.py:869` uses the deprecated
  `datetime.utcnow()` (DeprecationWarning surfaced by the new tests).
  Pre-existing.

## If shipped as-is

Safe. Every existing release builds byte-identically, the three previously
regressed `build-discrete` invocations pass, the shared helper is proven
inert, and the legacy-describe-cache guess is now loud instead of silent. The
residual risk is not in the code but in the process: nothing will *tell*
anyone that `bundles/releases/vm-snapshot-inventory-dashboard.yaml` still
declares no `builtin_metric_enables:`, so DEF-016 stays open until that
declaration is added and the zip rebuilt (per the CLAUDE.md trigger list this
diff just extended).
