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

## Update 2026-10-13 evening: the mechanism works; devel is the broken instance

Scott: "check it out" on a vendor note naming first-party paks that ship
`dashboards.properties`. Findings
(`2026-10-13-first-party-summary-binding.md`):

- On devel 9.0.2 the vSAN pak's bound clone is complete: its import won the
  same race we lose, because it was installed at first boot before the admin
  account had dashboards the server can never finish. Devel now carries ten
  such dashboards (six stock cost dashboards referencing Azure kinds, Rubrik,
  cluster-perf-risk, our MSSQL and Oracle ones), which keep the admin's
  materialization thread in ten-minute sleeps, so every pak import on devel
  clones an unmaterialized source. Nothing in our JSON, layout, flags or
  folder changes that.
- On qa/prod 9.1.1 all 73 first-party bound clones are complete even with
  five stuck admin dashboards, so on 9.1.1 the binding is not a race; the
  9.1.1 installer or importer differs (being read now).

Consequences for the parked items: the #200 tooling branch stays parked (a
factory rebind is still only a workaround for 9.0.2); the `summary_for`
binding stays in the pak; the adapter post-install script idea is still the
only in-pak fix for a 9.0.2 instance in devel's state. Open decisions for
Scott: install build 93 on qa to prove our clone on 9.1.1; clean devel's ten
unfinishable dashboards so devel stops losing the race.
