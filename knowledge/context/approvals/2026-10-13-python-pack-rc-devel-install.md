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

## Outcome 2026-10-13, cluster-perf-risk

Installed 5:10 to 5:13 PM: /api/solutions lists Cluster Performance Risk
1.3.0; pak results all exit 0; the adapter conf carries ghcr.io,
/sentania-labs/cluster-perf-risk and the expected digest; the pack dashboard
imported. Account NOT created: the pack is a Python container adapter and
the Add Account page requires a Cloud Proxy; devel has none (only collector
is the primary, no container runtime). No image pull occurred at install (per the
SDK docs the pull happens on a proxy at first container start; not observed). Blocked until a Cloud
Proxy is paired to devel (lab-admin pipeline, Scott's go) or the proof moves
to an instance that has one. vsanhostmetrics will stop at the same point.

## Outcome 2026-10-13, vsanhostmetrics

Installed 5:25 to 5:28 PM: /api/solutions lists vSAN Host Metrics 1.4.6;
pak results all exit 0; adapter conf carries ghcr.io,
/sentania-labs/vsanhostmetrics and digest sha256:62577d09...ba25; all 7
dashboards and 30 views imported; the extra content/*.md and help HTML
files produced no installer warning. Both Add Account tiles report the
Cloud Proxy requirement; no account created. Both rc paks left installed on
devel. Side note for both packs: the bridge logged "Traversal specs root tag
should be 'AdapterKind'" at import because the SDK-generated
content/traversalspecs/ holds only the schema file; harmless, SDK
scaffolding behaviour.

## Close 2026-10-13

Scott, verbatim: "the python paks install on dv: red herring - there is not
cloud proxy so it won't work". The devel install proves only that the paks
import (solution, dashboards, views); account creation, the registry pull
and collection cannot be exercised without a Cloud Proxy and are not
pursued on devel. Both rc paks remain installed on devel with no accounts;
remove them whenever devel is tidied. The fork CI work is complete at the
publish level.
