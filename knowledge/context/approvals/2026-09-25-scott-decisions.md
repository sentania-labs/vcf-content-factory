# Owner decisions, 2026-09-25

Scott's verbatim answers to the pending-decisions list of 2026-09-25
(session on the mini-app recon, issue assessments, compliance README and
UniFi/Synology dashboards). Recorded before any destructive or
outward-facing action is executed, per the owner rule that such actions
need his words preserved as an artifact.

The numbered items are the question as put to him; the quoted line under
each is his answer, unedited (typos kept).

1. Build the certificate-accept hook in the framework (tooling, then
   framework-reviewer, buildkit release, one-method opt-in per pak, test
   on devel).
   > Yes, proceed, we should also change this option from a string to a pulldown.
2. Fix #174 (REQUESTS_CA_BUNDLE overriding VERIFY_SSL=false) in the same
   tooling round.
   > Yes
3. Delete the stale accepted vcf-lab-vcenter-mgmt certificate on devel
   (expired July 6), the likely cause of the red banner.
   > Yes
4. Set Allow Insecure = true on the new prod compliance account.
   > (no answer; not done)
5. Blur lab hostnames and VM names in the README screenshots.
   > It's my lab, don't worry about it
6. Commit, push and open a PR for branch docs/readme-human-rewrite in the
   compliance repo.
   > Yes
7. File the five compliance dashboard defects as issues.
   > Yes
8. to 11. Compliance pak issues: build 81 scope; builds 82 to 84 plan;
   close #7 and fix #22 docs; #28 proprietary jars in public git history
   (rewrite history with a force-push, or leave history and only remove
   dead code).
   > Yes to all compliance pak issues
   Note: item 11 was an either/or; this answer does not pick one, so no
   history rewrite is executed until he chooses explicitly.
12. Where the defect gate lives.
   > I need to understand this better
13. Run the pipeline-hardening round (#181, #153, -proc:none, buildkit
   1.0.11 with published checksum), template first, then all six paks.
   > Yes
14. Unblock vcommunity-vsphere#22 (close or downgrade DEF-020 and DEF-021),
   then tag.
   > Yes unblock it, i'm not really interested in progressing the vcommunity stuff, it was mostly an exercise, so can we jsut silence it until I pick it up
15. Template code fixes #8, #14, #15, #16, #9; carry #8 into synology and
   unifi with a release note.
   > yes
16. Owner actions: runtime#4 confirm PAT revoked; runtime#2 delete the
   duplicate jar release asset; branch protection on runtime main.
   > Yes, done/proceed
17. Update tracker #182 with the agents' corrections.
   > Yes, approved
18. dashboard-author writes pak-bundled dashboards into each pak's
   dashboards/ folder (#173).
   > Yes
19. Summary dashboard layout.
   > I'd say one shared layout, as long as it provided meaningful information about the object.
20. General dashboards per pack.
   > OK, let me know when the mocks are ready
21. Commit the new findings docs.
   > yes
