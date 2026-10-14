# Approval: squash the two fork CI branches to one commit each and force-push

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "I wish the PRs had been squash merge of our work but whatever."
  then, offered a squash and force-push of the fork branches: "Do that don't
  comes over to them as a single commit"
- **Scope:** sentania-labs/vsanhostmetrics branch `tuneup/ci-ghcr-attestation-main`
  (seven commits on nickfirefoot main ee2c575, upstream PR #1) and
  sentania-labs/cluster-perf-risk branch `tuneup/ci-ghcr-attestation` (four
  commits on gillaspy main 6aa3e10, upstream PR #5): reset to the upstream base,
  one commit each with the combined message, `git push --force-with-lease` to
  our fork only. Tree content unchanged. Nothing else force-pushed.
