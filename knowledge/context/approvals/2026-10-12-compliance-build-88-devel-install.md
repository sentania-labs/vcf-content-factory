# Scott's go: compliance build 88 on devel

Date: 2026-10-12 (America/Chicago).

Asked: install `dist/vcfcf_sdk_compliance.0.0.0.88.pak` (sha256
`5e253764062df190c6278d440ca803d9d769e467d84862832f5634e54fafa641`, built
3:54 PM from adapter commit `936e1fa` on
`feat/build-88-rollup-unmatched-pod-skip`) on devel, replacing build 87.
Build 88 carries: AlertList widgets on the alert type filter 15_21 with
per-widget depth; rollup counts only objects with a VCF Ops resource, with
per-kind `Rollup|<Kind>|unmatched` and `Rollup|VM|skipped_pods`, vSphere
Pods (crx guest id) skipped; the Compliance World Summary dashboard bound
to the ComplianceWorld Summary tab; Suite API resource list paged and
verified (DEF-023). Review: `knowledge/context/reviews/compliance-build-88.md`
(APPROVE, all findings closed). Rollback is reinstalling build 87.

Scott (verbatim):

> yes install 88 on devel

Earlier today, on the rollup fix: "Option 1."; on the summary dashboard:
"not a wireframe, html mockup, but go."; and the hold: "nothign until we
figure out the math problem."

Scope: devel only; this pak. Not a go for prod, a PR merge, a `v*` tag,
or any change to adapter instance settings.
