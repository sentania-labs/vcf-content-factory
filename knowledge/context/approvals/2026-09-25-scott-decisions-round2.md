# Owner decisions, 2026-09-25 (round 2)

Scott's verbatim answers to the second pending-decisions list of
2026-09-25. Recorded before the actions run, per the owner rule that
destructive and outward-facing actions need his words preserved. Round 1
is `2026-09-25-scott-decisions.md`.

1. Approve the UniFi/Synology dashboard mocks
   (`knowledge/designs/dashboards/unifi-synology-index.html`: 6 general
   and 20 Summary dashboards, 14 views, 1 super metric) so authoring can
   start (RULE-011).
   > Mocks look good.
2. Approve the "PoE budget used %" super metric
   (`knowledge/designs/supermetrics/unifi-switch-poe-budget-used-pct.md`).
   > Yes.
3. File issues: UniFi adapter should collect UniFi's rate fields; Synology
   adapter pool/volume capacity, disk remaining life and LUN latency;
   alerts for both packs; the missing certificate hostname check on the
   framework collection path; the scaffold digit-leading class name and
   `composer.py` `rstrip("s")` bugs.
   > File them.
4. Devel stale certificate: re-validate the vcf-lab-mgmt vSAN account in
   the UI first so the expired vcf-lab-vcenter-mgmt certificate can be
   deleted, or force the delete.
   > Done
   (Read as: Scott re-validated the vSAN account; the non-forced delete
   approved in round 1 item 3 proceeds.)
5. Compliance #28: rewrite public git history to remove the proprietary
   jars (force-push), or only remove the dead code.
   > WHat's this?
   (Not decided; explanation owed. No history rewrite.)
6. Where the defect gate lives (#153 / #180).
   > Keep it in the pak CI

## Later the same day

7. Merge the framework PRs #183 (certificate-accept hook, allowInsecure
   pulldown, #174) and #184 (pipeline hardening), both framework-reviewer
   approved and Codex-reviewed.
   > 183/184 merge them
8. Compliance #28 follow-up question.
   > #11 - what jar?
   (Explanation owed; no action.)
9. Compliance #28: rewrite the public compliance repo's git history to
   remove `lib/vim25.jar` and `lib/vim-vmodl-bindings-8.0.2.jar` from every
   commit and force-push, with the plan presented: mirror backup first,
   git filter-repo on those two paths only, release workflow disabled and
   main force-push protection lifted only for the push, all branches and
   the 7 tags pushed, protection and workflow restored, releases and CI
   verified, PR #35 rebased, local clone reset, GitHub Support ticket
   drafted for the 12 refs/pull references. Scott's context: "they aren't
   hard to find, so it probably falls into a grey area, and I lean towards
   rewriting them, especially sine we just pulled back the VDDK."
   > DO the rewrite
   (First force-push attempt at 2:18 PM was denied at the permission check;
   protection and workflow were restored with nothing pushed.)
   > YOu can proceed
10. Standing merge rule for open PRs (factory #188, compliance #35,
    runtime #6 and PRs from this work stream): merge once Codex gives a
    thumbs-up, or once its findings are addressed.
    > merege on thumbs up or after addressing the findes
