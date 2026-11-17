# Design note — vcommunity (Tier 2 Java SDK rewrite)

## Request and decisions

Goal: plan a Tier 2 MP that rewrites the vCommunity MP as a native Java
SDK pak, removing the Docker requirement. Upgrade compatibility with the
original is not required.

Scope decisions (2026-06-10 and follow-up turns):

- v1 scope: full parity in v1, including Windows guest-ops.
- Content port: port all ~100 bundled artifacts in v1, regardless of
  collector phasing, by converting them to factory YAML as references
  that also exercise the factory's MP content pipeline.
- Naming: vCommunity.
- Upgrade pak: whether the rewrite could be a true upgrade pak for the
  installed original was explored empirically and ruled out (see
  `knowledge/context/investigations/vcommunity_upgrade_path_experiment.md` and
  `knowledge/lessons/cross-runtime-pak-upgrade-split-brain.md`); the
  decision is side-by-side install plus a migration runbook.
- Config UX: the original has many custom options and events, so they
  are driven by input files rather than instance fields, and the files
  must not have to live on every collector.
- Report scope: stay as close to a pure rewrite as possible; port all
  reports, including the generic "Report - VOA -" set, and keep the
  original's config-file and defaults behaviour.
- Build-gate decisions (post-build): pak-compare B1 (two
  CredentialKinds vs the compliance reference's one) is accepted as a
  reference-topology divergence (pending reviewer concurrence); once
  installed and verified, vcommunity becomes the factory's
  2-credential reference pak. Gap handling: v1 ships with documented
  gaps (event push degraded to properties; EMPIRICAL-VERIFY items
  smoke-tested at install); each gap is recorded in the pak repo
  CHANGELOG/README and the design doc, with v1.1 items routed to
  `tooling` (SuiteApiStitcher.pushEvents).
- Config storage: re-checking the original showed it stores config
  centrally in the Ops configuration-file store
  (`api/configurations/files?path=SolutionConfig/<name>.xml`,
  adapter.py:261), fetched via Suite API each cycle, with instance
  fields holding file *names*. The rewrite matches that: the pak
  imports default XMLs centrally at install, six file-name identifier
  fields carry defaults, and no files live on collectors. The earlier
  `custom_config_dir` on-collector design is dead.

## Vision

- Native **Tier 2 Java SDK** rewrite of
  `vmbro/VCF-Operations-vCommunity` (Onur Yuzseven, CC-licensed,
  mirrored at `reference/references/vmbro_vcf_operations_vcommunity/`). The
  whole point is killing the Python Integration SDK's
  Docker-on-Cloud-Proxy runtime; the adapter runs natively in the
  collector like the compliance adapter does.
- **Full collector parity in v1**, both mechanisms:
  - Pure vCenter SOAP (vim25): cluster DRS/HA/EVC properties +
    metrics, host advanced settings / install date / licensing / VIB
    packages / NIC uplinks, VM config / extra-config / SCSI
    controller / snapshot metrics. Config-file-driven check lists
    (the `solutionconfig/*.xml` user-editable files) carry over as a
    feature.
  - Guest-ops: Windows service status, guest OS info, Windows event
    logs via vCenter `guestOperationsManager` (file transfer +
    run-in-guest, Windows credential kind required).
- **No new object types** — ARIA_OPS-style stitching onto existing
  VMware adapter Cluster / Host System / Virtual Machine resources,
  same as the original. Keep the **`vCommunity|` property/metric key
  namespace** so ported content works mechanically and users coming
  from the Docker MP keep metric continuity. (Upgrade compatibility
  is explicitly NOT a requirement; key-namespace continuity is a
  cheap win, not a contract.)
- **Port all bundled content** (~50 super metrics, 12 dashboards,
  ~35 reports/views, 2 symptoms + 3 alerts) — and do it by
  **converting to factory YAML as the canonical source**, rendered
  into the pak by the factory pipeline. Strengthening the MP content
  pipeline is a goal of this build alongside shipping the pak.
- Repo: `sentania-labs/vcf-content-factory-sdk-vcommunity` from the
  sdk-template; one line in `knowledge/context/managed_paks.md`; official
  release is CI on a `v*` tag. Display name: prose prefix per
  convention. Attribution to Onur Yuzseven /
  `vmbro/VCF-Operations-vCommunity` in MP and content descriptions.
- Known design questions to resolve in the designer interview:
  - Adapter kind key: must NOT collide with the original
    (`VCFOperationsvCommunity`) if both can be installed side by side.
  - Foreign-resource **metric/stat and event push**: proven pusher is
    property-shaped; confirm or gap-report the stats/events path.
  - Content name collisions with an installed original MP.
