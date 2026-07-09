# Design note — vcommunity (Tier 2 Java SDK rewrite)

## Initial prompt

> Let's talk about a plan to create a new tier 2 MP that is a rewrite
> of the vCommunity MP into a native java sdk pak. I don't think we
> need to make it "upgrade compatile" rewrite - thought that would be
> cool, but just get ride of the docker requirement.

Scope clarification turns (2026-06-10):

- v1 scope ("What's in scope for v1? The guest-ops chunk is the
  biggest single piece of work"): **"Full parity in v1"** — everything
  including Windows guest-ops in the first release.
- Content port ("How much of the bundled content do we port?"):
  **"Port everything now"** — all ~100 artifacts in v1 regardless of
  collector phasing.
- Naming: **"let's go with vCommunity - this is more an exercise in
  how strong/effective you can be with this as it is about creating
  lessons, etc. I think part of this should also be breaking
  dashboards and the like into yaml as references, to strengthen our
  MP pipeline."**
- Upgrade pak (follow-up turn): **"could we reimplement this as a
  true upgrade pak? it does exist on prod"** → explored empirically;
  ruled out (see
  `knowledge/context/investigations/vcommunity_upgrade_path_experiment.md` and
  `knowledge/lessons/cross-runtime-pak-upgrade-split-brain.md`). User then
  asked **"Is the upgrade option we are exploring to
  complicated/uneeded?"** — agreed to side-by-side + migration
  runbook.
- Config UX: **"there a shit ton of custom options and events - so
  an input file seems to make the most sense (as long as they don't
  have to be on all collectors...."** → pak-bundled default
  check-list files + optional `custom_config_dir` override on the
  hosting collector only.
- Report scope + final scope confirmation: **"we want to make this
  as close to a pure rewrite as possible so include them, as well as
  the config file/defaults behavior (for now)"** — port ALL reports
  including the generic "Report - VOA -" set; keep the original's
  config-file/defaults behavior.
- Build-gate decisions (post-build turn): pak-compare B1
  (two CredentialKinds vs compliance reference's one) — **"so 1> is
  just me acknowleding he new pattern (which would be needed if say
  we wanted to make a join enphase + franklinwh MP)?"** → yes;
  user ACCEPTS B1 as a reference-topology divergence (pending
  reviewer concurrence). Once installed/verified, vcommunity becomes
  the factory's 2-credential reference pak. Gap handling — **"2>
  lets get as far as we can and can close gaps in subsequent builds -
  so it's important to document them."** → v1 ships with documented
  gaps (event push degraded to properties; EMPIRICAL-VERIFY items
  smoke-tested at install); each gap must be durably recorded in the
  pak repo CHANGELOG/README and the design doc, with v1.1 items
  routed to `tooling` (SuiteApiStitcher.pushEvents).
- Config storage (follow-up turn): **"the config file has to be on
  teh running collector and not central?"** → re-checked the
  original: it stores config CENTRALLY in the Ops configuration-file
  store (`api/configurations/files?path=SolutionConfig/<name>.xml`,
  adapter.py:261), fetched via Suite API each cycle; instance fields
  hold file *names*. The rewrite matches that (pure-rewrite spirit):
  pak imports default XMLs centrally at install; six file-name
  identifier fields with defaults; no files on collectors. The
  earlier `custom_config_dir` on-collector design is dead.

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
  pipeline (and harvesting lessons/toolset gaps) is an explicit goal
  of this build, co-equal with shipping the pak.
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
