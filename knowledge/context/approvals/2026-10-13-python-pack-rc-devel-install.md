# Approval: install the fork-built Python packs on devel

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "no upstream PRs yet. fully back them and install them to devel"
  (read as: complete both fork CI builds, install both rc paks on devel; no
  pull requests to the upstream authors yet)

## Scope this covers (devel only)

- Install `dist/ClusterPerfRisk_1.3.0.pak` (fork release v1.3.0-rc.1, image
  digest sha256:f995d453...5e51 on ghcr.io/sentania-labs/cluster-perf-risk,
  attested and signed) on devel; create one adapter account with the pack's
  defaults (it has no credential); verify the Cloud Proxy pulls the image
  from GHCR, the account collects, and the pack's content imports.
- Install the vsanhostmetrics rc pak the same way once its fork tag run
  succeeds; its account needs a vCenter credential (use the same lab
  vCenter account the compliance instances use, entered in the UI, never
  printed).
- Uninstall is not covered; leave both installed and report.

## Not covered

- Upstream pull requests, prod or qa, any change to existing accounts.
