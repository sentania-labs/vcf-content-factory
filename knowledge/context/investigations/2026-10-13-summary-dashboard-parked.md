# Stake: pak-bound Summary dashboards, parked 2026-10-13

Scott, verbatim: "let's park the summary dashboard line of thought for now -
put a stake in it". Earlier the same day: "if we install a pack it shoudl
bind the summary dashboards. I thought we had solved this problem".

## Where it stands

- **The pak binds, the clone is blank.** On VCF Operations 9.0.2 (devel) a
  pak's `dashboards.properties` binding runs, but the installer clones the
  dashboard seconds after import while every widget is still deferred, and
  nothing on an on-prem 9.0.2 instance ever finishes the clone. The Summary
  tab shows stock widgets inside our layout with an hourglass on each.
  Deferral is unconditional; no JSON form or import flag avoids it.
  Evidence: `2026-10-13-compliance-summary-clone-config-loss.md`,
  `2026-10-13-dashboard-import-deferral-trigger.md`,
  `../api-surface/summary_dashboard_pak_binding.md`.
- **Build 89 proved the other half.** Dropping the `Section` widget (absent
  on 9.0.x) let the World Summary import; lesson
  `../../lessons/unknown-widget-type-aborts-pak-dashboard-import.md`.
- **Nobody else does this.** No shipped pak on the three appliances binds a
  Summary dashboard; the field convention is to ship a dashboard named
  Summary and let the admin bind it via Manage Summary Dashboards.
  Broadcom's own objects use compiled pages or a plugin path closed to
  third parties.
- **The HostSystem smoke test on qa 9.2 bound after materialization** with
  the factory's `bind-summary`, which is why it worked. Whether 9.1 and 9.2
  installs lose the same race is unknown.

## What exists, in what state

| Thing | State |
|---|---|
| World Summary dashboard in the compliance pak (build 89 and 90) | Ships with `summary_for`; the install-time clone is blank on 9.0.2. Decision pending on whether to keep `summary_for` or drop it and document the manual bind. |
| Devel ComplianceWorld Summary tab | Blank clone `4cfb2eb2`. Fix is one `bind-summary` run after the source is materialized (needs Scott's go). |
| Factory branch `fix/200-bind-summary-after-materialization` (worktree `vcf-content-factory-wt200`) | Materialization wait helper, bind-summary refusal with `--wait` / `--force-deferred`, opt-in `install --rebind-summary`. Framework review CHANGES REQUESTED (1 B / 7 W / 6 N, report in `reviews/framework/`); fix pass stopped before any edit; empty marker commit `671eb1f` lists all 14 open findings in its message. Not pushed, no PR. Orchestrator side (content-installer prompt, assignment doc synopsis) not done. |
| Only in-pak route | `adapter_post_script` in the pak manifest calling the appliance's own summary-template import (ops-cli). Three links unverified: ops-cli exposes it on 9.0.2; imports finish before the script phase; the template renders. The read-only checks were stopped when parked. |
| Factory issue #200 | Open; carries the go for the tooling fix and should get this stake as a comment. |

## To resume

1. Decide the pak policy: keep `summary_for` (and pursue the post-install
   script) or drop it and document the manual bind in docs/installing.md.
2. If pursuing the script: run the three checks above, then one disposable
   install.
3. Finish the #200 branch from the review report, orchestrator items
   included, re-review, PR.
4. Rebind on devel either way so the demo tab is not blank.
