# Framework review: customgroups loader `all_of_kind` + View self_provider pin guard

- Date: 2026-10-28
- Branch: `customgroup-all-of-kind` (ac08713, 1ba4065) vs origin/main 2cac2c7
- Reviewer: framework-reviewer
- Verdict: **APPROVE** (0 BLOCKING / 2 WARNING / 3 NIT)

## Scope

`src/vcfcf_core/customgroups/loader.py` (`_validate_rule`: `all_of_kind`
opt-in), `src/vcfcf_core/dashboards/loader.py` (`Dashboard.validate`: View
`self_provider` requires `pin`), `tests/test_all_of_kind_helper_group.py`,
docs (`customgroup_authoring.md`, `wire-formats/view_widget_all_objects_of_kind.md`,
`customgroup-author.md`, `vcfops-content-model/SKILL.md`).

## Checks re-run

- Seven-package validate chain (content/sdk-adapters symlinked from the main
  checkout for the run, removed after): all rc=0. Only the pre-existing
  name-length / Section warnings.
- Full suite: 3253 passed, 9 skipped, 131 deselected, 0 failed.
- Render regression: no emitter touched (`to_wire`, `to_ui_wire`, `render.py`
  unchanged); the change only alters which YAML validates. Clean by construction.
- pak-compare: n/a (no builder/template change).
- Stale-zip / `CURRENT_TEMPLATE_VERSION`: no file on the trigger list touched; no bump needed.

## What was proven safe

1. **Wire, REST path.** `to_wire` for an `all_of_kind` rule emits all five
   condition arrays as `[]`, identical to the 201-accepted body in the wire
   doc §3 apart from `resourceKey.resourceIdentifiers: []`, which `to_wire`
   emits for every group already in the corpus and which installs today.
   The test asserts the whole dict, so absent-vs-empty drift would fail it.
2. **Wire, UI path.** `to_ui_wire` ruleGroup is `{resourceKind, adapterKind,
   rules: []}`, byte-equivalent to
   `reference/references/vmbro_vcf_operations_hardware_vcommunity/Management Pack/content/customgroups/Dell EMC Servers.json`
   (only localization/display order differ, pre-existing for all groups).
3. **No leak into wire.** Both emitters pick keys explicitly; `all_of_kind`
   never appears in output (probed, plus the full-dict test assertions).
4. **Downgrade paths.** `all_of_kind: false` + no conditions fails;
   `"true"`, `1`, `"yes"`, `null` fail as non-bool; `all_of_kind_s` typo with
   no conditions fails on the at-least-one-condition check. All loud.
5. **Distribution install path.** `install.py` `_install_customgroups` posts
   the REST payload from `to_wire`; the UI-import `customgroup.json` comes from
   `to_ui_wire`. Both carry the proven empty-rule shape.
6. **New View check vs corpus.** Scanned every dashboard YAML in `content/`,
   `third_party/`, `content/sdk-adapters/*` and the main checkout's
   uncommitted `content/dashboards/`: 74 View widgets, exactly one hit,
   `content/dashboards/application_allocation_summary.yaml` widget
   `app_allocation` (expected). Reference ground truth: 379 self-provider View
   widgets across `reference/references/**`, **zero** without a
   `config.resource.resourceId`, so the guard matches vendor behavior and
   rejects nothing a known-good export would produce.
7. **Extractor / round trip.** `vcfcf_extractor` does not extract custom
   groups (Phase 1 WARN only, `extractor.py:835`), so no reverse path meets an
   empty rule and none needs to emit `all_of_kind`. `reverse.py` View branch
   (`:1363-1386`) omits `pin` with a WARN when it cannot resolve
   `config.resource`; such a reversed dashboard now fails validate loudly
   instead of rendering `selfProvider:false` silently. That is the intended
   direction (silent downgrade became loud) and no reference export hits it.
8. **Escape anchors.** No pak-local default or global-path behavior
   (`00d3382`); no key/label derivation (`6c59f6b`).

## WARNING

### W1. Mutual exclusion is defeated by a misspelled condition key
`src/vcfcf_core/customgroups/loader.py:191-199`. `has_conditions` only looks
at the five known keys and `_validate_rule` ignores unknown rule keys. Probe:
`all_of_kind: true` plus `properties: [{key: x, op: EQ, value: y}]` (typo of
`property`) **loads**, the condition is dropped, and the group matches every
object of the kind. Before this change the same typo with no `all_of_kind`
failed; with the opt-in present it is silent. The docs
(`customgroup_authoring.md`, agent prompt) promise "rejects `all_of_kind: true`
combined with any condition", which this case breaks. Authority: shared
reviewer doctrine (silent downgrade), CLAUDE.md "never silently downgrade".
Fix: reject unknown rule keys (allow-list `resource_kind`, `adapter_kind`,
`all_of_kind`, `stat`, `property`, `name`, `relationship`, `tag`). Corpus
check: every rule in content/, third_party/, sdk-adapters uses only
`resource_kind`, `adapter_kind`, `property`, `stat`, so the allow-list rejects
nothing existing. Add a test for the typo case.

### W2. The recommended pattern is unproven end to end and the distribution installer runs in the opposite order
The wire doc (§3) says the helper group "must exist with that exact name
**before** the dashboard imports, or the dashboard sits stuck-deferred", and
admits the pinned-dashboard import was never live-verified. Factory sync
honors that (`syncer.py:54`, customgroups before dashboards), but the
distributed `install.py` imports views+dashboards at `install_order: 2`
(`templates/install.py:2714`) and custom groups at `4` (`:2751`);
`install.ps1` follows the same sequence (`Install-Dashboard` before
`Install-CustomGroups`). Whether binding happens at import or at
materialization (~2 min, `knowledge/lessons/dashboard-import-deferred-materialization.md`)
is unknown, so a bundle shipping helper group + pinned dashboard may land
stuck-deferred on exactly the global install path. Also: `pin.name` on a
non-singleton kind (`Container/Environment`, many groups) is the
"unverified" case in `wire-formats/dashboard_view_pin_resolution.md`;
vendor export evidence supports it, a live import does not yet.
Fix (this branch, docs only): state both caveats in the wire doc and the
`customgroup_authoring.md` paragraph (factory sync order is fine; bundle
installer order is dashboards-first and unproven), and require the first use
to be live-verified (dashboard materializes with a concrete `resourceId`)
before it ships in a bundle. Installer reordering is untouched code: open a
follow-up issue.

## NIT

- N1. `tests/test_all_of_kind_helper_group.py`: no case for explicit
  `all_of_kind: false` with no conditions or `all_of_kind: null`; both behave
  correctly (probed), add them to B so the contract is pinned.
- N2. `knowledge/context/README.md` index row for
  `view_widget_all_objects_of_kind.md` exists only as an uncommitted change in
  the main checkout, not on this branch. Commit it with the branch.
- N3. `src/vcfcf_core/customgroups/loader.py:182` comment cites the wire doc
  for "empty condition lists, 201"; the UI path's evidence (vendor Dell EMC
  export) is not cited there. Add it so both proven paths are referenced at
  the code.

## If shipped as-is

Content authoring works and both wires match proven shapes; an author who
pairs `all_of_kind: true` with a typo'd condition gets a silently over-broad
group, and a bundle shipping the helper-group pattern may import its dashboard
before the group exists on an operator's instance.
