# Scott's go: install compliance build 84 on devel

Date: 2026-10-02 (America/Chicago).

Asked: install `dist/vcfcf_sdk_compliance.0.0.0.84.pak` (sha256
`1185dcec1c064cce11430411883b3be0901d704b8052d28006fd56d47e31415f`) on
devel, replacing build 79. Adds four engine-computed environment totals
on ComplianceWorld and links each vCenter's VMwareAdapter Instance as a
ComplianceWorld child. Super metrics, dashboards, per-vCenter rollups and
collection unchanged. Rollback is reinstalling build 79; the relationship
edges would remain.

Scott (verbatim):

> install to devel

Scope: devel only, this pak only. Not a go for prod, for any commit or PR
merge, or for a `v*` tag.

Design: `knowledge/designs/sdk-adapters/compliance-environment-computed-metrics.md`.
Install gate: `knowledge/context/reviews/compliance-build-84.md` (APPROVE,
0 BLOCKING).
