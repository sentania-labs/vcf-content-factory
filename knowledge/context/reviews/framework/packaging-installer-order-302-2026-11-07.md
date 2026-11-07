# Framework review: installer install order, custom groups before dashboards (#302)

- **Date:** 2026-11-07
- **Reviewer:** framework-reviewer (RULE-013)
- **Branch:** `worktree-agent-a5c7604a66aa6b1a9`, diffed against `main` (ce34da8)
- **Area:** `src/vcfcf_packaging/templates/install.py`, `install.ps1`; new `tests/test_installer_install_order.py`
- **Change:** custom groups move from `install_order` 4 to 1.5 in both distributed
  installers (after super metrics at 1, before the views+dashboards import at 2);
  order comments updated; a test pins the full order in both installers and their agreement.

## Verdict: CHANGES REQUESTED

1 BLOCKING / 1 WARNING / 2 NIT.

The reorder itself is correct and proven safe. The change is blocked only because it
does not bump the template version stamp, so every already distributed bundle keeps
reporting current.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (worktree, system `python3`, `PYTHONPATH=src`) | all seven rc=0 |
| `pytest tests/test_installer_install_order.py tests/test_install*.py` (covers both `test_install_ps1_*` suites; `pwsh` present, nothing skipped) | 273 passed |
| New test against `main`'s two templates (copied to a scratch tree) | `test_install_order[install.py]` and `[install.ps1]` FAIL at index 1 (`views_and_dashboards` != `customgroups`); the agreement test passes on main (both said 4), as it should |
| Full suite, worktree vs main checkout (src/tests identical to `main`), same interpreter, run side by side | worktree 15 failed / 3242 passed; main 9 failed / 3250 passed. The 9 are common to both (`test_common_doctor` x5, `test_common_setup` x1, `test_gap_b_f_d` x2, `test_dashboard_import_all_skipped` recursion x1). The 6 worktree-only failures are `test_release_naming_phase_v2_item1` x5 and `test_validator_phase2` packaging-validate x1, all failing on `content/sdk-adapters/synology/adapter.yaml` not found: the gitignored managed-pak clones the worktree lacks. None reads the installer templates. Tooling's "15 environmental" claim confirmed. (A first solo run showed 43, the extra 28 being `test_sdk_content_emit` and the same environment set; they did not recur on the rerun and do not touch the templates.) |
| PowerShell registry evaluated in real `pwsh` (registry block extracted, the installer's own `Where-Object`/`Sort-Object { $_.InstallOrder }` pipeline applied) | 1 Int32 supermetrics, 1.5 Double customgroups, 2 views_and_dashboards, 3 sm_enable, 3.5 Double builtin_metric_enables, 5, 6, 7. Mixed Int32/Double sort is numeric. |
| Render regression / pak-compare | n/a: no renderer, builder, or pak-structure change |

## What was proven safe

- **Float order values.** `install_order` / `InstallOrder` are read in exactly one place
  each: `active.sort(key=lambda e: e["install_order"])` (install.py:2863) and
  `Sort-Object { $_.InstallOrder }` (install.ps1:3824). Step numbering (`[n/N]`) is a
  running counter (`step += 1`, `$Step.Value++`), not derived from order values. No `%d`,
  `int()`, or format of an order value anywhere in `src/` (grep). 3.5 already proved the
  float path in both installers; the pwsh run above re-proves it for 1.5. No order
  collision: all eight install values are distinct.
- **State coupling.** `_install_customgroups` / `Install-CustomGroups` read only
  `bundle_dir`, `manifest`, `client`, and do a by-name GET then PUT/POST
  (`upsert_custom_group`, install.py:959). They read nothing the dashboard step writes
  (`imported_dashboards`, `advisories`), and the dashboard step reads nothing the group
  step writes. No ctx key is order-dependent between them.
- **Super metric dependency.** Groups still follow the SM import (1 < 1.5). They now run
  before `sm_enable` (3), which matches the factory syncer: `vcfcf_supermetrics` handler
  `sync` imports without enabling, `sync_order` SM 1 / customgroups 2 / views 3 /
  dashboards 4. The brief's "matches the factory syncer" claim holds.
- **`builtin_metric_enables` at 3.5.** Still after `sm_enable` (3) and before reports (5);
  the rewritten comment ("after sm_enable (3), before reports (5)") is now accurate where
  the old one ("and customgroups (4)") would have gone stale.
- **Uninstall order untouched.** The diff changes no `uninstall_order` / `UninstallOrder`.
  pwsh evaluation: dashboards 10, reports 15, views 20, alerts 35, supermetrics 40,
  builtin note 45, customgroups 50, symptoms 55, identical to main. Dashboards (which pin
  the group) are deleted before the group.
- **Failure shape.** A custom-group `_die` now stops the run after the SM import instead of
  after dashboards and enables. Every step is idempotent on rerun (upsert, content import),
  so the partial state is recoverable the same way as before.
- **Global-default leak / key collision (anchors 00d3382, 6c59f6b).** Not applicable:
  no renderer, default, or key derivation touched. The change is installer ordering only,
  and it applies the same way to every bundle, which is the intent.

## BLOCKING

**B1. Template version not bumped.**
`src/vcfcf_core/packaging/template_version.py:46` is still `"2026-10-28-2"`. Its docstring
(lines 7-9) requires a bump whenever `templates/install.py` or `templates/install.ps1`
changes, and `check-staleness` compares only this stamp from `vcfops_manifest.json`.
Without it, every bundle already distributed with the dashboards-before-groups installer
reports **current**, and no operator is prompted to pick up the #302 fix. This is
dimension 9's reports-green-while-broken class (provenance: PR #105).
**Fix:** set `CURRENT_TEMPLATE_VERSION = "2026-11-07-1"` and add a History line, e.g.
`2026-11-07-1  install.py / install.ps1: custom groups install at order 1.5, before the
views + dashboards import (was 4, after), so a View widget pinned to a helper group binds
at import (issue #302)`.

## WARNING

**W1. The wire-format doc still describes the bug as current behavior.**
`knowledge/context/wire-formats/view_widget_all_objects_of_kind.md:133-143` (Caveat 1,
"Install order differs by path") says the distributed installer imports dashboards at
`install_order: 2` and groups at `install_order: 4`, and "Installer reordering is tracked
as a separate issue." After this change that is false, and it is the authority an author
reads before shipping the pinned-group pattern. Tooling owns `knowledge/context/`.
**Fix:** rewrite Caveat 1 to say both paths now install groups before dashboards (syncer
`sync_order` 2 < 3/4; installers `install_order` 1.5 < 2, #302), pointing at
`tests/test_installer_install_order.py`. Leave Caveat 2 (pinned-to-group import unproven
live) standing: this change makes the order right but does not prove the binding, and the
doc's "do not ship the pattern in a distributed bundle until it has" still holds.
(Also, the caveat attributes the syncer order to `SYNC_CONTENT_TYPES`; the order actually
comes from each handler's `sync_order`, sorted in `discover_handlers`. Correct it while there.)

## NIT

**N1. Registry key docs still type the order as `int`.**
`install.py:1894` (`install_order  int`) and `install.ps1:2967` (`InstallOrder    int`).
Two of eight values are now fractional, and the new comments lean on 1.5 deliberately.
**Fix:** say `number` (int or float; sorted numerically) in both.

**N2. Uninstall is not the reverse of install for super metrics vs custom groups.**
Pre-existing, but in the entry this branch edits. install.py:1895 documents
"uninstall = reverse install order", and the syncer honors it (`unsync_order = 100 -
sync_order`: customgroups 98 before supermetrics 99). The installers delete super metrics
(40) before custom groups (50), so a group whose rule references a bundle SM briefly
outlives the SM. Whether Ops refuses or orphans that is unproven (no lesson covers it).
**Fix:** set customgroups `uninstall_order` / `UninstallOrder` to 38 (after alerts 35,
before supermetrics 40) in both installers, and extend the new test with an uninstall
order assertion (dashboards before customgroups before supermetrics; installers agree).

## Distribution zips

The change touches `src/vcfcf_packaging/templates/`, so per CLAUDE.md "After tooling
changes" every distribution zip is stale. `dist/` is gitignored, so the rebuild cannot
ride in this PR's diff; it is a mandatory `content-packager` rebuild of every manifest in
`bundles/` immediately after merge (or on the branch before `/publish`, which is what
actually ships zips). The PR body should say so. The version bump in B1 is what makes
already distributed copies announce they are stale; the rebuild alone does not.

## If shipped as-is

New zips get the correct order, but every bundle already in operators' hands keeps saying
it is current, so nobody is told to replace the installer that leaves pinned-group
dashboards deferred.
