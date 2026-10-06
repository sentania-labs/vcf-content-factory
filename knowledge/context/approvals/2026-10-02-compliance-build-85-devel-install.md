# Scott's go: 5 minute collection interval, compliance build 85 on devel

Date: 2026-10-02 (America/Chicago).

Context: build 84 on devel proved the ComplianceWorld computed environment
totals evaluate correctly but surface one collection cycle late, and the
pak's interval was 60 minutes. Scott, verbatim:

> let's go to 5 minutes and see where we land.

Build 85 (`dist/vcfcf_sdk_compliance.0.0.0.85.pak`, sha256
`9b0d22a9607a2e8f5f53c7ca707065370869aba518e4e9ef1296d463a7209fa7`):
monitoringInterval 60 to 5; esxcli result cache cleared every cycle
(correctness fix found during the interval audit: results were cached for
the life of the vCenter session); cycle wall time in the summary log line;
two build 84 review nits. Install gate:
`knowledge/context/reviews/compliance-build-85.md` (APPROVE, 0 BLOCKING).

Scope: devel only, this pak. Not a go for prod, a commit, a PR merge, a
`v*` tag, or any change to a devel host's configuration (the reviewer's
live drift proof, checklist step 5, needs its own go).
