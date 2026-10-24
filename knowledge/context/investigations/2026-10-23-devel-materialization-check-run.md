# Devel run of the post-import dashboard materialization check (2026-10-23)

Branch `fix/plumbing-233-235-216-232-154-158-166-165-167`, run from its worktree
with `PYTHONPATH=src`, profile `devel` (VCF Operations 9.0.2). Run 11:36 to 11:43
America/Chicago. Visual verification: SKIPPED (the Playwright MCP server failed to
connect: `CONNECTION_CLOSED`). No commits made.

## Result in one line

The check works on both paths (OK, STALLED with exit 1), with two departures from
the brief: the stderr lines carry a `WARNING: ` prefix, and a normal re-sync of
the factory content exits 1 for reasons unrelated to materialization.

## 1. Normal path (11:37)

`python3 -m vcfcf_dashboards sync --profile devel` over the 10 factory dashboards.
No WAIT occurred. Wall time 48 s.

stdout:

    MATERIALIZATION OK: 8 of 10 dashboard(s) finished building

stderr (two lines, exit-relevant):

    WARNING: MATERIALIZATION ABSENT: dashboard '[VCF Content Factory] Summary Widget Smoke (HostSystem)' (3797d639-4623-486e-8633-1f7ce823c57c) was in the import but is not on the instance afterwards. The importer can drop a whole dashboard silently (for example a widget type this Ops build lacks); check the instance.
    WARNING: MATERIALIZATION ABSENT: dashboard '[VCF Content Factory] VCF License Consumption Overview' (1b53e065-4319-4b09-8dd2-6da8b732f0e8) was in the import but is not on the instance afterwards. The importer can drop a whole dashboard silently (for example a widget type this Ops build lacks); check the instance.

Exit code: 1. Import itself was clean (VIEW_DEFINITIONS imported=26 failed=0,
DASHBOARDS failed=0, state=FINISHED). Exit 1 came from the dependency step, not
materialization:

    DEP-ERROR  cannot fetch SM '[VCF Content Factory] VCF Total License Usage (cores)' (c43ec7e3-...) from instance: get failed (404): ... "No such SuperMetric ..."
    (same 404 for 10 more license/NSX/Automation super metrics)
    DEP-ERROR  OOTB metric check: describe endpoint unreachable for CASAdapter/CAS World, sync marked incomplete (use --skip-metric-check to override)
    sync incomplete: dependency check found errors (see DEP-ERROR above)

Reading of the ABSENT lines (not separately verified on the instance):
- Summary Widget Smoke uses widget type `Section`, which needs 9.1.1 or later;
  `validate` warns the same (issue #199) and 2026-10-12-compliance-pak-summary-binding.md
  records the 9.0.2 importer dropping it. Expected on devel 9.0.2.
- VCF License Consumption Overview depends on the 11 license super metrics that
  the 404s show are not installed on devel (a prior `sync` of super metrics was
  not part of this run). Likely cause, not proven.

So the brief's expectation "dashboards already installed there" was not true for
these two, and "expect OK or SKIPPED" held only for the other 8. The check
correctly reported both as ABSENT.

## 2. Stalled path (11:38 to 11:42)

Read-only adapter-kind list on devel: 22 kinds, none matching vcommunity
(vcfcf_vcommunity_vsphere absent; present kinds include VMWARE, NSXTAdapter,
SupervisorAdapter, vcfcf_compliance).

Throwaway `content/dashboards/zz_qa_throwaway_stalled.yaml`, id
63a6f629-8e6a-4422-bf7b-5f8cc0711569, name `[VCF Content Factory] QA Throwaway
Stalled 2026-10-23`, one Scoreboard widget pinned to adapter kind
`vcfcf_vcommunity_vsphere`, resource kind `vCommunityWorld` (kind key taken from
the vcommunity-vsphere pak `describe.xml`; the pak's dashboards pin VMWARE, so
the pin shape came from a factory dashboard). `validate`: exit 0, 11 dashboards
valid.

The dashboards `sync` takes no file argument (only a global `--dashboards-dir`),
so the sync ran with `--dashboards-dir` pointing at a scratch directory holding
only the throwaway (views still synced: 26). First attempt at 11:39 hit import
task busy (`403 ... "Task is already running."`, exit 2); retried after 30 s and
it went through (the busy task was most likely the previous run's background work).

Run A (11:40, default checks, `--materialization-wait 20`), exit 1. stderr:

    WARNING: MATERIALIZATION STALLED: dashboard '[VCF Content Factory] QA Throwaway Stalled 2026-10-23' is installed but cannot finish building: it is waiting on vcfcf_vcommunity_vsphere, which is not installed on this instance. Its widgets that use those resource kinds stay empty until the adapter is installed; re-importing does not help.
    DEP-ERROR  OOTB metric check: describe endpoint unreachable for CASAdapter/CAS World, vcfcf_vcommunity_vsphere/vCommunityWorld, sync marked incomplete (use --skip-metric-check to override)
    sync incomplete: dependency check found errors (see DEP-ERROR above)

Because Run A had a second cause for exit 1, Run B (11:42, same plus
`--skip-metric-check`) isolates the materialization exit code. Exit 1, stderr
was the STALLED line alone (identical text to Run A, no other output). So
STALLED alone returns exit 1, as described.

## 3. Cleanup (11:43)

- `delete-dashboard --profile devel "[VCF Content Factory] QA Throwaway Stalled 2026-10-23"`: exit 0 ("Deleting 1 dashboard(s) ... done").
- Gone confirmed: a second `delete-dashboard --dry-run` of the same name returned exit 1, "dashboard not found by name".
- YAML removed from the worktree; `git status --short` there is empty.
- Views imported by the runs are the factory's own and were already installed (idempotent); not deleted.

## Departures from the brief

1. Lines are `WARNING: MATERIALIZATION <STATE>:` on stderr; the OK line has no
   WARNING prefix and goes to stdout. A grep for a line starting with
   `MATERIALIZATION` misses the warning states.
2. A plain re-sync of the factory dashboards on devel exits 1 (missing license
   super metrics, CAS World describe endpoint unreachable), independent of the
   materialization check. Anyone gating on the exit code needs to know which
   cause fired.
3. No WAIT state was exercised: nothing was building after the first export.
4. The "OOTB metric check" fails for any pin to a kind the instance lacks
   (`describe endpoint unreachable`), so STALLED is usually accompanied by a
   DEP-ERROR in the default flow.
